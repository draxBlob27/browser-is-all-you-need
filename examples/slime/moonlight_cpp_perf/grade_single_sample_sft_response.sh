#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." &>/dev/null && pwd)"
PYTHON_BIN="${SLIME_CPP_PYTHON:-python3}"
RUN_ID="${SLIME_RUN_ID:-moonlight-aider-whole-single-sft}"
PROBE_DIR="${SLIME_PROBE_DIR:-${REPO_ROOT}/.w8-biayn/slime/moonlight-cpp-perf/runs/${RUN_ID}/probes/aider-whole-heldout-two-fer}"
OUT_DIR="${SLIME_GRADE_OUT:-${PROBE_DIR}/grade/two-fer}"

PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" \
  "${PYTHON_BIN}" -m w8_biayn.integrations.moonlight_single_sample_grade \
  --run-id "${RUN_ID}" \
  --probe-dir "${PROBE_DIR}" \
  --out "${OUT_DIR}" \
  "$@"
