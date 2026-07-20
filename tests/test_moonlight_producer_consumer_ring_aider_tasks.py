from __future__ import annotations

import json
import inspect
from pathlib import Path

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_producer_consumer_ring_aider_tasks as ring


def test_producer_consumer_ring_materializes_every_proposed_task(tmp_path: Path) -> None:
    roots = ring.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {spec.task_id for spec in ring.TASKS}
    assert len({spec.kind for spec in ring.TASKS}) == 20
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text())
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["curriculum_task_id"] == root.name
        assert provenance["legacy_task_id"].startswith("pcr-")
        assert provenance["family_id"] == ring.FAMILY_ID
        assert provenance["status"] == "local task artifact; not admitted SFT data"
        assert (root / ".meta/task_hidden_test.cpp").is_file()
        model_test = (root / ".meta/task_model_test.cpp").read_text()
        assert "model" in model_test
        assert root.name in ring.TRACE_TESTS
        fixture_name, mutated = ring.negative_source(
            root.name, ring.CASES[root.name].reference
        )
        assert fixture_name
        assert mutated != ring.CASES[root.name].reference


def test_producer_consumer_ring_core_screen_rejects_legacy_template(tmp_path: Path) -> None:
    ring.build(tmp_path)
    ring.verify_core(tmp_path, require_remedy=False)
    manifest = json.loads((tmp_path / ".state/materialization-manifest.json").read_text())
    assert manifest["task_count"] == 20
    assert manifest["screen"]["duplicate_family"] == "pass"
    assert manifest["screen"]["prompt_boundary"] == "pass"
    assert manifest["screen"]["executable_negative_fixtures"] == "pending"
    assert manifest["screen"]["independent_model_traces"] == "pending"
    for assets in ring.CASES.values():
        assert ring._core_failure(assets, assets.reference) is None
        broken = assets.reference.replace(assets.required_markers[0], "removed")
        assert ring._core_failure(assets, broken) == "invariant_not_enforced"
        assert "std::deque" not in assets.reference


def test_producer_consumer_ring_owner_has_locked_verifier_contract() -> None:
    source = inspect.getsource(ring.verify)
    assert "Unix Makefiles" in source
    assert "sanitizer_test_count_mismatch" in source
    assert "negative_fixture_not_rejected" in source
    receipt_source = inspect.getsource(ring.verify_receipt)
    assert 'runtime.get("environment") != "locked-docker"' in receipt_source
    assert 'runtime.get("network") != "none"' in receipt_source


def test_producer_consumer_ring_reference_makes_whole_file_sft_answer(tmp_path: Path) -> None:
    root = ring.build(tmp_path)[0]
    task = moonlight_aider_task_sft.load_task(root)
    answer = moonlight_aider_task_sft.build_assistant_response(task, moonlight_aider_task_sft.load_example_files_from_config(root))
    assert answer.startswith(f"{root.name}.h\n```")
    assert f"{root.name}.cpp\n```" in answer
    assert ".meta/example" not in answer


def test_producer_consumer_ring_wrapper_is_executable() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_producer_consumer_ring_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    assert "moonlight_producer_consumer_ring_aider_tasks" in wrapper.read_text()
    assert "aider-tasks-reverify/aider-dsa/producer-consumer-ring" in wrapper.read_text()
