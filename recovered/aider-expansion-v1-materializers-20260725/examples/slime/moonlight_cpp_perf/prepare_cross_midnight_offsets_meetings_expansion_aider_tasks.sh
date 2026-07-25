#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$repo_root"

export PYTHONPATH="${repo_root}/src${PYTHONPATH:+:${PYTHONPATH}}"
exec python3 -m \
  w8_biayn.integrations.moonlight_cross_midnight_offsets_meetings_aider_tasks \
  --out .w8-biayn/data/aider-tasks-expansion-v1/time-date/cross-midnight-offsets-meetings \
  "$@"
