"""Synthetic collector overhead only; not a forensic Case performance baseline.

Run from the repository: python -m scripts.measure_profiling_overhead
"""
from __future__ import annotations

import json
from statistics import median
from timeit import repeat

from app.observability.profiling import ProfilingBinding, profile_call, profiling_scope
from app.observability.service import ObservabilityService


def main() -> None:
    iterations = 10_000
    collector = ObservabilityService()
    collector.begin_case("synthetic-overhead", [("fixture", 4)], 0)

    def operation() -> int:
        return 42

    def invocation() -> int:
        return profile_call("synthetic", "operation", operation)

    disabled = median(repeat(invocation, number=iterations, repeat=5))
    with profiling_scope(ProfilingBinding(collector, None, "file_fixture", 4)):
        enabled = median(repeat(invocation, number=iterations, repeat=5))
    snapshot = median(repeat(collector.snapshot, number=100, repeat=5)) / 100
    payload = {
        "measurement": "synthetic_collector_overhead",
        "iterations_per_repeat": iterations,
        "repeats": 5,
        "disabled_us_per_call": disabled / iterations * 1_000_000,
        "enabled_us_per_call": enabled / iterations * 1_000_000,
        "added_us_per_call": (enabled - disabled) / iterations * 1_000_000,
        "snapshot_ms_2000_samples": snapshot * 1_000,
        "case_baseline": None,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
