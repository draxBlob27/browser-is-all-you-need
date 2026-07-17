from __future__ import annotations
import json
from pathlib import Path
from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_threaded_binary_tree_aider_tasks as tasks

def test_threaded_tree_curriculum_materializes_every_proposed_task(tmp_path: Path) -> None:
    roots=tasks.build(tmp_path);assert len(roots)==20;assert {root.name for root in roots}=={spec.task_id for spec in tasks.TASKS}
    for root in roots:
        config=json.loads((root/".meta/config.json").read_text());provenance=json.loads((root/".meta/provenance.json").read_text())
        assert config["files"]["solution"]==[f"{root.name}.h",f"{root.name}.cpp"];assert config["files"]["example"]==[".meta/example.h",".meta/example.cpp"]
        assert provenance["curriculum_task_id"]==root.name;assert "not admitted SFT data" in provenance["status"];assert "is_left_thread" in (root/f"{root.name}.h").read_text();assert (root/".meta/task_hidden_test.cpp").is_file()

def test_threaded_tree_references_make_a_whole_file_sft_answer(tmp_path: Path) -> None:
    root=tasks.build(tmp_path)[0];task=moonlight_aider_task_sft.load_task(root)
    answer=moonlight_aider_task_sft.build_assistant_response(task,moonlight_aider_task_sft.load_example_files_from_config(root))
    assert answer.startswith(f"{root.name}.h\n```");assert f"{root.name}.cpp\n```" in answer
