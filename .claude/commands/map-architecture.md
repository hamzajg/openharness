---
description: Analyze the target repo(s) and produce a structured architecture map saved to .openharness/context/architecture-<repo>.md and ingested into RAG
allowed-tools: [Bash, Read, Grep, Edit, Write]
---
# /map-architecture — Legacy migration: structured architecture analysis

## Context
!`python -m openharness self`
!`python -m openharness env`

Read REPOS.md and .openharness/ENV.md. If cwd is inside `sources/<repo>`,
that repo is the default target; otherwise ask the user which repo(s).

## Workflow

1. Run the deterministic architecture prep skill:
   ```
   !`python -m openharness run map_architecture --repo-path sources/<repo>`
   ```

2. Using the prep output as a skeleton, perform a deeper analysis using Read and Grep on `sources/<repo>` to identify:
   - Modules / packages and their responsibilities
   - Entry points (web, CLI, workers, background jobs)
   - Coupling hotspots: files/packages with many cross-imports or god classes
   - External dependencies and data stores
   - Migration risks (monolith seams, tightly coupled services, undocumented APIs, tech debt markers)

3. Write the full deliverable to `.openharness/context/architecture-<repo>.md` with sections: Overview, Module Inventory, Entry Points, Coupling Map, Migration Risks, Recommended Slicing Order.

4. Ingest the document so future commands can use it:
   ```
   !`python -m openharness ingest .openharness/context/architecture-<repo>.md`
   ```

5. Offer to proceed with `/strangler-plan`.
