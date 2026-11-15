---
description: Autonomously drive product delivery end to end — the oracle picks the next action, focused subagents execute it, every wave ships as a reviewed PR
allowed-tools: [Bash, Read, Grep, Glob, Edit, Write, Task]
---
# /ship-loop — Autonomous product delivery, one iteration at a time

Arguments (`$ARGUMENTS`), all optional:

| Arg | Default | Meaning |
|---|---|---|
| `--repo=sources/<repo>` | cwd inside `sources/` | Target repo (must be registered in REPOS.md) |
| `--feature=<name>` | first unfinished | Restrict the loop to one `specs/<feature>/` |
| `--merge=review\|auto` | `review` | `review` leaves each PR open for a human; `auto` merges green PRs |
| `--max=<N>` | `25` | Iteration budget before the loop stops and reports |

## Context

!`python -m openharness self`
!`python -m openharness env`
!`python -m openharness run ship_loop --action=status --repo_path=<repo>`

## The contract

`skills/product/ship_loop.py` is the **deterministic oracle**. It owns loop
state in `specs/<feature>/LOOP.md` (status, iteration counter, wave table,
append-only event log) and answers exactly one question per call: *what is
the next action?* `WAVES.md` remains the plan; `LOOP.md` is the execution
record. Both are product artifacts committed with the feature's PRs.

**The agent is the loop (D001).** The harness never launches agents, never
schedules tasks, never runs a DAG. You call the oracle, you do the work, you
write the outcome back. Never hand-edit `LOOP.md` — the skill is its only
writer. Never skip the oracle "because you remember" — re-read it every
iteration so the loop survives context loss and session restarts.

One iteration = one `--action=next` call + the work that directive names +
one state write (`start` / `complete` / `block` / `finish`).

## Loop

```
ship_loop --action=next   → read directive
  ├─ "no specs yet" / "complete the spec" / "plan waves"  → product-framer
  ├─ GATE: ...                                             → resolve or block
  ├─ "implement wave N" / "resume wave N"                  → wave-implementer
  │      └─ then wave-reviewer (must pass) → record complete
  ├─ "validate <feature>"                                  → delivery-verifier
  │      └─ then record finish
  ├─ BLOCKED / STOP                                        → report, exit
  └─ DONE / FEATURE-DONE                                   → close out, exit
```

After each delegated action, call `ship_loop --action=next` again. Do not
batch iterations or assume the next action; the oracle re-derives it from
the artifacts on disk.

### Recording rules

| Moment | Command |
|---|---|
| Before touching code | `--action=start --wave=N` |
| After green CI + review | `--action=complete --wave=N --pr="#<n>" --note="<tests N/N, CI green, demo: ...>"` |
| Agent-owned gate satisfied | `--action=gate --gate=G1 --status=met --evidence="file:docs/x.md / command output"` |
| Gate needs a human | `--action=block --note="G1: <decision or access needed>"`; after resolution record `met`/`waived`, then `--action=resume` |
| Gate waived by a human | `--action=gate --gate=G1 --status=waived --waived-by="<name>" --note="<reason>"` |
| Human decision needed | `--action=block --note="<exactly what must be decided>"` |
| Human resolved it | `--action=resume` |
| Validation walked | `--action=finish` (requires `VALIDATION.md`, all waves done, finish gates met) |
| Wave went sideways | `--action=reset --wave=N` (or `--force` for a full reset) |

Evidence is not optional: `--note` must name the tests that ran and their
result. "Done" without evidence is how loops lie to themselves.

## Gates — preconditions for phase transitions

Complex domains need decisions, artifacts, access, or sign-offs **before** a
phase can start. Those are gates, declared in `specs/<feature>/GATES.md`
(definitions) and tracked in `LOOP.md` (status/evidence). A blocking gate
stops the phase it is attached to:

| `Before:` | Blocks |
|---|---|
| `spec` | writing/refining the spec (domain glossary, regulatory rules) |
| `plan` | planning waves (architecture decisions, data contracts) |
| `wave:<n>` | starting wave n (credentials, seed data, schema) |
| `validate` | running validation (UAT environment, test data) |
| `finish` | closing the feature (legal/security/product sign-off) |

Overdue gates keep blocking: if a `Before: spec` gate is still pending when
the artifacts already exist, the loop refuses wave 1 until it is met or
waived. Gates are not checkboxes to route around.

When the oracle prints `GATE:`:

1. Read each gate's `owner`, `resolver`, and `check`.
2. **Resolver `agent`** — create the artifact or run the check, then record
   it with `--action=gate --gate=Gx --status=met --evidence="..."`.
   `Check: file:<path>` is verified by the oracle (the file must exist);
   `Check: command:<cmd>` is run by you, and you record the output — the
   oracle never executes repo-provided commands.
3. **Resolver `human`** — do not guess or self-approve. Record
   `--action=block --note="Gx: <what the person must decide/provide>"`,
   report, and exit. When the human answers, record the evidence and
   `--action=resume`.
4. **Waivers** are human decisions. Record one only when a human explicitly
   approved it: `--status=waived --waived-by="<name>" --note="<reason>"`.
5. Advisory gates (`Blocking: no`) are reported but never stop the loop.

If a gate turns out to be wrong (not a real precondition), fix `GATES.md` —
do not silently mark it met. If a check fails, record `--status=failed` with
the failure so the loop stops honestly.

## Optional — challenge a design decision

Gates check *whether* a precondition exists; they do not judge *how* a
decision was made. When a spec records a high-impact decision (data ownership,
schema, public contract, service split, security control) or the domain is
contested, run `/challenge-decision` before the wave that inherits it:

```
python -m openharness run challenge_decision --repo_path=<repo> \
  --spec_dir=<repo>/specs/<feature> --paths="<paths>" --write
```

Delegate the judgment to **decision-challenger**. It returns
`ACCEPT`/`REVISE`/`REVISIT`/`SPLIT` plus the smallest next step. This is
**advisory** (D011): it is not a gate, it never stops the loop, and a `REVISE`
becomes a backlog item or a new wave — not a silent edit during review. If the
review changes the decision, update `SPEC.md` → Decisions and, when it affects
a precondition, `GATES.md`.

Skip it for small reversible choices; a review that fires constantly stops
being read.

## Wave execution protocol

1. Delegate to **wave-implementer** with: repo path, spec dir, wave number,
   scenarios/backlog items from the directive, and `merge=review|auto`.
2. The implementer branches `feat/<feature>-w<N>` from the default branch,
   writes failing checks first for that wave's scenarios, implements
   minimally, runs the real build + tests, commits conventionally, pushes,
   and opens one PR (`feat:`/`fix:` etc.; body cites the spec and scenarios).
3. Wait for CI. Green → delegate to **wave-reviewer** (diff vs. spec,
   regressions, secrets, scope creep). Red → send the failure back to
   wave-implementer; retry once for flakiness, then block.
4. Review passes → apply the merge policy:
   - `review` (default): leave the PR open, record its number, continue to
     the next wave. The user merges later in order.
   - `auto`: merge only after green CI and a passing review, delete the
     branch, then record.
5. Record `complete` with the PR number and evidence.

Never merge a PR whose CI is red or pending. Never force-push a default
branch. Never commit secrets or `.env` files. One logical change per PR.

## Spec / planning protocol

Delegate to **product-framer** with the repo path and any feature hint. It
runs `discover_product`, proposes 3–5 scored candidates (value ×
feasibility × differentiation), picks the highest in autonomous mode,
scaffolds `specs/<feature>/`, fills SPEC.md / EXAMPLES.feature (tagged
`@w<N>`) / BACKLOG.md (user stories with `Depends:`), derives preconditions
into GATES.md, and runs `wave_plan` until warnings are clean. It may write
**only** under `specs/`.

The orchestrator then calls `ship_loop --action=next` again to enter wave 1.

## Validation protocol

Delegate to **delivery-verifier**. It runs `ship_validate`, walks the demo
script, verifies each acceptance criterion has scenario + wave + test
evidence, refreshes `specs/PRODUCT.md` via `product_map`, and updates
README/AGENTS.md for what shipped. It also verifies that every `Before:
validate` and `Before: finish` gate is met or explicitly waived. Real gaps
are reported back — do not paper over them. Only then call `--action=finish`.

## Stop conditions (report and exit the loop)

- `DONE` / `FEATURE-DONE` from the oracle — close out.
- `STOP` — iteration budget exhausted; report progress and the next action.
- `BLOCKED` — the note says what a human must decide (scope, pricing,
  credentials, destructive migration, product direction).
- A `GATE:` directive whose resolver is `human` — record `block`, report, exit.
- A failed gate check that needs a human decision or a re-plan.
- Two consecutive CI failures on the same wave after one flaky rerun.
- A merge conflict, a dirty worktree with changes you did not make, or a
  repo that is not registered / has no remote.
- Anything requiring secrets, credential rotation, or deleting user data.
- The user interrupts.

## Close-out report

When the loop ends, report:

```
Feature: <name> — <status>
Iterations: N/max
Waves:    W1 done (#12) · W2 done (#14) · W3 pending
Gates:    G1 met · G2 met · G3 pending (owner: security, resolver: human)
PRs:      #12, #14 (merge order matters; stacked: #14 on #12)
Evidence: <tests run, CI state>
Gaps:     <known gaps or "none">
Next:     <exact oracle directive or "needs human decision: ...">
```

Also update `specs/PRODUCT.md` (`product_map`) and leave `LOOP.md` committed
so the next session resumes exactly where this one stopped.

## Guardrails

- Specs and loop state live in the target repo under `specs/` — product
  content, committed via PRs. Harness config files are never copied into
  target repos (D008).
- Do not touch uncommitted changes you did not create; check
  `git status` before every wave and stop if the tree is dirty.
- Re-check PR state via the GitHub API before merging — another process or
  human may have merged or edited it.
- Respect the target repo's own AGENTS.md, build commands, and conventions.
- If the oracle's directive and reality disagree (e.g. LOOP.md says done but
  the PR is unmerged), trust reality, `--action=reset --wave=N`, and redo.
