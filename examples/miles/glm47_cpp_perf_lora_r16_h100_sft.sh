#!/usr/bin/env bash
# Fast 8x H100 Miles SFT LoRA rank-16 runner for GLM-4.7-Flash on PIE C++.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." &>/dev/null && pwd)"

RUN_ID="${MILES_RUN_ID:-glm47_h100_pie_cpp_lora_r16_sft_$(date +%Y%m%d_%H%M%S)}"
export MILES_RUN_ID="${RUN_ID}"
export MILES_RUN_ROOT="${MILES_RUN_ROOT:-${REPO_ROOT}/.w8-biayn/miles/glm47-h100-cpp-perf/runs/${RUN_ID}}"
export MILES_MODEL_ARGS_FILE="${MILES_MODEL_ARGS_FILE:-glm4.7-flash.sh}"
export MILES_HF_CHECKPOINT="${MILES_HF_CHECKPOINT:-/root/models/GLM-4.7-Flash}"
export MILES_REF_LOAD_DIR="${MILES_REF_LOAD_DIR:-${MILES_HF_CHECKPOINT}_torch_dist_tp4_pp1_ep8}"

export MILES_GPUS_PER_NODE="${MILES_GPUS_PER_NODE:-8}"
export MILES_TENSOR_MODEL_PARALLEL_SIZE="${MILES_TENSOR_MODEL_PARALLEL_SIZE:-4}"
export MILES_PIPELINE_MODEL_PARALLEL_SIZE="${MILES_PIPELINE_MODEL_PARALLEL_SIZE:-1}"
export MILES_CONTEXT_PARALLEL_SIZE="${MILES_CONTEXT_PARALLEL_SIZE:-1}"
export MILES_EXPERT_MODEL_PARALLEL_SIZE="${MILES_EXPERT_MODEL_PARALLEL_SIZE:-8}"
export MILES_EXPERT_TENSOR_PARALLEL_SIZE="${MILES_EXPERT_TENSOR_PARALLEL_SIZE:-1}"
export MILES_SEQ_LENGTH="${MILES_SEQ_LENGTH:-4096}"
# 24576 matched the validated 4x A100 packing; H100 80GB takes it with room to
# spare once recompute drops to selective (attention-only, few percent tax vs
# ~30% for full).
export MILES_MAX_TOKENS_PER_GPU="${MILES_MAX_TOKENS_PER_GPU:-24576}"
export MILES_MICRO_BATCH_SIZE="${MILES_MICRO_BATCH_SIZE:-1}"
export MILES_RECOMPUTE_GRANULARITY="${MILES_RECOMPUTE_GRANULARITY:-selective}"

export MILES_MOE_TOKEN_DISPATCHER_TYPE="${MILES_MOE_TOKEN_DISPATCHER_TYPE:-flex}"
export MILES_MOE_ENABLE_DEEPEP="${MILES_MOE_ENABLE_DEEPEP:-1}"
export NVSHMEM_DISABLE_NCCL="${NVSHMEM_DISABLE_NCCL:-1}"
export MILES_ATTENTION_BACKEND="${MILES_ATTENTION_BACKEND:-flash}"

# Production SFT scale, mirroring the validated A100 run (global batch 32).
export MILES_ROLLOUT_BATCH_SIZE="${MILES_ROLLOUT_BATCH_SIZE:-32}"
export MILES_GLOBAL_BATCH_SIZE="${MILES_GLOBAL_BATCH_SIZE:-32}"
export MILES_SAVE_INTERVAL="${MILES_SAVE_INTERVAL:-1000}"
# SFT has no KL/reference-logprob path; loading a second frozen policy only
# adds startup, host-memory, and state-switching overhead.
export MILES_NO_REF="${MILES_NO_REF:-1}"

export MILES_SGLANG_MEM_FRACTION_STATIC="${MILES_SGLANG_MEM_FRACTION_STATIC:-0.60}"
export MILES_SGLANG_CUDA_GRAPH_MAX_BS="${MILES_SGLANG_CUDA_GRAPH_MAX_BS:-16}"
export MILES_SGLANG_MAX_RUNNING_REQUESTS="${MILES_SGLANG_MAX_RUNNING_REQUESTS:-64}"
export MILES_SGLANG_ENABLE_DP_ATTENTION="${MILES_SGLANG_ENABLE_DP_ATTENTION:-1}"
export MILES_SGLANG_DP_SIZE="${MILES_SGLANG_DP_SIZE:-8}"
export MILES_SGLANG_ENABLE_DP_LM_HEAD="${MILES_SGLANG_ENABLE_DP_LM_HEAD:-1}"
export MILES_SGLANG_MOE_DENSE_TP_SIZE="${MILES_SGLANG_MOE_DENSE_TP_SIZE:-1}"
# EAGLE speculative decoding stays opt-in: SGLang LoRA serving + spec decode is
# an unproven pairing (the serve adapter is MTP-stripped, the draft head is
# base-policy). Validate in the fit probe before enabling.
export MILES_SGLANG_SPECULATIVE="${MILES_SGLANG_SPECULATIVE:-0}"
export MILES_SGLANG_SPECULATIVE_NUM_STEPS="${MILES_SGLANG_SPECULATIVE_NUM_STEPS:-3}"
export MILES_SGLANG_SPECULATIVE_EAGLE_TOPK="${MILES_SGLANG_SPECULATIVE_EAGLE_TOPK:-1}"
export MILES_SGLANG_SPECULATIVE_NUM_DRAFT_TOKENS="${MILES_SGLANG_SPECULATIVE_NUM_DRAFT_TOKENS:-4}"
# Custom allreduce is the fast path on NVLink; disabling it was a PCIe-node
# stability carryover.
export MILES_SGLANG_DISABLE_CUSTOM_ALL_REDUCE="${MILES_SGLANG_DISABLE_CUSTOM_ALL_REDUCE:-0}"

export MILES_LORA_TARGET_MODULES="${MILES_LORA_TARGET_MODULES:-q_a_proj,kv_a_proj_with_mqa,o_proj,gate_proj,up_proj,down_proj}"
export MILES_SGLANG_LORA_TARGET_MODULES="${MILES_SGLANG_LORA_TARGET_MODULES:-${MILES_LORA_TARGET_MODULES}}"
export MILES_EXPERTS_SHARED_OUTER_LORAS="${MILES_EXPERTS_SHARED_OUTER_LORAS:-1}"
# Train-only SFT has no SGLang engine or weight handoff, so retaining another
# base-policy copy on CPU only adds startup and host-memory pressure.
export MILES_LORA_BASE_CPU_BACKUP="${MILES_LORA_BASE_CPU_BACKUP:-0}"
export MILES_NO_GRADIENT_ACCUMULATION_FUSION="${MILES_NO_GRADIENT_ACCUMULATION_FUSION:-1}"
export MILES_SGLANG_LORA_USE_VIRTUAL_EXPERTS="${MILES_SGLANG_LORA_USE_VIRTUAL_EXPERTS:-1}"
# Miles normally offloads every colocated actor between batches. The SFT path
# is train-only, so keep the actor resident; callers can append
# --offload-train through MILES_EXTRA_ARGS to restore the upstream behavior.
export MILES_EXTRA_ARGS="--no-offload-train${MILES_EXTRA_ARGS:+ ${MILES_EXTRA_ARGS}}"
export MILES_TRAIN_MODULE="${MILES_TRAIN_MODULE:-w8_biayn.integrations.miles_train_with_glm47_bridge}"
export W8_REGISTER_GLM47_BRIDGE="${W8_REGISTER_GLM47_BRIDGE:-1}"
# With no colocated rollout engine, retaining the allocator cache is both safe
# and much cheaper than eight full Python GC scans after every SFT batch.
export W8_GLM47_SKIP_TRAIN_ONLY_CLEAR_MEMORY="${W8_GLM47_SKIP_TRAIN_ONLY_CLEAR_MEMORY:-1}"
# Modal 8x H100 has no docker daemon (gVisor). Default the local in-process
# sandbox; override with W8_CPP_SANDBOX_BACKEND=docker only on hosts that mount it.
export W8_CPP_SANDBOX_BACKEND="${W8_CPP_SANDBOX_BACKEND:-local}"
export W8_CPP_REWARD_WORKERS="${W8_CPP_REWARD_WORKERS:-32}"

export W8_EXPERIMENT_ID="${W8_EXPERIMENT_ID:-${RUN_ID}}"
export MILES_WANDB_PROJECT="${MILES_WANDB_PROJECT:-glm47-pie-cpp-posttraining}"
export MILES_WANDB_GROUP="${MILES_WANDB_GROUP:-${W8_EXPERIMENT_ID}}"
export MILES_WANDB_RUN_ID="${MILES_WANDB_RUN_ID:-${RUN_ID}}"
export MILES_WANDB_JOB_TYPE="${MILES_WANDB_JOB_TYPE:-sft}"
export WANDB_RUN_GROUP="${WANDB_RUN_GROUP:-${W8_EXPERIMENT_ID}}"
export WANDB_JOB_TYPE="${WANDB_JOB_TYPE:-sft}"
export WANDB_TAGS="${WANDB_TAGS:-canonical,pie-cpp,sft}"

exec "${SCRIPT_DIR}/moonlight_cpp_perf_lora_r16_sft.sh" "$@"
