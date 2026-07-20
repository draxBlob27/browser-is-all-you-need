"""Materialize and locally reverify the clean-room v2 trie task family."""
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

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_trie_cases import CASES, Case
from w8_biayn.integrations.moonlight_trie_hard_rule_cases import (
    HARD_RULE_TRACES,
    NEGATIVE_PROFILES,
)

ROOT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/trie")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dsa/trie")
CURRICULUM = Path("docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_TRIE_CURRICULUM.md")
AUDIT_SPEC = Path("docs/aider-tasks-spec/aider-dsa/trie.md")
PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
BENCHMARK_MANIFEST = Path("manifests/aider_sft/aider-polyglot-cpp-26.json")
UPSTREAM_HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
FALLBACK_HOLDOUT_ROOT = Path(".w8-biayn/data/polyglot-benchmark/cpp/exercises/practice")
FAMILY_ID = "aider-dsa-trie-v2"
NORMALIZER = "aider-cleanroom-family-v2-hard-diversity"
MIN_ROOTS = 15
MAX_ROOTS = 20
LOCKED_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
OWNER_PATHS = (
    "src/w8_biayn/integrations/moonlight_trie_cases.py",
    "src/w8_biayn/integrations/moonlight_trie_hard_rule_cases.py",
    "src/w8_biayn/integrations/moonlight_trie_aider_task_materializer.py",
)


def _sha(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _file_hash(path: Path) -> str:
    return _sha(path.read_bytes())


def _owner_hash() -> str:
    digest = hashlib.sha256()
    for name in OWNER_PATHS:
        path = Path(name)
        digest.update(name.encode() + b"\0" + path.read_bytes() + b"\0")
    return f"sha256:{digest.hexdigest()}"


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _family_hash(out: Path) -> str:
    digest = hashlib.sha256()
    for case in sorted(CASES, key=lambda item: item.task_id):
        digest.update(case.task_id.encode() + b"\0")
        digest.update(_tree_hash(out / case.task_id).encode() + b"\0")
    return f"sha256:{digest.hexdigest()}"


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") == content:
            return
        if not force:
            raise FileExistsError(f"{path} differs; pass --force for reverify output")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _record_path(out: Path, legacy_id: str) -> Path:
    return out / ".state" / "remedy" / f"{legacy_id}.json"


def _load_planned_record(out: Path, case: Case) -> dict[str, object]:
    path = _record_path(out, case.legacy_id)
    if not path.is_file():
        raise RuntimeError(f"remedy_spec_incomplete: {path}")
    record = json.loads(path.read_text(encoding="utf-8"))
    spec = Path(str(record.get("remedy_spec_path", "")))
    if not spec.is_file() or record.get("remedy_spec_hash") != _file_hash(spec):
        raise RuntimeError(f"remedy_spec_incomplete: stale spec for {case.legacy_id}")
    expected = {
        "schema_version": "aider-task-remedy-v1",
        "task_id": case.legacy_id,
        "replacement_task_id": case.task_id,
        "disposition": "replace",
        "family_id_before": "aider-dsa-trie-v1",
        "family_id_after": FAMILY_ID,
        "selected_prompt": PROMPT,
    }
    for key, value in expected.items():
        if record.get(key) != value:
            raise RuntimeError(f"remedy_disposition_conflict: {case.legacy_id}: {key}")
    if record.get("status") not in {"planned", "implemented", "verified"}:
        raise RuntimeError(f"remedy_disposition_conflict: {case.legacy_id}: status")
    legacy = LEGACY_ROOT / case.legacy_id
    if not legacy.is_dir() or record.get("tree_hash_before") != _tree_hash(legacy):
        raise RuntimeError(f"generator_output_drift: legacy {case.legacy_id}")
    return record


def _sync_records(out: Path, *, status: str, local_status: str, oracle: dict[str, object] | None = None) -> None:
    screened = local_status != "implemented_pending_oracle"
    for case in CASES:
        record = _load_planned_record(out, case)
        record.update({
            "benchmark_screen": "pass" if screened else "pending",
            "changed_owner_paths": list(OWNER_PATHS) + [
                str(CURRICULUM), str(AUDIT_SPEC),
                "tests/test_moonlight_trie_aider_tasks.py",
                "examples/slime/moonlight_cpp_perf/prepare_trie_aider_tasks.sh",
            ],
            "duplicate_family_screen": "pass" if screened else "pending",
            "generator_revision_after": _owner_hash(),
            "license_screen": "pass",
            "local_status": local_status,
            "primary_core_objective": "achieved",
            "prompt_boundary": "pass" if screened else "pending",
            "reference_mapping": "pass" if screened else "pending",
            "status": status,
            "tree_hash_after": _tree_hash(out / case.task_id),
        })
        if oracle is not None:
            record["oracle_evidence"] = oracle
            record["oracle_evidence_status"] = "current"
        _write(_record_path(out, case.legacy_id), json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def _invalidate_stale_owner_evidence(out: Path) -> None:
    current_owner = _owner_hash()
    for case in CASES:
        path = _record_path(out, case.legacy_id)
        if not path.is_file():
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("generator_revision_after") == current_owner:
            continue
        record.update({
            "benchmark_screen": "pending",
            "duplicate_family_screen": "pending",
            "local_status": "planned_owner_regeneration",
            "oracle_evidence_status": "invalidated_by_owner_change",
            "prompt_boundary": "pending",
            "reference_mapping": "pending",
            "status": "planned",
        })
        record.pop("oracle_evidence", None)
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def _test(case: Case, body: str, label: str) -> str:
    return f"""#include "{case.task_id}.h"
#include <algorithm>
#include <array>
#include <cstddef>
#include <functional>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>
int main(){{
  int failures=0;
  const auto check=[&](bool ok){{if(!ok)++failures;}};
  using namespace curriculum;
  {body}
  check({case.class_name}().audit_for_test().valid);
  return failures==0?0:1;
}}
// {label}
"""


def _cmake() -> str:
    return """cmake_minimum_required(VERSION 3.16)
project(trie_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
add_executable(task_hard_rule "${TASK_SOURCE}" .meta/hard_rule_test.cpp)
foreach(target task_visible task_hidden task_hard_rule)
  target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_test(NAME hard_rule COMMAND task_hard_rule)
"""


def _negative_fixture(case: Case) -> str:
    profile = NEGATIVE_PROFILES[case.task_id]
    fixture = case.starter.replace(
        '#include "task.h"',
        '#include "task.h"\n#include <map>\n#include <set>\n#include <unordered_map>\n'
        '#include <utility>\n#include <vector>\n' + profile.declaration,
        1,
    )
    fixture = fixture.replace(
        "return false;",
        profile.mutation,
        1,
    )
    return fixture.replace(
        "return {false,0U,0U",
        "return {false,bad_state.size(),bad_state.size()",
        1,
    )


def build(out: Path = ROOT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() == LEGACY_ROOT.resolve():
        raise RuntimeError("LEGACY_ROOT is immutable; use the trie reverify root")
    if not MIN_ROOTS <= len(CASES) <= MAX_ROOTS:
        raise RuntimeError(
            f"generator_output_drift: hard-rule root count {len(CASES)} "
            f"outside [{MIN_ROOTS}, {MAX_ROOTS}]"
        )
    task_ids = {case.task_id for case in CASES}
    if set(HARD_RULE_TRACES) != task_ids or set(NEGATIVE_PROFILES) != task_ids:
        raise RuntimeError("generator_output_drift: hard-rule inventory")
    _invalidate_stale_owner_evidence(out)
    for case in CASES:
        _load_planned_record(out, case)
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        config = {
            "authors": ["w8-biayn"],
            "blurb": case.objective,
            "files": {
                "example": [".meta/example.h", ".meta/example.cpp"],
                "solution": ["task.h", "task.cpp"],
                "test": [
                    "task_visible_test.cpp",
                    ".meta/task_hidden_test.cpp",
                    ".meta/hard_rule_test.cpp",
                ],
            },
        }
        provenance = {
            "audit_specification": str(AUDIT_SPEC),
            "benchmark_separation": "Clean-room v2 replacement; no official Aider wording, API, test, reference, or semantic contract was used.",
            "curriculum_document": str(CURRICULUM),
            "curriculum_task_id": case.task_id,
            "family_id": FAMILY_ID,
            "legacy_task_id": case.legacy_id,
            "origin": "repository-authored clean-room trie remediation",
            "primary_core_objective": case.objective,
            "selected_prompt": PROMPT,
            "status": "local candidate artifact; not admitted SFT data",
            "version": 3,
        }
        files = {
            ".docs/introduction.md": f"# {case.class_name}\n\nA clean-room C++17 trie task: {case.objective}.\n",
            ".docs/instructions.md": (
                "# Instructions\n\nImplement the complete public API declared in the editable header. "
                f"{case.behavior} Failed mutations return false without changing observable state. "
                "Empty or invalid input follows the API-specific empty or absent result. "
                "Implement the named trie nodes, edges, traversal, counters, caches, and pruning directly. "
                "A flat map, set, sorted vector, regular expression, or scan of complete stored strings "
                "must not perform the authoritative prefix work. audit_for_test() must recompute and "
                "validate the documented representation invariant.\n"
            ),
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/example.h": case.header,
            ".meta/example.cpp": case.reference,
            ".meta/hard_rule_test.cpp": _test(
                case, HARD_RULE_TRACES[case.task_id], "hard-diversity operation trace"
            ),
            ".meta/negative_fixture.cpp": _negative_fixture(case),
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/task_hidden_test.cpp": _test(case, case.hidden, "private trace"),
            ".meta/tests.toml": (
                "[visible]\n" + f'description = "{case.objective} public behavior"\n\n'
                "[hidden]\ndescription = \"boundary and representation invariants\"\n\n"
                "[hard_rule]\n"
                'description = "independent complete-state trace after every mutation and '
                f'{NEGATIVE_PROFILES[case.task_id].name} rejection"\n'
            ),
            "CMakeLists.txt": _cmake(),
            "task.h": case.header,
            "task.cpp": case.starter,
            "task_visible_test.cpp": _test(case, case.visible, "visible contract"),
        }
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    manifest = {
        "family_id": FAMILY_ID,
        "legacy_root": str(LEGACY_ROOT),
        "owner_hash": _owner_hash(),
        "root_count": len(roots),
        "selected_prompt": PROMPT,
        "hard_rule_root_bounds": [MIN_ROOTS, MAX_ROOTS],
        "status": "implemented_pending_hard_rule_oracle",
        "task_ids": [case.task_id for case in CASES],
    }
    _write(out / ".state" / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    _sync_records(out, status="implemented", local_status="implemented_pending_oracle")
    return tuple(roots)


def _normalize(text: str) -> tuple[str, ...]:
    text = re.sub(
        r'//.*?$|/\*.*?\*/|"(?:\\.|[^"])*"|\'(?:\\.|[^\'])*\'',
        " ",
        text,
        flags=re.M | re.S,
    )
    text = re.sub(r"\b\d+\b", "#", text.lower())
    domain = {
        token
        for case in CASES
        for token in re.findall(r"[a-z]+", f"{case.legacy_id} {case.task_id} {case.class_name}")
    }
    return tuple(
        token
        for token in re.findall(r"[a-z_]+|[{}();,*&<>]", text)
        if token not in domain
    )


def _ngrams(tokens: tuple[str, ...], width: int = 5) -> set[tuple[str, ...]]:
    return {
        tokens[index : index + width]
        for index in range(max(0, len(tokens) - width + 1))
    }


def _jaccard(
    left: set[tuple[str, ...]], right: set[tuple[str, ...]]
) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


_DIVERSITY_PATHS = {
    "docs_boundary": (".docs/instructions.md",),
    "public_api_state": ("{task_id}.h",),
    "reference_control_flow": (".meta/example.cpp",),
    "public_oracle": ("task_visible_test.cpp",),
    "private_value_oracle": (
        ".meta/task_hidden_test.cpp", ".meta/hard_rule_test.cpp"
    ),
}

_DIVERSITY_THRESHOLDS = {
    "docs_boundary": 0.90,
    "public_api_state": 0.92,
    "reference_control_flow": 0.80,
    "public_oracle": 0.90,
    "private_value_oracle": 0.80,
}


def _artifact_signatures(
    root: Path, task_id: str
) -> dict[str, set[tuple[str, ...]]]:
    result: dict[str, set[tuple[str, ...]]] = {}
    combined: list[str] = []
    for dimension, templates in _DIVERSITY_PATHS.items():
        text = "\n".join(
            (root / template.format(task_id=task_id)).read_text(encoding="utf-8")
            for template in templates
        )
        combined.append(text)
        result[dimension] = _ngrams(_normalize(text))
        if not result[dimension]:
            raise RuntimeError(f"duplicate_family: empty {dimension}: {task_id}")
    result["combined"] = _ngrams(_normalize("\n".join(combined)))
    return result


def _screen(out: Path) -> dict[str, object]:
    manifest = json.loads(BENCHMARK_MANIFEST.read_text(encoding="utf-8"))
    holdout_ids = set(manifest["task_ids"])
    task_ids = {case.task_id for case in CASES}
    if task_ids & holdout_ids:
        raise RuntimeError("benchmark_id_overlap")
    signatures: dict[str, dict[str, set[tuple[str, ...]]]] = {}
    negative_signatures: dict[str, set[tuple[str, ...]]] = {}
    for case in CASES:
        root = out / case.task_id
        signatures[case.task_id] = _artifact_signatures(root, case.task_id)
        negative_signatures[case.task_id] = _ngrams(
            _normalize(
                (root / ".meta/negative_fixture.cpp").read_text(encoding="utf-8")
            )
        )
    strongest_by_dimension: dict[str, dict[str, object]] = {
        dimension: {"pair": None, "jaccard": 0.0}
        for dimension in (*_DIVERSITY_PATHS, "combined", "negative_fixture")
    }
    decisions: list[dict[str, object]] = []
    ids = sorted(signatures)
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            scores = {
                dimension: _jaccard(
                    signatures[left][dimension], signatures[right][dimension]
                )
                for dimension in (*_DIVERSITY_PATHS, "combined")
            }
            scores["negative_fixture"] = _jaccard(
                negative_signatures[left], negative_signatures[right]
            )
            for dimension, score in scores.items():
                if score > float(strongest_by_dimension[dimension]["jaccard"]):
                    strongest_by_dimension[dimension] = {
                        "pair": [left, right], "jaccard": round(score, 6)
                    }
            distinct_dimensions = sum(
                scores[dimension] < threshold
                for dimension, threshold in _DIVERSITY_THRESHOLDS.items()
            )
            clone = (
                scores["combined"] >= 0.62
                or scores["reference_control_flow"] >= 0.80
                and scores["private_value_oracle"] >= 0.80
                or scores["public_api_state"] >= 0.92
                and scores["docs_boundary"] >= 0.90
                and scores["reference_control_flow"] >= 0.70
                or distinct_dimensions < 3
                or scores["negative_fixture"] == 1.0
            )
            if clone:
                raise RuntimeError(
                    f"duplicate_family: {left} and {right}: "
                    + ", ".join(
                        f"{name}={value:.3f}" for name, value in scores.items()
                    )
                )
            decisions.append({
                "pair": [left, right],
                "distinct_dimensions": distinct_dimensions,
                "scores": {name: round(value, 6) for name, value in scores.items()},
            })
    upstream = UPSTREAM_HOLDOUT_ROOT
    if not upstream.is_dir():
        upstream = FALLBACK_HOLDOUT_ROOT
    inventory: list[str] = []
    strongest_holdout: dict[str, object] = {"pair": None, "jaccard": 0.0}
    holdout_signatures: dict[str, set[tuple[str, ...]]] = {}
    if upstream.is_dir():
        for holdout in sorted(holdout_ids):
            root = upstream / holdout
            if not root.is_dir():
                continue
            paths = [
                path for path in root.rglob("*")
                if path.is_file() and path.suffix in {".md", ".h", ".hpp", ".cc", ".cpp", ".toml"}
            ]
            inventory.append(holdout)
            holdout_signatures[holdout] = _ngrams(
                _normalize("\n".join(path.read_text(encoding="utf-8", errors="replace") for path in paths))
            )
    if len(holdout_signatures) != len(holdout_ids):
        raise RuntimeError(
            f"benchmark_content_not_completed: found {len(inventory)}/{len(holdout_ids)} holdouts"
        )
    for task_id, dimensions in signatures.items():
        signature = dimensions["combined"]
        for holdout, holdout_signature in holdout_signatures.items():
            if not holdout_signature:
                continue
            score = len(signature & holdout_signature) / len(signature | holdout_signature)
            if score > float(strongest_holdout["jaccard"]):
                strongest_holdout = {"pair": [task_id, holdout], "jaccard": round(score, 6)}
            if score >= 0.60:
                raise RuntimeError(f"benchmark_content_overlap: {task_id} and {holdout}")
    return {
        "benchmark_content_screen": "pass",
        "benchmark_inventory": inventory,
        "family_duplicate_screen": "pass",
        "hard_diversity_dimensions": list(_DIVERSITY_PATHS),
        "hard_diversity_pair_decisions": decisions,
        "hard_diversity_thresholds": _DIVERSITY_THRESHOLDS,
        "normalizer": NORMALIZER,
        "pair_count": len(CASES) * (len(CASES) - 1) // 2,
        "strongest_family_match_by_dimension": strongest_by_dimension,
        "strongest_holdout_match": strongest_holdout,
    }


def verify_core(out: Path = ROOT) -> dict[str, object]:
    if not MIN_ROOTS <= len(CASES) <= MAX_ROOTS:
        raise RuntimeError("generator_output_drift: hard-rule count bounds")
    if len({case.legacy_id for case in CASES}) != len(CASES):
        raise RuntimeError("generator_output_drift: legacy inventory")
    if len({case.task_id for case in CASES}) != len(CASES):
        raise RuntimeError("duplicate_family: replacement IDs")
    prompt_files = 0
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta" / "config.json").read_text())
        expected_solution = [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        if config["files"]["solution"] != expected_solution:
            raise RuntimeError(f"target_reference_mismatch: {case.task_id}")
        if config["files"]["example"] != [".meta/example.h", ".meta/example.cpp"]:
            raise RuntimeError(f"target_reference_mismatch: {case.task_id}")
        if config["files"]["test"] != [
            "task_visible_test.cpp",
            ".meta/task_hidden_test.cpp",
            ".meta/hard_rule_test.cpp",
        ]:
            raise RuntimeError(f"target_reference_mismatch: {case.task_id}: tests")
        prompt = build_prompt(load_task(root))
        for private in (
            ".meta/example", "task_hidden_test", "hard_rule_test",
            "negative_fixture", "CMakeLists.txt", "provenance.json",
        ):
            if private in prompt:
                raise RuntimeError(f"prompt_contract_incomplete: {case.task_id}: {private}")
        for public in expected_solution:
            if public not in prompt:
                raise RuntimeError(f"prompt_contract_incomplete: {case.task_id}: {public}")
        prompt_files += len(expected_solution)
        reference = (root / ".meta" / "example.cpp").read_text(encoding="utf-8")
        missing = [token for token in case.required_tokens if token not in reference]
        if missing:
            raise RuntimeError(f"invariant_not_enforced: {case.task_id}: {', '.join(missing)}")
        if "std::map<std::string, int> entries_" in reference or "for (const auto& e : entries_)" in reference:
            raise RuntimeError(f"invariant_not_enforced: {case.task_id}: legacy flat map")
        trace = (root / ".meta/hard_rule_test.cpp").read_text(encoding="utf-8")
        operations = {
            name
            for name in re.findall(
                r"\b([a-z][a-z0-9_]*)\([^;{}]*\)(?:\s+const)?;", case.header
            )
            if name != "audit_for_test"
        }
        absent_operations = sorted(
            operation for operation in operations if f".{operation}(" not in trace
        )
        if absent_operations or "model" not in trace or "verify" not in trace:
            raise RuntimeError(
                f"invariant_not_enforced: {case.task_id}: incomplete hard-rule trace: "
                + ", ".join(absent_operations)
            )
        negative = (root / ".meta/negative_fixture.cpp").read_text(encoding="utf-8")
        profile = NEGATIVE_PROFILES[case.task_id]
        if profile.declaration not in negative or profile.mutation not in negative:
            raise RuntimeError(
                f"invariant_not_enforced: {case.task_id}: {profile.name}"
            )
        _load_planned_record(out, case)
    screen = _screen(out)
    result = {
        **screen,
        "hard_rule_adversarial_controls": [
            "identifier_renamed_clone",
            "constants_policy_only_clone",
            "opposite_end_selection_clone",
        ],
        "hard_rule_root_bounds": [MIN_ROOTS, MAX_ROOTS],
        "negative_fixtures": {
            case.task_id: NEGATIVE_PROFILES[case.task_id].name for case in CASES
        },
        "negative_fixture_expected_result": "invariant_not_enforced",
        "primary_core_objective": "achieved",
        "prompt_boundary": "pass",
        "prompt_editable_file_count": prompt_files,
        "reference_mapping": "pass",
        "root_count": len(CASES),
        "status": "pass",
        "unique_objectives": len({case.objective for case in CASES}),
    }
    _write(out / ".state" / "core-verification.json", json.dumps(result, indent=2, sort_keys=True) + "\n", True)
    _write(out / ".state" / "family-screen.json", json.dumps(screen, indent=2, sort_keys=True) + "\n", True)
    _sync_records(
        out,
        status="implemented",
        local_status="semantically_admitted_pending_oracle",
    )
    return result


def _ctest_count(output: str) -> int:
    match = re.search(r"Total Tests:\s*(\d+)", output)
    if not match:
        raise RuntimeError("test_discovery_failed")
    count = int(match.group(1))
    if count <= 0:
        raise RuntimeError("zero_tests")
    return count


def _run_build(
    root: Path,
    source: Path,
    build_dir: Path,
    sanitizer: bool,
    *,
    expect_test_failure: bool = False,
) -> int:
    flags = []
    if sanitizer:
        flags = [
            "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
            "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
        ]
    subprocess.run(
        [
            "cmake", "-S", str(root), "-B", str(build_dir), "-G", "Unix Makefiles",
            f"-DTASK_SOURCE={source}", *flags,
        ],
        check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["cmake", "--build", str(build_dir), "--parallel", "2"],
        check=True, capture_output=True, text=True,
    )
    discovery = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "-N"],
        check=True, capture_output=True, text=True,
    )
    count = _ctest_count(discovery.stdout + discovery.stderr)
    run = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
        check=False, capture_output=True, text=True,
        env={**os.environ, "ASAN_OPTIONS": "detect_leaks=0"},
    )
    if expect_test_failure:
        if run.returncode == 0:
            raise RuntimeError("invariant_not_enforced: topic-specific substitute passed")
    elif run.returncode != 0:
        raise RuntimeError(f"reference_tests_failed: {root.name}: {run.stdout[-2000:]}")
    return count


def verify_host(out: Path = ROOT) -> dict[str, object]:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        raise RuntimeError("host verification requires cmake and c++")
    verify_core(out)
    receipts: list[dict[str, object]] = []
    for case in CASES:
        root = out / case.task_id
        with tempfile.TemporaryDirectory(prefix=f"trie-host-{case.task_id}-") as temp_dir:
            copied = Path(temp_dir) / case.task_id
            shutil.copytree(root, copied)
            normal = _run_build(copied, copied / ".meta" / "example.cpp", copied / "build-normal", False)
            sanitizer = _run_build(copied, copied / ".meta" / "example.cpp", copied / "build-sanitizer", True)
            if normal != sanitizer:
                raise RuntimeError(f"sanitizer_test_count_mismatch: {case.task_id}")
            negative = _run_build(
                copied, copied / ".meta" / "negative_fixture.cpp",
                copied / "build-negative", False, expect_test_failure=True,
            )
        receipts.append({
            "negative_fixture_discovered_tests": negative,
            "normal_discovered_tests": normal,
            "sanitizer_discovered_tests": sanitizer,
            "task_id": case.task_id,
        })
    result = {
        "environment": "host_diagnostic",
        "local_family_verified": False,
        "receipts": receipts,
        "status": "pass",
    }
    _write(out / ".state" / "host-verification.json", json.dumps(result, indent=2, sort_keys=True) + "\n", True)
    return result


def _docker_script(task_ids: list[str], expected_hash: str) -> str:
    quoted = " ".join(task_ids)
    hash_code = (
        "from pathlib import Path;import hashlib;"
        "root=Path('/tasks');d=hashlib.sha256();"
        f"ids={task_ids!r};"
        "th=lambda r:'sha256:'+hashlib.sha256(b''.join("
        "p.relative_to(r).as_posix().encode()+b'\\0'+p.read_bytes() "
        "for p in sorted(x for x in r.rglob('*') if x.is_file()))).hexdigest();"
        "[(d.update(i.encode()+b'\\0'),d.update(th(root/i).encode()+b'\\0')) "
        "for i in sorted(ids)];print('sha256:'+d.hexdigest())"
    )
    return f"""set -euo pipefail
echo TOOLCHAIN_CXX
c++ --version | head -1
echo TOOLCHAIN_CXX_PATH "$(command -v c++)"
echo TOOLCHAIN_CXX_SHA256 "$(sha256sum "$(command -v c++)" | cut -d' ' -f1)"
echo TOOLCHAIN_CMAKE
cmake --version | head -1
echo TOOLCHAIN_CMAKE_PATH "$(command -v cmake)"
echo TOOLCHAIN_CMAKE_SHA256 "$(sha256sum "$(command -v cmake)" | cut -d' ' -f1)"
mounted_hash="$(python3 -c {json.dumps(hash_code)})"
test "$mounted_hash" = "{expected_hash}"
echo MOUNT_HASH "$mounted_hash"
for task in {quoted}; do
  normal="/tmp/build-$task-normal"
  cmake -S "/tasks/$task" -B "$normal" -G "Unix Makefiles" \
    "-DTASK_SOURCE=/tasks/$task/.meta/example.cpp" >/tmp/configure.log
  cmake --build "$normal" --parallel 2 >/tmp/build.log
  count="$(ctest --test-dir "$normal" -N | sed -n 's/.*Total Tests: *//p')"
  test "$count" = 3
  ctest --test-dir "$normal" --output-on-failure
  echo RESULT "$task" normal "$count"

  sanitizer="/tmp/build-$task-sanitizer"
  cmake -S "/tasks/$task" -B "$sanitizer" -G "Unix Makefiles" \
    "-DTASK_SOURCE=/tasks/$task/.meta/example.cpp" \
    "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" \
    "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined" >/tmp/configure.log
  cmake --build "$sanitizer" --parallel 2 >/tmp/build.log
  count="$(ctest --test-dir "$sanitizer" -N | sed -n 's/.*Total Tests: *//p')"
  test "$count" = 3
  ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$sanitizer" --output-on-failure
  echo RESULT "$task" sanitizer "$count"

  negative="/tmp/build-$task-negative"
  cmake -S "/tasks/$task" -B "$negative" -G "Unix Makefiles" \
    "-DTASK_SOURCE=/tasks/$task/.meta/negative_fixture.cpp" >/tmp/configure-negative.log
  cmake --build "$negative" --parallel 2 >/tmp/build-negative.log
  count="$(ctest --test-dir "$negative" -N | sed -n 's/.*Total Tests: *//p')"
  test "$count" = 3
  if ctest --test-dir "$negative" --output-on-failure >/tmp/negative.log 2>&1; then
    echo "negative fixture unexpectedly passed: $task"
    exit 91
  fi
  echo NEGATIVE "$task" "$count"
done
"""


def _audit_live_receipt(out: Path) -> dict[str, object]:
    receipt_path = out / ".state" / "oracle-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("status") != "pass":
        raise RuntimeError("docker_sanity_not_completed")
    if receipt.get("owner_hash") != _owner_hash():
        raise RuntimeError("generator_output_drift: receipt owner")
    if receipt.get("family_hash") != _family_hash(out):
        raise RuntimeError("grader_mount_hash_mismatch")
    verifier_path = out / str(receipt.get("verifier_script", ""))
    if (
        not verifier_path.is_file()
        or receipt.get("verifier_script_hash") != _file_hash(verifier_path)
    ):
        raise RuntimeError("generator_output_drift: verifier script")
    by_task = {item["task_id"]: item for item in receipt.get("tasks", [])}
    for case in CASES:
        root = out / case.task_id
        item = by_task.get(case.task_id)
        if item is None or item.get("tree_hash") != _tree_hash(root):
            raise RuntimeError(f"generator_output_drift: receipt tree: {case.task_id}")
        expected_references = {
            ".meta/example.cpp": _file_hash(root / ".meta/example.cpp"),
            ".meta/example.h": _file_hash(root / ".meta/example.h"),
        }
        expected_tests = {
            ".meta/hard_rule_test.cpp": _file_hash(root / ".meta/hard_rule_test.cpp"),
            ".meta/task_hidden_test.cpp": _file_hash(root / ".meta/task_hidden_test.cpp"),
            "task_visible_test.cpp": _file_hash(root / "task_visible_test.cpp"),
        }
        if item.get("reference_hashes") != expected_references:
            raise RuntimeError(f"generator_output_drift: references: {case.task_id}")
        if item.get("test_hashes") != expected_tests:
            raise RuntimeError(f"generator_output_drift: tests: {case.task_id}")
        if item.get("negative_fixture_hash") != _file_hash(
            root / ".meta/negative_fixture.cpp"
        ):
            raise RuntimeError(f"generator_output_drift: negative: {case.task_id}")
    screen = json.loads(
        (out / ".state" / "family-screen.json").read_text(encoding="utf-8")
    )
    if (
        screen.get("pair_count") != len(CASES) * (len(CASES) - 1) // 2
        or len(screen.get("hard_diversity_pair_decisions", []))
        != screen["pair_count"]
    ):
        raise RuntimeError("duplicate_family: incomplete final pair audit")
    result = {
        "family_hash": receipt["family_hash"],
        "hard_diversity_pair_count": screen["pair_count"],
        "owner_hash": receipt["owner_hash"],
        "receipt_hash": _file_hash(receipt_path),
        "record_count": len(CASES),
        "status": "pass",
        "task_hash_bindings": len(by_task),
        "verifier_script_hash": receipt["verifier_script_hash"],
    }
    _write(
        out / ".state" / "final-live-audit.json",
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        True,
    )
    return result


def verify_docker(out: Path = ROOT) -> dict[str, object]:
    core = verify_core(out)
    family_hash = _family_hash(out)
    task_ids = [case.task_id for case in CASES]
    verifier_script = _docker_script(task_ids, family_hash)
    verifier_path = out / ".state" / "docker-verifier.sh"
    _write(verifier_path, verifier_script, True)
    command = [
        "docker", "run", "--rm", "--network", "none",
        "--mount", f"type=bind,src={out.resolve()},dst=/tasks,readonly",
        LOCKED_IMAGE, "bash", "/tasks/.state/docker-verifier.sh",
    ]
    try:
        image = subprocess.run(
            ["docker", "image", "inspect", LOCKED_IMAGE, "--format", "{{.Id}}"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        run = subprocess.run(command, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        stdout = exc.stdout if isinstance(exc, subprocess.CalledProcessError) else ""
        stderr = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else ""
        result = {
            "blocked_command": command,
            "error": str(exc),
            "stdout_tail": (stdout or "")[-4000:],
            "stderr_tail": (stderr or "")[-4000:],
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "status": "not_completed",
        }
        _write(out / ".state" / "oracle-receipt.json", json.dumps(result, indent=2, sort_keys=True) + "\n", True)
        raise RuntimeError("docker_sanity_not_completed") from exc
    output = run.stdout + run.stderr
    counts: dict[str, dict[str, int]] = {task_id: {} for task_id in task_ids}
    negative: dict[str, int] = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) == 4 and fields[0] == "RESULT":
            counts[fields[1]][fields[2]] = int(fields[3])
        elif len(fields) == 3 and fields[0] == "NEGATIVE":
            negative[fields[1]] = int(fields[2])
    for task_id in task_ids:
        if counts[task_id] != {"normal": 3, "sanitizer": 3}:
            raise RuntimeError(f"sanitizer_test_count_mismatch: {task_id}")
        if negative.get(task_id) != 3:
            raise RuntimeError(f"invariant_not_enforced: {task_id}")
    result = {
        "benchmark_screen": core["benchmark_content_screen"],
        "command": command,
        "evidence_class": "docker_sanity",
        "executed_negative_fixtures": len(negative),
        "family_duplicate_screen": core["family_duplicate_screen"],
        "family_hash": family_hash,
        "image": LOCKED_IMAGE,
        "image_id": image,
        "locked_oracle": False,
        "network_policy": "none",
        "owner_hash": _owner_hash(),
        "prompt_boundary": core["prompt_boundary"],
        "reference_mapping": core["reference_mapping"],
        "status": "pass",
        "verifier_script": ".state/docker-verifier.sh",
        "verifier_script_hash": _file_hash(verifier_path),
        "tasks": [
            {
                "negative_fixture_discovered_tests": negative[task_id],
                "negative_fixture_hash": _file_hash(
                    out / task_id / ".meta/negative_fixture.cpp"
                ),
                "negative_fixture_name": NEGATIVE_PROFILES[task_id].name,
                "normal_discovered_tests": counts[task_id]["normal"],
                "reference_hashes": {
                    ".meta/example.cpp": _file_hash(
                        out / task_id / ".meta/example.cpp"
                    ),
                    ".meta/example.h": _file_hash(
                        out / task_id / ".meta/example.h"
                    ),
                },
                "sanitizer_discovered_tests": counts[task_id]["sanitizer"],
                "task_id": task_id,
                "test_hashes": {
                    ".meta/hard_rule_test.cpp": _file_hash(
                        out / task_id / ".meta/hard_rule_test.cpp"
                    ),
                    ".meta/task_hidden_test.cpp": _file_hash(
                        out / task_id / ".meta/task_hidden_test.cpp"
                    ),
                    "task_visible_test.cpp": _file_hash(
                        out / task_id / "task_visible_test.cpp"
                    ),
                },
                "tree_hash": _tree_hash(out / task_id),
            }
            for task_id in task_ids
        ],
        "toolchain_lines": [
            line for line in output.splitlines()
            if line.startswith((
                "c++ ", "cmake version", "MOUNT_HASH", "TOOLCHAIN_"
            ))
        ],
    }
    _write(out / ".state" / "oracle-receipt.json", json.dumps(result, indent=2, sort_keys=True) + "\n", True)
    oracle_binding = {
        "evidence_class": "docker_sanity",
        "family_hash": family_hash,
        "image": LOCKED_IMAGE,
        "locked_oracle": False,
        "network_policy": "none",
        "normal_discovered_tests": 3,
        "receipt": ".state/oracle-receipt.json",
        "receipt_hash": _file_hash(out / ".state" / "oracle-receipt.json"),
        "sanitizer_discovered_tests": 3,
    }
    _sync_records(
        out, status="verified", local_status="local_family_verified",
        oracle=oracle_binding,
    )
    manifest_path = out / ".state" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "final_live_audit": ".state/final-live-audit.json",
        "family_hash": family_hash,
        "normal_discovered_tests_per_root": 3,
        "oracle_receipt": ".state/oracle-receipt.json",
        "oracle_receipt_hash": _file_hash(out / ".state" / "oracle-receipt.json"),
        "sanitizer_discovered_tests_per_root": 3,
        "status": "local_family_verified",
    })
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    final_audit = _audit_live_receipt(out)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["final_live_audit_hash"] = _file_hash(
        out / ".state" / "final-live-audit.json"
    )
    manifest["final_live_audit_receipt_hash"] = final_audit["receipt_hash"]
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core or args.verify_host or args.verify:
        verify_core(args.out)
    if args.verify_host:
        verify_host(args.out)
    if args.verify:
        verify_docker(args.out)
    print(f"Wrote {len(roots)} trie task-spec v3 tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
