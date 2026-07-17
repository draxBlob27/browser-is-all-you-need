import json
from pathlib import Path

from w8_biayn.integrations import moonlight_aider_task_sft as sft
from w8_biayn.integrations import moonlight_xor_linked_list_aider_tasks as xor


def test_xor_linked_list_materializes_all_curriculum_roots(tmp_path: Path) -> None:
    roots = xor.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {spec.task_id for spec in xor.TASKS}
    for root in roots:
        provenance = json.loads((root / ".meta/provenance.json").read_text())
        assert provenance["curriculum_task_id"] == root.name
        assert "raw pointer XOR" in provenance["representation"]
        assert (root / ".meta/task_hidden_test.cpp").is_file()


def test_xor_linked_list_references_make_whole_file_answers(tmp_path: Path) -> None:
    root = xor.build(tmp_path)[0]
    task = sft.load_task(root)
    answer = sft.build_assistant_response(task, sft.load_example_files_from_config(root))
    assert answer.startswith(f"{root.name}.h\n```")
    assert f"{root.name}.cpp\n```" in answer


def test_xor_linked_list_wrapper_is_executable() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_xor_linked_list_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    assert "moonlight_xor_linked_list_aider_tasks" in wrapper.read_text()
