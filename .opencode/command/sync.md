---
description: Regenerate/verify that every skill has a matching command file in .claude/commands/ and .opencode/command/
---
# /sync — Keep skills ⇄ slash command files in sync

## Context

Run via Bash and read output:
- `python -m openharness self`
- `python -m openharness env`

Read REPOS.md and .openharness/ENV.md.

## Workflow

1. Get current catalog:
   ```bash
   python -m openharness
   ```

2. Enumerate existing `.claude/commands/*.md` and `.opencode/command/*.md`.

3. For every skill missing a command file in EITHER directory, create a stub in both:
   - Filename: `<underscores-to-dashes skill name>.md`
   - Claude frontmatter: `description: <first docstring line>` + `allowed-tools: [Bash(python -m openharness:*), Read, Grep, Edit, Write]`
   - OpenCode frontmatter: `description: <first docstring line>` only
   - Body: awareness preamble (run self + env, read ENV/REPOS), then instruct agent to run `python -m openharness run <skill> --param=value ...` using params from the typed signature, then act on output.

4. Flag orphan command files with no matching skill; ask user whether to delete.

5. Report diff: new stubs written, orphans flagged.
