# ADR 0004 — Audit files must not emit absolute host paths

Date: 2026-11-17
Status: accepted

## Context

`skills/product/review_delivery.py` writes a `Repo: <path>` header into every
`SPEC-AUDIT.md` / `DELIVERY-AUDIT.md` it generates. It used the raw resolved
repository root, so on this machine the header read:

    - Repo: `/home/kali/factory/openharness/sources/JavaMicroservicesDDD`

Those audit files are committed into the *target* repo and shipped in PRs.
An absolute path under `/home/<user>/` leaks the host user's home directory
into a remote the user may not want exposed — a privacy/security regression
introduced by a tool that exists to *prove* things about the repo.

## Decision

Collapse the user's home directory to `~` before emitting any path in
human-facing audit output. Add `_display_path(path)` in
`skills/product/review_delivery.py` and use it for the `Repo:` header:

```python
def _display_path(path: Path) -> str:
    try:
        home = Path.home()
        rel = path.resolve().relative_to(home)
        return f"~/{rel}"
    except (ValueError, OSError):
        return str(path)
```

`_rel(root, spec_dir)` is intentionally left alone — it already returns a
repo-relative path (`specs/<feature>`), which is safe and more useful.

## Alternatives considered

1. **Strip the path entirely.** Rejected: the header is useful for humans
   reading the audit locally; `~` is the standard, portable shorthand.
2. **Resolve against `$HOME` only when it is an ancestor.** Chosen — the
   `except (ValueError, OSError)` fallback keeps the original behaviour on
   systems where the repo is not under the home dir (e.g. `/workspace`,
   `/tmp`).
3. **Redact with a placeholder like `<repo>`.** Rejected: less readable
   than `~` and loses the directory name.

## Consequences

- Positive: no absolute host path reaches a committed audit file.
- Positive: audits still read naturally (`Repo: ~/...`).
- Negative: none measurable.
- Revisit trigger: if the harness ever runs on Windows (different home
  semantics) or if a future skill emits absolute paths elsewhere.

## Verification

- New test `test_audit_rewrites_home_path_to_tilde` in
  `tests/test_review_delivery.py` copies the spec tree under the real home
  dir and asserts the header reads `~/.openharness-audit-test-<pid>` and
  that `/home/` appears nowhere in the output.
- Full suite: `pytest` → 266 passed, 1 skipped (unchanged baseline).