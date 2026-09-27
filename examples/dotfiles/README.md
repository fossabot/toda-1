# Example dotfiles

A small manifest that exercises sections, includes, a glob and `@delete`.

Trial it against a throwaway directory instead of your real home, using `-d`:

```console
$ toda install -d /tmp/toda-trial -m examples/dotfiles/MANIFEST default
$ toda reconcile -d /tmp/toda-trial -m examples/dotfiles/MANIFEST default
$ toda purge -d /tmp/toda-trial -m examples/dotfiles/MANIFEST default
```

Without `-d`, `install` would write into your real home directory: `~/.vimrc`
and `~/.config/`. Use `--dry-run` first if that is what you want.
