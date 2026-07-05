"""Surface probe for the GLM-4.7 Miles LoRA training model build.

Enabled by ``W8_GLM47_SURFACE_PROBE=1`` via ``sitecustomize``. Intercepts the
``load_checkpoint`` call inside ``miles.backends.megatron_utils.model`` so the
probe sees exactly the model the trainer built (same args, same LoRA transform),
then instead of loading:

* dumps module names for the first decoder layers, MTP block, and all adapters;
* dumps ShardedTensor metadata (replica_id/offsets/shape) for adapter keys;
* runs Megatron's own sharding-integrity validation over the requested state dict;
* writes one JSON report per rank to ``W8_GLM47_PROBE_OUT`` and exits.

No checkpoint is read or written and no training step runs.
"""

from __future__ import annotations

import importlib.abc
import importlib.util
import json
import os
import sys

_TARGET_MODULE = "miles.backends.megatron_utils.model"
_INSTALLED = False


def install_probe() -> None:
    """Install an import hook that wraps load_checkpoint once the Miles model module loads."""

    global _INSTALLED
    if _INSTALLED:
        return
    sys.meta_path.insert(0, _ProbeFinder())
    _INSTALLED = True


class _ProbeFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname != _TARGET_MODULE:
            return None
        sys.meta_path.remove(self)
        try:
            spec = importlib.util.find_spec(fullname)
        finally:
            sys.meta_path.insert(0, self)
        if spec is None or spec.loader is None:
            return None
        spec.loader = _WrappingLoader(spec.loader)
        return spec


class _WrappingLoader(importlib.abc.Loader):
    def __init__(self, wrapped):
        self._wrapped = wrapped

    def create_module(self, spec):
        return self._wrapped.create_module(spec)

    def exec_module(self, module):
        self._wrapped.exec_module(module)
        _wrap_load_checkpoint(module)


def _wrap_load_checkpoint(model_module) -> None:
    original = getattr(model_module, "load_checkpoint", None)
    if original is None:
        return

    def probing_load_checkpoint(model, optimizer, opt_param_scheduler, *args, **kwargs):
        try:
            _run_probe(model)
        except Exception as exc:  # noqa: BLE001 - a probe bug must never wedge the job
            print(f"W8_GLM47_SURFACE_PROBE probe_error={type(exc).__name__}:{exc}", flush=True)
        raise SystemExit(0)

    model_module.load_checkpoint = probing_load_checkpoint


def _module_names(base, prefix: str, limit: int = 60) -> list[str]:
    return [name for name, _ in base.named_modules() if name.startswith(prefix)][:limit]


def _run_probe(model) -> None:
    import torch.distributed as dist
    from megatron.core import parallel_state
    from megatron.core.dist_checkpointing.dict_utils import nested_values
    from megatron.core.dist_checkpointing.mapping import apply_factories
    from megatron.core.dist_checkpointing.validation import (
        determine_global_metadata,
        validate_sharding_integrity,
    )
    from megatron.training.utils import unwrap_model

    rank = dist.get_rank()
    out_dir = os.environ.get("W8_GLM47_PROBE_OUT", "/tmp/w8_glm47_surface_probe")
    os.makedirs(out_dir, exist_ok=True)

    base = unwrap_model(model)[0]
    report = {
        "rank": rank,
        "ep_rank": parallel_state.get_expert_model_parallel_rank(),
        "modules": {
            "layer0_mlp": _module_names(base, "decoder.layers.0.mlp"),
            "layer1_mlp": _module_names(base, "decoder.layers.1.mlp"),
            "layer0_attention": _module_names(base, "decoder.layers.0.self_attention"),
            "mtp": _module_names(base, "mtp"),
        },
        "adapter_modules": [name for name, _ in base.named_modules() if "adapter" in name][:120],
        "adapter_shards": [],
        "validation": None,
    }

    sharded = base.sharded_state_dict(
        metadata={"dp_cp_group": parallel_state.get_data_parallel_group(with_context_parallel=True)}
    )
    apply_factories(sharded)
    shard_entries = [
        value
        for value in nested_values(sharded)
        if hasattr(value, "replica_id") and ".adapter." in getattr(value, "key", "")
    ]
    for value in sorted(shard_entries, key=lambda item: item.key):
        replica = value.replica_id
        report["adapter_shards"].append(
            {
                "key": value.key,
                "replica_id": list(replica) if isinstance(replica, tuple) else replica,
                "global_shape": list(getattr(value, "global_shape", ()) or ()),
                "global_offset": list(getattr(value, "global_offset", ()) or ()),
                "axis_fragmentations": list(getattr(value, "axis_fragmentations", ()) or ()),
            }
        )

    try:
        _, global_metadata = determine_global_metadata(sharded)
        validate_sharding_integrity(global_metadata)
        report["validation"] = "PASS"
    except Exception as exc:  # noqa: BLE001 - verdict capture, rethrowing defeats the probe
        report["validation"] = f"FAIL:{type(exc).__name__}:{exc}"

    report_path = os.path.join(out_dir, f"probe_rank{rank}.json")
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)
    print(f"W8_GLM47_SURFACE_PROBE rank={rank} validation={report['validation']} report={report_path}", flush=True)
