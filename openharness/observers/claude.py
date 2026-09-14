import json
import os
import re
from pathlib import Path
from .base import SessionMeta, _tail_lines, _last_slash_command


def _decode_project_path(encoded: str) -> str:
    try:
        import urllib.parse
        return urllib.parse.unquote(encoded)
    except Exception:
        return encoded


class ClaudeObserver:
    agent = "claude"

    def _root(self) -> Path:
        return Path.home() / ".claude" / "projects"

    def sessions(self) -> list[SessionMeta]:
        root = self._root()
        if not root.exists():
            return []
        out: list[SessionMeta] = []
        for proj_dir in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True):
            if not proj_dir.is_dir():
                continue
            project_path = _decode_project_path(proj_dir.name)
            for jsonl in sorted(proj_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
                try:
                    st = jsonl.stat()
                except OSError:
                    continue
                lines = _tail_lines(jsonl, 50)
                cmd = _last_slash_command(lines)
                sid = f"claude:{proj_dir.name}:{jsonl.stem}"
                out.append(SessionMeta(
                    id=sid,
                    agent=self.agent,
                    project_path=project_path,
                    last_seen=st.st_mtime,
                    current_command=cmd,
                    file=str(jsonl),
                ))
                break
        return out

    def tail(self, session_id: str, since_line: int = 0) -> list[dict]:
        parts = session_id.split(":", 2)
        if len(parts) < 3:
            return []
        _, proj_enc, stem = parts
        path = self._root() / proj_enc / f"{stem}.jsonl"
        if not path.exists():
            return []
        lines = _tail_lines(path, 200)
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
