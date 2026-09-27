from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from os.path import expanduser, join, normpath

log = logging.getLogger(__name__)
log.setLevel(logging.WARN)
log.addHandler(logging.StreamHandler())


class IllegalSyntax(Exception):
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


class Manifest(dict):
    DELETE_MACRO = "@delete"
    INCLUDE_MACRO = "@include"
    SRC_MACROS = {DELETE_MACRO}
    DEST_MACROS = {INCLUDE_MACRO}
    INIT_KWARGS = {"path", "startdir"}

    def __init__(self, **kw):
        for key in kw.keys():
            if key not in self.INIT_KWARGS:
                raise ValueError("{:s} is an invalid keyword-argument".format(key))
        path = kw.get("path")
        self._startdir = kw.get("startdir")
        if not self._startdir:
            self._startdir = os.getcwd()
        self._manifest_path = normpath(path) if path else "<memory>"
        self._declaration_metadata = {}
        if not path:
            return
        with open(path, "r") as fp:
            self._parse(fp)

    @staticmethod
    def _parse_line_comment(line):
        return not line or len(line) and line[0] == "#"

    @staticmethod
    def _parse_line_section_declaration(line):
        has_prefix = line and len(line) and line[0] == "$"
        if not has_prefix:
            return None
        if line[-1] in "@*:":
            raise IllegalSyntax(
                "section name {:s} cannot end in {:s}".format(line[:-1], line[-1])
            )
        return line.strip("$").strip()

    @staticmethod
    def _parse_part_macro(part):
        return part and isinstance(part, str) and part.startswith("@")

    @staticmethod
    def _is_macro_or_parsed(rubberducky):
        return rubberducky and (
            not isinstance(rubberducky, str) or rubberducky.startswith("@")
        )

    @staticmethod
    def _parse_part_terminal_glob(part):
        return part and isinstance(part, str) and part.endswith("*")

    @staticmethod
    def _parse_includes(part):
        includes = []
        for include in part.split():
            if include not in includes:
                includes.append(include)
        return tuple(includes)

    def _add_declaration_metadata(self, section_name, dest, line_number, raw_declaration):
        self._declaration_metadata[(section_name, dest)] = DeclarationMetadata(
            section=section_name,
            line_number=line_number,
            manifest_path=self._manifest_path,
            raw_declaration=raw_declaration,
        )

    def get_declaration_metadata(self, section_name, dest):
        return self._declaration_metadata[(section_name, dest)]

    def _parse(self, fp):
        section = None
        section_name = None
        for i, raw_line in enumerate(fp, 1):
            line = raw_line.strip()
            if self._parse_line_comment(line):
                continue

            new_section = self._parse_line_section_declaration(line)
            if new_section:
                if new_section in self:
                    raise IllegalSyntax(
                        "line {:d}: duplicate section declaration".format(i)
                    )
                section_name = new_section
                section = self[new_section] = dict()
                continue
            elif section is None or section_name is None:
                raise IllegalSyntax(
                    "line {:d}: target definition before "
                    "section declaration".format(i)
                )

            paths = line.split(":", 1)
            if len(paths) != 2:
                raise IllegalSyntax("line {:d}: missing colon separator".format(i))
            unparsed_separators = paths[-1].find(":") > -1
            if unparsed_separators:
                raise IllegalSyntax("line {:d}: multiple colons".format(i))

            dest, src = list(map(lambda p: p.strip(), paths))
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

            if dest == self.INCLUDE_MACRO:
                src = self._parse_includes(src)
            elif src_is_macro:
                if src not in self.SRC_MACROS:
                    raise IllegalSyntax("line {:d}: invalid {:}".format(i, src))

            if not (dest_is_macro or src_is_macro):
                has_glob = self._parse_part_terminal_glob(src)
                assert has_glob ^ (
                    not dest.endswith("/")
                ), "line {:d}: glob dest must be directory ending with `/`".format(i)

            section[dest] = src
            self._add_declaration_metadata(
                section_name=section_name,
                dest=dest,
                line_number=i,
                raw_declaration=line,
            )

    def _resolve_link(self, section_name, dest, src, include_chain):
        metadata = self.get_declaration_metadata(section_name, dest)
        resolved_dest = normpath(expanduser(dest))
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

        resolved_src = normpath(join(self._startdir, expanduser(src)))
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
        section_name,
        include_chain,
        active_stack,
        expanded_includes,
        from_include=False,
    ):
        if section_name in active_stack:
            cycle = " -> ".join(active_stack + (section_name,))
            raise AssertionError("include cycle detected: {:s}".format(cycle))

        if from_include:
            if section_name in expanded_includes:
                return
            expanded_includes.add(section_name)

        stack = active_stack + (section_name,)
        for dest, src in self[section_name].items():
            if self._is_macro_or_parsed(dest):
                if dest == self.INCLUDE_MACRO:
                    for include_name in src:
                        assert include_name in self, (
                            "cannot include `{:}` dependency `{:}` does not exist".format(
                                section_name, include_name
                            )
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
                assert False

            for link in self._resolve_link(section_name, dest, src, include_chain):
                yield link

    def iter_section_provenance(self, section_name, included=None):
        if section_name not in self:
            raise AssertionError(
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

    def iter_section(self, section_name, included=None):
        for link in self.iter_section_provenance(section_name, included=included):
            yield link.dest, link.src
