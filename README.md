<!-- vi: ft=markdown tw=80 ts=2 sw=2 sts=2 fdm=expr et: -->

# Symfest

Symfest gives you the power to safely deploy files using symlinks on any
operating system with Python installed.

Symfest requires only core Python, supporting versions 3.4+ and 2.7 in that order.

Multi-platform support for POSIX-compliant systems, Debian GNU/Linux, Windows,
  macOS and BSDs in that order of priority.

It requires admin on Windows, because symlinking is
a privileged operation on Windows.

## `manifest.py`
```
usage: manifest.py [-h] [-n] [-m MANIFEST] [-f] [-v]
                   [{install,purge,inspect}] [section [section ...]]

creates symlinks described by a manifest

positional arguments:
  {install,purge,inspect}
  section               manifest target

optional arguments:
  -h, --help            show this help message and exit
  -n, --dry-run         nop out all syscalls, verbose
  -m MANIFEST, --manifest MANIFEST
                        path to custom manifest file
  -f, --force           allow clobbering files in target paths
  -v, --verbose
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
   - in each run of `manifest.py` includes are resolved recursively so that they
       are only processed once
