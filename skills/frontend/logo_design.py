import json
import re
from pathlib import Path

from openharness.skill import skill

# --------------------------------------------------------------------------- #
# Logo / brand-mark design brief.
#
# Collects what the repository already says about the product (name, domain,
# audience, intent), then produces three concept territories, an SVG drawing
# contract, a platform asset matrix and an audit of the assets that exist. It
# never draws the mark: the logo-designer agent turns the brief into SVG. A
# brief that names the domain and the constraints is what stops a logo from
# being a generic swoosh.
# --------------------------------------------------------------------------- #

SKIP_DIRS = {".git", "node_modules", "dist", "build", "coverage", ".vite", "__pycache__", ".openharness"}

DOMAIN_TERMS = {
    "manufacturing": ("manufactur", "factory", "production", "shop floor", "loom", "textile",
                      "work order", "routing", "bill of material", "mes", "erp"),
    "logistics": ("logistic", "shipping", "fleet", "warehouse", "delivery", "supply chain",
                  "dispatch", "freight"),
    "commerce": ("commerce", "checkout", "cart", "storefront", "marketplace", "retail",
                 "merchandis", "shopper"),
    "finance": ("invoice", "payment", "ledger", "accounting", "bank", "fintech", "billing",
                "reconcil"),
    "health": ("patient", "clinic", "health", "medical", "care plan", "triage"),
    "education": ("course", "student", "learner", "school", "education", "curriculum"),
    "developer tools": ("sdk", "api client", "cli", "developer", "deploy", "infrastructure",
                        "observability", "pipeline"),
    "ai": ("llm", "machine learning", "embedding", "inference", "neural network",
           "artificial intelligence"),
}

DOMAIN_OBJECT = {
    "manufacturing": "a shuttle, beam or interlocking joint",
    "logistics": "a route node, arrow or stacked container",
    "commerce": "a tag, bag or price mark",
    "finance": "a ledger column, coin or balance",
    "health": "a pulse line, cross or protective arc",
    "education": "an open book, path or spark",
    "developer tools": "a bracket, terminal caret or pipeline node",
    "ai": "a node network, spark or orbit",
    "unknown": "the product's core verb — what the user does in one action",
}

STYLE_BY_DOMAIN = {
    "manufacturing": "durable and geometric — sturdy strokes, squared joins, no gradient",
    "logistics": "directional and light — one clear axis of movement, open counters",
    "commerce": "warm and confident — rounded terminals, generous counters",
    "finance": "precise and quiet — thin-to-medium strokes, strict grid",
    "health": "calm and humane — soft arcs, wide apertures, no sharp spikes",
    "education": "open and optimistic — upward arc, friendly geometry",
    "developer tools": "crisp and technical — monospaced rhythm, 90° angles",
    "ai": "emergent and connected — nodes with one differentiated link",
    "unknown": "neutral and structural — legible before expressive",
}

ASSETS = (
    ("Master mark", "32 × 32 viewBox", "SVG", "one file, no text, 8 px safe area"),
    ("Monochrome mark", "32 × 32", "SVG", "single path, `currentColor`, no gradient"),
    ("Horizontal lockup", "mark + wordmark", "SVG", "mark height = cap height; 0.5× gap"),
    ("Stacked lockup", "mark above wordmark", "SVG", "centred; for square placements"),
    ("Favicon", "16 / 32 / 48", "ICO + SVG", "test at 16 px; drop detail, not the silhouette"),
    ("PWA icon", "192 / 512", "PNG", "opaque background, no transparent halo"),
    ("Maskable icon", "512", "PNG", "mark inside the centre 80% safe zone"),
    ("Apple touch icon", "180", "PNG", "opaque, no rounded corners (OS masks it)"),
    ("Social / OG card", "1200 × 630", "PNG", "mark + wordmark + one-line promise"),
    ("Avatar", "512", "PNG", "circular-safe: mark centred within 70%"),
    ("Email signature", "400 × 120", "PNG", "light background only, 2× for retina"),
)


def _product_name(root: Path, explicit: str) -> str:
    if explicit.strip():
        return explicit.strip()
    for path in (root / "web" / "package.json", root / "package.json"):
        if path.exists():
            try:
                name = json.loads(path.read_text(errors="ignore")).get("name", "")
            except Exception:
                name = ""
            if name:
                name = re.sub(r"^@[^/]+/", "", name)
                return re.sub(r"[-_](web|app|frontend|ui|client)$", "", name)
    py = root / "pyproject.toml"
    if py.exists():
        m = re.search(r'^name\s*=\s*"([^"]+)"', py.read_text(errors="ignore"), re.M)
        if m:
            return m.group(1)
    return root.name


def _display(name: str) -> str:
    words = re.split(r"[-_.\s]+", name.strip())
    return " ".join(w[:1].upper() + w[1:] for w in words if w) or "Product"


def _evidence(root: Path, web: Path | None) -> str:
    parts: list[str] = []
    for candidate in (root / "README.md", root / "readme.md", root / "PRODUCT.md"):
        if candidate.exists():
            parts.append(candidate.read_text(errors="ignore")[:20000])
    for base in (root / "docs", root / "specs"):
        if not base.exists():
            continue
        for p in list(base.rglob("*.md"))[:300]:
            try:
                parts.append(p.read_text(errors="ignore")[:12000])
            except Exception:
                continue
    if web and (web / "package.json").exists():
        parts.append((web / "package.json").read_text(errors="ignore"))
    return "\n".join(parts).lower()


def _domain(text: str) -> tuple[str, dict[str, int]]:
    scores = {d: sum(text.count(t) for t in terms) for d, terms in DOMAIN_TERMS.items()}
    best = max(scores, key=lambda d: scores[d])
    if scores[best] == 0:
        return "unknown", scores
    return best, scores


def _audience(text: str) -> str:
    m = re.search(r"(?:^|\n)\s*[-*]?\s*(?:Primary\s+)?users?:\s*([^\n]+)", text, re.I)
    if not m:
        return ""
    value = " ".join(m.group(1).split())
    return value if len(value) <= 160 else value[:157].rstrip() + "…"


def _initials(name: str) -> str:
    words = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", name)
    letters = [w[0].upper() for w in words if w[0].isalnum()]
    if not letters:
        return name[:2].upper()
    return "".join(letters[:2]) if len(letters) > 1 else letters[0] * 2


def _assets(root: Path, web: Path | None) -> list[str]:
    dirs = [d for d in (web / "public" if web else None, root / "public", root / "static") if d and d.exists()]
    names = {p.name.lower() for d in dirs for p in d.rglob("*") if p.is_file()}
    out: list[str] = []
    out.append(("[ok]" if any(n.startswith("favicon") for n in names) else "[gap]")
               + " favicon (.svg/.ico)")
    out.append(("[ok]" if any("apple-touch" in n for n in names) else "[gap]")
               + " apple-touch-icon 180 px")
    manifest = None
    for d in dirs:
        for cand in ("site.webmanifest", "manifest.webmanifest", "manifest.json"):
            if (d / cand).exists():
                manifest = d / cand
                break
    if manifest:
        try:
            icons = json.loads(manifest.read_text(errors="ignore")).get("icons", [])
            sizes = sorted({str(i.get("sizes", "")) for i in icons if i.get("sizes")})
            maskable = any("maskable" in str(i.get("purpose", "")) for i in icons)
            out.append(("[ok]" if {"192x192", "512x512"} <= set(sizes) else "[gap]")
                       + f" manifest icons: {', '.join(sizes) or 'none'}")
            out.append(("[ok]" if maskable else "[gap]") + " maskable icon (safe zone)")
        except Exception:
            out.append("[gap] manifest exists but its icons could not be parsed")
    else:
        out.append("[gap] web app manifest with icons")
    out.append(("[ok]" if any(("og" in n or "social" in n) and n.endswith((".png", ".jpg", ".webp")) for n in names) else "[gap]")
               + " social / OG card 1200 × 630")
    svgs = [p for d in dirs for p in d.rglob("*.svg") if p.is_file()]
    with_viewbox = 0
    for p in svgs[:50]:
        try:
            if "viewBox" in p.read_text(errors="ignore")[:2000]:
                with_viewbox += 1
        except Exception:
            continue
    out.append(("[ok]" if with_viewbox else "[gap]")
               + f" scalable marks with viewBox ({with_viewbox}/{len(svgs)} SVG in public)")
    return out


@skill
def logo_design(repo_path: str = ".", web_dir: str = "", product_name: str = "",
                intent: str = "", out: str = "") -> str:
    """Draft a logo brief from the product's domain, then an asset plan for every platform.

    Reads README, docs and specs to infer the product name, domain, audience and
    style; audits the favicon/manifest/social assets that exist; and emits three
    concept territories, an SVG drawing contract, the full device/platform asset
    matrix and acceptance checks. Writes the brief to `out` when given. Does not
    render images — the logo-designer agent draws the SVGs from this brief.

    Params:
      repo_path: Repository root (default current dir).
      web_dir: Web project directory. Empty = auto-detect web/frontend/client.
      product_name: Override the detected product name.
      intent: One line on what the brand should promise (best supplied by a human).
      out: Markdown file to write. Empty = print only.
    """
    root = Path(repo_path)
    web = None
    if web_dir:
        web = Path(web_dir)
    else:
        for cand in (root / "web", root / "frontend", root / "client"):
            if (cand / "package.json").exists():
                web = cand
                break
    name = _display(_product_name(root, product_name))
    text = _evidence(root, web)
    domain, scores = _domain(text)
    audience = _audience(text) or "not recorded"
    initials = _initials(name)
    object_hint = DOMAIN_OBJECT[domain]
    style = STYLE_BY_DOMAIN[domain]
    top = sorted(((d, s) for d, s in scores.items() if s), key=lambda kv: -kv[1])[:3]

    lines: list[str] = [f"# Logo brief — {name}", ""]
    lines.append(f"Domain: **{domain}**" + (f" (signals: {', '.join(f'{d} {s}' for d, s in top)})" if top else " (no signals found)"))
    lines.append(f"Audience: {audience}")
    lines.append(f"Intent: {intent.strip() or 'NOT RECORDED — ask before drawing'}")
    lines.append(f"Suggested visual character: {style}")
    lines.append("")

    if not intent.strip():
        lines += [
            "## Questions to settle first",
            "",
            "1. Who should recognise the mark first — buyer, operator, or developer?",
            "2. What one promise must the mark imply (speed, control, craft, trust)?",
            "3. Which words must the brand avoid (cheap, clinical, playful, corporate)?",
            "4. Is there an existing wordmark, colour or symbol that must be kept?",
            "",
        ]

    lines += [
        "## Concept territories",
        "",
        f"### A. Monogram — “{initials}”",
        f"- Geometry: {initials} built on a 32 px grid from two or three primitives;",
        "  shared stroke weight; no enclosing circle unless it earns its place.",
        "- Wins when: the name is said aloud and the mark must survive at 16 px.",
        "- Risk: generic — differentiate with one cut, overlap or counter-shape.",
        "- Variants: solid, outline, single-path monochrome.",
        "",
        f"### B. Domain object — {object_hint}",
        f"- Geometry: reduce {object_hint} to at most three shapes; one accent fill,",
        "  one ink shape; no literal illustration or tiny details.",
        "- Wins when: the mark should explain the category without a tagline.",
        "- Risk: cliché if the object is drawn, not abstracted — remove one detail twice.",
        "- Variants: positive, negative-space, monochrome.",
        "",
        "### C. Motion / flow mark",
        "- Geometry: a single axis of movement (arrow, current, route, pulse) bent",
        "  once; the bend is the distinctive idea, not the arrowhead.",
        "- Wins when: the promise is speed, flow or coordination.",
        "- Risk: reads as a generic arrow — make the bend asymmetric and ownable.",
        "- Variants: horizontal lockup, square crop, animated draw-on (≤ 600 ms).",
        "",
        "## Drawing contract (SVG)",
        "",
        "- `viewBox=\"0 0 32 32\"`; geometry snapped to a 1 px grid; 2 px padding.",
        "- Mark is one to three paths; no `<text>`, no embedded raster, no filters.",
        "- Monochrome file uses `fill=\"currentColor\"`; colour file uses at most two",
        "  brand tokens plus ink.",
        "- Survives 16 px: remove the smallest detail rather than thin the stroke.",
        "- Corner radius and stroke weight stay consistent across mark and wordmark.",
        "- Wordmark is separate lettering or an outlined font — never live text.",
        "",
        "## Visual prompt (after a territory is chosen)",
        "",
        f"- “Minimal {domain} logo, {style}, abstract {object_hint}, flat vector,",
        "  two colours, no gradient, no text, centred on 32 px grid, high contrast.”",
        "- “Same mark as a single-path monochrome silhouette, legible at 16 px.”",
        "- “Horizontal lockup: mark left, geometric sans wordmark right, equal optical weight.”",
        "",
        "## Platform asset matrix",
        "",
        "| Asset | Size | Format | Rule |",
        "| --- | --- | --- | --- |",
    ]
    lines += [f"| {a} | {s} | {f} | {r} |" for a, s, f, r in ASSETS]
    lines += [
        "",
        "## Existing asset audit",
        "",
        *_assets(root, web),
        "",
        "## Acceptance checks",
        "",
        "- [ ] Recognisable at 16 px and at 512 px without redrawing.",
        "- [ ] Works in one colour, on light and dark, and over a photo.",
        "- [ ] Maskable icon keeps the mark inside the centre 80% safe zone.",
        "- [ ] Favicon SVG has a `viewBox`; ICO fallback exists for old clients.",
        "- [ ] Lockups use the same mark proportions as the master.",
        "- [ ] Social card carries mark + wordmark + one-line promise, readable at thumb size.",
        "- [ ] Mark is not colour-only: silhouette alone identifies it.",
        "",
        "## Agent handoff",
        "",
        "1. Present territories A–C with one sketch each; let the human choose.",
        "2. Draw the chosen mark as SVG in `public/`; add the monochrome variant.",
        "3. Export the matrix above; wire favicon, manifest and OG meta tags.",
        "4. Record the choice and its rationale in the design-system doc or an ADR.",
        "",
    ]
    report = "\n".join(lines)
    if out:
        path = Path(out)
        if not path.is_absolute():
            path = root / path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report)
        report += f"\nWrote {path}"
    return report
