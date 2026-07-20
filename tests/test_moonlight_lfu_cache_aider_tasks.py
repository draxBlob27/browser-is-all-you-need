from __future__ import annotations

import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_lfu_cache_aider_tasks as lfu
from w8_biayn.integrations.moonlight_lfu_cache_cases import (
    DIVERSITY_PROFILES,
    NEGATIVES,
    ORACLE_TESTS,
    REFERENCES,
    REJECTED,
    TASKS,
)


def _bind_fake_holdouts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path.parent / f"{tmp_path.name}-holdouts"
    for index, slug in enumerate(sorted(lfu.OFFICIAL_AIDER_CPP_HOLDOUTS)):
        task = root / slug
        task.mkdir(parents=True)
        (task / "instructions.md").write_text(f"independent holdout {index}\n")
        (task / "exercise.cpp").write_text(f"int holdout_{index}(){{return {index};}}\n")
    monkeypatch.setattr(lfu, "HOLDOUT_ROOT", root)


def test_lfu_v3_materializes_fifteen_and_rejects_five_duplicates(tmp_path: Path) -> None:
    roots = lfu.build(tmp_path)
    assert len(roots) == 15
    assert len(REJECTED) == 5
    assert {root.name for root in roots} == {spec.task_id for spec in TASKS}
    assert {spec.legacy_id for spec in TASKS} | set(REJECTED) == {
        path.name for path in lfu.LEGACY_OUT.iterdir() if path.is_dir()
    }
    assert len({spec.api for spec in TASKS}) == 15
    for dimension in range(7):
        assert len({profile[dimension] for profile in DIVERSITY_PROFILES.values()}) == 15
    for spec in TASKS:
        root = tmp_path / spec.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{spec.task_id}.h", f"{spec.task_id}.cpp"]
        assert provenance["task_spec_revision"] == 3
        assert provenance["legacy_task_id"] == spec.legacy_id
        assert (root / ".meta/negative.cpp").is_file()
        assert NEGATIVES[spec.mode] != REFERENCES[spec.mode]
        assert "check(" in ORACLE_TESTS[spec.mode]


def test_lfu_v3_core_prompt_family_and_holdout_screens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind_fake_holdouts(tmp_path, monkeypatch)
    lfu.build(tmp_path)
    lfu.verify_core(tmp_path)
    manifest = json.loads((tmp_path / ".state/materialization-manifest.json").read_text())
    assert manifest["audited_legacy_count"] == 20
    assert manifest["task_count"] == 15
    assert len(manifest["rejected"]) == 5
    assert manifest["status"] == "semantically_admitted_pending_docker"
    assert all(row["primary_core_objective"] == "achieved" for row in manifest["tasks"])
    assert len(json.loads((tmp_path / ".state/semantic-screen.json").read_text())["holdout_inventory"]) == 26
    first = TASKS[0]
    root = tmp_path / first.task_id
    task = moonlight_aider_task_sft.load_task(root)
    answer = moonlight_aider_task_sft.build_assistant_response(
        task, moonlight_aider_task_sft.load_example_files_from_config(root)
    )
    assert answer.startswith(f"{first.task_id}.h\n```")
    assert ".meta/example" not in answer


def test_lfu_v3_rejects_actual_normalized_duplicate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bind_fake_holdouts(tmp_path, monkeypatch)
    lfu.build(tmp_path)
    original = lfu._semantic_corpus

    def duplicate_second(root: Path, *, candidate: bool) -> str:
        if candidate and root.name == TASKS[1].task_id:
            return original(tmp_path / TASKS[0].task_id, candidate=True)
        return original(root, candidate=candidate)

    monkeypatch.setattr(lfu, "_semantic_corpus", duplicate_second)
    with pytest.raises(RuntimeError, match="duplicate_family"):
        lfu._semantic_screen(tmp_path)


def test_lfu_v3_remedies_account_for_rejections(tmp_path: Path) -> None:
    lfu.build(tmp_path)
    lfu._verify_remedies(tmp_path)
    records = [json.loads(path.read_text()) for path in (tmp_path / ".state/remedy").glob("*.json")]
    assert len(records) == 20
    assert sum(row["disposition"] == "replace" for row in records) == 15
    assert sum(row["disposition"] == "reject" for row in records) == 5


def test_lfu_wrapper_targets_only_reverify_root() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_lfu_cache_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    text = wrapper.read_text()
    assert "moonlight_lfu_cache_aider_tasks" in text
    assert "aider-tasks-reverify/aider-dsa/lfu-cache" in text
