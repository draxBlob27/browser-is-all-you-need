from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_priority_queue_aider_tasks as priority_queue


def test_priority_queue_v2_materializes_twenty_distinct_mechanisms(tmp_path: Path) -> None:
    roots = priority_queue.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {case.task_id for case in priority_queue.CASES}
    assert len({case.mechanism for case in priority_queue.CASES}) == 20
    assert len({hashlib.sha256(case.reference.encode()).hexdigest() for case in priority_queue.CASES}) == 20
    for root in roots:
        config = json.loads((root / ".meta" / "config.json").read_text())
        provenance = json.loads((root / ".meta" / "provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["family_id"] == priority_queue.FAMILY_ID
        assert provenance["semantic_profile"] in {case.mechanism for case in priority_queue.CASES}
        assert "return false" in (root / f"{root.name}.cpp").read_text()
        assert (root / ".meta" / "task_hidden_test.cpp").is_file()


def test_priority_queue_core_validator_executes_negative_fixture_rejections() -> None:
    fixture_hashes = set()
    oracle_hashes = set()
    for case in priority_queue.CASES:
        fixture = priority_queue._negative_fixture(case)
        assert priority_queue._assert_negative_fixture_rejected(case, fixture) == "forbidden_mechanism_substitute"
        fixture_hashes.add(hashlib.sha256(fixture.encode()).hexdigest())
        oracle_hashes.add(priority_queue._validate_oracle(case))
    assert len(fixture_hashes) == 20
    assert len(oracle_hashes) == 20
    case = priority_queue.CASES[0]
    with pytest.raises(RuntimeError, match="forbidden_core_substitute"):
        priority_queue._validate_reference(case, case.reference + "\nstd::priority_queue<int> delegated;")
    with pytest.raises(RuntimeError, match="invariant_not_enforced"):
        priority_queue._validate_reference(case, case.reference.replace(case.required_tokens[0], "missing_core_token"))
    with pytest.raises(RuntimeError, match="invariant_not_enforced"):
        priority_queue._validate_reference(case, case.reference.replace(f"mechanism:{case.mechanism}", "mechanism:rename-only"))


def test_priority_queue_semantic_screen_proves_non_template_family() -> None:
    signatures, maximum = priority_queue._semantic_screen()
    assert len(signatures) == 20
    assert len(set(signatures.values())) == 20
    assert maximum < 0.86
    holdout = priority_queue._holdout_semantic_screen()
    assert holdout["status"] == "pass"
    assert holdout["holdout_count"] == 26
    assert holdout["candidate_count"] == 20
    assert holdout["strongest_overlap"]["overlap"] < 0.90


def test_priority_queue_core_verifier_checks_boundary_and_contamination(tmp_path: Path) -> None:
    priority_queue.build(tmp_path)
    priority_queue.verify_core(tmp_path, require_remedy=False)
    manifest = json.loads((tmp_path / ".state" / "materialization-manifest.json").read_text())
    assert manifest["task_count"] == 20
    assert manifest["maximum_pairwise_token_jaccard"] < 0.86
    assert manifest["screen"]["primary_core_objective"] == "pass"
    assert all(task["negative_fixture_rejection"] == "forbidden_mechanism_substitute" for task in manifest["tasks"])
    assert len({task["oracle_hash"] for task in manifest["tasks"]}) == 20
    assert manifest["holdout_semantic_screen"]["status"] == "pass"
    contaminated = tmp_path / "contaminated"
    contaminated.mkdir()
    (contaminated / "copy.txt").write_text("grade-school")
    with pytest.raises(RuntimeError, match="benchmark_id_overlap"):
        priority_queue._benchmark_screen(contaminated)


def test_priority_queue_references_make_exact_whole_file_answers(tmp_path: Path) -> None:
    root = priority_queue.build(tmp_path)[0]
    task = moonlight_aider_task_sft.load_task(root)
    answer = moonlight_aider_task_sft.build_assistant_response(
        task, moonlight_aider_task_sft.load_example_files_from_config(root)
    )
    assert answer.startswith(f"{root.name}.h\n```")
    assert f"{root.name}.cpp\n```" in answer
    assert ".meta/example" not in answer


def test_priority_queue_wrapper_targets_reverify_tree() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_priority_queue_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_priority_queue_aider_tasks" in content
    assert "aider-tasks-reverify/aider-dsa/priority-queue" in content
