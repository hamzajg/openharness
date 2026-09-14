---
name: PRINCIPLES
type: principles
---
# Standing Principles

## KISS
Keep It Simple, Stupid. No frameworks beyond the explicitly listed ones. No abstractions "for the future." Complexity budget D003 is enforced on every commit.

## Agent-Agnostic
No harness code may import or reference a specific vendor SDK. Agent differences are handled only in Markdown command files and thin "observer" modules that tail agent session log files.

## Markdown-for-Specs / Python-for-Execution (D002 boundary)
- If an agent or human must **READ** it → `.md` (with YAML frontmatter for machine-parsed fields).
- If a machine must **EXECUTE** it → `.py`.
Rule of thumb: specs, profiles, principles, decisions, command files → Markdown. Executable logic → Python.

## Local-First
No cloud dependency. RAG runs locally (ChromaDB + sentence-transformers). State = files on disk.

## UI is an Observer, Not a Runtime
The web UI calls the same runtime verbs the CLI uses and reads the same files. It never re-implements harness logic. **D005.**

---
# Decision Log

### D001 — No orchestration in the harness
Rule: The harness never launches agents, never schedules tasks, never runs a DAG.
Because: The agent host (claude / opencode) already provides scheduling, permissions, parallelism, and human-in-the-loop. Adding a second orchestration layer duplicates work and breaks the single source of truth.

### D002 — Skills are Python; specs and context are Markdown
Rule: Executable logic lives in `.py`; everything the agent/human reads lives in `.md`.
Because: Markdown is native to agent CLIs (CLAUDE.md, AGENTS.md, slash commands) — no extra parsing layer. Python gives type hints for skill contracts and is universally available.

### D003 — Complexity budget
Rule: Python runtime core ≤ 300 LOC total (`__main__.py`, `skill.py`, `registry.py`, `frontmatter.py`, `repos.py`, `knowledge/rag.py`, `env.py`). `serve.py` + `serve_api.py` + observers + web UI are a separate optional block with its own ~900 LOC budget.
Because: LOC is a crude but effective discipline for KISS. Without it, codebases balloon and contributors build castles instead of tools.

### D004 — Specs in Markdown with YAML frontmatter
Rule: Every spec file (SELF/, command files, ENV.md) is `.md` with optional `---\n...\n---\n` YAML frontmatter. No YAML/TOML spec files anywhere.
Because: Matches CLAUDE.md / AGENTS.md / slash-command ecosystem conventions. Agent CLIs render Markdown natively. Frontmatter parser is ~15 LOC, no PyYAML.

### D005 — The web UI never re-implements harness logic
Rule: UI calls the same runtime verbs the CLI uses and reads the same files. No business logic in TSX.
Because: Two implementations of the same logic guarantee drift. The API surface is small enough (catalog + run + search + sessions + self + env) that re-use is trivial.

### D006 — Harness only observes what agent CLIs already record on disk
Rule: No vendor instrumentation, no message injection, no SDK hooks. The harness tails JSONL session files that the CLI already writes.
Because: Vendor APIs change. Logs are stable. Tail is 20 lines of stdlib, not 2000 lines of vendor SDK.

### D007 — Target repos live in sources/ (gitignored); REPOS.md is source of truth
Rule: sources/ is reconstructable via `python -m openharness pull`. Auth relies on the user's existing git credentials only.
Because: Keeps the harness repo clean. One table → one place to edit. No token management surface.

### D008 — Central mode only
Rule: The harness is the workspace root. Harness files are never copied into target repos. Agent CLIs discover commands because sessions run inside the harness tree.
Because: Copying files into target repos means divergence and dirtying pristine checkouts. Walking up from cwd to find `.claude/commands/` is the CLI's native behavior.
