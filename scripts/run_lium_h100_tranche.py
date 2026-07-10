#!/usr/bin/env python3
"""Fail-closed entry point for one signed Lium H100 booking."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from w8_biayn.integrations.h100_signed_approval import wrapper_main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(wrapper_main())
