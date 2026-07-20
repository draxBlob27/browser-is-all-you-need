from __future__ import annotations

import inspect
import itertools
import json
import shutil
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_cross_midnight_aider_tasks as midnight
from w8_biayn.integrations import moonlight_cross_midnight_hard_rule as hard_rule


def _plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    source = midnight.DEFAULT_OUT / ".state/remedy"
    target = tmp_path / ".state/remedy"
    target.mkdir(parents=True)
    for path in source.iterdir():
        (target / path.name).write_bytes(path.read_bytes())
    monkeypatch.setattr(midnight, "DEFAULT_OUT", tmp_path)
    return tmp_path


def test_materializes_exactly_eight_counted_roots_and_preserves_two_rejections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _plan(tmp_path, monkeypatch)
    roots = midnight.build(out, force=True)
    assert len(roots) == 8
    assert 8 <= len(roots) <= 12
    assert len({case.task_id for case in midnight.CASES}) == 8
    assert len({case.profile for case in midnight.CASES}) == 8
    assert all(case.task_id != case.legacy_id for case in midnight.CASES)
    for case, root in zip(midnight.CASES, roots, strict=True):
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        remedy = json.loads((out / ".state/remedy" / f"{case.task_id}.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["family_id"] == midnight.FAMILY_ID
        assert provenance["legacy_task_id"] == case.legacy_id
        assert remedy["disposition"] == "replace"
        assert remedy["status"] in {"planned", "implemented", "verified"}
        assert remedy["primary_core_objective"] == "achieved"
    for case in midnight.REJECTED_CASES:
        remedy = json.loads((out / ".state/remedy" / f"{case.task_id}.json").read_text())
        assert remedy["disposition"] == "reject" and remedy["status"] == "rejected"
        assert remedy["primary_core_objective"] == "not_achieved"
        assert not (out / case.task_id).exists()


def test_independently_inspects_every_material_decision_for_all_28_pairs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _plan(tmp_path, monkeypatch)
    roots = midnight.build(out, force=True)
    manifest = midnight.verify_core(out, Path("/missing/holdouts"))
    hard = manifest["screen"]["hard_rule"]
    assert hard["root_count"] == 8
    assert hard["pair_count"] == hard["expected_pair_count"] == 28
    assert hard["dimensions"] == list(hard_rule.HARD_DIMENSIONS)
    expected_pairs = {
        tuple(sorted((left.name, right.name)))
        for left, right in itertools.combinations(roots, 2)
    }
    assert {tuple(sorted((pair["left"], pair["right"]))) for pair in hard["pairs"]} == expected_pairs
    for root_name, evidence in hard["artifact_evidence"].items():
        assert evidence["root"] == root_name
        assert set(evidence["dimensions"]) == set(hard_rule.HARD_DIMENSIONS)
        for dimension in hard_rule.HARD_DIMENSIONS:
            row = evidence["dimensions"][dimension]
            assert row["valid"] is True
            assert len(row["matching_profiles"]) == 1
            assert len(row["facts"]) >= 3
            assert all(fact["matched"] for fact in row["facts"])
    for dimension in hard_rule.HARD_DIMENSIONS:
        profiles = {
            evidence["dimensions"][dimension]["profile"]
            for evidence in hard["artifact_evidence"].values()
        }
        assert len(profiles) == 8
    for pair in hard["pairs"]:
        assert set(pair["dimensions"]) == set(hard_rule.HARD_DIMENSIONS)
        for dimension in hard_rule.HARD_DIMENSIONS:
            decision = pair["dimensions"][dimension]
            assert decision["left_evidence_valid"] and decision["right_evidence_valid"]
            assert decision["material_profile_distinct"]
            assert decision["left_profile"] != decision["right_profile"]
            assert decision["left_fact_count"] >= 3 and decision["right_fact_count"] >= 3
            assert decision["normalized_similarity"] < decision["maximum_similarity"]
            assert decision["similarity_pass"] and decision["pass"]
        assert pair["pass"]
    assert manifest["screen"]["benchmark_contamination"]["status"] == "not_completed"


def test_hash_inequality_is_not_material_diversity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _plan(tmp_path, monkeypatch)
    source = midnight.build(out, force=True)[0]
    clone = tmp_path / ".state/comment-only-clone"
    shutil.copytree(source, clone)
    docs = clone / ".docs/introduction.md"
    docs.write_text(docs.read_text() + "\nA comment-only/domain-neutral revision.\n")
    assert midnight._tree_hash(source) != midnight._tree_hash(clone)
    comparison = hard_rule.compare_roots(source, clone)
    assert comparison["pass"] is False
    assert all(
        not decision["material_profile_distinct"]
        for decision in comparison["dimensions"].values()
    )


def test_coherent_controls_change_intended_files_and_production_rejects_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _plan(tmp_path, monkeypatch)
    midnight.build(out, force=True)
    screen = midnight._control_screen(out)
    assert screen["status"] == "pass"
    assert {row["name"] for row in screen["controls"]} == {
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
    }
    for row in screen["controls"]:
        assert row["changed"] and row["rejected"]
        assert row["comparison"]["pass"] is False
        assert any(
            not decision["pass"]
            for decision in row["comparison"]["dimensions"].values()
        )
    controls = out / ".state/controls"
    control_hashes = {
        path.name: midnight._tree_hash(path)
        for path in controls.iterdir()
        if path.is_dir()
    }
    assert len(set(control_hashes.values())) == 3
    assert "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" not in control_hashes.values()
    assert "Garage" in (controls / "domain-identifier-renamed-clone/.meta/example.h").read_text()
    assert "x.total_cents==300" in (controls / "constants-policy-clone/task_visible_test.cpp").read_text()
    assert "c.route_id==3" in (controls / "opposite-end-selection-clone/task_visible_test.cpp").read_text()


def test_every_counted_root_has_a_distinct_nonempty_topic_negative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = _plan(tmp_path, monkeypatch)
    roots = midnight.build(out, force=True)
    profiles = set()
    for case, root in zip(midnight.CASES, roots, strict=True):
        negative = (root / ".meta/negative_false_substitute.cpp").read_text()
        reference = (root / ".meta/example.cpp").read_text()
        assert negative != reference
        assert case.negative_old not in negative and case.negative_new in negative
        evidence = hard_rule.analyze_root(root)["dimensions"]["topic_negative_fixture"]
        assert evidence["valid"] and len(evidence["facts"]) >= 3
        profiles.add(evidence["profile"])
    assert len(profiles) == 8


def test_references_make_strict_whole_file_answers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = _plan(tmp_path, monkeypatch)
    for root in midnight.build(out, force=True):
        task = moonlight_aider_task_sft.load_task(root)
        answer = moonlight_aider_task_sft.build_assistant_response(
            task, moonlight_aider_task_sft.load_example_files_from_config(root)
        )
        assert answer.startswith(f"{root.name}.h\n```")
        assert f"{root.name}.cpp\n```" in answer
        assert ".meta/example" not in answer


def test_docker_verifier_owns_network_hash_sanitizer_and_negative_gates() -> None:
    source = inspect.getsource(midnight.docker_sanity)
    script = midnight.DOCKER_SCRIPT
    assert '"--network", "none"' in source
    assert '"Unix Makefiles"' in script
    assert "-fsanitize=address,undefined" in script
    assert "build-negative" in script
    assert "TREEHASH" in script and "grader_mount_hash_mismatch" in source
    assert "relative_to(root).parts" in script
    assert set(midnight._owner_source_hashes()) == {"materializer", "cases", "hard_rule"}
    assert "local_family_verified" in source
    assert "sanitizer_test_count_mismatch" in source


def test_wrapper_targets_parallel_user_requested_family_type() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_cross_midnight_aider_tasks.sh")
    assert wrapper.exists() and wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_cross_midnight_aider_tasks" in content
    assert "aider-tasks-reverify/aider-text-grid-reshaping/cross-midnight-intervals" in content
