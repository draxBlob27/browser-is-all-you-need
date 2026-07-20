from __future__ import annotations

import difflib
import inspect
import json
import re
from pathlib import Path

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_elapsed_time_accumulation_aider_tasks as elapsed


def _independent_normalize(content: str) -> tuple[str, ...]:
    content = re.sub(r"/\*.*?\*/|//[^\n]*", " ", content, flags=re.S)
    content = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", content)
    raw = re.findall(
        r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]",
        content,
    )
    keywords = {
        "if", "else", "for", "while", "return", "class", "struct", "const",
        "auto", "bool", "int", "long", "void", "true", "false", "public",
        "private", "namespace", "std", "vector", "array", "map", "set", "sort",
    }
    return tuple(
        "CMP"
        if token in {"<", ">", "<=", ">="}
        else token
        if token in keywords or not re.match(r"[A-Za-z_]", token)
        else "ID"
        for token in raw
    )


def _independent_matching_lines(content: str, patterns: tuple[str, ...]) -> str:
    return "\n".join(
        line for line in content.splitlines() if any(re.search(pattern, line) for pattern in patterns)
    )


def _independent_artifact_dimensions(root: Path) -> dict[str, tuple[str, ...]]:
    config_path = root / ".meta/config.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text())
        header = (root / config["files"]["solution"][0]).read_text()
        reference = (root / config["files"]["example"][1]).read_text()
    else:
        header = (root / "task.h").read_text()
        reference = (root / "candidate.cpp").read_text()
    docs = (root / ".docs/instructions.md").read_text()
    visible = (root / "task_visible_test.cpp").read_text()
    hidden = (root / ".meta/task_hidden_test.cpp").read_text()
    negative = (root / ".meta/negative_false_substitute.cpp").read_text()
    state_lines = _independent_matching_lines(
        reference,
        (
            r"\bstruct\b", r"std::(?:map|set|vector|array)", r"\b(?:Report|State)\b",
            r"\b(?:remaining|frontier|latest|ordered|merged|minutes_by|state_by|uncapped)\w*\b",
        ),
    )
    mutation_lines = _independent_matching_lines(
        reference,
        (r"\b(?:if|else|for|sort|stable_sort|find|insert|emplace)\b", r"(?:\+=|-=|\+\+|=)"),
    )
    control_lines = _independent_matching_lines(
        reference,
        (r"\b(?:if|else|for|while|return|continue)\b",),
    )
    negative_diff = "\n".join(
        difflib.unified_diff(
            reference.splitlines(), negative.splitlines(), lineterm="", n=1
        )
    )
    material = {
        "public_api": header,
        "owned_state_algorithm": state_lines,
        "mutation_selection_rules": docs + "\n" + mutation_lines,
        "invalid_boundary_behavior": docs + "\n" + hidden,
        "reference_control_flow": control_lines,
        "deterministic_oracle": visible + "\n" + hidden,
        "topic_negative_fixture": negative_diff,
    }
    assert set(material) == set(elapsed.HARD_RULE_DIMENSIONS)
    assert all(value.strip() for value in material.values())
    return {name: _independent_normalize(value) for name, value in material.items()}


def test_materializes_eight_distinct_replacements_and_two_rejections(tmp_path: Path) -> None:
    roots = elapsed.build(tmp_path)
    assert len(roots) == 8
    assert elapsed.HARD_RULE_MIN == 8
    assert elapsed.HARD_RULE_MAX == 12
    assert len({case.mechanism for case in elapsed.CASES}) == 8
    assert len({case.public_api for case in elapsed.CASES}) == 8
    assert set(elapsed.REJECTED_LEGACY) == {
        "elapsed-battery-test-log",
        "elapsed-lab-equipment-booking",
    }
    assert {root.name for root in roots} == {case.task_id for case in elapsed.CASES}
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["family_id"] == elapsed.FAMILY_ID
        assert provenance["semantic_mechanism"]
        assert (root / ".meta/negative_false_substitute.cpp").is_file()


def test_remedies_account_for_all_legacy_roots_before_verification(tmp_path: Path) -> None:
    elapsed.build(tmp_path)
    remedy = tmp_path / ".state/remedy"
    records = {path.stem: json.loads(path.read_text()) for path in remedy.glob("*.json")}
    assert len(records) == 10
    assert records["elapsed-battery-test-log"]["disposition"] == "reject"
    assert records["elapsed-battery-test-log"]["status"] == "rejected"
    assert records["elapsed-lab-equipment-booking"]["disposition"] == "reject"
    for case in elapsed.CASES:
        assert records[case.legacy_id]["task_id"] == case.task_id
        assert records[case.legacy_id]["legacy_task_id"] == case.legacy_id
        assert records[case.legacy_id]["disposition"] == "replace"
        assert records[case.legacy_id]["family_id_after"].endswith(case.task_id)
        assert records[case.legacy_id]["tree_hash_before"] != "not_available"
        spec = (remedy / f"{case.legacy_id}.md").read_text()
        positions = [spec.index(f"## {heading}") for heading in elapsed.REMEDY_HEADINGS]
        assert positions == sorted(positions)


def test_core_verifier_inspects_exact_seven_dimensions_and_all_pairs(tmp_path: Path) -> None:
    elapsed.build(tmp_path)
    elapsed.verify_core(tmp_path)
    manifest = json.loads((tmp_path / ".state/materialization-manifest.json").read_text())
    hard_rule = manifest["screen"]["hard_rule"]
    assert manifest["task_count"] == 8
    assert manifest["rejected_legacy_count"] == 2
    assert hard_rule["root_count"] == 8
    assert hard_rule["count_bounds"] == [8, 12]
    assert hard_rule["pair_count"] == 28
    assert hard_rule["expected_pair_count"] == 28
    assert hard_rule["dimensions"] == list(elapsed.HARD_RULE_DIMENSIONS)
    assert len(hard_rule["pairs"]) == 28
    for pair in hard_rule["pairs"]:
        assert pair["pass"] is True
        assert set(pair["dimensions"]) == set(elapsed.HARD_RULE_DIMENSIONS)
        assert all(pair["dimensions"].values())
    roots = sorted((tmp_path / case.task_id for case in elapsed.CASES), key=lambda path: path.name)
    independent = {root.name: _independent_artifact_dimensions(root) for root in roots}
    independent_pairs = 0
    manifest_pairs = {(row["left"], row["right"]): row for row in hard_rule["pairs"]}
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            decisions = {
                dimension: independent[left.name][dimension] != independent[right.name][dimension]
                for dimension in elapsed.HARD_RULE_DIMENSIONS
            }
            assert all(decisions.values()), (left.name, right.name, decisions)
            assert manifest_pairs[(left.name, right.name)]["dimensions"] == decisions
            independent_pairs += 1
    assert independent_pairs == 28
    assert manifest["screen"]["prompt_boundary"] == "pass"
    assert manifest["screen"]["reference_mapping"] == "pass"
    assert manifest["screen"]["semantic_holdout"]["holdout_root_count"] == 26
    assert manifest["screen"]["semantic_holdout"]["comparison_count"] == 208


def test_production_evaluator_rejects_coherent_adversarial_controls(tmp_path: Path) -> None:
    elapsed.build(tmp_path)
    outcomes = elapsed._run_adversarial_controls(tmp_path)
    assert set(outcomes) == {
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
    }
    controls = elapsed._control_cases()
    controls_manifest = json.loads(
        (tmp_path / ".state/hard-rule-controls/manifest.json").read_text()
    )["controls"]
    assert "ProjectInvoice" in controls["domain-identifier-renamed-clone"].header
    assert "summarize(entries, 12)" in controls["constants-policy-clone"].visible_test
    assert "attempt.sequence < found->second.sequence" in controls[
        "opposite-end-selection-clone"
    ].reference
    for name, outcome in outcomes.items():
        assert outcome["changed"] is True
        assert outcome["changed_files"]
        assert outcome["production_evaluator"] == "rejected:duplicate_family"
        assert not all(outcome["per_dimension_distinct"].values()), name
        control_root = tmp_path / ".state/hard-rule-controls" / name
        assert (control_root / "candidate.cpp").is_file()
        assert (control_root / "task.h").is_file()
        base_root = tmp_path / controls_manifest[name]["base_task_id"]
        base_config = json.loads((base_root / ".meta/config.json").read_text())
        base_paths = {
            ".docs/instructions.md": base_root / ".docs/instructions.md",
            "task.h": base_root / base_config["files"]["solution"][0],
            "candidate.cpp": base_root / base_config["files"]["example"][1],
            ".meta/negative_false_substitute.cpp": base_root
            / ".meta/negative_false_substitute.cpp",
            "task_visible_test.cpp": base_root / "task_visible_test.cpp",
            ".meta/task_hidden_test.cpp": base_root / ".meta/task_hidden_test.cpp",
            "CMakeLists.txt": base_root / "CMakeLists.txt",
        }
        independently_changed = sorted(
            relative
            for relative, base_path in base_paths.items()
            if (control_root / relative).read_bytes() != base_path.read_bytes()
        )
        assert independently_changed == controls_manifest[name]["changed_files"]
        independent_base = _independent_artifact_dimensions(base_root)
        independent_control = _independent_artifact_dimensions(control_root)
        independent_decisions = {
            dimension: independent_base[dimension] != independent_control[dimension]
            for dimension in elapsed.HARD_RULE_DIMENSIONS
        }
        assert independent_decisions == outcome["per_dimension_distinct"]
        assert not all(independent_decisions.values())


def test_every_topic_negative_changes_reference_and_is_unique(tmp_path: Path) -> None:
    roots = elapsed.build(tmp_path)
    hashes = set()
    for case, root in zip(elapsed.CASES, roots, strict=True):
        negative = elapsed._negative_source(case)
        assert negative != case.reference
        assert case.negative_old not in negative
        assert case.negative_new in negative
        emitted = (root / ".meta/negative_false_substitute.cpp").read_text()
        assert emitted == negative.replace("task.h", f"{case.task_id}.h")
        digest = elapsed._sha_bytes(" ".join(elapsed._normalized_tokens(emitted)).encode())
        assert digest not in hashes
        hashes.add(digest)
    assert len(hashes) == 8


def test_references_make_strict_whole_file_answers(tmp_path: Path) -> None:
    fence = chr(96) * 3
    for root in elapsed.build(tmp_path):
        task = moonlight_aider_task_sft.load_task(root)
        answer = moonlight_aider_task_sft.build_assistant_response(
            task,
            moonlight_aider_task_sft.load_example_files_from_config(root),
        )
        assert answer.startswith(f"{root.name}.h\n{fence}")
        assert f"{root.name}.cpp\n{fence}" in answer
        assert ".meta/example" not in answer


def test_docker_verifier_is_snapshot_safe_and_network_disabled() -> None:
    source = inspect.getsource(elapsed.verify_docker)
    assert '"--network", "none"' in source
    assert '"Unix Makefiles"' in source
    assert "-fsanitize=address,undefined" in source
    assert "grader_mount_hash_mismatch" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "topic-negative.tsv" in source
    assert "controls.tsv" in source
    assert "negative_fixture_not_rejected" in source


def test_owner_invalidates_and_archives_prior_verified_receipt(tmp_path: Path) -> None:
    state = tmp_path / ".state"
    state.mkdir(parents=True)
    (state / "oracle-receipt.json").write_text('{"prior": true}\n')
    (state / "materialization-manifest.json").write_text(
        json.dumps({"status": "local_family_verified"}) + "\n"
    )
    elapsed.build(tmp_path)
    assert not (state / "oracle-receipt.json").exists()
    manifest = json.loads((state / "materialization-manifest.json").read_text())
    assert manifest["status"] == "planned"
    invalidations = list((state / "invalidated").glob("*/invalidation.json"))
    assert len(invalidations) == 1
    invalidation = json.loads(invalidations[0].read_text())
    assert invalidation["prior_status"] == "local_family_verified"
    assert "case-table metadata" in invalidation["reason"]


def test_wrapper_targets_parallel_reverify_tree() -> None:
    wrapper = Path(elapsed.WRAPPER_PATH)
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_elapsed_time_accumulation_aider_tasks" in content
    assert "aider-tasks-reverify/aider-text-grid-reshaping/elapsed-time-accumulation" in content
