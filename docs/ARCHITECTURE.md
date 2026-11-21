# Architecture — openharness

Current-state map. Descriptive, not aspirational; normative decisions live
in `SELF/PRINCIPLES.md` (D001–D017). See `docs/adr/` for the baseline record.

## Dual role

OpenHarness is simultaneously:

1. **Workspace manager** — the active registry declares target repos:
   `.openharness/REPOS.local.md` (written by `/init`, gitignored) when present,
   otherwise the shipped, agnostic `REPOS.md` template. `openharness/repos.py`
   clones them into `sources/` (gitignored, reconstructable via `pull`). Launch agent CLIs from the
   harness root or a `sources/<repo>` — the harness tree *is* the workspace.
2. **Context package** — agent-facing assets discoverable in place:
   `.claude/commands/`, `.opencode/commands/` (legacy `command/`),
   `.claude/agents/`, `.opencode/agents/`, `skills/` (Python, run via
   `python -m openharness run <skill>`), `SELF/` (specs/principles),
   `.openharness/ENV.md`, local RAG index.

## Components

| Piece | File(s) | Role |
|---|---|---|
| CLI | `openharness/__main__.py` | `oh` verbs: serve, pull, run, catalog |
| Repo mgmt | `repos.py`, `registry.py` | active registry parse, clone/pull, skill catalog |
| Specs | `frontmatter.py`, `env.py`, `skill.py` | md+frontmatter parsing, ENV.md, skill runner |
| Observer | `serve.py`, `serve_api.py` | HTTP API + SSE streams (:7337): agent sessions, ship-loop state |
| Agent adapters | `observers/{base,claude,opencode}.py` | tail agent session JSONL — read-only, thin |
| Metrics | `metrics.py` + `/api/metrics*` | per-session cost/latency rollups over the same JSONL |
| RAG | `knowledge/rag.py` | ChromaDB + sentence-transformers, local |
| Web UI | `web/` (Vite+TS) | observer dashboard — calls same verbs, no logic (D005) |
| Skills | `skills/{harness,security,legacy_migration,product}/` | executable Python skills (`ship_loop`, `review_delivery`, `challenge_decision`, ...) |
| Delivery loop | `skills/product/ship_loop.py` + `.opencode/commands/ship-loop.md` + `.opencode/agents/*` | deterministic oracle, per-feature `specs/<feature>/LOOP.md` + `LOOP.state.json` state, `GATES.md` preconditions, subagent roles |
| Independent audit | `skills/product/review_delivery.py` + `.opencode/commands/review-delivery.md` + `delivery-auditor` | deterministic evidence brief + independent verdict; `SPEC-AUDIT.md` before planning, `DELIVERY-AUDIT.md` before `finish` (D013) |
| Evidence bundles | `evidence.py` + `skills/harness/evidence.py` | per-run manifest, hashes and generated walkthrough page in `.openharness/evidence/` (local scratch) or `evidence/` with `--tracked` (committable); `verify` binds the bundle to a commit, rejects tracked scratch bundles and secrets (ADR 0007) |
| Self specs | `SELF/` | PRINCIPLES.md, decision log, domain blocks |

## Data flow

- **Agent work:** agent CLI runs inside the harness tree → reads markdown
  commands/skills/SELF → executes Python skills via the CLI → writes code
  in `sources/<repo>` → session JSONL lands on disk.
- **Observation:** `oh serve` tails those JSONL logs via `observers/` →
  `serve_api` streams to the web UI; `/api/loops*` likewise streams the
  ship-loop oracle's `LOOP.state.json` projections read-only. Read-only;
  the harness never injects
  into agent sessions.
- **Product delivery:** `/ship-loop` → `ship_loop --action=next` reads
  `specs/<feature>/{SPEC.md,EXAMPLES.feature,BACKLOG.md,GATES.md,WAVES.md,LOOP.md,LOOP.state.json}`
  → checks blocking gates for the current phase → returns one directive (or a
  `GATE:`/`NEXT: fix wave-plan warnings` directive) → the agent delegates it
  to a subagent role → outcome recorded back into `LOOP.md`/`LOOP.state.json`.
  The audit mode (`review`) is persisted in that state. No harness-side
  scheduling (D001, D009).
- **Independent audit:** `/review-delivery` → `review_delivery` builds a
  deterministic brief (artifact presence, AC → scenario → wave → backlog →
  LOOP traceability, claimed path/script/endpoint/ADR existence, evidence
  integrity, scope drift) → `delivery-auditor` re-verifies the cited code and
  tests and fills `PASS`/`CONCERNS`/`BLOCK` → `SPEC-AUDIT.md` or
  `DELIVERY-AUDIT.md`. `ship_loop --review=required` refuses to plan or finish
  without a filled verdict (D013); the audit never marks a gate.
- **Decision review:** `/challenge-decision` → `challenge_decision` builds a
  deterministic brief (record completeness, heuristic code signals, design
  moves, lens questions) → `decision-challenger` supplies alternatives,
  tradeoffs, scores, and a verdict → `DECISION-REVIEW.md`. Advisory only
  (D011); it never blocks the loop.

## State

All state is files on disk: the active registry (`REPOS.md` or local override), `sources/` clones,
`.openharness/ENV.md`, `.openharness/chroma` RAG index, agent session logs.
No database, no cloud.

## Key decisions

See `SELF/PRINCIPLES.md` — D001 (no orchestration), D002 (md specs / py
execution), D003/D012/D016 (LOC budgets: core ≤330, platform ≤1100, CI-enforced), D005 (UI is observer), D006 (log-tail
observation only), D007 (REPOS.md + sources/), D008 (no copying into target
repos), D009 (agent-executed delivery loops, state in `specs/`), D010
(declared gates guard phase transitions), D011 (optional advisory decision
review), D013 (independent spec/delivery audit, enforced by `/ship-loop`).
