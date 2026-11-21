import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from openharness.skill import SkillError
from skills.product.discover_product import discover_product
from skills.product.spec_scaffold import spec_scaffold
from skills.product.wave_plan import wave_plan


def _write(root: Path, rel: str, content: str):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


# ---------- discover_product ----------

def test_discover_product_reports_stack_and_signals(tmp_path):
    _write(tmp_path, "README.md", "# Demo App\nA thing.")
    _write(tmp_path, "app.py", "from flask import Flask\napp = Flask(__name__)\n\n@app.get('/x')\ndef x():\n    # TODO: implement\n    raise NotImplementedError\n")
    _write(tmp_path, "tests/test_app.py", "def test_x():\n    assert True\n")
    _write(tmp_path, "node_modules/junk/index.js", "// skip me\n")

    report = discover_product.invoke(repo_path=str(tmp_path))
    assert "Product Surface Report" in report
    assert "Python" in report
    assert "NotImplementedError" not in report  # counts, not raw hits dump
    assert "placeholder markers" in report.lower()
    assert "specs/" in report


def test_discover_product_missing_dir(tmp_path):
    out = discover_product.invoke(repo_path=str(tmp_path / "nope"))
    assert out.startswith("ERROR")


# ---------- spec_scaffold ----------

def test_spec_scaffold_creates_artifacts_with_outcome_hypothesis(tmp_path):
    out = spec_scaffold.invoke(repo_path=str(tmp_path), feature="User Notifications", output_dir="specs")
    d = tmp_path / "specs" / "user-notifications"
    assert (d / "SPEC.md").is_file()
    assert (d / "EXAMPLES.feature").is_file()
    assert (d / "BACKLOG.md").is_file()
    assert (d / "GATES.md").is_file()
    spec = (d / "SPEC.md").read_text()
    assert "## Outcome hypothesis" in spec
    assert "Opportunity evidence" in spec
    assert "do not invent targets" in spec
    assert "user-notifications" in out
    assert "@w1" in (d / "EXAMPLES.feature").read_text()


def test_spec_scaffold_never_overwrites(tmp_path):
    spec_scaffold.invoke(repo_path=str(tmp_path), feature="Cart", output_dir="specs")
    spec = tmp_path / "specs" / "cart" / "SPEC.md"
    spec.write_text("# custom\n")
    spec_scaffold.invoke(repo_path=str(tmp_path), feature="Cart", output_dir="specs")
    assert spec.read_text() == "# custom\n"


def test_spec_scaffold_requires_feature(tmp_path):
    out = spec_scaffold.invoke(repo_path=str(tmp_path), feature="  ", output_dir="specs")
    assert out.startswith("ERROR")


# ---------- wave_plan ----------

_BACKLOG = textwrap.dedent("""\
    # Backlog: Demo

    ## B1 — Base model
    - Scenarios: @w1
    - Size: M

    ## B2 — API endpoint
    - Scenarios: @w2
    - Depends: B1
    - Size: M

    ## B3 — UI screen
    - Scenarios: @w2
    - Depends: B1
    - Size: L
    - Notes: needs design

    ## B4 — Export
    - Scenarios: @w3
    - Depends: B2, B3
    - Size: S
""")

_FEATURE = textwrap.dedent("""\
    Feature: Demo

      @w1
      Scenario: Create base
        Given x
        When y
        Then z

      @w2
      Scenario: See it in API
        Given x
        When y
        Then z

      @w2
      Scenario: See it on screen
        Given x
        When y
        Then z

      @w3
      Scenario: Export it
        Given x
        When y
        Then z
""")


def _spec_dir(tmp_path: Path, backlog=_BACKLOG, feature=_FEATURE) -> Path:
    d = tmp_path / "specs" / "demo"
    d.mkdir(parents=True)
    (d / "BACKLOG.md").write_text(backlog)
    (d / "EXAMPLES.feature").write_text(feature)
    return d


def test_wave_plan_orders_by_dependencies(tmp_path):
    d = _spec_dir(tmp_path)
    out = wave_plan.invoke(spec_dir=str(d))
    assert (d / "WAVES.md").is_file()
    # B1 wave1, B2/B3 wave2, B4 wave3
    assert "## Wave 1" in out and "## Wave 3" in out
    w1 = out.index("## Wave 1"); w2 = out.index("## Wave 2"); w3 = out.index("## Wave 3")
    assert "B1" in out[w1:w2] and "B4" not in out[w1:w3]
    assert "Create base" in out
    assert "Export it" in out


def test_wave_plan_detects_missing_dep(tmp_path):
    d = _spec_dir(tmp_path, backlog=_BACKLOG.replace("Depends: B1\n- Size: M\n\n## B3", "Depends: B9\n- Size: M\n\n## B3"))
    out = wave_plan.invoke(spec_dir=str(d))
    assert "#9" in out and "does not exist" in out


def test_wave_plan_requires_backlog(tmp_path):
    d = tmp_path / "specs" / "empty"
    d.mkdir(parents=True)
    out = wave_plan.invoke(spec_dir=str(d))
    assert out.startswith("ERROR")


def test_wave_plan_refuses_empty_backlog_loudly(tmp_path):
    # A BACKLOG.md with no `## US<n>` / `## B<n>` blocks must raise, not return
    # an "ERROR" string that every caller reads as success.
    d = tmp_path / "specs" / "empty"
    d.mkdir(parents=True)
    (d / "BACKLOG.md").write_text("# Backlog: Empty\n\nNothing approved yet.\n")

    with pytest.raises(SkillError) as err:
        wave_plan.invoke(spec_dir=str(d))

    assert "no backlog items parsed" in str(err.value)
    assert "WAVES.md was not written" in str(err.value)
    assert not (d / "WAVES.md").exists()


def test_wave_plan_refuses_a_fresh_scaffold(tmp_path):
    # Regression: the scaffold used to ship a parseable placeholder story, so
    # `wave_plan` happily planned the placeholders (the ship-loop run shipped a
    # plan reading "(first user-facing capability)").
    spec_scaffold.invoke(repo_path=str(tmp_path), feature="demo feature", output_dir="specs")
    d = tmp_path / "specs" / "demo-feature"

    with pytest.raises(SkillError):
        wave_plan.invoke(spec_dir=str(d))
    assert not (d / "WAVES.md").exists()


def test_wave_plan_cli_exits_nonzero_without_a_backlog(tmp_path):
    d = tmp_path / "specs" / "empty"
    d.mkdir(parents=True)
    (d / "BACKLOG.md").write_text("# Backlog: Empty\n")

    run = subprocess.run(
        [sys.executable, "-m", "openharness", "run", "wave_plan", f"--spec_dir={d}"],
        cwd=Path(__file__).resolve().parent.parent,
        capture_output=True,
        text=True,
    )

    assert run.returncode == 2, run.stdout + run.stderr
    assert "no backlog items parsed" in run.stderr
    assert "Traceback" not in run.stderr
    assert not (d / "WAVES.md").exists()


# ---------- user-story backlog format ----------

def test_wave_plan_accepts_user_story_ids(tmp_path):
    backlog = textwrap.dedent("""\
        # Backlog: US format

        ## US1 — As a user, I want login, so that I can save work
        - Scenarios: @w1
        - Size: M

        ## US2 — As a user, I want logout, so that I can switch accounts
        - Scenarios: @w2
        - Depends: US1
        - Size: S
    """)
    d = _spec_dir(tmp_path, backlog=backlog)
    out = wave_plan.invoke(spec_dir=str(d))
    assert "US1" in out and "US2" in out
    w1 = out.index("## Wave 1"); w2 = out.index("## Wave 2")
    assert "US1" in out[w1:w2] and "US2" in out[w2:]


# ---------- product_map ----------

def test_product_map_aggregates_specs(tmp_path):
    from skills.product.product_map import product_map
    d1 = _spec_dir(tmp_path)
    wave_plan.invoke(spec_dir=str(d1))
    d2 = tmp_path / "specs" / "other"
    d2.mkdir(parents=True)
    (d2 / "SPEC.md").write_text("# Spec: Other Feature\n")
    (d2 / "BACKLOG.md").write_text("## US1 — story\n- Scenarios: @w1\n")
    (d2 / "EXAMPLES.feature").write_text("Feature: X\n\n  @w1\n  Scenario: S\n    Given a\n    When b\n    Then c\n")
    out = product_map.invoke(repo_path=str(tmp_path))
    assert (tmp_path / "specs" / "PRODUCT.md").is_file()
    assert "demo" in out and "other" in out
    assert "Planned" in out


# ---------- ship_validate ----------

def test_ship_validate_writes_traceability(tmp_path):
    from skills.product.ship_validate import ship_validate
    repo = tmp_path / "repo"
    d = repo / "specs" / "demo"
    d.mkdir(parents=True)
    (d / "SPEC.md").write_text(
        "# Spec: Demo\n\n## Acceptance criteria\n\n| # | Criterion | Scenario(s) |\n|---|-----------|-------------|\n| 1 | It works | @w1 |\n"
    )
    (d / "EXAMPLES.feature").write_text(
        "Feature: Demo\n\n  @w1 @happy-path\n  Scenario: Create base\n    Given x\n    When y\n    Then z\n"
    )
    (d / "WAVES.md").write_text("# Waves\n\n## Wave 1 — iteration 1\n\n| Item |\n")
    _write(repo, "tests/test_demo.py", "def test_create_base():\n    # covers 'Create base' scenario\n    assert True\n")
    out = ship_validate.invoke(spec_dir=str(d), repo_path=str(repo))
    assert (d / "VALIDATION.md").is_file()
    assert "Traceability" in out and "Demo script" in out
    assert "test_demo.py" in out  # evidence found
    assert "## TDD evidence" in out and "Wave 1: no bundle recorded" in out


def test_ship_validate_finds_tsx_test_evidence(tmp_path):
    from skills.product.ship_validate import ship_validate
    repo = tmp_path / "repo"
    d = repo / "specs" / "demo"
    d.mkdir(parents=True)
    (d / "SPEC.md").write_text(
        "# Spec: Demo\n\n## Acceptance criteria\n\n| # | Criterion | Scenario(s) |\n|---|-----------|-------------|\n| 1 | It works | @w1 |\n"
    )
    (d / "EXAMPLES.feature").write_text(
        "Feature: Demo\n\n  @w1 @happy-path\n  Scenario: Render shell\n    Given x\n    When y\n    Then z\n"
    )
    (d / "WAVES.md").write_text("# Waves\n\n## Wave 1 — iteration 1\n\n| Item |\n")
    _write(repo, "src/__tests__/shell.test.tsx",
           "describe('Render shell', () => { it('works', () => {}) })\n")
    out = ship_validate.invoke(spec_dir=str(d), repo_path=str(repo))
    assert "shell.test.tsx" in out


def test_ship_validate_preserves_outcome_followup_on_rerun(tmp_path):
    from skills.product.ship_validate import ship_validate
    repo = tmp_path / "repo"
    d = repo / "specs" / "demo"
    d.mkdir(parents=True)
    (d / "SPEC.md").write_text("# Spec: Demo\n")
    (d / "EXAMPLES.feature").write_text("Feature: Demo\n")
    (d / "WAVES.md").write_text("# Waves\n")
    validation = d / "VALIDATION.md"

    ship_validate.invoke(spec_dir=str(d), repo_path=str(repo))
    text = validation.read_text().replace(
        "- Status: not yet measured",
        "- Status: measured\n- Learning or next action: schedule follow-up",
    )
    validation.write_text(text)

    out = ship_validate.invoke(spec_dir=str(d), repo_path=str(repo))
    assert "- Status: measured" in out
    assert "- Learning or next action: schedule follow-up" in out
    assert "not yet measured" not in out


def test_ship_validate_preserves_manual_verification_on_rerun(tmp_path):
    from skills.product.ship_validate import ship_validate
    repo = tmp_path / "repo"
    d = repo / "specs" / "demo"
    d.mkdir(parents=True)
    (d / "SPEC.md").write_text("# Spec: Demo\n")
    (d / "EXAMPLES.feature").write_text("Feature: Demo\n")
    (d / "WAVES.md").write_text("# Waves\n")
    validation = d / "VALIDATION.md"

    ship_validate.invoke(spec_dir=str(d), repo_path=str(repo))
    assert "## Manual verification" in validation.read_text()
    text = validation.read_text().replace(
        "## Manual verification\n",
        "## Manual verification\n\n- AC 1 — ran the demo flow → order created\n",
    )
    validation.write_text(text)

    out = ship_validate.invoke(spec_dir=str(d), repo_path=str(repo))
    assert "- AC 1 — ran the demo flow → order created" in out


def test_ship_validate_resolves_scenario_names_in_ac(tmp_path):
    from skills.product.ship_validate import ship_validate
    repo = tmp_path / "repo"
    d = repo / "specs" / "demo"
    d.mkdir(parents=True)
    (d / "SPEC.md").write_text(
        "# Spec: Demo\n\n## Acceptance criteria\n\n| # | Criterion | Scenario(s) |\n|---|-----------|-------------|\n| 1 | It works | Create base |\n"
    )
    (d / "EXAMPLES.feature").write_text(
        "Feature: Demo\n\n  @w1 @happy-path\n  Scenario: Create base\n    Given x\n"
    )
    (d / "WAVES.md").write_text("# Waves\n\n## Wave 1 — iteration 1\n\n| Item |\n")
    _write(repo, "tests/test_demo.py", "def test_unrelated():\n    assert True\n")
    out = ship_validate.invoke(spec_dir=str(d), repo_path=str(repo))
    assert "| 1 | It works | Create base | 1 |" in out  # name resolved to scenario+wave


def test_ship_validate_weak_evidence_marked(tmp_path):
    from skills.product.ship_validate import ship_validate
    repo = tmp_path / "repo"
    d = repo / "specs" / "demo"
    d.mkdir(parents=True)
    (d / "SPEC.md").write_text(
        "# Spec: Demo\n\n## Acceptance criteria\n\n| # | Criterion | Scenario(s) |\n|---|-----------|-------------|\n| 1 | It works | @w1 |\n"
    )
    (d / "EXAMPLES.feature").write_text(
        "Feature: Demo\n\n  @w1\n  Scenario: Order history shows own orders\n    Given x\n"
    )
    (d / "WAVES.md").write_text("# Waves\n\n## Wave 1 — iteration 1\n\n| Item |\n")
    _write(repo, "tests/test_orders.py",
           "def test_orders_list_only_own_orders_history():\n    assert True\n")
    out = ship_validate.invoke(spec_dir=str(d), repo_path=str(repo))
    assert "~" in out and "weak" in out


def test_ship_validate_counts_groovy_specs(tmp_path):
    from skills.product.ship_validate import ship_validate
    repo = tmp_path / "repo"
    d = repo / "specs" / "demo"
    d.mkdir(parents=True)
    (d / "SPEC.md").write_text(
        "# Spec: Demo\n\n## Acceptance criteria\n\n| # | Criterion | Scenario(s) |\n|---|-----------|-------------|\n| 1 | It works | @w1 |\n"
    )
    (d / "EXAMPLES.feature").write_text(
        "Feature: Demo\n\n  @w1\n  Scenario: Referral keeps posted details\n    Given x\n"
    )
    (d / "WAVES.md").write_text("# Waves\n\n## Wave 1 — iteration 1\n\n| Item |\n")
    _write(repo, "src/test/groovy/DemoSpec.groovy",
           "def 'Referral keeps posted details'() {\n    expect: true\n}\n")
    out = ship_validate.invoke(spec_dir=str(d), repo_path=str(repo))
    assert "DemoSpec.groovy" in out


def test_ship_validate_named_scenarios_do_not_expand_to_whole_wave(tmp_path):
    from skills.product.ship_validate import ship_validate
    repo = tmp_path / "repo"
    d = repo / "specs" / "demo"
    d.mkdir(parents=True)
    (d / "SPEC.md").write_text(
        "# Spec: Demo\n\n## Acceptance criteria\n\n"
        "| # | Criterion | Scenario(s) |\n|---|-----------|-------------|\n"
        "| 1 | It works | Create base |\n"
        "| 2 | Everything in wave 1 | @w1 |\n"
    )
    (d / "EXAMPLES.feature").write_text(
        "Feature: Demo\n\n  @w1\n  Scenario: Create base\n    Given x\n\n"
        "  @w1\n  Scenario: Other thing\n    Given x\n"
    )
    (d / "WAVES.md").write_text("# Waves\n\n## Wave 1 — iteration 1\n\n| Item |\n")
    _write(repo, "tests/test_demo.py", "def test_create_base():\n    assert True\n")
    out = ship_validate.invoke(spec_dir=str(d), repo_path=str(repo))
    row1 = next(line for line in out.splitlines() if line.startswith("| 1 |"))
    row2 = next(line for line in out.splitlines() if line.startswith("| 2 |"))
    assert "Other thing" not in row1
    assert "Other thing" in row2  # explicit @w1 still expands to the wave


def test_ship_validate_parses_numbered_acceptance_criteria(tmp_path):
    from skills.product.ship_validate import ship_validate
    repo = tmp_path / "repo"
    d = repo / "specs" / "demo"
    d.mkdir(parents=True)
    (d / "SPEC.md").write_text(
        "# Spec: Demo\n\n## Acceptance criteria\n\n1. Create base works (@w1)\n2. Export it works (@w2)\n"
    )
    (d / "EXAMPLES.feature").write_text(
        "Feature: Demo\n\n  @w1 @happy-path\n  Scenario: Create base\n    Given x\n\n  @w2\n  Scenario: Export it\n    Given x\n"
    )
    (d / "WAVES.md").write_text("# Waves\n\n## Wave 1 — iteration 1\n\n| Item |\n\n## Wave 2 — iteration 2\n\n| Item |\n")
    _write(repo, "tests/test_demo.py", "def test_create_base():\n    # Create base\n    assert True\n")
    out = ship_validate.invoke(spec_dir=str(d), repo_path=str(repo))
    assert "| 1 | Create base works (@w1) | Create base | 1 | test_demo.py |" in out
    assert "| 2 | Export it works (@w2) | Export it | 2 |" in out
