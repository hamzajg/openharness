"""Scaffold a spec-driven feature directory: SPEC.md + EXAMPLES.feature + BACKLOG.md + GATES.md.

Creates specs/<feature>/ inside the target repo with five artifacts:
- SPEC.md — the spec driver (problem, users, scope, value/experience contracts)
- EXAMPLES.feature — specifications by example (@w<N> waves + @m-<axis> maturity)
- DOMAIN.md — tier, ubiquitous language, contexts, aggregates, invariants (D019)
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

## Value contract

Required before wave planning (D017). Fill every field. Keep the target
measurable — a number, a unit, and a review window.

- Problem: (severity, frequency; what hurts today)
- Users: (who bears the cost, who benefits)
- Baseline / current cost: (observable starting point: time, money, effort, or risk)
- Target outcome indicator: (metric + numeric target + review window, e.g. p95 below 300ms in 30 days)
- Economic hypothesis: (why the value justifies build, operate, adopt, and migrate cost over 3 years)
- Owner / date: (who reviews the signal and when)

## Outcome hypothesis

- Expected user outcome: (what user behavior or problem should change?)
- Opportunity evidence: (source; if unknown, state that this is an assumption)
- Signal: (observable measure and baseline if known; do not invent baselines; target lives in the Value contract)
- Follow-up owner/date: (who will review the signal and when?)

## Experience

<!-- Required for any user-facing surface (D019). A feature with no user
    -facing surface writes `N/A — <reason>`; a bare N/A is rejected. -->

- Primary journey: (the ordered steps the primary user takes)
- Edge states: (empty / loading / error / permission-denied states that matter)
- UX bar: (what "intuitive" concretely means for this feature)
- Accessibility: (keyboard / screen-reader / contrast notes, or n/a — reason)
- UI pattern: (F-pattern | Z-pattern | single-column; optional `— rationale`; per tier: simple declares Z‑pattern implicit or F/Z; standard names the pattern; domain-heavy references the standard)
- Navigation/overlay: (full-page | side-pane | modal | inline; add `— rationale` for why this surface over the alternatives; per tier: standard explains the choice, domain-heavy cites the standard)

## Scope (in)

-

## Scope (out)

-

## Acceptance criteria

<!-- Scenario(s): use scenario names verbatim from EXAMPLES.feature and/or
     @w<N> tags — ship_validate resolves both for traceability. A numbered
     list is allowed under this heading, but every item must still name its
     scenario(s) or @w<N> tag inline. -->

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

_DOMAIN_MD = """# Domain model: {title}

> The domain contract for this feature (D019): ubiquitous language,
> bounded contexts, aggregates and invariants. Fill every section. `simple`
> tier means the feature introduces no NEW domain concepts — say so
> explicitly and name the owning context; it is not a blank file. Deeper
> tiers are checked semantically by the spec audit and wave reviewer.

**Tier:** simple | standard | domain-heavy

## Ubiquitous language

<!-- One entry per term this feature introduces or relies on. Use the SAME
     words in scenarios, stories, code and UI copy. -->

- (term: meaning — used in scenario/story/API/screen)

## Bounded contexts

<!-- Which context owns each concept; where translation is needed. -->

- (owning context and the concepts it owns)
- (context map: dependencies between contexts, ACL/translation points)
- (new concepts introduced, or "none — all terms borrowed from <context>")

## Domain model

<!-- Only what this feature needs. Invariants are enforced at the boundary. -->

- (aggregates and their invariants)
- (entities / value objects this feature adds or changes)
- (transaction boundary: what commits together; does one span aggregates?)

## Integration style

<!-- How this feature's context talks to the rest of the system. -->

- (domain events vs synchronous calls, and why)
- (what must be strongly consistent vs may be eventual)

## External translations

<!-- External systems/models entering this context and how they are
     translated — or an explicit "none". -->

- (external system/model and its translation, or "none — <reason>")
"""

_FEATURE = """# {title} — specifications by example
# Scenario tags @w<N> map items to delivery waves (see WAVES.md / BACKLOG.md).
# Scenario maturity (D020): examples must cover real-world behavior, not only
# a happy-path demo. Tag a REAL Scenario with one or more axes below:
#   @m-failure   idempotency, retry/timeout, partial failure, stale/conflict
#   @m-ownership roles, ownership, tenant isolation, revocation, audit trail
#   @m-data      persistence, migration, import/export, search/pagination
#   @m-ux        empty/loading/error/permission-denied/offline, undo, a11y
#   @m-outcome   observable signal tied to the value-contract target
# For an axis that genuinely does not apply, write OUTSIDE a Scenario:
#   # Maturity N/A: @m-ownership — anonymous tool, no auth boundary
# The DOMAIN.md tier sets the floor: simple needs 2 covered axes, standard
# needs 3 including failure, domain-heavy needs all axes covered or justified.
# Baby steps: one new maturity axis per wave; the happy path gets its own
# scenario. A wave may hold several scenarios for the SAME axis, never
# several different axes in one big iteration.

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
> (the agent can satisfy it). Check: `manual`, `file:<repo-relative-path>`,
> `section:<repo-relative-path>#<heading>` (the named `##` section must be
> filled — used for SPEC.md sections that need their own contract), or
> `command:<exact command>` (the agent runs it and records the output as
> evidence — the oracle never executes it).

## G0 — Value contract filled
- Before: plan
- Type: artifact
- Owner: agent
- Resolver: agent
- Blocking: yes
- Check: file:specs/{slug}/SPEC.md
- Why: D017 — value is the outcome, not the output. Problem, users, baseline,
  measurable target, economic hypothesis and review owner must be on record
  before wave planning commits the features.

<!-- Example (indented so it is not parsed):
  ## G5 — Pricing rules approved
  - Before: spec
  - Type: decision
  - Owner: product-owner
  - Resolver: human
  - Blocking: yes
  - Check: manual
  - Why: AC-2 and AC-3 use pricing terms that must be defined once.
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
  challenger review — alternatives, tradeoffs, testability, and a filled
  VERDICT — must exist before wave planning locks the design in. A human may
  waive this gate for genuinely trivial features.

## G2 — Domain model captured
- Before: plan
- Type: artifact
- Owner: agent
- Resolver: agent
- Blocking: yes
- Check: file:specs/{slug}/DOMAIN.md
- Why: D019 — waves inherit the ubiquitous language, bounded contexts,
  aggregates and invariants declared here. The file must name its tier
  (simple|standard|domain-heavy) and fill every section; `simple` still
  names the owning context and states "no new domain concepts" explicitly.

## G3 — Experience contract filled
- Before: plan
- Type: artifact
- Owner: agent
- Resolver: agent
- Blocking: yes
- Check: section:specs/{slug}/SPEC.md#Experience
- Why: D019 — user-facing features must name the primary journey, edge
  states, a concrete UX bar, accessibility notes, a UI pattern and a
  navigation surface (full-page | side-pane | modal | inline) before
  planning. A feature with no user-facing surface writes `N/A — <reason>`;
  a bare N/A is rejected.

## G4 — Scenario maturity floor
- Before: plan
- Type: artifact
- Owner: agent
- Resolver: agent
- Blocking: yes
- Check: file:specs/{slug}/EXAMPLES.feature
- Why: D020 — happy-path-only examples pass traceability while proving
  nothing about real-world operation. Cover failure/recovery, auth/ownership,
  data/integration and user-visible edge states with @m-<axis> scenarios
  tied to @w<N>, or justify each inapplicable axis with `Maturity N/A:
  @m-<axis> — <reason>`. The DOMAIN.md tier sets the depth floor. Baby
  steps are mandatory: one new maturity axis per wave, one axis per
  scenario; the happy path gets its own scenario. Do not cram the value
  contract into one big-bang wave.
"""


def _slug(feature: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", feature.strip().lower()).strip("-")
    return slug or "feature"


_VALUE_SECTION_RE = re.compile(r"^##\s+Value contract\s*$([\s\S]*?)(?=^## |\Z)", re.M)
_UNFILLED_VALUE_RE = re.compile(r"^\(.*\)$|^<[^>]*>$|\b(?:TBD|TODO|FIXME)\b", re.I)
VALUE_CONTRACT_FIELDS = (
    "Problem", "Users", "Baseline / current cost", "Target outcome indicator",
    "Economic hypothesis", "Owner / date",
)


def value_contract_status(text: str) -> tuple[bool, list[str]]:
    """(filled, problems) for SPEC.md's `## Value contract` (D017).

    Deliberately shallow: every field must be present, substantive, free of
    template guidance or unresolved markers, and the target must contain a
    number. This proves the contract is measurable enough to plan from — not
    that the numbers are wise. Judgment stays with the agent.
    """
    match = _VALUE_SECTION_RE.search(text)
    if not match:
        return False, ["## Value contract"]
    block = match.group(1)
    problems, values = [], {}
    for field in VALUE_CONTRACT_FIELDS:
        fm = re.search(rf"^-\s*{re.escape(field)}\s*:\s*(.+?)\s*$", block, re.M | re.I)
        value = fm.group(1).strip() if fm else ""
        if not value or _UNFILLED_VALUE_RE.search(value):
            problems.append(field)
        else:
            values[field] = value
    target = values.get("Target outcome indicator", "")
    if target and not re.search(r"\d", target):
        problems.append("Target outcome indicator (add a numeric target)")
    return not problems, problems


_COMMENT_RE = re.compile(r"<!--[\s\S]*?-->")
_PAREN_RE = re.compile(r"\([^)]*\)")
_SECTION_RE = lambda name: re.compile(  # noqa: E731
    rf"^##\s+{re.escape(name)}\s*$([\s\S]*?)(?=^## |\Z)", re.M
)


def _section_body(text: str, name: str) -> str:
    match = _SECTION_RE(name).search(text)
    if not match:
        return ""
    return _COMMENT_RE.sub("", match.group(1))


def _has_content_line(body: str) -> bool:
    """True when a section has a line that is not template placeholder.

    Template guidance lives in `<!-- -->` comments and placeholder bullets are
    fully parenthesized (e.g. `- (term: meaning — used in …)`), so stripping
    `(...)` groups and markdown punctuation leaves real content only.
    """
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith(">"):
            continue
        residue = re.sub(r"[^0-9A-Za-z]", "", _PAREN_RE.sub(" ", s))
        if len(residue) >= 3:
            return True
    return False


_DOMAIN_SECTIONS = (
    "Ubiquitous language", "Bounded contexts", "Domain model",
    "Integration style", "External translations",
)
_TIER_RE = re.compile(
    r"^\s*\*{0,2}Tier:?\*{0,2}\s*[:=]?\s*"
    r"(simple|standard|domain-heavy)\s*\.?\s*$",
    re.I | re.M,
)


def domain_tier(text: str) -> str | None:
    """The declared DOMAIN.md tier, lower-cased, or None when absent."""
    match = _TIER_RE.search(text or "")
    return match.group(1).lower() if match else None


def domain_status(text: str) -> tuple[bool, list[str]]:
    """(filled, problems) for DOMAIN.md (D019).

    Shallow by design: the tier must be one of the three declared values and
    every `##` section must hold at least one non-placeholder line. Whether a
    `domain-heavy` tier got a *real* model is semantic — the spec audit and
    wave reviewer judge that, not this check.
    """
    problems = []
    if not _TIER_RE.search(text):
        problems.append("Tier (simple | standard | domain-heavy)")
    for section in _DOMAIN_SECTIONS:
        body = _section_body(text, section)
        if not body.strip():
            problems.append(f"## {section}")
        elif not _has_content_line(body):
            problems.append(f"## {section} (still template placeholders)")
    return not problems, problems


_EXPERIENCE_FIELDS = ("Primary journey", "Edge states", "UX bar", "Accessibility", "UI pattern", "Navigation/overlay")
_NA_LINE_RE = re.compile(r"^N/?A\b", re.I)
_NA_REASON_RE = re.compile(r"^N/?A\s*[—–-]\s*(\S.{7,})\s*$", re.I)
_BARE_NA_RE = re.compile(r"^n/?a\.?$", re.I)
# The named pattern may carry a rationale ("F-pattern — dense stock tables"),
# and `F/Z` is the hedge the tier guidance prescribes for simple features.
_UI_PATTERN_RE = re.compile(r"^(?:F-pattern|Z-pattern|single-column|F/Z)\b", re.I)
_UI_PATTERN_NAMED_RE = re.compile(r"^(?:F-pattern|Z-pattern|single-column)\b", re.I)
_UI_SIMPLE_RE = re.compile(r"^(?:Z-pattern|F/Z)\b", re.I)
# Primary surface the journey runs on. `drawer` is accepted as an alias for
# the canonical `side-pane` so an author's vocabulary cannot fail the gate.
_NAV_SURFACE_RE = re.compile(r"^(?:full-page|side-pane|drawer|modal|inline)\b", re.I)
_NAV_WHY_RE = re.compile(
    r"^(?:full-page|side-pane|drawer|modal|inline)\s*[—–-]\s*(\S.{7,})\s*$",
    re.I,
)
# Design references a domain-heavy feature may cite for its pattern or
# navigation surface.
_UI_STANDARD_RE = re.compile(
    r"\b(?:Material(?:\s+Design)?|Apple\s+HIG|Human\s+Interface\s+Guidelines|NN/?g|Nielsen(?:\s+Norman)?|Polaris|Bootstrap|Fluent|Carbon|Ant\s+Design|Tailwind)\b",
    re.I,
)


def experience_field(text: str, field: str) -> str:
    """One `- <field>: value` bullet from `## Experience`, continuations joined.

    Indented continuation lines belong to the value; the next bullet, blank
    line or heading ends it. Returns "" when the section or field is absent.
    """
    body = _section_body(text, "Experience")
    pattern = re.compile(rf"^\s*-\s*{re.escape(field)}\s*:\s*(.*)$", re.I)
    parts: list[str] = []
    capturing = False
    for line in body.splitlines():
        if capturing:
            if line.startswith((" ", "\t")) and line.strip():
                parts.append(line.strip())
                continue
            break
        match = pattern.match(line)
        if match:
            capturing = True
            parts.append(match.group(1).strip())
    return " ".join(parts).strip()


def experience_surface(text: str) -> str | None:
    """The declared navigation surface, normalized (`drawer` -> `side-pane`)."""
    match = _NAV_SURFACE_RE.match(experience_field(text, "Navigation/overlay"))
    if not match:
        return None
    token = match.group(0).lower()
    return "side-pane" if token == "drawer" else token


def experience_status(text: str, tier: str | None = None) -> tuple[bool, list[str]]:
    """(filled, problems) for SPEC.md's `## Experience` section (D019).

    Either every field is substantively filled, or the whole section declares
    `N/A — <reason>` (a bare N/A is rejected — explicit defaults, not silent
    skips). Per-field `n/a — <reason>` is allowed inside filled fields.
    When `tier` (from DOMAIN.md) is supplied, the UI pattern must match the
    tier's depth rule: simple = Z-pattern/F-Z hedge, standard = a named
    pattern, domain-heavy = a named pattern citing a design standard. The
    navigation surface follows the same shape: standard must say why it was
    chosen, domain-heavy must also cite the design standard behind it.
    """
    body = _section_body(text, "Experience")
    if not body.strip():
        return False, ["## Experience"]
    first = next((l.strip() for l in body.splitlines() if l.strip()), "")
    if _NA_LINE_RE.match(first):
        if _NA_REASON_RE.match(first):
            return True, []
        return False, ["## Experience (N/A needs a reason after the dash)"]
    problems = []
    for field in _EXPERIENCE_FIELDS:
        fm = re.search(
            rf"^-\s*{re.escape(field)}\s*:\s*(.+?)\s*$",
            body, re.M | re.I,
        )
        value = fm.group(1).strip() if fm else ""
        if not value or _UNFILLED_VALUE_RE.search(value) or _BARE_NA_RE.match(value):
            problems.append(field)
    # Validate UI pattern field: a named pattern (optionally with a
    # rationale) or a per-field `n/a — <reason>`; anything else is rejected.
    pattern_fm = re.search(
        rf"^-\s*UI pattern:\s*(.+?)\s*$",
        body, re.M | re.I,
    )
    pattern_value = pattern_fm.group(1).strip() if pattern_fm else ""
    if (
        pattern_value
        and not _BARE_NA_RE.match(pattern_value)
        and not _NA_REASON_RE.match(pattern_value)
    ):
        if not _UI_PATTERN_RE.match(pattern_value):
            problems.append(
                "UI pattern (F-pattern | Z-pattern | single-column | F/Z)"
            )
        elif tier == "simple" and not _UI_SIMPLE_RE.match(pattern_value):
            problems.append("UI pattern (simple tier: Z-pattern or F/Z)")
        elif tier == "standard" and not _UI_PATTERN_NAMED_RE.match(pattern_value):
            problems.append(
                "UI pattern (standard tier must name F-pattern, Z-pattern or "
                "single-column; F/Z is a hedge, not a decision)"
            )
        elif tier == "domain-heavy" and not _UI_STANDARD_RE.search(pattern_value):
            problems.append(
                "UI pattern (domain-heavy tier must cite a design standard, "
                "e.g. Material, Apple HIG, Polaris, NN/g)"
            )
    # Validate the navigation surface: a closed vocabulary so the page / pane /
    # modal decision is reviewable, with depth scaling by tier.
    nav_fm = re.search(
        rf"^-\s*Navigation/overlay:\s*(.+?)\s*$",
        body, re.M | re.I,
    )
    nav_value = nav_fm.group(1).strip() if nav_fm else ""
    if (
        nav_value
        and not _BARE_NA_RE.match(nav_value)
        and not _NA_REASON_RE.match(nav_value)
    ):
        if not _NAV_SURFACE_RE.match(nav_value):
            problems.append(
                "Navigation/overlay (full-page | side-pane | modal | inline)"
            )
        elif tier in ("standard", "domain-heavy") and not _NAV_WHY_RE.match(
            nav_value
        ):
            problems.append(
                "Navigation/overlay (standard tier must explain the choice: "
                "`<surface> — <rationale>`)"
            )
        elif tier == "domain-heavy" and not _UI_STANDARD_RE.search(nav_value):
            problems.append(
                "Navigation/overlay (domain-heavy tier must cite a design "
                "standard, e.g. Material, Apple HIG, Polaris, NN/g)"
            )
    return not problems, problems


MATURITY_AXES = ("failure", "ownership", "data", "ux", "outcome")
_ANY_MATURITY_TAG_RE = re.compile(r"@m-([A-Za-z][A-Za-z0-9_-]*)", re.I)
_MATURITY_NA_LINE_RE = re.compile(
    r"^\s*#\s*Maturity\s+N/A\s*:\s*@m-([A-Za-z][A-Za-z0-9_-]*)"
    r"(?:\s*[—–-]\s*(.*?))?\s*$",
    re.I,
)
_MATURITY_FLOORS = {
    "simple": (2, ()),
    "standard": (3, ("failure",)),
    "domain-heavy": (3, ("failure", "data")),
}
_MATURITY_WAVE_RE = re.compile(r"@w(\d+)", re.I)


def maturity_wave_problems(feature_text: str) -> list[str]:
    """D020 baby-step problems: one new axis per wave, dedicated scenarios.

    This is deliberately orthogonal to axis coverage: a spec can cover all
    five axes and still be rejected for cramming them into wave 1. Multiple
    scenarios for the SAME axis in one wave are fine — that is depth, not a
    big-bang increment.
    """
    axes = set(MATURITY_AXES)
    problems: list[str] = []
    pending_axes: set[str] = set()
    pending_waves: set[int] = set()
    pending_happy = False
    pending_name = ""
    first_wave: dict[str, int] = {}

    def close_scenario() -> None:
        nonlocal pending_axes, pending_waves, pending_happy, pending_name
        name = pending_name.strip()
        if not name:
            return
        known = pending_axes & axes
        tags = ", ".join(f"@m-{a}" for a in MATURITY_AXES if a in known)
        if len(known) > 1:
            problems.append(
                f"scenario '{name}' carries {tags} — give each axis a "
                "dedicated scenario"
            )
        if pending_happy and known:
            problems.append(
                f"scenario '{name}' mixes @happy-path with {tags} — keep "
                "the baby steps separate"
            )
        if known and not pending_waves:
            problems.append(
                f"scenario '{name}' has {tags} but no @w<N> wave"
            )
        for axis in known:
            if pending_waves:
                w = min(pending_waves)
                if axis not in first_wave or w < first_wave[axis]:
                    first_wave[axis] = w
        pending_axes, pending_waves = set(), set()
        pending_happy, pending_name = False, ""

    for line in feature_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("@"):
            for axis in _ANY_MATURITY_TAG_RE.findall(stripped):
                axis = axis.lower()
                if axis in axes:
                    pending_axes.add(axis)
            pending_waves.update(int(w) for w in _MATURITY_WAVE_RE.findall(stripped))
            if "happy" in stripped.lower():
                pending_happy = True
            continue
        if stripped.startswith("Scenario"):
            pending_name = (
                stripped.split(":", 1)[1].strip()
                if ":" in stripped else stripped
            )
            close_scenario()

    by_wave: dict[int, list[str]] = {}
    for axis, wave in first_wave.items():
        by_wave.setdefault(wave, []).append(axis)
    for wave, wave_axes in by_wave.items():
        if len(wave_axes) > 1:
            tags = ", ".join(
                f"@m-{a}" for a in MATURITY_AXES if a in wave_axes
            )
            problems.append(
                f"wave @w{wave} introduces {tags} — split maturity axes into "
                "separate waves"
            )
    return problems


def declared_tier(domain_text: str) -> str:
    """Tier declared in DOMAIN.md; default to `simple` when absent (D019/D020)."""
    match = _TIER_RE.search(domain_text)
    return match.group(1).lower() if match else "simple"


def maturity_status(feature_text: str, tier: str = "simple") -> tuple[bool, list[str]]:
    """(covered, problems) for EXAMPLES.feature scenario maturity (D020).

    Deliberately shallow: every axis must be exercised by a real, tagged
    Scenario or justified with `# Maturity N/A: @m-<axis> — <reason>`, and the
    declared tier sets a floor on how many axes are actually exercised. This
    proves the examples are wide enough to plan from — not that the scenarios
    are good. Breadth is staged across waves (one new axis per wave, one axis
    per dedicated scenario) so a spec cannot smuggle the whole value contract
    into one big-bang iteration. Semantic quality stays with the spec audit
    and wave reviewer.
    """
    tier = (tier or "simple").lower()
    if tier not in _MATURITY_FLOORS:
        tier = "simple"
    floor, required = _MATURITY_FLOORS[tier]
    axes = set(MATURITY_AXES)
    covered: set[str] = set()
    justified: set[str] = set()
    pending: set[str] = set()
    problems: list[str] = maturity_wave_problems(feature_text)
    real_scenarios = 0
    has_happy = False

    for line in feature_text.splitlines():
        na_match = _MATURITY_NA_LINE_RE.match(line)
        if na_match:
            axis = na_match.group(1).lower()
            reason = (na_match.group(2) or "").strip()
            if axis not in axes:
                problems.append(f"unknown maturity tag @m-{axis}")
            elif not reason or _UNFILLED_VALUE_RE.search(reason):
                problems.append(f"@m-{axis} (N/A needs a reason after the dash)")
            elif axis in covered:
                problems.append(f"@m-{axis} (covered and marked N/A)")
            else:
                justified.add(axis)
            continue

        stripped = line.strip()
        if stripped.startswith("@"):
            for tag in _ANY_MATURITY_TAG_RE.findall(stripped):
                tag = tag.lower()
                if tag not in axes:
                    problems.append(f"unknown maturity tag @m-{tag}")
                else:
                    pending.add(tag)
            if "happy" in stripped.lower():
                pending.add("happy")
            continue

        if stripped.startswith("Scenario"):
            name = stripped.split(":", 1)[1].strip() if ":" in stripped else ""
            if not name or _UNFILLED_VALUE_RE.search(name):
                problems.append("scenario name still a placeholder")
            else:
                real_scenarios += 1
                has_happy = has_happy or "happy" in pending
                covered.update(pending & axes)
            pending = set()

    if not real_scenarios:
        problems.append("at least one real Scenario")
    elif not has_happy:
        problems.append("at least one @happy-path scenario")
    for axis in MATURITY_AXES:
        if axis not in covered and axis not in justified:
            problems.append(f"@m-{axis}")
    if len(covered) < floor:
        problems.append(f"{tier} tier needs {floor} covered axes (found {len(covered)})")
    for axis in required:
        if axis not in covered:
            problems.append(f"@m-{axis} ({tier} tier needs a real scenario)")
    if tier in ("standard", "domain-heavy") and "ux" not in covered and "ux" not in justified:
        problems.append("@m-ux (user-facing tier needs a scenario or N/A — <reason>)")
    return not problems, problems


def section_status(
    text: str, section: str, tier: str | None = None
) -> tuple[bool, list[str]]:
    """(filled, problems) for a generic `## <section>` gate target.

    `Experience` delegates to its field-aware validator (passing the DOMAIN.md
    tier when the caller has it); any other section only needs to exist with
    at least one non-placeholder line.
    """
    if section.strip().lower() == "experience":
        return experience_status(text, tier=tier)
    body = _section_body(text, section.strip())
    if not body.strip():
        return False, [f"## {section.strip()}"]
    if not _has_content_line(body):
        return False, [f"## {section.strip()} (still template placeholders)"]
    return True, []


@skill
def spec_scaffold(repo_path: str = ".", feature: str = "", output_dir: str = "specs") -> str:
    """Create the spec skeletons for one feature (SPEC/DOMAIN/EXAMPLES/BACKLOG/GATES).

    Writes five artifacts into <repo_path>/<output_dir>/<feature-slug>/.
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
        "DOMAIN.md": _DOMAIN_MD.format(title=title),
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
    out.append("Next: fill SPEC.md (problem/users/scope/acceptance criteria/experience),")
    out.append("write real Gherkin scenarios in EXAMPLES.feature with @w<N> tags,")
    out.append("fill DOMAIN.md (tier, glossary, bounded contexts, aggregates), add")
    out.append("backlog items to BACKLOG.md, define preconditions in GATES.md,")
    out.append("then run `wave_plan`.")
    return "\n".join(out)
