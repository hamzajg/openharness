---
description: Add a new managed repo to REPOS.md, clone it, optionally scaffold repo-level ENV.md
---
# /add-new-repo — Register and clone a new repository

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

Then read REPOS.md and .openharness/ENV.md.

## Workflow

1. Ask the user (one compact turn): repo name, git URL (https or ssh), branch (default `main`), stage, and role/constraints/landmines notes.

2. Append a row to REPOS.md table. Append `### <name>` under `## Per-repo notes`. Update frontmatter `repos: [...]` list.

3. Clone via:
   ```bash
   python -m openharness pull <name>
   ```

4. Ask whether to scaffold `sources/<name>/.openharness/ENV.md`; if yes, copy skeleton from root `.openharness/ENV.md` and fill in role fields.
