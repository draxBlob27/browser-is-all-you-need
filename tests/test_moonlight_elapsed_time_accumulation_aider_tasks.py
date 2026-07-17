from __future__ import annotations
import json
from pathlib import Path
from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_elapsed_time_accumulation_aider_tasks as elapsed
def test_materializes_every_elapsed_root(tmp_path:Path)->None:
 roots=elapsed.build(tmp_path);assert len(roots)==10;assert {p.name for p in roots}=={x.task_id for x in elapsed.TASKS}
 for root in roots:
  config=json.loads((root/'.meta/config.json').read_text());provenance=json.loads((root/'.meta/provenance.json').read_text())
  assert config['files']['solution']==[f'{root.name}.h',f'{root.name}.cpp'];assert provenance['curriculum_task_id']==root.name;assert provenance['status']=='local task artifact; not admitted SFT data'
def test_elapsed_reference_is_whole_file_sft_answer(tmp_path:Path)->None:
 root=elapsed.build(tmp_path)[0];task=moonlight_aider_task_sft.load_task(root);answer=moonlight_aider_task_sft.build_assistant_response(task,moonlight_aider_task_sft.load_example_files_from_config(root));assert answer.startswith(f'{root.name}.h\n```') and f'{root.name}.cpp\n```' in answer
def test_elapsed_wrapper_is_executable()->None:
 wrapper=Path('examples/slime/moonlight_cpp_perf/prepare_elapsed_time_accumulation_aider_tasks.sh');assert wrapper.stat().st_mode&0o111;assert 'moonlight_elapsed_time_accumulation_aider_tasks' in wrapper.read_text()
