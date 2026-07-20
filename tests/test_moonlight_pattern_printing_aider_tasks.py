from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_pattern_printing_aider_tasks as tasks


def test_materializes_exact_distinct_reverify_inventory(tmp_path: Path) -> None:
    roots = tasks.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {case.task_id for case in tasks.CASES}
    assert sum(case.disposition == "repair-in-place" for case in tasks.CASES) == 1
    assert next(case for case in tasks.CASES if case.disposition == "repair-in-place").task_id == "pattern-archway-stones"
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert config["files"]["test"] == ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"]
        assert provenance["family_id"] == "pattern-printing-v4"
        assert provenance["audit_specification"].endswith("pattern-printing.md")
        assert (root / ".meta/negative.cpp").is_file()


def test_remedy_records_bind_every_legacy_root_and_exact_disposition(tmp_path: Path) -> None:
    tasks.plan_remedies(tmp_path)
    tasks._verify_remedy_specs(tmp_path)
    for case in tasks.CASES:
        record = json.loads((tmp_path / ".state/remedy" / f"{case.legacy_id}.json").read_text())
        assert record["tree_hash_before"].startswith("sha256:")
        assert record["disposition"] == case.disposition
        assert record["replacement_task_id"] == case.task_id
        assert record["status"] == "planned"
        spec = Path(record["remedy_spec_path"]).read_text()
        assert "FAMILY_NAME=pattern-printing" in spec
        assert "not_requested" in spec


def test_reference_files_make_exact_whole_file_answer(tmp_path: Path) -> None:
    root = tasks.build(tmp_path)[0]
    task = moonlight_aider_task_sft.load_task(root)
    answer = moonlight_aider_task_sft.build_assistant_response(
        task, moonlight_aider_task_sft.load_example_files_from_config(root)
    )
    assert answer.startswith(f"{root.name}.h\n```")
    assert f"{root.name}.cpp\n```" in answer
    assert ".meta/example" not in answer


def test_core_screen_covers_all_pairs_holdouts_and_clone_controls(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    evidence = tasks.verify_core(tmp_path)
    assert set(evidence) == {case.task_id for case in tasks.CASES}
    screen = json.loads((tmp_path / ".state/family-screen.json").read_text())
    assert len(screen["pairwise_semantic_overlap"]) == 190
    assert len(screen["benchmark_comparisons"]) == 520
    hard_rule = screen["hard_rule"]
    assert hard_rule["dimensions"] == list(tasks.HARD_RULE_DIMENSIONS)
    assert hard_rule["thresholds"] == tasks.HARD_RULE_THRESHOLDS
    assert hard_rule["comparison_count"] == hard_rule["expected_comparison_count"] == 190
    assert len(hard_rule["pairwise"]) == 190
    for pair in hard_rule["pairwise"]:
        assert pair["failure"] is None
        assert pair["failed_dimensions"] == []
        assert set(pair["dimension_overlaps"]) == set(tasks.HARD_RULE_DIMENSIONS)
        assert all(
            pair["dimension_overlaps"][dimension]
            < tasks.HARD_RULE_THRESHOLDS[dimension]
            for dimension in tasks.HARD_RULE_DIMENSIONS
        )
    assert set(screen["adversarial_clone_results"]) == set(tasks.ADVERSARIAL_CONTROLS)
    assert all(
        item["failure"] == "duplicate_family"
        and set(item["failed_dimensions"]) == set(tasks.HARD_RULE_DIMENSIONS)
        for item in screen["adversarial_clone_results"].values()
    )
    for case in tasks.CASES:
        dimensions = evidence[case.task_id]["hard_rule_dimensions"]
        assert set(dimensions) == set(tasks.HARD_RULE_DIMENSIONS)
        assert all(item["feature_count"] > 0 for item in dimensions.values())
        assert all(
            re.fullmatch(r"sha256:[0-9a-f]{64}", item["fingerprint"])
            for item in dimensions.values()
        )
    assert screen["result"] == "pass"


def test_each_negative_mutation_is_unique_and_changes_reference() -> None:
    assert len({case.negative_description for case in tasks.CASES}) == 20
    for case in tasks.CASES:
        assert case.body.count(case.negative_old) == 1
        assert case.negative_old != case.negative_new
        assert case.negative_description


def test_genuine_adversarial_clones_are_coherent_and_rejected(
    tmp_path: Path,
) -> None:
    family = tmp_path / "family"
    tasks.build(family)
    case = next(
        case for case in tasks.CASES if case.task_id == "pattern-archway-stones"
    )
    root = family / case.task_id
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
            assert "raster_archive_portal" in combined
        elif variant == "constants-or-policy-only":
            assert "radius > 40" in combined
            assert "raster_archway(41" in combined
        else:
            assert "d >= inner" in combined
            assert "inner radius" in combined
        result = tasks._hard_rule_pair_result(root, clone, case, case)
        assert result["failure"] == "duplicate_family"
        assert set(result["failed_dimensions"]) == set(tasks.HARD_RULE_DIMENSIONS)


def test_hard_rule_root_count_is_fail_closed(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    shutil.rmtree(tmp_path / tasks.CASES[-1].task_id)
    with pytest.raises(tasks.VerificationError, match="hard_rule_root_count"):
        tasks.verify_core(tmp_path)


def test_legacy_root_is_immutable() -> None:
    with pytest.raises(tasks.VerificationError, match="legacy_root_immutable"):
        tasks.build(tasks.LEGACY_OUT, force=True)


def test_wrapper_targets_reverify_tree_and_owner() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_pattern_printing_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_pattern_printing_aider_tasks" in content
    assert "aider-tasks-reverify/aider-text-grid-reshaping/pattern-printing" in content
