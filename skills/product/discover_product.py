"""Product-surface discovery: scan a repo and report what exists, what's stubbed, and where the shipping gaps are.

Stdlib only. Walks the repo (skipping .git/build/vendor dirs), detects the
stack from manifests, counts real vs placeholder implementation signals
(TODO/FIXME/NotImplementedError/placeholder markers), inventories routes,
endpoints, screens, tests, and existing specs. Emits a markdown Product
Surface Report the agent uses to frame innovative feature candidates —
it describes FACTS, not opinions; prioritization is the agent's job.
"""

import os
import re
from pathlib import Path

from openharness.skill import skill

_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    "vendor", ".chroma", ".next", ".nuget", "bin", "obj", "target",
    ".gradle", "Pods",
}
_SKIP_FILES = {"package-lock.json", "yarn.lock", "poetry.lock", "Cargo.lock"}
_MAX_FILE_BYTES = 512 * 1024

_PLACEHOLDER_RES = [
    re.compile(r"\bTODO\b"),
    re.compile(r"\bFIXME\b"),
    re.compile(r"\bXXX\b"),
    re.compile(r"NotImplementedError"),
    re.compile(r"\bplaceholder\b", re.I),
    re.compile(r"\bnot implemented\b", re.I),
    re.compile(r"\bcoming soon\b", re.I),
    re.compile(r"throw new NotImplementedException"),
]

_ROUTE_RES = [
    re.compile(r"@app\.(get|post|put|delete|patch)\("),
    re.compile(r"@(?:Get|Post|Put|Delete|Patch)Mapping\b"),
    re.compile(r"@(?:RestController|Controller)\b"),
    re.compile(r"\.(get|post|put|delete|patch)\(['\"](/[\w\-/{}:]*)"),
    re.compile(r"app\.(get|post|put|delete|patch)\(['\"]"),
    re.compile(r"@app\.route\(['\"]"),
    re.compile(r"router\.(get|post|put|delete|patch)\(['\"]"),
    re.compile(r"createBrowserRouter|<Route\b"),
]

_MANIFESTS = {
    "pyproject.toml": "Python", "requirements.txt": "Python", "setup.py": "Python",
    "package.json": "Node/JS", "pom.xml": "Java/Maven", "build.gradle": "Java/Gradle",
    "build.gradle.kts": "Kotlin/Gradle", "Cargo.toml": "Rust", "go.mod": "Go",
    "*.csproj": "C#/.NET", "composer.json": "PHP", "Gemfile": "Ruby",
    "Dockerfile": "Docker", "docker-compose.yml": "Docker Compose",
}

_CODE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".cs", ".go", ".rs",
    ".rb", ".php", ".swift", ".m", ".scala", ".groovy",
}
_TEST_MARKERS = ("test", "spec")


def _looks_like_clones_dir(path: Path) -> bool:
    """True if path/sources holds git checkouts (openharness clones dir)."""
    src = path / "sources"
    if not src.is_dir():
        return False
    try:
        children = [c for c in src.iterdir() if c.is_dir() and not c.name.startswith(".")]
    except OSError:
        return False
    return bool(children) and sum(1 for c in children if (c / ".git").exists()) >= 1


def _prune(dirnames: list[str], dirpath: str) -> list[str]:
    keep = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
    if "sources" in dirnames and _looks_like_clones_dir(Path(dirpath)):
        keep = [d for d in keep if d != "sources"]
    return keep


def _iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = _prune(dirnames, dirpath)
        for name in filenames:
            if name in _SKIP_FILES:
                continue
            yield Path(dirpath) / name


def _is_test_path(p: Path) -> bool:
    parts = {x.lower() for x in p.parts}
    return bool(parts & {"test", "tests", "__tests__", "spec", "specs"}) or any(
        m in p.stem.lower() for m in _TEST_MARKERS
    )


_EXT_LANG = {
    ".py": "Python", ".js": "Node/JS", ".jsx": "Node/JS", ".ts": "Node/JS",
    ".tsx": "Node/JS", ".mjs": "Node/JS", ".java": "Java", ".kt": "Kotlin",
    ".cs": "C#/.NET", ".go": "Go", ".rs": "Rust", ".rb": "Ruby",
    ".php": "PHP", ".swift": "Swift", ".scala": "Scala", ".groovy": "Groovy",
}


def _detect_stack(root: Path) -> list[str]:
    found = []
    ext_counts: dict[str, int] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = _prune(dirnames, dirpath)
        for name in filenames:
            for pattern, lang in _MANIFESTS.items():
                if "*" in pattern:
                    if name.endswith(pattern.lstrip("*.")) and lang not in found:
                        found.append(lang)
                elif name == pattern and lang not in found:
                    found.append(lang)
            lang = _EXT_LANG.get(Path(name).suffix.lower())
            if lang:
                ext_counts[lang] = ext_counts.get(lang, 0) + 1
    # manifests win; fall back to dominant source language(s)
    if not found and ext_counts:
        top = max(ext_counts.values())
        found = sorted(l for l, c in ext_counts.items() if c >= max(2, top // 10))
    return found[:4]


_CLASS_RE = re.compile(r"\bclass\s+([A-Z][A-Za-z0-9_]{2,})\b")


def _scan_signals(root: Path):
    code_files = test_files = 0
    placeholders = []
    routes = 0
    route_hits = []
    classes: dict[str, int] = {}
    dir_counts: dict[str, int] = {}
    for p in _iter_files(root):
        if p.suffix.lower() not in _CODE_EXTS and p.suffix not in (".cshtml", ".vue", ".svelte"):
            continue
        try:
            if p.stat().st_size > _MAX_FILE_BYTES:
                continue
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        rel = str(p.relative_to(root))
        if _is_test_path(p):
            test_files += 1
        else:
            code_files += 1
            parts = p.relative_to(root).parts[:-1]
            if parts:
                top = "/".join(parts[:2])
                dir_counts[top] = dir_counts.get(top, 0) + 1
            for name in _CLASS_RE.findall(text):
                classes[name] = classes.get(name, 0) + 1
        hits = sum(len(rx.findall(text)) for rx in _PLACEHOLDER_RES)
        if hits:
            placeholders.append((rel, hits))
        rhits = sum(len(rx.findall(text)) for rx in _ROUTE_RES)
        routes += rhits
        if rhits:
            route_hits.append((rel, rhits))
    return code_files, test_files, placeholders, routes, route_hits, classes, dir_counts


def _existing_specs(root: Path) -> list[str]:
    specs = root / "specs"
    if specs.is_dir():
        return sorted(d.name for d in specs.iterdir() if d.is_dir())
    return []


def _readme_excerpt(root: Path) -> str:
    for name in ("README.md", "README.rst", "README"):
        p = root / name
        if p.is_file():
            try:
                lines = [l.strip() for l in p.read_text(errors="ignore").splitlines() if l.strip()]
                return " / ".join(lines[:3])[:300]
            except OSError:
                pass
    return "(no README found)"


@skill
def discover_product(repo_path: str = ".") -> str:
    """Scan a repo and emit a Product Surface Report: stack, size, stubs, routes, tests, spec gaps.

    Deterministic facts only — the agent turns them into feature candidates.
    Reports: detected stack, code/test file counts, placeholder-marker hits
    (file + count), route/endpoint signal count, existing specs/ dirs, and a
    short README excerpt. Use before /ship-product framing or any feature work.

    Params:
      repo_path: Repository root to scan.
    """
    root = Path(repo_path).resolve()
    if not root.is_dir():
        return f"ERROR: {repo_path} is not a directory"

    stack = _detect_stack(root)
    (code_files, test_files, placeholders, routes, route_hits,
     classes, dir_counts) = _scan_signals(root)
    specs = _existing_specs(root)

    out = [f"# Product Surface Report — {root.name}", ""]
    out.append(f"**Path:** `{root}`")
    out.append(f"**Stack:** {', '.join(stack) if stack else '(none detected)'}")
    out.append(f"**README:** {_readme_excerpt(root)}")
    out.append("")
    out.append("## Size")
    out.append(f"- Source files (non-test): {code_files}")
    out.append(f"- Test files: {test_files}")
    ratio = (test_files / code_files) if code_files else 0
    out.append(f"- Test ratio: {ratio:.2f}")
    out.append("")
    out.append("## Implementation signals")
    out.append(f"- Route/endpoint markers: {routes}")
    if route_hits:
        top = sorted(route_hits, key=lambda x: -x[1])[:8]
        out.append("- Files with most route markers:")
        for rel, n in top:
            out.append(f"  - `{rel}` ({n})")
    total_ph = sum(n for _, n in placeholders)
    out.append(f"- Placeholder markers (TODO/FIXME/NotImplemented/placeholder/etc.): {total_ph} across {len(placeholders)} files")
    if placeholders:
        top = sorted(placeholders, key=lambda x: -x[1])[:10]
        out.append("- Top stub files:")
        for rel, n in top:
            out.append(f"  - `{rel}` ({n})")
    out.append("")
    out.append("## Domain vocabulary")
    out.append("Candidate terms for DOMAIN.md's ubiquitous language — verify")
    out.append("against the code before adopting; invented terms are worse")
    out.append("than borrowed ones.")
    if dir_counts:
        out.append("- Modules/areas by source-file count:")
        for rel, n in sorted(dir_counts.items(), key=lambda x: -x[1])[:8]:
            out.append(f"  - `{rel}/` ({n} files)")
    if classes:
        out.append("- PascalCase types by frequency:")
        for name, n in sorted(classes.items(), key=lambda x: -x[1])[:12]:
            out.append(f"  - `{name}` ({n})")
    if not dir_counts and not classes:
        out.append("- (no code signals — greenfield; derive terms from the")
        out.append("  problem statement and user interviews, not invention)")
    out.append("")
    out.append("## Spec state")
    out.append(f"- `specs/` features present: {', '.join(specs) if specs else '(none — greenfield for spec-driven work)'}")
    out.append("")
    out.append("## Agent next step")
    out.append("Turn the gaps above into 3-5 candidate feature themes, score them")
    out.append("(user value × feasibility × wow), pick ONE, then run")
    out.append("`spec_scaffold` to create `specs/<feature>/` — including")
    out.append("DOMAIN.md (glossary seeded from the vocabulary above) and")
    out.append("SPEC.md's `## Experience` section.")
    return "\n".join(out)
