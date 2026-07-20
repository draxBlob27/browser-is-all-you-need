from __future__ import annotations

import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_xor_linked_list_aider_tasks as xor
from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task


def _copy_plans(out: Path) -> None:
    target = out / ".state" / "remedy"
    source = xor.ROOT / ".state" / "remedy"
    target.mkdir(parents=True)
    for case in xor.LEGACY_CASES:
        for suffix in (".json", ".md"):
            (target / f"{case.legacy_id}{suffix}").write_bytes(
                (source / f"{case.legacy_id}{suffix}").read_bytes()
            )
        record_path = target / f"{case.legacy_id}.json"
        record = json.loads(record_path.read_text())
        record["remedy_spec_path"] = str(target / f"{case.legacy_id}.md")
        record["remedy_spec_hash"] = xor._sha256_file(target / f"{case.legacy_id}.md")
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


def test_materializes_hard_rule_counted_xor_replacements(tmp_path: Path) -> None:
    _copy_plans(tmp_path)
    roots = xor.build(tmp_path)

    assert len(roots) == 17
    assert xor.MIN_COUNT <= len(roots) <= xor.MAX_COUNT
    assert {root.name for root in roots} == {case.task_id for case in xor.CASES}
    assert len({case.logic_tag for case in xor.CASES}) == 17
    assert sum(case.legacy_id == case.task_id for case in xor.CASES) == 1
    assert all((root / f"{root.name}.h").is_file() for root in roots)
    assert all((root / f"{root.name}.cpp").is_file() for root in roots)
    assert all((root / ".meta/task_trace_test.cpp").is_file() for root in roots)
    assert all((root / ".meta/negative.cpp").is_file() for root in roots)
    assert all((root / ".meta/negative.cpp").read_bytes() != (root / ".meta/example.cpp").read_bytes() for root in roots)
    for case in xor.REJECTED_CASES:
        assert not (tmp_path / case.task_id).exists()
        record = json.loads((tmp_path / ".state/remedy" / f"{case.legacy_id}.json").read_text())
        assert record["status"] == "rejected"
        assert record["local_status"] == "rejected_hard_rule"
        assert record["replacement_task_id"] is None

    core = json.loads((tmp_path / ".state/core-verification.json").read_text())
    assert core["status"] == "pending_execution"
    assert core["primary_core_objective"] == "achieved"
    assert core["compiled_negative_fixtures"] == "pending_execution"
    assert core["unique_logic_tags"] == 17
    assert core["hard_rule_pair_count"] == 136

    screen = json.loads((tmp_path / ".state/family-screen.json").read_text())
    assert screen["family_duplicate_screen"] == "pass"
    assert screen["hard_rule_pair_count"] == 136
    assert screen["count_bounds"] == {"actual": 17, "maximum": 20, "minimum": 15}
    assert screen["adversarial_controls"] == {
        "constants_policy_only_clone": "duplicate_family",
        "domain_identifier_renamed_clone": "duplicate_family",
        "opposite_end_selection_clone": "duplicate_family",
    }
    assert screen["prompt_boundary"] == "pass"
    assert len(screen["benchmark_inventory"]) == 26
    for root in roots:
        prompt = build_prompt(load_task(root))
        assert ".meta/example" not in prompt
        assert "task_hidden_test" not in prompt
        assert "CMakeLists.txt" not in prompt
        assert "SlotId" in prompt
        assert "previous_slot XOR next_slot" in prompt

    exemplar = xor._hard_material(roots[0], roots[0].name)
    for control in (
        "domain_identifier_renamed_clone",
        "constants_policy_only_clone",
        "opposite_end_selection_clone",
    ):
        with pytest.raises(RuntimeError, match="duplicate_family"):
            xor.assert_hard_rule_pair(roots[0].name, control, exemplar, xor.adversarial_variant(exemplar, control))


def test_refuses_legacy_root() -> None:
    with pytest.raises(RuntimeError, match="LEGACY_ROOT"):
        xor.build(xor.LEGACY_ROOT, force=True)


def test_core_verifier_rejects_banned_xor_representations() -> None:
    with pytest.raises(RuntimeError, match="invariant_not_enforced"):
        xor._validate_reference("class Fake { std::vector<int> order_; };", "vector_authority_fixture")
    with pytest.raises(RuntimeError, match="invariant_not_enforced"):
        xor._validate_reference(
            "auto bits = reinterpret_cast<unsigned long>(pointer);",
            "raw_pointer_xor_fixture",
        )


def test_verify_records_missing_locked_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _copy_plans(tmp_path)
    xor.build(tmp_path)
    monkeypatch.setattr(xor.shutil, "which", lambda name: "/usr/bin/c++" if name == "c++" else None)
    monkeypatch.delenv("W8_XOR_GRADER_IMAGE", raising=False)
    monkeypatch.delenv("W8_XOR_SANDBOX_POLICY", raising=False)
    xor.verify(tmp_path)
    receipt = json.loads((tmp_path / ".state/oracle/verification.json").read_text())
    assert receipt["status"] == "not_completed"
    assert "cmake" in receipt["missing_prerequisites"]
    assert "ctest" in receipt["missing_prerequisites"]
    assert "W8_XOR_GRADER_IMAGE" in receipt["missing_prerequisites"]
    assert "W8_XOR_SANDBOX_POLICY" in receipt["missing_prerequisites"]


def test_wrapper_targets_reverify_tree_and_is_executable() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_xor_linked_list_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    text = wrapper.read_text()
    assert "moonlight_xor_linked_list_aider_tasks" in text
    assert "aider-tasks-reverify/aider-dsa/xor-linked-list" in text
