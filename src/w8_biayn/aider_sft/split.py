"""Admitted-pool accounting and exact category/split constraint solver."""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .config import DATASET_PROFILE, profile_contract, profile_subject_id
from .errors import AiderSftError
from .review import register_subject, state_root, subject_path
from .schema import PrimaryCategory, ReviewScope, SourceManifest, Split
from .source_exercism import load_canonical_task
from .util import fingerprint, read_json, write_json


def _intended_split(
    task_root: Path,
    task_source_kind: str,
    source_splits: dict[str, Split],
) -> Split:
    task = load_canonical_task(task_root)
    if task_source_kind == "exercism":
        try:
            return source_splits[task.root_task_id]
        except KeyError as exc:
            raise AiderSftError(
                "source_inventory_mismatch", f"source split absent for {task.root_task_id}"
            ) from exc
    static = read_json(task_root / "receipts/static.json")
    try:
        return Split(static["intended_split"])
    except (KeyError, ValueError) as exc:
        raise AiderSftError("static_schema_error", "generated split cell is absent") from exc


def admitted_pool_report(
    *,
    task_roots: list[Path],
    source_manifest: SourceManifest,
    profile: str = DATASET_PROFILE,
) -> dict[str, Any]:
    contract = profile_contract(profile)
    source_splits = {entry.slug: entry.intended_split for entry in source_manifest.entries}
    records: list[dict[str, Any]] = []
    task_ids: set[str] = set()
    family_ids: set[str] = set()
    for task_root in sorted(task_roots):
        task = load_canonical_task(task_root)
        if task.task_id in task_ids:
            raise AiderSftError("duplicate_task", f"duplicate task ID: {task.task_id}")
        if task.task_family_id in family_ids:
            raise AiderSftError("duplicate_family", f"duplicate family: {task.task_family_id}")
        task_ids.add(task.task_id)
        family_ids.add(task.task_family_id)
        split = _intended_split(task_root, task.source.kind.value, source_splits)
        records.append(
            {
                "task_id": task.task_id,
                "root_task_id": task.root_task_id,
                "task_family_id": task.task_family_id,
                "split": split.value,
                "source_kind": task.source.kind.value,
                "primary_category": task.classification.primary_category.value,
                "difficulty": task.classification.difficulty.value,
                "tags": task.classification.tags,
                "task_content_sha256": task.source.content_sha256,
            }
        )

    cell_counts: dict[str, dict[str, int]] = {
        category.value: {split.value: 0 for split in Split} for category in PrimaryCategory
    }
    split_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    for record in records:
        cell_counts[record["primary_category"]][record["split"]] += 1
        split_counts[record["split"]] += 1
        source_counts[record["source_kind"]] += 1
    source_target_cells: dict[str, dict[str, int]] = {
        category.value: {split.value: 0 for split in Split} for category in PrimaryCategory
    }
    for entry in source_manifest.entries:
        source_target_cells[entry.primary_category.value][entry.intended_split.value] += 1
    deficits = {}
    for category in PrimaryCategory:
        deficits[category.value] = {}
        for split in Split:
            target = (
                contract.category_split_targets[split.value]
                if contract.category_split_targets is not None
                else source_target_cells[category.value][split.value]
            )
            deficits[category.value][split.value] = (
                target - cell_counts[category.value][split.value]
            )
    return {
        "schema_version": "aider-sft-admitted-pool-report-v1",
        "tasks": sorted(records, key=lambda item: item["task_id"]),
        "counts": {
            "total": len(records),
            "by_split": dict(sorted(split_counts.items())),
            "by_source_kind": dict(sorted(source_counts.items())),
            "by_cell": cell_counts,
        },
        "deficit_cells": deficits,
        "pool_fingerprint": fingerprint("aider-sft-admitted-pool-v1", records),
    }


def _validate_release_constraints(
    report: dict[str, Any],
    *,
    profile: str = DATASET_PROFILE,
) -> None:
    contract = profile_contract(profile)
    records = report["tasks"]
    counts = report["counts"]
    problems: list[str] = []
    if counts["total"] != contract.total_roots:
        problems.append(f"total={counts['total']}")
    for split in Split:
        target = contract.total_targets[split.value]
        observed = counts["by_split"].get(split.value, 0)
        if observed != target:
            problems.append(f"{split.value}={observed}")
    if contract.category_split_targets is not None:
        for category in PrimaryCategory:
            for split in Split:
                target = contract.category_split_targets[split.value]
                observed = counts["by_cell"][category.value][split.value]
                if observed != target:
                    problems.append(f"{category.value}/{split.value}={observed}")
    llm = [record for record in records if record["source_kind"] == "llm_assisted"]
    if contract.llm_enabled:
        if len(llm) < contract.minimum_llm_assisted:
            problems.append(f"llm_assisted={len(llm)}")
        if {record["split"] for record in llm} != {split.value for split in Split}:
            problems.append("llm_split_coverage")
        for category in PrimaryCategory:
            category_llm = [row for row in llm if row["primary_category"] == category.value]
            if len(category_llm) < 2:
                problems.append(f"llm_category={category.value}")
            if not any(row["split"] == Split.TRAIN.value for row in category_llm):
                problems.append(f"llm_train_category={category.value}")
            difficulties = {
                row["difficulty"] for row in records if row["primary_category"] == category.value
            }
            if difficulties != {"easy", "medium", "hard"}:
                problems.append(f"difficulty_coverage={category.value}")
    elif llm or counts["by_source_kind"].get("exercism", 0) != contract.total_roots:
        problems.append("source_only_provenance")
    if problems:
        raise AiderSftError(
            "category_quota_unsatisfied", "split constraints failed: " + "; ".join(problems)
        )


def propose_split(
    *,
    root: Path,
    task_roots: list[Path],
    source_manifest: SourceManifest,
    config_lock: dict[str, Any],
) -> dict[str, Any]:
    profile = config_lock["config"]["dataset"]["profile"]
    contract = profile_contract(profile)
    report = admitted_pool_report(
        task_roots=task_roots,
        source_manifest=source_manifest,
        profile=profile,
    )
    _validate_release_constraints(report, profile=profile)
    manifest = {
        "schema_version": "aider-sft-split-manifest-v1",
        "dataset_profile": config_lock["config"]["dataset"]["profile"],
        "seed": config_lock["config"]["dataset"]["split_seed"],
        "admitted_pool_fingerprint": report["pool_fingerprint"],
        "tasks": report["tasks"],
        "counts": report["counts"],
    }
    path = state_root(root) / "proposed-split.json"
    write_json(path, manifest)
    subject = register_subject(
        root,
        scope=ReviewScope.FINAL_SPLIT,
        subject_id=profile_subject_id(profile, "final-split"),
        payload={
            "split_manifest": manifest,
            "constraints": {
                "total": contract.total_roots,
                "splits": contract.total_targets,
                "per_category": contract.category_split_targets,
                "minimum_llm_assisted": contract.minimum_llm_assisted,
            },
            "taxonomy_version": config_lock["config"]["taxonomy_version"],
        },
    )
    return {
        "manifest": manifest,
        "path": str(path),
        "subject": subject,
    }


def freeze_split(root: Path, approved_fingerprint: str) -> dict[str, Any]:
    proposed = read_json(state_root(root) / "proposed-split.json")
    review_subject_path = subject_path(
        root,
        ReviewScope.FINAL_SPLIT,
        profile_subject_id(proposed["dataset_profile"], "final-split"),
    )
    subject = read_json(review_subject_path)
    if subject["subject_fingerprint"] != approved_fingerprint:
        raise AiderSftError("human_review_stale", "final split approval is stale")
    write_json(root / "split-manifest.json", proposed)
    return proposed


def split_task_roots(root: Path) -> dict[Split, list[Path]]:
    manifest = read_json(root / "split-manifest.json")
    canonical = root / "private/canonical-tasks"
    result: dict[Split, list[Path]] = defaultdict(list)
    for record in manifest["tasks"]:
        task_root = canonical / record["task_id"]
        if not task_root.is_dir():
            raise AiderSftError(
                "static_schema_error", f"missing canonical task {record['task_id']}"
            )
        result[Split(record["split"])].append(task_root)
    return {split: sorted(result[split]) for split in Split}
