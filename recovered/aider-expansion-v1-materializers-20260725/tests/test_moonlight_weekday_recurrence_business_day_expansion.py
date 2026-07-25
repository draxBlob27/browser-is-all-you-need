from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from w8_biayn.integrations import (
    moonlight_weekday_recurrence_business_day_expansion as calendar,
)


def _sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    expansion = tmp_path / "aider-tasks-expansion-v1"
    monkeypatch.setattr(calendar, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(calendar, "LEGACY_ROOT", tmp_path / "legacy")
    monkeypatch.setattr(calendar, "REVERIFY_ROOT", tmp_path / "reverify")
    out = expansion / "time-date/weekday-recurrence-business-day"
    return out


def test_exact_90_root_count_and_operation_balance(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    roots = calendar.build(out)
    assert len(roots) == 90
    assert len({root.name for root in roots}) == 90
    assert len(calendar.OPERATIONS) == 30
    assert {group: sum(case.group == group for case in calendar.CASES) for group in calendar.GROUPS} == {
        "weekday": 30,
        "recurrence": 30,
        "business-day": 30,
    }
    assert all(root.parent == out for root in roots)
    assert not any(".state" in root.parts for root in roots)


def test_generated_roles_references_and_negatives_are_complete(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    for case, root in zip(calendar.CASES, calendar.build(out), strict=True):
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["lineage"] == "new-root"
        assert provenance["mechanism"] == case.operation.mechanism
        assert set(provenance["semantic_profile"]) == set(calendar.HARD_DIMENSIONS)
        reference = (root / ".meta/example.cpp").read_text()
        negative = (root / ".meta/negative_false_substitute.cpp").read_text()
        absence_negative = (root / ".meta/negative_nonempty_absence.cpp").read_text()
        assert reference != negative
        assert reference != absence_negative
        assert "blocked.count(days[i])==0U" in reference
        assert "return !(" in negative
        assert "return std::vector<int>{100001}" in absence_negative
        assert (out / ".state/remedy/cycle-02" / f"{case.task_id}.md").is_file()
        remedy = json.loads(
            (out / ".state/remedy/cycle-02" / f"{case.task_id}.json").read_text()
        )
        assert remedy["finding_ids"] == [f"WRBD-AUD-{index:03d}" for index in range(1, 11)]
        instructions = (root / ".docs/instructions.md").read_text()
        assert "Visible example:" in instructions
        assert "[-100000,100000]" in instructions
        assert calendar.OPERATION_CONTRACTS[case.ordinal % len(calendar.OPERATIONS)] in instructions
        hidden = (root / ".meta/task_hidden_test.cpp").read_text()
        assert "*absent_result!=absent_expected" in hidden
        if case.group == "recurrence":
            assert "anchor_outside_low" in hidden and "anchor_outside_high" in hidden
            assert "primary` anchor in `[-100000,100000]" in instructions
            assert "static_cast<long long>(day)-request.primary" in reference


def test_oracle_guarantees_each_negative_changes_visible_or_hidden_result() -> None:
    for case in calendar.CASES:
        changed = False
        for hidden in (False, True):
            days, exclusions, primary, interval, parameter = calendar._request_values(case, hidden)
            good = calendar._operation_oracle(
                case.ordinal % len(calendar.OPERATIONS),
                days,
                exclusions,
                primary,
                interval,
                parameter,
                case.group,
            )
            bad = calendar._operation_oracle(
                case.ordinal % len(calendar.OPERATIONS),
                days,
                exclusions,
                primary,
                interval,
                parameter,
                case.group,
                invert_rule=True,
            )
            changed = changed or good != bad
        assert changed, case.task_id


def test_all_4005_pairs_pass_each_dimension_and_controls_are_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    calendar.build(out)
    screen = calendar._semantic_screen(out)
    assert screen["root_count"] == 90
    assert screen["pair_count"] == screen["expected_pair_count"] == 4005
    assert tuple(screen["dimensions"]) == calendar.HARD_DIMENSIONS
    seen = set()
    for pair in screen["pairs"]:
        seen.add((pair["left"], pair["right"]))
        assert set(pair["decisions"]) == set(calendar.HARD_DIMENSIONS)
        assert all(pair["decisions"].values())
    assert len(seen) == 4005
    assert set(screen["controls"]) == {
        "domain-identifier-renamed",
        "constants-policy-only",
        "opposite-end-selection",
    }
    for control in screen["controls"].values():
        assert control["production_rejected"] is True
        assert not any(control["decisions"].values())
        assert all(value == 1.0 for value in control["similarities"].values())
    control_manifest = json.loads(
        (out / ".state/adversarial-clone-controls/manifest.json").read_text()
    )
    base = out / control_manifest["base_task_id"]
    for name, record in control_manifest["controls"].items():
        control_root = out / ".state/adversarial-clone-controls" / name
        changed = []
        for path in sorted(item for item in control_root.rglob("*") if item.is_file()):
            relative = path.relative_to(control_root)
            counterpart = base / relative
            if not counterpart.is_file() or counterpart.read_bytes() != path.read_bytes():
                changed.append(relative.as_posix())
        assert changed == record["changed_files"]
        cmake = (control_root / "CMakeLists.txt").read_text()
        assert f'{control_manifest["base_task_id"]}.cpp' in cmake


def test_output_guard_refuses_existing_and_non_expansion_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    calendar._validate_output(out)
    with pytest.raises(RuntimeError, match="unsafe_path"):
        calendar._validate_output(calendar.LEGACY_ROOT / "time-date/family")
    with pytest.raises(RuntimeError, match="unsafe_path"):
        calendar._validate_output(tmp_path / "outside")


def test_force_reconciliation_quarantines_only_known_owned_replaced_roots(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    stale = out / "weekday-eligible-projection"
    (stale / ".meta").mkdir(parents=True)
    (stale / ".meta/config.json").write_text("{}\n")
    (stale / ".meta/provenance.json").write_text(
        json.dumps(
            {
                "family_id": calendar.FAMILY_ID,
                "task_id": stale.name,
            }
        )
        + "\n"
    )
    (stale / "evidence.txt").write_text("preserve me\n")
    calendar.build(out, force=True)
    assert not stale.exists()
    quarantined = out / ".state/rejected/cycle-03" / stale.name
    assert (quarantined / "evidence.txt").read_text() == "preserve me\n"
    active = [
        path
        for path in out.rglob(".meta/config.json")
        if ".state" not in path.parts
    ]
    assert len(active) == 90
    ledger = json.loads(
        (out / ".state/remedy/cycle-03/replaced-roots.json").read_text()
    )
    assert ledger["replacements"][0]["replacement_task_id"] == "weekday-first-occurrence"


def test_host_verifier_binds_tree_and_requires_full_oracle_evidence() -> None:
    source = inspect.getsource(calendar.verify_host)
    helper = inspect.getsource(calendar._run_host_build)
    assert "Unix Makefiles" in helper
    assert "-fsanitize=address,undefined" in helper
    assert "ASAN_OPTIONS" in helper
    assert "negative_fixture_not_rejected" in helper
    assert "reference_sanitizer_failed" in helper
    assert "generator_output_drift" in source
    assert "sanitizer_test_count_mismatch" in source
    assert '"negative_fixture_count": 180' in source
    assert "result_ledger_hash" in source
    assert "host-verify.json" in source
    assert "campaign_verified_host_only" in source
    assert '"evidence_class": "host_verify"' in source
    assert "--verify-host" in inspect.getsource(calendar.main)


def test_host_build_executes_reference_and_rejects_negative(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    calendar.build(out)
    root = out / calendar.CASES[0].task_id
    builds = tmp_path / "builds"
    reference_row = calendar._run_host_build(
        "tasks", root, ".meta/example.cpp", "normal", builds
    )
    assert reference_row == [
        "tasks", root.name, "normal", ".meta/example.cpp", "2", "pass",
    ]
    negative_row = calendar._run_host_build(
        "tasks", root, ".meta/negative_false_substitute.cpp", "normal", builds
    )
    assert negative_row[:-1] == [
        "tasks", root.name, "normal", ".meta/negative_false_substitute.cpp", "2",
    ]
    assert negative_row[-1] == "rejected"


def test_docker_verifier_is_network_disabled_and_fresh_sanitized() -> None:
    source = inspect.getsource(calendar.verify_docker)
    assert '"--network", "none"' in source
    assert "Unix Makefiles" in inspect.getsource(calendar)
    assert "-fsanitize=address,undefined" in source
    assert "compiler.sha256" in source
    assert "grader_mount_hash_mismatch" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "negative_fixture_count" in source
    assert '"negative_fixture_count": 180' in source
    assert ".meta/negative_nonempty_absence.cpp" in source
    assert "result_ledger_hash" in source
    assert "detailed_results" in source


def test_curriculum_and_spec_bind_expansion_count_and_nonclaims() -> None:
    curriculum = calendar.CURRICULUM.read_text()
    specification = calendar.FAMILY_SPEC.read_text()
    assert "exactly 30 weekday roots, 30 recurrence roots, and 30 business-day roots" in curriculum
    assert "4,005" in curriculum and "4,005" in specification
    assert ".w8-biayn/data/aider-tasks-expansion-v1/" in curriculum
    assert "local_family_verified" in curriculum
    assert "does not" in curriculum and "training" in curriculum
