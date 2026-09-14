---
description: Clone or pull all repos listed in REPOS.md into sources/
---
# /pull — Sync managed repositories

## Context

Run via Bash and read output:
- `python -m openharness self`
- `python -m openharness env`

## Target repo
If the session cwd is inside sources/<repo>, that repo is the default
target. Otherwise ask the user which managed repo to operate on
(see REPOS.md). Never guess.

## Layered ENV
If sources/<repo>/.openharness/ENV.md exists, prefer it over the global
.openharness/ENV.md for that repo. Compare with the live env probe
output and surface any drift; do not silently choose.

Read REPOS.md and .openharness/ENV.md.

## Workflow

1. Run sync, report raw output verbatim:
   ```bash
   python -m openharness pull
   ```
   (Append specific names if user named them.)

2. If any `!!` errors appear, surface them and suggest checking auth (ssh-agent, `gh auth status`), URL correctness, and network. Never write credentials to disk.
