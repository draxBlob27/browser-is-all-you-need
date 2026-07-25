#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../.."
exec uv run python -m w8_biayn.integrations.moonlight_fixed26_flag_analogs_aider_tasks "$@"
