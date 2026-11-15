"""Tests for metrics.py — session cost/latency rollups (stdlib-only)."""

import json
from pathlib import Path

from openharness.metrics import session_metrics, summarize


def _write_session(tmp_path: Path, entries: list[dict]) -> Path:
    p = tmp_path / "session.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return p


def _claude_line(ts: str, in_tok: int, out_tok: int, model="claude-sonnet-4-5",
                 tool_uses: int = 0):
    content = [{"type": "text", "text": "hi"}] * (1 - tool_uses) + [
        {"type": "tool_use", "id": f"t{i}", "name": "x", "input": {}}
        for i in range(tool_uses)
    ] if tool_uses else [{"type": "text", "text": "hi"}]
    return {
        "type": "assistant",
        "timestamp": ts,
        "message": {
            "model": model,
            "content": content,
            "usage": {"input_tokens": in_tok, "output_tokens": out_tok},
        },
    }


def test_session_metrics_counts_tokens_and_time(tmp_path):
    p = _write_session(tmp_path, [
        _claude_line("2026-01-01T00:00:00Z", 100, 50),
        _claude_line("2026-01-01T00:01:00Z", 200, 100, tool_uses=1),
        {"type": "user", "timestamp": "2026-01-01T00:00:30Z"},
    ])
    m = session_metrics(p)
    assert m["events"] == 3
    assert m["messages"] == 2
    assert m["tool_calls"] == 1
    assert m["duration_seconds"] == 60.0
    assert m["tokens"]["input"] == 300
    assert m["tokens"]["output"] == 150
    assert m["est_cost_usd"] is not None
    assert m["cost_approximate"] is False


def test_session_metrics_unknown_model_flags_approximate(tmp_path):
    p = _write_session(tmp_path, [
        _claude_line("2026-01-01T00:00:00Z", 100, 10, model="mystery-model"),
    ])
    m = session_metrics(p)
    assert m["cost_approximate"] is True


def test_session_metrics_missing_file_is_error(tmp_path):
    m = session_metrics(tmp_path / "nope.jsonl")
    assert "error" in m


def test_session_metrics_no_usage_has_no_cost(tmp_path):
    p = _write_session(tmp_path, [
        {"type": "user", "timestamp": "2026-01-01T00:00:00Z"},
        {"type": "assistant", "timestamp": "2026-01-01T00:00:05Z"},
    ])
    m = session_metrics(p)
    assert m["est_cost_usd"] is None
    assert m["duration_seconds"] == 5.0


def test_summarize_aggregates(tmp_path):
    p1 = _write_session(tmp_path, [
        _claude_line("2026-01-01T00:00:00Z", 100, 50),
        _claude_line("2026-01-01T00:01:00Z", 100, 50),
    ])
    p2 = tmp_path / "empty.jsonl"
    p2.write_text("")
    s = summarize([session_metrics(p1), session_metrics(p2)])
    assert s["sessions"] == 2
    assert s["total_tokens"] == 300
    assert s["avg_session_seconds"] == 60.0
