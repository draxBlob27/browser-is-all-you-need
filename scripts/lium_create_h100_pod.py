#!/opt/homebrew/opt/python@3.11/bin/python3.11
"""Create one bounded 8xH100 Lium pod without entering SSH."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, Mapping, Sequence


VERSION = "1.0.0"
OUTPUT_SCHEMA = "lium-h100-pod-create/v1"
MAX_TTL_SECONDS = 2 * 60 * 60
MAX_RATE_USD_PER_HOUR = Decimal("18")
MAX_POLL_TIMEOUT_SECONDS = 240
MAX_POLL_INTERVAL_SECONDS = 30
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


def build_parser() -> MachineArgumentParser:
    parser = MachineArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", parser_class=MachineArgumentParser)
    up = subparsers.add_parser("up", help="create one bounded H100 allocation")
    up.add_argument("executor_huid")
    up.add_argument("--ttl", required=True)
    up.add_argument("--name", required=True)
    up.add_argument("--yes", action="store_true")
    up.add_argument("--template-id")
    up.add_argument("--max-rate", default="18")
    up.add_argument("--ports", type=int)
    up.add_argument("--poll-timeout", type=int, default=240)
    up.add_argument("--poll-interval", type=int, default=5)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    client_factory: Callable[[], Any] | None = None,
    now_fn: Callable[[], datetime] | None = None,
) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments == ["--version"]:
        print(VERSION, flush=True)
        return 0
    try:
        args = build_parser().parse_args(arguments)
        if args.command != "up":
            raise ProviderFailure("invalid_arguments", "the up command is required")
        _validate_arguments(args)
        factory = client_factory or _new_lium_client
        client = factory()
        record = create_h100_pod(client, args, now_fn=now_fn)
    except ProviderFailure as exc:
        _emit(
            {
                "schema": OUTPUT_SCHEMA,
                "status": "ERROR",
                "error": exc.code,
                "message": exc.message,
                "details": exc.details,
            }
        )
        return 2
    except Exception:
        _emit(
            {
                "schema": OUTPUT_SCHEMA,
                "status": "ERROR",
                "error": "sdk_failure",
                "message": "Lium SDK operation failed",
                "details": {},
            }
        )
        return 3
    _emit(record)
    return 0


def create_h100_pod(
    client: Any,
    args: argparse.Namespace,
    *,
    now_fn: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    max_rate = _parse_rate(args.max_rate, "max-rate")
    initial = _resolve_executor_by_huid(client, args.executor_huid)
    _validate_executor(initial, args.executor_huid, max_rate, allow_unknown_from_ls=True)
    try:
        fresh_object = client.get_executor(initial.id)
    except Exception as exc:
        raise ProviderFailure(
            "executor_revalidation_failed", "Could not revalidate executor"
        ) from exc
    if fresh_object is None:
        raise ProviderFailure("executor_revalidation_failed", "Executor disappeared")
    fresh = _executor_snapshot(fresh_object)
    _validate_executor(fresh, args.executor_huid, max_rate, allow_unknown_from_ls=True)
    if fresh != initial:
        raise ProviderFailure("executor_changed", "Executor properties changed during validation")

    template = _resolve_template(client, fresh, args.template_id)
    try:
        created = client.up(
            executor_id=fresh.id,
            name=args.name,
            template_id=str(template.id),
            ports=args.ports,
        )
    except Exception as exc:
        raise ProviderFailure("pod_create_failed", "Lium pod creation failed") from exc
    if not isinstance(created, Mapping) or not _clean_text(created.get("id")):
        raise ProviderFailure("pod_create_failed", "Lium did not return a pod ID")
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
            "observed_rate_usd_per_hour": float(fresh.observed_rate),
            "observed_rate_usd_per_gpu_hour": float(fresh.observed_gpu_rate),
            "max_rate_usd_per_hour": float(max_rate),
        },
        "template": {
            "id": _clean_text(template.id),
            "name": _clean_text(getattr(template, "name", "")),
        },
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


def _new_lium_client() -> Any:
    try:
        from lium.sdk import Lium
    except ImportError as exc:
        raise ProviderFailure(
            "sdk_unavailable",
            "lium.sdk is unavailable under the provider interpreter",
        ) from exc
    return Lium()


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
    _parse_rate(args.max_rate, "max-rate")
    if args.template_id is not None and _TEMPLATE_RE.fullmatch(args.template_id) is None:
        raise ProviderFailure("invalid_arguments", "template-id has invalid format")
    if args.ports is not None and not 1 <= args.ports <= 64:
        raise ProviderFailure("invalid_arguments", "ports must be between 1 and 64")
    if not 1 <= args.poll_timeout <= MAX_POLL_TIMEOUT_SECONDS:
        raise ProviderFailure("invalid_arguments", "poll-timeout must be in [1, 240]")
    if not 1 <= args.poll_interval <= MAX_POLL_INTERVAL_SECONDS:
        raise ProviderFailure("invalid_arguments", "poll-interval must be in [1, 30]")
    if args.poll_interval > args.poll_timeout:
        raise ProviderFailure("invalid_arguments", "poll-interval exceeds poll-timeout")


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


def _validate_executor(
    executor: ExecutorSnapshot,
    expected_huid: str,
    max_rate: Decimal,
    *,
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
    if not Decimal("0") <= executor.observed_rate <= max_rate:
        raise ProviderFailure("executor_rate_exceeded", "Observed node rate exceeds cap")
    if executor.observed_gpu_rate < 0:
        raise ProviderFailure("executor_rate_invalid", "Observed GPU rate is invalid")


def _resolve_template(client: Any, executor: ExecutorSnapshot, template_id: str | None) -> Any:
    try:
        template = (
            client.get_template(template_id)
            if template_id is not None
            else client.default_docker_template(executor.id)
        )
    except Exception as exc:
        raise ProviderFailure("template_resolution_failed", "Template resolution failed") from exc
    if template is None or not _clean_text(getattr(template, "id", "")):
        raise ProviderFailure("template_resolution_failed", "No usable template was found")
    if template_id is not None and _clean_text(template.id) != template_id:
        raise ProviderFailure("template_identity_mismatch", "Template identity mismatch")
    if template_id is not None:
        template_status = _clean_text(getattr(template, "status", "")).upper()
        if template_status and template_status not in _USABLE_TEMPLATE_STATES:
            raise ProviderFailure(
                "template_unusable", "Explicit template is not in a usable status"
            )
    return template


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
