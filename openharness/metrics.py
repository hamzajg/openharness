"""Per-session cost/latency rollups over agent CLI JSONL logs.

The observers (`observers/`) already tail the session files the agent CLIs
write; this module reads the same files and reduces them to numbers an
operator can compare across agents: duration, message/tool-call counts,
token usage, and an approximate USD estimate.

Stdlib-only by design — the test suite runs with `--no-deps`.
"""

import json
from datetime import datetime
from pathlib import Path

# Approximate USD per 1M tokens (input, output). Kept deliberately small and
# clearly approximate — vendor pricing changes; null is returned for models
# not listed rather than guessing.
_PRICING = {
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-opus-4-1": (15.0, 75.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
_DEFAULT_PRICING = (3.0, 15.0)  # sonnet-class fallback


def _parse_ts(value) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _usage_of(entry: dict) -> dict | None:
    """Find a token-usage object wherever the CLI puts it."""
    for container in (entry, entry.get("message"), entry.get("data")):
        if isinstance(container, dict):
            usage = container.get("usage")
            if isinstance(usage, dict):
                return usage
    return None


def _model_of(entry: dict) -> str | None:
    msg = entry.get("message")
    if isinstance(msg, dict):
        model = msg.get("model")
        if isinstance(model, str):
            return model
    return entry.get("model") if isinstance(entry.get("model"), str) else None


def session_metrics(path: str | Path) -> dict:
    """Roll up one session JSONL/JSON file into cost/latency numbers."""
    p = Path(path)
    tokens_in = tokens_out = cache_read = cache_write = 0
    messages = tool_calls = 0
    first_ts = last_ts = None
    models: set[str] = set()
    lines = events = 0

    try:
        text = p.read_text(errors="ignore")
    except OSError:
        return {"error": f"unreadable: {p}"}

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        lines += 1
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict):
            continue
        events += 1

        ts = _parse_ts(entry.get("timestamp"))
        if ts is not None:
            first_ts = ts if first_ts is None else min(first_ts, ts)
            last_ts = ts if last_ts is None else max(last_ts, ts)

        model = _model_of(entry)
        if model:
            models.add(model)

        usage = _usage_of(entry)
        if usage:
            tokens_in += int(usage.get("input_tokens") or 0)
            tokens_out += int(usage.get("output_tokens") or 0)
            cache_read += int(usage.get("cache_read_input_tokens") or 0)
            cache_write += int(usage.get("cache_creation_input_tokens") or 0)

        msg = entry.get("message")
        if isinstance(msg, dict):
            messages += 1
            content = msg.get("content")
            if isinstance(content, list):
                tool_calls += sum(
                    1 for b in content
                    if isinstance(b, dict) and b.get("type") in ("tool_use", "tool_call")
                )

    duration = round(last_ts - first_ts, 1) if first_ts and last_ts else None

    # Cost: priced per-model when known; mixed/unknown models use the
    # sonnet-class fallback and are flagged as approximate.
    cost = None
    priced = True
    if tokens_in or tokens_out:
        cost = 0.0
        for model in models or {None}:
            pin, pout = _PRICING.get(model or "", _DEFAULT_PRICING)
            if model not in _PRICING:
                priced = False
            # Split tokens evenly across observed models — approximation.
            share = 1.0 / max(len(models), 1)
            cost += (tokens_in * pin + tokens_out * pout) / 1_000_000 * share
        cost = round(cost, 6)

    return {
        "file": str(p),
        "lines": lines,
        "events": events,
        "messages": messages,
        "tool_calls": tool_calls,
        "duration_seconds": duration,
        "tokens": {
            "input": tokens_in,
            "output": tokens_out,
            "cache_read": cache_read,
            "cache_write": cache_write,
        },
        "models": sorted(models),
        "est_cost_usd": cost,
        "cost_approximate": not priced,
    }


def summarize(metrics: list[dict]) -> dict:
    """Aggregate per-session rollups into fleet-level numbers."""
    ok = [m for m in metrics if "error" not in m]
    total_tokens = sum(m["tokens"]["input"] + m["tokens"]["output"] for m in ok)
    total_cost = sum(m["est_cost_usd"] or 0 for m in ok)
    durations = [m["duration_seconds"] for m in ok if m["duration_seconds"] is not None]
    return {
        "sessions": len(ok),
        "errors": len(metrics) - len(ok),
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 6) if total_cost else None,
        "total_tool_calls": sum(m["tool_calls"] for m in ok),
        "avg_session_seconds": round(sum(durations) / len(durations), 1) if durations else None,
        "max_session_seconds": max(durations) if durations else None,
    }
