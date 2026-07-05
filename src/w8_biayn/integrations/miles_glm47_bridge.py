from __future__ import annotations

import os
from typing import Any


_REGISTERED = False
_MBRIDGE_PATCHED = False
_SHARED_OUTER_CKPT_PATCHED = False


def register_glm47_bridge() -> None:
    """Register GLM-4.7-Flash Lite with Megatron Bridge inside Miles."""

    _patch_mbridge_glm47_lite()
    _patch_shared_outer_expert_adapter_replication()

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
