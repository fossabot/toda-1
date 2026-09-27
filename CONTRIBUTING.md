# Contributing

Thanks for taking the time to contribute. This document covers the setup and
the rules a change has to pass.

## Development setup

[uv](https://docs.astral.sh/uv/) creates the environment and locks the
dependency set:

```console
git clone git@github.com:hgto/toda.git
cd toda
uv sync --group dev
```

Then run the checks:

```console
uv run pytest --cov=toda
uv run ruff check toda tests
uv run ruff format --check toda tests
uv run mypy toda
```

`pre-commit` runs the linters and formatters on every commit:

```console
uv tool install pre-commit
pre-commit install
```

## Ground rules

### Cross-platform

Toda supports macOS, Windows and Linux, and every change has to keep working on
all three.

- Use `os.path` or `pathlib` for paths. Never hardcode `/` or `\` in
  implementation logic.
- Do not assume a POSIX shell in scripts, tests or CI.
- Keep manifest parsing and output order deterministic. Sort anything that
  comes from the filesystem.
- Add or update tests for behavior that can differ across systems, especially
  symlink handling. CI runs the suite on all three systems, so a Linux-only
  assumption will fail the build.
- New CLI behavior must work on every supported Python version, currently 3.10
  and newer.

### Code style

- Match the style of the surrounding code. The codebase uses `str.format()`
  rather than f-strings, and `ruff` is configured to leave that alone.
- Keep modules focused: `model.py` parses and resolves, `plan.py` decides the
  operations, `reconcile.py` diffs, `controller.py` drives, `__main__.py` is
  the CLI.
- Prefer self-documenting code and clear names to inline comments.

### Tests

Tests use real temporary directories rather than mocks of the filesystem.
`tests/test_smoke.py` runs the installed CLI in a subprocess, so it covers
argument parsing, exit codes and output together.

A bug fix should come with a test that fails before the fix.

## Pull requests

- Branch from `develop`. `develop` is the integration branch; releases are
  tagged from it.
- Keep a pull request to one change, with a short description of the problem
  and the fix.
- Add a line to `CHANGELOG.md` under `Unreleased` for anything a user would
  notice.
- Make sure `uv run pytest`, `ruff check`, `ruff format --check` and `mypy`
  all pass. CI runs the same commands.

## Releasing

Maintainers cut a release by tagging:

1. In `CHANGELOG.md`, rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD`,
   and add a fresh empty `## [Unreleased]` above it.
2. Commit that on `develop`.
3. Tag it and push the tag:

   ```console
   git tag -a vX.Y.Z -m "vX.Y.Z"
   git push origin vX.Y.Z
   ```

The tag starts the release workflow, which builds the distributions, publishes
them to PyPI over trusted publishing, and opens a GitHub release whose notes
are the CHANGELOG section for that version. `setuptools_scm` derives the
package version from the tag, so do not edit a version by hand.

PyPI will not accept a version twice, so the first release of a new version
number should be a release candidate, such as `v0.2.0rc1`. If anything goes
wrong, that version is expendable and you move to `rc2`. A pre-release is not
installed by default, so it is invisible to anyone running `pip install toda`.

## Reporting bugs

Open an issue with the OS, the Python version, the exact command, and what you
expected to happen. If the bug involves a manifest, include the smallest
manifest that reproduces it.

For security issues, follow [SECURITY.md](SECURITY.md) instead of opening a
public issue.
