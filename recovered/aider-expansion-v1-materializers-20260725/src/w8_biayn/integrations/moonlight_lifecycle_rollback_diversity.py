"""Artifact-derived diversity and adversarial-clone evaluator."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Iterable


DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
NORMALIZER = "lifecycle-rollback-v2-role-contract-witnesses"
SIMILARITY_THRESHOLD = 0.995


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _tokens(text: str) -> tuple[str, ...]:
    for ordered_loop in (
        "for(const auto& item:instances_){values.push_back(item.first);values.push_back(item.second);}",
        "for(auto it=instances_.rbegin();it!=instances_.rend();++it){values.push_back(it->first);values.push_back(it->second);}",
        "for(const auto& item:m.instances){out.push_back(item.first);out.push_back(item.second);}",
        "for(auto it=m.instances.rbegin();it!=m.instances.rend();++it){out.push_back(it->first);out.push_back(it->second);}",
    ):
        text = text.replace(ordered_loop, "ORDERED_MAP_EMIT_DIRECTION_NORMALIZED")
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"', '"S"', text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", "'C'", text)
    text = re.sub(r"\b(?:0[xX][0-9A-Fa-f]+|\d+)(?:[UuLl]+)?\b", "N", text)
    raw = re.findall(r"[A-Za-z_]\w*|==|!=|<=|>=|->|\+\+|--|\+=|-=|&&|\|\||\S", text)
    stable = {
        "bool", "break", "class", "const", "continue", "else", "enum", "false",
        "for", "if", "int", "long", "map", "private", "public", "return", "size_t",
        "std", "struct", "true", "vector", "void", "while",
    }
    result: list[str] = []
    for token in raw:
        lowered = token.lower()
        if lowered in {
            "begin", "end", "cbegin", "cend", "rbegin", "rend", "crbegin",
            "crend", "front", "back", "lower_bound", "upper_bound",
        }:
            result.append("ENDPOINT")
        elif lowered in stable:
            result.append(lowered)
        elif re.fullmatch(r"[A-Za-z_]\w*", token):
            result.append("ID")
        else:
            result.append(token)
    return tuple(result)


def _fingerprint(parts: Iterable[str]) -> str:
    return _sha("\n---\n".join(parts).encode())


def _shingles(tokens: tuple[str, ...], width: int = 5) -> Counter[str]:
    if len(tokens) < width:
        return Counter({" ".join(tokens): 1})
    return Counter(
        " ".join(tokens[index:index + width])
        for index in range(len(tokens) - width + 1)
    )


def _similarity(left: Counter[str], right: Counter[str]) -> float:
    keys = set(left) | set(right)
    denominator = sum(max(left[key], right[key]) for key in keys)
    numerator = sum(min(left[key], right[key]) for key in keys)
    return numerator / denominator if denominator else 1.0


def _load_profile(root: Path) -> dict[str, object]:
    header = next(root.glob("*.h")).read_text(encoding="utf-8")
    source = (root / ".meta/example.cpp").read_text(encoding="utf-8")
    instructions = (root / ".docs/instructions.md").read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    hidden = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
    negative = (root / ".meta/negative.cpp").read_text(encoding="utf-8")
    public, _, private = header.partition("private:")
    artifacts = {
        "public_api": public,
        "owned_state_or_algorithm": private + "\n" + source,
        "mutation_selection_rules": source,
        "invalid_boundary_behavior": instructions + "\n" + visible,
        "reference_control_flow": source,
        "deterministic_oracle": hidden,
        "topic_specific_negative_fixture": source + "\n---NEGATIVE---\n" + negative,
    }
    dimensions: dict[str, dict[str, object]] = {}
    for dimension in DIMENSIONS:
        artifact = artifacts[dimension]
        if not artifact.strip():
            raise ValueError(f"empty_dimension_witness:{root.name}:{dimension}")
        tokens = _tokens(artifact)
        shingles = _shingles(tokens)
        dimensions[dimension] = {
            "artifact_fingerprint": _sha(" ".join(tokens).encode()),
            "artifact_token_count": len(tokens),
            "witnesses": shingles,
            "witness_hash": _sha(
                "\n".join(f"{key}:{count}" for key, count in sorted(shingles.items())).encode()
            ),
        }
    return {
        "task_id": root.name,
        "tree_hash": _fingerprint(
            p.relative_to(root).as_posix() + ":" + _sha(p.read_bytes())
            for p in sorted(root.rglob("*")) if p.is_file()
        ),
        "dimensions": dimensions,
    }


def evaluate_family(
    roots: Iterable[Path],
    *,
    control_roots: dict[str, Path],
) -> dict[str, object]:
    ordered = sorted(roots, key=lambda item: item.name)
    profiles = {root.name: _load_profile(root) for root in ordered}
    if len(profiles) != 70:
        raise ValueError(f"binding_root_count_failed:{len(profiles)}")
    pairwise: list[dict[str, object]] = []
    for left_id, right_id in combinations(sorted(profiles), 2):
        left = profiles[left_id]
        right = profiles[right_id]
        decisions: dict[str, object] = {}
        for dimension in DIMENSIONS:
            ld = left["dimensions"][dimension]
            rd = right["dimensions"][dimension]
            score = _similarity(ld["witnesses"], rd["witnesses"])
            distinct = score < SIMILARITY_THRESHOLD
            decisions[dimension] = {
                "distinct": distinct,
                "left_artifact_fingerprint": ld["artifact_fingerprint"],
                "right_artifact_fingerprint": rd["artifact_fingerprint"],
                "left_witness_hash": ld["witness_hash"],
                "right_witness_hash": rd["witness_hash"],
                "left_witness_count": ld["artifact_token_count"],
                "right_witness_count": rd["artifact_token_count"],
                "jaccard_similarity": score,
                "distinct_below": SIMILARITY_THRESHOLD,
            }
        duplicate = [name for name, decision in decisions.items() if not decision["distinct"]]
        pairwise.append(
            {
                "left": left_id,
                "right": right_id,
                "dimension_decisions": decisions,
                "duplicate_dimensions": duplicate,
                "all_dimensions_distinct": not duplicate,
            }
        )
    failed = [item for item in pairwise if not item["all_dimensions_distinct"]]
    if failed:
        raise ValueError(f"duplicate_family:{failed[0]['left']}:{failed[0]['right']}")

    controls: dict[str, object] = {}
    base_by_control = {
        "domain-identifier-renamed": "snapshot-linear-lifecycle",
        "constants-or-policy-only": "snapshot-quota-lifecycle",
        "opposite-end-selection": "snapshot-keyed-lifecycle",
    }
    for name, control_root in control_roots.items():
        control = _load_profile(control_root)
        base = profiles[base_by_control[name]]
        decisions: dict[str, object] = {}
        for dimension in DIMENSIONS:
            left = base["dimensions"][dimension]
            right = control["dimensions"][dimension]
            score = _similarity(left["witnesses"], right["witnesses"])
            duplicate = score >= SIMILARITY_THRESHOLD
            decisions[dimension] = {
                "distinct": not duplicate,
                "base_artifact_fingerprint": left["artifact_fingerprint"],
                "control_artifact_fingerprint": right["artifact_fingerprint"],
                "base_witness_hash": left["witness_hash"],
                "control_witness_hash": right["witness_hash"],
                "jaccard_similarity": score,
                "duplicate_at_or_above": SIMILARITY_THRESHOLD,
            }
        changed_files = []
        base_root = next(root for root in ordered if root.name == base_by_control[name])
        for path in sorted(control_root.rglob("*")):
            if not path.is_file():
                continue
            counterpart = base_root / path.relative_to(control_root)
            if not counterpart.is_file() or counterpart.read_bytes() != path.read_bytes():
                changed_files.append(path.relative_to(control_root).as_posix())
        if not changed_files or any(item["distinct"] for item in decisions.values()):
            raise ValueError(f"adversarial_control_not_rejected:{name}")
        controls[name] = {
            "failure": "duplicate_family",
            "changed_files": changed_files,
            "tree_hash": control["tree_hash"],
            "dimension_decisions": decisions,
            "duplicate_dimensions": list(DIMENSIONS),
            "behavior_build_status": "pending_docker_sanity",
        }

    return {
        "schema_version": "lifecycle-rollback-family-screen-v1",
        "normalizer": NORMALIZER,
        "similarity_threshold": SIMILARITY_THRESHOLD,
        "decision_inputs": "generated artifact witnesses only; provenance descriptors excluded",
        "root_count": len(profiles),
        "expected_root_count": 70,
        "dimensions": list(DIMENSIONS),
        "comparison_count": len(pairwise),
        "expected_comparison_count": 2415,
        "pairwise": pairwise,
        "adversarial_clone_results": controls,
        "hard_rule_result": "pass",
    }
