# ADR 0008 — TDD evidence in wave bundles

Status: accepted · 2026-11-21 · relates to D009 (delivery loop),
D013 (delivery audit), ADR 0007 (evidence bundles)

## Context

The wave-implementer contract already says "write failing tests first,"
but nothing verifies it happened. Agents write tests after the
implementation and describe them as TDD; `ship_validate` proves a test
*cites* a scenario, not that it was written before the code it tests.
The result is the failure mode this harness exists to prevent: plausible
artifacts that look compliant while the underlying discipline is absent.

TDD's value is the *order*: red (the test fails for the right reason)
before green (the smallest change that passes) before refactor (cleanup
that keeps the suite green). Order is exactly the kind of claim an
evidence bundle can prove, because `record_step` already runs real
commands and timestamps them.

## Decision

A bundle step may carry `tdd: red|green|refactor`. `ship_loop
--action=complete --wave=N` and `--action=finish` reject a wave bundle
that does not contain `evidence.tdd_proof(manifest)["ok"]`:

- one `red` step: status `fail` **and** `expected_failure` set — the
  recorded run is the new scenario tests failing before implementation;
- one `green` step: status `pass` — the tests pass after the minimal
  implementation;
- one `refactor` step: status `pass` — the suite re-run after the
  KISS/DRY/SOLID review. Required even when no code changed: the step
  re-proves green and its title says what was reviewed.
- `started_at` must order red ≤ green ≤ refactor.

The refactor phase is a required recorded step, not a reviewer
impression: "nothing to refactor" is itself recorded as a green re-run
with that claim in the title.

`--force` bypasses like every other loop precondition. `ship_validate`
reports per-wave TDD status in `VALIDATION.md`; `review_delivery` emits
`tdd-missing` concerns so legacy waves are visible without retro-BLOCKing
audits.

## What this proves — and what it does not

The step timestamps prove the *runs* happened in order. They do not prove
the red log shows the scenario failing for the right reason (an import
error is also a failure), nor that no implementation existed beforehand.
That semantic check belongs to `wave-reviewer`, whose contract now
requires reading the red log and confirming the named scenario test
fails on its assertion. Commit-order archaeology (test commit before
implementation commit) was rejected: it is brittle across languages,
branch shapes, and amend/squash workflows, and the marginal assurance
does not justify it.

## Consequences

- Every new wave costs three recorded command runs — the same commands
  the agent already runs; the only addition is the `--tdd=` flag.
- Bundles captured before this ADR lack `tdd` steps: `complete` rejects
  them, `--force` or re-recording is the migration path. Done loops and
  legacy features are untouched — the check runs at completion time.
- Non-code waves use their smoke/check command for all three phases.
- The manifest field is additive and optional in the schema; `/1` and
  `/2` bundles still load, they simply fail `tdd_proof`.
