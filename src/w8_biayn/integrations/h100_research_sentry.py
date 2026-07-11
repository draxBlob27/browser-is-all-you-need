"""Independent offline stage machine for the 8x H100 research contract."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import itertools
import json
import math
import os
import re
import secrets
import shlex
import stat
import statistics
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence, TypeVar

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from w8_biayn.integrations import h100_signed_approval as _gate0_approval
from w8_biayn.integrations.h100_signed_approval import (
    ENVELOPE_SCHEMA as GATE0_ENVELOPE_SCHEMA,
    LAUNCH_RECEIPT_SCHEMA,
    PERMIT_SCHEMA as GATE0_PERMIT_SCHEMA,
    PUBLIC_KEY_SCHEMA as GATE0_PUBLIC_KEY_SCHEMA,
    SIGNATURE_DOMAIN as GATE0_SIGNATURE_DOMAIN,
    PermitError,
    canonical_json_bytes,
    domain_separated_message,
    key_id_for_public_key,
    load_public_key_document,
    verify_detached_signature,
    verify_permit,
)
from w8_biayn.integrations.miles_mfu import summarize_miles_mfu_trial
from w8_biayn.integrations.wandb_posttraining import (
    parse_miles_metric_events,
    read_json,
    read_key_value,
)


class Stage(str, Enum):
    PREFLIGHT = "preflight"
    SCREEN = "screen"
    PROMOTION = "promotion"
    CONFIRMATION = "confirmation"
    GRPO = "grpo"
    FINAL = "final"


class Decision(str, Enum):
    INVALID = "INVALID"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    PROMOTABLE = "PROMOTABLE"
    VERIFIED = "VERIFIED"
    NO_WIN = "NO_WIN"


@dataclass(frozen=True)
class SentryPolicy:
    contract_id: str = "h100-fastest-accepted-v1"
    metric_name: str = "estimated_active_model_equivalent_mfu"
    bf16_peak_tflops_per_gpu: float = 989.0
    screen_minimum_ratio: float = 0.98
    promotion_minimum_ratio: float = 1.03
    historical_reference_mfu_percent: float = 2.0690522449347637
    historical_reference_actor_tok_s: float = 6735.536057011609
    historical_mfu_percent: float = 2.1311238122828066
    historical_actor_tok_s: float = 6937.602138721957
    control_baseline_relative_tolerance: float = 0.05
    confirmation_min_pairs: int = 4
    confidence_level: float = 0.95
    warmup_observations: int = 2
    matched_observations: int = 14
    complete_cycle_observations: int = 12
    workload_cycle_size: int = 4
    min_vram_headroom_mib: float = 4096.0
    required_timing_status: str = "verified"
    required_gpu_count: int = 8
    required_gpu_name: str = "H100"
    minimum_gpu_memory_mib: float = 80_000.0
    minimum_power_limit_w: float = 690.0
    required_topology: str = "NV18"
    training_base_sha: str = "cd83e3c8780f09e38e5b58558d84580e74afbcf6"
    miles_sha: str = "01a6d7bb74befa6e97579c80a2b1add0667606f3"
    megatron_sha: str = "79fc0894d0ba57acd10a9c0da507abd1dfef3bdf"
    required_tranche_id: str = "T1"
    maximum_node_hours: float = 2.0
    maximum_usd: float = 36.0
    first_pair_deadline_seconds: int = 3600
    minimum_telemetry_rows_per_gpu: int = 2
    minimum_telemetry_overlap_fraction: float = 0.8


@dataclass(frozen=True)
class SentrySecurity:
    signing_private_key_path: str | Path
    sentry_public_key_path: str | Path
    sentry_principal: str
    executor_principal: str
    supervisor_public_key_path: str | Path | None = None
    supervisor_principal: str | None = None
    auditor_public_key_path: str | Path | None = None
    auditor_principal: str | None = None
    now: datetime | None = None
    decision_ttl_seconds: int = 1800


@dataclass(frozen=True)
class VerifiedDecision:
    payload: Mapping[str, Any]
    key_id: str
    request_id: str
    nonce: str
    issued_at: datetime
    expires_at: datetime
    artifact_sha256: str


class DecisionSecurityError(RuntimeError):
    """A signed research decision failed closed."""


class DecisionReplayError(DecisionSecurityError):
    """A signed research decision was already consumed."""


@dataclass(frozen=True)
class _Trial:
    summary_path: Path
    root: Path
    log_path: Path
    receipt_path: Path
    summary: dict[str, Any]
    canonical: dict[str, Any]
    receipt: dict[str, Any]
    log_text: str
    events: tuple[dict[str, Any], ...]
    vectors: tuple[dict[str, Any], ...]
    telemetry: dict[str, Any]
    timing: dict[str, Any]
    workload: dict[str, Any]
    valid: bool
    reasons: tuple[str, ...]


_OUTPUT_SCHEMA = "h100-research-sentry-decision/v3"
_AUTHOR = "h100_research_sentry"
_SIGNATURE_SCHEMA = "h100-research-detached-signature/v1"
BOOKING_REQUEST_SCHEMA = "h100-lium-booking-request/v1"
_INTENT_SCHEMAS = {
    "source": "h100-booking-source-intent/v1",
    "runtime": "h100-booking-runtime-intent/v1",
    "data": "h100-booking-data-intent/v1",
    "checkpoint": "h100-booking-checkpoint-intent/v1",
}
_BOOKING_REQUEST_FIELDS = frozenset(
    {
        "schema",
        "issue_number",
        "allocation_name",
        "provider",
        "provider_version",
        "profile",
        "executor_id",
        "sentry_principal",
        "executor_principal",
        "gate1_trust",
        "hardware",
        "budget",
        "intent_artifacts",
    }
)
_GATE1_TRUST_FIELDS = frozenset(
    {"public_key_sha256", "key_id", "sentry_principal", "executor_principal"}
)
_BOOKING_HARDWARE_FIELDS = frozenset({"gpu_type", "gpu_count"})
_BOOKING_BUDGET_FIELDS = frozenset(
    {
        "ttl_seconds",
        "max_cost_usd",
        "max_node_hourly_rate_usd",
        "observed_node_hourly_rate_usd",
        "observed_node_hourly_rate_status",
        "max_node_hours",
    }
)
_INTENT_DESCRIPTOR_FIELDS = frozenset({"path", "sha256"})
_INTENT_PAYLOAD_FIELDS = {
    "source": frozenset({"schema", "repo_sha", "training_base_sha", "acceptance_contract_sha256"}),
    "runtime": frozenset({"schema", "miles_sha", "megatron_sha", "runtime_pins"}),
    "data": frozenset({"schema", "train_sha256", "manifest_sha256", "row_count"}),
    "checkpoint": frozenset({"schema", "root", "layout", "hf_model", "hf_revision"}),
}
_RUNTIME_PIN_FIELDS = frozenset(
    {
        "container_image",
        "container_platform",
        "hf_model",
        "hf_revision",
        "lium_cli_version",
        "lium_provider_version",
    }
)
_SETUP_ATTESTATION_FIELDS = frozenset(
    {
        "schema",
        "created_at_utc",
        "hf_checkpoint_path",
        "hf_model",
        "hf_revision",
        "hf_revision_marker_path",
        "hf_revision_marker_sha256",
        "container_image_reference",
        "container_image_digest",
        "container_platform",
        "container_image_id",
        "container_inspection_path",
        "container_inspection_sha256",
    }
)
_DECISION_DOMAINS = {
    stage: f"w8-biayn/h100-research-{stage.value}-decision/ed25519/v1\0".encode() for stage in Stage
}
T2_AUTHORIZATION_DOMAIN = b"w8-biayn/h100-research-t2-authorization/ed25519/v1\0"
AUDIT_DECISION_DOMAIN = b"w8-biayn/h100-research-independent-audit/ed25519/v1\0"
_SIGNATURE_FIELDS = frozenset({"signature_base64", "signed_payload_sha256"})
_REQUEST_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}\Z")
_HEX_256_RE = re.compile(r"[0-9a-f]{64}\Z")
_GATE0_PAYLOAD_FIELDS = frozenset(_gate0_approval._PAYLOAD_FIELDS)  # noqa: SLF001
_FATAL_RE = re.compile(
    r"(?:CUDA out of memory|OutOfMemoryError|RayTaskError|ChildFailedError)"
    r"|(?:NCCL[^\n]*(?:unhandled|error|failed))",
    re.IGNORECASE,
)
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_SUMMARY_FIELDS = (
    "status",
    "ray_status",
    "peak_vram_mib",
    "steady_event_count",
    "steady_steps",
    "steady_token_signature",
    "actor_tflops_per_gpu_median",
    "bf16_equivalent_mfu_percent_median",
    "global_actor_tok_s_median",
    "loss_values",
    "grad_norm_values",
    "config",
)
_ONE_SIDED_T95 = {
    1: 6.313752,
    2: 2.919986,
    3: 2.353363,
    4: 2.131847,
    5: 2.015048,
    6: 1.94318,
    7: 1.894579,
    8: 1.859548,
    9: 1.833113,
    10: 1.812461,
    11: 1.795885,
    12: 1.782288,
    13: 1.770933,
    14: 1.76131,
    15: 1.75305,
    16: 1.745884,
    17: 1.739607,
    18: 1.734064,
    19: 1.729133,
    20: 1.724718,
    21: 1.720743,
    22: 1.717144,
    23: 1.713872,
    24: 1.710882,
    25: 1.708141,
    26: 1.705618,
    27: 1.703288,
    28: 1.701131,
    29: 1.699127,
    30: 1.697261,
}

_CallbackResult = TypeVar("_CallbackResult")


def _validate_gate0_booking_request(
    request_path: str | Path,
    permit_payload: Mapping[str, Any],
    public_key_path: str | Path,
) -> dict[str, Any]:
    reasons: list[str] = []
    supplied = Path(request_path).expanduser()
    try:
        metadata = supplied.lstat()
    except OSError:
        metadata = None
    if metadata is None or stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        return {
            "passed": False,
            "reasons": ["gate0_booking_request_not_regular"],
            "intent_artifacts": {},
        }
    source = supplied.resolve()
    try:
        request = read_json(source)
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "passed": False,
            "reasons": ["gate0_booking_request_malformed"],
            "intent_artifacts": {},
        }
    if request.get("schema") != BOOKING_REQUEST_SCHEMA:
        reasons.append("gate0_booking_request_schema_invalid")
    if set(request) != _BOOKING_REQUEST_FIELDS:
        reasons.append("gate0_booking_request_fields_invalid")

    bindings = {
        "issue_number": "issue_number",
        "allocation_name": "allocation_name",
        "provider": "provider",
        "provider_version": "provider_version",
        "profile": "profile",
        "executor_id": "executor_id",
        "sentry_principal": "sentry_principal",
        "executor_principal": "executor_principal",
    }
    for request_field, permit_field in bindings.items():
        if request.get(request_field) != permit_payload.get(permit_field):
            reasons.append(f"gate0_booking_request_{request_field}_mismatch")

    hardware = request.get("hardware")
    if not isinstance(hardware, dict) or set(hardware) != _BOOKING_HARDWARE_FIELDS:
        reasons.append("gate0_booking_request_hardware_invalid")
    elif hardware.get("gpu_type") != permit_payload.get("gpu_type") or hardware.get(
        "gpu_count"
    ) != permit_payload.get("gpu_count"):
        reasons.append("gate0_booking_request_hardware_mismatch")

    budget = request.get("budget")
    if not isinstance(budget, dict) or set(budget) != _BOOKING_BUDGET_FIELDS:
        reasons.append("gate0_booking_request_budget_invalid")
    else:
        for field in sorted(_BOOKING_BUDGET_FIELDS):
            if budget.get(field) != permit_payload.get(field):
                reasons.append(f"gate0_booking_request_budget_mismatch:{field}")

    trust = request.get("gate1_trust")
    try:
        public_key = load_public_key_document(public_key_path)
        expected_public_hash = _hash_file(Path(public_key_path).expanduser().resolve())
    except (OSError, PermitError):
        public_key = None
        expected_public_hash = ""
        reasons.append("gate0_booking_request_gate1_public_key_invalid")
    expected_trust = {
        "public_key_sha256": expected_public_hash,
        "key_id": public_key.key_id if public_key is not None else "",
        "sentry_principal": permit_payload.get("sentry_principal"),
        "executor_principal": permit_payload.get("executor_principal"),
    }
    if not isinstance(trust, dict) or set(trust) != _GATE1_TRUST_FIELDS or trust != expected_trust:
        reasons.append("gate0_booking_request_gate1_trust_mismatch")

    descriptors = request.get("intent_artifacts")
    expected_names = set(_INTENT_SCHEMAS)
    if not isinstance(descriptors, dict) or set(descriptors) != expected_names:
        reasons.append("gate0_booking_request_intent_map_invalid")
        descriptors = {}
    resolved_paths: set[Path] = {source}
    artifacts: dict[str, dict[str, Any]] = {}
    for name in sorted(expected_names):
        descriptor = descriptors.get(name)
        if not isinstance(descriptor, dict) or set(descriptor) != _INTENT_DESCRIPTOR_FIELDS:
            reasons.append(f"gate0_intent_descriptor_invalid:{name}")
            continue
        path_value = descriptor.get("path")
        path = Path(str(path_value or "")).expanduser()
        if not isinstance(path_value, str) or not path.is_absolute():
            reasons.append(f"gate0_intent_path_not_absolute:{name}")
            continue
        try:
            artifact_metadata = path.lstat()
        except OSError:
            artifact_metadata = None
        if (
            artifact_metadata is None
            or stat.S_ISLNK(artifact_metadata.st_mode)
            or not stat.S_ISREG(artifact_metadata.st_mode)
        ):
            reasons.append(f"gate0_intent_artifact_not_regular:{name}")
            continue
        resolved = path.resolve()
        if resolved in resolved_paths:
            reasons.append(f"gate0_intent_artifact_not_external:{name}")
            continue
        resolved_paths.add(resolved)
        actual_hash = _hash_file(resolved)
        permit_hash = permit_payload.get(f"{name}_sha256")
        if not _valid_sha256(descriptor.get("sha256")):
            reasons.append(f"gate0_intent_sha256_invalid:{name}")
        if descriptor.get("sha256") != actual_hash:
            reasons.append(f"gate0_intent_artifact_hash_mismatch:{name}")
        if permit_hash != actual_hash:
            reasons.append(f"gate0_intent_permit_hash_mismatch:{name}")
        try:
            intent = read_json(resolved)
        except (OSError, ValueError, json.JSONDecodeError):
            reasons.append(f"gate0_intent_artifact_malformed:{name}")
            continue
        if set(intent) != _INTENT_PAYLOAD_FIELDS[name]:
            reasons.append(f"gate0_intent_payload_fields_invalid:{name}")
        if intent.get("schema") != _INTENT_SCHEMAS[name]:
            reasons.append(f"gate0_intent_payload_schema_invalid:{name}")
        artifacts[name] = {
            "path": str(resolved),
            "sha256": actual_hash,
            "payload": intent,
        }

    source_intent = (artifacts.get("source") or {}).get("payload") or {}
    if (
        re.fullmatch(r"[0-9a-f]{40}", str(source_intent.get("repo_sha") or "")) is None
        or re.fullmatch(r"[0-9a-f]{40}", str(source_intent.get("training_base_sha") or "")) is None
        or not _valid_sha256(source_intent.get("acceptance_contract_sha256"))
    ):
        reasons.append("gate0_source_intent_values_invalid")
    runtime_intent = (artifacts.get("runtime") or {}).get("payload") or {}
    runtime_pins = runtime_intent.get("runtime_pins")
    if (
        re.fullmatch(r"[0-9a-f]{40}", str(runtime_intent.get("miles_sha") or "")) is None
        or re.fullmatch(r"[0-9a-f]{40}", str(runtime_intent.get("megatron_sha") or "")) is None
        or not isinstance(runtime_pins, dict)
        or set(runtime_pins) != _RUNTIME_PIN_FIELDS
        or any(not isinstance(value, str) or not value for value in runtime_pins.values())
    ):
        reasons.append("gate0_runtime_intent_values_invalid")
    elif runtime_pins.get("lium_provider_version") != request.get(
        "provider_version"
    ) or runtime_pins.get("lium_cli_version") != permit_payload.get("lium_cli_version"):
        reasons.append("gate0_runtime_intent_provider_version_mismatch")
    data_intent = (artifacts.get("data") or {}).get("payload") or {}
    if (
        not _valid_sha256(data_intent.get("train_sha256"))
        or not _valid_sha256(data_intent.get("manifest_sha256"))
        or type(data_intent.get("row_count")) is not int
        or data_intent.get("row_count", 0) <= 0
    ):
        reasons.append("gate0_data_intent_values_invalid")
    checkpoint_intent = (artifacts.get("checkpoint") or {}).get("payload") or {}
    if (
        not Path(str(checkpoint_intent.get("root") or "")).is_absolute()
        or not str(checkpoint_intent.get("layout") or "")
        or not str(checkpoint_intent.get("hf_model") or "")
        or re.fullmatch(r"[0-9a-f]{40}", str(checkpoint_intent.get("hf_revision") or "")) is None
    ):
        reasons.append("gate0_checkpoint_intent_values_invalid")
    return {
        "passed": not reasons,
        "reasons": sorted(set(reasons)),
        "artifact": str(source),
        "sha256": _hash_file(source),
        "gate1_trust": trust if isinstance(trust, dict) else {},
        "intent_artifacts": artifacts,
    }


def sign_gate0_permit_payload(
    payload: Mapping[str, Any],
    *,
    private_key_path: str | Path,
    public_key_path: str | Path,
    gate1_public_key_path: str | Path,
    parent_request_path: str | Path,
    expected_sentry_principal: str,
    expected_executor_principal: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate and issue the exact shared Gate0 permit envelope."""

    missing = sorted(_GATE0_PAYLOAD_FIELDS - set(payload))
    unknown = sorted(set(payload) - _GATE0_PAYLOAD_FIELDS)
    if missing or unknown:
        raise DecisionSecurityError(
            f"Gate0 payload fields mismatch: missing={missing}, unknown={unknown}"
        )
    parent_input = Path(parent_request_path).expanduser()
    try:
        parent_metadata = parent_input.lstat()
    except OSError as exc:
        raise DecisionSecurityError(f"Gate0 parent request unavailable: {exc}") from exc
    if stat.S_ISLNK(parent_metadata.st_mode) or not stat.S_ISREG(parent_metadata.st_mode):
        raise DecisionSecurityError("Gate0 parent request must be a regular file")
    parent = parent_input.resolve()
    if payload.get("parent_request_sha256") != _hash_file(parent):
        raise DecisionSecurityError("Gate0 parent request digest mismatch")
    booking = _validate_gate0_booking_request(parent, payload, gate1_public_key_path)
    if not booking["passed"]:
        raise DecisionSecurityError(
            "Gate0 booking request invalid: " + ", ".join(booking["reasons"])
        )
    executable_input = Path(str(payload.get("provider_executable"))).expanduser()
    try:
        executable_stat = executable_input.lstat()
    except OSError as exc:
        raise DecisionSecurityError(f"Gate0 provider executable unavailable: {exc}") from exc
    if (
        not stat.S_ISREG(executable_stat.st_mode)
        or stat.S_ISLNK(executable_stat.st_mode)
        or executable_stat.st_mode & 0o111 == 0
    ):
        raise DecisionSecurityError("Gate0 provider executable must be executable and regular")
    executable = executable_input.resolve()
    if payload.get("provider_executable_sha256") != _hash_file(executable):
        raise DecisionSecurityError("Gate0 provider executable digest mismatch")
    for path_field, hash_field, label in (
        ("provider_interpreter", "provider_interpreter_sha256", "provider interpreter"),
        ("lium_cli_path", "lium_cli_sha256", "Lium CLI"),
    ):
        bound_input = Path(str(payload.get(path_field) or "")).expanduser()
        try:
            bound_metadata = bound_input.lstat()
        except OSError as exc:
            raise DecisionSecurityError(f"Gate0 {label} unavailable: {exc}") from exc
        if (
            not bound_input.is_absolute()
            or stat.S_ISLNK(bound_metadata.st_mode)
            or not stat.S_ISREG(bound_metadata.st_mode)
            or bound_metadata.st_mode & 0o111 == 0
        ):
            raise DecisionSecurityError(f"Gate0 {label} must be executable and regular")
        if payload.get(hash_field) != _hash_file(bound_input.resolve()):
            raise DecisionSecurityError(f"Gate0 {label} digest mismatch")
    body = dict(payload)
    validation_key = Ed25519PrivateKey.generate()
    validation_raw = validation_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    validation_key_id = key_id_for_public_key(validation_raw)
    validation_envelope = {
        "schema": GATE0_ENVELOPE_SCHEMA,
        "key_id": validation_key_id,
        "payload": body,
        "signature_base64": base64.b64encode(
            validation_key.sign(domain_separated_message(GATE0_SIGNATURE_DOMAIN, body))
        ).decode("ascii"),
    }
    _validate_gate0_envelope_policy(
        validation_envelope,
        {
            "schema": GATE0_PUBLIC_KEY_SCHEMA,
            "algorithm": "Ed25519",
            "key_id": validation_key_id,
            "public_key_base64": base64.b64encode(validation_raw).decode("ascii"),
        },
        expected_sentry_principal=expected_sentry_principal,
        expected_executor_principal=expected_executor_principal,
        now=now,
    )
    private_key = _load_external_private_key(private_key_path)
    public_key = load_public_key_document(public_key_path)
    gate1_public_key = load_public_key_document(gate1_public_key_path)
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = key_id_for_public_key(public_raw)
    if key_id != public_key.key_id:
        raise DecisionSecurityError("private key does not match Gate0 public key")
    if key_id == gate1_public_key.key_id:
        raise DecisionSecurityError("Gate0 and Gate1 keys must be distinct")
    signature = private_key.sign(domain_separated_message(GATE0_SIGNATURE_DOMAIN, body))
    envelope = {
        "schema": GATE0_ENVELOPE_SCHEMA,
        "key_id": key_id,
        "payload": body,
        "signature_base64": base64.b64encode(signature).decode("ascii"),
    }
    _validate_gate0_envelope_policy(
        envelope,
        read_json(public_key_path),
        expected_sentry_principal=expected_sentry_principal,
        expected_executor_principal=expected_executor_principal,
        now=now,
    )
    return envelope


def _validate_gate0_envelope_policy(
    envelope: Mapping[str, Any],
    public_key_document: Mapping[str, Any],
    *,
    expected_sentry_principal: str,
    expected_executor_principal: str,
    now: datetime | None,
) -> None:
    body = envelope.get("payload")
    if not isinstance(body, Mapping):
        raise DecisionSecurityError("Gate0 permit payload must be an object")
    try:
        verify_permit(
            envelope,
            public_key_document,
            expected_key_id=str(envelope.get("key_id") or ""),
            expected_sentry_principal=expected_sentry_principal,
            expected_executor_principal=expected_executor_principal,
            expected_executor_id=str(body["executor_id"]),
            expected_provider=str(body["provider"]),
            expected_profile=str(body["profile"]),
            expected_source_sha256=str(body["source_sha256"]),
            expected_runtime_sha256=str(body["runtime_sha256"]),
            expected_data_sha256=str(body["data_sha256"]),
            expected_checkpoint_sha256=str(body["checkpoint_sha256"]),
            expected_provider_version=str(body["provider_version"]),
            expected_working_directory=str(body["working_directory"]),
            expected_argv=body["argv"] if isinstance(body["argv"], list) else (),
            now=now,
        )
    except (KeyError, PermitError) as exc:
        raise DecisionSecurityError(f"Gate0 policy validation failed: {exc}") from exc


def sign_bounded_payload(
    payload: Mapping[str, Any],
    *,
    private_key_path: str | Path,
    public_key_path: str | Path,
    domain: bytes,
    signer_principal: str,
    verifier_principal: str,
    request_id: str | None = None,
    nonce: str | None = None,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    lifetime_seconds: int = 1800,
) -> dict[str, Any]:
    """Sign a bounded JSON payload without exposing private material."""

    if any(field in payload for field in _SIGNATURE_FIELDS):
        raise DecisionSecurityError("payload is already signed")
    private_key = _load_external_private_key(private_key_path)
    public_document = load_public_key_document(public_key_path)
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    key_id = key_id_for_public_key(public_raw)
    if key_id != public_document.key_id:
        raise DecisionSecurityError("private key does not match trusted public key")
    current = _security_now(issued_at)
    expiry = expires_at or current + timedelta(seconds=lifetime_seconds)
    if expiry <= current or (expiry - current).total_seconds() > 2 * 60 * 60:
        raise DecisionSecurityError("signature lifetime must be in (0, 2h]")
    bounded = dict(payload)
    bounded.update(
        {
            "signature_schema": _SIGNATURE_SCHEMA,
            "signature_domain": domain[:-1].decode("ascii"),
            "request_id": request_id or f"sentry-{secrets.token_hex(12)}",
            "nonce": nonce or secrets.token_hex(32),
            "issued_at": _format_security_time(current),
            "expires_at": _format_security_time(expiry),
            "signer_principal": signer_principal,
            "verifier_principal": verifier_principal,
            "public_key_identity": {
                "algorithm": "Ed25519",
                "key_id": key_id,
                "public_key_document_sha256": _hash_file(
                    Path(public_key_path).expanduser().resolve()
                ),
            },
        }
    )
    _validate_signed_metadata(
        bounded,
        domain=domain,
        expected_signer_principal=signer_principal,
        expected_verifier_principal=verifier_principal,
        now=current,
    )
    canonical = canonical_json_bytes(bounded)
    signature = private_key.sign(domain_separated_message(domain, bounded))
    bounded["signed_payload_sha256"] = hashlib.sha256(canonical).hexdigest()
    bounded["signature_base64"] = base64.b64encode(signature).decode("ascii")
    return bounded


def verify_signed_decision(
    decision_path: str | Path,
    public_key_path: str | Path,
    *,
    expected_stage: Stage | str,
    expected_signer_principal: str,
    expected_verifier_principal: str,
    expected_request_sha256: str | None = None,
    expected_parent_decision_sha256: str | None = None,
    expected_parent_request_sha256: str | None = None,
    now: datetime | None = None,
) -> VerifiedDecision:
    """Verify one sentry decision and all independently supplied bindings."""

    path = Path(decision_path).expanduser().resolve()
    try:
        payload = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise DecisionSecurityError(f"signed decision is malformed: {exc}") from exc
    stage = expected_stage if isinstance(expected_stage, Stage) else Stage(expected_stage)
    if payload.get("stage") != stage.value:
        raise DecisionSecurityError("signed decision stage mismatch")
    metadata = _verify_bounded_payload(
        payload,
        public_key_path=public_key_path,
        domain=_DECISION_DOMAINS[stage],
        expected_signer_principal=expected_signer_principal,
        expected_verifier_principal=expected_verifier_principal,
        now=now,
    )
    for field, expected in (
        ("request_sha256", expected_request_sha256),
        ("parent_decision_sha256", expected_parent_decision_sha256),
        ("parent_request_sha256", expected_parent_request_sha256),
    ):
        if expected is not None and payload.get(field) != expected:
            raise DecisionSecurityError(f"signed decision {field} mismatch")
    return VerifiedDecision(
        payload=payload,
        key_id=metadata["key_id"],
        request_id=str(payload["request_id"]),
        nonce=str(payload["nonce"]),
        issued_at=metadata["issued_at"],
        expires_at=metadata["expires_at"],
        artifact_sha256=_hash_file(path),
    )


def consume_signed_decision_once(
    decision: VerifiedDecision,
    ledger_dir: str | Path,
    *,
    now: datetime | None = None,
) -> Path:
    """Durably consume one signed approval before execution."""

    ledger = Path(ledger_dir).expanduser()
    if not ledger.is_absolute():
        raise DecisionReplayError("decision ledger path must be absolute")
    ledger.mkdir(mode=0o700, parents=True, exist_ok=True)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        before = ledger.lstat()
        ledger_descriptor = os.open(ledger, directory_flags)
        after = os.fstat(ledger_descriptor)
    except OSError as exc:
        raise DecisionReplayError(
            f"decision ledger is not a real private directory: {exc}"
        ) from exc
    if (
        not stat.S_ISDIR(before.st_mode)
        or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
        or after.st_uid != os.getuid()
        or stat.S_IMODE(after.st_mode) & 0o077
    ):
        os.close(ledger_descriptor)
        raise DecisionReplayError("decision ledger must be an owner-only real directory")
    claim_material = canonical_json_bytes(
        {"nonce": decision.nonce, "request_id": decision.request_id}
    )
    claim_id = hashlib.sha256(claim_material).hexdigest()
    claim_name = f"{claim_id}.consumed.json"
    claim_path = ledger / claim_name
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(claim_name, flags, 0o600, dir_fd=ledger_descriptor)
    except FileExistsError as exc:
        os.close(ledger_descriptor)
        raise DecisionReplayError("decision request_id and nonce already consumed") from exc
    except OSError as exc:
        os.close(ledger_descriptor)
        raise DecisionReplayError(f"unable to atomically consume decision: {exc}") from exc
    record = (
        canonical_json_bytes(
            {
                "artifact_sha256": decision.artifact_sha256,
                "key_id": decision.key_id,
                "nonce": decision.nonce,
                "request_id": decision.request_id,
                "consumed_at": _format_security_time(_security_now(now)),
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
        raise DecisionReplayError(f"decision claim could not be durably recorded: {exc}") from exc
    finally:
        os.close(ledger_descriptor)
    return claim_path


def verify_consume_and_execute(
    decision_path: str | Path,
    public_key_path: str | Path,
    *,
    expected_stage: Stage | str,
    expected_signer_principal: str,
    expected_verifier_principal: str,
    expected_request_sha256: str,
    expected_parent_decision_sha256: str | None = None,
    expected_parent_request_sha256: str | None = None,
    ledger_dir: str | Path,
    callback: Callable[[], _CallbackResult],
    now: datetime | None = None,
) -> _CallbackResult:
    """Verify and consume an approval before invoking the execution callback."""

    verified = verify_signed_decision(
        decision_path,
        public_key_path,
        expected_stage=expected_stage,
        expected_signer_principal=expected_signer_principal,
        expected_verifier_principal=expected_verifier_principal,
        expected_request_sha256=expected_request_sha256,
        expected_parent_decision_sha256=expected_parent_decision_sha256,
        expected_parent_request_sha256=expected_parent_request_sha256,
        now=now,
    )
    if verified.payload.get("decision") != Decision.PROMOTABLE.value:
        raise DecisionSecurityError("signed decision does not authorize execution")
    consume_signed_decision_once(verified, ledger_dir, now=now)
    return callback()


def _verify_bounded_payload(
    payload: Mapping[str, Any],
    *,
    public_key_path: str | Path,
    domain: bytes,
    expected_signer_principal: str,
    expected_verifier_principal: str,
    now: datetime | None,
) -> dict[str, Any]:
    unsigned = {key: value for key, value in payload.items() if key not in _SIGNATURE_FIELDS}
    metadata = _validate_signed_metadata(
        unsigned,
        domain=domain,
        expected_signer_principal=expected_signer_principal,
        expected_verifier_principal=expected_verifier_principal,
        now=now,
    )
    expected_hash = hashlib.sha256(canonical_json_bytes(unsigned)).hexdigest()
    if payload.get("signed_payload_sha256") != expected_hash:
        raise DecisionSecurityError("signed payload digest mismatch")
    public_key = load_public_key_document(public_key_path)
    identity = unsigned.get("public_key_identity")
    if not isinstance(identity, dict) or identity != {
        "algorithm": "Ed25519",
        "key_id": public_key.key_id,
        "public_key_document_sha256": _hash_file(Path(public_key_path).expanduser().resolve()),
    }:
        raise DecisionSecurityError("signed public-key identity mismatch")
    try:
        verify_detached_signature(
            public_key,
            domain=domain,
            payload=unsigned,
            signature_base64=str(payload.get("signature_base64") or ""),
        )
    except PermitError as exc:
        raise DecisionSecurityError(str(exc)) from exc
    return {**metadata, "key_id": public_key.key_id}


def _validate_signed_metadata(
    payload: Mapping[str, Any],
    *,
    domain: bytes,
    expected_signer_principal: str,
    expected_verifier_principal: str,
    now: datetime | None,
) -> dict[str, Any]:
    if payload.get("signature_schema") != _SIGNATURE_SCHEMA:
        raise DecisionSecurityError("signature schema mismatch")
    if payload.get("signature_domain") != domain[:-1].decode("ascii"):
        raise DecisionSecurityError("signature domain mismatch")
    request_id = str(payload.get("request_id") or "")
    nonce = str(payload.get("nonce") or "")
    if _REQUEST_ID_RE.fullmatch(request_id) is None:
        raise DecisionSecurityError("request_id is invalid")
    if _HEX_256_RE.fullmatch(nonce) is None or len(bytes.fromhex(nonce)) != 32:
        raise DecisionSecurityError("nonce must contain at least 256 bits")
    if payload.get("signer_principal") != expected_signer_principal:
        raise DecisionSecurityError("signer principal mismatch")
    if payload.get("verifier_principal") != expected_verifier_principal:
        raise DecisionSecurityError("verifier principal mismatch")
    issued_at = _require_security_time(payload.get("issued_at"), "issued_at")
    expires_at = _require_security_time(payload.get("expires_at"), "expires_at")
    lifetime = (expires_at - issued_at).total_seconds()
    current = _security_now(now)
    if lifetime <= 0 or lifetime > 2 * 60 * 60:
        raise DecisionSecurityError("signed lifetime must be in (0, 2h]")
    if current < issued_at:
        raise DecisionSecurityError("signed payload is not yet valid")
    if current >= expires_at:
        raise DecisionSecurityError("signed payload is expired")
    return {"issued_at": issued_at, "expires_at": expires_at}


def _load_external_private_key(path: str | Path) -> Ed25519PrivateKey:
    supplied = Path(path).expanduser()
    try:
        metadata = supplied.lstat()
    except OSError as exc:
        raise DecisionSecurityError(f"private key is unavailable: {exc}") from exc
    if not stat.S_ISREG(metadata.st_mode) or stat.S_ISLNK(metadata.st_mode):
        raise DecisionSecurityError("private key must be a regular non-symlink file")
    source = supplied.resolve()
    repo_root = Path(__file__).resolve().parents[3]
    try:
        source.relative_to(repo_root)
    except ValueError:
        pass
    else:
        raise DecisionSecurityError("private key path must be external to the repository")
    if stat.S_IMODE(metadata.st_mode) & 0o077:
        raise DecisionSecurityError("private key mode is permissive; require 0600 or stricter")
    try:
        loaded = serialization.load_pem_private_key(source.read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise DecisionSecurityError(f"private key PEM is invalid: {exc}") from exc
    if not isinstance(loaded, Ed25519PrivateKey):
        raise DecisionSecurityError("private key must be Ed25519")
    return loaded


def _security_now(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(microsecond=0)


def _format_security_time(value: datetime) -> str:
    return _security_now(value).strftime("%Y-%m-%dT%H:%M:%SZ")


def _require_security_time(value: Any, field: str) -> datetime:
    parsed = _parse_time(value)
    if parsed is None:
        raise DecisionSecurityError(f"{field} is invalid")
    return parsed.replace(microsecond=0)


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _reconcile_preflight_intent(
    *,
    gate0: Mapping[str, Any],
    contract: Mapping[str, Any],
    request: Mapping[str, Any],
    hardware: Mapping[str, Any],
    policy: SentryPolicy,
) -> dict[str, Any]:
    reasons: list[str] = []
    artifacts = gate0.get("intent_artifacts")
    if not isinstance(artifacts, Mapping) or set(artifacts) != set(_INTENT_SCHEMAS):
        return {
            "passed": False,
            "reasons": ["preflight_gate0_intent_artifacts_incomplete"],
        }
    intents = {
        name: item.get("payload", {}) if isinstance(item, Mapping) else {}
        for name, item in artifacts.items()
    }
    prepared = request.get("prepared_evidence")
    if not isinstance(prepared, Mapping):
        prepared = {}
        reasons.append("preflight_prepared_evidence_missing")
    contract_payload = contract.get("payload")
    if not isinstance(contract_payload, Mapping):
        contract_payload = {}
    source_pins = contract_payload.get("source_pins")
    runtime_pins = contract_payload.get("runtime_pins")
    fixed_workload = contract_payload.get("fixed_workload")
    source_pins = source_pins if isinstance(source_pins, Mapping) else {}
    runtime_pins = runtime_pins if isinstance(runtime_pins, Mapping) else {}
    fixed_workload = fixed_workload if isinstance(fixed_workload, Mapping) else {}

    source_intent = intents.get("source", {})
    source_receipt = prepared.get("source")
    source_receipt = source_receipt if isinstance(source_receipt, Mapping) else {}
    source_identity = request.get("source_identity")
    source_identity = source_identity if isinstance(source_identity, Mapping) else {}
    if source_intent.get("repo_sha") != source_identity.get("repo_sha") or source_intent.get(
        "repo_sha"
    ) != source_receipt.get("repo_sha"):
        reasons.append("preflight_source_intent_repo_sha_mismatch")
    if (
        source_intent.get("training_base_sha") != policy.training_base_sha
        or source_intent.get("training_base_sha") != source_identity.get("training_base_sha")
        or source_intent.get("training_base_sha") != source_receipt.get("training_base_sha")
    ):
        reasons.append("preflight_source_intent_training_base_mismatch")
    if source_intent.get("acceptance_contract_sha256") != contract.get("sha256"):
        reasons.append("preflight_source_intent_contract_hash_mismatch")

    runtime_intent = intents.get("runtime", {})
    if runtime_intent.get("miles_sha") != hardware.get("miles_sha") or runtime_intent.get(
        "miles_sha"
    ) != source_pins.get("miles_sha"):
        reasons.append("preflight_runtime_intent_miles_sha_mismatch")
    if runtime_intent.get("megatron_sha") != hardware.get("megatron_sha") or runtime_intent.get(
        "megatron_sha"
    ) != source_pins.get("megatron_sha"):
        reasons.append("preflight_runtime_intent_megatron_sha_mismatch")
    if runtime_intent.get("runtime_pins") != dict(runtime_pins):
        reasons.append("preflight_runtime_intent_pins_mismatch")
    runtime_receipt = prepared.get("runtime")
    if not isinstance(runtime_receipt, Mapping) or _integer(runtime_receipt.get("returncode")) != 0:
        reasons.append("preflight_runtime_receipt_not_successful")
        runtime_receipt = {}

    data_intent = intents.get("data", {})
    data_receipt = prepared.get("data")
    data_receipt = data_receipt if isinstance(data_receipt, Mapping) else {}
    if data_intent.get("train_sha256") != data_receipt.get("sha256") or data_intent.get(
        "train_sha256"
    ) != fixed_workload.get("dataset_sha256"):
        reasons.append("preflight_data_intent_train_hash_mismatch")
    if data_intent.get("row_count") != data_receipt.get("row_count") or data_intent.get(
        "row_count"
    ) != fixed_workload.get("dataset_rows"):
        reasons.append("preflight_data_intent_row_count_mismatch")
    if data_intent.get("manifest_sha256") != data_receipt.get("manifest_sha256") or data_intent.get(
        "manifest_sha256"
    ) != fixed_workload.get("dataset_manifest_sha256"):
        reasons.append("preflight_data_intent_manifest_hash_mismatch")

    checkpoint_intent = intents.get("checkpoint", {})
    checkpoint_receipt = prepared.get("checkpoint")
    checkpoint_receipt = checkpoint_receipt if isinstance(checkpoint_receipt, Mapping) else {}
    if checkpoint_intent.get("root") != checkpoint_receipt.get("root"):
        reasons.append("preflight_checkpoint_intent_root_mismatch")
    if checkpoint_intent.get("layout") != checkpoint_receipt.get("layout"):
        reasons.append("preflight_checkpoint_intent_layout_mismatch")
    if checkpoint_intent.get("hf_model") != runtime_pins.get("hf_model"):
        reasons.append("preflight_checkpoint_intent_model_mismatch")
    if checkpoint_intent.get("hf_revision") != runtime_pins.get("hf_revision"):
        reasons.append("preflight_checkpoint_intent_revision_mismatch")
    setup_evidence = prepared.get("setup")
    setup_evidence = setup_evidence if isinstance(setup_evidence, Mapping) else {}
    reasons.extend(
        _setup_evidence_reasons(
            setup_evidence,
            runtime_receipt=runtime_receipt,
            checkpoint_receipt=checkpoint_receipt,
            runtime_pins=runtime_pins,
        )
    )
    return {
        "passed": not reasons,
        "reasons": sorted(set(reasons)),
        "contract_sha256": contract.get("sha256"),
        "intent_artifact_sha256": {
            name: item.get("sha256") if isinstance(item, Mapping) else None
            for name, item in artifacts.items()
        },
    }


def _setup_evidence_reasons(
    evidence: Mapping[str, Any],
    *,
    runtime_receipt: Mapping[str, Any],
    checkpoint_receipt: Mapping[str, Any],
    runtime_pins: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    attestation = evidence.get("attestation")
    attestation = attestation if isinstance(attestation, Mapping) else {}
    if (
        set(attestation) != _SETUP_ATTESTATION_FIELDS
        or attestation.get("schema") != "w8-h100-setup-attestation/v1"
    ):
        reasons.append("preflight_setup_attestation_schema_invalid")
    if _parse_time(attestation.get("created_at_utc")) is None:
        reasons.append("preflight_setup_attestation_timestamp_invalid")
    expected_attestation = {
        "hf_model": runtime_pins.get("hf_model"),
        "hf_revision": runtime_pins.get("hf_revision"),
        "container_image_reference": runtime_pins.get("container_image"),
        "container_platform": runtime_pins.get("container_platform"),
    }
    if any(attestation.get(field) != value for field, value in expected_attestation.items()):
        reasons.append("preflight_setup_attestation_runtime_pin_mismatch")
    image_reference = str(attestation.get("container_image_reference") or "")
    image_digest = str(attestation.get("container_image_digest") or "")
    image_id = str(attestation.get("container_image_id") or "")
    if (
        re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest) is None
        or not image_reference.endswith(f"@{image_digest}")
        or re.fullmatch(r"sha256:[0-9a-f]{64}", image_id) is None
    ):
        reasons.append("preflight_setup_container_identity_invalid")
    marker_hash = evidence.get("hf_revision_marker_sha256")
    marker_content = evidence.get("hf_revision_marker_content")
    if (
        not _valid_sha256(marker_hash)
        or marker_hash != attestation.get("hf_revision_marker_sha256")
        or marker_content != attestation.get("hf_revision")
    ):
        reasons.append("preflight_setup_hf_revision_marker_mismatch")
    inspection_hash = evidence.get("container_inspection_sha256")
    inspection = evidence.get("container_inspection")
    if (
        not _valid_sha256(inspection_hash)
        or inspection_hash != attestation.get("container_inspection_sha256")
        or not isinstance(inspection, list)
        or len(inspection) != 1
        or not isinstance(inspection[0], Mapping)
    ):
        reasons.append("preflight_setup_container_inspection_invalid")
    else:
        inspection_record = inspection[0]
        if (
            inspection_record.get("Id") != image_id
            or inspection_record.get("Os") != "linux"
            or inspection_record.get("Architecture") != "amd64"
            or not isinstance(inspection_record.get("RepoDigests"), list)
            or image_reference not in inspection_record.get("RepoDigests", [])
        ):
            reasons.append("preflight_setup_container_inspection_mismatch")
    attestation_hash = evidence.get("attestation_sha256")
    if not _valid_sha256(attestation_hash):
        reasons.append("preflight_setup_attestation_hash_invalid")
    for label, receipt in (
        ("runtime", runtime_receipt),
        ("checkpoint", checkpoint_receipt),
    ):
        if (
            receipt.get("setup_attestation_sha256") != attestation_hash
            or receipt.get("hf_model") != attestation.get("hf_model")
            or receipt.get("hf_revision") != attestation.get("hf_revision")
            or receipt.get("hf_revision_marker_sha256") != marker_hash
            or receipt.get("container_image_reference") != image_reference
            or receipt.get("container_image_digest") != image_digest
            or receipt.get("container_platform") != attestation.get("container_platform")
            or receipt.get("container_image_id") != image_id
            or receipt.get("container_inspection_sha256") != inspection_hash
        ):
            reasons.append(f"preflight_setup_{label}_receipt_mismatch")
    if checkpoint_receipt.get("hf_checkpoint_path") != attestation.get("hf_checkpoint_path"):
        reasons.append("preflight_setup_checkpoint_path_mismatch")
    return reasons


def evaluate_preflight(
    *,
    contract_path: str | Path,
    hardware_path: str | Path,
    budget_path: str | Path,
    request_path: str | Path | None = None,
    gate0_permit_path: str | Path | None = None,
    gate0_public_key_path: str | Path | None = None,
    launch_receipt_path: str | Path | None = None,
    booking_request_path: str | Path | None = None,
    provider_output_path: str | Path | None = None,
    security: SentrySecurity | None = None,
    policy: SentryPolicy | None = None,
    command: str | None = None,
) -> dict[str, Any]:
    policy = policy or SentryPolicy()
    contract = _validate_contract(contract_path, policy)
    hardware = _validate_hardware(hardware_path, policy)
    budget = _validate_budget(budget_path, hardware, policy)
    request = _validate_preflight_request(
        request_path,
        hardware_path=hardware_path,
        budget_path=budget_path,
        hardware=hardware,
        policy=policy,
    )
    gate0 = _validate_gate0_chain(
        permit_path=gate0_permit_path,
        public_key_path=gate0_public_key_path,
        launch_receipt_path=launch_receipt_path,
        booking_request_path=booking_request_path,
        provider_output_path=provider_output_path,
        security=security,
        policy=policy,
    )
    intent = _reconcile_preflight_intent(
        gate0=gate0,
        contract=contract,
        request=request,
        hardware=hardware,
        policy=policy,
    )
    invalid = [
        *contract["reasons"],
        *hardware["reasons"],
        *budget["invalid_reasons"],
        *request["reasons"],
        *gate0["reasons"],
        *intent["reasons"],
    ]
    if invalid:
        decision, reasons = Decision.INVALID, invalid
    elif not budget["within_budget"]:
        decision, reasons = Decision.REJECTED, ["budget_limit_exceeded"]
    else:
        decision, reasons = Decision.PROMOTABLE, []
    result = _envelope(Stage.PREFLIGHT, decision, reasons, policy)
    result["checks"] = {
        "contract": contract,
        "hardware": hardware,
        "budget": budget,
        "request": request,
        "gate0": gate0,
        "intent": intent,
    }
    result["context"] = {
        "contract_id": policy.contract_id,
        "acceptance_contract_sha256": contract.get("sha256"),
        "claim_boundary": contract.get("claim_boundary"),
        "hardware": hardware,
        "source_identity": request.get("source_identity"),
        "gate0": gate0,
    }
    _apply_request_binding(result, request)
    inputs: list[tuple[str, str | Path]] = [
        ("contract", contract_path),
        ("hardware", hardware_path),
        ("budget", budget_path),
    ]
    if request_path is not None:
        inputs.append(("request", request_path))
    for role, path in (
        ("gate0_permit", gate0_permit_path),
        ("gate0_public_key", gate0_public_key_path),
        ("gate0_launch_receipt", launch_receipt_path),
        ("gate0_booking_request", booking_request_path),
        ("gate0_provider_output", provider_output_path),
    ):
        if path is not None:
            inputs.append((role, path))
    inputs.extend(_request_provenance_inputs(request))
    inputs.extend(
        (f"gate0_intent:{name}", item["path"])
        for name, item in sorted((gate0.get("intent_artifacts") or {}).items())
        if isinstance(item, dict) and item.get("path")
    )
    return _finish(
        result,
        Stage.PREFLIGHT,
        inputs,
        command,
        security,
    )


def evaluate_screen(
    *,
    preflight_decision_path: str | Path,
    control_path: str | Path,
    candidate_path: str | Path,
    request_path: str | Path | None = None,
    security: SentrySecurity | None = None,
    policy: SentryPolicy | None = None,
    command: str | None = None,
) -> dict[str, Any]:
    policy = policy or SentryPolicy()
    prior = _validate_prior(preflight_decision_path, Stage.PREFLIGHT, security)
    inputs = [
        ("preflight_decision", preflight_decision_path),
        ("control:A1", _trial_root(control_path)),
        ("candidate:B1", _trial_root(candidate_path)),
    ]
    if request_path is not None:
        inputs.append(("request", request_path))
    prior_context = prior.get("payload", {}).get("context", {})
    request = _validate_screen_request(
        request_path,
        control_path=control_path,
        candidate_path=candidate_path,
        expected_source=prior_context.get("source_identity"),
        expected_gate0=prior_context.get("gate0"),
        evaluation_time=_security_now(security.now if security is not None else None),
        policy=policy,
    )
    inputs.extend(_request_provenance_inputs(request))
    invalid = [
        *([] if prior["passed"] else prior["reasons"]),
        *request["reasons"],
    ]
    if invalid:
        result = _envelope(Stage.SCREEN, Decision.INVALID, invalid, policy)
        result["prior_stage"] = prior
        result["request_validation"] = request
        _apply_request_binding(result, request)
        return _finish(result, Stage.SCREEN, inputs, command, security)
    hardware = prior["payload"]["context"]["hardware"]
    pair = _evaluate_pair("T1-P1", control_path, candidate_path, hardware, policy, False)
    if not pair["valid"]:
        decision, reasons = Decision.INVALID, pair["reasons"]
    elif baseline_reasons := _control_baseline_reasons(pair, policy):
        decision, reasons = Decision.INVALID, baseline_reasons
    else:
        ratios = pair["aggregate_run_pair_ratios"]
        below = [
            metric
            for metric, value in (
                ("estimated_mfu", ratios["estimated_active_model_equivalent_mfu_ratio"]),
                ("actor_throughput", ratios["actor_throughput_ratio"]),
            )
            if value < policy.screen_minimum_ratio
        ]
        if below:
            decision = Decision.REJECTED
            reasons = [f"screen_{metric}_ratio_below_0_98" for metric in below]
        else:
            decision, reasons = Decision.PROMOTABLE, []
    result = _envelope(Stage.SCREEN, decision, reasons, policy)
    result["prior_stage"] = prior
    result["request_validation"] = request
    result["pair"] = pair
    result["screen_rule"] = {
        "aggregate_process_pair_only": True,
        "matched_observations": policy.matched_observations,
        "minimum_ratio": policy.screen_minimum_ratio,
        "three_percent_required": False,
    }
    result["context"] = prior["payload"]["context"]
    _apply_request_binding(result, request)
    return _finish(result, Stage.SCREEN, inputs, command, security)


def evaluate_promotion(
    *,
    screen_decision_path: str | Path,
    control_paths: Sequence[str | Path],
    candidate_paths: Sequence[str | Path],
    security: SentrySecurity | None = None,
    policy: SentryPolicy | None = None,
    command: str | None = None,
) -> dict[str, Any]:
    policy = policy or SentryPolicy()
    prior = _validate_prior(screen_decision_path, Stage.SCREEN, security)
    inputs = [("screen_decision", screen_decision_path)]
    inputs.extend(
        (f"control:A{index}", _trial_root(path)) for index, path in enumerate(control_paths, 1)
    )
    inputs.extend(
        (f"candidate:B{index}", _trial_root(path)) for index, path in enumerate(candidate_paths, 1)
    )
    if not prior["passed"]:
        result = _envelope(Stage.PROMOTION, Decision.INVALID, prior["reasons"], policy)
        result["prior_stage"] = prior
        return _finish(result, Stage.PROMOTION, inputs, command, security)
    count_ok = len(control_paths) == 2 and len(candidate_paths) == 2
    inherited_ok = (
        count_ok
        and _prior_input_matches(prior["payload"], "control:A1", control_paths[0])
        and _prior_input_matches(prior["payload"], "candidate:B1", candidate_paths[0])
    )
    if not count_ok or not inherited_ok:
        reasons = ["promotion_requires_exact_T1_A1_B1_A2_B2_inputs"]
        result = _envelope(Stage.PROMOTION, Decision.INVALID, reasons, policy)
        result["prior_stage"] = prior
        return _finish(result, Stage.PROMOTION, inputs, command, security)
    runner_evidence = _validate_promotion_runner_evidence(
        screen_decision_path=screen_decision_path,
        screen_payload=prior["payload"],
        control_paths=control_paths,
        candidate_paths=candidate_paths,
    )
    inputs.extend(runner_evidence["inputs"])
    hardware = prior["payload"]["context"]["hardware"]
    pairs = [
        _evaluate_pair(f"T1-P{index}", control, candidate, hardware, policy, True)
        for index, (control, candidate) in enumerate(zip(control_paths, candidate_paths), 1)
    ]
    invalid = [
        *runner_evidence["reasons"],
        *(reason for pair in pairs if not pair["valid"] for reason in pair["reasons"]),
    ]
    if not invalid:
        invalid.extend(
            reason for pair in pairs for reason in _control_baseline_reasons(pair, policy)
        )
    failures: list[str] = []
    if not invalid:
        for pair in pairs:
            ratios = pair["aggregate_run_pair_ratios"]
            if (
                ratios["estimated_active_model_equivalent_mfu_ratio"]
                < policy.promotion_minimum_ratio
            ):
                failures.append(f"{pair['pair_id']}_estimated_mfu_ratio_below_1_03")
            if ratios["actor_throughput_ratio"] < policy.promotion_minimum_ratio:
                failures.append(f"{pair['pair_id']}_actor_throughput_ratio_below_1_03")
            if (
                pair["candidate_absolute"]["estimated_active_model_equivalent_mfu_percent"]
                < policy.historical_mfu_percent
            ):
                failures.append(f"{pair['pair_id']}_candidate_below_historical_mfu_hurdle")
            if pair["candidate_absolute"]["actor_tok_s"] < policy.historical_actor_tok_s:
                failures.append(f"{pair['pair_id']}_candidate_below_historical_throughput_hurdle")
    if invalid:
        decision, reasons = Decision.INVALID, invalid
    elif failures:
        decision, reasons = Decision.NO_WIN, failures
    else:
        decision, reasons = Decision.PROMOTABLE, []
    result = _envelope(Stage.PROMOTION, decision, reasons, policy)
    result["prior_stage"] = prior
    result["runner_evidence"] = {
        key: value for key, value in runner_evidence.items() if key != "inputs"
    }
    result["pairs"] = pairs
    result["promotion_rule"] = {
        "independent_process_pair_gate": True,
        "minimum_ratio_each_pair": policy.promotion_minimum_ratio,
        "preserved_observations_each_pair": policy.matched_observations,
        "complete_cycle_diagnostic_observations_each_pair": policy.complete_cycle_observations,
        "complete_block_bootstrap_is_diagnostic_only": True,
        "final_confidence_claim_allowed": False,
    }
    result["context"] = prior["payload"]["context"]
    return _finish(result, Stage.PROMOTION, inputs, command, security)


def evaluate_confirmation(
    *,
    promotion_decision_path: str | Path,
    control_paths: Sequence[str | Path],
    candidate_paths: Sequence[str | Path],
    request_path: str | Path | None = None,
    security: SentrySecurity | None = None,
    policy: SentryPolicy | None = None,
    command: str | None = None,
) -> dict[str, Any]:
    policy = policy or SentryPolicy()
    prior = _validate_prior(promotion_decision_path, Stage.PROMOTION, security)
    inputs = [("promotion_decision", promotion_decision_path)]
    inputs.extend(
        (f"control:A{index}", _trial_root(path)) for index, path in enumerate(control_paths, 1)
    )
    inputs.extend(
        (f"candidate:B{index}", _trial_root(path)) for index, path in enumerate(candidate_paths, 1)
    )
    if request_path is not None:
        inputs.append(("request", request_path))
    request = _validate_confirmation_request(
        request_path,
        promotion_decision_path=promotion_decision_path,
        control_paths=control_paths,
        candidate_paths=candidate_paths,
        expected_source=prior.get("payload", {}).get("context", {}).get("source_identity"),
        policy=policy,
        security=security,
    )
    inputs.extend(_request_provenance_inputs(request))
    invalid_prior = [
        *([] if prior["passed"] else prior["reasons"]),
        *request["reasons"],
    ]
    if invalid_prior:
        result = _envelope(Stage.CONFIRMATION, Decision.INVALID, invalid_prior, policy)
        result["prior_stage"] = prior
        result["request_validation"] = request
        _apply_request_binding(result, request)
        return _finish(result, Stage.CONFIRMATION, inputs, command, security)
    count_ok = len(control_paths) == len(candidate_paths) == policy.confirmation_min_pairs
    inherited_ok = count_ok and all(
        _prior_input_matches(prior["payload"], f"control:A{index}", control_paths[index - 1])
        and _prior_input_matches(
            prior["payload"], f"candidate:B{index}", candidate_paths[index - 1]
        )
        for index in (1, 2)
    )
    if not count_ok or not inherited_ok:
        result = _envelope(
            Stage.CONFIRMATION,
            Decision.INVALID,
            ["confirmation_requires_exactly_four_pairs_and_preserved_T1_inputs"],
            policy,
        )
        result["prior_stage"] = prior
        result["request_validation"] = request
        _apply_request_binding(result, request)
        return _finish(result, Stage.CONFIRMATION, inputs, command, security)
    hardware = prior["payload"]["context"]["hardware"]
    pairs = [
        _evaluate_pair(f"P{index}", control, candidate, hardware, policy, False)
        for index, (control, candidate) in enumerate(zip(control_paths, candidate_paths), 1)
    ]
    invalid = [reason for pair in pairs if not pair["valid"] for reason in pair["reasons"]]
    tranches = [pair.get("tranche_id") for pair in pairs]
    if tranches != ["T1", "T1", "T2", "T2"]:
        invalid.append("confirmation_requires_exactly_two_T1_then_two_T2_pairs")
    stats = _confirmation_statistics(pairs, policy) if not invalid else {}
    if invalid:
        decision, reasons = Decision.INVALID, invalid
    else:
        hurdle_failures = [
            reason for pair in pairs for reason in _candidate_hurdle_reasons(pair, policy)
        ]
        point_failures = [
            metric
            for metric in ("estimated_mfu", "actor_throughput")
            if stats[metric]["geometric_mean_ratio"] < policy.promotion_minimum_ratio
        ]
        confidence_failures = [
            metric
            for metric in ("estimated_mfu", "actor_throughput")
            if stats[metric]["one_sided_95_percent_lower_log_bound"] <= 0.0
        ]
        if hurdle_failures:
            decision, reasons = Decision.NO_WIN, hurdle_failures
        elif point_failures:
            decision = Decision.NO_WIN
            reasons = [
                f"confirmation_{metric}_geometric_mean_below_1_03" for metric in point_failures
            ]
        elif confidence_failures:
            decision = Decision.INCONCLUSIVE
            reasons = [
                f"confirmation_{metric}_lower_log_bound_not_positive"
                for metric in confidence_failures
            ]
        else:
            decision, reasons = Decision.PROMOTABLE, []
    result = _envelope(Stage.CONFIRMATION, decision, reasons, policy)
    result["prior_stage"] = prior
    result["request_validation"] = request
    result["pairs"] = pairs
    result["confirmation_statistics"] = stats
    result["confirmation_rule"] = {
        "independent_unit": "process_pair",
        "one_aggregate_log_ratio_per_process_pair": True,
        "step_or_block_pseudoreplicates_allowed": False,
        "minimum_pairs": policy.confirmation_min_pairs,
    }
    result["context"] = {
        **prior["payload"]["context"],
        "t2_authorization": request.get("t2_authorization"),
    }
    _apply_request_binding(result, request)
    return _finish(result, Stage.CONFIRMATION, inputs, command, security)


def evaluate_grpo(
    *,
    confirmation_decision_path: str | Path,
    grpo_path: str | Path,
    security: SentrySecurity | None = None,
    policy: SentryPolicy | None = None,
    command: str | None = None,
) -> dict[str, Any]:
    policy = policy or SentryPolicy()
    prior = _validate_prior(confirmation_decision_path, Stage.CONFIRMATION, security)
    inputs = [
        ("confirmation_decision", confirmation_decision_path),
        ("grpo_artifact", Path(grpo_path).expanduser().resolve()),
    ]
    if not prior["passed"]:
        result = _envelope(Stage.GRPO, Decision.INVALID, prior["reasons"], policy)
        result["prior_stage"] = prior
        return _finish(result, Stage.GRPO, inputs, command, security)
    hardware = prior["payload"]["context"]["hardware"]
    evidence = _evaluate_grpo_artifact(grpo_path, hardware, policy)
    decision = Decision.PROMOTABLE if evidence["passed"] else Decision.INVALID
    reasons = [] if evidence["passed"] else evidence["reasons"]
    result = _envelope(Stage.GRPO, decision, reasons, policy)
    result["prior_stage"] = prior
    result["grpo_evidence"] = evidence
    result["context"] = prior["payload"]["context"]
    return _finish(result, Stage.GRPO, inputs, command, security)


def evaluate_final(
    *,
    confirmation_decision_path: str | Path,
    grpo_decision_path: str | Path,
    audit_path: str | Path,
    contract_path: str | Path,
    termination_receipt_path: str | Path,
    security: SentrySecurity | None = None,
    policy: SentryPolicy | None = None,
    command: str | None = None,
) -> dict[str, Any]:
    policy = policy or SentryPolicy()
    confirmation = _validate_prior(confirmation_decision_path, Stage.CONFIRMATION, security)
    grpo = _validate_prior(grpo_decision_path, Stage.GRPO, security)
    contract = _validate_contract(contract_path, policy)
    confirmation_context = (confirmation.get("payload") or {}).get("context", {})
    termination = _validate_termination_receipt(
        termination_receipt_path,
        expected_gate0=confirmation_context.get("gate0"),
    )
    audit = _validate_audit(
        audit_path,
        contract_path=contract_path,
        confirmation_decision_path=confirmation_decision_path,
        grpo_decision_path=grpo_decision_path,
        termination_receipt_path=termination_receipt_path,
        contract=contract,
        security=security,
    )
    inputs: list[tuple[str, str | Path]] = [
        ("confirmation_decision", confirmation_decision_path),
        ("grpo_decision", grpo_decision_path),
        ("audit", audit_path),
        ("contract", contract_path),
        ("termination_receipt", termination_receipt_path),
    ]
    inputs.extend((item["role"], item["path"]) for item in termination.get("verified_inputs", []))
    inputs.extend((item["role"], item["path"]) for item in audit.get("verified_inputs", []))
    chain_reasons: list[str] = []
    if grpo["passed"] and not _provenance_input_matches_exact(
        grpo["payload"],
        "confirmation_decision",
        confirmation_decision_path,
    ):
        chain_reasons.append("grpo_confirmation_chain_mismatch")
    contract_sha256 = contract.get("sha256")
    for label, validated in (("confirmation", confirmation), ("grpo", grpo)):
        payload = validated.get("payload") or {}
        context = payload.get("context") or {}
        if (
            payload.get("acceptance_contract_sha256") != contract_sha256
            or context.get("acceptance_contract_sha256") != contract_sha256
        ):
            chain_reasons.append(f"final_{label}_acceptance_contract_hash_mismatch")
    reasons = [
        *([] if confirmation["passed"] else confirmation["reasons"]),
        *([] if grpo["passed"] else grpo["reasons"]),
        *chain_reasons,
        *contract["reasons"],
        *termination["reasons"],
        *audit["reasons"],
    ]
    decision = Decision.VERIFIED if not reasons else Decision.INVALID
    result = _envelope(Stage.FINAL, decision, reasons, policy)
    result["confirmation"] = confirmation
    result["grpo"] = grpo
    result["audit"] = audit
    result["termination"] = termination
    result["context"] = (confirmation.get("payload") or {}).get("context", {})
    result["acceptance_contract_sha256"] = contract_sha256
    return _finish(result, Stage.FINAL, inputs, command, security)


def evaluate_stage(
    stage: str | Stage,
    *,
    contract_path: str | Path | None = None,
    hardware_path: str | Path | None = None,
    budget_path: str | Path | None = None,
    preflight_decision_path: str | Path | None = None,
    screen_decision_path: str | Path | None = None,
    promotion_decision_path: str | Path | None = None,
    confirmation_decision_path: str | Path | None = None,
    grpo_decision_path: str | Path | None = None,
    control_paths: Sequence[str | Path] = (),
    candidate_paths: Sequence[str | Path] = (),
    grpo_path: str | Path | None = None,
    audit_path: str | Path | None = None,
    termination_receipt_path: str | Path | None = None,
    request_path: str | Path | None = None,
    gate0_permit_path: str | Path | None = None,
    gate0_public_key_path: str | Path | None = None,
    launch_receipt_path: str | Path | None = None,
    booking_request_path: str | Path | None = None,
    provider_output_path: str | Path | None = None,
    security: SentrySecurity | None = None,
    policy: SentryPolicy | None = None,
    command: str | None = None,
) -> dict[str, Any]:
    policy = policy or SentryPolicy()
    resolved = stage if isinstance(stage, Stage) else Stage(stage)
    kwargs: dict[str, Any]
    missing: list[str] = []
    if resolved is Stage.PREFLIGHT:
        for name, value in (
            ("contract", contract_path),
            ("hardware", hardware_path),
            ("budget", budget_path),
            ("request", request_path),
            ("gate0_permit", gate0_permit_path),
            ("gate0_public_key", gate0_public_key_path),
            ("launch_receipt", launch_receipt_path),
            ("booking_request", booking_request_path),
            ("provider_output", provider_output_path),
        ):
            if value is None:
                missing.append(f"{name}_missing")
        if not missing:
            return evaluate_preflight(
                contract_path=contract_path,  # type: ignore[arg-type]
                hardware_path=hardware_path,  # type: ignore[arg-type]
                budget_path=budget_path,  # type: ignore[arg-type]
                request_path=request_path,
                gate0_permit_path=gate0_permit_path,
                gate0_public_key_path=gate0_public_key_path,
                launch_receipt_path=launch_receipt_path,
                booking_request_path=booking_request_path,
                provider_output_path=provider_output_path,
                security=security,
                policy=policy,
                command=command,
            )
    elif resolved is Stage.SCREEN:
        if preflight_decision_path is None:
            missing.append("preflight_decision_missing")
        if request_path is None:
            missing.append("request_missing")
        if len(control_paths) != 1 or len(candidate_paths) != 1:
            missing.append("screen_requires_exactly_A1_and_B1")
        if not missing:
            return evaluate_screen(
                preflight_decision_path=preflight_decision_path,  # type: ignore[arg-type]
                control_path=control_paths[0],
                candidate_path=candidate_paths[0],
                request_path=request_path,
                security=security,
                policy=policy,
                command=command,
            )
    elif resolved is Stage.PROMOTION:
        if screen_decision_path is None:
            missing.append("screen_decision_missing")
        if not missing:
            return evaluate_promotion(
                screen_decision_path=screen_decision_path,  # type: ignore[arg-type]
                control_paths=control_paths,
                candidate_paths=candidate_paths,
                security=security,
                policy=policy,
                command=command,
            )
    elif resolved is Stage.CONFIRMATION:
        if promotion_decision_path is None:
            missing.append("promotion_decision_missing")
        if request_path is None:
            missing.append("request_missing")
        if not missing:
            return evaluate_confirmation(
                promotion_decision_path=promotion_decision_path,  # type: ignore[arg-type]
                control_paths=control_paths,
                candidate_paths=candidate_paths,
                request_path=request_path,
                security=security,
                policy=policy,
                command=command,
            )
    elif resolved is Stage.GRPO:
        if confirmation_decision_path is None:
            missing.append("confirmation_decision_missing")
        if grpo_path is None:
            missing.append("grpo_artifact_missing")
        if not missing:
            return evaluate_grpo(
                confirmation_decision_path=confirmation_decision_path,  # type: ignore[arg-type]
                grpo_path=grpo_path,  # type: ignore[arg-type]
                security=security,
                policy=policy,
                command=command,
            )
    else:
        for name, value in (
            ("confirmation_decision", confirmation_decision_path),
            ("grpo_decision", grpo_decision_path),
            ("audit", audit_path),
            ("contract", contract_path),
            ("termination_receipt", termination_receipt_path),
        ):
            if value is None:
                missing.append(f"{name}_missing")
        if not missing:
            return evaluate_final(
                confirmation_decision_path=confirmation_decision_path,  # type: ignore[arg-type]
                grpo_decision_path=grpo_decision_path,  # type: ignore[arg-type]
                audit_path=audit_path,  # type: ignore[arg-type]
                contract_path=contract_path,  # type: ignore[arg-type]
                termination_receipt_path=termination_receipt_path,  # type: ignore[arg-type]
                security=security,
                policy=policy,
                command=command,
            )
    kwargs = {"missing": missing}
    result = _envelope(resolved, Decision.INVALID, missing, policy)
    result.update(kwargs)
    return _finish(result, resolved, [], command, security)


def _evaluate_pair(
    pair_id: str,
    control_path: str | Path,
    candidate_path: str | Path,
    hardware: dict[str, Any],
    policy: SentryPolicy,
    require_cycle_diagnostic: bool,
) -> dict[str, Any]:
    control = _load_trial(control_path, hardware, policy)
    candidate = _load_trial(candidate_path, hardware, policy)
    reasons = [*control.reasons, *candidate.reasons]
    if control.valid and candidate.valid:
        reasons.extend(_configuration_reasons(control, candidate, policy))
    matched: list[dict[str, Any]] = []
    if not reasons:
        try:
            matched = _match_observations(control.vectors, candidate.vectors)
        except ValueError as exc:
            reasons.append(str(exc))
    diagnostic = _cycle_diagnostic(matched, policy) if matched else {"available": False}
    if (
        require_cycle_diagnostic
        and diagnostic.get("observation_count") != policy.complete_cycle_observations
    ):
        reasons.append("complete_cycle_diagnostic_observation_count_mismatch")
    if reasons:
        return {
            "pair_id": pair_id,
            "valid": False,
            "reasons": sorted(set(reasons)),
            "control": _trial_public(control),
            "candidate": _trial_public(candidate),
            "preserved_matched_observations": len(matched),
            "complete_cycle_diagnostic": diagnostic,
        }
    aggregate = _aggregate_pair(matched, policy)
    tranche_control = str(control.receipt.get("tranche_id") or "")
    tranche_candidate = str(candidate.receipt.get("tranche_id") or "")
    if tranche_control != tranche_candidate or not tranche_control:
        return {
            "pair_id": pair_id,
            "valid": False,
            "reasons": ["process_pair_tranche_mismatch_or_missing"],
            "control": _trial_public(control),
            "candidate": _trial_public(candidate),
        }
    return {
        "pair_id": pair_id,
        "tranche_id": tranche_control,
        "valid": True,
        "reasons": [],
        "control": _trial_public(control),
        "candidate": _trial_public(candidate),
        "preserved_matched_observations": len(matched),
        "raw_matched_observations": matched,
        "aggregate_run_pair_ratios": {
            "estimated_active_model_equivalent_mfu_ratio": aggregate["mfu_ratio"],
            "actor_throughput_ratio": aggregate["throughput_ratio"],
        },
        "candidate_absolute": {
            "estimated_active_model_equivalent_mfu_percent": aggregate["candidate_mfu_percent"],
            "actor_tok_s": aggregate["candidate_tok_s"],
        },
        "control_absolute": {
            "estimated_active_model_equivalent_mfu_percent": aggregate["control_mfu_percent"],
            "actor_tok_s": aggregate["control_tok_s"],
        },
        "complete_cycle_diagnostic": diagnostic,
    }


def _control_baseline_reasons(pair: dict[str, Any], policy: SentryPolicy) -> list[str]:
    control = pair["control_absolute"]
    reasons: list[str] = []
    checks = (
        (
            "estimated_mfu",
            float(control["estimated_active_model_equivalent_mfu_percent"]),
            policy.historical_reference_mfu_percent,
        ),
        (
            "actor_throughput",
            float(control["actor_tok_s"]),
            policy.historical_reference_actor_tok_s,
        ),
    )
    for name, actual, historical in checks:
        relative_delta = abs(actual / historical - 1.0)
        if relative_delta > policy.control_baseline_relative_tolerance:
            reasons.append(f"{pair['pair_id']}_control_{name}_outside_historical_5pct")
    return reasons


def _candidate_hurdle_reasons(pair: dict[str, Any], policy: SentryPolicy) -> list[str]:
    candidate = pair["candidate_absolute"]
    reasons: list[str] = []
    if (
        float(candidate["estimated_active_model_equivalent_mfu_percent"])
        < policy.historical_mfu_percent
    ):
        reasons.append(f"{pair['pair_id']}_candidate_below_historical_mfu_hurdle")
    if float(candidate["actor_tok_s"]) < policy.historical_actor_tok_s:
        reasons.append(f"{pair['pair_id']}_candidate_below_historical_throughput_hurdle")
    return reasons


def _load_trial(path: str | Path, hardware: dict[str, Any], policy: SentryPolicy) -> _Trial:
    summary_path = _resolve_summary(path)
    root = summary_path.parent
    summary = read_json(summary_path)
    log_path = _find_component(root, summary.get("log_path"), "run.log")
    receipt_path = _find_component(root, summary.get("receipt_path"), "run_receipt.txt")
    receipt = read_key_value(receipt_path)
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    peak = _positive(summary.get("peak_tflops_per_gpu")) or policy.bf16_peak_tflops_per_gpu
    canonical = summarize_miles_mfu_trial(
        log_path=log_path,
        receipt_path=receipt_path,
        round_number=_integer(summary.get("round")) or 0,
        name=str(summary.get("name") or root.name),
        precision=str(summary.get("precision") or "bf16"),
        peak_tflops_per_gpu=peak,
    )
    events = tuple(parse_miles_metric_events(log_path))
    reasons: list[str] = []
    if any(not _equivalent(summary.get(field), canonical.get(field)) for field in _SUMMARY_FIELDS):
        reasons.append("canonical_trial_summary_raw_parser_mismatch")
    if str(receipt.get("status") or "") != "success" or _integer(receipt.get("ray_status")) != 0:
        reasons.append("trial_implementation_or_runtime_failure")
    if _FATAL_RE.search(log_text):
        reasons.append("trial_failure_trace_present")
    if not _finite_training(canonical):
        reasons.append("trial_non_finite_or_missing_training_metric")
    if str(canonical.get("precision")) != "bf16" or not math.isclose(
        peak, policy.bf16_peak_tflops_per_gpu
    ):
        reasons.append("frozen_estimated_mfu_definition_mismatch")
    try:
        vectors = tuple(_raw_vectors(events, policy))
    except ValueError as exc:
        vectors = ()
        reasons.append(str(exc))
    timing = _timing_evidence(root, receipt, policy)
    if not timing["passed"]:
        reasons.extend(timing["reasons"])
    telemetry = _telemetry_evidence(root, receipt, log_text, policy)
    if not telemetry["passed"]:
        reasons.extend(telemetry["reasons"])
    total = _positive(hardware.get("minimum_memory_total_mib"))
    peak_vram = _positive(canonical.get("peak_vram_mib"))
    headroom = total - peak_vram if total is not None and peak_vram is not None else None
    if headroom is None or headroom < policy.min_vram_headroom_mib:
        reasons.append("trial_vram_headroom_below_minimum")
    workload = {
        "data_dir": receipt.get("data_dir"),
        "tasks_dir": receipt.get("tasks_dir"),
        "hf_checkpoint": receipt.get("hf_checkpoint"),
        "model_args_path": receipt.get("model_args_path"),
        "ref_load": receipt.get("ref_load"),
        "seq_length": receipt.get("seq_length"),
        "global_batch_size": receipt.get("global_batch_size"),
        "rollout_batch_size": receipt.get("rollout_batch_size"),
        "lora_rank": receipt.get("lora_rank"),
        "sft_rollout_shuffle": receipt.get("sft_rollout_shuffle"),
    }
    if any(value is None for value in workload.values()):
        reasons.append("fixed_workload_metadata_missing")
    return _Trial(
        summary_path=summary_path,
        root=root,
        log_path=log_path,
        receipt_path=receipt_path,
        summary=summary,
        canonical=canonical,
        receipt=receipt,
        log_text=log_text,
        events=events,
        vectors=vectors,
        telemetry=telemetry,
        timing=timing,
        workload=workload,
        valid=not reasons,
        reasons=tuple(sorted(set(reasons))),
    )


def _configuration_reasons(control: _Trial, candidate: _Trial, policy: SentryPolicy) -> list[str]:
    reasons: list[str] = []
    if control.workload != candidate.workload:
        reasons.append("fixed_workload_mismatch")
    control_config = control.canonical.get("config", {})
    candidate_config = candidate.canonical.get("config", {})
    if _without_dispatcher(control_config) != _without_dispatcher(candidate_config):
        reasons.append("candidate_changed_more_than_dispatcher")
    if str(control_config.get("moe_token_dispatcher_type")) != "flex" or not _truthy(
        control_config.get("moe_enable_deepep")
    ):
        reasons.append("control_dispatcher_contract_mismatch")
    if str(candidate_config.get("moe_token_dispatcher_type")) != "alltoall" or _truthy(
        candidate_config.get("moe_enable_deepep")
    ):
        reasons.append("candidate_dispatcher_contract_mismatch")
    fixed = {
        "seq_length": 4096,
        "global_batch_size": 32,
        "rollout_batch_size": 32,
        "micro_batch_size": 1,
    }
    for key, expected in fixed.items():
        if _integer(control_config.get(key)) != expected:
            reasons.append(f"fixed_{key}_mismatch")
    if (
        _integer(control.receipt.get("lora_rank")) != 16
        or _integer(candidate.receipt.get("lora_rank")) != 16
    ):
        reasons.append("fixed_lora_rank_mismatch")
    return reasons


def _raw_vectors(events: Sequence[dict[str, Any]], policy: SentryPolicy) -> list[dict[str, Any]]:
    perf = sorted(
        (
            event
            for event in events
            if event.get("family") == "perf"
            and all(
                key in event.get("metrics", {})
                for key in (
                    "perf/actor_train_time",
                    "perf/actor_train_tflops",
                    "perf/actor_train_tok_per_s",
                )
            )
        ),
        key=lambda event: int(event["step"]),
    )
    if len({int(event["step"]) for event in perf}) != len(perf):
        raise ValueError("duplicate_raw_perf_observations")
    measured = perf[policy.warmup_observations :]
    if len(measured) != policy.matched_observations:
        raise ValueError("expected_exactly_14_post_warmup_observations")
    vectors: list[dict[str, Any]] = []
    for measured_index, event in enumerate(measured):
        original_ordinal = measured_index + policy.warmup_observations
        actor_time = _positive(event["metrics"].get("perf/actor_train_time"))
        actor_tflops = _positive(event["metrics"].get("perf/actor_train_tflops"))
        actor_tok_s = _positive(event["metrics"].get("perf/actor_train_tok_per_s"))
        if None in (actor_time, actor_tflops, actor_tok_s):
            raise ValueError("non_finite_raw_work_observation")
        vectors.append(
            {
                "measured_index": measured_index,
                "original_ordinal": original_ordinal,
                "step": int(event["step"]),
                "actor_time_s": actor_time,
                "actor_tflops_per_gpu": actor_tflops,
                "global_actor_tok_s": actor_tok_s,
                "work_tokens": actor_time * actor_tok_s,
                "estimated_active_model_work_tflop_per_gpu": actor_time * actor_tflops,
            }
        )
    return vectors


def _match_observations(
    control: Sequence[dict[str, Any]], candidate: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    if len(control) != 14 or len(candidate) != 14:
        raise ValueError("matched_observation_count_not_14")
    matched: list[dict[str, Any]] = []
    for left, right in zip(control, candidate):
        if round(float(left["work_tokens"])) != round(float(right["work_tokens"])):
            raise ValueError("raw_token_work_vector_mismatch")
        if not math.isclose(
            float(left["estimated_active_model_work_tflop_per_gpu"]),
            float(right["estimated_active_model_work_tflop_per_gpu"]),
            rel_tol=1e-6,
            abs_tol=1e-6,
        ):
            raise ValueError("frozen_flop_work_vector_mismatch")
        matched.append({"control": left, "candidate": right})
    return matched


def _aggregate_pair(matched: Sequence[dict[str, Any]], policy: SentryPolicy) -> dict[str, float]:
    control_time = sum(float(row["control"]["actor_time_s"]) for row in matched)
    candidate_time = sum(float(row["candidate"]["actor_time_s"]) for row in matched)
    control_tokens = sum(float(row["control"]["work_tokens"]) for row in matched)
    candidate_tokens = sum(float(row["candidate"]["work_tokens"]) for row in matched)
    control_work = sum(
        float(row["control"]["estimated_active_model_work_tflop_per_gpu"]) for row in matched
    )
    candidate_work = sum(
        float(row["candidate"]["estimated_active_model_work_tflop_per_gpu"]) for row in matched
    )
    control_tok_s, candidate_tok_s = (
        control_tokens / control_time,
        candidate_tokens / candidate_time,
    )
    control_tflops, candidate_tflops = control_work / control_time, candidate_work / candidate_time
    return {
        "throughput_ratio": candidate_tok_s / control_tok_s,
        "mfu_ratio": candidate_tflops / control_tflops,
        "control_tok_s": control_tok_s,
        "control_mfu_percent": 100.0 * control_tflops / policy.bf16_peak_tflops_per_gpu,
        "candidate_tok_s": candidate_tok_s,
        "candidate_mfu_percent": 100.0 * candidate_tflops / policy.bf16_peak_tflops_per_gpu,
    }


def _cycle_diagnostic(matched: Sequence[dict[str, Any]], policy: SentryPolicy) -> dict[str, Any]:
    groups: dict[int, list[dict[str, Any]]] = {}
    for row in matched:
        ordinal = int(row["control"]["original_ordinal"])
        groups.setdefault(ordinal // policy.workload_cycle_size, []).append(row)
    blocks = [
        rows
        for block, rows in sorted(groups.items())
        if [int(row["control"]["original_ordinal"]) for row in rows]
        == list(range(block * policy.workload_cycle_size, (block + 1) * policy.workload_cycle_size))
    ]
    observation_count = sum(len(block) for block in blocks)
    if not blocks:
        return {"available": False, "observation_count": 0}
    block_rows = [[_aggregate_pair(block, policy)] for block in blocks]
    mfu_draws: list[float] = []
    throughput_draws: list[float] = []
    for indices in itertools.product(range(len(blocks)), repeat=len(blocks)):
        selected = [row for index in indices for row in blocks[index]]
        aggregate = _aggregate_pair(selected, policy)
        mfu_draws.append(aggregate["mfu_ratio"])
        throughput_draws.append(aggregate["throughput_ratio"])
    return {
        "available": True,
        "diagnostic_only": True,
        "inference_unit_for_confirmation": False,
        "observation_count": observation_count,
        "complete_block_count": len(blocks),
        "block_point_estimates": [rows[0] for rows in block_rows],
        "bootstrap_draw_count": len(mfu_draws),
        "one_sided_95_percent_lower_ratio": {
            "estimated_mfu": _lower_percentile(mfu_draws, 0.05),
            "actor_throughput": _lower_percentile(throughput_draws, 0.05),
        },
    }


def _confirmation_statistics(
    pairs: Sequence[dict[str, Any]], policy: SentryPolicy
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "sample_size": len(pairs),
        "independent_unit": "process_pair",
        "step_or_block_pseudoreplicates": False,
    }
    for output_name, ratio_name in (
        ("estimated_mfu", "estimated_active_model_equivalent_mfu_ratio"),
        ("actor_throughput", "actor_throughput_ratio"),
    ):
        ratios = [float(pair["aggregate_run_pair_ratios"][ratio_name]) for pair in pairs]
        logs = [math.log(value) for value in ratios]
        mean = statistics.fmean(logs)
        standard_deviation = statistics.stdev(logs) if len(logs) > 1 else 0.0
        critical = _one_sided_t95(len(logs) - 1)
        lower = mean - critical * standard_deviation / math.sqrt(len(logs))
        result[output_name] = {
            "process_pair_ratios": ratios,
            "process_pair_log_ratios": logs,
            "mean_log_ratio": mean,
            "geometric_mean_ratio": math.exp(mean),
            "one_sided_95_percent_t_critical": critical,
            "one_sided_95_percent_lower_log_bound": lower,
        }
    return result


def _evaluate_grpo_artifact(
    path: str | Path, hardware: dict[str, Any], policy: SentryPolicy
) -> dict[str, Any]:
    root = Path(path).expanduser().resolve()
    if root.is_file():
        root = root.parent
    try:
        receipt_path = _find_one(root, "run_receipt.txt")
        log_path = _find_one(root, "run.log")
        checkpoint_path = _find_one(root, "*.checkpoint_manifest.json")
        fingerprints_path = _find_one(root, "fingerprints.json")
        receipt = read_key_value(receipt_path)
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        checkpoint = read_json(checkpoint_path)
        fingerprints = read_json(fingerprints_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "passed": False,
            "reasons": ["grpo_evidence_missing_or_malformed"],
            "detail": str(exc),
        }
    reasons: list[str] = []
    if str(receipt.get("status") or "") != "success" or _integer(receipt.get("ray_status")) != 0:
        reasons.append("grpo_runtime_failure")
    if _FATAL_RE.search(log_text):
        reasons.append("grpo_failure_trace_present")
    lower_log = log_text.lower()
    if not (
        "successfully loaded lora adapter" in lower_log
        or "successfully loaded checkpoint" in lower_log
    ):
        reasons.append("grpo_load_evidence_missing")
    events = parse_miles_metric_events(log_path)
    grad_norms = [
        _finite(event["metrics"].get("train/grad_norm"))
        for event in events
        if event.get("family") == "step" and "train/grad_norm" in event.get("metrics", {})
    ]
    if not grad_norms or any(value is None for value in grad_norms):
        reasons.append("grpo_finite_update_evidence_missing")
    if "saving lora checkpoint" not in lower_log:
        reasons.append("grpo_save_evidence_missing")
    if "lora sync" not in lower_log:
        reasons.append("grpo_sync_evidence_missing")
    fingerprint_values = {
        name: _fingerprint_value(fingerprints.get(name))
        for name in ("pre_update", "post_update", "sglang_sync")
    }
    if (
        any(value is None for value in fingerprint_values.values())
        or fingerprint_values["pre_update"] == fingerprint_values["post_update"]
        or fingerprint_values["post_update"] != fingerprint_values["sglang_sync"]
    ):
        reasons.append("grpo_fingerprint_transition_or_sync_mismatch")
    checkpoint_validation = _validate_grpo_checkpoint_manifest(checkpoint_path, checkpoint)
    reasons.extend(checkpoint_validation["reasons"])
    timing = _timing_evidence(root, receipt, policy, required_artifact=checkpoint_path)
    if not timing["passed"]:
        reasons.extend(timing["reasons"])
    remote_summary = timing.get("remote_summary") or {}
    local_summary = timing.get("local_evidence_summary") or {}
    metric_count = _integer(remote_summary.get("metric_event_count")) or 0
    rollout_rows = _integer((local_summary.get("sample_rows_total") or {}).get("rollout")) or 0
    if metric_count <= 0 or rollout_rows <= 0:
        reasons.append("grpo_wandb_evidence_incomplete")
    telemetry = _telemetry_evidence(root, receipt, log_text, policy)
    if not telemetry["passed"]:
        reasons.extend(telemetry["reasons"])
    total = _positive(hardware.get("minimum_memory_total_mib"))
    peak = _positive(receipt.get("max_memory_used_mib"))
    headroom = total - peak if total is not None and peak is not None else None
    if headroom is None or headroom < policy.min_vram_headroom_mib:
        reasons.append("grpo_vram_headroom_below_minimum")
    return {
        "passed": not reasons,
        "reasons": sorted(set(reasons)),
        "artifact": str(root),
        "telemetry": telemetry,
        "timing": timing,
        "checkpoint": checkpoint_validation,
        "fingerprints": fingerprint_values,
        "wandb": {
            "run_id": (timing.get("identity") or {}).get("run_id"),
            "metric_event_count": metric_count,
            "rollout_rows": rollout_rows,
        },
        "vram_headroom_mib": headroom,
    }


def _validate_grpo_checkpoint_manifest(
    manifest_path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    if payload.get("schema_version") != 1:
        reasons.append("grpo_checkpoint_manifest_schema_invalid")
    root_value = payload.get("checkpoint_root")
    root = Path(str(root_value or "")).expanduser()
    if not root.is_absolute():
        root = manifest_path.parent / root
    root = root.resolve()
    if not root.is_dir():
        reasons.append("grpo_checkpoint_root_missing")
    entries = payload.get("files")
    if not isinstance(entries, list) or not entries:
        reasons.append("grpo_checkpoint_manifest_files_missing")
        entries = []
    seen: set[str] = set()
    verified: list[dict[str, Any]] = []
    for index, item in enumerate(entries):
        if not isinstance(item, dict):
            reasons.append("grpo_checkpoint_manifest_entry_invalid")
            continue
        relative_text = str(item.get("path") or "")
        relative = Path(relative_text)
        recorded_size = _integer(item.get("size_bytes"))
        recorded_hash = item.get("sha256")
        if (
            not relative_text
            or relative.is_absolute()
            or relative_text in seen
            or recorded_size is None
            or recorded_size < 0
            or not _valid_sha256(recorded_hash)
        ):
            reasons.append("grpo_checkpoint_manifest_entry_invalid")
            continue
        seen.add(relative_text)
        resolved = (root / relative).resolve()
        try:
            within_root = resolved.is_relative_to(root)
        except ValueError:
            within_root = False
        if not within_root or not resolved.is_file() or resolved.is_symlink():
            reasons.append(f"grpo_checkpoint_file_missing_or_not_regular:{index}")
            continue
        actual_size = resolved.stat().st_size
        actual_hash = _hash_file(resolved)
        if actual_size != recorded_size:
            reasons.append(f"grpo_checkpoint_file_size_mismatch:{index}")
        if actual_hash != recorded_hash:
            reasons.append(f"grpo_checkpoint_file_hash_mismatch:{index}")
        verified.append(
            {
                "path": str(resolved),
                "size_bytes": actual_size,
                "sha256": actual_hash,
            }
        )
    latest_iteration = str(payload.get("latest_iteration") or "")
    iteration_dirs = sorted(path for path in root.glob("iter_*") if path.is_dir())
    actual_latest = iteration_dirs[-1].name if iteration_dirs else ""
    if (
        re.fullmatch(r"iter_[0-9]{7}", latest_iteration) is None
        or latest_iteration != actual_latest
    ):
        reasons.append("grpo_checkpoint_latest_iteration_mismatch")
    manifest_paths = set(seen)
    selected_files: set[Path] = set()
    if iteration_dirs:
        selected_files.update(
            path
            for path in iteration_dirs[-1].rglob("*")
            if path.is_file() and not path.is_symlink()
        )
        selected_files.update(
            path for path in root.iterdir() if path.is_file() and not path.is_symlink()
        )
        rollout_dir = root / "rollout"
        if rollout_dir.is_dir():
            rollout_files = sorted(
                path for path in rollout_dir.rglob("*") if path.is_file() and not path.is_symlink()
            )
            if rollout_files:
                selected_files.add(rollout_files[-1])
    expected_manifest_paths = {path.relative_to(root).as_posix() for path in selected_files}
    if manifest_paths != expected_manifest_paths:
        reasons.append("grpo_checkpoint_manifest_real_file_set_mismatch")

    adapter_prefix = f"{latest_iteration}/adapter/"
    adapter_paths = {
        path.removeprefix(adapter_prefix)
        for path in manifest_paths
        if path.startswith(adapter_prefix)
    }
    required_native = {f"adapter_megatron_tp{rank}_pp0.pt" for rank in range(4)}
    required_training_state = {f"training_state_rank{rank}.pt" for rank in range(8)}
    native = {path for path in adapter_paths if path.startswith("adapter_megatron_")}
    training_state = {path for path in adapter_paths if path.startswith("training_state_rank")}
    hf_adapters = adapter_paths & {"adapter_model.bin", "adapter_model.safetensors"}
    if native != required_native:
        reasons.append("grpo_checkpoint_tp4_adapter_rank_set_incomplete")
    if training_state != required_training_state:
        reasons.append("grpo_checkpoint_training_state_rank_set_incomplete")
    if len(hf_adapters) != 1:
        reasons.append("grpo_checkpoint_hf_adapter_missing_or_ambiguous")
    if "adapter_config.json" not in adapter_paths:
        reasons.append("grpo_checkpoint_adapter_config_missing")
    expected_adapter_paths = (
        required_native | required_training_state | {"adapter_config.json"} | hf_adapters
    )
    if adapter_paths != expected_adapter_paths:
        reasons.append("grpo_checkpoint_adapter_file_set_unexpected")
    return {
        "passed": not reasons,
        "reasons": sorted(set(reasons)),
        "manifest": str(manifest_path),
        "manifest_sha256": _hash_file(manifest_path),
        "checkpoint_root": str(root),
        "verified_files": verified,
    }


def _validate_gate0_chain(
    *,
    permit_path: str | Path | None,
    public_key_path: str | Path | None,
    launch_receipt_path: str | Path | None,
    booking_request_path: str | Path | None,
    provider_output_path: str | Path | None,
    security: SentrySecurity | None,
    policy: SentryPolicy,
) -> dict[str, Any]:
    supplied = {
        "permit": permit_path,
        "public_key": public_key_path,
        "launch_receipt": launch_receipt_path,
        "booking_request": booking_request_path,
        "provider_output": provider_output_path,
    }
    missing = [f"gate0_{name}_missing" for name, value in supplied.items() if value is None]
    if security is None:
        missing.append("gate0_principal_configuration_missing")
    if missing:
        return {"passed": False, "reasons": sorted(missing)}
    paths = {
        name: Path(value).expanduser().resolve()
        for name, value in supplied.items()
        if value is not None
    }
    try:
        envelope = read_json(paths["permit"])
        receipt = read_json(paths["launch_receipt"])
        provider_output = read_json(paths["provider_output"])
        public_key = load_public_key_document(paths["public_key"])
    except (OSError, ValueError, json.JSONDecodeError, PermitError) as exc:
        return {
            "passed": False,
            "reasons": ["gate0_artifact_missing_or_malformed"],
            "detail": str(exc),
        }
    reasons: list[str] = []
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    if envelope.get("schema") != GATE0_ENVELOPE_SCHEMA:
        reasons.append("gate0_envelope_schema_invalid")
    if payload.get("schema") != GATE0_PERMIT_SCHEMA:
        reasons.append("gate0_permit_schema_invalid")
    if envelope.get("key_id") != public_key.key_id:
        reasons.append("gate0_key_identity_mismatch")
    try:
        verify_detached_signature(
            public_key,
            domain=GATE0_SIGNATURE_DOMAIN,
            payload=payload,
            signature_base64=str(envelope.get("signature_base64") or ""),
        )
    except PermitError as exc:
        reasons.append(f"gate0_signature_invalid:{exc}")
    if payload.get("stage") != "lium-booking" or payload.get("decision") != "PROMOTABLE":
        reasons.append("gate0_stage_or_decision_invalid")
    request_id = str(payload.get("request_id") or "")
    nonce = str(payload.get("nonce") or "")
    if _REQUEST_ID_RE.fullmatch(request_id) is None or _HEX_256_RE.fullmatch(nonce) is None:
        reasons.append("gate0_request_id_or_nonce_invalid")
    issued_at: datetime | None = None
    expires_at: datetime | None = None
    try:
        issued_at = _require_security_time(payload.get("issued_at"), "gate0 issued_at")
        expires_at = _require_security_time(payload.get("expires_at"), "gate0 expires_at")
        if expires_at <= issued_at or expires_at - issued_at > timedelta(minutes=10):
            reasons.append("gate0_permit_lifetime_invalid")
    except DecisionSecurityError as exc:
        reasons.append(str(exc))
    if security is not None and (
        payload.get("sentry_principal") != security.sentry_principal
        or payload.get("executor_principal") != security.executor_principal
    ):
        reasons.append("gate0_principal_mismatch")
    if (
        payload.get("provider") != "lium"
        or payload.get("gpu_type") != "H100"
        or _integer(payload.get("gpu_count")) != 8
    ):
        reasons.append("gate0_provider_or_hardware_mismatch")
    ssh_public_key_path = payload.get("ssh_public_key_path")
    if (
        not isinstance(ssh_public_key_path, str)
        or not Path(ssh_public_key_path).is_absolute()
        or _HEX_256_RE.fullmatch(str(payload.get("ssh_public_key_sha256") or "")) is None
    ):
        reasons.append("gate0_ssh_access_binding_invalid")
    gate1_public_key_path = (
        security.sentry_public_key_path if security is not None else paths["public_key"]
    )
    booking = _validate_gate0_booking_request(
        paths["booking_request"], payload, gate1_public_key_path
    )
    reasons.extend(booking["reasons"])
    try:
        gate1_public_key = load_public_key_document(gate1_public_key_path)
        if gate1_public_key.key_id == public_key.key_id:
            reasons.append("gate0_gate1_key_reuse_forbidden")
    except PermitError:
        reasons.append("gate1_public_key_invalid")
    booking_hash = (
        _hash_file(paths["booking_request"]) if paths["booking_request"].is_file() else None
    )
    permit_hash = _hash_file(paths["permit"]) if paths["permit"].is_file() else None
    provider_hash = (
        _hash_file(paths["provider_output"]) if paths["provider_output"].is_file() else None
    )
    if booking_hash is None or payload.get("parent_request_sha256") != booking_hash:
        reasons.append("gate0_booking_request_hash_mismatch")
    execution = receipt.get("execution") if isinstance(receipt.get("execution"), dict) else {}
    if (
        receipt.get("schema") != LAUNCH_RECEIPT_SCHEMA
        or receipt.get("status") != "COMPLETED"
        or _integer(execution.get("exit_code")) != 0
        or _integer(execution.get("wrapper_exit_code")) != 0
        or execution.get("timed_out") is not False
    ):
        reasons.append("gate0_launch_receipt_status_invalid")
    allocation_started_at = _parse_time(execution.get("started_at"))
    allocation_finished_at = _parse_time(execution.get("finished_at"))
    if (
        allocation_started_at is None
        or allocation_finished_at is None
        or allocation_finished_at < allocation_started_at
    ):
        reasons.append("gate0_launch_receipt_timeline_invalid")
        first_pair_deadline_at = None
    else:
        first_pair_deadline_at = allocation_started_at + timedelta(
            seconds=policy.first_pair_deadline_seconds
        )
        if (
            issued_at is None
            or expires_at is None
            or not issued_at <= allocation_started_at < expires_at
        ):
            reasons.append("gate0_launch_started_outside_permit_interval")
    receipt_permit = receipt.get("permit") if isinstance(receipt.get("permit"), dict) else {}
    if (
        receipt_permit.get("sha256") != permit_hash
        or receipt_permit.get("key_id") != public_key.key_id
        or receipt_permit.get("request_id") != request_id
        or receipt_permit.get("nonce") != nonce
        or receipt_permit.get("issued_at") != payload.get("issued_at")
        or receipt_permit.get("expires_at") != payload.get("expires_at")
    ):
        reasons.append("gate0_launch_receipt_permit_mismatch")
    receipt_parent = (
        receipt.get("parent_request") if isinstance(receipt.get("parent_request"), dict) else {}
    )
    if (
        _resolve_recorded_path(receipt_parent.get("path")) != paths["booking_request"]
        or receipt_parent.get("sha256") != booking_hash
    ):
        reasons.append("gate0_launch_receipt_booking_request_mismatch")
    receipt_output = (
        receipt.get("provider_output") if isinstance(receipt.get("provider_output"), dict) else {}
    )
    if (
        _resolve_recorded_path(receipt_output.get("path")) != paths["provider_output"]
        or receipt_output.get("sha256") != provider_hash
        or _integer(receipt_output.get("size_bytes")) != paths["provider_output"].stat().st_size
    ):
        reasons.append("gate0_provider_output_mismatch")
    claim = receipt.get("claim") if isinstance(receipt.get("claim"), dict) else {}
    claim_path = _resolve_recorded_path(claim.get("path"))
    try:
        claim_payload = read_json(claim_path) if claim_path is not None else {}
    except (OSError, ValueError, json.JSONDecodeError):
        claim_payload = {}
    if (
        claim_path is None
        or _hash_path(claim_path) != claim.get("sha256")
        or claim_payload.get("request_id") != request_id
        or claim_payload.get("nonce") != nonce
        or claim_payload.get("permit_sha256") != permit_hash
        or _parse_time(claim_payload.get("consumed_at")) is None
    ):
        reasons.append("gate0_single_use_claim_invalid")
    executor = (
        provider_output.get("executor") if isinstance(provider_output.get("executor"), dict) else {}
    )
    schedule = (
        provider_output.get("schedule") if isinstance(provider_output.get("schedule"), dict) else {}
    )
    allocation_id, allocation_name = _extract_provider_allocation(provider_output)
    gpu_label = f"{executor.get('gpu_type', '')} {executor.get('gpu_model', '')}".upper()
    provider_schema = provider_output.get("schema")
    if (
        provider_schema != "lium-h100-pod-create/v2"
        or provider_output.get("status") != "RUNNING"
        or not allocation_id
        or not allocation_name
        or type(executor.get("gpu_count")) is not int
        or executor.get("gpu_count") != 8
        or "H100" not in gpu_label
        or schedule.get("confirmed") is not True
    ):
        reasons.append("gate0_provider_output_schema_or_hardware_invalid")
    if provider_schema == "lium-h100-pod-create/v2":
        reconciliation = (
            provider_output.get("create_reconciliation")
            if isinstance(provider_output.get("create_reconciliation"), dict)
            else {}
        )
        if (
            reconciliation.get("status") != "CONFIRMED_UNIQUE"
            or reconciliation.get("rent_mutation_attempt_policy")
            != "single-attempt-sdk-request-boundary/v1"
            or reconciliation.get("allocation_name") != allocation_name
            or reconciliation.get("pod_id") != allocation_id
            or reconciliation.get("final_active_pod_ids") != [allocation_id]
            or (_integer(reconciliation.get("successful_snapshots")) or 0) < 2
            or reconciliation.get("duplicate_cleanup_status") not in {"NOT_REQUIRED", "CONFIRMED"}
        ):
            reasons.append("gate0_provider_unique_allocation_unproven")
        provider_template = (
            provider_output.get("template")
            if isinstance(provider_output.get("template"), dict)
            else {}
        )
        expected_template = {
            "id": payload.get("template_id"),
            "docker_image": payload.get("template_image"),
            "docker_image_tag": payload.get("template_tag"),
            "status": payload.get("template_status"),
        }
        if any(provider_template.get(key) != value for key, value in expected_template.items()):
            reasons.append("gate0_provider_template_mismatch")
        runtime_evidence = provider_output.get("runtime_evidence")
        expected_runtime = {
            "provider_version": payload.get("provider_version"),
            "interpreter": {
                "path": payload.get("provider_interpreter"),
                "sha256": payload.get("provider_interpreter_sha256"),
                "version": payload.get("provider_interpreter_version"),
            },
            "lium_sdk": {
                "distribution": payload.get("lium_sdk_distribution"),
                "version": payload.get("lium_sdk_version"),
            },
            "lium_cli": {
                "path": payload.get("lium_cli_path"),
                "sha256": payload.get("lium_cli_sha256"),
                "version": payload.get("lium_cli_version"),
                "version_source": "wrapper_verified_cli_version",
            },
        }
        if runtime_evidence != expected_runtime:
            reasons.append("gate0_provider_runtime_evidence_mismatch")
        if (
            executor.get("observed_rate_status") != payload.get("observed_node_hourly_rate_status")
            or executor.get("observed_rate_status") != "provider_reported_nonzero"
            or executor.get("rate_authority") != "provider_raw_price_per_gpu_x_gpu_count/v1"
        ):
            reasons.append("gate0_provider_rate_authority_mismatch")
        rate_evidence = (
            executor.get("rate_evidence") if isinstance(executor.get("rate_evidence"), dict) else {}
        )
        expected_rate_authority = "provider_raw_price_per_gpu_x_gpu_count/v1"
        aggregate_rate_fields = {
            "executor_id",
            "gpu_count",
            "available_gpu_count",
            "price_per_gpu",
            "price_per_hour",
            "pending_price_change",
        }
        if (
            set(rate_evidence) != aggregate_rate_fields
            or rate_evidence.get("executor_id") != executor.get("id")
            or type(rate_evidence.get("gpu_count")) is not int
            or rate_evidence.get("gpu_count") != 8
            or type(rate_evidence.get("available_gpu_count")) is not int
            or rate_evidence.get("available_gpu_count") != 8
            or not math.isclose(
                _finite(rate_evidence.get("price_per_hour")) or -1.0,
                _finite(executor.get("observed_rate_usd_per_hour")) or -2.0,
            )
            or not math.isclose(
                _finite(rate_evidence.get("price_per_gpu")) or -1.0,
                _finite(executor.get("observed_rate_usd_per_gpu_hour")) or -2.0,
            )
            or rate_evidence.get("pending_price_change") is not False
        ):
            reasons.append("gate0_provider_raw_rate_evidence_mismatch")
        rent_boundary = (
            executor.get("rent_boundary") if isinstance(executor.get("rent_boundary"), dict) else {}
        )
        expected_raw_rate = {
            "authority": expected_rate_authority,
            **rate_evidence,
        }
        after_post = rent_boundary.get("after_post")
        after_available = (
            after_post.get("available_gpu_count")
            if isinstance(after_post, dict)
            and type(after_post.get("available_gpu_count")) is int
            else None
        )
        expected_after_identity = {
            key: value
            for key, value in expected_raw_rate.items()
            if key != "available_gpu_count"
        }
        observed_after_identity = (
            {
                key: value
                for key, value in after_post.items()
                if key != "available_gpu_count"
            }
            if isinstance(after_post, dict)
            else {}
        )
        signed_observed_rate = _finite(payload.get("observed_node_hourly_rate_usd"))
        price_per_gpu = _finite(rate_evidence.get("price_per_gpu"))
        price_per_hour = _finite(rate_evidence.get("price_per_hour"))
        if (
            rent_boundary.get("status") != "VERIFIED_PRE_AND_POST"
            or rent_boundary.get("endpoint") != f"/executors/{executor.get('id')}/rent"
            or rent_boundary.get("before_post") != expected_raw_rate
            or not isinstance(after_post, dict)
            or set(after_post) != set(expected_raw_rate)
            or observed_after_identity != expected_after_identity
            or after_available is None
            or not 0 <= after_available <= 8
            or expected_raw_rate.get("authority") != executor.get("rate_authority")
            or signed_observed_rate is None
            or price_per_gpu is None
            or price_per_hour is None
            or not math.isclose(price_per_hour, signed_observed_rate)
            or not math.isclose(price_per_gpu * 8, price_per_hour)
        ):
            reasons.append("gate0_provider_rent_boundary_invalid")
    expected_access = {
        "ssh_public_key_path": payload.get("ssh_public_key_path"),
        "ssh_public_key_sha256": payload.get("ssh_public_key_sha256"),
    }
    provider_access = (
        provider_output.get("access") if isinstance(provider_output.get("access"), dict) else {}
    )
    if provider_access != expected_access:
        reasons.append("gate0_provider_ssh_access_mismatch")
    termination = _parse_time(schedule.get("termination_time"))
    server_termination = _parse_time(schedule.get("server_removal_scheduled_at"))
    verified_termination = _parse_time(schedule.get("verified_termination_time"))
    if (
        termination is None
        or server_termination is None
        or verified_termination is None
        or termination != server_termination
        or termination != verified_termination
        or _integer(schedule.get("ttl_seconds")) != _integer(payload.get("ttl_seconds"))
    ):
        reasons.append("gate0_provider_schedule_not_server_verified")
    selector = str(payload.get("executor_id") or "")
    if selector not in {str(executor.get("id") or ""), str(executor.get("huid") or "")}:
        reasons.append("gate0_provider_executor_mismatch")
    if not math.isclose(
        _finite(executor.get("observed_rate_usd_per_hour")) or -1.0,
        _finite(payload.get("observed_node_hourly_rate_usd")) or -2.0,
    ) or not math.isclose(
        _finite(executor.get("max_rate_usd_per_hour")) or -1.0,
        _finite(payload.get("max_node_hourly_rate_usd")) or -2.0,
    ):
        reasons.append("gate0_provider_rate_mismatch")
    receipt_provider = receipt.get("provider") if isinstance(receipt.get("provider"), dict) else {}
    if (
        receipt_provider.get("name") != payload.get("provider")
        or receipt_provider.get("profile") != payload.get("profile")
        or receipt_provider.get("executor_id") != selector
    ):
        reasons.append("gate0_launch_receipt_provider_mismatch")
    if receipt.get("schema") == LAUNCH_RECEIPT_SCHEMA:
        receipt_runtime = (
            receipt.get("runtime_evidence")
            if isinstance(receipt.get("runtime_evidence"), dict)
            else {}
        )
        if receipt_runtime != {
            "provider_version": payload.get("provider_version"),
            "lium_sdk_distribution": payload.get("lium_sdk_distribution"),
            "lium_sdk_version": payload.get("lium_sdk_version"),
            "lium_cli_path": payload.get("lium_cli_path"),
            "lium_cli_sha256": payload.get("lium_cli_sha256"),
            "lium_cli_version": payload.get("lium_cli_version"),
        }:
            reasons.append("gate0_launch_receipt_runtime_evidence_mismatch")
        receipt_template = (
            receipt.get("template") if isinstance(receipt.get("template"), dict) else {}
        )
        if receipt_template != {
            "id": payload.get("template_id"),
            "image": payload.get("template_image"),
            "tag": payload.get("template_tag"),
            "status": payload.get("template_status"),
        }:
            reasons.append("gate0_launch_receipt_template_mismatch")
        if execution.get("credential_transport") != payload.get("credential_transport"):
            reasons.append("gate0_launch_receipt_credential_transport_mismatch")
        receipt_access = receipt.get("access") if isinstance(receipt.get("access"), dict) else {}
        if receipt_access != expected_access:
            reasons.append("gate0_launch_receipt_ssh_access_mismatch")
    receipt_allocation = (
        receipt.get("allocation") if isinstance(receipt.get("allocation"), dict) else {}
    )
    if (
        not allocation_id
        or not allocation_name
        or allocation_name != payload.get("allocation_name")
        or receipt_allocation.get("name") != allocation_name
        or _integer(receipt_allocation.get("issue_number")) != _integer(payload.get("issue_number"))
    ):
        reasons.append("gate0_allocation_identity_mismatch")
    receipt_budget = receipt.get("budget") if isinstance(receipt.get("budget"), dict) else {}
    for field in sorted(_BOOKING_BUDGET_FIELDS):
        if receipt_budget.get(field) != payload.get(field):
            reasons.append(f"gate0_launch_receipt_budget_mismatch:{field}")
    return {
        "passed": not reasons,
        "reasons": sorted(set(reasons)),
        "permit_sha256": permit_hash,
        "permit_key_id": public_key.key_id,
        "launch_receipt_sha256": _hash_file(paths["launch_receipt"]),
        "booking_request_sha256": booking_hash,
        "provider_output_sha256": provider_hash,
        "allocation_id": allocation_id,
        "allocation_name": allocation_name,
        "request_id": request_id,
        "nonce": nonce,
        "allocation_started_at": (
            _format_security_time(allocation_started_at)
            if allocation_started_at is not None
            else None
        ),
        "first_pair_deadline_at": (
            _format_security_time(first_pair_deadline_at)
            if first_pair_deadline_at is not None
            else None
        ),
        "gate1_trust": booking.get("gate1_trust", {}),
        "intent_artifacts": booking.get("intent_artifacts", {}),
    }


def _resolve_recorded_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value).expanduser().resolve()
    return path if path.is_file() else None


def _extract_provider_allocation(payload: dict[str, Any]) -> tuple[str, str]:
    pod = payload.get("pod") if isinstance(payload.get("pod"), dict) else {}
    allocation_id = str(pod.get("id") or "")
    allocation_name = str(pod.get("name") or "")
    return allocation_id, allocation_name


def _load_stage_request(
    path: str | Path | None,
    expected_stage: Stage,
    policy: SentryPolicy,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if path is None:
        return {}, {
            "passed": False,
            "reasons": ["request_missing"],
            "artifact": None,
            "request_sha256": None,
            "source_identity": None,
            "referenced_inputs": [],
        }
    source = Path(path).expanduser().resolve()
    try:
        payload = read_json(source)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, {
            "passed": False,
            "reasons": ["request_missing_or_malformed"],
            "detail": str(exc),
            "artifact": str(source),
            "request_sha256": _hash_file(source) if source.is_file() else None,
            "source_identity": None,
            "referenced_inputs": [],
        }
    reasons: list[str] = []
    if payload.get("schema_version") != 1:
        reasons.append("request_schema_version_mismatch")
    if payload.get("requested_stage") != expected_stage.value:
        reasons.append("request_stage_mismatch")
    source_identity = payload.get("source_identity")
    if not isinstance(source_identity, dict) or set(source_identity) != {
        "repo_sha",
        "training_base_sha",
    }:
        reasons.append("request_source_identity_schema_invalid")
    else:
        if not re.fullmatch(r"[0-9a-f]{40}", str(source_identity.get("repo_sha") or "")):
            reasons.append("request_repo_sha_invalid")
        if source_identity.get("training_base_sha") != policy.training_base_sha:
            reasons.append("request_training_base_sha_mismatch")
    result: dict[str, Any] = {
        "passed": False,
        "reasons": reasons,
        "artifact": str(source),
        "request_sha256": _hash_file(source),
        "source_identity": source_identity,
        "referenced_inputs": [],
    }
    for field in (
        "input_hashes",
        "evidence_hashes",
        "evidence_manifest_hashes",
        "trial_summary_hashes",
        "wandb_readback_hashes",
        "parent_promotion_sha256",
        "t2_budget_sha256",
    ):
        if field in payload:
            result[field] = payload[field]
    return payload, result


def _validate_preflight_request(
    path: str | Path | None,
    *,
    hardware_path: str | Path,
    budget_path: str | Path,
    hardware: dict[str, Any],
    policy: SentryPolicy,
) -> dict[str, Any]:
    payload, result = _load_stage_request(path, Stage.PREFLIGHT, policy)
    reasons = list(result["reasons"])
    if path is None or not payload:
        result["reasons"] = sorted(set(reasons))
        return result
    expected_inputs = {
        "protocol",
        "source",
        "hardware",
        "checkpoint",
        "data",
        "wandb_auth",
        "runtime",
        "budget",
    }
    input_hashes = payload.get("input_hashes")
    if not _valid_hash_map(input_hashes, expected_inputs):
        reasons.append("preflight_request_input_hashes_invalid")
    if "evidence_hashes" in payload or "trial_summary_hashes" in payload:
        reasons.append("preflight_request_unexpected_screen_hashes")
    manifest_recorded = payload.get("prepare_manifest_sha256")
    if not _valid_sha256(manifest_recorded):
        reasons.append("preflight_request_manifest_hash_invalid")
    request_source = Path(path).expanduser().resolve()
    manifest_path = request_source.parent / "prepare_manifest.json"
    _add_request_reference(result, "request_prepare_manifest", manifest_path)
    try:
        manifest = read_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError):
        reasons.append("prepare_manifest_missing_or_malformed")
        manifest = {}
    if manifest and _hash_file(manifest_path) != manifest_recorded:
        reasons.append("prepare_manifest_request_hash_mismatch")
    if manifest.get("schema_version") != 1:
        reasons.append("prepare_manifest_schema_invalid")
    if manifest.get("authority") != "executor_prepare_evidence":
        reasons.append("prepare_manifest_authority_invalid")
    if manifest.get("ok") is not True:
        reasons.append("prepare_manifest_not_ok")
    artifacts = manifest.get("artifacts")
    manifest_hashes = manifest.get("sha256")
    if not isinstance(artifacts, dict) or set(artifacts) != expected_inputs:
        reasons.append("prepare_manifest_artifact_map_invalid")
        artifacts = {}
    if not _valid_hash_map(manifest_hashes, expected_inputs):
        reasons.append("prepare_manifest_hash_map_invalid")
        manifest_hashes = {}
    if input_hashes != manifest_hashes:
        reasons.append("preflight_request_manifest_hashes_mismatch")
    resolved: dict[str, Path] = {}
    for name in sorted(expected_inputs):
        reference = _resolve_request_reference(manifest_path.parent, artifacts.get(name))
        if reference is None:
            reasons.append(f"prepare_input_{name}_missing")
            continue
        resolved[name] = reference
        _add_request_reference(result, f"request_input:{name}", reference)
        if _hash_file(reference) != manifest_hashes.get(name):
            reasons.append(f"prepare_input_{name}_hash_mismatch")
    expected_supporting = {
        "setup_attestation",
        "hf_revision_marker",
        "container_inspection",
    }
    supporting_artifacts = manifest.get("supporting_artifacts")
    supporting_hashes = manifest.get("supporting_sha256")
    if (
        not isinstance(supporting_artifacts, dict)
        or set(supporting_artifacts) != expected_supporting
    ):
        reasons.append("prepare_manifest_supporting_artifact_map_invalid")
        supporting_artifacts = {}
    if not _valid_hash_map(supporting_hashes, expected_supporting):
        reasons.append("prepare_manifest_supporting_hash_map_invalid")
        supporting_hashes = {}
    supporting_resolved: dict[str, Path] = {}
    for name in sorted(expected_supporting):
        reference = _resolve_request_reference(
            manifest_path.parent,
            supporting_artifacts.get(name),
        )
        if reference is None:
            reasons.append(f"prepare_supporting_{name}_missing")
            continue
        supporting_resolved[name] = reference
        _add_request_reference(result, f"request_supporting:{name}", reference)
        if _hash_file(reference) != supporting_hashes.get(name):
            reasons.append(f"prepare_supporting_{name}_hash_mismatch")
    prepared_evidence: dict[str, dict[str, Any]] = {}
    for name in ("source", "runtime", "data", "checkpoint", "protocol"):
        reference = resolved.get(name)
        if reference is None:
            continue
        try:
            prepared_evidence[name] = read_json(reference)
        except (OSError, ValueError, json.JSONDecodeError):
            reasons.append(f"prepare_{name}_receipt_malformed")
    try:
        setup_attestation = read_json(supporting_resolved["setup_attestation"])
        marker_content = (
            supporting_resolved["hf_revision_marker"].read_text(encoding="utf-8").strip()
        )
        container_inspection = json.loads(
            supporting_resolved["container_inspection"].read_text(encoding="utf-8")
        )
        prepared_evidence["setup"] = {
            "attestation": setup_attestation,
            "attestation_sha256": supporting_hashes.get("setup_attestation"),
            "hf_revision_marker_sha256": supporting_hashes.get("hf_revision_marker"),
            "hf_revision_marker_content": marker_content,
            "container_inspection_sha256": supporting_hashes.get("container_inspection"),
            "container_inspection": container_inspection,
        }
    except (KeyError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        reasons.append("prepare_setup_supporting_evidence_malformed")
    if not _same_path(resolved.get("hardware"), hardware_path):
        reasons.append("preflight_request_hardware_path_mismatch")
    if not _same_path(resolved.get("budget"), budget_path):
        reasons.append("preflight_request_budget_path_mismatch")
    source_payload = prepared_evidence.get("source", {})
    if source_payload.get("ok") is not True:
        reasons.append("prepare_source_receipt_not_ok")
    expected_source = {
        "repo_sha": source_payload.get("repo_sha"),
        "training_base_sha": source_payload.get("training_base_sha"),
    }
    if result.get("source_identity") != expected_source:
        reasons.append("preflight_request_source_receipt_mismatch")
    hardware_source = {
        "repo_sha": hardware.get("repo_sha"),
        "training_base_sha": hardware.get("training_base_sha"),
    }
    if result.get("source_identity") != hardware_source:
        reasons.append("preflight_request_hardware_source_mismatch")
    expected_request_prepared = {
        name: prepared_evidence.get(name)
        for name in ("source", "runtime", "data", "checkpoint", "setup")
    }
    if payload.get("prepared_evidence") != expected_request_prepared:
        reasons.append("preflight_request_prepared_evidence_mismatch")
    result["prepared_evidence"] = prepared_evidence
    result["prepared_paths"] = {
        **{name: str(path) for name, path in resolved.items()},
        **{f"supporting:{name}": str(path) for name, path in supporting_resolved.items()},
    }
    result["passed"] = not reasons
    result["reasons"] = sorted(set(reasons))
    return result


def _validate_screen_request(
    path: str | Path | None,
    *,
    control_path: str | Path,
    candidate_path: str | Path,
    expected_source: Any,
    expected_gate0: Any,
    evaluation_time: datetime,
    policy: SentryPolicy,
) -> dict[str, Any]:
    payload, result = _load_stage_request(path, Stage.SCREEN, policy)
    reasons = list(result["reasons"])
    if path is None or not payload:
        result["reasons"] = sorted(set(reasons))
        return result
    leg_ids = {"a1", "b1"}
    evidence_hashes = payload.get("evidence_hashes")
    trial_hashes = payload.get("trial_summary_hashes")
    if not _valid_hash_map(evidence_hashes, leg_ids):
        reasons.append("screen_request_evidence_hashes_invalid")
        evidence_hashes = {}
    if not _valid_hash_map(trial_hashes, leg_ids):
        reasons.append("screen_request_trial_summary_hashes_invalid")
        trial_hashes = {}
    if "input_hashes" in payload or "prepare_manifest_sha256" in payload:
        reasons.append("screen_request_unexpected_preflight_hashes")
    if result.get("source_identity") != expected_source:
        reasons.append("screen_request_prior_source_identity_mismatch")
    recorded_gate0 = payload.get("gate0")
    if (
        not isinstance(expected_gate0, Mapping)
        or not isinstance(recorded_gate0, Mapping)
        or dict(recorded_gate0) != dict(expected_gate0)
    ):
        reasons.append("screen_request_gate0_context_mismatch")
    allocation_started_at = (
        _parse_time(expected_gate0.get("allocation_started_at"))
        if isinstance(expected_gate0, Mapping)
        else None
    )
    first_pair_deadline_at = (
        _parse_time(expected_gate0.get("first_pair_deadline_at"))
        if isinstance(expected_gate0, Mapping)
        else None
    )
    if (
        allocation_started_at is None
        or first_pair_deadline_at is None
        or first_pair_deadline_at
        != allocation_started_at + timedelta(seconds=policy.first_pair_deadline_seconds)
    ):
        reasons.append("screen_first_pair_deadline_context_invalid")
        first_pair_deadline_at = None
    request_issued_at = _parse_time(payload.get("issued_at"))
    if request_issued_at is None:
        reasons.append("screen_request_issued_at_invalid")
    request_source = Path(path).expanduser().resolve()
    source_path = request_source.parent / "receipts" / "source.json"
    _add_request_reference(result, "request_source_receipt", source_path)
    try:
        source_payload = read_json(source_path)
    except (OSError, ValueError, json.JSONDecodeError):
        source_payload = {}
        reasons.append("screen_source_receipt_missing_or_malformed")
    source_identity = {
        "repo_sha": source_payload.get("repo_sha"),
        "training_base_sha": source_payload.get("training_base_sha"),
    }
    if source_payload.get("ok") is not True:
        reasons.append("screen_source_receipt_not_ok")
    if result.get("source_identity") != source_identity:
        reasons.append("screen_request_source_receipt_mismatch")
    result_path = request_source.parent / "first_pair_result.json"
    _add_request_reference(result, "request_first_pair_result", result_path)
    try:
        first_pair = read_json(result_path)
    except (OSError, ValueError, json.JSONDecodeError):
        first_pair = {}
        reasons.append("first_pair_result_missing_or_malformed")
    if first_pair.get("status") != "first_pair_complete":
        reasons.append("first_pair_result_status_invalid")
    if first_pair.get("authority") != "executor_evidence":
        reasons.append("first_pair_result_authority_invalid")
    legs = first_pair.get("legs")
    if not isinstance(legs, list) or len(legs) != 2:
        reasons.append("first_pair_result_legs_invalid")
        legs = []
    leg_map = {
        str(leg.get("leg_id")): leg
        for leg in legs
        if isinstance(leg, dict) and leg.get("leg_id") in leg_ids
    }
    if set(leg_map) != leg_ids:
        reasons.append("first_pair_result_leg_ids_invalid")
    try:
        expected_trials = {
            "a1": _resolve_summary(control_path),
            "b1": _resolve_summary(candidate_path),
        }
    except ValueError:
        expected_trials = {}
        reasons.append("screen_trial_summary_missing_or_ambiguous")
    leg_finished_at: dict[str, datetime] = {}
    for leg_id in sorted(leg_ids):
        leg = leg_map.get(leg_id)
        if leg is None:
            continue
        trial = _resolve_request_reference(result_path.parent, leg.get("trial_summary"))
        manifest = _resolve_request_reference(result_path.parent, leg.get("evidence_manifest"))
        if trial is None or manifest is None:
            reasons.append(f"screen_{leg_id}_referenced_artifact_missing")
            continue
        _add_request_reference(result, f"request_trial_summary:{leg_id}", trial)
        _add_request_reference(result, f"request_evidence_manifest:{leg_id}", manifest)
        if not _same_path(trial, expected_trials.get(leg_id)):
            reasons.append(f"screen_{leg_id}_trial_path_mismatch")
        if _hash_file(trial) != trial_hashes.get(leg_id):
            reasons.append(f"screen_{leg_id}_trial_hash_mismatch")
        manifest_hash = _hash_file(manifest)
        if manifest_hash != evidence_hashes.get(leg_id):
            reasons.append(f"screen_{leg_id}_evidence_hash_mismatch")
        if leg.get("evidence_manifest_sha256") != manifest_hash:
            reasons.append(f"screen_{leg_id}_result_manifest_hash_mismatch")
        if leg.get("valid") is not True:
            reasons.append(f"screen_{leg_id}_runner_leg_not_valid")
        manifest_reasons, manifest_inputs, resolved_evidence = _validate_runner_evidence_manifest(
            manifest,
            leg_id=leg_id,
            expected_trial=trial,
        )
        reasons.extend(manifest_reasons)
        for role, reference in manifest_inputs:
            _add_request_reference(result, role, reference)
        run_receipt_path = resolved_evidence.get("run_receipt")
        try:
            run_receipt = read_key_value(run_receipt_path) if run_receipt_path is not None else {}
        except OSError:
            run_receipt = {}
        finished_at = _parse_time(run_receipt.get("run_finished_at_utc"))
        if finished_at is None:
            reasons.append(f"screen_{leg_id}_run_finished_at_invalid")
        else:
            leg_finished_at[leg_id] = finished_at
    if first_pair_deadline_at is not None:
        for leg_id in sorted(leg_ids):
            finished_at = leg_finished_at.get(leg_id)
            if finished_at is None or finished_at >= first_pair_deadline_at:
                reasons.append(f"screen_{leg_id}_finished_at_or_after_first_pair_deadline")
        if request_issued_at is not None:
            if request_issued_at >= first_pair_deadline_at:
                reasons.append("screen_request_issued_at_or_after_first_pair_deadline")
            if leg_finished_at and request_issued_at < max(leg_finished_at.values()):
                reasons.append("screen_request_issued_before_first_pair_completed")
            if evaluation_time < request_issued_at:
                reasons.append("screen_evaluation_precedes_request")
        if evaluation_time >= first_pair_deadline_at:
            reasons.append("screen_evaluation_at_or_after_first_pair_deadline")
    result["passed"] = not reasons
    result["reasons"] = sorted(set(reasons))
    return result


def _validate_confirmation_request(
    path: str | Path | None,
    *,
    promotion_decision_path: str | Path,
    control_paths: Sequence[str | Path],
    candidate_paths: Sequence[str | Path],
    expected_source: Any,
    policy: SentryPolicy,
    security: SentrySecurity | None,
) -> dict[str, Any]:
    payload, result = _load_stage_request(path, Stage.CONFIRMATION, policy)
    reasons = list(result["reasons"])
    if path is None or not payload:
        result["reasons"] = sorted(set(reasons))
        return result
    if result.get("source_identity") != expected_source:
        reasons.append("confirmation_request_prior_source_identity_mismatch")
    parent_hash = payload.get("parent_promotion_sha256")
    promotion_path = Path(promotion_decision_path).expanduser().resolve()
    if not _valid_sha256(parent_hash) or parent_hash != _hash_file(promotion_path):
        reasons.append("confirmation_parent_promotion_hash_mismatch")
    expected_labels = {
        *(f"a{index}" for index in range(1, 5)),
        *(f"b{index}" for index in range(1, 5)),
    }
    trial_hashes = payload.get("trial_summary_hashes")
    evidence_manifest_hashes = payload.get("evidence_manifest_hashes")
    readback_hashes = payload.get("wandb_readback_hashes")
    if not _valid_hash_map(trial_hashes, expected_labels):
        reasons.append("confirmation_trial_summary_hashes_invalid")
        trial_hashes = {}
    if not _valid_hash_map(evidence_manifest_hashes, expected_labels):
        reasons.append("confirmation_evidence_manifest_hashes_invalid")
        evidence_manifest_hashes = {}
    if not _valid_hash_map(readback_hashes, expected_labels):
        reasons.append("confirmation_wandb_readback_hashes_invalid")
        readback_hashes = {}
    if len(control_paths) != 4 or len(candidate_paths) != 4:
        reasons.append("confirmation_request_requires_exactly_four_process_pairs")
    else:
        labeled_paths = {
            **{f"a{index}": value for index, value in enumerate(control_paths, 1)},
            **{f"b{index}": value for index, value in enumerate(candidate_paths, 1)},
        }
        for label, trial_value in sorted(labeled_paths.items()):
            try:
                trial = _resolve_summary(trial_value)
            except ValueError:
                reasons.append(f"confirmation_{label}_trial_summary_missing_or_ambiguous")
                continue
            _add_request_reference(result, f"request_trial_summary:{label}", trial)
            if _hash_file(trial) != trial_hashes.get(label):
                reasons.append(f"confirmation_{label}_trial_summary_hash_mismatch")
            manifest = trial.parent / "leg_evidence_manifest.json"
            if not manifest.is_file():
                reasons.append(f"confirmation_{label}_evidence_manifest_missing")
            else:
                _add_request_reference(result, f"request_evidence_manifest:{label}", manifest)
                if _hash_file(manifest) != evidence_manifest_hashes.get(label):
                    reasons.append(f"confirmation_{label}_evidence_manifest_hash_mismatch")
                manifest_reasons, manifest_inputs, _ = _validate_runner_evidence_manifest(
                    manifest,
                    leg_id=label,
                    expected_trial=trial,
                    reason_scope="confirmation",
                )
                reasons.extend(manifest_reasons)
                for role, reference in manifest_inputs:
                    _add_request_reference(result, role, reference)
            readbacks = sorted(trial.parent.rglob("wandb_readback.json"))
            if len(readbacks) != 1:
                reasons.append(f"confirmation_{label}_wandb_readback_missing_or_ambiguous")
                continue
            readback = readbacks[0]
            _add_request_reference(result, f"request_wandb_readback:{label}", readback)
            if _hash_file(readback) != readback_hashes.get(label):
                reasons.append(f"confirmation_{label}_wandb_readback_hash_mismatch")
    request_path = Path(path).expanduser().resolve()
    budget_path = _resolve_request_reference(request_path.parent, payload.get("t2_budget_path"))
    if budget_path is None:
        reasons.append("confirmation_t2_budget_missing")
        budget = {"passed": False, "reasons": ["confirmation_t2_budget_missing"]}
    else:
        _add_request_reference(result, "request_t2_budget", budget_path)
        if not _valid_sha256(payload.get("t2_budget_sha256")) or _hash_file(
            budget_path
        ) != payload.get("t2_budget_sha256"):
            reasons.append("confirmation_t2_budget_hash_mismatch")
        budget = _validate_t2_authorization(
            budget_path,
            parent_promotion_sha256=str(parent_hash or ""),
            source_identity=result.get("source_identity"),
            policy=policy,
            security=security,
        )
        reasons.extend(budget["reasons"])
    result["t2_authorization"] = budget
    result["passed"] = not reasons
    result["reasons"] = sorted(set(reasons))
    return result


def _validate_t2_authorization(
    path: Path,
    *,
    parent_promotion_sha256: str,
    source_identity: Any,
    policy: SentryPolicy,
    security: SentrySecurity | None,
) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {"passed": False, "reasons": ["t2_authorization_malformed"]}
    reasons: list[str] = []
    if (
        security is None
        or security.supervisor_public_key_path is None
        or not security.supervisor_principal
    ):
        reasons.append("t2_authorization_signature_trust_missing")
        signature_metadata: dict[str, Any] = {}
    else:
        try:
            signature_metadata = _verify_bounded_payload(
                payload,
                public_key_path=security.supervisor_public_key_path,
                domain=T2_AUTHORIZATION_DOMAIN,
                expected_signer_principal=security.supervisor_principal,
                expected_verifier_principal=security.executor_principal,
                now=security.now,
            )
        except DecisionSecurityError as exc:
            signature_metadata = {}
            reasons.append(f"t2_authorization_signature_invalid:{exc}")
    if payload.get("schema_version") != 1:
        reasons.append("t2_authorization_schema_invalid")
    if payload.get("authority") != "supervisor_t2_authorization":
        reasons.append("t2_authorization_authority_invalid")
    if payload.get("authorized") is not True or payload.get("tranche_id") != "T2":
        reasons.append("t2_authorization_not_granted")
    if _integer(payload.get("issue_number")) != 32 or payload.get("nontransferable") is not True:
        reasons.append("t2_authorization_issue_or_transferability_invalid")
    if not str(payload.get("authorization_id") or "") or not str(
        payload.get("authorized_by") or ""
    ):
        reasons.append("t2_authorization_identity_missing")
    if _parse_time(payload.get("authorized_at_utc")) is None:
        reasons.append("t2_authorization_timestamp_invalid")
    if payload.get("parent_t1_promotion_sha256") != parent_promotion_sha256:
        reasons.append("t2_authorization_parent_promotion_mismatch")
    source_commit = str(payload.get("source_commit") or "")
    expected_repo = (
        str(source_identity.get("repo_sha") or "") if isinstance(source_identity, dict) else ""
    )
    if not source_commit or source_commit != expected_repo:
        reasons.append("t2_authorization_source_commit_mismatch")
    if str(payload.get("provider") or "").lower() != "lium":
        reasons.append("t2_authorization_provider_mismatch")
    if not re.search(r"8\s*x\s*H100", str(payload.get("accelerators") or ""), re.I):
        reasons.append("t2_authorization_hardware_shape_mismatch")
    if payload.get("unused_budget_transfer_allowed") is not False:
        reasons.append("t2_authorization_transfer_policy_invalid")
    planned_hours = _finite(payload.get("planned_hours"))
    maximum_hours = _finite(payload.get("maximum_node_hours"))
    hourly_rate = _finite(payload.get("hourly_rate_usd"))
    maximum_usd = _finite(payload.get("maximum_usd"))
    if (
        planned_hours is None
        or maximum_hours is None
        or hourly_rate is None
        or maximum_usd is None
        or planned_hours <= 0
        or hourly_rate <= 0
        or planned_hours > maximum_hours
        or maximum_hours > policy.maximum_node_hours
        or maximum_usd > policy.maximum_usd
        or planned_hours * hourly_rate > maximum_usd
    ):
        reasons.append("t2_authorization_budget_limits_invalid")
    return {
        "passed": not reasons,
        "reasons": sorted(set(reasons)),
        "artifact": str(path),
        "authorization_id": payload.get("authorization_id"),
        "authorized_by": payload.get("authorized_by"),
        "planned_hours": planned_hours,
        "maximum_node_hours": maximum_hours,
        "maximum_usd": maximum_usd,
        "key_id": signature_metadata.get("key_id"),
    }


def _validate_runner_evidence_manifest(
    path: Path,
    *,
    leg_id: str,
    expected_trial: Path,
    reason_scope: str = "screen",
) -> tuple[list[str], list[tuple[str, Path]], dict[str, Path]]:
    prefix = f"{reason_scope}_{leg_id}"
    try:
        payload = read_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return [f"{prefix}_evidence_manifest_malformed"], [], {}
    reasons: list[str] = []
    expected_names = {
        "trial_summary",
        "leg_summary",
        "run_log",
        "run_receipt",
        "gpu_telemetry",
        "nvlink_before",
        "nvlink_after",
        "process_cleanliness_before",
        "process_cleanliness_after",
        "wandb_readback",
        "wandb_evidence_summary",
        "wandb_artifact_manifest",
    }
    if payload.get("schema_version") != 1:
        reasons.append(f"{prefix}_evidence_manifest_schema_invalid")
    if payload.get("authority") != "executor_raw_evidence":
        reasons.append(f"{prefix}_evidence_manifest_authority_invalid")
    if payload.get("leg") != leg_id:
        reasons.append(f"{prefix}_evidence_manifest_leg_mismatch")
    if payload.get("valid") is not True:
        reasons.append(f"{prefix}_evidence_manifest_not_valid")
    paths = payload.get("paths")
    hashes = payload.get("sha256")
    if not isinstance(paths, dict) or set(paths) != expected_names:
        reasons.append(f"{prefix}_evidence_paths_invalid")
        paths = {}
    if not _valid_hash_map(hashes, expected_names):
        reasons.append(f"{prefix}_evidence_constituent_hashes_invalid")
        hashes = {}
    inputs: list[tuple[str, Path]] = []
    resolved: dict[str, Path] = {}
    for name in sorted(expected_names):
        reference = _resolve_request_reference(path.parent, paths.get(name))
        if reference is None:
            reasons.append(f"{prefix}_{name}_missing")
            continue
        resolved[name] = reference
        inputs.append((f"request_evidence:{leg_id}:{name}", reference))
        if _hash_file(reference) != hashes.get(name):
            reasons.append(f"{prefix}_{name}_hash_mismatch")
        if name == "trial_summary" and not _same_path(reference, expected_trial):
            reasons.append(f"{prefix}_manifest_trial_path_mismatch")
    reasons.extend(
        _process_cleanliness_evidence_reasons(
            resolved,
            leg_id=leg_id,
            reason_scope=reason_scope,
        )
    )
    return reasons, inputs, resolved


def _process_cleanliness_evidence_reasons(
    resolved: Mapping[str, Path],
    *,
    leg_id: str,
    reason_scope: str = "screen",
) -> list[str]:
    prefix = f"{reason_scope}_{leg_id}"
    reasons: list[str] = []
    receipts: dict[str, Mapping[str, Any]] = {}
    timestamps: dict[str, datetime | None] = {}
    required_fields = {
        "schema",
        "checked_at_utc",
        "ok",
        "errors",
        "gpu_process_inventory",
        "relevant_processes",
        "commands",
    }
    for position in ("before", "after"):
        path = resolved.get(f"process_cleanliness_{position}")
        try:
            payload = read_json(path) if path is not None else {}
        except (OSError, ValueError, json.JSONDecodeError):
            payload = {}
        receipts[position] = payload if isinstance(payload, Mapping) else {}
        timestamps[position] = _parse_time(receipts[position].get("checked_at_utc"))
        commands = receipts[position].get("commands")
        if (
            set(receipts[position]) != required_fields
            or receipts[position].get("schema") != "h100-process-cleanliness/v1"
            or timestamps[position] is None
            or receipts[position].get("ok") is not True
            or receipts[position].get("errors") != []
            or receipts[position].get("gpu_process_inventory") != []
            or receipts[position].get("relevant_processes") != []
            or not isinstance(commands, Mapping)
            or _integer(commands.get("gpu_process_inventory_returncode")) != 0
            or _integer(commands.get("process_inventory_returncode")) != 0
        ):
            reasons.append(f"{prefix}_process_cleanliness_{position}_invalid")
    run_receipt_path = resolved.get("run_receipt")
    try:
        run_receipt = read_key_value(run_receipt_path) if run_receipt_path is not None else {}
    except OSError:
        run_receipt = {}
    started = _parse_time(run_receipt.get("run_started_at_utc"))
    finished = _parse_time(run_receipt.get("run_finished_at_utc"))
    before = timestamps.get("before")
    after = timestamps.get("after")
    if (
        started is None
        or finished is None
        or before is None
        or after is None
        or not before <= started <= after <= finished
        or (started - before).total_seconds() > 300
        or (finished - after).total_seconds() > 300
    ):
        reasons.append(f"{prefix}_process_cleanliness_timeline_invalid")
    return reasons


def _validate_promotion_runner_evidence(
    *,
    screen_decision_path: str | Path,
    screen_payload: Mapping[str, Any],
    control_paths: Sequence[str | Path],
    candidate_paths: Sequence[str | Path],
) -> dict[str, Any]:
    labeled = {
        "a1": control_paths[0],
        "a2": control_paths[1],
        "b1": candidate_paths[0],
        "b2": candidate_paths[1],
    }
    reasons: list[str] = []
    inputs: list[tuple[str, Path]] = []
    manifests: dict[str, Path] = {}
    for label, trial_value in labeled.items():
        try:
            trial = _resolve_summary(trial_value)
        except ValueError:
            reasons.append(f"promotion_{label}_trial_summary_missing_or_ambiguous")
            continue
        manifest = trial.parent / "leg_evidence_manifest.json"
        if not manifest.is_file():
            reasons.append(f"promotion_{label}_evidence_manifest_missing")
            continue
        manifests[label] = manifest.resolve()
        inputs.append((f"runner_evidence_manifest:{label}", manifest))
        manifest_reasons, manifest_inputs, _ = _validate_runner_evidence_manifest(
            manifest,
            leg_id=label,
            expected_trial=trial,
            reason_scope="promotion",
        )
        reasons.extend(manifest_reasons)
        inputs.extend(manifest_inputs)
    aggregate_path = _shared_runner_artifact(manifests.values(), "executor_evidence_manifest.json")
    second_pair_path = _shared_runner_artifact(manifests.values(), "second_pair_result.json")
    if aggregate_path is None:
        reasons.append("promotion_executor_evidence_manifest_missing_or_ambiguous")
    else:
        inputs.append(("runner_executor_evidence_manifest", aggregate_path))
        try:
            aggregate = read_json(aggregate_path)
        except (OSError, ValueError, json.JSONDecodeError):
            aggregate = {}
        recorded = aggregate.get("leg_manifest_sha256")
        expected = {str(path): _hash_file(path) for path in manifests.values()}
        resolved_recorded: dict[str, Any] = {}
        if isinstance(recorded, Mapping):
            for raw_path, digest in recorded.items():
                reference = _resolve_request_reference(aggregate_path.parent, raw_path)
                if reference is not None:
                    resolved_recorded[str(reference)] = digest
        if (
            aggregate.get("schema_version") != 1
            or aggregate.get("authority") != "executor_raw_evidence"
            or resolved_recorded != expected
            or set(manifests) != {"a1", "a2", "b1", "b2"}
        ):
            reasons.append("promotion_executor_evidence_manifest_invalid")
    if second_pair_path is None:
        reasons.append("promotion_second_pair_result_missing_or_ambiguous")
    else:
        inputs.append(("runner_second_pair_result", second_pair_path))
        try:
            second_pair = read_json(second_pair_path)
        except (OSError, ValueError, json.JSONDecodeError):
            second_pair = {}
        legs = second_pair.get("legs")
        leg_map = (
            {str(item.get("leg_id") or ""): item for item in legs if isinstance(item, Mapping)}
            if isinstance(legs, list)
            else {}
        )
        expected_second = {"b2": manifests.get("b2"), "a2": manifests.get("a2")}
        if (
            second_pair.get("status") != "second_pair_complete"
            or second_pair.get("authority") != "executor_evidence"
            or second_pair.get("repair_required") is not False
            or list(leg_map) != ["b2", "a2"]
            or second_pair.get("signed_approval_sha256")
            != _hash_file(Path(screen_decision_path).expanduser().resolve())
            or second_pair.get("request_sha256") != screen_payload.get("request_sha256")
        ):
            reasons.append("promotion_second_pair_result_binding_invalid")
        for label, manifest in expected_second.items():
            leg = leg_map.get(label, {})
            if (
                manifest is None
                or leg.get("valid") is not True
                or _resolve_request_reference(second_pair_path.parent, leg.get("evidence_manifest"))
                != manifest
                or leg.get("evidence_manifest_sha256") != _hash_file(manifest)
            ):
                reasons.append(f"promotion_{label}_second_pair_manifest_binding_invalid")
    return {
        "passed": not reasons,
        "reasons": sorted(set(reasons)),
        "inputs": inputs,
        "manifest_sha256": {label: _hash_file(path) for label, path in sorted(manifests.items())},
        "executor_evidence_manifest": str(aggregate_path) if aggregate_path else None,
        "second_pair_result": str(second_pair_path) if second_pair_path else None,
    }


def _shared_runner_artifact(paths: Iterable[Path], filename: str) -> Path | None:
    candidates: set[Path] = set()
    for path in paths:
        for ancestor in (path.parent, *path.parents[:4]):
            candidate = ancestor / filename
            if candidate.is_file():
                candidates.add(candidate.resolve())
    return next(iter(candidates)) if len(candidates) == 1 else None


def _valid_hash_map(value: Any, expected_keys: set[str]) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == expected_keys
        and all(_valid_sha256(item) for item in value.values())
    )


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _resolve_request_reference(base: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    reference = Path(value).expanduser()
    if not reference.is_absolute():
        reference = base / reference
    reference = reference.resolve()
    return reference if reference.is_file() else None


def _same_path(left: Path | None, right: str | Path | None) -> bool:
    return left is not None and right is not None and left == Path(right).expanduser().resolve()


def _add_request_reference(result: dict[str, Any], role: str, path: Path) -> None:
    result["referenced_inputs"].append({"role": role, "path": str(path.resolve())})


def _request_provenance_inputs(request: dict[str, Any]) -> list[tuple[str, str | Path]]:
    return [
        (str(item["role"]), str(item["path"]))
        for item in request.get("referenced_inputs", [])
        if isinstance(item, dict) and item.get("role") and item.get("path")
    ]


def _apply_request_binding(result: dict[str, Any], request: dict[str, Any]) -> None:
    result["request_sha256"] = request.get("request_sha256")
    result["source_identity"] = request.get("source_identity")
    for field in (
        "input_hashes",
        "evidence_hashes",
        "evidence_manifest_hashes",
        "trial_summary_hashes",
        "wandb_readback_hashes",
        "parent_promotion_sha256",
        "t2_budget_sha256",
    ):
        if field in request:
            result[field] = request[field]


def _validate_contract(path: str | Path, policy: SentryPolicy) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    try:
        payload = read_json(source)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"passed": False, "reasons": ["contract_missing_or_malformed"], "detail": str(exc)}
    reasons: list[str] = []
    checks = (
        (payload.get("contract_id") == policy.contract_id, "contract_id_mismatch"),
        (
            (payload.get("metric_definition") or {}).get("name") == policy.metric_name,
            "contract_metric_name_mismatch",
        ),
        (
            math.isclose(
                _finite((payload.get("metric_definition") or {}).get("bf16_peak_tflops_per_gpu"))
                or 0,
                policy.bf16_peak_tflops_per_gpu,
            ),
            "contract_mfu_denominator_mismatch",
        ),
        (
            (payload.get("metric_definition") or {}).get("absolute_hardware_mfu_claim_allowed")
            is False,
            "contract_claim_boundary_invalid",
        ),
        (
            math.isclose(
                _finite((payload.get("acceptance") or {}).get("minimum_relative_mfu_gain")) or 0,
                0.03,
            ),
            "contract_mfu_gain_mismatch",
        ),
        (
            math.isclose(
                _finite(
                    (payload.get("acceptance") or {}).get("minimum_relative_actor_throughput_gain")
                )
                or 0,
                0.03,
            ),
            "contract_throughput_gain_mismatch",
        ),
        (
            math.isclose(
                _finite(
                    (payload.get("acceptance") or {}).get(
                        "early_stop_minimum_estimated_mfu_retention"
                    )
                )
                or 0,
                0.98,
            ),
            "contract_early_stop_mfu_mismatch",
        ),
        (
            math.isclose(
                _finite(
                    (payload.get("acceptance") or {}).get(
                        "early_stop_minimum_actor_throughput_retention"
                    )
                )
                or 0,
                0.98,
            ),
            "contract_early_stop_throughput_mismatch",
        ),
        (
            (payload.get("acceptance") or {}).get("early_stop_policy")
            == "reject after A1/B1 when either aggregate process-pair metric ratio is below 0.98",
            "contract_early_stop_policy_mismatch",
        ),
        (
            (payload.get("source_pins") or {}).get("training_base_sha") == policy.training_base_sha,
            "contract_training_base_mismatch",
        ),
        (
            math.isclose(
                _finite((payload.get("hardware") or {}).get("minimum_power_limit_w_per_gpu")) or 0,
                policy.minimum_power_limit_w,
            ),
            "contract_power_limit_mismatch",
        ),
        (
            _integer((payload.get("current_experiment") or {}).get("total_perf_steps_per_leg"))
            == 16,
            "contract_total_observations_mismatch",
        ),
        (
            _integer(
                (payload.get("current_experiment") or {}).get("discarded_warmup_steps_per_leg")
            )
            == 2,
            "contract_warmup_mismatch",
        ),
        (
            _integer((payload.get("current_experiment") or {}).get("measured_steps_per_leg")) == 14,
            "contract_measured_observations_mismatch",
        ),
        (
            _integer(
                (payload.get("budget") or {}).get(
                    "first_pair_deadline_seconds_from_allocation_start"
                )
            )
            == policy.first_pair_deadline_seconds,
            "contract_first_pair_deadline_mismatch",
        ),
        (
            _valid_sha256((payload.get("fixed_workload") or {}).get("dataset_manifest_sha256")),
            "contract_dataset_manifest_hash_missing",
        ),
        (
            (payload.get("budget") or {}).get("immediate_termination_receipt_required") is True,
            "contract_termination_receipt_requirement_missing",
        ),
        (
            (payload.get("authorization") or {}).get("supervisor_shutdown_script")
            == "scripts/lium_terminate_h100_pod.py"
            and (payload.get("authorization") or {}).get("termination_receipt_schema")
            == "lium-h100-termination-receipt/v1",
            "contract_shutdown_control_mismatch",
        ),
        (
            (payload.get("authorization") or {}).get("supervisor_shutdown_interpreter")
            == "/opt/homebrew/Cellar/python@3.11/3.11.14_3/Frameworks/Python.framework/Versions/3.11/bin/python3.11"
            and (payload.get("authorization") or {}).get("supervisor_shutdown_interpreter_sha256")
            == "5ca50299a6980ccfa9b12e582aa5262ef576dd5db23a8cf4595054e84f35f1b0"
            and (payload.get("authorization") or {}).get("supervisor_shutdown_interpreter_version")
            == "3.11.14",
            "contract_shutdown_interpreter_mismatch",
        ),
        (
            (payload.get("runtime_pins") or {}).get("lium_provider_version") == "1.3.0"
            and (payload.get("authorization") or {}).get("provider_output_schema")
            == "lium-h100-pod-create/v2"
            and (payload.get("authorization") or {}).get(
                "provider_terminal_reconciliation_receipt_schema"
            )
            == "h100-lium-terminal-reconciliation-receipt/v1"
            and (payload.get("authorization") or {}).get(
                "provider_terminal_reconciliation_retry_receipt_schema"
            )
            == "h100-lium-terminal-reconciliation-retry-receipt/v1"
            and (payload.get("authorization") or {}).get(
                "provider_terminal_reconciliation_lease_schema"
            )
            == "h100-lium-terminal-reconciliation-lease/v1"
            and (payload.get("authorization") or {}).get(
                "initial_terminal_reservation_binds_full_pre_snapshot"
            )
            is True
            and (payload.get("authorization") or {}).get("terminal_reconciliation_ownership")
            == "exclusive-kernel-flock"
            and (payload.get("authorization") or {}).get(
                "cleanup_retry_requires_consumed_claim_within_permit"
            )
            is True
            and (payload.get("authorization") or {}).get(
                "mutation_capable_provider_children_inherit_terminal_lease"
            )
            is True
            and (payload.get("authorization") or {}).get("provider_child_hard_timeout_required")
            is True
            and _integer(
                (payload.get("authorization") or {}).get("cleanup_child_hard_timeout_seconds")
            )
            == 120
            and (payload.get("authorization") or {}).get("provider_rent_boundary_evidence_required")
            is True
            and (payload.get("authorization") or {}).get("cleanup_retry_survives_gate0_expiry")
            is True,
            "contract_provider_terminal_control_mismatch",
        ),
        (
            {"auditor_key_id", "parent_decision_sha256"}.issubset(
                set((payload.get("audit_artifact") or {}).get("required_fields") or [])
            ),
            "contract_required_audit_fields_missing",
        ),
        (
            set((payload.get("audit_artifact") or {}).get("required_constituents") or [])
            == {
                "confirmation_decision",
                "grpo_decision",
                "contract",
                "termination_receipt",
            }
            and (payload.get("audit_artifact") or {}).get("termination_receipt_must_precede_audit")
            is True,
            "contract_audit_termination_binding_missing",
        ),
    )
    reasons.extend(reason for passed, reason in checks if not passed)
    return {
        "passed": not reasons,
        "reasons": reasons,
        "artifact": str(source),
        "sha256": _hash_file(source),
        "contract_id": payload.get("contract_id"),
        "claim_boundary": payload.get("claim_boundary"),
        "payload": payload,
    }


def _validate_hardware(path: str | Path, policy: SentryPolicy) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    try:
        payload = read_json(source)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {"passed": False, "reasons": ["hardware_missing_or_malformed"], "detail": str(exc)}
    parsed: list[dict[str, Any]] = []
    for row in payload.get("gpu_rows") or []:
        if isinstance(row, str):
            parts = [part.strip() for part in row.split(",")]
            if len(parts) >= 3:
                parsed.append(
                    {"index": _integer(parts[0]), "name": parts[1], "memory": _finite(parts[2])}
                )
    reasons: list[str] = []
    if len(parsed) != policy.required_gpu_count or {row["index"] for row in parsed} != set(
        range(8)
    ):
        reasons.append("hardware_gpu_count_or_indices_mismatch")
    if any(policy.required_gpu_name not in row["name"] for row in parsed):
        reasons.append("hardware_gpu_model_mismatch")
    memories = [row["memory"] for row in parsed]
    if not memories or any(
        value is None or value < policy.minimum_gpu_memory_mib for value in memories
    ):
        reasons.append("hardware_memory_below_minimum")
    operating_rows = payload.get("gpu_operating_rows")
    operating = operating_rows if isinstance(operating_rows, list) else []
    operating_indices: set[int] = set()
    power_limits: list[float] = []
    for row in operating:
        if not isinstance(row, Mapping):
            continue
        index = _integer(row.get("index"))
        clock = _positive(row.get("clocks.sm"))
        power_draw = _positive(row.get("power.draw"))
        power_limit = _positive(row.get("power.limit"))
        temperature = _finite(row.get("temperature.gpu"))
        if None in (index, clock, power_draw, power_limit, temperature):
            continue
        operating_indices.add(int(index))
        power_limits.append(float(power_limit))
        if _throttle_active(row.get("clocks_throttle_reasons.active")):
            reasons.append("hardware_preflight_throttling_detected")
    if (
        len(operating) != policy.required_gpu_count
        or operating_indices != set(range(policy.required_gpu_count))
        or len(power_limits) != len(operating)
    ):
        reasons.append("hardware_operating_snapshot_incomplete")
    if not power_limits or min(power_limits) < policy.minimum_power_limit_w:
        reasons.append("hardware_power_limit_below_minimum")
    topology = _ANSI_RE.sub("", str(payload.get("topology") or ""))
    gpu_lines = [line for line in topology.splitlines() if re.match(r"^GPU\d+\s", line)]
    edge_count = sum(
        len(re.findall(rf"\b{policy.required_topology}\b", line)) for line in gpu_lines
    )
    if len(gpu_lines) != 8 or edge_count < 56:
        reasons.append("hardware_NV18_topology_missing")
    repo_sha = str(payload.get("repo_sha") or "").strip()
    if not repo_sha:
        reasons.append("hardware_current_repo_sha_missing")
    if str(payload.get("training_base_sha") or "") != policy.training_base_sha:
        reasons.append("hardware_training_base_sha_mismatch")
    if str(payload.get("miles_sha") or "") != policy.miles_sha:
        reasons.append("hardware_miles_sha_mismatch")
    if str(payload.get("megatron_sha") or "") != policy.megatron_sha:
        reasons.append("hardware_megatron_sha_mismatch")
    return {
        "passed": not reasons,
        "reasons": reasons,
        "artifact": str(source),
        "repo_sha": repo_sha or None,
        "training_base_sha": payload.get("training_base_sha"),
        "miles_sha": payload.get("miles_sha"),
        "megatron_sha": payload.get("megatron_sha"),
        "minimum_memory_total_mib": min(
            (value for value in memories if value is not None), default=None
        ),
        "minimum_power_limit_w": min(power_limits, default=None),
        "gpu_count": len(parsed),
        "full_NV18": edge_count >= 56,
    }


def _validate_budget(
    path: str | Path, hardware: dict[str, Any], policy: SentryPolicy
) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    try:
        payload = read_json(source) if source.suffix == ".json" else read_key_value(source)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "passed": False,
            "invalid_reasons": ["budget_missing_or_malformed"],
            "within_budget": False,
            "detail": str(exc),
        }
    invalid: list[str] = []
    if str(payload.get("tranche_id") or "") != policy.required_tranche_id:
        invalid.append("budget_tranche_mismatch")
    if not str(payload.get("provider") or ""):
        invalid.append("budget_provider_missing")
    if not re.search(r"8\s*x\s*H100", str(payload.get("accelerators") or ""), re.I):
        invalid.append("budget_hardware_shape_mismatch")
    source_commit = str(payload.get("source_commit") or "")
    if not source_commit or source_commit != str(hardware.get("repo_sha") or ""):
        invalid.append("budget_current_repo_sha_mismatch")
    if payload.get("unused_budget_transfer_allowed") is not False:
        invalid.append("budget_transfer_policy_mismatch")
    hours = _finite(payload.get("uptime_hours", payload.get("planned_hours")))
    rate = _finite(payload.get("hourly_rate_usd"))
    spend = _finite(payload.get("reported_spend_usd"))
    projected = hours * rate if hours is not None and rate is not None else None
    if hours is None or rate is None:
        invalid.append("budget_hours_or_rate_missing")
    cost = spend if spend is not None else projected
    within = (
        not invalid
        and hours is not None
        and hours <= policy.maximum_node_hours
        and cost is not None
        and cost <= policy.maximum_usd
    )
    return {
        "passed": not invalid and within,
        "invalid_reasons": invalid,
        "within_budget": within,
        "artifact": str(source),
        "hours": hours,
        "cost_usd": cost,
        "maximum_node_hours": policy.maximum_node_hours,
        "maximum_usd": policy.maximum_usd,
        "source_commit": source_commit,
    }


def _timing_evidence(
    root: Path,
    receipt: dict[str, Any],
    policy: SentryPolicy,
    required_artifact: Path | None = None,
) -> dict[str, Any]:
    paths = sorted(root.rglob("wandb_readback.json"))
    if len(paths) != 1:
        return {
            "passed": False,
            "reasons": ["wandb_readback_missing_or_ambiguous"],
        }
    readback_path = paths[0]
    try:
        payload = read_json(readback_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {"passed": False, "reasons": ["wandb_readback_malformed"]}
    reasons: list[str] = []
    identity = {
        key: str(payload.get(key) or "")
        for key in ("entity", "project", "run_id", "experiment_id", "stage")
    }
    if payload.get("schema") != "h100-wandb-readback/v1":
        reasons.append("wandb_readback_schema_invalid")
    if payload.get("ok") is not True or payload.get("authenticated_api_read") is not True:
        reasons.append("wandb_authenticated_api_read_not_verified")
    if payload.get("errors") not in (None, []):
        reasons.append("wandb_readback_reports_errors")
    if any(not value for value in identity.values()):
        reasons.append("wandb_readback_identity_incomplete")
    local_timing = str(receipt.get("timing_status") or "")
    if local_timing != policy.required_timing_status:
        reasons.append("local_timing_status_not_verified")
    for receipt_key, identity_key in (
        ("wandb_entity", "entity"),
        ("wandb_project", "project"),
        ("wandb_run_id", "run_id"),
        ("experiment_id", "experiment_id"),
        ("wandb_stage", "stage"),
    ):
        recorded = str(receipt.get(receipt_key) or "")
        if recorded and recorded != identity[identity_key]:
            reasons.append(f"wandb_readback_{identity_key}_receipt_mismatch")
    remote = payload.get("remote") if isinstance(payload.get("remote"), dict) else {}
    summary = remote.get("summary") if isinstance(remote.get("summary"), dict) else {}
    config = remote.get("config") if isinstance(remote.get("config"), dict) else {}
    if remote.get("run_id") != identity["run_id"] or remote.get("state") != "finished":
        reasons.append("wandb_remote_run_identity_or_state_mismatch")
    if (
        summary.get("timing_status") != policy.required_timing_status
        or summary.get("experiment_id") != identity["experiment_id"]
        or summary.get("stage") != identity["stage"]
        or summary.get("status") != "success"
        or config.get("timing_status") != policy.required_timing_status
        or config.get("experiment_id") != identity["experiment_id"]
    ):
        reasons.append("wandb_remote_summary_or_config_mismatch")
    artifacts = remote.get("matching_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 1:
        reasons.append("wandb_remote_stage_artifact_missing_or_ambiguous")
        artifact: dict[str, Any] = {}
    else:
        artifact = artifacts[0] if isinstance(artifacts[0], dict) else {}
    metadata = artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}
    if not str(artifact.get("name") or "") or not str(artifact.get("digest") or ""):
        reasons.append("wandb_remote_artifact_identity_incomplete")
    if (
        metadata.get("experiment_id") != identity["experiment_id"]
        or metadata.get("stage") != identity["stage"]
        or metadata.get("status") != "success"
        or metadata.get("timing_status") != policy.required_timing_status
    ):
        reasons.append("wandb_remote_artifact_metadata_mismatch")
    run_id = identity["run_id"]
    evidence_paths = sorted(root.rglob(f"{run_id}.evidence_summary.json")) if run_id else []
    manifest_paths = sorted(root.rglob(f"{run_id}.artifact_manifest.json")) if run_id else []
    if len(evidence_paths) != 1 or len(manifest_paths) != 1:
        reasons.append("wandb_local_finalization_artifacts_missing_or_ambiguous")
        evidence_path = manifest_path = None
    else:
        evidence_path, manifest_path = evidence_paths[0], manifest_paths[0]
    local_hashes = payload.get("local_artifact_sha256")
    if not _valid_hash_map(local_hashes, {"evidence_summary", "artifact_manifest"}):
        reasons.append("wandb_local_artifact_hash_map_invalid")
        local_hashes = {}
    downloaded = (
        artifact.get("downloaded_files")
        if isinstance(artifact.get("downloaded_files"), dict)
        else {}
    )
    for name, local_path in (
        ("evidence_summary", evidence_path),
        ("artifact_manifest", manifest_path),
    ):
        if local_path is None:
            continue
        actual_hash = _hash_file(local_path)
        if local_hashes.get(name) != actual_hash:
            reasons.append(f"wandb_local_{name}_hash_mismatch")
        if downloaded.get(local_path.name) != actual_hash:
            reasons.append(f"wandb_remote_{name}_hash_mismatch")
    evidence: dict[str, Any] = {}
    artifact_manifest: dict[str, Any] = {}
    try:
        if evidence_path is not None:
            evidence = read_json(evidence_path)
        if manifest_path is not None:
            artifact_manifest = read_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError):
        reasons.append("wandb_local_finalization_artifact_malformed")
    if (
        evidence.get("timing_status") != policy.required_timing_status
        or evidence.get("experiment_id") != identity["experiment_id"]
    ):
        reasons.append("wandb_local_evidence_summary_mismatch")
    remote_metric_count = _integer(summary.get("metric_event_count"))
    local_metric_count = _integer(evidence.get("metric_event_count"))
    if (
        remote_metric_count is None
        or local_metric_count is None
        or remote_metric_count != local_metric_count
    ):
        reasons.append("wandb_remote_metric_count_mismatch")
    manifest_entries = artifact_manifest.get("files")
    remote_file_count = _integer(summary.get("artifact_file_count"))
    if (
        not isinstance(manifest_entries, list)
        or remote_file_count is None
        or remote_file_count != len(manifest_entries)
    ):
        reasons.append("wandb_remote_artifact_file_count_mismatch")
    if required_artifact is not None:
        required = required_artifact.resolve()
        matches = [
            item
            for item in manifest_entries or []
            if isinstance(item, dict) and item.get("name") == required.name
        ]
        if required.is_file():
            expected_hash = _hash_file(required)
            expected_size = required.stat().st_size
        else:
            expected_hash = None
            expected_size = None
        if len(matches) != 1 or expected_hash is None:
            reasons.append("wandb_artifact_manifest_required_file_mismatch")
        elif (
            matches[0].get("sha256") != expected_hash
            or _integer(matches[0].get("size_bytes")) != expected_size
        ):
            reasons.append("wandb_artifact_manifest_required_file_mismatch")
        if expected_hash is None or downloaded.get(required.name) != expected_hash:
            reasons.append("wandb_remote_required_artifact_hash_mismatch")
    return {
        "passed": not reasons,
        "reasons": sorted(set(reasons)),
        "artifact": str(readback_path),
        "identity": identity,
        "remote_summary": summary,
        "local_evidence_summary": evidence,
        "local_artifact_sha256": local_hashes,
    }


def _telemetry_evidence(
    root: Path, receipt: dict[str, Any], log_text: str, policy: SentryPolicy
) -> dict[str, Any]:
    paths = sorted(
        {
            *root.rglob("gpu_telemetry.csv"),
            *root.rglob("telemetry.csv"),
            *root.rglob("vram_usage.csv"),
        }
    )
    run_interval = _run_interval(receipt, log_text)
    missing_columns: list[str] = []
    for path in paths:
        try:
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                columns = reader.fieldnames or []
                selected = {
                    "timestamp": _column(
                        columns, lambda value: "timestamp" in value or value == "time"
                    ),
                    "index": _column(columns, lambda value: value in {"index", "gpu_index"}),
                    "clock": _column(
                        columns,
                        lambda value: "clock" in value and ("sm" in value or "graphics" in value),
                    ),
                    "power_draw": _column(
                        columns, lambda value: "power" in value and "limit" not in value
                    ),
                    "power_limit": _column(
                        columns, lambda value: "power" in value and "limit" in value
                    ),
                    "temperature": _column(
                        columns, lambda value: "temperature" in value or value.startswith("temp")
                    ),
                    "throttle": _column(
                        columns, lambda value: "throttle" in value or "clock_event_reason" in value
                    ),
                }
                if any(value is None for value in selected.values()):
                    missing_columns = [key for key, value in selected.items() if value is None]
                    continue
                rows = list(reader)
        except (OSError, csv.Error):
            continue
        times: list[datetime] = []
        per_gpu: dict[int, int] = {}
        throttle = False
        power_limit_below_minimum = False
        minimum_power_limit: float | None = None
        for row in rows:
            timestamp = _parse_time(row.get(selected["timestamp"] or ""))
            index = _integer(row.get(selected["index"] or ""))
            clock = _positive(row.get(selected["clock"] or ""))
            power_draw = _positive(row.get(selected["power_draw"] or ""))
            power_limit = _positive(row.get(selected["power_limit"] or ""))
            temperature = _finite(row.get(selected["temperature"] or ""))
            if (
                timestamp is None
                or index is None
                or clock is None
                or power_draw is None
                or power_limit is None
                or temperature is None
            ):
                continue
            times.append(timestamp)
            per_gpu[index] = per_gpu.get(index, 0) + 1
            minimum_power_limit = (
                power_limit
                if minimum_power_limit is None
                else min(minimum_power_limit, power_limit)
            )
            power_limit_below_minimum = (
                power_limit_below_minimum or power_limit < policy.minimum_power_limit_w
            )
            throttle = throttle or _throttle_active(row.get(selected["throttle"] or ""))
        coverage = set(per_gpu) == set(range(policy.required_gpu_count)) and all(
            count >= policy.minimum_telemetry_rows_per_gpu for count in per_gpu.values()
        )
        telemetry_interval = (min(times), max(times)) if times else None
        overlap = _interval_overlap_fraction(run_interval, telemetry_interval)
        duration = (
            (telemetry_interval[1] - telemetry_interval[0]).total_seconds()
            if telemetry_interval
            else 0.0
        )
        run_duration = (run_interval[1] - run_interval[0]).total_seconds() if run_interval else None
        meaningful_duration = (
            run_duration is not None
            and run_duration > 0
            and duration >= run_duration * policy.minimum_telemetry_overlap_fraction
        )
        reasons: list[str] = []
        if not coverage:
            reasons.append("telemetry_all_gpu_row_coverage_insufficient")
        if not meaningful_duration:
            reasons.append("telemetry_duration_insufficient")
        if overlap < policy.minimum_telemetry_overlap_fraction:
            reasons.append("telemetry_does_not_overlap_raw_run_wall_time")
        if throttle:
            reasons.append("telemetry_throttling_detected")
        if power_limit_below_minimum:
            reasons.append("telemetry_power_limit_below_minimum")
        return {
            "passed": not reasons,
            "reasons": reasons,
            "artifact": str(path),
            "rows_per_gpu": per_gpu,
            "duration_s": duration,
            "run_duration_s": run_duration,
            "overlap_fraction": overlap,
            "throttling_detected": throttle,
            "minimum_power_limit_w": minimum_power_limit,
        }
    return {
        "passed": False,
        "reasons": ["telemetry_required_columns_missing"],
        "missing_columns": missing_columns,
    }


def _run_interval(receipt: dict[str, Any], log_text: str) -> tuple[datetime, datetime] | None:
    start = _parse_time(receipt.get("run_started_at_utc"))
    end = _parse_time(receipt.get("run_finished_at_utc"))
    if start and end and end > start:
        return start, end
    matches = re.findall(r"(20\d\d[-/]\d\d[-/]\d\d[ T]\d\d:\d\d:\d\d(?:\.\d+)?)", log_text)
    parsed = [value for value in (_parse_time(item) for item in matches) if value is not None]
    if len(parsed) >= 2 and max(parsed) > min(parsed):
        return min(parsed), max(parsed)
    return None


def _validate_prior(
    path: str | Path,
    expected_stage: Stage,
    security: SentrySecurity | None,
) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    try:
        payload = read_json(source)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "passed": False,
            "reasons": ["prior_decision_missing_or_malformed"],
            "detail": str(exc),
            "payload": {},
        }
    reasons: list[str] = []
    if security is None:
        reasons.append("prior_signature_trust_configuration_missing")
    else:
        try:
            verify_signed_decision(
                source,
                security.sentry_public_key_path,
                expected_stage=expected_stage,
                expected_signer_principal=security.sentry_principal,
                expected_verifier_principal=security.executor_principal,
                now=security.now,
            )
        except (DecisionSecurityError, ValueError) as exc:
            reasons.append(f"prior_signature_invalid:{exc}")
        reasons.extend(_signed_parent_chain_reasons(payload, expected_stage))
        reasons.extend(_signed_contract_binding_reasons(payload, expected_stage))
    identity = _sentry_identity()
    if payload.get("output_schema") != _OUTPUT_SCHEMA or payload.get("schema_version") != 3:
        reasons.append("prior_decision_schema_invalid")
    if (
        payload.get("stage") != expected_stage.value
        or payload.get("decision") != Decision.PROMOTABLE.value
    ):
        reasons.append("prior_stage_not_promotable")
    if payload.get("exit_status") != 0:
        reasons.append("prior_stage_exit_status_invalid")
    sentry = payload.get("sentry") or {}
    if sentry.get("authored_by") != _AUTHOR:
        reasons.append("prior_decision_not_sentry_authored")
    if (
        sentry.get("source_sha256") != identity["source_sha256"]
        or sentry.get("script_sha256") != identity["script_sha256"]
    ):
        reasons.append("prior_decision_sentry_source_stale")
    timestamp = _parse_time(payload.get("generated_at_utc"))
    if timestamp is None or timestamp > datetime.now(timezone.utc) + timedelta(minutes=5):
        reasons.append("prior_decision_timestamp_invalid")
    for item in (payload.get("provenance") or {}).get("inputs", []):
        if not isinstance(item, dict):
            reasons.append("prior_decision_input_provenance_invalid")
            continue
        input_path = Path(str(item.get("path") or ""))
        if not input_path.exists() or _hash_path(input_path) != item.get("sha256"):
            reasons.append("prior_decision_input_artifact_stale")
    return {
        "passed": not reasons,
        "reasons": sorted(set(reasons)),
        "artifact": str(source),
        "payload": payload,
    }


def _signed_parent_chain_reasons(payload: dict[str, Any], stage: Stage) -> list[str]:
    role = {
        Stage.PREFLIGHT: "gate0_permit",
        Stage.SCREEN: "preflight_decision",
        Stage.PROMOTION: "screen_decision",
        Stage.CONFIRMATION: "promotion_decision",
        Stage.GRPO: "confirmation_decision",
        Stage.FINAL: "grpo_decision",
    }[stage]
    expected_parent = next(
        (
            str(item.get("sha256") or "")
            for item in (payload.get("provenance") or {}).get("inputs", [])
            if isinstance(item, dict) and item.get("role") == role
        ),
        "",
    )
    if stage is Stage.PREFLIGHT:
        expected_request = str(
            (((payload.get("context") or {}).get("gate0") or {}).get("booking_request_sha256"))
            or ""
        )
    else:
        expected_request = _nearest_request_hash(
            ((payload.get("prior_stage") or {}).get("payload") or {})
        )
    reasons: list[str] = []
    if payload.get("parent_decision_sha256") != expected_parent:
        reasons.append("prior_signed_parent_decision_mismatch")
    if payload.get("parent_request_sha256") != expected_request:
        reasons.append("prior_signed_parent_request_mismatch")
    return reasons


def _signed_contract_binding_reasons(payload: dict[str, Any], stage: Stage) -> list[str]:
    bound = payload.get("acceptance_contract_sha256")
    reasons: list[str] = []
    if not _valid_sha256(bound):
        return ["prior_acceptance_contract_hash_missing"]
    context = payload.get("context")
    if isinstance(context, Mapping) and context.get("acceptance_contract_sha256") != bound:
        reasons.append("prior_acceptance_contract_context_mismatch")
    if stage is Stage.PREFLIGHT:
        contract_hash = next(
            (
                item.get("sha256")
                for item in (payload.get("provenance") or {}).get("inputs", [])
                if isinstance(item, Mapping) and item.get("role") == "contract"
            ),
            None,
        )
        if contract_hash != bound:
            reasons.append("prior_acceptance_contract_provenance_mismatch")
    else:
        prior_payload = (payload.get("prior_stage") or {}).get("payload") or {}
        if prior_payload.get("acceptance_contract_sha256") != bound:
            reasons.append("prior_acceptance_contract_parent_mismatch")
    return reasons


def _validate_termination_receipt(
    receipt_path: str | Path,
    *,
    expected_gate0: Any,
) -> dict[str, Any]:
    source = Path(receipt_path).expanduser().resolve()
    try:
        payload = read_json(source)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "passed": False,
            "reasons": ["termination_receipt_missing_or_malformed"],
            "detail": str(exc),
            "verified_inputs": [],
        }
    reasons: list[str] = []
    gate0 = expected_gate0 if isinstance(expected_gate0, Mapping) else {}
    status = payload.get("status")
    started = _parse_time(payload.get("started_at_utc"))
    finished = _parse_time(payload.get("finished_at_utc"))
    if (
        payload.get("schema") != "lium-h100-termination-receipt/v1"
        or status not in {"TERMINATED", "ALREADY_ABSENT"}
        or started is None
        or finished is None
        or finished < started
    ):
        reasons.append("termination_receipt_status_or_timeline_invalid")
    allocation = payload.get("allocation") if isinstance(payload.get("allocation"), Mapping) else {}
    expected_id = str(gate0.get("allocation_id") or "")
    expected_name = str(gate0.get("allocation_name") or "")
    if (
        not expected_id
        or not expected_name
        or allocation.get("id") != expected_id
        or allocation.get("name") != expected_name
    ):
        reasons.append("termination_receipt_gate0_allocation_mismatch")
    source_binding = payload.get("source") if isinstance(payload.get("source"), Mapping) else {}
    provider_path = _resolve_audit_path(source.parent, source_binding.get("provider_output_path"))
    launch_path = _resolve_audit_path(source.parent, source_binding.get("launch_receipt_path"))
    verified_inputs: list[dict[str, str]] = []
    if (
        provider_path is None
        or source_binding.get("provider_output_sha256") != gate0.get("provider_output_sha256")
        or _hash_file(provider_path) != source_binding.get("provider_output_sha256")
    ):
        reasons.append("termination_receipt_provider_output_binding_invalid")
        provider: dict[str, Any] = {}
    else:
        verified_inputs.append({"role": "termination_provider_output", "path": str(provider_path)})
        try:
            provider = read_json(provider_path)
        except (OSError, ValueError, json.JSONDecodeError):
            provider = {}
            reasons.append("termination_receipt_provider_output_malformed")
    if (
        launch_path is None
        or source_binding.get("launch_receipt_sha256") != gate0.get("launch_receipt_sha256")
        or _hash_file(launch_path) != source_binding.get("launch_receipt_sha256")
    ):
        reasons.append("termination_receipt_launch_receipt_binding_invalid")
        launch: dict[str, Any] = {}
    else:
        verified_inputs.append({"role": "termination_launch_receipt", "path": str(launch_path)})
        try:
            launch = read_json(launch_path)
        except (OSError, ValueError, json.JSONDecodeError):
            launch = {}
            reasons.append("termination_receipt_launch_receipt_malformed")
    pod = provider.get("pod") if isinstance(provider.get("pod"), Mapping) else {}
    reconciliation = (
        provider.get("create_reconciliation")
        if isinstance(provider.get("create_reconciliation"), Mapping)
        else {}
    )
    if (
        provider.get("schema") != "lium-h100-pod-create/v2"
        or provider.get("status") != "RUNNING"
        or pod.get("id") != expected_id
        or pod.get("name") != expected_name
        or reconciliation.get("status") != "CONFIRMED_UNIQUE"
        or reconciliation.get("pod_id") != expected_id
        or reconciliation.get("allocation_name") != expected_name
        or reconciliation.get("final_active_pod_ids") != [expected_id]
    ):
        reasons.append("termination_receipt_provider_allocation_mismatch")
    launch_output = (
        launch.get("provider_output") if isinstance(launch.get("provider_output"), Mapping) else {}
    )
    launch_allocation = (
        launch.get("allocation") if isinstance(launch.get("allocation"), Mapping) else {}
    )
    if (
        launch.get("schema") != LAUNCH_RECEIPT_SCHEMA
        or launch.get("status") != "COMPLETED"
        or provider_path is None
        or launch_output.get("sha256") != gate0.get("provider_output_sha256")
        or _integer(launch_output.get("size_bytes")) != provider_path.stat().st_size
        or _resolve_audit_path(launch_path.parent, launch_output.get("path")) != provider_path
        or launch_allocation.get("name") != expected_name
    ):
        reasons.append("termination_receipt_launch_allocation_mismatch")
    preflight = payload.get("preflight") if isinstance(payload.get("preflight"), Mapping) else {}
    postflight = payload.get("postflight") if isinstance(payload.get("postflight"), Mapping) else {}
    snapshot_fields_valid = all(
        snapshot.get("identity_conflict") is False
        and _integer(snapshot.get("id_conflict_count")) == 0
        and _integer(snapshot.get("name_conflict_count")) == 0
        for snapshot in (preflight, postflight)
    )
    if (
        not snapshot_fields_valid
        or postflight.get("target_present") is not False
        or postflight.get("confirmed_absent") is not True
        or (_integer(postflight.get("poll_attempts")) or 0) not in range(1, 6)
        or (status == "TERMINATED" and preflight.get("target_present") is not True)
        or (status == "ALREADY_ABSENT" and preflight.get("target_present") is not False)
    ):
        reasons.append("termination_receipt_absence_proof_invalid")
    return {
        "passed": not reasons,
        "reasons": sorted(set(reasons)),
        "artifact": str(source),
        "status": status,
        "allocation_id": allocation.get("id"),
        "allocation_name": allocation.get("name"),
        "confirmed_absent": postflight.get("confirmed_absent"),
        "verified_inputs": verified_inputs,
    }


def _validate_audit(
    audit_path: str | Path,
    *,
    contract_path: str | Path,
    confirmation_decision_path: str | Path,
    grpo_decision_path: str | Path,
    termination_receipt_path: str | Path,
    contract: dict[str, Any],
    security: SentrySecurity | None,
) -> dict[str, Any]:
    source = Path(audit_path).expanduser().resolve()
    try:
        payload = read_json(source)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {
            "passed": False,
            "reasons": ["audit_missing_or_malformed"],
            "detail": str(exc),
            "verified_inputs": [],
        }
    reasons: list[str] = []
    if (
        security is None
        or security.auditor_public_key_path is None
        or not security.auditor_principal
    ):
        reasons.append("audit_signature_trust_missing")
        audit_signature: dict[str, Any] = {}
    else:
        try:
            audit_signature = _verify_bounded_payload(
                payload,
                public_key_path=security.auditor_public_key_path,
                domain=AUDIT_DECISION_DOMAIN,
                expected_signer_principal=security.auditor_principal,
                expected_verifier_principal=security.sentry_principal,
                now=security.now,
            )
        except DecisionSecurityError as exc:
            audit_signature = {}
            reasons.append(f"audit_signature_invalid:{exc}")
        try:
            sentry_key = load_public_key_document(security.sentry_public_key_path)
            auditor_key = load_public_key_document(security.auditor_public_key_path)
            if sentry_key.key_id == auditor_key.key_id:
                reasons.append("audit_sentry_key_reuse_forbidden")
        except PermitError as exc:
            reasons.append(f"audit_key_identity_invalid:{exc}")
        if security.auditor_principal == security.sentry_principal:
            reasons.append("audit_self_signing_forbidden")
    if payload.get("decision") != "ACCEPT":
        reasons.append("audit_decision_not_ACCEPT")
    if payload.get("auditor_key_id") != audit_signature.get("key_id"):
        reasons.append("audit_auditor_key_id_mismatch")
    expected_parent = _hash_file(Path(grpo_decision_path).expanduser().resolve())
    if payload.get("parent_decision_sha256") != expected_parent:
        reasons.append("audit_parent_decision_sha256_mismatch")
    if payload.get("auditor_role") != "independent_auditor" or not str(
        payload.get("auditor_identity") or ""
    ):
        reasons.append("audit_identity_or_role_invalid")
    timestamp = _parse_time(payload.get("auditor_timestamp_utc"))
    if timestamp is None:
        reasons.append("audit_timestamp_invalid")
    if str(payload.get("bounded_claim") or "") != str(contract.get("claim_boundary") or ""):
        reasons.append("audit_bounded_claim_mismatch")
    base = source.parent
    manifest = _resolve_audit_path(base, payload.get("manifest_path"))
    verified_inputs: list[dict[str, str]] = []
    if manifest is None or _hash_path(manifest) != payload.get("manifest_sha256"):
        reasons.append("audit_manifest_checksum_mismatch")
        manifest_payload: dict[str, Any] = {}
    else:
        verified_inputs.append({"role": "audit_manifest", "path": str(manifest)})
        try:
            manifest_payload = read_json(manifest)
        except (OSError, ValueError, json.JSONDecodeError):
            manifest_payload = {}
            reasons.append("audit_manifest_malformed")
    if manifest_payload.get("schema_version") != 1:
        reasons.append("audit_manifest_schema_invalid")
    audit_constituents, audit_constituent_reasons = _audit_constituent_map(
        payload.get("constituent_checksums")
    )
    manifest_constituents, manifest_constituent_reasons = _audit_constituent_map(
        manifest_payload.get("constituent_checksums")
    )
    reasons.extend(audit_constituent_reasons)
    reasons.extend(f"audit_manifest_{reason}" for reason in manifest_constituent_reasons)
    expected_paths = {
        "confirmation_decision": Path(confirmation_decision_path).expanduser().resolve(),
        "grpo_decision": Path(grpo_decision_path).expanduser().resolve(),
        "contract": Path(contract_path).expanduser().resolve(),
        "termination_receipt": Path(termination_receipt_path).expanduser().resolve(),
    }
    for role, expected_path in expected_paths.items():
        expected_hash = _hash_file(expected_path) if expected_path.is_file() else None
        audit_item = audit_constituents.get(role)
        manifest_item = manifest_constituents.get(role)
        if audit_item is None:
            reasons.append(f"audit_required_constituent_missing:{role}")
        else:
            audit_resolved = _resolve_audit_path(base, audit_item.get("path"))
            if (
                audit_resolved != expected_path
                or expected_hash is None
                or audit_item.get("sha256") != expected_hash
            ):
                reasons.append(f"audit_required_constituent_mismatch:{role}")
            else:
                verified_inputs.append(
                    {"role": f"audit_constituent:{role}", "path": str(audit_resolved)}
                )
        if manifest_item is None:
            reasons.append(f"audit_manifest_required_constituent_missing:{role}")
            continue
        manifest_resolved = _resolve_audit_path(manifest.parent, manifest_item.get("path"))
        if (
            manifest_resolved != expected_path
            or expected_hash is None
            or manifest_item.get("sha256") != expected_hash
            or audit_item is None
            or manifest_item != audit_item
        ):
            reasons.append(f"audit_manifest_required_constituent_mismatch:{role}")
    termination_item = audit_constituents.get("termination_receipt")
    manifest_termination_item = manifest_constituents.get("termination_receipt")
    termination_path = expected_paths["termination_receipt"]
    termination_hash = _hash_file(termination_path) if termination_path.is_file() else None
    termination_is_exact_constituent = (
        termination_item is not None
        and manifest_termination_item == termination_item
        and _resolve_audit_path(base, termination_item.get("path")) == termination_path
        and termination_item.get("sha256") == termination_hash
    )
    if termination_is_exact_constituent and timestamp is not None:
        try:
            termination_payload = read_json(termination_path)
        except (OSError, ValueError, json.JSONDecodeError):
            termination_payload = {}
        termination_finished_at = _parse_time(termination_payload.get("finished_at_utc"))
        if termination_finished_at is None:
            reasons.append("audit_termination_finished_at_invalid")
        elif termination_finished_at > timestamp:
            reasons.append("audit_termination_finished_after_auditor_timestamp")
    if _hash_path(Path(contract_path).resolve()) != payload.get("contract_sha256"):
        reasons.append("audit_contract_checksum_mismatch")
    return {
        "passed": not reasons,
        "reasons": sorted(set(reasons)),
        "artifact": str(source),
        "decision": payload.get("decision"),
        "auditor_identity": payload.get("auditor_identity"),
        "auditor_timestamp_utc": payload.get("auditor_timestamp_utc"),
        "bounded_claim": payload.get("bounded_claim"),
        "key_id": audit_signature.get("key_id"),
        "verified_inputs": verified_inputs,
    }


def _audit_constituent_map(value: Any) -> tuple[dict[str, dict[str, Any]], list[str]]:
    if not isinstance(value, list) or not value:
        return {}, ["constituent_checksums_missing"]
    result: dict[str, dict[str, Any]] = {}
    reasons: list[str] = []
    for item in value:
        if (
            not isinstance(item, dict)
            or not str(item.get("role") or "")
            or not str(item.get("path") or "")
            or not _valid_sha256(item.get("sha256"))
        ):
            reasons.append("constituent_checksum_entry_invalid")
            continue
        role = str(item["role"])
        if role in result:
            reasons.append("constituent_checksum_role_duplicate")
            continue
        result[role] = item
    return result, reasons


def _envelope(
    stage: Stage, decision: Decision, reasons: Iterable[str], policy: SentryPolicy
) -> dict[str, Any]:
    next_stage = {
        Stage.PREFLIGHT: Stage.SCREEN,
        Stage.SCREEN: Stage.PROMOTION,
        Stage.PROMOTION: Stage.CONFIRMATION,
        Stage.CONFIRMATION: Stage.GRPO,
        Stage.GRPO: Stage.FINAL,
    }.get(stage)
    return {
        "schema_version": 3,
        "output_schema": _OUTPUT_SCHEMA,
        "stage": stage.value,
        "decision": decision.value,
        "reasons": sorted(set(reasons)),
        "allow_next_stage": decision is Decision.PROMOTABLE and next_stage is not None,
        "next_stage": next_stage.value if decision is Decision.PROMOTABLE and next_stage else None,
        "accepted": decision is Decision.VERIFIED,
        "stop": decision is not Decision.PROMOTABLE,
        "policy": asdict(policy),
    }


def _finish(
    result: dict[str, Any],
    stage: Stage,
    inputs: Sequence[tuple[str, str | Path]],
    command: str | None,
    security: SentrySecurity | None,
) -> dict[str, Any]:
    if security is None:
        raise DecisionSecurityError("sentry signing configuration is required")
    identity = _sentry_identity()
    result["generated_at_utc"] = _format_security_time(_security_now(security.now))
    result["exact_command"] = command or f"library:{stage.value}"
    result["sentry"] = {"authored_by": _AUTHOR, **identity}
    result["provenance"] = {
        "inputs": [
            {
                "role": role,
                "path": str(Path(path).expanduser().resolve()),
                "sha256": _hash_path(Path(path).expanduser().resolve()),
            }
            for role, path in inputs
        ]
    }
    result["exit_status"] = _exit_status(Decision(result["decision"]))
    contract_sha256 = _result_contract_sha256(result)
    if _valid_sha256(contract_sha256):
        result["acceptance_contract_sha256"] = contract_sha256
    parent_decision, parent_request = _decision_parent_hashes(result, stage)
    if not _valid_sha256(parent_decision) or not _valid_sha256(parent_request):
        raise DecisionSecurityError("decision parent chain is incomplete")
    result["parent_decision_sha256"] = parent_decision
    result["parent_request_sha256"] = parent_request
    return sign_bounded_payload(
        result,
        private_key_path=security.signing_private_key_path,
        public_key_path=security.sentry_public_key_path,
        domain=_DECISION_DOMAINS[stage],
        signer_principal=security.sentry_principal,
        verifier_principal=security.executor_principal,
        issued_at=security.now,
        lifetime_seconds=security.decision_ttl_seconds,
    )


def _result_contract_sha256(result: Mapping[str, Any]) -> str:
    direct = result.get("acceptance_contract_sha256")
    if _valid_sha256(direct):
        return str(direct)
    context = result.get("context")
    if isinstance(context, Mapping) and _valid_sha256(context.get("acceptance_contract_sha256")):
        return str(context["acceptance_contract_sha256"])
    prior = result.get("prior_stage")
    if isinstance(prior, Mapping) and isinstance(prior.get("payload"), Mapping):
        return _result_contract_sha256(prior["payload"])
    confirmation = result.get("confirmation")
    if isinstance(confirmation, Mapping) and isinstance(confirmation.get("payload"), Mapping):
        return _result_contract_sha256(confirmation["payload"])
    return ""


def _decision_parent_hashes(result: dict[str, Any], stage: Stage) -> tuple[str, str]:
    if stage is Stage.PREFLIGHT:
        gate0 = (result.get("context") or {}).get("gate0") or {}
        return str(gate0.get("permit_sha256") or ""), str(gate0.get("booking_request_sha256") or "")
    role = {
        Stage.SCREEN: "preflight_decision",
        Stage.PROMOTION: "screen_decision",
        Stage.CONFIRMATION: "promotion_decision",
        Stage.GRPO: "confirmation_decision",
        Stage.FINAL: "grpo_decision",
    }[stage]
    parent_decision = next(
        (
            str(item.get("sha256") or "")
            for item in (result.get("provenance") or {}).get("inputs", [])
            if isinstance(item, dict) and item.get("role") == role
        ),
        "",
    )
    if stage is Stage.FINAL:
        parent_payload = (result.get("grpo") or {}).get("payload") or {}
    else:
        parent_payload = (result.get("prior_stage") or {}).get("payload") or {}
    return parent_decision, _nearest_request_hash(parent_payload)


def _nearest_request_hash(payload: Mapping[str, Any]) -> str:
    direct = payload.get("request_sha256")
    if _valid_sha256(direct):
        return str(direct)
    prior = payload.get("prior_stage")
    if isinstance(prior, Mapping) and isinstance(prior.get("payload"), Mapping):
        return _nearest_request_hash(prior["payload"])
    return str(payload.get("parent_request_sha256") or "")


def _sentry_identity() -> dict[str, str]:
    source = Path(__file__).resolve()
    script = source.parents[3] / "scripts" / "h100_research_sentry.py"
    return {
        "source_path": str(source),
        "source_sha256": _hash_file(source),
        "script_path": str(script),
        "script_sha256": _hash_file(script) if script.is_file() else "",
    }


def _exit_status(decision: Decision) -> int:
    if decision in {Decision.PROMOTABLE, Decision.VERIFIED}:
        return 0
    if decision is Decision.INVALID:
        return 3
    return 2


def _resolve_summary(path: str | Path) -> Path:
    source = Path(path).expanduser().resolve()
    if source.is_file():
        return source
    matches = sorted(source.rglob("trial_summary.json")) if source.is_dir() else []
    if len(matches) != 1:
        raise ValueError("canonical_trial_summary_missing_or_ambiguous")
    return matches[0]


def _trial_root(path: str | Path) -> Path:
    source = Path(path).expanduser().resolve()
    return source.parent if source.is_file() else source


def _find_component(root: Path, recorded: Any, filename: str) -> Path:
    if isinstance(recorded, str) and Path(recorded).is_file():
        return Path(recorded).resolve()
    matches = sorted(root.rglob(filename))
    if len(matches) != 1:
        raise ValueError(f"{filename}_missing_or_ambiguous")
    return matches[0]


def _find_one(root: Path, pattern: str) -> Path:
    matches = sorted(root.rglob(pattern))
    if len(matches) != 1:
        raise ValueError(f"{pattern}_missing_or_ambiguous")
    return matches[0]


def _trial_public(trial: _Trial) -> dict[str, Any]:
    return {
        "artifact": str(trial.root),
        "summary": str(trial.summary_path),
        "valid": trial.valid,
        "reasons": list(trial.reasons),
        "timing": trial.timing,
        "telemetry": trial.telemetry,
        "peak_vram_mib": trial.canonical.get("peak_vram_mib"),
    }


def _finite_training(summary: dict[str, Any]) -> bool:
    values = [
        summary.get("actor_tflops_per_gpu_median"),
        summary.get("global_actor_tok_s_median"),
        summary.get("loss_median"),
        summary.get("grad_norm_median"),
        *(summary.get("loss_values") or []),
        *(summary.get("grad_norm_values") or []),
    ]
    return bool(values) and all(_finite(value) is not None for value in values)


def _without_dispatcher(config: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in config.items()
        if key not in {"moe_token_dispatcher_type", "moe_enable_deepep"}
    }


def _prior_input_matches(payload: dict[str, Any], role: str, path: str | Path) -> bool:
    expected_path = _trial_root(path).resolve()
    expected_hash = _hash_path(expected_path)
    return any(
        item.get("role") == role
        and Path(str(item.get("path") or "")).resolve() == expected_path
        and item.get("sha256") == expected_hash
        for item in (payload.get("provenance") or {}).get("inputs", [])
        if isinstance(item, dict)
    )


def _provenance_input_matches_exact(payload: dict[str, Any], role: str, path: str | Path) -> bool:
    expected_path = Path(path).expanduser().resolve()
    expected_hash = _hash_path(expected_path)
    return any(
        item.get("role") == role
        and Path(str(item.get("path") or "")).expanduser().resolve() == expected_path
        and item.get("sha256") == expected_hash
        for item in (payload.get("provenance") or {}).get("inputs", [])
        if isinstance(item, dict)
    )


def _column(columns: Sequence[str], predicate: Any) -> str | None:
    for column in columns:
        normalized = re.sub(r"[^a-z0-9]+", "_", column.lower()).strip("_")
        if predicate(normalized):
            return column
    return None


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00").replace("/", "-")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _interval_overlap_fraction(
    run: tuple[datetime, datetime] | None,
    telemetry: tuple[datetime, datetime] | None,
) -> float:
    if run is None or telemetry is None:
        return 0.0
    duration = (run[1] - run[0]).total_seconds()
    if duration <= 0:
        return 0.0
    overlap = (min(run[1], telemetry[1]) - max(run[0], telemetry[0])).total_seconds()
    return max(0.0, overlap) / duration


def _throttle_active(value: Any) -> bool:
    return str(value or "").strip().lower() not in {
        "",
        "0",
        "0x0",
        "0x0000000000000000",
        "false",
        "no",
        "none",
        "not active",
        "inactive",
    }


def _fingerprint_value(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("sha256", value.get("fingerprint"))
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        return None
    return value.lower()


def _resolve_audit_path(base: Path, value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    path = path.resolve()
    return path if path.exists() else None


def _one_sided_t95(degrees_of_freedom: int) -> float:
    if degrees_of_freedom <= 30:
        return _ONE_SIDED_T95[max(1, degrees_of_freedom)]
    return 1.644854


def _lower_percentile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(probability * len(ordered)) - 1)
    return ordered[index]


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _hash_path(path: Path) -> str | None:
    if path.is_file():
        return _hash_file(path)
    if not path.is_dir():
        return None
    digest = hashlib.sha256()
    for item in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        digest.update(str(item.relative_to(path)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(_hash_file(item).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _positive(value: Any) -> float | None:
    number = _finite(value)
    return number if number is not None and number > 0 else None


def _integer(value: Any) -> int | None:
    number = _finite(value)
    return int(number) if number is not None and number.is_integer() else None


def _truthy(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _equivalent(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return (
            math.isfinite(float(left))
            and math.isfinite(float(right))
            and math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9)
        )
    if isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        return all(_equivalent(a, b) for a, b in zip(left, right))
    if isinstance(left, dict) and isinstance(right, dict) and left.keys() == right.keys():
        return all(_equivalent(left[key], right[key]) for key in left)
    return left == right


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=[stage.value for stage in Stage])
    parser.add_argument("--contract")
    parser.add_argument("--hardware")
    parser.add_argument("--budget")
    parser.add_argument("--preflight-decision")
    parser.add_argument("--screen-decision")
    parser.add_argument("--promotion-decision")
    parser.add_argument("--confirmation-decision")
    parser.add_argument("--grpo-decision")
    parser.add_argument("--control", action="append", default=[])
    parser.add_argument("--candidate", action="append", default=[])
    parser.add_argument("--grpo-artifact")
    parser.add_argument("--audit")
    parser.add_argument("--termination-receipt")
    parser.add_argument("--request")
    parser.add_argument("--gate0-permit")
    parser.add_argument("--gate0-public-key")
    parser.add_argument("--launch-receipt")
    parser.add_argument("--booking-request")
    parser.add_argument("--provider-output")
    parser.add_argument("--signing-key", required=True)
    parser.add_argument("--sentry-public-key", required=True)
    parser.add_argument("--sentry-principal", required=True)
    parser.add_argument("--executor-principal", required=True)
    parser.add_argument("--supervisor-public-key")
    parser.add_argument("--supervisor-principal")
    parser.add_argument("--auditor-public-key")
    parser.add_argument("--auditor-principal")
    parser.add_argument("--output")
    return parser


def signature_domain_for_kind(kind: str) -> bytes:
    if kind == "gate0-permit":
        return GATE0_SIGNATURE_DOMAIN
    if kind == "t2-authorization":
        return T2_AUTHORIZATION_DOMAIN
    if kind == "audit":
        return AUDIT_DECISION_DOMAIN
    try:
        return _DECISION_DOMAINS[Stage(kind)]
    except ValueError as exc:
        raise DecisionSecurityError(f"unsupported signing kind: {kind}") from exc


def build_signing_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sign one bounded H100 research decision or authorization"
    )
    parser.add_argument(
        "kind",
        choices=[stage.value for stage in Stage] + ["gate0-permit", "t2-authorization", "audit"],
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--private-key", required=True)
    parser.add_argument("--public-key", required=True)
    parser.add_argument("--gate1-public-key")
    parser.add_argument("--parent-request")
    parser.add_argument("--signer-principal", required=True)
    parser.add_argument("--verifier-principal", required=True)
    parser.add_argument("--request-id")
    parser.add_argument("--nonce")
    parser.add_argument("--issued-at")
    parser.add_argument("--expires-at")
    parser.add_argument("--lifetime-seconds", type=int, default=1800)
    return parser


def signing_main(argv: Sequence[str] | None = None) -> int:
    args = build_signing_parser().parse_args(argv)
    source = Path(args.input).expanduser().resolve()
    destination = Path(args.output).expanduser().resolve()
    try:
        payload = read_json(source)
        if not isinstance(payload, dict):
            raise DecisionSecurityError("signing input must be a JSON object")
        if args.kind in {stage.value for stage in Stage} and payload.get("stage") != args.kind:
            raise DecisionSecurityError("decision stage does not match signing kind")
        if destination.exists():
            raise DecisionSecurityError("signing output already exists")
        if args.kind == "gate0-permit":
            if not args.parent_request:
                raise DecisionSecurityError("Gate0 signing requires --parent-request")
            if not args.gate1_public_key:
                raise DecisionSecurityError("Gate0 signing requires --gate1-public-key")
            if any((args.request_id, args.nonce, args.issued_at, args.expires_at)):
                raise DecisionSecurityError(
                    "Gate0 identity and validity fields must come from the exact payload"
                )
            signed = sign_gate0_permit_payload(
                payload,
                private_key_path=args.private_key,
                public_key_path=args.public_key,
                gate1_public_key_path=args.gate1_public_key,
                parent_request_path=args.parent_request,
                expected_sentry_principal=args.signer_principal,
                expected_executor_principal=args.verifier_principal,
            )
        else:
            issued_at = _parse_cli_security_time(args.issued_at) if args.issued_at else None
            expires_at = _parse_cli_security_time(args.expires_at) if args.expires_at else None
            signed = sign_bounded_payload(
                payload,
                private_key_path=args.private_key,
                public_key_path=args.public_key,
                domain=signature_domain_for_kind(args.kind),
                signer_principal=args.signer_principal,
                verifier_principal=args.verifier_principal,
                request_id=args.request_id,
                nonce=args.nonce,
                issued_at=issued_at,
                expires_at=expires_at,
                lifetime_seconds=args.lifetime_seconds,
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(signed, indent=2, sort_keys=True, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        DecisionSecurityError,
        PermitError,
    ) as exc:
        print(f"signing failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": "signed", "output": str(destination)}))
    return 0


def _parse_cli_security_time(value: str) -> datetime:
    parsed = _parse_time(value)
    if parsed is None:
        raise DecisionSecurityError("CLI timestamp must be ISO-8601 UTC")
    return parsed


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    args = build_parser().parse_args(raw_argv)
    command = shlex.join([str(Path(sys.argv[0]).resolve()), *raw_argv])
    security = SentrySecurity(
        signing_private_key_path=args.signing_key,
        sentry_public_key_path=args.sentry_public_key,
        sentry_principal=args.sentry_principal,
        executor_principal=args.executor_principal,
        supervisor_public_key_path=args.supervisor_public_key,
        supervisor_principal=args.supervisor_principal,
        auditor_public_key_path=args.auditor_public_key,
        auditor_principal=args.auditor_principal,
    )
    result = evaluate_stage(
        args.stage,
        contract_path=args.contract,
        hardware_path=args.hardware,
        budget_path=args.budget,
        preflight_decision_path=args.preflight_decision,
        screen_decision_path=args.screen_decision,
        promotion_decision_path=args.promotion_decision,
        confirmation_decision_path=args.confirmation_decision,
        grpo_decision_path=args.grpo_decision,
        control_paths=args.control,
        candidate_paths=args.candidate,
        grpo_path=args.grpo_artifact,
        audit_path=args.audit,
        termination_receipt_path=args.termination_receipt,
        request_path=args.request,
        gate0_permit_path=args.gate0_permit,
        gate0_public_key_path=args.gate0_public_key,
        launch_receipt_path=args.launch_receipt,
        booking_request_path=args.booking_request,
        provider_output_path=args.provider_output,
        security=security,
        command=command,
    )
    rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        destination = Path(args.output).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return int(result["exit_status"])


__all__ = [
    "AUDIT_DECISION_DOMAIN",
    "BOOKING_REQUEST_SCHEMA",
    "Decision",
    "DecisionReplayError",
    "DecisionSecurityError",
    "SentrySecurity",
    "SentryPolicy",
    "Stage",
    "T2_AUTHORIZATION_DOMAIN",
    "VerifiedDecision",
    "build_parser",
    "build_signing_parser",
    "consume_signed_decision_once",
    "evaluate_confirmation",
    "evaluate_final",
    "evaluate_grpo",
    "evaluate_preflight",
    "evaluate_promotion",
    "evaluate_screen",
    "evaluate_stage",
    "main",
    "sign_bounded_payload",
    "sign_gate0_permit_payload",
    "signature_domain_for_kind",
    "signing_main",
    "verify_consume_and_execute",
    "verify_signed_decision",
]
