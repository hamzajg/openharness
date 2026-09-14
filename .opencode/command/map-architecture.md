---
description: Analyze the target repo(s) and produce a structured architecture map saved to .openharness/context/architecture-<repo>.md and ingested into RAG
---
# /map-architecture — Legacy migration: structured architecture analysis

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

Read REPOS.md and .openharness/ENV.md.

## Workflow

1. Run architecture prep:
   ```bash
   python -m openharness run map_architecture --repo-path sources/<repo>
   ```
   Read its output.

2. Using the prep output plus deeper Read/Grep on `sources/<repo>`, identify:
   - Modules/packages and responsibilities
   - Entry points (web, CLI, workers, background jobs)
   - Coupling hotspots: cross-import-heavy files, god classes
   - External dependencies and data stores
   - Migration risks: monolith seams, tight coupling, undocumented APIs, tech-debt markers

3. Write to `.openharness/context/architecture-<repo>.md` with sections: Overview, Module Inventory, Entry Points, Coupling Map, Migration Risks, Recommended Slicing Order.

4. Ingest:
   ```bash
   python -m openharness ingest .openharness/context/architecture-<repo>.md
   ```

5. Offer `/strangler-plan`.
