#!/usr/bin/env bash
set -euo pipefail

LANE="examples/modal/glm47_flash_multi_swe_cpp"
APP_NAME=""
PAID_STARTED=0
TEARDOWN_VERIFIED=0
PREFLIGHT_LIST=""

usage() {
  sed -n '1,140p' "$LANE/README.md"
}

stop_and_verify() {
  local list_json
  local local_run
  local results_volume
  local -a env_args=()
  if [[ -n "${MODAL_ENVIRONMENT:-}" ]]; then
    env_args=(--env "$MODAL_ENVIRONMENT")
  fi
  list_json="$(mktemp /tmp/w8-modal-multi-swe-app-list.XXXXXX.json)"
  uv run --extra modal modal app stop "$APP_NAME" --yes "${env_args[@]}" || true
  uv run --extra modal modal app list --json "${env_args[@]}" >"$list_json"
  uv run python -m w8_biayn.modal_multi_swe_cpp mark-stopped     --repo-root "$PWD" --app-list-json "$list_json"
  local_run="${W8_MODAL_MULTI_SWE_LOCAL_ROOT:-.w8-biayn/modal/glm47-flash-multi-swe-cpp}/runs/${W8_MODAL_MULTI_SWE_RUN_ID}"
  results_volume="${W8_MODAL_MULTI_SWE_RESULTS_VOLUME:-w8-multi-swe-cpp-results}"
  if [[ -f "$local_run/run_receipt.json" && -f "$local_run/artifact_manifest.json" ]]; then
    for artifact in run_receipt.json artifact_manifest.json; do
      uv run --extra modal modal volume put --force "${env_args[@]}"         "$results_volume" "$local_run/$artifact"         "runs/${W8_MODAL_MULTI_SWE_RUN_ID}/$artifact"
    done
  fi
  rm -f "$list_json"
  TEARDOWN_VERIFIED=1
}

cleanup() {
  local status=$?
  if [[ -n "$PREFLIGHT_LIST" ]]; then
    rm -f "$PREFLIGHT_LIST"
  fi
  trap - EXIT INT TERM HUP
  if [[ "$PAID_STARTED" == 1 && "$TEARDOWN_VERIFIED" != 1 ]]; then
    if ! stop_and_verify; then
      echo "ERROR: verify cleanup with: uv run --extra modal modal app stop '$APP_NAME' --yes" >&2
      status=1
    fi
  fi
  exit "$status"
}

# Installed before authentication and every paid operation.
trap cleanup EXIT INT TERM HUP

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
if [[ $# -ne 0 ]]; then
  echo "ERROR: positional configuration is unsupported; use exports." >&2
  exit 2
fi
if [[ ! -f pyproject.toml || ! -f "$LANE/modal_app.py" ]]; then
  echo "ERROR: run from the repository root." >&2
  exit 2
fi
command -v uv >/dev/null 2>&1 || {
  echo "ERROR: uv is required; run ./scripts/bootstrap.sh." >&2
  exit 2
}

uv run python -m w8_biayn.modal_multi_swe_cpp plan --repo-root "$PWD"
APP_NAME="w8-glm47-multi-swe-cpp-${W8_MODAL_MULTI_SWE_RUN_ID}"
uv run --extra modal modal token info >/dev/null

PHASE="${W8_MODAL_MULTI_SWE_PHASE:-plan}"
if [[ "$PHASE" == "plan" ]]; then
  echo "phase: plan"
  echo "paid_resources_created: false"
  exit 0
fi
if [[ "${W8_MODAL_MULTI_SWE_ACKNOWLEDGE_PAID_RUN:-0}" != 1 ]]; then
  echo "ERROR: W8_MODAL_MULTI_SWE_ACKNOWLEDGE_PAID_RUN=1 is required." >&2
  exit 2
fi

PREFLIGHT_LIST="$(mktemp /tmp/w8-modal-multi-swe-preflight.XXXXXX.json)"
PREFLIGHT_ENV_ARGS=()
if [[ -n "${MODAL_ENVIRONMENT:-}" ]]; then
  PREFLIGHT_ENV_ARGS=(--env "$MODAL_ENVIRONMENT")
fi
uv run --extra modal modal app list --json "${PREFLIGHT_ENV_ARGS[@]}" >"$PREFLIGHT_LIST"
uv run python -m w8_biayn.modal_multi_swe_cpp check-app-stopped \
  --repo-root "$PWD" --app-list-json "$PREFLIGHT_LIST"
rm -f "$PREFLIGHT_LIST"
PREFLIGHT_LIST=""
PAID_STARTED=1
uv run --extra modal modal run "$LANE/modal_app.py"
stop_and_verify
PAID_STARTED=0
uv run python -m w8_biayn.modal_multi_swe_cpp validate-artifacts --repo-root "$PWD" >/dev/null
uv run python -m w8_biayn.modal_multi_swe_cpp summary --repo-root "$PWD"
