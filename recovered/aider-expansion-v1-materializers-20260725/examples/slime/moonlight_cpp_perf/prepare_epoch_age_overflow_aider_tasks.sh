#!/usr/bin/env bash
set -euo pipefail

exec uv run python -m w8_biayn.integrations.moonlight_epoch_age_overflow_aider_tasks "$@"
