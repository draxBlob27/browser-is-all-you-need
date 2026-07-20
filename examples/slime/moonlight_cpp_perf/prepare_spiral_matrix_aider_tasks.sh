#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." &>/dev/null && pwd)"
PYTHON_BIN="${SLIME_CPP_PYTHON:-python3}"
OUT_DIR="${SLIME_SPIRAL_MATRIX_TASKS_DIR:-${REPO_ROOT}/.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/spiral-matrix}"
LEGACY_DIR="${REPO_ROOT}/.w8-biayn/data/aider-tasks/aider-text-grid-reshaping/spiral-matrix"
"${PYTHON_BIN}" "${REPO_ROOT}/scripts/plan_spiral_matrix_remedies.py" --check
PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" "${PYTHON_BIN}" -m w8_biayn.integrations.moonlight_spiral_matrix_aider_tasks \
  --out "${OUT_DIR}" --legacy-root "${LEGACY_DIR}" --verify-core "$@"
