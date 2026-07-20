from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft as sft
from w8_biayn.integrations import moonlight_overflow_safe_date_math_aider_tasks as tasks
from w8_biayn.integrations.moonlight_overflow_safe_date_math_cases import CASES


def test_materializes_ten_distinct_reverify_roots(tmp_path: Path) -> None:
    roots = tasks.build(tmp_path)
    expected = {case.task_id for case in CASES}
    assert len(roots) == 10
    assert tasks.FAMILY_ROOT_MIN <= len(roots) <= tasks.FAMILY_ROOT_MAX
    assert {root.name for root in roots} == expected
    assert len({case.profile for case in CASES}) == 10
    assert len({case.function for case in CASES}) == 10
    for case, root in zip(CASES, roots, strict=True):
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [
            f"{case.task_id}.h",
            f"{case.task_id}.cpp",
        ]
        assert config["files"]["example"] == [
            ".meta/example.h",
            ".meta/example.cpp",
        ]
        assert (root / ".meta/oracle_test.cpp").is_file()
        assert (root / ".meta/negative.cpp").is_file()
        assert (root / ".meta/negative_test.cpp").is_file()
        record = json.loads(
            (tmp_path / ".state/remedy" / f"{case.legacy_id}.json").read_text()
        )
        assert record["tree_hash_before"] == tasks._tree_hash(
            tasks.LEGACY_OUT / case.legacy_id
        )
        assert record["disposition"] == tasks.disposition_for(case)
        assert record["user_inputs"]["hard_root_count"] == "8-12"


def test_legacy_root_is_immutable(tmp_path: Path) -> None:
    before = tasks._tree_hash(tasks.LEGACY_OUT)
    tasks.build(tmp_path, force=True)
    assert tasks._tree_hash(tasks.LEGACY_OUT) == before
    with pytest.raises(tasks.VerificationError, match="legacy_root_immutable"):
        tasks.build(tasks.LEGACY_OUT, force=True)


def test_prompt_roles_all_pairs_and_holdouts_are_independently_inspected(
    tmp_path: Path,
) -> None:
    tasks.build(tmp_path)
    evidence = tasks.verify_core(tmp_path)
    assert set(evidence) == {case.task_id for case in CASES}
    screen = json.loads((tmp_path / ".state/family-screen.json").read_text())
    assert screen["root_count"] == 10
    assert screen["root_count_bounds"] == {"minimum": 8, "maximum": 12}
    assert len(screen["pairwise_semantic_overlap"]) == 45
    assert len(screen["benchmark_inventory"]) == 26
    assert len(screen["benchmark_comparisons"]) == 260
    hard = screen["hard_rule"]
    assert hard["dimensions"] == list(tasks.HARD_RULE_DIMENSIONS)
    assert hard["comparison_count"] == hard["expected_comparison_count"] == 45
    assert hard["thresholds"] == tasks.HARD_RULE_THRESHOLDS
    for pair in hard["pairwise"]:
        assert set(pair["dimension_overlaps"]) == set(tasks.HARD_RULE_DIMENSIONS)
        assert set(pair["dimension_decisions"]) == set(tasks.HARD_RULE_DIMENSIONS)
        assert all(pair["dimension_decisions"].values())
        assert pair["failed_dimensions"] == []
        assert pair["failure"] is None
    for case in CASES:
        root = tmp_path / case.task_id
        task = sft.load_task(root)
        response = sft.build_assistant_response(
            task, sft.load_example_files_from_config(root)
        )
        assert response.startswith(f"{case.task_id}.h\n```")
        assert ".meta/" not in response
        assert "CMakeLists.txt" not in response
        assert set(evidence[case.task_id]["hard_rule_dimensions"]) == set(
            tasks.HARD_RULE_DIMENSIONS
        )


def test_coherent_adversarial_controls_change_files_and_fail_all_dimensions(
    tmp_path: Path,
) -> None:
    tasks.build(tmp_path)
    source = tmp_path / "safe-date-audit-export"
    case = next(case for case in CASES if case.task_id == source.name)
    for variant in tasks.ADVERSARIAL_CONTROLS:
        clone, mutation = tasks._make_adversarial_clone(
            source, variant, tmp_path / "controls"
        )
        assert mutation["changed_file_count"] > 0
        assert mutation["changed_files"]
        assert mutation["role_coherent"] is True
        assert mutation["tree_hash"] != tasks._tree_hash(source)
        config = json.loads((clone / ".meta/config.json").read_text())
        assert tasks._role_failure(clone, config["files"]) is None
        result = tasks._hard_rule_pair_result(source, clone)
        assert result["failure"] == "duplicate_family"
        assert set(result["dimension_decisions"]) == set(tasks.HARD_RULE_DIMENSIONS)
        assert not any(result["dimension_decisions"].values())
        assert set(result["failed_dimensions"]) == set(tasks.HARD_RULE_DIMENSIONS)
        assert case.function in (clone / ".meta/example.cpp").read_text() or variant == "domain-identifier-renamed"


def test_every_topic_negative_is_a_real_source_mutation(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    for case in CASES:
        root = tmp_path / case.task_id
        reference = (root / ".meta/example.cpp").read_text()
        negative = (root / ".meta/negative.cpp").read_text()
        assert case.negative_old in reference
        assert case.negative_old not in negative
        assert case.negative_new in negative
        assert reference != negative
        assert "WILL_FAIL TRUE" in (root / "CMakeLists.txt").read_text()


def test_hard_rule_count_and_roles_fail_closed(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    shutil.rmtree(tmp_path / CASES[-1].task_id)
    with pytest.raises(tasks.VerificationError, match="generator_output_drift"):
        tasks.verify_core(tmp_path)

    roles_root = tmp_path / "roles"
    tasks.build(roles_root)
    config_path = roles_root / CASES[0].task_id / ".meta/config.json"
    config = json.loads(config_path.read_text())
    config["files"]["solution"].append(".meta/example.cpp")
    config_path.write_text(json.dumps(config))
    with pytest.raises(tasks.VerificationError, match="unsafe_path"):
        tasks.verify_core(roles_root)


def test_wrapper_targets_reverify_root_and_is_executable() -> None:
    path = Path(
        "examples/slime/moonlight_cpp_perf/prepare_overflow_safe_date_math_aider_tasks.sh"
    )
    assert path.is_file()
    assert path.stat().st_mode & 0o111
    text = path.read_text()
    assert "aider-tasks-reverify/aider-text-grid-reshaping/overflow-safe-date-math" in text


def test_default_docker_receipt_binds_live_tree_when_present() -> None:
    receipt_path = tasks.DEFAULT_OUT / ".state/docker-sanity.json"
    if not receipt_path.is_file():
        pytest.skip("owner-controlled Docker sanity has not run in this checkout")
    receipt = json.loads(receipt_path.read_text())
    assert receipt["status"] == "pass"
    assert receipt["evidence_class"] == "docker_sanity"
    assert receipt["locked_oracle"] is False
    assert receipt["network"] == "none"
    assert receipt["image"] == tasks.SANITY_IMAGE
    assert receipt["generator_revision"] == tasks._generator_revision()
    assert receipt["family_screen_hash"] == tasks._sha256(
        (tasks.DEFAULT_OUT / ".state/family-screen.json").read_bytes()
    )
    assert set(receipt["tasks"]) == {case.task_id for case in CASES}
    assert set(receipt["hard_rule_controls"]) == set(tasks.ADVERSARIAL_CONTROLS)
    for case in CASES:
        item = receipt["tasks"][case.task_id]
        assert item["normal"] == item["asan_ubsan"] == 4
        assert item["tree_hash"] == tasks._tree_hash(tasks.DEFAULT_OUT / case.task_id)
        assert item["mounted_tree_hash"] == item["tree_hash"]
        record = json.loads(
            (
                tasks.DEFAULT_OUT
                / ".state/remedy"
                / f"{case.legacy_id}.json"
            ).read_text()
        )
        assert record["status"] == "verified"
        assert record["local_status"] == "local_family_verified"
