from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_trees_ranges_ranks_expansion as family


def _sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    expansion = tmp_path / "aider-tasks-expansion-v1"
    legacy = tmp_path / "aider-tasks"
    reverify = tmp_path / "aider-tasks-reverify"
    holdouts = tmp_path / "holdouts"
    expansion.mkdir()
    legacy.mkdir()
    reverify.mkdir()
    holdouts.mkdir()
    for name in family.OFFICIAL_HOLDOUTS:
        root = holdouts / name
        root.mkdir()
        (root / "instructions.md").write_text(f"independent permanent holdout {name}\n")
    monkeypatch.setattr(family, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(family, "LEGACY_ROOT", legacy)
    monkeypatch.setattr(family, "REVERIFY_ROOT", reverify)
    monkeypatch.setattr(family, "HOLDOUT_ROOT", holdouts)
    return expansion / "algorithms-data-structures" / "trees-ranges-ranks"


def _independent_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.M | re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"', "STRING", text)
    text = re.sub(r"\b(?:0[xX][0-9A-Fa-f]+|\d+)(?:[UuLl]+)?\b", "NUMBER", text)
    text = re.sub(
        r"\b(?:treap|splay|scapegoat|fenwick|segment|wavelet|tree|range|rank|"
        r"ledger|index|catalog|cursor|page|rope|patricia)\b",
        "DOMAIN",
        text,
        flags=re.I,
    )
    return tuple(re.findall(r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\S", text))


def _independent_profile(root: Path) -> dict[str, str]:
    header = next(root.glob("*.h")).read_text()
    reference = (root / ".meta/example.cpp").read_text()
    docs = (root / ".docs/instructions.md").read_text()
    observable_docs = docs.split("## Implementation notes", 1)[0]
    observable_docs = re.sub(r"^- Owned mechanism:.*$", "", observable_docs, flags=re.M)
    hidden = (root / ".meta/task_hidden_test.cpp").read_text()
    negative = (root / ".meta/negative_false_substitute.cpp").read_text()
    scopes = {
        "public_api": header + observable_docs,
        "owned_state_algorithm": reference,
        "mutation_selection_rules": docs + reference,
        "invalid_boundary_behavior": docs + hidden,
        "reference_control_flow": reference,
        "deterministic_oracle": hidden,
        "topic_negative_fixture": negative,
    }
    return {
        name: hashlib.sha256(" ".join(_independent_tokens(text)).encode()).hexdigest()
        for name, text in scopes.items()
    }


def test_materializes_exact_count_roles_and_owner_boundary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    roots = family.build(out)
    assert len(roots) == 35
    assert {root.name for root in roots} == {case.task_id for case in family.CASES}
    assert len({case.mechanism for case in family.CASES}) == 35
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert config["files"]["test"] == [
            "task_visible_test.cpp",
            ".meta/task_hidden_test.cpp",
        ]
        assert (root / ".meta/negative_false_substitute.cpp").is_file()
        assert (root / ".meta/provenance.json").is_file()
        instructions = (root / ".docs/instructions.md").read_text()
        assert "mechanism_witness` is public" in instructions
        assert "Exact validation rules:" in instructions
        assert instructions.startswith("# Instructions\n")
        assert "## Examples" in instructions
        for banned in (
            "clean-room",
            "forbidden substitute",
            "Implementation constraint",
            "hidden test",
            "oracle",
            "grader",
            "benchmark",
        ):
            assert banned not in instructions, (root.name, banned)
        introduction = (root / ".docs/introduction.md").read_text()
        assert "clean-room" not in introduction
        assert len(introduction.split("\n\n")) >= 3
    with pytest.raises(RuntimeError, match="unsafe_path"):
        family.build(family.LEGACY_ROOT / "forbidden")
    with pytest.raises(RuntimeError, match="unsafe_path"):
        family.build(family.REVERIFY_ROOT / "forbidden")


def test_creator_preflight_screen_and_independent_all_pairs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    family.build(out)
    manifest = family.verify_core(out)
    assert manifest["task_count"] == 35
    assert manifest["strongest_local_status"] == "pending_execution"
    assert manifest["dataset_handoff"] == "not_requested"
    screen = json.loads((out / ".state/family-screen.json").read_text())
    assert screen["root_count"] == 35
    assert screen["pair_count"] == screen["expected_pair_count"] == 595
    assert screen["dimensions"] == list(family.HARD_DIMENSIONS)
    for pair in screen["pairs"]:
        assert pair["all_dimensions_distinct"] is True
        assert set(pair["dimension_decisions"]) == set(family.HARD_DIMENSIONS)
        assert all(item["distinct"] for item in pair["dimension_decisions"].values())

    profiles = {
        case.task_id: _independent_profile(out / case.task_id) for case in family.CASES
    }
    checked = 0
    ids = sorted(profiles)
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            assert set(profiles[left]) == set(family.HARD_DIMENSIONS)
            assert all(profiles[left][dimension] != profiles[right][dimension] for dimension in family.HARD_DIMENSIONS)
            checked += 1
    assert checked == 595
    assert profiles["persistent-kth-version-index"]["public_api"] != profiles[
        "wavelet-matrix-range-quantile"
    ]["public_api"]

    base = out / family.CASES[-1].task_id
    base_profile = json.loads((base / ".meta/provenance.json").read_text())["semantic_profile"]
    controls = screen["adversarial_clone_results"]
    assert set(controls) == set(family.CONTROL_NAMES)
    for name, record in controls.items():
        root = out / ".state/adversarial-clone-controls" / name
        assert record["failure"] == "duplicate_family"
        assert record["changed_files"]
        assert record["duplicate_dimensions"]
        assert json.loads((root / ".meta/provenance.json").read_text())["semantic_profile"] == base_profile
        assert family._tree_hash(root, include_state=True) != family._tree_hash(base, include_state=True)
        actual_changes = sorted(
            relative
            for relative, content in family._render_files(family.CASES[-1], control=name).items()
            if family._render_files(family.CASES[-1]).get(relative) != content
        )
        assert record["changed_files"] == actual_changes
    assert ".meta/example.cpp" in controls["domain-identifier-renamed"]["changed_files"]
    assert ".meta/example.cpp" in controls["constants-or-policy-only"]["changed_files"]
    assert ".meta/task_hidden_test.cpp" in controls["constants-or-policy-only"]["changed_files"]
    assert ".meta/example.cpp" in controls["opposite-end-selection"]["changed_files"]


def test_cross_tree_task_id_collision_fails_before_materialization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    collision = family.REVERIFY_ROOT / "reserved" / family.CASES[0].task_id / ".meta"
    collision.mkdir(parents=True)
    (collision / "config.json").write_text('{"files":{"solution":[],"test":[],"example":[]}}\n')
    with pytest.raises(RuntimeError, match="duplicate_task"):
        family.build(out)


def test_generated_prompts_exclude_private_assets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    family.build(out)
    manifest = family.verify_core(out)
    assert manifest["screen"]["prompt_boundary"] == "pass"
    for task in manifest["tasks"]:
        assert task["prompt_hash"].startswith("sha256:")
        assert task["reference_hash"].startswith("sha256:")
        assert task["primary_core_objective"] == "achieved"
        assert task["lineage"] == "new-root"
        root = out / task["task_id"]
        visible = (root / "task_visible_test.cpp").read_text()
        hidden = (root / ".meta/task_hidden_test.cpp").read_text()
        assert "independent_oracle" in visible and "expected_witness" in visible
        assert "independent_oracle" in hidden and "expected_witness" in hidden

    treap = out / "treap-split-rank-ledger"
    assert "9223372036854775807LL" in (treap / ".meta/task_hidden_test.cpp").read_text()
    assert "material_invalid.operations.back().second=1" in (
        treap / "task_visible_test.cpp"
    ).read_text()
    persistent = out / "persistent-kth-version-index"
    assert "then its multiplicity" in (persistent / ".docs/instructions.md").read_text()

    negative_profiles = {
        hashlib.sha256(" ".join(_independent_tokens(
            (out / case.task_id / ".meta/negative_false_substitute.cpp").read_text()
        )).encode()).hexdigest()
        for case in family.CASES
    }
    assert len(negative_profiles) == 35


def test_host_verify_fails_closed_on_tree_drift(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    family.build(out)
    family.verify_core(out)
    assert hasattr(family, "verify_host")
    with pytest.raises(RuntimeError, match="generator_output_drift"):
        family.verify_host(out / "missing-tree")
    target = out / family.CASES[0].task_id / ".docs" / "instructions.md"
    target.write_text(target.read_text() + "tampered after manifest binding\n")
    with pytest.raises(RuntimeError, match="generator_output_drift"):
        family.verify_host(out)
