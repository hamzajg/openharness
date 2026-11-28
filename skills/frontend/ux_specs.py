import re
from pathlib import Path

from openharness.skill import skill

# --------------------------------------------------------------------------- #
# UX spec audit.
#
# Checks the `## Experience` contract in SPEC.md against the normative guide
# (docs/frontend-page-guide.md) and ADR 0012/0013. Deterministic and advisory:
# it names a missing field or a plainly contradictory surface, it does not
# grade taste. "no evidence" means the text was not found — verify by hand.
# --------------------------------------------------------------------------- #

PATTERN_RE = re.compile(r"^(F-pattern|Z-pattern|single-column|F/Z)\b", re.I)
SURFACE_RE = re.compile(r"^(full-page|side-pane|drawer|modal|inline|n/a)\b", re.I)
TIER_RE = re.compile(r"\*\*Tier:\*\*\s*(simple|standard|domain-heavy)", re.I)
FIELD_PATTERN = re.compile(r"^\s*[-*]\s*UI pattern:\s*(.+)$", re.I | re.M)
FIELD_SURFACE = re.compile(r"^\s*[-*]\s*Navigation/overlay:\s*(.+)$", re.I | re.M)

STANDARDS = (
    "material", "apple hig", "human interface", "nn/g", "nielsen", "polaris",
    "bootstrap", "fluent", "carbon", "ant design", "tailwind",
)


def _experience(text: str):
    """Return (body, first_line_number) of the `## Experience` section."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower() == "## experience":
            body = []
            for nxt in lines[i + 1:]:
                if nxt.startswith("## "):
                    break
                body.append(nxt)
            return "\n".join(body), i + 1
    return None, None


def _tier(spec_dir: Path) -> str | None:
    domain = spec_dir / "DOMAIN.md"
    if not domain.exists():
        return None
    m = TIER_RE.search(domain.read_text(errors="ignore"))
    return m.group(1).lower() if m else None


NEGATED = re.compile(
    r"\b(?:no|not|never|without)\s+(?:a\s+|an\s+|separate\s+|new\s+)*(?:drawer|side[- ]pane|page|new route|route|modal)\b"
    r"(?:\s+or\s+(?:a\s+|an\s+)?(?:drawer|side[- ]pane|page|route|modal)\b)?",
    re.I,
)


def _mismatch(surface: str, body: str) -> str | None:
    # Drop negated mentions ("no separate route or drawer") so an inline
    # journey is not flagged for saying what it is *not*.
    t = NEGATED.sub(" ", body).lower()
    if surface == "modal" and any(
        k in t for k in ("browse", "list of", "table", "edit form", "long form", "multi-step")
    ):
        return "modal journey also describes browsing/editing a list or form — use side-pane/full-page"
    if surface == "inline" and any(k in t for k in ("drawer", "side pane", "side-pane", "new page", "navigates to")):
        return "inline journey opens a drawer or page — pick the surface the journey really uses"
    if surface == "full-page" and any(k in t for k in ("without leaving", "list stays visible", "page stays visible", "keeps the list")):
        return "full-page journey promises the list stays visible — a side-pane keeps context"
    if surface == "side-pane" and any(k in t for k in ("navigates to", "new route", "deep link only")):
        return "side-pane journey navigates to a separate route — a full-page is addressable"
    return None


def _audit(spec_dir: Path) -> list[str]:
    spec = spec_dir / "SPEC.md"
    if not spec.exists():
        return [f"[error] {spec_dir.name}: no SPEC.md"]
    text = spec.read_text(errors="ignore")
    body, line_no = _experience(text)
    name = spec.parent.name
    if body is None:
        return [f"[error] {name}: missing `## Experience` section (D019) — journey, edge states, UX bar, accessibility, UI pattern, navigation surface"]

    out: list[str] = []
    at = f"{spec.relative_to(spec_dir.parent.parent) if spec.is_relative_to(spec_dir.parent.parent) else spec}"
    low = body.lower()

    # Journey / edge states / UX bar / accessibility.
    if not any(k in low for k in ("journey", "primary flow", "step 1", "1.")):
        out.append(f"[error] {at}:{line_no} Experience has no primary journey")
    if not any(k in low for k in (
        "empty", "loading", "error", "permission", "denied", "invalid",
        "failure", "failed", "unavailable", "not found", "no session", "offline",
    )):
        out.append(f"[warn] {at}:{line_no} Experience names no edge states (empty/loading/error/denied)")
    if "accessib" not in low and "aria" not in low and "focus" not in low:
        out.append(f"[warn] {at}:{line_no} Experience has no accessibility notes")
    if "ux bar" not in low and "intuitive" not in low and "bar:" not in low:
        out.append(f"[warn] {at}:{line_no} Experience has no concrete UX bar")

    tier = _tier(spec_dir)
    surface = None

    # UI pattern.
    pm = FIELD_PATTERN.search(body)
    if not pm:
        out.append(f"[error] {at}:{line_no} missing `- UI pattern:` (ADR 0012)")
    else:
        value = pm.group(1).strip()
        token = PATTERN_RE.match(value)
        if not token:
            out.append(f"[error] {at}:{line_no} UI pattern `{value[:40]}` is not F-pattern, Z-pattern, single-column or F/Z")
        elif tier == "standard" and token.group(1).upper() == "F/Z":
            out.append(f"[warn] {at}:{line_no} standard tier should name a pattern, not the F/Z hedge")
        elif tier == "domain-heavy" and not any(s in value.lower() for s in STANDARDS):
            out.append(f"[warn] {at}:{line_no} domain-heavy tier should cite a design standard (Material, Apple HIG, NN/g, Polaris, …)")

    # Navigation surface.
    sm = FIELD_SURFACE.search(body)
    if not sm:
        out.append(f"[error] {at}:{line_no} missing `- Navigation/overlay:` (ADR 0013)")
    else:
        value = sm.group(1).strip()
        token = SURFACE_RE.match(value)
        if not token:
            out.append(f"[error] {at}:{line_no} surface `{value[:40]}` is not full-page, side-pane, modal or inline")
        else:
            surface = token.group(1).lower()
            if surface == "n/a" and "—" not in value and " - " not in value:
                out.append(f"[error] {at}:{line_no} bare `n/a` is rejected — write `n/a — <reason>`")
            if surface == "drawer":
                out.append(f"[warn] {at}:{line_no} `drawer` is an alias — prefer `side-pane` so reviewers compare features")
                surface = "side-pane"
            if surface != "n/a" and tier in ("standard", "domain-heavy"):
                rationale = value[len(token.group(1)):].strip(" —-:()")
                if len(rationale) < 12:
                    out.append(f"[error] {at}:{line_no} {tier} tier needs a rationale after the surface token")
            problem = _mismatch(surface, body)
            if problem:
                out.append(f"[warn] {at}:{line_no} experience-surface-mismatch: {problem}")

    # Behaviour cues the guide makes mandatory for the chosen surface.
    if surface and surface != "n/a":
        groups = {
            "side-pane": [("focus",), ("dirty", "unsaved")],
            "modal": [("focus",), ("escape",)],
            "full-page": [("route", "refresh", "deep link", "back", "url")],
        }.get(surface, [])
        missing = ["/".join(g) for g in groups if not any(c in low for c in g)]
        if missing:
            out.append(f"[warn] {at}:{line_no} {surface} behaviour contract does not mention: {', '.join(missing)}")

    if not out:
        out.append(f"[ok] {spec_dir.name}: Experience contract complete ({tier or 'no tier'})")
    return out


@skill
def ux_specs(spec_dir: str = "", repo_path: str = ".") -> str:
    """Audit SPEC.md `## Experience` against the frontend page guide (ADR 0012/0013).

    Checks the primary journey, edge states, UX bar, accessibility, the
    `UI pattern` and `Navigation/overlay` fields, tier depth, and advisory
    surface-mismatch cues. Deterministic and read-only. Reports
    `[ok]`, `[warn]` and `[error]` lines per spec, then a summary.

    Params:
      spec_dir: One spec directory (containing SPEC.md). Empty = all specs/*/SPEC.md.
      repo_path: Repository root when spec_dir is empty (default current dir).
    """
    root = Path(repo_path)
    if spec_dir:
        targets = [Path(spec_dir)]
    else:
        specs = root / "specs"
        targets = sorted(p.parent for p in specs.glob("*/SPEC.md")) if specs.exists() else []
    targets = [d for d in targets if d.exists()]
    if not targets:
        return f"No SPEC.md found under {spec_dir or (root / 'specs')}"

    results: list[str] = []
    errors = warns = 0
    for d in targets:
        lines = _audit(d)
        results.extend(lines)
        errors += sum(1 for l in lines if l.startswith("[error]"))
        warns += sum(1 for l in lines if l.startswith("[warn]"))

    results.append("")
    results.append(f"UX specs: {len(targets)} spec(s) · {errors} error(s) · {warns} warning(s)")
    if not errors:
        results.append("Verdict: PASS (advisory warnings do not block; a reviewer decides fit)")
    else:
        results.append("Verdict: CONCERNS — fix errors or record why each is intentional")
    return "\n".join(results)
