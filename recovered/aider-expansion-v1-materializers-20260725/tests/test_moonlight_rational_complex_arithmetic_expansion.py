from __future__ import annotations

import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_rational_complex_arithmetic_expansion as family


def _sandbox_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    expansion = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1"
    out = expansion / "numerical-anchors/rational-complex-value-arithmetic"
    monkeypatch.setattr(family, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(family, "LEGACY_ROOT", tmp_path / "legacy")
    monkeypatch.setattr(family, "REVERIFY_ROOT", tmp_path / "reverify")
    holdouts = tmp_path / "holdouts"
    for task_id in family.OFFICIAL_HOLDOUTS:
        (holdouts / task_id).mkdir(parents=True)
    monkeypatch.setattr(family, "HOLDOUT_ROOT", holdouts)
    weighted = (
        expansion
        / "numerical-arithmetic/overflow-scoring-combinatorial/weighted-median-mark"
    )
    (weighted / ".docs").mkdir(parents=True)
    (weighted / ".meta").mkdir()
    (weighted / ".docs/instructions.md").write_text(
        "Sort weighted values and return the first value whose cumulative weight "
        "reaches half; stable lower ordering wins.\n"
    )
    (weighted / ".docs/introduction.md").write_text("Weighted median selection.\n")
    (weighted / "weighted-median-mark.h").write_text(
        "struct WeightedMedianMark { unsigned value; unsigned weight; };\n"
    )
    (weighted / ".meta/example.cpp").write_text(
        "// sort weights; first cumulative weight reaching half selects lower value\n"
    )
    (weighted / ".meta/negative_false_substitute.cpp").write_text(
        "// ordinary unweighted median ignores cumulative half weights\n"
    )
    (weighted / "task_visible_test.cpp").write_text("// weighted half test\n")
    (weighted / ".meta/task_hidden_test.cpp").write_text("// stable cumulative test\n")
    (weighted / ".meta/config.json").write_text(
        json.dumps(
            {
                "files": {
                    "solution": ["weighted-median-mark.h", "weighted-median-mark.cpp"],
                    "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
                    "example": [".meta/example.h", ".meta/example.cpp"],
                }
            }
        )
        + "\n"
    )
    return out


def test_binding_count_domains_and_mechanisms_are_exact() -> None:
    assert len(family.TASKS) == 40
    assert len({case.task_id for case in family.TASKS}) == 40
    assert sum(case.domain == "rational" for case in family.TASKS) == 20
    assert sum(case.domain == "gaussian" for case in family.TASKS) == 2
    assert sum(case.domain == "complex" for case in family.TASKS) == 18
    assert len({case.mechanism for case in family.TASKS}) == 40
    ids = {case.task_id for case in family.TASKS}
    assert "rational-amortization-schedule" in ids
    assert "rational-weighted-median" not in ids
    assert family.HARD_RULE_DIMENSIONS == (
        "public_api",
        "owned_state_or_algorithm",
        "mutation_selection_rules",
        "invalid_boundary_behavior",
        "reference_control_flow",
        "deterministic_oracle",
        "topic_negative_fixture",
    )


def test_expansion_owner_refuses_every_wrong_or_existing_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _sandbox_roots(tmp_path, monkeypatch)
    assert family._safe_output(out) == out.resolve()
    for forbidden in (
        family.LEGACY_ROOT,
        family.REVERIFY_ROOT,
        family.EXPANSION_ROOT / "numerical-anchors/wrong-family",
        tmp_path / "outside",
    ):
        with pytest.raises(family.VerificationError, match="unsafe_output_root"):
            family._safe_output(forbidden)


def test_materialization_roles_provenance_and_private_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _sandbox_roots(tmp_path, monkeypatch)
    result = family.materialize(out)
    assert result["tasks"] == 40
    roots = sorted(path for path in out.iterdir() if path.is_dir() and path.name != ".state")
    assert len(roots) == 40
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert not set(config["files"]["solution"]) & set(config["files"]["test"])
        instructions = (root / ".docs/instructions.md").read_text()
        assert instructions.startswith("# Instructions\n")
        assert "## Examples" in instructions
        assert "## Mechanism" in instructions
        for banned in (
            "clean-room",
            "Advertised mechanism",
            "must not substitute",
            "Replace both supplied editable files",
            "hidden test",
            "oracle",
            "grader",
            "benchmark",
        ):
            assert banned not in instructions, (root.name, banned)
        introduction = (root / ".docs/introduction.md").read_text()
        assert "clean-room" not in introduction
        assert len(introduction.split("\n\n")) >= 3
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert provenance["lineage"] == "new-root"
        assert provenance["generator"] == family.OWNER
        assert provenance["status"] == "local candidate; not dataset admission"
        prompt = family.build_prompt(family.load_task(root))
        for private in ("CMakeLists.txt", "example.cpp", "task_hidden_test", "negative_false", "provenance"):
            assert private not in prompt
        assert f"{root.name}.h" in prompt and f"{root.name}.cpp" in prompt
    selected = json.loads((out / ".state/selected-manifest.json").read_text())
    assert selected["requested_count"] == selected["retained_count"] == 40
    assert len(selected["tasks"]) == 40


def test_whole_file_boundary_rejects_omissions_extras_and_prose(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _sandbox_roots(tmp_path, monkeypatch)
    family.materialize(out)
    case = family.TASKS[0]
    root = out / case.task_id
    header = (root / ".meta/example.h").read_text()
    source = (root / ".meta/example.cpp").read_text()
    response = f"{case.task_id}.h\n```cpp\n{header}```\n{case.task_id}.cpp\n```cpp\n{source}```\n"
    assert set(family.parse_whole_file_blocks(response)) == {f"{case.task_id}.h", f"{case.task_id}.cpp"}
    with pytest.raises(family.WholeFormatError):
        family.parse_whole_file_blocks("explanation\n" + response)
    parsed = family.parse_whole_file_blocks(f"{case.task_id}.h\n```cpp\n{header}```\n")
    assert set(parsed) != {f"{case.task_id}.h", f"{case.task_id}.cpp"}
    extra = family.parse_whole_file_blocks(response + "unknown.cpp\n```cpp\nint x;\n```\n")
    assert "unknown.cpp" in extra


def test_seven_dimension_screen_and_controls_are_artifact_derived(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _sandbox_roots(tmp_path, monkeypatch)
    family.materialize(out)
    result = family.verify_core(out)
    assert result["root_count"] == 40
    assert result["pair_count"] == 780
    screen = json.loads((out / ".state/family-screen.json").read_text())
    assert screen["pair_count"] == 40 * 39 // 2
    assert screen["dimensions"] == list(family.HARD_RULE_DIMENSIONS)
    assert len(screen["pairs"]) == 780
    for pair in screen["pairs"]:
        assert set(pair["dimensions"]) == set(family.HARD_RULE_DIMENSIONS)
        assert pair["pass"]
        for dimension, record in pair["dimensions"].items():
            assert record["distinct"]
            assert record["overlap"] <= 0.94
            if dimension in {"public_api", "deterministic_oracle"}:
                assert record["symmetric_difference"] >= 2
            else:
                assert record["symmetric_difference"] >= 3
                assert record["left_structure"] != record["right_structure"] or record["symmetric_difference"] >= 6
    assert len(screen["controls"]) == 4
    assert screen["control_bundle_hash"] == family._control_bundle_hash(
        out / ".state/adversarial-clone-controls"
    )
    for control in screen["controls"]:
        assert control["changed_file_count"] > 0
        assert control["tree_hash"] != "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert not control["comparison"]["pass"]
        if control["name"] == "representation-changed-weighted-selection":
            assert control["comparison"]["semantic_rule"] == (
                "representation-invariant-stable-weighted-cumulative-half-selection"
            )
            assert control["comparison"]["semantic_target"] == "weighted-median-mark"
        else:
            assert any(
                not item["distinct"]
                for item in control["comparison"]["dimensions"].values()
            )
    inventory = json.loads((out / ".state/source-inventory.json").read_text())
    lineage = json.loads((out / ".state/lineage-screen.json").read_text())
    assert inventory["schema_version"] == 2
    assert lineage["schema_version"] == 3
    assert lineage["source_inventory_hash"] == inventory["inventory_hash"]
    assert lineage["semantic_snapshot_hash"] == inventory["semantic_snapshot_hash"]
    assert lineage["semantic_snapshot_record_count"] == len(inventory["records"])
    assert inventory["semantic_snapshot_hash"] == family._semantic_snapshot_hash(
        inventory["records"]
    )
    for record in inventory["records"]:
        assert family._validate_snapshot_record(record) == set(
            record["semantic_tokens"]
        )
    assert lineage["inventory_counts"] == inventory["counts"]
    assert lineage["screen_start_inventory_hash"] == inventory["inventory_hash"]
    assert lineage["screen_end_inventory_hash"] == inventory["inventory_hash"]
    assert lineage["source_inventory_record_hash"] == family._sha256(
        (out / ".state/source-inventory.json").read_bytes()
    )
    assert lineage["comparison_count"] == 40 * sum(inventory["counts"].values())


def test_cross_tree_id_collision_fails_before_writing_tasks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _sandbox_roots(tmp_path, monkeypatch)
    collision = family.REVERIFY_ROOT / "topic" / family.TASKS[0].task_id / ".meta"
    collision.mkdir(parents=True)
    (collision / "config.json").write_text("{}\n")
    with pytest.raises(family.VerificationError, match="cross_tree_id_collision"):
        family.materialize(out)


def test_every_reference_and_negative_core_is_present_and_distinct() -> None:
    for case in family.TASKS:
        assert case.core.strip()
        assert case.negative_core.strip()
        assert case.core != case.negative_core
        files = family._task_files(case)
        assert "CORE_BEGIN" in files[".meta/example.cpp"]
        assert "CORE_BEGIN" in files[".meta/negative_false_substitute.cpp"]
        assert case.negative_name in files[".meta/tests.toml"]


def test_normative_spec_matches_every_emitted_declaration() -> None:
    spec = family.FAMILY_SPEC.read_text()
    for case in family.TASKS:
        assert f"`{case.task_id}`" in spec
        assert f"`{case.declaration}`" in spec


def test_numeric_boundary_policy_is_prompt_visible_for_every_affected_root() -> None:
    affected = {
        "complex-newton-iteration",
        "complex-impedance-reduction",
        "complex-mobius-transform",
        "complex-cross-ratio",
        "complex-matrix-determinant",
        "complex-linear-system",
        "complex-quantum-gate",
        "complex-state-normalization",
    }
    cases = {case.task_id: case for case in family.TASKS}
    assert set(cases) >= affected
    for task_id in affected:
        instructions = family._instructions(cases[task_id])
        assert "## Numerical policy" in instructions
        if task_id == "complex-quantum-gate":
            assert "1e-10L" in instructions
        else:
            assert "1e-24L" in instructions


def test_control_bundle_digest_changes_when_any_control_byte_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _sandbox_roots(tmp_path, monkeypatch)
    family.materialize(out)
    family.verify_core(out)
    controls = out / ".state/adversarial-clone-controls"
    before = family._control_bundle_hash(controls)
    target = controls / "constants-policy-only/.docs/introduction.md"
    target.write_text(target.read_text() + "mutation\n")
    assert family._control_bundle_hash(controls) != before


def test_verify_core_rejects_inventory_mutation_during_external_screen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _sandbox_roots(tmp_path, monkeypatch)
    family.materialize(out)
    original_screen = family._screen_external
    calls = 0

    def mutating_screen(*args: object, **kwargs: object) -> object:
        nonlocal calls
        result = original_screen(*args, **kwargs)
        calls += 1
        if calls == 1:
            added = family.EXPANSION_ROOT / "concurrent-family/concurrent-root/.meta"
            added.mkdir(parents=True)
            (added / "config.json").write_text("{}\n")
        return result

    monkeypatch.setattr(family, "_screen_external", mutating_screen)
    with pytest.raises(
        family.VerificationError, match="external_inventory_changed_during_screen"
    ):
        family.verify_core(out)


def test_creator_binding_rejects_a_lineage_screen_not_bound_to_inventory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _sandbox_roots(tmp_path, monkeypatch)
    family.materialize(out)
    family.verify_core(out)
    lineage_path = out / ".state/lineage-screen.json"
    lineage = json.loads(lineage_path.read_text())
    lineage["screen_end_inventory_hash"] = "sha256:" + "0" * 64
    lineage_path.write_text(json.dumps(lineage, indent=2, sort_keys=True) + "\n")
    with pytest.raises(
        family.VerificationError, match="external_inventory_screen_binding_mismatch"
    ):
        family._validate_inventory_screen_binding(out)


def test_creator_binding_rejects_mutated_semantic_snapshot_tokens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _sandbox_roots(tmp_path, monkeypatch)
    family.materialize(out)
    family.verify_core(out)
    inventory_path = out / ".state/source-inventory.json"
    inventory = json.loads(inventory_path.read_text())
    inventory["records"][0]["semantic_tokens"].append("unbound-mutation")
    inventory_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    with pytest.raises(
        family.VerificationError, match="external_inventory_snapshot_invalid"
    ):
        family._validate_inventory_screen_binding(out)


def test_ctest_discovery_count_parsing() -> None:
    assert family._ctest_discovery_count("Test project /x\nTotal Tests: 2\n") == 2
    assert family._ctest_discovery_count("Total Tests: 17\n") == 17
    assert family._ctest_discovery_count("No tests were found!!!\n") == 0
    assert family._ctest_discovery_count("") == 0


def _host_record(task_id: str, mode: str, **changes: object) -> dict[str, object]:
    record: dict[str, object] = {
        "task_id": task_id,
        "mode": mode,
        "discovered_tests": 2,
        "negative_discovered_tests": 2,
        "negative_outcome": "rejected",
    }
    record.update(changes)
    return record


def _good_host_records(expected: set[str]) -> list[dict[str, object]]:
    return [
        _host_record(task_id, mode)
        for task_id in sorted(expected)
        for mode in ("normal", "sanitizer")
    ]


def test_host_record_validation_accepts_complete_rejections() -> None:
    expected = {"task-a", "task-b"}
    family._validate_host_records(_good_host_records(expected), expected)


def test_host_record_validation_fails_closed_on_zero_tests() -> None:
    expected = {"task-a", "task-b"}
    records = _good_host_records(expected)
    records[0] = _host_record("task-a", "normal", discovered_tests=0)
    with pytest.raises(family.VerificationError, match="zero_tests"):
        family._validate_host_records(records, expected)


def test_host_record_validation_fails_closed_on_count_mismatch() -> None:
    expected = {"task-a", "task-b"}
    records = _good_host_records(expected)
    records[1] = _host_record("task-a", "sanitizer", negative_discovered_tests=3)
    with pytest.raises(
        family.VerificationError, match="sanitizer_test_count_mismatch"
    ):
        family._validate_host_records(records, expected)
    with pytest.raises(
        family.VerificationError, match="sanitizer_test_count_mismatch"
    ):
        family._validate_host_records(records[:2], expected)


def test_host_record_validation_fails_closed_on_unrejected_negative() -> None:
    expected = {"task-a", "task-b"}
    records = _good_host_records(expected)
    records[2] = _host_record("task-b", "normal", negative_outcome="passed")
    with pytest.raises(
        family.VerificationError, match="negative_fixture_not_rejected"
    ):
        family._validate_host_records(records, expected)


def test_verify_host_requires_host_toolchain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _sandbox_roots(tmp_path, monkeypatch)
    family.materialize(out)
    monkeypatch.setattr(family, "verify_core", lambda path: {"status": "pass"})
    monkeypatch.setattr(family.shutil, "which", lambda name: None)
    with pytest.raises(family.VerificationError, match="verification_not_completed"):
        family.verify_host(out)
