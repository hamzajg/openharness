---
description: Challenge a design/architecture decision — steelman, alternatives, tradeoffs, DDD/architecture/testability/craftsmanship review, then ACCEPT/REVISE/REVISIT/SPLIT
allowed-tools: [Bash, Read, Grep, Glob, Edit, Write, Task]
---
# /challenge-decision — Review a decision before it becomes expensive

Advisory design review — the verdict never blocks a gate, a wave, or a
merge. Inside `/ship-loop` the review *artifact* is mandatory, though:
every feature's `GATES.md` carries a blocking `Before: plan` gate that
requires `DECISION-REVIEW.md` before wave planning, and any new
one-way-door decision a wave introduces must be challenged before coding.

Arguments (`$ARGUMENTS`), all optional but one source is required:

| Arg | Meaning |
|---|---|
| `--repo=sources/<repo>` | Target repo (default: cwd inside `sources/`) |
| `--adr=<path>` | Decision record to review (e.g. `docs/adr/0007-order-store.md`) |
| `--spec=sources/<repo>/specs/<feature>` | Read the spec's `## Decisions` section |
| `--decision="<text>"` | Inline decision, when no file exists yet |
| `--paths=<a,b>` | Code paths to inspect for design signals |
| `--focus=<lens>` | Optional: bias the review (ddd, architecture, testability, craft) |

## When to use it

- Inside `/ship-loop`: once per feature (gate `G1`) before wave planning,
  and again whenever a wave introduces a new one-way-door decision.
- A decision is a **one-way door** (schema, public contract, data ownership,
  service split, security control).
- The domain is complex enough that business rules and language are contested.
- The team disagrees, or the decision is being made under schedule pressure.
- Before planning waves, when a spec records an architecture/data/integration
  decision that every wave will inherit.

Do **not** run it on every small choice. A review that fires constantly
becomes ceremony and stops being read.

## Context

Run and read:
- `python -m openharness self`
- `python -m openharness env`

## Procedure

1. **Resolve the source.** Exactly one of `--adr`, `--spec`, `--decision`.
   If the user gave a topic but no artifact, ask for the decision text — do
   not invent one. If `--spec` is a repo path, the skill expects the feature
   dir (`.../specs/<feature>`), not the repo root.

2. **Build the deterministic brief.**
   ```
   python -m openharness run challenge_decision --repo_path=<repo> \
     --adr=<path> --paths="<paths>" --focus="<lens>" --write
   ```
   (or `--spec_dir=<feature>` / `--decision="<text>"`). The brief contains:
   record completeness and readiness, heuristic code signals, design moves,
   lens questions, a scorecard, and a verdict block. Read it before reviewing
   — it tells you what is missing and what to inspect.

3. **Delegate the judgment.** Hand the repo, source, brief, and `--focus` to
   the **decision-challenger** subagent. It must:
   - steelman the decision first;
   - produce at least two credible alternatives (including the simplest and a
     smaller reversible step);
   - build a tradeoff matrix that names winners and losers;
   - apply the DDD, architecture, testability, and craftsmanship lenses;
   - score only with evidence, and fill the review file.

4. **Verify, don't rubber-stamp.** Read the subagent's alternatives and scores.
   If a score has no evidence, downgrade it to `unverified`. If the review
   recommends a change, make sure it names the **smallest next step**, not a
   rewrite.

5. **Persist the review.** The review lives next to the decision:
   `specs/<feature>/DECISION-REVIEW.md` or `<adr>-review.md`. If the decision
   changes, update the ADR/spec — the review is a snapshot, not the source of
   truth.

6. **Report** using the contract below.

## Output contract

```
DECISION: <title>
SOURCE: <path or inline>
VERDICT: ACCEPT | REVISE | REVISIT | SPLIT
WHY: <the decisive tradeoff in one or two sentences>
ALTERNATIVES: <count + the one that came closest>
SMALLEST NEXT STEP: <one change>
REVISIT TRIGGER: <metric, date, or event>
REVIEW: <path>
LOOP IMPACT: none (advisory) | <if the decision changes, which spec/gate to update>
```

## Relationship to the delivery loop

- **Artifact required, verdict advisory.** `spec_scaffold` writes gate
  `G1` (`Before: plan`, `Check: file:specs/<feature>/DECISION-REVIEW.md`)
  into every feature — the loop refuses wave planning and wave 1 until the
  review file exists. The verdict itself (`ACCEPT` / `REVISE` / `REVISIT` /
  `SPLIT`) stays advisory (D011): it informs the spec and backlog but never
  blocks a merge.
- **Value, economics & sustainability lens (D017/D018).** The brief asks for
  the value gap, who bears today's cost, a numeric target and window,
  build/operate/adopt lifecycle cost, an adoption signal, and the five
  dimensions' quality tradeoffs (business/user value, economic viability,
  UX/adoption, technical/operational quality, adaptability). Like every
  lens, it is advisory: score it with evidence, never turn it into a gate or
  a score.
- **Before planning waves** is the best moment for high-impact decisions: the
  cost of changing direction is still low.
- **If the review says REVISIT or SPLIT**, record the decision change in
  `SPEC.md` → Decisions and, if it affects a precondition, update `GATES.md`.
  Then continue with `/ship-loop` or `/ship-product`.
- **If the review says REVISE**, the smallest next step may become a backlog
  item or a new wave — record it; do not silently implement it during review.

## Guardrails

- One decision per review. If the decision bundles independent choices, use
  `SPLIT` and review them separately.
- Never edit product code, tests, build files, or CI during the review.
- Never fabricate evidence or precision. `unverified` beats a confident guess.
- Do not turn the review into a style debate; judge design against the stated
  forces and the domain, not personal preference.
- Do not launch subagents from the decision-challenger; the orchestrator owns
  delegation.
