---
description: Scan the target repo for credentials/secrets, classify, propose remediation plan
---
# /scan-secrets — Security architect: scan + triage + plan

## Context

Run via Bash and read output:
- `python -m openharness self`
- `python -m openharness env`

Read REPOS.md and .openharness/ENV.md. If cwd is inside `sources/<repo>`, that repo is the default target; otherwise ask the user.

## Workflow

1. Run scanner + inject secrets-policy RAG context, read both outputs:
   ```bash
   python -m openharness run scan_secrets --repo-path sources/<repo>
   python -m openharness ask "secrets credentials handling policy"
   ```

2. Act as security architect. For EACH finding:
   - Classify severity: `critical` | `high` | `medium` | `low` | `info`
   - 1-2 line justification
   - Specific remediation (rotate+revoke, env vars, secret manager, false-positive/whitelist)

3. Produce a risk-ordered remediation plan, tagged by file(s), severity, effort.

4. Offer to write `.openharness/context/secrets-<repo>.md` and ingest it via:
   ```bash
   python -m openharness ingest .openharness/context/secrets-<repo>.md
   ```
