import json
import re
from pathlib import Path

from openharness.skill import skill

# --------------------------------------------------------------------------- #
# CSS framework + design-token standards.
#
# Tailwind (v3/v4), Bootstrap and Material are all legitimate; mixing them is
# not. The audit checks which system is in use, whether the tokens are a
# single source of truth, WCAG 2.1 AA contrast for text tokens, hardcoded
# colours that bypass tokens, and the motion/focus/colour-scheme baseline.
# --------------------------------------------------------------------------- #

SKIP_DIRS = {".git", "node_modules", "dist", "build", "coverage", ".vite", "__pycache__"}
STYLE_EXT = {".css", ".scss", ".sass", ".less"}
CODE_EXT = {".tsx", ".ts", ".jsx", ".js", ".html"}
TEXT_HINT = re.compile(r"ink|text|fg|foreground|muted?|dim|faint|body|title|label", re.I)
BG_HINT = re.compile(r"canvas|bg|background|surface|base|app|page", re.I)
HEX = re.compile(r"#([0-9a-fA-F]{3,8})\b")
THEME_VAR = re.compile(r"--([a-z0-9-]+)\s*:\s*([^;}\n]+)")
ARBITRARY_COLOR = re.compile(r"\b(?:bg|text|border|ring|from|to|via)-\[#([0-9a-fA-F]{3,8})\]")
RAW_PALETTE = re.compile(
    r"\b(?:bg|text|border|ring|from|to|via)-(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b"
)


def _find_web(root: Path, web_dir: str) -> Path | None:
    if web_dir:
        p = Path(web_dir)
        return p if p.exists() else None
    for cand in (root / "web", root / "frontend", root / "client", root):
        if (cand / "package.json").exists():
            return cand
    return None


def _rgb(value: str):
    v = value.strip().lstrip("#")
    if len(v) == 3:
        v = "".join(ch * 2 for ch in v)
    if len(v) == 8:
        v = v[:6]
    if len(v) != 6:
        return None
    try:
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _lum(rgb) -> float:
    def f(x: float) -> float:
        x /= 255
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    r, g, b = (f(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _styles(web: Path):
    for p in web.rglob("*"):
        if p.is_file() and p.suffix.lower() in STYLE_EXT and not any(x in p.parts for x in SKIP_DIRS):
            yield p


def _code(web: Path):
    for p in web.rglob("*"):
        if p.is_file() and p.suffix.lower() in CODE_EXT and not any(x in p.parts for x in SKIP_DIRS):
            yield p


def _tokens(web: Path) -> dict[str, str]:
    tokens: dict[str, str] = {}
    for p in _styles(web):
        text = p.read_text(errors="ignore")
        for block in re.findall(r"@theme\s*\{(.*?)\}", text, re.S) + re.findall(r":root\s*\{(.*?)\}", text, re.S):
            for name, value in THEME_VAR.findall(block):
                if _rgb(value):
                    tokens.setdefault(name.lower(), value.strip())
    return tokens


@skill
def css_stack_standards(web_dir: str = "", repo_path: str = ".") -> str:
    """Audit Tailwind/Bootstrap/Material styling against design-token and WCAG standards.

    Detects which CSS system a web project uses, checks for one token source
    (Tailwind v4 `@theme` or `:root` custom properties), computes WCAG 2.1
    contrast for text tokens against the canvas/surface, and flags hardcoded
    hex values, arbitrary colours, raw palette classes, stale v3 configs,
    framework mixing, and missing reduced-motion / focus-visible / colour-scheme
    baselines. Read-only and advisory.

    Params:
      web_dir: Web project directory. Empty = auto-detect web/frontend/client.
      repo_path: Repository root used when web_dir is empty (default current dir).
    """
    root = Path(repo_path)
    web = _find_web(root, web_dir)
    if web is None:
        return f"No web project found at {web_dir or root}"

    pkg_path = web / "package.json"
    pkg = json.loads(pkg_path.read_text(errors="ignore")) if pkg_path.exists() else {}
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    out: list[str] = [f"Project: {web}"]
    errors = warns = 0

    def note(level: str, msg: str):
        nonlocal errors, warns
        out.append(f"[{level}] {msg}")
        if level == "error":
            errors += 1
        elif level == "warn":
            warns += 1

    css_text = "\n".join(p.read_text(errors="ignore") for p in _styles(web))
    code_text = "\n".join(p.read_text(errors="ignore") for p in _code(web))

    # --- which systems are in play ------------------------------------- #
    tailwind = "tailwindcss" in deps or "@tailwindcss/vite" in deps or "@tailwindcss/postcss" in deps
    tw_v4 = bool(re.search(r"@import\s+[\"']tailwindcss[\"']", css_text)) or "@theme" in css_text
    tw_v3 = bool(re.search(r"@tailwind\s+(base|components|utilities)", css_text))
    bootstrap = "bootstrap" in deps or "bootstrap.min.css" in code_text or "bootstrap.scss" in css_text
    material = any(k in deps for k in ("@mui/material", "@material-ui/core", "@angular/material"))
    systems = [n for n, on in (("Tailwind", tailwind), ("Bootstrap", bootstrap), ("Material", material)) if on]
    if not systems:
        note("warn", "no Tailwind, Bootstrap or Material detected — a bespoke CSS system needs its own tokens/docs")
    else:
        out.append(f"Systems: {', '.join(systems)}" + (" (Tailwind v4)" if tw_v4 else " (Tailwind v3)" if tw_v3 else ""))
    if len(systems) > 1:
        note("warn", f"{' + '.join(systems)} are mixed — pick one visual system so tokens and resets do not fight")

    if tailwind and tw_v4:
        for cfg in list(web.glob("tailwind.config.*")):
            if "@config" not in css_text:
                note("warn", f"{cfg.name} is inert under Tailwind v4 unless referenced with `@config` — duplicated tokens drift")
    if tailwind and tw_v3 and not any(web.glob("tailwind.config.*")):
        note("warn", "Tailwind v3 directives without tailwind.config.* — content scanning may miss files")

    if material and not re.search(r"ThemeProvider|createTheme|provide: ?MATERIAL", code_text):
        note("warn", "Material detected but no theme provider — components will use the default palette, not your tokens")

    # --- tokens --------------------------------------------------------- #
    tokens = _tokens(web)
    if tailwind and tw_v4 and not tokens:
        note("error", "Tailwind v4 without `@theme` colour tokens — the theme has no single source of truth")
    if tokens:
        out.append(f"Tokens: {len(tokens)} semantic colour(s): {', '.join(sorted(tokens)[:12])}" + ("…" if len(tokens) > 12 else ""))
    else:
        note("warn", "no CSS custom-property colour tokens found")

    # --- WCAG contrast for text tokens --------------------------------- #
    # Pair each text token with its role family, not every background: chrome
    # text belongs on chrome, feedback text on its own -bg, body text on the
    # page surfaces. Comparing all pairs produces false failures.
    by_name = {n: _rgb(v) for n, v in tokens.items()}
    text_names = [
        n for n in by_name
        if any(k in n for k in ("ink", "text", "fg", "foreground", "label", "title"))
        and not n.endswith("bg")
    ]
    bg_names = [n for n in by_name if n not in text_names and not n.endswith("fg")]

    def family(name: str) -> list[str]:
        n = name.lower()
        if "chrome" in n:
            return [b for b in bg_names if "chrome" in b]
        if "inverse" in n:
            return [b for b in bg_names if "chrome" in b or "accent-strong" in b]
        if "accent" in n:
            return [b for b in bg_names if "accent" in b and "soft" not in b]
        for state in ("danger", "error", "success", "warning", "info"):
            if state in n:
                # `*-fg` text sits on `*-bg` tint, not on the solid state fill.
                if n.endswith("fg"):
                    tinted = [b for b in bg_names if f"{state}-bg" in b]
                    if tinted:
                        return tinted
                return [b for b in bg_names if state in b]
        return [b for b in bg_names if any(k in b for k in ("canvas", "surface", "background", "base", "page"))]

    if tokens and text_names:
        for name in sorted(text_names):
            rgb = by_name[name]
            candidates = [b for b in family(name) if by_name[b]]
            pairs = [(b, _contrast(rgb, by_name[b])) for b in candidates]
            if not pairs:
                continue
            base_name, ratio = min(pairs, key=lambda p: p[1])
            if ratio < 3.0:
                note("error", f"token --{name} is {ratio:.2f}:1 on --{base_name} — below WCAG AA (4.5:1) even for large text")
            elif ratio < 4.5:
                note("warn", f"token --{name} is {ratio:.2f}:1 on --{base_name} — below WCAG AA 4.5:1 for body text")
    elif not tokens:
        note("warn", "cannot check contrast without colour tokens")

    # --- token bypass --------------------------------------------------- #
    # Ignore hex inside comments: the palette provenance note is not a style.
    css_styles = re.sub(r"/\*.*?\*/", "", css_text, flags=re.S)
    hard_hex = [m.group(0) for m in HEX.finditer(css_styles)]
    # Ignore the hex values that define the tokens themselves.
    token_values = {v.strip().lower() for v in tokens.values()}
    stray = [h for h in hard_hex if h.lower() not in token_values]
    if stray:
        note("warn", f"{len(stray)} hardcoded hex value(s) outside the token block, e.g. {', '.join(sorted(set(stray))[:5])}")
    arbitrary = ARBITRARY_COLOR.findall(code_text)
    if arbitrary:
        note("warn", f"{len(arbitrary)} arbitrary Tailwind colour(s) like bg-[#…] — add a token instead")
    raw = RAW_PALETTE.findall(code_text)
    if raw:
        note("warn", f"{len(raw)} raw palette utility use(s) (e.g. {', '.join(sorted(set(raw))[:5])}) — prefer semantic tokens for status colour")

    # --- baselines ------------------------------------------------------ #
    if ("@keyframes" in css_text or "animation:" in css_text or "animate-" in code_text) and "prefers-reduced-motion" not in css_text:
        note("error", "animation present without `prefers-reduced-motion` — motion must be suppressible")
    if ":focus-visible" not in css_text and "focus-visible:" not in code_text:
        note("warn", "no :focus-visible style — keyboard users lose the focus ring")
    if "color-scheme" not in css_text:
        note("warn", "no `color-scheme` declaration — native controls and scrollbars may not match the theme")
    if "::selection" not in css_text:
        note("warn", "no ::selection style — selection uses the browser default, which may not meet contrast")

    out.append("")
    out.append(f"CSS system: {errors} error(s) · {warns} warning(s)")
    out.append("Verdict: PASS" if not errors else "Verdict: CONCERNS — fix errors or record the exception")
    return "\n".join(out)
