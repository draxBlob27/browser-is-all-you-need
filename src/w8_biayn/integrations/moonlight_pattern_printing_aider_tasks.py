from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
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
from w8_biayn.integrations.moonlight_pattern_printing_cases import (
    CASES,
    Case,
)

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/"
    "aider-text-grid-reshaping/pattern-printing"
)
LEGACY_OUT = Path(
    ".w8-biayn/data/aider-tasks/"
    "aider-text-grid-reshaping/pattern-printing"
)
CURRICULUM = (
    "docs/aider-synthetic/aider-synthetic-text-grid-reshaping/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_PATTERN_PRINTING_CURRICULUM.md"
)
AUDIT_SPEC = "docs/aider-tasks-spec/aider-text-grid-reshaping/pattern-printing.md"
PROMPT_PATH = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
NORMALIZER = "pattern-printing-hard-rule-v4-artifact-dimension-shingles"
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
        Path(__file__).with_name("moonlight_pattern_printing_cases.py"),
    ):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def _header(case: Case) -> str:
    return (
        "#pragma once\n"
        "#include <cstddef>\n#include <string>\n#include <vector>\n"
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


def _source(case: Case) -> str:
    return (
        f'#include "{case.task_id}.h"\n'
        "#include <algorithm>\n#include <limits>\n#include <map>\n"
        "#include <numeric>\n#include <set>\n#include <stdexcept>\n#include <utility>\n"
        "namespace curriculum {\n"
        f"{case.return_type} {case.function}({case.params}) {{\n{_format_cpp_body(case.body)}\n}}\n"
        "}\n"
    )


def _negative(case: Case) -> str:
    if case.body.count(case.negative_old) != 1:
        _fail("negative_fixture_drift", case.task_id)
    body = case.body.replace(case.negative_old, case.negative_new)
    return (
        f'#include "../{case.task_id}.h"\n'
        "#include <algorithm>\n#include <limits>\n#include <map>\n"
        "#include <numeric>\n#include <set>\n#include <stdexcept>\n#include <utility>\n"
        "namespace curriculum {\n"
        f"{case.return_type} {case.function}({case.params}) {{\n"
        f"{_format_cpp_body(body)}\n}}\n"
        "}\n"
    )


def _test(case: Case, body: str) -> str:
    return (
        f'#include "{case.task_id}.h"\n#include <string>\n#include <vector>\n'
        "using namespace curriculum;\nint main() {\n"
        f"{_format_cpp_body(body)}\n"
        "}\n"
    )


def _cmake(case: Case) -> str:
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


def _instructions(case: Case) -> str:
    terms = ", ".join(f"`{term}`" for term in case.prompt_terms)
    return f"""# {case.title}

Implement `{case.function}` in namespace `curriculum` using the declarations in
`{case.task_id}.h`. The task is {case.objective}. The exact declarations,
parameter meanings, result fields, and validation bounds in the editable header
are part of the public contract.

The operation is pure and must not mutate inputs. Any condition explicitly
described as invalid returns the default report with `valid == false` and empty
result and diagnostic containers. Do not silently clamp, reorder, or repair an
invalid input.

The complete ordering and tie rules are part of the public contract. In
particular the implementation must preserve these capability terms: {terms}.
Use deterministic row-major order for coordinate diagnostics unless the
task-specific declaration names another order. Output strings are byte-oriented
pattern renderings; no Unicode display-width interpretation is performed.
"""


def _files(case: Case) -> dict[str, str]:
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
        "audit_specification": AUDIT_SPEC,
        "curriculum_task_id": case.task_id,
        "legacy_task_id": case.legacy_id,
        "origin": "newly-authored clean-room repository remediation",
        "prompt_path": PROMPT_PATH,
        "status": "local candidate artifact; not admitted SFT data",
        "version": 4,
        "family_id": "pattern-printing-v4",
        "semantic_profile": list(case.profile),
        "benchmark_separation": (
            "Artifact-derived screen against all bound official Aider C++ holdouts."
        ),
    }
    files = {
        ".docs/introduction.md": (
            f"# {case.title}\n\nA local clean-room pattern-rendering transformation task.\n"
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
                    "prior receipt lacked strict executed-negative and independent "
                    "Docker-mounted digest evidence"
                ),
            }
        )
        finding_ids = set(record.get("finding_ids", []))
        finding_ids.update({"PATTERN-PRINT-004", "PATTERN-PRINT-005", "PATTERN-PRINT-006"})
        record["finding_ids"] = sorted(finding_ids)
        _write(
            record_path,
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            True,
        )


_REMEDY_HEADINGS = (
    "Identity", "Objective", "Public API", "Behavior table",
    "Implementation invariant", "Starter and reference", "Tests",
    "Files and metadata", "Build/oracle", "Family/contamination",
    "Optional dataset handoff", "Acceptance",
)


def _remedy_markdown(case: Case) -> str:
    terms = ", ".join(case.prompt_terms)
    profile = ", ".join(case.profile)
    return f"""## Identity
Legacy `{case.legacy_id}`; task-spec revision 4; family `pattern-printing-v4`; disposition `{case.disposition}`; remediated root `{case.task_id}`; source inventory `pattern-printing-clean-room-v4`; repository-authored license `pass`; generator `src/w8_biayn/integrations/moonlight_pattern_printing_aider_tasks.py`; benchmark screen `pending` until the bound 26-root semantic screen runs. Selected prompt `{PROMPT_PATH}` with `FAMILY_NAME=pattern-printing` and `FAMILY_TYPE=aider-text-grid-reshaping`.

## Objective
Implement one observable capability: {case.objective}. The result fields and the topic-specific negative fixture make that mechanism testable without claiming an unobservable representation.

## Public API
Editable order is `{case.task_id}.h`, `{case.task_id}.cpp`. Exact C++17 declarations:

```cpp
{_header(case).rstrip()}
```

## Behavior table
The parameters are `{case.params}`. Valid input produces `{case.return_type}` with `valid == true` and deterministic output/order. The contract terms are {terms}. Invalid, empty, out-of-range, duplicate, or absent conditions explicitly exercised by the private boundary oracle return the default report with `valid == false`; valid empty sub-results remain valid only when the declared mechanism permits them. Input order is stable unless the API names a geometric or numeric order. Ties use source/row-major order. Counts use `std::size_t` and must reject bounds before unsafe arithmetic. The public principal example is the focused visible case for `{case.function}`.

## Implementation invariant
Required semantic profile: {profile}. The reference must execute that mechanism directly. Forbidden substitutes are the legacy centered-span/stripe renderer, a precomputed answer, hard-coded examples, a renamed copy of another root, or a constants/opposite-end-only variant. The private invariant is that the independent expected rendering and every diagnostic field agree for the boundary and adversarial cases.

## Starter and reference
The task-named header is complete and the task-named source is an API-complete compiling stub. `.meta/example.cpp` is a separately emitted clean-room reference implementing `{case.function}`. It does not import legacy rendering code, benchmark assets, hidden fixtures, or a generic policy switch.

## Tests
The visible test names the principal rendering and diagnostic. The private test covers invalid/empty/boundary behavior and a second mechanism-specific oracle. The deterministic false substitute is `{case.negative_description}`; it compiles under the same strict flags and must execute to exit 1. Family controls additionally reject a domain/identifier rename, constants-or-policy-only clone, and opposite-end-selection clone.

## Files and metadata
Prompt-visible roles are `.docs/*.md` plus `{case.task_id}.h` and `{case.task_id}.cpp`; only the latter pair is editable in that order. Private roles are `.meta/example.h`, `.meta/example.cpp`, `.meta/task_hidden_test.cpp`, `.meta/negative.cpp`, provenance, tests metadata, CMake, receipts, and remedy records. The two example files map one-to-one by suffix and order. Support digest is `none` because the family has no shared bundled support file.

## Build/oracle
Use `{SANITY_IMAGE}`, Docker network `none`, C++17, explicit `Unix Makefiles`, strict `-Wall -Wextra -Wpedantic -Werror`, clean normal and fresh ASan/UBSan builds, three positive equal CTest discoveries, and executed negative rejection in both modes. Bind tree, mounted-tree, owner, case inventory, reference, archive, image, compiler, CMake, commands, counts, and outcomes.

## Family/contamination
Use `{NORMALIZER}` over all 190 unordered emitted-family pairs and all 520 comparisons against the bound 26 official C++ holdouts. In every family pair, separately compare the actual emitted public API, owned state/algorithm, mutation/selection rules, invalid/boundary behavior, reference control flow, deterministic oracle, and topic-specific negative fixture. Require each dimension below its fail-closed threshold; unique IDs, profiles, declared signatures, and raw hashes are not evidence. Keep the wrong substitute isolated to its own dimension, reject all three coherent adversarial controls, and require the whole-slug/content holdout screen to pass. The official `diamond` root remains a permanent holdout.

## Optional dataset handoff
`not_requested`; no JSONL, token/mask, split, export, producer, consumer, training, or uplift evidence is created.

## Acceptance
Run focused pytest, `--verify-core`, host iteration when available, and owner-controlled `--docker-sanity`. Require exactly 20 roots, 20 remedy records, all seven artifact-derived dimensions in each of 190 family comparisons, 520 holdout comparisons, coherent rejection of the three required clone classes, strict prompt/role/reference mapping, three equal positive normal/sanitizer tests per root, and negative exit 1 in both modes. Stable failure codes include `remedy_spec_incomplete`, `hard_rule_root_count`, `hard_rule_evidence_incomplete`, `generator_output_drift`, `prompt_contract_incomplete`, `target_reference_mismatch`, `invariant_not_enforced`, `duplicate_family`, `benchmark_content_overlap`, `zero_tests`, `sanitizer_test_count_mismatch`, and `negative_fixture_not_rejected`.
"""


def plan_remedies(out: Path = DEFAULT_OUT, *, force: bool = False) -> None:
    if out.resolve() == LEGACY_OUT.resolve():
        _fail("legacy_root_immutable", str(out))
    remedy = out / ".state/remedy"
    remedy.mkdir(parents=True, exist_ok=True)
    for case in CASES:
        legacy = LEGACY_OUT / case.legacy_id
        if not legacy.is_dir():
            _fail("legacy_root_missing", case.legacy_id)
        spec_path = remedy / f"{case.legacy_id}.md"
        record_path = remedy / f"{case.legacy_id}.json"
        markdown = _remedy_markdown(case)
        _write(spec_path, markdown, force)
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": case.legacy_id,
            "replacement_task_id": case.task_id,
            "family_id_before": f"pattern-printing-v1/{case.legacy_id}",
            "tree_hash_before": _tree_hash(legacy),
            "generator_path": "src/w8_biayn/integrations/moonlight_pattern_printing_aider_tasks.py",
            "generator_revision": _sha256((legacy / ".meta/provenance.json").read_bytes()),
            "finding_ids": ["PATTERN-PRINT-001", "PATTERN-PRINT-002", "PATTERN-PRINT-003", "PATTERN-PRINT-004"],
            "disposition": case.disposition,
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": spec_path.as_posix(),
            "remedy_spec_hash": _sha256(markdown.encode()),
            "status": "planned",
            "local_status": "pending_execution",
        }
        _write(record_path, json.dumps(record, indent=2, sort_keys=True) + "\n", force)


def _verify_remedy_specs(out: Path) -> None:
    remedy = out / ".state/remedy"
    expected = {case.legacy_id for case in CASES}
    if {path.stem for path in remedy.glob("*.json")} != expected:
        _fail("remedy_spec_incomplete", "one record per legacy root required")
    for case in CASES:
        record = json.loads((remedy / f"{case.legacy_id}.json").read_text(encoding="utf-8"))
        spec_path = Path(record.get("remedy_spec_path", ""))
        if not spec_path.is_file() or record.get("remedy_spec_hash") != _sha256(spec_path.read_bytes()):
            _fail("remedy_spec_incomplete", case.legacy_id)
        text = spec_path.read_text(encoding="utf-8")
        positions = [text.find(f"## {heading}") for heading in _REMEDY_HEADINGS]
        if -1 in positions or positions != sorted(positions) or record.get("disposition") != case.disposition:
            _fail("remedy_disposition_conflict", case.legacy_id)


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() == LEGACY_OUT.resolve():
        _fail("legacy_root_immutable", str(out))
    out.mkdir(parents=True, exist_ok=True)
    if not (out / ".state/remedy").is_dir():
        plan_remedies(out)
    _verify_remedy_specs(out)
    if force:
        _invalidate_records_for_revision(out)
        stale_receipt = out / ".state/docker-sanity.json"
        if stale_receipt.is_file():
            stale_receipt.unlink()
    expected = {case.task_id for case in CASES}
    if force:
        for child in out.iterdir():
            if child.is_dir() and child.name != ".state" and child.name not in expected:
                provenance_path = child / ".meta/provenance.json"
                provenance = json.loads(provenance_path.read_text(encoding="utf-8")) if provenance_path.is_file() else {}
                if provenance.get("family_id") not in {
                    "pattern-printing-v3",
                    "pattern-printing-v4",
                }:
                    _fail("foreign_generated_root", str(child))
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
    "manhattan", "margin", "matrix", "nearest", "neighbor", "ordering",
    "orthogonal", "overflow", "padding", "palette", "phase", "polyline",
    "preserve", "proportional", "radius", "rasterization", "remainder",
    "repeat", "resampling", "rows", "scaling", "selection", "square",
    "stride", "strict", "symbols", "symmetric", "target", "tie", "ties",
    "tile", "token", "transparent", "validation", "vertical", "viewport",
    "whitespace", "width", "without", "zoom",
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


def _domain_nouns(case: Case) -> set[str]:
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


def _artifact_features(root: Path, case: Case | None = None) -> set[str]:
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
    left_case: Case | None = None,
    right_case: Case | None = None,
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


def _hard_rule_features(root: Path, case: Case) -> dict[str, set[str]]:
    """Derive each hard-rule dimension only from emitted task artifacts."""
    header = next(root.glob("*.h")).read_text(encoding="utf-8")
    reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    private = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
    negative = (root / ".meta/negative.cpp").read_text(encoding="utf-8")
    instructions = (root / ".docs/instructions.md").read_text(encoding="utf-8")
    nouns = _domain_nouns(case)
    features = {
        "public_api": _cpp_shingles(header, 8),
        "owned_state_or_algorithm": _cpp_shingles(header + "\n" + reference),
        "mutation_selection_rules": _selected_cpp_shingles(
            reference,
            (
                r"=",
                r"\bfor\s*\(",
                r"\bwhile\s*\(",
                r"\bsort\s*\(",
                r"\binsert\s*\(",
                r"\bpush_back\s*\(",
                r"\bappend\s*\(",
                r"\bassign\s*\(",
            ),
        ),
        "invalid_boundary_behavior": _doc_shingles(instructions, nouns)
        | _cpp_shingles(private, 8),
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
        "deterministic_oracle": _cpp_shingles(visible + "\n" + private),
        # Keep the wrong substitute separate so it cannot lower any primary
        # dimension's score and manufacture apparent family diversity.
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
    left_case: Case,
    right_case: Case,
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
    return (
        ".docs/introduction.md",
        ".docs/instructions.md",
        next(root.glob("*.h")).name,
        next(root.glob("*.cpp")).name,
        ".meta/example.h",
        ".meta/example.cpp",
        ".meta/negative.cpp",
        "task_visible_test.cpp",
        ".meta/task_hidden_test.cpp",
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
    case: Case,
    variant: str,
    parent: Path,
) -> tuple[Path, dict[str, object]]:
    if case.task_id != "pattern-archway-stones":
        _fail("adversarial_control_invalid", "controls require pattern-archway-stones")
    if variant not in ADVERSARIAL_CONTROLS:
        _fail("adversarial_control_invalid", variant)
    clone = parent / variant
    shutil.copytree(root, clone)
    paths = _adversarial_relative_paths(root)
    if variant == "domain-identifier-renamed":
        replacements = (
            ("ArchReport", "PortalReport"),
            ("raster_archway", "raster_archive_portal"),
            ("Archway", "Archive portal"),
            ("archway", "archive portal"),
            ("voussoir", "record"),
            ("stone", "stamp"),
            ("keystone", "apex record"),
        )
        summary = "coherent API/type/domain rename with unchanged behavior"
        minimum = 7
    elif variant == "constants-or-policy-only":
        replacements = (
            ("radius > 30", "radius > 40"),
            ("raster_archway(31", "raster_archway(41"),
        )
        summary = "coherent maximum-radius policy change from thirty to forty"
        minimum = 3
    else:
        replacements = (
            (
                'std::vector<std::string>{"  #  ", " ### ", "## ##"}',
                'std::vector<std::string>{"#####", "## ##", "## ##"}',
            ),
            ("z.stones == 8", "z.stones == 13"),
            ("outer radius", "inner radius"),
            ("outer-radius", "inner-radius"),
            ("d <= outer", "d >= inner"),
            ("d < outer", "d > inner"),
        )
        summary = "coherent outer-to-inner boundary selection change"
        minimum = 4
    changed = _apply_replacements(clone, paths, replacements)
    if len(changed) < minimum:
        _fail("adversarial_control_invalid", f"{variant}: only changed {changed}")
    combined = "\n".join(
        (clone / relative).read_text(encoding="utf-8")
        for relative in _adversarial_relative_paths(clone)
    )
    if variant == "domain-identifier-renamed":
        if case.function in combined or "raster_archive_portal" not in combined:
            _fail("adversarial_control_invalid", f"incomplete rename: {changed}")
    elif variant == "constants-or-policy-only":
        if "radius > 40" not in combined or "raster_archway(41" not in combined:
            _fail("adversarial_control_invalid", f"incomplete policy clone: {changed}")
    elif "d >= inner" not in combined or "inner radius" not in combined:
        _fail("adversarial_control_invalid", f"incomplete endpoint clone: {changed}")
    return clone, {
        "mutation": summary,
        "changed_files": sorted(changed),
        "tree_hash": _tree_hash(clone),
    }


def _adversarial_clone_results(root: Path, case: Case) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="pattern-print-clones-") as tmp:
        for variant in ADVERSARIAL_CONTROLS:
            clone, mutation = _make_adversarial_clone(
                root, case, variant, Path(tmp)
            )
            results[variant] = {
                **mutation,
                **_hard_rule_pair_result(root, clone, case, case),
            }
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


def _whole_format_failure(case: Case, response: str) -> str | None:
    expected = build_assistant_response(
        load_task(Path(case.task_id)), load_example_files_from_config(Path(case.task_id))
    )
    return None if response == expected else "whole_format_failed"


def _prompt_contract_failure(case: Case, instructions: str) -> str | None:
    lowered = instructions.lower()
    has_terms = all(term.lower() in lowered for term in case.prompt_terms)
    has_contract = case.function in instructions and case.objective in instructions
    return None if has_terms and has_contract else "prompt_contract_incomplete"


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
                "family_id_after": f"pattern-printing-v4/{case.task_id}",
                "generator_revision_after": _generator_revision(),
                "tree_hash_after": _tree_hash(out / case.task_id),
                "changed_owner_paths": [
                    "src/w8_biayn/integrations/moonlight_pattern_printing_aider_tasks.py",
                    "src/w8_biayn/integrations/moonlight_pattern_printing_cases.py",
                    "tests/test_moonlight_pattern_printing_aider_tasks.py",
                    "examples/slime/moonlight_cpp_perf/prepare_pattern_printing_aider_tasks.sh",
                    CURRICULUM,
                    AUDIT_SPEC,
                    "docs/AIDER_TASK_MATERIALIZATION_GUIDE.md",
                ],
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
            }
        )
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_core(out: Path, *, repo_root: Path | None = None) -> dict[str, dict[str, object]]:
    repo_root = repo_root or Path.cwd()
    _verify_remedy_specs(out)
    emitted = {
        path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"
    }
    if not FAMILY_ROOT_MIN <= len(emitted) <= FAMILY_ROOT_MAX:
        _fail(
            "hard_rule_root_count",
            f"{len(emitted)} outside {FAMILY_ROOT_MIN}..{FAMILY_ROOT_MAX}",
        )
    if emitted != {case.task_id for case in CASES}:
        _fail("generator_output_drift", "task inventory")
    with tempfile.TemporaryDirectory(prefix="pattern-print-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for case in CASES:
            if _tree_hash(fresh / case.task_id) != _tree_hash(out / case.task_id):
                _fail("generator_output_drift", case.task_id)
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
                    "feature_count": len(
                        hard_feature_sets[case.task_id][dimension]
                    ),
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
    archive_case = next(case for case in CASES if case.task_id == "pattern-archway-stones")
    adversarial = _adversarial_clone_results(out / archive_case.task_id, archive_case)
    if set(adversarial) != set(ADVERSARIAL_CONTROLS) or any(
        item["failure"] != "duplicate_family" or not item["failed_dimensions"]
        for item in adversarial.values()
    ):
        _fail("duplicate_family", f"adversarial controls: {adversarial}")
    screen = {
        "schema_version": "pattern-printing-family-screen-v4",
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
            "schema_version": "pattern-printing-host-oracle-v2",
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
        with tempfile.TemporaryDirectory(prefix=f"pattern-print-{case.task_id}-") as tmp:
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
        "schema_version": "pattern-printing-host-oracle-v2",
        "status": "pass",
        "classification": "host_iteration_only",
        "generator_revision": _generator_revision(),
        "tasks": results,
    }
    _write(out / ".state/host-oracle.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    return results


def _archive(out: Path, target: Path) -> str:
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
    return _sha256(target.read_bytes())


def _accept_docker_receipt(out: Path, receipt: dict[str, object]) -> dict[str, object]:
    if (
        receipt.get("schema_version") != "pattern-printing-docker-sanity-v4"
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
    family_screen_path = out / ".state/family-screen.json"
    family_screen = json.loads(family_screen_path.read_text(encoding="utf-8"))
    screen_binding = receipt.get("family_screen")
    if (
        not isinstance(screen_binding, dict)
        or screen_binding.get("hash") != _sha256(family_screen_path.read_bytes())
        or screen_binding.get("schema_version") != family_screen.get("schema_version")
        or screen_binding.get("hard_rule_result") != "pass"
        or screen_binding.get("hard_rule_comparisons") != 190
        or screen_binding.get("hard_rule_dimensions")
        != list(HARD_RULE_DIMENSIONS)
    ):
        _fail("docker_result_identity_mismatch", "family hard-rule screen")
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
            "family_screen_hash": screen_binding["hash"],
            "hard_rule_dimensions": list(HARD_RULE_DIMENSIONS),
            "hard_rule_pair_count": 190,
            "hard_rule_result": "pass",
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
    with tempfile.TemporaryDirectory(prefix="pattern-print-docker-") as tmp:
        archive = Path(tmp) / "family.tar"
        archive_hash = _archive(out, archive)
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
    toolchain = dict(re.findall(r"^W8TOOL (\S+) (.+)$", proc.stdout, re.M))
    family_screen_path = out / ".state/family-screen.json"
    family_screen = json.loads(family_screen_path.read_text(encoding="utf-8"))
    receipt: dict[str, object] = {
        "schema_version": "pattern-printing-docker-sanity-v4",
        "status": "pass",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "network": "none",
        "image": SANITY_IMAGE,
        "image_id": image_id,
        "archive_hash": archive_hash,
        "generator_revision": _generator_revision(),
        "family_screen": {
            "hash": _sha256(family_screen_path.read_bytes()),
            "schema_version": family_screen["schema_version"],
            "hard_rule_result": family_screen["hard_rule"]["result"],
            "hard_rule_comparisons": family_screen["hard_rule"]["comparison_count"],
            "hard_rule_dimensions": family_screen["hard_rule"]["dimensions"],
            "benchmark_comparisons": len(family_screen["benchmark_comparisons"]),
        },
        "toolchain": toolchain,
        "commands": [
            "cmake normal with strict target flags", "ctest normal",
            "execute normal negative target and require exit 1 with empty diagnostics",
            "fresh cmake ASan/UBSan with strict target flags", "ctest ASan/UBSan",
            "execute ASan/UBSan negative target and require exit 1 with empty diagnostics",
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
    parser.add_argument("--print-docker-result", action="store_true")
    parser.add_argument("--import-docker-stdin", action="store_true")
    parser.add_argument("--plan-remedies", action="store_true")
    args = parser.parse_args()
    if args.plan_remedies:
        plan_remedies(args.out, force=args.force)
        return
    build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    if args.docker_sanity:
        receipt = docker_sanity(args.out, result_out=args.docker_result_out)
        if args.print_docker_result:
            print("W8DOCKERRESULT " + json.dumps(receipt, sort_keys=True))
    if args.import_docker_result:
        import_docker_sanity(args.out, args.import_docker_result)
    if args.import_docker_stdin:
        receipt = json.loads(sys.stdin.read())
        if not isinstance(receipt, dict):
            _fail("docker_result_identity_mismatch", "stdin result is not an object")
        verify_core(args.out)
        _accept_docker_receipt(args.out, receipt)


if __name__ == "__main__":
    main()
