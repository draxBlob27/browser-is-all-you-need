#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
OUT_DIR="${SLIME_REFLOW_LAYOUT_EXPANSION_TASKS_DIR:-${REPO_ROOT}/.w8-biayn/data/aider-tasks-expansion-v1/text-grid-layout/reflow-layout}"

cd "${REPO_ROOT}"
PYTHONPATH="${REPO_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}" \
  "${PYTHON_BIN}" -m w8_biayn.integrations.moonlight_reflow_layout_expansion_aider_tasks \
  --out "${OUT_DIR}" "$@"
