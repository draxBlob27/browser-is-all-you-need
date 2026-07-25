from __future__ import annotations

import json
import re
from itertools import combinations
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_overflow_scoring_combinatorial_aider_tasks as family


def test_binding_count_clusters_and_dimensions() -> None:
    assert len(family.TASKS) == 40
    assert len({case.task_id for case in family.TASKS}) == 40
    assert [case.cluster for case in family.TASKS].count("overflow") == 14
    assert [case.cluster for case in family.TASKS].count("scoring") == 13
    assert [case.cluster for case in family.TASKS].count("combinatorial") == 13
    assert len({case.mechanism for case in family.TASKS}) == 40
    assert len(list(combinations(family.TASKS, 2))) == 780
    assert len(family.HARD_RULE_DIMENSIONS) == 7


def test_docs_shape_follows_benchmark_conventions() -> None:
    for case in family.TASKS:
        files = family._task_files(case)
        instructions = files[".docs/instructions.md"]
        assert instructions.startswith("# Instructions\n")
        assert "## Examples" in instructions
        assert case.forbidden in instructions
        assert case.boundary[1:41] in instructions
        for banned in (
            "clean-room",
            "core mechanism",
            "does not satisfy this task",
            "whole-file response",
            "hidden test",
            "oracle",
            "grader",
            "benchmark",
        ):
            assert banned not in instructions, (case.task_id, banned)
        introduction = files[".docs/introduction.md"]
        assert introduction.startswith(f"# {case.title}\n\n")
        assert "clean-room" not in introduction
        assert len(introduction.split("\n\n")) >= 3


def test_owner_refuses_both_existing_trees() -> None:
    for forbidden in (family.LEGACY_ROOT, family.REVERIFY_ROOT):
        with pytest.raises(family.VerificationError, match="unsafe_output_root"):
            family._safe_output(forbidden)


def test_creator_cycles_are_append_only(tmp_path: Path) -> None:
    cycles = tmp_path / "cycles"
    cycles.mkdir()
    (cycles / "cycle-001-creator-preflight.json").write_text("{}")
    (cycles / "cycle-003-creator-preflight.json").write_text("{}")
    (cycles / "evidence-invalidated-20260722T000000000000Z.json").write_text("{}")
    assert family._next_creator_cycle(tmp_path) == 4


def test_materialization_roles_and_separate_candidate_states(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    expansion = tmp_path / ".w8-biayn/data/aider-tasks-expansion-v1"
    out = expansion / "numerical-arithmetic/overflow-scoring-combinatorial"
    monkeypatch.setattr(family, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(family, "LEGACY_ROOT", tmp_path / "legacy")
    monkeypatch.setattr(family, "REVERIFY_ROOT", tmp_path / "reverify")
    result = family.materialize(out)
    assert result["tasks"] == 40
    roots = sorted(path for path in out.iterdir() if path.is_dir() and path.name != ".state")
    assert len(roots) == 40
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert not set(config["files"]["solution"]) & set(config["files"]["test"])
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert provenance["lineage"] == "new-root"
        assert provenance["generator"] == family.OWNER
        assert "CORE_BEGIN" in (root / ".meta/example.cpp").read_text()
    selected = json.loads((out / ".state/selected-manifest.json").read_text())
    rejected = json.loads((out / ".state/rejected-proposals.json").read_text())
    source_inventory = json.loads((out / ".state/source-inventory.json").read_text())
    assert selected["requested_count"] == selected["retained_count"] == 40
    assert len(selected["tasks"]) == 40
    assert len(rejected["rejected"]) == 3
    assert source_inventory["comparison_root_count"] == (
        source_inventory["legacy_count"]
        + source_inventory["reverify_count"]
        + source_inventory["expansion_other_count"]
    )


def test_prompt_exposes_only_docs_and_editable_files(tmp_path: Path) -> None:
    case = family.TASKS[0]
    root = tmp_path / case.task_id
    for relative, content in family._task_files(case).items():
        family._write(root / relative, content)
    prompt = family.build_prompt(family.load_task(root))
    assert f"{case.task_id}.h" in prompt
    assert f"{case.task_id}.cpp" in prompt
    for private in ("CMakeLists.txt", "provenance.json", "example.cpp", "task_hidden_test", "negative_false"):
        assert private not in prompt


def test_pair_evaluator_has_independent_per_dimension_evidence(tmp_path: Path) -> None:
    roots = []
    for case in family.TASKS[:2]:
        root = tmp_path / case.task_id
        for relative, content in family._task_files(case).items():
            family._write(root / relative, content)
        roots.append(root)
    decision = family._pair_decision(*roots)
    assert set(decision["dimensions"]) == set(family.HARD_RULE_DIMENSIONS)
    assert decision["pass"]
    for evidence in decision["dimensions"].values():
        assert set(evidence) == {"overlap", "symmetric_difference", "distinct"}
        assert evidence["distinct"] is True


def test_cross_corpus_projection_has_all_seven_independent_scopes(tmp_path: Path) -> None:
    case = family.TASKS[0]
    root = tmp_path / case.task_id
    for relative, content in family._task_files(case).items():
        family._write(root / relative, content)
    scopes = family._external_feature_scopes(root)
    assert set(scopes) == set(family.HARD_RULE_DIMENSIONS)
    assert all(tokens for tokens in scopes.values())


def test_three_coherent_clone_classes_change_files_and_are_rejected(tmp_path: Path) -> None:
    for name in ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection"):
        kind = {"domain-identifier-renamed": "sum", "constants-policy-only": "rubric", "opposite-end-selection": "weighted"}[name]
        base_case = next(case for case in family.TASKS if case.kind == kind)
        base = tmp_path / base_case.task_id
        for relative, content in family._task_files(base_case).items():
            family._write(base / relative, content)
        control = family._render_control(tmp_path, name)
        assert family._tree_hash(control) != family._tree_hash(base)
        decision = family._pair_decision(base, control)
        assert decision["pass"] is False
        assert any(not row["distinct"] for row in decision["dimensions"].values())


def test_every_negative_source_is_nonempty_and_changes_core() -> None:
    for case in family.TASKS:
        good = family._core(case)
        bad = family._core(case, wrong=True)
        assert good.strip()
        assert bad.strip()
        assert good != bad


def _independent_tokens(root: Path, relative: str, *, core_only: bool = False) -> set[str]:
    text = (root / relative).read_text()
    if core_only and "// CORE_BEGIN" in text:
        text = text.split("// CORE_BEGIN", 1)[1].split("// CORE_END", 1)[0]
    if relative.endswith(".toml"):
        text = text.replace('"', "")
    text = re.sub(r"//.*?$|/\*.*?\*/|\"(?:\\.|[^\"])*\"", " ", text, flags=re.M | re.S)
    text = re.sub(r"\b\d+(?:ULL|UL|U|LL)?\b", " number ", text)
    tokens = set(re.findall(r"[a-z_][a-z0-9_]*|[+*/%<>=!-]+", text.lower()))
    stop = {
        "const", "auto", "return", "input", "std", "uint64_t", "uint32_t",
        "size_t", "optional", "vector", "public", "class", "struct",
    }
    parts = root.name.split("-")
    identities = {root.name, "".join(parts), "_".join(parts), *parts, "".join(parts) + "input"}
    return {token for token in tokens - identities - stop if len(token) > 1}


def _independent_scopes(root: Path) -> dict[str, set[str]]:
    header = next(root.glob("*.h")).name
    docs = _independent_tokens(root, ".docs/instructions.md")
    reference = _independent_tokens(root, ".meta/example.cpp", core_only=True)
    return {
        "public_api": _independent_tokens(root, header) | docs,
        "owned_state_or_algorithm": reference,
        "mutation_selection_rules": docs | reference,
        "invalid_boundary_behavior": docs | _independent_tokens(
            root, ".meta/task_hidden_test.cpp"
        ),
        "reference_control_flow": reference,
        "deterministic_oracle": set().union(*(
            _independent_tokens(root, relative)
            for relative in (
                "task_visible_test.cpp",
                ".meta/task_hidden_test.cpp",
                ".meta/tests.toml",
            )
        )),
        "topic_negative_fixture": _independent_tokens(
            root, ".meta/negative_false_substitute.cpp"
        ) | _independent_tokens(root, ".meta/tests.toml"),
    }


def test_all_780_pairs_have_independent_artifact_differences(tmp_path: Path) -> None:
    roots: list[Path] = []
    for case in family.TASKS:
        root = tmp_path / case.task_id
        for relative, content in family._task_files(case).items():
            family._write(root / relative, content)
        roots.append(root)
    production_records = [
        family._pair_decision(left, right) for left, right in combinations(roots, 2)
    ]
    screen_path = tmp_path / "persisted-family-screen.json"
    screen_path.write_text(json.dumps({"pairs": production_records}, sort_keys=True))
    persisted = json.loads(screen_path.read_text())["pairs"]
    assert len(persisted) == 780
    for record in persisted:
        left = next(root for root in roots if root.name == record["left"])
        right = next(root for root in roots if root.name == record["right"])
        left_scopes = _independent_scopes(left)
        right_scopes = _independent_scopes(right)
        independent_pass = True
        for dimension in family.HARD_RULE_DIMENSIONS:
            lt = left_scopes[dimension]
            rt = right_scopes[dimension]
            overlap = len(lt & rt) / max(1, len(lt | rt))
            symmetric = len(lt ^ rt)
            distinct = overlap < 0.98 and symmetric >= 2
            independent_pass &= distinct
            assert record["dimensions"][dimension] == {
                "overlap": round(overlap, 6),
                "symmetric_difference": symmetric,
                "distinct": distinct,
            }, (left.name, right.name, dimension)
        assert record["pass"] is independent_pass is True


def test_private_oracles_cover_identity_invalid_and_resource_boundaries(tmp_path: Path) -> None:
    for case in family.TASKS:
        hidden = family._test_source(case, hidden=True)
        assert "const auto invalid" in hidden
        assert "const auto edge" in hidden
        assert "return 4" in hidden
        if case.kind in family.VECTOR_FIELDS or case.kind in family.DP_GUARDS:
            assert "oversized" in hidden
            assert "return 5" in hidden


def test_cycle_two_counterexamples_are_bound_to_wrap_safe_guards() -> None:
    for kind in ("stirling", "lattice", "bounded_composition"):
        guard = family.DP_GUARDS[kind]
        assert "1000000/(" in guard
        assert "*" not in guard
    assert family.DP_GUARDS["geometric_series"] == "input.count>1000000"

    trimmed = next(case for case in family.TASKS if case.kind == "trimmed_mean")
    trimmed_core = family._core(trimmed)
    assert "(input.marks.size()-1)/2" in trimmed_core
    assert "2*input.trim_each_side" not in trimmed_core
    assert any(
        "9223372036854775808ULL" in literal
        for literal in family.ADDITIONAL_INVALID_CASES["trimmed_mean"]
    )

    tier = next(case for case in family.TASKS if case.kind == "tier")
    tier_core = family._core(tier)
    assert tier_core.index("width==0||rate==0") < tier_core.index("U left=input.usage")
    assert any("{0, 1}" in literal for literal in family.ADDITIONAL_INVALID_CASES["tier"])


def test_cycle_eight_counterexamples_and_missing_contract_branches_are_bound() -> None:
    box = next(case for case in family.TASKS if case.kind == "box_volume")
    assert "b.width==0||b.height==0||b.depth==0" in family._core(box)
    assert "18446744073709551615ULL" in family.ADDITIONAL_VALID_CASES["box_volume"][0][0]

    decay = next(case for case in family.TASKS if case.kind == "decay")
    assert "i+1<input.newest_first.size()" in family._core(decay)
    assert family.ADDITIONAL_INVALID_CASES["decay"] == ["{{1}, 1, 0}"]
    assert family.ADDITIONAL_VALID_CASES["decay"][0][1] == 0

    bounded = next(case for case in family.TASKS if case.kind == "bounded_composition")
    bounded_core = family._core(bounded)
    assert "window" in bounded_core
    assert "for(U x=0" not in bounded_core
    assert ("{499999, {499999}}", 1) in family.ADDITIONAL_VALID_CASES["bounded_composition"]
    assert "{500000, {500000}}" in family.ADDITIONAL_INVALID_CASES["bounded_composition"]

    required_invalid_kinds = {"binomial", "falling", "quorum", "trapezoid", "onto"}
    assert required_invalid_kinds <= family.ADDITIONAL_INVALID_CASES.keys()
    required_valid_kinds = {
        "arithmetic_series",
        "multiset",
        "derangement",
        "stirling",
    }
    assert required_valid_kinds <= family.ADDITIONAL_VALID_CASES.keys()


def test_cycle_twelve_zero_usage_empty_tier_identity_is_bound() -> None:
    tier = next(case for case in family.TASKS if case.kind == "tier")
    tier_core = family._core(tier)
    assert tier_core.index("width==0||rate==0") < tier_core.index("input.usage==0")
    assert "if(input.usage==0)return U{0}" in tier_core
    assert ("{0, {}}", 0) in family.ADDITIONAL_VALID_CASES["tier"]
    hidden = family._test_source(tier, hidden=True)
    assert "ProgressiveTierScoreInput{0, {}}" in hidden
    assert "*extra_7 != 0ULL" in hidden


def test_host_verify_root_passes_reference_and_rejects_negative(tmp_path: Path) -> None:
    import shutil

    if not all(shutil.which(tool) for tool in ("c++", "cmake", "ctest")):
        pytest.skip("host verify requires c++, cmake, and ctest")
    case = next(case for case in family.TASKS if case.kind == "binomial")
    root = tmp_path / case.task_id
    for relative, content in family._task_files(case).items():
        family._write(root / relative, content)
    records = family._host_verify_root(root, tmp_path / "work")
    assert [row["mode"] for row in records] == ["normal", "sanitizer"]
    for row in records:
        assert row["task_id"] == case.task_id
        assert row["test_count"] == 2
        assert row["tests_exit"] == 0
        assert row["negative_exit"] == 2
