"""Pure contract for the GLM-4.7-Flash official Aider/Modal base evaluation.

This module deliberately has no Modal import.  Configuration, redaction,
command construction, cache validation, Aider result admission, receipts, and
artifact checks therefore stay testable without credentials, network access,
or a GPU.  ``examples/modal/glm47_flash_aider_polyglot_cpp/modal_app.py`` is
the only Modal-aware boundary.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence

import yaml


SCHEMA_VERSION = 1
BENCHMARK_LABEL = "aider-polyglot-cpp-modal-base-eval"
SEQUENTIAL_EVAL_MODE = "sequential-repair"
INDEPENDENT_EVAL_MODE = "independent-pass-at-1-and-8"
INDEPENDENT_RESULT_LABEL = (
    "repo-derived independent pass@1/pass@8 by cumulative Aider try depth"
)
INDEPENDENT_SAMPLES_PER_TASK = 8
INDEPENDENT_TRIES = 2
PASS_AT_ESTIMATOR_VERSION = "independent-aider-two-try-v2"
MODEL_REPO = "zai-org/GLM-4.7-Flash"
SERVED_MODEL_NAME = "glm-4.7-flash"
AIDER_MODEL_NAME = "openai/glm-4.7-flash"
AIDER_REPO_URL = "https://github.com/Aider-AI/aider.git"
TRANSFORMERS_REPO_URL = "https://github.com/huggingface/transformers.git"
TRANSFORMERS_COMMIT = "76732b4e7120808ff989edbd16401f61fa6a0afa"
POLYGLOT_REPO_URL = "https://github.com/Aider-AI/polyglot-benchmark.git"
MODAL_SDK_PIN = "1.5.2"
SGLANG_ADMISSION_MAX_TOKENS = 2048
DEFAULT_MAX_TOKENS = 32_768
SGLANG_SCALEDOWN_WINDOW_SECONDS = 20 * 60
SGLANG_POST_RUN_SCALEDOWN_WINDOW_SECONDS = 2
ARTIFACT_DOWNLOAD_CONCURRENCY = 16
DEFAULT_LOCAL_ROOT = ".w8-biayn/modal/glm47-flash-aider-polyglot-cpp"
MODEL_SETTINGS_PATH = "/run/glm47_flash.model.settings.yml"
SENSITIVE_NAMES = (
    "MODAL_TOKEN_ID",
    "MODAL_TOKEN_SECRET",
    "HF_TOKEN",
    "SGLANG_API_KEY",
)
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,37}$")
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
SGLANG_IMAGE_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}$")
SUPPORTED_GPU = "H100!:4"
REQUIRED_SGLANG_FLAGS = (
    "--model-path",
    "--tp-size",
    "--tool-call-parser",
    "--reasoning-parser",
    "--speculative-algorithm",
    "--speculative-num-steps",
    "--speculative-eagle-topk",
    "--speculative-num-draft-tokens",
    "--mem-fraction-static",
    "--max-running-requests",
    "--served-model-name",
    "--api-key",
    "--host",
    "--port",
)
AUTHORITATIVE_STATS_FIELDS = (
    "test_cases",
    "model",
    "edit_format",
    "commit_hash",
    "pass_rate_1",
    "pass_rate_2",
    "pass_num_1",
    "pass_num_2",
    "percent_cases_well_formed",
    "error_outputs",
    "num_malformed_responses",
    "num_with_malformed_responses",
    "user_asks",
    "lazy_comments",
    "syntax_errors",
    "indentation_errors",
    "exhausted_context_windows",
    "prompt_tokens",
    "completion_tokens",
    "test_timeouts",
    "total_tests",
    "seconds_per_case",
    "total_cost",
)


class ModalAiderError(RuntimeError):
    """A configuration, admission, artifact, or orchestration contract error."""


def _required(env: Mapping[str, str], name: str) -> str:
    value = str(env.get(name, "")).strip()
    if not value:
        raise ModalAiderError(f"missing required environment variable: {name}")
    return value


def _integer(env: Mapping[str, str], name: str, default: int) -> int:
    raw = str(env.get(name, default)).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise ModalAiderError(f"{name} must be an integer") from exc


def _floating(env: Mapping[str, str], name: str, default: float) -> float:
    raw = str(env.get(name, default)).strip()
    try:
        return float(raw)
    except ValueError as exc:
        raise ModalAiderError(f"{name} must be a number") from exc


def _boolean(env: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = str(env.get(name, "1" if default else "0")).strip()
    if raw not in {"0", "1"}:
        raise ModalAiderError(f"{name} must be 0 or 1")
    return raw == "1"


@dataclass(frozen=True)
class ModalAiderConfig:
    """Complete validated configuration for one ephemeral Modal evaluation."""

    modal_token_id: str = field(repr=False)
    modal_token_secret: str = field(repr=False)
    modal_profile: str
    modal_environment: str
    hf_token: str = field(default="", repr=False)
    run_id: str = ""
    model_repo: str = MODEL_REPO
    model_revision: str = ""
    aider_commit: str = ""
    polyglot_commit: str = ""
    sglang_image: str = ""
    phase: str = "plan"
    acknowledge_paid_run: bool = False
    expected_cpp_tasks: int = 26
    gpu: str = SUPPORTED_GPU
    sglang_mem_fraction: float = 0.8
    sglang_max_running_requests: int = 16
    startup_timeout_seconds: int = 3600
    max_run_seconds: int = 7200
    edit_format: str = "whole"
    tries: int = 2
    threads: int = 8
    max_tokens: int = DEFAULT_MAX_TOKENS
    temperature: float = 0.7
    top_p: float = 1.0
    smoke_tests: int = 2
    model_volume: str = "w8-glm47-flash-models"
    results_volume: str = "w8-aider-polyglot-cpp-results"
    local_root: str = DEFAULT_LOCAL_ROOT
    resume: bool = False
    eval_mode: str = SEQUENTIAL_EVAL_MODE
    samples_per_task: int = INDEPENDENT_SAMPLES_PER_TASK
    base_seed: int = 0
    acknowledge_pass_at_8: bool = False

    @classmethod
    def from_env(
        cls,
        env: Mapping[str, str] | None = None,
        *,
        repo_root: str | Path = ".",
    ) -> "ModalAiderConfig":
        env = os.environ if env is None else env
        config = cls(
            modal_token_id=_required(env, "MODAL_TOKEN_ID"),
            modal_token_secret=_required(env, "MODAL_TOKEN_SECRET"),
            modal_profile=_required(env, "MODAL_PROFILE"),
            modal_environment=str(env.get("MODAL_ENVIRONMENT", "")).strip(),
            hf_token=str(env.get("HF_TOKEN", "")).strip(),
            run_id=_required(env, "W8_MODAL_AIDER_RUN_ID"),
            model_repo=_required(env, "W8_MODAL_AIDER_MODEL_REPO"),
            model_revision=_required(env, "W8_MODAL_AIDER_MODEL_REVISION"),
            aider_commit=_required(env, "W8_MODAL_AIDER_AIDER_COMMIT"),
            polyglot_commit=_required(env, "W8_MODAL_AIDER_POLYGLOT_COMMIT"),
            sglang_image=_required(env, "W8_MODAL_AIDER_SGLANG_IMAGE"),
            phase=str(env.get("W8_MODAL_AIDER_PHASE", "plan")).strip(),
            acknowledge_paid_run=_boolean(env, "W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN"),
            expected_cpp_tasks=_integer(env, "W8_MODAL_AIDER_EXPECTED_CPP_TASKS", 26),
            gpu=str(env.get("W8_MODAL_AIDER_GPU", SUPPORTED_GPU)).strip(),
            sglang_mem_fraction=_floating(env, "W8_MODAL_AIDER_SGLANG_MEM_FRACTION", 0.8),
            sglang_max_running_requests=_integer(
                env, "W8_MODAL_AIDER_SGLANG_MAX_RUNNING_REQUESTS", 16
            ),
            startup_timeout_seconds=_integer(env, "W8_MODAL_AIDER_STARTUP_TIMEOUT_SECONDS", 3600),
            max_run_seconds=_integer(env, "W8_MODAL_AIDER_MAX_RUN_SECONDS", 7200),
            edit_format=str(env.get("W8_MODAL_AIDER_EDIT_FORMAT", "whole")).strip(),
            tries=_integer(env, "W8_MODAL_AIDER_TRIES", 2),
            threads=_integer(env, "W8_MODAL_AIDER_THREADS", 8),
            max_tokens=_integer(env, "W8_MODAL_AIDER_MAX_TOKENS", DEFAULT_MAX_TOKENS),
            temperature=_floating(env, "W8_MODAL_AIDER_TEMPERATURE", 0.7),
            top_p=_floating(env, "W8_MODAL_AIDER_TOP_P", 1.0),
            smoke_tests=_integer(env, "W8_MODAL_AIDER_SMOKE_TESTS", 2),
            model_volume=str(
                env.get("W8_MODAL_AIDER_MODEL_VOLUME", "w8-glm47-flash-models")
            ).strip(),
            results_volume=str(
                env.get("W8_MODAL_AIDER_RESULTS_VOLUME", "w8-aider-polyglot-cpp-results")
            ).strip(),
            local_root=str(env.get("W8_MODAL_AIDER_LOCAL_ROOT", DEFAULT_LOCAL_ROOT)).strip(),
            resume=_boolean(env, "W8_MODAL_AIDER_RESUME"),
            eval_mode=str(
                env.get("W8_MODAL_AIDER_EVAL_MODE", SEQUENTIAL_EVAL_MODE)
            ).strip(),
            samples_per_task=_integer(
                env, "W8_MODAL_AIDER_SAMPLES_PER_TASK", INDEPENDENT_SAMPLES_PER_TASK
            ),
            base_seed=_integer(env, "W8_MODAL_AIDER_BASE_SEED", 0),
            acknowledge_pass_at_8=_boolean(
                env, "W8_MODAL_AIDER_ACKNOWLEDGE_PASS_AT_8"
            ),
        )
        config.validate(repo_root=repo_root)
        return config

    def validate(self, *, repo_root: str | Path = ".") -> None:
        errors: list[str] = []
        if not RUN_ID_RE.fullmatch(self.run_id):
            errors.append("W8_MODAL_AIDER_RUN_ID must match ^[a-z0-9][a-z0-9-]{2,37}$")
        for value, name in (
            (self.modal_profile, "MODAL_PROFILE"),
            (self.model_volume, "W8_MODAL_AIDER_MODEL_VOLUME"),
            (self.results_volume, "W8_MODAL_AIDER_RESULTS_VOLUME"),
        ):
            if not SAFE_NAME_RE.fullmatch(value):
                errors.append(f"{name} is not a safe Modal name")
        if self.modal_environment and not SAFE_NAME_RE.fullmatch(self.modal_environment):
            errors.append("MODAL_ENVIRONMENT is not a safe Modal name")
        if self.model_repo != MODEL_REPO:
            errors.append(f"W8_MODAL_AIDER_MODEL_REPO must be exactly {MODEL_REPO}")
        for value, name in (
            (self.model_revision, "W8_MODAL_AIDER_MODEL_REVISION"),
            (self.aider_commit, "W8_MODAL_AIDER_AIDER_COMMIT"),
            (self.polyglot_commit, "W8_MODAL_AIDER_POLYGLOT_COMMIT"),
        ):
            if not HEX40_RE.fullmatch(value):
                errors.append(f"{name} must be an exact 40-character lowercase hex commit")
        if self.phase not in {"plan", "smoke", "full"}:
            errors.append("W8_MODAL_AIDER_PHASE must be plan, smoke, or full")
        if self.phase in {"smoke", "full"} and not self.acknowledge_paid_run:
            errors.append("W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN=1 is required for smoke/full")
        if self.phase == "full" and not SGLANG_IMAGE_RE.fullmatch(self.sglang_image):
            errors.append("full runs require a digest-pinned SGLang image")
        elif self.phase != "full" and not (
            SGLANG_IMAGE_RE.fullmatch(self.sglang_image)
            or re.fullmatch(r"[a-z0-9][a-z0-9._/-]*:[A-Za-z0-9._-]+", self.sglang_image)
        ):
            errors.append("SGLang image must be a registry tag or sha256 digest")
        if self.gpu != SUPPORTED_GPU:
            errors.append(f"the first supported GPU profile is exactly {SUPPORTED_GPU}")
        if not 0.1 <= self.sglang_mem_fraction <= 0.95:
            errors.append("SGLang memory fraction must be in [0.1, 0.95]")
        if not 1 <= self.sglang_max_running_requests <= 64:
            errors.append("SGLang max running requests must be in [1, 64]")
        if not 60 <= self.startup_timeout_seconds <= 3600:
            errors.append("startup timeout must be in [60, 3600] seconds")
        if not 60 <= self.max_run_seconds <= 14_400:
            errors.append("max run timeout must be in [60, 14400] seconds")
        if self.edit_format != "whole":
            errors.append("the first supported Aider edit format is exactly whole")
        if not 1 <= self.tries <= 2:
            errors.append("Aider tries must be in [1, 2]")
        if not 1 <= self.threads <= 16:
            errors.append("Aider threads must be in [1, 16]")
        if not 1 <= self.smoke_tests <= 3:
            errors.append("smoke tests must be in [1, 3]")
        if self.expected_cpp_tasks <= 0:
            errors.append("expected C++ task count must be positive")
        if not 256 <= self.max_tokens <= 32_768:
            errors.append("max tokens must be in [256, 32768]")
        if not 0.0 <= self.temperature <= 2.0:
            errors.append("temperature must be in [0, 2]")
        if not 0.0 < self.top_p <= 1.0:
            errors.append("top_p must be in (0, 1]")
        if self.eval_mode not in {SEQUENTIAL_EVAL_MODE, INDEPENDENT_EVAL_MODE}:
            errors.append(
                "W8_MODAL_AIDER_EVAL_MODE must be sequential-repair or "
                "independent-pass-at-1-and-8"
            )
        if self.base_seed < 0:
            errors.append("W8_MODAL_AIDER_BASE_SEED must be nonnegative")
        if self.eval_mode == INDEPENDENT_EVAL_MODE:
            if self.samples_per_task != INDEPENDENT_SAMPLES_PER_TASK:
                errors.append("independent pass@8 mode requires exactly 8 samples per task")
            if self.tries != INDEPENDENT_TRIES:
                errors.append("independent pass@8 mode requires W8_MODAL_AIDER_TRIES=2")
            if self.temperature <= 0:
                errors.append("independent pass@8 mode requires positive sampling temperature")
            if self.phase in {"smoke", "full"} and not self.acknowledge_pass_at_8:
                errors.append(
                    "W8_MODAL_AIDER_ACKNOWLEDGE_PASS_AT_8=1 is required for paid pass@8"
                )
        repo = Path(repo_root).resolve()
        local = (
            (repo / self.local_root).resolve()
            if not Path(self.local_root).is_absolute()
            else Path(self.local_root).resolve()
        )
        ignored = (repo / ".w8-biayn").resolve()
        if local == ignored or ignored not in local.parents:
            errors.append("local artifact root must be contained inside repository .w8-biayn/")
        if self.model_volume == self.results_volume:
            errors.append("model and result Volumes must be separate")
        if errors:
            raise ModalAiderError("; ".join(errors))

    @property
    def app_name(self) -> str:
        return f"w8-aider-polyglot-cpp-{self.run_id}"

    @property
    def remote_run_path(self) -> str:
        return f"/runs/{self.run_id}"

    def local_run_path(self, repo_root: str | Path = ".") -> Path:
        root = Path(repo_root).resolve()
        local = Path(self.local_root)
        if not local.is_absolute():
            local = root / local
        return local / "runs" / self.run_id

    def redacted_mapping(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("modal_token_id", "modal_token_secret", "hf_token"):
            payload[key] = "<redacted>" if payload.get(key) else ""
        payload.update(
            {
                "schema_version": SCHEMA_VERSION,
                "benchmark": BENCHMARK_LABEL,
                "modal_sdk_pin": MODAL_SDK_PIN,
                "transformers_repo_url": TRANSFORMERS_REPO_URL,
                "transformers_commit": TRANSFORMERS_COMMIT,
                "sglang_scaledown_window_seconds": SGLANG_SCALEDOWN_WINDOW_SECONDS,
                "app_name": self.app_name,
                "remote_run_path": self.remote_run_path,
            }
        )
        return payload

    def runtime_mapping(self) -> dict[str, Any]:
        """Return non-secret configuration safe to pass to Modal workers."""

        payload = self.redacted_mapping()
        payload.pop("modal_token_id", None)
        payload.pop("modal_token_secret", None)
        payload.pop("hf_token", None)
        payload["hf_token_present"] = bool(self.hf_token)
        return payload

    def identity_mapping(self) -> dict[str, Any]:
        """Fields which must match when resuming an incomplete run."""

        excluded = {
            "phase",
            "acknowledge_paid_run",
            "acknowledge_pass_at_8",
            "resume",
            "modal_token_id",
            "modal_token_secret",
            "hf_token",
            "local_root",
        }
        payload = {key: value for key, value in asdict(self).items() if key not in excluded}
        payload["transformers_repo_url"] = TRANSFORMERS_REPO_URL
        payload["transformers_commit"] = TRANSFORMERS_COMMIT
        payload["sglang_scaledown_window_seconds"] = SGLANG_SCALEDOWN_WINDOW_SECONDS
        return payload

    def identity_sha256(self) -> str:
        return sha256_json(self.identity_mapping())


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: str | Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def render_plan(config: ModalAiderConfig) -> dict[str, Any]:
    """Render the deterministic, printable, fully redacted launch plan."""

    plan = {
        "schema_version": SCHEMA_VERSION,
        "benchmark": BENCHMARK_LABEL,
        "action": "no paid resources" if config.phase == "plan" else "ephemeral paid run",
        "blocking_smoke": config.phase == "full",
        "config": config.redacted_mapping(),
        "aider_smoke_argv": aider_benchmark_command(config, stage="smoke"),
        "transformers_repo_url": TRANSFORMERS_REPO_URL,
        "transformers_commit": TRANSFORMERS_COMMIT,
        "aider_full_argv": aider_benchmark_command(config, stage="full"),
        "sglang_argv_redacted": [
            "<redacted>" if value == "$SGLANG_API_KEY" else value
            for value in sglang_server_command(config, api_key="$SGLANG_API_KEY")
        ],
        "teardown_command": modal_stop_command(config),
    }
    if config.eval_mode == INDEPENDENT_EVAL_MODE:
        plan["independent_sampling"] = {
            "result_family": INDEPENDENT_RESULT_LABEL,
            "samples_per_task": config.samples_per_task,
            "full_trajectory_count": config.expected_cpp_tasks * config.samples_per_task,
            "sampling_smoke_trajectory_count": config.smoke_tests * config.samples_per_task,
            "base_seed": config.base_seed,
            "seed_schedule": [sample_seed(config, index) for index in range(1, 9)],
            "max_tries_per_trajectory": INDEPENDENT_TRIES,
            "maximum_full_edit_attempts": (
                config.expected_cpp_tasks * config.samples_per_task * INDEPENDENT_TRIES
            ),
            "maximum_sampling_smoke_edit_attempts": (
                config.smoke_tests * config.samples_per_task * INDEPENDENT_TRIES
            ),
            "temperature": config.temperature,
            "top_p": config.top_p,
            "additional_paid_acknowledgement": config.acknowledge_pass_at_8,
        }
    return plan


def prepare_local_plan(config: ModalAiderConfig, *, repo_root: str | Path = ".") -> Path:
    run_root = config.local_run_path(repo_root)
    if run_root.exists() and any(run_root.iterdir()):
        allowed = {"plan.json", "config.redacted.json"}
        present = {path.name for path in run_root.iterdir()}
        if not present <= allowed:
            if not config.resume:
                raise ModalAiderError(
                    f"local run directory is nonempty; use a fresh run id: {run_root}"
                )
            assert_resume_compatible(config, run_root / "config.redacted.json")
        elif (run_root / "config.redacted.json").is_file():
            assert_resume_compatible(config, run_root / "config.redacted.json", allow_plan=True)
    run_root.mkdir(parents=True, exist_ok=True)
    write_json(run_root / "plan.json", render_plan(config))
    write_json(run_root / "config.redacted.json", config.redacted_mapping())
    return run_root


def modal_stop_command(config: ModalAiderConfig) -> list[str]:
    command = ["modal", "app", "stop", config.app_name, "--yes"]
    if config.modal_environment:
        command.extend(["--env", config.modal_environment])
    return command


def modal_list_command(config: ModalAiderConfig) -> list[str]:
    command = ["modal", "app", "list", "--json"]
    if config.modal_environment:
        command.extend(["--env", config.modal_environment])
    return command


def sample_seed(config: ModalAiderConfig, sample_index: int) -> int:
    if not 1 <= sample_index <= config.samples_per_task:
        raise ModalAiderError("sample index is outside the configured sample schedule")
    return config.base_seed + sample_index


def model_settings(config: ModalAiderConfig, *, sample_index: int | None = None) -> str:
    extra_params: dict[str, Any] = {
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "top_p": config.top_p,
    }
    if sample_index is not None:
        extra_params["seed"] = sample_seed(config, sample_index)
    payload = [
        {
            "name": AIDER_MODEL_NAME,
            "edit_format": config.edit_format,
            "use_repo_map": False,
            "use_temperature": True,
            "streaming": False,
            "extra_params": extra_params,
        }
    ]
    return yaml.safe_dump(payload, sort_keys=False)


def aider_benchmark_command(
    config: ModalAiderConfig,
    *,
    stage: str,
    result_name: str | None = None,
    settings_path: str = MODEL_SETTINGS_PATH,
    exercises_dir: str = "polyglot-benchmark",
) -> list[str]:
    if stage not in {"smoke", "full"}:
        raise ModalAiderError("Aider stage must be smoke or full")
    name = result_name or f"{config.run_id}-{stage}"
    command = [
        "/aider/benchmark/benchmark.py",
        name,
        "--model",
        AIDER_MODEL_NAME,
        "--edit-format",
        config.edit_format,
        "--languages",
        "cpp",
        "--tries",
        "1" if stage == "smoke" else str(config.tries),
        "--threads",
        "1" if stage == "smoke" else str(config.threads),
    ]
    if stage == "smoke":
        command.extend(["--num-tests", str(config.smoke_tests)])
    command.extend(
        [
            "--exercises-dir",
            exercises_dir,
            "--read-model-settings",
            settings_path,
        ]
    )
    if config.resume and stage == "full":
        command.append("--cont")
    return command


def independent_sample_command(
    config: ModalAiderConfig,
    *,
    sample_index: int,
    smoke: bool = False,
    settings_path: str,
    exercises_dir: str,
) -> list[str]:
    """Build one isolated two-try Aider trajectory for the independent protocol."""

    sample_seed(config, sample_index)
    result_name = f"{config.run_id}-{'smoke-' if smoke else ''}sample-{sample_index:02d}"
    command = aider_benchmark_command(
        config,
        stage="full",
        result_name=result_name,
        settings_path=settings_path,
        exercises_dir=exercises_dir,
    )
    command[command.index("--tries") + 1] = str(INDEPENDENT_TRIES)
    if smoke:
        command[command.index("--threads") + 1] = "1"
        command.extend(["--num-tests", str(config.smoke_tests)])
    return command


def aider_stats_command(result_dir: str | Path) -> list[str]:
    return ["/aider/benchmark/benchmark.py", "--stats", str(result_dir)]


def sglang_server_command(
    config: ModalAiderConfig,
    *,
    api_key: str,
    model_root: str = "/models",
) -> list[str]:
    model_path = f"{model_root}/zai-org--GLM-4.7-Flash/{config.model_revision}"
    return [
        "python",
        "-m",
        "sglang.launch_server",
        "--model-path",
        model_path,
        "--tp-size",
        "4",
        "--tool-call-parser",
        "glm47",
        "--reasoning-parser",
        "glm45",
        "--speculative-algorithm",
        "EAGLE",
        "--speculative-num-steps",
        "3",
        "--speculative-eagle-topk",
        "1",
        "--speculative-num-draft-tokens",
        "4",
        "--mem-fraction-static",
        str(config.sglang_mem_fraction),
        "--max-running-requests",
        str(config.sglang_max_running_requests),
        "--served-model-name",
        SERVED_MODEL_NAME,
        "--api-key",
        api_key,
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
    ]


def validate_sglang_help(help_text: str) -> None:
    missing = [flag for flag in REQUIRED_SGLANG_FLAGS if flag not in help_text]
    if missing:
        raise ModalAiderError(f"pinned SGLang image is missing required flags: {missing}")


def validate_model_snapshot(
    snapshot: str | Path,
    *,
    expected_repo: str = MODEL_REPO,
    expected_revision: str,
    minimum_weight_bytes: int = 1_000_000_000,
) -> dict[str, Any]:
    """Validate a cached HF snapshot, including every indexed weight shard."""

    root = Path(snapshot)
    required = [root / "config.json", root / "model.safetensors.index.json"]
    tokenizer_candidates = [
        root / "tokenizer.json",
        root / "tokenizer_config.json",
        root / "tokenizer.model",
    ]
    missing = [path.name for path in required if not path.is_file()]
    if not any(path.is_file() for path in tokenizer_candidates):
        missing.append("tokenizer material")
    if missing:
        raise ModalAiderError(f"model snapshot is incomplete; missing {missing}")
    try:
        index = json.loads((root / "model.safetensors.index.json").read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ModalAiderError("model safetensors index is unreadable") from exc
    weight_map = index.get("weight_map")
    if not isinstance(weight_map, dict) or not weight_map:
        raise ModalAiderError("model safetensors index has no weight_map")
    shard_names = sorted(set(weight_map.values()))
    if not all(isinstance(name, str) and Path(name).name == name for name in shard_names):
        raise ModalAiderError("model safetensors index contains unsafe shard names")
    absent = [name for name in shard_names if not (root / name).is_file()]
    if absent:
        raise ModalAiderError(f"model snapshot is missing indexed shards: {absent[:5]}")
    weight_bytes = sum((root / name).stat().st_size for name in shard_names)
    if weight_bytes < minimum_weight_bytes:
        raise ModalAiderError(
            f"model weight bytes are implausibly small: {weight_bytes} < {minimum_weight_bytes}"
        )
    files: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        files.append(
            {
                "path": relative,
                "size_bytes": size,
                "sha256": sha256_file(path) if size <= 64 * 1024 * 1024 else None,
            }
        )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "model_repo": expected_repo,
        "model_revision": expected_revision,
        "weight_shards": shard_names,
        "weight_bytes": weight_bytes,
        "files": files,
    }
    manifest["manifest_sha256"] = sha256_json(manifest)
    return manifest


def _coerce_stat(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?(?:\d+\.\d+|\d+\.)", value):
        return float(value)
    return value


def parse_aider_stats(text: str) -> dict[str, Any]:
    """Extract Aider's printed stats fields without recomputing outcomes."""

    stats: dict[str, Any] = {}
    for line in text.splitlines():
        clean = re.sub(r"\x1b\[[0-9;]*m", "", line).strip()
        match = re.match(r"^-?\s*([a-z][a-z0-9_]*)\s*:\s*(.*?)\s*$", clean)
        if not match:
            continue
        key, raw = match.groups()
        if key in AUTHORITATIVE_STATS_FIELDS or key == "dirname":
            stats[key] = _coerce_stat(raw)
    if "test_cases" not in stats:
        raise ModalAiderError("Aider stats output did not contain test_cases")
    return stats


@dataclass(frozen=True)
class AiderResultAdmission:
    result_dir: str
    expected_tasks: int
    completed_tasks: int
    exception_tasks: int
    chat_histories: int
    test_invocations: int
    exhausted_context_windows: int
    task_names: tuple[str, ...]

    def as_mapping(self) -> dict[str, Any]:
        return asdict(self)


def validate_aider_results(
    result_dir: str | Path,
    *,
    expected_tasks: int,
    require_chat_histories: bool = True,
    reject_all_exhausted: bool = True,
) -> AiderResultAdmission:
    root = Path(result_dir)
    paths = sorted(root.glob("cpp/exercises/practice/*/.aider.results.json"))
    if len(paths) != expected_tasks:
        raise ModalAiderError(
            f"expected {expected_tasks} Aider result files, found {len(paths)} in {root}"
        )
    exceptions = 0
    histories = 0
    test_invocations = 0
    exhausted = 0
    names: list[str] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ModalAiderError(f"malformed Aider result JSON: {path}") from exc
        if not isinstance(payload, dict) or not payload:
            raise ModalAiderError(f"empty Aider result row: {path}")
        if payload.get("exception"):
            exceptions += 1
            continue
        outcomes = payload.get("tests_outcomes")
        if not isinstance(outcomes, list) or not outcomes:
            raise ModalAiderError(f"Aider result has no completed C++ test invocation: {path}")
        test_invocations += len(outcomes)
        exhausted += int(payload.get("num_exhausted_context_windows", 0) or 0)
        history = path.with_name(".aider.chat.history.md")
        if history.is_file() and history.stat().st_size > 0:
            histories += 1
        names.append(path.parent.name)
    if exceptions:
        raise ModalAiderError(f"Aider produced {exceptions} exception-only result rows")
    if require_chat_histories and histories != expected_tasks:
        raise ModalAiderError(
            f"expected {expected_tasks} nonempty Aider chat histories, found {histories}"
        )
    if test_invocations == 0:
        raise ModalAiderError("Aider completed no C++ test invocation")
    if reject_all_exhausted and exhausted >= test_invocations:
        raise ModalAiderError("all Aider attempts exhausted their context windows")
    return AiderResultAdmission(
        result_dir=str(root),
        expected_tasks=expected_tasks,
        completed_tasks=len(paths),
        exception_tasks=exceptions,
        chat_histories=histories,
        test_invocations=test_invocations,
        exhausted_context_windows=exhausted,
        task_names=tuple(sorted(names)),
    )


def summarize_aider_exceptions(root: str | Path) -> list[dict[str, str]]:
    """Summarize official exception rows without copying full tracebacks."""

    rows = []
    for path in sorted(Path(root).glob("**/.aider.results.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        exception = payload.get("exception")
        if not isinstance(exception, str) or not exception.strip():
            continue
        final_line = exception.strip().splitlines()[-1][-1000:]
        exception_type = final_line.split(":", 1)[0].strip()
        rows.append(
            {
                "task": path.parent.name,
                "exception_type": exception_type,
                "exception_final_line": final_line,
            }
        )
    return rows


def summarize_aider_result_diagnostics(root: str | Path) -> list[dict[str, Any]]:
    """Summarize result counters without copying prompts or model-generated text."""

    def counter(payload: Mapping[str, Any], name: str) -> int:
        try:
            return int(payload.get(name, 0) or 0)
        except (TypeError, ValueError):
            return 0

    rows = []
    for path in sorted(Path(root).glob("**/.aider.results.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict):
            continue
        outcomes = payload.get("tests_outcomes")
        rows.append(
            {
                "task": path.parent.name,
                "exception": bool(payload.get("exception")),
                "test_invocations": len(outcomes) if isinstance(outcomes, list) else 0,
                "exhausted_context_windows": counter(payload, "num_exhausted_context_windows"),
                "prompt_tokens": counter(payload, "prompt_tokens"),
                "completion_tokens": counter(payload, "completion_tokens"),
            }
        )
    return rows


def validate_authoritative_stats(stats: Mapping[str, Any], *, expected_tasks: int) -> None:
    if int(stats.get("test_cases", -1)) != expected_tasks:
        raise ModalAiderError(
            f"Aider stats test_cases={stats.get('test_cases')} did not match {expected_tasks}"
        )
    if str(stats.get("model", "")) != AIDER_MODEL_NAME:
        raise ModalAiderError("Aider stats model identity does not match GLM-4.7-Flash")
    if str(stats.get("edit_format", "")) != "whole":
        raise ModalAiderError("Aider stats edit format is not whole")
    if "pass_rate_1" not in stats:
        raise ModalAiderError("Aider stats are missing pass_rate_1")


def _two_try_result_row(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ModalAiderError(f"malformed Aider result JSON: {path}") from exc
    if not isinstance(payload, dict) or not payload:
        raise ModalAiderError(f"empty Aider result row: {path}")
    if payload.get("exception"):
        raise ModalAiderError(f"infrastructure exception blocks pass@8 admission: {path}")
    outcomes = payload.get("tests_outcomes")
    if (
        not isinstance(outcomes, list)
        or not 1 <= len(outcomes) <= INDEPENDENT_TRIES
        or not all(isinstance(value, bool) for value in outcomes)
    ):
        raise ModalAiderError(
            f"independent trajectory must contain one or two boolean test outcomes: {path}"
        )
    if outcomes[0] and len(outcomes) != 1:
        raise ModalAiderError(f"Aider continued after a passing first try: {path}")
    if not outcomes[0] and len(outcomes) != INDEPENDENT_TRIES:
        raise ModalAiderError(f"failed first try is missing its second-try outcome: {path}")
    history = path.with_name(".aider.chat.history.md")
    if not history.is_file() or history.stat().st_size == 0:
        raise ModalAiderError(f"independent trajectory is missing its chat history: {path}")
    return payload


def validate_independent_aider_results(
    result_dir: str | Path, *, expected_tasks: int
) -> AiderResultAdmission:
    """Admit complete official two-try trajectories without rescoring Aider edits."""

    admission = validate_aider_results(
        result_dir,
        expected_tasks=expected_tasks,
        reject_all_exhausted=False,
    )
    for path in sorted(Path(result_dir).glob("cpp/exercises/practice/*/.aider.results.json")):
        _two_try_result_row(path)
    return admission


def validate_independent_authoritative_stats(
    stats: Mapping[str, Any], *, result_dir: str | Path, expected_tasks: int
) -> None:
    """Allow omitted pass_rate_2 only when every trajectory passed on try 1."""

    validate_authoritative_stats(stats, expected_tasks=expected_tasks)
    reached_try_2 = False
    for path in sorted(Path(result_dir).glob("cpp/exercises/practice/*/.aider.results.json")):
        payload = _two_try_result_row(path)
        reached_try_2 = reached_try_2 or len(payload["tests_outcomes"]) == INDEPENDENT_TRIES
    if reached_try_2 and "pass_rate_2" not in stats:
        raise ModalAiderError("two-try Aider stats are missing pass_rate_2")


def independent_config_fingerprint(config: ModalAiderConfig) -> str:
    """Fingerprint all cross-sample fields while leaving index/derived seed explicit."""

    return sha256_json(
        {
            **config.identity_mapping(),
            "eval_mode": INDEPENDENT_EVAL_MODE,
            "seed_schedule": "base_seed + one_based_sample_index",
            "estimator_version": PASS_AT_ESTIMATOR_VERSION,
        }
    )


def build_independent_pass_report(
    config: ModalAiderConfig,
    *,
    sample_result_dirs: Mapping[int, str | Path],
    out: str | Path,
    expected_tasks: int,
    persist: bool = True,
) -> dict[str, Any]:
    """Recompute both cumulative try-depth matrices and the four pass metrics."""

    if config.eval_mode != INDEPENDENT_EVAL_MODE:
        raise ModalAiderError("independent report requires independent-pass-at-1-and-8 mode")
    expected_indices = set(range(1, INDEPENDENT_SAMPLES_PER_TASK + 1))
    if set(sample_result_dirs) != expected_indices:
        raise ModalAiderError("independent report requires exactly sample indices 1 through 8")
    output = Path(out)
    output.mkdir(parents=True, exist_ok=True)
    fingerprint = independent_config_fingerprint(config)
    task_rows: dict[str, dict[int, dict[str, Any]]] = {}
    samples: list[dict[str, Any]] = []
    expected_task_ids: set[str] | None = None
    for sample_index in sorted(sample_result_dirs):
        result_root = Path(sample_result_dirs[sample_index])
        paths = sorted(result_root.glob("cpp/exercises/practice/*/.aider.results.json"))
        if len(paths) != expected_tasks:
            raise ModalAiderError(
                f"sample {sample_index:02d} expected {expected_tasks} rows, found {len(paths)}"
            )
        task_ids = {path.parent.name for path in paths}
        if expected_task_ids is None:
            expected_task_ids = task_ids
        elif task_ids != expected_task_ids:
            raise ModalAiderError("independent samples have mismatched task sets")
        for path in paths:
            payload = _two_try_result_row(path)
            task_id = path.parent.name
            if sample_index in task_rows.setdefault(task_id, {}):
                raise ModalAiderError(f"duplicate task/sample cell: {task_id}/{sample_index}")
            outcomes = payload["tests_outcomes"]
            try1_success = int(outcomes[0])
            try2_success = int(any(outcomes))
            if try1_success:
                outcome = "passed_try1"
            elif try2_success:
                outcome = "passed_try2"
            elif int(payload.get("num_exhausted_context_windows", 0) or 0):
                outcome = "context_exhausted"
            elif int(payload.get("num_malformed_responses", 0) or 0):
                outcome = "malformed_response"
            else:
                outcome = "failed_tests"
            try:
                official_result_path = path.relative_to(output).as_posix()
            except ValueError:
                official_result_path = path.as_posix()
            history = path.with_name(".aider.chat.history.md")
            try:
                chat_history_path = history.relative_to(output).as_posix()
            except ValueError:
                chat_history_path = history.as_posix()
            row = {
                "task_id": task_id,
                "sample_index": sample_index,
                "seed": sample_seed(config, sample_index),
                "official_result_path": official_result_path,
                "official_result_sha256": sha256_file(path),
                "chat_history_path": chat_history_path,
                "chat_history_sha256": sha256_file(history),
                "attempts_made": len(outcomes),
                "raw_tests_outcomes": outcomes,
                "try1_success": try1_success,
                "try2_success": try2_success,
                "outcome": outcome,
                "prompt_tokens": int(payload.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(payload.get("completion_tokens", 0) or 0),
                "config_fingerprint": fingerprint,
            }
            task_rows[task_id][sample_index] = row
            samples.append(row)
    if expected_task_ids is None or len(expected_task_ids) != expected_tasks:
        raise ModalAiderError("independent result has no complete task set")
    matrices: dict[str, list[dict[str, Any]]] = {"try1": [], "try2": []}
    for task_id in sorted(expected_task_ids):
        cells = task_rows[task_id]
        if set(cells) != expected_indices:
            raise ModalAiderError(f"task {task_id} does not have exactly eight samples")
        for try_name in ("try1", "try2"):
            values = [
                cells[index][f"{try_name}_success"] for index in sorted(expected_indices)
            ]
            successes = sum(values)
            matrices[try_name].append(
                {
                    "task_id": task_id,
                    "samples": values,
                    "successes": successes,
                    f"task_pass_at_1_{try_name}": successes / INDEPENDENT_SAMPLES_PER_TASK,
                    f"task_pass_at_8_{try_name}": int(successes > 0),
                }
            )
    metrics: dict[str, float] = {}
    for try_name in ("try1", "try2"):
        rows = matrices[try_name]
        metrics[f"pass@1_{try_name}"] = sum(
            row[f"task_pass_at_1_{try_name}"] for row in rows
        ) / expected_tasks
        metrics[f"pass@8_{try_name}"] = sum(
            row[f"task_pass_at_8_{try_name}"] for row in rows
        ) / expected_tasks
    monotonic_pairs = (
        ("pass@1_try1", "pass@1_try2"),
        ("pass@8_try1", "pass@8_try2"),
        ("pass@1_try1", "pass@8_try1"),
        ("pass@1_try2", "pass@8_try2"),
    )
    for lower, upper in monotonic_pairs:
        if metrics[lower] > metrics[upper] + 1e-12:
            raise ModalAiderError(f"independent metric invariant violated: {lower} <= {upper}")
    summary = {
        "schema_version": 2,
        "result_family": INDEPENDENT_RESULT_LABEL,
        "estimator_version": PASS_AT_ESTIMATOR_VERSION,
        "task_count": expected_tasks,
        "samples_per_task": INDEPENDENT_SAMPLES_PER_TASK,
        "trajectory_count": expected_tasks * INDEPENDENT_SAMPLES_PER_TASK,
        "max_tries_per_trajectory": INDEPENDENT_TRIES,
        "maximum_edit_attempts": (
            expected_tasks * INDEPENDENT_SAMPLES_PER_TASK * INDEPENDENT_TRIES
        ),
        "base_seed": config.base_seed,
        "seed_schedule": [sample_seed(config, index) for index in range(1, 9)],
        "temperature": config.temperature,
        "top_p": config.top_p,
        **metrics,
        "config_fingerprint": fingerprint,
    }
    if persist:
        for try_name in ("try1", "try2"):
            write_json(output / f"success-matrix.{try_name}.json", {"rows": matrices[try_name]})
        write_json(output / "pass-at-1-and-8-by-try.json", summary)
        with (output / "samples.jsonl").open("w", encoding="utf-8") as handle:
            for row in sorted(samples, key=lambda item: (item["task_id"], item["sample_index"])):
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        for try_name in ("try1", "try2"):
            with (output / f"success-matrix.{try_name}.csv").open(
                "w", encoding="utf-8", newline=""
            ) as handle:
                writer = csv.writer(handle)
                writer.writerow(
                    ["task_id", *[f"sample_{index:02d}" for index in range(1, 9)], "c_i"]
                )
                for row in matrices[try_name]:
                    writer.writerow([row["task_id"], *row["samples"], row["successes"]])
        with (output / "pass-at-1-and-8-by-try.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.writer(handle)
            writer.writerow(["metric", "value"])
            for metric in ("pass@1_try1", "pass@1_try2", "pass@8_try1", "pass@8_try2"):
                writer.writerow([metric, metrics[metric]])
        (output / "report.md").write_text(
            "\n".join(
                [
                    "# Independent Aider pass@1/pass@8 by try depth",
                    "",
                    INDEPENDENT_RESULT_LABEL + ".",
                    "",
                    f"- Tasks: {expected_tasks}",
                    f"- Independent trajectories per task: {INDEPENDENT_SAMPLES_PER_TASK}",
                    f"- Maximum Aider tries per trajectory: {INDEPENDENT_TRIES}",
                    f"- pass@1_try1: {metrics['pass@1_try1']:.12g}",
                    f"- pass@1_try2: {metrics['pass@1_try2']:.12g}",
                    f"- pass@8_try1: {metrics['pass@8_try1']:.12g}",
                    f"- pass@8_try2: {metrics['pass@8_try2']:.12g}",
                    "",
                    "Aider is authoritative for each trajectory's try outcomes. These four "
                    "metrics are repository-derived across independent trajectories and are "
                    "not renamed Aider pass_rate_1/pass_rate_2 statistics.",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
    return {"summary": summary, "matrices": matrices, "samples": samples}


def assert_resume_compatible(
    config: ModalAiderConfig,
    prior_config_path: str | Path,
    *,
    allow_plan: bool = False,
) -> None:
    path = Path(prior_config_path)
    if not path.is_file():
        raise ModalAiderError("resume requires the prior config.redacted.json")
    prior = json.loads(path.read_text(encoding="utf-8"))
    current = config.redacted_mapping()
    excluded = {
        "phase",
        "acknowledge_paid_run",
        "acknowledge_pass_at_8",
        "resume",
        "local_root",
        "app_name",
        "remote_run_path",
    }
    mismatches = {
        key: {"prior": prior.get(key), "current": current.get(key)}
        for key in sorted(set(prior) | set(current))
        if key not in excluded and prior.get(key) != current.get(key)
    }
    if mismatches:
        raise ModalAiderError(f"resume identity/config mismatch: {sorted(mismatches)}")
    if not config.resume and not allow_plan:
        raise ModalAiderError("existing run artifacts require W8_MODAL_AIDER_RESUME=1")


def validate_remote_preflight(config: ModalAiderConfig, run_root: str | Path) -> None:
    """Reject a stale remote run before model loading or GPU admission."""

    root = Path(run_root)
    present = list(root.iterdir()) if root.is_dir() else []
    prior_config = root / "config.redacted.json"
    if not present:
        if config.resume:
            raise ModalAiderError("resume requested but the remote run has no prior artifacts")
        return
    if not config.resume:
        raise ModalAiderError("remote run id already has artifacts; use a fresh run id")
    if not prior_config.is_file():
        raise ModalAiderError("resume requested but the remote run has no prior config")
    assert_resume_compatible(config, prior_config)
    prior_receipt = root / "run_receipt.json"
    if prior_receipt.is_file():
        status = json.loads(prior_receipt.read_text(encoding="utf-8")).get("status")
        if status == "complete":
            raise ModalAiderError("a completed full run cannot be resumed")


def summarize_sglang_admission(
    completion: Mapping[str, Any], *, requested_max_tokens: int
) -> dict[str, Any]:
    """Return a response-shape diagnostic without model-generated text."""

    choices = completion.get("choices")
    choice = (
        choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    )
    message_value = choice.get("message")
    message = message_value if isinstance(message_value, dict) else {}
    content = message.get("content")
    reasoning = message.get("reasoning_content")
    usage_value = completion.get("usage")
    usage = (
        {
            str(key): value
            for key, value in usage_value.items()
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        if isinstance(usage_value, dict)
        else {}
    )
    return {
        "requested_max_tokens": requested_max_tokens,
        "choices_count": len(choices) if isinstance(choices, list) else 0,
        "choice_keys": sorted(choice),
        "message_keys": sorted(message),
        "finish_reason": choice.get("finish_reason"),
        "content_present": isinstance(content, str) and bool(content.strip()),
        "content_chars": len(content) if isinstance(content, str) else 0,
        "reasoning_content_field_present": "reasoning_content" in message,
        "reasoning_content_present": isinstance(reasoning, str) and bool(reasoning.strip()),
        "reasoning_content_chars": len(reasoning) if isinstance(reasoning, str) else 0,
        "usage": usage,
    }


def validate_sglang_admission(summary: Mapping[str, Any]) -> None:
    """Require separated reasoning metadata and nonempty editable content."""

    missing = []
    if not summary.get("reasoning_content_field_present"):
        missing.append("reasoning_content field")
    if not summary.get("content_present"):
        missing.append("editable content")
    if missing:
        finish = summary.get("finish_reason")
        used = (
            summary.get("usage", {}).get("completion_tokens")
            if isinstance(summary.get("usage"), dict)
            else None
        )
        raise ModalAiderError(
            "SGLang admission response is missing "
            + " and ".join(missing)
            + f" (finish_reason={finish!r}, completion_tokens={used!r})"
        )


def ensure_secret_free(value: Any, secrets: Sequence[str]) -> None:
    rendered = json.dumps(value, sort_keys=True) if not isinstance(value, str) else value
    leaks = [secret for secret in secrets if secret and secret in rendered]
    if leaks:
        raise ModalAiderError("secret value appeared in printable or persisted content")


def build_artifact_manifest(root: str | Path) -> dict[str, Any]:
    root = Path(root).resolve()
    files: list[dict[str, Any]] = []
    total_size = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if relative.as_posix() == "artifact_manifest.json":
            continue
        if relative.is_absolute() or ".." in relative.parts:
            raise ModalAiderError(f"unsafe artifact path: {path}")
        size = path.stat().st_size
        total_size += size
        files.append(
            {
                "path": relative.as_posix(),
                "size_bytes": size,
                "sha256": sha256_file(path) if size <= 64 * 1024 * 1024 else None,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "file_count": len(files),
        "aggregate_size_bytes": total_size,
        "files": files,
    }


def validate_local_artifacts(
    config: ModalAiderConfig, *, repo_root: str | Path = "."
) -> dict[str, Any]:
    root = config.local_run_path(repo_root)
    required = [
        "plan.json",
        "config.redacted.json",
        "upstreams.json",
        "model-cache.receipt.json",
        "server.receipt.json",
        "model-settings.yml",
        "model-settings.sha256",
        "run_receipt.json",
        "artifact_manifest.json",
    ]
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        raise ModalAiderError(f"local artifact copy is incomplete; missing {missing}")
    receipt = json.loads((root / "run_receipt.json").read_text(encoding="utf-8"))
    expected_status = "complete" if config.phase == "full" else "smoke_complete"
    if receipt.get("status") != expected_status:
        raise ModalAiderError(
            f"run receipt status {receipt.get('status')!r} is not {expected_status!r}"
        )
    if receipt.get("benchmark") != BENCHMARK_LABEL:
        raise ModalAiderError("run receipt has the wrong benchmark label")
    if receipt.get("modal_app_stopped") is not True or receipt.get("teardown_status") != "verified":
        raise ModalAiderError("local receipt does not prove that the Modal App stopped")
    if config.eval_mode == INDEPENDENT_EVAL_MODE:
        protocol = root / INDEPENDENT_EVAL_MODE
        report_root = protocol if config.phase == "full" else protocol / "smoke"
        summary_path = report_root / "pass-at-1-and-8-by-try.json"
        matrix_paths = {
            try_name: report_root / f"success-matrix.{try_name}.json"
            for try_name in ("try1", "try2")
        }
        if not summary_path.is_file() or not all(path.is_file() for path in matrix_paths.values()):
            raise ModalAiderError("local independent pass@8 report is incomplete")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        expected = config.expected_cpp_tasks if config.phase == "full" else config.smoke_tests
        if summary.get("task_count") != expected or summary.get("samples_per_task") != 8:
            raise ModalAiderError("local independent pass@8 report has wrong dimensions")
        if (
            receipt.get("eval_mode") != INDEPENDENT_EVAL_MODE
            or receipt.get("result_family") != INDEPENDENT_RESULT_LABEL
            or receipt.get("tries") != INDEPENDENT_TRIES
            or receipt.get("completed_tasks") != expected
            or receipt.get("completed_trajectories") != expected * INDEPENDENT_SAMPLES_PER_TASK
            or receipt.get("maximum_edit_attempts")
            != expected * INDEPENDENT_SAMPLES_PER_TASK * INDEPENDENT_TRIES
            or receipt.get("independent_pass_at_1_and_8") != summary
        ):
            raise ModalAiderError("local independent receipt does not match the by-try report")
        expected_metric_keys = {
            "pass@1_try1",
            "pass@1_try2",
            "pass@8_try1",
            "pass@8_try2",
        }
        if set(key for key in summary if key.startswith("pass@")) != expected_metric_keys:
            raise ModalAiderError("independent report must contain exactly four by-try metrics")
        expected_indices = range(1, INDEPENDENT_SAMPLES_PER_TASK + 1)
        sample_result_dirs: dict[int, Path] = {}
        for sample_index in expected_indices:
            sample_root = report_root / f"sample-{sample_index:02d}"
            for name in (
                "command.json",
                "model-settings.yml",
                "model-settings.sha256",
                "request-metadata.json",
                "fresh-tree.receipt.json",
                "stats.json",
            ):
                if not (sample_root / name).is_file():
                    raise ModalAiderError(
                        f"local independent sample {sample_index:02d} is missing {name}"
                    )
            command = json.loads((sample_root / "command.json").read_text(encoding="utf-8"))
            metadata = json.loads(
                (sample_root / "request-metadata.json").read_text(encoding="utf-8")
            )
            expected_seed = sample_seed(config, sample_index)
            if (
                command.get("sample_index") != sample_index
                or command.get("seed") != expected_seed
                or command.get("tries") != INDEPENDENT_TRIES
                or metadata.get("seed") != expected_seed
            ):
                raise ModalAiderError(
                    f"local independent sample {sample_index:02d} has mismatched seed/config"
                )
            suffix = (
                f"--{config.run_id}-smoke-sample-{sample_index:02d}"
                if config.phase != "full"
                else f"--{config.run_id}-sample-{sample_index:02d}"
            )
            official_dirs = [
                path for path in sample_root.iterdir() if path.is_dir() and path.name.endswith(suffix)
            ]
            if len(official_dirs) != 1:
                raise ModalAiderError(
                    f"local independent sample {sample_index:02d} has no unique official result"
                )
            sample_result_dirs[sample_index] = official_dirs[0]
            validate_independent_aider_results(official_dirs[0], expected_tasks=expected)
            stats = json.loads((sample_root / "stats.json").read_text(encoding="utf-8"))
            validate_independent_authoritative_stats(
                stats, result_dir=official_dirs[0], expected_tasks=expected
            )
        recomputed = build_independent_pass_report(
            config,
            sample_result_dirs=sample_result_dirs,
            out=report_root,
            expected_tasks=expected,
            persist=False,
        )
        stored_matrices = {
            try_name: json.loads(path.read_text(encoding="utf-8"))
            for try_name, path in matrix_paths.items()
        }
        if recomputed["summary"] != summary or any(
            {"rows": recomputed["matrices"][try_name]} != stored_matrices[try_name]
            for try_name in ("try1", "try2")
        ):
            raise ModalAiderError("stored pass@1/pass@8 report does not match official rows")
        for try_name in ("try1", "try2"):
            csv_path = report_root / f"success-matrix.{try_name}.csv"
            if not csv_path.is_file():
                raise ModalAiderError(f"independent report is missing {csv_path.name}")
            with csv_path.open(encoding="utf-8", newline="") as handle:
                csv_rows = list(csv.reader(handle))
            expected_header = [
                "task_id",
                *[f"sample_{index:02d}" for index in range(1, 9)],
                "c_i",
            ]
            expected_rows = [
                [
                    row["task_id"],
                    *[str(value) for value in row["samples"]],
                    str(row["successes"]),
                ]
                for row in recomputed["matrices"][try_name]
            ]
            if csv_rows != [expected_header, *expected_rows]:
                raise ModalAiderError(f"{csv_path.name} does not match official rows")
        metrics_csv = report_root / "pass-at-1-and-8-by-try.csv"
        if not metrics_csv.is_file():
            raise ModalAiderError("independent report is missing its metric CSV")
        with metrics_csv.open(encoding="utf-8", newline="") as handle:
            metric_rows = list(csv.reader(handle))
        expected_metrics = [
            [metric, str(summary[metric])]
            for metric in ("pass@1_try1", "pass@1_try2", "pass@8_try1", "pass@8_try2")
        ]
        if metric_rows != [["metric", "value"], *expected_metrics]:
            raise ModalAiderError("metric CSV does not match the independent summary")
        report_path = report_root / "report.md"
        if not report_path.is_file():
            raise ModalAiderError("independent report is missing report.md")
        report_text = report_path.read_text(encoding="utf-8")
        for metric in ("pass@1_try1", "pass@1_try2", "pass@8_try1", "pass@8_try2"):
            if f"- {metric}: {summary[metric]:.12g}" not in report_text:
                raise ModalAiderError(f"report.md does not match {metric}")
        stored_samples = [
            json.loads(line)
            for line in (report_root / "samples.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        expected_samples = sorted(
            recomputed["samples"], key=lambda item: (item["task_id"], item["sample_index"])
        )
        if stored_samples != expected_samples:
            raise ModalAiderError("stored independent sample rows do not match official rows")
        manifest = build_artifact_manifest(root)
        stored_manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
        if stored_manifest != manifest:
            raise ModalAiderError("local artifact tree does not match artifact_manifest.json")
        return {"receipt": receipt, "stats": summary, "admission": summary, "manifest": manifest}
    stage = "full" if config.phase == "full" else "smoke"
    stats_path = root / stage / "stats.json"
    if not stats_path.is_file():
        raise ModalAiderError(f"local artifact copy has no {stage}/stats.json")
    stats = json.loads(stats_path.read_text(encoding="utf-8"))
    expected = config.expected_cpp_tasks if stage == "full" else config.smoke_tests
    validate_authoritative_stats(stats, expected_tasks=expected)
    official_dirs = [
        path
        for path in (root / stage).iterdir()
        if path.is_dir() and path.name.endswith(f"--{config.run_id}-{stage}")
    ]
    if len(official_dirs) != 1:
        raise ModalAiderError(f"expected one official Aider {stage} result directory")
    admission = validate_aider_results(official_dirs[0], expected_tasks=expected)
    manifest = build_artifact_manifest(root)
    stored_manifest = json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))
    if stored_manifest != manifest:
        raise ModalAiderError("local artifact tree does not match artifact_manifest.json")
    return {
        "receipt": receipt,
        "stats": stats,
        "admission": admission.as_mapping(),
        "manifest": manifest,
    }


def modal_app_is_stopped(app_list: Any, app_name: str) -> bool:
    """Return true when no matching App record is in a live state."""

    rows = app_list if isinstance(app_list, list) else app_list.get("apps", [])
    if not isinstance(rows, list):
        raise ModalAiderError("modal app list --json did not return an app list")
    live_states = {"running", "deployed", "initializing", "ephemeral", "active"}
    for row in rows:
        if not isinstance(row, dict):
            continue
        lowered = {str(key).lower(): value for key, value in row.items()}
        name = str(
            lowered.get("name") or lowered.get("app_name") or lowered.get("description") or ""
        )
        if name != app_name:
            continue
        state = str(lowered.get("state") or lowered.get("status") or "").lower()
        if state in live_states or not state:
            return False
    return True


def mark_local_teardown_verified(
    config: ModalAiderConfig,
    *,
    app_list_json: str | Path,
    repo_root: str | Path = ".",
) -> Path | None:
    app_list = json.loads(Path(app_list_json).read_text(encoding="utf-8"))
    if not modal_app_is_stopped(app_list, config.app_name):
        raise ModalAiderError(
            "Modal App still appears active; run: " + " ".join(modal_stop_command(config))
        )
    root = config.local_run_path(repo_root)
    receipt_path = root / "run_receipt.json"
    if not receipt_path.is_file():
        return None
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["modal_app_stopped"] = True
    receipt["teardown_status"] = "verified"
    receipt["teardown_verified_at_utc"] = utc_now()
    write_json(receipt_path, receipt)
    write_json(root / "artifact_manifest.json", build_artifact_manifest(root))
    return receipt_path


def _print_summary(validated: Mapping[str, Any], *, artifact_path: Path) -> None:
    receipt = validated["receipt"]
    stats = validated["stats"]
    print(f"status: {receipt['status']}")
    print(f"benchmark: {BENCHMARK_LABEL}")
    print(f"model: {receipt['model_repo']}@{receipt['model_revision']}")
    if receipt.get("eval_mode") == INDEPENDENT_EVAL_MODE:
        print(f"result_family: {INDEPENDENT_RESULT_LABEL}")
        print(f"tasks: {stats['task_count']}/{receipt['expected_tasks']}")
        print(f"samples_per_task: {stats['samples_per_task']}")
        print(f"pass@1_try1: {stats['pass@1_try1']}")
        print(f"pass@1_try2: {stats['pass@1_try2']}")
        print(f"pass@8_try1: {stats['pass@8_try1']}")
        print(f"pass@8_try2: {stats['pass@8_try2']}")
        print(f"modal_app_stopped: {str(bool(receipt.get('modal_app_stopped'))).lower()}")
        print(f"artifacts: {artifact_path}")
        return
    print(f"tasks: {stats['test_cases']}/{receipt['expected_tasks']}")
    print(f"pass_rate_1: {stats['pass_rate_1']}")
    if "pass_rate_2" in stats:
        print(f"pass_rate_2: {stats['pass_rate_2']}")
    print(f"modal_app_stopped: {str(bool(receipt.get('modal_app_stopped'))).lower()}")
    print(f"artifacts: {artifact_path}")


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "validate-artifacts", "summary"):
        command = sub.add_parser(name)
        command.add_argument("--repo-root", default=".")
    stopped = sub.add_parser("mark-stopped")
    stopped.add_argument("--repo-root", default=".")
    stopped.add_argument("--app-list-json", required=True)
    args = parser.parse_args(argv)
    try:
        config = ModalAiderConfig.from_env(repo_root=args.repo_root)
        if args.command == "plan":
            root = prepare_local_plan(config, repo_root=args.repo_root)
            plan = render_plan(config)
            ensure_secret_free(
                plan,
                [config.modal_token_id, config.modal_token_secret, config.hf_token],
            )
            print(json.dumps(plan, indent=2, sort_keys=True))
            print(f"plan: {root / 'plan.json'}")
            return 0
        if args.command == "mark-stopped":
            path = mark_local_teardown_verified(
                config,
                app_list_json=args.app_list_json,
                repo_root=args.repo_root,
            )
            if path is None:
                print("teardown: verified stopped (no run receipt was created)")
            else:
                print(f"teardown receipt: {path}")
            return 0
        validated = validate_local_artifacts(config, repo_root=args.repo_root)
        if args.command == "validate-artifacts":
            print(json.dumps(validated, indent=2, sort_keys=True))
        else:
            _print_summary(validated, artifact_path=config.local_run_path(args.repo_root))
        return 0
    except (ModalAiderError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(_main())
