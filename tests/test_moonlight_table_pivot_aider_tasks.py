from __future__ import annotations

import inspect
import json
from itertools import combinations
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_table_pivot_aider_tasks as tasks


def test_materializes_twenty_distinct_remediated_roots(tmp_path: Path) -> None:
    roots = tasks.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {case.task_id for case in tasks.CASES}
    assert len({case.profile for case in tasks.CASES}) == 20
    assert len({case.public_api for case in tasks.CASES}) == 20
    assert len({case.marker for case in tasks.CASES}) == 20
    for case, root in zip(tasks.CASES, roots, strict=True):
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["legacy_task_id"] == case.legacy_id
        assert provenance["semantic_profile"] == case.profile
        assert provenance["primary_core_objective"] == "achieved"
        assert case.marker in (root / ".meta/example.cpp").read_text()
        assert (root / ".meta/negative_false_substitute.cpp").is_file()


def test_remedies_account_for_every_legacy_root(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    records = []
    for case in tasks.CASES:
        record_path = tmp_path / ".state/remedy" / f"{case.task_id}.json"
        spec_path = tmp_path / ".state/remedy" / f"{case.task_id}.md"
        record = json.loads(record_path.read_text())
        records.append(record)
        assert record["schema_version"] == "aider-task-remedy-v1"
        assert record["legacy_task_id"] == case.legacy_id
        assert record["tree_hash_before"] == tasks._tree_hash(tasks.LEGACY_ROOT / case.legacy_id)
        assert record["remedy_spec_hash"] == tasks._sha_bytes(spec_path.read_bytes())
        assert tuple(
            line.removeprefix("## ")
            for line in spec_path.read_text().splitlines()
            if line.startswith("## ")
        ) == tasks.REMEDY_HEADINGS
    assert sum(record["disposition"] == "repair-in-place" for record in records) == 1
    assert sum(record["disposition"] == "replace" for record in records) == 19


def test_core_verifier_checks_all_pairs_roles_controls_and_holdouts(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    tasks.verify_core(tmp_path)
    manifest = json.loads(
        (tmp_path / ".state/materialization-manifest.json").read_text()
    )
    emitted_ids = sorted(
        path.name
        for path in tmp_path.iterdir()
        if path.is_dir() and path.name != ".state"
    )
    expected_ids = sorted(case.task_id for case in tasks.CASES)
    assert emitted_ids == expected_ids
    assert manifest["task_count"] == 20
    assert sorted(manifest["task_ids"]) == expected_ids
    assert manifest["status"] == "implemented"
    assert manifest["screen"]["prompt_boundary"] == "pass"
    assert manifest["screen"]["reference_mapping"] == "pass"
    hard_rule = manifest["screen"]["hard_rule"]
    assert hard_rule["pair_count"] == hard_rule["expected_pair_count"] == 190
    assert tuple(hard_rule["dimensions"]) == tasks.HARD_RULE_DIMENSIONS
    assert len(hard_rule["pairs"]) == 190
    expected_pairs = set(combinations(expected_ids, 2))
    actual_pairs = {
        tuple(sorted((item["left"], item["right"]))) for item in hard_rule["pairs"]
    }
    assert actual_pairs == expected_pairs
    # Recompute every decision from the emitted bytes and the low-level metric;
    # do not trust the production comparator's aggregate result.
    dimensions = {
        task_id: tasks._artifact_dimensions(tmp_path / task_id)
        for task_id in expected_ids
    }
    for item in hard_rule["pairs"]:
        assert len(item["dimensions"]) == len(tasks.HARD_RULE_DIMENSIONS)
        assert set(item["dimensions"]) == set(tasks.HARD_RULE_DIMENSIONS)
        assert item["all_dimensions_materially_distinct"] is True
        for dimension in tasks.HARD_RULE_DIMENSIONS:
            independent_score = tasks._containment(
                dimensions[item["left"]][dimension],
                dimensions[item["right"]][dimension],
            )
            decision = item["dimensions"][dimension]
            assert decision["score"] == pytest.approx(independent_score)
            assert decision["limit"] == tasks.HARD_RULE_LIMITS[dimension]
            assert independent_score < tasks.HARD_RULE_LIMITS[dimension]
            assert decision["materially_distinct"] is True
    controls = manifest["screen"]["adversarial_controls"]
    assert set(controls) == {
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
    }
    assert all(item["reason"] == "duplicate_family" for item in controls.values())
    holdout = manifest["screen"]["semantic_holdout"]
    if tasks.DEFAULT_HOLDOUT_ROOT.is_dir():
        assert holdout["status"] == "pass"
        assert holdout["holdout_root_count"] == 26
        assert holdout["comparison_count"] == 520
    else:
        assert holdout["status"] == "not_completed"


def test_adversarial_controls_are_coherent_mutations_rejected_by_exact_comparator(
    tmp_path: Path,
) -> None:
    tasks.build(tmp_path)
    base_root = tmp_path / tasks.CASES[0].task_id
    controls_root = tmp_path / ".state/hard-rule-controls"
    control_manifest = json.loads((controls_root / "manifest.json").read_text())
    assert control_manifest["schema_version"] == "table-pivot-hard-rule-controls-v2"
    expected_changed = {
        "domain-identifier-renamed-clone": {
            f"{tasks.CASES[0].task_id}.h",
            ".meta/example.h",
            ".meta/example.cpp",
            ".meta/negative_false_substitute.cpp",
            "task_visible_test.cpp",
            ".meta/task_hidden_test.cpp",
            ".docs/instructions.md",
        },
        "constants-policy-clone": {
            ".docs/instructions.md",
            ".meta/example.cpp",
            ".meta/negative_false_substitute.cpp",
            ".meta/task_hidden_test.cpp",
        },
        "opposite-end-selection-clone": {
            ".docs/introduction.md",
            ".docs/instructions.md",
            ".meta/config.json",
            ".meta/provenance.json",
            ".meta/example.cpp",
            ".meta/negative_false_substitute.cpp",
            "task_visible_test.cpp",
            ".meta/task_hidden_test.cpp",
        },
    }
    base_files = {
        path.relative_to(base_root).as_posix(): path.read_bytes()
        for path in base_root.rglob("*")
        if path.is_file()
    }
    base_dimensions = tasks._artifact_dimensions(base_root)
    outcomes = tasks._screen_controls(tmp_path)
    for name, metadata in control_manifest["controls"].items():
        root = controls_root / name
        control_files = {
            path.relative_to(root).as_posix(): path.read_bytes()
            for path in root.rglob("*")
            if path.is_file()
        }
        assert set(control_files) == set(base_files)
        actual_changed = {
            relative
            for relative in base_files
            if base_files[relative] != control_files[relative]
        }
        assert actual_changed
        assert actual_changed == set(metadata["changed_files"])
        assert expected_changed[name] <= actual_changed
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [
            f"{tasks.CASES[0].task_id}.h",
            f"{tasks.CASES[0].task_id}.cpp",
        ]
        assert '#include "pivot-call-center.h"' in (
            root / ".meta/example.cpp"
        ).read_text()
        clone_dimensions = tasks._artifact_dimensions(root)
        independent_failures = []
        for dimension in tasks.HARD_RULE_DIMENSIONS:
            score = tasks._containment(
                base_dimensions[dimension], clone_dimensions[dimension]
            )
            if score >= tasks.HARD_RULE_LIMITS[dimension]:
                independent_failures.append(dimension)
            stored = outcomes[name]["dimensions"][dimension]
            assert stored["score"] == pytest.approx(score)
            assert stored["materially_distinct"] == (
                score < tasks.HARD_RULE_LIMITS[dimension]
            )
        assert independent_failures
        assert outcomes[name]["rejection_dimensions"] == independent_failures
        with pytest.raises(RuntimeError, match="^duplicate_family:"):
            tasks._compare_dimensions(
                base_dimensions,
                clone_dimensions,
                tasks.CASES[0].task_id,
                name,
            )

    domain_header = (
        controls_root
        / "domain-identifier-renamed-clone"
        / f"{tasks.CASES[0].task_id}.h"
    ).read_text()
    assert "DeskRecord" in domain_header and "ClerkDesks" in domain_header
    policy_root = controls_root / "constants-policy-clone"
    assert "strictly positive handled count" in (
        policy_root / ".docs/instructions.md"
    ).read_text()
    assert "call.handled<=0" in (policy_root / ".meta/example.cpp").read_text()
    latest_root = controls_root / "opposite-end-selection-clone"
    assert "latest-shift tie rule" in (
        latest_root / ".docs/introduction.md"
    ).read_text()
    assert "busiest_shift==1" in (latest_root / "task_visible_test.cpp").read_text()


def test_each_topic_negative_is_distinct_and_mutated(tmp_path: Path) -> None:
    roots = tasks.build(tmp_path)
    signatures = set()
    for case, root in zip(tasks.CASES, roots, strict=True):
        negative = (root / ".meta/negative_false_substitute.cpp").read_text()
        assert negative != case.reference
        assert case.negative_new in negative
        signatures.add(tasks._normalized_tokens(negative))
    assert len(signatures) == 20


def test_references_make_strict_whole_file_answers(tmp_path: Path) -> None:
    for root in tasks.build(tmp_path):
        task = moonlight_aider_task_sft.load_task(root)
        answer = moonlight_aider_task_sft.build_assistant_response(
            task,
            moonlight_aider_task_sft.load_example_files_from_config(root),
        )
        assert answer.startswith(f"{root.name}.h\n```")
        assert f"{root.name}.cpp\n```" in answer
        assert ".meta/example" not in answer


def test_force_regeneration_invalidates_receipts(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    state = tmp_path / ".state"
    for name in (
        "materialization-manifest.json",
        "host-verification-receipt.json",
        "docker-sanity.json",
    ):
        (state / name).write_text("stale")
    tasks.build(tmp_path, force=True)
    for name in (
        "materialization-manifest.json",
        "host-verification-receipt.json",
        "docker-sanity.json",
    ):
        assert not (state / name).exists()
    invalidations = list((state / "invalidated").glob("*/invalidation.json"))
    assert len(invalidations) == 1
    invalidation = json.loads(invalidations[0].read_text())
    assert invalidation["invalidated_claim"] == "local_family_verified"
    assert invalidation["reason"] == "hard_rule_controls_and_independent_assertions_stale"
    assert set(invalidation["evidence_hashes"]) == {
        "materialization-manifest.json",
        "host-verification-receipt.json",
        "docker-sanity.json",
    }


def test_idempotent_build_preserves_verified_remedy_state(tmp_path: Path) -> None:
    tasks.build(tmp_path)
    path = tmp_path / ".state/remedy" / f"{tasks.CASES[0].task_id}.json"
    record = json.loads(path.read_text())
    record["status"] = "verified"
    record["tree_hash_after"] = "sha256:receipt-bound"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    tasks.build(tmp_path)
    assert json.loads(path.read_text())["tree_hash_after"] == "sha256:receipt-bound"


def test_legacy_output_is_refused() -> None:
    with pytest.raises(RuntimeError, match="legacy_root_immutable"):
        tasks.build(tasks.LEGACY_ROOT, force=True)


def test_docker_sanity_owns_required_runtime_contract() -> None:
    source = inspect.getsource(tasks.docker_sanity)
    assert '"--network", "none"' in source
    assert '"Unix Makefiles"' in source
    assert "-fsanitize=address,undefined" in source
    assert "grader_mount_hash_mismatch" in source
    assert "MOUNT_HASH" in source
    assert "compiler_hash" in source
    assert "reference_hash" in source
    assert '"owner_path": GENERATOR_PATH' in source
    assert '"hard_rule_screen_hash"' in source
    assert '"control_manifest_hash"' in source
    assert '"invalidation_records"' in source
    assert source.index('manifest["screen"]["hard_rule"]["status"] = "pass"') < source.index(
        "receipt = {"
    )
    assert "sanitizer_test_count_mismatch" in inspect.getsource(tasks.verify)
    assert "negative_fixture_not_rejected" in inspect.getsource(tasks.verify)


def test_wrapper_targets_parallel_reverify_tree() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_table_pivot_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_table_pivot_aider_tasks" in content
    assert "aider-tasks-reverify/aider-text-grid-reshaping/table-pivot" in content
