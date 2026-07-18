from __future__ import annotations

import json
from pathlib import Path

from w8_biayn.integrations import moonlight_balanced_search_tree_aider_tasks as balanced


def test_balanced_tree_curriculum_materializes_every_proposed_task(tmp_path: Path) -> None:
    roots = balanced.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {spec.task_id for spec in balanced.TASKS}
    assert "moonlight_binary_search_tree_aider_tasks" not in Path(balanced.__file__).read_text()
    for root in roots:
        task_id = root.name
        config = json.loads((root / ".meta" / "config.json").read_text())
        provenance = json.loads((root / ".meta" / "provenance.json").read_text())
        assert config["source"] == "newly-authored-in-repository"
        assert config["attribution"]
        assert config["files"]["solution"] == [f"{task_id}.h", f"{task_id}.cpp"]
        assert config["files"]["test"] == ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"]
        assert config["files"]["example"] == [".meta/example.h", ".meta/example.cpp"]
        assert provenance["curriculum_path"] == balanced.CURRICULUM
        assert provenance["task_id"] == task_id
        assert provenance["family_id"] == "aider-dsa-balanced-search-tree-v3"
        assert provenance["status"] == "local candidate only; no dataset release"
        assert (root / ".meta" / "task_hidden_test.cpp").exists()
        assert (root / ".meta" / "example.cpp").exists()
