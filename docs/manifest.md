# The `MANIFEST` grammar

A manifest is a UTF-8 text file. Every line is stripped of surrounding
whitespace before it is read.

## Comments and blank lines

A line is ignored when it is empty or when its first character is `#`.

```
# this is a comment
```

## Sections

A line starting with `$` declares a section. The rest of the line is the
name, so `$ bin` and `$bin` are the same section.

```
$default
$ shell
```

A section name may not end in `@`, `*` or `:`. Declaring the same section
twice is an error, as is a section declaration with no name.

A line starting with `${` is a mapping, not a section declaration, so a
destination may begin with an environment variable.

## Mappings

Every other line is a mapping of a destination to a source, separated by a
colon:

```
~/bin/destination_link: ./section/source_file
```

Both halves are stripped. A mapping must appear after a section declaration;
a mapping before the first section is an error.

The destination may be repeated across sections, but not twice within one
section.

### The separator

The colon that separates destination from source is the only colon on the
line, with one exception: a colon that follows a single drive letter and is
followed by a slash (`C:\`, `c:/`) belongs to the path.

```
~/note: C:\Users\me\notes.txt
```

Any other line containing two or more colons is an error.

### Paths

- A leading `~` expands to `$HOME`, or `%USERPROFILE%` on Windows. The
  `--dir` flag overrides both.
- `${VAR}` expands to the value of the environment variable `VAR`. An unset
  variable is left as written, and only the braced form is expanded, so
  `$HOME_LITERAL` stays literal.
- A relative source is resolved against the directory holding the manifest,
  not the working directory.
- Paths are normalized, so `~/./a/../b` becomes `~/b`.

## The `@delete` macro

A source of `@delete` removes the destination if it exists:

```
~/.old_config: @delete
```

`@delete` entries are ignored by `reconcile` and `trace`, because they
describe something to remove rather than a link to check. `install` performs
the deletion. A destination that is a directory is reported as a failure
rather than deleted.

## The `@include` macro

```
@include: bin default
```

`@include` pulls the listed sections into the current one. Names are
de-duplicated, and includes are resolved depth-first in declaration order, so
the result is deterministic. Each included section is expanded once even if
several sections include it.

An include naming a section that does not exist is an error, and so is a
cycle:

```
$a
@include: b
$b
@include: a
```

```
include cycle detected: a -> b -> a
```

## Globs

A source ending in `*` links every entry of the source directory into the
destination directory:

```
~/.config/: config/*
```

The destination of a glob must end in `/`. Entries are linked in sorted order,
so the result is deterministic across filesystems. Globs are one level deep;
a directory inside the source directory is linked as a whole.

## Example

```
# shell
$shell
~/.bashrc: bashrc
~/.config/starship.toml: starship.toml

# editor, shared between machines
$editor
~/.vimrc: vimrc
~/.config/nvim/: nvim/*

$default
@include: shell editor
~/.gitconfig: gitconfig
~/.old_config: @delete
```

`toda inspect` prints the parse result, `toda trace default` prints the fully
resolved links with their include chain, and `toda reconcile default` compares
them against the filesystem.
