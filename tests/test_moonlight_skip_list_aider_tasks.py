from pathlib import Path
from w8_biayn.integrations import moonlight_skip_list_aider_tasks as tasks
def test_materializes_all_skip_list_roots(tmp_path: Path) -> None:
    roots=tasks.build(tmp_path)
    assert len(roots)==20
    assert {r.name for r in roots}=={s.task_id for s in tasks.TASKS}
    for r in roots: assert (r/".docs/instructions.md").is_file() and (r/".meta/provenance.json").is_file() and (r/".meta/example.cpp").is_file() and (r/"CMakeLists.txt").is_file()
def test_reference_is_separate_and_has_level_invariants(tmp_path: Path) -> None:
    r=tasks.build(tmp_path)[0];reference=(r/".meta/example.cpp").read_text()
    assert (r/f"{r.name}.cpp").read_text()!=reference
    assert "level_for" in reference and "links_consistent" in reference
