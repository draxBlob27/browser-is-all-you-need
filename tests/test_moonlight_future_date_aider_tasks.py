from __future__ import annotations
import json
from pathlib import Path
from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_future_date_aider_tasks as future

def test_materializes_every_future_date_task(tmp_path:Path)->None:
 roots=future.build(tmp_path);assert {x.name for x in roots}=={x.id for x in future.TASKS}
 for root in roots:
  config=json.loads((root/'.meta/config.json').read_text());assert config['files']['solution']==[f'{root.name}.h',f'{root.name}.cpp'];assert (root/'.meta/task_hidden_test.cpp').is_file()
def test_reference_builds_whole_file_answer(tmp_path:Path)->None:
 root=future.build(tmp_path)[0];task=moonlight_aider_task_sft.load_task(root);answer=moonlight_aider_task_sft.build_assistant_response(task,moonlight_aider_task_sft.load_example_files_from_config(root));assert answer.startswith(f'{root.name}.h\n```') and f'{root.name}.cpp\n```' in answer
def test_wrapper_is_executable()->None:
 p=Path('examples/slime/moonlight_cpp_perf/prepare_future_date_aider_tasks.sh');assert p.is_file() and p.stat().st_mode&0o111
