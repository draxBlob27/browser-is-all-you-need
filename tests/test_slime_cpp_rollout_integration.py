from __future__ import annotations

import asyncio
import importlib
import json
import math
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from w8_biayn.cpp_perf.sandbox import DEFAULT_DOCKER_IMAGE
from w8_biayn.cpp_perf.schema import CppTask


RUN_ENV = "SLIME_CPP_RUN_REAL_REWARD_SMOKE"
BUNDLE_ROOT_ENV = "SLIME_CPP_BUNDLE_ROOT"


def test_slime_cpp_reward_hook_scores_real_bundle_row_with_docker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle_root = _require_real_smoke_bundle()
    _require_docker_ready()

    row = _load_first_train_row(bundle_root)
    task = CppTask.read_json(bundle_root / row["metadata"]["task_path"])
    sample = SimpleNamespace(
        prompt=row["prompt"],
        label=row["label"],
        metadata=row["metadata"],
        response=_strict_model_output(task.oracle_solution),
    )

    monkeypatch.syspath_prepend(str(Path.cwd()))
    module = importlib.import_module("examples.slime.cpp_grpo.cpp_rollout")

    reward = asyncio.run(module.reward_func(SimpleNamespace(slime_cpp_bundle_root=str(bundle_root)), sample))

    assert isinstance(reward, float)
    assert math.isfinite(reward)
    assert reward > 0.0


def _require_real_smoke_bundle() -> Path:
    if os.environ.get(RUN_ENV) != "1":
        pytest.skip(f"set {RUN_ENV}=1 and {BUNDLE_ROOT_ENV}=<bundle> to run the real Docker smoke")

    raw_root = os.environ.get(BUNDLE_ROOT_ENV)
    if not raw_root:
        pytest.fail(f"{RUN_ENV}=1 requires {BUNDLE_ROOT_ENV}=<SLIME C++ bundle root>")

    bundle_root = Path(raw_root).expanduser().resolve()
    train_jsonl = bundle_root / "grpo" / "train.jsonl"
    if not train_jsonl.is_file():
        pytest.fail(f"SLIME C++ train JSONL is missing: {train_jsonl}")
    return bundle_root


def _require_docker_ready() -> None:
    if shutil.which("docker") is None:
        pytest.fail("docker CLI is required for the real SLIME C++ reward smoke")

    version = subprocess.run(["docker", "version"], check=False, capture_output=True, text=True)
    if version.returncode != 0:
        pytest.fail(f"docker daemon is not reachable:\n{version.stderr or version.stdout}")

    image = subprocess.run(
        ["docker", "image", "inspect", DEFAULT_DOCKER_IMAGE],
        check=False,
        capture_output=True,
        text=True,
    )
    if image.returncode != 0:
        pytest.fail(
            f"Docker image {DEFAULT_DOCKER_IMAGE!r} is missing. "
            "Run `uv run w8-biayn cpp harness preflight` before this smoke."
        )


def _load_first_train_row(bundle_root: Path) -> dict[str, object]:
    train_jsonl = bundle_root / "grpo" / "train.jsonl"
    first_line = next((line for line in train_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()), "")
    if not first_line:
        pytest.fail(f"SLIME C++ train JSONL has no rows: {train_jsonl}")
    row = json.loads(first_line)
    if not isinstance(row, dict):
        pytest.fail(f"SLIME C++ train row is not an object: {train_jsonl}")
    metadata = row.get("metadata")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("task_path"), str):
        pytest.fail("SLIME C++ train row must contain metadata.task_path")
    if not isinstance(row.get("prompt"), str):
        pytest.fail("SLIME C++ train row must contain a prompt string")
    if not isinstance(row.get("label"), str):
        pytest.fail("SLIME C++ train row must contain a label string")
    task_path = bundle_root / metadata["task_path"]
    if not task_path.is_file():
        pytest.fail(f"SLIME C++ task JSON referenced by metadata.task_path is missing: {task_path}")
    return row


def _strict_model_output(code: str) -> str:
    return f"<reasoning>Use the task oracle for a reward smoke.</reasoning>\n```cpp\n{code.rstrip()}\n```\n"
