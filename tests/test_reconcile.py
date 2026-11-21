"""`ship_loop --action=reconcile`: claims in LOOP.* vs facts in git/GitHub.

Every test stubs `openharness.verify.{git_facts,pr_state,checks_state,_git}` so
the suite never touches a network or a real repository; the point is the
comparison logic, not the transport.
"""

import re
import sys
import textwrap
import types
from pathlib import Path

import pytest

from openharness import evidence
from openharness import verify
from openharness.skill import SkillError
from skills.product.ship_loop import ship_loop
from skills.product.spec_scaffold import spec_scaffold
from skills.product.wave_plan import wave_plan

BACKLOG = textwrap.dedent("""\
    # Backlog: Cart

    ## US1 — Add item
    - Scenarios: @w1
    - Size: S

    ## US2 — Checkout
    - Scenarios: @w2
    - Depends: US1
    - Size: M
    """)

FEATURE = textwrap.dedent("""\
    Feature: Cart

      @w1
      Scenario: add an item
        Given a cart
        When I add an item
        Then it appears

      @w2
      Scenario: checkout
        Given a full cart
        When I check out
        Then an order exists
    """)


def _spec(root: Path, name: str = "cart-checkout") -> Path:
    spec_scaffold.invoke(repo_path=str(root), feature=name, output_dir="specs")
    d = root / "specs" / name
    (d / "BACKLOG.md").write_text(BACKLOG)
    (d / "EXAMPLES.feature").write_text(FEATURE)
    wave_plan.invoke(spec_dir=str(d))
    # Reconcile tests check git/GitHub drift, not policy gates — reset the
    # scaffold's default design-challenge gate.
    (d / "GATES.md").write_text("# Gates: Cart\n\nNo gates defined yet.\n")
    _bundles(root, name)
    return d


def _bundles(root: Path, name: str) -> None:
    """A rendered, verifiable evidence bundle per planned wave (ADR 0007)."""
    waves_md = root / "specs" / name / "WAVES.md"
    text = waves_md.read_text() if waves_md.is_file() else ""
    waves = sorted(
        {int(n) for n in re.findall(r"^##\s+Wave\s+(\d+)", text, re.M)}
    ) or [1]
    for wave in waves:
        b = evidence.new_bundle(
            root, name, wave=wave, head="abc1234", run=f"run-w{wave}"
        )
        (b / "index.html").write_text("<html/>")
        _tdd_steps(b)


def _tdd_steps(bundle: Path) -> None:
    """The ordered red -> green -> refactor runs ship_loop requires (ADR 0008)."""
    py = f'"{sys.executable}"'
    evidence.record_step(
        bundle, title="RED", tdd="red", expected_failure=True,
        cmd=f"{py} -c \"import sys; sys.exit(1)\"",
    )
    evidence.record_step(bundle, title="GREEN", tdd="green", cmd=f"{py} -c \"pass\"")
    evidence.record_step(bundle, title="REFACTOR", tdd="refactor", cmd=f"{py} -c \"pass\"")


def _run(root: Path, **kw):
    kw.setdefault("review", "advisory")
    return ship_loop.invoke(repo_path=str(root), **kw)


FACTS = {
    "branch": "main",
    "head": "abc1234",
    "default_branch": "main",
    "branches": {"main", "feat/cart-checkout-w1", "feat/cart-checkout-w2"},
    "dirty": [],
    "slug": "acme/cart",
}

MERGED_PR = {
    "number": 15,
    "state": "closed",
    "merged": True,
    "merge_commit_sha": "3ed99af2aa",
    "head_ref": "feat/cart-checkout-w1",
    "head_sha": "4fed1de",
    "base_ref": "main",
    "url": "https://github.com/acme/cart/pull/15",
}


@pytest.fixture()
def facts(monkeypatch):
    """Fake git facts; returns a setter so a test can mutate them."""
    state = dict(FACTS)

    def setter(**kw):
        state.update(kw)
        return state

    monkeypatch.setattr(verify, "git_facts", lambda repo: dict(state))
    # ancestry check: pretend the merge commit is reachable
    monkeypatch.setattr(verify, "_git", lambda repo, *a: types.SimpleNamespace(returncode=0, stdout="", stderr=""))
    return setter


@pytest.fixture()
def github(monkeypatch):
    """Fake GitHub: register PRs and CI states per SHA."""
    prs: dict[int, dict | None] = {}
    checks: dict[str, dict] = {}

    def pr(number, **kw):
        prs[number] = {**MERGED_PR, "number": number, **kw}

    def no_pr(number):
        prs[number] = None

    def ci(sha, state="success", total=4, failed=()):
        checks[sha] = {"state": state, "total": total, "failed": list(failed)}

    def pr_state(repo, number):
        if number not in prs:
            raise AssertionError(f"unexpected PR #{number}")
        return prs[number]

    def checks_state(repo, ref):
        return checks.get(ref, {"state": "success", "total": 4, "failed": []})

    monkeypatch.setattr(verify, "pr_state", pr_state)
    monkeypatch.setattr(verify, "checks_state", checks_state)
    return {"pr": pr, "no_pr": no_pr, "ci": ci, "prs": prs, "checks": checks}


def _loop_through_wave1(root: Path) -> Path:
    d = _spec(root)
    _run(root, spec_dir=str(d), action="start", wave=1)
    _run(root, spec_dir=str(d), action="complete", wave=1, pr="#15", note="pytest 12 passed; CI green")
    return d


# --------------------------------------------------------------- clean loop

def test_clean_loop_reports_ok(tmp_path, facts, github):
    d = _loop_through_wave1(tmp_path)
    _run(tmp_path, spec_dir=str(d), action="start", wave=2)
    github["pr"](15)
    github["ci"]("3ed99af2aa")

    out = _run(tmp_path, spec_dir=str(d), action="reconcile")

    assert "OK — LOOP state matches git and GitHub" in out
    assert "PR #15 merged into `main` at 3ed99af2" in out
    assert "wave 2: in progress on `feat/cart-checkout-w2`" in out


def test_reconcile_is_read_only(tmp_path, facts, github):
    d = _loop_through_wave1(tmp_path)
    github["pr"](15)
    before = (d / "LOOP.state.json").read_text()

    _run(tmp_path, spec_dir=str(d), action="check")

    assert (d / "LOOP.state.json").read_text() == before


# --------------------------------------------------------------------- drift

def test_open_pr_recorded_as_done_is_drift(tmp_path, facts, github):
    d = _loop_through_wave1(tmp_path)
    github["pr"](15, merged=False, state="open")

    with pytest.raises(SkillError) as err:
        _run(tmp_path, spec_dir=str(d), action="reconcile")

    message = str(err.value)
    assert "DRIFT (1)" in message
    assert "PR #15 is open — recorded as done, but never merged" in message
    assert "reset --wave=1" in message


def test_missing_pr_is_drift(tmp_path, facts, github):
    d = _loop_through_wave1(tmp_path)
    github["no_pr"](15)

    with pytest.raises(SkillError) as err:
        _run(tmp_path, spec_dir=str(d), action="reconcile")

    assert "PR #15 does not exist" in str(err.value)


def test_ci_failure_is_drift(tmp_path, facts, github):
    d = _loop_through_wave1(tmp_path)
    github["pr"](15)
    github["ci"]("3ed99af2aa", state="failure", failed=["Backend tests"])

    with pytest.raises(SkillError) as err:
        _run(tmp_path, spec_dir=str(d), action="reconcile")

    assert "CI failed for PR #15: Backend tests" in str(err.value)


def test_unfinished_ci_is_drift(tmp_path, facts, github):
    d = _loop_through_wave1(tmp_path)
    github["pr"](15)
    github["ci"]("3ed99af2aa", state="pending", total=4)

    with pytest.raises(SkillError) as err:
        _run(tmp_path, spec_dir=str(d), action="reconcile")

    assert "CI for PR #15 has not finished (4 checks)" in str(err.value)


def test_merge_off_the_default_branch_is_drift(tmp_path, facts, github):
    d = _loop_through_wave1(tmp_path)
    github["pr"](15, base_ref="develop")

    with pytest.raises(SkillError) as err:
        _run(tmp_path, spec_dir=str(d), action="reconcile")

    message = str(err.value)
    assert "merged into `develop`, not the default `main`" in message


def test_pr_head_mismatch_is_drift(tmp_path, facts, github):
    d = _loop_through_wave1(tmp_path)
    github["pr"](15, head_ref="feat/something-else")

    with pytest.raises(SkillError) as err:
        _run(tmp_path, spec_dir=str(d), action="reconcile")

    assert "PR #15 came from `feat/something-else`, but LOOP records `feat/cart-checkout-w1`" in str(err.value)


def test_merge_commit_missing_from_default_branch_is_drift(tmp_path, facts, github, monkeypatch):
    d = _loop_through_wave1(tmp_path)
    github["pr"](15)
    monkeypatch.setattr(
        verify, "_git",
        lambda repo, *a: types.SimpleNamespace(returncode=1, stdout="", stderr=""),
    )

    with pytest.raises(SkillError) as err:
        _run(tmp_path, spec_dir=str(d), action="reconcile")

    assert "is not on `origin/main`" in str(err.value)


def test_missing_in_progress_branch_is_drift(tmp_path, facts, github):
    d = _loop_through_wave1(tmp_path)
    _run(tmp_path, spec_dir=str(d), action="start", wave=2)
    facts(branches={"main", "feat/cart-checkout-w1"})
    github["pr"](15)

    with pytest.raises(SkillError) as err:
        _run(tmp_path, spec_dir=str(d), action="reconcile")

    assert "`feat/cart-checkout-w2`, which exists neither locally nor on origin" in str(err.value)


def test_done_wave_without_pr_is_drift(tmp_path, facts, github):
    d = _spec(tmp_path)
    _run(tmp_path, spec_dir=str(d), action="start", wave=1)
    _run(tmp_path, spec_dir=str(d), action="complete", wave=1, note="tests pass, forgot the PR")

    with pytest.raises(SkillError) as err:
        _run(tmp_path, spec_dir=str(d), action="reconcile")

    assert "recorded done without a PR reference" in str(err.value)


def test_feature_done_with_pending_wave_is_drift(tmp_path, facts, github):
    d = _loop_through_wave1(tmp_path)
    (d / "VALIDATION.md").write_text("# Validation\n")
    github["pr"](15)
    _run(tmp_path, spec_dir=str(d), action="finish", force=True)

    with pytest.raises(SkillError) as err:
        _run(tmp_path, spec_dir=str(d), action="reconcile")

    assert "marked done but waves 2 are not done" in str(err.value)


def test_state_wave_absent_from_the_plan_is_drift(tmp_path, facts, github):
    d = _loop_through_wave1(tmp_path)
    github["pr"](15)
    import json

    state_file = d / "LOOP.state.json"
    payload = json.loads(state_file.read_text())
    payload["waves"]["9"] = {
        "status": "in-progress",
        "branch": "feat/leftover",
        "pr": "—",
        "evidence": "—",
        "updated": "2026-01-01T00:00:00Z",
    }
    state_file.write_text(json.dumps(payload))

    with pytest.raises(SkillError) as err:
        _run(tmp_path, spec_dir=str(d), action="reconcile")

    assert "wave 9: recorded in LOOP state but not planned in WAVES.md" in str(err.value)


# -------------------------------------------------------------- unverifiable

def test_unchecked_pr_is_reported_not_assumed(tmp_path, facts, github):
    d = _loop_through_wave1(tmp_path)

    with pytest.raises(SkillError) as err:
        _run(tmp_path, spec_dir=str(d), action="reconcile", offline=True)

    message = str(err.value)
    assert "UNVERIFIED (1)" in message
    assert "PR #15 not checked (--offline)" in message


def test_github_without_token_is_loud(tmp_path, facts, monkeypatch):
    d = _loop_through_wave1(tmp_path)
    monkeypatch.setattr(verify, "remote_slug", lambda repo: "acme/cart")

    def no_token():
        raise verify.VerifyUnavailable("no GH_TOKEN/GITHUB_TOKEN set — set one to verify PRs and CI")

    monkeypatch.setattr(verify, "_token", no_token)

    with pytest.raises(SkillError) as err:
        _run(tmp_path, spec_dir=str(d), action="reconcile")

    assert "UNVERIFIED" in str(err.value)
    assert "no GH_TOKEN" in str(err.value)


def test_non_git_repo_is_loud(tmp_path):
    d = _spec(tmp_path)

    with pytest.raises(SkillError) as err:
        _run(tmp_path, spec_dir=str(d), action="reconcile")

    assert "is not a git repository" in str(err.value)


def test_dirty_worktree_is_a_warning_not_drift(tmp_path, facts, github):
    d = _loop_through_wave1(tmp_path)
    github["pr"](15)
    facts(dirty=[" M specs/cart-checkout/BACKLOG.md"])

    out = _run(tmp_path, spec_dir=str(d), action="reconcile")

    assert "True right now, not drift:" in out
    assert "BACKLOG.md" in out
    assert "OK — LOOP state matches git and GitHub" in out
