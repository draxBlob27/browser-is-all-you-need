"""Remediate and materialize algorithmically distinct run-length task roots."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
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
from w8_biayn.integrations.moonlight_run_length_encoding_cases import CASES, RleCase

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/aider-dsa/run-length-encoding"
)
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dsa/run-length-encoding")
CURRICULUM = (
    "docs/aider-synthetic/aider-synthetic-dsa/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_RUN_LENGTH_ENCODING_CURRICULUM.md"
)
FAMILY_SPEC = "docs/aider-tasks-spec/aider-dsa/run-length-encoding.md"
SELECTED_PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY_ID = "aider-dsa-run-length-encoding-v2"
LEGACY_FAMILY_ID = "aider-dsa-run-length-encoding-v1-template"
NORMALIZER = "run-length-semantic-v3-emitted-artifact-dimensions-9gram"
PAIR_THRESHOLD = 0.72
DIMENSION_THRESHOLDS = {
    "public_api": 0.72,
    "owned_state_algorithm": 0.72,
    "mutation_selection": 0.72,
    "invalid_boundary": 0.72,
    "reference_control_flow": 0.72,
    "deterministic_oracle": 0.72,
    "topic_negative_fixture": 0.72,
}
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
SANITY_IMAGE_ID = (
    "sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
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
OFFICIAL_HOLDOUTS = frozenset(
    {
        "all-your-base", "allergies", "bank-account", "binary-search-tree",
        "circular-buffer", "clock", "complex-numbers", "crypto-square", "diamond",
        "dnd-character", "gigasecond", "grade-school", "kindergarten-garden",
        "knapsack", "linked-list", "meetup", "parallel-letter-frequency",
        "perfect-numbers", "phone-number", "queen-attack", "robot-name",
        "space-age", "spiral-matrix", "sublist", "yacht", "zebra-puzzle",
    }
)
TASKS = CASES
CASE_SOURCE = Path(__file__).with_name("moonlight_run_length_encoding_cases.py")


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _source_hash(path: Path) -> str:
    return _sha(path.read_bytes())


def _generator_hash() -> str:
    digest = hashlib.sha256()
    for path in (Path(__file__), CASE_SOURCE):
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        p for p in root.rglob("*") if p.is_file() and ".state" not in p.parts
    ):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _same_path(left: Path, right: Path) -> bool:
    return left.resolve() == right.resolve()


CMAKE = r'''cmake_minimum_required(VERSION 3.16)
project(run_length_encoding_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
enable_testing()
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Reference source")
set(BAD_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/.meta/bad_substitute.cpp" CACHE FILEPATH "Negative source")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
add_executable(task_negative "${BAD_SOURCE}" .meta/task_hidden_test.cpp)
foreach(target task_visible task_hidden task_negative)
  target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_test(NAME topic_negative_fixture COMMAND task_negative)
set_tests_properties(topic_negative_fixture PROPERTIES WILL_FAIL TRUE)
'''


def _legacy_hash(case: RleCase) -> str:
    root = LEGACY_ROOT / case.legacy_id
    if not root.is_dir():
        _fail("legacy_root_missing", str(root))
    return _tree_hash(root)


def _remedy_markdown(case: RleCase, *, identity: str, legacy: bool) -> str:
    role = "legacy audit root" if legacy else "retained/replacement generated root"
    return f"""# Remedy: {identity}

## Identity

Task ID: `{identity}`. Task-spec revision: 2. Family: `{FAMILY_ID}`. Role:
{role}. Disposition: `{case.disposition}`. Legacy input: `{case.legacy_id}`.
Source inventory: repository-authored clean-room curriculum. License: repository-authored,
pass. Generator: `src/w8_biayn/integrations/moonlight_run_length_encoding_aider_tasks.py`.
Benchmark screen: pending until artifact-derived verification. Selected workflow prompt:
`{SELECTED_PROMPT}`. User inputs: `FAMILY_NAME=run-length-encoding`,
`FAMILY_TYPE=aider-dsa`.

## Objective

{case.objective} The observable primary mechanism is `{case.profile}`; success requires
the task-specific hidden state/behavior marker `{case.marker}` and the full public trace.

## Public API

C++17 namespace is `curriculum`. Editable-file order is `<task-id>.h`, then
`<task-id>.cpp`; values are owned by the task object or returned by value/reference as declared.

```cpp
{case.header.strip()}
```

## Behavior table

The complete public behavior is the following visible contract. Valid inputs, successful and
empty results, invalid/duplicate/absent behavior, mutation atomicity, ordering, ties, overflow,
and a public boundary are binding exactly as stated:

{case.instructions.strip()}

## Implementation invariant

The reference must implement `{case.profile}` with marker `{case.marker}`. The legacy
`max_run_count`/`append_chunk`/`expand` vector template, noun-only variants, precomputed answers,
hard-coded visible cases, and cross-root references are forbidden substitutes. Private tests
observe complete public state after mutations and exercise the task-specific boundary.

## Starter and reference

The header is a complete compilable declaration. The editable source is a coherent set of
incomplete stubs. `.meta/example.h` reproduces the header and `.meta/example.cpp` independently
implements the contract without importing the legacy renderer, benchmark code, or hidden tests.

## Tests

The visible case covers ordinary behavior and a public boundary. The hidden case covers invalid
input without mutation, the mechanism marker, ordering/ties, and empty/absent behavior. The
deterministic negative fixture compiles the incomplete substitute and requires the same hidden
test to reject it. No randomness is used. Every public operation appears in the emitted hidden
oracle. Stateful roots use an independent value/vector state oracle after each mutation and
compare every public observable, including ordering and query results.

## Files and metadata

Solutions: `<task-id>.h`, `<task-id>.cpp`; tests: `task_visible_test.cpp`,
`.meta/task_hidden_test.cpp`; references: `.meta/example.h`, `.meta/example.cpp` in matching
order. Docs, CMake, provenance, tests, references, receipts, and `.meta/bad_substitute.cpp` are
private. Support digest is `not_applicable:no-shared-support`.

## Build/oracle

C++17, explicit `Unix Makefiles`, pinned `/usr/local/bin/g++` in `{SANITY_IMAGE}`. Expected
discovery is three tests in normal and three in a fresh ASan/UBSan build, including the executed
`WILL_FAIL` topic substitute. Receipt binds owner, tree, reference, image, compiler/CMake, exact
commands, equal positive counts, and `--network none`.

## Family/contamination

Compare emitted docs, API, reference control flow, visible test, and hidden test for all 190
unordered family pairs with `{NORMALIZER}`, plus all 20 roots against all 26 official C++
holdouts. The decision is pending before implementation; threshold breaches are
`duplicate_family` or `benchmark_content_overlap`, never waived.

## Optional dataset handoff

`not_requested`. No rows, renderer/token/mask evidence, split, export, producer, consumer,
training, or release work is authorized.

## Acceptance

Run the focused pytest, then the owner with `--force --verify-core --verify` in the pinned,
network-disabled image. Stable failures include `remedy_spec_incomplete`,
`prompt_contract_incomplete`, `unsafe_path`, `target_reference_mismatch`,
`whole_format_failed`, `invariant_not_enforced`, `trace_contract_incomplete`, `duplicate_family`,
`benchmark_content_overlap`, `zero_tests`, `reference_tests_failed`,
`reference_sanitizer_failed`, and `sanitizer_test_count_mismatch`.
"""


def _remedy_record(
    case: RleCase, *, identity: str, legacy: bool, markdown: str
) -> dict[str, object]:
    return {
        "schema_version": "aider-task-remedy-v1",
        "task_id": identity,
        "replacement_task_id": case.task_id,
        "legacy_task_id": case.legacy_id,
        "family_id_before": LEGACY_FAMILY_ID,
        "family_id_after": FAMILY_ID,
        "tree_hash_before": _legacy_hash(case),
        "generator_path": (
            "src/w8_biayn/integrations/"
            "moonlight_run_length_encoding_aider_tasks.py"
        ),
        "generator_revision": _generator_hash(),
        "finding_ids": ["RLE-F01", "RLE-F02", "RLE-F03", "RLE-F04"],
        "disposition": case.disposition,
        "benchmark_screen": "pending",
        "license_screen": "pass",
        "remedy_spec_path": f".state/remedy/{identity}.md",
        "remedy_spec_hash": _sha(markdown.encode()),
        "record_role": "legacy" if legacy else "candidate",
        "primary_core_objective": "not_achieved" if legacy else "planned",
        "status": "planned",
        "local_status": "planned",
    }


def _write_remedies(out: Path, force: bool) -> None:
    remedy = out / ".state" / "remedy"
    for case in CASES:
        identities = [(case.legacy_id, True)]
        if case.task_id != case.legacy_id:
            identities.append((case.task_id, False))
        for identity, legacy in identities:
            markdown = _remedy_markdown(case, identity=identity, legacy=legacy)
            record = _remedy_record(
                case, identity=identity, legacy=legacy, markdown=markdown
            )
            _write(remedy / f"{identity}.md", markdown, force)
            _write(
                remedy / f"{identity}.json",
                json.dumps(record, indent=2, sort_keys=True) + "\n",
                force,
            )


def _invalidate_generated_evidence(out: Path) -> None:
    """Remove only owner-recognized stale receipts before forced regeneration."""
    if not out.exists():
        return
    for root in sorted(
        path for path in out.iterdir() if path.is_dir() and path.name != ".state"
    ):
        provenance_path = root / ".meta/provenance.json"
        if not provenance_path.is_file():
            _fail("foreign_generated_root", str(root))
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        if provenance.get("family_id") != FAMILY_ID:
            _fail("foreign_generated_root", str(root))
    for relative in (
        ".state/docker-sanity.json",
        ".state/host-oracle-iteration.json",
        ".state/family-screen.json",
    ):
        path = out / relative
        if path.is_file():
            path.unlink()


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if _same_path(out, LEGACY_ROOT):
        _fail("legacy_root_is_immutable", str(out))
    if len(CASES) != 20 or len({case.task_id for case in CASES}) != 20:
        _fail("duplicate_family", "expected 20 unique v2 task IDs")
    if force:
        _invalidate_generated_evidence(out)
    _write_remedies(out, force)
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        config = {
            "authors": ["w8-biayn"],
            "blurb": case.objective,
            "files": {
                "solution": ["task.h", "task.cpp"],
                "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
                "example": [".meta/example.h", ".meta/example.cpp"],
            },
        }
        provenance = {
            "audit_specification": FAMILY_SPEC,
            "curriculum_document": CURRICULUM,
            "curriculum_task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "legacy_family_preserved_at": LEGACY_ROOT.as_posix(),
            "family_id": FAMILY_ID,
            "semantic_profile": case.profile,
            "disposition": case.disposition,
            "origin": "repository-authored clean-room remediation",
            "license": "repository-authored",
            "status": "local candidate; not dataset admission",
            "version": 2,
            "benchmark_separation": (
                "Independent API, state, control flow, tests, and reference; all 26 "
                "official Aider C++ roots and the excluded source RLE root remain holdouts."
            ),
        }
        files = {
            ".docs/introduction.md": f"# {case.title}\n\n{case.objective}\n",
            ".docs/instructions.md": case.instructions.rstrip() + "\n",
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": (
                json.dumps(provenance, indent=2, sort_keys=True) + "\n"
            ),
            ".meta/tests.toml": (
                "[visible]\n"
                'description = "ordinary behavior and public boundary"\n\n'
                "[hidden]\n"
                'description = "task-specific invariant, invalid input, ordering, and atomicity"\n\n'
                "[negative]\n"
                'description = "compiled incomplete substitute is rejected by hidden behavior"\n'
            ),
            "task.h": case.header,
            "task.cpp": case.starter,
            ".meta/example.h": case.header,
            ".meta/example.cpp": case.reference,
            ".meta/bad_substitute.cpp": case.starter,
            "task_visible_test.cpp": case.visible_test,
            ".meta/task_hidden_test.cpp": case.hidden_test,
            "CMakeLists.txt": CMAKE,
        }
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def _safe_relative(value: str) -> str:
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        _fail("unsafe_path", value)
    return path.as_posix()


def _whole_format_failure(root: Path, response: str) -> str | None:
    task = load_task(root)
    try:
        blocks = parse_whole_file_blocks(response)
    except WholeFormatError:
        return "whole_format_failed"
    if list(blocks) != list(task.editable_files):
        return "whole_format_failed"
    return None


def _semantic_tokens(content: str) -> list[str]:
    content = re.sub(r"/\*.*?\*/|//[^\n]*", " ", content, flags=re.S)
    content = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", content)
    raw = re.findall(
        r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]",
        content,
    )
    keywords = {
        "if", "else", "for", "while", "return", "throw", "class", "struct",
        "const", "auto", "bool", "int", "long", "void", "true", "false",
        "public", "private", "namespace", "std", "vector", "optional", "map",
        "set", "string", "size_t", "begin", "end", "insert", "erase",
    }
    return [
        token if token in keywords or not re.match(r"[A-Za-z_]", token) else "ID"
        for token in raw
    ]


def _ngrams(tokens: list[str], width: int = 9) -> set[tuple[str, ...]]:
    return {
        tuple(tokens[index : index + width])
        for index in range(max(0, len(tokens) - width + 1))
    }


def _overlap(left: str, right: str) -> float:
    a = _ngrams(_semantic_tokens(left))
    b = _ngrams(_semantic_tokens(right))
    denominator = min(len(a), len(b))
    return len(a & b) / denominator if denominator else 1.0


def _read_artifact_files(root: Path, paths: Sequence[str]) -> str:
    return "\n".join(
        (root / path).read_text(encoding="utf-8", errors="strict") for path in paths
    )


def _artifact_profile(root: Path) -> dict[str, object]:
    """Derive hard-rule evidence only from files emitted beneath one task root."""
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    files = config.get("files", {})
    failure = _role_failure(root, files)
    if failure:
        _fail(failure, root.name)
    docs_paths = [
        path
        for path in (
            ".docs/introduction.md",
            ".docs/instructions.md",
            ".docs/instructions.append.md",
        )
        if (root / path).is_file()
    ]
    api_paths = [
        path for path in files["solution"] if Path(path).suffix in {".h", ".hpp"}
    ]
    reference_paths = list(files["example"])
    reference_source_paths = [
        path for path in reference_paths if Path(path).suffix in {".cc", ".cpp", ".cxx"}
    ]
    visible_test_paths = [path for path in files["test"] if not path.startswith(".meta/")]
    private_test_paths = [path for path in files["test"] if path.startswith(".meta/")]
    negative_paths = [".meta/bad_substitute.cpp"]
    required_groups = {
        "docs": docs_paths,
        "public_api": api_paths,
        "reference": reference_paths,
        "reference_source": reference_source_paths,
        "visible_tests": visible_test_paths,
        "private_tests": private_test_paths,
        "negative_substitute": negative_paths,
    }
    for role, paths in required_groups.items():
        if not paths or any(not (root / path).is_file() for path in paths):
            _fail("generator_output_drift", f"{root.name} missing emitted {role}")
    sections = {
        role: _read_artifact_files(root, paths) for role, paths in required_groups.items()
    }
    tests = sections["visible_tests"] + "\n" + sections["private_tests"]
    combined = "\n".join(
        (
            sections["docs"],
            sections["public_api"],
            sections["reference"],
            tests,
        )
    )
    # The deliberately wrong substitute is excluded from the combined similarity corpus,
    # so a different bad answer cannot manufacture apparent candidate diversity. It is
    # still a separately blocking hard-rule dimension below.
    dimensions = {
        "public_api": sections["public_api"],
        "owned_state_algorithm": (
            sections["public_api"] + "\n" + sections["reference_source"]
        ),
        "mutation_selection": (
            sections["reference_source"] + "\n" + sections["private_tests"]
        ),
        "invalid_boundary": sections["docs"] + "\n" + tests,
        "reference_control_flow": sections["reference_source"],
        "deterministic_oracle": tests,
        "topic_negative_fixture": (
            sections["negative_substitute"] + "\n" + sections["private_tests"]
        ),
    }
    return {
        "task_id": root.name,
        "root": root,
        "paths": required_groups,
        "sections": sections,
        "combined": combined,
        "dimensions": dimensions,
        "section_hashes": {
            role: _sha(content.encode()) for role, content in sections.items()
        },
        "dimension_token_counts": {
            role: len(_semantic_tokens(content)) for role, content in dimensions.items()
        },
        "combined_token_count": len(_semantic_tokens(combined)),
    }


def _artifact_profiles(out: Path) -> dict[str, dict[str, object]]:
    return {
        case.task_id: _artifact_profile(out / case.task_id) for case in CASES
    }


def _pair_evidence(
    left: dict[str, object], right: dict[str, object]
) -> dict[str, object]:
    dimension_overlap = {
        name: round(
            _overlap(left["dimensions"][name], right["dimensions"][name]), 6
        )
        for name in DIMENSION_THRESHOLDS
    }
    combined_overlap = round(_overlap(left["combined"], right["combined"]), 6)
    violations = [
        name
        for name, threshold in DIMENSION_THRESHOLDS.items()
        if dimension_overlap[name] >= threshold
    ]
    if combined_overlap >= PAIR_THRESHOLD:
        violations.insert(0, "combined_primary_logic_implementation")
    return {
        "left": left["task_id"],
        "right": right["task_id"],
        "combined_overlap": combined_overlap,
        "dimension_overlap": dimension_overlap,
        "violations": violations,
    }


def _require_distinct_pair(evidence: dict[str, object]) -> None:
    if evidence["violations"]:
        _fail(
            "duplicate_family",
            f"{evidence['left']} resembles {evidence['right']}: "
            f"{','.join(evidence['violations'])}",
        )


def _screen_artifact_profiles(
    profiles: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    task_ids = sorted(profiles)
    for index, left_id in enumerate(task_ids):
        for right_id in task_ids[index + 1 :]:
            evidence = _pair_evidence(profiles[left_id], profiles[right_id])
            _require_distinct_pair(evidence)
            rows.append(evidence)
    return rows


def _make_adversarial_clone(source: Path, destination: Path, kind: str) -> None:
    if destination.exists():
        _fail("adversarial_fixture_failed", f"destination exists: {destination}")
    shutil.copytree(source, destination)
    profile = _artifact_profile(destination)
    paths = sorted({path for values in profile["paths"].values() for path in values})

    def transform(content: str) -> str:
        if kind == "domain-identifier-renamed":
            replacements = (
                ("Access", "Permit"),
                ("access", "permit"),
                ("Door", "Gate"),
                ("door", "gate"),
                ("User", "Member"),
                ("user", "member"),
            )
            for before, after in replacements:
                content = content.replace(before, after)
            return content
        if kind == "constants-or-policy-only":
            return re.sub(r"\b\d+\b", "77", content)
        if kind == "opposite-end-selection":
            return (
                content.replace("earlier", "later")
                .replace("back()", "front()")
                .replace("back().", "front().")
            )
        _fail("adversarial_fixture_failed", kind)
        raise AssertionError("unreachable")

    for relative in paths:
        path = destination / relative
        path.write_text(transform(path.read_text(encoding="utf-8")), encoding="utf-8")


def _adversarial_clone_results(out: Path) -> dict[str, dict[str, object]]:
    source = out / CASES[0].task_id
    original = _artifact_profile(source)
    results: dict[str, dict[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="rle-hard-rule-clones-") as temporary:
        temporary_root = Path(temporary)
        for kind in (
            "domain-identifier-renamed",
            "constants-or-policy-only",
            "opposite-end-selection",
        ):
            clone = temporary_root / kind
            _make_adversarial_clone(source, clone, kind)
            evidence = _pair_evidence(original, _artifact_profile(clone))
            if not evidence["violations"]:
                _fail("duplicate_family_fixture_failed", kind)
            try:
                _require_distinct_pair(evidence)
            except RuntimeError as error:
                if not str(error).startswith("duplicate_family:"):
                    raise
            else:
                _fail("duplicate_family_fixture_failed", kind)
            results[kind] = {
                "failure": "duplicate_family",
                "combined_overlap": evidence["combined_overlap"],
                "dimension_overlap": evidence["dimension_overlap"],
                "violations": evidence["violations"],
                "evidence_source": "copied_and_mutated_emitted_task_root",
            }
    return results


def _core_failure(case: RleCase, reference: str) -> str | None:
    if case.marker not in reference:
        return "invariant_not_enforced"
    legacy_markers = ("max_run_count", "append_chunk", "expand()", "total_units")
    if sum(marker in reference for marker in legacy_markers) >= 3:
        return "duplicate_family"
    return None


def _prompt_contract_failure(case: RleCase, instructions: str) -> str | None:
    lowered = instructions.lower()
    if any(term.lower() not in lowered for term in case.prompt_terms):
        return "prompt_contract_incomplete"
    return None


def _public_operation_names(case: RleCase) -> tuple[str, ...]:
    return tuple(
        part.strip().split("(", 1)[0].split("::")[-1]
        for part in case.public_api.split(";")
    )


def _trace_contract_failure(case: RleCase, root: Path) -> str | None:
    """Bind the declared contract to actual emitted API and deterministic tests."""
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    files = config["files"]
    public_api = "\n".join(
        (root / path).read_text(encoding="utf-8")
        for path in files["solution"]
        if Path(path).suffix in {".h", ".hpp"}
    )
    hidden_oracle = "\n".join(
        (root / path).read_text(encoding="utf-8")
        for path in files["test"]
        if path.startswith(".meta/")
    )
    for operation in _public_operation_names(case):
        token = rf"\b{re.escape(operation)}\b"
        if not re.search(token, public_api) or not re.search(token, hidden_oracle):
            return "trace_contract_incomplete"
    if "::" in case.public_api:
        if "auto state=" not in hidden_oracle or hidden_oracle.count("f+=!state") < 2:
            return "trace_contract_incomplete"
    return None


def _role_failure(root: Path, files: dict[str, list[str]]) -> str | None:
    try:
        solution = [_safe_relative(value) for value in files.get("solution", [])]
        tests = [_safe_relative(value) for value in files.get("test", [])]
        examples = [_safe_relative(value) for value in files.get("example", [])]
    except RuntimeError:
        return "unsafe_path"
    if any(
        value.startswith((".docs/", ".meta/")) or value == "CMakeLists.txt"
        for value in solution
    ):
        return "unsafe_path"
    if len(solution) != 2 or len(examples) != 2:
        return "target_reference_mismatch"
    if set(solution) & (set(tests) | set(examples)):
        return "unsafe_path"
    if any(not (root / value).is_file() for value in [*solution, *tests, *examples]):
        return "target_reference_mismatch"
    if [Path(value).suffix for value in solution] != [
        Path(value).suffix for value in examples
    ]:
        return "target_reference_mismatch"
    return None


def _verify_remedies(out: Path) -> None:
    remedy = out / ".state" / "remedy"
    expected = {case.legacy_id for case in CASES} | {
        case.task_id for case in CASES if case.task_id != case.legacy_id
    }
    records = {path.stem for path in remedy.glob("*.json")} if remedy.is_dir() else set()
    if records != expected:
        _fail("remedy_spec_incomplete", f"expected {len(expected)}, found {len(records)}")
    for identity in sorted(expected):
        record = json.loads((remedy / f"{identity}.json").read_text(encoding="utf-8"))
        markdown = (remedy / f"{identity}.md").read_text(encoding="utf-8")
        positions = [markdown.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if -1 in positions or positions != sorted(positions):
            _fail("remedy_spec_incomplete", identity)
        if record.get("remedy_spec_hash") != _sha(markdown.encode()):
            _fail("remedy_spec_incomplete", f"stale hash: {identity}")
        if record.get("disposition") not in {"replace", "repair-in-place"}:
            _fail("remedy_disposition_conflict", identity)


def _benchmark_slug_screen(root: Path) -> None:
    corpus = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".state" not in path.parts
    ).lower()
    for slug in OFFICIAL_HOLDOUTS:
        if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", corpus):
            _fail("benchmark_id_overlap", f"{root.name}: {slug}")


def _holdout_screen(
    profiles: dict[str, dict[str, object]],
) -> dict[str, object]:
    if not HOLDOUT_ROOT.is_dir():
        _fail("benchmark_screen_not_completed", str(HOLDOUT_ROOT))
    holdouts: dict[str, str] = {}
    inventory = hashlib.sha256()
    for root in sorted(path for path in HOLDOUT_ROOT.iterdir() if path.is_dir()):
        chunks: list[str] = []
        for path in sorted(
            p for p in root.rglob("*")
            if p.is_file() and p.suffix in {".h", ".hpp", ".cpp", ".md"}
            and "catch" not in p.name.lower()
        ):
            inventory.update(path.relative_to(HOLDOUT_ROOT).as_posix().encode())
            inventory.update(path.read_bytes())
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        holdouts[root.name] = "\n".join(chunks)
    strongest = {"candidate": None, "holdout": None, "overlap": 0.0}
    for task_id, profile in profiles.items():
        corpus = profile["combined"]
        for slug, holdout in holdouts.items():
            score = _overlap(corpus, holdout)
            if score > strongest["overlap"]:
                strongest = {
                    "candidate": task_id,
                    "holdout": slug,
                    "overlap": round(score, 6),
                }
            if score >= 0.60:
                _fail(
                    "benchmark_content_overlap",
                    f"{task_id} resembles {slug}: {score:.3f}",
                )
    return {
        "status": "pass",
        "normalizer": NORMALIZER,
        "source_inventory": f"sha256:{inventory.hexdigest()}",
        "holdout_root_count": len(holdouts),
        "comparison_scope": (
            "actual emitted docs, public API, reference, visible and private tests"
        ),
        "evidence_source": "emitted_task_tree",
        "threshold": 0.60,
        "strongest": strongest,
    }


def _family_screen(
    out: Path, profiles: dict[str, dict[str, object]] | None = None
) -> dict[str, object]:
    profiles = profiles or _artifact_profiles(out)
    rows = _screen_artifact_profiles(profiles)
    maximum_by_dimension = {
        name: max(row["dimension_overlap"][name] for row in rows)
        for name in DIMENSION_THRESHOLDS
    }
    task_profiles = {
        task_id: {
            "paths": profile["paths"],
            "section_hashes": profile["section_hashes"],
            "dimension_token_counts": profile["dimension_token_counts"],
            "combined_token_count": profile["combined_token_count"],
        }
        for task_id, profile in profiles.items()
    }
    return {
        "normalizer": NORMALIZER,
        "evidence_source": "actual_emitted_task_tree",
        "root_count": len(profiles),
        "count_contract": {
            "type": "curriculum_inventory",
            "expected": 20,
            "user_minimum": None,
            "user_maximum": None,
        },
        "pair_threshold": PAIR_THRESHOLD,
        "dimension_thresholds": DIMENSION_THRESHOLDS,
        "pairwise_semantic_overlap": rows,
        "adversarial_clone_results": _adversarial_clone_results(out),
        "maximum_overlap": max(
            (row["combined_overlap"] for row in rows), default=0.0
        ),
        "maximum_overlap_by_dimension": maximum_by_dimension,
        "task_artifact_profiles": task_profiles,
    }


def _update_records(out: Path, **updates: object) -> None:
    remedy = out / ".state" / "remedy"
    for path in remedy.glob("*.json"):
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update(updates)
        candidate = out / str(record["replacement_task_id"])
        if candidate.is_dir():
            record["tree_hash_after"] = _tree_hash(candidate)
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_core(out: Path, *, require_remedy: bool = True) -> dict[str, object]:
    expected = {case.task_id for case in CASES}
    actual = {
        path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"
    }
    if actual != expected:
        _fail("generator_output_drift", f"expected {sorted(expected)}, found {sorted(actual)}")
    if require_remedy:
        _verify_remedies(out)
    with tempfile.TemporaryDirectory(prefix="rle-v2-regeneration-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for task_id in expected:
            if _tree_hash(out / task_id) != _tree_hash(fresh / task_id):
                _fail("generator_output_drift", task_id)
    profiles = _artifact_profiles(out)
    family = _family_screen(out, profiles)
    holdouts = _holdout_screen(profiles)
    evidence: dict[str, object] = {}
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        files = config.get("files", {})
        failure = _role_failure(root, files)
        if failure:
            _fail(failure, case.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        private_names = [
            *files["test"], *files["example"], "CMakeLists.txt",
            ".meta/provenance.json", ".meta/bad_substitute.cpp",
        ]
        if any(name in prompt for name in private_names):
            _fail("prompt_contract_incomplete", case.task_id)
        if _prompt_contract_failure(case, (root / ".docs/instructions.md").read_text()):
            _fail("prompt_contract_incomplete", case.task_id)
        if _trace_contract_failure(case, root):
            _fail("trace_contract_incomplete", case.task_id)
        reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
        if _core_failure(case, reference):
            _fail("invariant_not_enforced", case.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if _whole_format_failure(root, answer):
            _fail("target_reference_mismatch", case.task_id)
        malformed = (
            "prose\n" + answer,
            answer + "\nunknown.cpp\n```cpp\n// no\n```\n",
            f"{task.editable_files[0]}\n```cpp\n// missing\n```\n",
        )
        if any(_whole_format_failure(root, response) != "whole_format_failed" for response in malformed):
            _fail("whole_format_failed", case.task_id)
        _benchmark_slug_screen(root)
        evidence[case.task_id] = {
            "legacy_task_id": case.legacy_id,
            "disposition": case.disposition,
            "primary_core_objective": "achieved",
            "semantic_profile": case.profile,
            "tree_hash": _tree_hash(root),
            "reference_hash": _source_hash(root / ".meta/example.cpp"),
            "prompt_boundary": "pass",
            "role_reference_mapping": "pass",
            "topic_negative_fixture": "configured_and_executed_by_oracle",
            "deterministic_trace": "all_public_operations_and_observable_state",
            "hard_rule_artifact_profile": family["task_artifact_profiles"][case.task_id],
        }
    state = out / ".state"
    state.mkdir(parents=True, exist_ok=True)
    screen = {
        "schema_version": "aider-rle-family-screen-v2",
        "family_id": FAMILY_ID,
        "owner_hash": _source_hash(Path(__file__)),
        "case_source_hash": _source_hash(CASE_SOURCE),
        "generator_hash": _generator_hash(),
        "prompt_boundary": "pass",
        "role_reference_mapping": "pass",
        "primary_core_objective": "pass:20/20",
        "negative_fixture": "configured:compiled topic substitute per root",
        "deterministic_trace": "pass:20/20",
        "duplicate_family": "pass",
        "benchmark_contamination": "pass",
        "family": family,
        "holdouts": holdouts,
        "tasks": evidence,
    }
    (state / "family-screen.json").write_text(
        json.dumps(screen, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _update_records(
        out,
        primary_core_objective="achieved",
        status="implemented",
        local_status="implemented_pending_mandatory_docker_oracle",
        benchmark_screen="pass",
        family_screen="pass",
        prompt_boundary="pass",
        generator_revision=_generator_hash(),
    )
    return screen


def _run_checked(command: list[str], *, failure: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    if result.returncode:
        _fail(failure, f"{' '.join(command)}\n{result.stdout[-4000:]}")
    return result


def _discovered(output: str) -> int:
    match = re.search(r"Total Tests:\s*(\d+)", output)
    if not match:
        _fail("test_discovery_failed", output[-1000:])
    count = int(match.group(1))
    if count <= 0:
        _fail("zero_tests", output[-1000:])
    return count


def verify(out: Path) -> dict[str, object]:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        _fail("oracle_prerequisite_missing", "verification requires cmake and c++")
    screen = verify_core(out)
    task_receipts: list[dict[str, object]] = []
    for case in CASES:
        root = out / case.task_id
        modes: dict[str, object] = {}
        with tempfile.TemporaryDirectory(prefix="rle-v2-oracle-") as temporary:
            copied = Path(temporary) / case.task_id
            shutil.copytree(root, copied)
            reference = copied / ".meta" / "example.cpp"
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
                build_dir = copied / f"build-{mode}"
                configure = [
                    "cmake", "-S", str(copied), "-B", str(build_dir),
                    "-G", "Unix Makefiles", "-DCMAKE_CXX_COMPILER=c++",
                    f"-DTASK_SOURCE={reference}", *flags,
                ]
                failure = "reference_sanitizer_failed" if mode == "sanitizer" else "reference_compile_failed"
                _run_checked(configure, failure=failure)
                _run_checked(
                    ["cmake", "--build", str(build_dir), "--parallel", "2"],
                    failure=failure,
                )
                discovery = _run_checked(
                    ["ctest", "--test-dir", str(build_dir), "-N"],
                    failure="test_discovery_failed",
                )
                count = _discovered(discovery.stdout)
                executed = _run_checked(
                    ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
                    failure=(
                        "reference_sanitizer_failed"
                        if mode == "sanitizer"
                        else "reference_tests_failed"
                    ),
                )
                modes[mode] = {
                    "discovered_tests": count,
                    "configure": configure,
                    "ctest_output_hash": _sha(executed.stdout.encode()),
                    "topic_negative_fixture_executed": True,
                }
        if modes["normal"]["discovered_tests"] != modes["sanitizer"]["discovered_tests"]:
            _fail("sanitizer_test_count_mismatch", case.task_id)
        task_receipts.append(
            {
                "task_id": case.task_id,
                "tree_hash": _tree_hash(root),
                "reference_hash": _source_hash(root / ".meta/example.cpp"),
                "modes": modes,
            }
        )
    runtime_kind = os.environ.get("W8_BIAYN_ORACLE_RUNTIME", "host-prerequisite")
    image = os.environ.get("W8_BIAYN_ORACLE_IMAGE")
    network = os.environ.get("W8_BIAYN_ORACLE_NETWORK", "not_recorded")
    docker_sanity = runtime_kind == "docker-sanity" and image in {
        SANITY_IMAGE, SANITY_IMAGE_ID
    } and network == "none"
    receipt = {
        "schema_version": "aider-rle-docker-sanity-v2",
        "family_id": FAMILY_ID,
        "evidence_class": "docker_sanity" if docker_sanity else "host_iteration",
        "locked_oracle": False,
        "local_family_verified": docker_sanity,
        "owner_hash": _source_hash(Path(__file__)),
        "case_source_hash": _source_hash(CASE_SOURCE),
        "generator_hash": _generator_hash(),
        "family_screen_hash": _source_hash(out / ".state/family-screen.json"),
        "image": image,
        "expected_image": SANITY_IMAGE,
        "network_policy": network,
        "compiler": _run_checked(["c++", "--version"], failure="compiler_identity_failed").stdout.splitlines()[0],
        "compiler_path": shutil.which("c++"),
        "compiler_hash": _source_hash(Path(shutil.which("c++") or "c++")),
        "cmake": _run_checked(["cmake", "--version"], failure="cmake_identity_failed").stdout.splitlines()[0],
        "commands": "owner --force --verify-core --verify; explicit Unix Makefiles; fresh normal and ASan/UBSan",
        "tasks": task_receipts,
        "screen_summary": {
            "prompt_boundary": screen["prompt_boundary"],
            "duplicate_family": screen["duplicate_family"],
            "benchmark_contamination": screen["benchmark_contamination"],
        },
    }
    receipt_path = out / ".state" / (
        "docker-sanity.json" if docker_sanity else "host-oracle-iteration.json"
    )
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if docker_sanity:
        _update_records(
            out,
            status="verified",
            local_status="local_family_verified",
            oracle_evidence={
                "result": "pass",
                "receipt": ".state/docker-sanity.json",
                "evidence_class": "docker_sanity",
                "locked_oracle": False,
                "normal_discovered_tests": 3,
                "sanitizer_discovered_tests": 3,
                "network_policy": "none",
                "image": image,
            },
        )
    else:
        _update_records(
            out,
            status="implemented",
            local_status="not_completed_mandatory_docker_sanity",
            oracle_evidence={
                "result": "host_iteration_pass",
                "receipt": ".state/host-oracle-iteration.json",
            },
        )
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materialize remediated run-length C++ task roots."
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    print(f"Wrote {len(roots)} run-length remediation tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
