# ADR 0009 — Outcomes over output: the value contract

Status: accepted · 2026-11-21 · relates to D009 (delivery loop),
D010 (gates), D011 (advisory design review), D013 (delivery audit), D017

## Context

AI-assisted coding lowers the cost of producing code, not the cost of
producing the wrong code. The harness already enforces trustworthy output —
scenario-to-test traceability, independent audits, evidence bundles, TDD
order — but an artifact can satisfy all of those and still have no reason to
exist. Delivery reports still tempt agents to describe success in outputs:
features, APIs, coverage, waves.

The harness cannot measure product outcomes: it has no production telemetry,
and D005 keeps the UI an observer. What it can do is require that the *claim*
be stated before implementation commits resources, and keep post-release
learning separate from acceptance validation (D009).

## Decision

`SPEC.md` gains a parseable `## Value contract` with six fields: problem,
users, baseline/current cost, target outcome indicator (numeric target and
review window), economic hypothesis (benefit against build, operate, adopt,
migrate and support cost), and owner/date. The target must be measurable; a
placeholder or a target without a number is not filled.

`spec_scaffold` emits that section plus a blocking `G0 — Value contract
filled` gate (`Before: plan`, `Check: file:specs/<feature>/SPEC.md`).
`ship_loop` checks the section when the gate is marked met, and re-checks it
on every phase decision — an artifact reverted to the template makes the gate
`stale`. Gate and waiver mechanics are unchanged (D010): a named human may
waive it, and the agent may not.

`review_delivery` reports a missing or unmeasurable contract as a `CONCERNS`
finding with code `value-contract-missing`, never a blocker. The
`challenge_decision` brief adds a `Value & economics` lens alongside the
existing seven; its verdict remains advisory (D011). `ship_validate` adds
optional baseline/target/adoption/TCO bullets inside the already-preserved
`## Outcome follow-up` section; none of them gate `finish`.

## Alternatives considered

- **ROI calculator / scoring engine.** Rejected: invented numbers would be
  treated as facts, and a score would replace judgment rather than inform it.
- **Value gate that blocks finish on measured outcomes.** Rejected: conflicts
  with D009. Many features only produce evidence after release; `done` means
  acceptance-validated, not proven in production.
- **New `VALUE-CONTRACT.md` artifact.** Rejected: one more file to keep in
  sync with the spec. The contract belongs where the problem and ACs already
  live, and reuses the existing `file:` gate mechanism.
- **Advisory only, no gate.** Rejected: agents reliably skip optional
  questions under delivery pressure; the chosen scope requires the contract
  before planning.

## Consequences

- Every new spec carries six short lines before planning; existing features
  are untouched because the check runs on scaffolded gates and on audits, not
  retroactively on done loops.
- The numeric-target rule is a heuristic. A well-argued qualitative outcome
  must still be expressed with a number and window, or waived by a human —
  that is the point of the contract.
- The audit finding is a concern, so a spec can pass review with an accepted
  concern while the gate still blocks planning. This is intentional: the
  auditor reports, the gate enforces (D013/D010).
- No new runtime module, no LOC-budget change, no business-metrics dashboard.
  The observer still reports outputs (sessions, cost, LOC) as outputs.
