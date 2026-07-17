from pathlib import Path
from w8_biayn.integrations import moonlight_ordered_registry_aider_tasks as tasks

def test_materializes_all_ordered_registry_roots(tmp_path: Path) -> None:
    roots = tasks.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {spec.task_id for spec in tasks.TASKS}
    for root in roots:
        assert (root / ".docs" / "instructions.md").is_file()
        assert (root / ".meta" / "provenance.json").is_file()
        assert (root / ".meta" / "example.cpp").is_file()
        assert (root / "CMakeLists.txt").is_file()

def test_reference_is_separate_from_starter(tmp_path: Path) -> None:
    root = tasks.build(tmp_path)[0]
    assert (root / f"{root.name}.cpp").read_text() != (root / ".meta" / "example.cpp").read_text()
