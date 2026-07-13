"""Offline contract for the agentic GLM-4.7-Flash Multi-SWE Modal lane."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any, Mapping, Sequence

from w8_biayn.integrations.slime_multi_swe_cpp import (
    BENCHMARK as MULTI_SWE_BENCHMARK,
    build_public_issue_context,
    preflight_patch_paths,
)

from w8_biayn.modal_glm47 import (
    ARTIFACT_DOWNLOAD_CONCURRENCY,
    MODEL_REPO,
    MODAL_SDK_PIN,
    SERVED_MODEL_NAME,
    SUPPORTED_GPU,
    TRANSFORMERS_COMMIT,
    ensure_secret_free,
    sha256_file,
    sha256_json,
    sglang_server_command,
)
from w8_biayn.modal_multi_swe_cpp import (
    DATASET_REVISION,
    aggregate_records,
    build_artifact_manifest,
    classify_response,
    modal_app_is_stopped,
    EXPECTED_CPP_TASKS,
    SMOKE_TASK_IDS,
    validate_image_lock,
    write_json,
)


SCHEMA_VERSION = 1
BENCHMARK_LABEL = "glm47-flash-agentic-multi-swe-cpp-modal-base-eval"
RESULT_FAMILY = "repo-owned-agentic-swe-agent-multi-swe-cpp"
DEFAULT_LOCAL_ROOT = ".w8-biayn/modal/glm47-flash-agentic-multi-swe-cpp"
DEFAULT_LOCK_PATH = "examples/modal/glm47_flash_multi_swe_cpp/mswebench-images.lock.json"
SWE_AGENT_REPO = "https://github.com/SWE-agent/SWE-agent.git"
SWE_AGENT_COMMIT = "5f40e63360d654adcd91e30ed11473389bc4909b"
SWE_AGENT_VERSION = "1.1.0"
SWEREX_VERSION = "1.4.0"
SWE_AGENT_CONFIG_BLOB = "09ff379e015a8762f856a65ecf8aed61e98ed2a9"
SWE_AGENT_CONFIG_SHA256 = (
    "495d80f770346ec5f022ba1d92611f4a1cd1480802bf97903cf616b4eab4d924"
)
SWE_AGENT_TOOLS_TREE = "990255abd07c584d765eb55fedbf6d4ba8dd168d"
SWE_AGENT_EDIT_TREE = "1bec0f16bf59231cf938c42f02f5b56d4841f35a"
SWE_AGENT_REVIEW_TREE = "ffb56a9ab91a191e6f03948b9c41a0dd290dd49d"
SANITIZER_REVISION = "modal-agent-workspace-sanitizer-v2"
FINALIZER_REVISION = "trusted-final-state-diff-v1"
TOOL_PATH_REWRITER_REVISION = "root-state-path-rewriter-v1"
WORKSPACE_PROTOCOL_REVISION = "agentic-workspace-proof-v1"
WORKSPACE_CANARY_REVISION = "hostile-path-tool-compile-v2"
MODAL_ADAPTER_REVISION = "modal-swerex-adapter-v1"
SWE_AGENT_DEPENDENCY_LOCK_SHA256 = (
    "faa3132962787f012c37dd9ebc0553bd86b8d7b237c953cf1b80ec6c8bb4da8e"
)
AGENT_PLATFORM = "linux/amd64"
TRAJECTORY_SCHEMA = "agentic-multi-swe-trajectory-v1"
AGENT_CALL_LIMIT = 40
AGENT_TURN_MAX_COMPLETION_TOKENS = 32_768
AGENT_CUMULATIVE_COMPLETION_TOKENS = 131_072
AGENT_MAX_INPUT_TOKENS = 196_608
AGENT_TOTAL_TIMEOUT_SECONDS = 1200
AGENT_TOOL_TIMEOUT_SECONDS = 120
AGENT_SANDBOX_CPU = 4.0
AGENT_SANDBOX_MEMORY_MIB = 8192
AGENT_SANDBOX_LIFETIME_SECONDS = 1500
AGENT_CONCURRENCY = 4
GRADER_CPU = 2.0
GRADER_MEMORY_MIB = 2048
GRADER_TIMEOUT_SECONDS = 1200
GRADER_SANDBOX_LIFETIME_SECONDS = 1320
GRADER_CONCURRENCY = 4
OBSERVATION_CHAR_LIMIT = 32_768
PERSISTED_STREAM_BYTE_LIMIT = 65_536
MAX_FINAL_FILES = 100_000
MAX_FINAL_BYTES = 2 * 1024 * 1024 * 1024
STARTUP_TIMEOUT_SECONDS = 3600
FULL_MAX_RUN_SECONDS = 43_200
SERVER_EXECUTION_TIMEOUT_SECONDS = (
    STARTUP_TIMEOUT_SECONDS + FULL_MAX_RUN_SECONDS + 600
)
RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,39}\Z")
HEX40_RE = re.compile(r"^[0-9a-f]{40}\Z")
IMAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}\Z")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}\Z")
SOURCE_IDENTITY_PATHS = (
    "src/w8_biayn/modal_agentic_multi_swe_cpp.py",
    "src/w8_biayn/modal_agentic_multi_swe_runtime.py",
    "src/w8_biayn/integrations/modal_swe_agent_driver.py",
    "src/w8_biayn/integrations/slime_multi_swe_cpp.py",
    "examples/modal/glm47_flash_agentic_multi_swe_cpp/modal_app.py",
    "examples/modal/glm47_flash_agentic_multi_swe_cpp/run.sh",
    "examples/modal/glm47_flash_agentic_multi_swe_cpp/swe-agent.requirements.lock",
)


class ModalAgenticMultiSweError(RuntimeError):
    """An immutable agentic benchmark contract failed."""


def _required(env: Mapping[str, str], name: str) -> str:
    value = str(env.get(name, "")).strip()
    if not value:
        raise ModalAgenticMultiSweError(
            f"missing required environment variable: {name}"
        )
    return value


def _integer(env: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(str(env.get(name, default)).strip())
    except ValueError as exc:
        raise ModalAgenticMultiSweError(f"{name} must be an integer") from exc


def _floating(env: Mapping[str, str], name: str, default: float) -> float:
    try:
        return float(str(env.get(name, default)).strip())
    except ValueError as exc:
        raise ModalAgenticMultiSweError(f"{name} must be a number") from exc


def _boolean(env: Mapping[str, str], name: str) -> bool:
    value = str(env.get(name, "0")).strip()
    if value not in {"0", "1"}:
        raise ModalAgenticMultiSweError(f"{name} must be 0 or 1")
    return value == "1"


def _source_identity(repo_root: str | Path) -> tuple[str, bool]:
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"], text=True
        ).strip()
        dirty = bool(
            subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "status",
                    "--porcelain",
                    "--untracked-files=no",
                ],
                text=True,
            ).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown", False
    return commit, dirty


def _source_hashes(repo_root: str | Path) -> dict[str, str]:
    root = Path(repo_root)
    return {
        relative: sha256_file(root / relative)
        for relative in SOURCE_IDENTITY_PATHS
        if (root / relative).is_file()
    }


@dataclass(frozen=True)
class ModalAgenticMultiSweConfig:
    modal_token_id: str = field(repr=False)
    modal_token_secret: str = field(repr=False)
    modal_profile: str
    modal_environment: str
    hf_token: str = field(default="", repr=False)
    run_id: str = ""
    model_repo: str = MODEL_REPO
    model_revision: str = ""
    swe_agent_revision: str = SWE_AGENT_COMMIT
    dataset_revision: str = DATASET_REVISION
    sglang_image: str = ""
    phase: str = "plan"
    acknowledge_paid_run: bool = False
    acknowledge_long_gpu_lease: bool = False
    expected_cpp_tasks: int = EXPECTED_CPP_TASKS
    samples_per_task: int = 1
    smoke_task_ids: tuple[str, ...] = SMOKE_TASK_IDS
    gpu: str = SUPPORTED_GPU
    sglang_mem_fraction: float = 0.8
    sglang_max_running_requests: int = 16
    startup_timeout_seconds: int = STARTUP_TIMEOUT_SECONDS
    max_run_seconds: int = FULL_MAX_RUN_SECONDS
    agent_call_limit: int = AGENT_CALL_LIMIT
    agent_turn_max_completion_tokens: int = AGENT_TURN_MAX_COMPLETION_TOKENS
    agent_cumulative_completion_tokens: int = AGENT_CUMULATIVE_COMPLETION_TOKENS
    agent_max_input_tokens: int = AGENT_MAX_INPUT_TOKENS
    agent_total_timeout_seconds: int = AGENT_TOTAL_TIMEOUT_SECONDS
    agent_tool_timeout_seconds: int = AGENT_TOOL_TIMEOUT_SECONDS
    agent_concurrency: int = AGENT_CONCURRENCY
    grader_concurrency: int = GRADER_CONCURRENCY
    artifact_download_concurrency: int = ARTIFACT_DOWNLOAD_CONCURRENCY
    model_volume: str = "w8-glm47-flash-models"
    data_volume: str = "w8-multi-swe-cpp-data"
    results_volume: str = "w8-multi-swe-cpp-results"
    local_root: str = DEFAULT_LOCAL_ROOT
    image_lock_path: str = DEFAULT_LOCK_PATH
    resume: bool = False
    oracle_source_run_id: str = ""
    workspace_source_run_id: str = ""
    source_commit: str = "unknown"
    source_dirty: bool = False
    source_file_hashes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        repo_root: str | Path = ".",
    ) -> "ModalAgenticMultiSweConfig":
        env = os.environ if env is None else env
        prefix = "W8_MODAL_AGENTIC_MULTI_SWE_"
        commit, dirty = _source_identity(repo_root)
        smoke = tuple(
            item.strip()
            for item in str(
                env.get(prefix + "SMOKE_TASKS", ",".join(SMOKE_TASK_IDS))
            ).split(",")
            if item.strip()
        )
        config = cls(
            modal_token_id=_required(env, "MODAL_TOKEN_ID"),
            modal_token_secret=_required(env, "MODAL_TOKEN_SECRET"),
            modal_profile=_required(env, "MODAL_PROFILE"),
            modal_environment=str(env.get("MODAL_ENVIRONMENT", "")).strip(),
            hf_token=str(env.get("HF_TOKEN", "")).strip(),
            run_id=_required(env, prefix + "RUN_ID"),
            model_repo=_required(env, prefix + "MODEL_REPO"),
            model_revision=_required(env, prefix + "MODEL_REVISION"),
            swe_agent_revision=_required(env, prefix + "SWE_AGENT_REVISION"),
            dataset_revision=_required(env, prefix + "DATASET_REVISION"),
            sglang_image=_required(env, prefix + "SGLANG_IMAGE"),
            phase=str(env.get(prefix + "PHASE", "plan")).strip(),
            acknowledge_paid_run=_boolean(env, prefix + "ACKNOWLEDGE_PAID_RUN"),
            acknowledge_long_gpu_lease=_boolean(
                env, prefix + "ACKNOWLEDGE_LONG_GPU_LEASE"
            ),
            expected_cpp_tasks=_integer(
                env, prefix + "EXPECTED_CPP_TASKS", EXPECTED_CPP_TASKS
            ),
            samples_per_task=_integer(env, prefix + "SAMPLES_PER_TASK", 1),
            smoke_task_ids=smoke,
            gpu=str(env.get(prefix + "GPU", SUPPORTED_GPU)).strip(),
            sglang_mem_fraction=_floating(
                env, prefix + "SGLANG_MEM_FRACTION", 0.8
            ),
            sglang_max_running_requests=_integer(
                env, prefix + "SGLANG_MAX_RUNNING_REQUESTS", 16
            ),
            startup_timeout_seconds=_integer(
                env,
                prefix + "STARTUP_TIMEOUT_SECONDS",
                STARTUP_TIMEOUT_SECONDS,
            ),
            max_run_seconds=_integer(
                env, prefix + "MAX_RUN_SECONDS", FULL_MAX_RUN_SECONDS
            ),
            agent_call_limit=_integer(
                env, prefix + "AGENT_CALL_LIMIT", AGENT_CALL_LIMIT
            ),
            agent_turn_max_completion_tokens=_integer(
                env,
                prefix + "AGENT_TURN_MAX_COMPLETION_TOKENS",
                AGENT_TURN_MAX_COMPLETION_TOKENS,
            ),
            agent_cumulative_completion_tokens=_integer(
                env,
                prefix + "AGENT_CUMULATIVE_COMPLETION_TOKENS",
                AGENT_CUMULATIVE_COMPLETION_TOKENS,
            ),
            agent_max_input_tokens=_integer(
                env,
                prefix + "AGENT_MAX_INPUT_TOKENS",
                AGENT_MAX_INPUT_TOKENS,
            ),
            agent_total_timeout_seconds=_integer(
                env,
                prefix + "AGENT_TOTAL_TIMEOUT_SECONDS",
                AGENT_TOTAL_TIMEOUT_SECONDS,
            ),
            agent_tool_timeout_seconds=_integer(
                env,
                prefix + "AGENT_TOOL_TIMEOUT_SECONDS",
                AGENT_TOOL_TIMEOUT_SECONDS,
            ),
            agent_concurrency=_integer(
                env, prefix + "AGENT_CONCURRENCY", AGENT_CONCURRENCY
            ),
            grader_concurrency=_integer(
                env, prefix + "GRADER_CONCURRENCY", GRADER_CONCURRENCY
            ),
            artifact_download_concurrency=_integer(
                env,
                prefix + "ARTIFACT_DOWNLOAD_CONCURRENCY",
                ARTIFACT_DOWNLOAD_CONCURRENCY,
            ),
            model_volume=str(
                env.get(prefix + "MODEL_VOLUME", "w8-glm47-flash-models")
            ).strip(),
            data_volume=str(
                env.get(prefix + "DATA_VOLUME", "w8-multi-swe-cpp-data")
            ).strip(),
            results_volume=str(
                env.get(
                    prefix + "RESULTS_VOLUME",
                    "w8-multi-swe-cpp-results",
                )
            ).strip(),
            local_root=str(
                env.get(prefix + "LOCAL_ROOT", DEFAULT_LOCAL_ROOT)
            ).strip(),
            image_lock_path=str(
                env.get(prefix + "IMAGE_LOCK", DEFAULT_LOCK_PATH)
            ).strip(),
            resume=_boolean(env, prefix + "RESUME"),
            oracle_source_run_id=str(
                env.get(prefix + "ORACLE_SOURCE_RUN_ID", "")
            ).strip(),
            workspace_source_run_id=str(
                env.get(prefix + "WORKSPACE_SOURCE_RUN_ID", "")
            ).strip(),
            source_commit=commit,
            source_dirty=dirty,
            source_file_hashes=_source_hashes(repo_root),
        )
        config.validate(repo_root=repo_root)
        return config
    def validate(self, *, repo_root: str | Path = ".") -> None:
        errors: list[str] = []
        prefix = "W8_MODAL_AGENTIC_MULTI_SWE_"
        if not RUN_ID_RE.fullmatch(self.run_id):
            errors.append(prefix + "RUN_ID has an unsafe value")
        for source, name in (
            (self.oracle_source_run_id, "ORACLE_SOURCE_RUN_ID"),
            (self.workspace_source_run_id, "WORKSPACE_SOURCE_RUN_ID"),
        ):
            if source and (
                not RUN_ID_RE.fullmatch(source) or source == self.run_id
            ):
                errors.append(
                    f"{prefix}{name} must be safe and differ from current run"
                )
        for value, name in (
            (self.modal_profile, "MODAL_PROFILE"),
            (self.model_volume, "model Volume"),
            (self.data_volume, "data Volume"),
            (self.results_volume, "results Volume"),
        ):
            if not SAFE_NAME_RE.fullmatch(value):
                errors.append(f"{name} has an unsafe value")
        if len({self.model_volume, self.data_volume, self.results_volume}) != 3:
            errors.append("model, data, and results Volumes must be distinct")
        if self.model_repo != MODEL_REPO:
            errors.append(f"model repository must be exactly {MODEL_REPO}")
        if not HEX40_RE.fullmatch(self.model_revision):
            errors.append("model revision must be exact 40-character lowercase hex")
        if self.swe_agent_revision != SWE_AGENT_COMMIT:
            errors.append(
                f"SWE-agent revision must be exactly {SWE_AGENT_COMMIT}"
            )
        if self.dataset_revision != DATASET_REVISION:
            errors.append(
                f"dataset revision must be exactly {DATASET_REVISION}"
            )
        if not IMAGE_RE.fullmatch(self.sglang_image):
            errors.append("SGLang image must be digest-pinned")
        if self.phase not in {"plan", "smoke", "full"}:
            errors.append("phase must be plan, smoke, or full")
        if self.phase in {"smoke", "full"} and not self.acknowledge_paid_run:
            errors.append(prefix + "ACKNOWLEDGE_PAID_RUN=1 is required")
        if self.phase == "full" and not self.acknowledge_long_gpu_lease:
            errors.append(prefix + "ACKNOWLEDGE_LONG_GPU_LEASE=1 is required")
        if self.phase == "full" and not self.workspace_source_run_id:
            errors.append(
                prefix + "WORKSPACE_SOURCE_RUN_ID is required for full"
            )
        if self.phase == "full" and self.source_dirty:
            errors.append("full evaluation requires a clean tracked Git tree")
        if self.expected_cpp_tasks != EXPECTED_CPP_TASKS:
            errors.append("result family requires exactly 50 tasks")
        if self.samples_per_task != 1:
            errors.append("result family requires one trajectory per task")
        if self.smoke_task_ids != SMOKE_TASK_IDS:
            errors.append("smoke tasks must match checked-in two-task list")
        fixed = {
            "GPU": (self.gpu, SUPPORTED_GPU),
            "startup timeout": (
                self.startup_timeout_seconds,
                STARTUP_TIMEOUT_SECONDS,
            ),
            "maximum run time": (
                self.max_run_seconds,
                FULL_MAX_RUN_SECONDS,
            ),
            "agent calls": (self.agent_call_limit, AGENT_CALL_LIMIT),
            "turn completion tokens": (
                self.agent_turn_max_completion_tokens,
                AGENT_TURN_MAX_COMPLETION_TOKENS,
            ),
            "cumulative completion tokens": (
                self.agent_cumulative_completion_tokens,
                AGENT_CUMULATIVE_COMPLETION_TOKENS,
            ),
            "input tokens": (
                self.agent_max_input_tokens,
                AGENT_MAX_INPUT_TOKENS,
            ),
            "agent timeout": (
                self.agent_total_timeout_seconds,
                AGENT_TOTAL_TIMEOUT_SECONDS,
            ),
            "tool timeout": (
                self.agent_tool_timeout_seconds,
                AGENT_TOOL_TIMEOUT_SECONDS,
            ),
            "agent concurrency": (
                self.agent_concurrency,
                AGENT_CONCURRENCY,
            ),
            "grader concurrency": (
                self.grader_concurrency,
                GRADER_CONCURRENCY,
            ),
            "download concurrency": (
                self.artifact_download_concurrency,
                ARTIFACT_DOWNLOAD_CONCURRENCY,
            ),
            "SGLang memory fraction": (
                self.sglang_mem_fraction,
                0.8,
            ),
            "SGLang maximum running requests": (
                self.sglang_max_running_requests,
                16,
            ),
        }
        errors.extend(
            f"{name} must be exactly {expected}"
            for name, (actual, expected) in fixed.items()
            if actual != expected
        )
        if self.image_lock_path != DEFAULT_LOCK_PATH:
            errors.append("image lock path must be the checked-in Multi-SWE lock")
        if self.workspace_source_run_id and self.phase != "full":
            errors.append("workspace proof import is supported only for full")
        root = Path(repo_root).resolve()
        local = Path(self.local_root)
        local = local.resolve() if local.is_absolute() else (root / local).resolve()
        ignored = (root / ".w8-biayn").resolve()
        if local == ignored or ignored not in local.parents:
            errors.append("local artifact root must be inside .w8-biayn/")
        if self.phase != "plan" and not (
            root / self.image_lock_path
        ).is_file():
            errors.append("paid phases require the checked-in image lock")
        if errors:
            raise ModalAgenticMultiSweError("; ".join(errors))

    @property
    def app_name(self) -> str:
        return f"w8-glm47-agentic-mswe-{self.run_id}"

    @property
    def remote_run_path(self) -> str:
        return f"/runs/{self.run_id}"

    def local_run_path(self, repo_root: str | Path = ".") -> Path:
        root = Path(self.local_root)
        if not root.is_absolute():
            root = Path(repo_root).resolve() / root
        return root / "runs" / self.run_id

    def redacted_mapping(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["smoke_task_ids"] = list(self.smoke_task_ids)
        for name in ("modal_token_id", "modal_token_secret", "hf_token"):
            payload[name] = "<redacted>" if payload[name] else ""
        payload.update(
            {
                "schema_version": SCHEMA_VERSION,
                "benchmark": BENCHMARK_LABEL,
                "result_family": RESULT_FAMILY,
                "app_name": self.app_name,
                "remote_run_path": self.remote_run_path,
                "modal_sdk_pin": MODAL_SDK_PIN,
                "transformers_commit": TRANSFORMERS_COMMIT,
                "swe_agent_repo": SWE_AGENT_REPO,
                "swe_agent_commit": SWE_AGENT_COMMIT,
                "swe_agent_version": SWE_AGENT_VERSION,
                "swerex_version": SWEREX_VERSION,
                "sanitizer_revision": SANITIZER_REVISION,
                "finalizer_revision": FINALIZER_REVISION,
                "tool_path_rewriter_revision": TOOL_PATH_REWRITER_REVISION,
                "workspace_protocol_revision": WORKSPACE_PROTOCOL_REVISION,
                "workspace_canary_revision": WORKSPACE_CANARY_REVISION,
                "modal_adapter_revision": MODAL_ADAPTER_REVISION,
                "swe_agent_config_blob": SWE_AGENT_CONFIG_BLOB,
                "swe_agent_config_sha256": SWE_AGENT_CONFIG_SHA256,
                "swe_agent_tools_tree": SWE_AGENT_TOOLS_TREE,
                "swe_agent_edit_tree": SWE_AGENT_EDIT_TREE,
                "swe_agent_review_tree": SWE_AGENT_REVIEW_TREE,
                "swe_agent_dependency_lock_sha256": (
                    SWE_AGENT_DEPENDENCY_LOCK_SHA256
                ),
                "agent_platform": AGENT_PLATFORM,
                "server_execution_timeout_seconds": (
                    SERVER_EXECUTION_TIMEOUT_SECONDS
                ),
            }
        )
        return payload

    def runtime_mapping(self) -> dict[str, Any]:
        payload = self.redacted_mapping()
        for name in ("modal_token_id", "modal_token_secret", "hf_token"):
            payload.pop(name, None)
        payload["hf_token_present"] = bool(self.hf_token)
        return payload

    def identity_mapping(self) -> dict[str, Any]:
        mutable = {
            "phase",
            "acknowledge_paid_run",
            "acknowledge_long_gpu_lease",
            "resume",
            "modal_token_id",
            "modal_token_secret",
            "hf_token",
            "local_root",
            "source_dirty",
        }
        return {
            key: value
            for key, value in self.redacted_mapping().items()
            if key not in mutable
        }

    def identity_sha256(self) -> str:
        return sha256_json(self.identity_mapping())


def workspace_cache_key(
    task: Mapping[str, Any], image_digest: str
) -> str:
    """Bind workspace reuse to every trust, tool, and resource invariant."""

    return sha256_json(
        {
            "instance_id": task["instance_id"],
            "base_ref": task["base_ref"],
            "image_digest": image_digest,
            "platform": AGENT_PLATFORM,
            "submodule_identities": task.get("submodule_identities", {}),
            "workspace_protocol_revision": WORKSPACE_PROTOCOL_REVISION,
            "workspace_canary_revision": WORKSPACE_CANARY_REVISION,
            "sanitizer_revision": SANITIZER_REVISION,
            "finalizer_revision": FINALIZER_REVISION,
            "modal_adapter_revision": MODAL_ADAPTER_REVISION,
            "tool_path_rewriter_revision": TOOL_PATH_REWRITER_REVISION,
            "swe_agent_commit": SWE_AGENT_COMMIT,
            "swe_agent_config_blob": SWE_AGENT_CONFIG_BLOB,
            "swe_agent_config_sha256": SWE_AGENT_CONFIG_SHA256,
            "swe_agent_dependency_lock_sha256": (
                SWE_AGENT_DEPENDENCY_LOCK_SHA256
            ),
            "swe_agent_tool_trees": {
                "registry": SWE_AGENT_TOOLS_TREE,
                "edit": SWE_AGENT_EDIT_TREE,
                "review": SWE_AGENT_REVIEW_TREE,
            },
            "modal_sdk_pin": MODAL_SDK_PIN,
            "sandbox": {
                "cpu": AGENT_SANDBOX_CPU,
                "memory_mib": AGENT_SANDBOX_MEMORY_MIB,
                "lifetime_seconds": AGENT_SANDBOX_LIFETIME_SECONDS,
                "block_network": True,
                "secrets": [],
                "volumes": [],
                "user": "w8agent",
                "workspace": "/workspace/repo",
            },
            "limits": {
                "tool_timeout_seconds": AGENT_TOOL_TIMEOUT_SECONDS,
                "total_timeout_seconds": AGENT_TOTAL_TIMEOUT_SECONDS,
                "observation_chars": OBSERVATION_CHAR_LIMIT,
                "persisted_stream_bytes": PERSISTED_STREAM_BYTE_LIMIT,
                "max_final_files": MAX_FINAL_FILES,
                "max_final_bytes": MAX_FINAL_BYTES,
            },
        }
    )


def safe_trajectory_event(
    step: Mapping[str, Any], index: int
) -> dict[str, Any]:
    query = str(step.get("query") or "")
    output = str(step.get("output") or "")
    observation = str(step.get("observation") or "")
    return {
        "schema": TRAJECTORY_SCHEMA,
        "step": index,
        "request_sha256": hashlib.sha256(query.encode()).hexdigest(),
        "request_chars": len(query),
        "response_sha256": hashlib.sha256(output.encode()).hexdigest(),
        "response_chars": len(output),
        "action": str(step.get("action") or ""),
        "observation": observation[:OBSERVATION_CHAR_LIMIT],
        "observation_sha256": hashlib.sha256(observation.encode()).hexdigest(),
        "observation_chars": len(observation),
        "observation_truncated": (
            len(observation) > OBSERVATION_CHAR_LIMIT
        ),
    }

def agent_problem_statement(
    row: dict[str, Any], *, harness: Any, instance_id: str
) -> str:
    public = build_public_issue_context(
        row, harness=harness, instance_id=instance_id
    )
    return (
        f"{public}\n\n"
        "Work directly in the repository at /workspace/repo. Inspect the code, "
        "edit the implementation, and run focused checks as useful. Do not read "
        "outside the workspace, access the network, or edit tests, examples, "
        "documentation, CI, build metadata, generated files, or benchmark "
        "assets. Finish by submitting repository state; the trusted controller "
        "will synthesize and validate the final patch."
    )


def validate_final_patch(
    task: dict[str, Any], patch: str
) -> tuple[str, ...]:
    if not patch.strip():
        raise ModalAgenticMultiSweError(
            "final repository state produced no changes"
        )
    if "GIT binary patch" in patch or "Binary files " in patch:
        raise ModalAgenticMultiSweError("binary final patches are forbidden")
    try:
        return preflight_patch_paths(patch, task)
    except Exception as exc:
        raise ModalAgenticMultiSweError(str(exc)) from exc


def classify_agentic_result(
    *,
    task: dict[str, Any],
    finalization: Mapping[str, Any],
    execution: Mapping[str, Any] | None,
    trajectory: Mapping[str, Any],
) -> dict[str, Any]:
    patch = str(finalization.get("patch") or "")
    final_status = str(
        finalization.get("status") or "invalid_final_state"
    )
    base = {
        "task_id": task["instance_id"],
        "problem_id": task["instance_id"],
        "instance_id": task["instance_id"],
        "org": task["org"],
        "repo": task["repo"],
        "repo_full_name": task["repo_full_name"],
        "sample_index": 0,
        "benchmark": MULTI_SWE_BENCHMARK,
        "agentic": True,
        "trajectory": dict(trajectory),
        "finalization": {
            key: value
            for key, value in finalization.items()
            if key != "patch"
        },
        "patch_sha256": (
            hashlib.sha256(patch.encode()).hexdigest() if patch else None
        ),
    }
    if final_status != "valid_patch":
        reason = {
            "no_changes": "no_changes",
            "invalid_files": "invalid_files",
        }.get(final_status, "invalid_submission")
        return {
            **base,
            "score": -1.0,
            "reward": -1.0,
            "reason": reason,
            "all_tests_pass": False,
            "invalid_format": False,
            "invalid_files": final_status == "invalid_files",
            "patch_apply_error": False,
            "harness_error": False,
            "compile_error": False,
            "timeout": False,
            "tests_failed": False,
            "tests_collected": None,
            "no_tests_collected": False,
            "infrastructure_failure": False,
        }
    validate_final_patch(task, patch)
    fence = chr(96) * 3
    response = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": f"{fence}diff\n{patch.rstrip()}\n{fence}"
                },
            }
        ],
        "usage": {},
    }
    classified = classify_response(
        task=task,
        response=response,
        execution=execution,
        trusted_oracle_patch=False,
    )
    classified.update(base)
    classified["invalid_format"] = False
    return classified


def aggregate_agentic_records(
    records: Sequence[dict[str, Any]],
    *,
    oracle_summary: Mapping[str, Any],
    workspace_summary: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    summary = aggregate_records(
        records,
        oracle_summary=oracle_summary,
        provenance={
            **dict(provenance),
            "result_family": RESULT_FAMILY,
        },
    )
    summary["workspace_setup_check"] = dict(workspace_summary)
    summary["trajectory_count"] = len(records)
    summary["result_family"] = RESULT_FAMILY
    total = len(records)
    summary["no_changes_rate"] = (
        sum(row.get("reason") == "no_changes" for row in records) / total
        if total
        else 0.0
    )
    summary["invalid_submission_rate"] = (
        sum(row.get("reason") == "invalid_submission" for row in records)
        / total
        if total
        else 0.0
    )
    terminations: dict[str, int] = {}
    for row in records:
        termination = str(
            row.get("trajectory", {}).get("exit_status") or "unknown"
        )
        terminations[termination] = terminations.get(termination, 0) + 1
    summary["termination_reason_counts"] = dict(sorted(terminations.items()))
    for output_name, path in (
        ("mean_agent_calls", ("trajectory", "model_stats", "api_calls")),
        ("mean_completion_tokens", ("trajectory", "model_stats", "tokens_received")),
        ("mean_tool_calls", ("trajectory", "tool_event_count")),
        ("mean_nonzero_tool_exits", ("trajectory", "nonzero_tool_exits")),
        ("mean_tool_timeouts", ("trajectory", "tool_timeouts")),
        ("mean_changed_files", ("finalization", "changed_file_count")),
        ("mean_changed_lines", ("finalization", "changed_line_count")),
    ):
        values: list[float] = []
        for row in records:
            value: Any = row
            for key in path:
                value = value.get(key) if isinstance(value, Mapping) else None
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.append(float(value))
        summary[output_name] = sum(values) / len(values) if values else 0.0
    return summary

def render_plan(
    config: ModalAgenticMultiSweConfig,
    lock: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": BENCHMARK_LABEL,
        "result_family": RESULT_FAMILY,
        "action": (
            "no paid resources"
            if config.phase == "plan"
            else "ephemeral paid run"
        ),
        "blocking_gates": {
            "all_50_oracles_before_gpu": True,
            "all_50_workspace_proofs_before_gpu": True,
            "fixed_smoke_before_full": config.phase == "full",
            "release_gpu_before_grading": True,
            "stopped_app_before_score": config.phase == "full",
        },
        "config": config.redacted_mapping(),
        "image_lock": {
            "path": config.image_lock_path,
            "sha256": lock.get("sha256") if lock else None,
            "expected_tasks": EXPECTED_CPP_TASKS,
        },
        "imports": {
            "oracle_source_run_id": (
                config.oracle_source_run_id or None
            ),
            "oracle_source_may_be_single_turn": True,
            "workspace_source_run_id": (
                config.workspace_source_run_id or None
            ),
            "workspace_source_must_be_agentic": True,
            "exact_cache_keys": True,
            "fallback_to_execution": False,
        },
        "agent": {
            "framework": f"SWE-agent {SWE_AGENT_VERSION}",
            "commit": SWE_AGENT_COMMIT,
            "swerex": SWEREX_VERSION,
            "samples_per_task": 1,
            "temperature": 0.0,
            "top_p": 1.0,
            "call_limit": config.agent_call_limit,
            "per_turn_completion_tokens": (
                config.agent_turn_max_completion_tokens
            ),
            "cumulative_completion_tokens": (
                config.agent_cumulative_completion_tokens
            ),
            "max_input_tokens": config.agent_max_input_tokens,
            "total_timeout_seconds": (
                config.agent_total_timeout_seconds
            ),
            "tool_timeout_seconds": config.agent_tool_timeout_seconds,
            "concurrency": config.agent_concurrency,
            "sandbox": {
                "cpu": AGENT_SANDBOX_CPU,
                "memory_mib": AGENT_SANDBOX_MEMORY_MIB,
                "lifetime_seconds": AGENT_SANDBOX_LIFETIME_SECONDS,
                "block_network": True,
                "secrets": [],
                "volumes": [],
                "user": "w8agent",
                "workspace": "/workspace/repo",
            },
            "persistence": {
                "reasoning": False,
                "raw_trajectory": False,
                "observation_char_limit": OBSERVATION_CHAR_LIMIT,
                "stream_byte_limit": PERSISTED_STREAM_BYTE_LIMIT,
            },
        },
        "finalizer": {
            "revision": FINALIZER_REVISION,
            "trusted_baseline": True,
            "reject_special_files_symlinks_hardlinks": True,
            "reject_binary_patch": True,
            "git_apply_check_on_pristine_copy": True,
            "max_files": MAX_FINAL_FILES,
            "max_bytes": MAX_FINAL_BYTES,
        },
        "grader": {
            "backend": "fresh-modal-sandbox",
            "after_gpu_release": True,
            "block_network": True,
            "cpu": GRADER_CPU,
            "memory_mib": GRADER_MEMORY_MIB,
            "timeout_seconds": GRADER_TIMEOUT_SECONDS,
            "lifetime_seconds": GRADER_SANDBOX_LIFETIME_SECONDS,
            "concurrency": GRADER_CONCURRENCY,
            "secrets": [],
        },
        "server": {
            "model": SERVED_MODEL_NAME,
            "execution_timeout_seconds": (
                SERVER_EXECUTION_TIMEOUT_SECONDS
            ),
            "min_containers_at_rest": 0,
            "active_lease_during_trajectories": 1,
            "sglang_argv_redacted": [
                "<redacted>" if item == "$SGLANG_API_KEY" else item
                for item in sglang_server_command(
                    config, api_key="$SGLANG_API_KEY"
                )
            ],
        },
        "teardown_command": modal_stop_command(config),
    }


def resume_identity_mismatches(
    config: ModalAgenticMultiSweConfig,
    prior: Mapping[str, Any],
) -> list[str]:
    """Return immutable remote/local identity differences for a resumed run."""

    current = config.redacted_mapping()
    mutable = {
        "phase",
        "acknowledge_paid_run",
        "acknowledge_long_gpu_lease",
        "resume",
        "source_dirty",
        "app_name",
        "remote_run_path",
    }
    return sorted(
        key
        for key in set(prior) | set(current)
        if key not in mutable and prior.get(key) != current.get(key)
    )


def prepare_local_plan(
    config: ModalAgenticMultiSweConfig,
    *,
    repo_root: str | Path = ".",
) -> Path:
    lock_path = Path(repo_root) / config.image_lock_path
    lock = (
        validate_image_lock(lock_path)
        if lock_path.is_file()
        else None
    )
    root = config.local_run_path(repo_root)
    root.mkdir(parents=True, exist_ok=True)
    existing = {
        item.name for item in root.iterdir()
    } - {"plan.json", "config.redacted.json"}
    if existing and not config.resume:
        raise ModalAgenticMultiSweError(
            f"local run directory is nonempty: {root}"
        )
    prior_path = root / "config.redacted.json"
    if prior_path.is_file():
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
        mismatches = resume_identity_mismatches(config, prior)
        if mismatches:
            raise ModalAgenticMultiSweError(
                f"resume identity mismatch: {mismatches}"
            )
    plan = render_plan(config, lock)
    ensure_secret_free(
        plan,
        [
            config.modal_token_id,
            config.modal_token_secret,
            config.hf_token,
        ],
    )
    write_json(root / "plan.json", plan)
    write_json(
        root / "config.redacted.json", config.redacted_mapping()
    )
    return root


def build_workspace_summary(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    passed = sum(row.get("passed") is True for row in records)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "agentic-workspace-setup-check",
        "expected_tasks": EXPECTED_CPP_TASKS,
        "task_count": len(records),
        "passed": passed,
        "failed": len(records) - passed,
        "all_passed": (
            len(records) == EXPECTED_CPP_TASKS
            and passed == EXPECTED_CPP_TASKS
        ),
        "sanitizer_revision": SANITIZER_REVISION,
        "finalizer_revision": FINALIZER_REVISION,
    }


def modal_stop_command(
    config: ModalAgenticMultiSweConfig,
) -> list[str]:
    command = ["modal", "app", "stop", config.app_name, "--yes"]
    if config.modal_environment:
        command.extend(["--env", config.modal_environment])
    return command

def mark_local_teardown_verified(
    config: ModalAgenticMultiSweConfig,
    *,
    app_list_json: str | Path,
    repo_root: str | Path = ".",
) -> Path | None:
    listing = json.loads(
        Path(app_list_json).read_text(encoding="utf-8")
    )
    if not modal_app_is_stopped(listing, config.app_name):
        raise ModalAgenticMultiSweError(
            "Modal App still appears active"
        )
    receipt_path = (
        config.local_run_path(repo_root) / "run_receipt.json"
    )
    if not receipt_path.is_file():
        return None
    receipt = json.loads(
        receipt_path.read_text(encoding="utf-8")
    )
    receipt.update(
        {
            "modal_app_stopped": True,
            "teardown_status": "verified",
        }
    )
    write_json(receipt_path, receipt)
    write_json(
        receipt_path.parent / "artifact_manifest.json",
        build_artifact_manifest(receipt_path.parent),
    )
    return receipt_path


def validate_local_artifacts(
    config: ModalAgenticMultiSweConfig,
    *,
    repo_root: str | Path = ".",
) -> dict[str, Any]:
    """Reconcile, recompute, and admit a stopped local artifact copy."""

    root = config.local_run_path(repo_root)
    stage = "full" if config.phase == "full" else "smoke"
    required = {
        "plan.json",
        "config.redacted.json",
        "source.receipt.json",
        "dataset.receipt.json",
        "model-cache.receipt.json",
        "image-lock.json",
        "swe-agent.identity.json",
        "admission.response.json",
        "server.runtime.json",
        "server.receipt.json",
        "run_receipt.json",
        "artifact_manifest.json",
        "data/oracle.records.jsonl",
        "data/oracle.summary.json",
        "data/workspace.records.jsonl",
        "data/workspace.summary.json",
        f"{stage}/trajectories.jsonl",
        f"{stage}/patches.jsonl",
        f"{stage}/records.jsonl",
        f"{stage}/summary.json",
    }
    if config.phase == "full":
        required.update(
            {
                "smoke/trajectories.jsonl",
                "smoke/patches.jsonl",
                "smoke/records.jsonl",
                "smoke/summary.json",
            }
        )
    if config.oracle_source_run_id:
        required.add("data/oracle-import.json")
    if config.workspace_source_run_id:
        required.add("data/workspace-import.json")
    missing = sorted(
        relative
        for relative in required
        if not (root / relative).is_file()
    )
    if missing:
        raise ModalAgenticMultiSweError(
            f"local artifact copy is incomplete: {missing}"
        )
    for candidate in root.rglob("*"):
        mode = candidate.lstat().st_mode
        if stat.S_ISLNK(mode) or not (
            stat.S_ISDIR(mode) or stat.S_ISREG(mode)
        ):
            raise ModalAgenticMultiSweError(
                f"unsafe local artifact type: {candidate}"
            )
        if stat.S_ISREG(mode) and candidate.stat().st_nlink != 1:
            raise ModalAgenticMultiSweError(
                f"hard-linked local artifact: {candidate}"
            )
    receipt = json.loads(
        (root / "run_receipt.json").read_text(encoding="utf-8")
    )
    expected_status = "complete" if stage == "full" else "smoke_complete"
    if (
        receipt.get("status") != expected_status
        or receipt.get("result_family") != RESULT_FAMILY
    ):
        raise ModalAgenticMultiSweError(
            "run receipt status or result identity is incomplete"
        )
    if (
        receipt.get("modal_app_stopped") is not True
        or receipt.get("teardown_status") != "verified"
    ):
        raise ModalAgenticMultiSweError(
            "run receipt does not prove stopped App state"
        )
    records = [
        json.loads(line)
        for line in (root / stage / "records.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    trajectories = [
        json.loads(line)
        for line in (root / stage / "trajectories.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    patches = [
        json.loads(line)
        for line in (root / stage / "patches.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    expected = EXPECTED_CPP_TASKS if stage == "full" else len(SMOKE_TASK_IDS)
    record_ids = [str(row.get("task_id") or "") for row in records]
    trajectory_ids = [str(row.get("task_id") or "") for row in trajectories]
    patch_ids = [str(row.get("task_id") or "") for row in patches]
    if (
        len(records) != expected
        or len(set(record_ids)) != expected
        or sorted(record_ids) != sorted(trajectory_ids)
        or sorted(record_ids) != sorted(patch_ids)
        or any(row.get("infrastructure_failure") for row in records)
    ):
        raise ModalAgenticMultiSweError(
            "one complete outcome, trajectory, and patch per task are required"
        )
    if stage == "smoke" and set(record_ids) != set(SMOKE_TASK_IDS):
        raise ModalAgenticMultiSweError("fixed smoke task set changed")
    task_files = sorted((root / "data/tasks").glob("*/task.json"))
    safe_tasks = {
        json.loads(item.read_text(encoding="utf-8"))["instance_id"]
        for item in task_files
    }
    if len(safe_tasks) != EXPECTED_CPP_TASKS:
        raise ModalAgenticMultiSweError(
            "safe all-task metadata set is incomplete"
        )
    if stage == "full" and set(record_ids) != safe_tasks:
        raise ModalAgenticMultiSweError("full task set changed")
    for task_id in record_ids:
        trajectory_root = root / stage / "trajectories" / task_id
        per_task = {
            "identity.json",
            "events.jsonl",
            "summary.json",
            "workspace.receipt.json",
            "final-state.manifest.json",
            "final.patch",
            "final-patch.receipt.json",
        }
        absent = sorted(
            name for name in per_task if not (trajectory_root / name).is_file()
        )
        if absent or not (root / stage / "prompts" / f"{task_id}.txt").is_file():
            raise ModalAgenticMultiSweError(
                f"trajectory artifact unit is incomplete for {task_id}: {absent}"
            )
        identity = json.loads(
            (trajectory_root / "identity.json").read_text(encoding="utf-8")
        )
        prompt = (root / stage / "prompts" / f"{task_id}.txt").read_text(
            encoding="utf-8"
        )
        if identity.get("prompt_sha256") != hashlib.sha256(
            prompt.encode()
        ).hexdigest():
            raise ModalAgenticMultiSweError(
                f"prompt hash mismatch for {task_id}"
            )
    serialized = json.dumps(trajectories).lower()
    if any(
        forbidden in serialized
        for forbidden in ('"reasoning_content"', '"reasoning":', '"thought":')
    ):
        raise ModalAgenticMultiSweError(
            "trajectory artifacts contain forbidden private reasoning"
        )
    oracle_records = [
        json.loads(line)
        for line in (root / "data/oracle.records.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    workspace_records = [
        json.loads(line)
        for line in (root / "data/workspace.records.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    if (
        len(oracle_records) != EXPECTED_CPP_TASKS
        or len({row.get("task_id") for row in oracle_records})
        != EXPECTED_CPP_TASKS
        or not all(row.get("setup_valid") is True for row in oracle_records)
        or len(workspace_records) != EXPECTED_CPP_TASKS
        or len({row.get("task_id") for row in workspace_records})
        != EXPECTED_CPP_TASKS
        or not all(row.get("passed") is True for row in workspace_records)
    ):
        raise ModalAgenticMultiSweError(
            "blocking proof record sets are incomplete"
        )
    oracle = json.loads(
        (root / "data/oracle.summary.json").read_text(encoding="utf-8")
    )
    workspace = json.loads(
        (root / "data/workspace.summary.json").read_text(encoding="utf-8")
    )
    if oracle.get("all_passed") is not True or workspace.get("all_passed") is not True:
        raise ModalAgenticMultiSweError(
            "blocking oracle or workspace proof did not pass"
        )
    summary = json.loads(
        (root / stage / "summary.json").read_text(encoding="utf-8")
    )
    recomputed = aggregate_agentic_records(
        records,
        oracle_summary=oracle,
        workspace_summary=workspace,
        provenance=summary.get("provenance", {}),
    )
    if recomputed != summary:
        raise ModalAgenticMultiSweError(
            "stored agentic summary does not recompute"
        )
    for source_id, relative, lineage_name in (
        (config.oracle_source_run_id, "data/oracle-import.json", "oracle"),
        (
            config.workspace_source_run_id,
            "data/workspace-import.json",
            "workspace",
        ),
    ):
        if not source_id:
            continue
        lineage = json.loads((root / relative).read_text(encoding="utf-8"))
        if (
            lineage.get("source_run_id") != source_id
            or lineage.get("exact_cache_keys") is not True
            or lineage.get("fallback_to_execution") is not False
        ):
            raise ModalAgenticMultiSweError(
                f"{lineage_name} import lineage is incomplete"
            )
    manifest = build_artifact_manifest(root)
    stored = json.loads(
        (root / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    if manifest != stored:
        raise ModalAgenticMultiSweError(
            "local files do not match artifact manifest"
        )
    return {"receipt": receipt, "summary": summary, "manifest": manifest}

def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices={
            "plan",
            "check-app-stopped",
            "mark-stopped",
            "validate-artifacts",
            "summary",
        },
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--app-list-json")
    args = parser.parse_args(argv)
    config = ModalAgenticMultiSweConfig.from_env(
        repo_root=args.repo_root
    )
    if args.command == "plan":
        root = prepare_local_plan(
            config, repo_root=args.repo_root
        )
        print(root / "plan.json")
        return 0
    if not args.app_list_json and args.command in {
        "check-app-stopped",
        "mark-stopped",
    }:
        parser.error("--app-list-json is required")
    if args.command == "check-app-stopped":
        listing = json.loads(
            Path(args.app_list_json).read_text(
                encoding="utf-8"
            )
        )
        if not modal_app_is_stopped(listing, config.app_name):
            raise ModalAgenticMultiSweError(
                "Modal App still appears active"
            )
        return 0
    if args.command == "mark-stopped":
        mark_local_teardown_verified(
            config,
            app_list_json=args.app_list_json,
            repo_root=args.repo_root,
        )
        return 0
    validated = validate_local_artifacts(
        config, repo_root=args.repo_root
    )
    if args.command == "summary":
        summary = validated["summary"]
        print(f"status: {validated['receipt']['status']}")
        print(f"benchmark: {BENCHMARK_LABEL}")
        print(f"result_family: {RESULT_FAMILY}")
        print(f"tasks: {summary['task_count']}")
        print(f"strict_pass_rate: {summary['pass_rate']}")
        print("modal_app_stopped: true")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
