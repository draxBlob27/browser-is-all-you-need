"""Orchestration for the primary Aider-style SFT dataset lifecycle."""

from __future__ import annotations

import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .benchmark import manifest_path as benchmark_manifest_path
from .config import (
    DATASET_PROFILE,
    build_config_lock,
    freeze_report,
    load_config,
    profile_contract,
    profile_contract_from_lock,
    profile_subject_id,
    source_manifest_path,
)
from .contamination import final_screen_policy_fingerprint, final_screen_rows, screen_task
from .errors import AiderSftError
from .export import (
    export_minimal_moonlight_rows,
    export_slime_bundle,
    verify_export_bundle,
)
from .grader_support import reconstruct_support_bundle
from .inventory import (
    build_inventory_proposal,
    promote_source_inventory,
    validate_source_manifest,
)
from .llm_curator import (
    author_candidate,
    capacity_report,
    schedule_cells,
    usage_terms_payload,
)
from .oracle import run_task_oracle, validate_oracle_receipt
from .receipts import create_manifest_and_readiness, verify_ready_bundle
from .renderer import (
    apply_target,
    render_prompt,
    render_row,
    render_target,
    renderer_policy_fingerprint,
)
from .review import (
    export_review_package,
    import_review_decisions,
    matching_decision,
    materialize_review_evidence,
    register_subject,
    state_root,
    subject_path,
)
from .scaffold import materialize_generated_task
from .schema import (
    CandidateState,
    Decision,
    ReviewScope,
    SourceKind,
    Split,
    reason_outcome,
)
from .source_exercism import canonicalize_exercism_task, load_canonical_task
from .split import (
    admitted_pool_report,
    freeze_split,
    propose_split,
    split_task_roots,
)
from .tokenization import (
    attach_token_record,
    compute_token_record,
    consumer_lock_from_config_lock,
    load_locked_tokenizer,
    preflight_loss_mask_generator,
)
from .util import (
    atomic_write,
    canonical_json_bytes,
    chmod_tree_readonly,
    fingerprint,
    read_json,
    require_empty_or_incomplete_root,
    run_lock,
    sha256_bytes,
    sha256_file,
    tree_files,
    write_json,
    write_jsonl,
)


DEFAULT_CONFIG = Path("configs/aider_sft/pilot-v1.toml")
_SOURCE_ADMISSION_FINGERPRINT_DOMAIN = "aider-sft-source-candidate-v2"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _write_run_state(root: Path, state: str, **details: Any) -> None:
    value = {
        "schema_version": "aider-sft-run-state-v1",
        "dataset_state": state,
        "updated_at_utc": _utc_now(),
        **details,
    }
    write_json(state_root(root) / "run-state.json", value)


def _record_path(root: Path, candidate_id: str) -> Path:
    return state_root(root) / "journals" / candidate_id / "terminal.json"


def _write_candidate_record(root: Path, record: dict[str, Any]) -> None:
    write_json(_record_path(root, record["candidate_id"]), record)


def _load_candidate_records(root: Path) -> list[dict[str, Any]]:
    journal_root = state_root(root) / "journals"
    if not journal_root.exists():
        return []
    return [read_json(path) for path in sorted(journal_root.glob("*/terminal.json"))]


def _canonical_task_roots(root: Path) -> list[Path]:
    canonical_root = root / "private/canonical-tasks"
    if not canonical_root.is_dir():
        return []
    return sorted(path for path in canonical_root.iterdir() if path.is_dir())


def _aggregate_ledgers(root: Path) -> None:
    records = sorted(_load_candidate_records(root), key=lambda row: row["candidate_id"])
    write_jsonl(root / "private/admission/records.jsonl", records)
    rejected = [
        row
        for row in records
        if row["state"]
        in {
            CandidateState.REJECTED_CONTENT.value,
            CandidateState.DEFERRED_PROFILE.value,
        }
    ]
    write_jsonl(root / "private/rejected/records.jsonl", rejected)
    summary = {
        "schema_version": "aider-sft-admission-summary-v1",
        "candidates": len(records),
        "states": dict(sorted(Counter(row["state"] for row in records).items())),
        "reason_codes": dict(
            sorted(
                Counter(row.get("reason_code") for row in records if row.get("reason_code")).items()
            )
        ),
    }
    write_json(root / "private/admission/summary.json", summary)

    request_root = state_root(root) / "generation/requests"
    generation_records = (
        [read_json(path) for path in sorted(request_root.glob("*.json"))]
        if request_root.exists()
        else []
    )
    safe_records = [
        {key: value for key, value in record.items() if key not in {"request", "normalized_output"}}
        for record in generation_records
    ]
    write_jsonl(root / "private/generation/records.jsonl", safe_records)
    write_json(
        root / "private/generation/summary.json",
        {
            "schema_version": "aider-sft-generation-summary-v1",
            "requests": len(safe_records),
            "states": dict(sorted(Counter(row["status"] for row in safe_records).items())),
        },
    )


def _copy_if_exact(source: Path, destination: Path) -> None:
    payload = source.read_bytes()
    if destination.exists() and destination.read_bytes() != payload:
        raise AiderSftError("human_review_stale", f"bound artifact changed: {destination}")
    atomic_write(destination, payload)


def plan_dataset(
    *,
    config_path: Path,
    repo_root: Path,
) -> dict[str, Any]:
    config = load_config(config_path)
    source_path = source_manifest_path(repo_root, config.dataset.profile)
    report = freeze_report(
        config,
        repo_root=repo_root,
        source_manifest_path=source_path,
    )
    return {
        "command": "plan",
        "no_spend": True,
        "no_generation": True,
        "dataset_profile": config.dataset.profile,
        **report,
    }


def inventory_dataset(
    *,
    config_path: Path,
    output_root: Path,
    repo_root: Path,
) -> dict[str, Any]:
    with run_lock(output_root):
        result = build_inventory_proposal(
            config_path=config_path,
            output_root=output_root,
            repo_root=repo_root,
        )
        _write_run_state(
            output_root,
            "awaiting_inventory_review",
            source_candidates=result["source_candidates"],
            required_llm_admissions=result["required_llm_admissions"],
        )
        return result


def promote_inventory(
    *,
    proposal_path: Path,
    decisions_path: Path,
    output_path: Path,
    repo_root: Path,
    config_path: Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    return promote_source_inventory(
        proposal_path=proposal_path,
        decisions_path=decisions_path,
        output_path=output_path,
        repo_root=repo_root,
        config_path=config_path,
    )


def _prepare_build_root(
    *,
    root: Path,
    repo_root: Path,
    config_path: Path,
    resume: bool,
) -> tuple[dict[str, Any], Any]:
    require_empty_or_incomplete_root(root, resume=resume)
    config = load_config(config_path)
    source_path = source_manifest_path(repo_root, config.dataset.profile)
    source_manifest = validate_source_manifest(
        source_path,
        repo_root,
        expected_profile=config.dataset.profile,
    )
    config_lock = build_config_lock(
        config,
        repo_root=repo_root,
        source_manifest_path=source_path,
    )
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / "config.lock.json"
    if lock_path.exists() and read_json(lock_path) != config_lock:
        raise AiderSftError("human_review_stale", "existing config lock differs")
    write_json(lock_path, config_lock)
    _copy_if_exact(source_path, root / "source-manifest.json")
    _copy_if_exact(
        benchmark_manifest_path(repo_root),
        root / "benchmark-denylist.json",
    )
    consumer_lock = consumer_lock_from_config_lock(config_lock)
    write_json(root / "consumer-lock.json", consumer_lock)
    tokenizer = config_lock["config"]["tokenizer"]
    write_json(
        root / "tokenizer-render-policy.json",
        {
            "schema_version": "aider-sft-tokenizer-policy-v1",
            "repository": tokenizer["repository"],
            "revision": tokenizer["revision"],
            "chat_template_sha256": tokenizer["chat_template_sha256"],
            "kwargs": tokenizer["apply_chat_template_kwargs"],
            "policy": tokenizer["policy"],
            "adapter": tokenizer["mask_adapter"],
            "loss_mask_type": tokenizer["loss_mask_type"],
            "sequence_length": tokenizer["sequence_length"],
        },
    )
    contract = profile_contract_from_lock(config_lock)
    if contract.llm_enabled:
        register_subject(
            root,
            scope=ReviewScope.LLM_USAGE_TERMS,
            subject_id=profile_subject_id(
                contract.profile,
                "llm-usage-terms",
            ),
            payload=usage_terms_payload(config_lock),
        )
    return config_lock, source_manifest


def _contamination_decision_state(root: Path, receipt: dict[str, Any]) -> str:
    for flag in receipt["flags"]:
        decision = matching_decision(
            root,
            scope=ReviewScope.CONTAMINATION_FLAG,
            subject_id=flag["flag_id"],
            subject_fingerprint=flag["subject_fingerprint"],
        )
        if decision is None:
            return "awaiting"
        if decision.decision is Decision.REJECT:
            return "rejected"
    return "approved"


def _whole_gate(task_root: Path) -> None:
    task = load_canonical_task(task_root)
    target = render_target(task_root, task)
    starter = {
        relative: (task_root / "workspace/starter" / relative).read_bytes()
        for relative in task.files.editable
    }
    reference = {
        relative: (task_root / "workspace/reference" / relative).read_bytes()
        for relative in task.files.editable
    }
    if apply_target(starter, target, expected_files=task.files.editable) != reference:
        raise AiderSftError("target_reference_mismatch", f"whole target differs: {task.task_id}")


def _admit_staged_task(staged_task: Path, canonical_root: Path) -> None:
    task = load_canonical_task(staged_task)
    destination = canonical_root / task.task_id
    if destination.exists():
        observed = load_canonical_task(destination)
        if observed.source.content_sha256 != task.source.content_sha256:
            raise AiderSftError("duplicate_task", f"task ID collision: {task.task_id}")
        return
    shutil.copytree(staged_task, destination)


def _source_record(
    *,
    entry: Any,
    state: CandidateState,
    task_id: str | None,
    reason_code: str | None,
    receipts: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "aider-sft-admission-record-v1",
        "candidate_id": f"source-{entry.slug}",
        "task_id": task_id,
        "source_kind": SourceKind.EXERCISM.value,
        "state": state.value,
        "reason_code": reason_code,
        "input_fingerprint": _source_input_fingerprint(entry),
        "receipt_fingerprints": receipts or {},
        "intended_split": entry.intended_split.value,
        "primary_category": entry.primary_category.value,
    }


def _source_input_fingerprint(entry: Any) -> str:
    return fingerprint(
        _SOURCE_ADMISSION_FINGERPRINT_DOMAIN,
        entry.model_dump(mode="json"),
    )


def _source_terminal_record_is_current(record: dict[str, Any], entry: Any) -> bool:
    if record.get("reason_code") == "final_screen_invalidated_split":
        if not _late_failure_reason_invalidates_task(
            str(record.get("late_failure_reason_code") or "")
        ):
            return False
        if record.get("late_failure_renderer_fingerprint") != renderer_policy_fingerprint():
            return False
        if record.get("late_failure_final_screen_fingerprint") != final_screen_policy_fingerprint():
            return False
    return record.get("input_fingerprint") == _source_input_fingerprint(entry)


def _late_failure_reason_invalidates_task(reason_code: str) -> bool:
    return (
        reason_code == "final_screen_invalidated_split"
        or reason_outcome(reason_code) == "rejected_content"
    )


def _late_failure_invalidates_task(failure: AiderSftError) -> bool:
    return _late_failure_reason_invalidates_task(failure.reason_code)


def _process_sources(
    *,
    root: Path,
    repo_root: Path,
    source_manifest: Any,
    config_lock: dict[str, Any],
) -> dict[str, int]:
    from w8_biayn.constants import UPSTREAMS
    from w8_biayn.upstreams import upstream_path

    checkout = upstream_path(UPSTREAMS["exercism-cpp"], repo_root)
    support_root = root / "private/grader-support"
    reconstruct_support_bundle(
        checkout=checkout,
        destination_root=support_root,
        repo_root=repo_root,
    )
    canonical_root = root / "private/canonical-tasks"
    admitted = rejected = awaiting = 0
    prior_roots = _canonical_task_roots(root)
    prior_records = {record["candidate_id"]: record for record in _load_candidate_records(root)}
    for entry in source_manifest.entries:
        prior = prior_records.get(f"source-{entry.slug}")
        if (
            prior is not None
            and prior["state"]
            in {
                CandidateState.REJECTED_CONTENT.value,
                CandidateState.DEFERRED_PROFILE.value,
            }
            and _source_terminal_record_is_current(prior, entry)
        ):
            if prior["state"] == CandidateState.REJECTED_CONTENT.value:
                rejected += 1
            continue
        if not entry.enabled:
            _write_candidate_record(
                root,
                _source_record(
                    entry=entry,
                    state=CandidateState.DEFERRED_PROFILE,
                    task_id=None,
                    reason_code="source_deferred_by_profile",
                ),
            )
            continue
        candidate_root = root / "private/candidates" / f"source-{entry.slug}"
        staged_parent = candidate_root / "canonical"
        try:
            result = canonicalize_exercism_task(
                entry=entry,
                checkout=checkout,
                canonical_root=staged_parent,
                config_lock=config_lock,
            )
            staged_task = Path(result["task_root"])
            oracle_path = staged_task / "receipts/oracle.json"
            if oracle_path.is_file():
                oracle = validate_oracle_receipt(
                    task_root=staged_task,
                    shared_support_root=support_root,
                    config_lock=config_lock,
                )
            else:
                oracle = run_task_oracle(
                    task_root=staged_task,
                    shared_support_root=support_root,
                    config_lock=config_lock,
                )
            _whole_gate(staged_task)
            contamination = screen_task(
                task_root=staged_task,
                repo_root=repo_root,
                root=root,
                config_lock=config_lock,
                other_tasks=[path for path in prior_roots if path.name != entry.slug],
            )
            review_state = _contamination_decision_state(root, contamination)
            receipts = {
                "static": result["static_receipt"]["input_fingerprint"],
                "oracle": oracle["oracle_fingerprint"],
                "contamination": contamination["receipt_fingerprint"],
            }
            if review_state == "rejected":
                state = CandidateState.REJECTED_CONTENT
                reason = "human_review_rejected"
                rejected += 1
            elif review_state == "awaiting":
                state = CandidateState.AWAITING_TASK_REVIEW
                reason = "contamination_review_required"
                awaiting += 1
            else:
                _admit_staged_task(staged_task, canonical_root)
                admitted_root = canonical_root / entry.slug
                if admitted_root not in prior_roots:
                    prior_roots.append(admitted_root)
                state = CandidateState.ADMITTED
                reason = None
                admitted += 1
            _write_candidate_record(
                root,
                _source_record(
                    entry=entry,
                    state=state,
                    task_id=entry.slug,
                    reason_code=reason,
                    receipts=receipts,
                ),
            )
        except AiderSftError as exc:
            state = (
                CandidateState.RETRYABLE_ERROR
                if exc.outcome == "retryable_error"
                else CandidateState.REJECTED_CONTENT
            )
            _write_candidate_record(
                root,
                _source_record(
                    entry=entry,
                    state=state,
                    task_id=None,
                    reason_code=exc.reason_code,
                ),
            )
            if state is CandidateState.RETRYABLE_ERROR:
                raise
            rejected += 1
    return {"admitted": admitted, "rejected": rejected, "awaiting_review": awaiting}


def _semantic_subject(
    *,
    root: Path,
    staged_task: Path,
    usage_decision: Any,
) -> dict[str, Any]:
    task = load_canonical_task(staged_task)
    included_files = {
        relative: sha256_bytes(payload)
        for relative, payload in tree_files(staged_task).items()
        if (
            relative == "task.json"
            or relative.startswith(
                (
                    "docs/",
                    "workspace/",
                    "grader/tests/",
                    "grader/negative-solutions/",
                    "provenance/generation.json",
                )
            )
            or relative
            in {
                "grader/shared-support.json",
                "grader/build/CMakeLists.txt",
                "receipts/oracle.json",
                "receipts/contamination.json",
                "receipts/mutation.json",
            }
        )
    }
    return register_subject(
        root,
        scope=ReviewScope.LLM_TASK_SEMANTICS,
        subject_id=task.task_id,
        payload={
            "task_id": task.task_id,
            "task_family_id": task.task_family_id,
            "classification": task.classification.model_dump(mode="json"),
            "source_content_sha256": task.source.content_sha256,
            "generation": task.generation,
            "files": dict(sorted(included_files.items())),
            "usage_terms_decision_sha256": sha256_bytes(
                canonical_json_bytes(usage_decision.model_dump(mode="json"))
            ),
            "grader_scaffold_fingerprint": fingerprint("aider-sft-grader-scaffold-v1", task.grader),
            "private_access_path": str(staged_task),
        },
    )


def _generated_record(
    *,
    candidate_id: str,
    task: Any | None,
    cell: dict[str, str],
    state: CandidateState,
    reason_code: str | None,
    fingerprints: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "aider-sft-admission-record-v1",
        "candidate_id": candidate_id,
        "task_id": task.task_id if task is not None else None,
        "source_kind": SourceKind.LLM_ASSISTED.value,
        "state": state.value,
        "reason_code": reason_code,
        "input_fingerprint": fingerprint("aider-sft-generated-cell-v1", candidate_id, cell),
        "receipt_fingerprints": fingerprints or {},
        "intended_split": cell["intended_split"],
        "primary_category": cell["primary_category"],
    }


def _process_existing_generated(
    *,
    root: Path,
) -> dict[str, int]:
    canonical_root = root / "private/canonical-tasks"
    result = {"admitted": 0, "rejected": 0, "awaiting_review": 0}
    for record in _load_candidate_records(root):
        if (
            record["source_kind"] != SourceKind.LLM_ASSISTED.value
            or record["state"] != CandidateState.AWAITING_TASK_REVIEW.value
        ):
            continue
        candidate_root = root / "private/candidates" / record["candidate_id"] / "canonical"
        task_roots = [path for path in candidate_root.iterdir() if path.is_dir()]
        if len(task_roots) != 1:
            raise AiderSftError("static_schema_error", "generated candidate staging is incomplete")
        staged_task = task_roots[0]
        task = load_canonical_task(staged_task)
        subject_path = (
            state_root(root)
            / "review-subjects"
            / ReviewScope.LLM_TASK_SEMANTICS.value
            / f"{task.task_id}.json"
        )
        subject = read_json(subject_path)
        semantic = matching_decision(
            root,
            scope=ReviewScope.LLM_TASK_SEMANTICS,
            subject_id=task.task_id,
            subject_fingerprint=subject["subject_fingerprint"],
        )
        contamination = read_json(staged_task / "receipts/contamination.json")
        contamination_state = _contamination_decision_state(root, contamination)
        if (
            semantic is not None and semantic.decision is Decision.REJECT
        ) or contamination_state == "rejected":
            record["state"] = CandidateState.REJECTED_CONTENT.value
            record["reason_code"] = "human_review_rejected"
            _write_candidate_record(root, record)
            result["rejected"] += 1
        elif semantic is None or contamination_state == "awaiting":
            result["awaiting_review"] += 1
        else:
            _admit_staged_task(staged_task, canonical_root)
            record["state"] = CandidateState.ADMITTED.value
            record["reason_code"] = None
            _write_candidate_record(root, record)
            result["admitted"] += 1
    return result


def _next_candidate_id(root: Path, cell: dict[str, str]) -> str:
    serial_path = state_root(root) / "generation/serial.json"
    serials = read_json(serial_path) if serial_path.is_file() else {}
    key = f"{cell['primary_category']}::{cell['intended_split']}"
    serials[key] = int(serials.get(key, 0)) + 1
    write_json(serial_path, serials)
    category = (
        cell["primary_category"].lower().replace("&", "and").replace(",", "").replace(" ", "-")
    )
    return f"llm-{category}-{cell['intended_split']}-{serials[key]:03d}"


def _awaiting_cells(root: Path) -> Counter[tuple[str, str]]:
    return Counter(
        (record["primary_category"], record["intended_split"])
        for record in _load_candidate_records(root)
        if record["source_kind"] == SourceKind.LLM_ASSISTED.value
        and record["state"] == CandidateState.AWAITING_TASK_REVIEW.value
    )


def _generate_missing_candidates(
    *,
    root: Path,
    repo_root: Path,
    source_manifest: Any,
    config_lock: dict[str, Any],
    usage_decision: Any,
    acknowledge_paid_calls: bool,
) -> dict[str, int]:
    task_roots = _canonical_task_roots(root)
    report = admitted_pool_report(
        task_roots=task_roots,
        source_manifest=source_manifest,
        profile=config_lock["config"]["dataset"]["profile"],
    )
    used_candidates = sum(
        record["source_kind"] == SourceKind.LLM_ASSISTED.value
        for record in _load_candidate_records(root)
    )
    capacity = capacity_report(
        config_lock=config_lock,
        deficit_cells=report["deficit_cells"],
        used_candidates=used_candidates,
    )
    write_json(root / "reports/capacity-summary.json", capacity)
    if capacity["status"] != "sufficient":
        raise AiderSftError(
            "llm_capacity_insufficient",
            "capacity is insufficient: " + ", ".join(capacity["insufficient_fields"]),
        )
    scheduled = schedule_cells(report["deficit_cells"])
    awaiting = _awaiting_cells(root)
    needed: list[dict[str, str]] = []
    for cell in scheduled:
        key = (cell["primary_category"], cell["intended_split"])
        if awaiting[key]:
            awaiting[key] -= 1
        else:
            needed.append(cell)
    budgets = config_lock["config"]["llm"]["budgets"]
    existing_count = sum(path.is_dir() for path in (root / "private/candidates").glob("llm-*"))
    generated = rejected = 0
    for cell in needed:
        if existing_count >= budgets["total_candidates"]:
            raise AiderSftError("llm_budget_exhausted", "candidate budget is exhausted")
        candidate_id = _next_candidate_id(root, cell)
        candidate_root = root / "private/candidates" / candidate_id
        try:
            candidate = author_candidate(
                root=root,
                candidate_id=candidate_id,
                cell=cell,
                config_lock=config_lock,
                acknowledge_paid_calls=acknowledge_paid_calls,
            )
            result = materialize_generated_task(
                candidate_value=candidate,
                canonical_root=candidate_root / "canonical",
                config_lock=config_lock,
            )
            staged_task = Path(result["task_root"])
            oracle = run_task_oracle(
                task_root=staged_task,
                shared_support_root=root / "private/grader-support",
                config_lock=config_lock,
            )
            _whole_gate(staged_task)
            contamination = screen_task(
                task_root=staged_task,
                repo_root=repo_root,
                root=root,
                config_lock=config_lock,
                other_tasks=[path for path in _canonical_task_roots(root)],
            )
            semantic = _semantic_subject(
                root=root,
                staged_task=staged_task,
                usage_decision=usage_decision,
            )
            task = load_canonical_task(staged_task)
            _write_candidate_record(
                root,
                _generated_record(
                    candidate_id=candidate_id,
                    task=task,
                    cell=cell,
                    state=CandidateState.AWAITING_TASK_REVIEW,
                    reason_code=(
                        "contamination_review_required"
                        if contamination["flags"]
                        else "human_review_stale"
                    ),
                    fingerprints={
                        "oracle": oracle["oracle_fingerprint"],
                        "contamination": contamination["receipt_fingerprint"],
                        "semantic_subject": semantic["subject_fingerprint"],
                    },
                ),
            )
            generated += 1
        except AiderSftError as exc:
            _write_candidate_record(
                root,
                _generated_record(
                    candidate_id=candidate_id,
                    task=None,
                    cell=cell,
                    state=(
                        CandidateState.RETRYABLE_ERROR
                        if exc.outcome == "retryable_error"
                        else CandidateState.DEFERRED_PROFILE
                        if exc.outcome == "incomplete"
                        else CandidateState.REJECTED_CONTENT
                    ),
                    reason_code=exc.reason_code,
                ),
            )
            if exc.outcome in {"retryable_error", "incomplete"}:
                raise
            rejected += 1
        existing_count += 1
    return {"generated": generated, "mechanically_rejected": rejected}


def build_dataset(
    *,
    config_path: Path,
    output_root: Path,
    repo_root: Path,
    resume: bool,
    acknowledge_paid_llm_calls: bool,
) -> dict[str, Any]:
    with run_lock(output_root):
        config_lock, source_manifest = _prepare_build_root(
            root=output_root,
            repo_root=repo_root,
            config_path=config_path,
            resume=resume,
        )
        contract = profile_contract_from_lock(config_lock)
        if not contract.llm_enabled and acknowledge_paid_llm_calls:
            raise AiderSftError(
                "profile_disallows_llm",
                f"{contract.profile} cannot acknowledge or make paid LLM calls",
            )
        _write_run_state(output_root, "pool_filling")
        source_result = _process_sources(
            root=output_root,
            repo_root=repo_root,
            source_manifest=source_manifest,
            config_lock=config_lock,
        )
        if contract.llm_enabled:
            _process_existing_generated(root=output_root)
        elif any(
            record["source_kind"] == SourceKind.LLM_ASSISTED.value
            for record in _load_candidate_records(output_root)
        ):
            raise AiderSftError(
                "profile_disallows_llm",
                "source-only construction state contains an LLM-assisted candidate",
            )
        _aggregate_ledgers(output_root)

        generated = {"generated": 0, "mechanically_rejected": 0}
        existing = {"admitted": 0, "rejected": 0, "awaiting_review": 0}
        if contract.llm_enabled:
            usage_id = profile_subject_id(contract.profile, "llm-usage-terms")
            usage_subject = read_json(
                subject_path(
                    output_root,
                    ReviewScope.LLM_USAGE_TERMS,
                    usage_id,
                )
            )
            usage_decision = matching_decision(
                output_root,
                scope=ReviewScope.LLM_USAGE_TERMS,
                subject_id=usage_subject["subject_id"],
                subject_fingerprint=usage_subject["subject_fingerprint"],
            )
            if usage_decision is None or usage_decision.decision is Decision.REJECT:
                _write_run_state(
                    output_root,
                    "incomplete",
                    reason_code="llm_usage_terms_unapproved",
                    source=source_result,
                )
                return {
                    "status": "incomplete",
                    "reason_code": "llm_usage_terms_unapproved",
                    "source": source_result,
                    "next": (
                        "review-export, approve llm_usage_terms, then "
                        "review-import and resume build"
                    ),
                }

            retryable_generated = [
                record["candidate_id"]
                for record in _load_candidate_records(output_root)
                if record["source_kind"] == SourceKind.LLM_ASSISTED.value
                and record["state"] == CandidateState.RETRYABLE_ERROR.value
            ]
            if retryable_generated:
                raise AiderSftError(
                    "llm_transport_failed",
                    "ambiguous generated requests require reconciliation before resume: "
                    + ", ".join(sorted(retryable_generated)),
                )
            pre_generation_roots = _canonical_task_roots(output_root)
            pre_generation_report = admitted_pool_report(
                task_roots=pre_generation_roots,
                source_manifest=source_manifest,
                profile=contract.profile,
            )
            if (
                pre_generation_report["counts"]["total"] < contract.total_roots
                and not acknowledge_paid_llm_calls
            ):
                _write_run_state(
                    output_root,
                    "incomplete",
                    reason_code="paid_llm_calls_unacknowledged",
                )
                return {
                    "status": "incomplete",
                    "reason_code": "paid_llm_calls_unacknowledged",
                    "admitted": pre_generation_report["counts"]["total"],
                    "next": "rerun build --resume --acknowledge-paid-llm-calls",
                }
            generated = _generate_missing_candidates(
                root=output_root,
                repo_root=repo_root,
                source_manifest=source_manifest,
                config_lock=config_lock,
                usage_decision=usage_decision,
                acknowledge_paid_calls=acknowledge_paid_llm_calls,
            )
            existing = _process_existing_generated(root=output_root)
        _aggregate_ledgers(output_root)
        task_roots = _canonical_task_roots(output_root)
        report = admitted_pool_report(
            task_roots=task_roots,
            source_manifest=source_manifest,
            profile=contract.profile,
        )
        write_json(output_root / "reports/admitted-pool.json", report)
        if not contract.llm_enabled:
            required = sum(
                max(value, 0)
                for cells in report["deficit_cells"].values()
                for value in cells.values()
            )
            write_json(
                output_root / "reports/capacity-summary.json",
                {
                    "schema_version": "aider-sft-capacity-report-v1",
                    "llm_enabled": False,
                    "required_llm_admissions": 0,
                    "source_root_shortfall": required,
                    "reserve_multiplier": 0,
                    "minimum_candidate_capacity": 0,
                    "configured_candidate_capacity": 0,
                    "used_candidate_capacity": 0,
                    "remaining_candidate_capacity": 0,
                    "minimum_stage_calls": 0,
                    "configured_total_calls": 0,
                    "status": "sufficient" if required == 0 else "source_only_shortfall",
                    "insufficient_fields": [] if required == 0 else ["source_roots"],
                },
            )
        if report["counts"]["total"] < contract.total_roots:
            awaiting_review = (
                source_result["awaiting_review"]
                + existing["awaiting_review"]
                + generated["generated"]
            )
            reason_code = (
                "human_review_stale"
                if awaiting_review
                else "source_only_shortfall"
                if not contract.llm_enabled
                else "human_review_stale"
            )
            _write_run_state(
                output_root,
                "pool_filling",
                reason_code=reason_code,
                admitted=report["counts"]["total"],
                awaiting_review=awaiting_review,
            )
            return {
                "status": "incomplete",
                "reason_code": reason_code,
                "admitted": report["counts"]["total"],
                "generated": generated,
                "awaiting_review": awaiting_review,
                "next": (
                    "review-export, import pending decisions, then resume build"
                    if awaiting_review
                    else (
                        "the source-only profile cannot backfill a rejected source root; "
                        "inspect the admission ledger"
                    )
                    if not contract.llm_enabled
                    else "inspect the capacity summary and generation rejection ledger"
                ),
            }
        proposed = propose_split(
            root=output_root,
            task_roots=task_roots,
            source_manifest=source_manifest,
            config_lock=config_lock,
        )
        _write_run_state(
            output_root,
            "awaiting_split_review",
            admitted=report["counts"]["total"],
            subject_fingerprint=proposed["subject"]["subject_fingerprint"],
        )
        return {
            "status": "awaiting_split_review",
            "admitted": report["counts"]["total"],
            "split_subject": proposed["subject"]["subject_fingerprint"],
            "next": "review-export, approve final_split, then finalize",
        }


def review_export(*, root: Path, output: Path) -> dict[str, Any]:
    return export_review_package(root, output)


def review_import(*, root: Path, decisions_path: Path) -> dict[str, Any]:
    if (root / "readiness.json").is_file():
        raise AiderSftError("human_review_stale", "ready dataset review evidence is immutable")
    config_lock = read_json(root / "config.lock.json")
    with run_lock(root):
        return import_review_decisions(
            root,
            decisions_path,
            config_lock=config_lock,
        )


def _eval_artifacts(root: Path, groups: dict[Split, list[Path]]) -> None:
    index: list[dict[str, Any]] = []
    for split in (Split.VALIDATION, Split.TEST):
        rows: list[dict[str, Any]] = []
        for task_root in groups[split]:
            task = load_canonical_task(task_root)
            eval_id = (
                "eval-"
                + fingerprint(
                    "aider-sft-eval-id-v1",
                    split.value,
                    task.source.content_sha256,
                )[:20]
            )
            rows.append(
                {
                    "task_id": eval_id,
                    "label": eval_id,
                    "messages": [{"role": "user", "content": render_prompt(task_root, task)}],
                    "metadata": {
                        "schema_version": "aider-sft-eval-prompt-v1",
                        "subset": split.value,
                        "task_id": eval_id,
                        "primary_category": task.classification.primary_category.value,
                        "difficulty": task.classification.difficulty.value,
                    },
                }
            )
            index.append(
                {
                    "eval_id": eval_id,
                    "split": split.value,
                    "task_id": task.task_id,
                    "canonical_path": f"private/canonical-tasks/{task.task_id}",
                    "task_content_sha256": task.source.content_sha256,
                }
            )
        write_jsonl(
            root / f"eval/{split.value}.jsonl", sorted(rows, key=lambda row: row["task_id"])
        )
    write_json(
        root / "private/evaluator-index.json",
        {
            "schema_version": "aider-sft-evaluator-index-v1",
            "entries": sorted(index, key=lambda row: row["eval_id"]),
        },
    )


def _token_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    values = sorted(record["token_counts"]["total"] for record in records)

    def percentile(fraction: float) -> int:
        return values[min(round((len(values) - 1) * fraction), len(values) - 1)]

    return {
        "schema_version": "aider-sft-token-summary-v1",
        "rows": len(values),
        "min": values[0],
        "median": percentile(0.5),
        "p95": percentile(0.95),
        "max": values[-1],
        "loss_bearing_total": sum(record["token_counts"]["loss_bearing"] for record in records),
    }


def _release_documents(
    *,
    root: Path,
    config_lock: dict[str, Any],
    rows: list[dict[str, Any]],
    records: list[dict[str, Any]],
) -> None:
    split = read_json(root / "split-manifest.json")
    tasks = split["tasks"]
    category = Counter(row["primary_category"] for row in tasks)
    difficulty = Counter(row["difficulty"] for row in tasks)
    provenance = Counter(row["source_kind"] for row in tasks)
    write_json(
        root / "reports/category-summary.json",
        {
            "schema_version": "aider-sft-category-summary-v1",
            "counts": dict(sorted(category.items())),
        },
    )
    write_json(
        root / "reports/difficulty-summary.json",
        {
            "schema_version": "aider-sft-difficulty-summary-v1",
            "counts": dict(sorted(difficulty.items())),
        },
    )
    write_json(root / "reports/token-summary.json", _token_summary(records))
    write_json(
        root / "reports/release-summary.json",
        {
            "schema_version": "aider-sft-release-summary-v1",
            "total_roots": len(tasks),
            "train_rows": len(rows),
            "split_counts": split["counts"]["by_split"],
            "provenance_counts": dict(sorted(provenance.items())),
            "distribution_scope": "internal_research",
            "benchmark_roots_excluded": 26,
        },
    )
    licenses = {
        "schema_version": "aider-sft-license-records-v1",
        "distribution_scope": "internal_research",
        "records": [
            {
                "source_kind": "exercism",
                "spdx": "MIT",
                "repository": config_lock["config"]["upstreams"]["exercism_cpp"]["repository"],
                "revision": config_lock["config"]["upstreams"]["exercism_cpp"]["revision"],
            }
        ],
    }
    llm_config = config_lock["config"].get("llm")
    if provenance.get("llm_assisted", 0):
        if not isinstance(llm_config, dict):
            raise AiderSftError(
                "profile_disallows_llm",
                "release contains LLM-assisted roots without an LLM-enabled profile",
            )
        licenses["records"].append(
            {
                "source_kind": "llm_assisted",
                "spdx": "NOASSERTION",
                "provider": llm_config["provider"],
                "model": llm_config["model"],
                "terms_snapshot_sha256": llm_config["usage_terms_snapshot_sha256"],
            }
        )
    write_json(root / "licenses.json", licenses)
    write_json(
        root / "reports/license-summary.json",
        {
            "schema_version": "aider-sft-license-summary-v1",
            "source_mit": provenance.get("exercism", 0),
            "generated_noassertion": provenance.get("llm_assisted", 0),
            "public_redistribution_approved": False,
        },
    )
    contract = profile_contract_from_lock(config_lock)
    split_counts = {
        subset.value: split["counts"]["by_split"].get(subset.value, 0) for subset in Split
    }
    if contract.llm_enabled:
        composition = (
            "It combines pinned MIT-licensed Exercism inputs with human-approved "
            "LLM-assisted task artifacts whose license is recorded as NOASSERTION."
        )
    else:
        composition = (
            "It contains only the exact pinned, non-benchmark MIT-licensed Exercism "
            "inventory; this profile performs no LLM authoring or API calls."
        )
    card = f"""# Aider-style C++ SFT dataset

Dataset ID: {config_lock["dataset_id"]}
Dataset profile: {contract.profile}

This internal-research dataset contains {len(tasks)} verified C++17 task roots:
{len(rows)} raw-message training rows, {split_counts["validation"]} validation prompts,
and {split_counts["test"]} internal-test prompts. {composition} All 26 official Aider
Polyglot C++ roots are held out.

Training rows contain only the task prompt and final Aider whole-file answer. Tests,
references, oracle receipts, review comments, and evaluator mappings remain private.
Readiness proves data construction and does not claim model quality, uplift, or a
benchmark score. Public redistribution is not approved by this profile.
"""
    atomic_write(root / "DATASET_CARD.md", card.encode("utf-8"))
    notice_lines = [
        "Internal research use only.",
        "Exercism C++ source tasks: Copyright their contributors, MIT License.",
    ]
    if provenance.get("llm_assisted", 0):
        notice_lines.append(
            "LLM-assisted artifacts: NOASSERTION; see licenses.json and reviewed provider terms."
        )
    else:
        notice_lines.append("No LLM-assisted artifacts or authoring API calls are in this profile.")
    notice_lines.append("Official Aider Polyglot C++ benchmark tasks are excluded.")
    notice = "\n".join(notice_lines) + "\n"
    atomic_write(root / "NOTICE", notice.encode("utf-8"))


def _release_subject(root: Path) -> dict[str, Any]:
    config_lock = read_json(root / "config.lock.json")
    profile = config_lock["config"]["dataset"]["profile"]
    included = [
        "split-manifest.json",
        "sft/train.jsonl",
        "sft/token-records.jsonl",
        "eval/validation.jsonl",
        "eval/test.jsonl",
        "reports/category-summary.json",
        "reports/difficulty-summary.json",
        "reports/token-summary.json",
        "reports/capacity-summary.json",
        "reports/release-summary.json",
        "reports/license-summary.json",
        "DATASET_CARD.md",
        "NOTICE",
        "licenses.json",
        "consumer-lock.json",
        "tokenizer-render-policy.json",
    ]
    payload = {
        "artifacts": {relative: sha256_file(root / relative) for relative in included},
        "distribution_scope": "internal_research",
        "sanitized_export_allowlist": [
            "DATASET_CARD.md",
            "NOTICE",
            "consumer-lock.json",
            "licenses.json",
            "readiness.json",
            "sft/token-records.jsonl",
            "sft/train.jsonl",
        ],
        "private_assets_excluded": True,
    }
    return register_subject(
        root,
        scope=ReviewScope.DATASET_RELEASE,
        subject_id=profile_subject_id(profile, "dataset-release"),
        payload=payload,
    )


def _invalidate_frozen_split(
    *,
    root: Path,
    task_id: str,
    failure: AiderSftError,
) -> dict[str, Any]:
    if not _late_failure_invalidates_task(failure):
        raise failure
    config_path = root / "config.lock.json"
    profile = (
        read_json(config_path)["config"]["dataset"]["profile"]
        if config_path.is_file()
        else DATASET_PROFILE
    )
    records = _load_candidate_records(root)
    matches = [
        record
        for record in records
        if record.get("task_id") == task_id and record.get("state") == CandidateState.ADMITTED.value
    ]
    if len(matches) != 1:
        raise AiderSftError(
            "static_schema_error",
            f"late failure cannot be bound to one admitted candidate: {task_id}",
        )
    record = matches[0]
    record["state"] = CandidateState.REJECTED_CONTENT.value
    record["reason_code"] = "final_screen_invalidated_split"
    record["late_failure_reason_code"] = failure.reason_code
    record["late_failure_renderer_fingerprint"] = renderer_policy_fingerprint()
    record["late_failure_final_screen_fingerprint"] = final_screen_policy_fingerprint()
    record["late_failure_fingerprint"] = fingerprint(
        "aider-sft-late-failure-v1",
        task_id,
        failure.reason_code,
        failure.message,
    )
    _write_candidate_record(root, record)

    canonical_task = root / "private/canonical-tasks" / task_id
    if canonical_task.exists():
        shutil.rmtree(canonical_task)

    for relative in (
        "split-manifest.json",
        "sft/train.jsonl",
        "sft/token-records.jsonl",
        "eval/validation.jsonl",
        "eval/test.jsonl",
        "private/evaluator-index.json",
        "private/review/dataset-release-subject.json",
        "reports/admitted-pool.json",
        "reports/final-contamination.json",
        "reports/category-summary.json",
        "reports/difficulty-summary.json",
        "reports/token-summary.json",
        "reports/release-summary.json",
        "reports/license-summary.json",
        "DATASET_CARD.md",
        "NOTICE",
        "licenses.json",
    ):
        path = root / relative
        if path.is_file() or path.is_symlink():
            path.unlink()

    for path in (
        state_root(root) / "proposed-split.json",
        subject_path(
            root,
            ReviewScope.FINAL_SPLIT,
            profile_subject_id(profile, "final-split"),
        ),
        subject_path(
            root,
            ReviewScope.DATASET_RELEASE,
            profile_subject_id(profile, "dataset-release"),
        ),
    ):
        if path.is_file() or path.is_symlink():
            path.unlink()

    _aggregate_ledgers(root)
    _write_run_state(
        root,
        "pool_filling",
        reason_code="final_screen_invalidated_split",
        rejected_task_id=task_id,
        late_failure_reason_code=failure.reason_code,
    )
    contract = profile_contract(profile)
    return {
        "status": "incomplete",
        "reason_code": "final_screen_invalidated_split",
        "rejected_task_id": task_id,
        "late_failure_reason_code": failure.reason_code,
        "next": (
            "inspect the rejected source; this source-only profile cannot backfill the shortfall"
            if not contract.llm_enabled
            else "resume build to compute the exact deficit and perform quota-preserving backfill"
        ),
    }


def finalize_dataset(*, root: Path) -> dict[str, Any]:
    with run_lock(root):
        if (root / "readiness.json").is_file():
            return verify_ready_bundle(root)
        config_lock = read_json(root / "config.lock.json")
        profile = config_lock["config"]["dataset"]["profile"]
        final_split_id = profile_subject_id(profile, "final-split")
        final_split_subject = read_json(
            subject_path(
                root,
                ReviewScope.FINAL_SPLIT,
                final_split_id,
            )
        )
        split_decision = matching_decision(
            root,
            scope=ReviewScope.FINAL_SPLIT,
            subject_id=final_split_subject["subject_id"],
            subject_fingerprint=final_split_subject["subject_fingerprint"],
        )
        if split_decision is None:
            _write_run_state(root, "awaiting_split_review")
            return {
                "status": "awaiting_split_review",
                "reason_code": "human_review_stale",
            }
        if split_decision.decision is Decision.REJECT:
            _write_run_state(root, "pool_filling", reason_code="human_review_rejected")
            return {"status": "incomplete", "reason_code": "human_review_rejected"}
        if not (root / "split-manifest.json").is_file():
            freeze_split(root, final_split_subject["subject_fingerprint"])
        groups = split_task_roots(root)
        consumer_lock = read_json(root / "consumer-lock.json")
        tokenizer = load_locked_tokenizer(consumer_lock)
        mask_generator = preflight_loss_mask_generator(
            consumer_lock=consumer_lock,
            tokenizer=tokenizer,
        )

        def locked_mask_generator(_tokenizer: Any, _loss_mask_type: str) -> Any:
            return mask_generator

        rows: list[dict[str, Any]] = []
        token_records: list[dict[str, Any]] = []
        for task_root in groups[Split.TRAIN]:
            try:
                oracle = read_json(task_root / "receipts/oracle.json")
                row = render_row(
                    task_root=task_root,
                    config_lock=config_lock,
                    oracle_fingerprint=oracle["oracle_fingerprint"],
                )
                final_screen_rows(rows=[row])
                provisional = compute_token_record(
                    row,
                    consumer_lock=consumer_lock,
                    tokenizer=tokenizer,
                    mask_generator_factory=locked_mask_generator,
                )
                row = attach_token_record(row, provisional)
                record = compute_token_record(
                    row,
                    consumer_lock=consumer_lock,
                    tokenizer=tokenizer,
                    mask_generator_factory=locked_mask_generator,
                )
            except AiderSftError as exc:
                return _invalidate_frozen_split(
                    root=root,
                    task_id=task_root.name,
                    failure=exc,
                )
            rows.append(row)
            token_records.append(record)
        for split in (Split.VALIDATION, Split.TEST):
            for task_root in groups[split]:
                try:
                    task = load_canonical_task(task_root)
                    final_screen_rows(
                        rows=[
                            {
                                "messages": [
                                    {
                                        "role": "user",
                                        "content": render_prompt(task_root, task),
                                    }
                                ]
                            }
                        ]
                    )
                except AiderSftError as exc:
                    return _invalidate_frozen_split(
                        root=root,
                        task_id=task_root.name,
                        failure=exc,
                    )
        rows.sort(key=lambda row: row["task_id"])
        token_records.sort(key=lambda row: row["task_id"])
        write_jsonl(root / "sft/train.jsonl", rows)
        write_jsonl(root / "sft/token-records.jsonl", token_records)
        _eval_artifacts(root, groups)
        final_contamination = final_screen_rows(rows=rows)
        write_json(root / "reports/final-contamination.json", final_contamination)
        _release_documents(
            root=root,
            config_lock=config_lock,
            rows=rows,
            records=token_records,
        )
        _aggregate_ledgers(root)
        release_subject = _release_subject(root)
        release_decision = matching_decision(
            root,
            scope=ReviewScope.DATASET_RELEASE,
            subject_id=release_subject["subject_id"],
            subject_fingerprint=release_subject["subject_fingerprint"],
        )
        write_json(
            root / "private/review/dataset-release-subject.json",
            release_subject,
        )
        if release_decision is None:
            _write_run_state(
                root,
                "awaiting_release_review",
                subject_fingerprint=release_subject["subject_fingerprint"],
            )
            return {
                "status": "awaiting_release_review",
                "release_subject": release_subject["subject_fingerprint"],
                "next": "review-export, approve dataset_release, import, then finalize",
            }
        if release_decision.decision is Decision.REJECT:
            _write_run_state(root, "final_screened", reason_code="human_review_rejected")
            return {
                "status": "incomplete",
                "reason_code": "human_review_rejected",
                "next": "correct release presentation and obtain a new dataset_release approval",
            }
        materialize_review_evidence(root)
        readiness = create_manifest_and_readiness(
            root,
            dataset_release_subject_sha256=release_subject["subject_fingerprint"],
        )
        _write_run_state(root, "ready", dataset_id=readiness["dataset_id"])
        chmod_tree_readonly(root)
        return {
            "status": "ready",
            "dataset_id": readiness["dataset_id"],
            "counts": readiness["counts"],
        }


def verify_dataset(
    *,
    root: Path,
    rerun_oracles: bool = False,
    scratch_parent: Path | None = None,
) -> dict[str, Any]:
    return verify_ready_bundle(
        root,
        rerun_oracles=rerun_oracles,
        scratch_parent=scratch_parent,
    )


def export_dataset(
    *,
    root: Path,
    audience: str,
    output: Path,
) -> dict[str, Any]:
    if audience != "slime-sft":
        raise AiderSftError(
            "consumer_export_manifest_mismatch",
            "V1 permits only the internal slime-sft audience",
        )
    return export_slime_bundle(source_root=root, output_root=output)


def export_minimal_dataset(
    *,
    root: Path,
    output: Path,
    model_family: str,
    purpose: str,
    source_prefix: str,
) -> dict[str, Any]:
    return export_minimal_moonlight_rows(
        source_root=root,
        output_root=output,
        model_family=model_family,
        purpose=purpose,
        source_prefix=source_prefix,
    )


def verify_export(*, root: Path) -> dict[str, Any]:
    return verify_export_bundle(root)
