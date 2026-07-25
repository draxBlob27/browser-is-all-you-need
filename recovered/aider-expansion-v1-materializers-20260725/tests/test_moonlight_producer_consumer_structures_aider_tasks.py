from __future__ import annotations

import inspect
import json
import shutil
from pathlib import Path

import pytest

from w8_biayn.integrations import (
    moonlight_producer_consumer_structures_aider_tasks as structures,
)
from w8_biayn.integrations import moonlight_producer_consumer_protocols as protocols


def _materialize(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    expansion = tmp_path / "aider-tasks-expansion-v1"
    out = expansion / "state-concurrency/producer-consumer-behavior-structures"
    monkeypatch.setattr(structures, "EXPANSION_ROOT", expansion)
    roots = structures.build(out, force=True)
    assert len(roots) == 60
    return out


def test_inventory_is_exact_count_plan_cell() -> None:
    assert len(structures.CASES) == structures.EXPECTED_ROOTS == 60
    assert structures.EXPECTED_PAIRS == 1770
    assert len({case.task_id for case in structures.CASES}) == 60
    assert len({case.mechanism for case in structures.CASES}) == 60
    assert len({case.state_model for case in structures.CASES}) == 60
    assert {case.group for case in structures.CASES} == {
        "admission", "lifecycle", "fanout", "scheduling", "ownership", "batching"
    }
    assert all(sum(case.group == group for case in structures.CASES) == 10 for group in {case.group for case in structures.CASES})


def test_materialization_has_exact_roles_and_private_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _materialize(tmp_path, monkeypatch)
    for case in structures.CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["lineage"] == "new-root"
        assert provenance["owner"] == structures.OWNER_ID
        assert provenance["task_id"] == case.task_id
        assert "no SFT release" in provenance["status"]
        assert (root / ".meta/visible_test.cpp").is_file()
        assert (root / ".meta/hidden_test.cpp").is_file()
        assert (root / ".meta/model_test.cpp").is_file()
        assert structures.negative_source(root) != (root / ".meta/example.cpp").read_text()


def test_protocol_roots_use_domain_types_literal_oracles_and_unique_negatives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _materialize(tmp_path, monkeypatch)
    negative_names: set[str] = set()
    negative_kinds: set[str] = set()
    for case in structures.CASES:
        root = out / case.task_id
        header = (root / f"{case.task_id}.h").read_text()
        reference = (root / ".meta/example.cpp").read_text()
        tests = "\n".join(
            (root / f".meta/{suite}_test.cpp").read_text()
            for suite in ("visible", "hidden", "model")
        )
        negative = json.loads((root / ".meta/negative.json").read_text())
        assert "int score;" not in header
        assert "candidate.score" not in reference
        assert "policy_tag" not in header
        assert "Submission" in header and "Control" in header
        assert case.mechanism in tests
        assert case.state_model in tests
        assert negative["mechanism"] == case.mechanism
        suffixes = (
            "-eligibility-gate",
            "-wrong-release-payload",
            "-wrong-release-order",
        )
        assert any(negative["name"].endswith(suffix) for suffix in suffixes)
        assert negative["name"].startswith(case.task_id)
        assert negative["from"] != negative["to"]
        negative_names.add(negative["name"])
        negative_kinds.add(next(suffix for suffix in suffixes if negative["name"].endswith(suffix)))
    assert len(negative_names) == 60
    assert negative_kinds == set(suffixes)
    owner_source = inspect.getsource(structures)
    assert "def _simulate" not in owner_source
    assert "def _profile" not in owner_source
    assert set(protocols._MECHANISM_EFFECTS) == {
        case.task_id for case in structures.CASES
    }
    assert len(set(protocols._MECHANISM_EFFECTS.values())) == 60


def test_retention_roots_own_executable_reclaim_transitions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _materialize(tmp_path, monkeypatch)
    retention = protocols._RETENTION_ROOTS
    assert len(retention) == 13
    assert set(protocols._RELEASE_TRANSITIONS) == set(retention)
    assert set(protocols._MODEL_TAILS) <= set(retention)
    assert set(protocols._RETENTION_RULES) == set(retention)
    assert protocols._CURSOR_ROOTS <= set(retention)
    for case in structures.CASES:
        root = out / case.task_id
        header = (root / f"{case.task_id}.h").read_text()
        reference = (root / ".meta/example.cpp").read_text()
        p = protocols.policy(case)
        if case.task_id in retention:
            assert case.task_id in protocols._RELEASE_TRANSITIONS
            if case.task_id in protocols._MODEL_TAILS:
                releases, _retained, history = protocols._MODEL_TAILS[case.task_id]
                # Retention changes reclamation, never the selection contract:
                # the first two releases and released history match the
                # declared protocol projection for the fixed trace.
                assert releases[:2] == [p.expected_first, p.expected_second]
                assert history == [p.expected_first, p.expected_second]
                assert releases[2] is None and releases[3] is None
            bitmask_roots = {
                "quorum-ack-reclaimer", "slow-reader-evictor",
                "branch-barrier-delivery", "selective-redelivery-table",
                "tombstone-confirmation-log",
            }
            assert protocols._extra_snapshot(case)[0] != ""
            if case.task_id in protocols._CURSOR_ROOTS:
                assert "consumer_cursors_" in reference
                assert "consumer_cursors_;" in header
            elif case.task_id == "durable-offset-tracker":
                assert "commit_frontier_" in header and "commit_frontier_" in reference
            elif case.task_id in bitmask_roots:
                assert "|= (1 << participant)" in reference
            else:
                assert case.task_id in {
                    "exactly-once-commit-table", "deduplicating-replay-ledger"
                }
        else:
            aggregate = protocols._state_terms(case)[0]
            default_erase = protocols._ERASE_SELECTED.format(
                aggregate=aggregate, ledger="ledger_", markers="markers_"
            )
            assert default_erase in reference
            assert case.task_id not in protocols._RELEASE_TRANSITIONS


def test_core_preflight_records_every_pair_and_dimension_independently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _materialize(tmp_path, monkeypatch)
    first = out / structures.CASES[0].task_id
    second = out / structures.CASES[1].task_id
    decision = structures._pair_decision(first, second)
    assert decision["pass"] is True
    assert set(decision["dimensions"]) == set(structures.DIMENSIONS)
    assert all(
        item["different"] is True
        and (
            item["code_similarity"] <= structures.MAX_DIMENSION_JACCARD
            or item["prose_similarity"] <= structures.MAX_DIMENSION_JACCARD
        )
        for item in decision["dimensions"].values()
    )
    # The evaluator compares executable topology (identifier-collapsed
    # shingles) plus contract prose, never raw naming.
    owner_source = inspect.getsource(structures)
    assert "_shingles" in owner_source and "_prose_tokens" in owner_source
    assert structures.NORMALIZER_VERSION.endswith("structural")
    manifest = structures.verify_core(out)
    assert manifest["retained_count"] == 60
    report = json.loads((out / ".state/diversity-report.json").read_text())
    assert report["pair_count"] == 1770
    assert all(pair["pass"] for pair in report["pairs"])


def test_three_coherent_adversarial_controls_build_and_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        pytest.skip("host toolchain is optional; Docker preflight executes controls")
    out = _materialize(tmp_path, monkeypatch)
    structures.verify_core(out)
    report = structures.verify_adversarial_controls(out)
    assert report["result"] == "pass"
    assert len(report["controls"]) == 3
    assert all(item["production_evaluator_rejected"] for item in report["controls"])


def test_cross_tree_screen_includes_other_expansion_roots() -> None:
    source = inspect.getsource(structures._cross_tree_screen)
    assert "(*LEGACY_ROOTS, EXPANSION_ROOT)" in source
    assert "if root == out or out in root.parents" in source


def test_output_boundary_rejects_existing_trees() -> None:
    for forbidden in structures.LEGACY_ROOTS:
        with pytest.raises(RuntimeError, match="unsafe_output_root"):
            structures.build(forbidden / "aider-state/producer-consumer-behavior-structures")


def test_owner_binds_locked_network_disabled_receipt() -> None:
    source = inspect.getsource(structures._verify_receipt)
    assert 'runtime.get("environment") != "locked-docker"' in source
    assert 'runtime.get("network") != "none"' in source
    assert 'runtime.get("image") != SANITY_IMAGE' in source
    verify_source = inspect.getsource(structures.verify)
    assert "Unix Makefiles" in verify_source
    assert "sanitizer_test_count_mismatch" in verify_source
    assert "negative_fixture_not_rejected" in verify_source
