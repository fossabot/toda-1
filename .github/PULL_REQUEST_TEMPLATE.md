## What this changes

<!-- One or two sentences. Link the issue it fixes, if there is one. -->

## Checklist

- [ ] `uv run pytest` passes
- [ ] `uv run ruff check toda tests` and `uv run ruff format --check toda tests` pass
- [ ] `uv run mypy toda` passes
- [ ] Paths use `os.path`/`pathlib`, and nothing assumes a POSIX shell
- [ ] Behavior that can differ across systems has a test, especially symlinks
- [ ] `CHANGELOG.md` has an entry under `Unreleased` if a user would notice
