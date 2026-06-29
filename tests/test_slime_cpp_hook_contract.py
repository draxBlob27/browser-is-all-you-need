from __future__ import annotations

from pathlib import Path

import pytest


SLIME_ROOT = Path(".cache/upstreams/slime")


def _read(relative: str) -> str:
    path = SLIME_ROOT / relative
    if not path.exists():
        pytest.skip("pinned SLIME checkout is absent; run `uv run w8-biayn upstreams clone slime`")
    return path.read_text(encoding="utf-8")


def test_pinned_slime_custom_rm_hook_contract_matches_cpp_plan() -> None:
    rm_hub = _read("slime/rollout/rm_hub/__init__.py")
    sglang_rollout = _read("slime/rollout/sglang_rollout.py")

    assert "rm_function = load_function(args.custom_rm_path)" in rm_hub
    assert "return await rm_function(args, sample, **kwargs)" in rm_hub
    assert "return await rm_function(args, samples, **kwargs)" in rm_hub
    assert "if args.group_rm:" in sglang_rollout
    assert "sample.reward = await async_rm(args, sample)" in sglang_rollout
    assert "rewards = await batched_async_rm(args, group)" in sglang_rollout


def test_pinned_slime_jsonl_loader_preserves_cpp_sample_fields() -> None:
    data_source = _read("slime/rollout/data_source.py")
    data = _read("slime/utils/data.py")
    types = _read("slime/utils/types.py")

    assert "prompt_key=args.input_key" in data_source
    assert "label_key=args.label_key" in data_source
    assert "metadata_key=args.metadata_key" in data_source
    assert "metadata = data.get(metadata_key) or {}" in data
    assert "prompt=output_prompt" in data
    assert "label=data[label_key] if label_key is not None else None" in data
    assert "metadata=metadata" in data
    assert "response: str = \"\"" in types
    assert "metadata: dict = field(default_factory=dict)" in types


def test_cpp_grpo_contract_note_documents_first_supported_mode() -> None:
    readme = Path("examples/slime/cpp_grpo/README.md").read_text(encoding="utf-8")

    assert "--custom-rm-path" in readme
    assert "async def reward_func(args, sample, **kwargs) -> float" in readme
    assert "sample.response" in readme
    assert 'sample.metadata["task_path"]' in readme
    assert "not `--group-rm`" in readme
