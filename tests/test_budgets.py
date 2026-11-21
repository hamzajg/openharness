"""D003/D012/D016 LOC budgets are a CI gate, not dashboard decoration."""

from pathlib import Path

from openharness.serve_api import CORE_BUDGET, PLATFORM_BUDGET, _harness_stats

ROOT = Path(__file__).resolve().parent.parent


def test_runtime_buckets_stay_within_their_ceilings():
    stats = _harness_stats(ROOT)
    assert stats["core_loc"] <= CORE_BUDGET, (
        f"core {stats['core_loc']}/{CORE_BUDGET}: delete code first, or "
        "supersede D016 with a new decision"
    )
    assert stats["platform_loc"] <= PLATFORM_BUDGET, (
        f"platform {stats['platform_loc']}/{PLATFORM_BUDGET}"
    )
