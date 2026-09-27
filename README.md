<!-- vi: ft=markdown tw=80 ts=2 sw=2 sts=2 fdm=expr et: -->

# Toda

[![CI](https://github.com/hgto/toda/actions/workflows/ci.yml/badge.svg)](https://github.com/hgto/toda/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/hgto/toda/branch/develop/graph/badge.svg)](https://codecov.io/gh/hgto/toda)
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2Fhgto%2Ftoda.svg?type=shield)](https://app.fossa.com/projects/git%2Bgithub.com%2Fhgto%2Ftoda?ref=badge_shield)

Toda ([תודה](https://en.wiktionary.org/wiki/%D7%AA%D7%95%D7%93%D7%94)) deploys
your dotfiles as symlinks, tells you exactly where each link came from, and
reports when your system has drifted. Pure Python, no dependencies.

```console
$ toda reconcile
- missing        /home/me/.vimrc expected=/home/me/dotfiles/vimrc
! wrong_target   /home/me/.config/git/config expected=/home/me/dotfiles/gitconfig actual=/home/me/old-config
totals ok=12 missing=1 wrong_target=1 overwritten_file=0 overwritten_dir=0 manifest_conflict=0
```

## Why toda

Most dotfile managers tell you how to make links. Toda also tells you whether
they are still right, and where each one came from.

| | toda | GNU Stow | dotbot | chezmoi |
| --- | --- | --- | --- | --- |
| Runtime dependencies | none (core Python) | Perl | Python | Go binary |
| Links files by | manifest | directory tree | config directives | file contents |
| Drift / diff report | yes (`reconcile`) | no | no | yes (`diff`) |
| Link provenance | yes (`trace`) | no | no | partial |
| Templating and secrets | no | no | no | yes |
| Windows | yes | no | yes | yes |

## Install

```console
uv tool install toda     # or: pipx install toda
```

Toda requires Python 3.10 or newer. It supports Linux, macOS, the BSDs and
Windows.

On Windows, creating symlinks requires Developer Mode or administrator rights.
Toda checks this before it changes anything and refuses to run when symlinks
are unavailable.

## Quickstart

Put your dotfiles in a repo next to a `MANIFEST`:

```console
dotfiles/
├── MANIFEST
├── gitconfig
└── vimrc
```

```
$default
~/.vimrc: vimrc
~/.config/git/config: gitconfig
```

Then:

```console
$ toda install --dry-run      # see the plan, change nothing
would link /home/me/.vimrc -> /home/me/dotfiles/vimrc
would link /home/me/.config/git/config -> /home/me/dotfiles/gitconfig

$ toda install                # do it
$ toda reconcile              # is the system still correct?
```

Sources are relative to the directory holding the manifest, so the commands
work from any working directory, and the same manifest works on every machine.

## Actions

```
install     create links from manifest sections
purge       remove destination paths defined by manifest sections
inspect     print section include relationships
trace       show resolved link provenance (declaration source + include chain)
reconcile   diff expected links vs filesystem (exit 0 clean, 2 drift, 1 error)
help        show this help message and exit
```

`install` and `purge` accept `-n/--dry-run`, which prints the plan instead of
applying it, and `-f/--force`, which replaces an existing file or directory
after moving it aside to `<dest>.toda-backup`. Under `--force`, `install`
also removes an `@delete` destination that is a directory, along with
everything in it.

`purge` removes only symlinks toda owns, meaning links pointing at the
expected source. A regular file that happens to sit at a manifest destination
is reported and left alone.

### Exit codes

| code | meaning |
| --- | --- |
| 0 | success; for `reconcile`, no drift |
| 1 | operational failure, or a skipped entry under `--strict` |
| 2 | `reconcile` found drift or a manifest conflict |

## `MANIFEST` file syntax

- `~/bin/destination_link: ./section/source_file`
  - destination-to-source mapping, with the two arguments delimited by a colon

- `$ bin`
  - defines the `bin` section

- `~/.old_config: @delete`
  - deletes `~/.old_config` if it exists; a directory needs `--force`, which
    removes it recursively

- `@include: bin default`
  - includes `bin` and `default`
  - includes are resolved recursively in deterministic order and each included
    section is processed once

- `~/.config/: config/*`
  - links every entry of a source directory into a destination directory; the
    destination must end in `/`

See [docs/manifest.md](docs/manifest.md) for the full grammar and its edge
cases.

## Manifest discovery

`toda` locates the manifest in this order:

1. the `-m`/`--manifest` flag
2. the `TODA_MANIFEST` environment variable
3. the nearest `MANIFEST` found walking up from the current directory

That means you can run `toda reconcile default` anywhere inside a dotfiles
repo and it will find the repo's manifest. If none is found, `./MANIFEST` is
used and the error names the path.

## Variables

`${VAR}` in a destination or source is replaced with the value of the
environment variable `VAR`. Only the braced form is expanded, and an unset
variable is left as written:

```
${XDG_CONFIG_HOME}/git/config: gitconfig
```

## Windows paths

A colon that follows a single drive letter (`C:\`, `c:/`) is part of the path,
not the destination/source separator, so absolute Windows paths work in both
positions:

```
~/note: C:\Users\me\notes.txt
```

## Provenance (`trace`)

`trace` shows where each resolved link came from in the manifest:

```console
$ toda trace default
/Users/me/.config/git/config <- /repo/dotfiles/gitconfig [section=base line=12 chain=default -> base]
```

Use JSON for tooling:

```console
$ toda trace --format json default
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

```console
$ toda reconcile --only-changed default
$ toda reconcile --format json default
$ toda reconcile --color never default
```

## JSON output

`trace`, `reconcile` and `inspect --format json` emit a document with a
`schema_version` field, currently `1`. Pin against it when consuming the
output from other tools. See [docs/json-schema.md](docs/json-schema.md).

## CLI reference

```
usage: toda [-h] [-n] [-m MANIFEST] [--version] [-f] [--strict] [-v] [-d DIR]
            [--no-preflight] [--format {text,json}]
            [--color {auto,always,never}] [--only-changed]
            [{install,purge,inspect,trace,reconcile,help}] [section ...]

creates symlinks described by a manifest

positional arguments:
  {install,purge,inspect,trace,reconcile,help}
                        action to run (default: inspect)
  section               manifest target

options:
  -h, --help            show this help message and exit
  -n, --dry-run         print the plan for install/purge without touching the
                        filesystem
  -m MANIFEST, --manifest MANIFEST
                        path to custom manifest file (default: $TODA_MANIFEST,
                        else the nearest MANIFEST walking up from the current
                        directory)
  --version             show program's version number and exit
  -f, --force           allow clobbering files in target paths, and recursive
                        removal of an @delete destination that is a directory
  --strict              treat skipped install/purge entries as failures
  -v, --verbose
  -d DIR, --dir DIR     override HOME and USERPROFILE (tilde expansion)
  --no-preflight        skip the preflight sanity checks
  --format {text,json}  output format for trace/reconcile actions
  --color {auto,always,never}
                        color mode for text output
  --only-changed        for reconcile text output, hide entries with status=ok
```

## CI example

Fail a build when a machine has drifted from its dotfiles:

```yaml
- run: toda install --manifest ./MANIFEST --no-preflight default
- run: toda reconcile --manifest ./MANIFEST --format json --color never default
```

`toda reconcile` exits 2 when links are missing or wrong, so this step fails
the job. See [examples/dotfiles](examples/dotfiles) for a complete repo.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports and pull requests are
welcome.

## License

MPL-2.0. See [LICENSE](LICENSE).


[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2Fhgto%2Ftoda.svg?type=large)](https://app.fossa.com/projects/git%2Bgithub.com%2Fhgto%2Ftoda?ref=badge_large)