from __future__ import annotations

import json
from pathlib import Path

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_duration_formatting_aider_tasks as tasks


def test_materializes_ten_distinct_replacements_with_safe_roles(tmp_path: Path) -> None:
    roots = tasks.build(tmp_path)
    assert tasks.MIN_TASKS == 8
    assert tasks.MAX_TASKS == 12
    assert len(roots) == 10
    assert {root.name for root in roots} == {case.task_id for case in tasks.CASES}
    assert {case.legacy_id for case in tasks.CASES} == {
        path.name for path in tasks.LEGACY_ROOT.iterdir() if path.is_dir()
    }
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert config["files"]["test"] == ["task_visible_test.cpp"]
        assert provenance["legacy_family_type"] == "aider-dates-and-clocks"
        assert provenance["user_family_type"] == "aider-text-grid-reshaping"
        assert (root / ".meta/negative_false_substitute.cpp").is_file()


def test_references_make_exact_whole_file_answers(tmp_path: Path) -> None:
    for root in tasks.build(tmp_path):
        task = moonlight_aider_task_sft.load_task(root)
        answer = moonlight_aider_task_sft.build_assistant_response(
            task, moonlight_aider_task_sft.load_example_files_from_config(root)
        )
        assert answer.startswith(f"{root.name}.h\n```")
        assert f"{root.name}.cpp\n```" in answer
        assert ".meta/example" not in answer


def test_independent_seven_dimension_all_pairs_and_controls(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    manifest = tasks.verify_core(tmp_path)
    screen = manifest["screen"]["hard_rule"]
    assert screen["task_count"] == 10
    assert screen["pair_count"] == 45
    assert screen["expected_pair_count"] == 45
    assert screen["dimensions"] == list(tasks.DIMENSIONS)
    assert screen["conjunctive_decision"] is True
    assert len(screen["pairs"]) == 45
    for pair in screen["pairs"]:
        assert set(pair["dimensions"]) == set(tasks.DIMENSIONS)
        for dimension in tasks.DIMENSIONS:
            row = pair["dimensions"][dimension]
            assert row["pass"] is True
            assert row["decision"] == "materially_distinct"
            assert row["left_normalized_hash"] != row["right_normalized_hash"]
            assert row["containment"] < 0.995

    controls = manifest["screen"]["adversarial_controls"]
    assert set(controls) == {
        "domain-identifier-renamed",
        "constants-or-policy-only",
        "opposite-end-selection",
    }
    for control in controls.values():
        assert control["tree_hash_before"] != control["tree_hash_after"]
        assert control["changed"] is True
        assert control["evaluator_result"] == "rejected:duplicate_family"
        # Inspect the per-dimension decisions instead of trusting a top-level pass bit.
        assert set(control["dimensions"]) == set(tasks.DIMENSIONS)
        assert any(not row["pass"] for row in control["dimensions"].values())


def test_remedy_records_bind_every_legacy_root(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    records = sorted((tmp_path / ".state/remedy").glob("*.json"))
    assert len(records) == 10
    for path in records:
        record = json.loads(path.read_text())
        assert record["disposition"] == "replace"
        assert record["primary_core_objective"] == "achieved"
        assert record["tree_hash_before"] == tasks._tree_hash(
            tasks.LEGACY_ROOT / record["legacy_task_id"]
        )
        assert record["tree_hash_after"].startswith("sha256:")
        assert record["user_inputs"]["hard_rule_count"] == "8-12"


def test_wrapper_targets_parallel_reverification_tree() -> None:
    wrapper = Path(tasks.WRAPPER_PATH)
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "aider-tasks-reverify/aider-text-grid-reshaping/duration-formatting" in content
    assert "moonlight_duration_formatting_aider_tasks" in content
