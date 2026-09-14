---
description: Clone or pull all repos listed in REPOS.md into sources/
---
# /pull — Sync managed repositories

## Context

Run via Bash and read output:
- `python -m openharness self`
- `python -m openharness env`

Read REPOS.md and .openharness/ENV.md. If a repo-level `sources/<repo>/.openharness/ENV.md` exists, prefer it for that repo scope.

## Workflow

1. Run sync, report raw output verbatim:
   ```bash
   python -m openharness pull
   ```
   (Append specific names if user named them.)

2. If any `!!` errors appear, surface them and suggest checking auth (ssh-agent, `gh auth status`), URL correctness, and network. Never write credentials to disk.
