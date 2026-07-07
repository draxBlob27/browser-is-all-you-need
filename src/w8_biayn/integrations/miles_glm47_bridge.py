from __future__ import annotations

import os
from typing import Any


_REGISTERED = False
_MBRIDGE_PATCHED = False
_SHARED_OUTER_CKPT_PATCHED = False
_LORA_SYNC_PATCHED = False
_SGLANG_MEM_POOL_PATCHED = False
_ROUTER_CB_PATCHED = False


def register_glm47_bridge() -> None:
    """Register GLM-4.7-Flash Lite with Megatron Bridge inside Miles.

    Installs post-import hooks only — no heavy imports happen here. This runs
    at interpreter startup in every gated process via sitecustomize, including
    Ray's node agents; eagerly importing megatron.bridge/mbridge from those
    agents stalls `ray start` past its node-start deadline. Each patch fires
    right after its target module finishes importing, in processes that
    actually load that module.
    """

    # Legacy mbridge registry: Miles never imports miles_plugins.mbridge on its
    # own, and plugin/registry import order is not fixed, so hook both sides;
    # _MBRIDGE_PATCHED keeps the patch idempotent.
    _when_imported("mbridge.core.bridge", lambda module: _patch_mbridge_glm47_lite())
    _when_imported("miles_plugins.mbridge", lambda module: _patch_mbridge_glm47_lite())
    _when_imported(
        "megatron.bridge.peft.utils",
        lambda module: _patch_shared_outer_expert_adapter_replication(),
    )
    _patch_sglang_lora_sync_skip_mtp()
    _patch_sglang_lora_mem_pool_ordering()
    _patch_router_circuit_breaker()
    _when_imported("megatron.bridge", lambda module: _register_glm47_bridge_class())


def _register_glm47_bridge_class() -> None:
    global _REGISTERED
    if _REGISTERED:
        return

    try:
        import megatron.bridge.models.glm.glm47_flash_bridge  # noqa: F401
    except (ImportError, ModuleNotFoundError):
        pass
    else:
        _REGISTERED = True
        return

    from functools import partial

    from megatron.bridge.models.conversion.mapping_registry import MegatronMappingRegistry
    from megatron.bridge.models.conversion.model_bridge import MegatronModelBridge
    from megatron.bridge.models.gpt_provider import GPTModelProvider
    from megatron.bridge.models.hf_pretrained.causal_lm import PreTrainedCausalLM
    from megatron.bridge.models.mla_provider import MLAModelProvider
    from megatron.core.models.gpt.gpt_layer_specs import get_gpt_decoder_block_spec
    from megatron.core.models.gpt.gpt_model import GPTModel

    try:
        import transformer_engine  # noqa: F401

        have_te = True
    except (ImportError, ModuleNotFoundError):
        have_te = False

    @MegatronModelBridge.register_bridge(
        source="Glm4MoeLiteForCausalLM",
        target=GPTModel,
        provider=MLAModelProvider,
        model_type="glm4_moe_lite",
    )
    class GLM47LiteBridge(MegatronModelBridge):
        """Megatron Bridge provider shim for GLM-4.7-Flash Lite LoRA runs."""

        def provider_bridge(self, hf_pretrained: PreTrainedCausalLM) -> GPTModelProvider:
            provider = super().provider_bridge(hf_pretrained)
            hf_config = hf_pretrained.config

            # The provider's default_layer_spec builds fused-QKV attention and
            # uniform MoE, silently ignoring multi_latent_attention and
            # moe_layer_freq. The heterogeneous block spec honors both.
            provider.transformer_layer_spec = partial(get_gpt_decoder_block_spec, use_transformer_engine=have_te)

            provider.normalization = "RMSNorm"
            provider.gated_linear_unit = True
            provider.add_bias_linear = False
            provider.share_embeddings_and_output_weights = False
            provider.qk_layernorm = True
            provider.multi_latent_attention = True
            provider.mtp_num_layers = getattr(hf_config, "num_nextn_predict_layers", None)
            provider.mtp_loss_scaling_factor = 0.3

            provider.moe_grouped_gemm = True
            provider.moe_router_pre_softmax = True
            provider.moe_token_dispatcher_type = "alltoall"
            provider.moe_router_load_balancing_type = "seq_aux_loss"
            provider.moe_shared_expert_overlap = True
            provider.moe_router_score_function = "sigmoid"
            provider.moe_router_enable_expert_bias = True
            provider.moe_router_dtype = "fp32"
            provider.moe_permute_fusion = True
            provider.moe_router_bias_update_rate = 0
            provider.moe_aux_loss_coeff = 0.0

            provider.hidden_dropout = 0.0
            provider.attention_softmax_in_fp32 = True
            provider.make_vocab_size_divisible_by = 64
            provider.moe_layer_freq = [0] * hf_config.first_k_dense_replace + [1] * (
                hf_config.num_hidden_layers - hf_config.first_k_dense_replace
            )
            provider.moe_shared_expert_intermediate_size = (
                hf_config.moe_intermediate_size * getattr(hf_config, "n_shared_experts", 1)
            )
            provider.rotary_base = getattr(hf_config, "rope_theta", 1000000)
            provider.rotary_scaling_factor = 1.0
            provider.mscale = 1.0
            provider.mscale_all_dim = 1.0

            return provider

        def mapping_registry(self) -> MegatronMappingRegistry:
            mappings = _glm47_base_mappings()
            mappings.extend(_glm47_mtp_mappings(self.hf_config))
            return MegatronMappingRegistry(*mappings)

    _REGISTERED = True


def _patch_mbridge_glm47_lite() -> None:
    """Patch Miles' mbridge GLM converter with GLM-specific QK layernorm names."""

    global _MBRIDGE_PATCHED
    if _MBRIDGE_PATCHED:
        return

    try:
        import miles_plugins.mbridge  # noqa: F401
        from mbridge.core.bridge import _MODEL_REGISTRY
    except (ImportError, ModuleNotFoundError):
        return

    glm_bridge = _MODEL_REGISTRY.get("glm4_moe_lite")
    if glm_bridge is None:
        return

    attention_mapping = dict(getattr(glm_bridge, "_ATTENTION_MAPPING", {}))
    attention_mapping.setdefault(
        "self_attention.linear_qkv.layer_norm_weight",
        ["model.layers.{layer_number}.input_layernorm.weight"],
    )
    glm_bridge._ATTENTION_MAPPING = attention_mapping
    _MBRIDGE_PATCHED = True


def _patch_shared_outer_expert_adapter_replication() -> None:
    """Mark shared-outer expert LoRA tensors as EP-replicated in checkpoint metadata.

    ``SharedOuterGroupedExpertAdapter`` keeps its shared LoRA side bit-identical
    across expert-parallel ranks at runtime (``_make_cross_ep_replicated``), but its
    ``sharded_state_dict`` delegates the shared side to the generic parallel-linear
    path, which stamps the same ``replica_id`` on every EP rank. Megatron's
    sharding-integrity validation then counts EP-world main-replica claims for one
    shard and rejects the whole checkpoint access pattern before any load or save.
    Folding the EP rank into ``replica_id`` leaves exactly one main replica.
    """

    global _SHARED_OUTER_CKPT_PATCHED
    if _SHARED_OUTER_CKPT_PATCHED:
        return
    if os.environ.get("W8_GLM47_NO_SHARED_LORA_CKPT_PATCH", "").strip().lower() in {"1", "true", "yes", "on"}:
        return

    try:
        from megatron.bridge.peft import utils as peft_utils
    except (ImportError, ModuleNotFoundError):
        return

    adapter_cls = getattr(peft_utils, "SharedOuterGroupedExpertAdapter", None)
    if adapter_cls is None or getattr(adapter_cls, "_w8_ep_replica_patched", False):
        return

    original_sharded_state_dict = adapter_cls.sharded_state_dict

    def sharded_state_dict(self, prefix="", sharded_offsets=(), metadata=None):
        sharded = original_sharded_state_dict(self, prefix, sharded_offsets, metadata)
        shared_prefix = f"{prefix}linear_in." if getattr(self, "_is_fc1", True) else f"{prefix}linear_out."
        try:
            from megatron.core import parallel_state

            ep_rank = parallel_state.get_expert_model_parallel_rank()
            ep_world = parallel_state.get_expert_model_parallel_world_size()
        except Exception:
            return sharded
        if ep_world <= 1:
            return sharded
        # Every entry of the shared side is replicated across EP ranks: the
        # weight tensor and TE _extra_state objects alike must carry the EP
        # rank in replica_id or validation sees duplicate main replicas.
        for key, entry in sharded.items():
            if not key.startswith(shared_prefix) or not hasattr(entry, "replica_id"):
                continue
            replica = entry.replica_id
            if isinstance(replica, int):
                entry.replica_id = replica * ep_world + ep_rank
            else:
                replica = tuple(replica)
                if not replica:
                    entry.replica_id = (ep_rank,)
                else:
                    entry.replica_id = (*replica[:-1], replica[-1] * ep_world + ep_rank)
        return sharded

    adapter_cls.sharded_state_dict = sharded_state_dict
    adapter_cls._w8_ep_replica_patched = True
    _SHARED_OUTER_CKPT_PATCHED = True


def _when_imported(module_name: str, callback) -> None:
    """Run callback(module) now if imported, else right after its import completes."""

    import importlib.abc
    import importlib.util
    import sys

    existing = sys.modules.get(module_name)
    if existing is not None:
        callback(existing)
        return

    class _Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname != module_name:
                return None
            sys.meta_path.remove(self)
            spec = importlib.util.find_spec(fullname)
            if spec is None or spec.loader is None:
                return None
            wrapped = spec.loader

            class _Loader(importlib.abc.Loader):
                def create_module(self, spec_inner):
                    return wrapped.create_module(spec_inner)

                def exec_module(self, module):
                    wrapped.exec_module(module)
                    callback(module)

            spec.loader = _Loader()
            return spec

    sys.meta_path.insert(0, _Finder())


def _patch_sglang_lora_sync_skip_mtp() -> None:
    """Keep MTP-layer adapter tensors out of the SGLang LoRA sync payload.

    The trainer exports MTP adapters as HF layer indices >= num_layers (layer 47
    for GLM-4.7-Flash). SGLang serves only the decoder layers and rejects the
    whole adapter with 'index 47 is out of range', which kills rollout weight
    sync. MTP adapters keep training on the Megatron side; generation does not
    execute the MTP head, so dropping them from the rollout payload is lossless.
    """

    global _LORA_SYNC_PATCHED
    if _LORA_SYNC_PATCHED:
        return
    if os.environ.get("W8_GLM47_NO_SGLANG_MTP_FILTER", "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    _LORA_SYNC_PATCHED = True
    _when_imported(
        "miles.backends.megatron_utils.update_weight.update_weight_from_tensor",
        _apply_sglang_lora_mtp_filter,
    )


def _dump_sync_forensics(updater, hf_named_tensors, out_dir) -> None:
    """Per-sync fingerprint of the gathered adapter tensors (W8_GLM47_SYNC_FORENSICS).

    With lr=0 every sync must ship bit-identical tensors; a fingerprint change
    between syncs convicts the trainer side (offload/wake or gather), while
    identical fingerprints with degraded generations convict the engine side.
    """
    import hashlib
    import json
    import os as _os

    try:
        rank = int(_os.environ.get("RANK", "0"))
    except ValueError:
        rank = 0
    _os.makedirs(out_dir, exist_ok=True)
    count = getattr(updater, "_w8_forensic_sync_count", 0) + 1
    updater._w8_forensic_sync_count = count

    entries = {}
    digest = hashlib.sha256()
    for name, tensor in sorted(hf_named_tensors, key=lambda item: item[0]):
        t = tensor.detach().float().cpu()
        entries[name] = {
            "shape": list(t.shape),
            "sum_abs": float(t.abs().sum()),
            "max_abs": float(t.abs().max()) if t.numel() else 0.0,
            "first3": t.flatten()[:3].tolist(),
        }
        digest.update(name.encode())
        digest.update(t.numpy().tobytes())
    payload = {
        "sync": count,
        "rank": rank,
        "n_tensors": len(entries),
        "sha256": digest.hexdigest(),
        "total_sum_abs": sum(e["sum_abs"] for e in entries.values()),
        "tensors": entries,
    }
    path = _os.path.join(out_dir, f"sync{count:02d}_rank{rank}.json")
    with open(path, "w") as fh:
        json.dump(payload, fh)
    print(
        f"w8 sync forensics: sync={count} rank={rank} tensors={len(entries)} "
        f"sha256={payload['sha256'][:16]} total_sum_abs={payload['total_sum_abs']:.3f}",
        flush=True,
    )


def _apply_sglang_lora_mtp_filter(module) -> None:
    import re

    cls = getattr(module, "UpdateWeightFromTensor", None)
    if cls is None or getattr(cls, "_w8_mtp_filter_patched", False):
        return

    original_send = cls._send_lora_params
    layer_pattern = re.compile(r"\.layers\.(\d+)\.")

    def _send_lora_params(self, hf_named_tensors):
        forensics_dir = os.environ.get("W8_GLM47_SYNC_FORENSICS", "").strip()
        if forensics_dir:
            _dump_sync_forensics(self, hf_named_tensors, forensics_dir)
        num_layers = getattr(getattr(self, "args", None), "num_layers", None)
        if num_layers:
            kept = []
            dropped = []
            for name, tensor in hf_named_tensors:
                match = layer_pattern.search(name)
                if match and int(match.group(1)) >= num_layers:
                    dropped.append(name)
                    continue
                kept.append((name, tensor))
            if dropped and kept:
                print(
                    f"w8 GLM47 rollout LoRA sync: dropping {len(dropped)} MTP adapter tensors "
                    f"(hf layer >= {num_layers}), e.g. {dropped[0]}",
                    flush=True,
                )
                hf_named_tensors = kept
        return original_send(self, hf_named_tensors)

    cls._send_lora_params = _send_lora_params

    # Warm starts (--lora-adapter-path) make the SGLang engine pre-load the
    # adapter from disk at boot, but the actor's _lora_loaded flag starts False,
    # so the first tensor sync skips the unload and the engine rejects the load
    # with "already loaded". Mark the adapter as loaded when a warm-start path
    # is configured so Miles' own unload-then-load branch handles the first sync.
    original_init = cls.__init__

    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        if getattr(getattr(self, "args", None), "lora_adapter_path", None) and hasattr(self, "_lora_loaded"):
            self._lora_loaded = True

    cls.__init__ = __init__
    cls._w8_mtp_filter_patched = True


def _patch_router_circuit_breaker() -> None:
    """Disable the sgl-router circuit breaker for single-worker colocated runs.

    Rollout and eval submit hundreds of concurrent requests to a router with
    exactly one worker behind it. The overflow beyond the router's tiny default
    queue (100) fails instantly; ten failures inside the breaker window open the
    circuit, and with no second worker to fail over to every retry sees 503
    "no_available_workers" until Miles' retry budget (~75s) expires and the job
    tears down a perfectly healthy engine. A breaker only makes sense with
    replicas; here it converts a burst into a fatal error. Also widen the queue
    so submission bursts wait instead of failing.
    """

    global _ROUTER_CB_PATCHED
    if _ROUTER_CB_PATCHED:
        return
    if os.environ.get("W8_GLM47_NO_ROUTER_CB_PATCH", "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    _ROUTER_CB_PATCHED = True
    _when_imported("miles.ray.rollout.router_manager", _apply_router_cb_patch)


def _apply_router_cb_patch(module) -> None:
    router_args_cls = getattr(module, "RouterArgs", None)
    if router_args_cls is None or getattr(router_args_cls, "_w8_cb_patched", False):
        return

    original_from_cli_args = router_args_cls.from_cli_args

    def from_cli_args(*args, **kwargs):
        router_args = original_from_cli_args(*args, **kwargs)
        router_args.disable_circuit_breaker = True
        router_args.queue_size = max(4096, int(getattr(router_args, "queue_size", 0) or 0))
        router_args.queue_timeout_secs = max(1800, int(getattr(router_args, "queue_timeout_secs", 0) or 0))
        print(
            "w8 GLM47 router patch: circuit breaker disabled, "
            f"queue_size={router_args.queue_size}, queue_timeout_secs={router_args.queue_timeout_secs}",
            flush=True,
        )
        return router_args

    router_args_cls.from_cli_args = staticmethod(from_cli_args)
    router_args_cls._w8_cb_patched = True


def _patch_sglang_lora_mem_pool_ordering() -> None:
    """Feed per-expert LoRA tensors to SGLang's memory pool before shared ones.

    SGLang's ``LoRAMemoryPool.load_lora_weight_to_buffer`` initializes its
    per-module temp dicts only when the first weight it sees for a module is
    per-expert. Under the shared-outer contract, fc1 ships a shared 3D lora_A
    plus per-expert lora_B; if the shared tensor is iterated first, the
    per-expert branch later re-guards ``temp_B_buffer`` but not
    ``temp_B_cache_keys`` and the scheduler dies with "'NoneType' object does
    not support item assignment". Reordering each layer's weights dict
    per-expert-first makes SGLang's own init path set up all four temp dicts.
    """

    global _SGLANG_MEM_POOL_PATCHED
    if _SGLANG_MEM_POOL_PATCHED:
        return
    if os.environ.get("W8_GLM47_NO_SGLANG_MEMPOOL_ORDER_PATCH", "").strip().lower() in {"1", "true", "yes", "on"}:
        return
    _SGLANG_MEM_POOL_PATCHED = True
    _when_imported("sglang.srt.lora.mem_pool", _apply_sglang_mem_pool_ordering)


def _apply_sglang_mem_pool_ordering(module) -> None:
    import re

    cls = getattr(module, "LoRAMemoryPool", None)
    if cls is None or getattr(cls, "_w8_expert_order_patched", False):
        return

    original_load = cls.load_lora_weight_to_buffer
    per_expert_pattern = re.compile(r"experts\.\d+\.")

    def load_lora_weight_to_buffer(self, uid, buffer_id, lora_adapter, *args, **kwargs):
        for layer in getattr(lora_adapter, "layers", None) or []:
            weights = getattr(layer, "weights", None)
            if not isinstance(weights, dict):
                continue
            per_expert = {n: w for n, w in weights.items() if per_expert_pattern.search(n)}
            if not per_expert or len(per_expert) == len(weights):
                continue
            for name, weight in weights.items():
                if name not in per_expert:
                    per_expert[name] = weight
            layer.weights = per_expert
        return original_load(self, uid, buffer_id, lora_adapter, *args, **kwargs)

    cls.load_lora_weight_to_buffer = load_lora_weight_to_buffer
    cls._w8_expert_order_patched = True
    print("w8 GLM47: SGLang LoRA mem-pool per-expert-first ordering active", flush=True)


def _glm47_base_mappings() -> list[Any]:
    from megatron.bridge.models.conversion.param_mapping import AutoMapping, GatedMLPMapping, QKVMapping

    param_mappings = {
        "embedding.word_embeddings.weight": "model.embed_tokens.weight",
        "decoder.final_layernorm.weight": "model.norm.weight",
        "output_layer.weight": "lm_head.weight",
        "decoder.layers.*.self_attention.linear_qkv.layer_norm_weight": "model.layers.*.input_layernorm.weight",
        "decoder.layers.*.input_layernorm.weight": "model.layers.*.input_layernorm.weight",
        "decoder.layers.*.self_attention.linear_proj.weight": "model.layers.*.self_attn.o_proj.weight",
        "decoder.layers.*.pre_mlp_layernorm.weight": "model.layers.*.post_attention_layernorm.weight",
        "decoder.layers.*.mlp.linear_fc1.layer_norm_weight": "model.layers.*.post_attention_layernorm.weight",
        "decoder.layers.*.self_attention.linear_q_down_proj.weight": "model.layers.*.self_attn.q_a_proj.weight",
        "decoder.layers.*.self_attention.linear_q_up_proj.weight": "model.layers.*.self_attn.q_b_proj.weight",
        "decoder.layers.*.self_attention.linear_q_up_proj.layer_norm_weight": "model.layers.*.self_attn.q_a_layernorm.weight",
        "decoder.layers.*.self_attention.q_layernorm.weight": "model.layers.*.self_attn.q_a_layernorm.weight",
        "decoder.layers.*.self_attention.linear_kv_down_proj.weight": "model.layers.*.self_attn.kv_a_proj_with_mqa.weight",
        "decoder.layers.*.self_attention.linear_kv_up_proj.weight": "model.layers.*.self_attn.kv_b_proj.weight",
        "decoder.layers.*.self_attention.linear_kv_up_proj.layer_norm_weight": (
            "model.layers.*.self_attn.kv_a_layernorm.weight"
        ),
        "decoder.layers.*.self_attention.kv_layernorm.weight": "model.layers.*.self_attn.kv_a_layernorm.weight",
        "decoder.layers.*.mlp.linear_fc2.weight": "model.layers.*.mlp.down_proj.weight",
        "decoder.layers.*.mlp.router.weight": "model.layers.*.mlp.gate.weight",
        "decoder.layers.*.mlp.router.expert_bias": "model.layers.*.mlp.gate.e_score_correction_bias",
        "decoder.layers.*.mlp.shared_experts.router.weight": "model.layers.*.mlp.shared_experts.gate.weight",
        "decoder.layers.*.mlp.shared_experts.linear_fc2.weight": (
            "model.layers.*.mlp.shared_experts.down_proj.weight"
        ),
    }

    mappings: list[Any] = [AutoMapping(megatron_param=k, hf_param=v) for k, v in param_mappings.items()]
    mappings.extend(
        [
            QKVMapping(
                megatron_param="decoder.layers.*.self_attention.linear_qkv.weight",
                q="model.layers.*.self_attn.q_proj.weight",
                k="model.layers.*.self_attn.k_proj.weight",
                v="model.layers.*.self_attn.v_proj.weight",
            ),
            QKVMapping(
                megatron_param="decoder.layers.*.self_attention.linear_qkv.bias",
                q="model.layers.*.self_attn.q_proj.bias",
                k="model.layers.*.self_attn.k_proj.bias",
                v="model.layers.*.self_attn.v_proj.bias",
            ),
            GatedMLPMapping(
                megatron_param="decoder.layers.*.mlp.linear_fc1.weight",
                gate="model.layers.*.mlp.gate_proj.weight",
                up="model.layers.*.mlp.up_proj.weight",
            ),
            GatedMLPMapping(
                megatron_param="decoder.layers.*.mlp.shared_experts.linear_fc1.weight",
                gate="model.layers.*.mlp.shared_experts.gate_proj.weight",
                up="model.layers.*.mlp.shared_experts.up_proj.weight",
            ),
            GatedMLPMapping(
                megatron_param="decoder.layers.*.mlp.experts.linear_fc1.weight*",
                gate="model.layers.*.mlp.experts.*.gate_proj.weight",
                up="model.layers.*.mlp.experts.*.up_proj.weight",
            ),
            AutoMapping(
                megatron_param="decoder.layers.*.mlp.experts.linear_fc2.weight*",
                hf_param="model.layers.*.mlp.experts.*.down_proj.weight",
            ),
        ]
    )
    return mappings


def _glm47_mtp_mappings(hf_config: Any) -> list[Any]:
    from megatron.bridge.models.conversion.param_mapping import AutoMapping, GatedMLPMapping

    num_mtp_layers = getattr(hf_config, "num_nextn_predict_layers", 0) or 0
    num_transformer_layers = hf_config.num_hidden_layers
    mappings: list[Any] = []
    for mtp_layer in range(num_mtp_layers):
        hf_layer = mtp_layer + num_transformer_layers
        for layer_prefix in ("mtp_model_layer", "transformer_layer"):
            megatron_prefix = f"mtp.layers.{mtp_layer}.{layer_prefix}"
            hf_prefix = f"model.layers.{hf_layer}"
            mappings.extend(
                [
                    AutoMapping(
                        megatron_param=f"{megatron_prefix}.input_layernorm.weight",
                        hf_param=f"{hf_prefix}.input_layernorm.weight",
                    ),
                    AutoMapping(
                        megatron_param=f"{megatron_prefix}.self_attention.linear_proj.weight",
                        hf_param=f"{hf_prefix}.self_attn.o_proj.weight",
                    ),
                    AutoMapping(
                        megatron_param=f"{megatron_prefix}.pre_mlp_layernorm.weight",
                        hf_param=f"{hf_prefix}.post_attention_layernorm.weight",
                    ),
                    AutoMapping(
                        megatron_param=f"{megatron_prefix}.self_attention.linear_q_down_proj.weight",
                        hf_param=f"{hf_prefix}.self_attn.q_a_proj.weight",
                    ),
                    AutoMapping(
                        megatron_param=f"{megatron_prefix}.self_attention.linear_q_up_proj.weight",
                        hf_param=f"{hf_prefix}.self_attn.q_b_proj.weight",
                    ),
                    AutoMapping(
                        megatron_param=f"{megatron_prefix}.self_attention.linear_q_up_proj.layer_norm_weight",
                        hf_param=f"{hf_prefix}.self_attn.q_a_layernorm.weight",
                    ),
                    AutoMapping(
                        megatron_param=f"{megatron_prefix}.self_attention.linear_kv_down_proj.weight",
                        hf_param=f"{hf_prefix}.self_attn.kv_a_proj_with_mqa.weight",
                    ),
                    AutoMapping(
                        megatron_param=f"{megatron_prefix}.self_attention.linear_kv_up_proj.weight",
                        hf_param=f"{hf_prefix}.self_attn.kv_b_proj.weight",
                    ),
                    AutoMapping(
                        megatron_param=f"{megatron_prefix}.self_attention.linear_kv_up_proj.layer_norm_weight",
                        hf_param=f"{hf_prefix}.self_attn.kv_a_layernorm.weight",
                    ),
                    AutoMapping(
                        megatron_param=f"{megatron_prefix}.mlp.linear_fc2.weight",
                        hf_param=f"{hf_prefix}.mlp.down_proj.weight",
                    ),
                    AutoMapping(
                        megatron_param=f"{megatron_prefix}.mlp.router.weight",
                        hf_param=f"{hf_prefix}.mlp.gate.weight",
                    ),
                    AutoMapping(
                        megatron_param=f"{megatron_prefix}.mlp.router.expert_bias",
                        hf_param=f"{hf_prefix}.mlp.gate.e_score_correction_bias",
                    ),
                    GatedMLPMapping(
                        megatron_param=f"{megatron_prefix}.mlp.shared_experts.linear_fc1.weight",
                        gate=f"{hf_prefix}.mlp.shared_experts.gate_proj.weight",
                        up=f"{hf_prefix}.mlp.shared_experts.up_proj.weight",
                    ),
                    AutoMapping(
                        megatron_param=f"{megatron_prefix}.mlp.shared_experts.linear_fc2.weight",
                        hf_param=f"{hf_prefix}.mlp.shared_experts.down_proj.weight",
                    ),
                    GatedMLPMapping(
                        megatron_param=f"{megatron_prefix}.mlp.experts.linear_fc1.weight*",
                        gate=f"{hf_prefix}.mlp.experts.*.gate_proj.weight",
                        up=f"{hf_prefix}.mlp.experts.*.up_proj.weight",
                    ),
                    AutoMapping(
                        megatron_param=f"{megatron_prefix}.mlp.experts.linear_fc2.weight*",
                        hf_param=f"{hf_prefix}.mlp.experts.*.down_proj.weight",
                    ),
                ]
            )
    return mappings
