#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." &>/dev/null && pwd)"
PYTHON_BIN="${SLIME_CPP_PYTHON:-python3}"
OUT_DIR="${SLIME_OVERFLOW_SAFE_DATE_MATH_TASKS_DIR:-${REPO_ROOT}/.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/overflow-safe-date-math}"
PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" "${PYTHON_BIN}" -m w8_biayn.integrations.moonlight_overflow_safe_date_math_aider_tasks --out "${OUT_DIR}" "$@"
