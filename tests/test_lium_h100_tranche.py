from __future__ import annotations

import base64
import hashlib
import json
import os
import pwd
import secrets
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import w8_biayn.integrations.h100_signed_approval as signed_approval

from w8_biayn.integrations.h100_signed_approval import (
    ENVELOPE_SCHEMA,
    LAUNCH_RECEIPT_SCHEMA,
    PERMIT_SCHEMA,
    PUBLIC_KEY_SCHEMA,
    SIGNATURE_DOMAIN,
    PermitVerificationError,
    PermitReplayError,
    canonical_json_bytes,
    consume_permit_once,
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
PROVIDER_INTERPRETER = Path("/opt/homebrew/opt/python@3.11/bin/python3.11").resolve()
LIUM_SDK_VERSION = "0.0.3"
TEMPLATE_ID = "345273fa-4818-46f7-a8fa-32f0e331713c"
TEMPLATE_IMAGE = "daturaai/pytorch"
TEMPLATE_TAG = "2.12.0-py3.12-cuda13.0.2-devel-ubuntu24.04-dind"
TEMPLATE_STATUS = "VERIFY_SUCCESS"
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
        f"#!{PROVIDER_INTERPRETER}\n"
        "import json, os, sys, time\n"
        f"if sys.argv[1:] == ['--version']:\n    print({PROVIDER_VERSION!r}); raise SystemExit(0)\n"
        "credential = sys.stdin.buffer.readline(4098).rstrip(b'\\n')\n"
        "if not credential: raise SystemExit(77)\n"
        "row = json.dumps({\n"
        "    'argv': sys.argv[1:],\n"
        "    'cwd': os.getcwd(),\n"
        "    'env_names': sorted(os.environ),\n"
        "    'has_api_key_env': bool(os.environ.get('LIUM_API_KEY')),\n"
        "    'stdin_credential_received': bool(credential),\n"
        "}, separators=(',', ':')) + '\\n'\n"
        "fd = os.open(os.environ['FAKE_LIUM_LOG'], "
        "os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)\n"
        "try:\n"
        "    os.write(fd, row.encode('utf-8'))\n"
        "finally:\n"
        "    os.close(fd)\n"
        "state = os.environ['FAKE_ALLOCATION_STATE']\n"
        "if os.path.exists(state): raise SystemExit(73)\n"
        "open(state, 'xb').close()\n"
        "with open(os.environ['FAKE_MUTATION_LOG'], 'ab') as h: h.write(b'up\\n')\n"
        "print('fake-lium-booking-output', flush=True)\n"
        "time.sleep(float(os.environ.get('FAKE_LIUM_SLEEP', '0')))\n",
        encoding="utf-8",
    )
    fake_lium.chmod(0o755)
    fake_cli = fake_bin / "lium-cli"
    fake_cli.write_text("#!/bin/sh\nprintf 'lium, version 0.0.3\\n'\n", encoding="utf-8")
    fake_cli.chmod(0o755)
    ssh_public_key = tmp_path / "id_ed25519.pub"
    ssh_public_key.write_text("ssh-ed25519 AAAATEST gate0-test\n", encoding="utf-8")
    ssh_public_key_sha256 = hashlib.sha256(ssh_public_key.read_bytes()).hexdigest()
    invocation_log = tmp_path / "provider-invocations.jsonl"
    mutation_log = tmp_path / "provider-mutations.log"
    allocation_state = tmp_path / "allocation.state"
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
        "FAKE_MUTATION_LOG": str(mutation_log),
        "FAKE_ALLOCATION_STATE": str(allocation_state),
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
        "--template-id",
        TEMPLATE_ID,
        "--template-image",
        TEMPLATE_IMAGE,
        "--template-tag",
        TEMPLATE_TAG,
        "--template-status",
        TEMPLATE_STATUS,
        "--expected-provider-version",
        PROVIDER_VERSION,
        "--expected-interpreter-path",
        str(PROVIDER_INTERPRETER),
        "--expected-interpreter-sha256",
        hashlib.sha256(PROVIDER_INTERPRETER.read_bytes()).hexdigest(),
        "--expected-interpreter-version",
        subprocess.run(
            [str(PROVIDER_INTERPRETER), "-c", "import platform;print(platform.python_version())"],
            check=True,
            text=True,
            capture_output=True,
        ).stdout.strip(),
        "--expected-lium-sdk-version",
        LIUM_SDK_VERSION,
        "--expected-lium-cli-path",
        str(fake_cli),
        "--expected-lium-cli-sha256",
        hashlib.sha256(fake_cli.read_bytes()).hexdigest(),
        "--expected-lium-cli-version",
        LIUM_SDK_VERSION,
        "--ssh-public-key-path",
        str(ssh_public_key),
        "--ssh-public-key-sha256",
        ssh_public_key_sha256,
        "--max-rate",
        "18",
        "--expected-observed-rate",
        "18",
        "--expected-rate-authority",
        "provider_raw_price_per_gpu_x_gpu_count/v1",
    ]
    now = datetime.now(timezone.utc).replace(microsecond=0)
    payload = {
        "schema": PERMIT_SCHEMA,
        "stage": "lium-booking",
        "decision": "PROMOTABLE",
        "request_id": f"gate0-request-{secrets.token_hex(8)}",
        "nonce": secrets.token_hex(32),
        "issued_at": (now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (now + timedelta(minutes=9)).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
        "provider_interpreter": str(PROVIDER_INTERPRETER),
        "provider_interpreter_sha256": hashlib.sha256(
            PROVIDER_INTERPRETER.read_bytes()
        ).hexdigest(),
        "provider_interpreter_version": signed_argv[
            signed_argv.index("--expected-interpreter-version") + 1
        ],
        "lium_sdk_distribution": "lium.io",
        "lium_sdk_version": LIUM_SDK_VERSION,
        "lium_cli_path": str(fake_cli),
        "lium_cli_sha256": hashlib.sha256(fake_cli.read_bytes()).hexdigest(),
        "lium_cli_version": LIUM_SDK_VERSION,
        "working_directory": str(working_directory),
        "environment": signed_environment,
        "credential_transport": "stdin-line/v1",
        "ssh_public_key_path": str(ssh_public_key),
        "ssh_public_key_sha256": ssh_public_key_sha256,
        "template_id": TEMPLATE_ID,
        "template_image": TEMPLATE_IMAGE,
        "template_tag": TEMPLATE_TAG,
        "template_status": TEMPLATE_STATUS,
        "issue_number": ISSUE_NUMBER,
        "allocation_name": ALLOCATION_NAME,
        "argv": signed_argv,
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
    permit_path = tmp_path / "permit.json"
    _write_signed_permit(permit_path, private_key, key_id, payload)
    env = os.environ.copy()
    env["LIUM_API_KEY"] = "ambient-lium-key-must-not-be-used"
    env["AMBIENT_MUST_NOT_LEAK"] = "ambient-value"
    env["PYTHONPATH"] = str(ROOT / "src")
    driver = tmp_path / "wrapper-driver.py"
    driver.write_text(
        "import sys\nfrom pathlib import Path\n"
        "import w8_biayn.integrations.h100_signed_approval as module\n"
        "module.GATE0_CONSUMPTION_ROOT = Path(sys.argv[1])\n"
        "raise SystemExit(module.wrapper_main(sys.argv[2:]))\n",
        encoding="utf-8",
    )
    return {
        "private_key": private_key,
        "key_id": key_id,
        "public_key": public_key_path,
        "permit": permit_path,
        "payload": payload,
        "ledger": tmp_path / "ledger",
        "log": invocation_log,
        "mutation_log": mutation_log,
        "allocation_state": allocation_state,
        "driver": driver,
        "env": env,
        "argv": signed_argv,
        "provider_executable": fake_lium,
        "provider_interpreter": PROVIDER_INTERPRETER,
        "lium_cli": fake_cli,
        "ssh_public_key": ssh_public_key,
        "parent_request": parent_request,
        "working_directory": working_directory,
        "receipt": tmp_path / "launch-receipt.json",
        "provider_output": tmp_path / "provider-output.bin",
        "sterile_home": sterile_home,
        "credential": "supervisor-stdin-lium-key",
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
        str(harness["driver"]),
        str(harness["ledger"]),
        "--permit",
        str(harness["permit"]),
        "--public-key",
        str(public_key or harness["public_key"]),
        "--key-id",
        key_id or harness["key_id"],
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
    credential = kwargs.pop("credential", harness["credential"])
    return subprocess.run(
        _wrapper_argv(harness, **kwargs),
        env=harness["env"],
        check=False,
        text=True,
        capture_output=True,
        input=(credential + "\n") if credential else "",
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


def test_gate0_consumption_rejects_symlinked_or_permissive_ledgers(tmp_path: Path) -> None:
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
    target = tmp_path / "ledger-target"
    target.mkdir(mode=0o700)
    symlink = tmp_path / "ledger-link"
    symlink.symlink_to(target, target_is_directory=True)
    with pytest.raises(PermitReplayError, match="real private directory"):
        consume_permit_once(verified, symlink)

    symlink.unlink()
    symlink.mkdir(mode=0o755)
    symlink.chmod(0o755)
    with pytest.raises(PermitReplayError, match="owner-only"):
        consume_permit_once(verified, symlink)


def test_default_gate0_ledger_uses_real_account_home_not_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", "/tmp/attacker-home")
    monkeypatch.setenv("XDG_STATE_HOME", "/tmp/attacker-xdg")
    expected = (
        Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
        / ".local/state/w8-biayn/control-plane/gate0-consumption/v1"
    )

    assert signed_approval.GATE0_CONSUMPTION_ROOT == expected


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
    assert receipt["execution"]["credential_transport"] == "stdin-line/v1"
    environment_binding = {
        "environment": harness["payload"]["environment"],
        "credential_transport": "stdin-line/v1",
    }
    assert (
        receipt["execution"]["sanitized_environment_sha256"]
        == hashlib.sha256(canonical_json_bytes(environment_binding)).hexdigest()
    )
    assert receipt["execution"]["started_at"] <= receipt["execution"]["finished_at"]
    assert receipt["budget"]["observed_node_hourly_rate_usd"] == 18
    assert receipt["budget"]["observed_node_hourly_rate_status"] == (
        "provider_reported_nonzero"
    )
    assert receipt["budget"]["max_node_hourly_rate_usd"] == 18
    assert len(receipt["claim"]["sha256"]) == 64
    assert harness["credential"] not in receipt_text
    assert receipt["template"]["id"] == TEMPLATE_ID
    assert receipt["runtime_evidence"]["lium_sdk_version"] == LIUM_SDK_VERSION
    assert receipt["access"] == {
        "ssh_public_key_path": str(harness["ssh_public_key"]),
        "ssh_public_key_sha256": hashlib.sha256(harness["ssh_public_key"].read_bytes()).hexdigest(),
    }


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
        input="",
    )
    wrapped = _run_wrapper(harness)
    invocations = _invocations(harness)

    assert direct.returncode == 77
    assert wrapped.returncode == 0, wrapped.stderr
    assert len(invocations) == 1
    assert invocations[0]["has_api_key_env"] is False
    assert invocations[0]["stdin_credential_received"] is True
    assert set(invocations[0]["env_names"]) == set(harness["payload"]["environment"])
    assert "LIUM_API_KEY" not in invocations[0]["env_names"]
    assert "AMBIENT_MUST_NOT_LEAK" not in invocations[0]["env_names"]
    combined = direct.stdout + direct.stderr + wrapped.stdout + wrapped.stderr
    assert harness["credential"] not in combined
    assert harness["credential"] not in json.dumps(invocations)
    assert harness["credential"] not in " ".join(_wrapper_argv(harness))
    assert harness["credential"] not in harness["log"].read_text(encoding="utf-8")


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


def _permit_too_long(harness: dict[str, Any]) -> dict[str, Any]:
    issued = datetime.strptime(harness["payload"]["issued_at"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    harness["payload"]["expires_at"] = (issued + timedelta(minutes=11)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
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


def _wrong_credential_transport(harness: dict[str, Any]) -> dict[str, Any]:
    harness["payload"]["credential_transport"] = "environment/v1"
    _resign(harness)
    return {}


def _ssh_public_key_tamper(harness: dict[str, Any]) -> dict[str, Any]:
    harness["ssh_public_key"].write_text("ssh-ed25519 AAAATAMPERED gate0-test\n", encoding="utf-8")
    return {}


def _ssh_public_key_payload_substitution(harness: dict[str, Any]) -> dict[str, Any]:
    harness["payload"]["ssh_public_key_path"] = str(
        harness["ssh_public_key"].with_name("substituted.pub")
    )
    _resign(harness)
    return {}


def _missing_credential(harness: dict[str, Any]) -> dict[str, Any]:
    del harness
    return {"credential": ""}


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
    ("permit-too-long", _permit_too_long),
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
    ("credential-transport", _wrong_credential_transport),
    ("ssh-public-key-tamper", _ssh_public_key_tamper),
    ("ssh-public-key-payload", _ssh_public_key_payload_substitution),
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


def test_production_cli_rejects_fresh_ledger_selection(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    production_args = _wrapper_argv(harness)[3:]
    command = [
        sys.executable,
        str(WRAPPER),
        "--ledger-dir",
        str(tmp_path / "attacker-fresh-ledger"),
        *production_args,
    ]

    completed = subprocess.run(
        command,
        env=harness["env"],
        input=harness["credential"] + "\n",
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert _invocations(harness) == []
    assert not (tmp_path / "attacker-fresh-ledger").exists()


def test_deleted_claim_still_cannot_mutate_same_allocation_twice(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)

    first = _run_wrapper(harness)
    for claim in harness["ledger"].glob("*.consumed.json"):
        claim.unlink()
    harness["receipt"].unlink()
    harness["provider_output"].unlink()
    second = _run_wrapper(harness)

    assert first.returncode == 0
    assert second.returncode == 73
    assert harness["mutation_log"].read_text(encoding="utf-8").splitlines() == ["up"]
    assert len(_invocations(harness)) == 2


def test_script_path_swap_immediately_before_popen_executes_held_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _make_harness(tmp_path)
    permit = load_and_verify_permit(
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
    script_fd = signed_approval._open_verified_executable(permit)
    interpreter_fd = signed_approval._open_verified_interpreter(permit, script_fd)
    replacement = tmp_path / "swapped-provider"
    replacement.write_text(
        f"#!{PROVIDER_INTERPRETER}\nprint('SWAPPED-BYTES-EXECUTED')\n",
        encoding="utf-8",
    )
    replacement.chmod(0o755)
    real_popen = subprocess.Popen

    def swap_then_popen(*args, **kwargs):
        os.replace(replacement, harness["provider_executable"])
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(signed_approval.subprocess, "Popen", swap_then_popen)
    try:
        process = signed_approval._start_provider_process(
            permit,
            executable_descriptor=script_fd,
            interpreter_descriptor=interpreter_fd,
            provider_environment=harness["payload"]["environment"],
        )
        output, _ = process.communicate(input=(harness["credential"] + "\n").encode(), timeout=10)
    finally:
        os.close(interpreter_fd)
        os.close(script_fd)

    assert process.returncode == 0
    assert output == b"fake-lium-booking-output\n"
    assert b"SWAPPED-BYTES-EXECUTED" not in output


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
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(2)
    ]
    outputs = [
        process.communicate(input=harness["credential"] + "\n", timeout=10) for process in processes
    ]

    assert sorted(process.returncode for process in processes) == [0, 2]
    assert len(_invocations(harness)) == 1
    assert any("PermitReplayError" in stderr for _, stderr in outputs)
