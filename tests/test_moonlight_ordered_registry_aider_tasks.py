from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_ordered_registry_aider_tasks as tasks
from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task


def test_materializes_twenty_hard_diversity_profiles_and_private_traces(tmp_path: Path) -> None:
    roots = tasks.build(tmp_path)
    assert len(roots) == 20
    assert len({case.task_id for case in tasks.CASES}) == 20
    assert len({case.class_name for case in tasks.CASES}) == 20
    assert len({case.objective for case in tasks.CASES}) == 20
    assert len({case.core_markers for case in tasks.CASES}) == 20
    profiles = {
        (
            tasks.VERIFICATION_CASES[case.task_id].logic,
            tasks.VERIFICATION_CASES[case.task_id].state,
            tasks.VERIFICATION_CASES[case.task_id].mutation,
            tasks.VERIFICATION_CASES[case.task_id].selection,
            tasks.VERIFICATION_CASES[case.task_id].boundary,
        )
        for case in tasks.CASES
    }
    assert len(profiles) == 20
    assert {root.name for root in roots} == {case.task_id for case in tasks.CASES}

    reference_hashes: set[str] = set()
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        reference = (root / ".meta/example.cpp").read_text()
        negative = (root / ".meta/negative_fixture.cpp").read_text()
        trace = (root / ".meta/task_trace_test.cpp").read_text()
        assert "group_limit_" not in reference
        assert "struct Entry { int id; std::string group; int rank; int stamp;" not in reference
        reference_hashes.add(tasks._sha(reference.encode()))
        assert negative != reference
        assert "auto audit" in trace
        prompt = build_prompt(load_task(root))
        assert ".meta/example" not in prompt
        assert "task_hidden_test" not in prompt
        assert "CMakeLists.txt" not in prompt
    assert len(reference_hashes) == 20


def test_core_screen_binds_each_compilable_topic_negative_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tasks.build(tmp_path)
    monkeypatch.setattr(tasks, "_screen_benchmarks", lambda _out: {"status": "pass", "holdouts_screened": 26})
    tasks.verify_core(tmp_path, require_remedy=False)
    for case in tasks.CASES:
        root = tmp_path / case.task_id
        source = (root / ".meta/example.h").read_text() + (root / ".meta/example.cpp").read_text()
        assert tasks._core_failure(case, source) is None
        assert (root / ".meta/negative_fixture.cpp").read_text() == tasks._rendered_negative_source(case)
        assert (root / ".meta/negative_fixture.json").read_text()
        legacy = source + "struct Entry { int id; std::string group; int rank; int stamp; };"
        assert tasks._core_failure(case, legacy) == "invariant_not_enforced"


def test_model_traces_cover_every_public_operation_class() -> None:
    for case in tasks.CASES:
        public = case.header.split("public:", 1)[1].split("private:", 1)[0]
        methods = {
            match.group(1)
            for match in re.finditer(r"\b([A-Za-z_][A-Za-z_0-9]*)\s*\([^;{}]*\)\s*(?:const)?\s*;", public)
            if match.group(1) != case.class_name
        }
        trace = tasks.VERIFICATION_CASES[case.task_id].trace
        assert methods
        assert all(re.search(rf"\b{re.escape(method)}\s*\(", trace) for method in methods), (case.task_id, methods)


def test_semantic_screen_rejects_renamed_logic_and_implementation_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    source = tasks.CASES[0]
    target = tasks.CASES[1]
    renamed = replace(
        source,
        legacy_id=target.legacy_id,
        task_id=target.task_id,
        title="Different nouns",
        class_name="RenamedRegistry",
        objective="Different words and constants",
        header=source.header.replace(source.class_name, "RenamedRegistry"),
        starter=source.starter.replace(source.class_name, "RenamedRegistry"),
        reference=source.reference.replace(source.class_name, "RenamedRegistry"),
        visible=source.visible.replace(source.class_name, "RenamedRegistry"),
        hidden=source.hidden.replace(source.class_name, "RenamedRegistry"),
    )
    source_verification = tasks.VERIFICATION_CASES[source.task_id]
    target_verification = tasks.VERIFICATION_CASES[target.task_id]
    monkeypatch.setitem(
        tasks.VERIFICATION_CASES,
        target.task_id,
        replace(target_verification, trace=source_verification.trace.replace(source.class_name, "RenamedRegistry")),
    )
    family = (source, renamed, *tasks.CASES[2:])
    with pytest.raises(RuntimeError, match="duplicate_family"):
        tasks._screen_family(family)


def test_build_never_mutates_legacy_family(tmp_path: Path) -> None:
    before = {case.legacy_id: tasks._tree_hash(tasks.LEGACY_ROOT / case.legacy_id) for case in tasks.CASES}
    tasks.build(tmp_path)
    after = {case.legacy_id: tasks._tree_hash(tasks.LEGACY_ROOT / case.legacy_id) for case in tasks.CASES}
    assert after == before


def test_wrapper_defaults_to_reverify_root_and_core_mode_is_exposed() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_ordered_registry_aider_tasks.sh")
    assert wrapper.stat().st_mode & 0o111
    text = wrapper.read_text()
    assert "aider-tasks-reverify/aider-dsa/ordered-registry" in text
    assert "moonlight_ordered_registry_aider_tasks" in text
    assert "--verify-core" in Path("src/w8_biayn/integrations/moonlight_ordered_registry_aider_tasks.py").read_text()
