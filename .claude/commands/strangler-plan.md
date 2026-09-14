---
description: Produce a strangler-fig migration plan from architecture map + ENV constraints, save to .openharness/context/strangler-plan.md, ingest into RAG
allowed-tools: [Bash, Read, Grep, Edit, Write]
---
# /strangler-plan — Incremental migration plan with seams + rollback points

## Context
!`python -m openharness self`
!`python -m openharness env`

Read REPOS.md, .openharness/ENV.md, and `.openharness/context/architecture-<repo>.md` (run `/map-architecture` first if missing).

## Workflow

1. Run the import-graph extractor to feed the planning step:
   ```
   !`python -m openharness run strangler_plan --repo-path sources/<repo> --target ""`
   ```

2. Produce the plan. It MUST include for EACH migration slice:
   - Slice name, scope (packages/modules extracted)
   - Seam definition (interface, anti-corruption layer if needed)
   - Rollback point (how to revert, data backout strategy)
   - Validation step (tests / healthchecks / canary signals)
   - Estimated order relative to other slices
   - Prerequisite slices
   - Known landmines / risks (pull from ENV.md Known Landmines)

3. Write it to `.openharness/context/strangler-plan.md`.

4. Ingest the plan:
   ```
   !`python -m openharness ingest .openharness/context/strangler-plan.md`
   ```
