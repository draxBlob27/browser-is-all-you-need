from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import sys
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from w8_biayn.integrations.h100_research_sentry import (
    AUDIT_DECISION_DOMAIN,
    BOOKING_REQUEST_SCHEMA,
    T2_AUTHORIZATION_DOMAIN,
    DecisionReplayError,
    DecisionSecurityError,
    SentrySecurity,
    SentryPolicy,
    Stage,
    evaluate_confirmation,
    evaluate_final,
    evaluate_grpo,
    evaluate_preflight,
    evaluate_promotion,
    evaluate_screen,
    main,
    sign_bounded_payload,
    signature_domain_for_kind,
    verify_consume_and_execute,
    verify_signed_decision,
    _validate_runner_evidence_manifest,
    _telemetry_evidence,
)
from w8_biayn.integrations.h100_signed_approval import (
    CREDENTIAL_TRANSPORT,
    ENVELOPE_SCHEMA,
    LAUNCH_RECEIPT_SCHEMA,
    PERMIT_SCHEMA,
    PUBLIC_KEY_SCHEMA,
    SIGNATURE_DOMAIN,
    domain_separated_message,
    key_id_for_public_key,
    load_public_key_document,
)
from w8_biayn.integrations.miles_mfu import (
    summarize_miles_mfu_trial,
    write_trial_summary,
)


TRAINING_BASE_SHA = "cd83e3c8780f09e38e5b58558d84580e74afbcf6"
CURRENT_REPO_SHA = "f" * 40
MILES_SHA = "01a6d7bb74befa6e97579c80a2b1add0667606f3"
MEGATRON_SHA = "79fc0894d0ba57acd10a9c0da507abd1dfef3bdf"
CLAIM = "fastest tested configuration on the pinned 8x H100 stack and declared search space"
RUNNER_SCRIPT = Path(__file__).parents[1] / "scripts/run_miles_h100_dispatcher_abba.py"
TEST_NOW = datetime(2026, 7, 10, 0, 5, tzinfo=timezone.utc)


def _write_test_key(root: Path, name: str) -> tuple[Path, Path]:
    private_path = root / "keys" / f"{name}.pem"
    public_path = root / "keys" / f"{name}.public.json"
    if private_path.is_file() and public_path.is_file():
        return private_path, public_path
    private_path.parent.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
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
    _json(
        public_path,
        {
            "schema": PUBLIC_KEY_SCHEMA,
            "algorithm": "Ed25519",
            "key_id": key_id_for_public_key(public_raw),
            "public_key_base64": base64.b64encode(public_raw).decode("ascii"),
        },
    )
    return private_path, public_path


def _test_security(root: Path) -> SentrySecurity:
    sentry_private, sentry_public = _write_test_key(root, "sentry")
    _, supervisor_public = _write_test_key(root, "supervisor")
    _, auditor_public = _write_test_key(root, "auditor")
    return SentrySecurity(
        signing_private_key_path=sentry_private,
        sentry_public_key_path=sentry_public,
        sentry_principal="research-sentry",
        executor_principal="h100-runner",
        supervisor_public_key_path=supervisor_public,
        supervisor_principal="research-supervisor",
        auditor_public_key_path=auditor_public,
        auditor_principal="independent-auditor",
        now=TEST_NOW,
    )


def _test_private_key(root: Path, name: str) -> Path:
    private, _ = _write_test_key(root, name)
    return private


def _copy_test_keys(source: Path, destination: Path) -> None:
    target = destination / "keys"
    target.mkdir(parents=True, exist_ok=True)
    for path in (source / "keys").iterdir():
        copied = target / path.name
        copied.write_bytes(path.read_bytes())
        if copied.suffix == ".pem":
            copied.chmod(0o600)


def _json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_gate0_chain(
    root: Path,
    security: SentrySecurity,
    *,
    now: datetime = TEST_NOW,
) -> dict[str, Path]:
    issued_at = now.astimezone(timezone.utc).replace(microsecond=0) - timedelta(minutes=1)
    expires_at = issued_at + timedelta(minutes=10)
    consumed_at = issued_at + timedelta(seconds=30)
    contract_path = Path(__file__).parents[1] / "examples/miles/h100_fastest_acceptance.json"
    contract_payload = json.loads(contract_path.read_text(encoding="utf-8"))
    gate0_private_path, gate0_public_path = _write_test_key(root, "gate0")
    gate0_public_document = json.loads(gate0_public_path.read_text(encoding="utf-8"))
    gate1_public_document = json.loads(
        Path(security.sentry_public_key_path).read_text(encoding="utf-8")
    )
    intent_root = root / "gate0/intent"
    intent_payloads = {
        "source": {
            "schema": "h100-booking-source-intent/v1",
            "repo_sha": CURRENT_REPO_SHA,
            "training_base_sha": TRAINING_BASE_SHA,
            "acceptance_contract_sha256": _sha256(contract_path),
        },
        "runtime": {
            "schema": "h100-booking-runtime-intent/v1",
            "miles_sha": MILES_SHA,
            "megatron_sha": MEGATRON_SHA,
            "runtime_pins": contract_payload["runtime_pins"],
        },
        "data": {
            "schema": "h100-booking-data-intent/v1",
            "train_sha256": contract_payload["fixed_workload"]["dataset_sha256"],
            "manifest_sha256": contract_payload["fixed_workload"][
                "dataset_manifest_sha256"
            ],
            "row_count": contract_payload["fixed_workload"]["dataset_rows"],
        },
        "checkpoint": {
            "schema": "h100-booking-checkpoint-intent/v1",
            "root": "/root/models/GLM-4.7-Flash_torch_dist_tp4_pp1_ep8",
            "layout": "TP4/PP1/EP8/ETP1",
            "hf_model": contract_payload["runtime_pins"]["hf_model"],
            "hf_revision": contract_payload["runtime_pins"]["hf_revision"],
        },
    }
    intent_paths = {
        name: _json(intent_root / f"{name}.json", payload)
        for name, payload in intent_payloads.items()
    }
    budget = {
        "ttl_seconds": 7200,
        "max_cost_usd": "36",
        "max_node_hourly_rate_usd": "18",
        "observed_node_hourly_rate_usd": "18",
        "observed_node_hourly_rate_status": "provider_reported_nonzero",
        "max_node_hours": "2",
    }
    booking = _json(
        root / "gate0/booking_request.json",
        {
            "schema": BOOKING_REQUEST_SCHEMA,
            "issue_number": 32,
            "allocation_name": "issue-32-dispatcher",
            "provider": "lium",
            "provider_version": "1.2.0",
            "profile": "h100-sxm",
            "executor_id": "golden-shark-c6",
            "sentry_principal": security.sentry_principal,
            "executor_principal": security.executor_principal,
            "gate1_trust": {
                "public_key_sha256": _sha256(Path(security.sentry_public_key_path)),
                "key_id": gate1_public_document["key_id"],
                "sentry_principal": security.sentry_principal,
                "executor_principal": security.executor_principal,
            },
            "hardware": {"gpu_type": "H100", "gpu_count": 8},
            "budget": budget,
            "intent_artifacts": {
                name: {"path": str(path.resolve()), "sha256": _sha256(path)}
                for name, path in intent_paths.items()
            },
        },
    )
    interpreter = Path(sys.executable).resolve()
    provider_executable = root / "gate0/lium_create_h100_pod.py"
    provider_executable.write_text(f"#!{interpreter}\n", encoding="utf-8")
    provider_executable.chmod(0o755)
    lium_cli = root / "gate0/lium"
    lium_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    lium_cli.chmod(0o755)
    ssh_public_key = root / "gate0/id_ed25519.pub"
    ssh_public_key.write_text("ssh-ed25519 AAAATEST sentry-test\n", encoding="utf-8")
    template = {
        "template_id": "template-h100",
        "template_image": "daturaai/pytorch",
        "template_tag": "2.12.0",
        "template_status": "VERIFY_SUCCESS",
    }
    argv = [
        str(provider_executable.resolve()),
        "up",
        "golden-shark-c6",
        "--ttl",
        "2h",
        "--name",
        "issue-32-dispatcher",
        "--yes",
        "--template-id",
        template["template_id"],
        "--template-image",
        template["template_image"],
        "--template-tag",
        template["template_tag"],
        "--template-status",
        template["template_status"],
        "--expected-provider-version",
        "1.2.0",
        "--expected-interpreter-path",
        str(interpreter),
        "--expected-interpreter-sha256",
        _sha256(interpreter),
        "--expected-interpreter-version",
        platform.python_version(),
        "--expected-lium-sdk-version",
        "1.2.3",
        "--expected-lium-cli-path",
        str(lium_cli.resolve()),
        "--expected-lium-cli-sha256",
        _sha256(lium_cli),
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
    ]
    termination = (issued_at + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    provider_output = _json(
        root / "gate0/provider_output.json",
        {
            "schema": "lium-h100-pod-create/v1",
            "status": "RUNNING",
            "pod": {
                "id": "pod-h100-001",
                "name": "issue-32-dispatcher",
                "huid": "steady-host-42",
                "ssh_cmd": "ssh root@203.0.113.10 -p 2222",
            },
            "executor": {
                "id": "executor-h100-001",
                "huid": "golden-shark-c6",
                "gpu_count": 8,
                "gpu_type": "H100",
                "gpu_model": "NVIDIA H100 80GB HBM3",
                "observed_rate_usd_per_hour": 18.0,
                "observed_rate_usd_per_gpu_hour": 2.25,
                "max_rate_usd_per_hour": 18.0,
            },
            "template": {"id": "template-h100", "name": "Pytorch CUDA"},
            "access": {
                "ssh_public_key_path": str(ssh_public_key.resolve()),
                "ssh_public_key_sha256": _sha256(ssh_public_key),
            },
            "create_reconciliation": {
                "status": "CONFIRMED_UNIQUE",
                "rent_mutation_attempt_policy": "single-attempt-sdk-request-boundary/v1",
                "allocation_name": "issue-32-dispatcher",
                "pod_id": "pod-h100-001",
                "successful_snapshots": 2,
                "lookup_failures": 0,
                "final_active_pod_ids": ["pod-h100-001"],
                "observed_duplicate_pod_ids": [],
                "duplicate_cleanup_status": "NOT_REQUIRED",
            },
            "schedule": {
                "confirmed": True,
                "termination_time": termination,
                "server_removal_scheduled_at": termination,
                "verified_termination_time": termination,
                "ttl_seconds": 7200,
            },
            "poll": {"timeout_seconds": 240, "interval_seconds": 5},
        },
    )
    private = serialization.load_pem_private_key(gate0_private_path.read_bytes(), password=None)
    assert isinstance(private, Ed25519PrivateKey)
    permit_payload = {
        "schema": PERMIT_SCHEMA,
        "stage": "lium-booking",
        "decision": "PROMOTABLE",
        "request_id": "gate0-request-0001",
        "nonce": "1" * 64,
        "issued_at": issued_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": expires_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sentry_principal": security.sentry_principal,
        "executor_principal": security.executor_principal,
        "source_sha256": _sha256(intent_paths["source"]),
        "runtime_sha256": _sha256(intent_paths["runtime"]),
        "data_sha256": _sha256(intent_paths["data"]),
        "checkpoint_sha256": _sha256(intent_paths["checkpoint"]),
        "parent_request_sha256": _sha256(booking),
        "executor_id": "golden-shark-c6",
        "provider": "lium",
        "profile": "h100-sxm",
        "provider_executable": str(provider_executable.resolve()),
        "provider_executable_sha256": _sha256(provider_executable),
        "provider_version": "1.2.0",
        "provider_interpreter": str(interpreter),
        "provider_interpreter_sha256": _sha256(interpreter),
        "provider_interpreter_version": platform.python_version(),
        "lium_sdk_distribution": "lium.io",
        "lium_sdk_version": "1.2.3",
        "lium_cli_path": str(lium_cli.resolve()),
        "lium_cli_sha256": _sha256(lium_cli),
        "lium_cli_version": "0.0.3",
        "working_directory": str(root.resolve()),
        "environment": {},
        "credential_transport": CREDENTIAL_TRANSPORT,
        "ssh_public_key_path": str(ssh_public_key.resolve()),
        "ssh_public_key_sha256": _sha256(ssh_public_key),
        **template,
        "issue_number": 32,
        "allocation_name": "issue-32-dispatcher",
        "argv": argv,
        "gpu_type": "H100",
        "gpu_count": 8,
        **budget,
        "provider_timeout_seconds": 300,
    }
    permit = _json(
        root / "gate0/permit.json",
        {
            "schema": ENVELOPE_SCHEMA,
            "key_id": gate0_public_document["key_id"],
            "payload": permit_payload,
            "signature_base64": base64.b64encode(
                private.sign(domain_separated_message(SIGNATURE_DOMAIN, permit_payload))
            ).decode("ascii"),
        },
    )
    claim = _json(
        root / "gate0/claim.consumed.json",
        {
            "key_id": gate0_public_document["key_id"],
            "nonce": permit_payload["nonce"],
            "permit_sha256": _sha256(permit),
            "request_id": permit_payload["request_id"],
            "consumed_at": consumed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )
    receipt = _json(
        root / "gate0/launch_receipt.json",
        {
            "schema": LAUNCH_RECEIPT_SCHEMA,
            "status": "COMPLETED",
            "permit": {
                "path": str(permit),
                "sha256": _sha256(permit),
                "key_id": gate0_public_document["key_id"],
                "request_id": permit_payload["request_id"],
                "nonce": permit_payload["nonce"],
                "issued_at": permit_payload["issued_at"],
                "expires_at": permit_payload["expires_at"],
            },
            "claim": {
                "path": str(claim),
                "sha256": _sha256(claim),
                "consumed_at": consumed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            "parent_request": {"path": str(booking), "sha256": _sha256(booking)},
            "provider": {
                "name": "lium",
                "profile": "h100-sxm",
                "executor_id": "golden-shark-c6",
                "executable": str(provider_executable.resolve()),
                "executable_sha256": _sha256(provider_executable),
                "declared_version": "1.2.0",
                "interpreter": str(interpreter),
                "interpreter_sha256": _sha256(interpreter),
                "interpreter_version": platform.python_version(),
                "fd_loader_sha256": "0" * 64,
                "execution_boundary": "script-fd-bound-interpreter-path-rechecked",
            },
            "runtime_evidence": {
                "provider_version": "1.2.0",
                "lium_sdk_distribution": "lium.io",
                "lium_sdk_version": "1.2.3",
                "lium_cli_path": str(lium_cli.resolve()),
                "lium_cli_sha256": _sha256(lium_cli),
                "lium_cli_version": "0.0.3",
            },
            "template": {
                "id": template["template_id"],
                "image": template["template_image"],
                "tag": template["template_tag"],
                "status": template["template_status"],
            },
            "access": {
                "ssh_public_key_path": str(ssh_public_key.resolve()),
                "ssh_public_key_sha256": _sha256(ssh_public_key),
            },
            "provider_output": {
                "path": str(provider_output),
                "sha256": _sha256(provider_output),
                "size_bytes": provider_output.stat().st_size,
            },
            "allocation": {"issue_number": 32, "name": "issue-32-dispatcher"},
            "execution": {
                "cwd": str(root.resolve()),
                "argv": argv,
                "sanitized_environment_sha256": "0" * 64,
                "sanitized_environment_names": [],
                "credential_transport": CREDENTIAL_TRANSPORT,
                "started_at": issued_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "finished_at": consumed_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "exit_code": 0,
                "wrapper_exit_code": 0,
                "timed_out": False,
                "provider_timeout_seconds": 300,
            },
            "budget": budget,
        },
    )
    return {
        "permit": permit,
        "public_key": gate0_public_path,
        "launch_receipt": receipt,
        "booking_request": booking,
        "provider_output": provider_output,
        **{f"{name}_intent": path for name, path in intent_paths.items()},
    }


def _save_decision(path: Path, payload: dict[str, Any]) -> Path:
    return _json(path, payload)


def _write_preflight_inputs(root: Path) -> tuple[Path, Path, Path, Path]:
    contract_source = Path(__file__).parents[1] / "examples/miles/h100_fastest_acceptance.json"
    contract = root / "contract.json"
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_text(contract_source.read_text(encoding="utf-8"), encoding="utf-8")
    contract_payload = json.loads(contract.read_text(encoding="utf-8"))
    runtime_pins = contract_payload["runtime_pins"]
    topology = "\n".join(
        "\t".join([f"GPU{index}", *["X" if peer == index else "NV18" for peer in range(8)]])
        for index in range(8)
    )
    hardware = _json(
        root / "hardware.json",
        {
            "ok": True,
            "gpu_rows": [
                f"{index}, NVIDIA H100 80GB HBM3, 81559, 595.1, 0000:{index:02x}:00.0"
                for index in range(8)
            ],
            "gpu_operating_rows": [
                {
                    "timestamp": "2026/07/10 00:00:00.000",
                    "index": str(index),
                    "clocks.sm": "345",
                    "power.draw": "75",
                    "power.limit": "700",
                    "temperature.gpu": "30",
                    "clocks_throttle_reasons.active": "0x0000000000000000",
                    "utilization.gpu": "0",
                    "utilization.memory": "0",
                    "memory.used": "0",
                    "memory.total": "81559",
                }
                for index in range(8)
            ],
            "topology": topology,
            "repo_sha": CURRENT_REPO_SHA,
            "training_base_sha": TRAINING_BASE_SHA,
            "miles_sha": MILES_SHA,
            "megatron_sha": MEGATRON_SHA,
        },
    )
    budget = _json(
        root / "budget.json",
        {
            "provider": "Lium",
            "tranche_id": "T1",
            "accelerators": "8xH100-SXM-80GB",
            "hourly_rate_usd": 18.0,
            "planned_hours": 1.0,
            "unused_budget_transfer_allowed": False,
            "source_commit": CURRENT_REPO_SHA,
        },
    )
    source = _json(
        root / "receipts/source.json",
        {
            "schema_version": 1,
            "ok": True,
            "errors": [],
            "repo_sha": CURRENT_REPO_SHA,
            "training_base_sha": TRAINING_BASE_SHA,
            "training_base_is_ancestor": True,
            "worktree_clean": True,
            "changed_paths_since_training_base": [],
            "allowed_paths_since_training_base": [],
            "disallowed_paths": [],
        },
    )
    marker = root / "receipts/hf_revision_marker.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(runtime_pins["hf_revision"] + "\n", encoding="utf-8")
    image_id = "sha256:" + "a" * 64
    inspection = _json(
        root / "receipts/container_inspect.json",
        [
            {
                "Id": image_id,
                "RepoDigests": [runtime_pins["container_image"]],
                "Os": "linux",
                "Architecture": "amd64",
            }
        ],
    )
    image_digest = runtime_pins["container_image"].rsplit("@", 1)[1]
    attestation = _json(
        root / "receipts/setup_attestation.json",
        {
            "schema": "w8-h100-setup-attestation/v1",
            "created_at_utc": "2026-07-10T00:00:00Z",
            "hf_checkpoint_path": "/root/models/GLM-4.7-Flash",
            "hf_model": runtime_pins["hf_model"],
            "hf_revision": runtime_pins["hf_revision"],
            "hf_revision_marker_path": "/root/models/GLM-4.7-Flash/.w8-hf-revision",
            "hf_revision_marker_sha256": _sha256(marker),
            "container_image_reference": runtime_pins["container_image"],
            "container_image_digest": image_digest,
            "container_platform": runtime_pins["container_platform"],
            "container_image_id": image_id,
            "container_inspection_path": "/data/w8-biayn/control-plane/setup/issue32-t1-container-inspect.json",
            "container_inspection_sha256": _sha256(inspection),
        },
    )
    setup_bundle = {
        "attestation": json.loads(attestation.read_text(encoding="utf-8")),
        "attestation_sha256": _sha256(attestation),
        "hf_revision_marker_sha256": _sha256(marker),
        "hf_revision_marker_content": runtime_pins["hf_revision"],
        "container_inspection_sha256": _sha256(inspection),
        "container_inspection": json.loads(inspection.read_text(encoding="utf-8")),
    }
    setup_receipt_fields = {
        "hf_checkpoint_path": "/root/models/GLM-4.7-Flash",
        "hf_model": runtime_pins["hf_model"],
        "hf_revision": runtime_pins["hf_revision"],
        "hf_revision_marker_sha256": _sha256(marker),
        "container_image_reference": runtime_pins["container_image"],
        "container_image_digest": image_digest,
        "container_platform": runtime_pins["container_platform"],
        "container_image_id": image_id,
        "container_inspection_sha256": _sha256(inspection),
        "setup_attestation_sha256": _sha256(attestation),
    }
    immutable = {
        "protocol": _json(
            root / "protocol.json",
            {"schema_version": 2, "authority": "executor_evidence_only"},
        ),
        "source": source,
        "hardware": hardware,
        "checkpoint": _json(
            root / "receipts/checkpoint.json",
            {
                "schema_version": 2,
                "root": "/root/models/GLM-4.7-Flash_torch_dist_tp4_pp1_ep8",
                "layout": "TP4/PP1/EP8/ETP1",
                "tag": "release",
                "marker_sha256": "2" * 64,
                "metadata_path": "/root/models/GLM-4.7-Flash_torch_dist_tp4_pp1_ep8/release/.metadata",
                "metadata_sha256": "3" * 64,
                "metadata_size": 1024,
                **setup_receipt_fields,
            },
        ),
        "data": _json(
            root / "receipts/data.json",
            {
                "schema_version": 1,
                "path": "/data/glm47-pie-profile-long128-oracle-v2/sft/train.jsonl",
                "sha256": "f1f5f70b1e77dbb6da51d075a35b2e48f784f4080873f356c9c4bd3c83a3d783",
                "row_count": 128,
                "manifest_path": "/data/glm47-pie-profile-long128-oracle-v2/manifest.json",
                "manifest_sha256": "5d72f758320b4373b61d2008dadbbdf459eb8749c93d5c81b43a4f8415ce00a7",
            },
        ),
        "wandb_auth": _json(
            root / "receipts/wandb_auth.json",
            {"schema_version": 1, "ok": True, "authenticated_api_read": True},
        ),
        "runtime": _json(
            root / "receipts/runtime.json",
            {
                "schema_version": 2,
                "ok": True,
                "returncode": 0,
                "stdout": "ok",
                "stderr": "",
                **setup_receipt_fields,
            },
        ),
        "budget": budget,
    }
    input_hashes = {name: _sha256(path) for name, path in immutable.items()}
    manifest = _json(
        root / "prepare_manifest.json",
        {
            "schema_version": 1,
            "authority": "executor_prepare_evidence",
            "ok": True,
            "artifacts": {name: str(path) for name, path in immutable.items()},
            "sha256": input_hashes,
            "supporting_artifacts": {
                "setup_attestation": str(attestation),
                "hf_revision_marker": str(marker),
                "container_inspection": str(inspection),
            },
            "supporting_sha256": {
                "setup_attestation": _sha256(attestation),
                "hf_revision_marker": _sha256(marker),
                "container_inspection": _sha256(inspection),
            },
        },
    )
    request = _json(
        root / "preflight_request.json",
        {
            "schema_version": 1,
            "requested_stage": "preflight",
            "input_hashes": input_hashes,
            "prepare_manifest_sha256": _sha256(manifest),
            "source_identity": {
                "repo_sha": CURRENT_REPO_SHA,
                "training_base_sha": TRAINING_BASE_SHA,
            },
            "prepared_evidence": {
                "source": json.loads(source.read_text(encoding="utf-8")),
                "runtime": json.loads(immutable["runtime"].read_text(encoding="utf-8")),
                "data": json.loads(immutable["data"].read_text(encoding="utf-8")),
                "checkpoint": json.loads(
                    immutable["checkpoint"].read_text(encoding="utf-8")
                ),
                "setup": setup_bundle,
            },
        },
    )
    return contract, hardware, budget, request


def _refresh_prepare_bindings(root: Path) -> None:
    manifest_path = root / "prepare_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sha256"] = {name: _sha256(Path(path)) for name, path in manifest["artifacts"].items()}
    manifest["supporting_sha256"] = {
        name: _sha256(Path(path)) for name, path in manifest["supporting_artifacts"].items()
    }
    _json(manifest_path, manifest)
    request_path = root / "preflight_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    source = json.loads((root / "receipts/source.json").read_text(encoding="utf-8"))
    request["input_hashes"] = manifest["sha256"]
    request["prepare_manifest_sha256"] = _sha256(manifest_path)
    request["source_identity"] = {
        "repo_sha": source["repo_sha"],
        "training_base_sha": source["training_base_sha"],
    }
    request["prepared_evidence"] = {
        name: json.loads(Path(manifest["artifacts"][name]).read_text(encoding="utf-8"))
        for name in ("source", "runtime", "data", "checkpoint")
    }
    supporting = {
        name: Path(path) for name, path in manifest["supporting_artifacts"].items()
    }
    request["prepared_evidence"]["setup"] = {
        "attestation": json.loads(
            supporting["setup_attestation"].read_text(encoding="utf-8")
        ),
        "attestation_sha256": manifest["supporting_sha256"]["setup_attestation"],
        "hf_revision_marker_sha256": manifest["supporting_sha256"]["hf_revision_marker"],
        "hf_revision_marker_content": supporting["hf_revision_marker"]
        .read_text(encoding="utf-8")
        .strip(),
        "container_inspection_sha256": manifest["supporting_sha256"][
            "container_inspection"
        ],
        "container_inspection": json.loads(
            supporting["container_inspection"].read_text(encoding="utf-8")
        ),
    }
    _json(request_path, request)


def _write_telemetry(stage: Path) -> None:
    rows = [
        "timestamp,index,clocks.sm,power.draw,power.limit,temperature.gpu,clocks_throttle_reasons.active"
    ]
    for timestamp in ("2026-07-10T00:00:00Z", "2026-07-10T00:01:00Z"):
        rows.extend(f"{timestamp},{index},1410,500,700,65,0x0000000000000000" for index in range(8))
    (stage / "gpu_telemetry.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_telemetry_rejects_an_underpowered_h100_run(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    stage.mkdir()
    _write_telemetry(stage)
    telemetry = stage / "gpu_telemetry.csv"
    telemetry.write_text(telemetry.read_text(encoding="utf-8").replace(",700,", ",500,"))
    result = _telemetry_evidence(
        tmp_path,
        {
            "run_started_at_utc": "2026-07-10T00:00:00Z",
            "run_finished_at_utc": "2026-07-10T00:01:00Z",
        },
        "",
        SentryPolicy(),
    )

    assert result["passed"] is False
    assert "telemetry_power_limit_below_minimum" in result["reasons"]


def _write_wandb_bundle(
    output_dir: Path,
    *,
    run_id: str,
    experiment_id: str,
    job_stage: str,
    metric_event_count: int,
    artifact_files: tuple[Path, ...] = (),
    rollout_rows: int = 0,
) -> tuple[Path, Path, Path]:
    evidence = _json(
        output_dir / f"{run_id}.evidence_summary.json",
        {
            "schema_version": 1,
            "experiment_id": experiment_id,
            "timing_status": "verified",
            "metric_event_count": metric_event_count,
            "sample_rows_total": {"rollout": rollout_rows, "eval": 0},
            "checkpoint_file_count": len(artifact_files),
        },
    )
    artifact_manifest = _json(
        output_dir / f"{run_id}.artifact_manifest.json",
        {
            "schema_version": 1,
            "files": [
                {
                    "name": path.name,
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
                for path in artifact_files
            ],
            "skipped": [],
        },
    )
    downloaded_files = {
        evidence.name: _sha256(evidence),
        artifact_manifest.name: _sha256(artifact_manifest),
        **{path.name: _sha256(path) for path in artifact_files},
    }
    readback = _json(
        output_dir / "wandb_readback.json",
        {
            "schema": "h100-wandb-readback/v1",
            "ok": True,
            "errors": [],
            "authenticated_api_read": True,
            "entity": "research-team",
            "project": "glm47-pie-cpp-posttraining",
            "run_id": run_id,
            "experiment_id": experiment_id,
            "stage": job_stage,
            "local_artifact_sha256": {
                "evidence_summary": _sha256(evidence),
                "artifact_manifest": _sha256(artifact_manifest),
            },
            "remote": {
                "run_id": run_id,
                "state": "finished",
                "summary": {
                    "timing_status": "verified",
                    "experiment_id": experiment_id,
                    "stage": job_stage,
                    "status": "success",
                    "metric_event_count": metric_event_count,
                    "artifact_file_count": len(artifact_files),
                },
                "config": {
                    "timing_status": "verified",
                    "experiment_id": experiment_id,
                },
                "matching_artifacts": [
                    {
                        "name": f"{experiment_id}-{job_stage}-run:v0",
                        "digest": "remote-artifact-digest",
                        "metadata": {
                            "experiment_id": experiment_id,
                            "stage": job_stage,
                            "status": "success",
                            "timing_status": "verified",
                        },
                        "downloaded_files": downloaded_files,
                    }
                ],
            },
        },
    )
    return readback, evidence, artifact_manifest


def _write_trial(
    root: Path,
    *,
    name: str,
    ratio: float,
    candidate: bool,
    tranche: str,
) -> Path:
    stage = root / "sft_lora_r16"
    stage.mkdir(parents=True)
    log = stage / "run.log"
    receipt = stage / "run_receipt.txt"
    token_cycle = (93021, 101665, 112769, 86256)
    lines: list[str] = []
    for step in range(16):
        work_tokens = token_cycle[step % len(token_cycle)]
        tok_s = 6800.0 * ratio
        actor_time = work_tokens / tok_s
        actor_tflops = 21.0 * ratio
        lines.append(
            "train_metric_utils.py:50 - perf "
            f"{step}: {{'perf/actor_train_time': {actor_time}, "
            f"'perf/actor_train_tflops': {actor_tflops}, "
            f"'perf/actor_train_tok_per_s': {tok_s}, "
            f"'perf/step_time': {actor_time + 8.0}, 'perf/wait_time_ratio': 0.3}}"
        )
        lines.append(
            f"log_utils.py:463 - step {step}: {{'train/loss': 0.25, 'train/grad_norm': 0.3}}"
        )
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    dispatcher = "alltoall" if candidate else "flex"
    deepep = 0 if candidate else 1
    receipt.write_text(
        "status=success\n"
        "ray_status=0\n"
        "wall_s=60\n"
        "run_started_at_utc=2026-07-10T00:00:00Z\n"
        "run_finished_at_utc=2026-07-10T00:01:00Z\n"
        "max_memory_used_mib=74000\n"
        "data_dir=/data/fixed-long128\n"
        "tasks_dir=/data/fixed-tasks\n"
        "hf_checkpoint=/models/GLM-4.7-Flash\n"
        "model_args_path=/miles/glm4.7-flash.sh\n"
        "ref_load=/models/GLM-4.7-Flash_tp4_ep8\n"
        "seq_length=4096\n"
        "gpus_per_node=8\n"
        "tensor_model_parallel_size=4\n"
        "pipeline_model_parallel_size=1\n"
        "context_parallel_size=1\n"
        "expert_model_parallel_size=8\n"
        "expert_tensor_parallel_size=1\n"
        "max_tokens_per_gpu=16384\n"
        "micro_batch_size=1\n"
        "use_dynamic_batch_size=1\n"
        "balance_data=1\n"
        "sft_rollout_shuffle=0\n"
        "rollout_batch_size=32\n"
        "global_batch_size=32\n"
        "lora_rank=16\n"
        "no_gradient_accumulation_fusion=1\n"
        f"moe_token_dispatcher_type={dispatcher}\n"
        f"moe_enable_deepep={deepep}\n"
        "recompute_granularity=selective\n"
        "cuda_device_max_connections=1\n"
        "extra_args=--no-offload-train\n"
        "timing_status=verified\n"
        "wandb_entity=research-team\n"
        "wandb_project=glm47-pie-cpp-posttraining\n"
        f"wandb_run_id={name}\n"
        "experiment_id=issue32-test\n"
        "wandb_stage=dispatcher-abba\n"
        f"tranche_id={tranche}\n",
        encoding="utf-8",
    )
    summary = summarize_miles_mfu_trial(
        log_path=log,
        receipt_path=receipt,
        round_number=1,
        name=name,
    )
    summary["launcher_exit_code"] = 0
    summary_path = write_trial_summary(root / "trial_summary.json", summary)
    _write_wandb_bundle(
        stage,
        run_id=name,
        experiment_id="issue32-test",
        job_stage="dispatcher-abba",
        metric_event_count=16,
    )
    _write_telemetry(stage)
    return summary_path


def _write_leg_evidence(summary: Path, leg_id: str) -> dict[str, Any]:
    leg_root = summary.parent
    stage = leg_root / "sft_lora_r16"
    evidence_paths = {
        "trial_summary": summary,
        "leg_summary": _json(
            leg_root / "leg_summary.json",
            {
                "schema_version": 1,
                "authority": "executor_supplementary_evidence",
                "valid": True,
            },
        ),
        "run_log": stage / "run.log",
        "run_receipt": stage / "run_receipt.txt",
        "gpu_telemetry": stage / "gpu_telemetry.csv",
        "nvlink_before": _json(leg_root / "nvlink_before.json", {"supported": True}),
        "nvlink_after": _json(leg_root / "nvlink_after.json", {"supported": True}),
        "process_cleanliness_before": _json(
            leg_root / "process_cleanliness_before.json",
            {
                "schema": "h100-process-cleanliness/v1",
                "checked_at_utc": "2026-07-09T23:59:59Z",
                "ok": True,
                "errors": [],
                "gpu_process_inventory": [],
                "relevant_processes": [],
                "commands": {
                    "gpu_process_inventory_returncode": 0,
                    "process_inventory_returncode": 0,
                },
            },
        ),
        "process_cleanliness_after": _json(
            leg_root / "process_cleanliness_after.json",
            {
                "schema": "h100-process-cleanliness/v1",
                "checked_at_utc": "2026-07-10T00:00:59Z",
                "ok": True,
                "errors": [],
                "gpu_process_inventory": [],
                "relevant_processes": [],
                "commands": {
                    "gpu_process_inventory_returncode": 0,
                    "process_inventory_returncode": 0,
                },
            },
        ),
        "wandb_readback": stage / "wandb_readback.json",
        "wandb_evidence_summary": next(stage.glob("*.evidence_summary.json")),
        "wandb_artifact_manifest": next(stage.glob("*.artifact_manifest.json")),
    }
    runner = _runner_module()
    hashes = {name: _sha256(path) for name, path in evidence_paths.items()}
    manifest = _json(
        leg_root / "leg_evidence_manifest.json",
        runner["build_leg_evidence_manifest"](
            runner["LEG_SPECS"][leg_id],
            evidence_paths=evidence_paths,
            hashes=hashes,
            valid=True,
        ),
    )
    return {
        "leg_id": leg_id,
        "leg_root": str(leg_root),
        "trial_summary": str(summary),
        "leg_summary": str(evidence_paths["leg_summary"]),
        "evidence_manifest": str(manifest),
        "evidence_manifest_sha256": _sha256(manifest),
        "valid": True,
    }


def _write_screen_request(root: Path, control: Path, candidate: Path) -> Path:
    legs = [
        _write_leg_evidence(control, "a1"),
        _write_leg_evidence(candidate, "b1"),
    ]
    _json(
        root / "first_pair_result.json",
        {
            "status": "first_pair_complete",
            "authority": "executor_evidence",
            "legs": legs,
        },
    )
    return _json(
        root / "screen_request.json",
        {
            "schema_version": 1,
            "requested_stage": "screen",
            "evidence_hashes": {leg["leg_id"]: leg["evidence_manifest_sha256"] for leg in legs},
            "trial_summary_hashes": {
                leg["leg_id"]: _sha256(Path(leg["trial_summary"])) for leg in legs
            },
            "source_identity": {
                "repo_sha": CURRENT_REPO_SHA,
                "training_base_sha": TRAINING_BASE_SHA,
            },
        },
    )


def test_real_runner_manifest_schema_and_process_cleanliness_are_sentry_graded(
    tmp_path: Path,
) -> None:
    summary = _write_trial(
        tmp_path / "A1",
        name="A1",
        ratio=1.0,
        candidate=False,
        tranche="T1",
    )
    leg = _write_leg_evidence(summary, "a1")
    manifest_path = Path(leg["evidence_manifest"])

    reasons, _ = _validate_runner_evidence_manifest(
        manifest_path,
        leg_id="a1",
        expected_trial=summary,
    )
    assert reasons == []

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    after_path = Path(manifest["paths"]["process_cleanliness_after"])
    after = json.loads(after_path.read_text(encoding="utf-8"))
    after["gpu_process_inventory"] = [
        {"pid": 123, "process_name": "python", "used_gpu_memory_mib": "1024"}
    ]
    _json(after_path, after)
    manifest["sha256"]["process_cleanliness_after"] = _sha256(after_path)
    _json(manifest_path, manifest)

    reasons, _ = _validate_runner_evidence_manifest(
        manifest_path,
        leg_id="a1",
        expected_trial=summary,
    )
    assert "screen_a1_process_cleanliness_after_invalid" in reasons


def _runner_module() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("h100_runner_for_sentry_test", RUNNER_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return vars(module)


def _run_preflight(root: Path) -> tuple[Path, Path, Path, Path]:
    security = _test_security(root)
    gate0 = _write_gate0_chain(root, security)
    contract, hardware, budget, request = _write_preflight_inputs(root)
    result = evaluate_preflight(
        contract_path=contract,
        hardware_path=hardware,
        budget_path=budget,
        request_path=request,
        gate0_permit_path=gate0["permit"],
        gate0_public_key_path=gate0["public_key"],
        launch_receipt_path=gate0["launch_receipt"],
        booking_request_path=gate0["booking_request"],
        provider_output_path=gate0["provider_output"],
        security=security,
        command="sentry preflight",
    )
    return contract, hardware, budget, _save_decision(root / "preflight.json", result)


def _run_screen(
    root: Path, *, ratio: float = 1.04, control_scale: float = 1.0
) -> tuple[Path, Path, Path, Path, Path, dict[str, Any]]:
    contract, hardware, _, preflight = _run_preflight(root)
    control = _write_trial(
        root / "A1",
        name="A1",
        ratio=control_scale,
        candidate=False,
        tranche="T1",
    )
    candidate = _write_trial(
        root / "B1",
        name="B1",
        ratio=control_scale * ratio,
        candidate=True,
        tranche="T1",
    )
    request = _write_screen_request(root, control, candidate)
    security = _test_security(root)
    result = evaluate_screen(
        preflight_decision_path=preflight,
        control_path=control,
        candidate_path=candidate,
        request_path=request,
        security=security,
        command="sentry screen",
    )
    decision = _save_decision(root / "screen.json", result)
    return contract, hardware, control, candidate, decision, result


def _run_promotion(
    root: Path, *, a2_scale: float = 1.0
) -> tuple[Path, list[Path], list[Path], Path, dict[str, Any]]:
    contract, _, a1, b1, screen, _ = _run_screen(root)
    controls = [
        a1,
        _write_trial(
            root / "A2",
            name="A2",
            ratio=a2_scale,
            candidate=False,
            tranche="T1",
        ),
    ]
    candidates = [
        b1,
        _write_trial(
            root / "B2",
            name="B2",
            ratio=a2_scale * 1.04,
            candidate=True,
            tranche="T1",
        ),
    ]
    result = evaluate_promotion(
        screen_decision_path=screen,
        control_paths=controls,
        candidate_paths=candidates,
        security=_test_security(root),
        command="sentry promotion",
    )
    decision = _save_decision(root / "promotion.json", result)
    return contract, controls, candidates, decision, result


def _write_confirmation_request(
    root: Path,
    promotion: Path,
    controls: list[Path],
    candidates: list[Path],
) -> Path:
    parent_hash = _sha256(promotion)
    security = _test_security(root)
    unsigned_budget = {
        "schema_version": 1,
        "authority": "supervisor_t2_authorization",
        "authorization_id": "T2-AUTH-001",
        "authorized": True,
        "authorized_by": "research-supervisor",
        "authorized_at_utc": "2026-07-10T00:03:00Z",
        "tranche_id": "T2",
        "provider": "Lium",
        "accelerators": "8xH100-SXM-80GB",
        "planned_hours": 1.0,
        "maximum_node_hours": 2.0,
        "hourly_rate_usd": 18.0,
        "maximum_usd": 36.0,
        "unused_budget_transfer_allowed": False,
        "source_commit": CURRENT_REPO_SHA,
        "parent_t1_promotion_sha256": parent_hash,
        "issue_number": 32,
        "nontransferable": True,
    }
    budget = _json(
        root / "t2_budget.json",
        sign_bounded_payload(
            unsigned_budget,
            private_key_path=_test_private_key(root, "supervisor"),
            public_key_path=security.supervisor_public_key_path,  # type: ignore[arg-type]
            domain=T2_AUTHORIZATION_DOMAIN,
            signer_principal=security.supervisor_principal or "",
            verifier_principal=security.executor_principal,
            request_id="t2-authorization-0001",
            nonce="2" * 64,
            issued_at=TEST_NOW,
            expires_at=TEST_NOW + timedelta(hours=1),
        ),
    )
    labeled = {
        **{f"a{index}": path for index, path in enumerate(controls, 1)},
        **{f"b{index}": path for index, path in enumerate(candidates, 1)},
    }
    readbacks = {
        label: next(path.parent.rglob("wandb_readback.json")) for label, path in labeled.items()
    }
    return _json(
        root / "confirmation_request.json",
        {
            "schema_version": 1,
            "requested_stage": "confirmation",
            "source_identity": {
                "repo_sha": CURRENT_REPO_SHA,
                "training_base_sha": TRAINING_BASE_SHA,
            },
            "parent_promotion_sha256": parent_hash,
            "t2_budget_path": str(budget),
            "t2_budget_sha256": _sha256(budget),
            "trial_summary_hashes": {label: _sha256(path) for label, path in labeled.items()},
            "wandb_readback_hashes": {label: _sha256(path) for label, path in readbacks.items()},
        },
    )


def _run_confirmation(
    root: Path,
    *,
    t2_control_scale: float = 1.0,
    t2_candidate_pair_ratio: float = 1.04,
) -> tuple[Path, Path, dict[str, Any]]:
    contract, controls, candidates, promotion, _ = _run_promotion(root)
    for index in (3, 4):
        controls.append(
            _write_trial(
                root / f"A{index}",
                name=f"A{index}",
                ratio=t2_control_scale,
                candidate=False,
                tranche="T2",
            )
        )
        candidates.append(
            _write_trial(
                root / f"B{index}",
                name=f"B{index}",
                ratio=t2_control_scale * t2_candidate_pair_ratio,
                candidate=True,
                tranche="T2",
            )
        )
    request = _write_confirmation_request(root, promotion, controls, candidates)
    result = evaluate_confirmation(
        promotion_decision_path=promotion,
        control_paths=controls,
        candidate_paths=candidates,
        request_path=request,
        security=_test_security(root),
        command="sentry confirmation",
    )
    decision = _save_decision(root / "confirmation.json", result)
    return contract, decision, result


def _write_grpo(root: Path) -> Path:
    stage = root / "grpo_lora_r16"
    stage.mkdir(parents=True)
    (stage / "run_receipt.txt").write_text(
        "status=success\n"
        "ray_status=0\n"
        "run_started_at_utc=2026-07-10T00:00:00Z\n"
        "run_finished_at_utc=2026-07-10T00:01:00Z\n"
        "max_memory_used_mib=74000\n"
        "timing_status=verified\n"
        "wandb_entity=research-team\n"
        "wandb_project=glm47-pie-cpp-posttraining\n"
        "wandb_run_id=grpo-run-1\n"
        "experiment_id=issue32-grpo-test\n"
        "wandb_stage=grpo\n",
        encoding="utf-8",
    )
    (stage / "run.log").write_text(
        "Successfully loaded LoRA adapter\n"
        "Finish rollout\n"
        "log_utils.py:463 - step 0: {'train/loss': 0.1, 'train/grad_norm': 0.2}\n"
        "Saving LoRA checkpoint\n"
        "LoRA sync staging complete\n",
        encoding="utf-8",
    )
    checkpoint_root = root / "checkpoint"
    checkpoint_entries: list[dict[str, Any]] = []
    checkpoint_files = [
        ("latest_checkpointed_iteration.txt", b"0\n"),
        ("iter_0000000/adapter/adapter_config.json", b"{}\n"),
        ("iter_0000000/adapter/adapter_model.bin", b"hf-adapter"),
        *[
            (
                f"iter_0000000/adapter/adapter_megatron_tp{rank}_pp0.pt",
                f"megatron-adapter-{rank}".encode(),
            )
            for rank in range(4)
        ],
        *[
            (
                f"iter_0000000/adapter/training_state_rank{rank}.pt",
                f"training-state-{rank}".encode(),
            )
            for rank in range(8)
        ],
    ]
    for relative, content in checkpoint_files:
        checkpoint_file = checkpoint_root / relative
        checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        checkpoint_file.write_bytes(content)
        checkpoint_entries.append(
            {
                "path": relative,
                "size_bytes": checkpoint_file.stat().st_size,
                "sha256": _sha256(checkpoint_file),
            }
        )
    checkpoint_manifest = _json(
        stage / "grpo.checkpoint_manifest.json",
        {
            "schema_version": 1,
            "checkpoint_root": str(checkpoint_root),
            "latest_iteration": "iter_0000000",
            "files": checkpoint_entries,
        },
    )
    _write_wandb_bundle(
        stage,
        run_id="grpo-run-1",
        experiment_id="issue32-grpo-test",
        job_stage="grpo",
        metric_event_count=1,
        artifact_files=(checkpoint_manifest,),
        rollout_rows=32,
    )
    post = "b" * 64
    _json(
        stage / "fingerprints.json",
        {
            "pre_update": {"sha256": "a" * 64},
            "post_update": {"sha256": post},
            "sglang_sync": {"sha256": post},
        },
    )
    _write_telemetry(stage)
    return root


def _run_grpo_stage(root: Path, confirmation: Path) -> tuple[Path, Path, dict[str, Any]]:
    artifact = _write_grpo(root / "grpo-artifact")
    result = evaluate_grpo(
        confirmation_decision_path=confirmation,
        grpo_path=artifact,
        security=_test_security(confirmation.parent),
        command="sentry grpo",
    )
    decision = _save_decision(root / "grpo.json", result)
    return artifact, decision, result


def _write_audit(
    root: Path,
    *,
    contract: Path,
    confirmation: Path,
    grpo: Path,
) -> Path:
    constituents = [
        {"role": role, "path": str(path), "sha256": _sha256(path)}
        for role, path in (
            ("confirmation_decision", confirmation),
            ("grpo_decision", grpo),
            ("contract", contract),
        )
    ]
    manifest = _json(
        root / "audit-manifest.json",
        {"schema_version": 1, "constituent_checksums": constituents},
    )
    security = _test_security(confirmation.parent)
    auditor_public = load_public_key_document(security.auditor_public_key_path)  # type: ignore[arg-type]
    unsigned = {
        "decision": "ACCEPT",
        "auditor_role": "independent_auditor",
        "auditor_identity": "SD-REVIEW-02",
        "auditor_key_id": auditor_public.key_id,
        "auditor_timestamp_utc": "2026-07-10T00:04:00Z",
        "bounded_claim": CLAIM,
        "parent_decision_sha256": _sha256(grpo),
        "manifest_path": str(manifest),
        "manifest_sha256": _sha256(manifest),
        "constituent_checksums": constituents,
        "contract_sha256": _sha256(contract),
    }
    return _json(
        root / "audit.json",
        sign_bounded_payload(
            unsigned,
            private_key_path=_test_private_key(confirmation.parent, "auditor"),
            public_key_path=security.auditor_public_key_path,  # type: ignore[arg-type]
            domain=AUDIT_DECISION_DOMAIN,
            signer_principal=security.auditor_principal or "",
            verifier_principal=security.sentry_principal,
            request_id="independent-audit-0001",
            nonce="3" * 64,
            issued_at=TEST_NOW,
            expires_at=TEST_NOW + timedelta(hours=1),
        ),
    )


def test_preflight_provenance_and_sha_contract(tmp_path: Path) -> None:
    security = _test_security(tmp_path)
    gate0 = _write_gate0_chain(tmp_path, security)
    contract, hardware, budget, request = _write_preflight_inputs(tmp_path)
    result = evaluate_preflight(
        contract_path=contract,
        hardware_path=hardware,
        budget_path=budget,
        request_path=request,
        gate0_permit_path=gate0["permit"],
        gate0_public_key_path=gate0["public_key"],
        launch_receipt_path=gate0["launch_receipt"],
        booking_request_path=gate0["booking_request"],
        provider_output_path=gate0["provider_output"],
        security=security,
        command="sentry preflight --offline",
    )

    assert result["decision"] == "PROMOTABLE"
    assert result["next_stage"] == "screen"
    assert result["exact_command"] == "sentry preflight --offline"
    assert result["sentry"]["source_sha256"]
    assert result["sentry"]["script_sha256"]
    assert len(result["provenance"]["inputs"]) > 3
    assert result["request_sha256"] == _sha256(request)
    assert result["input_hashes"] == json.loads(request.read_text())["input_hashes"]
    assert result["source_identity"] == {
        "repo_sha": CURRENT_REPO_SHA,
        "training_base_sha": TRAINING_BASE_SHA,
    }
    assert result["exit_status"] == 0

    hardware_payload = json.loads(hardware.read_text(encoding="utf-8"))
    hardware_payload["gpu_operating_rows"][0]["power.limit"] = "500"
    _json(hardware, hardware_payload)
    underpowered = evaluate_preflight(
        contract_path=contract,
        hardware_path=hardware,
        budget_path=budget,
        request_path=request,
        gate0_permit_path=gate0["permit"],
        gate0_public_key_path=gate0["public_key"],
        launch_receipt_path=gate0["launch_receipt"],
        booking_request_path=gate0["booking_request"],
        provider_output_path=gate0["provider_output"],
        security=security,
    )
    assert underpowered["decision"] == "INVALID"
    assert "hardware_power_limit_below_minimum" in underpowered["reasons"]

    hardware_payload["gpu_operating_rows"][0]["power.limit"] = "700"
    hardware_payload["training_base_sha"] = "0" * 40
    _json(hardware, hardware_payload)
    assert (
        evaluate_preflight(
            contract_path=contract,
            hardware_path=hardware,
            budget_path=budget,
            request_path=request,
            gate0_permit_path=gate0["permit"],
            gate0_public_key_path=gate0["public_key"],
            launch_receipt_path=gate0["launch_receipt"],
            booking_request_path=gate0["booking_request"],
            provider_output_path=gate0["provider_output"],
            security=security,
        )["decision"]
        == "INVALID"
    )

    hardware_payload["training_base_sha"] = TRAINING_BASE_SHA
    _json(hardware, hardware_payload)
    budget_payload = json.loads(budget.read_text(encoding="utf-8"))
    budget_payload["source_commit"] = "e" * 40
    _json(budget, budget_payload)
    assert (
        evaluate_preflight(
            contract_path=contract,
            hardware_path=hardware,
            budget_path=budget,
            request_path=request,
            gate0_permit_path=gate0["permit"],
            gate0_public_key_path=gate0["public_key"],
            launch_receipt_path=gate0["launch_receipt"],
            booking_request_path=gate0["booking_request"],
            provider_output_path=gate0["provider_output"],
            security=security,
        )["decision"]
        == "INVALID"
    )


def test_gate0_accepts_real_provider_shape_and_requires_server_verified_schedule(
    tmp_path: Path,
) -> None:
    security = _test_security(tmp_path)
    gate0 = _write_gate0_chain(tmp_path, security)
    contract, hardware, budget, request = _write_preflight_inputs(tmp_path)
    accepted = evaluate_preflight(
        contract_path=contract,
        hardware_path=hardware,
        budget_path=budget,
        request_path=request,
        gate0_permit_path=gate0["permit"],
        gate0_public_key_path=gate0["public_key"],
        launch_receipt_path=gate0["launch_receipt"],
        booking_request_path=gate0["booking_request"],
        provider_output_path=gate0["provider_output"],
        security=security,
    )
    provider = json.loads(gate0["provider_output"].read_text(encoding="utf-8"))
    assert accepted["decision"] == "PROMOTABLE"
    assert accepted["context"]["gate0"]["allocation_id"] == provider["pod"]["id"]
    assert provider["schema"] == "lium-h100-pod-create/v1"
    assert "allocation" not in provider

    provider["schedule"]["server_removal_scheduled_at"] = "2026-07-10T03:00:00Z"
    _json(gate0["provider_output"], provider)
    receipt = json.loads(gate0["launch_receipt"].read_text(encoding="utf-8"))
    receipt["provider_output"]["sha256"] = _sha256(gate0["provider_output"])
    receipt["provider_output"]["size_bytes"] = gate0["provider_output"].stat().st_size
    _json(gate0["launch_receipt"], receipt)
    rejected = evaluate_preflight(
        contract_path=contract,
        hardware_path=hardware,
        budget_path=budget,
        request_path=request,
        gate0_permit_path=gate0["permit"],
        gate0_public_key_path=gate0["public_key"],
        launch_receipt_path=gate0["launch_receipt"],
        booking_request_path=gate0["booking_request"],
        provider_output_path=gate0["provider_output"],
        security=security,
    )
    assert rejected["decision"] == "INVALID"
    assert "gate0_provider_schedule_not_server_verified" in rejected["reasons"]


def test_preflight_independently_rejects_forged_container_inspection(
    tmp_path: Path,
) -> None:
    security = _test_security(tmp_path)
    gate0 = _write_gate0_chain(tmp_path, security)
    contract, hardware, budget, request = _write_preflight_inputs(tmp_path)
    inspection_path = tmp_path / "receipts/container_inspect.json"
    inspection = json.loads(inspection_path.read_text(encoding="utf-8"))
    inspection[0]["RepoDigests"] = ["radixark/miles@sha256:" + "b" * 64]
    _json(inspection_path, inspection)
    inspection_sha = _sha256(inspection_path)
    attestation_path = tmp_path / "receipts/setup_attestation.json"
    attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
    attestation["container_inspection_sha256"] = inspection_sha
    _json(attestation_path, attestation)
    for name in ("runtime", "checkpoint"):
        receipt_path = tmp_path / f"receipts/{name}.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["container_inspection_sha256"] = inspection_sha
        receipt["setup_attestation_sha256"] = _sha256(attestation_path)
        _json(receipt_path, receipt)
    _refresh_prepare_bindings(tmp_path)

    result = evaluate_preflight(
        contract_path=contract,
        hardware_path=hardware,
        budget_path=budget,
        request_path=request,
        gate0_permit_path=gate0["permit"],
        gate0_public_key_path=gate0["public_key"],
        launch_receipt_path=gate0["launch_receipt"],
        booking_request_path=gate0["booking_request"],
        provider_output_path=gate0["provider_output"],
        security=security,
    )

    assert result["decision"] == "INVALID"
    assert "preflight_setup_container_inspection_mismatch" in result["reasons"]


def test_gate0_accepts_current_provider_v2_runtime_and_template_evidence(
    tmp_path: Path,
) -> None:
    security = _test_security(tmp_path)
    gate0 = _write_gate0_chain(tmp_path, security)
    contract, hardware, budget, request = _write_preflight_inputs(tmp_path)
    permit = json.loads(gate0["permit"].read_text(encoding="utf-8"))["payload"]
    provider = json.loads(gate0["provider_output"].read_text(encoding="utf-8"))
    provider["schema"] = "lium-h100-pod-create/v2"
    provider["executor"].update(
        {
            "observed_rate_status": permit["observed_node_hourly_rate_status"],
            "rate_authority": "provider_raw_price_per_gpu_x_gpu_count/v1",
            "rate_evidence": {
                "executor_id": provider["executor"]["id"],
                "gpu_count": 8,
                "available_gpu_count": 8,
                "price_per_gpu": 2.25,
                "price_per_hour": 18.0,
                "pending_price_change": False,
            },
        }
    )
    provider["template"].update(
        {
            "docker_image": permit["template_image"],
            "docker_image_tag": permit["template_tag"],
            "status": permit["template_status"],
        }
    )
    provider["runtime_evidence"] = {
        "provider_version": permit["provider_version"],
        "interpreter": {
            "path": permit["provider_interpreter"],
            "sha256": permit["provider_interpreter_sha256"],
            "version": permit["provider_interpreter_version"],
        },
        "lium_sdk": {
            "distribution": permit["lium_sdk_distribution"],
            "version": permit["lium_sdk_version"],
        },
        "lium_cli": {
            "path": permit["lium_cli_path"],
            "sha256": permit["lium_cli_sha256"],
            "version": permit["lium_cli_version"],
            "version_source": "wrapper_verified_cli_version",
        },
    }
    _json(gate0["provider_output"], provider)
    receipt = json.loads(gate0["launch_receipt"].read_text(encoding="utf-8"))
    receipt["provider_output"]["sha256"] = _sha256(gate0["provider_output"])
    receipt["provider_output"]["size_bytes"] = gate0["provider_output"].stat().st_size
    _json(gate0["launch_receipt"], receipt)

    result = evaluate_preflight(
        contract_path=contract,
        hardware_path=hardware,
        budget_path=budget,
        request_path=request,
        gate0_permit_path=gate0["permit"],
        gate0_public_key_path=gate0["public_key"],
        launch_receipt_path=gate0["launch_receipt"],
        booking_request_path=gate0["booking_request"],
        provider_output_path=gate0["provider_output"],
        security=security,
    )
    assert result["decision"] == "PROMOTABLE"

    provider["create_reconciliation"]["successful_snapshots"] = 1
    _json(gate0["provider_output"], provider)
    receipt["provider_output"]["sha256"] = _sha256(gate0["provider_output"])
    receipt["provider_output"]["size_bytes"] = gate0["provider_output"].stat().st_size
    _json(gate0["launch_receipt"], receipt)
    rejected = evaluate_preflight(
        contract_path=contract,
        hardware_path=hardware,
        budget_path=budget,
        request_path=request,
        gate0_permit_path=gate0["permit"],
        gate0_public_key_path=gate0["public_key"],
        launch_receipt_path=gate0["launch_receipt"],
        booking_request_path=gate0["booking_request"],
        provider_output_path=gate0["provider_output"],
        security=security,
    )
    assert rejected["decision"] == "INVALID"
    assert "gate0_provider_unique_allocation_unproven" in rejected["reasons"]


@pytest.mark.parametrize(
    ("surface", "expected_reason"),
    [
        ("provider", "gate0_provider_ssh_access_mismatch"),
        ("receipt", "gate0_launch_receipt_ssh_access_mismatch"),
    ],
)
def test_gate0_ssh_public_key_binding_fails_closed(
    tmp_path: Path, surface: str, expected_reason: str
) -> None:
    security = _test_security(tmp_path)
    gate0 = _write_gate0_chain(tmp_path, security)
    contract, hardware, budget, request = _write_preflight_inputs(tmp_path)
    artifact = gate0["provider_output"] if surface == "provider" else gate0["launch_receipt"]
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload["access"]["ssh_public_key_sha256"] = "f" * 64
    _json(artifact, payload)
    if surface == "provider":
        receipt = json.loads(gate0["launch_receipt"].read_text(encoding="utf-8"))
        receipt["provider_output"]["sha256"] = _sha256(gate0["provider_output"])
        receipt["provider_output"]["size_bytes"] = gate0["provider_output"].stat().st_size
        _json(gate0["launch_receipt"], receipt)

    result = evaluate_preflight(
        contract_path=contract,
        hardware_path=hardware,
        budget_path=budget,
        request_path=request,
        gate0_permit_path=gate0["permit"],
        gate0_public_key_path=gate0["public_key"],
        launch_receipt_path=gate0["launch_receipt"],
        booking_request_path=gate0["booking_request"],
        provider_output_path=gate0["provider_output"],
        security=security,
    )

    assert result["decision"] == "INVALID"
    assert expected_reason in result["reasons"]


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        ("source", "preflight_source_intent_repo_sha_mismatch"),
        ("runtime", "preflight_runtime_intent_miles_sha_mismatch"),
        ("data", "preflight_data_intent_train_hash_mismatch"),
        ("checkpoint", "preflight_checkpoint_intent_root_mismatch"),
        ("contract", "preflight_source_intent_contract_hash_mismatch"),
    ],
)
def test_preflight_reconciles_signed_booking_intent_to_prepared_evidence(
    tmp_path: Path, mutation: str, expected_reason: str
) -> None:
    security = _test_security(tmp_path)
    gate0 = _write_gate0_chain(tmp_path, security)
    contract, hardware, budget, request = _write_preflight_inputs(tmp_path)
    if mutation == "source":
        source_path = tmp_path / "receipts/source.json"
        source = json.loads(source_path.read_text(encoding="utf-8"))
        source["repo_sha"] = "e" * 40
        _json(source_path, source)
        hardware_payload = json.loads(hardware.read_text(encoding="utf-8"))
        hardware_payload["repo_sha"] = "e" * 40
        _json(hardware, hardware_payload)
        budget_payload = json.loads(budget.read_text(encoding="utf-8"))
        budget_payload["source_commit"] = "e" * 40
        _json(budget, budget_payload)
    elif mutation == "runtime":
        hardware_payload = json.loads(hardware.read_text(encoding="utf-8"))
        hardware_payload["miles_sha"] = "0" * 40
        _json(hardware, hardware_payload)
    elif mutation == "data":
        data_path = tmp_path / "receipts/data.json"
        data = json.loads(data_path.read_text(encoding="utf-8"))
        data["sha256"] = "0" * 64
        _json(data_path, data)
    elif mutation == "checkpoint":
        checkpoint_path = tmp_path / "receipts/checkpoint.json"
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        checkpoint["root"] = "/root/models/substituted"
        _json(checkpoint_path, checkpoint)
    else:
        contract_payload = json.loads(contract.read_text(encoding="utf-8"))
        contract_payload["non_semantic_substitution"] = True
        _json(contract, contract_payload)
    _refresh_prepare_bindings(tmp_path)

    result = evaluate_preflight(
        contract_path=contract,
        hardware_path=hardware,
        budget_path=budget,
        request_path=request,
        gate0_permit_path=gate0["permit"],
        gate0_public_key_path=gate0["public_key"],
        launch_receipt_path=gate0["launch_receipt"],
        booking_request_path=gate0["booking_request"],
        provider_output_path=gate0["provider_output"],
        security=security,
    )
    assert result["decision"] == "INVALID"
    assert expected_reason in result["reasons"]


def test_signed_gate1_chain_binds_gate0_and_exact_screen_parents(tmp_path: Path) -> None:
    run_root = tmp_path / "chain"
    _run_screen(run_root)
    security = _test_security(run_root)
    preflight_path = run_root / "preflight.json"
    screen_path = run_root / "screen.json"
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    screen = json.loads(screen_path.read_text(encoding="utf-8"))

    verified_preflight = verify_signed_decision(
        preflight_path,
        security.sentry_public_key_path,
        expected_stage=Stage.PREFLIGHT,
        expected_signer_principal=security.sentry_principal,
        expected_verifier_principal=security.executor_principal,
        expected_request_sha256=_sha256(run_root / "preflight_request.json"),
        expected_parent_decision_sha256=_sha256(run_root / "gate0/permit.json"),
        expected_parent_request_sha256=_sha256(run_root / "gate0/booking_request.json"),
        now=TEST_NOW,
    )
    verified_screen = verify_signed_decision(
        screen_path,
        security.sentry_public_key_path,
        expected_stage=Stage.SCREEN,
        expected_signer_principal=security.sentry_principal,
        expected_verifier_principal=security.executor_principal,
        expected_request_sha256=_sha256(run_root / "screen_request.json"),
        expected_parent_decision_sha256=_sha256(preflight_path),
        expected_parent_request_sha256=_sha256(run_root / "preflight_request.json"),
        now=TEST_NOW,
    )
    assert len(bytes.fromhex(verified_preflight.nonce)) == 32
    assert len(bytes.fromhex(verified_screen.nonce)) == 32
    assert preflight["context"]["gate0"]["allocation_id"] == "pod-h100-001"
    assert preflight["context"]["gate0"]["provider_output_sha256"] == _sha256(
        run_root / "gate0/provider_output.json"
    )
    assert screen["parent_decision_sha256"] == _sha256(preflight_path)


def test_signed_decision_rejects_tamper_domain_principal_parent_and_expiry(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "signed"
    _run_preflight(run_root)
    security = _test_security(run_root)
    source = run_root / "preflight.json"
    signed = json.loads(source.read_text(encoding="utf-8"))
    unsigned = {
        key: value
        for key, value in signed.items()
        if key not in {"signature_base64", "signed_payload_sha256"}
    }

    tampered = dict(signed)
    tampered["decision"] = "REJECTED"
    tampered_path = _json(tmp_path / "tampered.json", tampered)
    with pytest.raises(DecisionSecurityError, match="digest mismatch"):
        verify_signed_decision(
            tampered_path,
            security.sentry_public_key_path,
            expected_stage="preflight",
            expected_signer_principal=security.sentry_principal,
            expected_verifier_principal=security.executor_principal,
            now=TEST_NOW,
        )

    wrong_domain = _json(
        tmp_path / "wrong-domain.json",
        sign_bounded_payload(
            unsigned,
            private_key_path=security.signing_private_key_path,
            public_key_path=security.sentry_public_key_path,
            domain=T2_AUTHORIZATION_DOMAIN,
            signer_principal=security.sentry_principal,
            verifier_principal=security.executor_principal,
            issued_at=TEST_NOW,
        ),
    )
    with pytest.raises(DecisionSecurityError, match="domain mismatch"):
        verify_signed_decision(
            wrong_domain,
            security.sentry_public_key_path,
            expected_stage="preflight",
            expected_signer_principal=security.sentry_principal,
            expected_verifier_principal=security.executor_principal,
            now=TEST_NOW,
        )

    wrong_principal = _json(
        tmp_path / "wrong-principal.json",
        sign_bounded_payload(
            unsigned,
            private_key_path=security.signing_private_key_path,
            public_key_path=security.sentry_public_key_path,
            domain=signature_domain_for_kind("preflight"),
            signer_principal="different-sentry",
            verifier_principal=security.executor_principal,
            issued_at=TEST_NOW,
        ),
    )
    with pytest.raises(DecisionSecurityError, match="signer principal mismatch"):
        verify_signed_decision(
            wrong_principal,
            security.sentry_public_key_path,
            expected_stage="preflight",
            expected_signer_principal=security.sentry_principal,
            expected_verifier_principal=security.executor_principal,
            now=TEST_NOW,
        )

    expired = _json(
        tmp_path / "expired.json",
        sign_bounded_payload(
            unsigned,
            private_key_path=security.signing_private_key_path,
            public_key_path=security.sentry_public_key_path,
            domain=signature_domain_for_kind("preflight"),
            signer_principal=security.sentry_principal,
            verifier_principal=security.executor_principal,
            issued_at=TEST_NOW - timedelta(hours=2),
            expires_at=TEST_NOW - timedelta(hours=1),
        ),
    )
    with pytest.raises(DecisionSecurityError, match="expired"):
        verify_signed_decision(
            expired,
            security.sentry_public_key_path,
            expected_stage="preflight",
            expected_signer_principal=security.sentry_principal,
            expected_verifier_principal=security.executor_principal,
            now=TEST_NOW,
        )
    with pytest.raises(DecisionSecurityError, match="parent_decision_sha256 mismatch"):
        verify_signed_decision(
            source,
            security.sentry_public_key_path,
            expected_stage="preflight",
            expected_signer_principal=security.sentry_principal,
            expected_verifier_principal=security.executor_principal,
            expected_parent_decision_sha256="0" * 64,
            now=TEST_NOW,
        )


def test_execution_approval_is_single_use_and_concurrently_consumed_once(
    tmp_path: Path,
) -> None:
    run_root = tmp_path / "execution"
    _run_preflight(run_root)
    security = _test_security(run_root)
    decision = run_root / "preflight.json"
    request_hash = _sha256(run_root / "preflight_request.json")
    calls: list[str] = []

    def callback() -> str:
        calls.append("ran")
        return "executed"

    assert (
        verify_consume_and_execute(
            decision,
            security.sentry_public_key_path,
            expected_stage="preflight",
            expected_signer_principal=security.sentry_principal,
            expected_verifier_principal=security.executor_principal,
            expected_request_sha256=request_hash,
            ledger_dir=tmp_path / "ledger-one",
            callback=callback,
            now=TEST_NOW,
        )
        == "executed"
    )
    with pytest.raises(DecisionReplayError):
        verify_consume_and_execute(
            decision,
            security.sentry_public_key_path,
            expected_stage="preflight",
            expected_signer_principal=security.sentry_principal,
            expected_verifier_principal=security.executor_principal,
            expected_request_sha256=request_hash,
            ledger_dir=tmp_path / "ledger-one",
            callback=callback,
            now=TEST_NOW,
        )
    assert calls == ["ran"]

    target = tmp_path / "ledger-target"
    target.mkdir(mode=0o700)
    symlink = tmp_path / "ledger-link"
    symlink.symlink_to(target, target_is_directory=True)
    with pytest.raises(DecisionReplayError, match="real private directory"):
        verify_consume_and_execute(
            decision,
            security.sentry_public_key_path,
            expected_stage="preflight",
            expected_signer_principal=security.sentry_principal,
            expected_verifier_principal=security.executor_principal,
            expected_request_sha256=request_hash,
            ledger_dir=symlink,
            callback=callback,
            now=TEST_NOW,
        )

    concurrent_calls: list[str] = []

    def concurrent_worker() -> str:
        try:
            return verify_consume_and_execute(
                decision,
                security.sentry_public_key_path,
                expected_stage="preflight",
                expected_signer_principal=security.sentry_principal,
                expected_verifier_principal=security.executor_principal,
                expected_request_sha256=request_hash,
                ledger_dir=tmp_path / "ledger-concurrent",
                callback=lambda: concurrent_calls.append("ran") or "executed",
                now=TEST_NOW,
            )
        except DecisionReplayError:
            return "replay"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(lambda _: concurrent_worker(), range(2)))
    assert outcomes == ["executed", "replay"]
    assert concurrent_calls == ["ran"]

    rejected_calls: list[str] = []
    with pytest.raises(DecisionSecurityError, match="signer principal mismatch"):
        verify_consume_and_execute(
            decision,
            security.sentry_public_key_path,
            expected_stage="preflight",
            expected_signer_principal="wrong-principal",
            expected_verifier_principal=security.executor_principal,
            expected_request_sha256=request_hash,
            ledger_dir=tmp_path / "ledger-rejected",
            callback=lambda: rejected_calls.append("ran"),
            now=TEST_NOW,
        )
    assert rejected_calls == []


def test_screen_uses_98_percent_guardrail_not_success_threshold(tmp_path: Path) -> None:
    _, _, _, _, _, retained = _run_screen(tmp_path / "retained", ratio=0.99)
    _, _, _, _, _, stopped = _run_screen(tmp_path / "stopped", ratio=0.97)

    assert retained["decision"] == "PROMOTABLE"
    assert retained["pair"]["preserved_matched_observations"] == 14
    assert retained["screen_rule"]["three_percent_required"] is False
    request = json.loads((tmp_path / "retained/screen_request.json").read_text())
    assert retained["evidence_hashes"] == request["evidence_hashes"]
    assert retained["trial_summary_hashes"] == request["trial_summary_hashes"]
    assert stopped["decision"] == "REJECTED"


def test_control_baseline_envelope_is_enforced_at_screen_and_promotion(
    tmp_path: Path,
) -> None:
    *_, screen = _run_screen(tmp_path / "screen", control_scale=1.06)
    *_, promotion = _run_promotion(tmp_path / "promotion", a2_scale=1.06)

    assert screen["decision"] == "INVALID"
    assert "T1-P1_control_estimated_mfu_outside_historical_5pct" in screen["reasons"]
    assert promotion["decision"] == "INVALID"
    assert "T1-P2_control_estimated_mfu_outside_historical_5pct" in promotion["reasons"]


def test_wandb_readback_is_request_bound_and_required(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing"
    _, _, control, candidate, _, _ = _run_screen(missing_root)
    (control.parent / "sft_lora_r16/wandb_readback.json").unlink()
    missing = evaluate_screen(
        preflight_decision_path=missing_root / "preflight.json",
        control_path=control,
        candidate_path=candidate,
        request_path=missing_root / "screen_request.json",
        security=_test_security(missing_root),
    )
    assert missing["decision"] == "INVALID"
    assert "screen_a1_wandb_readback_missing" in missing["reasons"]

    tampered_root = tmp_path / "tampered"
    _, _, control, candidate, _, _ = _run_screen(tampered_root)
    readback = control.parent / "sft_lora_r16/wandb_readback.json"
    payload = json.loads(readback.read_text(encoding="utf-8"))
    payload["remote"]["config"]["timing_status"] = "unverified"
    _json(readback, payload)
    tampered = evaluate_screen(
        preflight_decision_path=tampered_root / "preflight.json",
        control_path=control,
        candidate_path=candidate,
        request_path=tampered_root / "screen_request.json",
        security=_test_security(tampered_root),
    )
    assert tampered["decision"] == "INVALID"
    assert "screen_a1_wandb_readback_hash_mismatch" in tampered["reasons"]


def test_promotion_is_abba_only_and_reports_cycle_diagnostic(tmp_path: Path) -> None:
    _, _, _, _, result = _run_promotion(tmp_path)

    assert result["decision"] == "PROMOTABLE"
    assert result["next_stage"] == "confirmation"
    assert [pair["preserved_matched_observations"] for pair in result["pairs"]] == [14, 14]
    assert [pair["complete_cycle_diagnostic"]["observation_count"] for pair in result["pairs"]] == [
        12,
        12,
    ]
    assert result["promotion_rule"]["complete_block_bootstrap_is_diagnostic_only"] is True
    assert result["promotion_rule"]["final_confidence_claim_allowed"] is False


def test_confirmation_uses_four_independent_process_pair_ratios(tmp_path: Path) -> None:
    _, _, result = _run_confirmation(tmp_path)

    assert result["decision"] == "PROMOTABLE"
    assert result["next_stage"] == "grpo"
    stats = result["confirmation_statistics"]
    assert stats["sample_size"] == 4
    assert stats["independent_unit"] == "process_pair"
    for metric in ("estimated_mfu", "actor_throughput"):
        assert stats[metric]["geometric_mean_ratio"] >= 1.03
        assert stats[metric]["one_sided_95_percent_lower_log_bound"] > 0.0


def test_confirmation_rejects_three_t1_pairs_and_only_one_t2_pair(tmp_path: Path) -> None:
    _, controls, candidates, promotion, _ = _run_promotion(tmp_path)
    for index, tranche in ((3, "T1"), (4, "T2")):
        controls.append(
            _write_trial(
                tmp_path / f"A{index}",
                name=f"A{index}",
                ratio=1.0,
                candidate=False,
                tranche=tranche,
            )
        )
        candidates.append(
            _write_trial(
                tmp_path / f"B{index}",
                name=f"B{index}",
                ratio=1.04,
                candidate=True,
                tranche=tranche,
            )
        )
    request = _write_confirmation_request(tmp_path, promotion, controls, candidates)
    result = evaluate_confirmation(
        promotion_decision_path=promotion,
        control_paths=controls,
        candidate_paths=candidates,
        request_path=request,
        security=_test_security(tmp_path),
    )

    assert result["decision"] == "INVALID"
    assert "confirmation_requires_exactly_two_T1_then_two_T2_pairs" in result["reasons"]


def test_confirmation_requires_t2_authorization_and_every_candidate_hurdle(
    tmp_path: Path,
) -> None:
    authorized_root = tmp_path / "authorized"
    _, _, authorized = _run_confirmation(authorized_root)
    controls = [authorized_root / f"A{index}/trial_summary.json" for index in range(1, 5)]
    candidates = [authorized_root / f"B{index}/trial_summary.json" for index in range(1, 5)]
    no_request = evaluate_confirmation(
        promotion_decision_path=authorized_root / "promotion.json",
        control_paths=controls,
        candidate_paths=candidates,
        security=_test_security(authorized_root),
    )
    assert authorized["decision"] == "PROMOTABLE"
    assert no_request["decision"] == "INVALID"
    assert "request_missing" in no_request["reasons"]

    budget = authorized_root / "t2_budget.json"
    budget_payload = json.loads(budget.read_text(encoding="utf-8"))
    budget_payload["maximum_usd"] = 72.0
    _json(budget, budget_payload)
    tampered_budget = evaluate_confirmation(
        promotion_decision_path=authorized_root / "promotion.json",
        control_paths=controls,
        candidate_paths=candidates,
        request_path=authorized_root / "confirmation_request.json",
        security=_test_security(authorized_root),
    )
    assert tampered_budget["decision"] == "INVALID"
    assert "confirmation_t2_budget_hash_mismatch" in tampered_budget["reasons"]

    *_, weak = _run_confirmation(
        tmp_path / "weak-candidate",
        t2_control_scale=0.96,
        t2_candidate_pair_ratio=1.04,
    )
    assert weak["decision"] == "NO_WIN"
    assert "P3_candidate_below_historical_throughput_hurdle" in weak["reasons"]
    assert "P4_candidate_below_historical_throughput_hurdle" in weak["reasons"]


def test_grpo_checkpoint_files_must_exist_and_match_manifest(tmp_path: Path) -> None:
    _, confirmation, _ = _run_confirmation(tmp_path / "chain")
    artifact = _write_grpo(tmp_path / "grpo")
    checkpoint = artifact / "checkpoint/iter_0000000/adapter/adapter_model.bin"
    original = checkpoint.read_bytes()

    checkpoint.unlink()
    missing = evaluate_grpo(
        confirmation_decision_path=confirmation,
        grpo_path=artifact,
        security=_test_security(tmp_path / "chain"),
    )
    assert missing["decision"] == "INVALID"
    assert any(
        reason.startswith("grpo_checkpoint_file_missing_or_not_regular")
        for reason in missing["reasons"]
    )

    checkpoint.write_bytes(original + b"tampered")
    tampered = evaluate_grpo(
        confirmation_decision_path=confirmation,
        grpo_path=artifact,
        security=_test_security(tmp_path / "chain"),
    )
    assert tampered["decision"] == "INVALID"
    assert any(
        reason.startswith("grpo_checkpoint_file_hash_mismatch") for reason in tampered["reasons"]
    )


@pytest.mark.parametrize(
    ("relative_path", "expected_reason"),
    [
        (
            "iter_0000000/adapter/adapter_megatron_tp3_pp0.pt",
            "grpo_checkpoint_tp4_adapter_rank_set_incomplete",
        ),
        (
            "iter_0000000/adapter/training_state_rank7.pt",
            "grpo_checkpoint_training_state_rank_set_incomplete",
        ),
        (
            "iter_0000000/adapter/adapter_config.json",
            "grpo_checkpoint_adapter_config_missing",
        ),
        (
            "iter_0000000/adapter/adapter_model.bin",
            "grpo_checkpoint_hf_adapter_missing_or_ambiguous",
        ),
    ],
)
def test_grpo_requires_exact_complete_tp4_and_training_rank_set(
    tmp_path: Path, relative_path: str, expected_reason: str
) -> None:
    _, confirmation, _ = _run_confirmation(tmp_path / "chain")
    artifact = _write_grpo(tmp_path / "grpo")
    checkpoint_root = artifact / "checkpoint"
    (checkpoint_root / relative_path).unlink()
    manifest_path = next(artifact.rglob("*.checkpoint_manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"] = [item for item in manifest["files"] if item["path"] != relative_path]
    _json(manifest_path, manifest)

    result = evaluate_grpo(
        confirmation_decision_path=confirmation,
        grpo_path=artifact,
        security=_test_security(tmp_path / "chain"),
    )
    assert result["decision"] == "INVALID"
    assert expected_reason in result["reasons"]


def test_grpo_requires_latest_iteration_and_complete_real_file_manifest(
    tmp_path: Path,
) -> None:
    _, confirmation, _ = _run_confirmation(tmp_path / "chain")
    artifact = _write_grpo(tmp_path / "grpo")
    manifest_path = next(artifact.rglob("*.checkpoint_manifest.json"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["latest_iteration"] = "iter_0000001"
    _json(manifest_path, manifest)
    mismatched_iteration = evaluate_grpo(
        confirmation_decision_path=confirmation,
        grpo_path=artifact,
        security=_test_security(tmp_path / "chain"),
    )
    assert "grpo_checkpoint_latest_iteration_mismatch" in mismatched_iteration["reasons"]

    manifest["latest_iteration"] = "iter_0000000"
    _json(manifest_path, manifest)
    extra = artifact / "checkpoint/iter_0000000/adapter/unmanifested.pt"
    extra.write_bytes(b"unmanifested")
    incomplete_manifest = evaluate_grpo(
        confirmation_decision_path=confirmation,
        grpo_path=artifact,
        security=_test_security(tmp_path / "chain"),
    )
    assert "grpo_checkpoint_manifest_real_file_set_mismatch" in incomplete_manifest["reasons"]


def test_grpo_then_independent_audit_is_required_for_verified(tmp_path: Path) -> None:
    contract, confirmation, _ = _run_confirmation(tmp_path)
    grpo_artifact = _write_grpo(tmp_path / "grpo")
    grpo_result = evaluate_grpo(
        confirmation_decision_path=confirmation,
        grpo_path=grpo_artifact,
        security=_test_security(tmp_path),
        command="sentry grpo",
    )
    grpo_decision = _save_decision(tmp_path / "grpo.json", grpo_result)
    assert grpo_result["decision"] == "PROMOTABLE"

    audit = _write_audit(
        tmp_path,
        contract=contract,
        confirmation=confirmation,
        grpo=grpo_decision,
    )
    final = evaluate_final(
        confirmation_decision_path=confirmation,
        grpo_decision_path=grpo_decision,
        audit_path=audit,
        contract_path=contract,
        security=_test_security(tmp_path),
        command="sentry final",
    )

    assert final["decision"] == "VERIFIED"
    assert final["accepted"] is True
    assert final["exit_status"] == 0
    expected_contract_sha256 = _sha256(contract)
    for decision_path in (
        tmp_path / "preflight.json",
        tmp_path / "screen.json",
        tmp_path / "promotion.json",
        confirmation,
        grpo_decision,
    ):
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        assert decision["acceptance_contract_sha256"] == expected_contract_sha256
    assert final["acceptance_contract_sha256"] == expected_contract_sha256


def test_final_rejects_substituted_contract_with_matching_identifiers(tmp_path: Path) -> None:
    contract, confirmation, _ = _run_confirmation(tmp_path / "chain")
    _, grpo, grpo_result = _run_grpo_stage(tmp_path / "grpo-stage", confirmation)
    assert grpo_result["decision"] == "PROMOTABLE"
    substituted_payload = json.loads(contract.read_text(encoding="utf-8"))
    substituted_payload["non_semantic_substitution"] = "different artifact bytes"
    substituted = _json(tmp_path / "substituted-contract.json", substituted_payload)
    audit = _write_audit(
        tmp_path / "audit",
        contract=substituted,
        confirmation=confirmation,
        grpo=grpo,
    )

    result = evaluate_final(
        confirmation_decision_path=confirmation,
        grpo_decision_path=grpo,
        audit_path=audit,
        contract_path=substituted,
        security=_test_security(tmp_path / "chain"),
    )
    assert result["decision"] == "INVALID"
    assert "final_confirmation_acceptance_contract_hash_mismatch" in result["reasons"]
    assert "final_grpo_acceptance_contract_hash_mismatch" in result["reasons"]


@pytest.mark.parametrize(
    ("mutation", "expected_reason"),
    [
        ("missing-auditor-key", "audit_auditor_key_id_mismatch"),
        ("wrong-parent", "audit_parent_decision_sha256_mismatch"),
    ],
)
def test_final_enforces_contract_required_auditor_key_and_parent_fields(
    tmp_path: Path, mutation: str, expected_reason: str
) -> None:
    contract, confirmation, _ = _run_confirmation(tmp_path / "chain")
    _, grpo, _ = _run_grpo_stage(tmp_path / "grpo-stage", confirmation)
    valid_audit = _write_audit(
        tmp_path / "audit-source",
        contract=contract,
        confirmation=confirmation,
        grpo=grpo,
    )
    unsigned = {
        key: value
        for key, value in json.loads(valid_audit.read_text(encoding="utf-8")).items()
        if key not in {"signature_base64", "signed_payload_sha256"}
    }
    if mutation == "missing-auditor-key":
        unsigned.pop("auditor_key_id")
    else:
        unsigned["parent_decision_sha256"] = "0" * 64
    security = _test_security(tmp_path / "chain")
    resigned = _json(
        tmp_path / f"{mutation}.json",
        sign_bounded_payload(
            unsigned,
            private_key_path=_test_private_key(tmp_path / "chain", "auditor"),
            public_key_path=security.auditor_public_key_path,  # type: ignore[arg-type]
            domain=AUDIT_DECISION_DOMAIN,
            signer_principal=security.auditor_principal or "",
            verifier_principal=security.sentry_principal,
            request_id=f"audit-{mutation}-0001",
            nonce="4" * 64,
            issued_at=TEST_NOW,
            expires_at=TEST_NOW + timedelta(hours=1),
        ),
    )
    result = evaluate_final(
        confirmation_decision_path=confirmation,
        grpo_decision_path=grpo,
        audit_path=resigned,
        contract_path=contract,
        security=security,
    )
    assert result["decision"] == "INVALID"
    assert expected_reason in result["reasons"]


def test_final_rejects_cross_run_grpo_and_audit_splices(tmp_path: Path) -> None:
    contract_a, confirmation_a, _ = _run_confirmation(tmp_path / "chain-a")
    _, grpo_a, result_a = _run_grpo_stage(tmp_path / "chain-a-final", confirmation_a)
    chain_b = tmp_path / "chain-b"
    _copy_test_keys(tmp_path / "chain-a", chain_b)
    contract_b, confirmation_b, _ = _run_confirmation(chain_b)
    _, grpo_b, result_b = _run_grpo_stage(tmp_path / "chain-b-final", confirmation_b)
    assert result_a["decision"] == result_b["decision"] == "PROMOTABLE"

    mixed_audit = _write_audit(
        tmp_path / "mixed-audit",
        contract=contract_a,
        confirmation=confirmation_a,
        grpo=grpo_b,
    )
    mixed = evaluate_final(
        confirmation_decision_path=confirmation_a,
        grpo_decision_path=grpo_b,
        audit_path=mixed_audit,
        contract_path=contract_a,
        security=_test_security(tmp_path / "chain-a"),
    )
    assert mixed["decision"] == "INVALID"
    assert "grpo_confirmation_chain_mismatch" in mixed["reasons"]

    foreign_audit = _write_audit(
        tmp_path / "foreign-audit",
        contract=contract_b,
        confirmation=confirmation_b,
        grpo=grpo_b,
    )
    foreign = evaluate_final(
        confirmation_decision_path=confirmation_a,
        grpo_decision_path=grpo_a,
        audit_path=foreign_audit,
        contract_path=contract_a,
        security=_test_security(tmp_path / "chain-a"),
    )
    assert foreign["decision"] == "INVALID"
    assert "audit_required_constituent_mismatch:confirmation_decision" in foreign["reasons"]


def test_final_rejects_self_audit_and_sentry_auditor_key_reuse(tmp_path: Path) -> None:
    contract, confirmation, _ = _run_confirmation(tmp_path)
    _, grpo, grpo_result = _run_grpo_stage(tmp_path / "final", confirmation)
    assert grpo_result["decision"] == "PROMOTABLE"
    valid_audit = _write_audit(
        tmp_path / "audit",
        contract=contract,
        confirmation=confirmation,
        grpo=grpo,
    )
    unsigned = {
        key: value
        for key, value in json.loads(valid_audit.read_text(encoding="utf-8")).items()
        if key not in {"signature_base64", "signed_payload_sha256"}
    }
    security = _test_security(tmp_path)
    self_audit = _json(
        tmp_path / "self-audit.json",
        sign_bounded_payload(
            unsigned,
            private_key_path=security.signing_private_key_path,
            public_key_path=security.sentry_public_key_path,
            domain=AUDIT_DECISION_DOMAIN,
            signer_principal=security.sentry_principal,
            verifier_principal=security.sentry_principal,
            issued_at=TEST_NOW,
        ),
    )
    reused_security = SentrySecurity(
        signing_private_key_path=security.signing_private_key_path,
        sentry_public_key_path=security.sentry_public_key_path,
        sentry_principal=security.sentry_principal,
        executor_principal=security.executor_principal,
        supervisor_public_key_path=security.supervisor_public_key_path,
        supervisor_principal=security.supervisor_principal,
        auditor_public_key_path=security.sentry_public_key_path,
        auditor_principal=security.sentry_principal,
        now=TEST_NOW,
    )
    result = evaluate_final(
        confirmation_decision_path=confirmation,
        grpo_decision_path=grpo,
        audit_path=self_audit,
        contract_path=contract,
        security=reused_security,
    )
    assert result["decision"] == "INVALID"
    assert "audit_sentry_key_reuse_forbidden" in result["reasons"]
    assert "audit_self_signing_forbidden" in result["reasons"]


def test_runner_requests_validate_end_to_end_and_reject_tampering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current_now = datetime.now(timezone.utc).replace(microsecond=0)
    original_write_gate0_chain = _write_gate0_chain

    def write_current_gate0_chain(
        root: Path,
        security: SentrySecurity,
        *,
        now: datetime = current_now,
    ) -> dict[str, Path]:
        return original_write_gate0_chain(root, security, now=now)

    monkeypatch.setitem(globals(), "TEST_NOW", current_now)
    monkeypatch.setitem(globals(), "_write_gate0_chain", write_current_gate0_chain)
    run_root = tmp_path / "run"
    _, _, control, candidate, _, screen = _run_screen(run_root)
    runner = _runner_module()
    security = _test_security(run_root)
    public_key = Path(security.sentry_public_key_path)
    booking_request = json.loads((run_root / "gate0/booking_request.json").read_text())
    gate1_trust = booking_request["gate1_trust"]
    runner["_verify_gate1_trust_anchor"](
        public_key,
        trust=gate1_trust,
        expected_sentry_principal=security.sentry_principal,
        expected_executor_principal=security.executor_principal,
    )

    preflight_path = run_root / "preflight.json"
    preflight_request = run_root / "preflight_request.json"
    preflight_payload = json.loads(preflight_path.read_text())
    preflight_request_sha256 = _sha256(preflight_request)
    gate0_permit_sha256 = _sha256(run_root / "gate0/permit.json")
    booking_request_sha256 = _sha256(run_root / "gate0/booking_request.json")
    assert preflight_payload["request_sha256"] == preflight_request_sha256
    assert preflight_payload["parent_decision_sha256"] == gate0_permit_sha256
    assert preflight_payload["parent_request_sha256"] == booking_request_sha256

    ledger = run_root / "approval-ledger"
    runner["GATE1_CONSUMPTION_ROOT"] = ledger
    preserved_preflight = run_root / "runner-approvals/preflight.json"
    preflight_approval_sha256 = runner["_verify_consume_and_preserve_approval"](
        approval_path=preflight_path,
        public_key_path=public_key,
        destination=preserved_preflight,
        expected_stage=Stage.PREFLIGHT,
        expected_sentry_principal=security.sentry_principal,
        expected_executor_principal=security.executor_principal,
        expected_request_sha256=preflight_request_sha256,
        expected_parent_decision_sha256=gate0_permit_sha256,
        expected_parent_request_sha256=booking_request_sha256,
        expected_public_key_sha256=gate1_trust["public_key_sha256"],
        request_path=preflight_request,
        run_root=run_root,
        consumed_phase="first_pair_authorized",
    )
    assert preflight_approval_sha256 == _sha256(preflight_path)
    assert _sha256(preserved_preflight) == preflight_approval_sha256

    screen_path = run_root / "screen.json"
    screen_request = run_root / "screen_request.json"
    screen_payload = json.loads(screen_path.read_text())
    screen_request_sha256 = _sha256(screen_request)
    assert screen_payload["request_sha256"] == screen_request_sha256
    assert screen_payload["parent_decision_sha256"] == preflight_approval_sha256
    assert screen_payload["parent_request_sha256"] == preflight_request_sha256

    preserved_screen = run_root / "runner-approvals/screen.json"
    screen_approval_sha256 = runner["_verify_consume_and_preserve_approval"](
        approval_path=screen_path,
        public_key_path=public_key,
        destination=preserved_screen,
        expected_stage=Stage.SCREEN,
        expected_sentry_principal=security.sentry_principal,
        expected_executor_principal=security.executor_principal,
        expected_request_sha256=screen_request_sha256,
        expected_parent_decision_sha256=preflight_approval_sha256,
        expected_parent_request_sha256=preflight_request_sha256,
        expected_public_key_sha256=gate1_trust["public_key_sha256"],
        request_path=screen_request,
        run_root=run_root,
        consumed_phase="second_pair_authorized",
    )
    assert screen_approval_sha256 == _sha256(screen_path)
    assert _sha256(preserved_screen) == screen_approval_sha256
    assert screen_payload["evidence_hashes"] == screen["evidence_hashes"]
    assert screen_payload["trial_summary_hashes"] == screen["trial_summary_hashes"]
    assert len(list(ledger.glob("*.consumed.json"))) == 2

    control_log = control.parent / "sft_lora_r16/run.log"
    control_log.write_text(
        control_log.read_text(encoding="utf-8") + "tampered after request\n",
        encoding="utf-8",
    )
    sentry_recheck = evaluate_screen(
        preflight_decision_path=run_root / "preflight.json",
        control_path=control,
        candidate_path=candidate,
        request_path=run_root / "screen_request.json",
        security=_test_security(run_root),
    )
    assert sentry_recheck["decision"] == "INVALID"
    assert "screen_a1_run_log_hash_mismatch" in sentry_recheck["reasons"]

    request_payload = json.loads((run_root / "screen_request.json").read_text())
    request_payload["trial_summary_hashes"]["b1"] = "0" * 64
    _json(run_root / "screen_request.json", request_payload)
    claims_before = {path.name for path in ledger.iterdir()}
    rejected_copy = run_root / "runner-approvals/rejected-screen.json"
    with pytest.raises(SystemExit, match="stage request changed before approval verification"):
        runner["_verify_consume_and_preserve_approval"](
            approval_path=screen_path,
            public_key_path=public_key,
            destination=rejected_copy,
            expected_stage=Stage.SCREEN,
            expected_sentry_principal=security.sentry_principal,
            expected_executor_principal=security.executor_principal,
            expected_request_sha256=screen_request_sha256,
            expected_parent_decision_sha256=preflight_approval_sha256,
            expected_parent_request_sha256=preflight_request_sha256,
            expected_public_key_sha256=gate1_trust["public_key_sha256"],
            request_path=screen_request,
            run_root=run_root,
            consumed_phase="must_not_be_written",
        )
    assert {path.name for path in ledger.iterdir()} == claims_before
    assert not rejected_copy.exists()


def test_runner_authored_and_stale_stage_receipts_are_invalid(tmp_path: Path) -> None:
    _, hardware, control, candidate, _, _ = _run_screen(tmp_path)
    preflight = json.loads((tmp_path / "preflight.json").read_text(encoding="utf-8"))
    preflight["sentry"]["authored_by"] = "runner"
    runner_receipt = _json(tmp_path / "runner-preflight.json", preflight)
    runner_result = evaluate_screen(
        preflight_decision_path=runner_receipt,
        control_path=control,
        candidate_path=candidate,
        request_path=tmp_path / "screen_request.json",
        security=_test_security(tmp_path),
    )
    assert runner_result["decision"] == "INVALID"
    assert "prior_decision_not_sentry_authored" in runner_result["reasons"]

    hardware_payload = json.loads(hardware.read_text(encoding="utf-8"))
    hardware_payload["probe_note"] = "changed after preflight"
    _json(hardware, hardware_payload)
    stale_result = evaluate_screen(
        preflight_decision_path=tmp_path / "preflight.json",
        control_path=control,
        candidate_path=candidate,
        request_path=tmp_path / "screen_request.json",
        security=_test_security(tmp_path),
    )
    assert stale_result["decision"] == "INVALID"
    assert "prior_decision_input_artifact_stale" in stale_result["reasons"]


def test_cli_emits_machine_readable_preflight_decision(tmp_path: Path, capsys: Any) -> None:
    security = _test_security(tmp_path)
    gate0 = _write_gate0_chain(tmp_path, security, now=datetime.now(timezone.utc))
    contract, hardware, budget, request = _write_preflight_inputs(tmp_path)

    exit_code = main(
        [
            "preflight",
            "--contract",
            str(contract),
            "--hardware",
            str(hardware),
            "--budget",
            str(budget),
            "--request",
            str(request),
            "--gate0-permit",
            str(gate0["permit"]),
            "--gate0-public-key",
            str(gate0["public_key"]),
            "--launch-receipt",
            str(gate0["launch_receipt"]),
            "--booking-request",
            str(gate0["booking_request"]),
            "--provider-output",
            str(gate0["provider_output"]),
            "--signing-key",
            str(security.signing_private_key_path),
            "--sentry-public-key",
            str(security.sentry_public_key_path),
            "--sentry-principal",
            security.sentry_principal,
            "--executor-principal",
            security.executor_principal,
            "--supervisor-public-key",
            str(security.supervisor_public_key_path),
            "--supervisor-principal",
            security.supervisor_principal or "",
            "--auditor-public-key",
            str(security.auditor_public_key_path),
            "--auditor-principal",
            security.auditor_principal or "",
        ]
    )
    output = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert output["decision"] == "PROMOTABLE"
    assert output["output_schema"] == "h100-research-sentry-decision/v3"
