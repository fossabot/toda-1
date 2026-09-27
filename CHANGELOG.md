# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `toda --version`.
- `inspect --format json`, and a readable section tree for plain `inspect`.
- `--strict`, which makes a skipped `install` or `purge` entry fail the run.
- `#` comments, sections, includes, globs and `@delete` are now covered by
  reference documentation in `docs/manifest.md`, and the JSON output by
  `docs/json-schema.md`.
- An example dotfiles repo under `examples/dotfiles`, exercised by the test
  suite.

### Changed

- **Breaking.** `purge` now removes only symlinks that point at the expected
  source. A regular file or directory at a destination is reported and left
  alone. Pass `--force` to replace it, which moves it to
  `<dest>.toda-backup` instead of deleting it.
- **Breaking.** Relative sources resolve against the directory containing the
  manifest, not the current working directory, so `toda install -m
  ~/dotfiles/MANIFEST` works from anywhere.
- **Breaking.** `trace --format json` returns an object with `entries` and
  `schema_version` rather than a bare array. `reconcile --format json` and
  `inspect --format json` also carry `schema_version`.
- The manifest is discovered from `-m`, then `$TODA_MANIFEST`, then the nearest
  `MANIFEST` walking up from the current directory.
- `install` and `purge` return 1 when an operation fails, instead of always
  returning 0.
- `--dry-run` prints the plan and never touches the filesystem, including the
  preflight check. It is implemented as a plan/apply split rather than by
  monkeypatching syscalls.
- Windows: a colon after a single drive letter is part of the path, so
  `C:\path` works in both positions of a mapping, and directory symlinks are
  created as directory links.
- `${VAR}` expands in destinations and sources. An unset variable is left as
  written.
- Errors are reported as `toda: error: ...` on stderr with exit code 1 instead
  of an `AssertionError` traceback.
- Verbosity flags now affect all of toda's logging, which goes to stderr.

### Fixed

- Directory symlinks are created with `target_is_directory` on Windows.
- `purge` no longer deletes files it did not create.
- A missing or unreadable manifest produces a clear error rather than a
  traceback.

## [0.0.1] - 2021-03-11

Initial release.
