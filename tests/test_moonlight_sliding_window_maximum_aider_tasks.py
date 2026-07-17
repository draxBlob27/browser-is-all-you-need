from __future__ import annotations
import json
from pathlib import Path
from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_sliding_window_maximum_aider_tasks as sliding

def test_materializes_every_sliding_window_maximum_root(tmp_path: Path) -> None:
    roots = sliding.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {spec.task_id for spec in sliding.TASKS}
    for root in roots:
        config = json.loads((root / ".meta/config.json").read_text()); provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["curriculum_task_id"] == root.name
        assert provenance["status"] == "local task artifact; not admitted SFT data"
        assert (root / ".meta/task_hidden_test.cpp").exists()

def test_reference_files_make_an_ordered_whole_file_answer(tmp_path: Path) -> None:
    root = sliding.build(tmp_path)[0]; task = moonlight_aider_task_sft.load_task(root)
    answer = moonlight_aider_task_sft.build_assistant_response(task, moonlight_aider_task_sft.load_example_files_from_config(root))
    assert answer.startswith(f"{root.name}.h\n```") and f"{root.name}.cpp\n```" in answer and ".meta/example" not in answer
