from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess

import pytest

import w8_biayn.modal_multi_swe_cpp as modal_contract
import w8_biayn.modal_multi_swe_runtime as modal_runtime
from w8_biayn.modal_glm47 import (
    DEFAULT_MAX_TOKENS,
    SGLANG_SCALEDOWN_WINDOW_SECONDS,
    sglang_server_command,
)
from w8_biayn.modal_multi_swe_cpp import (
    BENCHMARK_LABEL,
    DATASET_REVISION,
    DEFAULT_LOCK_PATH,
    EXPECTED_CPP_TASKS,
    MODEL_REPO,
    RESULT_FAMILY,
    SMOKE_TASK_IDS,
    ModalMultiSweConfig,
    ModalMultiSweError,
    aggregate_records,
    build_artifact_manifest,
    classify_response,
    generate_image_lock,
    grader_cache_key,
    model_request,
    model_request_sha256,
    prepare_local_plan,
    render_plan,
    response_sha256,
    validate_image_lock,
)


ROOT = Path(__file__).resolve().parents[1]
LANE = ROOT / "examples/modal/glm47_flash_multi_swe_cpp"
LOCK = ROOT / DEFAULT_LOCK_PATH
RUN_SH = LANE / "run.sh"
MODAL_APP = LANE / "modal_app.py"
PURE = ROOT / "src/w8_biayn/modal_multi_swe_cpp.py"


def valid_env(**overrides: str) -> dict[str, str]:
    env = {
        "MODAL_TOKEN_ID": "modal-id-sentinel",
        "MODAL_TOKEN_SECRET": "modal-secret-sentinel",
        "MODAL_PROFILE": "test-profile",
        "HF_TOKEN": "hf-secret-sentinel",
        "W8_MODAL_MULTI_SWE_RUN_ID": "glm47-mswe-cpp-test",
        "W8_MODAL_MULTI_SWE_MODEL_REPO": MODEL_REPO,
        "W8_MODAL_MULTI_SWE_MODEL_REVISION": "a" * 40,
        "W8_MODAL_MULTI_SWE_DATASET_REVISION": DATASET_REVISION,
        "W8_MODAL_MULTI_SWE_SGLANG_IMAGE": "lmsysorg/sglang@sha256:" + "b" * 64,
        "W8_MODAL_MULTI_SWE_PHASE": "plan",
    }
    env.update(overrides)
    return env


def config(tmp_path: Path, **overrides: str) -> ModalMultiSweConfig:
    return ModalMultiSweConfig.from_env(valid_env(**overrides), repo_root=tmp_path)


def task() -> dict[str, object]:
    return {
        "instance_id": "fmtlib__fmt-1171",
        "org": "fmtlib",
        "repo": "fmt",
        "repo_full_name": "fmtlib/fmt",
        "base_ref": "a" * 40,
        "test_patch": "",
        "fix_patch": valid_patch(),
        "sandbox_image": "mswebench/fmtlib_m_fmt:pr-1171",
        "sandbox_image_digest": (
            "mswebench/fmtlib_m_fmt@sha256:"
            "0fa6db578f073c6b2278da620ca90e8e87f914f94f9d7652510646a7567db791"
        ),
    }


def valid_patch() -> str:
    return """diff --git a/include/fmt/core.h b/include/fmt/core.h
--- a/include/fmt/core.h
+++ b/include/fmt/core.h
@@ -1 +1 @@
-old
+new
"""


def response(content: str) -> dict[str, object]:
    return {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"content": content, "reasoning_content": "private reasoning"},
            }
        ],
        "usage": {"completion_tokens": 12},
    }


def test_checked_in_lock_is_exact_and_immutable() -> None:
    lock = validate_image_lock(LOCK)

    assert lock["dataset_revision"] == DATASET_REVISION
    assert lock["expected_tasks"] == EXPECTED_CPP_TASKS == 50
    assert len(lock["tasks"]) == 50
    assert set(SMOKE_TASK_IDS) <= set(lock["tasks"])
    assert all("@sha256:" in row["digest"] for row in lock["tasks"].values())
    assert all(row["tag"] == row["tag"].lower() for row in lock["tasks"].values())
    assert len(lock["sha256"]) == 64


def test_config_plan_is_deterministic_redacted_and_no_spend(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    plan = render_plan(cfg, validate_image_lock(LOCK))

    assert plan == render_plan(cfg, validate_image_lock(LOCK))
    assert plan["benchmark"] == BENCHMARK_LABEL
    assert plan["result_family"] == RESULT_FAMILY
    assert plan["action"] == "no paid resources"
    assert plan["grader"]["block_network"] is True
    assert plan["grader"]["secrets"] == []
    assert plan["blocking_oracle"] is False
    rendered = json.dumps(plan)
    for secret in ("modal-id-sentinel", "modal-secret-sentinel", "hf-secret-sentinel"):
        assert secret not in rendered
    assert cfg.max_tokens == DEFAULT_MAX_TOKENS
    assert SGLANG_SCALEDOWN_WINDOW_SECONDS == 1200


@pytest.mark.parametrize(
    ("name", "value", "message"),
    [
        ("W8_MODAL_MULTI_SWE_MODEL_REVISION", "main", "40-character"),
        ("W8_MODAL_MULTI_SWE_DATASET_REVISION", "c" * 40, "checked-in lock"),
        ("W8_MODAL_MULTI_SWE_SGLANG_IMAGE", "lmsysorg/sglang:latest", "digest-pinned"),
        ("W8_MODAL_MULTI_SWE_GPU", "H200:4", "H100"),
        ("W8_MODAL_MULTI_SWE_SAMPLES_PER_TASK", "2", "one sample"),
        ("W8_MODAL_MULTI_SWE_TEMPERATURE", "0.7", "temperature=0"),
        ("W8_MODAL_MULTI_SWE_GRADER_CONCURRENCY", "5", "grader concurrency"),
        ("W8_MODAL_MULTI_SWE_SANDBOX_MEMORY_MIB", "4096", "2048"),
    ],
)
def test_config_rejects_mutable_or_noncanonical_values(
    tmp_path: Path, name: str, value: str, message: str
) -> None:
    with pytest.raises(ModalMultiSweError, match=message):
        config(tmp_path, **{name: value})


def test_paid_phase_requires_acknowledgement_and_lock(tmp_path: Path) -> None:
    with pytest.raises(ModalMultiSweError, match="ACKNOWLEDGE"):
        config(tmp_path, W8_MODAL_MULTI_SWE_PHASE="smoke")
    with pytest.raises(ModalMultiSweError, match="image lock"):
        config(
            tmp_path,
            W8_MODAL_MULTI_SWE_PHASE="smoke",
            W8_MODAL_MULTI_SWE_ACKNOWLEDGE_PAID_RUN="1",
        )


def test_plan_to_paid_acknowledgement_is_not_identity(tmp_path: Path) -> None:
    cfg = config(tmp_path)
    identity = cfg.identity_mapping()
    assert "acknowledge_paid_run" not in identity
    assert "phase" not in identity
    prepare_local_plan(cfg, repo_root=tmp_path)


def test_request_is_secret_free_and_uses_one_prompt() -> None:
    cfg = ModalMultiSweConfig.from_env(valid_env(), repo_root=ROOT)
    payload = model_request(cfg, "public issue prompt")

    assert payload == {
        "model": "glm-4.7-flash",
        "messages": [{"role": "user", "content": "public issue prompt"}],
        "max_tokens": 32768,
        "temperature": 0.0,
        "top_p": 1.0,
        "stream": False,
    }
    assert "Authorization" not in json.dumps(payload)


def test_shared_server_command_keeps_glm_and_auth_contract(tmp_path: Path) -> None:
    argv = sglang_server_command(config(tmp_path), api_key="bearer-sentinel")

    for flag, expected in (
        ("--tp-size", "4"),
        ("--tool-call-parser", "glm47"),
        ("--reasoning-parser", "glm45"),
        ("--speculative-algorithm", "EAGLE"),
        ("--api-key", "bearer-sentinel"),
    ):
        assert argv[argv.index(flag) + 1] == expected


def test_classifier_uses_only_editable_content_and_strict_metrics() -> None:
    fence = chr(96) * 3
    raw = response(fence + "diff\n" + valid_patch() + fence)
    execution = {
        "returncode": 0,
        "logs": "100% tests passed, 0 tests failed out of 12\n",
        "timed_out": False,
        "image": task()["sandbox_image_digest"],
        "sandbox_id": "sb-1",
    }
    record = classify_response(task=task(), response=raw, execution=execution)

    assert record["all_tests_pass"] is True
    assert record["tests_collected"] == 12
    assert record["score"] == 1.0
    assert "private reasoning" not in json.dumps(record["response_metadata"])

    invalid = classify_response(
        task=task(),
        response=response("reasoning text\n" + fence + "diff\n" + valid_patch() + fence),
        execution=None,
    )
    assert invalid["reason"] == "invalid_format"
    assert invalid["score"] == -1.0


def test_aggregation_has_oracle_provenance_and_no_pie_speed_metrics() -> None:
    row = {
        "task_id": "fmtlib__fmt-1171",
        "repo_full_name": "fmtlib/fmt",
        "reward": 1.0,
        "score": 1.0,
        "reason": "passed",
        "all_tests_pass": True,
    }
    oracle = {"complete": True, "all_passed": True, "passed_count": 50}
    summary = aggregate_records([row], oracle_summary=oracle, provenance={"backend": "modal"})

    assert summary["pass_rate"] == 1.0
    assert summary["oracle_setup_check"] == oracle
    assert summary["provenance"]["backend"] == "modal"
    assert "correct_and_faster_rate" not in summary
    assert "runtime_speedup" not in summary


def test_artifact_manifest_hashes_safe_relative_paths(tmp_path: Path) -> None:
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "evidence.json").write_text("{}", encoding="utf-8")
    manifest = build_artifact_manifest(tmp_path)

    assert manifest["file_count"] == 1
    assert manifest["files"][0]["path"] == "nested/evidence.json"
    assert len(manifest["files"][0]["sha256"]) == 64


def test_source_shape_enforces_sandbox_and_lifecycle_contract() -> None:
    app = MODAL_APP.read_text(encoding="utf-8")
    run = RUN_SH.read_text(encoding="utf-8")
    pure = PURE.read_text(encoding="utf-8")

    assert "import modal" not in pure
    assert "modal.Sandbox.create(" in app
    assert 'modal.Image.from_registry(task["sandbox_image_digest"])' in app
    assert "block_network=True" in app
    assert "cpu=(CONFIG.sandbox_cpu, CONFIG.sandbox_cpu)" in app
    assert "memory=(CONFIG.sandbox_memory_mib, CONFIG.sandbox_memory_mib)" in app
    assert "secrets=[]" in app
    assert 'sandbox.filesystem.write_text(patch, "/home/fix.patch")' in app
    assert "sandbox.terminate(wait=True)" in app
    assert "sandbox.detach()" in app
    assert "server.failure.json" in app
    assert "admission.failure.json" in app
    assert "resume_state=resume_state" in app
    assert "generate-lock" in pure
    assert "docker" not in run
    assert "min_containers=0" in app and "max_containers=1" in app
    assert "check-app-stopped" in run
    assert app.index("prepare_and_admit(") < app.index("preload_model.remote(")
    assert run.index("trap cleanup EXIT") < run.index("modal token info") < run.index("modal run")
    assert "modal deploy" not in run
    assert os.access(RUN_SH, os.X_OK)
    subprocess.run(["bash", "-n", str(RUN_SH)], check=True)


def test_runbook_and_repo_docs_name_pending_paid_validation() -> None:
    lane = (LANE / "README.md").read_text(encoding="utf-8")
    assert "paid Modal validation remains" in lane
    assert "not a leaderboard" in lane
    assert "modal_app_stopped: true" in lane
    assert "generate-lock" in lane and "never an implicit benchmark step" in lane
    for path in (ROOT / "README.md", ROOT / "ROADMAP.md", ROOT / ".agents/REPO_GUIDE.md"):
        assert "glm47_flash_multi_swe_cpp" in path.read_text(encoding="utf-8")


def test_lock_generator_is_sorted_and_uses_explicit_resolver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = [{"instance_id": f"fmtlib__fmt-{index:02d}"} for index in reversed(range(50))]
    monkeypatch.setattr(modal_contract, "load_multi_swe_rows", lambda _path: rows)
    monkeypatch.setattr(modal_contract, "repo_harness_for_row", lambda _row: object())
    monkeypatch.setattr(
        modal_contract,
        "normalized_task",
        lambda row, **_kwargs: {
            "sandbox_image": "mswebench/fmtlib_m_fmt:pr-" + row["instance_id"].rsplit("-", 1)[1]
        },
    )
    resolved: list[str] = []

    def resolver(tag: str) -> str:
        resolved.append(tag)
        return tag.rsplit(":", 1)[0] + "@sha256:" + "a" * 64

    lock = generate_image_lock("fixture.jsonl", resolver=resolver)

    assert list(lock["tasks"]) == sorted(row["instance_id"] for row in rows)
    assert len(resolved) == EXPECTED_CPP_TASKS
    assert lock["platform"] == "linux/amd64"


def test_config_identity_hashes_lane_sources() -> None:
    cfg = ModalMultiSweConfig.from_env(valid_env(), repo_root=ROOT)

    assert set(cfg.source_file_hashes) >= {
        "src/w8_biayn/modal_multi_swe_cpp.py",
        "src/w8_biayn/modal_multi_swe_runtime.py",
        "examples/modal/glm47_flash_multi_swe_cpp/modal_app.py",
    }
    assert cfg.identity_mapping()["source_file_hashes"] == cfg.source_file_hashes


def test_missing_editable_content_is_strict_model_outcome() -> None:
    record = classify_response(
        task=task(),
        response={"choices": [{"message": {"reasoning_content": "private"}}]},
        execution=None,
    )

    assert record["reason"] == "invalid_format"
    assert record["all_tests_pass"] is False
    assert "private" not in json.dumps(record["response_metadata"])


def test_oracle_resume_reuses_exact_passes_and_checkpoints_each_task(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = config(tmp_path)
    task_ids = [f"task-{index:02d}" for index in range(EXPECTED_CPP_TASKS)]
    tasks = [{"instance_id": task_id, "fix_patch": "diff"} for task_id in task_ids]
    lock = {
        "sha256": "d" * 64,
        "platform": "linux/amd64",
        "tasks": {
            task_id: {
                "tag": "mswebench/fmtlib_m_fmt:pr-1",
                "digest": "mswebench/fmtlib_m_fmt@sha256:" + "e" * 64,
            }
            for task_id in task_ids
        },
    }
    prompts = {task_id: {"prompt": "prompt " + task_id} for task_id in task_ids}
    monkeypatch.setattr(
        modal_runtime,
        "oracle_cache_key",
        lambda _config, row, _lock: "cache-" + row["instance_id"],
    )
    prior = {
        task_id: {
            "schema_version": 1,
            "task_id": task_id,
            "instance_id": task_id,
            "oracle_cache_key": "cache-" + task_id,
            "setup_valid": True,
            "reason": "passed",
            "tests_collected": 1,
        }
        for task_id in task_ids
    }
    writes: list[dict[str, object]] = []

    admitted = modal_runtime.prepare_and_admit(
        config=cfg,
        lock=lock,
        tasks=tasks,
        dataset_receipt={"prompts": prompts},
        grade=lambda *_args: pytest.fail("exact passing oracle must be reused"),
        persist=writes.append,
        resume_state={"oracle_records": prior},
    )

    assert admitted["oracle_summary"]["all_passed"] is True
    checkpoints = [write for write in writes if "data/oracle.summary.json" in write]
    assert len(checkpoints) == EXPECTED_CPP_TASKS + 1
    assert checkpoints[-1]["data/oracle.summary.json"]["record_count"] == EXPECTED_CPP_TASKS


def test_stage_resume_reuses_matching_response_and_grader_record(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cfg = config(tmp_path)
    row = task()
    row["prompt"] = "public prompt"
    lock = {
        "sha256": "f" * 64,
        "tasks": {row["instance_id"]: {"digest": row["sandbox_image_digest"]}},
    }
    request = model_request(cfg, row["prompt"])
    raw_response = response("not a fenced diff")
    record = classify_response(task=row, response=raw_response, execution=None)
    record["request_sha256"] = model_request_sha256(request)
    record["grader_cache_key"] = grader_cache_key(
        cfg, row, lock["tasks"][row["instance_id"]], raw_response
    )
    assert record["response_sha256"] == response_sha256(raw_response)
    monkeypatch.setattr(
        modal_runtime,
        "_request",
        lambda **_kwargs: pytest.fail("matching saved response must be reused"),
    )
    writes: list[dict[str, object]] = []

    records, summary = modal_runtime._run_stage(
        name="smoke",
        config=cfg,
        lock=lock,
        tasks=[row],
        oracle_summary={"complete": True, "all_passed": True, "passed_count": 50},
        server_url="http://unused",
        api_key="unused",
        grade=lambda *_args: pytest.fail("matching grader record must be reused"),
        persist=writes.append,
        resume_stage={
            "requests": {row["instance_id"]: request},
            "responses": {row["instance_id"]: raw_response},
            "records": {row["instance_id"]: record},
        },
    )

    assert records == [record]
    assert summary["pass_rate"] == 0.0
    assert summary["provenance"]["modal_sdk_pin"] == "1.5.2"
    assert summary["provenance"]["prompt_sha256"][row["instance_id"]]
    assert summary["provenance"]["response_distribution"]["finish_reasons"] == {"stop": 1}
    assert summary["provenance"]["infrastructure_retries"] == 0
    assert any("smoke/summary.json" in write for write in writes)


def test_active_app_preflight_rejects_live_deterministic_app() -> None:
    name = "w8-glm47-multi-swe-cpp-run"

    assert modal_contract.modal_app_is_stopped([], name) is True
    assert (
        modal_contract.modal_app_is_stopped(
            [{"name": name, "state": "running"}],
            name,
        )
        is False
    )
    assert modal_contract.modal_app_is_stopped([{"name": name, "state": "stopped"}], name) is True
