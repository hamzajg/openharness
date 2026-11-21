---
description: Interview the user, write the local repo registry and ENV.md, offer to pull
allowed-tools: [Bash, Read, Grep, Edit, Write]
---
# /init — Initialize the OpenHarness workspace

## Context
!`python -m openharness self`
!`python -m openharness env`

## Target repo
If the session cwd is inside sources/<repo>, that repo is the default
target. Otherwise ask the user which managed repo to operate on
(see the active registry: REPOS.md or .openharness/REPOS.local.md). Never guess.

## Layered ENV
If sources/<repo>/.openharness/ENV.md exists, prefer it over the global
.openharness/ENV.md for that repo. Compare with the live env probe
output and surface any drift; do not silently choose.

Read the active registry (REPOS.md or .openharness/REPOS.local.md) and .openharness/ENV.md.

## Workflow

1. Interview the user. Ask in a single compact turn:
   - Product/ecosystem name
   - Stage: `greenfield` | `legacy-migration` | `modernization`
   - Repos to manage: for each collect `name`, `git URL`, `branch`, stage override (if differs from ecosystem stage), role/notes
   - Known languages, frameworks, infra, CI, compliance requirements
   - Branch prefix convention (default `feat/`)
   - Critical flows, constraints, conventions, landmines

2. Compile the answers into comma-separated triples for repos.

3. Write the initial drafts by running:
   ```
   !`python -m openharness run init_profile --product="<product>" --stage="<stage>" --repos="name:url:branch|stage,..." --languages="..." --frameworks="..." --infra="..." --ci="<ci>" --compliance="..." --branch_prefix="feat/" --constraints="..." --conventions="..." --landmines="..."`
   ```

4. Read the newly written `.openharness/REPOS.local.md` and `.openharness/ENV.md`. The shipped `REPOS.md` stays an agnostic template. If anything looks wrong (e.g. URL parse failures in the table), edit manually.

5. Offer to run `/pull` to clone all registered repos into `sources/`.
