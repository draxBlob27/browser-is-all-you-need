from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path

import pytest

from w8_biayn.integrations import slime_polyglot_cpp as polyglot


EXAMPLE_ROOT = Path("examples/slime/moonlight_polyglot_cpp")
RUNNER = EXAMPLE_ROOT / "moonlight_polyglot_cpp.sh"
README = EXAMPLE_ROOT / "README.md"


def make_polyglot_tree(tmp_path: Path) -> Path:
    exercise = tmp_path / "polyglot-benchmark" / "cpp" / "exercises" / "practice" / "two-fer"
    (exercise / ".meta").mkdir(parents=True)
    (exercise / ".docs").mkdir()
    (exercise / ".meta" / "config.json").write_text(
        json.dumps(
            {
                "blurb": "Create a phrase for one person or for everyone.",
                "files": {
                    "solution": ["two_fer.cpp", "two_fer.h"],
                    "test": ["two_fer_test.cpp"],
                    "example": ["example.cpp"],
                }
            }
        ),
        encoding="utf-8",
    )
    (exercise / ".docs" / "introduction.md").write_text("Intro text.", encoding="utf-8")
    (exercise / ".docs" / "instructions.md").write_text("Return a phrase.", encoding="utf-8")
    (exercise / "two_fer.cpp").write_text("std::string two_fer() { return \"\"; }\n", encoding="utf-8")
    (exercise / "two_fer.h").write_text("#pragma once\n", encoding="utf-8")
    (exercise / "two_fer_test.cpp").write_text("// tests\n", encoding="utf-8")
    (exercise / "example.cpp").write_text("// example\n", encoding="utf-8")
    (exercise / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.10)\n", encoding="utf-8")
    return tmp_path / "polyglot-benchmark"


def valid_response() -> str:
    return """```path
two_fer.cpp
```

```cpp
std::string two_fer() { return "One for you, one for me."; }
```

```path
two_fer.h
```

```hpp
#pragma once
std::string two_fer();
```
"""


def recoverable_unlabeled_response() -> str:
    return """Here is the complete solution.

```cpp
std::string two_fer() { return "One for you, one for me."; }
```

```hpp
#pragma once
std::string two_fer();
```
<|im_end|>
"""


def test_build_slime_polyglot_cpp_dataset_writes_eval_rows_and_manifest(tmp_path: Path) -> None:
    source = make_polyglot_tree(tmp_path)
    out = tmp_path / "out"

    paths = polyglot.build_slime_polyglot_cpp_dataset(source, out, eval_limit=None, run_id="r1", force=True)

    rows = [json.loads(line) for line in paths["eval"].read_text(encoding="utf-8").splitlines()]
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert len(rows) == 1
    row = rows[0]
    assert row["task_id"] == "cpp/two-fer"
    assert row["label"] == "cpp/two-fer"
    assert row["split"] == "eval"
    assert "Return replacements for every editable solution file" in row["prompt"]
    assert "Return a phrase." in row["prompt"]
    assert row["metadata"]["solution_files"] == ["two_fer.cpp", "two_fer.h"]
    assert row["metadata"]["blurb"] == "Create a phrase for one person or for everyone."
    assert row["metadata"]["category"] == "strings"
    assert row["metadata"]["categories"] == ["strings", "conditionals"]
    assert row["metadata"]["exercise_path"] == "tasks/cpp/exercises/practice/two-fer"
    assert (out / row["metadata"]["exercise_path"] / "two_fer_test.cpp").exists()
    assert manifest["kind"] == "slime-polyglot-cpp-dataset"
    assert manifest["counts"] == {"copied_exercises": 1, "eval": 1}


def test_parse_replacements_accepts_path_code_pairs_and_rejects_bad_files() -> None:
    parsed = polyglot.parse_replacements(valid_response(), ["two_fer.cpp", "two_fer.h"])
    assert parsed["two_fer.cpp"].startswith("std::string two_fer")
    assert parsed["two_fer.h"].startswith("#pragma once")

    with pytest.raises(polyglot.PolyglotResponseError, match="unexpected prose"):
        polyglot.parse_replacements("Here is the fix.\n" + valid_response(), ["two_fer.cpp", "two_fer.h"])

    with pytest.raises(polyglot.PolyglotResponseError, match="unknown or forbidden"):
        polyglot.parse_replacements(valid_response().replace("two_fer.h", "two_fer_test.cpp"), ["two_fer.cpp", "two_fer.h"])

    with pytest.raises(polyglot.PolyglotResponseError, match="missing replacement"):
        polyglot.parse_replacements(
            """```path
two_fer.cpp
```

```cpp
ok
```
""",
            ["two_fer.cpp", "two_fer.h"],
        )


def test_recover_replacements_diagnoses_unlabeled_code_blocks_without_changing_strict_parser() -> None:
    response = recoverable_unlabeled_response()

    with pytest.raises(polyglot.PolyglotResponseError, match="unexpected prose"):
        polyglot.parse_replacements(response, ["two_fer.cpp", "two_fer.h"])

    recovered = polyglot.recover_replacements(response, ["two_fer.cpp", "two_fer.h"])

    assert recovered["two_fer.cpp"].startswith("std::string two_fer")
    assert recovered["two_fer.h"].startswith("#pragma once")


def test_recover_replacements_can_use_markdown_headings_but_not_forbidden_files() -> None:
    response = """### `two_fer.h`

```hpp
#pragma once
std::string two_fer();
```

### `two_fer.cpp`

```cpp
std::string two_fer() { return "One for you, one for me."; }
```
"""

    recovered = polyglot.recover_replacements(response, ["two_fer.cpp", "two_fer.h"])

    assert recovered["two_fer.cpp"].startswith("std::string two_fer")
    assert recovered["two_fer.h"].startswith("#pragma once")

    forbidden = response.replace("two_fer.h", "two_fer_test.cpp", 1)
    with pytest.raises(polyglot.PolyglotResponseError, match="unknown or forbidden"):
        polyglot.recover_replacements(forbidden, ["two_fer.cpp", "two_fer.h"])


def test_reward_func_scores_invalid_format_without_running_tests() -> None:
    sample = {
        "metadata": {
            "task_id": "cpp/two-fer",
            "problem_id": "two-fer",
            "exercise": "two-fer",
            "solution_files": ["two_fer.cpp"],
        },
        "response": "plain prose",
    }

    record = asyncio.run(polyglot.reward_func(None, sample))

    assert record["score"] == -1.0
    assert record["reason"] == "invalid_format"
    assert record["category"] == "strings"
    assert record["categories"] == ["strings", "conditionals"]
    assert record["all_tests_pass"] is False
    assert record["tests_total"] == 0


def test_reward_func_records_recovered_diagnostics_without_awarding_strict_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_polyglot_tree(tmp_path)
    exercise = source / "cpp" / "exercises" / "practice" / "two-fer"
    calls: list[Path] = []

    def fake_runner(path: str | Path) -> polyglot.PolyglotTestResult:
        path = Path(path)
        calls.append(path)
        assert (path / "two_fer.cpp").read_text(encoding="utf-8").startswith("std::string two_fer")
        assert (path / "two_fer.h").read_text(encoding="utf-8").startswith("#pragma once")
        return polyglot.PolyglotTestResult(returncode=0, logs="passed")

    monkeypatch.setattr(polyglot, "run_polyglot_tests", fake_runner)

    sample = {
        "metadata": {
            "task_id": "cpp/two-fer",
            "problem_id": "two-fer",
            "split": "eval",
            "exercise": "two-fer",
            "exercise_path": str(exercise),
            "solution_files": ["two_fer.cpp", "two_fer.h"],
        },
        "response": recoverable_unlabeled_response(),
    }

    record = asyncio.run(polyglot.reward_func(None, sample))

    assert calls
    assert record["score"] == -1.0
    assert record["reason"] == "invalid_format"
    assert record["format_valid"] is False
    assert record["all_tests_pass"] is False
    assert record["tests_total"] == 0
    assert record["candidate_bytes"] == 0
    assert record["recovered_format"] is True
    assert record["recovered_reason"] == "passed"
    assert record["recovered_all_tests_pass"] is True
    assert record["recovered_tests_passed"] == 1
    assert record["recovered_tests_total"] == 1
    assert record["recovered_candidate_bytes"] > 0


def test_reward_func_applies_replacements_and_records_test_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = make_polyglot_tree(tmp_path)
    exercise = source / "cpp" / "exercises" / "practice" / "two-fer"
    calls: list[Path] = []

    def fake_runner(path: str | Path) -> polyglot.PolyglotTestResult:
        path = Path(path)
        calls.append(path)
        assert (path / "two_fer.cpp").read_text(encoding="utf-8").startswith("std::string two_fer")
        return polyglot.PolyglotTestResult(returncode=0, logs="passed")

    monkeypatch.setattr(polyglot, "run_polyglot_tests", fake_runner)

    sample = {
        "metadata": {
            "task_id": "cpp/two-fer",
            "problem_id": "two-fer",
            "split": "eval",
            "exercise": "two-fer",
            "exercise_path": str(exercise),
            "solution_files": ["two_fer.cpp", "two_fer.h"],
        },
        "response": valid_response(),
    }

    record = asyncio.run(polyglot.reward_func(None, sample))

    assert calls
    assert record["score"] == 1.0
    assert record["reason"] == "passed"
    assert record["all_tests_pass"] is True
    assert record["category"] == "strings"
    assert record["categories"] == ["strings", "conditionals"]
    assert record["tests_passed"] == 1
    assert record["tests_total"] == 1
    assert record["runtime_cpu_ns"] is None


def test_score_debug_dump_writes_polyglot_summary_without_speed_metrics(tmp_path: Path) -> None:
    debug_jsonl = tmp_path / "debug.jsonl"
    debug_jsonl.write_text(
        json.dumps(
            {
                "index": 0,
                "metadata": {"task_id": "cpp/two-fer", "problem_id": "two-fer", "split": "eval"},
                "response": valid_response(),
                "reward": {
                    "score": 1.0,
                    "reward": 1.0,
                    "reason": "passed",
                    "task_id": "cpp/two-fer",
                    "problem_id": "two-fer",
                    "split": "eval",
                    "all_tests_pass": True,
                    "tests_passed": 1,
                    "tests_total": 1,
                    "compile_error": False,
                    "timeout": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    _records, summary, paths = polyglot.score_debug_dump(label="base", debug_samples_path=debug_jsonl, output_dir=tmp_path / "eval")

    assert paths["records"].exists()
    assert paths["summary"].exists()
    assert summary["pass_rate"] == 1.0
    assert summary["category_summary"]["strings"]["pass_rate"] == 1.0
    assert summary["category_summary"]["conditionals"]["task_count"] == 1
    assert summary["best_records"][0]["categories"] == ["strings", "conditionals"]
    assert summary["invalid_format_rate"] == 0.0
    assert "correct_and_faster_rate" not in summary
    assert "missing_runtime_rate" not in summary


def test_aggregate_reports_recovery_diagnostics_without_changing_strict_pass_rate() -> None:
    records = [
        {
            "score": -1.0,
            "reward": -1.0,
            "reason": "invalid_format",
            "task_id": "cpp/two-fer",
            "problem_id": "two-fer",
            "split": "eval",
            "all_tests_pass": False,
            "compile_error": False,
            "timeout": False,
            "category": "strings",
            "categories": ["strings", "conditionals"],
            "recovered_format": True,
            "recovered_reason": "passed",
            "recovered_all_tests_pass": True,
            "recovered_compile_error": False,
            "recovered_timeout": False,
        }
    ]

    summary = polyglot.aggregate_polyglot_records(records, label="base")

    assert summary["pass_rate"] == 0.0
    assert summary["invalid_format_rate"] == 1.0
    assert summary["recovered_format_rate"] == 1.0
    assert summary["recovered_pass_rate"] == 1.0
    assert summary["recovered_task_pass_rate"] == 1.0
    assert summary["category_summary"]["strings"]["pass_rate"] == 0.0
    assert summary["category_summary"]["strings"]["recovered_pass_rate"] == 1.0
    assert summary["category_summary"]["conditionals"]["recovered_task_pass_rate"] == 1.0


def test_polyglot_sandbox_image_plan_installs_cmake_and_make() -> None:
    plan = polyglot.polyglot_sandbox_image_build_plan()
    assert "docker build -t w8-biayn-polyglot-cpp:latest -" in plan
    assert "cmake make python3" in plan
    assert plan.rstrip().endswith("DOCKERFILE")


def test_moonlight_polyglot_cpp_example_files_are_present_and_executable() -> None:
    expected = {"README.md", "moonlight_polyglot_cpp.sh", "prepare_data.sh", "eval_base.sh"}

    assert expected.issubset({path.name for path in EXAMPLE_ROOT.iterdir()})
    for script in expected - {"README.md"}:
        assert os.access(EXAMPLE_ROOT / script, os.X_OK), script


def test_moonlight_polyglot_cpp_scripts_are_bash_syntax_valid() -> None:
    for script in sorted(EXAMPLE_ROOT.glob("*.sh")):
        subprocess.run(["bash", "-n", str(script)], check=True)


def test_moonlight_polyglot_cpp_runner_is_base_eval_only() -> None:
    text = RUNNER.read_text(encoding="utf-8")

    assert "prepare-data|base-eval" in text
    assert "sft" not in text.lower()
    assert "grpo" not in text.lower()
    assert 'RUN_ID="${SLIME_RUN_ID:-moonlight_polyglot_cpp}"' in text
    assert 'POLYGLOT_SOURCE="${SLIME_POLYGLOT_SOURCE:-${REPO_ROOT}/.w8-biayn/data/polyglot-benchmark}"' in text
    assert 'EVAL_MAX_RESPONSE_LEN="${SLIME_EVAL_MAX_RESPONSE_LEN:-4096}"' in text
    assert "w8_biayn.integrations.slime_polyglot_cpp build-data" in text
    assert "--eval-prompt-data polyglot_cpp" in text
    assert "--custom-rm-path w8_biayn.integrations.slime_polyglot_cpp.reward_func" in text
    assert "W8_SLIME_POLYGLOT_SANDBOX_IMAGE" in text
    assert "base.records.jsonl" in text
    assert "correct_and_faster_rate" not in text


def test_moonlight_polyglot_cpp_readme_documents_operator_flow() -> None:
    text = README.read_text(encoding="utf-8")

    assert "Aider-AI/polyglot-benchmark" in text
    assert "not an official Aider leaderboard run" in text
    assert "sandbox-image --dry-run" in text
    assert "bash examples/slime/moonlight_polyglot_cpp/prepare_data.sh" in text
    assert "bash examples/slime/moonlight_polyglot_cpp/eval_base.sh" in text
    assert "base.records.jsonl" in text
    assert "base.summary.json" in text
    assert "recovered_pass_rate" in text
    assert "correct_and_faster_rate" in text

