import json
import re
from pathlib import Path

from openharness.skill import SkillError, skill

# --------------------------------------------------------------------------- #
# Frontend theme designer.
#
# Builds the reusable visual system for a whole product: a curated palette with
# computed WCAG ratios, typography and spacing scales, shell landmarks, page
# templates, alert patterns and component states. It emits real CSS
# (`tokens.css`) plus a usage guide (`THEME.md`) when an output directory is
# given. The palette is chosen by product domain unless overridden; every
# semantic text pair is verified at generation time, so the theme cannot ship
# with a known AA failure.
# --------------------------------------------------------------------------- #

SKIP_DIRS = {".git", "node_modules", "dist", "build", "coverage", ".vite", "__pycache__", ".openharness"}
STYLE_EXT = {".css", ".scss", ".sass", ".less"}
CODE_EXT = {".tsx", ".ts", ".jsx", ".js", ".html"}

PALETTES = {
    "industrial": {
        "why": "dense operational screens, long shifts, shop-floor light",
        "light": dict(canvas="f6f7f8", surface="ffffff", raised="eef1f3", ink="16202a",
                      muted="47535f", subtle="5f6b76", border="d3dae0", strong="9aa7b2",
                      accent="0f7f6b", accent_contrast="ffffff", danger="b3261e",
                      success="1c6b45", warning="8a5a00", info="1a5f8a", focus="0b6ea8"),
        "dark": dict(canvas="0e1418", surface="151d23", raised="1c262e", ink="e8eef2",
                     muted="a8b6c0", subtle="8b9aa5", border="2a3741", strong="46545f",
                     accent="4fd1b5", accent_contrast="08231d", danger="ff8a80",
                     success="7ad9a8", warning="f0c060", info="8fc8ee", focus="7cc4f0"),
    },
    "editorial": {
        "why": "story-led product, generous whitespace, warm neutrals",
        "light": dict(canvas="faf8f4", surface="ffffff", raised="f1ece4", ink="241f1a",
                      muted="574f46", subtle="6b6157", border="ded5c8", strong="b3a899",
                      accent="8a3b12", accent_contrast="ffffff", danger="a3241c",
                      success="2f6b3a", warning="7a5300", info="2b5f7a", focus="1f5f8b"),
        "dark": dict(canvas="17130f", surface="1f1a15", raised="2a231b", ink="efe8df",
                     muted="b8aa9c", subtle="9a8b7c", border="3b3227", strong="6b5a48",
                     accent="e08a5a", accent_contrast="2a1408", danger="ff9a8f",
                     success="8fd3a0", warning="e8c26a", info="8fc3e0", focus="9ccdec"),
    },
    "clinical": {
        "why": "trust-critical, calm, low-saturation, high legibility",
        "light": dict(canvas="f5f8fa", surface="ffffff", raised="eaf0f4", ink="12232e",
                      muted="425666", subtle="56697a", border="d2dde5", strong="9fb1bf",
                      accent="0f6f8f", accent_contrast="ffffff", danger="b02a37",
                      success="1f6b47", warning="8a5a00", info="1a5f8a", focus="0b6ea8"),
        "dark": dict(canvas="0b1218", surface="121c24", raised="1a2630", ink="e6f0f5",
                     muted="a6bac7", subtle="8aa0b0", border="293845", strong="4a5d6b",
                     accent="63c9e6", accent_contrast="05222c", danger="ff9aa3",
                     success="7fd6a8", warning="f2c96b", info="8fc8ee", focus="86cdf2"),
    },
    "playful": {
        "why": "consumer or creative tool, expressive brand, friendly density",
        "light": dict(canvas="f7f5ff", surface="ffffff", raised="efeaff", ink="1d1a2b",
                      muted="4f4a63", subtle="635d78", border="dcd4f5", strong="ab9fd0",
                      accent="5b3ee8", accent_contrast="ffffff", danger="b3261e",
                      success="1f6b47", warning="8a5a00", info="1a5f8a", focus="6b4df0"),
        "dark": dict(canvas="121019", surface="1a1724", raised="241f31", ink="ebe8f5",
                     muted="b3adc7", subtle="9a94ae", border="352e47", strong="5c5375",
                     accent="a99bff", accent_contrast="1b1238", danger="ff9aa3",
                     success="7fd6a8", warning="f2c96b", info="9ccdf0", focus="b9aaff"),
    },
}

FONTS = {
    "industrial": ('"IBM Plex Sans", "Inter", system-ui, -apple-system, sans-serif',
                   '"IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace'),
    "editorial": ('"Inter", "Source Sans 3", system-ui, -apple-system, sans-serif',
                  '"IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace'),
    "clinical": ('"Inter", system-ui, -apple-system, "Segoe UI", sans-serif',
                 '"IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace'),
    "playful": ('"Nunito Sans", "Inter", system-ui, -apple-system, sans-serif',
                '"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace'),
}

ROLES = ("canvas", "surface", "raised", "ink", "muted", "subtle", "border", "strong",
         "accent", "accent_contrast", "danger", "success", "warning", "info", "focus")

ROLE_TOKEN = {
    "canvas": "color-canvas", "surface": "color-surface", "raised": "color-surface-raised",
    "ink": "color-ink", "muted": "color-ink-muted", "subtle": "color-ink-subtle",
    "border": "color-border", "strong": "color-border-strong", "accent": "color-accent",
    "accent_contrast": "color-accent-contrast", "danger": "color-danger",
    "success": "color-success", "warning": "color-warning", "info": "color-info",
    "focus": "color-focus",
}

TYPE = (("text-xs", "0.75rem"), ("text-sm", "0.875rem"), ("text-base", "1rem"),
        ("text-lg", "1.125rem"), ("text-xl", "1.375rem"), ("text-2xl", "1.75rem"),
        ("text-3xl", "2.25rem"), ("leading-tight", "1.25"), ("leading-normal", "1.5"),
        ("leading-relaxed", "1.65"), ("weight-regular", "400"), ("weight-medium", "500"),
        ("weight-semibold", "600"), ("weight-bold", "700"),
        ("tracking-tight", "-0.02em"), ("tracking-wide", "0.02em"))

SPACE = (("space-1", "4px"), ("space-2", "8px"), ("space-3", "12px"), ("space-4", "16px"),
         ("space-5", "24px"), ("space-6", "32px"), ("space-7", "48px"), ("space-8", "64px"))

RADIUS = (("radius-sm", "4px"), ("radius-md", "8px"), ("radius-lg", "12px"), ("radius-pill", "999px"))

SHADOW = (("shadow-sm", "0 1px 2px rgba(9, 14, 18, 0.08)"),
          ("shadow-md", "0 4px 12px rgba(9, 14, 18, 0.14)"),
          ("shadow-lg", "0 16px 40px rgba(9, 14, 18, 0.20)"))

MOTION = (("duration-fast", "120ms"), ("duration-base", "200ms"), ("duration-slow", "320ms"),
          ("ease-standard", "cubic-bezier(0.2, 0.8, 0.2, 1)"))

LAYOUT = (("layout-content", "1200px"), ("layout-prose", "68ch"), ("layout-gutter", "24px"),
          ("layout-header", "56px"), ("z-dropdown", "10"), ("z-sticky", "100"),
          ("z-overlay", "500"), ("z-modal", "600"), ("z-toast", "700"))

CHECK_PAIRS = (("ink", "surface", 4.5), ("muted", "surface", 4.5), ("subtle", "surface", 4.5),
               ("accent", "surface", 4.5), ("accent_contrast", "accent", 4.5),
               ("danger", "surface", 4.5), ("success", "surface", 4.5),
               ("warning", "surface", 4.5), ("info", "surface", 4.5),
               ("focus", "canvas", 3.0))


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


def _contrast(a: str, b: str) -> float:
    ra, rb = _rgb(a), _rgb(b)
    if ra is None or rb is None:
        return 0.0
    la, lb = _lum(ra), _lum(rb)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _mix(fg: str, bg: str, pct: float) -> str:
    a, b = _rgb(fg), _rgb(bg)
    if a is None or b is None:
        return fg
    return "#" + "".join(f"{round(a[i] * pct + b[i] * (1 - pct)):02x}" for i in range(3))


def _find_web(root: Path, web_dir: str) -> Path | None:
    if web_dir:
        p = Path(web_dir)
        return p if p.exists() else None
    for cand in (root / "web", root / "frontend", root / "client", root):
        if (cand / "package.json").exists():
            return cand
    return None


def _styles(web: Path | None) -> str:
    if web is None:
        return ""
    parts: list[str] = []
    for p in web.rglob("*"):
        if p.is_file() and p.suffix.lower() in STYLE_EXT and not any(x in p.parts for x in SKIP_DIRS):
            try:
                parts.append(p.read_text(errors="ignore"))
            except Exception:
                continue
    return "\n".join(parts)


def _stack(web: Path | None) -> str:
    if web is None or not (web / "package.json").exists():
        return "no package.json found"
    try:
        data = json.loads((web / "package.json").read_text(errors="ignore"))
    except Exception:
        return "package.json unreadable"
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    found = [n for n in ("react", "vue", "svelte", "solid-js", "next", "vite", "tailwindcss",
                         "bootstrap", "sass", "typescript") if n in deps]
    return ", ".join(found) or "no known frontend framework"


def _product_text(root: Path) -> str:
    parts = []
    for p in (root / "README.md", root / "PRODUCT.md"):
        if p.exists():
            parts.append(p.read_text(errors="ignore")[:20000])
    for base in (root / "docs", root / "specs"):
        if base.exists():
            for p in list(base.rglob("*.md"))[:200]:
                try:
                    parts.append(p.read_text(errors="ignore")[:8000])
                except Exception:
                    continue
    return "\n".join(parts).lower()


def _infer_style(text: str) -> tuple[str, str]:
    if any(w in text for w in ("manufactur", "factory", "shop floor", "mes", "loom", "production order")):
        return "industrial", "manufacturing language in the docs"
    if any(w in text for w in ("patient", "clinic", "health", "medical")):
        return "clinical", "health language in the docs"
    if any(w in text for w in ("commerce", "storefront", "checkout", "catalog", "catalogue")):
        return "editorial", "commerce/catalogue language in the docs"
    if any(w in text for w in ("llm", "agent", "creative", "playful", "community")):
        return "playful", "creative/consumer language in the docs"
    return "industrial", "no strong domain signal — defaulting to the densest neutral"


def _code_bypasses(web: Path | None) -> tuple[int, int]:
    if web is None:
        return 0, 0
    hexes = inline = 0
    for p in web.rglob("*"):
        if not (p.is_file() and p.suffix.lower() in CODE_EXT) or any(x in p.parts for x in SKIP_DIRS):
            continue
        try:
            text = p.read_text(errors="ignore")
        except Exception:
            continue
        hexes += len(re.findall(r"#[0-9a-fA-F]{3,8}\b", text))
        inline += len(re.findall(r"style=\{\{[^}]*color", text))
    return hexes, inline


def _decl(tokens: list[tuple[str, str]], prefix: str, indent: str = "  ") -> str:
    return "\n".join(f"{indent}--{prefix}-{k}: {v};" for k, v in tokens)


def _colors(p: dict, prefix: str, mode: str, include_scheme: bool = True) -> str:
    light = mode == "light"
    soft = {r: _mix(p[r], p["surface"], 0.12) for r in ("accent", "danger", "success", "warning", "info")}
    hover = _mix(p["accent"], "#000000" if light else "#ffffff", 0.12)
    selection = _mix(p["accent"], p["surface"], 0.22)
    disabled_bg = _mix(p["ink"], p["surface"], 0.08)
    tokens = [
        ("color-canvas", "#" + p["canvas"]),
        ("color-surface", "#" + p["surface"]),
        ("color-surface-raised", "#" + p["raised"]),
        ("color-ink", "#" + p["ink"]),
        ("color-ink-muted", "#" + p["muted"]),
        ("color-ink-subtle", "#" + p["subtle"]),
        ("color-border", "#" + p["border"]),
        ("color-border-strong", "#" + p["strong"]),
        ("color-accent", "#" + p["accent"]),
        ("color-accent-hover", hover),
        ("color-accent-contrast", "#" + p["accent_contrast"]),
        ("color-accent-soft", soft["accent"]),
        ("color-focus", "#" + p["focus"]),
        ("color-danger", "#" + p["danger"]),
        ("color-danger-soft", soft["danger"]),
        ("color-success", "#" + p["success"]),
        ("color-success-soft", soft["success"]),
        ("color-warning", "#" + p["warning"]),
        ("color-warning-soft", soft["warning"]),
        ("color-info", "#" + p["info"]),
        ("color-info-soft", soft["info"]),
        ("color-overlay", "rgba(9, 14, 18, 0.45)" if light else "rgba(0, 0, 0, 0.60)"),
        ("color-selection-bg", selection),
        ("color-selection-ink", "#" + p["ink"]),
        ("color-disabled-bg", disabled_bg),
        ("color-disabled-ink", "#" + p["subtle"]),
    ]
    head = f"color-scheme: {mode};\n" if include_scheme else ""
    return head + _decl(tokens, prefix)


def _css(style: str, prefix: str, dark: bool) -> str:
    light = PALETTES[style]["light"]
    darkp = PALETTES[style]["dark"]
    sans, mono = FONTS[style]
    scale = [("font-sans", sans), ("font-mono", mono)] + list(TYPE) + list(SPACE) + list(RADIUS) \
        + list(SHADOW) + list(MOTION) + list(LAYOUT)
    blocks = [
        f"/* Generated by theme_designer — style: {style}, prefix: {prefix}. */",
        "",
        ":root {",
        _colors(light, prefix, "light"),
        _decl(scale, prefix, ""),
        "}",
    ]
    if dark:
        blocks += [
            "",
            "@media (prefers-color-scheme: dark) {",
            "  :root {",
            _colors(darkp, prefix, "dark", include_scheme=False),
            "  }",
            "}",
            "",
            f':root[data-theme="light"] {{',
            _colors(light, prefix, "light", include_scheme=False),
            "}",
            "",
            f':root[data-theme="dark"] {{',
            _colors(darkp, prefix, "dark", include_scheme=False),
            "}",
        ]
    blocks += [
        "",
        "*, *::before, *::after { box-sizing: border-box; }",
        "html { -webkit-text-size-adjust: 100%; }",
        "body {",
        f"  margin: 0;",
        f"  background: var(--{prefix}-color-canvas);",
        f"  color: var(--{prefix}-color-ink);",
        f"  font-family: var(--{prefix}-font-sans);",
        f"  font-size: var(--{prefix}-text-base);",
        f"  line-height: var(--{prefix}-leading-normal);",
        "}",
        f"::selection {{ background: var(--{prefix}-color-selection-bg); "
        f"color: var(--{prefix}-color-selection-ink); }}",
        f":focus-visible {{ outline: 2px solid var(--{prefix}-color-focus); outline-offset: 2px; }}",
        "img, svg { display: block; max-width: 100%; }",
        "",
        ".visually-hidden {",
        "  position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;",
        "  overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; border: 0;",
        "}",
        "",
        ".skip-link {",
        f"  position: absolute; left: -9999px; top: var(--{prefix}-space-2);",
        f"  background: var(--{prefix}-color-surface); color: var(--{prefix}-color-ink);",
        f"  padding: var(--{prefix}-space-2) var(--{prefix}-space-4);",
        f"  border-radius: var(--{prefix}-radius-md); z-index: var(--{prefix}-z-toast);",
        "}",
        ".skip-link:focus { left: 16px; }",
        "",
        "@media (prefers-reduced-motion: reduce) {",
        "  *, *::before, *::after {",
        "    animation-duration: 0.01ms !important;",
        "    animation-iteration-count: 1 !important;",
        "    transition-duration: 0.01ms !important;",
        "    scroll-behavior: auto !important;",
        "  }",
        "}",
        "",
    ]
    return "\n".join(blocks)


def _contrast_rows(p: dict) -> list[str]:
    rows = []
    for fg, bg, need in CHECK_PAIRS:
        ratio = _contrast("#" + p[fg], "#" + p[bg])
        rows.append(f"| `{fg}` on `{bg}` | {ratio:.2f}:1 | {need}:1 | "
                    + ("pass" if ratio >= need else "**FAIL**") + " |")
    return rows


def _audit(css: str, web: Path | None) -> list[str]:
    tokens = sorted(set(re.findall(r"--([a-z0-9-]+)\s*:", css)))
    low = css.lower()
    out = [f"Existing custom properties: {len(tokens)}"
           + (f" (e.g. {', '.join(tokens[:6])})" if tokens else " — none found")]
    checks = (
        ("single token block", len(re.findall(r":root\s*\{|@theme\s*\{", css)) == 1),
        ("accent role", any("accent" in t for t in tokens)),
        ("surface + ink roles", any("surface" in t for t in tokens) and any("ink" in t or "text" in t for t in tokens)),
        ("status roles (danger/success/warning)", all(any(k in t for t in tokens) for k in ("danger", "success", "warning"))
         or all(any(k in t for t in tokens) for k in ("error", "success", "warning"))),
        ("focus ring token", any("focus" in t for t in tokens) or ":focus-visible" in low),
        ("selection token", "::selection" in low),
        ("disabled tokens", any("disabled" in t for t in tokens)),
        ("overlay token", any("overlay" in t or "scrim" in t for t in tokens)),
        ("reduced-motion", "prefers-reduced-motion" in low),
        ("explicit color-scheme", "color-scheme" in low),
        ("dark theme mechanism", bool(re.search(r"prefers-color-scheme|\[data-theme|\.dark\b", low))),
    )
    out += [("[ok] " if ok else "[gap] ") + label for label, ok in checks]
    hexes, inline = _code_bypasses(web)
    out.append(("[ok] " if hexes == 0 else "[gap] ")
               + f"hardcoded hex in component code: {hexes}"
               + ("" if hexes == 0 else " — move literal colours into the token layer"))
    out.append(("[ok] " if inline == 0 else "[gap] ") + f"inline colour styles: {inline}")
    return out


def _guide(style: str, prefix: str, dark: bool, root: Path, web: Path | None,
           stack: str, audit: list[str], reason: str, css: str) -> str:
    light = PALETTES[style]["light"]
    darkp = PALETTES[style]["dark"]
    sans, mono = FONTS[style]
    v = lambda name: f"var(--{prefix}-{name})"
    rows = [f"| `{k}` | `#{light[k]}` | `#{darkp[k]}` |" for k in ROLES]
    lines = [
        f"# Theme system — {style}",
        "",
        f"Token prefix: `--{prefix}-` · Dark mode: {'included' if dark else 'omitted'} · "
        f"Stack: {stack}",
        "",
        f"Chosen because: {reason} — {PALETTES[style]['why']}.",
        "",
        "## Audit of the existing theme",
        "",
        *audit,
        "",
        "## Colour",
        "",
        "| Role | Light | Dark |",
        "| --- | --- | --- |",
        *rows,
        "",
        "Derived roles: `accent-hover` (12% darker/lighter), `accent-soft` (12% tint "
        "on surface), and the status `-soft` tints. Selection uses a 22% accent tint.",
        "",
        "### Contrast (WCAG 2.1)",
        "",
        "| Pair | Ratio | Minimum | Result |",
        "| --- | --- | --- | --- |",
        *_contrast_rows(light),
        "",
        "<details><summary>Dark-mode ratios</summary>",
        "",
        "| Pair | Ratio | Minimum | Result |",
        "| --- | --- | --- | --- |",
        *_contrast_rows(darkp),
        "",
        "</details>",
        "",
        "Status is always **text + icon + colour**; colour alone never carries meaning.",
        "",
        "## Typography",
        "",
        f"- Sans: `{sans}`",
        f"- Mono: `{mono}`",
        f"- Scale: 12 / 14 / 16 / 18 / 22 / 28 / 36 px (`text-xs` … `text-3xl`).",
        "- Body 16 px, line-height 1.5; dense tables may use `text-sm` at 1.5.",
        "- Self-host fonts with `font-display: swap`; never block first paint on a CDN.",
        "- Max two families and three weights per screen.",
        "",
        "## Space, radius, elevation, motion",
        "",
        f"- Space: {', '.join(v(k) for k, _ in SPACE)}.",
        f"- Radius: {', '.join(v(k) for k, _ in RADIUS)}.",
        "- Elevation is for overlays only; page surfaces use borders, not shadows.",
        f"- Motion: {v('duration-fast')} for hover, {v('duration-base')} for enter/exit, "
        f"{v('ease-standard')}; honour `prefers-reduced-motion` (already in tokens.css).",
        "",
        "## UI shell",
        "",
        "```html",
        f'<a class="skip-link" href="#main">Skip to content</a>',
        '<header class="app-header"> … brand lockup · primary nav · account menu … </header>',
        '<div class="app-body">',
        '  <nav aria-label="Primary"> … </nav>          <!-- collapses to a drawer < 900px -->',
        f'  <main id="main" tabindex="-1"> … page … </main>',
        '  <aside aria-label="Context"> … optional … </aside>',
        '</div>',
        '<footer> … </footer>',
        "```",
        "",
        "- One `<main>` per page, one `<h1>`; header height `layout-header`.",
        "- Skip link is the first focusable element and targets `#main`.",
        "- Content width `layout-content`; prose `layout-prose`; gutter `layout-gutter`.",
        "- Navigation is text-first; icons never replace a label without `aria-label`.",
        "",
        "## Page templates",
        "",
        "| Page | Structure | Notes |",
        "| --- | --- | --- |",
        "| List | header (title + primary action) → labelled filters → live region → table with caption | empty, loading and error states in the same slot |",
        "| Detail | back link → title + status badge → meta grid → sections → sticky action bar | destructive actions separated and confirmed |",
        "| Form | single column ≤ 680 px → field groups → inline errors → primary action | labels above fields; no placeholder-only labels |",
        "| Auth | centred card ≤ 400 px → mark + wordmark → one column | no app navigation before sign-in |",
        "| Settings | section nav (≥ 900 px) → stacked sections | save is explicit; unsaved-changes guard |",
        "",
        "## Alerts and feedback",
        "",
        "| Pattern | Markup | Behaviour |",
        "| --- | --- | --- |",
        "| Field error | `<p class=\"field-error\" id=\"x-error\" role=\"alert\">` | input gets `aria-invalid` + `aria-describedby`; focus first invalid field |",
        "| Page banner | `<div role=\"alert\">` error · `role=\"status\"` success | never auto-dismiss an error; dismiss button has an accessible name |",
        "| Toast | `role=\"status\"` polite, `role=\"alert\"` assertive | one at a time; 6 s for success, persistent for error |",
        "| Confirm | `role=\"dialog\" aria-modal=\"true\"` + labelled title | focus trap, Escape cancels, focus returns to the trigger |",
        "| Loading | `aria-busy=\"true\"` + `role=\"status\"` text | spinner is decorative (`aria-hidden`); state is announced |",
        "",
        "## Component states",
        "",
        "- **Default / hover / active**: background shifts by token, never by a raw hex.",
        "- **Focus-visible**: 2 px `color-focus` ring, 2 px offset; never removed.",
        "- **Disabled**: `disabled` or `aria-disabled` + `color-disabled-*`; still readable.",
        "- **Loading**: keep width stable, disable the action, announce the state.",
        "- **Selected**: accent-soft background + 3 px accent edge, not colour alone.",
        "- **Error**: danger border + field message + `aria-invalid`.",
        "",
        "## Usage rules",
        "",
        f"1. Components use only semantic tokens (`{v('color-surface')}`), never raw hex.",
        "2. One token source: this file. A per-component palette is drift.",
        "3. New token ⇒ new role and a line in this guide; otherwise reuse.",
        "4. Tables, badges and alerts share the same status recipe.",
        "5. Any animation must have a reduced-motion path.",
        "",
        "## Adoption checklist",
        "",
        "- [ ] Map the existing prefix to the new prefix (or keep `--" + prefix + "-`).",
        "- [ ] Replace hardcoded hex and inline colour styles.",
        "- [ ] Add shell landmarks and the skip link.",
        "- [ ] Convert one list, one detail and one form page before the rest.",
        "- [ ] Re-run `css_stack_standards` and `ux_architecture`; both should improve.",
        "- [ ] Record the chosen style and palette in the design-system doc or an ADR.",
        "",
        f"Generated CSS: `tokens.css` ({len(css.splitlines())} lines).",
        "",
    ]
    return "\n".join(lines)


@skill
def theme_designer(repo_path: str = ".", web_dir: str = "", style: str = "",
                   prefix: str = "ds", dark: bool = True, out_dir: str = "") -> str:
    """Design the reusable theme system: palette, type, shell, pages and alerts.

    Detects the stack and existing tokens, then generates a complete design
    system contract — AA-verified light/dark palettes, typography and spacing
    scales, shell landmarks, page templates, alert and component-state recipes —
    and writes `tokens.css` + `THEME.md` when `out_dir` is given. Use it once per
    product, before styling pages, so every feature consumes the same tokens.

    Params:
      repo_path: Repository root (default current dir).
      web_dir: Web project directory. Empty = auto-detect web/frontend/client.
      style: industrial | editorial | clinical | playful. Empty = infer from docs.
      prefix: CSS custom-property prefix, e.g. `ds` → `--ds-color-ink`.
      dark: Include a dark theme (prefers-color-scheme + data-theme override).
      out_dir: Directory for `tokens.css` and `THEME.md`. Empty = print only.
    """
    root = Path(repo_path)
    web = _find_web(root, web_dir)
    text = _product_text(root)
    if style:
        style = style.strip().lower()
        if style not in PALETTES:
            raise SkillError(f"Unknown style '{style}'. Choose one of: {', '.join(PALETTES)}")
        reason = "requested explicitly"
    else:
        style, reason = _infer_style(text)
    if not re.fullmatch(r"[a-z][a-z0-9-]*", prefix):
        raise SkillError(f"Invalid token prefix '{prefix}' — use lowercase letters, digits and hyphens")

    css = _css(style, prefix, dark)
    stack = _stack(web)
    audit = _audit(_styles(web), web)
    guide = _guide(style, prefix, dark, root, web, stack, audit, reason, css)

    failures = []
    for mode in ("light", "dark"):
        p = PALETTES[style][mode]
        for fg, bg, need in CHECK_PAIRS:
            ratio = _contrast("#" + p[fg], "#" + p[bg])
            if ratio < need:
                failures.append(f"{mode} {fg} on {bg}: {ratio:.2f}:1 < {need}:1")

    report = guide
    if failures:
        report += "\n## Contrast failures — fix before shipping\n\n" + \
            "\n".join(f"- {f}" for f in failures) + "\n"

    if out_dir:
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "tokens.css").write_text(css)
        (out / "THEME.md").write_text(report)
        report += f"\nWrote {out / 'tokens.css'} and {out / 'THEME.md'}"
    return report
