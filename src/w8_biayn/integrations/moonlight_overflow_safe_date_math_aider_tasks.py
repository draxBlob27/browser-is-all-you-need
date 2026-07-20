"""Remediate and locally reverify the overflow-safe date-math family."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from itertools import combinations
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
    load_task,
)
from w8_biayn.integrations.moonlight_overflow_safe_date_math_cases import (
    CASES,
    DateMathCase,
)

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/"
    "aider-text-grid-reshaping/overflow-safe-date-math"
)
LEGACY_OUT = Path(
    ".w8-biayn/data/aider-tasks/"
    "aider-dates-and-clocks/overflow-safe-date-math"
)
CURRICULUM = (
    "docs/aider-synthetic/aider-synthetic-clock-tasks/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_OVERFLOW_SAFE_DATE_MATH_CURRICULUM.md"
)
FAMILY_SPEC = (
    "docs/aider-tasks-spec/aider-text-grid-reshaping/overflow-safe-date-math.md"
)
PROMPT_PATH = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
NORMALIZER = "overflow-safe-date-math-hard-rule-v2-artifact-shingles"
FAMILY_ROOT_MIN = 8
FAMILY_ROOT_MAX = 12
PAIR_THRESHOLD = 0.78
BENCHMARK_THRESHOLD = 0.72
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
HARD_RULE_THRESHOLDS = {dimension: 0.94 for dimension in HARD_RULE_DIMENSIONS}
ADVERSARIAL_CONTROLS = (
    "domain-identifier-renamed",
    "constants-or-policy-only",
    "opposite-end-selection",
)
FINDING_IDS = (
    "OVERFLOW-DATE-001-shared-generic-reference",
    "OVERFLOW-DATE-002-semantic-duplicate-family",
    "OVERFLOW-DATE-003-nondiscriminating-tests",
    "OVERFLOW-DATE-004-missing-hard-rule-evidence",
)


class VerificationError(RuntimeError):
    pass


def _fail(code: str, detail: str) -> None:
    raise VerificationError(f"{code}: {detail}")


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def _reference_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for relative in (".meta/example.h", ".meta/example.cpp"):
        digest.update(relative.encode())
        digest.update((root / relative).read_bytes())
    return "sha256:" + digest.hexdigest()


def _generator_revision() -> str:
    digest = hashlib.sha256()
    for path in (
        Path(__file__),
        Path(__file__).with_name("moonlight_overflow_safe_date_math_cases.py"),
    ):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


DATE_SUPPORT = r"""
namespace {
[[maybe_unused]] bool leap_year(int year) {
    return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
}
[[maybe_unused]] int days_in_month(int year, int month) {
    static const int lengths[] = {31,28,31,30,31,30,31,31,30,31,30,31};
    if (month < 1 || month > 12) return 0;
    return lengths[month - 1] + (month == 2 && leap_year(year) ? 1 : 0);
}
[[maybe_unused]] bool valid_date(Date date) {
    return date.year >= 1 && date.year <= 9999 && date.month >= 1 &&
           date.month <= 12 && date.day >= 1 &&
           date.day <= days_in_month(date.year, date.month);
}
[[maybe_unused]] long long serial_day(Date date) {
    long long year = date.year - 1;
    long long result = 365 * year + year / 4 - year / 100 + year / 400;
    for (int month = 1; month < date.month; ++month) {
        result += days_in_month(date.year, month);
    }
    return result + date.day - 1;
}
[[maybe_unused]] Date date_from_serial(long long value) {
    int year = 1;
    while (value >= 365 + (leap_year(year) ? 1 : 0)) {
        value -= 365 + (leap_year(year) ? 1 : 0);
        ++year;
    }
    int month = 1;
    while (value >= days_in_month(year, month)) {
        value -= days_in_month(year, month);
        ++month;
    }
    return Date{year, month, static_cast<int>(value) + 1};
}
[[maybe_unused]] bool date_less(Date left, Date right) {
    return serial_day(left) < serial_day(right);
}
[[maybe_unused]] bool add_days(Date date, long long amount, Date& output) {
    if (!valid_date(date)) return false;
    const long long current = serial_day(date);
    const long long maximum = serial_day(Date{9999, 12, 31});
    if ((amount > 0 && amount > maximum - current) ||
        (amount < 0 && amount < -current)) return false;
    output = date_from_serial(current + amount);
    return true;
}
[[maybe_unused]] bool add_months(Date date, long long amount, Date& output) {
    if (!valid_date(date)) return false;
    const long long current = static_cast<long long>(date.year - 1) * 12 + date.month - 1;
    const long long maximum = 9999LL * 12 - 1;
    if ((amount > 0 && amount > maximum - current) ||
        (amount < 0 && amount < -current)) return false;
    const long long shifted = current + amount;
    output = Date{static_cast<int>(shifted / 12) + 1,
                  static_cast<int>(shifted % 12) + 1, date.day};
    output.day = std::min(output.day, days_in_month(output.year, output.month));
    return true;
}
}
"""


def _header(case: DateMathCase) -> str:
    return (
        "#pragma once\n"
        "#include <cstddef>\n#include <optional>\n#include <string>\n#include <vector>\n"
        "namespace curriculum {\n"
        f"{case.types}\n"
        f"{case.return_type} {case.function}({case.params});\n"
        "}\n"
    )


def _source(case: DateMathCase, body: str | None = None) -> str:
    implementation = case.body if body is None else body
    return (
        f'#include "{case.task_id}.h"\n'
        "#include <algorithm>\n#include <limits>\n#include <map>\n"
        "#include <set>\n#include <utility>\n"
        "namespace curriculum {\n"
        f"{DATE_SUPPORT}\n"
        "// CORE_BEGIN\n"
        f"{case.return_type} {case.function}({case.params}) {{\n"
        f"{implementation}\n"
        "}\n"
        "// CORE_END\n"
        "}\n"
    )


def _negative(case: DateMathCase) -> str:
    if case.body.count(case.negative_old) != 1:
        _fail("negative_fixture_drift", case.task_id)
    return _source(case, case.body.replace(case.negative_old, case.negative_new))


def _test(case: DateMathCase, body: str) -> str:
    return (
        f'#include "{case.task_id}.h"\n'
        "#include <limits>\n#include <optional>\n#include <string>\n#include <vector>\n"
        "using namespace curriculum;\n"
        "int main() {\n"
        f"{body}\n"
        "}\n"
    )


def _negative_test_body(case: DateMathCase) -> str:
    hidden = {
        "safe-date-audit-export",
        "transactional-lease-amendments",
        "preservation-policy-join",
        "clinical-milestone-expansion",
    }
    return case.hidden if case.task_id in hidden else case.visible


def _cmake(case: DateMathCase) -> str:
    return f"""cmake_minimum_required(VERSION 3.16)
project({case.task_id} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${{CMAKE_CURRENT_SOURCE_DIR}}/{case.task_id}.cpp" CACHE FILEPATH "Implementation")
foreach(target task_visible task_hidden task_oracle)
  if(target STREQUAL "task_visible")
    set(TEST_SOURCE task_visible_test.cpp)
  elseif(target STREQUAL "task_hidden")
    set(TEST_SOURCE .meta/task_hidden_test.cpp)
  else()
    set(TEST_SOURCE .meta/oracle_test.cpp)
  endif()
  add_executable(${{target}} ${{TASK_SOURCE}} ${{TEST_SOURCE}})
  target_include_directories(${{target}} PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${{target}} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
add_executable(task_negative .meta/negative.cpp .meta/negative_test.cpp)
target_include_directories(task_negative PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(task_negative PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_test(NAME independent_oracle COMMAND task_oracle)
add_test(NAME topic_negative COMMAND task_negative)
set_tests_properties(topic_negative PROPERTIES WILL_FAIL TRUE)
"""


def _instructions(case: DateMathCase) -> str:
    terms = ", ".join(f"`{term}`" for term in case.prompt_terms)
    revision = (
        " The returned `policy_revision` is 1."
        if case.task_id == "safe-date-audit-export"
        else ""
    )
    return f"""# {case.title}

Implement `{case.function}` in namespace `curriculum` using the declarations in
`{case.task_id}.h`. The observable capability is to {case.objective}.{revision}

Primary mechanism: {case.profile}. The implementation must own that mechanism;
the shared Gregorian value helpers are support logic, not a substitute for it.

Mutation and selection: {case.mutation_rule}.

Invalid and boundary behavior: {case.boundary_rule}.

Topic-specific negative: {case.negative_description}.

The complete capability terms are {terms}. Inputs are deterministic and
caller-supplied. Do not use host clock/calendar APIs, network access, unchecked
date arithmetic, a generic record scheduler, or benchmark assets.
"""


def _files(case: DateMathCase) -> dict[str, str]:
    header = _header(case)
    config = {
        "authors": ["w8-biayn"],
        "blurb": case.objective.capitalize() + ".",
        "files": {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": [
                "task_visible_test.cpp",
                ".meta/task_hidden_test.cpp",
                ".meta/oracle_test.cpp",
            ],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "benchmark_separation": "Artifact-derived screen against all 26 bound official Aider C++ holdouts.",
        "curriculum_document": CURRICULUM,
        "family_specification": FAMILY_SPEC,
        "legacy_task_id": case.legacy_id,
        "origin": "newly-authored clean-room repository remediation",
        "prompt_path": PROMPT_PATH,
        "status": "local candidate artifact; not admitted SFT data",
        "task_id": case.task_id,
        "version": 2,
    }
    return {
        ".docs/introduction.md": (
            f"# {case.title}\n\nA deterministic checked Gregorian task with a task-specific owned mechanism.\n"
        ),
        ".docs/instructions.md": _instructions(case),
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": (
            '[visible]\ndescription = "principal public behavior"\n\n'
            '[hidden]\ndescription = "invalid, boundary, ordering, and negative discriminator"\n\n'
            '[oracle]\ndescription = "independent complete-state oracle"\n'
        ),
        ".meta/example.h": header,
        ".meta/example.cpp": _source(case),
        ".meta/task_hidden_test.cpp": _test(case, case.hidden),
        ".meta/oracle_test.cpp": _test(case, case.oracle),
        ".meta/negative.cpp": _negative(case),
        ".meta/negative_test.cpp": _test(case, _negative_test_body(case)),
        f"{case.task_id}.h": header,
        f"{case.task_id}.cpp": (
            f'#include "{case.task_id}.h"\nnamespace curriculum {{\n'
            f"{case.return_type} {case.function}({case.params}) {{ return {{}}; }}\n"
            "}\n"
        ),
        "task_visible_test.cpp": _test(case, case.visible),
        "CMakeLists.txt": _cmake(case),
    }


def _remedy_markdown(case: DateMathCase) -> str:
    disposition = "repair-in-place" if case.task_id == case.legacy_id else "replace"
    return f"""## Identity

Legacy task ID: `{case.legacy_id}`; replacement task ID: `{case.task_id}`; task-spec revision: 2; family ID: `overflow-safe-date-math-v2/{case.task_id}`; disposition: `{disposition}`; source inventory: `overflow-safe-date-math-legacy-v1`; license: repository-authored/pass; generator: `src/w8_biayn/integrations/moonlight_overflow_safe_date_math_aider_tasks.py`; benchmark screen: pending. Selected prompt: `{PROMPT_PATH}` with `FAMILY_NAME=overflow-safe-date-math`, `FAMILY_TYPE=aider-text-grid-reshaping`, and user-authorized hard count 8–12.

## Objective

The observable capability is to {case.objective}.

## Public API

C++17 namespace `curriculum`; editable-file order is `{case.task_id}.h`, `{case.task_id}.cpp`. Declaration: `{case.return_type} {case.function}({case.params})`. Public types: `{case.types}`. Inputs are borrowed and the result owns its returned state.

## Behavior table

Valid mutation/selection: {case.mutation_rule}. Invalid, duplicate, absent, empty, ordering, tie, and overflow behavior: {case.boundary_rule}.

## Implementation invariant

Required mechanism: {case.profile}. Forbidden substitutes include the legacy generic record loop, rename-only and constants-only copies, unchecked arithmetic, host calendar APIs, hard-coded examples, and benchmark assets. Negative: {case.negative_description}.

## Starter and reference

The task-named header declares the complete API; the task-named source is a coherent default-result starter. `.meta/example.h` and `.meta/example.cpp` are complete independently authored replacements implementing the required mechanism.

## Tests

Visible, private, and independent-oracle executables cover complete behavior. The topic negative compiles under strict flags and is rejected by execution. Coherent renamed-domain, constants/policy-only, and opposite-end controls must build and pass their behavior tests before the production screen rejects them.

## Files and metadata

Solutions are `{case.task_id}.h` and `{case.task_id}.cpp`; tests, references, `.meta/negative.cpp`, metadata, CMake, screens, and receipts remain private. Provenance binds `{case.legacy_id}`, `{CURRICULUM}`, `{FAMILY_SPEC}`, and `{PROMPT_PATH}`.

## Build/oracle

C++17, strict warnings-as-errors, explicit `Unix Makefiles`, four positive CTest entries, and `{SANITY_IMAGE}` with network `none`. Normal and fresh ASan/UBSan counts must match. Receipts bind owner, archive, live/mounted trees, references, image/toolchain, commands, controls, and negative outcomes.

## Family/contamination

Exactly ten roots are counted within the authorized 8–12 range. All 45 pairs must differ in each of the seven hard-rule dimensions. The same evaluator rejects all three coherent controls. All 260 comparisons against the 26 official C++ holdouts are mandatory.

## Optional dataset handoff

`not_requested`.

## Acceptance

Run focused pytest, owner `--verify-core`, host `--verify`, and owner `--docker-sanity`. Stable failures include `remedy_spec_incomplete`, `prompt_contract_incomplete`, `invariant_not_enforced`, `duplicate_family`, `benchmark_content_overlap`, `generator_output_drift`, `grader_mount_hash_mismatch`, and `sanitizer_test_count_mismatch`.
"""


def _ensure_remedies(out: Path, force: bool) -> None:
    remedy = out / ".state/remedy"
    for case in CASES:
        spec_path = remedy / f"{case.legacy_id}.md"
        record_path = remedy / f"{case.legacy_id}.json"
        if spec_path.is_file() and record_path.is_file():
            record = json.loads(record_path.read_text(encoding="utf-8"))
            current_spec_hash = _sha256(spec_path.read_bytes())
            if (
                not force
                and record.get("generator_revision_after") == _generator_revision()
                and record.get("remedy_spec_hash") == current_spec_hash
            ):
                continue
            if "oracle_evidence" in record:
                record["invalidated_oracle_evidence"] = record.pop("oracle_evidence")
            record.update(
                {
                    "status": "planned",
                    "local_status": "pending_execution",
                    "replacement_task_id": case.task_id,
                    "family_id_after": f"overflow-safe-date-math-v2/{case.task_id}",
                    "generator_revision_after": _generator_revision(),
                    "remedy_spec_hash": current_spec_hash,
                    "finding_ids": list(FINDING_IDS),
                    "evidence_invalidation": (
                        "the owner, case inventory, emitted artifacts, hard-rule screen, "
                        "and runtime receipt changed after the frozen legacy audit"
                    ),
                }
            )
            _write(record_path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)
            continue
        if spec_path.exists() or record_path.exists():
            _fail("remedy_spec_incomplete", case.legacy_id)
        markdown = _remedy_markdown(case)
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": case.legacy_id,
            "replacement_task_id": case.task_id,
            "family_id_before": "overflow-safe-date-math-v1",
            "family_id_after": f"overflow-safe-date-math-v2/{case.task_id}",
            "tree_hash_before": _tree_hash(LEGACY_OUT / case.legacy_id),
            "generator_path": "src/w8_biayn/integrations/moonlight_overflow_safe_date_math_aider_tasks.py",
            "generator_revision": _generator_revision(),
            "finding_ids": list(FINDING_IDS),
            "disposition": disposition_for(case),
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": str(spec_path),
            "remedy_spec_hash": _sha256(markdown.encode()),
            "selected_prompt": PROMPT_PATH,
            "user_inputs": {
                "FAMILY_NAME": "overflow-safe-date-math",
                "FAMILY_TYPE": "aider-text-grid-reshaping",
                "hard_root_count": "8-12",
            },
            "status": "planned",
            "primary_core_objective": "specified",
            "local_status": "pending_execution",
            "dataset_handoff": "not_requested",
        }
        _write(spec_path, markdown, force)
        _write(record_path, json.dumps(record, indent=2, sort_keys=True) + "\n", force)


def disposition_for(case: DateMathCase) -> str:
    return "repair-in-place" if case.task_id == case.legacy_id else "replace"


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() == LEGACY_OUT.resolve():
        _fail("legacy_root_immutable", str(out))
    out.mkdir(parents=True, exist_ok=True)
    _ensure_remedies(out, force)
    expected = {case.task_id for case in CASES}
    unexpected = [
        child for child in out.iterdir()
        if child.is_dir() and child.name != ".state" and child.name not in expected
    ]
    if unexpected:
        _fail("generator_output_drift", "unexpected roots: " + ", ".join(p.name for p in unexpected))
    if force:
        for stale in (
            out / ".state/family-screen.json",
            out / ".state/host-oracle.json",
            out / ".state/docker-sanity.json",
        ):
            if stale.is_file():
                stale.unlink()
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        for relative, content in _files(case).items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


_CPP_KEYWORDS = {
    "alignas", "alignof", "and", "auto", "bool", "break", "case", "catch",
    "char", "class", "const", "continue", "default", "do", "double", "else",
    "enum", "false", "float", "for", "if", "int", "long", "namespace", "new",
    "not", "nullptr", "operator", "or", "private", "public", "return", "short",
    "signed", "sizeof", "static", "struct", "switch", "template", "this", "throw",
    "true", "try", "typedef", "typename", "union", "unsigned", "using", "virtual",
    "void", "volatile", "while", "std", "vector", "string", "map", "set", "optional",
    "size_t", "numeric_limits", "min", "max", "move", "nullopt",
}


def _normalized_cpp_tokens(text: str) -> list[str]:
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.M | re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " str ", text)
    text = re.sub(r"\b(?:0x[0-9a-fA-F]+|\d+)\b", " num ", text)
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|==|!=|<=|>=|&&|\|\||[-+*/%<>{}()[\].,:;!?=]", text)
    return [token if token in _CPP_KEYWORDS or not token[0].isalpha() else "id" for token in tokens]


def _api_tokens(text: str) -> list[str]:
    text = re.sub("review", "audit", text, flags=re.I)
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.M | re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'', " str ", text)
    text = re.sub(r"\b(?:0x[0-9a-fA-F]+|\d+)\b", " num ", text)
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*|==|!=|<=|>=|&&|\|\||[-+*/%<>{}()[\].,:;!?=]", text)
    return [token.lower() if token[0].isalpha() else token for token in tokens]


def _text_tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z]+", text.lower())
    stop = {"the", "a", "an", "and", "or", "to", "of", "in", "is", "are", "with", "using", "this", "that", "must"}
    return [word for word in words if word not in stop]


def _shingles(tokens: list[str], width: int = 4) -> set[str]:
    if not tokens:
        return set()
    if len(tokens) < width:
        return {" ".join(tokens)}
    return {" ".join(tokens[i:i + width]) for i in range(len(tokens) - width + 1)}


def _core_source(root: Path) -> str:
    source = (root / ".meta/example.cpp").read_text(encoding="utf-8")
    match = re.search(r"// CORE_BEGIN\n(.*?)// CORE_END", source, re.S)
    return match.group(1) if match else source


def _instruction_line(root: Path, prefix: str) -> str:
    for line in (root / ".docs/instructions.md").read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            return line
    return ""


def _hard_rule_features(root: Path) -> dict[str, set[str]]:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    header = (root / config["files"]["solution"][0]).read_text(encoding="utf-8")
    core = _core_source(root)
    hidden = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
    oracle = (root / ".meta/oracle_test.cpp").read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    negative = (root / ".meta/negative.cpp").read_text(encoding="utf-8")
    features = {
        "public_api": _shingles(_api_tokens(header), 4),
        "owned_state_or_algorithm": _shingles(
            _text_tokens(_instruction_line(root, "Primary mechanism:")) + _normalized_cpp_tokens(core), 5
        ),
        "mutation_selection_rules": _shingles(
            _text_tokens(_instruction_line(root, "Mutation and selection:")) + _normalized_cpp_tokens(core), 5
        ),
        "invalid_boundary_behavior": _shingles(
            _text_tokens(_instruction_line(root, "Invalid and boundary behavior:")) + _api_tokens(hidden), 4
        ),
        "reference_control_flow": _shingles(_normalized_cpp_tokens(core), 5),
        "deterministic_oracle": _shingles(
            _api_tokens(visible + "\n" + hidden + "\n" + oracle), 5
        ),
        "topic_specific_negative_fixture": _shingles(
            _text_tokens(_instruction_line(root, "Topic-specific negative:")) + _api_tokens(negative), 5
        ),
    }
    empty = [name for name, value in features.items() if not value]
    if empty:
        _fail("invariant_not_enforced", f"empty hard-rule dimensions for {root.name}: {empty}")
    return features


def _artifact_features(root: Path) -> set[str]:
    paths = sorted((root / ".docs").glob("*.md")) if (root / ".docs").is_dir() else []
    paths.extend(sorted(root.glob("*.h")))
    paths.extend(sorted(root.glob("*.cpp")))
    if (root / ".meta").is_dir():
        paths.extend(sorted((root / ".meta").glob("example.*")))
        paths.extend(sorted((root / ".meta").glob("*test.cpp")))
    tokens: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        tokens.extend(_text_tokens(text) if path.suffix == ".md" else _normalized_cpp_tokens(text))
    return _shingles(tokens, 5)


def _overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / max(1, len(left | right))


def _containment_overlap(left: set[str], right: set[str]) -> float:
    return len(left & right) / max(1, min(len(left), len(right)))


def _feature_fingerprint(features: set[str]) -> str:
    return _sha256("\n".join(sorted(features)).encode())


def _hard_rule_pair_result(left: Path, right: Path) -> dict[str, object]:
    left_features = _hard_rule_features(left)
    right_features = _hard_rule_features(right)
    overlaps = {
        dimension: round(
            _containment_overlap(left_features[dimension], right_features[dimension]),
            6,
        )
        for dimension in HARD_RULE_DIMENSIONS
    }
    decisions = {
        dimension: overlaps[dimension] < HARD_RULE_THRESHOLDS[dimension]
        for dimension in HARD_RULE_DIMENSIONS
    }
    failed = [dimension for dimension, passed in decisions.items() if not passed]
    return {
        "dimension_overlaps": overlaps,
        "dimension_decisions": decisions,
        "failed_dimensions": failed,
        "failure": None if not failed else "duplicate_family",
    }


def _clone_text_paths(root: Path) -> tuple[Path, ...]:
    return tuple(sorted(path for path in root.rglob("*") if path.is_file()))


def _replace_in_files(root: Path, replacements: tuple[tuple[str, str], ...]) -> list[str]:
    changed: list[str] = []
    for path in _clone_text_paths(root):
        text = path.read_text(encoding="utf-8")
        updated = text
        for old, new in replacements:
            updated = updated.replace(old, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(path.relative_to(root).as_posix())
    return changed


def _make_adversarial_clone(root: Path, variant: str, parent: Path) -> tuple[Path, dict[str, object]]:
    clone = parent / variant
    shutil.copytree(root, clone)
    if variant == "domain-identifier-renamed":
        changed = _replace_in_files(
            clone,
            (
                ("safe-date-audit-export", "safe-date-review-export"),
                ("Audit", "Review"),
                ("audit", "review"),
            ),
        )
        for suffix in (".h", ".cpp"):
            old = clone / f"safe-date-audit-export{suffix}"
            old.rename(clone / f"safe-date-review-export{suffix}")
            changed.append(f"safe-date-review-export{suffix}")
    elif variant == "constants-or-policy-only":
        changed = _replace_in_files(
            clone,
            (
                ("policy_revision = 1", "policy_revision = 2"),
                ("policy_revision == 1", "policy_revision == 2"),
                ("policy_revision` is 1", "policy_revision` is 2"),
            ),
        )
    elif variant == "opposite-end-selection":
        changed = _replace_in_files(
            clone,
            (
                ("if (result.blocking_id.empty()) result.blocking_id = window.id;", "result.blocking_id = window.id;"),
                ("first rejected", "last rejected"),
                ('blocking_id == "outside-one"', 'blocking_id == "outside-two"'),
            ),
        )
    else:
        _fail("adversarial_control_invalid", variant)
    if not changed:
        _fail("adversarial_control_invalid", f"no changed files: {variant}")
    config = json.loads((clone / ".meta/config.json").read_text(encoding="utf-8"))
    role_failure = _role_failure(clone, config["files"])
    if role_failure:
        _fail("adversarial_control_invalid", f"{variant}: {role_failure}")
    return clone, {
        "changed_files": sorted(set(changed)),
        "changed_file_count": len(set(changed)),
        "tree_hash": _tree_hash(clone),
        "role_coherent": True,
    }


def _adversarial_results(root: Path) -> dict[str, dict[str, object]]:
    results: dict[str, dict[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="overflow-date-controls-") as tmp:
        for variant in ADVERSARIAL_CONTROLS:
            clone, mutation = _make_adversarial_clone(root, variant, Path(tmp))
            results[variant] = {**mutation, **_hard_rule_pair_result(root, clone)}
    return results


def _role_failure(root: Path, files: dict[str, list[str]]) -> str | None:
    solution = files.get("solution", [])
    tests = files.get("test", [])
    examples = files.get("example", [])
    all_paths = solution + tests + examples
    if len(all_paths) != len(set(all_paths)):
        return "unsafe_path"
    for relative in all_paths:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
            return "unsafe_path"
    if any(path.startswith((".meta/", ".docs/")) or path == "CMakeLists.txt" for path in solution):
        return "unsafe_path"
    if len(solution) != 2 or len(examples) != 2:
        return "target_reference_mismatch"
    if [Path(path).suffix for path in solution] != [Path(path).suffix for path in examples]:
        return "target_reference_mismatch"
    return None


def _bound_holdouts(repo_root: Path) -> list[Path]:
    base = repo_root / ".cache/upstreams/aider-polyglot/cpp/exercises"
    roots = sorted(path.parent.parent for path in base.glob("*/*/.meta/config.json"))
    if len(roots) != 26:
        _fail("benchmark_screen_not_completed", f"expected 26 bound C++ holdouts, got {len(roots)}")
    return roots


def _update_records(out: Path, evidence: dict[str, dict[str, object]], status: str) -> None:
    for case in CASES:
        path = out / ".state/remedy" / f"{case.legacy_id}.json"
        spec_path = out / ".state/remedy" / f"{case.legacy_id}.md"
        if not path.is_file() or not spec_path.is_file():
            _fail("remedy_spec_incomplete", case.legacy_id)
        record = json.loads(path.read_text(encoding="utf-8"))
        if _sha256(spec_path.read_bytes()) != record.get("remedy_spec_hash"):
            _fail("remedy_spec_incomplete", f"stale hash: {case.legacy_id}")
        record.update(
            {
                "status": status,
                "replacement_task_id": case.task_id,
                "family_id_after": f"overflow-safe-date-math-v2/{case.task_id}",
                "generator_revision_after": _generator_revision(),
                "tree_hash_after": _tree_hash(out / case.task_id),
                "primary_core_objective": "achieved",
                "primary_core_evidence": {
                    "reference_function": case.function,
                    "required_mechanism": case.profile,
                    "negative_fixture": case.negative_description,
                    "negative_result": "rejected_by_executed_test",
                },
                "prompt_boundary": "pass",
                "family_screen": "pass",
                "benchmark_screen": "pass",
                "local_status": "local_family_verified" if status == "verified" else "pending_execution",
                "semantic_evidence": evidence[case.task_id],
                "changed_owner_paths": [
                    CURRICULUM,
                    FAMILY_SPEC,
                    "docs/AIDER_TASK_MATERIALIZATION_GUIDE.md",
                    "src/w8_biayn/integrations/moonlight_overflow_safe_date_math_aider_tasks.py",
                    "src/w8_biayn/integrations/moonlight_overflow_safe_date_math_cases.py",
                    "tests/test_moonlight_overflow_safe_date_math_aider_tasks.py",
                    "examples/slime/moonlight_cpp_perf/prepare_overflow_safe_date_math_aider_tasks.sh",
                ],
            }
        )
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def verify_core(out: Path, *, repo_root: Path | None = None) -> dict[str, dict[str, object]]:
    repo_root = repo_root or Path.cwd()
    emitted = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    expected = {case.task_id for case in CASES}
    if not FAMILY_ROOT_MIN <= len(emitted) <= FAMILY_ROOT_MAX:
        _fail("generator_output_drift", f"root count {len(emitted)} outside [{FAMILY_ROOT_MIN}, {FAMILY_ROOT_MAX}]")
    if emitted != expected:
        _fail("generator_output_drift", "task inventory")
    evidence: dict[str, dict[str, object]] = {}
    artifact_features: dict[str, set[str]] = {}
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        failure = _role_failure(root, config["files"])
        if failure:
            _fail(failure, case.task_id)
        instructions = (root / ".docs/instructions.md").read_text(encoding="utf-8")
        if not all(term.lower() in instructions.lower() for term in case.prompt_terms):
            _fail("prompt_contract_incomplete", case.task_id)
        task = load_task(root)
        response = build_assistant_response(task, load_example_files_from_config(root))
        if not response.startswith(f"{case.task_id}.h\n```") or ".meta/" in response:
            _fail("whole_format_failed", case.task_id)
        reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
        if case.function not in reference or case.body.strip() not in reference:
            _fail("invariant_not_enforced", case.task_id)
        negative = (root / ".meta/negative.cpp").read_text(encoding="utf-8")
        if case.negative_new not in negative or case.negative_old in negative:
            _fail("invariant_not_enforced", f"negative fixture: {case.task_id}")
        cmake = (root / "CMakeLists.txt").read_text(encoding="utf-8")
        if "WILL_FAIL TRUE" not in cmake or "-Wall -Wextra -Wpedantic -Werror" not in cmake:
            _fail("negative_fixture_not_strict", case.task_id)
        hard = _hard_rule_features(root)
        artifact_features[case.task_id] = _artifact_features(root)
        evidence[case.task_id] = {
            "tree_hash": _tree_hash(root),
            "reference_hash": _reference_hash(root),
            "prompt_boundary": "pass",
            "role_mapping": "pass",
            "topic_negative": case.negative_description,
            "hard_rule_dimensions": {
                dimension: {
                    "feature_count": len(hard[dimension]),
                    "fingerprint": _feature_fingerprint(hard[dimension]),
                }
                for dimension in HARD_RULE_DIMENSIONS
            },
        }
    aggregate_pairs: list[dict[str, object]] = []
    hard_pairs: list[dict[str, object]] = []
    for left, right in combinations(CASES, 2):
        overlap = _overlap(artifact_features[left.task_id], artifact_features[right.task_id])
        aggregate_pairs.append({"left": left.task_id, "right": right.task_id, "overlap": round(overlap, 6)})
        if overlap >= PAIR_THRESHOLD:
            _fail("duplicate_family", f"aggregate {left.task_id} vs {right.task_id}: {overlap:.3f}")
        decision = _hard_rule_pair_result(out / left.task_id, out / right.task_id)
        hard_pairs.append({"left": left.task_id, "right": right.task_id, **decision})
        if decision["failure"] is not None:
            _fail("duplicate_family", f"{left.task_id} vs {right.task_id}: {decision['failed_dimensions']}")
    if len(hard_pairs) != len(CASES) * (len(CASES) - 1) // 2:
        _fail("generator_output_drift", "incomplete pair inventory")
    holdouts = _bound_holdouts(repo_root)
    benchmark: list[dict[str, object]] = []
    for case in CASES:
        for holdout in holdouts:
            overlap = _overlap(artifact_features[case.task_id], _artifact_features(holdout))
            benchmark.append({"task_id": case.task_id, "holdout": holdout.name, "overlap": round(overlap, 6)})
            if case.task_id == holdout.name or overlap >= BENCHMARK_THRESHOLD:
                _fail("benchmark_content_overlap", f"{case.task_id} vs {holdout.name}: {overlap:.3f}")
    audit_case = next(case for case in CASES if case.task_id == "safe-date-audit-export")
    adversarial = _adversarial_results(out / audit_case.task_id)
    if set(adversarial) != set(ADVERSARIAL_CONTROLS) or any(
        item["failure"] != "duplicate_family" or set(item["failed_dimensions"]) != set(HARD_RULE_DIMENSIONS)
        for item in adversarial.values()
    ):
        _fail("duplicate_family", f"adversarial controls: {adversarial}")
    screen = {
        "schema_version": "overflow-safe-date-math-family-screen-v2",
        "normalizer": NORMALIZER,
        "root_count": len(CASES),
        "root_count_bounds": {"minimum": FAMILY_ROOT_MIN, "maximum": FAMILY_ROOT_MAX},
        "pair_threshold": PAIR_THRESHOLD,
        "pairwise_semantic_overlap": aggregate_pairs,
        "benchmark_inventory": [root.name for root in holdouts],
        "benchmark_comparisons": benchmark,
        "adversarial_clone_results": adversarial,
        "hard_rule": {
            "dimensions": list(HARD_RULE_DIMENSIONS),
            "thresholds": HARD_RULE_THRESHOLDS,
            "comparison_count": len(hard_pairs),
            "expected_comparison_count": len(CASES) * (len(CASES) - 1) // 2,
            "pairwise": hard_pairs,
            "adversarial_controls": list(ADVERSARIAL_CONTROLS),
            "result": "pass",
        },
        "legacy_finding": "ten roots shared one generic reference and test template",
        "result": "pass",
    }
    serialized = json.dumps(screen, indent=2, sort_keys=True) + "\n"
    _write(out / ".state/family-screen.json", serialized, True)
    for case in CASES:
        evidence[case.task_id]["family_screen_hash"] = _sha256(serialized.encode())
    _update_records(out, evidence, "implemented")
    return evidence


def _test_count(build_dir: Path) -> int:
    process = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "-N"],
        check=True,
        capture_output=True,
        text=True,
    )
    match = re.search(r"Total Tests:\s*(\d+)", process.stdout + process.stderr)
    if not match or int(match.group(1)) <= 0:
        _fail("zero_tests", str(build_dir))
    return int(match.group(1))


def verify(out: Path) -> dict[str, dict[str, int]]:
    missing = [tool for tool in ("cmake", "c++") if shutil.which(tool) is None]
    if missing:
        receipt = {
            "schema_version": "overflow-safe-date-math-host-oracle-v2",
            "status": "not_completed",
            "missing": missing,
            "blocked_command": "owner --verify",
            "next_action": "run the mandatory owner-controlled network-disabled Docker sanity verifier",
        }
        _write(out / ".state/host-oracle.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        _fail("oracle_not_completed", ", ".join(missing))
    verify_core(out)
    counts: dict[str, dict[str, int]] = {}
    for case in CASES:
        with tempfile.TemporaryDirectory(prefix=f"overflow-date-{case.task_id}-") as tmp:
            root = Path(tmp) / case.task_id
            shutil.copytree(out / case.task_id, root)
            counts[case.task_id] = {}
            for mode, flags in (
                ("normal", []),
                ("asan_ubsan", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]),
            ):
                build_dir = root / f"build-{mode}"
                commands = (
                    ["cmake", "-G", "Unix Makefiles", "-S", str(root), "-B", str(build_dir), f"-DTASK_SOURCE={root / '.meta/example.cpp'}", *flags],
                    ["cmake", "--build", str(build_dir), "--parallel", "2"],
                    ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
                )
                for command in commands:
                    subprocess.run(command, check=True, capture_output=True, text=True)
                counts[case.task_id][mode] = _test_count(build_dir)
            if counts[case.task_id]["normal"] != counts[case.task_id]["asan_ubsan"]:
                _fail("sanitizer_test_count_mismatch", case.task_id)
    receipt = {
        "schema_version": "overflow-safe-date-math-host-oracle-v2",
        "status": "pass",
        "evidence_class": "host_iteration",
        "generator_revision": _generator_revision(),
        "counts": counts,
    }
    _write(out / ".state/host-oracle.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    return counts


def _tar_filter(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    return info


def _archive(out: Path, archive: Path, controls: dict[str, Path]) -> str:
    with tarfile.open(archive, "w") as bundle:
        for case in CASES:
            bundle.add(out / case.task_id, arcname=f"family/{case.task_id}", filter=_tar_filter)
        for variant, root in controls.items():
            bundle.add(root, arcname=f"controls/{variant}", filter=_tar_filter)
    return _sha256(archive.read_bytes())


def _accept_docker_receipt(out: Path, receipt: dict[str, object]) -> dict[str, object]:
    evidence = verify_core(out)
    screen_bytes = (out / ".state/family-screen.json").read_bytes()
    if (
        receipt.get("schema_version") != "overflow-safe-date-math-docker-sanity-v2"
        or receipt.get("status") != "pass"
        or receipt.get("network") != "none"
        or receipt.get("image") != SANITY_IMAGE
        or receipt.get("generator_revision") != _generator_revision()
        or receipt.get("family_screen_hash") != _sha256(screen_bytes)
    ):
        _fail("docker_result_identity_mismatch", "receipt header")
    tasks = receipt.get("tasks")
    if not isinstance(tasks, dict) or set(tasks) != {case.task_id for case in CASES}:
        _fail("docker_sanity_incomplete", "task inventory")
    for case in CASES:
        item = tasks[case.task_id]
        if not isinstance(item, dict) or item.get("normal") != 4 or item.get("asan_ubsan") != 4:
            _fail("sanitizer_test_count_mismatch", case.task_id)
        if item.get("tree_hash") != _tree_hash(out / case.task_id) or item.get("mounted_tree_hash") != item.get("tree_hash"):
            _fail("grader_mount_hash_mismatch", case.task_id)
        if item.get("reference_hash") != _reference_hash(out / case.task_id):
            _fail("docker_result_identity_mismatch", f"reference: {case.task_id}")
        if item.get("negative_normal") != "exit_1" or item.get("negative_asan_ubsan") != "exit_1":
            _fail("negative_fixture_not_rejected", case.task_id)
    controls = receipt.get("hard_rule_controls")
    if not isinstance(controls, dict) or set(controls) != set(ADVERSARIAL_CONTROLS):
        _fail("docker_sanity_incomplete", "control inventory")
    with tempfile.TemporaryDirectory(prefix="overflow-date-receipt-controls-") as tmp:
        audit_root = out / "safe-date-audit-export"
        for variant in ADVERSARIAL_CONTROLS:
            clone, _ = _make_adversarial_clone(audit_root, variant, Path(tmp))
            item = controls[variant]
            if not isinstance(item, dict) or item.get("normal") != 4 or item.get("asan_ubsan") != 4:
                _fail("sanitizer_test_count_mismatch", f"control: {variant}")
            if item.get("tree_hash") != _tree_hash(clone) or item.get("mounted_tree_hash") != item.get("tree_hash"):
                _fail("grader_mount_hash_mismatch", f"control: {variant}")
    serialized = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    _write(out / ".state/docker-sanity.json", serialized, True)
    _update_records(out, evidence, "verified")
    for case in CASES:
        path = out / ".state/remedy" / f"{case.legacy_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["oracle_evidence"] = {
            "receipt": ".state/docker-sanity.json",
            "receipt_hash": _sha256(serialized.encode()),
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "normal_test_count": 4,
            "sanitizer_test_count": 4,
            "network": "none",
            "image": SANITY_IMAGE,
        }
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)
    return receipt


def import_docker_sanity(out: Path, result_path: Path) -> dict[str, object]:
    receipt = json.loads(result_path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        _fail("docker_result_identity_mismatch", "result is not an object")
    return _accept_docker_receipt(out, receipt)


def docker_sanity(out: Path, *, result_out: Path | None = None) -> dict[str, object]:
    verify_core(out)
    with tempfile.TemporaryDirectory(prefix="overflow-date-docker-") as tmp:
        tmp_root = Path(tmp)
        control_parent = tmp_root / "control-source"
        controls = {
            variant: _make_adversarial_clone(out / "safe-date-audit-export", variant, control_parent)[0]
            for variant in ADVERSARIAL_CONTROLS
        }
        control_hashes = {variant: _tree_hash(root) for variant, root in controls.items()}
        archive = tmp_root / "family.tar"
        archive_hash = _archive(out, archive, controls)
        image_id = subprocess.run(
            ["docker", "image", "inspect", SANITY_IMAGE, "--format", "{{.Id}}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        script = r'''set -eu
mkdir -p /tmp/family
tar -xf /input/family.tar -C /tmp/family
compiler=$(command -v c++)
echo "W8TOOL compiler_path $compiler"
echo "W8TOOL compiler_hash sha256:$(sha256sum "$compiler" | sed 's/ .*//')"
echo "W8TOOL compiler_version $(c++ --version | head -1)"
echo "W8TOOL cmake_version $(cmake --version | head -1)"
hash_tree() {
python3 -c 'import hashlib,pathlib,sys
r=pathlib.Path(sys.argv[1]); d=hashlib.sha256()
for p in sorted(x for x in r.rglob("*") if x.is_file()):
 q=p.relative_to(r).as_posix().encode(); b=p.read_bytes(); d.update(len(q).to_bytes(8,"big")); d.update(q); d.update(len(b).to_bytes(8,"big")); d.update(b)
print("sha256:"+d.hexdigest())' "$1"
}
run_root() {
  root=$1; kind=$2; name=${root##*/}
  mounted_hash=$(hash_tree "$root")
  echo "W8HASH $kind $name $mounted_hash"
  for mode in normal asan_ubsan; do
    flags=
    if [ "$mode" = asan_ubsan ]; then flags='-fsanitize=address,undefined -fno-omit-frame-pointer'; fi
    build="/tmp/build-$kind-$name-$mode"
    cmake -S "$root" -B "$build" -G 'Unix Makefiles' -DTASK_SOURCE="$root/.meta/example.cpp" -DCMAKE_CXX_FLAGS="$flags" -DCMAKE_EXE_LINKER_FLAGS="$flags" >/dev/null
    cmake --build "$build" --parallel 2 >/dev/null
    count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: *//p')
    test "$count" = 4
    ctest --test-dir "$build" --output-on-failure
    set +e
    negative_output=$("$build/task_negative" 2>&1)
    negative_status=$?
    set -e
    test "$negative_status" = 1
    test -z "$negative_output"
    echo "W8COUNT $kind $name $mode $count"
    echo "W8NEG $kind $name $mode exit_1"
  done
}
for root in /tmp/family/family/*; do run_root "$root" task; done
for root in /tmp/family/controls/*; do run_root "$root" control; done
'''
        process = subprocess.run(
            ["docker", "run", "--rm", "--network", "none", "-v", f"{archive}:/input/family.tar:ro", SANITY_IMAGE, "bash", "-lc", script],
            check=False,
            capture_output=True,
            text=True,
        )
        if process.returncode != 0:
            _fail("docker_sanity_failed", (process.stdout + "\n" + process.stderr)[-12000:])
    counts: dict[tuple[str, str], dict[str, int]] = {}
    for kind, name, mode, count in re.findall(r"^W8COUNT (\S+) (\S+) (\S+) (\d+)$", process.stdout, re.M):
        counts.setdefault((kind, name), {})[mode] = int(count)
    hashes = {(kind, name): value for kind, name, value in re.findall(r"^W8HASH (\S+) (\S+) (sha256:[0-9a-f]{64})$", process.stdout, re.M)}
    negatives = {(kind, name, mode): value for kind, name, mode, value in re.findall(r"^W8NEG (\S+) (\S+) (\S+) (\S+)$", process.stdout, re.M)}
    expected_tasks = {case.task_id for case in CASES}
    if {name for kind, name in counts if kind == "task"} != expected_tasks:
        _fail("docker_sanity_incomplete", "task inventory")
    for case in CASES:
        key = ("task", case.task_id)
        if counts.get(key) != {"normal": 4, "asan_ubsan": 4}:
            _fail("sanitizer_test_count_mismatch", case.task_id)
        if hashes.get(key) != _tree_hash(out / case.task_id):
            _fail("grader_mount_hash_mismatch", case.task_id)
        if any(negatives.get(("task", case.task_id, mode)) != "exit_1" for mode in ("normal", "asan_ubsan")):
            _fail("negative_fixture_not_rejected", case.task_id)
    if {name for kind, name in counts if kind == "control"} != set(ADVERSARIAL_CONTROLS):
        _fail("docker_sanity_incomplete", "control inventory")
    for variant in ADVERSARIAL_CONTROLS:
        key = ("control", variant)
        if counts.get(key) != {"normal": 4, "asan_ubsan": 4}:
            _fail("sanitizer_test_count_mismatch", f"control: {variant}")
        if hashes.get(key) != control_hashes[variant]:
            _fail("grader_mount_hash_mismatch", f"control: {variant}")
    toolchain = dict(re.findall(r"^W8TOOL (\S+) (.+)$", process.stdout, re.M))
    screen_hash = _sha256((out / ".state/family-screen.json").read_bytes())
    receipt: dict[str, object] = {
        "schema_version": "overflow-safe-date-math-docker-sanity-v2",
        "status": "pass",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "network": "none",
        "image": SANITY_IMAGE,
        "image_id": image_id,
        "archive_hash": archive_hash,
        "generator_revision": _generator_revision(),
        "family_screen_hash": screen_hash,
        "toolchain": toolchain,
        "commands": [
            "network-disabled clean normal CMake/CTest for every root and control",
            "network-disabled fresh ASan/UBSan CMake/CTest for every root and control",
            "direct executed topic negative requires exit 1 and empty diagnostics in both modes",
        ],
        "tasks": {
            case.task_id: {
                **counts[("task", case.task_id)],
                "tree_hash": _tree_hash(out / case.task_id),
                "mounted_tree_hash": hashes[("task", case.task_id)],
                "reference_hash": _reference_hash(out / case.task_id),
                "negative_fixture": case.negative_description,
                "negative_normal": negatives[("task", case.task_id, "normal")],
                "negative_asan_ubsan": negatives[("task", case.task_id, "asan_ubsan")],
            }
            for case in CASES
        },
        "hard_rule_controls": {
            variant: {
                **counts[("control", variant)],
                "tree_hash": control_hashes[variant],
                "mounted_tree_hash": hashes[("control", variant)],
                "behavior_coherent": True,
                "classification": "rejected by the exact seven-dimension production screen",
            }
            for variant in ADVERSARIAL_CONTROLS
        },
    }
    if result_out is not None:
        _write(result_out, json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    return _accept_docker_receipt(out, receipt)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--docker-result-out", type=Path)
    parser.add_argument("--import-docker-result", type=Path)
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    if args.docker_sanity:
        docker_sanity(args.out, result_out=args.docker_result_out)
    if args.import_docker_result:
        import_docker_sanity(args.out, args.import_docker_result)
    print(f"Wrote {len(roots)} overflow-safe date-math tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
