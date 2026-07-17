from pathlib import Path
from w8_biayn.integrations import moonlight_aider_task_sft as sft
from w8_biayn.integrations import moonlight_nested_structure_aider_tasks as nested

def test_nested_structure_materializes_every_proposed_task(tmp_path: Path) -> None:
    roots = nested.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {spec.task_id for spec in nested.TASKS}
    for root in roots:
        assert (root / ".docs" / "instructions.md").is_file()
        assert (root / ".meta" / "provenance.json").is_file()
        assert (root / ".meta" / "task_hidden_test.cpp").is_file()

def test_nested_structure_references_make_whole_file_sft_answers(tmp_path: Path) -> None:
    root = nested.build(tmp_path)[0]; task = sft.load_task(root)
    answer = sft.build_assistant_response(task, sft.load_example_files_from_config(root))
    assert answer.startswith(f"{root.name}.h\n```") and f"{root.name}.cpp\n```" in answer

def test_nested_structure_wrapper_is_executable() -> None:
    wrapper = Path("examples/slime/moonlight_cpp_perf/prepare_nested_structure_aider_tasks.sh")
    assert wrapper.is_file() and wrapper.stat().st_mode & 0o111
    assert "moonlight_nested_structure_aider_tasks" in wrapper.read_text()
