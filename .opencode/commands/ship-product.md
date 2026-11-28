---
description: Take a managed repo from "code exists" to an acceptance-validated feature — discover gaps, frame ONE feature, specify it, plan waves, implement and validate
---
# /ship-product — Spec-driven product delivery

> For autonomous delivery, use `/ship-loop`. The oracle (`ship_loop`)
> walks these phases and delegates to subagents.

## Context

Run via Bash and read output:
- `python -m openharness self`
- `python -m openharness env`

## Target repo

- If the cwd is inside `sources/<repo>`, that repo is the target.
- Otherwise, ask the user which managed repo to use. See the active registry (REPOS.md or .openharness/REPOS.local.md). Do not
  guess.
- Put all spec artifacts inside the target repo under `specs/`. They are
  product content. Commit them through PRs.

## ENV

If `sources/<repo>/.openharness/ENV.md` exists, it overrides the global
`.openharness/ENV.md` for that repo.

## The pipeline

Do not skip phases.

### Phase 1 — Discover (facts, not opinions)

```
`python -m openharness run discover_product --repo_path=sources/<repo>`
```

Read the Product Surface Report. Also read `README.md`, `AGENTS.md`, and
any existing `specs/` directories. Find:

- What the product is today.
- What is stubbed (placeholder markers).
- Which routes or features exist but are thin.
- What evidence exists about user needs (interviews, support themes,
  analytics, or other direct feedback). Repository evidence is useful for
  identifying gaps, but is not customer evidence.

### Phase 2 — Frame (feature planning)
Propose 3–5 candidate features. Each must move the repo toward a
shippable product. Score each on three axes: user value, feasibility,
differentiation.

Show the shortlist to the user. Get approval for ONE feature before you
write the spec. For each candidate, state its expected user outcome and the
evidence or unverified assumption behind it. Do not invent user research,
baselines, or numeric targets.

For a kata or legacy repo, an innovative feature usually adds the missing
product loop: persistence, auth, notifications, export, or a real data
source. It does not add a new framework.

Keep the product map current:

```
`python -m openharness run product_map --repo_path=sources/<repo>`
```

`product_map` writes `specs/PRODUCT.md`: every feature's stories,
scenarios, waves, and validation state in one table. Order features by
dependency and user value. Ship ONE feature at a time.

### Phase 2.5 — Gates (preconditions)

Complex domains need prerequisites before a phase can start. Examples: a
signed-off glossary, a data contract, sandbox access, seed data, or a
security review.

Write the prerequisites into `specs/<feature>/GATES.md`:

```
## G1 — Coverage rules signed off
- Before: spec | plan | wave:<n> | validate | finish
- Type: decision | artifact | external | technical | quality | data
- Owner: <role>
- Resolver: human | agent
- Blocking: yes | no
- Check: manual | file:<repo-relative-path> | command:<exact command>
- Why: <which AC / business rule depends on it>
```

Derive the gates from the acceptance criteria. For each criterion, ask:
"what must be decided, known, or available before we can build or prove
this?" Keep 2–6 gates. Each gate must be falsifiable: a path, a decision
id, or a command output.

`/ship-loop` enforces the gates. In manual mode, treat them as hard
prerequisites. Revisit the gates in Phase 3 when the AC table is final.

### Phase 3 — Spec (spec driver)

```
`python -m openharness run spec_scaffold --repo_path=sources/<repo> --feature="<name>"`
```

Fill `specs/<feature>/SPEC.md`:

- Problem.
- Users.
- Value contract (required before planning, D017): problem severity, users
  who bear the cost, baseline/current cost, target outcome indicator with
  a numeric target and review window, economic hypothesis covering build,
  operate, adopt and migrate cost, and an owner/date. `spec_scaffold`
  emits gate `G0 — Value contract filled`; `ship_loop` refuses wave
  planning until the fields are filled and the gate is recorded `met`.
  A placeholder or a target without a number is not filled.
- Outcome hypothesis: expected user outcome, opportunity evidence, an
  observable signal (and baseline if known), and a follow-up owner/date.
  Mark unknowns explicitly; do not make up evidence or targets.
- `## Experience` (D019): primary user journey as ordered steps, edge
  states that matter, a concrete UX bar, accessibility notes, a UI pattern
  (`F-pattern`, `Z-pattern` or `single-column`) and a navigation surface
  (`full-page`, `side-pane`, `modal` or `inline`) — or `N/A — <reason>` for
  a feature with no user-facing surface. See `docs/frontend-page-guide.md`
  for choosing the surface.
- Five-dimension fit (D018): name which of business/user value, economic
  viability, UX/adoption, technical/operational quality, and adaptability
  the feature improves or puts at risk; prefer the simplest intervention.
- Scope in and out.
- Acceptance criteria table. Map each criterion to scenario tags.
- Decisions section. Write ADR-style entries.

Fill `specs/<feature>/DOMAIN.md` (D019) at the same checkpoint: declare the
tier (`simple | standard | domain-heavy`), the ubiquitous-language glossary
(one agreed term per concept, seeded from `discover_product`'s domain
vocabulary), the bounded contexts that own each concept with translation
points, aggregates and their invariants, the transaction boundary,
integration style, and external translations. `simple` still names its
owning context and states "no new domain concepts" explicitly. Gates
`G2 — Domain model captured` and `G3 — Experience contract filled` block
wave planning until both are filled; a bare `N/A` is rejected. `G4 — Scenario
maturity floor` (D020) also blocks planning: `EXAMPLES.feature` must cover the
five maturity axes with real `@m-<axis>` scenarios or reasoned
`Maturity N/A: @m-<axis> — <reason>` lines at the DOMAIN.md tier's depth.
Stage them as small waves: one new axis per `@w<N>` wave in a dedicated
scenario, with the happy path in its own scenario; do not bundle all axes in
one big-bang wave.

**Optional — challenge high-impact decisions.** When a decision is a
one-way door (data ownership, schema, public contract, service split,
security control) or the domain is contested, run `/challenge-decision`
before you plan waves.

The review is advisory (D011). It gives alternatives, a tradeoff matrix,
and a verdict. It does not block the pipeline. Record the outcome in the
Decisions section. If it changes a precondition, update `GATES.md`.

### Phase 4 — Examples (specifications by example)

Write Gherkin scenarios in `EXAMPLES.feature`. Rules:

- Each scenario describes observable behavior. Not implementation.
- Tag each scenario with `@w<N>` for its delivery wave **and** its single
  `@m-<axis>` scenario-maturity axis (D020): `@m-failure`, `@m-ownership`,
  `@m-data`, `@m-ux`, `@m-outcome`. One axis per scenario.
- Stage the value: one NEW axis per `@w<N>` wave, in a dedicated scenario,
  with the happy path in its own scenario. Several scenarios for the SAME axis
  in one wave are depth; several different axes in one wave are a big-bang
  iteration and fail G4 / `wave_plan` warnings.
- Cover the happy path and real-world cases that would fail a demo: retries,
  ownership, reload/persistence, error/empty states and an observable outcome.
  The DOMAIN.md tier sets the exercised-axis floor; an inapplicable axis
  needs `# Maturity N/A: @m-<axis> — <reason>` outside a scenario, never a
  bare `N/A`. Add a tag only when the scenario truly exercises that axis.
- Use scenario names as the spec's vocabulary. Tests must cite them.

### Phase 5 — Backlog + Waves

Add user stories to `BACKLOG.md`. Each item is a story, not a task:

```
## US<n> — As a <role>, I want <goal>, so that <value>
- Scenarios: @wN
- Depends: USk        (optional)
- Size: S|M|L
- Notes: <one line>
```

Order stories by user value. `Depends:` gives technical order only. Then
run:

```
`python -m openharness run wave_plan --spec_dir=sources/<repo>/specs/<feature>`
```

Review `WAVES.md`. Each wave must ship alone: one branch, one PR, green
tests. If a wave is too big or the dependencies are wrong, fix
`BACKLOG.md`. Do not write code yet.

Before planning waves, run the independent spec audit:

```
`python -m openharness run review_delivery --repo_path=sources/<repo> --spec_dir=sources/<repo>/specs/<feature> --phase=spec --write`
```

Hand the brief to **delivery-auditor**. It re-verifies every finding and
checks that the spec's paths, endpoints, and scenarios are grounded in the
repo. A `BLOCK` verdict stops the pipeline: fix the spec before writing
code. `PASS` or accepted `CONCERNS` continue.

### Phase 6 — Implement (waves are iterations)

Each wave is one iteration: a time-boxed increment with a demoable
result. Do the waves in order:

1. Inspect the merge state of earlier wave PRs. If the preceding wave PR is
   still open, branch from its head and target the new PR at that branch
   (stack it). If it has merged, branch from the default branch. Record the
   stacked PR and merge order; never base a dependent wave on a default
   branch that lacks its predecessor.
2. Write failing checks first for the wave's scenarios. The `.feature`
   scenarios are the acceptance spec.
3. Implement the smallest correct change. Match repo conventions (KISS).
4. Verify: build + tests green locally. Then CI green on the PR.
5. Open one PR. Merge per the merge policy (default: leave open for
   review). For stacked PRs, retarget/rebase descendants onto the default
   branch after their parent merges and rerun CI. Delete only the merged
   wave's branch after descendants no longer depend on it. Demo the result.
6. Record the wave: `ship_loop --action=complete`. `LOOP.md` holds the
   execution state. `WAVES.md` holds the plan.

### Phase 7 — Validate + Ship

Run the acceptance walkthrough:

```
`python -m openharness run ship_validate --spec_dir=sources/<repo>/specs/<feature> --repo_path=sources/<repo>`
```

`ship_validate` writes `VALIDATION.md`: the AC → scenario → wave → test
evidence matrix, coverage stats, a demo script, and a gaps list.

Walk the demo script by hand. Close real gaps: missing checks, unproven
scenarios. "No evidence found" means verify by hand. It does not prove
absence. Each `Before: finish` gate in `GATES.md` must be `met` or
`waived` before acceptance validation is complete. `ship_loop` status
`done` means the feature was acceptance-validated; it does not mean its PRs
were merged or the feature was deployed.

Run the independent delivery audit before calling the feature done:

```
`python -m openharness run review_delivery --repo_path=sources/<repo> --spec_dir=sources/<repo>/specs/<feature> --phase=delivery --write`
```

Hand the brief to **delivery-auditor**. It opens the cited tests, checks that
each acceptance criterion is proven by behavior (not just a matching name),
verifies changed contracts against the spec, and looks for scope drift. A
`BLOCK` verdict stops the pipeline; fix the delivery and re-audit.

Then:

1. Update `README.md` and `AGENTS.md`.
2. Refresh `specs/PRODUCT.md` with `product_map`.
3. Make sure `specs/<feature>/` tells the true story.
4. Record an optional `Outcome follow-up` in `VALIDATION.md`: observed
   signal/result, source, owner/date, and learning. If the feature is not
   released or the signal is unavailable, state that and leave the follow-up
   pending; it is not a finish gate.
5. Report acceptance status separately from PR merge/deployment status. When
   available, include actual elapsed time and review wait from recorded
   timestamps. Do not invent metrics or use them to rank teams.

## Agent execution and merge safeguards

- Read the target repo's `AGENTS.md` and layered `.openharness/ENV.md`;
  follow the active agent host's permission prompts and least-privilege
  settings. The harness protocol does not create an isolated sandbox.
- Do not broaden filesystem, network, or credential access to complete a
  wave. Never copy secrets into prompts, tests, specs, or PRs. Stop and ask
  for a human when required access is unavailable.
- `--merge=auto` is allowed only when branch protection and required CI and
  security checks are verified for the target branch. If their state cannot
  be confirmed, use `review` and hand off to a human.

## Rules

- Specs live in the repo under `specs/`. They are product artifacts. They
  must outlive any session. Do not put them in `.openharness/context/`.
- Ship one feature at a time. Do not stack unmerged spec dirs.
- A wave without failing-tests-first is not a wave.
- Never commit to the default branch. Every wave is a PR.
- If `wave_plan` reports dependency cycles or missing deps, fix
  `BACKLOG.md` before you write code.
