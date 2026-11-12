---
product: Hamza JGUERIM — multi-repo software factory
stage: modernization
critical_flows: []
languages: [python, typescript, javascript, java, csharp, swift, ruby, shell]
frameworks: [fastapi, react, vite, spring, dotnet, flask, gradle]
infra: [docker, docker-compose]
ci: github-actions
compliance: []
branch_prefix: "feat/"
---
# Environment Profile

## Product
Personal portfolio of 58 GitHub repositories under `hamzajg`, spanning:
- **Active AI/agent platforms (2026):** openharness, agentcraft, orca-platform, intentfoundry,
  stream-weave-platform, al-minhej, dynamic-soft, ai-agent-bot-mfe, fluxion.
- **Katas / coursework / archived demos (2014-2024):** the remaining repos, used for
  learning and reference. Treat as legacy unless stated otherwise.

## Constraints
- Never commit secrets or credentials.
- Do not force-push to default branches.
- Repos under `sources/` are pristine clones; all work happens on `feat/*` branches.
- Forks: prefer upstream sync; do not open feature PRs against your own fork unless asked.

## Conventions
- Branch prefix: `feat/` (bugfixes may use `fix/`).
- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`.
- One logical change per branch/PR; include a short summary and test evidence.
- Keep existing code style, formatting, and project structure.

## Known Landmines
- Several legacy repos predate modern toolchains (Java 8, .NET Framework, Swift 3) and
  may not build on the current machine (Java 17, no Xcode/.NET SDK guaranteed).
- Large forks (`eShopOnContainers` ~640MB, `odeev-kata` ~69MB) — clone shallow.
- `sources/*` clones accumulate merged `feat/*`/`fix/*`/`chore/*` branches; prune with
  `git branch --merged <default>` after pulling.
- Resolved since profiling: `ai-agent-bot-mfe`'s `AuthService.ts`/`authService.ts`
  case collision (PR #2) and `fluxion`'s empty-repo state (bootstrapped + PR #1).
