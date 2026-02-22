"""Tests for toda.reconcile."""

import os

from toda.model import Manifest
from toda.reconcile import (
    STATUS_MANIFEST_CONFLICT,
    STATUS_MISSING,
    STATUS_OK,
    STATUS_OVERWRITTEN_DIR,
    STATUS_OVERWRITTEN_FILE,
    STATUS_WRONG_TARGET,
    reconcile_manifest,
)


class TestReconcileStatuses:
    def test_delete_macro_is_ignored(self, temp_dir, manifest_file):
        dest = os.path.join(temp_dir, "remove-me")
        content = f"$default\n{dest}: @delete\n"
        path = manifest_file(content)
        manifest = Manifest(path=path, startdir=temp_dir)

        result = reconcile_manifest(manifest, ["default"])
        assert len(result.entries) == 0

    def test_missing_status(self, temp_dir, manifest_file, source_file):
        src = source_file(content="one", filename="one.txt")
        dest = os.path.join(temp_dir, "dest")
        content = f"$default\n{dest}: {os.path.basename(src)}\n"
        path = manifest_file(content)
        manifest = Manifest(path=path, startdir=temp_dir)

        result = reconcile_manifest(manifest, ["default"])
        assert result.entries[0].status == STATUS_MISSING

    def test_ok_status(self, temp_dir, manifest_file, source_file):
        src = source_file(content="one", filename="one.txt")
        dest = os.path.join(temp_dir, "dest")
        os.symlink(src, dest)
        content = f"$default\n{dest}: {os.path.basename(src)}\n"
        path = manifest_file(content)
        manifest = Manifest(path=path, startdir=temp_dir)

        result = reconcile_manifest(manifest, ["default"])
        assert result.entries[0].status == STATUS_OK

    def test_wrong_target_status(self, temp_dir, manifest_file, source_file):
        src1 = source_file(content="one", filename="one.txt")
        src2 = source_file(content="two", filename="two.txt")
        dest = os.path.join(temp_dir, "dest")
        os.symlink(src2, dest)
        content = f"$default\n{dest}: {os.path.basename(src1)}\n"
        path = manifest_file(content)
        manifest = Manifest(path=path, startdir=temp_dir)

        result = reconcile_manifest(manifest, ["default"])
        assert result.entries[0].status == STATUS_WRONG_TARGET

    def test_overwritten_file_status(self, temp_dir, manifest_file, source_file):
        src = source_file(content="one", filename="one.txt")
        dest = os.path.join(temp_dir, "dest")
        with open(dest, "w") as fp:
            fp.write("clobbered")
        content = f"$default\n{dest}: {os.path.basename(src)}\n"
        path = manifest_file(content)
        manifest = Manifest(path=path, startdir=temp_dir)

        result = reconcile_manifest(manifest, ["default"])
        assert result.entries[0].status == STATUS_OVERWRITTEN_FILE

    def test_overwritten_dir_status(self, temp_dir, manifest_file, source_file):
        src = source_file(content="one", filename="one.txt")
        dest = os.path.join(temp_dir, "dest")
        os.makedirs(dest, exist_ok=True)
        content = f"$default\n{dest}: {os.path.basename(src)}\n"
        path = manifest_file(content)
        manifest = Manifest(path=path, startdir=temp_dir)

        result = reconcile_manifest(manifest, ["default"])
        assert result.entries[0].status == STATUS_OVERWRITTEN_DIR

    def test_manifest_conflict_status(self, temp_dir, manifest_file, source_file):
        src1 = source_file(content="one", filename="one.txt")
        src2 = source_file(content="two", filename="two.txt")
        dest = os.path.join(temp_dir, "dest")
        content = (
            f"$s1\n{dest}: {os.path.basename(src1)}\n"
            f"$s2\n{dest}: {os.path.basename(src2)}\n"
        )
        path = manifest_file(content)
        manifest = Manifest(path=path, startdir=temp_dir)

        result = reconcile_manifest(manifest, ["s1", "s2"])
        assert result.entries[0].status == STATUS_MANIFEST_CONFLICT
