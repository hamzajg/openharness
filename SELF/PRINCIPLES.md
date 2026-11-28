---
name: PRINCIPLES
type: principles
---
# Standing Principles

## KISS
Keep It Simple, Stupid. No frameworks beyond the explicitly listed ones. No abstractions "for the future." Complexity budget D003 is enforced on every commit.

## Sustainable Outcomes (D018)
Good software is not code volume. It solves a meaningful problem for
identified users, creates measurable value, delivers it reliably, and stays
economically sustainable to operate and evolve. Judge work on five dimensions
— business/user value, economic viability, UX/adoption, technical/operational
quality, and adaptability/longevity — and report outcomes, not output. These
are lenses for judgment, not a scoring engine.

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
Rule: sources/ is reconstructable via `python -m openharness pull`. Auth relies on the user's existing git credentials only. The tracked REPOS.md is an agnostic template; `/init` writes the concrete list to `.openharness/REPOS.local.md` (gitignored by default), which becomes the active registry when present. Only one registry is active at a time — never a merge of both.
Because: Keeps the harness repo clean and shareable as a framework. One table → one place to edit. No token management surface.

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
≤ 300 LOC (ceiling revised to 330 by D016). **Platform** — workspace + observation plumbing (`repos.py`,
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

Rule: `review_delivery` (D013) writes a `Repo: <path>` header into every
`SPEC-AUDIT.md` / `DELIVERY-AUDIT.md` it generates. Those files are
committed into the *target* repo and shipped in PRs, so the header must
never contain an absolute path under the operator's home directory
(`/home/<user>/...`, `C:\Users\<user>\...`). Emit it as `~`-prefixed
instead: collapse `Path.home()` to `~` and fall back to the raw path only
when the repo is not under the home dir. More generally, any skill that emits
a path into a file that will be committed into a target repo must run it
through `_display_path` (or equivalent) first.

Because: The harness's whole value is that it writes into other people's
repositories. An audit tool that leaks the operator's home path is a
privacy regression in the one place its output is most visible — the
committed spec dir. `~` is the standard, portable shorthand and preserves
readability.

### D015 — TDD is the default wave cycle, proven by evidence

Rule: Every wave runs red → green → refactor and proves it in its
evidence bundle: a `tdd: red` step that fails as expected, a `tdd: green`
step that passes, and a `tdd: refactor` step that re-runs the suite after
the KISS/DRY/SOLID review — required even when no code changed. The oracle
(`ship_loop --action=complete`/`finish`) rejects a wave bundle without an
ordered sequence; `--force` remains the escape. Tests are written from the
spec's scenarios first — specification by example upstream, failing test
downstream — never reverse-engineered after the implementation.

Because: "Write tests first" was already agent guidance; guidance is not
enforcement. The expensive failure is a plausible `VALIDATION.md` built on
tests written to fit code that already existed — they pass, they cite the
scenario, and they prove nothing about order. The bundle's recorded,
hashed, timestamped command runs are the only place order can be proven
without brittle git archaeology, so the cycle lives there (ADR 0008). The
refactor step stays mandatory because "nothing to refactor" is itself a
claim that deserves a green re-run, not an absence of evidence.

### D016 — Core budget ceiling follows the permanent guard surface

Rule: D012's core bucket ceiling is raised from 300 to 330 LOC; platform stays
at 1100. The permanent additions since D012 are the pre-import Python-version
guard (module-level `X | Y` annotations crash old interpreters before any
message can be shown), the `SkillError` contract that makes refusals loud
rather than silent, and the `--` passthrough for evidence command steps.
Seven lines were removed from the CLI dispatcher before raising the ceiling.
`tests/test_budgets.py` reads the same counters as `GET /api/evolution` and
fails CI if either bucket exceeds its ceiling; deleting code still comes
before any further raise, which needs a new decision that says what it
supersedes.

Because: The budget's purpose is KISS pressure on the agent-facing contract,
not ritual. Holding 300 after those three permanent additions would reward
deleting useful behavior or hiding code in another bucket. An explicit ceiling
plus a CI gate keeps the pressure honest and visible instead of letting the
dashboard warn while every PR merges.

### D017 — Outcomes over output; the value contract precedes planning

Rule: A spec carries a one-page, parseable `## Value contract` before any
wave is planned: problem, users, baseline/current cost, target outcome
indicator (numeric target + window), economic hypothesis (lifecycle cost vs
benefit, including adoption), and owner/date. `spec_scaffold` emits the
section and a blocking `G0 — Value contract filled` gate (`Before: plan`,
`Check: file:specs/<feature>/SPEC.md`); `ship_loop` refuses to mark that
gate met while any field is a template placeholder or the target has no
number, and treats a later regression as a stale gate. `review_delivery`
reports a missing/unmeasurable contract as `CONCERNS`, never `BLOCK`.
`challenge_decision` gains a value/economics lens — still advisory, never a
gate (D011). `VALIDATION.md` may record baseline, target, adoption and TCO
observations after release, but `done` still means acceptance-validated
(D009), not measured in production.

Because: When AI makes code cheap, output stops being evidence of value. A
feature can ship on time, pass every test and still solve a problem nobody
has. Asking for the value gap *before* planning forces the expensive question
while it is still cheap to change direction; leaving outcome measurement
after release keeps the oracle honest about what it can know. The contract is
a short spec field and an existing gate mechanism — no scoring engine, no ROI
calculator, no business dashboard, no new runtime module (ADR 0009).

### D018 — Good software is sustainable outcomes, not output

Rule: Judge every feature and decision on five dimensions:
(1) business and user value — a real problem and a meaningful outcome;
(2) economic viability — lifecycle benefit justifies build, operate, adopt,
migrate and support cost; (3) UX and adoption — users can and actually do
achieve their objectives; (4) technical and operational quality — correct,
secure, reliable, performant and maintainable; (5) adaptability and longevity
— the system can evolve without disproportionate cost.

Quality has three levels: product (works for its users), system (behaves
correctly and safely) and business (remains a good investment). Technical
quality is an enabler, not the goal. Delivery reports lead with outcome
evidence — time, error rate, adoption, cost — and treat features, APIs and
coverage as supporting output. A technically excellent system nobody uses, a
popular system that loses money indefinitely, and a profitable system that
risks customer data are all failures of different dimensions.

These dimensions are advisory lenses in `product-framer`,
`challenge_decision` and `delivery-auditor`; they never become a score, a
dashboard, a gate or a runtime module. D017's value contract remains the
pre-planning artifact. KISS remains the implementation discipline: prefer the
simplest intervention that delivers the outcome, including not building it.

Because: AI lowers the cost of producing code, not the cost of producing the
wrong code. Cheap implementation makes wrong problems, unnecessary
complexity, duplicate capability, security and operational debt, and unused
software more expensive relative to the code itself. The scarce work is
choosing what is worth building, validating assumptions, integrating with
real processes, and measuring whether the outcome improved (ADR 0010).

### D019 — The domain model and the experience are spec artifacts

Rule: Every feature carries two contracts beyond the value contract.
`DOMAIN.md` captures the ubiquitous language (one agreed word per concept),
the bounded contexts that own each concept, the aggregates and invariants,
the transaction boundary, and how external models are translated. `SPEC.md`
carries `## Experience`: the primary user journey, the edge states that
matter, a concrete UX bar, and accessibility notes.

Both scale with a declared tier — `simple | standard | domain-heavy` — but
`tier` controls required *depth*, never existence. A `simple` feature still
names its owning context and states "no new domain concepts" explicitly; a
user-facing feature still names its journey or declares `N/A — <reason>`.
A bare `N/A` is rejected: skipping is an explicit, reviewable decision, not
a silent default. Scaffold gates G2 (DOMAIN.md) and G3 (`## Experience`)
block wave planning until both are filled; only a named human may waive
them. Deterministic checks prove presence and non-placeholder content —
whether a `domain-heavy` model is *real* is semantic judgment for the spec
audit, the challenger and the wave reviewer (ADR 0011).

Because: AI agents invent vocabulary freely — the same concept gets three
names across spec, code and UI, boundaries are redrawn per wave, and
invariants leak into callers. Specs that skip the domain model produce
plausible-looking waves that do not compose. The experience contract does
the same for UX: "intuitive" is ungradeable until it is written down as a
journey, edge states and a bar a reviewer can check (ADR 0011).

### D020 — Scenario maturity is a spec artifact

Rule: `EXAMPLES.feature` must describe observable behavior beyond the happy
path. Five axes are tagged on real scenarios: `@m-failure`
(retry/timeout/idempotency/partial failure/conflict), `@m-ownership`
(roles/ownership/isolation/revocation/audit), `@m-data` (persistence,
migration, import/export, search/pagination, eventual consistency), `@m-ux`
(empty/loading/error/denied/offline, undo, accessibility), and `@m-outcome`
(an observable signal tied to D017's numeric target). An axis that genuinely
does not apply must be justified outside a scenario with `# Maturity N/A:
@m-<axis> — <reason>`; a bare `N/A` or placeholder is rejected. Added value
arrives in small waves: each new axis gets its own `@w<N>` wave and a dedicated
scenario, and the happy path gets its own scenario. More than one scenario for
the SAME axis in one wave is depth; several different axes in one wave is the
big-bang iteration this decision forbids.

The DOMAIN.md tier controls depth, never presence: `simple` needs a happy path
and at least 2 exercised axes, `standard` needs 3 including failure (and UX
covered or justified), `domain-heavy` needs every axis covered or justified
plus at least 3 exercised, including failure and data. `spec_scaffold` emits
blocking gate `G4 — Scenario maturity floor` (`Before: plan`,
`Check: file:specs/<feature>/EXAMPLES.feature`); `ship_loop` refuses to mark
it met while the axis floor is unmet and treats a later regression as stale.
`review_delivery` reports `maturity-axis-missing`, `maturity-na-unjustified`,
`maturity-tag-unknown`, `maturity-scenario-mixed`, `maturity-wave-crowded` and
`maturity-axis-untagged` as advisory concerns; `wave_plan` warns on crowded
waves without changing wave order, and `ship_validate` reports the first wave
per covered axis in `VALIDATION.md`. Deterministic checks prove breadth, not quality:
whether a scenario actually exercises the axis remains semantic judgment for
the spec audit, challenger and wave reviewer. Innovation means closing real
maturity gaps that create product value, not adding frameworks to look mature
(D018).

Because: happy-path-only examples pass every traceability check while
proving nothing about operation in the real world. Agents optimize for the
demo they can imagine, so the product stops at primitive use cases that
would not survive multi-user use, failure, reload, or a measured outcome.
Putting the axes in the spec artifact — with the same shallow gate pattern as
D017/D019 — forces the expensive questions while they are still cheap to
change, and leaves a reviewable trace from value contract to executable
example (ADR 0015).
