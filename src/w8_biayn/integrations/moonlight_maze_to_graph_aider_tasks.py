from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from itertools import combinations
from pathlib import Path

from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
    load_task,
)
from w8_biayn.integrations.moonlight_maze_to_graph_cases import (
    CASES,
    MazeGraphCase,
)

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/"
    "aider-text-grid-reshaping/maze-to-graph"
)
LEGACY_OUT = Path(
    ".w8-biayn/data/aider-tasks/"
    "aider-text-grid-reshaping/maze-to-graph"
)
CURRICULUM = (
    "docs/aider-synthetic/aider-synthetic-text-grid-reshaping/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_MAZE_TO_GRAPH_CURRICULUM.md"
)
FAMILY_SPEC = (
    "docs/aider-tasks-spec/aider-text-grid-reshaping/maze-to-graph.md"
)
PROMPT_PATH = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
NORMALIZER = "maze-to-graph-hard-rule-v4-artifact-dimension-shingles"
PAIR_THRESHOLD = 0.84
FAMILY_ROOT_MIN = 20
FAMILY_ROOT_MAX = 20
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
HARD_RULE_THRESHOLDS = {dimension: 0.85 for dimension in HARD_RULE_DIMENSIONS}
ADVERSARIAL_CONTROLS = (
    "domain-identifier-renamed",
    "constants-or-policy-only",
    "opposite-end-selection",
)


class VerificationError(RuntimeError):
    pass


def _fail(code: str, detail: str) -> None:
    raise VerificationError(f"{code}: {detail}")


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rel = path.relative_to(root).as_posix().encode()
        digest.update(len(rel).to_bytes(8, "big"))
        digest.update(rel)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def _reference_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for name in (".meta/example.h", ".meta/example.cpp"):
        data = (root / name).read_bytes()
        digest.update(name.encode())
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def _generator_revision() -> str:
    digest = hashlib.sha256()
    for path in (
        Path(__file__),
        Path(__file__).with_name("moonlight_maze_to_graph_cases.py"),
    ):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def _header(case: MazeGraphCase) -> str:
    return (
        "#pragma once\n"
        "#include <array>\n#include <cstddef>\n#include <cstdint>\n"
        "#include <stdexcept>\n#include <string>\n#include <utility>\n#include <vector>\n"
        "namespace curriculum {\n"
        f"{case.types}\n{case.return_type} {case.function}({case.params});\n"
        "}\n"
    )


def _format_cpp_body(body: str) -> str:
    output: list[str] = []
    paren_depth = 0
    quote: str | None = None
    escaped = False
    for char in body:
        output.append(char)
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
        elif char == ";" and paren_depth == 0:
            output.append("\n")
        elif char == "}":
            output.append("\n")
    return "".join(output)


def _source(case: MazeGraphCase) -> str:
    return (
        f'#include "{case.task_id}.h"\n'
        "#include <algorithm>\n#include <limits>\n#include <map>\n"
        "#include <functional>\n#include <numeric>\n#include <queue>\n"
        "#include <set>\n#include <tuple>\n#include <utility>\n"
        "namespace curriculum {\n"
        f"{case.return_type} {case.function}({case.params}) {{\n{_format_cpp_body(case.body)}\n}}\n"
        "}\n"
    )


def _negative(case: MazeGraphCase) -> str:
    if case.body.count(case.negative_old) != 1:
        _fail("negative_fixture_drift", case.task_id)
    body = case.body.replace(case.negative_old, case.negative_new)
    return (
        f'#include "../{case.task_id}.h"\n'
        "#include <algorithm>\n#include <limits>\n#include <map>\n"
        "#include <functional>\n#include <numeric>\n#include <queue>\n"
        "#include <set>\n#include <tuple>\n#include <utility>\n"
        "namespace curriculum {\n"
        f"{case.return_type} {case.function}({case.params}) {{\n"
        f"{_format_cpp_body(body)}\n}}\n"
        "}\n"
    )


def _test(case: MazeGraphCase, body: str) -> str:
    return (
        f'#include "{case.task_id}.h"\n#include <string>\n#include <vector>\n'
        "using namespace curriculum;\nint main() {\n"
        f"{_format_cpp_body(body)}\n"
        "}\n"
    )


def _cmake(case: MazeGraphCase) -> str:
    return f'''cmake_minimum_required(VERSION 3.16)
project({case.task_id} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${{CMAKE_CURRENT_SOURCE_DIR}}/{case.task_id}.cpp" CACHE FILEPATH "Reference source")
foreach(target task_visible task_hidden)
  if(target STREQUAL "task_visible")
    add_executable(${{target}} ${{TASK_SOURCE}} task_visible_test.cpp)
  else()
    add_executable(${{target}} ${{TASK_SOURCE}} .meta/task_hidden_test.cpp)
  endif()
  target_include_directories(${{target}} PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${{target}} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
add_executable(task_negative .meta/negative.cpp task_visible_test.cpp)
target_include_directories(task_negative PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(task_negative PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_test(NAME negative_fixture COMMAND task_negative)
set_tests_properties(negative_fixture PROPERTIES WILL_FAIL TRUE)
'''


def _instructions(case: MazeGraphCase) -> str:
    terms = ", ".join(f"`{term}`" for term in case.prompt_terms)
    return f"""# {case.title}

Implement `{case.function}` in namespace `curriculum` using the declarations in
`{case.task_id}.h`. The task is {case.objective}.

Every root is a pure graph construction. Validate rectangular shape, symbols,
labels, bounds, duplicates, and task parameters before returning a graph.
Invalid input returns the default report with `valid == false`; an empty outer
grid is valid and returns an empty graph. Vertices are numbered in the
task-specific row-major or label order stated below.

The complete ordering and tie rules are part of the public contract. In
particular the implementation must preserve these capability terms: {terms}.
Use the task-specific canonical ordering for vertices, edges, and diagnostics.
Grid coordinates use a top-left origin with rows increasing downward and
columns increasing rightward. Private tests exercise these published rules.
"""


def _files(case: MazeGraphCase) -> dict[str, str]:
    header = _header(case)
    config = {
        "authors": ["w8-biayn"],
        "blurb": case.objective.capitalize() + ".",
        "files": {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "curriculum_document": CURRICULUM,
        "family_specification": FAMILY_SPEC,
        "curriculum_task_id": case.task_id,
        "legacy_task_id": case.legacy_id,
        "origin": "newly-authored clean-room repository remediation",
        "prompt_path": PROMPT_PATH,
        "status": "local candidate artifact; not admitted SFT data",
        "version": 2,
        "family_id": f"maze-to-graph-v2/{case.task_id}",
        "semantic_profile": case.profile,
        "benchmark_separation": (
            "Artifact-derived screen against all bound official Aider C++ holdouts."
        ),
    }
    files = {
        ".docs/introduction.md": (
            f"# {case.title}\n\nA local clean-room graph construction task.\n"
        ),
        ".docs/instructions.md": _instructions(case),
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True)
        + "\n",
        ".meta/tests.toml": (
            '[visible]\ndescription = "principal transformation and diagnostics"\n\n'
            '[hidden]\ndescription = "validation, boundary, ordering, and false-substitute rejection"\n'
        ),
        ".meta/example.h": header,
        ".meta/example.cpp": _source(case),
        ".meta/task_hidden_test.cpp": _test(case, case.hidden),
        ".meta/negative.cpp": _negative(case),
        f"{case.task_id}.h": header,
        f"{case.task_id}.cpp": (
            f'#include "{case.task_id}.h"\nnamespace curriculum {{\n'
            f"{case.return_type} {case.function}({case.params}) {{ return {{}}; }}\n"
            "}\n"
        ),
        "task_visible_test.cpp": _test(case, case.visible),
        "CMakeLists.txt": _cmake(case),
    }
    return task_named_files(Path(case.task_id), files)


def _remedy_markdown(case: MazeGraphCase) -> str:
    disposition = "repair-in-place" if case.task_id == case.legacy_id else "replace"
    return f"""## Identity

Legacy task ID: `{case.legacy_id}`; replacement task ID: `{case.task_id}`; task-spec revision: 2; family ID: `maze-to-graph-v2/{case.task_id}`; disposition: `{disposition}`; source inventory: `maze-to-graph-legacy-v1`; license: repository-authored/pass; generator: `src/w8_biayn/integrations/moonlight_maze_to_graph_aider_tasks.py`; benchmark screen: pending. Selected prompt: `{PROMPT_PATH}` with `FAMILY_NAME=maze-to-graph` and `FAMILY_TYPE=aider-text-grid-reshaping`.

## Objective

The observable capability is to {case.objective}. This objective is tested through complete returned state and task-specific diagnostics, not by a name or marker alone.

## Public API

C++17 namespace `curriculum`; editable-file order is `{case.task_id}.h`, `{case.task_id}.cpp`. Declaration: `{case.return_type} {case.function}({case.params})`. Public types: `{case.types}`. Inputs, ownership, mutation, invalid results, and result ordering follow the visible instructions and declarations.

## Behavior table

Valid input executes `{case.profile}` and returns `valid == true` with the documented complete graph state. Ragged or empty rows, duplicate identities, unknown symbols, invalid bounds, and invalid numeric parameters return the default invalid report; all roots are pure. An empty outer grid is a valid empty graph. Ordering and tie behavior is deterministic and task-specific. Arithmetic and indexing are checked before use. The visible test is the public boundary example and the private test covers invalid, empty, duplicate, and boundary behavior.

## Implementation invariant

Required mechanism: `{case.profile}`. Required reference marker: `{case.marker}`. Forbidden substitutes are the legacy `GraphAudit` superset and generic four-neighbor component template, domain or identifier renames, constants/policy-only copies, opposite-end variants, a policy switch over one shared graph builder, hard-coded examples, and benchmark assets. The private negative fixture is: {case.negative_description}.

## Starter and reference

The task-named header declares the complete API and the task-named source is a coherent default-report starter. `.meta/example.h` and `.meta/example.cpp` are independently generated complete replacements. The reference owns the named mechanism and imports neither legacy renderers nor hidden fixtures.

## Tests

The visible executable covers the principal transformation and observable report. The private executable covers validation and task-specific boundaries. The deterministic negative fixture replaces exactly `{case.negative_old}` with `{case.negative_new}` and must compile under strict flags, execute, and be rejected by the visible test. Family controls cover domain/identifier rename, constants/policy-only mutation, and opposite-end selection.

## Files and metadata

Solutions: `{case.task_id}.h`, `{case.task_id}.cpp`. Tests: `task_visible_test.cpp`, `.meta/task_hidden_test.cpp`. References: `.meta/example.h`, `.meta/example.cpp`, mapped by suffix and ordered with solutions. `.meta/negative.cpp`, docs, tests, references, metadata, CMake, and receipts stay private. Provenance binds `{case.legacy_id}`, `{case.profile}`, `{CURRICULUM}`, `{FAMILY_SPEC}`, and the selected prompt.

## Build/oracle

C++17, strict `-Wall -Wextra -Wpedantic -Werror`, explicit `Unix Makefiles`, three CTest entries, and the pinned `{SANITY_IMAGE}` image with Docker network `none`. Clean normal and fresh ASan/UBSan builds must each discover three tests, including the expected-failing executed negative fixture. Receipts bind deterministic archive, live and mounted tree hashes, owner/reference hashes, image identity, compiler/CMake versions, commands, network policy, and counts.

## Family/contamination

Compare all 190 unordered emitted-root pairs separately across public API, owned state/algorithm, mutation/selection rules, invalid/boundary behavior, reference control flow, deterministic oracle, and topic-specific negative fixture. Every dimension must remain below its fail-closed threshold; an aggregate score cannot offset a duplicate dimension. Also compare emitted artifacts with all 26 bound official C++ holdouts using `{NORMALIZER}` for 520 mandatory comparisons. Coherent domain/identifier-renamed, constants/policy-only, and opposite-end-selection clones must each be rejected in all seven dimensions and must compile and execute in the Docker oracle. No near-match waiver is allowed.

## Optional dataset handoff

`not_requested`. This remediation creates no JSONL, token/mask evidence, split, export, consumer verification, training run, dataset release, or benchmark-uplift claim.

## Acceptance

Run focused pytest, owner `--verify-core`, owner host `--verify`, and owner `--docker-sanity`. Require generator-owned regeneration, exact prompt/role/reference mapping, executed negative rejection, all 190 pair-by-dimension hard-rule decisions, all 520 bound-holdout comparisons, coherent compiled adversarial controls, equal positive normal/sanitizer discovery, and owner acceptance of independently mounted tree digests for roots and controls. Stable failures include `remedy_spec_incomplete`, `hard_rule_evidence_incomplete`, `adversarial_control_invalid`, `prompt_contract_incomplete`, `invariant_not_enforced`, `duplicate_family`, `benchmark_content_overlap`, `generator_output_drift`, `grader_mount_hash_mismatch`, and `sanitizer_test_count_mismatch`.
"""


def _write_remedies(out: Path, force: bool) -> None:
    remedy = out / ".state/remedy"
    for case in CASES:
        markdown = _remedy_markdown(case)
        spec_path = remedy / f"{case.legacy_id}.md"
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": case.legacy_id,
            "replacement_task_id": case.task_id,
            "family_id_before": "maze-to-graph-v1",
            "family_id_after": f"maze-to-graph-v2/{case.task_id}",
            "tree_hash_before": _tree_hash(LEGACY_OUT / case.legacy_id),
            "generator_path": "src/w8_biayn/integrations/moonlight_maze_to_graph_aider_tasks.py",
            "generator_revision": _generator_revision(),
            "finding_ids": [
            "MTG-F1",
            "MTG-F2",
            "MTG-F3",
            "MTG-F4",
            ],
            "disposition": (
                "repair-in-place" if case.task_id == case.legacy_id else "replace"
            ),
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": str(spec_path),
            "remedy_spec_hash": _sha256(markdown.encode()),
            "selected_prompt": PROMPT_PATH,
            "user_inputs": {
                "FAMILY_NAME": "maze-to-graph",
                "FAMILY_TYPE": "aider-text-grid-reshaping",
            },
            "status": "planned",
            "primary_core_objective": "specified",
            "local_status": "pending_execution",
            "dataset_handoff": "not_requested",
        }
        _write(spec_path, markdown, force)
        _write(
            remedy / f"{case.legacy_id}.json",
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            force,
        )


def _invalidate_records_for_revision(out: Path) -> None:
    remedy = out / ".state/remedy"
    if not remedy.is_dir():
        return
    for case in CASES:
        record_path = remedy / f"{case.legacy_id}.json"
        spec_path = remedy / f"{case.legacy_id}.md"
        if not record_path.is_file() or not spec_path.is_file():
            _fail("remedy_spec_incomplete", case.legacy_id)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if "oracle_evidence" in record:
            record["invalidated_oracle_evidence"] = record.pop("oracle_evidence")
        record.update(
            {
                "status": "planned",
                "local_status": "pending_execution",
                "remedy_spec_hash": _sha256(spec_path.read_bytes()),
                "evidence_invalidation": (
                    "owner/case/generated-tree revision changed; all pair-by-dimension "
                    "hard-rule decisions, coherent-control execution, strict negatives, "
                    "and independently mounted digests must be regenerated"
                ),
            }
        )
        _write(
            record_path,
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            True,
        )


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() == LEGACY_OUT.resolve():
        _fail("legacy_root_immutable", str(out))
    out.mkdir(parents=True, exist_ok=True)
    if not (out / ".state/remedy").is_dir():
        _write_remedies(out, force)
    if force:
        _invalidate_records_for_revision(out)
        stale_receipt = out / ".state/docker-sanity.json"
        if stale_receipt.is_file():
            stale_receipt.unlink()
    expected = {case.task_id for case in CASES}
    if force:
        for child in out.iterdir():
            if child.is_dir() and child.name != ".state" and child.name not in expected:
                shutil.rmtree(child)
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        for relative, content in _files(case).items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


_CPP_PRESERVED = {
    "alignof", "and", "auto", "bool", "break", "case", "catch", "char",
    "class", "const", "continue", "default", "do", "double", "else",
    "false", "float", "for", "if", "int", "long", "namespace", "new",
    "noexcept", "not", "nullptr", "or", "private", "public", "return",
    "short", "sizeof", "static", "struct", "switch", "throw", "true",
    "try", "using", "void", "while", "vector", "string", "size_t", "map",
    "set", "pair", "min", "max", "count", "find", "sort", "stable_sort",
    "binary_search", "append", "assign", "insert", "push_back", "substr",
}
_ENDPOINT_WORDS = {"front", "back", "left", "right", "top", "bottom", "first", "last"}
_DOC_STOP = {
    "the", "and", "with", "from", "into", "using", "task", "complete",
    "public", "contract", "implement", "namespace", "declarations", "must",
    "invalid", "valid", "input", "output", "result", "returns", "return",
    "documented", "behavior", "operation", "pure", "before", "after",
    "this", "that", "these", "those", "each", "another", "particular",
    "deterministic", "ascii", "grid", "grids", "rows", "strings", "files",
}
_DOC_SEMANTIC = {
    "allocation", "anisotropic", "area", "aspect", "atlas", "average",
    "band", "block", "boundary", "bounded", "bucket", "cells", "center",
    "centered", "chebyshev", "columns", "complete", "compositing",
    "coordinates", "corners", "decoding", "diagnostics", "dilation",
    "dimensions", "divisible", "duplicates", "edges", "enlargement",
    "factor", "fit", "fixed", "frame", "gutter", "horizontal", "indices",
    "insertion", "integer", "layer", "length", "letterbox", "majority",
    "adjacency", "articulation", "biconnected", "bridge", "capacity",
    "component", "condensation", "conflict", "corridor", "dag", "degree",
    "directed", "distance", "edges", "flow", "heading", "incidence",
    "junction", "label", "lowlink", "neighbor", "ordering", "ports",
    "reachability", "segment", "shortest", "state", "transition", "visibility",
    "weighted", "wrap",
}


def _shingles(tokens: list[str], width: int) -> set[str]:
    if len(tokens) < width:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[index : index + width]) for index in range(len(tokens) - width + 1)}


def _cpp_shingles(text: str, width: int = 5) -> set[str]:
    text = re.sub(
        r"//.*?$|/\*.*?\*/|\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'",
        " LITERAL ",
        text,
        flags=re.M | re.S,
    )
    text = re.sub(r"\b(?:0x[0-9a-fA-F]+|\d+)\w*\b", " NUMBER ", text)
    raw = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|==|!=|<=|>=|\+\+|--|&&|\|\||->|::|[{}()\[\];,?:.+*/%<>=!-]", text)
    tokens: list[str] = []
    for token in raw:
        lowered = token.lower()
        if re.match(r"[A-Za-z_]", token):
            if lowered in _ENDPOINT_WORDS:
                tokens.append("endpoint")
            elif lowered in _CPP_PRESERVED or lowered in {"literal", "number"}:
                tokens.append(lowered)
            else:
                tokens.append("identifier")
        else:
            tokens.append(token)
    return _shingles(tokens, width)


def _domain_nouns(case: MazeGraphCase) -> set[str]:
    text = " ".join((case.legacy_id, case.task_id, case.title, case.function))
    return {part.lower() for part in re.findall(r"[A-Za-z]{3,}", text)}


def _doc_shingles(text: str, domain_nouns: set[str]) -> set[str]:
    text = re.sub(r"`[^`]*`|\b(?:0x[0-9a-fA-F]+|\d+)\w*\b", " ", text)
    tokens = [
        "endpoint" if word in _ENDPOINT_WORDS else word
        for word in re.findall(r"[a-z]+", text.lower())
        if word in _DOC_SEMANTIC and word not in _DOC_STOP and word not in domain_nouns
    ]
    return _shingles(tokens, 3)


def _artifact_features(root: Path, case: MazeGraphCase | None = None) -> set[str]:
    nouns = _domain_nouns(case) if case else {
        part.lower() for part in re.findall(r"[A-Za-z]{3,}", root.name)
    }
    role_paths = {
        "docs": sorted((root / ".docs").glob("*.md")),
        "api": sorted(root.glob("*.h")),
        "reference": [root / ".meta/example.cpp"] if (root / ".meta/example.cpp").is_file() else [],
        "visible": [root / "task_visible_test.cpp"] if (root / "task_visible_test.cpp").is_file() else [],
        "private": [root / ".meta/task_hidden_test.cpp"] if (root / ".meta/task_hidden_test.cpp").is_file() else [],
    }
    if not role_paths["reference"]:
        role_paths["reference"] = sorted(root.glob("*.cpp"))
    features: set[str] = set()
    for role, paths in role_paths.items():
        text = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in paths)
        shingles = _doc_shingles(text, nouns) if role == "docs" else _cpp_shingles(text)
        features.update(f"{role}:{item}" for item in shingles)
    return features


def _pair_result(
    left: Path,
    right: Path,
    left_case: MazeGraphCase | None = None,
    right_case: MazeGraphCase | None = None,
) -> dict[str, object]:
    score = _overlap(
        _artifact_features(left, left_case),
        _artifact_features(right, right_case),
    )
    return {
        "overlap": round(score, 6),
        "failure": "duplicate_family" if score >= PAIR_THRESHOLD else None,
    }


def _selected_cpp_shingles(text: str, patterns: tuple[str, ...]) -> set[str]:
    selected = "\n".join(
        line
        for line in text.splitlines()
        if any(re.search(pattern, line) for pattern in patterns)
    )
    return _cpp_shingles(selected)


def _hard_rule_features(root: Path, case: MazeGraphCase) -> dict[str, set[str]]:
    header = next(root.glob("*.h")).read_text(encoding="utf-8")
    reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    private = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
    negative = (root / ".meta/negative.cpp").read_text(encoding="utf-8")
    instructions = (root / ".docs/instructions.md").read_text(encoding="utf-8")
    nouns = _domain_nouns(case)
    features = {
        "public_api": _cpp_shingles(header, 12),
        "owned_state_or_algorithm": _cpp_shingles(reference),
        "mutation_selection_rules": _selected_cpp_shingles(
            reference,
            (
                r"=",
                r"\bfor\s*\(",
                r"\bwhile\s*\(",
                r"\bsort\s*\(",
                r"\binsert\s*\(",
                r"\bpush_back\s*\(",
                r"\bassign\s*\(",
                r"\bmove\s*\(",
            ),
        ),
        "invalid_boundary_behavior": _doc_shingles(instructions, nouns)
        | _cpp_shingles(private, 12),
        "reference_control_flow": _selected_cpp_shingles(
            reference,
            (
                r"\bif\s*\(",
                r"\bfor\s*\(",
                r"\bwhile\s*\(",
                r"\breturn\b",
                r"\bsort\s*\(",
                r"\bassign\s*\(",
            ),
        ),
        "deterministic_oracle": _cpp_shingles(visible + "\n" + private, 10),
        "topic_specific_negative_fixture": _cpp_shingles(negative),
    }
    empty = [dimension for dimension in HARD_RULE_DIMENSIONS if not features[dimension]]
    if empty:
        _fail("hard_rule_evidence_incomplete", f"{case.task_id}: {empty}")
    return features


def _feature_fingerprint(features: set[str]) -> str:
    return _sha256("\n".join(sorted(features)).encode())


def _hard_rule_pair_result(
    left: Path,
    right: Path,
    left_case: MazeGraphCase,
    right_case: MazeGraphCase,
) -> dict[str, object]:
    left_features = _hard_rule_features(left, left_case)
    right_features = _hard_rule_features(right, right_case)
    overlaps = {
        dimension: round(
            _overlap(left_features[dimension], right_features[dimension]), 6
        )
        for dimension in HARD_RULE_DIMENSIONS
    }
    failed = [
        dimension
        for dimension in HARD_RULE_DIMENSIONS
        if overlaps[dimension] >= HARD_RULE_THRESHOLDS[dimension]
    ]
    return {
        "dimension_overlaps": overlaps,
        "failed_dimensions": failed,
        "failure": "duplicate_family" if failed else None,
    }


def _adversarial_relative_paths(root: Path) -> tuple[str, ...]:
    return tuple(
        path.relative_to(root).as_posix()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    )


def _apply_replacements(
    clone: Path,
    relative_paths: tuple[str, ...],
    replacements: tuple[tuple[str, str], ...],
) -> list[str]:
    changed: list[str] = []
    for relative in relative_paths:
        path = clone / relative
        before = path.read_text(encoding="utf-8")
        after = before
        for old, new in replacements:
            after = after.replace(old, new)
        if after != before:
            path.write_text(after, encoding="utf-8")
            changed.append(relative)
    return changed


def _make_adversarial_clone(
    root: Path,
    case: MazeGraphCase,
    variant: str,
    parent: Path,
) -> tuple[Path, dict[str, object]]:
    if case.task_id != "trail-signpost-route-graph":
        _fail("adversarial_control_invalid", "controls require trail-signpost-route-graph")
    if variant not in ADVERSARIAL_CONTROLS:
        _fail("adversarial_control_invalid", variant)
    clone = parent / variant
    shutil.copytree(root, clone)
    paths = _adversarial_relative_paths(root)
    if variant == "domain-identifier-renamed":
        replacements = (
            (case.task_id, "waypoint-arrow-route-graph"),
            (case.function, "trace_waypoint_routes"),
            ("SignedRoute", "WaypointRoute"),
            ("TrailGraph", "WaypointGraph"),
            ("Signpost", "Waypoint"),
            ("signpost", "waypoint"),
            ("Trails", "Paths"),
            ("trails", "paths"),
            ("Trail", "Path"),
            ("trail", "path"),
        )
        summary = "coherent API/type/domain rename with unchanged behavior"
    elif variant == "constants-or-policy-only":
        replacements = (
            (
                '{"B","^","A","v","C"}',
                '{"B","^","^","A","v","v","C"}',
            ),
            ("g.routes[0].steps!=2", "g.routes[0].steps!=3"),
            (
                "Private tests exercise these published rules.",
                "Private tests exercise these published rules. The public example uses two-arrow chains and therefore reports three steps.",
            ),
        )
        summary = "coherent example-constant-only change from one arrow to two"
    else:
        replacements = (
            (
                "for(int d=0;d<4&&!found;++d)",
                "for(int d=3;d>=0&&!found;--d)",
            ),
            (
                "g.routes[0].to!='B'",
                "g.routes[0].to!='C'",
            ),
            (
                "Use the task-specific canonical ordering for vertices, edges, and diagnostics.",
                "When several routes leave one sign, inspect south, east, west, then north; choose the first route in that order. Use the task-specific canonical ordering for vertices, edges, and diagnostics.",
            ),
        )
        summary = "coherent north-first to south-first endpoint-selection change"
    changed = _apply_replacements(clone, paths, replacements)
    if variant == "domain-identifier-renamed":
        for suffix in (".h", ".cpp"):
            old_name = f"{case.task_id}{suffix}"
            new_name = "waypoint-arrow-route-graph" + suffix
            (clone / old_name).rename(clone / new_name)
            changed.append(f"{old_name} -> {new_name}")
    minimum = {
        "domain-identifier-renamed": 8,
        "constants-or-policy-only": 2,
        "opposite-end-selection": 3,
    }[variant]
    if len(changed) < minimum:
        _fail("adversarial_control_invalid", f"{variant}: only changed {changed}")
    combined = "\n".join(
        (clone / relative).read_text(encoding="utf-8")
        for relative in _adversarial_relative_paths(clone)
    )
    if variant == "domain-identifier-renamed":
        if case.function in combined or "trace_waypoint_routes" not in combined:
            _fail("adversarial_control_invalid", f"incomplete rename: {changed}")
    elif variant == "constants-or-policy-only":
        if '"^","^"' not in combined or '"v","v"' not in combined or "steps!=3" not in combined:
            _fail("adversarial_control_invalid", f"incomplete constants clone: {changed}")
    elif not all(
        value in combined
        for value in (
            "for(int d=3;d>=0&&!found;--d)",
            "g.routes[0].to!='C'",
            "inspect south, east, west, then north",
        )
    ):
        _fail("adversarial_control_invalid", f"incomplete endpoint clone: {changed}")
    return clone, {
        "mutation": summary,
        "changed_files": sorted(changed),
        "tree_hash": _tree_hash(clone),
    }


def _adversarial_clone_results(
    root: Path, case: MazeGraphCase
) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="maze-to-graph-clones-") as tmp:
        for variant in ADVERSARIAL_CONTROLS:
            clone, mutation = _make_adversarial_clone(root, case, variant, Path(tmp))
            pair = _hard_rule_pair_result(root, clone, case, case)
            results[variant] = {**mutation, **pair}
    return results


def _overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / max(1, len(left | right))


def _role_failure(root: Path, files: dict[str, list[str]]) -> str | None:
    solution = files.get("solution", [])
    tests = files.get("test", [])
    examples = files.get("example", [])
    all_paths = solution + tests + examples
    if len(all_paths) != len(set(all_paths)):
        return "unsafe_path"
    for item in all_paths:
        path = Path(item)
        if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
            return "unsafe_path"
    if any(item.startswith(".meta/") or item.startswith(".docs/") or item == "CMakeLists.txt" for item in solution):
        return "unsafe_path"
    if len(solution) != 2 or len(examples) != 2:
        return "target_reference_mismatch"
    if [Path(item).suffix for item in solution] != [Path(item).suffix for item in examples]:
        return "target_reference_mismatch"
    return None


def _whole_format_failure(case: MazeGraphCase, response: str) -> str | None:
    expected = build_assistant_response(
        load_task(Path(case.task_id)), load_example_files_from_config(Path(case.task_id))
    )
    return None if response == expected else "whole_format_failed"


def _prompt_contract_failure(case: MazeGraphCase, instructions: str) -> str | None:
    lowered = instructions.lower()
    return None if all(term.lower() in lowered for term in case.prompt_terms) else "prompt_contract_incomplete"


def _bound_holdouts(repo_root: Path) -> list[Path]:
    base = repo_root / ".cache/upstreams/aider-polyglot/cpp/exercises"
    roots = sorted(path.parent.parent for path in base.glob("*/*/.meta/config.json"))
    if len(roots) != 26:
        _fail("benchmark_screen_not_completed", f"expected 26 bound C++ holdouts, got {len(roots)}")
    return roots


def _update_records(out: Path, evidence: dict[str, dict[str, object]], status: str) -> None:
    remedy = out / ".state/remedy"
    for case in CASES:
        path = remedy / f"{case.legacy_id}.json"
        if not path.is_file():
            _fail("remedy_spec_incomplete", case.legacy_id)
        record = json.loads(path.read_text(encoding="utf-8"))
        spec_path = Path(record["remedy_spec_path"])
        if not spec_path.is_file() or _sha256(spec_path.read_bytes()) != record["remedy_spec_hash"]:
            _fail("remedy_spec_incomplete", f"stale hash: {case.legacy_id}")
        if status != "verified" and "oracle_evidence" in record:
            record["invalidated_oracle_evidence"] = record.pop("oracle_evidence")
            record["evidence_invalidation"] = (
                "owner/case/generated-tree revision changed; strict executed-negative and "
                "independent mounted-digest evidence must be regenerated"
            )
        record.update(
            {
                "status": status,
                "replacement_task_id": case.task_id,
                "family_id_after": f"maze-to-graph-v2/{case.task_id}",
                "generator_revision_after": _generator_revision(),
                "tree_hash_after": _tree_hash(out / case.task_id),
                "primary_core_objective": "achieved",
                "primary_core_evidence": {
                    "reference_function": case.function,
                    "negative_fixture": case.negative_description,
                    "result": "rejected",
                },
                "prompt_boundary": "pass",
                "family_screen": "pass",
                "benchmark_screen": "pass",
                "local_status": "local_family_verified" if status == "verified" else "pending_execution",
                "semantic_evidence": evidence[case.task_id],
                "changed_owner_paths": [
                    CURRICULUM,
                    FAMILY_SPEC,
                    "docs/AIDER_TASK_MATERIALIZATION_GUIDE.md",
                    "src/w8_biayn/integrations/moonlight_maze_to_graph_aider_tasks.py",
                    "src/w8_biayn/integrations/moonlight_maze_to_graph_cases.py",
                    "tests/test_moonlight_maze_to_graph_aider_tasks.py",
                    "examples/slime/moonlight_cpp_perf/prepare_maze_to_graph_aider_tasks.sh",
                ],
            }
        )
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_core(out: Path, *, repo_root: Path | None = None) -> dict[str, dict[str, object]]:
    repo_root = repo_root or Path.cwd()
    emitted = {
        path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"
    }
    expected = {case.task_id for case in CASES}
    if not FAMILY_ROOT_MIN <= len(emitted) <= FAMILY_ROOT_MAX:
        _fail(
            "generator_output_drift",
            f"hard-rule root count {len(emitted)} outside "
            f"[{FAMILY_ROOT_MIN}, {FAMILY_ROOT_MAX}]",
        )
    if emitted != expected:
        _fail("generator_output_drift", "task inventory")
    evidence: dict[str, dict[str, object]] = {}
    feature_sets: dict[str, set[str]] = {}
    hard_feature_sets: dict[str, dict[str, set[str]]] = {}
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        failure = _role_failure(root, config["files"])
        if failure:
            _fail(failure, case.task_id)
        instructions = (root / ".docs/instructions.md").read_text(encoding="utf-8")
        failure = _prompt_contract_failure(case, instructions)
        if failure:
            _fail(failure, case.task_id)
        task = load_task(root)
        response = build_assistant_response(task, load_example_files_from_config(root))
        if not response.startswith(f"{case.task_id}.h\n```") or ".meta/" in response:
            _fail("whole_format_failed", case.task_id)
        reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
        if case.function not in reference or _format_cpp_body(case.body).strip() not in reference:
            _fail("invariant_not_enforced", case.task_id)
        negative = (root / ".meta/negative.cpp").read_text(encoding="utf-8")
        formatted_new = _format_cpp_body(case.negative_new).strip()
        formatted_old = _format_cpp_body(case.negative_old).strip()
        if formatted_new not in negative or formatted_old in negative:
            _fail("invariant_not_enforced", f"negative fixture: {case.task_id}")
        cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
        negative_target = cmake.split("add_executable(task_negative", 1)[-1]
        if "task_visible_test.cpp" not in negative_target or "target_compile_options(task_negative PRIVATE -Wall -Wextra -Wpedantic -Werror)" not in cmake:
            _fail("negative_fixture_not_strict", case.task_id)
        feature_sets[case.task_id] = _artifact_features(root, case)
        hard_feature_sets[case.task_id] = _hard_rule_features(root, case)
        evidence[case.task_id] = {
            "artifact_roles": ["docs", "public_api", "reference", "visible_tests", "private_tests"],
            "tree_hash": _tree_hash(root),
            "reference_hash": _reference_hash(root),
            "negative_fixture": case.negative_description,
            "prompt_boundary": "pass",
            "hard_rule_dimensions": {
                dimension: {
                    "feature_count": len(hard_feature_sets[case.task_id][dimension]),
                    "fingerprint": _feature_fingerprint(
                        hard_feature_sets[case.task_id][dimension]
                    ),
                }
                for dimension in HARD_RULE_DIMENSIONS
            },
        }
    pairwise = []
    hard_pairwise = []
    for left, right in combinations(CASES, 2):
        score = _overlap(feature_sets[left.task_id], feature_sets[right.task_id])
        pairwise.append({"left": left.task_id, "right": right.task_id, "overlap": round(score, 6)})
        if score >= PAIR_THRESHOLD:
            _fail("duplicate_family", f"{left.task_id} vs {right.task_id}: {score:.3f}")
        hard_result = _hard_rule_pair_result(
            out / left.task_id,
            out / right.task_id,
            left,
            right,
        )
        hard_pairwise.append(
            {"left": left.task_id, "right": right.task_id, **hard_result}
        )
        if hard_result["failure"] is not None:
            _fail(
                "duplicate_family",
                f"{left.task_id} vs {right.task_id}: "
                f"{hard_result['failed_dimensions']}",
            )
    holdouts = _bound_holdouts(repo_root)
    benchmark_results = []
    for case in CASES:
        for holdout in holdouts:
            score = _overlap(feature_sets[case.task_id], _artifact_features(holdout))
            result = {"task_id": case.task_id, "holdout": holdout.name, "overlap": round(score, 6)}
            benchmark_results.append(result)
            if case.task_id == holdout.name or score >= 0.72:
                _fail("benchmark_content_overlap", f"{case.task_id} vs {holdout.name}: {score:.3f}")
    archive_case = next(
        case for case in CASES if case.task_id == "trail-signpost-route-graph"
    )
    adversarial = _adversarial_clone_results(out / archive_case.task_id, archive_case)
    if set(adversarial) != set(ADVERSARIAL_CONTROLS) or any(
        item["failure"] != "duplicate_family"
        or set(item["failed_dimensions"]) != set(HARD_RULE_DIMENSIONS)
        for item in adversarial.values()
    ):
        _fail("duplicate_family", f"adversarial controls: {adversarial}")
    screen = {
        "schema_version": "maze-to-graph-family-screen-v4",
        "normalizer": NORMALIZER,
        "root_count": len(CASES),
        "root_count_bounds": {
            "minimum": FAMILY_ROOT_MIN,
            "maximum": FAMILY_ROOT_MAX,
        },
        "pair_threshold": PAIR_THRESHOLD,
        "pairwise_semantic_overlap": pairwise,
        "benchmark_comparisons": benchmark_results,
        "benchmark_inventory": [root.name for root in holdouts],
        "legacy_finding": "20 roots shared one implementation and one test template",
        "normalization_contract": (
            "comments, strings, literals, identifiers, task/domain nouns, and endpoint direction "
            "are normalized while API punctuation, arity, control flow, operators, standard "
            "algorithm calls, docs semantics, and assertions remain"
        ),
        "adversarial_clone_results": adversarial,
        "hard_rule": {
            "dimensions": list(HARD_RULE_DIMENSIONS),
            "thresholds": HARD_RULE_THRESHOLDS,
            "comparison_count": len(hard_pairwise),
            "expected_comparison_count": len(CASES) * (len(CASES) - 1) // 2,
            "pairwise": hard_pairwise,
            "adversarial_controls": list(ADVERSARIAL_CONTROLS),
            "result": "pass",
        },
        "result": "pass",
    }
    state = out / ".state"
    _write(state / "family-screen.json", json.dumps(screen, indent=2, sort_keys=True) + "\n", True)
    _update_records(out, evidence, "implemented")
    return evidence


def _test_count(build_dir: Path) -> int:
    proc = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "-N"],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"Total Tests:\s*(\d+)", proc.stdout + proc.stderr)
    if not match or int(match.group(1)) == 0:
        _fail("zero_tests", str(build_dir))
    return int(match.group(1))


def verify(out: Path) -> dict[str, dict[str, int]]:
    missing = [tool for tool in ("cmake", "c++") if shutil.which(tool) is None]
    if missing:
        receipt = {
            "schema_version": "maze-to-graph-host-oracle-v2",
            "status": "not_completed",
            "classification": "host_iteration_only",
            "blocked_command": "cmake -S <task> -B <build> -G Unix Makefiles",
            "missing_prerequisites": missing,
            "next_action": "run the owner-controlled network-disabled --docker-sanity verifier",
            "generator_revision": _generator_revision(),
        }
        _write(
            out / ".state/host-oracle.json",
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            True,
        )
        return {}
    results: dict[str, dict[str, int]] = {}
    for case in CASES:
        root = out / case.task_id
        with tempfile.TemporaryDirectory(prefix=f"maze-to-graph-{case.task_id}-") as tmp:
            copied = Path(tmp) / case.task_id
            shutil.copytree(root, copied)
            result: dict[str, int] = {}
            for mode, flags in (
                ("normal", []),
                ("asan_ubsan", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer"]),
            ):
                build_dir = copied / f"build-{mode}"
                subprocess.run(
                    ["cmake", "-S", str(copied), "-B", str(build_dir), "-G", "Unix Makefiles", f"-DTASK_SOURCE={copied / '.meta/example.cpp'}", *flags],
                    check=True,
                )
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True)
                count = _test_count(build_dir)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True)
                result[mode] = count
            if result["normal"] != result["asan_ubsan"]:
                _fail("sanitizer_test_count_mismatch", case.task_id)
            results[case.task_id] = result
    receipt = {
        "schema_version": "maze-to-graph-host-oracle-v2",
        "status": "pass",
        "classification": "host_iteration_only",
        "generator_revision": _generator_revision(),
        "tasks": results,
    }
    _write(out / ".state/host-oracle.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    return results


def _archive(
    out: Path,
    target: Path,
    controls: dict[str, Path] | None = None,
) -> str:
    with tarfile.open(target, "w") as archive:
        for case in CASES:
            root = out / case.task_id
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                info = archive.gettarinfo(str(path), arcname=f"family/{case.task_id}/{path.relative_to(root).as_posix()}")
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                with path.open("rb") as stream:
                    archive.addfile(info, stream)
        for variant, root in sorted((controls or {}).items()):
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                info = archive.gettarinfo(
                    str(path),
                    arcname=f"controls/{variant}/{path.relative_to(root).as_posix()}",
                )
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                with path.open("rb") as stream:
                    archive.addfile(info, stream)
    return _sha256(target.read_bytes())


def _accept_docker_receipt(out: Path, receipt: dict[str, object]) -> dict[str, object]:
    if (
        receipt.get("schema_version") != "maze-to-graph-docker-sanity-v4"
        or receipt.get("status") != "pass"
        or receipt.get("network") != "none"
        or receipt.get("image") != SANITY_IMAGE
        or receipt.get("generator_revision") != _generator_revision()
    ):
        _fail("docker_result_identity_mismatch", "receipt header")
    tasks = receipt.get("tasks")
    if not isinstance(tasks, dict) or set(tasks) != {case.task_id for case in CASES}:
        _fail("docker_sanity_incomplete", "receipt task inventory")
    for case in CASES:
        item = tasks[case.task_id]
        if not isinstance(item, dict):
            _fail("docker_sanity_incomplete", case.task_id)
        live_hash = _tree_hash(out / case.task_id)
        if item.get("tree_hash") != live_hash or item.get("mounted_tree_hash") != live_hash:
            _fail("grader_mount_hash_mismatch", case.task_id)
        if item.get("reference_hash") != _reference_hash(out / case.task_id):
            _fail("docker_result_identity_mismatch", f"reference: {case.task_id}")
        if item.get("normal") != 3 or item.get("asan_ubsan") != 3:
            _fail("sanitizer_test_count_mismatch", case.task_id)
        if item.get("negative_normal") != "semantic_rejection exit_1" or item.get(
            "negative_asan_ubsan"
        ) != "semantic_rejection exit_1":
            _fail("negative_fixture_not_rejected", case.task_id)
    controls = receipt.get("hard_rule_controls")
    if not isinstance(controls, dict) or set(controls) != set(ADVERSARIAL_CONTROLS):
        _fail("docker_sanity_incomplete", "hard-rule control inventory")
    archive_case = next(
        case for case in CASES if case.task_id == "trail-signpost-route-graph"
    )
    with tempfile.TemporaryDirectory(prefix="maze-to-graph-receipt-controls-") as tmp:
        for variant in ADVERSARIAL_CONTROLS:
            clone, _ = _make_adversarial_clone(
                out / archive_case.task_id,
                archive_case,
                variant,
                Path(tmp),
            )
            item = controls[variant]
            if not isinstance(item, dict):
                _fail("docker_sanity_incomplete", variant)
            if item.get("normal") != 3 or item.get("asan_ubsan") != 3:
                _fail("sanitizer_test_count_mismatch", f"control: {variant}")
            live_hash = _tree_hash(clone)
            if item.get("tree_hash") != live_hash or item.get(
                "mounted_tree_hash"
            ) != live_hash:
                _fail("grader_mount_hash_mismatch", f"control: {variant}")
    serialized = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    _write(out / ".state/docker-sanity.json", serialized, True)
    evidence = verify_core(out)
    _update_records(out, evidence, "verified")
    for case in CASES:
        record_path = out / ".state/remedy" / f"{case.legacy_id}.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["oracle_evidence"] = {
            "receipt": ".state/docker-sanity.json",
            "receipt_hash": _sha256(serialized.encode()),
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "normal_tests": 3,
            "asan_ubsan_tests": 3,
            "negative_normal": "semantic_rejection exit_1",
            "negative_asan_ubsan": "semantic_rejection exit_1",
            "mounted_tree_hash": tasks[case.task_id]["mounted_tree_hash"],
            "hard_rule_controls": list(ADVERSARIAL_CONTROLS),
        }
        record_path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return receipt


def import_docker_sanity(out: Path, result_path: Path) -> dict[str, object]:
    verify_core(out)
    receipt = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        _fail("docker_result_identity_mismatch", "result is not an object")
    return _accept_docker_receipt(out, receipt)


def docker_sanity(out: Path, *, result_out: Path | None = None) -> dict[str, object]:
    verify_core(out)
    with tempfile.TemporaryDirectory(prefix="maze-to-graph-docker-") as tmp:
        archive = Path(tmp) / "family.tar"
        archive_case = next(
            case for case in CASES if case.task_id == "trail-signpost-route-graph"
        )
        control_parent = Path(tmp) / "controls"
        controls = {
            variant: _make_adversarial_clone(
                out / archive_case.task_id,
                archive_case,
                variant,
                control_parent,
            )[0]
            for variant in ADVERSARIAL_CONTROLS
        }
        control_tree_hashes = {
            variant: _tree_hash(root) for variant, root in controls.items()
        }
        archive_hash = _archive(out, archive, controls)
        image_id = subprocess.run(
            ["docker", "image", "inspect", SANITY_IMAGE, "--format", "{{.Id}}"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        script = r'''set -eu
mkdir -p /tmp/family
tar -xf /input/family.tar -C /tmp/family
compiler=$(command -v c++)
echo "W8TOOL compiler_path $compiler"
echo "W8TOOL compiler_hash sha256:$(sha256sum "$compiler" | sed 's/ .*//')"
echo "W8TOOL compiler_version $(c++ --version | head -1)"
echo "W8TOOL cmake_version $(cmake --version | head -1)"
for root in /tmp/family/family/*; do
  task=${root##*/}
  mounted_hash=$(python3 -c 'import hashlib,pathlib,sys
r=pathlib.Path(sys.argv[1]); d=hashlib.sha256()
for p in sorted(x for x in r.rglob("*") if x.is_file()):
 q=p.relative_to(r).as_posix().encode(); b=p.read_bytes(); d.update(len(q).to_bytes(8,"big")); d.update(q); d.update(len(b).to_bytes(8,"big")); d.update(b)
print("sha256:"+d.hexdigest())' "$root")
  echo "W8HASH $task $mounted_hash"
  for mode in normal asan_ubsan; do
    flags=
    if [ "$mode" = asan_ubsan ]; then flags='-fsanitize=address,undefined -fno-omit-frame-pointer'; fi
    cmake -S "$root" -B "/tmp/build-$task-$mode" -G 'Unix Makefiles' -DTASK_SOURCE="$root/.meta/example.cpp" -DCMAKE_CXX_FLAGS="$flags" >/dev/null
    cmake --build "/tmp/build-$task-$mode" --parallel 2 >/dev/null
    count=$(ctest --test-dir "/tmp/build-$task-$mode" -N | sed -n 's/.*Total Tests: *//p')
    test "$count" = 3
    ctest --test-dir "/tmp/build-$task-$mode" --output-on-failure
    set +e
    negative_output=$("/tmp/build-$task-$mode/task_negative" 2>&1)
    negative_status=$?
    set -e
    test "$negative_status" = 1
    test -z "$negative_output"
    echo "W8NEG $task $mode semantic_rejection exit_1"
    echo "W8COUNT $task $mode $count"
  done
done
for root in /tmp/family/controls/*; do
  control=${root##*/}
  mounted_hash=$(python3 -c 'import hashlib,pathlib,sys
r=pathlib.Path(sys.argv[1]); d=hashlib.sha256()
for p in sorted(x for x in r.rglob("*") if x.is_file()):
 q=p.relative_to(r).as_posix().encode(); b=p.read_bytes(); d.update(len(q).to_bytes(8,"big")); d.update(q); d.update(len(b).to_bytes(8,"big")); d.update(b)
print("sha256:"+d.hexdigest())' "$root")
  echo "W8CONTROLHASH $control $mounted_hash"
  for mode in normal asan_ubsan; do
    flags=
    if [ "$mode" = asan_ubsan ]; then flags='-fsanitize=address,undefined -fno-omit-frame-pointer'; fi
    cmake -S "$root" -B "/tmp/build-control-$control-$mode" -G 'Unix Makefiles' -DTASK_SOURCE="$root/.meta/example.cpp" -DCMAKE_CXX_FLAGS="$flags" >/dev/null
    cmake --build "/tmp/build-control-$control-$mode" --parallel 2 >/dev/null
    count=$(ctest --test-dir "/tmp/build-control-$control-$mode" -N | sed -n 's/.*Total Tests: *//p')
    test "$count" = 3
    ctest --test-dir "/tmp/build-control-$control-$mode" --output-on-failure
    echo "W8CONTROLCOUNT $control $mode $count"
  done
done'''
        proc = subprocess.run(
            ["docker", "run", "--rm", "--network", "none", "-v", f"{archive}:/input/family.tar:ro", SANITY_IMAGE, "bash", "-lc", script],
            check=False, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            diagnostic = (proc.stdout + "\n" + proc.stderr)[-12000:]
            _fail("docker_sanity_failed", diagnostic)
    counts: dict[str, dict[str, int]] = {}
    for task_id, mode, count in re.findall(r"^W8COUNT (\S+) (\S+) (\d+)$", proc.stdout, re.M):
        counts.setdefault(task_id, {})[mode] = int(count)
    mounted_hashes = dict(re.findall(r"^W8HASH (\S+) (sha256:[0-9a-f]{64})$", proc.stdout, re.M))
    negative_results = {
        (task_id, mode): outcome
        for task_id, mode, outcome in re.findall(
            r"^W8NEG (\S+) (\S+) (semantic_rejection exit_1)$", proc.stdout, re.M
        )
    }
    control_counts: dict[str, dict[str, int]] = {}
    for control, mode, count in re.findall(
        r"^W8CONTROLCOUNT (\S+) (\S+) (\d+)$", proc.stdout, re.M
    ):
        control_counts.setdefault(control, {})[mode] = int(count)
    control_mounted_hashes = dict(
        re.findall(
            r"^W8CONTROLHASH (\S+) (sha256:[0-9a-f]{64})$",
            proc.stdout,
            re.M,
        )
    )
    if set(counts) != {case.task_id for case in CASES}:
        _fail("docker_sanity_incomplete", "task inventory")
    for case in CASES:
        if counts[case.task_id] != {"normal": 3, "asan_ubsan": 3}:
            _fail("sanitizer_test_count_mismatch", case.task_id)
        live_hash = _tree_hash(out / case.task_id)
        if mounted_hashes.get(case.task_id) != live_hash:
            _fail(
                "grader_mount_hash_mismatch",
                f"{case.task_id}: owner={live_hash} docker={mounted_hashes.get(case.task_id)}",
            )
        if any(
            negative_results.get((case.task_id, mode)) != "semantic_rejection exit_1"
            for mode in ("normal", "asan_ubsan")
        ):
            _fail("negative_fixture_not_rejected", case.task_id)
    if set(control_counts) != set(ADVERSARIAL_CONTROLS):
        _fail("docker_sanity_incomplete", "hard-rule control inventory")
    for variant in ADVERSARIAL_CONTROLS:
        if control_counts[variant] != {"normal": 3, "asan_ubsan": 3}:
            _fail("sanitizer_test_count_mismatch", f"control: {variant}")
        if control_mounted_hashes.get(variant) != control_tree_hashes[variant]:
            _fail(
                "grader_mount_hash_mismatch",
                f"control: {variant}: owner={control_tree_hashes[variant]} "
                f"docker={control_mounted_hashes.get(variant)}",
            )
    toolchain = dict(re.findall(r"^W8TOOL (\S+) (.+)$", proc.stdout, re.M))
    receipt: dict[str, object] = {
        "schema_version": "maze-to-graph-docker-sanity-v4",
        "status": "pass",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "network": "none",
        "image": SANITY_IMAGE,
        "image_id": image_id,
        "archive_hash": archive_hash,
        "generator_revision": _generator_revision(),
        "toolchain": toolchain,
        "commands": [
            "cmake normal with strict target flags", "ctest normal",
            "execute normal negative target and require exit 1 with empty diagnostics",
            "fresh cmake ASan/UBSan with strict target flags", "ctest ASan/UBSan",
            "execute ASan/UBSan negative target and require exit 1 with empty diagnostics",
            "compile and execute all three coherent hard-rule controls in clean normal and fresh ASan/UBSan builds",
        ],
        "tasks": {
            case.task_id: {
                **counts[case.task_id],
                "tree_hash": _tree_hash(out / case.task_id),
                "mounted_tree_hash": mounted_hashes[case.task_id],
                "reference_hash": _reference_hash(out / case.task_id),
                "negative_fixture": case.negative_description,
                "negative_normal": negative_results[(case.task_id, "normal")],
                "negative_asan_ubsan": negative_results[(case.task_id, "asan_ubsan")],
            }
            for case in CASES
        },
        "hard_rule_controls": {
            variant: {
                **control_counts[variant],
                "tree_hash": control_tree_hashes[variant],
                "mounted_tree_hash": control_mounted_hashes[variant],
                "classification": "coherent clone rejected by seven-dimensional screen",
            }
            for variant in ADVERSARIAL_CONTROLS
        },
    }
    if result_out is not None:
        _write(
            result_out,
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            True,
        )
    return _accept_docker_receipt(out, receipt)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--docker-result-out", type=Path)
    parser.add_argument("--import-docker-result", type=Path)
    args = parser.parse_args()
    build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    if args.docker_sanity:
        docker_sanity(args.out, result_out=args.docker_result_out)
    if args.import_docker_result:
        import_docker_sanity(args.out, args.import_docker_result)


if __name__ == "__main__":
    main()
