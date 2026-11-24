"""SELF/blocks specs must name real code and stay linked from the MANIFEST.

Specs drift quietly: an interface gets renamed, an action is added, a block is
split out and never indexed (D001-D019 live in SELF/PRINCIPLES.md). These
tests make the drift fail instead of survive.
"""

from __future__ import annotations

import re
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

from openharness import frontmatter

ROOT = Path(__file__).resolve().parent.parent
BLOCKS = ROOT / "SELF" / "blocks"
MANIFEST_TEXT = (ROOT / "SELF" / "MANIFEST.md").read_text()

_HTTP = re.compile(r"^(GET|POST) (/api/\S+)$")
_DOTTED = re.compile(r"^([A-Za-z_]\w*)\.([A-Za-z_]\w*)$")
_ACTIONS = re.compile(r"^([a-z_]\w*) --action=([\w|]+)$")
_ROUTE = re.compile(r'@(?:app|router)\.(get|post)\("([^"]+)"\)')


@lru_cache(maxsize=1)
def _py_files() -> tuple[Path, ...]:
    skip = {"tests", "web", "sources", "node_modules", ".venv", ".git"}
    return tuple(
        p
        for p in ROOT.rglob("*.py")
        if not skip & set(p.parts) and not any(part.startswith(".") for part in p.relative_to(ROOT).parts)
    )


@lru_cache(maxsize=None)
def _files_named(stem: str) -> list[Path]:
    return [p for p in _py_files() if p.stem == stem]


@lru_cache(maxsize=None)
def _symbol_exists(mod: str, attr: str) -> bool:
    if mod == "Skill":
        text = (ROOT / "openharness" / "skill.py").read_text()
        return bool(re.search(rf"^class Skill\b[\s\S]*?^    def {attr}\(", text, re.M))
    for path in _files_named(mod):
        text = path.read_text()
        if re.search(rf"^(?:def|class) {attr}\b|^\s*{attr}\s*=", text, re.M):
            return True
    if attr == "invoke":
        return any(re.search(rf"^def {re.escape(mod)}\(", p.read_text(), re.M) for p in _py_files())
    return False


@lru_cache(maxsize=1)
def _tracked() -> set[str]:
    """Files git knows about; env-specific registries are gitignored on purpose."""
    out = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return set(out.stdout.splitlines()) if out.returncode == 0 else set()


@lru_cache(maxsize=1)
def _routes() -> frozenset[tuple[str, str]]:
    api = (ROOT / "openharness" / "serve_api.py").read_text()
    m = re.search(r'APIRouter\(prefix="([^"]*)"', api) or re.search(
        r'include_router\([^)]*prefix="([^"]*)"', (ROOT / "openharness" / "serve.py").read_text(), re.S
    )
    api_prefix = m.group(1) if m else ""
    out = set()
    for path in _files_named("serve") + _files_named("serve_api"):
        prefix = api_prefix if path.stem == "serve_api" else ""
        for method, route in _ROUTE.findall(path.read_text()):
            out.add((method.upper(), re.sub(r"\{[^}]+\}", "{}", prefix + route)))
    return frozenset(out)


@lru_cache(maxsize=None)
def _code_actions(mod: str) -> set[str] | None:
    for path in _files_named(mod):
        m = re.search(r"unknown action .*?\((?:[^)]*)\)", path.read_text(), re.S)
        if m:
            return {a for a in m.group(0).rsplit("(", 1)[1].rstrip(")").split("|") if a}
    return None


@pytest.fixture(scope="module")
def blocks() -> dict[str, dict]:
    out = {}
    for path in sorted(BLOCKS.glob("*.md")):
        meta = frontmatter.parse(path.read_text())
        meta["_path"] = path
        out[path.stem] = meta
    return out


def test_every_block_has_frontmatter_and_is_indexed(blocks):
    assert blocks, "no block specs found"
    for stem, meta in blocks.items():
        assert meta.get("name") == stem, f"{stem}: frontmatter name must match the file name"
        assert meta.get("type") == "block", f"{stem}: type must be 'block'"
        assert meta.get("location"), f"{stem}: location is required"
        assert meta.get("interfaces"), f"{stem}: interfaces is required"
        assert f"blocks/{stem}.md" in MANIFEST_TEXT, f"{stem}: not linked from SELF/MANIFEST.md"


def test_block_locations_exist(blocks):
    tracked = _tracked()
    for stem, meta in blocks.items():
        for loc in str(meta["location"]).split(","):
            loc = loc.strip().rstrip("/")
            if not loc or "*" in loc or "<" in loc:
                continue
            if Path(loc).suffix not in (".py", ".md"):
                continue  # runtime/data directories may not exist yet
            if tracked and loc not in tracked:
                continue  # gitignored local state (e.g. .openharness/REPOS.local.md)
            assert (ROOT / loc).exists(), f"{stem}: location not found: {loc}"


def test_http_interfaces_match_routes(blocks):
    routes = _routes()
    for stem, meta in blocks.items():
        for iface in meta["interfaces"]:
            m = _HTTP.match(iface)
            if not m:
                continue
            method, path = m.group(1), re.sub(r"\{[^}]+\}", "{}", m.group(2))
            assert (method, path) in routes, f"{stem}: {method} {path} is not a route"


def test_action_interfaces_match_code(blocks):
    for stem, meta in blocks.items():
        for iface in meta["interfaces"]:
            m = _ACTIONS.match(iface)
            if not m:
                continue
            code = _code_actions(m.group(1))
            if code is None:
                continue
            spec = set(m.group(2).split("|"))
            assert spec == code, (
                f"{stem}: actions for {m.group(1)} drifted — spec-only: {spec - code}, "
                f"code-only: {code - spec}"
            )


def test_dotted_interfaces_resolve(blocks):
    for stem, meta in blocks.items():
        for iface in meta["interfaces"]:
            m = _DOTTED.match(iface)
            if not m:
                continue
            mod, attr = m.groups()
            assert _symbol_exists(mod, attr), f"{stem}: {mod}.{attr} does not exist in code"
