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
| `/ship-loop` | Autonomous loop over the same pipeline: the oracle picks the next action, subagents execute it, every wave is one PR. Stacks on open predecessor PRs; `done` means acceptance-validated, not necessarily merged or deployed. |
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

See `SELF/blocks/delivery-loop.md` for the state model, gate contract, and
action contract, and `SELF/blocks/decision-review.md` for the review lenses
and guardrails.
