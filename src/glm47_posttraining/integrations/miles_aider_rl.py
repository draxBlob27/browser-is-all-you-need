"""Miles custom reward bridge for one-shot Aider whole-file C++ RL."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from glm47_posttraining.aider_rl.admission import verify_task_tree
from glm47_posttraining.aider_rl.reward import (
    RewardBreakdown,
    RewardInfrastructureError,
    compute_reward,
)
from glm47_posttraining.aider_rl.schema import AiderTask


DATA_ROOT_ENV = "MILES_AIDER_DATA_DIR"
TASKS_ROOT_ENV = "MILES_AIDER_TASKS_DIR"
REWARD_WORKERS_ENV = "GLM47_AIDER_REWARD_WORKERS"
INCLUDE_LOGS_ENV = "MILES_AIDER_INCLUDE_LOGS"
REWARD_RETRIES_ENV = "GLM47_AIDER_INFRASTRUCTURE_RETRIES"
DEFAULT_REWARD_WORKERS = 8
DEFAULT_INFRASTRUCTURE_RETRIES = 2


class AiderRewardConfigurationError(RuntimeError):
    """Immutable task metadata cannot be resolved safely on a reward worker."""


class AiderRewardInfrastructureExhausted(RuntimeError):
    """The grader remained unavailable after bounded retries; abort the rollout."""


async def reward_func(args: Any, sample: Any, **_kwargs: Any) -> dict[str, Any] | list[dict[str, Any]]:
    """Score a Miles sample or list while preserving one output per input."""

    if isinstance(sample, list):
        return _score_batch(sample)
    return _score_sample(sample)


def _score_batch(samples: list[Any]) -> list[dict[str, Any]]:
    workers = max(1, min(len(samples), _reward_workers()))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="aider-reward") as pool:
        return list(pool.map(_score_sample, samples))


def _score_sample(sample: Any) -> dict[str, Any]:
    metadata = _sample_metadata(sample)
    task_path = metadata.get("task_path")
    expected_digest = metadata.get("task_digest")
    if not isinstance(task_path, str) or not task_path:
        raise AiderRewardConfigurationError("metadata.task_path is required")
    if not isinstance(expected_digest, str) or not expected_digest:
        raise AiderRewardConfigurationError("metadata.task_digest is required")
    resolved = _resolve_task_path(task_path)
    task = AiderTask.read_json(resolved)
    if task.task_digest != expected_digest:
        raise AiderRewardConfigurationError("task digest is stale or mismatched")
    if metadata.get("task_id") != task.task_id:
        raise AiderRewardConfigurationError("task ID is stale or mismatched")
    tree = resolved.parent / "tree"
    verify_task_tree(task, tree)
    attempts = _infrastructure_retries() + 1
    last_error: RewardInfrastructureError | None = None
    for _attempt in range(attempts):
        try:
            breakdown = compute_reward(task, _sample_response(sample), task_tree=tree)
            return reward_record_from_breakdown(sample, task, breakdown)
        except RewardInfrastructureError as exc:
            last_error = exc
    raise AiderRewardInfrastructureExhausted(
        f"grader infrastructure failed after {attempts} attempts: {last_error}"
    ) from last_error


def reward_record_from_breakdown(
    sample: Any,
    task: AiderTask,
    breakdown: RewardBreakdown,
) -> dict[str, Any]:
    harness = breakdown.harness
    record: dict[str, Any] = {
        "score": breakdown.reward,
        "reward": breakdown.reward,
        "reason": breakdown.reason,
        "reward_policy_version": breakdown.reward_policy_version,
        "task_id": task.task_id,
        "family_id": task.family_id,
        "lineage_id": task.lineage_id,
        "capability_tags": task.capability_tags,
        "rubric_ids": [rubric.rubric_id for rubric in task.rubrics],
        "rubric_scores": {
            rubric.rubric_id: rubric.score for rubric in breakdown.rubric_scores
        },
        "split": task.split,
        "sample_index": _sample_index(sample),
        "rollout_id": _sample_value(sample, "rollout_id"),
        "round_number": breakdown.round_number,
        "format_valid": breakdown.format_valid,
        "allowed_file_compliance": breakdown.format_valid,
        "candidate_bytes": breakdown.parsed_edit.total_bytes if breakdown.parsed_edit else 0,
        "response_bytes": len(_sample_response(sample).encode("utf-8")),
        "response_tokens": _sample_value(sample, "response_tokens"),
        "context_exhausted": bool(_sample_value(sample, "context_exhausted")),
        "configure_pass": bool(harness and not harness.configure_error),
        "compile_pass": bool(harness and not harness.configure_error and not harness.compile_error),
        "visible_pass": bool(harness and harness.normal_visible.passed),
        "hidden_pass": bool(harness and harness.normal_hidden.passed),
        "sanitizer_pass": bool(harness and harness.full_success),
        "full_success": bool(harness and harness.full_success),
        "visible_passed": harness.normal_visible.passed_tests if harness else 0,
        "visible_total": harness.normal_visible.discovered if harness else 0,
        "hidden_passed": harness.normal_hidden.passed_tests if harness else 0,
        "hidden_total": harness.normal_hidden.discovered if harness else 0,
        "timeout": bool(harness and harness.timeout),
        "infrastructure_error": False,
        "grader_latency_s": _grader_latency(harness),
        "response": _sample_response(sample),
    }
    if harness and _include_logs():
        record["logs"] = harness.logs
    elif harness:
        record["log_keys"] = sorted(harness.logs)
    return record


def _resolve_task_path(task_path: str) -> Path:
    relative = Path(task_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise AiderRewardConfigurationError("task_path must be a contained relative path")
    roots = [os.environ.get(DATA_ROOT_ENV), os.environ.get(TASKS_ROOT_ENV)]
    for raw_root in roots:
        if not raw_root:
            continue
        root = Path(raw_root).resolve(strict=True)
        candidates = [root / relative]
        if raw_root == os.environ.get(TASKS_ROOT_ENV) and relative.parts[:1] == ("tasks",):
            candidates.append(root.joinpath(*relative.parts[1:]))
        for candidate in candidates:
            try:
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(root)
            except (FileNotFoundError, ValueError):
                continue
            if resolved.is_file():
                return resolved
    raise AiderRewardConfigurationError("task_path is not inside a configured immutable Aider root")


def _reward_workers() -> int:
    try:
        return max(1, int(os.environ.get(REWARD_WORKERS_ENV, str(DEFAULT_REWARD_WORKERS))))
    except ValueError:
        return DEFAULT_REWARD_WORKERS


def _infrastructure_retries() -> int:
    try:
        return max(0, int(os.environ.get(REWARD_RETRIES_ENV, str(DEFAULT_INFRASTRUCTURE_RETRIES))))
    except ValueError:
        return DEFAULT_INFRASTRUCTURE_RETRIES


def _include_logs() -> bool:
    return os.environ.get(INCLUDE_LOGS_ENV, "").lower() in {"1", "true", "yes", "on"}


def _sample_metadata(sample: Any) -> dict[str, Any]:
    value = sample.get("metadata") if isinstance(sample, dict) else getattr(sample, "metadata", None)
    return value if isinstance(value, dict) else {}


def _sample_response(sample: Any) -> str:
    value = sample.get("response") if isinstance(sample, dict) else getattr(sample, "response", "")
    return str(value or "")


def _sample_index(sample: Any) -> int | None:
    value = _sample_value(sample, "index")
    return value if isinstance(value, int) else None


def _sample_value(sample: Any, key: str) -> Any:
    return sample.get(key) if isinstance(sample, dict) else getattr(sample, key, None)


def _grader_latency(harness: Any) -> float | None:
    if harness is None:
        return None
    aggregate = sum(
        stage.duration_s
        for stage in (
            harness.normal_visible,
            harness.normal_hidden,
            harness.sanitizer_visible,
            harness.sanitizer_hidden,
        )
    )
    rubric = sum(
        stage.duration_s
        for result in harness.rubric_results
        for stage in (
            result.normal_visible,
            result.normal_hidden,
            result.sanitizer_visible,
            result.sanitizer_hidden,
        )
    )
    return aggregate + rubric
