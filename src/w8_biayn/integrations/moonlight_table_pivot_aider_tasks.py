"""Remediate and locally reverify the table-pivot Aider task family."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from itertools import combinations
from pathlib import Path, PurePosixPath
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_table_pivot_cases import CASES, PivotCase

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/table-pivot"
)
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-text-grid-reshaping/table-pivot")
CURRICULUM = (
    "docs/aider-synthetic/aider-synthetic-text-grid-reshaping/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_TABLE_PIVOT_CURRICULUM.md"
)
FAMILY_SPEC = "docs/aider-tasks-spec/aider-text-grid-reshaping/table-pivot.md"
PROMPT_PATH = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
GENERATOR_PATH = "src/w8_biayn/integrations/moonlight_table_pivot_aider_tasks.py"
CASES_PATH = "src/w8_biayn/integrations/moonlight_table_pivot_cases.py"
FAMILY_ID_BEFORE = "aider-text-grid-reshaping-table-pivot-v1-template"
FAMILY_ID = "aider-text-grid-reshaping-table-pivot-v2"
# The v1 owner was an untracked workspace file, so no Git blob survives the
# audit. Bind its immutable emitted evidence bundle instead of inventing a
# source revision; every record also carries its root-specific pre-change hash.
LEGACY_GENERATOR_REVISION = "sha256:5f9be13006a512c6b4ef09efe7099ab45e9b81125250c928d8fb0911cdc66a9f"
SEMANTIC_NORMALIZER = "table-pivot-v2-identifier-literal-endpoint-neutral-7gram"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
DEFAULT_HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
TASKS = CASES
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
    "owned_state_or_algorithm": 0.90,
    "mutation_or_selection_rules": 0.90,
    "invalid_and_boundary_behavior": 0.95,
    "reference_control_flow": 0.90,
    "deterministic_oracle": 0.98,
    "topic_specific_negative_fixture": 0.90,
}
OFFICIAL_AIDER_CPP_HOLDOUTS = frozenset(
    {
        "all-your-base", "allergies", "bank-account", "binary-search-tree",
        "circular-buffer", "clock", "complex-numbers", "crypto-square", "diamond",
        "dnd-character", "gigasecond", "grade-school", "kindergarten-garden",
        "knapsack", "linked-list", "meetup", "parallel-letter-frequency",
        "perfect-numbers", "phone-number", "queen-attack", "robot-name", "space-age",
        "spiral-matrix", "sublist", "yacht", "zebra-puzzle",
    }
)
REMEDY_HEADINGS = (
    "Identity", "Objective", "Public API", "Behavior table",
    "Implementation invariant", "Starter and reference", "Tests",
    "Files and metadata", "Build/oracle", "Family/contamination",
    "Optional dataset handoff", "Acceptance",
)

CMAKE = """cmake_minimum_required(VERSION 3.16)
project(table_pivot_v2 LANGUAGES CXX)
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
    for path in sorted(
        p
        for p in root.rglob("*")
        if p.is_file() and ".state" not in p.relative_to(root).parts
    ):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return _sha_bytes(digest.digest())


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _starter(case: PivotCase) -> str:
    match = re.search(r"namespace curriculum \{\n(.*?)\)\s*\{", case.reference, re.S)
    if match is None:
        _fail("header_source_incoherent", case.task_id)
    return f'#include "task.h"\nnamespace curriculum {{\n{match.group(1)}) {{ return {{}}; }}\n}}  // namespace curriculum\n'


def _negative_source(case: PivotCase) -> str:
    if case.negative_old not in case.reference:
        _fail("invariant_not_enforced", f"negative mutation drift: {case.task_id}")
    return case.reference.replace(case.negative_old, case.negative_new)


def _remedy_markdown(case: PivotCase) -> str:
    revision = 2 if case.disposition == "repair-in-place" else 1
    return f"""## Identity

Task ID: `{case.task_id}`; legacy root: `{case.legacy_id}`; task-spec revision: {revision}; family ID: `{FAMILY_ID}/{case.task_id}`; disposition: `{case.disposition}`; source inventory: `table-pivot-legacy-v1`; license result: repository-authored/pass; generator: `{GENERATOR_PATH}` plus `{CASES_PATH}`; benchmark screen: pending. Selected prompt: `{PROMPT_PATH}` with `FAMILY_NAME=table-pivot`, `FAMILY_TYPE=aider-text-grid-reshaping`.

## Objective

{case.objective}

## Public API

C++17 namespace `curriculum`; editable order is `{case.task_id}.h`, then `{case.task_id}.cpp`. Complete API: `{case.public_api}`. Inputs and outputs are owned values; invalid input returns `valid=false` without partial rows.

## Behavior table

Valid, invalid, duplicate, absent, empty, mutation, ordering, tie, signed-arithmetic, overflow, and boundary behavior are specified in `.docs/instructions.md`. The public boundary examples and both deterministic executables enforce the published rules. No private test introduces an undisclosed rule.

## Implementation invariant

Required mechanism: {case.profile}. Required emitted marker: `{case.marker}`. Forbidden substitutes are the legacy generic `PivotBatch`/`PivotRow` map template, noun renaming, a policy-only branch, hard-coded examples, another root's algorithm, and benchmark assets. Topic negative: {case.negative_reason}.

## Starter and reference

The task-named header declares the complete API. The task-named source is a coherent incomplete stub. `.meta/example.cpp` independently implements the mechanism and imports neither the legacy renderer, hidden fixtures, nor an official holdout. The named negative mutation is a strict-compiling false substitute.

## Tests

`task_visible_test.cpp` covers ordinary published behavior. `.meta/task_hidden_test.cpp` covers empty, invalid, duplicate/absent, tie/order, and boundary behavior. `.meta/negative_false_substitute.cpp` must compile under the same warnings and be rejected by executed tests. The all-pairs screen derives all seven hard-rule dimensions from emitted docs, API, reference, visible/private tests, and the negative source. Domain/identifier-renamed, constants/policy-only, and opposite-end-selection clones must be rejected by the production comparator.

## Files and metadata

Solutions: `{case.task_id}.h`, `{case.task_id}.cpp`; visible test: `task_visible_test.cpp`; private test: `.meta/task_hidden_test.cpp`; references: `.meta/example.h`, `.meta/example.cpp`; false substitute: `.meta/negative_false_substitute.cpp`. Config maps one reference per solution suffix. Docs, tests, metadata, CMake, references, controls, manifests, and receipts stay private.

## Build/oracle

C++17, `-Wall -Wextra -Wpedantic -Werror`, explicit `Unix Makefiles`, compiler `c++`, and exactly two positive CTest discoveries. Run clean normal and fresh ASan/UBSan builds in `{SANITY_IMAGE}` with Docker network `none`. The receipt binds live and mounted tree hashes, owner/case/reference/negative hashes, immutable image, compiler/CMake identities, commands, and equal counts.

## Family/contamination

Compare all 190 v2 pairs and all 520 available official-holdout comparisons using `{SEMANTIC_NORMALIZER}` over emitted artifacts. The shared legacy template is rejected. Family and permanent-holdout decisions cannot be waived.

## Optional dataset handoff

`not_requested`. No JSONL, token/mask evidence, split, export, consumer verification, training, or release is authorized.

## Acceptance

Run focused pytest, owner `--verify-core`, host `--verify` for iteration, and owner `--docker-sanity`. Require deterministic generation, strict prompt/role/reference boundaries, 190 seven-axis pair decisions, three adversarial controls, the 26-root holdout screen, executed rejection of all 20 topic negatives, and two equal positive normal/fresh-sanitizer tests per root. Stable failures include `remedy_spec_incomplete`, `prompt_contract_incomplete`, `invariant_not_enforced`, `duplicate_family`, `benchmark_content_overlap`, `generator_output_drift`, `negative_fixture_not_rejected`, `grader_mount_hash_mismatch`, and `sanitizer_test_count_mismatch`.
"""


def _write_remedies(out: Path, force: bool) -> None:
    remedy_root = out / ".state/remedy"
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
            "generator_revision_basis": "legacy_family_tree_hash; pre-change owner source was untracked",
            "selected_prompt": PROMPT_PATH,
            "user_inputs": {"FAMILY_NAME": "table-pivot", "FAMILY_TYPE": "aider-text-grid-reshaping"},
            "finding_ids": [
                "TP-F1-shared-pivot-template", "TP-F2-policy-only-duplicates",
                "TP-F3-objective-contract-mismatch", "TP-F4-host-only-oracle",
                "TP-F5-missing-executed-negatives", "TP-F6-missing-semantic-screen",
                "TP-F7-stale-hard-rule-reverification",
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
        _write(remedy_root / f"{case.task_id}.md", markdown, force)
        record_path = remedy_root / f"{case.task_id}.json"
        if record_path.is_file() and not force:
            existing = json.loads(record_path.read_text(encoding="utf-8"))
            if (
                existing.get("status") == "verified"
                and existing.get("remedy_spec_hash") == record["remedy_spec_hash"]
                and existing.get("tree_hash_before") == record["tree_hash_before"]
                and existing.get("disposition") == record["disposition"]
            ):
                continue
        _write(record_path, json.dumps(record, indent=2, sort_keys=True) + "\n", force)


def _case_files(case: PivotCase) -> dict[str, str]:
    config = {
        "authors": ["w8-biayn"],
        "blurb": case.objective,
        "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]},
    }
    provenance = {
        "family_id": FAMILY_ID, "task_id": case.task_id, "legacy_task_id": case.legacy_id,
        "disposition": case.disposition, "curriculum_document": CURRICULUM,
        "family_spec": FAMILY_SPEC, "selected_prompt": PROMPT_PATH,
        "origin": "independently authored repository remediation",
        "license_result": "repository-authored/pass", "semantic_profile": case.profile,
        "primary_core_objective": "achieved",
        "status": "local candidate artifact; dataset handoff not requested",
    }
    return {
        ".docs/introduction.md": f"# {case.title}\n\n{case.objective}\n",
        ".docs/instructions.md": f"# Instructions\n\n{case.instructions}\n",
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": f'[visible]\ndescription = "public behavior for {case.title}"\n\n[hidden]\ndescription = "invalid, duplicate, absent, ordering, boundary, and {case.negative_reason} rejection"\n',
        "task.h": case.header, "task.cpp": _starter(case),
        ".meta/example.h": case.header, ".meta/example.cpp": case.reference,
        ".meta/negative_false_substitute.cpp": _negative_source(case),
        "task_visible_test.cpp": case.visible_test,
        ".meta/task_hidden_test.cpp": case.hidden_test,
        "CMakeLists.txt": CMAKE,
    }


def _replace_required(content: str, old: str, new: str, control: str) -> str:
    if old not in content:
        _fail("invariant_not_enforced", f"{control}: missing mutation anchor {old!r}")
    return content.replace(old, new)


def _clone_control(base_root: Path, name: str) -> tuple[dict[str, str], tuple[str, ...]]:
    files = {
        path.relative_to(base_root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(base_root.rglob("*"))
        if path.is_file()
    }
    mutated = dict(files)
    if name == "domain-identifier-renamed-clone":
        for relative, content in mutated.items():
            if relative == "CMakeLists.txt":
                continue
            for old, new in (
                ("Call", "Desk"),
                ("call", "desk"),
                ("Agent", "Clerk"),
                ("agent", "clerk"),
            ):
                content = content.replace(old, new)
            # The control is a full emitted-root clone, so its configured file
            # names and include paths remain those of the source root.
            content = content.replace("pivot-desk-center", "pivot-call-center")
            mutated[relative] = content
    elif name == "constants-policy-clone":
        instructions = ".docs/instructions.md"
        mutated[instructions] = _replace_required(
            mutated[instructions],
            "a nonnegative handled count",
            "a strictly positive handled count",
            name,
        )
        mutated[instructions] = _replace_required(
            mutated[instructions],
            "; an all-zero row chooses the first shift",
            "",
            name,
        )
        for relative in (".meta/example.cpp", ".meta/negative_false_substitute.cpp"):
            mutated[relative] = _replace_required(
                mutated[relative], "call.handled<0", "call.handled<=0", name
            )
        hidden = ".meta/task_hidden_test.cpp"
        mutated[hidden] = _replace_required(
            mutated[hidden],
            'const auto z=curriculum::pivot_calls({"a","b"},{{"x","b",0}});check(z.valid&&z.rows[0].busiest_shift==0);',
            'check(!curriculum::pivot_calls({"a","b"},{{"x","b",0}}).valid);',
            name,
        )
    elif name == "opposite-end-selection-clone":
        for relative in (
            ".docs/introduction.md",
            ".docs/instructions.md",
            ".meta/config.json",
            ".meta/provenance.json",
        ):
            mutated[relative] = (
                mutated[relative]
                .replace("earliest", "latest")
                .replace("first shift", "last shift")
            )
        reference = _replace_required(
            mutated[".meta/example.cpp"],
            "row.busiest_shift=0;",
            "row.busiest_shift=static_cast<int>(row.counts.size())-1;",
            name,
        )
        reference = _replace_required(
            reference,
            ">row.counts[static_cast<std::size_t>(row.busiest_shift)]",
            ">=row.counts[static_cast<std::size_t>(row.busiest_shift)]",
            name,
        )
        mutated[".meta/example.cpp"] = reference
        mutated["task_visible_test.cpp"] = _replace_required(
            mutated["task_visible_test.cpp"],
            'rows[0].busiest_shift==0',
            'rows[0].busiest_shift==1',
            name,
        )
        mutated[".meta/task_hidden_test.cpp"] = _replace_required(
            mutated[".meta/task_hidden_test.cpp"],
            "busiest_shift==0",
            "busiest_shift==1",
            name,
        )
        # Under the latest-tie contract, the coherent false substitute chooses
        # the earliest tied index instead.
        negative = _replace_required(
            reference,
            "row.busiest_shift=static_cast<int>(row.counts.size())-1;",
            "row.busiest_shift=0;",
            name,
        )
        mutated[".meta/negative_false_substitute.cpp"] = _replace_required(
            negative,
            ">=row.counts[static_cast<std::size_t>(row.busiest_shift)]",
            ">row.counts[static_cast<std::size_t>(row.busiest_shift)]",
            name,
        )
    else:
        _fail("invariant_not_enforced", name)
    changed = tuple(sorted(relative for relative in files if files[relative] != mutated[relative]))
    if not changed:
        _fail("invariant_not_enforced", f"{name}: empty control mutation")
    return mutated, changed


def _write_controls(out: Path, force: bool) -> None:
    root = out / ".state/hard-rule-controls"
    base_root = out / CASES[0].task_id
    controls = {}
    for name in ("domain-identifier-renamed-clone", "constants-policy-clone", "opposite-end-selection-clone"):
        files, changed = _clone_control(base_root, name)
        for relative, content in files.items():
            _write(root / name / relative, content, force)
        controls[name] = {
            "source_root": CASES[0].task_id,
            "source_tree_hash": _tree_hash(base_root),
            "control_tree_hash": _tree_hash(root / name),
            "changed_files": list(changed),
            "expected_compile": "pass",
            "expected_ctest": "pass",
            "expected_semantic_screen": "duplicate_family",
        }
    _write(root / "manifest.json", json.dumps({"schema_version": "table-pivot-hard-rule-controls-v2", "controls": controls}, indent=2, sort_keys=True) + "\n", force)


def _invalidate_prior_evidence(out: Path, reason: str) -> None:
    state = out / ".state"
    evidence_names = (
        "materialization-manifest.json",
        "host-verification-receipt.json",
        "docker-sanity.json",
    )
    evidence = {
        name: (state / name).read_bytes()
        for name in evidence_names
        if (state / name).is_file()
    }
    verified_remedies = []
    for path in sorted((state / "remedy").glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if record.get("status") == "verified" or record.get("strongest_local_status"):
            verified_remedies.append(
                {
                    "task_id": record.get("task_id"),
                    "status": record.get("status"),
                    "strongest_local_status": record.get("strongest_local_status"),
                    "oracle_receipt_hash": record.get("oracle_receipt_hash"),
                }
            )
    if evidence or verified_remedies:
        subject = {
            "reason": reason,
            "evidence_hashes": {
                name: _sha_bytes(content) for name, content in sorted(evidence.items())
            },
            "verified_remedies": verified_remedies,
        }
        bundle_id = hashlib.sha256(
            json.dumps(subject, sort_keys=True).encode()
        ).hexdigest()
        archive = state / "invalidated" / bundle_id
        archive.mkdir(parents=True, exist_ok=True)
        for name, content in evidence.items():
            (archive / name).write_bytes(content)
        invalidation = {
            "schema_version": "table-pivot-evidence-invalidation-v1",
            "invalidated_claim": "local_family_verified",
            "reason": reason,
            "replacement_required": (
                "regenerate controls, independently assert every hard-rule "
                "decision, and rerun exact-tree Docker normal/sanitizer evidence"
            ),
            **subject,
        }
        _write(
            archive / "invalidation.json",
            json.dumps(invalidation, indent=2, sort_keys=True) + "\n",
            True,
        )
    for name in evidence_names:
        (state / name).unlink(missing_ok=True)


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() == LEGACY_ROOT.resolve():
        _fail("legacy_root_immutable", str(out))
    if force:
        _invalidate_prior_evidence(
            out,
            "hard_rule_controls_and_independent_assertions_stale",
        )
    _write_remedies(out, force)
    roots = []
    expected = {case.task_id for case in CASES}
    if out.exists():
        foreign = {p.name for p in out.iterdir() if p.is_dir() and p.name != ".state"} - expected
        if foreign:
            _fail("generator_output_drift", f"foreign roots: {sorted(foreign)}")
    for case in CASES:
        root = out / case.task_id
        for relative, content in task_named_files(root, _case_files(case)).items():
            _write(root / relative, content, force)
        roots.append(root)
    _write_controls(out, force)
    return tuple(roots)


_CPP_KEYWORDS = frozenset("alignas alignof and and_eq asm auto bitand bitor bool break case catch char class compl const constexpr continue decltype default delete do double dynamic_cast else enum explicit export extern false float for friend goto if inline int long mutable namespace new noexcept not not_eq nullptr operator or or_eq private protected public register reinterpret_cast return short signed sizeof static static_assert static_cast struct switch template this thread_local throw true try typedef typeid typename union unsigned using virtual void volatile wchar_t while xor xor_eq".split())


def _normalized_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.M | re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " literal ", text)
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|==|!=|<=|>=|&&|\|\||[-+*/%<>{}()[\];,.?:=!&|]", text)
    normalized = []
    for token in tokens:
        if token in {"begin", "rbegin", "end", "rend", "front", "back"}:
            normalized.append("endpoint")
        elif re.match(r"[A-Za-z_]", token) and token not in _CPP_KEYWORDS and token not in {"std", "vector", "map", "set", "pair", "string", "size_t", "sort", "min", "max", "lower_bound", "upper_bound"}:
            normalized.append("identifier")
        else:
            normalized.append(token)
    return tuple(normalized)


def _ngrams(tokens: tuple[str, ...], width: int = 7) -> set[tuple[str, ...]]:
    if len(tokens) < width:
        return {tokens} if tokens else set()
    return {tokens[i : i + width] for i in range(len(tokens) - width + 1)}


def _containment(left: str, right: str) -> float:
    a, b = _ngrams(_normalized_tokens(left)), _ngrams(_normalized_tokens(right))
    return 0.0 if not a or not b else len(a & b) / len(a | b)


def _artifact_dimensions(root: Path) -> dict[str, str]:
    config_path = root / ".meta/config.json"
    if not config_path.is_file():
        _fail("generator_output_drift", f"{root.name}: missing config: {config_path}")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    headers = [value for value in config["files"]["solution"] if value.endswith(".h")]
    if len(headers) != 1:
        _fail("generator_output_drift", f"{root.name}: expected exactly one solution header")
    paths = {
        "header": root / headers[0],
        "reference": root / ".meta/example.cpp",
        "instructions": root / ".docs/instructions.md",
        "hidden": root / ".meta/task_hidden_test.cpp",
        "visible": root / "task_visible_test.cpp",
        "negative": root / ".meta/negative_false_substitute.cpp",
        "provenance": root / ".meta/provenance.json",
    }
    for name, path in paths.items():
        if not path.is_file():
            _fail("generator_output_drift", f"{root.name}: missing {name}: {path}")
    text = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    return {
        "public_api": text["header"],
        "owned_state_or_algorithm": text["reference"] + text["provenance"],
        "mutation_or_selection_rules": text["instructions"] + text["reference"],
        "invalid_and_boundary_behavior": text["instructions"] + text["hidden"],
        "reference_control_flow": text["reference"],
        "deterministic_oracle": text["visible"] + text["hidden"],
        "topic_specific_negative_fixture": text["negative"] + text["hidden"],
    }


def _compare_dimensions(left: dict[str, str], right: dict[str, str], left_id: str, right_id: str) -> dict[str, object]:
    scores = {name: _containment(left[name], right[name]) for name in HARD_RULE_DIMENSIONS}
    decisions = {
        name: {
            "score": scores[name],
            "limit": HARD_RULE_LIMITS[name],
            "materially_distinct": scores[name] < HARD_RULE_LIMITS[name],
        }
        for name in HARD_RULE_DIMENSIONS
    }
    failed = [name for name, decision in decisions.items() if not decision["materially_distinct"]]
    if failed:
        _fail("duplicate_family", f"{left_id}/{right_id}: {failed}")
    return {
        "left": left_id,
        "right": right_id,
        "scores": scores,
        "dimensions": decisions,
        "all_dimensions_materially_distinct": True,
    }


def _validate_remedy(case: PivotCase, out: Path) -> None:
    record_path = out / ".state/remedy" / f"{case.task_id}.json"
    spec_path = out / ".state/remedy" / f"{case.task_id}.md"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    spec = spec_path.read_text(encoding="utf-8")
    headings = tuple(re.findall(r"^## (.+)$", spec, flags=re.M))
    if headings != REMEDY_HEADINGS or record.get("remedy_spec_hash") != _sha_bytes(spec.encode()):
        _fail("remedy_spec_incomplete", case.task_id)
    if record.get("disposition") != case.disposition or record.get("tree_hash_before") != _tree_hash(LEGACY_ROOT / case.legacy_id):
        _fail("remedy_disposition_conflict", case.task_id)


def _validate_prompt_roles(case: PivotCase, root: Path) -> None:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    solution = config["files"]["solution"]
    expected = [f"{case.task_id}.h", f"{case.task_id}.cpp"]
    if solution != expected:
        _fail("prompt_contract_incomplete", f"{case.task_id}: solution order")
    roles = sum((config["files"][key] for key in ("solution", "test", "example")), [])
    for value in roles:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or not (root / value).is_file():
            _fail("unsafe_path", f"{case.task_id}: {value}")
    task = load_task(root)
    prompt = build_prompt(task)
    for private in ("example.cpp", "task_hidden_test", "CMakeLists", "provenance.json", "negative_false_substitute"):
        if private in prompt:
            _fail("prompt_contract_incomplete", f"{case.task_id}: exposed {private}")
    answer = build_assistant_response(task, load_example_files_from_config(root))
    if not answer.startswith(f"{case.task_id}.h\n```") or f"{case.task_id}.cpp\n```" not in answer:
        _fail("target_reference_mismatch", case.task_id)


def _screen_controls(out: Path) -> dict[str, dict[str, object]]:
    base = _artifact_dimensions(out / CASES[0].task_id)
    results = {}
    for name in ("domain-identifier-renamed-clone", "constants-policy-clone", "opposite-end-selection-clone"):
        root = out / ".state/hard-rule-controls" / name
        clone = _artifact_dimensions(root)
        decisions = {
            dimension: {
                "score": _containment(base[dimension], clone[dimension]),
                "limit": HARD_RULE_LIMITS[dimension],
                "materially_distinct": (
                    _containment(base[dimension], clone[dimension])
                    < HARD_RULE_LIMITS[dimension]
                ),
            }
            for dimension in HARD_RULE_DIMENSIONS
        }
        try:
            _compare_dimensions(base, clone, CASES[0].task_id, name)
        except RuntimeError as exc:
            if not str(exc).startswith("duplicate_family:"):
                raise
            results[name] = {
                "status": "rejected",
                "reason": "duplicate_family",
                "production_comparator": True,
                "dimensions": decisions,
                "rejection_dimensions": [
                    dimension
                    for dimension, decision in decisions.items()
                    if not decision["materially_distinct"]
                ],
            }
        else:
            _fail("duplicate_family", f"control escaped: {name}")
    return results


def _holdout_screen(out: Path, holdout_root: Path = DEFAULT_HOLDOUT_ROOT) -> dict[str, object]:
    if not holdout_root.is_dir():
        return {"status": "not_completed", "reason": f"missing {holdout_root}", "holdout_root_count": 0, "comparison_count": 0}
    roots = sorted(p for p in holdout_root.iterdir() if p.is_dir() and p.name in OFFICIAL_AIDER_CPP_HOLDOUTS)
    if {p.name for p in roots} != OFFICIAL_AIDER_CPP_HOLDOUTS:
        _fail("benchmark_content_overlap", "incomplete bound holdout inventory")
    holdout_ngrams = {
        holdout.name: _ngrams(_normalized_tokens("\n".join(
            path.read_text(errors="ignore")
            for path in holdout.rglob("*")
            if path.is_file() and path.stat().st_size < 2_000_000
        )))
        for holdout in roots
    }
    comparisons_count = 0
    for case in CASES:
        candidate = _ngrams(_normalized_tokens("\n".join(_artifact_dimensions(out / case.task_id).values())))
        for holdout in roots:
            bound = holdout_ngrams[holdout.name]
            score = 0.0 if not candidate or not bound else len(candidate & bound) / len(candidate | bound)
            if score >= 0.90:
                _fail("benchmark_content_overlap", f"{case.task_id}/{holdout.name}: {score:.3f}")
            comparisons_count += 1
    return {"status": "pass", "normalizer": SEMANTIC_NORMALIZER, "holdout_root_count": len(roots), "comparison_count": comparisons_count}


def verify_core(out: Path) -> dict[str, object]:
    if len(CASES) != 20 or sum(case.disposition == "repair-in-place" for case in CASES) != 1:
        _fail("remedy_disposition_conflict", "expected one repair plus nineteen replacements")
    dimensions = {}
    for case in CASES:
        _validate_remedy(case, out)
        _validate_prompt_roles(case, out / case.task_id)
        reference = (out / case.task_id / ".meta/example.cpp").read_text()
        if case.marker not in reference:
            _fail("invariant_not_enforced", f"{case.task_id}: {case.marker}")
        dimensions[case.task_id] = _artifact_dimensions(out / case.task_id)
    pairs = [_compare_dimensions(dimensions[a.task_id], dimensions[b.task_id], a.task_id, b.task_id) for a, b in combinations(CASES, 2)]
    controls = _screen_controls(out)
    holdouts = _holdout_screen(out)
    manifest = {
        "schema_version": "table-pivot-materialization-v2", "family_id": FAMILY_ID,
        "task_count": len(CASES), "task_ids": [case.task_id for case in CASES],
        "legacy_root": str(LEGACY_ROOT), "legacy_root_immutable": True,
        "tree_hash": _tree_hash(out), "owner_hash": _source_hash(),
        "cases_hash": _source_hash(Path(CASES_PATH)), "status": "implemented",
        "screen": {
            "prompt_boundary": "pass", "reference_mapping": "pass",
            "hard_rule": {"status": "pending_execution", "dimensions": list(HARD_RULE_DIMENSIONS), "dimension_limits": HARD_RULE_LIMITS, "pair_count": len(pairs), "expected_pair_count": 190, "pairs": pairs},
            "adversarial_controls": controls, "semantic_holdout": holdouts,
        },
        "dataset_handoff": "not_requested",
    }
    path = out / ".state/materialization-manifest.json"
    _write(path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    return manifest


def _ctest_count(build_dir: Path) -> int:
    result = subprocess.run(["ctest", "--test-dir", str(build_dir), "-N"], check=True, capture_output=True, text=True)
    match = re.search(r"Total Tests:\s*(\d+)", result.stdout)
    if match is None or int(match.group(1)) <= 0:
        _fail("zero_tests", str(build_dir))
    return int(match.group(1))


def verify(out: Path) -> dict[str, object]:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        receipt = {
            "schema_version": "table-pivot-host-iteration-v1",
            "status": "not_completed",
            "reason": "host verification requires both cmake and c++",
            "blocked_command": "prepare_table_pivot_aider_tasks.sh --force --verify-core --verify",
            "missing_prerequisites": [
                name for name in ("cmake", "c++") if shutil.which(name) is None
            ],
            "evidence_class": "host_iteration",
            "local_family_verified": False,
            "tree_hash": _tree_hash(out),
        }
        _write(
            out / ".state/host-verification-receipt.json",
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            True,
        )
        return receipt
    records = []
    for case in CASES:
        root = out / case.task_id
        with tempfile.TemporaryDirectory(prefix="table-pivot-host-") as temporary:
            copied = Path(temporary) / case.task_id
            shutil.copytree(root, copied)
            counts = {}
            for mode, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{mode}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), "-G", "Unix Makefiles", f"-DTASK_SOURCE={copied / '.meta/example.cpp'}", *flags], check=True, capture_output=True, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, capture_output=True, text=True)
                counts[mode] = _ctest_count(build_dir)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, capture_output=True, text=True)
            if counts["normal"] != counts["sanitizer"]:
                _fail("sanitizer_test_count_mismatch", case.task_id)
            negative_build = copied / "build-negative"
            subprocess.run(["cmake", "-S", str(copied), "-B", str(negative_build), "-G", "Unix Makefiles", f"-DTASK_SOURCE={copied / '.meta/negative_false_substitute.cpp'}"], check=True, capture_output=True, text=True)
            subprocess.run(["cmake", "--build", str(negative_build), "--parallel", "2"], check=True, capture_output=True, text=True)
            rejected = subprocess.run(["ctest", "--test-dir", str(negative_build), "--output-on-failure"], capture_output=True, text=True).returncode != 0
            if not rejected:
                _fail("negative_fixture_not_rejected", case.task_id)
            records.append({"task_id": case.task_id, "normal_tests": counts["normal"], "sanitizer_tests": counts["sanitizer"], "negative_rejected": True})
    receipt = {"schema_version": "table-pivot-host-iteration-v1", "evidence_class": "host_iteration", "local_family_verified": False, "tree_hash": _tree_hash(out), "records": records}
    _write(out / ".state/host-verification-receipt.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    return receipt


def docker_sanity(out: Path, image: str = SANITY_IMAGE) -> dict[str, object]:
    if shutil.which("docker") is None:
        _fail("docker_sanity_not_completed", "docker executable unavailable")
    manifest = verify_core(out)
    inspect = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], capture_output=True, text=True)
    if inspect.returncode != 0:
        _fail("docker_sanity_not_completed", inspect.stderr.strip())
    task_ids = [case.task_id for case in CASES]
    control_ids = ["domain-identifier-renamed-clone", "constants-policy-clone", "opposite-end-selection-clone"]
    script = r'''set -eu
compiler_path=$(command -v c++)
printf 'TOOLCHAIN\tcompiler_path\t%s\n' "$compiler_path"
printf 'TOOLCHAIN\tcompiler_hash\tsha256:%s\n' "$(sha256sum "$compiler_path" | sed 's/ .*//')"
printf 'TOOLCHAIN\tcompiler_version\t%s\n' "$(c++ --version | sed -n '1p')"
printf 'TOOLCHAIN\tcmake_version\t%s\n' "$(cmake --version | sed -n '1p')"
rm -rf /tmp/table-pivot-sanity
mkdir -p /tmp/table-pivot-sanity
for task in $TASK_IDS; do
  cp -a "/family/$task" "/tmp/table-pivot-sanity/$task"
  root="/tmp/table-pivot-sanity/$task"
  cmake -S "$root" -B "$root/build-normal" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp" >/dev/null
  cmake --build "$root/build-normal" --parallel 2 >/dev/null
  normal_count=$(ctest --test-dir "$root/build-normal" -N | sed -n 's/.*Total Tests: *//p')
  test "$normal_count" -gt 0
  ctest --test-dir "$root/build-normal" --output-on-failure >/dev/null
  cmake -S "$root" -B "$root/build-sanitizer" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp" -DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined >/dev/null
  cmake --build "$root/build-sanitizer" --parallel 2 >/dev/null
  sanitizer_count=$(ctest --test-dir "$root/build-sanitizer" -N | sed -n 's/.*Total Tests: *//p')
  test "$normal_count" = "$sanitizer_count"
  ctest --test-dir "$root/build-sanitizer" --output-on-failure >/dev/null
  cmake -S "$root" -B "$root/build-negative" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/negative_false_substitute.cpp" >/dev/null
  cmake --build "$root/build-negative" --parallel 2 >/dev/null
  if ctest --test-dir "$root/build-negative" >/dev/null 2>&1; then exit 41; fi
  printf '%s\t%s\t%s\tpass\n' "$task" "$normal_count" "$sanitizer_count"
done
for control in $CONTROL_IDS; do
  cp -a "/family/.state/hard-rule-controls/$control" "/tmp/table-pivot-sanity/$control"
  root="/tmp/table-pivot-sanity/$control"
  cmake -S "$root" -B "$root/build-normal" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp" >/dev/null
  cmake --build "$root/build-normal" --parallel 2 >/dev/null
  normal_count=$(ctest --test-dir "$root/build-normal" -N | sed -n 's/.*Total Tests: *//p')
  test "$normal_count" -gt 0
  ctest --test-dir "$root/build-normal" --output-on-failure >/dev/null
  cmake -S "$root" -B "$root/build-sanitizer" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp" -DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined >/dev/null
  cmake --build "$root/build-sanitizer" --parallel 2 >/dev/null
  sanitizer_count=$(ctest --test-dir "$root/build-sanitizer" -N | sed -n 's/.*Total Tests: *//p')
  test "$normal_count" = "$sanitizer_count"
  ctest --test-dir "$root/build-sanitizer" --output-on-failure >/dev/null
  printf 'CONTROL\t%s\t%s\t%s\n' "$control" "$normal_count" "$sanitizer_count"
done
python3 -c 'import hashlib,pathlib; root=pathlib.Path("/family"); digest=hashlib.sha256(); files=sorted(p for p in root.rglob("*") if p.is_file() and ".state" not in p.parts); [(digest.update(p.relative_to(root).as_posix().encode()),digest.update(b"\0"),digest.update(p.read_bytes()),digest.update(b"\0")) for p in files]; print("MOUNT_HASH\tsha256:"+hashlib.sha256(digest.digest()).hexdigest())'
'''
    result = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", "-e", f"TASK_IDS={' '.join(task_ids)}", "-e", f"CONTROL_IDS={' '.join(control_ids)}", "-v", f"{out.resolve()}:/family:ro", image, "sh", "-lc", script],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        _fail("docker_sanity_failed", (result.stdout + "\n" + result.stderr)[-6000:])
    records = []
    control_records = []
    mounted_tree_hash = None
    toolchain = {}
    control_manifest = json.loads(
        (out / ".state/hard-rule-controls/manifest.json").read_text(encoding="utf-8")
    )
    for line in result.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) == 4 and fields[0] in task_ids:
            task_root = out / fields[0]
            records.append({
                "task_id": fields[0],
                "tree_hash": _tree_hash(task_root),
                "reference_hash": _sha_bytes((task_root / ".meta/example.cpp").read_bytes()),
                "negative_hash": _sha_bytes((task_root / ".meta/negative_false_substitute.cpp").read_bytes()),
                "normal_tests": int(fields[1]),
                "sanitizer_tests": int(fields[2]),
                "negative_rejected": fields[3] == "pass",
            })
        if len(fields) == 4 and fields[0] == "CONTROL" and fields[1] in control_ids:
            control_root = out / ".state/hard-rule-controls" / fields[1]
            control_records.append({
                "control": fields[1],
                "tree_hash": _tree_hash(control_root),
                "reference_hash": _sha_bytes((control_root / ".meta/example.cpp").read_bytes()),
                "negative_hash": _sha_bytes((control_root / ".meta/negative_false_substitute.cpp").read_bytes()),
                "changed_files": control_manifest["controls"][fields[1]]["changed_files"],
                "normal_tests": int(fields[2]),
                "sanitizer_tests": int(fields[3]),
                "behavior_passed": True,
                "semantic_screen": "duplicate_family",
            })
        if len(fields) == 2 and fields[0] == "MOUNT_HASH":
            mounted_tree_hash = fields[1]
        if len(fields) == 3 and fields[0] == "TOOLCHAIN":
            toolchain[fields[1]] = fields[2]
    if {r["task_id"] for r in records} != set(task_ids):
        _fail("docker_sanity_incomplete", "task inventory")
    if {r["control"] for r in control_records} != set(control_ids):
        _fail("docker_sanity_incomplete", "hard-rule control inventory")
    if set(toolchain) != {
        "compiler_path", "compiler_hash", "compiler_version", "cmake_version"
    }:
        _fail("docker_sanity_incomplete", f"toolchain identity: {sorted(toolchain)}")
    tree_hash = _tree_hash(out)
    if tree_hash != manifest["tree_hash"] or mounted_tree_hash != tree_hash:
        _fail(
            "grader_mount_hash_mismatch",
            f"live={tree_hash} manifest={manifest['tree_hash']} mounted={mounted_tree_hash}",
        )
    # Promote the in-memory screen before hashing it into the receipt. The
    # exact same object is written after the receipt/remedy records, so the
    # receipt cannot bind a pre-promotion `pending_execution` screen.
    manifest["status"] = "local_family_verified"
    manifest["screen"]["hard_rule"]["status"] = "pass"
    manifest["docker_receipt"] = ".state/docker-sanity.json"
    receipt = {
        "schema_version": "table-pivot-docker-sanity-v2", "status": "local_family_verified",
        "evidence_class": "docker_sanity", "locked_oracle": False,
        "image": image, "image_id": inspect.stdout.strip(), "network_policy": "none",
        "tree_hash": tree_hash, "mounted_tree_hash": mounted_tree_hash,
        "owner_path": GENERATOR_PATH,
        "owner_hash": _source_hash(),
        "cases_path": CASES_PATH,
        "cases_hash": _source_hash(Path(CASES_PATH)),
        "hard_rule_screen_hash": _sha_bytes(
            json.dumps(
                manifest["screen"]["hard_rule"], sort_keys=True
            ).encode()
        ),
        "control_manifest_hash": _sha_bytes(
            (out / ".state/hard-rule-controls/manifest.json").read_bytes()
        ),
        "invalidation_records": [
            {
                "path": path.relative_to(out).as_posix(),
                "hash": _sha_bytes(path.read_bytes()),
            }
            for path in sorted((out / ".state/invalidated").glob("*/invalidation.json"))
        ],
        "toolchain": toolchain,
        "commands": {
            "normal": "cmake -G 'Unix Makefiles' -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE=<reference>; cmake --build --parallel 2; ctest -N; ctest --output-on-failure",
            "sanitizer": "fresh cmake -G 'Unix Makefiles' -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE=<reference> -DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined; cmake --build --parallel 2; ctest -N; ctest --output-on-failure",
            "negative": "fresh normal configure/build with TASK_SOURCE=.meta/negative_false_substitute.cpp; require nonzero ctest",
            "mount_hash": "independent in-container SHA-256 over mounted emitted roots excluding .state",
        },
        "records": records, "hard_rule_pair_count": 190,
        "control_records": control_records,
        "adversarial_controls": manifest["screen"]["adversarial_controls"],
        "benchmark_screen": manifest["screen"]["semantic_holdout"],
        "dataset_handoff": "not_requested",
    }
    receipt_hash = _sha_bytes(json.dumps(receipt, sort_keys=True).encode())
    receipt["receipt_hash"] = receipt_hash
    _write(out / ".state/docker-sanity.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    for case in CASES:
        path = out / ".state/remedy" / f"{case.task_id}.json"
        record = json.loads(path.read_text())
        record.update({"status": "verified", "primary_core_objective": "achieved", "tree_hash_after": _tree_hash(out / case.task_id), "benchmark_screen": receipt["benchmark_screen"]["status"], "family_screen": "pass", "prompt_boundary": "pass", "normal_test_count": 2, "sanitizer_test_count": 2, "oracle_receipt": ".state/docker-sanity.json", "oracle_receipt_hash": receipt_hash, "strongest_local_status": "local_family_verified"})
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)
    _write(out / ".state/materialization-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Remediate local Aider-format table-pivot tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    if args.docker_sanity:
        docker_sanity(args.out)
    print(f"Wrote {len(roots)} remediated table-pivot tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
