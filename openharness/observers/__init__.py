from pathlib import Path
from typing import Iterator

from .base import SessionMeta
from .claude import ClaudeObserver
from .opencode import OpenCodeObserver

ALL_OBSERVERS = [ClaudeObserver(), OpenCodeObserver()]


def _repo_of(path_str: str, sources_root: Path | None = None) -> str:
    if sources_root is None:
        sources_root = Path.cwd() / "sources"
    try:
        p = Path(path_str).resolve()
        rel = p.relative_to(sources_root.resolve())
        return rel.parts[0] if rel.parts else "external"
    except (ValueError, IndexError):
        return "external"


def all_sessions(sources_root: Path | None = None) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for obs in ALL_OBSERVERS:
        try:
            for s in obs.sessions():
                repo = _repo_of(s.project_path, sources_root)
                grouped.setdefault(repo, []).append(s.as_dict())
        except Exception:
            continue
    for repo in grouped:
        grouped[repo].sort(key=lambda d: d["last_seen"], reverse=True)
    return grouped


def find_session(session_id: str):
    for obs in ALL_OBSERVERS:
        try:
            for s in obs.sessions():
                if s.id == session_id:
                    return obs, s
        except Exception:
            continue
    return None, None
