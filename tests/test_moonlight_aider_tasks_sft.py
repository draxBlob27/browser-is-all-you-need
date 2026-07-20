from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from w8_biayn.cli import app
from w8_biayn.integrations.moonlight_aider_tasks_sft import (
    build_dataset,
    verify_dataset,
)


def _write_reference(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "label": "reference",
        "messages": [
            {"role": "user", "content": "prompt"},
            {"role": "assistant", "content": "answer"},
        ],
        "metadata": {
            "purpose": "reference-family",
            "subset": "train",
            "task_id": "reference",
        },
        "task_id": "reference",
    }
    path.write_text(json.dumps(row, separators=(",", ":")) + "\n", encoding="utf-8")
    return path


def _write_task(tasks_root: Path, family_type: str, family: str, task_id: str) -> Path:
    task = tasks_root / family_type / family / task_id
    (task / ".docs").mkdir(parents=True)
    (task / ".meta").mkdir()
    (task / ".docs" / "introduction.md").write_text("intro\n", encoding="utf-8")
    (task / ".docs" / "instructions.md").write_text("instructions\n", encoding="utf-8")
    (task / f"{task_id}.h").write_text("#pragma once\n", encoding="utf-8")
    (task / f"{task_id}.cpp").write_text(
        f'#include "{task_id}.h"\n', encoding="utf-8"
    )
    (task / ".meta" / "example.h").write_text("#pragma once\n", encoding="utf-8")
    (task / ".meta" / "example.cpp").write_text(
        f'#include "{task_id}.h"\nint solved = 1;\n', encoding="utf-8"
    )
    (task / ".meta" / "config.json").write_text(
        json.dumps({
            "files": {
                "solution": [f"{task_id}.h", f"{task_id}.cpp"],
                "example": [".meta/example.h", ".meta/example.cpp"],
            }
        }),
        encoding="utf-8",
    )
    return task


def test_build_dataset_matches_reference_row_shape(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task(tasks_root, "aider-dsa", "demo-family", "demo-task")
    reference = _write_reference(tmp_path / "reference.jsonl")
    out = tmp_path / "out"

    paths = build_dataset(
        tasks_root=tasks_root, out=out, reference=reference
    )

    row = json.loads(paths.train_jsonl.read_text(encoding="utf-8"))
    assert set(row) == {"label", "messages", "metadata", "task_id"}
    assert row["task_id"] == "demo-task"
    assert row["metadata"] == {
        "purpose": "demo-family",
        "subset": "train",
        "task_id": "demo-task",
    }
    assert [message["role"] for message in row["messages"]] == ["user", "assistant"]
    assert ".meta/example" not in row["messages"][0]["content"]
    assert "int solved = 1" in row["messages"][1]["content"]
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    assert manifest["train_count"] == 1
    assert manifest["family_count"] == 1
    assert manifest["projection_status"] == (
        "user_requested_local_projection_not_dataset_release"
    )
    assert verify_dataset(tasks_root=tasks_root, out=out, reference=reference)["status"] == "pass"


def test_excludes_state_controls_and_qualifies_real_id_collisions(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task(tasks_root, "aider-dsa", "family-a", "same-task")
    _write_task(tasks_root, "aider-dsa", "family-b", "same-task")
    _write_task(tasks_root / "aider-dsa" / "family-a" / ".state", "controls", "clone", "control-task")
    reference = _write_reference(tmp_path / "reference.jsonl")

    paths = build_dataset(
        tasks_root=tasks_root, out=tmp_path / "out", reference=reference
    )
    rows = [json.loads(line) for line in paths.train_jsonl.read_text().splitlines()]
    assert [row["task_id"] for row in rows] == [
        "aider-dsa--family-a--same-task",
        "aider-dsa--family-b--same-task",
    ]
    assert all(row["task_id"] != "control-task" for row in rows)
    result = verify_dataset(
        tasks_root=tasks_root, out=tmp_path / "out", reference=reference
    )
    assert result["train_count"] == 2
    assert result["collision_qualified_row_count"] == 2
    assert result["private_state_excluded"] is True


def test_verify_rejects_output_drift(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task(tasks_root, "aider-dsa", "family", "task")
    reference = _write_reference(tmp_path / "reference.jsonl")
    paths = build_dataset(
        tasks_root=tasks_root, out=tmp_path / "out", reference=reference
    )
    paths.train_jsonl.write_text('{"different":true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="does not exactly match"):
        verify_dataset(
            tasks_root=tasks_root, out=tmp_path / "out", reference=reference
        )


def test_reference_shape_fails_closed(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task(tasks_root, "aider-dsa", "family", "task")
    reference = tmp_path / "reference.jsonl"
    reference.write_text('{"messages":[]}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="row keys differ"):
        build_dataset(
            tasks_root=tasks_root, out=tmp_path / "out", reference=reference
        )


def test_private_prompt_markers_fail_closed(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task = _write_task(tasks_root, "aider-dsa", "family", "task")
    (task / ".docs" / "instructions.md").write_text(
        "Read .meta/example.cpp to solve this task.\n", encoding="utf-8"
    )
    reference = _write_reference(tmp_path / "reference.jsonl")
    with pytest.raises(ValueError, match="private prompt markers remain"):
        build_dataset(
            tasks_root=tasks_root, out=tmp_path / "out", reference=reference
        )


def test_known_balanced_tree_maintenance_appendix_is_recorded_and_removed(
    tmp_path: Path,
) -> None:
    tasks_root = tmp_path / "tasks"
    task = _write_task(
        tasks_root, "aider-dsa", "balanced-search-tree", "rb-last-task"
    )
    (task / ".docs" / "instructions.md").write_text(
        "Public rules.\n\n"
        "## C. Deterministic build, metadata, and admission implementation\n\n"
        "Inspect `.meta/config.json` and CMakeLists.txt.\n\n"
        "The index must own a real RB tree.\n",
        encoding="utf-8",
    )
    reference = _write_reference(tmp_path / "reference.jsonl")
    paths = build_dataset(
        tasks_root=tasks_root, out=tmp_path / "out", reference=reference
    )
    row = json.loads(paths.train_jsonl.read_text(encoding="utf-8"))
    prompt = row["messages"][0]["content"]
    assert "Public rules." in prompt
    assert "The index must own a real RB tree." in prompt
    assert ".meta/config.json" not in prompt
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    assert manifest["prompt_boundary"]["sanitized_row_count"] == 1
    assert manifest["inventory"][0]["prompt_sanitizations"] == [
        "balanced_tree_owner_spec_appendix_removed"
    ]


def test_repo_cli_builds_and_verifies_projection(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task(tasks_root, "aider-dsa", "family", "task")
    reference = _write_reference(tmp_path / "reference.jsonl")
    out = tmp_path / "out"
    runner = CliRunner()
    built = runner.invoke(
        app,
        [
            "data", "aider-tasks-sft", "build",
            "--tasks-root", str(tasks_root),
            "--out", str(out),
            "--reference", str(reference),
        ],
    )
    assert built.exit_code == 0, built.output
    assert '"train_count": 1' in built.output
    verified = runner.invoke(
        app,
        [
            "data", "aider-tasks-sft", "verify",
            "--tasks-root", str(tasks_root),
            "--root", str(out),
            "--reference", str(reference),
        ],
    )
    assert verified.exit_code == 0, verified.output
    assert '"row_shape_matches_reference": true' in verified.output
