"""Delivery-loop controller: turn the /ship-product playbook into a repeatable loop.

The loop is AGENT-DRIVEN (D001): the harness never launches an agent or a
scheduler. This skill is the deterministic oracle the agent calls once per
iteration — it reads the spec artifacts plus its own run log and answers
"what is the next action?" (frame, spec, plan, wave N, validate, done) or
"blocked/stop". It also records wave outcomes so a loop survives context
loss and session restarts.

State lives in `specs/<feature>/LOOP.md` next to the spec it describes:
a status line, an iteration counter, a wave table, and an append-only event
log — the human/PR-facing rendering. `LOOP.state.json` next to it is the
machine-readable projection (same state, written atomically by the same
`_save_state` call; never hand-edit either). WAVES.md stays the immutable
plan; LOOP.* is the mutable execution record. All are product artifacts
committed with the PRs.

Deterministic; stdlib only.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from openharness.skill import SkillError, skill

_WAVE_RE = re.compile(r"^##\s+Wave\s+(\d+)\b.*$", re.M)
_SCENARIO_RE = re.compile(r"^\s*Scenario(?: Outline)?:\s*(.+?)\s*$")
_TAG_RE = re.compile(r"@w(\d+)")
_ITEM_ROW_RE = re.compile(r"^\|\s*((?:US|B)\d+)\s*\|\s*([^|]*?)\s*\|", re.M)
_STATE_ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*([a-z-]+)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|"
    r"\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*$",
    re.M,
)
_STATUS_RE = re.compile(r"^Status:\s*(\S+)\s*$", re.M)
_ITER_RE = re.compile(r"^Iterations:\s*(\d+)\s*$", re.M)
_GATE_RE = re.compile(r"^##\s+(G\d+)\s*[—-]\s*(.+)$", re.M)
_GATE_STATE_RE = re.compile(
    r"^\|\s*(G\d+)\s*\|\s*([a-z-]+)\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*$",
    re.M,
)
_WAVE_STATUSES = ("pending", "in-progress", "done")
_FEATURE_STATUSES = ("running", "blocked", "done")
_GATE_STATUSES = ("pending", "met", "waived", "failed")
_GATE_PHASES = ("spec", "plan", "validate", "finish")
_GATE_TYPES = ("decision", "artifact", "external", "technical", "quality", "data")
_AGENT_GATE_TYPES = ("artifact", "technical", "data")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean(value: str, limit: int = 120) -> str:
    value = " ".join(str(value).split()).replace("|", "/")
    return value[:limit]


# ---------------------------------------------------------------- artifacts

def _feature_dirs(root: Path) -> list[Path]:
    specs = root / "specs"
    if not specs.is_dir():
        return []
    return [
        d for d in sorted(specs.iterdir())
        if d.is_dir() and not d.name.startswith(".")
    ]


def _read(path: Path) -> str:
    try:
        return path.read_text(errors="ignore")
    except OSError:
        return ""


def _parse_waves(spec_dir: Path) -> dict[int, dict]:
    """Wave number -> {scenarios, items} from WAVES.md + EXAMPLES.feature."""
    waves: dict[int, dict] = {}
    for m in _WAVE_RE.finditer(_read(spec_dir / "WAVES.md")):
        waves[int(m.group(1))] = {"scenarios": [], "items": []}

    # Scenario names grouped by @w<N> tag.
    tagged: dict[int, list[str]] = {}
    pending: list[int] = []
    for line in _read(spec_dir / "EXAMPLES.feature").splitlines():
        s = line.strip()
        if s.startswith("@"):
            pending = [int(w) for w in _TAG_RE.findall(s)]
        elif _SCENARIO_RE.match(s):
            name = _SCENARIO_RE.match(s).group(1)
            for w in pending:
                tagged.setdefault(w, []).append(name)
            pending = []

    # Item rows inside each wave section.
    sections = list(_WAVE_RE.finditer(_read(spec_dir / "WAVES.md")))
    for i, m in enumerate(sections):
        w = int(m.group(1))
        end = sections[i + 1].start() if i + 1 < len(sections) else len(_read(spec_dir / "WAVES.md"))
        block = _read(spec_dir / "WAVES.md")[m.end():end]
        for row in _ITEM_ROW_RE.finditer(block):
            waves[w]["items"].append(f"{row.group(1)} — {row.group(2)}")

    for w, data in waves.items():
        data["scenarios"] = tagged.get(w, [])
    return dict(sorted(waves.items()))


def _load_state(spec_dir: Path) -> dict:
    state_file = spec_dir / "LOOP.state.json"
    if state_file.is_file():
        try:
            data = json.loads(state_file.read_text())
            status = data.get("status")
            return {
                "status": status if status in _FEATURE_STATUSES else "running",
                "iterations": int(data.get("iterations", 0)),
                "waves": {int(k): v for k, v in data.get("waves", {}).items()},
                "gates": data.get("gates", {}),
                "events": data.get("events", []),
            }
        except (OSError, ValueError, TypeError):
            pass  # corrupt/missing JSON — fall back to the markdown record
    text = _read(spec_dir / "LOOP.md")
    status = (_STATUS_RE.search(text).group(1) if _STATUS_RE.search(text) else "running")
    iterations = int(_ITER_RE.search(text).group(1)) if _ITER_RE.search(text) else 0
    if status not in _FEATURE_STATUSES:
        status = "running"
    waves = {}
    for m in _STATE_ROW_RE.finditer(text):
        w = int(m.group(1))
        waves[w] = {
            "status": m.group(2) if m.group(2) in _WAVE_STATUSES else "pending",
            "branch": m.group(3),
            "pr": m.group(4),
            "evidence": m.group(5),
            "updated": m.group(6),
        }
    events = []
    if "## Events" in text:
        events = [
            line[2:].strip()
            for line in text.split("## Events", 1)[1].splitlines()
            if line.startswith("- ") and line[2:].strip() != "(none)"
        ]
    gates = {}
    for m in _GATE_STATE_RE.finditer(text):
        gates[m.group(1).upper()] = {
            "status": m.group(2) if m.group(2) in _GATE_STATUSES else "pending",
            "evidence": m.group(3),
            "updated": m.group(4),
        }
    return {
        "status": status,
        "iterations": iterations,
        "waves": waves,
        "gates": gates,
        "events": events,
    }


def _save_state(spec_dir: Path, state: dict) -> None:
    numbers = sorted(set(state["waves"]) | set(_parse_waves(spec_dir)))
    out = [
        f"# Delivery Loop — {spec_dir.name}",
        "",
        f"Status: {state['status']}",
        f"Iterations: {state['iterations']}",
        f"Updated: {_now()}",
        "",
        "| Wave | Status | Branch | PR | Evidence | Updated |",
        "|------|--------|--------|----|----------|---------|",
    ]
    for w in numbers:
        row = state["waves"].get(w, {})
        out.append(
            f"| {w} | {row.get('status', 'pending')} | {row.get('branch', '—')} "
            f"| {row.get('pr', '—')} | {row.get('evidence', '—')} "
            f"| {row.get('updated', '—')} |"
        )
    gate_numbers = sorted(
        set(state.get("gates", {})) | set(_parse_gates(spec_dir)),
        key=lambda g: int(g[1:]) if g[1:].isdigit() else 10**6,
    )
    if gate_numbers:
        out += [
            "",
            "## Gates",
            "",
            "| Gate | Status | Evidence | Updated |",
            "|------|--------|----------|---------|",
        ]
        for gid in gate_numbers:
            row = state["gates"].get(gid, {})
            out.append(
                f"| {gid} | {row.get('status', 'pending')} "
                f"| {row.get('evidence', '—')} | {row.get('updated', '—')} |"
            )
    out += ["", "## Events", ""]
    out += [f"- {e}" for e in state["events"][-200:]] or ["- (none)"]
    (spec_dir / "LOOP.md").write_text("\n".join(out) + "\n")

    payload = {
        "feature": spec_dir.name,
        "status": state["status"],
        "iterations": state["iterations"],
        "updated": _now(),
        "waves": {str(w): state["waves"][w] for w in sorted(state["waves"])},
        "gates": state.get("gates", {}),
        "events": state["events"][-200:],
    }
    tmp = spec_dir / "LOOP.state.json.tmp"
    tmp.write_text(json.dumps(payload, indent=2) + "\n")
    tmp.replace(spec_dir / "LOOP.state.json")


def _wave(state: dict, n: int) -> dict:
    return state["waves"].setdefault(
        n, {"status": "pending", "branch": "—", "pr": "—", "evidence": "—", "updated": "—"}
    )


def _gate(state: dict, gid: str) -> dict:
    return state["gates"].setdefault(
        gid, {"status": "pending", "evidence": "—", "updated": "—"}
    )


def _event(state: dict, text: str) -> None:
    state["events"].append(f"{_now()} {text}")


# --------------------------------------------------------------------- gates

def _field(block: str, name: str, default: str = "") -> str:
    m = re.search(rf"^-\s*{re.escape(name)}:\s*(.*)$", block, re.M | re.I)
    return m.group(1).strip() if m else default


def _normalize_before(raw: str) -> tuple[str, bool]:
    value = raw.strip().lower()
    if value in _GATE_PHASES:
        return value, True
    m = re.match(r"^(?:wave|w)[:\s]*(\d+)$", value)
    if m:
        return f"wave:{int(m.group(1))}", True
    return raw.strip(), False


def _parse_gates(spec_dir: Path) -> dict[str, dict]:
    """Gate definitions from GATES.md, keyed by id (G1, G2, ...)."""
    text = _read(spec_dir / "GATES.md")
    gates: dict[str, dict] = {}
    matches = list(_GATE_RE.finditer(text))
    for i, m in enumerate(matches):
        gid = m.group(1).upper()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[m.end():end]
        gtype = _field(block, "Type", "decision").lower()
        if gtype not in _GATE_TYPES:
            gtype = "decision"
        resolver = _field(block, "Resolver", "").lower()
        if resolver not in ("agent", "human"):
            resolver = "agent" if gtype in _AGENT_GATE_TYPES else "human"
        blocking_raw = _field(block, "Blocking", "yes").lower()
        before, valid = _normalize_before(_field(block, "Before", "spec"))
        gates[gid] = {
            "id": gid,
            "title": m.group(2).strip(),
            "before": before,
            "before_valid": valid,
            "type": gtype,
            "owner": _field(block, "Owner", "unassigned"),
            "resolver": resolver,
            "blocking": blocking_raw not in ("no", "false", "advisory"),
            "check": _field(block, "Check", "manual").strip(),
            "why": _field(block, "Why", ""),
        }
    return gates


def _gate_effective(gate: dict, state: dict, root: Path) -> tuple[str, str]:
    """(effective status, evidence) — `stale` means met but evidence vanished."""
    row = state["gates"].get(gate["id"], {})
    status = row.get("status", "pending")
    evidence = row.get("evidence", "—")
    if status == "waived":
        return "waived", evidence
    if status == "met" and gate["check"].lower().startswith("file:"):
        rel = gate["check"].split(":", 1)[1].strip()
        if not rel or not (root / rel).exists():
            return "stale", evidence
    if status in ("met", "failed"):
        return status, evidence
    return "pending", evidence


def _phase_rank(phase: str) -> int:
    if phase == "spec":
        return 10
    if phase == "plan":
        return 20
    if phase.startswith("wave:"):
        try:
            return 30 + int(phase.split(":", 1)[1])
        except ValueError:
            return 30
    if phase == "validate":
        return 1000
    if phase == "finish":
        return 1001
    return 10**6


def _blocking_gates(spec_dir: Path, state: dict, phase: str, root: Path) -> list[tuple[dict, str]]:
    """Blocking gates due at or before `phase` that are not met/waived.

    Overdue gates keep blocking: filling artifacts out of order must not let a
    pending `Before: spec` gate slip past by jumping straight to a wave.
    """
    out = []
    limit = _phase_rank(phase)
    for gate in _parse_gates(spec_dir).values():
        if not gate["blocking"]:
            continue
        if not gate["before_valid"]:
            out.append((gate, "invalid"))
            continue
        if _phase_rank(gate["before"]) > limit:
            continue
        status, _ = _gate_effective(gate, state, root)
        if status in ("pending", "failed", "stale"):
            out.append((gate, status))
    return out


def _phase_label(phase: str) -> str:
    if phase.startswith("wave:"):
        return f"starting wave {phase.split(':', 1)[1]}"
    return {
        "spec": "writing the spec",
        "plan": "planning waves",
        "validate": "validation",
        "finish": "closing the feature",
    }.get(phase, phase)


def _gate_directive(root: Path, spec_dir: Path, phase: str, blocking: list[tuple[dict, str]]) -> str:
    rel = _rel(root, spec_dir)
    overdue = any(
        gate["before_valid"] and _phase_rank(gate["before"]) < _phase_rank(phase)
        for gate, _ in blocking
    )
    suffix = " (including overdue)" if overdue else ""
    lines = [
        f"GATE: {len(blocking)} blocking precondition(s) before {_phase_label(phase)}"
        f"{suffix} — {spec_dir.name}",
        "",
    ]
    for gate, status in blocking:
        lines.append(f"- {gate['id']} — {gate['title']}  [{status}]")
        lines.append(
            f"  before {gate['before']} · {gate['type']} · owner {gate['owner']} "
            f"· resolver {gate['resolver']} · check {gate['check']}"
        )
        if gate["why"]:
            lines.append(f"  why: {gate['why']}")
        if status == "invalid":
            lines.append(
                f"  fix: set `- Before:` to spec|plan|wave:<n>|validate|finish "
                f"in `{rel}/GATES.md`"
            )
        elif status == "stale":
            lines.append("  fix: the evidence file is gone — restore it or re-record the gate")
        elif gate["resolver"] == "agent":
            hint = "create the artifact" if gate["type"] in ("artifact", "data") else "run the check"
            lines.append(f"  next (agent): {hint}, then record it:")
            lines.append(
                f"    python -m openharness run ship_loop --action=gate --spec_dir={rel} "
                f"--gate={gate['id']} --status=met --evidence=\"<path or command output>\""
            )
        else:
            lines.append("  next (human): stop and hand this back:")
            lines.append(
                f"    python -m openharness run ship_loop --action=block --spec_dir={rel} "
                f"--note=\"{gate['id']}: <what the human must decide or provide>\""
            )
        lines.append("")
    lines += [
        "Resolve agent-owned gates inline; block for human-owned gates. A waiver is",
        "a human decision and must be recorded, never assumed:",
        "  python -m openharness run ship_loop --action=gate --gate=<G> "
        "--status=waived --waived-by=\"<name>\" --note=\"<reason>\"",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------ decisions

def _phase_guidance(root: Path) -> str:
    return "\n".join([
        "# Delivery loop — no specs yet",
        "",
        "NEXT: frame the first feature (ship-product phases 1–5).",
        "",
        "1. Facts: `python -m openharness run discover_product --repo_path="
        f"{root}`",
        "2. Read the report + README; propose 3–5 feature themes and score",
        "   value × feasibility × differentiation. In autonomous mode pick the",
        "   highest score and record the choice in SPEC.md → Decisions.",
        "3. Scaffold: `python -m openharness run spec_scaffold --repo_path="
        f"{root} --feature=\"<name>\"`",
        "4. Fill SPEC.md (incl. `## Decisions` — every one-way-door choice,",
        "   options + simplest/reversible alternative, consequences),",
        "   EXAMPLES.feature (@w<N> tags) and BACKLOG.md (user stories, one",
        "   `## US<n> — ...` block each). Keep the scaffold's G1 gate.",
        "5. Challenge the decisions: `challenge_decision --spec_dir=<dir> --write`,",
        "   decision-challenger fills DECISION-REVIEW.md, record gate G1 met.",
        "6. `python -m openharness run wave_plan --spec_dir="
        f"{root}/specs/<feature>` (after G1 is met and SPEC-AUDIT passes).",
        "",
        "Then call `ship_loop --action=next` again to start wave 1.",
    ])


def _rel(root: Path, spec_dir: Path) -> str:
    return str(spec_dir.relative_to(root)) if root in spec_dir.parents else str(spec_dir)


def _wave_brief(root: Path, spec_dir: Path, state: dict, n: int, waves: dict) -> str:
    rel = _rel(root, spec_dir)
    lines = [f"NEXT: implement wave {n} — {spec_dir.name}", ""]
    items = waves[n]["items"]
    scenarios = waves[n]["scenarios"]
    if scenarios:
        lines.append("Scenarios proven by this wave:")
        lines += [f"- {s}" for s in scenarios]
        lines.append("")
    if items:
        lines.append("Backlog items:")
        lines += [f"- {i}" for i in items]
        lines.append("")
    lines += [
        "Protocol:",
        f"1. Branch `feat/{spec_dir.name}-w{n}` from the default branch.",
        "2. Write the failing checks first — the scenarios above are the",
        "   acceptance spec; tests cite their names.",
        "3. Implement minimally, matching repo conventions (KISS). If the",
        "   wave introduces a new one-way-door decision (schema, public",
        "   contract, service/module boundary, persistence model), record it",
        "   in SPEC.md → Decisions and run /challenge-decision BEFORE coding;",
        "   a REVISE verdict shapes this wave's scope.",
        "4. Verify locally: build + tests green.",
        "5. One commit series, one PR; wait for CI.",
        "6. Record the outcome:",
        f"   `python -m openharness run ship_loop --action=complete --spec_dir={rel} "
        f"--wave={n} --pr=\"#<n>\" --note=\"<tests N/N, CI green>\"`",
        "",
        "Before implementing, mark it in progress:",
        f"   `python -m openharness run ship_loop --action=start --spec_dir={rel} --wave={n}`",
    ]
    return "\n".join(lines)


def _validate_brief(root: Path, spec_dir: Path) -> str:
    rel = _rel(root, spec_dir)
    return "\n".join([
        f"NEXT: validate {spec_dir.name} (ship-product phase 7)",
        "",
        f"1. `python -m openharness run ship_validate --spec_dir={rel} "
        f"--repo_path={root}`",
        "2. Walk VALIDATION.md's demo script by hand; close real gaps",
        "   (missing checks, unproven scenarios) before declaring done.",
        "3. Refresh the product map:",
        f"   `python -m openharness run product_map --repo_path={root}`",
        "4. Update README/AGENTS.md for what shipped, then mark the feature:",
        f"   `python -m openharness run ship_loop --action=finish --spec_dir={rel}`",
    ])


_AUDIT_VERDICT_RE = re.compile(
    r"^AUDIT:\s*(PASS|CONCERNS|BLOCK)\s*$", re.M | re.I
)


def _audit_status(spec_dir: Path, filename: str) -> str:
    """Review artifact status: missing | unverified | pass | concerns | block.

    `unverified` means the deterministic brief exists but no reviewer filled a
    single-value verdict. The template line (`AUDIT: PASS | CONCERNS | BLOCK`)
    does not count.
    """
    path = spec_dir / filename
    if not path.is_file():
        return "missing"
    match = _AUDIT_VERDICT_RE.search(_read(path))
    return match.group(1).lower() if match else "unverified"


def _audit_brief(root: Path, spec_dir: Path, phase: str, status: str) -> str:
    rel = _rel(root, spec_dir)
    filename = "SPEC-AUDIT.md" if phase == "spec" else "DELIVERY-AUDIT.md"
    why = (
        f"`{rel}/{filename}` is missing"
        if status == "missing"
        else f"`{rel}/{filename}` has no filled verdict"
    )
    lines = [
        f"NEXT: audit the {phase} for {spec_dir.name}",
        "",
        f"{why}. The loop runs with `--review=required`.",
        "",
        "1. Build the deterministic evidence brief:",
        f"   `python -m openharness run review_delivery --repo_path={root} "
        f"--spec_dir={rel} --phase={phase} --write`",
        "2. Give the brief to the `delivery-auditor` subagent. It re-verifies",
        "   every finding against the code, checks the tests assert the",
        "   scenarios, and fills `AUDIT: PASS|CONCERNS|BLOCK`.",
        "3. Fix every confirmed blocker, then re-run and re-audit.",
        "",
        "A `BLOCK` verdict stops the loop. `PASS` or `CONCERNS` lets it",
        "continue; `CONCERNS` must be explicitly accepted.",
    ]
    return "\n".join(lines)


def _audit_block_brief(root: Path, spec_dir: Path, phase: str) -> str:
    rel = _rel(root, spec_dir)
    filename = "SPEC-AUDIT.md" if phase == "spec" else "DELIVERY-AUDIT.md"
    return "\n".join([
        f"AUDIT-BLOCK: {spec_dir.name} — the {phase} audit says BLOCK",
        "",
        f"Read `{rel}/{filename}`. Fix every confirmed blocker, then re-run",
        f"`python -m openharness run ship_validate --spec_dir={rel} "
        f"--repo_path={root}` (delivery) and",
        f"`python -m openharness run review_delivery --repo_path={root} "
        f"--spec_dir={rel} --phase={phase} --write`,",
        "and have the `delivery-auditor` re-review.",
        "",
        "The loop will not continue while the audit says BLOCK. Do not edit",
        "the verdict by hand; fix the delivery or the spec.",
    ])


def _decide(
    root: Path, spec_dir: Path, state: dict, waves: dict,
    review: str = "required",
) -> str:
    missing = [
        name for name in ("SPEC.md", "EXAMPLES.feature", "BACKLOG.md")
        if not (spec_dir / name).is_file()
    ]
    if missing:
        blocked = _blocking_gates(spec_dir, state, "spec", root)
        if blocked:
            return _gate_directive(root, spec_dir, "spec", blocked)
        return "\n".join([
            f"NEXT: complete the spec for {spec_dir.name}",
            "",
            f"Missing: {', '.join(missing)}",
            f"Run `python -m openharness run spec_scaffold --repo_path={root} "
            f"--feature=\"{spec_dir.name}\"` (existing files are kept), then fill",
            "the artifacts: problem/users/scope/acceptance criteria in SPEC.md,",
            "observable Gherkin scenarios with @w<N> tags in EXAMPLES.feature,",
            "and user stories in BACKLOG.md.",
        ])
    if not waves:
        blocked = _blocking_gates(spec_dir, state, "plan", root)
        if blocked:
            return _gate_directive(root, spec_dir, "plan", blocked)
        if review == "required":
            status = _audit_status(spec_dir, "SPEC-AUDIT.md")
            if status in ("missing", "unverified"):
                return _audit_brief(root, spec_dir, "spec", status)
            if status == "block":
                return _audit_block_brief(root, spec_dir, "spec")
        return "\n".join([
            f"NEXT: plan waves for {spec_dir.name}",
            "",
            f"`python -m openharness run wave_plan --spec_dir="
            f"{spec_dir.relative_to(root) if root in spec_dir.parents else spec_dir}`",
            "",
            "Fix any dependency/retag warnings in BACKLOG.md, re-run until clean.",
        ])

    for n in sorted(waves):
        if _wave(state, n)["status"] == "in-progress":
            return "\n".join([
                f"NEXT: resume wave {n} — {spec_dir.name}",
                "",
                "The wave is recorded in progress. Re-read the branch/PR in",
                f"`{spec_dir.name}/LOOP.md`, finish the checks, then record the",
                "outcome with `--action=complete` (or `--action=block` if stuck).",
                "",
                _wave_brief(root, spec_dir, state, n, waves),
            ])

    pending = [n for n in sorted(waves) if _wave(state, n)["status"] != "done"]
    if pending:
        phase = f"wave:{pending[0]}"
        blocked = _blocking_gates(spec_dir, state, phase, root)
        if blocked:
            return _gate_directive(root, spec_dir, phase, blocked)
        if review == "required" and not any(
            _wave(state, w)["status"] == "done" for w in waves
        ):
            # The spec audit is a precondition for wave 1, not only for
            # planning: a plan written without it must not reach code.
            audit = _audit_status(spec_dir, "SPEC-AUDIT.md")
            if audit in ("missing", "unverified"):
                return _audit_brief(root, spec_dir, "spec", audit)
            if audit == "block":
                return _audit_block_brief(root, spec_dir, "spec")
        return _wave_brief(root, spec_dir, state, pending[0], waves)

    if not (spec_dir / "VALIDATION.md").is_file():
        blocked = _blocking_gates(spec_dir, state, "validate", root)
        if blocked:
            return _gate_directive(root, spec_dir, "validate", blocked)
        return _validate_brief(root, spec_dir)

    blocked = _blocking_gates(spec_dir, state, "finish", root)
    if blocked:
        return _gate_directive(root, spec_dir, "finish", blocked)
    if review == "required":
        status = _audit_status(spec_dir, "DELIVERY-AUDIT.md")
        if status in ("missing", "unverified"):
            return _audit_brief(root, spec_dir, "delivery", status)
        if status == "block":
            return _audit_block_brief(root, spec_dir, "delivery")
    return "FEATURE-DONE"


def _summary(
    root: Path, spec_dir: Path, state: dict, waves: dict, budget: int,
    review: str = "required",
) -> str:
    done = sum(1 for w in waves if _wave(state, w)["status"] == "done")
    progress = sum(1 for w in waves if _wave(state, w)["status"] == "in-progress")
    gates = _parse_gates(spec_dir)
    gate_text = ""
    if gates:
        met = sum(
            1 for g in gates.values()
            if _gate_effective(g, state, root)[0] in ("met", "waived")
        )
        pending = sum(
            1 for g in gates.values()
            if g["blocking"] and _gate_effective(g, state, root)[0] in ("pending", "failed", "stale")
        )
        gate_text = f" · gates {met}/{len(gates)} met"
        if pending:
            gate_text += f" ({pending} blocking pending)"
    review_text = ""
    if review == "required":
        spec = _audit_status(spec_dir, "SPEC-AUDIT.md")
        delivery = _audit_status(spec_dir, "DELIVERY-AUDIT.md")
        review_text = f" · review spec:{spec} delivery:{delivery}"
    return (
        f"Feature: `{spec_dir.name}` · status {state['status']} · "
        f"iteration {state['iterations']}/{budget} · "
        f"waves {done}/{len(waves)} done"
        + (f", {progress} in progress" if progress else "")
        + gate_text
        + review_text
    )


# --------------------------------------------------------------------- skill

@skill
def ship_loop(
    repo_path: str = ".",
    spec_dir: str = "",
    action: str = "next",
    wave: int = 0,
    note: str = "",
    pr: str = "",
    branch: str = "",
    gate: str = "",
    status: str = "",
    evidence: str = "",
    waived_by: str = "",
    max_iterations: int = 25,
    review: str = "required",
    force: bool = False,
    offline: bool = False,
) -> str:
    """Drive one delivery-loop iteration: report the next action and record wave/gate outcomes.

    Actions: `next` (default; increments the iteration counter and prints the
    next action or DONE/BLOCKED/GATE/STOP), `status` (same without incrementing),
    `start` (mark a wave in progress), `complete` (mark it done with evidence),
    `gate` (record a precondition as met/waived/failed/pending), `block` (stop
    the loop with a reason), `resume` (clear blocked), `reset` (clear wave
    state), `finish` (mark a validated feature done), `reconcile` (alias
    `check`; compare LOOP's claims with git and GitHub and raise on drift).

    Gates are preconditions declared in `specs/<feature>/GATES.md`; their
    status is recorded in `LOOP.md`. A blocking gate prevents the phase it is
    attached to (`spec`, `plan`, `wave:<n>`, `validate`, `finish`).

    State is `specs/<feature>/LOOP.md`; the plan stays in WAVES.md. The agent
    executes the action — the harness never launches agents (D001).

    Params:
      repo_path: Repository root containing specs/.
      spec_dir: Feature dir; defaults to the first unfinished feature.
      action: next|status|start|complete|gate|block|resume|reset|finish|reconcile.
      wave: Wave number for start/complete/reset.
      note: Evidence (complete), reason (block), or waiver/failure reason (gate).
      pr: PR reference recorded on complete.
      branch: Branch name recorded on start (default feat/<feature>-w<N>).
      gate: Gate id for `gate` (e.g. G1).
      status: Gate status for `gate`: pending|met|waived|failed.
      evidence: Proof recorded when a gate is marked met.
      waived_by: Human who approved a waiver (required with `--status=waived`).
      max_iterations: Hard stop after this many `next` calls (default 25).
      review: `required` (default) or `advisory`. When required, the loop
        refuses to plan waves until `SPEC-AUDIT.md` has a filled verdict,
        refuses to start wave 1 until the spec audit passes, and refuses to
        finish until `DELIVERY-AUDIT.md` has one. A `BLOCK` verdict stops
        the loop. `advisory` keeps existing loops working and never
        enforces the audit.
      force: Allow out-of-order start/complete or a full reset.
      offline: For `reconcile` only — check git facts and skip GitHub, so
        PR/CI claims are reported as unverified instead of quietly assumed.
    """
    budget = max(1, int(max_iterations))
    if review not in ("advisory", "required"):
        return "ERROR: --review must be advisory|required"
    root = Path(repo_path).resolve()
    if not root.is_dir():
        return f"ERROR: {repo_path} is not a directory"
    if action not in (
        "next", "status", "start", "complete", "gate",
        "block", "resume", "reset", "finish", "reconcile", "check",
    ):
        return (
            f"ERROR: unknown action {action!r} "
            "(next|status|start|complete|gate|block|resume|reset|finish|reconcile)"
        )

    dirs = _feature_dirs(root)
    explicit = bool(spec_dir)
    if explicit:
        d = Path(spec_dir)
        if not d.is_absolute():
            d = (root / d).resolve()
        if not d.is_dir():
            return f"ERROR: spec_dir {spec_dir} not found"
        dirs = [d]
    elif not dirs:
        return _phase_guidance(root)

    if action != "next" and action != "status":
        d = dirs[0] if explicit else next(
            (x for x in dirs if _load_state(x)["status"] != "done"), dirs[0]
        )
        state = _load_state(d)
        waves = _parse_waves(d)

        if action in ("reconcile", "check"):
            # Read-only: the record is the claim, git and GitHub are the truth.
            from openharness import verify

            findings = verify.reconcile(
                repo=root,
                wave_state=state["waves"],
                plan_waves=sorted(waves),
                feature_status=state["status"],
                offline=offline,
            )
            info = [f for f in findings if f.severity == "info"]
            warnings = [f for f in findings if f.severity == "warning"]
            drift = [f for f in findings if f.severity == "drift"]
            unverified = [f for f in findings if f.severity == "unverified"]

            report = [
                f"# Reconcile — {d.name}",
                "",
                "Facts: git + GitHub. Claims: LOOP.md / LOOP.state.json. Nothing was written.",
                "",
            ]
            if info:
                report.extend(f.render() for f in info)
            elif not drift and not unverified:
                report.append("- no completed or in-progress wave to check")
            if warnings:
                report += ["", "True right now, not drift:"]
                report.extend(f.render() for f in warnings)

            if not drift and not unverified:
                report += ["", "OK — LOOP state matches git and GitHub."]
                return "\n".join(report)

            report.append("")
            if drift:
                report.append(f"DRIFT ({len(drift)}) — the record contradicts reality:")
                report.extend(f.render() for f in drift)
                report.append("")
            if unverified:
                report.append(f"UNVERIFIED ({len(unverified)}) — reality could not be checked:")
                report.extend(f.render() for f in unverified)
                report.append("")
            waves_in_drift = sorted(
                int(f.subject.split()[1])
                for f in drift
                if f.subject.startswith("wave ") and f.subject.split()[1].isdigit()
            )
            if waves_in_drift:
                resets = ", ".join(f"--action=reset --wave={n}" for n in waves_in_drift)
                report.append(
                    f"Fix the record (`{resets}`, then redo the wave) or the world "
                    "(merge the PR, push the branch), then reconcile again."
                )
            else:
                report.append(
                    "Fix the record or the world, then reconcile again."
                )
            raise SkillError("\n".join(report))

        if action == "gate":
            gates = _parse_gates(d)
            gid = gate.strip().upper()
            if not gid:
                return "ERROR: --gate is required (e.g. --gate=G1)"
            if gid not in gates:
                return f"ERROR: gate {gid} is not defined in {_rel(root, d)}/GATES.md"
            if status not in _GATE_STATUSES:
                return "ERROR: --status must be pending|met|waived|failed"
            g = gates[gid]
            row = _gate(state, gid)
            if status == "met":
                if not evidence.strip():
                    return "ERROR: --evidence is required to mark a gate met"
                if g["check"].lower().startswith("file:"):
                    rel = g["check"].split(":", 1)[1].strip()
                    if not rel or not (root / rel).exists():
                        return f"ERROR: evidence file `{rel}` does not exist — create it first"
                row.update({"status": "met", "evidence": _clean(evidence), "updated": _now()})
                _event(state, f"gate {gid} met: {_clean(evidence)}")
            elif status == "waived":
                if not waived_by.strip() or not note.strip():
                    return "ERROR: --waived-by and --note (reason) are required to waive a gate"
                row.update({
                    "status": "waived",
                    "evidence": _clean(f"waived by {waived_by}: {note}"),
                    "updated": _now(),
                })
                _event(state, f"gate {gid} waived by {_clean(waived_by)}: {_clean(note)}")
            elif status == "failed":
                reason = note.strip() or evidence.strip()
                if not reason:
                    return "ERROR: --note or --evidence is required to mark a gate failed"
                row.update({"status": "failed", "evidence": _clean(reason), "updated": _now()})
                _event(state, f"gate {gid} failed: {_clean(reason)}")
            else:
                row.update({"status": "pending", "evidence": "—", "updated": _now()})
                _event(state, f"gate {gid} reset to pending")
            _save_state(d, state)
            return (
                f"Gate {gid} {status}.\n\n" + _summary(root, d, state, waves, budget, review)
                + "\n\n" + _decide(root, d, state, waves, review)
            )

        if action == "start":
            if not wave:
                return "ERROR: --wave is required"
            if not waves:
                return "ERROR: WAVES.md has no waves — run wave_plan first"
            if wave not in waves:
                return f"ERROR: wave {wave} is not in WAVES.md ({', '.join(map(str, waves))})"
            for earlier in sorted(w for w in waves if w < wave):
                if _wave(state, earlier)["status"] != "done" and not force:
                    return f"ERROR: wave {earlier} is not done — finish it first (or --force)"
            blocked = _blocking_gates(d, state, f"wave:{wave}", root)
            if blocked:
                return _gate_directive(root, d, f"wave:{wave}", blocked)
            if _wave(state, wave)["status"] == "done" and not force:
                return f"ERROR: wave {wave} is already done (or --force)"
            row = _wave(state, wave)
            row.update({
                "status": "in-progress",
                "branch": _clean(branch) if branch else f"feat/{d.name}-w{wave}",
                "updated": _now(),
            })
            state["status"] = "running"
            _event(state, f"start wave {wave} on {row['branch']}")
            _save_state(d, state)
            return f"Recorded wave {wave} in progress (`{row['branch']}`).\n\n" + _summary(root, d, state, waves, budget, review)

        if action == "complete":
            if not wave:
                return "ERROR: --wave is required"
            if waves and wave not in waves:
                return f"ERROR: wave {wave} is not in WAVES.md"
            if not note.strip():
                return "ERROR: --note is required — record the evidence (tests, CI, demo)"
            row = _wave(state, wave)
            if row["status"] != "in-progress" and not force:
                return f"ERROR: wave {wave} is {row['status']}, not in-progress (or --force)"
            row.update({
                "status": "done",
                "pr": _clean(pr) if pr else row.get("pr", "—"),
                "evidence": _clean(note),
                "updated": _now(),
            })
            _event(state, f"complete wave {wave}" + (f" ({pr})" if pr else "") + f": {_clean(note)}")
            _save_state(d, state)
            return (f"Recorded wave {wave} done.\n\n" + _summary(root, d, state, waves, budget, review)
                    + "\n\n" + _decide(root, d, state, waves, review))

        if action == "block":
            if not note.strip():
                return "ERROR: --note is required — say what the human must decide"
            state["status"] = "blocked"
            _event(state, f"blocked: {_clean(note)}")
            _save_state(d, state)
            return f"BLOCKED: {_clean(note)}\n\nResume with `--action=resume` once resolved."

        if action == "resume":
            state["status"] = "running"
            _event(state, "resumed")
            _save_state(d, state)
            return f"Resumed {d.name}.\n\n" + _summary(root, d, state, waves, budget, review)

        if action == "reset":
            if wave:
                row = _wave(state, wave)
                row.update({"status": "pending", "evidence": "—", "updated": _now()})
                _event(state, f"reset wave {wave}")
            else:
                if not force:
                    return "ERROR: a full reset needs --force (or pass --wave=N)"
                state.update({"status": "running", "iterations": 0, "waves": {}})
                _event(state, "full reset")
            _save_state(d, state)
            return f"Reset {d.name}.\n\n" + _summary(root, d, state, waves, budget, review)

        if action == "finish":
            undone = [n for n in sorted(waves) if _wave(state, n)["status"] != "done"]
            if undone and not force:
                return (
                    f"ERROR: waves {', '.join(map(str, undone))} are not done "
                    "— finish them first (or --force)"
                )
            if not (d / "VALIDATION.md").is_file():
                return "ERROR: VALIDATION.md is missing — run ship_validate first"
            blocked = _blocking_gates(d, state, "finish", root)
            if blocked:
                return _gate_directive(root, d, "finish", blocked)
            if review == "required":
                audit = _audit_status(d, "DELIVERY-AUDIT.md")
                if audit in ("missing", "unverified"):
                    return _audit_brief(root, d, "delivery", audit)
                if audit == "block":
                    return _audit_block_brief(root, d, "delivery")
            state["status"] = "done"
            _event(state, "feature validated and shipped")
            _save_state(d, state)
            return f"Feature {d.name} marked done.\n\n" + _next_feature(root, d, review)

    # status / next: pick the first unfinished feature.
    for d in dirs:
        state = _load_state(d)
        waves = _parse_waves(d)
        if state["status"] == "done":
            continue
        if action == "next":
            if state["iterations"] >= budget:
                _save_state(d, state)
                return (
                    f"STOP: iteration budget exhausted ({state['iterations']}/{budget}) "
                    f"on `{d.name}`.\n\nReport progress and hand back to the human; "
                    "raise --max_iterations to continue."
                )
            state["iterations"] += 1
            _save_state(d, state)
        if state["status"] == "blocked":
            return (
                f"BLOCKED: `{d.name}` is blocked.\n\n"
                + (state["events"][-1] if state["events"] else "")
                + "\n\nResolve it, then run `--action=resume`."
            )
        verdict = _decide(root, d, state, waves, review)
        if verdict == "FEATURE-DONE":
            state["status"] = "done"
            _event(state, "feature validated and shipped")
            _save_state(d, state)
            continue
        head = f"# Delivery loop — {d.name}\n\n{_summary(root, d, state, waves, budget, review)}\n"
        return head + "\n" + verdict

    return "\n".join([
        "DONE: every specced feature is validated.",
        "",
        "Close the loop:",
        f"- refresh `python -m openharness run product_map --repo_path={root}`",
        "- make sure README/AGENTS.md describe what shipped",
        "- report iterations, waves, PRs and remaining known gaps",
        "- if new work is wanted, frame the next feature (discover → spec → plan)",
    ])


def _next_feature(
    root: Path, current: Path, review: str = "required",
) -> str:
    remaining = [d for d in _feature_dirs(root)
                 if d != current and _load_state(d)["status"] != "done"]
    if not remaining:
        return "No unfinished feature remains — the product map is complete."
    d = remaining[0]
    state = _load_state(d)
    waves = _parse_waves(d)
    return f"Next feature: `{d.name}`.\n\n" + _decide(root, d, state, waves, review)
