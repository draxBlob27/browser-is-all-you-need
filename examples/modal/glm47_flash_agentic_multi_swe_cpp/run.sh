#!/usr/bin/env bash
set -euo pipefail

LANE="examples/modal/glm47_flash_agentic_multi_swe_cpp"
APP_NAME=""
PAID_STARTED=0
TEARDOWN_VERIFIED=0
PREFLIGHT_LIST=""
MODAL_ENVIRONMENT_VALUE="$(printenv MODAL_ENVIRONMENT 2>/dev/null || true)"

usage() {
  sed -n '1,180p' "$LANE/README.md"
}

run_modal() {
  if [[ -n "$MODAL_ENVIRONMENT_VALUE" ]]; then
    uv run --extra modal modal "$@" --env "$MODAL_ENVIRONMENT_VALUE"
  else
    uv run --extra modal modal "$@"
  fi
}

stop_and_verify() {
  local list_json
  local local_root
  local local_run
  local results_volume
  list_json="$(mktemp /tmp/w8-modal-agentic-mswe-app-list.XXXXXX.json)"
  run_modal app stop "$APP_NAME" --yes || true
  run_modal app list --json >"$list_json"
  local_root="$(printenv W8_MODAL_AGENTIC_MULTI_SWE_LOCAL_ROOT 2>/dev/null || true)"
  if [[ -z "$local_root" ]]; then
    local_root=".w8-biayn/modal/glm47-flash-agentic-multi-swe-cpp"
  fi
  results_volume="$(printenv W8_MODAL_AGENTIC_MULTI_SWE_RESULTS_VOLUME 2>/dev/null || true)"
  if [[ -z "$results_volume" ]]; then
    results_volume="w8-multi-swe-cpp-results"
  fi
  local_run="$local_root/runs/$W8_MODAL_AGENTIC_MULTI_SWE_RUN_ID"
  mkdir -p "$local_run"
  run_modal volume get --force "$results_volume" \
    "runs/$W8_MODAL_AGENTIC_MULTI_SWE_RUN_ID/" "$local_run" || true
  uv run python -m w8_biayn.modal_agentic_multi_swe_cpp mark-stopped \
    --repo-root "$PWD" --app-list-json "$list_json"
  if [[ -f "$local_run/run_receipt.json" && -f "$local_run/artifact_manifest.json" ]]; then
    run_modal volume put --force "$results_volume" \
      "$local_run/run_receipt.json" \
      "runs/$W8_MODAL_AGENTIC_MULTI_SWE_RUN_ID/run_receipt.json"
    run_modal volume put --force "$results_volume" \
      "$local_run/artifact_manifest.json" \
      "runs/$W8_MODAL_AGENTIC_MULTI_SWE_RUN_ID/artifact_manifest.json"
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
      echo "ERROR: explicit Modal stop verification failed." >&2
      status=1
    fi
  fi
  exit "$status"
}

trap cleanup EXIT INT TERM HUP

if [[ "$(printenv W8_MODAL_AGENTIC_MULTI_SWE_HELP 2>/dev/null || true)" == 1 || "$#" == 1 && "$1" == "--help" ]]; then
  usage
  exit 0
fi
if [[ "$#" -ne 0 ]]; then
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

uv run python -m w8_biayn.modal_agentic_multi_swe_cpp plan \
  --repo-root "$PWD"
APP_NAME="w8-glm47-agentic-mswe-$W8_MODAL_AGENTIC_MULTI_SWE_RUN_ID"
PHASE="$(printenv W8_MODAL_AGENTIC_MULTI_SWE_PHASE 2>/dev/null || true)"
if [[ -z "$PHASE" ]]; then
  PHASE="plan"
fi
if [[ "$PHASE" == "plan" ]]; then
  echo "phase: plan"
  echo "paid_resources_created: false"
  exit 0
fi
if [[ "$(printenv W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_PAID_RUN 2>/dev/null || true)" != 1 ]]; then
  echo "ERROR: W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_PAID_RUN=1 is required." >&2
  exit 2
fi
if [[ "$PHASE" == "full" && "$(printenv W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_LONG_GPU_LEASE 2>/dev/null || true)" != 1 ]]; then
  echo "ERROR: W8_MODAL_AGENTIC_MULTI_SWE_ACKNOWLEDGE_LONG_GPU_LEASE=1 is required." >&2
  exit 2
fi

run_modal token info >/dev/null
PREFLIGHT_LIST="$(mktemp /tmp/w8-modal-agentic-mswe-preflight.XXXXXX.json)"
run_modal app list --json >"$PREFLIGHT_LIST"
uv run python -m w8_biayn.modal_agentic_multi_swe_cpp \
  check-app-stopped --repo-root "$PWD" \
  --app-list-json "$PREFLIGHT_LIST"
rm -f "$PREFLIGHT_LIST"
PREFLIGHT_LIST=""
PAID_STARTED=1
run_modal run "$LANE/modal_app.py"
stop_and_verify
PAID_STARTED=0
uv run python -m w8_biayn.modal_agentic_multi_swe_cpp \
  validate-artifacts --repo-root "$PWD" >/dev/null
uv run python -m w8_biayn.modal_agentic_multi_swe_cpp \
  summary --repo-root "$PWD"
