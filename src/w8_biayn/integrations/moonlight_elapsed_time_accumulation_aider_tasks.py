"""Remediate and locally reverify elapsed-time accumulation task roots."""

from __future__ import annotations

import argparse
import difflib
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
from w8_biayn.integrations.moonlight_elapsed_time_accumulation_cases import (
    CASES,
    REJECTED_LEGACY,
    ElapsedCase,
)

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/elapsed-time-accumulation"
)
LEGACY_ROOT = Path(
    ".w8-biayn/data/aider-tasks/aider-dates-and-clocks/elapsed-time-accumulation"
)
REQUESTED_LEGACY_ROOT = Path(
    ".w8-biayn/data/aider-tasks/aider-text-grid-reshaping/elapsed-time-accumulation"
)
CURRICULUM = "docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_ELAPSED_TIME_ACCUMULATION_ARITHMETIC_CURRICULUM.md"
FAMILY_SPEC = "docs/aider-tasks-spec/aider-text-grid-reshaping/elapsed-time-accumulation.md"
PROMPT_PATH = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
GENERATOR_PATH = "src/w8_biayn/integrations/moonlight_elapsed_time_accumulation_aider_tasks.py"
CASES_PATH = "src/w8_biayn/integrations/moonlight_elapsed_time_accumulation_cases.py"
TEST_PATH = "tests/test_moonlight_elapsed_time_accumulation_aider_tasks.py"
WRAPPER_PATH = "examples/slime/moonlight_cpp_perf/prepare_elapsed_time_accumulation_aider_tasks.sh"
FAMILY_ID_BEFORE = "aider-dates-and-clocks-elapsed-time-accumulation-v1-template"
FAMILY_ID = "aider-text-grid-reshaping-elapsed-time-accumulation-v2"
MANIFEST_SCHEMA = "aider-elapsed-time-accumulation-materialization-v2"
SEMANTIC_NORMALIZER = "elapsed-time-v2-control-flow-9gram"
DEFAULT_HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
HARD_RULE_MIN = 8
HARD_RULE_MAX = 12
HARD_RULE_DIMENSIONS = (
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
OFFICIAL_AIDER_CPP_HOLDOUTS = frozenset(
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

CMAKE = r'''cmake_minimum_required(VERSION 3.16)
project(elapsed_time_accumulation_v2 LANGUAGES CXX)
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
'''


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _write(path: Path, content: str, force: bool = True) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha_bytes(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _source_hash(path: Path | None = None) -> str:
    return _sha_bytes((path or Path(__file__)).read_bytes())


def _owner_hash() -> str:
    digest = hashlib.sha256()
    for path in (Path(__file__), Path(CASES_PATH)):
        digest.update(path.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _tree_hash(root: Path) -> str:
    if not root.is_dir():
        return "not_available"
    digest = hashlib.sha256()
    for path in sorted(
        path for path in root.rglob("*") if path.is_file() and ".state" not in path.parts
    ):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _negative_source(case: ElapsedCase) -> str:
    if case.reference.count(case.negative_old) != 1:
        _fail("invariant_not_enforced", f"negative mutation drift: {case.task_id}")
    changed = case.reference.replace(case.negative_old, case.negative_new, 1)
    if changed == case.reference:
        _fail("invariant_not_enforced", f"negative mutation unchanged: {case.task_id}")
    return changed


def _remedy_markdown(
    task_id: str,
    *,
    legacy_task_id: str,
    disposition: str,
    case: ElapsedCase | None,
    rejection_reason: str | None = None,
) -> str:
    family_after = f"{FAMILY_ID}/{task_id}" if case is not None else "not_applicable_rejected"
    if case is None:
        objective = rejection_reason or "rejected legacy objective"
        public_api = "Legacy generic audit API; no replacement API is retained."
        mechanism = "The legacy shared set-and-sum template did not implement the advertised policy."
        tests = "No new executable is emitted. The owner verifies a rejection record and absence from the counted family."
        acceptance = "The legacy tree remains immutable, the rejection record stays terminal, and the ID is absent from generated roots."
    else:
        objective = case.objective
        public_api = case.public_api
        mechanism = f"{case.mechanism}. Marker: `{case.marker}`."
        tests = f"Visible and private deterministic programs exercise normal and boundary behavior. The compiling topic negative models “{case.negative_reason}” and must be rejected by executed tests."
        acceptance = "Focused pytest, owner `--verify-core`, and owner `--verify-docker` must pass with seven-dimension all-pairs evidence and executed negative checks."
    return f'''## Identity

Task ID: `{task_id}`; legacy task ID: `{legacy_task_id}`; task-spec revision: 2; family before: `{FAMILY_ID_BEFORE}`; family after: `{family_after}`; disposition: `{disposition}`; source inventory: `elapsed-time-legacy-v1`; license: repository-authored/pass; generator: `{GENERATOR_PATH}` plus `{CASES_PATH}`; benchmark screen: pending. Selected prompt: `{PROMPT_PATH}` with `FAMILY_NAME=elapsed-time-accumulation`, `FAMILY_TYPE=aider-text-grid-reshaping`, and user-authorized hard count `8-12`.

## Objective

{objective}

## Public API

C++17 namespace `curriculum`. {public_api} Replacement editable order is `<task-id>.h`, `<task-id>.cpp`; values are caller-owned.

## Behavior table

Valid input, invalid/duplicate input, empty input, ordering/tie rules, mutation, and overflow behavior are fully visible in the generated instructions. {case.invalid_rule if case else rejection_reason} {case.selection_rule if case else ''}

## Implementation invariant

{mechanism} Forbidden substitutes include the legacy generic `id/minutes/contributes` report, renamed/policy/opposite-end clones, hard-coded answers, and benchmark assets.

## Starter and reference

The task-named starter is coherent and incomplete. The hidden reference independently implements the stated mechanism; it does not import the legacy renderer, benchmark code, or private fixture.

## Tests

{tests}

## Files and metadata

Replacement roles are two task-named solution files, one visible test, two suffix-matched `.meta/example.*` references, private test/support under `.meta`, and private CMake/provenance. Rejected roots emit remedy state only.

## Build/oracle

C++17 with strict warnings, explicit `Unix Makefiles`, two positive CTest discoveries, clean normal and fresh ASan/UBSan builds in `{SANITY_IMAGE}` under Docker network `none`. Receipt binds archive/tree/owner/reference/image/toolchain hashes and commands.

## Family/contamination

Compare all counted pairs conjunctively in exactly seven dimensions using `{SEMANTIC_NORMALIZER}`; compare all counted roots against the bound 26 official C++ holdouts. The requested but absent text-grid legacy path and the actual dates-and-clocks legacy source path are both recorded.

## Optional dataset handoff

`not_requested`. No row, tokenizer, mask, split, export, consumer, training, or release work is authorized.

## Acceptance

{acceptance} Stable failures include `remedy_spec_incomplete`, `generator_output_drift`, `prompt_contract_incomplete`, `duplicate_family`, `benchmark_content_overlap`, `negative_fixture_not_rejected`, `grader_mount_hash_mismatch`, and `sanitizer_test_count_mismatch`.
'''


def _write_remedies(out: Path) -> None:
    remedy_root = out / ".state/remedy"
    legacy_ids = [case.legacy_id for case in CASES] + sorted(REJECTED_LEGACY)
    for legacy_task_id in legacy_ids:
        case = next((item for item in CASES if item.legacy_id == legacy_task_id), None)
        task_id = case.task_id if case is not None else legacy_task_id
        disposition = "replace" if case is not None else "reject"
        rejection_reason = REJECTED_LEGACY.get(legacy_task_id)
        markdown = _remedy_markdown(
            task_id,
            legacy_task_id=legacy_task_id,
            disposition=disposition,
            case=case,
            rejection_reason=rejection_reason,
        )
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": task_id,
            "legacy_task_id": legacy_task_id,
            "family_id_before": FAMILY_ID_BEFORE,
            "family_id_after": f"{FAMILY_ID}/{case.task_id}" if case else None,
            "tree_hash_before": _tree_hash(LEGACY_ROOT / legacy_task_id),
            "requested_legacy_root": REQUESTED_LEGACY_ROOT.as_posix(),
            "requested_legacy_root_status": "absent" if not REQUESTED_LEGACY_ROOT.is_dir() else "present",
            "actual_legacy_root": (LEGACY_ROOT / legacy_task_id).as_posix(),
            "generator_path": GENERATOR_PATH,
            "generator_revision": _owner_hash(),
            "finding_ids": [
                "ETA-F1-generic-template-objective-mismatch",
                "ETA-F2-semantic-family-duplicates",
                "ETA-F3-stale-host-only-oracle",
                "ETA-F4-hard-rule-controls-absent",
            ],
            "disposition": disposition,
            "disposition_reason": rejection_reason,
            "benchmark_screen": "pending" if case else "not_applicable_rejected",
            "license_screen": "pass",
            "remedy_spec_path": f".state/remedy/{legacy_task_id}.md",
            "remedy_spec_hash": _sha_bytes(markdown.encode()),
            "selected_prompt": PROMPT_PATH,
            "user_inputs": {
                "FAMILY_NAME": "elapsed-time-accumulation",
                "FAMILY_TYPE": "aider-text-grid-reshaping",
                "hard_rule_count": "8-12",
            },
            "status": "rejected" if case is None else "planned",
            "primary_core_objective": "not_achieved_legacy",
            "dataset_handoff": "not_requested",
        }
        _write(remedy_root / f"{legacy_task_id}.md", markdown)
        _write(
            remedy_root / f"{legacy_task_id}.json",
            json.dumps(record, indent=2, sort_keys=True) + "\n",
        )


def _sync_replacement_remedies(out: Path, **updates: object) -> None:
    for case in CASES:
        path = out / ".state/remedy" / f"{case.legacy_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update(updates)
        record["tree_hash_after"] = _tree_hash(out / case.task_id)
        record["generator_revision_after"] = _owner_hash()
        record["changed_owner_paths"] = [
            CURRICULUM,
            FAMILY_SPEC,
            "docs/AIDER_TASK_MATERIALIZATION_GUIDE.md",
            GENERATOR_PATH,
            CASES_PATH,
            TEST_PATH,
            WRAPPER_PATH,
        ]
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n")


def _case_files(case: ElapsedCase) -> dict[str, str]:
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
        "semantic_mechanism": case.mechanism,
        "origin": "newly authored in-repository clean-room remediation",
        "license": "repository-authored",
        "status": "local task artifact; not admitted SFT data",
        "version": 2,
        "benchmark_separation": "Independent domain-record accumulation with collection state, policy diagnostics, and no civil-time value object.",
    }
    return {
        ".docs/introduction.md": f"# {case.title}\n\n{case.objective}\n",
        ".docs/instructions.md": case.instructions,
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": f'[visible]\ndescription = "normal {case.mechanism} behavior"\n\n[hidden]\ndescription = "invalid, empty, duplicate, ordering, boundary, and overflow behavior"\n\n[negative]\ndescription = "{case.negative_reason}; compiles but must fail executed tests"\n',
        "task.h": case.header,
        "task.cpp": case.starter,
        ".meta/example.h": case.header,
        ".meta/example.cpp": case.reference,
        ".meta/negative_false_substitute.cpp": _negative_source(case),
        "task_visible_test.cpp": case.visible_test,
        ".meta/task_hidden_test.cpp": case.hidden_test,
        "CMakeLists.txt": CMAKE,
    }


def _control_cases() -> dict[str, ElapsedCase]:
    base = CASES[0]
    domain_replacements = (
        ("ConsultingInvoice", "ProjectInvoice"),
        ("client", "account"),
        ("Client", "Account"),
        ("acme", "north"),
        ("beta", "south"),
    )

    def replaced(value: str, replacements: Sequence[tuple[str, str]]) -> str:
        for old, new in replacements:
            value = value.replace(old, new)
        return value

    domain = replace(
        base,
        task_id="domain-identifier-renamed-clone",
        title=replaced(base.title, domain_replacements),
        objective=replaced(base.objective, domain_replacements),
        public_api=replaced(base.public_api, domain_replacements),
        mechanism=replaced(base.mechanism, domain_replacements),
        selection_rule=replaced(base.selection_rule, domain_replacements),
        invalid_rule=replaced(base.invalid_rule, domain_replacements),
        marker=replaced(base.marker, domain_replacements),
        instructions=replaced(base.instructions, domain_replacements),
        header=replaced(base.header, domain_replacements),
        starter=replaced(base.starter, domain_replacements),
        reference=replaced(base.reference, domain_replacements),
        visible_test=replaced(base.visible_test, domain_replacements),
        hidden_test=replaced(base.hidden_test, domain_replacements),
    )
    constants = replace(
        base,
        task_id="constants-policy-clone",
        visible_test=base.visible_test.replace("summarize(entries, 10)", "summarize(entries, 12)").replace("billable_minutes == 10", "billable_minutes == 12").replace("capped_minutes == 3", "capped_minutes == 1"),
        hidden_test=base.hidden_test.replace("summarize(entries, 5)", "summarize(entries, 6)").replace("billable_minutes == 5", "billable_minutes == 6").replace("capped_minutes == 3", "capped_minutes == 2"),
    )
    podcast = CASES[-2]
    opposite = replace(
        podcast,
        task_id="opposite-end-selection-clone",
        title=podcast.title.replace("Latest", "Earliest"),
        objective=podcast.objective.replace("latest", "earliest").replace("greatest", "smallest"),
        selection_rule=podcast.selection_rule.replace("greatest", "smallest"),
        instructions=podcast.instructions.replace("greatest", "smallest").replace("older sequence is counted as superseded", "newer sequence is counted as superseded"),
        reference=podcast.reference.replace("attempt.sequence > found->second.sequence", "attempt.sequence < found->second.sequence", 1),
        visible_test=podcast.visible_test.replace("r.stage_minutes[1] == 7", "r.stage_minutes[0] == 10"),
        negative_old="else if (attempt.sequence < found->second.sequence)",
        negative_new="else if (attempt.sequence > found->second.sequence)",
    )
    return {
        "domain-identifier-renamed-clone": domain,
        "constants-policy-clone": constants,
        "opposite-end-selection-clone": opposite,
    }


def _write_controls(out: Path) -> None:
    controls_root = out / ".state/hard-rule-controls"
    manifest: dict[str, object] = {
        "schema_version": "elapsed-time-hard-rule-controls-v1",
        "controls": {},
    }
    base_by_name = {
        "domain-identifier-renamed-clone": CASES[0],
        "constants-policy-clone": CASES[0],
        "opposite-end-selection-clone": CASES[-2],
    }
    for name, case in _control_cases().items():
        root = controls_root / name
        files = {
            ".docs/instructions.md": case.instructions,
            "task.h": case.header,
            "candidate.cpp": case.reference,
            ".meta/negative_false_substitute.cpp": _negative_source(case),
            "task_visible_test.cpp": case.visible_test,
            ".meta/task_hidden_test.cpp": case.hidden_test,
            "CMakeLists.txt": CMAKE,
        }
        for relative, content in files.items():
            _write(root / relative, content)
        base = base_by_name[name]
        base_root = out / base.task_id
        base_files = {
            ".docs/instructions.md": base_root / ".docs/instructions.md",
            "task.h": base_root / f"{base.task_id}.h",
            "candidate.cpp": base_root / ".meta/example.cpp",
            ".meta/negative_false_substitute.cpp": base_root / ".meta/negative_false_substitute.cpp",
            "task_visible_test.cpp": base_root / "task_visible_test.cpp",
            ".meta/task_hidden_test.cpp": base_root / ".meta/task_hidden_test.cpp",
            "CMakeLists.txt": base_root / "CMakeLists.txt",
        }
        changed_files = sorted(
            relative
            for relative, content in files.items()
            if content != base_files[relative].read_text(encoding="utf-8")
        )
        if not changed_files:
            _fail("duplicate_family", f"adversarial control changed no files: {name}")
        manifest["controls"][name] = {
            "base_task_id": base.task_id,
            "changed_files": changed_files,
            "changed_file_hashes": {
                relative: _sha_bytes((root / relative).read_bytes()) for relative in changed_files
            },
            "source_hash": _sha_bytes(case.reference.encode()),
            "expected_build": "pass",
            "expected_tests": "pass",
            "expected_production_screen": "duplicate_family",
        }
    _write(
        controls_root / "manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )


def _invalidate_previous_evidence(out: Path) -> None:
    state = out / ".state"
    receipt = state / "oracle-receipt.json"
    manifest = state / "materialization-manifest.json"
    if not receipt.is_file():
        return
    receipt_hash = _source_hash(receipt)
    suffix = receipt_hash.removeprefix("sha256:")[:16]
    invalidated = state / "invalidated" / suffix
    invalidated.mkdir(parents=True, exist_ok=True)
    shutil.copy2(receipt, invalidated / "oracle-receipt.json")
    prior_status = "unknown"
    if manifest.is_file():
        prior = json.loads(manifest.read_text(encoding="utf-8"))
        prior_status = str(prior.get("status", "unknown"))
        shutil.copy2(manifest, invalidated / "materialization-manifest.json")
    record = {
        "schema_version": "aider-evidence-invalidation-v1",
        "prior_status": prior_status,
        "prior_receipt_hash": receipt_hash,
        "reason": "hard-rule evidence used case-table metadata and focused tests did not independently recompute emitted-artifact decisions",
        "required_next_state": "planned",
    }
    _write(invalidated / "invalidation.json", json.dumps(record, indent=2, sort_keys=True) + "\n")
    receipt.unlink()
    _write(
        manifest,
        json.dumps(
            {
                "schema_version": MANIFEST_SCHEMA,
                "family_id": FAMILY_ID,
                "status": "planned",
                "invalidated_evidence": f".state/invalidated/{suffix}/invalidation.json",
                "prior_receipt_hash": receipt_hash,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    del force  # Owner regeneration is deterministic; generated output is never hand-edited.
    if not HARD_RULE_MIN <= len(CASES) <= HARD_RULE_MAX:
        _fail("hard_rule_count_failed", f"{len(CASES)} not in {HARD_RULE_MIN}..{HARD_RULE_MAX}")
    _invalidate_previous_evidence(out)
    _write_remedies(out)
    expected = {case.task_id for case in CASES}
    for existing in sorted(path for path in out.iterdir() if path.is_dir() and path.name != ".state"):
        if existing.name in expected:
            continue
        provenance_path = existing / ".meta/provenance.json"
        if not provenance_path.is_file():
            _fail("generator_output_drift", f"refusing to prune unowned root: {existing}")
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        if provenance.get("family_id") != FAMILY_ID:
            _fail("generator_output_drift", f"refusing to prune foreign root: {existing}")
        shutil.rmtree(existing)
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        for relative, content in task_named_files(root, _case_files(case)).items():
            _write(root / relative, content)
        roots.append(root)
    _write_controls(out)
    return tuple(roots)


def _safe_relative(value: str) -> str:
    path = Path(value)
    if not value or path.is_absolute() or ".." in path.parts:
        _fail("unsafe_path", value)
    return path.as_posix()


def _normalized_tokens(content: str) -> list[str]:
    content = re.sub(r"/\*.*?\*/|//[^\n]*", " ", content, flags=re.S)
    content = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", content)
    raw = re.findall(
        r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]",
        content,
    )
    keywords = {
        "if", "else", "for", "while", "return", "class", "struct", "const",
        "auto", "bool", "int", "long", "void", "true", "false", "public",
        "private", "namespace", "std", "vector", "array", "map", "set", "sort",
    }
    normalized = []
    for token in raw:
        if token in {"<", ">", "<=", ">="}:
            normalized.append("CMP")
        elif token in keywords or not re.match(r"[A-Za-z_]", token):
            normalized.append(token)
        else:
            normalized.append("ID")
    return normalized


def _artifact_sources(root: Path) -> dict[str, str]:
    config_path = root / ".meta/config.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        solution = config["files"]["solution"]
        examples = config["files"]["example"]
        if len(solution) != 2 or len(examples) != 2:
            _fail("reference_map_failed", root.name)
        header_path = root / solution[0]
        reference_path = root / examples[1]
    else:
        header_path = root / "task.h"
        reference_path = root / "candidate.cpp"
    paths = {
        "docs": root / ".docs/instructions.md",
        "header": header_path,
        "reference": reference_path,
        "visible": root / "task_visible_test.cpp",
        "hidden": root / ".meta/task_hidden_test.cpp",
        "negative": root / ".meta/negative_false_substitute.cpp",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        _fail("generator_output_drift", f"{root}: missing hard-rule artifacts {missing}")
    return {name: path.read_text(encoding="utf-8") for name, path in paths.items()}


def _matching_lines(content: str, patterns: tuple[str, ...]) -> str:
    return "\n".join(
        line
        for line in content.splitlines()
        if any(re.search(pattern, line) for pattern in patterns)
    )


def _artifact_dimension_material(root: Path) -> dict[str, str]:
    source = _artifact_sources(root)
    reference = source["reference"]
    state_lines = _matching_lines(
        reference,
        (
            r"\bstruct\b",
            r"std::(?:map|set|vector|array)",
            r"\b(?:Report|State)\b",
            r"\b(?:remaining|frontier|latest|ordered|merged|minutes_by|state_by|uncapped)\w*\b",
        ),
    )
    mutation_lines = _matching_lines(
        reference,
        (
            r"\b(?:if|else|for|sort|stable_sort|find|insert|emplace)\b",
            r"(?:\+=|-=|\+\+|=)",
        ),
    )
    control_lines = _matching_lines(
        reference,
        (r"\b(?:if|else|for|while|return|continue)\b",),
    )
    negative_diff = "\n".join(
        difflib.unified_diff(
            reference.splitlines(),
            source["negative"].splitlines(),
            fromfile="reference",
            tofile="negative",
            lineterm="",
            n=1,
        )
    )
    material = {
        "public_api": source["header"],
        "owned_state_algorithm": state_lines,
        "mutation_selection_rules": source["docs"] + "\n" + mutation_lines,
        "invalid_boundary_behavior": source["docs"] + "\n" + source["hidden"],
        "reference_control_flow": control_lines,
        "deterministic_oracle": source["visible"] + "\n" + source["hidden"],
        "topic_negative_fixture": negative_diff,
    }
    empty = [name for name, value in material.items() if not value.strip()]
    if empty:
        _fail("invariant_not_enforced", f"{root.name}: empty artifact evidence {empty}")
    return material


def _artifact_dimension_evidence(root: Path) -> dict[str, str]:
    material = _artifact_dimension_material(root)
    return {
        name: _sha_bytes(" ".join(_normalized_tokens(material[name])).encode())
        for name in HARD_RULE_DIMENSIONS
    }


def _evaluate_artifact_pair(left_root: Path, right_root: Path) -> dict[str, bool]:
    left_evidence = _artifact_dimension_evidence(left_root)
    right_evidence = _artifact_dimension_evidence(right_root)
    return {name: left_evidence[name] != right_evidence[name] for name in HARD_RULE_DIMENSIONS}


def _hard_rule_matrix(out: Path) -> dict[str, object]:
    evidence = {
        case.task_id: _artifact_dimension_evidence(out / case.task_id) for case in CASES
    }
    pairs: list[dict[str, object]] = []
    ordered = sorted(CASES, key=lambda item: item.task_id)
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            decisions = {
                name: evidence[left.task_id][name] != evidence[right.task_id][name]
                for name in HARD_RULE_DIMENSIONS
            }
            if not all(decisions.values()):
                _fail("duplicate_family", f"hard-rule pair failed: {left.task_id}, {right.task_id}: {decisions}")
            pairs.append({"left": left.task_id, "right": right.task_id, "dimensions": decisions, "pass": True})
    expected = len(CASES) * (len(CASES) - 1) // 2
    if len(pairs) != expected:
        _fail("duplicate_family", f"all-pairs incomplete: {len(pairs)} != {expected}")
    return {
        "status": "pending_execution",
        "root_count": len(CASES),
        "count_bounds": [HARD_RULE_MIN, HARD_RULE_MAX],
        "pair_count": len(pairs),
        "expected_pair_count": expected,
        "dimensions": list(HARD_RULE_DIMENSIONS),
        "evidence_source": "actual emitted docs, public header, reference source, visible/private tests, and reference-to-negative diff",
        "pairs": pairs,
    }


def _run_adversarial_controls(out: Path) -> dict[str, object]:
    base_by_name = {
        "domain-identifier-renamed-clone": CASES[0].task_id,
        "constants-policy-clone": CASES[0].task_id,
        "opposite-end-selection-clone": CASES[-2].task_id,
    }
    outcomes: dict[str, object] = {}
    control_manifest = json.loads(
        (out / ".state/hard-rule-controls/manifest.json").read_text(encoding="utf-8")
    )
    for name in sorted(_control_cases()):
        control_root = out / ".state/hard-rule-controls" / name
        decisions = _evaluate_artifact_pair(out / base_by_name[name], control_root)
        if all(decisions.values()):
            _fail("duplicate_family", f"adversarial control passed production evaluator: {name}")
        changed_files = control_manifest["controls"][name]["changed_files"]
        if not changed_files:
            _fail("duplicate_family", f"adversarial control changed no emitted files: {name}")
        outcomes[name] = {
            "changed": True,
            "changed_files": changed_files,
            "production_evaluator": "rejected:duplicate_family",
            "per_dimension_distinct": decisions,
        }
    return outcomes


def _ngrams(tokens: list[str], width: int = 9) -> set[tuple[str, ...]]:
    return {tuple(tokens[index : index + width]) for index in range(max(0, len(tokens) - width + 1))}


def _semantic_holdout_screen(
    root: Path = DEFAULT_HOLDOUT_ROOT, *, candidate_root: Path
) -> dict[str, object]:
    if not root.is_dir():
        _fail("benchmark_screen_not_completed", str(root))
    holdouts: dict[str, set[tuple[str, ...]]] = {}
    inventory = hashlib.sha256()
    for task_root in sorted(path for path in root.iterdir() if path.is_dir()):
        corpus = ""
        for path in sorted(
            item for item in task_root.rglob("*")
            if item.is_file() and item.suffix in {".h", ".hpp", ".cpp"} and "catch" not in item.name
        ):
            inventory.update(path.relative_to(root).as_posix().encode())
            inventory.update(path.read_bytes())
            corpus += "\n" + path.read_text(encoding="utf-8", errors="replace")
        holdouts[task_root.name] = _ngrams(_normalized_tokens(corpus))
    strongest: dict[str, object] = {"candidate": None, "holdout": None, "containment": 0.0}
    for case in CASES:
        emitted = _artifact_sources(candidate_root / case.task_id)
        candidate = _ngrams(
            _normalized_tokens(
                emitted["docs"]
                + emitted["header"]
                + emitted["reference"]
                + emitted["visible"]
                + emitted["hidden"]
            )
        )
        for slug, grams in holdouts.items():
            denominator = min(len(candidate), len(grams))
            score = len(candidate & grams) / denominator if denominator else 0.0
            if score > float(strongest["containment"]):
                strongest = {"candidate": case.task_id, "holdout": slug, "containment": round(score, 6)}
            if score >= 0.60:
                _fail("benchmark_content_overlap", f"{case.task_id} resembles {slug}: {score:.3f}")
    return {
        "status": "pass",
        "normalizer": SEMANTIC_NORMALIZER,
        "source_inventory": f"sha256:{inventory.hexdigest()}",
        "holdout_root_count": len(holdouts),
        "comparison_count": len(CASES) * len(holdouts),
        "threshold": 0.60,
        "strongest": strongest,
    }


def _benchmark_slug_screen(root: Path) -> None:
    screened_roles = {
        ".docs/introduction.md",
        ".docs/instructions.md",
        ".meta/example.h",
        ".meta/example.cpp",
        ".meta/task_hidden_test.cpp",
        ".meta/negative_false_substitute.cpp",
        f"{root.name}.h",
        f"{root.name}.cpp",
        "task_visible_test.cpp",
    }
    corpus = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() in screened_roles
    ).lower()
    for slug in OFFICIAL_AIDER_CPP_HOLDOUTS:
        if re.search(rf"(?<![a-z0-9]){re.escape(slug)}(?![a-z0-9])", corpus):
            _fail("benchmark_id_overlap", slug)


def _whole_format_code(root: Path, response: str) -> str | None:
    task = load_task(root)
    try:
        blocks = parse_whole_file_blocks(response)
    except WholeFormatError:
        return "whole_format_failed"
    return None if set(blocks) == set(task.editable_files) else "whole_format_failed"


def _verify_remedies(out: Path) -> None:
    expected = {case.legacy_id for case in CASES} | set(REJECTED_LEGACY)
    remedy = out / ".state/remedy"
    records = {path.stem: path for path in remedy.glob("*.json")}
    if set(records) != expected:
        _fail("remedy_spec_incomplete", f"records={sorted(records)}")
    for task_id, path in records.items():
        record = json.loads(path.read_text(encoding="utf-8"))
        spec_path = remedy / f"{task_id}.md"
        text = spec_path.read_text(encoding="utf-8") if spec_path.is_file() else ""
        positions = [text.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if -1 in positions or positions != sorted(positions) or record.get("remedy_spec_hash") != _sha_bytes(text.encode()):
            _fail("remedy_spec_incomplete", task_id)
        expected_disposition = "reject" if task_id in REJECTED_LEGACY else "replace"
        if record.get("disposition") != expected_disposition:
            _fail("remedy_disposition_conflict", task_id)


def verify_core(out: Path) -> None:
    expected = {case.task_id for case in CASES}
    actual = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", f"expected {sorted(expected)}, found {sorted(actual)}")
    _verify_remedies(out)
    with tempfile.TemporaryDirectory(prefix="elapsed-time-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for task_id in expected:
            if _tree_hash(out / task_id) != _tree_hash(fresh / task_id):
                _fail("generator_output_drift", task_id)
    hard_rule = _hard_rule_matrix(out)
    controls = _run_adversarial_controls(out)
    holdout = _semantic_holdout_screen(candidate_root=out)
    tasks = []
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        solution = [_safe_relative(value) for value in config["files"]["solution"]]
        tests = [_safe_relative(value) for value in config["files"]["test"]]
        examples = [_safe_relative(value) for value in config["files"]["example"]]
        if solution != [f"{case.task_id}.h", f"{case.task_id}.cpp"] or examples != [".meta/example.h", ".meta/example.cpp"]:
            _fail("target_reference_mismatch", case.task_id)
        if any(not (root / path).is_file() for path in [*solution, *tests, *examples]):
            _fail("reference_map_failed", case.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        hidden_names = [*tests, *examples, "CMakeLists.txt", ".meta/provenance.json", ".meta/task_hidden_test.cpp", ".meta/negative_false_substitute.cpp"]
        if any(name in prompt for name in hidden_names):
            _fail("prompt_contract_incomplete", case.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if _whole_format_code(root, answer) is not None:
            _fail("target_reference_mismatch", case.task_id)
        malformed = (
            f"{task.editable_files[0]}\n```cpp\n// missing\n```\n",
            answer + "\nunknown.cpp\n```cpp\n// forbidden\n```\n",
            "prose\n" + answer,
        )
        if any(_whole_format_code(root, item) != "whole_format_failed" for item in malformed):
            _fail("whole_format_failed", case.task_id)
        if case.marker not in case.reference:
            _fail("invariant_not_enforced", case.task_id)
        _benchmark_slug_screen(root)
        tasks.append({
            "task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "tree_hash": _tree_hash(root),
            "mechanism": case.mechanism,
            "dimension_hashes": _artifact_dimension_evidence(root),
            "primary_core_objective": "achieved",
        })
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "family_id": FAMILY_ID,
        "task_count": len(CASES),
        "rejected_legacy_count": len(REJECTED_LEGACY),
        "owner_hash": _owner_hash(),
        "status": "implemented",
        "hard_rule_status": "pending_execution",
        "legacy_source": {
            "requested_path": REQUESTED_LEGACY_ROOT.as_posix(),
            "requested_path_status": "absent" if not REQUESTED_LEGACY_ROOT.is_dir() else "present",
            "actual_preserved_path": LEGACY_ROOT.as_posix(),
        },
        "tasks": tasks,
        "rejected_legacy": REJECTED_LEGACY,
        "screen": {
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
            "hard_rule": hard_rule,
            "adversarial_controls": controls,
            "duplicate_family": "pass",
            "benchmark_contamination": "pass",
            "semantic_holdout": holdout,
        },
    }
    _write(out / ".state/materialization-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    _sync_replacement_remedies(
        out,
        status="implemented",
        primary_core_objective="achieved",
        prompt_boundary="pass",
        reference_mapping="pass",
        benchmark_screen="pass",
        semantic_holdout_screen=holdout,
        hard_rule_status="pending_execution",
        hard_rule_evidence={
            "status": "pending_execution",
            "pair_count": hard_rule["pair_count"],
            "dimensions": hard_rule["dimensions"],
            "matrix_path": ".state/materialization-manifest.json",
            "adversarial_controls": controls,
        },
        strongest_local_status="implemented",
    )


def _deterministic_archive(out: Path, destination: Path) -> str:
    with tarfile.open(destination, "w") as archive:
        sources: list[tuple[Path, Path]] = []
        for case in sorted(CASES, key=lambda item: item.task_id):
            root = out / case.task_id
            sources.extend((path, Path(case.task_id) / path.relative_to(root)) for path in sorted(item for item in root.rglob("*") if item.is_file()))
        controls = out / ".state/hard-rule-controls"
        sources.extend((path, Path(".hard-rule-controls") / path.relative_to(controls)) for path in sorted(item for item in controls.rglob("*") if item.is_file()))
        for path, relative in sources:
            data = path.read_bytes()
            info = tarfile.TarInfo(relative.as_posix())
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
    with tempfile.TemporaryDirectory(prefix="elapsed-time-docker-") as temporary:
        temp = Path(temporary)
        archive = temp / "family.tar"
        results = temp / "results"
        results.mkdir()
        archive_hash = _deterministic_archive(out, archive)
        runner = r'''set -eu
mkdir -p /tmp/family
tar -xf /input/family.tar -C /tmp/family
: > /result/counts.tsv
: > /result/topic-negative.tsv
: > /result/controls.tsv
c++ --version | head -1 > /result/compiler.txt
cmake --version | head -1 > /result/cmake.txt
for root in /tmp/family/*; do
  task=$(basename "$root")
  if [ "$task" = ".hard-rule-controls" ]; then continue; fi
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
  negative_build="/tmp/build-${task}-negative"
  cmake -S "$root" -B "$negative_build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/negative_false_substitute.cpp"
  cmake --build "$negative_build" --parallel 2
  negative_count=$(ctest --test-dir "$negative_build" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
  set +e
  ctest --test-dir "$negative_build" --output-on-failure
  negative_exit=$?
  set -e
  test -n "$negative_count" && test "$negative_count" -gt 0 && test "$negative_exit" -ne 0
  printf '%s\t%s\t%s\n' "$task" "$negative_count" "$negative_exit" >> /result/topic-negative.tsv
done
for root in /tmp/family/.hard-rule-controls/*; do
  test -d "$root" || continue
  name=$(basename "$root")
  build="/tmp/build-control-${name}"
  cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/candidate.cpp"
  cmake --build "$build" --parallel 2
  count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
  test -n "$count" && test "$count" -gt 0
  ctest --test-dir "$build" --output-on-failure
  printf '%s\t%s\n' "$name" "$count" >> /result/controls.tsv
done
sha256sum /input/family.tar | awk '{print "sha256:" $1}' > /result/archive.sha256
'''
        command = [
            "docker", "run", "--rm", "--network", "none",
            "--mount", f"type=bind,src={archive},dst=/input/family.tar,readonly",
            "--mount", f"type=bind,src={results},dst=/result",
            image, "sh", "-lc", runner,
        ]
        run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if run.returncode:
            _fail("docker_sanity_failed", run.stdout[-6000:])
        mounted_hash = (results / "archive.sha256").read_text(encoding="utf-8").strip()
        if mounted_hash != archive_hash:
            _fail("grader_mount_hash_mismatch", f"owner={archive_hash} docker={mounted_hash}")
        counts: dict[str, dict[str, int]] = {}
        for line in (results / "counts.tsv").read_text(encoding="utf-8").splitlines():
            task_id, mode, raw_count = line.split("\t")
            counts.setdefault(task_id, {})[mode] = int(raw_count)
        expected = {case.task_id for case in CASES}
        if set(counts) != expected:
            _fail("test_discovery_failed", "incomplete task receipt")
        for task_id, modes in counts.items():
            if modes.get("normal", 0) <= 0 or modes.get("normal") != modes.get("sanitizer"):
                _fail("sanitizer_test_count_mismatch", task_id)
        negatives: dict[str, dict[str, object]] = {}
        for line in (results / "topic-negative.tsv").read_text(encoding="utf-8").splitlines():
            task_id, raw_count, raw_exit = line.split("\t")
            negatives[task_id] = {"compiled": True, "discovered_tests": int(raw_count), "ctest_exit": int(raw_exit), "rejected_by_executed_tests": int(raw_exit) != 0}
        if set(negatives) != expected or any(not item["rejected_by_executed_tests"] for item in negatives.values()):
            _fail("negative_fixture_not_rejected", "topic-negative receipt")
        controls: dict[str, dict[str, object]] = {}
        semantic_controls = _run_adversarial_controls(out)
        for line in (results / "controls.tsv").read_text(encoding="utf-8").splitlines():
            name, raw_count = line.split("\t")
            controls[name] = {"compiled": True, "discovered_tests": int(raw_count), "tests_passed": True, "production_evaluator": semantic_controls[name]["production_evaluator"]}
        if set(controls) != set(_control_cases()) or any(item["discovered_tests"] <= 0 for item in controls.values()):
            _fail("negative_fixture_not_rejected", "adversarial-control receipt")
        manifest_path = out / ".state/materialization-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["screen"]["hard_rule"]["status"] = "pass"
        manifest["screen"]["hard_rule"]["topic_negative_execution"] = negatives
        manifest["screen"]["hard_rule"]["adversarial_control_execution"] = controls
        receipt = {
            "schema_version": "aider-elapsed-time-docker-sanity-v2",
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "network_policy": "none",
            "image": image,
            "image_id": image_id,
            "archive_hash": archive_hash,
            "owner_hash": _owner_hash(),
            "family_tree_hashes": {case.task_id: _tree_hash(out / case.task_id) for case in CASES},
            "reference_hashes": {case.task_id: _source_hash(out / case.task_id / ".meta/example.cpp") for case in CASES},
            "negative_hashes": {case.task_id: _source_hash(out / case.task_id / ".meta/negative_false_substitute.cpp") for case in CASES},
            "compiler": (results / "compiler.txt").read_text(encoding="utf-8").strip(),
            "cmake": (results / "cmake.txt").read_text(encoding="utf-8").strip(),
            "commands": {
                "normal": "fresh Unix Makefiles reference build and ctest",
                "sanitizer": "fresh ASan/UBSan Unix Makefiles reference build and ctest",
                "topic_negative": "strict build followed by required executed-test rejection",
                "controls": "strict build and passing behavior tests followed by production duplicate-family rejection",
            },
            "test_counts": counts,
            "topic_negative_execution": negatives,
            "adversarial_control_execution": controls,
        }
        receipt_path = out / ".state/oracle-receipt.json"
        _write(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        receipt_hash = _source_hash(receipt_path)
        _sync_replacement_remedies(
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
            },
            hard_rule_status="pass",
            hard_rule_evidence={
                "status": "pass",
                "pair_count": manifest["screen"]["hard_rule"]["pair_count"],
                "dimensions": list(HARD_RULE_DIMENSIONS),
                "matrix_path": ".state/materialization-manifest.json",
                "adversarial_controls": controls,
            },
            strongest_local_status="local_family_verified",
        )
        manifest.update({
            "status": "local_family_verified",
            "hard_rule_status": "pass",
            "oracle_receipt": ".state/oracle-receipt.json",
            "oracle_receipt_hash": receipt_hash,
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
        })
        _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-docker", action="store_true")
    parser.add_argument("--verify", action="store_true", help="compatibility alias for --verify-docker")
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify_docker or args.verify:
        verify_docker(args.out, args.image)
    print(f"Wrote {len(roots)} distinct elapsed-time accumulation roots under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
