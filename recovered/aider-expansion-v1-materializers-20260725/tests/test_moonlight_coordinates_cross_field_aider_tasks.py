from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_coordinates_cross_field_aider_tasks as tasks
from w8_biayn.integrations.moonlight_coordinates_cross_field_cases import (
    BASELINE,
    DOMAINS,
    PREDICATE_TRIPLES,
    predicate_fails,
    witness_for,
)


AUDITED_CLONE_PAIRS = (
    ("constraint-theater-seat-relocation", "constraint-customs-declaration-review"),
    ("constraint-lab-plate-transfer", "constraint-scholarship-eligibility-review"),
    ("constraint-marina-berth-assignment", "constraint-medication-order-review"),
    ("constraint-delivery-locker-route", "constraint-railway-timetable-change"),
    ("constraint-hiking-checkpoint-route", "constraint-food-allergen-label"),
    ("constraint-library-cart-sort", "constraint-shipment-insurance-quote"),
    ("constraint-blood-sample-chain", "constraint-warehouse-return-authorization"),
    ("constraint-pharmacy-batch-release", "constraint-clinic-appointment-reschedule"),
    ("constraint-cargo-manifest-count", "constraint-school-bus-route-change"),
    ("constraint-invoice-tax-reconciliation", "constraint-election-district-update"),
    ("constraint-parcel-dimension-weight", "constraint-manufacturing-work-order"),
    ("constraint-sensor-range-calibration", "constraint-airline-itinerary-change"),
    ("constraint-rental-key-handoff", "constraint-loan-repayment-amendment"),
    ("constraint-bakery-batch-split", "constraint-subscription-plan-migration"),
    ("constraint-museum-loan-return", "constraint-habitat-restoration-survey"),
)


def _render_family(root: Path) -> None:
    for case in tasks.CASES:
        tasks._render_case(case, root / case.domain.task_id)


def test_inventory_is_exactly_one_hundred_unique_new_root_contracts() -> None:
    assert len(DOMAINS) == len(PREDICATE_TRIPLES) == len(tasks.CASES) == 100
    assert len({domain.task_id for domain in DOMAINS}) == 100
    assert len({tuple(rule.kind for rule in triple) for triple in PREDICATE_TRIPLES}) == 100
    assert {domain.capability for domain in DOMAINS} == {
        "coordinate_bounds_and_routes",
        "paired_field_consistency",
        "impossible_state_rejection",
        "atomic_validation_and_diagnostics",
    }
    assert all(task.domain.task_id.startswith("constraint-") for task in tasks.CASES)
    assert not ({task.domain.task_id for task in tasks.CASES} & tasks.OFFICIAL_HOLDOUTS)


def test_every_domain_owned_predicate_is_independently_witnessed() -> None:
    for triple in PREDICATE_TRIPLES:
        assert not any(predicate_fails(rule.kind, BASELINE) for rule in triple)
        for rule in triple:
            others = tuple(other for other in triple if other != rule)
            witness = witness_for(rule, others)
            assert witness is not None
            assert predicate_fails(rule.kind, witness)
            assert not any(predicate_fails(other.kind, witness) for other in others)


def test_rendering_is_deterministic_and_roles_are_private(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    _render_family(first)
    _render_family(second)
    assert tasks._tree_hash(first) == tasks._tree_hash(second)
    assert len(tasks._inventory(first)) == 100
    for case in tasks.CASES:
        root = first / case.domain.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [
            f"{case.domain.task_id}.h",
            f"{case.domain.task_id}.cpp",
        ]
        assert config["files"]["example"] == [
            ".meta/example.h",
            ".meta/example.cpp",
        ]
        prompt = tasks._validate_prompt_and_roles(root)
        assert prompt["solution"] == config["files"]["solution"]


def test_all_4950_pairs_have_independently_distinct_rule_sets_and_dimensions(tmp_path: Path) -> None:
    root = tmp_path / "family"
    _render_family(root)
    pair_count = 0
    for left, right in combinations(tasks.CASES, 2):
        pair_count += 1
        assert tuple(rule.kind for rule in left.rules) != tuple(rule.kind for rule in right.rules)
        decision = tasks._pair_decision(
            root / left.domain.task_id,
            root / right.domain.task_id,
        )
        assert set(decision["dimensions"]) == set(tasks.HARD_RULE_DIMENSIONS)
        for dimension in tasks.HARD_RULE_DIMENSIONS:
            row = decision["dimensions"][dimension]
            assert row["symmetric_difference"] > 0
            assert row["similarity"] < 0.995
            assert row["pass"] is True
    assert pair_count == 100 * 99 // 2 == 4950


def test_cycle_02_semantic_clone_pairs_are_canonicalized_and_materially_distinct(
    tmp_path: Path,
) -> None:
    root = tmp_path / "family"
    _render_family(root)
    by_id = {case.domain.task_id: case for case in tasks.CASES}
    for left_id, right_id in AUDITED_CLONE_PAIRS:
        left, right = by_id[left_id], by_id[right_id]
        left_contract = (
            tuple(tasks._rule_code(rule, left.domain.fields, 0) for rule in left.rules),
            tasks._certificate_code(left, left.domain.fields, 0),
        )
        right_contract = (
            tuple(tasks._rule_code(rule, right.domain.fields, 0) for rule in right.rules),
            tasks._certificate_code(right, right.domain.fields, 0),
        )
        assert left_contract != right_contract
        assert tasks._pair_decision(root / left_id, root / right_id)["pass"] is True


def test_host_verify_work_labels_are_unique_across_roots_and_controls(
    tmp_path: Path,
) -> None:
    root = tmp_path / "family"
    _render_family(root)
    controls = tasks._materialize_controls(root)
    roots = [root / case.domain.task_id for case in tasks.CASES]
    control_roots = [root / row["root"] for row in controls.values()]
    labels = [tasks._host_work_label(root, path) for path in (*roots, *control_roots)]
    assert len(labels) == 103
    assert len(set(labels)) == 103
    assert all("/" not in label and label for label in labels)
    # The original defect: a control re-rendering a candidate shares its
    # basename, so basename-derived work directories collide.
    base_names = [path.name for path in (*roots, *control_roots)]
    assert len(set(base_names)) < len(base_names)


@pytest.mark.parametrize("kind", tasks.ADVERSARIAL_CONTROLS)
def test_genuine_clone_controls_change_files_and_fail_all_dimensions(
    tmp_path: Path, kind: str
) -> None:
    root = tmp_path / "family"
    _render_family(root)
    controls = tasks._materialize_controls(root)
    row = controls[kind]
    assert row["changed"] is True
    assert row["changed_files"]
    assert row["base_tree_hash"] != row["control_tree_hash"]
    assert row["rejected_in_all_seven_dimensions"] is True
    assert set(row["production_evaluator"]["dimensions"]) == set(
        tasks.HARD_RULE_DIMENSIONS
    )
    assert all(
        decision["pass"] is False
        for decision in row["production_evaluator"]["dimensions"].values()
    )


def test_each_compiled_false_substitute_omits_only_its_named_primary_rule(
    tmp_path: Path,
) -> None:
    root = tmp_path / "family"
    _render_family(root)
    for case in tasks.CASES:
        task_root = root / case.domain.task_id
        reference = (task_root / ".meta/example.cpp").read_text()
        negative = (task_root / ".meta/negative_fixture.cpp").read_text()
        hidden = (task_root / ".meta/task_hidden_test.cpp").read_text()
        primary_name = case.rules[0].error
        assert f"::{primary_name}" in reference
        assert f"::{primary_name}" not in negative
        assert f"::{primary_name}" in hidden
        for secondary in case.rules[1:]:
            name = secondary.error
            assert f"::{name}" in reference
            assert f"::{name}" in negative
            assert f"::{name}" in hidden
        wrong_success = (task_root / ".meta/wrong_success_fixture.cpp").read_text()
        assert "::none, 1 + 0LL" in wrong_success
        assert "numeric_limits<int>::min" in hidden
        assert "numeric_limits<int>::max" in hidden
        assert "const long long" in reference


def test_output_guard_rejects_protected_and_non_expansion_paths(tmp_path: Path) -> None:
    with pytest.raises(tasks.VerificationError, match="protected_output_root"):
        tasks._validate_output(Path(".w8-biayn/data/aider-tasks/new-family"))
    with pytest.raises(tasks.VerificationError, match="protected_output_root"):
        tasks._validate_output(Path(".w8-biayn/data/aider-tasks-reverify/new-family"))
    with pytest.raises(tasks.VerificationError, match="unsafe_output_root"):
        tasks._validate_output(tmp_path / "outside-expansion")


def test_current_exact_tree_receipt_has_all_required_hard_rule_evidence() -> None:
    state = tasks.DEFAULT_OUT / ".state"
    screen_path = state / "family-screen.json"
    if not screen_path.exists():
        pytest.skip("generated expansion family is local ignored state")
    screen = json.loads(screen_path.read_text())
    assert screen["root_count"] == 100
    assert screen["pair_count"] == screen["expected_pair_count"] == 4950
    assert screen["dimensions"] == list(tasks.HARD_RULE_DIMENSIONS)
    assert len(screen["pairs"]) == 4950
    assert all(pair["pass"] for pair in screen["pairs"])
    assert screen["corpus_screen"]["status"] == "pass"
    assert screen["prompt_boundary"]["status"] == "pass"
    tasks._validate_frozen_pre_docker_subject(tasks.DEFAULT_OUT)
    source = json.loads((state / "source-inventory.json").read_text())
    comparison = json.loads((state / "comparison-manifest.json").read_text())
    assert screen["corpus_screen"]["comparison_count"] == 100 * (
        sum(source["counts"].values()) + 26
    )
    assert comparison["holdout_revision"]
    records = comparison["snapshot_records"]
    assert len(records) == sum(source["counts"].values()) + 26
    assert sum(row["scope"] == "official_holdout" for row in records.values()) == 26
    assert comparison["snapshot_blob_count"] <= len(records)
    snapshot_root = state / "comparison-snapshot"
    assert comparison["snapshot_root_hash"] == tasks._tree_hash(snapshot_root)
    for row in records.values():
        blob = tasks.DEFAULT_OUT / row["blob"]
        blob_bytes = blob.read_bytes()
        assert tasks._sha256(blob_bytes) == row["blob_hash"]
        features = tasks._ngrams(tasks._semantic_tokens(tasks._snapshot_blob(blob_bytes)), 4)
        assert tasks._sha256(tasks._json_bytes(sorted(features))) == row["semantic_feature_hash"]
    if (state / "docker-sanity.json").exists():
        docker = json.loads((state / "docker-sanity.json").read_text())
        preflight = json.loads((state / "creator-preflight.json").read_text())
        manifest_bytes = (state / "candidate-manifest.json").read_bytes()
        assert docker["candidate_manifest_hash"] == tasks._sha256(manifest_bytes)
        assert docker["family_screen_hash"] == tasks._sha256(screen_path.read_bytes())
        assert preflight["docker_sanity_hash"] == tasks._sha256(
            (state / "docker-sanity.json").read_bytes()
        )
        assert docker["compiler_path"].startswith("/")
        assert len(docker["compiler_sha256"]) == 64
        assert docker["normal_test_count"] == docker["sanitizer_test_count"] == 412
        assert docker["topic_negative_rejections"] == 103
        assert docker["wrong_success_rejections"] == 103
