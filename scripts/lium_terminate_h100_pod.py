#!/usr/bin/env python3
"""Terminate one artifact-bound Lium H100 allocation and prove it is absent."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


RECEIPT_SCHEMA = "lium-h100-termination-receipt/v1"
MAX_CREDENTIAL_BYTES = 4096
POLL_ATTEMPTS = 5
POLL_INTERVAL_SECONDS = 2
_ALLOCATION_NAME_RE = re.compile(r"issue-[1-9][0-9]*-[a-z0-9][a-z0-9-]{2,62}\Z")


class TerminationFailure(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider-output", required=True)
    parser.add_argument("--launch-receipt", required=True)
    parser.add_argument("--allocation-id", required=True)
    parser.add_argument("--allocation-name", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--yes", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    client_factory: Callable[[bytearray], Any] | None = None,
    credential_reader: Callable[[], bytearray] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> int:
    args = build_parser().parse_args(argv)
    receipt_path = Path(args.receipt).expanduser()
    started_at = _utc_timestamp()
    try:
        if not args.yes:
            raise TerminationFailure("noninteractive_required", "--yes is required")
        binding = _verify_artifact_binding(
            Path(args.provider_output),
            Path(args.launch_receipt),
            allocation_id=args.allocation_id,
            allocation_name=args.allocation_name,
        )
        credential = (credential_reader or _read_stdin_credential)()
        try:
            client = (client_factory or _new_lium_client)(credential)
        finally:
            _wipe_bytearray(credential)
        result = _terminate_and_confirm(
            client,
            allocation_id=args.allocation_id,
            allocation_name=args.allocation_name,
            sleep_fn=sleep_fn,
        )
        payload = {
            "schema": RECEIPT_SCHEMA,
            "status": result["status"],
            "started_at_utc": started_at,
            "finished_at_utc": _utc_timestamp(),
            "allocation": {
                "id": args.allocation_id,
                "name": args.allocation_name,
            },
            "source": binding,
            "preflight": result["preflight"],
            "postflight": result["postflight"],
        }
        exit_code = 0
    except TerminationFailure as exc:
        payload = {
            "schema": RECEIPT_SCHEMA,
            "status": "ERROR",
            "error": exc.code,
            "message": exc.message,
            "started_at_utc": started_at,
            "finished_at_utc": _utc_timestamp(),
        }
        exit_code = 2
    try:
        _write_exclusive_json(receipt_path, payload)
    except TerminationFailure as exc:
        print(json.dumps({"status": "ERROR", "error": exc.code}), flush=True)
        return 3
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")), flush=True)
    return exit_code


def _verify_artifact_binding(
    provider_output_path: Path,
    launch_receipt_path: Path,
    *,
    allocation_id: str,
    allocation_name: str,
) -> dict[str, Any]:
    if not allocation_id or _ALLOCATION_NAME_RE.fullmatch(allocation_name) is None:
        raise TerminationFailure("allocation_identity_invalid", "Allocation identity is invalid")
    provider_path = _regular_resolved_path(provider_output_path, "provider output")
    receipt_path = _regular_resolved_path(launch_receipt_path, "launch receipt")
    provider = _read_json(provider_path, "provider output")
    receipt = _read_json(receipt_path, "launch receipt")
    pod = provider.get("pod") if isinstance(provider.get("pod"), Mapping) else {}
    reconciliation = (
        provider.get("create_reconciliation")
        if isinstance(provider.get("create_reconciliation"), Mapping)
        else {}
    )
    if (
        provider.get("schema") != "lium-h100-pod-create/v2"
        or provider.get("status") != "RUNNING"
        or pod.get("id") != allocation_id
        or pod.get("name") != allocation_name
        or reconciliation.get("status") != "CONFIRMED_UNIQUE"
        or reconciliation.get("pod_id") != allocation_id
        or reconciliation.get("allocation_name") != allocation_name
        or reconciliation.get("final_active_pod_ids") != [allocation_id]
    ):
        raise TerminationFailure(
            "provider_binding_invalid",
            "Provider output does not bind the exact unique allocation",
        )
    receipt_output = (
        receipt.get("provider_output")
        if isinstance(receipt.get("provider_output"), Mapping)
        else {}
    )
    receipt_allocation = (
        receipt.get("allocation") if isinstance(receipt.get("allocation"), Mapping) else {}
    )
    provider_sha = _sha256(provider_path)
    if (
        receipt.get("schema") != "h100-lium-launch-receipt/v2"
        or receipt.get("status") != "COMPLETED"
        or receipt_output.get("sha256") != provider_sha
        or receipt_output.get("size_bytes") != provider_path.stat().st_size
        or Path(str(receipt_output.get("path") or "")).expanduser().resolve() != provider_path
        or receipt_allocation.get("name") != allocation_name
    ):
        raise TerminationFailure(
            "launch_receipt_binding_invalid",
            "Launch receipt does not bind the provider output and allocation",
        )
    return {
        "provider_output_path": str(provider_path),
        "provider_output_sha256": provider_sha,
        "launch_receipt_path": str(receipt_path),
        "launch_receipt_sha256": _sha256(receipt_path),
    }


def _terminate_and_confirm(
    client: Any,
    *,
    allocation_id: str,
    allocation_name: str,
    sleep_fn: Callable[[float], None],
) -> dict[str, Any]:
    initial = _target_snapshot(client, allocation_id, allocation_name)
    if initial["identity_conflict"]:
        raise TerminationFailure(
            "allocation_identity_conflict",
            "Active pod state conflicts with the artifact-bound allocation",
        )
    if initial["target_present"]:
        try:
            client.down(initial["target"])
        except Exception:
            pass
    last = initial
    for attempt in range(POLL_ATTEMPTS):
        last = _target_snapshot(client, allocation_id, allocation_name)
        if last["identity_conflict"]:
            raise TerminationFailure(
                "allocation_identity_conflict",
                "Post-termination pod state conflicts with the allocation",
            )
        if not last["target_present"]:
            return {
                "status": "TERMINATED" if initial["target_present"] else "ALREADY_ABSENT",
                "preflight": _public_snapshot(initial),
                "postflight": {
                    **_public_snapshot(last),
                    "confirmed_absent": True,
                    "poll_attempts": attempt + 1,
                },
            }
        if attempt + 1 < POLL_ATTEMPTS:
            sleep_fn(POLL_INTERVAL_SECONDS)
    raise TerminationFailure(
        "termination_unconfirmed",
        "Artifact-bound allocation remains active after bounded polling",
    )


def _target_snapshot(client: Any, allocation_id: str, allocation_name: str) -> dict[str, Any]:
    try:
        pods = client.ps()
    except Exception as exc:
        raise TerminationFailure("pod_listing_failed", "Could not list active pods") from exc
    if pods is None or isinstance(pods, (str, bytes, Mapping)):
        raise TerminationFailure("pod_listing_invalid", "Active pod listing is malformed")
    exact = []
    id_conflicts = 0
    name_conflicts = 0
    for pod in pods:
        pod_id = str(_pod_field(pod, "id") or "").strip()
        pod_name = str(_pod_field(pod, "name") or "").strip()
        if pod_id == allocation_id and pod_name == allocation_name:
            exact.append(pod)
        elif pod_id == allocation_id:
            id_conflicts += 1
        elif pod_name == allocation_name:
            name_conflicts += 1
    return {
        "target_present": len(exact) == 1,
        "target": exact[0] if len(exact) == 1 else None,
        "identity_conflict": len(exact) > 1 or id_conflicts > 0 or name_conflicts > 0,
        "id_conflict_count": id_conflicts,
        "name_conflict_count": name_conflicts,
    }


def _public_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "target_present": snapshot["target_present"],
        "identity_conflict": snapshot["identity_conflict"],
        "id_conflict_count": snapshot["id_conflict_count"],
        "name_conflict_count": snapshot["name_conflict_count"],
    }


def _pod_field(pod: Any, field: str) -> Any:
    return pod.get(field) if isinstance(pod, Mapping) else getattr(pod, field, None)


def _new_lium_client(credential: bytearray) -> Any:
    try:
        from lium.sdk import Config, Lium
    except ImportError as exc:
        raise TerminationFailure("sdk_unavailable", "lium.sdk is unavailable") from exc
    try:
        api_key = credential.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise TerminationFailure("credential_invalid", "stdin credential is not UTF-8") from exc
    os.environ.pop("LIUM_API_KEY", None)
    return Lium(Config(api_key=api_key))


def _read_stdin_credential() -> bytearray:
    line = sys.stdin.buffer.readline(MAX_CREDENTIAL_BYTES + 2)
    tail = sys.stdin.buffer.read(1)
    if tail or len(line) > MAX_CREDENTIAL_BYTES + 1:
        raise TerminationFailure("credential_invalid", "stdin credential exceeds one bounded line")
    if line.endswith(b"\n"):
        line = line[:-1]
    if not line or b"\n" in line or b"\r" in line or b"\x00" in line:
        raise TerminationFailure("credential_invalid", "stdin credential is invalid")
    return bytearray(line)


def _wipe_bytearray(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0


def _regular_resolved_path(path: Path, label: str) -> Path:
    source = path.expanduser()
    try:
        metadata = source.lstat()
    except OSError as exc:
        raise TerminationFailure("artifact_unavailable", f"{label} is unavailable") from exc
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise TerminationFailure("artifact_invalid", f"{label} must be a regular non-symlink file")
    return source.resolve()


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TerminationFailure("artifact_malformed", f"{label} is malformed") from exc
    if not isinstance(value, dict):
        raise TerminationFailure("artifact_malformed", f"{label} must be an object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_exclusive_json(path: Path, payload: Mapping[str, Any]) -> None:
    if not path.is_absolute():
        raise TerminationFailure("receipt_path_invalid", "Termination receipt path must be absolute")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(
                json.dumps(payload, indent=2, sort_keys=True, allow_nan=False).encode("utf-8")
                + b"\n"
            )
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise TerminationFailure("receipt_exists", "Termination receipt already exists") from exc
    except OSError as exc:
        raise TerminationFailure("receipt_write_failed", "Could not write termination receipt") from exc


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


if __name__ == "__main__":
    raise SystemExit(main())
