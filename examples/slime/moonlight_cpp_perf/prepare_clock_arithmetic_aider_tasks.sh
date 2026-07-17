#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." &>/dev/null && pwd)"
PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" "${SLIME_CPP_PYTHON:-python3}" -m w8_biayn.integrations.moonlight_clock_arithmetic_aider_tasks --out "${SLIME_CLOCK_ARITHMETIC_TASKS_DIR:-${REPO_ROOT}/.w8-biayn/data/aider-tasks/aider-dates-and-clocks/clock-arithmetic}" "$@"
