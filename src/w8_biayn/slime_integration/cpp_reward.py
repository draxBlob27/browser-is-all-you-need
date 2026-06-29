"""Bridge SLIME JSONL rows to the repo-owned C++ reward harness."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..cpp_perf.reward import Runner, compute_reward
from ..cpp_perf.schema import CppTask


class SlimeCppRewardError(ValueError):
    """Raised when a SLIME C++ row is missing task metadata needed for scoring."""


def slime_cpp_metadata(row: Mapping[str, Any]) -> Mapping[str, Any]:
    """Extract and validate the SLIME metadata payload from one JSONL row."""

    metadata = row.get("metadata")
    if not isinstance(metadata, Mapping):
        raise SlimeCppRewardError("SLIME C++ row is missing a metadata mapping")
    return metadata


def resolve_slime_cpp_task_path(
    row: Mapping[str, Any],
    *,
    bundle_root: str | Path | None = None,
) -> Path:
    """Resolve the task JSON path referenced by a SLIME C++ JSONL row."""

    metadata = slime_cpp_metadata(row)
    task_path = metadata.get("task_path")
    if not isinstance(task_path, str) or not task_path.strip():
        raise SlimeCppRewardError("SLIME C++ row metadata.task_path is required")

    candidate = Path(task_path)
    if not candidate.is_absolute():
        base = Path(bundle_root).resolve() if bundle_root is not None else Path.cwd()
        candidate = base / candidate
    candidate = candidate.resolve()
    if not candidate.is_file():
        raise FileNotFoundError(f"SLIME C++ task file does not exist: {candidate}")
    return candidate


def load_slime_cpp_task(
    row: Mapping[str, Any],
    *,
    bundle_root: str | Path | None = None,
) -> CppTask:
    """Load the referenced C++ task JSON for one SLIME prompt row."""

    return CppTask.read_json(resolve_slime_cpp_task_path(row, bundle_root=bundle_root))


def score_slime_cpp_row(
    row: Mapping[str, Any],
    model_output: str,
    *,
    bundle_root: str | Path | None = None,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Score a SLIME C++ prompt row with the repo-owned reward implementation."""

    metadata = slime_cpp_metadata(row)
    task_file = resolve_slime_cpp_task_path(row, bundle_root=bundle_root)
    task = CppTask.read_json(task_file)
    breakdown = compute_reward(task, model_output, runner=runner)
    harness = breakdown.harness
    code = breakdown.code or ""

    return {
        "reward": breakdown.reward,
        "reason": breakdown.reason,
        "format_valid": breakdown.format_valid,
        "label": row.get("label"),
        "task_id": metadata.get("task_id", task.task_id),
        "problem_id": metadata.get("problem_id", task.problem_id),
        "split": metadata.get("split", task.split),
        "task_path": metadata.get("task_path"),
        "task_file": str(task_file),
        "code": code,
        "candidate_bytes": len(code.encode("utf-8")),
        "compile_error": harness.compile_error if harness else False,
        "sanitizer_error": harness.sanitizer_error if harness else False,
        "timeout": harness.timeout if harness else False,
        "tests_passed": harness.tests_passed if harness else 0,
        "tests_total": harness.tests_total if harness else 0,
        "all_tests_pass": harness.all_tests_pass if harness else False,
        "fraction_tests_passed": harness.fraction_tests_passed if harness else 0.0,
        "runtime_cpu_ns": harness.runtime_cpu_ns if harness else None,
        "runtime_wall_ns": harness.runtime_wall_ns if harness else None,
        "reference_runtime_cpu_ns": harness.reference_runtime_cpu_ns if harness else None,
        "reference_runtime_wall_ns": harness.reference_runtime_wall_ns if harness else None,
        "runtime_speedup": harness.runtime_speedup if harness else None,
    }
