#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../../.."

exec uv run python -m w8_biayn.integrations.moonlight_radix_checksum_validation_aider_tasks "$@"
