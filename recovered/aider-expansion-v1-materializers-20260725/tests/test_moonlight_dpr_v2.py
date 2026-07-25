from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_dpr_v2 as dpr
from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory):
    temporary = tmp_path_factory.mktemp("dpr-v2")
    old = (dpr.EXPANSION_ROOT, dpr.LEGACY_ROOT, dpr.REVERIFY_ROOT)
    dpr.EXPANSION_ROOT = temporary / "expansion"
    dpr.LEGACY_ROOT = temporary / "legacy"
    dpr.REVERIFY_ROOT = temporary / "reverify"
    dpr.LEGACY_ROOT.mkdir()
    dpr.REVERIFY_ROOT.mkdir()
    out = dpr.EXPANSION_ROOT / "state-concurrency/deterministic-parallel-reductions"
    roots = dpr.build(out, force=True)
    try:
        yield out, roots
    finally:
        dpr.EXPANSION_ROOT, dpr.LEGACY_ROOT, dpr.REVERIFY_ROOT = old


def _digest(tokens: tuple[str, ...]) -> str:
    return hashlib.sha256("\0".join(tokens).encode()).hexdigest()


def test_exact_inventory_and_case_contracts():
    assert len(dpr.CASES) == 60
    assert len({case.task_id for case in dpr.CASES}) == 60
    assert {group: sum(case.group == group for case in dpr.CASES) for group in dpr.GROUPS} == {
        group: 12 for group in dpr.GROUPS
    }
    assert len({case.mechanism for case in dpr.CASES}) == 60
    assert len({case.api for case in dpr.CASES}) == 60
    assert len({case.negative_reason for case in dpr.CASES}) == 60
    for case in dpr.CASES:
        assert case.definition.count(case.negative_old) == 1
        assert case.negative_old != case.negative_new
        assert case.visible.strip() and case.hidden.strip()
        assert "pop_back()" not in case.negative_reason


def test_materialized_roles_prompts_references_and_negatives(generated):
    out, roots = generated
    assert len(roots) == 60
    for case, root in zip(dpr.CASES, roots, strict=True):
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        prompt = build_prompt(load_task(root))
        assert f"{case.task_id}.h" in prompt and f"{case.task_id}.cpp" in prompt
        assert not any(
            marker in prompt
            for marker in (".meta/", "CMakeLists", "task_visible_test", "negative_false_substitute", "provenance.json")
        )
        answer = build_assistant_response(load_task(root), load_example_files_from_config(root))
        assert answer.startswith(f"{case.task_id}.h\n```")
        assert f"{case.task_id}.cpp\n```" in answer
        reference = (root / ".meta/example.cpp").read_text()
        negative = (root / ".meta/negative_false_substitute.cpp").read_text()
        assert reference != negative
        assert case.negative_old in reference and case.negative_new in negative
        assert case.negative_old not in negative
    assert len(list((out / ".state/contracts-v2").glob("dpr-*.md"))) == 60


def test_independent_all_pairs_and_controls(generated):
    out, roots = generated
    screen = dpr._family_screen(out)
    assert screen["pair_count"] == 1770
    assert tuple(screen["dimensions"]) == dpr.HARD_DIMENSIONS
    expected = {
        (left.name, right.name)
        for index, left in enumerate(sorted(roots, key=lambda p: p.name))
        for right in sorted(roots, key=lambda p: p.name)[index + 1 :]
    }
    assert {(row["left"], row["right"]) for row in screen["pairs"]} == expected
    assert all(
        set(row["decisions"]) == set(dpr.HARD_DIMENSIONS) and all(row["decisions"].values())
        for row in screen["pairs"]
    )
    # Independent artifact signatures do not call pair_decisions or trust the
    # receipt's top-level pass. Task IDs and provenance are outside every scope.
    for dimension in dpr.HARD_DIMENSIONS:
        signatures = [_digest(dpr._dimension_material(root)[dimension]) for root in roots]
        assert len(set(signatures)) == 60
    controls_manifest = json.loads(
        (out / ".state/adversarial-clone-controls/manifest.json").read_text()
    )["controls"]
    for name in dpr.CONTROL_NAMES:
        base = out / controls_manifest[name]["base_task_id"]
        control = out / ".state/adversarial-clone-controls" / name
        changed = [
            path.relative_to(control).as_posix()
            for path in control.rglob("*")
            if path.is_file()
            and (base / path.relative_to(control)).is_file()
            and path.read_bytes() != (base / path.relative_to(control)).read_bytes()
        ]
        assert changed
        assert not any(dpr.pair_decisions(base, control).values())
    sparse_base = out / controls_manifest["dimensional-wrapper-clone"]["base_task_id"]
    sparse_control = out / ".state/adversarial-clone-controls/dimensional-wrapper-clone"
    assert dpr._semantic_mechanism_fingerprint(sparse_base) == dpr._semantic_mechanism_fingerprint(sparse_control)


def test_path_collision_and_rejected_root_guards(tmp_path: Path):
    with pytest.raises(RuntimeError, match="unsafe_path"):
        dpr._validate_output(dpr.LEGACY_ROOT)
    with pytest.raises(RuntimeError, match="unsafe_path"):
        dpr._validate_output(dpr.REVERIFY_ROOT)
    with pytest.raises(RuntimeError, match="unsafe_path"):
        dpr._validate_output(dpr.EXPANSION_ROOT)

    expansion, legacy, reverify = tmp_path / "expansion", tmp_path / "legacy", tmp_path / "reverify"
    collision = legacy / "topic" / dpr.CASES[0].task_id / ".meta/config.json"
    collision.parent.mkdir(parents=True)
    collision.write_text('{"files":{"solution":[],"test":[],"example":[]}}\n')
    reverify.mkdir()
    old = dpr.EXPANSION_ROOT, dpr.LEGACY_ROOT, dpr.REVERIFY_ROOT
    dpr.EXPANSION_ROOT, dpr.LEGACY_ROOT, dpr.REVERIFY_ROOT = expansion, legacy, reverify
    try:
        with pytest.raises(RuntimeError, match="duplicate_task"):
            dpr.build(expansion / "state-concurrency/family", force=True)
    finally:
        dpr.EXPANSION_ROOT, dpr.LEGACY_ROOT, dpr.REVERIFY_ROOT = old


def test_host_verify_receipt_binds_tree_and_rejects_negatives(
    tmp_path: Path, generated, monkeypatch: pytest.MonkeyPatch
):
    out, roots = generated
    holdouts = tmp_path / "holdouts"
    for name in dpr.OFFICIAL_HOLDOUTS:
        root = holdouts / name
        root.mkdir(parents=True)
        (root / f"{name}.h").write_text("// holdout stub\n")
    monkeypatch.setattr(dpr, "HOLDOUT_ROOT", holdouts)
    dpr.verify_core(out)
    manifest = json.loads((out / ".state/materialization-manifest-v2.json").read_text())
    assert manifest["strongest_local_status"] == "pending_execution"
    cases = dpr.CASES[:2]
    with pytest.raises(RuntimeError, match="remedy_disposition_conflict"):
        dpr.verify_host(out, cases=cases, controls=(), update_manifest=True)
    receipt_path = tmp_path / "host-verify.json"
    receipt = dpr.verify_host(
        out, cases=cases, controls=(), receipt_path=receipt_path, update_manifest=False
    )
    assert receipt["schema_version"] == "dpr-v2-host-verify-v1"
    assert receipt["status"] == "pass"
    assert receipt["evidence_class"] == "host_verify"
    assert receipt["locked_oracle"] is False
    assert receipt["family_tree_hash"] == dpr._tree_hash(out)
    assert receipt["owner_hash"] == dpr._file_hash(dpr.GENERATOR)
    assert receipt["task_mode_record_count"] == 2 * len(cases)
    assert receipt["control_mode_record_count"] == 0
    assert receipt["negative_rejection_count_per_mode"] == len(cases)
    task_records = [record for record in receipt["execution_records"] if record["kind"] == "tasks"]
    assert {record["mode"] for record in task_records} == {"normal", "sanitizer"}
    assert all(record["discovered_test_count"] == 2 for record in task_records)
    assert all(record["discovered_tests"] == ["visible", "hidden"] for record in task_records)
    assert all(
        record["negative_visible_exit"] != 0 and record["negative_hidden_exit"] != 0
        for record in task_records
    )
    on_disk = json.loads(receipt_path.read_text())
    assert on_disk["family_tree_hash"] == receipt["family_tree_hash"]
    # A subset run must never upgrade the manifest status.
    manifest = json.loads((out / ".state/materialization-manifest-v2.json").read_text())
    assert manifest["strongest_local_status"] == "pending_execution"
