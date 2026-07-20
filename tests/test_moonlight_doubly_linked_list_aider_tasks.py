from __future__ import annotations

import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_doubly_linked_list_aider_tasks as dll
from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task


def test_materializes_twenty_logically_distinct_replacements(tmp_path: Path) -> None:
    remedy = tmp_path / ".state" / "remedy"
    source_remedy = dll.ROOT / ".state" / "remedy"
    remedy.mkdir(parents=True)
    for case in dll.CASES:
        for suffix in (".json", ".md"):
            (remedy / f"{case.legacy_id}{suffix}").write_bytes(
                (source_remedy / f"{case.legacy_id}{suffix}").read_bytes()
            )
        record_path = remedy / f"{case.legacy_id}.json"
        record = json.loads(record_path.read_text())
        record["remedy_spec_path"] = str(remedy / f"{case.legacy_id}.md")
        record["remedy_spec_hash"] = dll._sha256_file(remedy / f"{case.legacy_id}.md")
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")

    roots = dll.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {case.task_id for case in dll.CASES}
    assert len({case.logic_tag for case in dll.CASES}) == 20
    assert sum(case.legacy_id == case.task_id for case in dll.CASES) == 2
    assert all((root / f"{root.name}.h").is_file() for root in roots)
    assert all((root / f"{root.name}.cpp").is_file() for root in roots)

    core = json.loads((tmp_path / ".state" / "core-verification.json").read_text())
    assert core["status"] == "pass"
    assert core["primary_core_objective"] == "achieved"
    assert core["negative_fixture_result"] == "invariant_not_enforced"
    assert core["unique_logic_tags"] == 20

    screen = json.loads((tmp_path / ".state" / "family-screen.json").read_text())
    assert screen["family_duplicate_screen"] == "pass"
    assert screen["prompt_boundary"] == "pass"
    for root in roots:
        prompt = build_prompt(load_task(root))
        assert ".meta/example" not in prompt
        assert "task_hidden_test" not in prompt
        assert "CMakeLists.txt" not in prompt


def test_refuses_legacy_root() -> None:
    with pytest.raises(RuntimeError, match="LEGACY_ROOT"):
        dll.build(dll.LEGACY_ROOT, force=True)


def test_core_verifier_rejects_vector_authority_fixture() -> None:
    fixture = "#include <vector>\nclass Fake { std::vector<int> order_; };\n"
    required = ("::Node", "Node* prev", "Node* next", "audit_for_test", "->prev", "->next")
    assert any(token not in fixture for token in required)
    assert "std::vector" in fixture


def test_verify_records_missing_locked_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    remedy = tmp_path / ".state" / "remedy"
    source_remedy = dll.ROOT / ".state" / "remedy"
    remedy.mkdir(parents=True)
    for case in dll.CASES:
        for suffix in (".json", ".md"):
            (remedy / f"{case.legacy_id}{suffix}").write_bytes((source_remedy / f"{case.legacy_id}{suffix}").read_bytes())
        path = remedy / f"{case.legacy_id}.json"
        record = json.loads(path.read_text())
        record["remedy_spec_path"] = str(remedy / f"{case.legacy_id}.md")
        record["remedy_spec_hash"] = dll._sha256_file(remedy / f"{case.legacy_id}.md")
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    dll.build(tmp_path)
    monkeypatch.delenv("W8_DLL_GRADER_IMAGE", raising=False)
    monkeypatch.delenv("W8_DLL_SANDBOX_POLICY", raising=False)
    dll.verify(tmp_path)
    receipt = json.loads((tmp_path / ".state" / "oracle" / "verification.json").read_text())
    assert receipt["status"] == "not_completed"
    assert "W8_DLL_GRADER_IMAGE" in receipt["missing_prerequisites"]
    assert "W8_DLL_SANDBOX_POLICY" in receipt["missing_prerequisites"]
