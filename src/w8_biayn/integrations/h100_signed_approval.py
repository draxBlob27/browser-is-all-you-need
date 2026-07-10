"""Verify and consume single-use Ed25519 permits for Lium H100 bookings."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import math
import os
import pwd
import re
import stat
import subprocess
import sys
from dataclasses import dataclass, field as dataclass_field, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping, Sequence

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


ENVELOPE_SCHEMA = "h100-lium-signed-permit-envelope/v4"
PERMIT_SCHEMA = "h100-lium-booking-permit/v4"
PUBLIC_KEY_SCHEMA = "h100-lium-ed25519-public-key/v1"
SIGNATURE_DOMAIN = b"w8-biayn/h100-lium-booking-permit/ed25519/v4\x00"
LAUNCH_RECEIPT_SCHEMA = "h100-lium-launch-receipt/v2"
REQUIRED_STAGE = "lium-booking"
REQUIRED_DECISION = "PROMOTABLE"
REQUIRED_PROVIDER = "lium"
REQUIRED_GPU_TYPE = "H100"
REQUIRED_GPU_COUNT = 8
MAX_TTL_SECONDS = 2 * 60 * 60
MAX_PERMIT_VALIDITY_SECONDS = 10 * 60
MAX_COST_USD = Decimal("36")
MAX_NODE_HOURLY_RATE_USD = Decimal("18")
MAX_NODE_HOURS = Decimal("2")
DEFAULT_PROVIDER_TIMEOUT_SECONDS = 300
MAX_PROVIDER_TIMEOUT_SECONDS = 300
CREDENTIAL_TRANSPORT = "stdin-line/v1"
MAX_CREDENTIAL_BYTES = 4096
GATE0_CONSUMPTION_ROOT = (
    Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
    / ".local/state/w8-biayn/control-plane/gate0-consumption/v1"
)
PROVIDER_FD_LOADER = (
    "import sys\n"
    "fd_path, display_path, *script_args = sys.argv[1:]\n"
    "with open(fd_path, 'rb', buffering=0) as handle:\n"
    "    handle.seek(0)\n"
    "    source = handle.read()\n"
    "sys.argv = [display_path, *script_args]\n"
    "scope = {'__name__': '__main__', '__file__': display_path, "
    "'__package__': None, '__cached__': None}\n"
    "exec(compile(source, display_path, 'exec'), scope, scope)\n"
)

_HEX_256_RE = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@/-]{2,127}\Z")
_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}\Z")
_UTC_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")
_TTL_RE = re.compile(r"([1-9][0-9]*)([hm])\Z")
_VERSION_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,63}\Z")
_ENV_NAME_RE = re.compile(r"[A-Z_][A-Z0-9_]{0,127}\Z")
_ALLOCATION_RE = re.compile(r"issue-([1-9][0-9]*)-[a-z0-9][a-z0-9-]{2,62}\Z")
_SECRETISH_ENV_RE = re.compile(
    r"(?:^|_)(?:API_KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIALS?|PRIVATE_KEY)(?:$|_)"
)
_FORBIDDEN_ENV_NAMES = frozenset(
    {
        "BASH_ENV",
        "ENV",
        "IFS",
        "LD_LIBRARY_PATH",
        "LD_PRELOAD",
        "PYTHONHOME",
        "PYTHONPATH",
        "SHELLOPTS",
    }
)
_PAYLOAD_FIELDS = frozenset(
    {
        "schema",
        "stage",
        "decision",
        "request_id",
        "nonce",
        "issued_at",
        "expires_at",
        "sentry_principal",
        "executor_principal",
        "source_sha256",
        "runtime_sha256",
        "data_sha256",
        "checkpoint_sha256",
        "parent_request_sha256",
        "executor_id",
        "provider",
        "profile",
        "provider_executable",
        "provider_executable_sha256",
        "provider_version",
        "provider_interpreter",
        "provider_interpreter_sha256",
        "provider_interpreter_version",
        "lium_sdk_distribution",
        "lium_sdk_version",
        "lium_cli_path",
        "lium_cli_sha256",
        "lium_cli_version",
        "working_directory",
        "environment",
        "credential_transport",
        "template_id",
        "template_image",
        "template_tag",
        "template_status",
        "ssh_public_key_path",
        "ssh_public_key_sha256",
        "issue_number",
        "allocation_name",
        "argv",
        "gpu_type",
        "gpu_count",
        "ttl_seconds",
        "max_cost_usd",
        "max_node_hourly_rate_usd",
        "observed_node_hourly_rate_usd",
        "observed_node_hourly_rate_status",
        "max_node_hours",
        "provider_timeout_seconds",
    }
)
_ENVELOPE_FIELDS = frozenset({"schema", "key_id", "payload", "signature_base64"})
_PUBLIC_KEY_FIELDS = frozenset({"schema", "algorithm", "key_id", "public_key_base64"})


class PermitError(RuntimeError):
    """Base class for all fail-closed permit failures."""


class PermitFormatError(PermitError):
    """The permit or trust document is malformed or violates policy."""


class PermitVerificationError(PermitError):
    """The permit signature or an independently supplied binding is invalid."""


class PermitReplayError(PermitError):
    """The request ID and nonce have already been consumed."""


@dataclass(frozen=True)
class VerifiedPermit:
    payload: Mapping[str, Any]
    key_id: str
    argv: tuple[str, ...]
    issued_at: datetime
    expires_at: datetime
    permit_sha256: str
    parent_request_path: str = ""
    provider_executable: str = ""
    provider_interpreter: str = ""
    working_directory: str = ""
    environment_sha256: str = ""

    @property
    def request_id(self) -> str:
        return str(self.payload["request_id"])

    @property
    def nonce(self) -> str:
        return str(self.payload["nonce"])


@dataclass(frozen=True)
class LoadedPublicKeyDocument:
    key_id: str
    verifier: Ed25519PublicKey = dataclass_field(repr=False)


def canonical_json_bytes(value: Any) -> bytes:
    """Return the sole byte representation covered by an Ed25519 signature."""

    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise PermitFormatError(f"value is not canonical-JSON encodable: {exc}") from exc
    return rendered.encode("utf-8")


def domain_separated_message(domain: bytes, payload: Any) -> bytes:
    """Return a canonical JSON message under an explicit versioned domain."""

    if (
        not isinstance(domain, bytes)
        or not 0 < len(domain) <= 255
        or not domain.endswith(b"\x00")
        or re.search(rb"/v[1-9][0-9]*\x00\Z", domain) is None
    ):
        raise PermitFormatError("signature domain must be 1-255 bytes and end in /v<version>\\0")
    return domain + canonical_json_bytes(payload)


def permit_signing_message(payload: Mapping[str, Any]) -> bytes:
    """Build the versioned, domain-separated Ed25519 message."""

    return domain_separated_message(SIGNATURE_DOMAIN, payload)


def load_public_key_document(
    path: str | Path, *, expected_key_id: str | None = None
) -> LoadedPublicKeyDocument:
    """Load and authenticate a public-key document for detached verification."""

    document = _load_json_object(path, max_bytes=8 * 1024)
    document_key_id = document.get("key_id")
    if not isinstance(document_key_id, str):
        raise PermitFormatError("public key document key_id must be text")
    verifier, key_id = _load_public_key(
        document, expected_key_id if expected_key_id is not None else document_key_id
    )
    return LoadedPublicKeyDocument(key_id=key_id, verifier=verifier)


def verify_detached_signature(
    public_key: LoadedPublicKeyDocument,
    *,
    domain: bytes,
    payload: Any,
    signature_base64: str,
) -> str:
    """Verify a detached Ed25519 signature and return the authenticated key ID."""

    if not isinstance(public_key, LoadedPublicKeyDocument):
        raise PermitFormatError("public_key must be a loaded public-key document")
    signature = _decode_base64(signature_base64, expected_length=64, label="signature")
    try:
        public_key.verifier.verify(signature, domain_separated_message(domain, payload))
    except InvalidSignature as exc:
        raise PermitVerificationError("Ed25519 signature verification failed") from exc
    return public_key.key_id


def key_id_for_public_key(public_key_bytes: bytes) -> str:
    if len(public_key_bytes) != 32:
        raise PermitFormatError("Ed25519 public key must be exactly 32 bytes")
    return "ed25519-sha256:" + hashlib.sha256(public_key_bytes).hexdigest()


def load_and_verify_permit(
    permit_path: str | Path,
    public_key_path: str | Path,
    *,
    expected_key_id: str,
    expected_sentry_principal: str,
    expected_executor_principal: str,
    expected_executor_id: str,
    expected_provider: str,
    expected_profile: str,
    expected_source_sha256: str,
    expected_runtime_sha256: str,
    expected_data_sha256: str,
    expected_checkpoint_sha256: str,
    parent_request_path: str | Path,
    expected_provider_version: str,
    expected_working_directory: str | Path,
    expected_argv: Sequence[str],
    now: datetime | None = None,
) -> VerifiedPermit:
    permit_file = Path(permit_path)
    envelope = _load_json_object(permit_file, max_bytes=64 * 1024)
    public_key_document = _load_json_object(public_key_path, max_bytes=8 * 1024)
    permit_sha256 = hashlib.sha256(permit_file.read_bytes()).hexdigest()
    verified = verify_permit(
        envelope,
        public_key_document,
        expected_key_id=expected_key_id,
        expected_sentry_principal=expected_sentry_principal,
        expected_executor_principal=expected_executor_principal,
        expected_executor_id=expected_executor_id,
        expected_provider=expected_provider,
        expected_profile=expected_profile,
        expected_source_sha256=expected_source_sha256,
        expected_runtime_sha256=expected_runtime_sha256,
        expected_data_sha256=expected_data_sha256,
        expected_checkpoint_sha256=expected_checkpoint_sha256,
        expected_provider_version=expected_provider_version,
        expected_working_directory=str(expected_working_directory),
        expected_argv=expected_argv,
        now=now,
        permit_sha256=permit_sha256,
    )
    parent_path = Path(parent_request_path)
    parent_digest = _sha256_bound_file(parent_path, label="parent booking request")
    if parent_digest != verified.payload["parent_request_sha256"]:
        raise PermitVerificationError("parent booking-request artifact digest mismatch")
    executable = Path(verified.payload["provider_executable"])
    executable_digest = _sha256_bound_file(
        executable, label="provider executable", require_executable=True
    )
    if executable_digest != verified.payload["provider_executable_sha256"]:
        raise PermitVerificationError("provider executable digest mismatch")
    interpreter = Path(verified.payload["provider_interpreter"])
    if (
        _sha256_bound_file(interpreter, label="provider interpreter", require_executable=True)
        != verified.payload["provider_interpreter_sha256"]
    ):
        raise PermitVerificationError("provider interpreter digest mismatch")
    cli_path = Path(verified.payload["lium_cli_path"])
    if (
        _sha256_bound_file(cli_path, label="Lium CLI", require_executable=True)
        != verified.payload["lium_cli_sha256"]
    ):
        raise PermitVerificationError("Lium CLI digest mismatch")
    ssh_public_key_path = Path(verified.payload["ssh_public_key_path"])
    if (
        _sha256_bound_file(ssh_public_key_path, label="SSH public key")
        != verified.payload["ssh_public_key_sha256"]
    ):
        raise PermitVerificationError("SSH public key digest mismatch")
    return replace(
        verified,
        parent_request_path=str(parent_path.resolve()),
        provider_executable=str(executable),
        provider_interpreter=str(interpreter),
        working_directory=str(verified.payload["working_directory"]),
        environment_sha256=_environment_binding_sha256(verified.payload),
    )


def verify_permit(
    envelope: Mapping[str, Any],
    public_key_document: Mapping[str, Any],
    *,
    expected_key_id: str,
    expected_sentry_principal: str,
    expected_executor_principal: str,
    expected_executor_id: str,
    expected_provider: str,
    expected_profile: str,
    expected_source_sha256: str,
    expected_runtime_sha256: str,
    expected_data_sha256: str,
    expected_checkpoint_sha256: str,
    expected_provider_version: str,
    expected_working_directory: str,
    expected_argv: Sequence[str],
    now: datetime | None = None,
    permit_sha256: str = "",
) -> VerifiedPermit:
    """Authenticate a permit and verify every launch-affecting binding."""

    _require_exact_fields(envelope, _ENVELOPE_FIELDS, "permit envelope")
    if envelope.get("schema") != ENVELOPE_SCHEMA:
        raise PermitFormatError("permit envelope schema mismatch")
    if not isinstance(envelope.get("payload"), Mapping):
        raise PermitFormatError("permit payload must be an object")

    public_key, key_id = _load_public_key(public_key_document, expected_key_id)
    if envelope.get("key_id") != key_id:
        raise PermitVerificationError("permit key_id does not match trusted public key")
    payload = dict(envelope["payload"])
    verify_detached_signature(
        LoadedPublicKeyDocument(key_id=key_id, verifier=public_key),
        domain=SIGNATURE_DOMAIN,
        payload=payload,
        signature_base64=envelope.get("signature_base64"),
    )

    issued_at, expires_at, argv = _validate_payload(
        payload,
        expected_sentry_principal=expected_sentry_principal,
        expected_executor_principal=expected_executor_principal,
        expected_executor_id=expected_executor_id,
        expected_provider=expected_provider,
        expected_profile=expected_profile,
        expected_source_sha256=expected_source_sha256,
        expected_runtime_sha256=expected_runtime_sha256,
        expected_data_sha256=expected_data_sha256,
        expected_checkpoint_sha256=expected_checkpoint_sha256,
        expected_provider_version=expected_provider_version,
        expected_working_directory=expected_working_directory,
        expected_argv=expected_argv,
        now=now,
    )
    return VerifiedPermit(
        payload=payload,
        key_id=key_id,
        argv=argv,
        issued_at=issued_at,
        expires_at=expires_at,
        permit_sha256=permit_sha256,
    )


def consume_permit_once(
    permit: VerifiedPermit,
    ledger_dir: str | Path,
    *,
    now: datetime | None = None,
) -> Path:
    """Atomically consume the request-id/nonce pair before provider execution."""

    ledger = Path(ledger_dir)
    ledger.mkdir(mode=0o700, parents=True, exist_ok=True)
    ledger_stat = ledger.lstat()
    if not stat.S_ISDIR(ledger_stat.st_mode) or stat.S_ISLNK(ledger_stat.st_mode):
        raise PermitReplayError("permit ledger is not a real directory")

    claim_material = canonical_json_bytes({"nonce": permit.nonce, "request_id": permit.request_id})
    claim_id = hashlib.sha256(claim_material).hexdigest()
    claim_path = ledger / f"{claim_id}.consumed.json"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(claim_path, flags, 0o600)
    except FileExistsError as exc:
        raise PermitReplayError("permit request_id and nonce already consumed") from exc
    except OSError as exc:
        raise PermitReplayError(f"unable to atomically consume permit: {exc}") from exc

    consumed_at = _utc_now(now).strftime("%Y-%m-%dT%H:%M:%SZ")
    record = (
        canonical_json_bytes(
            {
                "key_id": permit.key_id,
                "nonce": permit.nonce,
                "permit_sha256": permit.permit_sha256,
                "request_id": permit.request_id,
                "consumed_at": consumed_at,
            }
        )
        + b"\n"
    )
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(record)
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(ledger)
    except OSError as exc:
        raise PermitReplayError(f"permit claim could not be durably recorded: {exc}") from exc
    return claim_path


def wrapper_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Launch one exact signed Lium H100 booking command"
    )
    parser.add_argument("--permit", required=True)
    parser.add_argument("--public-key", required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--sentry-principal", required=True)
    parser.add_argument("--executor-principal", required=True)
    parser.add_argument("--executor-id", required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--runtime-sha256", required=True)
    parser.add_argument("--data-sha256", required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--parent-request", required=True)
    parser.add_argument("--provider-version", required=True)
    parser.add_argument("--working-directory", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--provider-output", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("the exact signed lium up argv is required after --")

    try:
        permit = load_and_verify_permit(
            args.permit,
            args.public_key,
            expected_key_id=args.key_id,
            expected_sentry_principal=args.sentry_principal,
            expected_executor_principal=args.executor_principal,
            expected_executor_id=args.executor_id,
            expected_provider=args.provider,
            expected_profile=args.profile,
            expected_source_sha256=args.source_sha256,
            expected_runtime_sha256=args.runtime_sha256,
            expected_data_sha256=args.data_sha256,
            expected_checkpoint_sha256=args.checkpoint_sha256,
            parent_request_path=args.parent_request,
            expected_provider_version=args.provider_version,
            expected_working_directory=args.working_directory,
            expected_argv=command,
        )
        provider_environment = _build_provider_environment(permit.payload)
        executable_descriptor = _open_verified_executable(permit)
        interpreter_descriptor = _open_verified_interpreter(permit, executable_descriptor)
        cli_descriptor = _open_verified_cli(permit)
        _verify_runtime_evidence(
            permit,
            executable_descriptor=executable_descriptor,
            interpreter_descriptor=interpreter_descriptor,
            cli_descriptor=cli_descriptor,
            provider_environment=provider_environment,
        )
        credential = _read_stdin_credential()
        claim_path = consume_permit_once(permit, GATE0_CONSUMPTION_ROOT)
        _reserve_receipt(Path(args.receipt), permit)
        _reserve_provider_output(Path(args.provider_output))
    except PermitError as exc:
        for descriptor_name in (
            "cli_descriptor",
            "interpreter_descriptor",
            "executable_descriptor",
        ):
            if descriptor_name in locals():
                os.close(locals()[descriptor_name])
        if "credential" in locals():
            _wipe_bytearray(credential)
        _print_failure(type(exc).__name__, str(exc))
        return 2

    started_at = _utc_timestamp()
    provider_output = b""
    execution_error = False
    timed_out = False
    try:
        process = _start_provider_process(
            permit,
            executable_descriptor=executable_descriptor,
            interpreter_descriptor=interpreter_descriptor,
            provider_environment=provider_environment,
        )
        credential.append(10)
        try:
            provider_output, _ = process.communicate(
                input=credential, timeout=int(permit.payload["provider_timeout_seconds"])
            )
            exit_code: int | None = process.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            provider_output, _ = process.communicate()
            exit_code = process.returncode
    except (OSError, PermitError):
        execution_error = True
        exit_code = None
    finally:
        _wipe_bytearray(credential)
        os.close(cli_descriptor)
        os.close(interpreter_descriptor)
        os.close(executable_descriptor)
    finished_at = _utc_timestamp()
    if execution_error:
        wrapper_exit_code = 126
    elif timed_out:
        wrapper_exit_code = 124
    else:
        wrapper_exit_code = int(exit_code)
    try:
        _replace_reserved_output(Path(args.provider_output), provider_output)
    except PermitError as exc:
        _print_failure(type(exc).__name__, str(exc))
        return 125
    receipt = _build_launch_receipt(
        permit=permit,
        permit_path=Path(args.permit),
        claim_path=claim_path,
        parent_request_path=Path(args.parent_request),
        provider_output_path=Path(args.provider_output),
        provider_output=provider_output,
        started_at=started_at,
        finished_at=finished_at,
        exit_code=exit_code,
        wrapper_exit_code=wrapper_exit_code,
        execution_error=execution_error,
        timed_out=timed_out,
    )
    try:
        _replace_reserved_receipt(Path(args.receipt), receipt)
    except PermitError as exc:
        _print_failure(type(exc).__name__, str(exc))
        return 125
    if execution_error:
        _print_failure("ProviderExecutionError", "verified executable could not be invoked")
        return wrapper_exit_code
    if timed_out:
        _print_failure("ProviderTimeout", "provider launch exceeded signed timeout")
        return wrapper_exit_code
    return wrapper_exit_code


def _validate_payload(
    payload: Mapping[str, Any],
    *,
    expected_sentry_principal: str,
    expected_executor_principal: str,
    expected_executor_id: str,
    expected_provider: str,
    expected_profile: str,
    expected_source_sha256: str,
    expected_runtime_sha256: str,
    expected_data_sha256: str,
    expected_checkpoint_sha256: str,
    expected_provider_version: str,
    expected_working_directory: str,
    expected_argv: Sequence[str],
    now: datetime | None,
) -> tuple[datetime, datetime, tuple[str, ...]]:
    _require_exact_fields(payload, _PAYLOAD_FIELDS, "permit payload")
    _require_equal(payload, "schema", PERMIT_SCHEMA)
    _require_equal(payload, "stage", REQUIRED_STAGE)
    _require_equal(payload, "decision", REQUIRED_DECISION)

    request_id = _require_string(payload, "request_id", _REQUEST_ID_RE)
    if not request_id:
        raise PermitFormatError("request_id is empty")
    nonce = _require_string(payload, "nonce", _HEX_256_RE)
    if len(bytes.fromhex(nonce)) != 32:
        raise PermitFormatError("nonce must contain exactly 256 bits")
    expected_hashes = {
        "source_sha256": expected_source_sha256,
        "runtime_sha256": expected_runtime_sha256,
        "data_sha256": expected_data_sha256,
        "checkpoint_sha256": expected_checkpoint_sha256,
    }
    for field, expected_hash in expected_hashes.items():
        if _HEX_256_RE.fullmatch(expected_hash) is None:
            raise PermitFormatError(f"expected {field} has invalid format")
        _require_string(payload, field, _HEX_256_RE)
        if payload[field] != expected_hash:
            raise PermitVerificationError(f"{field} mismatch")
    _require_string(payload, "parent_request_sha256", _HEX_256_RE)
    _require_string(payload, "provider_executable_sha256", _HEX_256_RE)

    _require_expected_principal(payload, "sentry_principal", expected_sentry_principal)
    _require_expected_principal(payload, "executor_principal", expected_executor_principal)
    _require_expected_identifier(payload, "executor_id", expected_executor_id)
    _require_expected_identifier(payload, "profile", expected_profile)
    _require_expected_identifier(payload, "provider", expected_provider)
    if payload["provider"] != REQUIRED_PROVIDER:
        raise PermitVerificationError("only provider=lium is permitted")
    provider_version = _require_string(payload, "provider_version", _VERSION_RE)
    if _VERSION_RE.fullmatch(expected_provider_version) is None:
        raise PermitFormatError("expected provider_version has invalid format")
    if provider_version != expected_provider_version:
        raise PermitVerificationError("provider_version mismatch")

    executable = _require_absolute_path(payload, "provider_executable")
    working_directory = _require_absolute_path(payload, "working_directory")
    expected_cwd = Path(expected_working_directory)
    if not expected_cwd.is_absolute() or str(expected_cwd) != working_directory:
        raise PermitVerificationError("working_directory mismatch")
    _validate_working_directory(Path(working_directory))
    environment = _validate_environment(payload)
    _require_equal(payload, "credential_transport", CREDENTIAL_TRANSPORT)
    _require_absolute_path(payload, "ssh_public_key_path")
    _require_string(payload, "ssh_public_key_sha256", _HEX_256_RE)
    _require_string(payload, "provider_interpreter_sha256", _HEX_256_RE)
    _require_string(payload, "lium_cli_sha256", _HEX_256_RE)
    _require_absolute_path(payload, "provider_interpreter")
    _require_absolute_path(payload, "lium_cli_path")
    _require_string(payload, "provider_interpreter_version", _VERSION_RE)
    _require_equal(payload, "lium_sdk_distribution", "lium.io")
    _require_string(payload, "lium_sdk_version", _VERSION_RE)
    _require_string(payload, "lium_cli_version", _VERSION_RE)
    _require_string(payload, "template_id", _IDENTIFIER_RE)
    _require_string(payload, "template_image", _IDENTIFIER_RE)
    _require_string(payload, "template_tag", _VERSION_RE)
    template_status = _require_string(payload, "template_status", _IDENTIFIER_RE)
    if template_status not in {
        "ACTIVE",
        "AVAILABLE",
        "READY",
        "SUCCESS",
        "VERIFIED",
        "VERIFY_SUCCESS",
    }:
        raise PermitVerificationError("template_status is not usable")

    issued_at = _parse_utc(payload.get("issued_at"), "issued_at")
    expires_at = _parse_utc(payload.get("expires_at"), "expires_at")
    lifetime_seconds = (expires_at - issued_at).total_seconds()
    if lifetime_seconds <= 0 or lifetime_seconds > MAX_PERMIT_VALIDITY_SECONDS:
        raise PermitVerificationError("permit validity must be in (0, 10m]")
    current = _utc_now(now)
    if current < issued_at:
        raise PermitVerificationError("permit is not yet valid")
    if current >= expires_at:
        raise PermitVerificationError("permit is expired")

    gpu_count = _require_int(payload, "gpu_count")
    if payload.get("gpu_type") != REQUIRED_GPU_TYPE or gpu_count != REQUIRED_GPU_COUNT:
        raise PermitVerificationError("permit must bind exactly 8xH100")

    ttl_seconds = _require_int(payload, "ttl_seconds")
    if not 0 < ttl_seconds <= MAX_TTL_SECONDS:
        raise PermitVerificationError("provider TTL must be in (0, 2h]")
    provider_timeout_seconds = _require_int(payload, "provider_timeout_seconds")
    if not 0 < provider_timeout_seconds <= MAX_PROVIDER_TIMEOUT_SECONDS:
        raise PermitVerificationError("provider timeout must be in (0, 300s]")
    max_cost = _require_decimal(payload, "max_cost_usd")
    max_hourly_rate = _require_decimal(payload, "max_node_hourly_rate_usd")
    observed_hourly_rate = _require_decimal(payload, "observed_node_hourly_rate_usd")
    observed_rate_status = _require_string(
        payload, "observed_node_hourly_rate_status", _IDENTIFIER_RE
    )
    max_node_hours = _require_decimal(payload, "max_node_hours")
    if not Decimal("0") < max_cost <= MAX_COST_USD:
        raise PermitVerificationError("max_cost_usd exceeds the $36 tranche")
    if not Decimal("0") < max_hourly_rate <= MAX_NODE_HOURLY_RATE_USD:
        raise PermitVerificationError("max_node_hourly_rate_usd exceeds $18")
    if not Decimal("0") <= observed_hourly_rate <= max_hourly_rate:
        raise PermitVerificationError("observed node rate must be between zero and the cap")
    expected_rate_status = (
        "provider_reported_zero" if observed_hourly_rate == 0 else "provider_reported_nonzero"
    )
    if observed_rate_status != expected_rate_status:
        raise PermitVerificationError("observed node rate status does not match the API value")
    if not Decimal("0") < max_node_hours <= MAX_NODE_HOURS:
        raise PermitVerificationError("max_node_hours exceeds 2h")
    ttl_hours = Decimal(ttl_seconds) / Decimal(3600)
    if ttl_hours > max_node_hours or ttl_hours * max_hourly_rate > max_cost:
        raise PermitVerificationError("TTL and budget fields are internally inconsistent")

    issue_number = _require_int(payload, "issue_number")
    if issue_number <= 0:
        raise PermitFormatError("issue_number must be positive")
    allocation_name = _require_string(payload, "allocation_name", _ALLOCATION_RE)
    allocation_match = _ALLOCATION_RE.fullmatch(allocation_name)
    if allocation_match is None or int(allocation_match.group(1)) != issue_number:
        raise PermitVerificationError("allocation_name is not owned by issue_number")
    argv = _validate_command(
        payload.get("argv"),
        expected_argv,
        expected_executor_id,
        executable,
        allocation_name,
        payload,
    )
    if _command_ttl_seconds(argv) != ttl_seconds:
        raise PermitVerificationError("signed command TTL does not match ttl_seconds")
    if environment != payload["environment"]:
        raise AssertionError("validated environment changed unexpectedly")
    return issued_at, expires_at, argv


def _validate_command(
    value: Any,
    expected_argv: Sequence[str],
    expected_executor_id: str,
    provider_executable: str,
    allocation_name: str,
    payload: Mapping[str, Any],
) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise PermitFormatError("argv must be a non-empty JSON array")
    if any(
        not isinstance(token, str) or not token or any(ord(character) < 32 for character in token)
        for token in value
    ):
        raise PermitFormatError("argv entries must be non-empty strings without controls")
    argv = tuple(value)
    if argv != tuple(expected_argv):
        raise PermitVerificationError("runtime argv does not match signed argv")
    if len(argv) < 6 or argv[:2] != (provider_executable, "up"):
        raise PermitVerificationError(
            "signed command must begin with the absolute provider executable and up"
        )
    if argv[2] != expected_executor_id or argv[2].startswith("-"):
        raise PermitVerificationError("signed command does not select the exact executor_id")
    selection_overrides = {"--executor", "--executor-id", "--gpu", "--count", "-c"}
    if any(token.partition("=")[0] in selection_overrides for token in argv[3:]):
        raise PermitVerificationError("signed command contains a forbidden selection override")
    if _command_option_values(argv, "--name") != [allocation_name]:
        raise PermitVerificationError(
            "signed command must contain the exact issue-owned allocation name"
        )
    expected_options = {
        "--template-id": str(payload["template_id"]),
        "--template-image": str(payload["template_image"]),
        "--template-tag": str(payload["template_tag"]),
        "--template-status": str(payload["template_status"]),
        "--expected-provider-version": str(payload["provider_version"]),
        "--expected-interpreter-path": str(payload["provider_interpreter"]),
        "--expected-interpreter-sha256": str(payload["provider_interpreter_sha256"]),
        "--expected-interpreter-version": str(payload["provider_interpreter_version"]),
        "--expected-lium-sdk-version": str(payload["lium_sdk_version"]),
        "--expected-lium-cli-path": str(payload["lium_cli_path"]),
        "--expected-lium-cli-sha256": str(payload["lium_cli_sha256"]),
        "--expected-lium-cli-version": str(payload["lium_cli_version"]),
        "--ssh-public-key-path": str(payload["ssh_public_key_path"]),
        "--ssh-public-key-sha256": str(payload["ssh_public_key_sha256"]),
    }
    for option, expected in expected_options.items():
        if _command_option_values(argv, option) != [expected]:
            raise PermitVerificationError(f"signed command {option} mismatch")
    max_rates = _command_option_values(argv, "--max-rate")
    if len(max_rates) != 1 or _require_decimal(
        {"value": max_rates[0]}, "value"
    ) != _require_decimal(payload, "max_node_hourly_rate_usd"):
        raise PermitVerificationError("signed command --max-rate mismatch")
    return argv


def _command_ttl_seconds(argv: Sequence[str]) -> int:
    values: list[str] = []
    index = 3
    while index < len(argv):
        token = argv[index]
        if token == "--ttl":
            if index + 1 >= len(argv):
                raise PermitFormatError("--ttl requires a value")
            values.append(argv[index + 1])
            index += 2
            continue
        if token.startswith("--ttl="):
            values.append(token.partition("=")[2])
        index += 1
    if len(values) != 1:
        raise PermitVerificationError("signed command must contain exactly one --ttl")
    match = _TTL_RE.fullmatch(values[0])
    if match is None:
        raise PermitFormatError("command TTL must use an integer h or m suffix")
    magnitude = int(match.group(1))
    return magnitude * (3600 if match.group(2) == "h" else 60)


def _command_option_values(argv: Sequence[str], option: str) -> list[str]:
    values: list[str] = []
    index = 3
    while index < len(argv):
        token = argv[index]
        if token == option:
            if index + 1 >= len(argv):
                raise PermitFormatError(f"{option} requires a value")
            values.append(argv[index + 1])
            index += 2
            continue
        if token.startswith(option + "="):
            values.append(token.partition("=")[2])
        index += 1
    return values


def _require_absolute_path(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value or "\x00" in value or not Path(value).is_absolute():
        raise PermitFormatError(f"{field} must be an absolute path")
    return value


def _validate_working_directory(path: Path) -> None:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise PermitVerificationError(f"working_directory is unavailable: {exc}") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise PermitVerificationError("working_directory must be a real directory")


def _validate_environment(payload: Mapping[str, Any]) -> dict[str, str]:
    environment = payload.get("environment")
    if not isinstance(environment, dict) or len(environment) > 64:
        raise PermitFormatError("environment must be an object with at most 64 entries")
    sanitized: dict[str, str] = {}
    for name, value in environment.items():
        if not isinstance(name, str) or _ENV_NAME_RE.fullmatch(name) is None:
            raise PermitFormatError("environment contains an invalid variable name")
        if (
            name in _FORBIDDEN_ENV_NAMES
            or name.startswith("DYLD_")
            or _SECRETISH_ENV_RE.search(name)
        ):
            raise PermitVerificationError(f"environment contains forbidden name: {name}")
        if (
            not isinstance(value, str)
            or len(value) > 8192
            or any(ord(character) < 32 for character in value)
        ):
            raise PermitFormatError(f"environment value for {name} is not sanitized text")
        sanitized[name] = value

    return sanitized


def _environment_binding_sha256(payload: Mapping[str, Any]) -> str:
    binding = {
        "environment": _validate_environment(payload),
        "credential_transport": payload["credential_transport"],
    }
    return hashlib.sha256(canonical_json_bytes(binding)).hexdigest()


def _build_provider_environment(payload: Mapping[str, Any]) -> dict[str, str]:
    provider_environment = dict(_validate_environment(payload))
    provider_environment.pop("LIUM_API_KEY", None)
    return provider_environment


def _open_bound_file(path: Path, *, label: str, require_executable: bool = False) -> int:
    try:
        before = path.lstat()
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
            raise PermitVerificationError(f"{label} must be a real regular file")
        if require_executable and before.st_mode & 0o111 == 0:
            raise PermitVerificationError(f"{label} is not executable")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        after = os.fstat(descriptor)
    except PermitError:
        raise
    except OSError as exc:
        raise PermitVerificationError(f"cannot open {label}: {exc}") from exc
    if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
        os.close(descriptor)
        raise PermitVerificationError(f"{label} changed while opening")
    return descriptor


def _sha256_descriptor(descriptor: int) -> str:
    digest = hashlib.sha256()
    os.lseek(descriptor, 0, os.SEEK_SET)
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return digest.hexdigest()


def _sha256_bound_file(path: Path, *, label: str, require_executable: bool = False) -> str:
    descriptor = _open_bound_file(path, label=label, require_executable=require_executable)
    try:
        return _sha256_descriptor(descriptor)
    finally:
        os.close(descriptor)


def _open_verified_executable(permit: VerifiedPermit) -> int:
    descriptor = _open_bound_file(
        Path(permit.provider_executable),
        label="provider executable",
        require_executable=True,
    )
    if _sha256_descriptor(descriptor) != permit.payload["provider_executable_sha256"]:
        os.close(descriptor)
        raise PermitVerificationError("provider executable changed after verification")
    return descriptor


def _read_shebang_interpreter(descriptor: int) -> str:
    os.lseek(descriptor, 0, os.SEEK_SET)
    first_line = os.read(descriptor, 4096).splitlines()[:1]
    os.lseek(descriptor, 0, os.SEEK_SET)
    if not first_line or not first_line[0].startswith(b"#!"):
        raise PermitVerificationError("provider executable has no absolute shebang")
    try:
        shebang = first_line[0][2:].decode("ascii")
    except UnicodeDecodeError as exc:
        raise PermitVerificationError("provider shebang is not ASCII") from exc
    if not shebang or any(character.isspace() for character in shebang):
        raise PermitVerificationError("provider shebang must contain one interpreter path")
    if not Path(shebang).is_absolute():
        raise PermitVerificationError("provider shebang interpreter must be absolute")
    return shebang


def _open_verified_interpreter(permit: VerifiedPermit, script_descriptor: int) -> int:
    if _read_shebang_interpreter(script_descriptor) != permit.provider_interpreter:
        raise PermitVerificationError("provider shebang interpreter mismatch")
    descriptor = _open_bound_file(
        Path(permit.provider_interpreter),
        label="provider interpreter",
        require_executable=True,
    )
    if _sha256_descriptor(descriptor) != permit.payload["provider_interpreter_sha256"]:
        os.close(descriptor)
        raise PermitVerificationError("provider interpreter changed after verification")
    return descriptor


def _open_verified_cli(permit: VerifiedPermit) -> int:
    descriptor = _open_bound_file(
        Path(str(permit.payload["lium_cli_path"])),
        label="Lium CLI",
        require_executable=True,
    )
    if _sha256_descriptor(descriptor) != permit.payload["lium_cli_sha256"]:
        os.close(descriptor)
        raise PermitVerificationError("Lium CLI changed after verification")
    return descriptor


def _recheck_path_identity(
    path: Path,
    descriptor: int,
    expected_sha256: str,
    *,
    label: str,
) -> None:
    try:
        path_metadata = path.lstat()
        descriptor_metadata = os.fstat(descriptor)
    except OSError as exc:
        raise PermitVerificationError(f"{label} identity check failed: {exc}") from exc
    if stat.S_ISLNK(path_metadata.st_mode) or not stat.S_ISREG(path_metadata.st_mode):
        raise PermitVerificationError(f"{label} path was substituted")
    identity_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    if any(
        getattr(path_metadata, field) != getattr(descriptor_metadata, field)
        for field in identity_fields
    ):
        raise PermitVerificationError(f"{label} changed before launch")
    if _sha256_descriptor(descriptor) != expected_sha256:
        raise PermitVerificationError(f"{label} digest changed before launch")


def _provider_loader_command(
    permit: VerifiedPermit,
    executable_descriptor: int,
    script_args: Sequence[str],
) -> list[str]:
    return [
        permit.provider_interpreter,
        "-I",
        "-c",
        PROVIDER_FD_LOADER,
        f"/dev/fd/{executable_descriptor}",
        permit.provider_executable,
        *script_args,
    ]


def _run_probe(
    command: Sequence[str],
    *,
    env: Mapping[str, str],
    cwd: str,
    pass_fds: Sequence[int] = (),
) -> str:
    try:
        result = subprocess.run(
            list(command),
            cwd=cwd,
            env=dict(env),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=15,
            pass_fds=tuple(pass_fds),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PermitVerificationError("runtime evidence probe failed") from exc
    output = result.stdout.decode("utf-8", errors="replace").strip()
    if result.returncode != 0 or not output or "\n" in output:
        raise PermitVerificationError("runtime evidence probe returned invalid output")
    return output


def _verify_runtime_evidence(
    permit: VerifiedPermit,
    *,
    executable_descriptor: int,
    interpreter_descriptor: int,
    cli_descriptor: int,
    provider_environment: Mapping[str, str],
) -> None:
    _recheck_path_identity(
        Path(permit.provider_interpreter),
        interpreter_descriptor,
        str(permit.payload["provider_interpreter_sha256"]),
        label="provider interpreter",
    )
    interpreter_version = _run_probe(
        [
            permit.provider_interpreter,
            "-I",
            "-c",
            "import platform;print(platform.python_version())",
        ],
        env=provider_environment,
        cwd=permit.working_directory,
    )
    sdk_version = _run_probe(
        [
            permit.provider_interpreter,
            "-I",
            "-c",
            "import importlib.metadata as m;print(m.version('lium.io'))",
        ],
        env=provider_environment,
        cwd=permit.working_directory,
    )
    provider_version = _run_probe(
        _provider_loader_command(permit, executable_descriptor, ["--version"]),
        env=provider_environment,
        cwd=permit.working_directory,
        pass_fds=(executable_descriptor,),
    )
    _recheck_path_identity(
        Path(str(permit.payload["lium_cli_path"])),
        cli_descriptor,
        str(permit.payload["lium_cli_sha256"]),
        label="Lium CLI",
    )
    cli_version = _run_probe(
        [str(permit.payload["lium_cli_path"]), "--version"],
        env=provider_environment,
        cwd=permit.working_directory,
    )
    if cli_version.startswith("lium, version "):
        cli_version = cli_version.removeprefix("lium, version ")
    expected = {
        "provider interpreter": str(permit.payload["provider_interpreter_version"]),
        "Lium SDK": str(permit.payload["lium_sdk_version"]),
        "provider executable": str(permit.payload["provider_version"]),
        "Lium CLI": str(permit.payload["lium_cli_version"]),
    }
    actual = {
        "provider interpreter": interpreter_version,
        "Lium SDK": sdk_version,
        "provider executable": provider_version,
        "Lium CLI": cli_version,
    }
    for label, expected_value in expected.items():
        if actual[label] != expected_value:
            raise PermitVerificationError(f"{label} version evidence mismatch")


def _start_provider_process(
    permit: VerifiedPermit,
    *,
    executable_descriptor: int,
    interpreter_descriptor: int,
    provider_environment: Mapping[str, str],
) -> subprocess.Popen[bytes]:
    # macOS lacks a usable fexecve path for this Python interpreter. A same-UID
    # replacement between this final identity check and posix_spawn is the
    # irreducible interpreter-path boundary; provider script bytes use the held fd.
    _recheck_path_identity(
        Path(permit.provider_interpreter),
        interpreter_descriptor,
        str(permit.payload["provider_interpreter_sha256"]),
        label="provider interpreter",
    )
    return subprocess.Popen(
        _provider_loader_command(permit, executable_descriptor, permit.argv[1:]),
        executable=permit.provider_interpreter,
        cwd=permit.working_directory,
        env=dict(provider_environment),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        close_fds=True,
        pass_fds=(executable_descriptor,),
    )


def _read_stdin_credential() -> bytearray:
    line = sys.stdin.buffer.readline(MAX_CREDENTIAL_BYTES + 2)
    tail = sys.stdin.buffer.read(1)
    if tail or len(line) > MAX_CREDENTIAL_BYTES + 1:
        raise PermitVerificationError("stdin credential exceeds the bounded single line")
    if line.endswith(b"\n"):
        line = line[:-1]
    if not line or b"\n" in line or b"\r" in line or b"\x00" in line:
        raise PermitVerificationError("stdin credential must be one non-empty sanitized line")
    return bytearray(line)


def _wipe_bytearray(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _reserve_receipt(path: Path, permit: VerifiedPermit) -> None:
    if not path.is_absolute():
        raise PermitFormatError("receipt path must be absolute")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(
                canonical_json_bytes(
                    {
                        "schema": LAUNCH_RECEIPT_SCHEMA,
                        "status": "RESERVED",
                        "permit_sha256": permit.permit_sha256,
                    }
                )
                + b"\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        _fsync_directory(path.parent)
    except FileExistsError as exc:
        raise PermitVerificationError("launch receipt already exists") from exc
    except OSError as exc:
        raise PermitVerificationError(f"cannot reserve launch receipt: {exc}") from exc


def _reserve_provider_output(path: Path) -> None:
    if not path.is_absolute():
        raise PermitFormatError("provider output path must be absolute")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
        os.fsync(descriptor)
        os.close(descriptor)
        _fsync_directory(path.parent)
    except FileExistsError as exc:
        raise PermitVerificationError("provider output already exists") from exc
    except OSError as exc:
        raise PermitVerificationError(f"cannot reserve provider output: {exc}") from exc


def _build_launch_receipt(
    *,
    permit: VerifiedPermit,
    permit_path: Path,
    claim_path: Path,
    parent_request_path: Path,
    provider_output_path: Path,
    provider_output: bytes,
    started_at: str,
    finished_at: str,
    exit_code: int | None,
    wrapper_exit_code: int,
    execution_error: bool,
    timed_out: bool,
) -> dict[str, Any]:
    claim = _load_json_object(claim_path, max_bytes=16 * 1024)
    if timed_out:
        status = "PROVIDER_TIMEOUT"
    elif execution_error:
        status = "PROVIDER_EXECUTION_ERROR"
    elif exit_code == 0:
        status = "COMPLETED"
    else:
        status = "PROVIDER_NONZERO_EXIT"
    return {
        "schema": LAUNCH_RECEIPT_SCHEMA,
        "status": status,
        "permit": {
            "path": str(permit_path.resolve()),
            "sha256": permit.permit_sha256,
            "key_id": permit.key_id,
            "request_id": permit.request_id,
            "nonce": permit.nonce,
            "issued_at": permit.payload["issued_at"],
            "expires_at": permit.payload["expires_at"],
        },
        "claim": {
            "path": str(claim_path.resolve()),
            "sha256": _sha256_bound_file(claim_path, label="permit claim"),
            "consumed_at": claim.get("consumed_at"),
        },
        "parent_request": {
            "path": str(parent_request_path.resolve()),
            "sha256": permit.payload["parent_request_sha256"],
        },
        "provider": {
            "name": permit.payload["provider"],
            "profile": permit.payload["profile"],
            "executor_id": permit.payload["executor_id"],
            "executable": permit.provider_executable,
            "executable_sha256": permit.payload["provider_executable_sha256"],
            "declared_version": permit.payload["provider_version"],
            "interpreter": permit.provider_interpreter,
            "interpreter_sha256": permit.payload["provider_interpreter_sha256"],
            "interpreter_version": permit.payload["provider_interpreter_version"],
            "fd_loader_sha256": hashlib.sha256(PROVIDER_FD_LOADER.encode("utf-8")).hexdigest(),
            "execution_boundary": "script-fd-bound-interpreter-path-rechecked",
        },
        "runtime_evidence": {
            "provider_version": permit.payload["provider_version"],
            "lium_sdk_distribution": permit.payload["lium_sdk_distribution"],
            "lium_sdk_version": permit.payload["lium_sdk_version"],
            "lium_cli_path": permit.payload["lium_cli_path"],
            "lium_cli_sha256": permit.payload["lium_cli_sha256"],
            "lium_cli_version": permit.payload["lium_cli_version"],
        },
        "template": {
            "id": permit.payload["template_id"],
            "image": permit.payload["template_image"],
            "tag": permit.payload["template_tag"],
            "status": permit.payload["template_status"],
        },
        "access": {
            "ssh_public_key_path": permit.payload["ssh_public_key_path"],
            "ssh_public_key_sha256": permit.payload["ssh_public_key_sha256"],
        },
        "provider_output": {
            "path": str(provider_output_path.resolve()),
            "sha256": hashlib.sha256(provider_output).hexdigest(),
            "size_bytes": len(provider_output),
        },
        "allocation": {
            "issue_number": permit.payload["issue_number"],
            "name": permit.payload["allocation_name"],
        },
        "execution": {
            "cwd": permit.working_directory,
            "argv": list(permit.argv),
            "sanitized_environment_sha256": permit.environment_sha256,
            "sanitized_environment_names": sorted(permit.payload["environment"]),
            "credential_transport": permit.payload["credential_transport"],
            "started_at": started_at,
            "finished_at": finished_at,
            "exit_code": exit_code,
            "wrapper_exit_code": wrapper_exit_code,
            "timed_out": timed_out,
            "provider_timeout_seconds": permit.payload["provider_timeout_seconds"],
        },
        "budget": {
            "ttl_seconds": permit.payload["ttl_seconds"],
            "max_cost_usd": permit.payload["max_cost_usd"],
            "max_node_hourly_rate_usd": permit.payload["max_node_hourly_rate_usd"],
            "observed_node_hourly_rate_usd": permit.payload["observed_node_hourly_rate_usd"],
            "observed_node_hourly_rate_status": permit.payload["observed_node_hourly_rate_status"],
            "max_node_hours": permit.payload["max_node_hours"],
        },
    }


def _replace_reserved_output(path: Path, output: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        reserved = path.lstat()
        if stat.S_ISLNK(reserved.st_mode) or not stat.S_ISREG(reserved.st_mode):
            raise PermitVerificationError("reserved provider output path was substituted")
        if reserved.st_size != 0:
            raise PermitVerificationError("reserved provider output was modified")
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(output)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except PermitError:
        raise
    except OSError as exc:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise PermitVerificationError(f"cannot write provider output: {exc}") from exc


def _replace_reserved_receipt(path: Path, receipt: Mapping[str, Any]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(
                json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False).encode("utf-8")
                + b"\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except OSError as exc:
        try:
            temporary.unlink()
        except OSError:
            pass
        raise PermitVerificationError(f"cannot write launch receipt: {exc}") from exc


def _load_public_key(
    document: Mapping[str, Any], expected_key_id: str
) -> tuple[Ed25519PublicKey, str]:
    _require_exact_fields(document, _PUBLIC_KEY_FIELDS, "public key document")
    if document.get("schema") != PUBLIC_KEY_SCHEMA:
        raise PermitFormatError("public key document schema mismatch")
    if document.get("algorithm") != "Ed25519":
        raise PermitFormatError("public key algorithm must be Ed25519")
    raw = _decode_base64(document.get("public_key_base64"), expected_length=32, label="public key")
    derived_key_id = key_id_for_public_key(raw)
    if document.get("key_id") != derived_key_id:
        raise PermitVerificationError("public key document key_id is not derived from its key")
    if expected_key_id != derived_key_id:
        raise PermitVerificationError("expected key_id does not match trusted public key")
    return Ed25519PublicKey.from_public_bytes(raw), derived_key_id


def _load_json_object(path: str | Path, *, max_bytes: int) -> dict[str, Any]:
    source = Path(path)
    try:
        size = source.stat().st_size
        if size > max_bytes:
            raise PermitFormatError(f"JSON document exceeds {max_bytes} bytes")
        text = source.read_text(encoding="utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
    except PermitError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise PermitFormatError(f"cannot load JSON document {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise PermitFormatError("JSON document root must be an object")
    return value


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_non_finite(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _decode_base64(value: Any, *, expected_length: int, label: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise PermitFormatError(f"{label} must be base64 text")
    try:
        decoded = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise PermitFormatError(f"{label} is not strict base64") from exc
    if len(decoded) != expected_length:
        raise PermitFormatError(f"{label} has the wrong byte length")
    return decoded


def _require_exact_fields(value: Mapping[str, Any], expected: frozenset[str], label: str) -> None:
    actual = set(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing or unknown:
        raise PermitFormatError(f"{label} fields mismatch: missing={missing} unknown={unknown}")


def _require_equal(payload: Mapping[str, Any], field: str, expected: str) -> None:
    if payload.get(field) != expected:
        raise PermitVerificationError(f"{field} mismatch")


def _require_string(payload: Mapping[str, Any], field: str, pattern: re.Pattern[str]) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise PermitFormatError(f"{field} has invalid format")
    return value


def _require_expected_principal(payload: Mapping[str, Any], field: str, expected: str) -> None:
    if _IDENTIFIER_RE.fullmatch(expected) is None:
        raise PermitFormatError(f"expected {field} has invalid format")
    _require_string(payload, field, _IDENTIFIER_RE)
    if payload[field] != expected:
        raise PermitVerificationError(f"{field} mismatch")


def _require_expected_identifier(payload: Mapping[str, Any], field: str, expected: str) -> None:
    if _IDENTIFIER_RE.fullmatch(expected) is None:
        raise PermitFormatError(f"expected {field} has invalid format")
    _require_string(payload, field, _IDENTIFIER_RE)
    if payload[field] != expected:
        raise PermitVerificationError(f"{field} mismatch")


def _require_int(payload: Mapping[str, Any], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise PermitFormatError(f"{field} must be an integer")
    return value


def _require_decimal(payload: Mapping[str, Any], field: str) -> Decimal:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise PermitFormatError(f"{field} must be numeric")
    if isinstance(value, float) and not math.isfinite(value):
        raise PermitFormatError(f"{field} must be finite")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise PermitFormatError(f"{field} must be numeric") from exc
    if not number.is_finite():
        raise PermitFormatError(f"{field} must be finite")
    return number


def _parse_utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or _UTC_RE.fullmatch(value) is None:
        raise PermitFormatError(f"{field} must be canonical UTC YYYY-MM-DDTHH:MM:SSZ")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise PermitFormatError(f"{field} is not a valid UTC timestamp") from exc


def _utc_now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise PermitFormatError("current time must be timezone-aware")
    return current.astimezone(timezone.utc)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _print_failure(kind: str, message: str) -> None:
    print(
        json.dumps(
            {
                "schema": "h100-lium-launch-failure/v1",
                "status": "REJECTED",
                "error": kind,
                "message": message,
            },
            sort_keys=True,
        ),
        file=sys.stderr,
        flush=True,
    )


__all__ = [
    "CREDENTIAL_TRANSPORT",
    "DEFAULT_PROVIDER_TIMEOUT_SECONDS",
    "ENVELOPE_SCHEMA",
    "GATE0_CONSUMPTION_ROOT",
    "LAUNCH_RECEIPT_SCHEMA",
    "MAX_PROVIDER_TIMEOUT_SECONDS",
    "MAX_PERMIT_VALIDITY_SECONDS",
    "PERMIT_SCHEMA",
    "PUBLIC_KEY_SCHEMA",
    "SIGNATURE_DOMAIN",
    "LoadedPublicKeyDocument",
    "PermitError",
    "PermitFormatError",
    "PermitReplayError",
    "PermitVerificationError",
    "VerifiedPermit",
    "canonical_json_bytes",
    "consume_permit_once",
    "domain_separated_message",
    "key_id_for_public_key",
    "load_and_verify_permit",
    "load_public_key_document",
    "permit_signing_message",
    "verify_detached_signature",
    "verify_permit",
    "wrapper_main",
]
