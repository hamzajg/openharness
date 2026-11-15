# ADR 0004 — Gates as declared preconditions

Status: accepted · 2026-11-15 · decision D010

## Context

The delivery loop (ADR 0003) advances through phases: spec → plan → wave N →
validate → finish. It assumes that by the time a phase starts, everything the
phase needs already exists: business rules are decided, data contracts are
agreed, sandbox credentials are available, seed data is loaded, legal/security
sign-off is in hand.

For simple features that assumption holds. For complex domains it does not:

- an acceptance criterion encodes a business rule nobody has signed off
  (coverage exclusions, tax treatment, refund policy, eligibility);
- a wave needs a data contract or event schema that has not been agreed;
- a wave needs external access (sandbox, third-party API, test tenant);
- validation needs UAT data or an environment that is not ready;
- shipping needs a security/legal/product sign-off.

Without an explicit precondition, the loop does the worst possible thing: it
invents a rule, fakes a credential, skips validation, or silently declares the
feature done. A prose note in `SPEC.md` ("pending legal review") is not
enforced and disappears from the agent's context.

## Decision

Phase transitions are guarded by **gates**:

1. **Definitions** live in `specs/<feature>/GATES.md`, one block per gate:
   `Before` (`spec`/`plan`/`wave:<n>`/`validate`/`finish`), `Type`
   (`decision`/`artifact`/`external`/`technical`/`quality`/`data`), `Owner`,
   `Resolver` (`human`/`agent`), `Blocking` (`yes`/`no`), `Check`
   (`manual`/`file:<path>`/`command:<cmd>`), and `Why` (the AC or rule that
   depends on it).
2. **Status** lives in `LOOP.md` under `## Gates`: `pending`, `met`,
   `waived`, or `failed`, with evidence and timestamp. `ship_loop` is the only
   writer.
3. **Enforcement** is in the oracle. Before any phase directive it collects
   blocking gates due at or before that phase and prints a `GATE:` directive
   instead. `start`, `finish`, and `next` all respect it.
4. **Evidence rules.** `met` requires `--evidence`. `file:` checks are
   verified by the oracle (the path must exist); `command:` checks are run by
   the agent and the output recorded — the oracle never executes
   repo-provided commands. A met `file:` gate whose evidence later disappears
   becomes `stale` and blocks again.
5. **Waivers** require `--waived-by` and `--note`. Only a human can waive.
6. **Overdue gates keep blocking.** Filling artifacts out of order must not
   let a pending `Before: spec` gate slip past by jumping to wave 1. A gate
   with an invalid `Before` blocks every phase until fixed. Advisory gates
   (`Blocking: no`) are reported but never block.
7. **Ownership.** The agent resolves `agent`-owned gates inline; a
   `human`-owned gate is handed back with `--action=block` naming exactly what
   the person must decide or provide. The agent never self-approves a human
   gate.

`spec_scaffold` writes an empty `GATES.md`; `product-framer` derives gates
from the AC table; `wave-implementer` refuses to start a wave with an unmet
entry gate; `wave-reviewer` and `delivery-verifier` verify gate evidence.

## Consequences

- Complex-domain preconditions are explicit, owned, and falsifiable before
  code is written, instead of living in prose or in someone's head.
- The loop stops honestly on a missing decision or access instead of
  inventing a rule or skipping sign-off — preserving the human-in-the-loop
  boundary in D001/D009.
- The oracle stays deterministic and offline: it parses `GATES.md`, checks
  file existence, and never runs repo code.
- Backwards compatible: a feature without `GATES.md` behaves exactly as
  before.
- Cost: one small artifact per feature and an extra status table in
  `LOOP.md`; gates must be kept honest (fix a wrong gate in `GATES.md`, do not
  route around it).
