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
GLM47_H100_SFT_RUNNER = EXAMPLE_ROOT / "glm47_cpp_perf_lora_r16_h100_sft.sh"
GLM47_H100_GRPO_RUNNER = EXAMPLE_ROOT / "glm47_cpp_perf_lora_r16_h100_grpo.sh"
GLM47_H100_CONVERTER = EXAMPLE_ROOT / "glm47_h100_convert_tp4_pp1_ep8.sh"
MILES_SCRIPTS = (
    SFT_RUNNER,
    GRPO_RUNNER,
    GLM47_SFT_RUNNER,
    GLM47_GRPO_RUNNER,
    GLM47_H100_SFT_RUNNER,
    GLM47_H100_GRPO_RUNNER,
    GLM47_H100_CONVERTER,
)


def test_miles_moonlight_lora_r16_scripts_are_present_and_executable() -> None:
    for script in MILES_SCRIPTS:
        assert script.exists(), script
        assert os.access(script, os.X_OK), script


def test_miles_moonlight_lora_r16_scripts_are_bash_syntax_valid() -> None:
    for script in MILES_SCRIPTS:
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
        assert 'MILES_EXPERT_TENSOR_PARALLEL_SIZE="${MILES_EXPERT_TENSOR_PARALLEL_SIZE:-1}"' in text
        assert 'MILES_MOE_TOKEN_DISPATCHER_TYPE="${MILES_MOE_TOKEN_DISPATCHER_TYPE:-alltoall}"' in text
        assert 'MILES_ATTENTION_BACKEND="${MILES_ATTENTION_BACKEND:-flash}"' in text
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
    sft_runner_text = SFT_RUNNER.read_text(encoding="utf-8")
    grpo_runner_text = GRPO_RUNNER.read_text(encoding="utf-8")
    assert '"W8_REGISTER_GLM47_BRIDGE",' in sft_runner_text
    assert "W8_REGISTER_GLM47_BRIDGE" in sft_text
    assert '\\"W8_REGISTER_GLM47_BRIDGE\\": \\"${W8_REGISTER_GLM47_BRIDGE:-}\\"' in grpo_runner_text
    for probe_key in ("W8_GLM47_SURFACE_PROBE", "W8_GLM47_PROBE_OUT", "W8_GLM47_NO_SHARED_LORA_CKPT_PATCH"):
        assert f'"{probe_key}",' in sft_runner_text
        assert f'\\"{probe_key}\\": \\"${{{probe_key}:-}}\\"' in grpo_runner_text
    grpo_text = GLM47_GRPO_RUNNER.read_text(encoding="utf-8")
    assert (
        'MILES_APPLY_CHAT_TEMPLATE_KWARGS="${MILES_APPLY_CHAT_TEMPLATE_KWARGS:-{\\"enable_thinking\\": false}}"'
        in grpo_text
    )


def test_miles_glm47_h100_wrappers_select_fast_8x_h100_defaults() -> None:
    for script in (GLM47_H100_SFT_RUNNER, GLM47_H100_GRPO_RUNNER):
        text = script.read_text(encoding="utf-8")
        assert 'MILES_MODEL_ARGS_FILE="${MILES_MODEL_ARGS_FILE:-glm4.7-flash.sh}"' in text
        assert 'MILES_HF_CHECKPOINT="${MILES_HF_CHECKPOINT:-/root/models/GLM-4.7-Flash}"' in text
        assert 'MILES_REF_LOAD_DIR="${MILES_REF_LOAD_DIR:-${MILES_HF_CHECKPOINT}_torch_dist_tp4_pp1_ep8}"' in text
        assert 'MILES_GPUS_PER_NODE="${MILES_GPUS_PER_NODE:-8}"' in text
        assert 'MILES_TENSOR_MODEL_PARALLEL_SIZE="${MILES_TENSOR_MODEL_PARALLEL_SIZE:-4}"' in text
        assert 'MILES_PIPELINE_MODEL_PARALLEL_SIZE="${MILES_PIPELINE_MODEL_PARALLEL_SIZE:-1}"' in text
        assert 'MILES_CONTEXT_PARALLEL_SIZE="${MILES_CONTEXT_PARALLEL_SIZE:-1}"' in text
        assert 'MILES_EXPERT_MODEL_PARALLEL_SIZE="${MILES_EXPERT_MODEL_PARALLEL_SIZE:-8}"' in text
        assert 'MILES_EXPERT_TENSOR_PARALLEL_SIZE="${MILES_EXPERT_TENSOR_PARALLEL_SIZE:-1}"' in text
        assert 'MILES_SEQ_LENGTH="${MILES_SEQ_LENGTH:-4096}"' in text
        assert 'MILES_MAX_TOKENS_PER_GPU="${MILES_MAX_TOKENS_PER_GPU:-24576}"' in text
        assert 'MILES_RECOMPUTE_GRANULARITY="${MILES_RECOMPUTE_GRANULARITY:-selective}"' in text
        assert 'MILES_MOE_TOKEN_DISPATCHER_TYPE="${MILES_MOE_TOKEN_DISPATCHER_TYPE:-flex}"' in text
        assert 'MILES_MOE_ENABLE_DEEPEP="${MILES_MOE_ENABLE_DEEPEP:-1}"' in text
        assert 'NVSHMEM_DISABLE_NCCL="${NVSHMEM_DISABLE_NCCL:-1}"' in text
        assert 'MILES_ATTENTION_BACKEND="${MILES_ATTENTION_BACKEND:-flash}"' in text
        assert 'MILES_SGLANG_ENABLE_DP_ATTENTION="${MILES_SGLANG_ENABLE_DP_ATTENTION:-1}"' in text
        assert 'MILES_SGLANG_DP_SIZE="${MILES_SGLANG_DP_SIZE:-8}"' in text
        assert 'MILES_SGLANG_ENABLE_DP_LM_HEAD="${MILES_SGLANG_ENABLE_DP_LM_HEAD:-1}"' in text
        assert 'MILES_SGLANG_MOE_DENSE_TP_SIZE="${MILES_SGLANG_MOE_DENSE_TP_SIZE:-1}"' in text
        # Speculative decoding is opt-in until SGLang LoRA + EAGLE is proven.
        assert 'MILES_SGLANG_SPECULATIVE="${MILES_SGLANG_SPECULATIVE:-0}"' in text
        # Custom allreduce stays on for NVLink nodes.
        assert 'MILES_SGLANG_DISABLE_CUSTOM_ALL_REDUCE="${MILES_SGLANG_DISABLE_CUSTOM_ALL_REDUCE:-0}"' in text
        assert 'MILES_EXPERTS_SHARED_OUTER_LORAS="${MILES_EXPERTS_SHARED_OUTER_LORAS:-1}"' in text
        assert 'MILES_TRAIN_MODULE="${MILES_TRAIN_MODULE:-w8_biayn.integrations.miles_train_with_glm47_bridge}"' in text
        # Modal gVisor has no docker daemon; H100 wrappers default local sandbox.
        assert 'W8_CPP_SANDBOX_BACKEND="${W8_CPP_SANDBOX_BACKEND:-local}"' in text

    grpo_text = GLM47_H100_GRPO_RUNNER.read_text(encoding="utf-8")
    assert 'MILES_NUM_ROLLOUT="${MILES_NUM_ROLLOUT:-100}"' in grpo_text
    assert 'MILES_ROLLOUT_BATCH_SIZE="${MILES_ROLLOUT_BATCH_SIZE:-32}"' in grpo_text
    assert 'MILES_N_SAMPLES_PER_PROMPT="${MILES_N_SAMPLES_PER_PROMPT:-8}"' in grpo_text
    assert 'MILES_GLOBAL_BATCH_SIZE="${MILES_GLOBAL_BATCH_SIZE:-256}"' in grpo_text
    assert 'MILES_ROLLOUT_MAX_RESPONSE_LEN="${MILES_ROLLOUT_MAX_RESPONSE_LEN:-1536}"' in grpo_text
    assert 'MILES_ROLLOUT_TEMPERATURE="${MILES_ROLLOUT_TEMPERATURE:-1.0}"' in grpo_text
    assert 'MILES_EVAL_MAX_RESPONSE_LEN="${MILES_EVAL_MAX_RESPONSE_LEN:-1536}"' in grpo_text
    assert 'MILES_EVAL_INTERVAL="${MILES_EVAL_INTERVAL:-20}"' in grpo_text
    assert 'MILES_SAVE_INTERVAL="${MILES_SAVE_INTERVAL:-10}"' in grpo_text
    assert 'MILES_LR="${MILES_LR:-2e-6}"' in grpo_text
    assert 'MILES_NO_REF="${MILES_NO_REF:-1}"' in grpo_text
    assert 'MILES_SGLANG_MEM_FRACTION_STATIC="${MILES_SGLANG_MEM_FRACTION_STATIC:-0.75}"' in grpo_text
    assert 'MILES_SGLANG_SERVER_CONCURRENCY="${MILES_SGLANG_SERVER_CONCURRENCY:-1024}"' in grpo_text
    assert 'MILES_SGLANG_CUDA_GRAPH_MAX_BS="${MILES_SGLANG_CUDA_GRAPH_MAX_BS:-64}"' in grpo_text
    assert 'MILES_SGLANG_MAX_RUNNING_REQUESTS="${MILES_SGLANG_MAX_RUNNING_REQUESTS:-256}"' in grpo_text
    assert 'W8_CPP_REWARD_WORKERS="${W8_CPP_REWARD_WORKERS:-32}"' in grpo_text
    assert (
        'MILES_APPLY_CHAT_TEMPLATE_KWARGS="${MILES_APPLY_CHAT_TEMPLATE_KWARGS:-{\\"enable_thinking\\": false}}"'
        in grpo_text
    )

    sft_text = GLM47_H100_SFT_RUNNER.read_text(encoding="utf-8")
    assert 'MILES_ROLLOUT_BATCH_SIZE="${MILES_ROLLOUT_BATCH_SIZE:-32}"' in sft_text
    assert 'MILES_GLOBAL_BATCH_SIZE="${MILES_GLOBAL_BATCH_SIZE:-32}"' in sft_text
    assert 'MILES_SAVE_INTERVAL="${MILES_SAVE_INTERVAL:-1000}"' in sft_text
    assert 'MILES_NO_REF="${MILES_NO_REF:-1}"' in sft_text
    assert 'MILES_SGLANG_MEM_FRACTION_STATIC="${MILES_SGLANG_MEM_FRACTION_STATIC:-0.60}"' in sft_text
    assert 'MILES_SGLANG_CUDA_GRAPH_MAX_BS="${MILES_SGLANG_CUDA_GRAPH_MAX_BS:-16}"' in sft_text
    assert 'MILES_SGLANG_MAX_RUNNING_REQUESTS="${MILES_SGLANG_MAX_RUNNING_REQUESTS:-64}"' in sft_text
    assert 'MILES_LORA_BASE_CPU_BACKUP="${MILES_LORA_BASE_CPU_BACKUP:-0}"' in sft_text
    assert 'MILES_EXTRA_ARGS="--no-offload-train${MILES_EXTRA_ARGS:+ ${MILES_EXTRA_ARGS}}"' in sft_text


def test_miles_h100_wandb_lineage_reaches_ray_workers_and_receipts() -> None:
    expected_job_types = {
        GLM47_H100_SFT_RUNNER: "sft",
        GLM47_H100_GRPO_RUNNER: "grpo",
    }
    for script, job_type in expected_job_types.items():
        text = script.read_text(encoding="utf-8")
        assert 'W8_EXPERIMENT_ID="${W8_EXPERIMENT_ID:-${RUN_ID}}"' in text
        assert 'MILES_WANDB_GROUP="${MILES_WANDB_GROUP:-${W8_EXPERIMENT_ID}}"' in text
        assert f'MILES_WANDB_JOB_TYPE="${{MILES_WANDB_JOB_TYPE:-{job_type}}}"' in text
        assert 'WANDB_RUN_GROUP="${WANDB_RUN_GROUP:-${W8_EXPERIMENT_ID}}"' in text
        assert f'WANDB_JOB_TYPE="${{WANDB_JOB_TYPE:-{job_type}}}"' in text

    for runner in (SFT_RUNNER, GRPO_RUNNER):
        text = runner.read_text(encoding="utf-8")
        assert "wandb_job_type=${WANDB_JOB_TYPE}" in text
        assert "experiment_id=${EXPERIMENT_ID}" in text
        assert "W8_EXPERIMENT_ID" in text
        assert "WANDB_JOB_TYPE" in text
        assert "WANDB_RUN_GROUP" in text
        assert "WANDB_TAGS" in text
        assert '"${REPO_ROOT}/scripts/wandb_posttraining.py" finalize-stage' in text
        assert '--timing-status "${W8_TIMING_STATUS:-unverified}"' in text
        assert "wall_s=$((SECONDS - STAGE_STARTED_AT))" in text
        assert 'finalize_wandb "${STAGE_STATUS}"' in text


def test_miles_glm47_h100_converter_matches_runner_layout() -> None:
    text = GLM47_H100_CONVERTER.read_text(encoding="utf-8")
    assert 'MODEL_ARGS_FILE="${MILES_MODEL_ARGS_FILE:-glm4.7-flash.sh}"' in text
    assert 'HF_CHECKPOINT="${MILES_HF_CHECKPOINT:-/root/models/GLM-4.7-Flash}"' in text
    assert 'REF_LOAD_DIR="${MILES_REF_LOAD_DIR:-${HF_CHECKPOINT}_torch_dist_tp4_pp1_ep8}"' in text
    assert 'TP_SIZE="${MILES_TENSOR_MODEL_PARALLEL_SIZE:-4}"' in text
    assert 'PP_SIZE="${MILES_PIPELINE_MODEL_PARALLEL_SIZE:-1}"' in text
    assert 'EP_SIZE="${MILES_EXPERT_MODEL_PARALLEL_SIZE:-8}"' in text
    assert 'ETP_SIZE="${MILES_EXPERT_TENSOR_PARALLEL_SIZE:-1}"' in text
    assert 'CONVERT_NPROC="${MILES_CONVERT_NPROC:-8}"' in text
    # grouped-GEMM stays in conversion args by default (mbridge's expert
    # mapper needs grouped names); stripping is opt-in for old images.
    assert 'STRIP_GROUPED_GEMM="${W8_CONVERT_STRIP_MOE_GROUPED_GEMM:-0}"' in text
    assert 'if [ "${STRIP_GROUPED_GEMM}" = "1" ] && [ "${arg}" = "--moe-grouped-gemm" ]; then' in text
    assert 'convert_hf_to_torch_dist.py' in text
    assert '--expert-model-parallel-size "${EP_SIZE}"' in text
    # The converter must run through the bridge-registering wrapper with the
    # repo src on PYTHONPATH; stock mbridge cannot map Glm4MoeLite.
    assert "-m w8_biayn.integrations.miles_convert_with_glm47_bridge" in text
    assert 'CONVERT_PYTHONPATH="${REPO_ROOT}/src:${MEGATRON_DIR}:${PYTHONPATH:-}"' in text


def test_miles_convert_wrapper_registers_bridge_before_exec() -> None:
    import inspect

    from w8_biayn.integrations import miles_convert_with_glm47_bridge as wrapper

    source = inspect.getsource(wrapper.main)
    assert source.index("register_glm47_bridge()") < source.index("exec(compile(")
    assert "convert_hf_to_torch_dist.py" in inspect.getsource(wrapper)


def test_miles_convert_wrapper_pp1_patch(tmp_path, monkeypatch) -> None:
    from w8_biayn.integrations import miles_convert_with_glm47_bridge as wrapper

    tool = tmp_path / "convert_hf_to_torch_dist.py"
    body = (
        "def get_args(args, world_size):\n"
        f"    {wrapper.PP_OVERRIDE_MARKER}\n"
        "        args.pipeline_model_parallel_size = world_size\n"
        "    return args\n"
    )
    tool.write_text(body, encoding="utf-8")

    # gate off: source untouched
    monkeypatch.delenv("W8_CONVERT_KEEP_PP1", raising=False)
    assert wrapper._load_source(tool) == body

    # gate on: override branch neutralized, body still valid python
    monkeypatch.setenv("W8_CONVERT_KEEP_PP1", "1")
    patched = wrapper._load_source(tool)
    assert wrapper.PP_OVERRIDE_MARKER not in patched
    assert "if False:" in patched
    compile(patched, str(tool), "exec")

    # gate on but marker missing: fail loud instead of converting a lie
    tool.write_text("def get_args():\n    return None\n", encoding="utf-8")
    import pytest as _pytest

    with _pytest.raises(RuntimeError, match="PP-override marker"):
        wrapper._load_source(tool)


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


def test_glm47_bridge_marks_shared_outer_lora_as_ep_replicated(monkeypatch) -> None:
    from w8_biayn.integrations import miles_glm47_bridge

    class FakeShardedTensor:
        def __init__(self, replica_id):
            self.replica_id = replica_id

    class FakeSharedOuterAdapter:
        def __init__(self, is_fc1, replica_id):
            self._is_fc1 = is_fc1
            self._replica_id = replica_id

        def sharded_state_dict(self, prefix="", sharded_offsets=(), metadata=None):
            shared_side = "linear_in" if self._is_fc1 else "linear_out"
            per_expert_side = "linear_out" if self._is_fc1 else "linear_in"
            return {
                f"{prefix}{shared_side}.weight": FakeShardedTensor(self._replica_id),
                f"{prefix}{shared_side}._extra_state": FakeShardedTensor(self._replica_id),
                f"{prefix}{per_expert_side}.weight": FakeShardedTensor((0, 0, 0)),
            }

    fake_peft_utils = types.ModuleType("megatron.bridge.peft.utils")
    fake_peft_utils.SharedOuterGroupedExpertAdapter = FakeSharedOuterAdapter

    fake_parallel_state = types.ModuleType("megatron.core.parallel_state")
    fake_parallel_state.get_expert_model_parallel_rank = lambda: 3
    fake_parallel_state.get_expert_model_parallel_world_size = lambda: 4

    fake_core = types.ModuleType("megatron.core")
    fake_core.parallel_state = fake_parallel_state

    monkeypatch.setattr(miles_glm47_bridge, "_SHARED_OUTER_CKPT_PATCHED", False)
    monkeypatch.setitem(sys.modules, "megatron", types.ModuleType("megatron"))
    monkeypatch.setitem(sys.modules, "megatron.bridge", types.ModuleType("megatron.bridge"))
    monkeypatch.setitem(sys.modules, "megatron.bridge.peft", types.ModuleType("megatron.bridge.peft"))
    monkeypatch.setitem(sys.modules, "megatron.bridge.peft.utils", fake_peft_utils)
    monkeypatch.setitem(sys.modules, "megatron.core", fake_core)
    monkeypatch.setitem(sys.modules, "megatron.core.parallel_state", fake_parallel_state)

    miles_glm47_bridge._patch_shared_outer_expert_adapter_replication()
    assert FakeSharedOuterAdapter._w8_ep_replica_patched is True

    fc1 = FakeSharedOuterAdapter(is_fc1=True, replica_id=(0, 0, 0)).sharded_state_dict(prefix="a.")
    assert fc1["a.linear_in.weight"].replica_id == (0, 0, 3)
    assert fc1["a.linear_in._extra_state"].replica_id == (0, 0, 3)
    assert fc1["a.linear_out.weight"].replica_id == (0, 0, 0)

    fc2 = FakeSharedOuterAdapter(is_fc1=False, replica_id=(0, 0, 1)).sharded_state_dict(prefix="b.")
    assert fc2["b.linear_out.weight"].replica_id == (0, 0, 7)
    assert fc2["b.linear_out._extra_state"].replica_id == (0, 0, 7)
    assert fc2["b.linear_in.weight"].replica_id == (0, 0, 0)

    int_replica = FakeSharedOuterAdapter(is_fc1=True, replica_id=2).sharded_state_dict(prefix="c.")
    assert int_replica["c.linear_in.weight"].replica_id == 11

    # Re-running the patch must not double-wrap.
    monkeypatch.setattr(miles_glm47_bridge, "_SHARED_OUTER_CKPT_PATCHED", False)
    miles_glm47_bridge._patch_shared_outer_expert_adapter_replication()
    rewrapped = FakeSharedOuterAdapter(is_fc1=True, replica_id=(0, 0, 0)).sharded_state_dict(prefix="d.")
    assert rewrapped["d.linear_in.weight"].replica_id == (0, 0, 3)


def test_glm47_bridge_drops_mtp_adapters_from_sglang_lora_sync() -> None:
    from w8_biayn.integrations import miles_glm47_bridge

    sent = []

    class FakeUpdater:
        def __init__(self, num_layers):
            self.args = types.SimpleNamespace(num_layers=num_layers)

        def _send_lora_params(self, hf_named_tensors):
            sent.append(list(hf_named_tensors))
            return [], None

    fake_module = types.ModuleType("miles.backends.megatron_utils.update_weight.update_weight_from_tensor")
    fake_module.UpdateWeightFromTensor = FakeUpdater

    miles_glm47_bridge._apply_sglang_lora_mtp_filter(fake_module)
    assert FakeUpdater._w8_mtp_filter_patched is True

    tensors = [
        ("base_model.model.model.layers.0.self_attn.q_a_proj.lora_A.weight", "t0"),
        ("base_model.model.model.layers.46.mlp.gate_proj.lora_B.weight", "t46"),
        ("base_model.model.model.layers.47.mlp.shared_experts.gate_proj.lora_A.weight", "t47"),
    ]
    FakeUpdater(num_layers=47)._send_lora_params(tensors)
    assert [name for name, _ in sent[-1]] == [
        "base_model.model.model.layers.0.self_attn.q_a_proj.lora_A.weight",
        "base_model.model.model.layers.46.mlp.gate_proj.lora_B.weight",
    ]

    # All-MTP payload must pass through unfiltered rather than become empty.
    only_mtp = [("base_model.model.model.layers.47.mlp.gate_proj.lora_A.weight", "t")]
    FakeUpdater(num_layers=47)._send_lora_params(only_mtp)
    assert sent[-1] == only_mtp

    # Double application must not re-wrap.
    miles_glm47_bridge._apply_sglang_lora_mtp_filter(fake_module)
    FakeUpdater(num_layers=47)._send_lora_params(tensors)
    assert len(sent[-1]) == 2


def test_glm47_bridge_orders_sglang_mem_pool_per_expert_first() -> None:
    from w8_biayn.integrations import miles_glm47_bridge

    observed = []

    class FakePool:
        def load_lora_weight_to_buffer(self, uid, buffer_id, lora_adapter, *args, **kwargs):
            observed.append([list(layer.weights) for layer in lora_adapter.layers])
            return "ok"

    fake_module = types.ModuleType("sglang.srt.lora.mem_pool")
    fake_module.LoRAMemoryPool = FakePool

    miles_glm47_bridge._apply_sglang_mem_pool_ordering(fake_module)
    assert FakePool._w8_expert_order_patched is True

    shared_first = types.SimpleNamespace(
        weights={
            "mlp.experts.gate_proj.lora_A.weight": "shared3d",
            "mlp.experts.0.gate_proj.lora_B.weight": "e0",
            "mlp.experts.1.gate_proj.lora_B.weight": "e1",
            "self_attn.o_proj.lora_A.weight": "attn",
        }
    )
    no_experts = types.SimpleNamespace(weights={"self_attn.o_proj.lora_A.weight": "attn"})
    adapter = types.SimpleNamespace(layers=[shared_first, no_experts])

    result = FakePool().load_lora_weight_to_buffer("uid", 0, adapter)
    assert result == "ok"
    assert observed[-1][0] == [
        "mlp.experts.0.gate_proj.lora_B.weight",
        "mlp.experts.1.gate_proj.lora_B.weight",
        "mlp.experts.gate_proj.lora_A.weight",
        "self_attn.o_proj.lora_A.weight",
    ]
    assert observed[-1][1] == ["self_attn.o_proj.lora_A.weight"]


def test_register_glm47_bridge_installs_hooks_without_heavy_imports(monkeypatch) -> None:
    """Registration must be lazy: it runs via sitecustomize at interpreter startup
    in every gated process (including Ray node agents, where an eager
    megatron.bridge import once stalled `ray start` past its deadline)."""

    import importlib.abc

    from w8_biayn.integrations import miles_glm47_bridge

    heavy_roots = ("megatron", "mbridge", "miles_plugins", "transformers", "modelopt")
    attempted: list[str] = []

    class RecordingFinder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in heavy_roots:
                attempted.append(fullname)
            return None

    recorder = RecordingFinder()
    monkeypatch.setattr(miles_glm47_bridge, "_REGISTERED", False)
    monkeypatch.setattr(miles_glm47_bridge, "_MBRIDGE_PATCHED", False)
    monkeypatch.setattr(miles_glm47_bridge, "_SHARED_OUTER_CKPT_PATCHED", False)
    monkeypatch.setattr(miles_glm47_bridge, "_LORA_SYNC_PATCHED", False)
    monkeypatch.setattr(miles_glm47_bridge, "_SGLANG_MEM_POOL_PATCHED", False)
    monkeypatch.setattr(miles_glm47_bridge, "_ROUTER_CB_PATCHED", False)
    monkeypatch.setattr(miles_glm47_bridge, "_WARM_START_OPT_PATCHED", False)
    before_meta_path = list(sys.meta_path)
    sys.meta_path.insert(0, recorder)
    try:
        miles_glm47_bridge.register_glm47_bridge()
        assert attempted == []
        added = [f for f in sys.meta_path if f is not recorder and f not in before_meta_path]
        # one lazy hook per patch target: mbridge.core.bridge, miles_plugins.mbridge,
        # megatron.bridge.peft.utils, miles update_weight module, sglang mem_pool,
        # miles router_manager, miles lora_utils (optimizer reload), and
        # megatron.bridge for the bridge-class registration
        assert len(added) == 8
    finally:
        sys.meta_path[:] = [f for f in sys.meta_path if f is recorder or f in before_meta_path]
        sys.meta_path.remove(recorder)


def test_grpo_runner_supports_adapter_init_passthrough() -> None:
    text = GRPO_RUNNER.read_text(encoding="utf-8")
    assert 'LORA_ADAPTER_PATH="${MILES_LORA_ADAPTER_PATH:-}"' in text
    assert '--lora-adapter-path "${LORA_ADAPTER_PATH}"' in text


def test_grpo_runner_save_interval_is_configurable() -> None:
    text = GRPO_RUNNER.read_text(encoding="utf-8")
    assert '--save-interval "${MILES_SAVE_INTERVAL:-1}"' in text


def test_grpo_runner_guards_existing_data_from_forced_rebuild() -> None:
    text = GRPO_RUNNER.read_text(encoding="utf-8")
    guard = 'if [ ! -f "${DATA_DIR}/grpo/train.jsonl" ]; then'
    assert text.count(guard) == 2
    assert text.index(guard) < text.index('BUILD_DATA_ARGS[@]}"')


def test_warm_start_marks_engine_adapter_preloaded() -> None:
    from w8_biayn.integrations import miles_glm47_bridge

    class FakeArgs:
        num_layers = 47
        lora_adapter_path = "/some/adapter"

    class FakeArgsNoWarmStart:
        num_layers = 47
        lora_adapter_path = None

    class FakeUpdater:
        def __init__(self, args):
            self.args = args
            self._lora_loaded = False

        def _send_lora_params(self, hf_named_tensors):
            return hf_named_tensors

    fake_module = types.SimpleNamespace(UpdateWeightFromTensor=FakeUpdater)
    miles_glm47_bridge._apply_sglang_lora_mtp_filter(fake_module)

    assert FakeUpdater(FakeArgs())._lora_loaded is True
    assert FakeUpdater(FakeArgsNoWarmStart())._lora_loaded is False


def test_router_circuit_breaker_patch_disables_breaker_and_widens_queue() -> None:
    from w8_biayn.integrations import miles_glm47_bridge

    class FakeRouterArgs:
        def __init__(self):
            self.disable_circuit_breaker = False
            self.queue_size = 100
            self.queue_timeout_secs = 60

        @classmethod
        def from_cli_args(cls, args, use_router_prefix=False):
            return cls()

    fake_module = types.SimpleNamespace(RouterArgs=FakeRouterArgs)
    miles_glm47_bridge._apply_router_cb_patch(fake_module)

    router_args = FakeRouterArgs.from_cli_args(object(), use_router_prefix=True)
    assert router_args.disable_circuit_breaker is True
    assert router_args.queue_size == 4096
    assert router_args.queue_timeout_secs == 1800

    # no double wrap
    miles_glm47_bridge._apply_router_cb_patch(fake_module)
    assert FakeRouterArgs.from_cli_args(object()).queue_size == 4096


def test_grpo_runner_exposes_server_concurrency() -> None:
    text = GRPO_RUNNER.read_text(encoding="utf-8")
    assert 'SGLANG_SERVER_CONCURRENCY="${MILES_SGLANG_SERVER_CONCURRENCY:-512}"' in text
    assert '--sglang-server-concurrency "${SGLANG_SERVER_CONCURRENCY}"' in text


def test_grpo_runner_eval_prompt_data_is_configurable() -> None:
    text = GRPO_RUNNER.read_text(encoding="utf-8")
    assert 'EVAL_PROMPT_DATA="${MILES_EVAL_PROMPT_DATA:-}"' in text
    assert '--eval-prompt-data pie_cpp "${EVAL_PROMPT_DATA:-${DATA_DIR}/eval/validation.jsonl}"' in text


def test_grpo_runner_supports_raw_extra_args() -> None:
    text = GRPO_RUNNER.read_text(encoding="utf-8")
    assert 'read -r -a EXTRA_ARGS <<< "${MILES_EXTRA_ARGS}"' in text


def test_sft_runner_supports_raw_extra_args() -> None:
    text = SFT_RUNNER.read_text(encoding="utf-8")
    assert 'read -r -a EXTRA_ARGS <<< "${MILES_EXTRA_ARGS}"' in text
    assert "extra_args=${MILES_EXTRA_ARGS:-}" in text


def test_miles_runners_expose_h100_throughput_knobs() -> None:
    for script in (SFT_RUNNER, GRPO_RUNNER):
        text = script.read_text(encoding="utf-8")
        assert 'USE_DYNAMIC_BATCH_SIZE="${MILES_USE_DYNAMIC_BATCH_SIZE:-0}"' in text
        assert 'BALANCE_DATA="${MILES_BALANCE_DATA:-0}"' in text
        assert 'PERF_ARGS+=(--use-dynamic-batch-size)' in text
        assert 'PERF_ARGS+=(--balance-data)' in text
        assert "use_dynamic_batch_size=${USE_DYNAMIC_BATCH_SIZE}" in text
        assert "balance_data=${BALANCE_DATA}" in text
        assert 'MOE_ENABLE_DEEPEP="${MILES_MOE_ENABLE_DEEPEP:-0}"' in text
        assert 'SGLANG_MAX_RUNNING_REQUESTS="${MILES_SGLANG_MAX_RUNNING_REQUESTS:-}"' in text
        assert 'SGLANG_DP_SIZE="${MILES_SGLANG_DP_SIZE:-${GPUS_PER_NODE}}"' in text
        assert 'SGLANG_ENABLE_DP_ATTENTION="${MILES_SGLANG_ENABLE_DP_ATTENTION:-0}"' in text
        assert 'SGLANG_ENABLE_DP_LM_HEAD="${MILES_SGLANG_ENABLE_DP_LM_HEAD:-0}"' in text
        assert 'SGLANG_MOE_DENSE_TP_SIZE="${MILES_SGLANG_MOE_DENSE_TP_SIZE:-}"' in text
        assert 'SGLANG_SPECULATIVE="${MILES_SGLANG_SPECULATIVE:-0}"' in text
        assert 'SGLANG_DISABLE_CUSTOM_ALL_REDUCE="${MILES_SGLANG_DISABLE_CUSTOM_ALL_REDUCE:-0}"' in text
        assert 'PERF_ARGS+=(--moe-enable-deepep)' in text
        assert 'SGLANG_ARGS+=(--sglang-enable-dp-attention --sglang-dp-size "${SGLANG_DP_SIZE}")' in text
        assert 'SGLANG_ARGS+=(--sglang-enable-dp-lm-head)' in text
        assert 'SGLANG_ARGS+=(--sglang-moe-dense-tp-size "${SGLANG_MOE_DENSE_TP_SIZE}")' in text
        assert "--sglang-speculative-algorithm EAGLE" in text
        assert 'SGLANG_ARGS+=(--sglang-max-running-requests "${SGLANG_MAX_RUNNING_REQUESTS}")' in text
        assert 'SGLANG_ARGS+=(--sglang-disable-custom-all-reduce)' in text
        assert "moe_enable_deepep=${MOE_ENABLE_DEEPEP}" in text
        assert "sglang_speculative=${SGLANG_SPECULATIVE}" in text

    grpo_text = GRPO_RUNNER.read_text(encoding="utf-8")
    assert '\\"NVSHMEM_DISABLE_NCCL\\": \\"${NVSHMEM_DISABLE_NCCL:-}\\"' in grpo_text
    sft_text = SFT_RUNNER.read_text(encoding="utf-8")
    assert '"NVSHMEM_DISABLE_NCCL": os.environ.get("NVSHMEM_DISABLE_NCCL", "")' in sft_text


def test_miles_runners_gate_recompute_behind_env() -> None:
    for script in (SFT_RUNNER, GRPO_RUNNER):
        text = script.read_text(encoding="utf-8")
        assert 'RECOMPUTE_GRANULARITY="${MILES_RECOMPUTE_GRANULARITY:-full}"' in text
        assert 'case "${RECOMPUTE_GRANULARITY}" in' in text
        assert "PERF_ARGS+=(--recompute-granularity full --recompute-method uniform --recompute-num-layers 1)" in text
        assert "PERF_ARGS+=(--recompute-granularity selective)" in text
        assert "recompute_granularity=${RECOMPUTE_GRANULARITY}" in text
        # The default profile keeps full recompute; the flags must no longer be
        # unconditional members of PERF_ARGS.
        assert "  --recompute-granularity full\n" not in text


def test_runners_gate_docker_preflight_on_sandbox_backend() -> None:
    for script in (SFT_RUNNER, GRPO_RUNNER):
        text = script.read_text(encoding="utf-8")
        assert 'if [ "${W8_CPP_SANDBOX_BACKEND:-docker}" != "local" ]; then' in text
        # the docker checks live inside the backend gate, not at top level
        gate = text.index('if [ "${W8_CPP_SANDBOX_BACKEND:-docker}" != "local" ]; then')
        docker_check = text.index("Missing docker CLI inside container")
        assert gate < docker_check
    grpo_text = GRPO_RUNNER.read_text(encoding="utf-8")
    assert "W8_CPP_SANDBOX_BACKEND=local but g++ is missing" in grpo_text


def test_grpo_runner_prefers_mini_eval_when_present() -> None:
    text = GRPO_RUNNER.read_text(encoding="utf-8")
    assert '[ -f "${DATA_DIR}/eval/validation_mini126.jsonl" ]' in text
    assert 'EVAL_PROMPT_DATA="${DATA_DIR}/eval/validation_mini126.jsonl"' in text
    fallback = text.index("validation_mini126.jsonl")
    eval_args = text.index("--eval-prompt-data pie_cpp")
    assert fallback < eval_args


def test_grpo_runner_ref_load_is_optional() -> None:
    text = GRPO_RUNNER.read_text(encoding="utf-8")
    assert 'if [ "${MILES_NO_REF:-0}" != "1" ]; then' in text
    assert text.count('--ref-load "${REF_LOAD_DIR}"') == 1


def test_sft_runner_ref_load_is_optional() -> None:
    text = SFT_RUNNER.read_text(encoding="utf-8")
    assert 'if [ "${MILES_NO_REF:-0}" != "1" ]; then' in text
    assert text.count('--ref-load "${REF_LOAD_DIR}"') == 1


def test_miles_runners_forward_offline_wandb_mode() -> None:
    sft_text = SFT_RUNNER.read_text(encoding="utf-8")
    grpo_text = GRPO_RUNNER.read_text(encoding="utf-8")
    assert '"WANDB_MODE",' in sft_text
    assert '\\"WANDB_MODE\\": \\"${WANDB_MODE:-online}\\"' in grpo_text


def test_warm_start_reloads_optimizer_master_params() -> None:
    from w8_biayn.integrations import miles_glm47_bridge

    calls = []

    class FakeOptimizer:
        def reload_model_params(self):
            calls.append("reloaded")

    def fake_load(model, adapter_path, *, optimizer=None, opt_param_scheduler=None):
        return True, 244

    fake_module = types.SimpleNamespace(load_lora_adapter=fake_load)
    miles_glm47_bridge._apply_warm_start_optimizer_reload(fake_module)

    loaded, iteration = fake_module.load_lora_adapter([], "/x", optimizer=FakeOptimizer())
    assert (loaded, iteration) == (True, 244)
    assert calls == ["reloaded"]

    # not-loaded path must not touch the optimizer
    def fake_load_fail(model, adapter_path, *, optimizer=None, opt_param_scheduler=None):
        return False, None

    fake_module2 = types.SimpleNamespace(load_lora_adapter=fake_load_fail)
    miles_glm47_bridge._apply_warm_start_optimizer_reload(fake_module2)
    fake_module2.load_lora_adapter([], "/x", optimizer=FakeOptimizer())
    assert calls == ["reloaded"]
