from __future__ import annotations

import inspect
import json
from pathlib import Path

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_leap_year_rule_aider_tasks as leap


def _seed_remedies(out: Path) -> None:
    source = leap.DEFAULT_OUT / ".state" / "remedy"
    target = out / ".state" / "remedy"
    target.mkdir(parents=True)
    for path in source.iterdir():
        (target / path.name).write_bytes(path.read_bytes())


def test_materializes_exactly_eight_distinct_replacements(tmp_path: Path) -> None:
    _seed_remedies(tmp_path)
    roots = leap.build(tmp_path)
    assert leap.MIN_ROOTS == 8 and leap.MAX_ROOTS == 12
    assert len(roots) == 8
    assert len({case.task_id for case in leap.CASES}) == 8
    assert len({case.mechanism for case in leap.CASES}) == 8
    assert sum(case.legacy_id is not None for case in leap.CASES) == 5
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["family_id"] == leap.FAMILY_ID
        assert (root / ".meta/negative_false_substitute.cpp").is_file()
        assert (root / ".meta/task_hard_rule_test.cpp").is_file()


def test_core_verifier_records_all_pairs_and_every_dimension(tmp_path: Path) -> None:
    _seed_remedies(tmp_path)
    leap.build(tmp_path)
    manifest = leap.verify_core(tmp_path)
    hard_rule = manifest["hard_rule"]
    assert hard_rule["root_count"] == 8
    assert hard_rule["pair_count"] == 28
    assert hard_rule["expected_pair_count"] == 28
    assert hard_rule["dimensions"] == list(leap.HARD_RULE_DIMENSIONS)
    assert len(hard_rule["pairs"]) == 28
    for pair in hard_rule["pairs"]:
        assert pair["pass"] is True
        assert set(pair["dimensions"]) == set(leap.HARD_RULE_DIMENSIONS)
        for dimension in leap.HARD_RULE_DIMENSIONS:
            decision = pair["dimensions"][dimension]
            assert decision["distinct"] is True
            assert decision["left_token_count"] > 0
            assert decision["right_token_count"] > 0
    assert manifest["benchmark_screen"]["holdout_count"] == 26
    assert manifest["benchmark_screen"]["comparison_count"] == 208


def test_coherent_controls_change_files_and_fail_all_seven_dimensions(tmp_path: Path) -> None:
    _seed_remedies(tmp_path)
    leap.build(tmp_path)
    outcomes = leap._verify_controls(tmp_path)
    assert set(outcomes) == {
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
    }
    for outcome in outcomes.values():
        assert outcome["changed_tree"] is True
        assert outcome["semantic_result"] == "rejected:duplicate_family"
        assert set(outcome["failed_dimensions"]) == set(leap.HARD_RULE_DIMENSIONS)
    controls = leap._adversarial_cases()
    assert controls["domain-identifier-renamed-clone"][1].header != controls["domain-identifier-renamed-clone"][0].header
    assert controls["constants-policy-clone"][1].reference != controls["constants-policy-clone"][0].reference
    assert controls["opposite-end-selection-clone"][1].reference != controls["opposite-end-selection-clone"][0].reference


def test_every_topic_negative_is_nonempty_and_normalized_distinct() -> None:
    signatures = set()
    for case in leap.CASES:
        assert case.negative_source != case.reference
        assert case.negative_reason
        signature = leap._normalized_tokens(case.negative_source)
        assert signature not in signatures
        signatures.add(signature)
    assert len(signatures) == 8


def test_references_make_role_safe_whole_file_answers(tmp_path: Path) -> None:
    _seed_remedies(tmp_path)
    for root in leap.build(tmp_path):
        task = moonlight_aider_task_sft.load_task(root)
        response = moonlight_aider_task_sft.build_assistant_response(
            task, moonlight_aider_task_sft.load_example_files_from_config(root)
        )
        assert response.startswith(f"{root.name}.h\n```")
        assert f"{root.name}.cpp\n```" in response
        assert ".meta/example" not in response


def test_docker_verifier_is_snapshot_safe_and_network_disabled() -> None:
    source = inspect.getsource(leap.verify_docker) + inspect.getsource(leap._docker_script)
    assert '"--network", "none"' in source
    assert "family.tar" in source
    assert "grader_mount_hash_mismatch" not in source or "hash_tree" in source
    assert "-fsanitize=address,undefined" in source
    assert "negative_false_substitute.cpp" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "local_family_verified" in source


def test_wrapper_targets_supplied_parallel_reverify_type() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_leap_year_rule_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_leap_year_rule_aider_tasks" in content
    assert "aider-tasks-reverify/aider-text-grid-reshaping/leap-year-rule" in content
