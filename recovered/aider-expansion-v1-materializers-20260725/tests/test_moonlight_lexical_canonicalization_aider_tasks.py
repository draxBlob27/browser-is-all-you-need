from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_lexical_canonicalization_aider_tasks as tasks
from w8_biayn.integrations.moonlight_lexical_canonicalization_contracts import build_contract


def _patch_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    expansion = repo / ".w8-biayn/data/aider-tasks-expansion-v1"
    out = expansion / "validation-parsing/lexical-canonicalization-eoi"
    curriculum = repo / tasks.CURRICULUM.relative_to(tasks.REPO_ROOT)
    curriculum.parent.mkdir(parents=True)
    curriculum.write_text(tasks.CURRICULUM.read_text())
    family_spec = repo / tasks.FAMILY_SPEC.relative_to(tasks.REPO_ROOT)
    family_spec.parent.mkdir(parents=True)
    family_spec.write_text(tasks.FAMILY_SPEC.read_text())
    holdouts = repo / ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
    for slug in tasks.OFFICIAL_HOLDOUTS:
        root = holdouts / slug / ".docs"
        root.mkdir(parents=True)
        (root / "instructions.md").write_text(f"Independent official holdout {slug} exercise.\n")
    monkeypatch.setattr(tasks, "REPO_ROOT", repo)
    monkeypatch.setattr(tasks, "CURRICULUM", curriculum)
    monkeypatch.setattr(tasks, "FAMILY_SPEC", family_spec)
    monkeypatch.setattr(tasks, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(tasks, "DEFAULT_OUT", out)
    monkeypatch.setattr(tasks, "LEGACY_ROOTS", (repo / ".w8-biayn/data/aider-tasks", repo / ".w8-biayn/data/aider-tasks-reverify"))
    monkeypatch.setattr(tasks, "HOLDOUT_ROOT", holdouts)
    owner = repo / tasks.OWNER
    owner.parent.mkdir(parents=True)
    owner.write_text(Path(tasks.__file__).read_text())
    return out


def test_curriculum_has_exact_unique_100() -> None:
    cases = tasks.cases()
    assert len(cases) == 100
    assert len({case.task_id for case in cases}) == 100
    assert cases[0].task_id == "lex-vessel-call-sign"
    assert cases[-1].task_id == "lex-sentinel-command-stream"
    contracts = [build_contract(case.task_id, case.api_stem, case.index) for case in cases]
    assert len({contract.band for contract in contracts}) == 10
    assert all(sum(contract.band == band for contract in contracts) == 10 for band in {item.band for item in contracts})
    assert all(len({contracts[index * 10 + offset].profile for offset in range(10)}) == 10 for index in range(10))


def test_materializes_role_safe_owner_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    manifest = tasks.materialize(out)
    assert manifest["task_count"] == 100
    assert len(list(out.glob("lex-*/.meta/config.json"))) == 100
    for case in tasks.cases():
        config = json.loads((out / case.task_id / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        prompt = [".docs/introduction.md", ".docs/instructions.md", *config["files"]["solution"]]
        assert all(".meta" not in path and path != "CMakeLists.txt" for path in prompt)
        instructions = (out / case.task_id / ".docs/instructions.md").read_text()
        assert "documented reserved rolling-checksum spelling" not in instructions
        assert "exact" in instructions.lower()
        assert (out / case.task_id / ".meta/negative_test.cpp").is_file()
        private_test = (out / case.task_id / ".meta/private_test.cpp").read_text()
        assert "||!a." not in private_test
        assert "||!again." not in private_test
        assert "||!(a." in private_test
        assert "||!(again." in private_test


def _independent_shape(text: str) -> tuple[str, ...]:
    text = re.sub(r"//[^\n]*|/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " LIT ", text)
    text = re.sub(r"\b\d+(?:\.\d+)?(?:[uUlLfF]+)?\b", " NUM ", text)
    keep = {"if", "else", "for", "while", "return", "vector", "array", "map", "optional", "pair", "string", "int", "long", "double", "bool", "size_t", "digit_sum", "strictly_increasing", "all_unique", "contains_digit", "shares_symbol", "identifier_hyphen_count", "locator_slash_count", "decoded_atom_bytes", "mantissa_digit_count", "version_component_count", "normalized_segment_count", "unit_symbol_count", "range_count", "record_field_count", "declared_payload_bytes", "checksum_remainder", "approval_word", "increasing_digit_count", "unique_symbol_count", "bounded_witness", "required_digit_index", "parity_even", "leading_symbol", "witness_disjoint", "optional_value"}
    raw = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|==|!=|>=|<=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,:?=]", text)
    return tuple(token if token in keep or not token[0].isalpha() else "ID" for token in raw)


def test_emitted_semantics_are_not_identifier_or_literal_clones(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    references = set()
    oracles = set()
    negatives = set()
    for case in tasks.cases():
        root = out / case.task_id
        references.add(_independent_shape((root / ".meta/example.cpp").read_text()))
        oracles.add(_independent_shape((root / "visible_test.cpp").read_text() + (root / ".meta/private_test.cpp").read_text()))
        negatives.add(_independent_shape((root / ".meta/negative.cpp").read_text()))
    assert len(references) == 100
    assert len(oracles) == 100
    assert len(negatives) == 100


def test_rejects_legacy_and_collision_outputs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    with pytest.raises(tasks.CreatorError, match="invalid_output_root"):
        tasks.materialize(tasks.LEGACY_ROOTS[0])
    collision = tasks.LEGACY_ROOTS[0] / "other" / tasks.cases()[0].task_id / ".meta"
    collision.mkdir(parents=True)
    (collision / "config.json").write_text("{}")
    with pytest.raises(tasks.CreatorError, match="existing_task_id"):
        tasks.materialize(out)


def test_all_pairs_and_controls_are_independently_accounted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    screen = tasks.diversity_screen(out)
    assert screen["root_count"] == 100
    assert screen["pair_count"] == 4950
    assert tuple(screen["dimensions"]) == tasks.DIMENSIONS
    assert all(row["pass"] for row in screen["decisions"])
    assert all(set(row["dimensions"]) == set(tasks.DIMENSIONS) for row in screen["decisions"])
    assert len(screen["controls"]) == 3
    for control in screen["controls"].values():
        assert control["changed_files"]
        assert control["actual_changed_files"] == sorted(set(control["changed_files"]))
        assert control["production_evaluator_rejected"] is True
        assert set(control["rejected_dimensions"]) == set(tasks.DIMENSIONS)
        assert all(not decision["pass"] for decision in control["dimensions"].values())
    opposite = out / ".state/controls/opposite-end-selection"
    assert "std::reverse" not in (opposite / ".meta/example.cpp").read_text()
    assert 'a.canonical!="[18,14-16];OK!OK;"' in (opposite / "visible_test.cpp").read_text()
    assert 'a.canonical!="[18,14-16];OK!OK;"' in (opposite / ".meta/private_test.cpp").read_text()


@pytest.mark.parametrize("mutation", ["domain-identifier-rename", "constants-policy-only", "opposite-end-selection"])
def test_clone_controls_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mutation: str) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    screen = tasks.diversity_screen(out)
    control = screen["controls"][mutation]
    assert control["actual_changed_files"]
    assert control["mutation_witness"]
    assert control["production_evaluator_rejected"] is True
    assert set(control["rejected_dimensions"]) == set(tasks.DIMENSIONS)


def test_tree_hash_detects_generated_drift(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    (out / tasks.cases()[0].task_id / ".docs/instructions.md").write_text("drift\n")
    with pytest.raises(tasks.CreatorError, match="generator_output_drift"):
        tasks.verify_core(out)


def test_cycle03_adversarial_findings_are_owner_encoded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    assert "numeric_limits<int>::max" in tasks.COMMON_HELPERS
    owner_text = Path(tasks.__file__).read_text()
    assert "def _apply_clone_policy" not in owner_text
    for case in tasks.cases():
        root = out / case.task_id
        prompt = (root / ".docs/instructions.md").read_text()
        assert "parser cursor at failure" in prompt
        assert "private grader" not in prompt
        assert "false substitute" not in prompt
        private = (root / ".meta/private_test.cpp").read_text()
        assert "120U,'9'" in private
        contract = build_contract(case.task_id, case.api_stem, case.index)
        if contract.band == "escaped-quoted-atom":
            assert contract.valid_variants
            escaped = contract.valid_variants[0][0]
            assert "\\\\" in escaped and '\\"' in escaped
        if contract.band == "ordered-range-list":
            assert any(",];" in value for value in contract.other_invalid)
            assert "range after comma" in contract.source
        if contract.band == "length-framed-input":
            assert contract.valid_variants and contract.valid_variants[0][0].startswith("1:")
            assert "payload.size()<=" not in contract.source


def test_json_refresh_replaces_unwritable_receipt(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    receipt.write_text("{}\n")
    receipt.chmod(0o444)
    tasks._json(receipt, {"status": "pass"})
    assert json.loads(receipt.read_text()) == {"status": "pass"}


def test_log_base_separates_host_and_docker_evidence(tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert tasks._log_base(out, "docker_sanity") == out / ".state/runtime-logs"
    assert tasks._log_base(out, "host_iteration") == out / ".state/runtime-logs-host"


def test_verify_core_rebinds_manifest_provenance_after_spec_change(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = _patch_paths(monkeypatch, tmp_path)
    tasks.materialize(out)
    with tasks.FAMILY_SPEC.open("a") as handle:
        handle.write("\nLedger provenance drift probe.\n")
    receipt = tasks.verify_core(out)
    manifest = json.loads((out / ".state/manifest.json").read_text())
    assert manifest["family_spec_hash"] == tasks._file_sha(tasks.FAMILY_SPEC)
    assert receipt["manifest_provenance_refreshed"] == ["family_spec_hash"]


def test_history_records_missing_cycles_truthfully() -> None:
    spec = re.sub(r"\s+", " ", tasks.FAMILY_SPEC.read_text())
    assert "not present in the current tree copy" in spec
    assert "are preserved under `.state/audits/cycle-01/`" not in spec
    assert "are preserved under `.state/audits/cycle-02/`" not in spec
    curriculum = re.sub(r"\s+", " ", tasks.CURRICULUM.read_text())
    assert "not present in the current tree copy" in curriculum
    assert "remain preserved beneath family" not in curriculum
