from __future__ import annotations

import json
from pathlib import Path

from w8_biayn.integrations import moonlight_aider_task_sft as sft
from w8_biayn.integrations import moonlight_calendar_arithmetic_aider_tasks as calendar


def test_calendar_arithmetic_materializes_every_proposed_task(tmp_path: Path) -> None:
    roots = calendar.build(tmp_path)
    assert {root.name for root in roots} == {task.task_id for task in calendar.TASKS}
    for root in roots:
        config = json.loads((root / ".meta" / "config.json").read_text())
        provenance = json.loads((root / ".meta" / "provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["curriculum_task_id"] == root.name
        assert provenance["status"] == "local task artifact; not admitted SFT data"
        assert (root / ".meta" / "task_hidden_test.cpp").is_file()


def test_calendar_references_make_whole_file_sft_answers(tmp_path: Path) -> None:
    root = calendar.build(tmp_path)[0]
    task = sft.load_task(root)
    answer = sft.build_assistant_response(task, sft.load_example_files_from_config(root))
    assert answer.startswith(f"{root.name}.h\n```")
    assert f"{root.name}.cpp\n```" in answer
    assert ".meta/example" not in answer


def test_calendar_arithmetic_wrapper_is_executable() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_calendar_arithmetic_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    assert "moonlight_calendar_arithmetic_aider_tasks" in wrapper.read_text()
