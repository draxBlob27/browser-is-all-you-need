from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT_PATH = Path("scripts/build_eval_subset.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("build_eval_subset", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_select_subset_preserves_stratum_proportions() -> None:
    module = _load_module()

    task_ids = [f"t{i:04d}" for i in range(1000)]
    primary = {}
    secondary = {}
    for i, tid in enumerate(task_ids):
        if i < 600:
            primary[tid] = {"reason": "correct", "runtime_speedup": 2.0 if i < 300 else 0.5, "all_tests_pass": True, "reward": 1.5 if i < 300 else 1.0}
        elif i < 900:
            primary[tid] = {"reason": "tests_failed", "runtime_speedup": None, "all_tests_pass": False, "reward": -0.2}
        else:
            primary[tid] = {"reason": "invalid_format", "runtime_speedup": None, "all_tests_pass": False, "reward": -1.0}
        secondary[tid] = {"reason": "correct", "runtime_speedup": 1.0, "all_tests_pass": i % 5 == 0, "reward": 0.0}

    picked = module.select_subset(task_ids, primary, secondary, target=100, seed=7)
    assert len(picked) == 100
    assert len(set(picked)) == 100

    buckets = {"correct_faster": 0, "correct_slower": 0, "tests_failed": 0, "invalid_format": 0}
    for tid in picked:
        buckets[module.reason_bucket(primary[tid])] += 1
    # proportions: 30/30/30/10 out of 100, allow rounding slack of 2
    assert abs(buckets["correct_faster"] - 30) <= 2
    assert abs(buckets["correct_slower"] - 30) <= 2
    assert abs(buckets["tests_failed"] - 30) <= 2
    assert abs(buckets["invalid_format"] - 10) <= 2

    full = module.metrics(primary, task_ids)
    mini = module.metrics(primary, picked)
    assert abs(full["pass_rate"] - mini["pass_rate"]) < 0.03
    assert abs(full["mean_reward"] - mini["mean_reward"]) < 0.06
