from __future__ import annotations

import asyncio
import json
import os
import subprocess
from pathlib import Path

import pytest

from w8_biayn.integrations import slime_multi_swe_cpp as multi_swe


EXAMPLE_ROOT = Path("examples/slime/moonlight_multi_swe_cpp")
RUNNER = EXAMPLE_ROOT / "moonlight_multi_swe_cpp.sh"
README = EXAMPLE_ROOT / "README.md"


def cpp_row(instance_id: str = "fmtlib__fmt__123") -> dict[str, object]:
    return {
        "org": "fmtlib",
        "repo": "fmt",
        "number": 123,
        "state": "closed",
        "title": "Fix formatter edge case",
        "body": "Calling fmt::format with a custom type crashes.",
        "base": {"sha": "abc123"},
        "resolved_issues": ["The formatter should not crash."],
        "fix_patch": "ORACLE_FIX_SHOULD_NOT_APPEAR",
        "test_patch": """diff --git a/test/core-test.cc b/test/core-test.cc
--- a/test/core-test.cc
+++ b/test/core-test.cc
@@ -1 +1 @@
-old
+new
""",
        "fixed_tests": {"hidden": "ORACLE_TEST_BUCKET_SHOULD_NOT_APPEAR"},
        "p2p_tests": {"stable": "still passes"},
        "f2p_tests": {},
        "s2p_tests": {},
        "n2p_tests": {},
        "run_result": {"oracle": "DO_NOT_PROMPT"},
        "test_patch_result": {"oracle": "DO_NOT_PROMPT"},
        "fix_patch_result": {"oracle": "DO_NOT_PROMPT"},
        "instance_id": instance_id,
    }


def make_dataset(tmp_path: Path) -> Path:
    source = tmp_path / "multi-swe-bench-mini"
    source.mkdir()
    rows = [
        cpp_row(),
        {**cpp_row("catchorg__Catch2__44"), "org": "catchorg", "repo": "Catch2", "number": 44},
        {**cpp_row("pydantic__pydantic__1"), "org": "pydantic", "repo": "pydantic", "number": 1},
    ]
    (source / "multi_swe_bench_mini.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    return source


def valid_diff_response() -> str:
    return """```diff
diff --git a/include/fmt/core.h b/include/fmt/core.h
--- a/include/fmt/core.h
+++ b/include/fmt/core.h
@@ -1 +1 @@
-old
+new
```
"""


def raw_recoverable_diff() -> str:
    return """diff --git a/include/fmt/core.h b/include/fmt/core.h
--- a/include/fmt/core.h
+++ b/include/fmt/core.h
@@ -1 +1 @@
-old
+new
"""


def test_build_slime_multi_swe_cpp_dataset_filters_cpp_rows_and_hides_oracles(
    tmp_path: Path,
) -> None:
    source = make_dataset(tmp_path)
    out = tmp_path / "out"

    paths = multi_swe.build_slime_multi_swe_cpp_dataset(
        source,
        out,
        eval_limit=None,
        run_id="r1",
        force=True,
    )

    rows = [json.loads(line) for line in paths["eval"].read_text(encoding="utf-8").splitlines()]
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert [row["task_id"] for row in rows] == ["catchorg__Catch2__44", "fmtlib__fmt__123"]
    assert manifest["kind"] == "slime-multi-swe-cpp-dataset"
    assert manifest["counts"] == {"eval": 2, "task_json": 2}
    assert "fmtlib/fmt" in manifest["allowed_repos"]

    row = rows[1]
    prompt = row["prompt"]
    assert "Fix formatter edge case" in prompt
    assert "The formatter should not crash." in prompt
    assert "ORACLE_FIX_SHOULD_NOT_APPEAR" not in prompt
    assert "ORACLE_TEST_BUCKET_SHOULD_NOT_APPEAR" not in prompt
    assert "test_patch" not in prompt
    assert row["metadata"]["task_path"] == "tasks/fmtlib__fmt__123/task.json"
    task = json.loads((out / row["metadata"]["task_path"]).read_text(encoding="utf-8"))
    assert task["fix_patch"] == "ORACLE_FIX_SHOULD_NOT_APPEAR"
    assert task["base_ref"] == "abc123"


def test_parse_patch_response_accepts_single_diff_block_and_rejects_prose() -> None:
    patch = multi_swe.parse_patch_response(valid_diff_response())

    assert patch.startswith("diff --git")
    assert multi_swe.extract_patch_paths(patch) == ("include/fmt/core.h",)

    with pytest.raises(multi_swe.MultiSweResponseError, match="unexpected prose"):
        multi_swe.parse_patch_response("Here is the fix.\n" + valid_diff_response())

    with pytest.raises(multi_swe.MultiSweResponseError, match="expected exactly one"):
        multi_swe.parse_patch_response(valid_diff_response() + "\n" + valid_diff_response())

    with pytest.raises(multi_swe.MultiSweResponseError, match="binary"):
        multi_swe.parse_patch_response("```diff\nGIT binary patch\nliteral 0\n```")


def test_recover_patch_response_accepts_raw_diff_without_changing_strict_parser() -> None:
    with pytest.raises(multi_swe.MultiSweResponseError, match="expected exactly one"):
        multi_swe.parse_patch_response(raw_recoverable_diff())

    recovered = multi_swe.recover_patch_response(raw_recoverable_diff())

    assert recovered.startswith("diff --git")


def test_patch_preflight_rejects_forbidden_paths_and_test_patch_paths() -> None:
    task = cpp_row()

    with pytest.raises(multi_swe.MultiSweResponseError, match="test-patch path"):
        multi_swe.preflight_patch_paths(
            """diff --git a/test/core-test.cc b/test/core-test.cc
--- a/test/core-test.cc
+++ b/test/core-test.cc
@@ -1 +1 @@
-old
+new
""",
            task,
        )

    with pytest.raises(multi_swe.MultiSweResponseError, match="forbidden file edit"):
        multi_swe.preflight_patch_paths(
            """diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -1 +1 @@
-old
+new
""",
            task,
        )

    assert multi_swe.preflight_patch_paths(multi_swe.parse_patch_response(valid_diff_response()), task)


def test_reward_func_scores_invalid_format_without_running_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_dataset(tmp_path)
    out = tmp_path / "out"
    paths = multi_swe.build_slime_multi_swe_cpp_dataset(source, out, eval_limit=1, force=True)
    row = json.loads(paths["eval"].read_text(encoding="utf-8").splitlines()[0])
    monkeypatch.setenv(multi_swe.DEFAULT_DATA_ROOT_ENV, str(out))

    def forbidden_runner(_task: dict[str, object], _patch: str) -> multi_swe.MultiSweTestResult:
        raise AssertionError("harness should not run")

    monkeypatch.setattr(multi_swe, "run_multi_swe_tests", forbidden_runner)
    sample = {"metadata": row["metadata"], "response": "plain prose"}

    record = asyncio.run(multi_swe.reward_func(None, sample))

    assert record["score"] == -1.0
    assert record["reason"] == "invalid_format"
    assert record["all_tests_pass"] is False
    assert record["recovered_format"] is False


def test_reward_func_runs_fake_harness_and_records_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_dataset(tmp_path)
    out = tmp_path / "out"
    paths = multi_swe.build_slime_multi_swe_cpp_dataset(source, out, eval_limit=1, force=True)
    row = json.loads(paths["eval"].read_text(encoding="utf-8").splitlines()[0])
    monkeypatch.setenv(multi_swe.DEFAULT_DATA_ROOT_ENV, str(out))
    calls: list[tuple[dict[str, object], str]] = []

    def fake_runner(task: dict[str, object], patch: str) -> multi_swe.MultiSweTestResult:
        calls.append((task, patch))
        assert task["fix_patch"] == "ORACLE_FIX_SHOULD_NOT_APPEAR"
        assert patch.startswith("diff --git")
        return multi_swe.MultiSweTestResult(returncode=0, logs="passed")

    monkeypatch.setattr(multi_swe, "run_multi_swe_tests", fake_runner)
    sample = {"metadata": row["metadata"], "response": valid_diff_response()}

    record = asyncio.run(multi_swe.reward_func(None, sample))

    assert calls
    assert record["score"] == 1.0
    assert record["reason"] == "passed"
    assert record["all_tests_pass"] is True
    assert record["repo_full_name"] == "catchorg/Catch2"
    assert record["tests_passed_count"] == 1
    assert "runtime_speedup" not in record


def test_reward_func_records_recovery_diagnostics_without_awarding_strict_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_dataset(tmp_path)
    out = tmp_path / "out"
    paths = multi_swe.build_slime_multi_swe_cpp_dataset(source, out, eval_limit=1, force=True)
    row = json.loads(paths["eval"].read_text(encoding="utf-8").splitlines()[0])
    monkeypatch.setenv(multi_swe.DEFAULT_DATA_ROOT_ENV, str(out))

    def fake_runner(_task: dict[str, object], _patch: str) -> multi_swe.MultiSweTestResult:
        return multi_swe.MultiSweTestResult(returncode=0, logs="passed")

    monkeypatch.setattr(multi_swe, "run_multi_swe_tests", fake_runner)
    sample = {"metadata": row["metadata"], "response": raw_recoverable_diff()}

    record = asyncio.run(multi_swe.reward_func(None, sample))

    assert record["score"] == -1.0
    assert record["reason"] == "invalid_format"
    assert record["all_tests_pass"] is False
    assert record["recovered_format"] is True
    assert record["recovered_reason"] == "passed"
    assert record["recovered_all_tests_pass"] is True


def test_score_debug_dump_writes_multi_swe_summary_without_speed_metrics(tmp_path: Path) -> None:
    debug_jsonl = tmp_path / "debug.jsonl"
    debug_jsonl.write_text(
        json.dumps(
            {
                "index": 0,
                "metadata": {
                    "task_id": "fmtlib__fmt__123",
                    "problem_id": "fmtlib__fmt__123",
                    "split": "eval",
                    "org": "fmtlib",
                    "repo": "fmt",
                    "repo_full_name": "fmtlib/fmt",
                },
                "response": valid_diff_response(),
                "reward": {
                    "score": 1.0,
                    "reward": 1.0,
                    "reason": "passed",
                    "task_id": "fmtlib__fmt__123",
                    "problem_id": "fmtlib__fmt__123",
                    "split": "eval",
                    "org": "fmtlib",
                    "repo": "fmt",
                    "repo_full_name": "fmtlib/fmt",
                    "all_tests_pass": True,
                    "compile_error": False,
                    "timeout": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    _records, summary, paths = multi_swe.score_debug_dump(
        label="base",
        debug_samples_path=debug_jsonl,
        output_dir=tmp_path / "eval",
    )

    assert paths["records"].exists()
    assert paths["summary"].exists()
    assert paths["oracle_records"].exists()
    assert summary["pass_rate"] == 1.0
    assert summary["repo_summary"]["fmtlib/fmt"]["pass_rate"] == 1.0
    assert summary["mean_reward"] == 1.0
    assert summary["oracle_setup_check"]["enabled"] is True
    assert summary["oracle_setup_check"]["correct_answer_source"] == "fix_patch"
    assert summary["oracle_setup_check"]["task_count"] == 0
    assert summary["oracle_setup_check"]["all_passed"] is False
    assert "correct_and_faster_rate" not in summary
    assert "missing_runtime_rate" not in summary
    assert "runtime_speedup" not in summary


def test_score_debug_dump_runs_oracle_setup_check_with_fix_patch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_dataset(tmp_path)
    out = tmp_path / "out"
    paths = multi_swe.build_slime_multi_swe_cpp_dataset(source, out, eval_limit=1, force=True)
    row = json.loads(paths["eval"].read_text(encoding="utf-8").splitlines()[0])
    metadata = {
        **row["metadata"],
        "task_id": row["task_id"],
        "problem_id": row["problem_id"],
        "split": row["split"],
    }
    debug_jsonl = tmp_path / "debug.jsonl"
    debug_jsonl.write_text(
        json.dumps(
            {
                "index": 0,
                "metadata": metadata,
                "response": valid_diff_response(),
                "reward": {
                    "score": 0.0,
                    "reward": 0.0,
                    "reason": "tests_failed",
                    "task_id": row["task_id"],
                    "problem_id": row["problem_id"],
                    "split": row["split"],
                    "org": row["metadata"]["org"],
                    "repo": row["metadata"]["repo"],
                    "repo_full_name": row["metadata"]["repo_full_name"],
                    "all_tests_pass": False,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    calls: list[tuple[dict[str, object], str]] = []

    def fake_runner(task: dict[str, object], patch: str) -> multi_swe.MultiSweTestResult:
        calls.append((task, patch))
        assert patch == task["fix_patch"]
        return multi_swe.MultiSweTestResult(returncode=0, logs="oracle passed")

    monkeypatch.setattr(multi_swe, "run_multi_swe_tests", fake_runner)

    _records, summary, aggregate_paths = multi_swe.score_debug_dump(
        label="base",
        debug_samples_path=debug_jsonl,
        output_dir=tmp_path / "eval",
        data_root=out,
    )

    assert calls
    assert aggregate_paths["oracle_records"].exists()
    assert summary["oracle_setup_check"] == {
        "enabled": True,
        "correct_answer_source": "fix_patch",
        "records_file": "base.oracle.records.jsonl",
        "task_count": 1,
        "passed_count": 1,
        "failed_count": 0,
        "pass_rate": 1.0,
        "all_passed": True,
        "reason_counts": {"passed": 1},
        "repo_summary": {
            row["metadata"]["repo_full_name"]: {
                "task_count": 1,
                "passed_count": 1,
                "failed_count": 0,
                "pass_rate": 1.0,
                "all_passed": True,
                "reason_counts": {"passed": 1},
            }
        },
    }
    oracle_rows = [
        json.loads(line)
        for line in aggregate_paths["oracle_records"].read_text(encoding="utf-8").splitlines()
    ]
    assert len(oracle_rows) == 1
    oracle = oracle_rows[0]
    assert oracle["correct_answer_source"] == "fix_patch"
    assert oracle["setup_valid"] is True
    assert oracle["reason"] == "passed"
    assert oracle["fix_patch_bytes"] > 0
    assert oracle["log_excerpt"] == "oracle passed"


def test_multi_swe_sandbox_image_plan_installs_cmake_git_and_make() -> None:
    plan = multi_swe.multi_swe_sandbox_image_build_plan()
    assert "docker build -t w8-biayn-multi-swe-cpp:latest -" in plan
    assert "cmake git make" in plan
    assert plan.rstrip().endswith("DOCKERFILE")


def test_moonlight_multi_swe_cpp_example_files_are_present_and_executable() -> None:
    expected = {"README.md", "moonlight_multi_swe_cpp.sh", "prepare_data.sh", "eval_base.sh"}

    assert expected.issubset({path.name for path in EXAMPLE_ROOT.iterdir()})
    for script in expected - {"README.md"}:
        assert os.access(EXAMPLE_ROOT / script, os.X_OK), script


def test_moonlight_multi_swe_cpp_scripts_are_bash_syntax_valid() -> None:
    for script in sorted(EXAMPLE_ROOT.glob("*.sh")):
        subprocess.run(["bash", "-n", str(script)], check=True)


def test_moonlight_multi_swe_cpp_runner_is_base_eval_only() -> None:
    text = RUNNER.read_text(encoding="utf-8")

    assert "prepare-data|base-eval" in text
    assert "sft.sh" not in text.lower()
    assert "grpo.sh" not in text.lower()
    assert 'RUN_ID="${SLIME_RUN_ID:-moonlight_multi_swe_cpp}"' in text
    assert ".w8-biayn/data/multi-swe-bench-mini" in text
    assert 'EVAL_MAX_RESPONSE_LEN="${SLIME_EVAL_MAX_RESPONSE_LEN:-16384}"' in text
    assert "w8_biayn.integrations.slime_multi_swe_cpp build-data" in text
    assert "--eval-prompt-data multi_swe_cpp" in text
    assert "--custom-rm-path w8_biayn.integrations.slime_multi_swe_cpp.reward_func" in text
    assert "W8_SLIME_MULTI_SWE_SANDBOX_IMAGE" in text
    assert "W8_SLIME_MULTI_SWE_ORACLE_SETUP_CHECK" in text
    assert '--data-root "${DATA_DIR}"' in text
    assert "SLIME_MULTI_SWE_SKIP_ORACLE_CHECK" in text
    assert "base.records.jsonl" in text
    assert "base.oracle.records.jsonl" in text
    assert "multi_swe_oracle_setup_check" in text
    assert "correct_and_faster_rate" not in text


def test_moonlight_multi_swe_cpp_readme_documents_operator_flow() -> None:
    text = README.read_text(encoding="utf-8")

    assert "ByteDance-Seed/Multi-SWE-bench_mini" in text
    assert "not an official Multi-SWE" in text
    assert "leaderboard run" in text
    assert "sandbox-image --dry-run" in text
    assert "bash examples/slime/moonlight_multi_swe_cpp/prepare_data.sh" in text
    assert "bash examples/slime/moonlight_multi_swe_cpp/eval_base.sh" in text
    assert "base.records.jsonl" in text
    assert "base.oracle.records.jsonl" in text
    assert "base.summary.json" in text
    assert "oracle_setup_check" in text
    assert "fix_patch" in text
    assert "recovered_*" in text
    assert "correct_and_faster_rate" in text


def test_repo_docs_reference_multi_swe_lane() -> None:
    expected = [
        "examples/slime/moonlight_multi_swe_cpp/",
        "src/w8_biayn/integrations/slime_multi_swe_cpp.py",
    ]
    docs = [
        Path("README.md"),
        Path("ROADMAP.md"),
        Path(".agents/REPO_GUIDE.md"),
        Path(".agents/skills/w8-biayn-framework/SKILL.md"),
        Path("docs/MOONLIGHT_MULTI_SWE_CPP_BASE_EVAL_IMPLEMENTATION_PLAN.md"),
    ]

    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        assert "Multi-SWE" in text, doc
    for needle in expected:
        assert needle in Path("README.md").read_text(encoding="utf-8")
        assert needle in Path(".agents/REPO_GUIDE.md").read_text(encoding="utf-8")
