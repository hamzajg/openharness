"""Acceptance validation walkthrough for a spec: traceability + demo script.

Reads specs/<feature>/{SPEC.md, EXAMPLES.feature, WAVES.md, BACKLOG.md} and
writes VALIDATION.md containing:
- Traceability matrix: acceptance criterion -> scenarios -> wave -> items ->
  test evidence found in the repo (scenario names searched in test files).
- Coverage stats: scenarios with/without detected test evidence.
- Demo script: the happy-path scenarios ordered as a manual walkthrough.
- Gaps: scenarios with no evidence, unplanned waves, missing artifacts.
- Outcome follow-up: preserves optional post-release learning across reruns.

Evidence matching: literal scenario-name hits are strong; a token-overlap
match (>=50% of significant words on one test line) is reported as weak.
Absence of either is a prompt for the agent to verify, not proof of
missing tests. Deterministic.
"""

import os
import re
from pathlib import Path

from openharness.skill import skill

_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    "vendor", ".chroma", ".next", ".nuget", "bin", "obj", "target",
    ".gradle", "Pods", "specs",
}
_MAX_FILE = 512 * 1024

_AC_ROW_RE = re.compile(r"^\|\s*\d+\s*\|\s*([^|]+?)\s*\|\s*([^|]*?)\s*\|\s*$", re.M)
_TAG_RE = re.compile(r"@w(\d+)")
_ITEM_RE = re.compile(r"^##\s+(?:B|US)(\d+)\s*[—-]\s*(.+)$", re.M)
_WAVE_ITEM_RE = re.compile(r"^##\s+Wave\s+(\d+)", re.M)
_OUTCOME_SECTION_RE = re.compile(
    r"^## Outcome follow-up\s*$([\s\S]*?)(?=^## |\Z)", re.M
)


def _test_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            p = Path(dirpath) / name
            low = name.lower()
            if any(m in low for m in ("test", "spec")) and p.suffix.lower() in (
                ".py", ".js", ".jsx", ".ts", ".tsx", ".mts", ".cts",
                ".java", ".groovy", ".cs", ".kt", ".go", ".rb",
            ):
                yield p


def _scenario_index(feature_text: str):
    """Return list of {name, waves:set[int], happy:bool}."""
    out = []
    lines = feature_text.splitlines()
    pending_tags = []
    for line in lines:
        s = line.strip()
        if s.startswith("@"):
            pending_tags += _TAG_RE.findall(s)
            if "happy" in s:
                pending_tags.append("happy")
        elif s.startswith("Scenario"):
            name = s.split(":", 1)[1].strip()
            out.append({
                "name": name,
                "waves": {int(w) for w in pending_tags if w.isdigit()},
                "happy": "happy" in pending_tags,
            })
            pending_tags = []
    return out


def _cell(text: str, limit: int = 60) -> str:
    """Single-line table cell, truncated at a word boundary with ellipsis."""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:")
    return cut + "…"


def _ac_rows(spec_text: str, scenarios: list):
    """Parse the SPEC.md AC table. The Scenario(s) cell may hold @wN tags
    and/or scenario names written verbatim — names are resolved against
    EXAMPLES.feature (case-insensitive substring)."""
    rows = []
    for m in _AC_ROW_RE.finditer(spec_text):
        criterion, scen_refs = m.group(1).strip(), m.group(2)
        if criterion.lower() in ("criterion", "---") or set(criterion) <= {"-", ":"}:
            continue
        waves = {int(w) for w in _TAG_RE.findall(scen_refs)}
        cell = scen_refs.lower()
        linked = {s["name"] for s in scenarios if s["name"].lower() in cell}
        for s in scenarios:
            if s["name"] in linked:
                waves |= s["waves"]
        rows.append({"criterion": criterion, "waves": waves, "scenarios": linked})
    return rows


_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has",
    "are", "was", "were", "will", "would", "could", "should", "into",
    "only", "when", "then", "given", "she", "her", "his", "our", "your",
    "their", "they", "them", "you", "can", "per", "via", "not", "all",
    "any", "see", "shows", "show", "gets", "get", "new", "its",
}


def _tokens(name: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", name.lower())
            if len(w) >= 4 and w not in _STOPWORDS}


def _evidence_for(name: str, test_texts: dict[Path, str]):
    """Return {'strong': [...], 'weak': [...]} evidence hits.

    Strong = the full scenario name appears on a test-file line.
    Weak = one line contains >=50% of the scenario's significant tokens
    (>=2 tokens) — heuristic, reported separately, never counted as proof.
    """
    needle = name.lower()
    tokens = _tokens(name)
    strong, weak = [], []
    for path, text in test_texts.items():
        file_strong = file_weak = False
        for line in text.splitlines():
            low = line.lower()
            if needle in low:
                file_strong = True
                break
            if tokens and not file_weak:
                matched = sum(1 for t in tokens if t in low)
                if matched >= 2 and matched / len(tokens) >= 0.5:
                    file_weak = True
        if file_strong:
            strong.append(path.name)
        elif file_weak:
            weak.append(path.name)
    return {"strong": strong, "weak": weak}


@skill
def ship_validate(spec_dir: str = "", repo_path: str = ".") -> str:
    """Write VALIDATION.md — acceptance walkthrough for a spec dir.

    Produces the traceability matrix (AC -> scenarios -> wave -> items ->
    test evidence), coverage stats, a manual demo script from happy-path
    scenarios, and a gaps list. Run after waves merge; re-run anytime.

    Params:
      spec_dir: Path to specs/<feature>/.
      repo_path: Repository root used to search test files for evidence.
    """
    d = Path(spec_dir)
    if not d.is_dir():
        return f"ERROR: {spec_dir} is not a directory"
    root = Path(repo_path).resolve()

    spec_f, feat_f, waves_f = d / "SPEC.md", d / "EXAMPLES.feature", d / "WAVES.md"
    missing = [f.name for f in (spec_f, feat_f) if not f.is_file()]
    if missing:
        return f"ERROR: missing artifacts in {d}: {', '.join(missing)}"

    scenarios = _scenario_index(feat_f.read_text())
    acs = _ac_rows(spec_f.read_text(), scenarios) if spec_f.is_file() else []
    waves_text = waves_f.read_text() if waves_f.is_file() else ""
    planned_waves = {int(w) for w in _WAVE_ITEM_RE.findall(waves_text)}
    validation_f = d / "VALIDATION.md"
    previous_validation = validation_f.read_text(errors="ignore") if validation_f.is_file() else ""
    outcome_match = _OUTCOME_SECTION_RE.search(previous_validation)
    outcome_followup = outcome_match.group(1).strip() if outcome_match else ""

    test_texts = {}
    for p in _test_files(root):
        try:
            if p.stat().st_size <= _MAX_FILE:
                test_texts[p] = p.read_text(errors="ignore")
        except OSError:
            continue

    evidence = {s["name"]: _evidence_for(s["name"], test_texts) for s in scenarios}
    covered = sum(1 for s in scenarios if evidence[s["name"]]["strong"])
    weak_only = sum(1 for s in scenarios
                    if not evidence[s["name"]]["strong"] and evidence[s["name"]]["weak"])

    out = [f"# Validation — {d.name}", ""]
    out.append("## Traceability")
    out.append("")
    out.append("| AC | Criterion | Scenarios | Wave(s) | Test evidence |")
    out.append("|----|-----------|-----------|---------|---------------|")
    scen_by_wave = {}
    for s in scenarios:
        for w in s["waves"]:
            scen_by_wave.setdefault(w, []).append(s["name"])
    for i, ac in enumerate(acs, 1):
        names = set(ac.get("scenarios", ()))
        for w in sorted(ac["waves"]):
            names.update(scen_by_wave.get(w, []))
        names = sorted(names)
        strong = sorted({h for n in names for h in evidence.get(n, {}).get("strong", [])})
        weak = sorted({h for n in names for h in evidence.get(n, {}).get("weak", [])} - set(strong))
        if strong:
            ev_str = ", ".join(strong[:3])
        elif weak:
            ev_str = "(weak) " + ", ".join(weak[:2])
        else:
            ev_str = "—"
        scen_cell = ", ".join(names) if names else "—"
        wave_cell = ", ".join(str(w) for w in sorted(ac["waves"])) or "—"
        out.append(
            f"| {i} | {_cell(ac['criterion'])} | {scen_cell} "
            f"| {wave_cell} | {ev_str} |"
        )
    out.append("")
    out.append("## Scenario coverage")
    out.append("")
    out.append(f"- Scenarios: {len(scenarios)} total, {covered} with detected test evidence"
               + (f", {weak_only} with weak (token-match) evidence only" if weak_only else "")
               + f", {len(scenarios) - covered - weak_only} without")
    for s in scenarios:
        mark = "✓" if evidence[s["name"]]["strong"] else ("~" if evidence[s["name"]]["weak"] else "✗")
        waves = ", ".join(f"@w{w}" for w in sorted(s["waves"])) or "untagged"
        out.append(f"- {mark} `{s['name']}` ({waves})")
    out.append("")
    out.append("## Demo script (manual walkthrough)")
    out.append("")
    happy = [s for s in scenarios if s["happy"]] or [s for s in scenarios if s["waves"]]
    for i, s in enumerate(happy, 1):
        out.append(f"{i}. **{s['name']}** — run the app, perform the scenario, observe the outcome.")
    if not happy:
        out.append("(no happy-path scenarios tagged — tag one with @happy-path in EXAMPLES.feature)")
    out.append("")
    gaps = []
    if not waves_f.is_file():
        gaps.append("WAVES.md missing — run wave_plan")
    unproven = [w for w in sorted({w for s in scenarios for w in s['waves']}) if w not in planned_waves]
    if unproven:
        gaps.append(f"Scenario waves {', '.join(f'@w{w}' for w in unproven)} not covered by WAVES.md")
    no_evidence = [s for s in scenarios
                   if not evidence[s["name"]]["strong"] and not evidence[s["name"]]["weak"]]
    if no_evidence:
        gaps.append(f"{len(no_evidence)} scenario(s) lack detected test evidence — verify manually or add checks")
    out.append("## Gaps")
    out.append("")
    for g in gaps or ["none — spec is fully traced"]:
        out.append(f"- {g}")
    out.append("")
    out.append("Note: 'no evidence' means neither the scenario name nor a")
    out.append("token match was found in test files — verify by hand before")
    out.append("treating it as a real gap. '~' marks weak token-match evidence.")
    out += ["", "## Outcome follow-up", ""]
    if outcome_followup:
        out.append(outcome_followup)
    else:
        out += [
            "Optional; this is a post-release learning record, not a finish gate.",
            "- Status: not yet measured",
            "- Owner and review date: (record when known)",
            "- Signal and observed result: (record after release; do not invent)",
            "- Learning or next action: (record after review)",
        ]

    validation_f.write_text("\n".join(out))
    return "\n".join(out)
