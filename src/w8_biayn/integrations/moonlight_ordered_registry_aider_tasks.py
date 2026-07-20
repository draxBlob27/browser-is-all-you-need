"""Materialize and reverify the ordered-registry v2 Aider task family."""

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
from w8_biayn.integrations.moonlight_ordered_registry_cases import CASES, Case
from w8_biayn.integrations.moonlight_ordered_registry_verification_cases import (
    CASES as VERIFICATION_CASES,
    VerificationCase,
)

TASKS = CASES


DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/ordered-registry")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dsa/ordered-registry")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_ORDERED_REGISTRY_CURRICULUM.md"
PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
BENCHMARK_MANIFEST = Path("manifests/aider_sft/aider-polyglot-cpp-26.json")
UPSTREAM_CPP = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
FAMILY_ID = "aider-dsa-ordered-registry-v2"
MANIFEST_SCHEMA = "ordered-registry-materialization-v2"
NORMALIZER_VERSION = "ordered-registry-contract-v3"
EXPECTED_TASK_COUNT = 20
DESIGNATED_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
OWNER_PATHS = (
    Path(__file__),
    Path(__file__).with_name("moonlight_ordered_registry_cases.py"),
    Path(__file__).with_name("moonlight_ordered_registry_verification_cases.py"),
    Path(CURRICULUM),
    Path("docs/aider-tasks-spec/aider-dsa/ordered-registry.md"),
    Path("docs/AIDER_TASK_MATERIALIZATION_GUIDE.md"),
    Path(PROMPT),
    Path("docs/aider-tasks-spec/verify-and-remedy.md"),
    Path(".agents/skills/aider-task-family-remediation/SKILL.md"),
    Path("tests/test_moonlight_ordered_registry_aider_tasks.py"),
)
REMEDY_HEADINGS = (
    "Identity", "Objective", "Public API", "Behavior table", "Implementation invariant",
    "Starter and reference", "Tests", "Files and metadata", "Build/oracle",
    "Family/contamination", "Optional dataset handoff", "Acceptance",
)


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "missing"
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode() + b"\0" + path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _family_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for case in CASES:
        digest.update(case.task_id.encode() + b"\0" + _tree_hash(root / case.task_id).encode() + b"\n")
    return f"sha256:{digest.hexdigest()}"


def _owner_hash() -> str:
    digest = hashlib.sha256()
    for path in OWNER_PATHS:
        digest.update(path.name.encode() + b"\0" + path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _instructions(case: Case) -> str:
    rules = {
        "registry-audit-retention": "Expiry equality is eligible; legal holds block deletion and failed erasure changes nothing.",
        "customs-clearance-workflow": "Only filed-to-inspected-to-cleared transitions are legal; pending results exclude cleared declarations and order by deadline then ID.",
        "triage-priority-board": "Severity is 1 through 5; treatment removes severity-descending, arrival-ascending, ID-ascending priority while reprioritization preserves arrival.",
        "session-seat-waitlist": "Requests seat until capacity, then wait by request time and ID; cancelling a seat promotes the queue head and transfer is atomic.",
        "device-heartbeat-index": "Heartbeats never go backward, ring moves preserve last-seen time, and stale means strictly before the cutoff.",
        "rollout-token-ring": "Tokens are 0 through 359; routing selects the first token at or clockwise after account modulo 360 and wraps to the smallest token.",
        "gate-conflict-scheduler": "Gate compatibility is explicit; stays are half-open and may touch; conflicting moves fail atomically.",
        "dish-allergen-catalog": "Allergens are canonical sets; safe dishes have empty intersection with the forbidden set and are returned lexically.",
        "proposal-review-matcher": "Conflicts and reviewer assignments are distinct relations; duplicate edges reject and deficits order by count then proposal ID.",
        "room-stay-calendar": "Bookings use half-open intervals, choose the lowest available compatible room, and retain multiple non-overlapping stays per room.",
        "service-incident-queue": "Escalation is monotonic, resolution removes the incident, and service priority is severity descending then opened time and ID.",
        "copy-loan-ledger": "One physical copy has one active borrower; renewal moves due dates strictly forward; overdue is due strictly before today.",
        "crew-workload-ledger": "Capacity is the sum of effort rather than order count; reassignment preserves effort and rolls back when the destination is full.",
        "asset-custody-history": "Transfers append at strictly increasing timestamps; history is never overwritten and owner-at selects the final event not later than the query.",
        "permit-expiry-wheel": "Issue and extension delays are 1 through the horizon; extension leaves a stale bucket entry, so advance must remove only permits whose current absolute due tick is reached.",
        "shipping-rate-resolver": "Inclusive weight bands may overlap; choose cost, then narrower width, then contract ID.",
        "billing-cycle-counter": "Every active account belongs to one plan/cycle cell; changes and cancellation keep the two-dimensional snapshot reconciled.",
        "sla-escalation-heap": "The indexed heap's observable priority front orders priority descending then deadline, opened time, and ID; breached candidates must also have deadline at most now.",
        "vaccine-lot-fefo": "Allocation ignores expired lots, plans across lots by expiry and ID, and commits nothing on a dose shortfall.",
        "warehouse-batch-splitter": "Zone load is summed units; split conserves units, compatible merge restores them, and moves are atomic.",
    }[case.task_id]
    return (
        f"# Instructions\n\nImplement `{case.class_name}`. {case.objective} {rules} "
        "Inputs outside the declared domain and absent or duplicate identities reject without changing valid state. "
        "Use the exact declarations in the starter header. This is local candidate material, not a dataset release.\n"
    )


CMAKE = """cmake_minimum_required(VERSION 3.16)
project(ordered_registry_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
add_executable(task_trace "${TASK_SOURCE}" .meta/task_trace_test.cpp)
foreach(target task_visible task_hidden task_trace)
 target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
 if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
 endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_test(NAME model_trace COMMAND task_trace)
"""


def _negative_source(case: Case, verification: VerificationCase | None = None) -> str:
    verification = verification or VERIFICATION_CASES[case.task_id]
    if case.reference.count(verification.false_old) != 1:
        raise RuntimeError(f"negative_fixture_source_drift:{case.task_id}:{verification.false_name}")
    source = case.reference.replace(verification.false_old, verification.false_new)
    if source == case.reference:
        raise RuntimeError(f"negative_fixture_source_drift:{case.task_id}:{verification.false_name}")
    return source


def _rendered_negative_source(case: Case) -> str:
    return _negative_source(case).replace('"task.h"', f'"{case.task_id}.h"')


def _remedy_spec(case: Case) -> str:
    verification = VERIFICATION_CASES[case.task_id]
    disposition = "repair-in-place" if case.legacy_id == "registry-audit-retention" else "replace"
    return f"""## Identity
Legacy `{case.legacy_id}`; replacement `{case.task_id}`; task-spec revision 2; family `{FAMILY_ID}`; disposition `{disposition}`; generator `{Path(__file__).as_posix()}`; clean-room/license pass; benchmark screen required.
## Objective
{case.objective}
## Public API
```cpp
{case.header.strip()}
```
Editable order is `{case.task_id}.h`, `{case.task_id}.cpp`; namespace is `curriculum`; values are owned by the class.
## Behavior table
The generated instructions define valid, invalid, duplicate, absent, empty, ordering, tie, and boundary behavior for every method. Failed mutations are atomic. Diversity boundary: {verification.boundary}.
## Implementation invariant
State/algorithm: {verification.state}. Mutation: {verification.mutation}. Selection: {verification.selection}. Required source markers: {', '.join(case.core_markers)}. Legacy generic entry state and declared forbidden markers are prohibited.
## Starter and reference
The starter is coherent stubs for the complete API. The independent reference implements `{verification.logic}` without the legacy renderer. The false substitute `{verification.false_name}` is generated from one exact source mutation and must compile before tests reject it.
## Tests
Visible examples cover the public boundary. Private examples cover failure atomicity. `.meta/task_trace_test.cpp` uses an independent vector/value model, compares every return and complete public ordering after every operation, and invokes every public operation class. Trace hash: `{_sha(verification.trace.encode())}`. Negative fixture: `{verification.false_name}`.
## Files and metadata
Docs and exactly two slug-named solution files are prompt-visible. Visible/private/model-trace tests, CMake, provenance, example reference, and negative fixture are private. Reference order maps one-to-one to solution order; no support bundle is used.
## Build/oracle
C++17, Unix Makefiles, strict warnings; designated image `{DESIGNATED_IMAGE}`; network none. Require three discovered tests in normal and a fresh ASan/UBSan build, equal positive counts, reference hashes, owner hash, owner/Docker family hashes, commands, compiler, and CMake in the receipt.
## Family/contamination
Run `{NORMALIZER_VERSION}` over all {EXPECTED_TASK_COUNT} proposed docs/APIs/source/tests and all 26 bound permanent holdouts after removing nouns/literals while preserving API arity, control flow, invariants, and assertions. A normalized similarity of 0.94 or higher is `duplicate_family`/benchmark overlap.
## Optional dataset handoff
`not_requested`; no rows, tokens, masks, split, export, producer, or consumer evidence belongs to local remediation.
## Acceptance
Focused tests, `--verify-core`, all compiled negative fixtures, and network-disabled Docker `--verify` must pass. Stable failures include `family_count_out_of_bounds`, `duplicate_family`, `negative_fixture_source_drift`, `invariant_not_enforced`, and `grader_mount_hash_mismatch`.
"""


def _write_planned_remedies(out: Path) -> None:
    remedy_root = out / ".state/remedy"
    expected = {case.legacy_id for case in CASES}
    if remedy_root.is_dir():
        for path in remedy_root.iterdir():
            if path.is_file() and path.suffix in {".json", ".md"} and path.stem not in expected:
                path.unlink()
    for case in CASES:
        spec = _remedy_spec(case)
        existing_path = remedy_root / f"{case.legacy_id}.json"
        existing = json.loads(existing_path.read_text(encoding="utf-8")) if existing_path.is_file() else {}
        record = {
            "benchmark_screen": "pending",
            "disposition": "repair-in-place" if case.legacy_id == "registry-audit-retention" else "replace",
            "family_id_before": "aider-dsa-ordered-registry-v1",
            "finding_ids": ["OR-001", "OR-002", "OR-003"],
            "generator_path": Path(__file__).as_posix(),
            "generator_revision": _owner_hash(),
            "license_screen": "pass",
            "primary_core_objective": "not_achieved",
            "remedy_spec_hash": _sha(spec.encode()),
            "remedy_spec_path": f".state/remedy/{case.legacy_id}.md",
            "replacement_task_id": case.task_id,
            "schema_version": "aider-task-remedy-v1",
            "status": "planned",
            "task_id": case.legacy_id,
            "tree_hash_after": None,
            "tree_hash_before": existing.get("tree_hash_before", _tree_hash(LEGACY_ROOT / case.legacy_id)),
        }
        _write(remedy_root / f"{case.legacy_id}.md", spec, True)
        _write(existing_path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if len(CASES) != EXPECTED_TASK_COUNT or set(VERIFICATION_CASES) != {case.task_id for case in CASES}:
        raise RuntimeError("family_count_or_verification_inventory_mismatch")
    expected_roots = {case.task_id for case in CASES}
    if out.is_dir():
        for child in out.iterdir():
            if child.is_dir() and child.name != ".state" and child.name not in expected_roots:
                if not force:
                    raise RuntimeError(f"generator_output_drift:obsolete_root:{child.name}")
                shutil.rmtree(child)
    _write_planned_remedies(out)
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
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
            "benchmark_separation": "Clean-room v2 contract with task-specific API, state, transitions, query, reference, and tests; not derived from the grade-school holdout.",
            "curriculum_document": CURRICULUM,
            "curriculum_task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "origin": "repository-authored ordered-registry remediation",
            "prompt": PROMPT,
            "status": "local task artifact; not admitted SFT data",
            "version": 2,
        }
        files = {
            ".docs/introduction.md": f"# {case.title}\n\n{case.objective}\n",
            ".docs/instructions.md": _instructions(case),
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": "[visible]\ndescription = \"public behavior, boundary, and ordering contract\"\n\n[hidden]\ndescription = \"atomic failure, state invariant, adversarial transition, and negative-fixture boundary\"\n",
            "task.h": case.header,
            "task.cpp": case.starter,
            ".meta/example.h": case.header,
            ".meta/example.cpp": case.reference,
            ".meta/negative_fixture.cpp": _negative_source(case),
            ".meta/negative_fixture.json": json.dumps(
                {
                    "expected_failure": "topic_specific_false_substitute_rejected",
                    "name": VERIFICATION_CASES[case.task_id].false_name,
                    "source_hash": _sha(_negative_source(case).encode()),
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            "task_visible_test.cpp": case.visible,
            ".meta/task_hidden_test.cpp": case.hidden,
            ".meta/task_trace_test.cpp": VERIFICATION_CASES[case.task_id].trace,
            "CMakeLists.txt": CMAKE,
        }
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def _safe_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise RuntimeError("unsafe_path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise RuntimeError(f"unsafe_path:{value}")
    return path.as_posix()


def _core_failure(case: Case, source: str) -> str | None:
    if any(marker not in source for marker in case.core_markers):
        return "invariant_not_enforced"
    if any(marker in source for marker in case.forbidden_markers):
        return "invariant_not_enforced"
    return None


def _verify_remedies(out: Path) -> None:
    remedy = out / ".state" / "remedy"
    expected = {case.legacy_id for case in CASES}
    records = {path.stem: path for path in remedy.glob("*.json")}
    specs = {path.stem: path for path in remedy.glob("*.md")}
    if set(records) != expected or set(specs) != expected:
        raise RuntimeError("remedy_spec_incomplete")
    for case in CASES:
        record = json.loads(records[case.legacy_id].read_text(encoding="utf-8"))
        text = specs[case.legacy_id].read_text(encoding="utf-8")
        positions = [text.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if -1 in positions or positions != sorted(positions):
            raise RuntimeError(f"remedy_spec_incomplete:{case.legacy_id}")
        expected_disposition = "repair-in-place" if case.legacy_id == "registry-audit-retention" else "replace"
        if record.get("task_id") != case.legacy_id or record.get("disposition") != expected_disposition:
            raise RuntimeError(f"remedy_disposition_conflict:{case.legacy_id}")
        if record.get("remedy_spec_hash") != _sha(text.encode()):
            raise RuntimeError(f"remedy_spec_incomplete:{case.legacy_id}:hash")


def _whole_format_code(root: Path, response: str) -> str | None:
    try:
        parsed = parse_whole_file_blocks(response)
    except WholeFormatError:
        return "whole_format_failed"
    return None if set(parsed) == set(load_task(root).editable_files) else "whole_format_failed"


_SEMANTIC_KEYWORDS = {
    "if", "else", "for", "while", "do", "switch", "case", "break", "continue", "return",
    "true", "false", "nullopt", "public", "private", "class", "struct", "enum", "using",
    "const", "static", "auto", "bool", "int", "long", "size_t", "void", "string", "optional",
    "vector", "map", "set", "unordered_map", "pair", "tuple", "move", "find", "count", "at",
    "begin", "end", "empty", "size", "front", "back", "push_back", "pop_back", "emplace",
    "insert", "erase", "sort", "min", "max", "min_element", "find_if", "remove_if", "all_of",
    "none_of", "swap", "numeric_limits", "namespace", "include", "define", "operator", "check",
}


def _normalize_cpp(text: str) -> tuple[str, ...]:
    """Erase nouns/literals while retaining API shape, branches, operators and assertions."""
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b(?:0x[0-9a-fA-F]+|\d+)\b', " LIT ", text)
    raw = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|::|->|==|!=|<=|>=|&&|\|\||\+\+|--|[{}()\[\],;?:.+*/%<>=!&|-]", text)
    return tuple(token.lower() if token.lower() in _SEMANTIC_KEYWORDS else ("LIT" if token == "LIT" else "ID") for token in raw)


def _api_shape(header: str) -> tuple[str, ...]:
    public = header.split("public:", 1)[1].split("private:", 1)[0] if "public:" in header else header
    shape: list[str] = []
    for match in re.finditer(r"([^;{}]+?)\(([^()]*)\)\s*(const)?\s*;", public):
        prefix, params, const = match.groups()
        param_parts = [] if not params.strip() else [part.strip() for part in params.split(",")]
        type_shape = ["ref" if "&" in part else "value" for part in param_parts]
        shape.extend(("method", str(len(param_parts)), "const" if const else "mutable", *type_shape, *_normalize_cpp(prefix)))
    return tuple(shape)


def _normalized_contract(case: Case) -> tuple[str, ...]:
    verification = VERIFICATION_CASES[case.task_id]
    return (
        *_api_shape(case.header), "SECTION", *_normalize_cpp(case.header), "SECTION",
        *_normalize_cpp(case.reference), "SECTION", *_normalize_cpp(case.visible), "SECTION",
        *_normalize_cpp(case.hidden), "SECTION", *_normalize_cpp(verification.trace),
    )


def _shingles(tokens: tuple[str, ...], width: int = 7) -> set[tuple[str, ...]]:
    if len(tokens) < width:
        return {tokens}
    return {tokens[index:index + width] for index in range(len(tokens) - width + 1)}


def _contract_similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    a, b = _shingles(left), _shingles(right)
    return len(a & b) / max(1, len(a | b))


def _screen_family(cases: Sequence[Case] = CASES) -> dict[str, object]:
    if len(cases) != EXPECTED_TASK_COUNT:
        raise RuntimeError(f"family_count_out_of_bounds:{len(cases)}")
    profiles: set[tuple[str, ...]] = set()
    normalized: dict[str, tuple[str, ...]] = {}
    strongest: dict[str, dict[str, object]] = {}
    for case in cases:
        verification = VERIFICATION_CASES.get(case.task_id)
        if verification is None:
            raise RuntimeError(f"verification_inventory_missing:{case.task_id}")
        profile = (verification.logic, verification.state, verification.mutation, verification.selection, verification.boundary)
        if profile in profiles:
            raise RuntimeError(f"duplicate_family:{case.task_id}:diversity_profile")
        profiles.add(profile)
        normalized[case.task_id] = _normalized_contract(case)
    ids = list(normalized)
    for index, task_id in enumerate(ids):
        best_id, best_score = "", 0.0
        for other_id in ids[index + 1:]:
            score = _contract_similarity(normalized[task_id], normalized[other_id])
            if score > best_score:
                best_id, best_score = other_id, score
            if normalized[task_id] == normalized[other_id] or score >= 0.94:
                raise RuntimeError(f"duplicate_family:{task_id}:{other_id}:{score:.6f}")
        strongest[task_id] = {"other_task_id": best_id or None, "similarity": round(best_score, 6)}
    return {
        "comparison_scope": "all proposed docs/APIs/source/visible/private/model-trace tests",
        "normalizer": NORMALIZER_VERSION,
        "root_count": len(cases),
        "strongest_later_pair_by_task": strongest,
        "status": "pass",
    }


def _screen_benchmarks(out: Path) -> dict[str, object]:
    manifest = json.loads(BENCHMARK_MANIFEST.read_text(encoding="utf-8"))
    holdout_ids = set(manifest["task_ids"])
    available: dict[str, tuple[str, ...]] = {}
    for task_id in holdout_ids:
        root = UPSTREAM_CPP / task_id
        if root.is_dir():
            text = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in sorted(root.rglob("*"))
                if path.is_file() and path.stat().st_size < 300_000 and "catch.hpp" not in path.name
            )
            available[task_id] = _normalize_cpp(text)
    if len(available) != len(holdout_ids):
        raise RuntimeError(f"benchmark_content_unavailable:{len(available)}/{len(holdout_ids)}")
    strongest: dict[str, float] = {}
    for case in CASES:
        if case.task_id in holdout_ids:
            raise RuntimeError(f"benchmark_id_overlap:{case.task_id}")
        verification = VERIFICATION_CASES[case.task_id]
        candidate = _normalize_cpp(case.header + case.reference + case.visible + case.hidden + verification.trace + _instructions(case))
        overlaps = {
            holdout: _contract_similarity(candidate, tokens)
            for holdout, tokens in available.items()
        }
        strongest[case.task_id] = max(overlaps.values(), default=0.0)
        if strongest[case.task_id] >= 0.94:
            raise RuntimeError(f"benchmark_content_overlap:{case.task_id}")
    return {
        "manifest": str(BENCHMARK_MANIFEST),
        "holdouts_screened": len(available),
        "comparison_scope": "candidate and all bound holdout docs/APIs/source/tests",
        "normalizer": NORMALIZER_VERSION,
        "max_token_overlap_by_task": strongest,
        "status": "pass",
    }


def _promote_remedies(out: Path, status: str) -> None:
    remedy = out / ".state" / "remedy"
    case_by_legacy = {case.legacy_id: case for case in CASES}
    for path in sorted(remedy.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        case = case_by_legacy[path.stem]
        record.update({
            "benchmark_screen": "pass",
            "primary_core_objective": "achieved",
            "primary_core_evidence": {
                "mechanism": case.objective,
                "negative_fixture": VERIFICATION_CASES[case.task_id].false_name,
                "verified_by": "compiled private-test rejection plus model trace in verify",
            },
            "replacement_task_id": case.task_id,
            "status": status,
            "tree_hash_after": _tree_hash(out / case.task_id),
        })
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def verify_core(out: Path, *, require_remedy: bool = True) -> None:
    if require_remedy:
        _verify_remedies(out)
    expected = {case.task_id for case in CASES}
    actual = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    if actual != expected:
        raise RuntimeError(f"generator_output_drift:expected={len(expected)}:actual={len(actual)}")
    prompt_hashes: dict[str, str] = {}
    tasks = []
    family_screen = _screen_family()
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        files = config.get("files", {})
        solution = [_safe_path(item) for item in files.get("solution", [])]
        tests = [_safe_path(item) for item in files.get("test", [])]
        examples = [_safe_path(item) for item in files.get("example", [])]
        expected_solution = [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        if solution != expected_solution or examples != [".meta/example.h", ".meta/example.cpp"]:
            raise RuntimeError(f"target_reference_mismatch:{case.task_id}")
        if set(solution) & set(tests + examples) or any(not (root / item).is_file() for item in solution + tests + examples):
            raise RuntimeError(f"unsafe_path:{case.task_id}")
        task = load_task(root)
        prompt = build_prompt(task)
        private_names = tests + examples + ["CMakeLists.txt", ".meta/provenance.json", ".meta/task_hidden_test.cpp", ".meta/task_trace_test.cpp", ".meta/negative_fixture.cpp", ".meta/negative_fixture.json"]
        if any(name in prompt for name in private_names):
            raise RuntimeError(f"prompt_contract_incomplete:{case.task_id}:private_path")
        # example.h intentionally equals the public starter header, so content
        # equality is not evidence of oracle exposure.  The source reference
        # and every executable/private role must remain absent by content.
        for private in tests + [examples[1], "CMakeLists.txt", ".meta/provenance.json", ".meta/task_hidden_test.cpp", ".meta/task_trace_test.cpp", ".meta/negative_fixture.cpp", ".meta/negative_fixture.json"]:
            private_path = root / private
            if private_path.is_file() and private_path.read_text(encoding="utf-8") in prompt:
                raise RuntimeError(f"prompt_contract_incomplete:{case.task_id}")
        answer = build_assistant_response(task, load_example_files_from_config(root))
        missing = f"{solution[0]}\n```cpp\n// incomplete\n```\n"
        extra = answer + "\nunknown.cpp\n```cpp\n// forbidden\n```\n"
        prose = "explanation\n" + answer
        if _whole_format_code(root, answer) or any(_whole_format_code(root, value) != "whole_format_failed" for value in (missing, extra, prose)):
            raise RuntimeError(f"whole_format_failed:{case.task_id}")
        source = (root / ".meta/example.h").read_text(encoding="utf-8") + "\n" + (root / ".meta/example.cpp").read_text(encoding="utf-8")
        if _core_failure(case, source):
            raise RuntimeError(f"invariant_not_enforced:{case.task_id}")
        legacy_generic = "struct Entry { int id; std::string group; int rank; int stamp; };"
        if _core_failure(case, source + legacy_generic) != "invariant_not_enforced":
            raise RuntimeError(f"negative_fixture_not_rejected:{case.task_id}:legacy")
        negative = (root / ".meta/negative_fixture.cpp").read_text(encoding="utf-8")
        if negative != _rendered_negative_source(case) or negative == case.reference:
            raise RuntimeError(f"negative_fixture_source_drift:{case.task_id}")
        signature = _sha(" ".join(_normalized_contract(case)).encode())
        prompt_hashes[case.task_id] = _sha(prompt.encode())
        verification = VERIFICATION_CASES[case.task_id]
        tasks.append({
            "diversity_profile": {
                "boundary": verification.boundary,
                "logic": verification.logic,
                "mutation": verification.mutation,
                "selection": verification.selection,
                "state": verification.state,
            },
            "legacy_task_id": case.legacy_id,
            "negative_fixture": verification.false_name,
            "negative_fixture_hash": _sha(negative.encode()),
            "reference_hash": _sha(case.reference.encode()),
            "semantic_signature": signature,
            "task_id": case.task_id,
            "tree_hash": _tree_hash(root),
        })
    benchmark = _screen_benchmarks(out)
    with tempfile.TemporaryDirectory(prefix="ordered-registry-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for case in CASES:
            if _tree_hash(out / case.task_id) != _tree_hash(fresh / case.task_id):
                raise RuntimeError(f"generator_output_drift:{case.task_id}")
    state = out / ".state"
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "family_id": FAMILY_ID,
        "status": "semantically_admitted",
        "task_count": len(CASES),
        "legacy_root_preserved": str(LEGACY_ROOT),
        "prompt": PROMPT,
        "screen": {"prompt_boundary": "pass", "reference_mapping": "pass", "duplicate_family": "pass", "benchmark_contamination": "pass", "primary_core_objective": "achieved"},
        "family_screen": family_screen,
        "benchmark": benchmark,
        "prompt_hashes": prompt_hashes,
        "tasks": tasks,
    }
    _write(state / "materialization-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    _promote_remedies(out, "implemented")


def _run(command: list[str]) -> str:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode:
        raise RuntimeError(f"command_failed:{' '.join(command)}\n{result.stdout}")
    return result.stdout


def _run_expected_failure(command: list[str], code: str) -> str:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode == 0:
        raise RuntimeError(f"{code}:unexpected_pass:{' '.join(command)}\n{result.stdout}")
    return result.stdout


def _test_count(build_dir: Path) -> int:
    payload = json.loads(_run(["ctest", "--test-dir", str(build_dir), "--show-only=json-v1"]))
    count = len(payload.get("tests", []))
    if count == 0:
        raise RuntimeError("zero_tests")
    return count


def _verify_negative_fixture(case: Case, copied: Path) -> dict[str, object]:
    negative = copied / ".meta/negative_fixture.cpp"
    negative_build = copied / "build-negative-fixture"
    configure = ["cmake", "-S", str(copied), "-B", str(negative_build), "-G", "Unix Makefiles", "-DCMAKE_CXX_COMPILER=c++", f"-DTASK_SOURCE={negative}"]
    _run(configure)
    build_command = ["cmake", "--build", str(negative_build), "--parallel", "2"]
    _run(build_command)
    count = _test_count(negative_build)
    test_command = ["ctest", "--test-dir", str(negative_build), "--output-on-failure"]
    fixture = VERIFICATION_CASES[case.task_id]
    _run_expected_failure(test_command, f"invariant_not_enforced:{case.task_id}:{fixture.false_name}")
    return {
        "build": build_command,
        "configure": configure,
        "discovered_tests": count,
        "expected_result": "private_and_model_tests_reject_topic_specific_false_substitute",
        "fixture_hash": _sha(negative.read_bytes()),
        "fixture_name": fixture.false_name,
        "status": "pass",
        "test": test_command,
    }


def verify_negative_fixtures(out: Path) -> None:
    verify_core(out)
    if any(shutil.which(name) is None for name in ("cmake", "c++")):
        raise RuntimeError("negative_fixture_runtime_missing")
    receipts = []
    for case in CASES:
        with tempfile.TemporaryDirectory(prefix=f"negative-{case.task_id}-") as temporary:
            copied = Path(temporary) / case.task_id
            shutil.copytree(out / case.task_id, copied)
            receipts.append({"task_id": case.task_id, "mode": _verify_negative_fixture(case, copied)})
    _write(out / ".state/oracle/negative-fixture-preflight.json", json.dumps({"status": "pass", "tasks": receipts}, indent=2, sort_keys=True) + "\n", True)


def verify(out: Path) -> None:
    expected_mount_hash = os.environ.get("W8_BIAYN_ORACLE_EXPECTED_FAMILY_HASH")
    network_policy = os.environ.get("W8_BIAYN_ORACLE_NETWORK_POLICY")
    runtime_name = os.environ.get("W8_BIAYN_ORACLE_RUNTIME")
    image = os.environ.get("W8_BIAYN_ORACLE_IMAGE")
    docker_missing = []
    if runtime_name != "docker_sanity":
        docker_missing.append("W8_BIAYN_ORACLE_RUNTIME=docker_sanity")
    if network_policy != "none":
        docker_missing.append("W8_BIAYN_ORACLE_NETWORK_POLICY=none")
    if image != DESIGNATED_IMAGE:
        docker_missing.append(f"W8_BIAYN_ORACLE_IMAGE={DESIGNATED_IMAGE}")
    if not expected_mount_hash:
        docker_missing.append("W8_BIAYN_ORACLE_EXPECTED_FAMILY_HASH=<owner hash>")
    missing = [name for name in ("cmake", "c++") if shutil.which(name) is None]
    if missing or docker_missing:
        receipt = {"status": "not_completed", "blocked_command": "network-disabled Docker owner --verify", "missing_prerequisites": [*missing, *docker_missing]}
        _write(out / ".state/oracle/verification.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        return
    verify_core(out)
    mount_hash = _family_hash(out)
    if expected_mount_hash != mount_hash:
        raise RuntimeError(f"grader_mount_hash_mismatch:owner={expected_mount_hash}:docker={mount_hash}")
    receipts = []
    for case in CASES:
        task_root = out / case.task_id
        modes: dict[str, object] = {}
        with tempfile.TemporaryDirectory(prefix=f"{case.task_id}-") as temporary:
            copied = Path(temporary) / case.task_id
            shutil.copytree(task_root, copied)
            reference = copied / ".meta/example.cpp"
            modes["negative_fixture"] = _verify_negative_fixture(case, copied)
            for mode, flags in (
                ("normal", []),
                ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]),
            ):
                build_dir = copied / f"build-{mode}"
                configure = ["cmake", "-S", str(copied), "-B", str(build_dir), "-G", "Unix Makefiles", "-DCMAKE_CXX_COMPILER=c++", f"-DTASK_SOURCE={reference}", *flags]
                _run(configure)
                build_command = ["cmake", "--build", str(build_dir), "--parallel", "2"]
                _run(build_command)
                count = _test_count(build_dir)
                test_command = ["ctest", "--test-dir", str(build_dir), "--output-on-failure"]
                _run(test_command)
                modes[mode] = {"build": build_command, "configure": configure, "discovered_tests": count, "status": "pass", "test": test_command}
        if modes["normal"]["discovered_tests"] != modes["sanitizer"]["discovered_tests"]:
            raise RuntimeError(f"sanitizer_test_count_mismatch:{case.task_id}")
        receipts.append({
            "modes": modes,
            "negative_fixture_hash": _sha((task_root / ".meta/negative_fixture.cpp").read_bytes()),
            "reference_hash": _sha((task_root / ".meta/example.cpp").read_bytes()),
            "task_id": case.task_id,
            "tree_hash": _tree_hash(task_root),
        })
    runtime = {
        "cmake": _run(["cmake", "--version"]).splitlines()[0],
        "compiler": _run(["c++", "--version"]).splitlines()[0],
        "docker_mount_family_hash": mount_hash,
        "environment": runtime_name,
        "expected_owner_family_hash": expected_mount_hash,
        "image": image,
        "network_policy": network_policy,
        "normal_and_fresh_sanitizer": True,
        "owner_hash": _owner_hash(),
    }
    _write(out / ".state/oracle/verification.json", json.dumps({"status": "pass", "runtime": runtime, "tasks": receipts}, indent=2, sort_keys=True) + "\n", True)
    manifest_path = out / ".state/materialization-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({"status": "local_family_verified", "oracle_receipts": len(receipts), "executed_negative_fixtures": len(receipts), "normal_test_count_per_root": 3, "sanitizer_test_count_per_root": 3, "owner_hash": _owner_hash(), "verified_family_hash": mount_hash})
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    _promote_remedies(out, "verified")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--verify-negative-fixtures", action="store_true")
    parser.add_argument("--print-family-hash", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify_negative_fixtures:
        verify_negative_fixtures(args.out)
    if args.verify:
        verify(args.out)
    if args.print_family_hash:
        print(_family_hash(args.out))
    print(f"Wrote {len(roots)} ordered-registry v2 tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
