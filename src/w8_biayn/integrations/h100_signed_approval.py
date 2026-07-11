"""Verify and consume single-use Ed25519 permits for Lium H100 bookings."""

from __future__ import annotations

import argparse
import base64
import binascii
import fcntl
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
TERMINAL_RECONCILIATION_RECEIPT_SCHEMA = "h100-lium-terminal-reconciliation-receipt/v1"
TERMINAL_RECONCILIATION_RETRY_SCHEMA = "h100-lium-terminal-reconciliation-retry-receipt/v1"
TERMINAL_RECONCILIATION_LEASE_SCHEMA = "h100-lium-terminal-reconciliation-lease/v1"
PROVIDER_OUTPUT_SCHEMA = "lium-h100-pod-create/v2"
PROVIDER_RECONCILIATION_SCHEMA = "lium-h100-allocation-reconciliation/v1"
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
MAX_PROVIDER_OUTPUT_BYTES = 256 * 1024
MAX_RECONCILIATION_OUTPUT_BYTES = 64 * 1024
RECONCILIATION_TIMEOUT_SECONDS = 120
GATE0_CONSUMPTION_ROOT = (
    Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
    / ".local/state/w8-biayn/control-plane/gate0-consumption/v1"
)
PROVIDER_FD_LOADER = (
    "import os, signal, sys\n"
    "fd_path, display_path, hard_timeout_text, *script_args = sys.argv[1:]\n"
    "hard_timeout_seconds = int(hard_timeout_text)\n"
    "def hard_timeout(_signum, _frame):\n"
    "    os._exit(124)\n"
    "signal.signal(signal.SIGALRM, hard_timeout)\n"
    "signal.alarm(hard_timeout_seconds)\n"
    "with open(fd_path, 'rb', buffering=0) as handle:\n"
    "    handle.seek(0)\n"
    "    source = handle.read()\n"
    "sys.argv = [display_path, *script_args]\n"
    "scope = {'__name__': '__main__', '__file__': display_path, "
    "'__package__': None, '__cached__': None}\n"
    "try:\n"
    "    exec(compile(source, display_path, 'exec'), scope, scope)\n"
    "finally:\n"
    "    signal.alarm(0)\n"
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

    ledger, ledger_descriptor = _open_private_ledger(ledger_dir)
    claim_path = _permit_claim_path(permit, ledger)
    claim_name = claim_path.name
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(claim_name, flags, 0o600, dir_fd=ledger_descriptor)
    except FileExistsError as exc:
        os.close(ledger_descriptor)
        raise PermitReplayError("permit request_id and nonce already consumed") from exc
    except OSError as exc:
        os.close(ledger_descriptor)
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
        os.fsync(ledger_descriptor)
    except OSError as exc:
        raise PermitReplayError(f"permit claim could not be durably recorded: {exc}") from exc
    finally:
        os.close(ledger_descriptor)
    return claim_path


def _open_private_ledger(ledger_dir: str | Path) -> tuple[Path, int]:
    ledger = Path(ledger_dir).expanduser()
    if not ledger.is_absolute():
        raise PermitReplayError("permit ledger path must be absolute")
    ledger.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        before = ledger.lstat()
        ledger_descriptor = os.open(ledger, directory_flags)
        after = os.fstat(ledger_descriptor)
    except OSError as exc:
        raise PermitReplayError(f"permit ledger is not a real private directory: {exc}") from exc
    if (
        not stat.S_ISDIR(before.st_mode)
        or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
        or after.st_uid != os.getuid()
        or stat.S_IMODE(after.st_mode) & 0o077
    ):
        os.close(ledger_descriptor)
        raise PermitReplayError("permit ledger must be an owner-only real directory")
    return ledger, ledger_descriptor


def _permit_claim_path(permit: VerifiedPermit, ledger: Path) -> Path:
    claim_material = canonical_json_bytes({"nonce": permit.nonce, "request_id": permit.request_id})
    claim_id = hashlib.sha256(claim_material).hexdigest()
    return ledger / f"{claim_id}.consumed.json"


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
    parser.add_argument("--retry-terminal-reconciliation", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("the exact signed lium up argv is required after --")

    executable_descriptor: int | None = None
    interpreter_descriptor: int | None = None
    cli_descriptor: int | None = None
    terminal_lease_descriptor: int | None = None
    credential: bytearray | None = None
    try:
        verification_now = (
            _cleanup_retry_verification_time(Path(args.permit))
            if args.retry_terminal_reconciliation
            else None
        )
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
            now=verification_now,
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
        if args.retry_terminal_reconciliation:
            retry_exit_code = _retry_terminal_reconciliation(
                permit,
                executable_descriptor=executable_descriptor,
                interpreter_descriptor=interpreter_descriptor,
                provider_environment=provider_environment,
                credential=credential,
            )
            _close_descriptors(cli_descriptor, interpreter_descriptor, executable_descriptor)
            _wipe_bytearray(credential)
            return retry_exit_code
        pre_snapshot = _snapshot_exact_allocation_name(
            permit,
            executable_descriptor=executable_descriptor,
            interpreter_descriptor=interpreter_descriptor,
            provider_environment=provider_environment,
            credential=credential,
        )
        claim_path, terminal_receipt_path = _reserve_terminal_reconciliation_receipt(
            permit,
            ledger_dir=GATE0_CONSUMPTION_ROOT,
            pre_snapshot=pre_snapshot,
        )
        terminal_lease_descriptor, _ = _acquire_terminal_reconciliation_lease(permit, claim_path)
        try:
            consumed_claim_path = consume_permit_once(permit, GATE0_CONSUMPTION_ROOT)
        except PermitError as exc:
            _write_unconsumed_terminal_receipt(
                permit,
                claim_path=claim_path,
                terminal_receipt_path=terminal_receipt_path,
                pre_snapshot=pre_snapshot,
                failure_kind=type(exc).__name__,
            )
            raise
        claim_path = consumed_claim_path
    except PermitError as exc:
        _release_terminal_reconciliation_lease(terminal_lease_descriptor)
        terminal_lease_descriptor = None
        _close_descriptors(cli_descriptor, interpreter_descriptor, executable_descriptor)
        if credential is not None:
            _wipe_bytearray(credential)
        _print_failure(type(exc).__name__, str(exc))
        return 2

    receipt_path = Path(args.receipt)
    provider_output_path = Path(args.provider_output)
    provider_output = b""
    provider_output_valid = False
    execution_error = False
    timed_out = False
    exit_code: int | None = None
    wrapper_exit_code = 0
    failure_kind = ""
    failure_message = ""
    receipt_reserved = False
    output_reserved = False
    started_at = _utc_timestamp()
    try:
        try:
            _reserve_receipt(receipt_path, permit)
            receipt_reserved = True
            _reserve_provider_output(provider_output_path)
            output_reserved = True
        except PermitError as exc:
            wrapper_exit_code = 125
            failure_kind = type(exc).__name__
            failure_message = str(exc)

        if not failure_kind:
            try:
                process = _start_provider_process(
                    permit,
                    executable_descriptor=executable_descriptor,
                    interpreter_descriptor=interpreter_descriptor,
                    terminal_lease_descriptor=terminal_lease_descriptor,
                    provider_environment=provider_environment,
                )
                credential_line = bytearray(credential)
                credential_line.append(10)
                try:
                    try:
                        provider_output, _ = process.communicate(
                            input=credential_line,
                            timeout=int(permit.payload["provider_timeout_seconds"]),
                        )
                        exit_code = process.returncode
                    except subprocess.TimeoutExpired:
                        timed_out = True
                        process.kill()
                        provider_output, _ = process.communicate()
                        exit_code = process.returncode
                finally:
                    _wipe_bytearray(credential_line)
            except (OSError, PermitError):
                execution_error = True
                exit_code = None

            if execution_error:
                wrapper_exit_code = 126
                failure_kind = "ProviderExecutionError"
                failure_message = "verified executable could not be invoked"
            elif timed_out:
                wrapper_exit_code = 124
                failure_kind = "ProviderTimeout"
                failure_message = "provider launch exceeded signed timeout"
            elif exit_code != 0:
                wrapper_exit_code = (
                    int(exit_code) if isinstance(exit_code, int) and exit_code > 0 else 125
                )
                failure_kind = "ProviderNonzeroExit"
                failure_message = "provider launch returned nonzero"
            else:
                try:
                    _validate_successful_provider_output(provider_output, permit)
                    provider_output_valid = True
                except PermitError as exc:
                    wrapper_exit_code = 125
                    failure_kind = type(exc).__name__
                    failure_message = str(exc)

        if output_reserved:
            try:
                _replace_reserved_output(provider_output_path, provider_output)
            except PermitError as exc:
                wrapper_exit_code = 125
                failure_kind = type(exc).__name__
                failure_message = str(exc)

        finished_at = _utc_timestamp()
        if receipt_reserved:
            receipt = _build_launch_receipt(
                permit=permit,
                permit_path=Path(args.permit),
                claim_path=claim_path,
                parent_request_path=Path(args.parent_request),
                provider_output_path=provider_output_path,
                provider_output=provider_output,
                started_at=started_at,
                finished_at=finished_at,
                exit_code=exit_code,
                wrapper_exit_code=wrapper_exit_code,
                execution_error=execution_error,
                timed_out=timed_out,
                provider_output_valid=provider_output_valid,
                terminal_failure_kind=failure_kind,
            )
            try:
                _replace_reserved_receipt(receipt_path, receipt)
            except PermitError as exc:
                wrapper_exit_code = 125
                failure_kind = type(exc).__name__
                failure_message = str(exc)

        if failure_kind:
            reconciliation_confirmed = _finish_terminal_reconciliation(
                permit,
                claim_path=claim_path,
                terminal_receipt_path=terminal_receipt_path,
                pre_snapshot=pre_snapshot,
                executable_descriptor=executable_descriptor,
                interpreter_descriptor=interpreter_descriptor,
                terminal_lease_descriptor=terminal_lease_descriptor,
                provider_environment=provider_environment,
                credential=credential,
                provider_output=provider_output,
                provider_output_path=provider_output_path,
                launch_receipt_path=receipt_path,
                failure_kind=failure_kind,
                wrapper_exit_code=wrapper_exit_code,
            )
            _print_failure(failure_kind, failure_message)
            return wrapper_exit_code if reconciliation_confirmed else 125

        success_receipt = _build_terminal_reconciliation_receipt(
            permit,
            claim_path=claim_path,
            pre_snapshot=pre_snapshot,
            status="LAUNCH_COMPLETED",
            failure_kind="",
            wrapper_exit_code=0,
            reconciliation={"status": "NOT_REQUIRED"},
            provider_output=provider_output,
            provider_output_path=provider_output_path,
            launch_receipt_path=receipt_path,
        )
        try:
            _replace_reserved_terminal_reconciliation_receipt(
                terminal_receipt_path, success_receipt
            )
        except PermitError as exc:
            reconciliation_confirmed = _finish_terminal_reconciliation(
                permit,
                claim_path=claim_path,
                terminal_receipt_path=terminal_receipt_path,
                pre_snapshot=pre_snapshot,
                executable_descriptor=executable_descriptor,
                interpreter_descriptor=interpreter_descriptor,
                terminal_lease_descriptor=terminal_lease_descriptor,
                provider_environment=provider_environment,
                credential=credential,
                provider_output=provider_output,
                provider_output_path=provider_output_path,
                launch_receipt_path=receipt_path,
                failure_kind=type(exc).__name__,
                wrapper_exit_code=125,
            )
            _print_failure(type(exc).__name__, str(exc))
            return 125 if reconciliation_confirmed else 125
        return 0
    except Exception:
        try:
            _finish_terminal_reconciliation(
                permit,
                claim_path=claim_path,
                terminal_receipt_path=terminal_receipt_path,
                pre_snapshot=pre_snapshot,
                executable_descriptor=executable_descriptor,
                interpreter_descriptor=interpreter_descriptor,
                terminal_lease_descriptor=terminal_lease_descriptor,
                provider_environment=provider_environment,
                credential=credential,
                provider_output=provider_output,
                provider_output_path=provider_output_path,
                launch_receipt_path=receipt_path,
                failure_kind="WrapperInternalError",
                wrapper_exit_code=125,
            )
        except Exception:
            pass
        _print_failure("WrapperInternalError", "signed launch wrapper failed closed")
        return 125
    finally:
        _release_terminal_reconciliation_lease(terminal_lease_descriptor)
        _wipe_bytearray(credential)
        _close_descriptors(cli_descriptor, interpreter_descriptor, executable_descriptor)


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
    if not Decimal("0") < observed_hourly_rate <= max_hourly_rate:
        raise PermitVerificationError("observed node rate must be positive and within the cap")
    expected_rate_status = "provider_reported_nonzero"
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
        "--expected-observed-rate": str(payload["observed_node_hourly_rate_usd"]),
        "--expected-rate-authority": "provider_raw_price_per_gpu_x_gpu_count/v1",
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
    *,
    hard_timeout_seconds: int,
) -> list[str]:
    if hard_timeout_seconds <= 0:
        raise PermitVerificationError("provider child hard timeout must be positive")
    return [
        permit.provider_interpreter,
        "-I",
        "-c",
        PROVIDER_FD_LOADER,
        f"/dev/fd/{executable_descriptor}",
        permit.provider_executable,
        str(hard_timeout_seconds),
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
        _provider_loader_command(
            permit,
            executable_descriptor,
            ["--version"],
            hard_timeout_seconds=15,
        ),
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
    terminal_lease_descriptor: int,
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
        _provider_loader_command(
            permit,
            executable_descriptor,
            permit.argv[1:],
            hard_timeout_seconds=int(permit.payload["provider_timeout_seconds"]),
        ),
        executable=permit.provider_interpreter,
        cwd=permit.working_directory,
        env=dict(provider_environment),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        close_fds=True,
        pass_fds=(executable_descriptor, terminal_lease_descriptor),
    )


def _close_descriptors(*descriptors: int | None) -> None:
    for descriptor in descriptors:
        if descriptor is not None:
            os.close(descriptor)


def _provider_control_args(
    permit: VerifiedPermit,
    *,
    mode: str,
    preexisting_ids: Sequence[str] = (),
) -> list[str]:
    arguments = [
        "reconcile",
        "--mode",
        mode,
        "--name",
        str(permit.payload["allocation_name"]),
    ]
    for pod_id in sorted(preexisting_ids):
        arguments.extend(("--preexisting-id", pod_id))
    return arguments


def _run_provider_control(
    permit: VerifiedPermit,
    *,
    mode: str,
    executable_descriptor: int,
    interpreter_descriptor: int,
    provider_environment: Mapping[str, str],
    credential: bytearray,
    preexisting_ids: Sequence[str] = (),
    terminal_lease_descriptor: int | None = None,
) -> dict[str, Any]:
    _recheck_path_identity(
        Path(permit.provider_interpreter),
        interpreter_descriptor,
        str(permit.payload["provider_interpreter_sha256"]),
        label="provider interpreter",
    )
    if mode == "cleanup" and terminal_lease_descriptor is None:
        raise PermitVerificationError("cleanup control requires terminal ownership lease")
    if mode not in {"snapshot", "cleanup"}:
        raise PermitVerificationError("allocation reconciliation mode is invalid")
    pass_fds = [executable_descriptor]
    if terminal_lease_descriptor is not None:
        pass_fds.append(terminal_lease_descriptor)
    try:
        process = subprocess.Popen(
            _provider_loader_command(
                permit,
                executable_descriptor,
                _provider_control_args(
                    permit,
                    mode=mode,
                    preexisting_ids=preexisting_ids,
                ),
                hard_timeout_seconds=RECONCILIATION_TIMEOUT_SECONDS,
            ),
            executable=permit.provider_interpreter,
            cwd=permit.working_directory,
            env=dict(provider_environment),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            close_fds=True,
            pass_fds=tuple(pass_fds),
        )
    except OSError as exc:
        raise PermitVerificationError("allocation reconciliation could not start") from exc
    credential_line = bytearray(credential)
    credential_line.append(10)
    timed_out = False
    try:
        try:
            output, _ = process.communicate(
                input=credential_line,
                timeout=RECONCILIATION_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            output, _ = process.communicate()
    finally:
        _wipe_bytearray(credential_line)
    if len(output) > MAX_RECONCILIATION_OUTPUT_BYTES:
        raise PermitVerificationError("allocation reconciliation output is too large")
    record = _load_single_json_record(output, label="allocation reconciliation output")
    if record.get("schema") != PROVIDER_RECONCILIATION_SCHEMA:
        raise PermitVerificationError("allocation reconciliation schema mismatch")
    if record.get("mode") != mode:
        raise PermitVerificationError("allocation reconciliation mode mismatch")
    if record.get("allocation_name") != permit.payload["allocation_name"]:
        raise PermitVerificationError("allocation reconciliation name mismatch")
    return {
        "exit_code": process.returncode,
        "timed_out": timed_out,
        "output_sha256": hashlib.sha256(output).hexdigest(),
        "output_size_bytes": len(output),
        "record": record,
    }


def _snapshot_exact_allocation_name(
    permit: VerifiedPermit,
    *,
    executable_descriptor: int,
    interpreter_descriptor: int,
    provider_environment: Mapping[str, str],
    credential: bytearray,
) -> dict[str, Any]:
    result = _run_provider_control(
        permit,
        mode="snapshot",
        executable_descriptor=executable_descriptor,
        interpreter_descriptor=interpreter_descriptor,
        provider_environment=provider_environment,
        credential=credential,
    )
    record = result["record"]
    if (
        result["timed_out"]
        or result["exit_code"] != 0
        or record.get("status") != "SNAPSHOT_CLEAR"
        or record.get("preexisting_exact_name_ids") != []
    ):
        raise PermitVerificationError("signed allocation name is not clear before consumption")
    return result


def _validate_successful_provider_output(output: bytes, permit: VerifiedPermit) -> None:
    if len(output) > MAX_PROVIDER_OUTPUT_BYTES:
        raise PermitVerificationError("provider output exceeds the bounded evidence size")
    record = _load_single_json_record(output, label="provider output")
    if record.get("schema") != PROVIDER_OUTPUT_SCHEMA or record.get("status") != "RUNNING":
        raise PermitVerificationError("provider output is not a successful allocation record")
    pod = record.get("pod")
    executor = record.get("executor")
    template = record.get("template")
    access = record.get("access")
    schedule = record.get("schedule")
    reconciliation = record.get("create_reconciliation")
    if not all(
        isinstance(value, Mapping)
        for value in (pod, executor, template, access, schedule, reconciliation)
    ):
        raise PermitVerificationError("provider output evidence sections are incomplete")
    pod_id = pod.get("id")
    if not isinstance(pod_id, str) or not pod_id:
        raise PermitVerificationError("provider output pod ID is missing")
    raw_executor_id = executor.get("id")
    raw_executor_huid = executor.get("huid")
    if (
        not isinstance(raw_executor_id, str)
        or not raw_executor_id
        or not isinstance(raw_executor_huid, str)
        or not raw_executor_huid
        or permit.payload["executor_id"] not in {raw_executor_id, raw_executor_huid}
    ):
        raise PermitVerificationError("provider output executor selector mismatch")
    expected = {
        "pod.name": (pod.get("name"), permit.payload["allocation_name"]),
        "executor.gpu_count": (executor.get("gpu_count"), permit.payload["gpu_count"]),
        "template.id": (template.get("id"), permit.payload["template_id"]),
        "template.image": (template.get("docker_image"), permit.payload["template_image"]),
        "template.tag": (template.get("docker_image_tag"), permit.payload["template_tag"]),
        "template.status": (template.get("status"), permit.payload["template_status"]),
        "access.path": (
            access.get("ssh_public_key_path"),
            permit.payload["ssh_public_key_path"],
        ),
        "access.sha256": (
            access.get("ssh_public_key_sha256"),
            permit.payload["ssh_public_key_sha256"],
        ),
        "schedule.ttl": (schedule.get("ttl_seconds"), permit.payload["ttl_seconds"]),
    }
    if any(actual != wanted for actual, wanted in expected.values()):
        raise PermitVerificationError("provider output does not match signed allocation bindings")
    try:
        observed_rate = Decimal(str(executor.get("observed_rate_usd_per_hour")))
        max_rate = Decimal(str(executor.get("max_rate_usd_per_hour")))
    except InvalidOperation as exc:
        raise PermitVerificationError("provider output rate evidence is invalid") from exc
    if (
        observed_rate != _require_decimal(permit.payload, "observed_node_hourly_rate_usd")
        or max_rate != _require_decimal(permit.payload, "max_node_hourly_rate_usd")
        or executor.get("rate_authority") != "provider_raw_price_per_gpu_x_gpu_count/v1"
    ):
        raise PermitVerificationError("provider output rate evidence mismatch")
    aggregate_rate = executor.get("rate_evidence")
    rent_boundary = executor.get("rent_boundary")
    if not isinstance(aggregate_rate, Mapping) or not isinstance(rent_boundary, Mapping):
        raise PermitVerificationError("provider output rent-boundary evidence is missing")
    if (
        rent_boundary.get("status") != "VERIFIED_PRE_AND_POST"
        or rent_boundary.get("endpoint") != f"/executors/{raw_executor_id}/rent"
    ):
        raise PermitVerificationError("provider output rent-boundary identity mismatch")
    before_post = _validate_raw_rate_snapshot(
        rent_boundary.get("before_post"),
        raw_executor_id=raw_executor_id,
        signed_observed_rate=observed_rate,
        label="before_post",
    )
    after_post = _validate_raw_rate_snapshot(
        rent_boundary.get("after_post"),
        raw_executor_id=raw_executor_id,
        signed_observed_rate=observed_rate,
        label="after_post",
        require_full_availability=False,
    )
    aggregate = _validate_raw_rate_snapshot(
        {"authority": executor.get("rate_authority"), **dict(aggregate_rate)},
        raw_executor_id=raw_executor_id,
        signed_observed_rate=observed_rate,
        label="aggregate",
    )
    before_identity = {
        key: value for key, value in before_post.items() if key != "available_gpu_count"
    }
    after_identity = {
        key: value for key, value in after_post.items() if key != "available_gpu_count"
    }
    if (
        before_post != aggregate
        or before_identity != after_identity
        or after_post["available_gpu_count"] > before_post["available_gpu_count"]
    ):
        raise PermitVerificationError("provider output rent-boundary rate evidence diverges")
    if (
        reconciliation.get("status") != "CONFIRMED_UNIQUE"
        or reconciliation.get("allocation_name") != permit.payload["allocation_name"]
        or reconciliation.get("pod_id") != pod_id
        or reconciliation.get("final_active_pod_ids") != [pod_id]
    ):
        raise PermitVerificationError("provider output creation reconciliation is invalid")


def _validate_raw_rate_snapshot(
    value: Any,
    *,
    raw_executor_id: str,
    signed_observed_rate: Decimal,
    label: str,
    require_full_availability: bool = True,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PermitVerificationError(f"provider output {label} rate evidence is missing")
    gpu_count = value.get("gpu_count")
    available_gpu_count = value.get("available_gpu_count")
    if (
        type(gpu_count) is not int
        or gpu_count != REQUIRED_GPU_COUNT
        or isinstance(available_gpu_count, bool)
        or not isinstance(available_gpu_count, int)
        or not 0 <= available_gpu_count <= REQUIRED_GPU_COUNT
        or (require_full_availability and available_gpu_count != REQUIRED_GPU_COUNT)
    ):
        raise PermitVerificationError(f"provider output {label} GPU rate shape is invalid")
    price_per_gpu = _require_decimal(value, "price_per_gpu")
    price_per_hour = _require_decimal(value, "price_per_hour")
    if (
        value.get("authority") != "provider_raw_price_per_gpu_x_gpu_count/v1"
        or value.get("executor_id") != raw_executor_id
        or value.get("pending_price_change") is not False
        or price_per_gpu <= 0
        or price_per_hour != signed_observed_rate
        or price_per_gpu * Decimal(REQUIRED_GPU_COUNT) != price_per_hour
    ):
        raise PermitVerificationError(f"provider output {label} raw rate is invalid")
    return {
        "authority": value["authority"],
        "executor_id": value["executor_id"],
        "gpu_count": gpu_count,
        "available_gpu_count": available_gpu_count,
        "price_per_gpu": price_per_gpu,
        "price_per_hour": price_per_hour,
        "pending_price_change": False,
    }


def _load_single_json_record(output: bytes, *, label: str) -> dict[str, Any]:
    try:
        text = output.decode("utf-8")
        lines = text.splitlines()
        if len(lines) != 1 or not lines[0]:
            raise ValueError("expected one JSON line")
        value = json.loads(
            lines[0],
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_non_finite,
        )
    except (UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise PermitVerificationError(f"{label} is not exactly one JSON record") from exc
    if not isinstance(value, dict):
        raise PermitVerificationError(f"{label} root must be an object")
    return value


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


def _terminal_reconciliation_receipt_path(claim_path: Path) -> Path:
    suffix = ".consumed.json"
    if not claim_path.name.endswith(suffix):
        raise PermitVerificationError("permit claim path has an unexpected name")
    return claim_path.with_name(
        claim_path.name.removesuffix(suffix) + ".terminal-reconciliation.json"
    )


def _terminal_reconciliation_retry_path(claim_path: Path, attempt: int) -> Path:
    if attempt < 1:
        raise PermitVerificationError("terminal reconciliation retry attempt is invalid")
    terminal_path = _terminal_reconciliation_receipt_path(claim_path)
    return terminal_path.with_name(
        f"{terminal_path.name.removesuffix('.json')}.retry-{attempt:04d}.json"
    )


def _terminal_reconciliation_lease_path(claim_path: Path) -> Path:
    terminal_path = _terminal_reconciliation_receipt_path(claim_path)
    return terminal_path.with_name(f"{terminal_path.name.removesuffix('.json')}.lease.json")


def _terminal_reconciliation_lease_record(
    permit: VerifiedPermit, claim_path: Path
) -> dict[str, Any]:
    return {
        "schema": TERMINAL_RECONCILIATION_LEASE_SCHEMA,
        "permit_sha256": permit.permit_sha256,
        "claim_path": str(claim_path.resolve()),
    }


def _acquire_terminal_reconciliation_lease(
    permit: VerifiedPermit,
    claim_path: Path,
) -> tuple[int, Path]:
    """Take the crash-released ownership lock shared by launch and cleanup."""

    ledger, ledger_descriptor = _open_private_ledger(GATE0_CONSUMPTION_ROOT)
    expected_claim_path = _permit_claim_path(permit, ledger)
    if expected_claim_path != claim_path:
        os.close(ledger_descriptor)
        raise PermitVerificationError("terminal reconciliation lease claim mismatch")
    path = _terminal_reconciliation_lease_path(claim_path)
    flags = os.O_RDWR | os.O_CREAT
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    acquired = False
    try:
        descriptor = os.open(path.name, flags, 0o600, dir_fd=ledger_descriptor)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise PermitVerificationError(
                "terminal reconciliation lease must be an owner-only regular file"
            )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except BlockingIOError as exc:
            raise PermitReplayError("terminal reconciliation is owned by a live wrapper") from exc
        expected = (
            canonical_json_bytes(_terminal_reconciliation_lease_record(permit, claim_path)) + b"\n"
        )
        os.lseek(descriptor, 0, os.SEEK_SET)
        existing = os.read(descriptor, 16 * 1024 + 1)
        if len(existing) > 16 * 1024:
            raise PermitVerificationError("terminal reconciliation lease is oversized")
        if existing:
            if existing != expected:
                raise PermitVerificationError("terminal reconciliation lease binding mismatch")
        else:
            os.lseek(descriptor, 0, os.SEEK_SET)
            if os.write(descriptor, expected) != len(expected):
                raise PermitVerificationError(
                    "terminal reconciliation lease could not be fully written"
                )
            os.ftruncate(descriptor, len(expected))
            os.fsync(descriptor)
            os.fsync(ledger_descriptor)
        return descriptor, path
    except Exception as exc:
        if descriptor is not None:
            if acquired:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
        if isinstance(exc, PermitError):
            raise
        raise PermitVerificationError(
            "terminal reconciliation lease could not be acquired"
        ) from exc
    finally:
        os.close(ledger_descriptor)


def _release_terminal_reconciliation_lease(descriptor: int | None) -> None:
    if descriptor is None:
        return
    try:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
    finally:
        os.close(descriptor)


def _cleanup_retry_verification_time(permit_path: Path) -> datetime:
    """Verify stale cleanup authority without reviving stale launch authority."""

    envelope = _load_json_object(permit_path, max_bytes=64 * 1024)
    payload = envelope.get("payload")
    if not isinstance(payload, Mapping):
        raise PermitFormatError("permit payload must be an object")
    issued_at = _parse_utc(payload.get("issued_at"), "issued_at")
    expires_at = _parse_utc(payload.get("expires_at"), "expires_at")
    if expires_at <= issued_at:
        raise PermitVerificationError("permit validity interval is invalid")
    return issued_at


def _validate_initial_pre_snapshot_evidence(
    pre_snapshot: Mapping[str, Any],
    *,
    permit: VerifiedPermit,
) -> Mapping[str, Any]:
    expected_evidence_fields = {
        "exit_code",
        "timed_out",
        "output_sha256",
        "output_size_bytes",
        "record",
    }
    if set(pre_snapshot) != expected_evidence_fields:
        raise PermitVerificationError("initial terminal pre-snapshot evidence is invalid")
    output_sha256 = pre_snapshot.get("output_sha256")
    output_size = pre_snapshot.get("output_size_bytes")
    record = pre_snapshot.get("record")
    if (
        pre_snapshot.get("exit_code") != 0
        or type(pre_snapshot.get("exit_code")) is not int
        or pre_snapshot.get("timed_out") is not False
        or not isinstance(output_sha256, str)
        or _HEX_256_RE.fullmatch(output_sha256) is None
        or type(output_size) is not int
        or not 0 < output_size <= MAX_RECONCILIATION_OUTPUT_BYTES
        or not isinstance(record, Mapping)
    ):
        raise PermitVerificationError("initial terminal pre-snapshot evidence is invalid")
    expected_record_fields = {
        "schema",
        "status",
        "mode",
        "allocation_name",
        "preexisting_exact_name_ids",
    }
    preexisting_ids = record.get("preexisting_exact_name_ids")
    if (
        set(record) != expected_record_fields
        or record.get("schema") != PROVIDER_RECONCILIATION_SCHEMA
        or record.get("status") != "SNAPSHOT_CLEAR"
        or record.get("mode") != "snapshot"
        or record.get("allocation_name") != permit.payload["allocation_name"]
        or preexisting_ids != []
    ):
        raise PermitVerificationError("initial terminal pre-snapshot evidence is invalid")
    return record


def _reserve_terminal_reconciliation_receipt(
    permit: VerifiedPermit,
    *,
    ledger_dir: str | Path,
    pre_snapshot: Mapping[str, Any],
) -> tuple[Path, Path]:
    record = _validate_initial_pre_snapshot_evidence(pre_snapshot, permit=permit)
    frozen_pre_snapshot = json.loads(canonical_json_bytes(pre_snapshot))
    ledger, ledger_descriptor = _open_private_ledger(ledger_dir)
    claim_path = _permit_claim_path(permit, ledger)
    path = _terminal_reconciliation_receipt_path(claim_path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    placeholder = {
        "schema": TERMINAL_RECONCILIATION_RECEIPT_SCHEMA,
        "status": "RESERVED",
        "permit": {
            "sha256": permit.permit_sha256,
            "key_id": permit.key_id,
            "request_id": permit.request_id,
            "nonce": permit.nonce,
        },
        "claim": {"path": str(claim_path.resolve())},
        "allocation": {
            "name": permit.payload["allocation_name"],
            "preexisting_exact_name_ids": list(record["preexisting_exact_name_ids"]),
        },
        "pre_snapshot": {
            "sha256": hashlib.sha256(canonical_json_bytes(frozen_pre_snapshot)).hexdigest(),
            "evidence": frozen_pre_snapshot,
        },
    }
    try:
        descriptor = os.open(path.name, flags, 0o600, dir_fd=ledger_descriptor)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(canonical_json_bytes(placeholder) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.fsync(ledger_descriptor)
    except FileExistsError as exc:
        raise PermitReplayError("terminal reconciliation receipt already exists") from exc
    except OSError as exc:
        raise PermitVerificationError(
            "terminal reconciliation receipt could not be reserved"
        ) from exc
    finally:
        os.close(ledger_descriptor)
    return claim_path, path


def _write_unconsumed_terminal_receipt(
    permit: VerifiedPermit,
    *,
    claim_path: Path,
    terminal_receipt_path: Path,
    pre_snapshot: Mapping[str, Any],
    failure_kind: str,
) -> None:
    receipt = {
        "schema": TERMINAL_RECONCILIATION_RECEIPT_SCHEMA,
        "status": "CONSUMPTION_FAILED_NO_PROVIDER_MUTATION",
        "written_at_utc": _utc_timestamp(),
        "permit": {
            "sha256": permit.permit_sha256,
            "key_id": permit.key_id,
            "request_id": permit.request_id,
            "nonce": permit.nonce,
        },
        "claim": {
            "expected_path": str(claim_path.resolve()),
            "artifact": _artifact_binding(claim_path),
        },
        "pre_snapshot": {
            "sha256": hashlib.sha256(canonical_json_bytes(pre_snapshot)).hexdigest(),
            "evidence": dict(pre_snapshot),
        },
        "terminal_failure": {"kind": failure_kind, "wrapper_exit_code": 2},
        "reconciliation": {"status": "NOT_REQUIRED_NO_PROVIDER_MUTATION"},
    }
    try:
        _replace_reserved_terminal_reconciliation_receipt(terminal_receipt_path, receipt)
    except PermitError:
        pass


def _artifact_binding(path: Path) -> dict[str, Any]:
    binding: dict[str, Any] = {"path": str(path.resolve())}
    try:
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
            raise OSError("not a regular file")
        binding.update(
            {
                "status": "PRESENT",
                "sha256": _sha256_bound_file(path, label="terminal evidence artifact"),
                "size_bytes": metadata.st_size,
            }
        )
    except (OSError, PermitError):
        binding.update({"status": "UNAVAILABLE", "sha256": None, "size_bytes": None})
    return binding


def _retry_control_record(claim_path: Path, attempt: int) -> dict[str, Any]:
    return {
        "cli_flag": "--retry-terminal-reconciliation",
        "credential_transport": CREDENTIAL_TRANSPORT,
        "next_attempt": attempt,
        "next_receipt_path": str(
            _terminal_reconciliation_retry_path(claim_path, attempt).resolve()
        ),
        "mutation_scope": "terminate-attributable-exact-name-allocations-only",
    }


def _build_terminal_reconciliation_receipt(
    permit: VerifiedPermit,
    *,
    claim_path: Path,
    pre_snapshot: Mapping[str, Any],
    status: str,
    failure_kind: str,
    wrapper_exit_code: int,
    reconciliation: Mapping[str, Any],
    provider_output: bytes,
    provider_output_path: Path,
    launch_receipt_path: Path,
) -> dict[str, Any]:
    return {
        "schema": TERMINAL_RECONCILIATION_RECEIPT_SCHEMA,
        "status": status,
        "written_at_utc": _utc_timestamp(),
        "permit": {
            "sha256": permit.permit_sha256,
            "key_id": permit.key_id,
            "request_id": permit.request_id,
            "nonce": permit.nonce,
        },
        "claim": {
            "path": str(claim_path.resolve()),
            "sha256": _sha256_bound_file(claim_path, label="permit claim"),
        },
        "allocation": {
            "name": permit.payload["allocation_name"],
            "preexisting_exact_name_ids": pre_snapshot["record"]["preexisting_exact_name_ids"],
        },
        "pre_snapshot": {
            "sha256": hashlib.sha256(canonical_json_bytes(pre_snapshot)).hexdigest(),
            "evidence": dict(pre_snapshot),
        },
        "terminal_failure": {
            "kind": failure_kind or None,
            "wrapper_exit_code": wrapper_exit_code,
        },
        "reconciliation": dict(reconciliation),
        "retry_control": (
            _retry_control_record(claim_path, 1) if status == "CLEANUP_UNCONFIRMED" else None
        ),
        "artifacts": {
            "captured_provider_output": {
                "sha256": hashlib.sha256(provider_output).hexdigest(),
                "size_bytes": len(provider_output),
            },
            "provider_output": _artifact_binding(provider_output_path),
            "launch_receipt": _artifact_binding(launch_receipt_path),
        },
    }


def _recover_initial_terminal_reservation(
    reservation: Mapping[str, Any],
    *,
    permit: VerifiedPermit,
    claim_path: Path,
    terminal_path: Path,
) -> dict[str, Any]:
    expected_fields = {"schema", "status", "permit", "claim", "allocation", "pre_snapshot"}
    permit_binding = reservation.get("permit")
    claim_binding = reservation.get("claim")
    allocation = reservation.get("allocation")
    pre_snapshot_binding = reservation.get("pre_snapshot")
    if (
        set(reservation) != expected_fields
        or reservation.get("schema") != TERMINAL_RECONCILIATION_RECEIPT_SCHEMA
        or reservation.get("status") != "RESERVED"
        or not isinstance(permit_binding, Mapping)
        or set(permit_binding) != {"sha256", "key_id", "request_id", "nonce"}
        or permit_binding.get("sha256") != permit.permit_sha256
        or permit_binding.get("key_id") != permit.key_id
        or permit_binding.get("request_id") != permit.request_id
        or permit_binding.get("nonce") != permit.nonce
        or not isinstance(claim_binding, Mapping)
        or set(claim_binding) != {"path"}
        or claim_binding.get("path") != str(claim_path.resolve())
        or not isinstance(allocation, Mapping)
        or set(allocation) != {"name", "preexisting_exact_name_ids"}
        or allocation.get("name") != permit.payload["allocation_name"]
        or allocation.get("preexisting_exact_name_ids") != []
        or not isinstance(pre_snapshot_binding, Mapping)
        or set(pre_snapshot_binding) != {"sha256", "evidence"}
        or not isinstance(pre_snapshot_binding.get("evidence"), Mapping)
    ):
        raise PermitVerificationError("initial terminal reservation binding mismatch")
    pre_snapshot = pre_snapshot_binding["evidence"]
    try:
        expected_pre_snapshot_sha256 = hashlib.sha256(
            canonical_json_bytes(pre_snapshot)
        ).hexdigest()
        record = _validate_initial_pre_snapshot_evidence(pre_snapshot, permit=permit)
    except (PermitError, TypeError, ValueError) as exc:
        raise PermitVerificationError("initial terminal reservation binding mismatch") from exc
    if pre_snapshot_binding.get("sha256") != expected_pre_snapshot_sha256 or record.get(
        "preexisting_exact_name_ids"
    ) != allocation.get("preexisting_exact_name_ids"):
        raise PermitVerificationError("initial terminal reservation binding mismatch")
    return {
        "status": "CLEANUP_UNCONFIRMED",
        "allocation": dict(allocation),
        "initial_terminal_reservation": {
            "path": str(terminal_path.resolve()),
            "sha256": _sha256_bound_file(terminal_path, label="initial terminal reservation"),
            "pre_snapshot_sha256": expected_pre_snapshot_sha256,
            "pre_snapshot": pre_snapshot,
        },
    }


def _load_terminal_retry_parent(
    permit: VerifiedPermit, claim_path: Path
) -> tuple[Path, dict[str, Any], int]:
    terminal_path = _terminal_reconciliation_receipt_path(claim_path)
    parent_path = terminal_path
    try:
        terminal_metadata = parent_path.lstat()
    except OSError as exc:
        raise PermitVerificationError("terminal reconciliation parent is unavailable") from exc
    if stat.S_ISLNK(terminal_metadata.st_mode) or not stat.S_ISREG(terminal_metadata.st_mode):
        raise PermitVerificationError("terminal reconciliation parent must be a regular file")
    parent_document = _load_json_object(parent_path, max_bytes=512 * 1024)
    if parent_document.get("status") == "RESERVED":
        parent = _recover_initial_terminal_reservation(
            parent_document,
            permit=permit,
            claim_path=claim_path,
            terminal_path=parent_path,
        )
    else:
        parent = parent_document
        if (
            parent.get("schema") != TERMINAL_RECONCILIATION_RECEIPT_SCHEMA
            or parent.get("permit", {}).get("sha256") != permit.permit_sha256
            or parent.get("claim", {}).get("path") != str(claim_path.resolve())
            or parent.get("claim", {}).get("sha256")
            != _sha256_bound_file(claim_path, label="permit claim")
        ):
            raise PermitVerificationError("terminal reconciliation parent binding mismatch")
    attempt = 1
    while True:
        candidate = _terminal_reconciliation_retry_path(claim_path, attempt)
        if not candidate.exists():
            break
        retry = _load_json_object(candidate, max_bytes=512 * 1024)
        if retry.get("status") == "RESERVED":
            _validate_terminal_retry_reservation(
                retry,
                permit=permit,
                parent_path=parent_path,
                attempt=attempt,
            )
            break
        if (
            retry.get("schema") != TERMINAL_RECONCILIATION_RETRY_SCHEMA
            or retry.get("attempt") != attempt
            or retry.get("permit", {}).get("sha256") != permit.permit_sha256
            or retry.get("parent_receipt", {}).get("path") != str(parent_path.resolve())
            or retry.get("parent_receipt", {}).get("sha256")
            != _sha256_bound_file(parent_path, label="terminal retry parent")
        ):
            raise PermitVerificationError("terminal reconciliation retry chain mismatch")
        parent_path = candidate
        parent = retry
        attempt += 1
    if parent.get("status") != "CLEANUP_UNCONFIRMED":
        raise PermitVerificationError("terminal reconciliation does not require retry")
    return parent_path, parent, attempt


def _validate_terminal_retry_reservation(
    reservation: Mapping[str, Any],
    *,
    permit: VerifiedPermit,
    parent_path: Path,
    attempt: int,
) -> None:
    expected_fields = {
        "schema",
        "status",
        "attempt",
        "permit_sha256",
        "parent_receipt_sha256",
    }
    if (
        set(reservation) != expected_fields
        or reservation.get("schema") != TERMINAL_RECONCILIATION_RETRY_SCHEMA
        or reservation.get("status") != "RESERVED"
        or reservation.get("attempt") != attempt
        or reservation.get("permit_sha256") != permit.permit_sha256
        or reservation.get("parent_receipt_sha256")
        != _sha256_bound_file(parent_path, label="terminal retry parent")
    ):
        raise PermitVerificationError("terminal reconciliation retry reservation mismatch")


def _reserve_terminal_retry_receipt(
    permit: VerifiedPermit,
    *,
    claim_path: Path,
    parent_path: Path,
    attempt: int,
) -> Path:
    ledger, ledger_descriptor = _open_private_ledger(GATE0_CONSUMPTION_ROOT)
    expected_claim_path = _permit_claim_path(permit, ledger)
    if expected_claim_path != claim_path:
        os.close(ledger_descriptor)
        raise PermitVerificationError("terminal reconciliation claim path mismatch")
    path = _terminal_reconciliation_retry_path(claim_path, attempt)
    placeholder = {
        "schema": TERMINAL_RECONCILIATION_RETRY_SCHEMA,
        "status": "RESERVED",
        "attempt": attempt,
        "permit_sha256": permit.permit_sha256,
        "parent_receipt_sha256": _sha256_bound_file(parent_path, label="terminal retry parent"),
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path.name, flags, 0o600, dir_fd=ledger_descriptor)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(canonical_json_bytes(placeholder) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.fsync(ledger_descriptor)
    except FileExistsError:
        reservation = _load_json_object(path, max_bytes=16 * 1024)
        _validate_terminal_retry_reservation(
            reservation,
            permit=permit,
            parent_path=parent_path,
            attempt=attempt,
        )
    except OSError as exc:
        raise PermitVerificationError("terminal retry receipt could not be reserved") from exc
    finally:
        os.close(ledger_descriptor)
    return path


def _validate_consumed_claim_for_retry(permit: VerifiedPermit, claim_path: Path) -> None:
    try:
        metadata = claim_path.lstat()
    except OSError as exc:
        raise PermitVerificationError("terminal reconciliation claim is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise PermitVerificationError("terminal reconciliation claim must be a regular file")
    claim = _load_json_object(claim_path, max_bytes=16 * 1024)
    expected = {
        "key_id": permit.key_id,
        "nonce": permit.nonce,
        "permit_sha256": permit.permit_sha256,
        "request_id": permit.request_id,
    }
    if set(claim) != {*expected, "consumed_at"} or any(
        claim.get(field) != value for field, value in expected.items()
    ):
        raise PermitVerificationError("terminal reconciliation claim binding mismatch")
    consumed_at = _parse_utc(claim.get("consumed_at"), "claim consumed_at")
    if not permit.issued_at <= consumed_at < permit.expires_at:
        raise PermitVerificationError("terminal reconciliation claim time is outside permit")


def _retry_terminal_reconciliation(
    permit: VerifiedPermit,
    *,
    executable_descriptor: int,
    interpreter_descriptor: int,
    provider_environment: Mapping[str, str],
    credential: bytearray,
) -> int:
    ledger = Path(GATE0_CONSUMPTION_ROOT)
    claim_path = _permit_claim_path(permit, ledger)
    if not claim_path.is_file():
        raise PermitVerificationError("terminal reconciliation claim is unavailable")
    _validate_consumed_claim_for_retry(permit, claim_path)
    lease_descriptor, lease_path = _acquire_terminal_reconciliation_lease(permit, claim_path)
    try:
        _validate_consumed_claim_for_retry(permit, claim_path)
        parent_path, parent, attempt = _load_terminal_retry_parent(permit, claim_path)
        allocation = parent.get("allocation")
        if not isinstance(allocation, Mapping):
            raise PermitVerificationError("terminal reconciliation allocation binding is missing")
        preexisting_ids = allocation.get("preexisting_exact_name_ids")
        if not isinstance(preexisting_ids, list) or any(
            not isinstance(pod_id, str) for pod_id in preexisting_ids
        ):
            raise PermitVerificationError("terminal reconciliation pre-snapshot is invalid")
        retry_path = _reserve_terminal_retry_receipt(
            permit,
            claim_path=claim_path,
            parent_path=parent_path,
            attempt=attempt,
        )
        try:
            reconciliation = _run_provider_control(
                permit,
                mode="cleanup",
                executable_descriptor=executable_descriptor,
                interpreter_descriptor=interpreter_descriptor,
                provider_environment=provider_environment,
                credential=credential,
                preexisting_ids=preexisting_ids,
                terminal_lease_descriptor=lease_descriptor,
            )
            record = reconciliation["record"]
            confirmed = (
                not reconciliation["timed_out"]
                and reconciliation["exit_code"] == 0
                and record.get("status") == "CONFIRMED_ABSENT"
                and record.get("final_attributable_ids") == []
            )
        except PermitError as exc:
            reconciliation = {"status": "CONTROL_FAILED", "error": type(exc).__name__}
            confirmed = False
        receipt = {
            "schema": TERMINAL_RECONCILIATION_RETRY_SCHEMA,
            "status": "RETRY_RECONCILED" if confirmed else "CLEANUP_UNCONFIRMED",
            "cleanup_status": "CONFIRMED_ABSENT" if confirmed else "UNCONFIRMED",
            "attempt": attempt,
            "written_at_utc": _utc_timestamp(),
            "permit": {
                "sha256": permit.permit_sha256,
                "key_id": permit.key_id,
                "request_id": permit.request_id,
                "nonce": permit.nonce,
            },
            "claim": {
                "path": str(claim_path.resolve()),
                "sha256": _sha256_bound_file(claim_path, label="permit claim"),
            },
            "parent_receipt": {
                "path": str(parent_path.resolve()),
                "sha256": _sha256_bound_file(parent_path, label="terminal retry parent"),
            },
            "allocation": dict(allocation),
            "ownership_lease": {
                "path": str(lease_path.resolve()),
                "sha256": _sha256_bound_file(lease_path, label="terminal reconciliation lease"),
                "mode": "exclusive-kernel-flock",
            },
            "initial_terminal_reservation": parent.get("initial_terminal_reservation"),
            "reconciliation": reconciliation,
            "retry_control": (
                None if confirmed else _retry_control_record(claim_path, attempt + 1)
            ),
        }
        _replace_reserved_terminal_reconciliation_receipt(retry_path, receipt)
        if not confirmed:
            _print_failure(
                "TerminalReconciliationUnconfirmed",
                "attributable allocation cleanup remains unconfirmed",
            )
            return 125
        return 0
    finally:
        _release_terminal_reconciliation_lease(lease_descriptor)


def _replace_reserved_terminal_reconciliation_receipt(
    path: Path, receipt: Mapping[str, Any]
) -> None:
    try:
        reserved = _load_json_object(path, max_bytes=16 * 1024)
        metadata = path.lstat()
    except (OSError, PermitError) as exc:
        raise PermitVerificationError(
            "reserved terminal reconciliation receipt is unavailable"
        ) from exc
    if (
        stat.S_ISLNK(metadata.st_mode)
        or not stat.S_ISREG(metadata.st_mode)
        or reserved.get("schema")
        not in {
            TERMINAL_RECONCILIATION_RECEIPT_SCHEMA,
            TERMINAL_RECONCILIATION_RETRY_SCHEMA,
        }
        or reserved.get("status") != "RESERVED"
        or receipt.get("schema") != reserved.get("schema")
    ):
        raise PermitVerificationError("terminal reconciliation receipt reservation changed")
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
        raise PermitVerificationError("cannot write terminal reconciliation receipt") from exc


def _finish_terminal_reconciliation(
    permit: VerifiedPermit,
    *,
    claim_path: Path,
    terminal_receipt_path: Path,
    pre_snapshot: Mapping[str, Any],
    executable_descriptor: int,
    interpreter_descriptor: int,
    terminal_lease_descriptor: int,
    provider_environment: Mapping[str, str],
    credential: bytearray,
    provider_output: bytes,
    provider_output_path: Path,
    launch_receipt_path: Path,
    failure_kind: str,
    wrapper_exit_code: int,
) -> bool:
    preexisting_ids = pre_snapshot["record"]["preexisting_exact_name_ids"]
    try:
        reconciliation = _run_provider_control(
            permit,
            mode="cleanup",
            executable_descriptor=executable_descriptor,
            interpreter_descriptor=interpreter_descriptor,
            provider_environment=provider_environment,
            credential=credential,
            preexisting_ids=preexisting_ids,
            terminal_lease_descriptor=terminal_lease_descriptor,
        )
        record = reconciliation["record"]
        confirmed = (
            not reconciliation["timed_out"]
            and reconciliation["exit_code"] == 0
            and record.get("status") == "CONFIRMED_ABSENT"
            and record.get("final_attributable_ids") == []
        )
    except PermitError as exc:
        reconciliation = {
            "status": "CONTROL_FAILED",
            "error": type(exc).__name__,
        }
        confirmed = False
    receipt = _build_terminal_reconciliation_receipt(
        permit,
        claim_path=claim_path,
        pre_snapshot=pre_snapshot,
        status="FAILURE_RECONCILED" if confirmed else "CLEANUP_UNCONFIRMED",
        failure_kind=failure_kind,
        wrapper_exit_code=wrapper_exit_code,
        reconciliation=reconciliation,
        provider_output=provider_output,
        provider_output_path=provider_output_path,
        launch_receipt_path=launch_receipt_path,
    )
    try:
        _replace_reserved_terminal_reconciliation_receipt(terminal_receipt_path, receipt)
    except PermitError:
        return False
    return confirmed


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
    provider_output_valid: bool,
    terminal_failure_kind: str,
) -> dict[str, Any]:
    claim = _load_json_object(claim_path, max_bytes=16 * 1024)
    if timed_out:
        status = "PROVIDER_TIMEOUT"
    elif execution_error:
        status = "PROVIDER_EXECUTION_ERROR"
    elif exit_code == 0 and provider_output_valid:
        status = "COMPLETED"
    elif exit_code == 0:
        status = "PROVIDER_OUTPUT_INVALID"
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
            "provider_output_valid": provider_output_valid,
            "terminal_failure_kind": terminal_failure_kind or None,
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
    "TERMINAL_RECONCILIATION_RECEIPT_SCHEMA",
    "TERMINAL_RECONCILIATION_RETRY_SCHEMA",
    "TERMINAL_RECONCILIATION_LEASE_SCHEMA",
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
