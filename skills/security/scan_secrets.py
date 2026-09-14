import re
from pathlib import Path

from openharness.skill import skill

_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("Generic Secret", re.compile(r"""(?i)(?:api_key|apikey|secret|token|password|passwd)\s*[:=]\s*["'][^"'\s]{8,}["']""")),
    ("Private Key Block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----")),
]

_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build", ".chroma"}
_SKIP_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".tar", ".gz", ".pyc", ".so", ".dll"}


@skill
def scan_secrets(repo_path: str = ".") -> str:
    """Scan repository files for potential secrets and credentials.

    Detects AWS AKIA keys, generic api_key/secret/token assignments with
    quoted values, and private key block headers. Skips binary files,
    .git, node_modules, __pycache__, and vendor directories. Returns
    findings as file:line [pattern] lines or "No secrets found."

    Params:
      repo_path: Root directory to scan (default current dir).
    """
    root = Path(repo_path)
    if not root.exists():
        return f"Error: path does not exist: {repo_path}"
    findings: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in _SKIP_EXTS:
            continue
        try:
            lines = path.read_text(errors="ignore").splitlines()
        except Exception:
            continue
        for i, line in enumerate(lines, 1):
            for label, pattern in _PATTERNS:
                if pattern.search(line):
                    rel = path.relative_to(root) if path.is_relative_to(root) else path
                    findings.append(f"{rel}:{i} [{label}] {line.strip()[:200]}")
                    break
    if not findings:
        return "No secrets found."
    return "\n".join(findings)
