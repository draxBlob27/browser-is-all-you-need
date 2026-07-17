import json

from w8_biayn.integrations.moonlight_aider_tasks_sft import build_dataset


def test_build_dataset_uses_only_requested_metadata(tmp_path):
    task = tmp_path / "tasks" / "topic" / "demo-task"
    (task / ".docs").mkdir(parents=True)
    (task / ".meta").mkdir()
    (task / ".docs" / "introduction.md").write_text("intro\n")
    (task / ".docs" / "instructions.md").write_text("instructions\n")
    (task / "demo-task.h").write_text("#pragma once\n")
    (task / "demo-task.cpp").write_text('#include "demo-task.h"\n')
    (task / ".meta" / "example.h").write_text("#pragma once\n")
    (task / ".meta" / "example.cpp").write_text('#include "demo-task.h"\n')
    (task / ".meta" / "config.json").write_text(json.dumps({"files": {"solution": ["demo-task.h", "demo-task.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}))

    path = build_dataset(tasks_root=tmp_path / "tasks", out=tmp_path / "out")
    row = json.loads(path.read_text())
    assert row["task_id"] == "demo-task"
    assert row["metadata"] == {"purpose": "topic", "subset": "train", "task_id": "demo-task"}
