from __future__ import annotations

import inspect
import json
from pathlib import Path

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_future_date_aider_tasks as future


def test_materializes_eight_distinct_replacements_and_ten_remedies(tmp_path: Path) -> None:
    roots = future.build(tmp_path)
    assert len(roots) == 8
    assert 8 <= len(roots) <= 12
    assert {root.name for root in roots} == {case.task_id for case in future.CASES}
    assert len({case.profile for case in future.CASES}) == 8
    assert len({case.public_api for case in future.CASES}) == 8
    records = [json.loads(path.read_text()) for path in (tmp_path / ".state/remedy").glob("*.json")]
    assert len(records) == 10
    assert sum(row["disposition"] == "replace" for row in records) == 8
    assert sum(row["disposition"] == "reject" for row in records) == 2
    assert all(row["user_inputs"]["hard_count"] == "8-12" for row in records)
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert (root / ".meta/negative_false_substitute.cpp").is_file()


def test_core_verifier_records_complete_seven_dimension_matrix(tmp_path: Path) -> None:
    future.build(tmp_path)
    manifest = future.verify_core(tmp_path)
    hard_rule = manifest["screen"]["hard_rule"]
    assert hard_rule["pair_count"] == 28
    assert hard_rule["expected_pair_count"] == 28
    assert tuple(hard_rule["dimensions"]) == future.HARD_RULE_DIMENSIONS
    assert len(hard_rule["pairs"]) == 28
    for pair in hard_rule["pairs"]:
        assert pair["pass"]
        assert set(pair["dimensions"]) == set(future.HARD_RULE_DIMENSIONS)
        assert all(row["distinct"] for row in pair["dimensions"].values())
        assert all(
            row["containment"] < future.HARD_RULE_THRESHOLD for row in pair["dimensions"].values()
        )
    assert manifest["screen"]["prompt_boundary"] == "pass"
    assert manifest["screen"]["reference_mapping"] == "pass"
    assert manifest["screen"]["semantic_holdout"]["holdout_root_count"] == 26


def test_coherent_adversarial_controls_change_files_and_are_rejected(tmp_path: Path) -> None:
    future.build(tmp_path)
    base = future._features(tmp_path / future.CASES[0].task_id)
    outcomes = future._control_screen(tmp_path)
    assert set(outcomes) == {
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
    }
    for name, outcome in outcomes.items():
        assert outcome == "rejected:duplicate_family"
        root = tmp_path / ".state/hard-rule-controls" / name
        assert (root / "candidate.cpp").read_text() != future.CASES[0].reference
        feature = {
            "public_api": future._normalized_tokens((root / "task.h").read_text()),
            "owned_state_algorithm": future._normalized_tokens(
                (root / "task.h").read_text() + (root / "candidate.cpp").read_text()
            ),
            "mutation_selection_rules": base["mutation_selection_rules"],
            "invalid_boundary_behavior": base["invalid_boundary_behavior"],
            "reference_control_flow": future._normalized_tokens(
                (root / "candidate.cpp").read_text()
            ),
            "deterministic_oracle": future._normalized_tokens(
                (root / "task_visible_test.cpp").read_text()
                + (root / ".meta/task_hidden_test.cpp").read_text()
            ),
            "topic_negative_fixture": future._normalized_tokens(
                (root / "candidate.cpp").read_text()
            ),
        }
        decision = future._pair_decision(future.CASES[0].task_id, base, name, feature)
        assert not decision["pass"]
        assert any(not row["distinct"] for row in decision["dimensions"].values())


def test_each_root_has_distinct_nonempty_topic_negative(tmp_path: Path) -> None:
    roots = future.build(tmp_path)
    hashes = set()
    for case, root in zip(future.CASES, roots, strict=True):
        negative = (root / ".meta/negative_false_substitute.cpp").read_text()
        assert negative != case.reference
        assert case.negative_old not in negative
        assert case.negative_new in negative
        hashes.add(future._sha(" ".join(future._normalized_tokens(negative)).encode()))
    assert len(hashes) == 8


def test_references_make_strict_whole_file_answers(tmp_path: Path) -> None:
    for root in future.build(tmp_path):
        task = moonlight_aider_task_sft.load_task(root)
        answer = moonlight_aider_task_sft.build_assistant_response(
            task, moonlight_aider_task_sft.load_example_files_from_config(root)
        )
        assert answer.startswith(f"{root.name}.h\n```")
        assert f"{root.name}.cpp\n```" in answer
        assert ".meta/example" not in answer


def test_docker_verifier_owns_network_snapshot_sanitizer_and_controls() -> None:
    source = inspect.getsource(future.verify_docker)
    assert '"--network"' in source and '"none"' in source
    assert "Unix Makefiles" in source
    assert "-fsanitize=address,undefined" in source
    assert "grader_mount_hash_mismatch" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "negative.tsv" in source
    assert "controls.tsv" in source


def test_wrapper_targets_requested_parallel_family_type() -> None:
    path = Path("examples/slime/moonlight_cpp_perf/prepare_future_date_aider_tasks.sh")
    assert path.is_file() and path.stat().st_mode & 0o111
    content = path.read_text()
    assert "moonlight_future_date_aider_tasks" in content
    assert "aider-tasks-reverify/aider-text-grid-reshaping/future-date-calculations" in content
