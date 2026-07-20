from __future__ import annotations

import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_spiral_matrix_aider_tasks as tasks


def test_rejection_owner_preserves_legacy_and_emits_no_candidates(tmp_path: Path) -> None:
    before = {task_id: tasks._tree_hash(tasks.LEGACY_OUT / task_id) for task_id in tasks.TASK_IDS}
    assert tasks.build(tmp_path) == ()
    after = {task_id: tasks._tree_hash(tasks.LEGACY_OUT / task_id) for task_id in tasks.TASK_IDS}
    assert after == before
    assert [path for path in tmp_path.iterdir() if path.is_dir() and path.name != ".state"] == []
    audit = json.loads((tmp_path / ".state/family-audit.json").read_text())
    assert audit["task_count"] == 20
    assert audit["candidate_task_count"] == 0
    assert audit["strongest_local_status"] == "rejected_benchmark_overlap"
    assert audit["dataset_handoff"] == "not_requested"


def test_every_pair_and_required_adversarial_control_is_rejected(tmp_path: Path) -> None:
    audit = tasks.verify_core(tmp_path, require_remedies=False)
    pairs = audit["pairwise_semantic_overlap"]
    assert len(pairs) == 20 * 19 // 2
    assert all(item["result"] == "duplicate_family" for item in pairs)
    assert all(set(item["dimensions"]) == set(tasks.DIVERSITY_DIMENSIONS) for item in pairs)
    assert audit["all_pairs_duplicate"] is True
    assert audit["hard_rule_result"] == "duplicate_family_rejection_reverified"
    assert audit["hard_rule_dimensions"] == list(tasks.DIVERSITY_DIMENSIONS)
    controls = audit["adversarial_clone_controls"]
    assert set(controls) == {
        "domain-identifier-renamed",
        "constants-or-policy-only",
        "opposite-end-selection",
    }
    assert all(item["result"] == "duplicate_family" for item in controls.values())
    assert all(item["mutation_executed"] is True for item in controls.values())
    assert all(item["clone_tree_hash"] != item["source_tree_hash"] for item in controls.values())
    assert audit["benchmark_screen"]["status"] == "reject"
    assert audit["benchmark_screen"]["reason_code"] == "benchmark_content_overlap"
    assert audit["benchmark_screen"]["holdout"] == "spiral-matrix"
    assert len(audit["benchmark_inventory"]) == 26
    assert len(audit["benchmark_comparisons"]) == 20 * 26
    assert all(
        item["result"] == "benchmark_content_overlap"
        for item in audit["benchmark_comparisons"]
        if item["holdout"] == "spiral-matrix"
    )


def test_production_screen_rejects_actual_mutated_clone_trees(tmp_path: Path) -> None:
    source = tasks.LEGACY_OUT / "spiral-museum-tour"
    for kind in (
        "domain-identifier-renamed",
        "constants-or-policy-only",
        "opposite-end-selection",
    ):
        clone = tmp_path / kind
        tasks._create_adversarial_clone(source, clone, kind)
        assert tasks._tree_hash(clone) != tasks._tree_hash(source)
        result = tasks._pair_result(source, clone)
        assert result["result"] == "duplicate_family"
        assert set(result["dimensions"]) == set(tasks.DIVERSITY_DIMENSIONS)


def test_all_legacy_roots_have_terminal_hash_bound_remedies() -> None:
    audit = tasks.verify_core(tasks.DEFAULT_OUT)
    assert set(audit["task_evidence"]) == set(tasks.TASK_IDS)
    remedy_root = tasks.DEFAULT_OUT / ".state/remedy"
    assert len(list(remedy_root.glob("*.json"))) == 20
    assert len(list(remedy_root.glob("*.md"))) == 20
    for task_id in tasks.TASK_IDS:
        record = json.loads((remedy_root / f"{task_id}.json").read_text())
        assert record["tree_hash_before"] == tasks._tree_hash(tasks.LEGACY_OUT / task_id)
        assert record["disposition"] == "reject"
        assert record["benchmark_screen"] == "reject"
        assert record["primary_core_objective"] == "achieved"
        assert record["status"] == "rejected"
        assert record["local_status"] == "rejected_benchmark_overlap"
        assert record["selected_prompt"] == tasks.PROMPT_PATH
        assert audit["task_evidence"][task_id]["prompt_boundary"]["status"] == "pass"
        assert audit["task_evidence"][task_id]["role_reference_mapping"] == "pass"


def test_role_and_output_failures_are_fail_closed(tmp_path: Path) -> None:
    root = tasks.LEGACY_OUT / tasks.TASK_IDS[0]
    config = json.loads((root / ".meta/config.json").read_text())
    assert tasks._role_failure(root, config["files"]) is None
    unsafe = json.loads(json.dumps(config["files"]))
    unsafe["solution"].append("CMakeLists.txt")
    assert tasks._role_failure(root, unsafe) == "unsafe_path"
    missing_reference = json.loads(json.dumps(config["files"]))
    missing_reference["example"].pop()
    assert tasks._role_failure(root, missing_reference) == "target_reference_mismatch"

    candidate = tmp_path / "attempted-retention"
    candidate.mkdir(parents=True)
    with pytest.raises(tasks.VerificationError, match="benchmark_content_overlap"):
        tasks.verify_core(tmp_path, require_remedies=False)


def test_legacy_root_is_immutable() -> None:
    with pytest.raises(tasks.VerificationError, match="legacy_root_immutable"):
        tasks.build(tasks.LEGACY_OUT, force=True)


def test_wrapper_targets_reverify_and_runs_planner_check() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_spiral_matrix_aider_tasks.sh")
    text = wrapper.read_text()
    assert wrapper.stat().st_mode & 0o111
    assert "aider-tasks-reverify/aider-text-grid-reshaping/spiral-matrix" in text
    assert "plan_spiral_matrix_remedies.py\" --check" in text
    assert "--verify-core" in text


def test_default_docker_audit_receipt_binds_immutable_legacy_when_present() -> None:
    receipt_path = tasks.DEFAULT_OUT / ".state/legacy-docker-audit.json"
    if not receipt_path.is_file():
        pytest.skip("operator Docker audit has not been run")
    receipt = json.loads(receipt_path.read_text())
    assert receipt["status"] in {"pass", "fail"}
    assert receipt["evidence_class"] == "historical_docker_audit"
    assert receipt["locked_oracle"] is False
    assert receipt["network"] == "none"
    assert receipt["image"] == tasks.SANITY_IMAGE
    assert set(receipt["tasks"]) == set(tasks.TASK_IDS)
    for task_id in tasks.TASK_IDS:
        item = receipt["tasks"][task_id]
        assert item["tree_hash"] == tasks._tree_hash(tasks.LEGACY_OUT / task_id)
        assert item["normal"] == item["asan_ubsan"] == 2
        assert item["normal_status"] in {"pass", "reference_tests_failed"}
        assert item["asan_ubsan_status"] in {"pass", "reference_tests_failed"}
        record = json.loads(
            (tasks.DEFAULT_OUT / ".state/remedy" / f"{task_id}.json").read_text()
        )
        expected = (
            "historical_docker_audit_pass"
            if item["normal_status"] == item["asan_ubsan_status"] == "pass"
            else "historical_docker_audit_failed"
        )
        assert record["oracle_evidence"] == expected
        assert record["normal_test_count"] == record["sanitizer_test_count"] == 2
