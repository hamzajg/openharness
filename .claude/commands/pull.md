---
description: Clone or pull all repos listed in REPOS.md into sources/
allowed-tools: [Bash, Read]
---
# /pull — Sync managed repositories

## Context
!`python -m openharness self`
!`python -m openharness env`

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

1. Run the sync verb and report raw output back to the user verbatim:
   ```
   !`python -m openharness pull`
   ```
   (Append specific repo names if the user named them, e.g.
   `python -m openharness pull portal-api portal-web`.)

2. If any `!!` lines appear, surface them as errors and suggest checking
   auth (ssh-agent loaded, `gh auth status` ok), URL correctness, and
   network. Do NOT offer to write credentials to disk.
