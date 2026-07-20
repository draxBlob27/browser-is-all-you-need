from __future__ import annotations

import dataclasses
import inspect
import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_grid_ownership_mapping_aider_tasks as grid


def test_materializes_twenty_algorithmically_distinct_replacements(tmp_path: Path) -> None:
    roots = grid.build(tmp_path)
    assert len(roots) == 20
    assert len({case.profile for case in grid.CASES}) == 20
    assert len({case.public_api for case in grid.CASES}) == 20
    assert {root.name for root in roots} == {case.task_id for case in grid.CASES}
    assert all(case.task_id != case.legacy_id for case in grid.CASES)
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["family_id"] == grid.FAMILY_ID
        assert provenance["legacy_task_id"].startswith("ownership-")
        assert provenance["semantic_profile"]
        assert (root / ".meta/task_hidden_test.cpp").is_file()


def test_core_verifier_checks_prompt_roles_all_pairs_and_holdouts(tmp_path: Path) -> None:
    grid.build(tmp_path)
    grid.verify_core(tmp_path)
    manifest = json.loads((tmp_path / ".state/materialization-manifest.json").read_text())
    assert manifest["task_count"] == 20
    assert len({row["semantic_signature"] for row in manifest["tasks"]}) == 20
    assert manifest["screen"]["prompt_boundary"] == "pass"
    assert manifest["screen"]["reference_mapping"] == "pass"
    assert manifest["screen"]["duplicate_family"] == "pass"
    assert manifest["screen"]["artifact_family"]["pair_count"] == 190
    hard_rule = manifest["screen"]["hard_rule"]
    assert hard_rule["pair_count"] == 190
    assert hard_rule["expected_pair_count"] == 190
    assert len(hard_rule["pairs"]) == 190
    assert hard_rule["status"] == "pending_execution"
    for pair in hard_rule["pairs"]:
        assert pair["mechanism_marker_distinct"]
        assert all(
            pair[f"{dimension}_distinct"]
            for dimension in (
                "public_api",
                "behavior_contract",
                "reference_control_flow",
                "visible_oracle",
                "private_oracle",
                "topic_negative",
            )
        )
    assert manifest["screen"]["semantic_holdout"]["holdout_root_count"] == 26
    assert set(manifest["screen"]["negative_fixtures"]) == {
        "legacy-template-clone",
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
        "missing-mechanism-token",
    }


def test_real_adversarial_clones_and_missing_mechanism_fail_closed() -> None:
    base = grid.CASES[0]
    controls = grid._adversarial_cases()
    domain = controls["domain-identifier-renamed-clone"]
    assert "schedule_slots" in domain.header and "plan_gates" not in domain.header
    assert "SlotPlan" in domain.header and "GatePlan" not in domain.header
    constants = controls["constants-policy-clone"]
    assert '"ABC"' in constants.reference and '"SML"' not in constants.reference
    opposite = controls["opposite-end-selection-clone"]
    assert "cap.rbegin()" in opposite.reference
    for clone in controls.values():
        with pytest.raises(RuntimeError, match="duplicate_family"):
            grid._semantic_signatures((base, clone))
    missing = dataclasses.replace(base, task_id="missing", marker="not-present")
    with pytest.raises(RuntimeError, match="invariant_not_enforced"):
        grid._semantic_signatures((missing,))


def test_every_root_has_a_distinct_compiling_topic_negative_source(tmp_path: Path) -> None:
    roots = grid.build(tmp_path)
    assert set(grid.NEGATIVE_MUTATIONS) == {case.task_id for case in grid.CASES}
    normalized_negatives = set()
    for case, root in zip(grid.CASES, roots, strict=True):
        negative, reason = grid._negative_source(case)
        assert negative != case.reference
        assert reason
        emitted = (root / ".meta/negative_false_substitute.cpp").read_text()
        old, new, _ = grid.NEGATIVE_MUTATIONS[case.task_id]
        assert old not in emitted and new in emitted
        normalized = tuple(grid._normalized_code_tokens(emitted))
        assert normalized not in normalized_negatives
        normalized_negatives.add(normalized)
    assert len(normalized_negatives) == 20


def test_references_make_strict_whole_file_answers(tmp_path: Path) -> None:
    fence = chr(96) * 3
    for root in grid.build(tmp_path):
        task = moonlight_aider_task_sft.load_task(root)
        answer = moonlight_aider_task_sft.build_assistant_response(
            task, moonlight_aider_task_sft.load_example_files_from_config(root)
        )
        assert answer.startswith(f"{root.name}.h\n{fence}")
        assert f"{root.name}.cpp\n{fence}" in answer
        assert ".meta/example" not in answer


def test_docker_verifier_owns_snapshot_safe_oracle_contract() -> None:
    source = inspect.getsource(grid.verify_docker)
    assert '"--network",\n            "none"' in source
    assert '"Unix Makefiles"' in source
    assert "-fsanitize=address,undefined" in source
    assert "grader_mount_hash_mismatch" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "topic-negative.tsv" in source
    assert "adversarial-controls.tsv" in source
    assert "negative_fixture_not_rejected" in source


def test_wrapper_targets_parallel_reverify_tree() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_grid_ownership_mapping_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_grid_ownership_mapping_aider_tasks" in content
    assert "aider-tasks-reverify/aider-text-grid-reshaping/grid-ownership-mapping" in content
