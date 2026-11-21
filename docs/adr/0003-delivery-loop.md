# ADR 0003 — Agent-executed delivery loop

Status: accepted · 2026-11-15 · decision D009 · phase guards added 2026-11-18
(audit checkpoints from D013/ADR 0006, evidence gate from ADR 0007)

## Context

`/ship-product` defines a good seven-phase pipeline (discover → frame → spec
→ examples → waves → implement → validate), but it is a manual playbook. A
long delivery run loses its place when a session ends, and a human must
re-prompt every phase. The harness must not become a scheduler (D001).

## Decision

Add a delivery loop with three parts:

1. **Deterministic oracle** — `skills/product/ship_loop.py`. It reads the
   spec artifacts and `specs/<feature>/LOOP.md`, then returns exactly one
   directive (`frame`, `spec`, `plan`, `wave N`, `validate`, `DONE`,
   `BLOCKED`, `STOP`) and records outcomes (`start`, `complete`, `block`,
   `resume`, `reset`, `finish`).
2. **Markdown protocol** — `/ship-loop` command plus four subagent roles
   (`product-framer`, `wave-implementer`, `wave-reviewer`,
   `delivery-verifier`). The agent calls the oracle and executes the
   directive.
3. **File state** — `specs/<feature>/LOOP.md` (status, iteration counter,
   wave table, append-only events) committed with the feature's PRs.
   `WAVES.md` stays the immutable plan.

### Phase guards

The seven phases still read the same, but a phase is entered only when its
artifacts and guards are satisfied. Two later decisions add checkpoints to the
original list:

| Transition | Artifacts | Guards |
|---|---|---|
| → `spec` | — | none |
| `spec` → `plan` | `SPEC.md`, `EXAMPLES.feature`, `BACKLOG.md` | blocking `Before: spec` / `Before: plan` gates (ADR 0004); `SPEC-AUDIT.md` with a filled verdict (D013, ADR 0006) |
| `plan` → wave 1 | `WAVES.md` | `Before: wave:1` gates; no unresolved `## Warnings`; the spec audit still gates the first wave, so a plan written without it does not reach code |
| wave N | backlog items tagged `@wN` | `Before: wave:N` gates; `complete` needs an evidence bundle that records wave N, passes `verify` and is bound to the checked-out HEAD (ADR 0007) |
| waves done → `validate` | every wave `done` | `Before: validate` gates |
| `validate` → `finish` | `VALIDATION.md` | `Before: finish` gates; `DELIVERY-AUDIT.md` with a filled verdict (D013); a feature-level bundle or a verifying bundle for every done wave at HEAD (ADR 0007) |

`--review=required` is the default and turns the audit rows on;
`--review=advisory` is the explicit opt-out. `done` still means
acceptance-validated, not merged or deployed.

Default merge policy is `review`: every wave opens a PR and leaves it open
for a human. `--merge=auto` is opt-in. The iteration budget (default 25) is
a hard stop.

## Consequences

- The loop survives context loss and session restarts: the next session
  calls `--action=next` and resumes.
- No second orchestration layer; the harness still never launches agents
  (D001).
- Wave outcomes are auditable on disk, and specs/validation remain product
  artifacts rather than harness state.
- Cost: one extra oracle call per iteration and one state file per feature.
- Out-of-order or skipped phases are rejected by the oracle unless forced,
  which keeps the loop honest.
