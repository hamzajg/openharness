---
description: Take a managed repo from "code exists" to "product ships" — discover gaps, frame ONE innovative feature, spec it (spec-driven), write specifications-by-example, plan delivery waves, implement wave by wave
allowed-tools: [Bash, Read, Grep, Edit, Write]
---
# /ship-product — Spec-driven product completion, wave by wave

## Context
!`python -m openharness self`
!`python -m openharness env`

## Target repo
If the session cwd is inside sources/<repo>, that repo is the default
target. Otherwise ask the user which managed repo to operate on
(see REPOS.md). Never guess. All spec artifacts live INSIDE the target
repo under `specs/` — they are product content, committed via PRs.

## Layered ENV
If sources/<repo>/.openharness/ENV.md exists, prefer it over the global
.openharness/ENV.md for that repo.

## The pipeline (do not skip phases)

### Phase 1 — Discover (facts, not opinions)
```
!`python -m openharness run discover_product --repo_path=sources/<repo>`
```
Read the Product Surface Report. Also read README, AGENTS.md, and any
existing `specs/` dirs. Identify: what the product IS today, what is
stubbed (placeholder markers), what routes/features exist but are thin.

### Phase 2 — Frame (ONE feature)
Propose 3–5 candidate feature themes that move the repo toward a
shippable product. Score each: user value × feasibility × differentiation.
Present the shortlist and get user buy-in on ONE feature before speccing.
An innovative feature for a kata/legacy repo usually means: the missing
loop that makes it a product (persistence, auth, notifications, export,
real data source) — not a new framework.

### Phase 3 — Spec (spec driver)
```
!`python -m openharness run spec_scaffold --repo_path=sources/<repo> --feature="<name>"`
```
Fill `specs/<feature>/SPEC.md`: problem, users, scope in/out, acceptance
criteria table mapping each criterion to scenario tags. Record decisions
in the Decisions section as ADR-style entries.

### Phase 4 — Examples (specifications by example)
Write real Gherkin scenarios in `EXAMPLES.feature`. Rules:
- Every scenario is observable behavior, not implementation.
- Tag each with `@w<N>` matching its delivery wave.
- Cover happy path + the 2–3 edge cases that would embarrass a demo.
- Scenario names are the spec's executable vocabulary — tests cite them.

### Phase 5 — Backlog + Waves
Add backlog items to `BACKLOG.md` in the parseable format shown there
(`## B<n> — title`, `- Scenarios:`, `- Depends:`, `- Size:`), then:
```
!`python -m openharness run wave_plan --spec_dir=sources/<repo>/specs/<feature>`
```
Review `WAVES.md`. Each wave must be independently shippable: one branch,
one PR, tests green. Rebalance if a wave is too big or deps are wrong.

### Phase 6 — Implement (wave by wave)
For each wave, in order:
1. Branch `feat/<feature>-w<N>` from the default branch.
2. Write failing checks FIRST for that wave's scenarios (SBE: the
   .feature scenarios are the acceptance spec; implement until they pass).
3. Implement minimally — KISS, match repo conventions.
4. Verify: build + tests green locally, then CI on the PR.
5. Merge, delete branch, mark wave done in WAVES.md (commit the marker).

### Phase 7 — Ship
When all waves merge: update README/AGENTS.md to describe the feature,
ensure `specs/<feature>/` tells the true story (mark superseded decisions),
and report what shipped vs what remains.

## Rules
- Specs live in the repo (`specs/`), not in `.openharness/context/` —
  they are product artifacts that outlive any session.
- One feature at a time. Do not stack unmerged spec dirs.
- A wave without a failing-test-first check is not a wave.
- Never commit to the default branch; every wave is a PR.
- If `wave_plan` reports dependency cycles or missing deps, fix
  BACKLOG.md before writing code.
