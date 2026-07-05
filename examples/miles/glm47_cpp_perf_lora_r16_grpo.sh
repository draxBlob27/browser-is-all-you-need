#!/usr/bin/env bash
# Miles GRPO LoRA rank-16 runner for GLM-4.7-Flash on the PIE C++ task.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." &>/dev/null && pwd)"

RUN_ID="${MILES_RUN_ID:-glm47_pie_cpp_lora_r16_$(date +%Y%m%d_%H%M%S)}"
export MILES_RUN_ID="${RUN_ID}"
export MILES_RUN_ROOT="${MILES_RUN_ROOT:-${REPO_ROOT}/.w8-biayn/miles/glm47-cpp-perf/runs/${RUN_ID}}"
export MILES_MODEL_ARGS_FILE="${MILES_MODEL_ARGS_FILE:-glm4.7-flash.sh}"
export MILES_HF_CHECKPOINT="${MILES_HF_CHECKPOINT:-/root/models/GLM-4.7-Flash}"
export MILES_REF_LOAD_DIR="${MILES_REF_LOAD_DIR:-${MILES_HF_CHECKPOINT}_torch_dist}"
export MILES_LORA_TARGET_MODULES="${MILES_LORA_TARGET_MODULES:-q_a_proj,q_b_proj,kv_a_proj_with_mqa,kv_b_proj,o_proj}"
export MILES_SGLANG_LORA_TARGET_MODULES="${MILES_SGLANG_LORA_TARGET_MODULES:-${MILES_LORA_TARGET_MODULES}}"
export MILES_APPLY_CHAT_TEMPLATE_KWARGS="${MILES_APPLY_CHAT_TEMPLATE_KWARGS:-{\"enable_thinking\": false}}"
export MILES_TRAIN_MODULE="${MILES_TRAIN_MODULE:-w8_biayn.integrations.miles_train_with_glm47_bridge}"
export MILES_WANDB_PROJECT="${MILES_WANDB_PROJECT:-glm47-pie-cpp-posttraining}"
export MILES_WANDB_GROUP="${MILES_WANDB_GROUP:-glm47-pie-cpp-lora-r16}"
export MILES_WANDB_RUN_ID="${MILES_WANDB_RUN_ID:-${RUN_ID}}"

exec "${SCRIPT_DIR}/moonlight_cpp_perf_lora_r16_grpo.sh" "$@"
