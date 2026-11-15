"""Acceptance validation walkthrough for a spec: traceability + demo script.

Reads specs/<feature>/{SPEC.md, EXAMPLES.feature, WAVES.md, BACKLOG.md} and
writes VALIDATION.md containing:
- Traceability matrix: acceptance criterion -> scenarios -> wave -> items ->
  test evidence found in the repo (scenario names searched in test files).
- Coverage stats: scenarios with/without detected test evidence.
- Demo script: the happy-path scenarios ordered as a manual walkthrough.
- Gaps: scenarios with no evidence, unplanned waves, missing artifacts.

Evidence matching is literal (scenario name, case-insensitive) — absence of
a match is a prompt for the agent to verify, not proof of missing tests.
Deterministic.
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


def _test_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            p = Path(dirpath) / name
            low = name.lower()
            if any(m in low for m in ("test", "spec")) and p.suffix.lower() in (
                ".py", ".js", ".ts", ".java", ".cs", ".kt", ".go", ".rb",
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


def _ac_rows(spec_text: str):
    rows = []
    for m in _AC_ROW_RE.finditer(spec_text):
        criterion, scen_refs = m.group(1).strip(), m.group(2)
        if criterion.lower() in ("criterion", "---") or set(criterion) <= {"-", ":"}:
            continue
        refs = set(_TAG_RE.findall(scen_refs))
        rows.append({"criterion": criterion, "waves": {int(w) for w in refs}})
    return rows


def _evidence_for(name: str, test_texts: dict[Path, str]):
    """Return list of 'path:line' where scenario name appears (ci)."""
    needle = name.lower()
    hits = []
    for path, text in test_texts.items():
        for i, line in enumerate(text.splitlines(), 1):
            if needle in line.lower():
                hits.append(f"{path.name}:{i}")
                break
    return hits


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
    acs = _ac_rows(spec_f.read_text()) if spec_f.is_file() else []
    waves_text = waves_f.read_text() if waves_f.is_file() else ""
    planned_waves = {int(w) for w in _WAVE_ITEM_RE.findall(waves_text)}

    test_texts = {}
    for p in _test_files(root):
        try:
            if p.stat().st_size <= _MAX_FILE:
                test_texts[p] = p.read_text(errors="ignore")
        except OSError:
            continue

    evidence = {s["name"]: _evidence_for(s["name"], test_texts) for s in scenarios}
    covered = sum(1 for s in scenarios if evidence[s["name"]])

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
        names = [n for w in sorted(ac["waves"]) for n in scen_by_wave.get(w, [])]
        ev = []
        for n in names:
            ev += evidence.get(n, [])
        ev_str = ", ".join(sorted(set(ev))[:3]) if ev else "—"
        out.append(
            f"| {i} | {ac['criterion'][:60]} | {len(names)} "
            f"| {', '.join(f'@w{w}' for w in sorted(ac['waves'])) or '—'} | {ev_str} |"
        )
    out.append("")
    out.append("## Scenario coverage")
    out.append("")
    out.append(f"- Scenarios: {len(scenarios)} total, {covered} with detected test evidence, {len(scenarios) - covered} without")
    for s in scenarios:
        mark = "✓" if evidence[s["name"]] else "✗"
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
    if len(scenarios) - covered:
        gaps.append(f"{len(scenarios) - covered} scenario(s) lack detected test evidence — verify manually or add checks")
    out.append("## Gaps")
    out.append("")
    for g in gaps or ["none — spec is fully traced"]:
        out.append(f"- {g}")
    out.append("")
    out.append("Note: 'no evidence' means the scenario name was not found in")
    out.append("test files — verify by hand before treating it as a real gap.")

    (d / "VALIDATION.md").write_text("\n".join(out))
    return "\n".join(out)
