from __future__ import annotations

import argparse
import re
import runpy
import sys


MOONLIGHT_LOCAL_SPEC_ATTENTION_ALIASES = {
    "self_attention.q_layernorm.weight": ["model.layers.{layer_number}.self_attn.q_a_layernorm.weight"],
    "self_attention.kv_layernorm.weight": ["model.layers.{layer_number}.self_attn.kv_a_layernorm.weight"],
}

MOONLIGHT_LOCAL_EXPERT_PATTERN = re.compile(
    r"decoder\.layers\.(\d+)\.mlp\.experts\.local_experts\.(\d+)\.(linear_fc[12])\.weight"
)


def moonlight_local_expert_alias(name: str) -> list[str] | None:
    match = MOONLIGHT_LOCAL_EXPERT_PATTERN.fullmatch(name)
    if not match:
        return None
    layer_number, expert_id, linear_name = match.groups()
    if linear_name == "linear_fc1":
        return [
            f"model.layers.{layer_number}.mlp.experts.{expert_id}.gate_proj.weight",
            f"model.layers.{layer_number}.mlp.experts.{expert_id}.up_proj.weight",
        ]
    return [f"model.layers.{layer_number}.mlp.experts.{expert_id}.down_proj.weight"]


def _patch_mbridge_deepseekv3_import() -> None:
    import slime_plugins.mbridge  # noqa: F401
    from mbridge.models.deepseek_v3 import DeepseekV3Bridge

    original_mlp_mapping = DeepseekV3Bridge._weight_name_mapping_mlp

    def patched_mlp_mapping(self, name: str) -> list[str]:  # type: ignore[no-untyped-def]
        alias = moonlight_local_expert_alias(name)
        if alias is not None:
            return alias
        return original_mlp_mapping(self, name)

    DeepseekV3Bridge._ATTENTION_MAPPING = {
        **DeepseekV3Bridge._ATTENTION_MAPPING,
        **MOONLIGHT_LOCAL_SPEC_ATTENTION_ALIASES,
    }
    DeepseekV3Bridge._weight_name_mapping_mlp = patched_mlp_mapping


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run SLIME HF-to-torch-dist conversion with Moonlight local-spec aliases.",
    )
    parser.add_argument("--slime-root", default="/root/slime")
    parser.add_argument("converter_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.converter_args[:1] == ["--"]:
        args.converter_args = args.converter_args[1:]
    return args


def main() -> None:
    args = parse_args()
    _patch_mbridge_deepseekv3_import()
    converter = f"{args.slime_root}/tools/convert_hf_to_torch_dist.py"
    sys.argv = [converter, *args.converter_args]
    runpy.run_path(converter, run_name="__main__")


if __name__ == "__main__":
    main()
