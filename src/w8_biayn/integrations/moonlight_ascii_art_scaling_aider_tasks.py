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
from w8_biayn.integrations.moonlight_ascii_art_scaling_cases import (
    CASES,
    NEGATIVE_MUTATIONS,
    PUBLIC_CONTRACTS,
    Case,
)

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/"
    "aider-text-grid-reshaping/ascii-art-scaling"
)
LEGACY_OUT = Path(
    ".w8-biayn/data/aider-tasks/"
    "aider-text-grid-reshaping/ascii-art-scaling"
)
CURRICULUM = (
    "docs/aider-synthetic/aider-synthetic-text-grid-reshaping/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_ASCII_ART_SCALING_CURRICULUM.md"
)
PROMPT_PATH = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
NORMALIZER = "ascii-art-scaling-semantic-v3-name-and-literal-blind-shingles"
PAIR_THRESHOLD = 0.84


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
        Path(__file__).with_name("moonlight_ascii_art_scaling_cases.py"),
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
        "#include <numeric>\n#include <set>\n#include <utility>\n"
        "namespace curriculum {\n"
        f"{case.return_type} {case.function}({case.params}) {{\n{_format_cpp_body(case.body)}\n}}\n"
        "}\n"
    )


def _negative(case: Case) -> str:
    mutation = NEGATIVE_MUTATIONS[case.task_id]
    if case.body.count(mutation.old) != 1:
        _fail("negative_fixture_drift", case.task_id)
    body = case.body.replace(mutation.old, mutation.new)
    return (
        f'#include "../{case.task_id}.h"\n'
        "#include <algorithm>\n#include <limits>\n#include <map>\n"
        "#include <numeric>\n#include <set>\n#include <utility>\n"
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
    contract = PUBLIC_CONTRACTS[case.task_id]
    return f"""# {case.title}

Implement `{case.function}` in namespace `curriculum` using the declarations in
`{case.task_id}.h`. The task is {case.objective}.

{contract}

The operation is pure and must not mutate inputs. Any condition explicitly
described as invalid returns the default report with `valid == false` and empty
result and diagnostic containers. Do not silently clamp, reorder, or repair an
invalid input.

The complete ordering and tie rules are part of the public contract. In
particular the implementation must preserve these capability terms: {terms}.
Use deterministic row-major order for coordinate diagnostics unless the
task-specific declaration names another order. Output strings are byte-oriented
ASCII grids; no Unicode display-width interpretation is performed.
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
        "curriculum_task_id": case.task_id,
        "legacy_task_id": case.legacy_id,
        "origin": "newly-authored clean-room repository remediation",
        "prompt_path": PROMPT_PATH,
        "status": "local candidate artifact; not admitted SFT data",
        "version": 2,
        "benchmark_separation": (
            "Artifact-derived screen against all bound official Aider C++ holdouts."
        ),
    }
    files = {
        ".docs/introduction.md": (
            f"# {case.title}\n\nA local clean-room ASCII-grid transformation task.\n"
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
        finding_ids.update({"ASCII-SCALE-004", "ASCII-SCALE-005", "ASCII-SCALE-006"})
        record["finding_ids"] = sorted(finding_ids)
        _write(
            record_path,
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            True,
        )


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() == LEGACY_OUT.resolve():
        _fail("legacy_root_immutable", str(out))
    out.mkdir(parents=True, exist_ok=True)
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


def _cpp_shingles(text: str) -> set[str]:
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
    return _shingles(tokens, 5)


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


def _adversarial_clone_results(root: Path, case: Case) -> dict[str, dict[str, object]]:
    variants = {
        "domain-identifier-renamed": lambda text: text.replace("archive", "ledger").replace("stamp", "ticket"),
        "constants-or-policy-only": lambda text: re.sub(r"\b\d+\b", "997", text),
        "opposite-end-selection": lambda text: re.sub(
            r"\b(left|top|front|first)\b",
            lambda match: {"left": "right", "top": "bottom", "front": "back", "first": "last"}[match.group(1)],
            text,
            flags=re.IGNORECASE,
        ),
    }
    results: dict[str, dict[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="ascii-scale-clones-") as tmp:
        for name, transform in variants.items():
            clone = Path(tmp) / name
            shutil.copytree(root, clone)
            for relative in (
                ".docs/introduction.md", ".docs/instructions.md", next(root.glob("*.h")).name,
                ".meta/example.cpp", "task_visible_test.cpp", ".meta/task_hidden_test.cpp",
            ):
                path = clone / relative
                path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")
            results[name] = _pair_result(root, clone, case, case)
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
    has_contract = PUBLIC_CONTRACTS[case.task_id] in instructions
    return None if has_terms and has_contract else "prompt_contract_incomplete"


def _bound_holdouts(repo_root: Path) -> list[Path]:
    base = repo_root / ".cache/upstreams/aider-polyglot/cpp/exercises"
    roots = sorted(path.parent for path in base.glob("*/*/.meta/config.json"))
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
                "family_id_after": f"ascii-art-scaling-v2/{case.task_id}",
                "generator_revision_after": _generator_revision(),
                "tree_hash_after": _tree_hash(out / case.task_id),
                "primary_core_objective": "achieved",
                "primary_core_evidence": {
                    "reference_function": case.function,
                    "negative_fixture": NEGATIVE_MUTATIONS[case.task_id].description,
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
    if {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"} != {case.task_id for case in CASES}:
        _fail("generator_output_drift", "task inventory")
    evidence: dict[str, dict[str, object]] = {}
    feature_sets: dict[str, set[str]] = {}
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
        mutation = NEGATIVE_MUTATIONS[case.task_id]
        formatted_new = _format_cpp_body(mutation.new).strip()
        formatted_old = _format_cpp_body(mutation.old).strip()
        if formatted_new not in negative or formatted_old in negative:
            _fail("invariant_not_enforced", f"negative fixture: {case.task_id}")
        cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
        negative_target = cmake.split("add_executable(task_negative", 1)[-1]
        if "task_visible_test.cpp" not in negative_target or "target_compile_options(task_negative PRIVATE -Wall -Wextra -Wpedantic -Werror)" not in cmake:
            _fail("negative_fixture_not_strict", case.task_id)
        feature_sets[case.task_id] = _artifact_features(root, case)
        evidence[case.task_id] = {
            "artifact_roles": ["docs", "public_api", "reference", "visible_tests", "private_tests"],
            "tree_hash": _tree_hash(root),
            "reference_hash": _reference_hash(root),
            "negative_fixture": mutation.description,
            "prompt_boundary": "pass",
        }
    pairwise = []
    for left, right in combinations(CASES, 2):
        score = _overlap(feature_sets[left.task_id], feature_sets[right.task_id])
        pairwise.append({"left": left.task_id, "right": right.task_id, "overlap": round(score, 6)})
        if score >= PAIR_THRESHOLD:
            _fail("duplicate_family", f"{left.task_id} vs {right.task_id}: {score:.3f}")
    holdouts = _bound_holdouts(repo_root)
    benchmark_results = []
    for case in CASES:
        for holdout in holdouts:
            score = _overlap(feature_sets[case.task_id], _artifact_features(holdout))
            result = {"task_id": case.task_id, "holdout": holdout.name, "overlap": round(score, 6)}
            benchmark_results.append(result)
            if case.task_id == holdout.name or score >= 0.72:
                _fail("benchmark_content_overlap", f"{case.task_id} vs {holdout.name}: {score:.3f}")
    archive_case = next(case for case in CASES if case.task_id == "scale-archive-stamps")
    adversarial = _adversarial_clone_results(out / archive_case.task_id, archive_case)
    if any(item["failure"] != "duplicate_family" for item in adversarial.values()):
        _fail("duplicate_family", f"adversarial controls: {adversarial}")
    screen = {
        "schema_version": "ascii-art-scaling-family-screen-v3",
        "normalizer": NORMALIZER,
        "root_count": len(CASES),
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
            "schema_version": "ascii-art-scaling-host-oracle-v2",
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
        with tempfile.TemporaryDirectory(prefix=f"ascii-scale-{case.task_id}-") as tmp:
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
        "schema_version": "ascii-art-scaling-host-oracle-v2",
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
        receipt.get("schema_version") != "ascii-art-scaling-docker-sanity-v3"
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
    with tempfile.TemporaryDirectory(prefix="ascii-scale-docker-") as tmp:
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
    receipt: dict[str, object] = {
        "schema_version": "ascii-art-scaling-docker-sanity-v3",
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
        ],
        "tasks": {
            case.task_id: {
                **counts[case.task_id],
                "tree_hash": _tree_hash(out / case.task_id),
                "mounted_tree_hash": mounted_hashes[case.task_id],
                "reference_hash": _reference_hash(out / case.task_id),
                "negative_fixture": NEGATIVE_MUTATIONS[case.task_id].description,
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
    args = parser.parse_args()
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
