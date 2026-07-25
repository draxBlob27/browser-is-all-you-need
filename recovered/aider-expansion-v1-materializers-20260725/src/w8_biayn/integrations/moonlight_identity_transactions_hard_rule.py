"""Artifact-derived diversity and contamination checks for the 60-root family."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HARD_DIMENSIONS = (
    "public_api",
    "owned_state_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
)

_CPP_WORDS = frozenset(
    "alignas alignof and auto bool break case catch char class const constexpr "
    "continue default delete do double else enum explicit false float for friend "
    "if inline int long namespace new noexcept nullptr operator or private protected "
    "public return short signed sizeof static struct switch template this throw true "
    "try typedef typename union unsigned using virtual void volatile while size_t "
    "string vector map set deque optional pair tuple priority_queue function".split()
)
_ENDPOINT = {"first": "endpoint", "last": "endpoint", "front": "endpoint", "back": "endpoint", "left": "side", "right": "side", "begin": "bound", "end": "bound"}
_STRUCTURAL = _CPP_WORDS | frozenset({"literal", "number", "endpoint", "side", "bound"})


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def tree_hash(root: Path, *, include_state: bool = False) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "not_available"
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if not include_state and ".state" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def normalized_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r"\"(?:\\\\.|[^\"\\\\])*\"|'(?:\\\\.|[^'\\\\])*'", " literal ", text)
    text = re.sub(r"\b(?:0x[0-9a-fA-F]+|\d+)\b", " number ", text)
    words = re.findall(
        r"[A-Za-z_][A-Za-z_0-9]*|==|!=|<=|>=|&&|\|\||\+\+|--|->|[{}()\[\];,:?+*/%<>=.!&|-]",
        text.lower(),
    )
    out: list[str] = []
    identifiers: dict[str, str] = {}
    for word in words:
        word = _ENDPOINT.get(word, word)
        if word in {"++", "--"}:
            word = "step"
        if re.fullmatch(r"[a-z_][a-z_0-9]*", word) and word not in _STRUCTURAL:
            word = identifiers.setdefault(word, f"identifier_{len(identifiers)}")
        out.append(word)
    return tuple(out)


def _provenance(root: Path) -> dict[str, object]:
    return json.loads((root / ".meta/provenance.json").read_text())


def _profile(root: Path) -> dict[str, str]:
    provenance = _provenance(root)
    profile = provenance.get("semantic_profile")
    if not isinstance(profile, dict) or set(profile) != set(HARD_DIMENSIONS):
        raise RuntimeError(f"semantic_profile_invalid: {root}")
    return {key: str(profile[key]) for key in HARD_DIMENSIONS}


def dimension_material(root: Path) -> dict[str, tuple[str, ...]]:
    _profile(root)  # Provenance shape is validated, but never treated as diversity evidence.
    header = next(root.glob("*.h")).read_text()
    reference = (root / ".meta/example.cpp").read_text()
    visible = (root / "task_visible_test.cpp").read_text()
    hidden = (root / ".meta/task_hidden_test.cpp").read_text()
    negative = (root / ".meta/negative_false_substitute.cpp").read_text()
    scopes = {
        "public_api": header,
        "owned_state_algorithm": reference,
        "mutation_selection_rules": reference + visible,
        "invalid_boundary_behavior": reference + hidden,
        "reference_control_flow": reference,
        "deterministic_oracle": visible + hidden,
        "topic_negative_fixture": negative,
    }
    return {key: normalized_tokens(value) for key, value in scopes.items()}


def pair_decisions(left: Path, right: Path) -> dict[str, bool]:
    lhs, rhs = dimension_material(left), dimension_material(right)
    decisions: dict[str, bool] = {}
    for dimension in HARD_DIMENSIONS:
        a, b = lhs[dimension], rhs[dimension]
        left_shingles = {a[i : i + 7] for i in range(max(0, len(a) - 6))}
        right_shingles = {b[i : i + 7] for i in range(max(0, len(b) - 6))}
        containment = len(left_shingles & right_shingles) / min(len(left_shingles), len(right_shingles)) if left_shingles and right_shingles else 1.0
        decisions[dimension] = containment < 0.90
    return decisions


def family_screen(roots: list[Path], controls: dict[str, Path]) -> dict[str, object]:
    pairs: list[dict[str, object]] = []
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            decisions = pair_decisions(left, right)
            if not all(decisions.values()):
                raise RuntimeError(f"duplicate_family: {left.name} vs {right.name}: {decisions}")
            pairs.append({"left": left.name, "right": right.name, "decisions": decisions})
    expected = len(roots) * (len(roots) - 1) // 2
    if len(pairs) != expected:
        raise RuntimeError(f"pair_count_mismatch: {len(pairs)} != {expected}")
    source = roots[0]
    control_rows: dict[str, object] = {}
    for name, control in controls.items():
        decisions = pair_decisions(source, control)
        if any(decisions.values()):
            raise RuntimeError(f"clone_control_escaped: {name}: {decisions}")
        control_rows[name] = {
            "source": source.name,
            "changed_files": sorted(
                p.relative_to(control).as_posix()
                for p in control.rglob("*")
                if p.is_file()
                and (source / p.relative_to(control)).is_file()
                and p.read_bytes() != (source / p.relative_to(control)).read_bytes()
            ),
            "decisions": decisions,
            "production_rejected": True,
        }
        if not control_rows[name]["changed_files"]:
            raise RuntimeError(f"clone_control_noop: {name}")
    return {
        "status": "pass",
        "root_count": len(roots),
        "pair_count": len(pairs),
        "expected_pair_count": expected,
        "dimensions": list(HARD_DIMENSIONS),
        "normalizer": "idtx-v2-artifact-only-identifier-domain-literal-endpoint-neutral-structural-shingles",
        "pairs": pairs,
        "controls": control_rows,
    }


def shingles(text: str, width: int = 11) -> set[tuple[str, ...]]:
    tokens = normalized_tokens(text)
    return {tokens[i : i + width] for i in range(max(0, len(tokens) - width + 1))}


def semantic_text(root: Path) -> str:
    config_path = root / ".meta/config.json"
    roles: list[Path] = []
    if config_path.is_file():
        config = json.loads(config_path.read_text())
        files = config.get("files", {})
        for role in ("solution", "test", "example"):
            for relative in files.get(role, []):
                path = root / relative
                if path.is_file() and path.stat().st_size < 1_000_000:
                    roles.append(path)
    roles.extend(path for path in sorted((root / ".docs").glob("*.md")) if path.is_file())
    if not roles:
        roles.extend(path for path in sorted(root.rglob("*.cpp")) if path.stat().st_size < 1_000_000)
        roles.extend(path for path in sorted(root.rglob("*.h")) if path.stat().st_size < 1_000_000)
    return "\n".join(path.read_text(errors="ignore") for path in roles)


def containment(left: str, right: str) -> float:
    a, b = shingles(left), shingles(right)
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0
