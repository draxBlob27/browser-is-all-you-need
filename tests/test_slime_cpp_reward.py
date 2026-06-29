from __future__ import annotations

import pytest

from w8_biayn.cpp_perf.schema import CppTask, HarnessResult, ReferencePerformance, TestCase, TestCoverage
from w8_biayn.slime_integration.cpp_reward import (
    SlimeCppRewardError,
    load_slime_cpp_task,
    resolve_slime_cpp_task_path,
    score_slime_cpp_row,
)


VALID_OUTPUT = """<reasoning>Use the same logic with a valid wrapper.</reasoning>
```cpp
#include <iostream>
int main(){int n; std::cin>>n; std::cout<<n<<"\\n";}
```
"""


INVALID_OUTPUT = "plain text only"


def sample_task(task_id: str = "train_1", split: str = "train") -> CppTask:
    return CppTask(
        task_id=task_id,
        problem_id=f"p_{task_id}",
        prompt_code="#include <iostream>\nint main(){int n; std::cin>>n; std::cout<<n<<\"\\n\";}\n",
        unit_tests=[TestCase(input="1\n", expected="1\n")],
        hidden_tests=[TestCase(input="2\n", expected="2\n")],
        oracle_solution="#include <iostream>\nint main(){int n; std::cin>>n; std::cout<<n<<\"\\n\";}\n",
        test_coverage=TestCoverage(line=0.96, branch=0.86),
        reference=ReferencePerformance(value=100),
        split=split,  # type: ignore[arg-type]
    )


@pytest.fixture
def slime_row(tmp_path):
    bundle_root = tmp_path / "bundle"
    task_path = bundle_root / "tasks" / "train_1.json"
    sample_task().write_json(task_path)
    row = {
        "data_source": "cpp_perf",
        "prompt": "Optimize the following C++20 program...",
        "label": "train_1",
        "metadata": {
            "task_id": "train_1",
            "problem_id": "p_train_1",
            "split": "train",
            "task_path": "tasks/train_1.json",
        },
    }
    return bundle_root, row


def test_resolve_slime_cpp_task_path_from_bundle_root(slime_row):
    bundle_root, row = slime_row

    resolved = resolve_slime_cpp_task_path(row, bundle_root=bundle_root)

    assert resolved == (bundle_root / "tasks" / "train_1.json").resolve()


def test_load_slime_cpp_task_reads_task_json(slime_row):
    bundle_root, row = slime_row

    task = load_slime_cpp_task(row, bundle_root=bundle_root)

    assert task.task_id == "train_1"
    assert task.problem_id == "p_train_1"


def test_score_slime_cpp_row_uses_repo_reward_logic(slime_row):
    bundle_root, row = slime_row

    def runner(_task: CppTask, code: str) -> HarnessResult:
        assert "int main" in code
        return HarnessResult(
            tests_passed=2,
            tests_total=2,
            runtime_cpu_ns=50,
            runtime_wall_ns=75,
            reference_runtime_cpu_ns=100,
            reference_runtime_wall_ns=125,
            runtime_speedup=2.0,
        )

    scored = score_slime_cpp_row(row, VALID_OUTPUT, bundle_root=bundle_root, runner=runner)

    assert scored["reason"] == "correct"
    assert scored["format_valid"] is True
    assert scored["all_tests_pass"] is True
    assert scored["tests_passed"] == 2
    assert scored["runtime_speedup"] == pytest.approx(2.0)
    assert scored["reward"] > 1.0
    assert scored["candidate_bytes"] > 0
    assert scored["task_file"].endswith("tasks/train_1.json")


def test_score_slime_cpp_row_invalid_format_short_circuits_runner(slime_row):
    bundle_root, row = slime_row

    def runner(_task: CppTask, _code: str) -> HarnessResult:
        raise AssertionError("runner should not be called for invalid format")

    scored = score_slime_cpp_row(row, INVALID_OUTPUT, bundle_root=bundle_root, runner=runner)

    assert scored["reward"] == -1.0
    assert scored["reason"] == "invalid_format"
    assert scored["format_valid"] is False
    assert scored["tests_total"] == 0
    assert scored["candidate_bytes"] == 0


def test_resolve_slime_cpp_task_path_requires_metadata_task_path(tmp_path):
    row = {"metadata": {"task_id": "train_1"}}

    with pytest.raises(SlimeCppRewardError, match="metadata.task_path"):
        resolve_slime_cpp_task_path(row, bundle_root=tmp_path)


def test_resolve_slime_cpp_task_path_rejects_missing_file(tmp_path):
    row = {
        "metadata": {
            "task_id": "train_1",
            "task_path": "tasks/missing.json",
        }
    }

    with pytest.raises(FileNotFoundError, match="missing.json"):
        resolve_slime_cpp_task_path(row, bundle_root=tmp_path)
