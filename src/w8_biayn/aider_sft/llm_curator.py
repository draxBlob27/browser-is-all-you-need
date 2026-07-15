"""Budgeted, resumable OpenAI-compatible authoring stages for novel task artifacts."""

from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .benchmark import EXPECTED_CPP_TASK_IDS
from .errors import AiderSftError
from .review import state_root
from .scaffold import (
    Blueprint,
    GenerationProvenance,
    NegativeSolution,
    TaskAuthorOutput,
    TestAuthorOutput,
)
from .schema import Difficulty, PrimaryCategory, Split
from .util import (
    atomic_write,
    canonical_json_bytes,
    fingerprint,
    read_json,
    sha256_bytes,
    write_json,
)


STAGE_TEMPLATE_VERSIONS = {
    "planner": "aider-sft-planner-v1",
    "task_author": "aider-sft-task-author-v1",
    "test_author": "aider-sft-test-author-v1",
    "adversarial_author": "aider-sft-adversarial-author-v1",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def usage_terms_payload(config_lock: dict[str, Any]) -> dict[str, Any]:
    llm = config_lock["config"]["llm"]
    return {
        "provider": llm["provider"],
        "model": llm["model"],
        "model_revision": llm["model_revision"],
        "terms_snapshot_sha256": llm["usage_terms_snapshot_sha256"],
        "terms_snapshot_date": llm["usage_terms_date"],
        "intended_use": "supervised fine-tuning",
        "distribution_scope": "internal_research",
        "policy": "generated artifacts receive no inferred open-source license",
    }


def capacity_report(
    *,
    config_lock: dict[str, Any],
    deficit_cells: dict[str, dict[str, int]],
    used_candidates: int = 0,
) -> dict[str, Any]:
    required = sum(max(value, 0) for cells in deficit_cells.values() for value in cells.values())
    budgets = config_lock["config"]["llm"]["budgets"]
    reserve = math.ceil(required * budgets["reserve_multiplier"])
    configured = budgets["total_candidates"]
    remaining = max(configured - used_candidates, 0)
    calls_required = reserve * budgets["calls_per_candidate"]
    problems: list[str] = []
    if remaining < reserve:
        problems.append("total_candidates")
    if budgets["total_calls"] < calls_required:
        problems.append("total_calls")
    for key in ("input_tokens", "output_tokens", "wall_time_seconds", "spend_amount"):
        if budgets[key] <= 0:
            problems.append(key)
    return {
        "schema_version": "aider-sft-capacity-report-v1",
        "required_llm_admissions": required,
        "reserve_multiplier": budgets["reserve_multiplier"],
        "minimum_candidate_capacity": reserve,
        "configured_candidate_capacity": configured,
        "used_candidate_capacity": used_candidates,
        "remaining_candidate_capacity": remaining,
        "minimum_stage_calls": calls_required,
        "configured_total_calls": budgets["total_calls"],
        "status": "sufficient" if not problems else "insufficient",
        "insufficient_fields": sorted(problems),
    }


def schedule_cells(deficits: dict[str, dict[str, int]]) -> list[dict[str, str]]:
    cells: list[dict[str, str]] = []
    difficulties = list(Difficulty)
    index = 0
    for category in PrimaryCategory:
        category_cells = deficits.get(category.value, {})
        for split in Split:
            for _ in range(max(category_cells.get(split.value, 0), 0)):
                cells.append(
                    {
                        "primary_category": category.value,
                        "intended_split": split.value,
                        "difficulty": difficulties[index % len(difficulties)].value,
                    }
                )
                index += 1
    return cells


def _stage_prompt(stage: str, inputs: dict[str, Any]) -> list[dict[str, str]]:
    constraints = (
        "C++17 only. Emit one strict JSON object and no prose. Do not emit CMake, build "
        "commands, shell files, dependencies, downloads, benchmark material, or reasoning."
    )
    if stage == "planner":
        instruction = (
            "Design a novel programming task from the supplied generic category and API-shape "
            "constraints. The prohibited IDs are names only; do not imitate them. Return the "
            "aider-sft-blueprint-v1 fields."
        )
    elif stage == "task_author":
        instruction = (
            "Materialize the blueprint as docs plus complete starter/reference/context file "
            "objects. Return aider-sft-task-author-v1. Do not emit tests."
        )
    elif stage == "test_author":
        instruction = (
            "In a fresh stateless context, author private Catch2 v2 tests from only the "
            "blueprint and public API. Return aider-sft-test-author-v1. Include test/catch.hpp. "
            "Do not emit or request a reference implementation."
        )
    elif stage == "adversarial_author":
        instruction = (
            "Author at least three independent, compileable wrong complete editable states "
            "from the blueprint and starter only. Return negative_solutions. Do not emit tests."
        )
    else:
        raise ValueError(stage)
    return [
        {"role": "system", "content": constraints},
        {
            "role": "user",
            "content": instruction
            + "\nINPUT JSON:\n"
            + json.dumps(inputs, sort_keys=True, ensure_ascii=False),
        },
    ]


def _budget_path(root: Path) -> Path:
    return state_root(root) / "generation/budget.json"


def _load_budget(root: Path) -> dict[str, Any]:
    path = _budget_path(root)
    if path.is_file():
        return read_json(path)
    return {
        "schema_version": "aider-sft-generation-budget-v1",
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_spend": 0.0,
        "wall_time_seconds": 0.0,
    }


def _check_budget(config_lock: dict[str, Any], usage: dict[str, Any]) -> None:
    if usage.get("usage_unreconciled"):
        raise AiderSftError(
            "llm_budget_exhausted",
            "provider usage is unreconciled; no additional paid calls are permitted",
        )
    limits = config_lock["config"]["llm"]["budgets"]
    comparisons = {
        "calls": "total_calls",
        "input_tokens": "input_tokens",
        "output_tokens": "output_tokens",
        "estimated_spend": "spend_amount",
        "wall_time_seconds": "wall_time_seconds",
    }
    exceeded = [
        observed
        for observed, configured in comparisons.items()
        if usage[observed] > limits[configured]
    ]
    if exceeded:
        raise AiderSftError(
            "llm_budget_exhausted", "budget exhausted: " + ", ".join(sorted(exceeded))
        )


def _call_stage(
    *,
    root: Path,
    candidate_id: str,
    stage: str,
    inputs: dict[str, Any],
    config_lock: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    llm = config_lock["config"]["llm"]
    messages = _stage_prompt(stage, inputs)
    request_value = {
        "model": llm["model"],
        "messages": messages,
        "response_format": {"type": "json_object"},
        **llm["decoding"],
    }
    request_id = fingerprint(
        "aider-sft-provider-request-v1",
        candidate_id,
        stage,
        llm["provider"],
        llm["model"],
        llm["model_revision"],
        request_value,
    )
    record_path = state_root(root) / "generation/requests" / f"{request_id}.json"
    if record_path.is_file():
        record = read_json(record_path)
        if record.get("status") == "completed":
            return record["normalized_output"], record
        raise AiderSftError(
            "llm_transport_failed",
            f"request {request_id} is reserved/ambiguous; reconcile before retry",
        )

    credential = os.environ.get(llm["credential_env"])
    if not credential:
        raise AiderSftError(
            "llm_transport_failed",
            f"credential environment variable is unset: {llm['credential_env']}",
        )
    usage = _load_budget(root)
    _check_budget(config_lock, {**usage, "calls": usage["calls"] + 1})
    reservation = {
        "schema_version": "aider-sft-provider-request-v1",
        "request_id": request_id,
        "candidate_id": candidate_id,
        "stage": stage,
        "status": "reserved",
        "provider": llm["provider"],
        "model": llm["model"],
        "model_revision": llm["model_revision"],
        "request": request_value,
        "request_sha256": sha256_bytes(canonical_json_bytes(request_value)),
        "reserved_at_utc": utc_now(),
    }
    write_json(record_path, reservation)
    body = canonical_json_bytes(request_value)
    request = urllib.request.Request(
        llm["endpoint"],
        data=body,
        headers={
            "Authorization": f"Bearer {credential}",
            "Content-Type": "application/json",
            "Idempotency-Key": request_id,
        },
        method="POST",
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            envelope = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        failure = {
            **reservation,
            "status": "ambiguous",
            "failure_type": type(exc).__name__,
            "failed_at_utc": utc_now(),
        }
        write_json(record_path, failure)
        raise AiderSftError(
            "llm_transport_failed",
            f"authoring request is ambiguous and will not be repeated: {request_id}",
        ) from exc
    elapsed = time.monotonic() - started
    envelope_hash = sha256_bytes(canonical_json_bytes(envelope))
    provider_model = ""
    try:
        if not isinstance(envelope, dict):
            raise TypeError("provider envelope must be an object")
        raw_model = envelope.get("model", "")
        provider_model = raw_model if isinstance(raw_model, str) else str(raw_model)
        provider_usage = envelope.get("usage")
        if not isinstance(provider_usage, dict):
            raise TypeError("provider usage must be an object")
        raw_input_tokens = provider_usage.get("prompt_tokens")
        raw_output_tokens = provider_usage.get("completion_tokens")
        if type(raw_input_tokens) is not int or raw_input_tokens < 0:
            raise ValueError("prompt_tokens must be a non-negative integer")
        if type(raw_output_tokens) is not int or raw_output_tokens < 0:
            raise ValueError("completion_tokens must be a non-negative integer")
        input_tokens = raw_input_tokens
        output_tokens = raw_output_tokens
    except (TypeError, ValueError) as exc:
        usage.update(
            {
                "calls": usage["calls"] + 1,
                "wall_time_seconds": usage["wall_time_seconds"] + elapsed,
                "usage_unreconciled": True,
            }
        )
        write_json(_budget_path(root), usage)
        write_json(
            record_path,
            {
                **reservation,
                "status": "completed_invalid_usage",
                "provider_envelope_sha256": envelope_hash,
                "provider_returned_model": provider_model,
                "token_usage": {"input": None, "output": None},
                "failure_type": type(exc).__name__,
                "completed_at_utc": utc_now(),
            },
        )
        raise AiderSftError(
            "llm_budget_exhausted",
            f"provider usage is invalid and requires operator reconciliation: {request_id}",
        ) from exc
    spend = (
        input_tokens * llm["input_cost_per_million"]
        + output_tokens * llm["output_cost_per_million"]
    ) / 1_000_000
    usage.update(
        {
            "calls": usage["calls"] + 1,
            "input_tokens": usage["input_tokens"] + input_tokens,
            "output_tokens": usage["output_tokens"] + output_tokens,
            "estimated_spend": usage["estimated_spend"] + spend,
            "wall_time_seconds": usage["wall_time_seconds"] + elapsed,
        }
    )
    write_json(_budget_path(root), usage)
    terminal = {
        **reservation,
        "provider_envelope_sha256": envelope_hash,
        "provider_returned_model": provider_model,
        "token_usage": {"input": input_tokens, "output": output_tokens},
        "completed_at_utc": utc_now(),
    }
    allowed_models = {llm["model"], llm["model_revision"]}
    if provider_model and provider_model not in allowed_models:
        write_json(
            record_path,
            {**terminal, "status": "completed_identity_mismatch"},
        )
        raise AiderSftError(
            "profile_not_frozen", f"provider model identity differs: {provider_model}"
        )
    try:
        content = envelope["choices"][0]["message"]["content"]
        normalized = json.loads(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        write_json(
            record_path,
            {
                **terminal,
                "status": "completed_invalid_response",
                "failure_type": type(exc).__name__,
            },
        )
        raise AiderSftError(
            "static_schema_error", "provider returned invalid structured output"
        ) from exc
    completed = {
        **terminal,
        "status": "completed",
        "normalized_output": normalized,
        "response_sha256": sha256_bytes(canonical_json_bytes(normalized)),
    }
    try:
        _check_budget(config_lock, usage)
    except AiderSftError:
        completed["status"] = "completed_budget_exceeded"
        write_json(record_path, completed)
        raise
    write_json(record_path, completed)
    return normalized, completed


def author_candidate(
    *,
    root: Path,
    candidate_id: str,
    cell: dict[str, str],
    config_lock: dict[str, Any],
    acknowledge_paid_calls: bool,
) -> dict[str, Any]:
    if not acknowledge_paid_calls:
        raise AiderSftError(
            "llm_usage_terms_unapproved", "paid authoring requires explicit acknowledgement"
        )
    planner_input = {
        **cell,
        "language_standard": "c++17",
        "desired_file_shape": "one to four editable C++ source/header files",
        "prohibited_task_ids": sorted(EXPECTED_CPP_TASK_IDS),
    }
    blueprint_raw, planner_record = _call_stage(
        root=root,
        candidate_id=candidate_id,
        stage="planner",
        inputs=planner_input,
        config_lock=config_lock,
    )
    try:
        blueprint = Blueprint.model_validate(blueprint_raw)
    except ValidationError as exc:
        raise AiderSftError("static_schema_error", str(exc)) from exc
    if (
        blueprint.primary_category.value != cell["primary_category"]
        or blueprint.difficulty.value != cell["difficulty"]
    ):
        raise AiderSftError("static_schema_error", "planner changed its scheduled cell")

    task_raw, task_record = _call_stage(
        root=root,
        candidate_id=candidate_id,
        stage="task_author",
        inputs={"blueprint": blueprint.model_dump(mode="json")},
        config_lock=config_lock,
    )
    test_raw, test_record = _call_stage(
        root=root,
        candidate_id=candidate_id,
        stage="test_author",
        inputs={
            "blueprint": blueprint.model_dump(mode="json"),
            "public_api": blueprint.public_api,
        },
        config_lock=config_lock,
    )
    try:
        task = TaskAuthorOutput.model_validate(task_raw)
        tests = TestAuthorOutput.model_validate(test_raw)
    except ValidationError as exc:
        raise AiderSftError("static_schema_error", str(exc)) from exc
    adversarial_raw, adversarial_record = _call_stage(
        root=root,
        candidate_id=candidate_id,
        stage="adversarial_author",
        inputs={
            "blueprint": blueprint.model_dump(mode="json"),
            "starter_files": [item.model_dump(mode="json") for item in task.starter_files],
        },
        config_lock=config_lock,
    )
    try:
        negatives = [
            NegativeSolution.model_validate(value)
            for value in adversarial_raw["negative_solutions"]
        ]
    except (KeyError, TypeError, ValidationError) as exc:
        raise AiderSftError("static_schema_error", str(exc)) from exc

    records = {
        "planner": planner_record,
        "task_author": task_record,
        "test_author": test_record,
        "adversarial_author": adversarial_record,
    }
    timestamps = {stage: record["completed_at_utc"] for stage, record in records.items()}
    token_usage = {
        "input": sum(record["token_usage"]["input"] for record in records.values()),
        "output": sum(record["token_usage"]["output"] for record in records.values()),
    }
    llm = config_lock["config"]["llm"]
    generation = GenerationProvenance(
        provider=llm["provider"],
        model=llm["model"],
        model_revision=llm["model_revision"],
        generation_run_id=f"{root.name}:{candidate_id}",
        prompt_template_sha256={
            stage: sha256_bytes(STAGE_TEMPLATE_VERSIONS[stage].encode()) for stage in records
        },
        request_sha256={stage: record["request_sha256"] for stage, record in records.items()},
        response_sha256={stage: record["response_sha256"] for stage, record in records.items()},
        decoding=llm["decoding"],
        token_usage=token_usage,
        attempt_count=1,
        revision_count=0,
        timestamps_utc=timestamps,
    )
    candidate = {
        "schema_version": "aider-sft-generated-candidate-v1",
        "candidate_id": candidate_id,
        "intended_split": cell["intended_split"],
        "blueprint": blueprint.model_dump(mode="json"),
        "task": task.model_dump(mode="json"),
        "tests": tests.model_dump(mode="json"),
        "negative_solutions": [item.model_dump(mode="json") for item in negatives],
        "generation": generation.model_dump(mode="json"),
    }
    candidate_path = root / "private/candidates" / candidate_id / "normalized-candidate.json"
    atomic_write(candidate_path, canonical_json_bytes(candidate))
    return candidate
