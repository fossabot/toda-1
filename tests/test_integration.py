"""Integration tests for toda package."""

import os
import pytest
from toda.errors import ManifestError
from toda.model import Manifest
from toda.controller import Actions


class TestIntegrationInstallPurge:
    """Integration tests for install/purge workflow."""

    def test_full_install_workflow(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
        """Complete install workflow creates expected symlinks."""
        # Create source files
        src1 = source_file(content="config1", filename="config1.txt")
        src2 = source_file(content="config2", filename="config2.txt")

        # Create destinations within temp_dir to avoid touching home
        dest1 = os.path.join(temp_dir, "installed", "config1")
        dest2 = os.path.join(temp_dir, "installed", "config2")

        content = f"$default\n{dest1}: config1.txt\n{dest2}: config2.txt\n"
        path = manifest_file(content)

        # Install
        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        actions = Actions(m, mock_args)
        actions.install()

        # Verify
        assert os.path.islink(dest1)
        assert os.path.islink(dest2)
        with open(dest1) as f:
            assert f.read() == "config1"
        with open(dest2) as f:
            assert f.read() == "config2"

    def test_full_purge_workflow(self, temp_dir, manifest_file, source_file, mock_args):
        """Complete purge workflow removes expected files."""
        src = source_file(content="content")
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "to_purge")

        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)

        # Install first
        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        actions = Actions(m, mock_args)
        actions.install()
        assert os.path.islink(dest)

        # Purge
        actions.purge()
        assert not os.path.exists(dest)

    def test_include_inheritance(self, temp_dir, manifest_file, source_file, mock_args):
        """Sections with @include inherit files from other sections."""
        src_base = source_file(content="base config", filename="base.conf")
        src_extra = source_file(content="extra config", filename="extra.conf")

        dest_base = os.path.join(temp_dir, "installed", "base.conf")
        dest_extra = os.path.join(temp_dir, "installed", "extra.conf")

        content = f"""$base
{dest_base}: base.conf

$full
@include: base
{dest_extra}: extra.conf
"""
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["full"]
        mock_args.force = False
        actions = Actions(m, mock_args)
        actions.install()

        # Both should be installed
        assert os.path.islink(dest_base)
        assert os.path.islink(dest_extra)

    def test_glob_expansion(self, temp_dir, manifest_file, source_dir, mock_args):
        """Glob patterns expand to all matching files."""
        srcdir = source_dir(
            dirname="dotfiles",
            files={
                "bashrc": "bash config",
                "vimrc": "vim config",
                "gitconfig": "git config",
            },
        )

        dest_dir = os.path.join(temp_dir, "installed")
        os.makedirs(dest_dir, exist_ok=True)

        content = f"$default\n{dest_dir}/: dotfiles/*\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        actions = Actions(m, mock_args)
        actions.install()

        # All three files should be linked
        assert os.path.islink(os.path.join(dest_dir, "bashrc"))
        assert os.path.islink(os.path.join(dest_dir, "vimrc"))
        assert os.path.islink(os.path.join(dest_dir, "gitconfig"))

    def test_force_clobber(self, temp_dir, manifest_file, source_file, mock_args):
        """Force flag allows clobbering existing files."""
        src = source_file(content="new content")
        src_basename = os.path.basename(src)
        dest = os.path.join(temp_dir, "existing")

        # Create existing file
        with open(dest, "w") as f:
            f.write("old content")

        content = f"$default\n{dest}: {src_basename}\n"
        path = manifest_file(content)

        # Install without force - should skip
        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        actions = Actions(m, mock_args)
        actions.install()

        assert not os.path.islink(dest)
        with open(dest) as f:
            assert f.read() == "old content"

        # Install with force - should clobber
        mock_args.force = True
        actions = Actions(m, mock_args)
        actions.install()

        assert os.path.islink(dest)
        with open(dest) as f:
            assert f.read() == "new content"

    def test_multiple_sections(self, temp_dir, manifest_file, mock_args):
        """Multiple sections can be installed at once."""
        # Create source directory with files
        src_dir = os.path.join(temp_dir, "sources")
        os.makedirs(src_dir)
        src1 = os.path.join(src_dir, "work.conf")
        src2 = os.path.join(src_dir, "home.conf")
        with open(src1, "w") as f:
            f.write("work config")
        with open(src2, "w") as f:
            f.write("home config")

        # Create destination paths (different from sources)
        dest1 = os.path.join(temp_dir, "installed", "work.conf")
        dest2 = os.path.join(temp_dir, "installed", "home.conf")

        content = f"""$work
{dest1}: sources/work.conf

$home
{dest2}: sources/home.conf
"""
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["work", "home"]
        mock_args.force = False
        actions = Actions(m, mock_args)
        actions.install()

        assert os.path.islink(dest1)
        assert os.path.islink(dest2)


class TestIntegrationErrorHandling:
    """Integration tests for error scenarios."""

    def test_missing_source_file(self, temp_dir, manifest_file, mock_args):
        """Missing source file is logged and fails the install, without raising."""
        dest = os.path.join(temp_dir, "link")
        content = f"$default\n{dest}: nonexistent.txt\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["default"]
        mock_args.force = False
        actions = Actions(m, mock_args)

        assert actions.install() == 1
        assert not os.path.lexists(dest)

    def test_circular_include_detection(self, temp_dir, manifest_file, mock_args):
        """Circular includes are detected and raise error."""
        content = "$a\n@include: b\n$b\n@include: a\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)
        mock_args.section = ["a"]
        actions = Actions(m, mock_args)

        with pytest.raises(ManifestError, match="include cycle detected"):
            actions.install()


class TestIntegrationTildeExpansion:
    """Integration tests for tilde expansion."""

    def test_tilde_expansion_in_dest(
        self, temp_dir, manifest_file, source_file, mock_args
    ):
        """Tilde in destination is expanded."""
        src = source_file(content="content")
        src_basename = os.path.basename(src)

        # Use a relative path for dest that uses tilde
        content = f"$default\n~/.test_toda_config: {src_basename}\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)

        # Iterate and check that tilde is expanded
        results = list(m.iter_section("default"))
        dest, _ = results[0]

        assert "~" not in dest
        assert os.path.expanduser("~") in dest

    def test_tilde_expansion_in_src(self, temp_dir, manifest_file, mock_args):
        """Tilde in source is expanded."""
        dest = os.path.join(temp_dir, "link")

        content = f"$default\n{dest}: ~/.bashrc\n"
        path = manifest_file(content)

        m = Manifest(path=path, startdir=temp_dir)

        results = list(m.iter_section("default"))
        _, src = results[0]

        assert "~" not in src
