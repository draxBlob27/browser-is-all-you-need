#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." &>/dev/null && pwd)"
PYTHON_BIN="${SLIME_CPP_PYTHON:-python3}"

PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" \
  "${PYTHON_BIN}" -m w8_biayn.integrations.moonlight_aider_task_eval \
  "$@"
