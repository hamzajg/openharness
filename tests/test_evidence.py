"""Evidence bundles: manifest contract, checks, and the generated page.

Every test works inside `tmp_path`; nothing here touches the network, and git is
used only to *read* (`ls-files`, `rev-parse`) or to set up a fixture repo.
"""

import base64
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from openharness import evidence
from openharness.skill import SkillError
from skills.harness.evidence import harness_evidence

ROOT = Path(__file__).resolve().parents[1]
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BwDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
HEAD = "abc1234def5678"


def _save(bundle: Path, manifest: dict) -> None:
    (bundle / "evidence.json").write_text(json.dumps(manifest, indent=2) + "\n")


def _make(
    tmp_path: Path,
    *,
    head: str = HEAD,
    verdict: str = "pass",
    summary: str = "Backend tests pass; UI untouched.",
    not_verified=("the webapp was not opened",),
) -> tuple[Path, dict]:
    """A valid bundle: one command step, its log, and one screenshot."""
    bundle = evidence.new_bundle(
        tmp_path,
        "cart",
        wave=1,
        head=head,
        branch="feat/cart",
        summary=summary,
        not_verified=not_verified,
        run="20260101T000000Z-abc1234",
    )
    log = bundle / "logs" / "s1.log"
    log.write_text("97 passed in 59.41s\n")
    shot = bundle / "raw" / "s1" / "shot.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    shot.write_bytes(PNG)
    manifest = json.loads((bundle / "evidence.json").read_text())
    manifest["verdict"] = verdict
    manifest["steps"] = [
        {
            "id": "s1",
            "title": "Backend tests",
            "kind": "command",
            "status": "pass",
            "exit_code": 0,
            "duration_ms": 59410,
            "cmd": "pytest -q",
            "log": "logs/s1.log",
            "artifacts": [
                {
                    "path": "raw/s1/shot.png",
                    "mime": "image/png",
                    "sha256": evidence.sha256(shot),
                    "bytes": shot.stat().st_size,
                    "caption": "Approval card",
                }
            ],
            "note": "97 passed",
        }
    ]
    _save(bundle, manifest)
    return bundle, manifest


def _add_artifact(bundle: Path, manifest: dict, rel: str, mime: str, data: bytes) -> dict:
    path = bundle / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    art = {
        "path": rel,
        "mime": mime,
        "sha256": evidence.sha256(path),
        "bytes": path.stat().st_size,
        "caption": rel,
    }
    manifest["steps"][0]["artifacts"].append(art)
    _save(bundle, manifest)
    return art


def _codes(report) -> set[str]:
    return {f.code for f in report.findings}


# --------------------------------------------------------------------- module

def test_new_bundle_creates_the_layout(tmp_path):
    bundle = evidence.new_bundle(
        tmp_path, "cart", wave=2, head=HEAD, branch="feat/cart", not_verified=["x"]
    )

    assert bundle.parent == tmp_path / ".openharness" / "evidence" / "cart"
    assert bundle.name.endswith("-abc1234")
    assert (bundle / "raw").is_dir() and (bundle / "logs").is_dir()
    manifest = json.loads((bundle / "evidence.json").read_text())
    assert manifest["schema"] == evidence.SCHEMA
    assert manifest["wave"] == 2
    assert manifest["not_verified"] == ["x"]


def test_new_bundle_refuses_to_overwrite(tmp_path):
    evidence.new_bundle(tmp_path, "cart", run="20260101T000000Z-abc1234", head=HEAD)

    with pytest.raises(evidence.EvidenceError, match="already exists"):
        evidence.new_bundle(tmp_path, "cart", run="20260101T000000Z-abc1234", head=HEAD)


def test_load_rejects_an_unknown_schema(tmp_path):
    bundle, manifest = _make(tmp_path)
    manifest["schema"] = "something/2"
    _save(bundle, manifest)

    with pytest.raises(evidence.EvidenceError, match="schema"):
        evidence.load(bundle)


def test_load_rejects_a_manifest_without_not_verified(tmp_path):
    bundle, manifest = _make(tmp_path)
    del manifest["not_verified"]
    _save(bundle, manifest)

    with pytest.raises(evidence.EvidenceError, match="not_verified"):
        evidence.load(bundle)


def test_command_step_needs_an_exit_code(tmp_path):
    bundle, manifest = _make(tmp_path)
    del manifest["steps"][0]["exit_code"]
    _save(bundle, manifest)

    with pytest.raises(evidence.EvidenceError, match="exit_code"):
        evidence.load(bundle)


# --------------------------------------------------------------------- verify

def test_clean_bundle_verifies(tmp_path):
    bundle, _ = _make(tmp_path)

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert report.ok, report.render()
    assert not report.errors


def test_verify_uses_git_head_when_no_head_is_given(tmp_path):
    bundle, _ = _make(tmp_path)
    if not shutil.which("git"):
        pytest.skip("git not installed")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A", "."], check=True)

    report = evidence.verify(bundle, repo=tmp_path)

    # The bundle is force-added here, so it is tracked — that must be reported.
    assert "tracked-bundle" in _codes(report)


def test_commit_mismatch_is_an_error(tmp_path):
    bundle, _ = _make(tmp_path)

    report = evidence.verify(bundle, repo=tmp_path, head="9999fff0000")

    assert "commit-mismatch" in _codes(report)
    assert not report.ok
    assert "abc1234" in report.render() and "9999fff" in report.render()


def _git(root: Path, *args: str) -> str:
    run = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, capture_output=True, text=True,
    )
    return run.stdout.strip()


def _init_git(root: Path) -> None:
    if not shutil.which("git"):
        pytest.skip("git not installed")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")


def test_verify_accepts_a_recorded_head_that_is_an_ancestor(tmp_path):
    """Proof recorded at commit A still verifies after commit B lands on top."""
    _init_git(tmp_path)
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "a")
    head_a = _git(tmp_path, "rev-parse", "HEAD")
    bundle, _ = _make(tmp_path, head=head_a)
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "b")

    report = evidence.verify(bundle, repo=tmp_path)

    assert "commit-mismatch" not in _codes(report)
    assert report.ok, report.render()


def test_verify_rejects_a_head_from_an_unrelated_history(tmp_path):
    _init_git(tmp_path)
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "a")
    head_a = _git(tmp_path, "rev-parse", "HEAD")
    bundle, _ = _make(tmp_path, head=head_a)
    _git(tmp_path, "checkout", "-q", "--orphan", "unrelated")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "c")

    report = evidence.verify(bundle, repo=tmp_path)

    assert "commit-mismatch" in _codes(report)
    assert not report.ok


def test_hash_mismatch_is_an_error(tmp_path):
    bundle, _ = _make(tmp_path)
    (bundle / "raw" / "s1" / "shot.png").write_bytes(PNG + b"\x00")

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    codes = _codes(report)
    assert "hash-mismatch" in codes
    assert "size-mismatch" in codes


def test_missing_artifact_is_an_error(tmp_path):
    bundle, _ = _make(tmp_path)
    (bundle / "raw" / "s1" / "shot.png").unlink()

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert "missing-artifact" in _codes(report)
    assert "raw/s1/shot.png" in report.render()


def test_missing_log_is_an_error(tmp_path):
    bundle, _ = _make(tmp_path)
    (bundle / "logs" / "s1.log").unlink()

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert "missing-log" in _codes(report)


def test_a_secret_in_a_log_fails_the_bundle(tmp_path):
    bundle, _ = _make(tmp_path)
    (bundle / "logs" / "s1.log").write_text(
        "running...\nAuthorization: Bearer ghp_" + "a" * 36 + "\n"
    )
    manifest = json.loads((bundle / "evidence.json").read_text())
    manifest["steps"][0]["artifacts"] = []  # isolate the log check
    _save(bundle, manifest)

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert "secret-in-log" in _codes(report)
    assert "redact" in report.render()


def test_a_secret_in_a_text_artifact_fails_the_bundle(tmp_path):
    bundle, manifest = _make(tmp_path)
    _add_artifact(
        bundle, manifest, "raw/s1/env.json", "application/json",
        b'{"api_key": "sk-' + b"b" * 32 + b'"}',
    )

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert "secret-in-artifact" in _codes(report)


def test_redacted_logs_are_accepted(tmp_path):
    bundle, _ = _make(tmp_path)
    (bundle / "logs" / "s1.log").write_text(
        "GET /api/workflows\nAuthorization: Bearer [REDACTED]\n200 OK\n"
    )
    manifest = json.loads((bundle / "evidence.json").read_text())
    manifest["redactions"] = [
        {"path": "logs/s1.log", "pattern": "Authorization", "count": 1}
    ]
    _save(bundle, manifest)

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert report.ok, report.render()


def test_tracked_bundle_is_an_error(tmp_path):
    if not shutil.which("git"):
        pytest.skip("git not installed")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    bundle, _ = _make(tmp_path)
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "-f", bundle.relative_to(tmp_path).as_posix()],
        check=True,
    )

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert "tracked-bundle" in _codes(report)
    assert "local" in report.render()


def test_untracked_bundle_in_a_git_repo_passes(tmp_path):
    if not shutil.which("git"):
        pytest.skip("git not installed")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    bundle, _ = _make(tmp_path)

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert report.ok, report.render()
    assert "tracked-bundle" not in _codes(report)


def _git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.email=t@example.com",
         "-c", "user.name=T", "commit", "-q", "--allow-empty", "-m", "init"],
        check=True,
    )


def test_tracked_root_bundle_may_be_committed(tmp_path):
    if not shutil.which("git"):
        pytest.skip("git not installed")
    _git_init(tmp_path)
    bundle = evidence.new_bundle(
        tmp_path, "cart", head=HEAD, run="20260101T000000Z-abc1234", tracked=True
    )
    assert bundle.parent == tmp_path / "evidence" / "cart"
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A", "evidence"], check=True)

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert "tracked-bundle" not in _codes(report)
    assert "untracked-bundle" not in _codes(report)


def test_tracked_root_bundle_warns_until_git_tracks_it(tmp_path):
    if not shutil.which("git"):
        pytest.skip("git not installed")
    _git_init(tmp_path)
    bundle = evidence.new_bundle(
        tmp_path, "cart", head=HEAD, run="20260101T000000Z-abc1234", tracked=True
    )

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert "untracked-bundle" in _codes(report)
    assert report.ok  # a warning, not an error — the bundle just is not published yet


def test_scratch_bundle_stays_an_error_when_tracked_even_next_to_evidence(tmp_path):
    if not shutil.which("git"):
        pytest.skip("git not installed")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    bundle, _ = _make(tmp_path)
    subprocess.run(
        ["git", "-C", str(tmp_path), "add", "-f", bundle.relative_to(tmp_path).as_posix()],
        check=True,
    )

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert "tracked-bundle" in _codes(report)


def test_list_bundles_covers_scratch_and_tracked_roots(tmp_path):
    scratch, _ = _make(tmp_path)
    tracked = evidence.new_bundle(
        tmp_path, "cart", head=HEAD, run="20260202T000000Z-def5678", tracked=True
    )

    rows = evidence.list_bundles(tmp_path)

    assert [r["bundle"] for r in rows] == [tracked, scratch]
    assert rows[0]["tracked"] is True
    assert rows[1]["tracked"] is False
    assert [r["bundle"] for r in evidence.list_bundles(tmp_path, tracked=True)] == [tracked]
    assert [r["bundle"] for r in evidence.list_bundles(tmp_path, tracked=False)] == [scratch]


def test_no_git_repository_is_a_warning_not_an_error(tmp_path):
    bundle, _ = _make(tmp_path)

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert "no-git" in _codes(report)
    assert report.ok


def test_pass_verdict_with_a_failed_step_is_an_error(tmp_path):
    bundle, manifest = _make(tmp_path)
    manifest["steps"][0]["status"] = "fail"
    manifest["steps"][0]["exit_code"] = 1
    _save(bundle, manifest)

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert "verdict-contradicts-steps" in _codes(report)


def test_expected_failure_is_allowed_under_a_pass_verdict(tmp_path):
    bundle, manifest = _make(tmp_path)
    manifest["steps"].append(
        {
            "id": "s2",
            "title": "approval after demotion",
            "kind": "api",
            "status": "fail",
            "expected_failure": True,
            "note": "Insufficient permissions, as designed",
        }
    )
    _save(bundle, manifest)

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert report.ok, report.render()


def test_command_step_marked_pass_with_nonzero_exit_is_an_error(tmp_path):
    bundle, manifest = _make(tmp_path)
    manifest["steps"][0]["exit_code"] = 3
    _save(bundle, manifest)

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert "exit-code-contradicts-status" in _codes(report)


def test_ci_success_without_a_sha_is_an_error(tmp_path):
    bundle, manifest = _make(tmp_path)
    manifest["ci"] = {"pr": 22, "url": "https://example.test/22", "conclusion": "success"}
    _save(bundle, manifest)

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert "ci-without-sha" in _codes(report)


# --------------------------------------------------------------------- render

def test_render_writes_the_page_and_the_summary(tmp_path):
    bundle, _ = _make(tmp_path)

    paths = evidence.render(bundle)

    page = paths["html"].read_text()
    summary = paths["summary"].read_text()
    assert paths["html"] == bundle / "index.html"
    assert "What this proves" in page
    assert "Backend tests pass" in page
    assert "What was not verified" in page
    assert "the webapp was not opened" in summary
    assert "verdict: **pass**" in summary


def test_render_is_read_only_for_the_manifest(tmp_path):
    bundle, _ = _make(tmp_path)
    before = (bundle / "evidence.json").read_bytes()

    evidence.render(bundle)

    assert (bundle / "evidence.json").read_bytes() == before


def test_render_links_artifacts_relatively(tmp_path):
    bundle, _ = _make(tmp_path)

    page = evidence.render(bundle)["html"].read_text()

    assert 'src="raw/s1/shot.png"' in page
    assert "sha256" in page
    assert "pytest -q" in page
    assert "97 passed in 59.41s" in page


def test_render_inlines_images_when_asked(tmp_path):
    bundle, _ = _make(tmp_path)

    page = evidence.render(bundle, inline=True)["html"].read_text()

    assert 'src="data:image/png;base64,' in page


def test_render_shows_a_recording(tmp_path):
    bundle, manifest = _make(tmp_path)
    _add_artifact(bundle, manifest, "raw/s1/session.webm", "video/webm", b"fake-webm")

    page = evidence.render(bundle)["html"].read_text()

    assert "<h2>Recording</h2>" in page
    assert 'src="raw/s1/session.webm"' in page


def test_render_builds_the_coverage_matrix_from_covers(tmp_path):
    bundle, manifest = _make(tmp_path)
    manifest["steps"][0]["covers"] = ["AC1", "add an item"]
    manifest["steps"][0]["checks"] = [
        {"name": "cart count", "status": "pass", "expected": "1", "actual": "1"}
    ]
    _save(bundle, manifest)

    page = evidence.render(bundle)["html"].read_text()

    assert "<h2>Acceptance coverage</h2>" in page
    assert "<td>AC1</td>" in page and ">s1</td>" in page
    assert "cart count — expected 1, got 1 (pass)" in page


def test_render_shows_step_artifacts_and_log_controls(tmp_path):
    bundle, _ = _make(tmp_path)

    page = evidence.render(bundle)["html"].read_text()

    assert 'class="thumb"' in page
    assert 'class="logfilter"' in page and 'class="logcopy"' in page
    assert 'id="lb"' in page and "ArrowRight" in page


def test_render_uses_the_declared_poster_for_video(tmp_path):
    bundle, manifest = _make(tmp_path)
    _add_artifact(bundle, manifest, "raw/s1/session.webm", "video/webm", b"fake-webm")
    manifest["steps"][0]["artifacts"][-1]["poster"] = "raw/s1/shot.png"
    _save(bundle, manifest)

    page = evidence.render(bundle)["html"].read_text()

    assert 'poster="raw/s1/shot.png"' in page


def test_render_inline_lists_files_that_stayed_external(tmp_path):
    bundle, _ = _make(tmp_path)
    # Force an over-budget artifact: shrink the inline budget for this test.
    import openharness.evidence as ev
    old = ev.INLINE_BUDGET
    ev.INLINE_BUDGET = 4
    try:
        page = ev.render(bundle, inline=True)["html"].read_text()
    finally:
        ev.INLINE_BUDGET = old

    assert "<h2>Linked files</h2>" in page
    assert "raw/s1/shot.png" in page


def test_empty_bundle_warns_that_it_proves_nothing(tmp_path):
    bundle = evidence.new_bundle(tmp_path, "empty", head=HEAD, run="20260101T000000Z-abc1234")

    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)

    assert "empty-bundle" in _codes(report)
    assert report.ok  # structural, not a failure — the page says the same thing


def test_empty_bundle_renders_honestly(tmp_path):
    bundle = evidence.new_bundle(tmp_path, "empty", head=HEAD, run="20260101T000000Z-abc1234")
    manifest = json.loads((bundle / "evidence.json").read_text())
    manifest["summary"] = ""
    _save(bundle, manifest)

    paths = evidence.render(bundle)
    page = paths["html"].read_text()

    assert "Nothing was captured in this run" in page
    assert "proves nothing yet" in page
    assert "No summary was recorded" in page
    assert "proves nothing yet" in paths["summary"].read_text()


def test_render_escapes_manifest_text(tmp_path):
    bundle, manifest = _make(
        tmp_path,
        summary='<script>alert("x")</script>',
        not_verified=('<img src=x onerror=alert(1)>',),
    )

    page = evidence.render(bundle)["html"].read_text()

    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page
    assert "<img src=x onerror" not in page


# ---------------------------------------------------------------------- list

def test_list_bundles_is_newest_first(tmp_path):
    first, _ = _make(tmp_path)
    second = evidence.new_bundle(
        tmp_path, "cart", head=HEAD, run="20260202T000000Z-def5678"
    )

    rows = evidence.list_bundles(tmp_path, feature="cart")

    assert [r["bundle"] for r in rows] == [second, first]
    assert rows[0]["verdict"] == "pass"
    assert rows[0]["steps"] == 0


def test_list_bundles_marks_an_invalid_manifest(tmp_path):
    bundle, manifest = _make(tmp_path)
    manifest["schema"] = "nope"
    _save(bundle, manifest)

    rows = evidence.list_bundles(tmp_path)

    assert rows[0]["invalid"]


# ---------------------------------------------------------------------- skill

def test_skill_verify_returns_ok_for_a_clean_bundle(tmp_path):
    bundle, _ = _make(tmp_path)

    out = harness_evidence.invoke(
        action="verify", repo=str(tmp_path), bundle=str(bundle)
    )

    assert out.startswith("OK —")


def test_skill_verify_raises_on_drift(tmp_path):
    bundle, _ = _make(tmp_path)
    (bundle / "raw" / "s1" / "shot.png").write_bytes(PNG + b"\x01")

    with pytest.raises(SkillError) as err:
        harness_evidence.invoke(action="verify", repo=str(tmp_path), bundle=str(bundle))

    assert "hash-mismatch" in str(err.value)
    assert "FAILED" in str(err.value)


def test_skill_new_then_render(tmp_path):
    created = harness_evidence.invoke(
        action="new",
        repo=str(tmp_path),
        feature="cart",
        head=HEAD,
        summary="Nothing yet.",
        not_verified="ui; ci",
    )
    assert "Created" in created

    out = harness_evidence.invoke(action="render", repo=str(tmp_path), feature="cart")

    bundle = evidence.list_bundles(tmp_path, feature="cart")[0]["bundle"]
    assert (bundle / "index.html").is_file()
    assert "Verification: OK" in out


def test_skill_new_with_tracked_uses_the_committable_root(tmp_path):
    out = harness_evidence.invoke(
        action="new", repo=str(tmp_path), feature="cart", head=HEAD, tracked=True
    )

    assert (tmp_path / "evidence" / "cart").is_dir()
    assert "tracked root" in out
    rows = evidence.list_bundles(tmp_path, feature="cart")
    assert rows[0]["tracked"] is True

    listing = harness_evidence.invoke(action="list", repo=str(tmp_path))
    assert "tracked" in listing and "local" in listing


def test_skill_render_reports_an_unbound_bundle(tmp_path):
    harness_evidence.invoke(action="new", repo=str(tmp_path), feature="cart")

    out = harness_evidence.invoke(action="render", repo=str(tmp_path), feature="cart")

    assert "1 error(s)" in out


def test_new_bundle_records_git_head(tmp_path):
    if not shutil.which("git"):
        pytest.skip("git not installed")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "-c", "user.email=t@example.com",
         "-c", "user.name=T", "commit", "-q", "--allow-empty", "-m", "init"],
        check=True,
    )

    bundle = evidence.new_bundle(tmp_path, "cart")

    manifest = json.loads((bundle / "evidence.json").read_text())
    assert manifest["repo"]["head"]
    assert bundle.name.endswith(manifest["repo"]["head"][:7])


def test_skill_new_requires_a_feature(tmp_path):
    with pytest.raises(SkillError, match="feature is required"):
        harness_evidence.invoke(action="new", repo=str(tmp_path))


def test_skill_list_empty_root(tmp_path):
    assert "No evidence bundles" in harness_evidence.invoke(action="list", repo=str(tmp_path))


def test_skill_rejects_an_unknown_action(tmp_path):
    with pytest.raises(SkillError, match="unknown action"):
        harness_evidence.invoke(action="nope", repo=str(tmp_path))


# ------------------------------------------------------------------ CLI exit

def _cli(*args: str):
    return subprocess.run(
        [sys.executable, "-m", "openharness", "run", "harness_evidence", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def test_cli_verify_exits_2_on_drift(tmp_path):
    bundle, _ = _make(tmp_path)
    (bundle / "logs" / "s1.log").unlink()

    run = _cli("--action=verify", f"--repo={tmp_path}", f"--bundle={bundle}")

    assert run.returncode == 2, run.stdout + run.stderr
    assert "missing-log" in run.stderr


def test_cli_verify_exits_0_when_clean(tmp_path):
    bundle, _ = _make(tmp_path)

    run = _cli("--action=verify", f"--repo={tmp_path}", f"--bundle={bundle}")

    assert run.returncode == 0, run.stderr
    assert "OK —" in run.stdout


# ------------------------------------------------------------------- capture

def _capture_bundle(tmp_path: Path, feature: str = "capture") -> Path:
    return evidence.new_bundle(
        tmp_path,
        feature,
        head=HEAD,
        run=f"20260101T000000Z-{feature}",
    )


def _python(code: str) -> str:
    return shlex.join([sys.executable, "-c", code])


def test_step_records_exit_code_log_and_duration(tmp_path):
    bundle = _capture_bundle(tmp_path)

    step = evidence.record_step(bundle, title="Say hi", cmd=_python("print('hi')"))

    assert step["id"] == "s1"
    assert step["status"] == "pass"
    assert step["exit_code"] == 0
    assert step["duration_ms"] >= 0
    assert step["log"] == "logs/s1.log"
    log = (bundle / step["log"]).read_text()
    assert "hi" in log
    assert "exit 0" in log
    assert evidence.load(bundle)["steps"][0]["title"] == "Say hi"


def test_step_marks_a_nonzero_exit_as_fail(tmp_path):
    bundle = _capture_bundle(tmp_path)

    step = evidence.record_step(
        bundle, title="Fail", cmd=_python("raise SystemExit(3)")
    )

    assert step["status"] == "fail"
    assert step["exit_code"] == 3
    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)
    assert "verdict-contradicts-steps" in _codes(report)


def test_step_timeout_is_recorded_as_failure(tmp_path):
    bundle = _capture_bundle(tmp_path)

    step = evidence.record_step(
        bundle,
        title="Slow",
        cmd=_python("import time; time.sleep(2)"),
        timeout=1,
    )

    assert step["status"] == "fail"
    assert step["exit_code"] == 124
    assert "timed out" in step["note"]


def test_step_refuses_a_duplicate_id(tmp_path):
    bundle = _capture_bundle(tmp_path)
    evidence.record_step(bundle, title="One", cmd=_python("print(1)"), step_id="s1")

    with pytest.raises(evidence.EvidenceError, match="already exists"):
        evidence.record_step(
            bundle, title="Two", cmd=_python("print(2)"), step_id="s1"
        )


def test_step_requires_a_command(tmp_path):
    bundle = _capture_bundle(tmp_path)

    with pytest.raises(evidence.EvidenceError, match="cmd is required"):
        evidence.record_step(bundle, title="Empty", cmd="  ")


def test_step_redacts_secrets_in_the_log_and_command(tmp_path):
    bundle = _capture_bundle(tmp_path)

    step = evidence.record_step(
        bundle,
        title="Leak",
        cmd=_python("print('password=hunter2')"),
    )

    assert "hunter2" not in step["cmd"]
    log = (bundle / step["log"]).read_text()
    assert "hunter2" not in log
    assert "[REDACTED:password]" in log
    manifest = evidence.load(bundle)
    assert any(r["pattern"] == "password" for r in manifest["redactions"])
    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)
    assert report.ok, report.render()


def test_step_redacts_secrets_in_the_title(tmp_path):
    bundle = _capture_bundle(tmp_path)

    step = evidence.record_step(
        bundle,
        title="login with password=hunter2",
        cmd=_python("print('ok')"),
    )

    assert "hunter2" not in step["title"]
    assert "[REDACTED:password]" in step["title"]
    manifest = evidence.load(bundle)
    assert any(r["path"].endswith(".title") for r in manifest["redactions"])


def test_attach_hashes_and_copies_a_screenshot(tmp_path):
    bundle = _capture_bundle(tmp_path)
    shot = tmp_path / "shot.png"
    shot.write_bytes(PNG)

    art = evidence.record_attach(bundle, shot, caption="Approval card")

    assert art["path"] == "raw/s1/shot.png"
    assert art["mime"] == "image/png"
    assert art["role"] == "screenshot"
    assert art["bytes"] == len(PNG)
    assert art["sha256"] == evidence.sha256(bundle / art["path"])
    manifest = evidence.load(bundle)
    assert manifest["steps"][0]["kind"] == "manual"
    assert manifest["steps"][0]["status"] == "manual"
    assert manifest["steps"][0]["artifacts"][0]["caption"] == "Approval card"
    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)
    assert report.ok, report.render()


def test_attach_rejects_a_file_older_than_the_step(tmp_path):
    bundle = _capture_bundle(tmp_path)
    evidence.record_step(bundle, title="Now", cmd=_python("print('x')"))
    shot = tmp_path / "old.png"
    shot.write_bytes(PNG)
    old = time.time() - 3600
    os.utime(shot, (old, old))

    with pytest.raises(evidence.EvidenceError, match="older than step"):
        evidence.record_attach(bundle, shot, step_id="s1")


def test_attach_allow_old_records_the_file(tmp_path):
    bundle = _capture_bundle(tmp_path)
    evidence.record_step(bundle, title="Now", cmd=_python("print('x')"))
    shot = tmp_path / "old.png"
    shot.write_bytes(PNG)
    old = time.time() - 3600
    os.utime(shot, (old, old))

    art = evidence.record_attach(bundle, shot, step_id="s1", allow_old=True)

    assert art["path"] == "raw/s1/old.png"
    assert (bundle / art["path"]).is_file()


def test_attach_redacts_text_artifacts(tmp_path):
    bundle = _capture_bundle(tmp_path)
    env = tmp_path / "env.txt"
    env.write_text("API_KEY=sk-" + "a" * 32 + "\npassword=hunter2\n")

    art = evidence.record_attach(bundle, env, caption="Environment")

    body = (bundle / art["path"]).read_text()
    assert "sk-" not in body
    assert "hunter2" not in body
    assert "[REDACTED:api-key]" in body
    assert "[REDACTED:password]" in body
    manifest = evidence.load(bundle)
    patterns = {r["pattern"] for r in manifest["redactions"]}
    assert {"api-key", "password"} <= patterns
    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)
    assert report.ok, report.render()


def test_attach_redacts_json_secrets_and_keeps_valid_quotes(tmp_path):
    bundle = _capture_bundle(tmp_path)
    cfg = tmp_path / "config.json"
    cfg.write_text(
        '{"password": "hunter2", "Authorization": "Bearer abcdefghijklmnop"}\n'
    )

    art = evidence.record_attach(bundle, cfg, caption="Config")

    body = (bundle / art["path"]).read_text()
    assert "hunter2" not in body
    assert "Bearer" not in body
    assert '"[REDACTED:json-secret]"' in body
    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)
    assert report.ok, report.render()


def test_attach_unknown_step_is_an_error(tmp_path):
    bundle = _capture_bundle(tmp_path)
    shot = tmp_path / "shot.png"
    shot.write_bytes(PNG)

    with pytest.raises(evidence.EvidenceError, match="unknown step"):
        evidence.record_attach(bundle, shot, step_id="s9")


def test_attach_missing_file_is_an_error(tmp_path):
    bundle = _capture_bundle(tmp_path)

    with pytest.raises(evidence.EvidenceError, match="does not exist"):
        evidence.record_attach(bundle, tmp_path / "nope.png")


def test_attach_sniffs_mime_from_magic_bytes(tmp_path):
    bundle = _capture_bundle(tmp_path)
    shot = tmp_path / "shot.bin"
    shot.write_bytes(PNG)

    art = evidence.record_attach(bundle, shot)

    assert art["mime"] == "image/png"
    assert art["role"] == "screenshot"


def test_attach_records_who_captured_it(tmp_path):
    bundle = _capture_bundle(tmp_path)
    shot = tmp_path / "shot.png"
    shot.write_bytes(PNG)

    art = evidence.record_attach(bundle, shot, by="Hamza")

    assert art["captured_by"] == "Hamza"
    manifest = evidence.load(bundle)
    assert manifest["steps"][0]["captured_by"] == "Hamza"


def test_v1_manifest_still_loads(tmp_path):
    bundle, manifest = _make(tmp_path)
    manifest["schema"] = "openharness.evidence/1"
    _save(bundle, manifest)

    assert evidence.load(bundle)["schema"] == "openharness.evidence/1"


def test_cli_step_passthrough(tmp_path):
    bundle = _capture_bundle(tmp_path)

    run = _cli(
        "--action=step",
        f"--repo={tmp_path}",
        f"--bundle={bundle}",
        "--title=Say hi",
        "--",
        sys.executable,
        "-c",
        "print('hi')",
    )

    assert run.returncode == 0, run.stdout + run.stderr
    assert "Recorded step s1 (pass)" in run.stdout
    assert "hi" in (bundle / "logs" / "s1.log").read_text()


def test_cli_attach(tmp_path):
    bundle = _capture_bundle(tmp_path)
    shot = tmp_path / "shot.png"
    shot.write_bytes(PNG)

    run = _cli(
        "--action=attach",
        f"--repo={tmp_path}",
        f"--bundle={bundle}",
        f"--file={shot}",
        "--caption=Approval card",
    )

    assert run.returncode == 0, run.stdout + run.stderr
    assert "Attached raw/s1/shot.png" in run.stdout


# ------------------------------------------------------------------- attach --from

def test_attach_from_folds_fragment(tmp_path):
    bundle = _capture_bundle(tmp_path)
    shot = tmp_path / "shot.png"
    shot.write_bytes(PNG)

    # Create a fragment manually (simulating what a fixture would emit)
    fragment = {
        "id": "s2",
        "title": "Browser navigation",
        "kind": "browser",
        "status": "pass",
        "started_at": "2026-11-17T18:00:00Z",
        "duration_ms": 1234,
        "log": "logs/s2.log",
        "artifacts": [
            {
                "path": "raw/s2/01-page.png",
                "mime": "image/png",
                "sha256": evidence.sha256(shot),
                "bytes": len(PNG),
                "role": "screenshot",
                "caption": "Page loaded",
            }
        ],
    }

    # Write the fragment to a temp file and attach it
    from_file = tmp_path / "fragment.json"
    from_file.write_text(json.dumps(fragment, indent=2))

    run = _cli(
        "--action=attach",
        f"--repo={tmp_path}",
        f"--bundle={bundle}",
        f"--fragment={from_file}",
    )

    assert run.returncode == 0, run.stdout + run.stderr
    assert "Folded step s2 (pass)" in run.stdout
    assert "artifacts: 1" in run.stdout

    manifest = evidence.load(bundle)
    steps = manifest["steps"]
    assert len(steps) == 2
    assert steps[1]["id"] == "s2"
    assert steps[1]["kind"] == "browser"
    assert steps[1]["status"] == "pass"
    assert steps[1]["artifacts"][0]["caption"] == "Page loaded"


def test_attach_from_infers_artifact_role(tmp_path):
    """`role` is a label: infer it from MIME/suffix, keep an explicit one."""
    bundle = _capture_bundle(tmp_path)
    fragment = {
        "id": "s3",
        "title": "comprehensive test",
        "kind": "browser",
        "status": "pass",
        "started_at": "2026-11-17T21:04:00Z",
        "duration_ms": 3456,
        "log": "",
        "artifacts": [
            # no role: a structured capture is a trace
            {"path": "raw/s3/trace.json", "mime": "application/json",
             "sha256": "c" * 64, "bytes": 300},
            # no role: MIME decides
            {"path": "raw/s3/video.webm", "mime": "video/webm",
             "sha256": "d" * 64, "bytes": 100},
            # no role: the suffix is more specific than the MIME
            {"path": "raw/s3/network.har", "mime": "application/json",
             "sha256": "e" * 64, "bytes": 200},
            # explicit role always wins
            {"path": "raw/s3/notes.json", "mime": "application/json",
             "sha256": "f" * 64, "bytes": 50, "role": "attachment"},
        ],
    }

    from_file = tmp_path / "steps.json"
    from_file.write_text(json.dumps(fragment, indent=2))

    run = _cli(
        "--action=attach",
        f"--repo={tmp_path}",
        f"--bundle={bundle}",
        f"--fragment={from_file}",
    )

    assert run.returncode == 0, run.stdout + run.stderr
    manifest = evidence.load(bundle)
    roles = [a["role"] for a in manifest["steps"][1]["artifacts"]]
    assert roles == ["trace", "video", "har", "attachment"]


def test_attach_from_missing_required_field(tmp_path):
    bundle = _capture_bundle(tmp_path)
    from_file = tmp_path / "fragment.json"
    from_file.write_text('{"id": "s2", "title": "Missing fields"}')

    run = _cli(
        "--action=attach",
        f"--repo={tmp_path}",
        f"--bundle={bundle}",
        f"--fragment={from_file}",
    )

    assert run.returncode == 2, run.stdout + run.stderr
    assert "missing required field" in run.stderr


def test_attach_from_duplicate_id(tmp_path):
    bundle = _capture_bundle(tmp_path)
    evidence.record_step(bundle, title="First", cmd="echo x")

    fragment = {
        "id": "s1",  # duplicate
        "title": "Duplicate",
        "kind": "browser",
        "status": "pass",
        "started_at": "2026-11-17T18:00:00Z",
        "duration_ms": 1234,
        "log": "logs/s1.log",
        "artifacts": [],
    }

    from_file = tmp_path / "fragment.json"
    from_file.write_text(json.dumps(fragment, indent=2))

    run = _cli(
        "--action=attach",
        f"--repo={tmp_path}",
        f"--bundle={bundle}",
        f"--fragment={from_file}",
    )

    assert run.returncode == 2, run.stdout + run.stderr
    assert "already exists" in run.stderr


def test_attach_from_invalid_json(tmp_path):
    bundle = _capture_bundle(tmp_path)
    from_file = tmp_path / "fragment.json"
    from_file.write_text("not json {")

    run = _cli(
        "--action=attach",
        f"--repo={tmp_path}",
        f"--bundle={bundle}",
        f"--fragment={from_file}",
    )

    assert run.returncode == 2, run.stdout + run.stderr
    assert "invalid JSON fragment" in run.stderr


def test_attach_from_invalid_kind(tmp_path):
    bundle = _capture_bundle(tmp_path)
    fragment = {
        "id": "s2",
        "title": "Browser navigation",
        "kind": "unknown",  # invalid
        "status": "pass",
        "started_at": "2026-11-17T18:00:00Z",
        "duration_ms": 1234,
        "log": "logs/s2.log",
        "artifacts": [],
    }

    from_file = tmp_path / "fragment.json"
    from_file.write_text(json.dumps(fragment, indent=2))

    run = _cli(
        "--action=attach",
        f"--repo={tmp_path}",
        f"--bundle={bundle}",
        f"--fragment={from_file}",
    )

    assert run.returncode == 2, run.stdout + run.stderr
    assert "fragment kind must be one of" in run.stderr


def test_attach_from_invalid_status(tmp_path):
    bundle = _capture_bundle(tmp_path)
    fragment = {
        "id": "s2",
        "title": "Browser navigation",
        "kind": "browser",
        "status": "unknown",  # invalid
        "started_at": "2026-11-17T18:00:00Z",
        "duration_ms": 1234,
        "log": "logs/s2.log",
        "artifacts": [],
    }

    from_file = tmp_path / "fragment.json"
    from_file.write_text(json.dumps(fragment, indent=2))

    run = _cli(
        "--action=attach",
        f"--repo={tmp_path}",
        f"--bundle={bundle}",
        f"--fragment={from_file}",
    )

    assert run.returncode == 2, run.stdout + run.stderr
    assert "fragment status must be one of" in run.stderr


def test_attach_from_invalid_artifact(tmp_path):
    """A manifest-ready artifact still needs every proving field; only
    `role` is inferred. (An artifact without `sha256` is a source file
    instead — see the source-mode tests below.)"""
    bundle = _capture_bundle(tmp_path)
    fragment = {
        "id": "s2",
        "title": "Browser navigation",
        "kind": "browser",
        "status": "pass",
        "started_at": "2026-11-17T18:00:00Z",
        "duration_ms": 1234,
        "log": "logs/s2.log",
        "artifacts": [
            {
                "path": "raw/s2/01-page.png",
                "sha256": "0" * 64,
                "bytes": 100,
                # missing mime
            }
        ],
    }

    from_file = tmp_path / "fragment.json"
    from_file.write_text(json.dumps(fragment, indent=2))

    run = _cli(
        "--action=attach",
        f"--repo={tmp_path}",
        f"--bundle={bundle}",
        f"--fragment={from_file}",
    )

    assert run.returncode == 2, run.stdout + run.stderr
    assert "artifact missing required field" in run.stderr


# ---------- TDD steps (ADR 0008) ----------

def _tdd_bundle(tmp_path: Path, *, red_expected: bool = True) -> Path:
    """A bundle with a real ordered red -> green -> refactor run."""
    bundle = evidence.new_bundle(
        tmp_path, "cart", wave=1, head=HEAD, run="20260101T000000Z-tdd1"
    )
    py = f'"{sys.executable}"'
    evidence.record_step(
        bundle, title="RED", tdd="red", expected_failure=red_expected,
        cmd=f"{py} -c \"import sys; sys.exit(1)\"",
    )
    evidence.record_step(
        bundle, title="GREEN", tdd="green", cmd=f"{py} -c \"pass\""
    )
    evidence.record_step(
        bundle, title="REFACTOR", tdd="refactor", cmd=f"{py} -c \"pass\""
    )
    return bundle


def test_record_step_stamps_the_tdd_phase(tmp_path):
    bundle = _tdd_bundle(tmp_path)
    manifest = evidence.load(bundle)
    assert [s["tdd"] for s in manifest["steps"]] == ["red", "green", "refactor"]


def test_record_step_rejects_an_unknown_tdd_phase(tmp_path):
    bundle = evidence.new_bundle(
        tmp_path, "cart", head=HEAD, run="20260101T000000Z-tdd2"
    )
    with pytest.raises(evidence.EvidenceError):
        evidence.record_step(bundle, cmd="true", tdd="purple")


def test_tdd_proof_accepts_an_ordered_run(tmp_path):
    manifest = evidence.load(_tdd_bundle(tmp_path))
    proof = evidence.tdd_proof(manifest)
    assert proof["ok"], proof["problems"]
    assert set(proof["phases"]) == {"red", "green", "refactor"}


def test_tdd_proof_requires_every_phase(tmp_path):
    bundle = _tdd_bundle(tmp_path)
    manifest = evidence.load(bundle)
    manifest["steps"] = [s for s in manifest["steps"] if s["tdd"] != "refactor"]
    proof = evidence.tdd_proof(manifest)
    assert not proof["ok"]
    assert any("refactor" in p for p in proof["problems"])


def test_tdd_proof_rejects_a_red_step_that_passed(tmp_path):
    bundle = _tdd_bundle(tmp_path)
    manifest = evidence.load(bundle)
    for s in manifest["steps"]:
        if s["tdd"] == "red":
            s["status"] = "pass"
            s["exit_code"] = 0
    proof = evidence.tdd_proof(manifest)
    assert not proof["ok"]
    assert any("red step" in p for p in proof["problems"])


def test_tdd_proof_rejects_red_without_expected_failure(tmp_path):
    manifest = evidence.load(_tdd_bundle(tmp_path, red_expected=False))
    proof = evidence.tdd_proof(manifest)
    assert not proof["ok"]
    assert any("expected_failure" in p for p in proof["problems"])


def test_tdd_proof_rejects_out_of_order_runs(tmp_path):
    manifest = evidence.load(_tdd_bundle(tmp_path))
    stamps = {
        "red": "2026-01-01T00:00:03Z",
        "green": "2026-01-01T00:00:01Z",
        "refactor": "2026-01-01T00:00:02Z",
    }
    for s in manifest["steps"]:
        s["started_at"] = stamps[s["tdd"]]
    proof = evidence.tdd_proof(manifest)
    assert not proof["ok"]
    assert any("after" in p for p in proof["problems"])


def test_new_bundle_kind_walkthrough_stays_in_scratch(tmp_path):
    bundle = evidence.new_bundle(
        tmp_path, "cart", head=HEAD, run="20260101T000000Z-abc1234", kind="walkthrough"
    )
    assert bundle.parent == tmp_path / ".openharness" / "evidence" / "cart"
    assert evidence.load(bundle)["kind"] == "walkthrough"


def test_new_bundle_kind_defaults_to_proof(tmp_path):
    bundle = evidence.new_bundle(tmp_path, "cart", head=HEAD, run="20260101T000000Z-abc1234")
    assert evidence.load(bundle)["kind"] == "proof"


def test_walkthrough_cannot_be_tracked(tmp_path):
    with pytest.raises(evidence.EvidenceError, match="local-only"):
        evidence.new_bundle(
            tmp_path, "cart", head=HEAD, run="20260101T000000Z-abc1234",
            tracked=True, kind="walkthrough",
        )


def test_new_bundle_rejects_unknown_kind(tmp_path):
    with pytest.raises(evidence.EvidenceError, match="kind must be one of"):
        evidence.new_bundle(tmp_path, "cart", head=HEAD, kind="bogus")


def test_manifest_without_kind_loads_as_proof(tmp_path):
    bundle = evidence.new_bundle(tmp_path, "cart", head=HEAD, run="20260101T000000Z-abc1234")
    manifest = json.loads((bundle / "evidence.json").read_text())
    del manifest["kind"]
    _save(bundle, manifest)
    assert "kind" not in evidence.load(bundle)
    rows = evidence.list_bundles(tmp_path)
    assert rows[0]["kind"] == "proof"


def test_manifest_with_invalid_kind_is_rejected(tmp_path):
    bundle = evidence.new_bundle(tmp_path, "cart", head=HEAD, run="20260101T000000Z-abc1234")
    manifest = json.loads((bundle / "evidence.json").read_text())
    manifest["kind"] = "bogus"
    _save(bundle, manifest)
    with pytest.raises(evidence.EvidenceError, match="kind must be one of"):
        evidence.load(bundle)


def test_verify_warns_walkthrough_in_tracked_root(tmp_path):
    if not shutil.which("git"):
        pytest.skip("git not installed")
    _git_init(tmp_path)
    bundle = evidence.new_bundle(
        tmp_path, "cart", head=HEAD, run="20260101T000000Z-abc1234",
        tracked=True, kind="proof",
    )
    manifest = json.loads((bundle / "evidence.json").read_text())
    manifest["kind"] = "walkthrough"
    _save(bundle, manifest)
    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)
    assert "walkthrough-in-tracked-root" in _codes(report)
    assert report.ok  # a warning, not an error


def test_proof_bundle_in_tracked_root_has_no_kind_warning(tmp_path):
    if not shutil.which("git"):
        pytest.skip("git not installed")
    _git_init(tmp_path)
    bundle = evidence.new_bundle(
        tmp_path, "cart", head=HEAD, run="20260101T000000Z-abc1234", tracked=True
    )
    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)
    assert "walkthrough-in-tracked-root" not in _codes(report)


def test_list_rows_carry_kind(tmp_path):
    proof, _ = _make(tmp_path)
    wt = evidence.new_bundle(
        tmp_path, "cart", head=HEAD, run="20260202T000000Z-def5678", kind="walkthrough"
    )
    rows = {r["bundle"]: r for r in evidence.list_bundles(tmp_path)}
    assert rows[proof]["kind"] == "proof"
    assert rows[wt]["kind"] == "walkthrough"


def test_render_shows_walkthrough_kind(tmp_path):
    bundle = evidence.new_bundle(
        tmp_path, "cart", head=HEAD, run="20260101T000000Z-abc1234", kind="walkthrough"
    )
    paths = evidence.render(bundle)
    html_text = paths["html"].read_text()
    assert "walkthrough" in html_text
    assert "walkthrough" in paths["summary"].read_text()


# ------------------------------------------------------- fragment source mode

def _source_fragment(tmp_path: Path, art_path: Path, **step_over) -> Path:
    frag_dir = tmp_path / "run"
    frag_dir.mkdir(exist_ok=True)
    step = {
        "id": "pw-s1",
        "title": "Browser: create note",
        "kind": "browser",
        "status": "pass",
        "started_at": "2026-11-17T18:00:00Z",
        "duration_ms": 800,
        "artifacts": [{"path": art_path.name, "caption": "note created"}],
    }
    step.update(step_over)
    frag = frag_dir / "steps.json"
    frag.write_text(json.dumps(step))
    return frag


def test_fragment_source_artifact_is_copied_and_hashed(tmp_path):
    bundle = _capture_bundle(tmp_path)
    frag_dir = tmp_path / "run"
    frag_dir.mkdir()
    shot = frag_dir / "shot.png"  # media lives next to steps.json
    shot.write_bytes(PNG)
    frag = _source_fragment(tmp_path, shot)

    run = _cli(
        "--action=attach", f"--repo={tmp_path}", f"--bundle={bundle}",
        f"--fragment={frag}",
    )

    assert run.returncode == 0, run.stdout + run.stderr
    manifest = evidence.load(bundle)
    art = manifest["steps"][-1]["artifacts"][0]
    # copied under raw/<step>/ and hashed by the harness, not the producer
    assert art["path"].startswith("raw/pw-s1/")
    assert art["sha256"] == evidence.sha256(bundle / art["path"])
    assert art["mime"] == "image/png"
    assert art["role"] == "screenshot"
    assert art["caption"] == "note created"
    report = evidence.verify(bundle, repo=tmp_path, head=HEAD)
    assert report.ok, [f.message for f in report.errors]


def test_fragment_source_artifact_missing_file_fails(tmp_path):
    bundle = _capture_bundle(tmp_path)
    frag = _source_fragment(tmp_path, tmp_path / "nope.png")

    run = _cli(
        "--action=attach", f"--repo={tmp_path}", f"--bundle={bundle}",
        f"--fragment={frag}",
    )

    assert run.returncode != 0
    assert "not found" in run.stderr or "does not exist" in run.stderr


def test_fragment_source_artifact_stale_needs_allow_old(tmp_path):
    bundle = _capture_bundle(tmp_path)
    frag_dir = tmp_path / "run"
    frag_dir.mkdir()
    shot = frag_dir / "shot.png"
    shot.write_bytes(PNG)
    frag = _source_fragment(
        tmp_path, shot, started_at="2099-01-01T00:00:00Z"
    )

    run = _cli(
        "--action=attach", f"--repo={tmp_path}", f"--bundle={bundle}",
        f"--fragment={frag}",
    )
    assert run.returncode != 0
    assert "older than step" in run.stderr

    run = _cli(
        "--action=attach", f"--repo={tmp_path}", f"--bundle={bundle}",
        f"--fragment={frag}", "--allow-old",
    )
    assert run.returncode == 0, run.stdout + run.stderr


def test_fragment_mixed_artifact_forms(tmp_path):
    bundle = _capture_bundle(tmp_path)
    frag_dir = tmp_path / "run"
    frag_dir.mkdir()
    shot = frag_dir / "shot.png"
    shot.write_bytes(PNG)
    # manifest-ready artifact (bundle-relative, producer hash) + source file
    step = {
        "id": "pw-s2",
        "title": "mixed",
        "kind": "browser",
        "status": "pass",
        "started_at": "2026-11-17T18:00:00Z",
        "artifacts": [
            {
                "path": "raw/pw-s2/already.png",
                "mime": "image/png",
                "sha256": evidence.sha256(shot),
                "bytes": len(PNG),
            },
            {"path": shot.name, "caption": "from source"},
        ],
    }
    frag = frag_dir / "steps.json"
    frag.write_text(json.dumps(step))
    # place the manifest-ready file where the fragment claims it lives
    ready = bundle / "raw" / "pw-s2" / "already.png"
    ready.parent.mkdir(parents=True, exist_ok=True)
    ready.write_bytes(PNG)

    run = _cli(
        "--action=attach", f"--repo={tmp_path}", f"--bundle={bundle}",
        f"--fragment={frag}",
    )

    assert run.returncode == 0, run.stdout + run.stderr
    arts = evidence.load(bundle)["steps"][-1]["artifacts"]
    assert arts[0]["path"] == "raw/pw-s2/already.png"
    assert arts[1]["path"].startswith("raw/pw-s2/shot")


# ------------------------------------------------------------------- fixture

def test_fixture_writes_playwright_fixture(tmp_path):
    run = _cli("--action=fixture", f"--repo={tmp_path}")

    assert run.returncode == 0, run.stdout + run.stderr
    target = tmp_path / "e2e" / "evidence.fixture.ts"
    assert target.is_file()
    text = target.read_text()
    assert "EVIDENCE_RUN_DIR" in text
    assert "steps-" in text
    assert "--kind=walkthrough" in run.stdout


def test_fixture_refuses_overwrite_without_force(tmp_path):
    _cli("--action=fixture", f"--repo={tmp_path}")
    run = _cli("--action=fixture", f"--repo={tmp_path}")
    assert run.returncode != 0
    assert "already exists" in run.stderr

    run = _cli("--action=fixture", f"--repo={tmp_path}", "--force")
    assert run.returncode == 0, run.stdout + run.stderr


def test_fixture_warns_without_playwright(tmp_path):
    (tmp_path / "package.json").write_text('{"devDependencies": {}}')
    run = _cli("--action=fixture", f"--repo={tmp_path}")
    assert run.returncode == 0
    assert "@playwright/test" in run.stdout


def test_fixture_rejects_escaping_out_dir(tmp_path):
    run = _cli("--action=fixture", f"--repo={tmp_path}", "--out_dir=../x")
    assert run.returncode != 0
    assert "relative path" in run.stderr


# ----------------------------------------------------------------- capture

ADB_SH = """\
[ "$1" = "-s" ] && shift 2
case "$1" in
  exec-out) printf 'PNGDATA' ;;
  shell)
    case "$2" in screenrecord|rm) : ;; esac ;;
  pull)
    for last; do :; done
    printf 'MP4DATA' > "$last" ;;
  logcat) printf 'logcat-line\\n' ;;
esac
exit 0
"""

XCRUN_SH = """\
if [ "$1" = "simctl" ] && [ "$2" = "io" ]; then
  for last; do :; done
  if [ "$4" = "recordVideo" ]; then
    printf 'MOVDATA' > "$last"
    trap 'exit 0' INT TERM
    sleep 300
  fi
  printf 'PNGDATA' > "$last"
  exit 0
fi
if [ "$1" = "simctl" ] && [ "$2" = "spawn" ]; then printf 'ios-log\\n'; exit 0; fi
exit 1
"""


def _fake_tool(tmp_path: Path, name: str, body: str, monkeypatch) -> None:
    bindir = tmp_path / "fakebin"
    bindir.mkdir(exist_ok=True)
    tool = bindir / name
    tool.write_text("#!/bin/sh\n" + body)
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")


def _walkthrough(tmp_path: Path) -> Path:
    return evidence.new_bundle(
        tmp_path, "cart", wave=1, head=HEAD, run="wt-1", kind="walkthrough"
    )


def test_capture_android_screenshot_attaches_media(tmp_path, monkeypatch):
    _fake_tool(tmp_path, "adb", ADB_SH, monkeypatch)
    bundle = _walkthrough(tmp_path)

    out = harness_evidence.invoke(
        action="capture", repo=str(tmp_path), bundle=str(bundle),
        device="android", media="screenshot",
    )

    assert "Captured 1 artifact" in out
    arts = evidence.load(bundle)["steps"][-1]["artifacts"]
    assert arts[0]["role"] == "screenshot"
    assert "android screenshot" in arts[0]["caption"]


def test_capture_android_all_media(tmp_path, monkeypatch):
    _fake_tool(tmp_path, "adb", ADB_SH, monkeypatch)
    bundle = _walkthrough(tmp_path)

    out = harness_evidence.invoke(
        action="capture", repo=str(tmp_path), bundle=str(bundle),
        device="android", media="all",
    )

    assert "Captured 3 artifact" in out
    arts = evidence.load(bundle)["steps"][-1]["artifacts"]
    assert [a["role"] for a in arts] == ["screenshot", "video", "attachment"]


def test_capture_ios_screenshot(tmp_path, monkeypatch):
    _fake_tool(tmp_path, "xcrun", XCRUN_SH, monkeypatch)
    bundle = _walkthrough(tmp_path)

    out = harness_evidence.invoke(
        action="capture", repo=str(tmp_path), bundle=str(bundle),
        device="ios", media="screenshot",
    )

    assert "Captured 1 artifact" in out
    arts = evidence.load(bundle)["steps"][-1]["artifacts"]
    assert arts[0]["role"] == "screenshot"
    assert "ios simulator" in arts[0]["caption"]


def test_capture_requires_device_and_media(tmp_path):
    with pytest.raises(SkillError, match="--device"):
        harness_evidence.invoke(action="capture", repo=str(tmp_path))
    with pytest.raises(SkillError, match="media"):
        harness_evidence.invoke(
            action="capture", repo=str(tmp_path), device="android",
            media="bogus",
        )


def test_capture_fails_loudly_without_device_tool(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
    bundle = _walkthrough(tmp_path)

    with pytest.raises(SkillError, match="adb not found"):
        harness_evidence.invoke(
            action="capture", repo=str(tmp_path), bundle=str(bundle),
            device="android",
        )


# ----------------------------------------------------------------- share

def test_share_writes_zip_and_sha256(tmp_path):
    bundle, _ = _make(tmp_path)

    out = harness_evidence.invoke(
        action="share", repo=str(tmp_path), bundle=str(bundle)
    )

    zip_path = bundle.parent / f"{bundle.name}.zip"
    assert zip_path.is_file()
    assert "sha256" in out
    import zipfile
    names = zipfile.ZipFile(zip_path).namelist()
    assert any(n.startswith(bundle.name + "/") for n in names)
    assert Path(str(zip_path) + ".sha256").is_file()


def test_share_public_copies_a_verified_bundle(tmp_path):
    bundle, _ = _make(tmp_path)

    out = harness_evidence.invoke(
        action="share", repo=str(tmp_path), bundle=str(bundle), public=True
    )

    dest = tmp_path / "docs" / "evidence" / "cart" / bundle.name
    assert (dest / "evidence.json").is_file()
    assert "not secret-scanned" in out
    with pytest.raises(SkillError, match="already exists"):
        harness_evidence.invoke(
            action="share", repo=str(tmp_path), bundle=str(bundle), public=True
        )


# ----------------------------------------------------------------- prune

def test_prune_keeps_newest_and_loop_referenced(tmp_path):
    root = tmp_path / ".openharness" / "evidence" / "cart"
    for i in range(1, 5):
        evidence.new_bundle(tmp_path, "cart", run=f"run-{i}", head=HEAD)
    d = tmp_path / "specs" / "cart"
    d.mkdir(parents=True)
    (d / "LOOP.state.json").write_text(json.dumps(
        {"waves": {"1": {"bundle": "run-1"}}}
    ))

    out = harness_evidence.invoke(action="prune", repo=str(tmp_path), keep=2)

    assert sorted(p.name for p in root.iterdir()) == ["run-1", "run-3", "run-4"]
    assert "run-1" in out  # referenced bundle reported as skipped


def test_prune_requires_keep(tmp_path):
    with pytest.raises(SkillError, match="--keep"):
        harness_evidence.invoke(action="prune", repo=str(tmp_path), keep=0)
