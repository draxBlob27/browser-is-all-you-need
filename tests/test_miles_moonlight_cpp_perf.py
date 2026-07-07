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
    before_meta_path = list(sys.meta_path)
    sys.meta_path.insert(0, recorder)
    try:
        miles_glm47_bridge.register_glm47_bridge()
        assert attempted == []
        added = [f for f in sys.meta_path if f is not recorder and f not in before_meta_path]
        # one lazy hook per patch target: mbridge.core.bridge, miles_plugins.mbridge,
        # megatron.bridge.peft.utils, miles update_weight module, sglang mem_pool,
        # miles router_manager, and megatron.bridge for the bridge-class registration
        assert len(added) == 7
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


def test_grpo_runner_ref_load_is_optional() -> None:
    text = GRPO_RUNNER.read_text(encoding="utf-8")
    assert 'if [ "${MILES_NO_REF:-0}" != "1" ]; then' in text
    assert text.count('--ref-load "${REF_LOAD_DIR}"') == 1
