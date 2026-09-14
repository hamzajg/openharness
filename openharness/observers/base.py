from dataclasses import dataclass, asdict
from typing import Protocol, Iterator
from pathlib import Path
import time


@dataclass
class SessionMeta:
    id: str
    agent: str
    project_path: str
    last_seen: float
    current_command: str
    file: str

    def is_active(self, minutes: int = 15) -> bool:
        return (time.time() - self.last_seen) < (minutes * 60)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["active"] = self.is_active()
        return d


class SessionObserver(Protocol):
    def sessions(self) -> list[SessionMeta]: ...
    def tail(self, session_id: str, since_line: int = 0) -> list[dict]: ...


def _tail_lines(path: Path, n: int = 200) -> list[str]:
    try:
        text = path.read_text(errors="ignore")
    except OSError:
        return []
    lines = text.splitlines()
    return lines[-n:] if n > 0 else lines


def _last_slash_command(lines: list[str]) -> str:
    for line in reversed(lines):
        s = line.strip()
        if s.startswith(("!", "/")) and len(s) > 1:
            return s[:120]
    return ""
