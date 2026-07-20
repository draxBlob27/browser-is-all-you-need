from __future__ import annotations

import inspect
import json
from pathlib import Path

from w8_biayn.integrations import moonlight_aider_task_sft as sft
from w8_biayn.integrations import moonlight_nth_final_occurrences_aider_tasks as occurrences


def test_materializes_exact_authorized_diverse_inventory(tmp_path: Path) -> None:
    roots = occurrences.build(tmp_path)
    assert len(roots) == 10
    assert 8 <= len(roots) <= 12
    assert {root.name for root in roots} == {case.task_id for case in occurrences.CASES}
    assert len({case.mechanism for case in occurrences.CASES}) == 10
    assert [case.disposition for case in occurrences.CASES].count("repair-in-place") == 1
    assert [case.disposition for case in occurrences.CASES].count("replace") == 9
    assert len({case.legacy_id for case in occurrences.CASES}) == 10
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["family_id"] == occurrences.FAMILY_ID
        assert provenance["mechanism"]
        assert (root / ".meta/negative_false_substitute.cpp").is_file()


def test_core_manifest_independently_inspects_all_hard_rule_decisions(tmp_path: Path) -> None:
    occurrences.build(tmp_path)
    occurrences.verify_core(tmp_path)
    manifest = json.loads((tmp_path / ".state/materialization-manifest.json").read_text())
    hard = manifest["screen"]["hard_rule"]
    assert hard["root_count"] == 10
    assert hard["pair_count"] == 45 == hard["expected_pair_count"]
    assert tuple(hard["dimensions"]) == occurrences.HARD_DIMENSIONS
    assert len(hard["pairs"]) == 45
    expected_dimensions = set(occurrences.HARD_DIMENSIONS)
    seen_pairs = set()
    for pair in hard["pairs"]:
        seen_pairs.add((pair["left"], pair["right"]))
        assert set(pair["decisions"]) == expected_dimensions
        assert all(value is True for value in pair["decisions"].values())
    assert len(seen_pairs) == 45
    assert manifest["screen"]["semantic_holdout"]["holdout_root_count"] == 26


def test_controls_change_real_files_and_fail_every_production_dimension(tmp_path: Path) -> None:
    occurrences.build(tmp_path)
    hard = occurrences._hard_rule_screen(tmp_path)
    assert set(hard["controls"]) == {
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
    }
    for control in hard["controls"].values():
        assert control["changed_files"]
        assert set(control["decisions"]) == set(occurrences.HARD_DIMENSIONS)
        assert all(value is False for value in control["decisions"].values())
        assert control["production_rejected"] is True


def test_topic_negatives_are_nonempty_and_distinct(tmp_path: Path) -> None:
    roots = occurrences.build(tmp_path)
    normalized = set()
    for case, root in zip(occurrences.CASES, roots, strict=True):
        negative = (root / ".meta/negative_false_substitute.cpp").read_text()
        assert negative != case.reference
        assert case.negative_old not in negative
        signature = occurrences._normalize(negative)
        mutation = occurrences._normalize(case.negative_new)
        assert any(
            signature[index : index + len(mutation)] == mutation
            for index in range(len(signature) - len(mutation) + 1)
        )
        assert signature not in normalized
        normalized.add(signature)
    assert len(normalized) == 10


def test_references_render_as_strict_whole_file_answers(tmp_path: Path) -> None:
    for root in occurrences.build(tmp_path):
        task = sft.load_task(root)
        answer = sft.build_assistant_response(task, sft.load_example_files_from_config(root))
        assert answer.startswith(f"{root.name}.h\n```")
        assert f"{root.name}.cpp\n```" in answer
        assert ".meta/example" not in answer


def test_docker_verifier_owns_required_contract() -> None:
    source = inspect.getsource(occurrences.verify_docker)
    assert '"--network"' in source and '"none"' in source
    assert '"Unix Makefiles"' in source
    assert "-fsanitize=address,undefined" in source
    assert "grader_mount_hash_mismatch" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "negative_fixture_not_rejected" in inspect.getsource(occurrences._remedy_markdown)


def test_wrapper_targets_parallel_canonical_reverify_tree() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_nth_final_occurrences_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_nth_final_occurrences_aider_tasks" in content
    assert "aider-tasks-reverify/aider-dates-and-clocks/nth-and-final-occurrences" in content
