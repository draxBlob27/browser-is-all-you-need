from __future__ import annotations

import json
from pathlib import Path

from w8_biayn.integrations import moonlight_aider_task_sft as sft
from w8_biayn.integrations import moonlight_calendar_arithmetic_aider_tasks as calendar


EXPECTED_IDS = {
    "calendar-subscription-cycle",
    "calendar-harvest-plan",
    "calendar-clinic-followup",
    "calendar-inventory-expiry",
    "calendar-contract-amendment",
    "calendar-vacation-allocation",
    "calendar-maintenance-rotation",
    "calendar-licence-grace",
    "calendar-release-train",
    "calendar-lease-portfolio",
}


def test_calendar_arithmetic_materializes_v2_roles_and_private_oracles(
    tmp_path: Path,
) -> None:
    roots = calendar.build(tmp_path)
    assert 8 <= len(roots) <= 12
    assert {root.name for root in roots} == EXPECTED_IDS
    assert calendar.LEGACY_ROOT != calendar.DEFAULT_OUT
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [
            f"{root.name}.h",
            f"{root.name}.cpp",
        ]
        assert config["files"]["example"] == [
            ".meta/example.h",
            ".meta/example.cpp",
        ]
        assert provenance["family_id"] == calendar.FAMILY_ID
        assert provenance["disposition"] == "repair-in-place"
        assert (root / ".meta/task_hidden_test.cpp").is_file()
        assert (root / ".meta/task_hard_rule_test.cpp").is_file()
        assert (root / ".meta/negative_false_substitute.cpp").is_file()


def test_calendar_all_pairs_inspect_every_hard_dimension(tmp_path: Path) -> None:
    calendar.build(tmp_path)
    matrix = calendar._pair_matrix(tmp_path)
    assert matrix["root_count"] == 10
    assert matrix["pair_count"] == 45 == matrix["expected_pair_count"]
    assert tuple(matrix["dimensions"]) == calendar.HARD_RULE_DIMENSIONS
    seen: set[tuple[str, str]] = set()
    for row in matrix["pairs"]:
        pair = (str(row["left"]), str(row["right"]))
        assert pair not in seen
        seen.add(pair)
        decisions = row["dimensions"]
        assert decisions["pass"] is True
        for dimension in calendar.HARD_RULE_DIMENSIONS:
            decision = decisions[dimension]
            assert set(decision) == {"containment", "limit", "distinct"}
            assert decision["distinct"] is True
            assert decision["containment"] < decision["limit"]
    assert len(seen) == 10 * 9 // 2


def test_calendar_coherent_controls_change_build_inputs_and_fail_all_dimensions(
    tmp_path: Path,
) -> None:
    calendar.build(tmp_path)
    screen = calendar._screen_controls(tmp_path)
    assert set(screen) == {
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
    }
    for name, row in screen.items():
        assert row["base_task"] == "calendar-subscription-cycle"
        assert row["changed_files"], name
        assert ".meta/example.cpp" in row["changed_files"] or name == "constants-policy-clone"
        assert (tmp_path / ".state/hard-rule-controls" / name / "candidate.cpp").is_file()
        assert row["semantic_screen"] == "rejected:duplicate_family"
        assert set(row["failed_dimensions"]) == set(calendar.HARD_RULE_DIMENSIONS)
        for dimension in calendar.HARD_RULE_DIMENSIONS:
            assert row["dimensions"][dimension]["distinct"] is False


def test_calendar_topic_negatives_are_nonempty_and_task_specific() -> None:
    reasons: set[str] = set()
    for spec in calendar.TASKS:
        negative, reason = calendar._negative_source(spec)
        assert negative != spec.reference
        assert reason
        reasons.add(reason)
    assert len(reasons) == len(calendar.TASKS)


def test_calendar_force_invalidates_runtime_evidence_but_preserves_remedy_plan(
    tmp_path: Path,
) -> None:
    calendar.build(tmp_path)
    record_path = tmp_path / ".state/remedy/calendar-subscription-cycle.json"
    record = json.loads(record_path.read_text())
    before_hash = record["tree_hash_before"]
    remedy_hash = record["remedy_spec_hash"]
    record.update(
        {
            "status": "verified",
            "tree_hash_after": "sha256:stale",
            "oracle_evidence": {"status": "pass"},
            "changed_owner_paths": ["stale"],
        }
    )
    record_path.write_text(json.dumps(record))
    state = tmp_path / ".state"
    (state / "materialization-manifest.json").write_text("{}")
    (state / "oracle-receipt.json").write_text("{}")

    calendar.build(tmp_path, force=True)

    reset = json.loads(record_path.read_text())
    assert reset["status"] == "planned"
    assert reset["benchmark_screen"] == "pending"
    assert reset["tree_hash_before"] == before_hash
    assert reset["remedy_spec_hash"] == remedy_hash
    assert "tree_hash_after" not in reset
    assert "oracle_evidence" not in reset
    assert "changed_owner_paths" not in reset
    assert not (state / "materialization-manifest.json").exists()
    assert not (state / "oracle-receipt.json").exists()
    assert (state / "invalidated-evidence.json").is_file()


def test_calendar_references_make_exact_whole_file_answers(tmp_path: Path) -> None:
    root = calendar.build(tmp_path)[0]
    task = sft.load_task(root)
    answer = sft.build_assistant_response(
        task, sft.load_example_files_from_config(root)
    )
    assert answer.startswith(f"{root.name}.h\n```")
    assert answer.count("```") == 4
    assert answer.count(f"{root.name}.h\n```") == 1
    assert answer.count(f"{root.name}.cpp\n```") == 1
    assert ".meta/example" not in answer


def test_calendar_planned_remedies_bind_legacy_and_user_count() -> None:
    remedy = calendar.DEFAULT_OUT / ".state/remedy"
    records = [json.loads(path.read_text()) for path in sorted(remedy.glob("*.json"))]
    assert len(records) == 10
    assert {record["task_id"] for record in records} == EXPECTED_IDS
    for record in records:
        assert record["disposition"] == "repair-in-place"
        assert record["tree_hash_before"] == calendar._tree_hash(
            calendar.LEGACY_ROOT / record["task_id"]
        )
        assert record["user_inputs"]["hard_rule_count"] == "8-12"
        assert record["user_inputs"]["FAMILY_TYPE"] == "aider-dates-and-clocks"


def test_calendar_wrapper_targets_only_reverify_tree() -> None:
    wrapper = Path(
        "examples/slime/moonlight_cpp_perf/prepare_calendar_arithmetic_aider_tasks.sh"
    )
    text = wrapper.read_text()
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    assert "moonlight_calendar_arithmetic_aider_tasks" in text
    assert "aider-tasks-reverify/aider-dates-and-clocks/general-calendar-arithmetic" in text


def test_calendar_audit_documents_local_only_completion() -> None:
    audit = Path(
        "docs/aider-tasks-spec/aider-dates-and-clocks/general-calendar-arithmetic.md"
    ).read_text()
    assert "45 unordered pairs" in audit
    assert "all 26 official" in audit
    assert "local_family_verified" in audit
    assert "no SFT rows" in audit
