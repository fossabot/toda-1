from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from os.path import dirname, isdir, islink, join, lexists, normpath
from typing import TextIO

from . import SCHEMA_VERSION
from .model import Manifest, ResolvedLink

STATUS_OK = "ok"
STATUS_MISSING = "missing"
STATUS_WRONG_TARGET = "wrong_target"
STATUS_OVERWRITTEN_FILE = "overwritten_file"
STATUS_OVERWRITTEN_DIR = "overwritten_dir"
STATUS_MANIFEST_CONFLICT = "manifest_conflict"

STATUSES = (
    STATUS_OK,
    STATUS_MISSING,
    STATUS_WRONG_TARGET,
    STATUS_OVERWRITTEN_FILE,
    STATUS_OVERWRITTEN_DIR,
    STATUS_MANIFEST_CONFLICT,
)


@dataclass(frozen=True)
class ReconcileEntry:
    dest: str
    status: str
    expected_src: str | None
    actual_target: str | None
    actual_kind: str
    declarations: tuple[ResolvedLink, ...]
    conflict_sources: tuple[str, ...]


@dataclass(frozen=True)
class ReconcileResult:
    entries: tuple[ReconcileEntry, ...]
    totals: dict[str, int]

    @property
    def has_drift(self) -> bool:
        return any(entry.status != STATUS_OK for entry in self.entries)


def _strip_extended_prefix(path: str) -> str:
    r"""Drop the extended-length prefix Windows adds to some paths.

    `os.readlink` returns `\\?\C:\...` for a link aimed at an absolute path
    while a manifest source is written `C:\...`, so without this every correct
    link would compare unequal and read as `wrong_target`.
    """
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[8:]
    if path.startswith("\\\\?\\") or path.startswith("\\??\\"):
        return path[4:]
    return path


def _normalize_target(dest: str, target: str) -> str:
    target = _strip_extended_prefix(target)
    if os.path.isabs(target):
        return normpath(target)
    return normpath(join(dirname(dest), target))


def _same_target(actual_target: str, expected_src: str) -> bool:
    actual = normpath(_strip_extended_prefix(actual_target))
    expected = normpath(_strip_extended_prefix(expected_src))
    if os.path.normcase(actual) == os.path.normcase(expected):
        return True
    return os.path.normcase(os.path.realpath(actual)) == os.path.normcase(
        os.path.realpath(expected)
    )


def _collect_records(
    manifest: Manifest, sections: list[str]
) -> dict[str, list[ResolvedLink]]:
    records_by_dest: dict[str, list[ResolvedLink]] = {}
    for section in sections:
        for record in manifest.iter_section_provenance(section):
            if record.src.startswith("@"):
                continue
            records_by_dest.setdefault(record.dest, []).append(record)
    return records_by_dest


def _build_entry(dest: str, records: list[ResolvedLink]) -> ReconcileEntry:
    unique_expected: list[str] = []
    for record in records:
        if record.src not in unique_expected:
            unique_expected.append(record.src)

    actual_target: str | None
    if lexists(dest):
        if islink(dest):
            actual_kind = "symlink"
            actual_target = _normalize_target(dest, os.readlink(dest))
        elif isdir(dest):
            actual_kind = "directory"
            actual_target = None
        else:
            actual_kind = "file"
            actual_target = None
    else:
        actual_kind = "missing"
        actual_target = None

    if len(unique_expected) > 1:
        return ReconcileEntry(
            dest=dest,
            status=STATUS_MANIFEST_CONFLICT,
            expected_src=None,
            actual_target=actual_target,
            actual_kind=actual_kind,
            declarations=tuple(records),
            conflict_sources=tuple(unique_expected),
        )

    expected_src = unique_expected[0]
    status = STATUS_OK
    if actual_kind == "missing":
        status = STATUS_MISSING
    elif actual_kind == "symlink":
        assert actual_target is not None
        if not _same_target(actual_target, expected_src):
            status = STATUS_WRONG_TARGET
    elif actual_kind == "directory":
        status = STATUS_OVERWRITTEN_DIR
    else:
        status = STATUS_OVERWRITTEN_FILE

    return ReconcileEntry(
        dest=dest,
        status=status,
        expected_src=expected_src,
        actual_target=actual_target,
        actual_kind=actual_kind,
        declarations=tuple(records),
        conflict_sources=tuple(),
    )


def reconcile_manifest(manifest: Manifest, sections: list[str]) -> ReconcileResult:
    records_by_dest = _collect_records(manifest, sections)
    entries = tuple(
        _build_entry(dest, records) for dest, records in records_by_dest.items()
    )
    totals = {status: 0 for status in STATUSES}
    for entry in entries:
        totals[entry.status] += 1
    return ReconcileResult(entries=entries, totals=totals)


def _supports_color(mode: str, stream: TextIO) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    return stream.isatty()


def _paint(text: str, color_code: str, enabled: bool) -> str:
    if not enabled:
        return text
    return "\x1b[{0}m{1}\x1b[0m".format(color_code, text)


def render_reconcile_text(
    result: ReconcileResult,
    color_mode: str = "auto",
    only_changed: bool = False,
    stream: TextIO | None = None,
) -> str:
    stream = stream or sys.stdout
    colors_enabled = _supports_color(color_mode, stream)
    symbol_map = {
        STATUS_OK: "=",
        STATUS_MISSING: "-",
        STATUS_WRONG_TARGET: "!",
        STATUS_OVERWRITTEN_FILE: "~",
        STATUS_OVERWRITTEN_DIR: "~",
        STATUS_MANIFEST_CONFLICT: "x",
    }
    color_map = {
        STATUS_OK: "32",
        STATUS_MISSING: "31",
        STATUS_WRONG_TARGET: "31",
        STATUS_OVERWRITTEN_FILE: "33",
        STATUS_OVERWRITTEN_DIR: "33",
        STATUS_MANIFEST_CONFLICT: "35",
    }

    lines: list[str] = []
    for entry in result.entries:
        if only_changed and entry.status == STATUS_OK:
            continue
        status_label = _paint(entry.status, color_map[entry.status], colors_enabled)
        line = "{symbol} {status} {dest}".format(
            symbol=symbol_map[entry.status],
            status=status_label,
            dest=entry.dest,
        )
        if entry.status == STATUS_OK and entry.expected_src:
            line += " -> {0}".format(entry.expected_src)
        elif entry.status == STATUS_WRONG_TARGET:
            line += " expected={0} actual={1}".format(
                entry.expected_src, entry.actual_target
            )
        elif entry.status == STATUS_MANIFEST_CONFLICT:
            line += " sources={0}".format(", ".join(entry.conflict_sources))
        elif entry.expected_src:
            line += " expected={0}".format(entry.expected_src)
        lines.append(line)

    totals = " ".join(
        "{0}={1}".format(status, result.totals[status]) for status in STATUSES
    )
    lines.append("totals {0}".format(totals))
    return "\n".join(lines)


def result_to_dict(result: ReconcileResult) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "entries": [
            {
                "dest": entry.dest,
                "status": entry.status,
                "expected_src": entry.expected_src,
                "actual_target": entry.actual_target,
                "actual_kind": entry.actual_kind,
                "conflict_sources": list(entry.conflict_sources),
                "declarations": [
                    {
                        "dest": decl.dest,
                        "src": decl.src,
                        "declared_section": decl.declared_section,
                        "declaration_line": decl.declaration_line,
                        "manifest_path": decl.manifest_path,
                        "raw_declaration": decl.raw_declaration,
                        "include_chain": list(decl.include_chain),
                        "glob_origin": decl.glob_origin,
                    }
                    for decl in entry.declarations
                ],
            }
            for entry in result.entries
        ],
        "totals": dict(result.totals),
        "has_drift": result.has_drift,
    }


def render_reconcile_json(result: ReconcileResult) -> str:
    return json.dumps(result_to_dict(result), indent=2, sort_keys=True)
