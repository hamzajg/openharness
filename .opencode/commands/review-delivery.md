---
description: Independently audit a feature's spec and delivery — verify claims against the repo, trace every acceptance criterion to a real test, find hallucinated paths/APIs and wrong-feature delivery, then PASS/CONCERNS/BLOCK
agent: build
---
# /review-delivery — Prove the spec and the delivery are real

Independent review for one feature. It answers two questions:

- **Spec phase:** is this spec grounded in the repo, or does it describe files,
  APIs, and scenarios that do not exist?
- **Delivery phase:** did we ship what the spec says, with proof, and nothing
  outside it?

The review is **advisory by default**. `/ship-loop` can enforce it with
`ship_loop --review=required`; that is a process choice, not a claim that the
reviewer can replace tests.

Arguments (`$ARGUMENTS`), all optional:

| Arg | Default | Meaning |
|---|---|---|
| `--repo=sources/<repo>` | cwd inside `sources/` | Target repo. Must be registered in the active registry (REPOS.md or .openharness/REPOS.local.md). |
| `--feature=<name>` | first feature | `specs/<name>/`. |
| `--spec=<path>` | — | Explicit spec dir, when `--feature` is ambiguous. |
| `--phase=spec\|delivery\|all` | `delivery` | Which audit to run. |
| `--changed=<paths>` | git diff | Changed files for scope-drift checking. |
| `--base=<ref>` | origin/main, origin/master, main, master | Diff base. |
| `--write` | off | Write `SPEC-AUDIT.md` / `DELIVERY-AUDIT.md`. |
| `--force` | off | Overwrite an existing audit file. |

## Context

Run these first and read the output:
- `python -m openharness self`
- `python -m openharness env`
- `python -m openharness run ship_loop --action=status --repo_path=<repo>`

## Procedure

1. **Resolve the target.** Repo path, spec dir, phase. If the spec dir is
   missing or ambiguous, ask. Do not audit the wrong feature.

2. **Build the deterministic brief.**
   ```
   python -m openharness run review_delivery --repo_path=<repo> \
     --spec_dir=<repo>/specs/<feature> --phase=<phase> \
     --changed="<paths>" --base="<ref>"
   ```
   Read it. It reports, by severity:
   - missing artifacts and unresolved spec markers;
   - traceability: AC → scenario → wave → backlog → LOOP;
   - claim existence: backticked paths, scripts, endpoints, ADRs;
   - evidence integrity: placeholder wave/gate evidence, gate files, weak or
     empty validation rows, validation gaps;
   - scope drift and unfinished markers in changed code.

   The brief is **not** a verdict. A clean brief means nothing mechanical was
   found. It does not mean the feature is correct.

3. **Delegate the judgment.** Give **delivery-auditor** the repo, spec dir,
   phase, brief, and changed files. It must:
   - re-verify every blocker and concern against the cited file:line;
   - open the tests and confirm they assert the scenario's outcome, not just
     its name;
   - run the real test command when the toolchain is available;
   - check the demo script's happy path end to end;
   - compare changed public contracts with the spec and README;
   - record dismissed findings with a reason, and unverified items honestly;
   - fill the verdict block.

4. **Apply the verdict.**
   - `PASS` — all lists empty and evidence was verified. Continue.
   - `CONCERNS` — every remaining item is non-blocking and explicitly
     accepted. Report the list. Continue only if the user accepts it.
   - `BLOCK` — a confirmed blocker, a hallucinated claim, or an unproven
     acceptance criterion. **Stop.** Do not mark the feature done, do not
     merge, do not record `finish`. Report exactly what must change.

5. **Persist the review.** With `--write`, the audit lives at
   `specs/<feature>/SPEC-AUDIT.md` or `DELIVERY-AUDIT.md`. The deterministic
   brief stays; the auditor appends the verdict. If a human-authored audit
   exists, do not overwrite it without `--force` and a reason.

6. **Report** using the contract below.

## Output contract

```
FEATURE: <name>
PHASE: spec | delivery
AUDIT: PASS | CONCERNS | BLOCK
BLOCKERS: <count + the confirmed ones>
CONCERNS: <count + the accepted ones>
UNVERIFIED: <what could not be checked>
DISMISSED: <false positives from the brief, with why>
EVIDENCE: <tests run, files read, diff inspected>
AUDIT FILE: <path or "not written">
LOOP IMPACT: none | <what must change before finish>
```

## Relationship to the delivery loop

- **Spec phase:** run after `SPEC.md`, `EXAMPLES.feature`, and `BACKLOG.md`
  exist, before `wave_plan` and wave 1. A hallucinated spec is cheapest to fix
  here.
- **Delivery phase:** run after `ship_validate` writes `VALIDATION.md`, before
  `ship_loop --action=finish`.
- **Enforcement:** `/ship-loop` runs with `--review=required` (the oracle
  default). The oracle then requires `SPEC-AUDIT.md` before `plan` and
  `DELIVERY-AUDIT.md` before `finish`, and records the mode in
  `LOOP.state.json`. A `BLOCK` verdict stops the loop. Standalone
  `/review-delivery` remains advisory; `--review=advisory` is the explicit
  loop opt-out.
- **Not a gate.** The audit is a review artifact, not a `GATES.md` gate. It
  never marks a gate, never merges, and never edits product code.
- **Independence:** the auditor is not the implementer. If the same session
  wrote the code, hand the audit to a fresh session or state the conflict.

## Guardrails

- Do not fix what you find during the audit. Report it; the loop fixes it in
  a wave.
- Do not accept `VALIDATION.md` as proof. It is a generated claim; the tests
  are the evidence.
- Do not accept a green CI run as proof of the spec. CI proves the tests pass,
  not that they test the right thing.
- Do not mark `PASS` from the brief alone.
- Do not edit `LOOP.md`, `LOOP.state.json`, or `GATES.md`; `ship_loop` is their
  only writer.
- Do not commit, push, merge, or force-push.
