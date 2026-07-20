from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_cyclic_slot_systems_aider_tasks as cyclic


def test_cyclic_slot_systems_materialize_distinct_clean_room_roots(tmp_path: Path) -> None:
    roots = cyclic.build(tmp_path)
    assert cyclic.MIN_ROOTS == 15
    assert cyclic.MAX_ROOTS == 20
    assert len(roots) == 15
    assert cyclic.MIN_ROOTS <= len(roots) <= cyclic.MAX_ROOTS
    assert {root.name for root in roots} == {spec.task_id for spec in cyclic.TASKS}
    assert len({spec.kind for spec in cyclic.TASKS}) == len(cyclic.TASKS)
    assert cyclic.DEFAULT_OUT.parts[-2:] == (
        "aider-dsa",
        "circular-buffer",
    )
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert config["files"]["test"] == [
            "task_visible_test.cpp",
            ".meta/task_hidden_test.cpp",
        ]
        assert not any(
            term in (root / ".docs/instructions.md").read_text().lower()
            for term in ("fifo", "oldest", "forced write", "circular buffer")
        )


def test_cyclic_slot_systems_prompt_and_core_screen_pass(tmp_path: Path) -> None:
    cyclic.build(tmp_path)
    evidence = cyclic.verify_core(tmp_path, require_remedy=False)
    assert {item["mechanism"] for item in evidence.values()} == {
        spec.kind for spec in cyclic.TASKS
    }
    assert len({item["api_signature"] for item in evidence.values()}) == 15
    assert len({item["source_signature"] for item in evidence.values()}) == 15
    screen = json.loads((tmp_path / ".state/family-screen.json").read_text())
    assert screen["normalizer"] == "cyclic-slot-semantic-v4-artifact-derived"
    assert screen["root_count"] == 15
    assert screen["user_count_bound"] == {"minimum": 15, "maximum": 20}
    assert screen["count_negative_fixtures"] == {
        "above_maximum": "binding_root_count_failed",
        "at_maximum": None,
        "at_minimum": None,
        "below_minimum": "binding_root_count_failed",
    }
    assert len(screen["pairwise_semantic_overlap"]) == 15 * 14 // 2
    assert all(item["overlap"] < 0.70 for item in screen["pairwise_semantic_overlap"])
    assert set(screen["adversarial_clone_results"]) == {
        "domain-identifier-renamed",
        "constants-or-policy-only",
        "opposite-end-selection",
    }
    assert all(
        item["failure"] == "duplicate_family"
        for item in screen["adversarial_clone_results"].values()
    )
    assert all(
        set(results)
        >= {
            "omitted-file",
            "extra-file",
            "prose-prefix",
            "duplicate-file",
            "unsafe-solution-role",
            "missing-reference",
            "misordered-reference",
            "prompt-term-omission",
            "topic-specific-substitute",
        }
        for results in screen["negative_fixture_results"].values()
    )
    task = moonlight_aider_task_sft.load_task(tmp_path / cyclic.TASKS[0].task_id)
    answer = moonlight_aider_task_sft.build_assistant_response(
        task,
        moonlight_aider_task_sft.load_example_files_from_config(
            tmp_path / cyclic.TASKS[0].task_id
        ),
    )
    assert answer.startswith(f"{cyclic.TASKS[0].task_id}.h\n```")
    assert ".meta/example" not in answer


def test_cyclic_slot_systems_expose_and_trace_complete_observable_state(
    tmp_path: Path,
) -> None:
    cyclic.build(tmp_path)
    expected = {
        "parking-permit-slot-allocator": ("occupied_slots()", "trace.occupied_slots()==expected_slots"),
        "maintenance-duty-wheel": ("scheduled()", "trace.scheduled()==expected_schedule"),
        "api-sampling-window-counter": ("buckets_at", "trace.buckets_at(observed_tick)"),
        "weighted-service-rotor": ("lanes()", "subject.lanes()==model"),
        "generation-arrival-barrier": ("state()", "subject.state()==curriculum::BarrierState"),
        "traffic-phase-controller": ("state()", "subject.state()==std::optional<curriculum::PhaseState>"),
        "circular-signal-convolution": ("circular_convolution", "circular_convolution(a,b)"),
        "modular-arc-set": ("intervals()", "subject.intervals()==intervals"),
        "clockwise-token-router": ("tokens()", "subject.tokens()==tokens"),
        "functional-cycle-index": ("info(std::size_t", "g.info(i)==std::optional<curriculum::CycleInfo>"),
        "round-robin-pairing-table": ("rounds()", "all.size()==count*(count-1U)/2U"),
        "crc-byte-register": ("value()", "subject.value()==model"),
        "epoch-stamped-sparse-table": ("entries()", "subject.entries()==entries"),
        "rotating-bloom-membership": ("active_bits()", "subject.active_bits()==snapshot"),
        "serial-replay-window": ("state()", "subject.state()==curriculum::ReplayState"),
    }
    for task_id, (api_marker, trace_marker) in expected.items():
        root = tmp_path / task_id
        assert api_marker in next(root.glob("*.h")).read_text()
        hidden = (root / ".meta/task_hidden_test.cpp").read_text()
        assert trace_marker in hidden


def test_cyclic_slot_systems_negative_contract_helpers(tmp_path: Path) -> None:
    cyclic.build(tmp_path)
    for spec in cyclic.TASKS:
        root = tmp_path / spec.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        files = config["files"]
        assert cyclic._role_failure(root, files) is None

        unsafe = json.loads(json.dumps(files))
        unsafe["solution"].append("CMakeLists.txt")
        assert cyclic._role_failure(root, unsafe) == "unsafe_path"

        missing = json.loads(json.dumps(files))
        missing["example"].pop()
        assert cyclic._role_failure(root, missing) == "target_reference_mismatch"

        reversed_examples = json.loads(json.dumps(files))
        reversed_examples["example"].reverse()
        assert cyclic._role_failure(root, reversed_examples) == "target_reference_mismatch"

        task = cyclic.load_task(root)
        response = cyclic.build_assistant_response(
            task, cyclic.load_example_files_from_config(root)
        )
        assert cyclic._whole_format_failure(task, response) is None
        assert (
            cyclic._whole_format_failure(task, "prose before files\n" + response)
            == "whole_format_failed"
        )

        instructions = (root / ".docs/instructions.md").read_text()
        assert cyclic._prompt_contract_failure(spec, instructions) is None
        assert (
            cyclic._prompt_contract_failure(
                spec,
                re.sub(
                    re.escape(spec.prompt_terms[0]),
                    "omitted",
                    instructions,
                    flags=re.IGNORECASE,
                ),
            )
            == "prompt_contract_incomplete"
        )


def test_semantic_normalizer_removes_domain_nouns_literals_and_comments() -> None:
    left = cyclic._semantic_tokens(
        "// permits\nbool reserve_slot(int permit42) { return permit42 < 0x10U; }"
    )
    right = cyclic._semantic_tokens(
        "// duties\nbool enqueue_job(int duty99) { return duty99 < 77U; }"
    )
    assert left == right
    assert "permits" not in left
    assert "permit42" not in left
    assert "0x10U" not in left


def test_hard_rule_rejects_required_adversarial_clone_classes(tmp_path: Path) -> None:
    cyclic.build(tmp_path)
    results = cyclic._adversarial_clone_results(tmp_path / "clockwise-token-router")
    assert all(item["overlap"] >= 0.70 for item in results.values())
    assert all(item["failure"] == "duplicate_family" for item in results.values())


def test_replacement_record_invalidates_stale_oracle_evidence(tmp_path: Path) -> None:
    cyclic.build(tmp_path)
    remedy = tmp_path / ".state/remedy"
    remedy.mkdir(parents=True)
    evidence: dict[str, dict[str, object]] = {}
    for spec in cyclic.TASKS:
        evidence[spec.task_id] = {"mechanism": spec.kind}
        (remedy / f"{spec.task_id}.json").write_text(
            json.dumps(
                {
                    "generator_revision": "sha256:stale",
                    "local_status": "local_family_verified",
                    "oracle_evidence": {"result": "stale"},
                    "tree_hash_after": "sha256:stale",
                }
            )
        )

    cyclic._update_replacement_records(tmp_path, evidence)

    for spec in cyclic.TASKS:
        record = json.loads((remedy / f"{spec.task_id}.json").read_text())
        assert "oracle_evidence" not in record
        assert record["local_status"] == "not_completed_oracle_evidence_invalidated"
        assert record["tree_hash_after"] == cyclic._tree_hash(tmp_path / spec.task_id)


def test_cyclic_slot_systems_reject_cross_root_and_container_substitutes() -> None:
    for spec in cyclic.TASKS:
        reference = cyclic._reference(spec)
        assert cyclic._core_failure(spec, reference) is None
        assert cyclic._core_failure(
            spec,
            reference.replace(cyclic.required_marker(spec), "removed_primary_state"),
        ) == "invariant_not_enforced"
        assert cyclic._core_failure(
            spec, reference + "\n#include <deque>\nstd::deque<int> authoritative;"
        ) == "invariant_not_enforced"
        assert cyclic._core_failure(
            spec, reference + f"\nint {spec.forbidden[0]} = 0;"
        ) == "invariant_not_enforced"
        for other in cyclic.TASKS:
            if other.kind != spec.kind:
                assert cyclic._core_failure(spec, cyclic._reference(other)) is not None


def test_cyclic_slot_systems_count_bound_fails_closed() -> None:
    assert cyclic._count_failure(14) == "binding_root_count_failed"
    assert cyclic._count_failure(15) is None
    assert cyclic._count_failure(20) is None
    assert cyclic._count_failure(21) == "binding_root_count_failed"


def test_cyclic_slot_docker_sanity_receipt_is_bound_and_complete() -> None:
    state = cyclic.DEFAULT_OUT / ".state"
    receipt = json.loads((state / "docker-sanity.json").read_text())
    assert receipt["status"] == "pass"
    assert receipt["evidence_class"] == "docker_sanity"
    assert receipt["locked_oracle"] is False
    assert receipt["network"] == "none"
    assert receipt["image_id"] == cyclic.SANITY_IMAGE_ID
    assert receipt["generator_revision"] == cyclic._generator_revision()
    assert set(receipt["tasks"]) == {spec.task_id for spec in cyclic.TASKS}
    for spec in cyclic.TASKS:
        root = cyclic.DEFAULT_OUT / spec.task_id
        task = receipt["tasks"][spec.task_id]
        assert task["normal"] == task["asan_ubsan"] == 2
        assert task["tree_hash"] == cyclic._tree_hash(root)
        assert task["reference_hash"] == cyclic._reference_hash(root)
        remedy = json.loads((state / "remedy" / f"{spec.task_id}.json").read_text())
        assert remedy["local_status"] == "local_family_verified"
        assert remedy["oracle_evidence"]["evidence_class"] == "docker_sanity"


def test_cyclic_slot_systems_refuses_preserved_legacy_root() -> None:
    with pytest.raises(ValueError, match="preserved legacy"):
        cyclic.build(cyclic.LEGACY_ROOT, force=True)


def test_cyclic_slot_wrapper_is_executable() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_cyclic_slot_systems_aider_tasks.sh")
    assert wrapper.stat().st_mode & 0o111
    assert "moonlight_cyclic_slot_systems_aider_tasks" in wrapper.read_text()
