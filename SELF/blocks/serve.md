---
name: serve
type: block
location: openharness/serve.py, openharness/serve_api.py, openharness/observers/, openharness/web/
interfaces: [GET /api/sessions, GET /api/sessions/{id}, GET /api/stream/{id}, GET /api/skills, POST /api/skills/{name}/run, GET /api/self, GET /api/env, GET /api/knowledge, /api/docs]
---
# Block: serve

## Purpose
FastAPI observer + controller app (default `127.0.0.1:7337`). Provides: JSON API for all runtime verbs, SSE live tail of agent session transcripts, and a React SPA for browsing sessions/skills/self/knowledge.

## Invariants
- **UI is observer/controller, never a second runtime.** Every dynamic action calls the same Python function the CLI uses. (D005.)
  - `POST /api/skills/{name}/run` → calls the same `Skill.invoke` as `python -m openharness run`.
  - `GET /api/env` → calls `env.probe` + reads `ENV.md` + `env.drift`.
  - `GET /api/self` → reads SELF/*.md on disk.
  - `GET /api/knowledge` → `rag.search`.
- **Only observes what agent CLIs already record on disk.** (D006.) Sessions are discovered by globbing `~/.claude/projects/**/*.jsonl` (Claude) and opencode storage dir (OpenCodeObserver). No vendor SDK hooks.
- SSE not WebSocket. One-way tail is enough; `EventSource` in browser polls the file every 1s and emits new lines.
- Bind `127.0.0.1` by default. No auth in v1 (localhost only).
- FastAPI docs at `/api/docs` (free Swagger).

## UI Packaging Rules
- Source committed in `openharness/web/` (React 18 + TS + Vite + Tailwind v4 + react-router-dom + react-markdown).
- Build output `openharness/web/dist/` is **gitignored** but **wheel-included** (hatchling wheel package includes non-`.py` files under the `openharness/` package).
- `serve.py`: if `openharness/web/dist` exists, mounts `dist/assets` as static and adds a catch-all `GET /{path:path}` returning file or `index.html` (SPA fallback). If dist is missing, returns JSON hint: run `npm run build` in `openharness/web`.
- **UI contains no harness logic.** All orchestration is done via `api.ts` typed fetch client against `/api/*`.

## Observer Contract (openharness/observers/)
- `SessionMeta(id, agent, project_path, last_seen, current_command, file)` — dataclass.
- `SessionObserver` Protocol: `sessions() -> list[SessionMeta]`, `tail(session_id, since_line=0) -> list[dict]`.
- `"Active"` = transcript file `mtime` within the last 15 minutes.
- `current_command` = last slash-command line seen in the transcript.
- Sessions are **grouped per managed repo**: a session whose `project_path` is under `sources/<repo>` belongs to that repo; others are `"external"`.
