#!/usr/bin/env bash
set -Eeuo pipefail

exec uv run python -m w8_biayn.integrations.moonlight_identity_transactions_aider_tasks "$@"
