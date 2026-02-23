import json
import logging
import sys
from os import chdir, makedirs, remove, symlink
from os.path import basename, dirname, exists, isdir, islink, lexists
from pprint import pprint
from shutil import rmtree

from .model import Manifest
from .reconcile import (
    reconcile_manifest,
    render_reconcile_json,
    render_reconcile_text,
)


log = logging.getLogger(__name__)
log.setLevel(logging.WARN)
log.addHandler(logging.StreamHandler())


def _deploy_one(dest, src, force):
    # type: (str, str, bool) -> bool
    """
    :assumptions: manifest has already been parsed and validated.
    """

    destdir = dirname(dest)
    destname = basename(dest)

    if lexists(dest) or exists(dest):
        if not force:
            log.info("skipped (exists): %s" % dest)
            return False
        if isdir(dest) and not islink(dest):
            rmtree(dest)
        else:
            remove(dest)

    if not isdir(destdir):
        makedirs(destdir, 0o755)

    chdir(destdir)
    if src in Manifest.SRC_MACROS:
        if src == Manifest.DELETE_MACRO:
            if lexists(dest):
                remove(dest)
        else:
            assert False
            log.critical("{:s} is an invalid macro".format(src))
            return False
        return True
    assert exists(src), "Manifest src `{:}` does not exist on the filesystem".format(
        src
    )
    try:
        symlink(src, destname)
        log.warning("linked %s" % dest)
        return True
    except OSError as e:
        log.error("failure - %s :: %s" % (e, dest))
        return False


class Actions:
    def __init__(self, manifest, args):
        self.manifest = manifest
        self.args = args
        self._assert_symlink_works()

    def install(self):
        for section in self.args.section:
            for dest, src in self.manifest.iter_section(section):
                log.debug("installing {:s}".format(dest))
                _deploy_one(dest, src, force=self.args.force)

    def purge(self):
        for section in self.args.section:
            for dest, _ in self.manifest.iter_section(section):
                if lexists(dest) or exists(dest):
                    log.warning("purged %s" % dest)
                    remove(dest)

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
            return True
        nonce = "toda-preflight-symlink"
        target = nonce + ".target"
        try:
            symlink(nonce, target)
        except OSError:
            raise
        finally:
            if lexists(target):
                remove(target)
