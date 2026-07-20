from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_trie_aider_task_materializer as tasks
from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task


_CLONE_ARTIFACTS = (
    ".docs/instructions.md",
    ".meta/example.cpp",
    ".meta/task_hidden_test.cpp",
    ".meta/hard_rule_test.cpp",
    "task_visible_test.cpp",
)


def _planned_family(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    legacy = tmp_path / "legacy"
    out = tmp_path / "reverify"
    monkeypatch.setattr(tasks, "LEGACY_ROOT", legacy)
    remedy = out / ".state" / "remedy"
    remedy.mkdir(parents=True)
    headings = (
        "Identity", "Objective", "Public API", "Behavior table",
        "Implementation invariant", "Starter and reference", "Tests",
        "Files and metadata", "Build/oracle", "Family/contamination",
        "Optional dataset handoff", "Acceptance",
    )
    for case in tasks.CASES:
        root = legacy / case.legacy_id
        root.mkdir(parents=True)
        (root / "legacy.txt").write_text(case.legacy_id + "\n")
        spec = remedy / f"{case.legacy_id}.md"
        spec.write_text(
            "\n\n".join(f"## {heading}\n{case.task_id}" for heading in headings)
            + "\n"
        )
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": case.legacy_id,
            "replacement_task_id": case.task_id,
            "family_id_before": "aider-dsa-trie-v1",
            "family_id_after": tasks.FAMILY_ID,
            "tree_hash_before": tasks._tree_hash(root),
            "generator_path": tasks.OWNER_PATHS[1],
            "generator_revision": "fixture-before",
            "finding_ids": ["TRIE-F1"],
            "disposition": "replace",
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": str(spec),
            "remedy_spec_hash": tasks._file_hash(spec),
            "selected_prompt": tasks.PROMPT,
            "status": "planned",
        }
        (remedy / f"{case.legacy_id}.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n"
        )
    benchmark = tmp_path / "benchmark.json"
    holdout = tmp_path / "holdouts"
    holdout_ids = [f"official-{index:02d}" for index in range(26)]
    benchmark.write_text(json.dumps({"task_ids": holdout_ids}) + "\n")
    for index, task_id in enumerate(holdout_ids):
        root = holdout / task_id
        root.mkdir(parents=True)
        (root / "instructions.md").write_text(
            f"Official arithmetic holdout number {index} computes scalar checksums.\n"
        )
    monkeypatch.setattr(tasks, "BENCHMARK_MANIFEST", benchmark)
    monkeypatch.setattr(tasks, "UPSTREAM_HOLDOUT_ROOT", holdout)
    monkeypatch.setattr(tasks, "FALLBACK_HOLDOUT_ROOT", holdout)
    return out


def test_materializes_twenty_distinct_trie_replacements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _planned_family(tmp_path, monkeypatch)
    roots = tasks.build(out)
    assert len(roots) == 20
    assert len({case.task_id for case in tasks.CASES}) == 20
    assert len({case.objective for case in tasks.CASES}) == 20
    assert {root.name for root in roots} == {
        case.task_id for case in tasks.CASES
    }
    core = tasks.verify_core(out)
    assert core["status"] == "pass"
    assert core["pair_count"] == 190
    assert core["primary_core_objective"] == "achieved"
    assert len(core["hard_diversity_pair_decisions"]) == 190
    assert core["hard_diversity_dimensions"] == list(tasks._DIVERSITY_PATHS)
    assert core["hard_rule_root_bounds"] == [15, 20]
    for case in tasks.CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta" / "config.json").read_text())
        assert config["files"]["solution"] == [
            f"{case.task_id}.h", f"{case.task_id}.cpp"
        ]
        assert (root / ".meta" / "negative_fixture.cpp").is_file()
        assert (root / ".meta" / "hard_rule_test.cpp").is_file()
        prompt = build_prompt(load_task(root))
        assert case.task_id + ".h" in prompt
        assert ".meta/example" not in prompt
        assert "task_hidden_test" not in prompt
        assert "hard_rule_test" not in prompt
        assert "CMakeLists.txt" not in prompt


def test_refuses_to_regenerate_legacy_root() -> None:
    with pytest.raises(RuntimeError, match="LEGACY_ROOT"):
        tasks.build(tasks.LEGACY_ROOT, force=True)


def test_core_rejects_missing_trie_mechanism(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _planned_family(tmp_path, monkeypatch)
    tasks.build(out)
    case = tasks.CASES[0]
    reference = out / case.task_id / ".meta" / "example.cpp"
    reference.write_text(reference.read_text().replace(case.required_tokens[0], "removed"))
    with pytest.raises(RuntimeError, match="invariant_not_enforced"):
        tasks.verify_core(out)


def _install_identifier_renamed_clone(
    out: Path, left: tasks.Case, right: tasks.Case
) -> Path:
    left_root, right_root = out / left.task_id, out / right.task_id
    replacements = (
        (left.task_id, right.task_id),
        (left.class_name, right.class_name),
        (left.legacy_id, right.legacy_id),
        (left.objective, right.objective),
    )
    for relative in _CLONE_ARTIFACTS:
        text = (left_root / relative).read_text()
        for before, after in replacements:
            text = text.replace(before, after)
        (right_root / relative).write_text(text)
    header = (left_root / f"{left.task_id}.h").read_text()
    for before, after in replacements:
        header = header.replace(before, after)
    (right_root / f"{right.task_id}.h").write_text(header)
    return right_root


def test_family_screen_rejects_an_identifier_renamed_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _planned_family(tmp_path, monkeypatch)
    tasks.build(out)
    left, right = tasks.CASES[:2]
    _install_identifier_renamed_clone(out, left, right)
    with pytest.raises(RuntimeError, match="duplicate_family"):
        tasks._screen(out)


def test_family_screen_rejects_a_constants_or_policy_only_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _planned_family(tmp_path, monkeypatch)
    tasks.build(out)
    left, right = tasks.CASES[:2]
    right_root = _install_identifier_renamed_clone(out, left, right)
    for relative in (*_CLONE_ARTIFACTS, f"{right.task_id}.h"):
        path = right_root / relative
        text = re.sub(r"\b\d+\b", "777", path.read_text())
        text = text.replace("return false", "return true")
        path.write_text(text)
    with pytest.raises(RuntimeError, match="duplicate_family"):
        tasks._screen(out)


def test_family_screen_rejects_an_opposite_end_selection_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _planned_family(tmp_path, monkeypatch)
    tasks.build(out)
    left, right = tasks.CASES[:2]
    right_root = _install_identifier_renamed_clone(out, left, right)
    reference = right_root / ".meta" / "example.cpp"
    reference.write_text(
        reference.read_text().replace(
            "return out;", "std::reverse(out.begin(),out.end());return out;", 1
        )
    )
    with pytest.raises(RuntimeError, match="duplicate_family"):
        tasks._screen(out)


def test_count_bounds_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _planned_family(tmp_path, monkeypatch)
    monkeypatch.setattr(tasks, "CASES", tasks.CASES[:14])
    with pytest.raises(RuntimeError, match="hard-rule root count"):
        tasks.build(out)


def test_negative_fixtures_are_topic_specific_executed_substitutes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _planned_family(tmp_path, monkeypatch)
    tasks.build(out)
    names: set[str] = set()
    for case in tasks.CASES:
        profile = tasks.NEGATIVE_PROFILES[case.task_id]
        fixture = (
            out / case.task_id / ".meta" / "negative_fixture.cpp"
        ).read_text()
        names.add(profile.name)
        assert profile.declaration in fixture
        assert profile.mutation in fixture
        assert "return {false" in fixture
    assert len(names) == 20
