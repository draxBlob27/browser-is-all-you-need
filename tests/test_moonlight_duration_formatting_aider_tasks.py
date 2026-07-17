import json
from pathlib import Path
from w8_biayn.integrations import moonlight_aider_task_sft as sft
from w8_biayn.integrations import moonlight_duration_formatting_aider_tasks as durations
def test_materializes_every_duration_root(tmp_path:Path)->None:
 roots=durations.build(tmp_path);assert len(roots)==10
 for root in roots:
  config=json.loads((root/'.meta/config.json').read_text());assert config['files']['solution']==[f'{root.name}.h',f'{root.name}.cpp'];assert (root/'.meta/task_hidden_test.cpp').is_file()
def test_references_make_whole_file_answer(tmp_path:Path)->None:
 root=durations.build(tmp_path)[0];task=sft.load_task(root);answer=sft.build_assistant_response(task,sft.load_example_files_from_config(root));assert answer.startswith(f'{root.name}.h\n```') and f'{root.name}.cpp\n```' in answer
def test_wrapper_is_executable()->None:
 p=Path('examples/slime/moonlight_cpp_perf/prepare_duration_formatting_aider_tasks.sh');assert p.is_file() and p.stat().st_mode&0o111
