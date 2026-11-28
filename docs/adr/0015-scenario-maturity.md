# ADR 0015 — Scenario maturity as a spec contract

Status: accepted · 2026-11-28 · relates to D002 (markdown specs),
D010 (gates), D013 (delivery audit), D017 (value contract), D018
(sustainable outcomes), D019 (domain/experience contracts), D020

## Context

`EXAMPLES.feature` is the executable specification-by-example: every
acceptance criterion maps to a scenario, `wave_plan` turns `@w<N>` tags into
waves, and `wave-implementer` writes the RED test from that scenario. The
contract currently proves *traceability* but not *breadth*. A feature with
two happy-path scenarios passes the spec audit, every gate, and the
traceability matrix while saying nothing about retries, ownership, reload,
error states, or the outcome signal promised by the value contract.

Agents optimizing for a passing demo naturally stop at primitive use cases.
The result looks complete in the harness and fails immediately against real
world solutions: concurrent users, partial failures, stale state, migration,
degraded UI, and measurable outcomes. Adding more Gherkin rows without a
contract changes nothing — the row count is not the point; the covered
behavior is. The same failure appears in time: five axes delivered in a single
wave produce one large, unreviewable increment instead of small iterations with
dedicated scenarios and evidence. "Mature" must mean real behavior arriving in
digestible waves, not a big-bang spec that looks complete on paper.

## Decision

Add a scenario-maturity contract to `EXAMPLES.feature`, enforced like the
value, domain and experience contracts:

1. Five axes are tagged on real scenarios with `@m-failure`, `@m-ownership`,
   `@m-data`, `@m-ux` and `@m-outcome`. Tags coexist with `@w<N>` wave tags.
2. An axis that genuinely does not apply is justified outside a scenario:
   `# Maturity N/A: @m-<axis> — <reason>`. Bare `N/A`, `<reason>` placeholders
   and unknown `@m-*` tags are rejected.
3. The DOMAIN.md tier controls required depth, not existence: `simple` needs a
   happy path plus 2 exercised axes, `standard` needs 3 including failure and
   UX covered or justified, `domain-heavy` needs every axis covered or
   justified with at least 3 exercised, including failure and data.
4. `spec_scaffold` emits blocking gate `G4 — Scenario maturity floor`
   (`Before: plan`, `Check: file:specs/<feature>/EXAMPLES.feature`).
   `ship_loop` uses `maturity_status` from `spec_scaffold` to refuse `met` and
   to turn a previously `met` G4 `stale` when scenarios are removed.
5. `review_delivery` emits advisory findings (`maturity-axis-missing`,
   `maturity-na-unjustified`, `maturity-tag-unknown`); the independent auditor
   judges whether the scenario truly exercises the axis. `ship_validate`
   reports covered/justified axes in `VALIDATION.md` without adding a finish
   gate.
6. Added value is staged in small waves. Each new axis gets its own `@w<N>`
   wave and a dedicated scenario; the happy path gets its own scenario. Several
   scenarios for the SAME axis in a wave are depth. A mixed-axis scenario, a
   scenario that mixes `@happy-path` with an axis, an untagged axis, or a wave
   introducing two axes is rejected by G4 and warned about by `wave_plan`.
   `@m-*` never reorders waves; it only exposes a maturity planning smell.

"Innovation" is defined as closing a real maturity gap that changes the
product outcome — not introducing frameworks, layers, or scenarios that only
look sophisticated. The framer names the gap and the value in the existing
`value × feasibility × differentiation` score; no new scorecard is added
(D018).

## Alternatives considered

- **More advice in `product-framer` / `wave-implementer` only.** Rejected: D015
  already showed that agents write confirmatory tests after code when TDD is
  only advised. A blocking artifact gate with shallow deterministic proof is
  what makes the rule survive context loss.
- **A separate `MATURITY.md` artifact.** Rejected: the examples themselves are
  the artifact. A second file would drift from the scenarios it claims to
  describe and add a parse target without adding evidence.
- **A numeric maturity score or dashboard.** Rejected: scoring invites gaming
  and violates D018's "lenses, not a score" rule. Depth is expressed by tier
  floors and semantic review.
- **All five axes in one wave.** Rejected: it turns the maturity floor into a
  big-bang requirement, produces one unreviewable PR, and defeats the small,
  traced iterations the delivery loop exists to protect. Staging is checked
  deterministically; whether each scenario really exercises its axis stays
  semantic.
- **Retroactive gates on existing specs.** Rejected: gates are authored per
   feature at scaffold time. Existing loops keep their history; new loop
   iterations add the next free gate id when maturity is widened.

## Consequences

- `spec_scaffold` now emits G0–G4; agent-added gates start at G5.
- `ship_loop` learns one new `file:` validator (`EXAMPLES.feature`) using the
  DOMAIN.md tier; no new gate type or loop state field is introduced.
- New audit finding codes appear in the deterministic brief and the
  `delivery-auditor` procedure; they are advisory, like D017's value lens.
- `wave_plan` reports staged-breadth problems under `## Warnings` without
  changing wave order; `VALIDATION.md` reports the first wave per axis. Both
  help the framer split added value into small waves, and neither is a gate.
- Existing specs and running loops are not retroactively gated; they are
  widened in a later loop iteration by adding the next free gate id and
  re-running the spec audit.
- Skills sit outside the D003/D016 LOC budget, so the core budget is unchanged.
- Whether a tagged scenario is a real test of its axis stays with the
  reviewer: the oracle proves breadth, not truth.
