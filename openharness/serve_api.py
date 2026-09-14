from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api")


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
