#!/usr/bin/env bash
set -euo pipefail
R="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PYTHONPATH="$R/src" python3 -m w8_biayn.integrations.moonlight_ascii_art_scaling_aider_tasks --out "${SLIME_ASCII_ART_SCALING_TASKS_DIR:-$R/.w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/ascii-art-scaling}" "$@"
