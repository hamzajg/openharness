---
description: Clone or pull all repos listed in REPOS.md into sources/
allowed-tools: [Bash, Read]
---
# /pull — Sync managed repositories

## Context
!`python -m openharness self`
!`python -m openharness env`

Read REPOS.md and .openharness/ENV.md. If a repo-level
`sources/<repo>/.openharness/ENV.md` exists for the default repo, prefer it.

## Workflow

1. Run the sync verb and report raw output back to the user verbatim:
   ```
   !`python -m openharness pull`
   ```
   (Append specific repo names if the user named them, e.g.
   `python -m openharness pull portal-api portal-web`.)

2. If any `!!` lines appear, surface them as errors and suggest checking
   auth (ssh-agent loaded, `gh auth status` ok), URL correctness, and
   network. Do NOT offer to write credentials to disk.
