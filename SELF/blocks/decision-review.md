---
name: decision-review
type: block
location: skills/product/challenge_decision.py, .opencode/commands/challenge-decision.md, .claude/commands/challenge-decision.md, .opencode/agents/decision-challenger.md, .claude/agents/decision-challenger.md
interfaces: [challenge_decision.invoke]
---
# Block: decision-review

## Purpose
Reviews one design/architecture decision to **discover the better design**
before it becomes expensive. Its verdict is advisory and never a gate
(D011). The review *artifact* is different: `spec_scaffold` emits a
blocking `Before: plan` gate (`G1 — Design decisions challenged`,
`Check: file:specs/<feature>/DECISION-REVIEW.md`) so the review must exist
before wave planning; the verdict still does not block. The `file:` gate
requires a completed verdict block — a single-value `VERDICT:` plus
substantive `STEELMAN:`, `SMALLEST NEXT STEP:` and `REVISIT TRIGGER:`
entries — the deterministic template's `VERDICT: ACCEPT | REVISE |
REVISIT | SPLIT` alternation and `<...>` placeholders do not count.

Two halves:

1. **Deterministic brief** — `skills/product/challenge_decision.py`. Parses a
   decision from an ADR, a spec's `## Decisions`, or inline text; checks the
   record's completeness; scans referenced code for heuristic design signals;
   emits design moves, lens questions, a scorecard, and a verdict block.
2. **Semantic review** — `/challenge-decision` + the `decision-challenger`
   subagent. Steelmans the decision, generates credible alternatives, builds a
   tradeoff matrix, applies the lenses, scores with evidence, and writes a
   review file.

## Inputs
One source is required:

- `--adr=<path>` — a decision record (relative to the repo or absolute);
- `--spec_dir=<dir>` — reads the `## Decisions` section of `SPEC.md`;
- `--decision="<text>"` — inline, when no artifact exists yet.

Optional: `--paths="<a,b>"` code paths to inspect; `--write` to persist the
brief; `--force` to overwrite an existing review.

## What the brief contains
- **Readiness** (`INCOMPLETE` / `CHALLENGE` / `READY`) from six record
  elements: context, decision, alternatives (≥2), consequences, forces,
  evidence. This is record quality, **not** design quality.
  - Alternatives come from an `## Alternatives`/`## Options considered`
    section, or from conservative prose detection (`Options were A vs. B`);
    rhetorical "rather than" does not count.
  - For a spec, `## Scope (out)` / `## Non-goals` counts as the
    consequence record — the spec's way of naming what the decision excludes.
- **Reversibility** — stated or not; one-way doors get more scrutiny.
- **Detected type** — architecture, data, api, persistence, integration,
  security, domain, ux, process — which selects extra questions and moves.
- **Evidence signals** — labelled heuristic: framework/IO in domain code,
  missing tests, getter/setter-heavy models, domain-event/invariant
  vocabulary, repo layout. Paths inferred from backticks are code paths only;
  a decision that cites only markdown is reported as document-only. A
  non-domain path is reported as inspected-but-not-layering-checked, so the
  reviewer knows it was examined.
- **Design moves** — neutral moves to test (invert a dependency, shrink the
  decision, separate read/write shapes, introduce an ACL).
- **Challenge questions** across seven lenses, each with "good looks like".
- **Scorecard + verdict block** — filled by the agent, never by the skill.

## Lenses
1. Problem & forces
2. Alternatives & tradeoffs
3. Domain fit (DDD): bounded context, ubiquitous language, aggregates,
   invariants, consistency boundary, domain events, anti-corruption layer.
4. Architecture & boundaries: dependency direction, ports/adapters, smallest
   boundary, failure modes, data ownership, migration/rollback.
5. Testable design: seams, deterministic time/IO, unit vs integration vs
   contract tests, scenario→test traceability, production failure signal.
6. Craftsmanship: smallest reversible step, names, error model, no
   speculative abstraction.
7. Decision record: status/owner/date, consequences, revisit trigger, links.

## Verdicts
`ACCEPT` · `REVISE` (smallest next step) · `REVISIT` (evidence missing) ·
`SPLIT` (bundled decisions). The review file is a snapshot; the ADR/spec
remains the source of truth.

## Invariants
- Advisory only: never blocks a gate, wave, merge, or loop iteration.
- The skill judges **record completeness**, not design; the agent judges
  design, and only with evidence.
- Heuristic signals are labelled and must be verified; absence of a signal is
  not proof.
- The review writes only under `specs/` or `docs/adr/`; it never edits product
  code, tests, build files, or CI.
- `unverified` is an acceptable score; confident guesses are not.

## How to Extend
1. New deterministic checks go in `challenge_decision.py` and get a test in
   `tests/test_challenge_decision.py`; keep them language-light and label
   them as heuristics.
2. New lenses or design moves are constants in the same file; keep each lens
   falsifiable ("good looks like", not "is elegant").
3. The agent contract lives in the command and subagent; mirror every change
   to `.claude/`.
4. Keep the verdict advisory — the scaffold gate requires the artifact to
   exist, it does not judge the verdict. If a verdict ever needs to block,
   that is a gate (`GATES.md`), not this block.
