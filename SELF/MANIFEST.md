---
name: OpenHarness
version: 0.1.0
runtime_entry: "python -m openharness"
principles: [KISS, agent-agnostic, markdown-for-specs, python-for-execution, local-first, ui-observer-only]
blocks: [skill-system, rag, command-bridge, env-probe, repos, serve]
---
# OpenHarness MANIFEST

## What OpenHarness Is (dual role)

**Role A — Workspace Manager (the mothership).**
The harness folder is the user's working root for an entire multi-repo product/ecosystem. Target repositories are registered in `REPOS.md` and cloned into `sources/` INSIDE the harness tree (gitignored). Users launch agent CLIs (claude, opencode) from the harness root or from `sources/<repo>` — the harness tree IS the workspace. `oh serve` runs here, monitoring all agent sessions across all managed repos.

**Role B — Context Package (loaded into the agent, in place).**
Because agent sessions run inside the harness tree, the harness's agent-facing assets are natively discoverable by the agent CLI:
- `.claude/commands/` and `.opencode/command/` → slash commands
- `skills/` → Python skills executed via the agent's Bash tool through `python -m openharness run <skill>`
- `SELF/` → the harness's own specs/principles (agent-readable)
- `.openharness/ENV.md` → ecosystem profile; optional repo-level `sources/<repo>/.openharness/ENV.md`
- local RAG (`.openharness/chroma`) for project knowledge

> **The agent CLI is ALWAYS the orchestrator.** The harness never launches agents, never schedules tasks. It provides context (markdown), skills (python), awareness (SELF/ + ENV.md), repo management (REPOS.md + pull), and observation (serve). Harness files are never copied into target repos — repos under `sources/` remain untouched, pristine checkouts. Agent CLIs discover commands via the harness root's `.claude/commands/` / `.opencode/command/` because sessions run inside the harness tree (CLI config dirs are found by walking up from cwd). **This is D008: central mode only.**

## Interfaces

| Verb | Purpose |
|------|---------|
| `python -m openharness run <skill> --k=v` | Discover and invoke a skill by name |
| `python -m openharness ask <query>` | RAG search, print chunks separated by `---` |
| `python -m openharness ingest <path>` | Ingest all `.md` files under path into RAG |
| `python -m openharness env` | JSON of probed env + drift vs `.openharness/ENV.md` |
| `python -m openharness pull [name ...]` | Sync repos from REPOS.md into `sources/` |
| `python -m openharness self [block]` | Print SELF/MANIFEST.md or SELF/blocks/<block>.md |
| `python -m openharness serve [--host H] [--port P]` | Run uvicorn on `openharness.serve:app` (default 127.0.0.1:7337) |
| `oh` (no args) | Print skill catalog (name + first line of docstring) |

## Typical Multi-Terminal Workflow

```
Terminal 1: oh serve                              # observer
Terminal 2: cd sources/portal-api && opencode     # agent for repo A
  > /scan-secrets
Terminal 3: cd sources/portal-web && opencode     # agent for repo B
  > /map-architecture
Browser:    http://localhost:7337                 # all sessions, grouped per repo
```

## Index of Blocks

See `SELF/blocks/<name>.md` for full block specs:

| Block | Purpose |
|-------|---------|
| [skill-system](SELF/blocks/skill-system.md) | `@skill` decorator, discovery via registry, invocation contract |
| [rag](SELF/blocks/rag.md) | Local ChromaDB RAG, ingest / search / as_context |
| [command-bridge](SELF/blocks/command-bridge.md) | Slash command files → agent CLI discovery mechanism |
| [env-probe](SELF/blocks/env-probe.md) | Environment probe + drift check vs ENV.md |
| [repos](SELF/blocks/repos.md) | REPOS.md registry + clone/pull into `sources/` |
| [serve](SELF/blocks/serve.md) | FastAPI observer API + SSE + SPA web UI |
