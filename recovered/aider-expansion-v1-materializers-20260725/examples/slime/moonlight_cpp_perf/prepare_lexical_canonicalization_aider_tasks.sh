#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

OUT="$ROOT/.w8-biayn/data/aider-tasks-expansion-v1/validation-parsing/lexical-canonicalization-eoi"
exec uv run python -m w8_biayn.integrations.moonlight_lexical_canonicalization_aider_tasks --out "$OUT" --materialize "$@"
