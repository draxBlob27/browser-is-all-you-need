from __future__ import annotations

import hashlib
import itertools
import json
import re
import shutil
from pathlib import Path

import pytest

from w8_biayn.integrations import (
    moonlight_duration_elapsed_countdown_expansion_aider_tasks as expansion,
)


def _independent_tokens(content: str, *, keep_names: bool) -> tuple[str, ...]:
    content = re.sub(r"/\*.*?\*/|//[^\n]*", " ", content, flags=re.S)
    content = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", content)
    raw = re.findall(
        r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]",
        content,
    )
    keywords = {
        "if",
        "else",
        "for",
        "while",
        "return",
        "class",
        "struct",
        "const",
        "auto",
        "bool",
        "int",
        "long",
        "void",
        "true",
        "false",
        "public",
        "private",
        "namespace",
        "std",
        "vector",
        "set",
        "map",
        "sort",
        "stable_sort",
        "min",
        "max",
    }
    return tuple(
        token if keep_names or token in keywords or not re.match(r"[A-Za-z_]", token) else "ID"
        for token in raw
    )


def _independent_dimensions(root: Path) -> dict[str, set[tuple[str, ...]]]:
    config = json.loads((root / ".meta/config.json").read_text())
    values = {
        "docs": (root / ".docs/instructions.md").read_text(),
        "header": (root / config["files"]["solution"][0]).read_text(),
        "reference": (root / config["files"]["example"][1]).read_text(),
        "visible": (root / "task_visible_test.cpp").read_text(),
        "hidden": (root / ".meta/task_hidden_test.cpp").read_text(),
        "negative": (root / ".meta/negative_false_substitute.cpp").read_text(),
    }
    control = "\n".join(
        line
        for line in values["reference"].splitlines()
        if re.search(
            r"\b(if|else|for|while|return|sort|accumulator|witness|sample|numerator|spent|left|right|net|prefix|serial_cursor|even_total|odd_total|previous_sample)\b",
            line,
        )
    )
    negative_delta = "\n".join(
        line
        for line in values["negative"].splitlines()
        if line not in values["reference"].splitlines()
    )
    mechanism_start = values["reference"].index("  Big accumulator = 0;")
    mechanism_end = values["reference"].index("  if (!arithmetic_ok", mechanism_start)
    mechanism_core = values["reference"][mechanism_start:mechanism_end]
    negative_start = values["negative"].index("  Big accumulator = 0;")
    negative_end = values["negative"].index("  if (!arithmetic_ok", negative_start)
    negative_core = values["negative"][negative_start:negative_end]
    material = {
        "public_api": values["header"] + values["docs"],
        "owned_state_algorithm": mechanism_core,
        "mutation_selection_rules": values["docs"] + control,
        "invalid_boundary_behavior": values["docs"] + values["hidden"],
        "reference_control_flow": control,
        "deterministic_oracle": values["visible"] + values["hidden"],
        "topic_specific_negative_fixture": "\n".join(
            line
            for line in negative_core.splitlines()
            if re.search(
                r"\b(if|else|for|while|return|sort|accumulator|witness|sample|numerator|spent|left|right|net|prefix|serial_cursor|even_total|odd_total|previous_sample)\b",
                line,
            )
        )
        + negative_delta
        + values["hidden"],
    }
    assert set(material) == set(expansion.HARD_RULE_DIMENSIONS)
    result = {}
    for name, content in material.items():
        tokens = _independent_tokens(
            content,
            keep_names=name
            in {
                "public_api",
                "mutation_selection_rules",
                "invalid_boundary_behavior",
                "deterministic_oracle",
            },
        )
        width = 5 if len(tokens) >= 5 else max(1, len(tokens))
        result[name] = {
            tokens[index : index + width] for index in range(max(1, len(tokens) - width + 1))
        }
    return result


def test_inventory_is_exactly_eighty_contract_first_new_roots() -> None:
    assert expansion.MIN_ROOTS == expansion.MAX_ROOTS == 80
    assert len(expansion.CASES) == 80
    assert len({case.task_id for case in expansion.CASES}) == 80
    assert len({case.mechanism for case in expansion.CASES}) == 80
    assert len({case.strategy for case in expansion.CASES}) == 80
    assert {case.strategy for case in expansion.CASES} == set(range(80))
    assert all(
        case.invalid_rule and case.ordering_rule and case.boundary_rule for case in expansion.CASES
    )
    assert all(
        "LLONG_MAX is valid" in case.boundary_rule
        for case in expansion.CASES
        if case.strategy % 10 == 2
    )


def test_materializes_only_expansion_tree_with_role_correct_named_files(tmp_path: Path) -> None:
    out = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1/time-date/duration-elapsed-countdown"
    previous = expansion.EXPANSION_ROOT
    expansion.EXPANSION_ROOT = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1"
    try:
        roots = expansion.build(out)
    finally:
        expansion.EXPANSION_ROOT = previous
    assert len(roots) == 80
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["lineage"] == "replacement-new-root"
        assert provenance["replaces"] in expansion.REJECTED_CYCLE_01_IDS
        assert provenance["count_plan_cell"] == expansion.COUNT_PLAN_CELL
        assert provenance["version"] == 4
        assert (root / ".meta/negative_false_substitute.cpp").is_file()
        assert (root / ".meta/negative_transform.cpp").is_file()
        hidden = (root / ".meta/task_hidden_test.cpp").read_text()
        assert all(
            marker in hidden
            for marker in (
                "transform_probe",
                "reducer_boundary",
                "malformed_empty_id",
                "malformed_negative_start",
                "malformed_reversed_span",
                "unsorted_input",
                "primary_key_tie",
                "near_limit",
                "overflow_or_range_bound",
                "negative_limit",
                "LLONG_MAX",
            )
        )
        assert hidden.count("malformed_") >= 4
    raw = json.loads((out / ".state/proposals/raw-proposals.json").read_text())
    candidates = json.loads((out / ".state/candidates/candidate-manifest.json").read_text())
    rejected = json.loads((out / ".state/candidates/rejected-manifest.json").read_text())
    assert raw["count"] == 160
    assert candidates["count"] == rejected["count"] == 80
    assert {row["task_id"] for row in rejected["rows"]} == set(expansion.REJECTED_CYCLE_01_IDS)


def test_core_screen_records_all_3160_pairs_and_seven_separate_dimensions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = tmp_path / "expansion"
    monkeypatch.setattr(expansion, "EXPANSION_ROOT", tmp_path)
    monkeypatch.setattr(expansion, "LEGACY_ROOT", tmp_path / "legacy")
    monkeypatch.setattr(expansion, "REVERIFY_ROOT", tmp_path / "reverify")
    holdout = tmp_path / "holdout"
    for task_id in expansion.OFFICIAL_AIDER_CPP_HOLDOUTS:
        root = holdout / task_id
        root.mkdir(parents=True)
        (root / "instructions.md").write_text(f"official holdout {task_id}\n")
    monkeypatch.setattr(expansion, "DEFAULT_HOLDOUT_ROOT", holdout)
    expansion.build(out)
    manifest = expansion.verify_core(out)
    hard_rule = manifest["screen"]["hard_rule"]
    assert manifest["family_tree_hash"] == expansion._tree_hash(out)
    assert manifest["root_hash_ledger_hash"].startswith("sha256:")
    assert hard_rule["root_count"] == 80
    assert hard_rule["pair_count"] == hard_rule["expected_pair_count"] == 3160
    assert hard_rule["dimensions"] == list(expansion.HARD_RULE_DIMENSIONS)
    expected_pairs = {
        tuple(sorted(pair))
        for pair in itertools.combinations((case.task_id for case in expansion.CASES), 2)
    }
    actual_pairs = {tuple(sorted((row["left"], row["right"]))) for row in hard_rule["pairs"]}
    assert actual_pairs == expected_pairs
    for row in hard_rule["pairs"]:
        assert row["behavior_distinct"] is True
        decisions = row["dimensions"]
        assert decisions["pass"] is True
        for dimension in expansion.HARD_RULE_DIMENSIONS:
            assert decisions[dimension]["distinct"] is True
            assert decisions[dimension]["overlap"] < 0.995
    assert manifest["screen"]["semantic_holdout"]["comparison_count"] == 2080
    cross_tree = manifest["screen"]["cross_tree_semantic"]
    assert cross_tree["status"] == "pass"
    assert all(row["comparison_count"] == 0 for row in cross_tree["sources"].values())
    clone = cross_tree["adversarial_contract_clone"]
    assert clone["similarity"] >= clone["threshold"]
    assert clone["decision"] == "rejected:cross_tree_contract_near_duplicate"

    # Independent extraction inspects the emitted artifacts, not case labels
    # or the production helper's top-level verdict.
    independent = {
        root.name: _independent_dimensions(root)
        for root in sorted(out.iterdir())
        if root.is_dir() and root.name != ".state"
    }
    assert len(independent) == 80
    for left, right in itertools.combinations(sorted(independent), 2):
        for dimension in expansion.HARD_RULE_DIMENSIONS:
            a, b = independent[left][dimension], independent[right][dimension]
            overlap = len(a & b) / len(a | b) if a | b else 1.0
            assert a ^ b, (left, right, dimension)
            assert overlap < 0.995, (left, right, dimension, overlap)


def test_adversarial_controls_are_changed_coherent_and_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "expansion"
    monkeypatch.setattr(expansion, "EXPANSION_ROOT", tmp_path)
    monkeypatch.setattr(expansion, "LEGACY_ROOT", tmp_path / "legacy")
    monkeypatch.setattr(expansion, "REVERIFY_ROOT", tmp_path / "reverify")
    expansion.build(out)
    controls = expansion._screen_controls(out)
    assert set(controls) == {
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
        "superficial-token-difference-clone",
    }
    for name, row in controls.items():
        assert row["changed"] is True
        assert row["changed_files"]
        assert row["production_evaluator"] == "rejected:duplicate_family"
        assert row["behavior_vector_equal"] is (name != "opposite-end-selection-clone")
        assert row["base_behavior_hash"].startswith("sha256:")
        assert row["control_behavior_hash"].startswith("sha256:")
        assert row["rejection_basis"]
        assert row["dimensions"]["pass"] is False
        assert any(
            not row["dimensions"][dimension]["distinct"]
            for dimension in expansion.HARD_RULE_DIMENSIONS
        ), name
        root = out / ".state/hard-rule-controls" / name
        assert (root / "candidate.cpp").is_file()
        assert (root / "task_visible_test.cpp").is_file()
        assert (root / ".meta/task_hidden_test.cpp").is_file()


def test_every_negative_is_nonempty_unique_and_changes_compiled_logic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "expansion"
    monkeypatch.setattr(expansion, "EXPANSION_ROOT", tmp_path)
    monkeypatch.setattr(expansion, "LEGACY_ROOT", tmp_path / "legacy")
    monkeypatch.setattr(expansion, "REVERIFY_ROOT", tmp_path / "reverify")
    roots = expansion.build(out)
    hashes = set()
    for root in roots:
        reference = (root / ".meta/example.cpp").read_text()
        for relative in (
            ".meta/negative_false_substitute.cpp",
            ".meta/negative_transform.cpp",
        ):
            negative = (root / relative).read_text()
            assert negative != reference
            assert "++report.accepted;" not in negative
            assert (
                sum(
                    a != b
                    for a, b in zip(reference.splitlines(), negative.splitlines(), strict=True)
                )
                == 1
            )
            digest = hashlib.sha256(negative.encode()).hexdigest()
            assert digest not in hashes
            hashes.add(digest)
    assert len(hashes) == 160


def test_host_verify_owner_contract_and_single_root_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Path(expansion.__file__).read_text()
    assert '"--verify-host"' in source
    assert "aider-duration-expansion-host-verify-v1" in source
    assert "host_verify_not_completed" in source
    assert "host-oracle-receipt.json" in source
    assert "not_completed (campaign gate: host verify only)" in source
    assert '"Unix Makefiles"' in source
    assert "-fsanitize=address,undefined" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "negative_fixture_not_rejected" in source

    out = tmp_path / "expansion"
    monkeypatch.setattr(expansion, "EXPANSION_ROOT", tmp_path)
    monkeypatch.setattr(expansion, "LEGACY_ROOT", tmp_path / "legacy")
    monkeypatch.setattr(expansion, "REVERIFY_ROOT", tmp_path / "reverify")
    expansion.build(out)
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        pytest.skip("host toolchain unavailable")
    root = out / expansion.CASES[0].task_id
    work = tmp_path / "builds"
    normal = work / "normal"
    assert expansion._host_build(root, root / ".meta/example.cpp", normal) == 2
    assert expansion._host_ctest_run(normal) == 0
    sanitizer = work / "sanitizer"
    assert (
        expansion._host_build(root, root / ".meta/example.cpp", sanitizer, sanitizer=True) == 2
    )
    assert expansion._host_ctest_run(sanitizer) == 0
    negative = work / "negative"
    assert expansion._host_build(root, root / ".meta/negative_false_substitute.cpp", negative) == 2
    assert expansion._host_ctest_run(negative, expect_failure=True) != 0


def test_existing_and_reverify_output_roots_are_refused() -> None:
    with pytest.raises(RuntimeError, match="existing_tree_immutable|expansion_output_required"):
        expansion.build(expansion.LEGACY_ROOT)
    with pytest.raises(RuntimeError, match="existing_tree_immutable|expansion_output_required"):
        expansion.build(expansion.REVERIFY_ROOT)


def test_docker_owner_contract_is_snapshot_safe_network_disabled_and_fresh() -> None:
    source = Path(expansion.__file__).read_text()
    assert re.search(r'"--network",\s*"none"', source)
    assert '"Unix Makefiles"' in source
    assert "-fsanitize=address,undefined" in source
    assert "grader_mount_hash_mismatch" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "negative_fixture_not_rejected" in source
    assert "adversarial_control_execution_failed" in source


def test_owner_hash_binds_focused_policy_and_expansion_inventory_excludes_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = Path(expansion.__file__).read_text()
    assert "Path(TEST_PATH)" in source
    out = tmp_path / "expansion" / "family"
    foreign = tmp_path / "expansion" / "foreign" / ".meta"
    own = out / expansion.CASES[0].task_id / ".meta"
    foreign.mkdir(parents=True)
    own.mkdir(parents=True)
    payload = {"files": {"solution": [], "test": [], "example": []}}
    (foreign / "config.json").write_text(json.dumps(payload))
    (own / "config.json").write_text(json.dumps(payload))
    inventory = expansion._inventory(tmp_path / "expansion", exclude=out)
    assert inventory["count"] == 1
    assert inventory["records"][0]["task_id"] == "foreign"


def test_docs_follow_benchmark_register() -> None:
    banned = re.compile(
        r"clean-room|\bthis task\b|\bSFT\b|benchmark|campaign|remediation|oracle\b"
        r"|negative fixture|reference implementation|generator|adversarial"
        r"|hard rule|forbidden substitute|do not substitute|grader|hidden test"
        r"|local_family_verified|prompt|\bmodel\b|core mechanism|private \w+ probe",
        re.IGNORECASE,
    )
    for case in expansion.CASES:
        instructions = expansion._instructions(case)
        assert instructions.startswith("# Instructions\n")
        assert "## Example\n" in instructions
        assert "complete report is valid with value" in instructions
        assert not banned.search(instructions)
