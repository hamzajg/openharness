import json
import re
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api")


def _loops_root() -> Path:
    return Path.cwd() / "sources"


def _read_loop_state(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    data.setdefault("waves", {})
    data.setdefault("gates", {})
    data.setdefault("events", [])
    return data


def _scan_loops(root: Path) -> list[dict]:
    """All specs/<feature>/LOOP.state.json under sources/<repo>/."""
    loops = []
    sources = root if root.name == "sources" else root / "sources"
    if not sources.is_dir():
        return loops
    for state_file in sorted(sources.glob("*/specs/*/LOOP.state.json")):
        data = _read_loop_state(state_file)
        if data is None:
            continue
        spec_dir = state_file.parent
        waves = data["waves"]
        gates = data["gates"]
        loops.append({
            "repo": spec_dir.parent.parent.name,
            "feature": spec_dir.name,
            "status": data.get("status", "running"),
            "iterations": int(data.get("iterations", 0)),
            "updated": data.get("updated", ""),
            "waves_total": len(waves),
            "waves_done": sum(1 for w in waves.values() if w.get("status") == "done"),
            "gates_total": len(gates),
            "gates_pending": sum(
                1 for g in gates.values() if g.get("status") == "pending"
            ),
            "last_event": (data["events"][-1] if data["events"] else ""),
        })
    loops.sort(key=lambda l: l["updated"], reverse=True)
    return loops


@router.get("/loops")
def get_loops():
    return {"loops": _scan_loops(_loops_root())}


@router.get("/loops/{repo}/{feature}")
def get_loop(repo: str, feature: str):
    if not repo or not feature or "/" in repo or "/" in feature or ".." in repo or ".." in feature:
        raise HTTPException(status_code=404, detail="loop not found")
    state_file = (
        _loops_root() / repo / "specs" / feature / "LOOP.state.json"
    )
    data = _read_loop_state(state_file)
    if data is None:
        raise HTTPException(status_code=404, detail="loop not found")
    return {"repo": repo, "feature": feature, **data}


@router.get("/sessions")
def get_sessions():
    from openharness.observers import all_sessions
    return all_sessions()


@router.get("/sessions/{sid}")
def get_session(sid: str):
    from openharness.observers import find_session
    obs, _ = find_session(sid)
    if obs is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"lines": obs.tail(sid)}


@router.get("/sessions/{sid}/metrics")
def get_session_metrics(sid: str):
    from openharness.observers import find_session
    from openharness import metrics as metrics_mod
    _, meta = find_session(sid)
    if meta is None:
        raise HTTPException(status_code=404, detail="session not found")
    return metrics_mod.session_metrics(meta.file)


@router.get("/metrics")
def get_metrics_summary():
    from openharness.observers import ALL_OBSERVERS
    from openharness import metrics as metrics_mod
    files = []
    for obs in ALL_OBSERVERS:
        try:
            files.extend(s.file for s in obs.sessions())
        except Exception:
            continue
    per_session = [metrics_mod.session_metrics(f) for f in files]
    return {
        "summary": metrics_mod.summarize(per_session),
        "sessions": per_session,
    }


@router.get("/skills")
def get_skills():
    from openharness import registry
    out = []
    for s in sorted(registry.all_skills(), key=lambda x: x.name):
        out.append({
            "name": s.name,
            "description": s.description,
            "params": s.params,
            "non_deterministic": s.non_deterministic,
        })
    return out


@router.post("/skills/{name}/run")
def run_skill(name: str, body: dict | None = None):
    from openharness import registry
    s = registry.get(name)
    if not s:
        raise HTTPException(status_code=404, detail=f"unknown skill: {name}")
    from openharness.skill import SkillError

    try:
        result = s.invoke(**(body or {}))
        return {"ok": True, "result": result if result is not None else ""}
    except SkillError as ex:
        # A refusal is the caller's problem to fix, not a server fault.
        return JSONResponse(status_code=400, content={"ok": False, "error": str(ex)})
    except Exception as ex:
        return JSONResponse(status_code=500, content={"ok": False, "error": str(ex)})


@router.get("/self")
def get_self(block: str | None = Query(default=None)):
    from pathlib import Path
    self_root = Path(__file__).resolve().parent.parent / "SELF"
    if block:
        p = self_root / "blocks" / f"{block}.md"
        if not p.exists():
            p = self_root / f"{block}.md"
        if not p.exists():
            raise HTTPException(status_code=404, detail="block not found")
        return {"text": p.read_text(), "block": block}
    return {"text": (self_root / "MANIFEST.md").read_text(), "block": "MANIFEST"}


@router.get("/env")
def get_env():
    from openharness import env as envmod
    from openharness.frontmatter import parse
    from pathlib import Path
    ep = Path.cwd() / ".openharness" / "ENV.md"
    return {
        "probe": envmod.probe(Path.cwd()),
        "env_declared": parse(ep.read_text()) if ep.exists() else {},
        "env_content": ep.read_text() if ep.exists() else "",
        "drift": envmod.drift(ep),
    }


@router.get("/knowledge")
def knowledge(q: str = Query(...), k: int = 5):
    from openharness.knowledge import rag
    return {"query": q, "chunks": rag.search(q, k=k)}


@router.get("/repos/status")
def repos_status(names: str | None = Query(default=None)):
    from openharness import repos
    ns = [n.strip() for n in names.split(",") if n.strip()] if names else []
    return repos.status(*ns)


@router.post("/repos/sync")
def repos_sync(body: dict | None = None):
    from openharness import repos
    names = (body or {}).get("names") or []
    repos.sync(*names)
    return {"ok": True}


@router.post("/repos/prune")
def repos_prune(body: dict | None = None):
    from openharness import repos
    body = body or {}
    names = body.get("names") or []
    remote = bool(body.get("remote", False))
    return repos.prune(*names, remote=remote)


# ---------------------------------------------------------------- evolution

_HARNESS_ROOT = Path(__file__).resolve().parent.parent
_DECISION_RE = re.compile(r"^###\s+(D\d+)\s*[—-]\s*(.+?)\s*$", re.M)
_CORE_FILES = [
    "__main__.py", "skill.py", "registry.py", "frontmatter.py",
    "env.py", "knowledge/rag.py",
]
_PLATFORM_FILES = ["repos.py", "metrics.py", "serve.py", "serve_api.py"]
# D003/D012 budgets, as revised by D016. Checked by tests/test_budgets.py.
CORE_BUDGET = 330
PLATFORM_BUDGET = 1100
_COMMIT_TYPES = {
    "feat": "feature", "fix": "fix", "evolve": "evolve",
    "docs": "docs", "chore": "chore", "refactor": "refactor",
}


def _parse_decisions(path: Path) -> list[dict]:
    """### D00N — Title / Rule: … / Because: … blocks from PRINCIPLES.md."""
    try:
        text = path.read_text()
    except OSError:
        return []
    matches = list(_DECISION_RE.finditer(text))
    out = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.end():end]
        rule_m = re.search(r"^Rule:\s*(.+?)(?=^Because:|^###|\Z)", block, re.M | re.S)
        because_m = re.search(r"^Because:\s*(.+?)(?=^###|\Z)", block, re.M | re.S)
        out.append({
            "id": m.group(1),
            "title": m.group(2).strip(),
            "rule": " ".join(rule_m.group(1).split()) if rule_m else "",
            "because": " ".join(because_m.group(1).split()) if because_m else "",
        })
    return out


def _git_log(root: Path, limit: int = 200) -> list[dict]:
    """Harness self-history: commits on this repo, classified by prefix."""
    try:
        res = subprocess.run(
            ["git", "-C", str(root), "log", f"-{limit}",
             "--format=%h%x1f%aI%x1f%s"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if res.returncode != 0:
        return []
    commits = []
    for line in res.stdout.splitlines():
        parts = line.split("\x1f")
        if len(parts) != 3:
            continue
        sha, date, subject = parts
        prefix = subject.split(":", 1)[0].split("(", 1)[0].strip().lower()
        commits.append({
            "sha": sha,
            "date": date,
            "subject": subject,
            "type": _COMMIT_TYPES.get(prefix, "other"),
        })
    return commits


def _loc(path: Path) -> int:
    try:
        return sum(1 for _ in path.open(errors="ignore"))
    except OSError:
        return 0


def _harness_stats(root: Path) -> dict:
    pkg = root / "openharness"
    core_loc = sum(_loc(pkg / f) for f in _CORE_FILES if (pkg / f).is_file())
    platform_loc = sum(_loc(pkg / f) for f in _PLATFORM_FILES if (pkg / f).is_file())
    platform_loc += sum(_loc(p) for p in (pkg / "observers").glob("*.py"))
    skills_loc = sum(
        _loc(p) for p in (pkg.parent / "skills").rglob("*.py")
        if "__pycache__" not in p.parts
    )
    tests = 0
    for p in (root / "tests").glob("test_*.py"):
        try:
            tests += sum(1 for ln in p.read_text(errors="ignore").splitlines()
                         if ln.lstrip().startswith("def test_"))
        except OSError:
            pass
    try:
        from openharness import registry
        n_skills = len(registry.all_skills())
    except Exception:
        n_skills = len(list((root / "skills").rglob("*.py")))
    return {
        "core_loc": core_loc, "core_budget": CORE_BUDGET,
        "platform_loc": platform_loc, "platform_budget": PLATFORM_BUDGET,
        "skills_loc": skills_loc,
        "tests": tests,
        "skills": n_skills,
        "blocks": len(list((root / "SELF" / "blocks").glob("*.md"))),
    }


@router.get("/evolution")
def get_evolution():
    decisions = _parse_decisions(_HARNESS_ROOT / "SELF" / "PRINCIPLES.md")
    return {
        "decisions": decisions,
        "commits": _git_log(_HARNESS_ROOT),
        "stats": _harness_stats(_HARNESS_ROOT),
    }
