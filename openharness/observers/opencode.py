import json
import os
from pathlib import Path
from .base import SessionMeta, _tail_lines, _last_slash_command


class OpenCodeObserver:
    agent = "opencode"

    def _root(self) -> Path:
        env_dir = os.environ.get("OH_OPENCODE_DIR")
        if env_dir:
            return Path(env_dir)
        xdg = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
        return Path(xdg) / "opencode" / "sessions"

    def sessions(self) -> list[SessionMeta]:
        root = self._root()
        if not root.exists():
            return []
        out: list[SessionMeta] = []
        candidates: list[Path] = []
        for p in root.rglob("*.jsonl"):
            try:
                if p.stat().st_size > 0:
                    candidates.append(p)
            except OSError:
                pass
        for p in root.rglob("*.json"):
            try:
                if p.stat().st_size > 0:
                    candidates.append(p)
            except OSError:
                pass
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        seen_projects: set[str] = set()
        for f in candidates:
            try:
                st = f.stat()
            except OSError:
                continue
            project_path = str(f.parent.parent if (f.parent.name in ("logs", "transcripts")) else f.parent)
            if project_path in seen_projects:
                continue
            seen_projects.add(project_path)
            lines = _tail_lines(f, 50)
            cmd = _last_slash_command(lines)
            sid = f"opencode:{f.parent.name}:{f.stem}"
            out.append(SessionMeta(
                id=sid,
                agent=self.agent,
                project_path=project_path,
                last_seen=st.st_mtime,
                current_command=cmd,
                file=str(f),
            ))
        return out

    def tail(self, session_id: str, since_line: int = 0) -> list[dict]:
        parts = session_id.split(":", 2)
        if len(parts) < 3:
            return []
        _, parent, stem = parts
        root = self._root()
        found: Path | None = None
        for f in root.rglob(f"**/{parent}/{stem}.*"):
            if f.suffix in (".jsonl", ".json"):
                found = f
                break
        if found is None or not found.exists():
            return []
        lines = _tail_lines(found, 200)
        result: list[dict] = []
        for i, line in enumerate(lines):
            if i < since_line:
                continue
            if not line.strip():
                continue
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                result.append({"_raw": line})
        return result
