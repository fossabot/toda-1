"""Tests for toda.controller - Actions."""

import contextlib
import json
import os

from toda.controller import Actions
from toda.model import Manifest


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
        with contextlib.suppress(FileNotFoundError):  # cwd could be deleted
            old_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            Actions(m, mock_args)
        finally:
            os.chdir(old_cwd)

    def test_init_skips_preflight(self, mock_args, temp_dir):
        """Actions skips preflight when flag is set."""
        mock_args.no_preflight = True
        m = Manifest(startdir=temp_dir)
        Actions(m, mock_args)
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
        source_file(content="content1", filename="src1.txt")
        source_file(content="content2", filename="src2.txt")
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

    def test_install_force_deletes_directory_tree(
        self, temp_dir, manifest_file, mock_args
    ):
        dest = os.path.join(temp_dir, "adir")
        os.makedirs(os.path.join(dest, "sub"))
        with open(os.path.join(dest, "sub", "child.txt"), "w") as f:
            f.write("child")
        content = f"$default\n{dest}: @delete\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = True

        assert Actions(m, mock_args).install() == 0
        assert not os.path.lexists(dest)

    def test_install_without_force_refuses_directory_delete(
        self, temp_dir, manifest_file, mock_args
    ):
        dest = os.path.join(temp_dir, "adir")
        os.makedirs(dest)
        content = f"$default\n{dest}: @delete\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False

        assert Actions(m, mock_args).install() == 1
        assert os.path.isdir(dest)

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

        with caplog.at_level(logging.WARNING, logger="toda.plan"):
            actions.install()
        assert not any("skipped" in record.message for record in caplog.records)

        caplog.clear()
        with caplog.at_level(logging.INFO, logger="toda.plan"):
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
        assert os.path.samefile(dest, other)

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

    def test_purge_skips_delete_macro_entries(self, temp_dir, manifest_file, mock_args):
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
        assert "$default" in captured.out
        assert "~/.test: source" in captured.out
        assert "@include: default" in captured.out

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
        Actions(m, mock_args)
        # Should not raise or do anything

    def test_creates_and_removes_test_symlink(self, temp_dir, mock_args):
        mock_args.no_preflight = False
        m = Manifest(startdir=temp_dir)
        old_cwd = temp_dir  # Safe fallback
        with contextlib.suppress(FileNotFoundError):  # cwd could be deleted
            old_cwd = os.getcwd()
        try:
            os.chdir(temp_dir)
            Actions(m, mock_args)
            assert os.listdir(temp_dir) == []
        finally:
            os.chdir(old_cwd)


class TestActionsTrace:
    """Test Actions.trace method."""

    def test_trace_text_output(
        self, temp_dir, manifest_file, source_file, mock_args, capsys
    ):
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

    def test_trace_json_output(
        self, temp_dir, manifest_file, source_file, mock_args, capsys
    ):
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
        assert payload["schema_version"] == 1
        assert payload["entries"][0]["declared_section"] == "default"
        assert payload["entries"][0]["raw_declaration"] == "~/.default: source.txt"

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
        assert payload["schema_version"] == 1
        assert payload["entries"] == []


class TestActionsReconcile:
    """Test Actions.reconcile method."""

    def test_reconcile_outputs_statuses(
        self, temp_dir, manifest_file, source_file, mock_args, capsys
    ):
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

    def test_reconcile_exit_code_for_drift(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
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

    def test_reconcile_exit_code_for_clean_state(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
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


class TestInspectJson:
    """inspect --format json emits a versioned, machine-readable document."""

    def test_inspect_json(self, manifest_file, mock_args, capsys, temp_dir):
        content = "$base\n~/.base: base\n$extended\n@include: base\n"
        path = manifest_file(content)
        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["extended"]
        mock_args.format = "json"
        actions = Actions(m, mock_args)

        actions.inspect()

        payload = json.loads(capsys.readouterr().out)
        assert payload["schema_version"] == 1
        by_name = {section["name"]: section for section in payload["sections"]}
        assert by_name["extended"]["includes"] == ["base"]
        assert by_name["base"]["declarations"] == [{"dest": "~/.base", "src": "base"}]
