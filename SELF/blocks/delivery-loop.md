---
name: delivery-loop
type: block
location: skills/product/ship_loop.py, skills/product/spec_scaffold.py, skills/product/ship_validate.py, skills/product/review_delivery.py, .opencode/commands/ship-loop.md, .opencode/commands/review-delivery.md, .claude/commands/ship-loop.md, .claude/commands/review-delivery.md, .opencode/agents/, .claude/agents/
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
  Review: required | advisory
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
  `LOOP.state.json` carries the same fields plus `review`
  (`required`/`advisory`); `ship_loop` is still the only writer of both.
- `specs/<feature>/VALIDATION.md` — written by `ship_validate`; required by
  `finish`. It holds acceptance evidence and an optional post-release
  outcome follow-up, which is not a finish gate. `finish` (and the
  `FEATURE-DONE` path of `next`) requires every traceability row to carry
  strong test evidence or a `## Manual verification` entry naming the AC
  with the command run and observed result — weak `(weak)` token matches
  and `—` placeholders do not count as proof.
- `specs/<feature>/SPEC-AUDIT.md` — written by `review_delivery` +
  `delivery-auditor`; the spec review artifact.
- `specs/<feature>/DELIVERY-AUDIT.md` — same pair; the delivery review
  artifact. Both are review records, not gates.
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
  output recorded — the oracle never executes repo-provided commands. A
  `file:` check for `DECISION-REVIEW.md` additionally requires a completed
  verdict block — a single-value `VERDICT:` plus substantive `STEELMAN:`,
  `SMALLEST NEXT STEP:` and `REVISIT TRIGGER:` entries — not the
  challenge template's `ACCEPT | REVISE | ...` alternation or `<...>`
  placeholders.
- `waived` requires `--waived-by` and `--note`; only a human can waive.
- Overdue gates keep blocking: a pending `Before: spec` gate still blocks
  wave 1 if artifacts were filled out of order.
- An invalid `Before` value blocks every phase until fixed.
- Advisory gates (`Blocking: no`) are surfaced in `status` but never block.

## Independent review
Gates check *if* a precondition exists. They do not prove that the spec is
grounded in the repo or that the delivery matches the spec. The loop has a
separate review path:

- `review_delivery` is deterministic: it checks traceability (AC → scenario →
  wave → backlog → LOOP), claim existence (paths, scripts, endpoints, ADRs),
  evidence integrity (wave/gate/validation), scope drift, and unfinished
  markers. It emits findings and a verdict block; it never judges semantics.
- `delivery-auditor` is the independent judgment half: it re-verifies every
  finding, opens the cited tests, runs the real test command when possible,
  and fills `AUDIT: PASS|CONCERNS|BLOCK`. It may write only the audit file.

Two checkpoints:

| Phase | Artifact | When |
|---|---|---|
| spec | `SPEC-AUDIT.md` | after `SPEC.md`/`EXAMPLES.feature`/`BACKLOG.md`, before `plan`/wave 1 |
| delivery | `DELIVERY-AUDIT.md` | after `VALIDATION.md`, before `finish` |

`ship_loop` defaults to `--review=required`: it refuses to plan waves and
to start wave 1 without a filled `SPEC-AUDIT.md`, and refuses to finish
without a filled `DELIVERY-AUDIT.md`. `--review=advisory` never enforces
the audit. The mode is persisted as `Review:`/`review` once a mutating
action records it, so a later call cannot silently drop enforcement; pass
`--review` again to change it. A `BLOCK` verdict stops the loop. `PASS` and
accepted `CONCERNS` continue. The template line
`AUDIT: PASS | CONCERNS | BLOCK` is not a filled verdict.

The audit is advisory in principle (like D011): it never marks a gate, never
merges, and never edits product code. Enforcement is a process choice the
command makes, not a property of the reviewer.

## Actions
| Action | Effect |
|---|---|
| `next` | Increment the iteration counter and print the next directive, `DONE`, `BLOCKED`, or `STOP`. |
| `status` | Same decision without incrementing (orientation). |
| `compliance` | Read-only corpus report: per feature, review mode, audit verdicts, proven ACs, evidence coverage, and a `done-compliant` / `done-legacy` / `done-attention` verdict. |
| `start --wave=N` | Mark wave N in progress, record branch, reset `blocked`. |
| `complete --wave=N --note=... [--pr=#n]` | Mark wave N done with evidence; prints the next directive. |
| `gate --gate=G1 --status=met --evidence=...` | Record a precondition as met (evidence required; `file:` checks verified). |
| `gate --gate=G1 --status=waived --waived-by=... --note=...` | Record a human-approved waiver. |
| `gate --gate=G1 --status=failed --note=...` | Record a failed check; the loop stays blocked honestly. |
| `block --note=...` | Stop the loop; the note is what a human must decide. |
| `resume` | Clear `blocked`. |
| `reset [--wave=N] [--force]` | Reset one wave, or the whole loop (needs `--force`). |
| `finish` | Mark a validated feature done (requires `VALIDATION.md` with proven ACs, all waves done, finish gates met, verified evidence bundles). |

All actions accept `--review=advisory|required`; the recorded mode wins on
later calls unless `--review` is passed again. Enforcement happens on
`next` (before `plan`, before wave 1, and before `finish`) and on `finish`;
other actions report the audit status in the summary.

`compliance` is the corpus-level audit: a `done` feature with
`review=advisory`, unrecorded review mode, missing/unverified audit
verdicts, unproven ACs, or missing wave bundles is reported
`done-legacy`/`done-attention` — visible as unverified rather than silently
counted as compliant. It writes nothing.

Phases map to ship-product: no specs → frame; missing artifacts → spec;
no `WAVES.md` → plan; `WAVES.md` with unresolved `## Warnings` → fix the
backlog/scenario tags and re-run `wave_plan`; pending wave → wave N; all
waves done → validate; `VALIDATION.md` present → acceptance validated.
`done` does not mean PRs are merged or the feature deployed. Each phase is
gated by any blocking `GATES.md` entry due at or before it; the oracle
prints a `GATE:` directive instead of the next action until the gate is met
or waived.

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
- `complete --wave=N` and `finish` require a bundle that covers that wave,
  loads, passes `evidence.verify` (hashes, artifacts, secrets, verdict) and
  records the checked-out commit. A rendered page alone is not evidence, and
  another wave's bundle cannot stand in. Both roots count: the gitignored
  `.openharness/evidence/` and the committable `evidence/` (`--tracked`).
- A blocking gate stops its phase; the agent resolves `agent` gates inline and
  blocks for `human` gates — it never self-approves a human gate or a waiver.
- Overdue gates keep blocking; advisory gates never do.
- Events are append-only (last 200 kept).
- Default merge policy is `review`: PRs stay open for a human.
- `--review=required` adds exactly three artifact checks: `SPEC-AUDIT.md`
  before `plan` and again before wave 1 starts, `DELIVERY-AUDIT.md` before
  `finish`. Advisory mode adds none.
- A filled audit verdict is one value (`AUDIT: PASS`); the template line with
  all three values is not a verdict. The auditor is read-only outside the
  audit file and never marks a gate.

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
5. New audit checks go in `skills/product/review_delivery.py` with tests in
   `tests/test_review_delivery.py`; keep the `delivery-auditor` contract and
   the command tables in sync with any new finding code or phase.
