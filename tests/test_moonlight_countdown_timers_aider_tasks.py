from __future__ import annotations

import inspect
import itertools
import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_countdown_timers_aider_tasks as timers


def test_materializes_ten_repaired_roots_with_role_correct_files(tmp_path: Path) -> None:
    roots = timers.build(tmp_path)
    assert timers.MIN_ROOTS == 8
    assert timers.MAX_ROOTS == 12
    assert len(roots) == 10
    assert timers.MIN_ROOTS <= len(roots) <= timers.MAX_ROOTS
    assert {root.name for root in roots} == {spec.task_id for spec in timers.TASKS}
    assert len(set(timers.PROFILES.values())) == 10
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["family_id"] == timers.FAMILY_ID
        assert provenance["family_type"] == "aider-dates-and-clocks"
        assert provenance["requested_family_type"] == "aider-text-grid-reshaping"
        assert (root / ".meta/negative_false_substitute.cpp").is_file()


def test_core_verifier_records_exact_all_pairs_and_seven_dimensions(tmp_path: Path) -> None:
    timers.build(tmp_path)
    timers.verify_core(tmp_path)
    manifest = json.loads((tmp_path / ".state/materialization-manifest.json").read_text())
    hard_rule = manifest["screen"]["hard_rule"]
    assert manifest["task_count"] == 10
    assert hard_rule["root_count"] == 10
    assert hard_rule["minimum_root_count"] == 8
    assert hard_rule["maximum_root_count"] == 12
    assert hard_rule["pair_count"] == 45
    assert hard_rule["expected_pair_count"] == 45
    assert hard_rule["dimensions"] == list(timers.HARD_RULE_DIMENSIONS)
    expected_pairs = {
        tuple(sorted(pair))
        for pair in itertools.combinations((spec.task_id for spec in timers.TASKS), 2)
    }
    recorded_pairs = {
        tuple(sorted((row["left"], row["right"]))) for row in hard_rule["pairs"]
    }
    assert recorded_pairs == expected_pairs
    for row in hard_rule["pairs"]:
        assert set(row["dimensions"]) == {*timers.HARD_RULE_DIMENSIONS, "pass"}
        assert row["dimensions"]["pass"] is True
        for dimension in timers.HARD_RULE_DIMENSIONS:
            decision = row["dimensions"][dimension]
            assert set(decision) == {"containment", "limit", "distinct"}
            assert decision["distinct"] is True
            assert decision["containment"] < decision["limit"]
    assert manifest["screen"]["semantic_holdout"]["holdout_root_count"] == 26
    assert manifest["screen"]["semantic_holdout"]["comparison_count"] == 260


def test_adversarial_controls_change_files_and_production_screen_rejects(tmp_path: Path) -> None:
    timers.build(tmp_path)
    controls = timers._screen_controls(tmp_path)
    assert set(controls) == {
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
    }
    for name, row in controls.items():
        assert row["changed_files"]
        assert row["candidate_hash"].startswith("sha256:")
        assert row["semantic_screen"] == "rejected:duplicate_family"
        assert row["dimensions"]["pass"] is False
        assert any(
            not row["dimensions"][dimension]["distinct"]
            for dimension in timers.HARD_RULE_DIMENSIONS
        )
        control = tmp_path / ".state/hard-rule-controls" / name
        assert (control / "candidate.cpp").read_bytes()
        assert (control / "CMakeLists.txt").is_file()
        assert (control / "task_visible_test.cpp").is_file()
        assert (control / ".meta/task_hidden_test.cpp").is_file()


def test_every_topic_negative_is_changed_distinct_and_bound_to_tests(tmp_path: Path) -> None:
    roots = timers.build(tmp_path)
    normalized: set[tuple[str, ...]] = set()
    assert set(timers.NEGATIVE_MUTATIONS) == {spec.task_id for spec in timers.TASKS}
    for spec, root in zip(timers.TASKS, roots, strict=True):
        negative, reason = timers._negative_source(spec)
        assert reason
        assert negative != spec.reference
        emitted = (root / ".meta/negative_false_substitute.cpp").read_text()
        old, new, _ = timers.NEGATIVE_MUTATIONS[spec.task_id]
        assert old not in emitted
        assert new in emitted
        signature = timers._normalized_tokens(emitted)
        assert signature not in normalized
        normalized.add(signature)
    assert len(normalized) == 10


def test_grace_band_remedy_is_executable_and_negative_is_exact_boundary() -> None:
    spec = next(spec for spec in timers.TASKS if spec.task_id == "timer-evacuation-drill")
    assert "+stages_[i].grace" in spec.reference
    assert "grace.first_failure==-1" in spec.hidden
    assert "late.first_failure==0" in spec.hidden
    negative, _ = timers._negative_source(spec)
    assert ">=static_cast<long long>(stages_[i].deadline)+stages_[i].grace" in negative


def test_remedies_precede_verified_state_and_bind_legacy_hashes(tmp_path: Path) -> None:
    timers.build(tmp_path)
    for spec in timers.TASKS:
        record = json.loads((tmp_path / ".state/remedy" / f"{spec.task_id}.json").read_text())
        markdown = (tmp_path / ".state/remedy" / f"{spec.task_id}.md").read_text()
        assert record["status"] == "planned"
        assert record["disposition"] == "repair-in-place"
        assert record["tree_hash_before"] == timers._tree_hash(timers.LEGACY_ROOT / spec.task_id)
        assert record["remedy_spec_hash"] == timers._sha_bytes(markdown.encode())
        positions = [markdown.index(f"## {heading}") for heading in timers.REMEDY_HEADINGS]
        assert positions == sorted(positions)


def test_legacy_output_is_refused() -> None:
    with pytest.raises(RuntimeError, match="legacy_root_immutable"):
        timers.build(timers.LEGACY_ROOT, force=True)


def test_docker_verifier_owns_required_snapshot_safe_contract() -> None:
    source = inspect.getsource(timers.docker_sanity)
    assert '"--network", "none"' in source
    assert '"Unix Makefiles"' in source
    assert "-fsanitize=address,undefined" in source
    assert "grader_mount_hash_mismatch" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "topic-negative.tsv" in source
    assert "adversarial-controls.tsv" in source
    assert "negative_fixture_not_rejected" in source


def test_wrapper_targets_parallel_reverify_tree() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_countdown_timers_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_countdown_timers_aider_tasks" in content
    assert "aider-tasks-reverify/aider-dates-and-clocks/countdown-timers" in content
