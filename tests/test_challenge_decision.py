import textwrap
from pathlib import Path

from skills.product.challenge_decision import challenge_decision

ADR = textwrap.dedent("""\
    # ADR 0007 — Order store: Postgres with aggregate-owned tables

    Status: proposed · 2026-11-15

    ## Context
    Orders are written by checkout and read by support. We need durable storage,
    strong consistency per order, and a migration path from the JSON file.
    Constraint: one team, a 3-week deadline, existing Postgres skills.

    ## Decision
    Store each Order aggregate in its own table with a repository per aggregate.
    Keep the domain free of SQLAlchemy; map at the persistence boundary.
    This is reversible: the repository interface lets us swap storage later.

    ## Alternatives
    - Keep the JSON file and add locking — simplest, but no query or backup story.
    - Use an event store with projections — stronger audit, higher cost.
    - Use Postgres with a generic DAO — faster now, couples use cases to tables.

    ## Consequences
    Positive: strong per-order consistency, familiar operations, testable domain.
    Negative: support read models need explicit queries; schema migrations.
    Evidence: `docs/adr/0007-order-store.md`, spike at 1200 rps, ticket ORD-42.

    ## Revisit trigger
    Reopen if write volume exceeds 5k rps or a second context needs orders.
    """)

LOW_IMPACT = textwrap.dedent("""\
    # Decision: delivery review format

    ## Context
    The team spends two hours in a weekly review with no owner and no decisions
    recorded, so the same issues return. Constraint: 30 minutes of team time.

    ## Decision
    Rename it to delivery review, cap it at 30 minutes, and record decisions in
    the team log. This is reversible: we can revert the format next quarter.

    ## Alternatives
    - Keep the current review and add an agenda — cheapest, but no ownership.
    - Replace it with async written updates — less meeting time, slower decisions.

    ## Consequences
    Positive: decisions are recorded and owned. Negative: 30 minutes still spent.
    Evidence: `docs/team/review.md`, ticket TEAM-12.
    """)


def _adr(root: Path, rel: str = "docs/adr/0007-order-store.md", text: str = ADR) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def _spec(root: Path, name: str = "orders", decisions: str | None = None) -> Path:
    d = root / "specs" / name
    d.mkdir(parents=True, exist_ok=True)
    body = decisions if decisions is not None else textwrap.dedent("""\
        - Persist Order as an aggregate in Postgres, one repository per aggregate.
          Keep SQLAlchemy out of the domain; map at the adapter boundary.
          Alternative considered: event store with projections (stronger audit, more cost).
        - Evidence: `docs/adr/0007-order-store.md`, spike at 1200 rps.
        """)
    (d / "SPEC.md").write_text(
        "# Spec: Orders\n\n## Problem\nCheckout needs durable orders; support needs "
        "to read them.\n\n## Decisions\n" + body + "\n"
    )
    return d


def _run(root: Path, **kw) -> str:
    return challenge_decision.invoke(repo_path=str(root), **kw)


# ---------- sources / errors ----------

def test_inline_minimal_is_incomplete(tmp_path):
    out = _run(tmp_path, decision="Use Postgres for the order store.")
    assert "Readiness: **INCOMPLETE**" in out
    assert "`alternatives`" in out and "`consequences`" in out
    assert "Decision review brief" in out


def test_complete_adr_has_all_elements_and_alternatives(tmp_path):
    _adr(tmp_path)
    out = _run(tmp_path, adr="docs/adr/0007-order-store.md")
    assert "Readiness: **CHALLENGE** (6/6 record elements)" in out
    assert "**Reversibility:** stated" in out
    assert "Keep the JSON file" not in out  # alternatives are counted, not dumped


def test_spec_decisions_are_read(tmp_path):
    _spec(tmp_path)
    out = _run(tmp_path, spec_dir="specs/orders")
    assert "specs/orders/SPEC.md (## Decisions)" in out
    assert "Decision review brief" in out


def test_spec_without_decisions_is_an_error(tmp_path):
    d = tmp_path / "specs" / "empty"
    d.mkdir(parents=True)
    (d / "SPEC.md").write_text("# Spec: Empty\n\n## Problem\nNothing decided yet.\n")
    out = _run(tmp_path, spec_dir="specs/empty")
    assert out.startswith("ERROR:") and "## Decisions" in out


def test_missing_adr_is_an_error(tmp_path):
    out = _run(tmp_path, adr="docs/adr/nope.md")
    assert out.startswith("ERROR:") and "ADR not found" in out


def test_no_source_is_an_error(tmp_path):
    out = _run(tmp_path)
    assert out.startswith("ERROR:") and "--adr" in out


# ---------- readiness / types ----------

def test_missing_alternatives_is_challenge_not_incomplete(tmp_path):
    no_alts = (ADR.split("## Alternatives")[0]
               + "## Consequences" + ADR.split("## Consequences", 1)[1])
    _adr(tmp_path, "docs/adr/0009-no-alts.md", no_alts)
    out = _run(tmp_path, adr="docs/adr/0009-no-alts.md")
    assert "Readiness: **CHALLENGE**" in out
    assert "`alternatives`" in out


def test_low_impact_complete_decision_is_ready(tmp_path):
    _adr(tmp_path, "docs/adr/0008-review.md", LOW_IMPACT)
    out = _run(tmp_path, adr="docs/adr/0008-review.md")
    assert "Detected type: process" in out
    assert "Readiness: **READY**" in out


def test_high_impact_complete_decision_still_challenges(tmp_path):
    _adr(tmp_path)
    out = _run(tmp_path, adr="docs/adr/0007-order-store.md")
    assert "CHALLENGE" in out
    assert "Detected type:" in out and "data" in out


def test_type_detection_api(tmp_path):
    out = _run(tmp_path, decision=(
        "Expose a REST endpoint for orders, version the contract, and keep "
        "backward compatibility for existing payload consumers."
    ))
    assert "Detected type: api" in out


def test_type_detection_defaults_to_architecture(tmp_path):
    out = _run(tmp_path, decision="Do the thing.")
    assert "Detected type: architecture" in out


# ---------- signals ----------

def _domain_file(root: Path, text: str) -> Path:
    p = root / "src" / "domain" / "order.py"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(text))
    return p


def test_signals_flag_framework_io_and_anemic_model(tmp_path):
    _domain_file(tmp_path, """\
        from fastapi import HTTPException
        import requests

        class Order:
            def __init__(self):
                self.id = None
                self.status = None
                self.total = 0

            def get_id(self): return self.id
            def get_status(self): return self.status
            def get_total(self): return self.total
            def set_status(self, s): self.status = s

            def confirm(self):
                if self.total <= 0:
                    raise ValueError("invariant: total must be positive")
        """)
    out = _run(tmp_path, decision=(
        "Persist orders in Postgres with a repository per aggregate. "
        "Evidence: docs/adr/0007.md. Reversible via the repository interface."
    ), paths="src/domain")
    assert "domain code imports a framework/ORM" in out
    assert "domain code performs external I/O" in out
    assert "getter/setter-heavy" in out
    assert "no test file references" in out
    assert "invariant/guard vocabulary" in out


def test_signal_detects_test_reference(tmp_path):
    _domain_file(tmp_path, "class Order:\n    def confirm(self):\n        return True\n")
    t = tmp_path / "tests" / "test_order.py"
    t.parent.mkdir()
    t.write_text("from src.domain.order import Order\n\ndef test_order():\n    assert Order()\n")
    out = _run(tmp_path, decision="Keep the Order aggregate. Evidence: tests/test_order.py.",
               paths="src/domain")
    assert "no test file references" not in out


def test_signal_detects_domain_events(tmp_path):
    _domain_file(tmp_path, """\
        class OrderPlacedEvent:
            pass

        class Order:
            def place(self):
                return OrderPlacedEvent()
        """)
    out = _run(tmp_path, decision="Use a domain event when an order is placed. "
               "Evidence: src/domain/order.py. Reversible.", paths="src/domain")
    assert "domain-event vocabulary present" in out


def test_no_paths_is_document_only(tmp_path):
    out = _run(tmp_path, decision="Use Postgres. Evidence: docs/adr/0007.md.")
    assert "document-only" in out


def test_missing_path_is_ignored(tmp_path):
    out = _run(tmp_path, decision="Use Postgres. Evidence: docs/adr/0007.md.",
               paths="does/not/exist")
    assert "document-only" in out


def test_paths_inferred_from_backticks(tmp_path):
    _domain_file(tmp_path, "class Order:\n    pass\n")
    out = _run(tmp_path, decision=(
        "Keep `src/domain` pure. Evidence: `src/domain/order.py`. Reversible."
    ))
    assert "Inspected: `src/domain`" in out


# ---------- write behaviour ----------

def test_write_to_spec_dir_and_refuse_overwrite(tmp_path):
    d = _spec(tmp_path)
    out = _run(tmp_path, spec_dir="specs/orders", write=True)
    target = d / "DECISION-REVIEW.md"
    assert target.is_file()
    assert "Wrote specs/orders/DECISION-REVIEW.md" in out
    first = target.read_text()

    out = _run(tmp_path, spec_dir="specs/orders", write=True)
    assert "exists — pass --force" in out
    assert target.read_text() == first

    out = _run(tmp_path, spec_dir="specs/orders", write=True, force=True)
    assert "Wrote specs/orders/DECISION-REVIEW.md" in out


def test_write_next_to_adr(tmp_path):
    _adr(tmp_path)
    out = _run(tmp_path, adr="docs/adr/0007-order-store.md", write=True)
    target = tmp_path / "docs" / "adr" / "0007-order-store-review.md"
    assert target.is_file()
    assert "Wrote docs/adr/0007-order-store-review.md" in out


def test_write_without_destination_is_an_error(tmp_path):
    out = _run(tmp_path, decision="A decision with enough words to be meaningful here.",
               write=True)
    assert "ERROR: --write needs --spec_dir or --adr" in out


# ---------- brief content ----------

def test_brief_has_lenses_scorecard_and_verdict(tmp_path):
    _adr(tmp_path)
    out = _run(tmp_path, adr="docs/adr/0007-order-store.md")
    for lens in ("Problem & forces", "Alternatives & tradeoffs", "Domain fit (DDD)",
                 "Architecture & boundaries", "Testable design", "Craftsmanship",
                 "Decision record"):
        assert f"### " in out and lens in out
    assert "| Lens | Score | Evidence" in out
    assert "VERDICT: ACCEPT | REVISE | REVISIT | SPLIT" in out
    assert "REVISIT TRIGGER:" in out
    assert "advisory" in out


def test_focus_reorders_lenses(tmp_path):
    _adr(tmp_path)
    out = _run(tmp_path, adr="docs/adr/0007-order-store.md", focus="ddd")
    questions = out.split("## Challenge questions", 1)[1]
    assert "- Focus: ddd" in out
    assert questions.index("Domain fit (DDD)") < questions.index("Problem & forces")


def test_type_specific_question_is_added(tmp_path):
    _adr(tmp_path)
    out = _run(tmp_path, adr="docs/adr/0007-order-store.md")
    assert "Which consistency guarantee is required" in out


def test_design_moves_are_type_specific(tmp_path):
    _adr(tmp_path)
    out = _run(tmp_path, adr="docs/adr/0007-order-store.md")
    assert "Which invariant spans more than one aggregate" in out
    assert "Shrink the decision" in out


def test_architecture_decision_gets_boundary_move(tmp_path):
    out = _run(tmp_path, decision=(
        "Split the billing module into a separate service with its own deploy, "
        "to reduce coupling between layers. Evidence: docs/adr/0009.md. Reversible."
    ))
    assert "Can this be a module inside the current deployable" in out
