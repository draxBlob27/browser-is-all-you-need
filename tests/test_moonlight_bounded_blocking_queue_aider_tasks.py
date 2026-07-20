from __future__ import annotations

import json
import inspect
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_bounded_blocking_queue_aider_tasks as bbq


def test_bounded_blocking_queue_curriculum_materializes_every_proposed_task(tmp_path: Path) -> None:
    roots = bbq.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {spec.task_id for spec in bbq.TASKS}
    assert len({spec.mode for spec in bbq.TASKS}) == len(bbq.TASKS)
    specs = {spec.task_id: spec for spec in bbq.TASKS}
    for root in roots:
        config = json.loads((root / ".meta" / "config.json").read_text())
        provenance = json.loads((root / ".meta" / "provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["curriculum_task_id"] == root.name
        assert provenance["status"] == "local task artifact; not admitted SFT data"
        assert provenance["family_id"] == "aider-dsa-bounded-blocking-queue-v2"
        spec = specs[root.name]
        assert provenance["semantic_profile"] == spec.mode
        assert (root / ".meta" / "task_hidden_test.cpp").exists()
        assert "return false" in (root / f"{root.name}.cpp").read_text()
        assert spec.contract in (root / ".docs" / "instructions.md").read_text()
        assert spec.method in (root / f"{root.name}.h").read_text()
        assert spec.method in (root / ".meta" / "example.cpp").read_text()


def test_bounded_blocking_queue_private_discriminators_and_verifier_are_owned() -> None:
    hidden = bbq._test(bbq.TASKS[0], True)
    assert "wait_for" in hidden
    assert "full.close_dispatch()" in hidden
    assert "std::atomic<int> producer_failures" in hidden
    verifier = inspect.getsource(bbq.verify)
    assert "Unix Makefiles" in verifier
    assert "sanitizer_test_count_mismatch" in verifier


def test_bounded_blocking_queue_core_verifier_enforces_remedy_screens(tmp_path: Path) -> None:
    bbq.build(tmp_path)
    bbq.verify_core(tmp_path, require_remedy=False)
    manifest = json.loads((tmp_path / ".state" / "materialization-manifest.json").read_text())
    assert manifest["schema_version"] == bbq.MANIFEST_SCHEMA
    assert manifest["task_count"] == 20
    assert manifest["screen"] == {
        "benchmark_contamination": "pass",
        "duplicate_family": "pass",
        "prompt_boundary": "pass",
        "reference_mapping": "pass",
    }
    contaminated = tmp_path / "contaminated"
    contaminated.mkdir()
    (contaminated / "copied.txt").write_text("grade-school")
    with pytest.raises(RuntimeError, match="benchmark_id_overlap"):
        bbq._benchmark_screen(contaminated)


def test_bounded_blocking_queue_references_make_whole_file_sft_answers(tmp_path: Path) -> None:
    root = bbq.build(tmp_path)[0]
    task = moonlight_aider_task_sft.load_task(root)
    answer = moonlight_aider_task_sft.build_assistant_response(
        task, moonlight_aider_task_sft.load_example_files_from_config(root)
    )
    assert answer.startswith(f"{root.name}.h\n```")
    assert f"{root.name}.cpp\n```" in answer
    assert ".meta/example" not in answer


def test_bounded_blocking_queue_wrapper_is_executable() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_bounded_blocking_queue_aider_tasks.sh")
    assert wrapper.exists()
    assert wrapper.stat().st_mode & 0o111
    content = wrapper.read_text()
    assert "moonlight_bounded_blocking_queue_aider_tasks" in content
    assert "aider-tasks-reverify/aider-dsa/bounded-blocking-queue" in content
