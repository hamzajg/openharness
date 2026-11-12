import os
import subprocess
from pathlib import Path

from openharness.repos import entries, prune, status, sync


def _make_local_repo(tmp_path: Path, name: str) -> Path:
    p = tmp_path / "upstream" / name
    p.mkdir(parents=True)
    subprocess.run(["git", "init", "-b", "main", str(p)], check=True, capture_output=True)
    (p / "README.md").write_text(f"# {name}\n")
    subprocess.run(["git", "-C", str(p), "add", "README.md"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(p), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-m", "init"], check=True, capture_output=True)
    return p


def _write_repos_md(root: Path, rows: list[tuple[str, str, str, str]]):
    lines = [
        "---",
        "repos: [" + ", ".join(n for n, *_ in rows) + "]",
        "---",
        "# Managed Repositories",
        "",
        "| name | url | branch | stage |",
        "|------|-----|--------|-------|",
    ]
    for n, url, b, st in rows:
        lines.append(f"| {n} | {url} | {b} | {st} |")
    (root / "REPOS.md").write_text("\n".join(lines) + "\n")


def test_entries_parses_table(tmp_path):
    repo = _make_local_repo(tmp_path, "proj")
    cwd = Path.cwd()
    os.chdir(tmp_path)
    try:
        _write_repos_md(tmp_path, [("proj", f"file://{repo}", "main", "greenfield")])
        e = entries()
        assert "proj" in e
        assert e["proj"]["url"] == f"file://{repo}"
        assert e["proj"]["branch"] == "main"
    finally:
        os.chdir(cwd)


def test_sync_clones_and_pulls(tmp_path, monkeypatch):
    up = _make_local_repo(tmp_path, "mini")
    work = tmp_path / "work"
    work.mkdir()
    _write_repos_md(work, [("mini", f"file://{up}", "main", "modernization")])
    cwd = Path.cwd()
    os.chdir(work)
    try:
        sync("mini")
        dest = work / "sources" / "mini"
        assert dest.exists()
        assert (dest / "README.md").read_text().startswith("# mini")

        # second call = pull
        (up / "NEW.md").write_text("new file\n")
        subprocess.run(["git", "-C", str(up), "add", "NEW.md"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(up), "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-m", "update"], check=True, capture_output=True)
        sync("mini")
        assert (dest / "NEW.md").exists()
    finally:
        os.chdir(cwd)


def test_status_reports_repo_state(tmp_path):
    up = _make_local_repo(tmp_path, "status-proj")
    work = tmp_path / "work"
    work.mkdir()
    _write_repos_md(work, [
        ("status-proj", f"file://{up}", "main", "modernization"),
        ("missing-proj", "file:///tmp/nope", "main", "modernization"),
    ])
    cwd = Path.cwd()
    os.chdir(work)
    try:
        st = status()
        assert st["missing-proj"]["exists"] is False

        sync("status-proj")
        st = status("status-proj")
        assert st["status-proj"]["exists"] is True
        assert st["status-proj"]["branch"] == "main"
        assert st["status-proj"]["dirty"] is False

        # Make it dirty
        dest = work / "sources" / "status-proj"
        (dest / "dirty.txt").write_text("uncommitted")
        st = status("status-proj")
        assert st["status-proj"]["dirty"] is True
    finally:
        os.chdir(cwd)


def test_sync_switches_to_target_branch(tmp_path):
    up = _make_local_repo(tmp_path, "branch-proj")
    work = tmp_path / "work"
    work.mkdir()
    _write_repos_md(work, [("branch-proj", f"file://{up}", "main", "modernization")])
    cwd = Path.cwd()
    os.chdir(work)
    try:
        sync("branch-proj")
        dest = work / "sources" / "branch-proj"
        # Create and checkout feature branch
        subprocess.run(["git", "-C", str(dest), "checkout", "-b", "feat/my-feature"], check=True, capture_output=True)
        assert status("branch-proj")["branch-proj"]["branch"] == "feat/my-feature"

        # sync should switch back to main
        sync("branch-proj")
        assert status("branch-proj")["branch-proj"]["branch"] == "main"
    finally:
        os.chdir(cwd)


def _commit_file(repo: Path, name: str, content: str, message: str):
    (repo / name).write_text(content)
    subprocess.run(["git", "-C", str(repo), "add", name], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-m", message], check=True, capture_output=True)


def test_prune_deletes_only_merged_local_branches(tmp_path):
    up = _make_local_repo(tmp_path, "prune-proj")
    work = tmp_path / "work"
    work.mkdir()
    _write_repos_md(work, [("prune-proj", f"file://{up}", "main", "modernization")])
    cwd = Path.cwd()
    os.chdir(work)
    try:
        sync("prune-proj")
        dest = work / "sources" / "prune-proj"

        # A merged branch: commit on a branch, merge it back into main upstream.
        subprocess.run(["git", "-C", str(dest), "checkout", "-b", "feat/old"], check=True, capture_output=True)
        _commit_file(dest, "old.txt", "old\n", "old work")
        subprocess.run(["git", "-C", str(dest), "checkout", "main"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(dest), "merge", "--no-ff", "feat/old", "-m", "merge old"],
                       check=True, capture_output=True)
        # An unmerged branch: work that never landed.
        subprocess.run(["git", "-C", str(dest), "checkout", "-b", "feat/wip"], check=True, capture_output=True)
        _commit_file(dest, "wip.txt", "wip\n", "wip work")

        res = prune("prune-proj")
        rec = res["prune-proj"]
        assert rec["local"] == ["feat/old"]
        assert rec["remote"] == []
        branches = subprocess.run(["git", "-C", str(dest), "branch", "--format=%(refname:short)"],
                                  capture_output=True, text=True).stdout.split()
        assert "feat/old" not in branches
        assert "feat/wip" in branches
        assert "main" in branches
    finally:
        os.chdir(cwd)


def test_prune_remote_deletes_merged_remote_branches(tmp_path):
    # The remote must be bare: git refuses pushes to a non-bare repo's
    # checked-out branch, which is what a real origin never is.
    up = _make_local_repo(tmp_path, "prune-remote-seed")
    bare = tmp_path / "prune-remote.git"
    subprocess.run(["git", "clone", "--bare", str(up), str(bare)], check=True, capture_output=True)
    work = tmp_path / "work"
    work.mkdir()
    _write_repos_md(work, [("prune-remote", f"file://{bare}", "main", "modernization")])
    cwd = Path.cwd()
    os.chdir(work)
    try:
        sync("prune-remote")
        dest = work / "sources" / "prune-remote"

        # Push a branch upstream, then merge it into main upstream so the
        # remote branch is fully contained in origin/main.
        subprocess.run(["git", "-C", str(dest), "checkout", "-b", "feat/landed"], check=True, capture_output=True)
        _commit_file(dest, "landed.txt", "landed\n", "landed work")
        subprocess.run(["git", "-C", str(dest), "push", "-u", "origin", "feat/landed"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(dest), "checkout", "main"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(dest), "merge", "--no-ff", "feat/landed", "-m", "merge landed"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(dest), "push", "origin", "main"], check=True, capture_output=True)

        # A remote branch that never merged must survive.
        subprocess.run(["git", "-C", str(dest), "checkout", "-b", "feat/stale"], check=True, capture_output=True)
        _commit_file(dest, "stale.txt", "stale\n", "stale work")
        subprocess.run(["git", "-C", str(dest), "push", "-u", "origin", "feat/stale"],
                       check=True, capture_output=True)
        subprocess.run(["git", "-C", str(dest), "checkout", "main"], check=True, capture_output=True)

        res = prune("prune-remote", remote=True)
        rec = res["prune-remote"]
        assert "feat/landed" in rec["remote"]
        assert "feat/stale" not in rec["remote"]

        remote_heads = subprocess.run(
            ["git", "-C", str(bare), "branch", "--format=%(refname:short)"],
            capture_output=True, text=True).stdout.split()
        assert "feat/landed" not in remote_heads
        assert "feat/stale" in remote_heads
        assert "main" in remote_heads
    finally:
        os.chdir(cwd)

