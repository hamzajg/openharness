# ADR 0010 — Sustainable outcomes as the quality frame

Status: accepted · 2026-11-22 · relates to D009 (delivery loop),
D011 (advisory design review), D013 (delivery audit), D017 (value contract),
D018

## Context

ADR 0009 made the value contract explicit before planning, but a team can
still treat implementation output — features, APIs, coverage, services — as
the definition of quality. AI-assisted coding makes that mistake cheaper to
produce and more expensive to discover: generated code can be correct in
isolation, pass tests, and still solve the wrong problem, duplicate a
capability, add operational cost, or never be adopted.

The harness already has the right enforcement points: the spec's value
contract (D017), the decision review (D011), the independent delivery audit
(D013), and the loop's acceptance validation (D009). It lacks a shared
quality frame for the judgment those points require.

## Decision

Add D018: good software is sustainable outcomes across five dimensions —
business/user value, economic viability, UX/adoption, technical/operational
quality, and adaptability/longevity. Quality is judged at product, system and
business levels; technical quality is an enabler, not the objective.

Apply the frame as advisory lenses in existing artifacts:

- `product-framer` states which dimensions the feature improves and which it
  puts at risk, and prefers the simplest intervention that delivers the
  outcome.
- `challenge_decision` expands its value/economics lens with lifecycle cost,
  quality dimensions and adaptability questions. The verdict stays advisory.
- `delivery-auditor` checks outcome evidence against output claims, confirms
  the value contract is restated honestly, and records unmeasured outcomes as
  unverified rather than implied.
- `ship_loop` close-out reports outcomes first and lists features/APIs as
  supporting output.

D017's value contract remains the pre-planning artifact and G0 remains the
only blocking value gate. No score, ROI calculator, quality dashboard, new
spec section, or runtime module is added.

## Alternatives considered

- **Scoring engine or ROI calculator.** Rejected: invented precision would be
  treated as fact, and a score would replace the judgment the dimensions are
  meant to structure.
- **A new mandatory spec section for five-dimension fit.** Rejected: it
  duplicates the value contract and outcome hypothesis, and adds maintenance
  for every feature. A few lines in the existing sections are enough.
- **Blocking `finish` on measured outcomes.** Rejected: conflicts with D009.
  Many outcomes only become observable after release.
- **Replace D017 with the five dimensions.** Rejected: the value contract is
  a concrete pre-planning artifact; D018 is the broader judgment frame.

## Consequences

- Prompts and guidance get slightly longer; specs do not gain a new required
  section.
- Auditors can raise an output-only delivery report as a concern, but the
  finding is advisory and never a gate.
- Existing features are unaffected; D018 applies when a spec, decision or
  delivery is reviewed.
- No LOC-budget change and no new runtime behavior. The observer still
  reports outputs (sessions, cost, LOC) as outputs.
