# Architecture — openharness

Current-state map. Descriptive, not aspirational; normative decisions live
in `SELF/PRINCIPLES.md` (D001–D008). See `docs/adr/` for the baseline record.

## Dual role

OpenHarness is simultaneously:

1. **Workspace manager** — `REPOS.md` (YAML-frontmatter registry) declares
   target repos; `openharness/repos.py` clones them into `sources/`
   (gitignored, reconstructable via `pull`). Launch agent CLIs from the
   harness root or a `sources/<repo>` — the harness tree *is* the workspace.
2. **Context package** — agent-facing assets discoverable in place:
   `.claude/commands/`, `.opencode/command/`, `skills/` (Python, run via
   `python -m openharness run <skill>`), `SELF/` (specs/principles),
   `.openharness/ENV.md`, local RAG index.

## Components

| Piece | File(s) | Role |
|---|---|---|
| CLI | `openharness/__main__.py` | `oh` verbs: serve, pull, run, catalog |
| Repo mgmt | `repos.py`, `registry.py` | REPOS.md parse, clone/pull, skill catalog |
| Specs | `frontmatter.py`, `env.py`, `skill.py` | md+frontmatter parsing, ENV.md, skill runner |
| Observer | `serve.py`, `serve_api.py` | HTTP API + SSE session stream (:7337) |
| Agent adapters | `observers/{base,claude,opencode}.py` | tail agent session JSONL — read-only, thin |
| RAG | `knowledge/rag.py` | ChromaDB + sentence-transformers, local |
| Web UI | `web/` (Vite+TS) | observer dashboard — calls same verbs, no logic (D005) |
| Skills | `skills/{harness,security,legacy_migration}/` | executable Python skills |
| Self specs | `SELF/` | PRINCIPLES.md, decision log, domain blocks |

## Data flow

- **Agent work:** agent CLI runs inside the harness tree → reads markdown
  commands/skills/SELF → executes Python skills via the CLI → writes code
  in `sources/<repo>` → session JSONL lands on disk.
- **Observation:** `oh serve` tails those JSONL logs via `observers/` →
  `serve_api` streams to the web UI. Read-only; the harness never injects
  into agent sessions.

## State

All state is files on disk: `REPOS.md`, `sources/` clones,
`.openharness/ENV.md`, `.openharness/chroma` RAG index, agent session logs.
No database, no cloud.

## Key decisions

See `SELF/PRINCIPLES.md` — D001 (no orchestration), D002 (md specs / py
execution), D003 (LOC budgets), D005 (UI is observer), D006 (log-tail
observation only), D007 (REPOS.md + sources/), D008 (no copying into target
repos).
