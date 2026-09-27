<!-- vi: ft=markdown tw=80 ts=2 sw=2 sts=2 fdm=expr et: -->

# Toda

[![CI](https://github.com/hgto/toda/actions/workflows/ci.yml/badge.svg)](https://github.com/hgto/toda/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/hgto/toda/branch/main/graph/badge.svg)](https://codecov.io/gh/hgto/toda)

Toda ([תודה](https://en.wiktionary.org/wiki/%D7%AA%D7%95%D7%93%D7%94)) gives you
the power to safely deploy files using symlinks on any
operating system with Python installed.

Toda requires only core Python, supporting versions 3.10+. Toda has
multi-platform support for POSIX-compliant systems, Linux (Debian, Ubuntu, etc),
Windows, macOS and BSDs in that order of priority.

On Windows, creating symlinks requires either Developer Mode or administrator
rights.

## `toda`
```
usage: toda [-h] [-n] [-m MANIFEST] [-f] [-v] [-d DIR] [--no-preflight]
            [--format {text,json}] [--color {auto,always,never}]
            [--only-changed]
            [{install,purge,inspect,trace,reconcile,help}] [section ...]

creates symlinks described by a manifest

positional arguments:
  {install,purge,inspect,trace,reconcile,help}
                        action to run (default: inspect)
  section               manifest target

options:
  -h, --help            show this help message and exit
  -n, --dry-run         nop out all syscalls, verbose
  -m MANIFEST, --manifest MANIFEST
                        path to custom manifest file
  -f, --force           allow clobbering files in target paths
  -v, --verbose
  -d DIR, --dir DIR     override HOME and USERPROFILE (tilde expansion)
  --no-preflight        skip the preflight sanity checks
  --format {text,json}  output format for trace/reconcile actions
  --color {auto,always,never}
                        color mode for text output
  --only-changed        for reconcile text output, hide entries with status=ok

actions:
  install     create links from manifest sections
  purge       remove destination paths defined by manifest sections
  inspect     print section include relationships
  trace       show resolved link provenance (declaration source + include chain)
  reconcile   diff expected links vs filesystem state (exit 0 clean, 2 drift/conflict, 1 error)
  help        show this help message and exit
```

## `MANIFEST` file syntax

- `~/bin/destination_link: ./section/source_file`
  - destination-to-source mapping, with the two arguments delimited by a colon

- `$ bin`
  - defines the `bin` section

- `~/.old_config: @delete`
  - deletes `~/.old_config` if it exists

- `@include: bin default`
  - includes `bin` and `default`
  - includes are resolved recursively in deterministic order and each included
    section is processed once

## Provenance (`trace`)

`trace` shows where each resolved link came from in the manifest:

```bash
toda trace default
```

Example text output:

```text
/Users/me/.config/git/config <- /repo/dotfiles/gitconfig [section=base line=12 chain=default -> base]
```

Use JSON for tooling:

```bash
toda trace --format json default
```

## Reconciliation (`reconcile`)

`reconcile` compares manifest expectations against the filesystem and prints a
colored diff-style report. It also returns non-zero for drift in CI usage.

Statuses:

- `ok` (green): destination exists as a symlink and points to expected source.
- `missing` (red): destination does not exist.
- `wrong_target` (red): destination is a symlink but points somewhere else.
- `overwritten_file` (yellow): destination exists as a regular file.
- `overwritten_dir` (yellow): destination exists as a directory.
- `manifest_conflict` (magenta): multiple manifest declarations resolve to the
  same destination with different sources.

Examples:

```bash
toda reconcile --only-changed default
toda reconcile --format json default
toda reconcile --color never default
```

`reconcile` exit codes:

- `0`: all links are `ok`
- `2`: drift/conflicts detected
- `1`: operational failure

## CI Example

```bash
toda install --manifest ./MANIFEST --no-preflight default
toda reconcile --manifest ./MANIFEST --format json --color never default
```
