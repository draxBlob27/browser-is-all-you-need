
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../../.." &>/dev/null && pwd)"
PYTHON_BIN="${SLIME_CPP_PYTHON:-python3}"
OUT_DIR="${SLIME_BALANCED_TREE_TASKS_DIR:-${REPO_ROOT}/.w8-biayn/data/aider-tasks-reverify/aider-dsa/balanced-search-tree}"

if [[ "${OUT_DIR}" == "${REPO_ROOT}/.w8-biayn/data/aider-tasks/aider-dsa/balanced-search-tree" ]]; then
  echo "refusing to overwrite the preserved legacy balanced-search-tree family" >&2
  exit 2
fi

PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" \
  "${PYTHON_BIN}" -m w8_biayn.integrations.moonlight_balanced_search_tree_aider_tasks --out "${OUT_DIR}" "$@"
