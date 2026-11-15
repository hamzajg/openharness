import json

import openharness.serve_api as serve_api
from fastapi.testclient import TestClient

from openharness.serve import app

client = TestClient(app)


def test_repos_status_reports_missing_clone():
    r = client.get("/api/repos/status", params={"names": "definitely-not-a-repo"})
    assert r.status_code == 200
    assert r.json() == {"definitely-not-a-repo": {"exists": False, "default_branch": None}}


def test_repos_status_without_names_returns_mapping():
    r = client.get("/api/repos/status")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


def test_repos_prune_skips_missing_clone():
    r = client.post("/api/repos/prune", json={"names": ["definitely-not-a-repo"]})
    assert r.status_code == 200
    rec = r.json()["definitely-not-a-repo"]
    assert rec["skipped"] == "not cloned"


def test_repos_sync_unknown_name_is_a_noop():
    r = client.post("/api/repos/sync", json={"names": ["definitely-not-a-repo"]})
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def _write_loop(root, repo, feature, payload):
    d = root / "sources" / repo / "specs" / feature
    d.mkdir(parents=True)
    (d / "LOOP.state.json").write_text(json.dumps(payload))


def test_loops_empty_when_no_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(serve_api, "_loops_root", lambda: tmp_path / "sources")
    r = client.get("/api/loops")
    assert r.status_code == 200
    assert r.json() == {"loops": []}


def test_loops_lists_state_files(tmp_path, monkeypatch):
    _write_loop(tmp_path, "RepoA", "feat-x", {
        "feature": "feat-x", "status": "running", "iterations": 2,
        "updated": "2026-01-01T00:00:00Z",
        "waves": {"1": {"status": "done"}, "2": {"status": "in-progress"}},
        "gates": {"G1": {"status": "pending"}},
        "events": ["2026-01-01T00:00:00Z start wave 1"],
    })
    _write_loop(tmp_path, "RepoB", "feat-y", {
        "feature": "feat-y", "status": "done", "iterations": 5,
        "updated": "2026-01-02T00:00:00Z",
        "waves": {"1": {"status": "done"}},
        "gates": {}, "events": [],
    })
    # malformed file is skipped, not fatal
    bad = tmp_path / "sources" / "RepoC" / "specs" / "feat-z"
    bad.mkdir(parents=True)
    (bad / "LOOP.state.json").write_text("{not json")

    monkeypatch.setattr(serve_api, "_loops_root", lambda: tmp_path / "sources")
    loops = client.get("/api/loops").json()["loops"]
    assert len(loops) == 2
    # sorted by updated desc
    assert loops[0]["repo"] == "RepoB"
    first = next(l for l in loops if l["repo"] == "RepoA")
    assert first["waves_total"] == 2 and first["waves_done"] == 1
    assert first["gates_total"] == 1 and first["gates_pending"] == 1
    assert first["last_event"].endswith("start wave 1")


def test_loop_detail_and_404(tmp_path, monkeypatch):
    _write_loop(tmp_path, "RepoA", "feat-x", {
        "feature": "feat-x", "status": "blocked", "iterations": 3,
        "updated": "2026-01-01T00:00:00Z",
        "waves": {"1": {"status": "done", "branch": "b", "pr": "#1",
                        "evidence": "green", "updated": "t"}},
        "gates": {"G1": {"status": "pending", "evidence": "—", "updated": "—"}},
        "events": ["e1"],
    })
    monkeypatch.setattr(serve_api, "_loops_root", lambda: tmp_path / "sources")
    r = client.get("/api/loops/RepoA/feat-x")
    assert r.status_code == 200
    body = r.json()
    assert body["repo"] == "RepoA" and body["feature"] == "feat-x"
    assert body["status"] == "blocked" and body["events"] == ["e1"]
    assert client.get("/api/loops/RepoA/nope").status_code == 404


def test_evolution_shape():
    r = client.get("/api/evolution")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"decisions", "commits", "stats"}
    assert isinstance(body["decisions"], list)
    assert isinstance(body["commits"], list)
    assert isinstance(body["stats"], dict)
    for d in body["decisions"]:
        assert {"id", "title", "rule", "because"} <= set(d)
        assert d["id"].startswith("D")
    for c in body["commits"]:
        assert {"sha", "date", "subject", "type"} <= set(c)


def test_parse_decisions_extracts_rule_and_because(tmp_path):
    p = tmp_path / "PRINCIPLES.md"
    p.write_text(
        "### D001 — First decision\n"
        "Rule: Do the thing.\n"
        "Because: Reasons.\n\n"
        "### D002 — Second decision\n"
        "Rule: Other thing.\n"
    )
    ds = serve_api._parse_decisions(p)
    assert [d["id"] for d in ds] == ["D001", "D002"]
    assert ds[0]["title"] == "First decision"
    assert ds[0]["rule"] == "Do the thing."
    assert ds[0]["because"] == "Reasons."
    assert ds[1]["because"] == ""
