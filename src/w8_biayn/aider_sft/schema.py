"""Strict schemas and state machines for the primary Aider SFT pipeline."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TextEnum(str, Enum):
    pass


class PrimaryCategory(TextEnum):
    ALGORITHMS = "Algorithms & data structures"
    TEXT = "Text & parsing"
    NUMERICAL = "Numerical reasoning"
    TIME = "Time & date"
    STATE = "State & concurrency"
    LOGIC = "Logic, grids & games"


class Difficulty(TextEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Split(TextEnum):
    TRAIN = "train"
    VALIDATION = "validation"
    TEST = "test"


class SourceKind(TextEnum):
    EXERCISM = "exercism"
    LLM_ASSISTED = "llm_assisted"


class CandidateState(TextEnum):
    DISCOVERED = "discovered"
    MATERIALIZED = "materialized"
    MECHANICALLY_VALID = "mechanically_valid"
    AWAITING_TASK_REVIEW = "awaiting_task_review"
    ADMITTED = "admitted"
    REJECTED_CONTENT = "rejected_content"
    DEFERRED_PROFILE = "deferred_profile"
    RETRYABLE_ERROR = "retryable_error"


class DatasetState(TextEnum):
    COLLECTING = "collecting"
    AWAITING_INVENTORY_REVIEW = "awaiting_inventory_review"
    POOL_FILLING = "pool_filling"
    AWAITING_SPLIT_REVIEW = "awaiting_split_review"
    SPLIT_FROZEN = "split_frozen"
    FINAL_SCREENED = "final_screened"
    AWAITING_RELEASE_REVIEW = "awaiting_release_review"
    READY = "ready"
    INCOMPLETE = "incomplete"
    FAILED = "failed"


class ReviewScope(TextEnum):
    SOURCE_INVENTORY = "source_inventory"
    LLM_USAGE_TERMS = "llm_usage_terms"
    LLM_TASK_SEMANTICS = "llm_task_semantics"
    CONTAMINATION_FLAG = "contamination_flag"
    FINAL_SPLIT = "final_split"
    DATASET_RELEASE = "dataset_release"


class Decision(TextEnum):
    APPROVE = "approve"
    REJECT = "reject"


REASON_OUTCOMES: dict[str, str] = {
    "profile_not_frozen": "incomplete",
    "source_inventory_mismatch": "rejected_content",
    "source_inventory_review_stale": "incomplete",
    "source_inventory_promotion_mismatch": "incomplete",
    "source_deferred_by_profile": "deferred_profile",
    "benchmark_id_overlap": "rejected_content",
    "benchmark_content_overlap": "rejected_content",
    "contamination_review_required": "incomplete",
    "contamination_normalizer_error": "rejected_content",
    "shared_support_mismatch": "rejected_content",
    "duplicate_task": "rejected_content",
    "duplicate_family": "rejected_content",
    "missing_docs": "rejected_content",
    "missing_editable_files": "rejected_content",
    "missing_reference": "rejected_content",
    "missing_tests": "rejected_content",
    "unsafe_path": "rejected_content",
    "hardlink_rejected": "rejected_content",
    "file_limit_exceeded": "rejected_content",
    "reference_mapping_error": "rejected_content",
    "unsupported_editor_reference_change": "rejected_content",
    "static_schema_error": "rejected_content",
    "cmake_generator_mismatch": "rejected_content",
    "compiler_identity_mismatch": "rejected_content",
    "sandbox_policy_mismatch": "rejected_content",
    "language_standard_mismatch": "rejected_content",
    "generated_build_metadata_rejected": "rejected_content",
    "license_policy_missing": "rejected_content",
    "llm_usage_terms_unapproved": "incomplete",
    "paid_llm_calls_unacknowledged": "incomplete",
    "profile_disallows_llm": "incomplete",
    "source_only_shortfall": "incomplete",
    "starter_already_passes": "rejected_content",
    "starter_harness_error": "rejected_content",
    "test_discovery_failed": "rejected_content",
    "zero_tests": "rejected_content",
    "reference_compile_failed": "rejected_content",
    "reference_tests_failed": "rejected_content",
    "reference_timeout": "rejected_content",
    "reference_sanitizer_failed": "rejected_content",
    "sanitizer_test_discovery_failed": "rejected_content",
    "sanitizer_test_count_mismatch": "rejected_content",
    "weak_generated_tests": "rejected_content",
    "whole_format_failed": "rejected_content",
    "target_apply_failed": "rejected_content",
    "target_reference_mismatch": "rejected_content",
    "token_overflow": "rejected_content",
    "chat_template_policy_mismatch": "rejected_content",
    "category_quota_unsatisfied": "incomplete",
    "llm_capacity_insufficient": "incomplete",
    "llm_transport_failed": "retryable_error",
    "llm_budget_exhausted": "incomplete",
    "human_review_rejected": "rejected_content",
    "human_review_stale": "incomplete",
    "final_screen_invalidated_split": "incomplete",
    "dataset_release_review_stale": "incomplete",
    "consumer_readiness_missing": "consumer_preflight_failure",
    "consumer_model_revision_mismatch": "consumer_preflight_failure",
    "consumer_tokenizer_mismatch": "consumer_preflight_failure",
    "consumer_export_manifest_mismatch": "consumer_preflight_failure",
    "consumer_template_policy_mismatch": "consumer_preflight_failure",
    "consumer_loss_mask_mismatch": "consumer_preflight_failure",
    "consumer_sequence_length_mismatch": "consumer_preflight_failure",
    "consumer_raw_messages_required": "consumer_preflight_failure",
    "consumer_adapter_mismatch": "consumer_preflight_failure",
    "retryable_error": "retryable_error",
}


def reason_outcome(code: str) -> str:
    return REASON_OUTCOMES.get(code, "failed")


class SourceManifestEntry(StrictModel):
    source_kind: Literal["practice", "concept"]
    slug: str
    source_relative_path: str
    tree_sha256: str
    task_family_id: str
    primary_category: PrimaryCategory
    tags: list[str] = Field(min_length=1)
    difficulty: Difficulty
    intended_split: Split
    spdx_license: Literal["MIT"]
    enabled: bool = True

    @field_validator("slug", "task_family_id")
    @classmethod
    def validate_slug(cls, value: str) -> str:
        if (
            not value
            or value != value.lower()
            or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in value)
        ):
            raise ValueError("must be a normalized lowercase slug")
        return value

    @field_validator("tags")
    @classmethod
    def stable_tags(cls, value: list[str]) -> list[str]:
        if value != sorted(set(value)):
            raise ValueError("tags must be unique and sorted")
        return value


class SourceManifest(StrictModel):
    schema_version: Literal["aider-sft-source-manifest-v1"]
    dataset_profile: Literal[
        "aider-sft-pilot-v1",
        "aider-sft-source-only-75-v1",
    ]
    source_repository: str
    source_revision: str
    source_tree_sha256: str
    taxonomy_version: str
    benchmark_denylist_sha256: str
    entries: list[SourceManifestEntry]

    @field_validator("entries")
    @classmethod
    def unique_entries(cls, value: list[SourceManifestEntry]) -> list[SourceManifestEntry]:
        slugs = [item.slug for item in value]
        paths = [item.source_relative_path for item in value]
        if len(slugs) != len(set(slugs)) or len(paths) != len(set(paths)):
            raise ValueError("source manifest slugs and paths must be unique")
        if slugs != sorted(slugs):
            raise ValueError("source manifest entries must be sorted by slug")
        return value


class FileMapping(StrictModel):
    source_reference: str
    canonical_editable: str | None = None
    canonical_context: str | None = None
    required_relation: str | None = None


class CanonicalFiles(StrictModel):
    editable: list[str]
    model_context: list[str]
    task_specific_tests: list[str]
    shared_grader_support: list[str]
    source_reference_mapping: list[FileMapping] = Field(default_factory=list)
    context_reference_equivalence: list[FileMapping] = Field(default_factory=list)


class SourceIdentity(StrictModel):
    kind: SourceKind
    repository: str
    revision: str
    relative_path: str | None
    license: str
    content_sha256: str


class Classification(StrictModel):
    primary_category: PrimaryCategory
    tags: list[str]
    difficulty: Difficulty


class CanonicalTask(StrictModel):
    schema_version: Literal["aider-sft-task-v1"]
    task_id: str
    root_task_id: str
    task_family_id: str
    title: str
    language: Literal["cpp"]
    language_standard: Literal["c++17"]
    source: SourceIdentity
    classification: Classification
    files: CanonicalFiles
    grader: dict[str, Any]
    generation: dict[str, Any] | None = None
    distribution_scope: Literal["internal_research"]


class ReviewDecision(StrictModel):
    schema_version: Literal["aider-sft-review-decision-v1"]
    scope: ReviewScope
    subject_id: str
    subject_fingerprint: str
    decision: Decision
    reason_code: str
    reviewer: str
    timestamp_utc: str
    comment: str = Field(default="", max_length=2000)


class ReviewSubject(StrictModel):
    schema_version: Literal["aider-sft-review-subject-v1"]
    scope: ReviewScope
    subject_id: str
    subject_fingerprint: str
    payload: dict[str, Any]


class Message(StrictModel):
    role: Literal["user", "assistant"]
    content: str
    step_loss_mask: Literal[0, 1]


class SftRow(StrictModel):
    schema_version: Literal["aider-sft-row-v1"]
    task_id: str
    label: str
    messages: list[Message]
    metadata: dict[str, Any]

    @field_validator("messages")
    @classmethod
    def exact_messages(cls, value: list[Message]) -> list[Message]:
        if len(value) != 2:
            raise ValueError("exactly two messages are required")
        if [(item.role, item.step_loss_mask) for item in value] != [
            ("user", 0),
            ("assistant", 1),
        ]:
            raise ValueError("row must have zero-loss user then loss-bearing assistant")
        return value


class TokenRecord(StrictModel):
    schema_version: Literal["aider-sft-token-record-v1"]
    task_id: str
    row_sha256: str
    rendered_token_sha256: str
    loss_mask_sha256: str
    response_length: int = Field(ge=1)
    response_loss_mask_sha256: str
    token_counts: dict[str, int]
    adapter: Literal["w8-aider-sft-mask-v1"]
    template_kwargs_sha256: str
    tokenizer_repository: str
    tokenizer_revision: str
    chat_template_sha256: str
    sequence_length: int = Field(gt=0)


class AdmissionRecord(StrictModel):
    schema_version: Literal["aider-sft-admission-record-v1"]
    candidate_id: str
    task_id: str | None
    source_kind: SourceKind
    state: CandidateState
    reason_code: str | None
    input_fingerprint: str
    receipt_fingerprints: dict[str, str] = Field(default_factory=dict)


class SplitRecord(StrictModel):
    schema_version: Literal["aider-sft-split-manifest-v1"]
    dataset_profile: str
    seed: int
    admitted_pool_fingerprint: str
    tasks: list[dict[str, Any]]
    counts: dict[str, Any]
