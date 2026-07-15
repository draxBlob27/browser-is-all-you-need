"""Immutable manifest/readiness creation and offline producer verification."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from .config import profile_contract
from .errors import AiderSftError
from .oracle import validate_oracle_receipt
from .renderer import parse_target
from .schema import Decision, ReviewDecision, ReviewScope, SftRow, TokenRecord
from .tokenization import compute_token_record, load_locked_tokenizer
from .util import (
    canonical_json_bytes,
    fingerprint,
    manifest_entries,
    read_json,
    read_jsonl,
    sha256_bytes,
    sha256_file,
    verify_manifest_entries,
    write_json,
)


MANIFEST_EXCLUSIONS = ["manifest.json", "readiness.json"]
MANDATORY_BINDINGS = {
    "manifest_sha256",
    "config_lock_sha256",
    "source_manifest_sha256",
    "benchmark_denylist_sha256",
    "split_manifest_sha256",
    "review_manifest_sha256",
    "imported_decisions_sha256",
    "admission_records_sha256",
    "grader_support_manifest_sha256",
    "tokenizer_render_policy_sha256",
    "sft_train_jsonl_sha256",
    "sft_token_records_sha256",
    "dataset_release_subject_sha256",
}


def _artifact_hash(root: Path, relative: str) -> str:
    path = root / relative
    if not path.is_file():
        raise AiderSftError("static_schema_error", f"missing release artifact: {relative}")
    return sha256_file(path)


def _release_counts(root: Path) -> dict[str, int]:
    split = read_json(root / "split-manifest.json")
    source_counts = split["counts"]["by_source_kind"]
    return {
        "total_admitted": split["counts"]["total"],
        "train_rows": len(read_jsonl(root / "sft/train.jsonl")),
        "validation_roots": sum(row["split"] == "validation" for row in split["tasks"]),
        "test_roots": sum(row["split"] == "test" for row in split["tasks"]),
        "source_backed": source_counts.get("exercism", 0),
        "llm_assisted": source_counts.get("llm_assisted", 0),
    }


def create_manifest_and_readiness(
    root: Path,
    *,
    dataset_release_subject_sha256: str,
) -> dict[str, Any]:
    config_lock = read_json(root / "config.lock.json")
    split = read_json(root / "split-manifest.json")
    entries = manifest_entries(root)
    manifest = {
        "schema_version": "aider-sft-bundle-manifest-v1",
        "dataset_profile": config_lock["config"]["dataset"]["profile"],
        "dataset_id": config_lock["dataset_id"],
        "distribution_scope": "internal_research",
        "non_recursive_exclusions": MANIFEST_EXCLUSIONS,
        "entries": entries,
        "counts": split["counts"],
        "identities": {
            "renderer": config_lock["config"]["renderer_version"],
            "tokenizer": config_lock["config"]["tokenizer"],
            "grader": config_lock["config"]["toolchain"],
            "taxonomy": config_lock["config"]["taxonomy_version"],
        },
    }
    write_json(root / "manifest.json", manifest)
    bindings = {
        "manifest_sha256": sha256_file(root / "manifest.json"),
        "config_lock_sha256": _artifact_hash(root, "config.lock.json"),
        "source_manifest_sha256": _artifact_hash(root, "source-manifest.json"),
        "benchmark_denylist_sha256": _artifact_hash(root, "benchmark-denylist.json"),
        "split_manifest_sha256": _artifact_hash(root, "split-manifest.json"),
        "review_manifest_sha256": _artifact_hash(root, "private/review/review-manifest.json"),
        "imported_decisions_sha256": _artifact_hash(
            root, "private/review/imported-decisions.jsonl"
        ),
        "admission_records_sha256": _artifact_hash(root, "private/admission/records.jsonl"),
        "grader_support_manifest_sha256": _artifact_hash(
            root, "private/grader-support/manifest.json"
        ),
        "tokenizer_render_policy_sha256": _artifact_hash(root, "tokenizer-render-policy.json"),
        "sft_train_jsonl_sha256": _artifact_hash(root, "sft/train.jsonl"),
        "sft_token_records_sha256": _artifact_hash(root, "sft/token-records.jsonl"),
        "dataset_release_subject_sha256": dataset_release_subject_sha256,
    }
    counts = _release_counts(root)
    readiness = {
        "kind": "primary-aider-sft-dataset-readiness",
        "schema_version": 2,
        "dataset_id": config_lock["dataset_id"],
        "dataset_profile": config_lock["config"]["dataset"]["profile"],
        "status": "ready",
        "bindings": bindings,
        "counts": counts,
        "gates": {
            "source_inventory_frozen": True,
            "all_references_pass": True,
            "all_sanitizers_pass": True,
            "grader_identity_reconciled": True,
            "all_test_counts_positive": True,
            "all_targets_parse_and_apply": True,
            "all_rows_fit_token_budget": True,
            "tokenizer_policy_matches_consumer": True,
            "token_records_reconciled": True,
            "shared_grader_support_reconciled": True,
            "benchmark_overlap_count": 0,
            "cross_split_family_overlap_count": 0,
            "manifest_reconciled": True,
            "required_review_complete": True,
            "dataset_release_review_complete": True,
            "llm_category_coverage_complete": True,
        },
        "distribution_scope": "internal_research",
    }
    write_json(root / "readiness.json", readiness)
    return readiness


def _verify_rows_and_tokens(
    root: Path,
    *,
    tokenizer: Any | None,
    consumer_lock: dict[str, Any],
    expected_train_rows: int,
) -> None:
    rows = read_jsonl(root / "sft/train.jsonl")
    records = read_jsonl(root / "sft/token-records.jsonl")
    if len(rows) != expected_train_rows or len(records) != expected_train_rows:
        raise AiderSftError(
            "consumer_export_manifest_mismatch",
            f"expected {expected_train_rows} rows and token records",
        )
    by_task = {record["task_id"]: record for record in records}
    if len(by_task) != expected_train_rows:
        raise AiderSftError("consumer_loss_mask_mismatch", "token task IDs are not unique")
    for row in rows:
        SftRow.model_validate(row)
        parse_target(
            row["messages"][1]["content"],
            expected_files=row["metadata"]["editable_files"],
        )
        record = by_task.get(row["task_id"])
        if record is None:
            raise AiderSftError("consumer_loss_mask_mismatch", "row lacks token record")
        TokenRecord.model_validate(record)
        if record["row_sha256"] != sha256_bytes(canonical_json_bytes(row)):
            raise AiderSftError("consumer_loss_mask_mismatch", "row hash differs")
        for key in (
            "rendered_token_sha256",
            "loss_mask_sha256",
            "response_length",
            "response_loss_mask_sha256",
            "token_counts",
        ):
            if row["metadata"].get(key) != record[key]:
                raise AiderSftError("consumer_loss_mask_mismatch", f"row metadata differs: {key}")
        if tokenizer is not None:
            recomputed = compute_token_record(
                row,
                consumer_lock=consumer_lock,
                tokenizer=tokenizer,
            )
            if recomputed != record:
                raise AiderSftError(
                    "consumer_loss_mask_mismatch", f"token evidence differs: {row['task_id']}"
                )


def verify_ready_bundle(
    root: Path,
    *,
    rerun_oracles: bool = False,
    scratch_parent: Path | None = None,
    require_tokenizer: bool = True,
) -> dict[str, Any]:
    readiness_path = root / "readiness.json"
    if not readiness_path.is_file():
        raise AiderSftError("consumer_readiness_missing", f"missing {readiness_path}")
    readiness = read_json(readiness_path)
    if readiness.get("schema_version") != 2 or readiness.get("status") != "ready":
        raise AiderSftError("consumer_readiness_missing", "readiness is not schema-v2 ready")
    if set(readiness.get("bindings", {})) != MANDATORY_BINDINGS:
        raise AiderSftError("consumer_readiness_missing", "readiness bindings are incomplete")
    manifest = read_json(root / "manifest.json")
    if manifest.get("non_recursive_exclusions") != MANIFEST_EXCLUSIONS:
        raise AiderSftError("consumer_export_manifest_mismatch", "manifest exclusions differ")
    verify_manifest_entries(root, manifest["entries"])
    binding_paths = {
        "manifest_sha256": "manifest.json",
        "config_lock_sha256": "config.lock.json",
        "source_manifest_sha256": "source-manifest.json",
        "benchmark_denylist_sha256": "benchmark-denylist.json",
        "split_manifest_sha256": "split-manifest.json",
        "review_manifest_sha256": "private/review/review-manifest.json",
        "imported_decisions_sha256": "private/review/imported-decisions.jsonl",
        "admission_records_sha256": "private/admission/records.jsonl",
        "grader_support_manifest_sha256": "private/grader-support/manifest.json",
        "tokenizer_render_policy_sha256": "tokenizer-render-policy.json",
        "sft_train_jsonl_sha256": "sft/train.jsonl",
        "sft_token_records_sha256": "sft/token-records.jsonl",
    }
    for key, relative in binding_paths.items():
        if readiness["bindings"][key] != sha256_file(root / relative):
            raise AiderSftError("consumer_export_manifest_mismatch", f"stale binding: {key}")
    release_subject = read_json(root / "private/review/dataset-release-subject.json")
    if (
        release_subject.get("scope") != ReviewScope.DATASET_RELEASE.value
        or release_subject.get("subject_fingerprint")
        != fingerprint(
            f"aider-sft-review/{ReviewScope.DATASET_RELEASE.value}/v1",
            release_subject.get("payload", {}),
        )
        or readiness["bindings"]["dataset_release_subject_sha256"]
        != release_subject.get("subject_fingerprint")
    ):
        raise AiderSftError("dataset_release_review_stale", "release subject binding differs")
    decisions = [
        ReviewDecision.model_validate(value)
        for value in read_jsonl(root / "private/review/imported-decisions.jsonl")
    ]
    if not any(
        decision.scope is ReviewScope.DATASET_RELEASE
        and decision.subject_id == release_subject.get("subject_id")
        and decision.subject_fingerprint == release_subject.get("subject_fingerprint")
        and decision.decision is Decision.APPROVE
        for decision in decisions
    ):
        raise AiderSftError("dataset_release_review_stale", "release approval is absent or stale")
    if _release_counts(root) != readiness["counts"]:
        raise AiderSftError("consumer_export_manifest_mismatch", "readiness counts differ")
    config_lock = read_json(root / "config.lock.json")
    profile = config_lock["config"]["dataset"]["profile"]
    contract = profile_contract(profile)
    if readiness.get("dataset_profile") != profile or manifest.get("dataset_profile") != profile:
        raise AiderSftError(
            "consumer_export_manifest_mismatch",
            "dataset profile identity differs",
        )
    expected_counts = {
        "total_admitted": contract.total_roots,
        "train_rows": contract.total_targets["train"],
        "validation_roots": contract.total_targets["validation"],
        "test_roots": contract.total_targets["test"],
    }
    if (
        any(readiness["counts"].get(key) != value for key, value in expected_counts.items())
        or readiness["counts"].get("source_backed", 0) + readiness["counts"].get("llm_assisted", 0)
        != contract.total_roots
    ):
        raise AiderSftError("category_quota_unsatisfied", "release counts differ")
    if contract.llm_enabled and (
        readiness["counts"]["llm_assisted"] < contract.minimum_llm_assisted
    ):
        raise AiderSftError("category_quota_unsatisfied", "too few LLM-assisted roots")
    if not contract.llm_enabled and (
        readiness["counts"]["llm_assisted"] != 0
        or readiness["counts"]["source_backed"] != contract.total_roots
    ):
        raise AiderSftError(
            "category_quota_unsatisfied",
            "source-only provenance counts differ",
        )
    lock_value = dict(config_lock)
    lock_sha256 = lock_value.pop("lock_sha256", None)
    if lock_sha256 != sha256_bytes(canonical_json_bytes(lock_value)):
        raise AiderSftError("consumer_export_manifest_mismatch", "config lock hash differs")
    if readiness.get("dataset_id") != config_lock.get("dataset_id") or manifest.get(
        "dataset_id"
    ) != config_lock.get("dataset_id"):
        raise AiderSftError("consumer_export_manifest_mismatch", "dataset identity differs")
    consumer_lock = read_json(root / "consumer-lock.json")
    tokenizer = load_locked_tokenizer(consumer_lock) if require_tokenizer else None
    _verify_rows_and_tokens(
        root,
        tokenizer=tokenizer,
        consumer_lock=consumer_lock,
        expected_train_rows=contract.total_targets["train"],
    )

    canonical_root = root / "private/canonical-tasks"
    task_roots = sorted(path for path in canonical_root.iterdir() if path.is_dir())
    if len(task_roots) != contract.total_roots:
        raise AiderSftError("consumer_export_manifest_mismatch", "canonical task count differs")
    rerun_report_path: Path | None = None
    rerun_rows: list[dict[str, Any]] = []
    diagnostic_root: Path | None = None
    if rerun_oracles:
        if scratch_parent is not None:
            scratch = scratch_parent.resolve()
            ready = root.resolve()
            if scratch == ready or ready in scratch.parents:
                raise AiderSftError("unsafe_path", "oracle diagnostics must be outside ready root")
        diagnostic_root = Path(
            tempfile.mkdtemp(prefix=f"{root.name}-oracle-rerun-", dir=scratch_parent)
        )
        (diagnostic_root / "tasks").mkdir()
        (diagnostic_root / "work").mkdir()
        rerun_report_path = diagnostic_root / "oracle-rerun-report.json"
    for task_root in task_roots:
        if rerun_oracles and diagnostic_root is not None:
            from .oracle import run_task_oracle

            original = read_json(task_root / "receipts/oracle.json")
            copied = diagnostic_root / "tasks" / task_root.name
            shutil.copytree(task_root, copied, copy_function=shutil.copyfile)
            for path in sorted(copied.rglob("*"), reverse=True):
                path.chmod(0o755 if path.is_dir() else 0o644)
            copied.chmod(0o755)
            observed = run_task_oracle(
                task_root=copied,
                shared_support_root=root / "private/grader-support",
                config_lock=config_lock,
                scratch_parent=diagnostic_root / "work",
            )
            for receipt in (original, observed):
                for phase in receipt["phases"].values():
                    phase.pop("elapsed_ms", None)
                receipt.pop("oracle_fingerprint", None)
            matched = original == observed
            rerun_rows.append({"task_id": task_root.name, "matched": matched})
            shutil.rmtree(copied)
            if not matched:
                write_json(
                    rerun_report_path,
                    {
                        "schema_version": "aider-sft-oracle-rerun-report-v1",
                        "status": "failed",
                        "tasks": rerun_rows,
                    },
                )
                raise AiderSftError("human_review_stale", f"oracle rerun differs: {task_root.name}")
        validate_oracle_receipt(
            task_root=task_root,
            shared_support_root=root / "private/grader-support",
            config_lock=config_lock,
        )
    if rerun_report_path is not None:
        write_json(
            rerun_report_path,
            {
                "schema_version": "aider-sft-oracle-rerun-report-v1",
                "status": "passed",
                "tasks": rerun_rows,
            },
        )
    return {
        "root": str(root),
        "dataset_id": readiness["dataset_id"],
        "status": "ready",
        "counts": readiness["counts"],
        "manifest_sha256": readiness["bindings"]["manifest_sha256"],
        "oracle_rerun_report": str(rerun_report_path) if rerun_report_path else None,
    }
