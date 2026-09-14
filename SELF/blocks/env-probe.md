---
name: env-probe
type: block
location: openharness/env.py, .openharness/ENV.md, sources/<repo>/.openharness/ENV.md
interfaces: [env.probe, env.drift]
---
# Block: env-probe

## Purpose
Cheap, deterministic detection of host, languages, frameworks, CI, infra at a given root — plus a drift reporter that compares live facts against the declared `.openharness/ENV.md` profile.

## Invariants
- `probe(root) -> dict`:
  - Marker files → language/infra mapping (`pyproject.toml`→python, `package.json`→node, `go.mod`→go, `Cargo.toml`→rust, `pom.xml`→java-maven, `docker-compose.yml`→docker, `.github/workflows`→github-actions).
  - `shutil.which` for common tools (python, node, npm, poetry, pnpm, docker, kubectl, terraform, git).
  - `package.json` dependencies parsed to detect frameworks (react, vue, next, express, django, flask, fastapi).
  - `pyproject.toml` text-scanned for same framework keywords.
- `drift(env_path) -> str`: compares probe output with the YAML frontmatter fields of `.openharness/ENV.md`. Reports undeclared frameworks/tools. Returns `"env matches probed environment."` on success.
- **Layered resolution** (§7b): if cwd/explicit `--repo-path` is under `sources/<repo>` and `sources/<repo>/.openharness/ENV.md` exists → use it (repo scope); else use harness-root `.openharness/ENV.md` (ecosystem scope). Always overlay live `probe` facts. Conflicts are surfaced via `drift`, not silently resolved.

## How to Extend
- Add a new marker→language/infra pair: extend `_MARKERS` dict in `env.py`.
- Add a new framework detector: extend `_FRAMEWORK_HINTS` + add parsing branch.
- `/init` skill calls `probe` and writes the initial `ENV.md` draft. `/map-architecture` includes drift output in its preamble.
