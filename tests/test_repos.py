import os
import subprocess
from pathlib import Path

from openharness.repos import entries, sync


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
