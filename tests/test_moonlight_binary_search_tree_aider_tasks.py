from __future__ import annotations

import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_binary_search_tree_aider_tasks as bst
from w8_biayn.integrations.moonlight_aider_task_eval import (
    WholeFormatError,
    build_prompt,
    load_task,
    parse_whole_file_blocks,
)


def test_bst_v2_materializes_owned_node_replacements(tmp_path: Path) -> None:
    roots = bst.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {task.task_id for task in bst.TASKS}

    for root in roots:
        task_id = root.name
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        header = (root / f"{task_id}.h").read_text()
        reference = (root / ".meta/example.cpp").read_text()
        private = (root / ".meta" / f"{task_id}_private_test.cpp").read_text()
        cmake = (root / "CMakeLists.txt").read_text()

        assert config["family_id"] == bst.FAMILY_ID
        assert config["files"]["solution"] == [f"{task_id}.h", f"{task_id}.cpp"]
        assert config["files"]["test"] == [
            f"{task_id}_test.cpp", f".meta/{task_id}_private_test.cpp"
        ]
        assert provenance["task_id"] == task_id
        assert provenance["selected_prompt"].endswith("implement-family-for-sft.md")
        assert "not admitted SFT data" in provenance["status"]
        assert "struct Node" in header
        assert "std::unique_ptr<Node> root_" in header
        assert "friend struct BstInvariantProbe" in header
        assert "insert(" in reference and "erase(" in reference
        assert all(token not in reference.lower() for token in bst.BANNED)
        for name in (
            "public_examples", "invalid_and_atomic", "duplicate_or_payload_update",
            "deletion_shapes", "ordering_and_boundaries", "domain_special_rule",
            "deterministic_trace", "invariant_and_negative_fixtures",
        ):
            assert name in private or name in (root / f"{task_id}_test.cpp").read_text()
            assert f"add_test(NAME {name}" in cmake
        assert "4096U" in private
        assert "1664525U+1013904223U" in private
        assert "struct BstInvariantProbe" in private
        assert "inspect(tree).valid" in private
        assert "REQUIRE(true)" not in private
        for fixture in (
            "negative-set-wrapper", "negative-map-wrapper", "negative-sorted-vector",
            "negative-degenerate-node", "negative-bad-order", "negative-stale-augmentation",
            "negative-domain-boundary", "negative-prompt-omission",
        ):
            assert (root / ".meta/negative" / fixture / f"{task_id}.cpp").is_file()

        prompt = build_prompt(load_task(root))
        assert (root / ".docs/instructions.md").read_text().strip() in prompt
        assert header.strip() in prompt
        assert reference not in prompt
        assert private not in prompt
        assert cmake not in prompt

        remedy = json.loads((tmp_path / ".state/remedy" / f"{task_id}.json").read_text())
        assert remedy["disposition"] == "replace"
        # Materialization is deliberately not evidence for the advertised
        # core.  Only the compiling/executing core verifier may promote it.
        assert remedy["primary_core_objective"] == "not_achieved"
        assert remedy["status"] == "implemented"
        assert (tmp_path / remedy["remedy_spec_path"]).is_file()

    screen = json.loads((tmp_path / ".state/family-screen.json").read_text())
    assert screen["status"] == "pass"
    assert screen["benchmark_whole_slug"] == "pass"
    assert screen["prompt_boundary"] == "pass"

    bst.verify_core(tmp_path)
    for root in roots:
        remedy = json.loads((tmp_path / ".state/remedy" / f"{root.name}.json").read_text())
        assert remedy["primary_core_objective"] == "achieved"
        assert remedy["primary_core_evidence"]["verified_by"] == "verify_core"


def test_bst_v2_reference_files_make_a_whole_file_sft_answer(tmp_path: Path) -> None:
    root = bst.build(tmp_path)[0]
    task = moonlight_aider_task_sft.load_task(root)
    answer = moonlight_aider_task_sft.build_assistant_response(
        task, moonlight_aider_task_sft.load_example_files_from_config(root)
    )
    assert answer.startswith(f"{root.name}.h\n```")
    assert f"{root.name}.cpp\n```" in answer
    assert ".meta/example" not in answer
    applied = parse_whole_file_blocks(answer)
    assert applied == {
        f"{root.name}.h": (root / ".meta/example.h").read_text(),
        f"{root.name}.cpp": (root / ".meta/example.cpp").read_text(),
    }
    for malformed in (
        f"{root.name}.h\n```cpp\nx\n```",
        "CMakeLists.txt\n```cmake\nx\n```",
    ):
        parsed = parse_whole_file_blocks(malformed)
        assert set(parsed) != set(load_task(root).editable_files)
    with pytest.raises(WholeFormatError, match="duplicate"):
        parse_whole_file_blocks(f"{root.name}.h\n```cpp\nx\n```\n{root.name}.h\n```cpp\ny\n```")
    with pytest.raises(WholeFormatError, match="unsafe filename"):
        parse_whole_file_blocks("../escape.cpp\n```cpp\nx\n```")


def test_bst_v2_owner_refuses_legacy_output() -> None:
    with pytest.raises(ValueError, match="preserved legacy"):
        bst.build(bst.LEGACY_ROOT, force=True)
