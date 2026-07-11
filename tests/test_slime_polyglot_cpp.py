from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from w8_biayn.integrations import slime_polyglot_cpp as polyglot


EXAMPLE_ROOT = Path("examples/slime/moonlight_polyglot_cpp")
RUNNER = EXAMPLE_ROOT / "moonlight_polyglot_cpp.sh"
README = EXAMPLE_ROOT / "README.md"


def make_polyglot_comparison_run(
    root: Path,
    *,
    run_id: str,
    task_samples: dict[str, list[bool]],
    config_overrides: dict[str, str] | None = None,
) -> Path:
    records: list[dict[str, object]] = []
    oracle_records: list[dict[str, object]] = []
    for exercise, samples in task_samples.items():
        categories = list(polyglot.categorize_polyglot_cpp_exercise(exercise))
        task_id = f"cpp/{exercise}"
        oracle_records.append(
            {
                "task_id": task_id,
                "exercise": exercise,
                "setup_valid": True,
                "passed": True,
                "reason": "passed",
                "oracle_input_sha256": f"sha256:{exercise}",
            }
        )
        for sample_index, passed in enumerate(samples):
            records.append(
                {
                    "score": 1.0 if passed else 0.0,
                    "reward": 1.0 if passed else 0.0,
                    "reason": "passed" if passed else "tests_failed",
                    "task_id": task_id,
                    "problem_id": exercise,
                    "exercise": exercise,
                    "split": "eval",
                    "sample_index": sample_index,
                    "all_tests_pass": passed,
                    "tests_passed": 1 if passed else 0,
                    "tests_total": 1,
                    "compile_error": False,
                    "timeout": False,
                    "categories": categories,
                    "category": categories[0],
                }
            )

    oracle_check = {
        "enabled": True,
        "blocking": True,
        "complete": True,
        "schema_version": polyglot.SCHEMA_VERSION,
        "oracle_protocol_version": polyglot.ORACLE_PROTOCOL_VERSION,
        "correct_answer_source": polyglot.ORACLE_CORRECT_ANSWER_SOURCE,
        "task_count": len(task_samples),
        "all_passed": True,
    }
    summary = polyglot.aggregate_polyglot_records(records, label="base")
    summary["oracle_setup_check"] = oracle_check
    (root / "eval").mkdir(parents=True)
    (root / "data").mkdir()
    (root / "stages" / "base-eval").mkdir(parents=True)
    (root / "eval" / "base.records.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )
    (root / "eval" / "base.summary.json").write_text(
        json.dumps(summary),
        encoding="utf-8",
    )
    (root / "data" / "oracle.records.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in oracle_records),
        encoding="utf-8",
    )
    config = {
        "hf_model_id": "moonshotai/Moonlight-16B-A3B-Instruct",
        "eval_max_response_len": "4096",
        "eval_temperature": "0.7",
        "eval_top_p": "1",
        "rollout_skip_special_tokens": "1",
        "polyglot_sandbox_image": "w8-biayn-polyglot-cpp:latest",
        "polyglot_test_timeout_seconds": "180",
    }
    config.update(config_overrides or {})
    receipt = {"status": "0", "ray_job_terminal_status": "SUCCEEDED", "run_id": run_id}
    receipt.update(config)
    (root / "stages" / "base-eval" / "run_receipt.txt").write_text(
        "".join(f"{key}={value}\n" for key, value in receipt.items()),
        encoding="utf-8",
    )
    return root


@pytest.fixture(autouse=True)
def stable_polyglot_sandbox_image_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        polyglot, "_polyglot_sandbox_image_id", lambda _image: "sha256:test-polyglot"
    )


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
                    "example": [".meta/example.cpp", ".meta/example.h"],
                },
            }
        ),
        encoding="utf-8",
    )
    (exercise / ".docs" / "introduction.md").write_text("Intro text.", encoding="utf-8")
    (exercise / ".docs" / "instructions.md").write_text("Return a phrase.", encoding="utf-8")
    (exercise / "two_fer.cpp").write_text(
        'std::string two_fer() { return ""; }\n', encoding="utf-8"
    )
    (exercise / "two_fer.h").write_text("#pragma once\n", encoding="utf-8")
    (exercise / "two_fer_test.cpp").write_text("// tests\n", encoding="utf-8")
    (exercise / ".meta" / "example.cpp").write_text("// oracle cpp\n", encoding="utf-8")
    (exercise / ".meta" / "example.h").write_text("// oracle header\n", encoding="utf-8")
    (exercise / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.10)\n", encoding="utf-8"
    )
    return tmp_path / "polyglot-benchmark"


def make_admitted_polyglot_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[str, Path]]:
    source = make_polyglot_tree(tmp_path)
    out = tmp_path / "data"
    monkeypatch.setattr(
        polyglot,
        "run_polyglot_tests",
        lambda _path: polyglot.PolyglotTestResult(returncode=0, logs="oracle passed"),
    )
    paths = polyglot.build_slime_polyglot_cpp_dataset(
        source, out, eval_limit=None, run_id="r1", force=True
    )
    return out, paths


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


def test_build_slime_polyglot_cpp_dataset_writes_eval_rows_and_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_polyglot_tree(tmp_path)
    out = tmp_path / "out"

    def fake_runner(path: str | Path) -> polyglot.PolyglotTestResult:
        exercise = Path(path)
        assert (exercise / "two_fer.cpp").read_text(encoding="utf-8") == "// oracle cpp\n"
        assert (exercise / "two_fer.h").read_text(encoding="utf-8") == "// oracle header\n"
        return polyglot.PolyglotTestResult(returncode=0, logs="oracle passed")

    monkeypatch.setattr(polyglot, "run_polyglot_tests", fake_runner)

    paths = polyglot.build_slime_polyglot_cpp_dataset(
        source, out, eval_limit=None, run_id="r1", force=True
    )

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
    assert row["metadata"]["oracle_setup_valid"] is True
    assert row["metadata"]["oracle_correct_answer_source"] == "files.example"
    assert (out / row["metadata"]["exercise_path"] / "two_fer_test.cpp").exists()
    assert manifest["kind"] == "slime-polyglot-cpp-dataset"
    assert manifest["schema_version"] == 2
    assert manifest["admitted"] is True
    assert manifest["counts"] == {
        "copied_exercises": 1,
        "eval": 1,
        "oracle_checked": 1,
        "oracle_passed": 1,
    }
    assert manifest["oracle_setup_check"]["all_passed"] is True
    assert manifest["oracle_setup_check"]["correct_answer_source"] == "files.example"
    assert paths["oracle_records"].exists()
    assert paths["oracle_summary"].exists()
    oracle_record = json.loads(paths["oracle_records"].read_text(encoding="utf-8"))
    assert oracle_record["setup_valid"] is True
    assert oracle_record["oracle_protocol_version"] == 1
    assert oracle_record["grader_config"]["sandbox_image"] == "w8-biayn-polyglot-cpp:latest"
    assert oracle_record["grader_config"]["sandbox_image_id"] == "sha256:test-polyglot"
    assert oracle_record["grader_config"]["test_timeout_seconds"] == 180
    assert len(oracle_record["oracle_input_sha256"]) == 64
    assert oracle_record["test_files"] == ["two_fer_test.cpp"]
    assert oracle_record["reference_file_mappings"] == [
        {"example_file": ".meta/example.cpp", "solution_file": "two_fer.cpp"},
        {"example_file": ".meta/example.h", "solution_file": "two_fer.h"},
    ]
    assert polyglot.validate_polyglot_dataset(out)["all_passed"] is True


def test_reference_mapping_supports_header_only_exercism_oracles(tmp_path: Path) -> None:
    exercise = tmp_path / "header-only"
    (exercise / ".meta").mkdir(parents=True)
    (exercise / "answer.cpp").write_text("// inert starter\n", encoding="utf-8")
    (exercise / "answer.h").write_text("// incomplete\n", encoding="utf-8")
    (exercise / ".meta" / "example.h").write_text("// complete header\n", encoding="utf-8")

    replacements, mappings, unmapped = polyglot.polyglot_reference_replacements(
        exercise,
        solution_files=["answer.cpp", "answer.h"],
        example_files=[".meta/example.h"],
    )

    assert replacements == {"answer.h": "// complete header\n"}
    assert mappings == [{"example_file": ".meta/example.h", "solution_file": "answer.h"}]
    assert unmapped == ["answer.cpp"]


def test_build_data_blocks_failed_oracle_but_preserves_failure_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_polyglot_tree(tmp_path)
    out = tmp_path / "out"
    monkeypatch.setattr(
        polyglot,
        "run_polyglot_tests",
        lambda _path: polyglot.PolyglotTestResult(returncode=1, logs="tests failed"),
    )

    with pytest.raises(ValueError, match="oracle preflight failed"):
        polyglot.build_slime_polyglot_cpp_dataset(
            source, out, eval_limit=None, run_id="r1", force=True
        )

    assert not (out / "manifest.json").exists()
    assert not (out / "eval" / "cpp.jsonl").exists()
    oracle_summary = json.loads((out / "oracle.summary.json").read_text(encoding="utf-8"))
    oracle_record = json.loads((out / "oracle.records.jsonl").read_text(encoding="utf-8"))
    assert oracle_summary["all_passed"] is False
    assert oracle_summary["failed_task_ids"] == ["cpp/two-fer"]
    assert oracle_record["reason"] == "tests_failed"
    assert oracle_record["setup_valid"] is False


def test_validate_polyglot_dataset_rejects_forged_passing_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, paths = make_admitted_polyglot_data(tmp_path, monkeypatch)
    record = json.loads(paths["oracle_records"].read_text(encoding="utf-8"))
    record["setup_valid"] = False
    paths["oracle_records"].write_text(json.dumps(record) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="does not prove admission"):
        polyglot.validate_polyglot_dataset(data_root)


def test_validate_polyglot_dataset_rejects_stale_task_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, _paths = make_admitted_polyglot_data(tmp_path, monkeypatch)
    test_file = (
        data_root / "tasks" / "cpp" / "exercises" / "practice" / "two-fer" / "two_fer_test.cpp"
    )
    test_file.write_text("// tampered tests\n", encoding="utf-8")

    with pytest.raises(ValueError, match="stale Polyglot oracle record"):
        polyglot.validate_polyglot_dataset(data_root)


def test_validate_polyglot_dataset_rejects_changed_sandbox_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, _paths = make_admitted_polyglot_data(tmp_path, monkeypatch)
    monkeypatch.setattr(polyglot, "_polyglot_sandbox_image_id", lambda _image: "sha256:changed")

    with pytest.raises(ValueError, match="does not prove admission"):
        polyglot.validate_polyglot_dataset(data_root)


def test_validate_polyglot_dataset_recomputes_summary_from_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, paths = make_admitted_polyglot_data(tmp_path, monkeypatch)
    summary = json.loads(paths["oracle_summary"].read_text(encoding="utf-8"))
    summary["passed_count"] = 0
    paths["oracle_summary"].write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(ValueError, match="summary does not match records"):
        polyglot.validate_polyglot_dataset(data_root)


def test_validate_polyglot_dataset_rejects_oracle_eval_task_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, paths = make_admitted_polyglot_data(tmp_path, monkeypatch)
    row = json.loads(paths["eval"].read_text(encoding="utf-8"))
    row["task_id"] = "cpp/not-two-fer"
    row["label"] = row["task_id"]
    paths["eval"].write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="oracle/eval task mismatch"):
        polyglot.validate_polyglot_dataset(data_root)


def test_validate_polyglot_dataset_rejects_unrecorded_copied_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, paths = make_admitted_polyglot_data(tmp_path, monkeypatch)
    tasks_root = paths["tasks"]
    shutil.copytree(tasks_root / "two-fer", tasks_root / "allergies")

    with pytest.raises(ValueError, match="oracle/copied-task mismatch"):
        polyglot.validate_polyglot_dataset(data_root)


def test_build_data_flushes_each_oracle_record_before_next_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = make_polyglot_tree(tmp_path)
    practice_root = source / "cpp" / "exercises" / "practice"
    shutil.copytree(practice_root / "two-fer", practice_root / "allergies")
    monkeypatch.setattr(
        polyglot,
        "run_polyglot_tests",
        lambda _path: polyglot.PolyglotTestResult(returncode=0, logs="oracle passed"),
    )
    original = polyglot.polyglot_oracle_setup_record
    calls = 0

    def interrupt_second_record(*args: object, **kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt
        return original(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(polyglot, "polyglot_oracle_setup_record", interrupt_second_record)
    out = tmp_path / "out"

    with pytest.raises(KeyboardInterrupt):
        polyglot.build_slime_polyglot_cpp_dataset(
            source, out, eval_limit=None, run_id="r1", force=True
        )

    records = [
        json.loads(line)
        for line in (out / "oracle.records.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(records) == 1
    assert records[0]["setup_valid"] is True
    assert not (out / "oracle.summary.json").exists()
    assert not (out / "manifest.json").exists()
    assert not (out / "eval" / "cpp.jsonl").exists()


def test_parse_replacements_accepts_path_code_pairs_and_rejects_bad_files() -> None:
    parsed = polyglot.parse_replacements(valid_response(), ["two_fer.cpp", "two_fer.h"])
    assert parsed["two_fer.cpp"].startswith("std::string two_fer")
    assert parsed["two_fer.h"].startswith("#pragma once")

    with pytest.raises(polyglot.PolyglotResponseError, match="unexpected prose"):
        polyglot.parse_replacements(
            "Here is the fix.\n" + valid_response(), ["two_fer.cpp", "two_fer.h"]
        )

    with pytest.raises(polyglot.PolyglotResponseError, match="unexpected prose"):
        polyglot.parse_replacements(valid_response() + "<|im_end|>", ["two_fer.cpp", "two_fer.h"])

    with pytest.raises(polyglot.PolyglotResponseError, match="unknown or forbidden"):
        polyglot.parse_replacements(
            valid_response().replace("two_fer.h", "two_fer_test.cpp"), ["two_fer.cpp", "two_fer.h"]
        )

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


def test_recover_replacements_diagnoses_unlabeled_code_blocks_without_changing_strict_parser() -> (
    None
):
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


def test_reward_func_applies_replacements_and_records_test_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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


def test_gemini_sanity_uses_exact_admitted_prompt_and_strict_grader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, paths = make_admitted_polyglot_data(tmp_path, monkeypatch)
    eval_row = json.loads(paths["eval"].read_text(encoding="utf-8"))
    captured: dict[str, object] = {}
    monkeypatch.setenv("GEMINI_API_KEY", "api-key-secret")

    def fake_generate(**kwargs: object) -> polyglot.GeminiGeneration:
        captured.update(kwargs)
        return polyglot.GeminiGeneration(
            text=valid_response(),
            api_key_source="GEMINI_API_KEY",
            finish_reason="STOP",
            usage_metadata={"total_token_count": 123},
        )

    output = tmp_path / "gemini"
    summary, artifact_paths = polyglot.run_polyglot_gemini_sanity(
        data_root=data_root,
        task_id="two-fer",
        output_dir=output,
        model="gemini-3.5-flash",
        generator=fake_generate,
    )

    assert captured["prompt"] == eval_row["prompt"]
    assert "// oracle cpp" not in str(captured["prompt"])
    assert captured["temperature"] == 0.0
    assert captured["top_p"] == 1.0
    assert summary["strict_pass"] is True
    assert summary["strict_reason"] == "passed"
    assert summary["oracle_setup_check"]["all_passed"] is True
    assert artifact_paths["prompt"].read_text(encoding="utf-8") == eval_row["prompt"]
    assert artifact_paths["response"].read_text(encoding="utf-8") == valid_response()
    record = json.loads(artifact_paths["record"].read_text(encoding="utf-8"))
    assert record["all_tests_pass"] is True
    assert record["sanity_model"] == "gemini-3.5-flash"
    request_text = artifact_paths["request"].read_text(encoding="utf-8")
    assert "GEMINI_API_KEY" in request_text
    assert "api-key-secret" not in request_text


def test_gemini_sanity_preserves_strict_format_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, _paths = make_admitted_polyglot_data(tmp_path, monkeypatch)

    def fake_generate(**_kwargs: object) -> polyglot.GeminiGeneration:
        return polyglot.GeminiGeneration(
            text="Here is the answer with prose.",
            api_key_source="GOOGLE_API_KEY",
        )

    summary, artifact_paths = polyglot.run_polyglot_gemini_sanity(
        data_root=data_root,
        task_id="cpp/two-fer",
        output_dir=tmp_path / "gemini-invalid",
        generator=fake_generate,
    )

    assert summary["strict_pass"] is False
    assert summary["strict_reason"] == "invalid_format"
    assert summary["recovered_pass"] is False
    record = json.loads(artifact_paths["record"].read_text(encoding="utf-8"))
    assert record["score"] == -1.0
    assert record["invalid_format"] is True


def test_gemini_sanity_api_failure_does_not_create_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, _paths = make_admitted_polyglot_data(tmp_path, monkeypatch)
    output = tmp_path / "gemini-api-failure"

    def failed_generate(**_kwargs: object) -> polyglot.GeminiGeneration:
        raise RuntimeError("simulated Gemini API failure")

    with pytest.raises(RuntimeError, match="simulated Gemini API failure"):
        polyglot.run_polyglot_gemini_sanity(
            data_root=data_root,
            task_id="cpp/two-fer",
            output_dir=output,
            generator=failed_generate,
        )

    assert not output.exists()


def test_gemini_sanity_checks_output_path_before_api_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, _paths = make_admitted_polyglot_data(tmp_path, monkeypatch)
    blocked_parent = tmp_path / "not-a-directory"
    blocked_parent.write_text("occupied", encoding="utf-8")
    generator_called = False

    def forbidden_generate(**_kwargs: object) -> polyglot.GeminiGeneration:
        nonlocal generator_called
        generator_called = True
        raise AssertionError("API generator must not run before output preflight")

    with pytest.raises((FileExistsError, NotADirectoryError)):
        polyglot.run_polyglot_gemini_sanity(
            data_root=data_root,
            task_id="cpp/two-fer",
            output_dir=blocked_parent / "result",
            generator=forbidden_generate,
        )

    assert generator_called is False


def test_gemini_sanity_plan_is_one_task_raw_response_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, _paths = make_admitted_polyglot_data(tmp_path, monkeypatch)

    plan = polyglot.build_gemini_sanity_plan(
        data_root=data_root,
        task_id="two-fer",
        model="gemini-3.5-flash",
        temperature=0.0,
        top_p=1.0,
        seed=42,
        max_output_tokens=8192,
    )

    assert plan["kind"] == "polyglot-gemini-sanity"
    assert plan["task_id"] == "cpp/two-fer"
    assert plan["generation_config"]["candidate_count"] == 1
    assert plan["response_policy"] == {
        "raw_response_only": True,
        "strict_scoring": True,
        "recovery_is_diagnostic_only": True,
    }
    assert len(plan["prompt_sha256"]) == 64
    assert "// oracle cpp" not in plan["prompt"]

    with pytest.raises(ValueError, match="mutable -latest alias"):
        polyglot.build_gemini_sanity_plan(
            data_root=data_root,
            task_id="two-fer",
            model="gemini-flash-latest",
            temperature=0.0,
            top_p=1.0,
            seed=42,
            max_output_tokens=8192,
        )


def test_gemini_api_key_precedence_and_missing_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("GOOGLE_API_KEY", "google-key")
    assert polyglot._gemini_api_key() == ("google-key", "GOOGLE_API_KEY")

    monkeypatch.delenv("GOOGLE_API_KEY")
    assert polyglot._gemini_api_key() == ("gemini-key", "GEMINI_API_KEY")

    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(ValueError, match="Missing Gemini API key"):
        polyglot._gemini_api_key()


def test_gemini_sanity_cli_dry_run_uses_no_key_or_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    data_root, _paths = make_admitted_polyglot_data(tmp_path, monkeypatch)
    output = tmp_path / "unused-dry-run-output"
    args = polyglot.build_arg_parser().parse_args(
        [
            "gemini-sanity",
            "--data-root",
            str(data_root),
            "--task-id",
            "two-fer",
            "--out",
            str(output),
            "--dry-run",
        ]
    )

    args.func(args)

    plan = json.loads(capsys.readouterr().out)
    assert plan["task_id"] == "cpp/two-fer"
    assert plan["model"] == "gemini-3.5-flash"
    assert plan["response_policy"]["raw_response_only"] is True
    assert not output.exists()


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

    _records, summary, paths = polyglot.score_debug_dump(
        label="base", debug_samples_path=debug_jsonl, output_dir=tmp_path / "eval"
    )

    assert paths["records"].exists()
    assert paths["summary"].exists()
    assert summary["pass_rate"] == 1.0
    assert summary["category_summary"]["strings"]["pass_rate"] == 1.0
    assert summary["category_summary"]["conditionals"]["task_count"] == 1
    assert summary["best_records"][0]["categories"] == ["strings", "conditionals"]
    assert summary["invalid_format_rate"] == 0.0
    assert "correct_and_faster_rate" not in summary
    assert "missing_runtime_rate" not in summary


def test_polyglot_report_categories_are_complete_mutually_exclusive_and_apt() -> None:
    grouped = [
        exercise
        for exercises in polyglot.POLYGLOT_REPORT_CATEGORY_EXERCISES.values()
        for exercise in exercises
    ]

    assert len(polyglot.POLYGLOT_REPORT_CATEGORY_EXERCISES) == 6
    assert len(grouped) == len(set(grouped))
    assert set(grouped) == set(polyglot.POLYGLOT_CPP_EXERCISE_CATEGORIES)
    assert all(
        3 <= len(exercises) <= 6
        for exercises in polyglot.POLYGLOT_REPORT_CATEGORY_EXERCISES.values()
    )


def test_build_polyglot_pass_at_k_report_writes_category_visuals(tmp_path: Path) -> None:
    p1_samples = {
        "two-fer": [True],
        "knapsack": [False],
        "clock": [False],
        "bank-account": [False],
        "yacht": [True],
        "allergies": [False],
    }
    p8_passes = {
        "two-fer": True,
        "knapsack": True,
        "clock": False,
        "bank-account": True,
        "yacht": True,
        "allergies": True,
    }
    p8_samples = {exercise: [False] * 7 + [passed] for exercise, passed in p8_passes.items()}
    p1 = make_polyglot_comparison_run(
        tmp_path / "p1",
        run_id="polyglot-p1",
        task_samples=p1_samples,
    )
    p8 = make_polyglot_comparison_run(
        tmp_path / "p8",
        run_id="polyglot-p8",
        task_samples=p8_samples,
    )

    payload, paths = polyglot.build_polyglot_pass_at_k_report(
        [p8, p1],
        tmp_path / "report",
    )

    assert payload["schema_version"] == 2
    assert [run["label"] for run in payload["runs"]] == ["pass@1", "pass@8"]
    assert payload["runs"][0]["passed_task_count"] == 2
    assert payload["runs"][1]["passed_task_count"] == 5
    assert payload["oracle_reference"]["display_label"] == "files.example oracle"
    assert payload["oracle_reference"]["role"] == "reference_setup"
    assert payload["oracle_reference"]["correct_answer_source"] == "files.example"
    assert payload["oracle_reference"]["passed_task_count"] == 6
    assert payload["oracle_reference"]["pass_rate"] == 1.0
    assert all(
        category["oracle_reference"]["pass_rate"] == 1.0 for category in payload["categories"]
    )
    assert all(task["oracle_reference"]["passed"] for task in payload["tasks"])
    assert len(payload["categories"]) == 6
    assert {category["category"] for category in payload["categories"]} == set(
        polyglot.POLYGLOT_REPORT_CATEGORY_EXERCISES
    )
    assert all(path.exists() for path in paths.values())
    for key in ("overall_chart", "category_chart", "outcome_chart", "gain_chart"):
        chart = paths[key]
        chart_text = chart.read_text(encoding="utf-8")
        assert "<svg" in chart_text
        assert "files.example oracle" in chart_text
        assert ET.parse(chart).getroot().tag.endswith("svg")
    report = paths["report"].read_text(encoding="utf-8")
    assert "Strict pass@k by category" in report
    assert "dot/range" in report
    assert "not an official Aider leaderboard result" in report
    assert "files.example oracle" in report
    assert "not a model generation" in report
    category_csv = paths["category_csv"].read_text(encoding="utf-8")
    assert "pass_at_1_pass_rate" in category_csv
    assert "pass_at_8_pass_rate" in category_csv

    assert "oracle_reference_pass_rate" in category_csv
    task_csv = paths["task_csv"].read_text(encoding="utf-8")
    assert "oracle_reference_passed" in task_csv
    assert ",True" in task_csv


def test_polyglot_pass_at_k_report_rejects_nonuniform_sample_counts(tmp_path: Path) -> None:
    uneven = make_polyglot_comparison_run(
        tmp_path / "uneven",
        run_id="uneven",
        task_samples={"two-fer": [False, True], "knapsack": [False]},
    )
    p8 = make_polyglot_comparison_run(
        tmp_path / "p8",
        run_id="p8",
        task_samples={"two-fer": [True] * 8, "knapsack": [False] * 8},
    )

    with pytest.raises(ValueError, match="non-uniform samples per task"):
        polyglot.build_polyglot_pass_at_k_report([uneven, p8], tmp_path / "report")


def test_polyglot_pass_at_k_report_rejects_config_mismatch(tmp_path: Path) -> None:
    p1 = make_polyglot_comparison_run(
        tmp_path / "p1",
        run_id="p1",
        task_samples={"two-fer": [True]},
    )
    p8 = make_polyglot_comparison_run(
        tmp_path / "p8",
        run_id="p8",
        task_samples={"two-fer": [False] * 7 + [True]},
        config_overrides={"eval_temperature": "1.0"},
    )

    with pytest.raises(ValueError, match="eval_temperature.*differs"):
        polyglot.build_polyglot_pass_at_k_report([p1, p8], tmp_path / "report")


def test_polyglot_pass_at_k_report_allows_explicit_descriptive_temperature_mismatch(
    tmp_path: Path,
) -> None:
    p1 = make_polyglot_comparison_run(
        tmp_path / "p1",
        run_id="greedy-run",
        task_samples={"two-fer": [True]},
        config_overrides={"eval_temperature": "0"},
    )
    p8 = make_polyglot_comparison_run(
        tmp_path / "p8",
        run_id="sampled-run",
        task_samples={"two-fer": [False] * 7 + [True]},
        config_overrides={"eval_temperature": "0.7"},
    )

    payload, paths = polyglot.build_polyglot_pass_at_k_report(
        [p1, p8],
        tmp_path / "report",
        allow_config_mismatches=["eval_temperature"],
    )

    assert payload["comparison_mode"] == "descriptive_mixed_sampling"
    assert payload["config_mismatches"] == {
        "eval_temperature": {"greedy-run": "0", "sampled-run": "0.7"}
    }
    assert "eval_temperature" not in payload["comparison_config"]
    assert [run["display_label"] for run in payload["runs"]] == [
        "greedy@1 (T=0)",
        "pass@8 (T=0.7)",
    ]
    assert payload["runs"][0]["evaluation_config"]["eval_temperature"] == "0"
    report = paths["report"].read_text(encoding="utf-8")
    assert "Descriptive comparison warning" in report
    assert "cannot be attributed to k alone" in report
    assert "greedy@1 (T=0)" in report
    assert "pass@8 (T=0.7)" in report
    category_chart = paths["category_chart"].read_text(encoding="utf-8")
    assert "Descriptive strict success by category" in category_chart
    assert "greedy@1 (T=0)" in category_chart

    assert "files.example oracle" in category_chart
    assert payload["oracle_reference"]["pass_rate"] == 1.0


def test_polyglot_pass_at_k_report_never_overrides_non_sampling_config(
    tmp_path: Path,
) -> None:
    p1 = make_polyglot_comparison_run(
        tmp_path / "p1", run_id="p1", task_samples={"two-fer": [True]}
    )
    p8 = make_polyglot_comparison_run(
        tmp_path / "p8", run_id="p8", task_samples={"two-fer": [True] * 8}
    )

    with pytest.raises(ValueError, match="Only sampling configuration mismatches"):
        polyglot.build_polyglot_pass_at_k_report(
            [p1, p8],
            tmp_path / "report",
            allow_config_mismatches=["hf_model_id"],
        )


def test_polyglot_pass_at_k_report_rejects_task_set_mismatch(tmp_path: Path) -> None:
    p1 = make_polyglot_comparison_run(
        tmp_path / "p1",
        run_id="p1",
        task_samples={"two-fer": [True]},
    )
    p8 = make_polyglot_comparison_run(
        tmp_path / "p8",
        run_id="p8",
        task_samples={"two-fer": [True] * 8, "knapsack": [False] * 8},
    )

    with pytest.raises(ValueError, match="task sets differ"):
        polyglot.build_polyglot_pass_at_k_report([p1, p8], tmp_path / "report")


def test_polyglot_pass_at_k_report_rejects_oracle_fingerprint_mismatch(
    tmp_path: Path,
) -> None:
    p1 = make_polyglot_comparison_run(
        tmp_path / "p1",
        run_id="p1",
        task_samples={"two-fer": [True]},
    )
    p8 = make_polyglot_comparison_run(
        tmp_path / "p8",
        run_id="p8",
        task_samples={"two-fer": [True] * 8},
    )
    oracle_path = p8 / "data" / "oracle.records.jsonl"
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    oracle["oracle_input_sha256"] = "sha256:different-grader"
    oracle_path.write_text(json.dumps(oracle) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="fingerprints differ"):
        polyglot.build_polyglot_pass_at_k_report([p1, p8], tmp_path / "report")


def test_polyglot_pass_at_k_report_rejects_failed_receipt(tmp_path: Path) -> None:
    p1 = make_polyglot_comparison_run(
        tmp_path / "p1",
        run_id="p1",
        task_samples={"two-fer": [True]},
    )
    p8 = make_polyglot_comparison_run(
        tmp_path / "p8",
        run_id="p8",
        task_samples={"two-fer": [True] * 8},
    )
    receipt_path = p1 / "stages" / "base-eval" / "run_receipt.txt"
    receipt_path.write_text(
        receipt_path.read_text(encoding="utf-8").replace("status=0", "status=1"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="receipt is not successful"):
        polyglot.build_polyglot_pass_at_k_report([p1, p8], tmp_path / "report")


def test_polyglot_compare_runs_cli_parses_two_historical_runs() -> None:
    args = polyglot.build_arg_parser().parse_args(
        [
            "compare-runs",
            "--run",
            "/runs/p1",
            "--run",
            "/runs/p8",
            "--out",
            "/reports/x",
            "--allow-config-mismatch",
            "eval_temperature",
        ]
    )

    assert args.run == ["/runs/p1", "/runs/p8"]
    assert args.out == "/reports/x"
    assert args.allow_config_mismatch == ["eval_temperature"]


def test_score_debug_dump_embeds_admitted_oracle_setup_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data_root, paths = make_admitted_polyglot_data(tmp_path, monkeypatch)
    oracle_check = json.loads(paths["manifest"].read_text(encoding="utf-8"))["oracle_setup_check"]
    debug_jsonl = tmp_path / "debug.jsonl"
    debug_jsonl.write_text(
        json.dumps(
            {
                "metadata": {"task_id": "cpp/two-fer", "problem_id": "two-fer"},
                "reward": {"score": 0.0, "reason": "tests_failed"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    _records, summary, _paths = polyglot.score_debug_dump(
        label="base",
        debug_samples_path=debug_jsonl,
        output_dir=tmp_path / "eval",
        data_root=data_root,
    )

    assert summary["pass_rate"] == 0.0
    assert summary["oracle_setup_check"] == oracle_check
    assert summary["oracle_setup_check"]["all_passed"] is True


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


def test_run_polyglot_tests_preserves_exercise_dir_basename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    exercise = tmp_path / "knapsack"
    exercise.mkdir()
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

    monkeypatch.setattr(polyglot.subprocess, "run", fake_run)

    result = polyglot.run_polyglot_tests(exercise)

    assert result.passed
    command = commands[0]
    assert command[command.index("-v") + 1] == f"{tmp_path.resolve()}:/work:rw"
    assert command[command.index("-w") + 1] == "/work/knapsack"
    assert command[command.index("--pids-limit") + 1] == "2048"


def test_polyglot_sandbox_image_plan_installs_cmake_and_make() -> None:
    plan = polyglot.polyglot_sandbox_image_build_plan()
    assert "docker build -t w8-biayn-polyglot-cpp:latest -" in plan
    assert "cmake libboost-date-time-dev make python3" in plan
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
    assert (
        'POLYGLOT_SOURCE="${SLIME_POLYGLOT_SOURCE:-${REPO_ROOT}/.w8-biayn/data/polyglot-benchmark}"'
        in text
    )
    assert 'EVAL_MAX_RESPONSE_LEN="${SLIME_EVAL_MAX_RESPONSE_LEN:-4096}"' in text
    assert "w8_biayn.integrations.slime_polyglot_cpp build-data" in text
    assert "w8_biayn.integrations.slime_polyglot_cpp verify-data" in text
    assert "oracle_records_path=${DATA_DIR}/oracle.records.jsonl" in text
    assert "oracle_summary_path=${DATA_DIR}/oracle.summary.json" in text
    assert '--data-root "${DATA_DIR}"' in text
    assert "--eval-prompt-data polyglot_cpp" in text
    assert "--rollout-skip-special-tokens" in text
    assert "--custom-rm-path w8_biayn.integrations.slime_polyglot_cpp.reward_func" in text
    assert "W8_SLIME_POLYGLOT_SANDBOX_IMAGE" in text
    assert "base.records.jsonl" in text
    assert "rollout_skip_special_tokens=1" in text
    assert "eval_n_samples_per_prompt=" in text
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
    assert "oracle.records.jsonl" in text
    assert "oracle.summary.json" in text
    assert "oracle_setup_check" in text
    assert "files.example" in text
    assert "recovered_pass_rate" in text
    assert "--rollout-skip-special-tokens" in text
    assert "setup ceiling" in text
    assert "rollout_skip_special_tokens=1" in text
    assert "gemini-sanity" in text
    assert "host-owned" in text
    assert "GEMINI_API_KEY" in text
    assert "raw response" in text
    assert "not a" in text and "pass@k" in text
    assert "compare-runs" in text
    assert "--allow-config-mismatch eval_temperature" in text
    assert "correct_and_faster_rate" in text
