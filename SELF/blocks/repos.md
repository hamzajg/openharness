---
name: repos
type: block
location: openharness/repos.py, REPOS.md, .openharness/REPOS.local.md, sources/
interfaces: [repos.registry_path, repos.entries, repos.sync]
---
# Block: repos

## Purpose
Single source of truth for managed repositories. The tracked `REPOS.md` is an
agnostic template; `/init` writes the environment-specific table to
`.openharness/REPOS.local.md` (gitignored by default). One registry is active
at a time — the local file when present, otherwise the template. Repos are
cloned/updated into `sources/` using the user's existing git credentials only.

## Invariants
- **One active registry.** `registry_path()` resolves the local override first,
  then `REPOS.md`. An explicit `path` argument always wins. Never merge both
  tables.
- **Active registry table is authoritative.** Parsed by regex from `| name | url | branch | stage |` rows. Headers/`|---`-style separators are skipped.
- `entries(path=None) -> dict[name, {url, branch, stage}]`.
- `sync(*names)`:
  - If no names given → sync all entries.
  - If `sources/<name>/` exists: run `git -C sources/<name> pull --ff-only`.
  - Else: `git clone [-b branch] url sources/<name>`.
  - Prints `✓ <name>: ...` on success, `!! <name>: <error>` on failure.
- `sources/` is **gitignored**. Never committed. Reconstructable via `python -m openharness pull`.
- **No token management.** Auth relies entirely on the user's existing git credentials (ssh-agent, `gh auth`, `~/.netrc`, etc.). No secret surface in the harness. (D007.)
- **D008 (central mode):** Target repos stay pristine. No harness files are copied into them.

## How to Extend
- To add a repo: append a row to the active registry (use `/add-new-repo` slash command). If `.openharness/REPOS.local.md` is absent, copy the template table into it first so the shipped `REPOS.md` stays agnostic. Then run `python -m openharness pull <name>`.
- To change default branch or stage, edit the row. Stage is informational (greenfield | legacy-migration | modernization) and surfaced in command preambles.
- `/init` writes the initial `.openharness/REPOS.local.md` draft and `.openharness/ENV.md` profile.
