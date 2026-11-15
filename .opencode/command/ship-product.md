---
description: Take a managed repo from "code exists" to "product ships" — discover gaps, frame ONE innovative feature, spec it (spec-driven), write specifications-by-example, plan delivery waves, implement wave by wave
---
# /ship-product — Spec-driven product completion, wave by wave

> Want the same pipeline driven autonomously? Use `/ship-loop` — the oracle
> (`ship_loop`) walks these phases and delegates to focused subagents.

## Context

Run via Bash and read output:
- `python -m openharness self`
- `python -m openharness env`

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
python -m openharness run discover_product --repo_path=sources/<repo>
```
Read the Product Surface Report. Also read README, AGENTS.md, and any
existing `specs/` dirs. Identify: what the product IS today, what is
stubbed (placeholder markers), what routes/features exist but are thin.

### Phase 2 — Frame (feature planning)
Propose 3–5 candidate feature themes that move the repo toward a
shippable product. Score each: user value × feasibility × differentiation.
Present the shortlist and get user buy-in on ONE feature before speccing.
An innovative feature for a kata/legacy repo usually means: the missing
loop that makes it a product (persistence, auth, notifications, export,
real data source) — not a new framework.

For multi-feature planning, keep the product map current:
```
python -m openharness run product_map --repo_path=sources/<repo>
```
It writes `specs/PRODUCT.md` — every feature's stories/scenarios/waves/
validation state in one table. Sequence features by dependency and user
value; ship ONE at a time.

### Phase 3 — Spec (spec driver)
```
python -m openharness run spec_scaffold --repo_path=sources/<repo> --feature="<name>"
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
Add USER STORIES to `BACKLOG.md` — each item is a story, not a task:
`## US<n> — As a <role>, I want <goal>, so that <value>` with
`- Scenarios: @wN`, optional `- Depends: USk`, `- Size:`, `- Notes:`.
Order by user value; `Depends:` expresses technical order only. Then:
```
python -m openharness run wave_plan --spec_dir=sources/<repo>/specs/<feature>
```
Review `WAVES.md`. Each wave must be independently shippable: one branch,
one PR, tests green. Rebalance if a wave is too big or deps are wrong.

### Phase 6 — Implement (iterations = waves)
Each wave in WAVES.md IS an iteration: a time-boxed increment with a
demoable outcome. For each wave, in order:
1. Branch `feat/<feature>-w<N>` from the default branch.
2. Write failing checks FIRST for that wave's scenarios (SBE: the
   .feature scenarios are the acceptance spec; implement until they pass).
3. Implement minimally — KISS, match repo conventions.
4. Verify: build + tests green locally, then CI on the PR.
5. Merge, delete branch, demo the iteration outcome, mark wave done in
   WAVES.md (commit the marker).

### Phase 7 — Validate + Ship
Run the acceptance walkthrough:
```
python -m openharness run ship_validate --spec_dir=sources/<repo>/specs/<feature> --repo_path=sources/<repo>
```
It writes `VALIDATION.md`: AC → scenario → wave → test-evidence matrix,
coverage stats, a manual demo script, and a gaps list. Walk the demo
script by hand. Close real gaps (missing checks, unproven scenarios)
before declaring done — "no evidence found" is a prompt to verify, not
proof of absence.

Then: update README/AGENTS.md, refresh `specs/PRODUCT.md` via
`product_map`, ensure `specs/<feature>/` tells the true story, and
report what shipped vs what remains.

## Rules
- Specs live in the repo (`specs/`), not in `.openharness/context/` —
  they are product artifacts that outlive any session.
- One feature at a time. Do not stack unmerged spec dirs.
- A wave without a failing-test-first check is not a wave.
- Never commit to the default branch; every wave is a PR.
- If `wave_plan` reports dependency cycles or missing deps, fix
  BACKLOG.md before writing code.
