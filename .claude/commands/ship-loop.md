---
description: Autonomously drive product delivery end to end — the oracle picks the next action, focused subagents execute it, every wave ships as a reviewed PR
allowed-tools: [Bash, Read, Grep, Glob, Edit, Write, Task]
---
# /ship-loop — Autonomous product delivery

Arguments (`$ARGUMENTS`). All are optional:

| Arg | Default | Meaning |
|---|---|---|
| `--repo=sources/<repo>` | cwd inside `sources/` | Target repo. Must be in REPOS.md. |
| `--feature=<name>` | first unfinished | Limit the loop to one `specs/<feature>/`. |
| `--merge=review\|auto` | `review` | `review` keeps each PR open. `auto` merges green PRs. |
| `--max=<N>` | `25` | Iteration limit before the loop stops. |

## Context

!`python -m openharness self`
!`python -m openharness env`
!`python -m openharness run ship_loop --action=status --repo_path=<repo>`

## The loop contract

`skills/product/ship_loop.py` is the deterministic oracle. It owns the loop
state in `specs/<feature>/`:

- `LOOP.md` — human-readable status. Committed with the PRs.
- `LOOP.state.json` — machine-readable state. Committed with the PRs.
- `WAVES.md` — the plan. Do not change it during the loop.

The oracle answers one question per call: *what is the next action?*

**The agent is the loop (D001).** The harness does not start agents. The
harness does not schedule work. You do three things:

1. Call the oracle.
2. Do the work that the directive names.
3. Record the result.

Rules:

- Never edit `LOOP.md` or `LOOP.state.json` by hand. The skill is the only
  writer.
- Call the oracle at each iteration. Do not use memory. The loop must
  survive context loss and session restarts.

One iteration = one `--action=next` call + the named work + one state write
(`start`, `complete`, `block`, or `finish`).

## The loop

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
batch iterations. Do not guess the next step. The oracle reads the files on
disk.

## Record each step

| Moment | Command |
|---|---|
| Before you touch code | `--action=start --wave=N` |
| After green CI + review | `--action=complete --wave=N --pr="#<n>" --note="<tests N/N, CI green, demo: ...>"` |
| Agent-owned gate is satisfied | `--action=gate --gate=G1 --status=met --evidence="file:docs/x.md / command output"` |
| Gate needs a human | `--action=block --note="G1: <decision or access needed>"`; after resolution record `met`/`waived`, then `--action=resume` |
| Human waived a gate | `--action=gate --gate=G1 --status=waived --waived-by="<name>" --note="<reason>"` |
| Human must decide something | `--action=block --note="<exactly what must be decided>"` |
| Human resolved it | `--action=resume` |
| Validation is walked | `--action=finish` (needs `VALIDATION.md`, all waves done, finish gates met) |
| Wave went wrong | `--action=reset --wave=N` (or `--force` for a full reset) |

Evidence is mandatory. `--note` must name the tests that ran and their
result. A "done" without evidence is a false record.

## Gates

A gate is a precondition for a phase. Declare gates in
`specs/<feature>/GATES.md`. Track their status in `LOOP.md` and
`LOOP.state.json`. A blocking gate stops its phase.

| `Before:` | Blocks |
|---|---|
| `spec` | spec writing (glossary, rules) |
| `plan` | wave planning (architecture, data contracts) |
| `wave:<n>` | wave n start (credentials, seed data, schema) |
| `validate` | validation (UAT environment, test data) |
| `finish` | feature close (sign-offs) |

Overdue gates keep blocking. If a `Before: spec` gate is pending but the
spec exists, the loop refuses wave 1 until the gate is `met` or `waived`.
Do not route around a gate.

When the oracle prints `GATE:`:

1. Read the gate's `owner`, `resolver`, and `check`.
2. Resolver `agent`: make the artifact or run the check. Record it with
   `--action=gate --gate=Gx --status=met --evidence="..."`.
   - `Check: file:<path>` — the oracle verifies the file exists.
   - `Check: command:<cmd>` — you run it and record the output. The oracle
     does not run repo commands.
3. Resolver `human`: do not guess. Do not self-approve. Run
   `--action=block --note="Gx: <what the person must decide>"`. Report and
   exit. When the human answers, record the evidence and run
   `--action=resume`.
4. Waivers are human decisions only. Record one only after a human says
   yes: `--status=waived --waived-by="<name>" --note="<reason>"`.
5. Advisory gates (`Blocking: no`) are reported. They do not stop the loop.

If a gate is wrong, fix `GATES.md`. Do not mark it `met` silently. If a
check fails, record `--status=failed` with the failure.

## Challenge a design decision (optional)

Gates check *if* a precondition exists. They do not check *how* a decision
was made. For a high-impact decision (data ownership, schema, public
contract, service split, security control) or a contested domain, run
`/challenge-decision` before the wave that uses it:

```
python -m openharness run challenge_decision --repo_path=<repo> \
  --spec_dir=<repo>/specs/<feature> --paths="<paths>" --write
```

Give the review to **decision-challenger**. It returns
`ACCEPT`/`REVISE`/`REVISIT`/`SPLIT` plus the smallest next step. The review
is advisory (D011). It is not a gate. It does not stop the loop. A `REVISE`
becomes a backlog item or a new wave. Do not edit the decision silently
during review. If the review changes the decision, update `SPEC.md` →
Decisions. If it changes a precondition, update `GATES.md`.

Skip the review for small reversible choices. A review that fires too
often stops being read.

## Wave steps

1. Give **wave-implementer**: repo path, spec dir, wave number, the wave's
   scenarios and backlog items, and `merge=review|auto`.
2. The implementer must:
   - Branch `feat/<feature>-w<N>` from the default branch.
   - Write failing checks first for the wave's scenarios.
   - Implement the smallest correct change. Match repo conventions (KISS).
   - Run the real build and tests.
   - Commit with conventional messages. Push. Open one PR. The PR body
     cites the spec and the scenarios.
3. Wait for CI.
   - Green: give the diff to **wave-reviewer**. Check spec fit,
     regressions, secrets, and scope.
   - Red: return the failure to wave-implementer. Retry once for flake.
     Then block.
4. Review passes. Apply the merge policy:
   - `review` (default): leave the PR open. Record its number. Continue.
   - `auto`: merge only after green CI and a passing review. Delete the
     branch. Record the merge.
5. Record `complete` with the PR number and the evidence.

Never merge a PR with red or pending CI. Never force-push a default
branch. Never commit secrets or `.env` files. One logical change per PR.

## Spec and plan steps

Give **product-framer** the repo path and an optional feature hint. It
must:

1. Run `discover_product`.
2. Propose 3–5 candidate features. Score each: user value × feasibility ×
   differentiation.
3. Pick the best candidate in autonomous mode.
4. Scaffold `specs/<feature>/`.
5. Fill `SPEC.md`, `EXAMPLES.feature` (tags `@w<N>`), `BACKLOG.md` (user
   stories with `Depends:`).
6. Derive preconditions into `GATES.md`.
7. Run `wave_plan` until it reports no warnings.

The framer writes only under `specs/`.

Then call `ship_loop --action=next` again to enter wave 1.

## Validation steps

Give **delivery-verifier** the spec dir. It must:

1. Run `ship_validate`.
2. Walk the demo script by hand.
3. Verify that each acceptance criterion has scenario + wave + test
   evidence.
4. Refresh `specs/PRODUCT.md` with `product_map`.
5. Update `README.md` and `AGENTS.md` for what shipped.
6. Verify that each `Before: validate` and `Before: finish` gate is `met`
   or `waived`.

Report real gaps. Do not hide them. Only then call `--action=finish`.

## Stop conditions

Report and exit the loop when:

- The oracle says `DONE` or `FEATURE-DONE`.
- The oracle says `STOP` (iteration budget).
- The oracle says `BLOCKED`. The note names the human decision.
- A `GATE:` directive has `resolver: human`. Record `block`. Report. Exit.
- A gate check fails and needs a human decision or a re-plan.
- CI fails twice on the same wave after one flaky retry.
- A merge conflict occurs.
- The worktree is dirty with changes you did not make.
- The repo is not registered or has no remote.
- The task needs secrets, credential rotation, or data deletion.
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

Then refresh `specs/PRODUCT.md` (`product_map`). Commit `LOOP.md` and
`LOOP.state.json`. The next session must resume exactly where this one
stopped.

## Guardrails

- Specs and loop state live in the target repo under `specs/`. They are
  product content. Commit them through PRs. Never copy harness files into
  target repos (D008).
- Check `git status` before each wave. Stop if the tree is dirty with
  changes you did not make.
- Re-check PR state through the GitHub API before each merge. A human or
  another process can merge or edit a PR.
- Follow the target repo's `AGENTS.md`, build commands, and conventions.
- If the oracle and reality disagree (for example: `LOOP.md` says done but
  the PR is open), trust reality. Run `--action=reset --wave=N`. Redo.
