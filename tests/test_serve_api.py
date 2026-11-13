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
