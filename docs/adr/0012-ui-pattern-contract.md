# ADR 0012 — UI pattern as part of the experience contract

Status: accepted · 2026-11-27 · relates to D019, ADR 0011;
navigation surface extended by ADR 0013

## Context

ADR 0011 added `## Experience` to SPEC.md with a primary journey, edge
states, a UX bar and accessibility notes. That contract says *what* the
user journey is and how good the experience must be, but not how the
surface is laid out. Agents writing UI code therefore still choose a
layout freely — a centred form on one page, a two-column dashboard on
the next, with no reviewable decision between them. That is the
remaining gap where "intuitive" UI gets generated rather than derived
from the spec.

The community standards this project draws on (Material Design, Apple
HIG, Nielsen Norman Group, Shopify Polaris) differ in visual language
but agree on the scan pattern a page asks of its user: F-pattern for
dense, text- and table-led screens; Z-pattern for sparse, action-led
landing or marketing surfaces; single-column for forms and focus flows.
Naming the pattern is the smallest layout decision that constrains
composition without prescribing a design system.

## Decision

Add one field to `## Experience` in SPEC.md:

```
- UI pattern: (F-pattern | Z-pattern | single-column | F/Z; — rationale optional)
```

- `spec_scaffold` emits the field in every new SPEC.md.
- `experience_status` (used by gate G3 and `review_delivery`) requires
  the field and accepts only a named pattern, optionally followed by a
  rationale (`F-pattern — dense stock tables`). `F/Z` is accepted for
  `simple` features, where the template allows a deliberate hedge.
- A per-field `n/a — <reason>` is accepted, consistent with the rest of
  the section; the whole-section `N/A — <reason>` path is unchanged.
- Depth by tier is checked when the DOMAIN.md tier is available: `simple`
  declares `Z-pattern` (the implicit default) or the `F/Z` hedge, `standard`
  must name a pattern (the `F/Z` hedge is rejected there), and `domain-heavy`
  must name a pattern and cite a design standard it follows (Material, Apple
  HIG, Human Interface Guidelines, NN/g, Polaris, Bootstrap, Fluent, Carbon,
  Ant Design or Tailwind). With no DOMAIN.md/tier the tier check is skipped,
  so legacy specs stay valid; whether the cited standard is applied well is
  still semantic and belongs to the spec audit and wave reviewer.

## Alternatives considered

- **Free-text layout notes.** Rejected: unparseable, so no gate can
  distinguish a decision from a paragraph, and no reviewer has a fixed
  vocabulary to compare across features.
- **A separate UX.md artifact.** Rejected for now: the experience
  contract is already one section of SPEC.md; a second file adds a
  gate without adding a distinct decision surface.
- **Review-only (no field-triggered gate).** Rejected: consistency
  with D019 — the artifact is cheap at spec time and expensive to
  retrofit mid-wave.
- **Requiring an exact enum.** Rejected: it rejects a more informative
  value such as `F-pattern — dense tables`, and the template's own
  `F/Z` hedge would fail its own validator.

## Consequences

- Existing active loops whose G3 check targets `#Experience` become
  `stale` until the field is backfilled. This was observed and repaired
  in `sources/LoomLine/specs/stock-and-materials`.
- The five done-legacy LoomLine specs were backfilled with a grounded
  Experience section for the record, but no gate was retrofitted: they keep
  their original gates and remain `done-legacy`. With no DOMAIN.md, the tier
  rule does not apply to them.
- New fixtures and tests must include the field; `ship_loop` and
  `review_delivery` share `experience_status`, so one validator keeps
  both surfaces consistent.
- `ship_loop` (G3 staleness and mark-time validation) and `review_delivery`
  both resolve DOMAIN.md beside the spec and pass its tier into the shared
  validator, so a tier/pattern mismatch surfaces as a gate problem and an
  audit concern rather than drifting until review.
- No new runtime module; the oracle still performs all checks.
