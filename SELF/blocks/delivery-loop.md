---
name: delivery-loop
type: block
location: skills/product/ship_loop.py, .opencode/commands/ship-loop.md, .claude/commands/ship-loop.md, .opencode/agents/, .claude/agents/
interfaces: [ship_loop.invoke, ship_loop --action=next|status|start|complete|block|resume|reset|finish]
---
# Block: delivery-loop

## Purpose
Turns the `/ship-product` phased playbook into a **repeatable, resumable
loop** that an agent can drive autonomously across many sessions. The Python
skill is the deterministic oracle: it reads the spec artifacts plus its own
state file and answers "what is the next action?" The Markdown command and
subagents are the execution protocol. The harness never launches or schedules
anything (D001, D009).

## State model
- `specs/<feature>/WAVES.md` — the plan. Written by `wave_plan`, never by the loop.
- `specs/<feature>/LOOP.md` — the execution record. **Only `ship_loop` writes it.**
  ```
  Status: running | blocked | done
  Iterations: <n>
  | Wave | Status | Branch | PR | Evidence | Updated |
  | 1 | done | feat/x-w1 | #12 | 4/4 tests, CI green | ... |
  ## Events
  - <timestamp> start wave 1 on feat/x-w1
  - <timestamp> complete wave 1 (#12): 4/4 tests, CI green
  ```
- `specs/<feature>/VALIDATION.md` — written by `ship_validate`; required by `finish`.
- `specs/PRODUCT.md` — cross-feature map, refreshed by `product_map`.

## Actions
| Action | Effect |
|---|---|
| `next` | Increment the iteration counter and print the next directive, `DONE`, `BLOCKED`, or `STOP`. |
| `status` | Same decision without incrementing (orientation). |
| `start --wave=N` | Mark wave N in progress, record branch, reset `blocked`. |
| `complete --wave=N --note=... [--pr=#n]` | Mark wave N done with evidence; prints the next directive. |
| `block --note=...` | Stop the loop; the note is what a human must decide. |
| `resume` | Clear `blocked`. |
| `reset [--wave=N] [--force]` | Reset one wave, or the whole loop (needs `--force`). |
| `finish` | Mark a validated feature done (requires `VALIDATION.md`, all waves done). |

Phases map to ship-product: no specs → frame; missing artifacts → spec;
no `WAVES.md` → plan; pending wave → wave N; all waves done → validate;
`VALIDATION.md` present → feature done.

## Invariants
- The agent is the loop. No daemon, cron, queue, or scheduler in the harness.
- One `next` call per iteration; the oracle re-derives state from disk.
- The iteration budget (default 25) is a hard stop, not a suggestion.
- Out-of-order `start`/`complete` is rejected unless `--force`.
- `complete` requires evidence; `block` requires a decision to hand back.
- Events are append-only (last 200 kept).
- Default merge policy is `review`: PRs stay open for a human.

## How to Extend
1. Keep phase logic in `skills/product/ship_loop.py`; do not duplicate it in
   command files or subagents.
2. New artifact gates go in `_decide()` and get a test in
   `tests/test_ship_loop.py`.
3. New actions must update `_load_state`/`_save_state`, the docstring, the
   command tables, and this block.
4. New subagent roles are `.opencode/agents/<name>.md` with
   `mode: subagent` plus a `.claude/agents/<name>.md` mirror.
