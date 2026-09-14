import asyncio
import json
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .serve_api import router

app = FastAPI(title="OpenHarness", docs_url="/api/docs")
app.include_router(router)

_WEB_DIST = Path(__file__).resolve().parent / "web" / "dist"


@app.get("/api/stream/{sid}")
async def stream_session(sid: str, request: Request):
    from openharness.observers import find_session

    obs, meta = find_session(sid)
    if obs is None:
        return JSONResponse(status_code=404, content={"error": "session not found"})

    idx = [len(obs.tail(sid))]

    async def gen():
        while True:
            if await request.is_disconnected():
                break
            tail = obs.tail(sid)
            new_lines = tail[idx[0]:]
            if new_lines:
                idx[0] = len(tail)
                for ln in new_lines:
                    payload = json.dumps(ln, default=str).replace("\n", " ")
                    yield f"event: line\ndata: {payload}\n\n"
            else:
                yield f": ping {time.time()}\n\n"
            await asyncio.sleep(1.0)

    return StreamingResponse(gen(), media_type="text/event-stream",
                           headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})


def _spa_fallback(path_str: str) -> Response:
    if not _WEB_DIST.exists():
        return JSONResponse(status_code=404, content={
            "hint": "UI not built. Run: cd openharness/web && npm ci && npm run build"
        })
    target = _WEB_DIST / path_str
    if target.exists() and target.is_file():
        return FileResponse(str(target))
    return FileResponse(str(_WEB_DIST / "index.html"))


if _WEB_DIST.exists():
    assets = _WEB_DIST / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")


@app.get("/{path:path}")
def spa_catchall(path: str, request: Request):
    if path.startswith("api/") or path.startswith("docs") or path.startswith("openapi") or path.startswith("redoc"):
        return JSONResponse(status_code=404, content={"error": "not found"})
    return _spa_fallback(path or "index.html")


@app.get("/")
def root():
    return _spa_fallback("index.html")
