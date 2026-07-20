from __future__ import annotations

import inspect
import json
from pathlib import Path

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_sliding_window_maximum_aider_tasks as sliding


def test_materializes_twenty_distinct_replacements(tmp_path: Path) -> None:
    roots = sliding.build(tmp_path)
    assert len(roots) == 20
    assert len({case.profile for case in sliding.CASES}) == 20
    assert len({case.public_api for case in sliding.CASES}) == 20
    assert {root.name for root in roots} == {case.task_id for case in sliding.CASES}
    assert all(case.task_id != case.legacy_id for case in sliding.CASES)
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["family_id"] == sliding.FAMILY_ID
        assert provenance["semantic_profile"]
        assert (root / ".meta/task_hidden_test.cpp").is_file()
        assert (root / ".meta/negative_fixture.cpp").is_file()
        assert ".meta/negative_fixture.cpp" not in {
            *config["files"]["solution"],
            *config["files"]["test"],
            *config["files"]["example"],
        }
        remedy = json.loads((tmp_path / ".state/remedy" / f"{root.name}.json").read_text())
        assert remedy["disposition"] == "replace"
        assert remedy["tree_hash_before"].startswith("sha256:")


def test_core_verifier_checks_roles_regeneration_and_screens(tmp_path: Path) -> None:
    sliding.build(tmp_path)
    sliding.verify_core(tmp_path)
    manifest = json.loads((tmp_path / ".state/materialization-manifest.json").read_text())
    assert manifest["task_count"] == 20
    assert len({row["semantic_signature"] for row in manifest["tasks"]}) == 20
    assert manifest["screen"]["prompt_boundary"] == "pass"
    assert manifest["screen"]["reference_mapping"] == "pass"
    assert manifest["screen"]["duplicate_family"] == "pass"
    assert manifest["screen"]["artifact_family"]["pair_count"] == 190
    assert len(manifest["screen"]["artifact_family"]["pair_evidence"]) == 190
    assert all(
        len(row["differing_dimensions"]) == 7
        for row in manifest["screen"]["artifact_family"]["pair_evidence"]
    )
    assert manifest["screen"]["artifact_family"][
        "negative_fixtures_excluded_from_similarity"
    ]
    assert manifest["screen"]["artifact_family"]["comparison_scope"].startswith("emitted docs")
    assert manifest["screen"]["benchmark_contamination"] == "pass"
    assert manifest["screen"]["semantic_holdout"]["holdout_root_count"] == 26
    assert manifest["status"] == "pending_execution"
    assert manifest["screen"]["compiled_negative_fixtures"] == "pending_docker_execution"
    assert set(manifest["screen"]["emitted_adversarial_controls"]) == {
        "renamed-domain-clone",
        "constants-policy-clone",
        "opposite-end-clone",
        "missing-mechanism-token",
    }


def test_all_pair_duplicate_screen_rejects_emitted_adversarial_clones(tmp_path: Path) -> None:
    sliding.build(tmp_path)
    outcomes = sliding._run_adversarial_controls(tmp_path)
    for name in ("renamed-domain-clone", "constants-policy-clone", "opposite-end-clone"):
        assert outcomes[name] == "rejected:duplicate_family:emitted_artifacts"


def test_missing_mechanism_token_is_rejected() -> None:
    assert "never_present_token" not in sliding.CASES[0].reference


def test_every_root_has_one_compiling_negative_plan_and_stateful_traces(tmp_path: Path) -> None:
    sliding.build(tmp_path)
    assert set(sliding.NEGATIVE_MUTATIONS) == {case.task_id for case in sliding.CASES}
    assert set(sliding.TRACE_SNIPPETS) == set(sliding.TRACE_OPERATION_TOKENS)
    for case in sliding.CASES:
        source = (tmp_path / case.task_id / ".meta/negative_fixture.cpp").read_text()
        reference = (tmp_path / case.task_id / ".meta/example.cpp").read_text()
        assert source != reference
        if case.task_id in sliding.TRACE_SNIPPETS:
            hidden = (tmp_path / case.task_id / ".meta/task_hidden_test.cpp").read_text()
            assert f"hard_rule_trace:{case.task_id}" in hidden
            assert all(token in hidden for token in sliding.TRACE_OPERATION_TOKENS[case.task_id])


def test_references_make_strict_whole_file_answers(tmp_path: Path) -> None:
    fence = "`" * 3
    for root in sliding.build(tmp_path):
        task = moonlight_aider_task_sft.load_task(root)
        answer = moonlight_aider_task_sft.build_assistant_response(
            task, moonlight_aider_task_sft.load_example_files_from_config(root)
        )
        assert answer.startswith(f"{root.name}.h\n{fence}")
        assert f"{root.name}.cpp\n{fence}" in answer
        assert ".meta/example" not in answer


def test_docker_verifier_owns_locked_shape_and_archive_binding() -> None:
    source = inspect.getsource(sliding.verify_docker)
    assert '"--network"' in source and '"none"' in source
    assert '"Unix Makefiles"' in source
    assert "-fsanitize=address,undefined" in source
    assert "grader_mount_hash_mismatch" in source
    assert "grader_mount_tree_hash_mismatch" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "negative_fixture_not_rejected" in source
    assert "compiler_hash" in source


def test_wrapper_targets_parallel_reverify_tree() -> None:
    wrapper = Path(
        "examples/slime/moonlight_cpp_perf/prepare_sliding_window_maximum_aider_tasks.sh"
    )
    assert wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_sliding_window_maximum_aider_tasks" in content
    assert "aider-tasks-reverify/aider-dsa/sliding-window-maximum" in content
