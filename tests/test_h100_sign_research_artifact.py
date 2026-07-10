from __future__ import annotations

import base64
import hashlib
import json
import platform
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from w8_biayn.integrations.h100_research_sentry import (
    BOOKING_REQUEST_SCHEMA,
    signature_domain_for_kind,
    signing_main,
)
from w8_biayn.integrations.h100_signed_approval import (
    CREDENTIAL_TRANSPORT,
    ENVELOPE_SCHEMA,
    PERMIT_SCHEMA,
    PUBLIC_KEY_SCHEMA,
    PermitError,
    key_id_for_public_key,
    load_and_verify_permit,
    load_public_key_document,
    verify_detached_signature,
)


def _keys(root: Path, name: str = "signer") -> tuple[Path, Path]:
    private = Ed25519PrivateKey.generate()
    private_path = root / f"external-{name}-private.pem"
    private_path.write_bytes(
        private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    private_path.chmod(0o600)
    raw = private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    public_path = root / f"{name}-public.json"
    public_path.write_text(
        json.dumps(
            {
                "schema": PUBLIC_KEY_SCHEMA,
                "algorithm": "Ed25519",
                "key_id": key_id_for_public_key(raw),
                "public_key_base64": base64.b64encode(raw).decode("ascii"),
            }
        ),
        encoding="utf-8",
    )
    return private_path, public_path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _gate0_fixture(
    root: Path,
) -> tuple[dict[str, object], Path, Path, Path, Path, Path, list[str], datetime]:
    private_path, public_path = _keys(root, "gate0")
    _, gate1_public_path = _keys(root, "gate1")
    gate1_public_document = json.loads(gate1_public_path.read_text(encoding="utf-8"))
    intent_root = root / "booking-intent"
    intent_root.mkdir()
    intent_payloads = {
        "source": {
            "schema": "h100-booking-source-intent/v1",
            "repo_sha": "f" * 40,
            "training_base_sha": "c" * 40,
            "acceptance_contract_sha256": "a" * 64,
        },
        "runtime": {
            "schema": "h100-booking-runtime-intent/v1",
            "miles_sha": "1" * 40,
            "megatron_sha": "2" * 40,
            "runtime_pins": {
                "container_image": "miles@example",
                "container_platform": "linux/amd64",
                "hf_model": "zai-org/GLM-4.7-Flash",
                "hf_revision": "3" * 40,
                "lium_cli_version": "0.0.3",
                "lium_provider_version": "1.2.0",
            },
        },
        "data": {
            "schema": "h100-booking-data-intent/v1",
            "train_sha256": "4" * 64,
            "manifest_sha256": "5" * 64,
            "row_count": 128,
        },
        "checkpoint": {
            "schema": "h100-booking-checkpoint-intent/v1",
            "root": str((root / "model").resolve()),
            "layout": "TP4/PP1/EP8/ETP1",
            "hf_model": "zai-org/GLM-4.7-Flash",
            "hf_revision": "3" * 40,
        },
    }
    intent_paths: dict[str, Path] = {}
    for name, intent_payload in intent_payloads.items():
        path = intent_root / f"{name}.json"
        path.write_text(json.dumps(intent_payload), encoding="utf-8")
        intent_paths[name] = path
    parent_request = root / "booking-request.json"
    parent_request.write_text(
        json.dumps(
            {
                "schema": BOOKING_REQUEST_SCHEMA,
                "issue_number": 32,
                "allocation_name": "issue-32-dispatcher",
                "provider": "lium",
                "provider_version": "1.2.0",
                "profile": "h100-sxm",
                "executor_id": "h100-sxm",
                "sentry_principal": "research-sentry",
                "executor_principal": "h100-runner",
                "gate1_trust": {
                    "public_key_sha256": _sha256(gate1_public_path),
                    "key_id": gate1_public_document["key_id"],
                    "sentry_principal": "research-sentry",
                    "executor_principal": "h100-runner",
                },
                "hardware": {"gpu_type": "H100", "gpu_count": 8},
                "budget": {
                    "ttl_seconds": 3600,
                    "max_cost_usd": "18",
                    "max_node_hourly_rate_usd": "18",
                    "observed_node_hourly_rate_usd": "17.5",
                    "observed_node_hourly_rate_status": "provider_reported_nonzero",
                    "max_node_hours": "1",
                },
                "intent_artifacts": {
                    name: {"path": str(path.resolve()), "sha256": _sha256(path)}
                    for name, path in intent_paths.items()
                },
            }
        ),
        encoding="utf-8",
    )
    executable = root / "lium_create_h100_pod.py"
    executable.write_text(f"#!{sys.executable}\n", encoding="utf-8")
    executable.chmod(0o755)
    lium_cli = root / "lium"
    lium_cli.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    lium_cli.chmod(0o755)
    ssh_public_key = root / "id_ed25519.pub"
    ssh_public_key.write_text("ssh-ed25519 AAAATEST signing-test\n", encoding="utf-8")
    interpreter = Path(sys.executable).resolve()
    template = {
        "template_id": "template-h100",
        "template_image": "daturaai/pytorch",
        "template_tag": "2.12.0",
        "template_status": "VERIFY_SUCCESS",
    }
    argv = [
        str(executable.resolve()),
        "up",
        "h100-sxm",
        "--name",
        "issue-32-dispatcher",
        "--ttl",
        "1h",
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
        "17.5",
        "--expected-rate-authority",
        "provider_raw_price_per_gpu_x_gpu_count/v1",
    ]
    now = datetime.now(timezone.utc).replace(microsecond=0)
    payload: dict[str, object] = {
        "schema": PERMIT_SCHEMA,
        "stage": "lium-booking",
        "decision": "PROMOTABLE",
        "request_id": "gate0-request-0001",
        "nonce": "b" * 64,
        "issued_at": (now - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (now + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sentry_principal": "research-sentry",
        "executor_principal": "h100-runner",
        "source_sha256": _sha256(intent_paths["source"]),
        "runtime_sha256": _sha256(intent_paths["runtime"]),
        "data_sha256": _sha256(intent_paths["data"]),
        "checkpoint_sha256": _sha256(intent_paths["checkpoint"]),
        "parent_request_sha256": _sha256(parent_request),
        "executor_id": "h100-sxm",
        "provider": "lium",
        "profile": "h100-sxm",
        "provider_executable": str(executable.resolve()),
        "provider_executable_sha256": _sha256(executable),
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
        "ttl_seconds": 3600,
        "max_cost_usd": "18",
        "max_node_hourly_rate_usd": "18",
        "observed_node_hourly_rate_usd": "17.5",
        "observed_node_hourly_rate_status": "provider_reported_nonzero",
        "max_node_hours": "1",
        "provider_timeout_seconds": 300,
    }
    return (
        payload,
        private_path,
        public_path,
        gate1_public_path,
        parent_request,
        executable,
        argv,
        now,
    )


def _gate0_arguments(
    *,
    source: Path,
    output: Path,
    private_path: Path,
    public_path: Path,
    gate1_public_path: Path,
    parent_request: Path,
) -> list[str]:
    return [
        "gate0-permit",
        "--input",
        str(source),
        "--output",
        str(output),
        "--private-key",
        str(private_path),
        "--public-key",
        str(public_path),
        "--gate1-public-key",
        str(gate1_public_path),
        "--parent-request",
        str(parent_request),
        "--signer-principal",
        "research-sentry",
        "--verifier-principal",
        "h100-runner",
    ]


def test_signing_cli_signs_without_exposing_key_and_rejects_permissive_mode(
    tmp_path: Path, capsys: object
) -> None:
    private_path, public_path = _keys(tmp_path)
    source = tmp_path / "unsigned.json"
    source.write_text(
        json.dumps({"stage": "screen", "decision": "PROMOTABLE"}),
        encoding="utf-8",
    )
    output = tmp_path / "signed.json"
    arguments = [
        "screen",
        "--input",
        str(source),
        "--output",
        str(output),
        "--private-key",
        str(private_path),
        "--public-key",
        str(public_path),
        "--signer-principal",
        "research-sentry",
        "--verifier-principal",
        "h100-runner",
        "--request-id",
        "screen-request-0001",
        "--nonce",
        "a" * 64,
        "--issued-at",
        "2026-07-10T00:00:00Z",
        "--expires-at",
        "2026-07-10T01:00:00Z",
    ]

    assert signing_main(arguments) == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    signed = json.loads(output.read_text(encoding="utf-8"))
    unsigned = {
        key: value
        for key, value in signed.items()
        if key not in {"signature_base64", "signed_payload_sha256"}
    }
    verify_detached_signature(
        load_public_key_document(public_path),
        domain=signature_domain_for_kind("screen"),
        payload=unsigned,
        signature_base64=signed["signature_base64"],
    )
    private_material = private_path.read_text(encoding="utf-8")
    assert private_material not in captured.out
    assert private_material not in captured.err
    assert private_material not in output.read_text(encoding="utf-8")

    private_path.chmod(0o644)
    refused = tmp_path / "refused.json"
    bad_arguments = [*arguments]
    bad_arguments[bad_arguments.index(str(output))] = str(refused)
    assert signing_main(bad_arguments) == 2
    assert not refused.exists()
    failure = capsys.readouterr()  # type: ignore[attr-defined]
    assert "permissive" in failure.err
    assert private_material not in failure.err


def test_gate0_signing_roundtrips_exact_shared_envelope_and_detects_tamper(
    tmp_path: Path,
) -> None:
    (
        payload,
        private_path,
        public_path,
        gate1_public_path,
        parent_request,
        _,
        argv,
        now,
    ) = _gate0_fixture(tmp_path)
    source = tmp_path / "gate0-payload.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "gate0-permit.json"

    assert (
        signing_main(
            _gate0_arguments(
                source=source,
                output=output,
                private_path=private_path,
                public_path=public_path,
                gate1_public_path=gate1_public_path,
                parent_request=parent_request,
            )
        )
        == 0
    )
    envelope = json.loads(output.read_text(encoding="utf-8"))
    public_key = load_public_key_document(public_path)
    gate1_public_key = load_public_key_document(gate1_public_path)
    assert set(envelope) == {"schema", "key_id", "payload", "signature_base64"}
    assert envelope["schema"] == ENVELOPE_SCHEMA
    assert envelope["key_id"] == public_key.key_id
    assert envelope["key_id"] != gate1_public_key.key_id
    assert envelope["payload"] == payload
    verified = load_and_verify_permit(
        output,
        public_path,
        expected_key_id=public_key.key_id,
        expected_sentry_principal="research-sentry",
        expected_executor_principal="h100-runner",
        expected_executor_id="h100-sxm",
        expected_provider="lium",
        expected_profile="h100-sxm",
        expected_source_sha256=str(payload["source_sha256"]),
        expected_runtime_sha256=str(payload["runtime_sha256"]),
        expected_data_sha256=str(payload["data_sha256"]),
        expected_checkpoint_sha256=str(payload["checkpoint_sha256"]),
        parent_request_path=parent_request,
        expected_provider_version="1.2.0",
        expected_working_directory=tmp_path,
        expected_argv=argv,
        now=now,
    )
    assert verified.payload == payload

    envelope["payload"]["gpu_count"] = 7
    tampered = tmp_path / "tampered-permit.json"
    tampered.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(PermitError):
        load_and_verify_permit(
            tampered,
            public_path,
            expected_key_id=public_key.key_id,
            expected_sentry_principal="research-sentry",
            expected_executor_principal="h100-runner",
            expected_executor_id="h100-sxm",
            expected_provider="lium",
            expected_profile="h100-sxm",
            expected_source_sha256=str(payload["source_sha256"]),
            expected_runtime_sha256=str(payload["runtime_sha256"]),
            expected_data_sha256=str(payload["data_sha256"]),
            expected_checkpoint_sha256=str(payload["checkpoint_sha256"]),
            parent_request_path=parent_request,
            expected_provider_version="1.2.0",
            expected_working_directory=tmp_path,
            expected_argv=argv,
            now=now,
        )


@pytest.mark.parametrize("key_case", ["same-as-gate0", "mismatched-gate1"])
def test_gate0_signing_rejects_collapsed_or_mismatched_gate1_identity(
    tmp_path: Path, capsys: object, key_case: str
) -> None:
    (
        payload,
        private_path,
        public_path,
        _gate1_public_path,
        parent_request,
        _,
        _,
        _,
    ) = _gate0_fixture(tmp_path)
    if key_case == "same-as-gate0":
        supplied_gate1 = public_path
        booking = json.loads(parent_request.read_text(encoding="utf-8"))
        gate0_public = load_public_key_document(public_path)
        booking["gate1_trust"].update(
            {
                "public_key_sha256": _sha256(public_path),
                "key_id": gate0_public.key_id,
            }
        )
        parent_request.write_text(json.dumps(booking), encoding="utf-8")
        payload["parent_request_sha256"] = _sha256(parent_request)
    else:
        _, supplied_gate1 = _keys(tmp_path, "untrusted-gate1")
    source = tmp_path / f"{key_case}-payload.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / f"{key_case}-permit.json"

    assert (
        signing_main(
            _gate0_arguments(
                source=source,
                output=output,
                private_path=private_path,
                public_path=public_path,
                gate1_public_path=supplied_gate1,
                parent_request=parent_request,
            )
        )
        == 2
    )
    assert not output.exists()
    failure = capsys.readouterr()  # type: ignore[attr-defined]
    if key_case == "same-as-gate0":
        assert "must be distinct" in failure.err
    else:
        assert "Gate0 booking request invalid" in failure.err


@pytest.mark.parametrize("mutation", ["missing", "unknown", "invalid-policy"])
def test_gate0_signing_rejects_malformed_or_unbounded_payloads(
    tmp_path: Path, capsys: object, mutation: str
) -> None:
    (
        payload,
        private_path,
        public_path,
        gate1_public_path,
        parent_request,
        _,
        _,
        _,
    ) = _gate0_fixture(tmp_path)
    if mutation == "missing":
        del payload["checkpoint_sha256"]
    elif mutation == "unknown":
        payload["unbounded_override"] = True
    else:
        payload["gpu_count"] = 7
    source = tmp_path / f"{mutation}.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / f"{mutation}-signed.json"

    assert (
        signing_main(
            _gate0_arguments(
                source=source,
                output=output,
                private_path=private_path,
                public_path=public_path,
                gate1_public_path=gate1_public_path,
                parent_request=parent_request,
            )
        )
        == 2
    )
    assert not output.exists()
    failure = capsys.readouterr()  # type: ignore[attr-defined]
    assert "signing failed" in failure.err


def test_gate0_signing_rejects_permissive_private_key(tmp_path: Path, capsys: object) -> None:
    (
        payload,
        private_path,
        public_path,
        gate1_public_path,
        parent_request,
        _,
        _,
        _,
    ) = _gate0_fixture(tmp_path)
    source = tmp_path / "gate0-payload.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / "gate0-permit.json"
    private_path.chmod(0o644)

    assert (
        signing_main(
            _gate0_arguments(
                source=source,
                output=output,
                private_path=private_path,
                public_path=public_path,
                gate1_public_path=gate1_public_path,
                parent_request=parent_request,
            )
        )
        == 2
    )
    assert not output.exists()
    failure = capsys.readouterr()  # type: ignore[attr-defined]
    assert "permissive" in failure.err


@pytest.mark.parametrize("mutation", ["minimal-parent", "self-reference", "intent-tamper"])
def test_gate0_signing_rejects_unbound_booking_intent(
    tmp_path: Path, capsys: object, mutation: str
) -> None:
    (
        payload,
        private_path,
        public_path,
        gate1_public_path,
        parent_request,
        _,
        _,
        _,
    ) = _gate0_fixture(tmp_path)
    booking = json.loads(parent_request.read_text(encoding="utf-8"))
    if mutation == "minimal-parent":
        booking = {"issue_number": 32, "allocation_name": "issue-32-dispatcher"}
        parent_request.write_text(json.dumps(booking), encoding="utf-8")
    elif mutation == "self-reference":
        booking["intent_artifacts"]["source"] = {
            "path": str(parent_request.resolve()),
            "sha256": _sha256(parent_request),
        }
        parent_request.write_text(json.dumps(booking), encoding="utf-8")
    else:
        runtime_path = Path(booking["intent_artifacts"]["runtime"]["path"])
        runtime_path.write_text(
            runtime_path.read_text(encoding="utf-8") + "\n",
            encoding="utf-8",
        )
    payload["parent_request_sha256"] = _sha256(parent_request)
    source = tmp_path / f"{mutation}-payload.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / f"{mutation}-permit.json"

    assert (
        signing_main(
            _gate0_arguments(
                source=source,
                output=output,
                private_path=private_path,
                public_path=public_path,
                gate1_public_path=gate1_public_path,
                parent_request=parent_request,
            )
        )
        == 2
    )
    assert not output.exists()
    failure = capsys.readouterr()  # type: ignore[attr-defined]
    assert "Gate0 booking request invalid" in failure.err
