#!/usr/bin/env bash
# Miles GRPO LoRA rank-16 runner for Moonlight-16B-A3B on the PIE C++ task.

set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." &>/dev/null && pwd)"
if [ -n "${MILES_ROOT:-}" ]; then
  MILES_ROOT="${MILES_ROOT}"
elif [ -d /root/miles ]; then
  MILES_ROOT="/root/miles"
else
  MILES_ROOT="/root/slime"
fi
PYTHON_BIN="${MILES_PYTHON:-python3}"
MODEL_ARGS_FILE="${MILES_MODEL_ARGS_FILE:-moonlight.sh}"
MODEL_ARGS_PATH="${MILES_MODEL_ARGS_PATH:-${MILES_ROOT}/scripts/models/${MODEL_ARGS_FILE}}"

RUN_ID="${MILES_RUN_ID:-moonlight_pie_cpp_lora_r16_$(date +%Y%m%d_%H%M%S)}"
RUN_ROOT="${MILES_RUN_ROOT:-${REPO_ROOT}/.w8-biayn/miles/moonlight-cpp-perf/runs/${RUN_ID}}"
DATA_DIR="${MILES_CPP_DATA_DIR:-${RUN_ROOT}/data}"
TASKS_DIR="${MILES_CPP_TASKS_DIR:-${REPO_ROOT}/.w8-biayn/data/tasks-small}"
TRAIN_LIMIT="${MILES_CPP_TRAIN_LIMIT:-2}"
EVAL_LIMIT="${MILES_CPP_EVAL_LIMIT:-2}"
EVAL_SPLITS="${MILES_CPP_EVAL_SPLITS:-validation,test}"
SORT_BY_SIZE="${MILES_CPP_SORT_BY_SIZE:-1}"
FILTER_TRAIN_ORACLE_FULL_MARKS="${MILES_CPP_FILTER_TRAIN_ORACLE_FULL_MARKS:-0}"
ORACLE_FILTER_WORKERS="${MILES_CPP_ORACLE_FILTER_WORKERS:-8}"

HF_CHECKPOINT="${MILES_HF_CHECKPOINT:-/root/models/Moonlight-16B-A3B-Instruct}"
REF_LOAD_DIR="${MILES_REF_LOAD_DIR:-${HF_CHECKPOINT}_torch_dist}"
SAVE_DIR="${MILES_SAVE_DIR:-${RUN_ROOT}/checkpoints/grpo_lora_r16}"

GPUS_PER_NODE="${MILES_GPUS_PER_NODE:-4}"
TP_SIZE="${MILES_TENSOR_MODEL_PARALLEL_SIZE:-2}"
PP_SIZE="${MILES_PIPELINE_MODEL_PARALLEL_SIZE:-1}"
CP_SIZE="${MILES_CONTEXT_PARALLEL_SIZE:-1}"
EP_SIZE="${MILES_EXPERT_MODEL_PARALLEL_SIZE:-4}"
ETP_SIZE="${MILES_EXPERT_TENSOR_PARALLEL_SIZE:-1}"
MOE_TOKEN_DISPATCHER_TYPE="${MILES_MOE_TOKEN_DISPATCHER_TYPE:-}"
ATTENTION_BACKEND="${MILES_ATTENTION_BACKEND:-}"
SEQ_LENGTH="${MILES_SEQ_LENGTH:-2048}"
MAX_TOKENS_PER_GPU="${MILES_MAX_TOKENS_PER_GPU:-4096}"
MICRO_BATCH_SIZE="${MILES_MICRO_BATCH_SIZE:-1}"

NUM_ROLLOUT="${MILES_NUM_ROLLOUT:-1}"
ROLLOUT_BATCH_SIZE="${MILES_ROLLOUT_BATCH_SIZE:-2}"
N_SAMPLES_PER_PROMPT="${MILES_N_SAMPLES_PER_PROMPT:-2}"
GLOBAL_BATCH_SIZE="${MILES_GLOBAL_BATCH_SIZE:-4}"
GRPO_ROLLOUT_SHUFFLE="${MILES_GRPO_ROLLOUT_SHUFFLE:-1}"
ROLLOUT_MAX_RESPONSE_LEN="${MILES_ROLLOUT_MAX_RESPONSE_LEN:-1024}"
ROLLOUT_TEMPERATURE="${MILES_ROLLOUT_TEMPERATURE:-1.0}"
APPLY_CHAT_TEMPLATE_KWARGS="${MILES_APPLY_CHAT_TEMPLATE_KWARGS:-}"
TRAIN_MODULE="${MILES_TRAIN_MODULE:-}"
EVAL_INTERVAL="${MILES_EVAL_INTERVAL:-1}"
EVAL_N_SAMPLES_PER_PROMPT="${MILES_EVAL_N_SAMPLES_PER_PROMPT:-1}"
EVAL_MAX_RESPONSE_LEN="${MILES_EVAL_MAX_RESPONSE_LEN:-1536}"
EVAL_PROMPT_DATA="${MILES_EVAL_PROMPT_DATA:-}"

LORA_RANK="${MILES_LORA_RANK:-16}"
LORA_ALPHA="${MILES_LORA_ALPHA:-32}"
LORA_TARGET_MODULES="${MILES_LORA_TARGET_MODULES:-gate_proj,up_proj,down_proj}"
SGLANG_LORA_TARGET_MODULES="${MILES_SGLANG_LORA_TARGET_MODULES:-${LORA_TARGET_MODULES}}"
read -r -a SGLANG_LORA_TARGET_MODULE_ARGS <<< "${SGLANG_LORA_TARGET_MODULES//,/ }"
EXPERTS_SHARED_OUTER_LORAS="${MILES_EXPERTS_SHARED_OUTER_LORAS:-0}"
LORA_BASE_CPU_BACKUP="${MILES_LORA_BASE_CPU_BACKUP:-0}"
NO_GRADIENT_ACCUMULATION_FUSION="${MILES_NO_GRADIENT_ACCUMULATION_FUSION:-0}"
SGLANG_LORA_USE_VIRTUAL_EXPERTS="${MILES_SGLANG_LORA_USE_VIRTUAL_EXPERTS:-0}"
SGLANG_MEM_FRACTION_STATIC="${MILES_SGLANG_MEM_FRACTION_STATIC:-0.25}"
SGLANG_SERVER_CONCURRENCY="${MILES_SGLANG_SERVER_CONCURRENCY:-512}"
SGLANG_CUDA_GRAPH_MAX_BS="${MILES_SGLANG_CUDA_GRAPH_MAX_BS:-4}"

WANDB_PROJECT="${MILES_WANDB_PROJECT:-miles-moonlight-cpp-perf}"
WANDB_GROUP="${MILES_WANDB_GROUP:-moonlight-pie-cpp-lora-r16}"
WANDB_RUN_ID="${MILES_WANDB_RUN_ID:-${RUN_ID}}"

STAGE_ROOT="${RUN_ROOT}/grpo_lora_r16"
LOG_FILE="${STAGE_ROOT}/run.log"
VRAM_LOG="${STAGE_ROOT}/vram_usage.csv"
VRAM_PEAK_FILE="${STAGE_ROOT}/vram_peak.txt"
RUN_RECEIPT="${STAGE_ROOT}/run_receipt.txt"
ROLLOUT_DUMP_TEMPLATE="${RUN_ROOT}/rollout_dumps/grpo_{rollout_id}.pt"

mkdir -p "${STAGE_ROOT}" "${RUN_ROOT}/rollout_dumps" "${SAVE_DIR}"
exec > >(tee -a "${LOG_FILE}") 2>&1

echo "run_id=${RUN_ID}"
echo "run_root=${RUN_ROOT}"
echo "tasks_dir=${TASKS_DIR}"
echo "hf_checkpoint=${HF_CHECKPOINT}"
echo "model_args_path=${MODEL_ARGS_PATH}"
echo "ref_load=${REF_LOAD_DIR}"
echo "save_dir=${SAVE_DIR}"
echo "seq_length=${SEQ_LENGTH}"
echo "rollout_max_response_len=${ROLLOUT_MAX_RESPONSE_LEN}"
echo "eval_max_response_len=${EVAL_MAX_RESPONSE_LEN}"

if [ ! -d "${MILES_ROOT}" ]; then
  echo "Missing Miles root: ${MILES_ROOT}" >&2
  exit 2
fi
if [ ! -f "${HF_CHECKPOINT}/config.json" ]; then
  echo "Missing HF checkpoint: ${HF_CHECKPOINT}" >&2
  exit 2
fi
if [ ! -f "${REF_LOAD_DIR}/latest_checkpointed_iteration.txt" ]; then
  echo "Missing Megatron checkpoint: ${REF_LOAD_DIR}" >&2
  exit 2
fi
if [ ! -f "${MODEL_ARGS_PATH}" ]; then
  echo "Missing model args: ${MODEL_ARGS_PATH}" >&2
  exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "Missing docker CLI inside container. Mount it with -v /usr/bin/docker:/usr/bin/docker:ro." >&2
  exit 2
fi
if ! docker image inspect "${W8_CPP_SANDBOX_IMAGE:-w8-biayn-cpp-perf:latest}" >/dev/null 2>&1; then
  echo "Missing PIE C++ sandbox image: ${W8_CPP_SANDBOX_IMAGE:-w8-biayn-cpp-perf:latest}" >&2
  exit 2
fi

BUILD_DATA_ARGS=(
  -m w8_biayn.integrations.slime_cpp_perf build-data
  --tasks-dir "${TASKS_DIR}"
  --out "${DATA_DIR}"
  --train-limit "${TRAIN_LIMIT}"
  --eval-limit "${EVAL_LIMIT}"
  --eval-splits "${EVAL_SPLITS}"
  --profile "miles-moonlight-cpp-perf-lora-r16"
  --run-id "${RUN_ID}"
  --force
)
if [ "${SORT_BY_SIZE}" = "1" ]; then
  BUILD_DATA_ARGS+=(--sort-by-size)
fi
if [ "${FILTER_TRAIN_ORACLE_FULL_MARKS}" = "1" ]; then
  BUILD_DATA_ARGS+=(--filter-train-oracle-full-marks --oracle-filter-workers "${ORACLE_FILTER_WORKERS}")
fi

# Skip the (destructive, --force) rebuild when the data dir is already
# populated — same contract as the SFT runner's manifest guard.
if [ ! -f "${DATA_DIR}/grpo/train.jsonl" ]; then
  PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" "${PYTHON_BIN}" "${BUILD_DATA_ARGS[@]}"
fi
if [ ! -f "${DATA_DIR}/grpo/train.jsonl" ]; then
  echo "Missing GRPO train data: ${DATA_DIR}/grpo/train.jsonl" >&2
  exit 2
fi

monitor_vram() {
  echo "timestamp,index,memory.used,memory.total,utilization.gpu" > "${VRAM_LOG}"
  while true; do
    nvidia-smi --query-gpu=timestamp,index,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits >> "${VRAM_LOG}" || true
    sleep 2
  done
}

monitor_vram &
VRAM_MONITOR_PID=$!
cleanup() {
  kill "${VRAM_MONITOR_PID}" >/dev/null 2>&1 || true
  if [ -s "${VRAM_LOG}" ]; then
    awk -F, 'NR>1 {gsub(/^[ \t]+|[ \t]+$/, "", $3); if ($3+0 > max) max=$3+0} END {print "max_memory_used_mib=" max}' "${VRAM_LOG}" > "${VRAM_PEAK_FILE}" || true
    cat "${VRAM_PEAK_FILE}" || true
  fi
}
trap cleanup EXIT

write_receipt() {
  local status="$1"
  local ray_status="$2"
  local max_memory_used_mib=""
  if [ -s "${VRAM_LOG}" ]; then
    awk -F, 'NR>1 {gsub(/^[ \t]+|[ \t]+$/, "", $3); if ($3+0 > max) max=$3+0} END {print "max_memory_used_mib=" max}' "${VRAM_LOG}" > "${VRAM_PEAK_FILE}" || true
  fi
  if [ -s "${VRAM_PEAK_FILE}" ]; then
    max_memory_used_mib="$(awk -F= '/max_memory_used_mib/ {print $2}' "${VRAM_PEAK_FILE}" | tail -n 1)"
  fi
  cat >"${RUN_RECEIPT}" <<EOF
status=${status}
ray_status=${ray_status}
run_id=${RUN_ID}
run_root=${RUN_ROOT}
stage_root=${STAGE_ROOT}
log_file=${LOG_FILE}
vram_log=${VRAM_LOG}
vram_peak_file=${VRAM_PEAK_FILE}
max_memory_used_mib=${max_memory_used_mib}
data_dir=${DATA_DIR}
tasks_dir=${TASKS_DIR}
hf_checkpoint=${HF_CHECKPOINT}
model_args_path=${MODEL_ARGS_PATH}
ref_load=${REF_LOAD_DIR}
save_dir=${SAVE_DIR}
seq_length=${SEQ_LENGTH}
rollout_max_response_len=${ROLLOUT_MAX_RESPONSE_LEN}
eval_max_response_len=${EVAL_MAX_RESPONSE_LEN}
max_tokens_per_gpu=${MAX_TOKENS_PER_GPU}
micro_batch_size=${MICRO_BATCH_SIZE}
num_rollout=${NUM_ROLLOUT}
rollout_batch_size=${ROLLOUT_BATCH_SIZE}
n_samples_per_prompt=${N_SAMPLES_PER_PROMPT}
global_batch_size=${GLOBAL_BATCH_SIZE}
train_module=${TRAIN_MODULE}
lora_rank=${LORA_RANK}
lora_alpha=${LORA_ALPHA}
wandb_project=${WANDB_PROJECT}
wandb_group=${WANDB_GROUP}
wandb_run_id=${WANDB_RUN_ID}
EOF
  cat "${RUN_RECEIPT}"
}

pkill -9 sglang >/dev/null 2>&1 || true
ray stop --force >/dev/null 2>&1 || true
pkill -9 ray >/dev/null 2>&1 || true
pkill -9 python >/dev/null 2>&1 || true
pkill -9 redis >/dev/null 2>&1 || true

export PYTHONBUFFERED=16
export MASTER_ADDR="${MILES_MASTER_ADDR:-${MASTER_ADDR:-127.0.0.1}}"
RAY_NODE_IP_ADDRESS="${MILES_RAY_NODE_IP_ADDRESS:-127.0.0.1}"
RAY_DASHBOARD_HOST="${MILES_RAY_DASHBOARD_HOST:-127.0.0.1}"
RAY_DASHBOARD_PORT="${MILES_RAY_DASHBOARD_PORT:-8265}"
export no_proxy="127.0.0.1,${MASTER_ADDR},${RAY_NODE_IP_ADDRESS},${RAY_DASHBOARD_HOST}"
export W8_BIAYN_DATA_DIR="${DATA_DIR}"
export W8_CPP_SANDBOX_IMAGE="${W8_CPP_SANDBOX_IMAGE:-w8-biayn-cpp-perf:latest}"

NVLINK_COUNT="$(nvidia-smi topo -m 2>/dev/null | grep -o 'NV[0-9][0-9]*' | wc -l || true)"
if [ "${NVLINK_COUNT}" -gt 0 ]; then
  HAS_NVLINK=1
else
  HAS_NVLINK=0
fi
echo "HAS_NVLINK=${HAS_NVLINK} detected_nvlink_refs=${NVLINK_COUNT}"

cd "${MILES_ROOT}"
source "${MODEL_ARGS_PATH}"

CKPT_ARGS=(
  --hf-checkpoint "${HF_CHECKPOINT}"
  --load "${REF_LOAD_DIR}"
  --save "${SAVE_DIR}"
  --save-interval "${MILES_SAVE_INTERVAL:-1}"
  --megatron-to-hf-mode bridge
)
# The ref model is only needed for KL/ref-logprob paths. With kl 0 it is pure
# overhead, and its per-cycle tag switching is under investigation for LoRA
# state reversion (#11); MILES_NO_REF=1 drops it.
if [ "${MILES_NO_REF:-0}" != "1" ]; then
  CKPT_ARGS+=(--ref-load "${REF_LOAD_DIR}")
fi

LORA_ARGS=(
  --lora-rank "${LORA_RANK}"
  --lora-alpha "${LORA_ALPHA}"
  --lora-dropout 0.0
  --target-modules "${LORA_TARGET_MODULES}"
  --sglang-lora-backend triton
  --sglang-enable-lora
  --sglang-max-lora-rank "${LORA_RANK}"
  --sglang-lora-target-modules "${SGLANG_LORA_TARGET_MODULE_ARGS[@]}"
)
# Initialize adapter weights from a prior run (e.g. GRPO warm-started from the
# SFT adapter): point at an iter_*/adapter dir with Megatron-native shards.
LORA_ADAPTER_PATH="${MILES_LORA_ADAPTER_PATH:-}"
if [ -n "${LORA_ADAPTER_PATH}" ]; then
  LORA_ARGS+=(--lora-adapter-path "${LORA_ADAPTER_PATH}")
fi
if [ "${EXPERTS_SHARED_OUTER_LORAS}" = "1" ]; then
  LORA_ARGS+=(--experts-shared-outer-loras)
fi
if [ "${LORA_BASE_CPU_BACKUP}" = "1" ]; then
  LORA_ARGS+=(--lora-base-cpu-backup)
fi
if [ "${NO_GRADIENT_ACCUMULATION_FUSION}" = "1" ]; then
  LORA_ARGS+=(--no-gradient-accumulation-fusion)
fi
if [ "${SGLANG_LORA_USE_VIRTUAL_EXPERTS}" = "1" ]; then
  LORA_ARGS+=(--sglang-lora-use-virtual-experts)
fi

ROLLOUT_ARGS=(
  --prompt-data "${DATA_DIR}/grpo/train.jsonl"
  --input-key prompt
  --label-key label
  --metadata-key metadata
  --apply-chat-template
  --custom-rm-path w8_biayn.integrations.slime_cpp_perf.reward_func
  --reward-key score
  --num-rollout "${NUM_ROLLOUT}"
  --rollout-batch-size "${ROLLOUT_BATCH_SIZE}"
  --n-samples-per-prompt "${N_SAMPLES_PER_PROMPT}"
  --rollout-max-response-len "${ROLLOUT_MAX_RESPONSE_LEN}"
  --rollout-temperature "${ROLLOUT_TEMPERATURE}"
  --global-batch-size "${GLOBAL_BATCH_SIZE}"
)
if [ -n "${APPLY_CHAT_TEMPLATE_KWARGS}" ]; then
  ROLLOUT_ARGS+=(--apply-chat-template-kwargs "${APPLY_CHAT_TEMPLATE_KWARGS}")
fi
if [ "${GRPO_ROLLOUT_SHUFFLE}" = "1" ]; then
  ROLLOUT_ARGS+=(--rollout-shuffle)
fi

EVAL_ARGS=(
  --eval-interval "${EVAL_INTERVAL}"
  --eval-prompt-data pie_cpp "${EVAL_PROMPT_DATA:-${DATA_DIR}/eval/validation.jsonl}"
  --eval-input-key prompt
  --eval-label-key label
  --n-samples-per-eval-prompt "${EVAL_N_SAMPLES_PER_PROMPT}"
  --eval-max-response-len "${EVAL_MAX_RESPONSE_LEN}"
  --eval-top-p 1
)

PERF_ARGS=(
  --tensor-model-parallel-size "${TP_SIZE}"
  --sequence-parallel
  --pipeline-model-parallel-size "${PP_SIZE}"
  --context-parallel-size "${CP_SIZE}"
  --expert-model-parallel-size "${EP_SIZE}"
  --expert-tensor-parallel-size "${ETP_SIZE}"
  --seq-length "${SEQ_LENGTH}"
  --micro-batch-size "${MICRO_BATCH_SIZE}"
  --max-tokens-per-gpu "${MAX_TOKENS_PER_GPU}"
  --recompute-granularity full
  --recompute-method uniform
  --recompute-num-layers 1
)
if [ -n "${MOE_TOKEN_DISPATCHER_TYPE}" ]; then
  PERF_ARGS+=(--moe-token-dispatcher-type "${MOE_TOKEN_DISPATCHER_TYPE}")
fi
if [ -n "${ATTENTION_BACKEND}" ]; then
  PERF_ARGS+=(--attention-backend "${ATTENTION_BACKEND}")
fi

GRPO_ARGS=(
  --advantage-estimator grpo
  --kl-loss-coef 0.00
  --kl-loss-type low_var_kl
  --entropy-coef 0.00
  --eps-clip 0.2
  --eps-clip-high 0.28
)

OPTIMIZER_ARGS=(
  --optimizer adam
  --lr "${MILES_LR:-1e-5}"
  --lr-decay-style constant
  --weight-decay 0.1
  --adam-beta1 0.9
  --adam-beta2 0.98
)

WANDB_ARGS=(
  --use-wandb
  --wandb-dir "${RUN_ROOT}/wandb"
  --wandb-project "${WANDB_PROJECT}"
  --wandb-group "${WANDB_GROUP}"
  --wandb-run-id "${WANDB_RUN_ID}"
  --log-passrate
  --log-correct-samples
)

SGLANG_ARGS=(
  --rollout-num-gpus-per-engine "${GPUS_PER_NODE}"
  --sglang-dtype bfloat16
  --sglang-mem-fraction-static "${SGLANG_MEM_FRACTION_STATIC}"
  --sglang-cuda-graph-max-bs "${SGLANG_CUDA_GRAPH_MAX_BS}"
  --sglang-server-concurrency "${SGLANG_SERVER_CONCURRENCY}"
  --sglang-moe-runner-backend triton
)

MISC_ARGS=(
  --attention-dropout 0.0
  --hidden-dropout 0.0
  --accumulate-allreduce-grads-in-fp32
  --attention-softmax-in-fp32
  --save-debug-rollout-data "${ROLLOUT_DUMP_TEMPLATE}"
)
# Raw passthrough for experiments (e.g. --sglang-disable-cuda-graph); appended last.
if [ -n "${MILES_EXTRA_ARGS:-}" ]; then
  read -r -a EXTRA_ARGS <<< "${MILES_EXTRA_ARGS}"
  MISC_ARGS+=("${EXTRA_ARGS[@]}")
fi

ray start --head \
  --node-ip-address "${RAY_NODE_IP_ADDRESS}" \
  --num-gpus "${GPUS_PER_NODE}" \
  --disable-usage-stats \
  --dashboard-host="${RAY_DASHBOARD_HOST}" \
  --dashboard-port="${RAY_DASHBOARD_PORT}"

RUNTIME_ENV_JSON="{
  \"env_vars\": {
    \"PYTHONPATH\": \"/root/Megatron-LM/:${REPO_ROOT}/src:${MILES_ROOT}\",
    \"CUDA_DEVICE_MAX_CONNECTIONS\": \"1\",
    \"NCCL_NVLS_ENABLE\": \"${HAS_NVLINK}\",
    \"W8_BIAYN_DATA_DIR\": \"${DATA_DIR}\",
    \"W8_CPP_SANDBOX_IMAGE\": \"${W8_CPP_SANDBOX_IMAGE}\",
    \"W8_CPP_SANDBOX_CPU\": \"${W8_CPP_SANDBOX_CPU:-1}\",
    \"W8_CPP_REWARD_WORKERS\": \"${W8_CPP_REWARD_WORKERS:-8}\",
    \"W8_REGISTER_GLM47_BRIDGE\": \"${W8_REGISTER_GLM47_BRIDGE:-}\",
    \"W8_GLM47_SURFACE_PROBE\": \"${W8_GLM47_SURFACE_PROBE:-}\",
    \"W8_GLM47_PROBE_OUT\": \"${W8_GLM47_PROBE_OUT:-}\",
    \"W8_GLM47_NO_SHARED_LORA_CKPT_PATCH\": \"${W8_GLM47_NO_SHARED_LORA_CKPT_PATCH:-}\"
  }
}"

set +e
TRAIN_ENTRYPOINT=(python3 train.py)
if [ -n "${TRAIN_MODULE}" ]; then
  TRAIN_ENTRYPOINT=(python3 -m "${TRAIN_MODULE}")
fi
ray job submit --address="http://${RAY_DASHBOARD_HOST}:${RAY_DASHBOARD_PORT}" \
  --runtime-env-json="${RUNTIME_ENV_JSON}" \
  -- "${TRAIN_ENTRYPOINT[@]}" \
  --actor-num-nodes 1 \
  --actor-num-gpus-per-node "${GPUS_PER_NODE}" \
  --colocate \
  "${MODEL_ARGS[@]}" \
  "${CKPT_ARGS[@]}" \
  "${ROLLOUT_ARGS[@]}" \
  "${OPTIMIZER_ARGS[@]}" \
  "${GRPO_ARGS[@]}" \
  "${WANDB_ARGS[@]}" \
  "${PERF_ARGS[@]}" \
  "${EVAL_ARGS[@]}" \
  "${SGLANG_ARGS[@]}" \
  "${MISC_ARGS[@]}" \
  "${LORA_ARGS[@]}"
RAY_STATUS=$?
set -e

if [ "${RAY_STATUS}" -eq 0 ]; then
  write_receipt "success" "${RAY_STATUS}"
else
  write_receipt "failed" "${RAY_STATUS}"
fi
exit "${RAY_STATUS}"
