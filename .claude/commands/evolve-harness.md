---
description: Modify the harness itself following SELF/EVOLUTION.md exactly; propose smallest change, verify tests, present diff as PR
allowed-tools: [Bash, Read, Grep, Edit, Write]
---
# /evolve-harness — Safe modifications to the harness

## Context
!`python -m openharness self`
!`python -m openharness env`

## Target repo
If the session cwd is inside sources/<repo>, that repo is the default
target. Otherwise ask the user which managed repo to operate on
(see the active registry: REPOS.md or .openharness/REPOS.local.md). Never guess.

## Layered ENV
If sources/<repo>/.openharness/ENV.md exists, prefer it over the global
.openharness/ENV.md for that repo. Compare with the live env probe
output and surface any drift; do not silently choose.

## Workflow — follow SELF/EVOLUTION.md EXACTLY

1. **Read `SELF/PRINCIPLES.md` first.** Confirm the proposed change does not violate D001–D019. If it would, you MUST first propose a new D00N+1 decision that explicitly supersedes the old one, and only then proceed.

2. Design the **smallest possible change** that achieves the user's goal. No speculative abstractions. No "for the future."

3. Implement:
   - Code changes under `openharness/` or `skills/`
   - **Same commit rule**: for any touched building block, update its `SELF/blocks/<block>.md` in the same edit set.
   - If skills were added/removed/renamed, run the equivalent of `/sync` to update `.claude/commands/` and `.opencode/commands/`.

4. Run the tests:
   ```
   !`pytest`
   ```
   If any test fails, fix the code. Do NOT weaken tests.

5. Compute and report LOC counts (before & after) for the affected bucket — the same counters CI uses:
   - Core (≤ 330 LOC, D012/D016): `__main__.py`, `skill.py`, `registry.py`, `frontmatter.py`, `env.py`, `knowledge/rag.py`
   - Platform (≤ 1100 LOC): `repos.py`, `metrics.py`, `serve.py`, `serve_api.py`, `observers/*.py`
   - `GET /api/evolution` shows both; `pytest tests/test_budgets.py` enforces them. Delete code before growing a bucket.

6. Present the change as a PR summary titled `<type>: <one-line summary>` (`feat`/`fix`/`docs`/`chore`, or `evolve` for a harness change) with a body referencing which D00N decisions apply, passing pytest output, and LOC counts.
