from __future__ import annotations

import hashlib
import json
import re
from itertools import combinations
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import (
    moonlight_modular_clock_normalization_aider_tasks as modular,
)


def _independent_semantic_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.M | re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " STRING ", text)
    text = re.sub(r"\b(?:0[xX][0-9a-fA-F]+|\d+)\b", " NUMBER ", text)
    return tuple(re.findall(r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\S", text))


def _digest(text: str) -> str:
    return hashlib.sha256("\0".join(_independent_semantic_tokens(text)).encode()).hexdigest()


@pytest.fixture()
def materialized(tmp_path: Path) -> Path:
    modular.build(tmp_path, test_mode=True)
    return tmp_path


def test_curriculum_binds_exact_count_plan_cell_and_sixty_unique_cases() -> None:
    assert modular.EXPECTED_ROOTS == 60
    assert len(modular.CASES) == len({case.task_id for case in modular.CASES}) == 60
    assert [len(modular.NORMALIZATION_CASES), len(modular.SEQUENCE_CASES), len(modular.OFFSET_CASES)] == [20, 20, 20]
    assert len({case.class_name for case in modular.CASES}) == 60
    assert len({case.api for case in modular.CASES}) == 60
    assert len({case.mechanism for case in modular.CASES}) == 60
    assert len({case.boundary for case in modular.CASES}) == 60
    curriculum = (modular.REPO_ROOT / modular.CURRICULUM).read_text()
    count_plan = (modular.REPO_ROOT / modular.COUNT_PLAN).read_text()
    assert "modular clock normalization" in curriculum.lower()
    assert "60" in curriculum
    assert "Modular clock normalization" in count_plan
    assert modular.DEFAULT_OUT == Path(
        ".w8-biayn/data/aider-tasks-expansion-v1/time-date/modular-clock-normalization"
    )


def test_materialization_is_expansion_owned_and_role_safe(materialized: Path) -> None:
    roots = tuple(path for path in materialized.iterdir() if path.is_dir() and path.name != ".state")
    assert len(roots) == 60
    assert {root.name for root in roots} == {case.task_id for case in modular.CASES}
    inventories = json.loads((materialized / ".state/source-inventories.json").read_text())
    assert set(inventories) == {"legacy", "reverify", "expansion"}
    assert all(value["inventory_hash"].startswith("sha256:") for value in inventories.values())
    for case in modular.CASES:
        root = materialized / case.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert config["files"]["test"] == ["task_visible_test.cpp"]
        assert provenance["lineage"] == {"relation": "new-root", "parent": None}
        assert set(provenance["semantic_anchors"]) == set(modular.HARD_RULE_DIMENSIONS)
        assert all(value.startswith("sha256:") for value in provenance["semantic_anchors"].values())
        assert (root / ".meta/task_hidden_test.cpp").is_file()
        assert (root / ".meta/negative_false_substitute.cpp").is_file()


def test_core_screen_recomputes_every_pair_and_rejects_controls(materialized: Path) -> None:
    manifest = modular.verify_core(materialized, test_mode=True)
    screen = json.loads((materialized / ".state/hard-rule-screen.json").read_text())
    assert manifest["task_count"] == 60
    assert screen["status"] == "pass"
    assert screen["pair_count"] == 60 * 59 // 2 == 1770
    expected = {
        frozenset((left.task_id, right.task_id))
        for left, right in combinations(modular.CASES, 2)
    }
    assert {frozenset((row["left"], row["right"])) for row in screen["pairs"]} == expected
    for row in screen["pairs"]:
        assert row["materially_distinct_in_all_dimensions"] is True
        assert row["failed_dimensions"] == []
        assert set(row["dimensions"]) == set(modular.HARD_RULE_DIMENSIONS)
        assert all(item["similarity"] < item["limit"] for item in row["dimensions"].values())
    assert set(screen["adversarial_controls"]) == set(modular.ADVERSARIAL_CONTROLS)
    for control in screen["adversarial_controls"].values():
        assert control["status"] == "rejected"
        assert control["reason"] == "duplicate_family"
        assert control["decision"]["failed_dimensions"]
    assert screen["cross_tree"]["status"] == "pass"
    inventories = json.loads((materialized / ".state/source-inventories.json").read_text())
    assert screen["cross_tree"]["source_counts"]["expansion_non_subject"] == (
        inventories["expansion"]["root_count"] - 60
    )
    assert screen["cross_tree"]["comparison_count"] == 60 * sum(
        screen["cross_tree"]["source_counts"].values()
    )
    assert screen["holdout"]["status"] == "pass"


def test_independent_artifact_checks_bind_anchors_without_using_them_as_diversity_evidence(materialized: Path) -> None:
    reference_digests: set[str] = set()
    oracle_digests: set[str] = set()
    anchor_sets: set[tuple[str, ...]] = set()
    for case in modular.CASES:
        root = materialized / case.task_id
        header = (root / f"{case.task_id}.h").read_text()
        reference = (root / ".meta/example.cpp").read_text()
        visible = (root / "task_visible_test.cpp").read_text()
        hidden = (root / ".meta/task_hidden_test.cpp").read_text()
        negative = (root / ".meta/negative_false_substitute.cpp").read_text()
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert case.class_name in header and case.class_name in reference
        assert case.negative_old in reference and case.negative_new in negative
        assert reference != negative
        reference_digests.add(_digest(modular._strip_reference_scaffold(reference)))
        oracle_digests.add(_digest(visible + hidden))
        anchor_sets.add(tuple(provenance["semantic_anchors"][key] for key in modular.HARD_RULE_DIMENSIONS))
    assert len(reference_digests) == len(oracle_digests) == len(anchor_sets) == 60


def test_controls_are_changed_coherent_near_clones(materialized: Path) -> None:
    manifest = json.loads((materialized / ".state/hard-rule-controls/manifest.json").read_text())
    for name, record in manifest["controls"].items():
        root = materialized / ".state/hard-rule-controls" / name
        assert record["changed_files"]
        assert record["expected_compile"] == "pass"
        assert record["expected_tests"] == "pass"
        base = next(case for case in modular.CASES if case.task_id == record["base_task"])
        base_anchors = json.loads((materialized / base.task_id / ".meta/provenance.json").read_text())["semantic_anchors"]
        clone_anchors = json.loads((root / ".meta/provenance.json").read_text())["semantic_anchors"]
        assert clone_anchors != base_anchors
        decision = modular._pair_decision(
            base.task_id,
            name,
            modular._artifact_dimensions(materialized / base.task_id),
            modular._artifact_dimensions(root, control=True),
        )
        assert decision["failed_dimensions"]


def test_provenance_cannot_change_a_pair_diversity_decision(materialized: Path) -> None:
    base = materialized / modular.CASES[0].task_id
    control = materialized / ".state/hard-rule-controls" / modular.ADVERSARIAL_CONTROLS[0]
    before = modular._pair_decision(
        base.name,
        control.name,
        modular._artifact_dimensions(base),
        modular._artifact_dimensions(control, control=True),
    )
    provenance_path = control / ".meta/provenance.json"
    provenance = json.loads(provenance_path.read_text())
    provenance["semantic_anchors"] = {
        dimension: "sha256:" + hashlib.sha256(("fresh:" + dimension).encode()).hexdigest()
        for dimension in modular.HARD_RULE_DIMENSIONS
    }
    provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    after = modular._pair_decision(
        base.name,
        control.name,
        modular._artifact_dimensions(base),
        modular._artifact_dimensions(control, control=True),
    )
    assert before == after


def test_prompt_hides_private_material_and_reference_is_whole_edit(materialized: Path) -> None:
    for case in (modular.CASES[0], modular.CASES[20], modular.CASES[40], modular.CASES[-1]):
        root = materialized / case.task_id
        task = moonlight_aider_task_sft.load_task(root)
        prompt = moonlight_aider_task_sft.build_prompt(task)
        answer = moonlight_aider_task_sft.build_assistant_response(
            task, moonlight_aider_task_sft.load_example_files_from_config(root)
        )
        assert ".meta/example" not in prompt
        assert "task_hidden_test" not in prompt
        assert "negative_false_substitute" not in prompt
        assert answer.startswith(f"{case.task_id}.h\n```")
        assert f"{case.task_id}.cpp\n```" in answer


def test_output_guards_refuse_existing_and_release_trees(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="legacy_root_immutable"):
        modular.build(modular.LEGACY_ROOT)
    with pytest.raises(RuntimeError, match="reverify_root_immutable"):
        modular.build(modular.REVERIFY_ROOT)
    with pytest.raises(RuntimeError, match="expansion_output_required"):
        modular.build(tmp_path)


def test_force_regeneration_invalidates_stale_verification_receipts(materialized: Path) -> None:
    state = materialized / ".state"
    for relative in ("creator-preflight.json", "independent-audit.json", "fresh-reaudit.json"):
        (state / relative).write_text("stale")
    modular.build(materialized, force=True, test_mode=True)
    assert not (state / "creator-preflight.json").exists()
    assert not (state / "independent-audit.json").exists()
    assert not (state / "fresh-reaudit.json").exists()


def test_docker_runner_requires_fresh_normal_sanitizer_and_negative_execution() -> None:
    assert '"-G","Unix Makefiles"' in modular.DOCKER_RUNNER
    assert '"-DTASK_SOURCE="+str(source)' in modular.DOCKER_RUNNER
    assert "-fsanitize=address,undefined" in modular.DOCKER_RUNNER
    assert "-fno-sanitize-recover=all" in modular.DOCKER_RUNNER
    assert 'env["UBSAN_OPTIONS"]="halt_on_error=1:print_stacktrace=1"' in modular.DOCKER_RUNNER
    assert "negative_fixture_not_rejected" in modular.DOCKER_RUNNER
    assert "sanitizer_test_count_mismatch" in modular.DOCKER_RUNNER
    assert "mounted_tree_hash" in modular.DOCKER_RUNNER
    source = (modular.REPO_ROOT / modular.GENERATOR_PATH).read_text()
    assert "manifest = verify_core(out, test_mode=test_mode)" in source
    assert "def refresh_creator_receipt" in source
    assert 'record.get("mounted_tree_hash") != current' in source


def test_audit_cycle_one_overflow_and_mechanism_remedies_are_owner_bound() -> None:
    source = (modular.REPO_ROOT / modular.GENERATOR_PATH).read_text()
    sequence = (modular.REPO_ROOT / modular.CASE_PATHS[1]).read_text()
    offset = (modular.REPO_ROOT / modular.CASE_PATHS[2]).read_text()
    assert "forward_distance" in source
    assert "sub_mod_nonnegative" in source
    assert "inverse_mod_coprime" in source
    assert "while(k<n/g" not in offset
    assert "auto inv=inverse_mod_coprime" in offset
    assert "pieces connected through period/zero coalesce" in sequence
    assert "out.front().begin==0&&out.back().end==p" in sequence
    assert "sample phases are Euclidean-normalized" in offset
    assert "blocked phases are Euclidean-normalized and uniqued" in offset
    forbidden = (
        "(b-a+p)%p",
        "(a-b+p)%p",
        "(xs[i].phase-xs[i-1].phase+p)%p",
        "(xs[(i+1)%xs.size()]-xs[i]+p)%p",
        "xs[0]+p",
        "(x-d+p)%p",
    )
    joined = "\n".join((sequence, offset, (modular.REPO_ROOT / modular.CASE_PATHS[0]).read_text()))
    assert not any(pattern in joined for pattern in forbidden)


def test_expansion_semantic_screen_includes_every_non_subject_root() -> None:
    source = (modular.REPO_ROOT / modular.GENERATOR_PATH).read_text()
    assert "expansion_roots = tuple(" in source
    assert "*_task_roots(EXPANSION_ROOT)" not in source  # exclusion is explicit before composition
    assert '"expansion_non_subject": len(expansion_roots)' in source
