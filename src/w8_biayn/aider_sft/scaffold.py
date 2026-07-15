"""Repo-owned C++17 CMake/Catch scaffold for LLM-assisted roots."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, ValidationError, field_validator, model_validator

from .config import GENERATED_SCAFFOLD
from .errors import AiderSftError
from .grader_support import BUNDLE_ID
from .schema import (
    CanonicalTask,
    Difficulty,
    PrimaryCategory,
    Split,
    StrictModel,
)
from .util import (
    atomic_write,
    fingerprint,
    hash_file_records,
    normalize_relative_path,
    normalize_text_bytes,
    sha256_bytes,
    validate_fence_safe,
    write_json,
)

_ASSET = Path(__file__).parent / "assets/aider-sft-cmake-catch-v1/CMakeLists.txt.in"
_SAFE_GENERATED_PATH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
_FORBIDDEN_BUILD_NAMES = {
    "cmakelists.txt",
    "dockerfile",
    "makefile",
    "meson.build",
    "build.gradle",
}
_FORBIDDEN_CONTENT = (
    "std::system(",
    "popen(",
    "#include <curl",
    "curl ",
    "wget ",
)


class GeneratedFile(StrictModel):
    path: str
    content: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        value = normalize_relative_path(value)
        if not _SAFE_GENERATED_PATH.fullmatch(value):
            raise ValueError("generated paths use the portable V1 character set")
        if Path(value).name.lower() in _FORBIDDEN_BUILD_NAMES or Path(value).suffix == ".sh":
            raise ValueError("generated build/command files are forbidden")
        return value

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        payload = normalize_text_bytes(value.encode("utf-8"), label="generated file")
        validate_fence_safe(payload, label="generated file")
        if any(token in value for token in _FORBIDDEN_CONTENT):
            raise ValueError("generated content requires a forbidden command/dependency")
        return payload.decode("utf-8")


class Blueprint(StrictModel):
    schema_version: Literal["aider-sft-blueprint-v1"]
    title: str
    proposed_slug: str
    task_family_id: str
    primary_category: PrimaryCategory
    tags: list[str] = Field(min_length=1)
    difficulty: Difficulty
    learning_objectives: list[str] = Field(min_length=1)
    behavioral_contract: list[str] = Field(min_length=1)
    public_api: list[str] = Field(min_length=1)
    editable_files: list[str] = Field(min_length=1)
    constraints: list[str]
    edge_cases: list[str] = Field(min_length=1)
    test_plan: list[str] = Field(min_length=1)
    non_goals: list[str]

    @field_validator("proposed_slug", "task_family_id")
    @classmethod
    def slug(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
            raise ValueError("must be a normalized lowercase slug")
        return value

    @field_validator("editable_files")
    @classmethod
    def paths(cls, value: list[str]) -> list[str]:
        normalized = [GeneratedFile(path=path, content="placeholder\n").path for path in value]
        if normalized != sorted(set(normalized)):
            raise ValueError("editable files must be unique and sorted")
        return normalized

    @field_validator("tags")
    @classmethod
    def tags_sorted(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("tags must be unique and sorted")
        return value


class TaskAuthorOutput(StrictModel):
    schema_version: Literal["aider-sft-task-author-v1"]
    introduction: str
    instructions: str
    instructions_append: str | None = None
    starter_files: list[GeneratedFile]
    reference_files: list[GeneratedFile]
    context_files: list[GeneratedFile] = Field(default_factory=list)


class TestAuthorOutput(StrictModel):
    schema_version: Literal["aider-sft-test-author-v1"]
    tests: list[GeneratedFile] = Field(min_length=1)


class NegativeSolution(StrictModel):
    negative_id: str
    files: list[GeneratedFile]


class GenerationProvenance(StrictModel):
    provider: str
    model: str
    model_revision: str
    generation_run_id: str
    prompt_template_sha256: dict[str, str]
    request_sha256: dict[str, str]
    response_sha256: dict[str, str]
    decoding: dict[str, Any]
    token_usage: dict[str, int]
    attempt_count: int = Field(ge=1)
    revision_count: int = Field(ge=0, le=3)
    timestamps_utc: dict[str, str]


class GeneratedCandidate(StrictModel):
    schema_version: Literal["aider-sft-generated-candidate-v1"]
    candidate_id: str
    intended_split: Split
    blueprint: Blueprint
    task: TaskAuthorOutput
    tests: TestAuthorOutput
    negative_solutions: list[NegativeSolution] = Field(min_length=3)
    generation: GenerationProvenance

    @model_validator(mode="after")
    def role_completeness(self) -> "GeneratedCandidate":
        expected = self.blueprint.editable_files
        starter = sorted(item.path for item in self.task.starter_files)
        reference = sorted(item.path for item in self.task.reference_files)
        if starter != expected or reference != expected:
            raise ValueError("starter/reference files must exactly match blueprint editable_files")
        test_paths = [item.path for item in self.tests.tests]
        if len(test_paths) != len(set(test_paths)):
            raise ValueError("test paths must be unique")
        for test in self.tests.tests:
            if not test.path.endswith((".cpp", ".cc", ".cxx")):
                raise ValueError("task tests must be C++ sources")
            if "catch.hpp" not in test.content:
                raise ValueError("task tests must use the approved Catch surface")
        negative_ids = [item.negative_id for item in self.negative_solutions]
        if len(negative_ids) != len(set(negative_ids)):
            raise ValueError("negative IDs must be unique")
        for negative in self.negative_solutions:
            if sorted(item.path for item in negative.files) != expected:
                raise ValueError("each negative solution must replace every editable file")
        return self


def scaffold_identity() -> dict[str, Any]:
    payload = _ASSET.read_bytes()
    return {
        "scaffold_id": GENERATED_SCAFFOLD,
        "template_sha256": sha256_bytes(payload),
        "template_bytes": len(payload),
        "language_standard": "c++17",
        "test_framework": BUNDLE_ID,
    }


def _render_cmake(task_id: str, sources: list[str]) -> bytes:
    template = _ASSET.read_text(encoding="utf-8")
    rendered_sources = "\n".join(f'  "{path}"' for path in sources)
    rendered = (
        template.replace("@PROJECT@", task_id.replace("-", "_"))
        .replace("@TARGET@", task_id)
        .replace("@SOURCES@", rendered_sources)
    )
    return normalize_text_bytes(rendered.encode("utf-8"), label="generated CMakeLists.txt")


def _mapping(files: list[GeneratedFile]) -> dict[str, bytes]:
    return {
        item.path: normalize_text_bytes(item.content.encode("utf-8"), label=item.path)
        for item in files
    }


def materialize_generated_task(
    *,
    candidate_value: dict[str, Any],
    canonical_root: Path,
    config_lock: dict[str, Any],
) -> dict[str, Any]:
    try:
        candidate = GeneratedCandidate.model_validate(candidate_value)
    except ValidationError as exc:
        reason = (
            "generated_build_metadata_rejected"
            if any(token in str(exc).lower() for token in ("build", "command", "cmake", ".sh"))
            else "static_schema_error"
        )
        raise AiderSftError(reason, str(exc)) from exc
    starter = _mapping(candidate.task.starter_files)
    reference = _mapping(candidate.task.reference_files)
    context = _mapping(candidate.task.context_files)
    raw_tests = _mapping(candidate.tests.tests)
    tests = {f"grader/tests/{path}": payload for path, payload in raw_tests.items()}
    content_seed = hash_file_records(
        "aider-sft-generated-content-seed-v1",
        {
            **{f"starter/{path}": value for path, value in starter.items()},
            **{f"reference/{path}": value for path, value in reference.items()},
            **{f"context/{path}": value for path, value in context.items()},
            **{f"tests/{path}": value for path, value in raw_tests.items()},
        },
    )
    task_id = f"{candidate.blueprint.proposed_slug}-{content_seed[:10]}"
    source_paths = sorted(
        path for path in [*starter, *raw_tests] if Path(path).suffix in {".cpp", ".cc", ".cxx"}
    )
    cmake = _render_cmake(task_id, source_paths)
    build = {"grader/build/CMakeLists.txt": cmake}

    task_root = canonical_root / task_id
    docs = {
        "docs/introduction.md": normalize_text_bytes(
            candidate.task.introduction.encode("utf-8"), label="introduction"
        ),
        "docs/instructions.md": normalize_text_bytes(
            candidate.task.instructions.encode("utf-8"), label="instructions"
        ),
    }
    if candidate.task.instructions_append is not None:
        docs["docs/instructions.append.md"] = normalize_text_bytes(
            candidate.task.instructions_append.encode("utf-8"),
            label="instructions.append",
        )
    for base, files in (
        (task_root, docs),
        (task_root / "workspace/starter", starter),
        (task_root / "workspace/reference", reference),
        (task_root / "workspace/context", context),
        (task_root, tests),
        (task_root, build),
    ):
        for relative, payload in sorted(files.items()):
            atomic_write(base / relative, payload)

    negative_files: dict[str, bytes] = {}
    for negative in candidate.negative_solutions:
        for item in negative.files:
            relative = f"grader/negative-solutions/{negative.negative_id}/{item.path}"
            negative_files[relative] = normalize_text_bytes(
                item.content.encode("utf-8"), label=relative
            )
            atomic_write(task_root / relative, negative_files[relative])
    write_json(
        task_root / "grader/shared-support.json",
        {
            "schema_version": "aider-sft-task-shared-support-v1",
            "bundles": [
                {
                    "bundle_id": BUNDLE_ID,
                    "manifest": "private/grader-support/manifest.json",
                }
            ],
        },
    )

    toolchain = config_lock["config"]["toolchain"]
    sandbox = config_lock["config"]["sandbox"]
    compiler = toolchain["cxx_path"]
    normal_configure = [
        "cmake",
        "-S",
        ".",
        "-B",
        "build",
        "-G",
        "Unix Makefiles",
        f"-DCMAKE_CXX_COMPILER={compiler}",
    ]
    sanitizer_configure = [
        "cmake",
        "-S",
        ".",
        "-B",
        "build-sanitized",
        "-G",
        "Unix Makefiles",
        f"-DCMAKE_CXX_COMPILER={compiler}",
        "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
        "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
    ]
    mappings = [
        {"source": "grader/build/CMakeLists.txt", "destination": "CMakeLists.txt"},
        *[{"source": f"grader/tests/{path}", "destination": path} for path in sorted(raw_tests)],
        *[
            {"shared_bundle": BUNDLE_ID, "source": path, "destination": path}
            for path in ("test/catch.hpp", "test/tests-main.cpp")
        ],
    ]
    canonical_payloads = {
        **docs,
        **{f"workspace/starter/{path}": value for path, value in starter.items()},
        **{f"workspace/reference/{path}": value for path, value in reference.items()},
        **{f"workspace/context/{path}": value for path, value in context.items()},
        **tests,
        **build,
        **negative_files,
    }
    content_sha256 = hash_file_records("aider-sft-canonical-task-content-v1", canonical_payloads)
    grader = {
        "adapter": GENERATED_SCAFFOLD,
        "protocol_version": 2,
        "image_id": toolchain["docker_image_id"],
        "image": toolchain["docker_image"],
        "cmake_generator": "Unix Makefiles",
        "toolchain": {
            "cxx_path": compiler,
            "cxx_version": toolchain["cxx_version"],
            "cxx_binary_sha256": toolchain["cxx_binary_sha256"],
        },
        "sandbox": sandbox,
        "working_directory": ".",
        "workspace_assembly": {
            "state_tree": "workspace/{starter|reference}",
            "context_tree": "workspace/context",
            "shared_support_manifest": "grader/shared-support.json",
            "file_mappings": mappings,
        },
        "environment": {"LC_ALL": "C", "TZ": "UTC"},
        "configure_argv": normal_configure,
        "compile_argv": ["cmake", "--build", "build", "--target", task_id],
        "test_discovery_argv": [f"./build/{task_id}", "--list-tests"],
        "test_argv": [f"./build/{task_id}"],
        "test_count_protocol": "catch-v1-list-and-run",
        "configure_timeout_seconds": 120,
        "compile_timeout_seconds": 300,
        "test_timeout_seconds": 180,
        "sanitizer": {
            "profile_id": "clang-asan-ubsan-v1",
            "configure_argv": sanitizer_configure,
            "compile_argv": ["cmake", "--build", "build-sanitized", "--target", task_id],
            "test_discovery_argv": [f"./build-sanitized/{task_id}", "--list-tests"],
            "test_argv": [f"./build-sanitized/{task_id}"],
            "environment": {
                "ASAN_OPTIONS": "detect_leaks=1:halt_on_error=1",
                "UBSAN_OPTIONS": "halt_on_error=1:print_stacktrace=1",
            },
            "timeout_seconds": 300,
        },
        "limits": {
            "cpus": sandbox["cpus"],
            "memory_mib": sandbox["memory_mib"],
            "pids": sandbox["pids"],
            "file_size_mib": sandbox["file_size_mib"],
        },
    }
    task_value = {
        "schema_version": "aider-sft-task-v1",
        "task_id": task_id,
        "root_task_id": candidate.candidate_id,
        "task_family_id": candidate.blueprint.task_family_id,
        "title": candidate.blueprint.title,
        "language": "cpp",
        "language_standard": "c++17",
        "source": {
            "kind": "llm_assisted",
            "repository": "project-generated",
            "revision": candidate.generation.generation_run_id,
            "relative_path": None,
            "license": "NOASSERTION",
            "content_sha256": content_sha256,
        },
        "classification": {
            "primary_category": candidate.blueprint.primary_category.value,
            "tags": candidate.blueprint.tags,
            "difficulty": candidate.blueprint.difficulty.value,
        },
        "files": {
            "editable": sorted(starter),
            "model_context": sorted(context),
            "task_specific_tests": sorted(tests),
            "shared_grader_support": [BUNDLE_ID],
            "source_reference_mapping": [],
            "context_reference_equivalence": [],
        },
        "grader": grader,
        "generation": candidate.generation.model_dump(mode="json"),
        "distribution_scope": "internal_research",
    }
    try:
        task = CanonicalTask.model_validate(task_value)
    except ValidationError as exc:
        raise AiderSftError("static_schema_error", str(exc)) from exc
    write_json(task_root / "task.json", task.model_dump(mode="json"))
    write_json(task_root / "provenance/generation.json", candidate.model_dump(mode="json"))
    static = {
        "schema_version": "aider-sft-static-receipt-v1",
        "task_id": task_id,
        "status": "passed",
        "input_fingerprint": fingerprint(
            "aider-sft-generated-static-input-v1",
            candidate.model_dump(mode="json"),
            scaffold_identity(),
            config_lock["lock_sha256"],
        ),
        "content_sha256": content_sha256,
        "negative_solution_count": len(candidate.negative_solutions),
        "intended_split": candidate.intended_split.value,
    }
    write_json(task_root / "receipts/static.json", static)
    return {
        "task_id": task_id,
        "task_root": str(task_root),
        "content_sha256": content_sha256,
        "intended_split": candidate.intended_split.value,
        "static_receipt": static,
    }
