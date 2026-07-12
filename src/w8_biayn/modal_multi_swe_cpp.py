"""Pure contract for the GLM-4.7-Flash Multi-SWE C++ Modal evaluation.

Modal imports stay in the lane application.  Configuration, immutable locks,
requests, classification, resume, receipts, and artifact validation remain
offline-testable here.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Callable, Iterable, Mapping, Sequence

from w8_biayn.integrations.slime_multi_swe_cpp import (
    BENCHMARK as MULTI_SWE_BENCHMARK,
    ORACLE_PROTOCOL_VERSION,
    REPO_HARNESSES,
    aggregate_multi_swe_records,
    classify_official_test_result,
    load_multi_swe_rows,
    normalized_task,
    official_instance_script,
    parse_patch_response,
    preflight_patch_paths,
    repo_harness_for_row,
)
from w8_biayn.modal_glm47 import (
    ARTIFACT_DOWNLOAD_CONCURRENCY,
    DEFAULT_MAX_TOKENS,
    MODEL_REPO,
    MODAL_SDK_PIN,
    SERVED_MODEL_NAME,
    SGLANG_POST_GENERATION_WINDOW_SECONDS,
    SGLANG_SCALEDOWN_WINDOW_SECONDS,
    SUPPORTED_GPU,
    TRANSFORMERS_COMMIT,
    ensure_secret_free,
    sha256_file,
    sha256_json,
    sglang_server_command,
)


SCHEMA_VERSION = 1
BENCHMARK_LABEL = "glm47-flash-multi-swe-cpp-modal-base-eval"
RESULT_FAMILY = "repo-owned-single-turn-multi-swe-cpp"
DATASET_REPO = "ByteDance-Seed/Multi-SWE-bench_mini"
DATASET_FILENAME = "multi_swe_bench_mini.jsonl"
DATASET_REVISION = "d0fab3ccc7dff232fcaac234cf8af9a2efeaccf6"
EXPECTED_CPP_TASKS = 50
SAMPLES_PER_TASK = 1
SMOKE_TASK_IDS = ("catchorg__Catch2-1608", "fmtlib__fmt-1171")
DEFAULT_LOCAL_ROOT = ".w8-biayn/modal/glm47-flash-multi-swe-cpp"
DEFAULT_LOCK_PATH = "examples/modal/glm47_flash_multi_swe_cpp/mswebench-images.lock.json"
SGLANG_IMAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}$")
IMAGE_DIGEST_RE = re.compile(r"^mswebench/[a-z0-9._-]+@sha256:[0-9a-f]{64}$")
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,37}$")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
SOURCE_IDENTITY_PATHS = (
    "src/w8_biayn/modal_glm47.py",
    "src/w8_biayn/modal_multi_swe_cpp.py",
    "src/w8_biayn/modal_multi_swe_runtime.py",
    "src/w8_biayn/integrations/slime_multi_swe_cpp.py",
    "examples/modal/glm47_flash_multi_swe_cpp/modal_app.py",
    "examples/modal/glm47_flash_multi_swe_cpp/run.sh",
)
SIMDJSON_MODAL_MOUNT_LAYOUT = "single-parent-v1"
SIMDJSON_MODAL_MOUNT_RELATIVE = "modal-sandbox-dependencies"
ORACLE_SOURCE_MIGRATION_FIELDS = frozenset({"source_commit", "source_file_hashes"})


class ModalMultiSweError(RuntimeError):
    """A benchmark configuration, admission, or artifact contract failed."""


def _required(env: Mapping[str, str], name: str) -> str:
    value = str(env.get(name, "")).strip()
    if not value:
        raise ModalMultiSweError(f"missing required environment variable: {name}")
    return value


def _integer(env: Mapping[str, str], name: str, default: int) -> int:
    try:
        return int(str(env.get(name, default)).strip())
    except ValueError as exc:
        raise ModalMultiSweError(f"{name} must be an integer") from exc


def _floating(env: Mapping[str, str], name: str, default: float) -> float:
    try:
        return float(str(env.get(name, default)).strip())
    except ValueError as exc:
        raise ModalMultiSweError(f"{name} must be a number") from exc


def _boolean(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    value = str(env.get(name, "1" if default else "0")).strip()
    if value not in {"0", "1"}:
        raise ModalMultiSweError(f"{name} must be 0 or 1")
    return value == "1"


def git_source_identity(repo_root: str | Path) -> tuple[str, bool]:
    root = Path(repo_root)
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
                text=True,
            ).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown", False
    return commit, dirty


def source_file_hashes(repo_root: str | Path) -> dict[str, str]:
    root = Path(repo_root)
    hashes: dict[str, str] = {}
    for relative in SOURCE_IDENTITY_PATHS:
        path = root / relative
        if path.is_file():
            hashes[relative] = sha256_file(path)
    return hashes


@dataclass(frozen=True)
class ModalMultiSweConfig:
    modal_token_id: str = field(repr=False)
    modal_token_secret: str = field(repr=False)
    modal_profile: str
    modal_environment: str
    hf_token: str = field(default="", repr=False)
    run_id: str = ""
    model_repo: str = MODEL_REPO
    model_revision: str = ""
    dataset_revision: str = DATASET_REVISION
    sglang_image: str = ""
    phase: str = "plan"
    acknowledge_paid_run: bool = False
    expected_cpp_tasks: int = EXPECTED_CPP_TASKS
    samples_per_task: int = SAMPLES_PER_TASK
    smoke_task_ids: tuple[str, ...] = SMOKE_TASK_IDS
    gpu: str = SUPPORTED_GPU
    sglang_mem_fraction: float = 0.8
    sglang_max_running_requests: int = 16
    startup_timeout_seconds: int = 3600
    max_run_seconds: int = 14_400
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = 0.0
    top_p: float = 1.0
    test_timeout_seconds: int = 1200
    sandbox_cpu: float = 2.0
    sandbox_memory_mib: int = 2048
    sandbox_lifetime_seconds: int = 1320
    grader_concurrency: int = 4
    generation_concurrency: int = 8
    artifact_download_concurrency: int = ARTIFACT_DOWNLOAD_CONCURRENCY
    model_volume: str = "w8-glm47-flash-models"
    data_volume: str = "w8-multi-swe-cpp-data"
    results_volume: str = "w8-multi-swe-cpp-results"
    local_root: str = DEFAULT_LOCAL_ROOT
    image_lock_path: str = DEFAULT_LOCK_PATH
    resume: bool = False
    source_commit: str = "unknown"
    source_dirty: bool = False

    source_file_hashes: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, *, repo_root: str | Path = "."
    ) -> "ModalMultiSweConfig":
        env = os.environ if env is None else env
        commit, dirty = git_source_identity(repo_root)
        smoke = tuple(
            item.strip()
            for item in str(
                env.get("W8_MODAL_MULTI_SWE_SMOKE_TASKS", ",".join(SMOKE_TASK_IDS))
            ).split(",")
            if item.strip()
        )
        config = cls(
            modal_token_id=_required(env, "MODAL_TOKEN_ID"),
            modal_token_secret=_required(env, "MODAL_TOKEN_SECRET"),
            modal_profile=_required(env, "MODAL_PROFILE"),
            modal_environment=str(env.get("MODAL_ENVIRONMENT", "")).strip(),
            hf_token=str(env.get("HF_TOKEN", "")).strip(),
            run_id=_required(env, "W8_MODAL_MULTI_SWE_RUN_ID"),
            model_repo=_required(env, "W8_MODAL_MULTI_SWE_MODEL_REPO"),
            model_revision=_required(env, "W8_MODAL_MULTI_SWE_MODEL_REVISION"),
            dataset_revision=_required(env, "W8_MODAL_MULTI_SWE_DATASET_REVISION"),
            sglang_image=_required(env, "W8_MODAL_MULTI_SWE_SGLANG_IMAGE"),
            phase=str(env.get("W8_MODAL_MULTI_SWE_PHASE", "plan")).strip(),
            acknowledge_paid_run=_boolean(env, "W8_MODAL_MULTI_SWE_ACKNOWLEDGE_PAID_RUN"),
            expected_cpp_tasks=_integer(
                env, "W8_MODAL_MULTI_SWE_EXPECTED_CPP_TASKS", EXPECTED_CPP_TASKS
            ),
            samples_per_task=_integer(env, "W8_MODAL_MULTI_SWE_SAMPLES_PER_TASK", SAMPLES_PER_TASK),
            smoke_task_ids=smoke,
            gpu=str(env.get("W8_MODAL_MULTI_SWE_GPU", SUPPORTED_GPU)).strip(),
            sglang_mem_fraction=_floating(env, "W8_MODAL_MULTI_SWE_SGLANG_MEM_FRACTION", 0.8),
            sglang_max_running_requests=_integer(
                env, "W8_MODAL_MULTI_SWE_SGLANG_MAX_RUNNING_REQUESTS", 16
            ),
            startup_timeout_seconds=_integer(
                env, "W8_MODAL_MULTI_SWE_STARTUP_TIMEOUT_SECONDS", 3600
            ),
            max_run_seconds=_integer(env, "W8_MODAL_MULTI_SWE_MAX_RUN_SECONDS", 14_400),
            max_tokens=_integer(env, "W8_MODAL_MULTI_SWE_MAX_TOKENS", DEFAULT_MAX_TOKENS),
            temperature=_floating(env, "W8_MODAL_MULTI_SWE_TEMPERATURE", 0.0),
            top_p=_floating(env, "W8_MODAL_MULTI_SWE_TOP_P", 1.0),
            test_timeout_seconds=_integer(env, "W8_MODAL_MULTI_SWE_TEST_TIMEOUT_SECONDS", 1200),
            sandbox_cpu=_floating(env, "W8_MODAL_MULTI_SWE_SANDBOX_CPU", 2.0),
            sandbox_memory_mib=_integer(env, "W8_MODAL_MULTI_SWE_SANDBOX_MEMORY_MIB", 2048),
            sandbox_lifetime_seconds=_integer(
                env, "W8_MODAL_MULTI_SWE_SANDBOX_LIFETIME_SECONDS", 1320
            ),
            grader_concurrency=_integer(env, "W8_MODAL_MULTI_SWE_GRADER_CONCURRENCY", 4),
            generation_concurrency=_integer(env, "W8_MODAL_MULTI_SWE_GENERATION_CONCURRENCY", 8),
            artifact_download_concurrency=_integer(
                env, "W8_MODAL_MULTI_SWE_ARTIFACT_DOWNLOAD_CONCURRENCY", 16
            ),
            model_volume=str(
                env.get("W8_MODAL_MULTI_SWE_MODEL_VOLUME", "w8-glm47-flash-models")
            ).strip(),
            data_volume=str(
                env.get("W8_MODAL_MULTI_SWE_DATA_VOLUME", "w8-multi-swe-cpp-data")
            ).strip(),
            results_volume=str(
                env.get("W8_MODAL_MULTI_SWE_RESULTS_VOLUME", "w8-multi-swe-cpp-results")
            ).strip(),
            local_root=str(env.get("W8_MODAL_MULTI_SWE_LOCAL_ROOT", DEFAULT_LOCAL_ROOT)).strip(),
            image_lock_path=str(
                env.get("W8_MODAL_MULTI_SWE_IMAGE_LOCK", DEFAULT_LOCK_PATH)
            ).strip(),
            resume=_boolean(env, "W8_MODAL_MULTI_SWE_RESUME"),
            source_commit=commit,
            source_dirty=dirty,
            source_file_hashes=source_file_hashes(repo_root),
        )
        config.validate(repo_root=repo_root)
        return config

    def validate(self, *, repo_root: str | Path = ".") -> None:
        errors = []
        if not RUN_ID_RE.fullmatch(self.run_id):
            errors.append("W8_MODAL_MULTI_SWE_RUN_ID has an unsafe value")
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
        if self.dataset_revision != DATASET_REVISION:
            errors.append(f"dataset revision must match checked-in lock {DATASET_REVISION}")
        if self.phase not in {"plan", "smoke", "full"}:
            errors.append("phase must be plan, smoke, or full")
        if self.phase in {"smoke", "full"} and not self.acknowledge_paid_run:
            errors.append("W8_MODAL_MULTI_SWE_ACKNOWLEDGE_PAID_RUN=1 is required")
        if not SGLANG_IMAGE_RE.fullmatch(self.sglang_image):
            errors.append("SGLang image must be digest-pinned")
        if self.expected_cpp_tasks != EXPECTED_CPP_TASKS:
            errors.append("the first result family requires exactly 50 tasks")
        if self.samples_per_task != 1:
            errors.append("the first result family requires one sample per task")
        if self.smoke_task_ids != SMOKE_TASK_IDS:
            errors.append("smoke task list must match the checked-in two-task list")
        if self.gpu != SUPPORTED_GPU:
            errors.append(f"GPU must be exactly {SUPPORTED_GPU}")
        if self.temperature != 0.0 or self.top_p != 1.0:
            errors.append("the first result family requires temperature=0 and top_p=1")
        if not 256 <= self.max_tokens <= DEFAULT_MAX_TOKENS:
            errors.append("max tokens must be in [256, 32768]")
        if not 60 <= self.startup_timeout_seconds <= 3600:
            errors.append("startup timeout must be in [60, 3600]")
        if not 60 <= self.test_timeout_seconds <= 1200:
            errors.append("test timeout must be in [60, 1200]")
        if self.sandbox_cpu != 2.0 or self.sandbox_memory_mib != 2048:
            errors.append("Sandbox resources must be exactly 2 CPU and 2048 MiB")
        if self.sandbox_lifetime_seconds < self.test_timeout_seconds + 120:
            errors.append("Sandbox lifetime must exceed test timeout by at least 120 seconds")
        if not 1 <= self.grader_concurrency <= 4:
            errors.append("grader concurrency must be in [1, 4]")
        if not 1 <= self.generation_concurrency <= 16:
            errors.append("generation concurrency must be in [1, 16]")
        if self.artifact_download_concurrency != 16:
            errors.append("artifact download concurrency must be exactly 16")
        repo = Path(repo_root).resolve()
        local = (
            (repo / self.local_root).resolve()
            if not Path(self.local_root).is_absolute()
            else Path(self.local_root).resolve()
        )
        ignored = (repo / ".w8-biayn").resolve()
        if local == ignored or ignored not in local.parents:
            errors.append("local artifact root must be inside .w8-biayn/")
        lock = (repo / self.image_lock_path).resolve()
        if self.phase != "plan" and not lock.is_file():
            errors.append("paid phases require the checked-in image lock")
        if self.phase == "full" and self.source_dirty:
            errors.append("full evaluation requires a clean tracked Git tree")
        if errors:
            raise ModalMultiSweError("; ".join(errors))

    @property
    def app_name(self) -> str:
        return f"w8-glm47-multi-swe-cpp-{self.run_id}"

    @property
    def remote_run_path(self) -> str:
        return f"/runs/{self.run_id}"

    def local_run_path(self, repo_root: str | Path = ".") -> Path:
        root = Path(repo_root).resolve()
        local = Path(self.local_root)
        return (local if local.is_absolute() else root / local) / "runs" / self.run_id

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
                "modal_sdk_pin": MODAL_SDK_PIN,
                "transformers_commit": TRANSFORMERS_COMMIT,
                "server_scaledown_window_seconds": SGLANG_SCALEDOWN_WINDOW_SECONDS,
                "server_post_generation_window_seconds": SGLANG_POST_GENERATION_WINDOW_SECONDS,
                "app_name": self.app_name,
                "remote_run_path": self.remote_run_path,
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
        excluded = {
            "phase",
            "acknowledge_paid_run",
            "resume",
            "modal_token_id",
            "modal_token_secret",
            "hf_token",
            "local_root",
            "source_dirty",
        }
        return {key: value for key, value in self.redacted_mapping().items() if key not in excluded}

    def identity_sha256(self) -> str:
        return sha256_json(self.identity_mapping())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: str | Path, payload: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)


def validate_image_lock(
    path: str | Path,
    *,
    dataset_revision: str = DATASET_REVISION,
    expected_task_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    lock_path = Path(path)
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModalMultiSweError(f"unreadable image lock: {lock_path}") from exc
    if (
        lock.get("schema_version") != 1
        or lock.get("dataset_repo") != DATASET_REPO
        or lock.get("dataset_revision") != dataset_revision
        or lock.get("platform") != "linux/amd64"
        or lock.get("expected_tasks") != EXPECTED_CPP_TASKS
    ):
        raise ModalMultiSweError("image lock header does not match benchmark identity")
    tasks = lock.get("tasks")
    if not isinstance(tasks, dict) or len(tasks) != EXPECTED_CPP_TASKS:
        raise ModalMultiSweError("image lock must contain exactly 50 task rows")
    expected = set(expected_task_ids) if expected_task_ids is not None else set(tasks)
    if set(tasks) != expected:
        raise ModalMultiSweError("image lock task set does not match dataset C++ task set")
    for task_id, row in tasks.items():
        if not isinstance(row, dict):
            raise ModalMultiSweError(f"invalid image lock row: {task_id}")
        tag = row.get("tag")
        digest = row.get("digest")
        if (
            not isinstance(tag, str)
            or tag != tag.lower()
            or ":pr-" not in tag
            or not isinstance(digest, str)
            or not IMAGE_DIGEST_RE.fullmatch(digest)
            or digest.split("@", 1)[0] != tag.rsplit(":", 1)[0]
        ):
            raise ModalMultiSweError(f"mutable or mismatched image lock row: {task_id}")
    lock["sha256"] = sha256_file(lock_path)
    return lock


def _linux_amd64_manifest_digest(payload: Any) -> str:
    candidates: list[Mapping[str, Any]] = []
    if isinstance(payload, list):
        candidates.extend(item for item in payload if isinstance(item, dict))
    elif isinstance(payload, dict):
        manifests = payload.get("manifests")
        if isinstance(manifests, list):
            candidates.extend(item for item in manifests if isinstance(item, dict))
        else:
            candidates.append(payload)
    for item in candidates:
        descriptor = item.get("Descriptor") or item
        platform = item.get("Platform") or descriptor.get("platform") or {}
        digest = descriptor.get("digest")
        if (
            isinstance(platform, dict)
            and platform.get("os") == "linux"
            and platform.get("architecture") == "amd64"
            and isinstance(digest, str)
            and re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
        ):
            return digest
    raise ModalMultiSweError("registry response has no linux/amd64 manifest digest")


def resolve_linux_amd64_image(tag: str) -> str:
    try:
        output = subprocess.check_output(
            ["docker", "manifest", "inspect", "--verbose", tag], text=True
        )
        digest = _linux_amd64_manifest_digest(json.loads(output))
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        raise ModalMultiSweError(f"could not resolve image manifest: {tag}") from exc
    return tag.rsplit(":", 1)[0] + "@" + digest


def generate_image_lock(
    dataset_jsonl: str | Path,
    *,
    resolver: Callable[[str], str] = resolve_linux_amd64_image,
) -> dict[str, Any]:
    rows = sorted(
        (row for row in load_multi_swe_rows(dataset_jsonl) if repo_harness_for_row(row)),
        key=lambda row: str(row["instance_id"]),
    )
    if len(rows) != EXPECTED_CPP_TASKS:
        raise ModalMultiSweError("dataset must select exactly 50 supported C++ tasks")
    tasks: dict[str, dict[str, str]] = {}
    for row in rows:
        harness = repo_harness_for_row(row)
        assert harness is not None
        task_id = str(row["instance_id"])
        task = normalized_task(row, harness=harness, instance_id=task_id)
        tag = str(task["sandbox_image"])
        digest = resolver(tag)
        if (
            tag != tag.lower()
            or not IMAGE_DIGEST_RE.fullmatch(digest)
            or digest.split("@", 1)[0] != tag.rsplit(":", 1)[0]
        ):
            raise ModalMultiSweError(
                f"resolver returned an invalid linux/amd64 digest for {task_id}"
            )
        tasks[task_id] = {"tag": tag, "digest": digest}
    return {
        "schema_version": 1,
        "dataset_repo": DATASET_REPO,
        "dataset_revision": DATASET_REVISION,
        "platform": "linux/amd64",
        "expected_tasks": EXPECTED_CPP_TASKS,
        "tasks": tasks,
    }


def model_request(config: ModalMultiSweConfig, prompt: str) -> dict[str, Any]:
    return {
        "model": SERVED_MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "top_p": config.top_p,
        "stream": False,
    }


def response_metadata(response: Mapping[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    choice = (
        choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    )
    message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
    content = message.get("content")
    reasoning = message.get("reasoning_content")
    usage = response.get("usage") if isinstance(response.get("usage"), dict) else {}
    return {
        "response_keys": sorted(response),
        "message_keys": sorted(message),
        "finish_reason": choice.get("finish_reason"),
        "content_present": isinstance(content, str) and bool(content.strip()),
        "content_chars": len(content) if isinstance(content, str) else 0,
        "reasoning_content_present": isinstance(reasoning, str) and bool(reasoning.strip()),
        "reasoning_content_chars": len(reasoning) if isinstance(reasoning, str) else 0,
        "usage": {
            key: value
            for key, value in usage.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        },
    }


def editable_content(response: Mapping[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise ModalMultiSweError("model response must contain exactly one choice")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise ModalMultiSweError("model response has no editable content")
    return message["content"]


def classify_response(
    *,
    task: dict[str, Any],
    response: Mapping[str, Any],
    execution: Mapping[str, Any] | None,
    trusted_oracle_patch: bool = False,
) -> dict[str, Any]:
    base = {
        "task_id": task["instance_id"],
        "problem_id": task["instance_id"],
        "instance_id": task["instance_id"],
        "org": task["org"],
        "repo": task["repo"],
        "repo_full_name": task["repo_full_name"],
        "sample_index": 0,
        "benchmark": MULTI_SWE_BENCHMARK,
        "response_metadata": response_metadata(response),
        "response_sha256": response_sha256(response),
    }
    try:
        content = editable_content(response)
        patch = parse_patch_response(content)
        if not trusted_oracle_patch:
            preflight_patch_paths(patch, task)
    except Exception as exc:
        reason = getattr(exc, "reason", "invalid_format")
        return {
            **base,
            "score": -1.0,
            "reward": -1.0,
            "reason": reason,
            "all_tests_pass": False,
            "invalid_format": reason == "invalid_format",
            "invalid_files": reason == "invalid_files",
            "patch_apply_error": False,
            "harness_error": False,
            "compile_error": False,
            "timeout": False,
            "tests_failed": False,
            "tests_collected": None,
            "no_tests_collected": False,
            "recovered_format": False,
            "recovered_all_tests_pass": False,
            "exception": str(exc),
        }
    if execution is None:
        raise ModalMultiSweError("valid patch response is missing its Sandbox execution")
    result = classify_official_test_result(
        returncode=execution.get("returncode"),
        logs=str(execution.get("logs") or ""),
        timed_out=bool(execution.get("timed_out")),
        sandbox_image=str(execution.get("image") or ""),
        sandbox_image_id=str(execution.get("sandbox_id") or ""),
    )
    if result.passed:
        score, reason = 1.0, "passed"
    elif result.patch_apply_error:
        score, reason = -0.75, "patch_apply_error"
    elif result.no_tests_collected:
        score, reason = -0.5, "no_tests_collected"
    elif result.harness_error:
        score, reason = -0.5, "harness_error"
    elif result.timeout:
        score, reason = -0.5, "timeout"
    elif any(
        needle in result.logs.lower() for needle in ("error:", "cmake error", "undefined reference")
    ):
        score, reason = -0.5, "compile_error"
    else:
        score, reason = 0.0, "tests_failed"
    return {
        **base,
        "score": score,
        "reward": score,
        "reason": reason,
        "all_tests_pass": reason == "passed",
        "invalid_format": False,
        "invalid_files": False,
        "patch_apply_error": reason == "patch_apply_error",
        "harness_error": reason in {"harness_error", "no_tests_collected"},
        "compile_error": reason == "compile_error",
        "timeout": reason == "timeout",
        "tests_failed": reason == "tests_failed",
        "tests_collected": result.tests_collected,
        "no_tests_collected": result.no_tests_collected,
        "recovered_format": False,
        "recovered_all_tests_pass": False,
        "sandbox": dict(execution),
    }


def oracle_cache_key(
    config: ModalMultiSweConfig, task: Mapping[str, Any], lock_row: Mapping[str, Any]
) -> str:
    harness = REPO_HARNESSES[(str(task["org"]).lower(), str(task["repo"]).lower())]
    identity = {
        "backend": "modal-sandbox-v1",
        "protocol_version": ORACLE_PROTOCOL_VERSION,
        "task_id": task["instance_id"],
        "base_ref": task.get("base_ref"),
        "fix_patch_sha256": hashlib.sha256(str(task.get("fix_patch") or "").encode()).hexdigest(),
        "test_patch_sha256": hashlib.sha256(str(task.get("test_patch") or "").encode()).hexdigest(),
        "image": lock_row["digest"],
        "platform": "linux/amd64",
        "repo_harness_revision": task.get("repo_harness_revision"),
        "offline_dependency_bundle_sha256": task.get("offline_dependency_bundle_sha256"),
        "script_sha256": hashlib.sha256(
            official_instance_script(
                dict(task), harness, timeout_s=config.test_timeout_seconds
            ).encode()
        ).hexdigest(),
        "cpu": config.sandbox_cpu,
        "memory_mib": config.sandbox_memory_mib,
        "timeout_seconds": config.test_timeout_seconds,
        "network": "blocked",
    }
    if task.get("offline_dependency_bundle_sha256"):
        identity["offline_dependency_mount_layout"] = SIMDJSON_MODAL_MOUNT_LAYOUT
    return sha256_json(identity)


def model_request_sha256(request: Mapping[str, Any]) -> str:
    return sha256_json(request)


def response_sha256(response: Mapping[str, Any]) -> str:
    return sha256_json(response)


def grader_cache_key(
    config: ModalMultiSweConfig,
    task: Mapping[str, Any],
    lock_row: Mapping[str, Any],
    response: Mapping[str, Any],
) -> str:
    return sha256_json(
        {
            "backend": "modal-sandbox-v1",
            "oracle_setup_cache_key": oracle_cache_key(config, task, lock_row),
            "response_sha256": response_sha256(response),
            "output_tail_bytes": 65536,
            "infrastructure_retries": 1,
        }
    )


def render_plan(
    config: ModalMultiSweConfig, lock: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": BENCHMARK_LABEL,
        "result_family": RESULT_FAMILY,
        "action": "no paid resources" if config.phase == "plan" else "ephemeral paid run",
        "blocking_oracle": config.phase in {"smoke", "full"},
        "blocking_smoke": config.phase == "full",
        "config": config.redacted_mapping(),
        "image_lock": {
            "path": config.image_lock_path,
            "sha256": lock.get("sha256") if lock else None,
            "expected_tasks": EXPECTED_CPP_TASKS,
        },
        "request_template": model_request(config, "<saved prompt>"),
        "sglang_argv_redacted": [
            "<redacted>" if item == "$SGLANG_API_KEY" else item
            for item in sglang_server_command(config, api_key="$SGLANG_API_KEY")
        ],
        "grader": {
            "backend": "modal-sandbox",
            "block_network": True,
            "cpu": [config.sandbox_cpu, config.sandbox_cpu],
            "memory_mib": [config.sandbox_memory_mib, config.sandbox_memory_mib],
            "lifetime_seconds": config.sandbox_lifetime_seconds,
            "exec_timeout_seconds": config.test_timeout_seconds,
            "concurrency": config.grader_concurrency,
            "secrets": [],
        },
        "teardown_command": modal_stop_command(config),
    }


def prepare_local_plan(config: ModalMultiSweConfig, *, repo_root: str | Path = ".") -> Path:
    lock_path = Path(repo_root) / config.image_lock_path
    lock = validate_image_lock(lock_path) if lock_path.is_file() else None
    root = config.local_run_path(repo_root)
    if root.exists() and any(root.iterdir()):
        allowed = {"plan.json", "config.redacted.json"}
        unexpected = {item.name for item in root.iterdir()} - allowed
        if unexpected and not config.resume:
            raise ModalMultiSweError(f"local run directory is nonempty: {root}")
        prior = root / "config.redacted.json"
        if prior.is_file():
            assert_resume_compatible(
                config,
                prior,
                allow_plan=True,
                allow_oracle_source_migration=config.resume and not unexpected,
            )
    root.mkdir(parents=True, exist_ok=True)
    plan = render_plan(config, lock)
    ensure_secret_free(plan, [config.modal_token_id, config.modal_token_secret, config.hf_token])
    write_json(root / "plan.json", plan)
    write_json(root / "config.redacted.json", config.redacted_mapping())
    return root


def resume_identity_mismatches(
    config: ModalMultiSweConfig, prior_config_path: str | Path
) -> list[str]:
    path = Path(prior_config_path)
    if not path.is_file():
        raise ModalMultiSweError("resume requires prior config.redacted.json")
    prior = json.loads(path.read_text(encoding="utf-8"))
    current = config.redacted_mapping()
    excluded = {
        "phase",
        "acknowledge_paid_run",
        "resume",
        "local_root",
        "source_dirty",
        "app_name",
        "remote_run_path",
    }
    return [
        key
        for key in sorted(set(prior) | set(current))
        if key not in excluded and prior.get(key) != current.get(key)
    ]


def assert_resume_compatible(
    config: ModalMultiSweConfig,
    prior_config_path: str | Path,
    *,
    allow_plan: bool = False,
    allow_oracle_source_migration: bool = False,
) -> None:
    mismatches = resume_identity_mismatches(config, prior_config_path)
    source_only_migration = (
        allow_oracle_source_migration
        and bool(mismatches)
        and set(mismatches) <= ORACLE_SOURCE_MIGRATION_FIELDS
    )
    if mismatches and not source_only_migration:
        raise ModalMultiSweError(f"resume identity mismatch: {mismatches}")
    if not config.resume and not allow_plan:
        raise ModalMultiSweError("existing run requires W8_MODAL_MULTI_SWE_RESUME=1")


def build_artifact_manifest(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    rows = []
    total = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if relative.as_posix() == "artifact_manifest.json":
            continue
        if relative.is_absolute() or ".." in relative.parts:
            raise ModalMultiSweError(f"unsafe artifact path: {path}")
        size = path.stat().st_size
        total += size
        rows.append({"path": relative.as_posix(), "size_bytes": size, "sha256": sha256_file(path)})
    return {
        "schema_version": SCHEMA_VERSION,
        "file_count": len(rows),
        "aggregate_size_bytes": total,
        "files": rows,
    }


def aggregate_records(
    records: Sequence[dict[str, Any]],
    *,
    oracle_summary: Mapping[str, Any],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    if any(row.get("infrastructure_failure") for row in records):
        raise ModalMultiSweError("infrastructure-failed records block model aggregation")
    summary = aggregate_multi_swe_records(records, label="base")
    summary["oracle_setup_check"] = dict(oracle_summary)
    summary["provenance"] = dict(provenance)
    if any(key in summary for key in ("correct_and_faster_rate", "runtime_speedup")):
        raise ModalMultiSweError("PIE speed metrics are forbidden in Multi-SWE summaries")
    return summary


def modal_stop_command(config: ModalMultiSweConfig) -> list[str]:
    command = ["modal", "app", "stop", config.app_name, "--yes"]
    if config.modal_environment:
        command.extend(["--env", config.modal_environment])
    return command


def modal_app_is_stopped(value: Any, app_name: str) -> bool:
    rows = value if isinstance(value, list) else value.get("apps", [])
    if not isinstance(rows, list):
        raise ModalMultiSweError("Modal App listing is not a list")
    live = {"running", "deployed", "initializing", "ephemeral", "active"}
    for row in rows:
        if not isinstance(row, dict):
            continue
        lowered = {str(key).lower(): item for key, item in row.items()}
        name = str(lowered.get("name") or lowered.get("app_name") or "")
        state = str(lowered.get("state") or lowered.get("status") or "").lower()
        if name == app_name and (state in live or not state):
            return False
    return True


def mark_local_teardown_verified(
    config: ModalMultiSweConfig, *, app_list_json: str | Path, repo_root: str | Path = "."
) -> Path | None:
    listing = json.loads(Path(app_list_json).read_text(encoding="utf-8"))
    if not modal_app_is_stopped(listing, config.app_name):
        raise ModalMultiSweError("Modal App still appears active")
    receipt_path = config.local_run_path(repo_root) / "run_receipt.json"
    if not receipt_path.is_file():
        return None
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["modal_app_stopped"] = True
    receipt["teardown_status"] = "verified"
    receipt["teardown_verified_at_utc"] = utc_now()
    write_json(receipt_path, receipt)
    write_json(
        receipt_path.parent / "artifact_manifest.json", build_artifact_manifest(receipt_path.parent)
    )
    return receipt_path


def validate_local_artifacts(
    config: ModalMultiSweConfig, *, repo_root: str | Path = "."
) -> dict[str, Any]:
    root = config.local_run_path(repo_root)
    required = {
        "plan.json",
        "config.redacted.json",
        "source.receipt.json",
        "dataset.receipt.json",
        "model-cache.receipt.json",
        "image-lock.json",
        "server.receipt.json",
        "run_receipt.json",
        "artifact_manifest.json",
    }
    missing = sorted(name for name in required if not (root / name).is_file())
    if missing:
        raise ModalMultiSweError(f"local artifact copy is incomplete: {missing}")
    receipt = json.loads((root / "run_receipt.json").read_text(encoding="utf-8"))
    expected_status = "complete" if config.phase == "full" else "smoke_complete"
    if receipt.get("status") != expected_status:
        raise ModalMultiSweError("run receipt status is incomplete")
    if receipt.get("modal_app_stopped") is not True or receipt.get("teardown_status") != "verified":
        raise ModalMultiSweError("run receipt does not prove stopped App state")
    stage = "full" if config.phase == "full" else "smoke"
    records_path = root / stage / "records.jsonl"
    summary_path = root / stage / "summary.json"
    oracle_path = root / "data" / "oracle.summary.json"
    if not all(path.is_file() for path in (records_path, summary_path, oracle_path)):
        raise ModalMultiSweError("local result records or oracle proof are missing")
    records = [
        json.loads(line)
        for line in records_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    expected = EXPECTED_CPP_TASKS if stage == "full" else len(SMOKE_TASK_IDS)
    if len(records) != expected or len({row.get("task_id") for row in records}) != expected:
        raise ModalMultiSweError("local result set has wrong task cardinality")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
    recomputed = aggregate_records(
        records,
        oracle_summary=oracle,
        provenance=summary.get("provenance", {}),
    )
    if recomputed != summary:
        raise ModalMultiSweError("stored summary does not recompute from per-task records")
    manifest = build_artifact_manifest(root)
    stored = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    if manifest != stored:
        raise ModalMultiSweError("local files do not match artifact manifest")
    return {"receipt": receipt, "summary": summary, "manifest": manifest}


def _print_summary(validated: Mapping[str, Any], path: Path) -> None:
    receipt = validated["receipt"]
    summary = validated["summary"]
    print(f"status: {receipt['status']}")
    print(f"benchmark: {BENCHMARK_LABEL}")
    print(f"result_family: {RESULT_FAMILY}")
    print(f"model: {receipt['model_repo']}@{receipt['model_revision']}")
    print(f"dataset: {DATASET_REPO}@{receipt['dataset_revision']}")
    print(f"tasks: {summary['task_count']}/{receipt['expected_tasks']}")
    print(f"strict_pass_rate: {summary['pass_rate']}")
    print(f"oracle_setup: {receipt['oracle_passed']}/{EXPECTED_CPP_TASKS} passed")
    print("harness_backend: modal-sandbox")
    print("modal_app_stopped: true")
    print(f"artifacts: {path}")


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "validate-artifacts", "summary"):
        item = sub.add_parser(name)
        item.add_argument("--repo-root", default=".")
    stopped = sub.add_parser("mark-stopped")
    stopped.add_argument("--repo-root", default=".")
    stopped.add_argument("--app-list-json", required=True)
    check = sub.add_parser("check-app-stopped")
    check.add_argument("--repo-root", default=".")
    check.add_argument("--app-list-json", required=True)
    lock = sub.add_parser("verify-lock")
    lock.add_argument("--lock", default=DEFAULT_LOCK_PATH)
    generate = sub.add_parser("generate-lock")
    generate.add_argument("--dataset-jsonl", required=True)
    generate.add_argument("--out", default=DEFAULT_LOCK_PATH)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify-lock":
            print(json.dumps(validate_image_lock(args.lock), indent=2, sort_keys=True))
            return 0
        if args.command == "generate-lock":
            payload = generate_image_lock(args.dataset_jsonl)
            write_json(args.out, payload)
            validate_image_lock(args.out, expected_task_ids=payload["tasks"])
            print(f"lock: {args.out}")
            return 0
        config = ModalMultiSweConfig.from_env(repo_root=args.repo_root)
        if args.command == "plan":
            root = prepare_local_plan(config, repo_root=args.repo_root)
            print(
                json.dumps(
                    render_plan(
                        config, validate_image_lock(Path(args.repo_root) / config.image_lock_path)
                    ),
                    indent=2,
                    sort_keys=True,
                )
            )
            print(f"plan: {root / 'plan.json'}")
            return 0
        if args.command == "check-app-stopped":
            listing = json.loads(Path(args.app_list_json).read_text(encoding="utf-8"))
            if not modal_app_is_stopped(listing, config.app_name):
                raise ModalMultiSweError("deterministic Modal App is already active")
            print("app_preflight: stopped")
            return 0
        if args.command == "mark-stopped":
            mark_local_teardown_verified(
                config, app_list_json=args.app_list_json, repo_root=args.repo_root
            )
            print("teardown: verified")
            return 0
        validated = validate_local_artifacts(config, repo_root=args.repo_root)
        if args.command == "validate-artifacts":
            print(json.dumps(validated, indent=2, sort_keys=True))
        else:
            _print_summary(validated, config.local_run_path(args.repo_root))
        return 0
    except (ModalMultiSweError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
