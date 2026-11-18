# ADR 0006 — Independent spec and delivery audit

Status: accepted · 2026-11-16 · decision D013 · amended 2026-11-18 (the
review default is `required`, as D013 says)

## Context

The delivery loop (ADR 0003) records what was built, and gates (ADR 0004)
stop a phase when a declared precondition is missing. Neither proves that
the artifacts are *true*. In real runs the loop produced:

- acceptance criteria that named a scenario which did not exist;
- specs that cited paths, scripts, endpoints, and ADRs absent from the repo;
- validation rows that pointed at a test file without the test asserting the
  behavior;
- wave and gate evidence that was a placeholder (`ok`, `done`);
- changed files outside the spec's declared scope.

A per-wave reviewer and a delivery verifier exist, but both read the same
artifacts the loop produced. A loop can therefore pass every gate and still
declare a feature done that was never delivered. The failure is
hallucination, not a failing test, so a test-only gate cannot catch it.

## Decision

Add an **independent audit** with two checkpoints:

1. **Deterministic brief** — `skills/product/review_delivery.py`
   (`review_delivery`). It reads `specs/<feature>/` and reports, by severity:
   - missing artifacts for the phase (`spec` or `delivery`) and unresolved
     `TBD`/`TODO`/`FIXME` markers in the contract;
   - traceability integrity: AC → scenario → wave → backlog → LOOP, including
     dangling wave references and untagged scenarios;
   - claim existence: every backticked path, script, endpoint, and ADR named
     in the artifacts resolves in the repository (or is explicitly planned);
   - evidence integrity: placeholder wave/gate evidence, missing `file:` gate
     artifacts, weak or empty validation rows, unresolved validation gaps;
   - scope drift and unfinished markers in changed product code.
   It emits findings plus a verdict block. It does **not** judge semantics
   and never writes a verdict.
2. **Independent judgment** — `/review-delivery` and the `delivery-auditor`
   subagent. It re-verifies every finding against the cited file and line,
   opens the tests and confirms they assert the scenario's outcome, runs the
   real test command when the toolchain exists, walks the demo path, checks
   changed public contracts against the spec and README, records dismissed
   findings with a reason, and fills one verdict:
   - `BLOCK` — any confirmed blocker, hallucinated claim, or unproven AC;
   - `CONCERNS` — every remaining item is non-blocking and accepted;
   - `PASS` — all three lists are empty and evidence was personally verified.
3. **Artifacts** — `specs/<feature>/SPEC-AUDIT.md` before `plan`/wave 1 and
   `specs/<feature>/DELIVERY-AUDIT.md` after `VALIDATION.md`, before `finish`.
   The deterministic brief is kept; the auditor appends the verdict.

Enforcement is a loop setting, not a property of the reviewer:
`ship_loop --review=required` is the default (D013, used by `/ship-loop`) —
it refuses to plan without a filled spec audit, refuses to start wave 1 until
that audit passes, and refuses to finish without a filled delivery audit.
`--review=advisory` remains as an explicit opt-out and never enforces the
audit. A `BLOCK` verdict stops the loop. The template line
`AUDIT: PASS | CONCERNS | BLOCK` is not a filled verdict.

The audit is advisory in principle (like D011): it never marks a gate, never
merges, and never edits product code. The auditor writes only the audit file.

## Consequences

- Hallucinated specs and wrong-feature delivery become visible before a
  feature is called done, at the two points where fixing them is cheapest.
- The deterministic half keeps the review grounded and repeatable; the
  independent half keeps it honest, because it must read code and tests
  rather than restate the loop's claims.
- Backwards compatible: `--review=advisory` is still there as an explicit
  opt-out for a loop that wants no audit; without it the audit applies, which
  is what D013 requires.
- Cost: one skill, one command, one subagent role, and one or two review
  documents per feature. The risk is ceremony; the command therefore says
  when the audit is required and what each verdict means.
- The audit does not replace tests, CI, or human review. It checks that the
  evidence is real, not that the product decision is right.
