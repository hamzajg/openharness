import re, subprocess as _sp
from pathlib import Path

_ROW = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$")


def entries(path=None) -> dict:
    p = Path(path or (Path.cwd()/"REPOS.md"))
    out: dict = {}
    if not p.exists(): return out
    for ln in p.read_text().splitlines():
        m = _ROW.match(ln)
        if not m: continue
        n,u,b,s = (m.group(i).strip() for i in (1,2,3,4))
        if n in ("name","") or "---" in n or not u: continue
        out[n] = {"url":u,"branch":b,"stage":s}
    return out


def status(*names, repos_path=None) -> dict:
    all_e = entries(repos_path)
    targets = list(names) if names else list(all_e.keys())
    src = Path.cwd() / "sources"
    out = {}
    for n in targets:
        e = all_e.get(n, {})
        d = src / n
        if not d.exists() or not (d / ".git").exists():
            out[n] = {"exists": False, "default_branch": e.get("branch")}
            continue
        try:
            br_res = _sp.run(["git", "-C", str(d), "branch", "--show-current"], capture_output=True, text=True, check=True)
            br = br_res.stdout.strip()
            st_res = _sp.run(["git", "-C", str(d), "status", "--porcelain"], capture_output=True, text=True, check=True)
            dirty = bool(st_res.stdout.strip())
            ahead = 0
            behind = 0
            rev_res = _sp.run(["git", "-C", str(d), "rev-list", "--left-right", "--count", f"HEAD...origin/{br}"], capture_output=True, text=True)
            if rev_res.returncode == 0:
                parts = rev_res.stdout.strip().split()
                if len(parts) == 2:
                    ahead, behind = int(parts[0]), int(parts[1])
            out[n] = {
                "exists": True,
                "branch": br,
                "default_branch": e.get("branch"),
                "dirty": dirty,
                "ahead": ahead,
                "behind": behind,
            }
        except Exception as ex:
            out[n] = {"exists": True, "error": str(ex), "default_branch": e.get("branch")}
    return out


def _git(d: Path, *args, check=True):
    return _sp.run(["git", "-C", str(d), *args], capture_output=True, text=True, check=check)


def _default_branch(d: Path, declared: str | None) -> str | None:
    """The branch work lands on: REPOS.md's column first, then origin/HEAD."""
    if declared:
        return declared
    res = _git(d, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
    if res.returncode == 0 and res.stdout.strip():
        return res.stdout.strip().removeprefix("origin/")
    for cand in ("main", "master"):
        if _git(d, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{cand}", check=False).returncode == 0:
            return cand
    return None


def prune(*names, remote=False, repos_path=None) -> dict:
    """Delete branches whose work already landed on the default branch.

    Local branches are removed with `git branch -d`, which refuses anything
    not fully merged — safe by construction. With `remote=True`, remote
    branches fully merged into `origin/<default>` are deleted on the remote
    too; that is the post-merge sweep a factory run does after every PR.

    Returns {name: {"local": [...], "remote": [...], "skipped": str|None}}.
    """
    all_e = entries(repos_path)
    targets = list(names) if names else list(all_e.keys())
    src = Path.cwd() / "sources"
    out = {}
    for n in targets:
        e = all_e.get(n, {})
        d = src / n
        rec = {"local": [], "remote": [], "skipped": None}
        out[n] = rec
        if not d.exists() or not (d / ".git").exists():
            rec["skipped"] = "not cloned"
            continue
        default = _default_branch(d, e.get("branch"))
        if not default:
            rec["skipped"] = "no default branch"
            continue
        current = _git(d, "branch", "--show-current").stdout.strip()

        merged = _git(
            d, "branch", "--merged", default, "--format=%(refname:short)", check=False
        ).stdout.split()
        for b in merged:
            if b in (default, current):
                continue
            res = _git(d, "branch", "-d", b, check=False)
            if res.returncode == 0:
                rec["local"].append(b)

        if remote:
            # Remote-tracking refs are only as fresh as the last fetch — and
            # single-branch clones don't even track the merged branches. An
            # explicit refspec fetches every head without touching git config.
            _git(d, "fetch", "origin", "+refs/heads/*:refs/remotes/origin/*", "--prune", check=False)
            ref = f"origin/{default}"
            if _git(d, "rev-parse", "--verify", ref, check=False).returncode == 0:
                rmerged = _git(
                    d, "branch", "-r", "--merged", ref, "--format=%(refname:short)", check=False
                ).stdout.split()
                for rb in rmerged:
                    b = rb.removeprefix("origin/")
                    if b in (default, "HEAD") or rb.endswith("/HEAD"):
                        continue
                    res = _git(d, "push", "origin", "--delete", b, check=False)
                    if res.returncode == 0:
                        rec["remote"].append(b)
        rec["skipped"] = rec["skipped"] or (
            None if (rec["local"] or rec["remote"]) else "nothing merged to prune"
        )
    return out


def sync(*names, repos_path=None):
    all_e = entries(repos_path)
    targets = list(names) if names else list(all_e.keys())
    src = Path.cwd()/"sources"
    src.mkdir(exist_ok=True)
    G = lambda *a: _sp.run(list(a), capture_output=True, text=True, check=True)
    for n in targets:
        e = all_e.get(n)
        if not e: print(f"!! {n}: not found in REPOS.md"); continue
        d = src/n
        try:
            if d.exists():
                cur_br = _sp.run(["git", "-C", str(d), "branch", "--show-current"], capture_output=True, text=True).stdout.strip()
                target_br = e.get("branch")
                if target_br and cur_br != target_br:
                    G("git", "-C", str(d), "checkout", target_br)
                G("git","-C",str(d),"pull","--ff-only")
                print(f"✓ {n}: pulled ({target_br or cur_br})")
            else:
                a = ["git","clone"] + (["-b",e["branch"]] if e.get("branch") else []) + [e["url"],str(d)]
                G(*a)
                print(f"✓ {n}: cloned {e['url']} -> sources/{n}")
        except _sp.CalledProcessError as ex:
            print(f"!! {n}: {(ex.stderr or ex.stdout or str(ex)).strip()}")
