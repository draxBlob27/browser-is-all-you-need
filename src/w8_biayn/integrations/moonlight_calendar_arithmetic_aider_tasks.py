"""Materialize the newly authored general-calendar-arithmetic local Aider curriculum.

These roots are deliberately local diagnostic artifacts. They model distinct
Gregorian policy algorithms; they are not variations of the
Polyglot ``clock`` holdout and are not admitted SFT data.
"""
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
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/aider-dates-and-clocks/general-calendar-arithmetic"
)
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dates-and-clocks/general-calendar-arithmetic")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_GENERAL_CALENDAR_ARITHMETIC_CURRICULUM.md"
FAMILY_SPEC = "docs/aider-tasks-spec/aider-dates-and-clocks/general-calendar-arithmetic.md"
PROMPT_PATH = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
CASES_PATH = "src/w8_biayn/integrations/moonlight_calendar_arithmetic_cases.py"
FAMILY_ID_BEFORE = "aider-dates-and-clocks-general-calendar-arithmetic-v1-template"
FAMILY_ID = "aider-dates-and-clocks-general-calendar-arithmetic-v2-hard-rule"
LEGACY_GENERATOR_REVISION = (
    "sha256:6a456e81c10f204210d6f3d23c365dfe8313f8faa0990ef5641ad66f213c2e1a"
)
MANIFEST_SCHEMA = "aider-general-calendar-arithmetic-materialization-v2"
SEMANTIC_NORMALIZER = "general-calendar-arithmetic-v2-role-aware-7gram"
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
HARD_RULE_LIMITS = {
    "public_api": 0.97,
    "owned_state_algorithm": 0.94,
    "mutation_selection_rules": 0.94,
    "invalid_boundary_behavior": 0.94,
    "reference_control_flow": 0.94,
    "deterministic_oracle": 0.94,
    "topic_specific_negative_fixture": 0.94,
}
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


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    summary: str
    header: str
    reference: str
    starter: str
    visible: str
    hidden: str
    hard_rule: str
    contract: str


CALENDAR_SUPPORT = r'''
namespace {
[[maybe_unused]] bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}
[[maybe_unused]] int dim(int y,int m){static const int d[]={0,31,28,31,30,31,30,31,31,30,31,30,31};return m==2&&leap(y)?29:d[m];}
[[maybe_unused]] bool valid(CivilDate d){return d.year>=1&&d.year<=9999&&d.month>=1&&d.month<=12&&d.day>=1&&d.day<=dim(d.year,d.month);}
[[maybe_unused]] long long ord(CivilDate d){int y=d.year;unsigned m=static_cast<unsigned>(d.month),day=static_cast<unsigned>(d.day);y-=m<=2;int era=(y>=0?y:y-399)/400;unsigned yoe=static_cast<unsigned>(y-era*400);unsigned doy=(153U*(m+(m>2?static_cast<unsigned>(-3):9U))+2U)/5U+day-1U;unsigned doe=yoe*365U+yoe/4U-yoe/100U+doy;return static_cast<long long>(era)*146097LL+doe;}
[[maybe_unused]] CivilDate civil(long long z){long long era=(z>=0?z:z-146096)/146097;unsigned doe=static_cast<unsigned>(z-era*146097);unsigned yoe=(doe-doe/1460U+doe/36524U-doe/146096U)/365U;int y=static_cast<int>(yoe)+static_cast<int>(era)*400;unsigned doy=doe-(365U*yoe+yoe/4U-yoe/100U);unsigned mp=(5U*doy+2U)/153U;unsigned day=doy-(153U*mp+2U)/5U+1U;unsigned month=mp+(mp<10U?3U:static_cast<unsigned>(-9));y+=month<=2U;CivilDate d{y,static_cast<int>(month),static_cast<int>(day)};return valid(d)?d:CivilDate{};}
[[maybe_unused]] int cmp(CivilDate a,CivilDate b){long long x=ord(a),y=ord(b);return x==y?0:(x<y?-1:1);}
[[maybe_unused]] CivilDate add_days(CivilDate d,long long n){return valid(d)?civil(ord(d)+n):CivilDate{};}
[[maybe_unused]] CivilDate add_months(CivilDate d,long long n,int anchor){if(!valid(d))return{};long long z=static_cast<long long>(d.year-1)*12+d.month-1+n;if(z<0||z>=9999LL*12)return{};int y=static_cast<int>(z/12)+1,m=static_cast<int>(z%12)+1;return{y,m,std::min(anchor,dim(y,m))};}
}
'''


def _task(task_id: str, class_name: str, summary: str, header: str, body: str, checks: str, hidden: str, hard_rule: str, contract: str) -> TaskSpec:
    prefix = '#include "task.h"\n#include <algorithm>\n#include <limits>\n#include <map>\n#include <set>\n#include <stdexcept>\n#include <tuple>\nnamespace curriculum {\n' + CALENDAR_SUPPORT
    suffix = '}  // namespace curriculum\n'
    starter = '#include "task.h"\nnamespace curriculum {\n// TODO: implement every public method declared in task.h.\n' + suffix
    test_prefix = "#include \"task.h\"\n#include <map>\n#include <stdexcept>\n"
    return TaskSpec(task_id, class_name, summary, header, prefix + body.replace("/*REFERENCE*/", "") + suffix, starter, test_prefix + checks.replace("\\n", "\n"), test_prefix + hidden.replace("\\n", "\n"), test_prefix + hard_rule.replace("\\n", "\n"), contract)


# V1 artifacts remain immutable audit inputs; v2 definitions live in the case table.
from w8_biayn.integrations.moonlight_calendar_arithmetic_cases import (
    CASES as CALENDAR_CASES,
    NEGATIVE_MUTATIONS as CALENDAR_NEGATIVE_MUTATIONS,
    PROFILES as CALENDAR_PROFILES,
)

TASKS = tuple(_task(*case) for case in CALENDAR_CASES)
PROFILES = CALENDAR_PROFILES
NEGATIVE_MUTATIONS = CALENDAR_NEGATIVE_MUTATIONS


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
    for path in sorted(p for p in root.rglob("*") if p.is_file() and ".state" not in p.parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _negative_source(spec: TaskSpec) -> tuple[str, str]:
    old, new, reason = NEGATIVE_MUTATIONS[spec.task_id]
    if spec.reference.count(old) != 1:
        _fail("invariant_not_enforced", f"topic-negative mutation drift: {spec.task_id}")
    candidate = spec.reference.replace(old, new, 1)
    if candidate == spec.reference:
        _fail("invariant_not_enforced", f"unchanged topic negative: {spec.task_id}")
    return candidate, reason


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(general_calendar_arithmetic_curriculum LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
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
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_test(NAME hard_rule COMMAND task_hard_rule)
'''


def _remedy_markdown(spec: TaskSpec) -> str:
    profile, marker = PROFILES[spec.task_id]
    _, _, negative_reason = NEGATIVE_MUTATIONS[spec.task_id]
    return f"""## Identity

Task ID: `{spec.task_id}`; task-spec revision: 2; family ID: `{FAMILY_ID}/{spec.task_id}`; disposition: `repair-in-place`; source inventory: `general-calendar-arithmetic-legacy-v1`; license result: repository-authored/pass; generator: `src/w8_biayn/integrations/moonlight_calendar_arithmetic_aider_tasks.py`; benchmark screen: pending. Selected prompt: `{PROMPT_PATH}` with user input `FAMILY_NAME=general-calendar-arithmetic`, `FAMILY_TYPE=aider-dates-and-clocks`; repository evidence resolves the actual immutable owner category to `aider-dates-and-clocks` because the supplied legacy grid root does not exist.

## Objective

{spec.summary}

## Public API

C++17 namespace `curriculum`; editable order is `{spec.task_id}.h`, then `{spec.task_id}.cpp`. The complete declarations are the task-specific `{spec.class_name}` header. Values are caller-owned; the object owns only the private state declared in that header.

## Behavior table

{spec.contract} Valid operations return the documented task-specific record or boolean and mutate atomically. Invalid input returns the documented false/empty/unchanged result. Duplicate, absent, empty, equality, saturation, stable-order, and terminal-state behavior are exercised by the visible and private tests; arithmetic is checked before state mutation.

## Implementation invariant

Required mechanism: {profile}. Required emitted marker: `{marker}`. Forbidden substitutes are a generic start/tick/remaining timer, a renamed copy of another root, host-clock or thread delegation, precomputed event answers, benchmark assets, and a shared policy-switch timer template.

## Starter and reference

The task-named header exposes the complete API; the task-named source remains coherent and incomplete. `.meta/example.cpp` independently owns the required state and transitions. It imports neither legacy generated files nor hidden fixtures.

## Tests

The visible executable covers the normal contract. The private executable covers invalid input, equality boundaries, repeated transitions, stable ordering, and no-partial-mutation behavior. The deterministic topic-negative models “{negative_reason}”; it must compile under the reference flags and be rejected by executed tests. Coherent domain/identifier-renamed, constants/policy-only, and opposite-end-selection controls must compile and pass behavior tests but fail the exact production seven-dimension evaluator.

## Files and metadata

Solutions: `{spec.task_id}.h`, `{spec.task_id}.cpp`. Test: `task_visible_test.cpp`; private test: `.meta/task_hidden_test.cpp`. References: `.meta/example.h`, `.meta/example.cpp`, mapped by suffix and solution order. Docs, tests, metadata, references, CMake, controls, manifests, and receipts remain private.

## Build/oracle

C++17, strict warnings, explicit `Unix Makefiles`, locked `c++`, and three CTest targets. Run clean normal and separate fresh ASan/UBSan builds in `{SANITY_IMAGE}` with Docker network `none`. Expected discovery is three tests in each mode for every root and coherent control. The receipt binds archive, owner, case table, tree, reference, negative, image, compiler, CMake, command, and count identities.

## Family/contamination

Compare all 45 unordered pairs separately across {", ".join(HARD_RULE_DIMENSIONS)} using `{SEMANTIC_NORMALIZER}`. Enforce the user-authorized 8–12 count, actual count 10, and screen all 26 permanent official C++ holdouts. No semantic or count waiver is allowed.

## Optional dataset handoff

`not_requested`. No JSONL, token/mask evidence, split, export, training, release, or benchmark-uplift claim is authorized.

## Acceptance

Run focused pytest, owner `--verify-core`, and owner `--docker-sanity`. Require exact regeneration, prompt/role/reference safety, 10 roots, 45 all-pairs decisions across the exact seven dimensions, three changed/coherent/passing clone controls rejected by the production evaluator, ten compiled and executed topic-negative rejections, 260 holdout comparisons, and equal positive normal/sanitizer counts. Stable failures include `remedy_spec_incomplete`, `prompt_contract_incomplete`, `invariant_not_enforced`, `duplicate_family`, `negative_fixture_not_rejected`, `benchmark_content_overlap`, `generator_output_drift`, `grader_mount_hash_mismatch`, and `sanitizer_test_count_mismatch`.
"""


def _write_remedies(out: Path, force: bool) -> None:
    remedy_root = out / ".state/remedy"
    expected_existing = [
        remedy_root / f"{spec.task_id}{suffix}"
        for spec in TASKS
        for suffix in (".md", ".json")
    ]
    if all(path.is_file() for path in expected_existing):
        for spec in TASKS:
            markdown_path = remedy_root / f"{spec.task_id}.md"
            record = json.loads((remedy_root / f"{spec.task_id}.json").read_text())
            if (
                record.get("disposition") != "repair-in-place"
                or record.get("tree_hash_before") != _tree_hash(LEGACY_ROOT / spec.task_id)
                or record.get("remedy_spec_hash")
                != _sha_bytes(markdown_path.read_bytes())
            ):
                _fail("remedy_spec_incomplete", spec.task_id)
        return
    for spec in TASKS:
        markdown = _remedy_markdown(spec)
        markdown_path = remedy_root / f"{spec.task_id}.md"
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": spec.task_id,
            "family_id_before": f"{FAMILY_ID_BEFORE}/{spec.task_id}",
            "tree_hash_before": _tree_hash(LEGACY_ROOT / spec.task_id),
            "generator_path": "src/w8_biayn/integrations/moonlight_calendar_arithmetic_aider_tasks.py",
            "generator_revision": LEGACY_GENERATOR_REVISION,
            "finding_ids": [
                "CT-F1-missing-hard-rule-proof",
                "CT-F2-missing-executed-negatives",
                "CT-F3-missing-docker-receipt",
                "CT-F4-shared-calendar-template",
            ],
            "disposition": "repair-in-place",
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": str(markdown_path),
            "remedy_spec_hash": _sha_bytes(markdown.encode()),
            "selected_prompt": PROMPT_PATH,
            "user_inputs": {
                "FAMILY_NAME": "general-calendar-arithmetic",
                "FAMILY_TYPE": "aider-dates-and-clocks",
                "hard_rule_count": "8-12",
            },
            "resolved_family_type": "aider-dates-and-clocks",
            "status": "planned",
        }
        _write(markdown_path, markdown, force)
        _write(
            remedy_root / f"{spec.task_id}.json",
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            force,
        )


def _invalidate_generated_evidence(out: Path) -> dict[str, object] | None:
    if not out.exists():
        return None
    invalidated: dict[str, object] = {
        "reason": "owner or emitted-artifact change invalidates all prior hard-rule and runtime evidence",
        "prior_manifest_hash": "not_available",
        "prior_oracle_receipt_hash": "not_available",
    }
    for name, key in (
        ("materialization-manifest.json", "prior_manifest_hash"),
        ("oracle-receipt.json", "prior_oracle_receipt_hash"),
    ):
        path = out / ".state" / name
        if path.is_file():
            invalidated[key] = _source_hash(path)
    for spec in TASKS:
        root = out / spec.task_id
        if not root.exists():
            continue
        provenance_path = root / ".meta/provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        if provenance.get("family_id") != FAMILY_ID:
            _fail("generator_output_drift", f"refuse foreign root: {root}")
        shutil.rmtree(root)
    state = out / ".state"
    if state.exists():
        for child in state.iterdir():
            if child.name == "remedy":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    remedy_root = state / "remedy"
    for spec in TASKS:
        record_path = remedy_root / f"{spec.task_id}.json"
        if not record_path.is_file():
            continue
        record = json.loads(record_path.read_text(encoding="utf-8"))
        for key in (
            "benchmark_screen",
            "changed_owner_paths",
            "family_screen",
            "hard_rule_status",
            "oracle_evidence",
            "primary_core_objective",
            "prompt_boundary",
            "reference_mapping",
            "semantic_holdout_screen",
            "strongest_local_status",
            "tree_hash_after",
        ):
            record.pop(key, None)
        record["benchmark_screen"] = "pending"
        record["status"] = "planned"
        _write(record_path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)
    return invalidated


def _control_files(out: Path, name: str) -> dict[str, str]:
    base_id = "calendar-subscription-cycle"
    base = out / base_id
    files = {
        path.relative_to(base).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(base.rglob("*"))
        if path.is_file()
    }
    if name == "domain-identifier-renamed-clone":
        replacements = (
            ("SubscriptionCycle", "MembershipCycle"),
            ("Subscriber", "Member"),
            ("subscriber", "member"),
            ("Subscription", "Membership"),
            ("subscription", "membership"),
        )
        for key, value in tuple(files.items()):
            for old, new in replacements:
                value = value.replace(old, new)
            files[key] = value
        files = {
            key.replace("calendar-subscription-cycle", "calendar-membership-cycle"): value
            for key, value in files.items()
        }
    elif name == "constants-policy-clone":
        visible = files["task_visible_test.cpp"]
        for old, new in (
            ('{"z",{2024,1,31},1}', '{"z",{2024,1,31},2}'),
            ('r.selected.id=="z"', 'r.selected.id=="a"'),
            ('CivilDate{2024,2,29}', 'CivilDate{2024,3,20}'),
        ):
            if old not in visible:
                _fail("invariant_not_enforced", f"constants control drift: {old}")
            visible = visible.replace(old, new, 1)
        files["task_visible_test.cpp"] = visible
        files[".docs/instructions.md"] += "\nThe public example uses a two-month cadence for subscriber z.\n"
    elif name == "opposite-end-selection-clone":
        reference = files[".meta/example.cpp"]
        old = "*std::min_element(out.projected.begin(),out.projected.end()"
        new = "*std::max_element(out.projected.begin(),out.projected.end()"
        if reference.count(old) != 1:
            _fail("invariant_not_enforced", "opposite-end control drift")
        files[".meta/example.cpp"] = reference.replace(old, new, 1)
        files["task_visible_test.cpp"] = files["task_visible_test.cpp"].replace(
            'r.selected.id=="z"', 'r.selected.id=="a"', 1
        ).replace("CivilDate{2024,2,29}", "CivilDate{2024,3,20}", 1)
        files[".docs/instructions.md"] = files[".docs/instructions.md"].replace(
            "earliest projected date", "latest projected date", 1
        )
    else:
        raise AssertionError(name)
    files["candidate.cpp"] = files[".meta/example.cpp"]
    return files


def _write_controls(out: Path, force: bool) -> None:
    for name in (
        "domain-identifier-renamed-clone",
        "constants-policy-clone",
        "opposite-end-selection-clone",
    ):
        root = out / ".state/hard-rule-controls" / name
        for relative, content in _control_files(out, name).items():
            _write(root / relative, content, force)


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() == LEGACY_ROOT.resolve() or LEGACY_ROOT.resolve() in out.resolve().parents:
        _fail("legacy_root_immutable", str(out))
    if not (MIN_ROOTS <= len(TASKS) <= MAX_ROOTS):
        _fail("hard_rule_count_mismatch", f"expected {MIN_ROOTS}-{MAX_ROOTS}, found {len(TASKS)}")
    invalidated = _invalidate_generated_evidence(out) if force else None
    _write_remedies(out, force)
    if invalidated is not None:
        _write(
            out / ".state/invalidated-evidence.json",
            json.dumps(invalidated, indent=2, sort_keys=True) + "\n",
            True,
        )
    roots = []
    for spec in TASKS:
        root = out / spec.task_id
        config = {"authors": ["w8-biayn"], "blurb": spec.summary, "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        profile, marker = PROFILES[spec.task_id]
        provenance = {"curriculum_document": CURRICULUM, "curriculum_hash": _source_hash(Path(CURRICULUM)), "family_spec": FAMILY_SPEC, "family_spec_hash": _source_hash(Path(FAMILY_SPEC)), "selected_prompt": PROMPT_PATH, "selected_prompt_hash": _source_hash(Path(PROMPT_PATH)), "case_table": CASES_PATH, "case_table_hash": _source_hash(Path(CASES_PATH)), "curriculum_task_id": spec.task_id, "family_id": FAMILY_ID, "family_type": "aider-dates-and-clocks", "requested_family_type": "aider-dates-and-clocks", "semantic_profile": profile, "mechanism_marker": marker, "disposition": "repair-in-place", "legacy_task_id": spec.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local candidate; pending mandatory verification", "version": 2, "benchmark_separation": "Domain calendar algorithm and public API are independently authored; this root is not derived from the permanent Aider Polyglot clock, gigasecond, or meetup holdouts."}
        negative, negative_reason = _negative_source(spec)
        files = {".docs/introduction.md": f"# {spec.class_name}\n\n{spec.summary}\n", ".docs/instructions.md": f"# Instructions\n\nImplement `{spec.class_name}`. {spec.contract}\n\nDates are caller-supplied proleptic Gregorian civil dates. Do not use system-time/date-library APIs, threads, randomness, files, or networking.\n", ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": f"[visible]\ndescription = \"domain API and primary calendar transition\"\n\n[hidden]\ndescription = \"invalid, empty, duplicate, equality, atomicity, and stable-order cases\"\n\n[hard_rule]\ndescription = \"independent leap-century or complete-state property oracle\"\n\n[topic_negative]\ndescription = {json.dumps(negative_reason)}\n", "task.h": spec.header, "task.cpp": spec.starter, ".meta/example.h": spec.header, ".meta/example.cpp": spec.reference, ".meta/negative_false_substitute.cpp": negative, "task_visible_test.cpp": spec.visible, ".meta/task_hidden_test.cpp": spec.hidden, ".meta/task_hard_rule_test.cpp": spec.hard_rule, "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items():
            _write(root / relative, content, force)
        roots.append(root)
    _write_controls(out, force)
    return tuple(roots)


def _safe_relative(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        _fail("unsafe_path", value)
    return value


def _normalized_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " literal ", text)
    raw = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|==|!=|<=|>=|&&|\|\||::|[-+*/%<>{}()[\],;:=.!]", text)
    kept = {
        "if", "else", "for", "while", "return", "class", "struct", "enum", "public", "private",
        "const", "bool", "int", "long", "void", "auto", "explicit", "static_cast", "std", "vector",
        "map", "string", "pair", "sort", "reverse", "min", "max", "find", "erase", "emplace",
        "push_back", "begin", "end", "size", "empty", "true", "false", "literal",
    }
    return tuple(token if token in kept or not token[0].isalpha() else "identifier" for token in raw)


def _ngrams(tokens: tuple[str, ...], width: int = 7) -> set[tuple[str, ...]]:
    if len(tokens) < width:
        return {tokens} if tokens else set()
    return {tokens[index : index + width] for index in range(len(tokens) - width + 1)}


def _containment(left: str, right: str) -> float:
    left_grams = _ngrams(_normalized_tokens(left))
    right_grams = _ngrams(_normalized_tokens(right))
    if not left_grams or not right_grams:
        return 1.0 if left_grams == right_grams else 0.0
    return max(
        len(left_grams & right_grams) / len(left_grams),
        len(left_grams & right_grams) / len(right_grams),
    )


def _artifact_dimensions(root: Path) -> dict[str, str]:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    solution = config["files"]["solution"]
    header = (root / solution[0]).read_text(encoding="utf-8")
    instructions = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((root / ".docs").glob("*.md"))
    )
    reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    hidden = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
    hard_rule = (root / ".meta/task_hard_rule_test.cpp").read_text(encoding="utf-8")
    negative = (root / ".meta/negative_false_substitute.cpp").read_text(encoding="utf-8")
    return {
        "public_api": header,
        "owned_state_algorithm": header + "\n" + reference,
        "mutation_selection_rules": instructions + "\n" + reference,
        "invalid_boundary_behavior": instructions + "\n" + hidden,
        "reference_control_flow": reference,
        "deterministic_oracle": visible + "\n" + hidden + "\n" + hard_rule,
        "topic_specific_negative_fixture": negative + "\n" + visible + "\n" + hidden + "\n" + hard_rule,
    }


def _compare_dimensions(left: Path, right: Path) -> dict[str, object]:
    left_dimensions = _artifact_dimensions(left)
    right_dimensions = _artifact_dimensions(right)
    decisions: dict[str, object] = {}
    for dimension in HARD_RULE_DIMENSIONS:
        score = _containment(left_dimensions[dimension], right_dimensions[dimension])
        decisions[dimension] = {
            "containment": round(score, 6),
            "limit": HARD_RULE_LIMITS[dimension],
            "distinct": score < HARD_RULE_LIMITS[dimension],
        }
    decisions["pass"] = all(
        bool(decisions[dimension]["distinct"]) for dimension in HARD_RULE_DIMENSIONS
    )
    return decisions


def _pair_matrix(out: Path) -> dict[str, object]:
    pairs: list[dict[str, object]] = []
    for left_index, left in enumerate(TASKS):
        for right in TASKS[left_index + 1 :]:
            decisions = _compare_dimensions(out / left.task_id, out / right.task_id)
            if not decisions["pass"]:
                _fail("duplicate_family", f"{left.task_id} vs {right.task_id}")
            pairs.append({"left": left.task_id, "right": right.task_id, "dimensions": decisions})
    expected = len(TASKS) * (len(TASKS) - 1) // 2
    if len(pairs) != expected:
        _fail("duplicate_family", f"expected {expected} pairs, found {len(pairs)}")
    return {
        "status": "pending_execution",
        "root_count": len(TASKS),
        "minimum_root_count": MIN_ROOTS,
        "maximum_root_count": MAX_ROOTS,
        "dimensions": list(HARD_RULE_DIMENSIONS),
        "pair_count": len(pairs),
        "expected_pair_count": expected,
        "pairs": pairs,
    }


def _screen_controls(out: Path) -> dict[str, object]:
    controls: dict[str, object] = {}
    base_by_name = {
        "domain-identifier-renamed-clone": "calendar-subscription-cycle",
        "constants-policy-clone": "calendar-subscription-cycle",
        "opposite-end-selection-clone": "calendar-subscription-cycle",
    }
    for name, base_id in base_by_name.items():
        base = out / base_id
        control = out / ".state/hard-rule-controls" / name
        changed = sorted(
            relative
            for relative in {
                path.relative_to(base).as_posix() for path in base.rglob("*") if path.is_file()
            }
            if (control / relative).is_file()
            and (base / relative).read_bytes() != (control / relative).read_bytes()
        )
        if not changed or not (control / "candidate.cpp").is_file():
            _fail("invariant_not_enforced", f"no coherent control change: {name}")
        decisions = _compare_dimensions(base, control)
        failed_dimensions = {
            dimension
            for dimension in HARD_RULE_DIMENSIONS
            if not decisions[dimension]["distinct"]
        }
        if decisions["pass"] or failed_dimensions != set(HARD_RULE_DIMENSIONS):
            _fail("duplicate_family", f"control not rejected in all dimensions: {name}")
        controls[name] = {
            "base_task": base_id,
            "changed_files": changed,
            "candidate_hash": _source_hash(control / "candidate.cpp"),
            "dimensions": decisions,
            "failed_dimensions": sorted(failed_dimensions),
            "semantic_screen": "rejected:duplicate_family",
        }
    return controls


def _benchmark_id_screen(root: Path) -> None:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        normalized = re.sub(r"[^a-z0-9]+", "-", path.read_text(encoding="utf-8").lower())
        for holdout in OFFICIAL_AIDER_CPP_HOLDOUTS:
            if re.search(rf"(?:^|-){re.escape(holdout)}(?:-|$)", normalized):
                if holdout in {"clock", "gigasecond", "meetup"} and path.name == "provenance.json":
                    continue
                _fail("benchmark_id_overlap", f"{root.name}: {holdout} in {path}")


def _semantic_holdout_screen(out: Path, holdout_root: Path = DEFAULT_HOLDOUT_ROOT) -> dict[str, object]:
    holdouts = sorted(path.parent.parent for path in holdout_root.rglob(".meta/config.json"))
    if len(holdouts) != len(OFFICIAL_AIDER_CPP_HOLDOUTS):
        _fail("benchmark_screen_not_completed", f"expected 26 holdouts, found {len(holdouts)}")
    comparisons: list[dict[str, object]] = []
    for spec in TASKS:
        candidate = "\n".join(_artifact_dimensions(out / spec.task_id).values())
        for holdout in holdouts:
            content = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in sorted(holdout.rglob("*"))
                if path.is_file() and path.suffix in {".md", ".h", ".hpp", ".cpp", ".toml", ".json"}
            )
            score = _containment(candidate, content)
            if score >= 0.94:
                _fail("benchmark_content_overlap", f"{spec.task_id} vs {holdout.name}: {score}")
            comparisons.append(
                {"task_id": spec.task_id, "holdout_id": holdout.name, "containment": round(score, 6)}
            )
    return {
        "status": "pass",
        "normalizer": SEMANTIC_NORMALIZER,
        "holdout_root_count": len(holdouts),
        "comparison_count": len(comparisons),
        "comparisons": comparisons,
    }


def _verify_remedies(out: Path) -> None:
    for spec in TASKS:
        record_path = out / ".state/remedy" / f"{spec.task_id}.json"
        markdown_path = out / ".state/remedy" / f"{spec.task_id}.md"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        markdown = markdown_path.read_text(encoding="utf-8")
        positions = [markdown.find(f"## {heading}") for heading in REMEDY_HEADINGS]
        if any(position < 0 for position in positions) or positions != sorted(positions):
            _fail("remedy_spec_incomplete", spec.task_id)
        if record["tree_hash_before"] != _tree_hash(LEGACY_ROOT / spec.task_id):
            _fail("generator_output_drift", f"legacy hash: {spec.task_id}")
        if record["remedy_spec_hash"] != _sha_bytes(markdown.encode()):
            _fail("remedy_spec_incomplete", f"hash: {spec.task_id}")
        if record["disposition"] != "repair-in-place" or record["status"] == "verified":
            _fail("remedy_disposition_conflict", spec.task_id)


def _sync_remedies(out: Path, **updates: object) -> None:
    for spec in TASKS:
        path = out / ".state/remedy" / f"{spec.task_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update(updates)
        record["tree_hash_after"] = _tree_hash(out / spec.task_id)
        record["changed_owner_paths"] = [
            CURRICULUM,
            FAMILY_SPEC,
            "docs/AIDER_TASK_MATERIALIZATION_GUIDE.md",
            "scripts/plan_general_calendar_arithmetic_remedies.py",
            "src/w8_biayn/integrations/moonlight_calendar_arithmetic_aider_tasks.py",
            CASES_PATH,
            "tests/test_moonlight_calendar_arithmetic_aider_tasks.py",
            "examples/slime/moonlight_cpp_perf/prepare_calendar_arithmetic_aider_tasks.sh",
        ]
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def _whole_answer_is_exact(root: Path) -> bool:
    task = load_task(root)
    response = build_assistant_response(task, load_example_files_from_config(root))
    return response.count("```") == 2 * len(task.editable_files) and all(
        response.count(f"{relative}\n```") == 1 for relative in task.editable_files
    )


def verify_core(out: Path) -> None:
    expected = {spec.task_id for spec in TASKS}
    actual = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", f"expected {sorted(expected)}, found {sorted(actual)}")
    if not (MIN_ROOTS <= len(actual) <= MAX_ROOTS):
        _fail("hard_rule_count_mismatch", str(len(actual)))
    _verify_remedies(out)
    with tempfile.TemporaryDirectory(prefix="calendar-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for spec in TASKS:
            if _tree_hash(out / spec.task_id) != _tree_hash(fresh / spec.task_id):
                _fail("generator_output_drift", spec.task_id)
    pair_matrix = _pair_matrix(out)
    controls = _screen_controls(out)
    holdout = _semantic_holdout_screen(out)
    task_rows: list[dict[str, object]] = []
    for spec in TASKS:
        root = out / spec.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        solution = [_safe_relative(value) for value in config["files"]["solution"]]
        tests = [_safe_relative(value) for value in config["files"]["test"]]
        examples = [_safe_relative(value) for value in config["files"]["example"]]
        if solution != [f"{spec.task_id}.h", f"{spec.task_id}.cpp"] or examples != [
            ".meta/example.h",
            ".meta/example.cpp",
        ]:
            _fail("target_reference_mismatch", spec.task_id)
        if any(not (root / value).is_file() for value in [*solution, *tests, *examples]):
            _fail("reference_map_failed", spec.task_id)
        if any(value.startswith((".meta/", ".docs/")) or value == "CMakeLists.txt" for value in solution):
            _fail("unsafe_path", spec.task_id)
        prompt = build_prompt(load_task(root))
        forbidden = [*tests, *examples, "CMakeLists.txt", "provenance.json", "task_hidden_test.cpp", "task_hard_rule_test.cpp", "negative_false_substitute.cpp"]
        if any(value in prompt for value in forbidden) or not all(value in prompt for value in solution):
            _fail("prompt_contract_incomplete", spec.task_id)
        if not _whole_answer_is_exact(root):
            _fail("whole_format_failed", spec.task_id)
        _benchmark_id_screen(root)
        task_rows.append(
            {
                "task_id": spec.task_id,
                "disposition": "repair-in-place",
                "primary_core_objective": "achieved",
                "tree_hash_before": _tree_hash(LEGACY_ROOT / spec.task_id),
                "tree_hash_after": _tree_hash(root),
                "semantic_profile": PROFILES[spec.task_id][0],
            }
        )
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "family_id": FAMILY_ID,
        "task_count": len(TASKS),
        "owner_hash": _source_hash(),
        "case_table_hash": _source_hash(Path(CASES_PATH)),
        "status": "implemented",
        "hard_rule_status": "pending_execution",
        "tasks": task_rows,
        "screen": {
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
            "duplicate_family": "pass",
            "hard_rule": pair_matrix,
            "adversarial_controls": controls,
            "benchmark_contamination": "pass",
            "semantic_holdout": holdout,
        },
    }
    _write(out / ".state/materialization-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    _sync_remedies(
        out,
        status="implemented",
        primary_core_objective="achieved",
        prompt_boundary="pass",
        reference_mapping="pass",
        family_screen="pass",
        benchmark_screen="pass",
        semantic_holdout_screen=holdout,
        hard_rule_status="pending_execution",
        strongest_local_status="implemented",
    )


def _ctest_count(build_dir: Path) -> int:
    result = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "-N"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    match = re.search(r"Total Tests:\s*(\d+)", result.stdout + result.stderr)
    if match is None or int(match.group(1)) <= 0:
        _fail("zero_tests", str(build_dir))
    return int(match.group(1))


def verify(out: Path) -> None:
    verify_core(out)
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        blocked = {
            "status": "not_completed",
            "command": "owner --verify (cmake -G 'Unix Makefiles' normal and sanitizer)",
            "missing_prerequisite": "host cmake and c++",
        }
        manifest_path = out / ".state/materialization-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["host_verification"] = blocked
        _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
        _sync_remedies(out, host_oracle_evidence=blocked)
        _fail("host_verification_not_completed", "verification requires cmake and c++")
    counts: dict[str, dict[str, int]] = {}
    for spec in TASKS:
        root = out / spec.task_id
        with tempfile.TemporaryDirectory(prefix=f"calendar-{spec.task_id}-") as temporary:
            copied = Path(temporary) / spec.task_id
            shutil.copytree(root, copied)
            for mode, flags in (
                ("normal", []),
                ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]),
            ):
                build_dir = Path(temporary) / f"build-{mode}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), "-G", "Unix Makefiles", "-DCMAKE_CXX_COMPILER=c++", f"-DTASK_SOURCE={copied / '.meta/example.cpp'}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                count = _ctest_count(build_dir)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                counts.setdefault(spec.task_id, {})[mode] = count
            negative = Path(temporary) / "build-negative"
            subprocess.run(["cmake", "-S", str(copied), "-B", str(negative), "-G", "Unix Makefiles", "-DCMAKE_CXX_COMPILER=c++", f"-DTASK_SOURCE={copied / '.meta/negative_false_substitute.cpp'}"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            subprocess.run(["cmake", "--build", str(negative), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if _ctest_count(negative) != 3 or subprocess.run(["ctest", "--test-dir", str(negative)], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode == 0:
                _fail("negative_fixture_not_rejected", spec.task_id)
    if any(modes.get("normal") != 3 or modes.get("sanitizer") != 3 for modes in counts.values()):
        _fail("sanitizer_test_count_mismatch", "host iteration")
    _write(out / ".state/host-verification-receipt.json", json.dumps({"schema_version": "aider-general-calendar-arithmetic-host-iteration-v1", "evidence_class": "host_iteration_only", "local_family_verified": False, "owner_hash": _source_hash(), "case_table_hash": _source_hash(Path(CASES_PATH)), "test_counts": counts}, indent=2, sort_keys=True) + "\n", True)


def _deterministic_archive(out: Path, destination: Path) -> str:
    with tarfile.open(destination, "w") as archive:
        roots = [(Path(spec.task_id), out / spec.task_id) for spec in TASKS]
        roots.append((Path(".hard-rule-controls"), out / ".state/hard-rule-controls"))
        for prefix, root in roots:
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                data = path.read_bytes()
                info = tarfile.TarInfo((prefix / path.relative_to(root)).as_posix())
                info.size = len(data)
                info.mode = 0o644
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                archive.addfile(info, io.BytesIO(data))
    return _sha_bytes(destination.read_bytes())


def docker_sanity(out: Path, image: str = SANITY_IMAGE) -> None:
    verify_core(out)
    if shutil.which("docker") is None:
        _fail("docker_sanity_not_completed", "docker executable unavailable")
    inspect = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if inspect.returncode:
        _fail("docker_sanity_not_completed", inspect.stderr.strip())
    image_id = inspect.stdout.strip()
    with tempfile.TemporaryDirectory(prefix="calendar-docker-") as temporary:
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
  negative="/tmp/build-${task}-negative"
  cmake -S "$root" -B "$negative" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/negative_false_substitute.cpp"
  cmake --build "$negative" --parallel 2
  count=$(ctest --test-dir "$negative" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
  set +e; ctest --test-dir "$negative" --output-on-failure; code=$?; set -e
  test "$count" -gt 0 && test "$code" -ne 0
  printf '%s\t%s\t%s\n' "$task" "$count" "$code" >> /result/topic-negative.tsv
done
for root in /tmp/family/.hard-rule-controls/*; do
  name=$(basename "$root")
  for mode in normal sanitizer; do
    build="/tmp/build-control-${name}-${mode}"
    if [ "$mode" = sanitizer ]; then
      cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/candidate.cpp" "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"
    else
      cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/candidate.cpp"
    fi
    cmake --build "$build" --parallel 2
    count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
    ctest --test-dir "$build" --output-on-failure
    printf '%s\t%s\t%s\n' "$name" "$mode" "$count" >> /result/adversarial-controls.tsv
  done
done
sha256sum /input/family.tar | awk '{print "sha256:" $1}' > /result/archive.sha256
'''
        command = ["docker", "run", "--rm", "--network", "none", "--mount", f"type=bind,src={archive},dst=/input/family.tar,readonly", "--mount", f"type=bind,src={results},dst=/result", image, "sh", "-lc", runner]
        run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if run.returncode:
            _fail("docker_sanity_failed", run.stdout[-8000:])
        mounted = (results / "archive.sha256").read_text(encoding="utf-8").strip()
        if mounted != archive_hash:
            _fail("grader_mount_hash_mismatch", f"owner={archive_hash} docker={mounted}")
        counts: dict[str, dict[str, int]] = {}
        for line in (results / "counts.tsv").read_text(encoding="utf-8").splitlines():
            task_id, mode, raw = line.split("\t")
            counts.setdefault(task_id, {})[mode] = int(raw)
        expected = {spec.task_id for spec in TASKS}
        if set(counts) != expected:
            _fail("test_discovery_failed", "incomplete task inventory")
        for task_id, modes in counts.items():
            if modes.get("normal", 0) <= 0 or modes.get("normal") != modes.get("sanitizer"):
                _fail("sanitizer_test_count_mismatch", task_id)
        negatives: dict[str, dict[str, object]] = {}
        for line in (results / "topic-negative.tsv").read_text(encoding="utf-8").splitlines():
            task_id, raw_count, raw_code = line.split("\t")
            negatives[task_id] = {"compiled": True, "discovered_tests": int(raw_count), "ctest_exit": int(raw_code), "rejected_by_executed_tests": int(raw_code) != 0}
        if set(negatives) != expected or any(not row["rejected_by_executed_tests"] for row in negatives.values()):
            _fail("negative_fixture_not_rejected", "topic-negative receipt")
        control_counts: dict[str, dict[str, int]] = {}
        for line in (results / "adversarial-controls.tsv").read_text(encoding="utf-8").splitlines():
            name, mode, raw_count = line.split("\t")
            control_counts.setdefault(name, {})[mode] = int(raw_count)
        expected_controls = {"domain-identifier-renamed-clone", "constants-policy-clone", "opposite-end-selection-clone"}
        if set(control_counts) != expected_controls or any(modes.get("normal", 0) <= 0 or modes.get("normal") != modes.get("sanitizer") for modes in control_counts.values()):
            _fail("adversarial_control_not_pure", "normal/sanitizer behavior passage")
        receipt = {
            "schema_version": "aider-general-calendar-arithmetic-docker-sanity-v1",
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "network_policy": "none",
            "image": image,
            "image_id": image_id,
            "archive_hash": archive_hash,
            "owner_hash": _source_hash(),
            "case_table_hash": _source_hash(Path(CASES_PATH)),
            "family_tree_hashes": {spec.task_id: _tree_hash(out / spec.task_id) for spec in TASKS},
            "reference_hashes": {spec.task_id: _source_hash(out / spec.task_id / ".meta/example.cpp") for spec in TASKS},
            "negative_hashes": {spec.task_id: _source_hash(out / spec.task_id / ".meta/negative_false_substitute.cpp") for spec in TASKS},
            "compiler": (results / "compiler.txt").read_text(encoding="utf-8").strip(),
            "cmake": (results / "cmake.txt").read_text(encoding="utf-8").strip(),
            "commands": {"docker": command[:8] + [image, "sh", "-lc", "<owner-controlled-runner>"], "normal": "fresh Unix Makefiles reference build and ctest", "sanitizer": "fresh ASan/UBSan Unix Makefiles reference build and ctest", "topic_negative": "strict build and executed-test rejection", "adversarial_controls": "normal and sanitizer build/test passage plus semantic rejection"},
            "test_counts": counts,
            "topic_negatives": negatives,
            "adversarial_controls": control_counts,
        }
        receipt_path = out / ".state/oracle-receipt.json"
        _write(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        receipt_hash = _source_hash(receipt_path)
        manifest_path = out / ".state/materialization-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["status"] = "local_family_verified"
        manifest["hard_rule_status"] = "pass"
        manifest["screen"]["hard_rule"]["status"] = "pass"
        manifest["screen"]["hard_rule"]["topic_negative_execution"] = negatives
        manifest["screen"]["hard_rule"]["adversarial_control_execution"] = control_counts
        manifest["oracle_receipt"] = ".state/oracle-receipt.json"
        manifest["oracle_receipt_hash"] = receipt_hash
        manifest["evidence_class"] = "docker_sanity"
        manifest["locked_oracle"] = False
        _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
        _sync_remedies(out, status="verified", oracle_evidence={"status": "pass", "evidence_class": "docker_sanity", "locked_oracle": False, "receipt_path": ".state/oracle-receipt.json", "receipt_hash": receipt_hash, "image": image_id, "network": "none", "normal_discovered_tests": 3, "sanitizer_discovered_tests": 3, "topic_negative_discovered_tests": 3, "topic_negative_rejected": True, "pure_clone_controls_behavior_tests_passed": True, "pure_clone_controls_semantically_rejected": True}, hard_rule_status="pass", strongest_local_status="local_family_verified")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format general-calendar-arithmetic curriculum tasks.")
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
    print(f"Wrote {len(roots)} general-calendar-arithmetic curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
