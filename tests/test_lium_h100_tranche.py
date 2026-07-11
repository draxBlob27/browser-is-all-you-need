from __future__ import annotations

import base64
import fcntl
import hashlib
import json
import os
import pwd
import secrets
import signal
import subprocess
import sys
import time
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
        "state_path = os.environ['FAKE_ALLOCATION_STATE']\n"
        "def load_state():\n"
        "    if not os.path.exists(state_path): return []\n"
        "    with open(state_path, encoding='utf-8') as handle: return json.load(handle)\n"
        "def save_state(rows):\n"
        "    if rows:\n"
        "        with open(state_path, 'w', encoding='utf-8') as handle: json.dump(rows, handle)\n"
        "    elif os.path.exists(state_path): os.unlink(state_path)\n"
        "def option(name): return sys.argv[sys.argv.index(name) + 1]\n"
        "if sys.argv[1:2] == ['reconcile']:\n"
        "    mode, name = option('--mode'), option('--name')\n"
        "    rows = load_state()\n"
        "    matches = [row for row in rows if row.get('name') == name]\n"
        "    if mode == 'snapshot':\n"
        "        ids = sorted(row['id'] for row in matches)\n"
        "        status = 'SNAPSHOT_CLEAR' if not ids else 'ERROR'\n"
        "        record = {'schema':'lium-h100-allocation-reconciliation/v1',"
        "'status':status,'mode':mode,'allocation_name':name,"
        "'preexisting_exact_name_ids':ids}\n"
        "        print(json.dumps(record), flush=True)\n"
        "        raise SystemExit(0 if not ids else 4)\n"
        "    once_file = os.environ.get('FAKE_RECONCILIATION_FAILURE_ONCE_FILE')\n"
        "    if once_file and not os.path.exists(once_file):\n"
        "        open(once_file, 'xb').close()\n"
        "        record = {'schema':'lium-h100-allocation-reconciliation/v1',"
        "'status':'ERROR','mode':mode,'allocation_name':name,"
        "'error':'allocation_cleanup_unconfirmed','details':{}}\n"
        "        print(json.dumps(record, separators=(',', ':')), flush=True); raise SystemExit(70)\n"
        "    if os.environ.get('FAKE_RECONCILIATION_FAILURE') == 'partial':\n"
        "        print('{\\\"schema\\\":', flush=True); raise SystemExit(70)\n"
        "    if os.environ.get('FAKE_RECONCILIATION_FAILURE') == 'lookup':\n"
        "        record = {'schema':'lium-h100-allocation-reconciliation/v1',"
        "'status':'ERROR','mode':mode,'allocation_name':name,"
        "'error':'allocation_cleanup_unconfirmed','details':{}}\n"
        "        print(json.dumps(record, separators=(',', ':')), flush=True); raise SystemExit(70)\n"
        "    cleanup_marker = os.environ.get('FAKE_CLEANUP_BEFORE_MUTATION_MARKER')\n"
        "    if cleanup_marker:\n"
        "        open(cleanup_marker, 'ab').close()\n"
        "        cleanup_release = os.environ.get('FAKE_CLEANUP_BEFORE_MUTATION_RELEASE')\n"
        "        while cleanup_release and not os.path.exists(cleanup_release): time.sleep(0.01)\n"
        "    preexisting = {sys.argv[index + 1] for index, token in enumerate(sys.argv[:-1]) "
        "if token == '--preexisting-id'}\n"
        "    attributable = [row for row in matches if row['id'] not in preexisting]\n"
        "    save_state([row for row in rows if row not in attributable])\n"
        "    final_ids = sorted(row['id'] for row in load_state() "
        "if row.get('name') == name and row['id'] not in preexisting)\n"
        "    record = {'schema':'lium-h100-allocation-reconciliation/v1',"
        "'status':'CONFIRMED_ABSENT' if not final_ids else 'ERROR','mode':mode,"
        "'allocation_name':name,'preexisting_exact_name_ids':sorted(preexisting),"
        "'observed_attributable_ids':sorted(row['id'] for row in attributable),"
        "'terminated_attributable_ids':sorted(row['id'] for row in attributable),"
        "'final_attributable_ids':final_ids,'lookup_failures':0,'termination_failures':0}\n"
        "    print(json.dumps(record, separators=(',', ':')), flush=True)\n"
        "    raise SystemExit(0 if not final_ids else 71)\n"
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
        "before_rent_marker = os.environ.get('FAKE_BEFORE_RENT_MARKER')\n"
        "if before_rent_marker:\n"
        "    open(before_rent_marker, 'ab').close()\n"
        "    before_rent_release = os.environ.get('FAKE_BEFORE_RENT_RELEASE')\n"
        "    while before_rent_release and not os.path.exists(before_rent_release): time.sleep(0.01)\n"
        "if load_state(): raise SystemExit(73)\n"
        "name, pod_id = option('--name'), 'fake-pod-123'\n"
        "extra_ids = [value for value in "
        "os.environ.get('FAKE_EXTRA_ALLOCATION_IDS', '').split(',') if value]\n"
        "save_state([{'id':value,'name':name} for value in [pod_id, *extra_ids]])\n"
        "with open(os.environ['FAKE_MUTATION_LOG'], 'ab') as h: h.write(b'up\\n')\n"
        "raw_executor_id = os.environ.get('FAKE_RAW_EXECUTOR_ID', sys.argv[2])\n"
        "raw_rate = {'authority':option('--expected-rate-authority'),"
        "'executor_id':raw_executor_id,'gpu_count':8,'available_gpu_count':8,"
        "'price_per_gpu':2.25,'price_per_hour':float(option('--expected-observed-rate')),"
        "'pending_price_change':False}\n"
        "after_rate = dict(raw_rate); after_rate['available_gpu_count'] = 0\n"
        "record = {\n"
        " 'schema':'lium-h100-pod-create/v2','status':'RUNNING',\n"
        " 'pod':{'id':pod_id,'name':name,'huid':'fake-huid','ssh_cmd':'ssh fake'},\n"
        " 'executor':{'id':raw_executor_id,'huid':sys.argv[2],'gpu_count':8,"
        "'observed_rate_usd_per_hour':float(option('--expected-observed-rate')),"
        "'max_rate_usd_per_hour':float(option('--max-rate')),"
        "'rate_authority':option('--expected-rate-authority'),"
        "'rate_evidence':{key:value for key,value in raw_rate.items() if key != 'authority'},"
        "'rent_boundary':{'status':'VERIFIED_PRE_AND_POST',"
        "'endpoint':f'/executors/{raw_executor_id}/rent',"
        "'before_post':raw_rate,'after_post':after_rate}},\n"
        " 'template':{'id':option('--template-id'),'docker_image':option('--template-image'),"
        "'docker_image_tag':option('--template-tag'),'status':option('--template-status')},\n"
        " 'access':{'ssh_public_key_path':option('--ssh-public-key-path'),"
        "'ssh_public_key_sha256':option('--ssh-public-key-sha256')},\n"
        " 'schedule':{'ttl_seconds':7200},\n"
        " 'create_reconciliation':{'status':'CONFIRMED_UNIQUE','allocation_name':name,"
        "'pod_id':pod_id,'final_active_pod_ids':[pod_id]}\n"
        "}\n"
        "boundary_tamper = os.environ.get('FAKE_RENT_BOUNDARY_TAMPER')\n"
        "if boundary_tamper == 'missing': del record['executor']['rent_boundary']\n"
        "elif boundary_tamper == 'status': "
        "record['executor']['rent_boundary']['status'] = 'UNVERIFIED'\n"
        "elif boundary_tamper == 'endpoint': "
        "record['executor']['rent_boundary']['endpoint'] = '/executors/attacker/rent'\n"
        "elif boundary_tamper == 'after_rate': "
        "record['executor']['rent_boundary']['after_post']['price_per_hour'] = 17\n"
        "elif boundary_tamper == 'after_availability': "
        "record['executor']['rent_boundary']['after_post']['available_gpu_count'] = 9\n"
        "elif boundary_tamper == 'after_gpu_count_type': "
        "record['executor']['rent_boundary']['after_post']['gpu_count'] = 8.0\n"
        "elif boundary_tamper == 'top_gpu_count_type': "
        "record['executor']['gpu_count'] = 8.0\n"
        "elif boundary_tamper == 'aggregate_rate': "
        "record['executor']['rate_evidence']['price_per_hour'] = 17\n"
        "output_mode = os.environ.get('FAKE_PROVIDER_OUTPUT_MODE', 'valid')\n"
        "if output_mode == 'valid': print(json.dumps(record, separators=(',', ':')), flush=True)\n"
        "elif output_mode == 'partial': print('{\\\"schema\\\":', flush=True)\n"
        "time.sleep(float(os.environ.get('FAKE_LIUM_SLEEP', '0')))\n"
        "raise SystemExit(int(os.environ.get('FAKE_PROVIDER_EXIT', '0')))\n",
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
        "import os, sys\nfrom pathlib import Path\n"
        "import w8_biayn.integrations.h100_signed_approval as module\n"
        "module.GATE0_CONSUMPTION_ROOT = Path(sys.argv[1])\n"
        "if os.environ.get('FAKE_RECONCILIATION_TIMEOUT_SECONDS'):\n"
        "    module.RECONCILIATION_TIMEOUT_SECONDS = int(\n"
        "        os.environ['FAKE_RECONCILIATION_TIMEOUT_SECONDS']\n"
        "    )\n"
        "if os.environ.get('FAKE_FAIL_INITIAL_TERMINAL_REPLACE') == '1':\n"
        "    original_replace = module._replace_reserved_terminal_reconciliation_receipt\n"
        "    def fail_initial(path, receipt):\n"
        "        if '.terminal-reconciliation.retry-' not in path.name:\n"
        "            raise module.PermitVerificationError('simulated initial terminal replace failure')\n"
        "        return original_replace(path, receipt)\n"
        "    module._replace_reserved_terminal_reconciliation_receipt = fail_initial\n"
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
    retry_terminal_reconciliation: bool = False,
) -> list[str]:
    arguments = [
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
    ]
    if retry_terminal_reconciliation:
        arguments.append("--retry-terminal-reconciliation")
    return [*arguments, "--", *(command or harness["argv"])]


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


def _wait_for_path(path: Path, *, timeout: float = 8) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(0.01)
    pytest.fail(f"timed out waiting for {path.name}")


def _wait_for_lease_release(path: Path, *, timeout: float = 8) -> None:
    deadline = time.monotonic() + timeout
    descriptor = os.open(path, os.O_RDWR)
    try:
        while time.monotonic() < deadline:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                time.sleep(0.01)
                continue
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            return
    finally:
        os.close(descriptor)
    pytest.fail("timed out waiting for terminal ownership lease release")


def _terminal_receipt(harness: dict[str, Any]) -> dict[str, Any]:
    paths = list(harness["ledger"].glob("*.terminal-reconciliation.json"))
    assert len(paths) == 1
    return json.loads(paths[0].read_text(encoding="utf-8"))


def _resign(harness: dict[str, Any]) -> None:
    _write_signed_permit(
        harness["permit"],
        harness["private_key"],
        harness["key_id"],
        harness["payload"],
    )


def _seed_cleanup_unconfirmed_chain(harness: dict[str, Any]) -> tuple[Path, Path]:
    permit_sha256 = hashlib.sha256(harness["permit"].read_bytes()).hexdigest()
    claim_material = canonical_json_bytes(
        {
            "nonce": harness["payload"]["nonce"],
            "request_id": harness["payload"]["request_id"],
        }
    )
    claim_id = hashlib.sha256(claim_material).hexdigest()
    harness["ledger"].mkdir(mode=0o700, exist_ok=True)
    harness["ledger"].chmod(0o700)
    claim_path = harness["ledger"] / f"{claim_id}.consumed.json"
    claim_path.write_bytes(
        canonical_json_bytes(
            {
                "key_id": harness["key_id"],
                "nonce": harness["payload"]["nonce"],
                "permit_sha256": permit_sha256,
                "request_id": harness["payload"]["request_id"],
                "consumed_at": harness["payload"]["issued_at"],
            }
        )
        + b"\n"
    )
    terminal_path = harness["ledger"] / f"{claim_id}.terminal-reconciliation.json"
    terminal_path.write_text(
        json.dumps(
            {
                "schema": signed_approval.TERMINAL_RECONCILIATION_RECEIPT_SCHEMA,
                "status": "CLEANUP_UNCONFIRMED",
                "permit": {"sha256": permit_sha256},
                "claim": {
                    "path": str(claim_path.resolve()),
                    "sha256": hashlib.sha256(claim_path.read_bytes()).hexdigest(),
                },
                "allocation": {
                    "name": ALLOCATION_NAME,
                    "preexisting_exact_name_ids": [],
                },
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return claim_path, terminal_path


def _initial_clear_pre_snapshot(harness: dict[str, Any]) -> dict[str, Any]:
    record = {
        "schema": signed_approval.PROVIDER_RECONCILIATION_SCHEMA,
        "status": "SNAPSHOT_CLEAR",
        "mode": "snapshot",
        "allocation_name": harness["payload"]["allocation_name"],
        "preexisting_exact_name_ids": [],
    }
    output = json.dumps(record).encode("utf-8") + b"\n"
    return {
        "exit_code": 0,
        "timed_out": False,
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "output_size_bytes": len(output),
        "record": record,
    }


def _seed_initial_terminal_reservation(
    harness: dict[str, Any],
) -> tuple[Path, Path, dict[str, Any]]:
    permit_sha256 = hashlib.sha256(harness["permit"].read_bytes()).hexdigest()
    claim_material = canonical_json_bytes(
        {
            "nonce": harness["payload"]["nonce"],
            "request_id": harness["payload"]["request_id"],
        }
    )
    claim_id = hashlib.sha256(claim_material).hexdigest()
    harness["ledger"].mkdir(mode=0o700, exist_ok=True)
    harness["ledger"].chmod(0o700)
    claim_path = harness["ledger"] / f"{claim_id}.consumed.json"
    claim_path.write_bytes(
        canonical_json_bytes(
            {
                "key_id": harness["key_id"],
                "nonce": harness["payload"]["nonce"],
                "permit_sha256": permit_sha256,
                "request_id": harness["payload"]["request_id"],
                "consumed_at": harness["payload"]["issued_at"],
            }
        )
        + b"\n"
    )
    pre_snapshot = _initial_clear_pre_snapshot(harness)
    terminal_path = harness["ledger"] / f"{claim_id}.terminal-reconciliation.json"
    terminal_path.write_bytes(
        canonical_json_bytes(
            {
                "schema": signed_approval.TERMINAL_RECONCILIATION_RECEIPT_SCHEMA,
                "status": "RESERVED",
                "permit": {
                    "sha256": permit_sha256,
                    "key_id": harness["key_id"],
                    "request_id": harness["payload"]["request_id"],
                    "nonce": harness["payload"]["nonce"],
                },
                "claim": {"path": str(claim_path.resolve())},
                "allocation": {
                    "name": harness["payload"]["allocation_name"],
                    "preexisting_exact_name_ids": [],
                },
                "pre_snapshot": {
                    "sha256": hashlib.sha256(canonical_json_bytes(pre_snapshot)).hexdigest(),
                    "evidence": pre_snapshot,
                },
            }
        )
        + b"\n"
    )
    return claim_path, terminal_path, pre_snapshot


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


def test_huid_selector_matches_provider_uuid_or_huid(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    selector_huid = "gentle-hawk-2a"
    raw_executor_id = "4f4ad1c1-7d95-41a7-bd0d-35aa950d73ac"
    harness["payload"]["executor_id"] = selector_huid
    harness["argv"][2] = selector_huid
    harness["payload"]["environment"]["FAKE_RAW_EXECUTOR_ID"] = raw_executor_id
    _resign(harness)

    completed = _run_wrapper(harness, executor_id=selector_huid)
    record = json.loads(harness["provider_output"].read_bytes())

    assert completed.returncode == 0, completed.stderr
    assert record["executor"]["id"] == raw_executor_id
    assert record["executor"]["huid"] == selector_huid
    assert record["executor"]["rent_boundary"]["endpoint"] == (f"/executors/{raw_executor_id}/rent")


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
    provider_output = harness["provider_output"].read_bytes()
    provider_record = json.loads(provider_output)
    assert provider_record["status"] == "RUNNING"
    assert receipt["provider_output"]["path"] == str(harness["provider_output"])
    assert receipt["provider_output"]["sha256"] == hashlib.sha256(provider_output).hexdigest()
    assert receipt["provider_output"]["size_bytes"] == len(provider_output)
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
    assert receipt["budget"]["observed_node_hourly_rate_status"] == ("provider_reported_nonzero")
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
    assert json.loads(output)["status"] == "RUNNING"
    assert receipt["provider_output"]["sha256"] == hashlib.sha256(output).hexdigest()
    assert receipt["provider_output"]["size_bytes"] == len(output)
    assert len(_invocations(harness)) == 1
    assert not harness["allocation_state"].exists()
    terminal = _terminal_receipt(harness)
    assert terminal["status"] == "FAILURE_RECONCILED"
    assert terminal["terminal_failure"]["kind"] == "ProviderTimeout"
    assert terminal["reconciliation"]["record"]["status"] == "CONFIRMED_ABSENT"
    assert terminal["artifacts"]["captured_provider_output"] == {
        "sha256": hashlib.sha256(output).hexdigest(),
        "size_bytes": len(output),
    }


@pytest.mark.parametrize("output_mode", ["missing", "partial"])
def test_missing_or_partial_provider_output_reconciles_all_attributable_allocations(
    tmp_path: Path, output_mode: str
) -> None:
    harness = _make_harness(tmp_path)
    harness["payload"]["environment"]["FAKE_PROVIDER_OUTPUT_MODE"] = output_mode
    harness["payload"]["environment"]["FAKE_EXTRA_ALLOCATION_IDS"] = (
        "fake-pod-duplicate-a,fake-pod-duplicate-b"
    )
    _resign(harness)

    completed = _run_wrapper(harness)
    terminal = _terminal_receipt(harness)

    assert completed.returncode == 125
    assert not harness["allocation_state"].exists()
    assert terminal["status"] == "FAILURE_RECONCILED"
    assert terminal["reconciliation"]["record"]["observed_attributable_ids"] == [
        "fake-pod-123",
        "fake-pod-duplicate-a",
        "fake-pod-duplicate-b",
    ]
    assert terminal["reconciliation"]["record"]["final_attributable_ids"] == []
    assert (
        terminal["artifacts"]["captured_provider_output"]["sha256"]
        == hashlib.sha256(harness["provider_output"].read_bytes()).hexdigest()
    )


@pytest.mark.parametrize(
    "tamper",
    [
        "missing",
        "status",
        "endpoint",
        "after_rate",
        "after_availability",
        "after_gpu_count_type",
        "top_gpu_count_type",
        "aggregate_rate",
    ],
)
def test_outer_wrapper_rejects_tampered_rent_boundary_and_reconciles(
    tmp_path: Path, tamper: str
) -> None:
    harness = _make_harness(tmp_path)
    harness["payload"]["environment"]["FAKE_RENT_BOUNDARY_TAMPER"] = tamper
    _resign(harness)

    completed = _run_wrapper(harness)
    launch_receipt = json.loads(harness["receipt"].read_text(encoding="utf-8"))
    terminal = _terminal_receipt(harness)

    assert completed.returncode == 125
    assert launch_receipt["status"] == "PROVIDER_OUTPUT_INVALID"
    assert launch_receipt["execution"]["provider_output_valid"] is False
    assert terminal["status"] == "FAILURE_RECONCILED"
    assert terminal["reconciliation"]["record"]["status"] == "CONFIRMED_ABSENT"
    assert not harness["allocation_state"].exists()


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
    assert "PermitVerificationError" in replay.stderr
    assert before_replay == 1
    assert len(_invocations(harness)) == before_replay


def test_outer_snapshot_rejects_preexisting_exact_name_before_consumption(
    tmp_path: Path,
) -> None:
    harness = _make_harness(tmp_path)
    harness["allocation_state"].write_text(
        json.dumps([{"id": "preexisting-pod", "name": ALLOCATION_NAME}]),
        encoding="utf-8",
    )

    completed = _run_wrapper(harness)

    assert completed.returncode == 2
    assert _invocations(harness) == []
    assert not harness["mutation_log"].exists()
    assert not harness["ledger"].exists()
    assert json.loads(harness["allocation_state"].read_text(encoding="utf-8")) == [
        {"id": "preexisting-pod", "name": ALLOCATION_NAME}
    ]


def test_terminal_slot_conflict_rejects_before_claim_or_provider_mutation(
    tmp_path: Path,
) -> None:
    harness = _make_harness(tmp_path)
    claim_material = canonical_json_bytes(
        {
            "nonce": harness["payload"]["nonce"],
            "request_id": harness["payload"]["request_id"],
        }
    )
    claim_id = hashlib.sha256(claim_material).hexdigest()
    harness["ledger"].mkdir(mode=0o700)
    terminal_path = harness["ledger"] / f"{claim_id}.terminal-reconciliation.json"
    terminal_path.write_text("reserved-by-prior-attempt\n", encoding="utf-8")

    completed = _run_wrapper(harness)

    assert completed.returncode == 2
    assert "PermitReplayError" in completed.stderr
    assert not list(harness["ledger"].glob("*.consumed.json"))
    assert _invocations(harness) == []
    assert not harness["mutation_log"].exists()
    assert terminal_path.read_text(encoding="utf-8") == "reserved-by-prior-attempt\n"


def test_cleanup_retry_is_append_only_and_never_relaunches_provider(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    once_file = tmp_path / "reconciliation-failed-once.state"
    harness["payload"]["environment"]["FAKE_PROVIDER_OUTPUT_MODE"] = "partial"
    harness["payload"]["environment"]["FAKE_RECONCILIATION_FAILURE_ONCE_FILE"] = str(once_file)
    _resign(harness)

    first = _run_wrapper(harness)
    terminal_paths = list(harness["ledger"].glob("*.terminal-reconciliation.json"))
    assert len(terminal_paths) == 1
    original_terminal_bytes = terminal_paths[0].read_bytes()
    original_terminal = json.loads(original_terminal_bytes)
    assert first.returncode == 125
    assert original_terminal["status"] == "CLEANUP_UNCONFIRMED"
    assert original_terminal["retry_control"]["next_attempt"] == 1
    assert harness["allocation_state"].exists()

    retry = _run_wrapper(harness, retry_terminal_reconciliation=True)
    retry_paths = list(harness["ledger"].glob("*.terminal-reconciliation.retry-0001.json"))

    assert retry.returncode == 0, retry.stderr
    assert terminal_paths[0].read_bytes() == original_terminal_bytes
    assert len(retry_paths) == 1
    retry_receipt = json.loads(retry_paths[0].read_text(encoding="utf-8"))
    assert retry_receipt["status"] == "RETRY_RECONCILED"
    assert retry_receipt["attempt"] == 1
    assert (
        retry_receipt["parent_receipt"]["sha256"]
        == hashlib.sha256(original_terminal_bytes).hexdigest()
    )
    assert retry_receipt["reconciliation"]["record"]["final_attributable_ids"] == []
    assert not harness["allocation_state"].exists()
    assert harness["mutation_log"].read_text(encoding="utf-8").splitlines() == ["up"]
    assert len(_invocations(harness)) == 1

    no_second_retry = _run_wrapper(harness, retry_terminal_reconciliation=True)
    assert no_second_retry.returncode == 2
    assert not list(harness["ledger"].glob("*.retry-0002.json"))
    assert len(_invocations(harness)) == 1


def test_expired_permit_cannot_launch_but_can_retry_bound_cleanup(tmp_path: Path) -> None:
    launch_root = tmp_path / "launch"
    launch_root.mkdir()
    launch_harness = _make_harness(launch_root)
    launch_harness["payload"]["issued_at"] = "2026-07-10T00:00:00Z"
    launch_harness["payload"]["expires_at"] = "2026-07-10T00:10:00Z"
    _resign(launch_harness)

    rejected_launch = _run_wrapper(launch_harness)

    assert rejected_launch.returncode == 2
    assert "permit is expired" in rejected_launch.stderr
    assert not launch_harness["mutation_log"].exists()
    assert not launch_harness["ledger"].exists()

    retry_root = tmp_path / "retry"
    retry_root.mkdir()
    retry_harness = _make_harness(retry_root)
    retry_harness["payload"]["issued_at"] = "2026-07-10T00:00:00Z"
    retry_harness["payload"]["expires_at"] = "2026-07-10T00:10:00Z"
    _resign(retry_harness)
    _seed_cleanup_unconfirmed_chain(retry_harness)
    retry_harness["allocation_state"].write_text(
        json.dumps([{"id": "paid-pod-from-lost-response", "name": ALLOCATION_NAME}]),
        encoding="utf-8",
    )

    cleanup = _run_wrapper(retry_harness, retry_terminal_reconciliation=True)

    assert cleanup.returncode == 0, cleanup.stderr
    assert not retry_harness["allocation_state"].exists()
    assert not retry_harness["mutation_log"].exists()
    assert len(_invocations(retry_harness)) == 0
    retry_receipts = list(retry_harness["ledger"].glob("*.terminal-reconciliation.retry-0001.json"))
    assert len(retry_receipts) == 1
    assert json.loads(retry_receipts[0].read_text(encoding="utf-8"))["status"] == (
        "RETRY_RECONCILED"
    )


def test_exact_initial_terminal_reservation_after_claim_is_cleanup_authority(
    tmp_path: Path,
) -> None:
    harness = _make_harness(tmp_path)
    _, terminal_path, pre_snapshot = _seed_initial_terminal_reservation(harness)
    original_terminal = terminal_path.read_bytes()

    cleanup = _run_wrapper(harness, retry_terminal_reconciliation=True)
    retry_path = terminal_path.with_name(
        f"{terminal_path.name.removesuffix('.json')}.retry-0001.json"
    )
    retry = json.loads(retry_path.read_text(encoding="utf-8"))

    assert cleanup.returncode == 0, cleanup.stderr
    assert terminal_path.read_bytes() == original_terminal
    assert retry["status"] == "RETRY_RECONCILED"
    assert retry["cleanup_status"] == "CONFIRMED_ABSENT"
    assert retry["reconciliation"]["record"]["status"] == "CONFIRMED_ABSENT"
    assert retry["allocation"] == {
        "name": ALLOCATION_NAME,
        "preexisting_exact_name_ids": [],
    }
    assert retry["initial_terminal_reservation"]["pre_snapshot"] == pre_snapshot
    canonicalized_provider_output = canonical_json_bytes(pre_snapshot["record"]) + b"\n"
    assert (
        pre_snapshot["output_sha256"] != hashlib.sha256(canonicalized_provider_output).hexdigest()
    )
    assert retry["ownership_lease"]["mode"] == "exclusive-kernel-flock"
    assert not harness["mutation_log"].exists()
    assert _invocations(harness) == []


def test_initial_reservation_recovers_interruption_after_attributable_rent(
    tmp_path: Path,
) -> None:
    harness = _make_harness(tmp_path)
    _, terminal_path, _ = _seed_initial_terminal_reservation(harness)
    harness["allocation_state"].write_text(
        json.dumps(
            [
                {"id": "lost-rent-a", "name": ALLOCATION_NAME},
                {"id": "lost-rent-b", "name": ALLOCATION_NAME},
            ]
        ),
        encoding="utf-8",
    )

    cleanup = _run_wrapper(harness, retry_terminal_reconciliation=True)
    retry_path = terminal_path.with_name(
        f"{terminal_path.name.removesuffix('.json')}.retry-0001.json"
    )
    retry = json.loads(retry_path.read_text(encoding="utf-8"))

    assert cleanup.returncode == 0, cleanup.stderr
    assert retry["cleanup_status"] == "CONFIRMED_ABSENT"
    assert retry["reconciliation"]["record"]["observed_attributable_ids"] == [
        "lost-rent-a",
        "lost-rent-b",
    ]
    assert retry["reconciliation"]["record"]["final_attributable_ids"] == []
    assert not harness["allocation_state"].exists()
    assert not harness["mutation_log"].exists()


def test_expired_initial_reservation_retains_cleanup_only_authority(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    harness["payload"]["issued_at"] = "2026-07-10T00:00:00Z"
    harness["payload"]["expires_at"] = "2026-07-10T00:10:00Z"
    _resign(harness)
    _, terminal_path, _ = _seed_initial_terminal_reservation(harness)
    harness["allocation_state"].write_text(
        json.dumps([{"id": "expired-lost-rent", "name": ALLOCATION_NAME}]),
        encoding="utf-8",
    )

    cleanup = _run_wrapper(harness, retry_terminal_reconciliation=True)
    retry_path = terminal_path.with_name(
        f"{terminal_path.name.removesuffix('.json')}.retry-0001.json"
    )

    assert cleanup.returncode == 0, cleanup.stderr
    assert json.loads(retry_path.read_text(encoding="utf-8"))["cleanup_status"] == (
        "CONFIRMED_ABSENT"
    )
    assert not harness["allocation_state"].exists()
    assert not harness["mutation_log"].exists()


@pytest.mark.parametrize(
    "tamper",
    [
        "permit",
        "claim",
        "allocation",
        "pre_snapshot_hash",
        "pre_snapshot_evidence",
    ],
)
def test_tampered_initial_terminal_reservation_rejects_before_cleanup(
    tmp_path: Path,
    tamper: str,
) -> None:
    harness = _make_harness(tmp_path)
    _, terminal_path, _ = _seed_initial_terminal_reservation(harness)
    reservation = json.loads(terminal_path.read_text(encoding="utf-8"))
    if tamper == "permit":
        reservation["permit"]["nonce"] = "0" * 64
    elif tamper == "claim":
        reservation["claim"]["path"] = str(tmp_path / "substituted-claim.json")
    elif tamper == "allocation":
        reservation["allocation"]["name"] = "issue-32-substituted-allocation"
    elif tamper == "pre_snapshot_hash":
        reservation["pre_snapshot"]["sha256"] = "f" * 64
    else:
        evidence = reservation["pre_snapshot"]["evidence"]
        evidence["record"]["status"] = "ERROR"
        reservation["pre_snapshot"]["sha256"] = hashlib.sha256(
            canonical_json_bytes(evidence)
        ).hexdigest()
    terminal_path.write_text(json.dumps(reservation, sort_keys=True) + "\n", encoding="utf-8")
    harness["allocation_state"].write_text(
        json.dumps([{"id": "must-remain", "name": ALLOCATION_NAME}]),
        encoding="utf-8",
    )

    rejected = _run_wrapper(harness, retry_terminal_reconciliation=True)

    assert rejected.returncode == 2
    assert "initial terminal reservation binding mismatch" in rejected.stderr
    assert json.loads(harness["allocation_state"].read_text(encoding="utf-8")) == [
        {"id": "must-remain", "name": ALLOCATION_NAME}
    ]
    assert not list(harness["ledger"].glob("*.retry-*.json"))
    assert not harness["mutation_log"].exists()


def test_initial_terminal_replacement_failure_is_recoverable_append_only(
    tmp_path: Path,
) -> None:
    harness = _make_harness(tmp_path)
    harness["env"]["FAKE_FAIL_INITIAL_TERMINAL_REPLACE"] = "1"

    launch = _run_wrapper(harness)
    terminal_path = next(harness["ledger"].glob("*.terminal-reconciliation.json"))
    initial_reservation = terminal_path.read_bytes()
    retry = _run_wrapper(harness, retry_terminal_reconciliation=True)
    retry_path = terminal_path.with_name(
        f"{terminal_path.name.removesuffix('.json')}.retry-0001.json"
    )

    assert launch.returncode == 125
    reservation = json.loads(initial_reservation)
    assert reservation["status"] == "RESERVED"
    assert reservation["pre_snapshot"]["evidence"] == _initial_clear_pre_snapshot(harness)
    assert not harness["allocation_state"].exists()
    assert retry.returncode == 0, retry.stderr
    assert terminal_path.read_bytes() == initial_reservation
    assert json.loads(retry_path.read_text(encoding="utf-8"))["cleanup_status"] == (
        "CONFIRMED_ABSENT"
    )
    assert harness["mutation_log"].read_text(encoding="utf-8").splitlines() == ["up"]


def test_live_wrapper_lease_excludes_concurrent_initial_cleanup_retry(
    tmp_path: Path,
) -> None:
    harness = _make_harness(tmp_path)
    harness["payload"]["environment"]["FAKE_LIUM_SLEEP"] = "2"
    _resign(harness)
    live = subprocess.Popen(
        _wrapper_argv(harness),
        env=harness["env"],
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert live.stdin is not None
    live.stdin.write(harness["credential"] + "\n")
    live.stdin.close()
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        claims = (
            list(harness["ledger"].glob("*.consumed.json")) if harness["ledger"].exists() else []
        )
        terminals = (
            list(harness["ledger"].glob("*.terminal-reconciliation.json"))
            if harness["ledger"].exists()
            else []
        )
        if claims and terminals and harness["allocation_state"].exists():
            break
        time.sleep(0.02)
    else:
        live.kill()
        pytest.fail("live wrapper did not reach the attributable-rent window")

    rejected = _run_wrapper(harness, retry_terminal_reconciliation=True)

    assert rejected.returncode == 2
    assert "owned by a live wrapper" in rejected.stderr
    assert harness["allocation_state"].exists()
    assert not list(harness["ledger"].glob("*.retry-*.json"))
    assert live.wait(timeout=10) == 0
    assert harness["mutation_log"].read_text(encoding="utf-8").splitlines() == ["up"]
    terminal_path = next(harness["ledger"].glob("*.terminal-reconciliation.json"))
    assert json.loads(terminal_path.read_text(encoding="utf-8"))["status"] == ("LAUNCH_COMPLETED")


def test_pre_rent_orphan_holds_lease_until_exit_then_cleanup_confirms_absence(
    tmp_path: Path,
) -> None:
    harness = _make_harness(tmp_path)
    marker = tmp_path / "provider-paused-before-rent"
    release = tmp_path / "release-provider-rent"
    harness["payload"]["environment"].update(
        {
            "FAKE_BEFORE_RENT_MARKER": str(marker),
            "FAKE_BEFORE_RENT_RELEASE": str(release),
        }
    )
    harness["payload"]["provider_timeout_seconds"] = 5
    _resign(harness)
    live = subprocess.Popen(
        _wrapper_argv(harness),
        env=harness["env"],
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        assert live.stdin is not None
        live.stdin.write(harness["credential"] + "\n")
        live.stdin.close()
        _wait_for_path(marker)
        terminal_path = next(harness["ledger"].glob("*.terminal-reconciliation.json"))
        lease_path = next(harness["ledger"].glob("*.terminal-reconciliation.lease.json"))

        live.kill()
        assert live.wait(timeout=10) != 0
        denied = _run_wrapper(harness, retry_terminal_reconciliation=True)

        assert denied.returncode == 2
        assert "owned by a live wrapper" in denied.stderr
        assert not harness["allocation_state"].exists()
        assert not list(harness["ledger"].glob("*.retry-*.json"))
        release.touch()
        _wait_for_path(harness["allocation_state"])
        _wait_for_lease_release(lease_path)

        cleanup = _run_wrapper(harness, retry_terminal_reconciliation=True)
        retry_path = terminal_path.with_name(
            f"{terminal_path.name.removesuffix('.json')}.retry-0001.json"
        )
        retry = json.loads(retry_path.read_text(encoding="utf-8"))

        assert cleanup.returncode == 0, cleanup.stderr
        assert retry["cleanup_status"] == "CONFIRMED_ABSENT"
        assert retry["reconciliation"]["record"]["observed_attributable_ids"] == ["fake-pod-123"]
        assert harness["mutation_log"].read_text(encoding="utf-8").splitlines() == ["up"]
        assert len(_invocations(harness)) == 1
        assert not harness["allocation_state"].exists()
        time.sleep(0.1)
        assert not harness["allocation_state"].exists()
    finally:
        if live.poll() is None:
            live.kill()
            live.wait(timeout=10)
        try:
            os.killpg(live.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for stream in (live.stdout, live.stderr):
            if stream is not None:
                stream.close()


def test_pre_rent_orphan_hard_timeout_releases_lease_without_mutation(
    tmp_path: Path,
) -> None:
    harness = _make_harness(tmp_path)
    marker = tmp_path / "provider-paused-until-hard-timeout"
    never_release = tmp_path / "never-release-provider-rent"
    harness["payload"]["environment"].update(
        {
            "FAKE_BEFORE_RENT_MARKER": str(marker),
            "FAKE_BEFORE_RENT_RELEASE": str(never_release),
        }
    )
    harness["payload"]["provider_timeout_seconds"] = 2
    _resign(harness)
    live = subprocess.Popen(
        _wrapper_argv(harness),
        env=harness["env"],
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        assert live.stdin is not None
        live.stdin.write(harness["credential"] + "\n")
        live.stdin.close()
        _wait_for_path(marker)
        terminal_path = next(harness["ledger"].glob("*.terminal-reconciliation.json"))
        lease_path = next(harness["ledger"].glob("*.terminal-reconciliation.lease.json"))

        live.kill()
        assert live.wait(timeout=10) != 0
        denied = _run_wrapper(harness, retry_terminal_reconciliation=True)

        assert denied.returncode == 2
        assert "owned by a live wrapper" in denied.stderr
        _wait_for_lease_release(lease_path, timeout=5)
        assert not harness["allocation_state"].exists()
        assert not harness["mutation_log"].exists()

        cleanup = _run_wrapper(harness, retry_terminal_reconciliation=True)
        retry_path = terminal_path.with_name(
            f"{terminal_path.name.removesuffix('.json')}.retry-0001.json"
        )

        assert cleanup.returncode == 0, cleanup.stderr
        assert json.loads(retry_path.read_text(encoding="utf-8"))["cleanup_status"] == (
            "CONFIRMED_ABSENT"
        )
        assert len(_invocations(harness)) == 1
        time.sleep(0.1)
        assert not harness["allocation_state"].exists()
    finally:
        if live.poll() is None:
            live.kill()
            live.wait(timeout=10)
        try:
            os.killpg(live.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for stream in (live.stdout, live.stderr):
            if stream is not None:
                stream.close()


def test_orphan_cleanup_child_holds_lease_and_has_independent_timeout(
    tmp_path: Path,
) -> None:
    harness = _make_harness(tmp_path)
    marker = tmp_path / "cleanup-paused-before-mutation"
    release = tmp_path / "release-cleanup-mutation"
    harness["payload"]["environment"].update(
        {
            "FAKE_CLEANUP_BEFORE_MUTATION_MARKER": str(marker),
            "FAKE_CLEANUP_BEFORE_MUTATION_RELEASE": str(release),
        }
    )
    harness["env"]["FAKE_RECONCILIATION_TIMEOUT_SECONDS"] = "2"
    _resign(harness)
    _, terminal_path, _ = _seed_initial_terminal_reservation(harness)
    harness["allocation_state"].write_text(
        json.dumps([{"id": "orphan-cleanup-target", "name": ALLOCATION_NAME}]),
        encoding="utf-8",
    )
    live = subprocess.Popen(
        _wrapper_argv(harness, retry_terminal_reconciliation=True),
        env=harness["env"],
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        assert live.stdin is not None
        live.stdin.write(harness["credential"] + "\n")
        live.stdin.close()
        _wait_for_path(marker)
        retry_path = terminal_path.with_name(
            f"{terminal_path.name.removesuffix('.json')}.retry-0001.json"
        )
        _wait_for_path(retry_path)
        lease_path = next(harness["ledger"].glob("*.terminal-reconciliation.lease.json"))

        live.kill()
        assert live.wait(timeout=10) != 0
        denied = _run_wrapper(harness, retry_terminal_reconciliation=True)

        assert denied.returncode == 2
        assert "owned by a live wrapper" in denied.stderr
        assert json.loads(retry_path.read_text(encoding="utf-8"))["status"] == "RESERVED"
        _wait_for_lease_release(lease_path, timeout=5)
        assert harness["allocation_state"].exists()

        release.touch()
        resumed = _run_wrapper(harness, retry_terminal_reconciliation=True)
        retry = json.loads(retry_path.read_text(encoding="utf-8"))

        assert resumed.returncode == 0, resumed.stderr
        assert retry["status"] == "RETRY_RECONCILED"
        assert retry["cleanup_status"] == "CONFIRMED_ABSENT"
        assert retry["reconciliation"]["record"]["observed_attributable_ids"] == [
            "orphan-cleanup-target"
        ]
        assert not harness["allocation_state"].exists()
        assert not harness["mutation_log"].exists()
        assert _invocations(harness) == []
    finally:
        if live.poll() is None:
            live.kill()
            live.wait(timeout=10)
        try:
            os.killpg(live.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for stream in (live.stdout, live.stderr):
            if stream is not None:
                stream.close()


def test_post_rent_wrapper_death_releases_lease_for_cleanup_retry(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    harness["payload"]["environment"]["FAKE_LIUM_SLEEP"] = "2"
    _resign(harness)
    live = subprocess.Popen(
        _wrapper_argv(harness),
        env=harness["env"],
        text=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        assert live.stdin is not None
        live.stdin.write(harness["credential"] + "\n")
        live.stdin.close()
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            claims = (
                list(harness["ledger"].glob("*.consumed.json"))
                if harness["ledger"].exists()
                else []
            )
            terminals = (
                list(harness["ledger"].glob("*.terminal-reconciliation.json"))
                if harness["ledger"].exists()
                else []
            )
            if claims and terminals and harness["allocation_state"].exists():
                break
            time.sleep(0.02)
        else:
            pytest.fail("live wrapper did not reach the post-rent crash window")

        live.kill()
        assert live.wait(timeout=10) != 0
        terminal_path = next(harness["ledger"].glob("*.terminal-reconciliation.json"))
        assert json.loads(terminal_path.read_text(encoding="utf-8"))["status"] == "RESERVED"
        lease_path = next(harness["ledger"].glob("*.terminal-reconciliation.lease.json"))

        denied = _run_wrapper(harness, retry_terminal_reconciliation=True)
        assert denied.returncode == 2
        assert "owned by a live wrapper" in denied.stderr
        _wait_for_lease_release(lease_path, timeout=4)

        cleanup = _run_wrapper(harness, retry_terminal_reconciliation=True)
        retry_path = terminal_path.with_name(
            f"{terminal_path.name.removesuffix('.json')}.retry-0001.json"
        )
        retry = json.loads(retry_path.read_text(encoding="utf-8"))

        assert cleanup.returncode == 0, cleanup.stderr
        assert retry["cleanup_status"] == "CONFIRMED_ABSENT"
        assert retry["reconciliation"]["record"]["observed_attributable_ids"] == ["fake-pod-123"]
        assert not harness["allocation_state"].exists()
        assert harness["mutation_log"].read_text(encoding="utf-8").splitlines() == ["up"]
        assert len(_invocations(harness)) == 1
    finally:
        if live.poll() is None:
            live.kill()
            live.wait(timeout=10)
        try:
            os.killpg(live.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for stream in (live.stdout, live.stderr):
            if stream is not None:
                stream.close()


def test_exact_reserved_cleanup_retry_is_resumable(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    harness["payload"]["environment"]["FAKE_PROVIDER_OUTPUT_MODE"] = "partial"
    harness["payload"]["environment"]["FAKE_RECONCILIATION_FAILURE_ONCE_FILE"] = str(
        tmp_path / "reconciliation-failed-once.state"
    )
    _resign(harness)
    first = _run_wrapper(harness)
    assert first.returncode == 125
    terminal_path = next(harness["ledger"].glob("*.terminal-reconciliation.json"))
    retry_path = terminal_path.with_name(
        f"{terminal_path.name.removesuffix('.json')}.retry-0001.json"
    )
    retry_path.write_bytes(
        canonical_json_bytes(
            {
                "schema": signed_approval.TERMINAL_RECONCILIATION_RETRY_SCHEMA,
                "status": "RESERVED",
                "attempt": 1,
                "permit_sha256": hashlib.sha256(harness["permit"].read_bytes()).hexdigest(),
                "parent_receipt_sha256": hashlib.sha256(terminal_path.read_bytes()).hexdigest(),
            }
        )
        + b"\n"
    )

    resumed = _run_wrapper(harness, retry_terminal_reconciliation=True)

    assert resumed.returncode == 0, resumed.stderr
    assert json.loads(retry_path.read_text(encoding="utf-8"))["status"] == "RETRY_RECONCILED"
    assert not harness["allocation_state"].exists()
    assert harness["mutation_log"].read_text(encoding="utf-8").splitlines() == ["up"]


def test_tampered_reserved_cleanup_retry_fails_before_cleanup(tmp_path: Path) -> None:
    harness = _make_harness(tmp_path)
    _seed_cleanup_unconfirmed_chain(harness)
    harness["allocation_state"].write_text(
        json.dumps([{"id": "still-paid-pod", "name": ALLOCATION_NAME}]),
        encoding="utf-8",
    )
    terminal_path = next(harness["ledger"].glob("*.terminal-reconciliation.json"))
    retry_path = terminal_path.with_name(
        f"{terminal_path.name.removesuffix('.json')}.retry-0001.json"
    )
    retry_path.write_bytes(
        canonical_json_bytes(
            {
                "schema": signed_approval.TERMINAL_RECONCILIATION_RETRY_SCHEMA,
                "status": "RESERVED",
                "attempt": 1,
                "permit_sha256": hashlib.sha256(harness["permit"].read_bytes()).hexdigest(),
                "parent_receipt_sha256": "f" * 64,
            }
        )
        + b"\n"
    )

    rejected = _run_wrapper(harness, retry_terminal_reconciliation=True)

    assert rejected.returncode == 2
    assert "retry reservation mismatch" in rejected.stderr
    assert json.loads(harness["allocation_state"].read_text(encoding="utf-8")) == [
        {"id": "still-paid-pod", "name": ALLOCATION_NAME}
    ]
    assert not harness["mutation_log"].exists()


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
    assert second.returncode == 2
    assert harness["mutation_log"].read_text(encoding="utf-8").splitlines() == ["up"]
    assert len(_invocations(harness)) == 1


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
    lease_fd = os.open(tmp_path / "held-terminal.lease", os.O_RDWR | os.O_CREAT, 0o600)
    fcntl.flock(lease_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
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
            terminal_lease_descriptor=lease_fd,
            provider_environment=harness["payload"]["environment"],
        )
        output, _ = process.communicate(input=(harness["credential"] + "\n").encode(), timeout=10)
    finally:
        fcntl.flock(lease_fd, fcntl.LOCK_UN)
        os.close(lease_fd)
        os.close(interpreter_fd)
        os.close(script_fd)

    assert process.returncode == 0
    assert json.loads(output)["status"] == "RUNNING"
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
    assert any(
        error in stderr
        for _, stderr in outputs
        for error in ("PermitReplayError", "PermitVerificationError")
    )
