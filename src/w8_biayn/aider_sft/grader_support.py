"""Content-addressed shared Exercism Catch support."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .errors import AiderSftError
from .inventory import EXPECTED_SOURCE_SLUGS
from .util import atomic_write, read_json, sha256_bytes, write_json

BUNDLE_ID = "exercism-catch-v1"
SUPPORT_PATHS = ("test/catch.hpp", "test/tests-main.cpp")


def load_checked_support_manifest(repo_root: Path) -> dict[str, Any]:
    value = read_json(repo_root / "manifests/aider_sft/exercism-catch-v1.json")
    if value.get("schema_version") != "aider-sft-grader-support-v1":
        raise AiderSftError("shared_support_mismatch", "unknown shared-support schema")
    if value.get("bundle_id") != BUNDLE_ID:
        raise AiderSftError("shared_support_mismatch", "shared-support bundle ID changed")
    return value


def reconstruct_support_bundle(
    *,
    checkout: Path,
    destination_root: Path,
    repo_root: Path,
) -> dict[str, Any]:
    expected = load_checked_support_manifest(repo_root)
    expected_files = {entry["path"]: entry for entry in expected["files"]}
    if set(expected_files) != set(SUPPORT_PATHS):
        raise AiderSftError("shared_support_mismatch", "support manifest paths changed")
    observed_payloads: dict[str, bytes] = {}
    for slug in sorted(EXPECTED_SOURCE_SLUGS):
        kind = "concept" if (checkout / f"exercises/concept/{slug}").is_dir() else "practice"
        task_root = checkout / f"exercises/{kind}/{slug}"
        for relative in SUPPORT_PATHS:
            payload = (task_root / relative).read_bytes()
            record = expected_files[relative]
            if len(payload) != record["bytes"] or sha256_bytes(payload) != record["sha256"]:
                raise AiderSftError(
                    "shared_support_mismatch", f"{relative} differs in source task {slug}"
                )
            previous = observed_payloads.setdefault(relative, payload)
            if previous != payload:
                raise AiderSftError(
                    "shared_support_mismatch", f"{relative} is not repeated exactly"
                )
    bundle_root = destination_root / BUNDLE_ID
    for relative, payload in observed_payloads.items():
        atomic_write(bundle_root / relative, payload)
    manifest = {
        **expected,
        "storage_root": f"private/grader-support/{BUNDLE_ID}",
        "reconstructed_from_tasks": len(EXPECTED_SOURCE_SLUGS),
    }
    write_json(destination_root / "manifest.json", manifest)
    return manifest
