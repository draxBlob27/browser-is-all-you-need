#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../../.."
exec uv run python -m w8_biayn.integrations.moonlight_bounded_circular_storage_expansion "$@"
