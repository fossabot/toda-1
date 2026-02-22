"""Tests for toda CLI argument parsing."""

import os
import pytest
from unittest.mock import patch, MagicMock


class TestCLIArgumentParsing:
    """Test command line argument parsing."""

    def test_default_action_is_inspect(self, temp_dir):
        """Default action is 'inspect'."""
        from toda.__main__ import main

        # Create a minimal manifest file
        manifest_path = os.path.join(temp_dir, "MANIFEST")
        with open(manifest_path, "w") as f:
            f.write("$default\n")

        with patch("argparse.ArgumentParser.parse_intermixed_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.action = "inspect"
            mock_args.dry_run = False
            mock_args.manifest = manifest_path
            mock_args.force = False
            mock_args.verbose = 0
            mock_args.dir = None
            mock_args.no_preflight = True
            mock_args.section = []
            mock_parse.return_value = mock_args

            with patch("toda.__main__.Actions") as mock_actions:
                mock_actions_instance = MagicMock()
                mock_actions.return_value = mock_actions_instance

                main()

                mock_actions_instance.inspect.assert_called_once()

    def test_install_action(self, temp_dir):
        """Install action calls install method."""
        from toda.__main__ import main

        manifest_path = os.path.join(temp_dir, "MANIFEST")
        with open(manifest_path, "w") as f:
            f.write("$default\n")

        with patch("argparse.ArgumentParser.parse_intermixed_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.action = "install"
            mock_args.dry_run = False
            mock_args.manifest = manifest_path
            mock_args.force = False
            mock_args.verbose = 0
            mock_args.dir = None
            mock_args.no_preflight = True
            mock_args.section = []
            mock_parse.return_value = mock_args

            with patch("toda.__main__.Actions") as mock_actions:
                mock_actions_instance = MagicMock()
                mock_actions.return_value = mock_actions_instance

                main()

                mock_actions_instance.install.assert_called_once()

    def test_purge_action(self, temp_dir):
        """Purge action calls purge method."""
        from toda.__main__ import main

        manifest_path = os.path.join(temp_dir, "MANIFEST")
        with open(manifest_path, "w") as f:
            f.write("$default\n")

        with patch("argparse.ArgumentParser.parse_intermixed_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.action = "purge"
            mock_args.dry_run = False
            mock_args.manifest = manifest_path
            mock_args.force = False
            mock_args.verbose = 0
            mock_args.dir = None
            mock_args.no_preflight = True
            mock_args.section = []
            mock_parse.return_value = mock_args

            with patch("toda.__main__.Actions") as mock_actions:
                mock_actions_instance = MagicMock()
                mock_actions.return_value = mock_actions_instance

                main()

                mock_actions_instance.purge.assert_called_once()

    def test_trace_action(self, temp_dir):
        """Trace action calls trace method."""
        from toda.__main__ import main

        manifest_path = os.path.join(temp_dir, "MANIFEST")
        with open(manifest_path, "w") as f:
            f.write("$default\n")

        with patch("argparse.ArgumentParser.parse_intermixed_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.action = "trace"
            mock_args.dry_run = False
            mock_args.manifest = manifest_path
            mock_args.force = False
            mock_args.verbose = 0
            mock_args.dir = None
            mock_args.no_preflight = True
            mock_args.section = []
            mock_parse.return_value = mock_args

            with patch("toda.__main__.Actions") as mock_actions:
                mock_actions_instance = MagicMock()
                mock_actions.return_value = mock_actions_instance

                main()

                mock_actions_instance.trace.assert_called_once()

    def test_reconcile_action(self, temp_dir):
        """Reconcile action calls reconcile method."""
        from toda.__main__ import main

        manifest_path = os.path.join(temp_dir, "MANIFEST")
        with open(manifest_path, "w") as f:
            f.write("$default\n")

        with patch("argparse.ArgumentParser.parse_intermixed_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.action = "reconcile"
            mock_args.dry_run = False
            mock_args.manifest = manifest_path
            mock_args.force = False
            mock_args.verbose = 0
            mock_args.dir = None
            mock_args.no_preflight = True
            mock_args.section = []
            mock_parse.return_value = mock_args

            with patch("toda.__main__.Actions") as mock_actions:
                mock_actions_instance = MagicMock()
                mock_actions.return_value = mock_actions_instance

                main()

                mock_actions_instance.reconcile.assert_called_once()

    def test_reconcile_action_raises_system_exit_with_code(self, temp_dir):
        """Reconcile action exit code is forwarded as SystemExit."""
        from toda.__main__ import main

        manifest_path = os.path.join(temp_dir, "MANIFEST")
        with open(manifest_path, "w") as f:
            f.write("$default\n")

        with patch("argparse.ArgumentParser.parse_intermixed_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.action = "reconcile"
            mock_args.dry_run = False
            mock_args.manifest = manifest_path
            mock_args.force = False
            mock_args.verbose = 0
            mock_args.dir = None
            mock_args.no_preflight = True
            mock_args.section = []
            mock_parse.return_value = mock_args

            with patch("toda.__main__.Actions") as mock_actions:
                mock_actions_instance = MagicMock()
                mock_actions_instance.reconcile.return_value = 2
                mock_actions.return_value = mock_actions_instance

                with pytest.raises(SystemExit) as exc:
                    main()

                assert exc.value.code == 2

    def test_default_section_is_default(self, temp_dir):
        """Default section is 'default' when none specified."""
        from toda.__main__ import main

        manifest_path = os.path.join(temp_dir, "MANIFEST")
        with open(manifest_path, "w") as f:
            f.write("$default\n")

        with patch("argparse.ArgumentParser.parse_intermixed_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.action = "inspect"
            mock_args.dry_run = False
            mock_args.manifest = manifest_path
            mock_args.force = False
            mock_args.verbose = 0
            mock_args.dir = None
            mock_args.no_preflight = True
            mock_args.section = []  # Empty list
            mock_parse.return_value = mock_args

            with patch("toda.__main__.Actions"):
                main()

                # Section should be set to ('default',)
                assert mock_args.section == ("default",)

    def test_section_trailing_slash_stripped(self, temp_dir):
        """Trailing slashes are stripped from section names."""
        from toda.__main__ import main

        manifest_path = os.path.join(temp_dir, "MANIFEST")
        with open(manifest_path, "w") as f:
            f.write("$mysection\n")

        with patch("argparse.ArgumentParser.parse_intermixed_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.action = "inspect"
            mock_args.dry_run = False
            mock_args.manifest = manifest_path
            mock_args.force = False
            mock_args.verbose = 0
            mock_args.dir = None
            mock_args.no_preflight = True
            mock_args.section = ["mysection/"]
            mock_parse.return_value = mock_args

            with patch("toda.__main__.Actions"):
                main()

                assert mock_args.section == ["mysection"]

    def test_dir_override_sets_env(self, temp_dir):
        """--dir option sets HOME and USERPROFILE."""
        from toda.__main__ import main

        manifest_path = os.path.join(temp_dir, "MANIFEST")
        with open(manifest_path, "w") as f:
            f.write("$default\n")

        with patch("argparse.ArgumentParser.parse_intermixed_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.action = "inspect"
            mock_args.dry_run = False
            mock_args.manifest = manifest_path
            mock_args.force = False
            mock_args.verbose = 0
            mock_args.dir = "/custom/home"
            mock_args.no_preflight = True
            mock_args.section = []
            mock_parse.return_value = mock_args

            with patch("toda.__main__.Actions"):
                with patch.dict(os.environ, {}, clear=False):
                    main()

                    assert os.environ["HOME"] == "/custom/home"
                    assert os.environ["USERPROFILE"] == "/custom/home"

    def test_dry_run_sets_verbose(self, temp_dir):
        """--dry-run sets verbose to 3."""
        from toda.__main__ import main
        import toda.controller as controller

        manifest_path = os.path.join(temp_dir, "MANIFEST")
        with open(manifest_path, "w") as f:
            f.write("$default\n")

        with patch("argparse.ArgumentParser.parse_intermixed_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.action = "inspect"
            mock_args.dry_run = True
            mock_args.manifest = manifest_path
            mock_args.force = False
            mock_args.verbose = 0
            mock_args.dir = None
            mock_args.no_preflight = True
            mock_args.section = []
            mock_parse.return_value = mock_args

            with patch("toda.__main__.Actions"):
                # Store original functions
                original_rmtree = controller.rmtree
                original_remove = controller.remove
                original_makedirs = controller.makedirs
                original_symlink = controller.symlink
                original_chdir = controller.chdir

                try:
                    main()
                    assert mock_args.verbose == 3
                finally:
                    # Restore original functions
                    controller.rmtree = original_rmtree
                    controller.remove = original_remove
                    controller.makedirs = original_makedirs
                    controller.symlink = original_symlink
                    controller.chdir = original_chdir

    def test_invalid_section_raises(self, temp_dir):
        """Invalid section name raises AssertionError."""
        from toda.__main__ import main

        manifest_path = os.path.join(temp_dir, "MANIFEST")
        with open(manifest_path, "w") as f:
            f.write("$default\n")

        with patch("argparse.ArgumentParser.parse_intermixed_args") as mock_parse:
            mock_args = MagicMock()
            mock_args.action = "inspect"
            mock_args.dry_run = False
            mock_args.manifest = manifest_path
            mock_args.force = False
            mock_args.verbose = 0
            mock_args.dir = None
            mock_args.no_preflight = True
            mock_args.section = ["nonexistent"]
            mock_parse.return_value = mock_args

            with pytest.raises(AssertionError, match="not in the manifest"):
                main()
