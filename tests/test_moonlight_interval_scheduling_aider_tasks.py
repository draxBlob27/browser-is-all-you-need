from __future__ import annotations

import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_interval_scheduling_aider_tasks as interval
from w8_biayn.integrations.moonlight_interval_scheduling_cases import REFERENCES, TASKS
from w8_biayn.integrations.moonlight_interval_scheduling_negatives import (
    DIVERSITY_PROFILES,
    NEGATIVES,
    ORACLE_TESTS,
)


def _bind_fake_holdouts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    holdouts = tmp_path.parent / f"{tmp_path.name}-holdouts"
    for index, slug in enumerate(sorted(interval.OFFICIAL_AIDER_CPP_HOLDOUTS)):
        root = holdouts / slug
        root.mkdir(parents=True)
        (root / "instructions.md").write_text(f"independent holdout {index}\n")
        (root / "exercise.cpp").write_text(f"int holdout_{index}() {{ return {index}; }}\n")
    monkeypatch.setattr(interval, "HOLDOUT_ROOT", holdouts)


def test_interval_v2_materializes_twenty_logic_diverse_replacements(
    tmp_path: Path,
) -> None:
    roots = interval.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {spec.task_id for spec in TASKS}
    assert len({spec.mode for spec in TASKS}) == len(TASKS)
    assert len({spec.api for spec in TASKS}) == len(TASKS)
    assert {spec.legacy_id for spec in TASKS} == {
        path.name for path in interval.LEGACY_ROOT.iterdir() if path.is_dir()
    }
    for spec in TASKS:
        root = tmp_path / spec.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [
            f"{spec.task_id}.h",
            f"{spec.task_id}.cpp",
        ]
        assert config["files"]["example"] == [
            ".meta/example.h",
            ".meta/example.cpp",
        ]
        assert provenance["legacy_task_id"] == spec.legacy_id
        assert provenance["task_spec_revision"] == 2
        assert NEGATIVES[spec.mode] != REFERENCES[spec.mode]
        assert (root / ".meta/negative.cpp").is_file()
        assert (root / ".meta/task_oracle_test.cpp").is_file()


def test_interval_v2_prompt_core_duplicate_and_benchmark_screens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_fake_holdouts(tmp_path, monkeypatch)
    interval.build(tmp_path)
    interval.verify_core(tmp_path, require_remedy=False)
    first = TASKS[0]
    root = tmp_path / first.task_id
    task = moonlight_aider_task_sft.load_task(root)
    answer = moonlight_aider_task_sft.build_assistant_response(
        task, moonlight_aider_task_sft.load_example_files_from_config(root)
    )
    assert answer.startswith(f"{first.task_id}.h\n```")
    assert ".meta/example" not in answer
    manifest = json.loads((tmp_path / ".state/materialization-manifest.json").read_text())
    assert manifest["task_count"] == 20
    assert manifest["screen"] == {
        "benchmark_contamination": "pass",
        "duplicate_family": "pass",
        "negative_fixture": "pending_execution",
        "prompt_boundary": "pass",
        "reference_mapping": "pass",
    }
    assert all(row["primary_core_objective"] == "achieved" for row in manifest["tasks"])
    assert all(row["negative_fixture"] for row in manifest["tasks"])
    assert (
        len(json.loads((tmp_path / ".state/semantic-screen.json").read_text())["holdout_inventory"])
        == 26
    )


def test_interval_v2_core_screen_rejects_normalized_duplicate_control_flow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_fake_holdouts(tmp_path, monkeypatch)
    interval.build(tmp_path)
    original = interval._semantic_corpus

    def duplicate_second(root: Path, *, candidate: bool) -> str:
        if candidate and root.name == TASKS[1].task_id:
            return original(tmp_path / TASKS[0].task_id, candidate=True)
        return original(root, candidate=candidate)

    monkeypatch.setattr(interval, "_semantic_corpus", duplicate_second)
    with pytest.raises(RuntimeError, match="duplicate_family"):
        interval._semantic_screen(tmp_path)


def test_interval_v2_has_per_root_executable_discriminators_and_state_oracle() -> None:
    assert set(NEGATIVES) == {spec.mode for spec in TASKS}
    assert set(ORACLE_TESTS) == {spec.mode for spec in TASKS}
    assert set(DIVERSITY_PROFILES) == {spec.mode for spec in TASKS}
    assert all(
        len({profile[dimension] for profile in DIVERSITY_PROFILES.values()}) == 20
        for dimension in range(4)
    )
    assert all("check(" in source for source in ORACLE_TESTS.values())
    ledger = ORACLE_TESTS["ordered_mutable_calendar"]
    assert "std::vector<CLASS::Booking> model" in ledger
    assert ledger.count("x.agenda()==agenda()") >= 6


def test_interval_v2_wrapper_targets_only_reverify_root() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_interval_scheduling_aider_tasks.sh")
    text = wrapper.read_text()
    assert wrapper.stat().st_mode & 0o111
    assert "aider-tasks-reverify/aider-dsa/interval-scheduling" in text
    assert "moonlight_interval_scheduling_aider_tasks" in text
