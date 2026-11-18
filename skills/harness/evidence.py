from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from openharness import evidence
from openharness.skill import SkillError, skill


def _resolve(repo: Path, bundle: str, feature: str) -> Path:
    """An explicit bundle path, else the newest bundle for a feature."""
    if bundle:
        return Path(bundle)
    if feature:
        found = evidence.list_bundles(repo, feature=feature)
        if not found:
            raise SkillError(
                f"no evidence bundles for feature {feature!r} under "
                f"{evidence.bundle_root(repo)} or {evidence.bundle_root(repo, tracked=True)}"
            )
        return found[0]["bundle"]
    latest = evidence.list_bundles(repo)
    if not latest:
        raise SkillError(
            f"no evidence bundles under {evidence.bundle_root(repo)} or "
            f"{evidence.bundle_root(repo, tracked=True)} — run `--action=new` first"
        )
    return latest[0]["bundle"]


@skill
def harness_evidence(
    action: str = "list",
    repo: str = ".",
    bundle: str = "",
    feature: str = "",
    wave: int = 0,
    head: str = "",
    branch: str = "",
    base: str = "main",
    summary: str = "",
    not_verified: str = "",
    inline: bool = False,
    cmd: str = "",
    cwd: str = ".",
    title: str = "",
    step: str = "",
    file: str = "",
    caption: str = "",
    role: str = "",
    note: str = "",
    timeout: int = 0,
    expected_failure: bool = False,
    allow_old: bool = False,
    by: str = "",
    fragment: str = "",
    tracked: bool = False,
) -> str:
    """Capture, render, verify or list evidence bundles (ADR 0007).

    Bundles live in `<repo>/.openharness/evidence/<feature>/<run-id>/` — local
    scratch, gitignored — unless `tracked` is set on `new`, which places them
    under `<repo>/evidence/<feature>/<run-id>/`, the folder meant to be
    committed and pushed when a run's proof should travel with the repo.
    `step` runs a command and records its real exit code, duration and log;
    `attach` adds an existing screenshot, recording, trace or log to a step.
    `verify` re-hashes every artifact, fails on a missing file, a token in a
    log, a manifest whose commit is not the checked-out one, or a scratch
    bundle git is tracking. Neither action touches the network, and neither
    writes to git — committing a tracked bundle is a separate, explicit step.

    Actions:
      list    Every bundle, newest first, with verdict, counts and commit.
      new     Create an empty bundle + manifest (feature required).
      step    Run a command; record exit code, duration and log.
      attach  Add a file to a step (copies it under raw/<step>/) or fold a
              steps.json fragment into the manifest.
      render  Write index.html + SUMMARY.md from evidence.json.
      verify  Check manifest, artifacts, hashes, commit, secrets, tracking.
              Raises (CLI exit 2) when anything is wrong.

    Params:
      action: list|new|step|attach|render|verify.
      repo: Repository root (default cwd).
      bundle: Explicit bundle path; else the newest bundle for `feature`,
        else the newest bundle overall.
      feature: Feature name (required for `new`, a selector elsewhere).
      wave: Wave number recorded in a new manifest.
      head, branch, base: Git facts recorded in a new manifest.
      summary: One-paragraph "what this proves".
      not_verified: Semicolon- or newline-separated list of what was not checked.
      inline: Render with images base64-inlined into one shareable file.
      cmd: Command for `step`; also accepted after `--` on the CLI.
      cwd: Working directory for `step`, relative to the repo root.
      title: Step title for `step`, or a manual-step title for `attach`.
      step: Step id for `attach` (defaults to the newest step).
      file: Artifact path for `attach`.
      caption: Caption shown in the page for an attached artifact.
      role: screenshot|video|trace|har|attachment (inferred when omitted).
      note: Free-text note recorded on a `step`.
      timeout: Seconds before a `step` is killed; 0 means no limit.
      expected_failure: A non-zero exit is expected for this `step`.
      allow_old: Attach a file older than the step (records why in the note).
      by: Who captured a manual artifact.
      fragment: Path to a JSON fragment (steps.json) to fold into the manifest.
        An artifact `role` omitted by the fragment is inferred from its MIME
        type and file name, exactly as `attach --file` does.
      tracked: On `new`, place the bundle under `evidence/` (committable)
        instead of the gitignored scratch root.
    """
    repo_path = Path(repo)
    action = (action or "list").strip().lower()

    if action == "list":
        rows = evidence.list_bundles(repo_path, feature=feature or None)
        if not rows:
            return f"No evidence bundles under {evidence.bundle_root(repo_path)}."
        width = max(len(r["feature"]) for r in rows) if rows else 8
        lines = [
            f"{'feature':{width}}  {'run':26}  {'verdict':8}  {'steps':>5}  {'arts':>4}  {'loc':7}  head"
        ]
        for r in rows:
            loc = "tracked" if r.get("tracked") else "local"
            if r.get("invalid"):
                lines.append(
                    f"{r['feature']:{width}}  {r['run_id']:26}  {'INVALID':8}  {'-':>5}  {'-':>4}  {loc:7}  {r['invalid']}"
                )
                continue
            lines.append(
                f"{r['feature']:{width}}  {r['run_id']:26}  {r['verdict']:8}  "
                f"{r['steps']:>5}  {r['artifacts']:>4}  {loc:7}  {(r['head'] or '?')[:12]}"
            )
        lines.append("")
        lines.append(f"local:   {evidence.bundle_root(repo_path)} (scratch, gitignored)")
        lines.append(f"tracked: {evidence.bundle_root(repo_path, tracked=True)} (commit to publish)")
        return "\n".join(lines)

    if action == "new":
        items = [
            x.strip()
            for x in (not_verified or "").replace("\n", ";").split(";")
            if x.strip()
        ]
        try:
            created = evidence.new_bundle(
                repo_path,
                feature,
                wave=wave,
                head=head,
                branch=branch,
                base=base,
                summary=summary,
                not_verified=items,
                tracked=tracked,
            )
        except evidence.EvidenceError as ex:
            raise SkillError(str(ex)) from ex
        return (
            f"Created {created}\n"
            f"  manifest: {created / 'evidence.json'}\n"
            + (
                "  tracked root — `git add` the bundle to publish it.\n"
                if tracked
                else ""
            )
            + "Next: record steps and artifacts, then `--action=render`."
        )

    if action == "step":
        target = _resolve(repo_path, bundle, feature)
        if not cmd.strip():
            raise SkillError("step requires --cmd or `-- <command>`")
        try:
            recorded = evidence.record_step(
                target,
                title=title,
                cmd=cmd,
                cwd=cwd,
                timeout=timeout,
                expected_failure=expected_failure,
                step_id=step,
                note=note,
            )
        except evidence.EvidenceError as ex:
            raise SkillError(str(ex)) from ex
        return (
            f"Recorded step {recorded['id']} ({recorded['status']}) in {target}\n"
            f"  log: {recorded['log']}\n"
            "Next: attach screenshots or recordings, then `--action=render`."
        )

    if action == "attach":
        target = _resolve(repo_path, bundle, feature)
        if not file.strip() and not fragment.strip():
            raise SkillError("attach requires --file or --fragment")
        if file.strip():
            try:
                art = evidence.record_attach(
                    target,
                    file,
                    step_id=step,
                    caption=caption,
                    role=role,
                    allow_old=allow_old,
                    by=by,
                )
            except evidence.EvidenceError as ex:
                raise SkillError(str(ex)) from ex
            return (
                f"Attached {art['path']} ({art['mime']}, {art['bytes']} bytes) "
                f"to {target.name}\n"
                f"  sha256: {art['sha256']}\n"
                "Next: `--action=render`."
            )
        if fragment.strip():
            fragment_path = Path(fragment.strip()).expanduser()
            if not fragment_path.is_absolute():
                fragment_path = Path.cwd() / fragment_path
            try:
                raw = fragment_path.read_text() if fragment_path.is_file() else fragment
                fragment_data = json.loads(raw)
            except (OSError, json.JSONDecodeError) as ex:
                raise SkillError(f"invalid JSON fragment: {ex}") from ex

            steps_in = fragment_data if isinstance(fragment_data, list) else [fragment_data]
            if not steps_in or not all(isinstance(s, dict) for s in steps_in):
                raise SkillError("fragment must be a step object or a list of step objects")

            manifest = evidence.load(target)
            existing = {s.get("id") for s in manifest["steps"]}
            folded = []
            for step_data in steps_in:
                for key in ("id", "title", "kind", "status", "started_at", "artifacts"):
                    if key not in step_data:
                        raise SkillError(f"fragment missing required field: {key}")

                if step_data["kind"] not in evidence.KINDS:
                    raise SkillError(f"fragment kind must be one of {evidence.KINDS}")
                if step_data["status"] not in evidence.STATUSES:
                    raise SkillError(f"fragment status must be one of {evidence.STATUSES}")
                if step_data["id"] in existing:
                    raise SkillError(f"step {step_data['id']!r} already exists")
                for art in step_data.get("artifacts") or []:
                    for key in ("path", "mime", "sha256", "bytes"):
                        if key not in art:
                            raise SkillError(f"artifact missing required field: {key}")
                    # `role` is a label, not a proof: infer it from MIME/suffix
                    # when the producer omitted it, exactly like `attach --file`.
                    # An explicit role always wins.
                    if not str(art.get("role") or "").strip():
                        art["role"] = evidence._role_for(art["mime"], Path(art["path"]))
                existing.add(step_data["id"])
                folded.append(step_data)

            if not manifest["steps"]:
                # Same rule as record_attach: external evidence landing in an
                # empty bundle gets a manual step recording who captured it.
                try:
                    mtime = fragment_path.stat().st_mtime
                except OSError:
                    mtime = time.time()
                manual = {
                    "id": evidence._next_step_id({"steps": [*manifest["steps"], *folded]}),
                    "title": fragment_path.name if fragment_path.is_file() else "steps.json",
                    "kind": "manual",
                    "status": "manual",
                    "started_at": datetime.fromtimestamp(mtime, timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                    "artifacts": [],
                }
                if by.strip():
                    manual["captured_by"] = by.strip()
                manifest["steps"].append(manual)
            manifest["steps"].extend(folded)
            evidence._write_manifest(target, manifest)
            names = ", ".join(f"{s['id']} ({s['status']})" for s in folded)
            arts = sum(len(s.get("artifacts") or []) for s in folded)
            return (
                f"Folded step {names} into {target.name}\n"
                f"  artifacts: {arts}\n"
                "Next: `--action=render`."
            )

    if action in ("render", "verify"):
        target = _resolve(repo_path, bundle, feature)
        if action == "render":
            try:
                paths = evidence.render(target, inline=inline)
            except evidence.EvidenceError as ex:
                raise SkillError(str(ex)) from ex
            mode = "single file (images inlined)" if inline else "folder"
            report = evidence.verify(target, repo=repo_path)
            tail = (
                f"\nVerification: OK ({len(report.warnings)} warning(s))."
                if report.ok
                else f"\nVerification: {len(report.errors)} error(s) — run --action=verify for detail."
            )
            return (
                f"Rendered {paths['html']} ({mode})\n"
                f"  summary: {paths['summary']}{tail}"
            )

        try:
            report = evidence.verify(target, repo=repo_path)
        except evidence.EvidenceError as ex:
            raise SkillError(str(ex)) from ex
        if not report.ok:
            raise SkillError(report.render())
        lines = [f"OK — {target.name} matches its manifest."]
        manifest = evidence.load(target)
        steps = manifest.get("steps") or []
        arts = sum(len(s.get("artifacts") or []) for s in steps)
        lines.append(f"  steps: {len(steps)} · artifacts: {arts}")
        if report.warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(f.render() for f in report.warnings)
        return "\n".join(lines)

    raise SkillError(
        f"unknown action {action!r} (list|new|step|attach|render|verify)"
    )
