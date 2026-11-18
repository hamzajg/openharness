---
name: delivery-audit
type: block
location: skills/product/review_delivery.py, .opencode/commands/review-delivery.md, .claude/commands/review-delivery.md, .opencode/agents/delivery-auditor.md, .claude/agents/delivery-auditor.md
interfaces: [review_delivery.invoke, ship_loop --review=advisory|required]
---
# Block: delivery-audit

## Purpose
Proves that a spec is grounded in the repository and that a delivery matches
the spec. It exists because gates check *whether* a precondition exists, not
whether the artifacts are true: a loop can pass every gate and still declare a
feature done that was never delivered. The audit is the independent check for
hallucinated paths, APIs, scenarios, and acceptance criteria (D013).

Two halves:

1. **Deterministic brief** — `skills/product/review_delivery.py`. Reads
   `specs/<feature>/` and reports findings by severity. It never judges
   semantics and never writes a verdict.
2. **Independent judgment** — `/review-delivery` + the `delivery-auditor`
   subagent. Re-verifies every finding against code and tests, runs the real
   test command when possible, and fills exactly one verdict.

## Checkpoints
| Phase | Artifact | When |
|---|---|---|
| spec | `specs/<feature>/SPEC-AUDIT.md` | after `SPEC.md`/`EXAMPLES.feature`/`BACKLOG.md`, before `plan`/wave 1 |
| delivery | `specs/<feature>/DELIVERY-AUDIT.md` | after `VALIDATION.md`, before `finish` |

## Inputs
- `--repo_path=<repo>` — repository root containing `specs/`.
- `--spec_dir=<dir>` — feature dir; defaults to the first feature.
- `--phase=spec|delivery|all` — which audit to build (default `delivery`).
- `--changed="<paths>"` — changed files for scope-drift checking; otherwise
  the skill reads `git diff --name-only <base>`.
- `--base=<ref>` — diff base (default: `origin/main`, `origin/master`, `main`,
  `master`, in that order).
- `--write` — persist `SPEC-AUDIT.md` / `DELIVERY-AUDIT.md`; `--force` to
  overwrite an existing file.

## What the brief contains
- **Artifacts** — required files for the phase, and unresolved
  `TBD`/`TODO`/`FIXME` markers in the contract.
- **Traceability** — AC → scenario → wave → backlog → LOOP: untraceable
  criteria, unknown waves, untagged scenarios, orphan scenarios, dangling
  backlog dependencies, missing LOOP rows.
- **Claims** — every backticked path, script, endpoint, and ADR resolves in
  the repo, or is explicitly marked as planned/future/negated. Build-gate
  criteria (`sh gradlew test`) need no Gherkin scenario.
- **Evidence** — placeholder wave/gate evidence, missing `file:` gate
  artifacts, unowned waivers, weak/empty validation rows, validation gaps.
- **Scope** — changed files outside the spec's in-scope paths, and
  `TODO`/`FIXME`/`placeholder` markers in changed product code.
- **Verdict block** — filled by the auditor, never by the skill.

## Verdicts
- `BLOCK` — any confirmed blocker, hallucinated claim, or acceptance criterion
  with no real proof.
- `CONCERNS` — every remaining item is non-blocking and explicitly accepted,
  with a reason.
- `PASS` — all three lists are empty and evidence was personally verified.

A filled verdict is a single value (`AUDIT: PASS`). The template line
`AUDIT: PASS | CONCERNS | BLOCK` is not a verdict.

## Enforcement
`ship_loop` defaults to `--review=required`: it refuses to plan without a
filled `SPEC-AUDIT.md`, refuses to start wave 1 until the spec audit
passes, and refuses to finish without a filled `DELIVERY-AUDIT.md`.
`--review=advisory` is the explicit opt-out and never enforces the audit.
A `BLOCK` verdict stops the loop; `PASS` and accepted `CONCERNS` continue.

## Invariants
- The audit is advisory in principle (like D011): it never marks a gate, never
  merges, and never edits product code. Enforcement is a loop setting.
- The auditor writes only the audit file and is independent of the
  implementer. If the same session wrote the code, say so and hand the audit
  to a fresh session.
- `VALIDATION.md`, `LOOP.md`, PR bodies, and commit messages are claims. The
  repository and the tests are the evidence.
- A passing test suite is not proof of the spec; the tests must assert the
  scenario's outcome, not merely contain its name.
- Dismissed brief findings are recorded with a reason, never dropped silently.
- Never invent evidence. If it was not read or run, it is `UNVERIFIED`.

## How to Extend
1. New deterministic checks go in `review_delivery.py` with tests in
   `tests/test_review_delivery.py`; keep them language-light and
   false-positive resistant (dogfood on real specs).
2. New finding codes must appear in the command/agent procedure and keep the
   severity rule: a claim that is false at delivery time is a blocker; a claim
   that may still be planned is a concern.
3. The agent contract lives in the command and subagent; mirror every change
   to `.claude/`.
4. Keep the two halves separate: the skill produces evidence, the auditor
   produces judgment.
