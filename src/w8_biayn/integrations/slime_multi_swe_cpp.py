"""SLIME data and reward bridge for Multi-SWE-bench mini C++ base evaluation."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import time
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
SCHEMA_VERSION = 1
DEFAULT_DATA_ROOT_ENV = "W8_BIAYN_DATA_DIR"
SANDBOX_IMAGE_ENV = "W8_SLIME_MULTI_SWE_SANDBOX_IMAGE"
INCLUDE_LOGS_ENV = "W8_SLIME_MULTI_SWE_INCLUDE_LOGS"
TEST_TIMEOUT_ENV = "W8_SLIME_MULTI_SWE_TEST_TIMEOUT_SECONDS"
REPO_CACHE_ENV = "W8_SLIME_MULTI_SWE_REPO_CACHE"
ORACLE_SETUP_CHECK_ENV = "W8_SLIME_MULTI_SWE_ORACLE_SETUP_CHECK"
DEFAULT_MULTI_SWE_SANDBOX_IMAGE = "w8-biayn-multi-swe-cpp:latest"
DEFAULT_TEST_TIMEOUT_SECONDS = 600
DEFAULT_EVAL_LIMIT = 4
ALLOWED_DIFF_FENCE_LANGS = {"diff", "patch"}
RECOVERABLE_DIFF_FENCE_LANGS = {"", "diff", "patch"}

_DIFF_GIT_RE = re.compile(r"^diff --git\s+(.+?)\s+(.+?)$", re.MULTILINE)
_DIFF_FILE_RE = re.compile(r"^(?:---|\+\+\+)\s+([^\t\n\r]+)", re.MULTILINE)
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

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and not self.timeout and not self.harness_error


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
                "ctest --test-dir build --output-on-failure"
            ),
        ),
        MultiSweRepoHarness(
            org="fmtlib",
            repo="fmt",
            git_url="https://github.com/fmtlib/fmt.git",
            test_command=(
                "cmake -S . -B build -DFMT_TEST=ON -DFMT_DOC=OFF && "
                "cmake --build build --parallel 2 && "
                "ctest --test-dir build --output-on-failure"
            ),
        ),
        MultiSweRepoHarness(
            org="nlohmann",
            repo="json",
            git_url="https://github.com/nlohmann/json.git",
            test_command=(
                "cmake -S . -B build -DJSON_BuildTests=ON && "
                "cmake --build build --parallel 2 && "
                "ctest --test-dir build --output-on-failure"
            ),
        ),
        MultiSweRepoHarness(
            org="simdjson",
            repo="simdjson",
            git_url="https://github.com/simdjson/simdjson.git",
            test_command=(
                "cmake -S . -B build -DSIMDJSON_BUILD_TESTS=ON && "
                "cmake --build build --parallel 2 && "
                "ctest --test-dir build --output-on-failure"
            ),
        ),
        MultiSweRepoHarness(
            org="yhirose",
            repo="cpp-httplib",
            git_url="https://github.com/yhirose/cpp-httplib.git",
            test_command=(
                "cmake -S . -B build -DHTTPLIB_TEST=ON && "
                "cmake --build build --parallel 2 && "
                "ctest --test-dir build --output-on-failure"
            ),
        ),
    )
}


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
    data_path = Path(jsonl_path) if jsonl_path is not None else source / "multi_swe_bench_mini.jsonl"
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
    tasks_root = output / "tasks"
    for row in rows:
        harness = repo_harness_for_row(row)
        if harness is None:  # pragma: no cover - filtered above
            continue
        instance_id = instance_id_for_row(row, harness=harness)
        task_path = tasks_root / safe_task_dir(instance_id) / "task.json"
        task_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(task_path, normalized_task(row, harness=harness, instance_id=instance_id))
        task_rel = task_path.relative_to(output).as_posix()
        eval_rows.append(_eval_row(row, harness=harness, instance_id=instance_id, task_path=task_rel))
        task_paths.append(task_rel)

    paths = {
        "eval": output / "eval" / "cpp.jsonl",
        "manifest": output / "manifest.json",
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
            "allowed_repos": sorted(harness.repo_full_name for harness in REPO_HARNESSES.values()),
            "counts": {
                "eval": len(eval_rows),
                "task_json": len(task_paths),
            },
            "files": {
                "eval": paths["eval"].relative_to(output).as_posix(),
                "tasks": task_paths,
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


async def reward_func(args: Any, sample: Any, **_kwargs: Any) -> dict[str, Any] | list[dict[str, Any]]:
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
        return _record_from_test_result(sample, metadata, task, result, patch_bytes=len(patch.encode()))
    except MultiSweResponseError as exc:
        return _record(sample, metadata, score=-1.0, reason=exc.reason, exception=str(exc), task=task)
    except Exception as exc:  # pragma: no cover - guards real rollout workers
        return _record(sample, metadata, score=-0.5, reason="harness_error", exception=str(exc), task=task)


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
    """Apply test/model patches and run the repository harness in Docker."""

    harness = repo_harness_for_task(task)
    timeout_s = int(os.environ.get(TEST_TIMEOUT_ENV, str(DEFAULT_TEST_TIMEOUT_SECONDS)))
    started = time.monotonic()
    with TemporaryDirectory(prefix="w8-multi-swe-cpp-") as scratch_dir:
        scratch = Path(scratch_dir)
        repo_dir = scratch / "repo"
        clone = clone_repository(task, harness, repo_dir, timeout_s=timeout_s)
        if clone.returncode != 0:
            return MultiSweTestResult(returncode=clone.returncode, logs=_logs(clone), harness_error=True)
        checkout = checkout_base_ref(task, repo_dir, timeout_s=timeout_s)
        if checkout.returncode != 0:
            return MultiSweTestResult(returncode=checkout.returncode, logs=_logs(checkout), harness_error=True)
        test_patch = str(task.get("test_patch") or "")
        if test_patch.strip():
            applied = apply_patch_to_repo(repo_dir, test_patch, timeout_s=timeout_s)
            if applied.returncode != 0:
                return MultiSweTestResult(returncode=applied.returncode, logs=_logs(applied), harness_error=True)
        checked = check_patch_in_repo(repo_dir, patch, timeout_s=timeout_s)
        if checked.returncode != 0:
            return MultiSweTestResult(
                returncode=checked.returncode,
                logs=_logs(checked),
                patch_apply_error=True,
            )
        applied = apply_patch_to_repo(repo_dir, patch, timeout_s=timeout_s)
        if applied.returncode != 0:
            return MultiSweTestResult(
                returncode=applied.returncode,
                logs=_logs(applied),
                patch_apply_error=True,
            )
        remaining_timeout = max(30, int(timeout_s - (time.monotonic() - started)))
        return run_repository_tests(repo_dir, harness, timeout_s=remaining_timeout)


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
    return subprocess.run(command, input=patch, capture_output=True, text=True, timeout=timeout_s, check=False)


def apply_patch_to_repo(
    repo_dir: Path,
    patch: str,
    *,
    timeout_s: int,
) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(repo_dir), "apply", "--whitespace=nowarn", "-"]
    return subprocess.run(command, input=patch, capture_output=True, text=True, timeout=timeout_s, check=False)


def run_repository_tests(
    repo_dir: str | Path,
    harness: MultiSweRepoHarness,
    *,
    timeout_s: int | None = None,
) -> MultiSweTestResult:
    timeout = timeout_s or int(os.environ.get(TEST_TIMEOUT_ENV, str(DEFAULT_TEST_TIMEOUT_SECONDS)))
    image = os.environ.get(SANDBOX_IMAGE_ENV, DEFAULT_MULTI_SWE_SANDBOX_IMAGE)
    repo_path = Path(repo_dir).resolve()
    workdir = PurePosixPath("/work") / repo_path.name
    command = _multi_swe_docker_args(repo_path.parent, workdir=workdir.as_posix(), image=image) + [
        "bash",
        "-lc",
        f"timeout {timeout}s bash -lc {shlex.quote(harness.test_command)}",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout + 30, check=False)
    except subprocess.TimeoutExpired as exc:
        logs = ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip()
        return MultiSweTestResult(returncode=None, logs=logs, timeout=True)
    logs = "\n".join(part for part in (result.stdout, result.stderr) if part)
    return MultiSweTestResult(returncode=result.returncode, logs=logs, timeout=result.returncode == 124)


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
            tests_passed_count=1,
            tests_failed_count=0,
        )
    elif result.patch_apply_error:
        record = _record(sample, metadata, task=task, score=-0.75, reason="patch_apply_error")
    elif result.harness_error:
        record = _record(sample, metadata, task=task, score=-0.5, reason="harness_error")
    elif result.timeout:
        record = _record(sample, metadata, task=task, score=-0.5, reason="timeout", timeout=True)
    elif _looks_like_compile_error(result.logs):
        record = _record(sample, metadata, task=task, score=-0.5, reason="compile_error", compile_error=True)
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
    record["patch_bytes"] = patch_bytes
    if _include_logs() and result.logs:
        record["logs"] = result.logs
    elif result.logs:
        record["log_excerpt"] = result.logs[-2000:]
    return record


def _recovered_fields_from_test_result(result: MultiSweTestResult, *, patch_bytes: int) -> dict[str, Any]:
    if result.passed:
        fields = {
            "recovered_reason": "passed",
            "recovered_tests_passed_count": 1,
            "recovered_tests_failed_count": 0,
        }
    elif result.patch_apply_error:
        fields = {"recovered_reason": "patch_apply_error"}
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
        "all_tests_pass": tests_passed_count > 0 and tests_failed_count == 0,
        "format_valid": format_valid,
        "invalid_format": reason == "invalid_format",
        "invalid_files": reason == "invalid_files",
        "patch_apply_error": reason == "patch_apply_error",
        "harness_error": reason == "harness_error",
        "tests_failed": reason == "tests_failed",
        "patch_bytes": 0,
        "recovered_format": False,
        "recovered_reason": None,
        "recovered_compile_error": False,
        "recovered_timeout": False,
        "recovered_tests_passed_count": 0,
        "recovered_tests_failed_count": 0,
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
            metadata.get("task_id") or metadata.get("problem_id") or metadata.get("instance_id") or ""
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
    instance_id = metadata.get("instance_id") or metadata.get("task_id") or metadata.get("problem_id")
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
        "patch_apply_error": False,
        "compile_error": False,
        "tests_failed": False,
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
    }


def _oracle_setup_fields_from_test_result(result: MultiSweTestResult) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "setup_valid": result.passed,
        "passed": result.passed,
        "all_tests_pass": result.passed,
        "returncode": result.returncode,
        "timeout": result.timeout,
        "harness_error": result.harness_error,
        "patch_apply_error": result.patch_apply_error,
        "compile_error": False,
        "tests_failed": False,
    }
    if result.passed:
        fields["reason"] = "passed"
    elif result.patch_apply_error:
        fields["reason"] = "patch_apply_error"
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
) -> dict[str, Any]:
    rows = list(records)
    passed = [row for row in rows if row.get("setup_valid") is True]
    reason_counts = Counter(str(row.get("reason", "unknown")) for row in rows)
    return {
        "enabled": True,
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
    should_run_oracle_check = _oracle_setup_check_enabled() if run_oracle_check is None else run_oracle_check
    if should_run_oracle_check:
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
    record.setdefault("compile_error", False)
    record.setdefault("timeout", False)
    record.setdefault("tests_failed", record.get("reason") == "tests_failed")
    record.setdefault("recovered_format", False)
    record.setdefault("recovered_reason", None)
    record.setdefault("recovered_compile_error", False)
    record.setdefault("recovered_timeout", False)
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


def _repo_summary(rows: list[dict[str, Any]], best_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
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
    return sum(1 for task_rows in by_task.values() if any(row.get(key) is True for row in task_rows)) / len(by_task)


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

    build_data = subparsers.add_parser("build-data", help="Convert Multi-SWE C++ rows into SLIME JSONL")
    build_data.add_argument("--source-root", required=True)
    build_data.add_argument("--jsonl", default=None)
    build_data.add_argument("--out", required=True)
    build_data.add_argument("--eval-limit", type=int, default=DEFAULT_EVAL_LIMIT)
    build_data.add_argument("--profile", default="moonlight-multi-swe-cpp")
    build_data.add_argument("--run-id", default=None)
    build_data.add_argument("--force", action="store_true")
    build_data.set_defaults(func=_build_data_command)

    aggregate = subparsers.add_parser("aggregate-debug", help="Aggregate SLIME debug rollout samples")
    aggregate.add_argument("--label", required=True, choices=("base",))
    aggregate.add_argument("--debug-rollout", required=True)
    aggregate.add_argument("--out", required=True)
    aggregate.add_argument("--data-root", default=None)
    aggregate.add_argument("--skip-oracle-check", action="store_true")
    aggregate.set_defaults(func=_aggregate_command)

    sandbox_image = subparsers.add_parser("sandbox-image", help="Build or render the Multi-SWE C++ sandbox image")
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
