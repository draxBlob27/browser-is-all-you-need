"""Materialize and Docker-verify the remediated skip-list task family."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from typing import Callable, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_skip_list_cases import CASES, Case


ROOT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/skip-list")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dsa/skip-list")
CURRICULUM = Path("docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_SKIP_LIST_CURRICULUM.md")
SPEC = Path("docs/aider-tasks-spec/aider-dsa/skip-list.md")
PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
BENCHMARK_MANIFEST = Path("manifests/aider_sft/aider-polyglot-cpp-26.json")
BENCHMARK_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
SUPPORT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice/sublist/test")
FAMILY_ID = "aider-dsa-skip-list-v3"
NORMALIZER = "aider-cleanroom-family-v3"
IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
BANNED_SOURCE_TOKENS = (
    "std::map<", "std::set<", "std::multiset<", "std::priority_queue<",
    "__gnu_pbds", "boost::", "SORTED_VECTOR_AUTHORITY",
)
ROLE_FILES = (
    ".docs/introduction.md", ".docs/instructions.md", ".meta/config.json",
    ".meta/provenance.json", ".meta/tests.toml", ".meta/example.h",
    ".meta/example.cpp", ".meta/task_hidden_test.cpp",
    ".meta/negative_topic_specific.cpp", "task_visible_test.cpp",
    "CMakeLists.txt", "test/catch.hpp", "test/tests-main.cpp",
)


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _raw_tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _generator_hash() -> str:
    paths = (Path(__file__), Path(__file__).with_name("moonlight_skip_list_cases.py"))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _spec_contract_hash() -> str:
    normative = SPEC.read_text(encoding="utf-8").split(
        "\n## Final re-verification evidence\n", 1
    )[0].rstrip() + "\n"
    return _sha256_bytes(normative.encode())


def _write(path: Path, content: str | bytes, force: bool) -> None:
    current = path.read_bytes() if path.is_file() else None
    data = content if isinstance(content, bytes) else content.encode()
    if current == data:
        return
    if current is not None and not force:
        raise FileExistsError(f"{path} differs; pass --force only for the re-verification root")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _remedy_record(out: Path, case: Case, *, status: str, tree_hash: str | None = None) -> dict[str, object]:
    path = out / ".state" / "remedy" / f"{case.legacy_id}.json"
    if not path.is_file():
        raise RuntimeError(f"remedy_spec_incomplete: {path}")
    record = json.loads(path.read_text(encoding="utf-8"))
    spec_path = Path(str(record.get("remedy_spec_path", "")))
    if not spec_path.is_absolute():
        if spec_path.is_file():
            pass
        else:
            candidate = out / ".state" / "remedy" / f"{case.legacy_id}.md"
            spec_path = candidate
    if not spec_path.is_file() or _sha256_file(spec_path) != record.get("remedy_spec_hash"):
        raise RuntimeError(f"remedy_spec_incomplete: stale spec for {case.legacy_id}")
    expected = "repair-in-place" if case.legacy_id == case.task_id else "replace"
    if record.get("disposition") != expected or record.get("replacement_task_id") != case.task_id:
        raise RuntimeError(f"remedy_disposition_conflict: {case.legacy_id}")
    record.update({
        "family_id_after": FAMILY_ID,
        "generator_content_hash_after": _generator_hash(),
        "primary_core_objective": "achieved",
        "status": status,
    })
    if tree_hash is not None:
        record["tree_hash_after"] = tree_hash
    _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)
    return record


def _instructions(case: Case) -> str:
    return f"""# Instructions

Implement `{case.class_name}` in the two editable files. {case.contract}

The complete public declarations, value types, ownership, and return types are
in the header. Invalid, duplicate, and absent operations return their declared
failure or empty result and leave all state unchanged. Integer range endpoints
must be checked before conversion or addition. Returned sequences use the
documented deterministic order and zero-based positions where an index is
part of the API.

The authoritative state must be the declared linked skip-list mechanism:
`{case.mechanism}`. Implement all tower links and task-specific augmentations.
Do not delegate ordered state to `std::map`, `std::set`, `std::multiset`, a
priority queue, PBDS, Boost ordered containers, or a globally sorted vector.
Vectors remain allowed for returned values, temporary update paths, audit
snapshots, and the bounded payload block of the unrolled-line task.
"""


def _visible_test(case: Case) -> str:
    return f'''#include "task.h"
#include <catch.hpp>
#include <string>
#include <unordered_set>
#include <vector>
TEST_CASE("{case.task_id} public contract", "[visible]") {{
  using namespace curriculum;
  {case.visible}
}}
'''


def _hidden_test(case: Case) -> str:
    return f'''#include "task.h"
#include <algorithm>
#include <catch.hpp>
#include <string>
#include <unordered_set>
#include <vector>
TEST_CASE("{case.task_id} deterministic private trace", "[hidden]") {{
  using namespace curriculum;
  constexpr unsigned kTraceSeed = 0x5A17U;
  (void)kTraceSeed;
  {case.hidden}
}}
'''


def _cmake(case: Case) -> str:
    required = " ".join(f'"{token}"' for token in case.required_tokens)
    banned = " ".join(f'"{token}"' for token in BANNED_SOURCE_TOKENS)
    return f'''cmake_minimum_required(VERSION 3.16)
project({case.task_id.replace('-', '_')} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${{CMAKE_CURRENT_SOURCE_DIR}}/{case.task_id}.cpp" CACHE FILEPATH "Implementation source")
file(READ "${{TASK_SOURCE}}" TASK_SOURCE_TEXT)
file(READ "${{CMAKE_CURRENT_SOURCE_DIR}}/{case.task_id}.h" TASK_HEADER_TEXT)
set(TASK_ALL_TEXT "${{TASK_HEADER_TEXT}}\n${{TASK_SOURCE_TEXT}}")
foreach(token IN ITEMS {banned})
  string(FIND "${{TASK_ALL_TEXT}}" "${{token}}" found)
  if(NOT found EQUAL -1)
    message(FATAL_ERROR "invariant_not_enforced: forbidden substitute ${{token}}")
  endif()
endforeach()
foreach(token IN ITEMS {required})
  string(FIND "${{TASK_ALL_TEXT}}" "${{token}}" found)
  if(found EQUAL -1)
    message(FATAL_ERROR "invariant_not_enforced: missing mechanism token ${{token}}")
  endif()
endforeach()
enable_testing()
add_executable(task_tests "${{TASK_SOURCE}}" task_visible_test.cpp .meta/task_hidden_test.cpp test/tests-main.cpp)
target_include_directories(task_tests PRIVATE "${{CMAKE_CURRENT_SOURCE_DIR}}" "${{CMAKE_CURRENT_SOURCE_DIR}}/test")
target_compile_definitions(task_tests PRIVATE CURRICULUM_TESTING=1 EXERCISM_RUN_ALL_TESTS=1)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(task_tests PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
add_test(NAME visible COMMAND task_tests "[visible]")
add_test(NAME hidden COMMAND task_tests "[hidden]")
'''


def _negative_source(case: Case) -> str:
    source = case.reference
    if not case.negative_name or not case.negative_edits:
        raise RuntimeError(f"remedy_spec_incomplete: missing negative fixture for {case.task_id}")
    for old, new in case.negative_edits:
        count = source.count(old)
        if count != 1:
            raise RuntimeError(
                f"generator_output_drift: {case.task_id} negative edit matched {count} times"
            )
        source = source.replace(old, new, 1)
    if source == case.reference:
        raise RuntimeError(f"generator_output_drift: unchanged negative source for {case.task_id}")
    if any(token in source for token in BANNED_SOURCE_TOKENS):
        raise RuntimeError(f"invariant_not_enforced: banned shortcut in {case.task_id} fixture")
    return source


def _rendered_negative_source(case: Case) -> str:
    return _negative_source(case).replace("task.h", f"{case.task_id}.h")


def _support() -> tuple[bytes, bytes, dict[str, str]]:
    catch = SUPPORT_ROOT / "catch.hpp"
    main = SUPPORT_ROOT / "tests-main.cpp"
    if not catch.is_file() or not main.is_file():
        raise RuntimeError(f"missing pinned Catch support beneath {SUPPORT_ROOT}")
    return catch.read_bytes(), main.read_bytes(), {
        "catch.hpp": _sha256_file(catch), "tests-main.cpp": _sha256_file(main)
    }


def _role_and_prompt_check(root: Path, case: Case) -> None:
    task = load_task(root)
    expected = (f"{case.task_id}.h", f"{case.task_id}.cpp")
    if task.editable_files != expected:
        raise RuntimeError(f"target_reference_mismatch: {case.task_id}")
    config = json.loads((root / ".meta/config.json").read_text())
    if tuple(config["files"]["solution"]) != expected:
        raise RuntimeError(f"target_reference_mismatch: {case.task_id}")
    if tuple(config["files"]["example"]) != (".meta/example.h", ".meta/example.cpp"):
        raise RuntimeError(f"target_reference_mismatch: {case.task_id}")
    prompt = build_prompt(task)
    forbidden = (".meta/example", "task_hidden_test", "CMakeLists.txt", "provenance.json", "catch.hpp")
    if any(token in prompt for token in forbidden):
        raise RuntimeError(f"prompt_contract_incomplete: private role exposed for {case.task_id}")
    for editable in expected:
        if editable not in prompt:
            raise RuntimeError(f"prompt_contract_incomplete: missing {editable}")


def _prune_owned_v2_negative(root: Path, case: Case, force: bool) -> None:
    obsolete = root / ".meta/negative_sorted_vector.cpp"
    if not obsolete.exists():
        return
    if not force:
        raise RuntimeError(
            f"generator_output_drift: obsolete v2 negative remains for {case.task_id}"
        )
    provenance_path = root / ".meta/provenance.json"
    if not provenance_path.is_file():
        raise RuntimeError(f"generator_output_drift: missing provenance for {case.task_id}")
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    if provenance.get("task_id") != case.task_id or provenance.get("family_id") not in {
        "aider-dsa-skip-list-v2",
        FAMILY_ID,
    }:
        raise RuntimeError(f"generator_output_drift: refusing foreign root {case.task_id}")
    obsolete.unlink()


def _reject_substitute(text: str, case: Case) -> str | None:
    if any(token in text for token in BANNED_SOURCE_TOKENS):
        return "invariant_not_enforced"
    if any(token not in text for token in case.required_tokens):
        return "invariant_not_enforced"
    return None


def _normalize(text: str, domain_words: set[str]) -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/|\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'", " ", text, flags=re.M | re.S)
    text = re.sub(r"\b(?:0x[0-9a-f]+|\d+)\b", "#", text.lower())
    tokens = re.findall(r"[a-z_]+|[{}();,*&<>!=+\-/]", text)
    return tuple(token for token in tokens if token not in domain_words)


def _ngrams(tokens: tuple[str, ...], width: int = 7) -> set[tuple[str, ...]]:
    return {tokens[index:index + width] for index in range(max(0, len(tokens) - width + 1))}


def _similarity(left: str, right: str, domain_words: set[str] | None = None) -> float:
    words = domain_words or set()
    a, b = _ngrams(_normalize(left, words)), _ngrams(_normalize(right, words))
    return len(a & b) / max(1, len(a | b))


DIVERSITY_LIMITS = {
    "public_api": 0.88,
    "owned_state_algorithm": 0.88,
    "mutation_selection": 0.88,
    "invalid_boundary": 0.88,
    "reference_control_flow": 0.88,
    "deterministic_oracle": 0.88,
    "topic_specific_negative": 0.88,
}


def _dimension_similarity(left: str, right: str, domain_words: set[str]) -> float:
    left_tokens = _normalize(left, domain_words)
    right_tokens = _normalize(right, domain_words)
    ordered_ratio = difflib.SequenceMatcher(
        None, left_tokens, right_tokens, autojunk=True
    ).ratio()
    return max(_similarity(left, right, domain_words), ordered_ratio)


def _pair_decision(
    left: dict[str, str], right: dict[str, str], domain_words: set[str]
) -> dict[str, object]:
    if set(left) != set(DIVERSITY_LIMITS) or set(right) != set(DIVERSITY_LIMITS):
        raise RuntimeError("duplicate_family: incomplete hard-rule dimensions")
    scores = {
        dimension: _dimension_similarity(left[dimension], right[dimension], domain_words)
        for dimension in DIVERSITY_LIMITS
    }
    violations = [
        dimension
        for dimension, score in scores.items()
        if score >= DIVERSITY_LIMITS[dimension]
    ]
    return {
        "decision": "duplicate_family" if violations else "distinct",
        "scores": scores,
        "violations": violations,
    }


def _artifact_dimensions(root: Path, case: Case) -> dict[str, str]:
    header = (root / f"{case.task_id}.h").read_text(encoding="utf-8")
    reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
    instructions = (root / ".docs/instructions.md").read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    hidden = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
    negative = (root / ".meta/negative_topic_specific.cpp").read_text(encoding="utf-8")
    return {
        "public_api": header,
        "owned_state_algorithm": header + "\n" + reference,
        "mutation_selection": reference,
        "invalid_boundary": instructions + "\n" + visible,
        "reference_control_flow": reference,
        "deterministic_oracle": hidden,
        "topic_specific_negative": negative,
    }


def _mutate_dimensions(
    dimensions: dict[str, str], transform: Callable[[str], str]
) -> dict[str, str]:
    return {name: transform(text) for name, text in dimensions.items()}


def _adversarial_clone_controls(
    out: Path, case: Case, domain_words: set[str]
) -> dict[str, dict[str, object]]:
    base = _artifact_dimensions(out / case.task_id, case)
    controls = {
        "domain_renamed_clone": _mutate_dimensions(
            base,
            lambda text: text.replace(case.class_name, "WarehouseTower")
            .replace(case.task_id, "warehouse-tower")
            .replace("auction", "warehouse")
            .replace("price", "aisle"),
        ),
        "constants_policy_clone": _mutate_dimensions(
            base,
            lambda text: re.sub(
                r"\b\d+\b", lambda match: str(int(match.group(0)) + 137), text
            ),
        ),
        "opposite_end_selection_clone": _mutate_dimensions(
            base,
            lambda text: text.replace("first", "last")
            .replace("best", "worst")
            .replace("highest", "lowest")
            .replace("front", "back"),
        ),
    }
    outcomes: dict[str, dict[str, object]] = {}
    for name, clone in controls.items():
        decision = _pair_decision(base, clone, domain_words)
        if decision["decision"] != "duplicate_family":
            raise RuntimeError(f"duplicate_family: emitted control escaped: {name}")
        outcomes[name] = {
            **decision,
            "source": "emitted_artifact",
            "production_pair_evaluator": True,
        }
    return outcomes


def _holdout_material(task_id: str) -> str:
    root = BENCHMARK_ROOT / task_id
    if not root.is_dir():
        raise RuntimeError(f"benchmark_content_overlap: missing bound holdout {task_id}")
    selected: list[str] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and (
            ".docs" in path.parts or ".meta" in path.parts
            or path.suffix in {".h", ".hpp", ".cpp", ".cc"}
        ):
            selected.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(selected)


def _screen(out: Path) -> dict[str, object]:
    manifest = json.loads(BENCHMARK_MANIFEST.read_text(encoding="utf-8"))
    holdout_ids = set(manifest["task_ids"])
    task_ids = {case.task_id for case in CASES}
    if task_ids & holdout_ids:
        raise RuntimeError("benchmark_id_overlap")
    domain_words = set()
    for case in CASES:
        domain_words.update(re.findall(r"[a-z]+", case.task_id + " " + case.class_name))
    dimensions = {
        case.task_id: _artifact_dimensions(out / case.task_id, case) for case in CASES
    }
    materials = {
        task_id: "\n".join(parts.values()) for task_id, parts in dimensions.items()
    }
    strongest_family: dict[str, object] = {
        "pair": None, "dimension": None, "score": 0.0
    }
    pair_decisions: list[dict[str, object]] = []
    ids = sorted(dimensions)
    comparisons = 0
    for index, left in enumerate(ids):
        for right in ids[index + 1:]:
            comparisons += 1
            decision = _pair_decision(dimensions[left], dimensions[right], domain_words)
            scores = decision["scores"]
            assert isinstance(scores, dict)
            strongest_dimension, score = max(scores.items(), key=lambda item: item[1])
            if score > float(strongest_family["score"]):
                strongest_family = {
                    "pair": [left, right],
                    "dimension": strongest_dimension,
                    "score": score,
                }
            pair_decisions.append({"pair": [left, right], **decision})
            if decision["decision"] != "distinct":
                raise RuntimeError(
                    f"duplicate_family: {left} {right} {decision['violations']}"
                )
    strongest_holdout: dict[str, object] = {"pair": None, "jaccard": 0.0}
    holdout_comparisons = 0
    for holdout_id in sorted(holdout_ids):
        holdout = _holdout_material(holdout_id)
        for task_id, material in materials.items():
            holdout_comparisons += 1
            score = _similarity(material, holdout, domain_words)
            if score > float(strongest_holdout["jaccard"]):
                strongest_holdout = {"pair": [task_id, holdout_id], "jaccard": score}
            if score >= 0.45:
                raise RuntimeError(f"benchmark_content_overlap: {task_id} {holdout_id} {score:.6f}")
    result = {
        "schema_version": 2,
        "status": "pass",
        "normalizer": NORMALIZER,
        "hard_rule_dimensions": list(DIVERSITY_LIMITS),
        "dimension_limits": DIVERSITY_LIMITS,
        "candidate_pairs": comparisons,
        "expected_candidate_pairs": 190,
        "pair_decisions": pair_decisions,
        "holdout_comparisons": holdout_comparisons,
        "holdout_inventory": sorted(holdout_ids),
        "strongest_family_pair": strongest_family,
        "strongest_holdout_pair": strongest_holdout,
        "family_duplicate_screen": "pass",
        "benchmark_screen": "pass",
        "prompt_boundary": "pass",
        "adversarial_controls": _adversarial_clone_controls(
            out, min(CASES, key=lambda case: case.task_id), domain_words
        ),
    }
    _write(out / ".state/family-screen.json", json.dumps(result, indent=2, sort_keys=True) + "\n", True)
    return result


def verify_core(out: Path) -> dict[str, object]:
    if len(CASES) != 20 or len({case.task_id for case in CASES}) != 20:
        raise RuntimeError("duplicate_family: invalid root inventory")
    if len({case.mechanism for case in CASES}) != 20:
        raise RuntimeError("duplicate_family: mechanism profiles are not unique")
    if sum(case.legacy_id == case.task_id for case in CASES) != 1:
        raise RuntimeError("remedy_disposition_conflict: expected one repair-in-place")
    for case in CASES:
        root = out / case.task_id
        _role_and_prompt_check(root, case)
        material = case.header + case.reference
        if _reject_substitute(material, case) is not None:
            raise RuntimeError(f"invariant_not_enforced: {case.task_id}")
        fixture = (root / ".meta/negative_topic_specific.cpp").read_text()
        if fixture != _rendered_negative_source(case):
            raise RuntimeError(f"generator_output_drift: negative fixture {case.task_id}")
        if _reject_substitute(case.header + fixture, case) is not None:
            raise RuntimeError(
                f"invariant_not_enforced: negative fixture must reach executed tests: {case.task_id}"
            )
    screen = _screen(out)
    result = {
        "schema_version": 2,
        "status": "pass",
        "primary_core_objective": "achieved",
        "roots": len(CASES),
        "unique_mechanisms": len({case.mechanism for case in CASES}),
        "negative_fixture_inventory": {
            case.task_id: case.negative_name for case in CASES
        },
        "negative_fixture_execution": "pending_docker",
        "prompt_boundary": "pass",
        "reference_mapping": "pass",
        "family_screen": screen,
    }
    _write(out / ".state/core-verification.json", json.dumps(result, indent=2, sort_keys=True) + "\n", True)
    return result


def build(out: Path = ROOT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() == LEGACY_ROOT.resolve():
        raise RuntimeError("LEGACY_ROOT is immutable; use the re-verification root")
    if not CURRICULUM.is_file() or not SPEC.is_file():
        raise RuntimeError("remedy_spec_incomplete: curriculum or family specification missing")
    catch, tests_main, support_hashes = _support()
    roots: list[Path] = []
    for case in CASES:
        _remedy_record(out, case, status="planned")
        root = out / case.task_id
        _prune_owned_v2_negative(root, case, force)
        config = {
            "authors": ["w8-biayn"],
            "blurb": case.contract,
            "files": {
                "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
                "test": ["task_visible_test.cpp"],
                "example": [".meta/example.h", ".meta/example.cpp"],
            },
        }
        provenance = {
            "curriculum_document": CURRICULUM.as_posix(),
            "family_specification": SPEC.as_posix(),
            "selected_prompt": PROMPT,
            "legacy_task_id": case.legacy_id,
            "task_id": case.task_id,
            "family_id": FAMILY_ID,
            "origin": "clean-room in-repository remediation replacement",
            "license": "repository license",
            "status": "local candidate material; not dataset admission",
            "mechanism": case.mechanism,
            "benchmark_separation": "screened against the pinned 26-root official C++ holdout inventory",
            "version": 2,
        }
        tests_toml = f'''[visible]
description = "public API, invalid inputs, ordering, and boundary behavior"

[hidden]
description = "deterministic full-state trace and mechanism invariant"

[negative]
description = "complete topic-specific false source must be rejected by executed tests"
fixture = "{case.negative_name}"
expected = "topic_specific_test_rejection"
'''
        files: dict[str, str | bytes] = {
            ".docs/introduction.md": f"# {case.class_name}\n\nLocal C++17 skip-list mechanism task: {case.contract}\n",
            ".docs/instructions.md": _instructions(case),
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": tests_toml,
            "task.h": case.header,
            "task.cpp": case.starter,
            ".meta/example.h": case.header,
            ".meta/example.cpp": case.reference,
            "task_visible_test.cpp": _visible_test(case),
            ".meta/task_hidden_test.cpp": _hidden_test(case),
            ".meta/negative_topic_specific.cpp": _negative_source(case),
            "CMakeLists.txt": _cmake(case),
            "test/catch.hpp": catch,
            "test/tests-main.cpp": tests_main,
        }
        text_files = task_named_files(root, {name: content for name, content in files.items() if isinstance(content, str)})
        rendered_files: dict[str, str | bytes] = {
            **text_files,
            **{name: content for name, content in files.items() if isinstance(content, bytes)},
        }
        for name, content in rendered_files.items():
            _write(root / name, content, force)
        expected_files = set(ROLE_FILES) | {f"{case.task_id}.h", f"{case.task_id}.cpp"}
        actual_files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
        unexpected = actual_files - expected_files
        if unexpected:
            raise RuntimeError(f"generator_output_drift: {case.task_id}: {sorted(unexpected)}")
        _role_and_prompt_check(root, case)
        tree_hash = _raw_tree_hash(root)
        _remedy_record(out, case, status="implemented", tree_hash=tree_hash)
        roots.append(root)
    core = verify_core(out)
    manifest = {
        "schema_version": 2,
        "family_id": FAMILY_ID,
        "status": "pending_execution",
        "local_only": True,
        "dataset_handoff": "not_requested",
        "selected_prompt": PROMPT,
        "curriculum": CURRICULUM.as_posix(),
        "family_specification": SPEC.as_posix(),
        "generator_hash": _generator_hash(),
        "spec_contract_hash": _spec_contract_hash(),
        "support_hashes": support_hashes,
        "task_ids": [case.task_id for case in CASES],
        "legacy_task_ids": [case.legacy_id for case in CASES],
        "tree_hashes": {case.task_id: _raw_tree_hash(out / case.task_id) for case in CASES},
        "core_verification": core,
        "oracle_status": "not_completed",
    }
    _write(out / ".state/manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    return tuple(roots)


def _archive_tasks(out: Path, destination: Path) -> None:
    with tarfile.open(destination, "w") as archive:
        for case in CASES:
            root = out / case.task_id
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                info = archive.gettarinfo(str(path), arcname=f"tasks/{case.task_id}/{path.relative_to(root).as_posix()}")
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                with path.open("rb") as handle:
                    archive.addfile(info, handle)


def quick_normal(out: Path) -> None:
    """Run receipt-free host normal builds for implementation iteration only."""
    if not shutil.which("cmake") or not shutil.which("c++"):
        raise RuntimeError("quick-normal requires host cmake and c++; it is not oracle evidence")
    for case in CASES:
        root = (out / case.task_id).resolve()
        with tempfile.TemporaryDirectory(prefix=f"skip-list-{case.task_id}-") as temporary:
            build_dir = Path(temporary) / "build"
            commands = (
                ["cmake", "-S", str(root), "-B", str(build_dir), "-G", "Unix Makefiles", f"-DTASK_SOURCE={root / '.meta/example.cpp'}"],
                ["cmake", "--build", str(build_dir)],
                ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
            )
            for command in commands:
                completed = subprocess.run(command, text=True, capture_output=True)
                if completed.returncode:
                    raise RuntimeError(
                        f"quick-normal failed for {case.task_id}: {' '.join(command)}\n"
                        f"{completed.stdout}{completed.stderr}"
                    )


def _docker_script() -> str:
    task_ids = " ".join(case.task_id for case in CASES)
    negative_cases = "\n".join(
        f'    {case.task_id}) fixture="{case.negative_name}" ;;' for case in CASES
    )
    return f'''set -euo pipefail
mkdir -p /snapshot
tar -xf /input/family.tar -C /snapshot
python3 - <<'PY'
from pathlib import Path
import hashlib
root=Path('/snapshot/tasks')
for task in sorted(p for p in root.iterdir() if p.is_dir()):
 d=hashlib.sha256()
 for path in sorted(p for p in task.rglob('*') if p.is_file()):
  d.update(path.relative_to(task).as_posix().encode());d.update(b'\\0');d.update(path.read_bytes());d.update(b'\\0')
 print('TREE|'+task.name+'|sha256:'+d.hexdigest(),flush=True)
PY
echo "TOOL|CXX|$(c++ --version | head -1)"
echo "TOOL|CXX_PATH|$(command -v c++)"
echo "TOOL|CXX_SHA256|sha256:$(sha256sum "$(command -v c++)" | cut -d' ' -f1)"
echo "TOOL|CMAKE|$(cmake --version | head -1)"
negative_escapes=0
for task in {task_ids}; do
  src="/snapshot/tasks/$task"
  reference_count=""
  for mode in normal sanitizer; do
    build="/work/$task-$mode"
    flags=()
    if [[ "$mode" == sanitizer ]]; then
      flags+=("-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined")
    fi
    cmake -S "$src" -B "$build" -G "Unix Makefiles" -DTASK_SOURCE="$src/.meta/example.cpp" "${{flags[@]}}" >/work/$task-$mode-configure.log 2>&1
    cmake --build "$build" >/work/$task-$mode-build.log 2>&1
    count=$(ctest --test-dir "$build" -N | sed -n 's/^Total Tests: //p')
    [[ "$count" =~ ^[1-9][0-9]*$ ]]
    if [[ "$mode" == normal ]]; then reference_count="$count"; fi
    ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=print_stacktrace=1 ctest --test-dir "$build" --output-on-failure >/work/$task-$mode-test.log 2>&1
    echo "RESULT|$task|$mode|$count"
  done
  bad="/work/$task-negative"
  case "$task" in
{negative_cases}
    *) echo "missing negative fixture identity: $task" >&2; exit 31 ;;
  esac
  cmake -S "$src" -B "$bad" -G "Unix Makefiles" -DTASK_SOURCE="$src/.meta/negative_topic_specific.cpp" >/work/$task-negative-configure.log 2>&1
  cmake --build "$bad" >/work/$task-negative-build.log 2>&1
  negative_count=$(ctest --test-dir "$bad" -N | sed -n 's/^Total Tests: //p')
  [[ "$negative_count" =~ ^[1-9][0-9]*$ ]]
  [[ "$negative_count" == "$reference_count" ]]
  visible_rc=0
  hidden_rc=0
  ctest --test-dir "$bad" -R '^visible$' --output-on-failure >/work/$task-negative-visible.log 2>&1 || visible_rc=$?
  ctest --test-dir "$bad" -R '^hidden$' --output-on-failure >/work/$task-negative-hidden.log 2>&1 || hidden_rc=$?
  grep -q 'Test #1: visible' /work/$task-negative-visible.log
  grep -q 'Test #2: hidden' /work/$task-negative-hidden.log
  if [[ "$visible_rc" == 0 && "$hidden_rc" == 0 ]]; then
    echo "negative fixture unexpectedly passed executed tests: $task $fixture" >&2
    negative_escapes=$((negative_escapes+1))
    continue
  fi
  echo "NEGATIVE|$task|$negative_count|$fixture|$visible_rc|$hidden_rc|topic_specific_test_rejection"
done
if [[ "$negative_escapes" != 0 ]]; then exit 32; fi
'''


def verify(out: Path) -> dict[str, object]:
    if not shutil.which("docker"):
        receipt = {"schema_version": 2, "status": "not_completed", "missing_prerequisites": ["docker CLI and daemon access"], "blocked_command": f"docker run --rm --network none {IMAGE} ..."}
        _write(out / ".state/oracle/verification.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        return receipt
    expected = {case.task_id: _raw_tree_hash(out / case.task_id) for case in CASES}
    with tempfile.TemporaryDirectory(prefix="skip-list-docker-") as temp_text:
        temp = Path(temp_text)
        archive = temp / "family.tar"
        work = temp / "work"
        snapshot = temp / "snapshot"
        work.mkdir()
        snapshot.mkdir()
        _archive_tasks(out, archive)
        command = [
            "docker", "run", "--rm", "--network", "none",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "-v", f"{archive}:/input/family.tar:ro",
            "-v", f"{work}:/work",
            "-v", f"{snapshot}:/snapshot",
            IMAGE, "bash", "-lc", _docker_script(),
        ]
        completed = subprocess.run(command, text=True, capture_output=True)
        log = out / ".state/oracle/docker.log"
        _write(log, completed.stdout + completed.stderr, True)
        if completed.returncode != 0:
            failure_root = out / ".state/oracle/failure-logs"
            for failure_log in sorted(work.glob("*.log")):
                _write(failure_root / failure_log.name, failure_log.read_bytes(), True)
            raise RuntimeError(f"Docker skip-list verification failed ({completed.returncode}); see {log}")
        docker_hashes: dict[str, str] = {}
        counts: dict[str, dict[str, int]] = {}
        negatives: dict[str, dict[str, object]] = {}
        tools: dict[str, str] = {}
        for line in completed.stdout.splitlines():
            fields = line.split("|")
            if fields[0] == "TREE" and len(fields) == 3:
                docker_hashes[fields[1]] = fields[2]
            elif fields[0] == "RESULT" and len(fields) == 4:
                counts.setdefault(fields[1], {})[fields[2]] = int(fields[3])
            elif (
                fields[0] == "NEGATIVE"
                and len(fields) == 7
                and fields[6] == "topic_specific_test_rejection"
            ):
                negatives[fields[1]] = {
                    "discovered_tests": int(fields[2]),
                    "fixture": fields[3],
                    "visible_returncode": int(fields[4]),
                    "hidden_returncode": int(fields[5]),
                    "outcome": fields[6],
                }
            elif fields[0] == "TOOL" and len(fields) == 3:
                tools[fields[1].lower()] = fields[2]
        if docker_hashes != expected:
            raise RuntimeError(f"grader_mount_hash_mismatch: host={expected} docker={docker_hashes}")
        for case in CASES:
            pair = counts.get(case.task_id, {})
            if pair.get("normal", 0) <= 0 or pair.get("sanitizer", 0) <= 0:
                raise RuntimeError(f"zero_tests: {case.task_id}: {pair}")
            if pair["normal"] != pair["sanitizer"]:
                raise RuntimeError(f"sanitizer_test_count_mismatch: {case.task_id}: {pair}")
        if set(negatives) != set(expected):
            raise RuntimeError(
                f"invariant_not_enforced: missing negative executions {set(expected)-set(negatives)}"
            )
        for case in CASES:
            negative = negatives[case.task_id]
            if negative["fixture"] != case.negative_name:
                raise RuntimeError(f"generator_output_drift: negative identity {case.task_id}")
            if negative["discovered_tests"] != counts[case.task_id]["normal"]:
                raise RuntimeError(f"sanitizer_test_count_mismatch: negative {case.task_id}")
            if (
                negative["visible_returncode"] == 0
                and negative["hidden_returncode"] == 0
            ):
                raise RuntimeError(f"invariant_not_enforced: negative passed {case.task_id}")
        inspect = subprocess.run(
            ["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"],
            check=True, text=True, capture_output=True,
        )
        image_id = inspect.stdout.strip()
        archive_hash = _sha256_file(archive)
        for case in CASES:
            record = _remedy_record(out, case, status="verified", tree_hash=expected[case.task_id])
            record.update({
                "benchmark_screen": "pass", "family_screen": "pass",
                "oracle_receipt": f".state/oracle/{case.task_id}.json",
                "test_counts": counts[case.task_id],
                "negative_fixture": negatives[case.task_id],
                "prompt_boundary": "pass", "local_status": "local_family_verified",
            })
            _write(out / ".state/remedy" / f"{case.legacy_id}.json", json.dumps(record, indent=2, sort_keys=True) + "\n", True)
            per_root = {
                "schema_version": 2, "task_id": case.task_id,
                "tree_hash": expected[case.task_id], "generator_hash": _generator_hash(),
                "reference_hashes": {
                    "header": _sha256_file(out / case.task_id / ".meta/example.h"),
                    "source": _sha256_file(out / case.task_id / ".meta/example.cpp"),
                },
                "negative_source_hash": _sha256_file(
                    out / case.task_id / ".meta/negative_topic_specific.cpp"
                ),
                "image": IMAGE, "image_id": image_id, "evidence_class": "docker_sanity",
                "locked_oracle": False, "network_policy": "none", "toolchain": tools,
                "normal_tests": counts[case.task_id]["normal"],
                "sanitizer_tests": counts[case.task_id]["sanitizer"],
                "negative_fixture": negatives[case.task_id], "status": "pass",
            }
            _write(out / ".state/oracle" / f"{case.task_id}.json", json.dumps(per_root, indent=2, sort_keys=True) + "\n", True)
        receipt = {
            "schema_version": 2, "status": "pass", "local_status": "local_family_verified",
            "evidence_class": "docker_sanity", "locked_oracle": False,
            "image": IMAGE, "image_id": image_id, "network_policy": "none",
            "archive_hash": archive_hash, "archive_tree_hashes": docker_hashes,
            "host_tree_hashes": expected, "generator_hash": _generator_hash(),
            "spec_contract_hash": _spec_contract_hash(), "toolchain": tools,
            "normal_total": sum(pair["normal"] for pair in counts.values()),
            "sanitizer_total": sum(pair["sanitizer"] for pair in counts.values()),
            "per_root_counts": counts, "negative_fixtures": len(negatives),
            "negative_test_discovery_total": sum(
                int(record["discovered_tests"]) for record in negatives.values()
            ),
            "negative_results": negatives,
            "commands": {"docker": command},
        }
        _write(out / ".state/oracle/verification.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    manifest_path = out / ".state/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.update({
        "status": "local_family_verified", "oracle_status": "pass",
        "oracle_receipts": len(CASES), "normal_tests": receipt["normal_total"],
        "sanitizer_tests": receipt["sanitizer_total"],
    })
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=ROOT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--quick-normal", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.quick_normal:
        quick_normal(args.out)
    if args.verify:
        verify(args.out)
    print(f"Wrote {len(roots)} remediated skip-list tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
