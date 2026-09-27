from __future__ import annotations

import logging
import os
import shutil
import stat
import sys
from dataclasses import dataclass
from datetime import datetime
from os import makedirs, remove, symlink
from os.path import (
    dirname,
    exists,
    expanduser,
    isdir,
    islink,
    lexists,
    normpath,
)

from .errors import DeployError, SourceMissing, TodaError
from .model import Manifest
from .reconcile import (
    STATUS_MANIFEST_CONFLICT,
    STATUS_MISSING,
    STATUS_OK,
    ReconcileEntry,
    ReconcileResult,
    reconcile_manifest,
)

log = logging.getLogger(__name__)

OP_CREATE = "create"
OP_REPLACE = "replace"
OP_REMOVE = "remove"
OP_SKIP = "skip"
OP_NOOP = "noop"

OUTCOME_LINKED = "linked"
OUTCOME_DELETED = "deleted"
OUTCOME_NOOP = "noop"
OUTCOME_SKIPPED = "skipped"


@dataclass(frozen=True)
class Operation:
    action: str
    dest: str
    src: str | None
    actual_kind: str
    reason: str | None = None
    for_delete: bool = False
    force: bool = False


@dataclass(frozen=True)
class Plan:
    operations: tuple[Operation, ...]
    action: str


def _collect_delete_dests(manifest: Manifest, sections: list[str]) -> tuple[str, ...]:
    dests: list[str] = []
    seen: set[str] = set()
    for section in sections:
        for entry in manifest.iter_section_provenance(section):
            if entry.src == Manifest.DELETE_MACRO and entry.dest not in seen:
                seen.add(entry.dest)
                dests.append(entry.dest)
    return tuple(dests)


def _is_top_level(dest: str) -> bool:
    return normpath(dest) in {os.sep, normpath(expanduser("~"))}


def _delete_operation(dest: str, force: bool) -> Operation:
    if islink(dest):
        return Operation(OP_REMOVE, dest, None, "symlink", for_delete=True, force=force)
    if isdir(dest):
        if force and not _is_top_level(dest):
            return Operation(
                OP_REMOVE,
                dest,
                None,
                "directory",
                "recursive delete (--force)",
                for_delete=True,
                force=True,
            )
        return Operation(
            OP_REMOVE,
            dest,
            None,
            "directory",
            "cannot delete a directory",
            for_delete=True,
        )
    if lexists(dest):
        return Operation(OP_REMOVE, dest, None, "file", for_delete=True, force=force)
    return Operation(OP_NOOP, dest, None, "missing", for_delete=True)


def _install_operation(entry: ReconcileEntry, force: bool) -> Operation:
    if entry.status == STATUS_OK:
        return Operation(OP_NOOP, entry.dest, entry.expected_src, entry.actual_kind)
    if entry.status == STATUS_MISSING:
        return Operation(OP_CREATE, entry.dest, entry.expected_src, entry.actual_kind)
    if entry.status == STATUS_MANIFEST_CONFLICT:
        reason = "conflicting sources declared: {:}".format(
            ", ".join(entry.conflict_sources)
        )
        return Operation(OP_SKIP, entry.dest, None, entry.actual_kind, reason)
    if force:
        return Operation(
            OP_REPLACE, entry.dest, entry.expected_src, entry.actual_kind, entry.status
        )
    return Operation(
        OP_SKIP, entry.dest, entry.expected_src, entry.actual_kind, entry.status
    )


def _purge_operation(entry: ReconcileEntry, force: bool) -> Operation:
    if entry.status == STATUS_MISSING:
        return Operation(OP_NOOP, entry.dest, entry.expected_src, entry.actual_kind)
    if entry.status == STATUS_OK:
        return Operation(OP_REMOVE, entry.dest, entry.expected_src, entry.actual_kind)
    if entry.status == STATUS_MANIFEST_CONFLICT:
        reason = "conflicting sources declared: {:}".format(
            ", ".join(entry.conflict_sources)
        )
        return Operation(OP_SKIP, entry.dest, None, entry.actual_kind, reason)
    if force:
        return Operation(
            OP_REMOVE, entry.dest, entry.expected_src, entry.actual_kind, entry.status
        )
    return Operation(
        OP_SKIP, entry.dest, entry.expected_src, entry.actual_kind, entry.status
    )


def build_plan(
    manifest: Manifest, sections: list[str], action: str, force: bool = False
) -> Plan:
    """Compute the operations `apply()` would perform for `action` ("install"
    or "purge"), without touching the filesystem."""

    result: ReconcileResult = reconcile_manifest(manifest, sections)
    operations: list[Operation] = []

    if action == "install":
        for dest in _collect_delete_dests(manifest, sections):
            operations.append(_delete_operation(dest, force))
        for entry in result.entries:
            operations.append(_install_operation(entry, force))
    elif action == "purge":
        for entry in result.entries:
            operations.append(_purge_operation(entry, force))
    else:
        raise ValueError("unsupported plan action `{:}`".format(action))

    return Plan(operations=tuple(operations), action=action)


def render_plan_text(plan: Plan) -> str:
    verb = {
        OP_CREATE: "would link",
        OP_REPLACE: "would replace",
        OP_REMOVE: "would remove",
        OP_SKIP: "would skip",
        OP_NOOP: "no change",
    }
    lines = []
    for op in plan.operations:
        line = "{verb} {dest}".format(verb=verb[op.action], dest=op.dest)
        if op.src:
            line += " -> {:}".format(op.src)
        if op.reason:
            line += " ({:})".format(op.reason)
        lines.append(line)
    return "\n".join(lines)


def _backup_path(dest: str) -> str:
    backup = dest + ".toda-backup"
    if not lexists(backup):
        return backup
    return "{:}.{:}".format(backup, datetime.now().strftime("%Y%m%d%H%M%S"))


def _remove_link_or_file(dest: str) -> None:
    # A symlink to a directory can't be os.remove()'d on Windows, but
    # os.rmdir() refuses a symlink to a directory on POSIX. Try both.
    try:
        remove(dest)
    except OSError:
        if islink(dest):
            os.rmdir(dest)
        else:
            raise


def _make_writable(path: str) -> None:
    mode = os.stat(path).st_mode
    extra = stat.S_IWUSR | (stat.S_IXUSR if stat.S_ISDIR(mode) else 0)
    os.chmod(path, mode | extra)


def _remove_tree(dest: str) -> None:
    def clear_and_retry(func, path, _exc):
        # Unlinking an entry needs write permission on its directory, not on
        # the entry itself.
        _make_writable(dirname(path) or ".")
        if not islink(path):
            _make_writable(path)
        func(path)

    if sys.version_info >= (3, 12):
        # 3.12 replaced onerror with onexc, which mypy rejects while it checks
        # against the 3.10 stubs, so reach rmtree dynamically.
        getattr(shutil, "rmtree")(dest, onexc=clear_and_retry)  # noqa: B009
    else:
        shutil.rmtree(dest, onerror=clear_and_retry)


def _remove_link_or_file_forced(dest: str) -> None:
    try:
        _remove_link_or_file(dest)
    except PermissionError:
        _make_writable(dirname(dest) or ".")
        if not islink(dest):
            _make_writable(dest)
        _remove_link_or_file(dest)


def _create_link(dest: str, src: str) -> None:
    if not exists(src):
        raise SourceMissing(
            "manifest src `{:}` does not exist on the filesystem".format(src)
        )
    destdir = dirname(dest)
    if not isdir(destdir):
        makedirs(destdir, 0o755)
    try:
        symlink(src, dest, target_is_directory=isdir(src))
    except OSError as e:
        raise DeployError("failure - {:} :: {:}".format(e, dest)) from e


def _apply_one(op: Operation) -> str:
    if op.action == OP_NOOP:
        log.debug("noop: %s" % op.dest)
        return OUTCOME_NOOP

    if op.action == OP_SKIP:
        log.info("skipped (%s): %s" % (op.reason, op.dest))
        return OUTCOME_SKIPPED

    if op.action == OP_CREATE:
        assert op.src is not None
        _create_link(op.dest, op.src)
        log.warning("linked %s" % op.dest)
        return OUTCOME_LINKED

    if op.action == OP_REPLACE:
        assert op.src is not None
        if op.actual_kind == "symlink":
            _remove_link_or_file(op.dest)
        else:
            backup = _backup_path(op.dest)
            os.rename(op.dest, backup)
            log.warning("backed up %s -> %s" % (op.dest, backup))
        _create_link(op.dest, op.src)
        log.warning("linked %s" % op.dest)
        return OUTCOME_LINKED

    if op.action == OP_REMOVE:
        if op.for_delete:
            if op.actual_kind == "directory":
                if not op.force:
                    raise DeployError(
                        "{:} is a directory, refusing to delete".format(op.dest)
                    )
                _remove_tree(op.dest)
            elif op.force:
                _remove_link_or_file_forced(op.dest)
            else:
                _remove_link_or_file(op.dest)
            log.warning("deleted %s" % op.dest)
            return OUTCOME_DELETED
        if op.actual_kind == "symlink":
            _remove_link_or_file(op.dest)
            log.warning("purged %s" % op.dest)
            return OUTCOME_DELETED
        backup = _backup_path(op.dest)
        os.rename(op.dest, backup)
        log.warning("backed up %s -> %s" % (op.dest, backup))
        return OUTCOME_DELETED

    raise ValueError("unsupported operation action `{:}`".format(op.action))


def apply(plan: Plan, strict: bool = False) -> int:
    """Execute `plan`'s operations against the real filesystem.

    Returns 1 if any operation failed, or was skipped while `strict`.
    """
    failed = False
    for op in plan.operations:
        try:
            outcome = _apply_one(op)
        except (TodaError, OSError) as e:
            log.error("failure - %s :: %s" % (e, op.dest))
            failed = True
            continue
        if outcome == OUTCOME_SKIPPED and strict:
            failed = True
    return 1 if failed else 0
