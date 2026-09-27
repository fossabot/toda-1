"""End-to-end tests that drive the installed CLI the way a user would.

These run the real `python -m toda` process against a real filesystem, on
every OS in the CI matrix.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def toda(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "toda", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def make_dotfiles(root: Path) -> tuple[Path, Path]:
    """A dotfiles repo plus a home directory, with one manifest entry."""
    dots = root / "dots"
    home = root / "home"
    dots.mkdir()
    home.mkdir()
    (dots / "vimrc").write_text("set number\n", encoding="utf-8")
    write_manifest(dots, [(str(home / ".vimrc"), "vimrc")])
    return dots, home


def write_manifest(dots: Path, entries: list[tuple[str, str]]) -> Path:
    body = "".join(
        "{dest}: {src}\n".format(dest=dest, src=src) for dest, src in entries
    )
    manifest = dots / "MANIFEST"
    manifest.write_text("$default\n" + body, encoding="utf-8")
    return manifest


def test_install_then_reconcile_from_another_directory(tmp_path: Path) -> None:
    dots, home = make_dotfiles(tmp_path)
    manifest = dots / "MANIFEST"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    install = toda("install", "--manifest", str(manifest), "default", cwd=elsewhere)
    assert install.returncode == 0, install.stderr

    link = home / ".vimrc"
    assert link.is_symlink()
    assert link.resolve() == (dots / "vimrc").resolve()

    reconcile = toda(
        "reconcile",
        "--manifest",
        str(manifest),
        "--color",
        "never",
        "default",
        cwd=elsewhere,
    )
    assert reconcile.returncode == 0, reconcile.stdout + reconcile.stderr


def test_dry_run_leaves_the_filesystem_untouched(tmp_path: Path) -> None:
    dots, home = make_dotfiles(tmp_path)
    manifest = dots / "MANIFEST"

    result = toda(
        "install", "--dry-run", "--manifest", str(manifest), "default", cwd=tmp_path
    )

    assert result.returncode == 0, result.stderr
    assert "would link" in result.stdout
    assert list(home.iterdir()) == []


def test_reconcile_exits_2_on_drift(tmp_path: Path) -> None:
    dots, home = make_dotfiles(tmp_path)
    manifest = dots / "MANIFEST"

    toda("install", "--manifest", str(manifest), "default", cwd=tmp_path)
    link = home / ".vimrc"
    link.unlink()
    link.write_text("local change\n", encoding="utf-8")

    result = toda("reconcile", "--manifest", str(manifest), "default", cwd=tmp_path)

    assert result.returncode == 2
    assert "overwritten_file" in result.stdout


def test_purge_removes_links_but_not_unowned_files(tmp_path: Path) -> None:
    dots, home = make_dotfiles(tmp_path)
    important = home / ".important"
    important.write_text("mine\n", encoding="utf-8")
    manifest = write_manifest(
        dots,
        [(str(home / ".vimrc"), "vimrc"), (str(important), "vimrc")],
    )

    install = toda("install", "--manifest", str(manifest), "default", cwd=tmp_path)
    assert install.returncode == 0
    result = toda("purge", "--manifest", str(manifest), "default", cwd=tmp_path)

    assert result.returncode == 0
    assert not (home / ".vimrc").is_symlink()
    assert important.read_text(encoding="utf-8") == "mine\n"


def test_version_and_help(tmp_path: Path) -> None:
    version = toda("--version", cwd=tmp_path)
    assert version.returncode == 0
    assert version.stdout.startswith("toda ")

    help_result = toda("--help", cwd=tmp_path)
    assert help_result.returncode == 0
    assert "reconcile" in help_result.stdout
