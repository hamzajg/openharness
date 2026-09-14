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
(see REPOS.md). Never guess.

## Layered ENV
If sources/<repo>/.openharness/ENV.md exists, prefer it over the global
.openharness/ENV.md for that repo. Compare with the live env probe
output and surface any drift; do not silently choose.

## Workflow — follow SELF/EVOLUTION.md EXACTLY

1. **Read `SELF/PRINCIPLES.md` first.** Confirm the proposed change does not violate D001–D008. If it would, you MUST first propose a new D00N+1 decision that explicitly supersedes the old one, and only then proceed.

2. Design the **smallest possible change** that achieves the user's goal. No speculative abstractions. No "for the future."

3. Implement:
   - Code changes under `openharness/` or `skills/`
   - **Same commit rule**: for any touched building block, update its `SELF/blocks/<block>.md` in the same edit set.
   - If skills were added/removed/renamed, run the equivalent of `/sync` to update `.claude/commands/` and `.opencode/command/`.

4. Run the tests:
   ```
   !`pytest`
   ```
   If any test fails, fix the code. Do NOT weaken tests.

5. Compute and report LOC counts (before & after for the affected budget bucket):
   - Runtime core (≤ 300 LOC): `find openharness -name "*.py" -not -path "*/web/*" -not -name "serve*.py" -not -path "*/observers/*" | xargs wc -l`
   - Serve/UI block (≤ 900 LOC): tally `serve.py`, `serve_api.py`, `observers/*.py`, and the web source files.

6. Present the change as a PR summary with title `evolve: <one-line summary>` and body referencing which D00N decisions apply, passing pytest output, and LOC counts.
