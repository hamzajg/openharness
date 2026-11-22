# Evidence v2 — capture, walkthrough page, and sharing

Status: draft · 2026-11-17 · extends [ADR 0007](../adr/0007-evidence-bundles.md)
(P1 shipped). Scope: P2 capture, P3 renderer/loop wiring, P4 sharing.

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
2. **Manifest v2 is additive.** v1 bundles keep loading and rendering. New
   fields are optional except where `verify` needs them for a UI wave.
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

## Two evidence tiers (implemented)

Every bundle declares `kind` in its manifest (absent = `proof`):

- **`proof`** — the wave/finish evidence `ship_loop` verifies: TDD steps,
  commit binding, rendered page. Lives in `.openharness/evidence/` scratch
  by default; `--tracked` on `new` places it under `evidence/` to be
  committed when a run's proof should travel with the repo.
- **`walkthrough`** — local-only companion material: screenshots,
  recordings, summarized logs for human review. `new --kind=walkthrough`
  always lands in the scratch root (`--tracked` is refused) and `verify`
  warns `walkthrough-in-tracked-root` if one is moved under `evidence/`.
  Per-wave optional; it is not gate evidence — it carries no `tdd:` steps,
  so `tdd_proof` cannot pass on it.

## Manifest v2

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

## Capture surface

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

## Capture policy (recommended and enforced)

| Artifact | When | Retention |
|---|---|---|
| manifest, page, summary, logs | every run | with the wave |
| screenshots | every UI wave; failures everywhere | with the wave |
| video | UI flow > 3 steps; any failed UI step | latest run per wave |
| trace / HAR | failures, on request | latest run per wave |
| zip for CI | when a link is needed | 14 days |

`--action=prune --keep=3` keeps the newest three runs per feature. It never
deletes a bundle referenced by a `LOOP.md` row or a gate.

## Walkthrough page v2

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

## Sharing

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

## Loop wiring

- `ship_loop complete --wave=N --evidence=evidence:<run-id>` accepts a bundle
  token. Before recording the wave as done it runs `evidence.verify`, checks
  `manifest.repo.head` against the wave head, and refuses a `fail` verdict.
- `review_delivery` gains four findings:
  - `stale-evidence` — bundle head does not match the wave head.
  - `evidence-contradicts-loop` — bundle verdict `fail` on a wave recorded
    `done`.
  - `ui-wave-without-media` — changed paths touch web/mobile and no step has
    an image or video artifact.
  - `unverified-evidence` — bundle missing, invalid, or `verify` errors.
- Agent-owned gates may use `evidence:<run-id>` as their evidence; `ship_loop
  gate` verifies it before marking the gate met. Human-owned gates still need
  a named human.
- `LOOP.md` rows may carry `evidence:<run-id>`; the page and the row point at
  each other.

Waves without a bundle keep today's free-text rules. This is additive, not a
tax on docs-only work.

## Implementation plan

### P2a — capture core (no browser) — ✅ implemented 2026-11-17

- `harness_evidence --action=step --bundle=… --title=… -- <cmd>`: runs the
  command, captures stdout/stderr to `logs/<id>.log`, records exit code,
  duration and cwd. The CLI accepts the command after `--` (joined with
  `shlex.join`); `--cmd="…"` still works.
- `--action=attach --step=<id> --file=<path> [--caption=…] [--role=…]`:
  hashes, sizes, sniffs MIME from magic bytes then suffix, enforces the mtime
  guard, and copies into `raw/<step>/`.
- Redaction runs on the command, title, note, log and text artifacts before
  hashing; counts land in `redactions` with a manifest path.
- Manifest v2 (`openharness.evidence/2`) with `/1` still accepted; new
  optional fields are `capture`, `step.covers`, `step.checks`,
  `artifact.role/caption/poster`, `redactions[].note`.
- Tests: 60 evidence tests (step exit codes, timeout, duplicate id, stale
  attach, `--allow-old`, magic-byte MIME, JSON redaction, title redaction,
  v1 compatibility, CLI passthrough). Full suite passes.
- Not yet in P2a: `--action=fixture` and `attach --from=steps.json` (P2b).

### P2b — browser attach

- `attach --fragment=steps.json` folds a fragment into the manifest.
  Fragment schema is a subset of a step, so a fixture can emit it without
  importing harness code. `role` is a label, not a proof, so an omitted
  `role` is inferred from the MIME type and file name (`_role_for`); an
  explicit one always wins.
- Fragment artifacts come in two forms. **Manifest-ready** entries carry
  `path` + `mime` + `sha256` + `bytes` and are recorded as-is.
  **Source-file** entries carry `path` (+ optional `caption`, `role`,
  `snippet`) naming a real file — resolved relative to the fragment's
  directory then cwd — which `attach` copies under `raw/<step>/` and
  hashes itself, with the same staleness guard and `--allow-old` override
  as `attach --file`. This keeps the "attach computes hashes, never
  trusts caller-supplied ones" rule true for producers too.
- `--action=fixture` generates `e2e/evidence.fixture.ts` into the target
  repo (fixture home resolved: generated per project, never a runtime
  dependency). The fixture exports `test`/`expect` with an `evidence.step`
  helper that screenshots each named step into `EVIDENCE_RUN_DIR` and
  writes `steps-<spec>.json`; failed steps also capture the video when
  Playwright recording is enabled. It covers web and mobile-web device
  emulation; Electron desktop and native mobile are different producers
  emitting the same fragment — no second fixture ships yet.
- Tests: fragment fold-in, duplicate artifacts, poster selection, trace MIME.
- Done when a Playwright run yields screenshots + video + trace + logs in one
  bundle, and the page shows them without a build step.

### P2c — device and manual capture

- Optional `--action=capture --device=android|ios`: shell out to `adb` /
  `xcrun` when present; fail with an install hint when not.
- `attach --by=<name>` records who captured a manual artifact.
- Tests: tool-missing path, output naming, MP4/PNG MIME.
- Done when an Android or iOS UI wave can attach a screenshot and a short
  recording without hand-writing manifest JSON.

### P3 — renderer v2 and enforcement

- Manifest v2 rendering: coverage matrix, thumbnails in the timeline,
  lightbox, video poster/chapters, log filter/copy, redaction notes.
- `--inline` budget with an explicit list of files left linked.
- `review_delivery` findings and `ship_loop` evidence token.
- Tests: HTML escaping, coverage matrix, missing artifact card, inline budget,
  UI-wave detection, stale/contradictory bundle, keyboard markup.
- Done when a reviewer can open one page and answer the four questions above,
  and a stale or media-less UI bundle is blocked.

### P4 — sharing and retention

- `--action=share` zip + sha256; `--action=prune --keep=N`.
- CI template and PR-comment snippet in docs.
- `--public` sanitized copy with a human approval step.
- Tests: zip contents, prune keeps referenced bundles, public copy refuses
  secrets.
- Done when a teammate can download one zip, open `index.html`, and verify it
  offline.

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
3. **Fixture home.** Template in this repo, generated into target repos, or
   both? Recommendation: template here, generated per project, never a runtime
   dependency.
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
