"""Shared Aider Polyglot C++ holdout manifest."""

from __future__ import annotations

from pathlib import Path

from .errors import AiderSftError
from .util import canonical_json_bytes, read_json, sha256_bytes

BENCHMARK_MANIFEST_RELATIVE = Path("manifests/aider_sft/aider-polyglot-cpp-26.json")

EXPECTED_CPP_TASK_IDS = frozenset(
    {
        "all-your-base",
        "allergies",
        "bank-account",
        "binary-search-tree",
        "circular-buffer",
        "clock",
        "complex-numbers",
        "crypto-square",
        "diamond",
        "dnd-character",
        "gigasecond",
        "grade-school",
        "kindergarten-garden",
        "knapsack",
        "linked-list",
        "meetup",
        "parallel-letter-frequency",
        "perfect-numbers",
        "phone-number",
        "queen-attack",
        "robot-name",
        "space-age",
        "spiral-matrix",
        "sublist",
        "yacht",
        "zebra-puzzle",
    }
)


def manifest_path(repo_root: Path) -> Path:
    return repo_root / BENCHMARK_MANIFEST_RELATIVE


def load_benchmark_manifest(repo_root: Path) -> dict:
    path = manifest_path(repo_root)
    value = read_json(path)
    if value.get("schema_version") != "aider-sft-benchmark-denylist-v1":
        raise AiderSftError("source_inventory_mismatch", "unknown benchmark manifest schema")
    task_ids = value.get("task_ids")
    if not isinstance(task_ids, list) or task_ids != sorted(EXPECTED_CPP_TASK_IDS):
        raise AiderSftError(
            "source_inventory_mismatch",
            "benchmark manifest does not contain the exact frozen 26-task set",
        )
    return value


def benchmark_manifest_sha256(repo_root: Path) -> str:
    return sha256_bytes(canonical_json_bytes(load_benchmark_manifest(repo_root)))
