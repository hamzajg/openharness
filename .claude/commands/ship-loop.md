---
description: Autonomously drive product delivery end to end — the oracle picks the next action, focused subagents execute it, every wave ships as a reviewed PR
allowed-tools: [Bash, Read, Grep, Glob, Edit, Write, Task]
---
# /ship-loop — Autonomous product delivery

Arguments (`$ARGUMENTS`). All are optional:

| Arg | Default | Meaning |
|---|---|---|
| `--repo=sources/<repo>` | cwd inside `sources/` | Target repo. Must be registered in the active registry (REPOS.md or .openharness/REPOS.local.md). |
| `--feature=<name>` | first unfinished | Limit the loop to one `specs/<feature>/`. |
| `--merge=review\|auto` | `review` | `review` keeps each PR open. `auto` merges green PRs only when required protections and checks are verified. |
| `--review=required\|advisory` | `required` | Independent spec/delivery audit. `advisory` records nothing and enforces nothing. |
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

`done` means acceptance-validated, not necessarily merged or deployed.
Always report PR merge state and deployment state separately.

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
  ├─ "no specs yet" / "complete the spec"                  → product-framer
  ├─ "audit the spec"                                      → delivery-auditor
  ├─ GATE: design decisions challenged                     → /challenge-decision
  ├─ "plan waves"                                          → product-framer
  ├─ GATE: ...                                             → resolve or block
  ├─ "implement wave N" / "resume wave N"                  → wave-implementer
  │      └─ then wave-reviewer (must pass) → record complete
  ├─ "validate <feature>"                                  → delivery-verifier
  ├─ "audit the delivery"                                  → delivery-auditor
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
| After green CI + review | `--action=complete --wave=N --pr="#<n>" --note="<tests N/N, CI green, demo: ...>" --bundle="<run-id>"` |
| Agent-owned gate is satisfied | `--action=gate --gate=G1 --status=met --evidence="file:docs/x.md / command output"` — or pin a proof bundle with `--evidence="evidence:<run-id>"` (verified under either evidence root; walkthroughs do not qualify) |
| Gate needs a human | `--action=block --note="G1: <decision or access needed>"`; after resolution record `met`/`waived`, then `--action=resume` |
| Human waived a gate | `--action=gate --gate=G1 --status=waived --waived-by="<name>" --note="<reason>"` |
| Human must decide something | `--action=block --note="<exactly what must be decided>"` |
| Human resolved it | `--action=resume` |
| Validation is walked | `--action=finish` (needs `VALIDATION.md` with proven ACs — strong test evidence or `## Manual verification` entries — all waves done, finish gates met, verified evidence bundles) |
| Wave went wrong | `--action=reset --wave=N` (or `--force` for a full reset) |
| Corpus audit | `--action=compliance` — read-only per-feature report: review mode, audit verdicts, proven ACs, evidence, `done-compliant`/`done-legacy`/`done-attention` |

Evidence is mandatory. `--note` must name the tests that ran and their
result. A "done" without evidence is a false record.

## Evidence bundles (required)

Every wave ships with an evidence bundle — the oracle refuses
`--action=complete` (for that wave) and `--action=finish` until a bundle
loads, passes `verify`, records the checked-out commit, **and proves the
TDD cycle**: an ordered `tdd: red` (expected-failure test run) →
`tdd: green` → `tdd: refactor` step sequence. Mark steps with
`--tdd=red|green|refactor` on `--action=step`; the red step must also
carry `--expected-failure`. Bundles live in
`.openharness/evidence/<feature>/<run-id>/` (gitignored scratch) or in the
committable `evidence/` root when `new` is given `--tracked`. The harness does not drive browsers: Playwright, a human,
or you produce screenshots/recordings; the bundle hashes and catalogs
them.

1. At wave start: `python -m openharness run harness_evidence --action=new
   --repo=<repo> --feature=<feature> --wave=N`.
2. During the wave: `--action=step` for real commands (build, tests —
   exit code, duration and log are recorded). UI-touching waves attach
   at least one screenshot per acceptance scenario touched; flows over
   ~3 steps or any failed UI step get a short recording. Backend-only
   waves (services/APIs, no UI) record live request/response evidence
   instead — present it like endpoint documentation, never as a helper
   script artifact. Preferred: drive the service's own API docs UI
   (e.g. Swagger "Try it out" via Playwright — authorize, execute the
   wave's scenarios, screenshot each request/response) and attach the
   generated contract (OpenAPI/Swagger for REST, AsyncAPI for events,
   schema-registry/IDL for gRPC/protobuf or other protocols). Also
   acceptable: an HTML doc pairing each curl example with its real
   response. For screenshot-driven walkthroughs (e.g. Swagger try-it-out),
   attach each capture with `--snippet` holding its curl command — the
   renderer shows every request as a rich code card in a Requests
   section, which is the quick-test surface. Event-driven waves attach schema docs plus sample messages
   for each topic/queue the wave introduces. Never log real secrets —
   redact tokens in output.
3. Before `complete`: `--action=render` then `--action=verify` (hashes,
   commit, secrets). Fix what verify reports; never commit the bundle.
   Then record the run id with `--bundle="<run-id>"` on `complete` — the
   wave row keeps the binding (`evidence:<run-id>`) so the audit can
   re-check it later.
4. UI media can also go in a companion walkthrough bundle —
   `--action=new ... --kind=walkthrough` (same feature/wave, scratch
   root only). It holds screenshots, recordings and log summaries for
   local review; it is companion material, never the wave's proof.
   Playwright repos: generate the fixture once with
   `--action=fixture --repo=<repo>`, run the wave's spec with
   `EVIDENCE_RUN_DIR` set, then fold each `steps-<spec>.json` with
   `--action=attach --fragment=<run>/steps-<spec>.json`. Native/device
   waves: `--action=capture --device=android|ios --media=all` grabs
   screenshots, recordings and logs via `adb`/`xcrun simctl` and attaches
   them (missing tools fail with an install hint).
5. `SUMMARY.md` can be pasted into the PR body or the LOOP evidence
   column.

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

## Fill the value contract before planning (required)

`spec_scaffold` writes a blocking gate — `G0 — Value contract filled`
(`Before: plan`, `Check: file:specs/<feature>/SPEC.md`) — into every
feature's `GATES.md`. Before `wave_plan`, fill all six fields of
`SPEC.md` → `## Value contract` (problem, users, baseline/current cost,
numeric target outcome indicator, economic hypothesis, owner/date) and
record the gate `met`. A placeholder or a target without a number is
not filled; a later regression makes the gate `stale`. This is D017:
the value gap must be stated before features are committed. Measured
outcomes stay post-release learning (D009), not a finish gate.

## Domain model + experience before planning (required)

`spec_scaffold` also writes two more blocking `Before: plan` gates
(D019): `G2 — Domain model captured`
(`Check: file:specs/<feature>/DOMAIN.md`) and `G3 — Experience contract
filled` (`Check: section:specs/<feature>/SPEC.md#Experience`).

- `DOMAIN.md` must declare its tier (`simple | standard |
domain-heavy`), a ubiquitous-language glossary, bounded contexts with
  translation points, aggregates/invariants, the transaction boundary,
  integration style, and external translations. `simple` is honest
  thinness — it still names the owning context and states "no new domain
  concepts" explicitly.
- `## Experience` in SPEC.md needs the primary journey, edge states, a
  concrete UX bar and accessibility notes — or `N/A — <reason>` for a
  feature with no user-facing surface. A bare `N/A` is rejected.

Both checks are shallow on purpose: they prove the contract exists and is
not a template. Whether a `domain-heavy` model is real is the spec
audit's and wave reviewer's judgment, not the oracle's.

## Challenge design decisions (required by default)

`spec_scaffold` writes a blocking gate — `G1 — Design decisions
challenged` (`Before: plan`, `Check:
file:specs/<feature>/DECISION-REVIEW.md`) — into every feature's
`GATES.md`. The loop refuses wave planning and wave 1 until that artifact
exists. The gate checks *that the review happened*; the verdict itself
stays advisory (D011) and never blocks a merge.

When the oracle prints `GATE:` for it (or before `wave_plan`):

1. Make sure `SPEC.md` → `## Decisions` records each one-way-door choice
   in the required shape: context & forces, at least two credible options
   (including the simplest and the most reversible), decision & why,
   consequences (+/-), reversibility and revisit trigger.
2. Build the brief and persist it:
   ```
   python -m openharness run challenge_decision --repo_path=<repo> \
     --spec_dir=<repo>/specs/<feature> --paths="<paths>" --write
   ```
3. Give the brief to **decision-challenger**. It steelmans the decision,
   generates alternatives, applies the DDD / architecture / testability /
   craftsmanship lenses, scores with evidence, and fills the verdict block
   in `DECISION-REVIEW.md`.
4. Verify the review — do not rubber-stamp it — then record the gate:
   `--action=gate --gate=G1 --status=met --evidence="file:specs/<feature>/DECISION-REVIEW.md — verdict ACCEPT"`.
5. A `REVISE` / `REVISIT` / `SPLIT` verdict is design feedback, not a
   blocker. Fold the smallest next step into `SPEC.md` → Decisions, a
   backlog item, or a wave. Update `GATES.md` if a precondition changes.

A human may waive G1 for genuinely trivial features — record the waiver,
never assume it. Skip *extra* reviews for small reversible choices inside
a wave; the gate covers the decisions every wave inherits. A wave that
introduces a NEW one-way-door decision must challenge it before coding
(see the wave protocol).

## Independent review (required)

Gates check *if* a precondition exists. They do not prove that the spec is
grounded in the repo or that the delivery matches the spec. Two audit
artifacts do, and this loop runs with `--review=required`:

- `specs/<feature>/SPEC-AUDIT.md` — required before `wave_plan` and wave 1.
- `specs/<feature>/DELIVERY-AUDIT.md` — required after `VALIDATION.md`,
  before `finish`.

Build the deterministic brief, then hand it to **delivery-auditor**:

```
python -m openharness run review_delivery --repo_path=<repo> \
  --spec_dir=<repo>/specs/<feature> --phase=spec|delivery --write
```

The auditor re-verifies every finding, opens the cited code and tests, and
fills one verdict:

- `PASS` — all lists empty and evidence was verified.
- `CONCERNS` — every remaining item is non-blocking and explicitly accepted.
- `BLOCK` — a confirmed blocker, a hallucinated claim, or an unproven
  acceptance criterion. **Stop.** Fix it in a wave, re-run, re-audit.

A `BLOCK` verdict stops the loop. Do not edit the verdict by hand; fix the
spec or the delivery. The audit is not a `GATES.md` gate and never marks one.

## Wave steps

1. Give **wave-implementer**: repo path, spec dir, wave number, the wave's
   scenarios and backlog items, and `merge=review|auto`.
2. Before dispatching, determine the effective base and PR target:
   - If the preceding wave PR is open, use its head as the branch base and
     its branch as this PR's target (stack it).
   - If the preceding PR has merged, use the default branch for both.
   - Pass both values to the implementer and record the stack/merge order.
3. The implementer must:
   - Branch from the supplied effective base and target the PR at the
     supplied base PR branch. If either is missing or ambiguous, stop and
     ask; do not guess.
   - Write failing checks first for the wave's scenarios.
   - Implement the smallest correct change. Match repo conventions (KISS).
   - Run the real build and tests.
   - Commit with conventional messages. Push. Open one PR. The PR body
     cites the spec and the scenarios.
4. Wait for CI.
   - Green: give the diff to **wave-reviewer**. Check spec fit,
     regressions, secrets, and scope.
   - Red: return the failure to wave-implementer. Retry once for flake.
     Then block.
5. Review passes. Apply the merge policy:
   - `review` (default): leave the PR open. Record its number. Continue.
   - `auto`: first verify target-branch protection and required CI/security
     checks. If they cannot be confirmed, stop and hand off in review mode.
     Merge only after green CI and a passing review.
6. After a parent PR merges, the orchestrator retargets/rebases open
   descendants onto the default branch and reruns CI before their merge.
   Do not delete a branch while an open PR depends on it.
7. Record `complete` with the PR number and the evidence.

Never merge a PR with red or pending CI. Never force-push a default
branch. Never commit secrets or `.env` files. One logical change per PR.

## Outcomes, execution boundaries, and flow evidence

- In `SPEC.md`, fill the D017 `## Value contract` before planning: problem,
  users, baseline/current cost, numeric target with review window, economic
  hypothesis, and owner/date. Gate G0 blocks `wave_plan` until it is filled;
  the value/economics lens and audit finding are advisory.
- Also record an outcome hypothesis, the evidence or assumption behind it,
  an observable signal, and an owner/review date when known. Never invent
  user research or baselines; the numeric target is the explicit
  value-contract claim.
- Report outcomes, not output (D018): lead with the value contract's target
  and whatever real evidence exists; features, APIs and coverage are
  supporting output. Name the five dimensions the release improves and any
  it makes worse. Unmeasured outcomes stay unverified, not implied.
- The harness protocol does not sandbox agents. Read the target repo's
  `AGENTS.md` and layered `.openharness/ENV.md`; follow host permission
  prompts and least-privilege settings. Do not broaden filesystem, network,
  or credential access. Stop for a human if required access is unavailable.
- After release, record an optional outcome follow-up in `VALIDATION.md`.
  If the feature is not released yet, leave it pending with an owner/date.
  This is learning evidence, not a finish gate.
- At close-out, report acceptance status, PR merge status, and deployment
  status separately. Include elapsed phase/PR review times only when they
  can be derived from actual timestamps. Use measurements to find friction,
  not to rank teams.

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

8. Run the spec audit (`/review-delivery --phase=spec --write`) and fix every
   confirmed blocker before wave 1. A `BLOCK` verdict stops the loop.

9. Resolve the design-challenge gate (`G1` in `GATES.md`): run
   `/challenge-decision` on `SPEC.md` → Decisions, let
   **decision-challenger** fill `DECISION-REVIEW.md`, then record the gate
   `met`. See "Challenge design decisions".

Then call `ship_loop --action=next` again to enter wave 1.

## Validation steps

Give **delivery-verifier** the spec dir. It must:

1. Run `ship_validate`.
2. Walk the demo script by hand.
3. Verify that each acceptance criterion has scenario + wave + test
   evidence. Weak token matches and `—` are not proof: add scenario-named
   tests, or record each unproven AC under `## Manual verification` in
   `VALIDATION.md` with the command run and observed result.
4. Refresh `specs/PRODUCT.md` with `product_map`.
5. Update `README.md` and `AGENTS.md` for what shipped.
6. Verify that each `Before: validate` and `Before: finish` gate is `met`
   or `waived`.
7. Run the delivery audit (`/review-delivery --phase=delivery --write`) and
   fix every confirmed blocker. A `BLOCK` verdict stops the loop.

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
PRs:      <open/merged per wave; stacked PRs include merge order>
Evidence: <tests run, CI/review state>
Audit:    spec PASS · delivery CONCERNS (accepted: ...) · artifacts: ...
Deploy:   deployed | not deployed | unknown — <evidence>
Outcome:  <observed signal or pending owner/date>
Flow:     <elapsed/review times, if evidence is available>
Gaps:     <known gaps or "none">
Next:     <exact oracle directive or "needs human decision: ...">
```

Then refresh `specs/PRODUCT.md` (`product_map`). Commit `LOOP.md` and
`LOOP.state.json`. The next session must resume exactly where this one
stopped. Do not describe a validated feature as released unless its actual
merge/deployment state confirms that.

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
