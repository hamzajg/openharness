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
            raise SkillError(f"no evidence bundles for feature {feature!r} under {evidence.bundle_root(repo)}")
        return found[0]["bundle"]
    latest = evidence.list_bundles(repo)
    if not latest:
        raise SkillError(f"no evidence bundles under {evidence.bundle_root(repo)} — run `--action=new` first")
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
) -> str:
    """Create, render, verify or list local evidence bundles (ADR 0007 phase 1).

    Bundles live in `<repo>/.openharness/evidence/<feature>/<run-id>/` — local
    scratch, gitignored, never committed. `verify` re-hashes every artifact,
    fails on a missing file, a token in a log, a manifest whose commit is not
    the checked-out one, or a bundle git is tracking. Neither action touches the
    network, and neither writes to git.

    Actions:
      list    Every bundle, newest first, with verdict, counts and commit.
      new     Create an empty bundle + manifest (feature required).
      render  Write index.html + SUMMARY.md from evidence.json.
      verify  Check manifest, artifacts, hashes, commit, secrets, tracking.
              Raises (CLI exit 2) when anything is wrong.

    Params:
      action: list|new|render|verify.
      repo: Repository root (default cwd).
      bundle: Explicit bundle path; else the newest bundle for `feature`,
        else the newest bundle overall.
      feature: Feature name (required for `new`, a selector elsewhere).
      wave: Wave number recorded in a new manifest.
      head, branch, base: Git facts recorded in a new manifest.
      summary: One-paragraph "what this proves".
      not_verified: Semicolon- or newline-separated list of what was not checked.
      inline: Render with images base64-inlined into one shareable file.
    """
    repo_path = Path(repo)
    action = (action or "list").strip().lower()

    if action == "list":
        rows = evidence.list_bundles(repo_path, feature=feature or None)
        if not rows:
            return f"No evidence bundles under {evidence.bundle_root(repo_path)}."
        width = max(len(r["feature"]) for r in rows) if rows else 8
        lines = [f"{'feature':{width}}  {'run':26}  {'verdict':8}  {'steps':>5}  {'arts':>4}  head"]
        for r in rows:
            if r.get("invalid"):
                lines.append(
                    f"{r['feature']:{width}}  {r['run_id']:26}  {'INVALID':8}  {'-':>5}  {'-':>4}  {r['invalid']}"
                )
                continue
            lines.append(
                f"{r['feature']:{width}}  {r['run_id']:26}  {r['verdict']:8}  "
                f"{r['steps']:>5}  {r['artifacts']:>4}  {(r['head'] or '?')[:12]}"
            )
        lines.append("")
        lines.append(f"root: {evidence.bundle_root(repo_path)} (local scratch, never committed)")
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
            )
        except evidence.EvidenceError as ex:
            raise SkillError(str(ex)) from ex
        return (
            f"Created {created}\n"
            f"  manifest: {created / 'evidence.json'}\n"
            "Next: record steps and artifacts, then `--action=render`."
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

    raise SkillError(f"unknown action {action!r} (list|new|render|verify)")
