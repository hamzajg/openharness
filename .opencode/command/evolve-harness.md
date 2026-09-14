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
(see REPOS.md). Never guess.

## Layered ENV
If sources/<repo>/.openharness/ENV.md exists, prefer it over the global
.openharness/ENV.md for that repo. Compare with the live env probe
output and surface any drift; do not silently choose.

## Workflow — follow SELF/EVOLUTION.md EXACTLY

1. Read `SELF/PRINCIPLES.md` first. Confirm no violation of D001–D008. If a change would violate, first propose D00N+1 that explicitly supersedes.

2. Design the smallest possible change. No speculative abstractions.

3. Implement:
   - Code under `openharness/` or `skills/`
   - Same-commit rule: update corresponding `SELF/blocks/<block>.md` in the same edit set
   - If skills changed, run the equivalent of `/sync` to update `.claude/commands/` and `.opencode/command/`

4. Run tests:
   ```bash
   pytest
   ```
   Fix failures; do NOT weaken tests.

5. Report LOC counts (before & after affected bucket):
   - Runtime core (≤ 300 LOC): `find openharness -name "*.py" -not -path "*/web/*" -not -name "serve*.py" -not -path "*/observers/*" | xargs wc -l`
   - Serve/UI block (≤ 900 LOC): tally serve.py, serve_api.py, observers/*.py, web source files.

6. Present PR: title `evolve: <summary>`, body with applicable D00N refs, passing pytest output, LOC counts.
