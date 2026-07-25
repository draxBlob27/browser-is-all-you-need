"""Artifact-derived seven-dimension screen for the 90-root time expansion."""

from __future__ import annotations

import difflib
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path


HARD_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)

DIMENSION_ROLES = {
    "public_api": ("header",),
    "owned_state_or_algorithm": ("reference",),
    "mutation_selection_rules": ("selection",),
    "invalid_boundary_behavior": ("instructions", "hidden"),
    "reference_control_flow": ("control_flow",),
    "deterministic_oracle": ("visible", "hidden"),
    "topic_specific_negative_fixture": ("negative_diff",),
}

# Exact and near clones fail. The family is additionally bound to distinct
# transformation/reducer mechanism evidence extracted from the emitted source.
MAX_NORMALIZED_SIMILARITY = {dimension: 0.97 for dimension in HARD_DIMENSIONS}

SEMANTIC_TERMS = {
    "id", "start", "end", "minute", "minutes", "local", "utc", "offset",
    "load", "weight", "day", "index", "duration", "period", "repeat",
    "repeats", "clip", "horizon", "buffer", "before", "after", "participant",
    "priority", "room", "capacity", "predecessor", "precedence", "lag",
    "blackout", "wrap", "recurring", "union", "coverage", "covered", "segment",
    "peak", "exact", "earliest", "quorum", "slot", "gap", "demand", "weighted",
    "exposure", "stable", "order", "conflict", "pairs", "valid", "found",
    "touching", "overlap", "half", "open", "duplicate", "empty", "invalid",
    "positive", "descending", "ascending", "atomic", "merge", "difference",
    "array", "threshold", "heap", "partition", "event", "sweep", "subtract",
    "shift", "project", "normalize", "intersect", "expand", "identity",
    "start_minute", "end_minute", "start_local", "end_local", "utc_offset",
    "day_index", "clip_start", "clip_end", "participant_id", "room_id",
    "predecessor_id", "blackout_start", "blackout_end", "covered_minutes",
    "segment_count", "peak_load", "first_minute", "exact_minutes", "exact_load",
    "required_load", "horizon_start", "horizon_end", "room_by_sorted_span",
    "weighted_minutes", "peak_weight", "count",
}


def _sha(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def _tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", text)
    raw = re.findall(
        r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]",
        text,
    )
    keep = {
        "if", "else", "for", "while", "return", "class", "struct", "const",
        "auto", "bool", "int", "long", "void", "true", "false", "public",
        "private", "namespace", "std", "vector", "array", "set", "map",
        "sort", "priority_queue", "greater", "max", "min", "break", "continue",
        "using", "static_cast", "size_t",
    }
    return tuple(
        token
        if token in keep or token.lower() in SEMANTIC_TERMS or not token[0].isalpha()
        else "ID"
        for token in raw
    )


def _ngrams(tokens: tuple[str, ...], width: int = 7) -> set[tuple[str, ...]]:
    if len(tokens) < width:
        return {tokens} if tokens else set()
    return {tokens[index : index + width] for index in range(len(tokens) - width + 1)}


def _similarity(left: str, right: str) -> float:
    a, b = _ngrams(_tokens(left)), _ngrams(_tokens(right))
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))


def _selection_lines(reference: str) -> str:
    return "\n".join(
        line.strip()
        for line in reference.splitlines()
        if re.search(r"\b(if|else|while|for|sort|max|min|priority_queue|push|erase)\b", line)
    )


def _control_flow(reference: str) -> str:
    tokens = _tokens(reference)
    structural = {
        "if", "else", "for", "while", "return", "sort", "priority_queue",
        "max", "min", "break", "continue", "{", "}", "(", ")", ";",
        "<", ">", "<=", ">=", "==", "!=", "&&", "||", "+", "-", "*",
    }
    return " ".join(token for token in tokens if token in structural)


@lru_cache(maxsize=None)
def read_artifacts(root: Path) -> dict[str, str]:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    header = (root / config["files"]["solution"][0]).read_text(encoding="utf-8")
    reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
    negative = (root / ".meta/negative.cpp").read_text(encoding="utf-8")
    negative_diff = "\n".join(
        difflib.unified_diff(reference.splitlines(), negative.splitlines(), lineterm="")
    )
    return {
        "header": header,
        "instructions": (root / ".docs/instructions.md").read_text(encoding="utf-8"),
        "reference": reference,
        "visible": (root / "task_visible_test.cpp").read_text(encoding="utf-8"),
        "hidden": (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8"),
        "negative": negative,
        "negative_diff": negative_diff,
        "selection": _selection_lines(reference),
        "control_flow": _control_flow(reference),
    }


def _mechanism_evidence(artifacts: dict[str, str]) -> dict[str, object]:
    reference = artifacts["reference"]
    transform = re.search(r"W8_TRANSFORM:([a-z_]+)", reference)
    reducer = re.search(r"W8_REDUCER:([a-z_]+)", reference)
    return {
        "transform": transform.group(1) if transform else None,
        "reducer": reducer.group(1) if reducer else None,
        "valid": bool(transform and reducer and transform.group(1) != reducer.group(1)),
    }


@lru_cache(maxsize=None)
def analyze_root(root: Path) -> dict[str, object]:
    artifacts = read_artifacts(root)
    mechanism = _mechanism_evidence(artifacts)
    dimensions: dict[str, object] = {}
    for dimension in HARD_DIMENSIONS:
        roles = DIMENSION_ROLES[dimension]
        content = "\n".join(artifacts[role] for role in roles)
        token_count = len(_tokens(content))
        dimensions[dimension] = {
            "valid": token_count >= 8 and mechanism["valid"],
            "artifact_roles": list(roles),
            "token_count": token_count,
            "normalized_fingerprint": _sha(" ".join(_tokens(content))),
            "mechanism_profile": f"{mechanism['transform']}+{mechanism['reducer']}",
        }
    return {"root": root.name, "mechanism": mechanism, "dimensions": dimensions}


def compare_roots(left_root: Path, right_root: Path) -> dict[str, object]:
    left_artifacts = read_artifacts(left_root)
    right_artifacts = read_artifacts(right_root)
    left = analyze_root(left_root)
    right = analyze_root(right_root)
    decisions: dict[str, object] = {}
    for dimension in HARD_DIMENSIONS:
        roles = DIMENSION_ROLES[dimension]
        left_content = "\n".join(left_artifacts[role] for role in roles)
        right_content = "\n".join(right_artifacts[role] for role in roles)
        similarity = _similarity(left_content, right_content)
        left_evidence = left["dimensions"][dimension]
        right_evidence = right["dimensions"][dimension]
        distinct = left_evidence["normalized_fingerprint"] != right_evidence["normalized_fingerprint"]
        mechanism_distinct = (
            left_evidence["mechanism_profile"] != right_evidence["mechanism_profile"]
        )
        passed = bool(
            left_evidence["valid"]
            and right_evidence["valid"]
            and distinct
            and mechanism_distinct
            and similarity < MAX_NORMALIZED_SIMILARITY[dimension]
        )
        decisions[dimension] = {
            "pass": passed,
            "left_evidence_valid": left_evidence["valid"],
            "right_evidence_valid": right_evidence["valid"],
            "fingerprint_distinct": distinct,
            "mechanism_profile_distinct": mechanism_distinct,
            "normalized_similarity": similarity,
            "maximum_similarity": MAX_NORMALIZED_SIMILARITY[dimension],
        }
    return {
        "left": left_root.name,
        "right": right_root.name,
        "dimensions": decisions,
        "pass": all(row["pass"] for row in decisions.values()),
    }
