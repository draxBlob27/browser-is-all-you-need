#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

OUT="${W8_COORDINATES_CROSS_FIELD_TASKS_DIR:-.w8-biayn/data/aider-tasks-expansion-v1/validation-parsing/coordinates-cross-field-constraints}"

exec uv run python -m w8_biayn.integrations.moonlight_coordinates_cross_field_aider_tasks \
  --out "$OUT" "$@"
