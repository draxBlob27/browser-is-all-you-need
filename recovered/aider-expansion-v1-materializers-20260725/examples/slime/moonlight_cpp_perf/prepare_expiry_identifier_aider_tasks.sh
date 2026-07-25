#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." &>/dev/null && pwd)"
OUT="${W8_EXPIRY_IDENTIFIER_TASKS_DIR:-${REPO_ROOT}/.w8-biayn/data/aider-tasks-expansion-v1/validation-input-parsing/date-bearing-identifiers}"
PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" "${SLIME_CPP_PYTHON:-python3}" \
  -m w8_biayn.integrations.moonlight_expiry_identifier_aider_tasks \
  --out "${OUT}" "$@"
