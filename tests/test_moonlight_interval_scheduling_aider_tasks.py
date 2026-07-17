from __future__ import annotations

import json
from pathlib import Path

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_interval_scheduling_aider_tasks as interval


def test_interval_scheduling_curriculum_materializes_every_proposed_task(tmp_path: Path) -> None:
    roots = interval.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {spec.task_id for spec in interval.TASKS}
    for root in roots:
        config = json.loads((root / ".meta" / "config.json").read_text())
        provenance = json.loads((root / ".meta" / "provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["curriculum_task_id"] == root.name
        assert provenance["status"] == "local task artifact; not admitted SFT data"
        assert (root / ".meta" / "task_hidden_test.cpp").exists()


def test_interval_scheduling_references_make_whole_file_sft_answers(tmp_path: Path) -> None:
    root = interval.build(tmp_path)[0]
    task = moonlight_aider_task_sft.load_task(root)
    answer = moonlight_aider_task_sft.build_assistant_response(task, moonlight_aider_task_sft.load_example_files_from_config(root))
    assert answer.startswith(f"{root.name}.h\n```")
    assert f"{root.name}.cpp\n```" in answer


def test_interval_scheduling_wrapper_is_executable() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_interval_scheduling_aider_tasks.sh")
    assert wrapper.exists()
    assert wrapper.stat().st_mode & 0o111
    assert "moonlight_interval_scheduling_aider_tasks" in wrapper.read_text()
