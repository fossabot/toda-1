from __future__ import annotations

import json
import logging
import sys
import tempfile
from os import symlink
from os.path import join
from typing import Any

from . import SCHEMA_VERSION
from .errors import DeployError
from .model import Manifest
from .plan import apply, build_plan, render_plan_text
from .reconcile import (
    ReconcileResult,
    reconcile_manifest,
    render_reconcile_json,
    render_reconcile_text,
)

log = logging.getLogger(__name__)


class Actions:
    def __init__(self, manifest: Manifest, args: Any) -> None:
        self.manifest = manifest
        self.args = args
        self._assert_symlink_works()

    def install(self) -> int:
        return self._install_or_purge("install")

    def purge(self) -> int:
        return self._install_or_purge("purge")

    def _install_or_purge(self, action: str) -> int:
        plan = build_plan(
            self.manifest, self.args.section, action, force=self.args.force
        )
        if self.args.dry_run:
            print(render_plan_text(plan))
            return 0
        return apply(plan, strict=getattr(self.args, "strict", False))

    def inspect(self) -> None:
        sections: list[dict[str, Any]] = []
        for name in self.manifest.keys():
            includes: tuple[str, ...] = ()
            declarations: list[dict[str, str]] = []
            for dest, src in self.manifest[name].items():
                if dest == Manifest.INCLUDE_MACRO:
                    assert isinstance(src, tuple)
                    includes = src
                else:
                    assert isinstance(src, str)
                    declarations.append({"dest": dest, "src": src})
            sections.append(
                {"name": name, "includes": list(includes), "declarations": declarations}
            )

        if self.args.format == "json":
            print(
                json.dumps(
                    {"schema_version": SCHEMA_VERSION, "sections": sections},
                    indent=2,
                    sort_keys=True,
                )
            )
            return

        for section in sections:
            print("${:s}".format(section["name"]))
            if section["includes"]:
                print("  @include: {:s}".format(" ".join(section["includes"])))
            for declaration in section["declarations"]:
                print(
                    "  {dest}: {src}".format(
                        dest=declaration["dest"], src=declaration["src"]
                    )
                )

    @staticmethod
    def _serialize_trace_entry(entry: Any) -> dict[str, Any]:
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

    def trace(self) -> None:
        records = []
        for section in self.args.section:
            for entry in self.manifest.iter_section_provenance(section):
                if entry.src in Manifest.SRC_MACROS:
                    continue
                records.append(entry)

        if self.args.format == "json":
            payload = {
                "schema_version": SCHEMA_VERSION,
                "entries": [self._serialize_trace_entry(entry) for entry in records],
            }
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

    def _run_reconcile(self) -> ReconcileResult:
        return reconcile_manifest(self.manifest, self.args.section)

    def _print_reconcile(self, result: ReconcileResult) -> None:
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

    def reconcile(self) -> int:
        try:
            result = self._run_reconcile()
            self._print_reconcile(result)
            if result.has_drift:
                return 2
            return 0
        except Exception as exc:
            log.error("reconcile failed: %s", exc)
            return 1

    def _assert_symlink_works(self) -> None:
        if self.args.no_preflight or self.args.dry_run:
            return
        with tempfile.TemporaryDirectory(prefix="toda-preflight-") as tmp:
            try:
                symlink(join(tmp, "target"), join(tmp, "link"))
            except OSError as e:
                raise DeployError(
                    "unable to create symlinks on this system: {:}. On Windows, "
                    "enable Developer Mode or run toda as Administrator.".format(e)
                ) from e
