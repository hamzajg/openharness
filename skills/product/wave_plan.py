"""Turn a spec's BACKLOG.md + EXAMPLES.feature into an ordered WAVES.md delivery plan.

Parses the deterministic artifact contract written by `spec_scaffold`:
- BACKLOG.md items: `## B<n> — title` blocks with `- Scenarios: @wX` and
  optional `- Depends: B1, B3` lines.
- EXAMPLES.feature scenario tags (@w<N>) link examples to waves.

Emits WAVES.md: waves ordered so dependencies land in earlier-or-equal
waves, each wave independently shippable (its own branch/PR). Deterministic.
"""

import re
from pathlib import Path

from openharness.skill import skill

_ITEM_RE = re.compile(r"^##\s+(B|US)(\d+)\s*[—-]\s*(.+)$", re.M)
_SCEN_RE = re.compile(r"^-\s*Scenarios:\s*(.+)$", re.M)
_DEP_RE = re.compile(r"^-\s*Depends:\s*(.+)$", re.M)
_TAG_RE = re.compile(r"@w(\d+)")
_SCENARIO_TAG_RE = re.compile(r"@w(\d+)")


def _parse_backlog(text: str):
    """Return {id: {title, scenarios:set[int], deps:set[int], size, notes}}."""
    items = {}
    matches = list(_ITEM_RE.finditer(text))
    for i, m in enumerate(matches):
        bid = int(m.group(2))
        ref = f"{m.group(1)}{bid}"
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.end():end]
        title = m.group(3).strip()

        def field(rx):
            fm = rx.search(block)
            return fm.group(1).strip() if fm else ""

        scen = field(_SCEN_RE)
        waves = {int(w) for w in _TAG_RE.findall(scen)}
        deps_raw = field(_DEP_RE)
        deps = {int(d) for d in re.findall(r"(?:B|US)(\d+)", deps_raw)}
        size_m = re.search(r"^-\s*Size:\s*(\S+)", block, re.M)
        notes_m = re.search(r"^-\s*Notes:\s*(.*)$", block, re.M)
        items[bid] = {
            "ref": ref,
            "title": title,
            "waves": waves or {1},
            "deps": deps,
            "size": size_m.group(1).upper() if size_m else "M",
            "notes": notes_m.group(1).strip() if notes_m else "",
        }
    return items


def _feature_scenarios(text: str) -> dict[int, list[str]]:
    """Map wave number -> scenario names from .feature tags."""
    waves = {}
    lines = text.splitlines()
    current_tags = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("@"):
            current_tags = re.findall(r"@w(\d+)", stripped)
        elif stripped.startswith("Scenario:") or stripped.startswith("Scenario Outline:"):
            name = stripped.split(":", 1)[1].strip()
            for w in current_tags:
                waves.setdefault(int(w), []).append(name)
            current_tags = []
    return waves


def _assign_waves(items):
    """Compute effective wave per item: max(declared waves, dep waves + ordering).

    Simple deterministic rule: an item's wave = max(its declared @w tags,
    and for each dep, dep.wave if sizes are equal-or-smaller...). To keep
    it predictable: wave(item) = max(declared) but never earlier than the
    max wave of its deps + (0 if dep already in same wave allowed).
    We enforce deps land in strictly earlier waves — safest shipping order.
    """
    wave = {}
    # first pass: declared waves
    for bid, it in items.items():
        wave[bid] = max(it["waves"])
    # iterate to fixpoint: dep must be in earlier wave
    for _ in range(len(items) + 2):
        changed = False
        for bid, it in items.items():
            for d in it["deps"]:
                if d in wave and wave[bid] <= wave[d]:
                    wave[bid] = wave[d] + 1
                    changed = True
        if not changed:
            break
    violations = [
        (bid, d)
        for bid, it in items.items()
        for d in it["deps"]
        if d in wave and wave[bid] <= wave[d]
    ]
    return wave, violations


@skill
def wave_plan(spec_dir: str = "") -> str:
    """Generate WAVES.md for a spec dir from BACKLOG.md + EXAMPLES.feature.

    Reads <spec_dir>/BACKLOG.md and <spec_dir>/EXAMPLES.feature, resolves
    dependencies into strictly-ordered delivery waves, and writes
    <spec_dir>/WAVES.md. Each wave is an independently shippable increment
    (branch + PR). Returns the generated plan as markdown.

    Params:
      spec_dir: Path to specs/<feature>/ directory.
    """
    d = Path(spec_dir)
    if not d.is_dir():
        return f"ERROR: {spec_dir} is not a directory"
    backlog = d / "BACKLOG.md"
    feature = d / "EXAMPLES.feature"
    if not backlog.is_file():
        return f"ERROR: {backlog} not found — run spec_scaffold first"

    items = _parse_backlog(backlog.read_text())
    if not items:
        return "ERROR: no backlog items parsed — expected `## US<n> — <user story>` blocks"

    scenarios = _feature_scenarios(feature.read_text()) if feature.is_file() else {}
    waves, violations = _assign_waves(items)
    missing_deps = sorted({(bid, dep) for bid, it in items.items() for dep in it["deps"] if dep not in items})
    retag = [
        (bid, waves[bid], sorted(items[bid]["waves"]))
        for bid in items
        if waves[bid] not in items[bid]["waves"]
    ]

    by_wave = {}
    for bid, w in waves.items():
        by_wave.setdefault(w, []).append(bid)
    for w in by_wave:
        by_wave[w].sort()

    out = [f"# Waves — {d.name}", ""]
    out.append("Each wave IS an iteration: a time-boxed, independently shippable")
    out.append("increment — one branch, one PR, green tests, demoable outcome.")
    out.append("Do not start wave N+1 until wave N merges.")
    out.append("")
    if violations or missing_deps or retag:
        out.append("## Warnings")
        out.append("")
        for bid, dep in missing_deps:
            out.append(f"- {items[bid]['ref']} depends on item #{dep} which does not exist in BACKLOG.md")
        for bid, w, tags in retag:
            tagstr = ", ".join(f"@w{t}" for t in tags)
            out.append(f"- {items[bid]['ref']} lands in wave {w} but its scenarios are tagged {tagstr} — retag EXAMPLES.feature to @w{w} or adjust Depends")
        if violations:
            out.append("Dependency cycle or unresolvable ordering detected — fix BACKLOG.md:")
            for bid, dep in violations:
                out.append(f"- {items[bid]['ref']} depends on {items.get(dep,{}).get('ref','#'+str(dep))} but cannot be ordered after it")
        out.append("")
    for w in sorted(by_wave):
        bids = by_wave[w]
        scen_names = scenarios.get(w, [])
        out.append(f"## Wave {w} — iteration {w}")
        out.append("")
        if scen_names:
            out.append("Scenarios proven by this wave:")
            for s in scen_names:
                out.append(f"- {s}")
            out.append("")
        out.append("| Item | Title | Size | Deps | Notes |")
        out.append("|------|-------|------|------|-------|")
        for bid in bids:
            it = items[bid]
            deps = ", ".join(items[x]["ref"] for x in sorted(it["deps"]) if x in items) or "—"
            out.append(f"| {it['ref']} | {it['title']} | {it['size']} | {deps} | {it['notes']} |")
        out.append("")
    (d / "WAVES.md").write_text("\n".join(out))
    return "\n".join(out)
