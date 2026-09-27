"""Tests for toda.plan - Operation planning and apply()."""

import os

import pytest

from toda.model import Manifest
from toda.plan import (
    OP_CREATE,
    OP_NOOP,
    OP_REMOVE,
    OP_REPLACE,
    OP_SKIP,
    apply,
    build_plan,
    render_plan_text,
)


def _manifest(manifest_file, temp_dir, content):
    path = manifest_file(content)
    return Manifest(path=path, startdir=temp_dir)


def _readonly_dir(temp_dir, entry, name="locked_dir"):
    """A directory holding `entry` but with no write bit, so the entry can't
    be unlinked until the directory is made writable again."""
    path = os.path.join(temp_dir, name)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, entry), "w") as f:
        f.write("gone")
    os.chmod(path, 0o500)
    return path


def _restore_writable(path):
    """Undo a read-only bit so tmp_path teardown can clean up."""
    if os.path.lexists(path):
        os.chmod(path, 0o700)


class TestBuildPlanInstall:
    def test_missing_dest_is_create(self, temp_dir, manifest_file, source_file):
        src = source_file()
        dest = os.path.join(temp_dir, "link")
        m = _manifest(
            manifest_file, temp_dir, f"$default\n{dest}: {os.path.basename(src)}\n"
        )

        plan = build_plan(m, ["default"], "install")

        assert [op.action for op in plan.operations] == [OP_CREATE]
        assert plan.operations[0].src == src

    def test_correct_existing_link_is_noop(self, temp_dir, manifest_file, source_file):
        src = source_file()
        dest = os.path.join(temp_dir, "link")
        os.symlink(src, dest)
        m = _manifest(
            manifest_file, temp_dir, f"$default\n{dest}: {os.path.basename(src)}\n"
        )

        plan = build_plan(m, ["default"], "install")

        assert [op.action for op in plan.operations] == [OP_NOOP]

    def test_conflicting_sources_is_skip(self, temp_dir, manifest_file, source_file):
        source_file(filename="one.txt")
        source_file(content="two", filename="two.txt")
        dest = os.path.join(temp_dir, "dest")
        m = _manifest(
            manifest_file,
            temp_dir,
            f"$s1\n{dest}: one.txt\n$s2\n{dest}: two.txt\n",
        )

        plan = build_plan(m, ["s1", "s2"], "install")

        assert [op.action for op in plan.operations] == [OP_SKIP]
        assert "conflicting sources" in plan.operations[0].reason

    def test_existing_file_without_force_is_skip(
        self, temp_dir, manifest_file, source_file
    ):
        src = source_file()
        dest = os.path.join(temp_dir, "existing")
        with open(dest, "w") as f:
            f.write("content")
        m = _manifest(
            manifest_file, temp_dir, f"$default\n{dest}: {os.path.basename(src)}\n"
        )

        plan = build_plan(m, ["default"], "install", force=False)

        assert [op.action for op in plan.operations] == [OP_SKIP]

    def test_existing_file_with_force_is_replace(
        self, temp_dir, manifest_file, source_file
    ):
        src = source_file()
        dest = os.path.join(temp_dir, "existing")
        with open(dest, "w") as f:
            f.write("content")
        m = _manifest(
            manifest_file, temp_dir, f"$default\n{dest}: {os.path.basename(src)}\n"
        )

        plan = build_plan(m, ["default"], "install", force=True)

        assert [op.action for op in plan.operations] == [OP_REPLACE]

    def test_delete_directory_with_force_plans_recursive_removal(
        self, temp_dir, manifest_file
    ):
        dest = os.path.join(temp_dir, "adir")
        os.makedirs(dest)
        m = _manifest(manifest_file, temp_dir, f"$default\n{dest}: @delete\n")

        plan = build_plan(m, ["default"], "install", force=True)

        op = plan.operations[0]
        assert op.action == OP_REMOVE
        assert op.actual_kind == "directory"
        assert op.force is True
        assert "recursive" in op.reason

    def test_delete_directory_without_force_plans_refusal(
        self, temp_dir, manifest_file
    ):
        dest = os.path.join(temp_dir, "adir")
        os.makedirs(dest)
        m = _manifest(manifest_file, temp_dir, f"$default\n{dest}: @delete\n")

        plan = build_plan(m, ["default"], "install", force=True)
        assert plan.operations[0].force is True

        plan = build_plan(m, ["default"], "install", force=False)
        assert plan.operations[0].force is False
        assert plan.operations[0].reason == "cannot delete a directory"

    def test_delete_top_level_directory_refuses_even_with_force(
        self, temp_dir, manifest_file
    ):
        m = _manifest(manifest_file, temp_dir, "$default\n~: @delete\n")

        plan = build_plan(m, ["default"], "install", force=True)

        op = plan.operations[0]
        assert op.action == OP_REMOVE
        assert op.force is False
        assert op.reason == "cannot delete a directory"


class TestRenderPlanText:
    def test_render_includes_dest_and_src(self, temp_dir, manifest_file, source_file):
        src = source_file()
        dest = os.path.join(temp_dir, "link")
        m = _manifest(
            manifest_file, temp_dir, f"$default\n{dest}: {os.path.basename(src)}\n"
        )

        plan = build_plan(m, ["default"], "install")
        text = render_plan_text(plan)

        assert "would link" in text
        assert dest in text
        assert src in text

    def test_render_marks_forced_recursive_delete(self, temp_dir, manifest_file):
        dest = os.path.join(temp_dir, "adir")
        os.makedirs(dest)
        m = _manifest(manifest_file, temp_dir, f"$default\n{dest}: @delete\n")

        text = render_plan_text(build_plan(m, ["default"], "install", force=True))
        assert "would remove" in text
        assert dest in text
        assert "recursive delete (--force)" in text

        text = render_plan_text(build_plan(m, ["default"], "install", force=False))
        assert "cannot delete a directory" in text


class TestApplyInstall:
    def test_creates_symlink(self, temp_dir, manifest_file, source_file):
        src = source_file(content="content")
        dest = os.path.join(temp_dir, "subdir", "link")
        m = _manifest(
            manifest_file, temp_dir, f"$default\n{dest}: {os.path.basename(src)}\n"
        )

        assert apply(build_plan(m, ["default"], "install")) == 0

        assert os.path.islink(dest)
        assert os.path.samefile(dest, src)

    def test_source_missing_is_a_failure(self, temp_dir, manifest_file):
        dest = os.path.join(temp_dir, "link")
        m = _manifest(manifest_file, temp_dir, f"$default\n{dest}: missing.txt\n")

        assert apply(build_plan(m, ["default"], "install")) == 1
        assert not os.path.lexists(dest)

    def test_backup_on_force_for_regular_file(
        self, temp_dir, manifest_file, source_file
    ):
        src = source_file(content="new")
        dest = os.path.join(temp_dir, "existing")
        with open(dest, "w") as f:
            f.write("old")
        m = _manifest(
            manifest_file, temp_dir, f"$default\n{dest}: {os.path.basename(src)}\n"
        )

        apply(build_plan(m, ["default"], "install", force=True))

        assert os.path.islink(dest)
        backup = dest + ".toda-backup"
        with open(backup) as f:
            assert f.read() == "old"

    def test_backup_on_force_for_directory(self, temp_dir, manifest_file, source_file):
        src = source_file(content="new")
        dest = os.path.join(temp_dir, "existingdir")
        os.makedirs(dest)
        with open(os.path.join(dest, "child.txt"), "w") as f:
            f.write("child")
        m = _manifest(
            manifest_file, temp_dir, f"$default\n{dest}: {os.path.basename(src)}\n"
        )

        apply(build_plan(m, ["default"], "install", force=True))

        assert os.path.islink(dest)
        backup = dest + ".toda-backup"
        assert os.path.isdir(backup)
        assert os.path.exists(os.path.join(backup, "child.txt"))

    def test_backup_timestamped_when_already_exists(
        self, temp_dir, manifest_file, source_file
    ):
        src = source_file(content="new")
        dest = os.path.join(temp_dir, "existing")
        with open(dest, "w") as f:
            f.write("old")
        with open(dest + ".toda-backup", "w") as f:
            f.write("previous backup")
        m = _manifest(
            manifest_file, temp_dir, f"$default\n{dest}: {os.path.basename(src)}\n"
        )

        apply(build_plan(m, ["default"], "install", force=True))

        with open(dest + ".toda-backup") as f:
            assert f.read() == "previous backup"
        timestamped = [
            name
            for name in os.listdir(temp_dir)
            if name.startswith("existing.toda-backup.")
        ]
        assert len(timestamped) == 1

    def test_force_removes_wrong_target_symlink_without_backup(
        self, temp_dir, manifest_file, source_file
    ):
        src1 = source_file(content="first", filename="first.txt")
        src2 = source_file(content="second", filename="second.txt")
        dest = os.path.join(temp_dir, "link")
        os.symlink(src1, dest)
        m = _manifest(manifest_file, temp_dir, f"$default\n{dest}: second.txt\n")

        apply(build_plan(m, ["default"], "install", force=True))

        assert os.path.samefile(dest, src2)
        assert not os.path.exists(dest + ".toda-backup")

    def test_delete_macro_removes_file(self, temp_dir, manifest_file):
        dest = os.path.join(temp_dir, "to_delete")
        with open(dest, "w") as f:
            f.write("gone")
        m = _manifest(manifest_file, temp_dir, f"$default\n{dest}: @delete\n")

        assert apply(build_plan(m, ["default"], "install")) == 0
        assert not os.path.lexists(dest)

    def test_delete_macro_removes_symlink(self, temp_dir, manifest_file, source_file):
        src = source_file()
        dest = os.path.join(temp_dir, "link")
        os.symlink(src, dest)
        m = _manifest(manifest_file, temp_dir, f"$default\n{dest}: @delete\n")

        assert apply(build_plan(m, ["default"], "install")) == 0
        assert not os.path.lexists(dest)
        assert os.path.exists(src)

    def test_delete_macro_directory_fails(self, temp_dir, manifest_file):
        dest = os.path.join(temp_dir, "adir")
        os.makedirs(dest)
        m = _manifest(manifest_file, temp_dir, f"$default\n{dest}: @delete\n")

        assert apply(build_plan(m, ["default"], "install")) == 1
        assert os.path.isdir(dest)

    def test_delete_macro_missing_dest_is_noop(self, temp_dir, manifest_file):
        dest = os.path.join(temp_dir, "absent")
        m = _manifest(manifest_file, temp_dir, f"$default\n{dest}: @delete\n")

        assert apply(build_plan(m, ["default"], "install")) == 0
        assert not os.path.lexists(dest)

    def test_delete_macro_directory_with_force_removes_tree(
        self, temp_dir, manifest_file
    ):
        dest = os.path.join(temp_dir, "adir")
        os.makedirs(os.path.join(dest, "sub"))
        with open(os.path.join(dest, "sub", "child.txt"), "w") as f:
            f.write("child")
        m = _manifest(manifest_file, temp_dir, f"$default\n{dest}: @delete\n")

        assert apply(build_plan(m, ["default"], "install", force=True)) == 0
        assert not os.path.lexists(dest)

    def test_delete_macro_in_unwritable_directory_with_force(
        self, temp_dir, manifest_file
    ):
        parent = _readonly_dir(temp_dir, "gone")
        dest = os.path.join(parent, "gone")
        m = _manifest(manifest_file, temp_dir, f"$default\n{dest}: @delete\n")

        try:
            assert apply(build_plan(m, ["default"], "install", force=True)) == 0
        finally:
            os.chmod(parent, 0o700)
        assert not os.path.lexists(dest)

    def test_delete_macro_in_unwritable_directory_without_force_fails(
        self, temp_dir, manifest_file
    ):
        parent = _readonly_dir(temp_dir, "gone")
        dest = os.path.join(parent, "gone")
        m = _manifest(manifest_file, temp_dir, f"$default\n{dest}: @delete\n")

        try:
            assert apply(build_plan(m, ["default"], "install")) == 1
            assert os.path.lexists(dest)
        finally:
            os.chmod(parent, 0o700)

    def test_delete_macro_unwritable_tree_with_force(self, temp_dir, manifest_file):
        dest = os.path.join(temp_dir, "adir")
        sub = os.path.join(dest, "sub")
        os.makedirs(sub)
        with open(os.path.join(sub, "child.txt"), "w") as f:
            f.write("child")
        os.chmod(sub, 0o500)
        m = _manifest(manifest_file, temp_dir, f"$default\n{dest}: @delete\n")

        try:
            assert apply(build_plan(m, ["default"], "install", force=True)) == 0
        finally:
            _restore_writable(dest)
            _restore_writable(sub)
        assert not os.path.lexists(dest)


class TestApplyPurge:
    def test_removes_correct_symlink(self, temp_dir, manifest_file, source_file):
        src = source_file()
        dest = os.path.join(temp_dir, "link")
        os.symlink(src, dest)
        m = _manifest(
            manifest_file, temp_dir, f"$default\n{dest}: {os.path.basename(src)}\n"
        )

        assert apply(build_plan(m, ["default"], "purge")) == 0
        assert not os.path.lexists(dest)

    def test_leaves_unowned_file_without_force(
        self, temp_dir, manifest_file, source_file
    ):
        src = source_file()
        dest = os.path.join(temp_dir, "owned_by_someone_else")
        with open(dest, "w") as f:
            f.write("keep me")
        m = _manifest(
            manifest_file, temp_dir, f"$default\n{dest}: {os.path.basename(src)}\n"
        )

        apply(build_plan(m, ["default"], "purge", force=False))

        assert os.path.exists(dest)

    def test_backs_up_unowned_file_with_force(
        self, temp_dir, manifest_file, source_file
    ):
        src = source_file()
        dest = os.path.join(temp_dir, "owned_by_someone_else")
        with open(dest, "w") as f:
            f.write("keep me")
        m = _manifest(
            manifest_file, temp_dir, f"$default\n{dest}: {os.path.basename(src)}\n"
        )

        apply(build_plan(m, ["default"], "purge", force=True))

        assert not os.path.exists(dest)
        assert os.path.exists(dest + ".toda-backup")

    def test_skips_delete_macro_entries(self, temp_dir, manifest_file):
        dest = os.path.join(temp_dir, "gone")
        with open(dest, "w") as f:
            f.write("keep me")
        m = _manifest(manifest_file, temp_dir, f"$default\n{dest}: @delete\n")

        assert apply(build_plan(m, ["default"], "purge")) == 0
        assert os.path.exists(dest)

    def test_removes_wrong_target_symlink_with_force(
        self, temp_dir, manifest_file, source_file
    ):
        source_file(filename="expected.txt")
        other = source_file(content="other", filename="other.txt")
        dest = os.path.join(temp_dir, "link")
        os.symlink(other, dest)
        m = _manifest(manifest_file, temp_dir, f"$default\n{dest}: expected.txt\n")

        assert apply(build_plan(m, ["default"], "purge", force=True)) == 0
        assert not os.path.lexists(dest)


class TestBuildPlanUnknownAction:
    def test_raises_for_unknown_action(self, temp_dir):
        m = Manifest(startdir=temp_dir)
        with pytest.raises(ValueError, match="bogus"):
            build_plan(m, [], "bogus")
