# OpenHarness v0.1.0

OpenHarness plays **two roles at once** in a single git repository:

## Dual Role

**Role A — Workspace Manager (the mothership).**
The harness folder is your working root for an entire multi-repo product/ecosystem. Target repositories are registered in `REPOS.md` and cloned into `sources/` (gitignored). Launch agent CLIs (claude, opencode) from the harness root or from `sources/<repo>` — the harness tree **is** the workspace. `oh serve` runs here, monitoring all agent sessions across all managed repos.

**Role B — Context Package (loaded into the agent, in place).**
Because agent sessions run inside the harness tree, the harness's agent-facing assets are natively discoverable:
- `.claude/commands/` and `.opencode/command/` → slash commands
- `skills/` → Python skills executed via `python -m openharness run <skill>`
- `SELF/` → the harness's own specs/principles (agent-readable)
- `.openharness/ENV.md` → ecosystem profile; optional repo-level `sources/<repo>/.openharness/ENV.md`
- Local RAG (`.openharness/chroma`) for project knowledge

> **The agent CLI is ALWAYS the orchestrator.** The harness never launches agents, never schedules tasks. It provides context (markdown), skills (python), awareness (SELF/ + ENV.md), repo management (REPOS.md + pull), and observation (serve).

## Mental Model

```
┌──────────────────────────────────────────────────┐
│  OpenHarness workspace root (you are here)       │
│                                                  │
│  ┌──────────┐     ┌────────────┐     ┌────────┐ │
│  │ oh serve │◄────│  Agent CLI │────►│ Skill  │ │
│  │(observer)│     │(orchestrator)│   │(Python)│ │
│  └──────────┘     └────────────┘     └────────┘ │
│        │                │                       │
│        ▼                ▼                       │
│  ┌──────────┐     ┌────────────┐                │
│  │ Sessions │     │ sources/   │                │
│  │  (SSE)   │     │ repo-a/    │                │
│  └──────────┘     │ repo-b/    │                │
│                   └────────────┘                │
└──────────────────────────────────────────────────┘
```

## Quickstart

```bash
pip install -e .
cd openharness/web && npm ci && npm run build   # build UI
oh serve                                        # terminal 1
opencode                                        # terminal 2 (or claude)
> /init   # register repos, build REPOS.md + ENV.md
> /pull   # clone repos into sources/
```

- **Terminal 1:** `oh serve` — observer (http://localhost:7337)
- **Terminal 2:** `cd sources/portal-api && opencode` → `/scan-secrets`
- **Terminal 3:** `cd sources/portal-web && opencode` → `/map-architecture`
- **Browser:** http://localhost:7337 — all sessions, grouped per repo
