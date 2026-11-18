# ADR 0007 — Evidence bundles and the walkthrough page

Status: accepted · 2026-11-16 · phase 1 implemented 2026-11-17 ·
phase 2a implemented 2026-11-17 · amended 2026-11-17 (tracked root) ·
relates to D009 (delivery loop), D013 (delivery audit)

## Context

The loop records evidence as free text in `LOOP.md`:

```
pytest 12 passed; CI green
```

`review_delivery` already rejects placeholders and weak token matches, and a
gate marked met must point at a path or command output. That stops "done"
being typed into existence. It does not let anyone *see* the run.

When a wave touches a UI, the honest evidence is a picture or a short
recording, not a sentence: which screen, what was clicked, what the response
looked like, what the console said. Today those live in the agent's chat
transcript and are gone by the next session. A reviewer on the PR sees a
summary and a green check and has to re-run the branch to know what happened.

So the harness needs a first-class evidence artifact: produced per run,
deterministic, reviewable without re-running anything, and checkable by the
oracle so a stale or fabricated bundle cannot back a `done` wave.

### What the community actually does

Surveyed practice converges on four rules and one shape.

**Rule 1 — rich media is failure-scoped, structure is not.** Playwright's own
guidance is `screenshot: 'only-on-failure'`, `video: 'retain-on-failure'`,
`trace: 'retain-on-failure'`, with the HTML report uploaded on every run — the
report is cheap, video is not. Its CI docs upload `playwright-report/` with
`if: !cancelled()` and keep traces/screenshots/videos behind `if: failure()`.
The same split appears in CI guidance: JUnit + HTML always, traces and video
on failure, short retention for heavy artifacts.

**Rule 2 — a screenshot is not an evidence artifact.** A screenshot preserves
pixels, not provenance: which run, which source, what was redacted, whether
the file changed afterwards. The recommended shape is a package —
`evidence.html`, `summary.md`, the run's logs, check results, a redaction
report and an `evidence.json` of hashes — that a reviewer can verify offline.

**Rule 3 — one link, not a folder.** Playwright's default reporter emits a
*directory*; the recurring complaint is that nobody can open it. The tools
that get shared either inline everything (monocart-reporter produces a
self-contained `report.html`) or seal a zip with a viewer inside
(kane-cli's `.evidence` pack, GSD browser's export bundle, proofshot's
`viewer.html` + `session.webm` + `SUMMARY.md` + `step-*.png` +
`session-log.json`). Agent-specific products land on the same set: Currents
"agent evidence" is screenshots + video + trace + logs behind one link.

**Rule 4 — the artifact must be generated, not authored.** Allure's model is
attachments per step with declared MIME types; SHAFT adds a self-contained
`trace.html` next to the raw archive; agent-inspect derives a redacted package
from read-only source traces. In every case the human writes nothing into the
evidence; a tool assembles it from the run.

**One shape:** a run directory with a machine-readable manifest, the raw media,
the logs, and one generated HTML entry point — plus a summary that survives
being pasted into a PR.

### What this harness is not allowed to become

D001: the harness never launches agents and never becomes a scheduler. It
therefore must not grow its own browser automation. Whatever drives the UI —
Playwright in the repo, the agent's preview tools, a human — *produces files*;
the harness's job starts at the manifest.

## Decision

Three layers, deliberately separable, shipped in that order.

### 1. The contract — two roots, scratch by default

```
.openharness/evidence/<feature>/<run-id>/   # default: local scratch
evidence/<feature>/<run-id>/                # --tracked: meant to be committed
├── evidence.json      # manifest, schema below (the authoritative record)
├── index.html         # generated walkthrough (never edited by hand)
├── SUMMARY.md         # 20-line summary for a PR comment or LOOP.md row
├── raw/               # media exactly as captured (png, webm, trace.zip, har)
└── logs/              # one .log per executed command, plus app server logs
```

`<run-id>` is `YYYYMMDDTHHMMSSZ-<sha7>` — sortable, and the sha makes a stale
bundle obvious at a glance.

#### Where bundles live — scratch by default, tracked on request

`.openharness/evidence/` is a **local scratch directory**, the same tier as
the existing `.openharness/chroma/`: created on demand, listed in
`.gitignore`, and never committed. Evidence is proof of a run on this
machine, not a product artifact; committing megabytes of PNG and WebM would
bloat history and rot as files move.

The exception is explicit: `--action=new --tracked` places the bundle under
`<repo>/evidence/<feature>/<run-id>/`, a normal tracked folder, for the case
where a run's proof should travel with the repo (a public demo, a compliance
record, a walkthrough a reviewer must see in the PR itself). Nothing is ever
committed automatically — the harness writes files only; `git add`/commit/push
stay a human or agent decision. `verify` enforces the split both ways: a
scratch bundle that git tracks is an error, and a bundle under `evidence/`
that git does not yet track draws an `untracked-bundle` warning.

| consumer | what they get |
|---|---|
| the agent, next iteration | the whole bundle, by path |
| the human reviewing the PR | `SUMMARY.md` pasted into the PR body or comment |
| CI / a teammate who needs the full thing | `<run-id>.zip` uploaded as a CI artifact (P4), retained ~14 days |
| a repo that must carry its proof | the bundle under `evidence/`, committed via `--tracked` |
| an evidence service, later | the bundle, if someone opts in |

Only `SUMMARY.md` is designed to travel into the repo as prose (a handful of
lines in `LOOP.md` or a PR body). A full committed bundle is opt-in via
`--tracked` and never automatic.

The skill resolves both roots — `<repo>/.openharness/evidence` and
`<repo>/evidence` — honours `--bundle=<path>` for anything else, and `verify`
fails if a scratch bundle sits in a tracked directory (`git ls-files` on its
path returns anything) — that is how "scratch stays local" is enforced rather
than promised.

Manifest v1 (JSON, all paths relative to the bundle):

```jsonc
{
  "schema": "openharness.evidence/1",
  "feature": "workflow-definitions",
  "wave": 3,
  "run_id": "20261116T101500Z-6c55d0d",
  "created_at": "2026-11-16T10:15:00Z",
  "repo": {"slug": "hamzajg/stream-weave-platform", "branch": "feat/x",
           "head": "6c55d0d…", "base": "main"},
  "ci": {"pr": 22, "url": "…", "sha": "6c55d0d…", "conclusion": "success"},
  "verdict": "pass",                       // pass | fail | partial
  "summary": "Create + draft write tools, 20 tests, UI untouched.",
  "not_verified": ["real LLM proposing the tools", "webapp layout"],
  "steps": [
    {
      "id": "s1", "title": "Backend tests", "kind": "command", // command|browser|api|manual
      "status": "pass",                                     // pass|fail|skip|manual
      "started_at": "…", "duration_ms": 59410,
      "cmd": "pytest -q", "cwd": ".",
      "exit_code": 0,
      "log": "logs/s1.log",
      "artifacts": [
        {"path": "raw/s1/console.txt", "mime": "text/plain", "sha256": "…", "bytes": 812}
      ],
      "note": "97 passed"
    }
  ],
  "redactions": [{"path": "logs/s2.log", "pattern": "Authorization", "count": 2}],
  "environment": {"os": "darwin", "python": "3.13.13", "node": "20"}
}
```

Rules:

- Every artifact carries `sha256` and `bytes`; a path that does not resolve is
  a hard error, not a warning.
- `kind: command` steps are produced by the harness itself (see layer 3), so
  their exit code is not self-reported.
- `not_verified` is required. An empty list is allowed but must be written
  deliberately — this is where "I did not look at the UI" lives.

### 2. The renderer — `openharness/evidence.py` + `harness_evidence` skill

Deterministic, stdlib-only, no network, no build step. Actions:

| action | what it does |
|---|---|
| `render` | build `index.html` + `SUMMARY.md` from `evidence.json` |
| `verify` | schema, hash, commit, CI and policy checks; exit 2 on failure |
| `attach` | register an already-captured file as an artifact of a step |
| `step` | run a command, capture log + exit code + duration as a step |
| `list` | bundles per feature, newest first, with verdict and staleness |

The page is one HTML file with inline CSS and ~2KB of vanilla JS: no CDN, no
framework, no fonts fetched. A static mock of the target page lives at
[`docs/evidence-page-mock.html`](../evidence-page-mock.html) — open it in a
browser to judge the layout before any of this is built. Sections, in review
order:

1. **Header** — feature, wave, verdict pill, commit sha, branch, PR link, CI
   conclusion, run id, "generated from evidence.json" so nobody mistakes it
   for authored prose.
2. **What this proves** — the summary, then the `not_verified` list rendered
   as its own boxed section rather than a footnote.
3. **Walkthrough timeline** — one row per step: status, title, duration, the
   command, and a one-line note. Clicking a row opens its log.
4. **Screenshots** — a gallery with captions and step attribution; click for
   full size (CSS-only lightbox, arrow keys); the sha256 of each file is in
   the caption's title attribute, not hidden.
5. **Recording** — `<video controls preload="metadata">` with a poster frame
   taken from the first PNG, plus a download link; a note that the recording
   was captured by whatever drove the browser.
6. **Logs** — per-step panes, monospace, with a client-side filter box and a
   copy button; secrets already redacted at write time.
7. **Provenance** — manifest table (hashes, sizes, env), the CI run linked by
   sha, and the exact command that regenerated the page
   (`python -m openharness run harness_evidence --action=render …`).
8. **Redaction report** — what was scrubbed from which file, so a reviewer
   knows the log is complete-or-sanitized, not silently truncated.

Sharing modes:

- **default: folder.** `index.html` references `raw/` and `logs/` relatively.
  This is the honest artifact and it lives next to the run.
- **`--inline`:** a single self-contained `index.html` with PNGs and text
  base64-inlined and the video linked externally (base64 video turns a 5 MB
  recording into 7 MB of HTML and kills the browser). Refuses to inline above
  a size budget with the list of files that would be dropped.
- `zip` is the artifact format for CI upload; the zip contains the folder, and
  GitHub's own artifact download is what the PR comment links to.

### 3. Capture — the harness records commands, everything else is attached

The harness runs commands and records them honestly:

```
python -m openharness run harness_evidence --action=step --bundle=… \
  --title="Backend tests" -- pytest -q
```

Exit code, wall time, full stdout/stderr and cwd come from the process, not
from the agent's retelling. This works headless in CI and covers the majority
of waves.

Browser evidence is produced by the thing that drove the browser, then
attached:

- **Playwright repos:** a 15-line fixture (`evidence.fixture.ts`) writes
  `trace.zip`, `video.webm` and `step-*.png` into the run directory and emits
  a `steps.json` fragment; `attach --from=steps.json` folds it into the
  manifest. No new dependency for repos that do not use Playwright.
- **Agent previews:** the agent's own screenshot/recording tools write files;
  it calls `attach --step=<id> --file=<path> --caption="…"`. The skill refuses
  artifacts whose mtime predates the step, so an old screenshot cannot be
  passed off as this run.

Capture policy the skill recommends and `verify` enforces:

| artifact | when | retention |
|---|---|---|
| `evidence.json`, `index.html`, `SUMMARY.md`, logs | every run | with the wave |
| screenshots | every UI wave; failures everywhere | with the wave |
| video | UI waves over ~3 steps, and any failed UI step | latest run only |
| Playwright trace / HAR | failures, on request | latest run only |

### 4. Enforcement — a bundle that cannot lie

`ship_loop complete --wave=N --evidence="evidence:20261116T101500Z-6c55d0d"`
is now a valid evidence token, and `verify` is what makes it mean something:

- **commit match** — `manifest.repo.head` must equal the wave's branch HEAD
  (or the PR's merge sha once merged). Mismatch → `drift`, exactly like the
  reconcile action added for LOOP-vs-git.
- **CI match** — `manifest.ci.sha` must be a commit GitHub reports green; a
  bundle whose CI section points at a different sha proves nothing.
- **UI waves** — a wave whose changed paths touch the web app must have at
  least one `browser` step with an image or video artifact. Detected from the
  same changed-file list `review_delivery` already computes; no new config.
- **no secrets** — the redaction pass runs before hashing; `verify` re-scans
  text artifacts for token-shaped strings and fails rather than shipping one.
- **hashes** — every artifact is re-hashed and compared.

`review_delivery` gains one blocker for waves that use bundles: *stale bundle*
(commit mismatch) and *bundle claims vs loop claims disagree* (e.g. bundle
verdict `fail` on a wave recorded `done`). Waves without a bundle keep today's
free-text rules — this is additive, not a new tax on docs-only work.

## Alternatives considered

- **Rely on CI artifacts only.** No local story (most waves are finished
  before CI runs), and a folder of PNGs in an artifact zip is exactly the
  "nobody can open it" problem rule 3 describes.
- **Adopt Allure / Playwright's HTML report wholesale.** Both are excellent
  and both are language- and framework-bound. The harness is polyglot by
  design (Python, TS, Go repos), and a wave may have no browser at all.
- **Hosted evidence service** (Currents-style). Needs an account and uploads
  private code to a third party; the harness must work offline and inside a
  repo that may be under NDA. The seam is kept: a bundle is just files, so a
  service can consume it later.
- **Commit everything, Markdown + PNG.** Video has no home in git, every
  screenshot is a permanent blob in history, and the page rots as files move.
- **Single-file everything, always.** Attractive for sharing, unusable for
  video and traces; kept as an explicit `--inline` mode with a size budget
  instead of the default.

## Consequences

- Evidence stops being a sentence and becomes a reviewable object; PR review
  starts from the page instead of from a rebuild.
- `verify` is the part that keeps it honest: commit/sha binding, real exit
  codes, hashes, redaction. A bundle is only as good as those checks.
- Costs: one module, one skill, one page renderer, plus a fixture for repos
  that use Playwright.
- Nothing new is committed per run by default. Bundles live in the local
  scratch directory `.openharness/evidence/` (gitignored); a zip is uploaded
  as a CI artifact when a link is needed. When a run's proof must travel with
  the repo, `--action=new --tracked` writes it under `evidence/` — a normal
  tracked folder the human or agent commits and pushes explicitly.
- The renderer is a single HTML template — deliberately boring, because it
  has to still open in three years with no build step.

## Phases

1. **P1 — contract + renderer + verify.** ✅ `openharness/evidence.py`,
   `harness_evidence` skill (`new`, `render`, `verify`, `list`), manifest
   schema, the page (`tests/test_evidence.py`, 41 tests). Checks now enforced:
   schema, artifact hash/size, missing artifact or log, commit binding to HEAD,
   verdict-vs-step contradictions, command exit codes, token shapes in logs and
   text artifacts, tracked bundles, and an `empty-bundle` warning so a bundle
   that proves nothing says so. No network, no git writes.
   (Deliberately deferred to P2: `attach`/`step` and the redaction pass;
   `render --inline` already inlines images under a size budget.)
2. **P2 — capture.** ✅ P2a (2026-11-17): `step` runs a command and records
   the real exit code, wall time, cwd and a redacted log; `attach` copies a
   file under `raw/<step>/`, sniffs MIME from magic bytes and the suffix,
   refuses a file older than the step (`--allow-old` overrides), and creates a
   `manual` step when the bundle is empty; a redaction pass scrubs
   auth/cookie/password/API-key/token/private-key/JWT/JSON-secret shapes
   before hashing and records counts in `redactions`. Manifest schema is
   `openharness.evidence/2`, with `/1` still accepted. Deferred to P2b:
   Playwright fixture and the `attach --from=steps.json` fold-in.
3. **P3 — loop wiring.** `evidence:` token in `ship_loop complete`, the
   stale/contradiction blockers in `review_delivery`, UI-wave requirement.
4. **P4 — sharing.** CI job zips `.openharness/evidence/<feature>/<run-id>` and
   uploads it as an artifact; the PR comment links to it and `SUMMARY.md` is
   appended to the PR body. Nothing is added to git.

Open question for review: whether the Playwright fixture belongs in this repo
or is generated per-project by the skill. Bundle location: local scratch
`.openharness/evidence/` by default; `evidence/` (tracked, committed on
request via `--tracked`) when a run's proof must travel with the repo.
