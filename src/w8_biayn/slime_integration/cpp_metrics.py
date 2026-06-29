"""Metric aggregation helpers for SLIME C++ reward results."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any


def aggregate_cpp_reward_metrics(
    results: Sequence[Mapping[str, Any]],
    *,
    prefix: str = "reward/cpp",
) -> dict[str, float]:
    """Aggregate scored C++ rollout rows into stable tracking metrics."""

    metric_prefix = prefix.rstrip("/")
    rewards = [_float_or_default(result.get("reward")) for result in results]
    speedups = [
        converted
        for result in results
        if (converted := _optional_float(result.get("runtime_speedup"))) is not None
    ]
    tests_passed = [_float_or_default(result.get("tests_passed")) for result in results]

    return {
        f"{metric_prefix}/mean": _mean(rewards),
        f"{metric_prefix}/max": max(rewards) if rewards else 0.0,
        f"{metric_prefix}/min": min(rewards) if rewards else 0.0,
        f"{metric_prefix}/std": _population_std(rewards),
        f"{metric_prefix}/format_valid_rate": _bool_rate(results, "format_valid"),
        f"{metric_prefix}/all_tests_pass_rate": _bool_rate(results, "all_tests_pass"),
        f"{metric_prefix}/compile_error_rate": _bool_rate(results, "compile_error"),
        f"{metric_prefix}/runtime_speedup_mean": _mean(speedups),
        f"{metric_prefix}/tests_passed_mean": _mean(tests_passed),
    }


def _bool_rate(results: Sequence[Mapping[str, Any]], key: str) -> float:
    if not results:
        return 0.0
    return sum(1.0 for result in results if bool(result.get(key))) / len(results)


def _float_or_default(value: Any, *, default: float = 0.0) -> float:
    converted = _optional_float(value)
    return default if converted is None else converted


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if math.isfinite(converted) else None


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return math.fsum(values) / len(values)


def _population_std(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean = _mean(values)
    variance = math.fsum((value - mean) ** 2 for value in values) / len(values)
    return math.sqrt(variance)
