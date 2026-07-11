from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from w8_biayn.modal_aider_polyglot_cpp import (
    AIDER_MODEL_NAME,
    BENCHMARK_LABEL,
    MODEL_SETTINGS_PATH,
    SERVED_MODEL_NAME,
    ModalAiderConfig,
    ModalAiderError,
    aider_benchmark_command,
    build_artifact_manifest,
    ensure_secret_free,
    mark_local_teardown_verified,
    modal_app_is_stopped,
    model_settings,
    parse_aider_stats,
    prepare_local_plan,
    render_plan,
    sglang_server_command,
    validate_aider_results,
    validate_authoritative_stats,
    validate_model_snapshot,
    validate_sglang_help,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "examples/modal/glm47_flash_aider_polyglot_cpp"
PURE = ROOT / "src/w8_biayn/modal_aider_polyglot_cpp.py"
MODAL_APP = LANE / "modal_app.py"
RUN_SH = LANE / "run.sh"
RUNNER_DOCKERFILE = LANE / "Dockerfile.aider"


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


def test_local_artifact_path_cannot_escape_w8_state(tmp_path: Path) -> None:
    with pytest.raises(ModalAiderError, match="contained"):
        config(tmp_path, W8_MODAL_AIDER_LOCAL_ROOT="../escape")


def test_aider_commands_pin_official_harness_semantics(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    smoke = aider_benchmark_command(cfg, stage="smoke")
    full = aider_benchmark_command(cfg, stage="full")

    assert smoke[0] == "/opt/aider/benchmark/benchmark.py"
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

    assert "import modal" not in pure
    assert "slime_polyglot_cpp" not in pure + modal_app
    assert "@app.server(" in modal_app
    assert "min_containers=0" in modal_app
    assert "max_containers=1" in modal_app
    assert "gpu=CONFIG.gpu" in modal_app
    assert 'volumes={"/models": model_volume}' in modal_app
    assert 'volumes={"/results": results_volume}' in modal_app
    assert "secrets=downloader_secrets" in modal_app
    assert "secrets=[runner_secret]" in modal_app
    assert "HF_TOKEN" not in modal_app.split("def run_aider_benchmark", 1)[1]
    assert run.index("trap cleanup EXIT") < run.index("modal token info") < run.index("modal run")
    assert "W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN" in run
    assert "modal app stop" in run and "modal app list --json" in run
    assert os.access(RUN_SH, os.X_OK)


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


def test_aider_runner_uses_python_311_for_pinned_dev_dependencies() -> None:
    """Pinned Aider's NumPy constraints are unsatisfiable on Python 3.10."""

    dockerfile = RUNNER_DOCKERFILE.read_text(encoding="utf-8")
    assert dockerfile.startswith("FROM python:3.11-bookworm\n")
    assert "buildpack-deps:jammy" not in dockerfile
