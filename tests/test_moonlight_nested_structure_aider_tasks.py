from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft as sft
from w8_biayn.integrations import moonlight_nested_structure_aider_tasks as nested


def test_nested_structure_materializes_twenty_distinct_mechanisms(tmp_path: Path) -> None:
    roots = nested.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {spec.task_id for spec in nested.TASKS}
    assert len({spec.kind for spec in nested.TASKS}) == 20
    assert all(spec.task_id.endswith("-v2") for spec in nested.TASKS)
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert provenance["family_id"] == nested.FAMILY_ID
        assert provenance["semantic_mechanism"]
        assert provenance["selected_prompt"] == nested.SELECTED_PROMPT
        assert (root / ".meta/task_private_test.cpp").is_file()
        negatives = list((root / ".meta/negative").glob("*/*.cpp"))
        assert len(negatives) == 1
        assert negatives[0].read_text() != (root / ".meta/example.cpp").read_text()


def test_nested_structure_core_verifier_enforces_diversity_and_boundaries(tmp_path: Path) -> None:
    nested.build(tmp_path)
    nested.verify_core(tmp_path, require_remedy=False)
    manifest = json.loads((tmp_path / ".state/materialization-manifest.json").read_text())
    assert manifest["task_count"] == 20
    assert manifest["status"] == "semantically_admitted"
    assert manifest["screen"]["primary_core_objective"] == "achieved"
    assert manifest["screen"]["duplicate_family"] == "pass"
    assert manifest["screen"]["benchmark_contamination"] == "pass"
    assert manifest["screen"]["official_holdout_inventory"] == 26
    assert manifest["screen"]["excluded_source_inventory"] == 1
    assert manifest["screen"]["semantic_screen_sources"] == 27
    assert len({row["mechanism"] for row in manifest["tasks"]}) == 20
    assert max(pair["similarity"] for pair in manifest["family_pairs"]) < 0.72


def test_nested_structure_references_make_whole_file_answers(tmp_path: Path) -> None:
    root = nested.build(tmp_path)[0]
    task = sft.load_task(root)
    answer = sft.build_assistant_response(task, sft.load_example_files_from_config(root))
    assert answer.startswith(f"{root.name}.h\n```")
    assert f"{root.name}.cpp\n```" in answer
    assert ".meta/example" not in answer


def test_nested_structure_verifier_is_locked_and_executes_negative_fixtures() -> None:
    source = inspect.getsource(nested.verify)
    script = inspect.getsource(nested._docker_script)
    assert "W8_NESTED_STRUCTURE_GRADER_IMAGE" in source
    assert '"--network", "none"' in source
    assert "grader_mount_hash_mismatch" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "negative fixture passed" in script
    assert "ctest" in script


def test_nested_structure_benchmark_slug_screen_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="benchmark_id_overlap"):
        nested._benchmark_slug_screen("copied grade-school contract", "candidate")


def test_nested_structure_wrapper_targets_reverify_tree() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_nested_structure_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_nested_structure_aider_tasks" in content
    assert "aider-tasks-reverify/aider-dsa/nested-structure" in content
