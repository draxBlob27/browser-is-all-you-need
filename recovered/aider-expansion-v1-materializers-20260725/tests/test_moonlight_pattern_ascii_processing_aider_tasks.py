from __future__ import annotations

import inspect
import json
import re
import shutil
from itertools import combinations
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_pattern_ascii_processing_aider_tasks as owner
from w8_biayn.integrations.moonlight_pattern_ascii_processing_cases import CASES


def _sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    expansion = repo / ".w8-biayn/data/aider-tasks-expansion-v1"
    legacy = repo / ".w8-biayn/data/aider-tasks"
    reverify = repo / ".w8-biayn/data/aider-tasks-reverify"
    holdouts = repo / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
    expansion.mkdir(parents=True)
    legacy.mkdir(parents=True)
    reverify.mkdir(parents=True)
    for slug in owner.OFFICIAL_HOLDOUTS:
        root = holdouts / slug
        (root / ".docs").mkdir(parents=True)
        (root / ".docs/instructions.md").write_text(f"official holdout {slug}\n")
    monkeypatch.setattr(owner, "REPO_ROOT", repo)
    monkeypatch.setattr(owner, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(owner, "LEGACY_ROOT", legacy)
    monkeypatch.setattr(owner, "REVERIFY_ROOT", reverify)
    monkeypatch.setattr(owner, "HOLDOUT_ROOT", holdouts)
    monkeypatch.setattr(owner, "CURRICULUM", Path(__file__).parents[1] / owner.CURRICULUM.relative_to(Path(__file__).parents[1]))
    monkeypatch.setattr(owner, "FAMILY_SPEC", Path(__file__).parents[1] / owner.FAMILY_SPEC.relative_to(Path(__file__).parents[1]))
    return expansion / "text-grid-logic/pattern-ascii-processing"


def test_case_inventory_is_exactly_twenty_and_contracts_are_not_profile_variants() -> None:
    assert len(CASES) == 20
    assert len({case.task_id for case in CASES}) == 20
    assert len({case.function for case in CASES}) == 20
    assert len({case.body for case in CASES}) == 20
    assert len({case.params for case in CASES}) >= 16
    assert all(case.negative_old != case.negative_new for case in CASES)
    assert all(case.body.count(case.negative_old) == 1 for case in CASES)
    assert all(len(case.profile) == len(set(case.profile)) == 4 for case in CASES)


def test_materialization_has_role_safe_task_named_files_and_new_lineage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    manifest = owner.materialize(out)
    assert manifest["root_count"] == 20
    assert manifest["task_ids"] == [case.task_id for case in CASES]
    assert manifest["status"] == "generated_pending_creator_preflight"
    assert not any((out / case.task_id).is_symlink() for case in CASES)
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["lineage"] == "new-root"
        assert provenance["parent_task_id"] is None
        assert provenance["family_id"] == owner.FAMILY_ID
        assert (root / ".meta/negative.cpp").read_text() != (root / ".meta/example.cpp").read_text()
        assert "return {};" in (root / f"{case.task_id}.cpp").read_text()


def _independent_tokens(text: str) -> set[str]:
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " token ", text)
    return set(re.findall(r"[a-z_]+|==|!=|<=|>=|&&|\|\||[%&|<>+*/-]", text.lower()))


def test_all_190_pairs_pass_every_recorded_dimension_and_have_independent_witnesses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    owner.materialize(out)
    screen = owner._family_screen(out)
    assert screen["root_count"] == 20
    assert screen["pair_count"] == screen["expected_pair_count"] == 190
    assert tuple(screen["dimensions"]) == owner.HARD_DIMENSIONS
    seen: set[tuple[str, str]] = set()
    for pair in screen["pairs"]:
        seen.add((pair["left"], pair["right"]))
        assert set(pair["decisions"]) == set(owner.HARD_DIMENSIONS)
        for dimension, decision in pair["decisions"].items():
            assert decision["pass"] is True, (pair["left"], pair["right"], dimension)
            assert decision["symmetric_difference"] >= 4
    assert len(seen) == len(list(combinations(CASES, 2))) == 190

    # This tokenizer is intentionally separate from the production normalizer.
    # It proves every pair changes real API/reference/test material, rather than
    # merely repeating the helper's aggregate verdict.
    signatures: dict[str, tuple[set[str], set[str], set[str]]] = {}
    for case in CASES:
        root = out / case.task_id
        signatures[case.task_id] = (
            _independent_tokens((root / f"{case.task_id}.h").read_text()),
            _independent_tokens((root / ".meta/example.cpp").read_text()),
            _independent_tokens((root / ".meta/task_hidden_test.cpp").read_text()),
        )
    for left, right in combinations(CASES, 2):
        for left_scope, right_scope in zip(signatures[left.task_id], signatures[right.task_id], strict=True):
            assert left_scope != right_scope


def test_coherent_controls_change_files_and_are_rejected_by_production_screen(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    owner.materialize(out)
    screen = owner._family_screen(out)
    assert set(screen["controls"]) == set(owner.CONTROL_KINDS)
    manifest = json.loads((out / ".state/adversarial-controls.json").read_text())
    for kind, result in screen["controls"].items():
        assert manifest[kind]["changed_file_count"] > 0
        assert result["production_rejected"] is True
        assert not all(item["pass"] for item in result["decisions"].values())
        root = out / manifest[kind]["root"]
        assert (root / "CMakeLists.txt").is_file()
        assert (root / ".meta/example.cpp").is_file()
        assert (root / ".meta/task_hidden_test.cpp").is_file()


def test_profile_metadata_cannot_create_diversity_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    owner.materialize(out)
    case = CASES[0]
    original = out / case.task_id
    clone = tmp_path / "metadata-only-clone"
    shutil.copytree(original, clone)
    provenance_path = clone / ".meta/provenance.json"
    provenance = json.loads(provenance_path.read_text())
    provenance["semantic_profile"] = {
        "dimensions": ["unique-metadata-label"],
        "mechanism_witnesses": ["never-semantic-evidence"],
    }
    provenance_path.write_text(json.dumps(provenance, sort_keys=True))
    decisions = owner._pair_decisions(original, case, clone, case)
    assert not any(item["pass"] for item in decisions.values())
    source = inspect.getsource(owner._dimension_features)
    assert "case.profile" not in source
    assert "semantic_profile" not in source


def test_emitted_cpp_roles_pass_all_hard_dimensions_without_instruction_features(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    owner.materialize(out)
    monkeypatch.setattr(owner, "_instruction_contract_features", lambda _text, _case: set())
    screen = owner._family_screen(out)
    assert screen["pair_count"] == 190
    assert all(
        decision["pass"]
        for pair in screen["pairs"]
        for decision in pair["decisions"].values()
    )


def test_emitted_doc_domain_and_identifier_clone_adds_no_diversity_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    owner.materialize(out)
    case = CASES[0]
    original = out / case.task_id
    clone = tmp_path / "docs-domain-only-clone"
    shutil.copytree(original, clone)
    instructions_path = clone / ".docs/instructions.md"
    original_text = instructions_path.read_text()
    renamed_text = re.sub(
        r"[A-Za-z]+",
        lambda match: match.group(0) if match.group(0).lower() in owner._CONTRACT_KEEP else "domainword",
        original_text,
    )
    instructions_path.write_text(renamed_text)
    assert owner._instruction_contract_features(original_text, case)
    assert owner._instruction_contract_features(original_text, case) == owner._instruction_contract_features(
        renamed_text, case
    )
    decisions = owner._pair_decisions(original, case, clone, case)
    assert not any(item["pass"] for item in decisions.values())


def test_expansion_siblings_are_frozen_and_screened(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    sibling = owner.EXPANSION_ROOT / "preexisting/family/preexisting-sibling"
    owner._write_root(sibling, owner._task_files(CASES[0]))
    owner.materialize(out)
    inventory = json.loads((out / ".state/source-inventory.json").read_text())
    assert inventory["schema_version"] == "pattern-ascii-source-inventory-v2"
    assert inventory["expansion_count"] == 1
    assert {entry["tree"] for entry in inventory["entries"]} == {"expansion"}
    assert {"api_hash", "tests_hash", "contract_hash", "lineage_hash"} <= set(inventory["entries"][0])
    with pytest.raises(owner.VerificationError, match="duplicate_prompt"):
        owner._cross_tree_screen(out)


def test_output_guard_rejects_existing_trees_and_outside_paths(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    assert owner._validate_output(out) == out.resolve()
    with pytest.raises(owner.VerificationError, match="unsafe_path"):
        owner._validate_output(owner.LEGACY_ROOT / "text-grid-logic/family")
    with pytest.raises(owner.VerificationError, match="unsafe_path"):
        owner._validate_output(tmp_path / "outside")


def test_docker_verifier_is_network_disabled_fresh_and_hash_bound() -> None:
    source = inspect.getsource(owner.docker_sanity)
    assert '"--network", "none"' in source
    assert "Unix Makefiles" in source
    assert "-fsanitize=address,undefined" in source
    assert "grader_mount_hash_mismatch" in source
    assert "negative_fixture_not_rejected" in source
    assert "sanitizer_test_count_mismatch" in source


def test_docs_follow_benchmark_register(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    owner.materialize(out)
    banned = re.compile(
        r"clean-room|\bthis task\b|\bSFT\b|benchmark|campaign|remediation|oracle"
        r"|negative fixture|reference implementation|generator|adversarial"
        r"|hard rule|forbidden substitute|do not substitute|grader|hidden test"
        r"|local_family_verified|prompt|\bmodel\b",
        re.IGNORECASE,
    )
    for case in CASES:
        root = out / case.task_id
        instructions = (root / ".docs/instructions.md").read_text()
        introduction = (root / ".docs/introduction.md").read_text()
        assert instructions.startswith("# Instructions\n")
        assert "## Example\n" in instructions
        assert "core mechanism" not in instructions
        assert case.contract in instructions
        assert f"`{case.function}`" in instructions and f"`{case.task_id}.h`" in instructions
        assert introduction.startswith(f"# {case.title}\n\n")
        assert len(introduction.split()) >= 40
        assert not banned.search(instructions)
        assert not banned.search(introduction)


def test_curriculum_and_spec_bind_count_cell_audit_loop_and_nonclaims() -> None:
    curriculum = owner.CURRICULUM.read_text()
    specification = owner.FAMILY_SPEC.read_text()
    assert "exactly 20" in curriculum
    assert "190" in curriculum and "190" in specification
    assert ".w8-biayn/data/aider-tasks-expansion-v1/" in curriculum
    assert "independent" in curriculum and "fresh" in curriculum
    assert "local_family_verified" in curriculum
    assert "no SFT" in curriculum and "no benchmark" in curriculum
    source = inspect.getsource(owner._audit_subject)
    assert "remedy_records" in source and "remedy_spec" in source
