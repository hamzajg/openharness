import ast
from collections import defaultdict
from pathlib import Path

from openharness.skill import skill

_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build", "vendor", ".chroma", "tests"}


def _py_modules(root: Path) -> list[Path]:
    out = []
    for path in root.rglob("*.py"):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        out.append(path)
    return out


def _top_level_package(path: Path, root: Path) -> str:
    try:
        rel = path.relative_to(root).with_suffix("")
    except ValueError:
        return path.stem
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts:
        return root.stem or "(root)"
    return parts[0]


def _imports_from(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(errors="ignore"))
    except SyntaxError:
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                found.add(node.module.split(".")[0])
    return found


@skill
def strangler_plan(repo_path: str = ".", target: str = "") -> str:
    """Extract module list and top-level import graph for strangler-fig planning.

    Walks .py files with stdlib AST only (no third-party deps). Reports
    each top-level package, its internal imports (to siblings inside
    the repo), and its external imports (stdlib + third-party). The
    agent uses this to identify seams, migration order, and rollback
    points.

    Params:
      repo_path: Repository root.
      target: Optional target module name to focus analysis on.
    """
    root = Path(repo_path)
    if not root.exists():
        return f"Error: path does not exist: {repo_path}"

    modules = _py_modules(root)
    packages: dict[str, int] = defaultdict(int)
    internal_edges: dict[str, set[str]] = defaultdict(set)
    external_imports: dict[str, set[str]] = defaultdict(set)

    package_names: set[str] = set()
    for m in modules:
        pkg = _top_level_package(m, root)
        packages[pkg] += 1
        package_names.add(pkg)

    for m in modules:
        src = _top_level_package(m, root)
        if target and target != src:
            continue
        for imp in _imports_from(m):
            if imp in package_names and imp != src:
                internal_edges[src].add(imp)
            else:
                external_imports[src].add(imp)

    out = [f"# Strangler-fig input: {root.resolve()}"]
    out.append(f"Top-level packages: {len(package_names)}")
    out.append("")
    out.append("## Packages (file count)")
    for pkg, n in sorted(packages.items(), key=lambda x: -x[1]):
        out.append(f"- {pkg}: {n} .py files")
    out.append("")
    out.append("## Internal import graph (package → siblings it imports)")
    for pkg in sorted(internal_edges):
        out.append(f"- {pkg} → {', '.join(sorted(internal_edges[pkg]))}")
    for pkg in sorted(package_names - set(internal_edges)):
        out.append(f"- {pkg} → (no internal imports)")
    out.append("")
    out.append("## External imports per package (top 8)")
    for pkg in sorted(external_imports):
        top = sorted(external_imports[pkg])[:8]
        out.append(f"- {pkg}: {', '.join(top)}")
    if target:
        out.append("")
        out.append(f"(Filtered to package: {target})")
    return "\n".join(out)
