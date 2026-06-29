from __future__ import annotations

import asyncio
import importlib
import importlib.util
import inspect
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from w8_biayn.slime_integration.cpp_reward import SlimeCppRewardError


def _load_cpp_rollout() -> ModuleType:
    path = Path("examples/slime/cpp_grpo/cpp_rollout.py")
    spec = importlib.util.spec_from_file_location("w8_test_cpp_rollout", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cpp_rollout = _load_cpp_rollout()


def test_slime_custom_rm_path_imports_with_repo_root_on_pythonpath(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.syspath_prepend(str(Path.cwd()))

    module = importlib.import_module("examples.slime.cpp_grpo.cpp_rollout")

    assert module.reward_func.__name__ == "reward_func"
    assert inspect.iscoroutinefunction(module.reward_func)


def test_reward_func_scores_sample_with_bridge_and_returns_float(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_score(row: dict[str, Any], model_output: str, *, bundle_root: Path) -> dict[str, Any]:
        calls.append({"row": row, "model_output": model_output, "bundle_root": bundle_root})
        return {"reward": "1.25"}

    monkeypatch.setattr(cpp_rollout, "score_slime_cpp_row", fake_score)
    bundle_root = tmp_path / "slime-cpp"
    sample = SimpleNamespace(
        prompt="rewrite this C++",
        label="accepted",
        response="<reasoning>ok</reasoning>\n```cpp\nint main(){return 0;}\n```",
        metadata={"task_path": "tasks/train/pie_cpp_000001.json", "split": "train"},
    )
    args = SimpleNamespace(slime_cpp_bundle_root=str(bundle_root))

    reward = asyncio.run(cpp_rollout.reward_func(args, sample))

    assert reward == pytest.approx(1.25)
    assert isinstance(reward, float)
    assert calls == [
        {
            "row": {
                "prompt": "rewrite this C++",
                "label": "accepted",
                "metadata": {"task_path": "tasks/train/pie_cpp_000001.json", "split": "train"},
            },
            "model_output": "<reasoning>ok</reasoning>\n```cpp\nint main(){return 0;}\n```",
            "bundle_root": bundle_root.resolve(),
        }
    ]


def test_reward_func_derives_bundle_root_from_prompt_data(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seen_bundle_roots: list[Path] = []

    def fake_score(row: dict[str, Any], model_output: str, *, bundle_root: Path) -> dict[str, Any]:
        seen_bundle_roots.append(bundle_root)
        return {"reward": 0.5}

    monkeypatch.setattr(cpp_rollout, "score_slime_cpp_row", fake_score)
    bundle_root = tmp_path / "slime-cpp"
    sample = SimpleNamespace(
        response="bad output",
        metadata={"task_path": "tasks/train/pie_cpp_000001.json"},
    )
    args = {"prompt_data": str(bundle_root / "grpo" / "train.jsonl")}

    reward = asyncio.run(cpp_rollout.reward_func(args, sample))

    assert reward == pytest.approx(0.5)
    assert seen_bundle_roots == [bundle_root.resolve()]


def test_reward_func_uses_env_bundle_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    seen_bundle_roots: list[Path] = []

    def fake_score(row: dict[str, Any], model_output: str, *, bundle_root: Path) -> dict[str, Any]:
        seen_bundle_roots.append(bundle_root)
        return {"reward": -1.0}

    monkeypatch.setattr(cpp_rollout, "score_slime_cpp_row", fake_score)
    bundle_root = tmp_path / "env-bundle"
    monkeypatch.setenv(cpp_rollout.BUNDLE_ROOT_ENV, str(bundle_root))
    sample = SimpleNamespace(response="", metadata={"task_path": "tasks/train/task.json"})

    reward = asyncio.run(cpp_rollout.reward_func(SimpleNamespace(), sample))

    assert reward == pytest.approx(-1.0)
    assert seen_bundle_roots == [bundle_root.resolve()]


@pytest.mark.parametrize(
    ("sample", "match"),
    [
        (SimpleNamespace(response="", metadata=None), "metadata"),
        (SimpleNamespace(response="", metadata={}), "task_path"),
        (SimpleNamespace(response=None, metadata={"task_path": "tasks/train/task.json"}), "response"),
    ],
)
def test_reward_func_rejects_invalid_sample_shape(sample: SimpleNamespace, match: str) -> None:
    with pytest.raises(SlimeCppRewardError, match=match):
        asyncio.run(cpp_rollout.reward_func(SimpleNamespace(), sample))


def test_reward_func_rejects_non_numeric_bridge_reward(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_score(row: dict[str, Any], model_output: str, *, bundle_root: Path) -> dict[str, Any]:
        return {"reward": object()}

    monkeypatch.setattr(cpp_rollout, "score_slime_cpp_row", fake_score)
    sample = SimpleNamespace(response="", metadata={"task_path": "tasks/train/task.json"})

    with pytest.raises(SlimeCppRewardError, match="non-numeric reward"):
        asyncio.run(cpp_rollout.reward_func(SimpleNamespace(), sample))
