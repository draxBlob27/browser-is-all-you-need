from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from w8_biayn.integrations.h100_research_sentry import (
    signature_domain_for_kind,
    signing_main,
)
from w8_biayn.integrations.h100_signed_approval import (
    ENVELOPE_SCHEMA,
    PERMIT_SCHEMA,
    PUBLIC_KEY_SCHEMA,
    PermitError,
    key_id_for_public_key,
    load_and_verify_permit,
    load_public_key_document,
    verify_detached_signature,
)


def _keys(root: Path) -> tuple[Path, Path]:
    private = Ed25519PrivateKey.generate()
    private_path = root / "external-private.pem"
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
    public_path = root / "public.json"
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
) -> tuple[dict[str, object], Path, Path, Path, Path, list[str], datetime]:
    private_path, public_path = _keys(root)
    parent_request = root / "booking-request.json"
    parent_request.write_text(
        json.dumps({"allocation_name": "issue-32-dispatcher", "issue_number": 32}),
        encoding="utf-8",
    )
    executable = root / "lium"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    argv = [
        str(executable.resolve()),
        "up",
        "h100-sxm",
        "--name",
        "issue-32-dispatcher",
        "--ttl",
        "1h",
    ]
    now = datetime.now(timezone.utc).replace(microsecond=0)
    payload: dict[str, object] = {
        "schema": PERMIT_SCHEMA,
        "stage": "lium-booking",
        "decision": "PROMOTABLE",
        "request_id": "gate0-request-0001",
        "nonce": "b" * 64,
        "issued_at": (now - timedelta(seconds=30)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sentry_principal": "research-sentry",
        "executor_principal": "h100-runner",
        "source_sha256": hashlib.sha256(b"source").hexdigest(),
        "runtime_sha256": hashlib.sha256(b"runtime").hexdigest(),
        "data_sha256": hashlib.sha256(b"data").hexdigest(),
        "checkpoint_sha256": hashlib.sha256(b"checkpoint").hexdigest(),
        "parent_request_sha256": _sha256(parent_request),
        "executor_id": "h100-sxm",
        "provider": "lium",
        "profile": "h100-sxm",
        "provider_executable": str(executable.resolve()),
        "provider_executable_sha256": _sha256(executable),
        "provider_version": "1.2.3",
        "working_directory": str(root.resolve()),
        "environment": {},
        "secret_env_names": ["LIUM_API_KEY"],
        "issue_number": 32,
        "allocation_name": "issue-32-dispatcher",
        "argv": argv,
        "gpu_type": "H100",
        "gpu_count": 8,
        "ttl_seconds": 3600,
        "max_cost_usd": "18",
        "max_node_hourly_rate_usd": "18",
        "observed_node_hourly_rate_usd": "17.5",
        "max_node_hours": "1",
        "provider_timeout_seconds": 300,
    }
    return (
        payload,
        private_path,
        public_path,
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
                parent_request=parent_request,
            )
        )
        == 0
    )
    envelope = json.loads(output.read_text(encoding="utf-8"))
    public_key = load_public_key_document(public_path)
    assert set(envelope) == {"schema", "key_id", "payload", "signature_base64"}
    assert envelope["schema"] == ENVELOPE_SCHEMA
    assert envelope["key_id"] == public_key.key_id
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
        expected_provider_version="1.2.3",
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
            expected_provider_version="1.2.3",
            expected_working_directory=tmp_path,
            expected_argv=argv,
            now=now,
        )


@pytest.mark.parametrize("mutation", ["missing", "unknown", "invalid-policy"])
def test_gate0_signing_rejects_malformed_or_unbounded_payloads(
    tmp_path: Path, capsys: object, mutation: str
) -> None:
    payload, private_path, public_path, parent_request, _, _, _ = _gate0_fixture(tmp_path)
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
                parent_request=parent_request,
            )
        )
        == 2
    )
    assert not output.exists()
    failure = capsys.readouterr()  # type: ignore[attr-defined]
    assert "signing failed" in failure.err


def test_gate0_signing_rejects_permissive_private_key(tmp_path: Path, capsys: object) -> None:
    payload, private_path, public_path, parent_request, _, _, _ = _gate0_fixture(tmp_path)
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
                parent_request=parent_request,
            )
        )
        == 2
    )
    assert not output.exists()
    failure = capsys.readouterr()  # type: ignore[attr-defined]
    assert "permissive" in failure.err
