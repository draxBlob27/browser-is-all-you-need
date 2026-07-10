#!/usr/bin/env python3
"""Sign a bounded H100 research decision with an external Ed25519 key."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from w8_biayn.integrations.h100_research_sentry import signing_main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(signing_main())
