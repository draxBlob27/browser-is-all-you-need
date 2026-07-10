#!/usr/bin/env python3
"""Fail fast when the Miles/SGLang FlashInfer packages are incompatible."""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from importlib import metadata


MINIMUM_FLASHINFER = (0, 6, 12)
FLASHINFER_PACKAGES = (
    "flashinfer-python",
    "flashinfer-cubin",
    "flashinfer-jit-cache",
)


def release_tuple(raw_version: str) -> tuple[int, int, int]:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", raw_version)
    if match is None:
        raise ValueError(f"cannot parse package version {raw_version!r}")
    return tuple(int(part) for part in match.groups())


def validate_flashinfer_runtime(
    version_lookup: Callable[[str], str] = metadata.version,
) -> dict[str, str]:
    versions: dict[str, str] = {}
    missing: list[str] = []
    for package in FLASHINFER_PACKAGES:
        try:
            versions[package] = version_lookup(package)
        except metadata.PackageNotFoundError:
            missing.append(package)

    if missing:
        raise RuntimeError(f"missing FlashInfer packages: {', '.join(missing)}")

    releases = {package: release_tuple(raw) for package, raw in versions.items()}
    python_release = releases["flashinfer-python"]
    if python_release < MINIMUM_FLASHINFER:
        minimum = ".".join(str(part) for part in MINIMUM_FLASHINFER)
        raise RuntimeError(
            f"flashinfer-python {versions['flashinfer-python']} is below SGLang's "
            f"minimum {minimum}"
        )
    if any(release != python_release for release in releases.values()):
        rendered = ", ".join(f"{name}={versions[name]}" for name in FLASHINFER_PACKAGES)
        raise RuntimeError(f"FlashInfer package versions are not aligned: {rendered}")
    return versions


def main() -> int:
    try:
        versions = validate_flashinfer_runtime()
    except (RuntimeError, ValueError) as exc:
        print(f"Miles H100 runtime preflight failed: {exc}", file=sys.stderr)
        print(
            "Build examples/miles/Dockerfile.h100-runtime and relaunch with that image.",
            file=sys.stderr,
        )
        return 2

    rendered = ", ".join(f"{name}={versions[name]}" for name in FLASHINFER_PACKAGES)
    print(f"Miles H100 runtime preflight passed: {rendered}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

