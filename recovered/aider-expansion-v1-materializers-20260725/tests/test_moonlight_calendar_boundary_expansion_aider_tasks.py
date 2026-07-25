from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_calendar_boundary_expansion_aider_tasks as family


def test_binding_inventory_and_mechanisms_are_exact() -> None:
    assert len(family.TASKS) == 90
    assert len({case.task_id for case in family.TASKS}) == 90
    assert [case.api_kind for case in family.TASKS].count("metric") == 30
    assert [case.api_kind for case in family.TASKS].count("transform") == 30
    assert [case.api_kind for case in family.TASKS].count("series") == 30
    assert len({case.mechanism for case in family.TASKS}) == 90
    assert family.HARD_RULE_DIMENSIONS == (
        "public_api",
        "owned_state_or_algorithm",
        "mutation_selection_rules",
        "invalid_boundary_behavior",
        "reference_control_flow",
        "deterministic_oracle",
        "topic_negative_fixture",
    )


def test_expansion_owner_refuses_existing_trees() -> None:
    for forbidden in (family.LEGACY_ROOT, family.REVERIFY_ROOT):
        with pytest.raises(family.VerificationError, match="unsafe_output_root"):
            family._safe_output(forbidden)


def test_every_negative_is_distinguished_by_private_oracle() -> None:
    for case in family.TASKS:
        assert family._expected(case, hidden=True) != family._expected(
            family._negative_case(case), hidden=True
        ), case.task_id


def test_materialization_roles_names_and_provenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    expansion = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1"
    out = expansion / "time-date/calendar-difference-leap-month-end"
    monkeypatch.setattr(family, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(family, "LEGACY_ROOT", tmp_path / "legacy")
    monkeypatch.setattr(family, "REVERIFY_ROOT", tmp_path / "reverify")
    result = family.materialize(out)
    assert result["tasks"] == 90
    roots = sorted(path for path in out.iterdir() if path.is_dir() and path.name != ".state")
    assert len(roots) == 90
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert not set(config["files"]["solution"]) & set(config["files"]["test"])
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert provenance["lineage"] == "new-root"
        assert provenance["generator"] == family.OWNER
        assert provenance["status"] == "local candidate; not dataset admission"
        assert "CORE_BEGIN" in (root / ".meta/example.cpp").read_text()
        assert "CORE_BEGIN" in (root / ".meta/negative_false_substitute.cpp").read_text()
        assert "Observable rule:" in (root / ".docs/instructions.md").read_text()
        behavior = json.loads((root / ".meta/behavior-signature.json").read_text())
        assert behavior["probe_policy"] == "calendar-boundary-observable-v2"
        assert behavior["signature"].startswith("sha256:")
        cmake = (root / "CMakeLists.txt").read_text()
        assert "target_include_directories(solution PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})" in cmake
        assert "target_include_directories(negative_test PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})" in cmake
    selected = json.loads((out / ".state/selected-manifest.json").read_text())
    assert selected["requested_count"] == selected["retained_count"] == 90
    assert len(selected["tasks"]) == 90
    rejected = json.loads((out / ".state/rejected-proposals.json").read_text())
    assert {item["proposal_id"] for item in rejected["rejected"]} == {
        "control-domain-rename",
        "control-policy-only",
        "control-opposite-end",
    }
    stale_receipt = out / ".state/receipts/replaced-root.json"
    family._write(stale_receipt, "{}\n")
    family.materialize(out, force=True)
    assert not (out / ".state/receipts").exists()


def test_pair_evaluator_records_seven_independent_decisions(tmp_path: Path) -> None:
    left = tmp_path / family.TASKS[0].task_id
    right = tmp_path / family.TASKS[1].task_id
    for case, root in ((family.TASKS[0], left), (family.TASKS[1], right)):
        for relative, content in family._task_files(case).items():
            family._write(root / relative, content)
    decision = family._pair_decision(left, right)
    assert set(decision["dimensions"]) == set(family.HARD_RULE_DIMENSIONS)
    for evidence in decision["dimensions"].values():
        assert set(evidence) == {
            "overlap",
            "symmetric_difference",
            "left_sequence",
            "right_sequence",
            "distinct",
        }
        assert isinstance(evidence["distinct"], bool)
    assert decision["observable_behavior"]["distinct"]


def test_complete_pair_matrix_and_adversarial_controls(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    expansion = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1"
    out = expansion / "time-date/calendar-difference-leap-month-end"
    monkeypatch.setattr(family, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(family, "LEGACY_ROOT", tmp_path / "legacy")
    monkeypatch.setattr(family, "REVERIFY_ROOT", tmp_path / "reverify")
    family.materialize(out)
    roots = [out / case.task_id for case in family.TASKS]
    decisions = [
        family._pair_decision(left, right)
        for index, left in enumerate(roots)
        for right in roots[index + 1 :]
    ]
    assert len(decisions) == 4005
    assert all(decision["pass"] for decision in decisions)
    assert all(decision["observable_behavior"]["distinct"] for decision in decisions)
    controls = {
        "domain-identifier-renamed": 0,
        "constants-or-policy-only": 0,
        "opposite-end-selection": 0,
    }
    for name, operation in controls.items():
        control = family._render_control(out, name, operation)
        assert not family._pair_decision(roots[0], control)["pass"]
        assert "CORE_BEGIN" in (control / ".meta/example.cpp").read_text()


def test_boundary_oracles_cover_upper_range_and_series_contract() -> None:
    for case in family.TASKS:
        behavior = family._behavior_signature(case)
        assert behavior["records"]
        if case.api_kind == "series":
            for values in behavior["records"]:
                if values is None:
                    continue
                assert values == sorted(set(values))
    next_boundary = next(case for case in family.TASKS if case.task_id == "monthend-next-boundary")
    assert family._safe_transform_value(next_boundary.operation, family.date(9999, 12, 31), 1) is None
    pairs = next(case for case in family.TASKS if case.task_id == "leapseries-capacity-change-pairs")
    values = family._series_value(pairs.operation, family.date(2023, 12, 15), family.date(2024, 5, 20), 1)
    assert values is not None
    assert all(family.date(2023, 12, 15) <= value <= family.date(2024, 5, 20) for value in values)
    for task_id in ("leapseries-clamped-monthly-anchor", "leapseries-rolled-monthly-anchor"):
        case = next(case for case in family.TASKS if case.task_id == task_id)
        assert family._series_value(case.operation, family.date(1900, 2, 28), family.date(1900, 3, 2), 0) is None
    fiscal = next(case for case in family.TASKS if case.task_id == "leapseries-fiscal-end-partition")
    for parameter in (0, 13):
        assert family._series_value(fiscal.operation, family.date(1900, 1, 1), family.date(1900, 12, 31), parameter) is None
    for task_id in ("monthend-add-years-clamped", "monthend-add-years-march-shift"):
        case = next(case for case in family.TASKS if case.task_id == task_id)
        for parameter in (-(2**31), 2**31 - 1):
            assert family._safe_transform_value(case.operation, family.date(2000, 2, 29), parameter) is None
    checkpoints = next(case for case in family.TASKS if case.task_id == "leapseries-calendar-cycle-checkpoints")
    assert family._series_value(checkpoints.operation, family.date(1900, 2, 28), family.date(1900, 3, 2), 1) == [family.date(1900, 2, 28)]
    assert family._series_value(checkpoints.operation, family.date(2000, 2, 28), family.date(2000, 3, 2), 1) == [family.date(2000, 2, 29)]


def test_replacement_prompts_have_date_valued_boundary_notes() -> None:
    stale_phrases = (
        "encodes the positive length",
        "encodes one maximal consecutive run",
        "allocation vector",
        "encodes the positive ordinal gap",
    )
    for task_id in (
        "leapseries-month-fragment-origins",
        "leapseries-leap-status-run-starts",
        "leapseries-quarter-start-partition",
        "leapseries-leap-gap-midpoints",
    ):
        case = next(case for case in family.TASKS if case.task_id == task_id)
        prompt = family._instructions(case)
        assert not any(phrase in prompt for phrase in stale_phrases)


def test_anchor_clamp_oracles_match_documented_semantics() -> None:
    monthly = next(case for case in family.TASKS if case.task_id == "leapseries-clamped-monthly-anchor")
    assert family._series_value(
        monthly.operation, family.date(2023, 12, 15), family.date(2024, 3, 31), 31
    ) == [
        family.date(2023, 12, 31),
        family.date(2024, 1, 31),
        family.date(2024, 2, 29),
        family.date(2024, 3, 31),
    ]
    quarterly = next(case for case in family.TASKS if case.task_id == "leapseries-quarterly-anchor")
    assert family._series_value(
        quarterly.operation, family.date(2024, 1, 31), family.date(2024, 12, 31), 1
    ) == [family.date(2024, 4, 30), family.date(2024, 7, 31), family.date(2024, 10, 31)]
    rolled = next(case for case in family.TASKS if case.task_id == "leapseries-rolled-monthly-anchor")
    assert family._series_value(
        rolled.operation, family.date(9999, 12, 15), family.date(9999, 12, 31), 32
    ) == []


def test_anchor_reference_cores_implement_documented_clamp_semantics() -> None:
    monthly_core = family.SERIES_CORES[6]
    assert "for(Date m={a.year,a.month,1}" in monthly_core
    assert "d=add_months_clamped(d,1)" not in monthly_core
    quarterly_core = family.SERIES_CORES[9]
    assert "add_months_clamped(a,3*k)" in quarterly_core
    assert "d=add_months_clamped(d,3)" not in quarterly_core
    assert "clamping the day of `first` to each target month's capacity" in family.SERIES_PUBLIC_RULES[9]
    for task_id, marker in (
        ("leapseries-clamped-monthly-anchor", "{2023,12,15},{2024,3,31},31"),
        ("leapseries-rolled-monthly-anchor", "{9999,12,15},{9999,12,31},32"),
        ("leapseries-quarterly-anchor", "{2024,1,31},{2024,12,31},1"),
    ):
        case = next(case for case in family.TASKS if case.task_id == task_id)
        files = family._task_files(case)
        assert marker in files["task_visible_test.cpp"].replace(" ", "")
        assert marker in files[".meta/task_hidden_test.cpp"].replace(" ", "")


def test_host_verify_entry_point_is_available() -> None:
    assert callable(family.verify_host)
    assert family.HOST_VERIFY_POLICY == "host-normal-plus-fresh-asan-ubsan-v1"


def test_prompt_builder_exposes_only_docs_and_solution(tmp_path: Path) -> None:
    case = family.TASKS[0]
    root = tmp_path / case.task_id
    for relative, content in family._task_files(case).items():
        family._write(root / relative, content)
    prompt = family.build_prompt(family.load_task(root))
    for name in (f"{case.task_id}.h", f"{case.task_id}.cpp"):
        assert name in prompt
    for private in (
        "CMakeLists.txt",
        "provenance.json",
        "example.cpp",
        "task_hidden_test",
        "negative_false",
    ):
        assert private not in prompt


def test_docs_follow_benchmark_register(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    expansion = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1"
    out = expansion / "time-date/calendar-difference-leap-month-end"
    monkeypatch.setattr(family, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(family, "LEGACY_ROOT", tmp_path / "legacy")
    monkeypatch.setattr(family, "REVERIFY_ROOT", tmp_path / "reverify")
    family.materialize(out)
    banned = re.compile(
        r"clean-room|\bthis task\b|\bSFT\b|benchmark|campaign|remediation|oracle\b"
        r"|negative fixture|reference implementation|generator|adversarial"
        r"|hard rule|forbidden substitute|do not substitute|grader|hidden test"
        r"|local_family_verified|prompt|\bmodel\b|core mechanism|executable properties",
        re.IGNORECASE,
    )
    for case in family.TASKS:
        root = out / case.task_id
        assert not (root / ".docs/introduction.md").exists()
        instructions = (root / ".docs/instructions.md").read_text()
        assert instructions.startswith("# Instructions\n")
        assert "## Example\n" in instructions
        assert "Observable rule:" in instructions
        assert case.mechanism in instructions
        assert not banned.search(instructions)
