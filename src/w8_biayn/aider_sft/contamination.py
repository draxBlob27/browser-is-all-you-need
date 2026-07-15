"""Role-aware exact and near-match contamination screening."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from w8_biayn.constants import UPSTREAMS
from w8_biayn.upstreams import upstream_path

from .benchmark import EXPECTED_CPP_TASK_IDS
from .errors import AiderSftError
from .review import register_subject
from .schema import ReviewScope
from .source_exercism import load_canonical_task
from .util import fingerprint, normalize_text_bytes, sha256_bytes, tree_files, write_json

_WORD_RE = re.compile(r"[a-z0-9_]+")
_CPP_COMMENT_RE = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)
EXCLUDED_ROLES = {
    "grader/build/CMakeLists.txt",
    "grader/shared-support.json",
}
FINAL_SCREEN_ID_MATCH_VERSION = "aider-sft-final-id-whole-slug-v2"
_TASK_ID_NEIGHBOR_CLASS = "a-z0-9_-"


def normalize_semantic_text(payload: bytes, *, code: bool) -> list[str]:
    text = normalize_text_bytes(payload, label="contamination input").decode("utf-8").lower()
    if code:
        text = _CPP_COMMENT_RE.sub(" ", text)
    return _WORD_RE.findall(text)


def shingles(tokens: list[str], size: int) -> set[tuple[str, ...]]:
    if len(tokens) < size:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[index : index + size]) for index in range(len(tokens) - size + 1)}


def jaccard(left: set[Any], right: set[Any]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _task_role_documents(task_root: Path) -> dict[str, tuple[bytes, bool]]:
    result: dict[str, tuple[bytes, bool]] = {}
    for relative, payload in tree_files(task_root).items():
        if relative in EXCLUDED_ROLES or relative.startswith("receipts/"):
            continue
        if relative.startswith(("provenance/", "grader/negative-solutions/")):
            continue
        if relative == "task.json" or relative.endswith(".json"):
            continue
        if relative.startswith("docs/"):
            result[f"instructions:{relative}"] = (payload, False)
        elif relative.startswith(
            ("workspace/starter/", "workspace/reference/", "workspace/context/")
        ):
            result[f"code:{relative}"] = (payload, True)
        elif relative.startswith("grader/tests/"):
            result[f"tests:{relative}"] = (payload, True)
    return result


def _benchmark_documents(repo_root: Path) -> dict[str, dict[str, tuple[bytes, bool]]]:
    checkout = upstream_path(UPSTREAMS["aider-polyglot"], repo_root)
    result: dict[str, dict[str, tuple[bytes, bool]]] = {}
    for task_id in sorted(EXPECTED_CPP_TASK_IDS):
        root = checkout / "cpp/exercises/practice" / task_id
        roles: dict[str, tuple[bytes, bool]] = {}
        for relative, payload in tree_files(root).items():
            if relative in {"CMakeLists.txt", "test/catch.hpp", "test/tests-main.cpp"}:
                continue
            if relative.startswith((".meta/", ".approaches/", ".articles/")):
                if not relative.startswith(".meta/example"):
                    continue
            if relative.startswith(".docs/") and Path(relative).name in {
                "introduction.md",
                "instructions.md",
                "instructions.append.md",
            }:
                roles[f"instructions:{relative}"] = (payload, False)
            elif Path(relative).suffix.lower() in {".cpp", ".cc", ".cxx", ".h", ".hpp"}:
                roles[f"code:{relative}"] = (payload, True)
        result[task_id] = roles
    return result


def screen_task(
    *,
    task_root: Path,
    repo_root: Path,
    root: Path,
    config_lock: dict[str, Any],
    other_tasks: list[Path] | None = None,
) -> dict[str, Any]:
    task = load_canonical_task(task_root)
    if task.task_id in EXPECTED_CPP_TASK_IDS or task.root_task_id in EXPECTED_CPP_TASK_IDS:
        raise AiderSftError("benchmark_id_overlap", f"held-out ID: {task.task_id}")
    config = config_lock["config"]["contamination"]
    shingle_size = config["token_shingle_size"]
    candidate_documents = _task_role_documents(task_root)
    benchmark_documents = _benchmark_documents(repo_root)
    exact_candidate = {
        sha256_bytes(payload): role for role, (payload, _) in candidate_documents.items()
    }
    flags: list[dict[str, Any]] = []
    for benchmark_id, documents in benchmark_documents.items():
        for benchmark_role, (benchmark_payload, benchmark_code) in documents.items():
            digest = sha256_bytes(benchmark_payload)
            if digest in exact_candidate:
                raise AiderSftError(
                    "benchmark_content_overlap",
                    f"exact held-out overlap between {task.task_id} and {benchmark_id}",
                )
            benchmark_tokens = normalize_semantic_text(benchmark_payload, code=benchmark_code)
            benchmark_shingles = shingles(benchmark_tokens, shingle_size)
            for candidate_role, (candidate_payload, candidate_code) in candidate_documents.items():
                if candidate_code != benchmark_code:
                    continue
                candidate_tokens = normalize_semantic_text(candidate_payload, code=candidate_code)
                score = jaccard(shingles(candidate_tokens, shingle_size), benchmark_shingles)
                threshold = (
                    config["instruction_review_threshold"]
                    if not candidate_code
                    else config["jaccard_review_threshold"]
                )
                if score >= threshold:
                    evidence = {
                        "left_id": task.task_id,
                        "left_role": candidate_role,
                        "right_id": benchmark_id,
                        "right_role": benchmark_role,
                        "score": round(score, 8),
                        "threshold": threshold,
                        "normalizer_version": config["normalizer_version"],
                    }
                    flag_id = fingerprint("aider-sft-contamination-flag-v1", evidence)[:20]
                    subject = register_subject(
                        root,
                        scope=ReviewScope.CONTAMINATION_FLAG,
                        subject_id=flag_id,
                        payload=evidence,
                    )
                    flags.append(
                        {
                            "flag_id": flag_id,
                            "subject_fingerprint": subject["subject_fingerprint"],
                            **evidence,
                        }
                    )

    candidate_signature = sorted(
        (role.split(":", 1)[0], sha256_bytes(payload))
        for role, (payload, _) in candidate_documents.items()
    )
    for other_root in sorted(other_tasks or []):
        other = load_canonical_task(other_root)
        if other.task_family_id == task.task_family_id:
            raise AiderSftError("duplicate_family", f"duplicate family: {task.task_family_id}")
        other_docs = _task_role_documents(other_root)
        other_signature = sorted(
            (role.split(":", 1)[0], sha256_bytes(payload))
            for role, (payload, _) in other_docs.items()
        )
        if candidate_signature == other_signature:
            raise AiderSftError("duplicate_task", f"exact content duplicate: {other.task_id}")

    receipt = {
        "schema_version": "aider-sft-contamination-receipt-v1",
        "task_id": task.task_id,
        "status": "review_required" if flags else "passed",
        "input_fingerprint": fingerprint(
            "aider-sft-contamination-input-v1",
            task.source.content_sha256,
            config,
            sorted(EXPECTED_CPP_TASK_IDS),
        ),
        "benchmark_exact_overlap_count": 0,
        "flags": sorted(flags, key=lambda item: item["flag_id"]),
        "allowlisted_exclusions": sorted(EXCLUDED_ROLES),
    }
    receipt["receipt_fingerprint"] = fingerprint("aider-sft-contamination-receipt-v1", receipt)
    write_json(task_root / "receipts/contamination.json", receipt)
    return receipt


def final_screen_rows(
    *,
    rows: list[dict[str, Any]],
    benchmark_task_ids: set[str] | None = None,
) -> dict[str, Any]:
    denylist = set(EXPECTED_CPP_TASK_IDS) if benchmark_task_ids is None else benchmark_task_ids
    serialized = "\n".join(
        message["content"].lower() for row in rows for message in row["messages"]
    )
    exact_ids = sorted(
        task_id
        for task_id in denylist
        if re.search(
            rf"(?<![{_TASK_ID_NEIGHBOR_CLASS}]){re.escape(task_id)}"
            rf"(?![{_TASK_ID_NEIGHBOR_CLASS}])",
            serialized,
        )
    )
    if exact_ids:
        raise AiderSftError(
            "final_screen_invalidated_split",
            "rendered rows expose held-out task IDs: " + ", ".join(exact_ids),
        )
    return {
        "schema_version": "aider-sft-final-contamination-v1",
        "row_count": len(rows),
        "benchmark_id_mentions": 0,
        "status": "passed",
        "rows_sha256": fingerprint("aider-sft-final-rows-v1", rows),
    }


def final_screen_policy_fingerprint() -> str:
    return fingerprint(
        "aider-sft-final-screen-policy-v1",
        FINAL_SCREEN_ID_MATCH_VERSION,
        sorted(EXPECTED_CPP_TASK_IDS),
    )
