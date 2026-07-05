from __future__ import annotations

from typing import Any


_REGISTERED = False


def register_glm47_bridge() -> None:
    """Register GLM-4.7-Flash Lite with Megatron Bridge inside Miles."""

    global _REGISTERED
    if _REGISTERED:
        return

    from megatron.bridge.models.conversion.mapping_registry import MegatronMappingRegistry
    from megatron.bridge.models.conversion.model_bridge import MegatronModelBridge
    from megatron.bridge.models.conversion.param_mapping import AutoMapping, GatedMLPMapping, QKVMapping
    from megatron.bridge.models.gpt_provider import GPTModelProvider
    from megatron.bridge.models.hf_pretrained.causal_lm import PreTrainedCausalLM
    from megatron.bridge.models.mla_provider import MLAModelProvider
    from megatron.core.models.gpt.gpt_model import GPTModel

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


def _glm47_base_mappings() -> list[Any]:
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
