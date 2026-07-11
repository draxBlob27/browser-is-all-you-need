#!/usr/bin/env bash
set -euo pipefail

LANE="examples/modal/glm47_flash_aider_polyglot_cpp"
APP_NAME=""
PAID_STARTED=0
TEARDOWN_VERIFIED=0

usage() {
  cat <<'EOF'
Usage: bash examples/modal/glm47_flash_aider_polyglot_cpp/run.sh

Configuration is export-only. Required for every phase:
  MODAL_TOKEN_ID, MODAL_TOKEN_SECRET, MODAL_PROFILE
  W8_MODAL_AIDER_RUN_ID, W8_MODAL_AIDER_MODEL_REPO
  W8_MODAL_AIDER_MODEL_REVISION, W8_MODAL_AIDER_AIDER_COMMIT
  W8_MODAL_AIDER_POLYGLOT_COMMIT, W8_MODAL_AIDER_SGLANG_IMAGE

W8_MODAL_AIDER_PHASE defaults to plan. Smoke/full additionally require:
  W8_MODAL_AIDER_ACKNOWLEDGE_PAID_RUN=1

See the lane README for every optional W8_MODAL_AIDER_* export.
EOF
}

stop_and_verify() {
  local list_json
  local local_run
  local results_volume
  local -a env_args=()
  if [[ -n "${MODAL_ENVIRONMENT:-}" ]]; then
    env_args=(--env "$MODAL_ENVIRONMENT")
  fi
  list_json="$(mktemp /tmp/w8-modal-aider-app-list.XXXXXX.json)"
  uv run --extra modal modal app stop "$APP_NAME" --yes "${env_args[@]}" || true
  if ! uv run --extra modal modal app list --json "${env_args[@]}" >"$list_json"; then
    echo "ERROR: could not verify Modal App state." >&2
    echo "Manual recovery: uv run --extra modal modal app stop '$APP_NAME' --yes ${env_args[*]}" >&2
    return 1
  fi
  if ! uv run python -m w8_biayn.modal_aider_polyglot_cpp mark-stopped \
      --repo-root "$PWD" --app-list-json "$list_json"; then
    echo "ERROR: Modal App did not reach a verified stopped state." >&2
    echo "Manual recovery: uv run --extra modal modal app stop '$APP_NAME' --yes ${env_args[*]}" >&2
    return 1
  fi
  local_run="${W8_MODAL_AIDER_LOCAL_ROOT:-.w8-biayn/modal/glm47-flash-aider-polyglot-cpp}/runs/${W8_MODAL_AIDER_RUN_ID}"
  results_volume="${W8_MODAL_AIDER_RESULTS_VOLUME:-w8-aider-polyglot-cpp-results}"
  if [[ -f "$local_run/run_receipt.json" && -f "$local_run/artifact_manifest.json" ]]; then
    for artifact in run_receipt.json artifact_manifest.json; do
      if ! uv run --extra modal modal volume put --force "${env_args[@]}" \
          "$results_volume" "$local_run/$artifact" \
          "runs/${W8_MODAL_AIDER_RUN_ID}/$artifact"; then
        echo "ERROR: stopped-state receipt could not be committed to the results Volume." >&2
        return 1
      fi
    done
  fi
  rm -f "$list_json"
  TEARDOWN_VERIFIED=1
}

cleanup() {
  local status=$?
  trap - EXIT INT TERM HUP
  if [[ "$PAID_STARTED" == 1 && "$TEARDOWN_VERIFIED" != 1 ]]; then
    if ! stop_and_verify; then
      status=1
    fi
  fi
  exit "$status"
}

# The cleanup trap is installed before authentication or any paid command.
trap cleanup EXIT INT TERM HUP

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
if [[ $# -ne 0 ]]; then
  echo "ERROR: positional configuration is unsupported; use exported variables." >&2
  usage >&2
  exit 2
fi
if [[ ! -f pyproject.toml || ! -d src/w8_biayn || ! -f "$LANE/modal_app.py" ]]; then
  echo "ERROR: run this script from the repository root." >&2
  exit 2
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is required. Run ./scripts/bootstrap.sh first." >&2
  exit 2
fi

# One Python parser owns defaults, validation, redaction, and the persisted plan.
uv run python -m w8_biayn.modal_aider_polyglot_cpp plan --repo-root "$PWD"
APP_NAME="w8-aider-polyglot-cpp-${W8_MODAL_AIDER_RUN_ID}"

# Authentication is verified without printing either token value.
uv run --extra modal modal token info >/dev/null

PHASE="${W8_MODAL_AIDER_PHASE:-plan}"
if [[ "$PHASE" == "plan" ]]; then
  echo "phase: plan"
  echo "paid_resources_created: false"
  exit 0
fi

PAID_STARTED=1
uv run --extra modal modal run "$LANE/modal_app.py"

# The ephemeral App should already be stopped; make the operation explicit and
# verify it through the control plane before admitting any local result.
stop_and_verify
PAID_STARTED=0
uv run python -m w8_biayn.modal_aider_polyglot_cpp validate-artifacts --repo-root "$PWD" >/dev/null
uv run python -m w8_biayn.modal_aider_polyglot_cpp summary --repo-root "$PWD"
