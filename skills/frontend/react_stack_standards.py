import json
import re
from pathlib import Path

from openharness.skill import skill

# --------------------------------------------------------------------------- #
# React + Vite + TypeScript + Jest community standards.
#
# Deterministic config/code audit of a web project. It checks the stack the
# project claims (React 18+, Vite, strict TS, Jest/Vitest + Testing Library)
# and a short list of well-established code smells (index keys, unsafe HTML,
# non-submit buttons, missing rel on _blank, untyped any). Advisory only.
# --------------------------------------------------------------------------- #

SKIP_DIRS = {".git", "node_modules", "dist", "build", "coverage", ".vite", "__pycache__"}
CODE_EXT = {".ts", ".tsx", ".js", ".jsx"}
BUTTON_RE = re.compile(r"<button\b[^>]*>", re.I | re.S)
RAW_PALETTE = re.compile(
    r"\b(?:bg|text|border|ring|from|to|via)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b"
)


def _find_web(root: Path, web_dir: str) -> Path | None:
    if web_dir:
        p = Path(web_dir)
        return p if (p / "package.json").exists() else None
    for cand in (root / "web", root / "frontend", root / "client", root):
        if (cand / "package.json").exists():
            return cand
    return None


def _strip_jsonc(text: str) -> str:
    text = re.sub(r"//[^\n]*", "", text)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r",\s*([}\]])", r"\1", text)
    return text


def _tsconfig(web: Path) -> dict:
    for name in ("tsconfig.json", "tsconfig.app.json", "tsconfig.build.json"):
        p = web / name
        if not p.exists():
            continue
        try:
            return json.loads(_strip_jsonc(p.read_text(errors="ignore")))
        except Exception:
            continue
    return {}


def _iter_code(web: Path):
    for p in web.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in CODE_EXT:
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


@skill
def react_stack_standards(web_dir: str = "", repo_path: str = ".") -> str:
    """Audit a React + Vite + TypeScript + Jest project against community standards.

    Checks the declared stack (React 18, Vite, strict TypeScript), the test
    runner and Testing Library setup, and scans source for common React
    smells: array-index keys, `dangerouslySetInnerHTML`, `<button>` without
    `type`, `target="_blank"` without rel=noopener, and untyped `any`.
    Read-only and advisory; prints counts with example file:line refs.

    Params:
      web_dir: Web project directory (contains package.json). Empty = auto-detect web/.
      repo_path: Repository root used when web_dir is empty (default current dir).
    """
    root = Path(repo_path)
    web = _find_web(root, web_dir)
    if web is None:
        return f"No package.json found at {web_dir or root} (looked for web/, frontend/, client/, root)"

    pkg = json.loads((web / "package.json").read_text(errors="ignore"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    scripts = pkg.get("scripts", {})
    out: list[str] = [f"Project: {web}"]
    errors = warns = 0

    def note(level: str, msg: str):
        nonlocal errors, warns
        out.append(f"[{level}] {msg}")
        if level == "error":
            errors += 1
        elif level == "warn":
            warns += 1

    # --- stack ---------------------------------------------------------- #
    if "react" not in deps:
        note("error", "React is not a dependency — this is not a React project")
    if "react-dom" not in deps:
        note("error", "react-dom is missing")
    if not any(k in deps for k in ("vite", "@vitejs/plugin-react", "@vitejs/plugin-react-swc")):
        note("warn", "Vite is not declared — the requested stack is React + Vite")
    if "typescript" not in deps and not list(web.glob("tsconfig*.json")):
        note("error", "TypeScript is not configured (no typescript dep, no tsconfig)")

    ts = _tsconfig(web)
    strict = bool(ts.get("compilerOptions", {}).get("strict"))
    if not strict:
        note("error", "tsconfig `strict` is not true — community baseline for TS + React")
    if not ts.get("compilerOptions", {}).get("jsx"):
        note("warn", "tsconfig does not set `jsx` (react-jsx recommended)")
    if ts and not ts.get("include"):
        note("warn", "tsconfig has no `include` — types may leak across the repo")

    # --- tests ---------------------------------------------------------- #
    test_script = str(scripts.get("test", ""))
    has_jest = "jest" in deps
    has_vitest = "vitest" in deps
    if not test_script:
        note("error", "package.json has no `test` script — the stack requires a test runner")
    elif not any(k in test_script for k in ("jest", "vitest")):
        note("warn", f"`test` script is `{test_script[:60]}` — expected Jest or Vitest")
    if not (has_jest or has_vitest) and test_script:
        note("error", "no Jest/Vitest dependency found")
    if has_jest and not any((web / n).exists() for n in ("jest.config.js", "jest.config.ts", "jest.config.mjs", "jest.config.cjs")):
        if "jest" not in json.dumps(pkg.get("jest", {})):
            note("warn", "Jest declared but no jest.config.* and no package.json `jest` block")
    if (has_jest or has_vitest) and "@testing-library/react" not in deps:
        note("warn", "no @testing-library/react — component tests will assert implementation, not behaviour")
    if "@testing-library/jest-dom" not in deps and (has_jest or has_vitest):
        note("warn", "no @testing-library/jest-dom — prefer accessible matchers (toBeVisible, toHaveFocus)")
    if has_jest and has_vitest:
        note("warn", "both Jest and Vitest are dependencies — pick one runner")

    # --- code smells ---------------------------------------------------- #
    index_keys: list[str] = []
    danger: list[str] = []
    bad_buttons: list[str] = []
    blank_links: list[str] = []
    raw_any = 0
    files = 0
    for p in _iter_code(web):
        files += 1
        rel = p.relative_to(web)
        try:
            text = p.read_text(errors="ignore")
        except Exception:
            continue
        for m in re.finditer(r"key=\{\s*(i|idx|index)\s*\}", text):
            index_keys.append(f"{rel}:{text[:m.start()].count(chr(10)) + 1}")
        if "dangerouslySetInnerHTML" in text:
            danger.append(str(rel))
        for m in BUTTON_RE.finditer(text):
            tag = m.group(0)
            if not re.search(r"\btype=", tag):
                bad_buttons.append(f"{rel}:{text[:m.start()].count(chr(10)) + 1}")
        for m in re.finditer(r"target=\"_blank\"[^>]*>", text):
            if "noopener" not in m.group(0) and "noreferrer" not in m.group(0):
                blank_links.append(f"{rel}:{text[:m.start()].count(chr(10)) + 1}")
        raw_any += len(re.findall(r":\s*any\b|<any>|as any", text))

    def ex(items: list[str]) -> str:
        return ", ".join(items[:5]) + (f" (+{len(items) - 5})" if len(items) > 5 else "")

    if index_keys:
        note("warn", f"{len(index_keys)} array-index key(s) — use a stable id: {ex(index_keys)}")
    if danger:
        note("warn", f"dangerouslySetInnerHTML in {len(danger)} file(s) — sanitize or avoid: {ex(danger)}")
    if bad_buttons:
        note("warn", f"{len(bad_buttons)} <button> without explicit type — inside a form it submits by default: {ex(bad_buttons)}")
    if blank_links:
        note("error", f"{len(blank_links)} target=_blank without rel=noopener/noreferrer: {ex(blank_links)}")
    if raw_any:
        note("warn", f"{raw_any} untyped `any` occurrence(s) — narrow types instead")
    if RAW_PALETTE.search("\n".join(p.read_text(errors="ignore") for p in _iter_code(web))):
        note("warn", "raw Tailwind palette classes used — prefer semantic design tokens")

    if not any((web / n).exists() for n in ("eslint.config.js", "eslint.config.mjs", ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.cjs")):
        note("warn", "no ESLint config — React hooks/exhaustive-deps rules are the community baseline")

    out.append("")
    out.append(f"Scanned {files} source file(s).")
    out.append(f"React stack: {errors} error(s) · {warns} warning(s)")
    out.append("Verdict: PASS" if not errors else "Verdict: CONCERNS — fix errors before calling the UI done")
    return "\n".join(out)
