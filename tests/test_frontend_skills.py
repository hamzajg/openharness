"""The frontend skills are discoverable and catch the defects they claim to."""

import json

import pytest

from openharness.registry import get
from openharness.skill import SkillError


def _web(tmp_path, name="web"):
    web = tmp_path / name
    web.mkdir()
    (web / "src").mkdir()
    return web


def _pkg(web, **deps):
    (web / "package.json").write_text(json.dumps({"name": "x", "dependencies": deps}))


def test_frontend_skills_are_discoverable():
    for name in ("ux_specs", "react_stack_standards", "css_stack_standards", "ux_architecture",
                 "logo_design", "theme_designer"):
        assert get(name) is not None, f"missing frontend skill: {name}"


def test_ux_specs_flags_a_missing_experience(tmp_path):
    spec = tmp_path / "specs" / "orders"
    spec.mkdir(parents=True)
    (spec / "SPEC.md").write_text("# orders\n\n## Scope (in)\n- x\n")
    out = get("ux_specs").invoke(repo_path=str(tmp_path))
    assert "[error]" in out
    assert "missing `## Experience`" in out


def test_ux_specs_accepts_a_complete_contract(tmp_path):
    spec = tmp_path / "specs" / "orders"
    spec.mkdir(parents=True)
    (spec / "DOMAIN.md").write_text("**Tier:** standard\n")
    (spec / "SPEC.md").write_text(
        "# orders\n\n## Experience\n\n"
        "- Primary journey: the planner opens the list and edits one row.\n"
        "- Edge states: empty list, loading, error and permission-denied.\n"
        "- UX bar: the edit saves without leaving the list; unsaved changes are guarded.\n"
        "- Accessibility: labelled fields and a visible focus ring.\n"
        "- UI pattern: F-pattern — a dense table.\n"
        "- Navigation/overlay: side-pane — keeps the filtered list and scroll position.\n"
    )
    out = get("ux_specs").invoke(repo_path=str(tmp_path))
    assert "[ok] orders" in out
    assert "0 error(s)" in out


def test_react_flags_a_missing_test_runner(tmp_path):
    web = _web(tmp_path)
    _pkg(web, react="^18.0.0", **{"react-dom": "^18.0.0"})
    out = get("react_stack_standards").invoke(web_dir=str(web))
    assert "no `test` script" in out


def test_css_flags_low_contrast_and_missing_reduced_motion(tmp_path):
    web = _web(tmp_path)
    _pkg(web, tailwindcss="^4.0.0")
    (web / "src" / "index.css").write_text(
        '@import "tailwindcss";\n'
        "@theme {\n"
        "  --color-canvas: #000000;\n"
        "  --color-ink-faint: #333333;\n"
        "}\n"
        "@keyframes in { from { opacity: 0 } to { opacity: 1 } }\n"
    )
    out = get("css_stack_standards").invoke(web_dir=str(web))
    assert "below WCAG" in out
    assert "prefers-reduced-motion" in out


def test_ux_architecture_reports_maturity(tmp_path):
    web = _web(tmp_path)
    _pkg(web, react="^18.0.0")
    out = get("ux_architecture").invoke(web_dir=str(web))
    assert "Maturity:" in out
    assert "Tokens" in out


def test_logo_design_infers_domain_and_plans_assets(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"name": "loomline-web"}))
    (tmp_path / "README.md").write_text(
        "# LoomLine\n\nA manufacturing execution tool for the shop floor: work orders,"
        " routing and textile production.\n"
    )
    (tmp_path / "specs" / "orders").mkdir(parents=True)
    brief = tmp_path / "docs" / "brand" / "logo.md"
    out = get("logo_design").invoke(repo_path=str(tmp_path), out=str(brief))
    assert "Logo brief — Loomline" in out
    assert "manufacturing" in out
    assert "## Concept territories" in out
    assert "Maskable icon" in out
    assert "NOT RECORDED" in out
    assert brief.exists()
    assert "Platform asset matrix" in brief.read_text()


def test_theme_designer_writes_aa_tokens_and_guide(tmp_path):
    web = _web(tmp_path)
    _pkg(web, react="^19.0.0", vite="^7.0.0")
    (web / "src" / "theme.css").write_text(":root {\n  --brand-accent: #16a085;\n}\n")
    (tmp_path / "README.md").write_text("A production planning tool for factory planners.\n")
    out_dir = tmp_path / "design"
    out = get("theme_designer").invoke(
        repo_path=str(tmp_path), web_dir=str(web), prefix="acme", out_dir=str(out_dir)
    )
    css = (out_dir / "tokens.css").read_text()
    guide = (out_dir / "THEME.md").read_text()
    assert "--acme-color-ink" in css
    assert "--acme-color-accent-soft" in css
    assert 'data-theme="dark"' in css
    assert "prefers-reduced-motion" in css
    assert "## Page templates" in guide
    assert "## Alerts and feedback" in guide
    assert "FAIL" not in out


def test_theme_designer_rejects_an_unknown_style(tmp_path):
    with pytest.raises(SkillError):
        get("theme_designer").invoke(repo_path=str(tmp_path), style="brutalist")
