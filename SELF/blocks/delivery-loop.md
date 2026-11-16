---
name: delivery-loop
type: block
location: skills/product/ship_loop.py, skills/product/spec_scaffold.py, skills/product/ship_validate.py, .opencode/commands/ship-loop.md, .claude/commands/ship-loop.md, .opencode/agents/, .claude/agents/
interfaces: [ship_loop.invoke, ship_loop --action=next|status|start|complete|gate|block|resume|reset|finish]
---
# Block: delivery-loop

## Purpose
Turns the `/ship-product` phased playbook into a **repeatable, resumable
loop** that an agent can drive autonomously across many sessions. The Python
skill is the deterministic oracle: it reads the spec artifacts plus its own
state file and answers "what is the next action?" The Markdown command and
subagents are the execution protocol. The harness never launches or schedules
anything (D001, D009).

## State model
- `specs/<feature>/WAVES.md` — the plan. Written by `wave_plan`, never by the loop.
- `specs/<feature>/SPEC.md` — includes the expected user outcome, evidence or
  assumption, an observable signal, and a follow-up owner/date when known.
- `specs/<feature>/GATES.md` — preconditions for phase transitions (definitions
  only). Written by the agent (product-framer); `ship_loop` parses it.
- `specs/<feature>/LOOP.md` — the execution record. **Only `ship_loop` writes it.**
  ```
  Status: running | blocked | done
  Iterations: <n>
  | Wave | Status | Branch | PR | Evidence | Updated |
  | 1 | done | feat/x-w1 | #12 | 4/4 tests, CI green | ... |
  ## Gates
  | Gate | Status | Evidence | Updated |
  | G1 | met | file:docs/data-contract.md | ... |
  ## Events
  - <timestamp> start wave 1 on feat/x-w1
  - <timestamp> complete wave 1 (#12): 4/4 tests, CI green
  - <timestamp> gate G1 met: file:docs/data-contract.md
  ```
- `specs/<feature>/VALIDATION.md` — written by `ship_validate`; required by
  `finish`. It holds acceptance evidence and an optional post-release outcome
  follow-up, which is not a finish gate.
- `specs/PRODUCT.md` — cross-feature map, refreshed by `product_map`.

## Gates
A gate is a precondition that must be satisfied before a phase can start —
the thing a complex domain needs *before* code: a signed-off rule, a data
contract, sandbox access, seed data, a security/legal review.

`GATES.md` declares each gate as `## G<n> — <title>` with fields:

| Field | Values |
|---|---|
| `Before` | `spec` · `plan` · `wave:<n>` · `validate` · `finish` |
| `Type` | `decision` · `artifact` · `external` · `technical` · `quality` · `data` |
| `Owner` | role responsible for satisfying it |
| `Resolver` | `human` (a person must decide/provide) · `agent` (agent can satisfy) |
| `Blocking` | `yes` · `no` (advisory: reported, never blocks) |
| `Check` | `manual` · `file:<repo-relative-path>` · `command:<exact command>` |
| `Why` | which AC / business rule depends on it |

Status lives in `LOOP.md`: `pending` · `met` · `waived` · `failed`.
- `met` requires `--evidence`; `file:` checks are verified by the oracle
  (the file must exist), `command:` checks are run by the agent and the
  output recorded — the oracle never executes repo-provided commands.
- `waived` requires `--waived-by` and `--note`; only a human can waive.
- Overdue gates keep blocking: a pending `Before: spec` gate still blocks
  wave 1 if artifacts were filled out of order.
- An invalid `Before` value blocks every phase until fixed.
- Advisory gates (`Blocking: no`) are surfaced in `status` but never block.

## Actions
| Action | Effect |
|---|---|
| `next` | Increment the iteration counter and print the next directive, `DONE`, `BLOCKED`, or `STOP`. |
| `status` | Same decision without incrementing (orientation). |
| `start --wave=N` | Mark wave N in progress, record branch, reset `blocked`. |
| `complete --wave=N --note=... [--pr=#n]` | Mark wave N done with evidence; prints the next directive. |
| `gate --gate=G1 --status=met --evidence=...` | Record a precondition as met (evidence required; `file:` checks verified). |
| `gate --gate=G1 --status=waived --waived-by=... --note=...` | Record a human-approved waiver. |
| `gate --gate=G1 --status=failed --note=...` | Record a failed check; the loop stays blocked honestly. |
| `block --note=...` | Stop the loop; the note is what a human must decide. |
| `resume` | Clear `blocked`. |
| `reset [--wave=N] [--force]` | Reset one wave, or the whole loop (needs `--force`). |
| `finish` | Mark a validated feature done (requires `VALIDATION.md`, all waves done). |

Phases map to ship-product: no specs → frame; missing artifacts → spec;
no `WAVES.md` → plan; pending wave → wave N; all waves done → validate;
`VALIDATION.md` present → acceptance validated. `done` does not mean PRs are
merged or the feature deployed. Each phase is gated by any blocking
`GATES.md` entry due at or before it; the oracle prints a `GATE:` directive
instead of the next action until the gate is met or waived.

## Outcomes and delivery flow

- Product framing distinguishes repository findings from customer evidence.
  An unverified user need remains an explicit assumption, not a research claim.
- `SPEC.md` records an outcome hypothesis and a signal without inventing
  targets or baselines. After release, `VALIDATION.md` may record the observed
  result, source, owner/date, and learning. A pending follow-up is not an
  acceptance gap or a finish blocker.
- Close-out reports acceptance, PR merge, and deployment state separately.
  Phase and PR review times may be reported only when supported by actual
  timestamps; they are for finding friction, not ranking teams.

## Branching, execution, and merge policy

- In review mode, a wave whose predecessor PR remains open branches from that
  PR's head and targets its PR at the predecessor branch. The orchestrator
  supplies both base branches to the implementer and records the stack and
  merge order. Once a parent merges, the orchestrator retargets or rebases
  open descendants onto the default branch and CI is rerun before their merge.
- The default `review` policy remains human-reviewed. `auto` requires the
  agent to verify branch protection and required CI/security checks; if it
  cannot, the work is handed back in review mode.
- The Markdown protocol does not provide process isolation. Agents follow
  host permission prompts and target-repo least-privilege guidance; they do
  not broaden filesystem, network, or credential access to finish a wave.

## Invariants
- The agent is the loop. No daemon, cron, queue, or scheduler in the harness.
- One `next` call per iteration; the oracle re-derives state from disk.
- The iteration budget (default 25) is a hard stop, not a suggestion.
- Out-of-order `start`/`complete` is rejected unless `--force`.
- `complete` requires a note; the protocol requires that it record test,
  CI, and review evidence, but the oracle only checks that the note is
  nonempty. `block` requires a decision to hand back.
- A blocking gate stops its phase; the agent resolves `agent` gates inline and
  blocks for `human` gates — it never self-approves a human gate or a waiver.
- Overdue gates keep blocking; advisory gates never do.
- Events are append-only (last 200 kept).
- Default merge policy is `review`: PRs stay open for a human.

## How to Extend
1. Keep phase logic in `skills/product/ship_loop.py`; do not duplicate it in
   command files or subagents.
2. New artifact gates go in `_decide()` and get a test in
   `tests/test_ship_loop.py`; new gate semantics go in the gates section and
   get a test in `tests/test_ship_gates.py`.
3. New actions must update `_load_state`/`_save_state`, the docstring, the
   command tables, and this block.
4. New subagent roles are `.opencode/agents/<name>.md` with
   `mode: subagent` plus a `.claude/agents/<name>.md` mirror.
