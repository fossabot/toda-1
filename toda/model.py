from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
import re
from os.path import abspath, dirname, exists, expanduser, join, normpath
from typing import ClassVar, Iterable, Iterator, TextIO

from .errors import ManifestError, SectionNotFound

log = logging.getLogger(__name__)

Section = dict[str, "str | tuple[str, ...]"]

MANIFEST_ENV_VAR = "TODA_MANIFEST"
MANIFEST_FILENAME = "MANIFEST"

# A `:` right after a single drive letter at the start of a path (`C:\`,
# `C:/`) is part of the path, not the dest/src separator.
_DRIVE_LETTER_COLON = re.compile(r"(?:^|(?<=\s))[A-Za-z]:[\\/]")

# Only the braced form is expanded, so a literal `$` never collides with the
# unrelated `$section` declaration syntax.
_BRACED_ENV_VAR = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _expand_vars(value: str) -> str:
    return _BRACED_ENV_VAR.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)


def discover_manifest(startdir: str, explicit: str | None = None) -> str:
    """Resolve the manifest path: an explicit flag, then $TODA_MANIFEST, then
    the nearest MANIFEST found walking up from `startdir`."""
    if explicit:
        return explicit
    from_env = os.environ.get(MANIFEST_ENV_VAR)
    if from_env:
        return from_env
    current = abspath(startdir)
    while True:
        candidate = join(current, MANIFEST_FILENAME)
        if exists(candidate):
            return candidate
        parent = dirname(current)
        if parent == current:
            return join(startdir, MANIFEST_FILENAME)
        current = parent


class IllegalSyntax(ManifestError):
    pass


@dataclass(frozen=True)
class DeclarationMetadata:
    section: str
    line_number: int
    manifest_path: str
    raw_declaration: str


@dataclass(frozen=True)
class ResolvedLink:
    dest: str
    src: str
    declared_section: str
    declaration_line: int
    manifest_path: str
    raw_declaration: str
    include_chain: tuple[str, ...]
    glob_origin: str | None = None


@dataclass
class Manifest:
    """A parsed MANIFEST: a mapping of section name to `Section`.

    Use `iter_section_provenance`/`iter_section` to resolve links; the
    `sections` mapping (and the dict-like `__contains__`/`__getitem__`
    convenience methods) are for inspecting the raw, unresolved declarations.
    """

    DELETE_MACRO: ClassVar[str] = "@delete"
    INCLUDE_MACRO: ClassVar[str] = "@include"
    SRC_MACROS: ClassVar[frozenset[str]] = frozenset({DELETE_MACRO})
    DEST_MACROS: ClassVar[frozenset[str]] = frozenset({INCLUDE_MACRO})

    path: str | None = None
    startdir: str | None = None
    sections: dict[str, Section] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        self._startdir = self.startdir or os.getcwd()
        self._manifest_path = normpath(self.path) if self.path else "<memory>"
        self._srcdir = dirname(abspath(self.path)) if self.path else self._startdir
        self._declaration_metadata: dict[tuple[str, str], DeclarationMetadata] = {}
        if not self.path:
            return
        try:
            fp = open(self.path, "r")
        except OSError as e:
            raise ManifestError(
                "cannot read manifest `{:}`: {:}".format(self.path, e)
            ) from None
        with fp:
            self._parse(fp)

    def __contains__(self, section_name: object) -> bool:
        return section_name in self.sections

    def __getitem__(self, section_name: str) -> Section:
        return self.sections[section_name]

    def keys(self) -> Iterable[str]:
        return self.sections.keys()

    @staticmethod
    def _parse_line_comment(line: str) -> bool:
        return not line or line[0] == "#"

    @staticmethod
    def _parse_line_section_declaration(line: str) -> str | None:
        has_prefix = bool(line) and line[0] == "$"
        if not has_prefix:
            return None
        if line.startswith("${"):
            # `${VAR}/path: src` is a mapping, not a section declaration.
            return None
        if line[-1] in "@*:":
            raise IllegalSyntax(
                "section name {:s} cannot end in {:s}".format(line[:-1], line[-1])
            )
        name = line.strip("$").strip()
        if not name:
            raise IllegalSyntax("section declaration is missing a name")
        return name

    @staticmethod
    def _parse_part_macro(part: str | None) -> bool:
        return bool(part) and isinstance(part, str) and part.startswith("@")

    @staticmethod
    def _is_macro_or_parsed(rubberducky: str | tuple[str, ...]) -> bool:
        return bool(rubberducky) and (
            not isinstance(rubberducky, str) or rubberducky.startswith("@")
        )

    @staticmethod
    def _parse_part_terminal_glob(part: str | None) -> bool:
        return bool(part) and isinstance(part, str) and part.endswith("*")

    @staticmethod
    def _parse_includes(part: str) -> tuple[str, ...]:
        includes: list[str] = []
        for include in part.split():
            if include not in includes:
                includes.append(include)
        return tuple(includes)

    @staticmethod
    def _unprotected_colon_indices(line: str) -> list[int]:
        protected = {m.start() + 1 for m in _DRIVE_LETTER_COLON.finditer(line)}
        return [i for i, ch in enumerate(line) if ch == ":" and i not in protected]

    def _add_declaration_metadata(
        self, section_name: str, dest: str, line_number: int, raw_declaration: str
    ) -> None:
        self._declaration_metadata[(section_name, dest)] = DeclarationMetadata(
            section=section_name,
            line_number=line_number,
            manifest_path=self._manifest_path,
            raw_declaration=raw_declaration,
        )

    def get_declaration_metadata(
        self, section_name: str, dest: str
    ) -> DeclarationMetadata:
        return self._declaration_metadata[(section_name, dest)]

    def _parse(self, fp: TextIO) -> None:
        section: Section | None = None
        section_name: str | None = None
        for i, raw_line in enumerate(fp, 1):
            line = raw_line.strip()
            if self._parse_line_comment(line):
                continue

            try:
                new_section = self._parse_line_section_declaration(line)
            except IllegalSyntax as e:
                raise IllegalSyntax("line {:d}: {}".format(i, e)) from None
            if new_section:
                if new_section in self.sections:
                    raise IllegalSyntax(
                        "line {:d}: duplicate section declaration".format(i)
                    )
                section_name = new_section
                section = self.sections[new_section] = {}
                continue
            elif section is None or section_name is None:
                raise IllegalSyntax(
                    "line {:d}: target definition before "
                    "section declaration".format(i)
                )

            colon_indices = self._unprotected_colon_indices(line)
            if not colon_indices:
                raise IllegalSyntax("line {:d}: missing colon separator".format(i))
            if len(colon_indices) > 1:
                raise IllegalSyntax("line {:d}: multiple colons".format(i))

            sep = colon_indices[0]
            dest, src = line[:sep].strip(), line[sep + 1 :].strip()
            dest_is_macro = self._parse_part_macro(dest)
            src_is_macro = self._parse_part_macro(src)

            if dest in section:
                raise IllegalSyntax(
                    "line {:d}: target redefinition `{:}` "
                    "in same section".format(i, dest)
                )

            if dest_is_macro:
                if dest not in self.DEST_MACROS:
                    raise IllegalSyntax("line {:d}: invalid {:}".format(i, dest))

            resolved_src: str | tuple[str, ...] = src
            if dest == self.INCLUDE_MACRO:
                resolved_src = self._parse_includes(src)
            elif src_is_macro:
                if src not in self.SRC_MACROS:
                    raise IllegalSyntax("line {:d}: invalid {:}".format(i, src))

            if not (dest_is_macro or src_is_macro):
                has_glob = self._parse_part_terminal_glob(src)
                if not has_glob ^ (not dest.endswith("/")):
                    raise IllegalSyntax(
                        "line {:d}: glob dest must be directory ending with `/`".format(
                            i
                        )
                    )

            section[dest] = resolved_src
            self._add_declaration_metadata(
                section_name=section_name,
                dest=dest,
                line_number=i,
                raw_declaration=line,
            )

    def _resolve_link(
        self,
        section_name: str,
        dest: str,
        src: str | tuple[str, ...],
        include_chain: tuple[str, ...],
    ) -> list[ResolvedLink]:
        metadata = self.get_declaration_metadata(section_name, dest)
        resolved_dest = normpath(expanduser(_expand_vars(dest)))
        assert isinstance(src, str)
        if src in self.SRC_MACROS:
            return [
                ResolvedLink(
                    dest=resolved_dest,
                    src=src,
                    declared_section=section_name,
                    declaration_line=metadata.line_number,
                    manifest_path=metadata.manifest_path,
                    raw_declaration=metadata.raw_declaration,
                    include_chain=include_chain,
                    glob_origin=None,
                )
            ]

        resolved_src = normpath(join(self._srcdir, expanduser(_expand_vars(src))))
        has_glob = self._parse_part_terminal_glob(resolved_src)
        if not has_glob:
            return [
                ResolvedLink(
                    dest=resolved_dest,
                    src=resolved_src,
                    declared_section=section_name,
                    declaration_line=metadata.line_number,
                    manifest_path=metadata.manifest_path,
                    raw_declaration=metadata.raw_declaration,
                    include_chain=include_chain,
                    glob_origin=None,
                )
            ]

        glob_root = resolved_src[:-1]
        names = sorted(os.listdir(glob_root))
        records = []
        for name in names:
            records.append(
                ResolvedLink(
                    dest=normpath(join(resolved_dest, name)),
                    src=normpath(join(glob_root, name)),
                    declared_section=section_name,
                    declaration_line=metadata.line_number,
                    manifest_path=metadata.manifest_path,
                    raw_declaration=metadata.raw_declaration,
                    include_chain=include_chain,
                    glob_origin=normpath(src),
                )
            )
        return records

    def _iter_section_provenance(
        self,
        section_name: str,
        include_chain: tuple[str, ...],
        active_stack: tuple[str, ...],
        expanded_includes: set[str],
        from_include: bool = False,
    ) -> Iterator[ResolvedLink]:
        if section_name in active_stack:
            cycle = " -> ".join(active_stack + (section_name,))
            raise ManifestError("include cycle detected: {:s}".format(cycle))

        if from_include:
            if section_name in expanded_includes:
                return
            expanded_includes.add(section_name)

        stack = active_stack + (section_name,)
        for dest, src in self.sections[section_name].items():
            if self._is_macro_or_parsed(dest):
                if dest == self.INCLUDE_MACRO:
                    assert isinstance(src, tuple)
                    for include_name in src:
                        if include_name not in self.sections:
                            raise SectionNotFound(
                                "cannot include `{:}` dependency `{:}` "
                                "does not exist".format(section_name, include_name)
                            )
                        for link in self._iter_section_provenance(
                            include_name,
                            include_chain + (include_name,),
                            stack,
                            expanded_includes,
                            from_include=True,
                        ):
                            yield link
                    continue
                raise ManifestError("unsupported macro `{:}`".format(dest))

            for link in self._resolve_link(section_name, dest, src, include_chain):
                yield link

    def iter_section_provenance(
        self, section_name: str, included: set[str] | None = None
    ) -> Iterator[ResolvedLink]:
        if section_name not in self.sections:
            raise SectionNotFound(
                "section `{:s}` is not in the manifest".format(section_name)
            )
        if included is None:
            included = set()
        for link in self._iter_section_provenance(
            section_name,
            include_chain=(section_name,),
            active_stack=tuple(),
            expanded_includes=included,
            from_include=False,
        ):
            yield link

    def iter_section(
        self, section_name: str, included: set[str] | None = None
    ) -> Iterator[tuple[str, str]]:
        for link in self.iter_section_provenance(section_name, included=included):
            yield link.dest, link.src
