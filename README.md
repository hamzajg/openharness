# OpenHarness v0.1.0

OpenHarness plays **two roles at once** in a single git repository:

## Dual Role

**Role A — Workspace Manager (the mothership).**
The harness folder is your working root for an entire multi-repo product/ecosystem. Target repositories are registered in `REPOS.md` and cloned into `sources/` (gitignored). Launch agent CLIs (claude, opencode) from the harness root or from `sources/<repo>` — the harness tree **is** the workspace. `oh serve` runs here, monitoring all agent sessions across all managed repos.

**Role B — Context Package (loaded into the agent, in place).**
Because agent sessions run inside the harness tree, the harness's agent-facing assets are natively discoverable:
- `.claude/commands/` and `.opencode/commands/` → slash commands (legacy `.opencode/command/` still discovered)
- `.claude/agents/` and `.opencode/agents/` → focused subagent roles for the delivery loop
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

## Product delivery

Two commands take a managed repo from "code exists" to an acceptance-validated
feature:

| Command | Shape |
|---|---|
| `/ship-product` | Phased, human-in-the-loop: discover → frame → spec/outcome hypothesis → examples → waves → implement → validate. One feature at a time. |
| `/ship-loop` | Autonomous loop over the same pipeline: the oracle picks the next action, subagents execute it, every wave is one PR. Stacks on open predecessor PRs; `done` means acceptance-validated, not necessarily merged or deployed. Runs with `--review=required`: a spec audit gates planning and a delivery audit gates `finish`. |
| `/review-delivery` | Independent audit of one feature's spec or delivery: a deterministic brief checks claims against the repo, then `delivery-auditor` re-verifies the code and tests and returns `PASS`/`CONCERNS`/`BLOCK`. |
| `/challenge-decision` | Optional, advisory design review: steelman a decision, generate alternatives, weigh tradeoffs, apply DDD/architecture/testability/craftsmanship lenses. Never blocks. |

```
/ship-loop --repo=sources/portal-api --merge=review --max=25
```

The loop is **agent-driven** (D001/D009): `skills/product/ship_loop.py` is a
deterministic oracle that owns state in `specs/<feature>/LOOP.md`; the agent
calls `--action=next`, delegates to `product-framer` / `wave-implementer` /
`wave-reviewer` / `delivery-verifier`, and records outcomes. The harness never
launches or schedules agents. `--merge=review` (default) leaves PRs open for a
human; `--merge=auto` is opt-in and requires verified branch protection and
CI/security checks. Dependent waves stack on open predecessor PRs and are
retargeted/retested after the parent merges. Loop state and specs are product
artifacts committed with the feature's PRs.

**Gates.** Complex domains need preconditions before a phase can start — a
signed-off business rule, a data contract, sandbox credentials, seed data, a
security/legal review. Declare them in `specs/<feature>/GATES.md`
(`Before: spec|plan|wave:<n>|validate|finish`, `Resolver: human|agent`,
`Check: manual|file:<path>|command:<cmd>`); the oracle refuses to advance
past a phase while a blocking gate is `pending`/`failed`, and only a named
human can waive one. Status and evidence live in `LOOP.md`.

**Product learning.** Feature specs record an outcome hypothesis, its
evidence or assumption, an observable signal, and a follow-up owner/date
when known. Post-release results can be recorded in `VALIDATION.md`; this
follow-up does not block acceptance validation. Close-out distinguishes
validated behavior from merged/deployed state and reports flow timing only
when real timestamps are available. The protocol does not itself sandbox
agents; target-repo permissions and agent-host isolation remain the
environment's responsibility.

**Decision review.** Complex domains also need their *design* challenged —
where the boundary sits, what owns the invariant, whether the domain depends on
a framework, how it will be tested. `/challenge-decision` builds a
deterministic brief (`challenge_decision`: record completeness, heuristic code
signals, design moves, lens questions) and delegates the judgment to the
`decision-challenger` subagent: steelman, alternatives, tradeoff matrix,
scores with evidence, verdict `ACCEPT`/`REVISE`/`REVISIT`/`SPLIT`. It is
advisory (D011) — it never blocks a gate, wave, or merge.

**Independent audit.** Gates check whether a precondition exists; they do not
prove the spec is grounded in the repo or that the delivery matches the spec.
`/review-delivery` runs `review_delivery` to build an evidence brief (artifact
presence, AC → scenario → wave → backlog → LOOP traceability, existence of
every claimed path/script/endpoint/ADR, placeholder evidence, scope drift,
unfinished markers), then hands it to the independent `delivery-auditor`
subagent. The auditor opens the cited code and tests, re-verifies each finding,
and fills one verdict: `BLOCK` on any confirmed blocker, hallucinated claim, or
unproven acceptance criterion; `CONCERNS` only when every remaining item is
accepted; `PASS` only when all lists are empty. `/ship-loop` enforces two
checkpoints with `ship_loop --review=required`: `SPEC-AUDIT.md` before
planning, `DELIVERY-AUDIT.md` before `finish`. The audit never marks a gate,
merges, or edits product code (D013).

See `SELF/blocks/delivery-loop.md` for the state model, gate contract, and
action contract, `SELF/blocks/delivery-audit.md` for the audit checkpoints and
verdict rules, and `SELF/blocks/decision-review.md` for the review lenses and
guardrails.

## Evidence bundles

A wave is not proven by a sentence. `harness_evidence` (ADR 0007) builds a
local, offline-reviewable bundle per run. By default bundles are local scratch
(gitignored); pass `--tracked` on `new` when a run's proof should be committed
and pushed — those live under `evidence/` instead:

```
.openharness/evidence/<feature>/<run-id>/   # default: scratch, never committed
evidence/<feature>/<run-id>/                # --tracked: committable, pushed on purpose
├── evidence.json   manifest: commit, steps, artifacts, hashes, redactions
├── index.html      generated walkthrough page
├── SUMMARY.md      short, pasteable into a PR or LOOP row
├── raw/            screenshots, recordings, traces
└── logs/           one log per executed command
``` The harness does
not drive browsers or devices: Playwright, `adb`, `xcrun`, or a human produce
files, and `attach` records them with a hash.

```bash
# create a bundle for the current commit (scratch by default;
# add --tracked=true to place it under evidence/ for committing)
python -m openharness run harness_evidence --action=new \
  --repo=. --feature=photo-notes --wave=2 --head=$(git rev-parse HEAD)

# run a command; real exit code, duration and log are recorded
python -m openharness run harness_evidence --action=step \
  --repo=. --feature=photo-notes --title="API tests" -- pytest -q

# attach a screenshot (copied under raw/<step>/, MIME + hash recorded)
python -m openharness run harness_evidence --action=attach \
  --repo=. --feature=photo-notes --file=/tmp/note-created.png \
  --caption="A note is created"

# generate the page, then verify hashes, commit and secrets
python -m openharness run harness_evidence --action=render --repo=. --feature=photo-notes
python -m openharness run harness_evidence --action=verify --repo=. --feature=photo-notes
```

`step` and `attach` redact auth headers, cookies, passwords, API keys, tokens,
private keys, JWTs and JSON-shaped secrets before hashing; `verify` fails if a
token still appears in a log, an artifact changed, or the manifest commit is
not the checked-out one. The full design — capture policy, walkthrough page,
loop wiring, sharing — is in `docs/plans/evidence-v2.md`.
