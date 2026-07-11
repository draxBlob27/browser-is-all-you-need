#!/opt/homebrew/Cellar/python@3.11/3.11.14_3/Frameworks/Python.framework/Versions/3.11/bin/python3.11
"""Create one bounded 8xH100 Lium pod without entering SSH."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import re
import stat
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping, NoReturn, Sequence


VERSION = "1.3.0"
OUTPUT_SCHEMA = "lium-h100-pod-create/v2"
RECONCILIATION_SCHEMA = "lium-h100-allocation-reconciliation/v1"
MAX_TTL_SECONDS = 2 * 60 * 60
MAX_RATE_USD_PER_HOUR = Decimal("18")
MAX_POLL_TIMEOUT_SECONDS = 240
MAX_POLL_INTERVAL_SECONDS = 30
SDK_HTTP_TIMEOUT_SECONDS = 30
RECOVERY_LOOKUP_ATTEMPTS = 2
MAX_RECOVERY_LOOKUP_SECONDS = SDK_HTTP_TIMEOUT_SECONDS * RECOVERY_LOOKUP_ATTEMPTS
SUCCESS_RECONCILIATION_ATTEMPTS = 3
MIN_SUCCESSFUL_RECONCILIATION_SNAPSHOTS = 2
TERMINAL_RECONCILIATION_ATTEMPTS = 3
MAX_TERMINAL_RECONCILIATION_PODS = 16
RENT_MUTATION_ATTEMPT_POLICY = "single-attempt-sdk-request-boundary/v1"
RATE_AUTHORITY = "provider_raw_price_per_gpu_x_gpu_count/v1"
MAX_CREDENTIAL_BYTES = 4096
_HUID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,127}\Z")
_NAME_RE = re.compile(r"issue-[1-9][0-9]*-[a-z0-9][a-z0-9-]{2,62}\Z")
_TEMPLATE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,127}\Z")
_TTL_RE = re.compile(r"([1-9][0-9]*)([hm])\Z")
_READY_EXECUTOR_STATES = frozenset({"AVAILABLE", "ONLINE", "READY"})
_USABLE_TEMPLATE_STATES = frozenset(
    {"ACTIVE", "AVAILABLE", "READY", "SUCCESS", "VERIFIED", "VERIFY_SUCCESS"}
)


class ProviderFailure(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = dict(details or {})


class MachineArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ProviderFailure("invalid_arguments", message)


@dataclass(frozen=True)
class PodHandle:
    id: str


@dataclass(frozen=True)
class ExecutorSnapshot:
    id: str
    huid: str
    gpu_type: str
    gpu_model: str
    gpu_count: int
    status: str
    observed_rate: Decimal
    observed_gpu_rate: Decimal


@dataclass(frozen=True)
class RawRateEvidence:
    executor_id: str
    gpu_count: int
    available_gpu_count: int
    price_per_gpu: Decimal
    price_per_hour: Decimal
    authority: str = RATE_AUTHORITY


@dataclass(frozen=True)
class RentBoundaryEvidence:
    endpoint: str
    before_post: RawRateEvidence
    after_post: RawRateEvidence


class RentBoundaryFailure(ProviderFailure):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        mutation_started: bool,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, details=details)
        self.mutation_started = mutation_started


def build_parser() -> MachineArgumentParser:
    parser = MachineArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", parser_class=MachineArgumentParser)
    up = subparsers.add_parser("up", help="create one bounded H100 allocation")
    up.add_argument("executor_huid")
    up.add_argument("--ttl", required=True)
    up.add_argument("--name", required=True)
    up.add_argument("--yes", action="store_true")
    up.add_argument("--template-id", required=True)
    up.add_argument("--template-image", required=True)
    up.add_argument("--template-tag", required=True)
    up.add_argument("--template-status", required=True)
    up.add_argument("--expected-provider-version", required=True)
    up.add_argument("--expected-interpreter-path", required=True)
    up.add_argument("--expected-interpreter-sha256", required=True)
    up.add_argument("--expected-interpreter-version", required=True)
    up.add_argument("--expected-lium-sdk-version", required=True)
    up.add_argument("--expected-lium-cli-path", required=True)
    up.add_argument("--expected-lium-cli-sha256", required=True)
    up.add_argument("--expected-lium-cli-version", required=True)
    up.add_argument("--ssh-public-key-path", required=True)
    up.add_argument("--ssh-public-key-sha256", required=True)
    up.add_argument("--max-rate", default="18")
    up.add_argument("--expected-observed-rate", required=True)
    up.add_argument("--expected-rate-authority", required=True)
    up.add_argument("--ports", type=int)
    up.add_argument("--poll-timeout", type=int, default=240)
    up.add_argument("--poll-interval", type=int, default=5)
    reconcile = subparsers.add_parser(
        "reconcile",
        help=argparse.SUPPRESS,
        description="Internal allocation reconciliation control surface",
    )
    reconcile.add_argument("--mode", choices=("snapshot", "cleanup"), required=True)
    reconcile.add_argument("--name", required=True)
    reconcile.add_argument("--preexisting-id", action="append", default=[])
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    client_factory: Callable[[bytearray], Any] | None = None,
    now_fn: Callable[[], datetime] | None = None,
    credential_reader: Callable[[], bytearray] | None = None,
    runtime_probe: Callable[[argparse.Namespace], Mapping[str, Any]] | None = None,
    ssh_public_key_reader: Callable[[Path, str], str] | None = None,
) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["--version"]:
        print(VERSION, flush=True)
        return 0
    try:
        args = build_parser().parse_args(arguments)
        if args.command == "up":
            _validate_arguments(args)
            ssh_public_key = (ssh_public_key_reader or _load_ssh_public_key)(
                Path(args.ssh_public_key_path), args.ssh_public_key_sha256
            )
        elif args.command == "reconcile":
            _validate_reconciliation_arguments(args)
        else:
            raise ProviderFailure("invalid_arguments", "a supported command is required")
        os.environ.pop("LIUM_API_KEY", None)
        factory = client_factory or _new_lium_client
        credential = (credential_reader or _read_stdin_credential)()
        try:
            client = factory(credential)
        finally:
            _wipe_bytearray(credential)
        if args.command == "reconcile":
            record = reconcile_exact_name_allocations(client, args)
        else:
            runtime = dict((runtime_probe or _collect_runtime_evidence)(args))
            record = create_h100_pod(
                client,
                args,
                ssh_public_key=ssh_public_key,
                now_fn=now_fn,
                runtime_evidence=runtime,
            )
    except ProviderFailure as exc:
        is_reconciliation = "args" in locals() and args.command == "reconcile"
        failure = {
            "schema": RECONCILIATION_SCHEMA if is_reconciliation else OUTPUT_SCHEMA,
            "status": "ERROR",
            "error": exc.code,
            "message": exc.message,
            "details": exc.details,
        }
        if is_reconciliation:
            failure.update({"mode": args.mode, "allocation_name": args.name})
        _emit(failure)
        return 2
    except Exception:
        is_reconciliation = "args" in locals() and args.command == "reconcile"
        failure = {
            "schema": RECONCILIATION_SCHEMA if is_reconciliation else OUTPUT_SCHEMA,
            "status": "ERROR",
            "error": "sdk_failure",
            "message": "Lium SDK operation failed",
            "details": {},
        }
        if is_reconciliation:
            failure.update({"mode": args.mode, "allocation_name": args.name})
        _emit(failure)
        return 3
    _emit(record)
    return 0


def _read_stdin_credential() -> bytearray:
    line = sys.stdin.buffer.readline(MAX_CREDENTIAL_BYTES + 2)
    tail = sys.stdin.buffer.read(1)
    if tail or len(line) > MAX_CREDENTIAL_BYTES + 1:
        raise ProviderFailure("credential_invalid", "stdin credential exceeds one bounded line")
    if line.endswith(b"\n"):
        line = line[:-1]
    if not line or b"\n" in line or b"\r" in line or b"\x00" in line:
        raise ProviderFailure("credential_invalid", "stdin credential is invalid")
    return bytearray(line)


def _wipe_bytearray(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_ssh_public_key(path: Path, expected_sha256: str) -> str:
    if not path.is_absolute():
        raise ProviderFailure("ssh_public_key_invalid", "SSH public key path is not absolute")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        before = path.lstat()
        descriptor = os.open(path, flags)
        after = os.fstat(descriptor)
    except OSError as exc:
        raise ProviderFailure("ssh_public_key_invalid", "SSH public key is unavailable") from exc
    if (
        not stat.S_ISREG(before.st_mode)
        or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
        or after.st_size > 16 * 1024
    ):
        os.close(descriptor)
        raise ProviderFailure(
            "ssh_public_key_invalid",
            "SSH public key must be a bounded regular non-symlink file",
        )
    data = bytearray()
    try:
        while len(data) <= 16 * 1024:
            chunk = os.read(descriptor, min(4096, 16 * 1024 + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
    except OSError as exc:
        raise ProviderFailure("ssh_public_key_invalid", "SSH public key is unreadable") from exc
    finally:
        os.close(descriptor)
    if len(data) > 16 * 1024:
        raise ProviderFailure("ssh_public_key_invalid", "SSH public key grew while reading")
    public_key_bytes = bytes(data)
    if hashlib.sha256(public_key_bytes).hexdigest() != expected_sha256:
        raise ProviderFailure("ssh_public_key_invalid", "SSH public key digest mismatch")
    try:
        lines = [
            line.strip() for line in public_key_bytes.decode("utf-8").splitlines() if line.strip()
        ]
    except UnicodeError as exc:
        raise ProviderFailure("ssh_public_key_invalid", "SSH public key is unreadable") from exc
    if len(lines) != 1 or not lines[0].startswith(("ssh-", "ecdsa-")):
        raise ProviderFailure("ssh_public_key_invalid", "SSH public key format is invalid")
    if any(ord(character) < 32 for character in lines[0]):
        raise ProviderFailure("ssh_public_key_invalid", "SSH public key contains controls")
    return lines[0]


def _collect_runtime_evidence(args: argparse.Namespace) -> dict[str, Any]:
    interpreter = Path(sys.executable).resolve()
    cli_path = Path(args.expected_lium_cli_path)
    try:
        sdk_version = importlib.metadata.version("lium.io")
        interpreter_sha256 = _sha256_file(interpreter)
        cli_sha256 = _sha256_file(cli_path)
    except (OSError, importlib.metadata.PackageNotFoundError) as exc:
        raise ProviderFailure(
            "runtime_evidence_failed", "Installed runtime evidence is unavailable"
        ) from exc
    actual = {
        "provider_version": VERSION,
        "interpreter": {
            "path": str(interpreter),
            "sha256": interpreter_sha256,
            "version": platform.python_version(),
        },
        "lium_sdk": {"distribution": "lium.io", "version": sdk_version},
        "lium_cli": {
            "path": str(cli_path),
            "sha256": cli_sha256,
            "version": args.expected_lium_cli_version,
            "version_source": "wrapper_verified_cli_version",
        },
    }
    expected = {
        "interpreter_path": args.expected_interpreter_path,
        "interpreter_sha256": args.expected_interpreter_sha256,
        "interpreter_version": args.expected_interpreter_version,
        "lium_sdk_version": args.expected_lium_sdk_version,
        "lium_cli_sha256": args.expected_lium_cli_sha256,
    }
    observed = {
        "interpreter_path": actual["interpreter"]["path"],
        "interpreter_sha256": actual["interpreter"]["sha256"],
        "interpreter_version": actual["interpreter"]["version"],
        "lium_sdk_version": actual["lium_sdk"]["version"],
        "lium_cli_sha256": actual["lium_cli"]["sha256"],
    }
    if observed != expected:
        raise ProviderFailure("runtime_evidence_mismatch", "Installed runtime evidence mismatch")
    return actual


def create_h100_pod(
    client: Any,
    args: argparse.Namespace,
    *,
    ssh_public_key: str,
    now_fn: Callable[[], datetime] | None = None,
    runtime_evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    max_rate = _parse_rate(args.max_rate, "max-rate")
    initial = _resolve_executor_by_huid(client, args.executor_huid)
    initial_rate = _raw_executor_rate(client, initial.id)
    _validate_executor(
        initial,
        args.executor_huid,
        max_rate,
        rate_evidence=initial_rate,
        allow_unknown_from_ls=True,
    )
    try:
        fresh_object = client.get_executor(initial.id)
    except Exception as exc:
        raise ProviderFailure(
            "executor_revalidation_failed", "Could not revalidate executor"
        ) from exc
    if fresh_object is None:
        raise ProviderFailure("executor_revalidation_failed", "Executor disappeared")
    fresh = _executor_snapshot(fresh_object)
    fresh_rate = _raw_executor_rate(client, fresh.id)
    _validate_executor(
        fresh,
        args.executor_huid,
        max_rate,
        rate_evidence=fresh_rate,
        allow_unknown_from_ls=True,
    )
    if fresh != initial or fresh_rate != initial_rate:
        raise ProviderFailure("executor_changed", "Executor properties changed during validation")
    expected_observed_rate = _parse_rate(args.expected_observed_rate, "expected-observed-rate")
    if fresh_rate.price_per_hour != expected_observed_rate:
        raise ProviderFailure(
            "executor_rate_changed_from_signed_observation",
            "Raw executor rate no longer matches the signed observation",
        )

    template = _resolve_template(client, fresh, args)
    preexisting_pod_ids = _snapshot_active_pod_ids(client, args.name)
    launch_rate = _raw_executor_rate(client, fresh.id)
    if launch_rate != fresh_rate or launch_rate.price_per_hour != expected_observed_rate:
        raise ProviderFailure(
            "executor_rate_changed_before_mutation",
            "Raw executor rate changed before the rent mutation",
        )
    try:
        created, rent_boundary = _single_attempt_provider_up(
            client,
            expected_rate_evidence=launch_rate,
            expected_observed_rate=expected_observed_rate,
            max_rate=max_rate,
            executor_id=fresh.id,
            name=args.name,
            template_id=str(template.id),
            ports=args.ports,
            ssh_keys=[ssh_public_key],
        )
    except RentBoundaryFailure as exc:
        if not exc.mutation_started:
            raise
        _raise_after_ambiguous_creation(
            client,
            allocation_name=args.name,
            preexisting_pod_ids=preexisting_pod_ids,
            confirmed_error=exc.code,
            confirmed_message=(
                "Raw executor rate changed after rent; attributable pods were terminated"
            ),
            failure_details=exc.details,
        )
    except Exception:
        _raise_after_ambiguous_creation(
            client,
            allocation_name=args.name,
            preexisting_pod_ids=preexisting_pod_ids,
            confirmed_error="pod_create_failed",
            confirmed_message="Lium pod creation failed; attributable pods were terminated",
        )
    if not isinstance(created, Mapping) or not _clean_text(created.get("id")):
        _raise_after_ambiguous_creation(
            client,
            allocation_name=args.name,
            preexisting_pod_ids=preexisting_pod_ids,
            confirmed_error="pod_create_response_invalid",
            confirmed_message="Lium returned malformed pod metadata; attributable pods were terminated",
        )
    pod_id = _clean_text(created["id"])
    pod_handle = PodHandle(pod_id)

    ttl_seconds = _parse_ttl(args.ttl)
    now = _utc_now(now_fn() if now_fn is not None else None)
    termination_time = (now + timedelta(seconds=ttl_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")
    requested_termination = _parse_utc_instant(termination_time)
    try:
        schedule = client.schedule_termination(pod_handle, termination_time=termination_time)
        if not isinstance(schedule, Mapping):
            raise TypeError("schedule response is not a mapping")
    except Exception as exc:
        cleanup = _terminate_created_pod(client, pod_handle)
        raise ProviderFailure(
            "schedule_failed",
            "Termination scheduling failed; created pod cleanup was attempted",
            details={"pod_id": pod_id, "cleanup": cleanup},
        ) from exc

    try:
        ready = client.wait_ready(
            {"id": pod_id},
            timeout=args.poll_timeout,
            poll_interval=args.poll_interval,
        )
    except Exception as exc:
        cleanup = _terminate_created_pod(client, pod_handle)
        raise ProviderFailure(
            "readiness_poll_failed",
            "Pod readiness polling failed; created pod cleanup was attempted",
            details={"pod_id": pod_id, "cleanup": cleanup},
        ) from exc
    if ready is None:
        cleanup = _terminate_created_pod(client, pod_handle)
        raise ProviderFailure(
            "readiness_timeout",
            "Pod did not become SSH-ready before the bounded timeout",
            details={"pod_id": pod_id, "cleanup": cleanup},
        )
    try:
        server_removal_scheduled_at = _validate_ready_pod(
            ready,
            pod_id,
            args.name,
            fresh,
            requested_termination=requested_termination,
        )
    except ProviderFailure as exc:
        cleanup = _terminate_created_pod(client, pod_handle)
        raise ProviderFailure(
            exc.code,
            "Ready pod validation failed; created pod cleanup was attempted",
            details={"pod_id": pod_id, "cleanup": cleanup},
        ) from exc
    create_reconciliation = _reconcile_successful_creation(
        client,
        allocation_name=args.name,
        expected_pod_id=pod_id,
    )

    return {
        "schema": OUTPUT_SCHEMA,
        "status": "RUNNING",
        "pod": {
            "id": _clean_text(ready.id),
            "name": _clean_text(ready.name),
            "huid": _clean_text(ready.huid),
            "ssh_cmd": _clean_text(ready.ssh_cmd),
        },
        "executor": {
            "id": fresh.id,
            "huid": fresh.huid,
            "gpu_count": fresh.gpu_count,
            "gpu_type": fresh.gpu_type,
            "gpu_model": fresh.gpu_model,
            "observed_rate_usd_per_hour": float(launch_rate.price_per_hour),
            "observed_rate_usd_per_gpu_hour": float(launch_rate.price_per_gpu),
            "observed_rate_status": "provider_reported_nonzero",
            "max_rate_usd_per_hour": float(max_rate),
            "rate_authority": launch_rate.authority,
            "rate_evidence": {
                "executor_id": rent_boundary.before_post.executor_id,
                "gpu_count": rent_boundary.before_post.gpu_count,
                "available_gpu_count": rent_boundary.before_post.available_gpu_count,
                "price_per_gpu": float(rent_boundary.before_post.price_per_gpu),
                "price_per_hour": float(rent_boundary.before_post.price_per_hour),
                "pending_price_change": False,
            },
            "rent_boundary": {
                "status": "VERIFIED_PRE_AND_POST",
                "endpoint": rent_boundary.endpoint,
                "before_post": _raw_rate_record(rent_boundary.before_post),
                "after_post": _raw_rate_record(rent_boundary.after_post),
            },
        },
        "template": {
            "id": _clean_text(template.id),
            "name": _clean_text(getattr(template, "name", "")),
            "docker_image": _clean_text(getattr(template, "docker_image", "")),
            "docker_image_tag": _clean_text(getattr(template, "docker_image_tag", "")),
            "status": _clean_text(getattr(template, "status", "")),
        },
        "runtime_evidence": dict(runtime_evidence or {}),
        "access": {
            "ssh_public_key_path": args.ssh_public_key_path,
            "ssh_public_key_sha256": args.ssh_public_key_sha256,
        },
        "create_reconciliation": create_reconciliation,
        "schedule": {
            "confirmed": True,
            "termination_time": termination_time,
            "server_removal_scheduled_at": server_removal_scheduled_at,
            "verified_termination_time": requested_termination.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ttl_seconds": ttl_seconds,
        },
        "poll": {
            "timeout_seconds": args.poll_timeout,
            "interval_seconds": args.poll_interval,
        },
    }


def _new_lium_client(credential: bytearray) -> Any:
    try:
        from lium.sdk import Config, Lium
    except ImportError as exc:
        raise ProviderFailure(
            "sdk_unavailable",
            "lium.sdk is unavailable under the provider interpreter",
        ) from exc
    try:
        api_key = credential.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProviderFailure("credential_invalid", "stdin credential is not UTF-8") from exc
    return Lium(Config(api_key=api_key))


def _single_attempt_provider_up(
    client: Any,
    *,
    expected_rate_evidence: RawRateEvidence,
    expected_observed_rate: Decimal,
    max_rate: Decimal,
    executor_id: str,
    **kwargs: Any,
) -> tuple[Any, RentBoundaryEvidence]:
    """Call SDK up once, bracketing its exact rent POST with raw rate reads."""

    request = getattr(client, "_request", None)
    undecorated = getattr(request, "__wrapped__", None)
    if not callable(undecorated):
        if type(client).__module__.startswith("lium."):
            raise ProviderFailure(
                "sdk_mutation_boundary_unavailable",
                "Pinned Lium SDK no longer exposes the single-attempt request boundary",
            )
        raise ProviderFailure(
            "sdk_mutation_boundary_unavailable",
            "The provider client does not expose the pinned rent request boundary",
        )

    instance_attributes = vars(client)
    sentinel = object()
    previous_instance_request = instance_attributes.get("_request", sentinel)
    rent_endpoint = f"/executors/{executor_id}/rent"
    boundary_evidence: RentBoundaryEvidence | None = None
    rent_post_count = 0

    def direct_request(method: str, endpoint: str, *args: Any, **request_kwargs: Any) -> Any:
        return undecorated(client, method, endpoint, *args, **request_kwargs)

    def one_attempt(method: str, endpoint: str, *args: Any, **request_kwargs: Any) -> Any:
        nonlocal boundary_evidence, rent_post_count
        if method.upper() != "POST":
            return direct_request(method, endpoint, *args, **request_kwargs)
        if endpoint != rent_endpoint or rent_post_count:
            raise RentBoundaryFailure(
                "unexpected_sdk_mutation",
                "SDK attempted an unexpected or repeated provider mutation",
                mutation_started=False,
                details={"expected_endpoint": rent_endpoint},
            )
        try:
            before_post = _raw_executor_rate_with_request(direct_request, executor_id)
            _validate_rent_boundary_rate(
                before_post,
                expected_rate_evidence=expected_rate_evidence,
                expected_observed_rate=expected_observed_rate,
                max_rate=max_rate,
                phase="before_post",
            )
        except ProviderFailure as exc:
            raise RentBoundaryFailure(
                "executor_rate_changed_at_rent_boundary",
                "Raw executor rate validation failed at the rent POST boundary",
                mutation_started=False,
                details={"phase": "before_post", **exc.details},
            ) from exc
        rent_post_count += 1
        response = direct_request(method, endpoint, *args, **request_kwargs)
        try:
            after_post = _raw_executor_rate_with_request(
                direct_request,
                executor_id,
                require_full_availability=False,
            )
            _validate_rent_boundary_rate(
                after_post,
                expected_rate_evidence=before_post,
                expected_observed_rate=expected_observed_rate,
                max_rate=max_rate,
                phase="after_post",
                allow_availability_decrease=True,
            )
        except ProviderFailure as exc:
            details = {
                "phase": "after_post",
                "rent_endpoint": rent_endpoint,
                "before_post": _raw_rate_record(before_post),
            }
            details.update(exc.details)
            raise RentBoundaryFailure(
                "executor_rate_changed_after_rent",
                "Raw executor rate changed immediately after the rent POST",
                mutation_started=True,
                details=details,
            ) from exc
        boundary_evidence = RentBoundaryEvidence(
            endpoint=rent_endpoint,
            before_post=before_post,
            after_post=after_post,
        )
        return response

    client._request = one_attempt
    try:
        result = client.up(executor_id=executor_id, **kwargs)
        if rent_post_count != 1 or boundary_evidence is None:
            raise ProviderFailure(
                "sdk_rent_boundary_not_observed",
                "SDK up did not execute exactly one verified rent POST",
            )
        return result, boundary_evidence
    finally:
        if previous_instance_request is sentinel:
            del client._request
        else:
            client._request = previous_instance_request


def _validate_arguments(args: argparse.Namespace) -> None:
    if _HUID_RE.fullmatch(args.executor_huid) is None:
        raise ProviderFailure("invalid_arguments", "executor_huid has invalid format")
    if _NAME_RE.fullmatch(args.name) is None:
        raise ProviderFailure(
            "invalid_arguments", "name must be issue-owned: issue-<number>-<slug>"
        )
    if not args.yes:
        raise ProviderFailure("noninteractive_required", "--yes is required")
    _parse_ttl(args.ttl)
    max_rate = _parse_rate(args.max_rate, "max-rate")
    expected_rate = _parse_rate(args.expected_observed_rate, "expected-observed-rate")
    if expected_rate > max_rate:
        raise ProviderFailure("invalid_arguments", "expected-observed-rate exceeds max-rate")
    if args.expected_rate_authority != RATE_AUTHORITY:
        raise ProviderFailure("invalid_arguments", "expected-rate-authority mismatch")
    if args.template_id is not None and _TEMPLATE_RE.fullmatch(args.template_id) is None:
        raise ProviderFailure("invalid_arguments", "template-id has invalid format")
    for field in ("template_image", "template_tag", "template_status"):
        value = _clean_text(getattr(args, field, ""))
        if not value or any(ord(character) < 32 for character in value):
            raise ProviderFailure("invalid_arguments", f"{field} is invalid")
    if args.expected_provider_version != VERSION:
        raise ProviderFailure("runtime_version_mismatch", "Provider version mismatch")
    for field in ("expected_interpreter_path", "expected_lium_cli_path"):
        if not Path(getattr(args, field)).is_absolute():
            raise ProviderFailure("invalid_arguments", f"{field} must be absolute")
    if not Path(args.ssh_public_key_path).is_absolute():
        raise ProviderFailure("invalid_arguments", "ssh-public-key-path must be absolute")
    for field in ("expected_interpreter_sha256", "expected_lium_cli_sha256"):
        if re.fullmatch(r"[0-9a-f]{64}", getattr(args, field)) is None:
            raise ProviderFailure("invalid_arguments", f"{field} must be SHA-256 hex")
    if re.fullmatch(r"[0-9a-f]{64}", args.ssh_public_key_sha256) is None:
        raise ProviderFailure("invalid_arguments", "ssh-public-key-sha256 must be SHA-256 hex")
    if args.ports is not None and not 1 <= args.ports <= 64:
        raise ProviderFailure("invalid_arguments", "ports must be between 1 and 64")
    if not 1 <= args.poll_timeout <= MAX_POLL_TIMEOUT_SECONDS:
        raise ProviderFailure("invalid_arguments", "poll-timeout must be in [1, 240]")
    if not 1 <= args.poll_interval <= MAX_POLL_INTERVAL_SECONDS:
        raise ProviderFailure("invalid_arguments", "poll-interval must be in [1, 30]")
    if args.poll_interval > args.poll_timeout:
        raise ProviderFailure("invalid_arguments", "poll-interval exceeds poll-timeout")


def _validate_reconciliation_arguments(args: argparse.Namespace) -> None:
    if _NAME_RE.fullmatch(args.name) is None:
        raise ProviderFailure(
            "invalid_arguments", "name must be issue-owned: issue-<number>-<slug>"
        )
    if len(args.preexisting_id) > MAX_TERMINAL_RECONCILIATION_PODS:
        raise ProviderFailure("invalid_arguments", "too many preexisting pod IDs")
    if len(set(args.preexisting_id)) != len(args.preexisting_id):
        raise ProviderFailure("invalid_arguments", "preexisting pod IDs must be unique")
    if any(_HUID_RE.fullmatch(pod_id) is None for pod_id in args.preexisting_id):
        raise ProviderFailure("invalid_arguments", "preexisting pod ID has invalid format")
    if args.mode == "snapshot" and args.preexisting_id:
        raise ProviderFailure("invalid_arguments", "snapshot does not accept preexisting IDs")


def reconcile_exact_name_allocations(client: Any, args: argparse.Namespace) -> dict[str, Any]:
    """Snapshot or remove exact-name allocations for the outer signed wrapper."""

    preexisting_ids = frozenset(args.preexisting_id)
    if args.mode == "snapshot":
        try:
            matches, ambiguous = _named_pod_snapshot(client, args.name)
        except Exception as exc:
            raise ProviderFailure(
                "allocation_snapshot_failed",
                "Exact-name allocation snapshot failed",
                details={"mode": "snapshot", "allocation_name": args.name},
            ) from exc
        if ambiguous:
            raise ProviderFailure(
                "allocation_snapshot_ambiguous",
                "Exact-name allocation metadata is ambiguous",
                details={"mode": "snapshot", "allocation_name": args.name},
            )
        ids = sorted(matches)
        if ids:
            raise ProviderFailure(
                "allocation_name_in_use",
                "The signed allocation name is already active",
                details={
                    "mode": "snapshot",
                    "allocation_name": args.name,
                    "preexisting_exact_name_ids": ids,
                },
            )
        return {
            "schema": RECONCILIATION_SCHEMA,
            "status": "SNAPSHOT_CLEAR",
            "mode": "snapshot",
            "allocation_name": args.name,
            "preexisting_exact_name_ids": [],
        }

    observed_ids: set[str] = set()
    terminated_ids: set[str] = set()
    lookup_failures = 0
    termination_failures = 0
    ambiguous = False
    final_ids: list[str] = []
    for _ in range(TERMINAL_RECONCILIATION_ATTEMPTS):
        try:
            matches, snapshot_ambiguous = _named_pod_snapshot(client, args.name)
        except Exception:
            lookup_failures += 1
            continue
        ambiguous = ambiguous or snapshot_ambiguous
        attributable = {
            pod_id: pod for pod_id, pod in matches.items() if pod_id not in preexisting_ids
        }
        observed_ids.update(attributable)
        final_ids = sorted(attributable)
        if not attributable and not snapshot_ambiguous:
            return {
                "schema": RECONCILIATION_SCHEMA,
                "status": "CONFIRMED_ABSENT",
                "mode": "cleanup",
                "allocation_name": args.name,
                "preexisting_exact_name_ids": sorted(preexisting_ids),
                "observed_attributable_ids": sorted(observed_ids),
                "terminated_attributable_ids": sorted(terminated_ids),
                "final_attributable_ids": [],
                "lookup_failures": lookup_failures,
                "termination_failures": termination_failures,
            }
        if len(observed_ids) > MAX_TERMINAL_RECONCILIATION_PODS:
            ambiguous = True
            break
        for pod_id, pod in sorted(attributable.items()):
            try:
                client.down(pod)
                terminated_ids.add(pod_id)
            except Exception:
                termination_failures += 1

    raise ProviderFailure(
        "allocation_cleanup_unconfirmed",
        "Attributable exact-name allocation cleanup could not be confirmed",
        details={
            "mode": "cleanup",
            "allocation_name": args.name,
            "preexisting_exact_name_ids": sorted(preexisting_ids),
            "observed_attributable_ids": sorted(observed_ids),
            "terminated_attributable_ids": sorted(terminated_ids),
            "final_attributable_ids": final_ids,
            "lookup_failures": lookup_failures,
            "termination_failures": termination_failures,
            "attribution_ambiguous": ambiguous,
        },
    )


def _resolve_executor_by_huid(client: Any, huid: str) -> ExecutorSnapshot:
    try:
        executors = client.ls()
    except Exception as exc:
        raise ProviderFailure("executor_lookup_failed", "Executor lookup failed") from exc
    matches = [executor for executor in executors if _clean_text(executor.huid) == huid]
    if len(matches) != 1:
        raise ProviderFailure(
            "executor_not_unique", "Expected exactly one executor matching the signed HUID"
        )
    return _executor_snapshot(matches[0])


def _executor_snapshot(executor: Any) -> ExecutorSnapshot:
    try:
        return ExecutorSnapshot(
            id=_clean_text(executor.id),
            huid=_clean_text(executor.huid),
            gpu_type=_clean_text(executor.gpu_type),
            gpu_model=_clean_text(executor.gpu_model),
            gpu_count=int(executor.gpu_count),
            status=_clean_text(executor.status).upper(),
            observed_rate=_decimal(executor.price_per_hour, "price_per_hour"),
            observed_gpu_rate=_decimal(executor.price_per_gpu_hour, "price_per_gpu_hour"),
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise ProviderFailure("executor_shape_invalid", "Executor metadata is incomplete") from exc


def _raw_executor_rate(client: Any, executor_id: str) -> RawRateEvidence:
    return _raw_executor_rate_with_request(client._request, executor_id)


def _raw_executor_rate_with_request(
    request: Callable[..., Any],
    executor_id: str,
    *,
    require_full_availability: bool = True,
) -> RawRateEvidence:
    try:
        response = request("GET", "/executors", params={"size": 1000})
        rows = response.json()
    except Exception as exc:
        raise ProviderFailure(
            "executor_rate_lookup_failed",
            "Raw executor rate lookup failed",
        ) from exc
    if not isinstance(rows, list):
        raise ProviderFailure("executor_rate_shape_invalid", "Raw executor list is malformed")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("id") == executor_id]
    if len(matches) != 1:
        raise ProviderFailure(
            "executor_rate_not_unique",
            "Expected exactly one raw rate record for the executor",
        )
    row = matches[0]
    try:
        gpu_count = int(row.get("gpu_count"))
        available_gpu_count = int(row.get("available_gpu_count"))
    except (TypeError, ValueError) as exc:
        raise ProviderFailure(
            "executor_rate_shape_invalid",
            "Raw executor GPU availability is malformed",
        ) from exc
    price_per_gpu = _decimal(row.get("price_per_gpu"), "price_per_gpu")
    if row.get("pending_price_per_hour") is not None or row.get("price_change_effective_date"):
        raise ProviderFailure(
            "executor_rate_change_pending",
            "Executor has a pending rate change",
        )
    availability_is_valid = 0 <= available_gpu_count <= gpu_count
    if (
        gpu_count != 8
        or not availability_is_valid
        or (require_full_availability and available_gpu_count != gpu_count)
    ):
        raise ProviderFailure(
            "executor_raw_availability_mismatch",
            "Raw executor record has invalid GPU availability for this boundary",
        )
    if price_per_gpu <= 0:
        raise ProviderFailure(
            "executor_rate_invalid",
            "Raw executor price_per_gpu must be positive",
        )
    return RawRateEvidence(
        executor_id=executor_id,
        gpu_count=gpu_count,
        available_gpu_count=available_gpu_count,
        price_per_gpu=price_per_gpu,
        price_per_hour=price_per_gpu * Decimal(gpu_count),
    )


def _raw_rate_record(evidence: RawRateEvidence) -> dict[str, Any]:
    return {
        "authority": evidence.authority,
        "executor_id": evidence.executor_id,
        "gpu_count": evidence.gpu_count,
        "available_gpu_count": evidence.available_gpu_count,
        "price_per_gpu": float(evidence.price_per_gpu),
        "price_per_hour": float(evidence.price_per_hour),
        "pending_price_change": False,
    }


def _validate_rent_boundary_rate(
    evidence: RawRateEvidence,
    *,
    expected_rate_evidence: RawRateEvidence,
    expected_observed_rate: Decimal,
    max_rate: Decimal,
    phase: str,
    allow_availability_decrease: bool = False,
) -> None:
    same_rate_identity = (
        evidence.executor_id == expected_rate_evidence.executor_id
        and evidence.gpu_count == expected_rate_evidence.gpu_count
        and evidence.price_per_gpu == expected_rate_evidence.price_per_gpu
        and evidence.price_per_hour == expected_rate_evidence.price_per_hour
        and evidence.authority == expected_rate_evidence.authority
    )
    availability_matches = (
        evidence.available_gpu_count == expected_rate_evidence.available_gpu_count
    )
    if allow_availability_decrease:
        availability_matches = (
            0 <= evidence.available_gpu_count <= expected_rate_evidence.available_gpu_count
        )
    if (
        not same_rate_identity
        or not availability_matches
        or evidence.price_per_hour != expected_observed_rate
        or not Decimal("0") < evidence.price_per_hour <= max_rate
    ):
        raise ProviderFailure(
            "executor_rate_boundary_mismatch",
            "Raw executor rate does not match the signed rent authority",
            details={
                "phase": phase,
                "expected": _raw_rate_record(expected_rate_evidence),
                "observed": _raw_rate_record(evidence),
            },
        )


def _validate_executor(
    executor: ExecutorSnapshot,
    expected_huid: str,
    max_rate: Decimal,
    *,
    rate_evidence: RawRateEvidence,
    allow_unknown_from_ls: bool = False,
) -> None:
    if not executor.id or executor.huid != expected_huid:
        raise ProviderFailure("executor_identity_mismatch", "Executor identity mismatch")
    if executor.gpu_count != 8:
        raise ProviderFailure("executor_gpu_count_mismatch", "Executor must have 8 GPUs")
    if "H100" not in f"{executor.gpu_type} {executor.gpu_model}".upper():
        raise ProviderFailure("executor_gpu_model_mismatch", "Executor must use H100 GPUs")
    status_is_eligible = executor.status in _READY_EXECUTOR_STATES or (
        allow_unknown_from_ls and executor.status == "UNKNOWN"
    )
    if not status_is_eligible:
        raise ProviderFailure("executor_unavailable", "Executor is not available")
    if rate_evidence.executor_id != executor.id or rate_evidence.gpu_count != executor.gpu_count:
        raise ProviderFailure("executor_rate_identity_mismatch", "Raw rate identity mismatch")
    if not Decimal("0") < rate_evidence.price_per_hour <= max_rate:
        raise ProviderFailure("executor_rate_exceeded", "Observed node rate exceeds cap")
    if executor.observed_rate < 0 or executor.observed_gpu_rate < 0:
        raise ProviderFailure("executor_rate_invalid", "SDK-mapped executor rate is invalid")
    if executor.observed_rate not in {Decimal("0"), rate_evidence.price_per_hour}:
        raise ProviderFailure("executor_rate_mapping_mismatch", "SDK and raw node rates disagree")


def _resolve_template(client: Any, executor: ExecutorSnapshot, args: argparse.Namespace) -> Any:
    del executor
    try:
        template = client.get_template(args.template_id)
    except Exception as exc:
        raise ProviderFailure("template_resolution_failed", "Template resolution failed") from exc
    if template is None or not _clean_text(getattr(template, "id", "")):
        raise ProviderFailure("template_resolution_failed", "No usable template was found")
    if _clean_text(template.id) != args.template_id:
        raise ProviderFailure("template_identity_mismatch", "Template identity mismatch")
    template_status = _clean_text(getattr(template, "status", "")).upper()
    if template_status not in _USABLE_TEMPLATE_STATES:
        raise ProviderFailure("template_unusable", "Explicit template is not usable")
    expected = {
        "docker_image": args.template_image,
        "docker_image_tag": args.template_tag,
        "status": args.template_status,
    }
    for field, value in expected.items():
        if _clean_text(getattr(template, field, "")) != value:
            raise ProviderFailure(
                "template_metadata_mismatch", "Explicit template metadata mismatch"
            )
    return template


def _pod_field(pod: Any, field: str) -> Any:
    if isinstance(pod, Mapping):
        return pod.get(field)
    return getattr(pod, field, None)


def _list_active_pods(client: Any) -> list[Any]:
    pods = client.ps()
    if pods is None or isinstance(pods, (str, bytes, Mapping)):
        raise TypeError("pod listing is not a sequence")
    return list(pods)


def _cleanup_details(status: str, pod_ids: Sequence[str]) -> dict[str, Any]:
    unique_ids = sorted(set(pod_ids))
    return {
        "cleanup_status": status,
        "cleanup_count": len(unique_ids),
        "cleanup_pod_ids": unique_ids,
    }


def _snapshot_active_pod_ids(client: Any, allocation_name: str) -> frozenset[str]:
    try:
        pods = _list_active_pods(client)
    except Exception as exc:
        raise ProviderFailure(
            "pod_snapshot_failed",
            "Could not snapshot active pods before creation",
            details=_cleanup_details("NOT_REQUIRED", ()),
        ) from exc
    pod_ids: set[str] = set()
    for pod in pods:
        pod_name = _clean_text(_pod_field(pod, "name"))
        pod_id = _clean_text(_pod_field(pod, "id"))
        if pod_name == allocation_name:
            raise ProviderFailure(
                "allocation_name_in_use",
                "An active pod already uses the signed allocation name",
                details=_cleanup_details("NOT_REQUIRED", ()),
            )
        if not pod_id:
            raise ProviderFailure(
                "pod_snapshot_invalid",
                "Active pod metadata is missing an ID",
                details=_cleanup_details("NOT_REQUIRED", ()),
            )
        pod_ids.add(pod_id)
    return frozenset(pod_ids)


def _recover_ambiguous_creation(
    client: Any,
    *,
    allocation_name: str,
    preexisting_pod_ids: frozenset[str],
) -> dict[str, Any]:
    candidates: dict[str, Any] = {}
    lookup_failed = False
    attribution_ambiguous = False
    successful_lookups = 0
    for _ in range(RECOVERY_LOOKUP_ATTEMPTS):
        try:
            pods = _list_active_pods(client)
        except Exception:
            lookup_failed = True
            continue
        successful_lookups += 1
        for pod in pods:
            if _clean_text(_pod_field(pod, "name")) != allocation_name:
                continue
            pod_id = _clean_text(_pod_field(pod, "id"))
            if not pod_id:
                attribution_ambiguous = True
                continue
            if pod_id not in preexisting_pod_ids:
                candidates[pod_id] = pod

    cleanup_failed = False
    for pod_id in sorted(candidates):
        try:
            client.down(candidates[pod_id])
        except Exception:
            cleanup_failed = True
    final_attributable_ids: list[str] = []
    try:
        final_matches, final_ambiguous = _named_pod_snapshot(client, allocation_name)
        attribution_ambiguous = attribution_ambiguous or final_ambiguous
        final_attributable_ids = sorted(set(final_matches) - set(preexisting_pod_ids))
    except Exception:
        lookup_failed = True
    confirmed = (
        successful_lookups == RECOVERY_LOOKUP_ATTEMPTS
        and not lookup_failed
        and not attribution_ambiguous
        and bool(candidates)
        and not cleanup_failed
        and not final_attributable_ids
    )
    return _cleanup_details(
        "CONFIRMED" if confirmed else "UNCONFIRMED",
        tuple(candidates),
    )


def _raise_after_ambiguous_creation(
    client: Any,
    *,
    allocation_name: str,
    preexisting_pod_ids: frozenset[str],
    confirmed_error: str,
    confirmed_message: str,
    failure_details: Mapping[str, Any] | None = None,
) -> NoReturn:
    cleanup = _recover_ambiguous_creation(
        client,
        allocation_name=allocation_name,
        preexisting_pod_ids=preexisting_pod_ids,
    )
    details = dict(failure_details or {})
    if failure_details is None:
        details = cleanup
    else:
        details["cleanup"] = cleanup
    if cleanup["cleanup_status"] != "CONFIRMED":
        raise ProviderFailure(
            "pod_create_cleanup_unconfirmed",
            "Ambiguous pod creation cleanup could not be confirmed",
            details=details,
        )
    raise ProviderFailure(confirmed_error, confirmed_message, details=details)


def _named_pod_snapshot(
    client: Any,
    allocation_name: str,
) -> tuple[dict[str, Any], bool]:
    matches: dict[str, Any] = {}
    attribution_ambiguous = False
    for pod in _list_active_pods(client):
        if _clean_text(_pod_field(pod, "name")) != allocation_name:
            continue
        pod_id = _clean_text(_pod_field(pod, "id"))
        if not pod_id or pod_id in matches:
            attribution_ambiguous = True
            continue
        matches[pod_id] = pod
    return matches, attribution_ambiguous


def _reconcile_successful_creation(
    client: Any,
    *,
    allocation_name: str,
    expected_pod_id: str,
) -> dict[str, Any]:
    """Prove SDK retries did not leave another paid pod with the signed name."""

    observed: dict[str, Any] = {}
    lookup_failures = 0
    successful_snapshots = 0
    attribution_ambiguous = False
    final_ids: list[str] = []
    for _ in range(SUCCESS_RECONCILIATION_ATTEMPTS):
        try:
            matches, ambiguous = _named_pod_snapshot(client, allocation_name)
        except Exception:
            lookup_failures += 1
            continue
        successful_snapshots += 1
        attribution_ambiguous = attribution_ambiguous or ambiguous
        observed.update(matches)
        final_ids = sorted(matches)
        duplicate_ids = sorted(set(matches) - {expected_pod_id})
        for pod_id in duplicate_ids:
            try:
                client.down(matches[pod_id])
            except Exception:
                pass
        if (
            not attribution_ambiguous
            and successful_snapshots >= MIN_SUCCESSFUL_RECONCILIATION_SNAPSHOTS
            and final_ids == [expected_pod_id]
        ):
            observed_duplicates = sorted(set(observed) - {expected_pod_id})
            return {
                "status": "CONFIRMED_UNIQUE",
                "rent_mutation_attempt_policy": RENT_MUTATION_ATTEMPT_POLICY,
                "allocation_name": allocation_name,
                "pod_id": expected_pod_id,
                "successful_snapshots": successful_snapshots,
                "lookup_failures": lookup_failures,
                "final_active_pod_ids": final_ids,
                "observed_duplicate_pod_ids": observed_duplicates,
                "duplicate_cleanup_status": (
                    "CONFIRMED" if observed_duplicates else "NOT_REQUIRED"
                ),
            }

    cleanup_failed = False
    cleanup_ids = set(observed) | {expected_pod_id}
    for pod_id in sorted(cleanup_ids):
        target = observed.get(pod_id, PodHandle(pod_id))
        try:
            client.down(target)
        except Exception:
            cleanup_failed = True
    raise ProviderFailure(
        "pod_create_reconciliation_unconfirmed",
        "Successful create did not prove one unique allocation; cleanup was attempted",
        details={
            "expected_pod_id": expected_pod_id,
            "allocation_name": allocation_name,
            "successful_snapshots": successful_snapshots,
            "lookup_failures": lookup_failures,
            "attribution_ambiguous": attribution_ambiguous,
            "final_active_pod_ids": final_ids,
            "observed_named_pod_ids": sorted(observed),
            "cleanup": _cleanup_details(
                "UNCONFIRMED" if cleanup_failed else "CONFIRMED",
                sorted(cleanup_ids),
            ),
        },
    )


def _validate_ready_pod(
    pod: Any,
    expected_id: str,
    expected_name: str,
    executor: ExecutorSnapshot,
    *,
    requested_termination: datetime,
) -> str:
    if _clean_text(getattr(pod, "id", "")) != expected_id:
        raise ProviderFailure("pod_identity_mismatch", "Ready pod ID mismatch")
    if _clean_text(getattr(pod, "name", "")) != expected_name:
        raise ProviderFailure("pod_identity_mismatch", "Ready pod name mismatch")
    if _clean_text(getattr(pod, "status", "")).upper() != "RUNNING":
        raise ProviderFailure("pod_not_running", "Pod is not RUNNING")
    if not _clean_text(getattr(pod, "ssh_cmd", "")):
        raise ProviderFailure("pod_not_ssh_ready", "Pod has no SSH command")
    pod_executor = getattr(pod, "executor", None)
    if pod_executor is not None:
        ready_executor = _executor_snapshot(pod_executor)
        if ready_executor.id != executor.id or ready_executor.huid != executor.huid:
            raise ProviderFailure("pod_executor_mismatch", "Pod executor mismatch")
        if ready_executor.gpu_count != 8 or "H100" not in (
            f"{ready_executor.gpu_type} {ready_executor.gpu_model}".upper()
        ):
            raise ProviderFailure("pod_executor_mismatch", "Pod GPU shape mismatch")
    server_value = _clean_text(getattr(pod, "removal_scheduled_at", ""))
    if not server_value:
        raise ProviderFailure("schedule_verification_failed", "Ready pod has no scheduled removal")
    try:
        server_termination = _parse_utc_instant(server_value)
    except ProviderFailure as exc:
        raise ProviderFailure(
            "schedule_verification_failed", "Ready pod schedule is not valid UTC"
        ) from exc
    if server_termination != requested_termination:
        raise ProviderFailure(
            "schedule_verification_failed", "Ready pod schedule does not match request"
        )
    return server_value


def _terminate_created_pod(client: Any, pod: PodHandle) -> str:
    target: Any = pod
    try:
        matches = [
            candidate
            for candidate in client.ps()
            if _clean_text(getattr(candidate, "id", "")) == pod.id
        ]
        if len(matches) > 1:
            return "FAILED"
        if len(matches) == 1:
            target = matches[0]
    except Exception:
        target = pod
    try:
        client.down(target)
    except Exception:
        return "FAILED"
    return "TERMINATED"


def _parse_ttl(value: str) -> int:
    match = _TTL_RE.fullmatch(value)
    if match is None:
        raise ProviderFailure("invalid_arguments", "ttl must use an integer h or m suffix")
    seconds = int(match.group(1)) * (3600 if match.group(2) == "h" else 60)
    if not 0 < seconds <= MAX_TTL_SECONDS:
        raise ProviderFailure("invalid_arguments", "ttl must be in (0, 2h]")
    return seconds


def _parse_rate(value: Any, label: str) -> Decimal:
    rate = _decimal(value, label)
    if not Decimal("0") < rate <= MAX_RATE_USD_PER_HOUR:
        raise ProviderFailure("invalid_arguments", f"{label} must be in (0, 18]")
    return rate


def _decimal(value: Any, label: str) -> Decimal:
    if isinstance(value, bool):
        raise ProviderFailure("invalid_numeric_value", f"{label} is invalid")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ProviderFailure("invalid_numeric_value", f"{label} is invalid") from exc
    if not number.is_finite() or not math.isfinite(float(number)):
        raise ProviderFailure("invalid_numeric_value", f"{label} is invalid")
    return number


def _utc_now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ProviderFailure("invalid_clock", "Clock must be timezone-aware")
    return current.astimezone(timezone.utc)


def _parse_utc_instant(value: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ProviderFailure("invalid_schedule_time", "Schedule time is missing")
    if value.endswith("Z"):
        normalized = value[:-1] + "+00:00"
    elif value.endswith("+00:00"):
        normalized = value
    else:
        raise ProviderFailure("invalid_schedule_time", "Schedule time is not UTC")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ProviderFailure(
            "invalid_schedule_time", "Schedule time is not valid ISO-8601"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ProviderFailure("invalid_schedule_time", "Schedule time is not UTC")
    return parsed.astimezone(timezone.utc)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _emit(payload: Mapping[str, Any]) -> None:
    print(
        json.dumps(payload, sort_keys=True, allow_nan=False, separators=(",", ":")),
        flush=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
