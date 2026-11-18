---
repos: [taskflow, metromesh]
---
# Managed Repositories

| name      | url                              | branch | stage            |
|-----------|----------------------------------|--------|------------------|
| taskflow  | https://github.com/hamzajg/taskflow.git | main | greenfield       |
| metromesh | https://github.com/hamzajg/metromesh.git | main | greenfield      |

## Per-repo notes
### taskflow
- New product (greenfield rewrite). Stack: Quarkus + React/TypeScript.
- Requirements source: legacy/taskifysaas-113 (read-only reference;
  never referenced in this repo — different product name, fresh code).
- First feature: workspaces & accounts.

### metromesh
- New product (greenfield). Stack and MVP boundary are decided in product specs.
- Requirements source: library event-driven microservices resource (read-only
  reference; never referenced in this repo — different product name, fresh specs/code).
- First feature: chosen by product framing from the synthesized requirements dossier.
