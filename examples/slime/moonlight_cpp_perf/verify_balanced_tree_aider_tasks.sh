#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"

if ! command -v cmake >/dev/null 2>&1; then
  echo "CMake is required for balanced-tree reference verification." >&2
  echo "Materialization does not require CMake; run prepare_balanced_tree_aider_tasks.sh first." >&2
  exit 2
fi

exec bash "${SCRIPT_DIR}/prepare_balanced_tree_aider_tasks.sh" --verify "$@"
