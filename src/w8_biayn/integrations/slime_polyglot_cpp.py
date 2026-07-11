"""SLIME data and reward bridge for Aider Polyglot C++ base evaluation."""

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
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Any, Callable, Iterable, Sequence

from w8_biayn.cpp_perf.eval import write_json
from w8_biayn.cpp_perf.sandbox import BASE_DOCKER_IMAGE, DEFAULT_MEMORY
from w8_biayn.integrations.slime_cpp_perf import load_slime_debug_samples

DATA_SOURCE = "Aider-AI/polyglot-benchmark"
BENCHMARK = "aider-polyglot"
LANGUAGE = "cpp"
DATASET_KIND = "slime-polyglot-cpp-dataset"
SCHEMA_VERSION = 2
ORACLE_PROTOCOL_VERSION = 1
DEFAULT_DATA_ROOT_ENV = "W8_BIAYN_DATA_DIR"
SANDBOX_IMAGE_ENV = "W8_SLIME_POLYGLOT_SANDBOX_IMAGE"
INCLUDE_LOGS_ENV = "W8_SLIME_POLYGLOT_INCLUDE_LOGS"
TEST_TIMEOUT_ENV = "W8_SLIME_POLYGLOT_TEST_TIMEOUT_SECONDS"
DEFAULT_POLYGLOT_SANDBOX_IMAGE = "w8-biayn-polyglot-cpp:latest"
DEFAULT_TEST_TIMEOUT_SECONDS = 180
DEFAULT_EVAL_LIMIT = 4
DEFAULT_POLYGLOT_PIDS_LIMIT = 2048
ORACLE_CORRECT_ANSWER_SOURCE = "files.example"
GEMINI_SANITY_KIND = "polyglot-gemini-sanity"
GEMINI_SANITY_SCHEMA_VERSION = 1
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_API_KEY_ENV_NAMES = ("GOOGLE_API_KEY", "GEMINI_API_KEY")
POLYGLOT_TEST_SCRIPT = (
    "mkdir -p build && cd build && "
    "cmake -DEXERCISM_RUN_ALL_TESTS=1 -G 'Unix Makefiles' .. && make"
)
ALLOWED_CODE_FENCE_LANGS = {"", "cpp", "c++", "cc", "cxx", "h", "hh", "hpp", "hxx"}
UNCATEGORIZED_CATEGORY = "uncategorized"
_PATH_MENTION_RE = re.compile(
    r"(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:c|cc|cpp|cxx|h|hh|hpp|hxx)\b"
)

# Aider Polyglot ships a curated Exercism subset without the C++ track-level
# concept graph. Keep this map deterministic so eval summaries can drive
# category heatmaps without reclassifying historical runs.
POLYGLOT_CPP_EXERCISE_CATEGORIES: dict[str, tuple[str, ...]] = {
    "all-your-base": ("numeric", "base-conversion", "sequences"),
    "allergies": ("numeric", "bitmasks", "conditionals"),
    "bank-account": ("concurrency", "stateful-objects", "classes"),
    "binary-search-tree": ("data-structures", "trees", "recursion"),
    "circular-buffer": ("data-structures", "stateful-objects", "queues"),
    "clock": ("date-time", "numeric", "operator-overloading"),
    "complex-numbers": ("numeric", "classes", "operator-overloading"),
    "crypto-square": ("strings", "parsing", "matrix"),
    "diamond": ("strings", "pattern-generation"),
    "dnd-character": ("randomness", "numeric", "classes"),
    "gigasecond": ("date-time", "chrono"),
    "grade-school": ("collections", "sorting", "maps"),
    "kindergarten-garden": ("strings", "parsing", "maps"),
    "knapsack": ("algorithms", "dynamic-programming", "optimization"),
    "linked-list": ("data-structures", "pointers", "stateful-objects"),
    "meetup": ("date-time", "calendar-logic"),
    "parallel-letter-frequency": ("concurrency", "strings", "maps"),
    "perfect-numbers": ("numeric", "factorization", "conditionals"),
    "phone-number": ("strings", "parsing", "validation"),
    "queen-attack": ("grid-logic", "conditionals"),
    "robot-name": ("stateful-objects", "randomness", "sets"),
    "space-age": ("numeric", "date-time", "conditionals"),
    "spiral-matrix": ("matrix", "loops", "grid-logic"),
    "sublist": ("sequences", "algorithms"),
    "two-fer": ("strings", "conditionals"),
    "yacht": ("collections", "game-scoring", "conditionals"),
    "zebra-puzzle": ("constraint-solving", "logic-puzzles"),
}


@dataclass(frozen=True)
class PolyglotExercise:
    name: str
    source_path: Path
    blurb: str
    categories: tuple[str, ...]
    solution_files: tuple[str, ...]
    test_files: tuple[str, ...]
    example_files: tuple[str, ...]


@dataclass(frozen=True)
class PolyglotTestResult:
    returncode: int | None
    logs: str
    timeout: bool = False

    @property
    def passed(self) -> bool:
        return self.returncode == 0 and not self.timeout


@dataclass(frozen=True)
class GeminiGeneration:
    text: str
    api_key_source: str
    finish_reason: str | None = None
    usage_metadata: dict[str, Any] | None = None


class PolyglotResponseError(ValueError):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def build_slime_polyglot_cpp_dataset(
    source_root: str | Path,
    output_dir: str | Path,
    *,
    eval_limit: int | None = DEFAULT_EVAL_LIMIT,
    profile: str = "moonlight-polyglot-cpp",
    run_id: str | None = None,
    force: bool = False,
) -> dict[str, Path]:
    """Write SLIME eval JSONL files from Aider Polyglot C++ exercises."""

    source = Path(source_root)
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        if not force:
            raise FileExistsError(f"{output} already exists and is not empty; pass force=True to replace it")
        shutil.rmtree(output)

    exercises = discover_cpp_exercises(source)
    if eval_limit is not None:
        exercises = exercises[:eval_limit]
    if not exercises:
        raise ValueError(f"No Polyglot C++ exercises found under {source}")

    copied_root = output / "tasks" / "cpp" / "exercises" / "practice"
    copied_exercises: list[tuple[PolyglotExercise, Path]] = []
    for exercise in exercises:
        destination = copied_root / exercise.name
        shutil.copytree(exercise.source_path, destination)
        copied_exercises.append((exercise, destination))

    paths = {
        "tasks": copied_root,
        "eval": output / "eval" / "cpp.jsonl",
        "manifest": output / "manifest.json",
        "oracle_records": output / "oracle.records.jsonl",
        "oracle_summary": output / "oracle.summary.json",
    }
    grader_config = polyglot_oracle_grader_config()
    _write_jsonl(paths["oracle_records"], ())
    for exercise, destination in copied_exercises:
        _append_jsonl_record(
            paths["oracle_records"],
            polyglot_oracle_setup_record(
                exercise,
                exercise_dir=destination,
                grader_config=grader_config,
            ),
        )
    oracle_records = _read_jsonl(paths["oracle_records"])
    oracle_summary = aggregate_polyglot_oracle_setup_records(
        oracle_records,
        records_file=paths["oracle_records"].name,
        summary_file=paths["oracle_summary"].name,
    )
    write_json(paths["oracle_summary"], oracle_summary)
    if not oracle_summary["all_passed"]:
        failures = ", ".join(
            f"{record['task_id']}:{record['reason']}"
            for record in oracle_records
            if record.get("setup_valid") is not True
        )
        raise ValueError(
            "Polyglot C++ oracle preflight failed; no eval manifest was admitted. "
            f"Failures: {failures}. Inspect {paths['oracle_records']}"
        )

    oracle_by_exercise = {str(record["exercise"]): record for record in oracle_records}
    rows = [
        _eval_row(
            exercise,
            exercise_path=destination.relative_to(output).as_posix(),
            source_root=source,
            oracle_record=oracle_by_exercise[exercise.name],
        )
        for exercise, destination in copied_exercises
    ]
    _write_jsonl(paths["eval"], rows)
    write_json(
        paths["manifest"],
        {
            "kind": DATASET_KIND,
            "schema_version": SCHEMA_VERSION,
            "admitted": True,
            "data_source": DATA_SOURCE,
            "benchmark": BENCHMARK,
            "language": LANGUAGE,
            "profile": profile,
            "run_id": run_id,
            "source_root": str(source),
            "output_dir": str(output),
            "counts": {
                "eval": len(rows),
                "copied_exercises": len(rows),
                "oracle_checked": oracle_summary["task_count"],
                "oracle_passed": oracle_summary["passed_count"],
            },
            "files": {
                "tasks": paths["tasks"].relative_to(output).as_posix(),
                "eval": paths["eval"].relative_to(output).as_posix(),
                "oracle_records": paths["oracle_records"].relative_to(output).as_posix(),
                "oracle_summary": paths["oracle_summary"].relative_to(output).as_posix(),
            },
            "oracle_setup_check": oracle_summary,
        },
    )
    try:
        validate_polyglot_dataset(output)
    except Exception:
        paths["manifest"].unlink(missing_ok=True)
        paths["eval"].unlink(missing_ok=True)
        raise
    return paths


def discover_cpp_exercises(source_root: str | Path) -> list[PolyglotExercise]:
    """Discover C++ exercises in an Aider Polyglot checkout."""

    source = Path(source_root)
    practice_root = source / "cpp" / "exercises" / "practice"
    if not practice_root.exists():
        practice_root = source
    exercises = []
    for exercise_dir in sorted(path for path in practice_root.iterdir() if path.is_dir()):
        config_path = exercise_dir / ".meta" / "config.json"
        if not config_path.exists():
            continue
        config = json.loads(config_path.read_text(encoding="utf-8"))
        files = config.get("files", {})
        blurb = str(config.get("blurb") or "")
        test_files = _normalize_file_list(files.get("test", []))
        example_files = _normalize_file_list(files.get("example", []))
        solution_files = _normalize_file_list(files.get("solution", []))
        ignored = set(test_files) | set(example_files)
        ignored.update(_metadata_doc_paths(exercise_dir))
        ignored.add("CMakeLists.txt")
        solution_files = tuple(path for path in solution_files if path not in ignored)
        if not solution_files:
            continue
        exercises.append(
            PolyglotExercise(
                name=exercise_dir.name,
                source_path=exercise_dir,
                blurb=blurb,
                categories=categorize_polyglot_cpp_exercise(exercise_dir.name),
                solution_files=solution_files,
                test_files=test_files,
                example_files=example_files,
            )
        )
    return exercises


def categorize_polyglot_cpp_exercise(exercise_name: str) -> tuple[str, ...]:
    """Return stable heatmap categories for a Polyglot C++ exercise slug."""

    categories = POLYGLOT_CPP_EXERCISE_CATEGORIES.get(exercise_name, (UNCATEGORIZED_CATEGORY,))
    return tuple(dict.fromkeys(category for category in categories if category)) or (UNCATEGORIZED_CATEGORY,)


def _metadata_doc_paths(exercise_dir: Path) -> set[str]:
    paths: set[str] = set()
    for root in (exercise_dir / ".meta", exercise_dir / ".docs"):
        if root.exists():
            paths.update(path.relative_to(exercise_dir).as_posix() for path in root.rglob("*") if path.is_file())
    return paths


def _normalize_file_list(values: object) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    output = []
    for value in values:
        if isinstance(value, str):
            output.append(_normalize_relative_path(value))
    return tuple(dict.fromkeys(output))


def _normalize_relative_path(value: str) -> str:
    cleaned = value.strip().replace("\\", "/")
    path = PurePosixPath(cleaned)
    if not cleaned or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe relative path: {value!r}")
    return path.as_posix()


def polyglot_reference_replacements(
    exercise_dir: str | Path,
    *,
    solution_files: Sequence[str],
    example_files: Sequence[str],
) -> tuple[dict[str, str], list[dict[str, str]], list[str]]:
    """Map Exercism `.meta/example.*` files onto editable solution files.

    C++ exercises use at most one editable file per extension. Some references
    are intentionally header-only; their inert `.cpp` starter remains in place.
    """

    exercise_path = Path(exercise_dir)
    normalized_solutions = tuple(_normalize_relative_path(path) for path in solution_files)
    normalized_examples = tuple(_normalize_relative_path(path) for path in example_files)
    if not normalized_examples:
        raise PolyglotResponseError(
            "missing_example_files",
            "metadata.files.example must provide at least one reference implementation",
        )

    solutions_by_suffix: dict[str, list[str]] = defaultdict(list)
    for solution_file in normalized_solutions:
        solutions_by_suffix[PurePosixPath(solution_file).suffix.lower()].append(solution_file)

    replacements: dict[str, str] = {}
    mappings: list[dict[str, str]] = []
    for example_file in normalized_examples:
        example_path = exercise_path / example_file
        if not example_path.is_file():
            raise PolyglotResponseError(
                "missing_example_file",
                f"reference implementation file does not exist: {example_file}",
            )
        suffix = PurePosixPath(example_file).suffix.lower()
        candidates = solutions_by_suffix.get(suffix, [])
        if len(candidates) != 1:
            raise PolyglotResponseError(
                "reference_mapping_error",
                f"expected exactly one solution file for reference {example_file}; found {candidates}",
            )
        solution_file = candidates[0]
        if solution_file in replacements:
            raise PolyglotResponseError(
                "reference_mapping_error",
                f"multiple reference files map to solution file: {solution_file}",
            )
        replacements[solution_file] = example_path.read_text(encoding="utf-8")
        mappings.append({"example_file": example_file, "solution_file": solution_file})

    unmapped = sorted(set(normalized_solutions) - set(replacements))
    return replacements, mappings, unmapped


def _polyglot_sandbox_image_id(image: str) -> str | None:
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", "--format={{.Id}}", image],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    image_id = result.stdout.strip()
    return image_id if result.returncode == 0 and image_id else None


def polyglot_oracle_grader_config(
    *, require_image_id: bool = True
) -> dict[str, Any]:
    """Return the grader inputs that an oracle record must remain bound to."""

    try:
        timeout_seconds = int(
            os.environ.get(TEST_TIMEOUT_ENV, str(DEFAULT_TEST_TIMEOUT_SECONDS))
        )
    except ValueError as exc:
        raise ValueError(f"{TEST_TIMEOUT_ENV} must be an integer") from exc
    if timeout_seconds <= 0:
        raise ValueError(f"{TEST_TIMEOUT_ENV} must be positive")
    sandbox_image = os.environ.get(
        SANDBOX_IMAGE_ENV, DEFAULT_POLYGLOT_SANDBOX_IMAGE
    )
    sandbox_image_id = _polyglot_sandbox_image_id(sandbox_image)
    if require_image_id and sandbox_image_id is None:
        raise ValueError(
            f"Polyglot sandbox image {sandbox_image!r} is unavailable; "
            "build it with the sandbox-image command before preparing or verifying data"
        )
    return {
        "oracle_protocol_version": ORACLE_PROTOCOL_VERSION,
        "sandbox_image": sandbox_image,
        "sandbox_image_id": sandbox_image_id,
        "test_timeout_seconds": timeout_seconds,
        "test_script": POLYGLOT_TEST_SCRIPT,
        "memory": DEFAULT_MEMORY,
        "pids_limit": DEFAULT_POLYGLOT_PIDS_LIMIT,
    }


def polyglot_oracle_input_sha256(
    exercise_dir: str | Path,
    *,
    solution_files: Sequence[str],
    example_files: Sequence[str],
    grader_config: dict[str, Any],
) -> str:
    """Fingerprint the copied task tree and all same-grader oracle inputs."""

    root = Path(exercise_dir)
    if not root.is_dir():
        raise ValueError(f"missing Polyglot exercise directory: {root}")
    digest = hashlib.sha256()
    header = {
        "solution_files": list(solution_files),
        "example_files": list(example_files),
        "grader_config": grader_config,
    }
    digest.update(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
    for path in sorted((item for item in root.rglob("*") if item.is_file())):
        relative = path.relative_to(root).as_posix()
        contents = path.read_bytes()
        digest.update(b"\0path\0" + relative.encode() + b"\0bytes\0")
        digest.update(str(len(contents)).encode() + b"\0" + contents)
    return digest.hexdigest()


def polyglot_oracle_setup_record(
    exercise: PolyglotExercise,
    *,
    exercise_dir: str | Path,
    grader_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one Exercism reference implementation through the model grader."""

    active_grader_config = dict(grader_config or polyglot_oracle_grader_config())
    record: dict[str, Any] = {
        "benchmark": BENCHMARK,
        "data_source": DATA_SOURCE,
        "language": LANGUAGE,
        "oracle_protocol_version": ORACLE_PROTOCOL_VERSION,
        "task_id": f"cpp/{exercise.name}",
        "problem_id": exercise.name,
        "exercise": exercise.name,
        "category": exercise.categories[0],
        "categories": list(exercise.categories),
        "correct_answer_source": ORACLE_CORRECT_ANSWER_SOURCE,
        "solution_files": list(exercise.solution_files),
        "test_files": list(exercise.test_files),
        "example_files": list(exercise.example_files),
        "grader_config": active_grader_config,
        "reference_file_mappings": [],
        "unmapped_solution_files": list(exercise.solution_files),
        "oracle_input_sha256": None,
        "setup_valid": False,
        "passed": False,
        "all_tests_pass": False,
        "reason": "not_run",
        "returncode": None,
        "timeout": False,
        "harness_error": False,
        "compile_error": False,
        "tests_failed": False,
        "reference_bytes": 0,
    }
    try:
        record["oracle_input_sha256"] = polyglot_oracle_input_sha256(
            exercise_dir,
            solution_files=exercise.solution_files,
            example_files=exercise.example_files,
            grader_config=active_grader_config,
        )
        replacements, mappings, unmapped = polyglot_reference_replacements(
            exercise_dir,
            solution_files=exercise.solution_files,
            example_files=exercise.example_files,
        )
        record["reference_file_mappings"] = mappings
        record["unmapped_solution_files"] = unmapped
        result, reference_bytes = _run_replacements(
            {"exercise_path": str(Path(exercise_dir).resolve())},
            replacements,
        )
        record["reference_bytes"] = reference_bytes
    except PolyglotResponseError as exc:
        record.update({"reason": exc.reason, "exception": str(exc)})
        return record
    except Exception as exc:  # noqa: BLE001 - preserve setup failures as evidence
        record.update(
            {
                "reason": "oracle_exception",
                "exception": str(exc),
                "harness_error": True,
            }
        )
        return record

    record.update(_polyglot_oracle_fields_from_test_result(result))
    return record


def _polyglot_oracle_fields_from_test_result(result: PolyglotTestResult) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "setup_valid": result.passed,
        "passed": result.passed,
        "all_tests_pass": result.passed,
        "returncode": result.returncode,
        "timeout": result.timeout,
        "harness_error": False,
        "compile_error": False,
        "tests_failed": False,
    }
    if result.passed:
        fields["reason"] = "passed"
    elif result.timeout:
        fields["reason"] = "timeout"
    elif result.returncode in {125, 126, 127}:
        fields["reason"] = "harness_error"
        fields["harness_error"] = True
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


def aggregate_polyglot_oracle_setup_records(
    records: Iterable[dict[str, Any]],
    *,
    records_file: str | None = None,
    summary_file: str | None = None,
) -> dict[str, Any]:
    rows = list(records)
    passed = [row for row in rows if row.get("setup_valid") is True]
    reason_counts = Counter(str(row.get("reason", "unknown")) for row in rows)
    return {
        "enabled": True,
        "blocking": True,
        "complete": bool(rows),
        "phase": "data_preflight",
        "schema_version": SCHEMA_VERSION,
        "oracle_protocol_version": ORACLE_PROTOCOL_VERSION,
        "correct_answer_source": ORACLE_CORRECT_ANSWER_SOURCE,
        "records_file": records_file,
        "summary_file": summary_file,
        "task_count": len(rows),
        "passed_count": len(passed),
        "failed_count": len(rows) - len(passed),
        "pass_rate": len(passed) / len(rows) if rows else 0.0,
        "all_passed": bool(rows) and len(passed) == len(rows),
        "reason_counts": dict(sorted(reason_counts.items())),
        "failed_task_ids": [
            str(row.get("task_id")) for row in rows if row.get("setup_valid") is not True
        ],
    }


def _polyglot_artifact_path(
    root: Path, files: dict[str, Any], key: str, *, expect_directory: bool = False
) -> Path:
    relative_path = files.get(key)
    if not isinstance(relative_path, str):
        raise ValueError(f"missing Polyglot dataset artifact {key!r} under {root}")
    try:
        normalized = _normalize_relative_path(relative_path)
    except ValueError as exc:
        raise ValueError(f"unsafe Polyglot dataset artifact {key!r} under {root}") from exc
    resolved_root = root.resolve()
    path = (root / normalized).resolve()
    if path != resolved_root and resolved_root not in path.parents:
        raise ValueError(f"unsafe Polyglot dataset artifact {key!r} under {root}")
    exists = path.is_dir() if expect_directory else path.is_file()
    if not exists:
        raise ValueError(f"missing Polyglot dataset artifact {key!r} under {root}")
    return path


def _polyglot_record_paths(
    record: dict[str, Any], key: str, *, task_id: str
) -> list[str]:
    values = record.get(key)
    if not isinstance(values, list) or not values or not all(
        isinstance(value, str) for value in values
    ):
        raise ValueError(f"Polyglot oracle record {task_id!r} has invalid {key}")
    try:
        normalized = [_normalize_relative_path(value) for value in values]
    except ValueError as exc:
        raise ValueError(f"Polyglot oracle record {task_id!r} has invalid {key}") from exc
    if normalized != values or len(set(normalized)) != len(normalized):
        raise ValueError(f"Polyglot oracle record {task_id!r} has invalid {key}")
    return normalized


def validate_polyglot_dataset(data_root: str | Path) -> dict[str, Any]:
    """Recompute and require a fully passing, current same-grader oracle proof."""

    root = Path(data_root)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing Polyglot data manifest: {manifest_path}")
    manifest = _read_json_object(manifest_path)
    if manifest.get("kind") != DATASET_KIND:
        raise ValueError(f"unexpected Polyglot dataset kind in {manifest_path}")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported Polyglot dataset schema in {manifest_path}")
    if manifest.get("admitted") is not True:
        raise ValueError(f"Polyglot dataset has not passed blocking admission: {manifest_path}")

    oracle_check = manifest.get("oracle_setup_check")
    if (
        not isinstance(oracle_check, dict)
        or oracle_check.get("all_passed") is not True
        or oracle_check.get("complete") is not True
        or oracle_check.get("oracle_protocol_version") != ORACLE_PROTOCOL_VERSION
    ):
        raise ValueError(
            f"Polyglot dataset is missing a fully passing oracle setup check: {manifest_path}"
        )
    if oracle_check.get("correct_answer_source") != ORACLE_CORRECT_ANSWER_SOURCE:
        raise ValueError(f"unexpected Polyglot correct-answer source in {manifest_path}")

    files = manifest.get("files") if isinstance(manifest.get("files"), dict) else {}
    eval_path = _polyglot_artifact_path(root, files, "eval")
    records_path = _polyglot_artifact_path(root, files, "oracle_records")
    summary_path = _polyglot_artifact_path(root, files, "oracle_summary")
    tasks_path = _polyglot_artifact_path(root, files, "tasks", expect_directory=True)

    oracle_records = _read_jsonl(records_path)
    eval_rows = _read_jsonl(eval_path)
    copied_by_task_id = {
        f"cpp/{exercise.name}": exercise for exercise in discover_cpp_exercises(tasks_path)
    }
    if not oracle_records:
        raise ValueError(f"Polyglot oracle records are empty in {manifest_path}")

    eval_by_task_id: dict[str, dict[str, Any]] = {}
    for row in eval_rows:
        task_id = row.get("task_id")
        metadata = row.get("metadata")
        if (
            not isinstance(task_id, str)
            or not task_id
            or task_id in eval_by_task_id
            or row.get("label") != task_id
            or row.get("split") != "eval"
            or not isinstance(metadata, dict)
            or metadata.get("oracle_setup_valid") is not True
            or metadata.get("oracle_correct_answer_source")
            != ORACLE_CORRECT_ANSWER_SOURCE
        ):
            raise ValueError(f"invalid or duplicate Polyglot eval row in {eval_path}")
        eval_by_task_id[task_id] = row

    current_grader_config = polyglot_oracle_grader_config()
    record_task_ids: set[str] = set()
    for record in oracle_records:
        task_id = record.get("task_id")
        exercise = record.get("exercise")
        if (
            not isinstance(task_id, str)
            or not isinstance(exercise, str)
            or not exercise
            or task_id != f"cpp/{exercise}"
            or task_id in record_task_ids
        ):
            raise ValueError(f"invalid or duplicate Polyglot oracle record in {records_path}")
        record_task_ids.add(task_id)
        if (
            record.get("benchmark") != BENCHMARK
            or record.get("data_source") != DATA_SOURCE
            or record.get("language") != LANGUAGE
            or record.get("problem_id") != exercise
            or record.get("correct_answer_source") != ORACLE_CORRECT_ANSWER_SOURCE
            or record.get("oracle_protocol_version") != ORACLE_PROTOCOL_VERSION
            or record.get("grader_config") != current_grader_config
            or record.get("setup_valid") is not True
            or record.get("passed") is not True
            or record.get("all_tests_pass") is not True
            or record.get("reason") != "passed"
            or type(record.get("returncode")) is not int
            or record.get("returncode") != 0
            or record.get("timeout") is not False
            or record.get("harness_error") is not False
            or record.get("compile_error") is not False
            or record.get("tests_failed") is not False
            or type(record.get("reference_bytes")) is not int
            or record["reference_bytes"] <= 0
        ):
            raise ValueError(
                f"Polyglot oracle record {task_id!r} does not prove admission in {manifest_path}"
            )

        row = eval_by_task_id.get(task_id)
        if row is None:
            raise ValueError(f"Polyglot oracle/eval task mismatch in {manifest_path}")
        metadata = row["metadata"]
        if metadata.get("exercise") != exercise or row.get("problem_id") != exercise:
            raise ValueError(f"Polyglot oracle/eval identity mismatch for {task_id!r}")

        solution_files = _polyglot_record_paths(record, "solution_files", task_id=task_id)
        test_files = _polyglot_record_paths(record, "test_files", task_id=task_id)
        example_files = _polyglot_record_paths(record, "example_files", task_id=task_id)
        if (
            metadata.get("solution_files") != solution_files
            or metadata.get("test_files") != test_files
            or metadata.get("example_files") != example_files
        ):
            raise ValueError(f"Polyglot oracle/eval file mismatch for {task_id!r}")

        exercise_files = {"exercise": metadata.get("exercise_path")}
        exercise_path = _polyglot_artifact_path(
            root, exercise_files, "exercise", expect_directory=True
        )
        copied_exercise = copied_by_task_id.get(task_id)
        if (
            copied_exercise is None
            or exercise_path != copied_exercise.source_path.resolve()
        ):
            raise ValueError(f"Polyglot oracle/task identity mismatch for {task_id!r}")
        try:
            replacements, mappings, unmapped = polyglot_reference_replacements(
                exercise_path,
                solution_files=solution_files,
                example_files=example_files,
            )
        except PolyglotResponseError as exc:
            raise ValueError(
                f"Polyglot oracle mapping is stale for {task_id!r}: {exc}"
            ) from exc
        if (
            record.get("reference_file_mappings") != mappings
            or record.get("unmapped_solution_files") != unmapped
            or record.get("reference_bytes") != _replacement_bytes(replacements)
        ):
            raise ValueError(f"Polyglot oracle mapping mismatch for {task_id!r}")
        expected_fingerprint = polyglot_oracle_input_sha256(
            exercise_path,
            solution_files=solution_files,
            example_files=example_files,
            grader_config=current_grader_config,
        )
        if record.get("oracle_input_sha256") != expected_fingerprint:
            raise ValueError(f"stale Polyglot oracle record for {task_id!r}")

    if record_task_ids != set(eval_by_task_id):
        raise ValueError(f"Polyglot oracle/eval task mismatch in {manifest_path}")
    if record_task_ids != set(copied_by_task_id):
        raise ValueError(f"Polyglot oracle/copied-task mismatch in {manifest_path}")

    recomputed_summary = aggregate_polyglot_oracle_setup_records(
        oracle_records,
        records_file=records_path.name,
        summary_file=summary_path.name,
    )
    oracle_summary = _read_json_object(summary_path)
    if oracle_summary != recomputed_summary:
        raise ValueError(f"Polyglot oracle summary does not match records in {manifest_path}")
    if oracle_check != recomputed_summary:
        raise ValueError(f"Polyglot manifest oracle check does not match records in {manifest_path}")

    task_count = len(oracle_records)
    counts = manifest.get("counts") if isinstance(manifest.get("counts"), dict) else {}
    expected_counts = {
        "eval": task_count,
        "copied_exercises": task_count,
        "oracle_checked": task_count,
        "oracle_passed": task_count,
    }
    if any(counts.get(key) != value for key, value in expected_counts.items()):
        raise ValueError(f"Polyglot manifest counts do not match records in {manifest_path}")
    return recomputed_summary


def _eval_row(
    exercise: PolyglotExercise,
    *,
    exercise_path: str,
    source_root: Path,
    oracle_record: dict[str, Any],
) -> dict[str, Any]:
    return {
        "prompt": build_prompt(exercise),
        "label": f"cpp/{exercise.name}",
        "task_id": f"cpp/{exercise.name}",
        "problem_id": exercise.name,
        "split": "eval",
        "metadata": {
            "benchmark": BENCHMARK,
            "data_source": DATA_SOURCE,
            "language": LANGUAGE,
            "exercise": exercise.name,
            "blurb": exercise.blurb,
            "category": exercise.categories[0],
            "categories": list(exercise.categories),
            "exercise_path": exercise_path,
            "source_exercise_path": str(exercise.source_path),
            "source_root": str(source_root),
            "solution_files": list(exercise.solution_files),
            "test_files": list(exercise.test_files),
            "example_files": list(exercise.example_files),
            "oracle_setup_valid": oracle_record.get("setup_valid") is True,
            "oracle_correct_answer_source": oracle_record.get("correct_answer_source"),
        },
    }


def build_prompt(exercise: PolyglotExercise) -> str:
    docs = _exercise_docs(exercise.source_path)
    editable = "\n".join(f"- `{path}`" for path in exercise.solution_files)
    file_sections = []
    for rel_path in exercise.solution_files:
        path = exercise.source_path / rel_path
        content = path.read_text(encoding="utf-8") if path.exists() else ""
        file_sections.append(f"File: `{rel_path}`\n\n```cpp\n{content.rstrip()}\n```")
    return "\n\n".join(
        [
            "You are editing a C++ Exercism exercise from Aider Polyglot.",
            "Modify only the editable solution files so all provided tests pass.",
            docs.strip(),
            "Editable solution files:\n" + editable,
            "Current file contents:\n\n" + "\n\n".join(file_sections),
            _output_contract(),
        ]
    ).strip()


def _exercise_docs(exercise_dir: Path) -> str:
    parts = []
    for name in ("introduction.md", "instructions.md", "instructions.append.md"):
        path = exercise_dir / ".docs" / name
        if path.exists():
            parts.append(path.read_text(encoding="utf-8").strip())
    return "\n\n".join(part for part in parts if part)


def _output_contract() -> str:
    return """Return replacements for every editable solution file and no other files.

For each file, use this exact format:

```path
relative/path/from/exercise/root.cpp
```

```cpp
complete replacement file contents
```

Do not include tests, examples, build files, markdown, or explanations outside the required blocks."""


def parse_replacements(
    response: str,
    allowed_files: Sequence[str],
    *,
    require_all: bool = True,
) -> dict[str, str]:
    """Parse strict path/code-block file replacements from a model response."""

    allowed = {_normalize_relative_path(path) for path in allowed_files}
    if not response.strip():
        raise PolyglotResponseError("invalid_format", "empty response")

    blocks: list[tuple[str, str]] = []
    cursor = 0
    for match in _iter_fenced_blocks(response):
        if response[cursor : match["start"]].strip():
            raise PolyglotResponseError("invalid_format", "unexpected prose outside fenced blocks")
        blocks.append((match["info"], match["body"]))
        cursor = match["end"]
    if response[cursor:].strip():
        raise PolyglotResponseError("invalid_format", "unexpected prose after fenced blocks")
    if not blocks or len(blocks) % 2 != 0:
        raise PolyglotResponseError("invalid_format", "expected path/code block pairs")

    replacements: dict[str, str] = {}
    for index in range(0, len(blocks), 2):
        path_info, path_body = blocks[index]
        code_info, code_body = blocks[index + 1]
        if path_info.strip().lower() != "path":
            raise PolyglotResponseError("invalid_format", "expected a ```path block")
        lang = code_info.strip().lower()
        if lang not in ALLOWED_CODE_FENCE_LANGS:
            raise PolyglotResponseError("invalid_format", f"unsupported code fence language: {code_info!r}")
        path_lines = [line.strip() for line in path_body.splitlines() if line.strip()]
        if len(path_lines) != 1:
            raise PolyglotResponseError("invalid_format", "path block must contain exactly one path")
        rel_path = _normalize_relative_path(path_lines[0])
        if rel_path not in allowed:
            raise PolyglotResponseError("invalid_files", f"unknown or forbidden file: {rel_path}")
        if rel_path in replacements:
            raise PolyglotResponseError("invalid_files", f"duplicate replacement for: {rel_path}")
        replacements[rel_path] = code_body.rstrip() + "\n"

    if require_all:
        missing = sorted(allowed - set(replacements))
        if missing:
            raise PolyglotResponseError("invalid_files", f"missing replacement files: {', '.join(missing)}")
    return replacements


def recover_replacements(
    response: str,
    allowed_files: Sequence[str],
    *,
    require_all: bool = True,
) -> dict[str, str]:
    """Best-effort parser for diagnostic-only format recovery.

    This must not feed strict pass/fail scoring. It exists to identify samples
    where useful code is present but the model missed the requested path fences.
    """

    allowed_order = tuple(dict.fromkeys(_normalize_relative_path(path) for path in allowed_files))
    allowed = set(allowed_order)
    if not response.strip():
        raise PolyglotResponseError("invalid_format", "empty response")

    blocks = [
        block
        for block in _iter_fenced_blocks(response)
        if block["info"].strip().lower() in ALLOWED_CODE_FENCE_LANGS
    ]
    if not blocks:
        raise PolyglotResponseError("invalid_format", "no recoverable code blocks")

    replacements: dict[str, str] = {}
    previous_end = 0
    can_map_by_order = len(blocks) == len(allowed_order)
    for index, block in enumerate(blocks):
        context = response[previous_end : block["start"]]
        previous_end = block["end"]
        rel_path = _recover_path_from_context(context, allowed_order)
        if rel_path is None:
            if not can_map_by_order:
                raise PolyglotResponseError("invalid_format", "could not infer replacement file")
            rel_path = allowed_order[index]
        if rel_path in replacements:
            raise PolyglotResponseError("invalid_files", f"duplicate replacement for: {rel_path}")
        replacements[rel_path] = block["body"].rstrip() + "\n"

    if require_all:
        missing = sorted(allowed - set(replacements))
        if missing:
            raise PolyglotResponseError("invalid_files", f"missing replacement files: {', '.join(missing)}")
    return replacements


def _recover_path_from_context(context: str, allowed_order: Sequence[str]) -> str | None:
    last_line = ""
    for line in reversed(context.splitlines()):
        if line.strip():
            last_line = line.strip()
            break
    if not last_line:
        return None
    mentions = [_normalize_relative_path(match.group(0)) for match in _PATH_MENTION_RE.finditer(last_line)]
    if not mentions:
        return None
    token = mentions[-1]
    if token in allowed_order:
        return token
    basename_matches = [path for path in allowed_order if PurePosixPath(path).name == PurePosixPath(token).name]
    if len(basename_matches) == 1:
        return basename_matches[0]
    raise PolyglotResponseError("invalid_files", f"unknown or forbidden file: {token}")


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
    """SLIME custom reward hook for one Polyglot sample or a batch."""

    if isinstance(sample, list):
        return [await reward_func(args, item) for item in sample]
    return _score_sample(sample)


def _score_sample(sample: Any) -> dict[str, Any]:
    metadata = _sample_metadata(sample)
    allowed_files = metadata.get("solution_files")
    if not isinstance(allowed_files, list) or not allowed_files:
        return _record(
            sample,
            metadata,
            score=-1.0,
            reason="missing_solution_files",
            exception="metadata.solution_files is required",
        )

    allowed_file_names = [str(path) for path in allowed_files]
    response = _sample_response(sample)
    try:
        replacements = parse_replacements(response, allowed_file_names)
    except PolyglotResponseError as exc:
        record = _record(
            sample,
            metadata,
            score=-1.0,
            reason=exc.reason,
            exception=str(exc),
            format_valid=False,
        )
        if exc.reason == "invalid_format":
            return _attach_recovery_diagnostics(
                record, metadata, response=response, allowed_files=allowed_file_names
            )
        return record
    except Exception as exc:  # noqa: BLE001 - protects rollout workers from parser bugs
        record = _record(
            sample,
            metadata,
            score=-1.0,
            reason="invalid_format",
            exception=str(exc),
            format_valid=False,
        )
        return _attach_recovery_diagnostics(
            record, metadata, response=response, allowed_files=allowed_file_names
        )

    try:
        result, candidate_bytes = _run_replacements(metadata, replacements)
        return _record_from_test_result(sample, metadata, result, candidate_bytes=candidate_bytes)
    except PolyglotResponseError as exc:
        return _record(sample, metadata, score=-1.0, reason=exc.reason, exception=str(exc))
    except Exception as exc:  # pragma: no cover - guards real rollout workers
        return _record(sample, metadata, score=-1.0, reason="reward_exception", exception=str(exc))


def _attach_recovery_diagnostics(
    record: dict[str, Any],
    metadata: dict[str, Any],
    *,
    response: str,
    allowed_files: Sequence[str],
) -> dict[str, Any]:
    try:
        recovered = recover_replacements(response, allowed_files)
    except PolyglotResponseError as exc:
        record["recovered_reason"] = exc.reason
        record["recovered_exception"] = str(exc)
        return record
    except Exception as exc:  # noqa: BLE001 - diagnostic path must not fail rollout workers
        record["recovered_reason"] = "invalid_format"
        record["recovered_exception"] = str(exc)
        return record

    record["recovered_format"] = True
    try:
        result, candidate_bytes = _run_replacements(metadata, recovered)
    except PolyglotResponseError as exc:
        record["recovered_reason"] = exc.reason
        record["recovered_exception"] = str(exc)
        record["recovered_candidate_bytes"] = _replacement_bytes(recovered)
        return record
    except Exception as exc:  # pragma: no cover - guards real rollout workers
        record["recovered_reason"] = "reward_exception"
        record["recovered_exception"] = str(exc)
        record["recovered_candidate_bytes"] = _replacement_bytes(recovered)
        return record

    record.update(_recovered_fields_from_test_result(result, candidate_bytes=candidate_bytes))
    return record


def _run_replacements(metadata: dict[str, Any], replacements: dict[str, str]) -> tuple[PolyglotTestResult, int]:
    exercise_path = metadata.get("exercise_path")
    if not exercise_path:
        raise PolyglotResponseError("missing_exercise_path", "metadata.exercise_path is required")

    source_exercise = _resolve_exercise_path(str(exercise_path), metadata=metadata)
    with TemporaryDirectory(prefix="w8-polyglot-cpp-") as scratch_dir:
        scratch = Path(scratch_dir) / source_exercise.name
        shutil.copytree(source_exercise, scratch)
        for rel_path, content in replacements.items():
            target = scratch / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        result = run_polyglot_tests(scratch)
    candidate_bytes = _replacement_bytes(replacements)
    return result, candidate_bytes


def _replacement_bytes(replacements: dict[str, str]) -> int:
    return sum(len(value.encode("utf-8")) for value in replacements.values())


def _recovered_fields_from_test_result(
    result: PolyglotTestResult, *, candidate_bytes: int
) -> dict[str, Any]:
    if result.passed:
        fields = {
            "recovered_reason": "passed",
            "recovered_tests_passed": 1,
            "recovered_tests_total": 1,
        }
    elif result.timeout:
        fields = {"recovered_reason": "timeout", "recovered_timeout": True}
    elif _looks_like_compile_error(result.logs):
        fields = {"recovered_reason": "compile_error", "recovered_compile_error": True}
    else:
        fields = {
            "recovered_reason": "tests_failed",
            "recovered_tests_passed": 0,
            "recovered_tests_total": 1,
        }
    recovered_tests_total = fields.get("recovered_tests_total", 0)
    fields["recovered_all_tests_pass"] = (
        recovered_tests_total > 0
        and fields.get("recovered_tests_passed", 0) == recovered_tests_total
    )
    fields["recovered_candidate_bytes"] = candidate_bytes
    if _include_logs() and result.logs:
        fields["recovered_logs"] = result.logs
    elif result.logs:
        fields["recovered_log_excerpt"] = result.logs[-2000:]
    return fields


def run_polyglot_tests(exercise_dir: str | Path) -> PolyglotTestResult:
    """Run Aider-compatible C++ tests for one exercise inside Docker."""

    grader_config = polyglot_oracle_grader_config(require_image_id=False)
    timeout_s = grader_config["test_timeout_seconds"]
    image = grader_config["sandbox_image"]
    exercise_path = Path(exercise_dir).resolve()
    workdir = PurePosixPath("/work") / exercise_path.name
    command = _polyglot_docker_args(exercise_path.parent, workdir=workdir.as_posix(), image=image) + [
        "bash",
        "-lc",
        f"timeout {timeout_s}s bash -lc {shlex.quote(POLYGLOT_TEST_SCRIPT)}",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_s + 30, check=False)
    except subprocess.TimeoutExpired as exc:
        logs = ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip()
        return PolyglotTestResult(returncode=None, logs=logs, timeout=True)
    logs = "\n".join(part for part in (result.stdout, result.stderr) if part)
    return PolyglotTestResult(returncode=result.returncode, logs=logs, timeout=result.returncode == 124)


def _polyglot_docker_args(
    mount_root: str | Path,
    *,
    workdir: str,
    image: str = DEFAULT_POLYGLOT_SANDBOX_IMAGE,
    memory: str = DEFAULT_MEMORY,
) -> list[str]:
    """Return Docker args while preserving the exercise directory basename for CMake."""

    return [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--network",
        "none",
        "--cpus",
        "1",
        "--memory",
        memory,
        "--pids-limit",
        str(DEFAULT_POLYGLOT_PIDS_LIMIT),
        "--read-only",
        "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=64m,mode=1777",
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


def _record_from_test_result(
    sample: Any,
    metadata: dict[str, Any],
    result: PolyglotTestResult,
    *,
    candidate_bytes: int,
) -> dict[str, Any]:
    if result.passed:
        record = _record(sample, metadata, score=1.0, reason="passed", tests_passed=1, tests_total=1)
    elif result.timeout:
        record = _record(sample, metadata, score=-0.5, reason="timeout", timeout=True)
    elif _looks_like_compile_error(result.logs):
        record = _record(sample, metadata, score=-0.5, reason="compile_error", compile_error=True)
    else:
        record = _record(sample, metadata, score=0.0, reason="tests_failed", tests_passed=0, tests_total=1)
    record["candidate_bytes"] = candidate_bytes
    if _include_logs():
        record["logs"] = result.logs
    elif result.logs:
        record["log_excerpt"] = result.logs[-2000:]
    return record


def _looks_like_compile_error(logs: str) -> bool:
    lowered = logs.lower()
    needles = (
        "cmake error",
        "compiler error",
        "error:",
        "undefined reference",
        "no rule to make target",
        "could not compile",
        "compilation terminated",
    )
    return any(needle in lowered for needle in needles)


def _record(
    sample: Any,
    metadata: dict[str, Any],
    *,
    score: float,
    reason: str,
    exception: str | None = None,
    format_valid: bool = True,
    compile_error: bool = False,
    timeout: bool = False,
    tests_passed: int = 0,
    tests_total: int = 0,
) -> dict[str, Any]:
    categories = _record_categories(metadata)
    record = {
        "score": score,
        "reward": score,
        "reason": reason,
        "task_id": metadata.get("task_id") or f"cpp/{metadata.get('exercise', '')}".rstrip("/"),
        "problem_id": metadata.get("problem_id") or metadata.get("exercise"),
        "split": metadata.get("split", "eval"),
        "sample_index": _sample_index(sample),
        "rollout_id": getattr(sample, "rollout_id", None),
        "response": _sample_response(sample),
        "benchmark": BENCHMARK,
        "data_source": DATA_SOURCE,
        "language": LANGUAGE,
        "exercise": metadata.get("exercise"),
        "blurb": metadata.get("blurb"),
        "category": metadata.get("category") or categories[0],
        "categories": categories,
        "oracle_setup_valid": metadata.get("oracle_setup_valid") is True,
        "oracle_correct_answer_source": metadata.get("oracle_correct_answer_source"),
        "compile_error": compile_error,
        "sanitizer_error": False,
        "timeout": timeout,
        "tests_passed": tests_passed,
        "tests_total": tests_total,
        "all_tests_pass": tests_total > 0 and tests_passed == tests_total,
        "runtime_cpu_ns": None,
        "runtime_wall_ns": None,
        "reference_runtime_cpu_ns": None,
        "reference_runtime_wall_ns": None,
        "runtime_speedup": None,
        "candidate_bytes": 0,
        "format_valid": format_valid,
        "invalid_format": reason == "invalid_format",
        "invalid_files": reason == "invalid_files",
        "recovered_format": False,
        "recovered_reason": None,
        "recovered_compile_error": False,
        "recovered_timeout": False,
        "recovered_tests_passed": 0,
        "recovered_tests_total": 0,
        "recovered_all_tests_pass": False,
        "recovered_candidate_bytes": 0,
    }
    if exception:
        record["exception"] = exception
    return record


def _first_category(categories: object) -> str | None:
    if isinstance(categories, list):
        for category in categories:
            if isinstance(category, str) and category:
                return category
    return None


def _record_categories(metadata: dict[str, Any]) -> list[str]:
    categories = metadata.get("categories")
    if isinstance(categories, list):
        normalized = [str(category) for category in categories if str(category)]
        if normalized:
            return list(dict.fromkeys(normalized))
    category = metadata.get("category")
    if isinstance(category, str) and category:
        return [category]
    exercise = metadata.get("exercise") or metadata.get("problem_id")
    if isinstance(exercise, str) and exercise:
        return list(categorize_polyglot_cpp_exercise(exercise))
    return [UNCATEGORIZED_CATEGORY]


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


def _resolve_exercise_path(exercise_path: str, *, metadata: dict[str, Any]) -> Path:
    path = Path(exercise_path)
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


def score_debug_dump(
    *,
    label: str,
    debug_samples_path: str | Path,
    output_dir: str | Path,
    data_root: str | Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Path]]:
    samples = load_slime_debug_samples(debug_samples_path)
    records = [record_from_debug_sample(sample, label=label) for sample in samples]
    summary = aggregate_polyglot_records(records, label=label)
    if data_root is None:
        summary["oracle_setup_check"] = {
            "enabled": False,
            "blocking": True,
            "correct_answer_source": ORACLE_CORRECT_ANSWER_SOURCE,
            "reason": "data_root_not_provided",
        }
    else:
        summary["oracle_setup_check"] = validate_polyglot_dataset(data_root)
    output = Path(output_dir)
    records_path = output / f"{label}.records.jsonl"
    summary_path = output / f"{label}.summary.json"
    _write_jsonl(records_path, records)
    write_json(summary_path, summary)
    return records, summary, {"records": records_path, "summary": summary_path}


def record_from_debug_sample(sample: dict[str, Any], *, label: str | None = None) -> dict[str, Any]:
    metadata = sample.get("metadata") if isinstance(sample.get("metadata"), dict) else {}
    stashed = metadata.get("polyglot_reward_record")
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
    record.setdefault("language", LANGUAGE)
    record.setdefault("exercise", metadata.get("exercise") or metadata.get("problem_id"))
    record.setdefault("blurb", metadata.get("blurb"))
    record.setdefault("categories", _record_categories(metadata))
    record.setdefault("category", metadata.get("category") or _first_category(record.get("categories")))
    record.setdefault("oracle_setup_valid", metadata.get("oracle_setup_valid") is True)
    record.setdefault(
        "oracle_correct_answer_source", metadata.get("oracle_correct_answer_source")
    )
    record.setdefault("all_tests_pass", bool(record.get("tests_total")) and record.get("tests_passed") == record.get("tests_total"))
    record.setdefault("recovered_format", False)
    record.setdefault("recovered_reason", None)
    record.setdefault("recovered_compile_error", False)
    record.setdefault("recovered_timeout", False)
    record.setdefault("recovered_tests_passed", 0)
    record.setdefault("recovered_tests_total", 0)
    record.setdefault("recovered_all_tests_pass", False)
    record.setdefault("recovered_candidate_bytes", 0)
    if label is not None:
        record["label"] = label
    return record


def aggregate_polyglot_records(records: Iterable[dict[str, Any]], *, label: str) -> dict[str, Any]:
    rows = list(records)
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_task[str(row.get("task_id"))].append(row)

    best_rows = [_best_record(task_rows) for task_rows in by_task.values()]
    task_count = len(best_rows)
    sample_count = len(rows)
    passed = [row for row in best_rows if row.get("all_tests_pass") is True]
    reason_counts = Counter(str(row.get("reason", "unknown")) for row in rows)
    best_rewards = [float(row.get("reward", 0.0)) for row in best_rows]
    sample_rewards = [float(row.get("reward", 0.0)) for row in rows]

    return {
        "label": label,
        "benchmark": BENCHMARK,
        "language": LANGUAGE,
        "task_count": task_count,
        "sample_count": sample_count,
        "samples_per_task_mean": sample_count / task_count if task_count else 0.0,
        "pass_rate": len(passed) / task_count if task_count else 0.0,
        "compile_error_rate": _rate(rows, "compile_error"),
        "timeout_rate": _rate(rows, "timeout"),
        "invalid_format_rate": _reason_rate(rows, "invalid_format"),
        "invalid_files_rate": _reason_rate(rows, "invalid_files"),
        "tests_failed_rate": _reason_rate(rows, "tests_failed"),
        "recovered_format_rate": _rate(rows, "recovered_format"),
        "recovered_pass_rate": _rate(rows, "recovered_all_tests_pass"),
        "recovered_task_pass_rate": _task_any_rate(by_task, "recovered_all_tests_pass"),
        "recovered_compile_error_rate": _rate(rows, "recovered_compile_error"),
        "recovered_timeout_rate": _rate(rows, "recovered_timeout"),
        "mean_best_reward": _mean(best_rewards),
        "mean_sample_reward": _mean(sample_rewards),
        "reason_counts": dict(sorted(reason_counts.items())),
        "category_summary": _category_summary(rows, best_rows),
        "best_records": best_rows,
    }


def _category_summary(rows: list[dict[str, Any]], best_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    sample_by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    best_by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        for category in _row_categories(row):
            sample_by_category[category].append(row)
    for row in best_rows:
        for category in _row_categories(row):
            best_by_category[category].append(row)

    summary: dict[str, dict[str, Any]] = {}
    for category in sorted(set(sample_by_category) | set(best_by_category)):
        category_samples = sample_by_category.get(category, [])
        category_best = best_by_category.get(category, [])
        reason_counts = Counter(str(row.get("reason", "unknown")) for row in category_samples)
        best_rewards = [float(row.get("reward", 0.0)) for row in category_best]
        sample_rewards = [float(row.get("reward", 0.0)) for row in category_samples]
        passed = [row for row in category_best if row.get("all_tests_pass") is True]
        category_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in category_samples:
            category_by_task[str(row.get("task_id"))].append(row)
        summary[category] = {
            "task_count": len(category_best),
            "sample_count": len(category_samples),
            "pass_rate": len(passed) / len(category_best) if category_best else 0.0,
            "compile_error_rate": _rate(category_samples, "compile_error"),
            "timeout_rate": _rate(category_samples, "timeout"),
            "invalid_format_rate": _reason_rate(category_samples, "invalid_format"),
            "invalid_files_rate": _reason_rate(category_samples, "invalid_files"),
            "tests_failed_rate": _reason_rate(category_samples, "tests_failed"),
            "recovered_format_rate": _rate(category_samples, "recovered_format"),
            "recovered_pass_rate": _rate(category_samples, "recovered_all_tests_pass"),
            "recovered_task_pass_rate": _task_any_rate(category_by_task, "recovered_all_tests_pass"),
            "recovered_compile_error_rate": _rate(category_samples, "recovered_compile_error"),
            "recovered_timeout_rate": _rate(category_samples, "recovered_timeout"),
            "mean_best_reward": _mean(best_rewards),
            "mean_sample_reward": _mean(sample_rewards),
            "reason_counts": dict(sorted(reason_counts.items())),
        }
    return summary


def _row_categories(row: dict[str, Any]) -> list[str]:
    categories = row.get("categories")
    if isinstance(categories, list):
        normalized = [str(category) for category in categories if str(category)]
        if normalized:
            return list(dict.fromkeys(normalized))
    category = row.get("category")
    if isinstance(category, str) and category:
        return [category]
    exercise = row.get("exercise") or row.get("problem_id")
    if isinstance(exercise, str) and exercise:
        return list(categorize_polyglot_cpp_exercise(exercise))
    return [UNCATEGORIZED_CATEGORY]


def _best_record(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(rows, key=lambda row: float(row.get("reward", 0.0)))


def _rate(rows: list[dict[str, Any]], key: str) -> float:
    return sum(1 for row in rows if row.get(key) is True) / len(rows) if rows else 0.0


def _task_any_rate(by_task: dict[str, list[dict[str, Any]]], key: str) -> float:
    if not by_task:
        return 0.0
    matching_tasks = sum(
        1 for task_rows in by_task.values() if any(row.get(key) is True for row in task_rows)
    )
    return matching_tasks / len(by_task)


def _reason_rate(rows: list[dict[str, Any]], reason: str) -> float:
    return sum(1 for row in rows if row.get("reason") == reason) / len(rows) if rows else 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"invalid JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"cannot read JSONL: {path}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise ValueError(f"invalid JSONL record at {path}:{line_number}")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL record at {path}:{line_number}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"invalid JSONL record at {path}:{line_number}")
        rows.append(value)
    return rows


def _append_jsonl_record(path: Path, row: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return path


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return path


def polyglot_sandbox_image_dockerfile() -> str:
    return f"""FROM {BASE_DOCKER_IMAGE}
RUN apt-get update \\
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \\
        cmake libboost-date-time-dev make python3 \\
    && rm -rf /var/lib/apt/lists/*
"""


def build_polyglot_sandbox_image_command(*, image: str = DEFAULT_POLYGLOT_SANDBOX_IMAGE) -> list[str]:
    return ["docker", "build", "-t", image, "-"]


def polyglot_sandbox_image_build_plan(*, image: str = DEFAULT_POLYGLOT_SANDBOX_IMAGE) -> str:
    return "\n".join(
        [
            "# Polyglot C++ sandbox image build dry run",
            f"{shlex.join(build_polyglot_sandbox_image_command(image=image))} <<'DOCKERFILE'",
            polyglot_sandbox_image_dockerfile().rstrip(),
            "DOCKERFILE",
        ]
    )


def build_polyglot_sandbox_image(*, image: str = DEFAULT_POLYGLOT_SANDBOX_IMAGE) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        build_polyglot_sandbox_image_command(image=image),
        input=polyglot_sandbox_image_dockerfile(),
        check=False,
        capture_output=True,
        text=True,
    )


def _normalize_polyglot_task_id(task_id: str) -> str:
    normalized = task_id.strip()
    if not normalized:
        raise ValueError("Gemini sanity task id must not be empty")
    return normalized if normalized.startswith("cpp/") else f"cpp/{normalized}"


def load_admitted_polyglot_eval_row(
    data_root: str | Path, task_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = Path(data_root).resolve()
    oracle_check = validate_polyglot_dataset(root)
    normalized_task_id = _normalize_polyglot_task_id(task_id)
    rows = _read_jsonl(root / "eval" / "cpp.jsonl")
    matches = [row for row in rows if row.get("task_id") == normalized_task_id]
    if len(matches) != 1:
        available = ", ".join(sorted(str(row.get("task_id")) for row in rows))
        raise ValueError(
            f"Expected one admitted Polyglot row for {normalized_task_id!r}; "
            f"found {len(matches)}. Available: {available}"
        )
    row = matches[0]
    prompt = row.get("prompt")
    metadata = row.get("metadata")
    if not isinstance(prompt, str) or not prompt.strip() or not isinstance(metadata, dict):
        raise ValueError(f"Invalid admitted Polyglot eval row for {normalized_task_id!r}")
    if metadata.get("oracle_setup_valid") is not True:
        raise ValueError(f"Polyglot oracle admission is not valid for {normalized_task_id!r}")
    return row, oracle_check


def _gemini_api_key() -> tuple[str, str]:
    for env_name in GEMINI_API_KEY_ENV_NAMES:
        value = os.environ.get(env_name, "").strip()
        if value:
            return value, env_name
    names = " or ".join(GEMINI_API_KEY_ENV_NAMES)
    raise ValueError(f"Missing Gemini API key; export {names}")


def _sdk_json_object(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return dict(value)
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json", exclude_none=True)
        return dict(dumped) if isinstance(dumped, dict) else {"value": dumped}
    return {"value": str(value)}


def _gemini_finish_reason(response: Any) -> str | None:
    candidates = getattr(response, "candidates", None)
    if not isinstance(candidates, list) or not candidates:
        return None
    finish_reason = getattr(candidates[0], "finish_reason", None)
    if finish_reason is None:
        return None
    value = getattr(finish_reason, "value", None)
    return str(value if value is not None else finish_reason)


def _validate_gemini_generation_config(
    *, model: str, temperature: float, top_p: float, max_output_tokens: int
) -> None:
    if not model.strip():
        raise ValueError("Gemini model must not be empty")
    if model.strip().endswith("-latest"):
        raise ValueError("Use an exact Gemini model id, not a mutable -latest alias")
    if temperature < 0.0:
        raise ValueError("Gemini temperature must not be negative")
    if not 0.0 <= top_p <= 1.0:
        raise ValueError("Gemini top-p must be between 0 and 1")
    if max_output_tokens <= 0:
        raise ValueError("Gemini max output tokens must be positive")


def generate_gemini_text(
    *,
    prompt: str,
    model: str,
    temperature: float,
    top_p: float,
    seed: int,
    max_output_tokens: int,
) -> GeminiGeneration:
    _validate_gemini_generation_config(
        model=model,
        temperature=temperature,
        top_p=top_p,
        max_output_tokens=max_output_tokens,
    )
    api_key, api_key_source = _gemini_api_key()
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - exercised without the optional extra
        raise RuntimeError(
            "Gemini sanity dependencies are missing; rerun with `uv run --extra gemini`"
        ) from exc

    config = types.GenerateContentConfig(
        candidate_count=1,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        top_p=top_p,
        seed=seed,
    )
    with genai.Client(api_key=api_key) as client:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
    text = getattr(response, "text", None)
    if not isinstance(text, str) or not text.strip():
        finish_reason = _gemini_finish_reason(response) or "unknown"
        raise RuntimeError(f"Gemini returned no text; finish_reason={finish_reason}")
    return GeminiGeneration(
        text=text,
        api_key_source=api_key_source,
        finish_reason=_gemini_finish_reason(response),
        usage_metadata=_sdk_json_object(getattr(response, "usage_metadata", None)),
    )


def build_gemini_sanity_plan(
    *,
    data_root: str | Path,
    task_id: str,
    model: str,
    temperature: float,
    top_p: float,
    seed: int,
    max_output_tokens: int,
) -> dict[str, Any]:
    _validate_gemini_generation_config(
        model=model,
        temperature=temperature,
        top_p=top_p,
        max_output_tokens=max_output_tokens,
    )
    row, oracle_check = load_admitted_polyglot_eval_row(data_root, task_id)
    return _gemini_sanity_plan_from_row(
        row=row,
        oracle_check=oracle_check,
        model=model,
        temperature=temperature,
        top_p=top_p,
        seed=seed,
        max_output_tokens=max_output_tokens,
    )


def _gemini_sanity_plan_from_row(
    *,
    row: dict[str, Any],
    oracle_check: dict[str, Any],
    model: str,
    temperature: float,
    top_p: float,
    seed: int,
    max_output_tokens: int,
) -> dict[str, Any]:
    prompt = str(row["prompt"])
    return {
        "kind": GEMINI_SANITY_KIND,
        "schema_version": GEMINI_SANITY_SCHEMA_VERSION,
        "provider": "google-gemini-api",
        "task_id": row["task_id"],
        "problem_id": row["problem_id"],
        "model": model,
        "generation_config": {
            "candidate_count": 1,
            "max_output_tokens": max_output_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "seed": seed,
        },
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
        "prompt": prompt,
        "oracle_setup_check": oracle_check,
        "response_policy": {
            "raw_response_only": True,
            "strict_scoring": True,
            "recovery_is_diagnostic_only": True,
        },
    }


def _preflight_gemini_output_dir(output: Path, *, force: bool) -> bool:
    created = False
    if output.exists():
        if not output.is_dir():
            raise FileExistsError(f"Gemini sanity output is not a directory: {output}")
        if any(output.iterdir()) and not force:
            raise FileExistsError(
                f"{output} already exists and is not empty; pass --force to replace it"
            )
    else:
        output.mkdir(parents=True)
        created = True

    # Exercise both permissions needed after the paid request: writing inside
    # the result directory and replacing it atomically when --force is used.
    with TemporaryDirectory(prefix=".gemini-write-check-", dir=output):
        pass
    with TemporaryDirectory(prefix=".gemini-parent-write-check-", dir=output.parent):
        pass
    return created


def run_polyglot_gemini_sanity(
    *,
    data_root: str | Path,
    task_id: str,
    output_dir: str | Path,
    model: str = DEFAULT_GEMINI_MODEL,
    temperature: float = 0.0,
    top_p: float = 1.0,
    seed: int = 42,
    max_output_tokens: int = 8192,
    force: bool = False,
    generator: Callable[..., GeminiGeneration] | None = None,
) -> tuple[dict[str, Any], dict[str, Path]]:
    output = Path(output_dir).resolve()
    created_output = _preflight_gemini_output_dir(output, force=force)
    try:
        _validate_gemini_generation_config(
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
        )
        row, oracle_check = load_admitted_polyglot_eval_row(data_root, task_id)
        plan = _gemini_sanity_plan_from_row(
            row=row,
            oracle_check=oracle_check,
            model=model,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
            max_output_tokens=max_output_tokens,
        )
        generate = generator or generate_gemini_text
        generation = generate(
            prompt=plan["prompt"],
            model=model,
            temperature=temperature,
            top_p=top_p,
            seed=seed,
            max_output_tokens=max_output_tokens,
        )
    except Exception:
        if created_output:
            output.rmdir()
        raise

    metadata = {
        **row["metadata"],
        "task_id": row["task_id"],
        "problem_id": row["problem_id"],
        "split": row["split"],
        "task_root": str(Path(data_root).resolve()),
    }
    record = _score_sample({"index": 0, "metadata": metadata, "response": generation.text})
    record["sanity_provider"] = "google-gemini-api"
    record["sanity_model"] = model

    if force and not created_output:
        shutil.rmtree(output)
        output.mkdir(parents=True)
    paths = {
        "prompt": output / "prompt.txt",
        "response": output / "response.txt",
        "request": output / "request.json",
        "record": output / "record.json",
        "summary": output / "summary.json",
    }
    paths["prompt"].write_text(str(plan.pop("prompt")), encoding="utf-8")
    paths["response"].write_text(generation.text, encoding="utf-8")
    request = {
        key: value
        for key, value in plan.items()
        if key not in {"oracle_setup_check", "response_policy"}
    }
    request["api_key_source"] = generation.api_key_source
    write_json(paths["request"], request)
    write_json(paths["record"], record)
    summary = {
        **plan,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "api_key_source": generation.api_key_source,
        "finish_reason": generation.finish_reason,
        "usage_metadata": generation.usage_metadata,
        "strict_pass": record.get("all_tests_pass") is True,
        "strict_score": record.get("score"),
        "strict_reason": record.get("reason"),
        "recovered_pass": record.get("recovered_all_tests_pass") is True,
        "recovered_reason": record.get("recovered_reason"),
        "artifacts": {key: path.name for key, path in paths.items()},
    }
    write_json(paths["summary"], summary)
    return summary, paths


def _build_data_command(args: argparse.Namespace) -> None:
    paths = build_slime_polyglot_cpp_dataset(
        args.source_root,
        args.out,
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
    )
    print(json.dumps({key: str(path) for key, path in paths.items()}, indent=2, sort_keys=True))


def _verify_data_command(args: argparse.Namespace) -> None:
    oracle_check = validate_polyglot_dataset(args.data_root)
    print(json.dumps(oracle_check, indent=2, sort_keys=True))


def _sandbox_image_command(args: argparse.Namespace) -> None:
    if args.dry_run:
        print(polyglot_sandbox_image_build_plan(image=args.image))
        return
    result = build_polyglot_sandbox_image(image=args.image)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    raise SystemExit(result.returncode)


def _gemini_sanity_command(args: argparse.Namespace) -> None:
    if args.dry_run:
        plan = build_gemini_sanity_plan(
            data_root=args.data_root,
            task_id=args.task_id,
            model=args.model,
            temperature=args.temperature,
            top_p=args.top_p,
            seed=args.seed,
            max_output_tokens=args.max_output_tokens,
        )
        print(json.dumps(plan, indent=2, sort_keys=True))
        return
    summary, paths = run_polyglot_gemini_sanity(
        data_root=args.data_root,
        task_id=args.task_id,
        output_dir=args.out,
        model=args.model,
        temperature=args.temperature,
        top_p=args.top_p,
        seed=args.seed,
        max_output_tokens=args.max_output_tokens,
        force=args.force,
    )
    print(
        json.dumps(
            {
                "paths": {key: str(path) for key, path in paths.items()},
                "summary": summary,
            },
            indent=2,
            sort_keys=True,
        )
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_data = subparsers.add_parser("build-data", help="Convert Polyglot C++ exercises into SLIME JSONL")
    build_data.add_argument("--source-root", required=True)
    build_data.add_argument("--out", required=True)
    build_data.add_argument("--eval-limit", type=int, default=DEFAULT_EVAL_LIMIT)
    build_data.add_argument("--profile", default="moonlight-polyglot-cpp")
    build_data.add_argument("--run-id", default=None)
    build_data.add_argument("--force", action="store_true")
    build_data.set_defaults(func=_build_data_command)

    aggregate = subparsers.add_parser("aggregate-debug", help="Aggregate SLIME debug rollout samples")
    aggregate.add_argument("--label", required=True, choices=("base",))
    aggregate.add_argument("--debug-rollout", required=True)
    aggregate.add_argument("--out", required=True)
    aggregate.add_argument("--data-root", default=None)
    aggregate.set_defaults(func=_aggregate_command)

    verify_data = subparsers.add_parser(
        "verify-data", help="Require a fully passing Polyglot reference-solution preflight"
    )
    verify_data.add_argument("--data-root", required=True)
    verify_data.set_defaults(func=_verify_data_command)

    sandbox_image = subparsers.add_parser("sandbox-image", help="Build or render the Polyglot C++ sandbox image")
    sandbox_image.add_argument("--image", default=DEFAULT_POLYGLOT_SANDBOX_IMAGE)
    sandbox_image.add_argument("--dry-run", action="store_true")
    sandbox_image.set_defaults(func=_sandbox_image_command)

    gemini_sanity = subparsers.add_parser(
        "gemini-sanity",
        help="Run one admitted Polyglot task through Gemini and the strict local grader",
    )
    gemini_sanity.add_argument("--data-root", required=True)
    gemini_sanity.add_argument("--task-id", required=True)
    gemini_sanity.add_argument("--out", required=True)
    gemini_sanity.add_argument("--model", default=DEFAULT_GEMINI_MODEL)
    gemini_sanity.add_argument("--temperature", type=float, default=0.0)
    gemini_sanity.add_argument("--top-p", type=float, default=1.0)
    gemini_sanity.add_argument("--seed", type=int, default=42)
    gemini_sanity.add_argument("--max-output-tokens", type=int, default=8192)
    gemini_sanity.add_argument("--dry-run", action="store_true")
    gemini_sanity.add_argument("--force", action="store_true")
    gemini_sanity.set_defaults(func=_gemini_sanity_command)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main()
