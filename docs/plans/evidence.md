# Evidence — capture, walkthrough page, and sharing

Status: phases P1–P2b shipped · extends
[ADR 0007](../adr/0007-evidence-bundles.md). One evidence system, delivered
in phases: P1 contract+renderer+verify, P2 capture, P3 renderer/loop
wiring, P4 sharing. Manifest schema versions (`openharness.evidence/1`,
`/2`) are internal compatibility labels, not product versions.

## Why this exists

P1 made evidence a reviewable object: a manifest, hashes, commit binding, a
generated page, and a `verify` that refuses to bless a bundle that cannot
support its claim. What it cannot do yet is *show* a UI run. Today a wave that
touches a screen still records a sentence, and the reviewer has to rebuild the
branch to see what happened.

The target is one local folder per run that a reviewer can open offline:

```
.openharness/evidence/<feature>/<run-id>/
├── evidence.json      # authoritative manifest
├── index.html         # generated walkthrough (rich preview)
├── SUMMARY.md         # 10–20 lines, pasteable into a PR or LOOP row
├── raw/               # screenshots, video, trace, HAR
└── logs/              # one log per command + console/network logs
```

The page answers four questions in review order: **what was proven**, **what
was not**, **what did the reviewer see**, and **can I trust the files**.

## What the community actually recommends

Surveyed primary docs (2026-11-17). The pattern is consistent:

| Source | Model | What to borrow | Why not adopt wholesale |
|---|---|---|---|
| Playwright HTML report / trace viewer | per-test report + attachments; trace is a zip | `screenshot: only-on-failure`, `video: retain-on-failure`, `trace: retain-on-failure`; report uploaded every run | JS/TS-bound; default output is a directory, not one link |
| Allure Report | attachments attached to a test or a step, declared by MIME type; previews for image/video/text/JSON/trace | step-level attachments, previews, "screenshot on failure first, every step if affordable" | framework integrations and a report server/runtime; heavier than a stdlib bundle |
| Cypress | screenshots/videos on failure | `videoUploadOnPasses: false`, compression, failure-first capture | E2E-only, JS-only |
| monocart-reporter | self-contained `report.html` | inline assets so the report travels as one file | Playwright-specific |
| GitHub Actions artifacts | zip + `retention-days`, SHA-256 `digest` | upload report always, heavy media on failure, short retention | no viewer, no provenance model, bounded retention |
| Currents / Allure TestOps | hosted dashboards | "one link" UX | needs an account and uploads private code; harness is local-first |

**Recommendation:** combine Playwright's *capture policy* (structure always,
heavy media failure-scoped), Allure's *attachment model* (media belongs to a
step, with a MIME type and a caption), and monocart's *single-file output*
(inline images/CSS/JS, link video). Implement it framework-agnostically and
stdlib-only, because this harness is polyglot and may have no browser at all.

Concretely:

- **Always:** `evidence.json`, `index.html`, `SUMMARY.md`, command logs.
- **Every UI wave:** at least one screenshot per acceptance scenario touched.
- **UI flows over ~3 steps, and every failed UI step:** a short recording.
- **Failures, on request:** Playwright trace / HAR / console + network logs.
- **Never inline video** by default: base64 turns a 5 MB WebM into ~7 MB of
  HTML and stalls the browser. Link it, or zip the folder.

## Decisions

1. **The harness does not drive browsers or devices.** D001 stands. Playwright,
   Cypress, `adb`, `xcrun`, or a human produce files; the harness starts at the
   manifest and the attach boundary. A browser step is *attached*, never
   synthesized.
2. **The manifest schema is additive.** Older bundles keep loading
   and rendering. New fields are optional except where `verify` needs
   them for a UI wave.
3. **Media is step-scoped.** A screenshot without a step, a caption, and a
   hash is not evidence; it is a file.
4. **A UI wave without media is not done.** `review_delivery` and `ship_loop`
   treat that as a blocker, using the same changed-path detection they already
   have.
5. **Local by default, share by zip.** Bundles stay in `.openharness/evidence/`
   (gitignored). A zip is the unit for CI artifacts; committing a sanitized
   bundle is opt-in (`--public`) and never automatic.
6. **No secrets, no silent truncation.** Redaction runs before hashing; the
   page reports what was scrubbed. Binary media is marked "not scanned" rather
   than implied clean.

## Two evidence tracks (implemented)

Every bundle declares `kind` in its manifest (absent = `proof`) — the two
tracks of this plan. Track A is proof: the wave/finish evidence
`ship_loop` verifies (TDD steps, commit binding, rendered page), in
`.openharness/evidence/` scratch by default or `evidence/` when `--tracked`
commits it with the repo. Track B is walkthrough: local-only companion
material (screenshots, recordings, summarized logs) that `new
--kind=walkthrough` always places in scratch (`--tracked` refused), `verify`
warns `walkthrough-in-tracked-root` if moved under `evidence/`, and which is
never gate evidence — it carries no `tdd:` steps, so `tdd_proof` cannot
pass on it.

## Manifest (schema `openharness.evidence/2`)

```jsonc
{
  "schema": "openharness.evidence/2",
  "feature": "photo-notes",
  "wave": 2,
  "run_id": "20261117T101500Z-1cd5ed6",
  "created_at": "2026-11-17T10:15:00Z",
  "repo": {"slug": "hamzajg/CarFilters", "branch": "feat/photo-notes",
           "head": "1cd5ed6…", "base": "main"},
  "ci": {"pr": 12, "url": "…", "sha": "1cd5ed6…", "conclusion": "success"},
  "verdict": "pass",
  "summary": "Create, edit, and delete a photo note; empty note rejected.",
  "not_verified": ["rotation on a physical device", "tablet layout"],
  "capture": {
    "tool": "playwright", "version": "1.49.0",
    "viewport": "1280x720", "device": "Pixel 7", "os": "android-34"
  },
  "steps": [
    {
      "id": "s2", "title": "Create a note", "kind": "browser",
      "status": "pass", "started_at": "…", "duration_ms": 4210,
      "covers": ["AC1", "A note can be created"],
      "checks": [
        {"name": "note count", "status": "pass", "expected": "1", "actual": "1"}
      ],
      "artifacts": [
        {"path": "raw/s2/01-empty.png", "mime": "image/png",
         "sha256": "…", "bytes": 184233, "role": "screenshot",
         "caption": "Empty note is rejected"},
        {"path": "raw/s2/session.webm", "mime": "video/webm",
         "sha256": "…", "bytes": 1742331, "role": "video",
         "caption": "Create flow, 4.2s", "poster": "raw/s2/01-empty.png"}
      ],
      "log": "logs/s2.log"
    }
  ],
  "redactions": [
    {"path": "logs/s2.log", "pattern": "Authorization", "count": 2},
    {"path": "raw/s2/session.webm", "pattern": "binary", "count": 0,
     "note": "binary media is not scanned for secrets"}
  ],
  "environment": {"os": "darwin", "python": "3.13.13", "node": "20"}
}
```

New optional fields: `capture`, `step.covers`, `step.checks`,
`artifact.role`, `artifact.caption`, `artifact.poster`,
`redactions[].note`. `schema` moves to `openharness.evidence/2`;
`load` accepts `/1` and `/2`, and `new_bundle` writes `/2`.

`covers` is the link between the walkthrough and `SPEC.md` /
`EXAMPLES.feature`. It is what makes the coverage matrix possible and what
turns "I clicked around" into "AC5 was exercised by step s3".

## Capture surface (Track B producers)

| Source | How it is produced | Artifacts | Default |
|---|---|---|---|
| Command | harness runs it (`--action=step`) | log, exit code, duration, cwd | always |
| Browser (Playwright) | generated fixture writes `steps.json` + files; `attach --fragment` folds them in | PNG, WebM, trace.zip, console, HAR | screenshots every UI wave; video/trace on failure or long flow |
| Browser (Electron/desktop) | same fragment contract, adapted launch | PNG, WebM | desktop waves |
| Mobile (native) | future producer (Appium/Maestro) emitting the same fragment | PNG, MP4 | native app waves |
| Browser (Cypress) | plugin writes files; `attach` | PNG, MP4, JSON | optional, same policy |
| Android | `adb exec-out screencap -p`, `adb shell screenrecord`, `adb logcat -d` | PNG, MP4, log | UI waves on Android |
| iOS | `xcrun simctl io booted screenshot`, `xcrun simctl io booted recordVideo` | PNG, MOV/MP4, log | UI waves on iOS |
| Manual | human or agent captures; `attach --file --caption --by` | PNG, MP4, PDF | human-owned gates |
| API | `step` running curl/httpie; `attach` HAR/JSON | HAR, JSON, log | API waves |

Rules the skill enforces:

- `attach` computes `sha256` and `bytes`; it never trusts caller-supplied
  hashes.
- An artifact whose `mtime` predates the step's `started_at` is rejected
  (`stale-artifact`), so an old screenshot cannot be passed off as this run.
  `--allow-old` exists for intentionally historical attachments and records
  why.
- `step` records the real exit code, wall time, and cwd from the process.
- MIME is sniffed from the file suffix and magic bytes, not from the caption.
- Redaction runs on text artifacts and logs before hashing. Patterns:
  `Authorization`, `Cookie`, `Set-Cookie`, `password=`, `token=`, AWS keys,
  GitHub tokens, private-key headers, JWTs. Replacement is
  `[REDACTED:<name>]`; the count is written to `redactions`.
- Video is copied as captured. `--compress` uses `ffmpeg` when present and
  records the command; it is never required.

## Capture policy (Track B)

| Artifact | When | Retention |
|---|---|---|
| manifest, page, summary, logs | every run | with the wave |
| screenshots | every UI wave; failures everywhere | with the wave |
| video | UI flow > 3 steps; any failed UI step | latest run per wave |
| trace / HAR | failures, on request | latest run per wave |
| zip for CI | when a link is needed | 14 days |

`--action=prune --keep=3` keeps the newest three runs per feature. It never
deletes a bundle referenced by a `LOOP.md` row or a gate.

## Walkthrough page (Track B)

One HTML file, inline CSS and ~3 KB vanilla JS, no CDN, no fonts, no network.
Opens from `file://`. Sections in review order:

1. **Header** — verdict, feature/wave, run id, head/branch, PR, CI conclusion,
   capture tool/device, "generated from evidence.json".
2. **What this proves** — summary, counts, and the `not_verified` list in its
   own warning box, not a footnote.
3. **Acceptance coverage** — a table of AC/scenario → steps → artifacts.
   Uncovered ACs are highlighted. This is the walkthrough summary in
   structured form; it is derived from `covers`, not authored.
4. **Walkthrough** — one row per step: status, title, duration, command, note,
   inline thumbnail, log link. Click to expand checks and artifacts.
5. **Screenshots** — gallery with caption, step attribution, and sha256.
   Click for a CSS-only lightbox with arrow keys and Escape; download link.
6. **Recording** — `<video controls preload="metadata">` with a poster frame,
   size, sha256, download. Chapters are generated as WebVTT from step
   `started_at` offsets when available.
7. **Logs** — per-step panes, monospace, client-side filter, copy, download,
   ANSI escapes stripped. Secrets are already redacted at write time.
8. **Provenance** — artifact table (path, size, sha256), environment, CI link
   by sha, and the exact `render` command.
9. **Redaction report** — what was scrubbed from which file, and which binary
   artifacts were not scanned.
10. **Footer** — schema, verify status, "generated, never edited by hand",
    local-scratch notice.

Accessibility and robustness:

- Semantic headings and tables; visible focus rings; alt text from captions.
- Lightbox is keyboard-operable; `prefers-reduced-motion` disables animation.
- Light/dark via `prefers-color-scheme`; print stylesheet for PDF export.
- All manifest strings are HTML-escaped; no raw markdown/HTML injection.
- The page never fetches anything; a strict CSP meta is included where it does
  not break `file://` media.
- Missing files render as an explicit error card, not a broken image.

`SUMMARY.md` stays deliberately small and pasteable:

```md
## Evidence — photo-notes · wave 2
- verdict: **pass**
- run: `20261117T101500Z-1cd5ed6`
- head: `1cd5ed6` on `feat/photo-notes`
- CI: PR #12 — success @ `1cd5ed6`
- steps: 5 · artifacts: 8 · screenshots: 3 · recordings: 1

Create, edit, and delete a photo note; empty note rejected.

**Not verified:** rotation on a physical device; tablet layout
```

## Sharing (Track B)

| Mode | What it is | When |
|---|---|---|
| folder (default) | `index.html` + relative `raw/` and `logs/` | local review; the honest artifact |
| `--inline` | one `index.html` with images and text base64-inlined; video linked | paste into a ticket/chat; 6 MB budget |
| zip (`--action=share`) | `<run-id>.zip` containing the folder + sha256 | CI artifact or hand-off |
| `--public` | sanitized copy under `docs/evidence/<feature>/<run-id>/` | opt-in only, after `verify` and human approval |

CI template (P4), deliberately boring:

```yaml
- name: Upload evidence report
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: evidence-${{ github.run_id }}
    path: .openharness/evidence/
    retention-days: 14
```

Heavy media can be split into a second artifact with `if: failure()`. The PR
comment carries `SUMMARY.md` plus the artifact link; the harness does not post
it itself (no network in the skill).

## Loop wiring (Track A — proof)

Track A owns everything the loop enforces. Track B (walkthrough media)
never satisfies a gate and is never required by one.

- `ship_loop complete --wave=N --bundle=<run-id>` binds a specific verified
  bundle to the wave row; `--evidence="evidence:<run-id>"` does the same
  for agent-owned gates. Before recording, the oracle runs
  `evidence.verify`, requires the manifest's wave to match, and refuses a
  `fail` verdict. `manifest.repo.head` binds to an ancestor of HEAD — a
  bundle proves the run at its recorded commit; later commits do not
  stale it.
- `review_delivery` findings on proof bundles: `stale-evidence` (bound
  bundle no longer resolves/verifies), `evidence-contradicts-loop` (verdict
  `fail` on a `done` wave), `unbound-wave-evidence` (done wave with no
  bundle recorded — legacy visibility, not a blocker).
- `LOOP.md`/`LOOP.state.json` wave rows carry the bound `bundle` run-id;
  the page and the row point at each other.
- **Media ownership rule:** UI screenshots, recordings and `covers`
  coverage live in Track B walkthrough bundles. A proof bundle is never
  required to carry media; `ui-wave-without-media`-style checks, when
  built, evaluate walkthrough bundles only.

Waves without a bundle keep today's free-text rules. This is additive, not a
tax on docs-only work.

## Implementation plan — two tracks

One evidence system, two tracks matching the manifest `kind` field.

### Track A — proof (gate evidence)

Compact, reviewable, tracked-eligible. Commands, logs, TDD steps,
commit-bound verdicts. This is what `ship_loop` and gates check.

- **A1 — contract, verify, render, TDD** — ✅ shipped.
  Manifest + schema, `verify` (hashes, secrets, commit binding, tracking
  split), generated page/`SUMMARY.md`, `step`/`attach` with redaction,
  `tdd_proof` ordering, `complete`/`finish` enforcement.
- **A2 — loop binding** — in progress.
  `--bundle=<run-id>` on `complete`, `evidence:<run-id>` gate tokens,
  ancestor commit binding, `review_delivery` proof findings, LOOP.md
  bundle field.
- **A3 — verdict depth (future).** CI-sha cross-checks, per-AC `covers`
  on proof steps if wanted; kept deliberately small — proof stays cheap.

### Track B — walkthrough (local media)

Rich, local-only, never gate evidence. Screenshots, recordings, traces,
log summaries for human review.

- **B1 — capture + producers** — ✅ shipped.
  `step`/`attach`/redaction (shared primitives), `attach --fragment`
  with manifest-ready and source-file artifact forms, `--action=fixture`
  generating the Playwright fixture per repo, `kind:"walkthrough"`
  bundles.
- **B2 — device capture** — ✅ shipped.
  `--action=capture --device=android|ios` shells to `adb`
  (screencap/screenrecord/logcat, optional `--serial`) or `xcrun simctl`
  on the booted simulator (screenshot/recordVideo/log show) and attaches
  the files via `record_attach`; `--media=screenshot|video|log|all`,
  `--seconds` for video. Missing tools fail with an install hint.
  `attach --by=<name>` covers manual captures. Electron desktop and
  native mobile producers still emit the same fragment — no second
  fixture needed.
- **B3 — page depth** — ✅ shipped.
  Coverage matrix derived from `step.covers` (uncovered steps counted),
  per-step artifact thumbnails and `checks` rows in the timeline,
  keyboard lightbox on the gallery, video `poster` frames, client-side
  log filter/copy, capture-tool chip, and an explicit linked-files list
  on `--inline` renders. Video chapters remain future work — the
  manifest records no step→video timing to build them from.
- **B4 — sharing and retention** — ✅ shipped.
  `--action=share` writes `<run-id>.zip` + `.sha256` beside the bundle;
  `--public` copies a *verified* bundle to `docs/evidence/<feature>/
  <run-id>/` with an explicit unscanned-binary warning. `--action=prune
  --keep=N` deletes oldest scratch runs per feature and never touches a
  bundle referenced by `LOOP.state.json`/`LOOP.md` (`bundle` fields and
  `evidence:<run-id>` tokens) or anything under the tracked root. The CI
  artifact template lives in "Sharing" above; `--public` copies remain
  opt-in with human approval.

### Shipped-phase detail (was P2a/P2b)

- `harness_evidence --action=step --bundle=… --title=… -- <cmd>`: runs the
  command, captures stdout/stderr to `logs/<id>.log`, records exit code,
  duration and cwd. The CLI accepts the command after `--` (joined with
  `shlex.join`); `--cmd="…"` still works.
- `--action=attach --step=<id> --file=<path> [--caption=…] [--role=…]`:
  hashes, sizes, sniffs MIME from magic bytes then suffix, enforces the mtime
  guard, and copies into `raw/<step>/`.
- Redaction runs on the command, title, note, log and text artifacts before
  hashing; counts land in `redactions` with a manifest path.
- Manifest schema `openharness.evidence/2` with `/1` still accepted; optional
  fields: `capture`, `step.covers`, `step.checks`,
  `artifact.role/caption/poster`, `redactions[].note`, `kind`.
- `attach --fragment=steps.json` folds a fragment into the manifest.
  Fragment artifacts come in two forms: **manifest-ready** (`path` +
  `mime` + `sha256` + `bytes`, recorded as-is) and **source-file**
  (`path` + optional `caption`/`role`/`snippet` — resolved relative to the
  fragment's directory then cwd, copied under `raw/<step>/`, hashed by the
  harness). `role` is inferred from MIME/suffix when omitted.
- `--action=fixture` generates `e2e/evidence.fixture.ts` into the target
  repo. The fixture exports `test`/`expect` with an `evidence.step`
  helper that screenshots each named step into `EVIDENCE_RUN_DIR` and
  writes `steps-<spec>.json`; failed steps also capture video when
  Playwright recording is enabled. Covers web and mobile-web device
  emulation.
- Tests: evidence suite covers step exit codes, timeout, duplicate id,
  stale attach, `--allow-old`, magic-byte MIME, JSON redaction, title
  redaction, schema compatibility, CLI passthrough, fragment fold-in in
  both artifact forms, `kind` rules, and the fixture action.

## Non-goals

- No browser automation, device farm, scheduler, or hosted service.
- No new runtime dependency; `ffmpeg`, `adb`, `xcrun`, Playwright are optional
  producers, never imports.
- No pixel-level secret redaction. Screenshots and video are marked "not
  scanned"; `--public` requires human review.
- No committing media to git by default.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Screenshots/video leak secrets or PII | local-only default; redaction report; "binary not scanned" note; `--public` requires approval |
| Video bloats the page or repo | link, never inline by default; size cap; optional ffmpeg compression; prune |
| Capture tool missing in CI | `step` works everywhere; browser/device adapters fail loudly with an install hint |
| Fixture rots as Playwright changes | generate it per project; keep it ~30 lines; test the fragment schema, not Playwright internals |
| Bundle becomes a second source of truth | manifest is authoritative; page and summary are generated; `verify` binds to commit and hashes |
| Determinism in tests | normalize timestamps and durations; assert structure, not pixel output |
| Scope creep into D001 | browsers/devices only produce files; the harness never drives them |

## Open questions for review

1. **Video default.** Record every UI wave, or only flows over ~3 steps and
   failures? Recommendation: the latter, with screenshots always.
2. **`covers` strictness.** Required for browser steps, or a warning? 
   Recommendation: required for UI waves; warning elsewhere.
3. **Fixture home** — resolved: template in this repo, generated into
   target repos by `--action=fixture`, never a runtime dependency.
4. **`--public`.** Is a committed, sanitized bundle ever wanted for public
   repos, or is a CI artifact enough? Recommendation: keep `--public` opt-in
   and off by default.

## Acceptance for the whole effort

A reviewer on a UI wave can:

1. open one local `index.html` with no network;
2. see the verdict, the claim, and what was not verified;
3. follow AC/scenario → step → screenshot/video/log;
4. check the sha256 of every artifact and the commit it belongs to;
5. paste `SUMMARY.md` into the PR;
6. download a zip that still works offline;
7. and `verify` fails if any of that is stale, missing, contradictory, or
   contains a token.
