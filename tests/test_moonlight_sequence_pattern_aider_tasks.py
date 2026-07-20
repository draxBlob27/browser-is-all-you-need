from __future__ import annotations

import dataclasses
import hashlib
import inspect
import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_sequence_pattern_aider_tasks as tasks


def _semantic_clone(
    target: tasks.SequenceCase,
    source: tasks.SequenceCase,
    **overrides: str,
) -> tasks.SequenceCase:
    fields = {
        "title": source.title,
        "objective": source.objective,
        "instructions": source.instructions,
        "header": source.header,
        "reference": source.reference,
        "visible_test": source.visible_test,
        "hidden_test": source.hidden_test,
    }
    fields.update(overrides)
    return dataclasses.replace(target, **fields)


def test_materializes_twenty_distinct_replacements(tmp_path: Path) -> None:
    roots = tasks.build(tmp_path)
    assert len(roots) == 20
    assert len({case.profile for case in tasks.CASES}) == 20
    assert len({case.public_api for case in tasks.CASES}) == 20
    assert {root.name for root in roots} == {case.task_id for case in tasks.CASES}
    assert all(case.task_id != case.legacy_id for case in tasks.CASES)
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert config["files"]["test"] == [
            "task_visible_test.cpp", ".meta/task_hidden_test.cpp", ".meta/negative.cpp"
        ]
        assert provenance["family_id"] == tasks.FAMILY_ID
        assert provenance["legacy_task_id"].startswith("seq-")
        assert (root / ".meta/negative.cpp").is_file()


def test_core_verifier_checks_every_pair_prompt_roles_and_holdouts(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    manifest = tasks.verify_core(tmp_path, require_remedy=False)
    assert manifest["task_count"] == 20
    assert manifest["screen"]["prompt_boundary"] == "pass"
    assert manifest["screen"]["reference_mapping"] == "pass"
    assert manifest["screen"]["negative_fixtures"].startswith("pass:20")
    family_screen = manifest["screen"]["duplicate_family"]
    assert family_screen["root_count"] == 20
    assert family_screen["minimum_roots"] == 20
    assert family_screen["maximum_roots"] == 20
    assert family_screen["comparison_scope"] == "all_unordered_pairs"
    assert family_screen["pair_count"] == 190
    assert family_screen["evidence_fields"] == [
        "emitted_introduction",
        "emitted_instructions",
        "public_api",
        "reference_source",
        "visible_tests",
        "private_tests",
    ]
    assert manifest["screen"]["benchmark_contamination"]["holdout_root_count"] == 26
    assert manifest["screen"]["benchmark_contamination"]["comparisons"] == 520
    assert len({row["semantic_signature"] for row in manifest["tasks"]}) == 20
    assert all(row["primary_core_objective"] == "achieved" for row in manifest["tasks"])


def test_duplicate_family_control_rejects_renamed_clone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = tasks.CASES[:2]
    replacements = {
        "AuditEventMatcher": "TelemetryRecordMatcher",
        "AuditEvent": "TelemetryRecord",
        "AuditSpan": "TelemetrySpan",
        "Audit": "Telemetry",
        "Event": "Record",
        "audit-event": "telemetry-record",
        "audit": "telemetry",
        "event": "record",
        "stream": "feed",
        "signature": "template",
        "code": "signal",
        "severity": "level",
    }

    def renamed(value: str) -> str:
        for old, new in replacements.items():
            value = value.replace(old, new)
        return value

    clone = _semantic_clone(
        second,
        first,
        title=renamed(first.title),
        objective=renamed(first.objective),
        instructions=renamed(first.instructions),
        header=renamed(first.header),
        reference=renamed(first.reference),
        visible_test=renamed(first.visible_test),
        hidden_test=renamed(first.hidden_test),
    )
    monkeypatch.setattr(tasks, "CASES", (first, clone, *tasks.CASES[2:]))
    tasks.build(tmp_path)
    with pytest.raises(RuntimeError, match="duplicate_family"):
        tasks._family_screen(tmp_path)


def test_duplicate_family_control_rejects_constants_only_clone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = tasks.CASES[:2]
    clone = _semantic_clone(
        second,
        first,
        reference=(
            first.reference
            .replace('severity<0', 'severity<-7')
            .replace('{"a",1', '{"a",7')
            .replace('{"b",2', '{"b",9')
        ),
        visible_test=(
            first.visible_test
            .replace('{"a",1', '{"a",7')
            .replace('{"b",2', '{"b",9')
        ),
        hidden_test=(
            first.hidden_test
            .replace('{"a",1', '{"a",7')
            .replace('{"b",2', '{"b",9')
            .replace('severity=9', 'severity=11')
        ),
    )
    monkeypatch.setattr(tasks, "CASES", (first, clone, *tasks.CASES[2:]))
    tasks.build(tmp_path)
    with pytest.raises(RuntimeError, match="duplicate_family"):
        tasks._family_screen(tmp_path)


def test_duplicate_family_control_rejects_opposite_selection_clone(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second, source = tasks.CASES[:3]
    clone = _semantic_clone(
        second,
        source,
        instructions=source.instructions.replace("lower priority", "higher priority"),
        reference=source.reference.replace("std::min_element", "std::max_element"),
        visible_test=source.visible_test.replace('"safer"', '"danger"'),
        hidden_test=source.hidden_test.replace('"suffix"', '"long"'),
    )
    monkeypatch.setattr(tasks, "CASES", (first, clone, *tasks.CASES[2:]))
    tasks.build(tmp_path)
    with pytest.raises(RuntimeError, match="duplicate_family"):
        tasks._family_screen(tmp_path)


def test_family_screen_fails_closed_outside_twenty_root_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tasks, "CASES", tasks.CASES[:-1])
    tasks.build(tmp_path)
    with pytest.raises(RuntimeError, match="family_count_out_of_bounds"):
        tasks._family_screen(tmp_path)

    extra = dataclasses.replace(
        tasks.TASKS[0],
        legacy_id="seq-extra-hard-rule-control",
        task_id="extra-hard-rule-control-v2",
        profile="extra-hard-rule-control",
    )
    monkeypatch.setattr(tasks, "CASES", (*tasks.TASKS, extra))
    tasks.build(tmp_path)
    with pytest.raises(RuntimeError, match="family_count_out_of_bounds"):
        tasks._family_screen(tmp_path)


def test_missing_primary_marker_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = dataclasses.replace(tasks.CASES[0], marker="marker-that-is-not-present")
    monkeypatch.setattr(tasks, "CASES", (bad, *tasks.CASES[1:]))
    tasks.build(tmp_path)
    with pytest.raises(RuntimeError, match="invariant_not_enforced"):
        tasks.verify_core(tmp_path, require_remedy=False)


def test_whole_file_answers_expose_only_editable_files(tmp_path: Path) -> None:
    fence = "`" * 3
    for root in tasks.build(tmp_path):
        task = moonlight_aider_task_sft.load_task(root)
        answer = moonlight_aider_task_sft.build_assistant_response(
            task, moonlight_aider_task_sft.load_example_files_from_config(root)
        )
        assert answer.startswith(f"{root.name}.h\n{fence}")
        assert f"{root.name}.cpp\n{fence}" in answer
        assert ".meta/example" not in answer


def test_planned_remedies_bind_all_legacy_roots() -> None:
    remedy = tasks.DEFAULT_OUT / ".state/remedy"
    records = sorted(remedy.glob("*.json"))
    assert len(records) == 20
    assert {path.stem for path in records} == {case.legacy_id for case in tasks.CASES}
    for path in records:
        record = json.loads(path.read_text())
        spec = remedy / f"{path.stem}.md"
        assert record["disposition"] == "replace"
        assert record["optional_dataset_handoff"] == "not_requested"
        assert record["remedy_spec_hash"] == f"sha256:{hashlib.sha256(spec.read_bytes()).hexdigest()}"


def test_verifier_owns_explicit_normal_sanitizer_and_discovery_contract() -> None:
    source = inspect.getsource(tasks.verify)
    assert '"Unix Makefiles"' in source
    assert "-fsanitize=address,undefined" in source
    assert "sanitizer_test_count_mismatch" in source
    assert '!= 3' in source
    assert "ctest" in source


def test_wrapper_targets_parallel_reverify_tree() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_sequence_pattern_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_sequence_pattern_aider_tasks" in content
    assert "aider-tasks-reverify/aider-dsa/sequence-pattern" in content
