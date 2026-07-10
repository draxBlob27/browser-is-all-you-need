#!/usr/bin/env python3
"""Produce staged raw evidence for the fixed 8x H100 dispatcher A-B-B-A protocol."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import secrets
import statistics
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from w8_biayn.integrations.miles_mfu import (  # noqa: E402
    H100_SXM_BF16_PEAK_TFLOPS,
    summarize_miles_mfu_trial,
    write_trial_summary,
)
from w8_biayn.integrations.h100_research_sentry import (  # noqa: E402
    Decision,
    DecisionReplayError,
    DecisionSecurityError,
    Stage,
    consume_signed_decision_once,
    verify_signed_decision,
)
from w8_biayn.integrations.h100_signed_approval import (  # noqa: E402
    PermitError,
    load_public_key_document,
)
from w8_biayn.integrations.wandb_posttraining import (  # noqa: E402
    parse_miles_metric_events,
    read_key_value,
)


RUNNER = REPO_ROOT / "examples/miles/glm47_cpp_perf_lora_r16_h100_sft.sh"
RUNTIME_CHECK = REPO_ROOT / "scripts/check_miles_h100_runtime.py"
ACCEPTANCE_CONTRACT = REPO_ROOT / "examples/miles/h100_fastest_acceptance.json"
DATA_DIR = Path("/data/glm47-pie-profile-long128-oracle-v2")
TASKS_DIR = Path("/data/pie-tasks-full-20260706")
HF_CHECKPOINT = Path("/root/models/GLM-4.7-Flash")
REF_LOAD_DIR = Path("/root/models/GLM-4.7-Flash_torch_dist_tp4_pp1_ep8")
CANONICAL_RUN_ROOT = Path("/tmp/w8-issue32-t1")
GATE1_CONSUMPTION_ROOT = Path("/data/w8-biayn/control-plane/gate1-consumption/v1")
SETUP_ATTESTATION_PATH = Path(
    "/data/w8-biayn/control-plane/setup/issue32-t1-setup-attestation.json"
)
SETUP_ATTESTATION_SCHEMA = "w8-h100-setup-attestation/v1"
HF_REVISION_MARKER_PATH = HF_CHECKPOINT / ".w8-hf-revision"

TRAINING_BASE_SHA = "cd83e3c8780f09e38e5b58558d84580e74afbcf6"
TRAIN_SHA256 = "f1f5f70b1e77dbb6da51d075a35b2e48f784f4080873f356c9c4bd3c83a3d783"
TRAIN_ROW_COUNT = 128
TOTAL_PERF_STEPS = 16
WARMUP_STEPS = 2
MEASURED_STEPS = 14
EXPECTED_RAW_TOKEN_SIGNATURE = (86256, 93021, 101665, 112769) * 4
EXPECTED_MEASURED_TOKEN_SIGNATURE = EXPECTED_RAW_TOKEN_SIGNATURE[2:]
HISTORICAL_MFU_HURDLE = 2.1311238122828066
HISTORICAL_ACTOR_TOK_S_HURDLE = 6937.602138721957
REQUEST_LIFETIME = timedelta(hours=2)
REQUEST_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{7,127}\Z")
HEX_256_RE = re.compile(r"[0-9a-f]{64}\Z")

FAILURE_RE = re.compile(
    r"(?:CUDA out of memory|OutOfMemoryError|RayTaskError|ChildFailedError|"
    r"Traceback \(most recent call last\)|NCCL[^\n]*(?:error|failure))",
    re.IGNORECASE,
)
RELEVANT_PROCESS_RE = re.compile(
    r"(?:raylet|gcs_server|ray::|sglang|torchrun|megatron|actor_train|"
    r"(?:^|[/\s])train(?:ing)?(?:[._/-]|\s|$))",
    re.IGNORECASE,
)
TELEMETRY_COLUMNS = (
    "timestamp",
    "index",
    "clocks.sm",
    "power.draw",
    "temperature.gpu",
    "clocks_throttle_reasons.active",
    "utilization.gpu",
    "utilization.memory",
    "memory.used",
    "memory.total",
)
PER_STEP_COLUMNS = (
    "leg_id",
    "profile",
    "raw_step",
    "measured",
    "measured_position",
    "token_count",
    "actor_train_time_s",
    "actor_train_tflops_per_gpu",
    "estimated_mfu_percent",
    "global_actor_tok_s",
    "step_time_s",
    "wait_ratio",
    "loss",
    "grad_norm",
)


@dataclass(frozen=True)
class LegSpec:
    order: int
    leg_id: str
    profile: str
    dispatcher: str
    deepep: str


LEG_SPECS = {
    "a1": LegSpec(1, "a1", "A", "flex", "1"),
    "b1": LegSpec(2, "b1", "B", "alltoall", "0"),
    "b2": LegSpec(3, "b2", "B", "alltoall", "0"),
    "a2": LegSpec(4, "a2", "A", "flex", "1"),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="phase", required=True)
    prepare = subparsers.add_parser("prepare", help="write immutable preflight evidence only")
    prepare.add_argument("--run-root", required=True)
    prepare.add_argument("--budget-receipt", required=True)
    prepare.add_argument("--gate0-permit", required=True)
    prepare.add_argument("--gate0-launch-receipt", required=True)
    prepare.add_argument("--gate0-booking-request", required=True)
    prepare.add_argument("--gate0-provider-output", required=True)
    for phase in ("first-pair", "second-pair"):
        command = subparsers.add_parser(phase)
        command.add_argument("--run-root", required=True)
        command.add_argument("--sentry-approval", required=True)
        command.add_argument("--sentry-public-key", required=True)
        command.add_argument("--sentry-principal", required=True)
        command.add_argument("--executor-principal", required=True)
    return parser.parse_args(argv)


def _require_canonical_run_root(run_root: Path) -> None:
    if run_root.expanduser().resolve() != CANONICAL_RUN_ROOT.expanduser().resolve():
        raise SystemExit(f"run root must be exactly {CANONICAL_RUN_ROOT}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], columns: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows({key: row.get(key) for key in columns} for row in rows)


def _run_capture(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "returncode": None, "stdout": "", "stderr": str(exc)}
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _git_output(args: list[str]) -> dict[str, Any]:
    return _run_capture(["git", *args], cwd=REPO_ROOT)


def load_acceptance_contract() -> dict[str, Any]:
    payload = json.loads(ACCEPTANCE_CONTRACT.read_text(encoding="utf-8"))
    if payload.get("source_pins", {}).get("training_base_sha") != TRAINING_BASE_SHA:
        raise RuntimeError("acceptance contract training_base_sha mismatch")
    return payload


def collect_source_provenance() -> dict[str, Any]:
    contract = load_acceptance_contract()
    status = _git_output(["status", "--porcelain"])
    head = _git_output(["rev-parse", "HEAD"])
    ancestor = _git_output(["merge-base", "--is-ancestor", TRAINING_BASE_SHA, "HEAD"])
    changed = _git_output(["diff", "--name-only", f"{TRAINING_BASE_SHA}..HEAD"])
    repo_sha = head["stdout"].strip() if head["returncode"] == 0 else ""
    changed_paths = sorted(line for line in changed["stdout"].splitlines() if line)
    allowed_paths = set(contract["source_pins"]["allowed_paths_since_training_base"])
    disallowed_paths = sorted(set(changed_paths) - allowed_paths)
    errors: list[str] = []
    if status["returncode"] != 0 or status["stdout"].strip():
        errors.append("measurement_worktree_not_clean")
    if not re.fullmatch(r"[0-9a-f]{40}", repo_sha):
        errors.append("current_repo_sha_invalid")
    if ancestor["returncode"] != 0:
        errors.append("training_base_not_ancestor")
    if changed["returncode"] != 0:
        errors.append("source_diff_unavailable")
    if disallowed_paths:
        errors.append("source_diff_contains_unapproved_paths")
    return {
        "schema_version": 1,
        "ok": not errors,
        "errors": errors,
        "repo_sha": repo_sha,
        "training_base_sha": TRAINING_BASE_SHA,
        "training_base_is_ancestor": ancestor["returncode"] == 0,
        "worktree_clean": status["returncode"] == 0 and not status["stdout"].strip(),
        "changed_paths_since_training_base": changed_paths,
        "allowed_paths_since_training_base": sorted(allowed_paths),
        "disallowed_paths": disallowed_paths,
    }


def _optional_git_sha(path: Path) -> str:
    if not (path / ".git").exists():
        return ""
    result = _run_capture(["git", "rev-parse", "HEAD"], cwd=path)
    return result["stdout"].strip() if result["returncode"] == 0 else ""


def collect_hardware_receipt(source: dict[str, Any]) -> dict[str, Any]:
    query = _run_capture(
        [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,driver_version,pci.bus_id",
            "--format=csv,noheader,nounits",
        ]
    )
    topology = _run_capture(["nvidia-smi", "topo", "-m"])
    rows = [line.strip() for line in query["stdout"].splitlines() if line.strip()]
    errors: list[str] = []
    if query["returncode"] != 0 or len(rows) != 8 or any("H100" not in row for row in rows):
        errors.append("expected_exactly_8_h100_gpus")
    if topology["returncode"] != 0:
        errors.append("gpu_topology_query_failed")
    return {
        "schema_version": 1,
        "ok": not errors,
        "errors": errors,
        "gpu_rows": rows,
        "topology": topology["stdout"],
        "repo_sha": source["repo_sha"],
        "training_base_sha": source["training_base_sha"],
        "miles_sha": _optional_git_sha(Path("/root/miles")),
        "megatron_sha": _optional_git_sha(Path("/root/Megatron-LM")),
    }


def load_setup_attestation(path: Path = SETUP_ATTESTATION_PATH) -> dict[str, Any]:
    attestation = _read_json_object(path, "setup attestation")
    required = {
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
    }
    if set(attestation) != required or attestation.get("schema") != SETUP_ATTESTATION_SCHEMA:
        raise RuntimeError("setup attestation schema mismatch")
    _parse_utc(attestation.get("created_at_utc"), "setup attestation created_at_utc")
    if attestation.get("hf_checkpoint_path") != str(HF_CHECKPOINT):
        raise RuntimeError("setup attestation HF checkpoint mismatch")
    if attestation.get("hf_revision_marker_path") != str(HF_REVISION_MARKER_PATH):
        raise RuntimeError("setup attestation HF revision marker path mismatch")
    if re.fullmatch(r"[0-9a-f]{40}", str(attestation.get("hf_revision") or "")) is None:
        raise RuntimeError("setup attestation HF revision is not pinned")
    container_digest = str(attestation.get("container_image_digest") or "")
    container_reference = str(attestation.get("container_image_reference") or "")
    if re.fullmatch(r"sha256:[0-9a-f]{64}", container_digest) is None:
        raise RuntimeError("setup attestation container digest is invalid")
    if not container_reference.endswith(f"@{container_digest}"):
        raise RuntimeError("setup attestation container reference does not bind its digest")
    runtime_pins = load_acceptance_contract().get("runtime_pins", {})
    expected = {
        "hf_model": runtime_pins.get("hf_model"),
        "hf_revision": runtime_pins.get("hf_revision"),
        "container_image_reference": runtime_pins.get("container_image"),
        "container_platform": runtime_pins.get("container_platform"),
    }
    if any(attestation.get(field) != value for field, value in expected.items()):
        raise RuntimeError("setup attestation does not match acceptance runtime pins")
    if not HF_REVISION_MARKER_PATH.is_file():
        raise RuntimeError("HF revision marker is missing")
    if _sha256(HF_REVISION_MARKER_PATH) != attestation["hf_revision_marker_sha256"]:
        raise RuntimeError("HF revision marker hash mismatch")
    if HF_REVISION_MARKER_PATH.read_text(encoding="utf-8").strip() != attestation["hf_revision"]:
        raise RuntimeError("HF revision marker content mismatch")
    return attestation


def checkpoint_receipt(
    setup: dict[str, Any] | None = None,
    *,
    setup_path: Path = SETUP_ATTESTATION_PATH,
) -> dict[str, Any]:
    setup = setup or load_setup_attestation(setup_path)
    marker = REF_LOAD_DIR / "latest_checkpointed_iteration.txt"
    if not marker.is_file():
        raise RuntimeError(f"missing checkpoint tracker: {marker}")
    tag = marker.read_text(encoding="utf-8").strip()
    try:
        directory = REF_LOAD_DIR / ("release" if tag == "release" else f"iter_{int(tag):07d}")
    except ValueError as exc:
        raise RuntimeError(f"invalid checkpoint tracker value: {tag!r}") from exc
    metadata = directory / ".metadata"
    if not metadata.is_file():
        raise RuntimeError(f"incomplete distributed checkpoint: {metadata}")
    return {
        "schema_version": 2,
        "root": str(REF_LOAD_DIR),
        "layout": "TP4/PP1/EP8/ETP1",
        "tag": tag,
        "marker_sha256": _sha256(marker),
        "metadata_path": str(metadata),
        "metadata_sha256": _sha256(metadata),
        "metadata_size": metadata.stat().st_size,
        "hf_checkpoint_path": setup["hf_checkpoint_path"],
        "hf_model": setup["hf_model"],
        "hf_revision": setup["hf_revision"],
        "hf_revision_marker_path": setup["hf_revision_marker_path"],
        "hf_revision_marker_sha256": setup["hf_revision_marker_sha256"],
        "container_image_reference": setup["container_image_reference"],
        "container_image_digest": setup["container_image_digest"],
        "container_platform": setup["container_platform"],
        "setup_attestation_path": str(setup_path),
        "setup_attestation_sha256": _sha256(setup_path),
    }


def runtime_receipt(
    setup: dict[str, Any],
    *,
    setup_path: Path,
) -> dict[str, Any]:
    check = _run_capture([sys.executable, str(RUNTIME_CHECK)], cwd=REPO_ROOT)
    return {
        "schema_version": 2,
        "ok": check["returncode"] == 0,
        "returncode": check["returncode"],
        "stdout": check["stdout"],
        "stderr": check["stderr"],
        "runtime_check": check,
        "hf_checkpoint_path": setup["hf_checkpoint_path"],
        "hf_model": setup["hf_model"],
        "container_image_reference": setup["container_image_reference"],
        "container_image_digest": setup["container_image_digest"],
        "container_platform": setup["container_platform"],
        "hf_revision": setup["hf_revision"],
        "hf_revision_marker_path": setup["hf_revision_marker_path"],
        "hf_revision_marker_sha256": setup["hf_revision_marker_sha256"],
        "setup_attestation_path": str(setup_path),
        "setup_attestation_sha256": _sha256(setup_path),
    }


def data_receipt() -> dict[str, Any]:
    train = DATA_DIR / "sft/train.jsonl"
    if not train.is_file():
        raise RuntimeError(f"fixed train data missing: {train}")
    with train.open("r", encoding="utf-8") as handle:
        rows = sum(1 for line in handle if line.strip())
    sha = _sha256(train)
    if sha != TRAIN_SHA256 or rows != TRAIN_ROW_COUNT:
        raise RuntimeError(f"fixed train data mismatch: sha={sha} rows={rows}")
    return {
        "schema_version": 1,
        "path": str(train),
        "sha256": sha,
        "row_count": rows,
    }


def check_wandb_authenticated_read() -> dict[str, Any]:
    code = (
        "import wandb\n"
        "viewer = wandb.Api(timeout=30).viewer\n"
        "assert viewer\n"
        "print('wandb_authenticated_read_ok')\n"
    )
    env = os.environ.copy()
    env["WANDB_MODE"] = "online"
    result = _run_capture([sys.executable, "-c", code], env=env, timeout=45)
    secret = os.environ.get("WANDB_API_KEY", "")
    stderr = result["stderr"].replace(secret, "<redacted>") if secret else result["stderr"]
    return {
        "schema_version": 1,
        "ok": result["returncode"] == 0 and "wandb_authenticated_read_ok" in result["stdout"],
        "authenticated_api_read": result["returncode"] == 0,
        "mode": "online",
        "stderr": stderr[-1000:],
    }


def collect_wandb_readback(
    stage: Path,
    controlled: dict[str, str],
    env: dict[str, str],
) -> dict[str, Any]:
    entity = env.get("WANDB_ENTITY", "").strip()
    project = controlled["MILES_WANDB_PROJECT"]
    run_id = controlled["MILES_WANDB_RUN_ID"]
    experiment_id = controlled["W8_EXPERIMENT_ID"]
    expected_stage = controlled["MILES_WANDB_JOB_TYPE"]
    download_root = stage / "wandb_remote_artifact"
    local_files = {
        "evidence_summary": stage / f"{run_id}.evidence_summary.json",
        "artifact_manifest": stage / f"{run_id}.artifact_manifest.json",
    }
    errors: list[str] = []
    if not entity:
        errors.append("wandb_entity_missing")
    if any(not path.is_file() for path in local_files.values()):
        errors.append("wandb_local_finalization_artifact_missing")
    if errors:
        return {
            "schema": "h100-wandb-readback/v1",
            "ok": False,
            "errors": errors,
            "authenticated_api_read": False,
            "entity": entity,
            "project": project,
            "run_id": run_id,
        }

    code = r"""
import hashlib
import json
import sys
import time
from pathlib import Path

import wandb

entity, project, run_id, experiment_id, stage, download_root = sys.argv[1:]
api = wandb.Api(timeout=45)
run = None
artifacts = []
last_error = None
for attempt in range(10):
    try:
        run = api.run(f"{entity}/{project}/{run_id}")
        artifacts = list(run.logged_artifacts())
        if artifacts:
            break
    except Exception as exc:
        last_error = f"{type(exc).__name__}:{exc}"
    time.sleep(3)
if run is None:
    raise RuntimeError(last_error or "wandb run unavailable")

matching = []
for artifact in artifacts:
    metadata = dict(getattr(artifact, "metadata", {}) or {})
    if (
        metadata.get("experiment_id") == experiment_id
        and metadata.get("stage") == stage
        and metadata.get("status") == "success"
        and metadata.get("timing_status") == "verified"
    ):
        root = Path(artifact.download(root=download_root))
        files = {}
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            files[str(path.relative_to(root))] = digest.hexdigest()
        matching.append(
            {
                "name": str(getattr(artifact, "name", "")),
                "digest": str(getattr(artifact, "digest", "")),
                "metadata": metadata,
                "downloaded_files": files,
            }
        )

payload = {
    "run_id": str(getattr(run, "id", "")),
    "state": str(getattr(run, "state", "")),
    "url": str(getattr(run, "url", "")),
    "summary": {
        "timing_status": run.summary.get("observability/timing_status"),
        "experiment_id": run.summary.get("observability/experiment_id"),
        "stage": run.summary.get("stage/job_type"),
        "status": run.summary.get("stage/status"),
        "metric_event_count": run.summary.get("evidence/metric_event_count"),
        "artifact_file_count": run.summary.get("stage/artifact_file_count"),
    },
    "config": {
        "timing_status": run.config.get("timing_status"),
        "experiment_id": run.config.get("experiment_id"),
    },
    "matching_artifacts": matching,
}
print("W8_WANDB_READBACK=" + json.dumps(payload, sort_keys=True, allow_nan=False))
"""
    result = _run_capture(
        [
            sys.executable,
            "-c",
            code,
            entity,
            project,
            run_id,
            experiment_id,
            expected_stage,
            str(download_root),
        ],
        env=env,
        timeout=120,
    )
    marker = "W8_WANDB_READBACK="
    payload: dict[str, Any] = {}
    for line in reversed(result["stdout"].splitlines()):
        if line.startswith(marker):
            try:
                payload = json.loads(line[len(marker) :])
            except json.JSONDecodeError:
                pass
            break
    if result["returncode"] != 0 or not payload:
        errors.append("wandb_authenticated_readback_failed")
    summary = payload.get("summary") or {}
    config = payload.get("config") or {}
    if payload.get("run_id") != run_id or payload.get("state") != "finished":
        errors.append("wandb_remote_run_identity_or_state_mismatch")
    if (
        summary.get("timing_status") != "verified"
        or config.get("timing_status") != "verified"
        or summary.get("experiment_id") != experiment_id
        or config.get("experiment_id") != experiment_id
        or summary.get("stage") != expected_stage
        or summary.get("status") != "success"
    ):
        errors.append("wandb_remote_summary_or_config_mismatch")
    artifacts = payload.get("matching_artifacts") or []
    if len(artifacts) != 1:
        errors.append("wandb_remote_stage_artifact_missing_or_ambiguous")
    local_hashes = {name: _sha256(path) for name, path in local_files.items()}
    remote_hashes = artifacts[0].get("downloaded_files", {}) if len(artifacts) == 1 else {}
    for name, path in local_files.items():
        if remote_hashes.get(path.name) != local_hashes[name]:
            errors.append(f"wandb_remote_{name}_hash_mismatch")
    secret = env.get("WANDB_API_KEY", "")
    stderr = result["stderr"].replace(secret, "<redacted>") if secret else result["stderr"]
    return {
        "schema": "h100-wandb-readback/v1",
        "ok": not errors,
        "errors": sorted(set(errors)),
        "authenticated_api_read": result["returncode"] == 0 and bool(payload),
        "entity": entity,
        "project": project,
        "run_id": run_id,
        "experiment_id": experiment_id,
        "stage": expected_stage,
        "local_artifact_sha256": local_hashes,
        "remote": payload,
        "stderr": stderr[-2000:],
    }


def build_protocol(run_root: Path) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "protocol": "miles_h100_dispatcher_abba_staged_raw_evidence",
        "authority": "executor_evidence_only",
        "phases": ["prepare", "first-pair", "second-pair"],
        "no_one_shot_paid_path": True,
        "schedule": ["a1", "b1", "b2", "a2"],
        "phase_legs": {"first-pair": ["a1", "b1"], "second-pair": ["b2", "a2"]},
        "external_approval_requirements": {
            "first-pair": {"stage": "preflight", "decision": "PROMOTABLE"},
            "second-pair": {"stage": "screen", "decision": "PROMOTABLE"},
        },
        "fixed_workload": {
            "epochs": 4,
            "total_perf_steps": TOTAL_PERF_STEPS,
            "discarded_warmup_steps": [0, 1],
            "measured_steps": MEASURED_STEPS,
            "measured_token_signature": list(EXPECTED_MEASURED_TOKEN_SIGNATURE),
            "data_sha256": TRAIN_SHA256,
        },
        "profiles": {
            "A": {"dispatcher": "flex", "deepep": True},
            "B": {"dispatcher": "alltoall", "deepep": False},
        },
        "descriptive_hurdles": {
            "mfu_percent": HISTORICAL_MFU_HURDLE,
            "actor_tok_s": HISTORICAL_ACTOR_TOK_S_HURDLE,
            "scientific_authority": False,
        },
        "run_root": str(run_root),
    }


def controlled_leg_config(spec: LegSpec, run_root: Path) -> dict[str, str]:
    leg_root = run_root / "legs" / f"{spec.order:02d}_{spec.leg_id}"
    experiment_id = run_root.name
    run_id = f"dispatcher-abba-{spec.leg_id}"
    return {
        "MILES_RUN_ID": run_id,
        "MILES_RUN_ROOT": str(leg_root),
        "MILES_MODEL_ARGS_FILE": "glm4.7-flash.sh",
        "MILES_HF_CHECKPOINT": str(HF_CHECKPOINT),
        "MILES_REF_LOAD_DIR": str(REF_LOAD_DIR),
        "MILES_CPP_DATA_DIR": str(DATA_DIR),
        "MILES_CPP_TASKS_DIR": str(TASKS_DIR),
        "MILES_CPP_AUTO_PREPARE_DATA": "0",
        "MILES_GPUS_PER_NODE": "8",
        "MILES_TENSOR_MODEL_PARALLEL_SIZE": "4",
        "MILES_PIPELINE_MODEL_PARALLEL_SIZE": "1",
        "MILES_CONTEXT_PARALLEL_SIZE": "1",
        "MILES_EXPERT_MODEL_PARALLEL_SIZE": "8",
        "MILES_EXPERT_TENSOR_PARALLEL_SIZE": "1",
        "MILES_SEQ_LENGTH": "4096",
        "MILES_MAX_TOKENS_PER_GPU": "16384",
        "MILES_MICRO_BATCH_SIZE": "1",
        "MILES_RECOMPUTE_GRANULARITY": "selective",
        "MILES_USE_DYNAMIC_BATCH_SIZE": "1",
        "MILES_BALANCE_DATA": "1",
        "MILES_MOE_TOKEN_DISPATCHER_TYPE": spec.dispatcher,
        "MILES_MOE_ENABLE_DEEPEP": spec.deepep,
        "NVSHMEM_DISABLE_NCCL": "1",
        "MILES_ATTENTION_BACKEND": "flash",
        "MILES_SFT_NUM_EPOCH": "4",
        "MILES_START_ROLLOUT_ID": "0",
        "MILES_ROLLOUT_BATCH_SIZE": "32",
        "MILES_GLOBAL_BATCH_SIZE": "32",
        "MILES_SFT_ROLLOUT_SHUFFLE": "0",
        "MILES_SAVE_INTERVAL": "1000",
        "MILES_NO_REF": "1",
        "MILES_CUDA_DEVICE_MAX_CONNECTIONS": "1",
        "MILES_LORA_RANK": "16",
        "MILES_LORA_ALPHA": "32",
        "MILES_NO_GRADIENT_ACCUMULATION_FUSION": "1",
        "MILES_LORA_BASE_CPU_BACKUP": "0",
        "MILES_EXTRA_ARGS": "",
        "W8_REGISTER_GLM47_BRIDGE": "1",
        "W8_TIMING_STATUS": "verified",
        "W8_EXPERIMENT_ID": experiment_id,
        "MILES_WANDB_PROJECT": "glm47-pie-cpp-posttraining",
        "MILES_WANDB_GROUP": experiment_id,
        "MILES_WANDB_RUN_ID": run_id,
        "MILES_WANDB_JOB_TYPE": "dispatcher-abba",
        "WANDB_MODE": "online",
        "WANDB_RUN_GROUP": experiment_id,
        "WANDB_JOB_TYPE": "dispatcher-abba",
        "WANDB_TAGS": f"canonical,pie-cpp,dispatcher-abba,{spec.leg_id}",
    }


def build_subprocess_env(controlled: dict[str, str]) -> dict[str, str]:
    preserved = {
        "MILES_ROOT",
        "MILES_PYTHON",
        "MILES_MASTER_ADDR",
        "MILES_RAY_NODE_IP_ADDRESS",
        "MILES_RAY_DASHBOARD_HOST",
        "MILES_RAY_DASHBOARD_PORT",
        "WANDB_API_KEY",
        "WANDB_ENTITY",
        "WANDB_BASE_URL",
    }
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("MILES_", "W8_", "WANDB_"))
    }
    env.update({key: os.environ[key] for key in preserved if key in os.environ})
    for key in ("NCCL_ALGO", "NCCL_PROTO", "PYTORCH_CUDA_ALLOC_CONF", "PYTHONPATH"):
        env.pop(key, None)
    env.update(controlled)
    return env


def query_gpu_telemetry() -> tuple[list[dict[str, str]], str | None]:
    base = [
        "timestamp",
        "index",
        "clocks.sm",
        "power.draw",
        "temperature.gpu",
    ]
    tail = ["utilization.gpu", "utilization.memory", "memory.used", "memory.total"]
    for throttle in ("clocks_event_reasons.active", "clocks_throttle_reasons.active"):
        fields = [*base, throttle, *tail]
        result = _run_capture(
            ["nvidia-smi", f"--query-gpu={','.join(fields)}", "--format=csv,noheader,nounits"],
            timeout=10,
        )
        if result["returncode"] != 0:
            continue
        parsed = list(csv.reader(result["stdout"].splitlines()))
        if len(parsed) != 8 or any(len(row) != len(TELEMETRY_COLUMNS) for row in parsed):
            return [], "telemetry_row_shape_mismatch"
        rows = [
            {column: value.strip() for column, value in zip(TELEMETRY_COLUMNS, row)}
            for row in parsed
        ]
        return rows, None
    return [], "nvidia_smi_telemetry_query_failed"


class TelemetryMonitor:
    def __init__(
        self,
        path: Path,
        *,
        query: Callable[[], tuple[list[dict[str, str]], str | None]] = query_gpu_telemetry,
        interval_s: float = 2.0,
    ) -> None:
        self.path = path
        self.query = query
        self.interval_s = interval_s
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.errors: list[str] = []
        self.sample_count = 0
        self.row_count = 0

    def _sample(self) -> None:
        rows, error = self.query()
        if error:
            self.errors.append(error)
            return
        indices = {int(row["index"]) for row in rows if row["index"].isdigit()}
        if indices != set(range(8)):
            self.errors.append("telemetry_gpu_coverage_mismatch")
            return
        with self.path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(TELEMETRY_COLUMNS))
            writer.writerows(rows)
        self.sample_count += 1
        self.row_count += len(rows)

    def _loop(self) -> None:
        while not self.stop_event.wait(self.interval_s):
            self._sample()

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8", newline="") as handle:
            csv.DictWriter(handle, fieldnames=list(TELEMETRY_COLUMNS)).writeheader()
        self._sample()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self) -> dict[str, Any]:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=max(5.0, self.interval_s * 2))
            if self.thread.is_alive():
                self.errors.append("telemetry_thread_did_not_stop")
        if not self.errors:
            self._sample()
        return {
            "ok": self.sample_count >= 2 and not self.errors,
            "sample_count": self.sample_count,
            "row_count": self.row_count,
            "errors": self.errors,
            "path": str(self.path),
        }


def nvlink_snapshot() -> dict[str, Any]:
    commands = (
        ["nvidia-smi", "nvlink", "--get-error-counters"],
        ["nvidia-smi", "nvlink", "-e"],
    )
    attempts = []
    for command in commands:
        result = _run_capture(command, timeout=10)
        attempts.append({"command": command, "returncode": result["returncode"]})
        if result["returncode"] == 0:
            return {"supported": True, "command": command, "output": result["stdout"]}
    return {"supported": False, "attempts": attempts}


def _ray_stop(env: dict[str, str]) -> dict[str, Any]:
    result = _run_capture(["ray", "stop", "--force"], env=env, timeout=30)
    return {
        "ok": result["returncode"] == 0,
        "returncode": result["returncode"],
        "stdout": result["stdout"][-2000:],
        "stderr": result["stderr"][-2000:],
    }


def collect_process_cleanliness() -> dict[str, Any]:
    gpu = _run_capture(
        [
            "nvidia-smi",
            "--query-compute-apps=pid,process_name,used_gpu_memory",
            "--format=csv,noheader,nounits",
        ],
        timeout=15,
    )
    processes = _run_capture(["ps", "-axo", "pid=,lstart=,args="], timeout=15)
    errors: list[str] = []
    gpu_inventory: list[dict[str, Any]] = []
    if gpu["returncode"] != 0:
        errors.append("gpu_process_inventory_failed")
    else:
        for row in csv.reader(gpu["stdout"].splitlines()):
            if not row or not row[0].strip() or row[0].startswith("No running"):
                continue
            if len(row) != 3 or not row[0].strip().isdigit():
                errors.append("gpu_process_inventory_malformed")
                continue
            gpu_inventory.append(
                {
                    "pid": int(row[0].strip()),
                    "process_name": row[1].strip(),
                    "used_gpu_memory_mib": row[2].strip(),
                }
            )
    process_rows: dict[int, dict[str, Any]] = {}
    if processes["returncode"] != 0:
        errors.append("process_inventory_failed")
    else:
        pattern = re.compile(
            r"^\s*(\d+)\s+([A-Z][a-z]{2}\s+[A-Z][a-z]{2}\s+\d{1,2}\s+"
            r"\d{2}:\d{2}:\d{2}\s+\d{4})\s+(.*)$"
        )
        for line in processes["stdout"].splitlines():
            match = pattern.match(line)
            if match is None:
                continue
            pid = int(match.group(1))
            process_rows[pid] = {
                "pid": pid,
                "start_time": match.group(2),
                "args": match.group(3),
            }
    relevant: dict[int, dict[str, Any]] = {}
    for pid, row in process_rows.items():
        if pid != os.getpid() and RELEVANT_PROCESS_RE.search(str(row["args"])):
            relevant[pid] = {**row, "sources": ["process_inventory"]}
    for gpu_row in gpu_inventory:
        pid = int(gpu_row["pid"])
        row = process_rows.get(
            pid,
            {"pid": pid, "start_time": None, "args": gpu_row["process_name"]},
        )
        sources = list(relevant.get(pid, {}).get("sources", []))
        if "gpu_process_inventory" not in sources:
            sources.append("gpu_process_inventory")
        relevant[pid] = {**row, "sources": sources}
    if relevant:
        errors.append("surviving_relevant_processes")
    return {
        "schema": "h100-process-cleanliness/v1",
        "checked_at_utc": _utc_now(),
        "ok": not errors,
        "errors": sorted(set(errors)),
        "gpu_process_inventory": gpu_inventory,
        "relevant_processes": [relevant[pid] for pid in sorted(relevant)],
        "commands": {
            "gpu_process_inventory_returncode": gpu["returncode"],
            "process_inventory_returncode": processes["returncode"],
        },
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _tranche_id(run_root: Path) -> str:
    budget_path = run_root / "budget.json"
    try:
        budget = json.loads(budget_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid budget receipt: {budget_path}") from exc
    tranche_id = budget.get("tranche_id")
    if not isinstance(tranche_id, str) or not tranche_id.strip():
        raise RuntimeError("budget receipt has no tranche_id")
    return tranche_id.strip()


def _append_receipt_evidence(
    path: Path,
    *,
    tranche_id: str,
    run_started_at_utc: str,
    run_finished_at_utc: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    additions = {
        "dataset_sha256": TRAIN_SHA256,
        "tranche_id": tranche_id,
        "run_started_at_utc": run_started_at_utc,
        "run_finished_at_utc": run_finished_at_utc,
    }
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    rendered: list[str] = []
    written: set[str] = set()
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line else ""
        if key in additions:
            if key not in written:
                rendered.append(f"{key}={additions[key]}")
                written.add(key)
            continue
        rendered.append(line)
    rendered.extend(f"{key}={value}" for key, value in additions.items() if key not in written)
    path.write_text("\n".join(rendered) + "\n", encoding="utf-8")


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def summarize_two_warmup(
    spec: LegSpec,
    log_path: Path,
    receipt_path: Path,
    *,
    launcher_exit_code: int,
    pre_cleanup: dict[str, Any],
    post_cleanup: dict[str, Any],
    pre_process_cleanliness: dict[str, Any],
    post_process_cleanliness: dict[str, Any],
    telemetry: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    receipt = read_key_value(receipt_path) if receipt_path.is_file() else {}
    events = parse_miles_metric_events(log_path)
    perf = sorted(
        (
            event
            for event in events
            if event["family"] == "perf" and "perf/actor_train_time" in event["metrics"]
        ),
        key=lambda event: event["step"],
    )
    train = {event["step"]: event["metrics"] for event in events if event["family"] == "step"}
    records = []
    for index, event in enumerate(perf):
        metrics = event["metrics"]
        actor_time = _number(metrics.get("perf/actor_train_time"))
        actor_tok_s = _number(metrics.get("perf/actor_train_tok_per_s"))
        actor_tflops = _number(metrics.get("perf/actor_train_tflops"))
        measured = index >= WARMUP_STEPS
        records.append(
            {
                "leg_id": spec.leg_id,
                "profile": spec.profile,
                "raw_step": event["step"],
                "measured": measured,
                "measured_position": index - WARMUP_STEPS if measured else None,
                "token_count": (
                    round(actor_time * actor_tok_s)
                    if actor_time is not None and actor_tok_s is not None
                    else None
                ),
                "actor_train_time_s": actor_time,
                "actor_train_tflops_per_gpu": actor_tflops,
                "estimated_mfu_percent": (
                    100.0 * actor_tflops / H100_SXM_BF16_PEAK_TFLOPS
                    if actor_tflops is not None
                    else None
                ),
                "global_actor_tok_s": actor_tok_s,
                "step_time_s": _number(metrics.get("perf/step_time")),
                "wait_ratio": _number(metrics.get("perf/wait_time_ratio")),
                "loss": _number(train.get(event["step"], {}).get("train/loss")),
                "grad_norm": _number(train.get(event["step"], {}).get("train/grad_norm")),
            }
        )
    measured_records = [row for row in records if row["measured"]]
    signature = [row["token_count"] for row in measured_records]
    required = (
        "actor_train_time_s",
        "actor_train_tflops_per_gpu",
        "global_actor_tok_s",
        "loss",
        "grad_norm",
    )
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
    reasons = []
    if (
        launcher_exit_code != 0
        or receipt.get("status") != "success"
        or receipt.get("ray_status") not in (0, 0.0)
    ):
        reasons.append("stage_failed")
    if not pre_cleanup.get("ok"):
        reasons.append("pre_leg_ray_cleanup_failed")
    if not post_cleanup.get("ok"):
        reasons.append("post_leg_ray_cleanup_failed")
    if not pre_process_cleanliness.get("ok"):
        reasons.append("pre_leg_process_cleanliness_failed")
    if not post_process_cleanliness.get("ok"):
        reasons.append("post_leg_process_cleanliness_failed")
    if not telemetry.get("ok"):
        reasons.append("telemetry_monitor_failed")
    if len(perf) != TOTAL_PERF_STEPS or [event["step"] for event in perf] != list(range(16)):
        reasons.append("unexpected_perf_steps")
    if len(measured_records) != MEASURED_STEPS:
        reasons.append("unexpected_measured_step_count")
    if signature != list(EXPECTED_MEASURED_TOKEN_SIGNATURE):
        reasons.append("fixed_token_signature_mismatch")
    if any(row.get(key) is None for row in records for key in required):
        reasons.append("missing_or_non_finite_metric")
    if FAILURE_RE.search(log_text):
        reasons.append("failure_trace_in_log")

    def median_value(key: str) -> float | None:
        values = [float(row[key]) for row in measured_records if row.get(key) is not None]
        return statistics.median(values) if values else None

    return (
        {
            "schema_version": 1,
            "authority": "executor_supplementary_evidence",
            "leg": asdict(spec),
            "valid": not reasons,
            "rejection_reasons": sorted(set(reasons)),
            "total_perf_steps": len(records),
            "discarded_warmup_steps": [0, 1],
            "measured_step_count": len(measured_records),
            "measured_token_signature": signature,
            "estimated_mfu_percent_median": median_value("estimated_mfu_percent"),
            "global_actor_tok_s_median": median_value("global_actor_tok_s"),
            "pre_ray_cleanup": pre_cleanup,
            "post_ray_cleanup": post_cleanup,
            "pre_process_cleanliness": pre_process_cleanliness,
            "post_process_cleanliness": post_process_cleanliness,
            "telemetry": telemetry,
        },
        records,
    )


def run_leg(spec: LegSpec, run_root: Path) -> dict[str, Any]:
    controlled = controlled_leg_config(spec, run_root)
    env = build_subprocess_env(controlled)
    tranche_id = _tranche_id(run_root)
    leg_root = Path(controlled["MILES_RUN_ROOT"])
    leg_root.mkdir(parents=True, exist_ok=True)
    stage = leg_root / "sft_lora_r16"
    write_json(leg_root / "leg_spec.json", {"leg": asdict(spec), "controlled_env": controlled})
    pre_cleanup = _ray_stop(env)
    write_json(leg_root / "ray_cleanup_before.json", pre_cleanup)
    pre_process_cleanliness = collect_process_cleanliness()
    write_json(leg_root / "process_cleanliness_before.json", pre_process_cleanliness)
    before_nvlink = nvlink_snapshot()
    write_json(leg_root / "nvlink_before.json", before_nvlink)
    monitor = TelemetryMonitor(stage / "gpu_telemetry.csv")
    monitor_started = False
    launcher_exit_code = 125
    receipt_path = stage / "run_receipt.txt"
    log_path = stage / "run.log"
    run_started_at_utc = _utc_now()
    try:
        monitor.start()
        monitor_started = True
        if pre_cleanup["ok"] and pre_process_cleanliness["ok"]:
            launcher_exit_code = subprocess.run(
                ["bash", str(RUNNER)], env=env, check=False
            ).returncode
    finally:
        try:
            if monitor_started:
                try:
                    telemetry = monitor.stop()
                except Exception as exc:  # pragma: no cover - defensive hardware cleanup
                    telemetry = {
                        "ok": False,
                        "sample_count": monitor.sample_count,
                        "row_count": monitor.row_count,
                        "errors": [f"telemetry_stop_failed:{type(exc).__name__}:{exc}"],
                        "path": str(monitor.path),
                    }
            else:
                telemetry = {
                    "ok": False,
                    "sample_count": 0,
                    "row_count": 0,
                    "errors": ["telemetry_start_failed"],
                    "path": str(monitor.path),
                }
        finally:
            post_cleanup = _ray_stop(env)
            post_process_cleanliness = collect_process_cleanliness()
        run_finished_at_utc = _utc_now()
        after_nvlink = nvlink_snapshot()
        write_json(leg_root / "nvlink_after.json", after_nvlink)
        write_json(leg_root / "ray_cleanup_after.json", post_cleanup)
        write_json(leg_root / "process_cleanliness_after.json", post_process_cleanliness)
        _append_receipt_evidence(
            receipt_path,
            tranche_id=tranche_id,
            run_started_at_utc=run_started_at_utc,
            run_finished_at_utc=run_finished_at_utc,
        )
    wandb_readback_path = leg_root / "wandb_readback.json"
    wandb_readback = collect_wandb_readback(stage, controlled, env)
    write_json(wandb_readback_path, wandb_readback)
    canonical = summarize_miles_mfu_trial(
        log_path=log_path,
        receipt_path=receipt_path,
        round_number=spec.order,
        name=f"dispatcher_abba_{spec.leg_id}",
        precision="bf16",
        peak_tflops_per_gpu=H100_SXM_BF16_PEAK_TFLOPS,
    )
    canonical["launcher_exit_code"] = launcher_exit_code
    trial_summary_path = write_trial_summary(leg_root / "trial_summary.json", canonical)
    supplementary, records = summarize_two_warmup(
        spec,
        log_path,
        receipt_path,
        launcher_exit_code=launcher_exit_code,
        pre_cleanup=pre_cleanup,
        post_cleanup=post_cleanup,
        pre_process_cleanliness=pre_process_cleanliness,
        post_process_cleanliness=post_process_cleanliness,
        telemetry=telemetry,
    )
    if not canonical.get("accepted"):
        supplementary["valid"] = False
        supplementary["rejection_reasons"] = sorted(
            {*supplementary["rejection_reasons"], "canonical_trial_rejected"}
        )
    if not wandb_readback["ok"]:
        supplementary["valid"] = False
        supplementary["rejection_reasons"] = sorted(
            {*supplementary["rejection_reasons"], "wandb_remote_readback_failed"}
        )
    write_json(leg_root / "leg_summary.json", supplementary)
    write_json(leg_root / "per_step_records.json", records)
    write_csv(leg_root / "per_step_records.csv", records, PER_STEP_COLUMNS)
    evidence_paths = {
        "trial_summary": trial_summary_path,
        "leg_summary": leg_root / "leg_summary.json",
        "run_log": log_path,
        "run_receipt": receipt_path,
        "gpu_telemetry": stage / "gpu_telemetry.csv",
        "nvlink_before": leg_root / "nvlink_before.json",
        "nvlink_after": leg_root / "nvlink_after.json",
        "process_cleanliness_before": leg_root / "process_cleanliness_before.json",
        "process_cleanliness_after": leg_root / "process_cleanliness_after.json",
        "wandb_readback": wandb_readback_path,
        "wandb_evidence_summary": stage
        / f"{controlled['MILES_WANDB_RUN_ID']}.evidence_summary.json",
        "wandb_artifact_manifest": stage
        / f"{controlled['MILES_WANDB_RUN_ID']}.artifact_manifest.json",
    }
    hashes = {name: _sha256(path) for name, path in evidence_paths.items() if path.is_file()}
    manifest = {
        "schema_version": 1,
        "authority": "executor_raw_evidence",
        "leg": spec.leg_id,
        "paths": {name: str(path) for name, path in evidence_paths.items()},
        "sha256": hashes,
        "valid": supplementary["valid"],
    }
    write_json(leg_root / "leg_evidence_manifest.json", manifest)
    return {
        "leg_id": spec.leg_id,
        "leg_root": str(leg_root),
        "trial_summary": str(trial_summary_path),
        "leg_summary": str(leg_root / "leg_summary.json"),
        "evidence_manifest": str(leg_root / "leg_evidence_manifest.json"),
        "evidence_manifest_sha256": _sha256(leg_root / "leg_evidence_manifest.json"),
        "valid": supplementary["valid"],
    }


def _artifact_hashes(paths: dict[str, Path]) -> dict[str, str]:
    return {name: _sha256(path) for name, path in paths.items()}


def _write_state(run_root: Path, phase: str, **details: Any) -> None:
    write_json(
        run_root / "executor_state.json",
        {
            "schema_version": 1,
            "authority": "executor_phase_state",
            "phase": phase,
            **details,
        },
    )


def _read_state(run_root: Path, expected: str) -> None:
    path = run_root / "executor_state.json"
    payload = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if payload.get("phase") != expected:
        raise SystemExit(f"expected executor phase {expected!r}, got {payload.get('phase')!r}")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise RuntimeError(f"{field} is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError(f"{field} is not an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise RuntimeError(f"{field} must include a UTC offset")
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _request_security(
    stage: Stage,
    *,
    sentry_principal: str,
    executor_principal: str,
) -> dict[str, str]:
    now = _utc_now()
    return {
        "request_id": f"executor-{stage.value}-{secrets.token_hex(12)}",
        "nonce": secrets.token_hex(32),
        "issued_at": _format_utc(now),
        "expires_at": _format_utc(now + REQUEST_LIFETIME),
        "sentry_principal": sentry_principal,
        "executor_principal": executor_principal,
    }


def _validate_request_security(
    payload: dict[str, Any],
    *,
    expected_stage: Stage,
    expected_sentry_principal: str,
    expected_executor_principal: str,
    require_current: bool,
) -> None:
    if payload.get("requested_stage") != expected_stage.value:
        raise SystemExit(f"{expected_stage.value} request stage mismatch")
    request_id = str(payload.get("request_id") or "")
    nonce = str(payload.get("nonce") or "")
    if REQUEST_ID_RE.fullmatch(request_id) is None:
        raise SystemExit(f"{expected_stage.value} request_id is invalid")
    if HEX_256_RE.fullmatch(nonce) is None or len(bytes.fromhex(nonce)) != 32:
        raise SystemExit(f"{expected_stage.value} request nonce is not 256-bit hex")
    if payload.get("sentry_principal") != expected_sentry_principal:
        raise SystemExit(f"{expected_stage.value} request sentry principal mismatch")
    if payload.get("executor_principal") != expected_executor_principal:
        raise SystemExit(f"{expected_stage.value} request executor principal mismatch")
    try:
        issued_at = _parse_utc(payload.get("issued_at"), "request issued_at")
        expires_at = _parse_utc(payload.get("expires_at"), "request expires_at")
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    if expires_at <= issued_at or expires_at - issued_at > REQUEST_LIFETIME:
        raise SystemExit(f"{expected_stage.value} request lifetime is invalid")
    if require_current:
        now = _utc_now()
        if now < issued_at or now >= expires_at:
            raise SystemExit(f"{expected_stage.value} request is outside its validity window")


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"{label} is missing or malformed: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} must contain a JSON object")
    return value


def _copy_exact(source: Path, destination: Path) -> str:
    source = source.expanduser().resolve()
    if not source.is_file():
        raise RuntimeError(f"required artifact is not a regular file: {source}")
    if destination.exists():
        raise RuntimeError(f"refusing to overwrite preserved artifact: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    before = _sha256(source)
    temporary = destination.with_name(f".{destination.name}.{secrets.token_hex(8)}.tmp")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with source.open("rb") as reader, os.fdopen(descriptor, "wb", closefd=True) as writer:
            while chunk := reader.read(1024 * 1024):
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
        os.replace(temporary, destination)
    except BaseException:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise
    after = _sha256(source)
    copied = _sha256(destination)
    if before != after or copied != before:
        raise RuntimeError(f"artifact changed while being preserved: {source}")
    return copied


def _gate0_paths(run_root: Path) -> dict[str, Path]:
    gate0 = run_root / "gate0"
    return {
        "permit": gate0 / "permit.json",
        "launch_receipt": gate0 / "launch_receipt.json",
        "booking_request": gate0 / "booking_request.json",
        "provider_output": gate0 / "provider_output.json",
    }


def _validate_gate0_chain(
    paths: dict[str, Path], *, require_current_permit: bool
) -> dict[str, Any]:
    permit = _read_json_object(paths["permit"], "Gate0 permit")
    receipt = _read_json_object(paths["launch_receipt"], "Gate0 launch receipt")
    booking_request = _read_json_object(paths["booking_request"], "Gate0 booking request")
    provider_output = _read_json_object(paths["provider_output"], "Gate0 provider output")
    payload = permit.get("payload")
    if permit.get("schema") != "h100-lium-signed-permit-envelope/v4" or not isinstance(
        payload, dict
    ):
        raise RuntimeError("Gate0 permit envelope schema is invalid")
    if (
        payload.get("schema") != "h100-lium-booking-permit/v4"
        or payload.get("stage") != "lium-booking"
        or payload.get("decision") != Decision.PROMOTABLE.value
    ):
        raise RuntimeError("Gate0 permit payload is not a promotable lium-booking permit")
    request_id = str(payload.get("request_id") or "")
    nonce = str(payload.get("nonce") or "")
    key_id = str(permit.get("key_id") or "")
    if REQUEST_ID_RE.fullmatch(request_id) is None:
        raise RuntimeError("Gate0 request_id is invalid")
    if HEX_256_RE.fullmatch(nonce) is None or len(bytes.fromhex(nonce)) != 32:
        raise RuntimeError("Gate0 nonce is not 256-bit hex")
    if not key_id:
        raise RuntimeError("Gate0 key_id is missing")
    issued_at = _parse_utc(payload.get("issued_at"), "Gate0 issued_at")
    expires_at = _parse_utc(payload.get("expires_at"), "Gate0 expires_at")
    if expires_at <= issued_at or expires_at - issued_at > timedelta(minutes=10):
        raise RuntimeError("Gate0 permit lifetime is invalid")
    if require_current_permit:
        now = _utc_now()
        if now < issued_at or now >= expires_at:
            raise RuntimeError("Gate0 permit is outside its validity window")
    sentry_principal = str(payload.get("sentry_principal") or "")
    executor_principal = str(payload.get("executor_principal") or "")
    if not sentry_principal or not executor_principal:
        raise RuntimeError("Gate0 principals are missing")
    gate1_trust = booking_request.get("gate1_trust")
    required_trust_fields = {
        "public_key_sha256",
        "key_id",
        "sentry_principal",
        "executor_principal",
    }
    if not isinstance(gate1_trust, dict) or set(gate1_trust) != required_trust_fields:
        raise RuntimeError("Gate0 booking request Gate1 trust shape is invalid")
    if (
        HEX_256_RE.fullmatch(str(gate1_trust.get("public_key_sha256") or "")) is None
        or re.fullmatch(r"ed25519-sha256:[0-9a-f]{64}", str(gate1_trust.get("key_id") or ""))
        is None
        or gate1_trust.get("sentry_principal") != sentry_principal
        or gate1_trust.get("executor_principal") != executor_principal
    ):
        raise RuntimeError("Gate0 booking request Gate1 trust binding is invalid")
    if (
        payload.get("provider") != "lium"
        or payload.get("gpu_type") != "H100"
        or payload.get("gpu_count") != 8
        or payload.get("credential_transport") != "stdin-line/v1"
    ):
        raise RuntimeError("Gate0 provider or 8x H100 binding is invalid")
    ssh_public_key_path = payload.get("ssh_public_key_path")
    if (
        not isinstance(ssh_public_key_path, str)
        or not Path(ssh_public_key_path).is_absolute()
        or HEX_256_RE.fullmatch(str(payload.get("ssh_public_key_sha256") or "")) is None
    ):
        raise RuntimeError("Gate0 SSH public-key permit binding is invalid")

    hashes = _artifact_hashes(paths)
    if payload.get("parent_request_sha256") != hashes["booking_request"]:
        raise RuntimeError("Gate0 permit booking-request hash mismatch")
    execution = receipt.get("execution") if isinstance(receipt.get("execution"), dict) else {}
    if (
        receipt.get("schema") != "h100-lium-launch-receipt/v2"
        or receipt.get("status") != "COMPLETED"
        or execution.get("exit_code") != 0
        or execution.get("wrapper_exit_code") != 0
        or execution.get("timed_out") is not False
    ):
        raise RuntimeError("Gate0 launch receipt does not prove a successful launch")
    receipt_permit = receipt.get("permit") if isinstance(receipt.get("permit"), dict) else {}
    if (
        receipt_permit.get("sha256") != hashes["permit"]
        or receipt_permit.get("key_id") != key_id
        or receipt_permit.get("request_id") != request_id
        or receipt_permit.get("nonce") != nonce
    ):
        raise RuntimeError("Gate0 launch receipt permit binding mismatch")
    receipt_parent = (
        receipt.get("parent_request") if isinstance(receipt.get("parent_request"), dict) else {}
    )
    if receipt_parent.get("sha256") != hashes["booking_request"]:
        raise RuntimeError("Gate0 launch receipt booking-request hash mismatch")
    receipt_output = (
        receipt.get("provider_output") if isinstance(receipt.get("provider_output"), dict) else {}
    )
    if (
        receipt_output.get("sha256") != hashes["provider_output"]
        or receipt_output.get("size_bytes") != paths["provider_output"].stat().st_size
    ):
        raise RuntimeError("Gate0 launch receipt provider-output binding mismatch")

    pod = provider_output.get("pod") if isinstance(provider_output.get("pod"), dict) else {}
    executor = (
        provider_output.get("executor") if isinstance(provider_output.get("executor"), dict) else {}
    )
    schedule = (
        provider_output.get("schedule") if isinstance(provider_output.get("schedule"), dict) else {}
    )
    allocation_id = str(pod.get("id") or "")
    allocation_name = str(pod.get("name") or "")
    gpu_label = f"{executor.get('gpu_type', '')} {executor.get('gpu_model', '')}".upper()
    if (
        provider_output.get("schema") != "lium-h100-pod-create/v2"
        or provider_output.get("status") != "RUNNING"
        or not allocation_id
        or not allocation_name
        or executor.get("gpu_count") != 8
        or "H100" not in gpu_label
        or executor.get("observed_rate_status") != payload.get("observed_node_hourly_rate_status")
        or schedule.get("confirmed") is not True
    ):
        raise RuntimeError("Gate0 provider output does not prove a running 8x H100 allocation")
    try:
        requested_termination = _parse_utc(
            schedule.get("termination_time"), "provider termination_time"
        )
        server_termination = _parse_utc(
            schedule.get("server_removal_scheduled_at"),
            "provider server_removal_scheduled_at",
        )
    except RuntimeError as exc:
        raise RuntimeError(f"Gate0 provider schedule is invalid: {exc}") from exc
    ttl_seconds = schedule.get("ttl_seconds")
    if (
        requested_termination != server_termination
        or type(ttl_seconds) is not int
        or ttl_seconds != payload.get("ttl_seconds")
        or not 0 < ttl_seconds <= 7200
    ):
        raise RuntimeError("Gate0 provider schedule or TTL binding mismatch")
    selector = str(payload.get("executor_id") or "")
    if selector not in {str(executor.get("id") or ""), str(executor.get("huid") or "")}:
        raise RuntimeError("Gate0 provider output executor mismatch")
    receipt_provider = receipt.get("provider") if isinstance(receipt.get("provider"), dict) else {}
    if (
        receipt_provider.get("name") != payload.get("provider")
        or receipt_provider.get("profile") != payload.get("profile")
        or receipt_provider.get("executor_id") != selector
    ):
        raise RuntimeError("Gate0 launch receipt provider binding mismatch")
    receipt_execution = (
        receipt.get("execution") if isinstance(receipt.get("execution"), dict) else {}
    )
    if receipt_execution.get("credential_transport") != payload.get("credential_transport"):
        raise RuntimeError("Gate0 credential transport binding mismatch")
    expected_access = {
        "ssh_public_key_path": payload.get("ssh_public_key_path"),
        "ssh_public_key_sha256": payload.get("ssh_public_key_sha256"),
    }
    output_access = (
        provider_output.get("access") if isinstance(provider_output.get("access"), dict) else {}
    )
    receipt_access = receipt.get("access") if isinstance(receipt.get("access"), dict) else {}
    if output_access != expected_access or receipt_access != expected_access:
        raise RuntimeError("Gate0 SSH public-key binding mismatch")
    output_template = (
        provider_output.get("template") if isinstance(provider_output.get("template"), dict) else {}
    )
    expected_template = {
        "id": payload.get("template_id"),
        "docker_image": payload.get("template_image"),
        "docker_image_tag": payload.get("template_tag"),
        "status": payload.get("template_status"),
    }
    if any(output_template.get(field) != value for field, value in expected_template.items()):
        raise RuntimeError("Gate0 provider template binding mismatch")
    output_runtime = (
        provider_output.get("runtime_evidence")
        if isinstance(provider_output.get("runtime_evidence"), dict)
        else {}
    )
    interpreter = (
        output_runtime.get("interpreter")
        if isinstance(output_runtime.get("interpreter"), dict)
        else {}
    )
    sdk = output_runtime.get("lium_sdk") if isinstance(output_runtime.get("lium_sdk"), dict) else {}
    cli = output_runtime.get("lium_cli") if isinstance(output_runtime.get("lium_cli"), dict) else {}
    if (
        output_runtime.get("provider_version") != payload.get("provider_version")
        or interpreter.get("path") != payload.get("provider_interpreter")
        or interpreter.get("sha256") != payload.get("provider_interpreter_sha256")
        or interpreter.get("version") != payload.get("provider_interpreter_version")
        or sdk.get("distribution") != payload.get("lium_sdk_distribution")
        or sdk.get("version") != payload.get("lium_sdk_version")
        or cli.get("path") != payload.get("lium_cli_path")
        or cli.get("sha256") != payload.get("lium_cli_sha256")
        or cli.get("version") != payload.get("lium_cli_version")
    ):
        raise RuntimeError("Gate0 provider runtime evidence mismatch")
    receipt_allocation = (
        receipt.get("allocation") if isinstance(receipt.get("allocation"), dict) else {}
    )
    if (
        allocation_name != payload.get("allocation_name")
        or receipt_allocation.get("name") != allocation_name
        or receipt_allocation.get("issue_number") != payload.get("issue_number")
    ):
        raise RuntimeError("Gate0 allocation identity mismatch")
    receipt_budget = receipt.get("budget") if isinstance(receipt.get("budget"), dict) else {}
    for field in (
        "ttl_seconds",
        "max_cost_usd",
        "max_node_hourly_rate_usd",
        "observed_node_hourly_rate_usd",
        "observed_node_hourly_rate_status",
        "max_node_hours",
    ):
        if receipt_budget.get(field) != payload.get(field):
            raise RuntimeError(f"Gate0 launch receipt budget binding mismatch: {field}")
    return {
        "permit_sha256": hashes["permit"],
        "launch_receipt_sha256": hashes["launch_receipt"],
        "booking_request_sha256": hashes["booking_request"],
        "provider_output_sha256": hashes["provider_output"],
        "provider_output_size_bytes": paths["provider_output"].stat().st_size,
        "allocation_id": allocation_id,
        "allocation_name": allocation_name,
        "request_id": request_id,
        "nonce": nonce,
        "key_id": key_id,
        "sentry_principal": sentry_principal,
        "executor_principal": executor_principal,
        "provider": payload["provider"],
        "profile": payload.get("profile"),
        "executor_id": selector,
        "gate1_trust": dict(gate1_trust),
    }


def prepare_phase(
    run_root: Path,
    budget_receipt: Path,
    *,
    gate0_permit: Path,
    gate0_launch_receipt: Path,
    gate0_booking_request: Path,
    gate0_provider_output: Path,
) -> int:
    _require_canonical_run_root(run_root)
    if run_root.exists() and any(run_root.iterdir()):
        raise SystemExit(f"prepare requires a new or empty run root: {run_root}")
    run_root.mkdir(parents=True, exist_ok=True)
    receipts = run_root / "receipts"
    receipts.mkdir()
    budget_copy = run_root / "budget.json"
    setup_copy = receipts / "setup_attestation.json"
    try:
        _copy_exact(budget_receipt, budget_copy)
        _copy_exact(SETUP_ATTESTATION_PATH, setup_copy)
        setup = load_setup_attestation(setup_copy)
        source_gate0 = {
            "permit": gate0_permit,
            "launch_receipt": gate0_launch_receipt,
            "booking_request": gate0_booking_request,
            "provider_output": gate0_provider_output,
        }
        copied_gate0 = _gate0_paths(run_root)
        for name, destination in copied_gate0.items():
            _copy_exact(source_gate0[name], destination)
        gate0 = _validate_gate0_chain(copied_gate0, require_current_permit=True)
    except (OSError, RuntimeError) as exc:
        write_json(run_root / "prepare_result.json", {"status": "failed", "error": str(exc)})
        return 2
    protocol_path = run_root / "protocol.json"
    source_path = receipts / "source.json"
    hardware_path = run_root / "hardware.json"
    checkpoint_path = receipts / "checkpoint.json"
    data_path = receipts / "data.json"
    wandb_path = receipts / "wandb_auth.json"
    runtime_path = receipts / "runtime.json"
    write_json(protocol_path, build_protocol(run_root))
    source = collect_source_provenance()
    write_json(source_path, source)
    hardware = collect_hardware_receipt(source)
    write_json(hardware_path, hardware)
    try:
        checkpoint = checkpoint_receipt(setup, setup_path=setup_copy)
        data = data_receipt()
        write_json(checkpoint_path, checkpoint)
        write_json(data_path, data)
    except RuntimeError as exc:
        write_json(run_root / "prepare_result.json", {"status": "failed", "error": str(exc)})
        return 2
    wandb = check_wandb_authenticated_read()
    write_json(wandb_path, wandb)
    runtime = runtime_receipt(setup, setup_path=setup_copy)
    write_json(runtime_path, runtime)
    immutable = {
        "protocol": protocol_path,
        "source": source_path,
        "hardware": hardware_path,
        "checkpoint": checkpoint_path,
        "data": data_path,
        "wandb_auth": wandb_path,
        "runtime": runtime_path,
        "budget": budget_copy,
    }
    hashes = _artifact_hashes(immutable)
    gate0_hashes = _artifact_hashes(copied_gate0)
    prepare_ok = source["ok"] and hardware["ok"] and wandb["ok"] and runtime["ok"]
    manifest_path = run_root / "prepare_manifest.json"
    write_json(
        manifest_path,
        {
            "schema_version": 1,
            "authority": "executor_prepare_evidence",
            "ok": prepare_ok,
            "artifacts": {name: str(path) for name, path in immutable.items()},
            "sha256": hashes,
            "gate0_artifacts": {name: str(path) for name, path in copied_gate0.items()},
            "gate0_sha256": gate0_hashes,
            "supporting_artifacts": {"setup_attestation": str(setup_copy)},
            "supporting_sha256": {"setup_attestation": _sha256(setup_copy)},
        },
    )
    if not prepare_ok:
        write_json(
            run_root / "prepare_result.json",
            {"status": "failed", "scientific_decision": None},
        )
        return 2
    request = {
        "schema_version": 1,
        "requested_stage": "preflight",
        **_request_security(
            Stage.PREFLIGHT,
            sentry_principal=gate0["sentry_principal"],
            executor_principal=gate0["executor_principal"],
        ),
        "input_hashes": hashes,
        "prepare_manifest_sha256": _sha256(manifest_path),
        "source_identity": {
            "repo_sha": source["repo_sha"],
            "training_base_sha": source["training_base_sha"],
        },
        "parent_decision_sha256": gate0["permit_sha256"],
        "parent_request_sha256": gate0["booking_request_sha256"],
        "gate0": gate0,
        "gate1_trust": gate0["gate1_trust"],
        "prepared_evidence": {
            "source": source,
            "runtime": runtime,
            "data": data,
            "checkpoint": checkpoint,
        },
    }
    request_path = run_root / "preflight_request.json"
    write_json(request_path, request)
    write_json(
        run_root / "prepare_result.json",
        {
            "status": "prepared",
            "scientific_decision": None,
            "preflight_request_sha256": _sha256(request_path),
        },
    )
    _write_state(run_root, "prepared")
    return 0


def _verify_prepare_immutability(run_root: Path) -> dict[str, Any]:
    manifest = _read_json_object(run_root / "prepare_manifest.json", "prepare manifest")
    if manifest.get("ok") is not True:
        raise SystemExit("prepare manifest is not valid")
    for paths_key, hashes_key in (
        ("artifacts", "sha256"),
        ("gate0_artifacts", "gate0_sha256"),
        ("supporting_artifacts", "supporting_sha256"),
    ):
        paths = manifest.get(paths_key)
        hashes = manifest.get(hashes_key)
        if not isinstance(paths, dict) or not isinstance(hashes, dict) or set(paths) != set(hashes):
            raise SystemExit(f"prepare manifest {paths_key} map is invalid")
        for name, recorded in hashes.items():
            path = Path(str(paths[name])).expanduser().resolve()
            if not path.is_file() or _sha256(path) != recorded:
                raise SystemExit(f"immutable prepare artifact changed: {name}")
    return manifest


def _verify_preflight_request(
    run_root: Path,
    *,
    expected_sentry_principal: str,
    expected_executor_principal: str,
    require_current: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = _verify_prepare_immutability(run_root)
    request_path = run_root / "preflight_request.json"
    request = _read_json_object(request_path, "preflight request")
    if request.get("schema_version") != 1:
        raise SystemExit("preflight request schema mismatch")
    _validate_request_security(
        request,
        expected_stage=Stage.PREFLIGHT,
        expected_sentry_principal=expected_sentry_principal,
        expected_executor_principal=expected_executor_principal,
        require_current=require_current,
    )
    if request.get("prepare_manifest_sha256") != _sha256(run_root / "prepare_manifest.json"):
        raise SystemExit("preflight request prepare-manifest hash mismatch")
    if request.get("input_hashes") != manifest.get("sha256"):
        raise SystemExit("preflight request input hashes mismatch")
    source = _read_json_object(run_root / "receipts/source.json", "source receipt")
    expected_source = {
        "repo_sha": source.get("repo_sha"),
        "training_base_sha": source.get("training_base_sha"),
    }
    if request.get("source_identity") != expected_source:
        raise SystemExit("preflight request source identity mismatch")
    prepared_evidence = {
        "source": source,
        "runtime": _read_json_object(run_root / "receipts/runtime.json", "runtime receipt"),
        "data": _read_json_object(run_root / "receipts/data.json", "data receipt"),
        "checkpoint": _read_json_object(
            run_root / "receipts/checkpoint.json", "checkpoint receipt"
        ),
    }
    if request.get("prepared_evidence") != prepared_evidence:
        raise SystemExit("preflight request prepared evidence mismatch")
    gate0 = _validate_gate0_chain(_gate0_paths(run_root), require_current_permit=False)
    if request.get("gate0") != gate0:
        raise SystemExit("preflight request Gate0 chain mismatch")
    if request.get("parent_decision_sha256") != gate0["permit_sha256"]:
        raise SystemExit("preflight request Gate0 permit parent mismatch")
    if request.get("parent_request_sha256") != gate0["booking_request_sha256"]:
        raise SystemExit("preflight request Gate0 booking parent mismatch")
    if request.get("gate1_trust") != gate0["gate1_trust"]:
        raise SystemExit("preflight request Gate1 trust mismatch")
    return request, gate0


def _verify_gate1_trust_anchor(
    public_key_path: Path,
    *,
    trust: dict[str, Any],
    expected_sentry_principal: str,
    expected_executor_principal: str,
) -> None:
    if (
        trust.get("sentry_principal") != expected_sentry_principal
        or trust.get("executor_principal") != expected_executor_principal
    ):
        raise SystemExit("Gate1 trust principals do not match the execution principals")
    expected_hash = str(trust.get("public_key_sha256") or "")
    expected_key_id = str(trust.get("key_id") or "")
    if _sha256(public_key_path) != expected_hash:
        raise SystemExit("supplied Gate1 public key hash does not match Gate0 trust")
    try:
        loaded = load_public_key_document(
            public_key_path,
            expected_key_id=expected_key_id,
        )
    except (OSError, PermitError) as exc:
        raise SystemExit(f"supplied Gate1 public key is invalid: {exc}") from exc
    if loaded.key_id != expected_key_id:
        raise SystemExit("supplied Gate1 public key ID does not match Gate0 trust")


def _verify_consume_and_preserve_approval(
    *,
    approval_path: Path,
    public_key_path: Path,
    destination: Path,
    expected_stage: Stage,
    expected_sentry_principal: str,
    expected_executor_principal: str,
    expected_request_sha256: str,
    expected_parent_decision_sha256: str,
    expected_parent_request_sha256: str,
    expected_public_key_sha256: str,
    request_path: Path,
    run_root: Path,
    consumed_phase: str,
) -> str:
    request_hash_before = _sha256(request_path)
    if request_hash_before != expected_request_sha256:
        raise SystemExit("stage request changed before approval verification")
    approval_hash_before = _sha256(approval_path)
    public_key_hash_before = _sha256(public_key_path)
    if public_key_hash_before != expected_public_key_sha256:
        raise SystemExit("supplied Gate1 public key changed after trust-anchor validation")
    try:
        verified = verify_signed_decision(
            approval_path,
            public_key_path,
            expected_stage=expected_stage,
            expected_signer_principal=expected_sentry_principal,
            expected_verifier_principal=expected_executor_principal,
            expected_request_sha256=expected_request_sha256,
            expected_parent_decision_sha256=expected_parent_decision_sha256,
            expected_parent_request_sha256=expected_parent_request_sha256,
        )
        if verified.payload.get("decision") != Decision.PROMOTABLE.value:
            raise DecisionSecurityError("signed sentry decision is not PROMOTABLE")
        if (
            _sha256(approval_path) != approval_hash_before
            or verified.artifact_sha256 != approval_hash_before
        ):
            raise DecisionSecurityError("signed approval changed during verification")
        if (
            _sha256(public_key_path) != public_key_hash_before
            or public_key_hash_before != expected_public_key_sha256
        ):
            raise DecisionSecurityError("trusted sentry public key changed during verification")
        if _sha256(request_path) != request_hash_before:
            raise DecisionSecurityError("stage request changed during verification")
        consume_signed_decision_once(verified, GATE1_CONSUMPTION_ROOT)
        _write_state(run_root, consumed_phase, approval_consumed=True)
    except DecisionReplayError as exc:
        raise SystemExit(f"signed sentry approval rejected: {exc}") from exc
    except DecisionSecurityError as exc:
        raise SystemExit(f"signed sentry approval rejected: {exc}") from exc
    copied_hash = _copy_exact(approval_path, destination)
    if copied_hash != approval_hash_before or _sha256(request_path) != request_hash_before:
        raise SystemExit("signed approval or stage request changed after consumption")
    return copied_hash


def _run_pair_sequential(
    run_root: Path,
    *,
    leg_ids: tuple[str, str],
    result_name: str,
    complete_status: str,
    repair_state: str,
    approval_sha256: str,
    request_sha256: str,
) -> tuple[list[dict[str, Any]], bool]:
    result_path = run_root / result_name
    legs: list[dict[str, Any]] = []
    for position, leg_id in enumerate(leg_ids):
        try:
            leg = run_leg(LEG_SPECS[leg_id], run_root)
        except (Exception, SystemExit) as exc:
            payload = {
                "status": repair_state,
                "authority": "executor_evidence",
                "terminal": True,
                "repair_required": True,
                "legs": legs,
                "failed_leg": leg_id,
                "not_run": list(leg_ids[position + 1 :]),
                "execution_error": f"{type(exc).__name__}: {exc}",
                "signed_approval_sha256": approval_sha256,
                "request_sha256": request_sha256,
            }
            write_json(result_path, payload)
            _write_state(run_root, repair_state, failed_leg=leg_id, approval_consumed=True)
            return legs, False
        legs.append(leg)
        if not leg.get("valid"):
            payload = {
                "status": repair_state,
                "authority": "executor_evidence",
                "terminal": True,
                "repair_required": True,
                "legs": legs,
                "failed_leg": leg_id,
                "not_run": list(leg_ids[position + 1 :]),
                "signed_approval_sha256": approval_sha256,
                "request_sha256": request_sha256,
            }
            write_json(result_path, payload)
            _write_state(run_root, repair_state, failed_leg=leg_id, approval_consumed=True)
            return legs, False
        write_json(
            result_path,
            {
                "status": (
                    complete_status
                    if position == len(leg_ids) - 1
                    else f"{complete_status.removesuffix('_complete')}_in_progress"
                ),
                "authority": "executor_evidence",
                "terminal": False,
                "repair_required": False,
                "legs": legs,
                "signed_approval_sha256": approval_sha256,
                "request_sha256": request_sha256,
            },
        )
    return legs, True


def first_pair_phase(
    run_root: Path,
    approval_path: Path,
    *,
    sentry_public_key: Path,
    sentry_principal: str,
    executor_principal: str,
) -> int:
    _require_canonical_run_root(run_root)
    _read_state(run_root, "prepared")
    request_path = run_root / "preflight_request.json"
    _, gate0 = _verify_preflight_request(
        run_root,
        expected_sentry_principal=sentry_principal,
        expected_executor_principal=executor_principal,
        require_current=True,
    )
    request_sha256 = _sha256(request_path)
    _verify_gate1_trust_anchor(
        sentry_public_key,
        trust=gate0["gate1_trust"],
        expected_sentry_principal=sentry_principal,
        expected_executor_principal=executor_principal,
    )
    approval_copy = run_root / "approvals/preflight.json"
    approval_sha256 = _verify_consume_and_preserve_approval(
        approval_path=approval_path,
        public_key_path=sentry_public_key,
        destination=approval_copy,
        expected_stage=Stage.PREFLIGHT,
        expected_sentry_principal=sentry_principal,
        expected_executor_principal=executor_principal,
        expected_request_sha256=request_sha256,
        expected_parent_decision_sha256=gate0["permit_sha256"],
        expected_parent_request_sha256=gate0["booking_request_sha256"],
        expected_public_key_sha256=gate0["gate1_trust"]["public_key_sha256"],
        request_path=request_path,
        run_root=run_root,
        consumed_phase="first_pair_authorized",
    )
    _write_state(run_root, "first_pair_running", approval_consumed=True)
    _verify_preflight_request(
        run_root,
        expected_sentry_principal=sentry_principal,
        expected_executor_principal=executor_principal,
        require_current=True,
    )
    if _sha256(request_path) != request_sha256 or _sha256(approval_copy) != approval_sha256:
        raise SystemExit("preflight request or approval changed before first-pair execution")
    legs, complete = _run_pair_sequential(
        run_root,
        leg_ids=("a1", "b1"),
        result_name="first_pair_result.json",
        complete_status="first_pair_complete",
        repair_state="first_pair_repair_needed",
        approval_sha256=approval_sha256,
        request_sha256=request_sha256,
    )
    if not complete:
        return 1
    source = _read_json_object(run_root / "receipts/source.json", "source receipt")
    request = {
        "schema_version": 1,
        "requested_stage": "screen",
        **_request_security(
            Stage.SCREEN,
            sentry_principal=sentry_principal,
            executor_principal=executor_principal,
        ),
        "evidence_hashes": {leg["leg_id"]: leg["evidence_manifest_sha256"] for leg in legs},
        "trial_summary_hashes": {
            leg["leg_id"]: _sha256(Path(leg["trial_summary"])) for leg in legs
        },
        "source_identity": {
            "repo_sha": source["repo_sha"],
            "training_base_sha": source["training_base_sha"],
        },
        "preflight_request_sha256": request_sha256,
        "signed_preflight_decision_sha256": approval_sha256,
        "parent_decision_sha256": approval_sha256,
        "parent_request_sha256": request_sha256,
        "gate0": gate0,
        "gate1_trust": gate0["gate1_trust"],
    }
    screen_request_path = run_root / "screen_request.json"
    write_json(screen_request_path, request)
    result = _read_json_object(run_root / "first_pair_result.json", "first-pair result")
    result["screen_request_sha256"] = _sha256(screen_request_path)
    write_json(run_root / "first_pair_result.json", result)
    _write_state(run_root, "first_pair_complete", approval_consumed=True)
    return 0


def _verify_first_pair_immutability(run_root: Path) -> dict[str, Any]:
    result = _read_json_object(run_root / "first_pair_result.json", "first-pair result")
    if (
        result.get("status") != "first_pair_complete"
        or result.get("authority") != "executor_evidence"
    ):
        raise SystemExit("first-pair result is not complete executor evidence")
    if [leg.get("leg_id") for leg in result.get("legs", [])] != ["a1", "b1"]:
        raise SystemExit("first-pair result leg order mismatch")
    for leg in result["legs"]:
        if leg.get("valid") is not True:
            raise SystemExit(f"first-pair leg is invalid: {leg.get('leg_id')}")
        path = Path(leg["evidence_manifest"])
        if not path.is_file() or _sha256(path) != leg["evidence_manifest_sha256"]:
            raise SystemExit(f"first-pair evidence changed: {leg['leg_id']}")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for name, recorded in manifest.get("sha256", {}).items():
            evidence_path = Path(manifest["paths"][name])
            if not evidence_path.is_file() or _sha256(evidence_path) != recorded:
                raise SystemExit(f"first-pair constituent evidence changed: {leg['leg_id']}:{name}")
    return result


def _verify_screen_request(
    run_root: Path,
    *,
    expected_sentry_principal: str,
    expected_executor_principal: str,
    require_current: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    preflight_request, gate0 = _verify_preflight_request(
        run_root,
        expected_sentry_principal=expected_sentry_principal,
        expected_executor_principal=expected_executor_principal,
        require_current=False,
    )
    result = _verify_first_pair_immutability(run_root)
    request = _read_json_object(run_root / "screen_request.json", "screen request")
    if request.get("schema_version") != 1:
        raise SystemExit("screen request schema mismatch")
    _validate_request_security(
        request,
        expected_stage=Stage.SCREEN,
        expected_sentry_principal=expected_sentry_principal,
        expected_executor_principal=expected_executor_principal,
        require_current=require_current,
    )
    preflight_request_sha256 = _sha256(run_root / "preflight_request.json")
    preflight_approval_sha256 = _sha256(run_root / "approvals/preflight.json")
    expected_evidence = {leg["leg_id"]: leg["evidence_manifest_sha256"] for leg in result["legs"]}
    expected_trials = {leg["leg_id"]: _sha256(Path(leg["trial_summary"])) for leg in result["legs"]}
    checks = {
        "preflight_request_sha256": preflight_request_sha256,
        "signed_preflight_decision_sha256": preflight_approval_sha256,
        "parent_decision_sha256": preflight_approval_sha256,
        "parent_request_sha256": preflight_request_sha256,
        "gate0": gate0,
        "gate1_trust": gate0["gate1_trust"],
        "evidence_hashes": expected_evidence,
        "trial_summary_hashes": expected_trials,
        "source_identity": preflight_request["source_identity"],
    }
    for field, expected in checks.items():
        if request.get(field) != expected:
            raise SystemExit(f"screen request {field} mismatch")
    if result.get("screen_request_sha256") != _sha256(run_root / "screen_request.json"):
        raise SystemExit("first-pair result screen-request hash mismatch")
    return request, gate0


def second_pair_phase(
    run_root: Path,
    approval_path: Path,
    *,
    sentry_public_key: Path,
    sentry_principal: str,
    executor_principal: str,
) -> int:
    _require_canonical_run_root(run_root)
    _read_state(run_root, "first_pair_complete")
    request_path = run_root / "screen_request.json"
    _verify_screen_request(
        run_root,
        expected_sentry_principal=sentry_principal,
        expected_executor_principal=executor_principal,
        require_current=True,
    )
    request_sha256 = _sha256(request_path)
    preflight_approval_sha256 = _sha256(run_root / "approvals/preflight.json")
    preflight_request_sha256 = _sha256(run_root / "preflight_request.json")
    screen_request = _read_json_object(request_path, "screen request")
    _verify_gate1_trust_anchor(
        sentry_public_key,
        trust=screen_request["gate1_trust"],
        expected_sentry_principal=sentry_principal,
        expected_executor_principal=executor_principal,
    )
    approval_copy = run_root / "approvals/screen.json"
    approval_sha256 = _verify_consume_and_preserve_approval(
        approval_path=approval_path,
        public_key_path=sentry_public_key,
        destination=approval_copy,
        expected_stage=Stage.SCREEN,
        expected_sentry_principal=sentry_principal,
        expected_executor_principal=executor_principal,
        expected_request_sha256=request_sha256,
        expected_parent_decision_sha256=preflight_approval_sha256,
        expected_parent_request_sha256=preflight_request_sha256,
        expected_public_key_sha256=screen_request["gate1_trust"]["public_key_sha256"],
        request_path=request_path,
        run_root=run_root,
        consumed_phase="second_pair_authorized",
    )
    _write_state(run_root, "second_pair_running", approval_consumed=True)
    _verify_screen_request(
        run_root,
        expected_sentry_principal=sentry_principal,
        expected_executor_principal=executor_principal,
        require_current=True,
    )
    if _sha256(request_path) != request_sha256 or _sha256(approval_copy) != approval_sha256:
        raise SystemExit("screen request or approval changed before second-pair execution")
    legs, complete = _run_pair_sequential(
        run_root,
        leg_ids=("b2", "a2"),
        result_name="second_pair_result.json",
        complete_status="second_pair_complete",
        repair_state="second_pair_repair_needed",
        approval_sha256=approval_sha256,
        request_sha256=request_sha256,
    )
    if not complete:
        return 1
    all_manifests = sorted((run_root / "legs").glob("*/leg_evidence_manifest.json"))
    write_json(
        run_root / "executor_evidence_manifest.json",
        {
            "schema_version": 1,
            "authority": "executor_raw_evidence",
            "leg_manifest_sha256": {str(path): _sha256(path) for path in all_manifests},
            "descriptive_hurdles": {
                "mfu_percent": HISTORICAL_MFU_HURDLE,
                "actor_tok_s": HISTORICAL_ACTOR_TOK_S_HURDLE,
                "scientific_authority": False,
            },
        },
    )
    _write_state(run_root, "complete", approval_consumed=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    run_root = Path(args.run_root).resolve()
    _require_canonical_run_root(run_root)
    if args.phase == "prepare":
        return prepare_phase(
            run_root,
            Path(args.budget_receipt).resolve(),
            gate0_permit=Path(args.gate0_permit).resolve(),
            gate0_launch_receipt=Path(args.gate0_launch_receipt).resolve(),
            gate0_booking_request=Path(args.gate0_booking_request).resolve(),
            gate0_provider_output=Path(args.gate0_provider_output).resolve(),
        )
    if args.phase == "first-pair":
        return first_pair_phase(
            run_root,
            Path(args.sentry_approval).resolve(),
            sentry_public_key=Path(args.sentry_public_key).resolve(),
            sentry_principal=args.sentry_principal,
            executor_principal=args.executor_principal,
        )
    if args.phase == "second-pair":
        return second_pair_phase(
            run_root,
            Path(args.sentry_approval).resolve(),
            sentry_public_key=Path(args.sentry_public_key).resolve(),
            sentry_principal=args.sentry_principal,
            executor_principal=args.executor_principal,
        )
    raise AssertionError(args.phase)


if __name__ == "__main__":
    raise SystemExit(main())
