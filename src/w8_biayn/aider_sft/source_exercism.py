"""Canonicalize pinned Exercism roots into the common private task schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .errors import AiderSftError
from .grader_support import BUNDLE_ID
from .inventory import tracked_task_files
from .schema import CanonicalTask, SourceManifestEntry
from .util import (
    atomic_write,
    fingerprint,
    hash_file_records,
    normalize_relative_path,
    normalize_text_bytes,
    read_json,
    validate_fence_safe,
    write_json,
)


def _load_text(path: Path, *, label: str, fence_safe: bool = False) -> bytes:
    if not path.is_file() or path.is_symlink():
        raise AiderSftError("static_schema_error", f"missing regular file: {label}")
    raw = normalize_text_bytes(path.read_bytes(), label=label)
    if fence_safe:
        validate_fence_safe(raw, label=label)
    return raw


def _declared_paths(config: dict[str, Any], key: str) -> list[str]:
    files = config.get("files")
    if not isinstance(files, dict):
        raise AiderSftError("static_schema_error", "source .meta/config.json lacks files")
    raw = files.get(key, [])
    if not isinstance(raw, list) or any(not isinstance(value, str) for value in raw):
        raise AiderSftError("static_schema_error", f"files.{key} must be a string list")
    paths = [normalize_relative_path(value) for value in raw]
    if len(paths) != len(set(paths)):
        raise AiderSftError("static_schema_error", f"files.{key} contains duplicates")
    return paths


def _reference_for(
    canonical_path: str,
    candidates: list[str],
    *,
    source_root: Path,
    allow_missing: bool,
) -> tuple[str | None, bytes | None]:
    suffix = Path(canonical_path).suffix
    matches = [candidate for candidate in candidates if Path(candidate).suffix == suffix]
    if len(matches) > 1:
        canonical_stem = Path(canonical_path).stem
        narrowed = [
            candidate
            for candidate in matches
            if canonical_stem in Path(candidate).stem
            or Path(candidate).stem in {"example", "exemplar"}
        ]
        if len(narrowed) == 1:
            matches = narrowed
    if not matches:
        if allow_missing:
            return None, None
        raise AiderSftError("missing_reference", f"no example/exemplar maps to {canonical_path}")
    if len(matches) != 1:
        raise AiderSftError(
            "reference_mapping_error",
            f"ambiguous example/exemplar mapping for {canonical_path}: {matches}",
        )
    source_reference = matches[0]
    return source_reference, _load_text(
        source_root / source_reference,
        label=source_reference,
        fence_safe=True,
    )


def _check_limits(
    *,
    editable: dict[str, bytes],
    context: dict[str, bytes],
    tests: dict[str, bytes],
    build: dict[str, bytes],
    limits: dict[str, Any],
) -> None:
    if len(editable) > limits["editable_files"] or len(context) > limits["context_files"]:
        raise AiderSftError("file_limit_exceeded", "model-visible file-count limit exceeded")
    all_files = {**editable, **context, **tests, **build}
    if len(all_files) > limits["task_local_files"]:
        raise AiderSftError("file_limit_exceeded", "task-local file-count limit exceeded")
    for relative, payload in {**editable, **context}.items():
        if len(payload) > limits["visible_file_bytes"]:
            raise AiderSftError("file_limit_exceeded", f"visible file too large: {relative}")
    for relative, payload in {**tests, **build}.items():
        if len(payload) > limits["grader_file_bytes"]:
            raise AiderSftError("file_limit_exceeded", f"grader file too large: {relative}")
    if sum(map(len, [*editable.values(), *context.values()])) > limits["visible_total_bytes"]:
        raise AiderSftError("file_limit_exceeded", "model-visible byte limit exceeded")
    if sum(map(len, all_files.values())) > limits["task_total_bytes"]:
        raise AiderSftError("file_limit_exceeded", "task-local byte limit exceeded")


def _write_files(root: Path, files: dict[str, bytes]) -> None:
    for relative, payload in sorted(files.items()):
        atomic_write(root / normalize_relative_path(relative), payload)


def canonicalize_exercism_task(
    *,
    entry: SourceManifestEntry,
    checkout: Path,
    canonical_root: Path,
    config_lock: dict[str, Any],
) -> dict[str, Any]:
    source_root = checkout / entry.source_relative_path
    source_config = read_json(source_root / ".meta/config.json")
    solutions = _declared_paths(source_config, "solution")
    editors = _declared_paths(source_config, "editor")
    test_paths = _declared_paths(source_config, "test")
    example_paths = sorted(
        set(_declared_paths(source_config, "example") + _declared_paths(source_config, "exemplar"))
    )
    if not solutions:
        raise AiderSftError("missing_editable_files", f"{entry.slug} has no solution files")
    if not test_paths:
        raise AiderSftError("missing_tests", f"{entry.slug} has no declared tests")
    context_paths = sorted(set(editors) - set(solutions))
    if set(solutions) & set(context_paths):
        raise AiderSftError("static_schema_error", "editable and context roles collide")

    introduction_path = source_root / ".docs/introduction.md"
    introduction = (
        _load_text(introduction_path, label=f"{entry.slug}/.docs/introduction.md")
        if introduction_path.is_file()
        else None
    )
    instructions = _load_text(
        source_root / ".docs/instructions.md",
        label=f"{entry.slug}/.docs/instructions.md",
    )
    append_path = source_root / ".docs/instructions.append.md"
    append = (
        _load_text(
            append_path,
            label=f"{entry.slug}/.docs/instructions.append.md",
        )
        if append_path.is_file()
        else None
    )

    starter: dict[str, bytes] = {}
    reference: dict[str, bytes] = {}
    context: dict[str, bytes] = {}
    source_reference_mapping: list[dict[str, Any]] = []
    context_equivalence: list[dict[str, Any]] = []

    for relative in sorted(solutions):
        starter_payload = _load_text(
            source_root / relative,
            label=f"{entry.slug}/{relative}",
            fence_safe=True,
        )
        starter[relative] = starter_payload
        source_reference, reference_payload = _reference_for(
            relative,
            example_paths,
            source_root=source_root,
            allow_missing=True,
        )
        reference[relative] = (
            reference_payload if reference_payload is not None else starter_payload
        )
        if source_reference is not None:
            source_reference_mapping.append(
                {
                    "source_reference": source_reference,
                    "canonical_editable": relative,
                    "canonical_context": None,
                    "required_relation": None,
                }
            )

    for relative in context_paths:
        payload = _load_text(
            source_root / relative,
            label=f"{entry.slug}/{relative}",
            fence_safe=True,
        )
        context[relative] = payload
        source_reference, exemplar = _reference_for(
            relative,
            example_paths,
            source_root=source_root,
            allow_missing=False,
        )
        if exemplar != payload:
            raise AiderSftError(
                "unsupported_editor_reference_change",
                f"context-only editor file changes in the reference: {entry.slug}/{relative}",
            )
        context_equivalence.append(
            {
                "source_reference": source_reference,
                "canonical_editable": None,
                "canonical_context": relative,
                "required_relation": "byte_identical_to_starter",
            }
        )

    tests = {
        f"grader/tests/{relative}": _load_text(
            source_root / relative,
            label=f"{entry.slug}/{relative}",
        )
        for relative in test_paths
    }
    cmake = _load_text(source_root / "CMakeLists.txt", label=f"{entry.slug}/CMakeLists.txt")
    if b"CXX_STANDARD 17" not in cmake:
        raise AiderSftError("language_standard_mismatch", f"{entry.slug} is not C++17")
    build_files = {"grader/build/CMakeLists.txt": cmake}
    limits = config_lock["config"]["limits"]
    _check_limits(
        editable=starter,
        context=context,
        tests=tests,
        build=build_files,
        limits=limits,
    )

    task_root = canonical_root / entry.slug
    docs = {"docs/instructions.md": instructions}
    if introduction is not None:
        docs["docs/introduction.md"] = introduction
    if append is not None:
        docs["docs/instructions.append.md"] = append
    _write_files(task_root, docs)
    _write_files(task_root / "workspace/starter", starter)
    _write_files(task_root / "workspace/reference", reference)
    _write_files(task_root / "workspace/context", context)
    _write_files(task_root, tests)
    _write_files(task_root, build_files)

    shared_support = {
        "schema_version": "aider-sft-task-shared-support-v1",
        "bundles": [
            {
                "bundle_id": BUNDLE_ID,
                "manifest": "private/grader-support/manifest.json",
            }
        ],
    }
    write_json(task_root / "grader/shared-support.json", shared_support)

    toolchain = config_lock["config"]["toolchain"]
    sandbox = config_lock["config"]["sandbox"]
    compiler = toolchain["cxx_path"]
    target = entry.slug
    normal_configure = [
        "cmake",
        "-S",
        ".",
        "-B",
        "build",
        "-G",
        "Unix Makefiles",
        f"-DCMAKE_CXX_COMPILER={compiler}",
        "-DEXERCISM_RUN_ALL_TESTS=1",
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
        "-DEXERCISM_RUN_ALL_TESTS=1",
        "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
        "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
    ]
    mappings = [
        {
            "source": "grader/build/CMakeLists.txt",
            "destination": "CMakeLists.txt",
        },
        *[{"source": f"grader/tests/{path}", "destination": path} for path in sorted(test_paths)],
        *[
            {
                "shared_bundle": BUNDLE_ID,
                "source": path,
                "destination": path,
            }
            for path in ("test/catch.hpp", "test/tests-main.cpp")
        ],
    ]
    canonical_payloads = {
        **docs,
        **{f"workspace/starter/{path}": value for path, value in starter.items()},
        **{f"workspace/reference/{path}": value for path, value in reference.items()},
        **{f"workspace/context/{path}": value for path, value in context.items()},
        **tests,
        **build_files,
    }
    content_sha256 = hash_file_records("aider-sft-canonical-task-content-v1", canonical_payloads)
    task_value = {
        "schema_version": "aider-sft-task-v1",
        "task_id": entry.slug,
        "root_task_id": entry.slug,
        "task_family_id": entry.task_family_id,
        "title": entry.slug.replace("-", " ").title(),
        "language": "cpp",
        "language_standard": "c++17",
        "source": {
            "kind": "exercism",
            "repository": config_lock["config"]["upstreams"]["exercism_cpp"]["repository"],
            "revision": config_lock["config"]["upstreams"]["exercism_cpp"]["revision"],
            "relative_path": entry.source_relative_path,
            "license": entry.spdx_license,
            "content_sha256": content_sha256,
        },
        "classification": {
            "primary_category": entry.primary_category.value,
            "tags": entry.tags,
            "difficulty": entry.difficulty.value,
        },
        "files": {
            "editable": sorted(starter),
            "model_context": sorted(context),
            "task_specific_tests": sorted(tests),
            "shared_grader_support": [BUNDLE_ID],
            "source_reference_mapping": source_reference_mapping,
            "context_reference_equivalence": context_equivalence,
        },
        "grader": {
            "adapter": "exercism-cmake-catch-v1",
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
            "compile_argv": ["cmake", "--build", "build", "--target", target],
            "test_discovery_argv": [f"./build/{target}", "--list-tests"],
            "test_argv": [f"./build/{target}"],
            "test_count_protocol": "catch-v1-list-and-run",
            "configure_timeout_seconds": 120,
            "compile_timeout_seconds": 300,
            "test_timeout_seconds": 180,
            "sanitizer": {
                "profile_id": "clang-asan-ubsan-v1",
                "configure_argv": sanitizer_configure,
                "compile_argv": [
                    "cmake",
                    "--build",
                    "build-sanitized",
                    "--target",
                    target,
                ],
                "test_discovery_argv": [
                    f"./build-sanitized/{target}",
                    "--list-tests",
                ],
                "test_argv": [f"./build-sanitized/{target}"],
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
        },
        "generation": None,
        "distribution_scope": "internal_research",
    }
    try:
        task = CanonicalTask.model_validate(task_value)
    except ValidationError as exc:
        raise AiderSftError("static_schema_error", str(exc)) from exc
    write_json(task_root / "task.json", task.model_dump(mode="json"))
    source_map = {
        "schema_version": "aider-sft-source-map-v1",
        "source_tree_sha256": entry.tree_sha256,
        "canonical_content_sha256": content_sha256,
        "tracked_source_tree_sha256": hash_file_records(
            "aider-sft-source-tree-v1",
            tracked_task_files(checkout, entry.source_relative_path),
        ),
        "reference_mapping": source_reference_mapping,
        "context_reference_equivalence": context_equivalence,
    }
    if source_map["tracked_source_tree_sha256"] != entry.tree_sha256:
        raise AiderSftError("source_inventory_mismatch", f"source task changed: {entry.slug}")
    write_json(task_root / "provenance/source-map.json", source_map)
    static_receipt = {
        "schema_version": "aider-sft-static-receipt-v1",
        "task_id": task.task_id,
        "status": "passed",
        "input_fingerprint": fingerprint(
            "aider-sft-static-input-v1",
            content_sha256,
            config_lock["lock_sha256"],
            entry.model_dump(mode="json"),
        ),
        "counts": {
            "editable": len(starter),
            "context": len(context),
            "tests": len(tests),
        },
        "content_sha256": content_sha256,
    }
    write_json(task_root / "receipts/static.json", static_receipt)
    return {
        "task_id": task.task_id,
        "task_root": str(task_root),
        "content_sha256": content_sha256,
        "static_receipt": static_receipt,
    }


def load_canonical_task(task_root: Path) -> CanonicalTask:
    try:
        return CanonicalTask.model_validate(read_json(task_root / "task.json"))
    except ValidationError as exc:
        raise AiderSftError("static_schema_error", str(exc)) from exc
