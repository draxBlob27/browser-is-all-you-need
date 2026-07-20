"""Remediate and reverify the sparse-matrix-encoding Aider task family."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_sparse_matrix_encoding_cases import CASES, SparseCase

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/sparse-matrix-encoding"
)
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-text-grid-reshaping/sparse-matrix-encoding")
CURRICULUM = (
    "docs/aider-synthetic/aider-synthetic-text-grid-reshaping/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_SPARSE_MATRIX_ENCODING_CURRICULUM.md"
)
FAMILY_SPEC = "docs/aider-tasks-spec/aider-text-grid-reshaping/sparse-matrix-encoding.md"
PROMPT_PATH = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
GENERATOR_PATH = "src/w8_biayn/integrations/moonlight_sparse_matrix_encoding_aider_tasks.py"
LEGACY_GENERATOR_REVISION = (
    "sha256:d774a7846d810b783fa7380c8098e7711ccee6a4e5dbe0b304ac5818b00e51a0"
)
FAMILY_ID_BEFORE = "aider-text-grid-reshaping-sparse-matrix-encoding-v1"
FAMILY_ID = "aider-text-grid-reshaping-sparse-matrix-encoding-v2"
MANIFEST_SCHEMA = "aider-sparse-matrix-encoding-materialization-v2"
SEMANTIC_NORMALIZER = "sparse-matrix-v2-identifier-literal-endpoint-neutral-7gram"
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_or_selection_rules",
    "invalid_and_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
HARD_RULE_LIMITS = {
    "public_api": 0.98,
    "owned_state_or_algorithm": 0.85,
    "mutation_or_selection_rules": 0.85,
    "invalid_and_boundary_behavior": 0.90,
    "reference_control_flow": 0.85,
    "deterministic_oracle": 0.97,
    "topic_specific_negative_fixture": 0.85,
}
HARD_RULE_AGGREGATE_LIMIT = 0.90
REQUESTED_ROOT_COUNT = {"minimum": 15, "maximum": 20}
DEFAULT_HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
REMEDY_HEADINGS = (
    "Identity",
    "Objective",
    "Public API",
    "Behavior table",
    "Implementation invariant",
    "Starter and reference",
    "Tests",
    "Files and metadata",
    "Build/oracle",
    "Family/contamination",
    "Optional dataset handoff",
    "Acceptance",
)
OFFICIAL_AIDER_CPP_HOLDOUTS = frozenset(
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
TASKS = CASES

CMAKE = """cmake_minimum_required(VERSION 3.16)
project(sparse_matrix_encoding_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
enable_testing()
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(name visible hidden)
  target_include_directories(task_${name} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(task_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  add_test(NAME ${name} COMMAND task_${name})
endforeach()
"""


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _sha_bytes(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _source_hash(path: Path | None = None) -> str:
    return _sha_bytes((path or Path(__file__)).read_bytes())


def _tree_hash(root: Path) -> str:
    if not root.is_dir():
        return "not_available"
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".state" not in p.parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _safe_relative(value: str) -> str:
    path = PurePosixPath(value)
    if path.is_absolute() or not value or ".." in path.parts:
        _fail("unsafe_path", value)
    return value


def _starter(case: SparseCase) -> str:
    signature = re.search(r"namespace curriculum \{\n(.*?)\)\s*\{", case.reference, re.S)
    if signature is None:
        _fail("header_source_incoherent", case.task_id)
    return (
        f'#include "task.h"\nnamespace curriculum {{\n{signature.group(1)}) '
        "{ return {}; }\n}  // namespace curriculum\n"
    )


def _negative_source(case: SparseCase) -> str:
    if case.reference.count(case.negative_old) != 1:
        _fail("invariant_not_enforced", f"negative mutation drift: {case.task_id}")
    return case.reference.replace(case.negative_old, case.negative_new, 1)


def _remedy_markdown(case: SparseCase) -> str:
    revision = 2 if case.disposition == "repair-in-place" else 1
    return f"""## Identity

Task ID: `{case.task_id}`; legacy root: `{case.legacy_id}`; task-spec revision: {revision}; family ID: `{FAMILY_ID}/{case.task_id}`; disposition: `{case.disposition}`; source inventory: `sparse-matrix-encoding-legacy-v1`; license result: repository-authored/pass; generator: `{GENERATOR_PATH}`; benchmark screen: pending. Selected prompt: `{PROMPT_PATH}` with `FAMILY_NAME=sparse-matrix-encoding`, `FAMILY_TYPE=aider-text-grid-reshaping`.

## Objective

{case.objective}

## Public API

C++17 namespace `curriculum`; editable order is `{case.task_id}.h`, then `{case.task_id}.cpp`. Complete API: `{case.public_api}`. Inputs and results are owned values. Invalid input never returns a partial valid result.

## Behavior table

Valid input executes the stated mechanism and returns the documented canonical ordering. Invalid dimensions, coordinates, duplicates, query bounds, spans, or timestamps return `valid=false` without partial output. Empty input follows the task-visible empty rule. Duplicate handling, stable ties, signed arithmetic, boundary coordinates, and one public boundary example are specified in `.docs/instructions.md` and exercised by the two deterministic tests.

## Implementation invariant

Required mechanism: {case.profile}. Required emitted source marker: `{case.marker}`. The implementation must operate on the sparse input and may not delegate to the legacy dense reconstruction plus generic `row_total` template, a renamed root, hard-coded cases, benchmark assets, or another root's algorithm. Topic false substitute: {case.negative_reason}.

## Starter and reference

The task-named header declares the complete API and the task-named source is an intentionally incomplete coherent stub. `.meta/example.cpp` independently implements `{case.profile}` and does not import the legacy renderer, another replacement, hidden fixtures, or an official holdout.

## Tests

`task_visible_test.cpp` covers the ordinary contract; `.meta/task_hidden_test.cpp` covers empty, invalid, duplicate/tie, and boundary behavior. The compiled topic negative replaces `{case.negative_old}` with `{case.negative_new}` and must be rejected by executed tests. Artifact-derived all-pairs comparison covers all seven hard-rule dimensions: public API, owned state or algorithm, mutation or selection rules, invalid and boundary behavior, reference control flow, deterministic oracle, and topic-specific negative fixture. Pure domain/identifier-renamed, constants/policy-only, and opposite-end-selection controls must still pass the behavioral tests but be rejected by that same semantic screen.

## Files and metadata

Solutions: `{case.task_id}.h`, `{case.task_id}.cpp`; public test: `task_visible_test.cpp`; private test: `.meta/task_hidden_test.cpp`; references: `.meta/example.h`, `.meta/example.cpp`; topic negative: `.meta/negative_false_substitute.cpp`. Config maps each reference to the same-suffix editable file in solution order. Docs, tests, metadata, CMake, references, manifests, controls, and receipts remain private.

## Build/oracle

C++17 with `-Wall -Wextra -Wpedantic -Werror`, explicit `Unix Makefiles`, compiler `c++`, two CTest discoveries. Run clean normal and separate fresh ASan/UBSan builds in `{SANITY_IMAGE}` with Docker network `none`. The receipt binds archive/tree/owner/reference/negative hashes, immutable image identity, compiler and CMake versions, commands, and equal positive test counts.

## Family/contamination

Compare all 190 replacement pairs and all available official C++ holdouts over emitted docs, APIs, references, visible/private tests, and negatives using `{SEMANTIC_NORMALIZER}`. The legacy generic dense-grid template is rejected. Permanent-holdout and family decisions cannot be waived.

## Optional dataset handoff

`not_requested`. No JSONL, token/mask evidence, split, export, consumer verification, training, or release is authorized.

## Acceptance

Run focused pytest, owner `--verify-core`, host `--verify` for iteration, and owner `--docker-sanity`. Require deterministic regeneration, strict prompt/role/reference boundaries, all 190 seven-axis pair decisions, the 26-root holdout screen, compiled/executed rejection of all 20 topic negatives, behavioral passage plus semantic rejection of all three pure clone controls, and two equal positive normal/sanitizer tests per root. Stable failures include `remedy_spec_incomplete`, `prompt_contract_incomplete`, `invariant_not_enforced`, `duplicate_family`, `benchmark_content_overlap`, `generator_output_drift`, `negative_fixture_not_rejected`, `grader_mount_hash_mismatch`, and `sanitizer_test_count_mismatch`.
"""


def _write_remedies(out: Path, force: bool) -> None:
    remedy = out / ".state/remedy"
    for case in CASES:
        markdown = _remedy_markdown(case)
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "family_id_before": FAMILY_ID_BEFORE,
            "family_id_after": f"{FAMILY_ID}/{case.task_id}",
            "tree_hash_before": _tree_hash(LEGACY_ROOT / case.legacy_id),
            "generator_path": GENERATOR_PATH,
            "generator_revision": LEGACY_GENERATOR_REVISION,
            "selected_prompt": PROMPT_PATH,
            "user_inputs": {
                "FAMILY_NAME": "sparse-matrix-encoding",
                "FAMILY_TYPE": "aider-text-grid-reshaping",
            },
            "finding_ids": [
                "SME-F1-shared-dense-template",
                "SME-F2-published-objective-mismatch",
                "SME-F3-family-semantic-duplicates",
                "SME-F4-missing-locked-evidence",
                "SME-F5-missing-executed-negatives",
                "SME-F6-incomplete-hard-rule-evidence",
            ],
            "disposition": case.disposition,
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": f".state/remedy/{case.task_id}.md",
            "remedy_spec_hash": _sha_bytes(markdown.encode()),
            "status": "planned",
            "primary_core_objective": "specified",
            "dataset_handoff": "not_requested",
        }
        _write(remedy / f"{case.task_id}.md", markdown, force)
        _write(
            remedy / f"{case.task_id}.json",
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            force,
        )


def _case_files(case: SparseCase) -> dict[str, str]:
    config = {
        "authors": ["w8-biayn"],
        "blurb": case.objective,
        "files": {
            "solution": ["task.h", "task.cpp"],
            "test": ["task_visible_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "family_id": FAMILY_ID,
        "task_id": case.task_id,
        "legacy_task_id": case.legacy_id,
        "disposition": case.disposition,
        "curriculum_document": CURRICULUM,
        "family_spec": FAMILY_SPEC,
        "selected_prompt": PROMPT_PATH,
        "origin": "independently authored repository remediation",
        "license_result": "repository-authored/pass",
        "semantic_profile": case.profile,
        "primary_core_objective": "achieved",
        "status": "local candidate artifact; dataset handoff not requested",
    }
    return {
        ".docs/introduction.md": f"# {case.title}\n\n{case.objective}\n",
        ".docs/instructions.md": f"# Instructions\n\n{case.instructions}\n",
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": (
            "[visible]\n"
            f'description = "public behavior for {case.title}"\n\n'
            "[hidden]\n"
            f'description = "invalid, duplicate, empty, boundary, and {case.negative_reason} rejection"\n'
        ),
        "task.h": case.header,
        "task.cpp": _starter(case),
        ".meta/example.h": case.header,
        ".meta/example.cpp": case.reference,
        ".meta/negative_false_substitute.cpp": _negative_source(case),
        "task_visible_test.cpp": case.visible_test,
        ".meta/task_hidden_test.cpp": case.hidden_test,
        "CMakeLists.txt": CMAKE,
    }


def _clone_control(case: SparseCase, name: str) -> dict[str, str]:
    header, reference, instructions, visible, hidden, negative = (
        case.header,
        case.reference,
        case.instructions,
        case.visible_test,
        case.hidden_test,
        _negative_source(case),
    )
    if name == "domain-identifier-renamed-clone":
        replacements = (
            ("Star", "Beacon"),
            ("Constellation", "BeaconField"),
            ("constellation", "beacon_field"),
            ("star", "beacon"),
        )
        for old, new in replacements:
            header = header.replace(old, new)
            reference = reference.replace(old, new)
            instructions = instructions.replace(old, new)
            visible = visible.replace(old, new)
            hidden = hidden.replace(old, new)
            negative = negative.replace(old, new)
    elif name == "constants-policy-clone":
        visible = visible.replace("8, 9", "18, 19")
        hidden = hidden.replace("2, 3", "12, 13")
    elif name == "opposite-end-selection-clone":
        reference = reference.replace("stars.front().row", "stars.back().row").replace(
            "stars.front().column", "stars.back().column"
        )
        negative = negative.replace("stars.front().row", "stars.back().row").replace(
            "stars.front().column", "stars.back().column"
        )
    else:
        _fail("invariant_not_enforced", name)
    return {
        "task.h": header,
        "candidate.cpp": reference,
        ".docs/instructions.md": f"# Instructions\n\n{instructions}\n",
        ".meta/negative_false_substitute.cpp": negative,
        "task_visible_test.cpp": visible,
        ".meta/task_hidden_test.cpp": hidden,
        "CMakeLists.txt": CMAKE,
    }


def _write_controls(out: Path, force: bool) -> None:
    root = out / ".state/hard-rule-controls"
    manifest: dict[str, object] = {
        "schema_version": "sparse-matrix-hard-rule-controls-v1",
        "controls": {},
    }
    for name in (
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
    ):
        files = _clone_control(CASES[0], name)
        for relative, content in files.items():
            _write(root / name / relative, content, force)
        manifest["controls"][name] = {
            "expected_compile": "pass",
            "expected_ctest": "pass",
            "expected_semantic_screen": "duplicate_family",
        }
    _write(root / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", force)


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() == LEGACY_ROOT.resolve():
        _fail("legacy_root_immutable", str(out))
    if force:
        for name in (
            "host-verification-receipt.json",
            "materialization-manifest.json",
            "oracle-receipt.json",
        ):
            (out / ".state" / name).unlink(missing_ok=True)
    _write_remedies(out, force)
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        for relative, content in task_named_files(root, _case_files(case)).items():
            _write(root / relative, content, force)
        roots.append(root)
    _write_controls(out, force)
    return tuple(roots)


_CPP_KEYWORDS = frozenset(
    "alignas alignof and and_eq asm auto bitand bitor bool break case catch char class compl const constexpr continue decltype default delete do double dynamic_cast else enum explicit export extern false float for friend goto if inline int long mutable namespace new noexcept not not_eq nullptr operator or or_eq private protected public register reinterpret_cast return short signed sizeof static static_assert static_cast struct switch template this thread_local throw true try typedef typeid typename union unsigned using virtual void volatile wchar_t while xor xor_eq".split()
)


def _normalized_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.M | re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " literal ", text)
    tokens = re.findall(
        r"[A-Za-z_][A-Za-z0-9_]*|\d+|==|!=|<=|>=|&&|\|\||<<|>>|[-+*/%<>{}()[\];,.?:=!&|]", text
    )
    normalized: list[str] = []
    for token in tokens:
        if token.isdigit():
            normalized.append("number")
        elif token in {"begin", "rbegin", "end", "rend", "front", "back"}:
            normalized.append("endpoint")
        elif (
            re.match(r"[A-Za-z_]", token)
            and token not in _CPP_KEYWORDS
            and token
            not in {
                "std",
                "vector",
                "map",
                "set",
                "queue",
                "pair",
                "size_t",
                "sort",
                "max",
                "min",
                "move",
                "numeric_limits",
            }
        ):
            normalized.append("identifier")
        else:
            normalized.append(token)
    return tuple(normalized)


def _ngrams(tokens: tuple[str, ...], width: int = 7) -> set[tuple[str, ...]]:
    if not tokens:
        return set()
    if len(tokens) < width:
        return {tokens}
    return {tokens[index : index + width] for index in range(len(tokens) - width + 1)}


def _containment(left: str, right: str) -> float:
    a, b = _ngrams(_normalized_tokens(left)), _ngrams(_normalized_tokens(right))
    denominator = min(len(a), len(b))
    return len(a & b) / denominator if denominator else 0.0


def _artifact_dimensions(
    root: Path, *, reference_path: str = ".meta/example.cpp"
) -> dict[str, str]:
    public_api = next(root.glob("*.h")).read_text(encoding="utf-8")
    instructions = (root / ".docs/instructions.md").read_text(encoding="utf-8")
    reference = (root / reference_path).read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    hidden = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
    negative = (root / ".meta/negative_false_substitute.cpp").read_text(encoding="utf-8")
    dimensions = {
        "public_api": public_api,
        "owned_state_or_algorithm": reference,
        "mutation_or_selection_rules": f"{instructions}\n{reference}",
        "invalid_and_boundary_behavior": f"{instructions}\n{hidden}",
        "reference_control_flow": reference,
        "deterministic_oracle": f"{visible}\n{hidden}",
        "topic_specific_negative_fixture": negative,
    }
    if tuple(dimensions) != HARD_RULE_DIMENSIONS:
        _fail("invariant_not_enforced", "hard-rule dimension drift")
    return dimensions


def _compare_hard_rule_dimensions(
    left_parts: dict[str, str],
    right_parts: dict[str, str],
    left_id: str,
    right_id: str,
) -> dict[str, object]:
    scores = {
        name: round(_containment(left_parts[name], right_parts[name]), 6)
        for name in HARD_RULE_DIMENSIONS
    }
    structurally_distinct = {
        name: _normalized_tokens(left_parts[name]) != _normalized_tokens(right_parts[name])
        for name in HARD_RULE_DIMENSIONS
    }
    materially_distinct = {
        name: structurally_distinct[name] and scores[name] < HARD_RULE_LIMITS[name]
        for name in HARD_RULE_DIMENSIONS
    }
    aggregate = round(
        _containment("\n".join(left_parts.values()), "\n".join(right_parts.values())), 6
    )
    failed = [name for name, distinct in materially_distinct.items() if not distinct]
    if failed or aggregate >= HARD_RULE_AGGREGATE_LIMIT:
        detail = (
            f"{left_id}/{right_id}: axes={','.join(failed) or 'aggregate'}, aggregate={aggregate}"
        )
        _fail("duplicate_family", detail)
    return {
        "left": left_id,
        "right": right_id,
        "aggregate_containment": aggregate,
        "scores": scores,
        **{f"{name}_structurally_distinct": value for name, value in structurally_distinct.items()},
        **{f"{name}_materially_distinct": value for name, value in materially_distinct.items()},
    }


def _pair_matrix(out: Path) -> dict[str, object]:
    if not REQUESTED_ROOT_COUNT["minimum"] <= len(CASES) <= REQUESTED_ROOT_COUNT["maximum"]:
        _fail("invariant_not_enforced", f"root count {len(CASES)} outside requested bounds")
    rows: list[dict[str, object]] = []
    for index, left in enumerate(CASES):
        left_parts = _artifact_dimensions(out / left.task_id)
        if left.marker not in left_parts["reference_control_flow"]:
            _fail("invariant_not_enforced", left.task_id)
        for right in CASES[index + 1 :]:
            right_parts = _artifact_dimensions(out / right.task_id)
            rows.append(
                _compare_hard_rule_dimensions(left_parts, right_parts, left.task_id, right.task_id)
            )
    expected_pairs = len(CASES) * (len(CASES) - 1) // 2
    if len(rows) != expected_pairs:
        _fail("duplicate_family", f"expected {expected_pairs} pairs, found {len(rows)}")
    return {
        "status": "pending_execution",
        "normalizer": SEMANTIC_NORMALIZER,
        "pair_count": len(rows),
        "expected_pair_count": expected_pairs,
        "requested_root_count": REQUESTED_ROOT_COUNT,
        "materialized_root_count": len(CASES),
        "count_within_bounds": True,
        "dimensions": list(HARD_RULE_DIMENSIONS),
        "dimension_limits": HARD_RULE_LIMITS,
        "aggregate_limit": HARD_RULE_AGGREGATE_LIMIT,
        "pairs": rows,
    }


def _screen_controls(out: Path) -> dict[str, dict[str, object]]:
    base = _artifact_dimensions(out / CASES[0].task_id)
    outcomes: dict[str, dict[str, object]] = {}
    for name in (
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
    ):
        root = out / ".state/hard-rule-controls" / name
        clone = _artifact_dimensions(root, reference_path="candidate.cpp")
        try:
            _compare_hard_rule_dimensions(
                base,
                clone,
                CASES[0].task_id,
                name,
            )
        except RuntimeError as error:
            if not str(error).startswith("duplicate_family:"):
                raise
            outcomes[name] = {
                "status": "rejected",
                "reason": "duplicate_family",
                "production_comparator": True,
                "detail": str(error),
            }
        else:
            _fail("duplicate_family", f"adversarial control escaped: {name}")
    return outcomes


def _benchmark_id_screen(root: Path) -> None:
    corpus = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    )
    lowered = corpus.lower()
    for slug in OFFICIAL_AIDER_CPP_HOLDOUTS:
        if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", lowered):
            _fail("benchmark_id_overlap", f"{root.name}:{slug}")


def _semantic_holdout_screen(
    out: Path, holdout_root: Path = DEFAULT_HOLDOUT_ROOT
) -> dict[str, object]:
    if not holdout_root.is_dir():
        _fail("benchmark_screen_not_completed", str(holdout_root))
    inventory = hashlib.sha256()
    holdouts: dict[str, str] = {}
    for root in sorted(path for path in holdout_root.iterdir() if path.is_dir()):
        chunks: list[str] = []
        for path in sorted(
            p
            for p in root.rglob("*")
            if p.is_file() and p.suffix in {".h", ".hpp", ".cpp"} and "catch" not in p.name
        ):
            inventory.update(path.relative_to(holdout_root).as_posix().encode())
            inventory.update(b"\0")
            inventory.update(path.read_bytes())
            inventory.update(b"\0")
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        holdouts[root.name] = "\n".join(chunks)
    if set(OFFICIAL_AIDER_CPP_HOLDOUTS) - set(holdouts):
        _fail("benchmark_screen_not_completed", "official holdout inventory incomplete")
    strongest: dict[str, object] = {"candidate": None, "holdout": None, "containment": 0.0}
    for case in CASES:
        candidate = "\n".join(_artifact_dimensions(out / case.task_id).values())
        for slug, corpus in holdouts.items():
            score = _containment(candidate, corpus)
            if score > float(strongest["containment"]):
                strongest = {
                    "candidate": case.task_id,
                    "holdout": slug,
                    "containment": round(score, 6),
                }
            if score >= 0.72:
                _fail("benchmark_content_overlap", f"{case.task_id}/{slug}:{score:.3f}")
    return {
        "status": "pass",
        "normalizer": SEMANTIC_NORMALIZER,
        "source_inventory": f"sha256:{inventory.hexdigest()}",
        "holdout_root_count": len(holdouts),
        "comparison_count": len(CASES) * len(holdouts),
        "threshold": 0.72,
        "strongest": strongest,
    }


def _verify_remedies(out: Path) -> None:
    remedy = out / ".state/remedy"
    expected = {case.task_id for case in CASES}
    records = {path.stem: path for path in remedy.glob("*.json")} if remedy.is_dir() else {}
    if set(records) != expected:
        _fail("remedy_spec_incomplete", "one record per affected legacy root")
    for case in CASES:
        record = json.loads(records[case.task_id].read_text(encoding="utf-8"))
        spec = remedy / f"{case.task_id}.md"
        text = spec.read_text(encoding="utf-8") if spec.is_file() else ""
        positions = [text.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if record.get("disposition") != case.disposition:
            _fail("remedy_disposition_conflict", case.task_id)
        if (
            -1 in positions
            or positions != sorted(positions)
            or record.get("remedy_spec_hash") != _sha_bytes(text.encode())
        ):
            _fail("remedy_spec_incomplete", case.task_id)
        if record.get("tree_hash_before") != _tree_hash(LEGACY_ROOT / case.legacy_id):
            _fail("generator_output_drift", f"legacy hash changed: {case.legacy_id}")


def _whole_answer_is_exact(root: Path) -> bool:
    task = load_task(root)
    answer = build_assistant_response(task, load_example_files_from_config(root))
    return (
        answer.startswith(f"{root.name}.h\n```")
        and f"{root.name}.cpp\n```" in answer
        and ".meta/example" not in answer
    )


def _sync_remedies(out: Path, **updates: object) -> None:
    for case in CASES:
        path = out / ".state/remedy" / f"{case.task_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update(updates)
        record["tree_hash_after"] = _tree_hash(out / case.task_id)
        record["changed_owner_paths"] = [
            GENERATOR_PATH,
            "src/w8_biayn/integrations/moonlight_sparse_matrix_encoding_cases.py",
            "tests/test_moonlight_sparse_matrix_encoding_aider_tasks.py",
            CURRICULUM,
            FAMILY_SPEC,
            "examples/slime/moonlight_cpp_perf/prepare_sparse_matrix_encoding_aider_tasks.sh",
        ]
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def verify_core(out: Path) -> None:
    expected = {case.task_id for case in CASES}
    actual = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", f"expected {sorted(expected)}, found {sorted(actual)}")
    _verify_remedies(out)
    with tempfile.TemporaryDirectory(prefix="sparse-matrix-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for case in CASES:
            if _tree_hash(out / case.task_id) != _tree_hash(fresh / case.task_id):
                _fail("generator_output_drift", case.task_id)
    pair_matrix = _pair_matrix(out)
    controls = _screen_controls(out)
    holdout = _semantic_holdout_screen(out)
    tasks: list[dict[str, object]] = []
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        files = config["files"]
        solution = [_safe_relative(item) for item in files["solution"]]
        tests = [_safe_relative(item) for item in files["test"]]
        examples = [_safe_relative(item) for item in files["example"]]
        if solution != [f"{case.task_id}.h", f"{case.task_id}.cpp"] or examples != [
            ".meta/example.h",
            ".meta/example.cpp",
        ]:
            _fail("target_reference_mismatch", case.task_id)
        if any(
            name.startswith((".meta/", ".docs/")) or name == "CMakeLists.txt" for name in solution
        ):
            _fail("unsafe_path", case.task_id)
        if any(not (root / name).is_file() for name in [*solution, *tests, *examples]):
            _fail("reference_map_failed", case.task_id)
        prompt = build_prompt(load_task(root))
        forbidden = [
            *tests,
            *examples,
            "CMakeLists.txt",
            ".meta/provenance.json",
            ".meta/task_hidden_test.cpp",
            ".meta/negative_false_substitute.cpp",
        ]
        if any(item in prompt for item in forbidden) or not all(
            item in prompt for item in solution
        ):
            _fail("prompt_contract_incomplete", case.task_id)
        if not _whole_answer_is_exact(root):
            _fail("whole_format_failed", case.task_id)
        _benchmark_id_screen(root)
        tasks.append(
            {
                "task_id": case.task_id,
                "legacy_task_id": case.legacy_id,
                "disposition": case.disposition,
                "tree_hash_before": _tree_hash(LEGACY_ROOT / case.legacy_id),
                "tree_hash_after": _tree_hash(root),
                "semantic_profile": case.profile,
                "primary_core_objective": "achieved",
            }
        )
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "family_id": FAMILY_ID,
        "task_count": len(CASES),
        "owner_hash": _source_hash(),
        "status": "implemented",
        "hard_rule_status": "pending_execution",
        "tasks": tasks,
        "screen": {
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
            "duplicate_family": "pass",
            "hard_rule": pair_matrix,
            "adversarial_controls": controls,
            "benchmark_contamination": "pass",
            "semantic_holdout": holdout,
        },
    }
    _write(
        out / ".state/materialization-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        True,
    )
    _sync_remedies(
        out,
        status="implemented",
        primary_core_objective="achieved",
        prompt_boundary="pass",
        reference_mapping="pass",
        family_screen="pass",
        benchmark_screen="pass",
        semantic_holdout_screen=holdout,
        hard_rule_status="pending_execution",
        strongest_local_status="implemented",
    )


def _ctest_count(build_dir: Path) -> int:
    result = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "-N"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    match = re.search(r"Total Tests:\s*(\d+)", result.stdout + result.stderr)
    if match is None or int(match.group(1)) <= 0:
        _fail("zero_tests", str(build_dir))
    return int(match.group(1))


def verify(out: Path) -> None:
    verify_core(out)
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        _fail("host_verification_not_completed", "verification requires cmake and c++")
    counts: dict[str, dict[str, int]] = {}
    for case in CASES:
        root = out / case.task_id
        with tempfile.TemporaryDirectory(prefix=f"sparse-matrix-{case.task_id}-") as temporary:
            copied = Path(temporary) / case.task_id
            shutil.copytree(root, copied)
            for mode, flags in (
                ("normal", []),
                (
                    "sanitizer",
                    [
                        "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
                        "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
                    ],
                ),
            ):
                build_dir = Path(temporary) / f"build-{mode}"
                subprocess.run(
                    [
                        "cmake",
                        "-S",
                        str(copied),
                        "-B",
                        str(build_dir),
                        "-G",
                        "Unix Makefiles",
                        "-DCMAKE_CXX_COMPILER=c++",
                        f"-DTASK_SOURCE={copied / '.meta/example.cpp'}",
                        *flags,
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                subprocess.run(
                    ["cmake", "--build", str(build_dir), "--parallel", "2"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                count = _ctest_count(build_dir)
                subprocess.run(
                    ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                counts.setdefault(case.task_id, {})[mode] = count
            negative = Path(temporary) / "build-negative"
            subprocess.run(
                [
                    "cmake",
                    "-S",
                    str(copied),
                    "-B",
                    str(negative),
                    "-G",
                    "Unix Makefiles",
                    "-DCMAKE_CXX_COMPILER=c++",
                    f"-DTASK_SOURCE={copied / '.meta/negative_false_substitute.cpp'}",
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            subprocess.run(
                ["cmake", "--build", str(negative), "--parallel", "2"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if (
                _ctest_count(negative) != 2
                or subprocess.run(
                    ["ctest", "--test-dir", str(negative)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                ).returncode
                == 0
            ):
                _fail("negative_fixture_not_rejected", case.task_id)
    for task_id, modes in counts.items():
        if modes.get("normal") != 2 or modes.get("sanitizer") != 2:
            _fail("sanitizer_test_count_mismatch", task_id)
    receipt = {
        "schema_version": "aider-sparse-matrix-host-iteration-v1",
        "evidence_class": "host_iteration_only",
        "local_family_verified": False,
        "owner_hash": _source_hash(),
        "test_counts": counts,
    }
    _write(
        out / ".state/host-verification-receipt.json",
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        True,
    )


def _deterministic_archive(out: Path, destination: Path) -> str:
    with tarfile.open(destination, "w") as archive:
        roots = [(Path(case.task_id), out / case.task_id) for case in CASES]
        roots.append((Path(".hard-rule-controls"), out / ".state/hard-rule-controls"))
        for prefix, root in roots:
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                data = path.read_bytes()
                info = tarfile.TarInfo((prefix / path.relative_to(root)).as_posix())
                info.size = len(data)
                info.mode = 0o644
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(data))
    return _sha_bytes(destination.read_bytes())


def docker_sanity(out: Path, image: str = SANITY_IMAGE) -> None:
    verify_core(out)
    if shutil.which("docker") is None:
        _fail("docker_sanity_not_completed", "docker executable unavailable")
    inspect = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if inspect.returncode:
        _fail("docker_sanity_not_completed", inspect.stderr.strip())
    image_id = inspect.stdout.strip()
    with tempfile.TemporaryDirectory(prefix="sparse-matrix-docker-") as temporary:
        temp = Path(temporary)
        archive = temp / "family.tar"
        results = temp / "results"
        results.mkdir()
        archive_hash = _deterministic_archive(out, archive)
        runner = r"""set -eu
mkdir -p /tmp/family
tar -xf /input/family.tar -C /tmp/family
: > /result/counts.tsv
: > /result/topic-negative.tsv
: > /result/adversarial-controls.tsv
c++ --version | head -1 > /result/compiler.txt
cmake --version | head -1 > /result/cmake.txt
for root in /tmp/family/*; do
  task=$(basename "$root")
  for mode in normal sanitizer; do
    build="/tmp/build-${task}-${mode}"
    if [ "$mode" = sanitizer ]; then
      cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp" "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"
    else
      cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp"
    fi
    cmake --build "$build" --parallel 2
    count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
    test -n "$count" && test "$count" -gt 0
    ctest --test-dir "$build" --output-on-failure
    printf '%s\t%s\t%s\n' "$task" "$mode" "$count" >> /result/counts.tsv
  done
  negative="/tmp/build-${task}-negative"
  cmake -S "$root" -B "$negative" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/negative_false_substitute.cpp"
  cmake --build "$negative" --parallel 2
  count=$(ctest --test-dir "$negative" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
  set +e; ctest --test-dir "$negative" --output-on-failure; code=$?; set -e
  test "$count" -gt 0 && test "$code" -ne 0
  printf '%s\t%s\t%s\n' "$task" "$count" "$code" >> /result/topic-negative.tsv
done
for root in /tmp/family/.hard-rule-controls/*; do
  test -d "$root" || continue
  name=$(basename "$root"); build="/tmp/build-control-${name}"
  cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/candidate.cpp"
  cmake --build "$build" --parallel 2
  count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
  set +e; ctest --test-dir "$build" --output-on-failure; code=$?; set -e
  test "$count" -gt 0 && test "$code" -eq 0
  printf '%s\t%s\t%s\n' "$name" "$count" "$code" >> /result/adversarial-controls.tsv
done
sha256sum /input/family.tar | awk '{print "sha256:" $1}' > /result/archive.sha256
"""
        command = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--mount",
            f"type=bind,src={archive},dst=/input/family.tar,readonly",
            "--mount",
            f"type=bind,src={results},dst=/result",
            image,
            "sh",
            "-lc",
            runner,
        ]
        run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if run.returncode:
            _fail("docker_sanity_failed", run.stdout[-6000:])
        mounted = (results / "archive.sha256").read_text(encoding="utf-8").strip()
        if mounted != archive_hash:
            _fail("grader_mount_hash_mismatch", f"owner={archive_hash} docker={mounted}")
        counts: dict[str, dict[str, int]] = {}
        for line in (results / "counts.tsv").read_text(encoding="utf-8").splitlines():
            task_id, mode, raw = line.split("\t")
            counts.setdefault(task_id, {})[mode] = int(raw)
        expected = {case.task_id for case in CASES}
        if set(counts) != expected:
            _fail("test_discovery_failed", "incomplete task inventory")
        for task_id, modes in counts.items():
            if modes.get("normal", 0) <= 0 or modes.get("normal") != modes.get("sanitizer"):
                _fail("sanitizer_test_count_mismatch", task_id)
        negatives: dict[str, dict[str, object]] = {}
        for line in (results / "topic-negative.tsv").read_text(encoding="utf-8").splitlines():
            task_id, raw_count, raw_code = line.split("\t")
            negatives[task_id] = {
                "compiled": True,
                "discovered_tests": int(raw_count),
                "ctest_exit": int(raw_code),
                "rejected_by_executed_tests": int(raw_code) != 0,
            }
        if set(negatives) != expected or any(
            not row["rejected_by_executed_tests"] for row in negatives.values()
        ):
            _fail("negative_fixture_not_rejected", "topic-negative receipt")
        controls: dict[str, dict[str, object]] = {}
        for line in (results / "adversarial-controls.tsv").read_text(encoding="utf-8").splitlines():
            name, raw_count, raw_code = line.split("\t")
            controls[name] = {
                "compiled": True,
                "discovered_tests": int(raw_count),
                "ctest_exit": int(raw_code),
                "behavior_tests_passed": int(raw_code) == 0,
                "semantic_screen": "rejected:duplicate_family",
            }
        if set(controls) != {
            "domain-identifier-renamed-clone",
            "constants-policy-clone",
            "opposite-end-selection-clone",
        } or any(not row["behavior_tests_passed"] for row in controls.values()):
            _fail("adversarial_control_not_pure", "behavior-preserving clone controls")
        receipt = {
            "schema_version": "aider-sparse-matrix-docker-sanity-v2",
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "network_policy": "none",
            "image": image,
            "image_id": image_id,
            "archive_hash": archive_hash,
            "owner_hash": _source_hash(),
            "family_tree_hashes": {case.task_id: _tree_hash(out / case.task_id) for case in CASES},
            "reference_hashes": {
                case.task_id: _source_hash(out / case.task_id / ".meta/example.cpp")
                for case in CASES
            },
            "negative_hashes": {
                case.task_id: _source_hash(
                    out / case.task_id / ".meta/negative_false_substitute.cpp"
                )
                for case in CASES
            },
            "compiler": (results / "compiler.txt").read_text(encoding="utf-8").strip(),
            "cmake": (results / "cmake.txt").read_text(encoding="utf-8").strip(),
            "commands": {
                "docker": command[:8] + [image, "sh", "-lc", "<owner-controlled-runner>"],
                "normal": "fresh Unix Makefiles reference build and ctest",
                "sanitizer": "fresh ASan/UBSan Unix Makefiles reference build and ctest",
                "topic_negative": "strict build and executed-test rejection",
                "adversarial_controls": "strict build and behavioral passage plus semantic rejection",
            },
            "test_counts": counts,
            "topic_negatives": negatives,
            "adversarial_controls": controls,
        }
        receipt_path = out / ".state/oracle-receipt.json"
        _write(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        receipt_hash = _source_hash(receipt_path)
        manifest_path = out / ".state/materialization-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["status"] = "local_family_verified"
        manifest["hard_rule_status"] = "pass"
        manifest["screen"]["hard_rule"]["status"] = "pass"
        manifest["screen"]["hard_rule"]["topic_negative_execution"] = negatives
        manifest["screen"]["hard_rule"]["adversarial_control_execution"] = controls
        manifest["oracle_receipt"] = ".state/oracle-receipt.json"
        manifest["oracle_receipt_hash"] = receipt_hash
        manifest["evidence_class"] = "docker_sanity"
        manifest["locked_oracle"] = False
        _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
        _sync_remedies(
            out,
            status="verified",
            oracle_evidence={
                "status": "pass",
                "evidence_class": "docker_sanity",
                "locked_oracle": False,
                "receipt_path": ".state/oracle-receipt.json",
                "receipt_hash": receipt_hash,
                "image": image_id,
                "network": "none",
                "normal_discovered_tests": 2,
                "sanitizer_discovered_tests": 2,
                "topic_negative_discovered_tests": 2,
                "topic_negative_rejected": True,
                "pure_clone_controls_behavior_tests_passed": True,
                "pure_clone_controls_semantically_rejected": True,
            },
            hard_rule_status="pass",
            strongest_local_status="local_family_verified",
        )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true", help="host-only iteration evidence")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    if args.docker_sanity:
        docker_sanity(args.out, args.image)
    print(f"Wrote {len(roots)} sparse-matrix-encoding v2 tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
