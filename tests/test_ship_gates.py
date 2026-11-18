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
    spec_scaffold.invoke(repo_path=str(root), feature=name, output_dir="specs")
    d = root / "specs" / name
    (d / "BACKLOG.md").write_text(BACKLOG)
    (d / "EXAMPLES.feature").write_text(FEATURE)
    wave_plan.invoke(spec_dir=str(d))
    # Gate tests declare their own GATES.md; reset the scaffold's default
    # design-challenge gate so each test starts from a clean slate.
    (d / "GATES.md").write_text("# Gates: Cart\n\nNo gates defined yet.\n")
    b = root / ".openharness" / "evidence" / name / "run-1"
    b.mkdir(parents=True, exist_ok=True)
    (b / "index.html").write_text("<html/>")
    return d


def _gates(d: Path, *blocks: str) -> None:
    (d / "GATES.md").write_text("# Gates: Cart\n\n" + "\n\n".join(blocks) + "\n")


def _gate(gid: str, title: str, before: str, **fields) -> str:
    lines = [f"## {gid} — {title}", f"- Before: {before}"]
    for key, value in fields.items():
        lines.append(f"- {key.replace('_', ' ').title()}: {value}")
    return "\n".join(lines)


def _run(root: Path, **kw) -> str:
    # These tests exercise gate mechanics, not the review policy — run
    # advisory so audit artifacts are not required.
    kw.setdefault("review", "advisory")
    return ship_loop.invoke(repo_path=str(root), **kw)


def _finish_waves(root: Path, d: Path) -> None:
    _run(root, action="start", wave=1)
    _run(root, action="complete", wave=1, note="ok")
    _run(root, action="start", wave=2)
    _run(root, action="complete", wave=2, note="ok")


# ---------- authoring / compatibility ----------

def test_scaffold_creates_design_challenge_gate(tmp_path):
    spec_scaffold.invoke(repo_path=str(tmp_path), feature="Cart Checkout", output_dir="specs")
    gates = tmp_path / "specs" / "cart-checkout" / "GATES.md"
    assert gates.is_file()
    text = gates.read_text()
    assert "G1 — Design decisions challenged" in text
    assert "Before: plan" in text and "Blocking: yes" in text
    assert "DECISION-REVIEW.md" in text


def test_no_gates_file_is_backwards_compatible(tmp_path):
    d = _spec(tmp_path)
    (d / "GATES.md").unlink()
    out = _run(tmp_path)
    assert "implement wave 1" in out
    assert "gates" not in out.splitlines()[1]


def test_advisory_gate_does_not_block(tmp_path):
    d = _spec(tmp_path)
    _gates(d, _gate("G1", "Nice to have", "wave:1", Type="quality", Blocking="no"))
    out = _run(tmp_path)
    assert "implement wave 1" in out


# ---------- phase gates ----------

def test_gate_before_spec_blocks_spec_phase(tmp_path):
    d = tmp_path / "specs" / "cart-checkout"
    d.mkdir(parents=True)
    _gates(d, _gate("G1", "Domain glossary agreed", "spec", Type="decision",
                    Owner="product-owner", Resolver="human", Check="manual"))
    out = _run(tmp_path)
    assert "GATE: 1 blocking precondition" in out
    assert "before writing the spec" in out
    assert "G1 — Domain glossary agreed" in out
    assert "next (human)" in out and "--action=block" in out


def test_gate_before_plan_blocks_plan_phase(tmp_path):
    d = _spec(tmp_path)
    (d / "WAVES.md").unlink()
    _gates(d, _gate("G1", "Data contract agreed", "plan", Type="artifact",
                    Resolver="agent", Check="manual"))
    out = _run(tmp_path)
    assert "GATE:" in out
    assert "before planning waves" in out
    assert "next (agent)" in out
    out = _run(tmp_path, action="gate", gate="G1", status="met", evidence="docs/data.md")
    assert "Gate G1 met." in out
    assert "plan waves" in out


def test_gate_before_wave_blocks_next_and_start(tmp_path):
    d = _spec(tmp_path)
    _gates(d, _gate("G1", "Seed data loaded", "wave:1", Type="data",
                    Resolver="agent", Check="command:make seed"))
    out = _run(tmp_path)
    assert "GATE:" in out and "before starting wave 1" in out
    out = _run(tmp_path, action="start", wave=1)
    assert "GATE:" in out
    _run(tmp_path, action="gate", gate="G1", status="met", evidence="make seed → 0")
    out = _run(tmp_path)
    assert "implement wave 1" in out


def test_gate_before_validate_blocks_validation(tmp_path):
    d = _spec(tmp_path)
    _finish_waves(tmp_path, d)
    _gates(d, _gate("G1", "UAT environment ready", "validate", Type="external",
                    Resolver="human", Check="manual"))
    out = _run(tmp_path)
    assert "GATE:" in out and "before validation" in out


def test_overdue_gate_still_blocks_later_phase(tmp_path):
    d = _spec(tmp_path)
    _gates(d, _gate("G1", "Coverage rules signed off", "spec", Type="decision",
                    Resolver="human", Check="manual"))
    out = _run(tmp_path)
    assert "GATE:" in out and "before starting wave 1" in out
    assert "G1 — Coverage rules signed off" in out and "before spec" in out


def test_future_gate_does_not_block_earlier_phase(tmp_path):
    d = _spec(tmp_path)
    _gates(d, _gate("G2", "UAT environment", "wave:2", Type="external",
                    Resolver="human", Check="manual"))
    out = _run(tmp_path)
    assert "implement wave 1" in out
    assert "G2" not in out


def test_gate_before_finish_blocks_auto_done_and_finish(tmp_path):
    d = _spec(tmp_path)
    _finish_waves(tmp_path, d)
    (d / "VALIDATION.md").write_text("# Validation\n")
    _gates(d, _gate("G1", "Legal sign-off", "finish", Type="quality",
                    Resolver="human", Check="manual"))
    out = _run(tmp_path)
    assert "GATE:" in out and "before closing the feature" in out
    out = _run(tmp_path, action="finish")
    assert "GATE:" in out
    _run(tmp_path, action="gate", gate="G1", status="met", evidence="legal ticket LAW-7")
    out = _run(tmp_path)
    assert out.startswith("DONE")


# ---------- checks / waivers ----------

def test_file_gate_requires_existing_file_and_detects_stale_evidence(tmp_path):
    d = _spec(tmp_path)
    (d / "WAVES.md").unlink()
    _gates(d, _gate("G1", "Data contract", "plan", Type="artifact",
                    Resolver="agent", Check="file:docs/data-contract.md"))
    out = _run(tmp_path, action="gate", gate="G1", status="met", evidence="file:docs/data-contract.md")
    assert out.startswith("ERROR") and "does not exist" in out
    _write(tmp_path, "docs/data-contract.md", "# Contract\n")
    assert "Gate G1 met." in _run(tmp_path, action="gate", gate="G1", status="met",
                                  evidence="file:docs/data-contract.md")
    (tmp_path / "docs" / "data-contract.md").unlink()
    out = _run(tmp_path)
    assert "GATE:" in out and "[stale]" in out


def test_waiver_requires_waived_by_and_reason(tmp_path):
    d = _spec(tmp_path)
    _gates(d, _gate("G1", "Tax sandbox", "wave:1", Type="external",
                    Resolver="human", Check="manual"))
    out = _run(tmp_path, action="gate", gate="G1", status="waived")
    assert out.startswith("ERROR") and "--waived-by" in out
    out = _run(tmp_path, action="gate", gate="G1", status="waived", waived_by="hamza")
    assert out.startswith("ERROR") and "--note" in out
    out = _run(tmp_path, action="gate", gate="G1", status="waived",
               waived_by="hamza", note="sandbox unavailable until Q1")
    assert "Gate G1 waived." in out
    assert "implement wave 1" in out
    loop = (d / "LOOP.md").read_text()
    assert "waived by hamza" in loop
    assert "| G1 | waived |" in loop


def test_gate_action_validates_ids_and_statuses(tmp_path):
    d = _spec(tmp_path)
    _gates(d, _gate("G1", "Thing", "wave:1", Resolver="agent"))
    out = _run(tmp_path, action="gate", gate="G9", status="met", evidence="x")
    assert out.startswith("ERROR") and "not defined" in out
    out = _run(tmp_path, action="gate", gate="G1", status="maybe", evidence="x")
    assert out.startswith("ERROR") and "--status must be" in out
    out = _run(tmp_path, action="gate", gate="G1", status="met")
    assert out.startswith("ERROR") and "--evidence is required" in out


def test_invalid_before_blocks_with_fix_instruction(tmp_path):
    d = _spec(tmp_path)
    _gates(d, _gate("G1", "Broken phase", "deployment", Resolver="agent"))
    out = _run(tmp_path)
    assert "GATE:" in out and "[invalid]" in out
    assert "fix: set `- Before:`" in out


def test_gate_state_persists_and_events_logged(tmp_path):
    d = _spec(tmp_path)
    _gates(d, _gate("G1", "Seed data", "wave:1", Type="data", Resolver="agent"))
    _run(tmp_path, action="gate", gate="G1", status="met", evidence="seeded 42 rows")
    loop = (d / "LOOP.md").read_text()
    assert "## Gates" in loop
    assert "| G1 | met | seeded 42 rows |" in loop
    assert "gate G1 met: seeded 42 rows" in loop
    assert "gates 1/1 met" in _run(tmp_path, action="status")


def test_summary_counts_pending_blocking_gates(tmp_path):
    d = _spec(tmp_path)
    _gates(
        d,
        _gate("G1", "Met gate", "wave:1", Resolver="agent"),
        _gate("G2", "Pending gate", "wave:2", Resolver="human"),
    )
    _run(tmp_path, action="gate", gate="G1", status="met", evidence="done")
    out = _run(tmp_path, action="status")
    assert "gates 1/2 met" in out
    assert "(1 blocking pending)" in out


def test_gate_failure_blocks_and_can_be_retried(tmp_path):
    d = _spec(tmp_path)
    _gates(d, _gate("G1", "Load test", "wave:1", Type="technical",
                    Resolver="agent", Check="command:make load"))
    _run(tmp_path, action="gate", gate="G1", status="failed", note="p95 900ms > 300ms")
    out = _run(tmp_path)
    assert "GATE:" in out and "[failed]" in out
    _run(tmp_path, action="gate", gate="G1", status="met", evidence="p95 210ms")
    assert "implement wave 1" in _run(tmp_path)
