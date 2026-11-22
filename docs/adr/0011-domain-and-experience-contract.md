# ADR 0011 — Domain model and experience as spec contracts

Status: accepted · 2026-11-23 · relates to D002 (markdown specs),
D010 (gates), D013 (delivery audit), D017 (value contract), D018
(sustainable outcomes), D019

## Context

The spec pipeline (SPEC.md + EXAMPLES.feature + BACKLOG.md + GATES.md +
WAVES.md) covers the *what* (value contract, scenarios, proven ACs, TDD
evidence) and whether design choices were *challenged* (G1 +
`challenge_decision`, whose "Domain fit (DDD)" lens already asks about
bounded contexts, aggregates and anti-corruption layers). What it lacks is
the artifact those questions review: there is no ubiquitous-language
glossary, no declared bounded-context ownership, no aggregate/invariant
capture at spec time, and no UX/experience contract. `## Scope (out)` says
what is excluded; nothing says what the domain *is*.

For simple CRUD features the gap is tolerable. For complex or innovative
features — the ones where the harness is supposed to add the most value —
agents invent vocabulary per wave, redraw boundaries opportunistically, and
ship "intuitive" UIs nobody can grade.

## Decision

Add two spec-time contracts, both scaffolded for every new feature:

1. **`DOMAIN.md`** — ubiquitous-language glossary, bounded contexts and
   their ownership/translation points, aggregates with invariants,
   transaction boundary, integration style (events vs synchronous),
   consistency needs, and anti-corruption notes for external models.
2. **`## Experience` in SPEC.md** — primary user journey, edge states that
   matter, a concrete UX bar, accessibility notes.

Both declare a **tier** (`simple | standard | domain-heavy`) that controls
required *depth*, not existence. `simple` must still name the owning
context and state "no new domain concepts" explicitly; a user-facing
feature must still name its journey or write `N/A — <reason>`.

Enforcement is deterministic but shallow, matching the value-contract
pattern: `ship_loop` gate checks `file:…/DOMAIN.md` via `domain_status`
and `section:…/SPEC.md#Experience` via `section_status`/`experience_status`
— presence, valid tier, and non-placeholder content. Bare `N/A` is
rejected; `N/A — <reason>` is an explicit, reviewable decision. Whether a
`domain-heavy` model is *real* remains semantic judgment for the spec
audit, challenger and wave reviewer.

New scaffold gates: **G2 — Domain model captured** and **G3 — Experience
contract filled**, both `Before: plan`, `Blocking: yes`, agent-resolved.
A new `section:<path>#<heading>` check type lets a gate target one `##`
section of a file without weakening the existing `file:SPEC.md` value
check — this keeps old specs (no `## Experience`) from going stale
retroactively.

## Alternatives considered

- **Sections inside SPEC.md only.** Rejected by design choice: a separate
  DOMAIN.md keeps the domain model a first-class artifact the challenger
  and auditor can cite, and scales to context maps without bloating SPEC.
- **Advisory-only (audit findings, no gate).** Rejected: the user asked for
  blocking enforcement; the artifacts are cheap to fill and expensive to
  retrofit mid-wave. Consistent with G0's precedent.
- **Per-bounded-context files.** Rejected for now: one feature rarely spans
  enough contexts to justify a file per context; the context map lives
  inside DOMAIN.md. Revisit if multi-context features prove the template
  cramped.
- **Retroactive gates on existing specs.** Rejected: gates are per-feature
  artifacts written at scaffold time; old loops stay `done-legacy` and
  visible via `--action=compliance` rather than silently blocked.

## Consequences

- `spec_scaffold` emits five artifacts (adds DOMAIN.md) and four blocking
  pre-plan gates (G0–G3). `product-framer` must classify the tier and
  start agent-added gates at G4.
- `ship_loop` learns one new check type (`section:`) and two validators;
  all shallow, all naming missing fields in errors.
- Reviewers gain concrete text to check: glossary consistency, invariant
  boundaries, edge-state implementation — semantic checks stay with agents.
- No LOC-budget impact (skills sit outside the budgeted runtime files) and
  no new runtime module; the oracle remains the only writer of loop state.
