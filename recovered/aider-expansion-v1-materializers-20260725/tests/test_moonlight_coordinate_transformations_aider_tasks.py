from __future__ import annotations

import hashlib
import json
import re
import shutil
from itertools import combinations
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_coordinate_transformations_aider_tasks as tasks
from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task


def _patch_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    expansion = repo / ".w8-biayn/data/aider-tasks-expansion-v1"
    out = expansion / "text-grid/coordinate-transformations"
    curriculum = repo / tasks.CURRICULUM.relative_to(tasks.REPO_ROOT)
    spec = repo / tasks.FAMILY_SPEC.relative_to(tasks.REPO_ROOT)
    focused = repo / tasks.FOCUSED_TEST.relative_to(tasks.REPO_ROOT)
    owner = repo / tasks.OWNER
    for source, destination in (
        (tasks.CURRICULUM, curriculum),
        (tasks.FAMILY_SPEC, spec),
        (tasks.FOCUSED_TEST, focused),
        (Path(tasks.__file__), owner),
    ):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    holdouts = repo / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
    for slug in tasks.OFFICIAL_HOLDOUTS:
        docs = holdouts / slug / ".docs"
        docs.mkdir(parents=True)
        (docs / "instructions.md").write_text(f"Permanent unrelated benchmark contract for {slug}.\n")
    monkeypatch.setattr(tasks, "REPO_ROOT", repo)
    monkeypatch.setattr(tasks, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(tasks, "DEFAULT_OUT", out)
    monkeypatch.setattr(tasks, "LEGACY_ROOTS", (repo / ".w8-biayn/data/aider-tasks", repo / ".w8-biayn/data/aider-tasks-reverify"))
    monkeypatch.setattr(tasks, "HOLDOUT_ROOT", holdouts)
    monkeypatch.setattr(tasks, "CURRICULUM", curriculum)
    monkeypatch.setattr(tasks, "FAMILY_SPEC", spec)
    monkeypatch.setattr(tasks, "FOCUSED_TEST", focused)
    return out


def _independent_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " STR ", text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", " STR ", text)
    text = re.sub(r"\b\d[\d']*\b", " NUM ", text)
    return tuple(re.findall(r"[A-Za-z_][A-Za-z_0-9]*|::|->|==|!=|<=|>=|&&|\|\||\S", text.lower()))


def _independent_role_digest(root: Path, dimension: str) -> str:
    task_id = root.name
    paths = {
        "public_api": [f"{task_id}.h"],
        "owned_state_or_algorithm": [".docs/instructions.md", ".meta/example.cpp"],
        "mutation_or_selection_rules": [".meta/example.cpp", ".meta/private_test.cpp"],
        "invalid_and_boundary_behavior": [".docs/instructions.md", ".meta/private_test.cpp"],
        "reference_control_flow": [".meta/example.cpp"],
        "deterministic_oracle": ["visible_test.cpp", ".meta/private_test.cpp"],
        "topic_specific_negative_fixture": [".meta/example.cpp", ".meta/negative.cpp"],
    }[dimension]
    tokens: list[str] = []
    for relative in paths:
        tokens.extend(_independent_tokens((root / relative).read_text()))
    structural_counts = tuple(tokens.count(keyword) for keyword in ("struct", "enum", "optional", "vector", "array", "if", "for", "while", "switch", "return", "nullopt"))
    semantic_words = sorted(set(re.findall(r"[a-z][a-z_-]{4,}", " ".join(tokens))))
    payload = repr((structural_counts, tokens, semantic_words)).encode()
    return hashlib.sha256(payload).hexdigest()


def test_exact_binding_inventory_and_distinct_contracts() -> None:
    assert len(tasks.CASES) == 25
    assert len({case.task_id for case in tasks.CASES}) == 25
    assert tasks.CASES[0].task_id == "coord-affine-lattice"
    assert tasks.CASES[-1].task_id == "coord-dihedral-canonical"
    assert "coord-hex-ring-address" in {case.task_id for case in tasks.CASES}
    assert "coord-morton-interleave" not in {case.task_id for case in tasks.CASES}
    assert "coord-reflective-boundary-fold" in {case.task_id for case in tasks.CASES}
    assert "coord-quadtree-path" not in {case.task_id for case in tasks.CASES}
    assert len({case.mechanism for case in tasks.CASES}) == 25
    assert len({case.header for case in tasks.CASES}) == 25
    assert len({case.reference for case in tasks.CASES}) == 25
    assert len({case.private for case in tasks.CASES}) == 25
    assert len({case.negative for case in tasks.CASES}) == 25


def test_representation_width_mechanism_alias_control() -> None:
    packed = "Morton bit interleave two sixteen-bit axes into a packed integer."
    radix = "Morton quadrant digits interleave paired x/y bits in base four."
    quadtree = "Quadtree quadrant path walks top-down paired coordinate bits."
    assert tasks._mechanism_alias_marker(packed, radix) == ("morton", "interleav")
    assert tasks._mechanism_alias_marker(packed, quadtree) == ("morton", "interleav")
    assert tasks._mechanism_alias_marker(packed, "six-direction axial hex shell rank") is None


def test_materializes_only_role_safe_new_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    manifest = tasks.materialize(out)
    assert manifest["task_count"] == 25
    assert len(list(out.glob("coord-*/.meta/config.json"))) == 25
    assert len(list((out / ".state/controls").glob("*/.meta/config.json"))) == 3
    assert (out / ".state/controls/cross-alias-controls.json").is_file()
    for case in tasks.CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        prompt = build_prompt(load_task(root))
        assert ".meta/" not in prompt
        assert "CMakeLists.txt" not in prompt
        assert case.reference[:100] not in prompt


def test_output_and_cross_tree_collision_guards(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    with pytest.raises(tasks.CreatorError, match="invalid_output_root"):
        tasks.materialize(tasks.LEGACY_ROOTS[0])
    collision = tasks.LEGACY_ROOTS[1] / "reserved" / tasks.CASES[0].task_id / ".meta"
    collision.mkdir(parents=True)
    (collision / "config.json").write_text("{}")
    with pytest.raises(tasks.CreatorError, match="existing_task_id"):
        tasks.materialize(out)


def test_all_300_pairs_have_independent_seven_dimension_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    screen = tasks.diversity_screen(out)
    assert screen["root_count"] == 25
    assert screen["pair_count"] == 300
    assert tuple(screen["dimensions"]) == tasks.DIMENSIONS
    assert all(row["pass"] for row in screen["decisions"])
    assert screen["cross_alias_controls"][0]["decision"] == "duplicate_family"
    assert all(set(row["dimensions"]) == set(tasks.DIMENSIONS) for row in screen["decisions"])
    # This recomputes role evidence without calling the production extractor.
    for dimension in tasks.DIMENSIONS:
        evidence = {_independent_role_digest(out / case.task_id, dimension) for case in tasks.CASES}
        assert len(evidence) == 25
    assert len(list(combinations(tasks.CASES, 2))) == 300


@pytest.mark.parametrize("control_name", ["domain-identifier-rename", "constants-policy-only", "opposite-end-selection"])
def test_materialized_clone_controls_are_changed_coherent_and_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, control_name: str) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    screen = tasks.diversity_screen(out)
    control = screen["controls"][control_name]
    assert control["changed_files"]
    assert control["decision"]["pass"] is True
    assert all(value["pass"] is False for value in control["decision"]["dimensions"].values())
    source = out / "coord-torus-nearest-delta"
    clone = out / control["root"]
    assert clone.is_dir()
    assert any((source / path).read_bytes() != (clone / path).read_bytes() for path in control["changed_files"])
    assert (clone / ".meta/config.json").is_file()
    assert (clone / "CMakeLists.txt").is_file()


def test_verify_core_binds_inventory_prompts_family_and_holdouts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    receipt = tasks.verify_core(out)
    assert receipt["root_count"] == 25
    assert receipt["pair_count"] == 300
    assert receipt["control_count"] == 3
    assert receipt["prompt_boundary"] == {"count": 25, "status": "pass"}
    assert receipt["contamination"]["holdout_root_count"] == 26
    assert receipt["status"] == "structural_pass_pending_runtime"


def test_generated_drift_and_non_owner_force_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    (out / tasks.CASES[0].task_id / ".docs/instructions.md").write_text("drift\n")
    with pytest.raises(tasks.CreatorError, match="generator_output_drift"):
        tasks.verify_core(out)
    manifest_path = out / ".state/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["owner"] = "foreign-owner.py"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(tasks.CreatorError, match="foreign_output_root"):
        tasks.materialize(out, force=True)


def test_compiler_resolution_prefers_image_then_path_then_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv(tasks.COMPILER_ENV, raising=False)
    image_compiler = tmp_path / "image-g++"
    image_compiler.write_text("")
    monkeypatch.setattr(tasks, "IMAGE_COMPILER", str(image_compiler))
    assert tasks._compiler_path() == str(image_compiler)
    monkeypatch.setattr(tasks, "IMAGE_COMPILER", str(tmp_path / "absent-g++"))
    assert tasks._compiler_path() in {shutil.which("c++"), shutil.which("g++")}
    override = tmp_path / "override-g++"
    override.write_text("")
    monkeypatch.setenv(tasks.COMPILER_ENV, str(override))
    assert tasks._compiler_path() == str(override)
    monkeypatch.setenv(tasks.COMPILER_ENV, str(tmp_path / "missing-override"))
    with pytest.raises(tasks.CreatorError, match="host_compiler_not_found"):
        tasks._compiler_path()
    monkeypatch.delenv(tasks.COMPILER_ENV, raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(tasks.CreatorError, match="host_compiler_not_found"):
        tasks._compiler_path()


def test_verify_runtime_labels_host_and_grader_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)

    def fake_mode(root: Path, workspace: Path, *, sanitizer: bool) -> dict[str, object]:
        return {"mode": "sanitizer" if sanitizer else "normal", "discovered_tests": 3, "ctest_status": "pass", "negative_exit": 1, "negative_rejected": True, "configure_command": ["cmake"]}

    monkeypatch.setattr(tasks, "_runtime_mode", fake_mode)
    monkeypatch.setattr(tasks, "_toolchain", lambda: {"compiler_path": "stub", "compiler_version": "stub", "compiler_hash": "sha256:0", "cmake_version": "stub"})
    monkeypatch.delenv(tasks.GRADER_ENV, raising=False)
    host = tasks.verify_runtime(out, result_out=tmp_path / "host.json")
    assert host["evidence_class"] == "host_runtime"
    assert host["network_policy"] == "host_not_enforced"
    assert host["root_count"] == 25
    assert host["control_count"] == 3
    monkeypatch.setenv(tasks.GRADER_ENV, "docker")
    grader = tasks.verify_runtime(out, result_out=tmp_path / "grader.json")
    assert grader["evidence_class"] == "docker_sanity"
    assert grader["network_policy"] == "none"
