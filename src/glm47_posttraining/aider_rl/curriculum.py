"""Failure-derived rubric catalog validation and no-update canary gates."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .admission import AdmissionError
from .schema import (
    AiderTaskDraft,
    AiderTask,
    RubricSpec,
    SAFE_ID_RE,
    canonical_sha256,
)


class CapabilityDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    capability: str
    target_weight: float = Field(gt=0.0, le=1.0)
    rationale: str = Field(min_length=1)

    @field_validator("capability")
    @classmethod
    def _safe_id(cls, value: str) -> str:
        if not SAFE_ID_RE.fullmatch(value):
            raise ValueError("capability must be a stable safe identifier")
        return value


class FailureModeDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    failure_mode_id: str
    capability: str
    observed_pattern: str = Field(min_length=1)
    abstract_defect: str = Field(min_length=1)
    clean_room_rule: str = Field(min_length=1)

    @field_validator("failure_mode_id", "capability")
    @classmethod
    def _safe_id(cls, value: str) -> str:
        if not SAFE_ID_RE.fullmatch(value):
            raise ValueError("failure-mode identity must be a stable safe identifier")
        return value


class RubricDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    rubric_id: str
    capability: str
    failure_mode_ids: list[str] = Field(min_length=1)
    desired_behavior: str = Field(min_length=1)
    undesirable_behaviors: list[str] = Field(min_length=1)
    critical: bool = False
    weight: float = Field(gt=0.0, le=100.0)

    @field_validator("rubric_id", "capability")
    @classmethod
    def _safe_id(cls, value: str) -> str:
        if not SAFE_ID_RE.fullmatch(value):
            raise ValueError("rubric identity must be a stable safe identifier")
        return value

    @field_validator("failure_mode_ids")
    @classmethod
    def _unique_failures(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("rubric failure-mode IDs must be unique")
        return values


class CurriculumCatalog(BaseModel):
    """Clean-room behavior catalog derived from aggregate SFT/eval failures."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    catalog_version: str
    derivation_policy: str = Field(min_length=1)
    capabilities: list[CapabilityDefinition] = Field(min_length=1)
    failure_modes: list[FailureModeDefinition] = Field(min_length=1)
    rubrics: list[RubricDefinition] = Field(min_length=1)

    @model_validator(mode="after")
    def _consistent(self) -> "CurriculumCatalog":
        capabilities = {item.capability for item in self.capabilities}
        if len(capabilities) != len(self.capabilities):
            raise ValueError("catalog capability IDs must be unique")
        if not math.isclose(sum(item.target_weight for item in self.capabilities), 1.0):
            raise ValueError("catalog capability target weights must sum to one")
        failures = {item.failure_mode_id: item for item in self.failure_modes}
        if len(failures) != len(self.failure_modes):
            raise ValueError("catalog failure-mode IDs must be unique")
        rubrics = {item.rubric_id: item for item in self.rubrics}
        if len(rubrics) != len(self.rubrics):
            raise ValueError("catalog rubric IDs must be unique")
        for failure in self.failure_modes:
            if failure.capability not in capabilities:
                raise ValueError("failure mode references an unknown capability")
        for rubric in self.rubrics:
            if rubric.capability not in capabilities:
                raise ValueError("rubric references an unknown capability")
            for failure_id in rubric.failure_mode_ids:
                failure = failures.get(failure_id)
                if failure is None:
                    raise ValueError("rubric references an unknown failure mode")
                if failure.capability != rubric.capability:
                    raise ValueError("rubric and failure mode capabilities differ")
        return self

    @property
    def fingerprint(self) -> str:
        return canonical_sha256(self.model_dump(mode="json"))

    @classmethod
    def read_json(cls, path: str | Path) -> "CurriculumCatalog":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


def resolve_task_rubrics(
    draft: AiderTaskDraft, catalog: CurriculumCatalog
) -> list[RubricSpec]:
    """Resolve task test groups against the immutable behavior catalog."""

    definitions = {item.rubric_id: item for item in catalog.rubrics}
    known_capabilities = {item.capability for item in catalog.capabilities}
    if not set(draft.capability_tags) <= known_capabilities:
        raise AdmissionError("task capability_tags reference an unknown catalog capability")
    resolved: list[RubricSpec] = []
    for binding in draft.rubrics:
        definition = definitions.get(binding.rubric_id)
        if definition is None:
            raise AdmissionError(f"task references unknown catalog rubric: {binding.rubric_id}")
        if definition.capability not in draft.capability_tags:
            raise AdmissionError(
                f"rubric capability is missing from task capability_tags: {binding.rubric_id}"
            )
        resolved.append(
            RubricSpec(
                **definition.model_dump(mode="json"),
                test_groups=binding.test_groups,
            )
        )
    return resolved


def verify_admitted_task_curriculum(task: AiderTask, catalog: CurriculumCatalog) -> None:
    """Prove resolved task behavior still matches the fingerprinted catalog."""

    if task.curriculum_fingerprint != catalog.fingerprint:
        raise AdmissionError("task curriculum fingerprint differs from catalog")
    definitions = {item.rubric_id: item for item in catalog.rubrics}
    for rubric in task.rubrics:
        definition = definitions.get(rubric.rubric_id)
        if definition is None:
            raise AdmissionError(f"admitted task has an unknown rubric: {rubric.rubric_id}")
        actual = rubric.model_dump(mode="json", exclude={"test_groups"})
        if actual != definition.model_dump(mode="json"):
            raise AdmissionError(f"admitted rubric differs from catalog: {rubric.rubric_id}")


def analyze_no_update_canary(
    records: Iterable[dict[str, Any]],
    catalog: CurriculumCatalog,
    *,
    group_size: int = 8,
    min_tasks: int = 16,
    max_tasks: int = 32,
    max_zero_variance_fraction: float = 0.5,
    max_infrastructure_failure_rate: float = 0.02,
    max_capability_weight_delta: float = 0.20,
) -> dict[str, Any]:
    """Fail closed when rollout groups cannot provide trustworthy GRPO signal."""

    rows = list(records)
    if not rows:
        raise AdmissionError("no no-update canary records were provided")
    groups: dict[tuple[str, Any], list[dict[str, Any]]] = defaultdict(list)
    task_capabilities: dict[str, tuple[str, ...]] = {}
    malformed_rubrics: list[str] = []
    for row in rows:
        task_id = str(row.get("task_id") or "")
        rollout_id = row.get("rollout_id")
        if not task_id or rollout_id is None:
            raise AdmissionError("canary rows require task_id and rollout_id")
        groups[(task_id, rollout_id)].append(row)
        capabilities = tuple(sorted(set(row.get("capability_tags") or [])))
        if not capabilities:
            raise AdmissionError("canary rows require capability_tags")
        previous = task_capabilities.setdefault(task_id, capabilities)
        if previous != capabilities:
            raise AdmissionError("capability_tags changed within a canary task")
        expected_rubrics = set(row.get("rubric_ids") or [])
        actual_scores = row.get("rubric_scores")
        if not isinstance(actual_scores, dict) or set(actual_scores) != expected_rubrics:
            malformed_rubrics.append(task_id)
        elif any(not 0.0 <= float(value) <= 1.0 for value in actual_scores.values()):
            malformed_rubrics.append(task_id)

    group_shape_failures = [
        f"{task_id}:{rollout_id}"
        for (task_id, rollout_id), items in groups.items()
        if len(items) != group_size
    ]
    infrastructure = [row for row in rows if row.get("infrastructure_error")]
    zero_variance = 0
    mixed = 0
    eligible_groups = 0
    for items in groups.values():
        scores = [float(row["score"]) for row in items if not row.get("infrastructure_error")]
        if len(scores) < 2:
            continue
        eligible_groups += 1
        if max(scores) == min(scores):
            zero_variance += 1
        else:
            mixed += 1

    capability_mass: Counter[str] = Counter()
    for capabilities in task_capabilities.values():
        share = 1.0 / len(capabilities)
        for capability in capabilities:
            capability_mass[capability] += share
    task_count = len(task_capabilities)
    actual_weights = {
        capability: capability_mass[capability] / task_count for capability in capability_mass
    }
    target_weights = {item.capability: item.target_weight for item in catalog.capabilities}
    capability_deltas = {
        capability: abs(actual_weights.get(capability, 0.0) - target)
        for capability, target in target_weights.items()
    }
    zero_fraction = zero_variance / eligible_groups if eligible_groups else 1.0
    infrastructure_rate = len(infrastructure) / len(rows)
    gates = {
        "task_count": min_tasks <= task_count <= max_tasks,
        "group_shape": not group_shape_failures,
        "rubric_shape": not malformed_rubrics,
        "reward_variance": eligible_groups > 0
        and zero_fraction <= max_zero_variance_fraction,
        "infrastructure": infrastructure_rate <= max_infrastructure_failure_rate,
        "capability_balance": bool(capability_deltas)
        and max(capability_deltas.values()) <= max_capability_weight_delta,
    }
    return {
        "status": "ready" if all(gates.values()) else "not_ready",
        "gates": gates,
        "task_count": task_count,
        "group_count": len(groups),
        "eligible_group_count": eligible_groups,
        "mixed_reward_group_count": mixed,
        "zero_variance_group_fraction": zero_fraction,
        "infrastructure_failure_rate": infrastructure_rate,
        "group_shape_failures": group_shape_failures,
        "malformed_rubric_task_ids": sorted(set(malformed_rubrics)),
        "capability_actual_weights": dict(sorted(actual_weights.items())),
        "capability_target_weights": dict(sorted(target_weights.items())),
        "capability_weight_deltas": dict(sorted(capability_deltas.items())),
        "catalog_fingerprint": catalog.fingerprint,
    }


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-catalog")
    validate.add_argument("--catalog", required=True)
    canary = subparsers.add_parser("analyze-canary")
    canary.add_argument("--catalog", required=True)
    canary.add_argument("--records", required=True)
    canary.add_argument("--group-size", type=int, default=8)
    canary.add_argument("--min-tasks", type=int, default=16)
    canary.add_argument("--max-tasks", type=int, default=32)
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    catalog = CurriculumCatalog.read_json(args.catalog)
    if args.command == "validate-catalog":
        result: object = {
            "status": "valid",
            "catalog_version": catalog.catalog_version,
            "catalog_fingerprint": catalog.fingerprint,
            "capability_count": len(catalog.capabilities),
            "failure_mode_count": len(catalog.failure_modes),
            "rubric_count": len(catalog.rubrics),
        }
    else:
        result = analyze_no_update_canary(
            _read_jsonl(args.records),
            catalog,
            group_size=args.group_size,
            min_tasks=args.min_tasks,
            max_tasks=args.max_tasks,
        )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
