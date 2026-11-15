# ADR 0005 — Optional design-decision review

Status: accepted · 2026-11-15 · decision D011

## Context

The delivery loop (ADR 0003) and its gates (ADR 0004) make *what* must be
decided explicit and stop the loop on missing preconditions. They do not
challenge *how* a decision is made. For complex domains the expensive mistakes
are design mistakes: a boundary drawn in the wrong place, an aggregate split
across transactions, a framework leaking into the domain, a public contract
with no versioning, a test suite with no seams.

These are not binary preconditions, so a gate is the wrong tool. They are
judgment calls that benefit from a structured challenge: alternatives,
tradeoffs, domain fit, testability, reversibility, and the smallest reversible
step. Making them blocking would give a reviewer veto power and turn the loop
into ceremony.

## Decision

Add an **optional, advisory** decision review:

1. **Deterministic brief** — `skills/product/challenge_decision.py`. It reads a
   decision from an ADR, a spec's `## Decisions`, or inline text, then reports:
   - record completeness (context, decision, alternatives, consequences,
     forces, evidence) and a readiness hint;
   - reversibility and detected decision type;
   - heuristic code signals (framework/IO in domain paths, missing tests,
     getter/setter-heavy models, domain-event/invariant vocabulary, repo
     layout), explicitly labelled as heuristics;
   - neutral design moves and lens questions with "good looks like" criteria;
   - a scorecard and verdict block for the agent.
2. **Semantic review** — `/challenge-decision` and the `decision-challenger`
   subagent. It steelmans the decision, generates at least two credible
   alternatives, builds a tradeoff matrix, applies the lenses, scores only with
   evidence, and returns `ACCEPT`/`REVISE`/`REVISIT`/`SPLIT` plus the smallest
   next step and a revisit trigger.
3. **Artifact** — `specs/<feature>/DECISION-REVIEW.md` or
   `<adr>-review.md`. It is a snapshot; the ADR/spec remains the source of
   truth.

The review is never a gate: it cannot block a wave, a merge, or the loop. It
writes only review documents, never product code.

## Consequences

- Complex, one-way-door decisions get a rigorous challenge while the cost of
  change is still low, without adding a veto.
- The deterministic brief keeps the review grounded: missing record elements
  and code signals are surfaced before the agent opines.
- The skill judges record completeness, not design quality; the agent judges
  design, and only with evidence. `unverified` is an honest score.
- Backwards compatible: features that never run it are unaffected.
- Cost: one skill, one command, one subagent role, and a review document when
  used. The risk is ceremony — so the command says explicitly when *not* to run
  it.
