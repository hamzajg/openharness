---
name: EVOLUTION
type: rules
---
# Rules for Agents Modifying the Harness

## Before You Change Anything
1. **Read `SELF/PRINCIPLES.md` first.** Every decision D001–D018 is binding precedent.
2. Never violate a standing decision. If you must, **append D00N+1** with rationale that **explicitly supersedes** it. Reference the old decision by number.

## Block Spec Contract
3. Any new or changed building block → update its `SELF/blocks/*.md` in the **same commit** that changes the code. Block spec and code must agree.
4. Block frontmatter is authoritative: `name`, `type: block`, `location`, `interfaces` (list).

## Skills ⇄ Command Files Sync
5. After adding, removing, or renaming a skill: run the equivalent of `/sync` so slash command files stay in sync across `.claude/commands/` and `.opencode/commands/`.
6. Every command file that does engineering work **must** start with the awareness preamble (self + env outputs) and resolve the managed repo it operates on.

## LOC Budget (D003, split by D012)
7. Respect the two budgets (D012, ceiling revised by D016). Core =
   `__main__.py`, `skill.py`, `registry.py`, `frontmatter.py`, `env.py`,
   `knowledge/rag.py` → ≤ 330 LOC. Platform = `repos.py`, `metrics.py`,
   `observers/*`, `serve.py`, `serve_api.py` → ≤ 1100 LOC. Check via
   `GET /api/evolution` (`stats.core_loc`, `stats.platform_loc`) or count
   manually. `tests/test_budgets.py` checks both in CI.
8. If you blow a budget, **delete something first**. Rewrite two functions as one. Remove an abstraction. Default to less. Raising a ceiling needs a new decision that explicitly supersedes the old one (D016).

## Tests
9. `pytest` **must pass** before proposing the change.
10. New code path → new test. Coverage of runtime core should stay at 100%.

## New Files
11. New spec files are **always** `.md` with YAML frontmatter. (D004.)
12. New executable logic lives in `.py`, preferably under `skills/` (if user-facing) or `openharness/` (if plumbing).

## Presenting the Change
13. Title the PR: `evolve: <one-line summary>`.
14. Body must: (a) reference which SELF/PRINCIPLES decision(s) apply, (b) show `pytest` output, (c) show before/after LOC counts for the touched budget bucket.
