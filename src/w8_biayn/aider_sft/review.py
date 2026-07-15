"""Scope-specific review subjects, deterministic exports, and decision imports."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .errors import AiderSftError
from .schema import Decision, ReviewDecision, ReviewScope, ReviewSubject
from .util import (
    canonical_json_bytes,
    fingerprint,
    read_json,
    read_jsonl,
    sha256_bytes,
    write_json,
    write_jsonl,
)


def state_root(root: Path) -> Path:
    return root.parent / f"{root.name}.state"


def subject_path(root: Path, scope: ReviewScope, subject_id: str) -> Path:
    safe_id = subject_id.replace("/", "__")
    return state_root(root) / "review-subjects" / scope.value / f"{safe_id}.json"


def register_subject(
    root: Path,
    *,
    scope: ReviewScope,
    subject_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    subject = {
        "schema_version": "aider-sft-review-subject-v1",
        "scope": scope.value,
        "subject_id": subject_id,
        "subject_fingerprint": fingerprint(f"aider-sft-review/{scope.value}/v1", payload),
        "payload": payload,
    }
    ReviewSubject.model_validate(subject)
    path = subject_path(root, scope, subject_id)
    if path.exists() and read_json(path) != subject:
        path.unlink()
    write_json(path, subject)
    return subject


def _all_subjects(root: Path) -> list[dict[str, Any]]:
    subjects: list[dict[str, Any]] = []
    subject_root = state_root(root) / "review-subjects"
    if subject_root.exists():
        for path in sorted(subject_root.rglob("*.json")):
            value = read_json(path)
            ReviewSubject.model_validate(value)
            subjects.append(value)
    inventory_subject = root / "private/inventory/source-inventory-subject.json"
    if inventory_subject.is_file():
        value = read_json(inventory_subject)
        ReviewSubject.model_validate(value)
        if not any(
            row["scope"] == value["scope"] and row["subject_id"] == value["subject_id"]
            for row in subjects
        ):
            subjects.append(value)
    return sorted(subjects, key=lambda row: (row["scope"], row["subject_id"]))


def export_review_package(root: Path, output: Path) -> dict[str, Any]:
    subjects = _all_subjects(root)
    if not subjects:
        raise AiderSftError("human_review_stale", "no current review subjects exist")
    if output.exists() and any(output.iterdir()):
        raise AiderSftError(
            "human_review_stale", f"review export destination is not empty: {output}"
        )
    output.mkdir(parents=True, exist_ok=True)
    for subject in subjects:
        destination = output / subject["scope"] / f"{subject['subject_id'].replace('/', '__')}.json"
        write_json(destination, subject)
    manifest = {
        "schema_version": "aider-sft-review-export-v1",
        "subjects": [
            {
                "scope": subject["scope"],
                "subject_id": subject["subject_id"],
                "subject_fingerprint": subject["subject_fingerprint"],
            }
            for subject in subjects
        ],
    }
    manifest["package_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
    write_json(output / "review-manifest.json", manifest)
    return {
        "output": str(output),
        "subjects": len(subjects),
        "scopes": dict(sorted(Counter(row["scope"] for row in subjects).items())),
        "package_sha256": manifest["package_sha256"],
    }


def imported_decisions_path(root: Path) -> Path:
    return state_root(root) / "imported-decisions.jsonl"


def load_decisions(root: Path) -> list[ReviewDecision]:
    path = imported_decisions_path(root)
    if not path.is_file():
        return []
    decisions: list[ReviewDecision] = []
    for value in read_jsonl(path):
        try:
            decisions.append(ReviewDecision.model_validate(value))
        except ValidationError as exc:
            raise AiderSftError("human_review_stale", str(exc)) from exc
    return decisions


def import_review_decisions(
    root: Path,
    decisions_path: Path,
    *,
    config_lock: dict[str, Any],
) -> dict[str, Any]:
    current = {
        (subject["scope"], subject["subject_id"]): subject for subject in _all_subjects(root)
    }
    existing = load_decisions(root)
    combined = list(existing)
    seen = {(item.scope.value, item.subject_id, item.subject_fingerprint) for item in existing}
    imported = 0
    for value in read_jsonl(decisions_path):
        try:
            decision = ReviewDecision.model_validate(value)
        except ValidationError as exc:
            raise AiderSftError("human_review_stale", str(exc)) from exc
        key = (decision.scope.value, decision.subject_id)
        decision_key = (*key, decision.subject_fingerprint)
        if decision_key in seen:
            raise AiderSftError("human_review_stale", f"duplicate decision for {decision_key}")
        subject = current.get(key)
        if subject is None or subject["subject_fingerprint"] != decision.subject_fingerprint:
            reason = (
                "dataset_release_review_stale"
                if decision.scope is ReviewScope.DATASET_RELEASE
                else "human_review_stale"
            )
            raise AiderSftError(reason, f"decision subject is absent or stale: {key}")
        review = config_lock["config"]["review"]
        authorized = review["authorized_reviewers"].get(decision.scope.value, [])
        if (
            decision.reviewer not in authorized
            or decision.reviewer in review["authoring_identities"]
        ):
            raise AiderSftError("human_review_stale", f"unauthorized reviewer: {decision.reviewer}")
        combined.append(decision)
        seen.add(decision_key)
        imported += 1
    ordered = sorted(
        combined,
        key=lambda item: (item.scope.value, item.subject_id, item.subject_fingerprint),
    )
    write_jsonl(
        imported_decisions_path(root),
        [item.model_dump(mode="json") for item in ordered],
    )
    return {
        "imported": imported,
        "total": len(ordered),
        "approvals": sum(item.decision is Decision.APPROVE for item in ordered),
        "rejections": sum(item.decision is Decision.REJECT for item in ordered),
    }


def matching_decision(
    root: Path,
    *,
    scope: ReviewScope,
    subject_id: str,
    subject_fingerprint: str,
) -> ReviewDecision | None:
    for decision in load_decisions(root):
        if (
            decision.scope is scope
            and decision.subject_id == subject_id
            and decision.subject_fingerprint == subject_fingerprint
        ):
            return decision
    return None


def require_approval(
    root: Path,
    *,
    scope: ReviewScope,
    subject_id: str,
    subject_fingerprint: str,
) -> ReviewDecision:
    decision = matching_decision(
        root,
        scope=scope,
        subject_id=subject_id,
        subject_fingerprint=subject_fingerprint,
    )
    if decision is None:
        reason = (
            "llm_usage_terms_unapproved"
            if scope is ReviewScope.LLM_USAGE_TERMS
            else "dataset_release_review_stale"
            if scope is ReviewScope.DATASET_RELEASE
            else "human_review_stale"
        )
        raise AiderSftError(reason, f"approval is missing for {scope.value}/{subject_id}")
    if decision.decision is Decision.REJECT:
        raise AiderSftError("human_review_rejected", f"{scope.value}/{subject_id} was rejected")
    return decision


def materialize_review_evidence(root: Path) -> dict[str, Any]:
    decisions = load_decisions(root)
    destination = root / "private/review/imported-decisions.jsonl"
    write_jsonl(destination, [item.model_dump(mode="json") for item in decisions])
    subjects = _all_subjects(root)
    manifest = {
        "schema_version": "aider-sft-review-manifest-v1",
        "subjects": [
            {
                "scope": item["scope"],
                "subject_id": item["subject_id"],
                "subject_fingerprint": item["subject_fingerprint"],
            }
            for item in subjects
        ],
        "decisions": [
            {
                "scope": item.scope.value,
                "subject_id": item.subject_id,
                "subject_fingerprint": item.subject_fingerprint,
                "decision": item.decision.value,
                "decision_sha256": sha256_bytes(canonical_json_bytes(item.model_dump(mode="json"))),
            }
            for item in decisions
        ],
    }
    write_json(root / "private/review/review-manifest.json", manifest)
    return manifest
