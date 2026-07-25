from __future__ import annotations

import inspect
import itertools
import json
import re
from pathlib import Path

import pytest

from w8_biayn.integrations import (
    moonlight_cross_midnight_offsets_meetings_aider_tasks as family,
)
from w8_biayn.integrations import (
    moonlight_cross_midnight_offsets_meetings_hard_rule as hard_rule,
)


def _out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    expansion = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1"
    out = expansion / "time-date/cross-midnight-offsets-meetings"
    monkeypatch.setattr(family, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(family, "DEFAULT_OUT", out)
    return out


def test_materializes_exact_10_by_9_matrix_with_safe_roles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _out(tmp_path, monkeypatch)
    roots = family.build(out, force=True)
    assert len(roots) == 90
    assert len(family.TRANSFORMS) == 10
    assert len(family.REDUCERS) == 9
    assert len({task.task_id for task in family.TASKS}) == 90
    assert len({task.lineage_id for task in family.TASKS}) == 90
    inventory = json.loads((out / ".state/source-inventory.json").read_text())
    assert inventory["reverify_sorted_root_sha256"] == family.PLAN_REVERIFY_ROOTS_SHA256
    assert inventory["count_plan_reverify_sorted_root_sha256"] == family.PLAN_REVERIFY_ROOTS_SHA256
    assert inventory["expansion_roots_before"] >= inventory["owner_expansion_roots_before"]
    for task, root in zip(family.TASKS, roots, strict=True):
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{task.task_id}.h", f"{task.task_id}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["relation"] == "new-root"
        assert provenance["family_id"] == family.FAMILY_ID
        assert (out / ".state/contracts" / f"{task.task_id}.md").is_file()
        ledger = json.loads((root / ".meta/requirements.json").read_text())
        visible = (root / "task_visible_test.cpp").read_text()
        hidden = (root / ".meta/task_hidden_test.cpp").read_text()
        assert ledger["contract_hash"] == family._sha_bytes(family._instructions(task).encode())
        required = [item for item in ledger["requirements"] if item["applicability"] == "required"]
        assert required and all(item["assertions"] for item in required)
        assertion_ids = {assertion for item in required for assertion in item["assertions"]}
        assert "hidden.empty-input" in assertion_ids
        assert "hidden.input-immutability" in assertion_ids
        for assertion_id in assertion_ids:
            if assertion_id.startswith("docker."):
                continue
            assert f"W8_ASSERT:{assertion_id}" in visible + hidden
        valid, boundary_spans = family._transform_rows(
            task.transform.key,
            family._parse_rows(family._touching_tie_literal(task)),
        )
        assert valid
        assert any(
            left[2] == right[1] or right[2] == left[1]
            for left, right in itertools.combinations(boundary_spans, 2)
        )
        assert any(
            left[1:3] == right[1:3] and left[0] != right[0]
            for left, right in itertools.combinations(boundary_spans, 2)
        )
        expected_invalid_snapshots = len(family._transform_invalid_mutations(task)) + 1
        assert hidden.count("auto bad_before=bad;") == expected_invalid_snapshots
        assert hidden.count("same_input(bad,bad_before)") == expected_invalid_snapshots
        assert "W8_ASSERT:hidden.valid-inclusive-maxima" in hidden
        assert "W8_ASSERT:hidden.valid-input-size-1000" in hidden
        assert "200000000" in hidden and "1000000" in hidden
        assert f"std::vector<{task.transform.input_name}> boundary(1000" in hidden
        assert hidden.count("same_input(boundary,boundary_before)") >= 2
        omission_literal = family._valid_omission_literal(task)
        omission_requirement = next(
            item
            for item in ledger["requirements"]
            if item["requirement_id"] == "transform-valid-empty-omission"
        )
        if task.transform.key in {"clip", "participant"}:
            assert omission_literal is not None
            omission_valid, omission_spans = family._transform_rows(
                task.transform.key,
                family._parse_rows(omission_literal),
            )
            assert omission_valid and omission_spans == []
            assert omission_requirement["applicability"] == "required"
            assert omission_requirement["assertions"] == ["hidden.valid-empty-omission"]
            assert "W8_ASSERT:hidden.valid-empty-omission" in hidden
            assert "same_input(omission,omission_before)" in hidden
        else:
            assert omission_literal is None
            assert omission_requirement["applicability"].startswith("not_applicable")
            assert omission_requirement["assertions"] == []
        reference = (root / ".meta/example.cpp").read_text()
        negative = (root / ".meta/negative.cpp").read_text()
        assert f"W8_TRANSFORM:{task.transform.key}" in reference
        assert f"W8_REDUCER:{task.reducer.key}" in reference
        assert reference != negative


def test_independently_recomputes_all_4005_seven_dimension_decisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _out(tmp_path, monkeypatch)
    roots = family.build(out, force=True)
    screen = family.verify_core(out)
    hard = screen["hard_rule"]
    assert hard["root_count"] == 90
    assert hard["pair_count"] == hard["expected_pair_count"] == 4005
    assert hard["dimensions"] == list(hard_rule.HARD_DIMENSIONS)
    expected_pairs = {
        tuple(sorted((left.name, right.name)))
        for left, right in itertools.combinations(roots, 2)
    }
    actual_pairs = {
        tuple(sorted((row["left"], row["right"]))) for row in hard["pairs"]
    }
    assert actual_pairs == expected_pairs
    for row in hard["pairs"]:
        assert set(row["dimensions"]) == set(hard_rule.HARD_DIMENSIONS)
        for dimension, decision in row["dimensions"].items():
            assert decision["left_evidence_valid"]
            assert decision["right_evidence_valid"]
            assert decision["fingerprint_distinct"]
            assert decision["mechanism_profile_distinct"]
            assert decision["normalized_similarity"] < hard_rule.MAX_NORMALIZED_SIMILARITY[dimension]
            assert decision["pass"]
        assert row["pass"]


def test_controls_are_changed_coherent_and_rejected_by_production_screen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _out(tmp_path, monkeypatch)
    family.build(out, force=True)
    controls = family._control_screen(out)
    assert controls["status"] == "pass"
    assert {row["name"] for row in controls["controls"]} == set(family.CONTROL_NAMES)
    for row in controls["controls"]:
        assert row["changed"] and row["rejected"]
        assert row["comparison"]["pass"] is False
        assert any(not decision["pass"] for decision in row["comparison"]["dimensions"].values())


def test_owner_refuses_every_non_expansion_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _out(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="unsafe_expansion_output"):
        family.build(tmp_path / "aider-tasks-reverify/time-date/family", force=True)


def test_docker_verifier_binds_network_hash_sanitizer_and_negative_gates() -> None:
    source = inspect.getsource(family.docker_sanity)
    assert '"--network", "none"' in source
    assert "-fsanitize=address,undefined" in family.DOCKER_SCRIPT
    assert "W8HASH" in family.DOCKER_SCRIPT
    assert "negative_visible" in family.DOCKER_SCRIPT
    assert "sanitizer_test_count_mismatch" in source
    assert "grader_mount_hash_mismatch" in source
    assert "creator-preflight.json" in source


def test_host_verifier_binds_toolchain_counts_and_negative_gates() -> None:
    source = inspect.getsource(family.verify_host)
    helper = inspect.getsource(family._host_build_and_run)
    assert "verify_core(out)" in source
    assert "-fsanitize=address,undefined -fno-omit-frame-pointer" in helper
    assert "Unix Makefiles" in helper
    assert "negative_visible" in helper and "negative_hidden" in helper
    assert "detect_leaks=0" in helper
    assert "sanitizer_test_count_mismatch" in source
    assert "invariant_not_enforced" in source
    assert "host_toolchain_unavailable" in inspect.getsource(family._host_tool)
    assert "host-verify.json" in source
    assert '"evidence_class": "host_verify"' in source
    assert '"locked_oracle": False' in source
    assert "host_verify_failed" in source
    main_source = inspect.getsource(family.main)
    assert '"--verify-host"' in main_source
    assert "verify_host(args.out, cycle_number=args.cycle)" in main_source


def test_host_build_and_run_single_root_rejects_negative_in_both_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _out(tmp_path, monkeypatch)
    family.build(out, force=True)
    root = out / "fixed-offset-peak-load"
    compiler = family._host_tool("c++")
    builds = tmp_path / "host-builds"
    builds.mkdir()
    for mode in ("normal", "asan_ubsan"):
        outcome = family._host_build_and_run(root, builds, "tasks", mode, compiler)
        assert outcome == {"ok": True, "count": 2, "negative_rejected": True}


def test_remediation_planning_requires_real_findings_and_freezes_pre_edit_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _out(tmp_path, monkeypatch)
    family.build(out, force=True)
    family.verify_core(out)
    report = out / ".state/audits/cycle-01/audit-report.json"
    report.parent.mkdir(parents=True)
    report.write_text(json.dumps({"findings": [{"finding_id": "TIME-AUDIT-001"}]}))
    remedy = family.plan_remediation(out, report)
    payload = json.loads(remedy.read_text())
    assert payload["status"] == "planned_before_source_edit"
    assert payload["finding_ids"] == ["TIME-AUDIT-001"]
    assert payload["pre_edit_owner_hashes"] == family._owner_hashes()
    assert payload["pre_edit_family_hash"] == family._family_hash(out)
    assert remedy.with_suffix(".md").is_file()


def test_audit_subject_hash_cli_is_strictly_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out = _out(tmp_path, monkeypatch)
    family.build(out, force=True)
    family.verify_core(out)
    before = {
        path.relative_to(out).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in out.rglob("*")
        if path.is_file()
    }
    expected = family.audit_subject_hash(out)
    assert family.main(["--out", str(out), "--audit-subject-hash"]) == 0
    assert capsys.readouterr().out.strip() == expected
    after = {
        path.relative_to(out).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in out.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_curriculum_and_spec_bind_count_output_and_nonclaims() -> None:
    curriculum = family.CURRICULUM.read_text()
    spec = family.FAMILY_SPEC.read_text()
    assert "90-root" in curriculum
    assert "4,005" in curriculum
    assert ".w8-biayn/data/aider-tasks-expansion-v1/" in curriculum
    assert "local_family_verified" in curriculum
    assert "sft release" in curriculum.lower()
    assert "independent `audit-sft-data-quality`" in spec


def test_docs_follow_benchmark_register() -> None:
    banned = re.compile(
        r"clean-room|\bthis task\b|\bSFT\b|benchmark|campaign|remediation|oracle\b"
        r"|negative fixture|reference implementation|generator|adversarial"
        r"|hard rule|forbidden substitute|do not substitute|grader|hidden test"
        r"|local_family_verified|prompt|\bmodel\b|core mechanism",
        re.IGNORECASE,
    )
    for task in family.TASKS:
        instructions = family._instructions(task)
        assert instructions.startswith("# Instructions\n")
        assert "## Example\n" in instructions
        assert f"`{task.function_name}`" in instructions
        assert f"`{task.task_id}.h`" in instructions
        assert not banned.search(instructions)
        example = family._example_block(task)
        assert "returns a report with `valid == true`" in example
