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

Verified 2026-11-15 against CI (`.github/workflows/ci.yml`) and README.

| Task | Command |
|---|---|
| Install | `pip install -e .` (full); tests need `pip install pytest && pip install -e . --no-deps` |
| Test | `pytest` (stdlib-only — CI skips heavy RAG deps) |
| CLI | `oh <command>` / `python -m openharness <command>` |
| Run a skill | `python -m openharness run <skill>` |
| Delivery loop | `/ship-loop` (agent-driven) · oracle: `python -m openharness run ship_loop --action=next --repo_path=sources/<repo>` |
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
  - `serve.py` + `serve_api.py` — observer HTTP API + SSE streams
    (agent sessions via `/api/stream/{sid}`; ship-loop state via
    `/api/loops` + `/api/loops/stream`, read from
    `sources/*/specs/*/LOOP.state.json`).
  - `metrics.py` — per-session cost/latency rollups over session JSONL
    (`GET /api/sessions/{sid}/metrics`, `GET /api/metrics`).
  - `observers/` — per-agent-CLI log tailers (`claude.py`, `opencode.py`,
    `base.py`) — the only vendor-aware code, kept thin.
  - `knowledge/rag.py` — local RAG (ChromaDB + sentence-transformers).
  - `web/` — observer UI (Vite+TS): Sessions, Loops (live ship-loop
    progress), Skills, SELF, Knowledge; **observer only, never re-implements
    runtime logic (D005)**.
- `skills/` — executable Python skills grouped by area (`harness/`,
  `security/` e.g. `scan_secrets`, `legacy_migration/` e.g.
  `map_architecture`, `strangler_plan`, `product/` e.g. `discover_product`,
  `spec_scaffold`, `wave_plan`, `ship_validate`, `product_map`,
  `ship_loop`, `review_delivery`, `challenge_decision` — the /ship-product
  pipeline, its delivery loop, the independent spec/delivery audit, and the
  optional decision review).
- `.opencode/commands/`, `.claude/commands/` — slash commands (`ship-loop`,
  `ship-product`, `review-delivery`, `challenge-decision`, `sync`, ...).
  `.opencode/agents/`, `.claude/agents/` — subagent roles for the loop
  (`product-framer`, `wave-implementer`, `wave-reviewer`,
  `delivery-verifier`), the independent audit (`delivery-auditor`), and the
  review (`decision-challenger`).
- `SELF/` — the harness's own specs/principles (`PRINCIPLES.md`, decision
  log D001–D013, `blocks/`, `harness/`, `legacy_migration/`, `security/`).
- `REPOS.md` — YAML-frontmatter registry of managed repos (source of truth).
- `tests/` — unittest-style pytest files per module.

### Dual-role model

```
harness root = workspace root
  REPOS.md ──► sources/<repo>/   (clones, gitignored)
  .claude/commands, .opencode/commands, .claude/agents, .opencode/agents,
  skills/, SELF/, ENV.md
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
- **Complexity budgets (D003, split by D012):** core runtime ≤ 300 LOC;
  platform (repos/metrics/observers/serve) ≤ 1100 LOC. Check via
  `GET /api/evolution` stats. Respects KISS — don't grow casually.
- **D008:** harness files are never copied into target repos.
- **D009:** delivery loops are agent-executed, not harness-scheduled. The
  oracle (`skills/product/ship_loop.py`) owns `specs/<feature>/LOOP.md`; the
  agent owns execution. Default merge policy is `review` (PRs stay open).
  `done` means acceptance-validated, not necessarily merged or deployed.
  Dependent waves stack on open predecessor PRs and must be retargeted and
  retested after the parent merges. Specs record an outcome hypothesis;
  post-release learning is optional and is not a finish gate.
- **D010:** phase transitions are guarded by gates declared in
  `specs/<feature>/GATES.md` and tracked in `LOOP.md`. A blocking gate stops
  its phase; only a named human can waive one. Agent-owned gates are resolved
  with evidence; human-owned gates are handed back with `block`.
- **D011:** design decisions get an optional, advisory review
  (`/challenge-decision` + `decision-challenger`). The deterministic skill
  judges record completeness and surfaces signals; the agent judges design
  with evidence. It never blocks a gate, wave, or merge.
- **D013:** specs and deliveries get an independent audit at two checkpoints
  (`SPEC-AUDIT.md` before planning, `DELIVERY-AUDIT.md` before `finish`).
  `review_delivery` builds a deterministic evidence brief; `delivery-auditor`
  re-verifies code and tests and fills `PASS`/`CONCERNS`/`BLOCK`. Advisory by
  default; `/ship-loop` enforces it with `--review=required`. It never marks
  a gate, merges, or edits product code.

## Landmines

- Tests run with `--no-deps` in CI deliberately — the suite must stay
  stdlib-only; don't add imports that require chromadb etc. to tested
  modules without guarding them.
- `sources/` is gitignored — never commit clones; `REPOS.md` is the
  registry.
- `oh serve` observes session JSONL files the agent CLIs already write —
  don't add instrumentation hooks into agents.
- Decision log D001–D013 in `SELF/PRINCIPLES.md` is normative — read it
  before structural changes.
- The web UI must call the same verbs as the CLI (D005) — no business
  logic in TSX.
- Never hand-edit `specs/<feature>/LOOP.md` or `LOOP.state.json`;
  `ship_loop` is their only writer (JSON is the machine projection,
  markdown the human render — both regenerated together).
  The loop is driven by the agent, not by a daemon or cron (D001/D009).
- Never mark a gate `met` without evidence or `waived` without a human's name
  and reason. Fix a wrong gate in `GATES.md`; do not route around it.
- `/challenge-decision` is advisory: never make its verdict a gate or a merge
  blocker, and never let the reviewer edit product code.
- `/review-delivery` is independent: the auditor must not audit its own
  implementation, must not edit `LOOP.md`/`LOOP.state.json`/`GATES.md` or
  product code, and must not mark `PASS` from the deterministic brief alone.
  Enforcement belongs to `ship_loop --review=required`, not the reviewer.
- The delivery-loop protocol does not sandbox agents. Follow host
  permission prompts and target-repo least-privilege guidance; `--merge=auto`
  requires verified branch protection and required CI/security checks.

## Agent rules

- Branch from `main`; name branches `feat/*`, `fix/*`, `chore/*`, `docs/*`.
- Docs-only changes still go through a PR; never commit to `main` directly.
- Verify before claiming: run `pytest` (with `--no-deps` install path) and
  report the real result.
- Keep changes minimal and consistent with surrounding code. Respect the
  D001–D013 decision log.
- For product work, prefer `/ship-loop` (autonomous) or `/ship-product`
  (phased); both keep specs and loop state in the target repo under
  `specs/` and ship one wave per PR.
- Update AGENTS.md / docs/ARCHITECTURE.md when you change commands, the
  skill contract, or module layout.
