"""SLIME custom reward entrypoint for C++ GRPO rollouts."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from w8_biayn.slime_integration.cpp_reward import SlimeCppRewardError, score_slime_cpp_row


BUNDLE_ROOT_ENV = "SLIME_CPP_BUNDLE_ROOT"


async def reward_func(args: Any, sample: Any, **kwargs: Any) -> float:
    """Score one SLIME Sample with the repo-owned C++ reward bridge."""

    row = _row_from_sample(sample)
    response = _response_from_sample(sample)
    bundle_root = _resolve_bundle_root(args, kwargs)
    result = score_slime_cpp_row(row, response, bundle_root=bundle_root)
    try:
        return float(result["reward"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SlimeCppRewardError("SLIME C++ reward bridge returned a non-numeric reward") from exc


def _row_from_sample(sample: Any) -> dict[str, Any]:
    metadata = getattr(sample, "metadata", None)
    if not isinstance(metadata, Mapping):
        raise SlimeCppRewardError("SLIME Sample.metadata must be a mapping")

    task_path = metadata.get("task_path")
    if not isinstance(task_path, str) or not task_path.strip():
        raise SlimeCppRewardError("SLIME Sample.metadata['task_path'] is required")

    return {
        "prompt": getattr(sample, "prompt", ""),
        "label": getattr(sample, "label", None),
        "metadata": dict(metadata),
    }


def _response_from_sample(sample: Any) -> str:
    response = getattr(sample, "response", None)
    if not isinstance(response, str):
        raise SlimeCppRewardError("SLIME Sample.response must be a string")
    return response


def _resolve_bundle_root(args: Any, kwargs: Mapping[str, Any]) -> Path:
    explicit = kwargs.get("bundle_root")
    if explicit is not None:
        return Path(str(explicit)).expanduser().resolve()

    env_value = os.environ.get(BUNDLE_ROOT_ENV)
    if env_value:
        return Path(env_value).expanduser().resolve()

    for name in ("slime_cpp_bundle_root", "cpp_bundle_root", "bundle_root", "data_dir"):
        value = _arg_value(args, name)
        if value:
            return Path(str(value)).expanduser().resolve()

    prompt_data = _arg_value(args, "prompt_data")
    if prompt_data:
        path = Path(str(prompt_data)).expanduser()
        if path.suffix == ".jsonl":
            parent = path.parent
            if parent.name == "grpo":
                return parent.parent.resolve()
            return parent.resolve()
        return path.resolve()

    return Path.cwd().resolve()


def _arg_value(args: Any, name: str) -> Any:
    if isinstance(args, Mapping):
        return args.get(name)
    return getattr(args, name, None)
