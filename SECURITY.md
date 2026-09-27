# Security Policy

## Supported versions

The latest release is supported with security updates. Older releases are not.

## Reporting a vulnerability

Please do not open a public issue for a security problem.

Report it privately through GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability):
open the repository's **Security** tab and choose **Report a vulnerability**.

Include, as far as you can:

- the version of toda, and the OS and Python version,
- the smallest manifest and command that reproduces the problem,
- what an attacker gains, and what access they need to start.

You can expect an acknowledgement within a week, and an assessment with a
fix or a mitigation plan shortly after. Please give us a chance to release a
fix before writing publicly about the issue.

## What toda does to your files

Toda is a tool that changes your filesystem, so its failure modes matter:

- `install` creates symlinks, and only replaces an existing path when
  `--force` is passed. With `--force`, the existing path is renamed to
  `<dest>.toda-backup` rather than deleted.
- `purge` removes a destination only when it is a symlink pointing at the
  source the manifest expects. Files and directories toda did not create are
  reported and left alone.
- `@delete` removes the destination, but refuses to delete a directory.
- `--dry-run` prints the plan without touching the filesystem.
- Toda never reads the contents of your dotfiles, and never sends anything
  over the network.

Anything that lets a manifest cause a write outside these rules, such as a
path traversal that escapes the declared destination, is a security issue and
should be reported privately.
