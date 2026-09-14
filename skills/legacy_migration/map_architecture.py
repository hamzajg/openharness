from collections import Counter
from pathlib import Path

from openharness.skill import skill

_EXTS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript/JSX",
    ".ts": "TypeScript",
    ".tsx": "TypeScript/TSX",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".h": "Header",
    ".md": "Markdown",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".sh": "Shell",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
}

_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build", "vendor", ".chroma"}


@skill
def map_architecture(repo_path: str = ".") -> str:
    """Produce a deterministic repo structure summary for architecture analysis.

    Walks the repo, counts files by extension/language, lists the 10
    largest source files, top-level directory inventory, and per-dir
    file counts. Returned as structured text the agent uses to produce
    an architecture map.

    Params:
      repo_path: Repository root to walk.
    """
    root = Path(repo_path)
    if not root.exists():
        return f"Error: path does not exist: {repo_path}"

    ext_counts: Counter[str] = Counter()
    lang_counts: Counter[str] = Counter()
    file_sizes: list[tuple[int, Path]] = []
    dir_counts: Counter[str] = Counter()

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        ext = path.suffix.lower()
        ext_counts[ext] += 1
        lang = _EXTS.get(ext, "Other")
        lang_counts[lang] += 1
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        file_sizes.append((size, path))
        try:
            parent = path.relative_to(root).parts[0]
        except (ValueError, IndexError):
            parent = "."
        dir_counts[parent] += 1

    total_files = sum(ext_counts.values())
    out = [f"# Architecture Prep: {root.resolve()}"]
    out.append(f"Total files (excluding vendor dirs): {total_files}")
    out.append("")
    out.append("## Languages (by file count)")
    for lang, n in lang_counts.most_common():
        out.append(f"- {lang}: {n}")
    out.append("")
    out.append("## Top-level directories")
    for d, n in sorted(dir_counts.items(), key=lambda x: -x[1]):
        out.append(f"- {d}/: {n} files")
    out.append("")
    out.append("## 10 largest files")
    for size, path in sorted(file_sizes, reverse=True)[:10]:
        try:
            rel = path.relative_to(root)
        except ValueError:
            rel = path
        out.append(f"- {size:>10d} B  {rel}")
    out.append("")
    out.append("## Extensions")
    for ext, n in ext_counts.most_common(15):
        out.append(f"- {ext or '(no ext)'}: {n}")
    return "\n".join(out)
