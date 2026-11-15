import json
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
    try:
        result = s.invoke(**(body or {}))
        return {"ok": True, "result": result if result is not None else ""}
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
