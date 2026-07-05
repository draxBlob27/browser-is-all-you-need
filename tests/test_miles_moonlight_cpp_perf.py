from __future__ import annotations

import os
import subprocess
import sys
import types
from pathlib import Path


EXAMPLE_ROOT = Path("examples/miles")
SFT_RUNNER = EXAMPLE_ROOT / "moonlight_cpp_perf_lora_r16_sft.sh"
GRPO_RUNNER = EXAMPLE_ROOT / "moonlight_cpp_perf_lora_r16_grpo.sh"
GLM47_SFT_RUNNER = EXAMPLE_ROOT / "glm47_cpp_perf_lora_r16_sft.sh"
GLM47_GRPO_RUNNER = EXAMPLE_ROOT / "glm47_cpp_perf_lora_r16_grpo.sh"


def test_miles_moonlight_lora_r16_scripts_are_present_and_executable() -> None:
    for script in (SFT_RUNNER, GRPO_RUNNER, GLM47_SFT_RUNNER, GLM47_GRPO_RUNNER):
        assert script.exists(), script
        assert os.access(script, os.X_OK), script


def test_miles_moonlight_lora_r16_scripts_are_bash_syntax_valid() -> None:
    for script in (SFT_RUNNER, GRPO_RUNNER, GLM47_SFT_RUNNER, GLM47_GRPO_RUNNER):
        subprocess.run(["bash", "-n", str(script)], check=True)


def test_miles_grpo_defaults_match_2048_follow_up_profile() -> None:
    text = GRPO_RUNNER.read_text(encoding="utf-8")

    assert 'SEQ_LENGTH="${MILES_SEQ_LENGTH:-2048}"' in text
    assert 'ROLLOUT_MAX_RESPONSE_LEN="${MILES_ROLLOUT_MAX_RESPONSE_LEN:-1024}"' in text
    assert 'EVAL_MAX_RESPONSE_LEN="${MILES_EVAL_MAX_RESPONSE_LEN:-1536}"' in text
    assert "seq_length=${SEQ_LENGTH}" in text
    assert "rollout_max_response_len=${ROLLOUT_MAX_RESPONSE_LEN}" in text
    assert "eval_max_response_len=${EVAL_MAX_RESPONSE_LEN}" in text
    assert "run_receipt.txt" in text


def test_miles_sft_defaults_share_the_2048_sequence_profile() -> None:
    text = SFT_RUNNER.read_text(encoding="utf-8")

    assert 'SEQ_LENGTH="${MILES_SEQ_LENGTH:-2048}"' in text
    assert (
        'SFT_ROLLOUT_FUNCTION_PATH="${MILES_SFT_ROLLOUT_FUNCTION_PATH:-miles.rollout.sft_rollout.generate_rollout}"'
        in text
    )
    assert "--rollout-function-path \"${SFT_ROLLOUT_FUNCTION_PATH}\"" in text
    assert "seq_length=${SEQ_LENGTH}" in text
    assert "sft_rollout_function_path=${SFT_ROLLOUT_FUNCTION_PATH}" in text
    assert 'TRAIN_ENTRYPOINT=(python3 train.py)' in text
    assert 'TRAIN_ENTRYPOINT=(python3 -m "${TRAIN_MODULE}")' in text
    assert "run_receipt.txt" in text


def test_miles_moonlight_runners_accept_model_args_overrides() -> None:
    for script in (SFT_RUNNER, GRPO_RUNNER):
        text = script.read_text(encoding="utf-8")
        assert 'MODEL_ARGS_FILE="${MILES_MODEL_ARGS_FILE:-moonlight.sh}"' in text
        assert 'MODEL_ARGS_PATH="${MILES_MODEL_ARGS_PATH:-${MILES_ROOT}/scripts/models/${MODEL_ARGS_FILE}}"' in text
        assert 'source "${MODEL_ARGS_PATH}"' in text
        assert 'SGLANG_LORA_TARGET_MODULES="${MILES_SGLANG_LORA_TARGET_MODULES:-${LORA_TARGET_MODULES}}"' in text
        assert 'read -r -a SGLANG_LORA_TARGET_MODULE_ARGS <<< "${SGLANG_LORA_TARGET_MODULES//,/ }"' in text
        assert '--sglang-lora-target-modules "${SGLANG_LORA_TARGET_MODULE_ARGS[@]}"' in text
    grpo_text = GRPO_RUNNER.read_text(encoding="utf-8")
    assert 'APPLY_CHAT_TEMPLATE_KWARGS="${MILES_APPLY_CHAT_TEMPLATE_KWARGS:-}"' in grpo_text
    assert 'ROLLOUT_ARGS+=(--apply-chat-template-kwargs "${APPLY_CHAT_TEMPLATE_KWARGS}")' in grpo_text
    assert 'TRAIN_ENTRYPOINT=(python3 train.py)' in grpo_text
    assert 'TRAIN_ENTRYPOINT=(python3 -m "${TRAIN_MODULE}")' in grpo_text


def test_miles_glm47_wrappers_select_glm_defaults() -> None:
    for script in (GLM47_SFT_RUNNER, GLM47_GRPO_RUNNER):
        text = script.read_text(encoding="utf-8")
        assert 'MILES_MODEL_ARGS_FILE="${MILES_MODEL_ARGS_FILE:-glm4.7-flash.sh}"' in text
        assert 'MILES_HF_CHECKPOINT="${MILES_HF_CHECKPOINT:-/root/models/GLM-4.7-Flash}"' in text
        assert "q_a_proj,kv_a_proj_with_mqa,o_proj,gate_proj,up_proj,down_proj" in text
        assert 'MILES_REF_LOAD_DIR="${MILES_REF_LOAD_DIR:-${MILES_HF_CHECKPOINT}_torch_dist_tp4_pp1}"' in text
        assert 'MILES_TENSOR_MODEL_PARALLEL_SIZE="${MILES_TENSOR_MODEL_PARALLEL_SIZE:-4}"' in text
        assert 'MILES_PIPELINE_MODEL_PARALLEL_SIZE="${MILES_PIPELINE_MODEL_PARALLEL_SIZE:-1}"' in text
        assert 'MILES_EXPERT_MODEL_PARALLEL_SIZE="${MILES_EXPERT_MODEL_PARALLEL_SIZE:-4}"' in text
        assert 'MILES_EXPERTS_SHARED_OUTER_LORAS="${MILES_EXPERTS_SHARED_OUTER_LORAS:-1}"' in text
        assert 'MILES_LORA_BASE_CPU_BACKUP="${MILES_LORA_BASE_CPU_BACKUP:-1}"' in text
        assert 'MILES_NO_GRADIENT_ACCUMULATION_FUSION="${MILES_NO_GRADIENT_ACCUMULATION_FUSION:-1}"' in text
        assert 'MILES_SGLANG_LORA_USE_VIRTUAL_EXPERTS="${MILES_SGLANG_LORA_USE_VIRTUAL_EXPERTS:-1}"' in text
        assert 'MILES_WANDB_PROJECT="${MILES_WANDB_PROJECT:-glm47-pie-cpp-posttraining}"' in text
        assert (
            'MILES_TRAIN_MODULE="${MILES_TRAIN_MODULE:-w8_biayn.integrations.miles_train_with_glm47_bridge}"'
            in text
        )
        assert 'W8_REGISTER_GLM47_BRIDGE="${W8_REGISTER_GLM47_BRIDGE:-1}"' in text
    sft_text = GLM47_SFT_RUNNER.read_text(encoding="utf-8")
    assert '"W8_REGISTER_GLM47_BRIDGE",' in SFT_RUNNER.read_text(encoding="utf-8")
    assert "W8_REGISTER_GLM47_BRIDGE" in sft_text
    assert '\\"W8_REGISTER_GLM47_BRIDGE\\": \\"${W8_REGISTER_GLM47_BRIDGE:-}\\"' in GRPO_RUNNER.read_text(
        encoding="utf-8"
    )
    grpo_text = GLM47_GRPO_RUNNER.read_text(encoding="utf-8")
    assert (
        'MILES_APPLY_CHAT_TEMPLATE_KWARGS="${MILES_APPLY_CHAT_TEMPLATE_KWARGS:-{\\"enable_thinking\\": false}}"'
        in grpo_text
    )


def test_glm47_bridge_patches_mbridge_qk_layernorm_mapping(monkeypatch) -> None:
    from w8_biayn.integrations import miles_glm47_bridge

    class FakeGLMBridge:
        _ATTENTION_MAPPING = {
            "self_attention.linear_proj.weight": [
                "model.layers.{layer_number}.self_attn.o_proj.weight"
            ],
        }

    fake_bridge_module = types.ModuleType("mbridge.core.bridge")
    fake_bridge_module._MODEL_REGISTRY = {"glm4_moe_lite": FakeGLMBridge}

    monkeypatch.setattr(miles_glm47_bridge, "_MBRIDGE_PATCHED", False)
    monkeypatch.setitem(sys.modules, "miles_plugins", types.ModuleType("miles_plugins"))
    monkeypatch.setitem(sys.modules, "miles_plugins.mbridge", types.ModuleType("miles_plugins.mbridge"))
    monkeypatch.setitem(sys.modules, "mbridge", types.ModuleType("mbridge"))
    monkeypatch.setitem(sys.modules, "mbridge.core", types.ModuleType("mbridge.core"))
    monkeypatch.setitem(sys.modules, "mbridge.core.bridge", fake_bridge_module)

    miles_glm47_bridge._patch_mbridge_glm47_lite()

    assert FakeGLMBridge._ATTENTION_MAPPING["self_attention.linear_qkv.layer_norm_weight"] == [
        "model.layers.{layer_number}.input_layernorm.weight"
    ]
