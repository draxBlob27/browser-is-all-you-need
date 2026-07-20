"""Materialize and reverify clean-room grid-ownership-mapping replacements."""

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
from dataclasses import replace
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
from w8_biayn.integrations.moonlight_grid_ownership_mapping_cases import (
    CASES,
    NEGATIVE_MUTATIONS,
    GridCase,
)

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/grid-ownership-mapping")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-text-grid-reshaping/grid-ownership-mapping")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-text-grid-reshaping/GLM47_FLASH_AIDER_POLYGLOT_CPP_GRID_OWNERSHIP_MAPPING_CURRICULUM.md"
FAMILY_SPEC = "docs/aider-tasks-spec/aider-text-grid-reshaping/grid-ownership-mapping.md"
FAMILY_ID = "aider-text-grid-reshaping-grid-ownership-v2"
MANIFEST_SCHEMA = "aider-grid-ownership-materialization-v2"
SEMANTIC_NORMALIZER = "grid-ownership-v2-control-flow-9gram"
LEGACY_GENERATOR_REVISION = "sha256:63726f86dc02fdb52884ca04692becc93b16543400d8d28c3c6ac69bb2ea4593"
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
    (
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
    )
)
TASKS = CASES


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha_bytes(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _source_hash(path: Path | None = None) -> str:
    return _sha_bytes((path or Path(__file__)).read_bytes())


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "not_available"
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".state" not in p.parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _negative_source(case: GridCase) -> tuple[str, str]:
    try:
        old, new, reason = NEGATIVE_MUTATIONS[case.task_id]
    except KeyError:
        _fail("invariant_not_enforced", f"missing topic negative: {case.task_id}")
    occurrences = case.reference.count(old)
    if occurrences != 1:
        _fail(
            "invariant_not_enforced",
            f"topic negative mutation count for {case.task_id}: {occurrences}",
        )
    candidate = case.reference.replace(old, new, 1)
    if candidate == case.reference:
        _fail("invariant_not_enforced", f"topic negative unchanged: {case.task_id}")
    return candidate, reason


CMAKE = """cmake_minimum_required(VERSION 3.16)
project(grid_ownership_mapping_v2 LANGUAGES CXX)
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
    target_compile_options(task_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror -Wno-error=misleading-indentation)
  endif()
  add_test(NAME ${name} COMMAND task_${name})
endforeach()
"""


def _remedy_markdown(case: GridCase) -> str:
    old, new, negative_reason = NEGATIVE_MUTATIONS[case.task_id]
    return f"""## Identity

Task ID: `{case.task_id}`; legacy root: `{case.legacy_id}`; task-spec revision: 2; family ID: `{FAMILY_ID}/{case.task_id}`; disposition: `replace`; source inventory: `grid-ownership-clean-room-v2`; license result: repository-authored/pass; generator: `src/w8_biayn/integrations/moonlight_grid_ownership_mapping_aider_tasks.py`; benchmark screen: pending. Selected prompt: `docs/aider-tasks-spec/prompts/remediate-family-reverify.md` with `FAMILY_NAME=grid-ownership-mapping`, `FAMILY_TYPE=aider-text-grid-reshaping`.

## Objective

{case.objective}

## Public API

C++17 namespace `curriculum`; editable order is `{case.task_id}.h`, then `{case.task_id}.cpp`. API: `{case.public_api}`. Inputs and return values are owned values; results preserve the documented deterministic ordering and ties.

## Behavior table

Valid inputs execute the objective and return the documented task-specific report or state. Invalid bounds, dimensions, domains, timestamps, or empty state return the documented false/empty sentinel without partial mutation. Duplicate maxima follow the task-specific tie rule. Ordering, ownership, reachability, and boundary rules follow the task-specific contract. Arithmetic is checked before indexing. The visible test contains the public boundary example; private tests cover empty, singleton, duplicate, ordering, and invalid-input behavior.

## Implementation invariant

Required mechanism: {case.profile}. Required source evidence: {", ".join(f"`{token}`" for token in (case.marker,))}. Forbidden substitutes are the legacy shared legend/count/conflict/primary-metric template, renamed copies of another v2 root, a shared generic grid analyzer that replaces the advertised algorithm, hard-coded answers, and benchmark assets.

## Starter and reference

The task-named header declares the complete API. The task-named source is a coherent incomplete implementation. `.meta/example.cpp` is an independently authored reference that owns and maintains the required mechanism. It does not import legacy renderers or hidden fixtures.

## Tests

The visible executable covers the normal contract. The private executable covers task-specific boundaries and the prior family defect. Deterministic literals and complete observable results are used. The compiling topic negative replaces `{old}` with `{new}` to model “{negative_reason}”; both task tests must execute and at least one must reject it. The named `domain-identifier-renamed-clone`, `constants-policy-clone`, and `opposite-end-selection-clone` controls must compile under the same strict flags, execute both tests, and be rejected by the semantic screen and behavior oracle.

## Files and metadata

Solutions: `{case.task_id}.h`, `{case.task_id}.cpp`. Test: `task_visible_test.cpp`; private test: `.meta/task_hidden_test.cpp`. References: `.meta/example.h`, `.meta/example.cpp`, mapped by suffix and solution order. Docs, tests, metadata, references, CMake, manifests, and receipts remain private. Provenance binds the legacy root, family/profile, prompt, and repository-authored origin.

## Build/oracle

C++17, strict warnings, explicit `Unix Makefiles`, locked `c++`, two CTest targets. Run clean normal and separate fresh ASan/UBSan reference builds in `{SANITY_IMAGE}` with Docker network `none`. Expected discovery is two tests in each mode. The receipt binds the deterministic archive, task/reference/owner hashes, image identity, compiler/CMake versions, commands, and counts.

## Family/contamination

Compare normalized public APIs, references, and tests across all 20 v2 roots, all legacy roots, and all 26 bound official C++ holdouts using `{SEMANTIC_NORMALIZER}`. Family and permanent-holdout decisions remain pending until owner verification passes; no waiver is allowed.

## Optional dataset handoff

`not_requested`. No JSONL, token/mask evidence, split, export, consumer verification, training, or release is authorized.

## Acceptance

Run focused pytest, owner `--verify-core`, and owner `--verify-docker`. Require exact generator regeneration, prompt/role/reference safety, the complete 190-pair seven-dimension matrix, compilation and executed-test rejection of all 20 topic negatives and all three adversarial controls, benchmark separation, and equal positive normal/sanitizer counts. Stable failures include `remedy_spec_incomplete`, `prompt_contract_incomplete`, `invariant_not_enforced`, `duplicate_family`, `negative_fixture_not_rejected`, `benchmark_content_overlap`, `generator_output_drift`, `grader_mount_hash_mismatch`, and `sanitizer_test_count_mismatch`.
"""


def _write_remedies(out: Path, force: bool) -> None:
    remedy = out / ".state" / "remedy"
    for case in CASES:
        markdown = _remedy_markdown(case)
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "family_id_before": "aider-text-grid-reshaping-grid-ownership-v1",
            "family_id_after": f"{FAMILY_ID}/{case.task_id}",
            "tree_hash_before": _tree_hash(LEGACY_ROOT / case.legacy_id),
            "generator_path": "src/w8_biayn/integrations/moonlight_grid_ownership_mapping_aider_tasks.py",
            "generator_revision": LEGACY_GENERATOR_REVISION,
            "selected_prompt": "docs/aider-tasks-spec/prompts/remediate-family-reverify.md",
            "user_inputs": {
                "FAMILY_NAME": "grid-ownership-mapping",
                "FAMILY_TYPE": "aider-text-grid-reshaping",
                "hard_rule": "complete all-pairs logic-and-implementation diversity; rename/policy/opposite-end clones prohibited",
            },
            "finding_ids": [
                "GOM-F1-template-semantic-duplicate",
                "GOM-F2-objective-contract-mismatch",
                "GOM-F3-oracle-evidence-stale",
                "GOM-F4-hard-rule-executable-negative-gap",
            ],
            "disposition": "replace",
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": f".state/remedy/{case.task_id}.md",
            "remedy_spec_hash": _sha_bytes(markdown.encode()),
            "status": "planned",
            "primary_core_objective": "specified",
            "audit_evidence": {
                "legacy_shape": "shared legend/count/unknown/conflict/primary_metric analyzer",
                "duplicate_scope": "20 of 20 legacy roots",
            },
            "dataset_handoff": "not_requested",
        }
        _write(remedy / f"{case.task_id}.md", markdown, force)
        _write(
            remedy / f"{case.task_id}.json",
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            force,
        )


def _refresh_remedy_hard_rule_specs(out: Path) -> None:
    remedy = out / ".state/remedy"
    for case in CASES:
        spec_path = remedy / f"{case.task_id}.md"
        record_path = remedy / f"{case.task_id}.json"
        if not spec_path.is_file() or not record_path.is_file():
            _fail("remedy_spec_incomplete", case.task_id)
        old, new, reason = NEGATIVE_MUTATIONS[case.task_id]
        sentence = (
            f"Hard-rule executable evidence: `.meta/negative_false_substitute.cpp` replaces "
            f"`{old}` with `{new}` to model “{reason}”; the strict Docker build must "
            "succeed, both tests must execute, and CTest must reject it. The domain/identifier, "
            "constants/policy, and opposite-end controls must likewise compile, execute, and fail."
        )
        text = spec_path.read_text(encoding="utf-8")
        text = re.sub(
            r"\nHard-rule executable evidence:.*?(?=\n\n## Files and metadata\n)",
            "",
            text,
            flags=re.S,
        )
        if sentence not in text:
            marker = "\n## Files and metadata\n"
            if marker not in text:
                _fail("remedy_spec_incomplete", case.task_id)
            text = text.replace(marker, f"\n{sentence}\n{marker}", 1)
            _write(spec_path, text, True)
        record = json.loads(record_path.read_text(encoding="utf-8"))
        findings = set(record.get("finding_ids", []))
        findings.add("GOM-F4-hard-rule-executable-negative-gap")
        record["finding_ids"] = sorted(findings)
        record["remedy_spec_hash"] = _sha_bytes(text.encode())
        record["status"] = "planned"
        record["strongest_local_status"] = "planned"
        record["hard_rule_status"] = "pending_execution"
        _write(record_path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def _sync_remedies(out: Path, **updates: object) -> None:
    remedy = out / ".state" / "remedy"
    for case in CASES:
        path = remedy / f"{case.task_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update(updates)
        record["tree_hash_after"] = _tree_hash(out / case.task_id)
        record["generator_revision_after"] = _source_hash()
        record["changed_owner_paths"] = [
            CURRICULUM,
            FAMILY_SPEC,
            "docs/AIDER_TASK_MATERIALIZATION_GUIDE.md",
            "src/w8_biayn/integrations/moonlight_grid_ownership_mapping_aider_tasks.py",
            "src/w8_biayn/integrations/moonlight_grid_ownership_mapping_cases.py",
            "tests/test_moonlight_grid_ownership_mapping_aider_tasks.py",
            "examples/slime/moonlight_cpp_perf/prepare_grid_ownership_mapping_aider_tasks.sh",
        ]
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if not (out / ".state/remedy").is_dir():
        _write_remedies(out, force)
    _refresh_remedy_hard_rule_specs(out)
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        negative_source, negative_reason = _negative_source(case)
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
            "curriculum_document": CURRICULUM,
            "family_specification": FAMILY_SPEC,
            "curriculum_task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "family_id": FAMILY_ID,
            "semantic_profile": case.profile,
            "origin": "newly authored in-repository clean-room replacement",
            "license": "repository-authored",
            "status": "local task artifact; not admitted SFT data",
            "version": 2,
            "benchmark_separation": "Independent API, owned state, algorithm, and tests; official Aider C++ roots remain permanent holdouts.",
        }
        files = {
            ".docs/introduction.md": f"# {case.title}\n\n{case.objective}\n",
            ".docs/instructions.md": case.instructions,
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": f'[visible]\ndescription = "normal {case.profile} behavior and public boundary"\n\n[hidden]\ndescription = "invalid, empty, duplicate, ordering, tie, and task-specific mechanism regression"\n\n[negative]\ndescription = "{negative_reason}; source must compile and both tests must reject it"\n',
            "task.h": case.header,
            "task.cpp": case.starter,
            ".meta/example.h": case.header,
            ".meta/example.cpp": case.reference,
            ".meta/negative_false_substitute.cpp": negative_source,
            "task_visible_test.cpp": case.visible_test,
            ".meta/task_hidden_test.cpp": case.hidden_test,
            "CMakeLists.txt": CMAKE,
        }
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    _write_hard_rule_controls(out, force)
    return tuple(roots)


def _safe_relative(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not value:
        _fail("unsafe_path", value)
    return path.as_posix()


def _whole_format_code(root: Path, response: str) -> str | None:
    task = load_task(root)
    try:
        blocks = parse_whole_file_blocks(response)
    except WholeFormatError:
        return "whole_format_failed"
    return None if set(blocks) == set(task.editable_files) else "whole_format_failed"


def _normalized_code_tokens(content: str) -> list[str]:
    content = re.sub(r"/\*.*?\*/|//[^\n]*", " ", content, flags=re.S)
    content = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", content)
    raw = re.findall(r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]", content)
    keywords = {
        "if",
        "else",
        "for",
        "while",
        "return",
        "class",
        "struct",
        "const",
        "auto",
        "bool",
        "int",
        "long",
        "void",
        "true",
        "false",
        "public",
        "private",
        "namespace",
        "std",
        "vector",
        "deque",
        "queue",
        "priority_queue",
        "optional",
        "array",
        "unique_ptr",
        "shared_ptr",
    }
    return [
        token if token in keywords or not re.match(r"[A-Za-z_]", token) else "ID" for token in raw
    ]


def _ngrams(tokens: list[str], width: int = 9) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + width]) for i in range(max(0, len(tokens) - width + 1))}


def _semantic_signatures(cases: Sequence[GridCase] | None = None) -> dict[str, str]:
    selected = tuple(cases or CASES)
    signatures: dict[str, str] = {}
    fingerprints: dict[str, set[tuple[str, ...]]] = {}
    for case in selected:
        mechanism_source = case.header + "\n" + case.reference
        if case.marker not in mechanism_source or any(
            token not in mechanism_source for token in (case.marker,)
        ):
            _fail("invariant_not_enforced", f"missing-mechanism-token: {case.task_id}")
        tokens = _normalized_code_tokens(
            case.header + "\n" + case.reference + "\n" + case.visible_test + "\n" + case.hidden_test
        )
        signature = _sha_bytes(" ".join(tokens).encode())
        grams = _ngrams(tokens)
        for other, other_grams in fingerprints.items():
            denominator = min(len(grams), len(other_grams))
            similarity = len(grams & other_grams) / denominator if denominator else 1.0
            if similarity >= 0.78:
                _fail("duplicate_family", f"{case.task_id} resembles {other}: {similarity:.3f}")
        fingerprints[case.task_id] = grams
        signatures[case.task_id] = signature
    if len({case.profile for case in selected}) != len(selected) or len(
        {case.public_api for case in selected}
    ) != len(selected):
        _fail("duplicate_family", "profiles and public APIs must be one-to-one")
    return signatures


def _artifact_family_screen(out: Path) -> tuple[dict[str, str], dict[str, object]]:
    signatures: dict[str, str] = {}
    fingerprints: dict[str, set[tuple[str, ...]]] = {}
    strongest: dict[str, object] = {"left": None, "right": None, "containment": 0.0}
    comparisons = 0
    for case in sorted(CASES, key=lambda item: item.task_id):
        root = out / case.task_id
        header = (root / f"{case.task_id}.h").read_text(encoding="utf-8")
        reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
        visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
        hidden = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
        negative = (root / ".meta/negative_false_substitute.cpp").read_text(encoding="utf-8")
        docs = (root / ".docs/instructions.md").read_text(encoding="utf-8")
        mechanism_source = header + "\n" + reference
        if case.marker not in mechanism_source or any(
            token not in mechanism_source for token in (case.marker,)
        ):
            _fail("invariant_not_enforced", f"emitted artifact lacks mechanism: {case.task_id}")
        tokens = _normalized_code_tokens(docs + header + reference + visible + hidden + negative)
        grams = _ngrams(tokens)
        signatures[case.task_id] = _sha_bytes(" ".join(tokens).encode())
        for other, other_grams in fingerprints.items():
            comparisons += 1
            denominator = min(len(grams), len(other_grams))
            similarity = len(grams & other_grams) / denominator if denominator else 1.0
            if similarity > float(strongest["containment"]):
                strongest = {
                    "left": other,
                    "right": case.task_id,
                    "containment": round(similarity, 6),
                }
            if similarity >= 0.78:
                _fail(
                    "duplicate_family",
                    f"emitted {case.task_id} resembles {other}: {similarity:.3f}",
                )
        fingerprints[case.task_id] = grams
    expected = len(CASES) * (len(CASES) - 1) // 2
    if comparisons != expected:
        _fail("duplicate_family", f"all-pairs incomplete: {comparisons} != {expected}")
    return signatures, {
        "status": "pass",
        "normalizer": SEMANTIC_NORMALIZER,
        "comparison_scope": "emitted docs, public API, reference, visible/private tests, and topic negative source",
        "pair_count": comparisons,
        "threshold": 0.78,
        "strongest": strongest,
    }


def _token_containment(left: list[str], right: list[str]) -> float:
    left_grams = _ngrams(left)
    right_grams = _ngrams(right)
    denominator = min(len(left_grams), len(right_grams))
    return len(left_grams & right_grams) / denominator if denominator else 1.0


def _hard_rule_pair_matrix(out: Path) -> dict[str, object]:
    emitted: dict[str, dict[str, list[str]]] = {}
    markers = {case.task_id: case.marker for case in CASES}
    for case in CASES:
        root = out / case.task_id
        emitted[case.task_id] = {
            "public_api": _normalized_code_tokens(
                (root / f"{case.task_id}.h").read_text(encoding="utf-8")
            ),
            "behavior_contract": _normalized_code_tokens(
                (root / ".docs/instructions.md").read_text(encoding="utf-8")
            ),
            "reference_control_flow": _normalized_code_tokens(
                (root / ".meta/example.cpp").read_text(encoding="utf-8")
            ),
            "visible_oracle": _normalized_code_tokens(
                (root / "task_visible_test.cpp").read_text(encoding="utf-8")
            ),
            "private_oracle": _normalized_code_tokens(
                (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
            ),
            "topic_negative": _normalized_code_tokens(
                (root / ".meta/negative_false_substitute.cpp").read_text(encoding="utf-8")
            ),
        }
    pairs: list[dict[str, object]] = []
    task_ids = sorted(emitted)
    dimensions = tuple(next(iter(emitted.values())))
    for index, left_id in enumerate(task_ids):
        for right_id in task_ids[index + 1 :]:
            evidence: dict[str, object] = {
                "left": left_id,
                "right": right_id,
                "mechanism_marker_distinct": markers[left_id] != markers[right_id],
            }
            if not evidence["mechanism_marker_distinct"]:
                _fail("duplicate_family", f"shared mechanism marker: {left_id}, {right_id}")
            for dimension in dimensions:
                left = emitted[left_id][dimension]
                right = emitted[right_id][dimension]
                distinct = left != right
                containment = round(_token_containment(left, right), 6)
                evidence[f"{dimension}_distinct"] = distinct
                evidence[f"{dimension}_containment"] = containment
                if not distinct:
                    _fail(
                        "duplicate_family",
                        f"hard-rule {dimension} clone: {left_id}, {right_id}",
                    )
            pairs.append(evidence)
    expected = len(CASES) * (len(CASES) - 1) // 2
    if len(pairs) != expected:
        _fail("duplicate_family", f"hard-rule all-pairs incomplete: {len(pairs)} != {expected}")
    return {
        "status": "pending_execution",
        "pair_count": len(pairs),
        "expected_pair_count": expected,
        "dimensions": [
            "public API",
            "behavior/invalid/boundary contract",
            "owned algorithm and reference control flow",
            "visible deterministic oracle",
            "private deterministic oracle",
            "topic-specific negative fixture",
            "mechanism/mutation-selection marker",
        ],
        "evidence_source": "actual emitted docs, task-named header, reference, visible/private tests, and false-substitute source",
        "pairs": pairs,
    }


def _replace_case_text(
    case: GridCase,
    *,
    task_id: str,
    legacy_id: str,
    replacements: Sequence[tuple[str, str]],
) -> GridCase:
    fields = (
        "title",
        "profile",
        "objective",
        "public_api",
        "marker",
        "instructions",
        "header",
        "starter",
        "reference",
        "visible_test",
        "hidden_test",
    )
    updates: dict[str, str] = {"task_id": task_id, "legacy_id": legacy_id}
    for field in fields:
        value = getattr(case, field)
        for old, new in replacements:
            value = value.replace(old, new)
        updates[field] = value
    return replace(case, **updates)


def _adversarial_cases() -> dict[str, GridCase]:
    base = CASES[0]
    domain = _replace_case_text(
        base,
        task_id="domain-identifier-renamed-clone",
        legacy_id="synthetic-domain",
        replacements=(
            ("GatePlan", "SlotPlan"),
            ("plan_gates", "schedule_slots"),
            ("Flight", "Job"),
            ("flights", "jobs"),
            ("flight", "job"),
            ("Gate", "Slot"),
            ("gates", "slots"),
            ("gate", "slot"),
            ("arrival", "start"),
            ("departure", "finish"),
            ("assignment", "allocation"),
            ("unassigned", "unplaced"),
            ("closed", "disabled"),
            ("busy", "occupied"),
            ("size", "tier"),
            ("cap", "limit"),
        ),
    )
    domain = replace(
        domain,
        reference=domain.reference.replace("occupied[name]<=f.start", "occupied[name]<f.start", 1),
    )
    constants = _replace_case_text(
        base,
        task_id="constants-policy-clone",
        legacy_id="synthetic-constants",
        replacements=(("SML", "ABC"), ("'S'", "'A'"), ("'M'", "'B'"), ("'L'", "'C'")),
    )
    constants = replace(
        constants,
        reference=constants.reference.replace("busy[name]<=f.arrival", "busy[name]<f.arrival", 1),
    )
    old_loop = "for(auto [name,size]:cap)if(!shut.count(name)&&rank(size)>=rank(f.size)&&busy[name]<=f.arrival){pick=name;break;}"
    new_loop = "for(auto it=cap.rbegin();it!=cap.rend();++it){auto [name,size]=*it;if(!shut.count(name)&&rank(size)>=rank(f.size)&&busy[name]<=f.arrival){pick=name;break;}}"
    if base.reference.count(old_loop) != 1:
        _fail("invariant_not_enforced", "opposite-end control source drift")
    opposite = replace(
        base,
        task_id="opposite-end-selection-clone",
        legacy_id="synthetic-opposite",
        reference=base.reference.replace(old_loop, new_loop, 1),
    )
    return {
        "domain-identifier-renamed-clone": domain,
        "constants-policy-clone": constants,
        "opposite-end-selection-clone": opposite,
    }


def _write_hard_rule_controls(out: Path, force: bool) -> None:
    controls_root = out / ".state/hard-rule-controls"
    manifest: dict[str, object] = {
        "schema_version": "grid-ownership-hard-rule-controls-v1",
        "controls": {},
    }
    for name, case in _adversarial_cases().items():
        root = controls_root / name
        files = {
            "task.h": case.header,
            "candidate.cpp": case.reference,
            "task_visible_test.cpp": case.visible_test,
            ".meta/task_hidden_test.cpp": case.hidden_test,
            "CMakeLists.txt": CMAKE,
        }
        for relative, content in files.items():
            _write(root / relative, content, force)
        manifest["controls"][name] = {
            "source_hash": _sha_bytes(case.reference.encode()),
            "header_hash": _sha_bytes(case.header.encode()),
            "expected_compile": "pass",
            "expected_ctest": "reject",
            "expected_semantic_screen": "duplicate_family",
        }
    _write(
        controls_root / "manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        force,
    )


def _run_adversarial_controls() -> dict[str, str]:
    base = CASES[0]
    controls = {
        "legacy-template-clone": replace(
            base, task_id="legacy-template-clone", legacy_id="synthetic-legacy"
        ),
        **_adversarial_cases(),
    }
    outcomes: dict[str, str] = {}
    for name, clone in controls.items():
        try:
            _semantic_signatures((base, clone))
        except RuntimeError as error:
            if "duplicate_family" not in str(error):
                raise
            outcomes[name] = "rejected:duplicate_family"
        else:
            _fail("duplicate_family", f"adversarial control passed: {name}")
    missing = replace(
        base,
        task_id="missing-mechanism-token",
        marker="never_present_token",
    )
    try:
        _semantic_signatures((missing,))
    except RuntimeError as error:
        if "invariant_not_enforced" not in str(error):
            raise
        outcomes["missing-mechanism-token"] = "rejected:invariant_not_enforced"
    else:
        _fail("invariant_not_enforced", "missing-mechanism-token control passed")
    return outcomes


def _semantic_holdout_screen(holdout_root: Path = DEFAULT_HOLDOUT_ROOT) -> dict[str, object]:
    if not holdout_root.is_dir():
        _fail("benchmark_screen_not_completed", str(holdout_root))
    holdouts: dict[str, set[tuple[str, ...]]] = {}
    inventory = hashlib.sha256()
    for root in sorted(path for path in holdout_root.iterdir() if path.is_dir()):
        corpus = ""
        for path in sorted(
            p
            for p in root.rglob("*")
            if p.is_file() and p.suffix in {".h", ".hpp", ".cpp"} and "catch" not in p.name
        ):
            inventory.update(path.relative_to(holdout_root).as_posix().encode())
            inventory.update(path.read_bytes())
            corpus += "\n" + path.read_text(encoding="utf-8", errors="replace")
        holdouts[root.name] = _ngrams(_normalized_code_tokens(corpus))
    strongest: dict[str, object] = {"candidate": None, "holdout": None, "containment": 0.0}
    for case in CASES:
        candidate = _ngrams(
            _normalized_code_tokens(
                case.header + case.reference + case.visible_test + case.hidden_test
            )
        )
        for slug, grams in holdouts.items():
            denominator = min(len(candidate), len(grams))
            score = len(candidate & grams) / denominator if denominator else 0.0
            if score > float(strongest["containment"]):
                strongest = {
                    "candidate": case.task_id,
                    "holdout": slug,
                    "containment": round(score, 6),
                }
            if score >= 0.60:
                _fail("benchmark_content_overlap", f"{case.task_id} resembles {slug}: {score:.3f}")
    return {
        "status": "pass",
        "normalizer": SEMANTIC_NORMALIZER,
        "source_inventory": f"sha256:{inventory.hexdigest()}",
        "holdout_root_count": len(holdouts),
        "comparison_scope": "public API, reference, visible and hidden tests",
        "threshold": 0.60,
        "strongest": strongest,
    }


def _benchmark_screen(root: Path) -> None:
    corpus = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(root.rglob("*")) if path.is_file()
    )
    normalized = corpus.lower()
    for slug in OFFICIAL_AIDER_CPP_HOLDOUTS:
        if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", normalized):
            _fail("benchmark_id_overlap", slug)
    for forbidden in ("aider-ai/polyglot", "exercism c++ exercise"):
        if forbidden in normalized:
            _fail("benchmark_content_overlap", forbidden)


def _verify_remedies(out: Path) -> None:
    remedy = out / ".state" / "remedy"
    expected = {case.task_id for case in CASES}
    records = {path.stem: path for path in remedy.glob("*.json")} if remedy.is_dir() else {}
    if set(records) != expected:
        _fail("remedy_spec_incomplete", "one record per replacement is required")
    for task_id, path in records.items():
        record = json.loads(path.read_text(encoding="utf-8"))
        spec = remedy / f"{task_id}.md"
        if record.get("disposition") != "replace" or not spec.is_file():
            _fail("remedy_disposition_conflict", task_id)
        text = spec.read_text(encoding="utf-8")
        positions = [text.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if (
            -1 in positions
            or positions != sorted(positions)
            or record.get("remedy_spec_hash") != _sha_bytes(text.encode())
        ):
            _fail("remedy_spec_incomplete", task_id)


def verify_core(out: Path, *, require_remedy: bool = True) -> None:
    expected = {case.task_id for case in CASES}
    actual = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", f"expected {len(expected)} roots, found {len(actual)}")
    if require_remedy:
        _verify_remedies(out)
    with tempfile.TemporaryDirectory(prefix="grid-ownership-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for task_id in expected:
            if _tree_hash(out / task_id) != _tree_hash(fresh / task_id):
                _fail("generator_output_drift", task_id)
    _semantic_signatures()
    signatures, artifact_family = _artifact_family_screen(out)
    hard_rule = _hard_rule_pair_matrix(out)
    controls = _run_adversarial_controls()
    holdout = _semantic_holdout_screen()
    manifest_tasks = []
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        files = config["files"]
        solution = [_safe_relative(item) for item in files["solution"]]
        tests = [_safe_relative(item) for item in files["test"]]
        examples = [_safe_relative(item) for item in files["example"]]
        if len(solution) != 2 or len(examples) != 2 or set(solution) & (set(tests) | set(examples)):
            _fail("reference_map_failed", case.task_id)
        if any(
            name.startswith((".meta/", ".docs/")) or name == "CMakeLists.txt" for name in solution
        ):
            _fail("unsafe_path", case.task_id)
        if any(not (root / name).is_file() for name in [*solution, *tests, *examples]):
            _fail("reference_map_failed", case.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        if any(
            name in prompt
            for name in [
                *tests,
                *examples,
                "CMakeLists.txt",
                ".meta/provenance.json",
                ".meta/task_hidden_test.cpp",
                ".meta/negative_false_substitute.cpp",
            ]
        ):
            _fail("prompt_contract_incomplete", case.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if _whole_format_code(root, answer) is not None:
            _fail("target_reference_mismatch", case.task_id)
        malformed = (
            f"{task.editable_files[0]}\n```cpp\n// missing\n```\n",
            answer + "\nunknown.cpp\n```cpp\n// forbidden\n```\n",
            "prose\n" + answer,
        )
        if any(_whole_format_code(root, value) != "whole_format_failed" for value in malformed):
            _fail("whole_format_failed", case.task_id)
        _benchmark_screen(root)
        manifest_tasks.append(
            {
                "task_id": case.task_id,
                "legacy_task_id": case.legacy_id,
                "tree_hash": _tree_hash(root),
                "semantic_profile": case.profile,
                "semantic_signature": signatures[case.task_id],
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
        "tasks": manifest_tasks,
        "screen": {
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
            "negative_fixtures": controls,
            "duplicate_family": "pass",
            "artifact_family": artifact_family,
            "hard_rule": hard_rule,
            "benchmark_contamination": "pass",
            "semantic_holdout": holdout,
        },
    }
    _write(
        out / ".state/materialization-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        True,
    )
    if require_remedy:
        _sync_remedies(
            out,
            status="implemented",
            primary_core_objective="achieved",
            prompt_boundary="pass",
            reference_mapping="pass",
            family_screen=artifact_family,
            benchmark_screen="pass",
            semantic_holdout_screen=holdout,
            negative_fixtures=controls,
            hard_rule_status="pending_execution",
            hard_rule_evidence={
                "status": "pending_execution",
                "pair_count": hard_rule["pair_count"],
                "dimensions": hard_rule["dimensions"],
                "matrix_path": ".state/materialization-manifest.json",
            },
            strongest_local_status="implemented",
        )


def _deterministic_archive(out: Path, destination: Path) -> str:
    with tarfile.open(destination, "w") as archive:
        for case in sorted(CASES, key=lambda item: item.task_id):
            root = out / case.task_id
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                relative = Path(case.task_id) / path.relative_to(root)
                info = tarfile.TarInfo(relative.as_posix())
                data = path.read_bytes()
                info.size = len(data)
                info.mode = 0o644
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(data))
        controls_root = out / ".state/hard-rule-controls"
        for path in sorted(p for p in controls_root.rglob("*") if p.is_file()):
            relative = Path(".hard-rule-controls") / path.relative_to(controls_root)
            info = tarfile.TarInfo(relative.as_posix())
            data = path.read_bytes()
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(data))
    return _sha_bytes(destination.read_bytes())


def verify_docker(out: Path, image: str = SANITY_IMAGE) -> None:
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
    with tempfile.TemporaryDirectory(prefix="grid-ownership-docker-") as temporary:
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
  negative_build="/tmp/build-${task}-topic-negative"
  cmake -S "$root" -B "$negative_build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/negative_false_substitute.cpp"
  cmake --build "$negative_build" --parallel 2
  negative_count=$(ctest --test-dir "$negative_build" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
  test -n "$negative_count" && test "$negative_count" -gt 0
  set +e
  ctest --test-dir "$negative_build" --output-on-failure
  negative_exit=$?
  set -e
  test "$negative_exit" -ne 0
  printf '%s\t%s\t%s\n' "$task" "$negative_count" "$negative_exit" >> /result/topic-negative.tsv
done
for root in /tmp/family/.hard-rule-controls/*; do
  test -d "$root" || continue
  control=$(basename "$root")
  build="/tmp/build-control-${control}"
  cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/candidate.cpp"
  cmake --build "$build" --parallel 2
  count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
  test -n "$count" && test "$count" -gt 0
  set +e
  ctest --test-dir "$build" --output-on-failure
  control_exit=$?
  set -e
  test "$control_exit" -ne 0
  printf '%s\t%s\t%s\n' "$control" "$count" "$control_exit" >> /result/adversarial-controls.tsv
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
            _fail("docker_sanity_failed", run.stdout[-4000:])
        mounted_hash = (results / "archive.sha256").read_text(encoding="utf-8").strip()
        if mounted_hash != archive_hash:
            _fail("grader_mount_hash_mismatch", f"owner={archive_hash} docker={mounted_hash}")
        counts: dict[str, dict[str, int]] = {}
        for line in (results / "counts.tsv").read_text(encoding="utf-8").splitlines():
            task_id, mode, raw = line.split("\t")
            counts.setdefault(task_id, {})[mode] = int(raw)
        if set(counts) != {case.task_id for case in CASES}:
            _fail("test_discovery_failed", "incomplete Docker receipt")
        for task_id, modes in counts.items():
            if modes.get("normal", 0) <= 0 or modes.get("normal") != modes.get("sanitizer"):
                _fail("sanitizer_test_count_mismatch", task_id)
        topic_negatives: dict[str, dict[str, object]] = {}
        for line in (results / "topic-negative.tsv").read_text(encoding="utf-8").splitlines():
            task_id, raw_count, raw_exit = line.split("\t")
            topic_negatives[task_id] = {
                "compiled": True,
                "discovered_tests": int(raw_count),
                "ctest_exit": int(raw_exit),
                "rejected_by_executed_tests": int(raw_exit) != 0,
            }
        if set(topic_negatives) != {case.task_id for case in CASES}:
            _fail("negative_fixture_not_rejected", "incomplete topic-negative receipt")
        for task_id, outcome in topic_negatives.items():
            if outcome["discovered_tests"] <= 0 or not outcome["rejected_by_executed_tests"]:
                _fail("negative_fixture_not_rejected", task_id)
        adversarial_execution: dict[str, dict[str, object]] = {}
        for line in (results / "adversarial-controls.tsv").read_text(encoding="utf-8").splitlines():
            name, raw_count, raw_exit = line.split("\t")
            adversarial_execution[name] = {
                "compiled": True,
                "discovered_tests": int(raw_count),
                "ctest_exit": int(raw_exit),
                "rejected_by_executed_tests": int(raw_exit) != 0,
                "semantic_screen": "rejected:duplicate_family",
            }
        expected_controls = set(_adversarial_cases())
        if set(adversarial_execution) != expected_controls:
            _fail("negative_fixture_not_rejected", "incomplete adversarial-control receipt")
        for name, outcome in adversarial_execution.items():
            if outcome["discovered_tests"] <= 0 or not outcome["rejected_by_executed_tests"]:
                _fail("negative_fixture_not_rejected", name)
        manifest_path = out / ".state/materialization-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        hard_rule = manifest["screen"]["hard_rule"]
        hard_rule["status"] = "pass"
        hard_rule["topic_negative_execution"] = topic_negatives
        hard_rule["adversarial_control_execution"] = adversarial_execution
        receipt = {
            "schema_version": "aider-grid-ownership-docker-sanity-v3",
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
            "topic_negative_hashes": {
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
                "topic_negative": "strict Unix Makefiles build; both task tests execute and must reject",
                "adversarial_controls": "strict Unix Makefiles build; both control tests execute and semantic screen must reject",
            },
            "test_counts": counts,
            "hard_rule": {
                "pair_count": hard_rule["pair_count"],
                "dimensions": hard_rule["dimensions"],
                "topic_negative_execution": topic_negatives,
                "adversarial_control_execution": adversarial_execution,
                "semantic_controls": manifest["screen"]["negative_fixtures"],
            },
        }
        receipt_path = out / ".state/oracle-receipt.json"
        _write(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        receipt_hash = _source_hash(receipt_path)
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
            },
            hard_rule_status="pass",
            hard_rule_evidence={
                "status": "pass",
                "pair_count": hard_rule["pair_count"],
                "dimensions": hard_rule["dimensions"],
                "matrix_path": ".state/materialization-manifest.json",
                "adversarial_controls": adversarial_execution,
            },
            strongest_local_status="local_family_verified",
        )
        for case in CASES:
            record_path = out / ".state/remedy" / f"{case.task_id}.json"
            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["topic_negative_fixture"] = topic_negatives[case.task_id]
            record["topic_negative_fixture"]["source"] = ".meta/negative_false_substitute.cpp"
            _write(record_path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)
        manifest.update(
            {
                "status": "local_family_verified",
                "hard_rule_status": "pass",
                "oracle_receipt": ".state/oracle-receipt.json",
                "oracle_receipt_hash": receipt_hash,
                "evidence_class": "docker_sanity",
                "locked_oracle": False,
            }
        )
        _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-docker", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify_docker:
        verify_docker(args.out, args.image)
    print(
        f"Wrote {len(roots)} algorithmically distinct grid-ownership-mapping replacements under {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
