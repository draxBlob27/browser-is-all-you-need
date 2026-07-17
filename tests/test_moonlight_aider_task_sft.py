from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from w8_biayn.integrations import (
    moonlight_aider_task_eval,
    moonlight_aider_task_sft,
    moonlight_leap_aider_task,
)


WRAPPER = Path("examples/slime/moonlight_cpp_perf/prepare_leap_aider_sft_data.sh")


def test_aider_task_sft_builder_writes_leap_training_row(tmp_path: Path) -> None:
    task_root = tmp_path / "leap"
    out = tmp_path / "aider-leap-sft"
    moonlight_leap_aider_task.build_task(task_root)

    paths = moonlight_aider_task_sft.build_dataset(
        task_dir=task_root,
        out=out,
        task_id="leap",
        label="leap",
        source="aider-tasks/aider-dsa/leap",
    )

    assert paths.root == out
    assert paths.manifest == out / "manifest.json"
    assert paths.train_jsonl == out / "sft" / "train.jsonl"

    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    assert manifest["kind"] == "aider-task-whole-sft"
    assert manifest["task_id"] == "leap"
    assert manifest["label"] == "leap"
    assert manifest["train_count"] == 1
    assert manifest["editable_files"] == ["leap.h", "leap.cpp"]
    assert manifest["example_files"] == [".meta/example.h", ".meta/example.cpp"]
    assert manifest["files"]["sft_train"] == "sft/train.jsonl"

    rows = paths.train_jsonl.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row["label"] == "leap"
    assert row["task_id"] == "leap"
    assert row["metadata"] == {
        "format": "aider-whole",
        "model_family": "moonlight",
        "purpose": "aider-task-sft",
        "source": "aider-tasks/aider-dsa/leap",
        "subset": "train",
        "task_id": "leap",
    }
    assert [message["role"] for message in row["messages"]] == ["user", "assistant"]

    prompt = row["messages"][0]["content"]
    expected_prompt = moonlight_aider_task_eval.build_prompt(moonlight_aider_task_eval.load_task(task_root))
    assert prompt == expected_prompt
    assert "leap_test.cpp" not in prompt
    assert ".meta/example" not in prompt
    assert "bool is_leap_year" not in prompt

    response = row["messages"][1]["content"]
    assert response.startswith("leap.h\n```\n")
    assert "\n\nleap.cpp\n```\n" in response
    assert "```cpp" not in response
    assert "bool is_leap_year(int year)" in response
    assert "year % 4 == 0" in response


def test_aider_task_sft_builder_requires_example_files(tmp_path: Path) -> None:
    task_root = tmp_path / "leap"
    moonlight_leap_aider_task.build_task(task_root)
    config_path = task_root / ".meta" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["files"].pop("example")
    config_path.write_text(json.dumps(config), encoding="utf-8")

    with pytest.raises(moonlight_aider_task_eval.TaskEvalError, match="files.example"):
        moonlight_aider_task_sft.build_dataset(task_dir=task_root, out=tmp_path / "out")


def test_aider_task_sft_builder_is_idempotent_and_refuses_drift(tmp_path: Path) -> None:
    task_root = tmp_path / "leap"
    out = tmp_path / "aider-leap-sft"
    moonlight_leap_aider_task.build_task(task_root)
    paths = moonlight_aider_task_sft.build_dataset(task_dir=task_root, out=out)
    first_train = paths.train_jsonl.read_text(encoding="utf-8")

    moonlight_aider_task_sft.build_dataset(task_dir=task_root, out=out)
    assert paths.train_jsonl.read_text(encoding="utf-8") == first_train

    paths.train_jsonl.write_text('{"different":true}\n', encoding="utf-8")
    with pytest.raises(FileExistsError, match="pass --force"):
        moonlight_aider_task_sft.build_dataset(task_dir=task_root, out=out)

    moonlight_aider_task_sft.build_dataset(task_dir=task_root, out=out, force=True)
    assert paths.train_jsonl.read_text(encoding="utf-8") == first_train


def test_prepare_leap_aider_sft_wrapper_is_documented() -> None:
    assert WRAPPER.exists()
    assert os.access(WRAPPER, os.X_OK)
    wrapper_text = WRAPPER.read_text(encoding="utf-8")
    assert "moonlight_aider_task_sft" in wrapper_text
    assert ".w8-biayn/data/aider-tasks/aider-dsa/leap" in wrapper_text
    assert ".w8-biayn/data/aider-leap-sft" in wrapper_text

    for path in (
        Path("README.md"),
        Path("ROADMAP.md"),
        Path("examples/slime/moonlight_cpp_perf/README.md"),
        Path(".agents/REPO_GUIDE.md"),
        Path(".agents/skills/w8-biayn-framework/SKILL.md"),
    ):
        text = path.read_text(encoding="utf-8")
        assert "prepare_leap_aider_sft_data.sh" in text
        assert ".w8-biayn/data/aider-leap-sft" in text
