"""Remediate and locally reverify the leap-year-rule Aider task family."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_leap_year_rule_cases import CASES, LeapCase

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/leap-year-rule"
)
SUPPLIED_LEGACY_ROOT = Path(
    ".w8-biayn/data/aider-tasks/aider-text-grid-reshaping/leap-year-rule"
)
DISCOVERED_LEGACY_ROOT = Path(
    ".w8-biayn/data/aider-tasks/aider-dates-and-clocks/leap-year-rule"
)
CURRICULUM = "docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_LEAP_YEAR_RULE_CURRICULUM.md"
FAMILY_SPEC = "docs/aider-tasks-spec/aider-text-grid-reshaping/leap-year-rule.md"
PROMPT_PATH = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY_ID = "aider-text-grid-reshaping-leap-year-rule-v2"
MANIFEST_SCHEMA = "aider-leap-year-rule-materialization-v2"
SEMANTIC_NORMALIZER = "leap-year-rule-v2-role-aware-7gram"
MIN_ROOTS = 8
MAX_ROOTS = 12
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
DEFAULT_HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
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
        "all-your-base", "allergies", "bank-account", "binary-search-tree",
        "circular-buffer", "clock", "complex-numbers", "crypto-square", "diamond",
        "dnd-character", "gigasecond", "grade-school", "kindergarten-garden",
        "knapsack", "linked-list", "meetup", "parallel-letter-frequency",
        "perfect-numbers", "phone-number", "queen-attack", "robot-name",
        "space-age", "spiral-matrix", "sublist", "yacht", "zebra-puzzle",
    }
)


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _sha_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _source_hash() -> str:
    return _sha_bytes(Path(__file__).read_bytes())


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to regenerate")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _tree_hash(root: Path) -> str:
    if not root.is_dir():
        return "not_available"
    digest = hashlib.sha256()
    files = []
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if path.is_file() and ".state" not in relative.parts:
            files.append(path)
    for path in sorted(files):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


CMAKE = r'''cmake_minimum_required(VERSION 3.16)
project(leap_year_rule_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
enable_testing()
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
add_executable(task_hard_rule "${TASK_SOURCE}" .meta/task_hard_rule_test.cpp)
foreach(target task_visible task_hidden task_hard_rule)
  target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_test(NAME hard_rule COMMAND task_hard_rule)
'''


def _validate_remedies(out: Path) -> None:
    remedy_root = out / ".state" / "remedy"
    for case in CASES:
        md = remedy_root / f"{case.task_id}.md"
        record_path = remedy_root / f"{case.task_id}.json"
        if not md.is_file() or not record_path.is_file():
            _fail("remedy_spec_incomplete", case.task_id)
        text = md.read_text(encoding="utf-8")
        headings = tuple(re.findall(r"^## (.+)$", text, flags=re.M))
        if headings != REMEDY_HEADINGS:
            _fail("remedy_spec_incomplete", f"{case.task_id}: headings={headings}")
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record.get("task_id") != case.task_id or record.get("disposition") != "replace":
            _fail("remedy_disposition_conflict", case.task_id)
        if record.get("remedy_spec_hash") != _sha_bytes(text.encode()):
            _fail("remedy_spec_incomplete", f"stale spec hash: {case.task_id}")
        if record.get("status") not in {"planned", "implemented", "verified"}:
            _fail("remedy_disposition_conflict", f"bad status: {case.task_id}")


def _task_files(case: LeapCase) -> Mapping[str, str]:
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
        "origin": "newly authored in-repository clean-room replacement",
        "license": "repository-authored",
        "status": "local task artifact; not admitted SFT data",
        "version": 2,
        "selected_prompt": PROMPT_PATH,
        "benchmark_separation": "Independent domain API, state/algorithm, tests, and reference; all official Aider C++ roots remain permanent holdouts.",
    }
    return {
        ".docs/introduction.md": f"# {case.title}\n\n{case.objective}\n",
        ".docs/instructions.md": case.instructions,
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": (
            f'[visible]\ndescription = "normal {case.mechanism} behavior"\n\n'
            '[hidden]\ndescription = "invalid, leap-century, duplicate, ordering, and atomic-boundary cases"\n\n'
            f'[hard_rule]\ndescription = "independent property/trace discriminator for {case.mechanism}"\n\n'
            f'[negative]\ndescription = "{case.negative_reason}; source must compile and be rejected"\n'
        ),
        "task.h": case.header,
        "task.cpp": case.starter,
        ".meta/example.h": case.header,
        ".meta/example.cpp": case.reference,
        ".meta/negative_false_substitute.cpp": case.negative_source,
        "task_visible_test.cpp": case.visible_test,
        ".meta/task_hidden_test.cpp": case.hidden_test,
        ".meta/task_hard_rule_test.cpp": case.hard_rule_test,
        "CMakeLists.txt": CMAKE,
    }


def _prune_owned_stale_roots(out: Path) -> None:
    expected = {case.task_id for case in CASES}
    if not out.is_dir():
        return
    for path in out.iterdir():
        if not path.is_dir() or path.name == ".state" or path.name in expected:
            continue
        provenance = path / ".meta" / "provenance.json"
        if not provenance.is_file():
            _fail("generator_output_drift", f"refuse foreign root: {path}")
        record = json.loads(provenance.read_text(encoding="utf-8"))
        if record.get("family_id") != FAMILY_ID:
            _fail("generator_output_drift", f"refuse foreign provenance: {path}")
        shutil.rmtree(path)


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    _validate_remedies(out)
    if force:
        _prune_owned_stale_roots(out)
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        for relative, content in task_named_files(root, _task_files(case)).items():
            _write(root / relative, content, force)
        roots.append(root)
    _write_controls(out, force)
    return tuple(roots)


def _normalized_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", text)
    raw = re.findall(r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]", text)
    keywords = {
        "if", "else", "for", "while", "switch", "case", "return", "class", "struct",
        "const", "auto", "bool", "int", "long", "void", "true", "false", "public",
        "private", "namespace", "std", "vector", "array", "set", "map", "sort",
        "function", "break", "continue", "static_cast", "enum", "explicit",
    }
    output: list[str] = []
    for token in raw:
        if token in {"<", ">", "<=", ">="}:
            output.append("CMP")
        elif token in {"++", "--"}:
            output.append("STEP")
        elif re.match(r"[A-Za-z_]", token) and token not in keywords and token != "LIT":
            output.append("ID")
        else:
            output.append(token)
    return tuple(output)


def _control_flow_tokens(text: str) -> tuple[str, ...]:
    tokens = _normalized_tokens(text)
    keep = {"if", "else", "for", "while", "switch", "case", "return", "break", "continue", "CMP", "STEP", "&&", "||", "%", "+", "-", "=", "?", ":"}
    return tuple(token for token in tokens if token in keep)


def _features(root: Path, *, control: bool = False) -> dict[str, tuple[str, ...]]:
    header = (root / "task.h" if control else next(root.glob("*.h"))).read_text(encoding="utf-8")
    reference_path = root / "candidate.cpp" if control else root / ".meta" / "example.cpp"
    negative_path = root / "negative.cpp" if control else root / ".meta" / "negative_false_substitute.cpp"
    reference = reference_path.read_text(encoding="utf-8")
    negative = negative_path.read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    hidden = (root / ".meta" / "task_hidden_test.cpp").read_text(encoding="utf-8")
    hard = (root / ".meta" / "task_hard_rule_test.cpp").read_text(encoding="utf-8")
    docs = (root / ".docs" / "instructions.md").read_text(encoding="utf-8")
    return {
        "public_api": _normalized_tokens(header),
        "owned_state_algorithm": _normalized_tokens(header + reference),
        "mutation_selection_rules": _control_flow_tokens(reference),
        "invalid_boundary_behavior": _normalized_tokens(docs + hidden),
        "reference_control_flow": _control_flow_tokens(reference),
        "deterministic_oracle": _normalized_tokens(visible + hidden + hard),
        "topic_specific_negative_fixture": _normalized_tokens(negative),
    }


def _pair_decision(left: Mapping[str, tuple[str, ...]], right: Mapping[str, tuple[str, ...]]) -> dict[str, object]:
    dimensions: dict[str, object] = {}
    for name in HARD_RULE_DIMENSIONS:
        a, b = left[name], right[name]
        left_grams = _ngrams(a)
        right_grams = _ngrams(b)
        denominator = min(len(left_grams), len(right_grams))
        containment = len(left_grams & right_grams) / denominator if denominator else 1.0
        dimensions[name] = {
            "distinct": a != b and containment < 0.85,
            "left_token_count": len(a),
            "right_token_count": len(b),
            "normalized_7gram_containment": round(containment, 6),
            "threshold": 0.85,
        }
    return {
        "dimensions": dimensions,
        "pass": all(bool(dimensions[name]["distinct"]) for name in HARD_RULE_DIMENSIONS),
    }


def _hard_rule_matrix(out: Path) -> dict[str, object]:
    emitted = {case.task_id: _features(out / case.task_id) for case in CASES}
    pairs: list[dict[str, object]] = []
    ids = sorted(emitted)
    for index, left_id in enumerate(ids):
        for right_id in ids[index + 1 :]:
            decision = _pair_decision(emitted[left_id], emitted[right_id])
            row = {"left": left_id, "right": right_id, **decision}
            if not decision["pass"]:
                failed = [name for name, value in decision["dimensions"].items() if not value["distinct"]]
                _fail("duplicate_family", f"{left_id}, {right_id}: {failed}")
            pairs.append(row)
    expected = len(CASES) * (len(CASES) - 1) // 2
    if len(pairs) != expected:
        _fail("duplicate_family", f"incomplete all-pairs: {len(pairs)} != {expected}")
    return {
        "status": "pass",
        "dimensions": list(HARD_RULE_DIMENSIONS),
        "root_count": len(CASES),
        "pair_count": len(pairs),
        "expected_pair_count": expected,
        "evidence_source": "actual emitted docs, public API, reference, visible/private/property tests, and topic-negative source",
        "pairs": pairs,
    }


def _replace_all(case: LeapCase, replacements: Sequence[tuple[str, str]], task_id: str) -> LeapCase:
    updates: dict[str, object] = {"task_id": task_id, "legacy_id": None}
    for field in (
        "title", "objective", "public_api", "mechanism", "instructions", "header", "starter",
        "reference", "visible_test", "hidden_test", "hard_rule_test", "negative_source", "negative_reason",
    ):
        value = str(getattr(case, field))
        for old, new in replacements:
            value = value.replace(old, new)
        updates[field] = value
    return replace(case, **updates)


def _adversarial_cases() -> dict[str, tuple[LeapCase, LeapCase]]:
    capacity = CASES[0]
    benefit = CASES[1]
    domain = _replace_all(
        capacity,
        (("Capacity", "Quota"), ("capacity", "quota"), ("DayLoad", "SlotUse"), ("day", "slot"), ("load", "use")),
        "domain-identifier-renamed-clone",
    )
    constants = _replace_all(
        capacity,
        (
            ("std::array<bool, 30>", "std::array<bool, 31>"),
            ("std::array<int, 30>", "std::array<int, 31>"),
            ("29", "30"),
            ("28", "29"),
        ),
        "constants-policy-clone",
    )
    constants = replace(
        constants,
        visible_test=constants.visible_test.replace("r.missing_days == 27", "r.missing_days == 28", 1),
    )
    old = "a.rem!=b.rem?a.rem>b.rem:a.id<b.id"
    new = "a.rem!=b.rem?a.rem<b.rem:a.id>b.id"
    if benefit.reference.count(old) != 1:
        _fail("invariant_not_enforced", "opposite-end source drift")
    opposite = replace(
        benefit,
        task_id="opposite-end-selection-clone",
        legacy_id=None,
        reference=benefit.reference.replace(old, new, 1),
        visible_test=benefit.visible_test.replace("r.shares[0].units==2&&r.shares[1].units==3", "r.shares[0].units==1&&r.shares[1].units==4", 1),
        hidden_test=benefit.hidden_test.replace(".shares[0].units!=1", ".shares[0].units!=0", 1),
    )
    return {
        "domain-identifier-renamed-clone": (capacity, domain),
        "constants-policy-clone": (capacity, constants),
        "opposite-end-selection-clone": (benefit, opposite),
    }


def _write_control(root: Path, case: LeapCase, force: bool) -> None:
    files = {
        ".docs/instructions.md": case.instructions,
        "task.h": case.header,
        "candidate.cpp": case.reference,
        "negative.cpp": case.negative_source,
        "task_visible_test.cpp": case.visible_test,
        ".meta/task_hidden_test.cpp": case.hidden_test,
        ".meta/task_hard_rule_test.cpp": case.hard_rule_test,
        "CMakeLists.txt": CMAKE,
    }
    for relative, content in files.items():
        _write(root / relative, content, force)


def _write_controls(out: Path, force: bool) -> None:
    root = out / ".state" / "hard-rule-controls"
    manifest: dict[str, object] = {"schema_version": "aider-leap-year-controls-v1", "controls": {}}
    for name, (_, case) in _adversarial_cases().items():
        control_root = root / name
        _write_control(control_root, case, force)
        manifest["controls"][name] = {
            "tree_hash": _tree_hash(control_root),
            "changed_files": ["task.h", "candidate.cpp", "task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
            "expected_build": "pass",
            "expected_behavior": "pass",
            "expected_semantic_screen": "duplicate_family_all_seven_dimensions",
        }
    _write(root / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", force)


def _verify_controls(out: Path) -> dict[str, object]:
    outcomes: dict[str, object] = {}
    for name, (base, _) in _adversarial_cases().items():
        base_features = _features(out / base.task_id)
        control_features = _features(out / ".state" / "hard-rule-controls" / name, control=True)
        decision = _pair_decision(base_features, control_features)
        failed = [dimension for dimension, value in decision["dimensions"].items() if not value["distinct"]]
        if set(failed) != set(HARD_RULE_DIMENSIONS) or decision["pass"]:
            _fail("duplicate_family", f"control not rejected in all dimensions: {name}: {failed}")
        outcomes[name] = {
            "changed_tree": _tree_hash(out / base.task_id) != _tree_hash(out / ".state" / "hard-rule-controls" / name),
            "failed_dimensions": failed,
            "semantic_result": "rejected:duplicate_family",
            "runtime_status": "pending_execution",
        }
        if not outcomes[name]["changed_tree"]:
            _fail("generator_output_drift", f"no-op control: {name}")
    return outcomes


def _verify_prompt_and_roles(root: Path) -> dict[str, object]:
    task = load_task(root)
    config = json.loads((root / ".meta" / "config.json").read_text(encoding="utf-8"))
    expected = [f"{root.name}.h", f"{root.name}.cpp"]
    if list(task.editable_files) != expected or config["files"]["solution"] != expected:
        _fail("target_reference_mismatch", root.name)
    prompt = build_prompt(task)
    for forbidden in ("negative_false_substitute", "task_hidden_test", "task_hard_rule_test", "CMakeLists", ".meta/example"):
        if forbidden in prompt:
            _fail("prompt_contract_incomplete", f"{root.name}: {forbidden}")
    response = build_assistant_response(task, load_example_files_from_config(root))
    if not response.startswith(f"{root.name}.h\n```") or f"{root.name}.cpp\n```" not in response:
        _fail("whole_format_failed", root.name)
    return {"prompt_sha256": _sha_bytes(prompt.encode()), "editable_files": expected, "status": "pass"}


def _semantic_holdout_screen(out: Path, holdout_root: Path = DEFAULT_HOLDOUT_ROOT) -> dict[str, object]:
    if not holdout_root.is_dir():
        _fail("benchmark_screen_not_completed", str(holdout_root))
    found = {path.name for path in holdout_root.iterdir() if path.is_dir()}
    if found != OFFICIAL_AIDER_CPP_HOLDOUTS:
        _fail("benchmark_screen_not_completed", f"holdout inventory drift: {sorted(found)}")
    candidates = {}
    for case in CASES:
        root = out / case.task_id
        corpus = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.suffix in {".md", ".h", ".cpp"} and "negative" not in path.name
        )
        candidates[case.task_id] = set(_ngrams(_normalized_tokens(corpus)))
    holdouts = {}
    inventory = hashlib.sha256()
    for slug in sorted(found):
        corpus = ""
        for path in sorted((holdout_root / slug).rglob("*")):
            if path.is_file() and path.suffix in {".h", ".hpp", ".cpp"} and "catch" not in path.name:
                inventory.update(path.relative_to(holdout_root).as_posix().encode())
                inventory.update(path.read_bytes())
                corpus += path.read_text(encoding="utf-8", errors="replace")
        holdouts[slug] = set(_ngrams(_normalized_tokens(corpus)))
    strongest = {"candidate": None, "holdout": None, "containment": 0.0}
    comparisons = 0
    for candidate_id, candidate in candidates.items():
        for slug, holdout in holdouts.items():
            comparisons += 1
            denominator = min(len(candidate), len(holdout))
            score = len(candidate & holdout) / denominator if denominator else 0.0
            if score > strongest["containment"]:
                strongest = {"candidate": candidate_id, "holdout": slug, "containment": round(score, 6)}
            if score >= 0.90:
                _fail("benchmark_content_overlap", f"{candidate_id}, {slug}: {score:.3f}")
    return {
        "status": "pass",
        "normalizer": SEMANTIC_NORMALIZER,
        "holdout_count": len(holdouts),
        "comparison_count": comparisons,
        "inventory_sha256": f"sha256:{inventory.hexdigest()}",
        "threshold": 0.90,
        "strongest": strongest,
    }


def _ngrams(tokens: Sequence[str], width: int = 7) -> set[tuple[str, ...]]:
    return {tuple(tokens[index : index + width]) for index in range(max(0, len(tokens) - width + 1))}


def _sync_remedies(out: Path, **updates: object) -> None:
    for case in CASES:
        path = out / ".state" / "remedy" / f"{case.task_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update(updates)
        record["tree_hash_after"] = _tree_hash(out / case.task_id)
        record["generator_revision_after"] = _source_hash()
        record["primary_core_objective"] = "achieved"
        record["changed_owner_paths"] = [
            CURRICULUM, FAMILY_SPEC,
            "docs/AIDER_TASK_MATERIALIZATION_GUIDE.md",
            "src/w8_biayn/integrations/moonlight_leap_year_rule_aider_tasks.py",
            "src/w8_biayn/integrations/moonlight_leap_year_rule_cases.py",
            "tests/test_moonlight_leap_year_rule_aider_tasks.py",
            "examples/slime/moonlight_cpp_perf/prepare_leap_year_rule_aider_tasks.sh",
        ]
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def verify_core(out: Path, holdout_root: Path = DEFAULT_HOLDOUT_ROOT) -> dict[str, object]:
    _validate_remedies(out)
    if not MIN_ROOTS <= len(CASES) <= MAX_ROOTS:
        _fail("duplicate_family", f"root count {len(CASES)} outside {MIN_ROOTS}..{MAX_ROOTS}")
    if len({case.task_id for case in CASES}) != len(CASES) or len({case.mechanism for case in CASES}) != len(CASES):
        _fail("duplicate_family", "task IDs and mechanisms must be one-to-one")
    prompts = {case.task_id: _verify_prompt_and_roles(out / case.task_id) for case in CASES}
    for case in CASES:
        if case.reference == case.negative_source:
            _fail("invariant_not_enforced", case.task_id)
    hard_rule = _hard_rule_matrix(out)
    controls = _verify_controls(out)
    holdouts = _semantic_holdout_screen(out, holdout_root)
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "family_id": FAMILY_ID,
        "selected_prompt": PROMPT_PATH,
        "user_inputs": {"FAMILY_NAME": "leap-year-rule", "FAMILY_TYPE": "aider-text-grid-reshaping", "hard_rule_count": "8-12"},
        "legacy_resolution": {"supplied_root": str(SUPPLIED_LEGACY_ROOT), "supplied_exists": SUPPLIED_LEGACY_ROOT.exists(), "audited_root": str(DISCOVERED_LEGACY_ROOT), "audited_count": 5},
        "task_count": len(CASES),
        "task_ids": [case.task_id for case in CASES],
        "root_count_bounds": [MIN_ROOTS, MAX_ROOTS],
        "generator_sha256": _source_hash(),
        "family_tree_hash": _tree_hash(out),
        "task_tree_hashes": {case.task_id: _tree_hash(out / case.task_id) for case in CASES},
        "prompt_role_screen": prompts,
        "hard_rule": hard_rule,
        "adversarial_controls": controls,
        "benchmark_screen": holdouts,
        "docker_sanity": {"status": "pending_execution"},
        "strongest_local_status": "pending_execution",
        "dataset_handoff": "not_requested",
    }
    manifest_path = out / ".state" / "materialization-manifest.json"
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    _sync_remedies(
        out,
        status="implemented",
        strongest_local_status="pending_execution",
        prompt_boundary="pass",
        reference_mapping="pass",
        family_screen="pass",
        benchmark_screen="pass",
        hard_rule_status="pending_execution",
        materialization_manifest=str(manifest_path.relative_to(out)),
    )
    return manifest


def _make_archive(out: Path, archive: Path) -> str:
    with tarfile.open(archive, "w") as tar:
        for path in sorted(out.rglob("*")):
            relative = path.relative_to(out)
            if path.is_file() and not (
                relative.parts[:2] == (".state", "docker-sanity-receipt.json")
            ):
                info = tarfile.TarInfo(relative.as_posix())
                data = path.read_bytes()
                info.size = len(data)
                info.mode = 0o644
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                tar.addfile(info, io.BytesIO(data))
    return _sha_bytes(archive.read_bytes())


def _docker_script(out: Path) -> str:
    task_rows = "\n".join(f'run_task "{case.task_id}" "{_tree_hash(out / case.task_id).split(":",1)[1]}"' for case in CASES)
    control_rows = "\n".join(f'run_control "{name}" "{_tree_hash(out / ".state" / "hard-rule-controls" / name).split(":",1)[1]}"' for name in _adversarial_cases())
    return f'''set -eu
mkdir -p /work/family
tar -xf /input/family.tar -C /work/family
hash_tree() {{
  root="$1"
  (cd "$root"; find . -type f | sort | while IFS= read -r f; do rel="${{f#./}}"; printf '%s\\0' "$rel"; cat "$f"; printf '\\0'; done) | sha256sum | cut -d' ' -f1
}}
configure_run() {{
  root="$1"; source="$2"; label="$3"; sanitize="$4"; expected="$5"
  build="/work/build-${{label}}-${{sanitize}}"; rm -rf "$build"
  flags=""
  if [ "$sanitize" = sanitizer ]; then flags='-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined'; fi
  cmake -G 'Unix Makefiles' -S "$root" -B "$build" -DTASK_SOURCE="$source" $flags >/work/${{label}}-${{sanitize}}-configure.log 2>&1
  cmake --build "$build" --parallel 2 >/work/${{label}}-${{sanitize}}-build.log 2>&1
  count=$(ctest --test-dir "$build" -N | grep -c 'Test #')
  [ "$count" -eq 3 ]
  if [ "$expected" = pass ]; then
    ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$build" --output-on-failure >/work/${{label}}-${{sanitize}}-test.log 2>&1
  else
    if ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$build" --output-on-failure >/work/${{label}}-${{sanitize}}-test.log 2>&1; then exit 91; fi
  fi
  printf '%s\\t%s\\t%s\\t%s\\n' "$label" "$sanitize" "$count" "$expected"
}}
run_task() {{
  id="$1"; expected_hash="$2"; root="/work/family/$id"
  actual=$(hash_tree "$root")
  if [ "$actual" != "$expected_hash" ]; then echo "TASK_HASH_MISMATCH $id $expected_hash $actual" >&2; exit 92; fi
  configure_run "$root" "$root/.meta/example.cpp" "$id-reference" normal pass
  configure_run "$root" "$root/.meta/example.cpp" "$id-reference" sanitizer pass
  configure_run "$root" "$root/.meta/negative_false_substitute.cpp" "$id-negative" normal reject
  configure_run "$root" "$root/.meta/negative_false_substitute.cpp" "$id-negative" sanitizer reject
}}
run_control() {{
  id="$1"; expected_hash="$2"; root="/work/family/.state/hard-rule-controls/$id"
  actual=$(hash_tree "$root")
  if [ "$actual" != "$expected_hash" ]; then echo "CONTROL_HASH_MISMATCH $id $expected_hash $actual" >&2; exit 93; fi
  configure_run "$root" "$root/candidate.cpp" "$id" normal pass
  configure_run "$root" "$root/candidate.cpp" "$id" sanitizer pass
}}
{task_rows}
{control_rows}
c++ --version | head -1
cmake --version | head -1
printf 'DOCKER_SANITY_OK\\n'
'''


def verify_docker(out: Path, image: str = SANITY_IMAGE) -> dict[str, object]:
    manifest = verify_core(out)
    if shutil.which("docker") is None:
        _fail("docker_sanity_not_completed", "docker CLI unavailable")
    with tempfile.TemporaryDirectory(prefix="leap-year-rule-docker-") as temp:
        temp_root = Path(temp)
        archive = temp_root / "family.tar"
        archive_hash = _make_archive(out, archive)
        script = temp_root / "verify.sh"
        script.write_text(_docker_script(out), encoding="utf-8")
        script.chmod(0o755)
        inspect = subprocess.run(
            ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        command = [
            "docker", "run", "--rm", "--network", "none",
            "--mount", f"type=bind,src={archive},dst=/input/family.tar,readonly",
            "--mount", f"type=bind,src={script},dst=/input/verify.sh,readonly",
            image, "sh", "/input/verify.sh",
        ]
        completed = subprocess.run(command, capture_output=True, text=True)
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "no Docker diagnostic").strip()
            _fail("docker_sanity_not_completed", f"exit={completed.returncode}: {detail[-2000:]}")
    if "DOCKER_SANITY_OK" not in completed.stdout:
        _fail("docker_sanity_not_completed", "terminal marker absent")
    rows = [line.split("\t") for line in completed.stdout.splitlines() if line.count("\t") == 3]
    expected_rows = len(CASES) * 4 + len(_adversarial_cases()) * 2
    if len(rows) != expected_rows or any(row[2] != "3" for row in rows):
        _fail("sanitizer_test_count_mismatch", f"rows={len(rows)} expected={expected_rows}")
    receipt = {
        "schema_version": "aider-leap-year-rule-docker-sanity-v1",
        "status": "pass",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "network_policy": "none",
        "image": image,
        "image_id": inspect,
        "archive_sha256": archive_hash,
        "generator_sha256": _source_hash(),
        "family_tree_hash": _tree_hash(out),
        "task_tree_hashes": {case.task_id: _tree_hash(out / case.task_id) for case in CASES},
        "control_tree_hashes": {name: _tree_hash(out / ".state" / "hard-rule-controls" / name) for name in _adversarial_cases()},
        "reference_hashes": {case.task_id: _sha_bytes((out / case.task_id / ".meta" / "example.cpp").read_bytes()) for case in CASES},
        "normal_test_count_per_root": 3,
        "sanitizer_test_count_per_root": 3,
        "topic_negative_count": len(CASES),
        "topic_negative_outcome": "compiled_and_rejected_in_normal_and_sanitizer",
        "control_count": len(_adversarial_cases()),
        "control_runtime_outcome": "compiled_and_passed_behavior_in_normal_and_sanitizer",
        "hard_rule_screen": "all_controls_rejected_in_all_seven_dimensions",
        "result_rows": rows,
        "toolchain_tail": completed.stdout.splitlines()[-3:-1],
        "command": ["docker", "run", "--rm", "--network", "none", "<snapshot-mount>", image, "sh", "/input/verify.sh"],
    }
    receipt_path = out / ".state" / "docker-sanity-receipt.json"
    _write(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    manifest["docker_sanity"] = {
        "status": "pass",
        "receipt": str(receipt_path.relative_to(out)),
        "normal_test_count_per_root": 3,
        "sanitizer_test_count_per_root": 3,
        "topic_negatives": len(CASES),
        "controls": len(_adversarial_cases()),
    }
    manifest["strongest_local_status"] = "local_family_verified"
    manifest["hard_rule"]["status"] = "pass"
    for value in manifest["adversarial_controls"].values():
        value["runtime_status"] = "compiled_and_passed_behavior_normal_and_sanitizer"
    _write(out / ".state" / "materialization-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    _sync_remedies(
        out,
        status="verified",
        strongest_local_status="local_family_verified",
        hard_rule_status="pass",
        docker_sanity_receipt=str(receipt_path.relative_to(out)),
        normal_test_count=3,
        sanitizer_test_count=3,
        topic_negative_outcome="compiled_and_rejected_normal_and_sanitizer",
        adversarial_control_outcome="compiled_and_passed_behavior_then_rejected_all_seven_dimensions",
    )
    return receipt


def verify_host(out: Path) -> None:
    if not shutil.which("cmake") or not shutil.which("c++"):
        _fail("verification_not_completed", "host cmake and c++ required")
    for case in CASES:
        root = out / case.task_id
        with tempfile.TemporaryDirectory(prefix="leap-year-host-") as temp:
            copied = Path(temp) / case.task_id
            shutil.copytree(root, copied)
            for mode, flags in (
                ("normal", []),
                ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]),
            ):
                build_dir = copied / f"build-{mode}"
                commands = (
                    ["cmake", "-G", "Unix Makefiles", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={copied / '.meta' / 'example.cpp'}", *flags],
                    ["cmake", "--build", str(build_dir), "--parallel", "2"],
                    ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
                )
                for command in commands:
                    subprocess.run(command, check=True, capture_output=True, text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true", help="host-only iteration evidence")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--holdout-root", type=Path, default=DEFAULT_HOLDOUT_ROOT)
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out, args.holdout_root)
    if args.verify:
        verify_host(args.out)
    if args.docker_sanity:
        verify_docker(args.out, args.image)
    print(f"Wrote {len(roots)} leap-year-rule replacement tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
