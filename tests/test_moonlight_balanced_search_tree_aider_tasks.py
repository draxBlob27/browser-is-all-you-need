
from __future__ import annotations

import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_balanced_search_tree_aider_tasks as balanced
from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task


def test_balanced_tree_curriculum_materializes_every_specified_task(tmp_path: Path) -> None:
    roots = balanced.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {spec.task_id for spec in balanced.TASKS}
    owner = Path(balanced.__file__).read_text(encoding="utf-8")
    assert "moonlight_binary_search_tree_aider_tasks" not in owner
    assert balanced.ROOT.parts[-3:] == (
        "aider-tasks-reverify",
        "aider-dsa",
        "balanced-search-tree",
    )[-3:]

    for root in roots:
        task_id = root.name
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        reference = (root / ".meta/example.cpp").read_text()
        starter = (root / f"{task_id}.cpp").read_text()
        hidden = (root / ".meta/task_hidden_test.cpp").read_text()
        cmake = (root / "CMakeLists.txt").read_text()

        assert config["source"] == "newly-authored-in-repository"
        assert config["attribution"]
        assert config["files"]["solution"] == [f"{task_id}.h", f"{task_id}.cpp"]
        assert config["files"]["test"] == [
            "task_visible_test.cpp",
            ".meta/task_hidden_test.cpp",
        ]
        assert config["files"]["example"] == [
            ".meta/example.h",
            ".meta/example.cpp",
        ]
        assert provenance["curriculum_path"] == balanced.CURRICULUM
        assert provenance["task_id"] == task_id
        assert provenance["family_id"] == balanced.FAMILY_ID
        assert provenance["selected_prompt"].endswith("implement-family-for-sft.md")
        assert provenance["status"] == "local candidate only; no dataset release"

        assert reference != starter
        assert "struct Node" in reference
        assert "validate_for_test" in reference
        assert all(token not in reference.lower() for token in balanced.BANNED_REFERENCE_TOKENS)
        assert "10000U" in hidden
        assert "1664525U+1013904223U" in hidden
        assert "validate_for_test()" in hidden
        assert "add_library(solution_compile_check OBJECT" in cmake
        assert "CURRICULUM_TESTING EXERCISM_RUN_ALL_TESTS=1" in cmake
        assert "add_test(NAME visible" in cmake
        assert "add_test(NAME hidden" in cmake

        prompt = build_prompt(load_task(root))
        assert (root / ".docs/instructions.md").read_text().strip() in prompt
        assert (root / f"{task_id}.h").read_text().strip() in prompt
        assert reference not in prompt
        assert hidden not in prompt
        assert cmake not in prompt

        remedy = json.loads(
            (tmp_path.parent / ".state/remedy" / f"{task_id}.json").read_text()
        )
        assert remedy["disposition"] == "replace"
        assert remedy["status"] == "implemented"
        assert remedy["tree_hash_before"].startswith(("sha256:", "missing"))
        assert remedy["primary_core_objective"] == "achieved"
        assert remedy["primary_core_evidence"]["false_substitute"]
        remedy_spec = (tmp_path.parent / remedy["remedy_spec_path"]).read_text()
        headings = [
            "# Identity",
            "# Objective",
            "# Public API",
            "# Behavior table",
            "# Implementation invariant",
            "# Starter and reference",
            "# Tests",
            "# Files and metadata",
            "# Build/oracle",
            "# Family/contamination",
            "# Optional dataset handoff",
            "# Acceptance",
        ]
        assert [line for line in remedy_spec.splitlines() if line.startswith("# ")] == headings

    screen = json.loads((tmp_path.parent / ".state/family-screen.json").read_text())
    assert screen["status"] == "pass"
    assert screen["benchmark_whole_slug"] == "pass"
    assert screen["duplicate_contracts"] == "pass"
    assert screen["prompt_boundary"] == "pass"


def test_balanced_tree_owner_refuses_legacy_output() -> None:
    with pytest.raises(ValueError, match="preserved legacy"):
        balanced.build(balanced.LEGACY_ROOT, force=True)


def test_balanced_tree_reference_uses_distinct_real_tree_cores() -> None:
    avl = balanced._reference(next(task for task in balanced.TASKS if task.kind == "AVL"))
    red_black = balanced._reference(
        next(task for task in balanced.TASKS if task.kind == "RB")
    )
    assert "class AvlTree" in avl
    assert "height" in avl
    assert "class RbTree" in red_black
    assert "Color::black" in red_black
    assert "black_height" in red_black
