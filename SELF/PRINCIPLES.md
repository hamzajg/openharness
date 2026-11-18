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

### D009 — Delivery loops are agent-executed, not harness-scheduled
Rule: The product-delivery loop is a Markdown protocol (`/ship-loop` + four
subagent roles) plus a deterministic Python oracle
(`skills/product/ship_loop.py`). The agent calls the oracle once per iteration
and executes the returned action. The harness never launches an agent, daemon,
cron, or background worker. Loop state lives in `specs/<feature>/LOOP.md`
inside the target repo and is committed with that feature's PRs; `WAVES.md`
remains the immutable plan.
Because: This is D001 applied to product delivery. A deterministic oracle
makes the loop resumable after context loss, auditable (append-only event
log), and bounded (iteration budget) without adding a second orchestration
layer. Product artifacts (`specs/`, `LOOP.md`) are product content, not
harness files — D008 still forbids copying harness config into target repos.
The human gate stays explicit: default `--merge=review` leaves every PR open
for review; `--merge=auto` is opt-in.

### D010 — Gates are declared preconditions, not checkboxes
Rule: Phase transitions in the delivery loop are guarded by gates declared in
`specs/<feature>/GATES.md` and tracked in `LOOP.md`. A blocking gate stops the
phase it is attached to (`spec`/`plan`/`wave:<n>`/`validate`/`finish`) until it
is `met` with evidence or `waived` by a named human. Overdue gates keep
blocking; invalid `Before` values block every phase; advisory (`Blocking: no`)
gates never block. The oracle verifies `file:` evidence; `command:` checks are
run and recorded by the agent — the oracle never executes repo-provided
commands.
Because: Complex domains (regulated claims, billing, healthcare, data
pipelines) fail when code is written against undecided business rules or
missing access. Gates make those preconditions explicit, owned, and
falsifiable before a wave starts, so the loop stops honestly instead of
inventing rules or silently skipping sign-off. The agent resolves only
agent-owned gates; human-owned gates are handed back via `block`, preserving
the human-in-the-loop boundary in D001/D009.

### D011 — Design decisions get an optional challenge, not a gate
Rule: A design/architecture decision may be reviewed with `/challenge-decision`
(`skills/product/challenge_decision.py` + the `decision-challenger` subagent).
The deterministic skill assembles a brief — record completeness, heuristic code
signals, design moves, and lens questions for DDD, architecture, testability,
and craftsmanship — and the agent supplies the judgment, alternatives,
tradeoff matrix, scores, and verdict (`ACCEPT`/`REVISE`/`REVISIT`/`SPLIT`).
The review is advisory: it never blocks a gate, wave, merge, or loop
iteration, and it writes only a review document under `specs/` or `docs/adr/`.
Because: Complex domains need their design challenged before the cost of
change is high, but making every design opinion a blocking gate turns the loop
into ceremony and gives a reviewer veto power over the product. Separating a
deterministic brief from an evidence-based agent review keeps the challenge
rigorous and cheap while preserving D001/D009: the agent chooses to run it,
and the harness never schedules it.

### D012 — Complexity budget splits into core and platform buckets
Rule: D003's single 300-LOC core budget is superseded by two buckets.
**Core** — the agent-facing runtime (`__main__.py`, `skill.py`,
`registry.py`, `frontmatter.py`, `env.py`, `knowledge/rag.py`) — stays
≤ 300 LOC. **Platform** — workspace + observation plumbing (`repos.py`,
`metrics.py`, `observers/*`, `serve.py`, `serve_api.py`) — gets ≤ 1100
LOC. D003's separate ~900 serve+observers+UI budget is absorbed into
platform. Both budgets are enforced on every commit exactly as D003
required; only the file enumeration is redrawn.
Because: D003's file list predates `metrics.py`, `observers/`, and the
growth of `serve_api.py`. `repos.py` is workspace plumbing shared by the
CLI (`oh pull`) and the serve API — forcing it into the skill-runtime
bucket or into the serve block would both be bad layering. The budget's
intent was always to discipline the small contract surface agents depend
on; two honest buckets preserve that pressure without gaming the metric
or contorting the architecture.

### D013 — Spec and delivery get an independent audit before they count
Rule: A feature may be audited at two checkpoints: `SPEC-AUDIT.md` after
`SPEC.md`/`EXAMPLES.feature`/`BACKLOG.md` exist and before `wave_plan`/wave 1,
and `DELIVERY-AUDIT.md` after `VALIDATION.md` and before `finish`. The
deterministic skill `review_delivery` builds an evidence brief — artifact
presence, AC → scenario → wave → backlog → LOOP traceability, existence of
every claimed path/script/endpoint/ADR, placeholder evidence, scope drift,
and unfinished markers — and the independent `delivery-auditor` subagent
re-verifies each finding against the repository and fills exactly one
`AUDIT: PASS|CONCERNS|BLOCK`. `BLOCK` on any confirmed blocker, hallucinated
claim, or unproven acceptance criterion; `CONCERNS` only when every remaining
item is non-blocking and explicitly accepted; `PASS` only when all lists are
empty. `ship_loop` defaults to `--review=required`, which refuses to plan
without a filled spec audit, refuses to start wave 1 until the spec audit
passes, and refuses to finish without a filled delivery audit;
`--review=advisory` remains as an explicit opt-out. The audit never marks a
gate, never merges, and never edits product code.
Because: Gates (D010) check *whether* a precondition exists; they do not
check whether the spec is grounded in the repository or whether the delivery
matches the spec. The expensive failure is not a red test — it is a green
loop built on an invented path, a scenario that does not exist, or an
acceptance criterion with no real proof. A reviewer that trusts the artifacts
cannot catch that; only one that opens the code and tests can. Keeping the
deterministic brief separate from the judgment keeps the evidence auditable
and the reviewer honest, and keeping enforcement opt-in preserves existing
loops that opt out explicitly and the advisory principle of D011.

### D014 — Audit output must not leak absolute host paths

`review_delivery` (D013) writes a `Repo: <path>` header into every
`SPEC-AUDIT.md` / `DELIVERY-AUDIT.md` it generates. Those files are
committed into the *target* repo and shipped in PRs, so the header must
never contain an absolute path under the operator's home directory
(`/home/<user>/...`, `C:\Users\<user>\...`). Emit it as `~`-prefixed
instead: collapse `Path.home()` to `~` and fall back to the raw path only
when the repo is not under the home dir.

Because: The harness's whole value is that it writes into other people's
repositories. An audit tool that leaks the operator's home path is a
privacy regression in the one place its output is most visible — the
committed spec dir. `~` is the standard, portable shorthand and preserves
readability.

Rule: any skill that emits a path into a file that will be committed into a
target repo must run it through `_display_path` (or equivalent) first.
