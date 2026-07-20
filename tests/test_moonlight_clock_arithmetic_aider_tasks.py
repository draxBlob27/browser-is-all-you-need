from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_clock_arithmetic_aider_tasks as clock


def test_clock_arithmetic_materializes_authorized_reverify_family(
    tmp_path: Path,
) -> None:
    before = {
        spec.task_id: clock._tree_hash(clock.LEGACY_ROOT / spec.task_id)
        for spec in clock.TASKS
    }
    roots = clock.build(tmp_path)
    assert clock.MIN_ROOTS == 8
    assert clock.MAX_ROOTS == 12
    assert clock.MIN_ROOTS <= len(roots) == 10 <= clock.MAX_ROOTS
    assert {path.name for path in roots} == {spec.task_id for spec in clock.TASKS}
    assert before == {
        spec.task_id: clock._tree_hash(clock.LEGACY_ROOT / spec.task_id)
        for spec in clock.TASKS
    }
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        remedy = json.loads(
            (tmp_path / ".state/remedy" / f"{root.name}.json").read_text()
        )
        assert config["files"]["solution"] == [
            f"{root.name}.h", f"{root.name}.cpp",
        ]
        assert config["files"]["example"] == [
            ".meta/example.h", ".meta/example.cpp",
        ]
        assert provenance["task_id"] == root.name
        assert provenance["status"] == (
            "local candidate artifact; dataset handoff not requested"
        )
        assert remedy["disposition"] == "repair-in-place"
        assert remedy["tree_hash_before"] == before[root.name]
        assert remedy["requested_legacy_root_status"] == "absent"
        assert remedy["user_inputs"]["hard_rule_root_count"] == "8-12"
        assert (root / ".meta/negative_false_substitute.cpp").is_file()


def test_clock_arithmetic_hard_rule_is_complete_and_independently_inspected(
    tmp_path: Path,
) -> None:
    clock.build(tmp_path)
    manifest = clock.verify_core(tmp_path)
    hard_rule = manifest["screen"]["hard_rule"]
    assert hard_rule["pair_count"] == 45
    assert hard_rule["expected_pair_count"] == 45
    assert set(hard_rule["dimensions"]) == set(clock.HARD_RULE_DIMENSIONS)
    assert len(hard_rule["pairs"]) == 45
    expected_pairs = {
        frozenset((left.task_id, right.task_id))
        for left, right in combinations(clock.TASKS, 2)
    }
    assert {
        frozenset((item["left"], item["right"])) for item in hard_rule["pairs"]
    } == expected_pairs
    for item in hard_rule["pairs"]:
        assert item["materially_distinct_in_all_dimensions"] is True
        assert item["failed_dimensions"] == []
        assert set(item["dimensions"]) == set(clock.HARD_RULE_DIMENSIONS)
        for dimension, decision in item["dimensions"].items():
            assert decision["materially_distinct"] is True
            assert decision["similarity"] < clock.HARD_RULE_LIMITS[dimension]

    # Independent artifact inspection: every dimension has genuinely different
    # normalized emitted material, not merely unequal IDs or declared profiles.
    materials = {
        spec.task_id: clock._artifact_dimensions(tmp_path / spec.task_id)
        for spec in clock.TASKS
    }
    for left, right in combinations(clock.TASKS, 2):
        for dimension in clock.HARD_RULE_DIMENSIONS:
            assert clock._normalized_tokens(materials[left.task_id][dimension]) != (
                clock._normalized_tokens(materials[right.task_id][dimension])
            )


def test_clock_arithmetic_controls_are_nonempty_coherent_duplicate_controls(
    tmp_path: Path,
) -> None:
    clock.build(tmp_path)
    manifest = clock.verify_core(tmp_path)
    controls = manifest["screen"]["adversarial_controls"]
    assert set(controls) == set(clock.ADVERSARIAL_CONTROLS)
    base_for = {
        "domain-identifier-renamed-clone": clock.TASKS[0],
        "constants-policy-only-clone": clock.TASKS[0],
        "opposite-end-selection-clone": clock.TASKS[8],
    }
    for name, record in controls.items():
        assert record["status"] == "rejected"
        assert record["production_evaluator"] is True
        assert set(record["decision"]["failed_dimensions"]) == set(
            clock.HARD_RULE_DIMENSIONS
        )
        control_root = tmp_path / ".state/hard-rule-controls" / name
        assert clock._tree_hash(control_root, include_state=True) != "not_available"
        base = base_for[name]
        base_material = clock._artifact_dimensions(tmp_path / base.task_id)
        clone_material = clock._artifact_dimensions(control_root, control=True)
        assert any(
            base_material[dimension] != clone_material[dimension]
            for dimension in clock.HARD_RULE_DIMENSIONS
        )
        independent = clock._pair_decision(
            base_material, clone_material, base.task_id, name
        )
        assert set(independent["failed_dimensions"]) == set(
            clock.HARD_RULE_DIMENSIONS
        )


def test_clock_arithmetic_topic_negatives_change_reference_logic(
    tmp_path: Path,
) -> None:
    roots = clock.build(tmp_path)
    for spec, root in zip(clock.TASKS, roots, strict=True):
        reference = (root / ".meta/example.cpp").read_text()
        negative = (root / ".meta/negative_false_substitute.cpp").read_text()
        assert spec.reference_marker in reference
        assert reference != negative
        assert spec.negative_old in reference
        assert spec.negative_new in negative


def test_clock_arithmetic_reference_makes_whole_file_answer(
    tmp_path: Path,
) -> None:
    root = clock.build(tmp_path)[0]
    task = moonlight_aider_task_sft.load_task(root)
    answer = moonlight_aider_task_sft.build_assistant_response(
        task, moonlight_aider_task_sft.load_example_files_from_config(root)
    )
    assert answer.startswith(f"{root.name}.h\n```")
    assert f"{root.name}.cpp\n```" in answer


def test_clock_arithmetic_force_invalidates_stale_receipts(tmp_path: Path) -> None:
    clock.build(tmp_path)
    state = tmp_path / ".state"
    for name in (
        "materialization-manifest.json",
        "host-verification-receipt.json",
        "docker-sanity.json",
    ):
        (state / name).write_text("stale")
    clock.build(tmp_path, force=True)
    for name in (
        "materialization-manifest.json",
        "host-verification-receipt.json",
        "docker-sanity.json",
    ):
        assert not (state / name).exists()


def test_clock_arithmetic_refuses_both_legacy_roots() -> None:
    with pytest.raises(RuntimeError, match="legacy_root_immutable"):
        clock.build(clock.LEGACY_ROOT)
    with pytest.raises(RuntimeError, match="legacy_root_immutable"):
        clock.build(clock.REQUESTED_LEGACY_ROOT)


def test_clock_arithmetic_wrapper_targets_reverify_tree() -> None:
    wrapper = Path(clock.WRAPPER_PATH)
    assert wrapper.exists() and wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_clock_arithmetic_aider_tasks" in content
    assert (
        "aider-tasks-reverify/aider-text-grid-reshaping/clock-arithmetic"
        in content
    )


def test_clock_arithmetic_docker_runner_binds_tasks_controls_and_mount_hashes() -> None:
    assert 'for task_id,want in expected["tasks"].items()' in clock.DOCKER_RUNNER
    assert 'for name,want in expected["controls"].items()' in clock.DOCKER_RUNNER
    assert "grader_mount_hash_mismatch" in clock.DOCKER_RUNNER
    assert "negative_fixture_not_rejected" in clock.DOCKER_RUNNER
    assert 'env["ASAN_OPTIONS"]="detect_leaks=0"' in clock.DOCKER_RUNNER
