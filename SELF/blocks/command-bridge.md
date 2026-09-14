---
name: command-bridge
type: block
location: .claude/commands/*.md, .opencode/command/*.md
interfaces: [slash-command discovery by walking up from cwd]
---
# Block: command-bridge

## Purpose
Turns skills and harness workflows into **slash commands** discoverable natively by agent CLIs (Claude Code, OpenCode) running inside the harness tree. Uses each CLI's convention: Claude looks for `.claude/commands/<name>.md`; OpenCode looks for `.opencode/command/<name>.md`.

## Invariants
- **D008 (central mode):** Commands are NOT copied into target repos. Discovery works because the session runs inside the harness tree and each CLI walks **up from cwd** to find its command dir.
- One `.md` file per command, per agent.
- Every command that does engineering work starts with the **awareness preamble** (see below) and resolves the managed repo it operates on.
- Awareness preamble (Claude variant uses `` !`...` `` for prompt-time injection; OpenCode uses plain instructions):
  ```
  ## Context
  !`python -m openharness self`
  !`python -m openharness env`
  ```
  Then read `REPOS.md` and `.openharness/ENV.md`. If a repo-level `sources/<repo>/.openharness/ENV.md` exists, it overrides the global profile for that repo. If cwd is inside `sources/<repo>`, that repo is the default target; otherwise ask the user which repo.
- **No vendor SDK imports** anywhere to build these. Files are plain Markdown. (Agent-agnostic D002.)

## How to Extend
1. After adding a new skill, run `/sync` to regenerate both `.claude/commands/<name>.md` and `.opencode/command/<name>.md` stubs.
2. Edit the generated stubs: add the awareness preamble, flesh out the workflow, specify allowed tools.
3. For commands spanning multiple skills (e.g. `/init` calls `init_profile` and then offers `/pull`), write the orchestration logic **in the Markdown** — the agent CLI is the orchestrator, not the harness. (D001.)
