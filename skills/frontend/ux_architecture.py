import re
from pathlib import Path

from openharness.skill import skill

# --------------------------------------------------------------------------- #
# UX / UI architecture + decision-making.
#
# Scores a frontend on the five things a design system must get right —
# tokens, primitives, theming, accessibility plumbing and recorded decisions —
# then reports the gaps with a domain-specific inspiration menu. It never
# grades taste; it makes the architecture inspectable and the next decision
# explicit. Read-only.
# --------------------------------------------------------------------------- #

SKIP_DIRS = {".git", "node_modules", "dist", "build", "coverage", ".vite", "__pycache__"}
STYLE_EXT = {".css", ".scss", ".sass", ".less"}
CODE_EXT = {".tsx", ".ts", ".jsx", ".js"}
SURFACE_RE = re.compile(r"^\s*[-*]\s*Navigation/overlay:\s*(\S+)", re.I | re.M)
PATTERN_RE = re.compile(r"^\s*[-*]\s*UI pattern:\s*(\S+)", re.I | re.M)
STANDARDS = (
    "material", "apple hig", "human interface", "nn/g", "nielsen", "polaris",
    "bootstrap", "fluent", "carbon", "ant design", "tailwind",
)
PRIMITIVES = ("button", "input", "card", "badge", "dialog", "drawer", "select", "tooltip", "table", "tabs")


def _find_web(root: Path, web_dir: str) -> Path | None:
    if web_dir:
        p = Path(web_dir)
        return p if p.exists() else None
    for cand in (root / "web", root / "frontend", root / "client", root):
        if (cand / "package.json").exists():
            return cand
    return None


def _iter(web: Path, exts):
    for p in web.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts and not any(x in p.parts for x in SKIP_DIRS):
            yield p


def _docs(root: Path) -> str:
    parts = []
    for base in (root / "docs", root / "specs", root / "ADR", root / "adr"):
        if not base.exists():
            continue
        for p in base.rglob("*.md"):
            try:
                parts.append(p.read_text(errors="ignore").lower())
            except Exception:
                continue
    return "\n".join(parts)


@skill
def ux_architecture(web_dir: str = "", repo_path: str = ".", specs_dir: str = "") -> str:
    """Score a frontend's UX architecture and surface the next design decision.

    Inspects the design system on five axes — token source, primitive
    components, theming, accessibility plumbing, and recorded decisions — then
    checks `specs/*/SPEC.md` for one primary navigation surface per journey.
    Reports `[ok]·[partial]·[gap]` per axis, an overall maturity level, a
    domain-specific inspiration menu for the gaps, and cross-spec surface
    consistency. Deterministic, read-only, advisory.

    Params:
      web_dir: Web project directory. Empty = auto-detect web/frontend/client.
      repo_path: Repository root (default current dir).
      specs_dir: Specs directory to audit. Empty = <repo_path>/specs.
    """
    root = Path(repo_path)
    web = _find_web(root, web_dir)
    if web is None:
        return f"No web project found at {web_dir or root}"

    css = "\n".join(p.read_text(errors="ignore") for p in _iter(web, STYLE_EXT))
    code_files = list(_iter(web, CODE_EXT))
    code = "\n".join(p.read_text(errors="ignore") for p in code_files)
    low = code.lower()
    out: list[str] = [f"Project: {web}", ""]
    scores: list[int] = []

    def axis(name: str, earned: int, total: int, detail: str):
        scores.append(round(earned / total * 100))
        state = "ok" if earned == total else "partial" if earned else "gap"
        out.append(f"[{state}] {name} — {earned}/{total}: {detail}")

    # 1. Tokens ---------------------------------------------------------- #
    token_blocks = len(re.findall(r"@theme\s*\{|:root\s*\{", css))
    token_count = len(re.findall(r"--[a-z0-9-]+\s*:", css))
    has_color_tokens = bool(re.search(r"--[a-z0-9-]*(?:color|ink|surface|canvas|accent|danger|success|warning|info|text)[a-z0-9-]*\s*:", css))
    has_scale_tokens = bool(re.search(r"--[a-z0-9-]*(?:space|radius|font|shadow|z-|transition)[a-z0-9-]*\s*:", css))
    t = 0
    t += 1 if token_blocks else 0
    t += 1 if has_color_tokens else 0
    t += 1 if has_scale_tokens else 0
    axis("Tokens", t, 3,
         f"{token_blocks} token block(s), {token_count} custom properties — semantic colour"
         + (" + spacing/radius/type scale" if t == 3 else "; add scale tokens for spacing, radius and type")
         + ("" if token_blocks <= 1 else " (more than one block risks drift)"))

    # 2. Primitives ------------------------------------------------------ #
    ui_dirs = [p for p in web.rglob("*") if p.is_dir() and p.name in ("ui", "components", "shell") and "node_modules" not in p.parts]
    exported = {name for name in PRIMITIVES if re.search(rf"\b{name}\b", low)}
    comp_dir = next((p for p in ui_dirs if p.name in ("ui", "shell")), None) or next(iter(ui_dirs), None)
    prim_dir = comp_dir or (web / "src" / "components")
    files = len(list(_iter(prim_dir, {".tsx", ".jsx"}))) if prim_dir.exists() else 0
    p = 0
    p += 1 if comp_dir else 0
    p += 1 if files >= 3 else 0
    p += 1 if len(exported) >= 5 else 0
    axis("Primitives", p, 3,
         f"{files} component file(s) in {prim_dir.relative_to(web) if prim_dir.exists() else '—'}; "
         f"found {len(exported)}/{len(PRIMITIVES)} core primitives ({', '.join(sorted(exported)) or 'none'})")

    # 3. Theming --------------------------------------------------------- #
    theme_docs = _docs(root)
    th = 0
    th += 1 if "color-scheme" in css else 0
    th += 1 if not re.search(r"#(?:fff|ffffff|000|000000)\b", css) else 0  # token-based backgrounds
    th += 1 if (
        re.search(r"prefers-color-scheme|\.dark\b|darkMode|data-theme", css + code)
        or "single theme" in theme_docs
        or "light-only" in theme_docs
    ) else 0
    axis("Theming", th, 3,
         "explicit `color-scheme`, token-based backgrounds"
         + (", dark/light mechanism or recorded single-theme decision" if th >= 3 else ", no dark/light mechanism and no recorded single-theme decision")
         + ("; hardcoded pure black/white bypasses tokens" if th == 1 else ""))

    # 4. Accessibility plumbing ----------------------------------------- #
    a = 0
    a += 1 if ":focus-visible" in css or "focus-visible:" in code else 0
    a += 1 if "prefers-reduced-motion" in css else 0
    a += 1 if re.search(r"<main\b|role=\"main\"|aria-live|aria-labelledby|aria-describedby", code) else 0
    a += 1 if re.search(r"skip.*main|href=\"#main\"|SkipLink", low) else 0
    axis("A11y plumbing", a, 4,
         "focus-visible, reduced-motion, live/landmark wiring and a skip link are the four keystones; "
         + ("all present" if a == 4 else f"{4 - a} missing"))

    # 5. Recorded decisions --------------------------------------------- #
    docs = _docs(root)
    d = 0
    d += 1 if ("design system" in docs or "design-system" in docs) else 0
    d += 1 if "navigation/overlay" in docs else 0
    d += 1 if ("ui pattern" in docs or "frontend-page-guide" in docs) else 0
    d += 1 if any(s in docs for s in STANDARDS) else 0
    axis("Recorded decisions", d, 4,
         "design-system doc, navigation-surface ADR, scan-pattern choice, and a cited community standard"
         + ("" if d == 4 else f" — {4 - d} missing"))

    # --- cross-spec surface consistency --------------------------------- #
    specs = Path(specs_dir) if specs_dir else root / "specs"
    surfaces: dict[str, list[str]] = {}
    surfaces_missing: list[str] = []
    if specs.exists():
        for spec in sorted(specs.glob("*/SPEC.md")):
            text = spec.read_text(errors="ignore")
            m = SURFACE_RE.search(text)
            if not m:
                surfaces_missing.append(spec.parent.name)
                continue
            surfaces.setdefault(m.group(1).lower(), []).append(spec.parent.name)
    out.append("")
    if surfaces:
        out.append("Navigation surfaces across specs:")
        for surface, names in sorted(surfaces.items()):
            out.append(f"  - {surface}: {', '.join(names)}")
    if surfaces_missing:
        out.append(f"  - missing Navigation/overlay: {', '.join(surfaces_missing)}")
    conflicts = [n for n in ("full-page", "side-pane", "modal", "inline") if len(surfaces.get(n, [])) > 4]
    if conflicts:
        out.append(f"  - {', '.join(conflicts)} dominates; confirm each choice follows the decision order rather than habit")

    total = sum(scores) // len(scores)
    level = (
        "foundation" if total < 40 else
        "emerging" if total < 60 else
        "componentised" if total < 80 else
        "systemised"
    )

    # --- inspiration menu ---------------------------------------------- #
    menu: list[str] = []
    if t < 3:
        menu.append("Material 3 token model — role-based colour, elevation and type scales as CSS variables")
    if p < 3:
        menu.append("Shopify Polaris component anatomy — one primitive per concern with documented states")
    if th < 3:
        menu.append("Apple HIG appearance — explicit light/dark and semantic (not literal) colour names")
    if a < 4:
        menu.append("WAI-ARIA Authoring Practices — dialog focus trap/return, skip link, live regions")
    if d < 4:
        menu.append("Nielsen Norman Group — record the journey, error recovery and surface choice, not screenshots")
    if not menu:
        menu.append("System is coherent — next step is a contribution rule: new token/primitive/ADR or no new style")

    out.append("")
    out.append(f"Maturity: {total}/100 — {level}")
    out.append("Inspiration menu (deep domain sources for the gaps):")
    out.extend(f"  - {m}" for m in menu)
    return "\n".join(out)
