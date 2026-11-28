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
| Repo ops | `oh pull` (clone/pull into `sources/`); `oh status` (branch, ahead/behind, dirty); `oh prune [--remote]` (delete merged branches) |
| Web UI build | `cd openharness/web && npm ci && npm run build` |

Requires: Python ≥3.13. `sources/` is gitignored and reconstructable via
`pull`; auth uses the user's existing git credentials only.

## Architecture

- `openharness/` — runtime package:
  - `__main__.py` — CLI entry (`oh` commands).
  - `repos.py` — active-registry parsing (local override or shipped template), `sources/` clone/pull management.
  - `registry.py`, `skill.py`, `frontmatter.py`, `env.py` — skill catalog,
    YAML-frontmatter spec parsing (~15 LOC, no PyYAML), ENV.md handling.
  - `evidence.py` — evidence bundles: per-run manifest, hashes, generated
    walkthrough page, and the commit/secret checks behind `ship_loop`
    (ADR 0007).
  - `verify.py` — loop ground truth from git/GitHub for `--action=reconcile`.
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
- `skills/` — executable Python skills grouped by area (`harness/` e.g.
  `harness_evidence`, `init_profile`,
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
  log D001–D020, `blocks/`, `harness/`, `legacy_migration/`, `security/`).
- `REPOS.md` — shipped, agnostic registry template. `/init` writes the concrete
  repo list to `.openharness/REPOS.local.md` (gitignored by default); that file
  is the active registry when present, otherwise the template is used (D007).
- `tests/` — unittest-style pytest files per module.

### Dual-role model

```
harness root = workspace root
  active registry ──► sources/<repo>/   (clones, gitignored)
  .openharness/REPOS.local.md (local) or REPOS.md (agnostic template)
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
- **Complexity budgets (D003, split by D012, ceiling revised by D016):** core
  runtime ≤ 330 LOC; platform (repos/metrics/observers/serve) ≤ 1100 LOC.
  Enforced in CI by `tests/test_budgets.py`; also visible via
  `GET /api/evolution` stats. Respects KISS — don't grow casually.
- **D008:** harness files are never copied into target repos.
- **D009:** delivery loops are agent-executed, not harness-scheduled. The
  oracle (`skills/product/ship_loop.py`) owns `specs/<feature>/LOOP.md`; the
  agent owns execution. Default merge policy is `review` (PRs stay open).
  `done` means acceptance-validated, not necessarily merged or deployed.
  Dependent waves stack on open predecessor PRs and must be retargeted and
  retested after the parent merges. Specs record a value contract (D017) and
  an outcome hypothesis; post-release learning is optional and is not a
  finish gate.
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
  re-verifies code and tests and fills `PASS`/`CONCERNS`/`BLOCK`. Standalone
  `/review-delivery` is advisory; `/ship-loop` enforces it with
  `--review=required` (the oracle default) and records the mode in loop
  state. It never marks a gate, merges, or edits product code.
- **D015:** waves run TDD — tests are written from scenarios first, and the
  evidence bundle must record an ordered `tdd: red` (expected failure) →
  `green` → `refactor` step sequence or `complete`/`finish` rejects it
  (ADR 0008). Refactor is a required green re-run, not an impression.
- **D016:** the core LOC ceiling is 330 (up from 300) to accommodate the
  permanent interpreter guard, `SkillError`, and evidence `--` passthrough.
  Delete code before growing it again; a further raise needs a new decision.
- **D017:** outcomes over output. Every spec carries a one-page `## Value
  contract` (problem, users, baseline/current cost, numeric target indicator,
  economic hypothesis, owner/date). `spec_scaffold` emits a blocking `Before:
  plan` gate `G0`; `ship_loop` refuses an unfilled contract. The challenge
  lens and audit finding are advisory; measured outcomes stay post-release
  learning (D009). No scoring engine, ROI calculator, or new runtime module
  (ADR 0009).
- **D018:** good software is sustainable outcomes, not output. Judge work on
  five dimensions — business/user value, economic viability, UX/adoption,
  technical/operational quality, and adaptability/longevity — across product,
  system and business quality. Reports lead with outcome evidence; features,
  APIs and coverage are supporting output. The frame is advisory in
  `product-framer`, `challenge_decision` and `delivery-auditor`; no score,
  dashboard, gate or runtime module (ADR 0010).
- **D019:** the domain model and the experience are spec artifacts.
  `spec_scaffold` emits `DOMAIN.md` (tier, ubiquitous language, bounded
  contexts, aggregates/invariants, integration style, external
  translations) and a `## Experience` section in SPEC.md (journey, edge
  states, UX bar, accessibility). Blocking gates `G2`/`G3` (`Before:
  plan`) refuse placeholders and bare `N/A`; `N/A — <reason>` is the
  explicit escape. Depth scales with the declared tier; presence does not
  (ADR 0011).
- **D020:** scenario maturity is a spec artifact. `EXAMPLES.feature` carries
  `@w<N>` wave tags plus `@m-failure`, `@m-ownership`, `@m-data`, `@m-ux` and
  `@m-outcome` scenario tags, or `# Maturity N/A: @m-<axis> — <reason>` for
  genuinely inapplicable axes. Added value comes in baby steps: one new axis
  per `@w<N>` wave in a dedicated scenario, with the happy path in its own
  scenario; several scenarios for the SAME axis may share a wave, but one
  big-bang wave carrying multiple axes is rejected. DOMAIN.md tier sets the
  exercised-axis floor; `spec_scaffold` emits blocking `G4 — Scenario
  maturity floor` (`Before: plan`), `ship_loop` rejects/stales an unfilled
  floor, `review_delivery` emits advisory `maturity-*` findings, `wave_plan`
  warns on crowded waves without changing wave order, and `ship_validate`
  reports the first wave per covered axis. Tags prove staged breadth only;
  reviewers judge whether the scenario is real maturity and product value,
  not decorative complexity (ADR 0012).

## Landmines

- Tests run with `--no-deps` in CI deliberately — the suite must stay
  stdlib-only; don't add imports that require chromadb etc. to tested
  modules without guarding them.
- `sources/` is gitignored — never commit clones. Keep environment-specific
  repos in `.openharness/REPOS.local.md`; leave the tracked `REPOS.md` agnostic.
- `oh serve` observes session JSONL files the agent CLIs already write —
  don't add instrumentation hooks into agents.
- Decision log D001–D020 in `SELF/PRINCIPLES.md` is normative — read it
  before structural changes.
- `SELF/EVOLUTION.md` (`oh self evolution`) is the binding contract for
  changing the harness itself; `SELF/MANIFEST.md`'s "Rules" section points
  to it.
- The web UI must call the same verbs as the CLI (D005) — no business
  logic in TSX.
- Never hand-edit `specs/<feature>/LOOP.md` or `LOOP.state.json`;
  `ship_loop` is their only writer (JSON is the machine projection,
  markdown the human render — both regenerated together).
  The loop is driven by the agent, not by a daemon or cron (D001/D009).
- `ship_loop --action=complete`/`finish` refuse to record without a
  rendered `harness_evidence` bundle under `.openharness/evidence/`
  (gitignored local scratch) or the committable `evidence/` root
  (`--tracked`) that proves the TDD cycle — ordered
  `--tdd=red --expected-failure` → `--tdd=green` → `--tdd=refactor`
  steps. `complete --bundle=<run-id>` binds the wave row to one verified
  bundle (`evidence:<run-id>` in LOOP.md/state); gate `met` accepts the
  same token as `--evidence`. UI media is walkthrough-only — proof
  bundles never require screenshots; the capture policy lives in
  `docs/plans/evidence.md`. The harness never drives browsers itself.
  Bundles declare `kind`: `proof`
  (default, gate evidence) or `walkthrough` (local-only companion
  material — `--kind=walkthrough`, never `--tracked`). UI walkthroughs
  are produced by `--action=fixture` (generates a Playwright fixture
  per repo) emitting `steps-*.json` fragments folded in with
  `--action=attach --fragment`.
- Never mark a gate `met` without evidence or `waived` without a human's name
  and reason. Fix a wrong gate in `GATES.md`; do not route around it.
- `/challenge-decision` verdicts stay advisory: never make a verdict a gate
  or merge blocker. The review *artifact* is different — `spec_scaffold`
  emits a blocking `Before: plan` gate requiring `DECISION-REVIEW.md`, so
  the review must happen even though its verdict does not block. Never let
  the reviewer edit product code.
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
  D001–D020 decision log.
- Harness changes also follow `SELF/EVOLUTION.md`: block-spec sync, LOC
  budgets, tests, and the PR shape it defines.
- For product work, prefer `/ship-loop` (autonomous) or `/ship-product`
  (phased); both keep specs and loop state in the target repo under
  `specs/` and ship one wave per PR.
- Update AGENTS.md / docs/ARCHITECTURE.md when you change commands, the
  skill contract, or module layout.
