"""SLIME data and reward bridge for Multi-SWE-bench mini C++ base evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any, Iterable, Sequence

from w8_biayn.cpp_perf.eval import write_json
from w8_biayn.cpp_perf.sandbox import BASE_DOCKER_IMAGE, DEFAULT_MEMORY
from w8_biayn.integrations.slime_cpp_perf import load_slime_debug_samples

DATA_SOURCE = "ByteDance-Seed/Multi-SWE-bench_mini"
BENCHMARK = "multi-swe-bench-mini"
LANGUAGE = "cpp"
DATASET_KIND = "slime-multi-swe-cpp-dataset"
SANDBOX_IMAGE_RECEIPT_KIND = "multi-swe-sandbox-images"
SCHEMA_VERSION = 3
ORACLE_PROTOCOL_VERSION = 2
DEFAULT_DATA_ROOT_ENV = "W8_BIAYN_DATA_DIR"
SANDBOX_IMAGE_ENV = "W8_SLIME_MULTI_SWE_SANDBOX_IMAGE"
INCLUDE_LOGS_ENV = "W8_SLIME_MULTI_SWE_INCLUDE_LOGS"
TEST_TIMEOUT_ENV = "W8_SLIME_MULTI_SWE_TEST_TIMEOUT_SECONDS"
CLONE_TIMEOUT_ENV = "W8_SLIME_MULTI_SWE_CLONE_TIMEOUT_SECONDS"
REPO_CACHE_ENV = "W8_SLIME_MULTI_SWE_REPO_CACHE"
ORACLE_SETUP_CHECK_ENV = "W8_SLIME_MULTI_SWE_ORACLE_SETUP_CHECK"
DEFAULT_MULTI_SWE_SANDBOX_IMAGE = "w8-biayn-multi-swe-cpp:latest"
DEFAULT_TEST_TIMEOUT_SECONDS = 1200
DEFAULT_CLONE_TIMEOUT_SECONDS = 600
DEFAULT_EVAL_LIMIT = 4
OFFICIAL_SANDBOX_NAMESPACE = "mswebench"
ORACLE_RECORDS_FILENAME = "oracle.records.jsonl"
OFFICIAL_IMAGE_HARNESS_MODE = "official-instance-image"
_OFFICIAL_CONTRACT_ERROR = 86
_TRUSTED_PATCH_ERROR = 87
_CANDIDATE_PATCH_ERROR = 88
ORACLE_SUMMARY_FILENAME = "oracle.summary.json"
SANDBOX_IMAGES_FILENAME = "sandbox-images.json"
ALLOWED_DIFF_FENCE_LANGS = {"diff", "patch"}
RECOVERABLE_DIFF_FENCE_LANGS = {"", "diff", "patch"}

_DIFF_GIT_RE = re.compile(r"^diff --git\s+(.+?)\s+(.+?)$", re.MULTILINE)
_DIFF_FILE_RE = re.compile(r"^(?:---|\+\+\+)\s+([^\t\n\r]+)", re.MULTILINE)
_CTEST_TOTAL_RE = re.compile(
    r"(?:Total Tests:\s*|tests failed out of\s+)(\d+)",
    re.IGNORECASE,
)
_COMPILE_ERROR_NEEDLES = (
    "cmake error",
    "compiler error",
    "error:",
    "undefined reference",
    "no rule to make target",
    "could not compile",
    "compilation terminated",
)

FORBIDDEN_DIR_NAMES = {
    ".buildkite",
    ".circleci",
    ".github",
    "benchmark",
    "benchmarks",
    "build",
    "ci",
    "cmake",
    "doc",
    "docs",
    "documentation",
    "example",
    "examples",
    "fuzz",
    "fuzzing",
    "script",
    "scripts",
    "test",
    "tests",
    "testing",
}
FORBIDDEN_BASENAMES = {
    "build.gradle",
    "cargo.lock",
    "cargo.toml",
    "cmakelists.txt",
    "conanfile.py",
    "conanfile.txt",
    "makefile",
    "meson.build",
    "package-lock.json",
    "package.json",
    "pom.xml",
    "vcpkg.json",
    "yarn.lock",
}
SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
    ".ipp",
    ".inc",
}


@dataclass(frozen=True)
class MultiSweRepoHarness:
    org: str
    repo: str
    git_url: str
    test_command: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.org.lower(), self.repo.lower())

    @property
    def repo_full_name(self) -> str:
        return f"{self.org}/{self.repo}"

    @property
    def cache_name(self) -> str:
        return f"{self.org}__{self.repo}"


@dataclass(frozen=True)
class MultiSweTestResult:
    returncode: int | None
    logs: str
    timeout: bool = False
    harness_error: bool = False
    patch_apply_error: bool = False
    no_tests_collected: bool = False
    tests_collected: int | None = None
    sandbox_image: str | None = None
    sandbox_image_id: str | None = None

    @property
    def passed(self) -> bool:
        return (
            self.returncode == 0
            and not self.timeout
            and not self.harness_error
            and not self.no_tests_collected
            and bool(self.tests_collected)
        )


class MultiSweResponseError(ValueError):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


REPO_HARNESSES: dict[tuple[str, str], MultiSweRepoHarness] = {
    harness.key: harness
    for harness in (
        MultiSweRepoHarness(
            org="catchorg",
            repo="Catch2",
            git_url="https://github.com/catchorg/Catch2.git",
            test_command=(
                "cmake -S . -B build -DCATCH_BUILD_TESTING=ON "
                "-DCATCH_BUILD_EXAMPLES=OFF && "
                "cmake --build build --parallel 2 && "
                "cd build && ctest --output-on-failure"
            ),
        ),
        MultiSweRepoHarness(
            org="fmtlib",
            repo="fmt",
            git_url="https://github.com/fmtlib/fmt.git",
            test_command=(
                "cmake -S . -B build -DFMT_TEST=ON -DFMT_DOC=OFF && "
                "cmake --build build --parallel 2 && "
                "cd build && ctest --output-on-failure"
            ),
        ),
        MultiSweRepoHarness(
            org="nlohmann",
            repo="json",
            git_url="https://github.com/nlohmann/json.git",
            test_command=(
                "cmake -S . -B build -DJSON_BuildTests=ON && "
                "cmake --build build --parallel 2 && "
                "cd build && ctest --output-on-failure"
            ),
        ),
        MultiSweRepoHarness(
            org="simdjson",
            repo="simdjson",
            git_url="https://github.com/simdjson/simdjson.git",
            test_command=(
                "cmake -S . -B build -DSIMDJSON_BUILD_TESTS=ON && "
                "cmake --build build --parallel 2 && "
                "cd build && ctest --output-on-failure"
            ),
        ),
        MultiSweRepoHarness(
            org="yhirose",
            repo="cpp-httplib",
            git_url="https://github.com/yhirose/cpp-httplib.git",
            test_command=(
                "cmake -S . -B build -DHTTPLIB_TEST=ON && "
                "cmake --build build --parallel 2 && "
                "cd build && ctest --output-on-failure"
            ),
        ),
    )
}


def official_multi_swe_sandbox_image(org: object, repo: object, number: object) -> str:
    """Return the official per-instance Multi-SWE image reference."""

    normalized_org = str(org or "").strip()
    normalized_repo = str(repo or "").strip()
    normalized_number = str(number or "").strip()
    if not normalized_org or not normalized_repo:
        raise ValueError("Multi-SWE task is missing org/repo for sandbox image selection")
    if not normalized_number.isdigit() or int(normalized_number) <= 0:
        raise ValueError(f"Multi-SWE task has invalid pull-request number: {number!r}")
    repository = f"{OFFICIAL_SANDBOX_NAMESPACE}/{normalized_org}_m_{normalized_repo}".lower()
    return f"{repository}:pr-{int(normalized_number)}"


def build_slime_multi_swe_cpp_dataset(
    source_root: str | Path,
    output_dir: str | Path,
    *,
    jsonl_path: str | Path | None = None,
    eval_limit: int | None = DEFAULT_EVAL_LIMIT,
    profile: str = "moonlight-multi-swe-cpp",
    run_id: str | None = None,
    force: bool = False,
) -> dict[str, Path]:
    """Write SLIME eval JSONL files from Multi-SWE-bench mini C++ rows."""

    source = Path(source_root)
    data_path = (
        Path(jsonl_path) if jsonl_path is not None else source / "multi_swe_bench_mini.jsonl"
    )
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        if not force:
            raise FileExistsError(f"{output} already exists and is not empty; pass force=True")
        shutil.rmtree(output)

    rows = [row for row in load_multi_swe_rows(data_path) if repo_harness_for_row(row) is not None]
    rows.sort(key=lambda row: str(row.get("instance_id") or ""))
    if eval_limit is not None:
        rows = rows[:eval_limit]
    if not rows:
        raise ValueError(f"No C++ Multi-SWE-bench mini rows found in {data_path}")

    eval_rows = []
    task_paths = []
    sandbox_images: set[str] = set()
    tasks_root = output / "tasks"
    for row in rows:
        harness = repo_harness_for_row(row)
        if harness is None:  # pragma: no cover - filtered above
            continue
        instance_id = instance_id_for_row(row, harness=harness)
        task_path = tasks_root / safe_task_dir(instance_id) / "task.json"
        task_path.parent.mkdir(parents=True, exist_ok=True)
        task = normalized_task(row, harness=harness, instance_id=instance_id)
        write_json(task_path, task)
        sandbox_images.add(str(task["sandbox_image"]))
        task_rel = task_path.relative_to(output).as_posix()
        eval_rows.append(
            _eval_row(row, harness=harness, instance_id=instance_id, task_path=task_rel)
        )
        task_paths.append(task_rel)

    paths = {
        "eval": output / "eval" / "cpp.jsonl",
        "manifest": output / "manifest.json",
        "oracle_records": output / ORACLE_RECORDS_FILENAME,
        "oracle_summary": output / ORACLE_SUMMARY_FILENAME,
        "sandbox_images": output / SANDBOX_IMAGES_FILENAME,
    }
    _write_jsonl(paths["eval"], eval_rows)
    write_json(
        paths["manifest"],
        {
            "kind": DATASET_KIND,
            "schema_version": SCHEMA_VERSION,
            "data_source": DATA_SOURCE,
            "benchmark": BENCHMARK,
            "language": LANGUAGE,
            "profile": profile,
            "run_id": run_id,
            "source_root": str(source),
            "jsonl_path": str(data_path),
            "output_dir": str(output),
            "admitted": False,
            "harness_mode": OFFICIAL_IMAGE_HARNESS_MODE,
            "oracle_protocol_version": ORACLE_PROTOCOL_VERSION,
            "sandbox_image_mode": "official-per-task",
            "sandbox_images": sorted(sandbox_images),
            "allowed_repos": sorted(harness.repo_full_name for harness in REPO_HARNESSES.values()),
            "counts": {
                "eval": len(eval_rows),
                "task_json": len(task_paths),
                "oracle_checked": 0,
                "oracle_passed": 0,
            },
            "files": {
                "eval": paths["eval"].relative_to(output).as_posix(),
                "tasks": task_paths,
                "oracle_records": paths["oracle_records"].relative_to(output).as_posix(),
                "oracle_summary": paths["oracle_summary"].relative_to(output).as_posix(),
                "sandbox_images": paths["sandbox_images"].relative_to(output).as_posix(),
            },
            "oracle_setup_check": {
                "enabled": True,
                "blocking": True,
                "phase": "data_preflight",
                "correct_answer_source": "fix_patch",
                "all_passed": False,
                "reason": "not_run",
            },
        },
    )
    return paths


def load_multi_swe_rows(jsonl_path: str | Path) -> list[dict[str, Any]]:
    path = Path(jsonl_path)
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def repo_harness_for_row(row: dict[str, Any]) -> MultiSweRepoHarness | None:
    org = str(row.get("org") or "").lower()
    repo = str(row.get("repo") or "").lower()
    return REPO_HARNESSES.get((org, repo))


def repo_harness_for_task(task: dict[str, Any]) -> MultiSweRepoHarness:
    org = str(task.get("org") or "").lower()
    repo = str(task.get("repo") or "").lower()
    harness = REPO_HARNESSES.get((org, repo))
    if harness is None:
        raise MultiSweResponseError("harness_error", f"unsupported C++ repository: {org}/{repo}")
    return harness


def instance_id_for_row(row: dict[str, Any], *, harness: MultiSweRepoHarness) -> str:
    value = row.get("instance_id")
    if isinstance(value, str) and value.strip():
        return value.strip()
    number = row.get("number")
    return f"{harness.org}__{harness.repo}__{number or 'unknown'}"


def safe_task_dir(instance_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", instance_id.strip())
    return safe or "unknown"


def normalized_task(
    row: dict[str, Any], *, harness: MultiSweRepoHarness, instance_id: str
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": BENCHMARK,
        "data_source": DATA_SOURCE,
        "language": LANGUAGE,
        "org": harness.org,
        "repo": harness.repo,
        "repo_full_name": harness.repo_full_name,
        "git_url": harness.git_url,
        "instance_id": instance_id,
        "number": row.get("number"),
        "sandbox_image": official_multi_swe_sandbox_image(
            harness.org, harness.repo, row.get("number")
        ),
        "state": row.get("state"),
        "title": row.get("title"),
        "body": row.get("body"),
        "base": row.get("base"),
        "base_ref": base_ref_from_row(row),
        "resolved_issues": row.get("resolved_issues") or [],
        "fix_patch": row.get("fix_patch") or "",
        "test_patch": row.get("test_patch") or "",
        "fixed_tests": row.get("fixed_tests") or {},
        "p2p_tests": row.get("p2p_tests") or {},
        "f2p_tests": row.get("f2p_tests") or {},
        "s2p_tests": row.get("s2p_tests") or {},
        "n2p_tests": row.get("n2p_tests") or {},
        "run_result": row.get("run_result") or {},
        "test_patch_result": row.get("test_patch_result") or {},
        "fix_patch_result": row.get("fix_patch_result") or {},
    }


def base_ref_from_row(row: dict[str, Any]) -> str | None:
    return base_ref_from_base(row.get("base"))


def base_ref_from_base(base: object) -> str | None:
    if isinstance(base, str) and base.strip():
        return base.strip()
    if not isinstance(base, dict):
        return None
    for key in ("sha", "commit", "base_commit", "merge_commit_sha", "ref"):
        value = base.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, dict):
            nested = base_ref_from_base(value)
            if nested:
                return nested
    return None


def load_prepared_multi_swe_tasks(
    data_root: str | Path,
) -> list[tuple[Path, dict[str, Any]]]:
    root = Path(data_root)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing Multi-SWE data manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("kind") != DATASET_KIND:
        raise ValueError(f"unexpected Multi-SWE dataset kind in {manifest_path}")
    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    task_paths = files.get("tasks")
    if not isinstance(task_paths, list) or not task_paths:
        raise ValueError(f"Multi-SWE manifest has no prepared tasks: {manifest_path}")

    tasks: list[tuple[Path, dict[str, Any]]] = []
    for relative_path in task_paths:
        if not isinstance(relative_path, str):
            raise ValueError(f"invalid Multi-SWE task path in {manifest_path}: {relative_path!r}")
        task_path = root / relative_path
        if not task_path.is_file():
            raise ValueError(f"missing Multi-SWE task JSON: {task_path}")
        task = json.loads(task_path.read_text(encoding="utf-8"))
        if not isinstance(task, dict):
            raise ValueError(f"invalid Multi-SWE task JSON: {task_path}")
        tasks.append((task_path, task))
    return tasks


def sandbox_image_tag_for_task(task: dict[str, Any]) -> str:
    override = os.environ.get(SANDBOX_IMAGE_ENV, "").strip()
    if override:
        return override
    value = task.get("sandbox_image")
    if isinstance(value, str) and value.strip():
        return value.strip()
    try:
        return official_multi_swe_sandbox_image(
            task.get("org"),
            task.get("repo"),
            task.get("number"),
        )
    except ValueError as exc:
        raise MultiSweResponseError("sandbox_image_error", str(exc)) from exc


def sandbox_image_reference_for_task(task: dict[str, Any]) -> str:
    override = os.environ.get(SANDBOX_IMAGE_ENV, "").strip()
    if override:
        return override
    resolved = task.get("sandbox_image_digest")
    if isinstance(resolved, str) and resolved.strip():
        return resolved.strip()
    return sandbox_image_tag_for_task(task)


def _select_prepared_multi_swe_tasks(
    prepared_tasks: list[tuple[Path, dict[str, Any]]],
    task_ids: Sequence[str] | None,
) -> list[tuple[Path, dict[str, Any]]]:
    requested = {str(value).strip() for value in task_ids or () if str(value).strip()}
    if not requested:
        return prepared_tasks
    available = {
        str(task.get("instance_id") or task_path.parent.name) for task_path, task in prepared_tasks
    }
    unknown = sorted(requested - available)
    if unknown:
        raise ValueError(f"unknown Multi-SWE task id(s): {', '.join(unknown)}")
    return [
        (task_path, task)
        for task_path, task in prepared_tasks
        if str(task.get("instance_id") or task_path.parent.name) in requested
    ]


def selected_multi_swe_sandbox_images(
    data_root: str | Path,
    *,
    task_ids: Sequence[str] | None = None,
) -> list[str]:
    prepared_tasks = _select_prepared_multi_swe_tasks(
        load_prepared_multi_swe_tasks(data_root),
        task_ids,
    )
    return sorted({sandbox_image_tag_for_task(task) for _task_path, task in prepared_tasks})


def _pull_docker_image(image: str) -> None:
    result = subprocess.run(
        ["docker", "pull", image],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        details = _logs(result).strip()
        raise RuntimeError(f"failed to pull Multi-SWE sandbox image {image}: {details}")


def _inspect_docker_image(image: str) -> dict[str, Any]:
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        details = _logs(result).strip()
        raise RuntimeError(f"failed to inspect Multi-SWE sandbox image {image}: {details}")
    try:
        payload = json.loads(result.stdout)
        inspected = payload[0]
    except (IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"invalid docker image inspection payload for {image}") from exc
    if not isinstance(inspected, dict):
        raise RuntimeError(f"invalid docker image inspection payload for {image}")

    image_id = str(inspected.get("Id") or "").strip()
    repo_digests = [
        str(value)
        for value in inspected.get("RepoDigests") or []
        if isinstance(value, str) and value
    ]
    repository = image.rsplit(":", 1)[0]
    resolved_image = next(
        (digest for digest in repo_digests if digest.startswith(f"{repository}@")),
        image_id or image,
    )
    return {
        "image": image,
        "resolved_image": resolved_image,
        "image_id": image_id or None,
        "repo_digests": sorted(repo_digests),
    }


def _compatible_image_receipt(
    receipt_path: Path,
    *,
    mode: str,
    override: str | None,
) -> dict[str, Any]:
    if not receipt_path.is_file():
        return {}
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if (
        not isinstance(receipt, dict)
        or receipt.get("kind") != SANDBOX_IMAGE_RECEIPT_KIND
        or receipt.get("mode") != mode
        or receipt.get("override") != override
    ):
        return {}
    return receipt


def prepare_multi_swe_sandbox_images(
    data_root: str | Path,
    *,
    pull: bool = True,
    task_ids: Sequence[str] | None = None,
) -> tuple[dict[str, Any], Path]:
    """Resolve selected task images and merge their immutable receipt."""

    root = Path(data_root)
    prepared_tasks = load_prepared_multi_swe_tasks(root)
    selected_tasks = _select_prepared_multi_swe_tasks(prepared_tasks, task_ids)
    override = os.environ.get(SANDBOX_IMAGE_ENV, "").strip()
    mode = "override" if override else "official-per-task"
    receipt_path = root / SANDBOX_IMAGES_FILENAME
    previous = _compatible_image_receipt(
        receipt_path,
        mode=mode,
        override=override or None,
    )
    image_details = {
        str(item["image"]): dict(item)
        for item in previous.get("images") or []
        if isinstance(item, dict) and item.get("image")
    }
    task_receipts = {
        str(instance_id): dict(value)
        for instance_id, value in (previous.get("tasks") or {}).items()
        if isinstance(value, dict)
    }

    selected_by_task = {
        str(task.get("instance_id") or task_path.parent.name): sandbox_image_tag_for_task(task)
        for task_path, task in selected_tasks
    }
    for image in sorted(set(selected_by_task.values())):
        if pull:
            _pull_docker_image(image)
        image_details[image] = _inspect_docker_image(image)

    for task_path, task in selected_tasks:
        instance_id = str(task.get("instance_id") or task_path.parent.name)
        selected_image = selected_by_task[instance_id]
        details = image_details[selected_image]
        task_receipts[instance_id] = {
            "image": selected_image,
            "resolved_image": details["resolved_image"],
            "image_id": details["image_id"],
            "source": mode,
        }
        task["sandbox_image"] = selected_image
        task["sandbox_image_digest"] = details["resolved_image"]
        task["sandbox_image_id"] = details["image_id"]
        task["sandbox_image_source"] = mode
        write_json(task_path, task)

    receipt = {
        "kind": SANDBOX_IMAGE_RECEIPT_KIND,
        "schema_version": 2,
        "benchmark": BENCHMARK,
        "mode": mode,
        "override": override or None,
        "pull_performed": pull,
        "images": [image_details[image] for image in sorted(image_details)],
        "tasks": dict(sorted(task_receipts.items())),
    }
    write_json(receipt_path, receipt)
    return receipt, receipt_path


def _sha256_text(value: object) -> str:
    return hashlib.sha256(str(value or "").encode()).hexdigest()


def oracle_setup_cache_key(task: dict[str, Any]) -> str:
    """Fingerprint every input that can change the trusted oracle result."""

    payload = {
        "protocol_version": ORACLE_PROTOCOL_VERSION,
        "harness_mode": OFFICIAL_IMAGE_HARNESS_MODE,
        "instance_id": task.get("instance_id"),
        "repo_full_name": task.get("repo_full_name"),
        "base_ref": task.get("base_ref"),
        "test_patch_sha256": _sha256_text(task.get("test_patch")),
        "fix_patch_sha256": _sha256_text(task.get("fix_patch")),
        "sandbox_image": task.get("sandbox_image"),
        "sandbox_image_digest": task.get("sandbox_image_digest"),
        "sandbox_image_id": task.get("sandbox_image_id"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _oracle_metadata(
    root: Path,
    task_path: Path,
    task: dict[str, Any],
) -> dict[str, Any]:
    instance_id = task.get("instance_id")
    return {
        "task_id": instance_id,
        "problem_id": instance_id,
        "instance_id": instance_id,
        "org": task.get("org"),
        "repo": task.get("repo"),
        "repo_full_name": task.get("repo_full_name"),
        "task_path": task_path.relative_to(root).as_posix(),
        "task_root": str(root),
    }


def oracle_setup_records_from_prepared_tasks(
    data_root: str | Path,
) -> list[dict[str, Any]]:
    root = Path(data_root)
    return [
        oracle_setup_record_from_metadata(_oracle_metadata(root, task_path, task))
        for task_path, task in load_prepared_multi_swe_tasks(root)
    ]


def _persist_oracle_preflight(
    root: Path,
    *,
    prepared_tasks: list[tuple[Path, dict[str, Any]]],
    records_by_id: dict[str, dict[str, Any]],
    image_receipt: dict[str, Any],
    image_receipt_path: Path,
    reused_count: int,
    executed_count: int,
    selected_task_count: int,
) -> tuple[dict[str, Path], dict[str, Any]]:
    records = [
        records_by_id[instance_id]
        for task_path, task in prepared_tasks
        if (instance_id := str(task.get("instance_id") or task_path.parent.name)) in records_by_id
    ]
    records_path = root / ORACLE_RECORDS_FILENAME
    summary_path = root / ORACLE_SUMMARY_FILENAME
    summary = aggregate_oracle_setup_records(
        records,
        records_file=records_path.name,
        expected_task_count=len(prepared_tasks),
        reused_count=reused_count,
        executed_count=executed_count,
    )
    summary.update(
        {
            "summary_file": summary_path.name,
            "sandbox_images_file": image_receipt_path.name,
            "sandbox_image_mode": image_receipt["mode"],
            "harness_mode": OFFICIAL_IMAGE_HARNESS_MODE,
            "oracle_protocol_version": ORACLE_PROTOCOL_VERSION,
            "selected_task_count": selected_task_count,
        }
    )
    _write_jsonl(records_path, records)
    write_json(summary_path, summary)

    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["admitted"] = summary["all_passed"]
    manifest["harness_mode"] = OFFICIAL_IMAGE_HARNESS_MODE
    manifest["oracle_protocol_version"] = ORACLE_PROTOCOL_VERSION
    manifest["sandbox_image_mode"] = image_receipt["mode"]
    manifest["sandbox_images"] = [str(item["image"]) for item in image_receipt["images"]]
    counts = manifest.setdefault("counts", {})
    counts["oracle_checked"] = summary["task_count"]
    counts["oracle_passed"] = summary["passed_count"]
    files = manifest.setdefault("files", {})
    files["oracle_records"] = records_path.relative_to(root).as_posix()
    files["oracle_summary"] = summary_path.relative_to(root).as_posix()
    files["sandbox_images"] = image_receipt_path.relative_to(root).as_posix()
    manifest["oracle_setup_check"] = summary
    write_json(manifest_path, manifest)
    return {
        "manifest": manifest_path,
        "oracle_records": records_path,
        "oracle_summary": summary_path,
        "sandbox_images": image_receipt_path,
    }, summary


def run_multi_swe_oracle_preflight(
    data_root: str | Path,
    *,
    pull_images: bool = True,
    resume: bool = False,
    task_ids: Sequence[str] | None = None,
) -> tuple[dict[str, Path], dict[str, Any]]:
    """Resolve images and persist a resumable blocking fix-patch proof."""

    root = Path(data_root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported Multi-SWE dataset schema in {root / 'manifest.json'}; "
            "rebuild the prepared data"
        )
    prepared_tasks = load_prepared_multi_swe_tasks(root)
    selected_tasks = _select_prepared_multi_swe_tasks(prepared_tasks, task_ids)
    selected_ids = {
        str(task.get("instance_id") or task_path.parent.name) for task_path, task in selected_tasks
    }
    image_receipt, image_receipt_path = prepare_multi_swe_sandbox_images(
        root,
        pull=pull_images,
        task_ids=tuple(sorted(selected_ids)),
    )
    prepared_tasks = load_prepared_multi_swe_tasks(root)

    records_path = root / ORACLE_RECORDS_FILENAME
    existing_rows = _read_jsonl(records_path) if records_path.is_file() else []
    existing_by_id = {
        str(row.get("instance_id") or row.get("task_id")): row
        for row in existing_rows
        if isinstance(row, dict) and (row.get("instance_id") or row.get("task_id"))
    }
    preserve_existing = resume or bool(task_ids)
    records_by_id: dict[str, dict[str, Any]] = {}
    if preserve_existing:
        for _task_path, task in prepared_tasks:
            instance_id = str(task.get("instance_id"))
            row = existing_by_id.get(instance_id)
            if (
                row is not None
                and row.get("oracle_cache_key") == oracle_setup_cache_key(task)
                and row.get("harness_mode") == OFFICIAL_IMAGE_HARNESS_MODE
            ):
                records_by_id[instance_id] = row

    reused_count = 0
    executed_count = 0
    selected_total = len(selected_ids)
    selected_index = 0
    paths: dict[str, Path] = {}
    summary: dict[str, Any] = {}
    for task_path, task in prepared_tasks:
        instance_id = str(task.get("instance_id") or task_path.parent.name)
        if instance_id not in selected_ids:
            continue
        selected_index += 1
        cached = records_by_id.get(instance_id)
        if resume and cached is not None and cached.get("setup_valid") is True:
            reused_count += 1
            action = "reused"
            record = cached
        else:
            record = oracle_setup_record_from_metadata(_oracle_metadata(root, task_path, task))
            record["oracle_cache_key"] = oracle_setup_cache_key(task)
            record["harness_mode"] = OFFICIAL_IMAGE_HARNESS_MODE
            records_by_id[instance_id] = record
            executed_count += 1
            action = "executed"
        print(
            f"[{selected_index}/{selected_total}] {action} {instance_id}: "
            f"{record.get('reason', 'unknown')}",
            flush=True,
        )
        paths, summary = _persist_oracle_preflight(
            root,
            prepared_tasks=prepared_tasks,
            records_by_id=records_by_id,
            image_receipt=image_receipt,
            image_receipt_path=image_receipt_path,
            reused_count=reused_count,
            executed_count=executed_count,
            selected_task_count=selected_total,
        )

    if not selected_tasks:  # pragma: no cover - selection rejects this earlier
        raise ValueError("no Multi-SWE tasks selected")
    return paths, summary


def verify_multi_swe_dataset(data_root: str | Path) -> dict[str, Any]:
    """Require admitted data, immutable task images, and a passing oracle proof."""

    root = Path(data_root)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing Multi-SWE data manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("kind") != DATASET_KIND:
        raise ValueError(f"unexpected Multi-SWE dataset kind in {manifest_path}")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported Multi-SWE dataset schema in {manifest_path}")
    if manifest.get("admitted") is not True:
        raise ValueError(f"Multi-SWE dataset has not passed blocking admission: {manifest_path}")

    oracle_check = manifest.get("oracle_setup_check")
    if (
        not isinstance(oracle_check, dict)
        or oracle_check.get("all_passed") is not True
        or oracle_check.get("complete") is not True
        or oracle_check.get("harness_mode") != OFFICIAL_IMAGE_HARNESS_MODE
        or oracle_check.get("oracle_protocol_version") != ORACLE_PROTOCOL_VERSION
    ):
        raise ValueError(f"Multi-SWE dataset is missing a passing oracle proof: {manifest_path}")
    if oracle_check.get("correct_answer_source") != "fix_patch":
        raise ValueError(f"unexpected Multi-SWE correct-answer source in {manifest_path}")

    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    for key in ("eval", "oracle_records", "oracle_summary", "sandbox_images"):
        relative_path = files.get(key)
        if not isinstance(relative_path, str) or not (root / relative_path).is_file():
            raise ValueError(f"missing Multi-SWE dataset artifact {key!r} under {root}")

    oracle_summary = json.loads((root / files["oracle_summary"]).read_text(encoding="utf-8"))
    for key in (
        "all_passed",
        "complete",
        "expected_task_count",
        "task_count",
        "passed_count",
        "correct_answer_source",
        "harness_mode",
        "oracle_protocol_version",
    ):
        if oracle_summary.get(key) != oracle_check.get(key):
            raise ValueError(f"Multi-SWE oracle summary mismatch for {key!r} in {manifest_path}")
    oracle_records = _read_jsonl(root / files["oracle_records"])
    if len(oracle_records) != oracle_check.get("task_count") or not all(
        record.get("setup_valid") is True for record in oracle_records
    ):
        raise ValueError(f"Multi-SWE oracle records do not prove admission in {manifest_path}")
    records_by_id = {
        str(record.get("instance_id") or record.get("task_id")): record for record in oracle_records
    }

    image_receipt = json.loads((root / files["sandbox_images"]).read_text(encoding="utf-8"))
    if image_receipt.get("kind") != SANDBOX_IMAGE_RECEIPT_KIND:
        raise ValueError(f"invalid Multi-SWE sandbox-image receipt under {root}")

    tasks = load_prepared_multi_swe_tasks(root)
    if oracle_check.get("task_count") != len(tasks):
        raise ValueError(f"Multi-SWE oracle/task-count mismatch in {manifest_path}")
    override = os.environ.get(SANDBOX_IMAGE_ENV, "").strip()
    if override:
        if image_receipt.get("mode") != "override" or image_receipt.get("override") != override:
            raise ValueError(
                f"Multi-SWE sandbox-image override does not match admission in {manifest_path}"
            )
    else:
        if image_receipt.get("mode") != "official-per-task":
            raise ValueError(
                f"Multi-SWE data was admitted with a debug image override: {manifest_path}"
            )
        for task_path, task in tasks:
            expected_image = official_multi_swe_sandbox_image(
                task.get("org"), task.get("repo"), task.get("number")
            )
            if task.get("schema_version") != SCHEMA_VERSION:
                raise ValueError(f"unsupported Multi-SWE task schema in {task_path}")
            if task.get("sandbox_image") != expected_image:
                raise ValueError(f"unexpected Multi-SWE sandbox image in {task_path}")
            instance_id = str(task.get("instance_id"))
            record = records_by_id.get(instance_id)
            if record is None or record.get("oracle_cache_key") != oracle_setup_cache_key(task):
                raise ValueError(
                    f"stale Multi-SWE oracle record for {instance_id} in {manifest_path}"
                )
            resolved_image = task.get("sandbox_image_digest")
            if not isinstance(resolved_image, str) or not (
                "@sha256:" in resolved_image or resolved_image.startswith("sha256:")
            ):
                raise ValueError(f"missing immutable Multi-SWE sandbox image in {task_path}")
    return dict(oracle_check)


def _eval_row(
    row: dict[str, Any],
    *,
    harness: MultiSweRepoHarness,
    instance_id: str,
    task_path: str,
) -> dict[str, Any]:
    return {
        "prompt": build_prompt(row, harness=harness, instance_id=instance_id),
        "label": f"cpp/{instance_id}",
        "task_id": instance_id,
        "problem_id": instance_id,
        "split": "eval",
        "metadata": {
            "benchmark": BENCHMARK,
            "data_source": DATA_SOURCE,
            "language": LANGUAGE,
            "org": harness.org,
            "repo": harness.repo,
            "repo_full_name": harness.repo_full_name,
            "instance_id": instance_id,
            "number": row.get("number"),
            "sandbox_image": official_multi_swe_sandbox_image(
                harness.org, harness.repo, row.get("number")
            ),
            "base_ref": base_ref_from_row(row),
            "task_path": task_path,
        },
    }


def build_prompt(
    row: dict[str, Any],
    *,
    harness: MultiSweRepoHarness,
    instance_id: str,
    max_body_chars: int = 12000,
    max_issue_chars: int = 12000,
) -> str:
    title = str(row.get("title") or "").strip()
    body = _truncate(str(row.get("body") or "").strip(), max_body_chars)
    issues = _resolved_issues_text(row.get("resolved_issues"), max_chars=max_issue_chars)
    base_ref = base_ref_from_row(row) or "not provided"
    parts = [
        "You are fixing a C++ issue from Multi-SWE-bench mini.",
        f"Repository: `{harness.repo_full_name}`",
        f"Instance: `{instance_id}`",
        f"Base ref: `{base_ref}`",
    ]
    if title:
        parts.append(f"Title:\n{title}")
    if body:
        parts.append(f"Issue or pull request body:\n{body}")
    if issues:
        parts.append(f"Resolved issue context:\n{issues}")
    parts.append(_output_contract())
    return "\n\n".join(parts).strip()


def _resolved_issues_text(value: object, *, max_chars: int) -> str:
    if isinstance(value, list):
        text = "\n\n".join(str(item).strip() for item in value if str(item).strip())
    elif isinstance(value, str):
        text = value.strip()
    else:
        text = ""
    return _truncate(text, max_chars)


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n[truncated]"


def _output_contract() -> str:
    return """Return exactly one unified diff patch and nothing else.

Use this exact shape:

```diff
diff --git a/path/file.cpp b/path/file.cpp
...
```

Do not include explanations or prose outside the diff block.
Do not edit tests, examples, docs, build files, CI files, or generated files."""


def parse_patch_response(response: str) -> str:
    """Parse a strict single fenced unified-diff response."""

    if not response.strip():
        raise MultiSweResponseError("invalid_format", "empty response")
    blocks = list(_iter_fenced_blocks(response))
    if len(blocks) != 1:
        raise MultiSweResponseError("invalid_format", "expected exactly one fenced diff block")
    block = blocks[0]
    if response[: block["start"]].strip() or response[block["end"] :].strip():
        raise MultiSweResponseError("invalid_format", "unexpected prose outside fenced diff block")
    if block["info"].strip().lower() not in ALLOWED_DIFF_FENCE_LANGS:
        raise MultiSweResponseError("invalid_format", "expected a ```diff fenced block")
    return _validated_patch_text(block["body"])


def recover_patch_response(response: str) -> str:
    """Best-effort patch parser for diagnostic-only recovery."""

    stripped = response.strip()
    if not stripped:
        raise MultiSweResponseError("invalid_format", "empty response")
    blocks = list(_iter_fenced_blocks(response))
    if len(blocks) == 1 and blocks[0]["info"].strip().lower() in RECOVERABLE_DIFF_FENCE_LANGS:
        return _validated_patch_text(blocks[0]["body"])
    if stripped.startswith("diff --git ") or stripped.startswith("--- "):
        return _validated_patch_text(stripped)
    raise MultiSweResponseError("invalid_format", "no recoverable unified diff")


def _validated_patch_text(patch: str) -> str:
    normalized = patch.strip()
    if not normalized:
        raise MultiSweResponseError("invalid_format", "empty patch")
    if "GIT binary patch" in normalized or re.search(r"^Binary files ", normalized, re.MULTILINE):
        raise MultiSweResponseError("invalid_format", "binary patches are not supported")
    if not extract_patch_paths(normalized):
        raise MultiSweResponseError("invalid_format", "patch has no file paths")
    return normalized.rstrip() + "\n"


def extract_patch_paths(patch: str) -> tuple[str, ...]:
    paths: list[str] = []
    for left, right in _DIFF_GIT_RE.findall(patch):
        for raw in (left, right):
            normalized = _patch_header_path(raw)
            if normalized is not None:
                paths.append(normalized)
    for raw in _DIFF_FILE_RE.findall(patch):
        normalized = _patch_header_path(raw)
        if normalized is not None:
            paths.append(normalized)
    return tuple(dict.fromkeys(paths))


def _patch_header_path(value: str) -> str | None:
    cleaned = value.strip().strip('"').split("\t", 1)[0].strip()
    if cleaned in {"/dev/null", "dev/null"}:
        return None
    if cleaned.startswith("a/") or cleaned.startswith("b/"):
        cleaned = cleaned[2:]
    return _normalize_relative_path(cleaned)


def _normalize_relative_path(value: str) -> str:
    cleaned = value.strip().replace("\\", "/")
    path = PurePosixPath(cleaned)
    if not cleaned or path.is_absolute() or ".." in path.parts:
        raise MultiSweResponseError("invalid_files", f"unsafe relative path: {value!r}")
    return path.as_posix()


def preflight_patch_paths(patch: str, task: dict[str, Any]) -> tuple[str, ...]:
    paths = extract_patch_paths(patch)
    if not paths:
        raise MultiSweResponseError("invalid_format", "patch has no file paths")
    test_patch_paths = set(extract_patch_paths(str(task.get("test_patch") or "")))
    for rel_path in paths:
        if rel_path in test_patch_paths:
            raise MultiSweResponseError("invalid_files", f"patch edits test-patch path: {rel_path}")
        if path_is_forbidden(rel_path):
            raise MultiSweResponseError("invalid_files", f"forbidden file edit: {rel_path}")
    return paths


def path_is_forbidden(rel_path: str) -> bool:
    path = PurePosixPath(_normalize_relative_path(rel_path))
    parts = [part.lower() for part in path.parts]
    basename = parts[-1]
    stem = PurePosixPath(basename).stem.lower()
    suffix = PurePosixPath(basename).suffix.lower()
    if any(part in FORBIDDEN_DIR_NAMES for part in parts[:-1]):
        return True
    if basename in FORBIDDEN_BASENAMES:
        return True
    if "test" in stem or stem.startswith("bench") or "benchmark" in stem:
        return True
    if suffix not in SOURCE_EXTENSIONS:
        return True
    return False


def _iter_fenced_blocks(text: str) -> Iterable[dict[str, Any]]:
    cursor = 0
    while True:
        start = text.find("```", cursor)
        if start == -1:
            return
        info_end = text.find("\n", start + 3)
        if info_end == -1:
            return
        end = text.find("\n```", info_end + 1)
        if end == -1:
            return
        yield {
            "start": start,
            "end": end + 4,
            "info": text[start + 3 : info_end].strip(),
            "body": text[info_end + 1 : end],
        }
        cursor = end + 4


async def reward_func(
    args: Any, sample: Any, **_kwargs: Any
) -> dict[str, Any] | list[dict[str, Any]]:
    """SLIME custom reward hook for one Multi-SWE sample or a batch."""

    if isinstance(sample, list):
        return [await reward_func(args, item) for item in sample]
    return _score_sample(sample)


def _score_sample(sample: Any) -> dict[str, Any]:
    metadata = _sample_metadata(sample)
    task_path = metadata.get("task_path")
    if not task_path:
        return _record(sample, metadata, score=-1.0, reason="missing_task_path")
    try:
        task = load_task_from_metadata(metadata)
    except Exception as exc:  # noqa: BLE001 - protects rollout workers from data bugs
        return _record(sample, metadata, score=-0.5, reason="harness_error", exception=str(exc))

    response = _sample_response(sample)
    try:
        patch = parse_patch_response(response)
        preflight_patch_paths(patch, task)
    except MultiSweResponseError as exc:
        record = _record(
            sample,
            metadata,
            score=-1.0,
            reason=exc.reason,
            exception=str(exc),
            format_valid=exc.reason != "invalid_format",
            task=task,
        )
        if exc.reason == "invalid_format":
            return _attach_recovery_diagnostics(record, task, sample=sample, response=response)
        return record
    except Exception as exc:  # noqa: BLE001 - diagnostic path must not fail rollout workers
        record = _record(
            sample,
            metadata,
            score=-1.0,
            reason="invalid_format",
            exception=str(exc),
            format_valid=False,
            task=task,
        )
        return _attach_recovery_diagnostics(record, task, sample=sample, response=response)

    try:
        result = run_multi_swe_tests(task, patch)
        return _record_from_test_result(
            sample, metadata, task, result, patch_bytes=len(patch.encode())
        )
    except MultiSweResponseError as exc:
        return _record(
            sample, metadata, score=-1.0, reason=exc.reason, exception=str(exc), task=task
        )
    except Exception as exc:  # pragma: no cover - guards real rollout workers
        return _record(
            sample, metadata, score=-0.5, reason="harness_error", exception=str(exc), task=task
        )


def _attach_recovery_diagnostics(
    record: dict[str, Any],
    task: dict[str, Any],
    *,
    sample: Any,
    response: str,
) -> dict[str, Any]:
    try:
        patch = recover_patch_response(response)
        preflight_patch_paths(patch, task)
    except MultiSweResponseError as exc:
        record["recovered_reason"] = exc.reason
        record["recovered_exception"] = str(exc)
        return record
    except Exception as exc:  # noqa: BLE001
        record["recovered_reason"] = "invalid_format"
        record["recovered_exception"] = str(exc)
        return record

    record["recovered_format"] = True
    try:
        result = run_multi_swe_tests(task, patch)
    except MultiSweResponseError as exc:
        record["recovered_reason"] = exc.reason
        record["recovered_exception"] = str(exc)
        record["recovered_patch_bytes"] = len(patch.encode())
        return record
    except Exception as exc:  # pragma: no cover
        record["recovered_reason"] = "harness_error"
        record["recovered_exception"] = str(exc)
        record["recovered_patch_bytes"] = len(patch.encode())
        return record

    record.update(_recovered_fields_from_test_result(result, patch_bytes=len(patch.encode())))
    record["recovered_response"] = _sample_response(sample)
    return record


def load_task_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    task_path = str(metadata.get("task_path") or "")
    path = _resolve_task_path(task_path, metadata=metadata)
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_task_path(task_path: str, *, metadata: dict[str, Any]) -> Path:
    path = Path(task_path)
    if path.is_absolute():
        return path
    roots = [metadata.get("task_root"), os.environ.get(DEFAULT_DATA_ROOT_ENV), Path.cwd()]
    for root in roots:
        if not root:
            continue
        candidate = Path(root) / path
        if candidate.exists():
            return candidate
    return Path.cwd() / path


def run_multi_swe_tests(task: dict[str, Any], patch: str) -> MultiSweTestResult:
    """Run standard tasks in their prepared official instance image."""

    repo_harness_for_task(task)
    timeout_s = int(os.environ.get(TEST_TIMEOUT_ENV, str(DEFAULT_TEST_TIMEOUT_SECONDS)))
    if not os.environ.get(SANDBOX_IMAGE_ENV, "").strip():
        return run_official_instance_tests(task, patch, timeout_s=timeout_s)
    return _run_multi_swe_tests_from_checkout(task, patch, timeout_s=timeout_s)


def _official_instance_script(
    task: dict[str, Any],
    harness: MultiSweRepoHarness,
    *,
    timeout_s: int,
) -> str:
    repo_dir = f"/home/{harness.repo}"
    base_ref = str(task.get("base_ref") or "").strip()
    expected_test_patch_sha = _sha256_text(task.get("test_patch"))
    quoted_repo = shlex.quote(repo_dir)
    quoted_base = shlex.quote(base_ref)
    return f"""
set -euo pipefail
repo_dir={quoted_repo}
if [ ! -d "$repo_dir/.git" ] || [ ! -f /home/test.patch ] || [ ! -f /home/fix-run.sh ]; then
  echo W8_OFFICIAL_IMAGE_CONTRACT_ERROR
  exit {_OFFICIAL_CONTRACT_ERROR}
fi
actual_head="$(git -C "$repo_dir" rev-parse HEAD)"
expected_head="$(git -C "$repo_dir" rev-parse {quoted_base}^{{commit}} 2>/dev/null || true)"
if [ -z "$expected_head" ] || [ "$actual_head" != "$expected_head" ]; then
  echo "W8_OFFICIAL_IMAGE_BASE_MISMATCH expected=$expected_head actual=$actual_head"
  exit {_OFFICIAL_CONTRACT_ERROR}
fi
actual_test_patch_sha="$(sha256sum /home/test.patch | awk '{{print $1}}')"
if [ "$actual_test_patch_sha" != "{expected_test_patch_sha}" ]; then
  echo W8_OFFICIAL_IMAGE_TEST_PATCH_MISMATCH
  exit {_TRUSTED_PATCH_ERROR}
fi
if [ -s /home/test.patch ]; then
  if ! git -C "$repo_dir" apply --check --whitespace=nowarn /home/test.patch; then
    echo W8_TRUSTED_TEST_PATCH_APPLY_ERROR
    exit {_TRUSTED_PATCH_ERROR}
  fi
  if ! git -C "$repo_dir" apply --check --whitespace=nowarn /home/test.patch /home/fix.patch; then
    echo W8_CANDIDATE_PATCH_APPLY_ERROR
    exit {_CANDIDATE_PATCH_ERROR}
  fi
elif ! git -C "$repo_dir" apply --check --whitespace=nowarn /home/fix.patch; then
  echo W8_CANDIDATE_PATCH_APPLY_ERROR
  exit {_CANDIDATE_PATCH_ERROR}
fi
timeout {timeout_s}s bash /home/fix-run.sh
""".strip()


def _official_multi_swe_docker_args(
    patch_path: Path,
    *,
    image: str,
    memory: str = DEFAULT_MEMORY,
) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--cpus",
        "2",
        "--memory",
        memory,
        "--pids-limit",
        "256",
        "--tmpfs",
        "/tmp:rw,nosuid,size=512m,mode=1777",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "-v",
        f"{patch_path.resolve()}:/home/fix.patch:ro",
        image,
    ]


def run_official_instance_tests(
    task: dict[str, Any],
    patch: str,
    *,
    timeout_s: int | None = None,
) -> MultiSweTestResult:
    """Grade in the image-prepared checkout, build tree, and offline assets."""

    harness = repo_harness_for_task(task)
    timeout = timeout_s or int(os.environ.get(TEST_TIMEOUT_ENV, str(DEFAULT_TEST_TIMEOUT_SECONDS)))
    image = sandbox_image_reference_for_task(task)
    image_id = str(task.get("sandbox_image_id") or "").strip() or None
    with TemporaryDirectory(prefix="w8-multi-swe-patch-") as scratch_dir:
        patch_path = Path(scratch_dir) / "fix.patch"
        patch_path.write_text(patch, encoding="utf-8")
        command = _official_multi_swe_docker_args(patch_path, image=image) + [
            "bash",
            "-lc",
            _official_instance_script(task, harness, timeout_s=timeout),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout + 30,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            logs = ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip()
            return MultiSweTestResult(
                returncode=None,
                logs=logs,
                timeout=True,
                sandbox_image=image,
                sandbox_image_id=image_id,
            )

    logs = _logs(result)
    tests_collected = _ctest_tests_collected(logs)
    no_tests_collected = _ctest_collected_no_tests(
        logs,
        returncode=result.returncode,
        tests_collected=tests_collected,
    )
    contract_error = result.returncode in {_OFFICIAL_CONTRACT_ERROR, _TRUSTED_PATCH_ERROR}
    patch_apply_error = result.returncode == _CANDIDATE_PATCH_ERROR
    return MultiSweTestResult(
        returncode=result.returncode,
        logs=logs,
        timeout=result.returncode == 124,
        harness_error=contract_error or no_tests_collected,
        patch_apply_error=patch_apply_error,
        no_tests_collected=no_tests_collected,
        tests_collected=tests_collected,
        sandbox_image=image,
        sandbox_image_id=image_id,
    )


def _run_multi_swe_tests_from_checkout(
    task: dict[str, Any],
    patch: str,
    *,
    timeout_s: int,
) -> MultiSweTestResult:
    """Legacy generic-image debugging path; standard evaluation never uses it."""

    harness = repo_harness_for_task(task)
    clone_timeout_s = int(os.environ.get(CLONE_TIMEOUT_ENV, str(DEFAULT_CLONE_TIMEOUT_SECONDS)))
    with TemporaryDirectory(prefix="w8-multi-swe-cpp-") as scratch_dir:
        repo_dir = Path(scratch_dir) / "repo"
        clone = clone_repository(task, harness, repo_dir, timeout_s=clone_timeout_s)
        if clone.returncode != 0:
            return MultiSweTestResult(
                returncode=clone.returncode, logs=_logs(clone), harness_error=True
            )
        checkout = checkout_base_ref(task, repo_dir, timeout_s=clone_timeout_s)
        if checkout.returncode != 0:
            return MultiSweTestResult(
                returncode=checkout.returncode, logs=_logs(checkout), harness_error=True
            )
        test_patch = str(task.get("test_patch") or "")
        if test_patch.strip():
            applied = apply_patch_to_repo(repo_dir, test_patch, timeout_s=clone_timeout_s)
            if applied.returncode != 0:
                return MultiSweTestResult(
                    returncode=applied.returncode, logs=_logs(applied), harness_error=True
                )
        checked = check_patch_in_repo(repo_dir, patch, timeout_s=clone_timeout_s)
        if checked.returncode != 0:
            return MultiSweTestResult(
                returncode=checked.returncode,
                logs=_logs(checked),
                patch_apply_error=True,
            )
        applied = apply_patch_to_repo(repo_dir, patch, timeout_s=clone_timeout_s)
        if applied.returncode != 0:
            return MultiSweTestResult(
                returncode=applied.returncode,
                logs=_logs(applied),
                patch_apply_error=True,
            )
        return run_repository_tests(repo_dir, harness, task=task, timeout_s=timeout_s)


def clone_repository(
    task: dict[str, Any],
    harness: MultiSweRepoHarness,
    repo_dir: Path,
    *,
    timeout_s: int,
) -> subprocess.CompletedProcess[str]:
    cache_root = os.environ.get(REPO_CACHE_ENV)
    if cache_root:
        cached = Path(cache_root) / harness.cache_name
        if cached.exists():
            shutil.copytree(cached, repo_dir)
            return subprocess.CompletedProcess(["copytree", str(cached), str(repo_dir)], 0, "", "")
    command = ["git", "clone", "--no-tags", harness.git_url, str(repo_dir)]
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout_s, check=False)


def checkout_base_ref(
    task: dict[str, Any],
    repo_dir: Path,
    *,
    timeout_s: int,
) -> subprocess.CompletedProcess[str]:
    base_ref = task.get("base_ref")
    if not isinstance(base_ref, str) or not base_ref.strip():
        return subprocess.CompletedProcess(["git", "checkout"], 0, "", "")
    command = ["git", "-C", str(repo_dir), "checkout", base_ref.strip()]
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout_s, check=False)


def check_patch_in_repo(
    repo_dir: Path,
    patch: str,
    *,
    timeout_s: int,
) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(repo_dir), "apply", "--check", "--whitespace=nowarn", "-"]
    return subprocess.run(
        command, input=patch, capture_output=True, text=True, timeout=timeout_s, check=False
    )


def apply_patch_to_repo(
    repo_dir: Path,
    patch: str,
    *,
    timeout_s: int,
) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(repo_dir), "apply", "--whitespace=nowarn", "-"]
    return subprocess.run(
        command, input=patch, capture_output=True, text=True, timeout=timeout_s, check=False
    )


def run_repository_tests(
    repo_dir: str | Path,
    harness: MultiSweRepoHarness,
    *,
    task: dict[str, Any],
    timeout_s: int | None = None,
) -> MultiSweTestResult:
    timeout = timeout_s or int(os.environ.get(TEST_TIMEOUT_ENV, str(DEFAULT_TEST_TIMEOUT_SECONDS)))
    image = sandbox_image_reference_for_task(task)
    image_id = str(task.get("sandbox_image_id") or "").strip() or None
    repo_path = Path(repo_dir).resolve()
    workdir = PurePosixPath("/work") / repo_path.name
    command = _multi_swe_docker_args(repo_path.parent, workdir=workdir.as_posix(), image=image) + [
        "bash",
        "-lc",
        f"timeout {timeout}s bash -lc {shlex.quote(harness.test_command)}",
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout + 30, check=False
        )
    except subprocess.TimeoutExpired as exc:
        logs = ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip()
        return MultiSweTestResult(
            returncode=None,
            logs=logs,
            timeout=True,
            sandbox_image=image,
            sandbox_image_id=image_id,
        )
    logs = _logs(result)
    tests_collected = _ctest_tests_collected(logs)
    no_tests_collected = _ctest_collected_no_tests(
        logs,
        returncode=result.returncode,
        tests_collected=tests_collected,
    )
    return MultiSweTestResult(
        returncode=result.returncode,
        logs=logs,
        timeout=result.returncode == 124,
        harness_error=no_tests_collected,
        no_tests_collected=no_tests_collected,
        tests_collected=tests_collected,
        sandbox_image=image,
        sandbox_image_id=image_id,
    )


def _ctest_tests_collected(logs: str) -> int | None:
    matches = _CTEST_TOTAL_RE.findall(logs)
    return int(matches[-1]) if matches else None


def _ctest_collected_no_tests(
    logs: str,
    *,
    returncode: int,
    tests_collected: int | None,
) -> bool:
    lowered = logs.lower()
    if "no tests were found" in lowered or tests_collected == 0:
        return True
    return returncode == 0 and tests_collected is None


def _multi_swe_docker_args(
    mount_root: str | Path,
    *,
    workdir: str,
    image: str = DEFAULT_MULTI_SWE_SANDBOX_IMAGE,
    memory: str = DEFAULT_MEMORY,
) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--network",
        "none",
        "--cpus",
        "2",
        "--memory",
        memory,
        "--pids-limit",
        "256",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,size=512m,mode=1777",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "-v",
        f"{Path(mount_root).resolve()}:/work:rw",
        "-w",
        workdir,
        image,
    ]


def _logs(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part for part in (result.stdout, result.stderr) if part)


def _record_from_test_result(
    sample: Any,
    metadata: dict[str, Any],
    task: dict[str, Any],
    result: MultiSweTestResult,
    *,
    patch_bytes: int,
) -> dict[str, Any]:
    if result.passed:
        record = _record(
            sample,
            metadata,
            task=task,
            score=1.0,
            reason="passed",
            tests_passed_count=result.tests_collected or 1,
            tests_failed_count=0,
        )
    elif result.patch_apply_error:
        record = _record(sample, metadata, task=task, score=-0.75, reason="patch_apply_error")
    elif result.no_tests_collected:
        record = _record(sample, metadata, task=task, score=-0.5, reason="no_tests_collected")
    elif result.harness_error:
        record = _record(sample, metadata, task=task, score=-0.5, reason="harness_error")
    elif result.timeout:
        record = _record(sample, metadata, task=task, score=-0.5, reason="timeout", timeout=True)
    elif _looks_like_compile_error(result.logs):
        record = _record(
            sample, metadata, task=task, score=-0.5, reason="compile_error", compile_error=True
        )
    else:
        record = _record(
            sample,
            metadata,
            task=task,
            score=0.0,
            reason="tests_failed",
            tests_passed_count=0,
            tests_failed_count=1,
        )
    record.update(
        {
            "patch_bytes": patch_bytes,
            "tests_collected": result.tests_collected,
            "no_tests_collected": result.no_tests_collected,
            "sandbox_image": result.sandbox_image,
            "sandbox_image_id": result.sandbox_image_id,
        }
    )
    if _include_logs() and result.logs:
        record["logs"] = result.logs
    elif result.logs:
        record["log_excerpt"] = result.logs[-2000:]
    return record


def _recovered_fields_from_test_result(
    result: MultiSweTestResult, *, patch_bytes: int
) -> dict[str, Any]:
    if result.passed:
        fields = {
            "recovered_reason": "passed",
            "recovered_tests_passed_count": result.tests_collected or 1,
            "recovered_tests_failed_count": 0,
        }
    elif result.patch_apply_error:
        fields = {"recovered_reason": "patch_apply_error"}
    elif result.no_tests_collected:
        fields = {"recovered_reason": "no_tests_collected"}
    elif result.harness_error:
        fields = {"recovered_reason": "harness_error"}
    elif result.timeout:
        fields = {"recovered_reason": "timeout", "recovered_timeout": True}
    elif _looks_like_compile_error(result.logs):
        fields = {"recovered_reason": "compile_error", "recovered_compile_error": True}
    else:
        fields = {
            "recovered_reason": "tests_failed",
            "recovered_tests_passed_count": 0,
            "recovered_tests_failed_count": 1,
        }
    fields["recovered_all_tests_pass"] = fields.get("recovered_reason") == "passed"
    fields["recovered_patch_bytes"] = patch_bytes
    fields["recovered_tests_collected"] = result.tests_collected
    fields["recovered_no_tests_collected"] = result.no_tests_collected
    fields["recovered_sandbox_image"] = result.sandbox_image
    if _include_logs() and result.logs:
        fields["recovered_logs"] = result.logs
    elif result.logs:
        fields["recovered_log_excerpt"] = result.logs[-2000:]
    return fields


def _looks_like_compile_error(logs: str) -> bool:
    lowered = logs.lower()
    return any(needle in lowered for needle in _COMPILE_ERROR_NEEDLES)


def _record(
    sample: Any,
    metadata: dict[str, Any],
    *,
    score: float,
    reason: str,
    task: dict[str, Any] | None = None,
    exception: str | None = None,
    format_valid: bool = True,
    compile_error: bool = False,
    timeout: bool = False,
    tests_passed_count: int = 0,
    tests_failed_count: int = 0,
) -> dict[str, Any]:
    task = task or {}
    org = metadata.get("org") or task.get("org")
    repo = metadata.get("repo") or task.get("repo")
    instance_id = metadata.get("instance_id") or task.get("instance_id") or metadata.get("task_id")
    record = {
        "score": score,
        "reward": score,
        "reason": reason,
        "task_id": metadata.get("task_id") or instance_id,
        "problem_id": metadata.get("problem_id") or instance_id,
        "split": metadata.get("split", "eval"),
        "sample_index": _sample_index(sample),
        "rollout_id": getattr(sample, "rollout_id", None),
        "response": _sample_response(sample),
        "benchmark": BENCHMARK,
        "data_source": DATA_SOURCE,
        "language": LANGUAGE,
        "org": org,
        "repo": repo,
        "repo_full_name": metadata.get("repo_full_name") or task.get("repo_full_name"),
        "instance_id": instance_id,
        "compile_error": compile_error,
        "timeout": timeout,
        "tests_passed_count": tests_passed_count,
        "tests_failed_count": tests_failed_count,
        "tests_collected": None,
        "no_tests_collected": reason == "no_tests_collected",
        "all_tests_pass": tests_passed_count > 0 and tests_failed_count == 0,
        "format_valid": format_valid,
        "invalid_format": reason == "invalid_format",
        "invalid_files": reason == "invalid_files",
        "patch_apply_error": reason == "patch_apply_error",
        "harness_error": reason in {"harness_error", "no_tests_collected"},
        "tests_failed": reason == "tests_failed",
        "patch_bytes": 0,
        "recovered_format": False,
        "recovered_reason": None,
        "recovered_compile_error": False,
        "recovered_timeout": False,
        "recovered_tests_passed_count": 0,
        "recovered_tests_failed_count": 0,
        "recovered_tests_collected": None,
        "recovered_no_tests_collected": False,
        "recovered_all_tests_pass": False,
        "recovered_patch_bytes": 0,
    }
    if exception:
        record["exception"] = exception
    return record


def _include_logs() -> bool:
    return os.environ.get(INCLUDE_LOGS_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _sample_metadata(sample: Any) -> dict[str, Any]:
    metadata = getattr(sample, "metadata", None)
    if isinstance(metadata, dict):
        return metadata
    if isinstance(sample, dict) and isinstance(sample.get("metadata"), dict):
        return sample["metadata"]
    return {}


def _sample_response(sample: Any) -> str:
    if isinstance(sample, dict):
        return str(sample.get("response") or "")
    return str(getattr(sample, "response", "") or "")


def _sample_index(sample: Any) -> int | None:
    value = sample.get("index") if isinstance(sample, dict) else getattr(sample, "index", None)
    return int(value) if isinstance(value, int) else None


def _oracle_setup_check_enabled() -> bool:
    value = os.environ.get(ORACLE_SETUP_CHECK_ENV, "1").strip().lower()
    return value not in {"0", "false", "no", "off", "skip"}


def oracle_setup_records_from_debug_samples(
    samples: Iterable[dict[str, Any]],
    *,
    data_root: str | Path | None = None,
) -> list[dict[str, Any]]:
    records = []
    seen: set[str] = set()
    for sample in samples:
        metadata = dict(_sample_metadata(sample))
        task_path = str(metadata.get("task_path") or "")
        if not task_path:
            continue
        task_key = task_path or str(
            metadata.get("task_id")
            or metadata.get("problem_id")
            or metadata.get("instance_id")
            or ""
        )
        if not task_key or task_key in seen:
            continue
        seen.add(task_key)
        if data_root is not None:
            metadata.setdefault("task_root", str(data_root))
        records.append(oracle_setup_record_from_metadata(metadata))
    return records


def oracle_setup_record_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    record = _oracle_setup_base_record(metadata)
    try:
        task = load_task_from_metadata(metadata)
    except Exception as exc:  # noqa: BLE001 - summary should show data bugs, not hide them
        record.update({"reason": "task_load_error", "exception": str(exc)})
        return record

    record.update(_oracle_setup_task_fields(task))
    record["oracle_cache_key"] = oracle_setup_cache_key(task)
    record["harness_mode"] = OFFICIAL_IMAGE_HARNESS_MODE
    fix_patch = str(task.get("fix_patch") or "")
    record["fix_patch_bytes"] = len(fix_patch.encode())
    if not fix_patch.strip():
        record["reason"] = "missing_fix_patch"
        return record

    try:
        result = run_multi_swe_tests(task, fix_patch)
    except MultiSweResponseError as exc:
        record.update({"reason": exc.reason, "exception": str(exc), "harness_error": True})
        return record
    except Exception as exc:  # noqa: BLE001 - setup proof should be recorded as data
        record.update({"reason": "oracle_exception", "exception": str(exc), "harness_error": True})
        return record

    record.update(_oracle_setup_fields_from_test_result(result))
    return record


def _oracle_setup_base_record(metadata: dict[str, Any]) -> dict[str, Any]:
    instance_id = (
        metadata.get("instance_id") or metadata.get("task_id") or metadata.get("problem_id")
    )
    return {
        "benchmark": BENCHMARK,
        "data_source": DATA_SOURCE,
        "language": LANGUAGE,
        "task_id": metadata.get("task_id") or instance_id,
        "problem_id": metadata.get("problem_id") or instance_id,
        "instance_id": instance_id,
        "org": metadata.get("org"),
        "repo": metadata.get("repo"),
        "repo_full_name": metadata.get("repo_full_name"),
        "task_path": metadata.get("task_path"),
        "correct_answer_source": "fix_patch",
        "setup_valid": False,
        "passed": False,
        "all_tests_pass": False,
        "reason": "not_run",
        "returncode": None,
        "timeout": False,
        "harness_error": False,
        "no_tests_collected": False,
        "tests_collected": None,
        "patch_apply_error": False,
        "compile_error": False,
        "tests_failed": False,
        "sandbox_image": metadata.get("sandbox_image"),
        "sandbox_image_id": None,
        "harness_mode": OFFICIAL_IMAGE_HARNESS_MODE,
        "oracle_cache_key": None,
        "fix_patch_bytes": 0,
    }


def _oracle_setup_task_fields(task: dict[str, Any]) -> dict[str, Any]:
    instance_id = task.get("instance_id")
    return {
        "task_id": instance_id,
        "problem_id": instance_id,
        "instance_id": instance_id,
        "org": task.get("org"),
        "repo": task.get("repo"),
        "repo_full_name": task.get("repo_full_name"),
        "sandbox_image": task.get("sandbox_image"),
        "sandbox_image_digest": task.get("sandbox_image_digest"),
        "sandbox_image_id": task.get("sandbox_image_id"),
    }


def _oracle_setup_fields_from_test_result(result: MultiSweTestResult) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "setup_valid": result.passed,
        "passed": result.passed,
        "all_tests_pass": result.passed,
        "returncode": result.returncode,
        "timeout": result.timeout,
        "harness_error": result.harness_error,
        "no_tests_collected": result.no_tests_collected,
        "tests_collected": result.tests_collected,
        "patch_apply_error": result.patch_apply_error,
        "compile_error": False,
        "tests_failed": False,
    }
    if result.sandbox_image:
        fields["sandbox_image"] = result.sandbox_image
    if result.sandbox_image_id:
        fields["sandbox_image_id"] = result.sandbox_image_id
    if result.passed:
        fields["reason"] = "passed"
    elif result.patch_apply_error:
        fields["reason"] = "patch_apply_error"
    elif result.no_tests_collected:
        fields["reason"] = "no_tests_collected"
    elif result.harness_error:
        fields["reason"] = "harness_error"
    elif result.timeout:
        fields["reason"] = "timeout"
    elif _looks_like_compile_error(result.logs):
        fields["reason"] = "compile_error"
        fields["compile_error"] = True
    else:
        fields["reason"] = "tests_failed"
        fields["tests_failed"] = True
    if _include_logs() and result.logs:
        fields["logs"] = result.logs
    elif result.logs:
        fields["log_excerpt"] = result.logs[-2000:]
    return fields


def aggregate_oracle_setup_records(
    records: Iterable[dict[str, Any]],
    *,
    records_file: str | None = None,
    expected_task_count: int | None = None,
    reused_count: int = 0,
    executed_count: int = 0,
) -> dict[str, Any]:
    rows = list(records)
    passed = [row for row in rows if row.get("setup_valid") is True]
    reason_counts = Counter(str(row.get("reason", "unknown")) for row in rows)
    summary = {
        "enabled": True,
        "blocking": True,
        "phase": "data_preflight",
        "correct_answer_source": "fix_patch",
        "records_file": records_file,
        "task_count": len(rows),
        "passed_count": len(passed),
        "failed_count": len(rows) - len(passed),
        "pass_rate": len(passed) / len(rows) if rows else 0.0,
        "all_passed": bool(rows) and len(passed) == len(rows),
        "reason_counts": dict(sorted(reason_counts.items())),
        "repo_summary": _oracle_repo_summary(rows),
    }
    if expected_task_count is not None:
        missing_count = max(0, expected_task_count - len(rows))
        complete = expected_task_count > 0 and missing_count == 0
        summary.update(
            {
                "expected_task_count": expected_task_count,
                "missing_count": missing_count,
                "complete": complete,
                "reused_count": reused_count,
                "executed_count": executed_count,
                "all_passed": complete and len(passed) == expected_task_count,
            }
        )
    return summary


def _oracle_repo_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_repo[_row_repo(row)].append(row)

    summary: dict[str, dict[str, Any]] = {}
    for repo in sorted(by_repo):
        repo_rows = by_repo[repo]
        passed = [row for row in repo_rows if row.get("setup_valid") is True]
        reason_counts = Counter(str(row.get("reason", "unknown")) for row in repo_rows)
        summary[repo] = {
            "task_count": len(repo_rows),
            "passed_count": len(passed),
            "failed_count": len(repo_rows) - len(passed),
            "pass_rate": len(passed) / len(repo_rows) if repo_rows else 0.0,
            "all_passed": bool(repo_rows) and len(passed) == len(repo_rows),
            "reason_counts": dict(sorted(reason_counts.items())),
        }
    return summary


def score_debug_dump(
    *,
    label: str,
    debug_samples_path: str | Path,
    output_dir: str | Path,
    data_root: str | Path | None = None,
    run_oracle_check: bool | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Path]]:
    samples = load_slime_debug_samples(debug_samples_path)
    records = [record_from_debug_sample(sample, label=label) for sample in samples]
    summary = aggregate_multi_swe_records(records, label=label)
    output = Path(output_dir)
    records_path = output / f"{label}.records.jsonl"
    summary_path = output / f"{label}.summary.json"
    paths = {"records": records_path, "summary": summary_path}
    should_run_oracle_check = (
        _oracle_setup_check_enabled() if run_oracle_check is None else run_oracle_check
    )
    if should_run_oracle_check:
        prepared_records_path = Path(data_root) / ORACLE_RECORDS_FILENAME if data_root else None
        if prepared_records_path is not None and prepared_records_path.is_file():
            oracle_records = _read_jsonl(prepared_records_path)
        else:
            oracle_records = oracle_setup_records_from_debug_samples(samples, data_root=data_root)
        oracle_records_path = output / f"{label}.oracle.records.jsonl"
        _write_jsonl(oracle_records_path, oracle_records)
        paths["oracle_records"] = oracle_records_path
        summary["oracle_setup_check"] = aggregate_oracle_setup_records(
            oracle_records,
            records_file=oracle_records_path.name,
        )
    else:
        summary["oracle_setup_check"] = {
            "enabled": False,
            "correct_answer_source": "fix_patch",
        }
    _write_jsonl(records_path, records)
    write_json(summary_path, summary)
    return records, summary, paths


def record_from_debug_sample(sample: dict[str, Any], *, label: str | None = None) -> dict[str, Any]:
    metadata = sample.get("metadata") if isinstance(sample.get("metadata"), dict) else {}
    stashed = metadata.get("multi_swe_reward_record")
    reward_payload = sample.get("reward")
    if isinstance(stashed, dict):
        record = dict(stashed)
    elif isinstance(reward_payload, dict):
        record = dict(reward_payload)
    else:
        score = float(reward_payload or 0.0)
        record = {
            "score": score,
            "reward": score,
            "reason": metadata.get("reason", "unknown"),
            "task_id": metadata.get("task_id"),
            "problem_id": metadata.get("problem_id"),
            "split": metadata.get("split", "eval"),
        }
    record.setdefault("reward", record.get("score", 0.0))
    record.setdefault("score", record.get("reward", 0.0))
    record.setdefault("task_id", metadata.get("task_id"))
    record.setdefault("problem_id", metadata.get("problem_id"))
    record.setdefault("split", metadata.get("split", "eval"))
    record.setdefault("sample_index", sample.get("index"))
    record.setdefault("rollout_id", sample.get("rollout_id"))
    record.setdefault("response", sample.get("response", ""))
    record.setdefault("benchmark", BENCHMARK)
    record.setdefault("data_source", DATA_SOURCE)
    record.setdefault("language", LANGUAGE)
    record.setdefault("org", metadata.get("org"))
    record.setdefault("repo", metadata.get("repo"))
    record.setdefault("repo_full_name", metadata.get("repo_full_name"))
    record.setdefault("instance_id", metadata.get("instance_id") or metadata.get("task_id"))
    record.setdefault("all_tests_pass", False)
    record.setdefault("invalid_format", record.get("reason") == "invalid_format")
    record.setdefault("invalid_files", record.get("reason") == "invalid_files")
    record.setdefault("patch_apply_error", record.get("reason") == "patch_apply_error")
    record.setdefault("harness_error", record.get("reason") == "harness_error")
    record.setdefault("no_tests_collected", record.get("reason") == "no_tests_collected")
    record.setdefault("tests_collected", None)
    record.setdefault("compile_error", False)
    record.setdefault("timeout", False)
    record.setdefault("tests_failed", record.get("reason") == "tests_failed")
    record.setdefault("recovered_format", False)
    record.setdefault("recovered_reason", None)
    record.setdefault("recovered_compile_error", False)
    record.setdefault("recovered_timeout", False)
    record.setdefault("recovered_no_tests_collected", False)
    record.setdefault("recovered_tests_collected", None)
    record.setdefault("recovered_all_tests_pass", False)
    if label is not None:
        record["label"] = label
    return record


def aggregate_multi_swe_records(records: Iterable[dict[str, Any]], *, label: str) -> dict[str, Any]:
    rows = list(records)
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_task[str(row.get("task_id"))].append(row)
    best_rows = [_best_record(task_rows) for task_rows in by_task.values()]
    task_count = len(best_rows)
    sample_count = len(rows)
    best_rewards = [float(row.get("reward", 0.0)) for row in best_rows]
    sample_rewards = [float(row.get("reward", 0.0)) for row in rows]
    passed = [row for row in best_rows if row.get("all_tests_pass") is True]
    reason_counts = Counter(str(row.get("reason", "unknown")) for row in rows)

    return {
        "label": label,
        "benchmark": BENCHMARK,
        "language": LANGUAGE,
        "task_count": task_count,
        "sample_count": sample_count,
        "samples_per_task_mean": sample_count / task_count if task_count else 0.0,
        "pass_rate": len(passed) / task_count if task_count else 0.0,
        "mean_reward": _mean(best_rewards),
        "mean_best_reward": _mean(best_rewards),
        "mean_sample_reward": _mean(sample_rewards),
        "invalid_format_rate": _reason_rate(rows, "invalid_format"),
        "invalid_files_rate": _reason_rate(rows, "invalid_files"),
        "patch_apply_error_rate": _reason_rate(rows, "patch_apply_error"),
        "harness_error_rate": _reason_rate(rows, "harness_error"),
        "no_tests_collected_rate": _reason_rate(rows, "no_tests_collected"),
        "compile_error_rate": _rate(rows, "compile_error"),
        "timeout_rate": _rate(rows, "timeout"),
        "tests_failed_rate": _reason_rate(rows, "tests_failed"),
        "recovered_format_rate": _rate(rows, "recovered_format"),
        "recovered_pass_rate": _rate(rows, "recovered_all_tests_pass"),
        "recovered_task_pass_rate": _task_any_rate(by_task, "recovered_all_tests_pass"),
        "recovered_compile_error_rate": _rate(rows, "recovered_compile_error"),
        "recovered_timeout_rate": _rate(rows, "recovered_timeout"),
        "reason_counts": dict(sorted(reason_counts.items())),
        "repo_summary": _repo_summary(rows, best_rows),
        "best_records": best_rows,
    }


def _repo_summary(
    rows: list[dict[str, Any]], best_rows: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    sample_by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    best_by_repo: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        sample_by_repo[_row_repo(row)].append(row)
    for row in best_rows:
        best_by_repo[_row_repo(row)].append(row)

    summary: dict[str, dict[str, Any]] = {}
    for repo in sorted(set(sample_by_repo) | set(best_by_repo)):
        repo_samples = sample_by_repo.get(repo, [])
        repo_best = best_by_repo.get(repo, [])
        passed = [row for row in repo_best if row.get("all_tests_pass") is True]
        reason_counts = Counter(str(row.get("reason", "unknown")) for row in repo_samples)
        summary[repo] = {
            "task_count": len(repo_best),
            "sample_count": len(repo_samples),
            "pass_rate": len(passed) / len(repo_best) if repo_best else 0.0,
            "mean_reward": _mean([float(row.get("reward", 0.0)) for row in repo_best]),
            "invalid_format_rate": _reason_rate(repo_samples, "invalid_format"),
            "invalid_files_rate": _reason_rate(repo_samples, "invalid_files"),
            "patch_apply_error_rate": _reason_rate(repo_samples, "patch_apply_error"),
            "harness_error_rate": _reason_rate(repo_samples, "harness_error"),
            "no_tests_collected_rate": _reason_rate(repo_samples, "no_tests_collected"),
            "compile_error_rate": _rate(repo_samples, "compile_error"),
            "timeout_rate": _rate(repo_samples, "timeout"),
            "tests_failed_rate": _reason_rate(repo_samples, "tests_failed"),
            "reason_counts": dict(sorted(reason_counts.items())),
        }
    return summary


def _row_repo(row: dict[str, Any]) -> str:
    repo_full_name = row.get("repo_full_name")
    if isinstance(repo_full_name, str) and repo_full_name:
        return repo_full_name
    return f"{row.get('org')}/{row.get('repo')}"


def _best_record(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(rows, key=lambda row: float(row.get("reward", 0.0)))


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    return sum(1 for row in rows if row.get(key) is True) / len(rows) if rows else 0.0


def _task_any_rate(by_task: dict[str, list[dict[str, Any]]], key: str) -> float:
    if not by_task:
        return 0.0
    return sum(
        1 for task_rows in by_task.values() if any(row.get(key) is True for row in task_rows)
    ) / len(by_task)


def _reason_rate(rows: list[dict[str, Any]], reason: str) -> float:
    return sum(1 for row in rows if row.get("reason") == reason) / len(rows) if rows else 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return path


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            rows.append(row)
    return rows


def multi_swe_sandbox_image_dockerfile() -> str:
    return f"""FROM {BASE_DOCKER_IMAGE}
RUN apt-get update \\
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \\
      ca-certificates cmake git make ninja-build pkg-config python3 \\
    && rm -rf /var/lib/apt/lists/*
"""


def build_multi_swe_sandbox_image_command(
    *, image: str = DEFAULT_MULTI_SWE_SANDBOX_IMAGE
) -> list[str]:
    return ["docker", "build", "-t", image, "-"]


def multi_swe_sandbox_image_build_plan(*, image: str = DEFAULT_MULTI_SWE_SANDBOX_IMAGE) -> str:
    return "\n".join(
        [
            "# Multi-SWE C++ sandbox image build dry run",
            f"{shlex.join(build_multi_swe_sandbox_image_command(image=image))} <<'DOCKERFILE'",
            multi_swe_sandbox_image_dockerfile().rstrip(),
            "DOCKERFILE",
        ]
    )


def build_multi_swe_sandbox_image(
    *, image: str = DEFAULT_MULTI_SWE_SANDBOX_IMAGE
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        build_multi_swe_sandbox_image_command(image=image),
        input=multi_swe_sandbox_image_dockerfile(),
        check=False,
        capture_output=True,
        text=True,
    )


def _build_data_command(args: argparse.Namespace) -> None:
    paths = build_slime_multi_swe_cpp_dataset(
        args.source_root,
        args.out,
        jsonl_path=args.jsonl,
        eval_limit=args.eval_limit,
        profile=args.profile,
        run_id=args.run_id,
        force=args.force,
    )
    print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2, sort_keys=True))


def _preflight_command(args: argparse.Namespace) -> None:
    if args.dry_run:
        tasks = load_prepared_multi_swe_tasks(args.data_root)
        print(
            json.dumps(
                {
                    "data_root": str(Path(args.data_root).resolve()),
                    "task_count": len(tasks),
                    "sandbox_images": selected_multi_swe_sandbox_images(
                        args.data_root,
                        task_ids=args.task_id,
                    ),
                    "pull_images": not args.no_pull,
                    "resume": args.resume,
                    "task_ids": args.task_id or [],
                    "correct_answer_source": "fix_patch",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    paths, summary = run_multi_swe_oracle_preflight(
        args.data_root,
        pull_images=not args.no_pull,
        resume=args.resume,
        task_ids=args.task_id,
    )
    print(
        json.dumps(
            {
                "paths": {key: str(path) for key, path in paths.items()},
                "oracle_setup_check": summary,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not summary["all_passed"]:
        raise SystemExit(2)


def _verify_data_command(args: argparse.Namespace) -> None:
    proof = verify_multi_swe_dataset(args.data_root)
    print(json.dumps(proof, indent=2, sort_keys=True))


def _aggregate_command(args: argparse.Namespace) -> None:
    _records, _summary, paths = score_debug_dump(
        label=args.label,
        debug_samples_path=args.debug_rollout,
        output_dir=args.out,
        data_root=args.data_root,
        run_oracle_check=False if args.skip_oracle_check else None,
    )
    print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2, sort_keys=True))


def _sandbox_image_command(args: argparse.Namespace) -> None:
    if args.dry_run:
        print(multi_swe_sandbox_image_build_plan(image=args.image))
        return
    result = build_multi_swe_sandbox_image(image=args.image)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    raise SystemExit(result.returncode)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_data = subparsers.add_parser(
        "build-data", help="Convert Multi-SWE C++ rows into SLIME JSONL"
    )
    build_data.add_argument("--source-root", required=True)
    build_data.add_argument("--jsonl", default=None)
    build_data.add_argument("--out", required=True)
    build_data.add_argument("--eval-limit", type=int, default=DEFAULT_EVAL_LIMIT)
    build_data.add_argument("--profile", default="moonlight-multi-swe-cpp")
    build_data.add_argument("--run-id", default=None)
    build_data.add_argument("--force", action="store_true")
    build_data.set_defaults(func=_build_data_command)

    preflight = subparsers.add_parser(
        "preflight",
        help="Pull per-task images and require every fix-patch oracle to pass",
    )
    preflight.add_argument("--data-root", required=True)
    preflight.add_argument("--no-pull", action="store_true")
    preflight.add_argument(
        "--resume",
        action="store_true",
        help="Reuse only passing records whose task/image fingerprint still matches",
    )
    preflight.add_argument(
        "--task-id",
        action="append",
        default=None,
        help="Run or refresh one task; repeat for multiple tasks",
    )
    preflight.add_argument("--dry-run", action="store_true")
    preflight.set_defaults(func=_preflight_command)

    verify_data = subparsers.add_parser(
        "verify-data",
        help="Verify blocking Multi-SWE data admission before launching SLIME",
    )
    verify_data.add_argument("--data-root", required=True)
    verify_data.set_defaults(func=_verify_data_command)

    aggregate = subparsers.add_parser(
        "aggregate-debug", help="Aggregate SLIME debug rollout samples"
    )
    aggregate.add_argument("--label", required=True, choices=("base",))
    aggregate.add_argument("--debug-rollout", required=True)
    aggregate.add_argument("--out", required=True)
    aggregate.add_argument("--data-root", default=None)
    aggregate.add_argument("--skip-oracle-check", action="store_true")
    aggregate.set_defaults(func=_aggregate_command)

    sandbox_image = subparsers.add_parser(
        "sandbox-image",
        help="Build the generic debugging image (official per-task images are the default)",
    )
    sandbox_image.add_argument("--image", default=DEFAULT_MULTI_SWE_SANDBOX_IMAGE)
    sandbox_image.add_argument("--dry-run", action="store_true")
    sandbox_image.set_defaults(func=_sandbox_image_command)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main()
