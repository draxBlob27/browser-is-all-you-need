# SLIME C++ GRPO

This directory contains the repo-owned runtime glue for the experimental SLIME
C++ GRPO side lane. It must stay aligned with the pinned SLIME checkout under
`.cache/upstreams/slime`.

## Reward Hook Contract

Use SLIME's `--custom-rm-path` hook for C++ reward scoring. The first C++ smoke
must use per-sample reward mode, not `--group-rm`.

The per-sample hook must expose:

```python
async def reward_func(args, sample, **kwargs) -> float:
    ...
```

The hook receives a SLIME `Sample` with:

- `sample.response`: model-generated text to score.
- `sample.label`: copied from the JSONL `label` field.
- `sample.metadata`: copied from the JSONL `metadata` field.

For C++ bundles, `sample.metadata["task_path"]` points at the copied task JSON.
The reward hook should resolve that path against the local bundle root, call
`w8_biayn.slime_integration.cpp_reward.score_slime_cpp_row(...)`, and return the
scalar reward.

Do not enable `--group-rm` until the per-sample C++ reward smoke passes. In
group mode, SLIME calls the same custom reward path with `list[Sample]` and
expects `list[float]`.
