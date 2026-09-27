"""Tests for toda.controller - Actions."""

import json
import os
import pytest
from toda.errors import SourceMissing
from toda.model import Manifest
from toda.controller import Actions, _deploy_one


class TestDeployOne:
    """Test _deploy_one function."""

    def test_creates_symlink(self, temp_dir, source_file):
        """_deploy_one creates a symlink to the source."""
        src = source_file(content="test content")
        dest = os.path.join(temp_dir, "subdir", "link")

        _deploy_one(dest, src, force=False)

        assert os.path.islink(dest)
        assert os.readlink(dest) == src

    def test_creates_parent_dirs(self, temp_dir, source_file):
        """_deploy_one creates parent directories if needed."""
        src = source_file()
        dest = os.path.join(temp_dir, "a", "b", "c", "link")

        _deploy_one(dest, src, force=False)

        assert os.path.isdir(os.path.dirname(dest))
        assert os.path.islink(dest)

    def test_skip_existing_without_force(self, temp_dir, source_file):
        """_deploy_one skips existing files without force."""
        src = source_file()
        dest = os.path.join(temp_dir, "existing")
        with open(dest, "w") as f:
            f.write("existing content")

        _deploy_one(dest, src, force=False)

        # Should still be a regular file, not a symlink
        assert not os.path.islink(dest)
        with open(dest) as f:
            assert f.read() == "existing content"

    def test_clobber_existing_with_force(self, temp_dir, source_file):
        """_deploy_one replaces existing files with force."""
        src = source_file(content="source content")
        dest = os.path.join(temp_dir, "existing")
        with open(dest, "w") as f:
            f.write("existing content")

        _deploy_one(dest, src, force=True)

        assert os.path.islink(dest)
        with open(dest) as f:
            assert f.read() == "source content"

    def test_clobber_existing_symlink_with_force(self, temp_dir, source_file):
        """_deploy_one replaces existing symlinks with force."""
        src1 = source_file(content="first", filename="first.txt")
        src2 = source_file(content="second", filename="second.txt")
        dest = os.path.join(temp_dir, "link")
        os.symlink(src1, dest)

        _deploy_one(dest, src2, force=True)

        assert os.path.islink(dest)
        assert os.readlink(dest) == src2

    def test_clobber_existing_dir_with_force(self, temp_dir, source_file):
        """_deploy_one replaces existing directories with force."""
        src = source_file()
        dest = os.path.join(temp_dir, "existingdir")
        os.makedirs(dest)
        with open(os.path.join(dest, "child.txt"), "w") as f:
            f.write("child")

        _deploy_one(dest, src, force=True)

        assert os.path.islink(dest)

    def test_delete_macro(self, temp_dir):
        """_deploy_one handles @delete macro."""
        dest = os.path.join(temp_dir, "to_delete")
        with open(dest, "w") as f:
            f.write("delete me")

        assert _deploy_one(dest, "@delete", force=False) == "deleted"
        assert not os.path.lexists(dest)

    def test_delete_macro_missing_dest(self, temp_dir):
        """_deploy_one @delete is a no-op when dest is absent."""
        dest = os.path.join(temp_dir, "absent")

        assert _deploy_one(dest, "@delete", force=False) == "deleted"
        assert not os.path.lexists(dest)

    def test_delete_macro_symlink(self, temp_dir, source_file):
        """_deploy_one @delete removes a symlink without following it."""
        src = source_file()
        dest = os.path.join(temp_dir, "link")
        os.symlink(src, dest)

        assert _deploy_one(dest, "@delete", force=False) == "deleted"
        assert not os.path.lexists(dest)
        assert os.path.exists(src)

    def test_delete_macro_directory_fails(self, temp_dir):
        """_deploy_one @delete refuses to remove a real directory."""
        dest = os.path.join(temp_dir, "adir")
        os.makedirs(dest)

        assert _deploy_one(dest, "@delete", force=False) == "failed"
        assert os.path.isdir(dest)

    def test_nonexistent_source_raises(self, temp_dir):
        """_deploy_one raises when source doesn't exist."""
        dest = os.path.join(temp_dir, "link")

        with pytest.raises(SourceMissing, match="does not exist"):
            _deploy_one(dest, "/nonexistent/source", force=False)

    def test_source_checked_before_touching_dest(self, temp_dir):
        """A missing source leaves an existing destination untouched."""
        dest = os.path.join(temp_dir, "existing")
        with open(dest, "w") as f:
            f.write("original")

        with pytest.raises(SourceMissing):
            _deploy_one(dest, "/nonexistent/source", force=True)

        with open(dest) as f:
            assert f.read() == "original"

    def test_noop_for_correct_existing_link(self, temp_dir, source_file):
        """An existing symlink already pointing at the source is a no-op."""
        src = source_file(content="content")
        dest = os.path.join(temp_dir, "link")
        os.symlink(src, dest)

        result = _deploy_one(dest, src, force=False)

        assert result == "noop"
        assert os.readlink(dest) == src

    def test_backup_on_force_for_regular_file(self, temp_dir, source_file):
        """--force backs up an existing regular file instead of deleting it."""
        src = source_file(content="new content")
        dest = os.path.join(temp_dir, "existing")
        with open(dest, "w") as f:
            f.write("old content")

        _deploy_one(dest, src, force=True)

        assert os.path.islink(dest)
        backup = dest + ".toda-backup"
        assert os.path.exists(backup)
        with open(backup) as f:
            assert f.read() == "old content"

    def test_backup_on_force_for_directory(self, temp_dir, source_file):
        """--force backs up an existing directory instead of using rmtree."""
        src = source_file(content="new content")
        dest = os.path.join(temp_dir, "existingdir")
        os.makedirs(dest)
        with open(os.path.join(dest, "child.txt"), "w") as f:
            f.write("child")

        _deploy_one(dest, src, force=True)

        assert os.path.islink(dest)
        backup = dest + ".toda-backup"
        assert os.path.isdir(backup)
        assert os.path.exists(os.path.join(backup, "child.txt"))

    def test_backup_timestamped_when_already_exists(self, temp_dir, source_file):
        """A pre-existing backup path gets a timestamp suffix instead of clobbering."""
        src = source_file(content="new content")
        dest = os.path.join(temp_dir, "existing")
        with open(dest, "w") as f:
            f.write("old content")
        with open(dest + ".toda-backup", "w") as f:
            f.write("previous backup")

        _deploy_one(dest, src, force=True)

        assert os.path.islink(dest)
        with open(dest + ".toda-backup") as f:
            assert f.read() == "previous backup"
        timestamped = [
            name
            for name in os.listdir(temp_dir)
            if name.startswith("existing.toda-backup.")
        ]
        assert len(timestamped) == 1

    def test_force_removes_wrong_target_symlink_without_backup(
        self, temp_dir, source_file
    ):
        """--force removes (not backs up) a symlink pointing elsewhere."""
        src1 = source_file(content="first", filename="first.txt")
        src2 = source_file(content="second", filename="second.txt")
        dest = os.path.join(temp_dir, "link")
        os.symlink(src1, dest)

        _deploy_one(dest, src2, force=True)

        assert os.path.islink(dest)
        assert os.readlink(dest) == src2
        assert not os.path.exists(dest + ".toda-backup")


class TestActionsInit:
    """Test Actions initialization."""

    def test_init_stores_manifest_and_args(self, mock_args, temp_dir):
        m = Manifest(startdir=temp_dir)
        actions = Actions(m, mock_args)
        assert actions.manifest is m
        assert actions.args is mock_args

    def test_init_runs_preflight(self, mock_args, temp_dir):
        """Actions runs symlink preflight check."""
        mock_args.no_preflight = False
        m = Manifest(startdir=temp_dir)
        # Should not raise on systems that support symlinks
        old_cwd = temp_dir  # Safe fallback
        try:
            old_cwd = os.getcwd()
        except FileNotFoundError:
            pass  # cwd was deleted by previous test
        try:
            os.chdir(temp_dir)
            actions = Actions(m, mock_args)
        finally:
            os.chdir(old_cwd)

    def test_init_skips_preflight(self, mock_args, temp_dir):
        """Actions skips preflight when flag is set."""
        mock_args.no_preflight = True
        m = Manifest(startdir=temp_dir)
        actions = Actions(m, mock_args)
        # Should not raise


class TestActionsInstall:
    """Test Actions.install method."""

    def test_install_creates_symlinks(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
        src = source_file(content="source content")
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "dest_link")
        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        actions = Actions(m, mock_args)
        actions.install()

        assert os.path.islink(dest)

    def test_install_multiple_files(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
        src1 = source_file(content="content1", filename="src1.txt")
        src2 = source_file(content="content2", filename="src2.txt")
        dest1 = os.path.join(temp_dir, "dest1")
        dest2 = os.path.join(temp_dir, "dest2")
        content = f"$default\n{dest1}: src1.txt\n{dest2}: src2.txt\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        actions = Actions(m, mock_args)
        actions.install()

        assert os.path.islink(dest1)
        assert os.path.islink(dest2)

    def test_install_returns_zero_on_success(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
        src = source_file()
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "dest_link")
        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        actions = Actions(m, mock_args)

        assert actions.install() == 0

    def test_install_returns_one_on_missing_source(
        self, temp_dir, manifest_file, mock_args
    ):
        dest = os.path.join(temp_dir, "dest_link")
        content = f"$default\n{dest}: missing.txt\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        actions = Actions(m, mock_args)

        assert actions.install() == 1

    def test_install_skip_is_not_a_failure_by_default(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
        src = source_file()
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "existing")
        with open(dest, "w") as f:
            f.write("existing content")
        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        actions = Actions(m, mock_args)

        assert actions.install() == 0

    def test_install_skip_is_a_failure_with_strict(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
        src = source_file()
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "existing")
        with open(dest, "w") as f:
            f.write("existing content")
        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        mock_args.strict = True
        actions = Actions(m, mock_args)

        assert actions.install() == 1

    def test_install_verbose_shows_skip(
        self, temp_dir, manifest_file, source_file, mock_args, caplog
    ):
        """A skip is only surfaced at -v (INFO), not at the default WARNING level."""
        import logging

        src = source_file()
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "existing")
        with open(dest, "w") as f:
            f.write("existing content")
        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        actions = Actions(m, mock_args)

        with caplog.at_level(logging.WARNING, logger="toda.controller"):
            actions.install()
        assert not any("skipped" in record.message for record in caplog.records)

        caplog.clear()
        with caplog.at_level(logging.INFO, logger="toda.controller"):
            actions.install()
        assert any("skipped" in record.message for record in caplog.records)

    def test_install_directory_symlink(
        self, temp_dir, manifest_file, source_dir, mock_args
    ):
        """A directory source is linked with target_is_directory semantics."""
        srcdir = source_dir()
        dest = os.path.join(temp_dir, "dest_dir_link")
        content = f"$default\n{dest}: {os.path.basename(srcdir)}\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        actions = Actions(m, mock_args)
        actions.install()

        assert os.path.islink(dest)
        assert os.path.isdir(dest)
        assert sorted(os.listdir(dest)) == ["file1.txt", "file2.txt"]


class TestActionsPurge:
    """Test Actions.purge method."""

    def test_purge_removes_symlinks(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
        src = source_file()
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "to_purge")
        # Create symlink first
        os.symlink(src, dest)

        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        actions = Actions(m, mock_args)
        actions.purge()

        assert not os.path.exists(dest)
        assert not os.path.lexists(dest)

    def test_purge_leaves_regular_files_alone(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
        """Purge never removes a path toda didn't create as a symlink."""
        src = source_file()
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "to_purge")
        # Create regular file instead of symlink
        with open(dest, "w") as f:
            f.write("content")

        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        actions = Actions(m, mock_args)
        actions.purge()

        assert os.path.exists(dest)
        with open(dest) as f:
            assert f.read() == "content"

    def test_purge_leaves_wrong_target_symlink_alone_without_force(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
        """Purge skips a symlink that points somewhere else, unless --force."""
        src = source_file(filename="expected.txt")
        other = source_file(content="other", filename="other.txt")
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "to_purge")
        os.symlink(other, dest)

        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        actions = Actions(m, mock_args)
        actions.purge()

        assert os.path.islink(dest)
        assert os.readlink(dest) == other

    def test_purge_backs_up_regular_file_with_force(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
        src = source_file()
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "to_purge")
        with open(dest, "w") as f:
            f.write("content")

        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = True
        actions = Actions(m, mock_args)
        actions.purge()

        assert not os.path.exists(dest)
        assert os.path.exists(dest + ".toda-backup")

    def test_purge_handles_nonexistent(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
        """Purge doesn't fail for files that don't exist."""
        src = source_file()
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "nonexistent")

        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        actions = Actions(m, mock_args)
        # Should not raise
        actions.purge()

    def test_purge_returns_zero_on_success(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
        src = source_file()
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "to_purge")
        os.symlink(src, dest)

        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        actions = Actions(m, mock_args)

        assert actions.purge() == 0

    def test_purge_skip_is_a_failure_with_strict(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
        src = source_file()
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "to_purge")
        with open(dest, "w") as f:
            f.write("content")

        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        mock_args.strict = True
        actions = Actions(m, mock_args)

        assert actions.purge() == 1

    def test_purge_skips_delete_macro_entries(
        self, temp_dir, manifest_file, mock_args
    ):
        dest = os.path.join(temp_dir, "gone")
        with open(dest, "w") as f:
            f.write("keep me")
        content = f"$default\n{dest}: @delete\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        actions = Actions(m, mock_args)

        assert actions.purge() == 0
        assert os.path.exists(dest)


class TestActionsInspect:
    """Test Actions.inspect method."""

    def test_inspect_prints_output(self, manifest_file, mock_args, capsys, temp_dir):
        content = "$default\n~/.test: source\n$other\n@include: default\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        actions = Actions(m, mock_args)
        actions.inspect()

        captured = capsys.readouterr()
        assert "inspecting" in captured.out

    def test_inspect_shows_includes(self, manifest_file, mock_args, capsys, temp_dir):
        content = "$base\n~/.base: base\n$extended\n@include: base\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["extended"]
        actions = Actions(m, mock_args)
        actions.inspect()

        captured = capsys.readouterr()
        assert "base" in captured.out


class TestAssertSymlinkWorks:
    """Test _assert_symlink_works method."""

    def test_skips_with_no_preflight(self, mock_args, temp_dir):
        mock_args.no_preflight = True
        m = Manifest(startdir=temp_dir)
        actions = Actions(m, mock_args)
        # Should not raise or do anything

    def test_creates_and_removes_test_symlink(self, temp_dir, mock_args):
        mock_args.no_preflight = False
        m = Manifest(startdir=temp_dir)
        old_cwd = temp_dir  # Safe fallback
        try:
            old_cwd = os.getcwd()
        except FileNotFoundError:
            pass  # cwd was deleted by previous test
        try:
            os.chdir(temp_dir)
            Actions(m, mock_args)
            assert os.listdir(temp_dir) == []
        finally:
            os.chdir(old_cwd)


class TestActionsTrace:
    """Test Actions.trace method."""

    def test_trace_text_output(self, temp_dir, manifest_file, source_file, mock_args, capsys):
        src = source_file(content="trace", filename="source.txt")
        src_basename = os.path.basename(src)
        content = (
            f"$base\n~/.base: {src_basename}\n"
            f"$default\n@include: base\n~/.default: {src_basename}\n"
        )
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        mock_args.action = "trace"
        mock_args.section = ["default"]
        mock_args.format = "text"
        actions = Actions(m, mock_args)

        actions.trace()

        captured = capsys.readouterr()
        assert "section=base" in captured.out
        assert "chain=default -> base" in captured.out

    def test_trace_json_output(self, temp_dir, manifest_file, source_file, mock_args, capsys):
        src = source_file(content="trace", filename="source.txt")
        src_basename = os.path.basename(src)
        content = f"$default\n~/.default: {src_basename}\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        mock_args.action = "trace"
        mock_args.section = ["default"]
        mock_args.format = "json"
        actions = Actions(m, mock_args)

        actions.trace()

        payload = json.loads(capsys.readouterr().out)
        assert payload[0]["declared_section"] == "default"
        assert payload[0]["raw_declaration"] == "~/.default: source.txt"

    def test_trace_skips_delete_macro(self, temp_dir, manifest_file, mock_args, capsys):
        dest = os.path.join(temp_dir, "gone")
        content = f"$default\n{dest}: @delete\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        mock_args.action = "trace"
        mock_args.section = ["default"]
        mock_args.format = "json"
        actions = Actions(m, mock_args)

        actions.trace()
        payload = json.loads(capsys.readouterr().out)
        assert payload == []


class TestActionsReconcile:
    """Test Actions.reconcile method."""

    def test_reconcile_outputs_statuses(self, temp_dir, manifest_file, source_file, mock_args, capsys):
        src = source_file(content="reconcile", filename="source.txt")
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "dest")
        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        mock_args.action = "reconcile"
        mock_args.section = ["default"]
        mock_args.format = "text"
        mock_args.color = "never"
        actions = Actions(m, mock_args)

        actions.reconcile()
        captured = capsys.readouterr()
        assert "missing" in captured.out
        assert dest in captured.out

    def test_reconcile_exit_code_for_drift(self, temp_dir, manifest_file, source_file, mock_args):
        src = source_file(content="reconcile", filename="source.txt")
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "dest")
        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        mock_args.action = "reconcile"
        mock_args.section = ["default"]
        mock_args.format = "text"
        mock_args.color = "never"
        actions = Actions(m, mock_args)

        assert actions.reconcile() == 2

    def test_reconcile_exit_code_for_clean_state(self, temp_dir, manifest_file, source_file, mock_args):
        src = source_file(content="reconcile", filename="source.txt")
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "dest")
        os.symlink(src, dest)
        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        mock_args.action = "reconcile"
        mock_args.section = ["default"]
        mock_args.format = "json"
        actions = Actions(m, mock_args)

        assert actions.reconcile() == 0
