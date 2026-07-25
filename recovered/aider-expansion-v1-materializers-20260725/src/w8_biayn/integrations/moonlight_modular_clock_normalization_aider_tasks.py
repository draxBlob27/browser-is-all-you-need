"""Create and verify 60 modular-clock-normalization expansion tasks."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from functools import lru_cache
from itertools import combinations
from pathlib import Path, PurePosixPath
from typing import Iterable, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_modular_clock_normalization_cases import (
    CASES as NORMALIZATION_CASES,
    ClockCase,
)
from w8_biayn.integrations.moonlight_modular_clock_offset_cases import (
    CASES as OFFSET_CASES,
)
from w8_biayn.integrations.moonlight_modular_clock_sequence_cases import (
    CASES as SEQUENCE_CASES,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
DEFAULT_OUT = EXPANSION_ROOT / "time-date/modular-clock-normalization"
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-clock-tasks/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_MODULAR_CLOCK_NORMALIZATION_CURRICULUM.md"
)
COUNT_PLAN = Path("docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md")
GENERATOR_PATH = Path(
    "src/w8_biayn/integrations/"
    "moonlight_modular_clock_normalization_aider_tasks.py"
)
CASE_PATHS = (
    Path("src/w8_biayn/integrations/moonlight_modular_clock_normalization_cases.py"),
    Path("src/w8_biayn/integrations/moonlight_modular_clock_sequence_cases.py"),
    Path("src/w8_biayn/integrations/moonlight_modular_clock_offset_cases.py"),
)
FOCUSED_TEST = Path("tests/test_moonlight_modular_clock_normalization_aider_tasks.py")
SELECTED_DESIGN_PROMPT = Path("docs/aider-tasks-spec/prompts/generate-family-spec.md")
SELECTED_IMPLEMENT_PROMPT = Path("docs/aider-tasks-spec/prompts/implement-family-for-sft.md")
FAMILY_ID = "aider-expansion-modular-clock-normalization-v1"
EXPECTED_ROOTS = 60
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
DEFAULT_HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
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
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_or_selection_rules",
    "invalid_and_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
DIMENSION_LIMITS = {name: 0.84 for name in HARD_RULE_DIMENSIONS}
ADVERSARIAL_CONTROLS = (
    "domain-identifier-renamed-clone",
    "constants-policy-only-clone",
    "opposite-end-selection-clone",
)
REPLACED_CANDIDATES = (
    {
        "task_id": "mcn-angular-dms-normalizer",
        "disposition": "rejected_semantic_duplicate",
        "duplicate_of": "mcn-signed-hms-normalizer",
        "replaced_by": "mcn-weighted-phase-histogram",
        "audit_finding": "cycle-02/mcn-signed-hms-normalizer__mcn-angular-dms-normalizer/domain-renamed-semantic-duplicate",
    },
)
SEMANTIC_NORMALIZER = "mcn-v2-artifact-only-identifier-preserving-weighted-6gram"
CONTAMINATION_NORMALIZER = "mcn-v2-max(identifier-preserving,identifier-neutral)-6gram"
CASES: tuple[ClockCase, ...] = (
    *NORMALIZATION_CASES,
    *SEQUENCE_CASES,
    *OFFSET_CASES,
)


if len(CASES) != EXPECTED_ROOTS or len({case.task_id for case in CASES}) != EXPECTED_ROOTS:
    raise RuntimeError("hard_rule_root_count: case inventory is not exactly 60 unique IDs")


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _sha_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _tree_hash(root: Path, *, include_state: bool = False) -> str:
    if not root.is_dir():
        return "not_available"
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if not include_state and ".state" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _owner_hash() -> str:
    digest = hashlib.sha256()
    for relative in (GENERATOR_PATH, *CASE_PATHS):
        digest.update(relative.as_posix().encode())
        digest.update(b"\0")
        digest.update((REPO_ROOT / relative).read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _validate_output(out: Path, *, test_mode: bool) -> None:
    resolved = out.resolve()
    legacy = (REPO_ROOT / LEGACY_ROOT).resolve()
    reverify = (REPO_ROOT / REVERIFY_ROOT).resolve()
    expansion = (REPO_ROOT / EXPANSION_ROOT).resolve()
    expected = (REPO_ROOT / DEFAULT_OUT).resolve()
    if resolved == legacy or legacy in resolved.parents:
        _fail("legacy_root_immutable", str(out))
    if resolved == reverify or reverify in resolved.parents:
        _fail("reverify_root_immutable", str(out))
    if not test_mode and resolved != expected:
        _fail("expansion_output_required", f"expected {DEFAULT_OUT}, got {out}")
    if not test_mode and expansion not in resolved.parents:
        _fail("expansion_output_required", str(out))
    for parent in (resolved, *resolved.parents):
        if parent.exists() and parent.is_symlink():
            _fail("unsafe_path", f"symlink output component: {parent}")


def _task_roots(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    return tuple(
        sorted(
            config.parent.parent
            for config in root.rglob(".meta/config.json")
            if ".state" not in config.parts
        )
    )


def _inventory(root: Path) -> dict[str, object]:
    records = None
    for attempt in range(10):
        try:
            roots = _task_roots(root)
            records = [
                {
                    "task_id": task.name,
                    "relative_root": task.relative_to(root).as_posix(),
                    "tree_hash": _tree_hash(task),
                }
                for task in roots
            ]
            break
        except FileNotFoundError:
            if attempt == 9:
                _fail("source_inventory_unstable", root.as_posix())
            time.sleep(0.1)
    assert records is not None
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return {
        "root": root.as_posix(),
        "root_count": len(records),
        "records": records,
        "inventory_hash": _sha_bytes(payload),
    }


def _header(case: ClockCase) -> str:
    return (
        "#pragma once\n"
        "#include <optional>\n#include <string>\n#include <vector>\n"
        "namespace curriculum {\n" + case.api + "\n}  // namespace curriculum\n"
    )


_SOURCE_PRELUDE = r'''#include "task.h"
#include <algorithm>
#include <array>
#include <climits>
#include <functional>
#include <limits>
#include <map>
#include <numeric>
#include <queue>
#include <set>
#include <tuple>
#include <utility>
namespace {
[[maybe_unused]] long long euclidean_mod(long long value,long long modulus){
  long long residue=value%modulus;
  return residue<0?residue+modulus:residue;
}
[[maybe_unused]] long long add_mod_nonnegative(long long a,long long b,long long m){
  return a>=m-b?a-(m-b):a+b;
}
[[maybe_unused]] long long sub_mod_nonnegative(long long a,long long b,long long m){
  return a>=b?a-b:m-(b-a);
}
[[maybe_unused]] long long forward_distance(long long from,long long to,long long m){
  return sub_mod_nonnegative(to,from,m);
}
[[maybe_unused]] long long mul_mod_nonnegative(long long a,long long b,long long m){
  long long out=0;
  while(b){if(b&1)out=add_mod_nonnegative(out,a,m);b>>=1;if(b)a=add_mod_nonnegative(a,a,m);}
  return out;
}
[[maybe_unused]] std::optional<long long> inverse_mod_coprime(long long a,long long m){
  if(m<=0)return std::nullopt;
  if(m==1)return 0;
  a=euclidean_mod(a,m);
  long long r0=m,r1=a,t0=0,t1=1;
  while(r1){
    long long q=r0/r1,r2=r0%r1;
    long long product=mul_mod_nonnegative(q%m,t1,m);
    long long t2=sub_mod_nonnegative(t0,product,m);
    r0=r1;r1=r2;t0=t1;t1=t2;
  }
  return r0==1?std::optional<long long>{t0}:std::nullopt;
}
[[maybe_unused]] bool mul_div_nonnegative(long long a,long long b,long long d,long long* q,long long* r){
  if(a<0||b<0||d<=0)return false;
  long long aq=0,ar=b%d,whole=b/d,oq=0,orr=0;
  if(__builtin_mul_overflow(a,whole,&oq))return false;
  unsigned long long bits=static_cast<unsigned long long>(a);
  while(bits){
    if(bits&1ULL){if(__builtin_add_overflow(oq,aq,&oq))return false;if(orr>=d-ar){orr-=d-ar;if(__builtin_add_overflow(oq,1LL,&oq))return false;}else orr+=ar;}
    bits>>=1ULL;
    if(bits){if(__builtin_add_overflow(aq,aq,&aq))return false;if(ar>=d-ar){ar-=d-ar;if(__builtin_add_overflow(aq,1LL,&aq))return false;}else ar+=ar;}
  }
  *q=oq;*r=orr;return true;
}
}  // namespace
namespace curriculum {
'''


def _reference(case: ClockCase) -> str:
    return _SOURCE_PRELUDE + case.definition + "\n}  // namespace curriculum\n"


def _starter(case: ClockCase) -> str:
    return '#include "task.h"\nnamespace curriculum {\n' + case.starter + "\n}  // namespace curriculum\n"


def _test_source(case: ClockCase, body: str) -> str:
    return (
        '#include "task.h"\n#include <climits>\n#include <string>\n#include <vector>\n'
        "int main(){int failures=0;auto check=[&](bool ok){if(!ok)++failures;};"
        "using namespace curriculum;" + body + "return failures?1:0;}\n"
    )


def _negative(case: ClockCase) -> str:
    source = _reference(case)
    if source.count(case.negative_old) != 1:
        _fail("invariant_not_enforced", f"negative mutation drift: {case.task_id}")
    changed = source.replace(case.negative_old, case.negative_new, 1)
    if changed == source:
        _fail("invariant_not_enforced", f"negative is no-op: {case.task_id}")
    return changed


def _example_block(case: ClockCase) -> str:
    lines: list[str] = []
    for statement in case.visible.split(";"):
        statement = statement.strip()
        if not statement:
            continue
        if statement.startswith("check(") and statement.endswith(")"):
            lines.append(f"// expected: {statement[6:-1]}")
        else:
            lines.append(statement + ";")
    return "## Example\n\n```cpp\n" + "\n".join(lines) + "\n```\n"


def _instructions(case: ClockCase) -> str:
    return f"""# Instructions

Implement `{case.class_name}` using the exact C++17 declaration in the editable
header.

The operation is {case.mechanism}. Boundary and invalid-input contract: {case.boundary}. Invalid input returns the
declared empty/invalid result and must not expose partial mutation unless the
public result explicitly contains a valid-prefix diagnostic. Empty,
duplicate, absent, ordering, tie, and overflow behavior follow the declaration
and this rule. All arithmetic is deterministic and offline. Do not read host
time, locale, a time-zone database, files, or the network.

{_example_block(case)}
Implement the mechanism directly from the inputs on every call. A
general-purpose clock value type, a platform date/time facility, or a
precomputed table of answers cannot express the documented boundary and
overflow behavior, and wrapping an existing implementation under a new name
computes nothing. Return exactly the documented owned values in deterministic
order.
"""


def _cmake(*, control: bool = False) -> str:
    negative = "" if control else r'''
add_executable(task_negative "${NEGATIVE_SOURCE}" .meta/task_negative_test.cpp)
target_include_directories(task_negative PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(task_negative PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
add_test(NAME negative_fixture COMMAND task_negative)
set_tests_properties(negative_fixture PROPERTIES WILL_FAIL TRUE)
'''
    return f'''cmake_minimum_required(VERSION 3.16)
project(modular_clock_normalization LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
enable_testing()
set(TASK_SOURCE "${{CMAKE_CURRENT_SOURCE_DIR}}/task.cpp" CACHE FILEPATH "Implementation")
set(NEGATIVE_SOURCE "${{CMAKE_CURRENT_SOURCE_DIR}}/.meta/negative_false_substitute.cpp" CACHE FILEPATH "Negative implementation")
add_executable(task_visible "${{TASK_SOURCE}}" task_visible_test.cpp)
add_executable(task_hidden "${{TASK_SOURCE}}" .meta/task_hidden_test.cpp)
foreach(target task_visible task_hidden)
  target_include_directories(${{target}} PRIVATE "${{CMAKE_CURRENT_SOURCE_DIR}}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${{target}} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
{negative}'''


def _contract_markdown(case: ClockCase) -> str:
    return f"""# Creation contract: `{case.task_id}`

## Identity

New-root lineage; family `{FAMILY_ID}`; task-spec revision 1; repository-owned
clean-room provenance; no parent or replacement.

## Objective

Implement {case.mechanism}.

## Public API

`namespace curriculum {{ {case.api} }}` Editable order is `{case.task_id}.h`,
then `{case.task_id}.cpp`; all returned state is owned.

## Behavior table

{case.boundary}. Normal input returns the declaration's result. Invalid input
returns the declaration's invalid/empty result. Duplicate, absent, empty,
mutation, ordering, tie, and overflow behavior are governed by that rule and
the public declaration; no private rule may contradict the prompt.

## Implementation invariant

Required mechanism: {case.mechanism}. Forbidden substitutes are generic clock
objects, platform time/date facilities, precomputed cases, other retained
roots, and the named false substitute: {case.negative_reason}.

## Starter and reference

The header is complete; the task-named source is an incomplete coherent stub.
Private example files are complete independent replacements. The false
substitute compiles under the same strict flags and is rejected by executed
tests.

## Tests

Visible and private deterministic tests cover the published normal, invalid,
empty, signed, wrap, equality/tie, order, and overflow rules applicable to the
API. The private oracle is value-based and does not enter the prompt.

## Files and metadata

Two task-named editable files; one visible test; private hidden/negative tests;
two references; role-correct config, provenance, CMake, and receipts.

## Build/oracle

C++17, `-Wall -Wextra -Wpedantic -Werror`, explicit `Unix Makefiles`, pinned
network-disabled `{SANITY_IMAGE}`, clean normal and fresh ASan/UBSan builds,
three equal positive CTest entries including an expected-failing compiled
negative.

## Family/contamination

Compare all 1770 retained pairs in seven dimensions and all available existing
and official holdout contracts using `{SEMANTIC_NORMALIZER}`. Any collision is
reject/replace, never rename.

## Optional dataset handoff

`not_requested`.

## Acceptance

Owner regeneration, prompt/reference boundary, focused independent assertions,
normal/sanitizer/negative Docker evidence, coherent clone-control rejection,
lineage/holdout screens, and fresh independent audit must all pass.
"""


def _case_files(case: ClockCase) -> dict[str, str]:
    header = _header(case)
    config = {
        "authors": ["w8-biayn"],
        "blurb": f"Implement {case.mechanism}.",
        "files": {
            "solution": ["task.h", "task.cpp"],
            "test": ["task_visible_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "schema_version": "aider-cleanroom-provenance-v1",
        "family_id": FAMILY_ID,
        "task_id": case.task_id,
        "lineage": {"relation": "new-root", "parent": None},
        "curriculum": CURRICULUM.as_posix(),
        "count_plan": COUNT_PLAN.as_posix(),
        "selected_prompts": [
            SELECTED_DESIGN_PROMPT.as_posix(),
            SELECTED_IMPLEMENT_PROMPT.as_posix(),
        ],
        "origin": "independently authored repository clean-room task",
        "license_result": "repository-authored/pass",
        "primary_core_objective": "achieved",
        "semantic_anchors": {
            dimension: _sha_bytes(
                "\0".join(
                    (
                        dimension,
                        case.class_name,
                        case.api,
                        case.mechanism,
                        case.boundary,
                        case.negative_reason,
                    )
                ).encode("utf-8")
            )
            for dimension in HARD_RULE_DIMENSIONS
        },
        "dataset_handoff": "not_requested",
        "status": "local candidate; creator audit loop pending",
    }
    return {
        ".docs/instructions.md": _instructions(case),
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": (
            f'[visible]\ndescription = "published behavior for {case.title}"\n\n'
            f'[hidden]\ndescription = "invalid, boundary, tie/order, overflow, and {case.negative_reason} rejection"\n'
        ),
        "task.h": header,
        "task.cpp": _starter(case),
        ".meta/example.h": header,
        ".meta/example.cpp": _reference(case),
        ".meta/negative_false_substitute.cpp": _negative(case),
        "task_visible_test.cpp": _test_source(case, case.visible),
        ".meta/task_hidden_test.cpp": _test_source(case, case.hidden),
        # Keep the two oracle programs in separate scopes: independently
        # authored visible/hidden snippets may intentionally reuse local names.
        ".meta/task_negative_test.cpp": _test_source(
            case, "{" + case.visible + "}{" + case.hidden + "}"
        ),
        "CMakeLists.txt": _cmake(),
    }


def _reserve_ids(out: Path) -> dict[str, object]:
    inventories = {
        "legacy": _inventory(LEGACY_ROOT),
        "reverify": _inventory(REVERIFY_ROOT),
        "expansion": _inventory(EXPANSION_ROOT),
    }
    wanted = {case.task_id for case in CASES}
    for name, inventory in inventories.items():
        collisions = {
            row["task_id"]
            for row in inventory["records"]
            if row["task_id"] in wanted and not (
                name == "expansion"
                and row["relative_root"].startswith("time-date/modular-clock-normalization/")
            )
        }
        if collisions:
            _fail("duplicate_task", f"{name}: {sorted(collisions)}")
    return inventories


def _remove_owned_roots(out: Path) -> None:
    if not out.exists():
        return
    for child in out.iterdir():
        if not child.is_dir() or child.name == ".state":
            continue
        provenance = child / ".meta/provenance.json"
        if not provenance.is_file():
            _fail("generator_output_drift", f"foreign root without provenance: {child}")
        record = json.loads(provenance.read_text(encoding="utf-8"))
        if record.get("family_id") != FAMILY_ID:
            _fail("generator_output_drift", f"foreign root: {child}")
        shutil.rmtree(child)
    state = out / ".state"
    for relative in (
        "materialization-manifest.json",
        "host-verification.json",
        "creator-preflight.json",
        "hard-rule-screen.json",
        "independent-audit.json",
        "fresh-reaudit.json",
    ):
        (state / relative).unlink(missing_ok=True)


def _write_control(out: Path, name: str, case: ClockCase, replacements: Iterable[tuple[str, str]], force: bool) -> dict[str, object]:
    files = _case_files(case)
    selected = {
        "task.h": files["task.h"],
        "candidate.cpp": files[".meta/example.cpp"],
        ".docs/instructions.md": files[".docs/instructions.md"],
        "task_visible_test.cpp": files["task_visible_test.cpp"],
        ".meta/task_hidden_test.cpp": files[".meta/task_hidden_test.cpp"],
        ".meta/negative_false_substitute.cpp": files[".meta/negative_false_substitute.cpp"],
        ".meta/provenance.json": files[".meta/provenance.json"],
        "CMakeLists.txt": _cmake(control=True),
    }
    changed: list[str] = []
    for relative, content in tuple(selected.items()):
        updated = content
        for old, new in replacements:
            updated = updated.replace(old, new)
        if updated != content:
            changed.append(relative)
        selected[relative] = updated
    if not changed:
        _fail("adversarial_control_invalid", f"no-op: {name}")
    provenance = json.loads(selected[".meta/provenance.json"])
    provenance["task_id"] = name
    provenance["lineage"] = {"relation": "new-root", "parent": None}
    provenance["origin"] = "independently introduced adversarial new-root candidate"
    provenance["semantic_anchors"] = {
        dimension: _sha_bytes(
            "\0".join((name, dimension, selected["task.h"], selected["candidate.cpp"])).encode()
        )
        for dimension in HARD_RULE_DIMENSIONS
    }
    selected[".meta/provenance.json"] = json.dumps(provenance, indent=2, sort_keys=True) + "\n"
    if ".meta/provenance.json" not in changed:
        changed.append(".meta/provenance.json")
    root = out / ".state/hard-rule-controls" / name
    for relative, content in selected.items():
        _write(root / relative, content, force)
    return {
        "base_task": case.task_id,
        "changed_files": sorted(changed),
        "tree_hash": _tree_hash(root, include_state=True),
        "expected_compile": "pass",
        "expected_tests": "pass",
        "expected_family_screen": "duplicate_family_at_least_one_dimension",
    }


def _write_controls(out: Path, force: bool) -> dict[str, object]:
    rename_case = CASES[0]
    policy_case = next(c for c in CASES if c.task_id == "mcn-balanced-phase-residue")
    endpoint_case = next(c for c in CASES if c.task_id == "mcn-nearest-free-phase")
    controls = {
        ADVERSARIAL_CONTROLS[0]: _write_control(
            out,
            ADVERSARIAL_CONTROLS[0],
            rename_case,
            (("ResidueLedger", "OrbitLedger"), ("residue", "position"), ("Residue", "Position")),
            force,
        ),
        ADVERSARIAL_CONTROLS[1]: _write_control(
            out,
            ADVERSARIAL_CONTROLS[1],
            policy_case,
            (
                ("tie==Tie::negative", "tie==Tie::positive"),
                ("==-5", "==5"),
                ("Tie::positive)==5", "Tie::positive)==-5"),
                ("negative half-period", "positive half-period"),
            ),
            force,
        ),
        ADVERSARIAL_CONTROLS[2]: _write_control(
            out,
            ADVERSARIAL_CONTROLS[2],
            endpoint_case,
            (
                ("tie==Tie::counterclockwise?ccw:cw", "tie==Tie::clockwise?ccw:cw"),
                ("tie==Tie::counterclockwise?cw:ccw", "tie==Tie::clockwise?cw:ccw"),
                ("phase==8", "phase==2"),
                ("phase==1", "phase==4"),
            ),
            force,
        ),
    }
    _write(
        out / ".state/hard-rule-controls/manifest.json",
        json.dumps({"schema_version": "mcn-controls-v1", "controls": controls}, indent=2, sort_keys=True) + "\n",
        True,
    )
    return controls


_CPP_KEYWORDS = frozenset(
    "alignas alignof and and_eq asm auto bitand bitor bool break case catch char "
    "class compl const constexpr continue decltype default delete do double "
    "dynamic_cast else enum explicit export extern false float for friend goto if "
    "inline int long mutable namespace new noexcept not not_eq nullptr operator or "
    "or_eq private protected public register reinterpret_cast return short signed "
    "sizeof static static_assert static_cast struct switch template this thread_local "
    "throw true try typedef typeid typename union unsigned using virtual void volatile "
    "wchar_t while xor xor_eq".split()
)


def _normalized_tokens(text: str, *, neutral_identifiers: bool = False) -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.M | re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " literal ", text)
    tokens = re.findall(
        r"[A-Za-z_][A-Za-z0-9_]*|==|!=|<=|>=|&&|\|\||[-+*/%<>{}()[\];,.?:=!&|]",
        text,
    )
    allowed = {
        "std", "vector", "optional", "string", "size_t", "sort", "stable_sort",
        "min", "max", "gcd", "map", "set", "queue", "pair", "array",
    }
    out: list[str] = []
    for token in tokens:
        if token in {"begin", "rbegin", "end", "rend", "front", "back", "lower", "upper"}:
            out.append("endpoint")
        elif neutral_identifiers and re.match(r"[A-Za-z_]", token) and token not in _CPP_KEYWORDS and token not in allowed:
            out.append("identifier")
        else:
            out.append(token)
    return tuple(out)


@lru_cache(maxsize=None)
def _token_code(token: str) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode(), digest_size=8).digest(), "big")


def _ngrams(tokens: tuple[str, ...], width: int = 6) -> set[int]:
    if len(tokens) < width:
        return {_token_code("\0".join(tokens))} if tokens else set()
    result: set[int] = set()
    mask = (1 << 64) - 1
    for index in range(len(tokens) - width + 1):
        value = 0xCBF29CE484222325
        for token in tokens[index : index + width]:
            value ^= _token_code(token)
            value = (value * 0x100000001B3) & mask
        result.add(value)
    return result


def _ngram_counts(tokens: tuple[str, ...], width: int = 6) -> Counter[int]:
    if len(tokens) < width:
        return Counter({_token_code("\0".join(tokens)): 1}) if tokens else Counter()
    result: Counter[int] = Counter()
    mask = (1 << 64) - 1
    for index in range(len(tokens) - width + 1):
        value = 0xCBF29CE484222325
        for token in tokens[index : index + width]:
            value ^= _token_code(token)
            value = (value * 0x100000001B3) & mask
        result[value] += 1
    return result


def _similarity(left: str, right: str) -> float:
    a = _ngram_counts(_normalized_tokens(left))
    b = _ngram_counts(_normalized_tokens(right))
    if not a or not b:
        return 0.0
    keys = a.keys() | b.keys()
    return sum(min(a[key], b[key]) for key in keys) / sum(max(a[key], b[key]) for key in keys)


def _set_similarity(
    left: set[int], right: set[int]
) -> float:
    return 0.0 if not left or not right else len(left & right) / len(left | right)


def _strip_reference_scaffold(content: str) -> str:
    marker = "namespace curriculum {\n"
    return content.split(marker, 1)[1] if marker in content else content


def _artifact_dimensions(root: Path, *, control: bool = False) -> dict[str, str]:
    header = root / ("task.h" if control else f"{root.name}.h")
    reference = root / ("candidate.cpp" if control else ".meta/example.cpp")
    paths = {
        "header": header,
        "reference": reference,
        "instructions": root / ".docs/instructions.md",
        "visible": root / "task_visible_test.cpp",
        "hidden": root / ".meta/task_hidden_test.cpp",
        "negative": root / ".meta/negative_false_substitute.cpp",
        "provenance": root / ".meta/provenance.json",
    }
    for role, path in paths.items():
        if not path.is_file():
            _fail("hard_rule_evidence_incomplete", f"{root}: missing {role}")
    data = {key: path.read_text(encoding="utf-8") for key, path in paths.items()}
    data["reference"] = _strip_reference_scaffold(data["reference"])
    data["negative"] = _strip_reference_scaffold(data["negative"])
    provenance = json.loads(data["provenance"])
    anchors = provenance.get("semantic_anchors", {})
    if set(anchors) != set(HARD_RULE_DIMENSIONS):
        _fail("hard_rule_evidence_incomplete", f"{root}: semantic anchors")
    material = {
        "public_api": data["header"],
        "owned_state_or_algorithm": data["reference"],
        "mutation_or_selection_rules": data["instructions"] + data["reference"],
        "invalid_and_boundary_behavior": data["instructions"] + data["hidden"],
        "reference_control_flow": data["reference"],
        "deterministic_oracle": data["visible"] + data["hidden"],
        "topic_specific_negative_fixture": data["negative"] + data["hidden"],
    }
    return material


def _pair_decision(left_id: str, right_id: str, left: dict[str, str], right: dict[str, str]) -> dict[str, object]:
    dimensions = {}
    failed = []
    for dimension in HARD_RULE_DIMENSIONS:
        score = _similarity(left[dimension], right[dimension])
        distinct = score < DIMENSION_LIMITS[dimension]
        dimensions[dimension] = {
            "similarity": score,
            "limit": DIMENSION_LIMITS[dimension],
            "materially_distinct": distinct,
        }
        if not distinct:
            failed.append(dimension)
    return {
        "left": left_id,
        "right": right_id,
        "dimensions": dimensions,
        "failed_dimensions": failed,
        "materially_distinct_in_all_dimensions": not failed,
    }


def _validate_prompt(case: ClockCase, root: Path) -> dict[str, str]:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    expected = [f"{case.task_id}.h", f"{case.task_id}.cpp"]
    if config.get("files", {}).get("solution") != expected:
        _fail("prompt_contract_incomplete", f"solution order: {case.task_id}")
    roles = sum((config["files"][name] for name in ("solution", "test", "example")), [])
    if len(roles) != len(set(roles)):
        _fail("unsafe_path", f"duplicate roles: {case.task_id}")
    for relative in roles:
        path = PurePosixPath(relative)
        if path.is_absolute() or ".." in path.parts or not (root / relative).is_file():
            _fail("unsafe_path", f"{case.task_id}: {relative}")
    task = load_task(root)
    prompt = build_prompt(task)
    for private in (
        "example.cpp", "task_hidden_test", "negative_false_substitute",
        "provenance.json", "CMakeLists", "tests.toml", "creation contract",
    ):
        if private in prompt:
            _fail("prompt_contract_incomplete", f"{case.task_id}: exposed {private}")
    for visible in expected + [case.class_name]:
        if visible not in prompt:
            _fail("prompt_contract_incomplete", f"{case.task_id}: missing {visible}")
    answer = build_assistant_response(task, load_example_files_from_config(root))
    if not answer.startswith(expected[0] + "\n```") or expected[1] + "\n```" not in answer:
        _fail("target_reference_mismatch", case.task_id)
    return {"prompt_hash": _sha_bytes(prompt.encode()), "answer_hash": _sha_bytes(answer.encode())}


def _cross_tree_semantic_screen(out: Path, inventories: dict[str, object]) -> dict[str, object]:
    def frozen_roots(name: str, base: Path) -> tuple[Path, ...]:
        return tuple(base / row["relative_root"] for row in inventories[name]["records"])

    legacy_roots = frozen_roots("legacy", LEGACY_ROOT)
    reverify_roots = frozen_roots("reverify", REVERIFY_ROOT)
    subject_prefix = DEFAULT_OUT.relative_to(EXPANSION_ROOT).as_posix() + "/"
    expansion_records = tuple(
        row
        for row in inventories["expansion"]["records"]
        if not row["relative_root"].startswith(subject_prefix)
    )
    expansion_roots = tuple(EXPANSION_ROOT / row["relative_root"] for row in expansion_records)
    existing_roots = (
        *legacy_roots,
        *reverify_roots,
        *expansion_roots,
    )
    expected_hashes = {
        str(base / row["relative_root"]): row["tree_hash"]
        for name, base in (
            ("legacy", LEGACY_ROOT),
            ("reverify", REVERIFY_ROOT),
            ("expansion", EXPANSION_ROOT),
        )
        for row in inventories[name]["records"]
        if name != "expansion" or not row["relative_root"].startswith(subject_prefix)
    }
    candidates = {
        case.task_id: tuple(
            _ngrams(
                _normalized_tokens(
                    "\n".join(_artifact_dimensions(out / case.task_id).values()),
                    neutral_identifiers=neutral,
                )
            )
            for neutral in (False, True)
        )
        for case in CASES
    }
    strongest = {"similarity": 0.0, "candidate": None, "existing": None}
    comparison_count = 0
    for root in existing_roots:
        if _tree_hash(root) != expected_hashes[str(root)]:
            _fail("source_inventory_stale", root.as_posix())
        chunks = []
        for relative in (
            ".docs/introduction.md", ".docs/instructions.md", ".meta/example.cpp",
            "task_visible_test.cpp", ".meta/task_hidden_test.cpp",
        ):
            path = root / relative
            if path.is_file() and path.stat().st_size < 500_000:
                chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
        for header in root.glob("*.h"):
            chunks.append(header.read_text(encoding="utf-8", errors="ignore"))
        if chunks:
            joined = "\n".join(chunks)
            material = tuple(
                _ngrams(_normalized_tokens(joined, neutral_identifiers=neutral))
                for neutral in (False, True)
            )
            path = root.as_posix()
            for task_id, candidate in candidates.items():
                score = max(
                    _set_similarity(left, right)
                    for left, right in zip(candidate, material)
                )
                comparison_count += 1
                if score > strongest["similarity"]:
                    strongest = {"similarity": score, "candidate": task_id, "existing": path}
                if score >= 0.92:
                    _fail("duplicate_family", f"cross-tree {task_id}/{path}: {score:.3f}")
    return {
        "status": "pass",
        "normalizer": CONTAMINATION_NORMALIZER,
        "comparison_count": comparison_count,
        "source_counts": {
            "legacy": inventories["legacy"]["root_count"],
            "reverify": inventories["reverify"]["root_count"],
            "expansion_non_subject": len(expansion_roots),
        },
        "strongest_comparison": strongest,
        "inventory_hashes": {name: value["inventory_hash"] for name, value in inventories.items()},
    }


def _holdout_screen(out: Path, holdout_root: Path) -> dict[str, object]:
    if not holdout_root.is_dir():
        return {"status": "not_completed", "reason": f"missing {holdout_root}", "comparison_count": 0}
    roots = tuple(sorted(path for path in holdout_root.iterdir() if path.is_dir() and path.name in OFFICIAL_HOLDOUTS))
    if {root.name for root in roots} != OFFICIAL_HOLDOUTS:
        _fail("benchmark_content_overlap", "incomplete official holdout inventory")
    material = {}
    for root in roots:
        joined = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in root.rglob("*")
            if path.is_file() and path.stat().st_size < 500_000
        )
        material[root.name] = tuple(
            _ngrams(_normalized_tokens(joined, neutral_identifiers=neutral))
            for neutral in (False, True)
        )
    strongest = {"similarity": 0.0, "candidate": None, "holdout": None}
    for case in CASES:
        joined = "\n".join(_artifact_dimensions(out / case.task_id).values())
        candidate = tuple(
            _ngrams(_normalized_tokens(joined, neutral_identifiers=neutral))
            for neutral in (False, True)
        )
        for holdout, text in material.items():
            score = max(
                _set_similarity(left, right)
                for left, right in zip(candidate, text)
            )
            if score > strongest["similarity"]:
                strongest = {"similarity": score, "candidate": case.task_id, "holdout": holdout}
            if score >= 0.90:
                _fail("benchmark_content_overlap", f"{case.task_id}/{holdout}: {score:.3f}")
    return {
        "status": "pass",
        "normalizer": CONTAMINATION_NORMALIZER,
        "holdout_count": len(roots),
        "comparison_count": len(CASES) * len(roots),
        "strongest_comparison": strongest,
    }


def build(out: Path = DEFAULT_OUT, *, force: bool = False, test_mode: bool = False) -> tuple[Path, ...]:
    _validate_output(out, test_mode=test_mode)
    inventories = _reserve_ids(out)
    if force:
        _remove_owned_roots(out)
    expected = {case.task_id for case in CASES}
    if out.exists():
        foreign = {child.name for child in out.iterdir() if child.is_dir() and child.name != ".state"} - expected
        if foreign:
            _fail("generator_output_drift", f"foreign roots: {sorted(foreign)}")
    roots = []
    for case in CASES:
        root = out / case.task_id
        for relative, content in task_named_files(root, _case_files(case)).items():
            _write(root / relative, content, force)
        roots.append(root)
        contract = _contract_markdown(case)
        _write(out / ".state/contracts" / f"{case.task_id}.md", contract, force)
        _write(
            out / ".state/contracts" / f"{case.task_id}.json",
            json.dumps(
                {
                    "schema_version": "aider-task-creation-contract-v1",
                    "task_id": case.task_id,
                    "family_id": FAMILY_ID,
                    "lineage": {"relation": "new-root", "parent": None},
                    "contract_path": f".state/contracts/{case.task_id}.md",
                    "contract_hash": _sha_bytes(contract.encode()),
                    "primary_core_objective": "achieved",
                    "status": "generated_pending_creator_preflight",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            force,
        )
    controls = _write_controls(out, force)
    proposal_rows = [
        {
            "task_id": case.task_id,
            "title": case.title,
            "lineage": "new-root",
            "mechanism": case.mechanism,
            "boundary": case.boundary,
            "false_substitute": case.negative_reason,
        }
        for case in CASES
    ]
    state = out / ".state"
    _write(state / "source-inventories.json", json.dumps(inventories, indent=2, sort_keys=True) + "\n", True)
    _write(state / "raw-proposals.json", json.dumps(proposal_rows, indent=2, sort_keys=True) + "\n", True)
    _write(state / "generated-candidates.json", json.dumps(proposal_rows, indent=2, sort_keys=True) + "\n", True)
    _write(
        state / "rejected-proposals.json",
        json.dumps(REPLACED_CANDIDATES, indent=2, sort_keys=True) + "\n",
        True,
    )
    _write(
        state / "selected-candidates.json",
        json.dumps({"task_count": EXPECTED_ROOTS, "task_ids": [case.task_id for case in CASES]}, indent=2, sort_keys=True) + "\n",
        True,
    )
    _write(
        state / "generation.json",
        json.dumps(
            {
                "schema_version": "mcn-generation-v1",
                "family_id": FAMILY_ID,
                "task_count": len(roots),
                "owner_hash": _owner_hash(),
                "curriculum_hash": _sha_file(REPO_ROOT / CURRICULUM),
                "count_plan_hash": _sha_file(REPO_ROOT / COUNT_PLAN),
                "controls": controls,
                "status": "generated_pending_creator_preflight",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        True,
    )
    return tuple(roots)


def verify_core(out: Path = DEFAULT_OUT, *, test_mode: bool = False, holdout_root: Path = DEFAULT_HOLDOUT_ROOT) -> dict[str, object]:
    _validate_output(out, test_mode=test_mode)
    actual = {child.name for child in out.iterdir() if child.is_dir() and child.name != ".state"}
    expected = {case.task_id for case in CASES}
    if actual != expected or len(actual) != EXPECTED_ROOTS:
        _fail("hard_rule_root_count", f"expected 60, got {len(actual)}")
    dimensions: dict[str, dict[str, str]] = {}
    prompt_hashes: set[str] = set()
    answer_hashes: set[str] = set()
    task_records: dict[str, object] = {}
    for case in CASES:
        root = out / case.task_id
        hashes = _validate_prompt(case, root)
        if hashes["prompt_hash"] in prompt_hashes:
            _fail("duplicate_task", f"prompt hash: {case.task_id}")
        if hashes["answer_hash"] in answer_hashes:
            _fail("duplicate_family", f"answer hash: {case.task_id}")
        prompt_hashes.add(hashes["prompt_hash"])
        answer_hashes.add(hashes["answer_hash"])
        dimensions[case.task_id] = _artifact_dimensions(root)
        task_records[case.task_id] = {
            **hashes,
            "tree_hash": _tree_hash(root),
            "starter_hashes": {
                f"{case.task_id}.h": _sha_file(root / f"{case.task_id}.h"),
                f"{case.task_id}.cpp": _sha_file(root / f"{case.task_id}.cpp"),
            },
            "reference_hashes": {
                ".meta/example.h": _sha_file(root / ".meta/example.h"),
                ".meta/example.cpp": _sha_file(root / ".meta/example.cpp"),
            },
            "test_hashes": {
                "visible": _sha_file(root / "task_visible_test.cpp"),
                "hidden": _sha_file(root / ".meta/task_hidden_test.cpp"),
                "negative": _sha_file(root / ".meta/task_negative_test.cpp"),
            },
            "negative_source_hash": _sha_file(root / ".meta/negative_false_substitute.cpp"),
            "primary_core_objective": "achieved",
        }
    pairs = []
    for left, right in combinations(CASES, 2):
        decision = _pair_decision(left.task_id, right.task_id, dimensions[left.task_id], dimensions[right.task_id])
        if not decision["materially_distinct_in_all_dimensions"]:
            _fail("duplicate_family", f"{left.task_id}/{right.task_id}: {decision['failed_dimensions']}")
        pairs.append(decision)
    if len(pairs) != 1770:
        _fail("hard_rule_evidence_incomplete", f"pair count {len(pairs)}")
    controls = {}
    base_cases = {
        ADVERSARIAL_CONTROLS[0]: CASES[0],
        ADVERSARIAL_CONTROLS[1]: next(c for c in CASES if c.task_id == "mcn-balanced-phase-residue"),
        ADVERSARIAL_CONTROLS[2]: next(c for c in CASES if c.task_id == "mcn-nearest-free-phase"),
    }
    for name, base in base_cases.items():
        root = out / ".state/hard-rule-controls" / name
        decision = _pair_decision(base.task_id, name, dimensions[base.task_id], _artifact_dimensions(root, control=True))
        if not decision["failed_dimensions"]:
            _fail("duplicate_family", f"adversarial control escaped dimensions: {name}")
        controls[name] = {"status": "rejected", "reason": "duplicate_family", "decision": decision}
    cross_tree = None
    inventories = None
    for attempt in range(10):
        inventories = _reserve_ids(out)
        _write(
            out / ".state/source-inventories.json",
            json.dumps(inventories, indent=2, sort_keys=True) + "\n",
            True,
        )
        try:
            cross_tree = _cross_tree_semantic_screen(out, inventories)
            after = _reserve_ids(out)
            if any(
                inventories[name]["inventory_hash"] != after[name]["inventory_hash"]
                for name in inventories
            ):
                _fail("source_inventory_stale", "inventory changed during complete screen")
            break
        except RuntimeError as error:
            if not str(error).startswith("source_inventory_stale:") or attempt == 9:
                raise
            time.sleep(0.2)
    assert cross_tree is not None and inventories is not None
    holdout = _holdout_screen(out, holdout_root)
    screen = {
        "schema_version": "mcn-hard-rule-screen-v1",
        "task_count": EXPECTED_ROOTS,
        "pair_count": len(pairs),
        "dimensions": list(HARD_RULE_DIMENSIONS),
        "dimension_limits": DIMENSION_LIMITS,
        "pairs": pairs,
        "adversarial_controls": controls,
        "cross_tree": cross_tree,
        "holdout": holdout,
        "status": "pass" if holdout["status"] == "pass" else "not_completed",
    }
    screen_hash = _sha_bytes(json.dumps(screen, sort_keys=True).encode())
    _write(out / ".state/hard-rule-screen.json", json.dumps(screen, indent=2, sort_keys=True) + "\n", True)
    manifest = {
        "schema_version": "mcn-materialization-v1",
        "family_id": FAMILY_ID,
        "task_count": EXPECTED_ROOTS,
        "task_ids": [case.task_id for case in CASES],
        "tree_hash": _tree_hash(out),
        "owner_hash": _owner_hash(),
        "curriculum_hash": _sha_file(REPO_ROOT / CURRICULUM),
        "focused_test_hash": _sha_file(REPO_ROOT / FOCUSED_TEST) if (REPO_ROOT / FOCUSED_TEST).is_file() else "pending",
        "task_records": task_records,
        "prompt_boundary": "pass",
        "reference_mapping": "pass",
        "hard_rule_screen": ".state/hard-rule-screen.json",
        "hard_rule_screen_hash": screen_hash,
        "cross_tree_screen": cross_tree,
        "benchmark_screen": holdout,
        "status": "creator_core_pass" if holdout["status"] == "pass" else "not_completed",
        "dataset_handoff": "not_requested",
    }
    _write(out / ".state/materialization-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    return manifest


def verify_host(out: Path = DEFAULT_OUT, *, test_mode: bool = False) -> dict[str, object]:
    _validate_output(out, test_mode=test_mode)
    missing = [tool for tool in ("cmake", "c++") if shutil.which(tool) is None]
    if missing:
        receipt = {
            "schema_version": "mcn-host-iteration-v1",
            "status": "not_completed",
            "missing_prerequisites": missing,
            "blocked_command": "owner --verify-host",
            "tree_hash": _tree_hash(out),
            "evidence_class": "host_iteration",
            "local_family_verified": False,
        }
        _write(out / ".state/host-verification.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        return receipt
    records = []
    for case in CASES:
        root = out / case.task_id
        with tempfile.TemporaryDirectory(prefix="mcn-host-") as temporary:
            build_dir = Path(temporary) / "build"
            subprocess.run(
                ["cmake", "-S", str(root), "-B", str(build_dir), "-G", "Unix Makefiles", f"-DTASK_SOURCE={root / '.meta/example.cpp'}"],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, capture_output=True, text=True)
            result = subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], capture_output=True, text=True)
            if result.returncode != 0:
                _fail("reference_tests_failed", f"host: {case.task_id}: {result.stdout[-2000:]}")
            records.append({"task_id": case.task_id, "tests": 3})
    receipt = {"schema_version": "mcn-host-iteration-v1", "status": "pass", "records": records, "tree_hash": _tree_hash(out), "evidence_class": "host_iteration", "local_family_verified": False}
    _write(out / ".state/host-verification.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    return receipt


DOCKER_RUNNER = r'''import hashlib,json,os,pathlib,re,shutil,subprocess,tarfile
archive=pathlib.Path("/input/family.tar")
root=pathlib.Path("/tmp/mcn-family")
if root.exists():shutil.rmtree(root)
root.mkdir()
with tarfile.open(archive) as handle:handle.extractall(root)
expected=json.loads(pathlib.Path("/input/expected.json").read_text())
def tree_hash(path):
 d=hashlib.sha256()
 for item in sorted(v for v in path.rglob("*") if v.is_file()):
  d.update(item.relative_to(path).as_posix().encode());d.update(b"\0");d.update(item.read_bytes());d.update(b"\0")
 return "sha256:"+d.hexdigest()
def run_one(identity,path,source,mode,expected_count):
 build=pathlib.Path("/tmp/mcn-build")/identity/mode
 if build.exists():shutil.rmtree(build)
 args=["cmake","-S",str(path),"-B",str(build),"-G","Unix Makefiles","-DCMAKE_CXX_COMPILER=/usr/local/bin/g++","-DTASK_SOURCE="+str(source)]
 if mode=="sanitizer":args += ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-sanitize-recover=all -fno-omit-frame-pointer","-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined -fno-sanitize-recover=all"]
 configured=subprocess.run(args,capture_output=True,text=True,timeout=120)
 if configured.returncode!=0:raise SystemExit("reference_configure_failed:"+identity+":"+mode+"\n"+(configured.stdout+configured.stderr)[-4000:])
 built=subprocess.run(["cmake","--build",str(build),"--parallel","2"],capture_output=True,text=True,timeout=120)
 if built.returncode!=0:raise SystemExit("reference_compile_failed:"+identity+":"+mode+"\n"+(built.stdout+built.stderr)[-4000:])
 shown=subprocess.run(["ctest","--test-dir",str(build),"--show-only=json-v1"],check=True,capture_output=True,text=True,timeout=30)
 count=len(json.loads(shown.stdout)["tests"])
 env=dict(os.environ);env["ASAN_OPTIONS"]="detect_leaks=0";env["UBSAN_OPTIONS"]="halt_on_error=1:print_stacktrace=1"
 result=subprocess.run(["ctest","--test-dir",str(build),"--output-on-failure"],env=env,capture_output=True,text=True,timeout=60)
 if count!=expected_count:raise SystemExit(("sanitizer_test_count_mismatch:" if mode=="sanitizer" else "reference_test_count_mismatch:")+identity+":"+str(count))
 if result.returncode!=0:
  code="negative_fixture_not_rejected" if re.search(r"negative_fixture.*\\*\\*\\*Failed",result.stdout) else "reference_tests_failed"
  raise SystemExit(code+":"+identity+":"+mode+"\n"+result.stdout[-2000:])
 return count
tasks=[]
for task_id,want in expected["tasks"].items():
 path=root/"tasks"/task_id;got=tree_hash(path)
 if got!=want:raise SystemExit("grader_mount_hash_mismatch:"+task_id)
 for mode in ("normal","sanitizer"):
  count=run_one(task_id,path,path/".meta/example.cpp",mode,3)
  tasks.append({"task_id":task_id,"mode":mode,"test_count":count,"negative_rejected":True,"mounted_tree_hash":got})
controls=[]
for name,want in expected["controls"].items():
 path=root/"controls"/name;got=tree_hash(path)
 if got!=want:raise SystemExit("grader_mount_hash_mismatch:control:"+name)
 for mode in ("normal","sanitizer"):
  count=run_one("control-"+name,path,path/"candidate.cpp",mode,2)
  controls.append({"control":name,"mode":mode,"test_count":count,"mounted_tree_hash":got})
compiler=pathlib.Path("/usr/local/bin/g++")
toolchain={"compiler_path":str(compiler),"compiler_version":subprocess.run([str(compiler),"--version"],check=True,capture_output=True,text=True).stdout.splitlines()[0],"compiler_hash":"sha256:"+hashlib.sha256(compiler.read_bytes()).hexdigest(),"cmake_version":subprocess.run(["cmake","--version"],check=True,capture_output=True,text=True).stdout.splitlines()[0]}
pathlib.Path("/output/result.json").write_text(json.dumps({"tasks":tasks,"controls":controls,"toolchain":toolchain},sort_keys=True))
'''


def _archive(out: Path, archive: Path) -> str:
    entries: list[tuple[str, Path]] = []
    for case in CASES:
        root = out / case.task_id
        entries.extend((f"tasks/{case.task_id}/{path.relative_to(root).as_posix()}", path) for path in sorted(item for item in root.rglob("*") if item.is_file()))
    for name in ADVERSARIAL_CONTROLS:
        root = out / ".state/hard-rule-controls" / name
        entries.extend((f"controls/{name}/{path.relative_to(root).as_posix()}", path) for path in sorted(item for item in root.rglob("*") if item.is_file()))
    with tarfile.open(archive, "w") as handle:
        for relative, path in entries:
            data = path.read_bytes()
            info = tarfile.TarInfo(relative)
            info.size = len(data)
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o644
            with tempfile.SpooledTemporaryFile() as stream:
                stream.write(data)
                stream.seek(0)
                handle.addfile(info, stream)
    return _sha_file(archive)


def docker_sanity(out: Path = DEFAULT_OUT, *, test_mode: bool = False, image: str = SANITY_IMAGE) -> dict[str, object]:
    manifest = verify_core(out, test_mode=test_mode)
    if manifest["benchmark_screen"]["status"] != "pass":
        _fail("benchmark_content_overlap", str(manifest["benchmark_screen"]))
    inspect = subprocess.run(["docker", "image", "inspect", image, "--format", "{{.Id}}"], capture_output=True, text=True)
    if inspect.returncode != 0:
        _fail("docker_sanity_not_completed", inspect.stderr.strip())
    tasks = {case.task_id: _tree_hash(out / case.task_id) for case in CASES}
    controls = {name: _tree_hash(out / ".state/hard-rule-controls" / name, include_state=True) for name in ADVERSARIAL_CONTROLS}
    with tempfile.TemporaryDirectory(prefix="mcn-docker-") as temporary:
        root = Path(temporary)
        archive = root / "family.tar"
        archive_hash = _archive(out, archive)
        (root / "expected.json").write_text(json.dumps({"tasks": tasks, "controls": controls}, sort_keys=True), encoding="utf-8")
        (root / "runner.py").write_text(DOCKER_RUNNER, encoding="utf-8")
        output = root / "output"
        output.mkdir()
        result = subprocess.run(
            ["docker", "run", "--rm", "--network", "none", "-v", f"{root}:/input:ro", "-v", f"{output}:/output", image, "python3", "/input/runner.py"],
            capture_output=True,
            text=True,
            timeout=3600,
        )
        if result.returncode != 0:
            _fail("docker_sanity_failed", (result.stdout + "\n" + result.stderr)[-12000:])
        raw = json.loads((output / "result.json").read_text(encoding="utf-8"))
    # Docker is deliberately the expensive middle gate. Re-screen every
    # external source after it finishes so the emitted creator receipt cannot
    # silently bind an inventory that changed during the oracle run.
    manifest = verify_core(out, test_mode=test_mode)
    records = {}
    for case in CASES:
        rows = [row for row in raw["tasks"] if row["task_id"] == case.task_id]
        if {row["mode"] for row in rows} != {"normal", "sanitizer"} or any(row["test_count"] != 3 for row in rows):
            _fail("sanitizer_test_count_mismatch", case.task_id)
        records[case.task_id] = {
            "normal_tests": 3,
            "sanitizer_tests": 3,
            "negative_normal": "rejected",
            "negative_sanitizer": "rejected",
            "tree_hash": tasks[case.task_id],
            "mounted_tree_hash": tasks[case.task_id],
        }
    control_records = {}
    for name in ADVERSARIAL_CONTROLS:
        rows = [row for row in raw["controls"] if row["control"] == name]
        if {row["mode"] for row in rows} != {"normal", "sanitizer"} or any(row["test_count"] != 2 for row in rows):
            _fail("sanitizer_test_count_mismatch", f"control:{name}")
        control_records[name] = {
            "normal_tests": 2,
            "sanitizer_tests": 2,
            "tree_hash": controls[name],
            "mounted_tree_hash": controls[name],
            "semantic_screen": "duplicate_family_at_least_one_dimension",
        }
    receipt = {
        "schema_version": "mcn-creator-preflight-v1",
        "status": "creator_preflight_pass",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "image": image,
        "image_id": inspect.stdout.strip(),
        "network_policy": "none",
        "archive_hash": archive_hash,
        "tree_hash": _tree_hash(out),
        "owner_hash": _owner_hash(),
        "curriculum_hash": _sha_file(REPO_ROOT / CURRICULUM),
        "focused_test_hash": _sha_file(REPO_ROOT / FOCUSED_TEST),
        "toolchain": raw["toolchain"],
        "commands": {
            "normal": "fresh C++17 Unix Makefiles build and three CTests per root",
            "sanitizer": "fresh ASan/UBSan Unix Makefiles build and three CTests per root",
            "negative": "strict compile plus WILL_FAIL executed test in both modes",
            "controls": "two behavior CTests per coherent control in both modes",
        },
        "tasks": records,
        "controls": control_records,
        "hard_rule": {"root_count": 60, "pair_count": 1770, "dimensions": list(HARD_RULE_DIMENSIONS), "status": "pass"},
        "benchmark_screen": manifest["benchmark_screen"],
        "cross_tree_screen": manifest["cross_tree_screen"],
        "dataset_handoff": "not_requested",
        "local_family_verified": False,
        "next_gate": "independent_audit",
    }
    receipt["receipt_hash"] = _sha_bytes(json.dumps(receipt, sort_keys=True).encode())
    _write(out / ".state/creator-preflight.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    manifest["status"] = "creator_preflight_pass"
    manifest["creator_preflight"] = ".state/creator-preflight.json"
    manifest["creator_preflight_hash"] = receipt["receipt_hash"]
    _write(out / ".state/materialization-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    return receipt


def refresh_creator_receipt(out: Path = DEFAULT_OUT, *, test_mode: bool = False) -> dict[str, object]:
    """Refresh only mutable inventory evidence for an exact Docker-tested tree."""
    _validate_output(out, test_mode=test_mode)
    path = out / ".state/creator-preflight.json"
    if not path.is_file():
        _fail("creator_receipt_missing", path.as_posix())
    receipt = json.loads(path.read_text(encoding="utf-8"))
    saved_hash = receipt.pop("receipt_hash", None)
    if saved_hash != _sha_bytes(json.dumps(receipt, sort_keys=True).encode()):
        _fail("creator_receipt_invalid", "internal hash mismatch")
    if receipt.get("status") != "creator_preflight_pass" or receipt.get("tree_hash") != _tree_hash(out):
        _fail("creator_receipt_invalid", "status or subject tree mismatch")
    if set(receipt.get("tasks", {})) != {case.task_id for case in CASES}:
        _fail("creator_receipt_invalid", "task set mismatch")
    for case in CASES:
        current = _tree_hash(out / case.task_id)
        record = receipt["tasks"][case.task_id]
        if record.get("tree_hash") != current or record.get("mounted_tree_hash") != current:
            _fail("creator_receipt_invalid", f"task bytes changed: {case.task_id}")
    if set(receipt.get("controls", {})) != set(ADVERSARIAL_CONTROLS):
        _fail("creator_receipt_invalid", "control set mismatch")
    for name in ADVERSARIAL_CONTROLS:
        current = _tree_hash(out / ".state/hard-rule-controls" / name, include_state=True)
        record = receipt["controls"][name]
        if record.get("tree_hash") != current or record.get("mounted_tree_hash") != current:
            _fail("creator_receipt_invalid", f"control bytes changed: {name}")

    manifest = verify_core(out, test_mode=test_mode)
    receipt.update(
        {
            "tree_hash": _tree_hash(out),
            "owner_hash": _owner_hash(),
            "curriculum_hash": _sha_file(REPO_ROOT / CURRICULUM),
            "focused_test_hash": _sha_file(REPO_ROOT / FOCUSED_TEST),
            "hard_rule": {
                "root_count": EXPECTED_ROOTS,
                "pair_count": 1770,
                "dimensions": list(HARD_RULE_DIMENSIONS),
                "status": "pass",
            },
            "benchmark_screen": manifest["benchmark_screen"],
            "cross_tree_screen": manifest["cross_tree_screen"],
            "local_family_verified": False,
            "next_gate": "independent_audit",
        }
    )
    receipt["receipt_hash"] = _sha_bytes(json.dumps(receipt, sort_keys=True).encode())
    _write(path, json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    manifest["status"] = "creator_preflight_pass"
    manifest["creator_preflight"] = ".state/creator-preflight.json"
    manifest["creator_preflight_hash"] = receipt["receipt_hash"]
    _write(
        out / ".state/materialization-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        True,
    )
    return receipt


def append_cycle(
    out: Path,
    *,
    cycle: int,
    state: str,
    audit_subject_hash: str | None = None,
    audit_report: str | None = None,
    finding_ids: Sequence[str] = (),
    replaced: Sequence[str] = (),
    rejected: Sequence[str] = (),
    review: Sequence[str] = (),
    terminal_status: str | None = None,
) -> Path:
    path = out / ".state/creation-cycles" / f"cycle-{cycle:02d}.json"
    if path.exists():
        _fail("cycle_record_immutable", path.as_posix())
    manifest = json.loads((out / ".state/materialization-manifest.json").read_text(encoding="utf-8"))
    receipt_source = out / manifest.get("creator_preflight", ".state/creator-preflight.json")
    receipt_snapshot = path.with_name(f"cycle-{cycle:02d}.creator-preflight.json")
    receipt_snapshot_relative = None
    receipt_snapshot_hash = None
    if receipt_source.is_file():
        _write(receipt_snapshot, receipt_source.read_text(encoding="utf-8"), False)
        receipt_snapshot_relative = receipt_snapshot.relative_to(out).as_posix()
        receipt_snapshot_hash = _sha_file(receipt_snapshot)
    record = {
        "schema_version": "aider-creation-cycle-v1",
        "cycle": cycle,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "family_id": FAMILY_ID,
        "candidate_manifest": ".state/selected-candidates.json",
        "curriculum_hash": _sha_file(REPO_ROOT / CURRICULUM),
        "generator_hash": _owner_hash(),
        "focused_test_hash": _sha_file(REPO_ROOT / FOCUSED_TEST),
        "tree_hash": _tree_hash(out),
        "grader_policy_hash": _sha_bytes(DOCKER_RUNNER.encode()),
        "task_records": manifest["task_records"],
        "creator_preflight": manifest.get("creator_preflight"),
        "creator_preflight_snapshot": receipt_snapshot_relative,
        "creator_preflight_snapshot_hash": receipt_snapshot_hash,
        "audit_subject_hash": audit_subject_hash,
        "audit_report": audit_report,
        "finding_ids": list(finding_ids),
        "retained": [case.task_id for case in CASES],
        "replaced": list(replaced),
        "rejected": list(rejected),
        "review": list(review),
        "blocked": [],
        "state": state,
        "terminal_status": terminal_status,
        "dataset_handoff": "not_requested",
    }
    _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", False)
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--refresh-receipt", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(argv)
    roots = build(args.out, force=args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify_host:
        verify_host(args.out)
    if args.docker_sanity:
        docker_sanity(args.out, image=args.image)
    if args.refresh_receipt:
        refresh_creator_receipt(args.out)
    print(f"Wrote {len(roots)} modular-clock-normalization tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
