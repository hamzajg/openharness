from __future__ import annotations

import hashlib
import json
import re
import shutil
import signal
import subprocess
import tempfile
import time
import zipfile
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


# ------------------------------------------------------------- device capture

def _require_tool(name: str, hint: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SkillError(f"{name} not found — {hint}")
    return path


def _run(cmd: list[str], timeout: int = 0) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd, capture_output=True, timeout=timeout or None
        )
    except subprocess.TimeoutExpired as ex:
        raise SkillError(f"`{' '.join(cmd)}` timed out") from ex
    except OSError as ex:
        raise SkillError(f"cannot run `{cmd[0]}`: {ex}") from ex


def _check(run: subprocess.CompletedProcess, what: str) -> None:
    if run.returncode != 0:
        tail = (run.stderr or run.stdout or b"").decode(
            "utf-8", errors="replace"
        ).strip()[-300:]
        raise SkillError(f"{what} failed (exit {run.returncode}): {tail}")


def _capture_android(
    workdir: Path, media: str, seconds: int, serial: str
) -> list[tuple[Path, str]]:
    adb = _require_tool("adb", "install Android platform-tools")
    base = [adb] + (["-s", serial] if serial.strip() else [])
    out: list[tuple[Path, str]] = []
    want = {"screenshot", "video", "log"} if media == "all" else {media}

    if "screenshot" in want:
        p = workdir / "screenshot.png"
        with p.open("wb") as fh:
            run = _run([*base, "exec-out", "screencap", "-p"])
            _check(run, "adb screencap")
            fh.write(run.stdout)
        if p.stat().st_size == 0:
            raise SkillError("adb screencap produced an empty file")
        out.append((p, "android screenshot"))

    if "video" in want:
        secs = max(1, int(seconds or 10))
        remote = "/sdcard/openharness-evidence.mp4"
        local = workdir / "recording.mp4"
        _check(
            _run(
                [*base, "shell", "screenrecord", "--time-limit", str(secs), remote],
                timeout=secs + 30,
            ),
            "adb screenrecord",
        )
        _check(_run([*base, "pull", remote, str(local)]), "adb pull")
        _run([*base, "shell", "rm", "-f", remote])
        out.append((local, f"android screenrecord ({secs}s)"))

    if "log" in want:
        p = workdir / "logcat.txt"
        run = _run([*base, "logcat", "-d", "-t", "500"])
        _check(run, "adb logcat")
        p.write_bytes(run.stdout or b"")
        out.append((p, "adb logcat (last 500 lines)"))

    return out


def _capture_ios(
    workdir: Path, media: str, seconds: int
) -> list[tuple[Path, str]]:
    xcrun = _require_tool(
        "xcrun", "install Xcode command line tools (xcrun simctl)"
    )
    sim = [xcrun, "simctl"]
    out: list[tuple[Path, str]] = []
    want = {"screenshot", "video", "log"} if media == "all" else {media}

    if "screenshot" in want:
        p = workdir / "screenshot.png"
        _check(
            _run([*sim, "io", "booted", "screenshot", str(p)]),
            "simctl screenshot",
        )
        out.append((p, "ios simulator screenshot"))

    if "video" in want:
        secs = max(1, int(seconds or 10))
        p = workdir / "recording.mov"
        proc = subprocess.Popen(
            [*sim, "io", "booted", "recordVideo", str(p)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            proc.wait(timeout=secs)
        except subprocess.TimeoutExpired:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                raise SkillError("simctl recordVideo did not stop")
        if proc.returncode != 0 or not p.is_file() or p.stat().st_size == 0:
            raise SkillError("simctl recordVideo produced no file")
        out.append((p, f"ios simctl recordVideo ({secs}s)"))

    if "log" in want:
        p = workdir / "device.log"
        run = _run(
            [*sim, "spawn", "booted", "log", "show",
             "--last", "5m", "--style", "compact"]
        )
        _check(run, "simctl log show")
        p.write_bytes(run.stdout or b"")
        out.append((p, "ios simulator log (last 5m)"))

    return out


# ------------------------------------------------------------- share / prune

def _referenced_run_ids(repo: Path) -> set[str]:
    """Run ids a loop still points at — wave `bundle` fields and
    `evidence:<run-id>` gate tokens in LOOP.state.json / LOOP.md."""
    ids: set[str] = set()
    specs = repo / "specs"
    if not specs.is_dir():
        return ids
    for state in specs.glob("*/LOOP.state.json"):
        try:
            data = json.loads(state.read_text())
        except (OSError, ValueError):
            continue
        for row in (data.get("waves") or {}).values():
            if isinstance(row, dict) and row.get("bundle"):
                ids.add(str(row["bundle"]))
        for row in (data.get("gates") or {}).values():
            ev = str((row or {}).get("evidence") or "")
            if ev.lower().startswith("evidence:"):
                ids.add(ev.split(":", 1)[1].strip())
    for loop in specs.glob("*/LOOP.md"):
        try:
            text = loop.read_text(errors="ignore")
        except OSError:
            continue
        for m in re.finditer(r"evidence:(\S+)", text):
            ids.add(m.group(1).rstrip(").,"))
    return ids


def _share_public(target: Path, repo: Path, feature: str) -> str:
    report = evidence.verify(target, repo=repo)
    if not report.ok:
        raise SkillError(
            "refusing --public: the bundle does not verify — "
            + "; ".join(f.message for f in report.errors[:3])
        )
    dest = repo / "docs" / "evidence" / feature / target.name
    if dest.exists():
        raise SkillError(f"{dest} already exists — remove it or pick another run")
    shutil.copytree(target, dest)
    return (
        f"Published {target.name} to {dest}\n"
        "Warning: binary media (screenshots, recordings) is not "
        "secret-scanned — review it before committing.\n"
        "Next: `git add` the folder if it should travel with the repo."
    )


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
    snippet: str = "",
    note: str = "",
    timeout: int = 0,
    expected_failure: bool = False,
    tdd: str = "",
    allow_old: bool = False,
    by: str = "",
    fragment: str = "",
    tracked: bool = False,
    kind: str = "proof",
    out_dir: str = "e2e",
    force: bool = False,
    device: str = "",
    media: str = "screenshot",
    seconds: int = 0,
    serial: str = "",
    keep: int = 0,
    public: bool = False,
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
              steps.json fragment into the manifest. Fragment artifacts may
              be source files ({path, caption?}) — attach copies and hashes
              them — or manifest-ready entries (path+mime+sha256+bytes).
      fixture Write a Playwright evidence fixture into the repo (out_dir,
              default e2e/); it emits steps-*.json fragments for `attach`.
      capture Grab a screenshot, recording or log from a connected device
              (device=android via adb, ios via xcrun simctl) and attach the
              files to the resolved bundle's step. The harness never drives
              the device itself — it shells to the platform tool.
      share   Zip the resolved bundle to <run-id>.zip + .sha256 next to it;
              --public instead copies a verified bundle to
              docs/evidence/<feature>/<run-id>/ (opt-in; binary media is
              not secret-scanned).
      prune   Delete oldest scratch bundles beyond --keep=N per feature;
              bundles referenced by a LOOP row or gate are never deleted.
      render  Write index.html + SUMMARY.md from evidence.json.
      verify  Check manifest, artifacts, hashes, commit, secrets, tracking.
              Raises (CLI exit 2) when anything is wrong.

    Params:
      action: list|new|step|attach|fixture|capture|share|prune|render|verify.
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
      tdd: TDD phase for this `step`: red (expected-failure test run),
        green (tests pass after implementation), or refactor (suite
        re-run after cleanup). ship_loop requires an ordered
        red -> green -> refactor sequence to complete a wave.
      allow_old: Attach a file older than the step (records why in the note).
      by: Who captured a manual artifact.
      fragment: Path to a JSON fragment (steps.json) to fold into the manifest.
        An artifact `role` omitted by the fragment is inferred from its MIME
        type and file name, exactly as `attach --file` does. Artifacts may
        also be source files (`path` only): attach resolves them relative to
        the fragment's directory then cwd, copies them under raw/<step>/,
        and computes mime/sha256/bytes itself — the same staleness guard and
        `--allow-old` override as `attach --file` apply.
      tracked: On `new`, place the bundle under `evidence/` (committable)
        instead of the gitignored scratch root.
      kind: On `new`, `proof` (default — the wave/finish evidence ship_loop
        verifies) or `walkthrough` (local-only companion material: screenshots,
        recordings, log summaries; cannot be combined with `tracked`).
      out_dir: On `fixture`, subdirectory of `repo` that receives the
        generated Playwright fixture (default `e2e`).
      force: On `fixture`, overwrite an existing fixture file.
      device: On `capture`, `android` (adb) or `ios` (xcrun simctl, booted
        simulator). Required for `capture`.
      media: On `capture`, `screenshot` (default), `video`, `log`, or `all`.
      seconds: On `capture --media=video`, recording length (default 10).
      serial: On `capture --device=android`, adb `-s` serial when several
        devices are attached.
      keep: On `prune`, newest runs per feature to keep (required, >= 1).
      public: On `share`, copy the verified bundle to
        `docs/evidence/<feature>/<run-id>/` instead of zipping it.
    """
    repo_path = Path(repo)
    action = (action or "list").strip().lower()

    if action == "list":
        rows = evidence.list_bundles(repo_path, feature=feature or None)
        if not rows:
            return f"No evidence bundles under {evidence.bundle_root(repo_path)}."
        width = max(len(r["feature"]) for r in rows) if rows else 8
        lines = [
            f"{'feature':{width}}  {'run':26}  {'kind':11}  {'verdict':8}  {'steps':>5}  {'arts':>4}  {'loc':7}  head"
        ]
        for r in rows:
            loc = "tracked" if r.get("tracked") else "local"
            rkind = r.get("kind") or "proof"
            if r.get("invalid"):
                lines.append(
                    f"{r['feature']:{width}}  {r['run_id']:26}  {'?':11}  {'INVALID':8}  {'-':>5}  {'-':>4}  {loc:7}  {r['invalid']}"
                )
                continue
            lines.append(
                f"{r['feature']:{width}}  {r['run_id']:26}  {rkind:11}  {r['verdict']:8}  "
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
                kind=kind,
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
                tdd=tdd,
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
                    snippet=snippet,
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
            frag_base = (
                fragment_path.parent if fragment_path.is_file() else Path.cwd()
            )
            frag_redactions: list[dict] = []
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
                new_arts = []
                for art in step_data.get("artifacts") or []:
                    if not isinstance(art, dict) or not str(art.get("path") or "").strip():
                        raise SkillError("fragment artifact requires a path")
                    if "sha256" in art:
                        # Manifest-ready form: bundle-relative path with a
                        # producer-supplied digest — recorded as-is.
                        for key in ("mime", "sha256", "bytes"):
                            if key not in art:
                                raise SkillError(f"artifact missing required field: {key}")
                        # `role` is a label, not a proof: infer it from
                        # MIME/suffix when omitted; explicit wins.
                        if not str(art.get("role") or "").strip():
                            art["role"] = evidence._role_for(art["mime"], Path(art["path"]))
                        new_arts.append(art)
                    else:
                        # Source-file form: a real file the harness copies
                        # into raw/<step>/ and hashes itself.
                        try:
                            norm, reds = evidence.fragment_artifact(
                                target,
                                str(step_data["id"]),
                                art,
                                frag_base,
                                started_at=str(step_data.get("started_at") or ""),
                                allow_old=allow_old,
                            )
                        except evidence.EvidenceError as ex:
                            raise SkillError(str(ex)) from ex
                        frag_redactions.extend(reds)
                        new_arts.append(norm)
                step_data["artifacts"] = new_arts
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
            manifest.setdefault("redactions", []).extend(frag_redactions)
            evidence._write_manifest(target, manifest)
            names = ", ".join(f"{s['id']} ({s['status']})" for s in folded)
            arts = sum(len(s.get("artifacts") or []) for s in folded)
            return (
                f"Folded step {names} into {target.name}\n"
                f"  artifacts: {arts}\n"
                "Next: `--action=render`."
            )

    if action == "fixture":
        template = Path(__file__).with_name("evidence_playwright_fixture.ts")
        if not template.is_file():
            raise SkillError(f"fixture template missing: {template}")
        out_dir = Path(out_dir.strip() or "e2e")
        if out_dir.is_absolute() or ".." in out_dir.parts:
            raise SkillError("out_dir must be a relative path inside the repo")
        target = repo_path / out_dir / "evidence.fixture.ts"
        if target.exists() and not force:
            raise SkillError(
                f"{target} already exists — pass --force to overwrite "
                "or edit it in place (the fixture belongs to the repo)"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(template.read_text())

        warn = ""
        pkg = repo_path / "package.json"
        if pkg.is_file() and "@playwright/test" not in pkg.read_text(errors="replace"):
            warn = (
                "\nWarning: package.json does not list @playwright/test — "
                "install it and `npx playwright install` first."
            )
        return (
            f"Wrote {target}\n"
            "Next: import { test, expect } from it in your spec, run with "
            "EVIDENCE_RUN_DIR set, then fold the emitted steps-*.json into a "
            "walkthrough bundle:\n"
            f"  EVIDENCE_RUN_DIR=/tmp/walk npx playwright test <spec>\n"
            f"  python -m openharness run harness_evidence --action=new "
            f"--repo={repo_path} --feature=<feature> --wave=<n> --kind=walkthrough\n"
            "  python -m openharness run harness_evidence --action=attach "
            "--bundle=<bundle> --fragment=$EVIDENCE_RUN_DIR/steps-<spec>.json"
            f"{warn}"
        )

    if action == "capture":
        device = device.strip().lower()
        if device not in ("android", "ios"):
            raise SkillError("capture requires --device=android|ios")
        media = media.strip().lower() or "screenshot"
        if media not in ("screenshot", "video", "log", "all"):
            raise SkillError(
                f"media must be screenshot|video|log|all, got {media!r}"
            )
        if seconds < 0:
            raise SkillError("--seconds must be zero or positive")
        target = _resolve(repo_path, bundle, feature)
        attached = []
        with tempfile.TemporaryDirectory(prefix="oh-capture-") as tmp:
            workdir = Path(tmp)
            try:
                produced = (
                    _capture_android(workdir, media, seconds, serial)
                    if device == "android"
                    else _capture_ios(workdir, media, seconds)
                )
            except SkillError:
                raise
            except Exception as ex:  # device tools fail in many shapes
                raise SkillError(f"device capture failed: {ex}") from ex
            for path, caption in produced:
                try:
                    art = evidence.record_attach(
                        target,
                        path,
                        step_id=step,
                        caption=caption or f"{device} {media}",
                        by=by,
                    )
                except evidence.EvidenceError as ex:
                    raise SkillError(str(ex)) from ex
                attached.append(art)
        names = ", ".join(a["path"] for a in attached)
        return (
            f"Captured {len(attached)} artifact(s) from {device} into "
            f"{target.name}\n  {names}\n"
            "Next: `--action=render`."
        )

    if action == "share":
        target = _resolve(repo_path, bundle, feature)
        if public:
            feat = target.parent.name
            return _share_public(target, repo_path, feat)
        if not target.is_dir():
            raise SkillError(f"bundle not found: {target}")
        zip_path = target.parent / f"{target.name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(target.rglob("*")):
                if p.is_file():
                    zf.write(p, p.relative_to(target.parent).as_posix())
        digest = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        sha_path = Path(str(zip_path) + ".sha256")
        sha_path.write_text(f"{digest}  {zip_path.name}\n")
        return (
            f"Shared {target.name}\n"
            f"  zip: {zip_path}\n"
            f"  sha256: {digest}\n"
            f"  sums: {sha_path}"
        )

    if action == "prune":
        if keep < 1:
            raise SkillError("prune requires --keep=N with N >= 1")
        root = evidence.bundle_root(repo_path)  # scratch root only
        referenced = _referenced_run_ids(repo_path)
        deleted: list[str] = []
        kept_refs: list[str] = []
        if root.is_dir():
            for feature_dir in sorted(root.iterdir()):
                if not feature_dir.is_dir():
                    continue
                runs = sorted(
                    (d for d in feature_dir.iterdir() if d.is_dir()),
                    key=lambda p: p.name,
                    reverse=True,
                )
                for old in runs[keep:]:
                    if old.name in referenced:
                        kept_refs.append(old.name)
                        continue
                    shutil.rmtree(old)
                    deleted.append(f"{feature_dir.name}/{old.name}")
        lines = [f"Pruned {len(deleted)} bundle(s) (kept newest {keep} per feature)"]
        lines += [f"  - {d}" for d in deleted[:20]]
        if len(deleted) > 20:
            lines.append(f"  … {len(deleted) - 20} more")
        if kept_refs:
            lines.append(
                f"Skipped {len(kept_refs)} bundle(s) referenced by loop state: "
                + ", ".join(sorted(set(kept_refs))[:10])
            )
        lines.append(
            f"Tracked bundles under {evidence.bundle_root(repo_path, tracked=True)} "
            "are never pruned."
        )
        return "\n".join(lines)

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
        f"unknown action {action!r} "
        "(list|new|step|attach|fixture|capture|share|prune|render|verify)"
    )
