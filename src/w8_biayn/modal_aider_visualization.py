"""Offline visualization for the GLM-4.7-Flash Aider Polyglot C++ run.

The visualizer is intentionally read-only with respect to the canonical
``runs/<run-id>`` evidence tree. It validates admitted independent pass@1/pass@8
artifacts, normalizes structured Aider rows, and writes a separate local report
tree with JSON, CSV, Markdown, HTML, and SVG figures.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import fields as dataclass_fields
import html
import json
import math
from pathlib import Path
import shutil
import sys
from typing import Any, Mapping, Sequence

from w8_biayn.modal_aider_polyglot_cpp import (
    BENCHMARK_LABEL,
    INDEPENDENT_EVAL_MODE,
    INDEPENDENT_RESULT_LABEL,
    INDEPENDENT_SAMPLES_PER_TASK,
    INDEPENDENT_TRIES,
    ModalAiderConfig,
    ModalAiderError,
    build_artifact_manifest,
    build_independent_pass_report,
    ensure_secret_free,
    independent_config_fingerprint,
    model_settings,
    sample_seed,
    sha256_file,
    validate_independent_aider_results,
    validate_independent_authoritative_stats,
    write_json,
    _two_try_result_row,
)


VISUALIZATION_SCHEMA_VERSION = 2
GENERATOR_VERSION = "modal-aider-visualization-v2"
COMPATIBLE_OVERWRITE_GENERATORS = {
    "modal-aider-visualization-v1",
    GENERATOR_VERSION,
}
PARTIAL_WARNING_TEMPLATE = (
    "PARTIAL DIAGNOSTIC - {completed} OF 8 TRAJECTORIES COMPLETE - NOT PASS@8"
)

CELL_COLUMNS = [
    "task_id",
    "topic_category",
    "difficulty",
    "sample_index",
    "seed",
    "attempts_made",
    "raw_tests_outcomes",
    "try1_success",
    "try2_success",
    "recovered_on_try2",
    "outcome",
    "prompt_tokens",
    "completion_tokens",
    "duration_seconds",
    "num_user_asks",
    "num_error_outputs",
    "num_exhausted_context_windows",
    "num_malformed_responses",
    "syntax_errors",
    "test_timeouts",
    "official_result_sha256",
    "chat_history_sha256",
    "config_fingerprint",
]

OUTCOME_ORDER = [
    "passed_try1",
    "passed_try2",
    "context_exhausted",
    "malformed_response",
    "failed_tests",
]

OUTCOME_COLORS = {
    "passed_try1": "#2E7D32",
    "passed_try2": "#1565C0",
    "context_exhausted": "#EF6C00",
    "malformed_response": "#8E24AA",
    "failed_tests": "#90A4AE",
    "missing": "#FFFFFF",
}

OUTCOME_GLYPHS = {
    "passed_try1": "I",
    "passed_try2": "R",
    "context_exhausted": "C",
    "malformed_response": "M",
    "failed_tests": "F",
    "missing": "-",
}

DIAGNOSTIC_FIELDS = [
    "num_exhausted_context_windows",
    "num_malformed_responses",
    "num_error_outputs",
    "syntax_errors",
    "test_timeouts",
    "indentation_errors",
    "lazy_comments",
]


# The pinned official Aider C++ subset contains 26 tasks. Keep one stable,
# mutually-exclusive topic and difficulty label per task so reports remain
# comparable across runs. Topic groups are medium-grained (3-6 tasks each),
# while difficulty reflects implementation/test-surface complexity rather than
# this model's observed outcomes.
AIDER_CPP_TOPIC_TASKS: dict[str, tuple[str, ...]] = {
    "Algorithms & data structures": (
        "binary-search-tree",
        "circular-buffer",
        "grade-school",
        "knapsack",
        "linked-list",
        "sublist",
    ),
    "Text & parsing": (
        "crypto-square",
        "diamond",
        "kindergarten-garden",
        "phone-number",
    ),
    "Numerical reasoning": (
        "all-your-base",
        "allergies",
        "complex-numbers",
        "perfect-numbers",
        "space-age",
    ),
    "Time & date": (
        "clock",
        "gigasecond",
        "meetup",
    ),
    "State & concurrency": (
        "bank-account",
        "dnd-character",
        "parallel-letter-frequency",
        "robot-name",
    ),
    "Logic, grids & games": (
        "queen-attack",
        "spiral-matrix",
        "yacht",
        "zebra-puzzle",
    ),
}

AIDER_CPP_DIFFICULTY_TASKS: dict[str, tuple[str, ...]] = {
    "Easy": (
        "allergies",
        "clock",
        "complex-numbers",
        "diamond",
        "gigasecond",
        "perfect-numbers",
        "queen-attack",
        "space-age",
    ),
    "Medium": (
        "all-your-base",
        "crypto-square",
        "dnd-character",
        "grade-school",
        "kindergarten-garden",
        "meetup",
        "phone-number",
        "sublist",
        "yacht",
    ),
    "Hard": (
        "bank-account",
        "binary-search-tree",
        "circular-buffer",
        "knapsack",
        "linked-list",
        "parallel-letter-frequency",
        "robot-name",
        "spiral-matrix",
        "zebra-puzzle",
    ),
}


def _invert_task_groups(groups: Mapping[str, Sequence[str]], *, label: str) -> dict[str, str]:
    by_task: dict[str, str] = {}
    for group, tasks in groups.items():
        for task_id in tasks:
            if task_id in by_task:
                raise RuntimeError(f"duplicate {label} taxonomy entry for {task_id}")
            by_task[task_id] = group
    return by_task


AIDER_CPP_TOPIC_BY_TASK = _invert_task_groups(AIDER_CPP_TOPIC_TASKS, label="topic")
AIDER_CPP_DIFFICULTY_BY_TASK = _invert_task_groups(
    AIDER_CPP_DIFFICULTY_TASKS, label="difficulty"
)
if (
    set(AIDER_CPP_TOPIC_BY_TASK) != set(AIDER_CPP_DIFFICULTY_BY_TASK)
    or len(AIDER_CPP_TOPIC_BY_TASK) != 26
):
    raise RuntimeError("Aider C++ topic and difficulty taxonomies must cover the same 26 tasks")


def _task_taxonomy(task_id: str) -> tuple[str, str]:
    topic = AIDER_CPP_TOPIC_BY_TASK.get(task_id)
    difficulty = AIDER_CPP_DIFFICULTY_BY_TASK.get(task_id)
    if topic is None or difficulty is None:
        raise ModalAiderError(
            f"Aider C++ task taxonomy is missing {task_id!r}; classify it before rendering"
        )
    return topic, difficulty


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ModalAiderError(f"malformed JSON: {path}") from exc


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{100 * value:.1f}%"


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if math.isfinite(float(value)):
            return float(value)
        return None
    if isinstance(value, str) and value.strip():
        try:
            parsed = float(value)
        except ValueError:
            return None
        return parsed if math.isfinite(parsed) else None
    return None


def _int_counter(payload: Mapping[str, Any], *names: str) -> int:
    for name in names:
        value = _num(payload.get(name))
        if value is not None:
            return max(0, int(value))
    return 0


def _float_value(payload: Mapping[str, Any], *names: str) -> float | None:
    for name in names:
        value = _num(payload.get(name))
        if value is not None:
            return value
    return None


def _safe_relative(path: Path, root: Path) -> str:
    resolved = path.resolve()
    if resolved != root and root not in resolved.parents:
        raise ModalAiderError(f"evidence path escapes run root: {path}")
    relative = resolved.relative_to(root)
    if relative.is_absolute() or ".." in relative.parts:
        raise ModalAiderError(f"unsafe relative evidence path: {path}")
    return relative.as_posix()


def _load_config_from_run_root(run_root: Path) -> ModalAiderConfig:
    config_path = run_root / "config.redacted.json"
    if not config_path.is_file():
        raise ModalAiderError("visualization requires config.redacted.json")
    payload = _read_json(config_path)
    if not isinstance(payload, dict):
        raise ModalAiderError("config.redacted.json must contain an object")
    names = {field.name for field in dataclass_fields(ModalAiderConfig)}
    kwargs = {name: payload[name] for name in names if name in payload}
    config = ModalAiderConfig(**kwargs)
    if config.eval_mode != INDEPENDENT_EVAL_MODE:
        raise ModalAiderError("visualization supports only independent-pass-at-1-and-8 evidence")
    return config


def _find_official_result_dir(sample_root: Path, run_root: Path) -> Path:
    candidates = []
    for child in sorted(item for item in sample_root.iterdir() if item.is_dir()):
        if child.name == "incomplete-attempts":
            continue
        result_root = child / "cpp/exercises/practice"
        if result_root.is_dir():
            _safe_relative(result_root, run_root)
            candidates.append(child)
    if len(candidates) != 1:
        raise ModalAiderError(
            f"{sample_root.name} expected one official Aider result directory, "
            f"found {len(candidates)}"
        )
    return candidates[0]


def _validate_settings_hash(sample_root: Path) -> None:
    settings = sample_root / "model-settings.yml"
    digest = sample_root / "model-settings.sha256"
    if not settings.is_file() or not digest.is_file():
        raise ModalAiderError(f"{sample_root.name} is missing model settings evidence")
    actual = sha256_file(settings)
    expected = digest.read_text(encoding="utf-8").strip()
    if actual != expected:
        raise ModalAiderError(f"{sample_root.name} model-settings.sha256 does not match")


def _validate_sample_metadata(
    config: ModalAiderConfig,
    sample_root: Path,
    *,
    sample_index: int,
) -> dict[str, Any]:
    expected_seed = sample_seed(config, sample_index)
    expected_fingerprint = independent_config_fingerprint(config)
    command = _read_json(sample_root / "command.json")
    request = _read_json(sample_root / "request-metadata.json")
    fresh_tree = _read_json(sample_root / "fresh-tree.receipt.json")
    if not isinstance(command, dict) or not isinstance(request, dict) or not isinstance(fresh_tree, dict):
        raise ModalAiderError(f"{sample_root.name} metadata files must contain objects")
    if (
        command.get("sample_index") != sample_index
        or command.get("seed") != expected_seed
        or command.get("tries") != INDEPENDENT_TRIES
        or command.get("config_fingerprint") != expected_fingerprint
    ):
        raise ModalAiderError(f"{sample_root.name} command metadata does not match config")
    if request.get("sample_index") != sample_index or request.get("seed") != expected_seed:
        raise ModalAiderError(f"{sample_root.name} request metadata does not match config")
    if fresh_tree.get("copy_isolated_from_other_samples") is not True:
        raise ModalAiderError(f"{sample_root.name} lacks fresh-tree isolation proof")
    settings_text = (sample_root / "model-settings.yml").read_text(encoding="utf-8")
    if settings_text != model_settings(config, sample_index=sample_index):
        raise ModalAiderError(f"{sample_root.name} model settings do not match config")
    _validate_settings_hash(sample_root)
    return {
        "command": command,
        "request_metadata": request,
        "fresh_tree": fresh_tree,
        "seed": expected_seed,
        "config_fingerprint": expected_fingerprint,
    }


def _cell_from_result_path(
    config: ModalAiderConfig,
    result_path: Path,
    *,
    sample_index: int,
    run_root: Path,
) -> dict[str, Any]:
    payload = _two_try_result_row(result_path)
    task_id = result_path.parent.name
    topic_category, difficulty = _task_taxonomy(task_id)
    outcomes = payload["tests_outcomes"]
    try1_success = bool(outcomes[0])
    try2_success = bool(any(outcomes))
    recovered = not try1_success and try2_success
    exhausted = _int_counter(payload, "num_exhausted_context_windows", "exhausted_context_windows")
    malformed = _int_counter(payload, "num_malformed_responses", "malformed_responses")
    if try1_success:
        outcome = "passed_try1"
    elif try2_success:
        outcome = "passed_try2"
    elif exhausted:
        outcome = "context_exhausted"
    elif malformed:
        outcome = "malformed_response"
    else:
        outcome = "failed_tests"
    history = result_path.with_name(".aider.chat.history.md")
    return {
        "task_id": task_id,
        "topic_category": topic_category,
        "difficulty": difficulty,
        "sample_index": sample_index,
        "seed": sample_seed(config, sample_index),
        "attempts_made": len(outcomes),
        "raw_tests_outcomes": list(outcomes),
        "try1_success": try1_success,
        "try2_success": try2_success,
        "recovered_on_try2": recovered,
        "outcome": outcome,
        "prompt_tokens": _int_counter(payload, "prompt_tokens"),
        "completion_tokens": _int_counter(payload, "completion_tokens"),
        "duration_seconds": _float_value(payload, "duration_seconds", "duration", "seconds"),
        "num_user_asks": _int_counter(payload, "num_user_asks", "user_asks"),
        "num_error_outputs": _int_counter(payload, "num_error_outputs", "error_outputs"),
        "num_exhausted_context_windows": exhausted,
        "num_malformed_responses": malformed,
        "syntax_errors": _int_counter(payload, "syntax_errors"),
        "indentation_errors": _int_counter(payload, "indentation_errors"),
        "lazy_comments": _int_counter(payload, "lazy_comments"),
        "test_timeouts": _int_counter(payload, "test_timeouts"),
        "official_result_path": _safe_relative(result_path, run_root),
        "official_result_sha256": sha256_file(result_path),
        "chat_history_path": _safe_relative(history, run_root),
        "chat_history_sha256": sha256_file(history),
        "config_fingerprint": independent_config_fingerprint(config),
    }


def _has_minimum_completed_sample_evidence(sample_root: Path) -> bool:
    if not sample_root.is_dir():
        return False
    required = (
        "command.json",
        "request-metadata.json",
        "fresh-tree.receipt.json",
        "model-settings.yml",
        "model-settings.sha256",
        "stats.json",
    )
    if not all((sample_root / name).is_file() for name in required):
        return False
    return any(
        child.is_dir() and (child / "cpp/exercises/practice").is_dir()
        for child in sample_root.iterdir()
    )


def _complete_sample_indices(protocol_root: Path) -> list[int]:
    present_completed = []
    for sample_root in sorted(protocol_root.glob("sample-[0-9][0-9]")):
        try:
            index = int(sample_root.name.split("-", 1)[1])
        except ValueError:
            continue
        if (
            1 <= index <= INDEPENDENT_SAMPLES_PER_TASK
            and _has_minimum_completed_sample_evidence(sample_root)
        ):
            present_completed.append(index)
    if not present_completed:
        return []
    expected_prefix = list(range(1, max(present_completed) + 1))
    if present_completed != expected_prefix:
        raise ModalAiderError("partial independent samples must be a contiguous completed prefix")
    return present_completed


def _load_samples(
    config: ModalAiderConfig,
    run_root: Path,
    *,
    sample_indices: Sequence[int],
    expected_tasks: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[int, Path]]:
    protocol_root = run_root / INDEPENDENT_EVAL_MODE
    expected_task_ids: set[str] | None = None
    cells: list[dict[str, Any]] = []
    sample_rows: list[dict[str, Any]] = []
    result_dirs: dict[int, Path] = {}
    for sample_index in sample_indices:
        sample_root = protocol_root / f"sample-{sample_index:02d}"
        if not sample_root.is_dir():
            raise ModalAiderError(f"missing sample-{sample_index:02d}")
        metadata = _validate_sample_metadata(config, sample_root, sample_index=sample_index)
        result_dir = _find_official_result_dir(sample_root, run_root)
        admission = validate_independent_aider_results(result_dir, expected_tasks=expected_tasks)
        stats_path = sample_root / "stats.json"
        if not stats_path.is_file():
            raise ModalAiderError(f"sample-{sample_index:02d} is missing stats.json")
        stats = _read_json(stats_path)
        if not isinstance(stats, dict):
            raise ModalAiderError(f"sample-{sample_index:02d} stats.json must contain an object")
        validate_independent_authoritative_stats(
            stats, result_dir=result_dir, expected_tasks=expected_tasks
        )
        result_paths = sorted(result_dir.glob("cpp/exercises/practice/*/.aider.results.json"))
        task_ids = {path.parent.name for path in result_paths}
        if expected_task_ids is None:
            expected_task_ids = task_ids
        elif task_ids != expected_task_ids:
            raise ModalAiderError("independent samples have mismatched task sets")
        for path in result_paths:
            cells.append(
                _cell_from_result_path(
                    config, path, sample_index=sample_index, run_root=run_root
                )
            )
        sample_rows.append(
            {
                "sample_index": sample_index,
                "seed": metadata["seed"],
                "result_dir": _safe_relative(result_dir, run_root),
                "stats_path": _safe_relative(stats_path, run_root),
                "stats_txt_present": (sample_root / "stats.txt").is_file(),
                "aider_pass_rate_1": stats.get("pass_rate_1"),
                "aider_pass_rate_2": stats.get("pass_rate_2"),
                "test_invocations": admission.test_invocations,
                "config_fingerprint": metadata["config_fingerprint"],
            }
        )
        result_dirs[sample_index] = result_dir
    return cells, sample_rows, result_dirs


def _validate_final(
    config: ModalAiderConfig,
    run_root: Path,
    *,
    result_dirs: Mapping[int, Path],
    expected_tasks: int,
) -> dict[str, Any]:
    protocol_root = run_root / INDEPENDENT_EVAL_MODE
    recomputed = build_independent_pass_report(
        config,
        sample_result_dirs=result_dirs,
        out=protocol_root,
        expected_tasks=expected_tasks,
        persist=False,
    )
    summary_path = protocol_root / "pass-at-1-and-8-by-try.json"
    samples_path = protocol_root / "samples.jsonl"
    if not summary_path.is_file() or not samples_path.is_file():
        raise ModalAiderError("final independent report is missing stored summary or rows")
    stored_summary = _read_json(summary_path)
    if stored_summary != recomputed["summary"]:
        raise ModalAiderError("stored pass@1/pass@8 summary does not match official rows")
    for try_name in ("try1", "try2"):
        matrix_path = protocol_root / f"success-matrix.{try_name}.json"
        if not matrix_path.is_file():
            raise ModalAiderError(f"final independent report is missing {matrix_path.name}")
        if _read_json(matrix_path) != {"rows": recomputed["matrices"][try_name]}:
            raise ModalAiderError(f"{matrix_path.name} does not match official rows")
        csv_path = protocol_root / f"success-matrix.{try_name}.csv"
        if not csv_path.is_file():
            raise ModalAiderError(f"final independent report is missing {csv_path.name}")
    stored_samples = [
        json.loads(line)
        for line in samples_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    expected_samples = sorted(
        recomputed["samples"], key=lambda item: (item["task_id"], item["sample_index"])
    )
    if stored_samples != expected_samples:
        raise ModalAiderError("stored samples.jsonl does not match official rows")
    metrics_csv = protocol_root / "pass-at-1-and-8-by-try.csv"
    if not metrics_csv.is_file():
        raise ModalAiderError("final independent report is missing metric CSV")
    with metrics_csv.open(encoding="utf-8", newline="") as handle:
        metric_rows = list(csv.reader(handle))
    expected_metric_rows = [
        [metric, str(stored_summary[metric])]
        for metric in ("pass@1_try1", "pass@1_try2", "pass@8_try1", "pass@8_try2")
    ]
    if metric_rows != [["metric", "value"], *expected_metric_rows]:
        raise ModalAiderError("metric CSV does not match the independent summary")
    report_md = protocol_root / "report.md"
    if not report_md.is_file():
        raise ModalAiderError("final independent report is missing Markdown")
    report_text = report_md.read_text(encoding="utf-8")
    for metric in ("pass@1_try1", "pass@1_try2", "pass@8_try1", "pass@8_try2"):
        if f"- {metric}: {stored_summary[metric]:.12g}" not in report_text:
            raise ModalAiderError(f"stored Markdown does not match {metric}")
    receipt_path = run_root / "run_receipt.json"
    if not receipt_path.is_file():
        raise ModalAiderError("final evidence is missing run_receipt.json")
    receipt = _read_json(receipt_path)
    if (
        not isinstance(receipt, dict)
        or receipt.get("status") != "complete"
        or receipt.get("eval_mode") != INDEPENDENT_EVAL_MODE
        or receipt.get("modal_app_stopped") is not True
        or receipt.get("teardown_status") != "verified"
        or receipt.get("independent_pass_at_1_and_8") != stored_summary
    ):
        raise ModalAiderError("final receipt does not admit the independent report")
    manifest_path = run_root / "artifact_manifest.json"
    if not manifest_path.is_file():
        raise ModalAiderError("final evidence is missing artifact_manifest.json")
    stored_manifest = _read_json(manifest_path)
    manifest = build_artifact_manifest(run_root)
    if stored_manifest != manifest:
        raise ModalAiderError("canonical run tree does not match artifact_manifest.json")
    return {
        "summary": stored_summary,
        "receipt": receipt,
        "artifact_manifest": manifest,
        "source_manifest_sha256": sha256_file(manifest_path),
    }


def _group_cells(cells: Sequence[Mapping[str, Any]], key: str) -> dict[Any, list[Mapping[str, Any]]]:
    grouped: dict[Any, list[Mapping[str, Any]]] = {}
    for cell in cells:
        grouped.setdefault(cell[key], []).append(cell)
    return grouped


def _task_summaries(cells: Sequence[Mapping[str, Any]], completed_samples: int) -> list[dict[str, Any]]:
    rows = []
    for task_id, task_cells in _group_cells(cells, "task_id").items():
        try1 = sum(1 for cell in task_cells if cell["try1_success"])
        try2 = sum(1 for cell in task_cells if cell["try2_success"])
        recovered = sum(1 for cell in task_cells if cell["recovered_on_try2"])
        if try1 == completed_samples:
            pattern = "initially_always_solved"
        elif try1 < completed_samples and try2 == completed_samples:
            pattern = "retry_needed_for_full_coverage"
        elif 0 < try2 < completed_samples:
            pattern = "intermittently_solved"
        else:
            pattern = "never_solved"
        rows.append(
            {
                "task_id": task_id,
                "topic_category": task_cells[0]["topic_category"],
                "difficulty": task_cells[0]["difficulty"],
                "completed_samples": completed_samples,
                "try1_successes": try1,
                "try2_successes": try2,
                "recovered_on_try2": recovered,
                "final_failures": completed_samples - try2,
                "pattern": pattern,
            }
        )
    return sorted(rows, key=lambda row: (row["try2_successes"], row["try1_successes"], row["task_id"]))


def _task_category_summaries(
    tasks: Sequence[Mapping[str, Any]],
    *,
    field: str,
    categories: Sequence[str],
) -> list[dict[str, Any]]:
    rows = []
    for category in categories:
        members = [task for task in tasks if task[field] == category]
        if not members:
            continue
        trajectory_count = sum(int(task["completed_samples"]) for task in members)
        try1_successes = sum(int(task["try1_successes"]) for task in members)
        try2_successes = sum(int(task["try2_successes"]) for task in members)
        recovered = sum(int(task["recovered_on_try2"]) for task in members)
        rows.append(
            {
                field: category,
                "task_count": len(members),
                "task_ids": sorted(str(task["task_id"]) for task in members),
                "trajectory_count": trajectory_count,
                "try1_successes": try1_successes,
                "try2_successes": try2_successes,
                "try1_success_rate": (
                    try1_successes / trajectory_count if trajectory_count else 0.0
                ),
                "try2_success_rate": (
                    try2_successes / trajectory_count if trajectory_count else 0.0
                ),
                "recovered_on_try2": recovered,
                "task_coverage_try1": (
                    sum(1 for task in members if int(task["try1_successes"]) > 0)
                    / len(members)
                ),
                "task_coverage_try2": (
                    sum(1 for task in members if int(task["try2_successes"]) > 0)
                    / len(members)
                ),
            }
        )
    return rows


def _sample_summaries(cells: Sequence[Mapping[str, Any]], samples: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    stats_by_sample = {row["sample_index"]: row for row in samples}
    rows = []
    for sample_index, sample_cells in sorted(_group_cells(cells, "sample_index").items()):
        denominator = len(sample_cells)
        try1 = sum(1 for cell in sample_cells if cell["try1_success"])
        try2 = sum(1 for cell in sample_cells if cell["try2_success"])
        recovered = sum(1 for cell in sample_cells if cell["recovered_on_try2"])
        rows.append(
            {
                "sample_index": sample_index,
                "seed": stats_by_sample[sample_index]["seed"],
                "task_count": denominator,
                "try1_successes": try1,
                "try2_successes": try2,
                "try1_success_rate": try1 / denominator if denominator else 0.0,
                "try2_success_rate": try2 / denominator if denominator else 0.0,
                "recovered_on_try2": recovered,
                "final_failures": denominator - try2,
                "aider_pass_rate_1": stats_by_sample[sample_index].get("aider_pass_rate_1"),
                "aider_pass_rate_2": stats_by_sample[sample_index].get("aider_pass_rate_2"),
            }
        )
    return rows


def _retry_rows(cells: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for label, subset in [("overall", list(cells)), *sorted(_group_cells(cells, "sample_index").items())]:
        passed = sum(1 for cell in subset if cell["try1_success"])
        recovered = sum(1 for cell in subset if cell["recovered_on_try2"])
        failed = sum(1 for cell in subset if not cell["try2_success"])
        retry_denominator = recovered + failed
        rows.append(
            {
                "scope": str(label),
                "passed_initially": passed,
                "recovered_on_try2": recovered,
                "failed_after_try2": failed,
                "total_cells": len(subset),
                "retry_recovery_rate": (
                    recovered / retry_denominator if retry_denominator else None
                ),
            }
        )
    return rows


def _coverage_rows(
    cells: Sequence[Mapping[str, Any]],
    task_ids: Sequence[str],
    sample_indices: Sequence[int],
) -> list[dict[str, Any]]:
    rows = []
    seen_try1: set[str] = set()
    seen_try2: set[str] = set()
    cells_by_sample = _group_cells(cells, "sample_index")
    total_tasks = len(task_ids)
    for sample_index in sample_indices:
        before_try1 = set(seen_try1)
        before_try2 = set(seen_try2)
        for cell in cells_by_sample.get(sample_index, []):
            if cell["try1_success"]:
                seen_try1.add(cell["task_id"])
            if cell["try2_success"]:
                seen_try2.add(cell["task_id"])
        rows.append(
            {
                "sample_prefix": sample_index,
                "seed": sample_seed_from_cells(cells_by_sample.get(sample_index, [])),
                "coverage_try1": len(seen_try1) / total_tasks if total_tasks else 0.0,
                "coverage_try2": len(seen_try2) / total_tasks if total_tasks else 0.0,
                "new_tasks_try1": len(seen_try1 - before_try1),
                "new_tasks_try2": len(seen_try2 - before_try2),
            }
        )
    return rows


def sample_seed_from_cells(cells: Sequence[Mapping[str, Any]]) -> int | None:
    return int(cells[0]["seed"]) if cells else None


def _diagnostic_rows(cells: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for field in DIAGNOSTIC_FIELDS:
        total = sum(int(cell.get(field, 0) or 0) for cell in cells)
        flagged = sum(1 for cell in cells if int(cell.get(field, 0) or 0) > 0)
        rows.append(
            {
                "diagnostic": field,
                "cells_with_flag": flagged,
                "total_count": total,
                "cell_rate": flagged / len(cells) if cells else 0.0,
            }
        )
    return rows


def _outcome_pattern_rows(tasks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for pattern in (
        "initially_always_solved",
        "retry_needed_for_full_coverage",
        "intermittently_solved",
        "never_solved",
    ):
        members = [row["task_id"] for row in tasks if row["pattern"] == pattern]
        rows.append({"pattern": pattern, "count": len(members), "tasks": members})
    return rows


def _completeness_rows(
    run_root: Path,
    sample_indices: Sequence[int],
    *,
    final: bool,
) -> list[dict[str, Any]]:
    rows = []
    protocol_root = run_root / INDEPENDENT_EVAL_MODE
    sample_requirements = {
        "command/request metadata": ("command.json", "request-metadata.json"),
        "fresh-tree receipt": ("fresh-tree.receipt.json",),
        "settings and hash": ("model-settings.yml", "model-settings.sha256"),
        "stats JSON": ("stats.json",),
        "stats text": ("stats.txt",),
        "official result directory": (),
    }
    for sample_index in range(1, INDEPENDENT_SAMPLES_PER_TASK + 1):
        sample_root = protocol_root / f"sample-{sample_index:02d}"
        for requirement, filenames in sample_requirements.items():
            if sample_index not in sample_indices:
                status = "missing"
            elif requirement == "official result directory":
                try:
                    _find_official_result_dir(sample_root, run_root)
                    status = "complete"
                except ModalAiderError:
                    status = "incomplete"
            else:
                status = (
                    "complete"
                    if sample_root.is_dir() and all((sample_root / name).is_file() for name in filenames)
                    else "incomplete"
                )
            rows.append(
                {
                    "scope": f"sample-{sample_index:02d}",
                    "requirement": requirement,
                    "status": status,
                }
            )
    final_requirements = {
        "receipt stopped-App proof": "run_receipt.json",
        "artifact manifest": "artifact_manifest.json",
        "try1 matrix": f"{INDEPENDENT_EVAL_MODE}/success-matrix.try1.json",
        "try2 matrix": f"{INDEPENDENT_EVAL_MODE}/success-matrix.try2.json",
        "summary": f"{INDEPENDENT_EVAL_MODE}/pass-at-1-and-8-by-try.json",
    }
    for requirement, relative in final_requirements.items():
        present = (run_root / relative).is_file()
        rows.append(
            {
                "scope": "final",
                "requirement": requirement,
                "status": "complete" if final and present else ("incomplete" if present else "missing"),
            }
        )
    return rows


def _build_normalized_report(
    *,
    config: ModalAiderConfig,
    run_root: Path,
    mode: str,
    cells: list[dict[str, Any]],
    sample_rows: list[dict[str, Any]],
    final_admission: Mapping[str, Any] | None,
) -> dict[str, Any]:
    sample_indices = sorted({int(cell["sample_index"]) for cell in cells})
    completed_samples = len(sample_indices)
    task_rows = _task_summaries(cells, completed_samples)
    sample_summaries = _sample_summaries(cells, sample_rows)
    retry = _retry_rows(cells)
    coverage = _coverage_rows(cells, [row["task_id"] for row in task_rows], sample_indices)
    diagnostics = _diagnostic_rows(cells)
    patterns = _outcome_pattern_rows(task_rows)
    topic_categories = _task_category_summaries(
        task_rows,
        field="topic_category",
        categories=tuple(AIDER_CPP_TOPIC_TASKS),
    )
    difficulty_categories = _task_category_summaries(
        task_rows,
        field="difficulty",
        categories=tuple(AIDER_CPP_DIFFICULTY_TASKS),
    )
    total_cells = len(cells)
    try1_successes = sum(1 for cell in cells if cell["try1_success"])
    try2_successes = sum(1 for cell in cells if cell["try2_success"])
    if mode == "final":
        final_metrics = {
            key: final_admission["summary"][key]  # type: ignore[index]
            for key in ("pass@1_try1", "pass@1_try2", "pass@8_try1", "pass@8_try2")
        }
        partial_metrics = None
        warning = None
    else:
        final_metrics = None
        partial_metrics = {
            "observed_trajectory_success_rate_try1": (
                try1_successes / total_cells if total_cells else 0.0
            ),
            "observed_trajectory_success_rate_try2": (
                try2_successes / total_cells if total_cells else 0.0
            ),
            "observed_task_coverage_try1": (
                sum(1 for row in task_rows if row["try1_successes"] > 0) / len(task_rows)
                if task_rows
                else 0.0
            ),
            "observed_task_coverage_try2": (
                sum(1 for row in task_rows if row["try2_successes"] > 0) / len(task_rows)
                if task_rows
                else 0.0
            ),
        }
        warning = PARTIAL_WARNING_TEMPLATE.format(completed=completed_samples)
    return {
        "schema_version": VISUALIZATION_SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "benchmark": BENCHMARK_LABEL,
        "result_family": INDEPENDENT_RESULT_LABEL,
        "run": {
            "run_id": config.run_id,
            "run_root": run_root.as_posix(),
            "model_repo": config.model_repo,
            "model_revision": config.model_revision,
            "aider_commit": config.aider_commit,
            "polyglot_commit": config.polyglot_commit,
            "edit_format": config.edit_format,
            "temperature": config.temperature,
            "top_p": config.top_p,
            "max_tokens": config.max_tokens,
            "base_seed": config.base_seed,
            "seed_schedule": [sample_seed(config, index) for index in range(1, 9)],
            "config_fingerprint": independent_config_fingerprint(config),
        },
        "evidence": {
            "mode": mode,
            "completed_samples": completed_samples,
            "completed_sample_indices": sample_indices,
            "completed_cells": total_cells,
            "expected_cells_final": config.expected_cpp_tasks * INDEPENDENT_SAMPLES_PER_TASK,
            "expected_tasks": config.expected_cpp_tasks,
            "partial_warning": warning,
            "source_manifest_sha256": (
                final_admission.get("source_manifest_sha256") if final_admission else None
            ),
        },
        "final_metrics": final_metrics,
        "partial_diagnostics": partial_metrics,
        "summaries": {
            "tasks": task_rows,
            "samples": sample_summaries,
            "retry_transitions": retry,
            "coverage_by_prefix": coverage,
            "diagnostics": diagnostics,
            "outcome_patterns": patterns,
            "topic_categories": topic_categories,
            "difficulty_categories": difficulty_categories,
            "evidence_completeness": _completeness_rows(
                run_root, sample_indices, final=mode == "final"
            ),
        },
        "cells": sorted(cells, key=lambda cell: (cell["task_id"], cell["sample_index"])),
        "redacted_config": config.redacted_mapping(),
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            encoded = {
                key: _json_dumps(value) if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            }
            writer.writerow(encoded)


def _svg_root(width: int, height: int, title: str, desc: str, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<desc>{html.escape(desc)}</desc>\n"
        '<style>text{font-family:Arial,sans-serif;font-size:12px;fill:#263238}'
        '.title{font-size:18px;font-weight:700}.small{font-size:11px}'
        '.axis{stroke:#607D8B;stroke-width:1}.grid{stroke:#ECEFF1;stroke-width:1}'
        "</style>\n"
        f"{body}\n</svg>\n"
    )


def _text(x: float, y: float, value: Any, *, klass: str = "", anchor: str = "start") -> str:
    cls = f' class="{klass}"' if klass else ""
    return f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}"{cls}>{html.escape(str(value))}</text>'


def _rect(x: float, y: float, width: float, height: float, fill: str, stroke: str = "#FFFFFF") -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" '
        f'fill="{fill}" stroke="{stroke}" />'
    )


def _render_four_metrics(report: Mapping[str, Any]) -> str:
    metrics = report["final_metrics"]
    values = [
        ("breadth 1 / try 1", metrics["pass@1_try1"]),
        ("breadth 1 / try 2", metrics["pass@1_try2"]),
        ("breadth 8 / try 1", metrics["pass@8_try1"]),
        ("breadth 8 / try 2", metrics["pass@8_try2"]),
    ]
    width, height = 720, 390
    left, bottom, top = 80, 315, 70
    chart_h = bottom - top
    bar_w = 82
    parts = [
        _text(20, 30, "Four final independent metrics", klass="title"),
        _text(20, 52, INDEPENDENT_RESULT_LABEL, klass="small"),
        f'<line x1="{left}" y1="{bottom}" x2="680" y2="{bottom}" class="axis"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" class="axis"/>',
    ]
    for tick in range(0, 101, 25):
        y = bottom - chart_h * tick / 100
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="680" y2="{y:.1f}" class="grid"/>')
        parts.append(_text(70, y + 4, f"{tick}%", anchor="end", klass="small"))
    for index, (label, value) in enumerate(values):
        x = 115 + index * 135
        bar_h = chart_h * value
        parts.append(_rect(x, bottom - bar_h, bar_w, bar_h, "#1565C0" if "try 2" in label else "#2E7D32"))
        parts.append(_text(x + bar_w / 2, bottom - bar_h - 8, _percent(value), anchor="middle"))
        parts.append(_text(x + bar_w / 2, bottom + 20, label.replace(" / ", "\n"), anchor="middle", klass="small"))
    parts.append(_text(20, 370, "Denominator: task-average rate over admitted tasks. Try 2 is cumulative.", klass="small"))
    return _svg_root(
        width,
        height,
        "Four final independent metrics",
        "Grouped bars for breadth one and breadth eight by cumulative try depth.",
        "\n".join(parts),
    )


def _task_order(report: Mapping[str, Any]) -> list[str]:
    return [row["task_id"] for row in report["summaries"]["tasks"]]


def _render_matrix(report: Mapping[str, Any], *, try_name: str) -> str:
    tasks = _task_order(report)
    samples = report["evidence"]["completed_sample_indices"]
    cells = {(cell["task_id"], cell["sample_index"]): cell for cell in report["cells"]}
    cell_w, cell_h = 34, 22
    left, top = 230, 72
    width = max(760, left + len(samples) * cell_w + 60)
    height = max(260, top + len(tasks) * cell_h + 70)
    title = "Try-1 outcome matrix" if try_name == "try1" else "Cumulative try-2 transition matrix"
    parts = [
        _text(20, 30, title, klass="title"),
        _text(20, 52, "Rows are hardest first. I=initial pass, R=repaired, F=final failure, C/M=diagnostic failure.", klass="small"),
    ]
    for col, sample in enumerate(samples):
        parts.append(_text(left + col * cell_w + cell_w / 2, top - 12, f"s{sample}", anchor="middle", klass="small"))
    for row_index, task_id in enumerate(tasks):
        y = top + row_index * cell_h
        parts.append(_text(20, y + 15, task_id, klass="small"))
        for col, sample in enumerate(samples):
            x = left + col * cell_w
            cell = cells[(task_id, sample)]
            if try_name == "try1":
                outcome = "passed_try1" if cell["try1_success"] else "failed_tests"
                glyph = "I" if cell["try1_success"] else "F"
            elif cell["try1_success"]:
                outcome, glyph = "passed_try1", "I"
            elif cell["recovered_on_try2"]:
                outcome, glyph = "passed_try2", "R"
            else:
                outcome = cell["outcome"]
                glyph = OUTCOME_GLYPHS[outcome]
            stroke = "#EF6C00" if cell["num_exhausted_context_windows"] else "#FFFFFF"
            parts.append(_rect(x, y, cell_w, cell_h, OUTCOME_COLORS[outcome], stroke=stroke))
            parts.append(_text(x + cell_w / 2, y + 15, glyph, anchor="middle", klass="small"))
    return _svg_root(width, height, title, "Task by sample outcome heatmap.", "\n".join(parts))


def _render_task_difficulty(report: Mapping[str, Any]) -> str:
    tasks = report["summaries"]["tasks"]
    denominator = report["evidence"]["completed_samples"]
    width = 820
    row_h = 24
    left, top = 260, 70
    height = max(260, top + len(tasks) * row_h + 55)
    scale = 430 / max(denominator, 1)
    parts = [
        _text(20, 30, "Per-task difficulty and retry gain", klass="title"),
        _text(20, 52, f"Successful trajectories among {denominator} completed trajectories.", klass="small"),
    ]
    for tick in range(denominator + 1):
        x = left + tick * scale
        parts.append(f'<line x1="{x:.1f}" y1="{top-8}" x2="{x:.1f}" y2="{height-45}" class="grid"/>')
        parts.append(_text(x, height - 25, tick, anchor="middle", klass="small"))
    for idx, task in enumerate(tasks):
        y = top + idx * row_h
        x1 = left + task["try1_successes"] * scale
        x2 = left + task["try2_successes"] * scale
        parts.append(_text(20, y + 5, task["task_id"], klass="small"))
        parts.append(f'<line x1="{x1:.1f}" y1="{y:.1f}" x2="{x2:.1f}" y2="{y:.1f}" stroke="#1565C0" stroke-width="4"/>')
        parts.append(f'<circle cx="{x1:.1f}" cy="{y:.1f}" r="5" fill="#2E7D32"/>')
        parts.append(f'<circle cx="{x2:.1f}" cy="{y:.1f}" r="5" fill="#1565C0"/>')
        parts.append(_text(x2 + 10, y + 4, f"{task['try1_successes']}/{denominator} -> {task['try2_successes']}/{denominator}", klass="small"))
    return _svg_root(width, height, "Per-task difficulty and retry gain", "Paired dots show try-1 and cumulative try-2 successes.", "\n".join(parts))


def _render_category_performance(
    report: Mapping[str, Any],
    *,
    summary_key: str,
    field: str,
    title: str,
    subtitle: str,
) -> str:
    rows = report["summaries"][summary_key]
    width = 940
    left, top = 300, 82
    chart_w = 480
    row_h = 62
    height = max(280, top + len(rows) * row_h + 65)
    parts = [
        _text(20, 30, title, klass="title"),
        _text(20, 52, subtitle, klass="small"),
    ]
    for tick in range(0, 101, 25):
        x = left + chart_w * tick / 100
        parts.append(
            f'<line x1="{x:.1f}" y1="{top-10}" x2="{x:.1f}" y2="{height-48}" class="grid"/>'
        )
        parts.append(_text(x, height - 25, f"{tick}%", anchor="middle", klass="small"))
    for index, row in enumerate(rows):
        y = top + index * row_h
        try1_width = chart_w * float(row["try1_success_rate"])
        try2_width = chart_w * float(row["try2_success_rate"])
        parts.append(
            _text(20, y + 23, f"{row[field]} ({row['task_count']} tasks)", klass="small")
        )
        parts.append(_rect(left, y, try1_width, 18, "#2E7D32"))
        parts.append(_rect(left, y + 23, try2_width, 18, "#1565C0"))
        parts.append(
            _text(
                left + try1_width + 8,
                y + 14,
                f"I {_percent(row['try1_success_rate'])}",
                klass="small",
            )
        )
        parts.append(
            _text(
                left + try2_width + 8,
                y + 37,
                f"T2 {_percent(row['try2_success_rate'])}",
                klass="small",
            )
        )
    parts.append(
        _text(
            20,
            height - 8,
            "I = initial success; T2 = cumulative try-2 success. Denominator is task × trajectory cells.",
            klass="small",
        )
    )
    return _svg_root(
        width,
        height,
        title,
        "Paired bars compare initial and cumulative try-2 trajectory success by stable task category.",
        "\n".join(parts),
    )


def _render_retry_transitions(report: Mapping[str, Any]) -> str:
    rows = report["summaries"]["retry_transitions"]
    width, height = 820, max(240, 70 + len(rows) * 34 + 45)
    left, top = 170, 68
    bar_w = 520
    colors = [("#2E7D32", "passed_initially"), ("#1565C0", "recovered_on_try2"), ("#90A4AE", "failed_after_try2")]
    parts = [
        _text(20, 30, "Retry transition and recovery", klass="title"),
        _text(20, 52, "Exclusive cell states. Recovery rate excludes initial passes.", klass="small"),
    ]
    for idx, row in enumerate(rows):
        y = top + idx * 34
        total = max(int(row["total_cells"]), 1)
        x = left
        parts.append(_text(20, y + 16, row["scope"], klass="small"))
        for color, key in colors:
            w = bar_w * int(row[key]) / total
            parts.append(_rect(x, y, w, 20, color))
            if w > 24:
                parts.append(_text(x + w / 2, y + 14, int(row[key]), anchor="middle", klass="small"))
            x += w
        parts.append(_text(left + bar_w + 12, y + 15, f"recovery={_percent(row['retry_recovery_rate'])}", klass="small"))
    return _svg_root(width, height, "Retry transition and recovery", "Stacked bars for initial pass, repair, and final failure.", "\n".join(parts))


def _render_coverage(report: Mapping[str, Any]) -> str:
    rows = report["summaries"]["coverage_by_prefix"]
    width, height = 780, 360
    left, bottom, top = 70, 290, 65
    chart_w = 600
    chart_h = bottom - top
    max_s = max(1, len(rows))
    parts = [
        _text(20, 30, "Cumulative solved-task coverage by completed trajectory", klass="title"),
        _text(20, 52, "Order-sensitive curve over the frozen seed schedule.", klass="small"),
        f'<line x1="{left}" y1="{bottom}" x2="{left+chart_w}" y2="{bottom}" class="axis"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" class="axis"/>',
    ]
    prev_points: dict[str, list[tuple[float, float]]] = {"coverage_try1": [], "coverage_try2": []}
    for idx, row in enumerate(rows, start=1):
        x = left + (idx - 1) * (chart_w / max(max_s - 1, 1))
        for key in prev_points:
            y = bottom - chart_h * float(row[key])
            prev_points[key].append((x, y))
        parts.append(_text(x, bottom + 18, idx, anchor="middle", klass="small"))
        parts.append(_rect(x - 7, bottom - row["new_tasks_try2"] * 12, 14, row["new_tasks_try2"] * 12, "#BBDEFB"))
    for key, color in (("coverage_try1", "#2E7D32"), ("coverage_try2", "#1565C0")):
        points = " ".join(f"{x:.1f},{y:.1f}" for x, y in prev_points[key])
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="3"/>')
        for x, y in prev_points[key]:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}"/>')
    parts.append(_text(20, 335, "Lines: initial and cumulative try-2 task coverage. Bars: newly covered by sample.", klass="small"))
    return _svg_root(width, height, "Cumulative solved-task coverage", "Coverage lines and marginal newly solved task bars.", "\n".join(parts))


def _render_sample_stability(report: Mapping[str, Any]) -> str:
    rows = report["summaries"]["samples"]
    width, height = 820, 360
    left, bottom, top = 80, 290, 65
    group_w = 80
    chart_h = bottom - top
    parts = [
        _text(20, 30, "Per-sample stability", klass="title"),
        _text(20, 52, "Paired bars show task success percentages and recovered/final-failure counts.", klass="small"),
        f'<line x1="{left}" y1="{bottom}" x2="760" y2="{bottom}" class="axis"/>',
    ]
    for idx, row in enumerate(rows):
        x = left + idx * group_w
        h1 = chart_h * row["try1_success_rate"]
        h2 = chart_h * row["try2_success_rate"]
        parts.append(_rect(x, bottom - h1, 22, h1, "#2E7D32"))
        parts.append(_rect(x + 26, bottom - h2, 22, h2, "#1565C0"))
        parts.append(_text(x + 24, bottom + 18, f"s{row['sample_index']}", anchor="middle", klass="small"))
        parts.append(_text(x + 24, bottom + 32, f"seed {row['seed']}", anchor="middle", klass="small"))
    return _svg_root(width, height, "Per-sample stability", "Try-1 and cumulative try-2 rates per sample.", "\n".join(parts))


def _render_outcome_patterns(report: Mapping[str, Any]) -> str:
    rows = report["summaries"]["outcome_patterns"]
    width, height = 780, 300
    left, top = 300, 70
    max_count = max([row["count"] for row in rows] + [1])
    parts = [
        _text(20, 30, "Task outcome-pattern summary", klass="title"),
        _text(20, 52, "Mutually exclusive classes over completed samples.", klass="small"),
    ]
    for idx, row in enumerate(rows):
        y = top + idx * 42
        w = 360 * row["count"] / max_count
        parts.append(_text(20, y + 16, row["pattern"], klass="small"))
        parts.append(_rect(left, y, w, 22, "#1565C0"))
        parts.append(_text(left + w + 10, y + 16, row["count"], klass="small"))
    return _svg_root(width, height, "Task outcome-pattern summary", "Bar chart of mutually exclusive task patterns.", "\n".join(parts))


def _render_diagnostics(report: Mapping[str, Any]) -> str:
    rows = report["summaries"]["diagnostics"]
    width, height = 820, 320
    left, top = 300, 70
    max_count = max([row["cells_with_flag"] for row in rows] + [1])
    parts = [
        _text(20, 30, "Structured failure diagnostics", klass="title"),
        _text(20, 52, "Diagnostic panels overlap; do not sum them as exclusive outcomes.", klass="small"),
    ]
    for idx, row in enumerate(rows):
        y = top + idx * 30
        w = 380 * row["cells_with_flag"] / max_count
        parts.append(_text(20, y + 15, row["diagnostic"], klass="small"))
        parts.append(_rect(left, y, w, 18, "#EF6C00" if "context" in row["diagnostic"] else "#8E24AA"))
        parts.append(_text(left + w + 10, y + 14, f"{row['cells_with_flag']} cells / {row['total_count']} count", klass="small"))
    return _svg_root(width, height, "Structured failure diagnostics", "Counts for overlapping structured diagnostic flags.", "\n".join(parts))


def _render_token_efficiency(report: Mapping[str, Any]) -> str:
    cells = report["cells"]
    width, height = 780, 430
    left, bottom, top = 80, 340, 65
    chart_w, chart_h = 610, bottom - top
    max_prompt = max([cell["prompt_tokens"] for cell in cells] + [1])
    max_completion = max([cell["completion_tokens"] for cell in cells] + [1])
    parts = [
        _text(20, 30, "Token use and efficiency", klass="title"),
        _text(20, 52, "One point per task/sample cell. Axes are token counts.", klass="small"),
        f'<line x1="{left}" y1="{bottom}" x2="{left+chart_w}" y2="{bottom}" class="axis"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" class="axis"/>',
    ]
    for cell in cells:
        x = left + chart_w * (cell["prompt_tokens"] / max_prompt)
        y = bottom - chart_h * (cell["completion_tokens"] / max_completion)
        color = OUTCOME_COLORS[cell["outcome"]]
        stroke = "#EF6C00" if cell["num_exhausted_context_windows"] else "#263238"
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" stroke="{stroke}"/>')
    parts.append(_text(left + chart_w / 2, 395, "prompt tokens", anchor="middle", klass="small"))
    parts.append(_text(20, 200, "completion tokens", klass="small"))
    return _svg_root(width, height, "Token use and efficiency", "Scatter plot of prompt and completion token counts.", "\n".join(parts))


def _render_runtime_interactions(report: Mapping[str, Any]) -> str:
    cells = [cell for cell in report["cells"] if cell["duration_seconds"] is not None]
    width, height = 780, 420
    left, bottom, top = 80, 335, 65
    chart_w, chart_h = 610, bottom - top
    max_duration = max([cell["duration_seconds"] or 0 for cell in cells] + [1])
    max_asks = max([cell["num_user_asks"] for cell in cells] + [1])
    parts = [
        _text(20, 30, "Runtime and interaction intensity", klass="title"),
        _text(20, 52, "Duration is official end-to-end task time in seconds.", klass="small"),
        f'<line x1="{left}" y1="{bottom}" x2="{left+chart_w}" y2="{bottom}" class="axis"/>',
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" class="axis"/>',
    ]
    if not cells:
        parts.append(_text(120, 180, "No structured duration values were present.", klass="small"))
    for cell in cells:
        x = left + chart_w * ((cell["duration_seconds"] or 0) / max_duration)
        y = bottom - chart_h * (cell["num_user_asks"] / max_asks)
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{OUTCOME_COLORS[cell["outcome"]]}"/>')
    parts.append(_text(left + chart_w / 2, 390, "duration seconds", anchor="middle", klass="small"))
    return _svg_root(width, height, "Runtime and interaction intensity", "Scatter plot of duration and Aider user asks.", "\n".join(parts))


def _render_completeness(report: Mapping[str, Any]) -> str:
    rows = report["summaries"]["evidence_completeness"]
    scopes = []
    requirements = []
    for row in rows:
        if row["scope"] not in scopes:
            scopes.append(row["scope"])
        if row["requirement"] not in requirements:
            requirements.append(row["requirement"])
    status = {(row["scope"], row["requirement"]): row["status"] for row in rows}
    cell_w, cell_h = 34, 24
    left, top = 270, 78
    width = max(840, left + len(scopes) * cell_w + 70)
    height = max(320, top + len(requirements) * cell_h + 65)
    color = {"complete": "#2E7D32", "incomplete": "#EF6C00", "missing": "#FFFFFF"}
    glyph = {"complete": "Y", "incomplete": "!", "missing": "-"}
    parts = [
        _text(20, 30, "Evidence completeness matrix", klass="title"),
        _text(20, 52, "Complete, incomplete, and missing evidence by sample and final gate.", klass="small"),
    ]
    for col, scope in enumerate(scopes):
        parts.append(_text(left + col * cell_w + cell_w / 2, top - 12, scope.replace("sample-", "s"), anchor="middle", klass="small"))
    for row_idx, requirement in enumerate(requirements):
        y = top + row_idx * cell_h
        parts.append(_text(20, y + 16, requirement, klass="small"))
        for col, scope in enumerate(scopes):
            value = status.get((scope, requirement), "missing")
            x = left + col * cell_w
            parts.append(_rect(x, y, cell_w, cell_h, color[value], stroke="#607D8B"))
            parts.append(_text(x + cell_w / 2, y + 16, glyph[value], anchor="middle", klass="small"))
    return _svg_root(width, height, "Evidence completeness matrix", "Evidence completeness grid.", "\n".join(parts))


def _render_figures(report: Mapping[str, Any], figures_dir: Path) -> dict[str, str]:
    figures_dir.mkdir(parents=True, exist_ok=True)
    renderers: list[tuple[str, str]] = []
    if report["evidence"]["mode"] == "final":
        renderers.append(("01-four-metrics.svg", _render_four_metrics(report)))
    renderers.extend(
        [
            ("02-try1-matrix.svg", _render_matrix(report, try_name="try1")),
            ("03-try2-transition-matrix.svg", _render_matrix(report, try_name="try2")),
            ("04-task-difficulty.svg", _render_task_difficulty(report)),
            (
                "05-topic-category-performance.svg",
                _render_category_performance(
                    report,
                    summary_key="topic_categories",
                    field="topic_category",
                    title="Performance by topic category",
                    subtitle="Six stable, mutually-exclusive groups; each contains 3-6 official tasks.",
                ),
            ),
            (
                "06-difficulty-category-performance.svg",
                _render_category_performance(
                    report,
                    summary_key="difficulty_categories",
                    field="difficulty",
                    title="Performance by curated task difficulty",
                    subtitle="Stable 8/9/9 Easy, Medium, and Hard task-complexity groups; not model-derived.",
                ),
            ),
            ("07-retry-transitions.svg", _render_retry_transitions(report)),
            ("08-cumulative-coverage.svg", _render_coverage(report)),
            ("09-sample-stability.svg", _render_sample_stability(report)),
            ("10-outcome-patterns.svg", _render_outcome_patterns(report)),
            ("11-diagnostics.svg", _render_diagnostics(report)),
            ("12-token-efficiency.svg", _render_token_efficiency(report)),
            ("13-runtime-interactions.svg", _render_runtime_interactions(report)),
            ("14-evidence-completeness.svg", _render_completeness(report)),
        ]
    )
    paths = {}
    for name, content in renderers:
        path = figures_dir / name
        path.write_text(content, encoding="utf-8")
        paths[name] = f"figures/{name}"
    return paths


def _render_table(rows: Sequence[Mapping[str, Any]], columns: Sequence[str], *, limit: int | None = None) -> str:
    rendered = ["<table><thead><tr>"]
    for column in columns:
        rendered.append(f"<th>{html.escape(column)}</th>")
    rendered.append("</tr></thead><tbody>")
    for row in rows[:limit]:
        rendered.append("<tr>")
        for column in columns:
            value = row.get(column, "")
            if isinstance(value, float):
                text = f"{value:.6g}"
            elif isinstance(value, (list, dict)):
                text = _json_dumps(value)
            else:
                text = str(value)
            rendered.append(f"<td>{html.escape(text)}</td>")
        rendered.append("</tr>")
    rendered.append("</tbody></table>")
    return "".join(rendered)


def _render_html(report: Mapping[str, Any], figure_paths: Mapping[str, str]) -> str:
    warning = report["evidence"].get("partial_warning")
    metrics = report["final_metrics"] or report["partial_diagnostics"]
    metric_rows = [{"metric": key, "value": value} for key, value in metrics.items()]
    figure_html = "\n".join(
        f'<section><h2>{html.escape(name)}</h2><img src="{html.escape(path)}" alt="{html.escape(name)}"></section>'
        for name, path in figure_paths.items()
    )
    banner = f'<div class="banner">{html.escape(warning)}</div>' if warning else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{html.escape(report["run"]["run_id"])} Aider visualization</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; color: #263238; font-size: 14px; }}
h1, h2 {{ color: #102027; }}
.banner {{ border: 2px solid #EF6C00; background: #FFF3E0; padding: 12px; font-weight: 700; }}
.meta {{ display: grid; grid-template-columns: repeat(2, minmax(240px, 1fr)); gap: 8px; }}
table {{ border-collapse: collapse; margin: 12px 0; width: 100%; }}
th, td {{ border: 1px solid #CFD8DC; padding: 4px 6px; text-align: left; vertical-align: top; }}
th {{ background: #ECEFF1; cursor: pointer; }}
img {{ max-width: 100%; height: auto; border: 1px solid #ECEFF1; }}
code {{ background: #ECEFF1; padding: 1px 3px; }}
@media print {{ .banner {{ break-inside: avoid; }} section {{ break-inside: avoid; }} }}
</style>
<script>
function sortTable(table, col) {{
  const body = table.tBodies[0];
  Array.from(body.rows).sort((a,b) => a.cells[col].innerText.localeCompare(b.cells[col].innerText, undefined, {{numeric:true}})).forEach(r => body.appendChild(r));
}}
window.addEventListener('DOMContentLoaded', () => {{
  document.querySelectorAll('th').forEach((th) => th.addEventListener('click', () => sortTable(th.closest('table'), th.cellIndex)));
}});
</script>
</head>
<body>
<h1>Independent Aider Visualization</h1>
{banner}
<p>{html.escape(INDEPENDENT_RESULT_LABEL)}.</p>
<div class="meta">
<div><strong>Run:</strong> {html.escape(report["run"]["run_id"])}</div>
<div><strong>Evidence mode:</strong> {html.escape(report["evidence"]["mode"])}</div>
<div><strong>Model:</strong> {html.escape(report["run"]["model_repo"])}@{html.escape(report["run"]["model_revision"])}</div>
<div><strong>Completed samples:</strong> {report["evidence"]["completed_samples"]}/8</div>
<div><strong>Completed cells:</strong> {report["evidence"]["completed_cells"]}/{report["evidence"]["expected_cells_final"]}</div>
<div><strong>Config fingerprint:</strong> <code>{html.escape(report["run"]["config_fingerprint"])}</code></div>
</div>
<h2>Headline Values</h2>
{_render_table(metric_rows, ["metric", "value"])}
<h2>Task Taxonomy And Difficulty</h2>
<p>Topics are six stable, mutually-exclusive groups of 3-6 tasks. Easy/Medium/Hard is a stable repo-owned task-complexity label, not a label inferred from this run's model outcomes.</p>
{_render_table(report["summaries"]["tasks"], ["task_id", "topic_category", "difficulty", "try1_successes", "try2_successes", "recovered_on_try2"])}
<h3>Topic Summary</h3>
{_render_table(report["summaries"]["topic_categories"], ["topic_category", "task_count", "task_ids", "try1_success_rate", "try2_success_rate", "task_coverage_try1", "task_coverage_try2"])}
<h3>Difficulty Summary</h3>
{_render_table(report["summaries"]["difficulty_categories"], ["difficulty", "task_count", "task_ids", "try1_success_rate", "try2_success_rate", "task_coverage_try1", "task_coverage_try2"])}
{figure_html}
<h2>Cell Evidence</h2>
<p>Rows link to hashes and structured fields only; chat history and generated content are not embedded.</p>
{_render_table(report["cells"], CELL_COLUMNS, limit=None)}
<h2>Methodology And Limits</h2>
<p>Try 2 is cumulative within the same trajectory. Raw Aider pass_rate_1 and pass_rate_2 remain per-trajectory Aider statistics and are not renamed. Intermediate breadth values are not final benchmark metrics.</p>
</body>
</html>
"""


def _render_markdown(report: Mapping[str, Any], figure_paths: Mapping[str, str]) -> str:
    lines = [
        "# Independent Aider Visualization",
        "",
        INDEPENDENT_RESULT_LABEL + ".",
        "",
    ]
    warning = report["evidence"].get("partial_warning")
    if warning:
        lines.extend([f"**{warning}**", ""])
    lines.extend(
        [
            f"- Run: `{report['run']['run_id']}`",
            f"- Evidence mode: `{report['evidence']['mode']}`",
            f"- Completed samples: {report['evidence']['completed_samples']}/8",
            f"- Completed cells: {report['evidence']['completed_cells']}/{report['evidence']['expected_cells_final']}",
            "",
            "## Headline Values",
            "",
        ]
    )
    metrics = report["final_metrics"] or report["partial_diagnostics"]
    for key, value in metrics.items():
        lines.append(f"- `{key}`: {value:.12g}")
    lines.extend(
        [
            "",
            "## Task Taxonomy And Difficulty",
            "",
            "The six topic groups are stable and mutually exclusive. Easy/Medium/Hard is a "
            "repo-owned task-complexity label, not a label inferred from this run's outcomes.",
            "",
            "| Task | Topic | Difficulty | Try 1 | Cumulative try 2 |",
            "|---|---|---|---:|---:|",
        ]
    )
    for task in sorted(report["summaries"]["tasks"], key=lambda row: row["task_id"]):
        lines.append(
            f"| {task['task_id']} | {task['topic_category']} | {task['difficulty']} | "
            f"{task['try1_successes']}/{task['completed_samples']} | "
            f"{task['try2_successes']}/{task['completed_samples']} |"
        )
    lines.extend(["", "## Figures", ""])
    for name, path in figure_paths.items():
        lines.append(f"![{name}]({path})")
    lines.extend(
        [
            "",
            "## Methodology",
            "",
            "Try 2 is cumulative within the same trajectory. Raw Aider `pass_rate_1` "
            "and `pass_rate_2` are preserved as Aider statistics and are not renamed.",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_data_tables(report: Mapping[str, Any], data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    write_json(data_dir / "report.normalized.json", report)
    _write_csv(data_dir / "cells.csv", report["cells"], CELL_COLUMNS)
    _write_csv(
        data_dir / "tasks.csv",
        report["summaries"]["tasks"],
        [
            "task_id",
            "topic_category",
            "difficulty",
            "completed_samples",
            "try1_successes",
            "try2_successes",
            "recovered_on_try2",
            "final_failures",
            "pattern",
        ],
    )
    _write_csv(
        data_dir / "topic-categories.csv",
        report["summaries"]["topic_categories"],
        [
            "topic_category",
            "task_count",
            "task_ids",
            "trajectory_count",
            "try1_successes",
            "try2_successes",
            "try1_success_rate",
            "try2_success_rate",
            "recovered_on_try2",
            "task_coverage_try1",
            "task_coverage_try2",
        ],
    )
    _write_csv(
        data_dir / "difficulty-categories.csv",
        report["summaries"]["difficulty_categories"],
        [
            "difficulty",
            "task_count",
            "task_ids",
            "trajectory_count",
            "try1_successes",
            "try2_successes",
            "try1_success_rate",
            "try2_success_rate",
            "recovered_on_try2",
            "task_coverage_try1",
            "task_coverage_try2",
        ],
    )
    _write_csv(
        data_dir / "samples.csv",
        report["summaries"]["samples"],
        [
            "sample_index",
            "seed",
            "task_count",
            "try1_successes",
            "try2_successes",
            "try1_success_rate",
            "try2_success_rate",
            "recovered_on_try2",
            "final_failures",
            "aider_pass_rate_1",
            "aider_pass_rate_2",
        ],
    )
    _write_csv(
        data_dir / "coverage-by-prefix.csv",
        report["summaries"]["coverage_by_prefix"],
        [
            "sample_prefix",
            "seed",
            "coverage_try1",
            "coverage_try2",
            "new_tasks_try1",
            "new_tasks_try2",
        ],
    )
    _write_csv(
        data_dir / "retry-transitions.csv",
        report["summaries"]["retry_transitions"],
        [
            "scope",
            "passed_initially",
            "recovered_on_try2",
            "failed_after_try2",
            "total_cells",
            "retry_recovery_rate",
        ],
    )
    _write_csv(
        data_dir / "diagnostics.csv",
        report["summaries"]["diagnostics"],
        ["diagnostic", "cells_with_flag", "total_count", "cell_rate"],
    )
    _write_csv(
        data_dir / "evidence-completeness.csv",
        report["summaries"]["evidence_completeness"],
        ["scope", "requirement", "status"],
    )


def _build_report_manifest(output_root: Path, report: Mapping[str, Any]) -> dict[str, Any]:
    files = []
    for path in sorted(item for item in output_root.rglob("*") if item.is_file()):
        relative = path.relative_to(output_root).as_posix()
        if relative == "visualization_manifest.json":
            continue
        files.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "schema_version": VISUALIZATION_SCHEMA_VERSION,
        "generator_version": GENERATOR_VERSION,
        "evidence_mode": report["evidence"]["mode"],
        "run_id": report["run"]["run_id"],
        "config_fingerprint": report["run"]["config_fingerprint"],
        "source_manifest_sha256": report["evidence"].get("source_manifest_sha256"),
        "files": files,
    }


def _prepare_output_root(output_root: Path, run_root: Path, *, overwrite: bool) -> Path:
    output = output_root.resolve()
    run = run_root.resolve()
    if output == run or run in output.parents:
        raise ModalAiderError("visualization output must not be inside the canonical run tree")
    if output.exists():
        if not overwrite:
            raise ModalAiderError("output path already exists; pass --overwrite to replace it")
        manifest_path = output / "visualization_manifest.json"
        if not manifest_path.is_file():
            raise ModalAiderError("refusing to overwrite output without visualization manifest")
        manifest = _read_json(manifest_path)
        if (
            not isinstance(manifest, dict)
            or manifest.get("generator_version") not in COMPATIBLE_OVERWRITE_GENERATORS
        ):
            raise ModalAiderError("refusing to overwrite output from another generator")
        shutil.rmtree(output)
    tmp = output.with_name(f".{output.name}.tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    return tmp


def _commit_output(tmp_output: Path, output_root: Path) -> None:
    output = output_root.resolve()
    tmp_output.replace(output)


def generate_visualization_report(
    *,
    run_root: str | Path,
    output_root: str | Path,
    allow_partial: bool = False,
    overwrite: bool = False,
    secret_sentinels: Sequence[str] = (),
) -> dict[str, Any]:
    run = Path(run_root).resolve()
    output = Path(output_root).resolve()
    if output == run or run in output.parents:
        raise ModalAiderError("visualization output must not be inside the canonical run tree")
    if not run.is_dir():
        raise ModalAiderError("run root does not exist")
    config = _load_config_from_run_root(run)
    protocol_root = run / INDEPENDENT_EVAL_MODE
    if not protocol_root.is_dir():
        raise ModalAiderError("run root has no independent-pass-at-1-and-8 evidence")
    expected_tasks = config.expected_cpp_tasks
    final_ready = all((protocol_root / name).is_file() for name in (
        "pass-at-1-and-8-by-try.json",
        "success-matrix.try1.json",
        "success-matrix.try2.json",
        "samples.jsonl",
    )) and (run / "run_receipt.json").is_file() and (run / "artifact_manifest.json").is_file()
    if final_ready:
        indices = list(range(1, INDEPENDENT_SAMPLES_PER_TASK + 1))
        cells, samples, result_dirs = _load_samples(
            config, run, sample_indices=indices, expected_tasks=expected_tasks
        )
        final_admission = _validate_final(
            config, run, result_dirs=result_dirs, expected_tasks=expected_tasks
        )
        mode = "final"
    else:
        if not allow_partial:
            raise ModalAiderError("evidence is incomplete; pass --allow-partial for diagnostics")
        indices = _complete_sample_indices(protocol_root)
        if not indices:
            raise ModalAiderError("partial mode requires at least sample-01")
        if indices != list(range(1, len(indices) + 1)) or len(indices) >= INDEPENDENT_SAMPLES_PER_TASK:
            raise ModalAiderError("partial mode requires a contiguous prefix shorter than eight samples")
        cells, samples, _ = _load_samples(
            config, run, sample_indices=indices, expected_tasks=expected_tasks
        )
        final_admission = None
        mode = "partial"
    report = _build_normalized_report(
        config=config,
        run_root=run,
        mode=mode,
        cells=cells,
        sample_rows=samples,
        final_admission=final_admission,
    )
    ensure_secret_free(report, secret_sentinels)
    tmp = _prepare_output_root(Path(output_root), run, overwrite=overwrite)
    try:
        _write_data_tables(report, tmp / "data")
        figure_paths = _render_figures(report, tmp / "figures")
        html_text = _render_html(report, figure_paths)
        markdown_text = _render_markdown(report, figure_paths)
        ensure_secret_free(html_text, secret_sentinels)
        ensure_secret_free(markdown_text, secret_sentinels)
        (tmp / "index.html").write_text(html_text, encoding="utf-8")
        (tmp / "report.md").write_text(markdown_text, encoding="utf-8")
        manifest = _build_report_manifest(tmp, report)
        ensure_secret_free(manifest, secret_sentinels)
        write_json(tmp / "visualization_manifest.json", manifest)
        _commit_output(tmp, Path(output_root))
    except Exception:
        if tmp.exists():
            shutil.rmtree(tmp)
        raise
    return report


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--secret-sentinel", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        report = generate_visualization_report(
            run_root=args.run_root,
            output_root=args.output_root,
            allow_partial=args.allow_partial,
            overwrite=args.overwrite,
            secret_sentinels=args.secret_sentinel,
        )
    except ModalAiderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"status: {report['evidence']['mode']}")
    print(f"run_id: {report['run']['run_id']}")
    print(f"completed_samples: {report['evidence']['completed_samples']}/8")
    print(f"output: {Path(args.output_root).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
