---
description: Add a new managed repo to REPOS.md, clone it, optionally scaffold repo-level ENV.md
allowed-tools: [Bash, Read, Grep, Edit, Write]
---
# /add-new-repo — Register and clone a new repository

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

1. Ask the user for (in one compact turn):
   - Repo name
   - Git URL (https or ssh)
   - Branch (default `main`)
   - Stage: `greenfield` | `legacy-migration` | `modernization`
   - Role / constraints / landmines (free-form notes)

2. Append a row to the REPOS.md table. Append a per-repo note section `### <name>` under `## Per-repo notes`. Update the frontmatter `repos: [...]` list.

3. Clone it immediately by running:
   ```
   !`python -m openharness pull <name>`
   ```

4. Ask the user whether to scaffold a repo-level profile at `sources/<name>/.openharness/ENV.md`. If yes, copy the skeleton from the root `.openharness/ENV.md`, fill the product/role fields from the notes, and add a repo-specific preamble.
