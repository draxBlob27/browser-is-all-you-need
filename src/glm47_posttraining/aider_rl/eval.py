"""Aider-specific evaluation aggregation without PIE runtime semantics."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any, Iterable


def aggregate_eval_records(records: Iterable[dict[str, Any]], *, label: str) -> dict[str, Any]:
    rows = list(records)
    removed = [row for row in rows if bool(row.get("infrastructure_error"))]
    policy_rows = [row for row in rows if not bool(row.get("infrastructure_error"))]
    trajectories: dict[tuple[str, Any, Any], list[dict[str, Any]]] = defaultdict(list)
    for ordinal, row in enumerate(policy_rows):
        trajectories[_trajectory_key(row, ordinal)].append(row)
    first_edit_rows = [
        min(items, key=lambda row: int(row.get("round_number", 1)))
        for items in trajectories.values()
    ]
    eventual_rows = []
    for items in trajectories.values():
        final = dict(max(items, key=lambda row: int(row.get("round_number", 1))))
        final["full_success"] = any(bool(row.get("full_success")) for row in items)
        eventual_rows.append(final)
    one_shot_successes = sum(bool(row.get("full_success")) for row in first_edit_rows)
    eventual_successes = sum(
        any(bool(row.get("full_success")) for row in items) for items in trajectories.values()
    )
    repair_eligible = []
    for items in trajectories.values():
        first = min(items, key=lambda row: int(row.get("round_number", 1)))
        repairs = [row for row in items if int(row.get("round_number", 1)) == 2]
        if not bool(first.get("full_success")) and repairs:
            repair_eligible.append(max(repairs, key=lambda row: int(row.get("round_number", 1))))
    first_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    eventual_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in first_edit_rows:
        first_by_task[str(row.get("task_id") or "")].append(row)
    for row in eventual_rows:
        eventual_by_task[str(row.get("task_id") or "")].append(row)
    first_task_any = sum(
        any(bool(row.get("full_success")) for row in task_rows)
        for task_rows in first_by_task.values()
    )
    eventual_task_any = sum(
        any(bool(row.get("full_success")) for row in task_rows)
        for task_rows in eventual_by_task.values()
    )
    format_valid = sum(bool(row.get("format_valid")) for row in policy_rows)
    allowed_file_compliance = sum(
        bool(row.get("allowed_file_compliance")) for row in policy_rows
    )
    reward_rows = [row for row in policy_rows if row.get("score") is not None]
    rewards = [float(row["score"]) for row in reward_rows]
    reason_counts = Counter(str(row.get("reason") or "unknown") for row in rows)
    infrastructure_reason_counts = Counter(
        str(row.get("infrastructure_reason") or "unknown") for row in removed
    )
    family: dict[str, list[bool]] = defaultdict(list)
    capability: dict[str, list[bool]] = defaultdict(list)
    rubric_scores: dict[str, list[float]] = defaultdict(list)
    for row in eventual_rows:
        family[str(row.get("family_id") or "unknown")].append(bool(row.get("full_success")))
        for tag in row.get("capability_tags") or ["unknown"]:
            capability[str(tag)].append(bool(row.get("full_success")))
        for rubric_id, score in (row.get("rubric_scores") or {}).items():
            rubric_scores[str(rubric_id)].append(float(score))
    return {
        "label": label,
        "sample_count": len(rows),
        "trajectory_count": len(trajectories),
        "task_count": len(eventual_by_task),
        "strict_one_shot_pass_rate": _ratio(one_shot_successes, len(first_edit_rows)),
        "cumulative_correct_rate": _ratio(eventual_successes, len(trajectories)),
        "cumulative_second_edit_correctness": _ratio(eventual_successes, len(trajectories)),
        "repair_conversion_rate": _ratio(
            sum(bool(row.get("full_success")) for row in repair_eligible), len(repair_eligible)
        ),
        "empirical_pass_at_group_try1": _ratio(first_task_any, len(first_by_task)),
        "empirical_pass_at_group": _ratio(eventual_task_any, len(eventual_by_task)),
        "format_compliance_rate": _ratio(format_valid, len(policy_rows)),
        "allowed_file_compliance_rate": _ratio(allowed_file_compliance, len(policy_rows)),
        "configure_pass_rate": _rate(policy_rows, "configure_pass"),
        "compile_pass_rate": _rate(policy_rows, "compile_pass"),
        "visible_pass_rate": _rate(policy_rows, "visible_pass"),
        "hidden_pass_rate": _rate(policy_rows, "hidden_pass"),
        "sanitizer_pass_rate": _rate(policy_rows, "sanitizer_pass"),
        "removed_infrastructure_failures": len(removed),
        "infrastructure_failure_rate": _ratio(len(removed), len(rows)),
        "reward_mean": sum(rewards) / len(rewards) if rewards else None,
        "reward_stddev": _stddev(rewards),
        "reason_counts": dict(sorted(reason_counts.items())),
        "infrastructure_reason_counts": dict(sorted(infrastructure_reason_counts.items())),
        "response_tokens_mean": _mean_present(policy_rows, "response_tokens"),
        "context_exhaustion_rate": _rate(policy_rows, "context_exhausted"),
        "grader_latency_s_mean": _mean_present(policy_rows, "grader_latency_s"),
        "grader_throughput_per_s": _throughput(policy_rows),
        "family_results": {key: _ratio(sum(values), len(values)) for key, values in sorted(family.items())},
        "capability_results": {
            key: _ratio(sum(values), len(values)) for key, values in sorted(capability.items())
        },
        "rubric_results": {
            key: sum(values) / len(values) for key, values in sorted(rubric_scores.items())
        },
    }


def _trajectory_key(row: dict[str, Any], ordinal: int) -> tuple[str, Any, Any]:
    sample = row.get("sample_index")
    if sample is None:
        sample = row.get("index")
    if sample is None:
        sample = ordinal
    return (str(row.get("task_id") or ""), row.get("rollout_id"), sample)


def zero_variance_group_fraction(records: Iterable[dict[str, Any]]) -> float | None:
    groups: dict[tuple[str, Any], list[float]] = defaultdict(list)
    for row in records:
        if row.get("score") is None or row.get("infrastructure_error"):
            continue
        groups[(str(row.get("task_id") or ""), row.get("rollout_id"))].append(float(row["score"]))
    if not groups:
        return None
    zero = sum(max(values) == min(values) for values in groups.values())
    return zero / len(groups)


def _rate(rows: list[dict[str, Any]], key: str) -> float | None:
    eligible = [row for row in rows if not row.get("infrastructure_error")]
    return _ratio(sum(bool(row.get(key)) for row in eligible), len(eligible))


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _stddev(values: list[float]) -> float | None:
    if not values:
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _mean_present(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return sum(values) / len(values) if values else None


def _throughput(rows: list[dict[str, Any]]) -> float | None:
    latencies = [float(row["grader_latency_s"]) for row in rows if row.get("grader_latency_s")]
    return len(latencies) / sum(latencies) if latencies and sum(latencies) > 0 else None
