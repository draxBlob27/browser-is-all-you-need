from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_regions_mazes_expansion as subject


def _independent_tokens(text: str) -> tuple[str, ...]:
    for case in subject.CASES:
        text = text.replace(case.task_id, "TASK_ID").replace(case.function, "TASK_FUNCTION")
    text = text.replace("ordered-passage-symbols", "TASK_ID").replace(
        "ordered_passage_symbols", "TASK_FUNCTION"
    )
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|(?<![A-Za-z_])-?\d+\b', " LIT ", text)
    text = re.sub(
        r"\b(front|back|earlier|later|minimum|maximum|first|last|up|down|left|right|stable|reverse|tie|order|endpoint)\b",
        " ENDPOINT ",
        text,
        flags=re.I,
    )
    text = re.sub(r">=|<=|>|<", " REL ", text)
    text = re.sub(
        r"region|district|maze|passage|grid|land|occupied|wall|barrier|cell|route|lexicographic|ordered|codes|symbols",
        "DOMAIN",
        text,
        flags=re.I,
    )
    return tuple(re.findall(r"[A-Za-z_][A-Za-z_0-9]*|==|!=|&&|\|\||[-+*/%{}()[\];,?:=.]", text))


def _independent_material(root: Path) -> dict[str, tuple[str, ...]]:
    instructions = (root / ".docs/instructions.md").read_text()
    reference = (root / ".meta/example.cpp").read_text()
    config = json.loads((root / ".meta/config.json").read_text())
    header = (root / config["files"]["solution"][0]).read_text()
    visible = (root / "task_visible_test.cpp").read_text()
    hidden = (root / ".meta/task_hidden_test.cpp").read_text()
    negative = (root / ".meta/negative_false_substitute.cpp").read_text()
    return {
        "public_api": _independent_tokens(header + instructions),
        "owned_state_algorithm": _independent_tokens(reference),
        "mutation_selection_rules": _independent_tokens(instructions + reference),
        "invalid_boundary_behavior": _independent_tokens(instructions + hidden),
        "reference_control_flow": _independent_tokens(reference),
        "deterministic_oracle": _independent_tokens(instructions + visible + hidden),
        "topic_negative_fixture": _independent_tokens(negative),
    }


def _actual_changed_files(left: Path, right: Path) -> list[str]:
    left_files = {
        path.relative_to(left).as_posix(): path.read_bytes()
        for path in left.rglob("*")
        if path.is_file()
    }
    right_files = {
        path.relative_to(right).as_posix(): path.read_bytes()
        for path in right.rglob("*")
        if path.is_file()
    }
    return sorted(
        relative
        for relative in set(left_files) | set(right_files)
        if left_files.get(relative) != right_files.get(relative)
    )


def test_inventory_has_exact_binding_count_and_unique_mechanisms() -> None:
    assert len(subject.CASES) == 30
    assert len({case.task_id for case in subject.CASES}) == 30
    assert len({case.mechanism for case in subject.CASES}) == 30
    assert sum(case.domain == "region" for case in subject.CASES) == 15
    assert sum(case.domain == "maze" for case in subject.CASES) == 15
    assert len(subject.HARD_DIMENSIONS) == 7
    assert len(subject.CONTRACTS) == 30


def test_owner_refuses_existing_and_root_output_paths() -> None:
    for path in (subject.EXPANSION_ROOT, subject.LEGACY_ROOT, subject.REVERIFY_ROOT):
        with pytest.raises(RuntimeError, match="unsafe_path"):
            subject._validate_output(path)


def test_rendered_roles_prompt_boundary_and_oracles(tmp_path: Path) -> None:
    out = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1/text-grid-logic/regions-mazes"
    old = subject.EXPANSION_ROOT
    try:
        subject.EXPANSION_ROOT = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1"
        subject.LEGACY_ROOT = tmp_path / "legacy"
        subject.REVERIFY_ROOT = tmp_path / "reverify"
        roots = subject.build(out)
    finally:
        subject.EXPANSION_ROOT = old
        subject.LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
        subject.REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
    assert len(roots) == 30
    for case, root in zip(subject.CASES, roots, strict=True):
        remedy_spec = out / ".state/remedy" / f"{case.task_id}.md"
        remedy_record = json.loads((out / ".state/remedy" / f"{case.task_id}.json").read_text())
        assert remedy_record["schema_version"] == "aider-task-remedy-v1"
        assert remedy_record["task_id"] == case.task_id
        assert remedy_record["disposition"] == "repair-in-place"
        assert remedy_record["finding_ids"] == subject._remedy_finding_ids(case)
        assert remedy_record["remedy_spec_hash"] == subject._file_hash(remedy_spec)
        assert remedy_record["tree_hash_before"].startswith("sha256:")
        assert remedy_record["status"] == "planned"
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        prompt_text = (root / ".docs/instructions.md").read_text()
        assert ".meta/" not in prompt_text
        assert "CMakeLists" not in prompt_text
        for hidden in (False, True):
            grid, parameter = subject._case_input(case, hidden)
            assert isinstance(subject._oracle(case, grid, parameter), list)


def test_all_pair_decisions_and_adversarial_controls_are_independently_inspected(
    tmp_path: Path,
) -> None:
    out = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1/text-grid-logic/regions-mazes"
    old_values = subject.EXPANSION_ROOT, subject.LEGACY_ROOT, subject.REVERIFY_ROOT
    subject.EXPANSION_ROOT = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1"
    subject.LEGACY_ROOT = tmp_path / "legacy"
    subject.REVERIFY_ROOT = tmp_path / "reverify"
    try:
        subject.build(out)
        production_screen = subject._semantic_screen(out)
    finally:
        subject.EXPANSION_ROOT, subject.LEGACY_ROOT, subject.REVERIFY_ROOT = old_values
    roots = [out / case.task_id for case in subject.CASES]
    independent_pairs = 0
    for index, left in enumerate(roots):
        left_material = _independent_material(left)
        for right in roots[index + 1 :]:
            right_material = _independent_material(right)
            assert all(
                left_material[dimension] != right_material[dimension]
                for dimension in subject.HARD_DIMENSIONS
            )
            independent_pairs += 1
    assert independent_pairs == 435
    assert production_screen["pair_count"] == independent_pairs
    control_manifest = json.loads(
        (out / ".state/adversarial-clone-controls/manifest.json").read_text()
    )
    assert set(control_manifest["controls"]) == {
        "domain-identifier-renamed",
        "constants-policy-only",
        "opposite-end-selection",
    }
    base = out / subject.CASES[18].task_id
    base_material = _independent_material(base)
    for name, record in control_manifest["controls"].items():
        control = out / ".state/adversarial-clone-controls" / name
        actual_changed = _actual_changed_files(base, control)
        assert record["changed_files"] == actual_changed
        assert record["tree_hash"].startswith("sha256:")
        control_material = _independent_material(control)
        assert all(
            base_material[dimension] == control_material[dimension]
            for dimension in subject.HARD_DIMENSIONS
        )
        assert not any(production_screen["controls"][name]["decisions"].values())
        config = json.loads((control / ".meta/config.json").read_text())
        header, source = config["files"]["solution"]
        assert sorted(path.name for path in control.glob("*.h")) == [header]
        assert sorted(path.name for path in control.glob("*.cpp")) == sorted(
            [source, "task_visible_test.cpp"]
        )
        assert (control / source).is_file()
        cmake = (control / "CMakeLists.txt").read_text()
        assert f"${{CMAKE_CURRENT_SOURCE_DIR}}/{source}" in cmake
        assert f"${{CMAKE_CURRENT_SOURCE_DIR}}/{control.name}.cpp" not in cmake

    opposite_prompt = (
        out / ".state/adversarial-clone-controls/opposite-end-selection/.docs/instructions.md"
    ).read_text()
    assert "down,right,left,up encoded 0,1,2,3" in opposite_prompt
    assert "up,left,right,down encoded 0,1,2,3" not in opposite_prompt


def test_clone_controls_change_emitted_files_but_not_production_dimensions(
    tmp_path: Path,
) -> None:
    out = tmp_path / "family"
    base = out / subject.CASES[18].task_id
    subject._write_root(base, subject.CASES[18], False)
    base_hash = subject._tree_hash(base, include_state=True)
    for control in (
        "domain-identifier-renamed",
        "constants-policy-only",
        "opposite-end-selection",
    ):
        root = out / control
        subject._write_root(root, subject.CASES[18], False, control=control)
        assert subject._tree_hash(root, include_state=True) != base_hash
        assert all(
            _independent_material(base)[dimension] == _independent_material(root)[dimension]
            for dimension in subject.HARD_DIMENSIONS
        )


def test_force_regeneration_removes_obsolete_control_files(tmp_path: Path) -> None:
    root = tmp_path / "domain-identifier-renamed"
    subject._write_root(root, subject.CASES[18], False, control="domain-identifier-renamed")
    stale_header = root / "lexicographic-route-codes.h"
    stale_source = root / "lexicographic-route-codes.cpp"
    stale_header.write_text("stale header\n")
    stale_source.write_text("stale source\n")
    with pytest.raises(FileExistsError, match="stale generated files"):
        subject._write_root(root, subject.CASES[18], False, control="domain-identifier-renamed")
    subject._write_root(root, subject.CASES[18], True, control="domain-identifier-renamed")
    assert not stale_header.exists()
    assert not stale_source.exists()
    config = json.loads((root / ".meta/config.json").read_text())
    assert sorted(path.name for path in root.glob("*.h")) == [config["files"]["solution"][0]]
    assert sorted(path.name for path in root.glob("*.cpp")) == sorted(
        [config["files"]["solution"][1], "task_visible_test.cpp"]
    )


def test_audit_specific_mechanisms_and_invalid_branches_are_emitted() -> None:
    dsu = subject._render_files(subject.CASES[12])
    dsu_reference = dsu[".meta/example.cpp"]
    assert "parent" in dsu_reference and "rank" in dsu_reference and "find" in dsu_reference
    assert "std::vector<std::vector<int>> seen" not in dsu_reference

    portal = subject._render_files(subject.CASES[29])
    assert "portal_count" in portal[".meta/example.cpp"]
    assert "count!=0&&count!=2" in portal[".meta/example.cpp"]
    assert "seen.insert({next,mask})" in portal[".meta/example.cpp"]
    assert "next_mask=mask|(1<<(value-'0'))" in portal[".meta/example.cpp"]
    for role in ("task_visible_test.cpp", ".meta/task_hidden_test.cpp"):
        assert "single_portal" in portal[role]
        assert "triple_portal" in portal[role]
        assert "no_portal" in portal[role]

    mandatory = subject._render_files(subject.CASES[20])
    mandatory_reference = mandatory[".meta/example.cpp"]
    for evidence in (
        "struct Big",
        "digit",
        "base=1000000000ULL",
        "multiply",
        "counted_bfs",
        "from_ways",
        "to_ways",
        "total_ways",
    ):
        assert evidence in mandatory_reference
    assert "multiply(from_ways[cell],to_ways[cell]).digit==total_ways.digit" in mandatory_reference
    assert "std::vector<unsigned long long> ways" not in mandatory_reference
    assert "int only=-1,count=0" not in mandatory_reference
    overflow_grid = subject._overflow_diamond_grid()
    assert len(overflow_grid) == 29
    assert all(len(row) == 32 for row in overflow_grid)
    assert subject._exact_shortest_path_count(overflow_grid) == 1 << 100
    overflow_expected = subject._oracle(subject.CASES[20], overflow_grid, 0)
    assert overflow_expected[0] == 1
    for role in ("task_visible_test.cpp", ".meta/task_hidden_test.cpp"):
        assert "wrapped_path_counts" in mandatory[role]
        assert f"std::vector<int>{subject._cpp_ints(overflow_expected)}" in mandatory[role]
    wrapped_negative = mandatory[".meta/negative_false_substitute.cpp"]
    assert "std::vector<unsigned long long> ways" in wrapped_negative
    assert "out.push_back(0)" in wrapped_negative

    patrol = subject._render_files(subject.CASES[26])
    assert "rotate 180 degrees in place and count one transition" in patrol[".docs/instructions.md"]
    for role in ("task_visible_test.cpp", ".meta/task_hidden_test.cpp"):
        assert "trapped" in patrol[role]
        assert "std::vector<int>{0,2}" in patrol[role]
    assert subject._oracle(subject.CASES[26], ("#####", "#S###", "#####", "###G#", "#####"), 0) == [
        0,
        2,
    ]

    for case in subject.CASES:
        rendered = subject._render_files(case)
        prompt = rendered[".docs/instructions.md"]
        tests = rendered["task_visible_test.cpp"] + rendered[".meta/task_hidden_test.cpp"]
        assert subject.CONTRACTS[subject.CASES.index(case)] in prompt
        for branch in ("empty", "blank", "ragged", "illegal", "oversize", "boundary"):
            assert branch in tests
        if case.domain == "maze":
            assert "oversize.grid.front().front()='S'" in tests
            assert "oversize.grid.back().front()='G'" in tests

    expected_properties = {
        7: [16, 8, 1],
        8: [12, 3],
        21: [1, 1, 1],
        24: [2],
        26: [1, 8],
        29: [5],
    }
    for index, expected in expected_properties.items():
        grid, parameter = subject.PROPERTY_INPUTS[index]
        assert subject._oracle(subject.CASES[index], grid, parameter) == expected


def test_prewrite_hardlink_and_symlink_attacks_preserve_source_bytes(tmp_path: Path) -> None:
    old_values = subject.EXPANSION_ROOT, subject.LEGACY_ROOT, subject.REVERIFY_ROOT
    subject.EXPANSION_ROOT = tmp_path / "expansion"
    subject.LEGACY_ROOT = tmp_path / "legacy"
    subject.REVERIFY_ROOT = tmp_path / "reverify"
    out = subject.EXPANSION_ROOT / "text-grid-logic/regions-mazes"
    source = subject.LEGACY_ROOT / "source.cpp"
    source.parent.mkdir(parents=True)
    source.write_text("legacy bytes\n")
    candidate = out / subject.CASES[0].task_id / f"{subject.CASES[0].task_id}.cpp"
    candidate.parent.mkdir(parents=True)
    os.link(source, candidate)
    try:
        with pytest.raises(RuntimeError, match="pre-write hardlink"):
            subject.build(out, force=True)
        assert source.read_text() == "legacy bytes\n"
        candidate.unlink()
        candidate.symlink_to(source)
        with pytest.raises(RuntimeError, match="pre-write symlink"):
            subject.build(out, force=True)
        assert source.read_text() == "legacy bytes\n"
        assert not (out / ".state/source-inventory.json").exists()
    finally:
        subject.EXPANSION_ROOT, subject.LEGACY_ROOT, subject.REVERIFY_ROOT = old_values


def test_cross_tree_screen_uses_immutable_stable_snapshot(tmp_path: Path) -> None:
    old_values = subject.EXPANSION_ROOT, subject.LEGACY_ROOT, subject.REVERIFY_ROOT
    subject.EXPANSION_ROOT = tmp_path / "expansion"
    subject.LEGACY_ROOT = tmp_path / "legacy"
    subject.REVERIFY_ROOT = tmp_path / "reverify"
    out = subject.EXPANSION_ROOT / "text-grid-logic/regions-mazes"
    try:
        subject.build(out)
        inventory_before = (out / ".state/source-inventory.json").read_bytes()
        sibling = subject.EXPANSION_ROOT / "concurrent/sibling-root"
        subject._write_root(sibling, subject.CASES[0], False)
        screen = subject._cross_tree_semantic_screen(out)
        assert screen["per_tree"]["expansion_before"]["root_count"] == 0
        assert (out / ".state/source-inventory.json").read_bytes() == inventory_before

        subject.EXPANSION_ROOT = tmp_path / "expansion-next"
        other_out = subject.EXPANSION_ROOT / "text-grid-logic/regions-mazes"
        sibling = subject.EXPANSION_ROOT / "concurrent/sibling-root"
        subject._write_root(sibling, subject.CASES[0], False)
        subject.build(other_out)
        with pytest.raises(RuntimeError, match="duplicate_family"):
            subject._cross_tree_semantic_screen(other_out)
    finally:
        subject.EXPANSION_ROOT, subject.LEGACY_ROOT, subject.REVERIFY_ROOT = old_values


def test_verify_host_requires_manifest_bound_to_current_owner_and_tree(tmp_path: Path) -> None:
    out = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1/text-grid-logic/regions-mazes"
    old_values = subject.EXPANSION_ROOT, subject.LEGACY_ROOT, subject.REVERIFY_ROOT
    subject.EXPANSION_ROOT = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1"
    subject.LEGACY_ROOT = tmp_path / "legacy"
    subject.REVERIFY_ROOT = tmp_path / "reverify"
    try:
        subject.build(out)
        with pytest.raises(RuntimeError, match="generator_output_drift"):
            subject.verify_host(out)
    finally:
        subject.EXPANSION_ROOT, subject.LEGACY_ROOT, subject.REVERIFY_ROOT = old_values


def test_main_wires_verify_host_after_verify_core(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    monkeypatch.setattr(subject, "build", lambda out, force: calls.append("build") or ())
    monkeypatch.setattr(subject, "verify_core", lambda out: calls.append("verify_core"))
    monkeypatch.setattr(subject, "verify_host", lambda out: calls.append("verify_host"))
    monkeypatch.setattr(subject, "verify_docker", lambda out: calls.append("verify_docker"))
    subject.main(["--out", str(tmp_path), "--verify-host"])
    assert calls == ["build", "verify_core", "verify_host"]


def test_docs_follow_benchmark_register() -> None:
    banned = re.compile(
        r"clean-room|\bthis task\b|\bSFT\b|benchmark|campaign|remediation|oracle"
        r"|negative fixture|reference implementation|generator|adversarial"
        r"|hard rule|forbidden substitute|do not substitute|grader|hidden test"
        r"|local_family_verified|prompt|\bmodel\b",
        re.IGNORECASE,
    )
    for case in subject.CASES:
        rendered = subject._render_files(case)
        instructions = rendered[".docs/instructions.md"]
        introduction = rendered[".docs/introduction.md"]
        assert instructions.startswith("# Instructions\n")
        assert "## Example\n" in instructions
        assert "Required mechanism" not in instructions
        assert subject.CONTRACTS[subject.CASES.index(case)] in instructions
        assert f"`{case.function}`" in instructions
        assert introduction.startswith(f"# {case.title}\n\n")
        assert len(introduction.split()) >= 40
        assert not banned.search(instructions)
        assert not banned.search(introduction)
