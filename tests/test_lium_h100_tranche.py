from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from w8_biayn.integrations.h100_signed_approval import (
    ENVELOPE_SCHEMA,
    LAUNCH_RECEIPT_SCHEMA,
    PERMIT_SCHEMA,
    PUBLIC_KEY_SCHEMA,
    SIGNATURE_DOMAIN,
    PermitVerificationError,
    canonical_json_bytes,
    domain_separated_message,
    key_id_for_public_key,
    load_and_verify_permit,
    load_public_key_document,
    permit_signing_message,
    verify_detached_signature,
)


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts/run_lium_h100_tranche.py"
SENTRY_PRINCIPAL = "h100-research-sentry"
EXECUTOR_PRINCIPAL = "codex-e04-executor"
EXECUTOR_ID = "lium-executor-h100-0007"
PROVIDER = "lium"
PROFILE = "h100-sxm-80gb-8x"
PROVIDER_VERSION = "lium-test-1.2.3"
ISSUE_NUMBER = 32
ALLOCATION_NAME = "issue-32-e04a-gate0"
SOURCE_SHA256 = "1" * 64
RUNTIME_SHA256 = "2" * 64
DATA_SHA256 = "3" * 64
CHECKPOINT_SHA256 = "4" * 64


def _public_bytes(private_key: Ed25519PrivateKey) -> bytes:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _write_signed_permit(
    path: Path,
    private_key: Ed25519PrivateKey,
    key_id: str,
    payload: dict[str, Any],
) -> None:
    signature = private_key.sign(permit_signing_message(payload))
    envelope = {
        "schema": ENVELOPE_SCHEMA,
        "key_id": key_id,
        "payload": payload,
        "signature_base64": base64.b64encode(signature).decode("ascii"),
    }
    path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _make_harness(tmp_path: Path) -> dict[str, Any]:
    private_key = Ed25519PrivateKey.generate()
    public_bytes = _public_bytes(private_key)
    key_id = key_id_for_public_key(public_bytes)
    public_key_path = tmp_path / "public-key.json"
    public_key_path.write_text(
        json.dumps(
            {
                "schema": PUBLIC_KEY_SCHEMA,
                "algorithm": "Ed25519",
                "key_id": key_id,
                "public_key_base64": base64.b64encode(public_bytes).decode("ascii"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_lium = fake_bin / "lium"
    fake_lium.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys, time\n"
        "row = json.dumps({\n"
        "    'argv': sys.argv[1:],\n"
        "    'cwd': os.getcwd(),\n"
        "    'env_names': sorted(os.environ),\n"
        "    'has_api_key': bool(os.environ.get('LIUM_API_KEY')),\n"
        "}, separators=(',', ':')) + '\\n'\n"
        "fd = os.open(os.environ['FAKE_LIUM_LOG'], "
        "os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)\n"
        "try:\n"
        "    os.write(fd, row.encode('utf-8'))\n"
        "finally:\n"
        "    os.close(fd)\n"
        "if not os.environ.get('LIUM_API_KEY'):\n"
        "    raise SystemExit(77)\n"
        "print('fake-lium-booking-output', flush=True)\n"
        "time.sleep(float(os.environ.get('FAKE_LIUM_SLEEP', '0')))\n",
        encoding="utf-8",
    )
    fake_lium.chmod(0o755)
    invocation_log = tmp_path / "provider-invocations.jsonl"
    parent_request = tmp_path / "booking-request.json"
    parent_request.write_text(
        json.dumps({"request_id": "parent-e04a", "issue_number": ISSUE_NUMBER}) + "\n",
        encoding="utf-8",
    )
    working_directory = tmp_path / "provider-cwd"
    working_directory.mkdir()
    sterile_home = tmp_path / "sterile-home"
    sterile_home.mkdir()
    signed_environment = {
        "LC_CTYPE": "UTF-8",
        "FAKE_LIUM_LOG": str(invocation_log),
        "FAKE_LIUM_SLEEP": "0",
        "HOME": str(sterile_home),
        "SIGNED_ENV_MARKER": "gate0",
        "__CF_USER_TEXT_ENCODING": f"0x{os.getuid():X}:0:0",
    }
    signed_argv = [
        str(fake_lium),
        "up",
        EXECUTOR_ID,
        "--ttl",
        "2h",
        "--name",
        ALLOCATION_NAME,
        "--yes",
    ]
    now = datetime.now(timezone.utc).replace(microsecond=0)
    payload = {
        "schema": PERMIT_SCHEMA,
        "stage": "lium-booking",
        "decision": "PROMOTABLE",
        "request_id": f"gate0-request-{secrets.token_hex(8)}",
        "nonce": secrets.token_hex(32),
        "issued_at": (now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (now + timedelta(minutes=59)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sentry_principal": SENTRY_PRINCIPAL,
        "executor_principal": EXECUTOR_PRINCIPAL,
        "source_sha256": SOURCE_SHA256,
        "runtime_sha256": RUNTIME_SHA256,
        "data_sha256": DATA_SHA256,
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "parent_request_sha256": hashlib.sha256(parent_request.read_bytes()).hexdigest(),
        "executor_id": EXECUTOR_ID,
        "provider": PROVIDER,
        "profile": PROFILE,
        "provider_executable": str(fake_lium),
        "provider_executable_sha256": hashlib.sha256(fake_lium.read_bytes()).hexdigest(),
        "provider_version": PROVIDER_VERSION,
        "working_directory": str(working_directory),
        "environment": signed_environment,
        "secret_env_names": ["LIUM_API_KEY"],
        "issue_number": ISSUE_NUMBER,
        "allocation_name": ALLOCATION_NAME,
        "argv": signed_argv,
        "gpu_type": "H100",
        "gpu_count": 8,
        "ttl_seconds": 7200,
        "max_cost_usd": 36,
        "max_node_hourly_rate_usd": 18,
        "observed_node_hourly_rate_usd": 0,
        "max_node_hours": 2,
        "provider_timeout_seconds": 300,
    }
    permit_path = tmp_path / "permit.json"
    _write_signed_permit(permit_path, private_key, key_id, payload)
    env = os.environ.copy()
    env["LIUM_API_KEY"] = "lium-secret-test-value"
    env["AMBIENT_MUST_NOT_LEAK"] = "ambient-value"
    env["PYTHONPATH"] = str(ROOT / "src")
    return {
        "private_key": private_key,
        "key_id": key_id,
        "public_key": public_key_path,
        "permit": permit_path,
        "payload": payload,
        "ledger": tmp_path / "ledger",
        "log": invocation_log,
        "env": env,
        "argv": signed_argv,
        "provider_executable": fake_lium,
        "parent_request": parent_request,
        "working_directory": working_directory,
        "receipt": tmp_path / "launch-receipt.json",
        "provider_output": tmp_path / "provider-output.bin",
        "sterile_home": sterile_home,
    }


def _wrapper_argv(
    harness: dict[str, Any],
    *,
    command: list[str] | None = None,
    key_id: str | None = None,
    public_key: Path | None = None,
    sentry_principal: str = SENTRY_PRINCIPAL,
    executor_principal: str = EXECUTOR_PRINCIPAL,
    executor_id: str = EXECUTOR_ID,
    provider: str = PROVIDER,
    profile: str = PROFILE,
    source_sha256: str = SOURCE_SHA256,
    runtime_sha256: str = RUNTIME_SHA256,
    data_sha256: str = DATA_SHA256,
    checkpoint_sha256: str = CHECKPOINT_SHA256,
    parent_request: Path | None = None,
    provider_version: str = PROVIDER_VERSION,
    working_directory: Path | None = None,
    receipt: Path | None = None,
    provider_output: Path | None = None,
) -> list[str]:
    return [
        sys.executable,
        str(WRAPPER),
        "--permit",
        str(harness["permit"]),
        "--public-key",
        str(public_key or harness["public_key"]),
        "--key-id",
        key_id or harness["key_id"],
        "--ledger-dir",
        str(harness["ledger"]),
        "--sentry-principal",
        sentry_principal,
        "--executor-principal",
        executor_principal,
        "--executor-id",
        executor_id,
        "--provider",
        provider,
        "--profile",
        profile,
        "--source-sha256",
        source_sha256,
        "--runtime-sha256",
        runtime_sha256,
        "--data-sha256",
        data_sha256,
        "--checkpoint-sha256",
        checkpoint_sha256,
        "--parent-request",
        str(parent_request or harness["parent_request"]),
        "--provider-version",
        provider_version,
        "--working-directory",
        str(working_directory or harness["working_directory"]),
        "--receipt",
        str(receipt or harness["receipt"]),
        "--provider-output",
        str(provider_output or harness["provider_output"]),
        "--",
        *(command or harness["argv"]),
    ]


def _run_wrapper(
    harness: dict[str, Any],
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _wrapper_argv(harness, **kwargs),
        env=harness["env"],
        check=False,
        text=True,
        capture_output=True,
    )


def _invocations(harness: dict[str, Any]) -> list[dict[str, Any]]:
    if not harness["log"].is_file():
        return []
    return [
        json.loads(line) for line in harness["log"].read_text(encoding="utf-8").splitlines() if line
    ]


def _resign(harness: dict[str, Any]) -> None:
    _write_signed_permit(
        harness["permit"],
        harness["private_key"],
        harness["key_id"],
        harness["payload"],
    )


def test_production_verifier_accepts_canonical_ed25519_permit(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)

    verified = load_and_verify_permit(
        harness["permit"],
        harness["public_key"],
        expected_key_id=harness["key_id"],
        expected_sentry_principal=SENTRY_PRINCIPAL,
        expected_executor_principal=EXECUTOR_PRINCIPAL,
        expected_executor_id=EXECUTOR_ID,
        expected_provider=PROVIDER,
        expected_profile=PROFILE,
        expected_source_sha256=SOURCE_SHA256,
        expected_runtime_sha256=RUNTIME_SHA256,
        expected_data_sha256=DATA_SHA256,
        expected_checkpoint_sha256=CHECKPOINT_SHA256,
        parent_request_path=harness["parent_request"],
        expected_provider_version=PROVIDER_VERSION,
        expected_working_directory=harness["working_directory"],
        expected_argv=harness["argv"],
    )

    assert verified.argv == tuple(harness["argv"])
    assert verified.request_id == harness["payload"]["request_id"]
    assert canonical_json_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
    assert permit_signing_message(harness["payload"]).startswith(SIGNATURE_DOMAIN)


def test_public_detached_verifier_supports_independent_sentry_domains(
    tmp_path: Path,
) -> None:
    harness = _make_harness(tmp_path)
    preflight_domain = b"w8-biayn/h100-sentry/preflight/v1\x00"
    screen_domain = b"w8-biayn/h100-sentry/screen/v1\x00"
    payload = {"stage": "preflight", "decision": "PROMOTABLE", "request": "r-1"}
    signature = harness["private_key"].sign(domain_separated_message(preflight_domain, payload))
    signature_base64 = base64.b64encode(signature).decode("ascii")
    public_key = load_public_key_document(harness["public_key"], expected_key_id=harness["key_id"])

    assert (
        verify_detached_signature(
            public_key,
            domain=preflight_domain,
            payload=payload,
            signature_base64=signature_base64,
        )
        == harness["key_id"]
    )
    with pytest.raises(PermitVerificationError):
        verify_detached_signature(
            public_key,
            domain=screen_domain,
            payload=payload,
            signature_base64=signature_base64,
        )


def test_valid_permit_invokes_exact_signed_argv_once(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)

    completed = _run_wrapper(harness)

    assert completed.returncode == 0, completed.stderr
    invocations = _invocations(harness)
    assert len(invocations) == 1
    assert invocations[0]["argv"] == harness["argv"][1:]
    assert invocations[0]["cwd"] == str(harness["working_directory"])
    assert len(list(harness["ledger"].glob("*.consumed.json"))) == 1


def test_launch_receipt_binds_evidence_without_secret_values(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)

    completed = _run_wrapper(harness)
    receipt_text = harness["receipt"].read_text(encoding="utf-8")
    receipt = json.loads(receipt_text)

    assert completed.returncode == 0
    assert completed.stdout == ""
    assert receipt["schema"] == LAUNCH_RECEIPT_SCHEMA
    assert receipt["status"] == "COMPLETED"
    assert receipt["permit"]["sha256"] == hashlib.sha256(harness["permit"].read_bytes()).hexdigest()
    assert receipt["parent_request"]["sha256"] == harness["payload"]["parent_request_sha256"]
    assert (
        receipt["provider"]["executable_sha256"] == harness["payload"]["provider_executable_sha256"]
    )
    assert receipt["provider"]["declared_version"] == PROVIDER_VERSION
    assert harness["provider_output"].read_bytes() == b"fake-lium-booking-output\n"
    assert receipt["provider_output"]["path"] == str(harness["provider_output"])
    assert (
        receipt["provider_output"]["sha256"]
        == hashlib.sha256(b"fake-lium-booking-output\n").hexdigest()
    )
    assert receipt["provider_output"]["size_bytes"] == len(b"fake-lium-booking-output\n")
    assert receipt["execution"]["cwd"] == str(harness["working_directory"])
    assert receipt["execution"]["argv"] == harness["argv"]
    assert receipt["execution"]["exit_code"] == 0
    assert receipt["execution"]["wrapper_exit_code"] == 0
    assert receipt["execution"]["secret_env_names"] == ["LIUM_API_KEY"]
    environment_binding = {
        "environment": harness["payload"]["environment"],
        "secret_env_names": ["LIUM_API_KEY"],
    }
    assert (
        receipt["execution"]["sanitized_environment_sha256"]
        == hashlib.sha256(canonical_json_bytes(environment_binding)).hexdigest()
    )
    assert receipt["execution"]["started_at"] <= receipt["execution"]["finished_at"]
    assert receipt["budget"]["observed_node_hourly_rate_usd"] == 0
    assert receipt["budget"]["max_node_hourly_rate_usd"] == 18
    assert len(receipt["claim"]["sha256"]) == 64
    assert "lium-secret-test-value" not in receipt_text


def test_provider_timeout_preserves_output_and_durable_failure_receipt(
    tmp_path: Path,
) -> None:
    harness = _make_harness(tmp_path)
    harness["payload"]["environment"]["FAKE_LIUM_SLEEP"] = "2"
    harness["payload"]["provider_timeout_seconds"] = 1
    _resign(harness)

    completed = _run_wrapper(harness)
    output = harness["provider_output"].read_bytes()
    receipt = json.loads(harness["receipt"].read_text(encoding="utf-8"))

    assert completed.returncode == 124
    assert receipt["status"] == "PROVIDER_TIMEOUT"
    assert receipt["execution"]["timed_out"] is True
    assert receipt["execution"]["exit_code"] != 0
    assert receipt["execution"]["wrapper_exit_code"] == 124
    assert receipt["execution"]["provider_timeout_seconds"] == 1
    assert output == b"fake-lium-booking-output\n"
    assert receipt["provider_output"]["sha256"] == hashlib.sha256(output).hexdigest()
    assert receipt["provider_output"]["size_bytes"] == len(output)
    assert len(_invocations(harness)) == 1


def test_provider_output_tamper_is_detectable_from_receipt_hash(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)

    completed = _run_wrapper(harness)
    receipt = json.loads(harness["receipt"].read_text(encoding="utf-8"))
    recorded_hash = receipt["provider_output"]["sha256"]
    harness["provider_output"].write_bytes(b"tampered-output\n")

    assert completed.returncode == 0
    assert hashlib.sha256(harness["provider_output"].read_bytes()).hexdigest() != recorded_hash


def test_credential_custody_blocks_direct_bypass_and_injects_only_declared_secret(
    tmp_path: Path,
) -> None:
    harness = _make_harness(tmp_path)
    direct_environment = dict(harness["payload"]["environment"])

    direct = subprocess.run(
        harness["argv"],
        env=direct_environment,
        cwd=harness["working_directory"],
        check=False,
        text=True,
        capture_output=True,
    )
    wrapped = _run_wrapper(harness)
    invocations = _invocations(harness)

    assert direct.returncode == 77
    assert wrapped.returncode == 0, wrapped.stderr
    assert len(invocations) == 2
    assert invocations[0]["has_api_key"] is False
    assert invocations[1]["has_api_key"] is True
    assert set(invocations[1]["env_names"]) == {
        *harness["payload"]["environment"],
        "LIUM_API_KEY",
    }
    assert "AMBIENT_MUST_NOT_LEAK" not in invocations[1]["env_names"]


def _tamper(harness: dict[str, Any]) -> dict[str, Any]:
    envelope = json.loads(harness["permit"].read_text(encoding="utf-8"))
    envelope["payload"]["source_sha256"] = "f" * 64
    harness["permit"].write_text(json.dumps(envelope), encoding="utf-8")
    return {}


def _expire(harness: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    harness["payload"]["issued_at"] = (now - timedelta(minutes=61)).strftime("%Y-%m-%dT%H:%M:%SZ")
    harness["payload"]["expires_at"] = (now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _resign(harness)
    return {}


def _wrong_stage(harness: dict[str, Any]) -> dict[str, Any]:
    harness["payload"]["stage"] = "preflight"
    _resign(harness)
    return {}


def _wrong_principal(harness: dict[str, Any]) -> dict[str, Any]:
    harness["payload"]["executor_principal"] = "different-executor"
    _resign(harness)
    return {}


def _wrong_command(harness: dict[str, Any]) -> dict[str, Any]:
    command = [
        str(harness["provider_executable"]),
        "ps",
        EXECUTOR_ID,
        "--ttl",
        "2h",
        "--name",
        ALLOCATION_NAME,
    ]
    harness["payload"]["argv"] = command
    _resign(harness)
    return {"command": command}


def _wrong_profile(harness: dict[str, Any]) -> dict[str, Any]:
    harness["payload"]["profile"] = "h100-single"
    _resign(harness)
    return {}


def _wrong_provider(harness: dict[str, Any]) -> dict[str, Any]:
    harness["payload"]["provider"] = "other-provider"
    _resign(harness)
    return {}


def _wrong_hardware(harness: dict[str, Any]) -> dict[str, Any]:
    harness["payload"]["gpu_count"] = 4
    _resign(harness)
    return {}


def _over_budget(harness: dict[str, Any]) -> dict[str, Any]:
    harness["payload"]["max_cost_usd"] = 36.01
    _resign(harness)
    return {}


def _wrong_key_id(harness: dict[str, Any]) -> dict[str, Any]:
    envelope = json.loads(harness["permit"].read_text(encoding="utf-8"))
    envelope["key_id"] = "ed25519-sha256:" + "0" * 64
    harness["permit"].write_text(json.dumps(envelope), encoding="utf-8")
    return {}


def _wrong_runtime_binding(harness: dict[str, Any]) -> dict[str, Any]:
    del harness
    return {"runtime_sha256": "e" * 64}


def _selection_override(harness: dict[str, Any]) -> dict[str, Any]:
    command = [
        str(harness["provider_executable"]),
        "up",
        EXECUTOR_ID,
        "--gpu",
        "B200",
        "--ttl",
        "2h",
        "--name",
        ALLOCATION_NAME,
        "--yes",
    ]
    harness["payload"]["argv"] = command
    _resign(harness)
    return {"command": command}


def _wrong_domain(harness: dict[str, Any]) -> dict[str, Any]:
    envelope = json.loads(harness["permit"].read_text(encoding="utf-8"))
    signature = harness["private_key"].sign(canonical_json_bytes(harness["payload"]))
    envelope["signature_base64"] = base64.b64encode(signature).decode("ascii")
    harness["permit"].write_text(json.dumps(envelope), encoding="utf-8")
    return {}


def _parent_tamper(harness: dict[str, Any]) -> dict[str, Any]:
    harness["parent_request"].write_text('{"tampered":true}\n', encoding="utf-8")
    return {}


def _executable_tamper(harness: dict[str, Any]) -> dict[str, Any]:
    with harness["provider_executable"].open("a", encoding="utf-8") as handle:
        handle.write("# tampered\n")
    return {}


def _executable_path_substitution(harness: dict[str, Any]) -> dict[str, Any]:
    substitute = harness["provider_executable"].with_name("lium-substitute")
    substitute.write_bytes(harness["provider_executable"].read_bytes())
    substitute.chmod(0o755)
    command = [str(substitute), *harness["argv"][1:]]
    return {"command": command}


def _wrong_cwd(harness: dict[str, Any]) -> dict[str, Any]:
    other = harness["working_directory"].with_name("other-cwd")
    other.mkdir()
    return {"working_directory": other}


def _dangerous_environment(harness: dict[str, Any]) -> dict[str, Any]:
    harness["payload"]["environment"]["LD_PRELOAD"] = "/tmp/not-allowed.so"
    _resign(harness)
    return {}


def _unknown_secret_name(harness: dict[str, Any]) -> dict[str, Any]:
    harness["payload"]["secret_env_names"] = ["LIUM_API_KEY", "AWS_SECRET_ACCESS_KEY"]
    _resign(harness)
    return {}


def _missing_credential(harness: dict[str, Any]) -> dict[str, Any]:
    harness["env"].pop("LIUM_API_KEY")
    return {}


def _wrong_version(harness: dict[str, Any]) -> dict[str, Any]:
    return {"provider_version": "lium-test-9.9.9"}


def _wrong_allocation_owner(harness: dict[str, Any]) -> dict[str, Any]:
    harness["payload"]["allocation_name"] = "issue-99-not-owned"
    command = list(harness["argv"])
    command[command.index(ALLOCATION_NAME)] = "issue-99-not-owned"
    harness["payload"]["argv"] = command
    _resign(harness)
    return {"command": command}


def _timeout_over_policy(harness: dict[str, Any]) -> dict[str, Any]:
    harness["payload"]["provider_timeout_seconds"] = 301
    _resign(harness)
    return {}


REJECTED_CASES: tuple[tuple[str, Callable[[dict[str, Any]], dict[str, Any]]], ...] = (
    ("tamper", _tamper),
    ("expiry", _expire),
    ("stage", _wrong_stage),
    ("principal", _wrong_principal),
    ("command", _wrong_command),
    ("profile", _wrong_profile),
    ("provider", _wrong_provider),
    ("hardware", _wrong_hardware),
    ("budget", _over_budget),
    ("key-id", _wrong_key_id),
    ("runtime-binding", _wrong_runtime_binding),
    ("selection-override", _selection_override),
    ("signature-domain", _wrong_domain),
    ("parent-tamper", _parent_tamper),
    ("executable-tamper", _executable_tamper),
    ("executable-path", _executable_path_substitution),
    ("cwd", _wrong_cwd),
    ("environment", _dangerous_environment),
    ("unknown-secret", _unknown_secret_name),
    ("missing-credential", _missing_credential),
    ("version", _wrong_version),
    ("allocation-owner", _wrong_allocation_owner),
    ("timeout-over-policy", _timeout_over_policy),
)


@pytest.mark.parametrize(("case", "mutate"), REJECTED_CASES, ids=[row[0] for row in REJECTED_CASES])
def test_rejected_permits_never_invoke_provider(
    tmp_path: Path,
    case: str,
    mutate: Callable[[dict[str, Any]], dict[str, Any]],
) -> None:
    del case
    harness = _make_harness(tmp_path)
    wrapper_overrides = mutate(harness)

    completed = _run_wrapper(harness, **wrapper_overrides)

    assert completed.returncode != 0
    assert _invocations(harness) == []
    assert not harness["ledger"].exists() or not list(harness["ledger"].iterdir())


def test_wrong_public_key_never_invokes_provider(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    other_private_key = Ed25519PrivateKey.generate()
    other_public_bytes = _public_bytes(other_private_key)
    other_key_id = key_id_for_public_key(other_public_bytes)
    other_public_path = tmp_path / "other-public-key.json"
    other_public_path.write_text(
        json.dumps(
            {
                "schema": PUBLIC_KEY_SCHEMA,
                "algorithm": "Ed25519",
                "key_id": other_key_id,
                "public_key_base64": base64.b64encode(other_public_bytes).decode("ascii"),
            }
        ),
        encoding="utf-8",
    )

    completed = _run_wrapper(
        harness,
        public_key=other_public_path,
        key_id=other_key_id,
    )

    assert completed.returncode != 0
    assert _invocations(harness) == []


def test_replay_is_rejected_without_second_provider_invocation(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)

    first = _run_wrapper(harness)
    before_replay = len(_invocations(harness))
    replay = _run_wrapper(harness)

    assert first.returncode == 0
    assert replay.returncode != 0
    assert "PermitReplayError" in replay.stderr
    assert before_replay == 1
    assert len(_invocations(harness)) == before_replay


def test_concurrent_use_invokes_provider_at_most_once(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    harness["payload"]["environment"]["FAKE_LIUM_SLEEP"] = "0.2"
    _resign(harness)
    command = _wrapper_argv(harness)

    processes = [
        subprocess.Popen(
            command,
            env=harness["env"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(2)
    ]
    outputs = [process.communicate(timeout=10) for process in processes]

    assert sorted(process.returncode for process in processes) == [0, 2]
    assert len(_invocations(harness)) == 1
    assert any("PermitReplayError" in stderr for _, stderr in outputs)
