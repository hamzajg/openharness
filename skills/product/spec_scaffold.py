"""Scaffold a spec-driven feature directory: SPEC.md + EXAMPLES.feature + BACKLOG.md + GATES.md.

Creates specs/<feature>/ inside the target repo with four artifacts:
- SPEC.md — the spec driver (problem, users, scope, out-of-scope, acceptance criteria)
- EXAMPLES.feature — specifications by example (Gherkin scenarios, tagged @w<N>)
- BACKLOG.md — ordered work items referencing scenario tags and dependency hints
- GATES.md — preconditions for phase transitions (status lives in LOOP.md)

The agent fills the templates; this skill only writes deterministic skeletons
so the artifact contract is identical across repos. Deterministic file writer.
"""

import re
from pathlib import Path

from openharness.skill import skill

_SPEC_MD = """# Spec: {title}

> Spec-driven development artifact. This file is the contract: implementation
> is done when every acceptance criterion maps to a scenario in
> `EXAMPLES.feature` and every scenario has a passing check.

## Problem

{problem}

## Users

{users}

## Outcome hypothesis

- Expected user outcome: (what user behavior or problem should change?)
- Opportunity evidence: (source; if unknown, state that this is an assumption)
- Signal: (observable measure and baseline if known; do not invent targets)
- Follow-up owner/date: (who will review the signal and when?)

## Scope (in)

-

## Scope (out)

-

## Acceptance criteria

<!-- Scenario(s): use scenario names verbatim from EXAMPLES.feature and/or
     @w<N> tags — ship_validate resolves both for traceability. -->

| # | Criterion | Scenario(s) |
|---|-----------|-------------|
| 1 |             | @w1         |

## Decisions

<!-- One block per decision. Every one-way-door or high-impact choice
     (persistence model, consistency guarantees, module/service boundaries,
     stateless vs stateful design, public contracts — REST/OpenAPI,
     events/AsyncAPI or schema registry, gRPC/protobuf IDL — and their
     documentation, security controls, framework vs custom mechanism)
     MUST record:
       - Context & forces: what drives the choice, what breaks without it
       - Options considered: at least two credible options, INCLUDING the
         simplest one and the most reversible one
       - Decision & why: the choice and the decisive tradeoff
       - Consequences: positive AND negative
       - Reversibility: one-way or two-way door; revisit trigger if known
     These feed `challenge_decision` — the review brief scores exactly
     this shape. -->

- (record ADR-style choices here as they are made)
"""

_FEATURE = """# {title} — specifications by example
# Scenario tags @w<N> map items to delivery waves (see WAVES.md / BACKLOG.md).

Feature: {title}

  @w1 @happy-path
  Scenario: {scenario_name}
    Given {given}
    When {when}
    Then {then}
"""

_BACKLOG_MD = """# Backlog: {title}

Items are USER STORIES in the parseable format below — keep the heading
shape `## US<n> — <story>` and the field lines intact so `wave_plan` can
parse them. Write the story as: "As a <role>, I want <goal>, so that
<value>" — the title after the dash IS the story.

```
## US<n> — As a <role>, I want <goal>, so that <value>
- Scenarios: @w1, @w2
- Depends: US1, US3        (optional; omit for wave-1 items)
- Size: S|M|L
- Notes: <one line>
```

Order stories by user value; dependencies express technical order only.

<!-- Replace this comment with your stories, highest value first, e.g.
     (indented so the example itself is never parsed as a real story)
       ## US1 — As an editor, I want to save a draft, so that work survives reload
       - Scenarios: @w1
       - Size: M
       - Notes: <one line>

     Until a real story exists `wave_plan` refuses to plan: a scaffold must
     never be mistaken for an approved backlog.
-->
"""

_GATES_MD = """# Gates: {title}

> Preconditions for phase transitions. Each `## G<n> — <title>` block is a
> gate. `ship_loop` refuses to advance past a phase while a blocking gate is
> pending. Definitions live here; status and evidence live in `LOOP.md`.
>
> Gate phases: `spec` (before writing the spec), `plan` (before planning
> waves), `wave:<n>` (before starting wave n), `validate` (before validation),
> `finish` (before closing the feature).
>
> Gate types: decision | artifact | external | technical | quality | data.
> Resolver: `human` (needs a person to decide/provide something) or `agent`
> (the agent can satisfy it). Check: `manual`, `file:<repo-relative-path>`, or
> `command:<exact command>` (the agent runs it and records the output as
> evidence — the oracle never executes it).

<!-- Example (indented so it is not parsed):
  ## G1 — Domain glossary agreed
  - Before: spec
  - Type: decision
  - Owner: product-owner
  - Resolver: human
  - Blocking: yes
  - Check: manual
  - Why: AC-2 and AC-3 use domain terms that must be defined once.
-->

## G1 — Design decisions challenged
- Before: plan
- Type: artifact
- Owner: agent
- Resolver: agent
- Blocking: yes
- Check: file:specs/{slug}/DECISION-REVIEW.md
- Why: Every wave inherits the feature's architecture choices (persistence
  model, consistency, module boundaries, stateless vs stateful). The
  challenger review — alternatives, tradeoffs, testability — must exist
  before wave planning locks the design in. A human may waive this gate
  for genuinely trivial features.
"""


def _slug(feature: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", feature.strip().lower()).strip("-")
    return slug or "feature"


@skill
def spec_scaffold(repo_path: str = ".", feature: str = "", output_dir: str = "specs") -> str:
    """Create specs/<feature>/ with SPEC.md, EXAMPLES.feature, BACKLOG.md, GATES.md skeletons.

    Writes four artifacts into <repo_path>/<output_dir>/<feature-slug>/.
    Never overwrites an existing file. The agent fills the placeholders; keep
    the section headers and tag conventions intact so `wave_plan` can parse
    BACKLOG.md later.

    Params:
      repo_path: Repository root.
      feature: Feature name (kebab-cased into the directory name).
      output_dir: Specs root inside the repo (default "specs").
    """
    root = Path(repo_path).resolve()
    if not root.is_dir():
        return f"ERROR: {repo_path} is not a directory"
    if not feature.strip():
        return "ERROR: feature name is required"

    slug = _slug(feature)
    title = feature.strip()
    spec_dir = root / output_dir / slug
    spec_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "SPEC.md": _SPEC_MD.format(
            title=title,
            problem="(one paragraph: what hurts today, for whom)",
            users="(primary user persona(s))",
        ),
        "EXAMPLES.feature": _FEATURE.format(
            title=title,
            scenario_name="(name the first happy-path scenario)",
            given="(precondition)",
            when="(action)",
            then="(observable outcome)",
        ),
        "BACKLOG.md": _BACKLOG_MD.format(
            title=title,
            first_item="(first user-facing capability)",
            first_value="(the user outcome it enables)",
        ),
        "GATES.md": _GATES_MD.format(title=title, slug=slug),
    }

    written, skipped = [], []
    for name, content in files.items():
        path = spec_dir / name
        if path.exists():
            skipped.append(name)
            continue
        path.write_text(content)
        written.append(str(path.relative_to(root)))

    out = [f"# Spec scaffold — {slug}", ""]
    out.append(f"Directory: `{spec_dir.relative_to(root)}/`")
    for w in written:
        out.append(f"- created `{w}`")
    for s in skipped:
        out.append(f"- kept existing `{s}`")
    out.append("")
    out.append("Next: fill SPEC.md (problem/users/scope/AC table), write real")
    out.append("Gherkin scenarios in EXAMPLES.feature with @w<N> tags, add")
    out.append("backlog items to BACKLOG.md, define preconditions in GATES.md,")
    out.append("then run `wave_plan`.")
    return "\n".join(out)
