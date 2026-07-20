from __future__ import annotations

import inspect
import json
import re
import shutil
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_word_wrap_text_justify_aider_tasks as tasks


def _independent_tokens(content: str) -> list[str]:
    content = re.sub(r"/\*.*?\*/|//[^\n]*", " ", content, flags=re.S)
    content = re.sub(
        r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", content
    )
    tokens = re.findall(
        r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]",
        content,
    )
    keywords = {
        "if", "else", "for", "while", "return", "class", "struct", "const",
        "auto", "bool", "int", "long", "void", "true", "false", "public",
        "private", "namespace", "std", "vector", "deque", "string", "size_t",
    }
    return [
        token if token in keywords or not re.match(r"[A-Za-z_]", token) else "ID"
        for token in tokens
    ]


def _independent_containment(left: str, right: str) -> float:
    def ngrams(content: str) -> set[tuple[str, ...]]:
        tokens = _independent_tokens(content)
        return {tuple(tokens[i:i + 8]) for i in range(max(0, len(tokens) - 7))}

    a, b = ngrams(left), ngrams(right)
    denominator = min(len(a), len(b))
    return len(a & b) / denominator if denominator else 1.0


def _independent_artifacts(root: Path) -> dict[str, str]:
    config = json.loads((root / ".meta/config.json").read_text())
    header = (root / config["files"]["solution"][0]).read_text()
    instructions = (root / ".docs/instructions.md").read_text()
    reference = (root / ".meta/example.cpp").read_text()
    visible = (root / "task_visible_test.cpp").read_text()
    hidden = (root / ".meta/task_hidden_test.cpp").read_text()
    negative = (root / ".meta/negative_false_substitute.cpp").read_text()
    return {
        "public_api": header,
        "owned_state_or_algorithm": header + "\n" + reference,
        "mutation_or_selection_rules": instructions + "\n" + reference,
        "invalid_and_boundary_behavior": instructions + "\n" + hidden,
        "reference_control_flow": reference,
        "deterministic_oracle": visible + "\n" + hidden,
        "topic_specific_negative_fixture": negative,
    }


def _prepared_out(tmp_path: Path) -> Path:
    out = tmp_path / "family"
    shutil.copytree(tasks.DEFAULT_OUT / ".state" / "remedy", out / ".state" / "remedy")
    return out


def test_materializes_twenty_mechanism_distinct_replacements(tmp_path: Path) -> None:
    out = _prepared_out(tmp_path)
    roots = tasks.build(out)
    assert len(roots) == 20
    assert len({case.profile for case in tasks.CASES}) == 20
    assert len({case.public_api for case in tasks.CASES}) == 20
    assert {root.name for root in roots} == {case.task_id for case in tasks.CASES}
    dispositions = {
        case.task_id: json.loads(
            (out / ".state" / "remedy" / f"{case.task_id}.json").read_text()
        )["disposition"]
        for case in tasks.CASES
    }
    assert list(dispositions.values()).count("repair-in-place") == 1
    assert list(dispositions.values()).count("replace") == 19
    for case, root in zip(tasks.CASES, roots, strict=True):
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [
            f"{case.task_id}.h", f"{case.task_id}.cpp"
        ]
        assert config["files"]["example"] == [
            ".meta/example.h", ".meta/example.cpp"
        ]
        assert provenance["family_id"] == tasks.FAMILY_ID
        assert provenance["legacy_task_id"] == case.legacy_id
        assert (root / ".meta/negative_false_substitute.cpp").is_file()


def test_core_verifier_checks_prompts_all_pairs_controls_and_holdouts(
    tmp_path: Path,
) -> None:
    out = _prepared_out(tmp_path)
    tasks.build(out)
    manifest = tasks.verify_core(out)
    assert manifest["task_count"] == 20
    screen = manifest["screen"]
    assert screen["prompt_boundary"] == "pass"
    assert screen["reference_mapping"] == "pass"
    hard_rule = screen["hard_rule"]
    assert hard_rule["pair_count"] == 20 * 19 // 2 == 190
    assert hard_rule["expected_pair_count"] == 190
    assert len(hard_rule["pairs"]) == 190
    assert hard_rule["status"] == "pass"
    assert tuple(hard_rule["dimension_set"]) == tasks.HARD_RULE_DIMENSIONS
    assert len(hard_rule["dimension_set"]) == 7
    assert set(screen["adversarial_controls"]) == {
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
    }
    assert screen["semantic_holdout"]["holdout_root_count"] == 26
    for pair in hard_rule["pairs"]:
        assert tuple(pair["dimension_set"]) == tasks.HARD_RULE_DIMENSIONS
        assert pair["all_dimensions_materially_distinct"] is True
        assert pair["decision"] == "pass"
        assert pair["failed_dimensions"] == []
        assert set(pair["dimensions"]) == set(tasks.HARD_RULE_DIMENSIONS)
        left = _independent_artifacts(out / pair["left"])
        right = _independent_artifacts(out / pair["right"])
        for dimension in tasks.HARD_RULE_DIMENSIONS:
            decision = pair["dimensions"][dimension]
            independent = _independent_containment(left[dimension], right[dimension])
            assert decision["materially_distinct"] is True
            assert independent == pytest.approx(decision["normalized_containment"], abs=1e-6)
            assert independent < decision["threshold_exclusive"]
            assert decision["left_token_count"] > 0
            assert decision["right_token_count"] > 0


def test_every_topic_negative_is_distinct_and_mutates_once(tmp_path: Path) -> None:
    out = _prepared_out(tmp_path)
    roots = tasks.build(out)
    assert set(tasks.NEGATIVE_MUTATIONS) == {case.task_id for case in tasks.CASES}
    hashes: set[str] = set()
    for case, root in zip(tasks.CASES, roots, strict=True):
        old, new, reason = tasks.NEGATIVE_MUTATIONS[case.task_id]
        assert case.reference.count(old) == 1
        negative = (root / ".meta/negative_false_substitute.cpp").read_text()
        assert old not in negative
        assert new in negative
        assert reason
        digest = tasks._sha(negative.encode())
        assert digest not in hashes
        hashes.add(digest)


def test_adversarial_controls_are_rejected(tmp_path: Path) -> None:
    out = _prepared_out(tmp_path)
    tasks.build(out)
    manifest = tasks.verify_core(out)
    controls = manifest["screen"]["adversarial_controls"]
    assert tuple(controls) == tasks.CONTROL_NAMES
    base = _independent_artifacts(out / tasks.CONTROL_BASE_TASK)
    for name, record in controls.items():
        root = out / record["root"]
        assert root.is_dir()
        assert record["changed_files"]
        assert record["intended_files_changed"] is True
        assert record["structurally_coherent"] is True
        assert record["docker_build_status"] == "not_completed"
        assert record["tree_hash"] != tasks._sha(b"")
        assert record["tree_hash"] == tasks._tree_hash(root)
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert all((root / relative).is_file() for relative in config["files"]["solution"])
        evaluation = record["production_evaluator"]
        assert evaluation["decision"] == "rejected:duplicate_family"
        assert evaluation["all_dimensions_materially_distinct"] is False
        assert evaluation["failed_dimensions"]
        control = _independent_artifacts(root)
        independently_failed = []
        for dimension in tasks.HARD_RULE_DIMENSIONS:
            score = _independent_containment(base[dimension], control[dimension])
            decision = evaluation["dimensions"][dimension]
            assert score == pytest.approx(decision["normalized_containment"], abs=1e-6)
            if score >= decision["threshold_exclusive"]:
                independently_failed.append(dimension)
        assert independently_failed == evaluation["failed_dimensions"]

    domain = out / controls["domain-identifier-renamed-clone"]["root"]
    assert (domain / "schedule-meeting-notes.h").is_file()
    assert "layout_meeting" in (domain / ".meta/example.cpp").read_text()
    assert "layout_agenda" not in (domain / ".meta/example.cpp").read_text()
    constants = out / controls["constants-policy-clone"]["root"]
    assert "Width is 4..79" in (constants / ".docs/instructions.md").read_text()
    assert "width>79U" in (constants / ".meta/example.cpp").read_text()
    assert "80).valid" in (constants / ".meta/task_hidden_test.cpp").read_text()
    opposite = out / controls["opposite-end-selection-clone"]["root"]
    assert "reverse input order" in (opposite / ".docs/instructions.md").read_text()
    assert ".rbegin()" in (opposite / ".meta/example.cpp").read_text()
    assert '"B two","A one"' in (opposite / "task_visible_test.cpp").read_text()


def test_references_make_strict_whole_file_answers(tmp_path: Path) -> None:
    out = _prepared_out(tmp_path)
    fence = chr(96) * 3
    for root in tasks.build(out):
        task = moonlight_aider_task_sft.load_task(root)
        answer = moonlight_aider_task_sft.build_assistant_response(
            task, moonlight_aider_task_sft.load_example_files_from_config(root)
        )
        assert answer.startswith(f"{root.name}.h\n{fence}")
        assert f"{root.name}.cpp\n{fence}" in answer
        assert ".meta/example" not in answer


def test_missing_remedy_fails_closed(tmp_path: Path) -> None:
    out = _prepared_out(tmp_path)
    (out / ".state" / "remedy" / "segment-flight-telex.json").unlink()
    with pytest.raises(RuntimeError, match="remedy_spec_incomplete"):
        tasks.build(out)


def test_docker_verifier_owns_snapshot_safe_contract() -> None:
    source = inspect.getsource(tasks.docker_sanity)
    runner = tasks.DOCKER_RUNNER
    assert '"--network", "none"' in source
    assert '"Unix Makefiles"' in runner
    assert "-fsanitize=address,undefined" in runner
    assert "grader_mount_hash_mismatch" in runner
    assert "negative_fixture_not_rejected" in runner
    assert 'kind=subject["kind"]' in runner
    assert '"control_count": len(CONTROL_NAMES)' in source
    assert "sanitizer_test_count_mismatch" in source


def test_wrapper_targets_parallel_reverify_tree() -> None:
    wrapper = Path(
        "examples/slime/moonlight_cpp_perf/"
        "prepare_text_justification_aider_tasks.sh"
    )
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_word_wrap_text_justify_aider_tasks" in content
    assert (
        "aider-tasks-reverify/aider-text-grid-reshaping/text-justification"
        in content
    )
