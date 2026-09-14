---
description: Regenerate/verify that every skill has a matching command file in .claude/commands/ and .opencode/command/
allowed-tools: [Bash, Read, Edit, Write]
---
# /sync — Keep skills ⇄ slash command files in sync

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

1. Get the current skill catalog:
   ```
   !`python -m openharness`
   ```

2. Enumerate existing command files under `.claude/commands/` and `.opencode/command/`.

3. For every skill in the catalog that is missing a command file in EITHER directory, create a stub command file in both:
   - Name: `<skill_name_with_underscores_replaced_by_dashes>.md`
   - Claude frontmatter: `description: <first docstring line>` + `allowed-tools: [Bash(python -m openharness:*), Read, Grep, Edit, Write]`
   - OpenCode frontmatter: `description: <first docstring line>` only
   - Body: start with the awareness preamble (self + env), then instruct the agent to run `python -m openharness run <skill_name> --param=value ...` with parameters derived from the skill's typed signature, then act on the output.

4. For every command file that has NO corresponding skill, flag it as orphan and ask the user whether to delete it.

5. Report the diff (new stubs written, orphans flagged).
