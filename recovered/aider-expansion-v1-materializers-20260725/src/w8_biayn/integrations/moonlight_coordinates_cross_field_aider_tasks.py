"""Materialize the 100-root coordinate/cross-field expansion family.

This owner writes only the count-plan expansion tree.  It never mutates either
legacy generated tree and never creates SFT rows or release artifacts.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import cache
from itertools import combinations
from pathlib import Path
from typing import Iterable, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_coordinates_cross_field_cases import (
    BASELINE,
    DOMAINS,
    PREDICATE_TRIPLES,
    Domain,
    Predicate,
    _candidate_values,
    multi_failure_witness,
    predicate_fails,
    witness_for,
)

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/validation-parsing/"
    "coordinates-cross-field-constraints"
)
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
PROTECTED_ROOTS = (
    Path(".w8-biayn/data/aider-tasks"),
    Path(".w8-biayn/data/aider-tasks-reverify"),
)
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-validation-input-parsing/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_COORDINATES_MOVES_AND_CROSS_FIELD_CONSTRAINTS_CURRICULUM.md"
)
COUNT_PLAN = Path("docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md")
SELECTED_PROMPTS = (
    "docs/aider-tasks-spec/prompts/generate-family-spec.md",
    "docs/aider-tasks-spec/prompts/implement-family-for-sft.md",
)
OWNER = "w8_biayn.integrations.moonlight_coordinates_cross_field_aider_tasks"
FAMILY_ID = "validation-parsing-coordinates-cross-field-constraints-v1"
GENERATOR_REVISION = "coordinates-cross-field-owner-v2"
MANIFEST_SCHEMA = "coordinates-cross-field-materialization-v1"
NORMALIZER = "coordinates-cross-field-artifact-seven-dimension-v1"
MIN_ROOTS = MAX_ROOTS = 100
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
ADVERSARIAL_CONTROLS = (
    "domain-identifier-renamed",
    "constants-policy-only",
    "opposite-end-selection",
)
OFFICIAL_HOLDOUTS = frozenset(
    {
        "all-your-base", "allergies", "bank-account", "binary-search-tree",
        "circular-buffer", "clock", "complex-numbers", "crypto-square",
        "diamond", "dnd-character", "gigasecond", "grade-school",
        "kindergarten-garden", "knapsack", "linked-list", "meetup",
        "parallel-letter-frequency", "perfect-numbers", "phone-number",
        "queen-attack", "robot-name", "space-age", "spiral-matrix",
        "sublist", "yacht", "zebra-puzzle",
    }
)


class VerificationError(RuntimeError):
    """Fail-closed owner verification error with a stable reason code."""


@dataclass(frozen=True)
class Case:
    index: int
    domain: Domain
    rules: tuple[Predicate, Predicate, Predicate]


CASES = tuple(
    Case(index, domain, PREDICATE_TRIPLES[index]) for index, domain in enumerate(DOMAINS)
)


def _fail(code: str, detail: str) -> None:
    raise VerificationError(f"{code}: {detail}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _write(path: Path, data: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)


def _owner_hash() -> str:
    paths = (Path(__file__), Path(__file__).with_name("moonlight_coordinates_cross_field_cases.py"))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _slug_to_identifier(slug: str) -> str:
    return slug.replace("-", "_")


def _camel(slug: str) -> str:
    return "".join(part.capitalize() for part in slug.split("-"))


def _safe_relative(path: str) -> bool:
    candidate = Path(path)
    return not candidate.is_absolute() and ".." not in candidate.parts


def _root_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def _tree_hash(root: Path, *, include_state: bool = False) -> str:
    digest = hashlib.sha256()
    for path in _root_files(root):
        relative = path.relative_to(root)
        if not include_state and ".state" in relative.parts:
            continue
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _file_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path.read_bytes())
        for path in _root_files(root)
        if ".state" not in path.relative_to(root).parts
    }


def _validate_output(out: Path) -> None:
    repo = Path.cwd().resolve()
    expansion = (repo / EXPANSION_ROOT).resolve()
    resolved = out.resolve(strict=False)
    for protected in PROTECTED_ROOTS:
        protected_resolved = (repo / protected).resolve(strict=False)
        if resolved == protected_resolved or protected_resolved in resolved.parents:
            _fail("protected_output_root", str(out))
    if resolved == expansion or expansion not in resolved.parents:
        _fail("unsafe_output_root", f"output must be a family beneath {EXPANSION_ROOT}: {out}")
    cursor = resolved
    while cursor != repo and cursor != cursor.parent:
        if cursor.exists() and cursor.is_symlink():
            _fail("symlink_output_root", str(cursor))
        cursor = cursor.parent


def _inventory(root: Path) -> list[dict[str, str]]:
    if not root.exists():
        return []
    for attempt in range(5):
        rows: list[dict[str, str]] = []
        try:
            for config in sorted(root.rglob(".meta/config.json")):
                if ".state" in config.parts:
                    continue
                task_root = config.parent.parent
                config_bytes = config.read_bytes()
                payload = json.loads(config_bytes)
                rows.append(
                    {
                        "task_id": payload.get("task_id", task_root.name),
                        "root": task_root.as_posix(),
                        "config_hash": _sha256(config_bytes),
                        "tree_hash": _tree_hash(task_root),
                    }
                )
            return rows
        except FileNotFoundError:
            if attempt == 4:
                _fail("source_inventory_race", root.as_posix())
    raise AssertionError("unreachable")


def _frozen_inventory() -> dict[str, object]:
    trees = {root.as_posix(): _inventory(root) for root in (*PROTECTED_ROOTS, EXPANSION_ROOT)}
    sorted_ids = sorted(row["task_id"] for rows in trees.values() for row in rows)
    return {
        "schema_version": "coordinates-cross-field-source-inventory-v1",
        "trees": trees,
        "counts": {path: len(rows) for path, rows in trees.items()},
        "sorted_task_id_hash": _sha256("\n".join(sorted_ids).encode()),
    }


def _rule_code(rule: Predicate, fields: tuple[str, ...], shift: int) -> str:
    a, b, c, d, e, f = (f"({field} - {shift}LL)" for field in fields)
    expressions = {
        "coord_forward": f"{b} <= {a}",
        "coord_distinct": f"{b} == {a}",
        "coord_adjacent": f"{b} - {a} != 1",
        "coord_declared_span": f"{c} != {a} + {b}",
        "coord_span_limit": f"{b} - {a} > {c}",
        "coord_endpoint_blocked": f"{a} == {d} || {b} == {d}",
        "coord_blocked_between": f"({a} <= {d} && {d} <= {b})",
        "coord_budget": f"{c} > {e}",
        "coord_positive_count": f"{c} < 1",
        "coord_marker_after_count": f"{d} <= {c}",
        "coord_route_checksum": f"{f} != {c} + {d} - 1",
        "coord_terminal_budget": f"{f} <= {e}",
        "coord_terminal_count": f"{f} < {c}",
        "coord_even_check": f"{f} % 2 != 0",
        "coord_endpoint_check": f"{a} + {e} != {f}",
        "pair_ordered": f"{b} <= {a}",
        "pair_distinct": f"{b} == {a}",
        "pair_adjacent": f"{b} - {a} != 1",
        "pair_declared_total": f"{c} != {a} + {b}",
        "pair_within_limit": f"{a} > {d}",
        "pair_count_limit": f"{c} > {d}",
        "pair_count_evidence": f"{c} + {e} > {f} + 3",
        "pair_evidence_check": f"{e} > {c} + {d}",
        "pair_combined_capacity": f"{c} + {d} < {e}",
        "pair_limit_before_evidence": f"{d} >= {e}",
        "pair_evidence_offset": f"{e} != {c} + 2",
        "pair_check_successor": f"{f} != {e} + 1",
        "pair_first_evidence_check": f"{a} + {e} != {f}",
        "pair_second_limit_check": f"{b} + {d} != {f}",
        "pair_doubled_count_check": f"{c} * 2 != {f}",
        "state_conservation": f"{a} + {b} != {c}",
        "state_component_order": f"{a} >= {b}",
        "state_components_distinct": f"{a} == {b}",
        "state_component_delta": f"{b} - {a} != 1",
        "state_nonnegative": f"{a} < 0",
        "state_capacity": f"{c} > {d}",
        "state_aux_total": f"{e} > {b} + {d}",
        "state_first_plus_total": f"{a} + {c} > {d}",
        "state_second_plus_aux": f"{b} + {e} < {c}",
        "state_capacity_successor": f"{d} != {c} + 1",
        "state_aux_capacity_window": f"{e} > {d} + 1",
        "state_check_successor": f"{f} != {e} + 1",
        "state_first_aux_check": f"{a} + {e} != {f}",
        "state_double_total_check": f"{c} * 2 != {f}",
        "state_second_capacity_check": f"{b} + {d} != {f}",
        "review_monotone": f"{b} < {a}",
        "review_changed": f"{b} == {a}",
        "review_single_step": f"{b} - {a} != 1",
        "review_declared_total": f"{c} != {a} + {b}",
        "review_within_limit": f"{b} > {d}",
        "review_count_limit": f"{c} + {e} > {d} + {f}",
        "review_count_evidence": f"{c} > {d} + {e}",
        "review_evidence_check": f"{e} + {a} > {f} + {b}",
        "review_combined_capacity": f"{c} + {d} + {e} < {f}",
        "review_limit_before_evidence": f"{d} + {a} >= {f}",
        "review_evidence_offset": f"{e} != {d} + 1",
        "review_check_successor": f"{f} != {d} + 2",
        "review_original_evidence_check": f"{a} + {b} + {c} != {f}",
        "review_revised_limit_check": f"{b} + {c} != {e}",
        "review_doubled_count_check": f"{a} + {d} != {e}",
    }
    return expressions[rule.kind]


def _values(values: Iterable[int]) -> str:
    return ", ".join(str(value) for value in values)


def _certificate_value(case: Case, values: tuple[int, ...], shift: int = 0) -> int:
    a, b, c, d, e, f = (value - shift for value in values)
    if case.domain.capability == "coordinate_bounds_and_routes":
        return (b - a) + c + d + e + f
    if case.domain.capability == "paired_field_consistency":
        return (b - a) + c + d + e + f
    if case.domain.capability == "impossible_state_rejection":
        return a + b + c + d + e + f
    return a + 2 * b + c + d + e + f


def _certificate_code(case: Case, fields: tuple[str, ...], shift: int) -> str:
    a, b, c, d, e, f = (f"({field} - {shift}LL)" for field in fields)
    if case.domain.capability == "coordinate_bounds_and_routes":
        return f"({b} - {a}) + {c} + {d} + {e} + {f}"
    if case.domain.capability == "paired_field_consistency":
        return f"({b} - {a}) + {c} + {d} + {e} + {f}"
    if case.domain.capability == "impossible_state_rejection":
        return f"{a} + {b} + {c} + {d} + {e} + {f}"
    return f"{a} + 2 * {b} + {c} + {d} + {e} + {f}"


def _accepted_examples(case: Case, shift: int) -> tuple[tuple[int, ...], ...]:
    accepted = [
        values
        for values in _candidate_values(shift)
        if not any(predicate_fails(rule.kind, values, shift) for rule in case.rules)
    ]
    distinct: list[tuple[int, ...]] = []
    seen_certificates: set[int] = set()
    for values in accepted:
        certificate = _certificate_value(case, values, shift)
        if certificate in seen_certificates:
            continue
        distinct.append(values)
        seen_certificates.add(certificate)
        if len(distinct) == 3:
            break
    if len(distinct) != 3:
        _fail("insufficient_success_oracle", case.domain.task_id)
    return tuple(distinct)


def _render_case(
    case: Case,
    root: Path,
    *,
    shift: int = 0,
    reverse_precedence: bool = False,
    namespace: str = "coordinate_constraints",
    control_kind: str | None = None,
) -> None:
    task_id = case.domain.task_id
    header_name, source_name = f"{task_id}.h", f"{task_id}.cpp"
    prefix = _camel(task_id.removeprefix("constraint-"))
    function_name = f"assess_{_slug_to_identifier(task_id.removeprefix('constraint-'))}"
    request_name, decision_name, error_name = f"{prefix}Request", f"{prefix}Decision", f"{prefix}Error"
    order = tuple(reversed(case.rules)) if reverse_precedence else case.rules
    base = tuple(value + shift for value in BASELINE)
    independent_witnesses = {
        rule: witness_for(rule, tuple(other for other in case.rules if other != rule), shift)
        for rule in case.rules
    }
    if any(witness is None for witness in independent_witnesses.values()):
        _fail("missing_negative_witness", task_id)
    multi = multi_failure_witness(case.rules, shift)
    failed_multi = [rule for rule in order if predicate_fails(rule.kind, multi, shift)]
    if len(failed_multi) < 2:
        _fail("missing_precedence_witness", task_id)
    enum_names = [rule.error for rule in case.rules]
    rule_rows = [
        f"{position + 1}. `{rule.error}`: {rule.description}."
        for position, rule in enumerate(order)
    ]
    field_rows = "\n".join(
        f"- `{field}` is field {position + 1} in the cross-field record."
        for position, field in enumerate(case.domain.fields)
    )
    docs = f"# {case.domain.title}\n\n"
    docs += (
        f"Implement `{function_name}` in namespace `{namespace}`. The function validates one "
        f"{case.domain.capability.replace('_', ' ')} record atomically. It must return without "
        "partial output and must use the stable error precedence below.\n\n"
        "## Public API\n\n"
        f"The editable header declares `{request_name}`, `{error_name}`, `{decision_name}`, and "
        f"`{function_name}(const {request_name}&)`. All six request fields are signed integers. "
        "A valid record returns `accepted == true`, `error == none`, and a deterministic integer "
        "certificate equal to the exact formula published below. An invalid record returns "
        "`accepted == false`, its first error under the stated precedence, and certificate zero.\n\n"
        "## Fields\n\n"
        f"{field_rows}\n\n"
        "## Cross-field rules and diagnostic precedence\n\n"
        f"{' '.join(rule_rows)}\n\n"
        f"The policy constant shift is `{shift}`. Normalize each field by subtracting that shift. "
        f"On success the exact certificate is `{_certificate_code(case, case.domain.fields, shift)}`. "
        f"Values `{_values(base)}` in field order form a "
        "valid boundary example. When several rules fail, report the first rule in the precedence "
        "above. Do not sort, clamp, coerce, or repair the request before validation.\n\n"
        "## Required mechanism\n\n"
        "Evaluate the three published relationships directly on the original typed fields, in the "
        "published diagnostic order. A generic always-accepting checker, field-by-field bounds-only "
        "checker, reordered last-error selector, or policy that silently adjusts fields is forbidden.\n"
    )
    introduction = (
        f"# {case.domain.title}\n\n"
        "This clean-room task exercises coordinate or cross-field semantic rejection after lexical "
        "values have already been parsed. It is local candidate material only.\n"
    )
    guard = re.sub(r"[^A-Z0-9]", "_", task_id.upper()) + "_H"
    enum_body = ", ".join(("none", *enum_names))
    fields_body = " ".join(f"int {field};" for field in case.domain.fields)
    header = f"#ifndef {guard}\n#define {guard}\n\nnamespace {namespace} {{\n"
    header += f"enum class {error_name} {{ {enum_body} }};\n"
    header += f"struct {request_name} {{ {fields_body} }};\n"
    header += f"struct {decision_name} {{ bool accepted; {error_name} error; long long certificate; }};\n"
    header += f"{decision_name} {function_name}(const {request_name}& request);\n"
    header += f"}}  // namespace {namespace}\n\n#endif\n"
    condition_rows = []
    for rule in order:
        condition_rows.append(
            f"  if ({_rule_code(rule, case.domain.fields, shift)}) {{\n"
            f"    return {{false, {error_name}::{rule.error}, 0}};\n"
            "  }"
        )
    certificate = _certificate_code(case, case.domain.fields, shift)
    aliases = "\n".join(
        f"  const long long {field} = request.{field};" for field in case.domain.fields
    )
    source = f"#include \"{header_name}\"\n\nnamespace {namespace} {{\n"
    source += f"{decision_name} {function_name}(const {request_name}& request) {{\n{aliases}\n"
    source += "\n".join(condition_rows)
    source += f"\n  return {{true, {error_name}::none, {certificate}}};\n"
    source += f"}}\n}}  // namespace {namespace}\n"
    negative_rows = [row for rule, row in zip(order, condition_rows, strict=True) if rule != order[0]]
    negative = f"#include \"../{header_name}\"\n\nnamespace {namespace} {{\n"
    negative += f"{decision_name} {function_name}(const {request_name}& request) {{\n{aliases}\n"
    negative += "\n".join(negative_rows)
    negative += f"\n  return {{true, {error_name}::none, {certificate}}};\n"
    negative += f"}}\n}}  // namespace {namespace}\n"
    wrong_success = f"#include \"../{header_name}\"\n\nnamespace {namespace} {{\n"
    wrong_success += f"{decision_name} {function_name}(const {request_name}& request) {{\n{aliases}\n"
    wrong_success += "\n".join(condition_rows)
    consumed = " + ".join(case.domain.fields)
    wrong_success += f"\n  return {{true, {error_name}::none, 1 + 0LL * ({consumed})}};\n"
    wrong_success += f"}}\n}}  // namespace {namespace}\n"
    starter = f"#include \"{header_name}\"\n\nnamespace {namespace} {{\n"
    starter += f"{decision_name} {function_name}(const {request_name}&) {{\n"
    starter += f"  return {{false, {error_name}::{order[0].error}, 0}};\n"
    starter += f"}}\n}}  // namespace {namespace}\n"
    visible = f"#include \"{header_name}\"\n\nint main() {{\n"
    visible += f"  const {namespace}::{request_name} request{{{_values(base)}}};\n"
    visible += f"  const auto decision = {namespace}::{function_name}(request);\n"
    visible += f"  return decision.accepted && decision.error == {namespace}::{error_name}::none && decision.certificate == {_certificate_value(case, base, shift)} ? 0 : 1;\n}}\n"
    expected_multi = failed_multi[0].error
    hidden = f"#include \"../{header_name}\"\n\n#include <limits>\n\nint main() {{\n"
    for position, rule in enumerate(case.rules, start=1):
        witness = independent_witnesses[rule]
        hidden += f"  const {namespace}::{request_name} witness_{position}{{{_values(witness)}}};\n"
        hidden += f"  const auto rejected_{position} = {namespace}::{function_name}(witness_{position});\n"
        hidden += f"  if (rejected_{position}.accepted || rejected_{position}.error != {namespace}::{error_name}::{rule.error} || rejected_{position}.certificate != 0) return {position};\n"
    hidden += f"  const {namespace}::{request_name} several{{{_values(multi)}}};\n"
    hidden += f"  const auto precedence = {namespace}::{function_name}(several);\n"
    hidden += f"  if (precedence.accepted || precedence.error != {namespace}::{error_name}::{expected_multi} || precedence.certificate != 0) return 9;\n"
    for position, accepted in enumerate(_accepted_examples(case, shift), start=20):
        hidden += f"  const {namespace}::{request_name} accepted_{position}{{{_values(accepted)}}};\n"
        hidden += f"  const auto success_{position} = {namespace}::{function_name}(accepted_{position});\n"
        hidden += f"  if (!success_{position}.accepted || success_{position}.error != {namespace}::{error_name}::none || success_{position}.certificate != {_certificate_value(case, accepted, shift)}) return {position};\n"
    extrema = ("std::numeric_limits<int>::min()", "std::numeric_limits<int>::max()")
    return_code = 40
    for field_index in range(6):
        for extreme_index, literal in enumerate(extrema):
            boundary = list(base)
            boundary[field_index] = -(2**31) if extreme_index == 0 else 2**31 - 1
            boundary_tuple = tuple(boundary)
            first_failure = next(
                (rule for rule in order if predicate_fails(rule.kind, boundary_tuple, shift)),
                None,
            )
            values_cpp = [str(value) for value in base]
            values_cpp[field_index] = literal
            hidden += f"  const {namespace}::{request_name} boundary_{return_code}{{{', '.join(values_cpp)}}};\n"
            hidden += f"  const auto boundary_result_{return_code} = {namespace}::{function_name}(boundary_{return_code});\n"
            if first_failure is None:
                expected = _certificate_value(case, boundary_tuple, shift)
                hidden += f"  if (!boundary_result_{return_code}.accepted || boundary_result_{return_code}.error != {namespace}::{error_name}::none || boundary_result_{return_code}.certificate != {expected}) return {return_code};\n"
            else:
                hidden += f"  if (boundary_result_{return_code}.accepted || boundary_result_{return_code}.error != {namespace}::{error_name}::{first_failure.error} || boundary_result_{return_code}.certificate != 0) return {return_code};\n"
            return_code += 1
    hidden += "  return 0;\n}\n"
    cmake = f"""cmake_minimum_required(VERSION 3.16)\nproject({function_name} LANGUAGES CXX)\nset(CMAKE_CXX_STANDARD 17)\nset(CMAKE_CXX_STANDARD_REQUIRED ON)\nset(CMAKE_CXX_EXTENSIONS OFF)\nif(CMAKE_CXX_COMPILER_ID MATCHES \"GNU|Clang\")\n  add_compile_options(-Wall -Wextra -Wpedantic -Werror)\nendif()\nif(W8_SANITIZE)\n  add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer)\n  add_link_options(-fsanitize=address,undefined)\nendif()\nenable_testing()\nadd_executable(task_visible {source_name} task_visible_test.cpp)\nadd_executable(task_hidden {source_name} .meta/task_hidden_test.cpp)\nadd_executable(topic_negative .meta/negative_fixture.cpp .meta/task_hidden_test.cpp)\nadd_executable(success_negative .meta/wrong_success_fixture.cpp .meta/task_hidden_test.cpp)\ntarget_include_directories(task_visible PRIVATE .)\ntarget_include_directories(task_hidden PRIVATE .)\ntarget_include_directories(topic_negative PRIVATE .)\ntarget_include_directories(success_negative PRIVATE .)\nadd_test(NAME visible_contract COMMAND task_visible)\nadd_test(NAME hidden_contract COMMAND task_hidden)\nadd_test(NAME topic_negative_rejected COMMAND topic_negative)\nadd_test(NAME wrong_success_rejected COMMAND success_negative)\nset_tests_properties(topic_negative_rejected PROPERTIES WILL_FAIL TRUE)\nset_tests_properties(wrong_success_rejected PROPERTIES WILL_FAIL TRUE)\n"""
    config = {
        "authors": ["w8-biayn"],
        "blurb": f"Validate {case.domain.title.lower()} cross-field constraints atomically.",
        "family_id": FAMILY_ID,
        "files": {
            "solution": [header_name, source_name],
            "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
        "task_id": task_id,
    }
    provenance = {
        "authoring_origin": "independently authored clean-room generated family",
        "benchmark_holdout_separation": "all 26 official Aider Polyglot C++ roots are permanent holdouts",
        "capability": case.domain.capability,
        "control_kind": control_kind,
        "curriculum": CURRICULUM.as_posix(),
        "family_id": FAMILY_ID,
        "generator_revision": GENERATOR_REVISION,
        "license": "repository-local research task; no upstream attribution claimed",
        "lineage": "new_root",
        "owner": OWNER,
        "release_status": "local candidate only; not dataset admission",
        "predicate_kinds": [rule.kind for rule in case.rules],
        "task_id": task_id,
    }
    tests_toml = (
        "[visible]\n"
        'description = "documented valid boundary and deterministic certificate"\n\n'
        "[hidden]\n"
        'description = "primary-only counterexample, multi-error precedence, and atomic rejection"\n\n'
        "[negative]\n"
        f'description = "compiled substitute omits {order[0].error}; another returns a constant success certificate; both must be rejected"\n'
    )
    _write(root / ".docs/introduction.md", introduction)
    _write(root / ".docs/instructions.md", docs)
    _write(root / header_name, header)
    _write(root / source_name, starter)
    _write(root / "task_visible_test.cpp", visible)
    _write(root / "CMakeLists.txt", cmake)
    _write(root / ".meta/config.json", _json_bytes(config))
    _write(root / ".meta/provenance.json", _json_bytes(provenance))
    _write(root / ".meta/tests.toml", tests_toml)
    _write(root / ".meta/example.h", header)
    _write(root / ".meta/example.cpp", source)
    _write(root / ".meta/task_hidden_test.cpp", hidden)
    _write(root / ".meta/negative_fixture.cpp", negative)
    _write(root / ".meta/wrong_success_fixture.cpp", wrong_success)


def _task_root(out: Path, case: Case) -> Path:
    return out / case.domain.task_id


def _known_owner(root: Path) -> bool:
    provenance = root / ".meta/provenance.json"
    if not provenance.exists():
        return False
    try:
        return json.loads(provenance.read_text(encoding="utf-8")).get("owner") == OWNER
    except json.JSONDecodeError:
        return False


def _prepare_output(out: Path, force: bool) -> None:
    _validate_output(out)
    out.mkdir(parents=True, exist_ok=True)
    foreign = [
        child for child in out.iterdir()
        if child.name != ".state" and child.is_dir() and not _known_owner(child)
    ]
    if foreign:
        _fail("foreign_generated_root", ", ".join(path.name for path in foreign))
    present = [child for child in out.iterdir() if child.name != ".state" and child.is_dir()]
    if present and not force:
        _fail("output_exists", "use --force for owner-controlled regeneration")
    for child in present:
        shutil.rmtree(child)
    state = out / ".state"
    state.mkdir(parents=True, exist_ok=True)
    for name in (
        "adversarial-controls", "candidate-manifest.json", "family-screen.json",
        "creator-preflight.json", "docker-sanity.json", "source-inventory.json",
        "comparison-manifest.json", "comparison-snapshot", "audit-subject.json",
    ):
        path = state / name
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def materialize(out: Path, *, force: bool = False) -> dict[str, object]:
    _prepare_output(out, force)
    source_inventory = _frozen_inventory()
    existing_ids = {
        row["task_id"]
        for rows in source_inventory["trees"].values()
        for row in rows
    }
    collisions = sorted(case.domain.task_id for case in CASES if case.domain.task_id in existing_ids)
    if collisions:
        _fail("duplicate_task", ", ".join(collisions))
    for case in CASES:
        _render_case(case, _task_root(out, case))
    _write(out / ".state/source-inventory.json", _json_bytes(source_inventory))
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "family_id": FAMILY_ID,
        "owner": OWNER,
        "owner_hash": _owner_hash(),
        "curriculum": CURRICULUM.as_posix(),
        "curriculum_hash": _sha256(CURRICULUM.read_bytes()),
        "count_plan": COUNT_PLAN.as_posix(),
        "count_plan_hash": _sha256(COUNT_PLAN.read_bytes()),
        "selected_prompts": list(SELECTED_PROMPTS),
        "requested_count": 100,
        "task_count": len(CASES),
        "task_ids": [case.domain.task_id for case in CASES],
        "roots": {
            case.domain.task_id: {
                "tree_hash": _tree_hash(_task_root(out, case)),
                "predicate_kinds": [rule.kind for rule in case.rules],
                "capability": case.domain.capability,
                "lineage": "new_root",
                "candidate_state": "draft",
            }
            for case in CASES
        },
        "rejected": [],
        "replaced": [],
        "release_status": "not_requested",
    }
    _write(out / ".state/candidate-manifest.json", _json_bytes(manifest))
    return manifest


_CPP_KEYWORDS = frozenset(
    "alignas alignof and and_eq asm auto bitand bitor bool break case catch char class "
    "const constexpr continue default delete do double else enum explicit export extern false "
    "float for friend goto if inline int long namespace new noexcept not nullptr operator or "
    "private protected public register reinterpret_cast return short signed sizeof static struct "
    "switch template this throw true try typedef typeid typename union unsigned using virtual void "
    "volatile while xor include define endif".split()
)


@cache
def _semantic_identity_map() -> dict[str, str]:
    return {
        name: "predicate_" + _sha256(
            _rule_code(rule, ("a", "b", "c", "d", "e", "f"), 0).encode()
        )[:16]
        for case in CASES
        for rule in case.rules
        for name in (rule.kind, rule.error)
    }


def _semantic_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " STRING ", text)
    text = re.sub(r"\b\d+\b", " NUMBER ", text)
    words = re.findall(r"[a-z_][a-z0-9_]*|==|!=|<=|>=|&&|\|\||[+*/%<>{}()-]", text.lower())
    normalized = []
    semantic_identities = _semantic_identity_map()
    for word in words:
        if word in semantic_identities:
            # Generated labels are canonicalized to their executable predicate
            # identity.  A pair/review rename of the same expression therefore
            # cannot manufacture diversity.
            normalized.append(semantic_identities[word])
        elif word in _CPP_KEYWORDS or word in {"number", "string"}:
            normalized.append(word)
        else:
            # Domain nouns and C++ identifiers are intentionally erased.  The
            # retained evidence is operators, control-flow tokens, types, and
            # the published semantic error predicates.  This makes a coherent
            # noun/API rename invisible to the production duplicate screen.
            normalized.append("IDENTIFIER")
    return tuple(normalized)


def _ngrams(tokens: tuple[str, ...], width: int = 3) -> set[str]:
    if len(tokens) < width:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[index:index + width]) for index in range(len(tokens) - width + 1)}


def _dimension_text(root: Path) -> dict[str, str]:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    header, source = (root / path for path in config["files"]["solution"])
    docs = (root / ".docs/instructions.md").read_text(encoding="utf-8")
    reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    hidden = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
    negative = (root / ".meta/negative_fixture.cpp").read_text(encoding="utf-8")
    header_text = header.read_text(encoding="utf-8")
    return {
        "public_api": header_text + "\n" + docs.split("## Cross-field rules", 1)[0],
        "owned_state_algorithm": docs.split("## Cross-field rules", 1)[-1] + "\n" + reference,
        "mutation_selection_rules": docs + "\n" + reference,
        "invalid_boundary_behavior": docs + "\n" + hidden,
        "reference_control_flow": reference,
        "deterministic_oracle": visible + "\n" + hidden,
        "topic_specific_negative_fixture": negative + "\n" + hidden,
    }


@cache
def _features(root: Path) -> dict[str, set[str]]:
    # Token bags deliberately ignore statement and endpoint ordering.  An
    # opposite-end or last-error clone therefore cannot manufacture novelty;
    # distinct retained roots still carry different predicate/operator sets.
    return {dimension: _ngrams(_semantic_tokens(text), 1) for dimension, text in _dimension_text(root).items()}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def _pair_decision(left: Path, right: Path) -> dict[str, object]:
    left_features, right_features = _features(left), _features(right)
    dimensions = {}
    for dimension in HARD_RULE_DIMENSIONS:
        left_set, right_set = left_features[dimension], right_features[dimension]
        similarity = _jaccard(left_set, right_set)
        dimensions[dimension] = {
            "similarity": round(similarity, 6),
            "symmetric_difference": len(left_set ^ right_set),
            "pass": similarity < 0.995 and bool(left_set ^ right_set),
        }
    return {
        "left": left.name,
        "right": right.name,
        "dimensions": dimensions,
        "pass": all(row["pass"] for row in dimensions.values()),
    }


def _materialize_controls(out: Path) -> dict[str, dict[str, object]]:
    controls_root = out / ".state/adversarial-controls"
    if controls_root.exists():
        shutil.rmtree(controls_root)
    controls: dict[str, dict[str, object]] = {}
    plans = (
        (ADVERSARIAL_CONTROLS[0], CASES[0], 0, False, "renamed_coordinate_domain"),
        # Case 2's three predicates are invariant under a coherent +1 policy
        # shift; the emitted constant policy and all oracle values still
        # change, while the primary semantic contract remains a clone.
        (ADVERSARIAL_CONTROLS[1], CASES[2], 1, False, "coordinate_constraints"),
        (ADVERSARIAL_CONTROLS[2], CASES[3], 0, True, "coordinate_constraints"),
    )
    for kind, case, shift, reverse, namespace in plans:
        source = _task_root(out, case)
        destination = controls_root / kind / case.domain.task_id
        shutil.copytree(source, destination)
        before = _file_hashes(destination)
        _render_case(
            case,
            destination,
            shift=shift,
            reverse_precedence=reverse,
            namespace=namespace,
            control_kind=kind,
        )
        after = _file_hashes(destination)
        changed = sorted(path for path in after if before.get(path) != after[path])
        decision = _pair_decision(source, destination)
        controls[kind] = {
            "base_task_id": case.domain.task_id,
            "base_tree_hash": _tree_hash(source),
            "control_tree_hash": _tree_hash(destination),
            "changed_files": changed,
            "changed": bool(changed),
            "coherent_build_pending": True,
            "production_evaluator": decision,
            "rejected_in_all_seven_dimensions": not any(
                row["pass"] for row in decision["dimensions"].values()
            ),
            "root": destination.relative_to(out).as_posix(),
        }
        if not changed:
            _fail("adversarial_control_noop", kind)
        if not controls[kind]["rejected_in_all_seven_dimensions"]:
            _fail("adversarial_control_not_rejected", kind)
    return controls


COMPARISON_ROLES = (
    ".docs/introduction.md",
    ".docs/instructions.md",
    ".meta/example.h",
    ".meta/example.cpp",
    "task_visible_test.cpp",
    ".meta/task_hidden_test.cpp",
)


def _document_snapshot(root: Path) -> bytes:
    payload = {
        relative: (root / relative).read_text(encoding="utf-8")
        for relative in COMPARISON_ROLES
        if (root / relative).exists()
    }
    return _json_bytes(payload)


def _snapshot_blob(snapshot: bytes) -> str:
    payload = json.loads(snapshot)
    return "\n".join(payload[relative] for relative in COMPARISON_ROLES if relative in payload)


def _document_blob(root: Path) -> str:
    return _snapshot_blob(_document_snapshot(root))


def _corpus_screen(out: Path) -> dict[str, object]:
    candidate_roots = [_task_root(out, case) for case in CASES]
    candidate_ids = {root.name for root in candidate_roots}
    if candidate_ids & OFFICIAL_HOLDOUTS:
        _fail("benchmark_id_overlap", ", ".join(sorted(candidate_ids & OFFICIAL_HOLDOUTS)))
    source_inventory_path = out / ".state/source-inventory.json"
    frozen = json.loads(source_inventory_path.read_text(encoding="utf-8"))
    external_by_scope: dict[str, list[Path]] = {}
    for source_path, rows in frozen["trees"].items():
        scope = "prior_expansion" if source_path == EXPANSION_ROOT.as_posix() else source_path
        external_by_scope[scope] = [Path(row["root"]) for row in rows]
    holdout_roots = [HOLDOUT_ROOT / slug for slug in sorted(OFFICIAL_HOLDOUTS)]
    if not all(root.exists() for root in holdout_roots):
        missing = [root.name for root in holdout_roots if not root.exists()]
        _fail("holdout_inventory_missing", ", ".join(missing))
    revision = subprocess.run(
        ["git", "-C", str(HOLDOUT_ROOT.parents[2]), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    snapshot_root = out / ".state/comparison-snapshot"
    if snapshot_root.exists():
        shutil.rmtree(snapshot_root)
    snapshot_root.mkdir(parents=True)
    inventory_by_root = {
        row["root"]: row
        for rows in frozen["trees"].values()
        for row in rows
    }
    snapshot_records: dict[str, dict[str, object]] = {}
    external_features: dict[str, set[str]] = {}
    for scope, roots in (*external_by_scope.items(), ("official_holdout", holdout_roots)):
        for root in roots:
            try:
                before = _tree_hash(root)
                snapshot = _document_snapshot(root)
                after = _tree_hash(root)
            except FileNotFoundError:
                _fail("comparison_source_unstable", root.as_posix())
            expected = inventory_by_root.get(root.as_posix(), {}).get("tree_hash")
            if before != after or (expected is not None and before != expected):
                _fail("comparison_source_unstable", root.as_posix())
            blob_hash = _sha256(snapshot)
            blob_path = snapshot_root / "blobs" / f"{blob_hash}.json"
            if not blob_path.exists():
                _write(blob_path, snapshot)
            features = _ngrams(_semantic_tokens(_snapshot_blob(snapshot)), 4)
            feature_bytes = _json_bytes(sorted(features))
            snapshot_records[root.as_posix()] = {
                "scope": scope,
                "task_id": inventory_by_root.get(root.as_posix(), {}).get("task_id", root.name),
                "root": root.as_posix(),
                "tree_hash": before,
                "blob": blob_path.relative_to(out).as_posix(),
                "blob_hash": blob_hash,
                "blob_size": len(snapshot),
                "semantic_feature_hash": _sha256(feature_bytes),
                "semantic_feature_count": len(features),
            }
            external_features[root.as_posix()] = features
    comparison_manifest = {
        "schema_version": "coordinates-cross-field-comparison-manifest-v2",
        "source_inventory_hash": _sha256(source_inventory_path.read_bytes()),
        "source_roots": frozen["trees"],
        "holdout_checkout": HOLDOUT_ROOT.parents[2].as_posix(),
        "holdout_revision": revision,
        "comparison_roles": list(COMPARISON_ROLES),
        "snapshot_records": snapshot_records,
        "snapshot_root_hash": _tree_hash(snapshot_root),
        "snapshot_blob_count": len(list((snapshot_root / "blobs").glob("*.json"))),
    }
    comparison_manifest_path = out / ".state/comparison-manifest.json"
    _write(comparison_manifest_path, _json_bytes(comparison_manifest))
    candidate_features = {root.name: _ngrams(_semantic_tokens(_document_blob(root)), 4) for root in candidate_roots}
    comparisons = 0
    max_similarity: dict[str, dict[str, object]] = {}
    violations = []
    for candidate in candidate_roots:
        best = {"other": "", "similarity": 0.0, "scope": ""}
        scopes = [*external_by_scope.items(), ("official_holdout", holdout_roots)]
        for scope, roots in scopes:
            for other in roots:
                comparisons += 1
                similarity = _jaccard(
                    candidate_features[candidate.name], external_features[other.as_posix()]
                )
                if similarity > best["similarity"]:
                    best = {"other": other.as_posix(), "similarity": round(similarity, 6), "scope": scope}
                if similarity >= 0.90:
                    violations.append({"candidate": candidate.name, "other": other.as_posix(), "similarity": similarity})
        max_similarity[candidate.name] = best
    if violations:
        _fail("benchmark_content_overlap", json.dumps(violations[:5], sort_keys=True))
    return {
        "status": "pass",
        "normalizer": NORMALIZER,
        "comparison_count": comparisons,
        "existing_root_count": sum(len(roots) for roots in external_by_scope.values()),
        "existing_root_counts": {scope: len(roots) for scope, roots in external_by_scope.items()},
        "holdout_root_count": len(holdout_roots),
        "comparison_manifest_hash": _sha256(comparison_manifest_path.read_bytes()),
        "source_inventory_hash": _sha256(source_inventory_path.read_bytes()),
        "maximum_similarity_by_task": max_similarity,
        "violations": [],
    }


def _validate_prompt_and_roles(root: Path) -> dict[str, object]:
    loaded = load_task(root)
    prompt = build_prompt(loaded)
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    solution = config["files"]["solution"]
    if len(solution) != 2 or not all(_safe_relative(path) for path in solution):
        _fail("unsafe_path", root.name)
    forbidden = (".meta/", "CMakeLists.txt", "task_visible_test.cpp", "negative_fixture", "provenance.json")
    if any(token in prompt for token in forbidden):
        _fail("prompt_contract_incomplete", root.name)
    if not all(path in prompt for path in solution):
        _fail("target_reference_mismatch", root.name)
    examples = config["files"]["example"]
    if examples != [".meta/example.h", ".meta/example.cpp"]:
        _fail("target_reference_mismatch", root.name)
    return {"prompt_hash": _sha256(prompt.encode()), "prompt_length": len(prompt), "solution": solution}


def verify_core(out: Path) -> dict[str, object]:
    _features.cache_clear()
    _validate_output(out)
    manifest_path = out / ".state/candidate-manifest.json"
    if not manifest_path.exists():
        _fail("generator_output_drift", "missing candidate manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    roots = [_task_root(out, case) for case in CASES]
    if len(roots) != 100 or any(not root.exists() for root in roots):
        _fail("hard_rule_root_count", "expected exactly 100 generated roots")
    if len(_inventory(out)) != 100:
        _fail("hard_rule_root_count", "real config inventory differs from 100")
    if manifest.get("owner_hash") != _owner_hash():
        _fail("generator_output_drift", "owner hash changed after materialization")
    prompt_records = {root.name: _validate_prompt_and_roles(root) for root in roots}
    pairs = [_pair_decision(left, right) for left, right in combinations(roots, 2)]
    expected_pairs = 100 * 99 // 2
    if len(pairs) != expected_pairs:
        _fail("hard_rule_evidence_incomplete", f"{len(pairs)} != {expected_pairs}")
    failed = [pair for pair in pairs if not pair["pass"]]
    if failed:
        _fail("duplicate_family", json.dumps(failed[:3], sort_keys=True))
    controls = _materialize_controls(out)
    corpus = _corpus_screen(out)
    screen = {
        "schema_version": "coordinates-cross-field-family-screen-v1",
        "status": "pass",
        "normalizer": NORMALIZER,
        "root_count": 100,
        "minimum_roots": MIN_ROOTS,
        "maximum_roots": MAX_ROOTS,
        "dimensions": list(HARD_RULE_DIMENSIONS),
        "pair_count": len(pairs),
        "expected_pair_count": expected_pairs,
        "all_pairs_compared": True,
        "decision_rule": "every unordered pair differs in every one of seven artifact-derived dimensions",
        "pairs": pairs,
        "adversarial_clone_controls": controls,
        "corpus_screen": corpus,
        "prompt_boundary": {"status": "pass", "records": prompt_records},
    }
    _write(out / ".state/family-screen.json", _json_bytes(screen))
    roots_receipt = {}
    for case, root in zip(CASES, roots, strict=True):
        hashes = _file_hashes(root)
        roots_receipt[root.name] = {
            "tree_hash": _tree_hash(root),
            "prompt_hash": prompt_records[root.name]["prompt_hash"],
            "starter_hashes": {path: digest for path, digest in hashes.items() if path in {f"{root.name}.h", f"{root.name}.cpp"}},
            "reference_hashes": {path: digest for path, digest in hashes.items() if path.startswith(".meta/example")},
            "test_hashes": {path: digest for path, digest in hashes.items() if "test" in path},
            "metadata_hashes": {path: digest for path, digest in hashes.items() if path.startswith(".meta/") and "example" not in path and "test" not in path and "negative" not in path},
            "negative_fixture_hash": hashes[".meta/negative_fixture.cpp"],
            "wrong_success_fixture_hash": hashes[".meta/wrong_success_fixture.cpp"],
            "predicate_kinds": [rule.kind for rule in case.rules],
            "primary_core_objective": "achieved",
            "lineage": "new_root",
            "candidate_state": "implemented",
        }
    preflight = {
        "schema_version": "coordinates-cross-field-creator-preflight-v1",
        "status": "pending_execution",
        "family_id": FAMILY_ID,
        "owner": OWNER,
        "owner_hash": _owner_hash(),
        "curriculum_hash": _sha256(CURRICULUM.read_bytes()),
        "count_plan_hash": _sha256(COUNT_PLAN.read_bytes()),
        "case_inventory_hash": _sha256(
            Path(__file__).with_name("moonlight_coordinates_cross_field_cases.py").read_bytes()
        ),
        "tree_hash": _tree_hash(out),
        "candidate_manifest_hash": _sha256(manifest_path.read_bytes()),
        "source_inventory_hash": _sha256((out / ".state/source-inventory.json").read_bytes()),
        "comparison_manifest_hash": _sha256((out / ".state/comparison-manifest.json").read_bytes()),
        "family_screen_hash": _sha256((out / ".state/family-screen.json").read_bytes()),
        "root_count": 100,
        "pair_count": expected_pairs,
        "prompt_boundary": "pass",
        "duplicate_family": "pass",
        "benchmark_and_existing_tree_screen": "pass",
        "adversarial_clone_controls": "structurally coherent; Docker execution pending",
        "normal_sanitizer": "pending_execution",
        "roots": roots_receipt,
        "strongest_status": "implemented",
        "release_status": "not_requested",
    }
    _write(out / ".state/creator-preflight.json", _json_bytes(preflight))
    return screen


def _validate_frozen_pre_docker_subject(out: Path) -> None:
    state = out / ".state"
    required = (
        "candidate-manifest.json",
        "source-inventory.json",
        "comparison-manifest.json",
        "family-screen.json",
        "creator-preflight.json",
    )
    if any(not (state / name).exists() for name in required):
        _fail("creator_preflight_missing", "run --verify-core before --docker-sanity")
    preflight = json.loads((state / "creator-preflight.json").read_text(encoding="utf-8"))
    bindings = {
        "owner_hash": _owner_hash(),
        "tree_hash": _tree_hash(out),
        "candidate_manifest_hash": _sha256((state / "candidate-manifest.json").read_bytes()),
        "source_inventory_hash": _sha256((state / "source-inventory.json").read_bytes()),
        "comparison_manifest_hash": _sha256((state / "comparison-manifest.json").read_bytes()),
        "family_screen_hash": _sha256((state / "family-screen.json").read_bytes()),
    }
    stale = [key for key, value in bindings.items() if preflight.get(key) != value]
    if stale:
        _fail("frozen_pre_docker_subject_drift", ", ".join(stale))
    comparison = json.loads((state / "comparison-manifest.json").read_text(encoding="utf-8"))
    snapshot_root = state / "comparison-snapshot"
    if comparison.get("snapshot_root_hash") != _tree_hash(snapshot_root):
        _fail("comparison_snapshot_drift", "aggregate tree hash")
    for root, row in comparison.get("snapshot_records", {}).items():
        blob = out / row["blob"]
        if not blob.exists():
            _fail("comparison_snapshot_missing", root)
        blob_bytes = blob.read_bytes()
        features = _ngrams(_semantic_tokens(_snapshot_blob(blob_bytes)), 4)
        if (
            _sha256(blob_bytes) != row["blob_hash"]
            or _sha256(_json_bytes(sorted(features))) != row["semantic_feature_hash"]
        ):
            _fail("comparison_snapshot_drift", root)


def _host_work_label(out: Path, root: Path) -> str:
    # Control roots re-render a candidate under .state/adversarial-controls, so
    # the basename alone collides with the candidate's work directory.  Mirror
    # the Docker script and derive the label from the full relative path.
    return root.relative_to(out).as_posix().replace("/", "_")


def _verify_host_root(root: Path, build_parent: Path, *, label: str, sanitize: bool) -> dict[str, object]:
    work = build_parent / (label + ("-san" if sanitize else "-normal"))
    shutil.copytree(root, work)
    config = json.loads((work / ".meta/config.json").read_text(encoding="utf-8"))
    for target, example in zip(config["files"]["solution"], config["files"]["example"], strict=True):
        shutil.copyfile(work / example, work / target)
    build = work / "build"
    command = ["cmake", "-S", str(work), "-B", str(build), "-G", "Unix Makefiles"]
    if sanitize:
        command.append("-DW8_SANITIZE=ON")
    subprocess.run(command, check=True, capture_output=True, text=True)
    subprocess.run(["cmake", "--build", str(build), "--parallel", "2"], check=True, capture_output=True, text=True)
    listed = subprocess.run(["ctest", "--test-dir", str(build), "-N"], check=True, capture_output=True, text=True)
    count = len(re.findall(r"Test\s+#\d+:", listed.stdout))
    if count != 4:
        _fail("test_discovery_failed", f"{root.name}: {count}")
    subprocess.run(["ctest", "--test-dir", str(build), "--output-on-failure"], check=True, capture_output=True, text=True)
    negative = subprocess.run([str(build / "topic_negative")], capture_output=True, text=True)
    if negative.returncode == 0:
        _fail("negative_fixture_not_rejected", root.name)
    wrong_success = subprocess.run([str(build / "success_negative")], capture_output=True, text=True)
    if wrong_success.returncode == 0:
        _fail("wrong_success_fixture_not_rejected", root.name)
    return {
        "test_count": count,
        "negative_returncode": negative.returncode,
        "wrong_success_returncode": wrong_success.returncode,
    }


def verify_host(out: Path) -> dict[str, object]:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        _fail("host_prerequisite_missing", "cmake and c++ are required for --verify-host")
    roots = [_task_root(out, case) for case in CASES]
    controls = [out / row["root"] for row in json.loads((out / ".state/family-screen.json").read_text())["adversarial_clone_controls"].values()]
    all_roots = (*roots, *controls)
    labels = [_host_work_label(out, root) for root in all_roots]
    if len(set(labels)) != len(labels):
        _fail("host_work_label_collision", "work labels must be unique across roots and controls")
    records = {}
    with tempfile.TemporaryDirectory(prefix="coordinates-cross-field-host-") as tmp:
        build_parent = Path(tmp)
        for root, label in zip(all_roots, labels, strict=True):
            normal = _verify_host_root(root, build_parent, label=label, sanitize=False)
            sanitizer = _verify_host_root(root, build_parent, label=label, sanitize=True)
            if normal["test_count"] != sanitizer["test_count"]:
                _fail("sanitizer_test_count_mismatch", root.name)
            records[root.relative_to(out).as_posix()] = {"normal": normal, "sanitizer": sanitizer}
    receipt = {"schema_version": "coordinates-cross-field-host-verification-v1", "status": "pass", "records": records, "evidence_class": "host_iteration_only"}
    _write(out / ".state/host-verification.json", _json_bytes(receipt))
    return receipt


def _docker_script(relative_roots: Sequence[str]) -> str:
    quoted_roots = " ".join(json.dumps(path) for path in relative_roots)
    return f"""set -euo pipefail
trap 'status=$?; test -f /tmp/configure.log && cat /tmp/configure.log; test -f /tmp/build.log && cat /tmp/build.log; exit $status' ERR
echo \"TOOLCHAIN_BEGIN\"
compiler_path=$(command -v c++)
echo \"COMPILER_PATH|$compiler_path\"
echo \"COMPILER_SHA256|$(sha256sum \"$compiler_path\" | cut -d' ' -f1)\"
echo \"COMPILER_VERSION_B64|$(c++ --version | base64 -w0)\"
echo \"CMAKE_VERSION_B64|$(cmake --version | base64 -w0)\"
echo \"TOOLCHAIN_END\"
for relative in {quoted_roots}; do
  source_root=\"/input/$relative\"
  work=\"/tmp/work-${{relative//\\//_}}\"
  cp -a \"$source_root\" \"$work\"
  task_id=$(basename \"$source_root\")
  cp \"$work/.meta/example.h\" \"$work/$task_id.h\"
  cp \"$work/.meta/example.cpp\" \"$work/$task_id.cpp\"
  for mode in normal sanitizer; do
    build=\"$work/build-$mode\"
    args=(-S \"$work\" -B \"$build\" -G \"Unix Makefiles\")
    if [ \"$mode\" = sanitizer ]; then args+=(-DW8_SANITIZE=ON); fi
    cmake \"${{args[@]}}\" >/tmp/configure.log 2>&1
    cmake --build \"$build\" --parallel 2 >/tmp/build.log 2>&1
    count=$(ctest --test-dir \"$build\" -N | sed -n 's/^  Test #[0-9][0-9]*: /x/p' | wc -l)
    test \"$count\" -eq 4
    ctest --test-dir \"$build\" --output-on-failure
    if \"$build/topic_negative\"; then exit 91; fi
    if \"$build/success_negative\"; then exit 92; fi
    echo \"RESULT|$relative|$mode|$count\"
  done
done
"""


def docker_sanity(out: Path, image: str = SANITY_IMAGE) -> dict[str, object]:
    if image != SANITY_IMAGE:
        _fail("image_identity_mismatch", image)
    screen_path = out / ".state/family-screen.json"
    if not screen_path.exists():
        _fail("creator_preflight_missing", "run --verify-core first")
    screen = json.loads(screen_path.read_text(encoding="utf-8"))
    relative_roots = [case.domain.task_id for case in CASES]
    relative_roots.extend(row["root"] for row in screen["adversarial_clone_controls"].values())
    inspect = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        check=True, capture_output=True, text=True,
    )
    command = [
        "docker", "run", "--rm", "--network", "none",
        "-v", f"{out.resolve()}:/input:ro", image, "bash", "-lc",
        _docker_script(relative_roots),
    ]
    completed = subprocess.run(command, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        failure = {
            "schema_version": "coordinates-cross-field-docker-failure-v1",
            "status": "failed",
            "returncode": completed.returncode,
            "image": image,
            "network_policy": "none",
            "owner_hash": _owner_hash(),
            "tree_hash": _tree_hash(out),
            "stdout_tail": completed.stdout[-12000:],
            "stderr_tail": completed.stderr[-12000:],
            "failed_at": _utc_now(),
        }
        failure_bytes = _json_bytes(failure)
        _write(out / ".state/docker-failure.json", failure_bytes)
        failure_id = f"{failure['failed_at'].replace(':', '').replace('+', '_')}-{_sha256(failure_bytes)[:12]}"
        _write(out / f".state/docker-failures/{failure_id}.json", failure_bytes)
        detail = (completed.stderr or completed.stdout)[-2000:].strip()
        _fail("docker_sanity_failed", detail)
    records: dict[str, dict[str, object]] = {}
    for relative, mode, count in re.findall(r"^RESULT\|([^|]+)\|([^|]+)\|(\d+)$", completed.stdout, flags=re.MULTILINE):
        records.setdefault(relative, {})[mode] = {
            "test_count": int(count),
            "topic_negative_rejected": True,
            "wrong_success_rejected": True,
        }
    if set(records) != set(relative_roots):
        _fail("docker_result_incomplete", f"{len(records)} of {len(relative_roots)} roots")
    for relative, modes in records.items():
        if set(modes) != {"normal", "sanitizer"} or modes["normal"]["test_count"] != modes["sanitizer"]["test_count"] or modes["normal"]["test_count"] <= 0:
            _fail("sanitizer_test_count_mismatch", relative)
    toolchain_match = re.search(r"TOOLCHAIN_BEGIN\n(.*?)\nTOOLCHAIN_END", completed.stdout, re.DOTALL)
    if not toolchain_match:
        _fail("toolchain_identity_missing", "Docker output did not report compiler/CMake")
    toolchain_fields = dict(
        line.split("|", 1)
        for line in toolchain_match.group(1).splitlines()
        if "|" in line
    )
    required_toolchain = {
        "COMPILER_PATH", "COMPILER_SHA256", "COMPILER_VERSION_B64", "CMAKE_VERSION_B64"
    }
    if set(toolchain_fields) != required_toolchain:
        _fail("toolchain_identity_missing", json.dumps(toolchain_fields, sort_keys=True))
    for row in screen["adversarial_clone_controls"].values():
        row["coherent_build_pending"] = False
        row["normal_and_sanitizer_build"] = "pass"
        row["topic_negative_rejected"] = True
        row["wrong_success_rejected"] = True
    screen["docker_execution"] = {
        "status": "pass",
        "image": image,
        "image_id": inspect.stdout.strip(),
        "normal_test_count": sum(row["normal"]["test_count"] for row in records.values()),
        "sanitizer_test_count": sum(row["sanitizer"]["test_count"] for row in records.values()),
    }
    _write(screen_path, _json_bytes(screen))
    manifest_path = out / ".state/candidate-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for row in manifest["roots"].values():
        row["candidate_state"] = "verified"
    manifest["creator_preflight"] = "pass"
    manifest["strongest_status"] = "creator_preflight_passed_pending_independent_audit"
    _write(manifest_path, _json_bytes(manifest))
    source_inventory_path = out / ".state/source-inventory.json"
    comparison_manifest_path = out / ".state/comparison-manifest.json"
    receipt = {
        "schema_version": "coordinates-cross-field-docker-sanity-v1",
        "status": "pass",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "image": image,
        "image_id": inspect.stdout.strip(),
        "compiler_path": toolchain_fields["COMPILER_PATH"],
        "compiler_sha256": toolchain_fields["COMPILER_SHA256"],
        "compiler_version": base64.b64decode(toolchain_fields["COMPILER_VERSION_B64"]).decode(),
        "cmake_version": base64.b64decode(toolchain_fields["CMAKE_VERSION_B64"]).decode(),
        "network_policy": "none",
        "commands": {
            "docker": command,
            "normal_configure": ["cmake", "-S", "<task-work>", "-B", "<normal-build>", "-G", "Unix Makefiles"],
            "sanitizer_configure": ["cmake", "-S", "<task-work>", "-B", "<sanitizer-build>", "-G", "Unix Makefiles", "-DW8_SANITIZE=ON"],
            "build": ["cmake", "--build", "<mode-build>", "--parallel", "2"],
            "discover": ["ctest", "--test-dir", "<mode-build>", "-N"],
            "test": ["ctest", "--test-dir", "<mode-build>", "--output-on-failure"],
            "topic_negative": ["<mode-build>/topic_negative"],
            "wrong_success": ["<mode-build>/success_negative"],
        },
        "owner": OWNER,
        "owner_hash": _owner_hash(),
        "tree_hash": _tree_hash(out),
        "family_screen_hash": _sha256(screen_path.read_bytes()),
        "candidate_manifest_hash": _sha256(manifest_path.read_bytes()),
        "source_inventory_hash": _sha256(source_inventory_path.read_bytes()),
        "comparison_manifest_hash": _sha256(comparison_manifest_path.read_bytes()),
        "root_count": 100,
        "control_count": 3,
        "records": records,
        "normal_test_count": sum(row["normal"]["test_count"] for row in records.values()),
        "sanitizer_test_count": sum(row["sanitizer"]["test_count"] for row in records.values()),
        "topic_negative_rejections": len(records),
        "wrong_success_rejections": len(records),
        "completed_at": _utc_now(),
    }
    _write(out / ".state/docker-sanity.json", _json_bytes(receipt))
    preflight_path = out / ".state/creator-preflight.json"
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    preflight.update(
        {
            "status": "pass",
            "tree_hash": _tree_hash(out),
            "family_screen_hash": _sha256(screen_path.read_bytes()),
            "candidate_manifest_hash": _sha256(manifest_path.read_bytes()),
            "source_inventory_hash": _sha256(source_inventory_path.read_bytes()),
            "comparison_manifest_hash": _sha256(comparison_manifest_path.read_bytes()),
            "docker_sanity_hash": _sha256((out / ".state/docker-sanity.json").read_bytes()),
            "normal_sanitizer": "pass",
            "adversarial_clone_controls": "pass: changed, coherent, built, tested, and rejected",
            "strongest_status": "creator_preflight_passed_pending_independent_audit",
        }
    )
    for row in preflight["roots"].values():
        row["candidate_state"] = "verified"
        row["normal_test_count"] = 4
        row["sanitizer_test_count"] = 4
        row["topic_negative_rejected"] = True
        row["wrong_success_rejected"] = True
    _write(preflight_path, _json_bytes(preflight))
    audit_subject = {
        "schema_version": "coordinates-cross-field-audit-subject-v1",
        "family_id": FAMILY_ID,
        "owner_hash": _owner_hash(),
        "tree_hash": _tree_hash(out),
        "candidate_manifest_hash": _sha256(manifest_path.read_bytes()),
        "source_inventory_hash": _sha256(source_inventory_path.read_bytes()),
        "comparison_manifest_hash": _sha256(comparison_manifest_path.read_bytes()),
        "family_screen_hash": _sha256(screen_path.read_bytes()),
        "docker_sanity_hash": _sha256((out / ".state/docker-sanity.json").read_bytes()),
        "creator_preflight_hash": _sha256(preflight_path.read_bytes()),
        "curriculum_hash": _sha256(CURRICULUM.read_bytes()),
        "focused_test_hash": _sha256(Path("tests/test_moonlight_coordinates_cross_field_aider_tasks.py").read_bytes()),
    }
    _write(out / ".state/audit-subject.json", _json_bytes(audit_subject))
    return receipt


def append_cycle(
    out: Path,
    *,
    cycle: int,
    state: str,
    audit_subject_hash: str | None = None,
    audit_report: str | None = None,
    finding_ids: Sequence[str] = (),
    terminal_status: str | None = None,
) -> dict[str, object]:
    state_root = out / ".state"
    cycle_root = state_root / "cycles"
    cycle_root.mkdir(parents=True, exist_ok=True)
    path = cycle_root / f"cycle-{cycle:02d}.json"
    if path.exists():
        _fail("cycle_record_exists", path.as_posix())
    receipt = json.loads((state_root / "docker-sanity.json").read_text(encoding="utf-8")) if (state_root / "docker-sanity.json").exists() else None
    record = {
        "schema_version": "aider-task-creator-cycle-v1",
        "cycle": cycle,
        "timestamp": _utc_now(),
        "state": state,
        "family_id": FAMILY_ID,
        "candidate_manifest_hash": _sha256((state_root / "candidate-manifest.json").read_bytes()),
        "source_inventory_hash": _sha256((state_root / "source-inventory.json").read_bytes()),
        "comparison_manifest_hash": _sha256((state_root / "comparison-manifest.json").read_bytes()),
        "audit_subject_manifest_hash": _sha256((state_root / "audit-subject.json").read_bytes()) if (state_root / "audit-subject.json").exists() else None,
        "curriculum_hash": _sha256(CURRICULUM.read_bytes()),
        "generator_hash": _owner_hash(),
        "focused_test_hash": _sha256(Path("tests/test_moonlight_coordinates_cross_field_aider_tasks.py").read_bytes()),
        "generated_tree_hash": _tree_hash(out),
        "grader_policy_hash": _sha256((SANITY_IMAGE + NORMALIZER + "network:none").encode()),
        "family_screen_hash": _sha256((state_root / "family-screen.json").read_bytes()),
        "creator_preflight_hash": _sha256((state_root / "creator-preflight.json").read_bytes()),
        "docker_receipt_hash": _sha256((state_root / "docker-sanity.json").read_bytes()) if receipt else None,
        "audit_subject_hash": audit_subject_hash,
        "audit_report": audit_report,
        "finding_ids": list(finding_ids),
        "retained_task_ids": [case.domain.task_id for case in CASES],
        "replaced_task_ids": [],
        "rejected_task_ids": [],
        "review_task_ids": [],
        "prior_evidence_invalidated": [],
        "terminal_status": terminal_status,
        "blockers": [],
    }
    _write(path, _json_bytes(record))
    return record


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    parser.add_argument("--cycle", type=int)
    parser.add_argument("--cycle-state", choices=("creator_preflight", "auditing", "remediating", "re_auditing", "local_family_verified", "not_completed"))
    parser.add_argument("--audit-subject-hash")
    parser.add_argument("--audit-report")
    parser.add_argument("--finding-id", action="append", default=[])
    parser.add_argument("--terminal-status")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.force or not args.out.exists() or not (args.out / ".state/candidate-manifest.json").exists():
        materialize(args.out, force=args.force)
    if args.verify_core or args.verify_host:
        verify_core(args.out)
    elif args.docker_sanity:
        _validate_frozen_pre_docker_subject(args.out)
    if args.verify_host:
        verify_host(args.out)
    if args.docker_sanity:
        docker_sanity(args.out, args.image)
    if args.cycle is not None:
        if args.cycle_state is None:
            _fail("cycle_state_missing", "--cycle-state is required with --cycle")
        append_cycle(
            args.out,
            cycle=args.cycle,
            state=args.cycle_state,
            audit_subject_hash=args.audit_subject_hash,
            audit_report=args.audit_report,
            finding_ids=args.finding_id,
            terminal_status=args.terminal_status,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
