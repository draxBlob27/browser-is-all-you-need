#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." &>/dev/null && pwd)"
PYTHON_BIN="${SLIME_CPP_PYTHON:-python3}"
RUN_ID="${SLIME_RUN_ID:-moonlight-aider-whole-single-sft}"
OUT_DIR="${SLIME_PROBE_OUT:-${REPO_ROOT}/.w8-biayn/slime/moonlight-cpp-perf/runs/${RUN_ID}/probes/aider-whole-heldout-two-fer}"

PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" \
  "${PYTHON_BIN}" -m w8_biayn.integrations.moonlight_single_sample_probe \
  --run-id "${RUN_ID}" \
  --out "${OUT_DIR}" \
  "$@"
