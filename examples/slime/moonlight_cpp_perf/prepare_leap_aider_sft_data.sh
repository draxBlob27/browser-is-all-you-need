#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." &>/dev/null && pwd)"
PYTHON_BIN="${SLIME_CPP_PYTHON:-python3}"
TASK_DIR="${SLIME_LEAP_TASK_DIR:-${REPO_ROOT}/.w8-biayn/data/aider-tasks/leap}"
OUT_DIR="${SLIME_CPP_DATA_DIR:-${REPO_ROOT}/.w8-biayn/data/aider-leap-sft}"

PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" \
  "${PYTHON_BIN}" -m w8_biayn.integrations.moonlight_aider_task_sft \
  --task-dir "${TASK_DIR}" \
  --out "${OUT_DIR}" \
  --task-id leap \
  --label leap \
  --source "aider-tasks/leap" \
  "$@"
