---
repos: [example-repo]
---
# Managed Repositories

Shipped, agnostic template. `/init` writes your concrete list to
`.openharness/REPOS.local.md` (gitignored by default); that file is the active
registry while it exists, otherwise this table is used (D007).

| name         | url                          | branch | stage            |
|--------------|------------------------------|--------|------------------|
| example-repo | git@github.com:acme/api.git  | main   | legacy-migration |

## Per-repo notes
### example-repo
- <role, stack, constraints, landmines — filled by /init>
