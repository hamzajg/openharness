---
name: evidence
type: block
location: openharness/evidence.py, skills/harness/evidence.py, docs/adr/0007-evidence-bundles.md, docs/plans/evidence.md
interfaces: [harness_evidence.invoke, harness_evidence --action=list|new|step|attach|fixture|render|verify, evidence.new_bundle, evidence.record_step, evidence.record_attach, evidence.fragment_artifact, evidence.verify, evidence.list_bundles]
---
# Block: evidence

## Purpose
Makes "done" a reviewable object instead of a sentence: one bundle per run,
with an authoritative manifest, the raw media, the logs, and a generated
walkthrough page that opens offline with no network and no build step
(ADR 0007). Every bundle declares a `kind`: `proof` (the default — the
wave/finish evidence `ship_loop` verifies, scratch or `--tracked`) or
`walkthrough` (local-only companion material for screenshots, recordings
and log summaries; `new` refuses `--kind=walkthrough --tracked`, and
`verify` warns `walkthrough-in-tracked-root` if one lands under
`evidence/`). Walkthroughs are per-wave optional and never the gate
evidence — they carry no `tdd:` steps, so `tdd_proof` cannot pass on them. The loop used to record `pytest 12 passed; CI green` in `LOOP.md`
— true or not, it could not be seen, and it was gone by the next session.

The harness does not drive browsers or devices (D001). Playwright, `adb`,
`xcrun`, an agent's preview tools, or a human produce files; this block starts
at the manifest and records what it was handed.

## Layout
```
.openharness/evidence/<feature>/<run-id>/   # default: local scratch, gitignored
evidence/<feature>/<run-id>/                # --tracked on `new`: committable
├── evidence.json   manifest (authoritative, schema openharness.evidence/2)
├── index.html      generated walkthrough, never edited by hand
├── SUMMARY.md      20-line summary for a PR body or a LOOP row
├── raw/            screenshots, recordings, traces, HAR files
└── logs/           one log per executed command
```
`<run-id>` is `YYYYMMDDTHHMMSSZ-<sha7>`, so a stale bundle is obvious at a
glance. `verify` enforces the split both ways: a scratch bundle that git
tracks is an error, and a tracked-root bundle git does not yet track draws an
`untracked-bundle` warning. `--bundle=<path>` points at anything else.

## Actions
| Action | Effect |
|---|---|
| `list` | Bundles under both roots, newest first, with verdict, counts, commit. |
| `new` | Create a bundle and manifest (feature required; `--wave`, `--head`, `--tracked`, `--kind=proof|walkthrough`). |
| `step` | Run a command; record real exit code, wall time, cwd, redacted log. Optional `--tdd=red|green|refactor` marks the TDD phase the run belongs to. |
| `attach` | Copy a file under `raw/<step>/` (hash, MIME, mtime guard), or fold a `steps.json` fragment in with `--fragment`. Fragment artifacts are manifest-ready (`path`+`mime`+`sha256`+`bytes`) or source files (`path` only — attach copies and hashes them). |
| `fixture` | Write `evidence.fixture.ts` (Playwright walkthrough producer) into the repo; it emits `steps-<spec>.json` fragments for `attach`. |
| `render` | Write `index.html` + `SUMMARY.md` from the manifest. |
| `verify` | Schema, hashes, artifacts, commit binding, secrets, tracking. Exit 2 on failure. |

`attach` refuses a file older than the step it is attached to (`--allow-old`
overrides and records why). MIME is sniffed from magic bytes and suffix, not
from the caption. `role` is a label, not a proof: an explicit one wins,
otherwise it is inferred — image → `screenshot`, video → `video`, `.har` →
`har`, `.zip`/`.trace`/`application/json` → `trace`, else `attachment`.

## What `verify` enforces
- Manifest schema and required fields; `.json` on disk and every referenced
  artifact and log resolve; every artifact is re-hashed and size-checked.
- `manifest.repo.head` matches the checked-out commit.
- A `pass` verdict cannot coexist with a failed step, a non-zero recorded exit
  code, or a `ci.conclusion: success` without a `ci.sha`.
- Token-shaped strings in logs and text artifacts fail the bundle; the
  redaction pass (`Authorization`, cookies, passwords, API keys, tokens,
  private keys, JWTs, JSON secrets) runs before hashing and its counts land in
  `redactions`.
- An empty bundle is a valid manifest and an `empty-bundle` warning — it
  proves nothing and says so.

## Capture policy
| Artifact | When |
|---|---|
| manifest, page, summary, logs | every run |
| screenshots | every UI wave; failures everywhere |
| recording | UI flows over ~3 steps, and any failed UI step |
| trace / HAR / console log | failures, on request |

Binary media is not scanned for secrets and is reported that way rather than
implicitly clean.

## TDD steps
A step may carry `tdd: red|green|refactor`. `tdd_proof(manifest)` requires
one step per phase: `red` a failed command marked `expected_failure`,
`green` and `refactor` passing, ordered by `started_at` red ≤ green ≤
refactor. `ship_loop --action=complete`/`finish` rejects a wave bundle
without it (ADR 0008); `--force` bypasses like every other precondition.
The ordering proves the runs happened in sequence — whether the red log
shows the real scenario failure is the wave-reviewer's semantic check.

## Loop wiring
`ship_loop --action=complete --wave=N` and `--action=finish` refuse until a
bundle loads, records that wave, passes `verify`, proves TDD
(`tdd_proof`), and is bound to the checked-out commit; both roots count.
`--force` bypasses the gate like every other loop precondition.
`review_delivery` reports per-wave TDD status as `tdd-missing` concerns —
it surfaces the gap without re-blocking legacy waves. Still open
(P3/P4 of `docs/plans/evidence.md`): `evidence:<run-id>` tokens in
LOOP.md/gate evidence, `--action=share`/`prune`, and the CI template;
the Playwright fixture ships via `--action=fixture`.

## Invariants
- A bundle is proof of one run, not a product artifact: scratch by default,
  committed only on explicit `--tracked`, never automatically.
- The page and `SUMMARY.md` are generated from `evidence.json`; a human edit
  makes the bundle a claim rather than a record.
- `verify` is what gives the manifest meaning. A bundle that fails it is not
  evidence, and no action in this block writes to git or the network.
- `not_verified` is required and deliberate — it is where "I did not open the
  UI" lives.
- No browser automation, device farm, or hosted service (D001); producers stay
  optional and outside the runtime.

## How to Extend
1. New checks go in `evidence.verify` with tests in `tests/test_evidence.py`.
   The module is stdlib-only — CI installs with `--no-deps`.
2. New actions update the `harness_evidence` docstring, this block, and the
   evidence section of `.claude/commands/ship-loop.md` +
   `.opencode/commands/ship-loop.md`.
3. Manifest fields are additive and optional; bump `SCHEMA` only when `verify`
   needs the field to decide something. `/1` bundles must keep loading.
4. New producers emit files or a step-shaped `steps.json` fragment and are
   folded in with `attach --fragment`; never import harness code into a test
   fixture.
