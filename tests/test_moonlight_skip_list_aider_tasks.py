from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_skip_list_aider_tasks as tasks
from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task


def _copy_remedies(destination: Path) -> None:
    target = destination / ".state/remedy"
    target.mkdir(parents=True)
    source = tasks.ROOT / ".state/remedy"
    for case in tasks.CASES:
        markdown = target / f"{case.legacy_id}.md"
        markdown.write_bytes((source / f"{case.legacy_id}.md").read_bytes())
        record = json.loads((source / f"{case.legacy_id}.json").read_text())
        record["remedy_spec_path"] = str(markdown)
        record["remedy_spec_hash"] = "sha256:" + hashlib.sha256(markdown.read_bytes()).hexdigest()
        record["status"] = "planned"
        (target / f"{case.legacy_id}.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n"
        )


def test_materializes_distinct_replacements_and_screens_every_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _copy_remedies(tmp_path)
    roots = tasks.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {case.task_id for case in tasks.CASES}
    assert len({case.mechanism for case in tasks.CASES}) == 20
    assert sum(case.legacy_id == case.task_id for case in tasks.CASES) == 1

    for case, root in zip(tasks.CASES, roots, strict=True):
        assert (root / f"{case.task_id}.h").is_file()
        assert (root / f"{case.task_id}.cpp").is_file()
        prompt = build_prompt(load_task(root))
        assert f"{case.task_id}.h" in prompt
        assert f"{case.task_id}.cpp" in prompt
        assert ".meta/example" not in prompt
        assert "task_hidden_test" not in prompt
        assert "CMakeLists.txt" not in prompt
        assert "SORTED_VECTOR_AUTHORITY" not in prompt
        negative = (root / ".meta/negative_topic_specific.cpp").read_text()
        assert negative == tasks._rendered_negative_source(case)
        assert negative != case.reference
        assert tasks._reject_substitute(case.header + negative, case) is None

    core = json.loads((tmp_path / ".state/core-verification.json").read_text())
    assert core["status"] == "pass"
    assert core["primary_core_objective"] == "achieved"
    assert core["unique_mechanisms"] == 20
    assert core["negative_fixture_execution"] == "pending_docker"
    assert len(core["negative_fixture_inventory"]) == 20

    screen = json.loads((tmp_path / ".state/family-screen.json").read_text())
    assert screen["candidate_pairs"] == 190
    assert len(screen["pair_decisions"]) == 190
    assert all(row["decision"] == "distinct" for row in screen["pair_decisions"])
    assert all(
        set(row["scores"]) == set(tasks.DIVERSITY_LIMITS)
        for row in screen["pair_decisions"]
    )
    assert screen["holdout_comparisons"] == 520
    assert screen["family_duplicate_screen"] == "pass"
    assert screen["benchmark_screen"] == "pass"
    assert all(
        control["decision"] == "duplicate_family"
        and control["source"] == "emitted_artifact"
        and control["production_pair_evaluator"] is True
        for control in screen["adversarial_controls"].values()
    )

    monkeypatch.setattr(tasks.shutil, "which", lambda _: None)
    receipt = tasks.verify(tmp_path)
    assert receipt["status"] == "not_completed"
    assert "docker CLI" in receipt["missing_prerequisites"][0]


def test_refuses_to_regenerate_legacy_tree() -> None:
    with pytest.raises(RuntimeError, match="LEGACY_ROOT"):
        tasks.build(tasks.LEGACY_ROOT, force=True)


def test_substitute_screen_rejects_sorted_vector_authority() -> None:
    case = tasks.CASES[0]
    fixture = "// SORTED_VECTOR_AUTHORITY\n#include <vector>\n"
    assert tasks._reject_substitute(fixture, case) == "invariant_not_enforced"
    assert tasks._reject_substitute(case.header + case.reference, case) is None


def test_production_screen_rejects_emitted_artifact_clones() -> None:
    case = min(tasks.CASES, key=lambda item: item.task_id)
    domain_words: set[str] = set()
    for item in tasks.CASES:
        domain_words.update(re.findall(r"[a-z]+", item.task_id + " " + item.class_name))
    controls = tasks._adversarial_clone_controls(tasks.ROOT, case, domain_words)
    assert set(controls) == {
        "domain_renamed_clone",
        "constants_policy_clone",
        "opposite_end_selection_clone",
    }
    assert all(result["decision"] == "duplicate_family" for result in controls.values())


def test_every_negative_fixture_is_named_complete_and_distinct() -> None:
    assert len({case.negative_name for case in tasks.CASES}) == 20
    sources = []
    for case in tasks.CASES:
        source = tasks._negative_source(case)
        assert "SORTED_VECTOR_AUTHORITY" not in source
        assert source.startswith('#include "task.h"')
        assert source != case.reference
        assert tasks._reject_substitute(case.header + source, case) is None
        sources.append(source)
    assert len(set(sources)) == 20


def test_remedy_dispositions_are_deterministic() -> None:
    for case in tasks.CASES:
        record = json.loads(
            (tasks.ROOT / ".state/remedy" / f"{case.legacy_id}.json").read_text()
        )
        expected = "repair-in-place" if case.legacy_id == case.task_id else "replace"
        assert record["disposition"] == expected
        assert record["replacement_task_id"] == case.task_id
