#!/usr/bin/env bash
# Build the local Aider C++ grader, then print immutable admission identities.

set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." &>/dev/null && pwd)"
IMAGE="${GLM47_AIDER_GRADER_IMAGE:-glm47-aider-cpp-grader:1}"
PYTHON_BIN="${MILES_PYTHON:-python3}"

docker build --pull --provenance=false \
  --file "${REPO_ROOT}/docker/aider_cpp_grader.Dockerfile" \
  --tag "${IMAGE}" \
  "${REPO_ROOT}"

PYTHONPATH="${REPO_ROOT}/src:${PYTHONPATH:-}" "${PYTHON_BIN}" \
  -m glm47_posttraining.aider_rl.dataset grader \
  --image "${IMAGE}" \
  --lock "${REPO_ROOT}/docker/aider_cpp_grader.lock.json"
