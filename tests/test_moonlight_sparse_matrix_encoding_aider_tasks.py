from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_sparse_matrix_encoding_aider_tasks as tasks


def test_materializes_twenty_distinct_reverified_roots(tmp_path: Path) -> None:
    roots = tasks.build(tmp_path)
    assert len(roots) == 20
    assert len({case.task_id for case in tasks.CASES}) == 20
    assert len({case.profile for case in tasks.CASES}) == 20
    assert len({case.public_api for case in tasks.CASES}) == 20
    assert sum(case.disposition == "repair-in-place" for case in tasks.CASES) == 1
    assert sum(case.disposition == "replace" for case in tasks.CASES) == 19
    for case, root in zip(tasks.CASES, roots, strict=True):
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["family_id"] == tasks.FAMILY_ID
        assert provenance["legacy_task_id"] == case.legacy_id
        assert provenance["semantic_profile"] == case.profile
        assert case.marker in (root / ".meta/example.cpp").read_text()
        assert (root / ".meta/negative_false_substitute.cpp").is_file()


def test_core_verifier_checks_all_pairs_prompt_roles_and_holdouts(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    tasks.verify_core(tmp_path)
    manifest = json.loads((tmp_path / ".state/materialization-manifest.json").read_text())
    assert manifest["task_count"] == 20
    assert manifest["status"] == "implemented"
    assert manifest["screen"]["prompt_boundary"] == "pass"
    assert manifest["screen"]["reference_mapping"] == "pass"
    hard_rule = manifest["screen"]["hard_rule"]
    assert hard_rule["pair_count"] == hard_rule["expected_pair_count"] == 190
    assert hard_rule["requested_root_count"] == {"minimum": 15, "maximum": 20}
    assert hard_rule["materialized_root_count"] == 20
    assert hard_rule["count_within_bounds"] is True
    assert tuple(hard_rule["dimensions"]) == tasks.HARD_RULE_DIMENSIONS
    assert hard_rule["dimension_limits"] == tasks.HARD_RULE_LIMITS
    assert len(hard_rule["pairs"]) == 190
    assert hard_rule["status"] == "pending_execution"
    for pair in hard_rule["pairs"]:
        assert pair["aggregate_containment"] < hard_rule["aggregate_limit"]
        for dimension in hard_rule["dimensions"]:
            assert pair[f"{dimension}_structurally_distinct"]
            assert pair[f"{dimension}_materially_distinct"]
            assert pair["scores"][dimension] < hard_rule["dimension_limits"][dimension]
    assert manifest["screen"]["semantic_holdout"]["holdout_root_count"] == 26
    assert manifest["screen"]["semantic_holdout"]["comparison_count"] == 520
    assert set(manifest["screen"]["adversarial_controls"]) == {
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
    }


def test_adversarial_clone_controls_fail_closed(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    outcomes = tasks._screen_controls(tmp_path)
    assert all(
        value["status"] == "rejected"
        and value["reason"] == "duplicate_family"
        and value["production_comparator"] is True
        for value in outcomes.values()
    )
    base = tasks.CASES[0]
    controls = {name: tasks._clone_control(base, name) for name in outcomes}
    assert controls["constants-policy-clone"]["candidate.cpp"] == base.reference
    assert tasks._normalized_tokens(
        controls["domain-identifier-renamed-clone"]["candidate.cpp"]
    ) == tasks._normalized_tokens(base.reference)
    assert tasks._normalized_tokens(
        controls["opposite-end-selection-clone"]["candidate.cpp"]
    ) == tasks._normalized_tokens(base.reference)
    for name, files in controls.items():
        assert base.negative_new not in files["candidate.cpp"]
        root = tmp_path / ".state/hard-rule-controls" / name
        clone = tasks._artifact_dimensions(root, reference_path="candidate.cpp")
        with pytest.raises(RuntimeError, match="^duplicate_family:"):
            tasks._compare_hard_rule_dimensions(
                tasks._artifact_dimensions(tmp_path / base.task_id),
                clone,
                base.task_id,
                name,
            )


def test_hard_rule_names_all_seven_required_axes() -> None:
    assert tasks.HARD_RULE_DIMENSIONS == (
        "public_api",
        "owned_state_or_algorithm",
        "mutation_or_selection_rules",
        "invalid_and_boundary_behavior",
        "reference_control_flow",
        "deterministic_oracle",
        "topic_specific_negative_fixture",
    )


def test_force_regeneration_invalidates_stale_verification_receipts(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    state = tmp_path / ".state"
    for name in (
        "host-verification-receipt.json",
        "materialization-manifest.json",
        "oracle-receipt.json",
    ):
        (state / name).write_text("stale")
    tasks.build(tmp_path, force=True)
    assert not (state / "host-verification-receipt.json").exists()
    assert not (state / "materialization-manifest.json").exists()
    assert not (state / "oracle-receipt.json").exists()


def test_every_topic_negative_is_distinct_and_mutated(tmp_path: Path) -> None:
    roots = tasks.build(tmp_path)
    signatures = set()
    for case, root in zip(tasks.CASES, roots, strict=True):
        negative = (root / ".meta/negative_false_substitute.cpp").read_text()
        assert negative != case.reference
        assert case.negative_old not in negative
        assert case.negative_new in negative
        signatures.add(tasks._normalized_tokens(negative))
    assert len(signatures) == 20


def test_references_make_strict_whole_file_answers(tmp_path: Path) -> None:
    fence = "```"
    for root in tasks.build(tmp_path):
        task = moonlight_aider_task_sft.load_task(root)
        answer = moonlight_aider_task_sft.build_assistant_response(
            task, moonlight_aider_task_sft.load_example_files_from_config(root)
        )
        assert answer.startswith(f"{root.name}.h\n{fence}")
        assert f"{root.name}.cpp\n{fence}" in answer
        assert ".meta/example" not in answer


def test_legacy_output_is_refused() -> None:
    with pytest.raises(RuntimeError, match="legacy_root_immutable"):
        tasks.build(tasks.LEGACY_ROOT, force=True)


def test_docker_sanity_owns_required_evidence_contract() -> None:
    source = inspect.getsource(tasks.docker_sanity)
    assert '"--network"' in source and '"none"' in source
    assert '"Unix Makefiles"' in source
    assert "-fsanitize=address,undefined" in source
    assert "grader_mount_hash_mismatch" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "topic-negative.tsv" in source
    assert "adversarial-controls.tsv" in source


def test_wrapper_targets_parallel_reverify_tree() -> None:
    wrapper = Path(
        "examples/slime/moonlight_cpp_perf/prepare_sparse_matrix_encoding_aider_tasks.sh"
    )
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_sparse_matrix_encoding_aider_tasks" in content
    assert "aider-tasks-reverify/aider-text-grid-reshaping/sparse-matrix-encoding" in content
