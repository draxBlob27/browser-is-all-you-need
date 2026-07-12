from __future__ import annotations

import asyncio
import json
import os
import runpy
import sys
import tempfile
import types
from enum import IntEnum
from pathlib import Path

import pytest

from w8_biayn.modal_aider_polyglot_cpp import (
    AIDER_MODEL_NAME,
    ARTIFACT_DOWNLOAD_CONCURRENCY,
    BENCHMARK_LABEL,
    DEFAULT_MAX_TOKENS,
    INDEPENDENT_EVAL_MODE,
    INDEPENDENT_FULL_MAX_RUN_SECONDS,
    INDEPENDENT_RESULT_LABEL,
    INDEPENDENT_SMOKE_DIR,
    INDEPENDENT_SMOKE_TASKS,
    INDEPENDENT_TRIES,
    RUNNER_IDENTITY_FILENAME,
    MODEL_SETTINGS_PATH,
    SERVED_MODEL_NAME,
    SGLANG_ADMISSION_MAX_TOKENS,
    SGLANG_POST_RUN_SCALEDOWN_WINDOW_SECONDS,
    SGLANG_SCALEDOWN_WINDOW_SECONDS,
    TRANSFORMERS_COMMIT,
    ModalAiderConfig,
    ModalAiderError,
    admit_completed_independent_sample,
    aider_benchmark_command,
    archive_incomplete_independent_sample,
    archive_local_run_before_resume,
    build_independent_pass_report,
    build_artifact_manifest,
    ensure_secret_free,
    mark_local_teardown_verified,
    modal_app_is_stopped,
    model_settings,
    independent_sample_command,
    independent_config_fingerprint,
    parse_aider_stats,
    prepare_local_plan,
    render_plan,
    sample_seed,
    sglang_server_command,
    summarize_aider_exceptions,
    summarize_aider_result_diagnostics,
    summarize_sglang_admission,
    validate_aider_results,
    validate_authoritative_stats,
    validate_independent_aider_results,
    validate_independent_authoritative_stats,
    validate_local_artifacts,
    validate_model_snapshot,
    validate_remote_preflight,
    validate_runner_invocation,
    validate_sglang_admission,
    validate_sglang_help,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "examples/modal/glm47_flash_aider_polyglot_cpp"
PURE = ROOT / "src/w8_biayn/modal_aider_polyglot_cpp.py"
MODAL_APP = LANE / "modal_app.py"
RUN_SH = LANE / "run.sh"
RUNNER_DOCKERFILE = LANE / "Dockerfile.aider"
MODEL_SETTINGS_TEMPLATE = LANE / "glm47_flash.model.settings.yml"


def valid_env(**overrides: str) -> dict[str, str]:
    env = {
        "MODAL_TOKEN_ID": "ak-test-sentinel",
        "MODAL_TOKEN_SECRET": "as-test-sentinel",
        "MODAL_PROFILE": "test-profile",
        "W8_MODAL_AIDER_RUN_ID": "glm47-flash-aider-cpp-test",
        "W8_MODAL_AIDER_MODEL_REPO": "zai-org/GLM-4.7-Flash",
        "W8_MODAL_AIDER_MODEL_REVISION": "a" * 40,
        "W8_MODAL_AIDER_AIDER_COMMIT": "b" * 40,
        "W8_MODAL_AIDER_POLYGLOT_COMMIT": "c" * 40,
        "W8_MODAL_AIDER_SGLANG_IMAGE": "lmsysorg/sglang@sha256:" + "d" * 64,
        "W8_MODAL_AIDER_PHASE": "plan",
    }
    env.update(overrides)
    return env


def config(tmp_path: Path, **overrides: str) -> ModalAiderConfig:
    return ModalAiderConfig.from_env(valid_env(**overrides), repo_root=tmp_path)


def write_result(root: Path, task: str, *, exception: bool = False) -> None:
    task_root = root / "cpp/exercises/practice" / task
    task_root.mkdir(parents=True)
    payload = (
        {"exception": "boom"}
        if exception
        else {
            "testcase": task,
            "tests_outcomes": [False, True],
            "model": AIDER_MODEL_NAME,
            "edit_format": "whole",
            "num_exhausted_context_windows": 0,
        }
    )
    write_json(task_root / ".aider.results.json", payload)
    (task_root / ".aider.chat.history.md").write_text("model response\n", encoding="utf-8")


def write_independent_result(
    root: Path, task: str, *, outcomes: list[bool], exception: bool = False
) -> None:
    task_root = root / "cpp/exercises/practice" / task
    task_root.mkdir(parents=True)
    payload = (
        {"exception": "transport failed"}
        if exception
        else {
            "testcase": task,
            "tests_outcomes": outcomes,
            "model": AIDER_MODEL_NAME,
            "edit_format": "whole",
            "prompt_tokens": 10,
            "completion_tokens": 20,
        }
    )
    write_json(task_root / ".aider.results.json", payload)
    (task_root / ".aider.chat.history.md").write_text("one fresh trajectory\n", encoding="utf-8")


def authoritative_stats(tasks: int, *, tries: int = 2) -> dict[str, object]:
    stats: dict[str, object] = {
        "test_cases": tasks,
        "model": AIDER_MODEL_NAME,
        "edit_format": "whole",
        "pass_rate_1": 12.5,
    }
    if tries == 2:
        stats["pass_rate_2"] = 25.0
    return stats


def test_valid_plan_config_and_redacted_plan_are_deterministic(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    first = render_plan(cfg)
    second = render_plan(cfg)

    assert first == second
    assert first["benchmark"] == BENCHMARK_LABEL
    assert first["action"] == "no paid resources"
    assert first["transformers_commit"] == TRANSFORMERS_COMMIT
    assert first["config"]["transformers_commit"] == TRANSFORMERS_COMMIT
    assert first["config"]["sglang_scaledown_window_seconds"] == 1200
    assert cfg.identity_mapping()["transformers_commit"] == TRANSFORMERS_COMMIT
    assert cfg.identity_mapping()["sglang_scaledown_window_seconds"] == 1200
    assert SGLANG_SCALEDOWN_WINDOW_SECONDS == 20 * 60
    assert SGLANG_POST_RUN_SCALEDOWN_WINDOW_SECONDS == 2
    assert ARTIFACT_DOWNLOAD_CONCURRENCY == 16
    assert cfg.max_tokens == DEFAULT_MAX_TOKENS == 32_768
    assert "max_tokens: 32768" in model_settings(cfg)
    rendered = json.dumps(first, sort_keys=True)
    assert "ak-test-sentinel" not in rendered
    assert "as-test-sentinel" not in rendered
    assert rendered.count("<redacted>") >= 3
    assert cfg.app_name == "w8-aider-polyglot-cpp-glm47-flash-aider-cpp-test"


@pytest.mark.parametrize("missing", ["MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "MODAL_PROFILE"])
def test_missing_credentials_report_names_not_values(tmp_path: Path, missing: str) -> None:
    env = valid_env()
    env[missing] = ""
    with pytest.raises(ModalAiderError, match=missing) as caught:
        ModalAiderConfig.from_env(env, repo_root=tmp_path)
    assert "sentinel" not in str(caught.value)


@pytest.mark.parametrize("run_id", ["UPPER", "x", "bad/slash", "bad space", "x" * 39])
def test_invalid_run_ids_are_rejected(tmp_path: Path, run_id: str) -> None:
    with pytest.raises(ModalAiderError, match="RUN_ID"):
        config(tmp_path, W8_MODAL_AIDER_RUN_ID=run_id)


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("W8_MODAL_AIDER_MODEL_REVISION", "main", "40-character"),
        ("W8_MODAL_AIDER_AIDER_COMMIT", "abc1234", "40-character"),
        ("W8_MODAL_AIDER_POLYGLOT_COMMIT", "F" * 40, "40-character"),
        ("W8_MODAL_AIDER_MODEL_VOLUME", "bad/name", "safe Modal name"),
    ],
)
def test_mutable_or_unsafe_identities_are_rejected(
    tmp_path: Path, name: str, value: str, message: str
) -> None:
    with pytest.raises(ModalAiderError, match=message):
        config(tmp_path, **{name: value})


def test_full_requires_digest_ack_and_fixed_hardware(tmp_path: Path) -> None:
    with pytest.raises(ModalAiderError, match="ACKNOWLEDGE"):
        config(tmp_path, W8_MODAL_AIDER_PHASE="full")
    with pytest.raises(ModalAiderError, match="digest-pinned"):
        config(
            tmp_path,
            W8_MODAL_AIDER_PHASE="full",
            W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN="1",
            W8_MODAL_AIDER_SGLANG_IMAGE="lmsysorg/sglang:v1",
        )
    with pytest.raises(ModalAiderError, match="H100"):
        config(tmp_path, W8_MODAL_AIDER_GPU="H200:1")


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("W8_MODAL_AIDER_TRIES", "3"),
        ("W8_MODAL_AIDER_THREADS", "17"),
        ("W8_MODAL_AIDER_SMOKE_TESTS", "4"),
        ("W8_MODAL_AIDER_SGLANG_MEM_FRACTION", "1"),
        ("W8_MODAL_AIDER_MAX_RUN_SECONDS", "0"),
        ("W8_MODAL_AIDER_TEMPERATURE", "2.1"),
        ("W8_MODAL_AIDER_TOP_P", "0"),
    ],
)
def test_numeric_bounds_are_enforced(tmp_path: Path, name: str, value: str) -> None:
    with pytest.raises(ModalAiderError):
        config(tmp_path, **{name: value})


def test_independent_mode_requires_exact_paid_contract(tmp_path: Path) -> None:
    common = {
        "W8_MODAL_AIDER_EVAL_MODE": INDEPENDENT_EVAL_MODE,
        "W8_MODAL_AIDER_TRIES": "2",
        "W8_MODAL_AIDER_BASE_SEED": "700",
    }
    cfg = config(tmp_path, **common)
    assert cfg.samples_per_task == 8
    assert INDEPENDENT_TRIES == 2
    assert [sample_seed(cfg, index) for index in range(1, 9)] == list(range(701, 709))
    sampling_plan = render_plan(cfg)["independent_sampling"]
    assert sampling_plan["full_trajectory_count"] == 208
    assert sampling_plan["sampling_smoke_trajectory_count"] == 16
    assert sampling_plan["sampling_smoke_tasks"] == list(INDEPENDENT_SMOKE_TASKS)
    assert sampling_plan["sampling_smoke_artifact_dir"] == INDEPENDENT_SMOKE_DIR
    assert sampling_plan["required_full_max_run_seconds"] == INDEPENDENT_FULL_MAX_RUN_SECONDS
    assert sampling_plan["max_tries_per_trajectory"] == 2
    assert sampling_plan["maximum_full_edit_attempts"] == 416
    assert sampling_plan["seed_schedule"] == list(range(701, 709))
    with pytest.raises(ModalAiderError, match="exactly 8"):
        config(tmp_path, **common, W8_MODAL_AIDER_SAMPLES_PER_TASK="7")
    with pytest.raises(ModalAiderError, match="TRIES=2"):
        config(
            tmp_path,
            W8_MODAL_AIDER_EVAL_MODE=INDEPENDENT_EVAL_MODE,
            W8_MODAL_AIDER_TRIES="1",
        )
    with pytest.raises(ModalAiderError, match="positive sampling"):
        config(tmp_path, **common, W8_MODAL_AIDER_TEMPERATURE="0")
    with pytest.raises(ModalAiderError, match="exactly 2 fixed smoke tasks"):
        config(tmp_path, **common, W8_MODAL_AIDER_SMOKE_TESTS="1")
    with pytest.raises(ModalAiderError, match="MAX_RUN_SECONDS=14400"):
        config(
            tmp_path,
            **common,
            W8_MODAL_AIDER_PHASE="full",
            W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN="1",
            W8_MODAL_AIDER_ACKNOWLEDGE_PASS_AT_8="1",
        )
    with pytest.raises(ModalAiderError, match="ACKNOWLEDGE_PASS_AT_8"):
        config(
            tmp_path,
            **common,
            W8_MODAL_AIDER_PHASE="full",
            W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN="1",
            W8_MODAL_AIDER_MAX_RUN_SECONDS="14400",
        )


def test_independent_sample_settings_and_argv_transmit_seed(tmp_path: Path) -> None:
    cfg = config(
        tmp_path,
        W8_MODAL_AIDER_EVAL_MODE=INDEPENDENT_EVAL_MODE,
        W8_MODAL_AIDER_TRIES="2",
        W8_MODAL_AIDER_BASE_SEED="41",
    )
    settings = model_settings(cfg, sample_index=3)
    argv = independent_sample_command(
        cfg,
        sample_index=3,
        settings_path="/run/sample-03.yml",
        exercises_dir="/fresh/sample-03",
    )
    assert "seed: 44" in settings
    assert argv[argv.index("--tries") + 1] == "2"
    assert argv[argv.index("--read-model-settings") + 1] == "/run/sample-03.yml"
    assert argv[argv.index("--exercises-dir") + 1] == "/fresh/sample-03"
    assert "sample-03" in argv[1]
    smoke_argv = independent_sample_command(
        cfg,
        sample_index=3,
        smoke=True,
        settings_path="/run/sample-03.yml",
        exercises_dir="/fresh/sample-03",
    )
    assert smoke_argv[smoke_argv.index("--keywords") + 1] == ",".join(INDEPENDENT_SMOKE_TASKS)
    assert smoke_argv[smoke_argv.index("--num-tests") + 1] == "2"
    assert smoke_argv[smoke_argv.index("--tries") + 1] == "2"


def test_independent_matrix_computes_four_metrics_by_try_depth(tmp_path: Path) -> None:
    cfg = config(
        tmp_path,
        W8_MODAL_AIDER_EVAL_MODE=INDEPENDENT_EVAL_MODE,
        W8_MODAL_AIDER_TRIES="2",
        W8_MODAL_AIDER_BASE_SEED="100",
    )
    sample_dirs = {index: tmp_path / f"sample-{index:02d}" for index in range(1, 9)}
    # Try 1 covers c_i=0..8; cumulative try 2 covers min(8, c_i+1).
    # Column order is deliberately reversed.
    for sample_index, root in reversed(list(sample_dirs.items())):
        for try1_successes in range(9):
            try1_passed = sample_index <= try1_successes
            try2_passed = sample_index <= min(8, try1_successes + 1)
            write_independent_result(
                root,
                f"task-c{try1_successes}",
                outcomes=[True] if try1_passed else [False, try2_passed],
            )
    out = tmp_path / "report"
    report = build_independent_pass_report(
        cfg,
        sample_result_dirs=dict(reversed(list(sample_dirs.items()))),
        out=out,
        expected_tasks=9,
    )
    summary = report["summary"]
    assert summary["result_family"] == INDEPENDENT_RESULT_LABEL
    assert summary["pass@1_try1"] == pytest.approx(0.5)
    assert summary["pass@1_try2"] == pytest.approx(11 / 18)
    assert summary["pass@8_try1"] == pytest.approx(8 / 9)
    assert summary["pass@8_try2"] == pytest.approx(1.0)
    assert {key for key in summary if key.startswith("pass@")} == {
        "pass@1_try1",
        "pass@1_try2",
        "pass@8_try1",
        "pass@8_try2",
    }
    assert report["matrices"]["try1"][0]["successes"] == 0
    assert report["matrices"]["try2"][0]["successes"] == 1
    assert report["matrices"]["try1"][-1]["successes"] == 8
    assert report["matrices"]["try2"][-1]["successes"] == 8
    assert len((out / "samples.jsonl").read_text().splitlines()) == 72
    assert "pass@2" not in (out / "report.md").read_text()
    assert (out / "success-matrix.try1.json").is_file()
    assert (out / "success-matrix.try2.json").is_file()
    assert (out / "pass-at-1-and-8-by-try.json").is_file()


def test_independent_matrix_rejects_randomized_smoke_task_sets(tmp_path: Path) -> None:
    cfg = config(tmp_path, W8_MODAL_AIDER_EVAL_MODE=INDEPENDENT_EVAL_MODE)
    sample_dirs = {index: tmp_path / f"sample-{index:02d}" for index in range(1, 9)}
    for sample_index, root in sample_dirs.items():
        task_ids = INDEPENDENT_SMOKE_TASKS if sample_index < 8 else ("clock", "meetup")
        for task_id in task_ids:
            write_independent_result(root, task_id, outcomes=[False, False])
    with pytest.raises(ModalAiderError, match="mismatched task sets"):
        build_independent_pass_report(
            cfg,
            sample_result_dirs=sample_dirs,
            out=tmp_path / "report",
            expected_tasks=2,
        )


def test_independent_matrix_rejects_missing_and_exception_cells(tmp_path: Path) -> None:
    cfg = config(
        tmp_path,
        W8_MODAL_AIDER_EVAL_MODE=INDEPENDENT_EVAL_MODE,
        W8_MODAL_AIDER_TRIES="2",
    )
    sample_dirs = {index: tmp_path / f"sample-{index:02d}" for index in range(1, 9)}
    for index, root in sample_dirs.items():
        write_independent_result(root, "task", outcomes=[False, False], exception=index == 8)
    with pytest.raises(ModalAiderError, match="exception blocks"):
        build_independent_pass_report(
            cfg, sample_result_dirs=sample_dirs, out=tmp_path / "bad", expected_tasks=1
        )
    with pytest.raises(ModalAiderError, match="indices 1 through 8"):
        build_independent_pass_report(
            cfg,
            sample_result_dirs={key: value for key, value in sample_dirs.items() if key != 8},
            out=tmp_path / "missing",
            expected_tasks=1,
        )


def test_independent_two_try_admission_enforces_short_circuit_and_repair(tmp_path: Path) -> None:
    valid = tmp_path / "valid"
    write_independent_result(valid, "first-pass", outcomes=[True])
    write_independent_result(valid, "repaired", outcomes=[False, True])
    write_independent_result(valid, "failed", outcomes=[False, False])
    admission = validate_independent_aider_results(valid, expected_tasks=3)
    with pytest.raises(ModalAiderError, match="did not match"):
        validate_independent_aider_results(
            valid,
            expected_tasks=3,
            expected_task_ids=("first-pass", "repaired", "wrong-task"),
        )
    assert admission.test_invocations == 5

    missing_repair = tmp_path / "missing-repair"
    write_independent_result(missing_repair, "task", outcomes=[False])
    with pytest.raises(ModalAiderError, match="missing its second-try"):
        validate_independent_aider_results(missing_repair, expected_tasks=1)

    continued = tmp_path / "continued"
    write_independent_result(continued, "task", outcomes=[True, False])
    with pytest.raises(ModalAiderError, match="continued after a passing first try"):
        validate_independent_aider_results(continued, expected_tasks=1)


def test_independent_stats_allow_missing_try2_only_when_no_task_reached_it(
    tmp_path: Path,
) -> None:
    all_first_pass = tmp_path / "all-first-pass"
    write_independent_result(all_first_pass, "task", outcomes=[True])
    validate_independent_authoritative_stats(
        authoritative_stats(1, tries=1),
        result_dir=all_first_pass,
        expected_tasks=1,
    )

    reached_try2 = tmp_path / "reached-try2"
    write_independent_result(reached_try2, "task", outcomes=[False, True])
    with pytest.raises(ModalAiderError, match="missing pass_rate_2"):
        validate_independent_authoritative_stats(
            authoritative_stats(1, tries=1),
            result_dir=reached_try2,
            expected_tasks=1,
        )
    validate_independent_authoritative_stats(
        authoritative_stats(1, tries=2),
        result_dir=reached_try2,
        expected_tasks=1,
    )


def test_independent_local_artifacts_recompute_four_metrics_and_reject_tampering(
    tmp_path: Path,
) -> None:
    cfg = config(
        tmp_path,
        W8_MODAL_AIDER_EVAL_MODE=INDEPENDENT_EVAL_MODE,
        W8_MODAL_AIDER_TRIES="2",
        W8_MODAL_AIDER_PHASE="full",
        W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN="1",
        W8_MODAL_AIDER_ACKNOWLEDGE_PASS_AT_8="1",
        W8_MODAL_AIDER_EXPECTED_CPP_TASKS="1",
        W8_MODAL_AIDER_MAX_RUN_SECONDS="14400",
        W8_MODAL_AIDER_BASE_SEED="90",
    )
    root = cfg.local_run_path(tmp_path)
    protocol = root / INDEPENDENT_EVAL_MODE
    result_dirs: dict[int, Path] = {}
    for sample_index in range(1, 9):
        sample_root = protocol / f"sample-{sample_index:02d}"
        result_root = sample_root / f"run--{cfg.run_id}-sample-{sample_index:02d}"
        outcomes = [True] if sample_index == 1 else [False, sample_index == 2]
        write_independent_result(result_root, "task", outcomes=outcomes)
        result_dirs[sample_index] = result_root
        settings = model_settings(cfg, sample_index=sample_index)
        (sample_root / "model-settings.yml").write_text(settings, encoding="utf-8")
        (sample_root / "model-settings.sha256").write_text("settings-hash\n", encoding="utf-8")
        write_json(
            sample_root / "command.json",
            {
                "sample_index": sample_index,
                "seed": sample_seed(cfg, sample_index),
                "tries": 2,
            },
        )
        write_json(
            sample_root / "request-metadata.json",
            {"sample_index": sample_index, "seed": sample_seed(cfg, sample_index)},
        )
        write_json(
            sample_root / "fresh-tree.receipt.json",
            {"sample_index": sample_index, "copy_isolated_from_other_samples": True},
        )
        write_json(sample_root / "stats.json", authoritative_stats(1, tries=2))

    report = build_independent_pass_report(
        cfg,
        sample_result_dirs=result_dirs,
        out=protocol,
        expected_tasks=1,
    )
    for name in (
        "plan.json",
        "config.redacted.json",
        "upstreams.json",
        "model-cache.receipt.json",
        "server.receipt.json",
    ):
        write_json(root / name, {"status": "complete"})
    (root / "model-settings.yml").write_text("settings\n", encoding="utf-8")
    (root / "model-settings.sha256").write_text("settings-hash\n", encoding="utf-8")
    write_json(
        root / "run_receipt.json",
        {
            "status": "complete",
            "benchmark": BENCHMARK_LABEL,
            "eval_mode": INDEPENDENT_EVAL_MODE,
            "result_family": INDEPENDENT_RESULT_LABEL,
            "tries": 2,
            "expected_tasks": 1,
            "completed_tasks": 1,
            "completed_trajectories": 8,
            "maximum_edit_attempts": 16,
            "independent_pass_at_1_and_8": report["summary"],
            "modal_app_stopped": True,
            "teardown_status": "verified",
        },
    )
    write_json(root / "artifact_manifest.json", build_artifact_manifest(root))

    validated = validate_local_artifacts(cfg, repo_root=tmp_path)
    assert validated["stats"]["pass@1_try1"] == pytest.approx(1 / 8)
    assert validated["stats"]["pass@1_try2"] == pytest.approx(2 / 8)
    assert validated["stats"]["pass@8_try1"] == 1
    assert validated["stats"]["pass@8_try2"] == 1

    matrix_path = protocol / "success-matrix.try2.json"
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    matrix["rows"][0]["successes"] = 8
    write_json(matrix_path, matrix)
    write_json(root / "artifact_manifest.json", build_artifact_manifest(root))
    with pytest.raises(ModalAiderError, match="does not match official rows"):
        validate_local_artifacts(cfg, repo_root=tmp_path)


def test_local_artifact_path_cannot_escape_w8_state(tmp_path: Path) -> None:
    with pytest.raises(ModalAiderError, match="contained"):
        config(tmp_path, W8_MODAL_AIDER_LOCAL_ROOT="../escape")


def test_aider_commands_pin_official_harness_semantics(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    smoke = aider_benchmark_command(cfg, stage="smoke")
    full = aider_benchmark_command(cfg, stage="full")

    assert smoke[0] == "/aider/benchmark/benchmark.py"
    assert smoke[smoke.index("--languages") + 1] == "cpp"
    assert smoke[smoke.index("--tries") + 1] == "1"
    assert smoke[smoke.index("--threads") + 1] == "1"
    assert smoke[smoke.index("--num-tests") + 1] == "2"
    assert full[full.index("--tries") + 1] == "2"
    assert full[full.index("--threads") + 1] == "8"
    assert "--num-tests" not in full
    for argv in (smoke, full):
        assert argv[argv.index("--model") + 1] == AIDER_MODEL_NAME
        assert argv[argv.index("--edit-format") + 1] == "whole"
        assert argv[argv.index("--read-model-settings") + 1] == MODEL_SETTINGS_PATH


def test_model_settings_and_sglang_command_are_frozen(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    settings = model_settings(cfg)
    argv = sglang_server_command(cfg, api_key="secret-key")

    assert settings.count("name: openai/glm-4.7-flash") == 1
    assert "use_repo_map: false" in settings
    assert "streaming: false" in settings
    for flag, expected in (
        ("--tp-size", "4"),
        ("--tool-call-parser", "glm47"),
        ("--reasoning-parser", "glm45"),
        ("--speculative-algorithm", "EAGLE"),
        ("--served-model-name", SERVED_MODEL_NAME),
        ("--api-key", "secret-key"),
    ):
        assert argv[argv.index(flag) + 1] == expected
    validate_sglang_help(" ".join(part for part in argv if part.startswith("--")))


def test_model_manifest_rejects_missing_shards_and_accepts_complete_snapshot(
    tmp_path: Path,
) -> None:
    root = tmp_path / "model"
    root.mkdir()
    write_json(root / "config.json", {})
    write_json(root / "tokenizer_config.json", {})
    write_json(root / "model.safetensors.index.json", {"weight_map": {"a": "one.safetensors"}})
    with pytest.raises(ModalAiderError, match="missing indexed"):
        validate_model_snapshot(root, expected_revision="a" * 40, minimum_weight_bytes=1)
    (root / "one.safetensors").write_bytes(b"weights")
    manifest = validate_model_snapshot(root, expected_revision="a" * 40, minimum_weight_bytes=1)
    assert manifest["weight_shards"] == ["one.safetensors"]
    assert len(manifest["manifest_sha256"]) == 64


def test_aider_stats_parser_preserves_try_rates_without_pass_at_k_label() -> None:
    stats = parse_aider_stats(
        """\n- dirname: run-full\n test_cases: 26\n model: openai/glm-4.7-flash\n edit_format: whole\n pass_rate_1: 11.5\n pass_rate_2: 23.1\n num_malformed_responses: 2\n completion_tokens: 1234\n"""
    )
    validate_authoritative_stats(stats, expected_tasks=26)
    assert stats["pass_rate_1"] == 11.5
    assert stats["pass_rate_2"] == 23.1
    assert not any("pass@" in key for key in stats)


def test_sglang_admission_diagnostic_is_text_free_and_explains_truncation() -> None:
    completion = {
        "choices": [
            {
                "finish_reason": "length",
                "message": {
                    "content": None,
                    "reasoning_content": "private chain of thought sentinel",
                },
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 128, "total_tokens": 140},
    }
    summary = summarize_sglang_admission(completion, requested_max_tokens=128)

    assert summary["content_present"] is False
    assert summary["reasoning_content_field_present"] is True
    assert summary["reasoning_content_chars"] == len("private chain of thought sentinel")
    assert "private chain of thought sentinel" not in json.dumps(summary)
    with pytest.raises(ModalAiderError, match="finish_reason='length'.*completion_tokens=128"):
        validate_sglang_admission(summary)


def test_sglang_admission_accepts_separated_reasoning_and_editable_content() -> None:
    completion = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": "READY", "reasoning_content": "private sentinel"},
            }
        ],
        "usage": {"completion_tokens": 37},
    }
    summary = summarize_sglang_admission(
        completion,
        requested_max_tokens=SGLANG_ADMISSION_MAX_TOKENS,
    )

    validate_sglang_admission(summary)
    assert summary["content_chars"] == 5
    assert "READY" not in json.dumps(summary)
    assert "private sentinel" not in json.dumps(summary)


def test_smoke_admission_allows_wrong_code_but_rejects_exception_rows(tmp_path: Path) -> None:
    root = tmp_path / "smoke-result"
    write_result(root, "all-your-base")
    write_result(root, "bank-account")
    admitted = validate_aider_results(root, expected_tasks=2)
    assert admitted.completed_tasks == 2
    assert admitted.test_invocations == 4

    bad = tmp_path / "bad-result"
    write_result(bad, "all-your-base", exception=True)
    with pytest.raises(ModalAiderError, match="exception-only"):
        validate_aider_results(bad, expected_tasks=1)
    summary = summarize_aider_exceptions(bad)
    assert summary == [
        {
            "task": "all-your-base",
            "exception_type": "boom",
            "exception_final_line": "boom",
        }
    ]

    diagnostics = summarize_aider_result_diagnostics(root)
    assert diagnostics == [
        {
            "task": "all-your-base",
            "exception": False,
            "test_invocations": 2,
            "passing": True,
            "exhausted_context_windows": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        },
        {
            "task": "bank-account",
            "exception": False,
            "test_invocations": 2,
            "passing": True,
            "exhausted_context_windows": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
        },
    ]

    exhausted = tmp_path / "exhausted-result"
    write_result(exhausted, "xorcism")
    exhausted_path = exhausted / "cpp/exercises/practice/xorcism/.aider.results.json"
    payload = json.loads(exhausted_path.read_text(encoding="utf-8"))
    payload.update(
        {
            "tests_outcomes": [False],
            "num_exhausted_context_windows": 1,
            "prompt_tokens": 321,
            "completion_tokens": 8192,
        }
    )
    write_json(exhausted_path, payload)
    admitted_exhausted = validate_aider_results(exhausted, expected_tasks=1)
    assert admitted_exhausted.exhausted_context_windows == 1
    assert summarize_aider_result_diagnostics(exhausted) == [
        {
            "task": "xorcism",
            "exception": False,
            "test_invocations": 1,
            "passing": False,
            "exhausted_context_windows": 1,
            "prompt_tokens": 321,
            "completion_tokens": 8192,
        }
    ]

    exhausted_with_pass = tmp_path / "exhausted-with-pass"
    write_result(exhausted_with_pass, "binary-search-tree")
    write_result(exhausted_with_pass, "grade-school")
    for task, passed in (("binary-search-tree", False), ("grade-school", True)):
        path = exhausted_with_pass / f"cpp/exercises/practice/{task}/.aider.results.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.update(
            {
                "tests_outcomes": [passed],
                "num_exhausted_context_windows": 1,
            }
        )
        write_json(path, payload)
    admitted = validate_aider_results(exhausted_with_pass, expected_tasks=2)
    assert admitted.exhausted_context_windows == 2


def test_artifact_manifest_paths_are_relative_and_hashed(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "artifact_manifest.json").write_text("old manifest", encoding="utf-8")
    (tmp_path / "nested/file.txt").write_text("evidence", encoding="utf-8")
    manifest = build_artifact_manifest(tmp_path)
    assert manifest["files"][0]["path"] == "nested/file.txt"
    assert all(row["path"] != "artifact_manifest.json" for row in manifest["files"])
    assert len(manifest["files"][0]["sha256"]) == 64


def test_resume_rejects_identity_mismatch(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    prepare_local_plan(cfg, repo_root=tmp_path)
    with pytest.raises(ModalAiderError, match="mismatch"):
        prepare_local_plan(
            config(
                tmp_path,
                W8_MODAL_AIDER_MODEL_REVISION="e" * 40,
                W8_MODAL_AIDER_RESUME="1",
            ),
            repo_root=tmp_path,
        )


def test_plan_to_paid_pass_at_8_acknowledgements_are_not_identity(tmp_path: Path) -> None:
    planned = config(
        tmp_path,
        W8_MODAL_AIDER_EVAL_MODE=INDEPENDENT_EVAL_MODE,
        W8_MODAL_AIDER_MAX_RUN_SECONDS="14400",
    )
    prepare_local_plan(planned, repo_root=tmp_path)

    paid = config(
        tmp_path,
        W8_MODAL_AIDER_PHASE="full",
        W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN="1",
        W8_MODAL_AIDER_ACKNOWLEDGE_PASS_AT_8="1",
        W8_MODAL_AIDER_EVAL_MODE=INDEPENDENT_EVAL_MODE,
        W8_MODAL_AIDER_MAX_RUN_SECONDS="14400",
    )
    prepare_local_plan(paid, repo_root=tmp_path)

    stored = json.loads(
        (paid.local_run_path(tmp_path) / "config.redacted.json").read_text(encoding="utf-8")
    )
    assert stored["acknowledge_paid_run"] is True
    assert stored["acknowledge_pass_at_8"] is True
    assert "acknowledge_paid_run" not in paid.identity_mapping()
    assert "acknowledge_pass_at_8" not in paid.identity_mapping()


def test_remote_preflight_rejects_stale_runs_before_paid_startup(tmp_path: Path) -> None:
    cfg = config(tmp_path, W8_MODAL_AIDER_PHASE="smoke", W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN="1")
    run_root = tmp_path / "remote-run"

    validate_remote_preflight(cfg, run_root)
    run_root.mkdir()
    write_json(run_root / "server.failure.json", {"status": "failed"})
    with pytest.raises(ModalAiderError, match="fresh run id"):
        validate_remote_preflight(cfg, run_root)


def test_remote_preflight_allows_only_compatible_incomplete_resume(tmp_path: Path) -> None:
    run_root = tmp_path / "remote-run"
    run_root.mkdir()
    original = config(
        tmp_path,
        W8_MODAL_AIDER_PHASE="smoke",
        W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN="1",
    )
    write_json(run_root / "config.redacted.json", original.redacted_mapping())
    resumed = config(
        tmp_path,
        W8_MODAL_AIDER_PHASE="smoke",
        W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN="1",
        W8_MODAL_AIDER_ACKNOWLEDGE_PASS_AT_8="1",
        W8_MODAL_AIDER_RESUME="1",
    )
    validate_remote_preflight(resumed, run_root)

    write_json(run_root / "run_receipt.json", {"status": "complete"})
    with pytest.raises(ModalAiderError, match="completed full run"):
        validate_remote_preflight(resumed, run_root)


def test_runner_restart_requires_same_app_identity_or_explicit_resume(tmp_path: Path) -> None:
    run_root = tmp_path / "remote-run"
    run_root.mkdir()
    cfg = config(
        tmp_path,
        W8_MODAL_AIDER_PHASE="smoke",
        W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN="1",
    )
    identity = validate_runner_invocation(cfg, run_root, modal_app_id="ap-first")
    write_json(run_root / "config.redacted.json", cfg.redacted_mapping())
    write_json(run_root / RUNNER_IDENTITY_FILENAME, identity)

    restarted = validate_runner_invocation(cfg, run_root, modal_app_id="ap-first")
    assert restarted["modal_app_id"] == "ap-first"
    assert restarted["same_app_restart"] is True
    assert restarted["completed_run"] is False
    with pytest.raises(ModalAiderError, match="active Modal App/config"):
        validate_runner_invocation(cfg, run_root, modal_app_id="ap-other")

    resumed = config(
        tmp_path,
        W8_MODAL_AIDER_PHASE="smoke",
        W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN="1",
        W8_MODAL_AIDER_RESUME="1",
    )
    assert (
        validate_runner_invocation(resumed, run_root, modal_app_id="ap-resume")["modal_app_id"]
        == "ap-resume"
    )

    write_json(run_root / "run_receipt.json", {"status": "complete"})
    completed_restart = validate_runner_invocation(cfg, run_root, modal_app_id="ap-first")
    assert completed_restart["completed_run"] is True
    with pytest.raises(ModalAiderError, match="completed full run"):
        validate_runner_invocation(resumed, run_root, modal_app_id="ap-resume")


def test_independent_resume_reuses_complete_and_archives_only_incomplete(
    tmp_path: Path,
) -> None:
    cfg = config(tmp_path, W8_MODAL_AIDER_EVAL_MODE=INDEPENDENT_EVAL_MODE)

    def write_metadata(sample_root: Path, sample_index: int) -> None:
        sample_root.mkdir(parents=True)
        write_json(
            sample_root / "command.json",
            {
                "sample_index": sample_index,
                "seed": sample_seed(cfg, sample_index),
                "tries": INDEPENDENT_TRIES,
                "config_fingerprint": independent_config_fingerprint(cfg),
            },
        )
        write_json(
            sample_root / "request-metadata.json",
            {
                "sample_index": sample_index,
                "seed": sample_seed(cfg, sample_index),
            },
        )
        (sample_root / "model-settings.yml").write_text(
            model_settings(cfg, sample_index=sample_index),
            encoding="utf-8",
        )

    complete = tmp_path / "sample-01"
    write_metadata(complete, 1)
    result = complete / f"stamp--{cfg.run_id}-smoke-sample-01"
    for task in INDEPENDENT_SMOKE_TASKS:
        write_independent_result(result, task, outcomes=[False, True])
    write_json(complete / "stats.json", authoritative_stats(2, tries=2))
    admitted = admit_completed_independent_sample(
        cfg, complete, sample_index=1, smoke=True
    )
    assert admitted is not None
    assert Path(admitted["result_dir"]) == result
    with pytest.raises(ModalAiderError, match="completed"):
        archive_incomplete_independent_sample(
            cfg,
            complete,
            sample_index=1,
            smoke=True,
            archive_id="incident",
        )

    incomplete = tmp_path / "sample-02"
    write_metadata(incomplete, 2)
    (incomplete / "polyglot-benchmark").mkdir()
    (incomplete / "polyglot-benchmark/dirty.cpp").write_text(
        "partial edit\n", encoding="utf-8"
    )
    archived = archive_incomplete_independent_sample(
        cfg,
        incomplete,
        sample_index=2,
        smoke=False,
        archive_id="incident",
    )
    assert not incomplete.exists()
    assert (archived / "polyglot-benchmark/dirty.cpp").is_file()
    receipt = json.loads((archived / "resume.archive.json").read_text(encoding="utf-8"))
    assert receipt["sample_index"] == 2
    assert receipt["seed"] == sample_seed(cfg, 2)

    local_run = tmp_path / "runs" / cfg.run_id
    local_run.mkdir(parents=True)
    (local_run / "failure.txt").write_text("preserved\n", encoding="utf-8")
    local_archive = archive_local_run_before_resume(local_run, archive_id="incident")
    assert local_archive is not None
    assert (local_archive / "failure.txt").read_text(encoding="utf-8") == "preserved\n"
    assert not local_run.exists()


def test_runtime_mapping_keeps_only_hf_token_presence(tmp_path: Path) -> None:
    cfg = config(tmp_path, HF_TOKEN="hf-sentinel")
    runtime = cfg.runtime_mapping()
    assert runtime["hf_token_present"] is True
    assert "hf_token" not in runtime
    assert "hf-sentinel" not in json.dumps(runtime)


def test_secret_scanner_catches_every_secret_class() -> None:
    with pytest.raises(ModalAiderError, match="secret value"):
        ensure_secret_free("header Bearer sentinel-bearer", ["sentinel-bearer"])


def test_modal_app_stopped_parser_and_local_teardown_receipt(tmp_path: Path) -> None:
    cfg = config(tmp_path, W8_MODAL_AIDER_PHASE="smoke", W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN="1")
    root = cfg.local_run_path(tmp_path)
    root.mkdir(parents=True)
    write_json(root / "run_receipt.json", {"benchmark": BENCHMARK_LABEL})
    listing = tmp_path / "apps.json"
    write_json(listing, [{"Name": cfg.app_name, "State": "stopped"}])
    assert modal_app_is_stopped(json.loads(listing.read_text()), cfg.app_name)
    mark_local_teardown_verified(cfg, app_list_json=listing, repo_root=tmp_path)
    receipt = json.loads((root / "run_receipt.json").read_text())
    assert receipt["modal_app_stopped"] is True
    assert receipt["teardown_status"] == "verified"
    no_receipt = config(
        tmp_path,
        W8_MODAL_AIDER_RUN_ID="glm47-flash-aider-cpp-no-receipt",
        W8_MODAL_AIDER_PHASE="smoke",
        W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN="1",
    )
    write_json(listing, [{"Name": no_receipt.app_name, "State": "stopped"}])
    assert (
        mark_local_teardown_verified(no_receipt, app_list_json=listing, repo_root=tmp_path) is None
    )
    assert not modal_app_is_stopped([{"name": cfg.app_name, "state": "running"}], cfg.app_name)


def test_source_shape_keeps_modal_thin_and_paid_path_guarded() -> None:
    pure = PURE.read_text(encoding="utf-8")
    modal_app = MODAL_APP.read_text(encoding="utf-8")
    run = RUN_SH.read_text(encoding="utf-8")
    settings_template = MODEL_SETTINGS_TEMPLATE.read_text(encoding="utf-8")

    assert "import modal" not in pure
    assert "slime_polyglot_cpp" not in pure + modal_app
    assert "@app.server(" in modal_app
    assert "min_containers=0" in modal_app
    assert "max_containers=1" in modal_app
    assert "scaledown_window=SGLANG_SCALEDOWN_WINDOW_SECONDS" in modal_app
    assert "scaledown_window=60" not in modal_app
    assert "gpu=CONFIG.gpu" in modal_app
    assert 'volumes={"/models": model_volume}' in modal_app
    assert 'volumes={"/results": results_volume}' in modal_app
    assert "secrets=downloader_secrets" in modal_app
    assert "secrets=[runner_secret]" in modal_app
    assert (
        modal_app.index("preflight_remote_run.remote(RUNTIME)")
        < modal_app.index("preload_model.remote(RUNTIME)")
        < modal_app.index("SGLangServer.get_url()")
    )
    server_start = modal_app.split("class SGLangServer:", 1)[1].split("def _run_aider_stage", 1)[0]
    assert "assert_resume_compatible(config, prior_config, allow_plan=True)" in server_start
    assert "remote run id already has artifacts" not in server_start
    benchmark_body = modal_app.split("def run_aider_benchmark", 1)[1]
    assert "validate_runner_invocation(" in benchmark_body
    assert 'recover_existing = config.resume or runner_identity["same_app_restart"]' in benchmark_body
    assert 'write_json(root / "runner.identity.json", runner_identity)' in benchmark_body
    assert "archive_incomplete_independent_sample(" in modal_app
    assert "archive_local_run_before_resume(local_root)" in modal_app
    assert "SGLANG_ADMISSION_MAX_TOKENS" in modal_app
    assert 'write_json(root / "admission.failure.json", admission)' in modal_app
    assert (
        "completion"
        not in modal_app.split('write_json(root / "admission.failure.json"', 1)[1].split(
            "results_volume.commit()", 1
        )[0]
    )
    assert "HF_TOKEN" not in modal_app.split("def run_aider_benchmark", 1)[1]
    assert run.index("trap cleanup EXIT") < run.index("modal token info") < run.index("modal run")
    assert "W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN" in run
    assert "W8_MODAL_AIDER_ACKNOWLEDGE_PASS_AT_8" in run
    assert "modal app stop" in run and "modal app list --json" in run
    assert "from modal.volume import FileEntryType" in modal_app
    assert "if entry.type != FileEntryType.FILE:" in modal_app
    assert "asyncio.Semaphore(concurrency)" in modal_app
    assert "volume.iterdir.aio(" in modal_app
    assert "volume.read_file.aio(" in modal_app
    main_body = modal_app.split("def main() -> None:", 1)[1]
    assert main_body.index("run_aider_benchmark.remote(") < main_body.index(
        "_prepare_artifact_transfer()"
    )
    assert "downloaded_failure_artifacts" in main_body
    assert "result_diagnostics" in modal_app
    assert "max_tokens: 32768" in settings_template
    assert "max_tokens: 8192" not in settings_template
    assert 'kind = str(getattr(entry, "type", "")).lower()' not in modal_app
    assert os.access(RUN_SH, os.X_OK)
    for intermediate_k in range(2, 8):
        assert f'"pass@{intermediate_k}"' not in pure


def test_modal_images_add_mount_mode_local_source_after_build_steps() -> None:
    """Modal rejects an image build step after a mount-mode add_local_dir call."""

    modal_app = MODAL_APP.read_text(encoding="utf-8")
    image_section = modal_app.split("pure_source =", 1)[1].split("def _remote_config", 1)[0]
    for name, next_name in (
        ("downloader_image", "server_image"),
        ("server_image", "runner_image"),
        ("runner_image", None),
    ):
        block = image_section.split(f"{name} =", 1)[1]
        if next_name is not None:
            block = block.split(f"{next_name} =", 1)[0]
        assert block.count(".add_local_dir(") == 1
        assert block.rfind(".add_local_dir(") > block.rfind(".env(")
        if name == "server_image":
            assert "TRANSFORMERS_COMMIT" in block
            assert "glm4_moe_lite" in block
            assert (
                block.index(".pip_install(")
                < block.index(".run_commands(")
                < block.index(".env(")
                < block.index(".add_local_dir(")
            )


def test_aider_runner_uses_python_311_for_pinned_dev_dependencies() -> None:
    """Pinned Aider's NumPy constraints are unsatisfiable on Python 3.10."""

    dockerfile = RUNNER_DOCKERFILE.read_text(encoding="utf-8")
    assert dockerfile.startswith("FROM python:3.11-bookworm\n")
    assert "buildpack-deps:jammy" not in dockerfile
    assert "git clone https://github.com/Aider-AI/aider.git /aider" in dockerfile
    assert "test -x /aider/benchmark/cpp-test.sh" in dockerfile
    assert "WORKDIR /aider" in dockerfile
    assert "/opt/aider" not in dockerfile


def test_modal_app_imports_from_shallow_remote_path(tmp_path: Path, monkeypatch) -> None:
    """Modal imports mounted user code as /root/modal_app.py on every worker."""

    class _ModalObject:
        def __getattr__(self, _name):
            return self

        def __call__(self, *args, **kwargs):
            del kwargs
            if len(args) == 1 and callable(args[0]):
                return args[0]
            return self

    modal_object = _ModalObject()
    modal_stub = types.ModuleType("modal")
    modal_volume_stub = types.ModuleType("modal.volume")

    class _FileEntryType(IntEnum):
        UNSPECIFIED = 0
        FILE = 1
        DIRECTORY = 2
        SYMLINK = 3

    modal_volume_stub.FileEntryType = _FileEntryType

    def is_local() -> bool:
        return False

    modal_stub.is_local = is_local
    for name in ("App", "Image", "Secret", "Volume", "enter", "exit"):
        setattr(modal_stub, name, modal_object)

    cfg = config(tmp_path)
    monkeypatch.setenv("W8_MODAL_AIDER_RUNTIME_CONFIG", json.dumps(cfg.runtime_mapping()))
    monkeypatch.setitem(sys.modules, "modal", modal_stub)
    monkeypatch.setitem(sys.modules, "modal.volume", modal_volume_stub)
    monkeypatch.syspath_prepend(str(ROOT / "src"))

    with tempfile.NamedTemporaryFile(
        prefix="w8-modal-app-", suffix=".py", dir="/tmp", delete=False
    ) as handle:
        remote_path = Path(handle.name)
        handle.write(MODAL_APP.read_bytes())
    try:
        namespace = runpy.run_path(remote_path)
    finally:
        remote_path.unlink(missing_ok=True)

    assert namespace["IS_LOCAL"] is False
    assert namespace["ROOT"] == Path("/opt/w8-src")

    payloads = {f"runs/test/file-{index}.txt": f"payload-{index}".encode() for index in range(12)}
    active = 0
    max_active = 0

    async def iter_entries(prefix: str, *, recursive: bool):
        assert prefix == "runs/test"
        assert recursive is True
        yield types.SimpleNamespace(path="/runs/test/not-a-file", type=_FileEntryType.DIRECTORY)
        for path in payloads:
            yield types.SimpleNamespace(path=f"/{path}", type=_FileEntryType.FILE)

    async def read_file(path: str):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        try:
            await asyncio.sleep(0.01)
            yield payloads[path]
        finally:
            active -= 1

    fake_volume = types.SimpleNamespace(
        iterdir=types.SimpleNamespace(aio=iter_entries),
        read_file=types.SimpleNamespace(aio=read_file),
    )
    download_root = tmp_path / "parallel-download"
    downloaded = asyncio.run(
        namespace["_download_volume_files"](fake_volume, "runs/test", download_root, concurrency=4)
    )
    assert downloaded == len(payloads)
    assert max_active == 4
    assert not (download_root / "not-a-file").exists()
    for path, expected in payloads.items():
        relative = Path(path).relative_to("runs/test")
        assert (download_root / relative).read_bytes() == expected

    secret = "startup-bearer-sentinel"
    log_path = tmp_path / "sglang.log"
    log_path.write_text(f"old output\nkey={secret}\nfatal startup error\n", encoding="utf-8")
    log_tail = namespace["_redacted_log_tail"](log_path, secret)
    assert secret not in log_tail
    assert "<redacted>" in log_tail
    assert "fatal startup error" in log_tail

    class _ExitedProcess:
        @staticmethod
        def poll() -> int:
            return 17

    with pytest.raises(ModalAiderError, match="exited during startup with code 17"):
        namespace["_wait_for_process_json"](
            "http://127.0.0.1:1/health",
            secret,
            60,
            _ExitedProcess(),
        )

    assert cfg.startup_timeout_seconds == 3600
