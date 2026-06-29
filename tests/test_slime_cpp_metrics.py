from __future__ import annotations

import pytest

from w8_biayn.slime_integration.cpp_metrics import aggregate_cpp_reward_metrics


def test_aggregate_cpp_reward_metrics_returns_stable_zero_metrics_for_empty_input():
    metrics = aggregate_cpp_reward_metrics([])

    assert metrics == {
        "reward/cpp/mean": 0.0,
        "reward/cpp/max": 0.0,
        "reward/cpp/min": 0.0,
        "reward/cpp/std": 0.0,
        "reward/cpp/format_valid_rate": 0.0,
        "reward/cpp/all_tests_pass_rate": 0.0,
        "reward/cpp/compile_error_rate": 0.0,
        "reward/cpp/runtime_speedup_mean": 0.0,
        "reward/cpp/tests_passed_mean": 0.0,
    }


def test_aggregate_cpp_reward_metrics_computes_reward_stats_and_rates():
    metrics = aggregate_cpp_reward_metrics(
        [
            {
                "reward": 1.0,
                "format_valid": True,
                "all_tests_pass": True,
                "compile_error": False,
                "runtime_speedup": 2.0,
                "tests_passed": 4,
            },
            {
                "reward": -1.0,
                "format_valid": False,
                "all_tests_pass": False,
                "compile_error": False,
                "runtime_speedup": None,
                "tests_passed": 0,
            },
            {
                "reward": 0.5,
                "format_valid": True,
                "all_tests_pass": False,
                "compile_error": True,
                "runtime_speedup": 1.5,
                "tests_passed": 2,
            },
        ]
    )

    assert metrics["reward/cpp/mean"] == pytest.approx(1 / 6)
    assert metrics["reward/cpp/max"] == pytest.approx(1.0)
    assert metrics["reward/cpp/min"] == pytest.approx(-1.0)
    assert metrics["reward/cpp/std"] == pytest.approx(0.8498365856)
    assert metrics["reward/cpp/format_valid_rate"] == pytest.approx(2 / 3)
    assert metrics["reward/cpp/all_tests_pass_rate"] == pytest.approx(1 / 3)
    assert metrics["reward/cpp/compile_error_rate"] == pytest.approx(1 / 3)
    assert metrics["reward/cpp/runtime_speedup_mean"] == pytest.approx(1.75)
    assert metrics["reward/cpp/tests_passed_mean"] == pytest.approx(2.0)


def test_aggregate_cpp_reward_metrics_supports_custom_prefix():
    metrics = aggregate_cpp_reward_metrics(
        [{"reward": 2.0, "format_valid": True, "all_tests_pass": True, "tests_passed": 3}],
        prefix="eval/cpp/",
    )

    assert metrics["eval/cpp/mean"] == pytest.approx(2.0)
    assert metrics["eval/cpp/format_valid_rate"] == pytest.approx(1.0)
    assert metrics["eval/cpp/tests_passed_mean"] == pytest.approx(3.0)
    assert "reward/cpp/mean" not in metrics


def test_aggregate_cpp_reward_metrics_ignores_invalid_speedups_but_keeps_reward_rows():
    metrics = aggregate_cpp_reward_metrics(
        [
            {"reward": "1.0", "runtime_speedup": "bad", "tests_passed": "2"},
            {"reward": None, "runtime_speedup": float("nan"), "tests_passed": None},
            {"reward": 3.0, "runtime_speedup": 2.0, "tests_passed": 4},
        ]
    )

    assert metrics["reward/cpp/mean"] == pytest.approx(4 / 3)
    assert metrics["reward/cpp/runtime_speedup_mean"] == pytest.approx(2.0)
    assert metrics["reward/cpp/tests_passed_mean"] == pytest.approx(2.0)
