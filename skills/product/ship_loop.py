"""Delivery-loop controller: turn the /ship-product playbook into a repeatable loop.

The loop is AGENT-DRIVEN (D001): the harness never launches an agent or a
scheduler. This skill is the deterministic oracle the agent calls once per
iteration — it reads the spec artifacts plus its own run log and answers
"what is the next action?" (frame, spec, plan, wave N, validate, done) or
"blocked/stop". It also records wave outcomes so a loop survives context
loss and session restarts.

State lives in `specs/<feature>/LOOP.md` next to the spec it describes:
a status line, an iteration counter, a wave table, and an append-only event
log. WAVES.md stays the immutable plan; LOOP.md is the mutable execution
record. Both are product artifacts committed with the PRs.

Deterministic; stdlib only.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from openharness.skill import skill

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
_WAVE_STATUSES = ("pending", "in-progress", "done")
_FEATURE_STATUSES = ("running", "blocked", "done")


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
    return {"status": status, "iterations": iterations, "waves": waves, "events": events}


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
    out += ["", "## Events", ""]
    out += [f"- {e}" for e in state["events"][-200:]] or ["- (none)"]
    (spec_dir / "LOOP.md").write_text("\n".join(out) + "\n")


def _wave(state: dict, n: int) -> dict:
    return state["waves"].setdefault(
        n, {"status": "pending", "branch": "—", "pr": "—", "evidence": "—", "updated": "—"}
    )


def _event(state: dict, text: str) -> None:
    state["events"].append(f"{_now()} {text}")


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
        "4. Fill SPEC.md, EXAMPLES.feature (@w<N> tags) and BACKLOG.md",
        "   (user stories, one `## US<n> — ...` block each).",
        "5. `python -m openharness run wave_plan --spec_dir="
        f"{root}/specs/<feature>`",
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
        "3. Implement minimally, matching repo conventions (KISS).",
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


def _decide(root: Path, spec_dir: Path, state: dict, waves: dict) -> str:
    missing = [
        name for name in ("SPEC.md", "EXAMPLES.feature", "BACKLOG.md")
        if not (spec_dir / name).is_file()
    ]
    if missing:
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
        return _wave_brief(root, spec_dir, state, pending[0], waves)

    if not (spec_dir / "VALIDATION.md").is_file():
        return _validate_brief(root, spec_dir)

    return "FEATURE-DONE"


def _summary(spec_dir: Path, state: dict, waves: dict, budget: int) -> str:
    done = sum(1 for w in waves if _wave(state, w)["status"] == "done")
    progress = sum(1 for w in waves if _wave(state, w)["status"] == "in-progress")
    return (
        f"Feature: `{spec_dir.name}` · status {state['status']} · "
        f"iteration {state['iterations']}/{budget} · "
        f"waves {done}/{len(waves)} done"
        + (f", {progress} in progress" if progress else "")
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
    max_iterations: int = 25,
    force: bool = False,
) -> str:
    """Drive one delivery-loop iteration: report the next action and record wave outcomes.

    Actions: `next` (default; increments the iteration counter and prints the
    next action or DONE/BLOCKED/STOP), `status` (same without incrementing),
    `start` (mark a wave in progress), `complete` (mark it done with evidence),
    `block` (stop the loop with a reason), `resume` (clear blocked), `reset`
    (clear wave state), `finish` (mark a validated feature done).

    State is `specs/<feature>/LOOP.md`; the plan stays in WAVES.md. The agent
    executes the action — the harness never launches agents (D001).

    Params:
      repo_path: Repository root containing specs/.
      spec_dir: Feature dir; defaults to the first unfinished feature.
      action: next|status|start|complete|block|resume|reset|finish.
      wave: Wave number for start/complete/reset.
      note: Evidence (complete) or reason (block).
      pr: PR reference recorded on complete.
      branch: Branch name recorded on start (default feat/<feature>-w<N>).
      max_iterations: Hard stop after this many `next` calls (default 25).
      force: Allow out-of-order start/complete or a full reset.
    """
    budget = max(1, int(max_iterations))
    root = Path(repo_path).resolve()
    if not root.is_dir():
        return f"ERROR: {repo_path} is not a directory"
    if action not in ("next", "status", "start", "complete", "block", "resume", "reset", "finish"):
        return f"ERROR: unknown action {action!r} (next|status|start|complete|block|resume|reset|finish)"

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
            return f"Recorded wave {wave} in progress (`{row['branch']}`).\n\n" + _summary(d, state, waves, budget)

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
            return (f"Recorded wave {wave} done.\n\n" + _summary(d, state, waves, budget)
                    + "\n\n" + _decide(root, d, state, waves))

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
            return f"Resumed {d.name}.\n\n" + _summary(d, state, waves, budget)

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
            return f"Reset {d.name}.\n\n" + _summary(d, state, waves, budget)

        if action == "finish":
            undone = [n for n in sorted(waves) if _wave(state, n)["status"] != "done"]
            if undone and not force:
                return (
                    f"ERROR: waves {', '.join(map(str, undone))} are not done "
                    "— finish them first (or --force)"
                )
            if not (d / "VALIDATION.md").is_file():
                return "ERROR: VALIDATION.md is missing — run ship_validate first"
            state["status"] = "done"
            _event(state, "feature validated and shipped")
            _save_state(d, state)
            return f"Feature {d.name} marked done.\n\n" + _next_feature(root, d)

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
        verdict = _decide(root, d, state, waves)
        if verdict == "FEATURE-DONE":
            state["status"] = "done"
            _event(state, "feature validated and shipped")
            _save_state(d, state)
            continue
        head = f"# Delivery loop — {d.name}\n\n{_summary(d, state, waves, budget)}\n"
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


def _next_feature(root: Path, current: Path) -> str:
    remaining = [d for d in _feature_dirs(root)
                 if d != current and _load_state(d)["status"] != "done"]
    if not remaining:
        return "No unfinished feature remains — the product map is complete."
    d = remaining[0]
    state = _load_state(d)
    waves = _parse_waves(d)
    return f"Next feature: `{d.name}`.\n\n" + _decide(root, d, state, waves)
