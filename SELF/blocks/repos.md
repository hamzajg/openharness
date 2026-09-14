---
name: repos
type: block
location: openharness/repos.py, REPOS.md, sources/
interfaces: [repos.entries, repos.sync]
---
# Block: repos

## Purpose
Single source of truth for managed repositories. Registers repos in a Markdown table (`REPOS.md`), clones/updates them into `sources/` using the user's existing git credentials only.

## Invariants
- **REPOS.md table is authoritative.** Parsed by regex from `| name | url | branch | stage |` rows. Headers/`|---`-style separators are skipped.
- `entries() -> dict[name, {url, branch, stage}]`.
- `sync(*names)`:
  - If no names given → sync all entries.
  - If `sources/<name>/` exists: run `git -C sources/<name> pull --ff-only`.
  - Else: `git clone [-b branch] url sources/<name>`.
  - Prints `✓ <name>: ...` on success, `!! <name>: <error>` on failure.
- `sources/` is **gitignored**. Never committed. Reconstructable via `python -m openharness pull`.
- **No token management.** Auth relies entirely on the user's existing git credentials (ssh-agent, `gh auth`, `~/.netrc`, etc.). No secret surface in the harness. (D007.)
- **D008 (central mode):** Target repos stay pristine. No harness files are copied into them.

## How to Extend
- To add a repo: append a row to the REPOS.md table (use `/add-new-repo` slash command), then `python -m openharness pull <name>`.
- To change default branch or stage, edit the row. Stage is informational (greenfield | legacy-migration | modernization) and surfaced in command preambles.
- `/init` writes the initial REPOS.md draft.
