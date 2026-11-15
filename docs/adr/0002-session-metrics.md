# ADR 0002 — Session cost/latency rollups (`metrics.py`)

## Status

Accepted — implemented on `feat/session-metrics`.

## Context

`oh serve` already observes agent sessions by tailing the JSONL logs the
CLIs write (D006). Operators could see *that* sessions ran but not what
they cost: tokens, duration, tool calls, approximate spend. The queued
candidate was per-agent cost/latency rollups.

## Decision

`openharness/metrics.py` — a stdlib-only reducer over the same session
files the observers tail:

- `session_metrics(path)` → `{events, messages, tool_calls,
  duration_seconds, tokens{input,output,cache_*}, models,
  est_cost_usd, cost_approximate}`.
- Tolerant parsing: timestamp from `timestamp` (ISO-8601), usage from
  `usage`/`message.usage`/`data.usage`, tool calls counted from
  `tool_use`/`tool_call` content blocks. Unparseable lines skipped.
- Cost is **approximate by design**: a small `_PRICING` table for known
  Claude models, sonnet-class fallback, `cost_approximate: true` when the
  model isn't priced. Unknown models still report tokens — the honest
  number — rather than a fabricated dollar figure.
- `summarize()` aggregates across sessions.

API (same verbs as everything else, D005-compatible):
`GET /api/sessions/{sid}/metrics` and `GET /api/metrics` (summary +
per-session).

## Consequences

- Read-only like everything else in the observer path — no instrumentation
  hooks into agents (D006 preserved).
- Stdlib-only → the `--no-deps` test constraint holds; 5 new tests.
- Pricing table will drift — that's why it's small, flagged, and
  overridable later; tokens are the durable metric.
- Per-*agent* rollups come free since `file`/session ids carry the agent
  prefix; a grouped-by-agent view is a future UI concern, not a data gap.
