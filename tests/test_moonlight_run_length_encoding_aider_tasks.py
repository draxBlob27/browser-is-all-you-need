from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_run_length_encoding_aider_tasks as tasks


def test_materializes_twenty_distinct_reverify_roots(tmp_path: Path) -> None:
    roots = tasks.build(tmp_path)
    assert len(roots) == 20
    assert len({case.profile for case in tasks.CASES}) == 20
    assert len({case.public_api for case in tasks.CASES}) == 20
    assert {root.name for root in roots} == {case.task_id for case in tasks.CASES}
    assert sum(case.disposition == "repair-in-place" for case in tasks.CASES) == 1
    assert sum(case.disposition == "replace" for case in tasks.CASES) == 19
    assert tasks.CASES[0].legacy_id == tasks.CASES[0].task_id == "rle-access-badges"
    for case in tasks.CASES[1:]:
        assert case.legacy_id != case.task_id
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [
            ".meta/example.h",
            ".meta/example.cpp",
        ]
        assert config["files"]["test"] == [
            "task_visible_test.cpp",
            ".meta/task_hidden_test.cpp",
        ]
        assert provenance["family_id"] == tasks.FAMILY_ID
        assert provenance["legacy_family_preserved_at"] == tasks.LEGACY_ROOT.as_posix()
        assert (root / ".meta/bad_substitute.cpp").is_file()


def test_core_screen_is_artifact_derived_and_complete(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    screen = tasks.verify_core(tmp_path)
    family = screen["family"]
    assert family["normalizer"] == tasks.NORMALIZER
    assert family["evidence_source"] == "actual_emitted_task_tree"
    assert family["count_contract"] == {
        "type": "curriculum_inventory",
        "expected": 20,
        "user_minimum": None,
        "user_maximum": None,
    }
    assert len(family["pairwise_semantic_overlap"]) == 20 * 19 // 2
    assert family["maximum_overlap"] < tasks.PAIR_THRESHOLD
    assert set(family["maximum_overlap_by_dimension"]) == set(
        tasks.DIMENSION_THRESHOLDS
    )
    assert all(
        family["maximum_overlap_by_dimension"][name] < threshold
        for name, threshold in tasks.DIMENSION_THRESHOLDS.items()
    )
    assert all(
        set(row["dimension_overlap"]) == set(tasks.DIMENSION_THRESHOLDS)
        and not row["violations"]
        for row in family["pairwise_semantic_overlap"]
    )
    assert len(family["task_artifact_profiles"]) == 20
    for task_id, profile in family["task_artifact_profiles"].items():
        assert task_id in {case.task_id for case in tasks.CASES}
        assert set(profile["section_hashes"]) == {
            "docs",
            "public_api",
            "reference",
            "reference_source",
            "visible_tests",
            "private_tests",
            "negative_substitute",
        }
        assert set(profile["dimension_token_counts"]) == set(
            tasks.DIMENSION_THRESHOLDS
        )
        assert all(count > 0 for count in profile["dimension_token_counts"].values())
    assert set(family["adversarial_clone_results"]) == {
        "domain-identifier-renamed",
        "constants-or-policy-only",
        "opposite-end-selection",
    }
    assert all(
        row["failure"] == "duplicate_family"
        and row["evidence_source"] == "copied_and_mutated_emitted_task_root"
        and row["violations"]
        for row in family["adversarial_clone_results"].values()
    )
    assert screen["holdouts"]["holdout_root_count"] == 26
    assert screen["holdouts"]["status"] == "pass"
    assert screen["primary_core_objective"] == "pass:20/20"
    assert screen["deterministic_trace"] == "pass:20/20"
    assert all(
        row["deterministic_trace"] == "all_public_operations_and_observable_state"
        for row in screen["tasks"].values()
    )
    assert {row["semantic_profile"] for row in screen["tasks"].values()} == {
        case.profile for case in tasks.CASES
    }


def test_prompt_roles_references_and_remedies_are_bound(tmp_path: Path) -> None:
    roots = tasks.build(tmp_path)
    tasks.verify_core(tmp_path)
    remedy = tmp_path / ".state/remedy"
    assert len(list(remedy.glob("*.json"))) == 39
    for case in tasks.CASES:
        root = tmp_path / case.task_id
        task = moonlight_aider_task_sft.load_task(root)
        prompt = moonlight_aider_task_sft.build_prompt(task)
        answer = moonlight_aider_task_sft.build_assistant_response(
            task, moonlight_aider_task_sft.load_example_files_from_config(root)
        )
        assert answer.startswith(f"{case.task_id}.h\n```")
        assert f"{case.task_id}.cpp\n```" in answer
        assert ".meta/example" not in answer
        assert ".meta/example" not in prompt
        assert "CMakeLists.txt" not in prompt
        assert tasks._whole_format_failure(root, answer) is None
        record = json.loads((remedy / f"{case.legacy_id}.json").read_text())
        assert record["tree_hash_before"].startswith("sha256:")
        assert record["disposition"] == case.disposition
        assert record["finding_ids"] == ["RLE-F01", "RLE-F02", "RLE-F03", "RLE-F04"]
        assert record["primary_core_objective"] == "achieved"
    assert len(roots) == 20


def test_trace_contract_uses_emitted_api_and_hidden_oracle(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    for case in tasks.CASES:
        assert tasks._trace_contract_failure(case, tmp_path / case.task_id) is None

    case = tasks.CASES[0]
    hidden = tmp_path / case.task_id / ".meta/task_hidden_test.cpp"
    hidden.write_text(hidden.read_text().replace("longest_denial", "omitted_query"))
    assert (
        tasks._trace_contract_failure(case, tmp_path / case.task_id)
        == "trace_contract_incomplete"
    )


def test_fail_closed_helpers_cover_required_negative_classes(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    case = tasks.CASES[0]
    root = tmp_path / case.task_id
    config = json.loads((root / ".meta/config.json").read_text())
    files = config["files"]
    assert tasks._role_failure(root, files) is None

    unsafe = json.loads(json.dumps(files))
    unsafe["solution"].append("CMakeLists.txt")
    assert tasks._role_failure(root, unsafe) == "unsafe_path"

    missing = json.loads(json.dumps(files))
    missing["example"].pop()
    assert tasks._role_failure(root, missing) == "target_reference_mismatch"

    instructions = (root / ".docs/instructions.md").read_text()
    assert tasks._prompt_contract_failure(case, instructions) is None
    altered = re.sub(case.prompt_terms[0], "omitted", instructions, flags=re.I)
    assert tasks._prompt_contract_failure(case, altered) == "prompt_contract_incomplete"

    reference = (root / ".meta/example.cpp").read_text()
    assert tasks._core_failure(case, reference) is None
    assert (
        tasks._core_failure(case, reference.replace(case.marker, "removed_marker"))
        == "invariant_not_enforced"
    )
    legacy_clone = reference + "\nmax_run_count append_chunk expand() total_units\n"
    assert tasks._core_failure(case, legacy_clone) == "duplicate_family"


@pytest.mark.parametrize(
    "clone_kind",
    [
        "domain-identifier-renamed",
        "constants-or-policy-only",
        "opposite-end-selection",
    ],
)
def test_hard_rule_rejects_clones_of_emitted_artifacts(
    tmp_path: Path, clone_kind: str
) -> None:
    family = tmp_path / "family"
    tasks.build(family)
    source = family / tasks.CASES[0].task_id
    clone = tmp_path / clone_kind
    tasks._make_adversarial_clone(source, clone, clone_kind)
    original_profile = tasks._artifact_profile(source)
    clone_profile = tasks._artifact_profile(clone)
    evidence = tasks._pair_evidence(original_profile, clone_profile)
    assert evidence["violations"]
    assert evidence["combined_overlap"] >= tasks.PAIR_THRESHOLD
    with pytest.raises(RuntimeError, match="duplicate_family"):
        tasks._require_distinct_pair(evidence)


def test_hard_rule_cannot_be_rescued_by_a_different_negative_fixture(
    tmp_path: Path,
) -> None:
    family = tmp_path / "family"
    tasks.build(family)
    source = family / tasks.CASES[0].task_id
    clone = tmp_path / "negative-only-change"
    tasks._make_adversarial_clone(source, clone, "constants-or-policy-only")
    (clone / ".meta/bad_substitute.cpp").write_text(
        '#include "rle-access-badges.h"\n// deliberately unrelated bad answer\n'
    )
    evidence = tasks._pair_evidence(
        tasks._artifact_profile(source), tasks._artifact_profile(clone)
    )
    assert "combined_primary_logic_implementation" in evidence["violations"]
    with pytest.raises(RuntimeError, match="duplicate_family"):
        tasks._require_distinct_pair(evidence)


def test_legacy_output_path_is_immutable() -> None:
    with pytest.raises(RuntimeError, match="legacy_root_is_immutable"):
        tasks.build(tasks.LEGACY_ROOT, force=True)


def test_force_regeneration_invalidates_only_owner_recognized_receipts(
    tmp_path: Path,
) -> None:
    tasks.build(tmp_path)
    state = tmp_path / ".state"
    for name in ("docker-sanity.json", "host-oracle-iteration.json", "family-screen.json"):
        (state / name).write_text("stale\n")
    tasks.build(tmp_path, force=True)
    assert not (state / "docker-sanity.json").exists()
    assert not (state / "host-oracle-iteration.json").exists()
    assert not (state / "family-screen.json").exists()

    foreign = tmp_path / "foreign-root"
    (foreign / ".meta").mkdir(parents=True)
    (foreign / ".meta/provenance.json").write_text(
        json.dumps({"family_id": "another-owner"})
    )
    with pytest.raises(RuntimeError, match="foreign_generated_root"):
        tasks.build(tmp_path, force=True)


def test_verifier_owns_fresh_normal_sanitizer_and_negative_contract() -> None:
    source = inspect.getsource(tasks.verify)
    assert '"Unix Makefiles"' in source
    assert "-fsanitize=address,undefined" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "ctest" in source
    assert "topic_negative_fixture_executed" in source
    assert "docker-sanity.json" in source


def test_wrapper_targets_parallel_reverify_tree() -> None:
    wrapper = Path(
        "examples/slime/moonlight_cpp_perf/prepare_run_length_encoding_aider_tasks.sh"
    )
    assert wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_run_length_encoding_aider_tasks" in content
    assert "aider-tasks-reverify/aider-dsa/run-length-encoding" in content
