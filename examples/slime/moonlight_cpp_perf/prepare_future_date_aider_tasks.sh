#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." &>/dev/null && pwd)"
PYTHON_BIN="${SLIME_CPP_PYTHON:-python3}"
OUT_DIR="${SLIME_FUTURE_DATE_TASKS_DIR:-${REPO_ROOT}/.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/future-date-calculations}"
PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" "${PYTHON_BIN}" -m w8_biayn.integrations.moonlight_future_date_aider_tasks --out "${OUT_DIR}" "$@"
