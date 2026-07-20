#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." &>/dev/null && pwd)"
PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" "${SLIME_CPP_PYTHON:-python3}" -m w8_biayn.integrations.moonlight_skip_list_aider_tasks --out "${SLIME_SKIP_LIST_TASKS_DIR:-${REPO_ROOT}/.w8-biayn/data/aider-tasks-reverify/aider-dsa/skip-list}" "$@"
