"""Remediate and locally reverify the nth/final-occurrences task family."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tarfile
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Mapping, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_nth_final_occurrences_cases import CASES, OccurrenceCase

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/aider-dates-and-clocks/nth-and-final-occurrences"
)
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dates-and-clocks/nth-and-final-occurrences")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_NTH_AND_FINAL_OCCURRENCES_CURRICULUM.md"
FAMILY_SPEC = "docs/aider-tasks-spec/aider-dates-and-clocks/nth-and-final-occurrences.md"
PROMPT_PATH = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
GENERATOR_PATH = "src/w8_biayn/integrations/moonlight_nth_final_occurrences_aider_tasks.py"
CASES_PATH = "src/w8_biayn/integrations/moonlight_nth_final_occurrences_cases.py"
TEST_PATH = "tests/test_moonlight_nth_final_occurrences_aider_tasks.py"
WRAPPER_PATH = "examples/slime/moonlight_cpp_perf/prepare_nth_final_occurrences_aider_tasks.sh"
FAMILY_ID = "aider-dates-and-clocks-nth-final-occurrences-v2"
LEGACY_FAMILY_ID = "aider-dates-and-clocks-nth-final-occurrences-v1-template"
LEGACY_GENERATOR_REVISION = (
    "sha256:dfbb6bc60073800db33e549695b0428b90473e05431070747ab26dcee7cb86e4"
)
NORMALIZER = "nth-final-occurrences-v2-identifiers-literals-endpoints-neutral"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
OFFICIAL_HOLDOUTS = frozenset(
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
HARD_DIMENSIONS = (
    "public_api",
    "owned_state_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
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

CMAKE = r"""cmake_minimum_required(VERSION 3.16)
project(nth_final_occurrences_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
enable_testing()
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


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _file_hash(path: Path) -> str:
    return _sha(path.read_bytes())


def _tree_hash(root: Path, *, include_state: bool = False) -> str:
    if not root.is_dir():
        return "not_available"
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if not include_state and ".state" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _write(path: Path, content: str, force: bool = False) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _remedy_markdown(case: OccurrenceCase) -> str:
    return f"""## Identity

Task ID: `{case.task_id}`; legacy task ID: `{case.legacy_id}`; task-spec revision: 2; family ID: `{FAMILY_ID}/{case.task_id}`; disposition: `{case.disposition}`; source inventory: `nth-final-occurrences-legacy-v1`; license result: repository-authored/pass; generator: `{GENERATOR_PATH}` plus `{CASES_PATH}`; benchmark screen: pending. Selected prompt: `{PROMPT_PATH}` with canonicalized `FAMILY_NAME=nth-and-final-occurrences`, `FAMILY_TYPE=aider-dates-and-clocks`; the user-authorized hard family size is 8–12 and this specification counts 10 roots.

## Objective

{case.objective}

## Public API

C++17 namespace `curriculum`; editable order is `{case.task_id}.h`, `{case.task_id}.cpp`. API: `{case.public_api}`. Inputs are caller-owned values; the task owns only the state explicitly declared in its header.

## Behavior table

Valid input executes the documented mechanism and returns the numbered or final occurrence. Invalid input returns `false`, an invalid audit, or `std::nullopt` without partial mutation as declared by the API. Empty and absent queries are distinct from malformed state. {case.boundary} Integer arithmetic is bounded by the supplied values and no host clock is consulted. The visible test is the public boundary example; the private test covers empty, invalid, duplicate/order, and ordinal-zero behavior.

## Implementation invariant

Required mechanism: `{case.mechanism}`. The emitted header must contain necessary owned state or the deliberately stateless algorithm API, and the reference must execute that mechanism. Forbidden substitutes are the legacy shared `select(records, policy, threshold, ordinal, final_match)` template, a renamed/policy/opposite-end copy of another root, hard-coded cases, calendar/weekday APIs, and official benchmark assets.

## Starter and reference

The task-named header fully declares the API and the task-named source is a coherent incomplete implementation. `.meta/example.h` and `.meta/example.cpp` independently implement every editable file. The reference does not import the legacy generator, tests, or a generic mode switch.

## Tests

The visible and private executables use deterministic value oracles. The topic negative changes `{case.negative_old}` to `{case.negative_new}` to model “{case.negative_reason}”; it must compile under the reference flags and be rejected by executed tests. Coherent domain/identifier-renamed, constants/policy-only, and opposite-end-selection controls derived from an emitted root must change files, compile and pass their internally updated tests in normal and sanitizer modes, while the exact production evaluator rejects every hard-rule dimension.

## Files and metadata

Solutions: `{case.task_id}.h`, `{case.task_id}.cpp`; visible test: `task_visible_test.cpp`; private test: `.meta/task_hidden_test.cpp`; references: `.meta/example.h`, `.meta/example.cpp`. Config order maps references one-to-one by suffix. Docs, tests, metadata, CMake, references, controls, manifests, and receipts remain private.

## Build/oracle

C++17 with extensions off, strict warnings, explicit `Unix Makefiles`, two positive CTest discoveries. Use `{SANITY_IMAGE}` with Docker network `none` for clean normal and fresh ASan/UBSan reference builds, executed topic-negative rejection, and coherent-control builds. The receipt binds archive/tree/owner/reference/image/toolchain/command/count hashes.

## Family/contamination

Compare all 45 unordered pairs separately across exactly seven dimensions using actual emitted docs, API, reference, visible/private tests, and negative fixture under `{NORMALIZER}`. Screen all 26 official C++ holdouts across the same semantic roles. No benchmark or duplicate waiver is permitted.

## Optional dataset handoff

`not_requested`. No JSONL, tokens, masks, split, export, training, or release is authorized.

## Acceptance

Run focused pytest, owner `--verify-core`, and owner `--docker-sanity`. Require exact 10-root regeneration within the authorized 8–12 range, 45 passing all-pairs decisions in every dimension, nonempty coherent control changes and production rejection, prompt/role/reference safety, 26-root holdout separation, two equal positive normal/sanitizer tests for each root and control, and executed rejection of all 10 topic negatives. Stable failures include `remedy_spec_incomplete`, `prompt_contract_incomplete`, `invariant_not_enforced`, `duplicate_family`, `benchmark_content_overlap`, `negative_fixture_not_rejected`, `generator_output_drift`, `grader_mount_hash_mismatch`, and `sanitizer_test_count_mismatch`.
"""


def _write_remedies(out: Path, force: bool) -> None:
    remedy_root = out / ".state/remedy"
    for case in CASES:
        markdown = _remedy_markdown(case)
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "family_id_before": LEGACY_FAMILY_ID,
            "family_id_after": f"{FAMILY_ID}/{case.task_id}",
            "tree_hash_before": _tree_hash(LEGACY_ROOT / case.legacy_id),
            "generator_path": GENERATOR_PATH,
            "generator_revision": LEGACY_GENERATOR_REVISION,
            "finding_ids": [
                "NFO-F1-shared-selector-template",
                "NFO-F2-core-objective-underimplemented",
                "NFO-F3-oracle-evidence-not-image-bound",
                "NFO-F4-hard-rule-controls-absent",
            ],
            "disposition": case.disposition,
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": f".state/remedy/{case.task_id}.md",
            "remedy_spec_hash": _sha(markdown.encode()),
            "status": "planned",
            "primary_core_objective": "specified",
            "dataset_handoff": "not_requested",
            "selected_prompt": PROMPT_PATH,
            "user_inputs": {
                "FAMILY_NAME": "nth-and-final-occurence",
                "FAMILY_TYPE": "aider-text-grid-reshaping",
                "canonical_family": "aider-dates-and-clocks/nth-and-final-occurrences",
                "authorized_hard_size": "8-12",
            },
        }
        _write(remedy_root / f"{case.task_id}.md", markdown, force)
        _write(
            remedy_root / f"{case.task_id}.json",
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            force,
        )


def _negative_source(case: OccurrenceCase) -> str:
    if case.reference.count(case.negative_old) != 1:
        _fail("invariant_not_enforced", f"negative mutation drift: {case.task_id}")
    changed = case.reference.replace(case.negative_old, case.negative_new, 1)
    if changed == case.reference:
        _fail("invariant_not_enforced", f"empty negative mutation: {case.task_id}")
    return changed


def _instructions(case: OccurrenceCase) -> str:
    return f"# Instructions\n\nImplement `{case.title}`.\n\n{case.objective}\n\nPublic API: `{case.public_api}`.\n\nBoundary contract: {case.boundary}\n\nUse the mechanism required by the contract; do not use host time, calendar or weekday APIs, files, networking, threads, randomness, precomputed answers, or a generic mode-switch selector.\n"


def _cpp_layout(content: str) -> str:
    """Give compact authored C++ stable warning-clean statement layout."""
    return content.replace(";", ";\n")


def _invalidate_prior_evidence(out: Path) -> None:
    receipt = out / ".state/docker-sanity.json"
    if not receipt.exists():
        return
    archive = out / ".state/invalidated"
    archive.mkdir(parents=True, exist_ok=True)
    target = archive / f"docker-sanity-{_file_hash(receipt).split(':', 1)[1][:16]}.json"
    receipt.replace(target)
    _write(
        archive / "README.md",
        "Prior Docker evidence was invalidated by owner-controlled regeneration because task, test, owner, or hard-rule artifacts changed. Archived receipts do not prove the current tree.\n",
        True,
    )


def _control_cases() -> Mapping[str, OccurrenceCase]:
    base = CASES[0]
    domain_pairs = (
        ("Inspection", "Checkpoint"),
        ("inspection", "checkpoint"),
        ("Route", "Lane"),
        ("route", "lane"),
    )

    def renamed(value: str) -> str:
        for old, new in domain_pairs:
            value = value.replace(old, new)
        return value

    domain = replace(
        base,
        task_id="domain-identifier-renamed-clone",
        title=renamed(base.title),
        objective=renamed(base.objective),
        public_api=renamed(base.public_api),
        boundary=renamed(base.boundary),
        header=renamed(base.header),
        reference=renamed(base.reference),
        visible_test=renamed(base.visible_test),
        hidden_test=renamed(base.hidden_test),
    )
    constants = replace(
        base,
        task_id="constants-policy-clone",
        reference=base.reference.replace(
            "severity >= policy.minimum_severity", "severity > policy.minimum_severity"
        ),
        visible_test=base.visible_test.replace("RoutePolicy p{2,4}", "RoutePolicy p{2,3}"),
        hidden_test=base.hidden_test.replace("RoutePolicy p{2,4}", "RoutePolicy p{2,3}"),
    )
    opposite = replace(
        base,
        task_id="opposite-end-selection-clone",
        reference=base.reference.replace(
            "found.back().id,found.back().sequence", "found.front().id,found.front().sequence"
        ),
        visible_test=base.visible_test.replace("f.id==14", "f.id==11"),
    )
    return {case.task_id: case for case in (domain, constants, opposite)}


def _write_controls(out: Path, force: bool) -> None:
    root = out / ".state/hard-rule-controls"
    manifest: dict[str, object] = {"schema_version": "nth-final-hard-controls-v1", "controls": {}}
    for name, case in _control_cases().items():
        control = root / name
        files = {
            ".docs/instructions.md": _instructions(case),
            "task.h": _cpp_layout(case.header),
            "candidate.cpp": _cpp_layout(case.reference),
            "task_visible_test.cpp": _cpp_layout(case.visible_test),
            ".meta/task_hidden_test.cpp": _cpp_layout(case.hidden_test),
            "CMakeLists.txt": CMAKE.replace(
                '"${CMAKE_CURRENT_SOURCE_DIR}/task.cpp"',
                '"${CMAKE_CURRENT_SOURCE_DIR}/candidate.cpp"',
            ),
        }
        changed: list[str] = []
        base_files = {
            "task.h": _cpp_layout(CASES[0].header),
            "candidate.cpp": _cpp_layout(CASES[0].reference),
            "task_visible_test.cpp": _cpp_layout(CASES[0].visible_test),
            ".meta/task_hidden_test.cpp": _cpp_layout(CASES[0].hidden_test),
        }
        for relative, content in files.items():
            _write(control / relative, content, force)
            if relative in base_files and content != base_files[relative]:
                changed.append(relative)
        if not changed:
            _fail("invariant_not_enforced", f"control changed no files: {name}")
        manifest["controls"][name] = {
            "changed_files": sorted(changed),
            "tree_hash": _tree_hash(control, include_state=True),
        }
    _write(root / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", force)


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if force:
        _invalidate_prior_evidence(out)
    if not (out / ".state/remedy").is_dir():
        _write_remedies(out, force)
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
            "curriculum_document": CURRICULUM,
            "family_specification": FAMILY_SPEC,
            "curriculum_task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "family_id": FAMILY_ID,
            "mechanism": case.mechanism,
            "origin": "repository-authored clean-room remediation",
            "license": "repository-authored",
            "version": 2,
            "status": "local task artifact; not admitted SFT data",
            "benchmark_separation": "Caller-supplied domain records and non-calendar mechanisms; all official Aider C++ roots remain permanent holdouts.",
        }
        instructions = _instructions(case)
        files = {
            ".docs/introduction.md": f"# {case.title}\n\n{case.objective}\n",
            ".docs/instructions.md": instructions,
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": f'[visible]\ndescription = "normal {case.mechanism} behavior"\n\n[hidden]\ndescription = "invalid, empty, boundary, duplicate/order, and ordinal-zero behavior"\n\n[negative]\ndescription = "{case.negative_reason}"\n',
            "task.h": _cpp_layout(case.header),
            "task.cpp": '#include "task.h"\nnamespace curriculum {\n// TODO: implement the complete documented API.\n}\n',
            ".meta/example.h": _cpp_layout(case.header),
            ".meta/example.cpp": _cpp_layout(case.reference),
            ".meta/negative_false_substitute.cpp": _cpp_layout(_negative_source(case)),
            "task_visible_test.cpp": _cpp_layout(case.visible_test),
            ".meta/task_hidden_test.cpp": _cpp_layout(case.hidden_test),
            "CMakeLists.txt": CMAKE,
        }
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    _write_controls(out, force)
    return tuple(roots)


def _normalize(content: str) -> tuple[str, ...]:
    content = re.sub(r"/\*.*?\*/|//[^\n]*", " ", content, flags=re.S)
    content = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", content)
    content = re.sub(r"\b(front|back|rbegin|rend|begin|end)\b", " ENDPOINT ", content)
    content = re.sub(r">=|<=|>|<", " REL ", content)
    tokens = re.findall(r"[A-Za-z_]\w*|==|!=|&&|\|\||\+\+|--|[-+*/%{}()[\];,?:=.]", content)
    keywords = {
        "if",
        "else",
        "for",
        "while",
        "return",
        "class",
        "struct",
        "enum",
        "const",
        "auto",
        "bool",
        "int",
        "void",
        "true",
        "false",
        "public",
        "private",
        "namespace",
        "std",
        "vector",
        "map",
        "set",
        "deque",
        "queue",
        "optional",
        "size_t",
        "REL",
        "ENDPOINT",
        "LIT",
    }
    return tuple(
        token if token in keywords or not re.match(r"[A-Za-z_]", token) else "ID"
        for token in tokens
    )


def _dimension_material(root: Path) -> dict[str, tuple[str, ...]]:
    header = (
        (root / f"{root.name}.h").read_text(encoding="utf-8")
        if (root / f"{root.name}.h").exists()
        else (root / "task.h").read_text(encoding="utf-8")
    )
    reference_path = root / ".meta/example.cpp"
    if not reference_path.exists():
        reference_path = root / "candidate.cpp"
    reference = reference_path.read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    hidden = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
    instructions = (
        (root / ".docs/instructions.md").read_text(encoding="utf-8")
        if (root / ".docs/instructions.md").exists()
        else ""
    )
    negative_path = root / ".meta/negative_false_substitute.cpp"
    negative = negative_path.read_text(encoding="utf-8") if negative_path.exists() else reference
    return {
        "public_api": _normalize(header),
        "owned_state_algorithm": _normalize(header + reference),
        "mutation_selection_rules": _normalize(instructions + reference),
        "invalid_boundary_behavior": _normalize(instructions + hidden),
        "reference_control_flow": _normalize(reference),
        "deterministic_oracle": _normalize(visible + hidden),
        "topic_negative_fixture": _normalize(negative),
    }


def _pair_decisions(left: Path, right: Path) -> dict[str, bool]:
    left_material, right_material = _dimension_material(left), _dimension_material(right)
    return {
        dimension: left_material[dimension] != right_material[dimension]
        for dimension in HARD_DIMENSIONS
    }


def _hard_rule_screen(out: Path) -> dict[str, object]:
    task_ids = sorted(case.task_id for case in CASES)
    pairs: list[dict[str, object]] = []
    for index, left_id in enumerate(task_ids):
        for right_id in task_ids[index + 1 :]:
            decisions = _pair_decisions(out / left_id, out / right_id)
            if not all(decisions.values()):
                _fail("duplicate_family", f"{left_id} vs {right_id}: {decisions}")
            pairs.append({"left": left_id, "right": right_id, "decisions": decisions})
    expected = len(CASES) * (len(CASES) - 1) // 2
    if len(pairs) != expected:
        _fail("duplicate_family", f"pair count {len(pairs)} != {expected}")
    controls: dict[str, object] = {}
    base = out / CASES[0].task_id
    control_manifest = json.loads((out / ".state/hard-rule-controls/manifest.json").read_text())
    for name in sorted(_control_cases()):
        control = out / ".state/hard-rule-controls" / name
        decisions = _pair_decisions(base, control)
        changed = control_manifest["controls"][name]["changed_files"]
        if not changed or any(decisions.values()):
            _fail(
                "duplicate_family", f"control not rejected in every dimension: {name}: {decisions}"
            )
        controls[name] = {
            "changed_files": changed,
            "decisions": decisions,
            "production_rejected": True,
        }
    return {
        "status": "pending_execution",
        "root_count": len(CASES),
        "minimum": 8,
        "maximum": 12,
        "dimensions": list(HARD_DIMENSIONS),
        "pair_count": len(pairs),
        "expected_pair_count": expected,
        "pairs": pairs,
        "controls": controls,
        "normalizer": NORMALIZER,
        "evidence_source": "actual emitted docs, public API, reference, visible/private tests, and topic negative",
    }


def _ngrams(tokens: tuple[str, ...], width: int = 9) -> set[tuple[str, ...]]:
    return {tokens[i : i + width] for i in range(max(0, len(tokens) - width + 1))}


def _holdout_screen(out: Path) -> dict[str, object]:
    found = (
        {path.name for path in HOLDOUT_ROOT.iterdir() if path.is_dir()}
        if HOLDOUT_ROOT.is_dir()
        else set()
    )
    missing = sorted(OFFICIAL_HOLDOUTS - found)
    if missing:
        _fail("benchmark_content_overlap", f"bound holdout inventory unavailable: {missing}")
    comparisons = 0
    strongest = 0.0
    strongest_pair: list[str] = []
    candidate_tokens = {
        case.task_id: _normalize(
            " ".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in sorted((out / case.task_id).rglob("*"))
                if path.is_file() and "build" not in path.parts
            )
        )
        for case in CASES
    }
    for holdout_id in sorted(OFFICIAL_HOLDOUTS):
        holdout = HOLDOUT_ROOT / holdout_id
        text = " ".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in sorted(holdout.rglob("*"))
            if path.is_file() and path.stat().st_size < 1_000_000
        )
        holdout_grams = _ngrams(_normalize(text))
        for task_id, tokens in candidate_tokens.items():
            candidate_grams = _ngrams(tokens)
            denominator = min(len(candidate_grams), len(holdout_grams))
            similarity = len(candidate_grams & holdout_grams) / denominator if denominator else 0.0
            comparisons += 1
            if similarity > strongest:
                strongest = similarity
                strongest_pair = [task_id, holdout_id]
            if similarity >= 0.80:
                _fail("benchmark_content_overlap", f"{task_id} vs {holdout_id}: {similarity:.3f}")
    return {
        "status": "pass",
        "holdout_root_count": len(OFFICIAL_HOLDOUTS),
        "comparison_count": comparisons,
        "normalizer": NORMALIZER,
        "threshold": 0.80,
        "strongest_pair": strongest_pair,
        "strongest_containment": round(strongest, 6),
    }


def _sync_remedies(out: Path, **updates: object) -> None:
    for case in CASES:
        path = out / ".state/remedy" / f"{case.task_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update(updates)
        record["tree_hash_after"] = _tree_hash(out / case.task_id)
        record["generator_revision_after"] = _file_hash(Path(GENERATOR_PATH))
        record["changed_owner_paths"] = [
            CURRICULUM,
            FAMILY_SPEC,
            "docs/AIDER_TASK_MATERIALIZATION_GUIDE.md",
            GENERATOR_PATH,
            CASES_PATH,
            TEST_PATH,
            WRAPPER_PATH,
        ]
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def verify_core(out: Path) -> None:
    if not 8 <= len(CASES) <= 12 or len(CASES) != 10:
        _fail("duplicate_family", f"authorized count violated: {len(CASES)}")
    tasks: list[dict[str, object]] = []
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        expected_solution = [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        if config["files"]["solution"] != expected_solution or config["files"]["example"] != [
            ".meta/example.h",
            ".meta/example.cpp",
        ]:
            _fail("target_reference_mismatch", case.task_id)
        prompt = build_prompt(load_task(root))
        forbidden = (
            ".meta/example",
            "task_visible_test",
            "task_hidden_test",
            "CMakeLists",
            "provenance.json",
            "negative_false_substitute",
        )
        if any(token in prompt for token in forbidden):
            _fail("prompt_contract_incomplete", case.task_id)
        answer = build_assistant_response(load_task(root), load_example_files_from_config(root))
        if (
            not answer.startswith(f"{case.task_id}.h\n```")
            or f"{case.task_id}.cpp\n```" not in answer
        ):
            _fail("target_reference_mismatch", case.task_id)
        remedy = out / ".state/remedy" / f"{case.task_id}.md"
        text = remedy.read_text()
        headings = tuple(re.findall(r"^## (.+)$", text, flags=re.M))
        if headings != REMEDY_HEADINGS:
            _fail("remedy_spec_incomplete", f"{case.task_id}: {headings}")
        expected_negative = task_named_files(
            root, {".meta/negative_false_substitute.cpp": _cpp_layout(_negative_source(case))}
        )[".meta/negative_false_substitute.cpp"]
        if (
            case.mechanism not in (root / ".meta/provenance.json").read_text()
            or expected_negative != (root / ".meta/negative_false_substitute.cpp").read_text()
        ):
            _fail("invariant_not_enforced", case.task_id)
        tasks.append(
            {
                "task_id": case.task_id,
                "legacy_task_id": case.legacy_id,
                "disposition": case.disposition,
                "tree_hash": _tree_hash(root),
                "reference_hash": _file_hash(root / ".meta/example.cpp"),
                "primary_core_objective": "achieved",
            }
        )
    hard_rule = _hard_rule_screen(out)
    holdouts = _holdout_screen(out)
    manifest = {
        "schema_version": "nth-final-occurrences-materialization-v2",
        "family_id": FAMILY_ID,
        "task_count": len(CASES),
        "owner_hash": _file_hash(Path(GENERATOR_PATH)),
        "cases_hash": _file_hash(Path(CASES_PATH)),
        "family_tree_hash": _tree_hash(out),
        "tasks": tasks,
        "screen": {
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
            "primary_core_objective": "achieved",
            "duplicate_family": "pass",
            "hard_rule": hard_rule,
            "semantic_holdout": holdouts,
        },
        "strongest_local_status": "pending_execution",
        "dataset_handoff": "not_requested",
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
        benchmark_screen="pass",
        family_screen="pass",
        prompt_boundary="pass",
        hard_rule_status="pending_execution",
        strongest_local_status="pending_execution",
    )


def _deterministic_archive(out: Path, archive: Path) -> str:
    with tarfile.open(archive, "w", format=tarfile.PAX_FORMAT) as tar:
        entries: list[tuple[Path, str]] = []
        for case in CASES:
            for path in sorted((out / case.task_id).rglob("*")):
                if path.is_file():
                    entries.append(
                        (
                            path,
                            f"tasks/{case.task_id}/{path.relative_to(out / case.task_id).as_posix()}",
                        )
                    )
        for name in sorted(_control_cases()):
            root = out / ".state/hard-rule-controls" / name
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    entries.append((path, f"controls/{name}/{path.relative_to(root).as_posix()}"))
        for path, name in entries:
            info = tar.gettarinfo(str(path), arcname=name)
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            info.mtime = 0
            info.mode = 0o644
            with path.open("rb") as handle:
                tar.addfile(info, handle)
    return _file_hash(archive)


def verify_docker(out: Path, image: str = SANITY_IMAGE) -> None:
    manifest_path = out / ".state/materialization-manifest.json"
    if not manifest_path.is_file():
        _fail("generator_output_drift", "run --verify-core first")
    before = json.loads(manifest_path.read_text())
    if (
        before["family_tree_hash"] != _tree_hash(out)
        or before["owner_hash"] != _file_hash(Path(GENERATOR_PATH))
        or before["cases_hash"] != _file_hash(Path(CASES_PATH))
    ):
        _fail("generator_output_drift", "core manifest does not bind current owner/tree")
    with tempfile.TemporaryDirectory(prefix="nth-final-docker-") as temp_name:
        temp = Path(temp_name)
        archive = temp / "family.tar"
        result = temp / "result"
        result.mkdir()
        archive_hash = _deterministic_archive(out, archive)
        script = r"""set -Eeuo pipefail
trap 'status=$?; echo "docker verifier failed with status ${status}" >&2; for log in /tmp/*.log; do echo "== ${log} ==" >&2; tail -80 "${log}" >&2 || true; done; exit "${status}"' ERR
mkdir -p /work/tree
tar -xf /input/family.tar -C /work/tree
sha256sum /input/family.tar | awk '{print "archive\t"$1}' > /result/results.tsv
c++ --version | head -1 > /result/compiler.txt
cmake --version | head -1 > /result/cmake.txt
run_ref() { id="$1"; mode="$2"; echo "reference ${id} ${mode}" >&2; root="/work/tree/tasks/$id"; build="/tmp/${id}-${mode}-ref"; prefix="/result/${id}-${mode}"; flags=(); if [ "$mode" = sanitizer ]; then flags+=("-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"); fi; cmake -S "$root" -B "$build" -G "Unix Makefiles" -DTASK_SOURCE="$root/.meta/example.cpp" "${flags[@]}" >"${prefix}-config.log" 2>&1; cmake --build "$build" --parallel 2 >"${prefix}-build.log" 2>&1; count=$(ctest --test-dir "$build" -N | sed -n 's/^Total Tests: //p'); test "$count" = 2; ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$build" --output-on-failure >"${prefix}-test.log" 2>&1; printf 'reference\t%s\t%s\t%s\n' "$id" "$mode" "$count" >> /result/results.tsv; }
run_negative() { id="$1"; echo "negative ${id}" >&2; root="/work/tree/tasks/$id"; build="/tmp/${id}-negative"; prefix="/result/${id}-negative"; cmake -S "$root" -B "$build" -G "Unix Makefiles" -DTASK_SOURCE="$root/.meta/negative_false_substitute.cpp" >"${prefix}-config.log" 2>&1; cmake --build "$build" --parallel 2 >"${prefix}-build.log" 2>&1; count=$(ctest --test-dir "$build" -N | sed -n 's/^Total Tests: //p'); test "$count" = 2; if ctest --test-dir "$build" --output-on-failure >"${prefix}-test.log" 2>&1; then echo "negative fixture unexpectedly passed: ${id}" >&2; exit 71; fi; printf 'negative\t%s\tnormal\t%s\n' "$id" "$count" >> /result/results.tsv; }
run_control() { id="$1"; mode="$2"; root="/work/tree/controls/$id"; build="/tmp/control-${id}-${mode}"; flags=(); if [ "$mode" = sanitizer ]; then flags+=("-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"); fi; cmake -S "$root" -B "$build" -G "Unix Makefiles" "${flags[@]}" >/tmp/config.log; cmake --build "$build" --parallel 2 >/tmp/build.log; count=$(ctest --test-dir "$build" -N | sed -n 's/^Total Tests: //p'); test "$count" = 2; ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$build" --output-on-failure >/tmp/test.log; printf 'control\t%s\t%s\t%s\n' "$id" "$mode" "$count" >> /result/results.tsv; }
for root in /work/tree/tasks/*; do id=${root##*/}; run_ref "$id" normal; run_ref "$id" sanitizer; run_negative "$id"; done
for root in /work/tree/controls/*; do id=${root##*/}; run_control "$id" normal; run_control "$id" sanitizer; done
"""
        completed = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--mount",
                f"type=bind,src={archive},dst=/input/family.tar,readonly",
                "--mount",
                f"type=bind,src={result},dst=/result",
                image,
                "bash",
                "-lc",
                script,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            log_tail = "\n".join(
                f"== {path.name} ==\n{path.read_text(errors='replace')[-3000:]}"
                for path in sorted(result.glob("*.log"))
            )
            _fail(
                "docker_sanity_failed",
                (completed.stderr + "\n" + completed.stdout + "\n" + log_tail)[-12000:],
            )
        lines = [line.split("\t") for line in (result / "results.tsv").read_text().splitlines()]
        mounted_hash = f"sha256:{lines[0][1]}"
        if mounted_hash != archive_hash:
            _fail("grader_mount_hash_mismatch", f"{mounted_hash} != {archive_hash}")
        refs = [row for row in lines if row[0] == "reference"]
        negatives = [row for row in lines if row[0] == "negative"]
        controls = [row for row in lines if row[0] == "control"]
        if (
            len(refs) != len(CASES) * 2
            or len(negatives) != len(CASES)
            or len(controls) != 6
            or any(row[3] != "2" for row in refs + negatives + controls)
        ):
            _fail(
                "sanitizer_test_count_mismatch",
                f"refs={len(refs)} negatives={len(negatives)} controls={len(controls)}",
            )
        receipt = {
            "schema_version": "nth-final-occurrences-docker-sanity-v1",
            "status": "pass",
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "network_policy": "none",
            "image": image,
            "archive_hash": archive_hash,
            "mounted_archive_hash": mounted_hash,
            "family_tree_hash": _tree_hash(out),
            "owner_hash": _file_hash(Path(GENERATOR_PATH)),
            "cases_hash": _file_hash(Path(CASES_PATH)),
            "compiler": (result / "compiler.txt").read_text().strip(),
            "cmake": (result / "cmake.txt").read_text().strip(),
            "reference_results": [
                {"task_id": row[1], "mode": row[2], "test_count": int(row[3])} for row in refs
            ],
            "topic_negatives": [
                {
                    "task_id": row[1],
                    "compiled": True,
                    "executed": True,
                    "rejected": True,
                    "test_count": int(row[3]),
                }
                for row in negatives
            ],
            "controls": [
                {
                    "control": row[1],
                    "mode": row[2],
                    "compiled": True,
                    "executed": True,
                    "internally_passing": True,
                    "production_rejected": True,
                    "test_count": int(row[3]),
                }
                for row in controls
            ],
            "commands": {
                "docker": "docker run --rm --network none <pinned-image> bash -lc <owner-verifier>",
                "generator": f"PYTHONPATH=src python3 -m w8_biayn.integrations.moonlight_nth_final_occurrences_aider_tasks --out {out} --force --verify-core --docker-sanity",
            },
        }
        _write(
            out / ".state/docker-sanity.json",
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            True,
        )
    manifest = json.loads(manifest_path.read_text())
    manifest["screen"]["hard_rule"]["status"] = "pass"
    manifest["docker_sanity"] = {
        "status": "pass",
        "receipt": ".state/docker-sanity.json",
        "normal_test_count_per_root": 2,
        "sanitizer_test_count_per_root": 2,
        "topic_negative_count": len(CASES),
        "control_count": 3,
    }
    manifest["strongest_local_status"] = "local_family_verified"
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    _sync_remedies(
        out,
        status="verified",
        oracle_status="docker_sanity_pass",
        hard_rule_status="pass",
        benchmark_screen="pass",
        family_screen="pass",
        strongest_local_status="local_family_verified",
        docker_receipt=".state/docker-sanity.json",
        normal_test_count=2,
        sanitizer_test_count=2,
        topic_negative="compiled_executed_rejected",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core or args.docker_sanity:
        verify_core(args.out)
    if args.docker_sanity:
        verify_docker(args.out)
    print(f"Wrote {len(roots)} remediated nth/final-occurrence tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
