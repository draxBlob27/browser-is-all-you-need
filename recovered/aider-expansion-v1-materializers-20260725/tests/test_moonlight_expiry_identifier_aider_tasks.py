from __future__ import annotations

import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_expiry_identifier_aider_tasks as expiry
from w8_biayn.integrations.moonlight_expiry_identifier_cases import CASES, PARSERS


def _out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    expansion = tmp_path / "aider-tasks-expansion-v1"
    monkeypatch.setattr(expiry, "EXPANSION_ROOT", expansion)
    return expansion / "validation-input-parsing/date-bearing-identifiers"


def test_case_inventory_is_exact_unique_cartesian_contract() -> None:
    assert len(CASES) == 90
    assert len({case.task_id for case in CASES}) == 90
    assert len({(case.parser_index, case.policy_index) for case in CASES}) == 90
    assert {case.parser_index for case in CASES} == set(range(10))
    assert {case.policy_index for case in CASES} == set(range(9))


def test_materializes_exact_roles_new_lineage_and_task_named_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _out(tmp_path, monkeypatch)
    roots = expiry.build(out, force=True)
    assert len(roots) == 90
    assert len(expiry._inventory_configs(out)) == 90
    for case, root in zip(CASES, roots, strict=True):
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [
            f"{case.task_id}.h",
            f"{case.task_id}.cpp",
        ]
        assert config["files"]["example"] == [
            ".meta/example.h",
            ".meta/example.cpp",
        ]
        assert provenance["lineage"] == {
            "relation": "new-root",
            "parent": None,
            "replacement": None,
        }
        assert provenance["parser_profile"] == case.parser.key
        assert provenance["policy_profile"] == case.policy.key
        assert (root / ".meta/negative_false_substitute.cpp").is_file()


def test_structural_manifest_independently_reconciles_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _out(tmp_path, monkeypatch)
    expiry.build(out, force=True)
    manifest = expiry.structural_preflight(out)
    assert manifest["root_count"] == 90
    assert manifest["tree_hash"] == expiry._tree_hash(out)
    rows = manifest["rows"]
    assert len(rows) == 90
    assert len({row["prompt_hash"] for row in rows}) == 90
    assert len({tuple(row["reference_hashes"]) for row in rows}) == 90
    assert all(row["primary_core_objective"] == "achieved" for row in rows)


def test_prompt_boundary_inspects_every_root_and_whole_file_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _out(tmp_path, monkeypatch)
    expiry.build(out, force=True)
    report = expiry._prompt_boundary(out)
    assert report["pass"] is True
    assert len(report["rows"]) == 90
    for row in report["rows"]:
        task_id = row["task_id"]
        assert row["solution_order"] == [f"{task_id}.h", f"{task_id}.cpp"]


def test_all_4005_pairs_have_seven_independent_decisions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _out(tmp_path, monkeypatch)
    expiry.build(out, force=True)
    report = expiry.diversity_screen(out)
    assert report["root_count"] == 90
    assert report["pair_count"] == report["expected_pair_count"] == 4005
    assert tuple(report["dimensions"]) == expiry.HARD_RULE_DIMENSIONS
    seen: set[tuple[str, str]] = set()
    for row in report["pairs"]:
        pair = (row["left"], row["right"])
        assert pair not in seen
        seen.add(pair)
        decisions = row["dimensions"]
        assert decisions["pass"] is True
        for dimension in expiry.HARD_RULE_DIMENSIONS:
            decision = decisions[dimension]
            assert set(decision) == {
                "containment",
                "limit",
                "jaccard",
                "jaccard_limit",
                "distinct",
            }
            assert decision["distinct"] is True
            assert (
                decision["containment"] < decision["limit"]
                and decision["jaccard"] < decision["jaccard_limit"]
            )
    assert len(seen) == 4005


def test_coherent_clone_controls_change_files_and_fail_every_dimension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _out(tmp_path, monkeypatch)
    expiry.build(out, force=True)
    rows = expiry.control_screen(out)
    assert set(rows) == {
        "domain-identifier-renamed-clone",
        "constants-policy-only-clone",
        "opposite-end-selection-clone",
    }
    for row in rows.values():
        assert row["changed_files"]
        assert row["semantic_screen"] == "rejected:duplicate_family"
        assert set(row["failed_dimensions"]) == set(expiry.HARD_RULE_DIMENSIONS)
        assert Path(out / row["root"]).is_dir()


def test_each_policy_negative_is_nonempty_compilable_shape_and_task_local(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _out(tmp_path, monkeypatch)
    roots = expiry.build(out, force=True)
    negative_hashes = set()
    for case, root in zip(CASES, roots, strict=True):
        reference = (root / ".meta/example.cpp").read_text()
        negative = (root / ".meta/negative_false_substitute.cpp").read_text()
        assert negative != reference
        assert f'#include "{case.task_id}.h"' in negative
        negative_hashes.add(expiry._sha_bytes(negative.encode()))
    assert len(negative_hashes) == 90


def test_output_guard_refuses_both_existing_generated_trees() -> None:
    for forbidden in (expiry.LEGACY_ROOT / "x", expiry.REVERIFY_ROOT / "x"):
        with pytest.raises(RuntimeError, match="unsafe_output_root"):
            expiry._assert_output_root(forbidden)


def test_force_rejects_foreign_owned_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _out(tmp_path, monkeypatch)
    expiry.build(out, force=True)
    foreign = out / "foreign-root/.meta"
    foreign.mkdir(parents=True)
    (foreign / "config.json").write_text("{}")
    with pytest.raises(RuntimeError, match="generator_output_drift"):
        expiry.build(out, force=True)


def test_curriculum_spec_wrapper_and_local_only_boundary() -> None:
    curriculum = expiry.CURRICULUM.read_text()
    family_spec = expiry.FAMILY_SPEC.read_text()
    wrapper = Path(
        "examples/slime/moonlight_cpp_perf/prepare_expiry_identifier_aider_tasks.sh"
    )
    assert "exactly the 90 roots" in curriculum
    assert "4,005" in curriculum
    assert "local_family_verified" in curriculum
    assert "All 90 roots" in family_spec
    assert "no JSONL" in family_spec
    assert wrapper.is_file()
    assert "moonlight_expiry_identifier_aider_tasks" in wrapper.read_text()


def test_audit_counterexamples_are_bound_into_generated_references_and_oracles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _out(tmp_path, monkeypatch)
    roots = expiry.build(out, force=True)
    combined_references = "\n".join(
        (root / ".meta/example.cpp").read_text() for root in roots
    )
    assert "credential.size()!=8" in combined_references
    assert "credential.size()!=9" not in combined_references
    assert "<=29 ? ExpiryState::warning" in combined_references
    assert "input.packed & ~8388607U" in combined_references
    assert "numeric_limits<long long>::max()-input.utc_offset_minutes" in combined_references
    for forbidden_cap in ("grace_days>366", "business_grace>260", "shelf_months>120", "units>100000"):
        assert forbidden_cap not in combined_references
    for root in roots:
        hidden = (root / ".meta/task_hidden_test.cpp").read_text()
        assert "parser_case" in hidden
        assert "numeric_limits<int>::max()" in hidden or root.name in {
            case.task_id for case in CASES if case.policy_index in {0, 4, 7, 8}
        }


def test_force_regeneration_preserves_immutable_audits_and_remedies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _out(tmp_path, monkeypatch)
    expiry.build(out, force=True)
    audit = out / ".state/audits/cycle-01.json"
    remedy = out / ".state/remedies/cycle-01.json"
    audit.parent.mkdir(parents=True)
    remedy.parent.mkdir(parents=True)
    audit.write_text('{"immutable":true}\n')
    remedy.write_text('{"finding_id":"EXPIRY-AUD-001"}\n')
    expiry.build(out, force=True)
    assert audit.read_text() == '{"immutable":true}\n'
    assert remedy.read_text() == '{"finding_id":"EXPIRY-AUD-001"}\n'


def test_docker_receipt_redaction_preserves_the_exact_executed_argv_tail() -> None:
    command = [
        "docker",
        "run",
        "--network",
        "none",
        expiry.SANITY_IMAGE,
        "bash",
        "-lc",
        "set -euo pipefail\necho private-script",
    ]
    redacted = expiry._redacted_docker_command(command)
    assert redacted == command[:-1] + ["<owner-embedded-script>"]
    assert redacted[-4:] == [
        expiry.SANITY_IMAGE,
        "bash",
        "-lc",
        "<owner-embedded-script>",
    ]
    assert redacted.count("bash") == 1
    with pytest.raises(RuntimeError, match="receipt_command_mismatch"):
        expiry._redacted_docker_command(["docker", "run", "sh", "-c", "private"])


def test_epoch_minute_offset_direction_is_documented_and_discriminated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # EXPIRY-AUD-008: the civil minute is minute plus utc_offset_minutes; an
    # offset of zero cannot discriminate addition from subtraction, so every
    # epoch-minute fixture must carry a nonzero offset.
    assert "minute plus utc_offset_minutes" in PARSERS[9].grammar
    epoch_cases = [case for case in CASES if case.parser_index == 9]
    assert len(epoch_cases) == 9
    out = _out(tmp_path, monkeypatch)
    expiry.build(out, force=True)
    for case in epoch_cases:
        root = out / case.task_id
        instructions = (root / ".docs/instructions.md").read_text()
        assert "minute plus utc_offset_minutes" in instructions
        visible = (root / "task_visible_test.cpp").read_text()
        hidden = (root / ".meta/task_hidden_test.cpp").read_text()
        assert "{0LL,60}" in visible
        assert "parser_case.utc_offset_minutes==60" in hidden
        # Under subtraction the fixture resolves to 1999-12-31, so every
        # expectation pinned to the addition result 2000-01-01 rejects the
        # offset-direction mutant.
        assert "CivilDate{2000,1,1}" in visible + hidden
        reference = (root / ".meta/example.cpp").read_text()
        assert reference.count("input.minute+input.utc_offset_minutes") == 1
    # Policies whose weekday/window semantics can equate adjacent Friday and
    # Saturday expiries carry explicit same-expiry-day boundary checks so the
    # direction mutant cannot hide behind business-day or window equivalence.
    water_gauge = (out / "dated-water-gauge/.meta/task_hidden_test.cpp").read_text()
    assert "business_window(" in water_gauge and ",0)" in water_gauge
    jet_guest = (out / "dated-jet-propulsion-guest/.meta/task_hidden_test.cpp").read_text()
    assert "on_day.admitted&&on_day.state==ExpiryState::active" in jet_guest
