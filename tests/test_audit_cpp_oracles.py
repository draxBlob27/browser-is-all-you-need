from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from w8_biayn.cpp_perf.schema import CppTask, ReferencePerformance, TestCase, TestCoverage


SCRIPT_PATH = Path("scripts/audit_cpp_oracles.py")


def load_module():
    spec = importlib.util.spec_from_file_location("audit_cpp_oracles", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_task_rows_resolves_metadata_paths_and_deduplicates(tmp_path: Path) -> None:
    module = load_module()
    task = CppTask(
        task_id="task-1",
        problem_id="p1",
        prompt_code="int main(){return 0;}\n",
        unit_tests=[TestCase(input="", expected="")],
        hidden_tests=[TestCase(input="", expected="")],
        oracle_solution="int main(){return 0;}\n",
        test_coverage=TestCoverage(line=1.0, branch=1.0),
        reference=ReferencePerformance(value=1),
        split="test",
    )
    task.write_json(tmp_path / "tasks" / "test" / "task-1.json")
    rows_path = tmp_path / "eval.jsonl"
    row = {"task_id": "task-1", "metadata": {"task_path": "tasks/test/task-1.json"}}
    rows_path.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")

    loaded = module.load_task_rows(tmp_path, rows_path)

    assert len(loaded) == 1
    assert loaded[0][1].task_id == "task-1"
