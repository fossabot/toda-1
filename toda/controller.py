import json
import logging
import os
import sys
import tempfile
from datetime import datetime
from os import makedirs, remove, symlink
from os.path import dirname, exists, isdir, islink, join, lexists
from pprint import pprint

from .errors import DeployError, SourceMissing, TodaError
from .model import Manifest
from .reconcile import (
    _normalize_target,
    _same_target,
    reconcile_manifest,
    render_reconcile_json,
    render_reconcile_text,
)

log = logging.getLogger(__name__)

DEPLOY_LINKED = "linked"
DEPLOY_NOOP = "noop"
DEPLOY_SKIPPED = "skipped"
DEPLOY_DELETED = "deleted"
DEPLOY_FAILED = "failed"


def _backup_path(dest):
    backup = dest + ".toda-backup"
    if not lexists(backup):
        return backup
    return "{:}.{:}".format(backup, datetime.now().strftime("%Y%m%d%H%M%S"))


def _remove_link_or_file(dest):
    # A symlink to a directory can't be os.remove()'d on Windows, but
    # os.rmdir() refuses a symlink to a directory on POSIX. Try both.
    try:
        remove(dest)
    except OSError:
        if islink(dest):
            os.rmdir(dest)
        else:
            raise


def _delete_one(dest):
    if islink(dest):
        _remove_link_or_file(dest)
        log.warning("deleted %s" % dest)
        return DEPLOY_DELETED
    if isdir(dest):
        log.error("failure - %s is a directory, refusing to delete" % dest)
        return DEPLOY_FAILED
    if lexists(dest):
        remove(dest)
        log.warning("deleted %s" % dest)
        return DEPLOY_DELETED
    return DEPLOY_DELETED


def _deploy_one(dest, src, force):
    """
    :assumptions: manifest has already been parsed and validated.
    """

    if src == Manifest.DELETE_MACRO:
        return _delete_one(dest)

    if not exists(src):
        raise SourceMissing(
            "manifest src `{:}` does not exist on the filesystem".format(src)
        )

    if islink(dest):
        try:
            actual_target = _normalize_target(dest, os.readlink(dest))
        except OSError:
            actual_target = None
        if actual_target is not None and _same_target(actual_target, src):
            log.debug("already linked: %s" % dest)
            return DEPLOY_NOOP
        if not force:
            log.info("skipped (exists): %s" % dest)
            return DEPLOY_SKIPPED
        _remove_link_or_file(dest)
    elif lexists(dest):
        if not force:
            log.info("skipped (exists): %s" % dest)
            return DEPLOY_SKIPPED
        backup = _backup_path(dest)
        os.rename(dest, backup)
        log.warning("backed up %s -> %s" % (dest, backup))

    destdir = dirname(dest)
    if not isdir(destdir):
        makedirs(destdir, 0o755)

    try:
        symlink(src, dest, target_is_directory=isdir(src))
        log.warning("linked %s" % dest)
        return DEPLOY_LINKED
    except OSError as e:
        log.error("failure - %s :: %s" % (e, dest))
        return DEPLOY_FAILED


def _purge_one(dest, expected_src, force):
    if not lexists(dest):
        return DEPLOY_NOOP

    if islink(dest):
        try:
            actual_target = _normalize_target(dest, os.readlink(dest))
        except OSError:
            actual_target = None
        if actual_target is None or _same_target(actual_target, expected_src):
            _remove_link_or_file(dest)
            log.warning("purged %s" % dest)
            return DEPLOY_DELETED
        if not force:
            log.info("skipped (unowned symlink): %s" % dest)
            return DEPLOY_SKIPPED
        _remove_link_or_file(dest)
        log.warning("purged %s" % dest)
        return DEPLOY_DELETED

    if not force:
        log.info("skipped (not a symlink): %s" % dest)
        return DEPLOY_SKIPPED
    backup = _backup_path(dest)
    os.rename(dest, backup)
    log.warning("backed up %s -> %s" % (dest, backup))
    return DEPLOY_DELETED


class Actions:
    def __init__(self, manifest, args):
        self.manifest = manifest
        self.args = args
        self._assert_symlink_works()

    def install(self):
        strict = getattr(self.args, "strict", False)
        failed = False
        for section in self.args.section:
            for dest, src in self.manifest.iter_section(section):
                log.debug("installing {:s}".format(dest))
                try:
                    outcome = _deploy_one(dest, src, force=self.args.force)
                except (TodaError, OSError) as e:
                    log.error("failure - %s :: %s" % (e, dest))
                    failed = True
                    continue
                if outcome == DEPLOY_FAILED:
                    failed = True
                elif outcome == DEPLOY_SKIPPED and strict:
                    failed = True
        return 1 if failed else 0

    def purge(self):
        strict = getattr(self.args, "strict", False)
        failed = False
        for section in self.args.section:
            for dest, src in self.manifest.iter_section(section):
                if src in Manifest.SRC_MACROS:
                    continue
                try:
                    outcome = _purge_one(dest, src, force=self.args.force)
                except (TodaError, OSError) as e:
                    log.error("failure - %s :: %s" % (e, dest))
                    failed = True
                    continue
                if outcome == DEPLOY_FAILED:
                    failed = True
                elif outcome == DEPLOY_SKIPPED and strict:
                    failed = True
        return 1 if failed else 0

    def inspect(self):
        print("inspecting...")
        pprint(
            dict(
                (
                    key,
                    self.manifest[key].get(Manifest.INCLUDE_MACRO, None),
                )
                for key in self.manifest.keys()
            )
        )

    @staticmethod
    def _serialize_trace_entry(entry):
        return {
            "dest": entry.dest,
            "src": entry.src,
            "declared_section": entry.declared_section,
            "declaration_line": entry.declaration_line,
            "manifest_path": entry.manifest_path,
            "raw_declaration": entry.raw_declaration,
            "include_chain": list(entry.include_chain),
            "glob_origin": entry.glob_origin,
        }

    def trace(self):
        records = []
        for section in self.args.section:
            for entry in self.manifest.iter_section_provenance(section):
                if entry.src in Manifest.SRC_MACROS:
                    continue
                records.append(entry)

        if self.args.format == "json":
            payload = [self._serialize_trace_entry(entry) for entry in records]
            print(json.dumps(payload, indent=2, sort_keys=True))
            return

        for entry in records:
            print(
                "{dest} <- {src} [section={section} line={line} chain={chain}]".format(
                    dest=entry.dest,
                    src=entry.src,
                    section=entry.declared_section,
                    line=entry.declaration_line,
                    chain=" -> ".join(entry.include_chain),
                )
            )

    def _run_reconcile(self):
        return reconcile_manifest(self.manifest, self.args.section)

    def _print_reconcile(self, result):
        if self.args.format == "json":
            print(render_reconcile_json(result))
            return
        print(
            render_reconcile_text(
                result,
                color_mode=self.args.color,
                only_changed=self.args.only_changed,
                stream=sys.stdout,
            )
        )

    def reconcile(self):
        try:
            result = self._run_reconcile()
            self._print_reconcile(result)
            if result.has_drift:
                return 2
            return 0
        except Exception as exc:
            log.error("reconcile failed: %s", exc)
            return 1

    def _assert_symlink_works(self):
        if self.args.no_preflight:
            return
        with tempfile.TemporaryDirectory(prefix="toda-preflight-") as tmp:
            try:
                symlink(join(tmp, "target"), join(tmp, "link"))
            except OSError as e:
                raise DeployError(
                    "unable to create symlinks on this system: {:}. On Windows, "
                    "enable Developer Mode or run toda as Administrator.".format(e)
                ) from e
