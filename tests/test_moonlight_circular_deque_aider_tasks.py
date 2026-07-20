from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_circular_deque_aider_tasks as deque
from w8_biayn.integrations import moonlight_circular_deque_semantics as semantics


def test_distinct_family_materializes_fifteen_independent_roots(tmp_path: Path) -> None:
    roots = deque.build(tmp_path)
    assert len(roots) == 15
    assert 15 <= len(roots) <= 20
    assert {root.name for root in roots} == {spec.task_id for spec in deque.TASKS}
    assert len({spec.kind for spec in deque.TASKS}) == len(deque.TASKS)
    for spec in deque.TASKS:
        root = tmp_path / spec.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [
            f"{spec.task_id}.h",
            f"{spec.task_id}.cpp",
        ]
        assert config["files"]["example"] == [
            ".meta/example.h",
            ".meta/example.cpp",
        ]
    artifacts = tuple(semantics.load_artifact(root) for root in roots)
    scores = semantics.assert_semantic_diversity(artifacts)
    assert len(scores) == 105
    assert max(score.combined for score in scores) < semantics.DUPLICATE_THRESHOLD


def test_prompt_roles_core_and_semantic_screens_pass(tmp_path: Path) -> None:
    deque.build(tmp_path)
    report = deque.verify_core(tmp_path)
    assert report["normalizer"] == semantics.NORMALIZER_VERSION
    assert report["comparison_scope"] == {
        "family_roots": 15,
        "family_pairs": 105,
        "holdouts": 1,
        "holdout_pairs": 15,
    }
    for spec in deque.TASKS:
        root = tmp_path / spec.task_id
        task = moonlight_aider_task_sft.load_task(root)
        answer = moonlight_aider_task_sft.build_assistant_response(
            task,
            moonlight_aider_task_sft.load_example_files_from_config(root),
        )
        assert answer.startswith(f"{spec.task_id}.h\n```")
        assert f"{spec.task_id}.cpp\n```" in answer
        assert ".meta/example" not in answer


def test_ctest_count_accepts_positive_complete_discovery() -> None:
    assert deque._ctest_count("100% tests passed, 0 tests failed out of 2") == 2
    assert deque._ctest_count("No tests were found!!!") is None
    assert deque._ctest_count("50% tests passed, 1 tests failed out of 2") is None


@pytest.mark.parametrize("spec", deque.TASKS, ids=lambda spec: spec.task_id)
def test_topic_specific_negative_fixtures_are_rejected(
    tmp_path: Path, spec: deque.TaskSpec
) -> None:
    deque.build(tmp_path)
    source = (tmp_path / spec.task_id / ".meta/example.cpp").read_text()
    assert deque._core_failure(spec, source) is None
    assert (
        deque._core_failure(
            spec, source.replace(deque.required_marker(spec), "removed")
        )
        == "invariant_not_enforced"
    )
    extra = deque._extra(spec)
    banned = extra.forbidden[0] if extra else {
        "work_ring": "std::deque",
        "extrema": "std::multiset",
        "router": "std::priority_queue",
    }[spec.kind]
    assert deque._core_failure(spec, source + "\n// " + banned) == "invariant_not_enforced"


def _rename_work_ring(text: str) -> str:
    replacements = {
        "WorkStealScheduler": "CargoDispatchLane",
        "push_local": "accept_manifest",
        "pop_local": "withdraw_recent",
        "steal_oldest": "claim_earliest",
        "slots_": "berths_",
        "head_": "origin_",
        "size_": "cargo_count_",
        "grow": "expand_terminal",
    }
    for before, after in replacements.items():
        text = text.replace(before, after)
    return text


def test_hard_rule_rejects_a_domain_and_identifier_renamed_clone(tmp_path: Path) -> None:
    deque.build(tmp_path)
    original = semantics.load_artifact(tmp_path / "deque-work-steal-scheduler")
    clone = semantics.SemanticArtifact(
        "cargo-terminal-lane",
        original.docs.replace("work", "cargo").replace("scheduler", "terminal"),
        _rename_work_ring(original.api),
        _rename_work_ring(original.source),
        _rename_work_ring(original.tests),
    )
    score = semantics.compare(original, clone)
    assert score.source >= 0.82
    assert score.api >= 0.80
    assert score.tests == 1.0
    assert score.combined >= semantics.DUPLICATE_THRESHOLD
    with pytest.raises(RuntimeError, match=r"duplicate_family:"):
        semantics.assert_semantic_diversity((original, clone))


def test_hard_rule_rejects_constant_and_policy_toggle_clone(tmp_path: Path) -> None:
    deque.build(tmp_path)
    original = semantics.load_artifact(tmp_path / "deque-work-steal-scheduler")
    clone = semantics.SemanticArtifact(
        "work-ring-policy-variant",
        original.docs.replace("four", "sixty four"),
        original.api,
        original.source.replace("4U", "64U").replace(
            "if(id.empty())return;", "if(id.empty()){return;}"
        ),
        original.tests.replace("600", "900"),
    )
    score = semantics.compare(original, clone)
    assert score.combined >= semantics.DUPLICATE_THRESHOLD
    with pytest.raises(RuntimeError, match=r"duplicate_family:"):
        semantics.assert_semantic_diversity((original, clone))


def _flip_deque_ends(text: str) -> str:
    return (
        text.replace("push_front", "temporary_push_end")
        .replace("push_back", "push_front")
        .replace("temporary_push_end", "push_back")
        .replace("pop_front", "temporary_pop_end")
        .replace("pop_back", "pop_front")
        .replace("temporary_pop_end", "pop_back")
    )


def test_hard_rule_rejects_opposite_end_policy_clone(tmp_path: Path) -> None:
    deque.build(tmp_path)
    original = semantics.load_artifact(tmp_path / "deque-josephus-elimination")
    clone = semantics.SemanticArtifact(
        "reverse-policy-name",
        original.docs.replace("clockwise", "counterclockwise"),
        _flip_deque_ends(original.api),
        _flip_deque_ends(original.source),
        _flip_deque_ends(original.tests),
    )
    score = semantics.compare(original, clone)
    assert score.source >= 0.95
    assert score.combined >= semantics.DUPLICATE_THRESHOLD
    with pytest.raises(RuntimeError, match=r"duplicate_family:"):
        semantics.assert_semantic_diversity((original, clone))


def test_hard_rule_does_not_use_kind_labels_or_raw_source_hashes(tmp_path: Path) -> None:
    deque.build(tmp_path)
    original = semantics.load_artifact(tmp_path / "deque-run-segment-editor")
    clone = semantics.SemanticArtifact(
        "unrelated-kind-label",
        original.docs,
        original.api,
        original.source,
        original.tests,
    )
    assert original.task_id != clone.task_id
    with pytest.raises(RuntimeError, match=r"duplicate_family:"):
        semantics.assert_semantic_diversity((original, clone))


def test_legacy_family_is_not_modified_or_emitted(tmp_path: Path) -> None:
    roots = deque.build(tmp_path)
    assert not ({root.name for root in roots} & set(deque.LEGACY_IDS))
    assert deque.DEFAULT_OUT != deque.LEGACY_OUT
    expected_hashes = {
        "cdeque-audio-jitter": "1c0b7e37ceb0b63101d422721b1234a821a6c9fdb510994fbed1876555d570d6",
        "cdeque-warehouse-loading": "89b36011236b5e0252e595f16c1634f519d3beac6cfd21046ed05e749064041e",
    }
    for task_id, expected in expected_hashes.items():
        root = deque.LEGACY_OUT / task_id
        digest = hashlib.sha256()
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            digest.update(path.relative_to(root).as_posix().encode() + b"\0")
            digest.update(path.read_bytes() + b"\0")
        assert digest.hexdigest() == expected


def test_every_remedy_spec_precedes_implementation_and_has_required_sections() -> None:
    remedy = deque.DEFAULT_OUT / ".state/remedy"
    required = [
        "## Identity",
        "## Objective",
        "## Public API",
        "## Behavior table",
        "## Implementation invariant",
        "## Starter and reference",
        "## Tests",
        "## Files and metadata",
        "## Build/oracle",
        "## Family/contamination",
        "## Optional dataset handoff",
        "## Acceptance",
    ]
    for task_id in (*deque.LEGACY_IDS, *(spec.task_id for spec in deque.TASKS)):
        record = json.loads((remedy / f"{task_id}.json").read_text())
        specification = (remedy / f"{task_id}.md").read_text()
        positions = [specification.index(heading) for heading in required]
        assert positions == sorted(positions)
        assert record["selected_prompt_path"] == deque.PROMPT
        assert record["remedy_spec_hash"] == (
            "sha256:" + hashlib.sha256(specification.encode()).hexdigest()
        )


def test_skill_requires_artifact_derived_all_pairs_and_adversarial_controls() -> None:
    skill = Path(".agents/skills/aider-task-family-remediation/SKILL.md").read_text()
    for required in (
        "actual emitted docs, public API, reference",
        "compare every unordered pair",
        "kind labels",
        "domain/identifier-renamed clone",
        "constants-or-policy-only clone",
        "opposite-end-selection clone",
    ):
        assert required in skill


def _sha256sum_aggregate(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = "./" + path.relative_to(root).as_posix()
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        digest.update(f"{file_hash}  {relative}\n".encode())
    return digest.hexdigest()


def test_docker_sanity_receipt_is_bound_and_complete() -> None:
    state = deque.DEFAULT_OUT / ".state"
    receipt_path = state / "docker-sanity.json"
    receipt = json.loads(receipt_path.read_text())
    receipt_hash = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
    assert receipt["status"] == "pass"
    assert receipt["evidence_class"] == "docker_sanity"
    assert receipt["locked_oracle"] is False
    assert receipt["network"] == "none"
    assert receipt["host_container_mount_hash_match"] is True
    assert set(receipt["tasks"]) == {spec.task_id for spec in deque.TASKS}
    for spec in deque.TASKS:
        task_receipt = receipt["tasks"][spec.task_id]
        assert task_receipt["normal"] == task_receipt["asan_ubsan"] == 2
        assert task_receipt["tree_sha256"] == _sha256sum_aggregate(
            deque.DEFAULT_OUT / spec.task_id
        )
        remedy = json.loads((state / "remedy" / f"{spec.task_id}.json").read_text())
        assert remedy["local_status"] == "local_family_verified"
        assert remedy["docker_sanity_receipt"]["sha256"] == receipt_hash
