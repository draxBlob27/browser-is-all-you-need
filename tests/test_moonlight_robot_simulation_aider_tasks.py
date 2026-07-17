from __future__ import annotations
import json
from pathlib import Path
from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_robot_simulation_aider_tasks as robot
def test_materializes_every_robot_root(tmp_path: Path) -> None:
 roots=robot.build(tmp_path);assert len(roots)==20;assert {p.name for p in roots}=={s.task_id for s in robot.TASKS}
 for root in roots:
  config=json.loads((root/".meta/config.json").read_text());assert config["files"]["solution"]==[f"{root.name}.h",f"{root.name}.cpp"];assert json.loads((root/".meta/provenance.json").read_text())["status"]=="local task artifact; not admitted SFT data";assert (root/"task_visible_test.cpp").exists();assert (root/".meta/task_hidden_test.cpp").exists()
def test_robot_reference_makes_whole_file_answer(tmp_path: Path) -> None:
 root=robot.build(tmp_path)[0];task=moonlight_aider_task_sft.load_task(root);answer=moonlight_aider_task_sft.build_assistant_response(task,moonlight_aider_task_sft.load_example_files_from_config(root));assert answer.startswith(f"{root.name}.h\n```") and f"{root.name}.cpp\n```" in answer
def test_robot_wrapper_is_executable() -> None:
 wrapper=Path("examples/slime/moonlight_cpp_perf/prepare_robot_simulation_aider_tasks.sh");assert wrapper.stat().st_mode&0o111;assert "moonlight_robot_simulation_aider_tasks" in wrapper.read_text()
