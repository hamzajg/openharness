---
description: Interview the user about the product/ecosystem, write REPOS.md and ENV.md, offer to pull
---
# /init — Initialize the OpenHarness workspace

## Context

First build awareness by running these commands via the Bash tool and reading their output:
- `python -m openharness self` → read the harness manifest + decisions
- `python -m openharness env` → probe live environment + drift check

Then read REPOS.md and .openharness/ENV.md. If the session cwd is inside sources/<repo>, that repo is the default target; otherwise ask the user which repo.

## Workflow

1. Interview the user. Ask in a single compact turn:
   - Product/ecosystem name
   - Stage: `greenfield` | `legacy-migration` | `modernization`
   - Repos to manage: for each collect `name`, `git URL`, `branch`, stage override (if differs), role/notes
   - Known languages, frameworks, infra, CI, compliance requirements
   - Branch prefix convention (default `feat/`)
   - Critical flows, constraints, conventions, landmines

2. Compile the answers into comma-separated triples for repos.

3. Run:
   ```bash
   python -m openharness run init_profile --product="<product>" --stage="<stage>" --repos="name:url:branch|stage,..." --languages="..." --frameworks="..." --infra="..." --ci="<ci>" --compliance="..." --branch_prefix="feat/" --constraints="..." --conventions="..." --landmines="..."
   ```

4. Read the newly written REPOS.md and .openharness/ENV.md. If anything looks wrong, edit manually.

5. Offer to run `/pull` to clone all registered repos into `sources/`.
