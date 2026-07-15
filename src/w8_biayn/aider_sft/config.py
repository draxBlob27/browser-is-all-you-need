"""Strict TOML configuration and fully resolved run locks."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib

from pydantic import Field, ValidationError, model_validator

from w8_biayn.constants import (
    AIDER_PIN,
    AIDER_POLYGLOT_PIN,
    AIDER_POLYGLOT_REPO,
    AIDER_REPO,
    EXERCISM_CPP_PIN,
    EXERCISM_CPP_REPO,
    SLIME_PIN,
)

from .benchmark import benchmark_manifest_sha256
from .errors import AiderSftError
from .schema import ReviewScope, StrictModel
from .util import canonical_json_bytes, read_json, sha256_bytes, sha256_file


PIPELINE_CONTRACT_VERSION = "aider-sft-pipeline-v1.3"
DATASET_PROFILE = "aider-sft-pilot-v1"
SOURCE_ONLY_DATASET_PROFILE = "aider-sft-source-only-75-v1"
TASK_SCHEMA_VERSION = "aider-sft-task-v1"
ROW_SCHEMA_VERSION = "aider-sft-row-v1"
TOKEN_SCHEMA_VERSION = "aider-sft-token-record-v1"
RENDERER_VERSION = "aider-whole-compact-v1"
MASK_ADAPTER = "w8-aider-sft-mask-v1"
TAXONOMY_VERSION = "aider-cpp-six-groups-v1"
GENERATED_SCAFFOLD = "aider-sft-cmake-catch-v1"
GLM_REPOSITORY = "zai-org/GLM-4.7-Flash"
GLM_REVISION = "7dd20894a642a0aa287e9827cb1a1f7f91386b67"

DatasetProfileName = Literal[
    "aider-sft-pilot-v1",
    "aider-sft-source-only-75-v1",
]


@dataclass(frozen=True)
class DatasetProfileContract:
    """Non-overridable semantic constraints selected by dataset profile ID."""

    profile: str
    source_manifest_relative: str
    source_split_policy: Literal["frozen_manifest", "all_train"]
    total_targets: dict[str, int]
    category_split_targets: dict[str, int] | None
    llm_enabled: bool
    minimum_llm_assisted: int
    required_review_scopes: tuple[ReviewScope, ...]
    subject_prefix: str

    @property
    def total_roots(self) -> int:
        return sum(self.total_targets.values())


PROFILE_CONTRACTS: dict[str, DatasetProfileContract] = {
    DATASET_PROFILE: DatasetProfileContract(
        profile=DATASET_PROFILE,
        source_manifest_relative="manifests/aider_sft/pilot-v1-source.json",
        source_split_policy="frozen_manifest",
        total_targets={"train": 72, "validation": 12, "test": 12},
        category_split_targets={"train": 12, "validation": 2, "test": 2},
        llm_enabled=True,
        minimum_llm_assisted=21,
        required_review_scopes=tuple(ReviewScope),
        subject_prefix="pilot-v1",
    ),
    SOURCE_ONLY_DATASET_PROFILE: DatasetProfileContract(
        profile=SOURCE_ONLY_DATASET_PROFILE,
        source_manifest_relative="manifests/aider_sft/source-only-75-v1-source.json",
        source_split_policy="all_train",
        total_targets={"train": 75, "validation": 0, "test": 0},
        category_split_targets=None,
        llm_enabled=False,
        minimum_llm_assisted=0,
        required_review_scopes=(
            ReviewScope.SOURCE_INVENTORY,
            ReviewScope.CONTAMINATION_FLAG,
            ReviewScope.FINAL_SPLIT,
            ReviewScope.DATASET_RELEASE,
        ),
        subject_prefix="source-only-75-v1",
    ),
}


def profile_contract(profile: str) -> DatasetProfileContract:
    try:
        return PROFILE_CONTRACTS[profile]
    except KeyError as exc:
        raise AiderSftError(
            "profile_not_frozen", f"unsupported dataset profile: {profile}"
        ) from exc


def profile_contract_from_lock(config_lock: dict[str, Any]) -> DatasetProfileContract:
    return profile_contract(str(config_lock["config"]["dataset"]["profile"]))


def profile_subject_id(profile: str, suffix: str) -> str:
    return f"{profile_contract(profile).subject_prefix}-{suffix}"


def source_manifest_path(repo_root: Path, profile: str) -> Path:
    return repo_root / profile_contract(profile).source_manifest_relative


class DatasetConfig(StrictModel):
    profile: DatasetProfileName
    dataset_id_prefix: str
    split_seed: int
    distribution_scope: Literal["internal_research"]
    freeze_status: Literal["draft", "frozen"]


class UpstreamIdentity(StrictModel):
    repository: str
    revision: str


class UpstreamsConfig(StrictModel):
    exercism_cpp: UpstreamIdentity
    aider: UpstreamIdentity
    aider_polyglot: UpstreamIdentity
    slime_revision: str


class ToolchainConfig(StrictModel):
    docker_image: str
    docker_image_id: str
    cxx_path: str
    cxx_version: str
    cxx_binary_sha256: str
    cmake_generator: Literal["Unix Makefiles"]
    language_standard: Literal["c++17"]
    grader_protocol: Literal[2]


class SandboxConfig(StrictModel):
    network: Literal["none"]
    read_only_rootfs: Literal[True]
    run_as_non_root: Literal[True]
    no_new_privileges: Literal[True]
    cap_drop: list[Literal["ALL"]]
    mount_policy: Literal["single-rw-scratch-no-host-secrets-v1"]
    seccomp_profile_sha256: str
    cpus: int = Field(ge=1)
    memory_mib: int = Field(ge=256)
    pids: int = Field(ge=32)
    file_size_mib: int = Field(ge=1)


class TokenizerConfig(StrictModel):
    repository: Literal["zai-org/GLM-4.7-Flash"]
    revision: Literal["7dd20894a642a0aa287e9827cb1a1f7f91386b67"]
    chat_template_sha256: str
    load_kwargs: dict[str, bool]
    apply_chat_template_kwargs: dict[str, bool]
    policy: Literal["final_answer_only_thinking_disabled"]
    sequence_length: Literal[4096]
    loss_mask_type: Literal["qwen"]
    mask_adapter: Literal["w8-aider-sft-mask-v1"]
    local_path: str = ""


class LimitsConfig(StrictModel):
    editable_files: Literal[8]
    context_files: Literal[16]
    task_local_files: Literal[128]
    visible_file_bytes: Literal[262144]
    grader_file_bytes: Literal[262144]
    visible_total_bytes: Literal[524288]
    task_total_bytes: Literal[4194304]
    shared_file_bytes: Literal[1048576]
    shared_total_bytes: Literal[4194304]
    command_tail_bytes: Literal[65536]


class BudgetConfig(StrictModel):
    total_candidates: int = Field(ge=0)
    reserve_multiplier: float = Field(ge=3.0)
    calls_per_candidate: int = Field(ge=4)
    max_revisions: int = Field(ge=0, le=3)
    concurrency: int = Field(ge=1, le=4)
    transport_retries: int = Field(ge=0, le=3)
    total_calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    wall_time_seconds: int = Field(ge=0)
    spend_amount: float = Field(ge=0)
    spend_currency: str


class LlmConfig(StrictModel):
    provider: str
    model: str
    model_revision: str
    endpoint: str
    credential_env: str
    decoding: dict[str, int | float | bool | str]
    usage_terms_snapshot_sha256: str
    usage_terms_date: str
    input_cost_per_million: float = Field(ge=0)
    output_cost_per_million: float = Field(ge=0)
    budgets: BudgetConfig


class ReviewConfig(StrictModel):
    authorized_reviewers: dict[ReviewScope, list[str]]
    authoring_identities: list[str]


class ContaminationConfig(StrictModel):
    normalizer_version: str
    token_shingle_size: int = Field(ge=1)
    jaccard_review_threshold: float = Field(ge=0.0, le=1.0)
    instruction_review_threshold: float = Field(ge=0.0, le=1.0)


class AiderSftConfig(StrictModel):
    contract_version: Literal["aider-sft-pipeline-v1.3"]
    dataset: DatasetConfig
    upstreams: UpstreamsConfig
    toolchain: ToolchainConfig
    sandbox: SandboxConfig
    tokenizer: TokenizerConfig
    renderer_version: Literal["aider-whole-compact-v1"]
    taxonomy_version: Literal["aider-cpp-six-groups-v1"]
    generated_scaffold: Literal["aider-sft-cmake-catch-v1"]
    limits: LimitsConfig
    llm: LlmConfig | None = None
    review: ReviewConfig
    contamination: ContaminationConfig

    @model_validator(mode="after")
    def profile_components_match(self) -> "AiderSftConfig":
        contract = profile_contract(self.dataset.profile)
        if contract.llm_enabled and self.llm is None:
            raise ValueError(f"{contract.profile} requires an [llm] configuration")
        if not contract.llm_enabled and self.llm is not None:
            raise ValueError(f"{contract.profile} forbids an [llm] configuration")
        return self


def load_config(path: Path) -> AiderSftConfig:
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
        return AiderSftConfig.model_validate(raw)
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as exc:
        raise AiderSftError("profile_not_frozen", f"invalid config {path}: {exc}") from exc


def _exact_identity_missing(config: AiderSftConfig) -> list[str]:
    contract = profile_contract(config.dataset.profile)
    expected = {
        "upstreams.exercism_cpp.repository": (
            config.upstreams.exercism_cpp.repository,
            EXERCISM_CPP_REPO,
        ),
        "upstreams.exercism_cpp.revision": (
            config.upstreams.exercism_cpp.revision,
            EXERCISM_CPP_PIN,
        ),
        "upstreams.aider.repository": (config.upstreams.aider.repository, AIDER_REPO),
        "upstreams.aider.revision": (config.upstreams.aider.revision, AIDER_PIN),
        "upstreams.aider_polyglot.repository": (
            config.upstreams.aider_polyglot.repository,
            AIDER_POLYGLOT_REPO,
        ),
        "upstreams.aider_polyglot.revision": (
            config.upstreams.aider_polyglot.revision,
            AIDER_POLYGLOT_PIN,
        ),
        "upstreams.slime_revision": (config.upstreams.slime_revision, SLIME_PIN),
    }
    missing = [name for name, (actual, wanted) in expected.items() if actual != wanted]
    required_nonempty = {
        "toolchain.docker_image": config.toolchain.docker_image,
        "toolchain.docker_image_id": config.toolchain.docker_image_id,
        "toolchain.cxx_path": config.toolchain.cxx_path,
        "toolchain.cxx_version": config.toolchain.cxx_version,
        "toolchain.cxx_binary_sha256": config.toolchain.cxx_binary_sha256,
        "sandbox.seccomp_profile_sha256": config.sandbox.seccomp_profile_sha256,
        "tokenizer.local_path": config.tokenizer.local_path,
        "tokenizer.chat_template_sha256": config.tokenizer.chat_template_sha256,
    }
    if config.llm is not None:
        required_nonempty.update(
            {
                "llm.provider": config.llm.provider,
                "llm.model": config.llm.model,
                "llm.model_revision": config.llm.model_revision,
                "llm.endpoint": config.llm.endpoint,
                "llm.credential_env": config.llm.credential_env,
                "llm.usage_terms_snapshot_sha256": config.llm.usage_terms_snapshot_sha256,
                "llm.usage_terms_date": config.llm.usage_terms_date,
                "llm.budgets.spend_currency": config.llm.budgets.spend_currency,
            }
        )
    missing.extend(name for name, value in required_nonempty.items() if not value)
    if config.dataset.freeze_status != "frozen":
        missing.append("dataset.freeze_status")
    if config.tokenizer.apply_chat_template_kwargs != {"enable_thinking": False}:
        missing.append("tokenizer.apply_chat_template_kwargs")
    if config.tokenizer.load_kwargs != {"fix_mistral_regex": True}:
        missing.append("tokenizer.load_kwargs")
    for scope in contract.required_review_scopes:
        if not config.review.authorized_reviewers.get(scope):
            missing.append(f"review.authorized_reviewers.{scope.value}")
    if config.llm is not None:
        budgets = config.llm.budgets
        for name, value in {
            "llm.budgets.total_calls": budgets.total_calls,
            "llm.budgets.input_tokens": budgets.input_tokens,
            "llm.budgets.output_tokens": budgets.output_tokens,
            "llm.budgets.wall_time_seconds": budgets.wall_time_seconds,
            "llm.budgets.spend_amount": budgets.spend_amount,
        }.items():
            if value <= 0:
                missing.append(name)
    return sorted(set(missing))


def inspect_container_compiler(
    *,
    image: str,
    cxx_path: str,
    docker_available: bool,
) -> dict[str, Any]:
    """Read the compiler identity from the image that executes every oracle."""

    observed: dict[str, Any] = {
        "path": cxx_path,
        "exists": False,
        "sha256": "",
        "version": "",
        "source": "docker_image",
        "error": "",
    }
    if not docker_available or not image or not cxx_path:
        return observed
    sandbox = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--user",
        "65534:65534",
        "--cpus",
        "1",
        "--memory",
        "256m",
        "--pids-limit",
        "64",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
    ]
    version = subprocess.run(
        [*sandbox, "--entrypoint", cxx_path, image, "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    digest = subprocess.run(
        [*sandbox, "--entrypoint", "sha256sum", image, cxx_path],
        check=False,
        capture_output=True,
        text=True,
    )
    digest_value = digest.stdout.strip().split(maxsplit=1)[0] if digest.stdout.strip() else ""
    digest_valid = len(digest_value) == 64 and all(
        character in "0123456789abcdef" for character in digest_value.lower()
    )
    if version.returncode == 0 and digest.returncode == 0 and digest_valid:
        observed.update(
            {
                "exists": True,
                "sha256": digest_value.lower(),
                "version": version.stdout.strip(),
            }
        )
    else:
        diagnostic = version.stderr.strip() or digest.stderr.strip()
        observed["error"] = diagnostic[-1000:]
    return observed


def inspect_local_identity(config: AiderSftConfig, repo_root: Path) -> dict[str, Any]:
    from w8_biayn.constants import UPSTREAMS
    from w8_biayn.upstreams import upstream_path

    upstream_rows: dict[str, dict[str, Any]] = {}
    for config_key, registry_key, expected_revision in (
        ("exercism_cpp", "exercism-cpp", config.upstreams.exercism_cpp.revision),
        ("aider", "aider", config.upstreams.aider.revision),
        ("aider_polyglot", "aider-polyglot", config.upstreams.aider_polyglot.revision),
        ("slime", "slime", config.upstreams.slime_revision),
    ):
        path = upstream_path(UPSTREAMS[registry_key], repo_root)
        row: dict[str, Any] = {
            "path": str(path),
            "expected_revision": expected_revision,
        }
        if path.exists():
            head = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "HEAD"],
                check=False,
                capture_output=True,
                text=True,
            )
            dirty = subprocess.run(
                ["git", "-C", str(path), "status", "--porcelain", "--untracked-files=all"],
                check=False,
                capture_output=True,
                text=True,
            )
            row.update(
                {
                    "head": head.stdout.strip(),
                    "clean": dirty.returncode == 0 and not dirty.stdout.strip(),
                    "present": head.returncode == 0,
                }
            )
        else:
            row.update({"head": "", "clean": False, "present": False})
        upstream_rows[config_key] = row

    docker_available = shutil.which("docker") is not None
    docker_image_id = ""
    if docker_available and config.toolchain.docker_image:
        inspected = subprocess.run(
            [
                "docker",
                "image",
                "inspect",
                "--format={{.Id}}",
                config.toolchain.docker_image,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if inspected.returncode == 0:
            docker_image_id = inspected.stdout.strip()
    compiler_observed = inspect_container_compiler(
        image=config.toolchain.docker_image,
        cxx_path=config.toolchain.cxx_path,
        docker_available=docker_available,
    )

    seccomp_value = os.environ.get("W8_AIDER_SFT_SECCOMP_PROFILE", "")
    seccomp_path = Path(seccomp_value) if seccomp_value else None
    seccomp = {
        "path": seccomp_value,
        "exists": bool(seccomp_path and seccomp_path.is_file()),
        "sha256": sha256_file(seccomp_path)
        if seccomp_path is not None and seccomp_path.is_file()
        else "",
    }

    tokenizer_path = Path(config.tokenizer.local_path) if config.tokenizer.local_path else None
    tokenizer: dict[str, Any] = {
        "path": config.tokenizer.local_path,
        "exists": bool(tokenizer_path and tokenizer_path.is_dir()),
        "marker_matches": False,
        "chat_template_sha256": "",
        "error": "",
    }
    if tokenizer_path is not None and tokenizer_path.is_dir():
        marker_path = tokenizer_path / ".w8-aider-sft-model.json"
        try:
            tokenizer["marker_matches"] = read_json(marker_path) == {
                "repository": config.tokenizer.repository,
                "revision": config.tokenizer.revision,
                "schema_version": "w8-aider-sft-model-snapshot-v1",
            }
            from transformers import AutoTokenizer

            loaded = AutoTokenizer.from_pretrained(
                str(tokenizer_path),
                local_files_only=True,
                trust_remote_code=True,
                **config.tokenizer.load_kwargs,
            )
            template = getattr(loaded, "chat_template", None)
            if isinstance(template, str):
                tokenizer["chat_template_sha256"] = sha256_bytes(template.encode("utf-8"))
            else:
                tokenizer["error"] = "tokenizer lacks a string chat_template"
        except Exception as exc:  # noqa: BLE001 - report every local identity failure
            tokenizer["error"] = f"{type(exc).__name__}: {exc}"
    return {
        "upstreams": upstream_rows,
        "compiler": compiler_observed,
        "docker_available": docker_available,
        "docker_image_id": docker_image_id,
        "seccomp": seccomp,
        "tokenizer": tokenizer,
    }


def freeze_report(
    config: AiderSftConfig,
    *,
    repo_root: Path,
    source_manifest_path: Path,
) -> dict[str, Any]:
    missing = _exact_identity_missing(config)
    local = inspect_local_identity(config, repo_root)
    for key, value in local["upstreams"].items():
        if not value["present"]:
            missing.append(f"local_upstream.{key}")
        elif value["head"] != value["expected_revision"]:
            missing.append(f"local_upstream.{key}.revision")
        elif not value["clean"]:
            missing.append(f"local_upstream.{key}.clean_tree")
    if not source_manifest_path.is_file():
        missing.append("source_manifest")
    compiler = local["compiler"]
    if not compiler["exists"]:
        missing.append("toolchain.cxx_path.image")
    else:
        if compiler["sha256"] != config.toolchain.cxx_binary_sha256:
            missing.append("toolchain.cxx_binary_sha256.image")
        if compiler["version"] != config.toolchain.cxx_version:
            missing.append("toolchain.cxx_version.image")
    if not (repo_root / "manifests/aider_sft/aider-polyglot-cpp-26.json").is_file():
        missing.append("benchmark_manifest")
    if not local["docker_available"]:
        missing.append("docker")
    elif local["docker_image_id"] != config.toolchain.docker_image_id:
        missing.append("toolchain.docker_image_id.local")
    if not local["seccomp"]["exists"]:
        missing.append("sandbox.seccomp_profile.local")
    elif local["seccomp"]["sha256"] != config.sandbox.seccomp_profile_sha256:
        missing.append("sandbox.seccomp_profile_sha256.local")
    tokenizer = local["tokenizer"]
    if not tokenizer["exists"]:
        missing.append("tokenizer.local_path.local")
    else:
        if not tokenizer["marker_matches"]:
            missing.append("tokenizer.model_revision.local")
        if tokenizer["chat_template_sha256"] != config.tokenizer.chat_template_sha256:
            missing.append("tokenizer.chat_template_sha256.local")
    return {
        "status": "frozen" if not missing else "profile_not_frozen",
        "reason_code": None if not missing else "profile_not_frozen",
        "missing_or_mismatched": sorted(set(missing)),
        "local_identity": local,
    }


def build_config_lock(
    config: AiderSftConfig,
    *,
    repo_root: Path,
    source_manifest_path: Path,
) -> dict[str, Any]:
    report = freeze_report(config, repo_root=repo_root, source_manifest_path=source_manifest_path)
    if report["status"] != "frozen":
        raise AiderSftError(
            "profile_not_frozen",
            "profile inputs are incomplete: " + ", ".join(report["missing_or_mismatched"]),
        )
    source_manifest = read_json(source_manifest_path)
    source_hash = sha256_bytes(canonical_json_bytes(source_manifest))
    lock = {
        "schema_version": "aider-sft-config-lock-v1",
        "contract_version": PIPELINE_CONTRACT_VERSION,
        "task_schema_version": TASK_SCHEMA_VERSION,
        "row_schema_version": ROW_SCHEMA_VERSION,
        "token_schema_version": TOKEN_SCHEMA_VERSION,
        "config": config.model_dump(mode="json"),
        "resolved": {
            "source_manifest_path": source_manifest_path.relative_to(repo_root).as_posix(),
            "source_manifest_sha256": source_hash,
            "benchmark_denylist_sha256": benchmark_manifest_sha256(repo_root),
            "chat_template_kwargs_sha256": sha256_bytes(
                canonical_json_bytes(config.tokenizer.apply_chat_template_kwargs)
            ),
            "tokenizer_render_policy_sha256": sha256_bytes(
                canonical_json_bytes(
                    {
                        "adapter": MASK_ADAPTER,
                        "kwargs": config.tokenizer.apply_chat_template_kwargs,
                        "loss_mask_type": config.tokenizer.loss_mask_type,
                        "policy": config.tokenizer.policy,
                        "repository": config.tokenizer.repository,
                        "revision": config.tokenizer.revision,
                        "sequence_length": config.tokenizer.sequence_length,
                        "template_sha256": config.tokenizer.chat_template_sha256,
                    }
                )
            ),
        },
    }
    from .scaffold import scaffold_identity

    lock["resolved"]["generated_scaffold"] = scaffold_identity()
    content_id = sha256_bytes(canonical_json_bytes(lock))
    lock["dataset_id"] = f"{config.dataset.dataset_id_prefix}-{content_id[:12]}"
    lock["lock_sha256"] = sha256_bytes(canonical_json_bytes(lock))
    return lock
