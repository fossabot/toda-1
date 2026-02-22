# AGENTS

## Cross-Platform Editing Policy

All repository edits must remain compatible with:

- macOS
- Windows
- Linux

## Required Engineering Constraints

- Use cross-platform path handling (`os.path` or `pathlib`).
- Do not hardcode path separators (`/` or `\`) in implementation logic.
- Avoid OS-specific shell assumptions in scripts, tests, and CI steps.
- Keep manifest parsing and output order deterministic.
- Add or update tests for behavior that may differ across OSes (especially symlink handling).
- Ensure new CLI behavior runs on all supported Python versions in this repository.
