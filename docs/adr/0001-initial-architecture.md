# ADR 0001 — Initial architecture

Date: 2026-11-13 (baseline recorded retroactively; the authoritative
decision log is `SELF/PRINCIPLES.md` D001–D008 — this ADR summarises it)
Status: accepted (describes what is built)

## Context

OpenHarness supports multi-repo agentic work without becoming a second
orchestrator or a cloud service. It must stay small, local, and
agent-agnostic.

## Decisions

1. **No orchestration (D001).** The harness never launches agents, schedules
   tasks, or runs DAGs — the agent CLI already does that. Rationale: one
   orchestrator, one source of truth.
2. **Markdown for specs, Python for execution (D002/D004).** Everything
   read by agents/humans is `.md` with optional YAML frontmatter; skills
   and runtime are `.py`. Rationale: native to agent CLIs, no extra spec
   parser beyond ~15 LOC.
3. **Complexity budgets (D003).** Runtime core ≤ ~300 LOC; serve/UI block
   ~900 LOC. Rationale: LOC discipline keeps it a tool, not a platform.
4. **Local-first, file-based state.** ChromaDB + sentence-transformers for
   RAG; all state on disk. Rationale: privacy, zero infra, reconstructable.
5. **Observation by log-tailing only (D006).** The harness reads session
   JSONL the agent CLIs already write — no vendor SDKs, no hooks. Rationale:
   vendor APIs change; logs are stable.
6. **REPOS.md + `sources/` registry (D007).** One table → clones;
   `sources/` gitignored and rebuildable via `pull`. Rationale: clean repo,
   user's own git credentials, no token management.
7. **Web UI is an observer (D005).** It calls the same verbs and reads the
   same files; zero business logic in TSX. Rationale: two implementations
   guarantee drift.
8. **Harness never copied into target repos (D008).** Central mode only —
   agent CLIs discover commands by walking up from cwd. Rationale: no
   divergence, pristine checkouts.

## Consequences

- The harness can only observe what agent CLIs record — blind spots are
  accepted over instrumentation.
- LOC budgets mean features must justify space; growth requires revisiting
  D003 deliberately.
- `sources/` clones are disposable — never the source of truth.
