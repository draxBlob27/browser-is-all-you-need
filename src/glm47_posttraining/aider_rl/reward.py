"""Versioned correctness-only reward for Aider whole-file C++ edits."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

from .parser import ParsedEdit, WholeEditParseError, parse_whole_edit
from .schema import AiderHarnessResult, AiderTask, REWARD_POLICY_VERSION


Runner = Callable[[AiderTask, Mapping[str, str], Path], AiderHarnessResult]


class RewardInfrastructureError(RuntimeError):
    """Grader infrastructure failed; the sample must not receive policy reward."""


@dataclass(frozen=True)
class RubricScore:
    rubric_id: str
    score: float
    weight: float
    critical: bool


@dataclass(frozen=True)
class RewardBreakdown:
    reward: float
    reason: str
    format_valid: bool
    parsed_edit: ParsedEdit | None = None
    harness: AiderHarnessResult | None = None
    rubric_scores: tuple[RubricScore, ...] = ()
    reward_policy_version: str = REWARD_POLICY_VERSION
    round_number: int = 1


def compute_reward(
    task: AiderTask,
    model_output: str,
    *,
    task_tree: str | Path,
    runner: Runner | None = None,
    round_number: int = 1,
) -> RewardBreakdown:
    """Parse and grade a one-shot or explicitly identified repair response."""

    try:
        parsed = parse_whole_edit(
            model_output,
            task.allowed_paths,
            max_bytes_by_path={item.path: item.max_bytes for item in task.editable_files},
        )
    except WholeEditParseError as exc:
        return RewardBreakdown(
            reward=-1.0,
            reason=exc.reason,
            format_valid=False,
            round_number=round_number,
        )

    if runner is None:
        from .sandbox import run_in_sandbox

        runner = run_in_sandbox
    harness = runner(task, parsed.files, Path(task_tree))
    if harness.infrastructure_error:
        raise RewardInfrastructureError(harness.infrastructure_reason or "unknown grader failure")
    if harness.unsafe_edit:
        return _result(-1.0, "unsafe_edit", parsed, harness, round_number)
    if harness.configure_error:
        return _result(-0.5, "configure_error", parsed, harness, round_number)
    if harness.compile_error:
        return _result(-0.5, "compile_error", parsed, harness, round_number)
    if harness.timeout:
        return _result(-0.5, "timeout", parsed, harness, round_number)
    rubric_scores, semantic_progress = _score_rubrics(task, harness)
    if not harness.normal_all_pass:
        return _result(
            -0.2 + 0.4 * semantic_progress,
            "tests_failed",
            parsed,
            harness,
            round_number,
            rubric_scores,
        )
    if harness.sanitizer_error or not (
        harness.sanitizer_visible.passed
        and harness.sanitizer_hidden.passed
        and _sanitizer_rubrics_pass(task, harness)
    ):
        return _result(0.3, "sanitizer_failed", parsed, harness, round_number, rubric_scores)
    if round_number > 1:
        return _result(
            0.8, "correct_after_repair", parsed, harness, round_number, rubric_scores
        )
    return _result(1.0, "correct", parsed, harness, round_number, rubric_scores)


def _result(
    reward: float,
    reason: str,
    parsed: ParsedEdit,
    harness: AiderHarnessResult,
    round_number: int,
    rubric_scores: tuple[RubricScore, ...] = (),
) -> RewardBreakdown:
    return RewardBreakdown(
        reward=reward,
        reason=reason,
        format_valid=True,
        parsed_edit=parsed,
        harness=harness,
        rubric_scores=rubric_scores,
        round_number=round_number,
    )


def _score_rubrics(
    task: AiderTask, harness: AiderHarnessResult
) -> tuple[tuple[RubricScore, ...], float]:
    """Score behavior groups so raw test-case counts cannot dominate task reward."""

    actual = {item.rubric_id: item for item in harness.rubric_results}
    expected_ids = {item.rubric_id for item in task.rubrics}
    if set(actual) != expected_ids:
        raise RewardInfrastructureError("grader rubric result set differs from admitted task")
    scores: list[RubricScore] = []
    passed_by_visibility = {"visible": 0, "hidden": 0}
    for rubric in task.rubrics:
        evidence = actual[rubric.rubric_id]
        passed = 0
        expected = 0
        for group in rubric.test_groups:
            stage = getattr(evidence, f"normal_{group.visibility}")
            if stage.discovered != group.expected_count:
                raise RewardInfrastructureError(
                    f"rubric discovery differs from admission: {rubric.rubric_id}"
                )
            expected += group.expected_count
            passed += min(stage.passed_tests, group.expected_count)
            passed_by_visibility[group.visibility] += min(
                stage.passed_tests, group.expected_count
            )
        score = passed / expected
        scores.append(
            RubricScore(
                rubric_id=rubric.rubric_id,
                score=score,
                weight=rubric.weight,
                critical=rubric.critical,
            )
        )
    if passed_by_visibility["visible"] != harness.normal_visible.passed_tests:
        raise RewardInfrastructureError("visible aggregate and rubric results disagree")
    if passed_by_visibility["hidden"] != harness.normal_hidden.passed_tests:
        raise RewardInfrastructureError("hidden aggregate and rubric results disagree")
    weighted = sum(item.weight * item.score for item in scores) / sum(
        item.weight for item in scores
    )
    if any(item.critical and item.score < 1.0 for item in scores):
        weighted = min(weighted, 0.5)
    return tuple(scores), weighted


def _sanitizer_rubrics_pass(task: AiderTask, harness: AiderHarnessResult) -> bool:
    actual = {item.rubric_id: item for item in harness.rubric_results}
    for rubric in task.rubrics:
        evidence = actual[rubric.rubric_id]
        for group in rubric.test_groups:
            stage = getattr(evidence, f"sanitizer_{group.visibility}")
            if stage.discovered != group.expected_count:
                raise RewardInfrastructureError(
                    f"sanitizer rubric discovery differs from admission: {rubric.rubric_id}"
                )
            if not stage.passed:
                return False
    return True
