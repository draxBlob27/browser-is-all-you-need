from __future__ import annotations
import json
from pathlib import Path
from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_flood_fill_aider_tasks as flood_fill


def test_flood_fill_curriculum_materializes_every_proposed_task(tmp_path: Path) -> None:
    roots = flood_fill.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {spec.task_id for spec in flood_fill.TASKS}
    assert len({spec.mechanism for spec in flood_fill.TASKS}) == 20
    assert len({(spec.traversal, spec.selector, spec.connectivity, spec.wrap, spec.max_cells) for spec in flood_fill.TASKS}) == 20
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert (
            provenance["curriculum_task_id"] == root.name
            and provenance["status"] == "local task artifact; not admitted SFT data"
        )
        assert provenance["family_id"] == flood_fill.FAMILY_ID
        assert provenance["legacy_task_id"].startswith("fill-")
        assert (root / ".meta/task_hidden_test.cpp").is_file()
        assert "generic-bfs-substitute" in (root / ".meta/negative_fixture.cpp").read_text()


def test_flood_fill_references_make_a_whole_file_sft_answer(tmp_path: Path) -> None:
    root = flood_fill.build(tmp_path)[0]
    task = moonlight_aider_task_sft.load_task(root)
    answer = moonlight_aider_task_sft.build_assistant_response(
        task, moonlight_aider_task_sft.load_example_files_from_config(root)
    )
    assert (
        answer.startswith(f"{root.name}.h\n```")
        and f"{root.name}.cpp\n```" in answer
        and ".meta/example" not in answer
    )


def test_flood_fill_core_verifier_checks_roles_and_semantics(tmp_path: Path) -> None:
    flood_fill.build(tmp_path)
    flood_fill.verify_core(tmp_path, require_remedy=False)
    manifest = json.loads((tmp_path / ".state/materialization-manifest.json").read_text())
    assert manifest["task_count"] == 20
    assert manifest["screen"] == {
        "primary_core_objective": "pass",
        "prompt_boundary": "pass",
        "reference_mapping": "pass",
        "duplicate_family": "pass",
        "benchmark_contamination": "pass",
        "negative_fixture": "source_validated_pending_execution",
    }
    hard = manifest["hard_diversity"]
    assert hard["pair_count"] == 190
    assert len(hard["all_pairs"]) == 190
    assert hard["maximum_pairwise_token_jaccard"] < 0.82
    assert hard["adversarial_controls"] == {
        "identifier_renamed_clone": "rejected_as_duplicate_family",
        "constants_policy_only_clone": "rejected_as_duplicate_family",
        "opposite_end_selection_clone": "rejected_as_duplicate_family",
    }
    assert len({row["reference_sha256"] for row in manifest["tasks"]}) == 20


def test_flood_fill_wrapper_targets_reverify_tree() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_flood_fill_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    assert "aider-tasks-reverify/aider-text-grid-reshaping/flood-fill" in wrapper.read_text()


def test_hard_rule_adversarial_controls_reject_required_clone_classes(tmp_path: Path) -> None:
    flood_fill.build(tmp_path)
    controls = flood_fill._hard_rule_adversarial_controls(tmp_path)
    assert set(controls) == {
        "identifier_renamed_clone",
        "constants_policy_only_clone",
        "opposite_end_selection_clone",
    }
