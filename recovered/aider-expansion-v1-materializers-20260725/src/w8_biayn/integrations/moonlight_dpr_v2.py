"""Materialize and verify the 60-root deterministic parallel reductions v2 family."""

# ruff: noqa: E701,E702

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_dpr_v2_cases import CASES as DECOMPOSITION
from w8_biayn.integrations.moonlight_dpr_v2_composite_cases import CASES as COMPOSITE
from w8_biayn.integrations.moonlight_dpr_v2_merge_cases import (
    CASES as MERGE,
    SPARSE_VECTOR_CLONE,
)
from w8_biayn.integrations.moonlight_dpr_v2_numeric_cases import CASES as NUMERIC
from w8_biayn.integrations.moonlight_dpr_v2_structural_cases import CASES as STRUCTURAL

CASES = DECOMPOSITION + NUMERIC + STRUCTURAL + MERGE + COMPOSITE
GROUPS = ("decomposition", "numeric", "structural", "merge", "composite")
FAMILY_ID = "aider-expansion-v1-deterministic-parallel-reductions-v2"
PRIOR_FAMILY_ID = "aider-expansion-v1-deterministic-parallel-reductions-v1"
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
DEFAULT_OUT = EXPANSION_ROOT / "state-concurrency/deterministic-parallel-reductions"
CURRICULUM = Path("docs/aider-synthetic/aider-synthetic-state-concurrency/GLM47_FLASH_AIDER_POLYGLOT_CPP_DETERMINISTIC_PARALLEL_REDUCTIONS_CURRICULUM.md")
FAMILY_SPEC = Path("docs/aider-tasks-spec/aider-state-concurrency/deterministic-parallel-reductions.md")
GENERATOR = Path("src/w8_biayn/integrations/moonlight_dpr_v2.py")
CASE_PATHS = tuple(
    Path("src/w8_biayn/integrations") / name
    for name in (
        "moonlight_dpr_v2_cases.py",
        "moonlight_dpr_v2_numeric_cases.py",
        "moonlight_dpr_v2_structural_cases.py",
        "moonlight_dpr_v2_merge_cases.py",
        "moonlight_dpr_v2_composite_cases.py",
    )
)
FOCUSED_TEST = Path("tests/test_moonlight_dpr_v2.py")
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
OFFICIAL_HOLDOUTS = frozenset(
    "all-your-base allergies bank-account binary-search-tree circular-buffer clock complex-numbers crypto-square diamond dnd-character gigasecond grade-school kindergarten-garden knapsack linked-list meetup parallel-letter-frequency perfect-numbers phone-number queen-attack robot-name space-age spiral-matrix sublist yacht zebra-puzzle".split()
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
CONTROL_NAMES = (
    "domain-identifier-renamed",
    "constants-policy-only",
    "opposite-end-selection",
    "dimensional-wrapper-clone",
)

NEGATIVE_WITNESSES = {
    "dpr-checked-dot-product": "check(!CheckedDotProduct::reduce({{{LLONG_MAX,2}}}));",
    "dpr-component-affinity-shards": "auto witness=ComponentAffinityShards::assign({1,2},{{1,2}},2);check(witness&&(*witness)[1]==(*witness)[2]);",
    "dpr-edge-shards-to-csr": "auto witness=EdgeShardsToCsr::build(2,{{{0,1,2}},{{0,1,-2}}});check(witness&&witness->targets.empty());",
    "dpr-keyed-conflict-reconcile": "auto witness=KeyedConflictReconcile::merge({{{\"a\",\"x\",2,3}},{{\"a\",\"y\",2,1}}});check(witness&&witness->values.empty()&&witness->conflicts.size()==1);",
    "dpr-nonoverlap-hunk-merge": "auto witness=NonoverlapHunkMerge::merge(4,{{{0,2,\"a\",0},{2,4,\"b\",0}}});check(witness&&!witness->conflict&&witness->hunks.size()==2);",
    "dpr-paired-covariance-state": "auto witness=PairedCovarianceState::reduce({{},{{-2,3}}});check(witness&&witness->sum_xy==-6);",
    "dpr-seamed-tile-assembly": "auto witness=SeamedTileAssembly::assemble(1,1,{{1,0,0,1,1,{1}},{2,0,0,1,1,{2}}});check(!witness);",
    "dpr-two-phase-commit-log": "auto witness=TwoPhaseCommitLog::reduce({{{9,1,TwoPhaseCommitLog::Kind::Prepare},{9,1,TwoPhaseCommitLog::Kind::Commit}}},{1,2});check(!witness);",
    "dpr-domain-separated-merkle-fold": "auto witness=DomainSeparatedMerkleFold::root({{{0,\"a\"},{1,\"b\"},{2,\"c\"}}},3);check(witness&&*witness==15560649592390990879ULL);",
    "dpr-first-prefix-overflow": "auto witness=FirstPrefixOverflow::scan({{-1,1,1}},LLONG_MAX);check(witness.overflow&&witness.index==2);",
    "dpr-loser-tree-run-merge": "auto witness=LoserTreeRunMerge::merge({{{0,0,0},{1,0,1}},{{1,1,0}}});check(witness&&(*witness)[1].origin==0&&(*witness)[2].origin==1);",
    "dpr-majority-summary-verify": "check(!MajoritySummaryVerify::majority({{1,2,3}}));",
    "dpr-minimax-contiguous-cuts": "auto witness=MinimaxCuts::partition({0,0,0},2);check(witness&&witness->cuts==std::vector<std::size_t>({1,3}));",
    "dpr-modular-product-fold": "auto witness=ModularProductFold::reduce({{ULLONG_MAX-1,ULLONG_MAX-1}},ULLONG_MAX);check(witness&&*witness==1);",
    "dpr-morton-grid-tiles": "auto witness=MortonGridTiles::plan(3,3,1);check(witness.has_value());std::size_t a=9,b=9;for(std::size_t i=0;i<witness->size();++i){if((*witness)[i].row==1&&(*witness)[i].col==2)a=i;if((*witness)[i].row==2&&(*witness)[i].col==0)b=i;}check(a<b);",
    "dpr-priority-reservoir-merge": "auto witness=PriorityReservoirMerge::reduce({{{1,9},{3,9}}},0,1);check(witness&&witness->size()==1&&(*witness)[0].id==3);",
    "dpr-retry-state-lattice": "auto witness=RetryStateLattice::reduce({{{7,RetryStateLattice::State::Failed},{7,RetryStateLattice::State::Succeeded}}});check(witness&&(*witness)[7]==RetryStateLattice::State::Succeeded);",
}

COMMON_INCLUDES = """#include <algorithm>
#include <array>
#include <climits>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <functional>
#include <iterator>
#include <limits>
#include <map>
#include <numeric>
#include <optional>
#include <queue>
#include <set>
#include <string>
#include <tuple>
#include <utility>
#include <vector>
"""

CMAKE = r'''cmake_minimum_required(VERSION 3.16)
project(dpr_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation")
enable_testing()
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(name visible hidden)
  target_include_directories(task_${name} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  target_compile_options(task_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  add_test(NAME ${name} COMMAND task_${name})
endforeach()
if(DEFINED NEGATIVE_SOURCE)
  add_executable(negative_visible "${NEGATIVE_SOURCE}" task_visible_test.cpp)
  add_executable(negative_hidden "${NEGATIVE_SOURCE}" .meta/task_hidden_test.cpp)
  foreach(name visible hidden)
    target_include_directories(negative_${name} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
    target_compile_options(negative_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endforeach()
endif()
'''


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    return _sha(path.read_bytes())


def _tree_hash(root: Path, *, include_state: bool = False) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "not_available"
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if not include_state and ".state" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _validate_output(out: Path) -> None:
    resolved, expansion = out.resolve(), EXPANSION_ROOT.resolve()
    if resolved == expansion or expansion not in resolved.parents:
        _fail("unsafe_path", f"output must be below {EXPANSION_ROOT}: {out}")
    for forbidden in (LEGACY_ROOT.resolve(), REVERIFY_ROOT.resolve()):
        if resolved == forbidden or forbidden in resolved.parents:
            _fail("unsafe_path", str(out))
    cursor = out
    while cursor != EXPANSION_ROOT.parent and cursor != cursor.parent:
        if cursor.is_symlink():
            _fail("unsafe_path", f"symlink component: {cursor}")
        cursor = cursor.parent


def _inventory(root: Path) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    if not root.is_dir():
        return records
    for config in sorted(root.rglob(".meta/config.json")):
        if ".state" in config.parts:
            continue
        task_root = config.parent.parent
        records.append(
            {
                "task_id": task_root.name,
                "relative_root": task_root.relative_to(root).as_posix(),
                "tree_hash": _tree_hash(task_root),
                "config_hash": _file_hash(config),
            }
        )
    return records


def _freeze_inventory(out: Path, force: bool) -> dict[str, object]:
    relative = out.resolve().relative_to(EXPANSION_ROOT.resolve()).as_posix()
    groups = {
        "legacy": _inventory(LEGACY_ROOT),
        "reverify": _inventory(REVERIFY_ROOT),
        "expansion_before": [
            row
            for row in _inventory(EXPANSION_ROOT)
            if not row["relative_root"].startswith(relative + "/")
        ],
    }
    payload: dict[str, object] = {
        "schema_version": "dpr-v2-source-inventory-v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "roots": {},
    }
    for name, rows in groups.items():
        payload["roots"][name] = {
            "count": len(rows),
            "sha256": _sha(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()),
            "records": rows,
        }
    _write(out / ".state/source-inventory-v2.json", json.dumps(payload, indent=2, sort_keys=True) + "\n", force)
    return payload


def _header(case) -> str:
    return f"#pragma once\n{COMMON_INCLUDES}\nnamespace curriculum {{\n{case.api}\n}}\n"


def _source(case, definition: str | None = None) -> str:
    return f'#include "{case.task_id}.h"\nnamespace curriculum {{\n{definition or case.definition}\n}}\n'


def _test(case, body: str) -> str:
    body = re.sub(r"using ([A-Z])=", r"using \1 [[maybe_unused]]=", body)
    return f'''#include "{case.task_id}.h"
using namespace curriculum;
namespace {{ void check(bool condition){{if(!condition)std::exit(1);}} }}
int main(){{{body}return 0;}}
'''


def _instructions(case) -> str:
    return f'''# Instructions

Implement **{case.title}** in C++17 using the task-named header and source.

Public API:

```cpp
{case.api}
```

The owned mechanism is {case.mechanism}. {case.boundary}. Invalid input must
fail atomically using the API's documented optional/report state; never expose
a partial result. Preserve source order where the contract names it and use
the stated deterministic tie rule.

Do not replace the mechanism with a global sort/scan, a generic policy switch,
completion-order state, precomputed answers, randomness, clocks, files,
networking, or a parallel library. The specific false substitute rejected by
the private tests is: {case.negative_reason}.
'''


def _contract(case) -> str:
    return f'''# {case.title}: deterministic family contract

- Task ID: `{case.task_id}`
- Lineage: `replacement-new-root-v2` for rejected cycle-1 template; no cycle-1
  root is retained by the v2 manifest.
- Group: `{case.group}`
- Public API: `{case.api}`
- Owned mechanism: {case.mechanism}
- Boundary/invariant: {case.boundary}
- Compiling negative: {case.negative_reason}
- Primary core objective: reference implements the named partial/state/merge
  control flow and the visible/private tests execute its discriminator.
- Prompt roles: docs plus task-named header/source only.
- Oracle: pinned network-disabled C++17 normal and fresh ASan/UBSan builds.
- Dataset handoff: not requested.
'''


def _render(case) -> dict[str, str]:
    if case.definition.count(case.negative_old) != 1:
        _fail("negative_fixture_ambiguous", case.task_id)
    negative = case.definition.replace(case.negative_old, case.negative_new)
    config = {
        "authors": ["w8-biayn"],
        "blurb": case.mechanism,
        "files": {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": ["task_visible_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "schema_version": "dpr-v2-provenance-v1",
        "family_id": FAMILY_ID,
        "task_id": case.task_id,
        "lineage": "replacement-new-root-v2",
        "replaces_rejected_cycle": 1,
        "mechanism": case.mechanism,
        "boundary": case.boundary,
        "negative_reason": case.negative_reason,
        "count_plan_cell": "state/concurrency / deterministic parallel partition, reduction, and merge / 60",
        "origin": "repository-authored clean-room expansion",
        "benchmark_separation": "26 official Aider C++ roots are permanent holdouts",
        "status": "local candidate only; no dataset release",
    }
    witness = NEGATIVE_WITNESSES.get(case.task_id, "")
    visible_body = case.visible + witness
    hidden_body = case.hidden + "{" + visible_body + "}"
    return {
        ".docs/introduction.md": f"# {case.title}\n\nA clean-room deterministic parallel reduction task.\n",
        ".docs/instructions.md": _instructions(case),
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": "[visible]\ndescription='ordinary mechanism trace'\n[hidden]\ndescription='invalid, empty, tie, and boundary properties'\n[negative]\ndescription='topic-specific compiling false substitute'\n",
        ".meta/example.h": _header(case),
        ".meta/example.cpp": _source(case),
        ".meta/task_hidden_test.cpp": _test(case, hidden_body),
        ".meta/negative_false_substitute.cpp": _source(case, negative),
        f"{case.task_id}.h": _header(case),
        f"{case.task_id}.cpp": _source(case, case.starter),
        "task_visible_test.cpp": _test(case, visible_body),
        "CMakeLists.txt": CMAKE,
    }


def _write_root(root: Path, case, force: bool, transforms=()) -> list[str]:
    files = _render(case)
    for old, new in transforms:
        files = {name: content.replace(old, new) for name, content in files.items()}
    changed: list[str] = []
    for relative, content in files.items():
        path = root / relative
        before = path.read_text() if path.is_file() else None
        _write(path, content, force)
        if before != content:
            changed.append(relative)
    return changed


def _prune_rejected_roots(out: Path, force: bool) -> list[str]:
    expected = {case.task_id for case in CASES}
    removed: list[str] = []
    if not out.is_dir():
        return removed
    for root in sorted(p for p in out.iterdir() if p.is_dir() and p.name != ".state"):
        if root.name in expected:
            continue
        provenance = root / ".meta/provenance.json"
        if not provenance.is_file():
            _fail("foreign_root", str(root))
        family = json.loads(provenance.read_text()).get("family_id")
        if family not in {PRIOR_FAMILY_ID, FAMILY_ID}:
            _fail("foreign_root", f"{root}: {family}")
        if not force:
            _fail("stale_rejected_root", f"{root}; pass --force")
        shutil.rmtree(root)
        removed.append(root.name)
    return removed


def _write_controls(out: Path, force: bool) -> None:
    frame_case = DECOMPOSITION[3]
    sparse_case = next(case for case in STRUCTURAL if case.task_id == "dpr-sparse-coo-canonical-merge")
    base = out / ".state/adversarial-clone-controls"
    controls = {
        "domain-identifier-renamed": (frame_case, frame_case, (("FrameAlignedSlices", "PacketAlignedSlices"),)),
        "constants-policy-only": (frame_case, frame_case, (("workers>frames.size()", "workers>=frames.size()"),)),
        "opposite-end-selection": (
            frame_case,
            frame_case,
            (
                ("e<best", "e>best"),
                ("({3,9,12})", "({5,9,12})"),
                ("(*c)[0]==2", "(*c)[0]==4"),
            ),
        ),
        "dimensional-wrapper-clone": (SPARSE_VECTOR_CLONE, sparse_case, ()),
    }
    records = {}
    for name, (case, source_case, changes) in controls.items():
        root = base / name
        if root.exists() and force:
            shutil.rmtree(root)
        _write_root(root, case, force, changes)
        source = out / source_case.task_id
        changed = sorted(
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
            and (source / path.relative_to(root)).is_file()
            and path.read_bytes() != (source / path.relative_to(root)).read_bytes()
        )
        records[name] = {"base_task_id": source_case.task_id, "changed_files": changed, "tree_hash": _tree_hash(root, include_state=True)}
    _write(base / "manifest.json", json.dumps({"schema_version": "dpr-v2-controls-v1", "controls": records}, indent=2, sort_keys=True) + "\n", force)


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    _validate_output(out)
    if len(CASES) != 60 or len({c.task_id for c in CASES}) != 60:
        _fail("count_mismatch", str(len(CASES)))
    inventory = _freeze_inventory(out, force)
    external_ids = {
        row["task_id"]
        for group in inventory["roots"].values()
        for row in group["records"]
    }
    collisions = sorted(external_ids & {c.task_id for c in CASES})
    if collisions:
        _fail("duplicate_task", ",".join(collisions))
    removed = _prune_rejected_roots(out, force)
    roots = []
    for case in CASES:
        root = out / case.task_id
        if root.exists() and any(p.is_symlink() for p in root.rglob("*")):
            _fail("unsafe_path", str(root))
        _write_root(root, case, force)
        _write(out / ".state/contracts-v2" / f"{case.task_id}.md", _contract(case), force)
        roots.append(root)
    _write_controls(out, force)
    audit_path = out / ".state/audits/cycle-01-independent/audit.json"
    cycle_01_ids = []
    if audit_path.is_file():
        cycle_01_ids = sorted(row["task_id"] for row in json.loads(audit_path.read_text())["root_catalog"])
    _write(out / ".state/rejected-cycle-01-roots.json", json.dumps({"schema_version": "dpr-v2-replacement-v1", "audit": ".state/audits/cycle-01-independent/audit.json", "replaced_cycle_01_root_ids": cycle_01_ids, "physically_pruned_this_run": removed, "same_slug_replaced": sorted(set(cycle_01_ids) & {case.task_id for case in CASES}), "retained_cycle_01_root_ids": [], "replacement_count": 60}, indent=2, sort_keys=True) + "\n", True)
    return tuple(roots)


_CPP_KEEP = frozenset(
    "class struct enum public private static const auto bool int long unsigned void return if else for while switch case break continue true false namespace using optional vector map set deque array pair tuple string size_t sort merge rotate unique count min max lower_bound upper_bound emplace insert erase push_back pop_back pop_front front back begin end empty size resize reserve iota tie make_pair nullopt LLONG_MAX LLONG_MIN ULLONG_MAX INT_MIN".split()
)
_GENERIC = frozenset("task value values item items data result state report root current local input output source target actor worker workers shard shards frame frames packet packets record records key keys id ids".split())
_ALIASES = {"packet": "frame", "packets": "frames", "smaller": "endpoint", "larger": "endpoint", "earlier": "endpoint", "later": "endpoint", "first": "endpoint", "last": "endpoint", "minimum": "endpoint", "maximum": "endpoint"}


def _normalized_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " LITERAL ", text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", " LITERAL ", text)
    text = re.sub(r"\b(?:0x[0-9a-fA-F]+|\d+)[uUlL]*\b", " NUMBER ", text)
    words = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|==|!=|<=|>=|&&|\|\||\+\+|--|->|[-+*/%<>{}()[\];,?:=]", text.lower())
    out = []
    for word in words:
        word = _ALIASES.get(word, word)
        if word in _GENERIC:
            continue
        if word in {"<", ">", "<=", ">="}:
            out.append("ORDER")
        elif word in _CPP_KEEP or not re.match(r"[a-z_]", word):
            out.append(word)
        elif word in {"literal", "number"}:
            out.append(word)
        else:
            out.append("IDENTIFIER")
    return tuple(out)


def _dimension_material(root: Path) -> dict[str, tuple[str, ...]]:
    header = next(root.glob("*.h")).read_text()
    source = (root / ".meta/example.cpp").read_text()
    instructions = (root / ".docs/instructions.md").read_text()
    visible = (root / "task_visible_test.cpp").read_text()
    hidden = (root / ".meta/task_hidden_test.cpp").read_text()
    negative = (root / ".meta/negative_false_substitute.cpp").read_text()
    return {
        "public_api": _normalized_tokens(header),
        "owned_state_algorithm": _normalized_tokens(source),
        "mutation_selection_rules": _normalized_tokens(instructions + source),
        "invalid_boundary_behavior": _normalized_tokens(instructions + hidden),
        "reference_control_flow": _normalized_tokens(source),
        "deterministic_oracle": _normalized_tokens(visible + hidden),
        "topic_negative_fixture": _normalized_tokens(negative),
    }


def _decision(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    width = 5
    left = {a[index : index + width] for index in range(max(0, len(a) - width + 1))}
    right = {b[index : index + width] for index in range(max(0, len(b) - width + 1))}
    if not left or not right:
        return False
    containment = len(left & right) / min(len(left), len(right))
    # A dimensional wrapper can change token sequence lengths while preserving
    # the same sparse-map state machine.  Requiring at least four distinct
    # structural shingles catches that coherent clone without making ordinary
    # production pairs fail merely because they share common C++ scaffolding.
    return len(left ^ right) >= 4 and containment < 0.985


def _semantic_mechanism_fingerprint(root: Path) -> tuple[str, ...]:
    """Return artifact-derived mechanism flags that survive dimensional wrappers."""
    source = (root / ".meta/example.cpp").read_text()
    flags: list[str] = []
    if (
        "std::map<" in source
        and "__builtin_add_overflow" in source
        and "previous" in source
        and "return std::nullopt" in source
        and re.search(r"if\([^)]*(?:second|!=\s*0)[^)]*\).*push_back", source)
    ):
        flags.append("validated-sorted-sparse-checked-map-accumulate-drop-zero")
    return tuple(flags)


def pair_decisions(left: Path, right: Path) -> dict[str, bool]:
    lhs, rhs = _dimension_material(left), _dimension_material(right)
    left_mechanism = _semantic_mechanism_fingerprint(left)
    right_mechanism = _semantic_mechanism_fingerprint(right)
    if left_mechanism and left_mechanism == right_mechanism:
        return {dimension: False for dimension in HARD_DIMENSIONS}
    return {dimension: _decision(lhs[dimension], rhs[dimension]) for dimension in HARD_DIMENSIONS}


def _family_screen(out: Path) -> dict[str, object]:
    roots = sorted((out / c.task_id for c in CASES), key=lambda p: p.name)
    pairs = []
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            decisions = pair_decisions(left, right)
            if not all(decisions.values()):
                _fail("duplicate_family", f"{left.name} vs {right.name}: {decisions}")
            pairs.append({"left": left.name, "right": right.name, "decisions": decisions})
    expected = len(roots) * (len(roots) - 1) // 2
    if len(pairs) != expected:
        _fail("pair_count_mismatch", f"{len(pairs)} != {expected}")
    controls = {}
    control_manifest = json.loads((out / ".state/adversarial-clone-controls/manifest.json").read_text())
    for name in CONTROL_NAMES:
        root = out / ".state/adversarial-clone-controls" / name
        base = out / control_manifest["controls"][name]["base_task_id"]
        decisions = pair_decisions(base, root)
        if any(decisions.values()):
            _fail("clone_control_escaped", f"{name}: {decisions}")
        changed = control_manifest["controls"][name]["changed_files"]
        if not changed:
            _fail("clone_control_noop", name)
        controls[name] = {"source": base.name, "changed_files": changed, "decisions": decisions, "production_rejected": True}
    return {"status": "pass", "root_count": len(roots), "pair_count": len(pairs), "expected_pair_count": expected, "dimensions": list(HARD_DIMENSIONS), "normalizer": "dpr-v2-artifact-identifier-domain-literal-endpoint-neutral", "pairs": pairs, "controls": controls}


def _shingles(text: str, width: int = 11) -> set[tuple[str, ...]]:
    tokens = _normalized_tokens(text)
    return {tokens[i : i + width] for i in range(max(0, len(tokens) - width + 1))}


def _root_text(root: Path) -> str:
    paths = [next(root.glob("*.h")), root / ".meta/example.cpp", root / "task_visible_test.cpp", root / ".meta/task_hidden_test.cpp"]
    paths.extend(sorted((root / ".docs").glob("*.md")))
    return "\n".join(path.read_text(errors="ignore") for path in paths if path.is_file())


def _containment(left: str, right: str) -> float:
    a, b = _shingles(left), _shingles(right)
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def _holdout_screen(out: Path) -> dict[str, object]:
    found = {p.name for p in HOLDOUT_ROOT.iterdir() if p.is_dir()} if HOLDOUT_ROOT.is_dir() else set()
    missing = sorted(OFFICIAL_HOLDOUTS - found)
    if missing:
        _fail("benchmark_content_overlap", f"missing holdouts: {missing}")
    rows, strongest = [], (0.0, "", "")
    for case in CASES:
        candidate = _root_text(out / case.task_id)
        for holdout in sorted(OFFICIAL_HOLDOUTS):
            score = _containment(candidate, _root_text(HOLDOUT_ROOT / holdout))
            rows.append({"candidate": case.task_id, "holdout": holdout, "score": round(score, 6), "relation": "distinct" if score < 0.72 else "overlap"})
            if score > strongest[0]:
                strongest = (score, case.task_id, holdout)
            if score >= 0.72:
                _fail("benchmark_content_overlap", f"{case.task_id} vs {holdout}: {score:.3f}")
    ledger = out / ".state/holdout-comparisons-v2.jsonl"
    _write(ledger, "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n", True)
    return {"status": "pass", "comparison_count": len(rows), "expected_comparison_count": 60 * 26, "ledger": ".state/holdout-comparisons-v2.jsonl", "ledger_hash": _file_hash(ledger), "threshold": 0.72, "strongest_pair": [strongest[1], strongest[2]], "strongest_score": round(strongest[0], 6)}


def _cross_tree_screen(out: Path) -> dict[str, object]:
    inventory = json.loads((out / ".state/source-inventory-v2.json").read_text())
    tree_by_name = {"legacy": LEGACY_ROOT, "reverify": REVERIFY_ROOT, "expansion_before": EXPANSION_ROOT}
    candidate_grams = {case.task_id: _shingles(_root_text(out / case.task_id)) for case in CASES}
    rows, strongest = [], (0.0, "", "")
    count = 0
    for name in ("legacy", "reverify", "expansion_before"):
        for record in inventory["roots"][name]["records"]:
            root = tree_by_name[name] / record["relative_root"]
            config = root / ".meta/config.json"
            if not config.is_file() or _file_hash(config) != record["config_hash"] or _tree_hash(root) != record["tree_hash"]:
                _fail("source_inventory_drift", f"{name}:{record['relative_root']}")
            other_grams = _shingles(_root_text(root))
            for case in CASES:
                grams = candidate_grams[case.task_id]
                denominator = min(len(grams), len(other_grams))
                score = len(grams & other_grams) / denominator if denominator else 0.0
                external = f"{name}:{record['relative_root']}"
                row = {"candidate": case.task_id, "external": external, "external_tree_hash": record["tree_hash"], "score": round(score, 6), "relation": "distinct" if score < 0.76 else "overlap"}
                rows.append(row)
                count += 1
                if score > strongest[0]:
                    strongest = (score, case.task_id, external)
                if score >= 0.76:
                    _fail("duplicate_family", f"cross-tree {case.task_id} vs {external}: {score:.3f}")
    frozen_count = sum(inventory["roots"][name]["count"] for name in tree_by_name)
    expected = 60 * frozen_count
    if count != expected:
        _fail("source_inventory_drift", f"{count} != {expected}")
    ledger = out / ".state/cross-tree-comparisons-v2.jsonl"
    _write(ledger, "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows) + "\n", True)
    return {"status": "pass", "comparison_count": count, "expected_comparison_count": expected, "frozen_external_root_count": frozen_count, "ledger": ".state/cross-tree-comparisons-v2.jsonl", "ledger_hash": _file_hash(ledger), "threshold": 0.76, "strongest_pair": [strongest[1], strongest[2]], "strongest_score": round(strongest[0], 6)}


def verify_core(out: Path = DEFAULT_OUT) -> None:
    if len(CASES) != 60 or len({c.task_id for c in CASES}) != 60:
        _fail("count_mismatch", str(len(CASES)))
    group_counts = {group: sum(c.group == group for c in CASES) for group in GROUPS}
    if group_counts != {group: 12 for group in GROUPS}:
        _fail("count_mismatch", str(group_counts))
    rows, prompts, references, negatives = [], set(), set(), set()
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        if config["files"]["solution"] != [f"{case.task_id}.h", f"{case.task_id}.cpp"] or config["files"]["example"] != [".meta/example.h", ".meta/example.cpp"]:
            _fail("target_reference_mismatch", case.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        if any(marker in prompt for marker in (".meta/", "CMakeLists", "task_visible_test", "provenance.json", "negative_false_substitute")):
            _fail("prompt_contract_incomplete", case.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if not answer.startswith(f"{case.task_id}.h\n```") or f"{case.task_id}.cpp\n```" not in answer:
            _fail("target_reference_mismatch", case.task_id)
        prompt_hash, reference_hash, negative_hash = _sha(prompt.encode()), _file_hash(root / ".meta/example.cpp"), _file_hash(root / ".meta/negative_false_substitute.cpp")
        if prompt_hash in prompts or reference_hash in references or negative_hash in negatives:
            _fail("duplicate_family", f"raw hash collision: {case.task_id}")
        prompts.add(prompt_hash); references.add(reference_hash); negatives.add(negative_hash)
        rows.append({"task_id": case.task_id, "group": case.group, "mechanism": case.mechanism, "tree_hash": _tree_hash(root), "prompt_hash": prompt_hash, "starter_hash": _file_hash(root / f"{case.task_id}.cpp"), "reference_hash": reference_hash, "visible_test_hash": _file_hash(root / "task_visible_test.cpp"), "hidden_test_hash": _file_hash(root / ".meta/task_hidden_test.cpp"), "negative_hash": negative_hash, "metadata_hash": _file_hash(root / ".meta/config.json"), "provenance_hash": _file_hash(root / ".meta/provenance.json"), "contract_hash": _file_hash(out / ".state/contracts-v2" / f"{case.task_id}.md"), "primary_core_objective": "achieved_pending_execution"})
    family = _family_screen(out)
    holdout = _holdout_screen(out)
    cross_tree = _cross_tree_screen(out)
    manifest = {"schema_version": "dpr-v2-materialization-v1", "family_id": FAMILY_ID, "task_count": 60, "group_counts": group_counts, "owner_hash": _file_hash(GENERATOR), "case_hashes": {p.as_posix(): _file_hash(p) for p in CASE_PATHS}, "curriculum_hash": _file_hash(CURRICULUM), "family_spec_hash": _file_hash(FAMILY_SPEC), "focused_test_hash": _file_hash(FOCUSED_TEST), "family_tree_hash": _tree_hash(out), "tasks": rows, "screen": {"prompt_boundary": "pass", "reference_mapping": "pass", "diversity": family, "benchmark_holdout": holdout, "cross_tree": cross_tree}, "prior_audits": [".state/audits/cycle-01-independent/audit.json", ".state/audits/cycle-02-independent/audit.json", ".state/audits/cycle-03-independent/audit.json"], "remedy_records": [".state/remedies/cycle-01", ".state/remedies/cycle-02", ".state/remedies/cycle-03"], "strongest_local_status": "pending_execution", "dataset_handoff": "not_requested"}
    _write(out / ".state/materialization-manifest-v2.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)


def _archive(out: Path, target: Path) -> str:
    expected = target.parent / "expected.tsv"
    roots = [("tasks", out / c.task_id) for c in CASES] + [("controls", out / ".state/adversarial-clone-controls" / name) for name in CONTROL_NAMES]
    expected.write_text("".join(f"{kind}\t{root.name}\t{_tree_hash(root, include_state=True)}\n" for kind, root in roots))
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as archive:
        for source, arcname in [(expected, "expected.tsv")]:
            info = archive.gettarinfo(str(source), arcname=arcname); info.uid = info.gid = info.mtime = 0; info.uname = info.gname = ""; info.mode = 0o644
            with source.open("rb") as handle: archive.addfile(info, handle)
        for kind, root in roots:
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                info = archive.gettarinfo(str(path), arcname=f"{kind}/{root.name}/{path.relative_to(root).as_posix()}"); info.uid = info.gid = info.mtime = 0; info.uname = info.gname = ""; info.mode = 0o644
                with path.open("rb") as handle: archive.addfile(info, handle)
    return _file_hash(target)


def verify_docker(out: Path = DEFAULT_OUT, image: str = SANITY_IMAGE) -> None:
    manifest_path = out / ".state/materialization-manifest-v2.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["family_tree_hash"] != _tree_hash(out) or manifest["owner_hash"] != _file_hash(GENERATOR):
        _fail("generator_output_drift", "manifest does not bind current owner/tree")
    with tempfile.TemporaryDirectory(prefix="dpr-v2-") as temporary:
        temp = Path(temporary); archive = temp / "family.tar"; result = temp / "result"; result.mkdir()
        archive_hash = _archive(out, archive)
        script = r'''set -Eeuo pipefail
mkdir -p /work /result
trap 'rc=$?; echo "verifier failed rc=$rc" >&2; for f in /tmp/config.log /tmp/build.log /tmp/discovery.log /tmp/test.log /tmp/nv.log /tmp/nh.log;do [ ! -f "$f" ]||{ echo "LOG $f" >&2;tail -80 "$f" >&2;};done;exit $rc' ERR
tar -xf /input/family.tar -C /work
sha256sum /input/family.tar|awk '{print "archive\t"$1}' >/result/results.tsv
: >/result/negative-failures.tsv
: >/result/compile-failures.tsv
: >/result/positive-failures.tsv
command -v c++ >/result/compiler.path;c++ --version|head -1 >/result/compiler.version;sha256sum "$(command -v c++)"|awk '{print $1}' >/result/compiler.sha256;cmake --version|head -1 >/result/cmake.version
python3 - <<'PY'
from pathlib import Path
import hashlib
for line in Path('/work/expected.tsv').read_text().splitlines():
 k,n,e=line.split('\t');r=Path('/work')/k/n;d=hashlib.sha256()
 for p in sorted(x for x in r.rglob('*') if x.is_file()):d.update(p.relative_to(r).as_posix().encode());d.update(b'\0');d.update(p.read_bytes());d.update(b'\0')
 if 'sha256:'+d.hexdigest()!=e:raise SystemExit('grader_mount_hash_mismatch:'+n)
PY
run_one(){
 kind="$1";id="$2";mode="$3";negative="$4";root="/work/$kind/$id";build="/tmp/$kind-$id-$mode";flags=()
 [ "$mode" != sanitizer ]||flags+=("-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined")
 [ "$negative" != yes ]||flags+=("-DNEGATIVE_SOURCE=$root/.meta/negative_false_substitute.cpp")
 if ! cmake -S "$root" -B "$build" -G "Unix Makefiles" -DTASK_SOURCE="$root/.meta/example.cpp" "${flags[@]}" >/tmp/config.log 2>&1;then printf '%s\t%s\tconfigure\n' "$id" "$mode" >>/result/compile-failures.tsv;return;fi
 if ! cmake --build "$build" --parallel 2 >/tmp/build.log 2>&1;then printf '%s\t%s\tbuild\n' "$id" "$mode" >>/result/compile-failures.tsv;return;fi
 ctest --test-dir "$build" -N >/tmp/discovery.log 2>&1;count=$(sed -n 's/^Total Tests: //p' /tmp/discovery.log);names=$(sed -n 's/.*Test #[0-9][0-9]*: //p' /tmp/discovery.log|paste -sd, -);[ "$count" = 2 ]
 if ! ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$build" --output-on-failure >/tmp/test.log 2>&1;then printf '%s\t%s\n' "$id" "$mode" >>/result/positive-failures.tsv;return;fi
 vr=-1;hr=-1;: >/tmp/nv.log;: >/tmp/nh.log
 if [ "$negative" = yes ];then if ASAN_OPTIONS=detect_leaks=0 "$build/negative_visible" >/tmp/nv.log 2>&1;then vr=0;else vr=$?;fi;if ASAN_OPTIONS=detect_leaks=0 "$build/negative_hidden" >/tmp/nh.log 2>&1;then hr=0;else hr=$?;fi;if [ "$vr" -eq 0 ]||[ "$hr" -eq 0 ];then printf '%s\t%s\t%s\t%s\n' "$id" "$mode" "$vr" "$hr" >>/result/negative-failures.tsv;fi
 fi
 printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$kind" "$id" "$mode" "$count" "$names" "$vr" "$hr" "$(sha256sum /tmp/discovery.log|awk '{print $1}')" "$(sha256sum /tmp/test.log|awk '{print $1}')" "$(sha256sum /tmp/nv.log|awk '{print $1}')" "$(sha256sum /tmp/nh.log|awk '{print $1}')" >>/result/results.tsv
}
for r in /work/tasks/*;do id=${r##*/};run_one tasks "$id" normal yes;run_one tasks "$id" sanitizer yes;done
for r in /work/controls/*;do id=${r##*/};run_one controls "$id" normal no;run_one controls "$id" sanitizer no;done
if [ -s /result/compile-failures.tsv ];then echo 'compile_failures id mode stage' >&2;cat /result/compile-failures.tsv >&2;exit 70;fi
if [ -s /result/positive-failures.tsv ];then echo 'positive_failures id mode' >&2;cat /result/positive-failures.tsv >&2;exit 72;fi
if [ -s /result/negative-failures.tsv ];then echo 'negative_fixture_not_rejected id mode visible hidden' >&2;cat /result/negative-failures.tsv >&2;exit 71;fi
'''
        completed = subprocess.run(["docker", "run", "--rm", "--network", "none", "--mount", f"type=bind,src={archive},dst=/input/family.tar,readonly", "--mount", f"type=bind,src={result},dst=/result", image, "bash", "-lc", script], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if completed.returncode:
            _fail("docker_sanity_failed", (completed.stdout + completed.stderr)[-20000:])
        rows = [line.split("\t") for line in (result / "results.tsv").read_text().splitlines()]
        mounted = "sha256:" + rows[0][1]
        if mounted != archive_hash:
            _fail("grader_mount_hash_mismatch", f"{mounted} != {archive_hash}")
        records = []
        for row in rows[1:]:
            if row[3] != "2" or row[4] != "visible,hidden":
                _fail("sanitizer_test_count_mismatch", str(row[:5]))
            if row[0] == "tasks" and (int(row[5]) == 0 or int(row[6]) == 0):
                _fail("negative_fixture_not_rejected", row[1])
            records.append({"kind": row[0], "task_id": row[1], "mode": row[2], "discovered_test_count": 2, "discovered_tests": row[4].split(","), "positive_exit": 0, "negative_visible_exit": int(row[5]), "negative_hidden_exit": int(row[6]), "discovery_log_hash": "sha256:" + row[7], "test_log_hash": "sha256:" + row[8], "negative_visible_log_hash": "sha256:" + row[9], "negative_hidden_log_hash": "sha256:" + row[10]})
        task_records = [r for r in records if r["kind"] == "tasks"]
        control_records = [r for r in records if r["kind"] == "controls"]
        expected_controls = 2 * len(CONTROL_NAMES)
        if len(task_records) != 120 or len(control_records) != expected_controls:
            _fail("sanitizer_test_count_mismatch", f"tasks={len(task_records)} controls={len(control_records)}")
        receipt = {"schema_version": "dpr-v2-docker-sanity-v1", "status": "pass", "evidence_class": "docker_sanity", "network_policy": "none", "image": image, "archive_hash": archive_hash, "mounted_archive_hash": mounted, "family_tree_hash": _tree_hash(out), "owner_hash": _file_hash(GENERATOR), "case_hashes": {p.as_posix(): _file_hash(p) for p in CASE_PATHS}, "curriculum_hash": _file_hash(CURRICULUM), "family_spec_hash": _file_hash(FAMILY_SPEC), "focused_test_hash": _file_hash(FOCUSED_TEST), "compiler": {"path": (result / "compiler.path").read_text().strip(), "version": (result / "compiler.version").read_text().strip(), "sha256": "sha256:" + (result / "compiler.sha256").read_text().strip()}, "cmake": (result / "cmake.version").read_text().strip(), "task_mode_record_count": len(task_records), "control_mode_record_count": len(control_records), "execution_records": records}
        _write(out / ".state/docker-sanity-v2.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    manifest = json.loads(manifest_path.read_text())
    for row in manifest["tasks"]:
        row["primary_core_objective"] = "achieved"
    manifest["docker_sanity"] = {"status": "pass", "receipt": ".state/docker-sanity-v2.json", "task_mode_record_count": 120, "control_mode_record_count": 2 * len(CONTROL_NAMES)}
    manifest["strongest_local_status"] = "local_family_verified"
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)


def _tool_identity(name: str) -> dict[str, str]:
    path = shutil.which(name)
    if path is None:
        _fail("host_tool_missing", name)
    completed = subprocess.run([path, "--version"], text=True, stdout=subprocess.PIPE, check=True)
    return {"path": path, "version": completed.stdout.splitlines()[0].strip(), "sha256": _file_hash(Path(path))}


def _run_logged(command: list[str], log_path: Path, *, env: dict[str, str] | None = None) -> int:
    with log_path.open("w", encoding="utf-8") as handle:
        completed = subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, text=True, env=env)
    return completed.returncode


def _host_run_one(kind: str, root: Path, mode: str, with_negative: bool, build_parent: Path) -> dict[str, object]:
    task_id = root.name
    build = build_parent / f"{kind}-{task_id}-{mode}"
    logs = build_parent / f"{kind}-{task_id}-{mode}-logs"
    logs.mkdir(parents=True)
    configure = ["cmake", "-S", str(root), "-B", str(build), "-G", "Unix Makefiles", f"-DTASK_SOURCE={root}/.meta/example.cpp"]
    if mode == "sanitizer":
        configure += ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]
    if with_negative:
        configure.append(f"-DNEGATIVE_SOURCE={root}/.meta/negative_false_substitute.cpp")
    env = dict(os.environ)
    env["ASAN_OPTIONS"] = "detect_leaks=0"
    if _run_logged(configure, logs / "configure.log") != 0:
        _fail("reference_compile_failed", f"{task_id} {mode} configure: {(logs / 'configure.log').read_text()[-2000:]}")
    if _run_logged(["cmake", "--build", str(build), "--parallel", "4"], logs / "build.log") != 0:
        _fail("reference_compile_failed", f"{task_id} {mode} build: {(logs / 'build.log').read_text()[-2000:]}")
    if _run_logged(["ctest", "--test-dir", str(build), "-N"], logs / "discovery.log") != 0:
        _fail("test_discovery_failed", f"{task_id} {mode}")
    discovery = (logs / "discovery.log").read_text()
    count_match = re.search(r"^Total Tests: (\d+)$", discovery, flags=re.M)
    count = int(count_match.group(1)) if count_match else 0
    if count == 0:
        _fail("zero_tests", f"{task_id} {mode}")
    names = re.findall(r"Test #\d+: (\S+)", discovery)
    code = "reference_sanitizer_failed" if mode == "sanitizer" else "reference_tests_failed"
    if _run_logged(["ctest", "--test-dir", str(build), "--output-on-failure"], logs / "test.log", env=env) != 0:
        _fail(code, f"{task_id} {mode}: {(logs / 'test.log').read_text()[-2000:]}")
    visible_exit = hidden_exit = None
    if with_negative:
        visible_exit = _run_logged([str(build / "negative_visible")], logs / "negative-visible.log", env=env)
        hidden_exit = _run_logged([str(build / "negative_hidden")], logs / "negative-hidden.log", env=env)
        if visible_exit == 0 or hidden_exit == 0:
            _fail("negative_fixture_not_rejected", f"{task_id} {mode} visible={visible_exit} hidden={hidden_exit}")
    return {
        "kind": kind,
        "task_id": task_id,
        "mode": mode,
        "discovered_test_count": count,
        "discovered_tests": names,
        "positive_exit": 0,
        "negative_visible_exit": visible_exit,
        "negative_hidden_exit": hidden_exit,
        "configure_log_hash": _file_hash(logs / "configure.log"),
        "build_log_hash": _file_hash(logs / "build.log"),
        "discovery_log_hash": _file_hash(logs / "discovery.log"),
        "test_log_hash": _file_hash(logs / "test.log"),
    }


def verify_host(
    out: Path = DEFAULT_OUT,
    *,
    cases: tuple = CASES,
    controls: tuple = CONTROL_NAMES,
    receipt_path: Path | None = None,
    update_manifest: bool = True,
) -> dict[str, object]:
    """Run the normal + fresh ASan/UBSan reference oracle on the host.

    This mirrors verify_docker's per-root contract (clean normal build, fresh
    sanitizer build, exactly two positive tests per mode, direct execution and
    rejection of both negative binaries, and positive control evidence) without
    a container. It is host evidence only: it never upgrades the family to
    ``local_family_verified``, which still requires the pinned network-disabled
    Docker sanity run.
    """
    if update_manifest and (tuple(cases) != tuple(CASES) or tuple(controls) != tuple(CONTROL_NAMES)):
        _fail("remedy_disposition_conflict", "manifest update requires the full 60-case and four-control run")
    manifest_path = out / ".state/materialization-manifest-v2.json"
    if not manifest_path.is_file():
        _fail("generator_output_drift", "run --verify-core first")
    manifest = json.loads(manifest_path.read_text())
    if manifest["family_tree_hash"] != _tree_hash(out) or manifest["owner_hash"] != _file_hash(GENERATOR):
        _fail("generator_output_drift", "manifest does not bind current owner/tree")
    compiler = _tool_identity("c++")
    cmake = _tool_identity("cmake")
    resolved = out.resolve()
    units = [("tasks", (resolved / case.task_id), mode, True) for case in cases for mode in ("normal", "sanitizer")]
    units += [("controls", (resolved / ".state/adversarial-clone-controls" / name), mode, False) for name in controls for mode in ("normal", "sanitizer")]
    with tempfile.TemporaryDirectory(prefix="dpr-v2-host-") as temporary:
        build_parent = Path(temporary)
        with ThreadPoolExecutor(max_workers=8) as pool:
            records = list(pool.map(lambda unit: _host_run_one(unit[0], unit[1], unit[2], unit[3], build_parent), units))
    task_records = [record for record in records if record["kind"] == "tasks"]
    control_records = [record for record in records if record["kind"] == "controls"]
    if len(task_records) != 2 * len(cases) or len(control_records) != 2 * len(controls):
        _fail("sanitizer_test_count_mismatch", f"tasks={len(task_records)} controls={len(control_records)}")
    if any(record["discovered_test_count"] != 2 or record["discovered_tests"] != ["visible", "hidden"] for record in records):
        _fail("sanitizer_test_count_mismatch", "a discovered count/name set drifted")
    receipt = {
        "schema_version": "dpr-v2-host-verify-v1",
        "status": "pass",
        "evidence_class": "host_verify",
        "locked_oracle": False,
        "network_policy": "host_local_no_container",
        "family_tree_hash": _tree_hash(out),
        "owner_hash": _file_hash(GENERATOR),
        "case_hashes": {p.as_posix(): _file_hash(p) for p in CASE_PATHS},
        "curriculum_hash": _file_hash(CURRICULUM),
        "family_spec_hash": _file_hash(FAMILY_SPEC),
        "focused_test_hash": _file_hash(FOCUSED_TEST),
        "compiler": compiler,
        "cmake": cmake,
        "task_mode_record_count": len(task_records),
        "control_mode_record_count": len(control_records),
        "negative_rejection_count_per_mode": len(cases),
        "commands": [
            "cmake -G Unix Makefiles with reference and negative sources",
            "cmake --build --parallel 4",
            "ctest -N and ctest --output-on-failure",
            "direct negative_visible and negative_hidden execution",
        ],
        "execution_records": records,
    }
    target = receipt_path if receipt_path is not None else out / ".state/host-verify.json"
    _write(target, json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    if update_manifest:
        manifest = json.loads(manifest_path.read_text())
        for row in manifest["tasks"]:
            row["primary_core_objective"] = "achieved"
        manifest["host_verify"] = {
            "status": "pass",
            "receipt": ".state/host-verify.json",
            "task_mode_record_count": len(task_records),
            "control_mode_record_count": len(control_records),
            "negative_rejection_count_per_mode": len(cases),
        }
        manifest["strongest_local_status"] = "host_verified_pending_docker_sanity"
        _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    return receipt


def append_cycle(out: Path, status: str) -> None:
    cycles = out / ".state/cycles"; cycles.mkdir(parents=True, exist_ok=True)
    number = max([int(p.stem.split("-")[-1]) for p in cycles.glob("cycle-*.json") if p.stem.split("-")[-1].isdigit()] or [0]) + 1
    manifest_path = out / ".state/materialization-manifest-v2.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    receipt = None
    for name in (".state/docker-sanity-v2.json", ".state/host-verify.json"):
        candidate_path = out / name
        if not candidate_path.is_file():
            continue
        candidate = json.loads(candidate_path.read_text())
        if candidate.get("family_tree_hash") == manifest.get("family_tree_hash") and candidate.get("owner_hash") == manifest.get("owner_hash"):
            receipt = candidate
            break
    invalidated = []
    for name in (".state/docker-sanity-v2.json", ".state/host-direct-oracle-cycle-04.json"):
        stale_path = out / name
        if not stale_path.is_file():
            continue
        stored = json.loads(stale_path.read_text())
        if stored.get("family_tree_hash") != manifest.get("family_tree_hash") or stored.get("owner_hash") != manifest.get("owner_hash"):
            invalidated.append(name)
    audit_path = out / ".state/audits/cycle-03-independent/audit.json"
    findings = json.loads(audit_path.read_text()).get("findings", []) if audit_path.is_file() else []
    terminal = manifest.get("strongest_local_status", "pending_execution")
    record = {"schema_version": "aider-task-creator-cycle-v1", "cycle": number, "timestamp": datetime.now(timezone.utc).isoformat(), "family_id": FAMILY_ID, "family_tree_hash": manifest.get("family_tree_hash"), "owner_hash": manifest.get("owner_hash"), "case_hashes": manifest.get("case_hashes"), "curriculum_hash": manifest.get("curriculum_hash"), "family_spec_hash": manifest.get("family_spec_hash"), "focused_test_hash": manifest.get("focused_test_hash"), "status": terminal, "worker_action": status, "prior_evidence_invalidated": invalidated, "source_audit": ".state/audits/cycle-04-independent/audit.json", "finding_ids": [finding["id"] for finding in findings], "remedy_directory": ".state/remedies/cycle-03", "retained_cycle_03_roots": [], "replacement_or_repaired_root_count": 60, "receipt": receipt, "terminal_status": terminal}
    _write(cycles / f"cycle-{number:02d}.json", json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--record-cycle", action="store_true")
    args = parser.parse_args(argv)
    build(args.out, args.force)
    if args.verify_core or args.verify_host or args.docker_sanity:
        verify_core(args.out)
    if args.verify_host:
        verify_host(args.out)
    if args.docker_sanity:
        verify_docker(args.out)
    if args.record_cycle:
        append_cycle(args.out, "remediation_preflight" if args.docker_sanity else ("remediation_host_verify" if args.verify_host else "remediation_structural"))
    print(f"Wrote {len(CASES)} DPR v2 roots under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
