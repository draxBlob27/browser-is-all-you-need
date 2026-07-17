from __future__ import annotations

import json
from pathlib import Path

from w8_biayn.integrations import moonlight_balanced_search_tree_aider_tasks as balanced


def test_balanced_tree_curriculum_materializes_every_proposed_task(tmp_path: Path) -> None:
    roots = balanced.build(tmp_path)
    assert len(roots) == 20
    assert {root.name for root in roots} == {spec.task_id for spec in balanced.TASKS}
    for root in roots:
        provenance = json.loads((root / ".meta" / "provenance.json").read_text())
        assert provenance["tree_curriculum"] in {"AVL", "red-black"}
        assert provenance["status"] == "local task artifact; not admitted SFT data"
        assert (root / ".meta" / "task_hidden_test.cpp").exists()
        assert (root / ".meta" / "example.cpp").exists()
