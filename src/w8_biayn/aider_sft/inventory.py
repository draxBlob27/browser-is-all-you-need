"""Pinned Exercism discovery, proposal generation, and reviewed promotion."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from w8_biayn.constants import EXERCISM_CPP_PIN, EXERCISM_CPP_REPO, UPSTREAMS
from w8_biayn.upstreams import upstream_path

from .benchmark import EXPECTED_CPP_TASK_IDS, benchmark_manifest_sha256, load_benchmark_manifest
from .config import (
    TAXONOMY_VERSION,
    load_config,
    profile_contract,
    profile_subject_id,
)
from .errors import AiderSftError
from .schema import PrimaryCategory, ReviewDecision, ReviewScope, SourceManifest, Split
from .taxonomy import (
    CATEGORY_SLUGS,
    category_for,
    source_cell_counts,
    source_difficulty,
    source_split,
    source_tags,
    validate_taxonomy_inventory,
)
from .util import (
    atomic_write,
    fingerprint,
    hash_file_records,
    normalize_relative_path,
    pretty_json_bytes,
    read_json,
    read_jsonl,
    sha256_bytes,
    validate_regular_file,
    write_json,
)

CONCEPT_SLUGS = frozenset(
    {
        "doctor-data",
        "election-day",
        "ellens-alien-game",
        "freelancer-rates",
        "interest-is-interesting",
        "lasagna",
        "lasagna-master",
        "last-will",
        "log-levels",
        "making-the-grade",
        "pacman-rules",
        "power-of-troy",
        "speedywagon",
        "troll-the-trolls",
        "vehicle-purchase",
    }
)
EXPECTED_SOURCE_SLUGS = frozenset(slug for slugs in CATEGORY_SLUGS.values() for slug in slugs)
PRACTICE_SLUGS = EXPECTED_SOURCE_SLUGS - CONCEPT_SLUGS


def git_identity(path: Path, revision: str) -> dict[str, Any]:
    head = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    status = subprocess.run(
        ["git", "-C", str(path), "status", "--porcelain", "--untracked-files=all"],
        check=False,
        capture_output=True,
        text=True,
    )
    if head.returncode != 0 or head.stdout.strip() != revision:
        raise AiderSftError("source_inventory_mismatch", f"wrong upstream revision at {path}")
    if status.returncode != 0 or status.stdout.strip():
        raise AiderSftError("source_inventory_mismatch", f"upstream tree is not clean: {path}")
    tree = subprocess.run(
        ["git", "-C", str(path), "rev-parse", f"{revision}^{{tree}}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {"revision": revision, "git_tree": tree.stdout.strip(), "clean": True}


def tracked_task_files(checkout: Path, relative: str) -> dict[str, bytes]:
    result = subprocess.run(
        ["git", "-C", str(checkout), "ls-files", "-z", "--", relative],
        check=True,
        capture_output=True,
    )
    files: dict[str, bytes] = {}
    prefix = relative + "/"
    for item in result.stdout.split(b"\0"):
        if not item:
            continue
        source_relative = item.decode("utf-8")
        if not source_relative.startswith(prefix):
            raise AiderSftError("source_inventory_mismatch", "git returned an unrelated path")
        task_relative = normalize_relative_path(source_relative[len(prefix) :])
        path = checkout / source_relative
        validate_regular_file(path, root=checkout)
        files[task_relative] = path.read_bytes()
    if not files:
        raise AiderSftError("source_inventory_mismatch", f"empty source task: {relative}")
    return files


def reconcile_benchmark_checkout(repo_root: Path) -> dict[str, Any]:
    manifest = load_benchmark_manifest(repo_root)
    checkout = upstream_path(UPSTREAMS["aider-polyglot"], repo_root)
    identity = git_identity(checkout, manifest["revision"])
    root = checkout / manifest["root"]
    observed = {path.name for path in root.iterdir() if path.is_dir()}
    if observed != EXPECTED_CPP_TASK_IDS:
        raise AiderSftError(
            "source_inventory_mismatch",
            "pinned Polyglot checkout does not reconstruct the exact C++ denylist",
        )
    return {
        "manifest_sha256": benchmark_manifest_sha256(repo_root),
        "revision": identity["revision"],
        "git_tree": identity["git_tree"],
        "task_count": len(observed),
    }


def source_inventory_subject(raw_proposal: bytes, proposal: SourceManifest) -> dict[str, Any]:
    payload = {
        "proposal_sha256": sha256_bytes(raw_proposal),
        "source_revision": proposal.source_revision,
        "source_tree_sha256": proposal.source_tree_sha256,
        "taxonomy_version": proposal.taxonomy_version,
        "benchmark_denylist_sha256": proposal.benchmark_denylist_sha256,
    }
    return {
        "schema_version": "aider-sft-review-subject-v1",
        "scope": ReviewScope.SOURCE_INVENTORY.value,
        "subject_id": profile_subject_id(
            proposal.dataset_profile,
            "source-inventory",
        ),
        "subject_fingerprint": fingerprint(
            "aider-sft-review/source_inventory/v1", raw_proposal, payload
        ),
        "payload": payload,
    }


def build_inventory_proposal(
    *,
    config_path: Path,
    output_root: Path,
    repo_root: Path,
) -> dict[str, Any]:
    config = load_config(config_path)
    contract = profile_contract(config.dataset.profile)
    checkout = upstream_path(UPSTREAMS["exercism-cpp"], repo_root)
    identity = git_identity(checkout, EXERCISM_CPP_PIN)
    benchmark = reconcile_benchmark_checkout(repo_root)
    if EXPECTED_SOURCE_SLUGS & EXPECTED_CPP_TASK_IDS:
        raise AiderSftError("benchmark_id_overlap", "source list intersects benchmark denylist")
    if len(PRACTICE_SLUGS) != 60 or len(CONCEPT_SLUGS) != 15:
        raise AiderSftError("source_inventory_mismatch", "Appendix A counts changed")
    validate_taxonomy_inventory(set(EXPECTED_SOURCE_SLUGS))

    entries: list[dict[str, Any]] = []
    for slug in sorted(EXPECTED_SOURCE_SLUGS):
        source_kind = "practice" if slug in PRACTICE_SLUGS else "concept"
        relative = f"exercises/{source_kind}/{slug}"
        if not (checkout / relative).is_dir():
            raise AiderSftError("source_inventory_mismatch", f"missing {relative}")
        task_files = tracked_task_files(checkout, relative)
        category = category_for(slug)
        entries.append(
            {
                "source_kind": source_kind,
                "slug": slug,
                "source_relative_path": relative,
                "tree_sha256": hash_file_records("aider-sft-source-tree-v1", task_files),
                "task_family_id": slug,
                "primary_category": category.value,
                "tags": source_tags(slug, category, source_kind),
                "difficulty": source_difficulty(slug, category).value,
                "intended_split": (
                    Split.TRAIN.value
                    if contract.source_split_policy == "all_train"
                    else source_split(slug, category).value
                ),
                "spdx_license": "MIT",
                "enabled": True,
            }
        )

    proposal_value = {
        "schema_version": "aider-sft-source-manifest-v1",
        "dataset_profile": config.dataset.profile,
        "source_repository": EXERCISM_CPP_REPO,
        "source_revision": EXERCISM_CPP_PIN,
        "source_tree_sha256": fingerprint(
            "aider-sft-source-checkout-v1", identity, [entry["tree_sha256"] for entry in entries]
        ),
        "taxonomy_version": TAXONOMY_VERSION,
        "benchmark_denylist_sha256": benchmark["manifest_sha256"],
        "entries": entries,
    }
    try:
        proposal = SourceManifest.model_validate(proposal_value)
    except ValidationError as exc:
        raise AiderSftError("source_inventory_mismatch", str(exc)) from exc
    raw = pretty_json_bytes(proposal.model_dump(mode="json"))
    inventory_root = output_root / "private/inventory"
    proposal_path = inventory_root / "proposed-source.json"
    atomic_write(proposal_path, raw)
    subject = source_inventory_subject(raw, proposal)
    write_json(inventory_root / "source-inventory-subject.json", subject)

    source_counts = source_cell_counts(entries)
    deficits: dict[str, dict[str, int]] = {}
    for category in PrimaryCategory:
        deficits[category.value] = {}
        for split in Split:
            target = (
                contract.category_split_targets[split.value]
                if contract.category_split_targets is not None
                else source_counts[category.value].get(split.value, 0)
            )
            deficits[category.value][split.value] = max(
                target - source_counts[category.value].get(split.value, 0),
                0,
            )
    total_required = sum(value for cells in deficits.values() for value in cells.values())
    llm_budgets = config.llm.budgets if config.llm is not None else None
    reserve_multiplier = llm_budgets.reserve_multiplier if llm_budgets else 0.0
    configured_capacity = llm_budgets.total_candidates if llm_budgets else 0
    minimum_capacity = total_required * reserve_multiplier
    capacity = {
        "schema_version": "aider-sft-capacity-report-v1",
        "llm_enabled": contract.llm_enabled,
        "source_candidates": len(entries),
        "source_cells": source_counts,
        "llm_deficit_cells": deficits,
        "required_llm_admissions": total_required,
        "minimum_candidate_capacity": minimum_capacity,
        "configured_candidate_capacity": configured_capacity,
        "capacity_sufficient": configured_capacity >= minimum_capacity,
    }
    write_json(inventory_root / "capacity-report.json", capacity)
    return {
        "proposal": str(proposal_path),
        "subject": str(inventory_root / "source-inventory-subject.json"),
        "capacity_report": str(inventory_root / "capacity-report.json"),
        "source_candidates": len(entries),
        "required_llm_admissions": total_required,
        "subject_fingerprint": subject["subject_fingerprint"],
    }


def validate_source_manifest(
    path: Path,
    repo_root: Path,
    *,
    expected_profile: str | None = None,
) -> SourceManifest:
    try:
        manifest = SourceManifest.model_validate(read_json(path))
    except ValidationError as exc:
        raise AiderSftError("source_inventory_mismatch", str(exc)) from exc
    if len(manifest.entries) != 75:
        raise AiderSftError("source_inventory_mismatch", "source manifest must contain 75 entries")
    if expected_profile is not None and manifest.dataset_profile != expected_profile:
        raise AiderSftError(
            "source_inventory_mismatch",
            "source manifest belongs to a different dataset profile",
        )
    contract = profile_contract(manifest.dataset_profile)
    if contract.source_split_policy == "all_train" and any(
        entry.intended_split is not Split.TRAIN for entry in manifest.entries
    ):
        raise AiderSftError(
            "source_inventory_mismatch",
            "source-only profile requires all 75 source entries in train",
        )
    if {entry.slug for entry in manifest.entries} != EXPECTED_SOURCE_SLUGS:
        raise AiderSftError("source_inventory_mismatch", "source manifest differs from Appendix A")
    if any(entry.slug in EXPECTED_CPP_TASK_IDS for entry in manifest.entries):
        raise AiderSftError("benchmark_id_overlap", "source manifest contains a held-out task")
    if manifest.source_revision != EXERCISM_CPP_PIN:
        raise AiderSftError("source_inventory_mismatch", "source manifest revision changed")
    if manifest.benchmark_denylist_sha256 != benchmark_manifest_sha256(repo_root):
        raise AiderSftError("source_inventory_mismatch", "benchmark binding changed")
    return manifest


def promote_source_inventory(
    *,
    proposal_path: Path,
    decisions_path: Path,
    output_path: Path,
    repo_root: Path,
    config_path: Path,
) -> dict[str, Any]:
    raw = proposal_path.read_bytes()
    try:
        proposal = SourceManifest.model_validate_json(raw)
    except ValidationError as exc:
        raise AiderSftError("source_inventory_promotion_mismatch", str(exc)) from exc
    config = load_config(config_path)
    validate_source_manifest(
        proposal_path,
        repo_root,
        expected_profile=config.dataset.profile,
    )
    subject = source_inventory_subject(raw, proposal)
    matches: list[ReviewDecision] = []
    for value in read_jsonl(decisions_path):
        try:
            decision = ReviewDecision.model_validate(value)
        except ValidationError as exc:
            raise AiderSftError("source_inventory_promotion_mismatch", str(exc)) from exc
        if decision.scope is ReviewScope.SOURCE_INVENTORY:
            matches.append(decision)
    if len(matches) != 1:
        raise AiderSftError(
            "source_inventory_promotion_mismatch",
            "exactly one source_inventory decision is required",
        )
    decision = matches[0]
    if (
        decision.subject_id != subject["subject_id"]
        or decision.subject_fingerprint != subject["subject_fingerprint"]
    ):
        raise AiderSftError(
            "source_inventory_review_stale", "decision does not bind the exact proposal"
        )
    if decision.decision.value != "approve":
        raise AiderSftError("human_review_rejected", "source inventory was rejected")
    authorized = config.review.authorized_reviewers.get(ReviewScope.SOURCE_INVENTORY, [])
    if (
        decision.reviewer not in authorized
        or decision.reviewer in config.review.authoring_identities
    ):
        raise AiderSftError("human_review_stale", "reviewer is not authorized for this scope")
    expected_output = repo_root / profile_contract(config.dataset.profile).source_manifest_relative
    if output_path.resolve() != expected_output.resolve():
        raise AiderSftError(
            "source_inventory_promotion_mismatch",
            f"profile inventory must be promoted to {expected_output}",
        )
    if output_path.exists() and output_path.read_bytes() != raw:
        raise AiderSftError(
            "source_inventory_promotion_mismatch", "refusing to overwrite a different manifest"
        )
    atomic_write(output_path, raw)
    return {
        "output": str(output_path),
        "bytes": len(raw),
        "sha256": sha256_bytes(raw),
        "entries": len(proposal.entries),
        "reviewer": decision.reviewer,
    }
