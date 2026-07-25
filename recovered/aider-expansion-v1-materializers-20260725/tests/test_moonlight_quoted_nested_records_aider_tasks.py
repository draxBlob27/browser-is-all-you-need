from __future__ import annotations

import inspect
import json
import os
import shutil
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_quoted_nested_records_aider_tasks as owner
from w8_biayn.integrations.moonlight_quoted_nested_records_cases import (
    ARCHITECTURES,
    CASES,
    EXPECTED_PARSE,
    OPERATIONS,
    negative,
    private_test,
    reference,
    visible_test,
)


def _allow_scratch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(owner, "_assert_output_root", lambda _out: None)


def test_case_matrix_is_exact_110_and_not_id_padded() -> None:
    assert len(ARCHITECTURES) == 11
    assert len(OPERATIONS) == 10
    assert len(CASES) == 110
    assert len({case.task_id for case in CASES}) == 110
    assert len({case.architecture.mechanism for case in CASES}) == 11
    assert len({case.operation.objective for case in CASES}) == 10
    assert {
        (case.architecture.key, case.operation.key) for case in CASES
    } == {
        (architecture.key, operation.key)
        for architecture in ARCHITECTURES
        for operation in OPERATIONS
    }


def test_materialization_has_exact_roles_and_new_root_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_scratch(monkeypatch)
    roots = owner.build(tmp_path)
    assert len(roots) == 110
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [
            ".meta/example.h",
            ".meta/example.cpp",
        ]
        assert provenance["family_id"] == owner.FAMILY_ID
        assert provenance["lineage"].startswith("new-root")
        assert provenance["dataset_handoff"] == "not_requested"
        assert (root / ".meta/task_private_test.cpp").is_file()
        assert (root / ".meta/negative_false_substitute.cpp").is_file()
    manifest = json.loads((tmp_path / ".state/candidate-manifest.json").read_text())
    assert manifest["candidate_count"] == 110
    assert manifest["rejected"] == []
    assert manifest["replaced"] == []


def test_core_preflight_recomputes_all_pairs_and_controls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_scratch(monkeypatch)
    monkeypatch.setattr(
        owner,
        "_cross_tree_screen",
        lambda _out, tokens: {
            "status": "pass",
            "compared_existing_roots": 1470,
            "rows": sorted(tokens),
        },
    )
    monkeypatch.setattr(
        owner,
        "_holdout_screen",
        lambda tokens: {"status": "pass", "holdout_count": 26, "rows": sorted(tokens)},
    )
    owner.build(tmp_path)
    manifest = owner.verify_core(tmp_path)
    assert manifest["root_count"] == 110
    assert manifest["pair_count"] == 5995
    assert manifest["hard_rule_dimensions"] == list(owner.HARD_RULE_DIMENSIONS)
    assert all(pair["pass"] for pair in manifest["pair_decisions"])
    for pair in manifest["pair_decisions"]:
        assert set(pair["dimensions"]) == set(owner.HARD_RULE_DIMENSIONS)
        assert all(row["different"] for row in pair["dimensions"].values())
    controls = manifest["adversarial_controls"]
    assert set(controls) == {
        "domain-identifier-renamed-clone",
        "constants-policy-only-clone",
        "opposite-end-selection-clone",
    }
    assert all(row["changed_files"] for row in controls.values())
    assert all(not row["production_decision"]["pass"] for row in controls.values())


def test_owner_refuses_non_expansion_output(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="unsafe_output_root"):
        owner.build(tmp_path / "wrong-root")


def test_cross_tree_id_collision_is_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_scratch(monkeypatch)
    collision = tmp_path / "legacy" / CASES[0].task_id
    (collision / ".meta").mkdir(parents=True)
    (collision / ".meta/config.json").write_text(
        json.dumps({"files": {"solution": [], "test": [], "example": []}})
    )
    monkeypatch.setattr(owner, "LEGACY_ROOT", tmp_path / "legacy")
    monkeypatch.setattr(owner, "REVERIFY_ROOT", tmp_path / "reverify")
    monkeypatch.setattr(owner, "EXPANSION_ROOT", tmp_path / "expansion")
    with pytest.raises(RuntimeError, match="duplicate_task"):
        owner.build(tmp_path / "output")


def test_docker_creator_preflight_is_network_disabled_and_fresh() -> None:
    source = inspect.getsource(owner.docker_sanity)
    assert '"--network"' in source and '"none"' in source
    assert "grader_mount_hash_mismatch" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "negative_fixtures" in source
    assert 'for nmode in normal sanitizer' in source
    assert "adversarial_controls" in source
    assert "compiler_hash" in source
    assert "creator_preflight_receipt_hash" in source
    assert "holdout_inventory_hash" in inspect.getsource(owner._holdout_screen)
    assert "comparison_corpus_hash" in inspect.getsource(owner._cross_tree_screen)


def test_every_operation_has_exact_oracles_and_operation_wrong_substitute() -> None:
    weak_predicates = (
        ".empty()",
        ">0U",
        ">=0LL",
        "!=0ULL",
    )
    mutation_markers = {
        "project": "reverse(result.projected",
        "cardinality": "++result.count",
        "unique": "reverse(result.unique_values",
        "bounded-total": "++result.total",
        "flatten": "reverse(result.flattened",
        "checksum": "result.checksum^=1ULL",
        "ancestry": "reverse(result.paths",
        "spans": "reverse(result.spans",
        "group": "result.groups.pop_back",
        "canonical": "result.canonical+='!'",
    }
    for case in CASES:
        visible = visible_test(case)
        private = private_test(case)
        wrong = negative(case)
        assert "==std::vector" in visible or any(
            marker in visible for marker in (".count==", ".total==", ".checksum==", ".canonical==")
        )
        assert "auto probe=" in private
        assert "architecture_ok" in private
        assert mutation_markers[case.operation.key] in wrong
        assert "if(!core.valid)return {true" not in wrong
        assert not all(marker in visible for marker in weak_predicates)


def test_reference_regressions_are_fixed_and_exercised() -> None:
    cases = {case.task_id: case for case in CASES}
    sexpr = reference(cases["qr-sexpr-project"])
    multipart = reference(cases["qr-multipart-project"])
    typed = reference(cases["qr-typed-fields-project"])
    assert "if(!child_counts.empty())++child_counts.back();atom.clear()" in sexpr
    assert 'phase=line=="--"+feed.boundary+"--"?Phase::done' in multipart
    assert "line.back()=='-'" not in multipart
    assert 'kv.first!="label"' not in typed
    assert 'kv.second.empty()||!std::all_of' in typed
    assert "architecture_empty" in private_test(cases["qr-sexpr-project"])
    assert '"cut-"' in private_test(cases["qr-multipart-project"])
    typed_private = private_test(cases["qr-typed-fields-project"])
    for value in ('"extra"', '"yes"', '{"id",""}', '{"","17"}'):
        assert value in typed_private


def test_expected_parse_inventory_covers_every_architecture() -> None:
    assert set(EXPECTED_PARSE) == {architecture.key for architecture in ARCHITECTURES}
    for architecture in ARCHITECTURES:
        values, depths = EXPECTED_PARSE[architecture.key]
        assert len(values) == architecture.valid_count
        assert len(values) == len(depths)


def test_cycle_three_operation_discriminators_are_observable() -> None:
    cases = {case.task_id: case for case in CASES}
    for architecture in ARCHITECTURES:
        prefix = f"qr-{architecture.key}"
        project = private_test(cases[f"{prefix}-project"])
        unique = private_test(cases[f"{prefix}-unique"])
        spans = private_test(cases[f"{prefix}-spans"])
        canonical = private_test(cases[f"{prefix}-canonical"])
        assert "{1U,0U}" in project and "{999U}" in project
        assert '"Alpha"' in unique and '"alpha"' in unique
        assert "probe_original" in unique
        assert "include_separator" in cases[f"{prefix}-spans"].operation.option_decl
        assert "},false)" in spans
        assert "R\"(" in canonical and "\\b" in canonical
        assert ",'a')" in canonical


def test_record_relative_depths_and_missing_parent_are_explicit() -> None:
    affected = {"bracket-tree", "tag-stack", "multipart", "sexpr"}
    for architecture in affected:
        case = next(
            case
            for case in CASES
            if case.task_id == f"qr-{architecture}-ancestry"
        )
        source = reference(case)
        assert 'core.depths[i]>stack.size()' in source
        assert '"missing parent"' in source
        assert EXPECTED_PARSE[architecture][1][0] == 0
    cases = {case.task_id: case for case in CASES}
    for architecture in ("quoted-row", "bracket-tree", "sexpr"):
        private = private_test(cases[f"qr-{architecture}-ancestry"])
        assert "architecture_gap" in private
        assert 'architecture_gap.reason=="missing parent"' in private
        assert "architecture_gap.paths.empty()" in private


def test_host_verify_is_fail_closed_and_receipt_bound() -> None:
    source = inspect.getsource(owner.verify_host)
    helper = inspect.getsource(owner._host_build_and_test)
    assert "host_toolchain_not_completed" in source
    assert "reference_tests_failed" in source
    assert "test_discovery_failed" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "invariant_not_enforced" in source
    assert "adversarial_control_not_pure" in source
    assert "audit_subject_hash" in source
    assert "task_tree_hashes" in source
    assert "reference_hashes" in source
    assert "compiler_hash" in source
    assert "negative_fixtures" in source
    assert "host_verify" in source
    assert "Unix Makefiles" in helper
    assert "-fsanitize=address,undefined" in inspect.getsource(owner)
    assert owner.HOST_RECEIPT_NAME == ".state/host-verify-receipt.json"


def test_host_build_helper_runs_one_reference_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _allow_scratch(monkeypatch)
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        pytest.skip("host toolchain unavailable")
    roots = owner.build(tmp_path)
    root = next(path for path in roots if path.name == "qr-quoted-row-project")
    env = dict(os.environ)
    count, code = owner._host_build_and_test(
        root, tmp_path / "build-smoke", root / ".meta/example.cpp", False, env
    )
    assert count == 2
    assert code == 0
    negative_count, negative_code = owner._host_build_and_test(
        root,
        tmp_path / "build-smoke-negative",
        root / ".meta/negative_false_substitute.cpp",
        False,
        env,
    )
    assert negative_count == 2
    assert negative_code != 0


def test_wrapper_targets_only_expansion_tree() -> None:
    wrapper = Path(
        "examples/slime/moonlight_cpp_perf/prepare_quoted_nested_records_aider_tasks.sh"
    )
    assert wrapper.is_file()
    text = wrapper.read_text()
    assert "moonlight_quoted_nested_records_aider_tasks" in text
    assert "aider-tasks-expansion-v1/validation-parsing/quoted-nested-records" in text
    assert "aider-tasks-reverify" not in text
    assert "aider-tasks/aider" not in text
