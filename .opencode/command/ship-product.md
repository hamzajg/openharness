---
description: Take a managed repo from "code exists" to "product ships" — discover gaps, frame ONE innovative feature, spec it (spec-driven), write specifications-by-example, plan delivery waves, implement wave by wave
---
# /ship-product — Spec-driven product completion

> For autonomous delivery, use `/ship-loop`. The oracle (`ship_loop`)
> walks these phases and delegates to subagents.

## Context

Run via Bash and read output:
- `python -m openharness self`
- `python -m openharness env`

## Target repo

- If the cwd is inside `sources/<repo>`, that repo is the target.
- Otherwise, ask the user which managed repo to use. See REPOS.md. Do not
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

### Phase 2 — Frame (feature planning)
Propose 3–5 candidate features. Each must move the repo toward a
shippable product. Score each on three axes: user value, feasibility,
differentiation.

Show the shortlist to the user. Get approval for ONE feature before you
write the spec.

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
- Scope in and out.
- Acceptance criteria table. Map each criterion to scenario tags.
- Decisions section. Write ADR-style entries.

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
- Tag each scenario with `@w<N>` for its delivery wave.
- Cover the happy path and the 2–3 edge cases that would fail a demo.
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

### Phase 6 — Implement (waves are iterations)

Each wave is one iteration: a time-boxed increment with a demoable
result. Do the waves in order:

1. Branch `feat/<feature>-w<N>` from the default branch.
2. Write failing checks first for the wave's scenarios. The `.feature`
   scenarios are the acceptance spec.
3. Implement the smallest correct change. Match repo conventions (KISS).
4. Verify: build + tests green locally. Then CI green on the PR.
5. Open one PR. Merge per the merge policy (default: leave open for
   review). Delete the branch after merge. Demo the result.
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
`waived` before you declare the feature shipped.

Then:

1. Update `README.md` and `AGENTS.md`.
2. Refresh `specs/PRODUCT.md` with `product_map`.
3. Make sure `specs/<feature>/` tells the true story.
4. Report what shipped and what remains.

## Rules

- Specs live in the repo under `specs/`. They are product artifacts. They
  must outlive any session. Do not put them in `.openharness/context/`.
- Ship one feature at a time. Do not stack unmerged spec dirs.
- A wave without failing-tests-first is not a wave.
- Never commit to the default branch. Every wave is a PR.
- If `wave_plan` reports dependency cycles or missing deps, fix
  `BACKLOG.md` before you write code.
