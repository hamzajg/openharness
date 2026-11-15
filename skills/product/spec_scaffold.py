"""Scaffold a spec-driven feature directory: SPEC.md + EXAMPLES.feature + BACKLOG.md.

Creates specs/<feature>/ inside the target repo with three artifacts:
- SPEC.md — the spec driver (problem, users, scope, out-of-scope, acceptance criteria)
- EXAMPLES.feature — specifications by example (Gherkin scenarios, tagged @w<N>)
- BACKLOG.md — ordered work items referencing scenario tags and dependency hints

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

## Scope (in)

-

## Scope (out)

-

## Acceptance criteria

| # | Criterion | Scenario(s) |
|---|-----------|-------------|
| 1 |             | @w1         |

## Decisions

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

Format per item — keep it parseable by `wave_plan`:

```
## B<n> — <title>
- Scenarios: @w1, @w2
- Depends: B1, B3        (optional; omit for wave-1 items)
- Size: S|M|L
- Notes: <one line>
```

## B1 — {first_item}
- Scenarios: @w1
- Size: M
- Notes:
"""


def _slug(feature: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", feature.strip().lower()).strip("-")
    return slug or "feature"


@skill
def spec_scaffold(repo_path: str = ".", feature: str = "", output_dir: str = "specs") -> str:
    """Create specs/<feature>/ with SPEC.md, EXAMPLES.feature, BACKLOG.md skeletons.

    Writes three artifacts into <repo_path>/<output_dir>/<feature-slug>/.
    Never overwrites an existing SPEC.md unless force=true. The agent fills
    the placeholders; keep the section headers and tag conventions intact so
    `wave_plan` can parse BACKLOG.md later.

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
        "BACKLOG.md": _BACKLOG_MD.format(title=title, first_item="(first backlog item)"),
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
    out.append("Gherkin scenarios in EXAMPLES.feature with @w<N> tags, then add")
    out.append("backlog items to BACKLOG.md and run `wave_plan`.")
    return "\n".join(out)
