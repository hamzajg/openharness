"""Product feature map: aggregate every specs/<feature>/ into a roadmap view.

Scans <repo>/specs/*/ directories and summarizes each feature: title (from
SPEC.md), backlog story count, declared waves, scenario count, and whether
WAVES.md / VALIDATION.md exist. Writes specs/PRODUCT.md — the product-level
feature plan the agent uses for sequencing features across the repo.
Deterministic.
"""

import re
from pathlib import Path

from openharness.skill import skill

_ITEM_RE = re.compile(r"^##\s+(?:B|US)\d+", re.M)
_SCENARIO_RE = re.compile(r"^\s*Scenario(?: Outline)?:", re.M)
_WAVE_RE = re.compile(r"^##\s+Wave\s+\d+", re.M)
_TITLE_RE = re.compile(r"^#\s+Spec:\s*(.+)$", re.M)


def _feature_summary(spec_dir: Path) -> dict:
    spec = spec_dir / "SPEC.md"
    title = spec_dir.name
    if spec.is_file():
        m = _TITLE_RE.search(spec.read_text(errors="ignore"))
        if m:
            title = m.group(1).strip()
    backlog = spec_dir / "BACKLOG.md"
    stories = len(_ITEM_RE.findall(backlog.read_text())) if backlog.is_file() else 0
    feature = spec_dir / "EXAMPLES.feature"
    scenarios = len(_SCENARIO_RE.findall(feature.read_text())) if feature.is_file() else 0
    waves_md = spec_dir / "WAVES.md"
    waves = len(_WAVE_RE.findall(waves_md.read_text())) if waves_md.is_file() else 0
    return {
        "dir": spec_dir.name,
        "title": title,
        "stories": stories,
        "scenarios": scenarios,
        "waves": waves,
        "planned": waves_md.is_file(),
        "validated": (spec_dir / "VALIDATION.md").is_file(),
    }


@skill
def product_map(repo_path: str = ".") -> str:
    """Write specs/PRODUCT.md — a feature map across all specs/ in a repo.

    For each specs/<feature>/ dir reports title, user-story count,
    scenario count, wave count, and planning/validation state. The output
    is the product-level roadmap: which features are specced, which are
    wave-planned, which are validated. Use for multi-feature sequencing —
    one feature ships at a time per /ship-product.

    Params:
      repo_path: Repository root containing specs/.
    """
    root = Path(repo_path).resolve()
    specs_root = root / "specs"
    if not specs_root.is_dir():
        return f"ERROR: {specs_root} not found — run spec_scaffold first"

    feats = [_feature_summary(d) for d in sorted(specs_root.iterdir()) if d.is_dir()]
    if not feats:
        return f"ERROR: no feature dirs under {specs_root}"

    out = ["# Product Map", ""]
    out.append("| Feature | Stories | Scenarios | Waves | Planned | Validated |")
    out.append("|---------|---------|-----------|-------|---------|-----------|")
    for f in feats:
        out.append(
            f"| {f['title']} (`{f['dir']}/`) | {f['stories']} | {f['scenarios']} "
            f"| {f['waves']} | {'yes' if f['planned'] else 'no'} "
            f"| {'yes' if f['validated'] else 'no'} |"
        )
    out.append("")
    unplanned = [f["dir"] for f in feats if not f["planned"]]
    unvalidated = [f["dir"] for f in feats if f["planned"] and not f["validated"]]
    if unplanned:
        out.append(f"Specced but not wave-planned: {', '.join(unplanned)}")
    if unvalidated:
        out.append(f"Planned but not validated: {', '.join(unvalidated)}")
    out.append("")
    out.append("Rule: ship ONE feature at a time — finish its waves and")
    out.append("validation before starting the next spec dir.")

    (specs_root / "PRODUCT.md").write_text("\n".join(out))
    return "\n".join(out)
