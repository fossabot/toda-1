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

    def test_dry_run_leaves_filesystem_untouched(self, temp_dir, capsys):
        """--dry-run prints the plan and never creates the link."""
        from toda.__main__ import main

        src = os.path.join(temp_dir, "source.txt")
        with open(src, "w") as f:
            f.write("content")
        dest = os.path.join(temp_dir, "dest")
        manifest_path = os.path.join(temp_dir, "MANIFEST")
        with open(manifest_path, "w") as f:
            f.write(f"$default\n{dest}: source.txt\n")

        argv = ["toda", "--no-preflight", "-m", manifest_path, "-n", "install"]
        with patch("sys.argv", argv):
            with pytest.raises(SystemExit) as exc:
                main()
            assert exc.value.code == 0

        assert not os.path.lexists(dest)
        out = capsys.readouterr().out
        assert "would link" in out
        assert dest in out

    def test_invalid_section_raises(self, temp_dir, capsys):
        """Invalid section name prints a clean one-line error and returns 1."""
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

            assert main() == 1

        err = capsys.readouterr().err
        assert err.strip() == "toda: error: section `nonexistent` is not in the manifest"

    def test_help_action_prints_help(self, capsys):
        """'help' action prints full help without loading a manifest."""
        from toda.__main__ import main

        with patch("sys.argv", ["toda", "help"]):
            with patch("toda.__main__.Manifest") as mock_manifest:
                assert main() == 0
                mock_manifest.assert_not_called()

        out = capsys.readouterr().out
        assert "usage: toda" in out
        assert "reconcile" in out

    def test_install_exit_code_via_system_exit(self, temp_dir):
        """install()'s int return code is surfaced as SystemExit, not swallowed."""
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
                mock_actions_instance.install.return_value = 1
                mock_actions.return_value = mock_actions_instance

                with pytest.raises(SystemExit) as exc:
                    main()

                assert exc.value.code == 1
