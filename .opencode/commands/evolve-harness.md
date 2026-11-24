---
description: Modify the harness itself following SELF/EVOLUTION.md exactly; propose smallest change, verify tests, present diff as PR
---
# /evolve-harness — Safe modifications to the harness

## Context

Run via Bash and read output:
- `python -m openharness self`
- `python -m openharness env`

## Target repo
If the session cwd is inside sources/<repo>, that repo is the default
target. Otherwise ask the user which managed repo to operate on
(see the active registry: REPOS.md or .openharness/REPOS.local.md). Never guess.

## Layered ENV
If sources/<repo>/.openharness/ENV.md exists, prefer it over the global
.openharness/ENV.md for that repo. Compare with the live env probe
output and surface any drift; do not silently choose.

## Workflow — follow SELF/EVOLUTION.md EXACTLY

1. Read `SELF/PRINCIPLES.md` first. Confirm no violation of D001–D019. If a change would violate, first propose D00N+1 that explicitly supersedes.

2. Design the smallest possible change. No speculative abstractions.

3. Implement:
   - Code under `openharness/` or `skills/`
   - Same-commit rule: update corresponding `SELF/blocks/<block>.md` in the same edit set
   - If skills changed, run the equivalent of `/sync` to update `.claude/commands/` and `.opencode/commands/`

4. Run tests:
   ```bash
   pytest
   ```
   Fix failures; do NOT weaken tests.

5. Report LOC counts (before & after) for the affected bucket — the same counters CI uses:
   - Core (≤ 330 LOC, D012/D016): `__main__.py`, `skill.py`, `registry.py`, `frontmatter.py`, `env.py`, `knowledge/rag.py`
   - Platform (≤ 1100 LOC): `repos.py`, `metrics.py`, `serve.py`, `serve_api.py`, `observers/*.py`
   - `GET /api/evolution` shows both; `pytest tests/test_budgets.py` enforces them. Delete code before growing a bucket.

6. Present PR: title `<type>: <summary>` (`feat`/`fix`/`docs`/`chore`, or `evolve` for a harness change), body with applicable D00N refs, passing pytest output, LOC counts.
