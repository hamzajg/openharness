---
description: Produce a strangler-fig migration plan from architecture map + ENV constraints, save to .openharness/context/strangler-plan.md, ingest into RAG
---
# /strangler-plan — Incremental migration plan with seams + rollback points

## Context

Run via Bash and read output:
- `python -m openharness self`
- `python -m openharness env`

Read REPOS.md, `.openharness/ENV.md`, and `.openharness/context/architecture-<repo>.md` (run `/map-architecture` first if missing).

## Workflow

1. Run import-graph extractor, read output:
   ```bash
   python -m openharness run strangler_plan --repo-path sources/<repo> --target ""
   ```

2. Produce the plan. For EACH slice include:
   - Slice name, scope (packages/modules)
   - Seam definition (interface, anti-corruption layer if needed)
   - Rollback point (revert, data backout)
   - Validation step (tests / healthchecks / canary)
   - Estimated order
   - Prerequisite slices
   - Known landmines/risks (from ENV.md Known Landmines)

3. Write to `.openharness/context/strangler-plan.md`.

4. Ingest:
   ```bash
   python -m openharness ingest .openharness/context/strangler-plan.md
   ```
