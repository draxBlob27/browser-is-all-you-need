import json
from pathlib import Path

from w8_biayn.integrations import moonlight_aider_task_sft
from w8_biayn.integrations import moonlight_trie_aider_task_materializer as tasks


def test_materializes_all_trie_curriculum_roots(tmp_path: Path) -> None:
    roots = tasks.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {spec.task_id for spec in tasks.TASKS}
    for root in roots:
        config = json.loads((root / ".meta" / "config.json").read_text())
        assert config["files"]["solution"] == [f"{root.name}.h", f"{root.name}.cpp"]
        assert (root / ".meta" / "task_hidden_test.cpp").is_file()
        assert (root / f"{root.name}.cpp").read_text() != (root / ".meta" / "example.cpp").read_text()


def test_reference_makes_whole_file_sft_answer(tmp_path: Path) -> None:
    root = tasks.build(tmp_path)[0]
    task = moonlight_aider_task_sft.load_task(root)
    answer = moonlight_aider_task_sft.build_assistant_response(task, moonlight_aider_task_sft.load_example_files_from_config(root))
    assert answer.startswith(f"{root.name}.h\n```")
    assert f"{root.name}.cpp\n```" in answer
