---
description: Scan the target repo for credentials/secrets, classify, propose remediation plan
allowed-tools: [Bash, Read, Grep, Edit, Write]
---
# /scan-secrets — Security architect: scan + triage + plan

## Context
!`python -m openharness self`
!`python -m openharness env`

## Target repo
If the session cwd is inside sources/<repo>, that repo is the default
target. Otherwise ask the user which managed repo to operate on
(see REPOS.md). Never guess.

## Layered ENV
If sources/<repo>/.openharness/ENV.md exists, prefer it over the global
.openharness/ENV.md for that repo. Compare with the live env probe
output and surface any drift; do not silently choose.

Read REPOS.md and .openharness/ENV.md.

## Workflow

1. Inject the raw scanner output plus knowledge context on secrets handling policy:
   ```
   !`python -m openharness run scan_secrets --repo-path sources/<repo>`
   !`python -m openharness ask "secrets credentials handling policy"`
   ```

2. Act as a security architect. For EACH finding:
   - Classify severity: `critical` | `high` | `medium` | `low` | `info`
   - Justify classification in 1-2 lines.
   - Propose specific remediation (rotate + revoke, move to env var, use secret manager, false-positive / whitelist).

3. Produce a risk-ordered remediation plan as a Markdown list, with each item tagged by affected file(s), severity, and estimated effort.

4. Offer to write the plan to `.openharness/context/secrets-<repo>.md` and ingest it into RAG via `python -m openharness ingest .openharness/context/secrets-<repo>.md`.
