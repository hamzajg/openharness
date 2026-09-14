---
name: skill-system
type: block
location: openharness/skill.py, openharness/registry.py, skills/**/*.py
interfaces: [registry.discover, registry.get, registry.all_skills, registry.as_prompt, Skill.invoke]
---
# Block: skill-system

## Purpose
Defines typed executable units called **skills** (Python functions decorated with `@skill`) discovered by walking `skills/**/*.py`. Provides a prompt-able catalog and a uniform invocation path used by both the CLI (`python -m openharness run`) and the web API (`POST /api/skills/{name}/run`).

## Invariants
- A skill is a **typed function**. Type hints are the parameter contract.
- Docstring is the prompt/description given to the agent. First line = catalog summary.
- `non_deterministic: bool` is inferred from the docstring: if it contains `"non_deterministic"` (case-insensitive), the flag is set.
- Discovery walks `skills/**/*.py`, skipping files starting with `_`. Modules are imported via `importlib` from file path.
- Every `Skill` instance found in a module's namespace is collected into the registry keyed by `.name`.
- Same `Skill.invoke(**kwargs)` code path is used by CLI and API. **No re-implementation in JS.** (D005.)
- `Skill.invoke` coerces string CLI params to `int`/`bool` based on the declared param type name.

## How to Extend
1. Create a new `.py` file under `skills/<category>/` (file MUST NOT start with `_`).
2. Import `from openharness.skill import skill`.
3. Define a typed function decorated with `@skill`. Include a descriptive docstring.
4. Run `/sync` to generate matching `.claude/commands/<name>.md` and `.opencode/command/<name>.md` files.
5. Add a test under `tests/` that invokes the skill via both `Skill.invoke` and `python -m openharness run`.
