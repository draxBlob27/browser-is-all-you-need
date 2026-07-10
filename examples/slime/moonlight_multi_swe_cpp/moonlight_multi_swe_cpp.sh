#!/usr/bin/env bash
# Moonlight-16B-A3B SLIME runner for Multi-SWE C++ base evaluation.

set -euo pipefail

STAGE="${1:-${SLIME_MULTI_SWE_STAGE:-}}"
if [ -z "${STAGE}" ]; then
  echo "usage: $0 <prepare-data|base-eval>" >&2
  exit 2
fi

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." &>/dev/null && pwd)"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
if [ -n "${SLIME_ROOT:-}" ]; then
  SLIME_ROOT="${SLIME_ROOT}"
elif [ -d /root/slime/scripts/models ]; then
  SLIME_ROOT="/root/slime"
else
  SLIME_ROOT="${REPO_ROOT}/.cache/upstreams/slime"
fi
MEGATRON_DIR="${MEGATRON_DIR:-/root/Megatron-LM}"
PYTHON_BIN="${SLIME_MULTI_SWE_PYTHON:-python3}"
SLIME_TRAIN_MODULE="${SLIME_TRAIN_MODULE:-w8_biayn.integrations.slime_train_entry}"

RUN_ID="${SLIME_RUN_ID:-moonlight_multi_swe_cpp}"
RUN_ROOT="${SLIME_RUN_ROOT:-${REPO_ROOT}/.w8-biayn/slime/moonlight-multi-swe-cpp/runs/${RUN_ID}}"
DATA_DIR="${SLIME_MULTI_SWE_DATA_DIR:-${RUN_ROOT}/data}"
MULTI_SWE_SOURCE="${SLIME_MULTI_SWE_SOURCE:-${REPO_ROOT}/.w8-biayn/data/multi-swe-bench-mini}"
MULTI_SWE_JSONL="${SLIME_MULTI_SWE_JSONL:-}"
EVAL_LIMIT="${SLIME_MULTI_SWE_EVAL_LIMIT:-4}"

HF_CHECKPOINT="${SLIME_HF_CHECKPOINT:-/root/models/Moonlight-16B-A3B-Instruct}"
HF_MODEL_ID="${SLIME_HF_MODEL_ID:-moonshotai/Moonlight-16B-A3B-Instruct}"
DOWNLOAD_HF_CHECKPOINT="${SLIME_DOWNLOAD_HF_CHECKPOINT:-1}"
REF_LOAD_DIR="${SLIME_REF_LOAD_DIR:-${HF_CHECKPOINT}_torch_dist}"
CONVERT_IF_MISSING="${SLIME_CONVERT_IF_MISSING:-1}"
CONVERT_NPROC="${SLIME_CONVERT_NPROC:-1}"
HF_CHECKPOINT_WAS_DOWNLOADED=0

NUM_GPUS="${SLIME_NUM_GPUS:-4}"
TP_SIZE="${SLIME_TENSOR_MODEL_PARALLEL_SIZE:-2}"
PP_SIZE="${SLIME_PIPELINE_MODEL_PARALLEL_SIZE:-1}"
CP_SIZE="${SLIME_CONTEXT_PARALLEL_SIZE:-1}"
EP_SIZE="${SLIME_EXPERT_MODEL_PARALLEL_SIZE:-4}"
ETP_SIZE="${SLIME_EXPERT_TENSOR_PARALLEL_SIZE:-1}"
MAX_TOKENS_PER_GPU="${SLIME_MAX_TOKENS_PER_GPU:-4096}"
MICRO_BATCH_SIZE="${SLIME_MICRO_BATCH_SIZE:-1}"
SEQ_LENGTH="${SLIME_SEQ_LENGTH:-1024}"
ROLLOUT_NUM_GPUS_PER_ENGINE="${SLIME_ROLLOUT_NUM_GPUS_PER_ENGINE:-${NUM_GPUS}}"
SGLANG_MEM_FRACTION_STATIC="${SLIME_SGLANG_MEM_FRACTION:-0.45}"
SGLANG_CUDA_GRAPH_MAX_BS="${SLIME_SGLANG_CUDA_GRAPH_MAX_BS:-16}"
SGLANG_DISABLE_TP_MEMORY_INBALANCE_CHECK="${SLIME_SGLANG_DISABLE_TP_MEMORY_INBALANCE_CHECK:-1}"
SGLANG_ENABLE_TP_MEMORY_INBALANCE_CHECK="${SLIME_SGLANG_ENABLE_TP_MEMORY_INBALANCE_CHECK:-0}"
NVSHMEM_DISABLE_NCCL="${SLIME_NVSHMEM_DISABLE_NCCL:-${NVSHMEM_DISABLE_NCCL:-1}}"
UPDATE_WEIGHT_BUFFER_SIZE="${SLIME_UPDATE_WEIGHT_BUFFER_SIZE:-}"
ATTENTION_BACKEND="${SLIME_ATTENTION_BACKEND:-local}"
LOCAL_LAYER_SPEC_MODULE="${SLIME_LOCAL_LAYER_SPEC_MODULE:-local}"
LOCAL_LAYER_SPEC_NAME="${SLIME_LOCAL_LAYER_SPEC_NAME:-moonlight_local_decoder_block_spec}"
SEQUENCE_PARALLEL="${SLIME_SEQUENCE_PARALLEL:-1}"
MOE_GROUPED_GEMM="${SLIME_MOE_GROUPED_GEMM:-0}"
USE_DYNAMIC_BATCH_SIZE="${SLIME_USE_DYNAMIC_BATCH_SIZE:-auto}"

ROLLOUT_BATCH_SIZE="${SLIME_MULTI_SWE_ROLLOUT_BATCH_SIZE:-1}"
GLOBAL_BATCH_SIZE="${SLIME_MULTI_SWE_GLOBAL_BATCH_SIZE:-1}"
EVAL_N_SAMPLES_PER_PROMPT="${SLIME_EVAL_N_SAMPLES_PER_PROMPT:-1}"
EVAL_MAX_RESPONSE_LEN="${SLIME_EVAL_MAX_RESPONSE_LEN:-16384}"
EVAL_TEMPERATURE="${SLIME_EVAL_TEMPERATURE:-0}"
EVAL_TOP_P="${SLIME_EVAL_TOP_P:-1}"
EVAL_LR_DECAY_ITERS="${SLIME_EVAL_LR_DECAY_ITERS:-1}"

SAVE_INTERVAL="${SLIME_SAVE_INTERVAL:-1000}"
DISTRIBUTED_TIMEOUT_MINUTES="${SLIME_DISTRIBUTED_TIMEOUT_MINUTES:-60}"
MEGATRON_TO_HF_MODE="${SLIME_MEGATRON_TO_HF_MODE:-raw}"
USE_EXTERNAL_RAY="${SLIME_USE_EXTERNAL_RAY:-0}"
SKIP_CLEANUP="${SLIME_SKIP_CLEANUP:-0}"
RAY_MEMORY_USAGE_THRESHOLD="${SLIME_RAY_MEMORY_USAGE_THRESHOLD-0.999}"
RAY_MEMORY_MONITOR_REFRESH_MS="${SLIME_RAY_MEMORY_MONITOR_REFRESH_MS:-}"
COLOCATE="${SLIME_COLOCATE:-1}"
OPTIMIZER_CPU_OFFLOAD="${SLIME_OPTIMIZER_CPU_OFFLOAD:-0}"
MULTI_SWE_SANDBOX_IMAGE="${W8_SLIME_MULTI_SWE_SANDBOX_IMAGE:-w8-biayn-multi-swe-cpp:latest}"
MULTI_SWE_TEST_TIMEOUT_SECONDS="${W8_SLIME_MULTI_SWE_TEST_TIMEOUT_SECONDS:-600}"
MULTI_SWE_ORACLE_SETUP_CHECK="${W8_SLIME_MULTI_SWE_ORACLE_SETUP_CHECK:-1}"

absolute_path() {
  "${PYTHON_BIN}" - "$1" <<'PY'
import sys
from pathlib import Path

print(Path(sys.argv[1]).expanduser().resolve(strict=False))
PY
}

RUN_ROOT="$(absolute_path "${RUN_ROOT}")"
DATA_DIR="$(absolute_path "${DATA_DIR}")"
MULTI_SWE_SOURCE="$(absolute_path "${MULTI_SWE_SOURCE}")"
if [ -n "${MULTI_SWE_JSONL}" ]; then
  MULTI_SWE_JSONL="$(absolute_path "${MULTI_SWE_JSONL}")"
fi
HF_CHECKPOINT="$(absolute_path "${HF_CHECKPOINT}")"
REF_LOAD_DIR="$(absolute_path "${REF_LOAD_DIR}")"

stage_label() {
  case "${STAGE}" in
    base-eval) echo "base" ;;
    *) echo "${STAGE}" ;;
  esac
}

STAGE_LABEL="$(stage_label)"
STAGE_ROOT="${RUN_ROOT}/stages/${STAGE}"
LOG_FILE="${STAGE_ROOT}/run.log"
VRAM_LOG="${STAGE_ROOT}/vram_usage.csv"
VRAM_PEAK_FILE="${STAGE_ROOT}/vram_peak.txt"
RUN_RECEIPT="${STAGE_ROOT}/run_receipt.txt"
ROLLOUT_DUMP_TEMPLATE="${RUN_ROOT}/rollout_dumps/${STAGE_LABEL}_{rollout_id}.pt"
EVAL_DUMP_PATH="${RUN_ROOT}/rollout_dumps/${STAGE_LABEL}_eval_0.pt"

mkdir -p "${STAGE_ROOT}" "${RUN_ROOT}/rollout_dumps" "${RUN_ROOT}/eval"

run_repo_python() {
  PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" "${PYTHON_BIN}" "$@"
}

prepare_data() {
  if [ ! -d "${MULTI_SWE_SOURCE}" ]; then
    echo "Missing Multi-SWE benchmark checkout: ${MULTI_SWE_SOURCE}" >&2
    echo "Clone it first, for example:" >&2
    echo "  git clone https://huggingface.co/datasets/ByteDance-Seed/Multi-SWE-bench_mini .w8-biayn/data/multi-swe-bench-mini" >&2
    exit 2
  fi
  BUILD_DATA_ARGS=(
    -m w8_biayn.integrations.slime_multi_swe_cpp build-data
    --source-root "${MULTI_SWE_SOURCE}"
    --out "${DATA_DIR}"
    --profile "${SLIME_MULTI_SWE_PROFILE:-moonlight-multi-swe-cpp}"
    --run-id "${RUN_ID}"
    --force
  )
  if [ -n "${MULTI_SWE_JSONL}" ]; then
    BUILD_DATA_ARGS+=(--jsonl "${MULTI_SWE_JSONL}")
  fi
  if [ -n "${EVAL_LIMIT}" ]; then
    BUILD_DATA_ARGS+=(--eval-limit "${EVAL_LIMIT}")
  fi
  run_repo_python "${BUILD_DATA_ARGS[@]}"
}

ensure_data() {
  if [ ! -f "${DATA_DIR}/manifest.json" ]; then
    if [ "${SLIME_MULTI_SWE_AUTO_PREPARE_DATA:-1}" != "1" ]; then
      echo "Missing Multi-SWE data manifest: ${DATA_DIR}/manifest.json" >&2
      echo "Run: bash ${SCRIPT_DIR}/prepare_data.sh" >&2
      exit 2
    fi
    prepare_data
  fi
}

hf_checkpoint_is_present() {
  [ -f "${HF_CHECKPOINT}/config.json" ]
}

download_hf_checkpoint_if_missing() {
  if hf_checkpoint_is_present; then
    return
  fi
  if [ "${DOWNLOAD_HF_CHECKPOINT}" != "1" ]; then
    echo "Missing HF checkpoint: ${HF_CHECKPOINT}" >&2
    echo "Set SLIME_HF_CHECKPOINT or rerun with SLIME_DOWNLOAD_HF_CHECKPOINT=1." >&2
    exit 2
  fi
  mkdir -p "$(dirname -- "${HF_CHECKPOINT}")"
  echo "Downloading ${HF_MODEL_ID} to ${HF_CHECKPOINT}"
  "${PYTHON_BIN}" - "${HF_MODEL_ID}" "${HF_CHECKPOINT}" <<'PY'
import sys
from pathlib import Path

from huggingface_hub import snapshot_download

repo_id, local_dir = sys.argv[1], sys.argv[2]
Path(local_dir).mkdir(parents=True, exist_ok=True)
snapshot_download(repo_id=repo_id, local_dir=local_dir)
PY
  HF_CHECKPOINT_WAS_DOWNLOADED=1
}

checkpoint_ready() {
  [ -f "$1/latest_checkpointed_iteration.txt" ]
}

ensure_slime_runtime() {
  for required_path in "${SLIME_ROOT}" "${MEGATRON_DIR}" "${DATA_DIR}/manifest.json"; do
    if [ ! -e "${required_path}" ]; then
      echo "Missing required path: ${required_path}" >&2
      exit 2
    fi
  done
  if [ ! -f "${SLIME_ROOT}/scripts/models/moonlight.sh" ]; then
    echo "Missing Moonlight model args: ${SLIME_ROOT}/scripts/models/moonlight.sh" >&2
    echo "Refresh the pinned SLIME checkout with: uv run w8-biayn upstreams clone slime" >&2
    exit 2
  fi
  if ! command -v ray >/dev/null 2>&1; then
    echo "The SLIME runtime is not active: 'ray' is missing from PATH." >&2
    echo "Run inside the SLIME container started by .w8-biayn/slime/run-container.sh." >&2
    exit 1
  fi
}

filter_model_args() {
  if [ "${MOE_GROUPED_GEMM}" = "1" ]; then
    return
  fi
  local filtered_args=()
  local arg
  for arg in "${MODEL_ARGS[@]}"; do
    if [ "${arg}" = "--moe-grouped-gemm" ]; then
      continue
    fi
    filtered_args+=("${arg}")
  done
  MODEL_ARGS=("${filtered_args[@]}")
}

ensure_base_checkpoint() {
  download_hf_checkpoint_if_missing
  # shellcheck disable=SC1090
  source "${SLIME_ROOT}/scripts/models/moonlight.sh"
  CONVERT_MODEL_ARGS=("${MODEL_ARGS[@]}")
  filter_model_args
  if checkpoint_ready "${REF_LOAD_DIR}"; then
    return
  fi
  if [ "${CONVERT_IF_MISSING}" != "1" ]; then
    echo "Missing Megatron torch_dist checkpoint: ${REF_LOAD_DIR}" >&2
    echo "Set SLIME_REF_LOAD_DIR or rerun with SLIME_CONVERT_IF_MISSING=1." >&2
    exit 2
  fi
  echo "Converting ${HF_CHECKPOINT} to ${REF_LOAD_DIR}"
  if [ "${CONVERT_NPROC}" = "1" ]; then
    PYTHONPATH="${MEGATRON_DIR}:${PYTHONPATH:-}" \
      "${PYTHON_BIN}" "${SLIME_ROOT}/tools/convert_hf_to_torch_dist.py" \
      "${CONVERT_MODEL_ARGS[@]}" \
      --hf-checkpoint "${HF_CHECKPOINT}" \
      --save "${REF_LOAD_DIR}"
  else
    PYTHONPATH="${MEGATRON_DIR}:${PYTHONPATH:-}" \
      torchrun --nproc-per-node "${CONVERT_NPROC}" \
      "${SLIME_ROOT}/tools/convert_hf_to_torch_dist.py" \
      "${CONVERT_MODEL_ARGS[@]}" \
      --hf-checkpoint "${HF_CHECKPOINT}" \
      --save "${REF_LOAD_DIR}"
  fi
}

write_frozen_sglang_config() {
  local model_path="$1"
  local config_path="${RUN_ROOT}/sglang/${STAGE}-frozen-sglang.yaml"
  mkdir -p "$(dirname -- "${config_path}")"
  cat >"${config_path}" <<EOF
sglang:
  - name: default
    model_path: "${model_path}"
    update_weights: false
    num_gpus_per_engine: ${ROLLOUT_NUM_GPUS_PER_ENGINE}
    server_groups:
      - worker_type: regular
        num_gpus: ${NUM_GPUS}
        num_gpus_per_engine: ${ROLLOUT_NUM_GPUS_PER_ENGINE}
EOF
  printf "%s" "${config_path}"
}

cleanup_ray() {
  if [ "${SKIP_CLEANUP}" != "1" ] && [ "${USE_EXTERNAL_RAY}" = "0" ]; then
    pkill -9 sglang || true
    sleep 3
    if command -v timeout >/dev/null 2>&1; then
      timeout "${SLIME_RAY_STOP_TIMEOUT_SECONDS:-60}" ray stop --force || true
    else
      ray stop --force || true
    fi
    pkill -9 ray || true
    pkill -9 raylet || true
    pkill -9 gcs_server || true
    pkill -9 redis || true
    sleep 3
  fi
}

VRAM_MONITOR_PID=""
start_vram_monitor() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "nvidia-smi not found; VRAM monitor disabled" >&2
    return
  fi
  echo "timestamp,index,name,memory.used [MiB],memory.total [MiB]" >"${VRAM_LOG}"
  (
    while true; do
      nvidia-smi \
        --query-gpu=timestamp,index,name,memory.used,memory.total \
        --format=csv,noheader,nounits >>"${VRAM_LOG}" 2>/dev/null || true
      sleep "${SLIME_VRAM_POLL_SECONDS:-2}"
    done
  ) &
  VRAM_MONITOR_PID="$!"
}

stop_vram_monitor() {
  if [ -n "${VRAM_MONITOR_PID}" ]; then
    kill "${VRAM_MONITOR_PID}" 2>/dev/null || true
    wait "${VRAM_MONITOR_PID}" 2>/dev/null || true
    VRAM_MONITOR_PID=""
  fi
  if [ -f "${VRAM_LOG}" ]; then
    "${PYTHON_BIN}" - <<PY
import csv
from pathlib import Path

log_path = Path("${VRAM_LOG}")
peak_path = Path("${VRAM_PEAK_FILE}")
peaks = {}
with log_path.open(newline="") as handle:
    reader = csv.reader(handle)
    next(reader, None)
    for row in reader:
        if len(row) < 5:
            continue
        index = row[1].strip()
        name = row[2].strip()
        try:
            used = int(row[3].strip())
            total = int(row[4].strip())
        except ValueError:
            continue
        current = peaks.get(index)
        if current is None or used > current["used"]:
            peaks[index] = {"name": name, "used": used, "total": total}

lines = ["peak_vram_mib_by_gpu:"]
overall = 0
for index in sorted(peaks, key=lambda value: int(value) if value.isdigit() else value):
    item = peaks[index]
    overall = max(overall, item["used"])
    lines.append(f"gpu{index} {item['name']}: {item['used']} / {item['total']} MiB")
lines.append(f"max_peak_vram_mib: {overall}")
peak_path.write_text("\\n".join(lines) + "\\n", encoding="utf-8")
print(peak_path.read_text(encoding="utf-8"), end="")
PY
  fi
}

base_model_args() {
  PERF_ARGS=(
    --tensor-model-parallel-size "${TP_SIZE}"
    --pipeline-model-parallel-size "${PP_SIZE}"
    --context-parallel-size "${CP_SIZE}"
    --expert-model-parallel-size "${EP_SIZE}"
    --expert-tensor-parallel-size "${ETP_SIZE}"
    --recompute-granularity full
    --recompute-method uniform
    --recompute-num-layers 1
    --seq-length "${SEQ_LENGTH}"
  )
  if [ "${USE_DYNAMIC_BATCH_SIZE}" = "1" ] || { [ "${USE_DYNAMIC_BATCH_SIZE}" = "auto" ] && [ "${ATTENTION_BACKEND}" != "local" ]; }; then
    PERF_ARGS+=(--use-dynamic-batch-size --max-tokens-per-gpu "${MAX_TOKENS_PER_GPU}")
  else
    PERF_ARGS+=(--micro-batch-size "${MICRO_BATCH_SIZE}")
  fi
  if [ "${SEQUENCE_PARALLEL}" = "1" ] || { [ "${SEQUENCE_PARALLEL}" = "auto" ] && [ "${ATTENTION_BACKEND}" != "local" ]; }; then
    PERF_ARGS+=(--sequence-parallel)
  fi
  OPTIMIZER_ARGS=(
    --optimizer adam
    --lr "${SLIME_LR:-1e-6}"
    --lr-decay-style constant
    --lr-decay-iters "${EVAL_LR_DECAY_ITERS}"
    --weight-decay 0.1
    --adam-beta1 0.9
    --adam-beta2 0.98
  )
  SGLANG_ARGS=(
    --rollout-num-gpus-per-engine "${ROLLOUT_NUM_GPUS_PER_ENGINE}"
    --sglang-mem-fraction-static "${SGLANG_MEM_FRACTION_STATIC}"
  )
  if [ -n "${SGLANG_CUDA_GRAPH_MAX_BS}" ]; then
    SGLANG_ARGS+=(--sglang-cuda-graph-max-bs "${SGLANG_CUDA_GRAPH_MAX_BS}")
  fi
  if [ "${SLIME_SGLANG_DISABLE_CUSTOM_ALL_REDUCE:-1}" = "1" ]; then
    SGLANG_ARGS+=(--sglang-disable-custom-all-reduce)
  fi
  MISC_ARGS=(
    --attention-dropout 0.0
    --hidden-dropout 0.0
    --accumulate-allreduce-grads-in-fp32
    --attention-softmax-in-fp32
  )
  if [ -n "${ATTENTION_BACKEND}" ]; then
    MISC_ARGS+=(--attention-backend "${ATTENTION_BACKEND}")
  fi
  EXTRA_ARGS=(
    --distributed-timeout-minutes "${DISTRIBUTED_TIMEOUT_MINUTES}"
    --megatron-to-hf-mode "${MEGATRON_TO_HF_MODE}"
    --train-memory-margin-bytes "${SLIME_TRAIN_MEMORY_MARGIN_BYTES:-268435456}"
    --no-save-optim
    --no-save-rng
    --save-debug-rollout-data "${ROLLOUT_DUMP_TEMPLATE}"
  )
  if [ -n "${UPDATE_WEIGHT_BUFFER_SIZE}" ]; then
    EXTRA_ARGS+=(--update-weight-buffer-size "${UPDATE_WEIGHT_BUFFER_SIZE}")
  fi
  if [ "${ATTENTION_BACKEND}" = "local" ] && [ "${SLIME_USE_LOCAL_LAYER_SPEC:-1}" = "1" ]; then
    EXTRA_ARGS+=(--no-persist-layer-norm --spec "${LOCAL_LAYER_SPEC_MODULE}" "${LOCAL_LAYER_SPEC_NAME}")
  fi
  if [ -n "${SLIME_EXTRA_ARGS:-}" ]; then
    read -r -a SLIME_EXTRA_ARGS_ARRAY <<<"${SLIME_EXTRA_ARGS}"
    EXTRA_ARGS+=("${SLIME_EXTRA_ARGS_ARRAY[@]}")
  fi
}

wandb_args() {
  WANDB_ARGS=()
  WANDB_KEY="${WANDB_API_KEY:-${WANDB_KEY:-}}"
  WANDB_ALREADY_LOGGED_IN=0
  if [ -f "${HOME}/.netrc" ] || [ -f "${HOME}/.config/wandb/settings" ]; then
    WANDB_ALREADY_LOGGED_IN=1
  fi
  if [ -n "${WANDB_KEY}" ] || [ "${WANDB_ALREADY_LOGGED_IN}" = "1" ] || [ -n "${SLIME_WANDB_PROJECT:-}" ]; then
    WANDB_ARGS=(
      --use-wandb
      --wandb-project "${SLIME_WANDB_PROJECT:-slime-moonlight-multi-swe-cpp}"
      --wandb-group "${SLIME_WANDB_GROUP:-${RUN_ID}}"
      --wandb-run-id "${SLIME_WANDB_RUN_ID:-${RUN_ID}-${STAGE}}"
      --disable-wandb-random-suffix
    )
    if [ -n "${WANDB_KEY}" ]; then
      WANDB_ARGS+=(--wandb-key "${WANDB_KEY}")
    fi
  fi
}

stage_args() {
  CKPT_ARGS=(
    --hf-checkpoint "${HF_CHECKPOINT}"
    --ref-load "${REF_LOAD_DIR}"
    --load "${REF_LOAD_DIR}"
    --save "${RUN_ROOT}/checkpoints/base-eval"
    --save-interval "${SAVE_INTERVAL}"
  )
  TASK_ARGS=(
    --debug-rollout-only
    --prompt-data "${DATA_DIR}/eval/cpp.jsonl"
    --input-key prompt
    --label-key label
    --metadata-key metadata
    --apply-chat-template
    --reward-key score
    --num-rollout 0
    --rollout-batch-size "${ROLLOUT_BATCH_SIZE}"
    --n-samples-per-prompt 1
    --global-batch-size "${GLOBAL_BATCH_SIZE}"
    --eval-interval 1
    --eval-prompt-data multi_swe_cpp "${DATA_DIR}/eval/cpp.jsonl"
    --n-samples-per-eval-prompt "${EVAL_N_SAMPLES_PER_PROMPT}"
    --eval-max-response-len "${EVAL_MAX_RESPONSE_LEN}"
    --eval-temperature "${EVAL_TEMPERATURE}"
    --eval-top-p "${EVAL_TOP_P}"
  )
  ALGO_ARGS=()
  CUSTOM_ARGS=(--custom-rm-path w8_biayn.integrations.slime_multi_swe_cpp.reward_func)
  SGLANG_CONFIG_ARGS=(--sglang-config "$(write_frozen_sglang_config "${HF_CHECKPOINT}")")
}

append_optimizer_offload_args() {
  if [ "${OPTIMIZER_CPU_OFFLOAD}" = "1" ]; then
    OPTIMIZER_ARGS+=(--optimizer-cpu-offload --overlap-cpu-optimizer-d2h-h2d --use-precision-aware-optimizer)
  fi
}

start_ray_if_needed() {
  if [ "${USE_EXTERNAL_RAY}" = "0" ]; then
    export MASTER_ADDR="${MASTER_ADDR:-127.0.0.1}"
    export no_proxy="127.0.0.1,${MASTER_ADDR}"
    if [ -n "${RAY_MEMORY_USAGE_THRESHOLD}" ]; then
      export RAY_memory_usage_threshold="${RAY_MEMORY_USAGE_THRESHOLD}"
    fi
    if [ -n "${RAY_MEMORY_MONITOR_REFRESH_MS}" ]; then
      export RAY_memory_monitor_refresh_ms="${RAY_MEMORY_MONITOR_REFRESH_MS}"
    fi
    ray start --head --node-ip-address "${MASTER_ADDR}" --num-gpus "${NUM_GPUS}" \
      --disable-usage-stats --dashboard-host=0.0.0.0 --dashboard-port=8265
  fi
}

runtime_env_json() {
  "${PYTHON_BIN}" - <<PY
import json
import os

paths = ["${MEGATRON_DIR}", "${REPO_ROOT}/src", "${SLIME_ROOT}", os.environ.get("PYTHONPATH", "")]
env = {
    "PYTHONPATH": ":".join(path for path in paths if path),
    "CUDA_DEVICE_MAX_CONNECTIONS": "1",
    "NCCL_NVLS_ENABLE": "${HAS_NVLINK}",
    "W8_BIAYN_DATA_DIR": "${DATA_DIR}",
    "W8_SLIME_MULTI_SWE_SANDBOX_IMAGE": os.environ.get("W8_SLIME_MULTI_SWE_SANDBOX_IMAGE", "${MULTI_SWE_SANDBOX_IMAGE}"),
    "W8_SLIME_MULTI_SWE_TEST_TIMEOUT_SECONDS": os.environ.get("W8_SLIME_MULTI_SWE_TEST_TIMEOUT_SECONDS", "${MULTI_SWE_TEST_TIMEOUT_SECONDS}"),
    "W8_SLIME_MULTI_SWE_INCLUDE_LOGS": os.environ.get("W8_SLIME_MULTI_SWE_INCLUDE_LOGS", "0"),
    "W8_SLIME_MULTI_SWE_ORACLE_SETUP_CHECK": os.environ.get("W8_SLIME_MULTI_SWE_ORACLE_SETUP_CHECK", "${MULTI_SWE_ORACLE_SETUP_CHECK}"),
    "SGLANG_DISABLE_TP_MEMORY_INBALANCE_CHECK": "${SGLANG_DISABLE_TP_MEMORY_INBALANCE_CHECK}",
    "SGLANG_ENABLE_TP_MEMORY_INBALANCE_CHECK": "${SGLANG_ENABLE_TP_MEMORY_INBALANCE_CHECK}",
    "SGL_DISABLE_TP_MEMORY_INBALANCE_CHECK": "${SGLANG_DISABLE_TP_MEMORY_INBALANCE_CHECK}",
    "NVSHMEM_DISABLE_NCCL": "${NVSHMEM_DISABLE_NCCL}",
}
attention_backend = "${ATTENTION_BACKEND}".strip().lower()
nvte_flags_by_backend = {
    "flash": {"NVTE_FLASH_ATTN": "1", "NVTE_FUSED_ATTN": "0", "NVTE_UNFUSED_ATTN": "0"},
    "fused": {"NVTE_FLASH_ATTN": "0", "NVTE_FUSED_ATTN": "1", "NVTE_UNFUSED_ATTN": "0"},
    "unfused": {"NVTE_FLASH_ATTN": "0", "NVTE_FUSED_ATTN": "0", "NVTE_UNFUSED_ATTN": "1"},
    "local": {"NVTE_FLASH_ATTN": "0", "NVTE_FUSED_ATTN": "0", "NVTE_UNFUSED_ATTN": "0"},
}
for key, value in nvte_flags_by_backend.get(attention_backend, {}).items():
    env[key] = os.environ.get(f"SLIME_{key}", value)
for key in (
    "CUDA_HOME",
    "PATH",
    "LD_LIBRARY_PATH",
    "HF_HOME",
    "WANDB_API_KEY",
    "WANDB_KEY",
    "DOCKER_HOST",
):
    if key in os.environ:
        env[key] = os.environ[key]
print(json.dumps({"env_vars": env}))
PY
}

write_receipt() {
  local status="$1"
  local ray_submit_status="$2"
  local ray_job_id="$3"
  local ray_job_terminal_status="$4"
  local max_vram_mib=""
  if [ -f "${VRAM_PEAK_FILE}" ]; then
    max_vram_mib="$(awk '/max_peak_vram_mib:/ {print $2}' "${VRAM_PEAK_FILE}" | tail -n 1)"
  fi
  cat >"${RUN_RECEIPT}" <<EOF
status=${status}
stage=${STAGE}
stage_label=${STAGE_LABEL}
ray_submit_status=${ray_submit_status}
ray_job_id=${ray_job_id}
ray_job_terminal_status=${ray_job_terminal_status}
ray_memory_usage_threshold=${RAY_MEMORY_USAGE_THRESHOLD:-}
run_id=${RUN_ID}
run_root=${RUN_ROOT}
stage_root=${STAGE_ROOT}
log_file=${LOG_FILE}
vram_log=${VRAM_LOG}
vram_peak_file=${VRAM_PEAK_FILE}
max_vram_mib=${max_vram_mib}
data_dir=${DATA_DIR}
multi_swe_source=${MULTI_SWE_SOURCE}
multi_swe_jsonl=${MULTI_SWE_JSONL}
eval_limit=${EVAL_LIMIT}
hf_checkpoint=${HF_CHECKPOINT}
hf_model_id=${HF_MODEL_ID}
download_hf_checkpoint=${DOWNLOAD_HF_CHECKPOINT}
hf_checkpoint_was_downloaded=${HF_CHECKPOINT_WAS_DOWNLOADED}
ref_load=${REF_LOAD_DIR}
distributed_timeout_minutes=${DISTRIBUTED_TIMEOUT_MINUTES}
megatron_to_hf_mode=${MEGATRON_TO_HF_MODE}
num_gpus=${NUM_GPUS}
tp_size=${TP_SIZE}
ep_size=${EP_SIZE}
max_tokens_per_gpu=${MAX_TOKENS_PER_GPU}
micro_batch_size=${MICRO_BATCH_SIZE}
seq_length=${SEQ_LENGTH}
optimizer_cpu_offload=${OPTIMIZER_CPU_OFFLOAD}
nvshmem_disable_nccl=${NVSHMEM_DISABLE_NCCL}
update_weight_buffer_size=${UPDATE_WEIGHT_BUFFER_SIZE}
sglang_mem_fraction=${SGLANG_MEM_FRACTION_STATIC}
sglang_cuda_graph_max_bs=${SGLANG_CUDA_GRAPH_MAX_BS}
sglang_disable_tp_memory_inbalance_check=${SGLANG_DISABLE_TP_MEMORY_INBALANCE_CHECK}
sglang_enable_tp_memory_inbalance_check=${SGLANG_ENABLE_TP_MEMORY_INBALANCE_CHECK}
eval_max_response_len=${EVAL_MAX_RESPONSE_LEN}
eval_temperature=${EVAL_TEMPERATURE}
eval_top_p=${EVAL_TOP_P}
multi_swe_sandbox_image=${MULTI_SWE_SANDBOX_IMAGE}
multi_swe_test_timeout_seconds=${MULTI_SWE_TEST_TIMEOUT_SECONDS}
multi_swe_oracle_setup_check=${MULTI_SWE_ORACLE_SETUP_CHECK}
wandb_project=${SLIME_WANDB_PROJECT:-slime-moonlight-multi-swe-cpp}
wandb_group=${SLIME_WANDB_GROUP:-${RUN_ID}}
wandb_run_id=${SLIME_WANDB_RUN_ID:-${RUN_ID}-${STAGE}}
rollout_dump_template=${ROLLOUT_DUMP_TEMPLATE}
eval_dump_path=${EVAL_DUMP_PATH}
summary_path=${RUN_ROOT}/eval/base.summary.json
records_path=${RUN_ROOT}/eval/base.records.jsonl
oracle_records_path=${RUN_ROOT}/eval/base.oracle.records.jsonl
EOF
}

aggregate_eval() {
  if [ ! -f "${EVAL_DUMP_PATH}" ]; then
    echo "Missing eval debug rollout dump: ${EVAL_DUMP_PATH}" >&2
    exit 2
  fi
  AGGREGATE_ARGS=(
    -m w8_biayn.integrations.slime_multi_swe_cpp aggregate-debug
    --label "${STAGE_LABEL}"
    --debug-rollout "${EVAL_DUMP_PATH}"
    --out "${RUN_ROOT}/eval"
    --data-root "${DATA_DIR}"
  )
  if [ "${SLIME_MULTI_SWE_SKIP_ORACLE_CHECK:-0}" = "1" ]; then
    AGGREGATE_ARGS+=(--skip-oracle-check)
  fi
  run_repo_python "${AGGREGATE_ARGS[@]}"
}

submit_slime_job() {
  ensure_data
  ensure_slime_runtime
  ensure_base_checkpoint
  base_model_args
  wandb_args
  stage_args
  append_optimizer_offload_args

  COLOCATE_ARGS=()
  if [ "${COLOCATE}" = "1" ]; then
    COLOCATE_ARGS=(--colocate)
  fi

  if [ "${SLIME_TRACE:-1}" = "1" ]; then
    set -x
  fi
  ulimit -Sn "${SLIME_NOFILE_SOFT_LIMIT:-65536}" 2>/dev/null || true
  export PYTHONUNBUFFERED=1
  cleanup_ray

  TOPO_OUTPUT="$(nvidia-smi topo -m 2>/dev/null || true)"
  NVLINK_COUNT="$(grep -o 'NV[0-9][0-9]*' <<<"${TOPO_OUTPUT}" | wc -l | tr -d ' ' || true)"
  if [ "${NVLINK_COUNT}" -gt 0 ]; then
    HAS_NVLINK=1
  else
    HAS_NVLINK=0
  fi
  start_ray_if_needed
  RUNTIME_ENV_JSON="$(runtime_env_json)"
  cd "${SLIME_ROOT}"

  RAY_ADDRESS="${SLIME_RAY_ADDRESS:-http://127.0.0.1:8265}"
  RAY_JOB_ID="${SLIME_RAY_JOB_ID:-${RUN_ID}-${STAGE}}"
  RAY_JOB_ID="$(printf "%s" "${RAY_JOB_ID}" | tr -c "A-Za-z0-9_-" "-")"
  RAY_JOB_TERMINAL_STATUS="unknown"
  RAY_STATUS_STARTED_AT="$(date +%s)"
  RAY_STATUS_TIMEOUT_SECONDS="${SLIME_RAY_STATUS_TIMEOUT_SECONDS:-7200}"

  echo "Moonlight Multi-SWE C++ SLIME stage: ${STAGE}"
  echo "Run root: ${RUN_ROOT}"
  echo "Log: ${LOG_FILE}"
  echo "VRAM log: ${VRAM_LOG}"
  start_vram_monitor
  trap stop_vram_monitor EXIT

  set +e
  ray job submit --address="${RAY_ADDRESS}" \
    --submission-id="${RAY_JOB_ID}" \
    --log-style=record \
    --log-color=false \
    --runtime-env-json="${RUNTIME_ENV_JSON}" \
    -- "${PYTHON_BIN}" -u -m "${SLIME_TRAIN_MODULE}" \
    --actor-num-nodes 1 \
    --actor-num-gpus-per-node "${NUM_GPUS}" \
    "${COLOCATE_ARGS[@]}" \
    "${MODEL_ARGS[@]}" \
    "${CKPT_ARGS[@]}" \
    "${TASK_ARGS[@]}" \
    "${OPTIMIZER_ARGS[@]}" \
    "${ALGO_ARGS[@]}" \
    "${WANDB_ARGS[@]}" \
    "${PERF_ARGS[@]}" \
    "${SGLANG_ARGS[@]}" \
    "${SGLANG_CONFIG_ARGS[@]}" \
    "${MISC_ARGS[@]}" \
    "${EXTRA_ARGS[@]}" \
    "${CUSTOM_ARGS[@]}" \
    2>&1 | tee "${LOG_FILE}"
  RAY_SUBMIT_STATUS="${PIPESTATUS[0]}"
  RAY_STATUS="${RAY_SUBMIT_STATUS}"
  if [ "${RAY_SUBMIT_STATUS}" = "0" ]; then
    while true; do
      STATUS_OUTPUT="$(ray job status --address="${RAY_ADDRESS}" --log-style=record --log-color=false "${RAY_JOB_ID}" 2>&1)"
      STATUS_COMMAND_STATUS="$?"
      printf '%s\n' "${STATUS_OUTPUT}" | tee -a "${LOG_FILE}"
      if [ "${STATUS_COMMAND_STATUS}" != "0" ]; then
        RAY_STATUS="${STATUS_COMMAND_STATUS}"
        break
      fi
      RAY_JOB_TERMINAL_STATUS="$(printf '%s\n' "${STATUS_OUTPUT}" | sed -n "s/.*Status for job '.*': \\([A-Z_]*\\).*/\\1/p" | tail -n 1)"
      if [ -z "${RAY_JOB_TERMINAL_STATUS}" ]; then
        if grep -qi "Job '.*' succeeded" <<<"${STATUS_OUTPUT}"; then
          RAY_JOB_TERMINAL_STATUS="SUCCEEDED"
        elif grep -qi "Job '.*' failed" <<<"${STATUS_OUTPUT}"; then
          RAY_JOB_TERMINAL_STATUS="FAILED"
        elif grep -qi "Job '.*' stopped" <<<"${STATUS_OUTPUT}"; then
          RAY_JOB_TERMINAL_STATUS="STOPPED"
        fi
      fi
      case "${RAY_JOB_TERMINAL_STATUS}" in
        SUCCEEDED)
          RAY_STATUS=0
          break
          ;;
        FAILED | STOPPED)
          RAY_STATUS=1
          break
          ;;
        PENDING | RUNNING)
          if [ "${RAY_STATUS_TIMEOUT_SECONDS}" != "0" ]; then
            NOW_SECONDS="$(date +%s)"
            if [ $((NOW_SECONDS - RAY_STATUS_STARTED_AT)) -ge "${RAY_STATUS_TIMEOUT_SECONDS}" ]; then
              echo "Ray job ${RAY_JOB_ID} timed out after ${RAY_STATUS_TIMEOUT_SECONDS}s while ${RAY_JOB_TERMINAL_STATUS}" | tee -a "${LOG_FILE}"
              RAY_JOB_TERMINAL_STATUS="TIMEOUT"
              RAY_STATUS=124
              break
            fi
          fi
          sleep "${SLIME_RAY_STATUS_POLL_SECONDS:-15}"
          ;;
        *)
          RAY_STATUS=1
          break
          ;;
      esac
    done
    ray job logs --address="${RAY_ADDRESS}" --log-style=record --log-color=false "${RAY_JOB_ID}" >>"${LOG_FILE}" 2>&1 || true
  fi
  set -e
  stop_vram_monitor
  trap - EXIT
  write_receipt "${RAY_STATUS}" "${RAY_SUBMIT_STATUS}" "${RAY_JOB_ID}" "${RAY_JOB_TERMINAL_STATUS}"
  echo "RUN_RECEIPT=${RUN_RECEIPT}"
  if [ "${RAY_STATUS}" = "0" ]; then
    aggregate_eval
  fi
  exit "${RAY_STATUS}"
}

case "${STAGE}" in
  prepare-data)
    prepare_data
    ;;
  base-eval)
    submit_slime_job
    ;;
  *)
    echo "unknown stage: ${STAGE}" >&2
    echo "usage: $0 <prepare-data|base-eval>" >&2
    exit 2
    ;;
esac

