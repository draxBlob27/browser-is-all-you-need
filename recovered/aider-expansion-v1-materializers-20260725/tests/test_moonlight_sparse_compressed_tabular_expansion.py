from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_sparse_compressed_tabular_expansion as family


EXPECTED_CASE_COVERAGE = {
    "succinct-bit-rank-directory": frozenset(
        {"normal", "empty", "invalid", "absent_tie", "overflow_tail", "malformed", "boundary"}
    ),
    "frame-reference-integer-blocks": frozenset(
        {"normal", "empty", "invalid", "duplicate_order", "overflow_tail", "malformed", "boundary"}
    ),
    "zigzag-varint-ledger": frozenset(
        {"normal", "empty", "invalid", "overflow_tail", "malformed", "boundary"}
    ),
    "bounded-bitwidth-column": frozenset(
        {"normal", "empty", "invalid", "overflow_tail", "malformed", "boundary"}
    ),
    "run-end-status-column": frozenset(
        {"normal", "empty", "invalid", "duplicate_order", "malformed", "boundary"}
    ),
    "nullable-dictionary-column": frozenset(
        {"normal", "empty", "invalid", "duplicate_order", "absent_tie", "malformed", "boundary"}
    ),
    "front-coded-path-lexicon": frozenset(
        {
            "normal",
            "empty",
            "invalid",
            "duplicate_order",
            "overflow_tail",
            "malformed",
            "boundary",
        }
    ),
    "jagged-offset-table": frozenset(
        {
            "normal",
            "empty",
            "invalid",
            "duplicate_order",
            "overflow_tail",
            "malformed",
            "boundary",
        }
    ),
    "row-dictionary-fact-table": frozenset(
        {"normal", "empty", "invalid", "duplicate_order", "malformed", "boundary"}
    ),
    "nullable-columnar-record-batch": frozenset(
        {"normal", "empty", "invalid", "duplicate_order", "absent_tie", "malformed", "boundary"}
    ),
    "schema-permutation-table": frozenset(
        {"normal", "empty", "invalid", "duplicate_order", "malformed", "boundary"}
    ),
    "table-cell-delta-patch": frozenset(
        {
            "normal",
            "empty",
            "invalid",
            "duplicate_order",
            "absent_tie",
            "overflow_tail",
            "malformed",
            "boundary",
        }
    ),
    "full-outer-merge-table": frozenset(
        {"normal", "empty", "invalid", "duplicate_order", "absent_tie", "malformed", "boundary"}
    ),
    "asof-snapshot-join": frozenset(
        {"normal", "empty", "invalid", "duplicate_order", "absent_tie", "malformed", "boundary"}
    ),
    "sparse-polynomial-canonicalizer": frozenset(
        {
            "normal",
            "empty",
            "invalid",
            "duplicate_order",
            "absent_tie",
            "overflow_tail",
            "malformed",
            "boundary",
        }
    ),
    "adjacency-gap-catalog": frozenset(
        {"normal", "empty", "invalid", "duplicate_order", "absent_tie", "malformed", "boundary"}
    ),
    "posting-skip-directory": frozenset(
        {
            "normal",
            "empty",
            "invalid",
            "duplicate_order",
            "absent_tie",
            "overflow_tail",
            "malformed",
            "boundary",
        }
    ),
    "quotient-remainder-membership": frozenset(
        {"normal", "empty", "invalid", "duplicate_order", "absent_tie", "malformed", "boundary"}
    ),
    "block-coordinate-sparse-tensor": frozenset(
        {
            "normal",
            "empty",
            "invalid",
            "duplicate_order",
            "absent_tie",
            "overflow_tail",
            "malformed",
            "boundary",
        }
    ),
    "symmetric-triangle-packer": frozenset(
        {"normal", "invalid", "duplicate_order", "malformed", "boundary"}
    ),
    "binary-quadtree-leaf-stream": frozenset(
        {"normal", "invalid", "overflow_tail", "malformed", "boundary"}
    ),
    "boolean-interval-mask": frozenset(
        {
            "normal",
            "empty",
            "invalid",
            "duplicate_order",
            "absent_tie",
            "overflow_tail",
            "malformed",
            "boundary",
        }
    ),
    "last-write-sparse-overlay": frozenset(
        {
            "normal",
            "empty",
            "invalid",
            "duplicate_order",
            "absent_tie",
            "overflow_tail",
            "malformed",
            "boundary",
        }
    ),
    "sparse-histogram-gap-stream": frozenset(
        {
            "normal",
            "empty",
            "invalid",
            "duplicate_order",
            "absent_tie",
            "overflow_tail",
            "malformed",
            "boundary",
        }
    ),
    "byte-column-bitplanes": frozenset(
        {"normal", "empty", "invalid", "overflow_tail", "malformed", "boundary"}
    ),
}


def _executed_contract_markers(source: str, function_name: str) -> dict[str, str]:
    markers: dict[str, str] = {}
    blocks = re.split(r"// contract-case: ([a-z_]+)\s*", source)
    assert len(blocks) % 2 == 1
    for category, body in zip(blocks[1::2], blocks[2::2]):
        assert f"{function_name}(" in body, category
        assert "if" in body and "return" in body, category
        calls = re.findall(rf"{re.escape(function_name)}\(([^)]+)\)", body)
        assert calls, category
        if category != "normal":
            assert any(category in argument for argument in calls), category
        assert category not in markers
        markers[category] = body
    return markers


def _sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    expansion = tmp_path / "aider-tasks-expansion-v1"
    monkeypatch.setattr(family, "EXPANSION_ROOT", expansion)
    monkeypatch.setattr(
        family, "DEFAULT_OUT", expansion / "text-grid-logic/sparse-compressed-tabular"
    )
    monkeypatch.setattr(family, "LEGACY_ROOTS", (tmp_path / "legacy", tmp_path / "reverify"))
    monkeypatch.setattr(family, "HOLDOUT_ROOT", tmp_path / "holdouts")
    return family.DEFAULT_OUT


def test_exact_25_new_roots_and_safe_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    manifest = family.materialize(out)
    roots = [path for path in out.iterdir() if path.is_dir() and path.name != ".state"]
    assert manifest["task_count"] == len(roots) == 25
    assert len(manifest["task_ids"]) == len(set(manifest["task_ids"])) == 25
    assert all(root.parent == out for root in roots)
    with pytest.raises(family.CreatorError, match="unsafe_path"):
        family._safe_out(tmp_path / "legacy/family")


def test_inventory_refresh_does_not_rewrite_task_bytes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    family.materialize(out)
    before = family._tree_hash(out)
    payload = family.refresh_inventory(out)
    assert payload["schema_version"] == "sparse-compressed-tabular-inventory-v1"
    assert family._tree_hash(out) == before


def test_roles_references_prompts_and_negatives(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    family.materialize(out)
    for index, case in enumerate(family.CASES):
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["lineage"] == "new-root"
        assert provenance["primary_core_objective"] == "achieved"
        assert case.mechanism in (root / ".docs/instructions.md").read_text()
        assert family._source(case, index) != family._source(case, index, negative=True)
        reference = (root / ".meta/example.cpp").read_text()
        restored_field = family._api(index)[5]
        assert f"out.{restored_field}=values" not in reference.replace(" ", "")
        assert family.RULES[index] in (root / ".docs/instructions.md").read_text()
        assert family.BOUNDARY_EXAMPLES[index] in (root / ".docs/instructions.md").read_text()
        prompt = family.build_prompt(family.load_task(root))
        assert not any(
            marker in prompt
            for marker in (".meta/", "CMakeLists", "private_test", "negative_false")
        )


def test_public_contract_matrix_is_published_and_every_applicable_case_executes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    family.materialize(out)
    task_ids = {case.task_id for case in family.CASES}
    assert set(EXPECTED_CASE_COVERAGE) == task_ids
    assert set(family.CASE_COVERAGE) == task_ids
    assert set(family.BEHAVIOR_CASES) == task_ids
    for case in family.CASES:
        root = out / case.task_id
        expected = EXPECTED_CASE_COVERAGE[case.task_id]
        coverage = frozenset(family.CASE_COVERAGE[case.task_id])
        behaviors = family.BEHAVIOR_CASES[case.task_id]
        assert coverage == expected
        assert set(behaviors) == expected
        assert all(isinstance(detail, str) and detail.strip() for detail in behaviors.values())
        normalized_details = {
            detail.replace(category, "<category>") for category, detail in behaviors.items()
        }
        assert len(normalized_details) == len(expected), case.task_id

        instructions = (root / ".docs/instructions.md").read_text()
        visible = (root / "visible_test.cpp").read_text()
        private = (root / ".meta/private_test.cpp").read_text()
        for category, detail in behaviors.items():
            assert f"`{category}`" in instructions
            assert detail in instructions

        visible_markers = _executed_contract_markers(visible, case.snake)
        private_markers = _executed_contract_markers(private, case.snake)
        assert set(visible_markers) == {"normal"}
        assert set(private_markers) == expected - {"normal"}
        assert set(visible_markers) | set(private_markers) == expected
        assert len(private_markers) > 1, case.task_id
        normalized_bodies = {
            re.sub(r"\d+", "<n>", re.sub(r"\s+", "", body)).replace(category, "<case>")
            for category, body in (visible_markers | private_markers).items()
        }
        assert len(normalized_bodies) == len(expected), case.task_id


def test_all_300_pairs_have_independent_seven_dimension_witnesses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    family.materialize(out)
    pairs: set[tuple[str, str]] = set()
    roots = [out / case.task_id for case in family.CASES]
    for index, left in enumerate(roots):
        left_material = family._dimension_material(left)
        assert set(left_material) == set(family.DIMENSIONS)
        assert all(left_material[dimension] for dimension in family.DIMENSIONS)
        for right in roots[index + 1 :]:
            decisions, similarities = family._pair_decisions(left, right)
            assert all(decisions.values()), (left.name, right.name, decisions)
            assert all(similarities[dimension] < 0.90 for dimension in family.DIMENSIONS)
            pairs.add((left.name, right.name))
    assert len(pairs) == 25 * 24 // 2 == 300


def test_materialized_clone_controls_change_compile_inputs_and_are_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    family.materialize(out)
    base = out / family.CASES[4].task_id
    controls = out / ".state/adversarial-clone-controls"
    expected = {"domain-identifier-renamed", "constants-policy-only", "opposite-end-selection"}
    assert {path.name for path in controls.iterdir()} == expected
    for name in expected:
        control = controls / name
        changed = {
            path.relative_to(control).as_posix()
            for path in control.rglob("*")
            if path.is_file()
            and (
                not (base / path.relative_to(control)).is_file()
                or path.read_bytes() != (base / path.relative_to(control)).read_bytes()
            )
        }
        assert changed
        assert (control / "CMakeLists.txt").is_file()
        assert (control / ".meta/example.cpp").is_file()
        assert (control / ".meta/private_test.cpp").is_file()
        assert any(
            relative in changed
            for relative in (
                ".meta/example.cpp",
                ".meta/private_test.cpp",
                f"{family.CASES[4].task_id}.h",
            )
        )
    screen = family.diversity_screen(out)
    assert screen["pair_count"] == 300
    for record in screen["controls"].values():
        assert record["changed_files_nonempty"] is True
        assert record["production_rejected"] is True
        assert set(record["decisions"]) == set(family.DIMENSIONS)
        assert not all(record["decisions"].values())
        assert record["similarities"]


def test_topic_negatives_and_task_specific_apis_are_not_family_templates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    family.materialize(out)
    negative_hashes = set()
    headers = set()
    for index, case in enumerate(family.CASES):
        root = out / case.task_id
        negative = (root / ".meta/negative_false_substitute.cpp").read_text()
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert provenance["negative_fixture"] == case.false_substitute
        assert negative == family._negative_source(case, index)
        assert "Historical post-mutation" not in negative
        assert not hasattr(family, "_negative_mutation")
        assert "std::reverse(out." + family._api(index)[5] not in negative
        negative_hashes.add(family._sha(negative.encode()))
        header = (root / f"{case.task_id}.h").read_text()
        for field in family._api(index):
            assert field in header or field in {family._api(index)[1], family._api(index)[2]}
        headers.add(family._sha(header.encode()))
    assert len(negative_hashes) == len(headers) == 25


def test_all_results_have_independent_malformed_validators_and_negative_tests(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    family.materialize(out)
    assert all("malformed" in coverage for coverage in family.CASE_COVERAGE.values())
    assert len({family._malformed_result_mutation(index) for index in range(25)}) == 25
    for index, case in enumerate(family.CASES):
        root = out / case.task_id
        validator = family._validator_name(case)
        header = (root / f"{case.task_id}.h").read_text()
        reference = (root / ".meta/example.cpp").read_text()
        private = (root / ".meta/private_test.cpp").read_text()
        negative_test = (root / ".meta/negative_test.cpp").read_text()
        cmake = (root / "CMakeLists.txt").read_text()
        instructions = (root / ".docs/instructions.md").read_text()
        assert f"bool {validator}(const " in header
        assert f"bool {validator}(const " in reference
        validator_source = reference.split(f"bool {validator}", maxsplit=1)[1]
        assert f"{case.snake}(request" not in validator_source
        assert "// contract-case: malformed" in private
        malformed = private.split("// contract-case: malformed", maxsplit=1)[1]
        assert family._malformed_result_mutation(index) in malformed
        assert malformed.count(f"{validator}(") >= 2
        assert validator not in negative_test
        assert ".meta/negative_test.cpp" in cmake
        assert (
            ".meta/private_test.cpp)"
            not in cmake.split("add_executable(negative", maxsplit=1)[1].splitlines()[0]
        )
        assert cmake.count("add_test(") == 2
        assert f"`{validator}(request, encoded)`" in instructions


def test_audit_03_core_representation_contracts_are_explicit() -> None:
    rank_source = family._source(family.CASES[0], 0)
    assert "i+1==values.size()" in rank_source
    assert "completed=query/static_cast<std::size_t>(width)" in rank_source
    assert "out.rank_checkpoints[completed-1U]" in rank_source
    assert "out.packed_words[i/30U]" in rank_source
    assert "accumulate(out.decoded_bits" not in rank_source

    membership_header = family._header(family.CASES[17], 17)
    membership_source = family._source(family.CASES[17], 17)
    membership_test = family._test(family.CASES[17], 17, private=True)
    assert "int query_member=0" in membership_header
    assert "bool contains_member=false" in membership_header
    assert "out.contains_member=std::binary_search" in membership_source
    assert "request.query_member=6" in membership_test
    assert "result.contains_member" in membership_test

    tensor_source = family._source(family.CASES[18], 18)
    assert "std::numeric_limits<long long>::max()" in tensor_source
    assert "if(!checked_product(cells,extent))" in tensor_source
    assert "if(!checked_product(block_volume,extent))" in tensor_source

    for index in (8, 11, 12, 13, 19):
        source = family._source(family.CASES[index], index)
        prelude = source.split(family._algorithm_body(index).split(";")[0], maxsplit=1)[0]
        assert "for(int value:values)if(value<0)" not in prelude

    polynomial_source = family._source(family.CASES[14], 14)
    adjacency_source = family._source(family.CASES[15], 15)
    adjacency_test = family._test(family.CASES[15], 15, private=True)
    assert "if(width!=2" in polynomial_source
    assert "std::set<std::pair<int,int>> edges" in adjacency_source
    assert "edges.insert(edge)" in adjacency_source
    assert "edge_pairs.insert" in adjacency_test


def test_audit_04_normative_boundary_and_absent_cells_are_executable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    family.materialize(out)
    boundary_fragments = {
        "succinct-bit-rank-directory": "bits={1,0,1}",
        "frame-reference-integer-blocks": "integers={8,9,20}",
        "zigzag-varint-ledger": "signed_entries={-1,0,64}",
        "bounded-bitwidth-column": "column_values={7}",
        "run-end-status-column": "statuses={4,4,7}",
        "nullable-dictionary-column": "nullable_values={-1,4,2,4}",
        "front-coded-path-lexicon": 'ordered_paths={"ant","ante","anthem"}',
        "jagged-offset-table": "rows={{1,2},{},{3}}",
        "row-dictionary-fact-table": "flat_rows={2,1,2,1,1,9}",
        "nullable-columnar-record-batch": "values={10,99,30}",
        "schema-permutation-table": 'source_schema={"b","a"}',
        "table-cell-delta-patch": "old_and_new_cells={1,2,1,5}",
        "full-outer-merge-table": "left_and_right_keys={1,4,2,4}",
        "asof-snapshot-join": "snapshots_and_events={5,9,4,5,10}",
        "sparse-polynomial-canonicalizer": "term_pairs={0,2,0,-2,3,4}",
        "adjacency-gap-catalog": "edge_pairs={0,2,0,1}",
        "posting-skip-directory": "posting_ids={2,5,9,14}",
        "quotient-remainder-membership": "members={1,7}",
        "block-coordinate-sparse-tensor": "dense_cells={0,5,0,0,0,0,0,7}",
        "symmetric-triangle-packer": "square_matrix={1,2,2,3}",
        "binary-quadtree-leaf-stream": "binary_raster={1,1,1,1}",
        "boolean-interval-mask": "mask_bits={1,1,0,1}",
        "last-write-sparse-overlay": "update_triples={2,1,5,2,3,0,1,2,7}",
        "sparse-histogram-gap-stream": "bin_counts={0,4,0,0}",
        "byte-column-bitplanes": "byte_values={0,1}",
    }
    absent_fragments = {
        "table-cell-delta-patch": "old_and_new_cells={1,2,1,2}",
        "full-outer-merge-table": "left_and_right_keys={1,4,2,4}",
        "asof-snapshot-join": "snapshots_and_events={5,9,4,5,10}",
        "sparse-polynomial-canonicalizer": "term_pairs={0,2,0,-2}",
        "posting-skip-directory": "query_id=8",
        "sparse-histogram-gap-stream": "bin_counts={0,4,0,0}",
    }
    for case in family.CASES:
        private = (out / case.task_id / ".meta/private_test.cpp").read_text()
        markers = _executed_contract_markers(private, case.snake)
        assert boundary_fragments[case.task_id] in markers["boundary"]
        if case.task_id in absent_fragments:
            assert absent_fragments[case.task_id] in markers["absent_tie"]
            assert "validate_" in markers["absent_tie"]


def test_oracle_vectors_match_generated_reference_contract() -> None:
    assert len(family.CASES) == 25
    seen: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    for index, case in enumerate(family.CASES):
        data, aux = family._oracle(case, index)
        assert data or aux, case.task_id
        signature = (tuple(data), tuple(aux))
        assert signature not in seen, case.task_id
        seen.add(signature)
        visible = family._test(case, index, private=False)
        private = family._test(case, index, private=True)
        assert f"result.{family._api(index)[5]}!=" in visible
        assert "rejected.valid" in private


def test_docker_verifier_is_network_disabled_fresh_and_digest_bound() -> None:
    source = inspect.getsource(family.verify_docker)
    assert '"--network"' in source
    assert '"none"' in source
    assert "Unix Makefiles" in inspect.getsource(family)
    assert "-fsanitize=address,undefined" in inspect.getsource(family)
    assert "grader_mount_hash_mismatch" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "compiler.sha256" in source
    assert "negative_fixture_count" in source
    assert "reuse_verified_core" in source
    guard = inspect.getsource(family._require_verified_core_snapshot)
    assert "verified_core_snapshot_stale" in guard
    assert "frozen_inventory_verified_current" in guard
    assert "expected_extracted_tree_hash" in source
    assert "reconciled_extracted_tree_hash" in source
    assert "curriculum_hash" in source and "family_spec_hash" in source
    assert "focused_test_hash" in source and "task_results" in source


def test_cross_tree_screen_includes_all_expansion_artifacts() -> None:
    source = inspect.getsource(family._cross_tree_screen)
    assert "EXPANSION_ROOT" in source
    assert 'rglob("*")' in source
    assert "config_hash" in source


def test_curriculum_and_spec_bind_count_nonclaims_and_audit_loop() -> None:
    curriculum = family.CURRICULUM.read_text()
    specification = family.FAMILY_SPEC.read_text()
    assert "exactly 25" in curriculum
    assert "all 300" in curriculum
    assert ".w8-biayn/data/aider-tasks-expansion-v1/" in curriculum
    assert "read-only independent audit" in curriculum
    assert "local_family_verified" in curriculum
    assert "300 unordered" in specification
    assert "not_requested" in specification
    assert "no JSONL" in specification
    assert "Per-root public behavior and boundary matrix" in specification
    assert "Per-root executable coverage" in curriculum
    for task_id, coverage in EXPECTED_CASE_COVERAGE.items():
        row = f"| `{task_id}` |"
        assert row in specification
        assert row in curriculum
        assert coverage
    for category in {
        "normal",
        "empty",
        "invalid",
        "duplicate_order",
        "absent_tie",
        "overflow_tail",
        "malformed",
        "boundary",
    }:
        assert f"`{category}`" in specification
        assert f"`{category}`" in curriculum


def test_docs_follow_benchmark_register(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = _sandbox(monkeypatch, tmp_path)
    family.materialize(out)
    banned = re.compile(
        r"clean-room|\bthis task\b|\bSFT\b|benchmark|campaign|remediation|oracle"
        r"|negative fixture|reference implementation|generator|adversarial"
        r"|hard rule|forbidden substitute|do not substitute|grader|hidden test"
        r"|local_family_verified|prompt|\bmodel\b|task-specific",
        re.IGNORECASE,
    )
    for index, case in enumerate(family.CASES):
        root = out / case.task_id
        instructions = (root / ".docs/instructions.md").read_text()
        introduction = (root / ".docs/introduction.md").read_text()
        assert instructions.startswith("# Instructions\n")
        assert "## Example\n" in instructions
        assert "The owned mechanism is" not in instructions
        assert "must derive" not in instructions
        assert family.RULES[index] in instructions
        assert family.BOUNDARY_EXAMPLES[index] in instructions
        assert f"`{case.snake}`" in instructions and f"`{case.task_id}.h`" in instructions
        assert introduction.startswith(f"# {case.title}\n\n")
        assert len(introduction.split()) >= 40
        assert not banned.search(instructions)
        assert not banned.search(introduction)
