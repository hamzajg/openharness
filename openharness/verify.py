"""Ground truth for the delivery loop: what git and GitHub actually say.

The oracle records *claims* in `LOOP.md` / `LOOP.state.json` — a wave is done,
PR #17 merged, CI was green. Claims drift: a PR recorded as merged is still
open, a merge landed on a branch that is not the default, CI was red, a branch
recorded in progress was never pushed. `reconcile` compares the claims with the
facts and reports every mismatch; it never writes state.

Every fact-gathering function raises `VerifyUnavailable` when the truth cannot
be obtained (no git repository, no token, network error) so the caller can fail
loudly instead of reporting a clean bill of health it cannot support.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess as sp
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_PR_RE = re.compile(r"(?:#|/pull/)(\d+)")
_GITHUB_URL_RE = re.compile(r"github\.com[:/](?P<slug>[^/\s]+/[^/\s]+?)(?:\.git)?$")

#: GitHub conclusions that mean "this job did not fail".
_OK_CONCLUSIONS = ("success", "neutral", "skipped")


class VerifyUnavailable(Exception):
    """The facts needed to check a claim could not be obtained."""


@dataclass
class Finding:
    """One reconciled claim.

    severity: `drift` (the record contradicts reality), `unverified` (reality
    could not be checked), `warning` (true but not a contradiction), `info`.
    """

    severity: str
    subject: str
    message: str

    def render(self) -> str:
        return f"- {self.subject}: {self.message}"


# ------------------------------------------------------------------- git facts

def _git(repo: Path, *args: str) -> sp.CompletedProcess:
    return sp.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def remote_slug(repo: Path) -> str | None:
    """`owner/repo` for a github.com origin, else None."""
    url = _git(repo, "remote", "get-url", "origin").stdout.strip()
    if not url:
        return None
    match = _GITHUB_URL_RE.search(url)
    return match.group("slug") if match else None


def _branches(repo: Path) -> set[str]:
    names: set[str] = set()
    for args in (
        ("branch", "--format=%(refname:short)"),
        ("branch", "-r", "--format=%(refname:short)"),
    ):
        for line in _git(repo, *args).stdout.splitlines():
            name = line.strip()
            if name.startswith("origin/"):
                name = name[len("origin/"):]
            if not name or name.endswith("/HEAD"):
                continue
            names.add(name)
    return names


def _default_branch(repo: Path, branches: set[str]) -> str:
    symbolic = _git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").stdout.strip()
    if symbolic:
        return symbolic.split("/", 1)[-1]
    for candidate in ("main", "master"):
        if candidate in branches:
            return candidate
    return "main"


def git_facts(repo: Path) -> dict:
    """Branch, head, default branch, local/remote branches, dirty paths."""
    repo = Path(repo)
    if not (repo / ".git").exists():
        raise VerifyUnavailable(f"{repo} is not a git repository")
    branches = _branches(repo)
    return {
        "branch": _git(repo, "branch", "--show-current").stdout.strip() or "(detached)",
        "head": _git(repo, "rev-parse", "--short", "HEAD").stdout.strip(),
        "default_branch": _default_branch(repo, branches),
        "branches": branches,
        "dirty": [line for line in _git(repo, "status", "--porcelain").stdout.splitlines() if line.strip()],
        "slug": remote_slug(repo),
    }


# ---------------------------------------------------------------- github facts

def _token() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    if not token:
        raise VerifyUnavailable("no GH_TOKEN/GITHUB_TOKEN set — set one to verify PRs and CI")
    return token


def _api(path: str):
    token = _token()
    url = f"https://api.github.com{path}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "openharness-reconcile",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as ex:
        if ex.code == 404:
            return None
        raise VerifyUnavailable(f"GitHub {ex.code} for {path}") from ex
    except (urllib.error.URLError, TimeoutError, ValueError) as ex:
        # Python builds on macOS often ship without CA certificates
        # (CERTIFICATE_VERIFY_FAILED); curl uses the system store, so fall back
        # to it rather than reporting the claim as unverifiable.
        return _api_via_curl(url, token, path, ex)


def _api_via_curl(url: str, token: str, path: str, original: Exception):
    curl = shutil.which("curl")
    if not curl:
        raise VerifyUnavailable(f"GitHub request failed for {path}: {original}") from original
    # Token goes through curl's stdin config, never through argv.
    config = (
        f'url = "{url}"\n'
        f'header = "Authorization: Bearer {token}"\n'
        'header = "Accept: application/vnd.github+json"\n'
        'header = "User-Agent: openharness-reconcile"\n'
    )
    run = sp.run(
        [curl, "-sS", "-K", "-", "--write-out", "\n%{http_code}"],
        input=config,
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        raise VerifyUnavailable(
            f"GitHub request failed for {path}: {run.stderr.strip() or original}"
        ) from original
    body, _, code = run.stdout.rpartition("\n")
    if code == "404":
        return None
    if not code.startswith("2"):
        raise VerifyUnavailable(f"GitHub {code} for {path}")
    try:
        return json.loads(body)
    except ValueError as ex:
        raise VerifyUnavailable(f"GitHub returned non-JSON for {path}") from ex


def pr_state(repo: Path, number: int) -> dict | None:
    """PR facts, or None when the PR does not exist."""
    slug = remote_slug(Path(repo))
    if not slug:
        raise VerifyUnavailable(f"{repo} has no github.com origin remote")
    data = _api(f"/repos/{slug}/pulls/{number}")
    if data is None:
        return None
    return {
        "number": data.get("number", number),
        "state": data.get("state", "unknown"),
        "merged": bool(data.get("merged") or data.get("merged_at")),
        "merge_commit_sha": data.get("merge_commit_sha") or "",
        "head_ref": (data.get("head") or {}).get("ref", ""),
        "head_sha": (data.get("head") or {}).get("sha", ""),
        "base_ref": (data.get("base") or {}).get("ref", ""),
        "url": data.get("html_url", ""),
    }


def checks_state(repo: Path, ref: str) -> dict:
    """Aggregate CI state for a commit: success | failure | pending."""
    slug = remote_slug(Path(repo))
    if not slug:
        raise VerifyUnavailable(f"{repo} has no github.com origin remote")
    data = _api(f"/repos/{slug}/commits/{ref}/check-runs?per_page=100") or {}
    runs = data.get("check_runs", [])
    failed = [
        run.get("name", "?")
        for run in runs
        if run.get("status") == "completed" and run.get("conclusion") not in _OK_CONCLUSIONS
    ]
    pending = [run for run in runs if run.get("status") != "completed"]
    if failed:
        state = "failure"
    elif pending:
        state = "pending"
    else:
        state = "success"
    return {"state": state, "total": len(runs), "failed": failed}


# ------------------------------------------------------------------ reconcile

def pr_number(reference: str) -> int | None:
    """Parse `#17`, `17`, or a PR URL into 17."""
    match = _PR_RE.search(reference or "")
    return int(match.group(1)) if match else None


def _check_done_wave(repo: Path, facts: dict, subject: str, row: dict, offline: bool) -> list[Finding]:
    number = pr_number(str(row.get("pr", "")))
    if number is None:
        return [Finding("drift", subject, "recorded done without a PR reference — the evidence cannot be checked")]
    if offline:
        return [Finding("unverified", subject, f"PR #{number} not checked (--offline)")]

    try:
        pr = pr_state(repo, number)
    except VerifyUnavailable as ex:
        return [Finding("unverified", subject, f"PR #{number}: {ex}")]
    if pr is None:
        return [Finding("drift", subject, f"recorded done with PR #{number}, but PR #{number} does not exist")]

    findings: list[Finding] = []
    if not pr["merged"]:
        findings.append(
            Finding("drift", subject, f"PR #{number} is {pr['state']} — recorded as done, but never merged")
        )
        return findings

    default = facts["default_branch"]
    if pr["base_ref"] and pr["base_ref"] != default:
        findings.append(
            Finding("drift", subject, f"PR #{number} was merged into `{pr['base_ref']}`, not the default `{default}`")
        )

    branch = str(row.get("branch", "")).strip()
    if pr["head_ref"] and branch and branch not in ("—", "-") and pr["head_ref"] != branch:
        findings.append(
            Finding("drift", subject, f"PR #{number} came from `{pr['head_ref']}`, but LOOP records `{branch}`")
        )

    sha = pr["merge_commit_sha"]
    if sha:
        ancestry = _git(repo, "merge-base", "--is-ancestor", sha, f"origin/{default}")
        if ancestry.returncode == 1:
            findings.append(
                Finding("drift", subject, f"merge commit {sha[:8]} is not on `origin/{default}` — the merge never landed")
            )
        elif ancestry.returncode != 0:
            findings.append(
                Finding("unverified", subject, f"cannot check whether {sha[:8]} is on `origin/{default}` (fetch or clone depth?)")
            )

    try:
        checks = checks_state(repo, sha or pr["head_sha"])
    except VerifyUnavailable as ex:
        findings.append(Finding("unverified", subject, f"CI for PR #{number}: {ex}"))
    else:
        where = sha[:8] if sha else "the PR head"
        if checks["total"] == 0:
            findings.append(Finding("unverified", subject, f"no CI check runs found for {where}"))
        elif checks["state"] == "failure":
            findings.append(
                Finding("drift", subject, f"CI failed for PR #{number}: {', '.join(checks['failed'][:5])}")
            )
        elif checks["state"] == "pending":
            findings.append(Finding("drift", subject, f"CI for PR #{number} has not finished ({checks['total']} checks)"))
        else:
            findings.append(
                Finding("info", subject, f"PR #{number} merged into `{default}` at {where}, CI success ({checks['total']} checks)")
            )
    return findings


def reconcile(
    repo: Path,
    wave_state: dict[int, dict],
    plan_waves: list[int],
    feature_status: str,
    offline: bool = False,
) -> list[Finding]:
    """Compare LOOP claims with git/GitHub facts. Read-only."""
    try:
        facts = git_facts(repo)
    except VerifyUnavailable as ex:
        return [Finding("unverified", "git", str(ex))]

    findings: list[Finding] = []
    for number in plan_waves:
        row = wave_state.get(number, {})
        status = row.get("status", "pending")
        subject = f"wave {number}"
        if status == "done":
            findings.extend(_check_done_wave(repo, facts, subject, row, offline))
        elif status == "in-progress":
            branch = str(row.get("branch", "")).strip()
            if not branch or branch in ("—", "-"):
                findings.append(Finding("drift", subject, "recorded in progress without a branch"))
            elif branch not in facts["branches"]:
                findings.append(
                    Finding("drift", subject, f"recorded in progress on `{branch}`, which exists neither locally nor on origin")
                )
            else:
                findings.append(Finding("info", subject, f"in progress on `{branch}`"))

    for number in sorted(set(wave_state) - set(plan_waves)):
        if wave_state[number].get("status") not in (None, "pending"):
            findings.append(
                Finding("drift", f"wave {number}", "recorded in LOOP state but not planned in WAVES.md")
            )

    if feature_status == "done":
        pending = [n for n in plan_waves if wave_state.get(n, {}).get("status") != "done"]
        if pending:
            findings.append(
                Finding("drift", "feature", f"marked done but waves {', '.join(map(str, pending))} are not done")
            )

    if facts["dirty"]:
        shown = ", ".join(path.strip()[:60] for path in facts["dirty"][:5])
        findings.append(
            Finding("warning", "worktree", f"{len(facts['dirty'])} uncommitted path(s): {shown}")
        )
    return findings
