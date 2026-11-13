# AGENTS.md — openharness

Guidance for AI agents (and humans) working in this repository.

## Project

OpenHarness is a local-first workspace harness for multi-repo agentic work.
It plays two roles at once: **workspace manager** (registers repos in
`REPOS.md`, clones them into `sources/`, observes agent sessions via
`oh serve`) and **context package** (agent-facing markdown commands, Python
skills, SELF/ principles, local RAG). The agent CLI (claude/opencode) is
always the orchestrator — the harness never launches or schedules agents.
Stack: Python ≥3.13, optional web UI (`openharness/web`, Vite+TS).

## Commands

Verified 2026-11-13 against CI (`.github/workflows/ci.yml`) and README.

| Task | Command |
|---|---|
| Install | `pip install -e .` (full); tests need `pip install pytest && pip install -e . --no-deps` |
| Test | `pytest` (24 tests; stdlib-only — CI skips heavy RAG deps) |
| CLI | `oh <command>` / `python -m openharness <command>` |
| Run a skill | `python -m openharness run <skill>` |
| Serve (observer UI) | `oh serve` → http://localhost:7337 |
| Repo ops | `oh pull` (clone registered repos into `sources/`) |
| Web UI build | `cd openharness/web && npm ci && npm run build` |

Requires: Python ≥3.13. `sources/` is gitignored and reconstructable via
`pull`; auth uses the user's existing git credentials only.

## Architecture

- `openharness/` — runtime package:
  - `__main__.py` — CLI entry (`oh` commands).
  - `repos.py` — REPOS.md parsing, `sources/` clone/pull management.
  - `registry.py`, `skill.py`, `frontmatter.py`, `env.py` — skill catalog,
    YAML-frontmatter spec parsing (~15 LOC, no PyYAML), ENV.md handling.
  - `serve.py` + `serve_api.py` — observer HTTP API + SSE session stream.
  - `observers/` — per-agent-CLI log tailers (`claude.py`, `opencode.py`,
    `base.py`) — the only vendor-aware code, kept thin.
  - `knowledge/rag.py` — local RAG (ChromaDB + sentence-transformers).
  - `web/` — observer UI (Vite+TS); **observer only, never re-implements
    runtime logic (D005)**.
- `skills/` — executable Python skills grouped by area (`harness/`,
  `security/` e.g. `scan_secrets`, `legacy_migration/` e.g.
  `map_architecture`, `strangler_plan`).
- `SELF/` — the harness's own specs/principles (`PRINCIPLES.md`, decision
  log D001–D008, `blocks/`, `harness/`, `legacy_migration/`, `security/`).
- `REPOS.md` — YAML-frontmatter registry of managed repos (source of truth).
- `tests/` — unittest-style pytest files per module.

### Dual-role model

```
harness root = workspace root
  REPOS.md ──► sources/<repo>/   (clones, gitignored)
  .claude/commands, .opencode/command, skills/, SELF/, ENV.md
       │  discovered natively by agent CLIs running inside the tree
       ▼
agent CLI (orchestrator) ──► skills via `python -m openharness run <skill>`
oh serve (observer) ◄── tails agent session JSONL logs (read-only)
```

## Conventions

- **Markdown-for-specs / Python-for-execution (D002):** anything a human or
  agent reads → `.md` with optional YAML frontmatter; anything a machine
  executes → `.py`. No YAML/TOML spec files.
- **Agent-agnostic (D006):** no vendor SDK imports in runtime code; agent
  differences live in markdown commands + thin observer tailers.
- **Local-first:** no cloud deps; RAG runs locally.
- **Complexity budget (D003):** runtime core ≤ ~300 LOC; serve block has
  its own ~900 LOC budget. Respects KISS — don't grow the core casually.
- **D008:** harness files are never copied into target repos.

## Landmines

- Tests run with `--no-deps` in CI deliberately — the suite must stay
  stdlib-only; don't add imports that require chromadb etc. to tested
  modules without guarding them.
- `sources/` is gitignored — never commit clones; `REPOS.md` is the
  registry.
- `oh serve` observes session JSONL files the agent CLIs already write —
  don't add instrumentation hooks into agents.
- Decision log D001–D008 in `SELF/PRINCIPLES.md` is normative — read it
  before structural changes.
- The web UI must call the same verbs as the CLI (D005) — no business
  logic in TSX.

## Agent rules

- Branch from `main`; name branches `feat/*`, `fix/*`, `chore/*`, `docs/*`.
- Docs-only changes still go through a PR; never commit to `main` directly.
- Verify before claiming: run `pytest` (with `--no-deps` install path) and
  report the real result.
- Keep changes minimal and consistent with surrounding code. Respect the
  D001–D008 decision log.
- Update AGENTS.md / docs/ARCHITECTURE.md when you change commands, the
  skill contract, or module layout.
