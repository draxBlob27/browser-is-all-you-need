from __future__ import annotations

import base64
import hashlib
import json
import importlib.util
import secrets
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from w8_biayn.integrations.h100_research_sentry import (
    sign_bounded_payload,
    signature_domain_for_kind,
)
from w8_biayn.integrations.h100_signed_approval import (
    ENVELOPE_SCHEMA,
    PERMIT_SCHEMA,
    PUBLIC_KEY_SCHEMA,
    key_id_for_public_key,
    permit_signing_message,
)


SCRIPT = Path("scripts/run_miles_h100_dispatcher_abba.py")


def _module() -> dict:
    spec = importlib.util.spec_from_file_location("dispatcher_abba_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return vars(module)


def _write_leg_fixture(
    root: Path,
    module: dict,
    spec,
    *,
    scale: float = 1.0,
    corrupt_token_position: int | None = None,
    failure_trace: bool = False,
) -> tuple[Path, Path, dict]:
    root.mkdir(parents=True)
    log_path = root / "run.log"
    receipt_path = root / "run_receipt.txt"
    raw_signature = list(module["EXPECTED_RAW_TOKEN_SIGNATURE"])
    if corrupt_token_position is not None:
        raw_signature[corrupt_token_position] += 1

    lines = []
    for step, token_count in enumerate(raw_signature):
        position_factor = 1.0 + ((step % 4) - 1.5) * 0.01
        actor_tok_s = 6800.0 * position_factor * scale
        actor_time = token_count / actor_tok_s
        actor_tflops = 21.0 * position_factor * scale
        perf = {
            "perf/actor_train_time": actor_time,
            "perf/actor_train_tflops": actor_tflops,
            "perf/actor_train_tok_per_s": actor_tok_s,
            "perf/step_time": actor_time + 10.0,
            "perf/wait_time_ratio": 0.4,
        }
        train = {"train/loss": 0.25 + step * 0.001, "train/grad_norm": 0.3}
        lines.append(f"train_metric_utils.py:50 - perf {step}: {perf!r}")
        lines.append(f"log_utils.py:463 - step {step}: {train!r}")
    if failure_trace:
        lines.append("ray.exceptions.RayTaskError: synthetic failure")
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    receipt_config = module.get("expected_receipt_config")
    expected = receipt_config(spec) if receipt_config is not None else {}
    receipt = {
        "status": "success",
        "ray_status": 0,
        "wall_s": 600,
        "max_memory_used_mib": 72000,
        **expected,
    }
    receipt_path.write_text(
        "".join(f"{key}={value}\n" for key, value in receipt.items()),
        encoding="utf-8",
    )
    return log_path, receipt_path, expected


def _leg_payload(
    tmp_path: Path,
    module: dict,
    spec,
    *,
    scale: float,
    suffix: str = "",
) -> dict:
    log_path, receipt_path, expected = _write_leg_fixture(
        tmp_path / f"{spec.leg_id}{suffix}",
        module,
        spec,
        scale=scale,
    )
    summary, records = module["summarize_leg"](
        spec=spec,
        log_path=log_path,
        receipt_path=receipt_path,
        expected_receipt=expected,
        launcher_exit_code=0,
        ray_cleanup_exit_code=0,
    )
    return {"summary": summary, "records": records}


def legacy_protocol_is_fixed_dispatcher_abba_with_only_two_functional_deltas(
    tmp_path: Path,
) -> None:
    module = _module()
    protocol = module["build_protocol"](tmp_path / "run")

    assert protocol["schedule"] == ["a1", "b1", "b2", "a2"]
    assert protocol["fixed_workload"]["epochs"] == 4
    assert protocol["fixed_workload"]["total_perf_steps"] == 16
    assert protocol["fixed_workload"]["excluded_warmup_steps"] == [0, 1]
    assert len(protocol["fixed_workload"]["measured_token_signature"]) == 14
    assert protocol["exact_config_deltas"] == {
        "MILES_MOE_TOKEN_DISPATCHER_TYPE": {"A": "flex", "B": "alltoall"},
        "MILES_MOE_ENABLE_DEEPEP": {"A": "1", "B": "0"},
    }
    assert protocol["promotion_thresholds"]["minimum_point_ratio"] == 1.03
    assert protocol["promotion_thresholds"]["minimum_adjacent_baseline_retention"] == 0.98
    assert protocol["statistics"]["combined_pair_count"] == 28


def legacy_dry_run_is_machine_readable_and_side_effect_free(tmp_path: Path) -> None:
    run_root = tmp_path / "not-created"
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--run-root", str(run_root), "--dry-run"],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["protocol"] == "miles_h100_dispatcher_abba"
    assert payload["schedule"] == ["a1", "b1", "b2", "a2"]
    assert payload["outputs"]["sentry"] == "sentry_result.json"
    assert not run_root.exists()


def legacy_controlled_environment_discards_ambient_experiment_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _module()
    spec = module["LEG_SPECS"][0]
    monkeypatch.setenv("MILES_MAX_TOKENS_PER_GPU", "999")
    monkeypatch.setenv("MILES_EXTRA_ARGS", "--fp8-format e4m3")
    monkeypatch.setenv("NCCL_ALGO", "NVLS")
    monkeypatch.setenv("PYTHONPATH", "/tmp/ambient")
    monkeypatch.setenv("WANDB_API_KEY", "preserved-secret")

    controlled = module["controlled_leg_config"](spec, tmp_path / "run", "exp")
    env = module["build_subprocess_env"](controlled)

    assert env["MILES_MAX_TOKENS_PER_GPU"] == "16384"
    assert env["MILES_EXTRA_ARGS"] == ""
    assert "NCCL_ALGO" not in env
    assert "PYTHONPATH" not in env
    assert env["WANDB_API_KEY"] == "preserved-secret"


def legacy_leg_summary_excludes_two_warmups_and_preserves_all_raw_steps(
    tmp_path: Path,
) -> None:
    module = _module()
    spec = module["LEG_SPECS"][0]
    log_path, receipt_path, expected = _write_leg_fixture(tmp_path / "leg", module, spec)

    summary, records = module["summarize_leg"](
        spec=spec,
        log_path=log_path,
        receipt_path=receipt_path,
        expected_receipt=expected,
        launcher_exit_code=0,
        ray_cleanup_exit_code=0,
    )

    assert summary["valid"] is True
    assert len(records) == 16
    assert [row["measured"] for row in records[:2]] == [False, False]
    assert [row["raw_step"] for row in records if row["measured"]] == list(range(2, 16))
    assert summary["measured_step_count"] == 14
    assert summary["measured_token_signature"] == list(module["EXPECTED_MEASURED_TOKEN_SIGNATURE"])
    expected_mfu = 100.0 * records[2]["actor_train_tflops_per_gpu"] / 989.0
    assert records[2]["estimated_mfu_percent"] == pytest.approx(expected_mfu)


def legacy_signature_mismatch_and_failure_trace_invalidate_leg(tmp_path: Path) -> None:
    module = _module()
    spec = module["LEG_SPECS"][0]
    mismatch_log, mismatch_receipt, expected = _write_leg_fixture(
        tmp_path / "mismatch",
        module,
        spec,
        corrupt_token_position=2,
    )
    mismatch, _ = module["summarize_leg"](
        spec=spec,
        log_path=mismatch_log,
        receipt_path=mismatch_receipt,
        expected_receipt=expected,
        launcher_exit_code=0,
        ray_cleanup_exit_code=0,
    )
    failure_log, failure_receipt, expected = _write_leg_fixture(
        tmp_path / "failure",
        module,
        spec,
        failure_trace=True,
    )
    failure, _ = module["summarize_leg"](
        spec=spec,
        log_path=failure_log,
        receipt_path=failure_receipt,
        expected_receipt=expected,
        launcher_exit_code=0,
        ray_cleanup_exit_code=0,
    )

    assert mismatch["valid"] is False
    assert "fixed_measured_token_signature_mismatch" in mismatch["rejection_reasons"]
    assert failure["valid"] is False
    assert "failure_trace_in_log" in failure["rejection_reasons"]


def legacy_promotion_requires_3pct_paired_win_confidence_retention_and_history(
    tmp_path: Path,
) -> None:
    module = _module()
    specs = {spec.leg_id: spec for spec in module["LEG_SPECS"]}
    payloads = {
        "a1": _leg_payload(tmp_path, module, specs["a1"], scale=1.0),
        "b1": _leg_payload(tmp_path, module, specs["b1"], scale=1.04),
        "b2": _leg_payload(tmp_path, module, specs["b2"], scale=1.04),
        "a2": _leg_payload(tmp_path, module, specs["a2"], scale=1.0),
    }
    postflight = {"checkpoint_unchanged": True, "train_data_unchanged": True}

    comparison, paired_rows = module["build_comparison"](payloads, postflight=postflight)

    assert len(paired_rows) == 28
    assert comparison["promoted"] is True
    assert comparison["decision"] == "promote_b"
    combined = comparison["combined_paired_statistics"]
    assert combined["mfu"]["point_ratio"] == pytest.approx(1.04)
    assert combined["mfu"]["confidence_lower_bound_ratio"] == pytest.approx(1.04)
    assert combined["actor_tok_s"]["point_ratio"] == pytest.approx(1.04)
    assert all(
        pair["throughput_retention"] == pytest.approx(1.04) for pair in comparison["pair_summaries"]
    )

    weak_payloads = {
        "a1": _leg_payload(tmp_path, module, specs["a1"], scale=1.0, suffix="-weak"),
        "b1": _leg_payload(tmp_path, module, specs["b1"], scale=1.029, suffix="-weak"),
        "b2": _leg_payload(tmp_path, module, specs["b2"], scale=1.029, suffix="-weak"),
        "a2": _leg_payload(tmp_path, module, specs["a2"], scale=1.0, suffix="-weak"),
    }
    weak, _ = module["build_comparison"](weak_payloads, postflight=postflight)

    assert weak["promoted"] is False
    assert "combined_mfu_point_improvement_at_least_3pct" in weak["failed_requirements"]
    assert "combined_actor_tok_s_point_improvement_at_least_3pct" in weak["failed_requirements"]


def legacy_one_sided_confidence_gate_is_deterministic_on_log_ratios() -> None:
    module = _module()
    rows = [{"mfu_ratio": ratio, "actor_tok_s_ratio": ratio} for ratio in ([0.8, 1.4] * 14)]

    first = module["paired_metric_stats"](rows, "mfu_ratio")
    second = module["paired_metric_stats"](rows, "mfu_ratio")

    assert first == second
    assert first["point_ratio"] > 1.03
    assert first["confidence_lower_bound_ratio"] < 1.0
    assert first["passes_point_improvement"] is True
    assert first["passes_confidence"] is False


def legacy_machine_readable_json_and_csv_writers_are_stable(tmp_path: Path) -> None:
    module = _module()
    json_path = tmp_path / "rows.json"
    csv_path = tmp_path / "rows.csv"
    rows = [{"leg_id": "a1", "raw_step": 2, "measured": True}]

    module["write_json"](json_path, rows)
    module["write_csv"](csv_path, rows, ("leg_id", "raw_step", "measured"))

    assert json.loads(json_path.read_text()) == rows
    assert csv_path.read_text().splitlines() == [
        "leg_id,raw_step,measured",
        "a1,2,True",
    ]


SENTRY_PRINCIPAL = "research-sentry"
EXECUTOR_PRINCIPAL = "h100-executor"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_key_pair(root: Path, name: str) -> tuple[Path, Path]:
    private_key = Ed25519PrivateKey.generate()
    private_path = root / f"{name}.private.pem"
    public_path = root / f"{name}.public.json"
    private_path.parent.mkdir(parents=True, exist_ok=True)
    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    private_path.chmod(0o600)
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_path.write_text(
        json.dumps(
            {
                "schema": PUBLIC_KEY_SCHEMA,
                "algorithm": "Ed25519",
                "key_id": key_id_for_public_key(public_raw),
                "public_key_base64": base64.b64encode(public_raw).decode("ascii"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return private_path, public_path


def _write_gate0_chain(root: Path) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=True)
    private_path, public_path = _write_key_pair(root, "gate0")
    gate1_private_key, gate1_public_key = _write_key_pair(root / "gate1", "sentry")
    gate1_document = json.loads(gate1_public_key.read_text(encoding="utf-8"))
    private_key = serialization.load_pem_private_key(private_path.read_bytes(), password=None)
    booking = root / "booking_request.json"
    booking.write_text(
        json.dumps(
            {
                "issue_number": 32,
                "request_id": "booking-issue32",
                "gate1_trust": {
                    "public_key_sha256": _sha256(gate1_public_key),
                    "key_id": gate1_document["key_id"],
                    "sentry_principal": SENTRY_PRINCIPAL,
                    "executor_principal": EXECUTOR_PRINCIPAL,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    executable = root / "lium-provider"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    interpreter = Path("/bin/sh")
    cli = root / "lium-cli"
    cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    cli.chmod(0o755)
    ssh_public_key = root / "id_ed25519.pub"
    ssh_public_key.write_text("ssh-ed25519 AAAATEST dispatcher-test\n", encoding="utf-8")
    working_directory = root / "provider-cwd"
    working_directory.mkdir()
    provider_output = root / "provider_output.json"
    allocation_name = "issue-32-dispatcher-abba"
    executor_huid = "golden-shark-c6"
    provider_output.write_text(
        json.dumps(
            {
                "schema": "lium-h100-pod-create/v2",
                "status": "RUNNING",
                "pod": {
                    "id": "pod-issue32-001",
                    "name": allocation_name,
                    "huid": "pod-huid-001",
                    "ssh_cmd": "ssh root@example.invalid",
                },
                "executor": {
                    "id": "executor-uuid-001",
                    "huid": executor_huid,
                    "gpu_count": 8,
                    "gpu_type": "H100",
                    "gpu_model": "H100 SXM",
                    "observed_rate_usd_per_hour": 18.0,
                    "observed_rate_usd_per_gpu_hour": 2.25,
                    "observed_rate_status": "provider_reported_nonzero",
                    "max_rate_usd_per_hour": 18.0,
                    "rate_authority": "provider_raw_price_per_gpu_x_gpu_count/v1",
                    "rate_evidence": {
                        "executor_id": "executor-uuid-001",
                        "gpu_count": 8,
                        "available_gpu_count": 8,
                        "price_per_gpu": 2.25,
                        "price_per_hour": 18.0,
                        "pending_price_change": False,
                    },
                    "rent_boundary": {
                        "status": "VERIFIED_PRE_AND_POST",
                        "endpoint": "/executors/executor-uuid-001/rent",
                        "before_post": {
                            "authority": "provider_raw_price_per_gpu_x_gpu_count/v1",
                            "executor_id": "executor-uuid-001",
                            "gpu_count": 8,
                            "available_gpu_count": 8,
                            "price_per_gpu": 2.25,
                            "price_per_hour": 18.0,
                            "pending_price_change": False,
                        },
                        "after_post": {
                            "authority": "provider_raw_price_per_gpu_x_gpu_count/v1",
                            "executor_id": "executor-uuid-001",
                            "gpu_count": 8,
                            "available_gpu_count": 0,
                            "price_per_gpu": 2.25,
                            "price_per_hour": 18.0,
                            "pending_price_change": False,
                        },
                    },
                },
                "template": {
                    "id": "template-001",
                    "name": "Pytorch",
                    "docker_image": "daturaai/pytorch",
                    "docker_image_tag": "cuda13-test",
                    "status": "VERIFY_SUCCESS",
                },
                "runtime_evidence": {
                    "provider_version": "1.3.0",
                    "interpreter": {
                        "path": str(interpreter),
                        "sha256": _sha256(interpreter),
                        "version": "3.11.14",
                    },
                    "lium_sdk": {"distribution": "lium.io", "version": "0.0.3"},
                    "lium_cli": {
                        "path": str(cli.resolve()),
                        "sha256": _sha256(cli),
                        "version": "0.0.3",
                    },
                },
                "access": {
                    "ssh_public_key_path": str(ssh_public_key.resolve()),
                    "ssh_public_key_sha256": _sha256(ssh_public_key),
                },
                "create_reconciliation": {
                    "status": "CONFIRMED_UNIQUE",
                    "rent_mutation_attempt_policy": "single-attempt-sdk-request-boundary/v1",
                    "allocation_name": allocation_name,
                    "pod_id": "pod-issue32-001",
                    "successful_snapshots": 2,
                    "lookup_failures": 0,
                    "final_active_pod_ids": ["pod-issue32-001"],
                    "observed_duplicate_pod_ids": [],
                    "duplicate_cleanup_status": "NOT_REQUIRED",
                },
                "schedule": {
                    "confirmed": True,
                    "termination_time": "2026-07-10T14:00:00Z",
                    "server_removal_scheduled_at": "2026-07-10T14:00:00Z",
                    "ttl_seconds": 7200,
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    now = datetime.now(timezone.utc).replace(microsecond=0)
    public_document = json.loads(public_path.read_text(encoding="utf-8"))
    permit_payload = {
        "schema": PERMIT_SCHEMA,
        "stage": "lium-booking",
        "decision": "PROMOTABLE",
        "request_id": f"gate0-{secrets.token_hex(12)}",
        "nonce": secrets.token_hex(32),
        "issued_at": (now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (now + timedelta(minutes=9)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sentry_principal": SENTRY_PRINCIPAL,
        "executor_principal": EXECUTOR_PRINCIPAL,
        "source_sha256": "1" * 64,
        "runtime_sha256": "2" * 64,
        "data_sha256": "3" * 64,
        "checkpoint_sha256": "4" * 64,
        "parent_request_sha256": _sha256(booking),
        "executor_id": executor_huid,
        "provider": "lium",
        "profile": "h100-8x",
        "provider_executable": str(executable.resolve()),
        "provider_executable_sha256": _sha256(executable),
        "provider_version": "1.3.0",
        "provider_interpreter": str(interpreter),
        "provider_interpreter_sha256": _sha256(interpreter),
        "provider_interpreter_version": "3.11.14",
        "lium_sdk_distribution": "lium.io",
        "lium_sdk_version": "0.0.3",
        "lium_cli_path": str(cli.resolve()),
        "lium_cli_sha256": _sha256(cli),
        "lium_cli_version": "0.0.3",
        "working_directory": str(working_directory.resolve()),
        "environment": {"HOME": str((root / "home").resolve())},
        "credential_transport": "stdin-line/v1",
        "ssh_public_key_path": str(ssh_public_key.resolve()),
        "ssh_public_key_sha256": _sha256(ssh_public_key),
        "template_id": "template-001",
        "template_image": "daturaai/pytorch",
        "template_tag": "cuda13-test",
        "template_status": "VERIFY_SUCCESS",
        "issue_number": 32,
        "allocation_name": allocation_name,
        "argv": [
            str(executable.resolve()),
            "up",
            executor_huid,
            "--ttl",
            "2h",
            "--name",
            allocation_name,
            "--yes",
            "--template-id",
            "template-001",
            "--template-image",
            "daturaai/pytorch",
            "--template-tag",
            "cuda13-test",
            "--template-status",
            "VERIFY_SUCCESS",
            "--expected-provider-version",
            "1.3.0",
            "--expected-interpreter-path",
            str(interpreter),
            "--expected-interpreter-sha256",
            _sha256(interpreter),
            "--expected-interpreter-version",
            "3.11.14",
            "--expected-lium-sdk-version",
            "0.0.3",
            "--expected-lium-cli-path",
            str(cli.resolve()),
            "--expected-lium-cli-sha256",
            _sha256(cli),
            "--expected-lium-cli-version",
            "0.0.3",
            "--ssh-public-key-path",
            str(ssh_public_key.resolve()),
            "--ssh-public-key-sha256",
            _sha256(ssh_public_key),
            "--max-rate",
            "18",
            "--expected-observed-rate",
            "18",
            "--expected-rate-authority",
            "provider_raw_price_per_gpu_x_gpu_count/v1",
        ],
        "gpu_type": "H100",
        "gpu_count": 8,
        "ttl_seconds": 7200,
        "max_cost_usd": 36,
        "max_node_hourly_rate_usd": 18,
        "observed_node_hourly_rate_usd": 18,
        "observed_node_hourly_rate_status": "provider_reported_nonzero",
        "max_node_hours": 2,
        "provider_timeout_seconds": 300,
    }
    signature = private_key.sign(permit_signing_message(permit_payload))
    permit = root / "permit.json"
    permit.write_text(
        json.dumps(
            {
                "schema": ENVELOPE_SCHEMA,
                "key_id": public_document["key_id"],
                "payload": permit_payload,
                "signature_base64": base64.b64encode(signature).decode("ascii"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    claim = root / "gate0_claim.json"
    claim.write_text(
        json.dumps(
            {
                "request_id": permit_payload["request_id"],
                "nonce": permit_payload["nonce"],
                "permit_sha256": _sha256(permit),
                "consumed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    receipt = root / "launch_receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "schema": "h100-lium-launch-receipt/v2",
                "status": "COMPLETED",
                "permit": {
                    "path": str(permit.resolve()),
                    "sha256": _sha256(permit),
                    "key_id": public_document["key_id"],
                    "request_id": permit_payload["request_id"],
                    "nonce": permit_payload["nonce"],
                    "issued_at": permit_payload["issued_at"],
                    "expires_at": permit_payload["expires_at"],
                },
                "claim": {"path": str(claim.resolve()), "sha256": _sha256(claim)},
                "parent_request": {
                    "path": str(booking.resolve()),
                    "sha256": _sha256(booking),
                },
                "provider": {
                    "name": "lium",
                    "profile": "h100-8x",
                    "executor_id": executor_huid,
                    "executable": str(executable.resolve()),
                    "executable_sha256": _sha256(executable),
                    "declared_version": "1.3.0",
                },
                "access": {
                    "ssh_public_key_path": str(ssh_public_key.resolve()),
                    "ssh_public_key_sha256": _sha256(ssh_public_key),
                },
                "provider_output": {
                    "path": str(provider_output.resolve()),
                    "sha256": _sha256(provider_output),
                    "size_bytes": provider_output.stat().st_size,
                },
                "allocation": {"issue_number": 32, "name": allocation_name},
                "execution": {
                    "cwd": str(working_directory.resolve()),
                    "argv": permit_payload["argv"],
                    "exit_code": 0,
                    "wrapper_exit_code": 0,
                    "timed_out": False,
                    "credential_transport": "stdin-line/v1",
                    "started_at": (now - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "finished_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                "budget": {
                    "ttl_seconds": 7200,
                    "max_cost_usd": 36,
                    "max_node_hourly_rate_usd": 18,
                    "observed_node_hourly_rate_usd": 18,
                    "observed_node_hourly_rate_status": "provider_reported_nonzero",
                    "max_node_hours": 2,
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "permit": permit,
        "launch_receipt": receipt,
        "booking_request": booking,
        "provider_output": provider_output,
        "public_key": public_path,
        "gate1_private_key": gate1_private_key,
        "gate1_public_key": gate1_public_key,
    }


def _prepare_run(module: dict, root: Path) -> tuple[Path, dict[str, Path]]:
    root.mkdir(parents=True, exist_ok=True)
    run_root = root / "run"
    module["CANONICAL_RUN_ROOT"] = run_root.resolve()
    module["GATE1_CONSUMPTION_ROOT"] = root / "gate1-consumption/v1"
    hf_checkpoint = root / "hf-checkpoint"
    hf_checkpoint.mkdir()
    runtime_pins = module["load_acceptance_contract"]()["runtime_pins"]
    hf_revision = runtime_pins["hf_revision"]
    container_reference = runtime_pins["container_image"]
    container_digest = container_reference.rsplit("@", 1)[1]
    revision_marker = hf_checkpoint / ".w8-hf-revision"
    revision_marker.write_text(hf_revision + "\n", encoding="utf-8")
    container_image_id = "sha256:" + "a" * 64
    container_inspection = root / "issue32-t1-container-inspect.json"
    container_inspection.write_text(
        json.dumps(
            [
                {
                    "Id": container_image_id,
                    "RepoDigests": [container_reference],
                    "Os": "linux",
                    "Architecture": "amd64",
                }
            ],
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    setup_attestation = root / "issue32-t1-setup-attestation.json"
    setup_attestation.write_text(
        json.dumps(
            {
                "schema": module["SETUP_ATTESTATION_SCHEMA"],
                "created_at_utc": "2026-07-10T12:00:00Z",
                "hf_checkpoint_path": str(hf_checkpoint),
                "hf_model": runtime_pins["hf_model"],
                "hf_revision": hf_revision,
                "hf_revision_marker_path": str(revision_marker),
                "hf_revision_marker_sha256": _sha256(revision_marker),
                "container_image_reference": container_reference,
                "container_image_digest": container_digest,
                "container_platform": runtime_pins["container_platform"],
                "container_image_id": container_image_id,
                "container_inspection_path": str(container_inspection),
                "container_inspection_sha256": _sha256(container_inspection),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    module["HF_CHECKPOINT"] = hf_checkpoint
    module["HF_REVISION_MARKER_PATH"] = revision_marker
    module["CONTAINER_INSPECTION_PATH"] = container_inspection
    module["SETUP_ATTESTATION_PATH"] = setup_attestation
    budget = root / "budget.json"
    budget.write_text('{"tranche_id":"T1"}\n', encoding="utf-8")
    gate0 = _write_gate0_chain(root / "gate0-source")
    source = {
        "ok": True,
        "repo_sha": "a" * 40,
        "training_base_sha": module["TRAINING_BASE_SHA"],
    }
    module["collect_source_provenance"] = lambda: source
    module["collect_hardware_receipt"] = lambda value: {
        "ok": True,
        "repo_sha": value["repo_sha"],
        "training_base_sha": value["training_base_sha"],
        "gpu_operating_rows": [
            {
                "index": str(index),
                "clocks.sm": "345",
                "power.draw": "75",
                "power.limit": "700",
                "temperature.gpu": "30",
                "clocks_throttle_reasons.active": "0x0000000000000000",
            }
            for index in range(8)
        ],
    }
    module["checkpoint_receipt"] = lambda setup, setup_path: {
        "schema_version": 2,
        "checkpoint": "fixed",
        "sha256": "1" * 64,
        "hf_model": setup["hf_model"],
        "hf_revision": setup["hf_revision"],
        "hf_revision_marker_sha256": setup["hf_revision_marker_sha256"],
        "container_image_reference": setup["container_image_reference"],
        "container_image_digest": setup["container_image_digest"],
        "container_platform": setup["container_platform"],
        "container_image_id": setup["container_image_id"],
        "container_inspection_path": setup["container_inspection_path"],
        "container_inspection_sha256": setup["container_inspection_sha256"],
        "setup_attestation_path": str(setup_path),
        "setup_attestation_sha256": _sha256(setup_path),
    }
    module["data_receipt"] = lambda: {
        "sha256": module["TRAIN_SHA256"],
        "row_count": 128,
        "manifest_path": "/data/glm47-pie-profile-long128-oracle-v2/manifest.json",
        "manifest_sha256": module["TRAIN_MANIFEST_SHA256"],
    }
    module["check_wandb_authenticated_read"] = lambda: {
        "ok": True,
        "mode": "online",
        "authenticated_api_read": True,
    }
    module["runtime_receipt"] = lambda setup, setup_path: {
        "schema_version": 2,
        "ok": True,
        "returncode": 0,
        "stdout": "ok",
        "stderr": "",
        "hf_checkpoint_path": setup["hf_checkpoint_path"],
        "hf_model": setup["hf_model"],
        "hf_revision": setup["hf_revision"],
        "hf_revision_marker_path": setup["hf_revision_marker_path"],
        "hf_revision_marker_sha256": setup["hf_revision_marker_sha256"],
        "container_image_reference": setup["container_image_reference"],
        "container_image_digest": setup["container_image_digest"],
        "container_platform": setup["container_platform"],
        "container_image_id": setup["container_image_id"],
        "container_inspection_path": setup["container_inspection_path"],
        "container_inspection_sha256": setup["container_inspection_sha256"],
        "setup_attestation_path": str(setup_path),
        "setup_attestation_sha256": _sha256(setup_path),
    }
    module["_run_capture"] = lambda *args, **kwargs: {
        "command": args[0],
        "returncode": 0,
        "stdout": "ok",
        "stderr": "",
    }
    assert (
        module["prepare_phase"](
            run_root,
            budget,
            gate0_permit=gate0["permit"],
            gate0_launch_receipt=gate0["launch_receipt"],
            gate0_booking_request=gate0["booking_request"],
            gate0_provider_output=gate0["provider_output"],
        )
        == 0
    )
    return run_root, gate0


def _write_signed_decision(
    module: dict,
    path: Path,
    *,
    private_key: Path,
    public_key: Path,
    stage: str,
    request_path: Path,
    parent_decision_sha256: str,
    parent_request_sha256: str,
    decision: str = "PROMOTABLE",
    signer_principal: str = SENTRY_PRINCIPAL,
    verifier_principal: str = EXECUTOR_PRINCIPAL,
    domain_stage: str | None = None,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> Path:
    signed = sign_bounded_payload(
        {
            "stage": stage,
            "decision": decision,
            "request_sha256": module["_sha256"](request_path),
            "parent_decision_sha256": parent_decision_sha256,
            "parent_request_sha256": parent_request_sha256,
        },
        private_key_path=private_key,
        public_key_path=public_key,
        domain=signature_domain_for_kind(domain_stage or stage),
        signer_principal=signer_principal,
        verifier_principal=verifier_principal,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    module["write_json"](path, signed)
    return path


def _install_fake_run_leg(
    module: dict,
    calls: list[str],
    *,
    validity: dict[str, bool] | None = None,
) -> None:
    validity = validity or {}

    def fake_run_leg(spec, root, *, deadline_utc=None):
        assert deadline_utc is None or deadline_utc.tzinfo is not None
        calls.append(spec.leg_id)
        leg_root = root / "legs" / f"{spec.order:02d}_{spec.leg_id}"
        trial = leg_root / "trial_summary.json"
        module["write_json"](trial, {"name": spec.leg_id})
        manifest = leg_root / "leg_evidence_manifest.json"
        module["write_json"](
            manifest,
            {
                "paths": {"trial_summary": str(trial)},
                "sha256": {"trial_summary": module["_sha256"](trial)},
            },
        )
        return {
            "leg_id": spec.leg_id,
            "trial_summary": str(trial),
            "evidence_manifest": str(manifest),
            "evidence_manifest_sha256": module["_sha256"](manifest),
            "valid": validity.get(spec.leg_id, True),
        }

    module["run_leg"] = fake_run_leg


def _phase_kwargs(public_key: Path, ledger: Path | None = None) -> dict:
    del ledger
    return {
        "sentry_public_key": public_key,
        "sentry_principal": SENTRY_PRINCIPAL,
        "executor_principal": EXECUTOR_PRINCIPAL,
    }


def test_ea02_cli_and_protocol_are_strictly_staged(tmp_path: Path) -> None:
    module = _module()
    protocol = module["build_protocol"](tmp_path)

    assert module["CANONICAL_RUN_ROOT"] == Path("/tmp/w8-issue32-t1")
    assert module["GATE1_CONSUMPTION_ROOT"] == Path(
        "/data/w8-biayn/control-plane/gate1-consumption/v1"
    )
    with pytest.raises(SystemExit, match="run root must be exactly"):
        module["_require_canonical_run_root"](tmp_path)
    assert protocol["phases"] == ["prepare", "first-pair", "second-pair"]
    assert protocol["phase_legs"] == {
        "first-pair": ["a1", "b1"],
        "second-pair": ["b2", "a2"],
    }
    assert protocol["authority"] == "executor_evidence_only"
    assert protocol["fixed_workload"]["total_perf_steps"] == 16
    assert protocol["fixed_workload"]["measured_steps"] == 14
    with pytest.raises(SystemExit):
        module["parse_args"](["--run-root", str(tmp_path)])
    with pytest.raises(SystemExit):
        module["parse_args"](["first-pair", "--run-root", str(tmp_path)])
    with pytest.raises(SystemExit):
        module["parse_args"](
            [
                "first-pair",
                "--run-root",
                str(tmp_path),
                "--sentry-approval",
                "approval.json",
                "--sentry-public-key",
                "sentry.json",
                "--sentry-principal",
                SENTRY_PRINCIPAL,
                "--executor-principal",
                EXECUTOR_PRINCIPAL,
                "--approval-ledger",
                str(tmp_path / "fresh-ledger"),
            ]
        )


def test_prepare_rejects_symlinked_or_permissive_canonical_run_root(tmp_path: Path) -> None:
    module = _module()
    target = tmp_path / "target"
    target.mkdir(mode=0o700)
    symlink = tmp_path / "run"
    symlink.symlink_to(target, target_is_directory=True)
    module["CANONICAL_RUN_ROOT"] = symlink.resolve()

    with pytest.raises(SystemExit, match="real private directory"):
        module["_prepare_secure_run_root"](symlink)

    symlink.unlink()
    symlink.mkdir(mode=0o755)
    symlink.chmod(0o755)
    module["CANONICAL_RUN_ROOT"] = symlink.resolve()
    with pytest.raises(SystemExit, match="mode 0700"):
        module["_prepare_secure_run_root"](symlink)


def test_runner_never_authors_or_invokes_scientific_decisions() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "verify_signed_decision" in source
    assert "consume_signed_decision_once" in source
    assert "sign_bounded_payload" not in source
    assert "sentry_result.json" not in source
    assert "evaluate_promotion" not in source
    assert "evaluate_preflight" not in source
    assert "promoted" not in source.lower()


def test_prepare_writes_immutable_receipts_without_training(
    tmp_path: Path,
) -> None:
    module = _module()
    run_root, gate0 = _prepare_run(module, tmp_path)
    assert (run_root / "hardware.json").is_file()
    assert (run_root / "budget.json").is_file()
    assert not (run_root / "legs").exists()
    request = json.loads((run_root / "preflight_request.json").read_text())
    assert set(request["input_hashes"]) >= {"hardware", "budget", "checkpoint", "data"}
    assert len(bytes.fromhex(request["nonce"])) == 32
    assert request["sentry_principal"] == SENTRY_PRINCIPAL
    assert request["executor_principal"] == EXECUTOR_PRINCIPAL
    assert request["gate0"]["allocation_id"] == "pod-issue32-001"
    assert request["gate0"]["allocation_name"] == "issue-32-dispatcher-abba"
    booking = json.loads(gate0["booking_request"].read_text(encoding="utf-8"))
    assert request["gate1_trust"] == booking["gate1_trust"]
    manifest = json.loads((run_root / "prepare_manifest.json").read_text())
    for name in ("source", "runtime", "data", "checkpoint"):
        receipt_path = run_root / "receipts" / f"{name}.json"
        assert request["prepared_evidence"][name] == json.loads(receipt_path.read_text())
        assert request["input_hashes"][name] == _sha256(receipt_path)
        assert manifest["sha256"][name] == _sha256(receipt_path)
    runtime_pins = module["load_acceptance_contract"]()["runtime_pins"]
    assert request["prepared_evidence"]["runtime"]["hf_revision"] == runtime_pins["hf_revision"]
    assert request["prepared_evidence"]["runtime"]["returncode"] == 0
    assert (
        request["prepared_evidence"]["runtime"]["container_image_reference"]
        == (runtime_pins["container_image"])
    )
    assert (
        request["prepared_evidence"]["runtime"]["container_image_digest"]
        == (runtime_pins["container_image"].rsplit("@", 1)[1])
    )
    assert request["prepared_evidence"]["checkpoint"]["hf_revision"] == runtime_pins["hf_revision"]
    assert (
        request["prepared_evidence"]["checkpoint"]["container_image_reference"]
        == (runtime_pins["container_image"])
    )
    setup_path = Path(manifest["supporting_artifacts"]["setup_attestation"])
    assert setup_path == run_root / "receipts/setup_attestation.json"
    assert manifest["supporting_sha256"]["setup_attestation"] == _sha256(setup_path)
    setup = json.loads(setup_path.read_text())
    assert set(setup) == {
        "schema",
        "created_at_utc",
        "hf_checkpoint_path",
        "hf_model",
        "hf_revision",
        "hf_revision_marker_path",
        "hf_revision_marker_sha256",
        "container_image_reference",
        "container_image_digest",
        "container_platform",
        "container_image_id",
        "container_inspection_path",
        "container_inspection_sha256",
    }
    assert set(manifest["supporting_artifacts"]) == {
        "setup_attestation",
        "hf_revision_marker",
        "container_inspection",
    }
    assert (
        request["prepared_evidence"]["setup"]["hf_revision_marker_content"] == setup["hf_revision"]
    )
    assert (
        request["prepared_evidence"]["setup"]["container_inspection"][0]["Id"]
        == setup["container_image_id"]
    )
    copied_paths = module["_gate0_paths"](run_root)
    for name, source in gate0.items():
        if name not in copied_paths:
            continue
        destination = copied_paths[name]
        assert destination.read_bytes() == source.read_bytes()


def test_data_receipt_requires_exact_launcher_manifest(tmp_path: Path) -> None:
    module = _module()
    data_dir = tmp_path / "data"
    train = data_dir / "sft/train.jsonl"
    train.parent.mkdir(parents=True)
    train.write_text('{"messages":[],"metadata":{}}\n', encoding="utf-8")
    train_sha = _sha256(train)
    manifest = data_dir / "manifest.json"
    module["write_json"](
        manifest,
        {
            "profile": "glm47-pie-profile-long128-oracle-v2",
            "train_count": 1,
            "train_sha256": train_sha,
        },
    )
    module["DATA_DIR"] = data_dir
    module["TRAIN_SHA256"] = train_sha
    module["TRAIN_ROW_COUNT"] = 1
    module["TRAIN_MANIFEST_SHA256"] = _sha256(manifest)

    receipt = module["data_receipt"]()

    assert receipt["sha256"] == train_sha
    assert receipt["manifest_sha256"] == _sha256(manifest)
    manifest.unlink()
    with pytest.raises(RuntimeError, match="launcher data manifest missing"):
        module["data_receipt"]()


def test_pair_phases_require_signed_chain_and_preserve_approval_bytes(tmp_path: Path) -> None:
    module = _module()
    run_root, gate0 = _prepare_run(module, tmp_path)
    private_key = gate0["gate1_private_key"]
    public_key = gate0["gate1_public_key"]
    ledger = tmp_path / "approval-ledger"
    calls: list[str] = []
    _install_fake_run_leg(module, calls)
    preflight = _write_signed_decision(
        module,
        tmp_path / "signed-preflight.json",
        private_key=private_key,
        public_key=public_key,
        stage="preflight",
        request_path=run_root / "preflight_request.json",
        parent_decision_sha256=module["_sha256"](run_root / "gate0/permit.json"),
        parent_request_sha256=module["_sha256"](run_root / "gate0/booking_request.json"),
    )
    preflight_bytes = preflight.read_bytes()
    preflight_request = json.loads((run_root / "preflight_request.json").read_text())
    gate1_key = json.loads(public_key.read_text(encoding="utf-8"))
    assert preflight_request["sentry_principal"] == SENTRY_PRINCIPAL
    assert preflight_request["gate0"]["key_id"] != gate1_key["key_id"]
    assert module["first_pair_phase"](run_root, preflight, **_phase_kwargs(public_key, ledger)) == 0
    assert calls == ["a1", "b1"]
    assert (run_root / "approvals/preflight.json").read_bytes() == preflight_bytes
    screen_request = json.loads((run_root / "screen_request.json").read_text())
    assert screen_request["parent_decision_sha256"] == _sha256(preflight)
    assert screen_request["parent_request_sha256"] == _sha256(run_root / "preflight_request.json")
    assert screen_request["gate1_trust"] == preflight_request["gate1_trust"]

    screen = _write_signed_decision(
        module,
        tmp_path / "signed-screen.json",
        private_key=private_key,
        public_key=public_key,
        stage="screen",
        request_path=run_root / "screen_request.json",
        parent_decision_sha256=_sha256(preflight),
        parent_request_sha256=_sha256(run_root / "preflight_request.json"),
    )
    screen_bytes = screen.read_bytes()
    assert module["second_pair_phase"](run_root, screen, **_phase_kwargs(public_key, ledger)) == 0
    assert calls == ["a1", "b1", "b2", "a2"]
    assert (run_root / "approvals/screen.json").read_bytes() == screen_bytes


@pytest.mark.parametrize(
    "failure",
    [
        "tamper",
        "expired",
        "wrong_domain",
        "wrong_stage",
        "wrong_principal",
        "wrong_parent",
        "wrong_key",
        "rejected",
        "request_tamper",
    ],
)
def test_rejected_signed_preflight_paths_make_zero_run_leg_calls(
    tmp_path: Path,
    failure: str,
) -> None:
    module = _module()
    run_root, gate0 = _prepare_run(module, tmp_path / failure)
    private_key = gate0["gate1_private_key"]
    public_key = gate0["gate1_public_key"]
    passed_public_key = public_key
    stage = "screen" if failure == "wrong_stage" else "preflight"
    domain_stage = "screen" if failure == "wrong_domain" else None
    signer = "wrong-sentry" if failure == "wrong_principal" else SENTRY_PRINCIPAL
    parent_decision = (
        "0" * 64 if failure == "wrong_parent" else _sha256(run_root / "gate0/permit.json")
    )
    issued_at = None
    expires_at = None
    if failure == "expired":
        issued_at = datetime.now(timezone.utc) - timedelta(hours=2)
        expires_at = issued_at + timedelta(minutes=30)
    approval = _write_signed_decision(
        module,
        tmp_path / failure / "approval.json",
        private_key=private_key,
        public_key=public_key,
        stage=stage,
        request_path=run_root / "preflight_request.json",
        parent_decision_sha256=parent_decision,
        parent_request_sha256=_sha256(run_root / "gate0/booking_request.json"),
        decision="REJECTED" if failure == "rejected" else "PROMOTABLE",
        signer_principal=signer,
        domain_stage=domain_stage,
        issued_at=issued_at,
        expires_at=expires_at,
    )
    if failure == "tamper":
        payload = json.loads(approval.read_text(encoding="utf-8"))
        payload["decision"] = "REJECTED"
        module["write_json"](approval, payload)
    if failure == "wrong_key":
        _, passed_public_key = _write_key_pair(tmp_path / failure / "other", "other")
    if failure == "request_tamper":
        request_path = run_root / "preflight_request.json"
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request["tampered"] = True
        module["write_json"](request_path, request)
    calls: list[str] = []
    _install_fake_run_leg(module, calls)

    with pytest.raises(SystemExit):
        module["first_pair_phase"](
            run_root,
            approval,
            **_phase_kwargs(passed_public_key, tmp_path / failure / "ledger"),
        )

    assert calls == []
    assert not (run_root / "legs").exists()


def test_matching_attacker_signature_cannot_substitute_gate1_trust_anchor(
    tmp_path: Path,
) -> None:
    module = _module()
    run_root, _ = _prepare_run(module, tmp_path)
    attacker_private, attacker_public = _write_key_pair(tmp_path / "attacker", "attacker")
    approval = _write_signed_decision(
        module,
        tmp_path / "attacker-approval.json",
        private_key=attacker_private,
        public_key=attacker_public,
        stage="preflight",
        request_path=run_root / "preflight_request.json",
        parent_decision_sha256=_sha256(run_root / "gate0/permit.json"),
        parent_request_sha256=_sha256(run_root / "gate0/booking_request.json"),
    )
    calls: list[str] = []
    _install_fake_run_leg(module, calls)

    with pytest.raises(SystemExit, match="does not match Gate0 trust"):
        module["first_pair_phase"](
            run_root,
            approval,
            **_phase_kwargs(attacker_public, tmp_path / "ledger"),
        )

    assert calls == []
    assert not (tmp_path / "ledger").exists()


def test_signed_approval_replay_makes_zero_additional_run_leg_calls(tmp_path: Path) -> None:
    module = _module()
    run_root, gate0 = _prepare_run(module, tmp_path)
    private_key = gate0["gate1_private_key"]
    public_key = gate0["gate1_public_key"]
    ledger = tmp_path / "ledger"
    approval = _write_signed_decision(
        module,
        tmp_path / "preflight.json",
        private_key=private_key,
        public_key=public_key,
        stage="preflight",
        request_path=run_root / "preflight_request.json",
        parent_decision_sha256=_sha256(run_root / "gate0/permit.json"),
        parent_request_sha256=_sha256(run_root / "gate0/booking_request.json"),
    )
    calls: list[str] = []
    _install_fake_run_leg(module, calls)
    assert module["first_pair_phase"](run_root, approval, **_phase_kwargs(public_key, ledger)) == 0
    assert calls == ["a1", "b1"]
    module["_write_state"](run_root, "prepared")

    with pytest.raises(SystemExit, match="already consumed"):
        module["first_pair_phase"](run_root, approval, **_phase_kwargs(public_key, ledger))

    assert calls == ["a1", "b1"]


def test_concurrent_signed_approval_consumption_runs_at_most_one_pair(tmp_path: Path) -> None:
    module = _module()
    run_root, gate0 = _prepare_run(module, tmp_path)
    private_key = gate0["gate1_private_key"]
    public_key = gate0["gate1_public_key"]
    ledger = tmp_path / "ledger"
    approval = _write_signed_decision(
        module,
        tmp_path / "preflight.json",
        private_key=private_key,
        public_key=public_key,
        stage="preflight",
        request_path=run_root / "preflight_request.json",
        parent_decision_sha256=_sha256(run_root / "gate0/permit.json"),
        parent_request_sha256=_sha256(run_root / "gate0/booking_request.json"),
    )
    calls: list[str] = []
    _install_fake_run_leg(module, calls)
    barrier = threading.Barrier(2)
    production_verify = module["verify_signed_decision"]

    def synchronized_verify(*args, **kwargs):
        result = production_verify(*args, **kwargs)
        barrier.wait(timeout=5)
        return result

    module["verify_signed_decision"] = synchronized_verify

    def invoke():
        try:
            return module["first_pair_phase"](
                run_root, approval, **_phase_kwargs(public_key, ledger)
            )
        except SystemExit:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: invoke(), range(2)))

    assert sorted(outcomes, key=str) == [0, "rejected"]
    assert calls == ["a1", "b1"]
    assert len(list(module["GATE1_CONSUMPTION_ROOT"].glob("*.consumed.json"))) == 1


@pytest.mark.parametrize(
    ("invalid_leg", "expected_calls"),
    [("a1", ["a1"]), ("b1", ["a1", "b1"])],
)
def test_first_pair_stops_and_enters_repair_state_after_invalid_leg(
    tmp_path: Path,
    invalid_leg: str,
    expected_calls: list[str],
) -> None:
    module = _module()
    run_root, gate0 = _prepare_run(module, tmp_path / invalid_leg)
    private_key = gate0["gate1_private_key"]
    public_key = gate0["gate1_public_key"]
    approval = _write_signed_decision(
        module,
        tmp_path / invalid_leg / "preflight.json",
        private_key=private_key,
        public_key=public_key,
        stage="preflight",
        request_path=run_root / "preflight_request.json",
        parent_decision_sha256=_sha256(run_root / "gate0/permit.json"),
        parent_request_sha256=_sha256(run_root / "gate0/booking_request.json"),
    )
    calls: list[str] = []
    _install_fake_run_leg(module, calls, validity={invalid_leg: False})

    assert (
        module["first_pair_phase"](
            run_root,
            approval,
            **_phase_kwargs(public_key, tmp_path / invalid_leg / "ledger"),
        )
        == 1
    )

    assert calls == expected_calls
    assert not (run_root / "screen_request.json").exists()
    result = json.loads((run_root / "first_pair_result.json").read_text())
    state = json.loads((run_root / "executor_state.json").read_text())
    assert result["status"] == "first_pair_repair_needed"
    assert result["failed_leg"] == invalid_leg
    assert state["phase"] == "first_pair_repair_needed"


def test_second_pair_does_not_run_a2_after_invalid_b2(tmp_path: Path) -> None:
    module = _module()
    run_root, gate0 = _prepare_run(module, tmp_path)
    private_key = gate0["gate1_private_key"]
    public_key = gate0["gate1_public_key"]
    ledger = tmp_path / "ledger"
    preflight = _write_signed_decision(
        module,
        tmp_path / "preflight.json",
        private_key=private_key,
        public_key=public_key,
        stage="preflight",
        request_path=run_root / "preflight_request.json",
        parent_decision_sha256=_sha256(run_root / "gate0/permit.json"),
        parent_request_sha256=_sha256(run_root / "gate0/booking_request.json"),
    )
    calls: list[str] = []
    _install_fake_run_leg(module, calls)
    assert module["first_pair_phase"](run_root, preflight, **_phase_kwargs(public_key, ledger)) == 0
    screen = _write_signed_decision(
        module,
        tmp_path / "screen.json",
        private_key=private_key,
        public_key=public_key,
        stage="screen",
        request_path=run_root / "screen_request.json",
        parent_decision_sha256=_sha256(preflight),
        parent_request_sha256=_sha256(run_root / "preflight_request.json"),
    )
    _install_fake_run_leg(module, calls, validity={"b2": False})

    assert module["second_pair_phase"](run_root, screen, **_phase_kwargs(public_key, ledger)) == 1

    assert calls == ["a1", "b1", "b2"]
    result = json.loads((run_root / "second_pair_result.json").read_text())
    state = json.loads((run_root / "executor_state.json").read_text())
    assert result["status"] == "second_pair_repair_needed"
    assert result["not_run"] == ["a2"]
    assert state["phase"] == "second_pair_repair_needed"


def test_first_pair_deadline_stops_before_b1(tmp_path: Path) -> None:
    module = _module()
    calls: list[str] = []
    _install_fake_run_leg(module, calls)

    legs, complete = module["_run_pair_sequential"](
        tmp_path / "run",
        leg_ids=("a1", "b1"),
        result_name="first_pair_result.json",
        complete_status="first_pair_complete",
        repair_state="first_pair_repair_needed",
        approval_sha256="a" * 64,
        request_sha256="b" * 64,
        authorization_start_deadline_utc=module["_utc_now"]() - timedelta(seconds=1),
        run_completion_deadline_utc=module["_utc_now"]() - timedelta(seconds=1),
    )

    assert complete is False
    assert calls == []
    assert legs == []
    result = json.loads((tmp_path / "run/first_pair_result.json").read_text())
    assert result["status"] == "first_pair_repair_needed"


def test_second_pair_start_deadline_does_not_limit_leg_completion(tmp_path: Path) -> None:
    module = _module()
    deadline = datetime(2026, 7, 10, 14, 0, tzinfo=timezone.utc)
    clock = iter(
        [
            deadline - timedelta(microseconds=1),
            deadline,
        ]
    )
    module["_utc_now"] = lambda: next(clock)
    calls: list[str] = []
    completion_deadlines: list[datetime | None] = []

    def fake_run_leg(spec, root, *, deadline_utc=None):
        del root
        calls.append(spec.leg_id)
        completion_deadlines.append(deadline_utc)
        return {"leg_id": spec.leg_id, "valid": True}

    module["run_leg"] = fake_run_leg
    legs, complete = module["_run_pair_sequential"](
        tmp_path / "run",
        leg_ids=("b2", "a2"),
        result_name="second_pair_result.json",
        complete_status="second_pair_complete",
        repair_state="second_pair_repair_needed",
        approval_sha256="a" * 64,
        request_sha256="b" * 64,
        authorization_start_deadline_utc=deadline,
    )

    assert complete is False
    assert calls == ["b2"]
    assert completion_deadlines == [None]
    assert legs == [{"leg_id": "b2", "valid": True}]
    result = json.loads((tmp_path / "run/second_pair_result.json").read_text())
    assert result["failed_leg"] == "a2"
    assert "deadline reached before a2 execution start" in result["execution_error"]


def test_second_pair_deadline_is_rechecked_before_approval_consumption(
    tmp_path: Path,
) -> None:
    module = _module()
    run_root, gate0 = _prepare_run(module, tmp_path)
    private_key = gate0["gate1_private_key"]
    public_key = gate0["gate1_public_key"]
    calls: list[str] = []
    _install_fake_run_leg(module, calls)
    preflight = _write_signed_decision(
        module,
        tmp_path / "preflight.json",
        private_key=private_key,
        public_key=public_key,
        stage="preflight",
        request_path=run_root / "preflight_request.json",
        parent_decision_sha256=_sha256(run_root / "gate0/permit.json"),
        parent_request_sha256=_sha256(run_root / "gate0/booking_request.json"),
    )
    assert (
        module["first_pair_phase"](
            run_root,
            preflight,
            **_phase_kwargs(public_key),
        )
        == 0
    )
    request_path = run_root / "screen_request.json"
    screen = _write_signed_decision(
        module,
        tmp_path / "screen.json",
        private_key=private_key,
        public_key=public_key,
        stage="screen",
        request_path=request_path,
        parent_decision_sha256=_sha256(preflight),
        parent_request_sha256=_sha256(run_root / "preflight_request.json"),
    )
    request = json.loads(request_path.read_text(encoding="utf-8"))
    deadline = datetime.fromisoformat(
        request["gate0"]["first_pair_deadline_at"].replace("Z", "+00:00")
    )
    consumed_before = sorted(module["GATE1_CONSUMPTION_ROOT"].glob("*.consumed.json"))
    module["_utc_now"] = lambda: deadline

    with pytest.raises(SystemExit, match="deadline reached before approval consumption"):
        module["_verify_consume_and_preserve_approval"](
            approval_path=screen,
            public_key_path=public_key,
            destination=run_root / "approvals/screen.json",
            expected_stage=module["Stage"].SCREEN,
            expected_sentry_principal=SENTRY_PRINCIPAL,
            expected_executor_principal=EXECUTOR_PRINCIPAL,
            expected_request_sha256=_sha256(request_path),
            expected_parent_decision_sha256=_sha256(preflight),
            expected_parent_request_sha256=_sha256(run_root / "preflight_request.json"),
            expected_public_key_sha256=_sha256(public_key),
            request_path=request_path,
            run_root=run_root,
            consumed_phase="second_pair_authorized",
            authorization_deadline_utc=deadline,
        )

    assert calls == ["a1", "b1"]
    assert not (run_root / "approvals/screen.json").exists()
    assert sorted(module["GATE1_CONSUMPTION_ROOT"].glob("*.consumed.json")) == consumed_before


def test_gate0_launch_start_must_be_inside_permit_interval(tmp_path: Path) -> None:
    module = _module()
    gate0 = _write_gate0_chain(tmp_path / "gate0")
    module["_utc_now"] = lambda: datetime(2030, 1, 1, tzinfo=timezone.utc)

    accepted = module["_validate_gate0_chain"](gate0)
    assert accepted["allocation_started_at"]

    permit = json.loads(gate0["permit"].read_text(encoding="utf-8"))["payload"]
    expires_at = datetime.fromisoformat(permit["expires_at"].replace("Z", "+00:00"))
    receipt = json.loads(gate0["launch_receipt"].read_text(encoding="utf-8"))
    receipt["execution"]["started_at"] = permit["expires_at"]
    receipt["execution"]["finished_at"] = (expires_at + timedelta(seconds=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    module["write_json"](gate0["launch_receipt"], receipt)

    with pytest.raises(RuntimeError, match="did not start within the permit validity interval"):
        module["_validate_gate0_chain"](gate0)


def test_gate0_schedule_and_budget_bindings_fail_closed(tmp_path: Path) -> None:
    module = _module()
    gate0 = _write_gate0_chain(tmp_path / "gate0")
    provider = json.loads(gate0["provider_output"].read_text(encoding="utf-8"))
    provider["schedule"]["server_removal_scheduled_at"] = "2026-07-10T14:00:01Z"
    module["write_json"](gate0["provider_output"], provider)
    receipt = json.loads(gate0["launch_receipt"].read_text(encoding="utf-8"))
    receipt["provider_output"]["sha256"] = _sha256(gate0["provider_output"])
    receipt["provider_output"]["size_bytes"] = gate0["provider_output"].stat().st_size
    module["write_json"](gate0["launch_receipt"], receipt)

    with pytest.raises(RuntimeError, match="schedule or TTL"):
        module["_validate_gate0_chain"](gate0)

    provider["schedule"]["server_removal_scheduled_at"] = provider["schedule"]["termination_time"]
    module["write_json"](gate0["provider_output"], provider)
    receipt["provider_output"]["sha256"] = _sha256(gate0["provider_output"])
    receipt["provider_output"]["size_bytes"] = gate0["provider_output"].stat().st_size
    receipt["budget"]["max_cost_usd"] = 35
    module["write_json"](gate0["launch_receipt"], receipt)
    with pytest.raises(RuntimeError, match="budget binding mismatch"):
        module["_validate_gate0_chain"](gate0)


def test_gate0_unique_allocation_reconciliation_fails_closed(tmp_path: Path) -> None:
    module = _module()
    gate0 = _write_gate0_chain(tmp_path / "gate0")
    provider = json.loads(gate0["provider_output"].read_text(encoding="utf-8"))
    provider["create_reconciliation"]["final_active_pod_ids"].append("pod-retry-leak")
    module["write_json"](gate0["provider_output"], provider)
    receipt = json.loads(gate0["launch_receipt"].read_text(encoding="utf-8"))
    receipt["provider_output"]["sha256"] = _sha256(gate0["provider_output"])
    receipt["provider_output"]["size_bytes"] = gate0["provider_output"].stat().st_size
    module["write_json"](gate0["launch_receipt"], receipt)

    with pytest.raises(RuntimeError, match="unique allocation reconciliation"):
        module["_validate_gate0_chain"](gate0)


def test_gate0_post_rent_availability_must_be_a_bounded_decrease(tmp_path: Path) -> None:
    module = _module()
    gate0 = _write_gate0_chain(tmp_path / "gate0")
    provider = json.loads(gate0["provider_output"].read_text(encoding="utf-8"))
    provider["executor"]["rent_boundary"]["after_post"]["available_gpu_count"] = 9
    module["write_json"](gate0["provider_output"], provider)
    receipt = json.loads(gate0["launch_receipt"].read_text(encoding="utf-8"))
    receipt["provider_output"]["sha256"] = _sha256(gate0["provider_output"])
    receipt["provider_output"]["size_bytes"] = gate0["provider_output"].stat().st_size
    module["write_json"](gate0["launch_receipt"], receipt)

    with pytest.raises(RuntimeError, match="rent boundary is invalid"):
        module["_validate_gate0_chain"](gate0)


@pytest.mark.parametrize("invalid_availability", [8.0, "8", True, -1, 9])
def test_gate0_pre_rent_availability_requires_a_genuine_exact_integer(
    tmp_path: Path,
    invalid_availability: object,
) -> None:
    module = _module()
    gate0 = _write_gate0_chain(tmp_path / "gate0")
    provider = json.loads(gate0["provider_output"].read_text(encoding="utf-8"))
    provider["executor"]["rate_evidence"]["available_gpu_count"] = invalid_availability
    provider["executor"]["rent_boundary"]["before_post"][
        "available_gpu_count"
    ] = invalid_availability
    module["write_json"](gate0["provider_output"], provider)
    receipt = json.loads(gate0["launch_receipt"].read_text(encoding="utf-8"))
    receipt["provider_output"]["sha256"] = _sha256(gate0["provider_output"])
    receipt["provider_output"]["size_bytes"] = gate0["provider_output"].stat().st_size
    module["write_json"](gate0["launch_receipt"], receipt)

    with pytest.raises(RuntimeError, match="rate authority is invalid"):
        module["_validate_gate0_chain"](gate0)


@pytest.mark.parametrize("invalid_gpu_count", [8.0, "8", True])
def test_gate0_top_level_gpu_count_requires_a_genuine_integer(
    tmp_path: Path,
    invalid_gpu_count: object,
) -> None:
    module = _module()
    gate0 = _write_gate0_chain(tmp_path / "gate0")
    provider = json.loads(gate0["provider_output"].read_text(encoding="utf-8"))
    provider["executor"]["gpu_count"] = invalid_gpu_count
    module["write_json"](gate0["provider_output"], provider)
    receipt = json.loads(gate0["launch_receipt"].read_text(encoding="utf-8"))
    receipt["provider_output"]["sha256"] = _sha256(gate0["provider_output"])
    receipt["provider_output"]["size_bytes"] = gate0["provider_output"].stat().st_size
    module["write_json"](gate0["launch_receipt"], receipt)

    with pytest.raises(RuntimeError, match="running 8x H100 allocation"):
        module["_validate_gate0_chain"](gate0)


@pytest.mark.parametrize("mutation", ["observed-rate", "max-cap"])
def test_gate0_provider_rate_and_cap_must_match_the_signed_permit(
    tmp_path: Path,
    mutation: str,
) -> None:
    module = _module()
    gate0 = _write_gate0_chain(tmp_path / "gate0")
    provider = json.loads(gate0["provider_output"].read_text(encoding="utf-8"))
    executor = provider["executor"]
    if mutation == "max-cap":
        executor["max_rate_usd_per_hour"] = 100.0
    else:
        executor["observed_rate_usd_per_hour"] = 16.0
        executor["observed_rate_usd_per_gpu_hour"] = 2.0
        executor["rate_evidence"]["price_per_gpu"] = 2.0
        executor["rate_evidence"]["price_per_hour"] = 16.0
        executor["rent_boundary"]["before_post"]["price_per_gpu"] = 2.0
        executor["rent_boundary"]["before_post"]["price_per_hour"] = 16.0
        executor["rent_boundary"]["after_post"]["price_per_gpu"] = 2.0
        executor["rent_boundary"]["after_post"]["price_per_hour"] = 16.0
    module["write_json"](gate0["provider_output"], provider)
    receipt = json.loads(gate0["launch_receipt"].read_text(encoding="utf-8"))
    receipt["provider_output"]["sha256"] = _sha256(gate0["provider_output"])
    receipt["provider_output"]["size_bytes"] = gate0["provider_output"].stat().st_size
    module["write_json"](gate0["launch_receipt"], receipt)

    with pytest.raises(RuntimeError, match="rate authority is invalid"):
        module["_validate_gate0_chain"](gate0)


def test_gate0_ssh_public_key_binding_fails_closed(tmp_path: Path) -> None:
    module = _module()
    gate0 = _write_gate0_chain(tmp_path / "gate0")
    provider = json.loads(gate0["provider_output"].read_text(encoding="utf-8"))
    provider["access"]["ssh_public_key_sha256"] = "f" * 64
    module["write_json"](gate0["provider_output"], provider)
    receipt = json.loads(gate0["launch_receipt"].read_text(encoding="utf-8"))
    receipt["provider_output"]["sha256"] = _sha256(gate0["provider_output"])
    receipt["provider_output"]["size_bytes"] = gate0["provider_output"].stat().st_size
    module["write_json"](gate0["launch_receipt"], receipt)

    with pytest.raises(RuntimeError, match="SSH public-key binding mismatch"):
        module["_validate_gate0_chain"](gate0)


def test_telemetry_samples_full_fields_throughout_lifecycle(tmp_path: Path) -> None:
    module = _module()
    rows = [
        {column: str(index) if column == "index" else "1" for column in module["TELEMETRY_COLUMNS"]}
        for index in range(8)
    ]
    monitor = module["TelemetryMonitor"](
        tmp_path / "gpu_telemetry.csv",
        query=lambda: (rows, None),
        interval_s=60,
    )
    monitor.start()
    result = monitor.stop()

    assert result["ok"] is True
    assert result["sample_count"] == 2
    assert result["row_count"] == 16
    header = (tmp_path / "gpu_telemetry.csv").read_text().splitlines()[0]
    assert header.split(",") == list(module["TELEMETRY_COLUMNS"])


def test_receipt_evidence_binds_timing_and_budget_tranche(tmp_path: Path) -> None:
    module = _module()
    receipt = tmp_path / "run_receipt.txt"
    receipt.write_text(
        "status=success\ntiming_status=unverified\ntranche_id=stale\nrun_started_at_utc=stale\n",
        encoding="utf-8",
    )

    module["_append_receipt_evidence"](
        receipt,
        tranche_id="T1",
        run_started_at_utc="2026-07-10T00:00:00.000Z",
        run_finished_at_utc="2026-07-10T00:01:00.000Z",
    )

    values = module["read_key_value"](receipt)
    assert values["status"] == "success"
    assert values["timing_status"] == "unverified"
    assert values["tranche_id"] == "T1"
    assert values["run_started_at_utc"] == "2026-07-10T00:00:00.000Z"
    assert values["run_finished_at_utc"] == "2026-07-10T00:01:00.000Z"
    assert receipt.read_text().count("tranche_id=") == 1


def test_wandb_readback_requires_authenticated_remote_artifact_hashes(
    tmp_path: Path,
) -> None:
    module = _module()
    stage = tmp_path / "stage"
    stage.mkdir()
    run_id = "dispatcher-abba-a1"
    evidence = stage / f"{run_id}.evidence_summary.json"
    manifest = stage / f"{run_id}.artifact_manifest.json"
    evidence.write_text('{"timing_status":"verified"}\n', encoding="utf-8")
    manifest.write_text('{"files":[]}\n', encoding="utf-8")
    controlled = {
        "MILES_WANDB_PROJECT": "glm47-pie-cpp-posttraining",
        "MILES_WANDB_RUN_ID": run_id,
        "W8_EXPERIMENT_ID": "issue32-t1",
        "MILES_WANDB_JOB_TYPE": "dispatcher-abba",
    }
    remote = {
        "run_id": run_id,
        "state": "finished",
        "summary": {
            "timing_status": "verified",
            "experiment_id": "issue32-t1",
            "stage": "dispatcher-abba",
            "status": "success",
        },
        "config": {"timing_status": "verified", "experiment_id": "issue32-t1"},
        "matching_artifacts": [
            {
                "name": "issue32-t1-dispatcher-abba-run:v0",
                "digest": "remote-digest",
                "metadata": {"timing_status": "verified"},
                "downloaded_files": {
                    evidence.name: module["_sha256"](evidence),
                    manifest.name: module["_sha256"](manifest),
                },
            }
        ],
    }

    def fake_capture(command, **kwargs):
        assert kwargs["timeout"] == 120
        return {
            "returncode": 0,
            "stdout": "W8_WANDB_READBACK=" + json.dumps(remote) + "\n",
            "stderr": "",
        }

    module["_run_capture"] = fake_capture
    result = module["collect_wandb_readback"](
        stage,
        controlled,
        {"WANDB_ENTITY": "ahm-rimer", "WANDB_API_KEY": "secret"},
    )
    assert result["ok"] is True
    assert result["authenticated_api_read"] is True

    remote["matching_artifacts"][0]["downloaded_files"][manifest.name] = "0" * 64
    tampered = module["collect_wandb_readback"](
        stage,
        controlled,
        {"WANDB_ENTITY": "ahm-rimer", "WANDB_API_KEY": "secret"},
    )
    assert tampered["ok"] is False
    assert "wandb_remote_artifact_manifest_hash_mismatch" in tampered["errors"]


def test_telemetry_stop_fails_if_monitor_thread_remains_alive(tmp_path: Path) -> None:
    module = _module()
    monitor = module["TelemetryMonitor"](
        tmp_path / "gpu_telemetry.csv",
        query=lambda: ([], "must_not_sample"),
    )
    monitor.sample_count = 1

    class StuckThread:
        def join(self, timeout):
            assert timeout >= 5

        def is_alive(self):
            return True

    monitor.thread = StuckThread()
    result = monitor.stop()

    assert result["ok"] is False
    assert "telemetry_thread_did_not_stop" in result["errors"]
    assert "must_not_sample" not in result["errors"]


def test_run_leg_cleans_up_after_launcher_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _module()
    run_root = tmp_path / "run"
    module["write_json"](run_root / "budget.json", {"tranche_id": "T1"})
    leg_root = run_root / "legs/01_a1"
    controlled = {"MILES_RUN_ROOT": str(leg_root)}
    module["controlled_leg_config"] = lambda spec, root: controlled
    module["build_subprocess_env"] = lambda values: {}
    ray_calls: list[str] = []
    module["_ray_stop"] = lambda env: ray_calls.append("stop") or {"ok": True}
    module["nvlink_snapshot"] = lambda: {"supported": True}
    process_calls: list[str] = []

    def clean_process_inventory():
        process_calls.append("inventory")
        return {
            "schema": "h100-process-cleanliness/v1",
            "ok": True,
            "errors": [],
            "gpu_process_inventory": [],
            "relevant_processes": [],
        }

    module["collect_process_cleanliness"] = clean_process_inventory

    class FakeMonitor:
        def __init__(self, path):
            self.path = path
            self.sample_count = 1
            self.row_count = 8
            self.stopped = False

        def start(self):
            self.path.parent.mkdir(parents=True, exist_ok=True)

        def stop(self):
            self.stopped = True
            return {"ok": True, "sample_count": 2, "row_count": 16, "errors": []}

    monitor_holder = {}

    def fake_monitor(path):
        monitor_holder["monitor"] = FakeMonitor(path)
        return monitor_holder["monitor"]

    module["TelemetryMonitor"] = fake_monitor

    def fail_launch(*args, **kwargs):
        raise OSError("synthetic launch failure")

    monkeypatch.setattr(module["subprocess"], "run", fail_launch)

    with pytest.raises(OSError, match="synthetic launch failure"):
        module["run_leg"](module["LEG_SPECS"]["a1"], run_root)

    assert monitor_holder["monitor"].stopped is True
    assert ray_calls == ["stop", "stop"]
    assert process_calls == ["inventory", "inventory"]
    assert (leg_root / "process_cleanliness_before.json").is_file()
    assert (leg_root / "process_cleanliness_after.json").is_file()
    receipt = module["read_key_value"](leg_root / "sft_lora_r16/run_receipt.txt")
    assert receipt["tranche_id"] == "T1"
    assert receipt["run_started_at_utc"]
    assert receipt["run_finished_at_utc"]


def test_wandb_auth_is_online_and_redacts_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _module()
    captured = {}
    monkeypatch.setenv("WANDB_API_KEY", "top-secret")

    def fake_capture(command, **kwargs):
        captured["env"] = kwargs["env"]
        return {
            "returncode": 0,
            "stdout": "wandb_authenticated_read_ok\n",
            "stderr": "top-secret",
        }

    module["_run_capture"] = fake_capture
    receipt = module["check_wandb_authenticated_read"]()

    assert captured["env"]["WANDB_MODE"] == "online"
    assert receipt["ok"] is True
    assert "top-secret" not in json.dumps(receipt)


def test_canonical_and_two_warmup_artifacts_are_interoperable(tmp_path: Path) -> None:
    module = _module()
    log = tmp_path / "run.log"
    receipt = tmp_path / "run_receipt.txt"
    lines = []
    for step, tokens in enumerate(module["EXPECTED_RAW_TOKEN_SIGNATURE"]):
        tok_s = 7000.0
        actor_time = tokens / tok_s
        lines.append(
            f"train_metric_utils.py:50 - perf {step}: "
            f"{{'perf/actor_train_time': {actor_time}, "
            "'perf/actor_train_tflops': 22.0, "
            f"'perf/actor_train_tok_per_s': {tok_s}, "
            f"'perf/step_time': {actor_time + 8.0}, 'perf/wait_time_ratio': 0.3}}"
        )
        lines.append(
            f"log_utils.py:463 - step {step}: {{'train/loss': 0.25, 'train/grad_norm': 0.3}}"
        )
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    receipt.write_text(
        "status=success\nray_status=0\ntiming_status=verified\n",
        encoding="utf-8",
    )
    canonical = module["summarize_miles_mfu_trial"](
        log_path=log,
        receipt_path=receipt,
        round_number=1,
        name="a1",
    )
    path = module["write_trial_summary"](tmp_path / "trial_summary.json", canonical)
    supplementary, records = module["summarize_two_warmup"](
        module["LEG_SPECS"]["a1"],
        log,
        receipt,
        launcher_exit_code=0,
        pre_cleanup={"ok": True},
        post_cleanup={"ok": True},
        pre_process_cleanliness={"ok": True},
        post_process_cleanliness={"ok": True},
        telemetry={"ok": True},
    )

    assert json.loads(path.read_text())["accepted"] is True
    assert supplementary["valid"] is True
    assert supplementary["measured_step_count"] == 14
    assert len(records) == 16


def test_process_cleanliness_records_gpu_and_training_survivors() -> None:
    module = _module()

    def fake_capture(command, **kwargs):
        del kwargs
        if command[0] == "nvidia-smi":
            return {
                "returncode": 0,
                "stdout": "4321, python3, 1234\n",
                "stderr": "",
            }
        return {
            "returncode": 0,
            "stdout": (
                " 4321 Wed Jul 10 12:34:56 2026 python3 actor_train.py\n"
                " 9876 Wed Jul 10 12:35:01 2026 raylet --node-ip-address=127.0.0.1\n"
            ),
            "stderr": "",
        }

    module["_run_capture"] = fake_capture
    receipt = module["collect_process_cleanliness"]()

    assert receipt["ok"] is False
    assert receipt["errors"] == ["surviving_relevant_processes"]
    assert [row["pid"] for row in receipt["relevant_processes"]] == [4321, 9876]
    assert receipt["relevant_processes"][0]["start_time"] == "Wed Jul 10 12:34:56 2026"


def test_process_survivor_invalidates_leg_evidence_and_stops_next_leg(tmp_path: Path) -> None:
    module = _module()
    log, receipt, _ = _write_leg_fixture(
        tmp_path / "fixture",
        module,
        module["LEG_SPECS"]["a1"],
    )
    summary, _ = module["summarize_two_warmup"](
        module["LEG_SPECS"]["a1"],
        log,
        receipt,
        launcher_exit_code=0,
        pre_cleanup={"ok": True},
        post_cleanup={"ok": True},
        pre_process_cleanliness={"ok": True},
        post_process_cleanliness={
            "ok": False,
            "errors": ["surviving_relevant_processes"],
            "relevant_processes": [{"pid": 4321, "args": "raylet"}],
        },
        telemetry={"ok": True},
    )
    assert summary["valid"] is False
    assert "post_leg_process_cleanliness_failed" in summary["rejection_reasons"]

    calls: list[str] = []

    def fake_run_leg(spec, run_root, *, deadline_utc=None):
        del run_root
        del deadline_utc
        calls.append(spec.leg_id)
        return {
            "leg_id": spec.leg_id,
            "valid": False,
            "process_cleanliness_after": {
                "ok": False,
                "errors": ["surviving_relevant_processes"],
            },
        }

    module["run_leg"] = fake_run_leg
    legs, complete = module["_run_pair_sequential"](
        tmp_path / "run",
        leg_ids=("a1", "b1"),
        result_name="first_pair_result.json",
        complete_status="first_pair_complete",
        repair_state="first_pair_repair_needed",
        approval_sha256="a" * 64,
        request_sha256="b" * 64,
    )

    assert complete is False
    assert calls == ["a1"]
    assert legs[0]["valid"] is False
    result = json.loads((tmp_path / "run/first_pair_result.json").read_text())
    assert result["not_run"] == ["b1"]
    assert result["repair_required"] is True


def test_source_provenance_enforces_clean_ancestor_and_allowlist() -> None:
    module = _module()
    head = "a" * 40
    allowed = ["scripts/run_miles_h100_dispatcher_abba.py"]
    module["load_acceptance_contract"] = lambda: {
        "source_pins": {
            "training_base_sha": module["TRAINING_BASE_SHA"],
            "allowed_paths_since_training_base": allowed,
        }
    }

    def git_output(args):
        if args[:2] == ["status", "--porcelain"]:
            return {"returncode": 0, "stdout": "", "stderr": ""}
        if args[:2] == ["rev-parse", "HEAD"]:
            return {"returncode": 0, "stdout": head + "\n", "stderr": ""}
        if args[0] == "merge-base":
            return {"returncode": 0, "stdout": "", "stderr": ""}
        return {"returncode": 0, "stdout": allowed[0] + "\n", "stderr": ""}

    module["_git_output"] = git_output
    provenance = module["collect_source_provenance"]()

    assert provenance["ok"] is True
    assert provenance["repo_sha"] == head
    assert provenance["training_base_sha"] == module["TRAINING_BASE_SHA"]
