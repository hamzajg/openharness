---
name: scenario-maturity
type: block
location: skills/product/spec_scaffold.py, skills/product/ship_loop.py, skills/product/review_delivery.py, skills/product/ship_validate.py, skills/product/wave_plan.py, .opencode/commands/ship-product.md, .claude/commands/ship-product.md, .opencode/commands/ship-loop.md, .claude/commands/ship-loop.md, .opencode/commands/review-delivery.md, .claude/commands/review-delivery.md, .opencode/agents/product-framer.md, .claude/agents/product-framer.md, .opencode/agents/wave-implementer.md, .claude/agents/wave-implementer.md, .opencode/agents/wave-reviewer.md, .claude/agents/wave-reviewer.md, .opencode/agents/delivery-auditor.md, .claude/agents/delivery-auditor.md
interfaces: [spec_scaffold.maturity_status, spec_scaffold.maturity_wave_problems, spec_scaffold.declared_tier, ship_loop --action=gate --gate=G4, review_delivery --phase=spec|delivery, wave_plan --spec_dir, ship_validate --spec_dir]
---
# Block: scenario-maturity

## Purpose
Makes `EXAMPLES.feature` a breadth contract, not just a traceability index.
The harness already proves AC → scenario → wave → test; this block adds the
question "does the example set describe a product that can survive real use?"
It exists because happy-path-only specs pass every existing gate while
producing primitive products that do not compete with real world solutions
(D020, ADR 0015).

## Axis tags
Tags sit on real `Scenario` lines alongside `@w<N>` tags. Each axis needs its
own dedicated scenario; one scenario must not carry several maturity axes.

| Tag | Axis | Mature cases it should force |
|-----|------|------------------------------|
| `@m-failure` | Failure & recovery | idempotency, retry/timeout, partial failure, stale state, conflict, compensation |
| `@m-ownership` | Auth & ownership | roles, ownership, tenant isolation, revocation, audit trail |
| `@m-data` | Data & integration | persistence/reload, migration, import/export, search/pagination, eventual consistency |
| `@m-ux` | UX edge states | empty/loading/error/permission-denied/offline, undo, accessibility, latency budget |
| `@m-outcome` | Outcome signal | observable signal tied to SPEC.md's numeric value-contract target |

An inapplicable axis is declared outside a scenario:

```
# Maturity N/A: @m-ownership — anonymous local tool, no auth boundary
```

A bare `N/A`, `<reason>` placeholder, or unknown `@m-*` tag is a finding.

## Baby steps
Each new axis is introduced in its own `@w<N>` wave and a dedicated `Scenario`;
the happy path also gets its own scenario. Several scenarios for the SAME axis
in one wave are depth, not a big-bang increment. A scenario mixing two axes, a
scenario mixing `@happy-path` with an axis, an axis with no `@w<N>`, or a wave
introducing two different axes is rejected before planning. `wave_plan` emits
the same staged-breadth checks as advisory warnings; it never reorders waves.

## Tier floors
The tier comes from `DOMAIN.md` (D019); it controls depth, never presence.

| Tier | Floor |
|------|-------|
| `simple` | happy path + at least 2 exercised axes; every other axis covered or justified |
| `standard` | at least 3 exercised axes including failure; UX covered or justified |
| `domain-heavy` | every axis covered or justified; at least 3 exercised including failure and data |

"Exercised" means a real, non-placeholder Scenario carries the tag. `N/A`
entries are reviewable decisions, not coverage. Semantic quality — whether the
scenario actually asserts the failure/ownership/data behavior — is judged by
the spec audit, challenger and wave reviewer.

## Enforcement
- `spec_scaffold` writes the tagged template and gate **G4 — Scenario maturity
  floor** (`Before: plan`, `Blocking: yes`, `Resolver: agent`,
  `Check: file:specs/<feature>/EXAMPLES.feature`). Agent-added gates start at
  G5.
- `ship_loop` refuses `gate --status=met` when `maturity_status` reports gaps
  (including big-bang waves) and turns a previously met G4 `stale` if tags or
  reasoned N/A lines vanish. The DOMAIN.md tier is read at check time; no tier
  means `simple`.
- `review_delivery` emits advisory concerns: `maturity-axis-missing`,
  `maturity-na-unjustified`, `maturity-tag-unknown`, `maturity-scenario-mixed`,
  `maturity-wave-crowded`, `maturity-axis-untagged`. The `delivery-auditor`
  re-verifies them semantically; a shallow tag is not proof.
- `ship_validate` writes a `## Maturity coverage` section to `VALIDATION.md`
  (covered axes with their first wave, justified N/A, floor status). It is a
  walkthrough aid, not a finish gate.
- `wave_plan` parses only `@w<N>` for wave ordering; extra `@m-*` tags must not
  affect that order. Staged-breadth problems appear under `## Warnings` so the
  framer can split the axes into separate small waves.
- `wave-implementer` cites the scenario **and** its axis in the RED test/PR;
  `wave-reviewer` checks the red log for the axis behavior.

## Innovation rule
Adding an axis must close a real product gap named in the value contract. No
new framework, layer, or decorative scenario is an innovation. Record the gap,
the value, and the resulting scenario in the spec; keep the score in the
existing `value × feasibility × differentiation` frame (D018).

## Invariants
- Presence is deterministic; quality is semantic. Never promote a tag count
  to proof that the behavior works.
- `@w<N>` remains the only wave signal. `@m-*` only warns; it never changes
  wave order or becomes a second planning dimension.
- Staged breadth is mandatory: one new axis per wave, one axis per dedicated
  scenario. A big-bang wave is not maturity, even if all five axes are tagged.
- N/A is an explicit, reviewable decision with a reason, never a silent skip.
- Depth scales with DOMAIN.md tier; presence does not.
- Existing loops are not retroactively gated. Widen them in a new loop
  iteration by adding the next free gate id and re-running the spec audit.
