from pathlib import Path
from w8_biayn.integrations import moonlight_aider_task_sft as sft
from w8_biayn.integrations import moonlight_lfu_cache_aider_tasks as lfu

def test_lfu_curriculum_materializes_every_proposed_task(tmp_path: Path) -> None:
    roots = lfu.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {task.task_id for task in lfu.TASKS}
    for root in roots:
        assert (root / ".docs" / "instructions.md").is_file()
        assert (root / ".meta" / "provenance.json").is_file()
        assert (root / "CMakeLists.txt").is_file()

def test_lfu_references_make_whole_file_sft_answers(tmp_path: Path) -> None:
    root = lfu.build(tmp_path)[0]
    task = sft.load_task(root)
    answer = sft.build_assistant_response(task, sft.load_example_files_from_config(root))
    assert answer.startswith(f"{root.name}.h\n```")
    assert f"{root.name}.cpp\n```" in answer
    assert ".meta/example" not in answer

def test_lfu_wrapper_is_executable() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_lfu_cache_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    assert "moonlight_lfu_cache_aider_tasks" in wrapper.read_text()
