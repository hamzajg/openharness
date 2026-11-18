import textwrap
from pathlib import Path

from skills.product.review_delivery import review_delivery
from skills.product.ship_loop import ship_loop
from skills.product.ship_validate import ship_validate
from skills.product.wave_plan import wave_plan

SPEC = textwrap.dedent("""\
    # Spec: Cart

    ## Problem
    Shoppers lose their cart when they leave the page. We need a durable cart
    that survives a session and turns into an order at checkout.

    ## Users
    Shoppers and support agents.

    ## Scope (in)
    - `src/cart` — cart domain, storage, and HTTP surface.

    ## Scope (out)
    - Payments and inventory reservation.

    ## Acceptance criteria

    | # | Criterion | Scenario(s) |
    |---|-----------|-------------|
    | 1 | Adding an item shows it in the cart | add an item |
    | 2 | Checkout creates an order | checkout |
    """)

FEATURE = textwrap.dedent("""\
    Feature: Cart

      @w1 @happy-path
      Scenario: add an item
        Given a cart
        When I add an item
        Then it appears

      @w2 @happy-path
      Scenario: checkout
        Given a full cart
        When I check out
        Then an order exists
    """)

BACKLOG = textwrap.dedent("""\
    # Backlog: Cart

    ## US1 — As a shopper, I want to add items, so that I can buy them
    - Scenarios: @w1
    - Size: S

    ## US2 — As a shopper, I want to check out, so that I get my order
    - Scenarios: @w2
    - Depends: US1
    - Size: M
    """)

VALIDATION = textwrap.dedent("""\
    # Validation — cart

    ## Traceability

    | AC | Criterion | Scenarios | Wave(s) | Test evidence |
    |----|-----------|-----------|---------|---------------|
    | 1 | Adding an item shows it | add an item | 1 | test_cart.py |
    | 2 | Checkout creates an order | checkout | 2 | test_cart.py |

    ## Gaps

    - none — spec is fully traced
    """)


def _write(root: Path, rel: str, content: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def _spec_only(root: Path, name: str = "cart") -> Path:
    """Artifacts required for the spec audit, plus a source tree to resolve."""
    d = root / "specs" / name
    _write(root, f"specs/{name}/SPEC.md", SPEC)
    _write(root, f"specs/{name}/EXAMPLES.feature", FEATURE)
    _write(root, f"specs/{name}/BACKLOG.md", BACKLOG)
    _write(root, "src/cart/store.py", "class CartStore:\n    def add(self, item):\n        return [item]\n")
    return d


def _delivery(root: Path, name: str = "cart") -> Path:
    """A complete, clean delivery: waves done, validation written, tests named."""
    d = _spec_only(root, name)
    b = root / ".openharness" / "evidence" / name / "run-1"
    b.mkdir(parents=True, exist_ok=True)
    (b / "index.html").write_text("<html/>")
    wave_plan.invoke(spec_dir=str(d))
    _run(root, action="start", wave=1)
    _run(root, action="complete", wave=1, note="tests 2/2, CI green", pr="#12")
    _run(root, action="start", wave=2)
    _run(root, action="complete", wave=2, note="tests 2/2, CI green", pr="#13")
    _write(root, "tests/test_cart.py", textwrap.dedent("""\
        def test_cart():
            # add an item
            # checkout
            assert True
        """))
    ship_validate.invoke(spec_dir=str(d), repo_path=str(root))
    return d


def _run(root: Path, **kw) -> str:
    return ship_loop.invoke(repo_path=str(root), **kw)


def _audit(root: Path, **kw) -> str:
    return review_delivery.invoke(repo_path=str(root), **kw)


# ---------- happy path ----------

def test_clean_spec_audit_has_no_blockers(tmp_path):
    _spec_only(tmp_path)
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "Findings: **0 blockers · 0 concerns" in out
    assert "## Verdict (agent fills after verifying the code)" in out
    assert "AUDIT: PASS | CONCERNS | BLOCK" in out


def test_clean_delivery_audit_has_no_findings(tmp_path):
    _delivery(tmp_path)
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "Findings: **0 blockers · 0 concerns · 0 unverified**" in out
    assert "Validation rows: 2" in out


# ---------- artifacts ----------

def test_missing_artifacts_are_blockers(tmp_path):
    d = _spec_only(tmp_path)
    (d / "EXAMPLES.feature").unlink()
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "[missing-artifact]" in out and "EXAMPLES.feature" in out
    assert "[no-scenarios]" in out


def test_delivery_requires_waves_loop_and_validation(tmp_path):
    d = _spec_only(tmp_path)
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[missing-artifact] `specs/cart/WAVES.md`" in out
    assert "[missing-artifact] `specs/cart/LOOP.md`" in out
    assert "[missing-artifact] `specs/cart/VALIDATION.md`" in out


def test_no_specs_directory_is_an_error(tmp_path):
    out = _audit(tmp_path, phase="spec")
    assert out.startswith("ERROR") and "specs/" in out


def test_bad_phase_is_an_error(tmp_path):
    _spec_only(tmp_path)
    out = _audit(tmp_path, phase="nope")
    assert out.startswith("ERROR") and "spec|delivery|all" in out


# ---------- traceability ----------

def test_ac_without_scenario_is_a_blocker(tmp_path):
    d = _spec_only(tmp_path)
    spec = (d / "SPEC.md").read_text().replace(
        "| 2 | Checkout creates an order | checkout |",
        "| 2 | Checkout creates an order | — |",
    )
    (d / "SPEC.md").write_text(spec)
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "[ac-no-scenario]" in out and "AC 2" in out


def test_unknown_wave_reference_is_a_blocker(tmp_path):
    d = _spec_only(tmp_path)
    spec = (d / "SPEC.md").read_text().replace(
        "| add an item |", "| @w9 |"
    )
    (d / "SPEC.md").write_text(spec)
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "[ac-unknown-wave]" in out and "@w9" in out


def test_untagged_scenario_is_a_blocker(tmp_path):
    d = _spec_only(tmp_path)
    (d / "EXAMPLES.feature").write_text(
        (d / "EXAMPLES.feature").read_text().replace("  @w2 @happy-path\n", "")
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "[scenario-untagged]" in out and "checkout" in out


def test_scenario_tagged_for_missing_wave_is_a_blocker(tmp_path):
    d = _delivery(tmp_path)
    (d / "EXAMPLES.feature").write_text(
        (d / "EXAMPLES.feature").read_text().replace("@w2", "@w9")
    )
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[scenario-wave-missing]" in out and "@w9" in out


def test_wave_referencing_unknown_backlog_item_is_a_blocker(tmp_path):
    d = _delivery(tmp_path)
    waves = (d / "WAVES.md").read_text().replace("| US2 |", "| B99 |")
    (d / "WAVES.md").write_text(waves)
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[wave-unknown-item]" in out and "B99" in out


def test_backlog_unknown_dependency_is_a_blocker(tmp_path):
    d = _spec_only(tmp_path)
    (d / "BACKLOG.md").write_text(
        (d / "BACKLOG.md").read_text().replace("Depends: US1", "Depends: US9")
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "[backlog-unknown-dep]" in out and "item #9" in out


def test_backlog_scenario_for_missing_wave_is_a_blocker(tmp_path):
    d = _delivery(tmp_path)
    (d / "BACKLOG.md").write_text(
        (d / "BACKLOG.md").read_text().replace("Scenarios: @w2", "Scenarios: @w9")
    )
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[backlog-wave-missing]" in out


def test_unresolved_spec_marker_is_a_blocker(tmp_path):
    d = _spec_only(tmp_path)
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text() + "\n## Notes\n\nTBD: who owns the cart?\n"
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "[unresolved-spec] `SPEC.md:" in out and "TBD" in out


# ---------- claim verification ----------

def test_missing_path_is_a_concern_in_spec_and_blocker_in_delivery(tmp_path):
    d = _spec_only(tmp_path)
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text().replace(
            "## Scope (out)", "See `src/cart/missing.py`.\n\n## Scope (out)"
        )
    )
    spec = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "[missing-path]" in spec and "src/cart/missing.py" in spec
    assert "## Blockers\n\nNone." in spec

    delivery = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[missing-path]" in delivery
    assert "src/cart/missing.py" in delivery.split("## Blockers")[1]


def test_missing_path_claimed_as_current_is_a_blocker_even_in_spec(tmp_path):
    d = _spec_only(tmp_path)
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text().replace(
            "## Scope (out)", "The cart already exists in `src/cart/ghost.py`.\n\n## Scope (out)"
        )
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "claimed as current" in out
    assert "src/cart/ghost.py" in out.split("## Blockers")[1]


def test_negated_path_reference_is_not_a_claim(tmp_path):
    d = _spec_only(tmp_path)
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text()
        + "\nThe MVP bundles assets instead of reviving `api.php`.\n"
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "api.php" not in out.split("## Concerns")[1].split("## Unverified")[0]


def test_current_marker_after_the_token_does_not_upgrade_severity(tmp_path):
    d = _spec_only(tmp_path)
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text().replace(
            "## Scope (out)",
            "Generated audio in `assets/raw/`, seeded into the existing table.\n\n## Scope (out)",
        )
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "assets/raw/" in out
    assert "assets/raw/" not in out.split("## Blockers")[1].split("## Concerns")[0]


def test_missing_script_is_a_blocker(tmp_path):
    d = _spec_only(tmp_path)
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text() + "\nVerify with `sh scripts/verify.sh`.\n"
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "[missing-script]" in out and "scripts/verify.sh" in out


def test_endpoint_is_a_concern_in_spec_and_blocker_in_delivery(tmp_path):
    d = _spec_only(tmp_path)
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text() + "\nExpose `POST /cart/items`.\n"
    )
    spec = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "[endpoint-not-found]" in spec
    assert "expected if still planned" in spec

    delivery = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[endpoint-not-found]" in delivery
    assert "POST /cart/items" in delivery.split("## Blockers")[1]


def test_endpoint_found_in_code_is_not_flagged(tmp_path):
    d = _spec_only(tmp_path)
    _write(tmp_path, "src/cart/api.py", "def post():\n    return '/cart/items'\n")
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text() + "\nExpose `POST /cart/items`.\n"
    )
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "endpoint-not-found" not in out


def test_endpoint_composed_from_annotations_is_found(tmp_path):
    d = _spec_only(tmp_path)
    _write(tmp_path, "src/cart/OrderController.java", textwrap.dedent("""\
        @RequestMapping("/orders")
        class OrderController {
            @PostMapping("/{id}/cancel")
            void cancel() {}
        }
        """))
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text() + "\nExpose `POST /orders/{id}/cancel`.\n"
    )
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "endpoint-not-found" not in out


def test_endpoint_from_controller_name_is_found(tmp_path):
    d = _spec_only(tmp_path)
    _write(tmp_path, "src/Product.WebApi/ProductsController.cs", textwrap.dedent("""\
        [Route("[controller]")]
        class ProductsController {
            [HttpPost]
            void Create() {}
        }
        """))
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text() + "\nExpose `POST /Products`.\n"
    )
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "endpoint-not-found" not in out


def test_duplicate_endpoint_claims_are_reported_once(tmp_path):
    d = _spec_only(tmp_path)
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text()
        + "\nExpose `POST /cart/items`. Then call `POST /cart/items` again.\n"
    )
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert out.count("POST /cart/items was not found") == 1


def test_test_paths_are_exempt_from_scope_drift(tmp_path):
    d = _delivery(tmp_path)
    _write(tmp_path, "tests/Tests/Product.App/CreateProductTest.cs", "class T {}\n")
    out = _audit(
        tmp_path, phase="delivery",
        changed="src/cart/store.py tests/Tests/Product.App/CreateProductTest.cs",
    )
    assert "scope-drift" not in out


def test_source_root_relative_path_resolves_by_suffix(tmp_path):
    d = _spec_only(tmp_path)
    _write(
        tmp_path,
        "app/src/main/java/com/example/app/utils/Job.java",
        "class Job {}\n",
    )
    _write(
        tmp_path,
        "app/src/test/java/com/example/app/jobs/JobRepositoryTest.java",
        "class JobRepositoryTest {}\n",
    )
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text().replace(
            "## Scope (out)",
            "`utils/Job.java` and `jobs/JobRepositoryTest.java`.\n\n## Scope (out)",
        )
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "utils/Job.java" not in out.split("## Concerns")[1].split("## Unverified")[0]
    assert "JobRepositoryTest.java" not in out.split("## Concerns")[1].split("## Unverified")[0]


def test_package_id_is_not_a_path(tmp_path):
    d = _spec_only(tmp_path)
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text() + "\nAdd the `org.json` test dependency.\n"
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "org.json" not in out.split("## Concerns")[1].split("## Unverified")[0]


def test_url_without_scheme_is_not_a_path(tmp_path):
    d = _spec_only(tmp_path)
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text() + "\nThe `viaviweb.in/envato/cc/demo` API is dead.\n"
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "viaviweb.in" not in out.split("## Concerns")[1].split("## Unverified")[0]


def test_http_route_is_not_a_filesystem_path(tmp_path):
    d = _spec_only(tmp_path)
    _write(tmp_path, "src/IdentityController.java", textwrap.dedent("""\
        @RequestMapping("/identity")
        class IdentityController {
            @GetMapping("/me")
            void me() {}
        }
        """))
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text() + "\nIdentity exposes `/identity/me`.\n"
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "missing-path" not in out


def test_all_caps_enum_list_is_not_a_path(tmp_path):
    d = _spec_only(tmp_path)
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text()
        + "\nToken outcomes: `VALID/INVALID/UNAVAILABLE`.\n"
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "VALID/INVALID/UNAVAILABLE" not in out


def test_trailing_sentence_period_is_not_part_of_the_route(tmp_path):
    d = _spec_only(tmp_path)
    _write(tmp_path, "src/cart/CustomerController.java", textwrap.dedent("""\
        @RequestMapping("/customers")
        class CustomerController {
            @GetMapping("/by-email")
            void byEmail() {}
        }
        """))
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text() + "\nCall GET /customers/by-email.\n"
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "endpoint-not-found" not in out


def test_build_gate_acceptance_criterion_needs_no_scenario(tmp_path):
    d = _spec_only(tmp_path)
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text().replace(
            "| 2 | Checkout creates an order | checkout |",
            "| 2 | `sh gradlew clean test` passes on JDK 17 | — |",
        )
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "ac-no-scenario" not in out


def test_field_list_is_not_inferred_as_scope_path(tmp_path):
    d = _spec_only(tmp_path)
    spec = (d / "SPEC.md").read_text().replace(
        "- `src/cart` — cart domain, storage, and HTTP surface.",
        "- Order lines snapshot productId/sku/name/qty/unitPrice.",
    )
    (d / "SPEC.md").write_text(spec)
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "productId/sku" not in out
    assert "[scope-no-paths]" in out


def test_module_name_in_scope_maps_to_directory(tmp_path):
    d = _spec_only(tmp_path)
    _write(tmp_path, "src/Cart.App/pom.xml", "<project/>")
    spec = (d / "SPEC.md").read_text().replace(
        "- `src/cart` — cart domain, storage, and HTTP surface.",
        "- New `Cart.App` module with the aggregate.",
    )
    (d / "SPEC.md").write_text(spec)
    out = _audit(tmp_path, phase="delivery", changed="src/Cart.App/pom.xml")
    assert "[scope-no-paths]" not in out
    assert "scope-drift" not in out


def test_cross_repo_adr_reference_is_not_local(tmp_path):
    d = _spec_only(tmp_path)
    _write(tmp_path, "docs/adr/0001-cart-store.md", "# ADR 0001\n")
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text()
        + "\nSame lesson as ddd-eshop ADR 0003.\nSee ADR 0007 locally.\n"
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    concerns = out.split("## Concerns")[1].split("## Unverified")[0]
    assert "ADR 0003" not in concerns
    assert "ADR 0007" in concerns


def test_missing_adr_is_a_concern(tmp_path):
    d = _spec_only(tmp_path)
    _write(tmp_path, "docs/adr/0001-cart-store.md", "# ADR 0001\n")
    (d / "SPEC.md").write_text(
        (d / "SPEC.md").read_text() + "\nSee ADR 0007 for the storage choice.\n"
    )
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "[missing-adr]" in out and "ADR 0007" in out


# ---------- evidence integrity ----------

def test_placeholder_wave_evidence_is_a_blocker(tmp_path):
    d = _delivery(tmp_path)
    _run(tmp_path, action="reset", wave=2)
    _run(tmp_path, action="start", wave=2)
    _run(tmp_path, action="complete", wave=2, note="ok")
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[placeholder-wave-evidence]" in out and "wave 2" in out


def test_loop_missing_wave_row_is_a_blocker(tmp_path):
    d = _delivery(tmp_path)
    waves = (d / "WAVES.md").read_text().replace(
        "## Wave 2 — iteration 2", "## Wave 3 — iteration 3"
    ).replace("| US2 |", "| US2 |")
    (d / "WAVES.md").write_text(waves)
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[loop-missing-wave]" in out


def test_gate_without_state_is_a_blocker(tmp_path):
    d = _delivery(tmp_path)
    (d / "GATES.md").write_text(
        "# Gates: Cart\n\n## G1 — Glossary\n- Before: finish\n- Blocking: yes\n- Check: manual\n"
    )
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[gate-no-state]" in out and "G1" in out


def test_pending_blocking_gate_is_a_blocker(tmp_path):
    d = _delivery(tmp_path)
    (d / "GATES.md").write_text(
        "# Gates: Cart\n\n## G1 — Glossary\n- Before: finish\n- Blocking: yes\n- Check: manual\n"
    )
    _run(tmp_path, action="next")  # rewrites LOOP.md with the gate row
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[gate-unmet]" in out and "G1" in out


def test_placeholder_gate_evidence_is_a_blocker(tmp_path):
    d = _delivery(tmp_path)
    (d / "GATES.md").write_text(
        "# Gates: Cart\n\n## G1 — Glossary\n- Before: finish\n- Blocking: yes\n- Check: manual\n"
    )
    _run(tmp_path, action="gate", gate="G1", status="met", evidence="ok")
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[placeholder-gate-evidence]" in out and "G1" in out


def test_substantive_run_id_gate_evidence_is_not_a_placeholder(tmp_path):
    d = _delivery(tmp_path)
    (d / "GATES.md").write_text(
        "# Gates: Cart\n\n## G1 — Glossary\n- Before: finish\n- Blocking: yes\n- Check: manual\n"
    )
    _run(
        tmp_path, action="gate", gate="G1", status="met",
        evidence=(
            "compose-smoke run 43761667487 on merge 0e97364a: success — "
            "checkout through the gateway verified"
        ),
    )
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[placeholder-gate-evidence]" not in out


def test_gate_evidence_file_missing_is_a_blocker(tmp_path):
    d = _delivery(tmp_path)
    (d / "GATES.md").write_text(
        "# Gates: Cart\n\n## G1 — Glossary\n- Before: finish\n- Blocking: yes\n"
        "- Check: file:docs/glossary.md\n"
    )
    _write(tmp_path, "docs/glossary.md", "# Glossary\n")
    _run(tmp_path, action="gate", gate="G1", status="met",
         evidence="docs/glossary.md")
    (tmp_path / "docs" / "glossary.md").unlink()
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[gate-file-missing]" in out and "docs/glossary.md" in out


def test_gate_waived_without_owner_is_a_blocker(tmp_path):
    d = _delivery(tmp_path)
    (d / "GATES.md").write_text(
        "# Gates: Cart\n\n## G1 — Glossary\n- Before: finish\n- Blocking: yes\n- Check: manual\n"
    )
    _run(tmp_path, action="gate", gate="G1", status="met", evidence="docs/glossary.md")
    # Rewrite the LOOP gate row as an unowned waiver.
    loop = (d / "LOOP.md").read_text().replace(
        "| G1 | met | docs/glossary.md |", "| G1 | waived | because we said so |"
    )
    (d / "LOOP.md").write_text(loop)
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[gate-waiver-unowned]" in out


def test_invalid_gate_phase_is_a_blocker(tmp_path):
    d = _delivery(tmp_path)
    (d / "GATES.md").write_text(
        "# Gates: Cart\n\n## G1 — Glossary\n- Before: someday\n- Blocking: yes\n- Check: manual\n"
    )
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[gate-bad-phase]" in out and "someday" in out


def test_validation_without_rows_is_a_blocker(tmp_path):
    d = _delivery(tmp_path)
    (d / "VALIDATION.md").write_text("# Validation — cart\n\n## Gaps\n\n- none\n")
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[no-validation-rows]" in out


def test_validation_gaps_and_weak_evidence_are_concerns(tmp_path):
    d = _delivery(tmp_path)
    (d / "VALIDATION.md").write_text(textwrap.dedent("""\
        # Validation — cart

        ## Traceability

        | AC | Criterion | Scenarios | Wave(s) | Test evidence |
        |----|-----------|-----------|---------|---------------|
        | 1 | Adding an item shows it | add an item | 1 | (weak) test_cart.py |
        | 2 | Checkout creates an order | checkout | 2 | — |

        ## Gaps

        - 1 scenario lacks detected test evidence — verify manually
        - this scenario will be validated later
        """))
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[ac-weak-evidence]" in out
    assert "[ac-no-evidence]" in out
    assert "[validation-gap]" in out
    assert "[aspirational-validation]" in out


def test_expected_behavior_language_is_not_aspirational(tmp_path):
    d = _delivery(tmp_path)
    (d / "VALIDATION.md").write_text(textwrap.dedent("""\
        # Validation — cart

        ## Traceability

        | AC | Criterion | Scenarios | Wave(s) | Test evidence |
        |----|-----------|-----------|---------|---------------|
        | 1 | Adding an item shows it | add an item | 1 | test_cart.py |
        | 2 | Checkout creates an order | checkout | 2 | test_cart.py |

        ## Demo script

        1. Open the cart. Existing items should appear only after the load
           finishes; tapping during the load must not corrupt the list.

        ## Gaps

        - none — spec is fully traced
        """))
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "aspirational-validation" not in out


def test_scope_and_artifact_gap_bullets_are_not_gaps(tmp_path):
    d = _delivery(tmp_path)
    (d / "VALIDATION.md").write_text(textwrap.dedent("""\
        # Validation — cart

        ## Traceability

        | AC | Criterion | Scenarios | Wave(s) | Test evidence |
        |----|-----------|-----------|---------|---------------|
        | 1 | Adding an item shows it | add an item | 1 | test_cart.py |
        | 2 | Checkout creates an order | checkout | 2 | test_cart.py |

        ## Gaps

        - Deliberately out of scope: executing a checkout job.
        - `~` weak token-match on AC 1 is a heuristic artifact, not evidence.
        - **Regenerating IDs on save** is internal-only and
          acceptable per spec.
        - **No automated evidence** —
          this is a heuristic artifact, not evidence.
        """))
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "validation-gap" not in out


def test_outcome_followup_is_not_a_validation_gap(tmp_path):
    d = _delivery(tmp_path)
    (d / "VALIDATION.md").write_text(textwrap.dedent("""\
        # Validation — cart

        ## Traceability

        | AC | Criterion | Scenarios | Wave(s) | Test evidence |
        |----|-----------|-----------|---------|---------------|
        | 1 | Adding an item shows it | add an item | 1 | test_cart.py |
        | 2 | Checkout creates an order | checkout | 2 | test_cart.py |

        ## Gaps

        - none — spec is fully traced

        ## Outcome follow-up

        - Status: not yet measured
        - Owner and review date: (record when known)
        """))
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "validation-gap" not in out


def test_zero_scenario_validation_is_a_blocker(tmp_path):
    d = _delivery(tmp_path)
    (d / "VALIDATION.md").write_text(textwrap.dedent("""\
        # Validation — cart

        ## Traceability

        | AC | Criterion | Scenarios | Wave(s) | Test evidence |
        |----|-----------|-----------|---------|---------------|
        | 1 | Adding an item shows it | — | — | — |

        ## Scenario coverage

        - Scenarios: 0 total, 0 with detected test evidence, 0 without
        """))
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[validation-empty]" in out


# ---------- scope drift / unfinished code ----------

def test_scope_drift_is_a_concern(tmp_path):
    d = _delivery(tmp_path)
    _write(tmp_path, "src/billing/invoice.py", "def invoice():\n    return 1\n")
    out = _audit(
        tmp_path, phase="delivery",
        changed="src/cart/store.py src/billing/invoice.py",
    )
    assert "[scope-drift] `src/billing/invoice.py`" in out
    assert "src/cart/store.py" not in out.split("## Concerns")[1].split("## Unverified")[0]


def test_spec_and_docs_are_exempt_from_scope_drift(tmp_path):
    _delivery(tmp_path)
    out = _audit(
        tmp_path, phase="delivery",
        changed="src/cart/store.py specs/cart/SPEC.md README.md",
    )
    assert "scope-drift" not in out


def test_unfinished_marker_in_changed_code_is_a_concern(tmp_path):
    _delivery(tmp_path)
    _write(tmp_path, "src/cart/store.py", "def add(item):\n    # TODO: persist\n    return item\n")
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[unfinished-code] `src/cart/store.py:" in out


def test_scope_not_checked_when_git_is_unavailable(tmp_path):
    _delivery(tmp_path)
    out = _audit(tmp_path, phase="delivery")
    assert "[scope-not-checked]" in out
    assert "no git base ref" in out


def test_scope_not_checked_without_in_scope_paths(tmp_path):
    d = _delivery(tmp_path)
    spec = (d / "SPEC.md").read_text().replace(
        "## Scope (in)\n- `src/cart` — cart domain, storage, and HTTP surface.",
        "## Scope (in)\n- (to be filled)",
    )
    (d / "SPEC.md").write_text(spec)
    out = _audit(tmp_path, phase="delivery", changed="src/cart/store.py")
    assert "[scope-no-paths]" in out


# ---------- writing ----------

def test_write_creates_audit_files_and_refuses_overwrite(tmp_path):
    d = _delivery(tmp_path)
    out = _audit(tmp_path, phase="all", changed="src/cart/store.py", write=True)
    assert (d / "SPEC-AUDIT.md").is_file()
    assert (d / "DELIVERY-AUDIT.md").is_file()
    assert "Wrote specs/cart/SPEC-AUDIT.md" in out
    assert "Wrote specs/cart/DELIVERY-AUDIT.md" in out

    again = _audit(tmp_path, phase="all", changed="src/cart/store.py", write=True)
    assert "exists — pass --force" in again

    forced = _audit(
        tmp_path, phase="all", changed="src/cart/store.py", write=True, force=True
    )
    assert "exists — pass --force" not in forced
    assert "Wrote specs/cart/SPEC-AUDIT.md" in forced


def test_phase_all_reports_both_audits(tmp_path):
    _delivery(tmp_path)
    out = _audit(tmp_path, phase="all", changed="src/cart/store.py")
    assert "# Delivery audit — cart (spec)" in out
    assert "# Delivery audit — cart (delivery)" in out


def test_default_spec_dir_picks_first_feature(tmp_path):
    _spec_only(tmp_path)
    out = _audit(tmp_path, phase="spec", changed="src/cart/store.py")
    assert "# Delivery audit — cart (spec)" in out


# ---------- security: no absolute host paths in audit output ----------

def test_audit_rewrites_home_path_to_tilde(tmp_path):
    """The Repo: line must never emit an absolute /home/<user>/... path into
    a committed audit file (security: ADR 0004)."""
    import os
    import shutil

    home = Path(os.path.expanduser("~"))
    # Copy the temp spec tree under the real home dir so the display-path
    # logic actually collapses it (tmp_path is usually under /tmp, so a
    # symlink would resolve through to the tmp path and not collapse).
    repo = home / f".openharness-audit-test-{os.getpid()}"
    try:
        if repo.exists():
            shutil.rmtree(repo)
        shutil.copytree(tmp_path, repo)
        _spec_only(repo)
        out = _audit(repo, phase="spec", changed="src/cart/store.py")
        assert f"- Repo: `~/.openharness-audit-test-{os.getpid()}`" in out
        assert "/home/" not in out
    finally:
        if repo.exists():
            shutil.rmtree(repo)
