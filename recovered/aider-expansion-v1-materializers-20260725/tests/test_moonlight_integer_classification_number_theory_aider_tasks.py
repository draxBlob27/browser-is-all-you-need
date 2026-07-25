from __future__ import annotations

import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_integer_classification_number_theory_aider_tasks as tasks


def _patch_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    original_repo = tasks.REPO_ROOT
    repo = tmp_path / "repo"
    expansion = repo / ".w8-biayn/data/aider-tasks-expansion-v1"
    out = expansion / "numerical-anchors/integer-classification-number-theory"
    curriculum = repo / tasks.CURRICULUM.relative_to(original_repo)
    curriculum.parent.mkdir(parents=True)
    curriculum.write_text(tasks.CURRICULUM.read_text())
    remedy_spec = repo / tasks.REMEDY_SPEC.relative_to(original_repo)
    remedy_spec.parent.mkdir(parents=True)
    remedy_spec.write_text(tasks.REMEDY_SPEC.read_text())
    holdouts = repo / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
    for slug in tasks.OFFICIAL_HOLDOUTS:
        root = holdouts / slug
        docs = root / ".docs"
        meta = root / ".meta"
        docs.mkdir(parents=True)
        meta.mkdir(parents=True)
        (docs / "instructions.md").write_text(f"Independent permanent benchmark holdout {slug}.\n")
        (root / f"{slug}.h").write_text(f"int {slug.replace('-', '_')}(int);\n")
        (root / f"{slug}.cpp").write_text(f'#include "{slug}.h"\n')
        (meta / "example.h").write_text(f"int {slug.replace('-', '_')}(int);\n")
        (meta / "example.cpp").write_text(f'#include "example.h"\n// reference for {slug}\n')
        (meta / "test.cpp").write_text(f"// benchmark tests for {slug}\n")
        (root / "CMakeLists.txt").write_text(f"project({slug.replace('-', '_')})\n")
        (meta / "config.json").write_text(json.dumps({"files": {"solution": [f"{slug}.h", f"{slug}.cpp"], "example": [".meta/example.h", ".meta/example.cpp"], "test": [".meta/test.cpp"]}}))
    monkeypatch.setattr(tasks, "REPO_ROOT", repo)
    monkeypatch.setattr(tasks, "CURRICULUM", curriculum)
    monkeypatch.setattr(tasks, "REMEDY_SPEC", remedy_spec)
    monkeypatch.setattr(tasks, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(tasks, "DEFAULT_OUT", out)
    monkeypatch.setattr(tasks, "EXISTING_ROOTS", (repo / ".w8-biayn/data/aider-tasks", repo / ".w8-biayn/data/aider-tasks-reverify"))
    monkeypatch.setattr(tasks, "HOLDOUT_ROOT", holdouts)
    owner = repo / tasks.OWNER
    owner.parent.mkdir(parents=True)
    owner.write_text(Path(tasks.__file__).read_text())
    focused_test = repo / "tests/test_moonlight_integer_classification_number_theory_aider_tasks.py"
    focused_test.parent.mkdir(parents=True)
    focused_test.write_text(Path(__file__).read_text())
    return out


def test_count_plan_cell_has_exactly_40_unique_new_roots() -> None:
    assert len(tasks.CASES) == 40
    assert len({case.task_id for case in tasks.CASES}) == 40
    assert tasks.CASES[0].task_id == "prime-interval-profile"
    assert tasks.CASES[-1].task_id == "primitive-pythagorean-triple"
    assert not ({case.task_id for case in tasks.CASES} & tasks.OFFICIAL_HOLDOUTS)


def test_materializes_only_role_safe_expansion_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    manifest = tasks.materialize(out)
    assert manifest["task_count"] == 40
    assert len(list(out.glob("*/.meta/config.json"))) == 40
    for case in tasks.CASES:
        config = json.loads((out / case.task_id / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        prompt_files = [".docs/introduction.md", ".docs/instructions.md", *config["files"]["solution"]]
        assert all(".meta" not in path and path != "CMakeLists.txt" for path in prompt_files)
        prompt = "\n".join((out / case.task_id / path).read_text() for path in prompt_files)
        assert "private_test" not in prompt
        assert "example.cpp" not in prompt


def test_refuses_old_trees_foreign_output_and_id_collisions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    with pytest.raises(tasks.CreatorError, match="invalid_output_root"):
        tasks.materialize(tasks.EXISTING_ROOTS[0])
    collision = tasks.EXISTING_ROOTS[1] / "numeric" / tasks.CASES[3].task_id / ".meta"
    collision.mkdir(parents=True)
    (collision / "config.json").write_text("{}\n")
    with pytest.raises(tasks.CreatorError, match="existing_task_id"):
        tasks.materialize(out)


def test_all_780_pairs_differ_in_every_dimension(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    screen = tasks.diversity_screen(out)
    assert screen["root_count"] == 40
    assert screen["pair_count"] == 780
    assert tuple(screen["dimensions"]) == tasks.DIMENSIONS
    seen = set()
    for row in screen["pairs"]:
        seen.add((row["left"], row["right"]))
        assert row["pass"] is True
        assert set(row["dimensions"]) == set(tasks.DIMENSIONS)
        assert all(item["pass"] is True and item["jaccard"] < item["threshold"] for item in row["dimensions"].values())
        assert row["aggregate_jaccard"] < row["aggregate_threshold"]
    assert len(seen) == 780


@pytest.mark.parametrize("name", ["domain-identifier-renamed", "constants-policy-only", "opposite-end-selection"])
def test_real_changed_clone_controls_are_rejected_in_all_dimensions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    screen = tasks.diversity_screen(out)
    control = screen["controls"][name]
    assert control["changed_files"]
    for relative in control["changed_files"]:
        assert (out / ".state/adversarial-clone-controls" / name / relative).read_bytes() != (out / tasks.CASES[0].task_id / relative).read_bytes()
    assert control["production_rejected"] is True
    assert set(control["dimensions"]) == set(tasks.DIMENSIONS)
    assert any(item["pass"] is False for item in control["dimensions"].values()) or control["aggregate_jaccard"] >= control["aggregate_threshold"]


def test_semantic_evidence_is_present_in_emitted_artifacts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    for case in tasks.CASES:
        semantic = tasks._case_semantic(out / case.task_id, case)
        assert set(semantic) == set(tasks.DIMENSIONS)
        assert all(semantic[dimension] for dimension in tasks.DIMENSIONS)
        private = (out / case.task_id / ".meta/private_test.cpp").read_text()
        assert all(sample.args in private for sample in tasks._private_samples(case))
        assert case.body in (out / case.task_id / ".meta/example.cpp").read_text()


def test_manifest_hash_detects_generated_drift(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    (out / tasks.CASES[0].task_id / ".docs/instructions.md").write_text("drift\n")
    with pytest.raises(tasks.CreatorError, match="generator_output_drift"):
        tasks.verify_core(out)


def test_named_negative_fixture_is_coherent_mutated_algorithm(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    for case in tasks.CASES:
        root = out / case.task_id
        negative = (root / ".meta/negative.cpp").read_text()
        reference = (root / ".meta/example.cpp").read_text()
        assert tasks._negative_body(case) in negative
        assert case.bad in (root / ".docs/instructions.md").read_text()
        assert negative != reference
        assert "visible-case-only-hardcode" not in negative
        assert "negative_smoke" in (root / "CMakeLists.txt").read_text()
        assert "negative_rejected" in (root / "CMakeLists.txt").read_text()


def test_prompts_define_every_output_and_private_coverage_ledger(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    for case in tasks.CASES:
        root = out / case.task_id
        prompt = (root / ".docs/instructions.md").read_text()
        assert all(value in prompt for value in tasks.OUTPUT_FIELDS[case.task_id])
        assert prompt.startswith("# Instructions\n")
        assert "Public boundary example:" in prompt
        for banned in (
            "clean-room",
            "Required mechanism",
            "independent oracle",
            "Do not substitute",
            "hidden test",
            "grader",
            "benchmark",
        ):
            assert banned not in prompt, (case.task_id, banned)
        introduction = (root / ".docs/introduction.md").read_text()
        assert "clean-room" not in introduction
        assert len(introduction.split("\n\n")) >= 3
        coverage = json.loads((root / ".meta/coverage.json").read_text())
        assert coverage["status"] == "covered"
        requirement_names = {name for row in coverage["assertions"] for name in row["requirements"]}
        assert {"published_upper_bound", "above_published_upper_bound", "named_negative_counterexample"} <= requirement_names
        assert len(tasks._private_samples(case)) >= 5
        assert coverage["requirements"]["named_negative"] == case.bad
        assert tasks.MEMBER_PREDICATES.get(case.task_id, case.summary) in prompt
        assert tasks.UPPER_BOUND_SAMPLES[case.task_id][0].args in (root / ".meta/private_test.cpp").read_text()
        assert tasks.UPPER_BOUND_SAMPLES[case.task_id][1].args in (root / ".meta/private_test.cpp").read_text()
        assert tasks.NEGATIVE_COUNTEREXAMPLES[case.task_id].args in (root / ".meta/negative_test.cpp").read_text()


def test_diversity_is_derived_from_emitted_files_not_provenance(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    before = tasks.diversity_screen(out)
    provenance = out / tasks.CASES[0].task_id / ".meta/provenance.json"
    record = json.loads(provenance.read_text())
    record["diversity_signatures"] = {dimension: ["forged-identical"] for dimension in tasks.DIMENSIONS}
    provenance.write_text(json.dumps(record))
    after = tasks.diversity_screen(out)
    assert before["pairs"] == after["pairs"]
    assert after["normalizer"] == "emitted-artifact-token-bigrams-v2"


def test_cross_corpus_receipt_binds_all_five_surfaces(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    receipt = tasks.verify_core(out)
    screen = receipt["contamination"]
    assert screen["holdout_count"] == 26
    assert screen["source_digest"].startswith("sha256:")
    assert screen["surface_inventory_digest"].startswith("sha256:")
    assert screen["surfaces"] == ["prompt", "api", "reference", "tests", "lineage"]
    assert screen["inventory_stable"] is True
    assert len({(row["source_digest"], row["surface_inventory_digest"]) for row in screen["inventory_confirmations"].values()}) == 1
    inventory = json.loads((out / ".state/source-inventory.json").read_text())
    assert inventory["schema_version"] == "integer-source-inventory-v3"
    assert inventory["stable"] is True
    assert len(inventory["sources"]) == len(inventory["surface_records"]) == inventory["source_count"]
    assert receipt["source_inventory_hash"].startswith("sha256:")
    assert receipt["cross_corpus_screen_hash"].startswith("sha256:")


def test_cross_corpus_screen_fails_closed_when_inventory_changes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    collect = tasks._collect_contamination_inventory
    call_count = 0

    def changing_inventory(path: Path):
        nonlocal call_count
        inventory, sources, metadata = collect(path)
        call_count += 1
        if call_count >= 3:
            metadata = {**metadata, "surface_inventory_digest": "sha256:" + "0" * 64}
        return inventory, sources, metadata

    monkeypatch.setattr(tasks, "_collect_contamination_inventory", changing_inventory)
    with pytest.raises(tasks.CreatorError, match="inventory_changed_during_screen"):
        tasks._contamination_screen(out)


def test_k_almost_reference_returns_exact_total_after_exceeding_k() -> None:
    case = next(case for case in tasks.CASES if case.task_id == "k-almost-prime-membership")
    assert "if(total>k)" not in case.body
    assert tasks.NEGATIVE_COUNTEREXAMPLES[case.task_id] == tasks.S("72,1", True, False, 5, 3)


def test_remedy_records_bind_current_generator_and_distinct_lineage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    for case in tasks.CASES:
        remedy = json.loads((out / ".state/remedy" / f"{case.task_id}.json").read_text())
        assert remedy["generator_revision"] == tasks._file_hash(tasks.REPO_ROOT / tasks.OWNER)
        assert remedy["tree_hash_after"] == tasks._tree_hash(out / case.task_id)
        assert remedy["invalidated_audit_subject"] == "sha256:88c86864d4034f55cb08d08cf1088fb8b3465d3cf6432d9f80d1629ce517211e"
        assert "ICNT-AUD-010" in remedy["finding_ids"]
