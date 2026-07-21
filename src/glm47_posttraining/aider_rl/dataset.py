"""Build, verify, preflight, and summarize immutable Aider RL bundles."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Sequence

from .admission import (
    AdmissionError,
    load_reference_files,
    measure_token_evidence,
    reference_fingerprint,
    safe_copy_tree,
    tree_sha256,
    verify_measured_token_evidence,
    verify_prompt_boundary,
    verify_split_integrity,
    verify_task_tree,
    verify_token_evidence,
)
from .prompt import build_prompt, render_whole_edit
from .reward import compute_reward
from .curriculum import (
    CurriculumCatalog,
    resolve_task_rubrics,
    verify_admitted_task_curriculum,
)
from .schema import (
    PARSER_FINGERPRINT,
    REWARD_FINGERPRINT,
    AiderTask,
    AiderTaskDraft,
    EditableFile,
    FileIdentity,
    MutantFile,
    MutantSpec,
    OracleReceipt,
    TestSuiteIdentity,
    canonical_sha256,
    file_sha256,
)


DATASET_VERSION = "aider-cpp-rl-bundle-v2"
PUBLIC_DATA_SOURCE = "aider-clean-room-cpp-rl"
PUBLIC_METADATA_KEYS = {
    "data_source",
    "task_id",
    "family_id",
    "lineage_id",
    "capability_tags",
    "split",
    "task_path",
    "task_digest",
    "response_budget",
}


def admit_drafts(
    source: str | Path,
    output: str | Path,
    *,
    tokenizer: object,
    grader_lock: str | Path,
    curriculum_catalog: str | Path,
    force: bool = False,
) -> list[Path]:
    """Materialize human-authored task drafts into verified immutable task roots."""

    source_root = Path(source).resolve(strict=True)
    output_root = Path(output)
    if output_root.exists() and any(output_root.iterdir()):
        if not force:
            raise FileExistsError(f"{output_root} exists and is not empty")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    draft_rows: list[tuple[Path, Path, AiderTaskDraft]] = []
    for path in sorted(source_root.rglob("task.draft.json")):
        tree = path.parent / "tree"
        if not tree.is_dir():
            raise AdmissionError(f"draft has no sibling tree: {path}")
        draft_rows.append((path, tree, AiderTaskDraft.model_validate_json(path.read_text())))
    if not draft_rows:
        raise AdmissionError(f"no task.draft.json/tree pairs under {source_root}")
    _verify_draft_split_integrity(draft for _path, _tree, draft in draft_rows)
    split_fingerprint = canonical_sha256(
        sorted(
            (draft.task_id, draft.family_id, draft.lineage_id, draft.split)
            for _path, _tree, draft in draft_rows
        )
    )
    lock = json.loads(Path(grader_lock).read_text(encoding="utf-8"))
    catalog = CurriculumCatalog.read_json(curriculum_catalog)
    _write_json(output_root / "curriculum.catalog.json", catalog.model_dump(mode="json"))
    required_lock = {"image", "grader_image_digest", "compiler_fingerprint"}
    if set(lock) != required_lock:
        raise AdmissionError("grader lock has an unsupported shape")
    from .sandbox import grader_compiler_fingerprint, grader_image_id

    actual_image = grader_image_id(str(lock["image"]))
    if actual_image != lock["grader_image_digest"]:
        raise AdmissionError("installed grader image differs from admission lock")
    if grader_compiler_fingerprint(actual_image) != lock["compiler_fingerprint"]:
        raise AdmissionError("installed compiler differs from admission lock")

    written: list[Path] = []
    for _draft_path, source_tree, draft in draft_rows:
        destination = output_root / draft.task_id
        destination.mkdir(parents=True, exist_ok=False)
        tree = safe_copy_tree(source_tree, destination / "tree")
        task = _materialize_draft(
            draft,
            tree,
            tokenizer=tokenizer,
            split_fingerprint=split_fingerprint,
            grader_lock=lock,
            catalog=catalog,
        )
        references = load_reference_files(task, tree)
        breakdown = compute_reward(task, render_whole_edit(task, references), task_tree=tree)
        if breakdown.reward != 1.0 or breakdown.reason != "correct" or not breakdown.harness:
            raise AdmissionError(f"reference oracle failed during admission: {draft.task_id}")
        mutation_receipts = _validate_mutants(task, tree)
        _write_json(destination / "mutation.receipt.json", mutation_receipts)
        task_path = destination / "task.json"
        task.write_json(task_path)
        written.append(task_path)
    return written


def _materialize_draft(
    draft: AiderTaskDraft,
    tree: Path,
    *,
    tokenizer: object,
    split_fingerprint: str,
    grader_lock: dict[str, str],
    catalog: CurriculumCatalog,
) -> AiderTask:
    editable_files = [
        EditableFile(
            path=item.path,
            reference_path=item.reference_path,
            starter_sha256=file_sha256(tree / item.path),
            max_bytes=item.max_bytes,
        )
        for item in draft.editable_files
    ]
    visible = _materialize_test_suite(tree, draft.visible_tests.expected_count, draft.visible_tests.files)
    hidden = _materialize_test_suite(tree, draft.hidden_tests.expected_count, draft.hidden_tests.files)
    rubrics = resolve_task_rubrics(draft, catalog)
    mutants = [
        MutantSpec(
            mutant_id=mutant.mutant_id,
            files=[
                MutantFile(
                    target_path=item.target_path,
                    source_path=item.source_path,
                    sha256=file_sha256(tree / item.source_path),
                )
                for item in mutant.files
            ],
            expected_fail_rubric_ids=mutant.expected_fail_rubric_ids,
            expected_pass_rubric_ids=mutant.expected_pass_rubric_ids,
        )
        for mutant in draft.mutants
    ]
    allowed_paths = tuple(item.path for item in editable_files)
    prompt_proxy = SimpleNamespace(
        introduction=draft.introduction,
        instructions=draft.instructions,
        allowed_paths=allowed_paths,
    )
    starters = {item.path: (tree / item.path).read_text(encoding="utf-8") for item in editable_files}
    reference_files = {
        item.path: (tree / item.reference_path).read_text(encoding="utf-8")
        for item in editable_files
    }
    prompt = build_prompt(prompt_proxy, starters)
    answer = "\n\n".join(
        f"{path}\n```cpp\n{reference_files[path].rstrip()}\n```" for path in allowed_paths
    ) + "\n"
    token_evidence = measure_token_evidence(
        prompt,
        answer,
        tokenizer,
        response_budget_margin=draft.response_budget_margin,
    )
    reference_identity = canonical_sha256(
        [(item.path, file_sha256(tree / item.reference_path)) for item in editable_files]
    )
    oracle = OracleReceipt(
        reference_fingerprint=reference_identity,
        grader_image_digest=grader_lock["grader_image_digest"],
        compiler_fingerprint=grader_lock["compiler_fingerprint"],
        normal_visible_count=visible.expected_count,
        normal_hidden_count=hidden.expected_count,
        sanitizer_visible_count=visible.expected_count,
        sanitizer_hidden_count=hidden.expected_count,
    )
    return AiderTask(
        task_id=draft.task_id,
        family_id=draft.family_id,
        lineage_id=draft.lineage_id,
        split=draft.split,
        capability_tags=draft.capability_tags,
        curriculum_fingerprint=catalog.fingerprint,
        rubrics=rubrics,
        mutants=mutants,
        introduction=draft.introduction,
        instructions=draft.instructions,
        editable_files=editable_files,
        build=draft.build,
        visible_tests=visible,
        hidden_tests=hidden,
        tree_digest=tree_sha256(tree),
        prompt_fingerprint=token_evidence.prompt_hash,
        parser_fingerprint=PARSER_FINGERPRINT,
        reward_fingerprint=REWARD_FINGERPRINT,
        grader_image=grader_lock["image"],
        grader_image_digest=grader_lock["grader_image_digest"],
        compiler_fingerprint=grader_lock["compiler_fingerprint"],
        provenance_fingerprint=draft.provenance_receipt.fingerprint,
        contamination_fingerprint=draft.contamination_receipt.fingerprint,
        provenance_receipt=draft.provenance_receipt,
        contamination_receipt=draft.contamination_receipt,
        split_fingerprint=split_fingerprint,
        token_evidence=token_evidence,
        oracle_receipt=oracle,
    ).with_computed_digest()


def _validate_mutants(task: AiderTask, tree: Path) -> list[dict[str, Any]]:
    """Prove model-like faulty implementations isolate their declared rubrics."""

    receipts: list[dict[str, Any]] = []
    for mutant in task.mutants:
        if {item.target_path for item in mutant.files} != set(task.allowed_paths):
            raise AdmissionError(
                f"mutant must replace every editable file exactly once: {mutant.mutant_id}"
            )
        files: dict[str, str] = {}
        by_target = {item.target_path: item for item in mutant.files}
        for target in task.allowed_paths:
            identity = by_target[target]
            source = tree / identity.source_path
            if not source.is_file() or source.is_symlink() or file_sha256(source) != identity.sha256:
                raise AdmissionError(f"mutant source identity is stale: {mutant.mutant_id}")
            files[target] = source.read_text(encoding="utf-8")
        breakdown = compute_reward(
            task,
            render_whole_edit(task, files),
            task_tree=tree,
        )
        if not breakdown.harness or breakdown.reason != "tests_failed":
            raise AdmissionError(
                f"mutant must compile and fail diagnostic tests: {mutant.mutant_id}"
            )
        scores = {item.rubric_id: item.score for item in breakdown.rubric_scores}
        failed = [rubric_id for rubric_id in mutant.expected_fail_rubric_ids if scores[rubric_id] >= 1.0]
        regressed = [rubric_id for rubric_id in mutant.expected_pass_rubric_ids if scores[rubric_id] < 1.0]
        if failed:
            raise AdmissionError(
                f"mutant escaped its targeted rubrics {failed}: {mutant.mutant_id}"
            )
        if regressed:
            raise AdmissionError(
                f"mutant is not diagnostic; unrelated rubrics failed {regressed}: {mutant.mutant_id}"
            )
        receipts.append(
            {
                "receipt_version": "aider-mutant-admission-v1",
                "task_id": task.task_id,
                "task_digest": task.task_digest,
                "mutant_id": mutant.mutant_id,
                "expected_fail_rubric_ids": mutant.expected_fail_rubric_ids,
                "expected_pass_rubric_ids": mutant.expected_pass_rubric_ids,
                "rubric_scores": scores,
                "reward": breakdown.reward,
                "status": "passed",
            }
        )
    return receipts


def _materialize_test_suite(tree: Path, expected_count: int, files: list[str]) -> TestSuiteIdentity:
    identities = [FileIdentity(path=path, sha256=file_sha256(tree / path)) for path in files]
    return TestSuiteIdentity(
        expected_count=expected_count,
        files=identities,
        fingerprint=canonical_sha256([(item.path, item.sha256) for item in identities]),
    )


def _verify_draft_split_integrity(drafts: Iterable[AiderTaskDraft]) -> None:
    family_splits: dict[str, str] = {}
    lineage_splits: dict[str, str] = {}
    task_ids: set[str] = set()
    for draft in drafts:
        if draft.task_id in task_ids:
            raise AdmissionError(f"duplicate draft task ID: {draft.task_id}")
        task_ids.add(draft.task_id)
        for key, mapping in ((draft.family_id, family_splits), (draft.lineage_id, lineage_splits)):
            previous = mapping.setdefault(key, draft.split)
            if previous != draft.split:
                raise AdmissionError(f"draft family or lineage crosses splits: {key}")


def build_bundle(
    source: str | Path,
    output: str | Path,
    *,
    tokenizer: object,
    force: bool = False,
) -> dict[str, Path]:
    """Project already-admitted private task roots into Miles and eval JSONL."""

    source_root = Path(source).resolve(strict=True)
    source_catalog_path = source_root / "curriculum.catalog.json"
    if not source_catalog_path.is_file():
        raise AdmissionError("admitted root has no curriculum.catalog.json")
    source_catalog = CurriculumCatalog.read_json(source_catalog_path)
    output_root = Path(output)
    if output_root.exists() and any(output_root.iterdir()):
        if not force:
            raise FileExistsError(f"{output_root} exists and is not empty")
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    loaded = load_admitted_tasks(source_root, tokenizer=tokenizer)
    if not loaded:
        raise AdmissionError(f"no admitted task.json/tree pairs under {source_root}")
    for _record, _tree, task in loaded:
        verify_admitted_task_curriculum(task, source_catalog)
    _write_json(
        output_root / "curriculum.catalog.json", source_catalog.model_dump(mode="json")
    )
    verify_split_integrity(task for _record, _tree, task in loaded)
    split_identity = canonical_sha256(
        sorted(
            (task.task_id, task.family_id, task.lineage_id, task.split)
            for _record, _tree, task in loaded
        )
    )
    if any(task.split_fingerprint != split_identity for _record, _tree, task in loaded):
        raise AdmissionError("task split fingerprint does not match the complete family/lineage plan")
    curriculum_fingerprints = {task.curriculum_fingerprint for _record, _tree, task in loaded}
    if len(curriculum_fingerprints) != 1:
        raise AdmissionError("bundle tasks were admitted against different curriculum catalogs")
    present_splits = {task.split for _record, _tree, task in loaded}
    required_splits = {"train", "anchor", "validation", "internal_test"}
    if missing_splits := required_splits - present_splits:
        raise AdmissionError(f"bundle is missing required split roles: {sorted(missing_splits)}")

    public_rows: dict[str, list[dict[str, Any]]] = {
        "train": [],
        "anchor": [],
        "validation": [],
        "internal_test": [],
    }
    task_manifest: list[dict[str, Any]] = []
    admission_records: list[dict[str, Any]] = []
    oracle_records: list[dict[str, Any]] = []
    mutation_records: list[dict[str, Any]] = []

    for _source_record, source_tree, task in loaded:
        destination = output_root / "tasks" / task.task_id
        destination.mkdir(parents=True, exist_ok=False)
        safe_copy_tree(source_tree, destination / "tree")
        task_path = destination / "task.json"
        task.write_json(task_path)
        copied = AiderTask.read_json(task_path)
        prompt = verify_prompt_boundary(copied, destination / "tree")
        references = load_reference_files(copied, destination / "tree")
        verify_token_evidence(copied, prompt, references)
        verify_measured_token_evidence(copied, prompt, references, tokenizer)
        if reference_fingerprint(copied, destination / "tree") != copied.oracle_receipt.reference_fingerprint:
            raise AdmissionError("private reference fingerprint differs from oracle receipt")
        relative_task = task_path.relative_to(output_root).as_posix()
        public_rows[copied.split].append(_public_row(copied, prompt, relative_task))
        task_manifest.append(
            {
                "task_id": copied.task_id,
                "task_path": relative_task,
                "task_digest": copied.task_digest,
                "tree_digest": copied.tree_digest,
                "family_id": copied.family_id,
                "lineage_id": copied.lineage_id,
                "split": copied.split,
            }
        )
        admission_records.append(
            {
                "task_id": copied.task_id,
                "admitted": True,
                "prompt_fingerprint": copied.prompt_fingerprint,
                "parser_fingerprint": copied.parser_fingerprint,
                "reward_fingerprint": copied.reward_fingerprint,
                "token_evidence": copied.token_evidence.model_dump(mode="json"),
                "provenance_fingerprint": copied.provenance_fingerprint,
                "contamination_fingerprint": copied.contamination_fingerprint,
                "provenance_receipt": copied.provenance_receipt.model_dump(mode="json"),
                "contamination_receipt": copied.contamination_receipt.model_dump(mode="json"),
            }
        )
        oracle_records.append(
            {"task_id": copied.task_id, **copied.oracle_receipt.model_dump(mode="json")}
        )
        mutation_path = _source_record.parent / "mutation.receipt.json"
        if not mutation_path.is_file():
            raise AdmissionError(f"task has no mutant admission receipt: {copied.task_id}")
        receipts = json.loads(mutation_path.read_text(encoding="utf-8"))
        _verify_mutation_receipts(copied, receipts)
        mutation_records.extend(receipts)

    paths = {
        "manifest": output_root / "manifest.json",
        "task_manifest": output_root / "task-manifest.jsonl",
        "admission_records": output_root / "admission.records.jsonl",
        "oracle_records": output_root / "oracle.records.jsonl",
        "mutation_records": output_root / "mutation.records.jsonl",
        "curriculum_catalog": output_root / "curriculum.catalog.json",
        "grpo_train": output_root / "grpo" / "train.jsonl",
        "eval_anchor": output_root / "eval" / "anchor.jsonl",
        "eval_validation": output_root / "eval" / "validation.jsonl",
        "eval_internal_test": output_root / "eval" / "internal-test.jsonl",
    }
    _write_jsonl(paths["task_manifest"], task_manifest)
    _write_jsonl(paths["admission_records"], admission_records)
    _write_jsonl(paths["oracle_records"], oracle_records)
    _write_jsonl(paths["mutation_records"], mutation_records)
    _write_jsonl(paths["grpo_train"], public_rows["train"])
    _write_jsonl(paths["eval_anchor"], public_rows["anchor"])
    _write_jsonl(paths["eval_validation"], public_rows["validation"])
    _write_jsonl(paths["eval_internal_test"], public_rows["internal_test"])
    manifest = _manifest(output_root, loaded, paths)
    _write_json(paths["manifest"], manifest)
    verify_bundle(output_root, tokenizer=tokenizer)
    return paths


def load_admitted_tasks(
    root: str | Path, *, tokenizer: object
) -> list[tuple[Path, Path, AiderTask]]:
    loaded: list[tuple[Path, Path, AiderTask]] = []
    for record in sorted(Path(root).rglob("task.json")):
        tree = record.parent / "tree"
        if not tree.is_dir():
            continue
        task = AiderTask.read_json(record)
        verify_task_tree(task, tree)
        verify_prompt_boundary(task, tree)
        prompt = verify_prompt_boundary(task, tree)
        references = load_reference_files(task, tree)
        verify_measured_token_evidence(task, prompt, references, tokenizer)
        if reference_fingerprint(task, tree) != task.oracle_receipt.reference_fingerprint:
            raise AdmissionError("private reference fingerprint differs from oracle receipt")
        loaded.append((record, tree, task))
    return loaded


def verify_bundle(root: str | Path, *, tokenizer: object) -> dict[str, Any]:
    """Recompute bundle identities and prove public rows contain only safe metadata."""

    bundle = Path(root).resolve(strict=True)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("kind") != DATASET_VERSION:
        raise AdmissionError("unsupported Aider RL bundle version")
    catalog = CurriculumCatalog.read_json(bundle / "curriculum.catalog.json")
    if manifest.get("curriculum_fingerprint") != catalog.fingerprint:
        raise AdmissionError("bundle catalog differs from manifest curriculum fingerprint")
    task_rows = _read_jsonl(bundle / "task-manifest.jsonl")
    tasks: list[AiderTask] = []
    for row in task_rows:
        task_path = _resolve_bundle_path(bundle, row["task_path"])
        task = AiderTask.read_json(task_path)
        verify_admitted_task_curriculum(task, catalog)
        if task.task_id != row["task_id"] or task.task_digest != row["task_digest"]:
            raise AdmissionError("task manifest identity mismatch")
        verify_task_tree(task, task_path.parent / "tree")
        prompt = verify_prompt_boundary(task, task_path.parent / "tree")
        references = load_reference_files(task, task_path.parent / "tree")
        verify_measured_token_evidence(task, prompt, references, tokenizer)
        if reference_fingerprint(task, task_path.parent / "tree") != task.oracle_receipt.reference_fingerprint:
            raise AdmissionError("private reference fingerprint differs from oracle receipt")
        tasks.append(task)
    verify_split_integrity(tasks)
    curriculum_fingerprints = {task.curriculum_fingerprint for task in tasks}
    if len(curriculum_fingerprints) != 1:
        raise AdmissionError("bundle tasks use different curriculum catalogs")
    if manifest.get("curriculum_fingerprint") not in curriculum_fingerprints:
        raise AdmissionError("bundle curriculum fingerprint is stale or mismatched")
    mutation_rows = _read_jsonl(bundle / "mutation.records.jsonl")
    rows_by_task: dict[str, list[dict[str, Any]]] = {}
    for row in mutation_rows:
        rows_by_task.setdefault(str(row.get("task_id")), []).append(row)
    if set(rows_by_task) != {task.task_id for task in tasks}:
        raise AdmissionError("bundle mutant admission task set is stale or incomplete")
    for task in tasks:
        _verify_mutation_receipts(task, rows_by_task[task.task_id])
    expected_counts = Counter(task.split for task in tasks)
    if manifest.get("counts") != dict(sorted(expected_counts.items())):
        raise AdmissionError("bundle split counts do not match manifest")
    split_identity = canonical_sha256(
        sorted((task.task_id, task.family_id, task.lineage_id, task.split) for task in tasks)
    )
    if manifest.get("split_fingerprint") != split_identity or any(
        task.split_fingerprint != split_identity for task in tasks
    ):
        raise AdmissionError("bundle split fingerprint is stale or mismatched")

    split_files = {
        "train": "grpo/train.jsonl",
        "anchor": "eval/anchor.jsonl",
        "validation": "eval/validation.jsonl",
        "internal_test": "eval/internal-test.jsonl",
    }
    public_task_ids: list[str] = []
    for expected_split, relative in split_files.items():
        for row in _read_jsonl(bundle / relative):
            metadata = row.get("metadata")
            if not isinstance(metadata, dict) or set(metadata) != PUBLIC_METADATA_KEYS:
                raise AdmissionError(f"unsafe or incomplete public metadata in {relative}")
            if set(row) != {"prompt", "label", "task_id", "split", "metadata"}:
                raise AdmissionError(f"private field present in public row: {relative}")
            task_path = _resolve_bundle_path(bundle, metadata["task_path"])
            task = AiderTask.read_json(task_path)
            prompt = verify_prompt_boundary(task, task_path.parent / "tree")
            expected = _public_row(task, prompt, metadata["task_path"])
            if row != expected:
                raise AdmissionError("public row is stale relative to immutable task")
            if task.split != expected_split:
                raise AdmissionError(f"task appears in the wrong public split: {task.task_id}")
            public_task_ids.append(task.task_id)
    if sorted(public_task_ids) != sorted(task.task_id for task in tasks):
        raise AdmissionError("public rows do not contain every task exactly once")

    for relative, expected in manifest.get("file_sha256", {}).items():
        path = _resolve_bundle_path(bundle, relative)
        if file_sha256(path) != expected:
            raise AdmissionError(f"bundle file digest mismatch: {relative}")
    return manifest


def oracle_bundle(root: str | Path, *, tokenizer: object) -> list[dict[str, Any]]:
    """Regrade every private reference with the exact Docker-only candidate path."""

    bundle = Path(root).resolve(strict=True)
    verify_bundle(bundle, tokenizer=tokenizer)
    results: list[dict[str, Any]] = []
    for row in _read_jsonl(bundle / "task-manifest.jsonl"):
        task_path = _resolve_bundle_path(bundle, row["task_path"])
        task = AiderTask.read_json(task_path)
        references = load_reference_files(task, task_path.parent / "tree")
        breakdown = compute_reward(
            task,
            render_whole_edit(task, references),
            task_tree=task_path.parent / "tree",
        )
        if breakdown.reason != "correct" or breakdown.reward != 1.0:
            raise AdmissionError(f"oracle preflight failed for {task.task_id}: {breakdown.reason}")
        results.append(
            {
                "task_id": task.task_id,
                "task_digest": task.task_digest,
                "reward": breakdown.reward,
                "reason": breakdown.reason,
                "normal_visible": breakdown.harness.normal_visible.discovered,
                "normal_hidden": breakdown.harness.normal_hidden.discovered,
                "sanitizer_visible": breakdown.harness.sanitizer_visible.discovered,
                "sanitizer_hidden": breakdown.harness.sanitizer_hidden.discovered,
            }
        )
    return results


def summarize_bundle(root: str | Path, *, tokenizer: object) -> dict[str, Any]:
    bundle = Path(root).resolve(strict=True)
    verify_bundle(bundle, tokenizer=tokenizer)
    tasks = [
        AiderTask.read_json(_resolve_bundle_path(bundle, row["task_path"]))
        for row in _read_jsonl(bundle / "task-manifest.jsonl")
    ]
    capabilities = Counter(tag for task in tasks for tag in task.capability_tags)
    rubrics = Counter(rubric.rubric_id for task in tasks for rubric in task.rubrics)
    failure_modes = Counter(
        failure_id
        for task in tasks
        for rubric in task.rubrics
        for failure_id in rubric.failure_mode_ids
    )
    response_budgets = [task.token_evidence.response_budget for task in tasks]
    return {
        "task_count": len(tasks),
        "split_counts": dict(sorted(Counter(task.split for task in tasks).items())),
        "family_count": len({task.family_id for task in tasks}),
        "lineage_count": len({task.lineage_id for task in tasks}),
        "capability_counts": dict(sorted(capabilities.items())),
        "rubric_counts": dict(sorted(rubrics.items())),
        "failure_mode_counts": dict(sorted(failure_modes.items())),
        "mutant_count": sum(len(task.mutants) for task in tasks),
        "curriculum_fingerprint": tasks[0].curriculum_fingerprint,
        "max_response_budget": max(response_budgets),
        "min_response_budget": min(response_budgets),
        "max_prompt_tokens": max(task.token_evidence.prompt_tokens for task in tasks),
        "max_total_tokens": max(task.token_evidence.total_tokens for task in tasks),
    }


def readiness_bundle(root: str | Path, *, tokenizer: object) -> dict[str, Any]:
    """Run the complete pre-GPU bundle and reference-oracle readiness gate."""

    manifest = verify_bundle(root, tokenizer=tokenizer)
    oracle_results = oracle_bundle(root, tokenizer=tokenizer)
    summary = summarize_bundle(root, tokenizer=tokenizer)
    return {
        "status": "ready",
        "task_count": manifest["task_count"],
        "oracle_task_count": len(oracle_results),
        "split_counts": summary["split_counts"],
        "max_prompt_tokens": summary["max_prompt_tokens"],
        "max_response_budget": summary["max_response_budget"],
        "max_total_tokens": summary["max_total_tokens"],
        "rubric_counts": summary["rubric_counts"],
        "mutant_count": summary["mutant_count"],
        "curriculum_fingerprint": summary["curriculum_fingerprint"],
    }


def _public_row(task: AiderTask, prompt: str, task_path: str) -> dict[str, Any]:
    metadata = {
        "data_source": PUBLIC_DATA_SOURCE,
        "task_id": task.task_id,
        "family_id": task.family_id,
        "lineage_id": task.lineage_id,
        "capability_tags": task.capability_tags,
        "split": task.split,
        "task_path": task_path,
        "task_digest": task.task_digest,
        "response_budget": task.token_evidence.response_budget,
    }
    return {
        "prompt": prompt,
        "label": task.task_id,
        "task_id": task.task_id,
        "split": task.split,
        "metadata": metadata,
    }


def _verify_mutation_receipts(task: AiderTask, value: object) -> None:
    if not isinstance(value, list) or len(value) != len(task.mutants):
        raise AdmissionError(f"task mutant admission receipt is incomplete: {task.task_id}")
    rows = {str(row.get("mutant_id")): row for row in value if isinstance(row, dict)}
    if len(rows) != len(value) or set(rows) != {item.mutant_id for item in task.mutants}:
        raise AdmissionError(f"task mutant admission identities differ: {task.task_id}")
    rubric_ids = {item.rubric_id for item in task.rubrics}
    for mutant in task.mutants:
        row = rows[mutant.mutant_id]
        if (
            row.get("receipt_version") != "aider-mutant-admission-v1"
            or row.get("status") != "passed"
            or row.get("task_id") != task.task_id
            or row.get("task_digest") != task.task_digest
            or row.get("expected_fail_rubric_ids") != mutant.expected_fail_rubric_ids
            or row.get("expected_pass_rubric_ids") != mutant.expected_pass_rubric_ids
        ):
            raise AdmissionError(f"task mutant admission receipt is stale: {mutant.mutant_id}")
        scores = row.get("rubric_scores")
        if not isinstance(scores, dict) or set(scores) != rubric_ids:
            raise AdmissionError(f"task mutant rubric scores are incomplete: {mutant.mutant_id}")
        if any(not 0.0 <= float(score) <= 1.0 for score in scores.values()):
            raise AdmissionError(f"task mutant rubric score is out of range: {mutant.mutant_id}")
        if any(float(scores[item]) >= 1.0 for item in mutant.expected_fail_rubric_ids):
            raise AdmissionError(f"task mutant targeted rubric passed: {mutant.mutant_id}")
        if any(float(scores[item]) < 1.0 for item in mutant.expected_pass_rubric_ids):
            raise AdmissionError(f"task mutant unrelated rubric failed: {mutant.mutant_id}")
def _manifest(
    output: Path,
    loaded: list[tuple[Path, Path, AiderTask]],
    paths: dict[str, Path],
) -> dict[str, Any]:
    tasks = [task for _record, _tree, task in loaded]
    counts = dict(sorted(Counter(task.split for task in tasks).items()))
    split_identity = canonical_sha256(
        sorted((task.task_id, task.family_id, task.lineage_id, task.split) for task in tasks)
    )
    file_paths = {
        key: path.relative_to(output).as_posix() for key, path in paths.items() if key != "manifest"
    }
    return {
        "kind": DATASET_VERSION,
        "schema_version": 1,
        "data_source": PUBLIC_DATA_SOURCE,
        "counts": counts,
        "task_count": len(tasks),
        "split_fingerprint": split_identity,
        "curriculum_fingerprint": tasks[0].curriculum_fingerprint,
        "max_response_budget": max(task.token_evidence.response_budget for task in tasks),
        "max_prompt_tokens": max(task.token_evidence.prompt_tokens for task in tasks),
        "max_total_tokens": max(task.token_evidence.total_tokens for task in tasks),
        "files": file_paths,
        "file_sha256": {relative: file_sha256(output / relative) for relative in file_paths.values()},
    }


def _resolve_bundle_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute():
        raise AdmissionError("absolute paths are forbidden in bundle metadata")
    candidate = (root / path).resolve(strict=True)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise AdmissionError("bundle path escapes immutable root") from exc
    return candidate


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--source", required=True)
    build.add_argument("--out", required=True)
    build.add_argument("--tokenizer", required=True)
    build.add_argument("--force", action="store_true")
    verify = subparsers.add_parser("verify")
    verify.add_argument("--root", required=True)
    verify.add_argument("--tokenizer", required=True)
    oracle = subparsers.add_parser("oracle")
    oracle.add_argument("--root", required=True)
    oracle.add_argument("--tokenizer", required=True)
    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("--root", required=True)
    summarize.add_argument("--tokenizer", required=True)
    ready = subparsers.add_parser("ready")
    ready.add_argument("--root", required=True)
    ready.add_argument("--tokenizer", required=True)
    subparsers.add_parser("schema")
    subparsers.add_parser("draft-schema")
    admit = subparsers.add_parser("admit")
    admit.add_argument("--source", required=True)
    admit.add_argument("--out", required=True)
    admit.add_argument("--tokenizer", required=True)
    admit.add_argument("--grader-lock", required=True)
    admit.add_argument("--curriculum", required=True)
    admit.add_argument("--force", action="store_true")
    grader = subparsers.add_parser("grader")
    grader.add_argument("--image", required=True)
    grader.add_argument("--lock")
    return parser


def load_tokenizer(path: str) -> object:
    try:
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise AdmissionError("transformers is required for tokenizer admission checks") from exc
    return AutoTokenizer.from_pretrained(path, trust_remote_code=True, use_fast=True)


def main(argv: Sequence[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    if args.command == "schema":
        value: object = AiderTask.model_json_schema()
    elif args.command == "draft-schema":
        value = AiderTaskDraft.model_json_schema()
    elif args.command == "grader":
        from .sandbox import grader_compiler_fingerprint, grader_image_id

        image_digest = grader_image_id(args.image)
        value = {
            "image": args.image,
            "grader_image_digest": image_digest,
            "compiler_fingerprint": grader_compiler_fingerprint(image_digest),
        }
        if args.lock:
            expected = json.loads(Path(args.lock).read_text(encoding="utf-8"))
            if value != expected:
                raise AdmissionError("grader image/compiler identity differs from lock file")
    else:
        tokenizer = load_tokenizer(args.tokenizer)
    if args.command == "build":
        value = {
            key: str(path)
            for key, path in build_bundle(
                args.source, args.out, tokenizer=tokenizer, force=args.force
            ).items()
        }
    elif args.command == "admit":
        value = {
            "tasks": [
                str(path)
                for path in admit_drafts(
                    args.source,
                    args.out,
                    tokenizer=tokenizer,
                    grader_lock=args.grader_lock,
                    curriculum_catalog=args.curriculum,
                    force=args.force,
                )
            ]
        }
    elif args.command == "verify":
        value = verify_bundle(args.root, tokenizer=tokenizer)
    elif args.command == "oracle":
        value = oracle_bundle(args.root, tokenizer=tokenizer)
    elif args.command == "summarize":
        value = summarize_bundle(args.root, tokenizer=tokenizer)
    elif args.command == "ready":
        value = readiness_bundle(args.root, tokenizer=tokenizer)
    print(json.dumps(value, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
