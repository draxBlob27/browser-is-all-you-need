"""Create and verify 60 producer-consumer behavior-structure expansion tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import (
    WholeFormatError,
    build_prompt,
    load_task,
    parse_whole_file_blocks,
)
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_producer_consumer_structures_cases import (
    CASES,
    CaseSpec,
)
from w8_biayn.integrations.moonlight_producer_consumer_protocols import (
    dimension_claims,
    negative_mutation,
    render_header,
    render_instructions,
    render_reference,
    render_test,
)


DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/"
    "producer-consumer-behavior-structures"
)
LEGACY_ROOTS = (
    Path(".w8-biayn/data/aider-tasks"),
    Path(".w8-biayn/data/aider-tasks-reverify"),
)
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-state/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_PRODUCER_CONSUMER_BEHAVIOR_STRUCTURES_CURRICULUM.md"
)
SPECIFICATION = Path(
    "docs/aider-tasks-spec/aider-state/producer-consumer-behavior-structures.md"
)
SELECTED_DESIGN_PROMPT = Path("docs/aider-tasks-spec/prompts/generate-family-spec.md")
SELECTED_IMPLEMENT_PROMPT = Path(
    "docs/aider-tasks-spec/prompts/implement-family-for-sft.md"
)
FAMILY_ID = "state-concurrency-producer-consumer-behavior-structures-v1"
OWNER_ID = "moonlight_producer_consumer_structures_aider_tasks"
SCHEMA = "aider-producer-consumer-structures-v1"
NORMALIZER_VERSION = "producer-consumer-seven-dimension-v2-structural"
MAX_DIMENSION_JACCARD = 0.94
EXPECTED_ROOTS = 60
EXPECTED_PAIRS = 1770
CYCLE_ONE_SUBJECT = "sha256:0af0913a1d7c93874b32b64735a052f8f9cd7b7207ff7b056734b0aba14286d7"
CYCLE_ONE_FINDINGS = tuple(f"PCS-AUD-C01-00{index}" for index in range(1, 6))
CYCLE_THREE_SUBJECT = "sha256:9444e3f4d99486f9cacadf2571d403cb68c85d9694d0f1c61c82acaf22000d3b"
CYCLE_THREE_FINDINGS = (
    "PCS-AUD-C01-001",
    "PCS-AUD-C01-002",
    "PCS-AUD-C01-003",
    "PCS-AUD-C03-001",
)
CYCLE_FOUR_SUBJECT = "sha256:7edfbf6b27657bda62d5985e6bb4e987066c2cb1608d81e4310565a04804ae2d"
CYCLE_FOUR_FINDINGS = (
    "PCS-AUD-C01-001",
    "PCS-AUD-C01-002",
    "PCS-AUD-C01-003",
)
CYCLE_SIX_SUBJECT = "sha256:115ef3794d20227bbc0a1ea1f602db4a0598d1c36d88af40e10c225af97be0dc"
CYCLE_SEVEN_SUBJECT = "sha256:dc6c560881f72a39b91f436479f1cb4fd623e640fdc0f2bfd4fe1525e6dbd296"
CYCLE_SEVEN_FINDINGS = (
    "PCS-AUD-C01-001",
    "PCS-AUD-C01-003",
)
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
DIMENSIONS = (
    "public_api",
    "owned_state",
    "coordination_algorithm",
    "mutation_release_rules",
    "invalid_boundary_behavior",
    "ordering_ties",
    "oracle_negative_fixture",
)
OFFICIAL_HOLDOUTS = frozenset(
    {
        "all-your-base", "allergies", "bank-account", "binary-search-tree",
        "circular-buffer", "clock", "complex-numbers", "crypto-square",
        "diamond", "dnd-character", "gigasecond", "grade-school",
        "kindergarten-garden", "knapsack", "linked-list", "meetup",
        "parallel-letter-frequency", "perfect-numbers", "phone-number",
        "queen-attack", "robot-name", "space-age", "spiral-matrix",
        "sublist", "yacht", "zebra-puzzle",
    }
)
OWNER_PATHS = (
    Path(__file__),
    Path(__file__).with_name("moonlight_producer_consumer_structures_cases.py"),
    Path(__file__).with_name("moonlight_producer_consumer_protocols.py"),
    CURRICULUM,
    SPECIFICATION,
    Path("tests/test_moonlight_producer_consumer_structures_aider_tasks.py"),
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _file_hash(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _tree_hash(root: Path, *, include_state: bool = False) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or (not include_state and ".state" in path.parts):
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _json_hash(value: object) -> str:
    return _sha_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    )


def _fail(code: str, detail: str = "") -> None:
    raise RuntimeError(f"{code}{': ' + detail if detail else ''}")


def _camel(task_id: str) -> str:
    return "".join(part.capitalize() for part in task_id.split("-"))


def _symbol(value: str) -> str:
    return value.replace("-", "_")


def _header(case: CaseSpec, index: int) -> str:
    del index
    return render_header(case)


def _reference(case: CaseSpec, index: int, *, starter: bool = False) -> str:
    del index
    return render_reference(case, starter=starter)


def _tests(case: CaseSpec, index: int, suite: str) -> str:
    del index
    return render_test(case, suite)


def _instructions(case: CaseSpec, index: int) -> str:
    del index
    return render_instructions(case)


def _cmake(case: CaseSpec) -> str:
    return f"""cmake_minimum_required(VERSION 3.16)
project({ _symbol(case.task_id) } LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${{CMAKE_CURRENT_SOURCE_DIR}}/{case.task_id}.cpp" CACHE FILEPATH "Implementation to grade")
foreach(suite visible hidden model)
  add_executable(${{suite}} "${{TASK_SOURCE}}" ".meta/${{suite}}_test.cpp")
  target_include_directories(${{suite}} PRIVATE "${{CMAKE_CURRENT_SOURCE_DIR}}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${{suite}} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND visible)
add_test(NAME hidden COMMAND hidden)
add_test(NAME model COMMAND model)
set_tests_properties(visible hidden model PROPERTIES TIMEOUT 10)
"""


def _diversity_witnesses(case: CaseSpec, index: int, files: dict[str, str]) -> dict[str, str]:
    del index
    header = files[f"{case.task_id}.h"]
    source = files[".meta/example.cpp"]
    instructions = files[".docs/instructions.md"]
    private = header.split(" private:", 1)[-1]
    public = header.split(" private:", 1)[0]
    claims = dimension_claims(case)
    return {
        "public_api": _sha_bytes((claims["public_api"] + public).encode()),
        "owned_state": _sha_bytes((claims["owned_state"] + private).encode()),
        "coordination_algorithm": _sha_bytes((claims["coordination_algorithm"] + source).encode()),
        "mutation_release_rules": _sha_bytes((claims["mutation_release_rules"] + instructions).encode()),
        "invalid_boundary_behavior": _sha_bytes((claims["invalid_boundary_behavior"] + instructions).encode()),
        "ordering_ties": _sha_bytes((claims["ordering_ties"] + source).encode()),
        "oracle_negative_fixture": _sha_bytes((claims["oracle_negative_fixture"] + files[".meta/model_test.cpp"]).encode()),
    }


def _files(case: CaseSpec, index: int) -> dict[str, str]:
    config = {
        "authors": ["w8-biayn"],
        "blurb": case.mechanism,
        "files": {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": [".meta/visible_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "benchmark_separation": "clean-room; official Aider C++ roots and responses were not creation inputs",
        "count_plan_cell": "state-concurrency/producer-consumer-synchronization-closure-backpressure:60",
        "curriculum_document": CURRICULUM.as_posix(),
        "family_id": FAMILY_ID,
        "lineage": "new-root",
        "remediation": {
            "audit_subject_hash": CYCLE_SEVEN_SUBJECT,
            "finding_ids": list(CYCLE_SEVEN_FINDINGS),
            "prior_audit_subject_hash": CYCLE_SIX_SUBJECT,
            "revision": 7,
            "route": "repair-in-place",
        },
        "origin": "repository-authored deterministic expansion",
        "owner": OWNER_ID,
        "selected_prompts": [SELECTED_DESIGN_PROMPT.as_posix(), SELECTED_IMPLEMENT_PROMPT.as_posix()],
        "status": "local candidate material; no SFT release or training authorization",
        "task_id": case.task_id,
        "version": 7,
    }
    raw = {
        ".docs/introduction.md": f"# {case.task_id}\n\nA clean-room deterministic producer-consumer coordination task.\n",
        ".docs/instructions.md": _instructions(case, index),
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/negative.json": json.dumps(negative_mutation(case), indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": "[visible]\ndescription = \"documented normal behavior\"\n\n[hidden]\ndescription = \"invalid, duplicate, full, closure, ordering, and trace behavior\"\n",
        f"{case.task_id}.h": _header(case, index),
        f"{case.task_id}.cpp": _reference(case, index, starter=True),
        ".meta/example.h": _header(case, index),
        ".meta/example.cpp": _reference(case, index),
        ".meta/visible_test.cpp": _tests(case, index, "visible"),
        ".meta/hidden_test.cpp": _tests(case, index, "hidden"),
        ".meta/model_test.cpp": _tests(case, index, "model"),
        "CMakeLists.txt": _cmake(case),
    }
    raw[".meta/diversity.json"] = json.dumps(
        {
            "dimensions": _diversity_witnesses(case, index, raw),
            "mechanism": case.mechanism,
            "state_model": case.state_model,
        },
        indent=2,
        sort_keys=True,
    ) + "\n"
    return raw


def _assert_output_boundary(out: Path) -> None:
    root = EXPANSION_ROOT.resolve()
    resolved = out.resolve()
    if resolved == root or root not in resolved.parents:
        _fail("unsafe_output_root", out.as_posix())
    for legacy in LEGACY_ROOTS:
        legacy_resolved = legacy.resolve()
        if resolved == legacy_resolved or legacy_resolved in resolved.parents:
            _fail("unsafe_output_root", out.as_posix())
    cursor = resolved
    while cursor != root.parent:
        if cursor.exists() and cursor.is_symlink():
            _fail("output_symlink_forbidden", cursor.as_posix())
        if cursor == root:
            break
        cursor = cursor.parent


def _existing_task_ids(exclude: Path | None = None) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for base in (*LEGACY_ROOTS, EXPANSION_ROOT):
        if not base.exists():
            continue
        for config in base.rglob(".meta/config.json"):
            root = config.parent.parent
            if exclude is not None and (root == exclude or exclude in root.parents):
                continue
            result.setdefault(root.name, []).append(root.as_posix())
    return result


def _write(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        _fail("generator_output_drift", f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _prune_owned_stale_roots(out: Path, expected: set[str], *, force: bool) -> None:
    if not out.exists():
        return
    for child in out.iterdir():
        if not child.is_dir() or child.name == ".state" or child.name in expected:
            continue
        provenance = child / ".meta/provenance.json"
        owner = None
        if provenance.is_file():
            owner = json.loads(provenance.read_text()).get("owner")
        if owner != OWNER_ID or not force:
            _fail("foreign_or_stale_root", child.as_posix())
        shutil.rmtree(child)


def build(out: Path = DEFAULT_OUT, *, force: bool = False) -> tuple[Path, ...]:
    _assert_output_boundary(out)
    expected = {case.task_id for case in CASES}
    collisions = _existing_task_ids(exclude=out)
    overlap = sorted(expected & collisions.keys())
    if overlap:
        _fail("duplicate_task", ",".join(overlap))
    _prune_owned_stale_roots(out, expected, force=force)
    roots: list[Path] = []
    for index, case in enumerate(CASES):
        root = out / case.task_id
        files = task_named_files(root, _files(case, index))
        for relative, content in files.items():
            _write(root / relative, content, force=force)
        roots.append(root)
    return tuple(roots)


def _safe_relative(value: object) -> str:
    if not isinstance(value, str) or not value:
        _fail("unsafe_path", repr(value))
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        _fail("unsafe_path", value)
    return path.as_posix()


def _whole_format_failure(root: Path, response: str) -> str | None:
    task = load_task(root)
    try:
        parsed = parse_whole_file_blocks(response)
    except WholeFormatError:
        return "whole_format_failed"
    return None if list(parsed) == list(task.editable_files) else "whole_format_failed"


def _tokens(text: str) -> set[str]:
    text = re.sub(r'"(?:\\.|[^"\\])*"', " string ", text.lower())
    text = re.sub(r"\b\d+\b", " number ", text)
    text = re.sub(r"[a-z]+(?:_[a-z]+)+", " identifier ", text)
    return set(re.findall(r"[a-z]{4,}", text))


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


CPP_KEYWORDS = frozenset(
    "alignas alignof and and_eq asm auto bitand bitor bool break case catch "
    "char char16_t char32_t class compl const constexpr const_cast continue "
    "decltype default delete do double dynamic_cast else enum explicit export "
    "extern false float for friend goto if inline int long mutable namespace "
    "new noexcept not not_eq nullptr operator or or_eq private protected "
    "public register reinterpret_cast return short signed sizeof static "
    "static_assert static_cast struct switch template this thread_local throw "
    "true try typedef typeid typename union unsigned using virtual void "
    "volatile wchar_t while xor xor_eq std size_t ptrdiff_t uint32_t int64_t "
    "vector map set optional string pair tuple make_optional nullopt begin end "
    "cbegin cend rbegin rend count at insert erase push_back pop_back size "
    "empty front back clear find find_if min max min_element max_element swap "
    "has_value value first second move forward assert include pragma once "
    "main".split()
)


def _code_tokens(text: str) -> list[str]:
    """Structural token stream: strings/numbers collapse, every non-keyword
    identifier maps to one ID placeholder so comparison reflects executable
    topology rather than naming."""
    text = re.sub(r'"(?:\\.|[^"\\])*"', " STR ", text)
    text = re.sub(r"\b\d+[uUlL]*\b", " NUM ", text)
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|[^A-Za-z_0-9\s]", text)
    return [
        word if word in CPP_KEYWORDS or not re.match(r"[A-Za-z_]", word) else "ID"
        for word in words
    ]


def _shingles(tokens: list[str], width: int = 5) -> set[tuple[str, ...]]:
    if len(tokens) < width:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i : i + width]) for i in range(len(tokens) - width + 1)}


def _prose_variants(task_id: str) -> set[str]:
    camel = "".join(part.capitalize() for part in task_id.split("-"))
    words = re.findall(r"[a-z]+", task_id)
    concept = "".join(word.capitalize() for word in words[:2])
    return {task_id, _symbol(task_id), camel, concept}


def _prose_tokens(text: str, variants: set[str]) -> set[str]:
    normalized = text.lower()
    for variant in sorted(variants, key=len, reverse=True):
        normalized = re.sub(re.escape(variant.lower()), " ", normalized)
    normalized = re.sub(r'"(?:\\.|[^"\\])*"', " ", normalized)
    normalized = re.sub(r"\b\d+\b", " ", normalized)
    return set(re.findall(r"[a-z]{4,}", normalized))


def _dimension_aspects(root: Path) -> dict[str, tuple[set[tuple[str, ...]], set[str]]]:
    """Split every dimension into an executable-topology aspect (shingles over
    the structural token stream) and a contract-prose aspect (content words
    with task-derived identifiers stripped)."""
    config = json.loads((root / ".meta/config.json").read_text())
    solution = config["files"]["solution"]
    task_id = Path(solution[0]).stem if solution else root.name
    header = (root / solution[0]).read_text()
    source = (root / ".meta/example.cpp").read_text()
    docs = (root / ".docs/instructions.md").read_text()
    visible = (root / ".meta/visible_test.cpp").read_text()
    hidden = (root / ".meta/hidden_test.cpp").read_text()
    model = (root / ".meta/model_test.cpp").read_text()
    diversity = json.loads((root / ".meta/diversity.json").read_text())
    negative = json.loads((root / ".meta/negative.json").read_text())
    public = header.split(" private:", 1)[0]
    private = header.split(" private:", 1)[-1]
    contract = docs.split("## Implementation constraints", 1)[0]
    mechanism = diversity.get("mechanism", "")
    state_model = diversity.get("state_model", "")
    prose_variants = _prose_variants(task_id)
    payloads = {
        "public_api": (public, contract),
        "owned_state": (private, state_model),
        "coordination_algorithm": (source, mechanism),
        "mutation_release_rules": (source, f"{mechanism} {contract}"),
        "invalid_boundary_behavior": (hidden, docs),
        "ordering_ties": (model, docs),
        "oracle_negative_fixture": (
            visible + hidden + model + negative_source(root),
            f"{negative.get('name', '')} {negative.get('reason', '')}",
        ),
    }
    return {
        dimension: (
            _shingles(_code_tokens(code)),
            _prose_tokens(prose, prose_variants),
        )
        for dimension, (code, prose) in payloads.items()
    }


def _pair_decision(left: Path, right: Path) -> dict[str, object]:
    left_aspects = _dimension_aspects(left)
    right_aspects = _dimension_aspects(right)
    dimensions: dict[str, object] = {}
    for dimension in DIMENSIONS:
        code_similarity = _jaccard(left_aspects[dimension][0], right_aspects[dimension][0])
        prose_similarity = _jaccard(left_aspects[dimension][1], right_aspects[dimension][1])
        # A pair differs materially in a dimension when either its executable
        # topology or its contract prose differs beyond the threshold; a pair
        # similar on both aspects is a clone even under different names.
        different = (
            code_similarity <= MAX_DIMENSION_JACCARD
            or prose_similarity <= MAX_DIMENSION_JACCARD
        )
        dimensions[dimension] = {
            "different": different,
            "code_similarity": round(code_similarity, 6),
            "prose_similarity": round(prose_similarity, 6),
            "maximum_jaccard": MAX_DIMENSION_JACCARD,
        }
    passed = all(item["different"] for item in dimensions.values())
    return {"left": left.name, "right": right.name, "dimensions": dimensions, "pass": passed}


def negative_source(root: Path) -> str:
    source = (root / ".meta/example.cpp").read_text()
    mutation_path = root / ".meta/negative.json"
    if not mutation_path.is_file():
        _fail("negative_fixture_missing", root.name)
    mutation = json.loads(mutation_path.read_text())
    needle = mutation.get("from")
    replacement = mutation.get("to")
    if not isinstance(needle, str) or not isinstance(replacement, str):
        _fail("negative_fixture_invalid", root.name)
    if source.count(needle) != 1:
        _fail("negative_fixture_missing", root.name)
    return source.replace(needle, replacement, 1)


def _semantic_inventory(root: Path) -> tuple[set[str], set[str]]:
    docs = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.suffix in {".md", ".h", ".cpp"}
        and ".state" not in path.parts
    )
    api = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in sorted(root.glob("*.h"))
    )
    return _tokens(docs), _tokens(api)


def _cross_tree_screen(out: Path) -> dict[str, object]:
    existing: list[tuple[Path, set[str], set[str]]] = []
    compared_roots = (*LEGACY_ROOTS, EXPANSION_ROOT)
    for base in compared_roots:
        if not base.exists():
            continue
        for config in base.rglob(".meta/config.json"):
            root = config.parent.parent
            if root == out or out in root.parents:
                continue
            docs, api = _semantic_inventory(root)
            existing.append((root, docs, api))
    strongest: list[dict[str, object]] = []
    for case in CASES:
        root = out / case.task_id
        docs, api = _semantic_inventory(root)
        best = (0.0, "", 0.0)
        for other, other_docs, other_api in existing:
            doc_score = _jaccard(docs, other_docs)
            api_score = _jaccard(api, other_api)
            combined = (doc_score + api_score) / 2.0
            if combined > best[0]:
                best = (combined, other.as_posix(), max(doc_score, api_score))
        if best[0] >= 0.90:
            _fail("semantic_lineage_overlap", f"{case.task_id}:{best[1]}:{best[0]:.3f}")
        strongest.append({"task_id": case.task_id, "closest": best[1], "combined_jaccard": round(best[0], 6), "max_role_jaccard": round(best[2], 6)})
    return {
        "policy": "normalized docs and public API against every legacy, reverify, and other expansion real root",
        "comparison_roots": [base.as_posix() for base in compared_roots],
        "existing_roots": len(existing),
        "result": "pass",
        "strongest_by_task": strongest,
    }


def _holdout_screen(out: Path) -> dict[str, object]:
    for case in CASES:
        if case.task_id in OFFICIAL_HOLDOUTS:
            _fail("benchmark_id_overlap", case.task_id)
        corpus = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore").lower()
            for path in (out / case.task_id).rglob("*") if path.is_file()
        )
        for slug in OFFICIAL_HOLDOUTS:
            if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", corpus):
                _fail("benchmark_id_overlap", f"{case.task_id}:{slug}")
    bound = Path(".w8-biayn/data/polyglot-benchmark/cpp/exercises/practice")
    available = [bound / slug for slug in sorted(OFFICIAL_HOLDOUTS) if (bound / slug).is_dir()]
    if len(available) != len(OFFICIAL_HOLDOUTS):
        return {"id_screen": "pass", "semantic_screen": "not_completed", "reason": "complete bound 26-root holdout content unavailable", "available": len(available)}
    holdout_tokens = [(root.name, _semantic_inventory(root)[0]) for root in available]
    strongest = 0.0
    closest = ""
    candidate = ""
    for case in CASES:
        tokens = _semantic_inventory(out / case.task_id)[0]
        for slug, other in holdout_tokens:
            score = _jaccard(tokens, other)
            if score > strongest:
                strongest, closest, candidate = score, slug, case.task_id
    if strongest >= 0.55:
        _fail("benchmark_content_overlap", f"{candidate}:{closest}:{strongest:.3f}")
    return {"id_screen": "pass", "semantic_screen": "pass", "strongest_jaccard": round(strongest, 6), "candidate": candidate, "holdout": closest}


def _validate_root(root: Path) -> dict[str, object]:
    config = json.loads((root / ".meta/config.json").read_text())
    files = config.get("files")
    if not isinstance(files, dict):
        _fail("role_map_missing", root.name)
    solution = [_safe_relative(item) for item in files.get("solution", [])]
    tests = [_safe_relative(item) for item in files.get("test", [])]
    examples = [_safe_relative(item) for item in files.get("example", [])]
    expected_solution = [f"{root.name}.h", f"{root.name}.cpp"]
    if solution != expected_solution or examples != [".meta/example.h", ".meta/example.cpp"]:
        _fail("reference_map_failed", root.name)
    if set(solution) & (set(tests) | set(examples)):
        _fail("role_conflict", root.name)
    for relative in [*solution, *tests, *examples]:
        if not (root / relative).is_file():
            _fail("reference_map_failed", f"{root.name}:{relative}")
    task = load_task(root)
    prompt = build_prompt(task)
    forbidden = (".meta/", "CMakeLists.txt", "visible_test", "hidden_test", "model_test", "provenance.json", "example.cpp")
    if any(item in prompt for item in forbidden):
        _fail("prompt_contract_incomplete", root.name)
    answer = build_assistant_response(task, load_example_files_from_config(root))
    if _whole_format_failure(root, answer):
        _fail("target_reference_mismatch", root.name)
    missing = f"{solution[0]}\n```cpp\n// missing source\n```\n"
    extra = answer + "\nunknown.cpp\n```cpp\nint x;\n```\n"
    prose = "explanation\n" + answer
    if any(_whole_format_failure(root, value) is None for value in (missing, extra, prose)):
        _fail("whole_format_failed", root.name)
    source = (root / ".meta/example.cpp").read_text()
    for forbidden_core in ("std::queue", "std::deque", "std::priority_queue"):
        if forbidden_core in source:
            _fail("forbidden_core_substitute", f"{root.name}:{forbidden_core}")
    return {
        "task_id": root.name,
        "tree_hash": _tree_hash(root),
        "prompt_hash": _sha_bytes(prompt.encode()),
        "starter_hashes": [_file_hash(root / name) for name in solution],
        "reference_hashes": [_file_hash(root / name) for name in examples],
        "test_hashes": [_file_hash(root / f".meta/{suite}_test.cpp") for suite in ("visible", "hidden", "model")],
        "primary_core_objective": "achieved_pending_executable_oracle",
        "lineage": "new-root",
    }


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    _assert_output_boundary(out)
    expected = {case.task_id for case in CASES}
    actual = {child.name for child in out.iterdir() if child.is_dir() and child.name != ".state"}
    if actual != expected or len(actual) != EXPECTED_ROOTS:
        _fail("generator_output_drift", f"expected {EXPECTED_ROOTS}, found {len(actual)}")
    with tempfile.TemporaryDirectory(prefix="producer-consumer-fresh-") as temporary:
        fresh = Path(temporary) / "state-concurrency" / "producer-consumer-behavior-structures"
        # A scratch path is outside the expansion root, so render directly from
        # the immutable owner rather than calling the protected public build.
        for index, case in enumerate(CASES):
            root = fresh / case.task_id
            for relative, content in task_named_files(root, _files(case, index)).items():
                _write(root / relative, content, force=True)
            if _tree_hash(root) != _tree_hash(out / case.task_id):
                _fail("generator_output_drift", case.task_id)
    tasks = [_validate_root(out / case.task_id) for case in CASES]
    pairs: list[dict[str, object]] = []
    roots = [out / case.task_id for case in CASES]
    for left_index, left in enumerate(roots):
        for right in roots[left_index + 1:]:
            decision = _pair_decision(left, right)
            if not decision["pass"]:
                _fail("duplicate_family", f"{left.name}:{right.name}")
            pairs.append(decision)
    if len(pairs) != EXPECTED_PAIRS:
        _fail("diversity_pair_count_mismatch", str(len(pairs)))
    cross_tree = _cross_tree_screen(out)
    holdout = _holdout_screen(out)
    state = out / ".state"
    state.mkdir(parents=True, exist_ok=True)
    diversity = {
        "schema_version": SCHEMA,
        "dimensions": list(DIMENSIONS),
        "root_count": len(roots),
        "pair_count": len(pairs),
        "pairs": pairs,
        "adversarial_controls": "pending_executable_preflight",
        "result": "pass_pending_controls",
    }
    (state / "diversity-report.json").write_text(json.dumps(diversity, indent=2, sort_keys=True) + "\n")
    (state / "cross-tree-screen.json").write_text(json.dumps(cross_tree, indent=2, sort_keys=True) + "\n")
    manifest = {
        "schema_version": SCHEMA,
        "family_id": FAMILY_ID,
        "owner": OWNER_ID,
        "curriculum": CURRICULUM.as_posix(),
        "specification": SPECIFICATION.as_posix(),
        "selected_prompts": [SELECTED_DESIGN_PROMPT.as_posix(), SELECTED_IMPLEMENT_PROMPT.as_posix()],
        "requested_count": EXPECTED_ROOTS,
        "retained_count": len(tasks),
        "tree_hash": _tree_hash(out),
        "tasks": tasks,
        "screens": {
            "prompt_boundary": "pass", "reference_mapping": "pass",
            "whole_file_boundary": "pass", "family_diversity": "pass_pending_controls",
            "cross_tree_lineage": cross_tree["result"],
            "benchmark_id": holdout["id_screen"],
            "benchmark_semantic": holdout["semantic_screen"],
            "normal_sanitizer": "pending", "negative_fixtures": "pending",
        },
        "status": "creator_preflight_pending_executable_oracle",
    }
    (state / "candidate-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return manifest


def _count_discovered(output: str) -> int:
    match = re.search(r"Total Tests:\s*(\d+)", output)
    if not match:
        _fail("test_discovery_failed")
    count = int(match.group(1))
    if count <= 0:
        _fail("zero_tests")
    return count


def _run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if check and completed.returncode:
        tail = completed.stdout[-6000:]
        _fail("subprocess_failed", f"{' '.join(command)}\n{tail}")
    return completed


def verify(out: Path = DEFAULT_OUT) -> dict[str, object]:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        _fail("toolchain_missing", "verification requires cmake and c++")
    manifest = verify_core(out)
    task_receipts: list[dict[str, object]] = []
    for case in CASES:
        root = out / case.task_id
        receipt: dict[str, object] = {
            "task_id": case.task_id,
            "tree_hash": _tree_hash(root),
            "reference_hash": _file_hash(root / ".meta/example.cpp"),
            "negative_hash": _sha_bytes(negative_source(root).encode()),
            "modes": {},
        }
        with tempfile.TemporaryDirectory(prefix=f"pcs-{case.task_id}-") as temporary:
            copy = Path(temporary) / case.task_id
            shutil.copytree(root, copy)
            for mode, flags in (
                ("normal", []),
                ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]),
            ):
                build_dir = copy / f"build-{mode}"
                configure = ["cmake", "-S", str(copy), "-B", str(build_dir), "-G", "Unix Makefiles", "-DCMAKE_CXX_COMPILER=c++", f"-DTASK_SOURCE={copy / '.meta/example.cpp'}", *flags]
                _run(configure)
                _run(["cmake", "--build", str(build_dir), "--parallel", "2"])
                discovered = _count_discovered(_run(["ctest", "--test-dir", str(build_dir), "-N"]).stdout)
                executed = _run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"])
                receipt["modes"][mode] = {"configure": configure, "discovered_tests": discovered, "ctest_hash": _sha_bytes(executed.stdout.encode())}
            negative = copy / ".meta/negative.cpp"
            negative.write_text(negative_source(root))
            negative_build = copy / "build-negative"
            configure = ["cmake", "-S", str(copy), "-B", str(negative_build), "-G", "Unix Makefiles", "-DCMAKE_CXX_COMPILER=c++", f"-DTASK_SOURCE={negative}"]
            _run(configure)
            _run(["cmake", "--build", str(negative_build), "--parallel", "2"])
            negative_count = _count_discovered(_run(["ctest", "--test-dir", str(negative_build), "-N"]).stdout)
            negative_run = _run(["ctest", "--test-dir", str(negative_build), "-R", "^model$", "--output-on-failure"], check=False)
            if negative_run.returncode == 0 or "***timeout" in negative_run.stdout.lower():
                _fail("negative_fixture_not_rejected", case.task_id)
            negative_contract = json.loads((root / ".meta/negative.json").read_text())
            receipt["negative_fixture"] = {"name": negative_contract["name"], "mechanism": negative_contract["mechanism"], "reason": negative_contract["reason"], "compiled": True, "discovered_tests": negative_count, "selected_test": "model", "returncode": negative_run.returncode, "rejected": True, "output_hash": _sha_bytes(negative_run.stdout.encode())}
        normal = receipt["modes"]["normal"]["discovered_tests"]
        sanitizer = receipt["modes"]["sanitizer"]["discovered_tests"]
        if normal != 3 or sanitizer != normal:
            _fail("sanitizer_test_count_mismatch", case.task_id)
        task_receipts.append(receipt)
    runtime = {
        "environment": os.environ.get("W8_BIAYN_ORACLE_RUNTIME", "host-prerequisite"),
        "image": os.environ.get("W8_BIAYN_ORACLE_IMAGE"),
        "network": os.environ.get("W8_BIAYN_ORACLE_NETWORK", "host"),
        "compiler": _run(["c++", "--version"]).stdout.splitlines()[0],
        "compiler_path": shutil.which("c++"),
        "compiler_hash": _file_hash(Path(shutil.which("c++") or "c++")),
        "cmake": _run(["cmake", "--version"]).stdout.splitlines()[0],
        "owner_hashes": {path.as_posix(): _file_hash(path) for path in OWNER_PATHS},
    }
    receipt = {"schema_version": SCHEMA, "runtime": runtime, "tree_hash": _tree_hash(out), "tasks": task_receipts}
    state = out / ".state"
    (state / "oracle-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    manifest["screens"]["normal_sanitizer"] = "pass"
    manifest["screens"]["negative_fixtures"] = "pass"
    manifest["status"] = "creator_preflight_pending_clone_controls"
    (state / "candidate-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return receipt


def _verify_receipt(out: Path) -> dict[str, object]:
    receipt_path = out / ".state/oracle-receipt.json"
    if not receipt_path.is_file():
        _fail("oracle_receipt_missing")
    receipt = json.loads(receipt_path.read_text())
    runtime = receipt.get("runtime", {})
    if runtime.get("environment") != "locked-docker" or runtime.get("network") != "none" or runtime.get("image") != SANITY_IMAGE:
        _fail("docker_sanity_not_completed")
    if runtime.get("owner_hashes") != {path.as_posix(): _file_hash(path) for path in OWNER_PATHS}:
        _fail("oracle_receipt_owner_drift")
    if receipt.get("tree_hash") != _tree_hash(out):
        _fail("oracle_receipt_tree_drift")
    tasks = {item["task_id"]: item for item in receipt.get("tasks", [])}
    if set(tasks) != {case.task_id for case in CASES}:
        _fail("oracle_receipt_task_inventory_mismatch")
    for case in CASES:
        item = tasks[case.task_id]
        if item["tree_hash"] != _tree_hash(out / case.task_id):
            _fail("oracle_receipt_tree_drift", case.task_id)
        normal = item["modes"]["normal"]["discovered_tests"]
        sanitizer = item["modes"]["sanitizer"]["discovered_tests"]
        negative = item["negative_fixture"]
        if normal != 3 or sanitizer != normal or negative.get("rejected") is not True or negative.get("compiled") is not True:
            _fail("oracle_receipt_invalid", case.task_id)
    return receipt


def verify_adversarial_controls(out: Path = DEFAULT_OUT) -> dict[str, object]:
    # Controls are coherent source/test variants.  They first compile and pass
    # their own model test, then the exact pair evaluator must reject them as
    # insufficiently distinct from their parent in at least one dimension.
    parent = out / CASES[8].task_id  # waterline root exercises all API roles
    controls: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="pcs-controls-") as temporary:
        temp = Path(temporary)
        for kind in ("domain-identifier-rename", "constants-policy-only", "opposite-end-selection"):
            clone = temp / kind
            shutil.copytree(parent, clone)
            changed: list[str] = []
            if kind == "domain-identifier-rename":
                old_id = parent.name
                new_id = "harbor-pressure-gate-clone"
                old_cls = _camel(old_id)
                new_cls = _camel(new_id)
                old_snake = _symbol(old_id)
                new_snake = _symbol(new_id)
                for path in list(clone.rglob("*")):
                    if not path.is_file():
                        continue
                    text = path.read_text()
                    updated = text.replace(old_id, new_id).replace(old_cls, new_cls).replace(old_snake, new_snake)
                    if updated != text:
                        path.write_text(updated)
                        changed.append(path.relative_to(clone).as_posix())
                for suffix in (".h", ".cpp"):
                    old = clone / f"{old_id}{suffix}"
                    if old.exists():
                        old.rename(clone / f"{new_id}{suffix}")
                        changed.append(f"rename:{suffix}")
                clone_for_pair = clone
            elif kind == "constants-policy-only":
                for path in (clone / f"{parent.name}.h", clone / ".meta/example.h"):
                    text = path.read_text()
                    updated = text.replace("12U", "13U")
                    if updated != text:
                        path.write_text(updated)
                        changed.append(path.relative_to(clone).as_posix())
                clone_for_pair = clone
            else:
                source = clone / ".meta/example.cpp"
                text = source.read_text()
                # Reverse the observable delivered-history end while keeping
                # each release return and pending-state transition coherent.
                needle = "released_values_.push_back(protocol_result);"
                replacement = "released_values_.insert(released_values_.begin(), protocol_result);"
                if needle not in text:
                    _fail("adversarial_control_noop", kind)
                source.write_text(text.replace(needle, replacement, 1))
                changed.append(source.relative_to(clone).as_posix())
                for suite in ("visible", "hidden", "model"):
                    test = clone / f".meta/{suite}_test.cpp"
                    data = test.read_text()
                    released_field = parent.name.split("-", 1)[0] + "_released"
                    match = re.search(
                        rf"view\.{released_field} == std::vector<int>(\{{[^;]+\}})",
                        data,
                    )
                    if match:
                        values = [item.strip() for item in match.group(1).strip("{}").split(",") if item.strip()]
                        if len(values) > 1:
                            updated = data.replace(match.group(1), "{" + ", ".join(reversed(values)) + "}", 1)
                            test.write_text(updated)
                            changed.append(test.relative_to(clone).as_posix())
                clone_for_pair = clone
            if not changed:
                _fail("adversarial_control_noop", kind)
            build_dir = clone / "build-control"
            source_path = clone / ".meta/example.cpp"
            configure = ["cmake", "-S", str(clone), "-B", str(build_dir), "-G", "Unix Makefiles", "-DCMAKE_CXX_COMPILER=c++", f"-DTASK_SOURCE={source_path}"]
            _run(configure)
            _run(["cmake", "--build", str(build_dir), "--parallel", "2"])
            run = _run(["ctest", "--test-dir", str(build_dir), "-R", "^model$", "--output-on-failure"], check=False)
            if run.returncode != 0:
                _fail("adversarial_control_not_coherent", f"{kind}:{run.stdout[-2000:]}")
            decision = _pair_decision(parent, clone_for_pair)
            if decision["pass"]:
                _fail("adversarial_clone_not_rejected", kind)
            controls.append({"kind": kind, "changed_files": sorted(changed), "compiled": True, "model_test_passed": True, "production_evaluator_rejected": True, "pair_decision": decision})
    report = {"schema_version": SCHEMA, "parent": parent.name, "controls": controls, "result": "pass"}
    state = out / ".state"
    (state / "adversarial-controls.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    diversity_path = state / "diversity-report.json"
    diversity = json.loads(diversity_path.read_text())
    diversity["adversarial_controls"] = "pass"
    diversity["result"] = "pass"
    diversity_path.write_text(json.dumps(diversity, indent=2, sort_keys=True) + "\n")
    manifest_path = state / "candidate-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["screens"]["family_diversity"] = "pass"
    manifest["screens"]["adversarial_clone_controls"] = "pass"
    manifest["status"] = "creator_preflight_complete_pending_receipt_validation"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return report


def finalize_preflight(out: Path = DEFAULT_OUT) -> dict[str, object]:
    receipt = _verify_receipt(out)
    control = verify_adversarial_controls(out)
    state = out / ".state"
    manifest_path = state / "candidate-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["retained_count"] = EXPECTED_ROOTS
    manifest["status"] = "creator_preflight_pass"
    manifest["screens"]["docker_sanity"] = "pass"
    manifest["screens"]["normal_sanitizer"] = "pass"
    manifest["screens"]["negative_fixtures"] = "pass"
    for task in manifest["tasks"]:
        task["primary_core_objective"] = "achieved"
        task["status"] = "creator_preflight_pass_pending_independent_audit"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    preflight = {
        "schema_version": SCHEMA,
        "created_at": _utc_now(),
        "family_id": FAMILY_ID,
        "tree_hash": _tree_hash(out),
        "manifest_hash": _file_hash(manifest_path),
        "diversity_hash": _file_hash(state / "diversity-report.json"),
        "cross_tree_hash": _file_hash(state / "cross-tree-screen.json"),
        "control_hash": _json_hash(control),
        "oracle_hash": _json_hash(receipt),
        "owner_hashes": {path.as_posix(): _file_hash(path) for path in OWNER_PATHS},
        "retained_count": EXPECTED_ROOTS,
        "status": "creator_preflight_pass",
    }
    (state / "creator-preflight.json").write_text(json.dumps(preflight, indent=2, sort_keys=True) + "\n")
    cycle_path = state / "cycles.jsonl"
    existing = cycle_path.read_text().splitlines() if cycle_path.exists() else []
    previous = json.loads(existing[-1]) if existing else None
    generator_hash = _file_hash(Path(__file__))
    cycle = {
        "cycle": len(existing) + 1,
        "timestamp": _utc_now(),
        "state": "creator_preflight",
        "tree_hash": preflight["tree_hash"],
        "candidate_manifest_hash": preflight["manifest_hash"],
        "curriculum_hash": _file_hash(CURRICULUM),
        "generator_hash": generator_hash,
        "focused_test_hash": _file_hash(Path("tests/test_moonlight_producer_consumer_structures_aider_tasks.py")),
        "grader_policy_hash": _json_hash({"image": SANITY_IMAGE, "network": "none", "modes": ["normal", "asan-ubsan"], "tests_per_root": 3}),
        "requested_count": EXPECTED_ROOTS,
        "retained_count": EXPECTED_ROOTS,
        "terminal_status": "creator_preflight_pass_pending_independent_audit",
        "audit_subject_hash": None,
        "finding_ids": [],
        "rejected": [],
        "replaced": [],
        "prior_evidence_invalidated": (
            [
                {
                    "cycle": previous.get("cycle"),
                    "reason": "owner_or_artifact_hash_changed",
                    "tree_hash": previous.get("tree_hash"),
                    "generator_hash": previous.get("generator_hash"),
                }
            ]
            if previous is not None
            and (
                previous.get("tree_hash") != preflight["tree_hash"]
                or previous.get("generator_hash") != generator_hash
            )
            else []
        ),
    }
    if (
        not existing
        or previous.get("tree_hash") != cycle["tree_hash"]
        or previous.get("generator_hash") != cycle["generator_hash"]
    ):
        with cycle_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(cycle, sort_keys=True) + "\n")
    return preflight


def plan_cycle_one_remediation(out: Path = DEFAULT_OUT) -> dict[str, object]:
    """Preserve cycle-01 findings and create owner-controlled remedy records."""
    audit_dir = out / ".state/audit/cycle-01"
    report_path = audit_dir / "audit-report.json"
    findings_path = audit_dir / "findings.json"
    if not report_path.is_file() or not findings_path.is_file():
        _fail("audit_evidence_missing", audit_dir.as_posix())
    report = json.loads(report_path.read_text())
    findings = json.loads(findings_path.read_text())
    subject_hash = report.get("audit_subject_hash")
    finding_ids = [item["finding_id"] for item in findings.get("findings", [])]
    expected_findings = list(CYCLE_ONE_FINDINGS)
    if subject_hash != CYCLE_ONE_SUBJECT or finding_ids != expected_findings:
        _fail("audit_subject_mismatch")
    preflight_path = out / ".state/creator-preflight.json"
    current_preflight = False
    if preflight_path.is_file():
        preflight = json.loads(preflight_path.read_text())
        current_preflight = (
            preflight.get("status") == "creator_preflight_pass"
            and preflight.get("tree_hash") == _tree_hash(out)
            and preflight.get("owner_hashes")
            == {path.as_posix(): _file_hash(path) for path in OWNER_PATHS}
        )
    remedy_dir = out / ".state/remedy/cycle-01"
    remedy_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for case in CASES:
        root = out / case.task_id
        spec_path = remedy_dir / f"{case.task_id}.md"
        spec_text = f"""# Remedy for {case.task_id}

## Identity

Task `{case.task_id}`, revision 2, family `{FAMILY_ID}`, disposition
`repair-in-place`, clean-room source, owner `{OWNER_ID}`, audit subject
`{subject_hash}`, benchmark screen pending regeneration.

## Objective

Implement and test {case.mechanism}. The owned state must be
{case.state_model}; a generic scored pending-vector policy does not achieve the
objective.

## Public API

Replace the shared constructor/three-integer/snapshot shape with operations and
domain types required by this protocol. The editable order remains
`{case.task_id}.h`, `{case.task_id}.cpp`.

## Behavior table

Specify and execute normal, invalid, duplicate, absent, empty, full, closure,
rollback, ordering, tie, and overflow behavior for the protocol. No behavior
may be inherited from the removed generic profile table.

## Implementation invariant

The reference must own and mutate {case.state_model}. It must not retain the
generic score/admission record as the substantive implementation. Private
tests must inspect the protocol invariant after every operation.

## Starter and reference

Regenerate a coherent incomplete starter and an independent protocol-specific
reference. Queue/deque wrappers, shared policy switches, and hard-coded traces
are forbidden.

## Tests

Use a protocol-specific deterministic value model that is structurally
independent from the reference. Exercise every public operation and include a
compiled coherent false substitute that violates this protocol, not a uniform
delivered-value mutation.

## Files and metadata

Preserve prompt/private roles and new-root lineage. Bind revision 2, this
remedy, the cycle-01 audit subject, and all five finding IDs in provenance.

## Build/oracle

Require three positive equal normal/fresh ASan-UBSan discoveries in
`{SANITY_IMAGE}` with network disabled, plus compiled/executed protocol
negative evidence.

## Family/contamination

Compare all 1,770 pairs semantically in all seven dimensions, reject Jaccard
identity rather than treating unequal bytes as diversity, execute three
coherent clone controls, and screen both legacy trees plus every other
expansion root.

## Optional dataset handoff

`not_requested`.

## Acceptance

Close `PCS-AUD-C01-001` through `PCS-AUD-C01-005` only after owner
regeneration, current Docker evidence, and a fresh independent audit retains
this root with no review/repair/conflict disposition.
"""
        spec_path.write_text(spec_text, encoding="utf-8")
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": case.task_id,
            "family_id_before": FAMILY_ID,
            "tree_hash_before": _tree_hash(root),
            "generator_path": Path(__file__).as_posix(),
            "generator_revision": _file_hash(Path(__file__)),
            "finding_ids": expected_findings,
            "disposition": "repair-in-place",
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": spec_path.relative_to(out).as_posix(),
            "remedy_spec_hash": _file_hash(spec_path),
            "audit_subject_hash": subject_hash,
            "tree_hash_after": _tree_hash(root) if current_preflight else None,
            "creator_preflight_hash": (
                _file_hash(preflight_path) if current_preflight else None
            ),
            "status": (
                "verified_pending_fresh_audit" if current_preflight else "planned"
            ),
            "local_status": (
                "creator_preflight_pass" if current_preflight else "not_completed"
            ),
        }
        (remedy_dir / f"{case.task_id}.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        records.append(record)
    summary = {
        "schema_version": SCHEMA,
        "audit_subject_hash": subject_hash,
        "finding_ids": expected_findings,
        "record_count": len(records),
        "disposition_counts": {"repair-in-place": len(records)},
        "materialized_records": len(records) if current_preflight else 0,
        "closed_findings": [],
        "remediated_pending_audit": expected_findings if current_preflight else [],
        "remaining_findings": expected_findings,
        "status": (
            "remediation_verified_pending_fresh_audit"
            if current_preflight
            else "remediation_planned_not_completed"
        ),
    }
    (remedy_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_path = out / ".state/candidate-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["audit_subject_hash"] = subject_hash
    manifest["finding_ids_pending_fresh_audit"] = expected_findings
    manifest["remedy_summary"] = (remedy_dir / "summary.json").relative_to(out).as_posix()
    if current_preflight:
        manifest["status"] = "creator_preflight_pass_pending_fresh_independent_audit"
        for task in manifest["tasks"]:
            task["status"] = "remediated_pending_fresh_independent_audit"
    else:
        manifest["retained_count"] = 0
        manifest["status"] = "not_completed_remediation_planned"
        for task in manifest["tasks"]:
            task["primary_core_objective"] = "not_achieved"
            task["status"] = "repair-and-reverify"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return summary


def record_cycle_three_remediation(out: Path = DEFAULT_OUT) -> dict[str, object]:
    """Record cycle-03 mechanism-owned remediation before/after verification."""
    report_path = out / ".state/audit/cycle-03/audit-report.json"
    if not report_path.is_file():
        _fail("audit_evidence_missing", report_path.as_posix())
    report = json.loads(report_path.read_text())
    if report.get("audit_subject_hash") != CYCLE_THREE_SUBJECT:
        _fail("audit_subject_mismatch")
    open_findings = tuple(report.get("finding_status", {}).get("open", ()))
    if open_findings != CYCLE_THREE_FINDINGS:
        _fail("audit_finding_mismatch", repr(open_findings))

    preflight_path = out / ".state/creator-preflight.json"
    current_preflight = False
    if preflight_path.is_file():
        preflight = json.loads(preflight_path.read_text())
        current_preflight = (
            preflight.get("status") == "creator_preflight_pass"
            and preflight.get("tree_hash") == _tree_hash(out)
            and preflight.get("owner_hashes")
            == {path.as_posix(): _file_hash(path) for path in OWNER_PATHS}
        )

    remedy_dir = out / ".state/remedy/cycle-03"
    remedy_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    for case in CASES:
        root = out / case.task_id
        specification = f"""# Cycle-03 remedy for {case.task_id}

Audit subject: `{CYCLE_THREE_SUBJECT}`.

Disposition: `repair-in-place`. Revision 3 must implement
{case.mechanism} through the owned state `{case.state_model}`. The owner must
emit task-specific state roles and executable admission, release, lifecycle,
and ordering transitions rather than the prior shared ledger/marker policy
tables. Literal tests must exercise the named mechanism. The compiled false
substitute must preserve the API and state while reversing this protocol's
documented release/tie rule. Regenerate all 60 roots, rerun all 1,770 pair
decisions, expanded lineage/holdout checks, three coherent clone controls,
three normal and three fresh sanitizer tests per root, and all 60 negatives.
The selected manifest must record executable screens as pass only from the
current bound receipt. No dataset release is requested.
"""
        md_path = remedy_dir / f"{case.task_id}.md"
        md_path.write_text(specification, encoding="utf-8")
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": case.task_id,
            "audit_subject_hash": CYCLE_THREE_SUBJECT,
            "finding_ids": list(CYCLE_THREE_FINDINGS),
            "disposition": "repair-in-place",
            "generator_path": Path(__file__).as_posix(),
            "generator_revision": _file_hash(Path(__file__)),
            "tree_hash_after": _tree_hash(root) if current_preflight else None,
            "remedy_spec_path": md_path.relative_to(out).as_posix(),
            "remedy_spec_hash": _file_hash(md_path),
            "status": (
                "verified_pending_fresh_audit" if current_preflight else "planned"
            ),
            "local_status": (
                "creator_preflight_pass" if current_preflight else "not_completed"
            ),
        }
        (remedy_dir / f"{case.task_id}.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        records.append(record)
    summary = {
        "schema_version": SCHEMA,
        "audit_subject_hash": CYCLE_THREE_SUBJECT,
        "finding_ids": list(CYCLE_THREE_FINDINGS),
        "record_count": len(records),
        "materialized_records": len(records) if current_preflight else 0,
        "remediated_pending_audit": (
            list(CYCLE_THREE_FINDINGS) if current_preflight else []
        ),
        "remaining_findings": list(CYCLE_THREE_FINDINGS),
        "status": (
            "remediation_verified_pending_fresh_audit"
            if current_preflight
            else "remediation_planned_not_completed"
        ),
    }
    (remedy_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def record_cycle_four_remediation(out: Path = DEFAULT_OUT) -> dict[str, object]:
    """Record cycle-04 behavior-gating remediation before/after verification."""
    report_path = out / ".state/audit/cycle-04/audit-report.json"
    report = json.loads(report_path.read_text()) if report_path.is_file() else {}
    if report.get("audit_subject_hash") != CYCLE_FOUR_SUBJECT:
        _fail("audit_subject_mismatch")
    if tuple(report.get("finding_status", {}).get("open", ())) != CYCLE_FOUR_FINDINGS:
        _fail("audit_finding_mismatch")
    preflight_path = out / ".state/creator-preflight.json"
    current_preflight = False
    if preflight_path.is_file():
        preflight = json.loads(preflight_path.read_text())
        current_preflight = (
            preflight.get("status") == "creator_preflight_pass"
            and preflight.get("tree_hash") == _tree_hash(out)
            and preflight.get("owner_hashes")
            == {path.as_posix(): _file_hash(path) for path in OWNER_PATHS}
        )
    remedy_dir = out / ".state/remedy/cycle-04"
    remedy_dir.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        specification = f"""# Cycle-04 remedy for {case.task_id}

Audit subject `{CYCLE_FOUR_SUBJECT}`; disposition `repair-in-place`.
Revision 4 makes `{case.state_model}` a precondition for admission or release
in `{case.mechanism}` instead of post-hoc bookkeeping. The reference must
initialize named protocol state, reject ineligible transitions before generic
record mutation, and update eligibility through the task control. Its compiled
false substitute must invert this exact mechanism gate while preserving the
API and state representation. Literal tests and locked normal/sanitizer
evidence must reject it. Regenerate all 60 roots and rerun every family,
lineage, holdout, prompt, role, clone-control, and receipt gate. Dataset release
is not requested.
"""
        md_path = remedy_dir / f"{case.task_id}.md"
        md_path.write_text(specification, encoding="utf-8")
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": case.task_id,
            "audit_subject_hash": CYCLE_FOUR_SUBJECT,
            "finding_ids": list(CYCLE_FOUR_FINDINGS),
            "disposition": "repair-in-place",
            "generator_path": Path(__file__).as_posix(),
            "generator_revision": _file_hash(Path(__file__)),
            "tree_hash_after": _tree_hash(out / case.task_id) if current_preflight else None,
            "remedy_spec_path": md_path.relative_to(out).as_posix(),
            "remedy_spec_hash": _file_hash(md_path),
            "status": "verified_pending_fresh_audit" if current_preflight else "planned",
            "local_status": "creator_preflight_pass" if current_preflight else "not_completed",
        }
        (remedy_dir / f"{case.task_id}.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    summary = {
        "schema_version": SCHEMA,
        "audit_subject_hash": CYCLE_FOUR_SUBJECT,
        "finding_ids": list(CYCLE_FOUR_FINDINGS),
        "record_count": EXPECTED_ROOTS,
        "materialized_records": EXPECTED_ROOTS if current_preflight else 0,
        "remediated_pending_audit": list(CYCLE_FOUR_FINDINGS) if current_preflight else [],
        "remaining_findings": list(CYCLE_FOUR_FINDINGS),
        "status": (
            "remediation_verified_pending_fresh_audit"
            if current_preflight
            else "remediation_planned_not_completed"
        ),
    }
    (remedy_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--verify-controls", action="store_true")
    parser.add_argument("--finalize-preflight", action="store_true")
    parser.add_argument("--plan-cycle-one-remediation", action="store_true")
    parser.add_argument("--record-cycle-three-remediation", action="store_true")
    parser.add_argument("--record-cycle-four-remediation", action="store_true")
    args = parser.parse_args(argv)
    if args.plan_cycle_one_remediation:
        summary = plan_cycle_one_remediation(args.out)
        print(f"Planned {summary['record_count']} cycle-one remedies under {args.out}")
        return 0
    if args.record_cycle_three_remediation:
        summary = record_cycle_three_remediation(args.out)
        print(
            f"Recorded {summary['record_count']} cycle-three remedies under "
            f"{args.out}: {summary['status']}"
        )
        return 0
    if args.record_cycle_four_remediation:
        summary = record_cycle_four_remediation(args.out)
        print(
            f"Recorded {summary['record_count']} cycle-four remedies under "
            f"{args.out}: {summary['status']}"
        )
        return 0
    if args.finalize_preflight:
        finalize_preflight(args.out)
        print(f"Finalized creator preflight for {EXPECTED_ROOTS} roots under {args.out}")
        return 0
    roots = build(args.out, force=args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    if args.verify_controls:
        verify_adversarial_controls(args.out)
    print(f"Wrote {len(roots)} producer-consumer behavior-structure roots under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
