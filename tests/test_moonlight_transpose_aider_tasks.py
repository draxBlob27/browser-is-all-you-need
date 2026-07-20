from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft as sft
from w8_biayn.integrations import moonlight_transpose_aider_tasks as tasks
from w8_biayn.integrations.moonlight_transpose_cases import CASES


def test_materializes_twenty_distinct_reverify_roots(tmp_path: Path) -> None:
    roots = tasks.build(tmp_path)
    assert len(roots) == len(CASES) == 20
    assert {root.name for root in roots} == {case.task_id for case in CASES}
    assert len({case.function for case in CASES}) == 20
    assert len({case.profile for case in CASES}) == 20
    assert tasks.DEFAULT_OUT.parts[-2:] == (
        "aider-text-grid-reshaping",
        "transpose",
    )
    assert {case.legacy_id for case in CASES} == {
        path.name for path in tasks.LEGACY_OUT.iterdir() if path.is_dir()
    }
    assert sum(case.task_id == case.legacy_id for case in CASES) == 1
    for case in CASES:
        root = tmp_path / case.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"] == {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        }
        assert (root / ".meta/negative.cpp").is_file()
        assert "WILL_FAIL TRUE" in (root / "CMakeLists.txt").read_text()


def test_legacy_root_is_immutable() -> None:
    with pytest.raises(tasks.VerificationError, match="legacy_root_immutable"):
        tasks.build(tasks.LEGACY_OUT, force=True)


def test_prompt_roles_and_artifact_derived_family_screen(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    evidence = tasks.verify_core(tmp_path)
    assert set(evidence) == {case.task_id for case in CASES}
    screen = json.loads((tmp_path / ".state/family-screen.json").read_text())
    assert screen["normalizer"] == tasks.NORMALIZER
    assert len(screen["pairwise_semantic_overlap"]) == 20 * 19 // 2
    assert all(item["overlap"] < tasks.PAIR_THRESHOLD for item in screen["pairwise_semantic_overlap"])
    hard_rule = screen["hard_rule"]
    assert hard_rule["dimensions"] == list(tasks.HARD_RULE_DIMENSIONS)
    assert hard_rule["comparison_count"] == hard_rule["expected_comparison_count"] == 190
    assert hard_rule["thresholds"] == tasks.HARD_RULE_THRESHOLDS
    assert len(hard_rule["pairwise"]) == 190
    assert all(item["failure"] is None for item in hard_rule["pairwise"])
    assert all(item["failed_dimensions"] == [] for item in hard_rule["pairwise"])
    for item in hard_rule["pairwise"]:
        assert set(item["dimension_overlaps"]) == set(tasks.HARD_RULE_DIMENSIONS)
        assert all(
            item["dimension_overlaps"][dimension]
            < tasks.HARD_RULE_THRESHOLDS[dimension]
            for dimension in tasks.HARD_RULE_DIMENSIONS
        )
    assert len(screen["benchmark_inventory"]) == 26
    assert len(screen["benchmark_comparisons"]) == 20 * 26
    assert set(screen["adversarial_clone_results"]) == {
        "domain-identifier-renamed",
        "constants-or-policy-only",
        "opposite-end-selection",
    }
    archive_case = next(case for case in CASES if case.task_id == "transpose-call-center")
    assert tasks._adversarial_clone_results(
        tmp_path / archive_case.task_id, archive_case
    ) == screen[
        "adversarial_clone_results"
    ]
    assert all(
        item["failure"] == "duplicate_family"
        for item in screen["adversarial_clone_results"].values()
    )
    assert all(
        set(item["failed_dimensions"]) == set(tasks.HARD_RULE_DIMENSIONS)
        for item in screen["adversarial_clone_results"].values()
    )
    for case in CASES:
        root = tmp_path / case.task_id
        task = sft.load_task(root)
        response = sft.build_assistant_response(
            task, sft.load_example_files_from_config(root)
        )
        assert response.startswith(f"{case.task_id}.h\n```")
        assert f"{case.task_id}.cpp\n```" in response
        assert ".meta/" not in response
        assert "CMakeLists" not in response
        record = json.loads(
            (tmp_path / ".state/remedy" / f"{case.legacy_id}.json").read_text()
        )
        assert record["primary_core_objective"] == "achieved"
        assert record["local_status"] == "pending_execution"
        dimensions = record["semantic_evidence"]["hard_rule_dimensions"]
        assert set(dimensions) == set(tasks.HARD_RULE_DIMENSIONS)
        assert all(item["feature_count"] > 0 for item in dimensions.values())
        assert all(
            re.fullmatch(r"sha256:[0-9a-f]{64}", item["fingerprint"])
            for item in dimensions.values()
        )


def test_all_emitted_pairs_and_topic_specific_negatives_obey_hard_rule(
    tmp_path: Path,
) -> None:
    tasks.build(tmp_path)
    assert len({case.negative_description for case in CASES}) == 20
    for case in CASES:
        root = tmp_path / case.task_id
        reference = (root / ".meta/example.cpp").read_text()
        negative = (root / ".meta/negative.cpp").read_text()
        assert case.function in reference
        assert tasks._format_cpp_body(case.body).strip() in reference
        assert tasks._format_cpp_body(case.negative_new).strip() in negative
        assert tasks._format_cpp_body(case.negative_old).strip() not in negative
        assert negative != reference
        cmake = (root / "CMakeLists.txt").read_text()
        assert "add_executable(task_negative .meta/negative.cpp task_visible_test.cpp)" in cmake
        assert (
            "target_compile_options(task_negative PRIVATE -Wall -Wextra -Wpedantic -Werror)"
            in cmake
        )


def test_genuine_adversarial_clones_are_coherent_and_rejected(
    tmp_path: Path,
) -> None:
    tasks.build(tmp_path / "family")
    case = next(case for case in CASES if case.task_id == "transpose-call-center")
    root = tmp_path / "family" / case.task_id
    for variant in tasks.ADVERSARIAL_CONTROLS:
        clone, mutation = tasks._make_adversarial_clone(
            root, case, variant, tmp_path / "controls"
        )
        assert mutation["changed_files"]
        combined = "\n".join(
            (clone / relative).read_text()
            for relative in tasks._adversarial_relative_paths(clone)
        )
        if variant == "domain-identifier-renamed":
            assert case.function not in combined
            assert "transpose_ledger_records" in combined
        elif variant == "constants-or-policy-only":
            assert "long long weight=2" in combined
            assert "r.checksum!=107" in combined
            assert "r.checksum!=107" in combined
        else:
            assert "width-1U-c" in combined
            assert "{3,6}" in combined and "{1,4}" in combined
            assert "r.checksum!=70" in combined
        result = tasks._hard_rule_pair_result(root, clone, case, case)
        assert result["failure"] == "duplicate_family"
        assert set(result["failed_dimensions"]) == set(tasks.HARD_RULE_DIMENSIONS)


def test_hard_rule_root_count_is_fail_closed(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    shutil.rmtree(tmp_path / CASES[-1].task_id)
    with pytest.raises(tasks.VerificationError, match="generator_output_drift"):
        tasks.verify_core(tmp_path)


def test_role_and_prompt_failures_are_fail_closed(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    for case in CASES:
        root = tmp_path / case.task_id
        files = json.loads((root / ".meta/config.json").read_text())["files"]
        assert tasks._role_failure(root, files) is None
        unsafe = json.loads(json.dumps(files))
        unsafe["solution"].append("CMakeLists.txt")
        assert tasks._role_failure(root, unsafe) == "unsafe_path"
        missing = json.loads(json.dumps(files))
        missing["example"].pop()
        assert tasks._role_failure(root, missing) == "target_reference_mismatch"
        instructions = (root / ".docs/instructions.md").read_text()
        assert tasks._prompt_contract_failure(case, instructions) is None
        assert tasks._prompt_contract_failure(
            case,
            re.sub(
                re.escape(case.prompt_terms[0]),
                "omitted",
                instructions,
                flags=re.IGNORECASE,
            ),
        ) == "prompt_contract_incomplete"


def test_default_docker_sanity_receipt_binds_live_tree_when_present() -> None:
    receipt_path = tasks.DEFAULT_OUT / ".state/docker-sanity.json"
    if not receipt_path.is_file():
        pytest.skip("Docker sanity evidence is generated by the operator workflow")
    receipt = json.loads(receipt_path.read_text())
    assert receipt["status"] == "pass"
    assert receipt["evidence_class"] == "docker_sanity"
    assert receipt["locked_oracle"] is False
    assert receipt["network"] == "none"
    assert receipt["image"] == tasks.SANITY_IMAGE
    assert receipt["generator_revision"] == tasks._generator_revision()
    assert set(receipt["tasks"]) == {case.task_id for case in CASES}
    assert set(receipt["hard_rule_controls"]) == set(tasks.ADVERSARIAL_CONTROLS)
    assert all(
        item["normal"] == item["asan_ubsan"] == 3
        for item in receipt["hard_rule_controls"].values()
    )
    for case in CASES:
        item = receipt["tasks"][case.task_id]
        assert item["normal"] == item["asan_ubsan"] == 3
        assert item["tree_hash"] == tasks._tree_hash(tasks.DEFAULT_OUT / case.task_id)
        assert item["mounted_tree_hash"] == item["tree_hash"]
        assert item["negative_normal"] == "semantic_rejection exit_1"
        assert item["negative_asan_ubsan"] == "semantic_rejection exit_1"
        record = json.loads(
            (tasks.DEFAULT_OUT / ".state/remedy" / f"{case.legacy_id}.json").read_text()
        )
        assert record["local_status"] == "local_family_verified"
