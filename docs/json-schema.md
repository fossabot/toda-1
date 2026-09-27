# JSON output

`toda trace --format json`, `toda reconcile --format json` and
`toda inspect --format json` print a single JSON document to stdout.

Every document carries a `schema_version`, currently `1`. Consumers should
check it and refuse to parse a higher version rather than guess.

All documents are printed with sorted keys and two-space indentation. Paths
are absolute and normalized, using the separator of the host platform.

## `reconcile`

```json
{
  "schema_version": 1,
  "has_drift": true,
  "totals": {
    "ok": 12,
    "missing": 1,
    "wrong_target": 0,
    "overwritten_file": 0,
    "overwritten_dir": 0,
    "manifest_conflict": 0
  },
  "entries": [
    {
      "dest": "/home/me/.vimrc",
      "status": "missing",
      "expected_src": "/home/me/dotfiles/vimrc",
      "actual_target": null,
      "actual_kind": "missing",
      "conflict_sources": [],
      "declarations": [
        {
          "dest": "/home/me/.vimrc",
          "src": "/home/me/dotfiles/vimrc",
          "declared_section": "default",
          "declaration_line": 2,
          "manifest_path": "/home/me/dotfiles/MANIFEST",
          "raw_declaration": "~/.vimrc: vimrc",
          "include_chain": ["default"],
          "glob_origin": null
        }
      ]
    }
  ]
}
```

- `status` is one of `ok`, `missing`, `wrong_target`, `overwritten_file`,
  `overwritten_dir`, `manifest_conflict`.
- `actual_kind` is one of `symlink`, `file`, `directory`, `missing`.
- `actual_target` is the link target when the destination is a symlink, with a
  relative target resolved against the destination's directory. It is `null`
  otherwise.
- `expected_src` is `null` for a `manifest_conflict`.
- `conflict_sources` lists the competing sources, and is empty unless the
  status is `manifest_conflict`.
- `declarations` lists every manifest line that resolved to this destination,
  with its origin. Every entry comes from the manifest, so it is never empty.
- `has_drift` is true when any entry is not `ok`.

## `trace`

```json
{
  "schema_version": 1,
  "entries": [
    {
      "dest": "/home/me/.config/git/config",
      "src": "/home/me/dotfiles/gitconfig",
      "declared_section": "base",
      "declaration_line": 12,
      "manifest_path": "/home/me/dotfiles/MANIFEST",
      "raw_declaration": "~/.config/git/config: gitconfig",
      "include_chain": ["default", "base"],
      "glob_origin": null
    }
  ]
}
```

`include_chain` starts with the section requested on the command line and ends
with the section holding the declaration. `glob_origin` is the glob pattern
that produced the entry, or `null` when the entry is a direct mapping.
`@delete` entries are omitted.

## `inspect`

```json
{
  "schema_version": 1,
  "sections": [
    {
      "name": "default",
      "includes": ["base"],
      "declarations": [
        {"dest": "~/.base", "src": "base"}
      ]
    }
  ]
}
```

`inspect` reports the manifest as parsed, so paths are the literal strings
from the file rather than resolved paths, and `@include` lines appear in
`includes` rather than in `declarations`.
