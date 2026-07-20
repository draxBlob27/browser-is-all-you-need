from __future__ import annotations

import dataclasses
import inspect
import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_robot_simulation_aider_tasks as robot


def test_materializes_twenty_algorithmically_distinct_replacements(tmp_path: Path) -> None:
    roots = robot.build(tmp_path)
    assert len(roots) == 20
    assert len({case.profile for case in robot.CASES}) == 20
    assert len({case.public_api for case in robot.CASES}) == 20
    assert {root.name for root in roots} == {case.task_id for case in robot.CASES}
    assert all(case.task_id != case.legacy_id for case in robot.CASES)
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["family_id"] == robot.FAMILY_ID
        assert provenance["semantic_profile"]
        assert provenance["legacy_task_id"].startswith("sim-")
        assert (root / ".meta/task_hidden_test.cpp").is_file()


def test_core_verifier_checks_prompt_roles_drift_and_semantic_screens(tmp_path: Path) -> None:
    robot.build(tmp_path)
    robot.verify_core(tmp_path, require_remedy=False)
    manifest = json.loads((tmp_path / ".state/materialization-manifest.json").read_text())
    assert manifest["task_count"] == 20
    assert len({row["semantic_signature"] for row in manifest["tasks"]}) == 20
    assert manifest["screen"]["benchmark_contamination"] == "pass"
    assert manifest["screen"]["duplicate_family"] == "pass"
    assert manifest["screen"]["negative_fixture"] == "pass:legacy-template-clone"
    assert manifest["screen"]["prompt_boundary"] == "pass"
    assert manifest["screen"]["reference_mapping"] == "pass"
    assert manifest["screen"]["semantic_holdout"]["status"] == "pass"
    assert manifest["screen"]["semantic_holdout"]["holdout_root_count"] == 26
    contaminated = tmp_path / "contaminated"
    contaminated.mkdir()
    (contaminated / "copied.txt").write_text("grade-school")
    with pytest.raises(RuntimeError, match="benchmark_id_overlap"):
        robot._benchmark_screen(contaminated)


def test_legacy_template_clone_is_a_failing_negative_fixture(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = dataclasses.replace(
        robot.CASES[0],
        reference="MoveForward TurnClockwise TurnCounterClockwise",
        marker="MoveForward",
    )
    monkeypatch.setattr(robot, "CASES", (bad, *robot.CASES[1:]))
    with pytest.raises(RuntimeError, match="duplicate_family.*legacy-template-clone"):
        robot._semantic_signatures()


def test_references_make_strict_whole_file_answers(tmp_path: Path) -> None:
    fence = chr(96) * 3
    for root in robot.build(tmp_path):
        task = moonlight_aider_task_sft.load_task(root)
        answer = moonlight_aider_task_sft.build_assistant_response(
            task, moonlight_aider_task_sft.load_example_files_from_config(root)
        )
        assert answer.startswith(f"{root.name}.h\n{fence}")
        assert f"{root.name}.cpp\n{fence}" in answer
        assert ".meta/example" not in answer


def test_verifier_owns_fresh_normal_and_sanitizer_contract() -> None:
    source = inspect.getsource(robot.verify)
    assert '"Unix Makefiles"' in source
    assert "-fsanitize=address,undefined" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "ctest" in source


def test_robot_wrapper_targets_parallel_reverify_tree() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_robot_simulation_aider_tasks.sh")
    assert wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_robot_simulation_aider_tasks" in content
    assert "aider-tasks-reverify/aider-dsa/robot-simulation" in content
