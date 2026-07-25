#!/usr/bin/env bash
set -euo pipefail

OUT="${W8_QUOTED_NESTED_RECORDS_OUT:-.w8-biayn/data/aider-tasks-expansion-v1/validation-parsing/quoted-nested-records}"
exec uv run python -m w8_biayn.integrations.moonlight_quoted_nested_records_aider_tasks --out "$OUT" "$@"
