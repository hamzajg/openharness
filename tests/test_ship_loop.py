import textwrap
from pathlib import Path

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


def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def _spec(root: Path, name: str = "cart-checkout") -> Path:
    """Scaffold a feature and fill enough artifacts to plan waves."""
    spec_scaffold.invoke(repo_path=str(root), feature=name, output_dir="specs")
    d = root / "specs" / name
    (d / "BACKLOG.md").write_text(BACKLOG)
    (d / "EXAMPLES.feature").write_text(FEATURE)
    wave_plan.invoke(spec_dir=str(d))
    # Loop defaults are enforced now: satisfy the scaffold's G1
    # design-challenge gate and the required spec audit so wave-mechanics
    # tests exercise the loop, not the policy gates.
    (d / "DECISION-REVIEW.md").write_text("# Decision review\n\nVERDICT: ACCEPT\n")
    ship_loop.invoke(
        repo_path=str(root), spec_dir=str(d), action="gate", gate="G1",
        status="met",
        evidence=f"file:{d.relative_to(root)}/DECISION-REVIEW.md",
    )
    (d / "SPEC-AUDIT.md").write_text("# Audit\n\nAUDIT: PASS\n")
    _bundle(root, name)
    return d


def _bundle(root: Path, feature: str) -> Path:
    """A rendered evidence bundle — required before wave complete/finish."""
    b = root / ".openharness" / "evidence" / feature / "run-1"
    b.mkdir(parents=True, exist_ok=True)
    (b / "index.html").write_text("<html>walkthrough</html>")
    return b


def _run(root: Path, **kw) -> str:
    return ship_loop.invoke(repo_path=str(root), **kw)


# ---------- framing / artifact gates ----------

def test_no_specs_returns_frame_guidance(tmp_path):
    out = _run(tmp_path)
    assert "no specs yet" in out
    assert "discover_product" in out
    assert "spec_scaffold" in out


def test_missing_artifacts_ask_for_spec(tmp_path):
    d = tmp_path / "specs" / "half-baked"
    d.mkdir(parents=True)
    out = _run(tmp_path)
    assert "complete the spec for half-baked" in out
    assert "SPEC.md" in out and "BACKLOG.md" in out


def test_scaffolded_without_waves_asks_for_plan(tmp_path):
    spec_scaffold.invoke(repo_path=str(tmp_path), feature="Cart Checkout", output_dir="specs")
    d = tmp_path / "specs" / "cart-checkout"
    # G1 (design decisions challenged) blocks planning until the review
    # artifact exists; the required spec audit blocks it next.
    out = _run(tmp_path)
    assert "GATE:" in out and "G1" in out
    assert "DECISION-REVIEW.md" in out
    (d / "DECISION-REVIEW.md").write_text("# Review\n\nVERDICT: ACCEPT\n")
    _run(tmp_path, action="gate", gate="G1", status="met",
         evidence="file:specs/cart-checkout/DECISION-REVIEW.md")
    out = _run(tmp_path)
    assert "audit the spec" in out and "SPEC-AUDIT.md" in out
    (d / "SPEC-AUDIT.md").write_text("# Audit\n\nAUDIT: PASS\n")
    out = _run(tmp_path)
    assert "plan waves for cart-checkout" in out
    assert "wave_plan" in out


def test_plan_stage_lists_wave_scenarios_and_items(tmp_path):
    _spec(tmp_path)
    out = _run(tmp_path)
    assert "implement wave 1" in out
    assert "add an item" in out
    assert "US1 — Add item" in out
    assert "feat/cart-checkout-w1" in out


# ---------- wave state machine ----------

def test_start_then_complete_advances_to_next_wave(tmp_path):
    d = _spec(tmp_path)
    assert "Recorded wave 1 in progress" in _run(tmp_path, action="start", wave=1)
    out = _run(tmp_path, action="complete", wave=1, pr="#1", note="2/2 tests, CI green")
    assert "Recorded wave 1 done" in out
    assert "implement wave 2" in out
    state = (d / "LOOP.md").read_text()
    assert "| 1 | done |" in state
    assert "#1" in state and "2/2 tests, CI green" in state


def test_start_can_be_repeated_while_wave_is_in_progress(tmp_path):
    _spec(tmp_path)
    _run(tmp_path, action="start", wave=1)
    out = _run(tmp_path, action="start", wave=1)
    assert "Recorded wave 1 in progress" in out
    _run(tmp_path, action="complete", wave=1, note="ok")
    out = _run(tmp_path, action="start", wave=1)
    assert out.startswith("ERROR") and "already done" in out
    out = _run(tmp_path, action="start", wave=1, force=True)
    assert "Recorded wave 1 in progress" in out


def test_start_rejects_out_of_order_wave(tmp_path):
    _spec(tmp_path)
    out = _run(tmp_path, action="start", wave=2)
    assert out.startswith("ERROR") and "wave 1 is not done" in out


def test_start_rejects_unknown_wave(tmp_path):
    _spec(tmp_path)
    out = _run(tmp_path, action="start", wave=9)
    assert out.startswith("ERROR") and "not in WAVES.md" in out


def test_start_requires_planned_waves(tmp_path):
    spec_scaffold.invoke(repo_path=str(tmp_path), feature="Cart", output_dir="specs")
    d = tmp_path / "specs" / "cart"
    (d / "BACKLOG.md").write_text(BACKLOG)
    (d / "EXAMPLES.feature").write_text(FEATURE)
    out = _run(tmp_path, action="start", wave=1)
    assert out.startswith("ERROR") and "wave_plan first" in out


def test_complete_requires_started_wave_and_note(tmp_path):
    _spec(tmp_path)
    out = _run(tmp_path, action="complete", wave=1, note="done")
    assert out.startswith("ERROR") and "not in-progress" in out
    _run(tmp_path, action="start", wave=1)
    out = _run(tmp_path, action="complete", wave=1)
    assert out.startswith("ERROR") and "--note is required" in out


def test_resume_reports_in_progress_wave(tmp_path):
    _spec(tmp_path)
    _run(tmp_path, action="start", wave=1)
    out = _run(tmp_path)
    assert "resume wave 1" in out
    assert "LOOP.md" in out


def test_last_wave_complete_requests_validation(tmp_path):
    _spec(tmp_path)
    _run(tmp_path, action="start", wave=1)
    _run(tmp_path, action="complete", wave=1, note="ok")
    _run(tmp_path, action="start", wave=2)
    out = _run(tmp_path, action="complete", wave=2, note="ok")
    assert "validate cart-checkout" in out
    assert "ship_validate" in out


# ---------- validation / completion ----------

def test_next_marks_feature_done_when_validation_exists(tmp_path):
    d = _spec(tmp_path)
    _run(tmp_path, action="start", wave=1)
    _run(tmp_path, action="complete", wave=1, note="ok")
    _run(tmp_path, action="start", wave=2)
    _run(tmp_path, action="complete", wave=2, note="ok")
    (d / "VALIDATION.md").write_text("# Validation\n")
    (d / "DELIVERY-AUDIT.md").write_text("# Audit\n\nAUDIT: PASS\n")
    out = _run(tmp_path)
    assert out.startswith("DONE")
    assert "Status: done" in (d / "LOOP.md").read_text()


def test_finish_requires_validation_and_finished_waves(tmp_path):
    d = _spec(tmp_path)
    _run(tmp_path, action="start", wave=1)
    out = _run(tmp_path, action="finish")
    assert out.startswith("ERROR") and "not done" in out
    (d / "VALIDATION.md").write_text("# Validation\n")
    out = _run(tmp_path, action="finish")
    assert out.startswith("ERROR") and "not done" in out
    (d / "DELIVERY-AUDIT.md").write_text("# Audit\n\nAUDIT: PASS\n")
    out = _run(tmp_path, action="finish", force=True)
    assert "marked done" in out
    assert "Status: done" in (d / "LOOP.md").read_text()


def test_finish_requires_validation_file(tmp_path):
    d = _spec(tmp_path)
    _run(tmp_path, action="start", wave=1)
    _run(tmp_path, action="complete", wave=1, note="ok")
    _run(tmp_path, action="start", wave=2)
    _run(tmp_path, action="complete", wave=2, note="ok")
    out = _run(tmp_path, action="finish")
    assert out.startswith("ERROR") and "VALIDATION.md is missing" in out
    (d / "VALIDATION.md").write_text("# Validation\n")
    (d / "DELIVERY-AUDIT.md").write_text("# Audit\n\nAUDIT: PASS\n")
    assert "marked done" in _run(tmp_path, action="finish")


# ---------- blocking ----------

def test_block_and_resume(tmp_path):
    _spec(tmp_path)
    out = _run(tmp_path, action="block", note="needs a product decision on pricing")
    assert out.startswith("BLOCKED")
    out = _run(tmp_path)
    assert out.startswith("BLOCKED") and "needs a product decision" in out
    out = _run(tmp_path, action="resume")
    assert "Resumed cart-checkout" in out
    assert "implement wave 1" in _run(tmp_path)


def test_block_requires_reason(tmp_path):
    _spec(tmp_path)
    out = _run(tmp_path, action="block")
    assert out.startswith("ERROR") and "--note is required" in out


# ---------- budget / iteration accounting ----------

def test_next_stops_at_iteration_budget(tmp_path):
    _spec(tmp_path)
    for _ in range(3):
        assert "STOP" not in _run(tmp_path, max_iterations=3)
    out = _run(tmp_path, max_iterations=3)
    assert out.startswith("STOP")
    assert "3/3" in out


def test_status_does_not_increment_iterations(tmp_path):
    d = _spec(tmp_path)
    _run(tmp_path)  # one `next` → iterations 1
    _run(tmp_path, action="status")
    _run(tmp_path, action="status")
    text = (d / "LOOP.md").read_text()
    assert "Iterations: 1" in text


# ---------- reset ----------

def test_reset_wave_returns_it_to_pending(tmp_path):
    _spec(tmp_path)
    _run(tmp_path, action="start", wave=1)
    out = _run(tmp_path, action="reset", wave=1)
    assert "Reset cart-checkout" in out
    assert "| 1 | pending |" in (tmp_path / "specs" / "cart-checkout" / "LOOP.md").read_text()


def test_full_reset_requires_force(tmp_path):
    _spec(tmp_path)
    out = _run(tmp_path, action="reset")
    assert out.startswith("ERROR") and "--force" in out
    _run(tmp_path, action="start", wave=1)
    out = _run(tmp_path, action="reset", force=True)
    assert "Reset cart-checkout" in out
    text = (tmp_path / "specs" / "cart-checkout" / "LOOP.md").read_text()
    assert "Iterations: 0" in text and "| 1 | pending |" in text


# ---------- evidence bundles (ADR 0007) ----------

def test_complete_requires_rendered_evidence_bundle(tmp_path):
    _spec(tmp_path)
    import shutil
    shutil.rmtree(tmp_path / ".openharness" / "evidence" / "cart-checkout")
    _run(tmp_path, action="start", wave=1)
    out = _run(tmp_path, action="complete", wave=1, note="ok")
    assert out.startswith("ERROR") and "harness_evidence" in out
    # An unrendered bundle (no index.html) does not count either.
    b = tmp_path / ".openharness" / "evidence" / "cart-checkout" / "run-1"
    b.mkdir(parents=True)
    (b / "evidence.json").write_text("{}")
    out = _run(tmp_path, action="complete", wave=1, note="ok")
    assert out.startswith("ERROR") and "harness_evidence" in out
    (b / "index.html").write_text("<html/>")
    assert "Recorded wave 1 done" in _run(tmp_path, action="complete", wave=1, note="ok")


def test_finish_requires_rendered_evidence_bundle(tmp_path):
    d = _spec(tmp_path)
    _run(tmp_path, action="start", wave=1)
    _run(tmp_path, action="complete", wave=1, note="ok")
    _run(tmp_path, action="start", wave=2)
    _run(tmp_path, action="complete", wave=2, note="ok")
    (d / "VALIDATION.md").write_text("# Validation\n")
    (d / "DELIVERY-AUDIT.md").write_text("# Audit\n\nAUDIT: PASS\n")
    import shutil
    shutil.rmtree(tmp_path / ".openharness" / "evidence" / "cart-checkout")
    out = _run(tmp_path, action="finish")
    assert out.startswith("ERROR") and "harness_evidence" in out


# ---------- multi-feature / errors ----------

def test_moves_to_next_feature_after_one_is_done(tmp_path):
    first = _spec(tmp_path)
    second = _spec(tmp_path, "wishlist")
    for d in (first, second):
        _run(tmp_path, action="start", wave=1)
        _run(tmp_path, action="complete", wave=1, note="ok")
        _run(tmp_path, action="start", wave=2)
        _run(tmp_path, action="complete", wave=2, note="ok")
        (d / "VALIDATION.md").write_text("# Validation\n")
        (d / "DELIVERY-AUDIT.md").write_text("# Audit\n\nAUDIT: PASS\n")
    out = _run(tmp_path, action="finish")
    assert "wishlist" in out
    out = _run(tmp_path)
    assert "Delivery loop — wishlist" in out


def test_done_when_every_feature_is_done(tmp_path):
    d = _spec(tmp_path)
    (d / "VALIDATION.md").write_text("# Validation\n")
    (d / "DELIVERY-AUDIT.md").write_text("# Audit\n\nAUDIT: PASS\n")
    _run(tmp_path, action="finish", force=True)
    out = _run(tmp_path)
    assert out.startswith("DONE")


def test_unknown_action_and_bad_paths(tmp_path):
    out = _run(tmp_path, action="explode")
    assert out.startswith("ERROR") and "unknown action" in out
    out = _run(tmp_path, spec_dir="specs/nope")
    assert out.startswith("ERROR") and "not found" in out
    out = ship_loop.invoke(repo_path=str(tmp_path / "missing"))
    assert out.startswith("ERROR")


def test_state_survives_reload_and_events_are_append_only(tmp_path):
    d = _spec(tmp_path)
    _run(tmp_path, action="start", wave=1)
    _run(tmp_path, action="complete", wave=1, pr="#7", note="green")
    text = (d / "LOOP.md").read_text()
    assert "## Events" in text
    assert "start wave 1" in text and "complete wave 1 (#7)" in text
    assert "(none)" not in text
    out = _run(tmp_path)
    assert "waves 1/2 done" in out


# ---------- machine-readable state ----------

def test_state_json_written_alongside_loop_md(tmp_path):
    import json
    d = _spec(tmp_path)
    _run(tmp_path, action="start", wave=1)
    state_file = d / "LOOP.state.json"
    assert state_file.is_file()
    data = json.loads(state_file.read_text())
    assert data["feature"] == "cart-checkout"
    assert data["status"] == "running"
    assert data["waves"]["1"]["status"] == "in-progress"
    # markdown render still produced for humans/PRs
    assert "| 1 | in-progress |" in (d / "LOOP.md").read_text()


def test_state_json_is_authoritative_when_present(tmp_path):
    import json
    d = _spec(tmp_path)
    _run(tmp_path, action="start", wave=1)
    # machine consumer updates JSON directly; markdown is now stale
    data = json.loads((d / "LOOP.state.json").read_text())
    data["waves"]["1"]["status"] = "done"
    (d / "LOOP.state.json").write_text(json.dumps(data))
    out = _run(tmp_path)
    assert "implement wave 2" in out  # oracle followed JSON, not stale md


def test_state_json_regenerated_on_next_mutation(tmp_path):
    import json
    d = _spec(tmp_path)
    _run(tmp_path, action="start", wave=1)
    _run(tmp_path, action="complete", wave=1, pr="#7", note="green")
    data = json.loads((d / "LOOP.state.json").read_text())
    assert data["waves"]["1"]["status"] == "done"
    assert data["waves"]["1"]["pr"] == "#7"


# ---------- independent review enforcement ----------

def _unplanned(root: Path) -> Path:
    d = _spec(root)
    (d / "WAVES.md").unlink()
    (d / "SPEC-AUDIT.md").unlink(missing_ok=True)
    return d


def _all_waves_done(root: Path) -> None:
    _run(root, action="start", wave=1)
    _run(root, action="complete", wave=1, note="2/2 tests, CI green")
    _run(root, action="start", wave=2)
    _run(root, action="complete", wave=2, note="2/2 tests, CI green")


def test_review_required_is_default_and_requires_audit(tmp_path):
    _unplanned(tmp_path)
    out = _run(tmp_path)
    assert "audit the spec" in out
    assert "SPEC-AUDIT.md" in out


def test_review_advisory_skips_audit(tmp_path):
    _unplanned(tmp_path)
    out = _run(tmp_path, review="advisory")
    assert "plan waves" in out


def test_wave1_requires_spec_audit_even_when_planned(tmp_path):
    d = _spec(tmp_path)
    (d / "SPEC-AUDIT.md").unlink()
    out = _run(tmp_path)
    assert "audit the spec" in out and "SPEC-AUDIT.md" in out
    (d / "SPEC-AUDIT.md").write_text("# Audit\n\nAUDIT: PASS\n")
    assert "implement wave 1" in _run(tmp_path)


def test_review_required_blocks_planning_without_spec_audit(tmp_path):
    _unplanned(tmp_path)
    out = _run(tmp_path, review="required")
    assert "audit the spec" in out
    assert "SPEC-AUDIT.md" in out
    assert "review_delivery" in out


def test_review_required_rejects_template_only_audit(tmp_path):
    d = _unplanned(tmp_path)
    (d / "SPEC-AUDIT.md").write_text("# Audit\n\nAUDIT: PASS | CONCERNS | BLOCK\n")
    out = _run(tmp_path, review="required")
    assert "has no filled verdict" in out


def test_review_required_allows_pass(tmp_path):
    d = _unplanned(tmp_path)
    (d / "SPEC-AUDIT.md").write_text("# Audit\n\nAUDIT: PASS\n")
    out = _run(tmp_path, review="required")
    assert "plan waves" in out


def test_review_required_allows_concerns(tmp_path):
    d = _unplanned(tmp_path)
    (d / "SPEC-AUDIT.md").write_text("# Audit\n\nAUDIT: CONCERNS\n")
    out = _run(tmp_path, review="required")
    assert "plan waves" in out


def test_review_required_blocks_on_block_verdict(tmp_path):
    d = _unplanned(tmp_path)
    (d / "SPEC-AUDIT.md").write_text("# Audit\n\nAUDIT: BLOCK\n")
    out = _run(tmp_path, review="required")
    assert "AUDIT-BLOCK" in out
    assert "SPEC-AUDIT.md" in out


def test_review_required_requires_delivery_audit_before_finish(tmp_path):
    d = _spec(tmp_path)
    _all_waves_done(tmp_path)
    (d / "VALIDATION.md").write_text("# Validation\n")
    out = _run(tmp_path, review="required")
    assert "audit the delivery" in out
    assert "DELIVERY-AUDIT.md" in out


def test_review_required_delivery_pass_marks_feature_done(tmp_path):
    d = _spec(tmp_path)
    _all_waves_done(tmp_path)
    (d / "VALIDATION.md").write_text("# Validation\n")
    (d / "DELIVERY-AUDIT.md").write_text("# Audit\n\nAUDIT: PASS\n")
    out = _run(tmp_path, review="required")
    assert out.startswith("DONE")
    assert "Status: done" in (d / "LOOP.md").read_text()


def test_review_required_finish_action_enforces_delivery_audit(tmp_path):
    d = _spec(tmp_path)
    _all_waves_done(tmp_path)
    (d / "VALIDATION.md").write_text("# Validation\n")

    out = _run(tmp_path, action="finish", review="required")
    assert "audit the delivery" in out
    assert "Status: done" not in (d / "LOOP.md").read_text()

    (d / "DELIVERY-AUDIT.md").write_text("# Audit\n\nAUDIT: BLOCK\n")
    out = _run(tmp_path, action="finish", review="required")
    assert "AUDIT-BLOCK" in out

    (d / "DELIVERY-AUDIT.md").write_text("# Audit\n\nAUDIT: CONCERNS\n")
    out = _run(tmp_path, action="finish", review="required")
    assert "marked done" in out


def test_summary_reports_review_status_when_required(tmp_path):
    d = _spec(tmp_path)
    (d / "SPEC-AUDIT.md").write_text("# Audit\n\nAUDIT: PASS\n")
    out = _run(tmp_path, action="start", wave=1, review="required")
    assert "review spec:pass delivery:missing" in out


def test_review_rejects_unknown_mode(tmp_path):
    _unplanned(tmp_path)
    out = _run(tmp_path, review="strict")
    assert out.startswith("ERROR") and "advisory|required" in out
