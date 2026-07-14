from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from w8_biayn.integrations import moonlight_single_sample_sft


EXAMPLE_ROOT = Path("examples/slime/moonlight_cpp_perf")
PREPARE_SCRIPT = EXAMPLE_ROOT / "prepare_single_sample_sft_data.sh"
SFT_SCRIPT = EXAMPLE_ROOT / "sft.sh"
RUNNER = EXAMPLE_ROOT / "moonlight_cpp_perf.sh"


def test_single_sample_builder_writes_expected_manifest_and_jsonl(tmp_path: Path) -> None:
    root = tmp_path / "aider-whole-single"

    paths = moonlight_single_sample_sft.build_dataset(root)

    assert paths.root == root
    assert paths.manifest == root / "manifest.json"
    assert paths.train_jsonl == root / "sft" / "train.jsonl"

    manifest = json.loads(paths.manifest.read_text(encoding="utf-8"))
    assert manifest == moonlight_single_sample_sft.MANIFEST
    assert manifest["kind"] == "single-sample-aider-whole-sft"
    assert manifest["files"]["sft_train"] == "sft/train.jsonl"
    assert manifest["train_count"] == 1

    lines = paths.train_jsonl.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row == moonlight_single_sample_sft.TRAIN_ROW
    assert row["label"] == "aider-whole-format-001"
    assert row["task_id"] == "aider-whole-format-001"
    assert row["metadata"] == {
        "task_id": "aider-whole-format-001",
        "source": "single_sample_for_sft.md",
        "subset": "train",
        "format": "aider-whole",
        "model_family": "moonlight",
        "purpose": "single-sample-sft-smoke",
    }
    assert [message["role"] for message in row["messages"]] == ["user", "assistant"]


def test_single_sample_assistant_message_is_aider_whole_format() -> None:
    response = moonlight_single_sample_sft.TRAIN_ROW["messages"][1]["content"]

    assert "```cpp" not in response
    assert "I have" not in response
    assert response.startswith("leap.h\n```\n")
    assert response.endswith("\n```")
    assert re.fullmatch(
        r"leap\.h\n```\n.+\n```\n\nleap\.cpp\n```\n.+\n```",
        response,
        flags=re.DOTALL,
    )
    assert '#include "leap.h"' in response
    assert "year % 4 == 0" in response


def test_single_sample_builder_is_idempotent_and_refuses_drift(tmp_path: Path) -> None:
    root = tmp_path / "aider-whole-single"
    paths = moonlight_single_sample_sft.build_dataset(root)
    first_train = paths.train_jsonl.read_text(encoding="utf-8")

    moonlight_single_sample_sft.build_dataset(root)
    assert paths.train_jsonl.read_text(encoding="utf-8") == first_train

    paths.train_jsonl.write_text('{"different":true}\n', encoding="utf-8")
    with pytest.raises(FileExistsError, match="pass --force"):
        moonlight_single_sample_sft.build_dataset(root)

    moonlight_single_sample_sft.build_dataset(root, force=True)
    assert paths.train_jsonl.read_text(encoding="utf-8") == first_train


def test_single_sample_sft_wrapper_uses_non_lora_moonlight_lane() -> None:
    script = PREPARE_SCRIPT.read_text(encoding="utf-8")
    sft_script = SFT_SCRIPT.read_text(encoding="utf-8")
    runner = RUNNER.read_text(encoding="utf-8")

    assert os.access(PREPARE_SCRIPT, os.X_OK)
    assert "w8_biayn.integrations.moonlight_single_sample_sft" in script
    assert ".w8-biayn/data/aider-whole-single" in script
    assert "moonlight_lora_cpp_perf" not in script
    assert "SLIME_LORA" not in script
    assert 'exec "${SCRIPT_DIR}/moonlight_cpp_perf.sh" sft "$@"' in sft_script
    assert '--prompt-data "${DATA_DIR}/sft/train.jsonl"' in runner
    assert "--input-key messages" in runner
    assert "--metadata-key metadata" in runner
    assert "--loss-type sft_loss" in runner
    assert "--debug-train-only" in runner
