"""Own the expansion-v1 rational and complex value-arithmetic family."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import replace
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Iterable, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import (
    TaskEvalError,
    WholeFormatError as WholeFormatError,
    build_prompt,
    load_task,
    parse_whole_file_blocks,
)
from w8_biayn.integrations.moonlight_rational_complex_cases import (
    COMPLEX_SUPPORT,
    GAUSSIAN_SUPPORT,
    RATIONAL_SUPPORT,
    ArithmeticCase,
    TASKS,
)


DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/numerical-anchors/"
    "rational-complex-value-arithmetic"
)
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-numerical/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_RATIONAL_COMPLEX_ARITHMETIC_CURRICULUM.md"
)
FAMILY_SPEC = Path(
    "docs/aider-tasks-spec/aider-numerical/"
    "rational-complex-value-arithmetic-expansion.md"
)
OWNER = "src/w8_biayn/integrations/moonlight_rational_complex_arithmetic_expansion.py"
CASE_OWNER = "src/w8_biayn/integrations/moonlight_rational_complex_cases.py"
FOCUSED_TEST = "tests/test_moonlight_rational_complex_arithmetic_expansion.py"
FAMILY_ID = "expansion-v1-rational-complex-value-arithmetic-v1"
SELECTED_PROMPTS = (
    "docs/aider-tasks-spec/prompts/generate-family-spec.md",
    "docs/aider-tasks-spec/prompts/implement-family-for-sft.md",
)
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
NORMALIZER = "rational-complex-emitted-artifacts-v1"
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
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
    """A fail-closed creator or verifier gate did not pass."""


def _fail(code: str, detail: str = "") -> None:
    raise VerificationError(f"{code}: {detail}" if detail else code)


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _tree_hash(root: Path, *, include_state: bool = False) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "sha256:absent"
    files = (
        item
        for item in root.rglob("*")
        if item.is_file() and (include_state or ".state" not in item.parts)
    )
    for path in sorted(files):
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def _control_bundle_hash(root: Path) -> str:
    lines: list[str] = []
    files = (
        path
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    )
    for path in sorted(files):
        lines.append(
            f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
            f"{path.relative_to(root).as_posix()}\n"
        )
    return "sha256:" + hashlib.sha256("".join(lines).encode()).hexdigest()


def _portable_tree_hash(root: Path) -> str:
    lines: list[str] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file() and ".state" not in item.parts):
        lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(root).as_posix()}\n")
    return "sha256:" + hashlib.sha256("".join(lines).encode()).hexdigest()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, value: object) -> None:
    _write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _header(case: ArithmeticCase) -> str:
    filename = f"{case.task_id}.h"
    guard = re.sub(r"[^A-Z0-9]", "_", filename.upper()) + "_"
    base_type = {
        "rational": "struct Rational { long long numerator; long long denominator; };",
        "gaussian": "struct Gaussian { long long real; long long imag; };",
        "complex": "struct ComplexValue { long double real; long double imag; };",
    }[case.domain]
    type_name = {"rational": "Rational", "gaussian": "Gaussian", "complex": "ComplexValue"}[case.domain]
    declarations = case.extra_header
    if f"struct {type_name} " not in declarations:
        declarations = f"{base_type} {declarations}".rstrip()
    return f'''#ifndef {guard}
#define {guard}
#include <cstddef>
#include <optional>
#include <string>
#include <vector>
namespace rational_complex_curriculum {{
{declarations}
class {case.class_name} {{ public: {case.declaration}; }};
}}  // namespace rational_complex_curriculum
#endif
'''


def _support(case: ArithmeticCase) -> str:
    if case.domain == "rational":
        support = RATIONAL_SUPPORT
    elif case.domain == "gaussian":
        support = GAUSSIAN_SUPPORT
    else:
        support = COMPLEX_SUPPORT
    return re.sub(
        r"(?m)^(?=(?:bool |std::optional<|C |G |long double ))",
        "[[maybe_unused]] ",
        support,
    )


def _reference(case: ArithmeticCase, *, negative: bool = False) -> str:
    body = case.negative_core if negative else case.core
    body = re.sub(r"(return [^;]+;)(?=[A-Za-z_+\-])", r"\1\n", body)
    body = re.sub(r"((?:break|continue);)(?=[A-Za-z_+\-])", r"\1\n", body)
    body = re.sub(r";(?=(?:if|for|while|return)\b)", ";\n", body)
    return f'''#include "{case.task_id}.h"
#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <limits>
#include <map>
#include <numeric>
#include <queue>
#include <string>
#include <utility>
#include <vector>
namespace rational_complex_curriculum {{
{_support(case)}
{case.signature.format(cls=case.class_name)} {{
// CORE_BEGIN: {case.mechanism}
{body}
// CORE_END
}}
}}  // namespace rational_complex_curriculum
'''


def _starter(case: ArithmeticCase) -> str:
    signature = case.signature.format(cls=case.class_name)
    parameter_names = re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*(?:,|\))", signature.split("::", 1)[1])
    unused = "".join(f"static_cast<void>({name});" for name in parameter_names)
    return f'''#include "{case.task_id}.h"
namespace rational_complex_curriculum {{
{signature} {{ {unused} return std::nullopt; }}
}}  // namespace rational_complex_curriculum
'''


def _test_support(case: ArithmeticCase) -> str:
    if case.domain == "rational":
        return "[[maybe_unused]] bool same(Rational a,Rational b){return a.numerator*b.denominator==b.numerator*a.denominator;}"
    if case.domain == "gaussian":
        return "[[maybe_unused]] bool same(Gaussian a,Gaussian b){return a.real==b.real&&a.imag==b.imag;} [[maybe_unused]] bool contains(const std::vector<Gaussian>&v,Gaussian x){return std::find_if(v.begin(),v.end(),[&](Gaussian y){return same(x,y);})!=v.end();}"
    return "[[maybe_unused]] bool close(ComplexValue a,ComplexValue b){return std::fabs(a.real-b.real)<=1e-10L&&std::fabs(a.imag-b.imag)<=1e-10L;}"


def _test_source(case: ArithmeticCase, *, hidden: bool) -> str:
    body = case.hidden_test if hidden else case.visible_test
    return f'''#include "{case.task_id}.h"
#include <algorithm>
#include <cmath>
#include <limits>
#include <vector>
using namespace rational_complex_curriculum;
namespace {{ {_test_support(case)} }}
int main() {{ {body} }}
'''


def _instructions(case: ArithmeticCase) -> str:
    numeric_policy = (
        f"\n## Numerical policy\n\n{case.numeric_policy}\n"
        if case.numeric_policy
        else ""
    )
    return f'''# Instructions

## Public API

Implement `{case.declaration}` on class `{case.class_name}` in namespace
`rational_complex_curriculum`.

## Mechanism

{case.mechanism}. Implement this mechanism directly: a generic library, a
precomputed answer, or `{case.negative_name}` cannot reproduce the documented
behavior.

## Valid behavior

{case.valid_behavior}

## Examples

The visible check exercises these cases:

```cpp
{case.visible_test}
```

## Invalid and boundary behavior

{case.invalid_behavior} Return `std::nullopt` for every rejected input and do
not partially publish a result.
{numeric_policy}

## Mutation, ordering, and ties

{case.ordering_behavior}

All rational results are reduced with positive denominators. All floating
complex inputs and results are finite and component comparisons use absolute
tolerance `1e-10L`. Use C++17 and standard-library facilities only.
'''


def _cmake(case: ArithmeticCase) -> str:
    return f'''cmake_minimum_required(VERSION 3.16)
project({case.task_id.replace('-', '_')} LANGUAGES CXX)
enable_testing()
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
add_library(solution {case.task_id}.cpp)
target_include_directories(solution PUBLIC ${{CMAKE_CURRENT_SOURCE_DIR}})
target_compile_options(solution PRIVATE -Wall -Wextra -Wpedantic -Werror)
if(SANITIZE)
  target_compile_options(solution PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
  target_link_options(solution PRIVATE -fsanitize=address,undefined)
endif()
foreach(kind IN ITEMS visible hidden)
  if(kind STREQUAL "visible")
    set(test_source task_visible_test.cpp)
  else()
    set(test_source .meta/task_hidden_test.cpp)
  endif()
  add_executable(${{kind}} ${{test_source}})
  target_link_libraries(${{kind}} PRIVATE solution)
  target_compile_options(${{kind}} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  if(SANITIZE)
    target_compile_options(${{kind}} PRIVATE -fsanitize=address,undefined -fno-omit-frame-pointer)
    target_link_options(${{kind}} PRIVATE -fsanitize=address,undefined)
  endif()
  add_test(NAME ${{kind}} COMMAND ${{kind}})
endforeach()
'''


def _task_files(case: ArithmeticCase) -> dict[str, str]:
    config = {
        "authors": ["w8-biayn"],
        "blurb": case.title,
        "files": {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "schema_version": "aider-local-provenance-v2",
        "task_id": case.task_id,
        "family_id": FAMILY_ID,
        "lineage": "new-root",
        "source_document": str(CURRICULUM),
        "family_specification": str(FAMILY_SPEC),
        "authoring_origin": "clean-room deterministic repository generator",
        "license": "Apache-2.0",
        "generator": OWNER,
        "case_owner": CASE_OWNER,
        "selected_prompts": list(SELECTED_PROMPTS),
        "status": "local candidate; not dataset admission",
    }
    tests_toml = f'''[visible]
description = "Public normal and ordering behavior for {case.task_id}"

[hidden]
description = "Invalid, boundary, tie, and adversarial behavior for {case.task_id}"

[negative]
fixture = "{case.negative_name}"
expected = "compiles cleanly and is rejected by an executed task test"
'''
    return {
        ".docs/introduction.md": (
            f"# {case.title}\n\n"
            "Fractions and complex numbers are the exact arithmetic of "
            "engineering: ratios of integers kept in lowest terms, points on "
            "the complex plane, values that must stay reduced and finite. "
            "Working with them directly, with no floating-point shortcuts, is "
            "how small numeric errors stay visible instead of compounding "
            "silently.\n\n"
            "This exercise is about one such value type and its defining "
            "operation.\n"
        ),
        ".docs/instructions.md": _instructions(case),
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": tests_toml,
        ".meta/example.h": _header(case),
        ".meta/example.cpp": _reference(case),
        ".meta/negative_false_substitute.cpp": _reference(case, negative=True),
        ".meta/task_hidden_test.cpp": _test_source(case, hidden=True),
        f"{case.task_id}.h": _header(case),
        f"{case.task_id}.cpp": _starter(case),
        "task_visible_test.cpp": _test_source(case, hidden=False),
        "CMakeLists.txt": _cmake(case),
    }


def _task_inventory(root: Path, *, exclude: Path | None = None) -> dict[str, Path]:
    inventory: dict[str, Path] = {}
    if not root.is_dir():
        return inventory
    excluded = exclude.resolve() if exclude and exclude.exists() else None
    for config in root.rglob(".meta/config.json"):
        if ".state" in config.parts:
            continue
        task = config.parent.parent
        if excluded and (task.resolve() == excluded or excluded in task.resolve().parents):
            continue
        key = task.name
        if key in inventory:
            key = f"{task.name}@@{task.relative_to(root).as_posix()}"
        inventory[key] = task
    return inventory


def _safe_output(out: Path) -> Path:
    for candidate in (out, *out.parents):
        if candidate.exists() and candidate.is_symlink():
            _fail("unsafe_output_root", f"symlink:{candidate}")
    resolved = out.resolve()
    expansion = EXPANSION_ROOT.resolve()
    if resolved == LEGACY_ROOT.resolve() or resolved == REVERIFY_ROOT.resolve():
        _fail("unsafe_output_root", str(out))
    if expansion not in resolved.parents:
        _fail("unsafe_output_root", str(out))
    expected_suffix = Path("numerical-anchors/rational-complex-value-arithmetic")
    if resolved != (expansion / expected_suffix).resolve():
        _fail("unsafe_output_root", str(out))
    return resolved


def _freeze_inventory(out: Path) -> dict[str, object]:
    inventories = {
        "legacy": _task_inventory(LEGACY_ROOT),
        "reverify": _task_inventory(REVERIFY_ROOT),
        "expansion": _task_inventory(EXPANSION_ROOT, exclude=out),
    }
    candidate_ids = {case.task_id for case in TASKS}
    existing_ids = {
        inventory_key.split("@@", 1)[0]
        for items in inventories.values()
        for inventory_key in items
    }
    collisions = sorted(candidate_ids & existing_ids)
    if collisions:
        _fail("cross_tree_id_collision", ",".join(collisions))
    records: list[dict[str, object]] = []
    for tree, items in inventories.items():
        for inventory_key, path in sorted(items.items()):
            records.append(
                _snapshot_record(
                    tree=tree,
                    inventory_key=inventory_key,
                    task_id=path.name,
                    path=path,
                )
            )
    inventory_hash = _sha256("".join(f"{r['tree']}\0{r['task_id']}\0{r['tree_hash']}\n" for r in records).encode())
    semantic_snapshot_hash = _semantic_snapshot_hash(records)
    return {
        "schema_version": 2,
        "counts": {name: len(items) for name, items in inventories.items()},
        "records": records,
        "inventory_hash": inventory_hash,
        "semantic_snapshot_hash": semantic_snapshot_hash,
        "semantic_snapshot_record_count": len(records),
        "semantic_snapshot_policy": {
            "normalizer": NORMALIZER,
            "stores_task_source_bytes": False,
            "record_fields": [
                "tree_hash",
                "semantic_payload_hash",
                "semantic_tokens",
                "semantic_token_hash",
                "prompt_hash",
                "reference_hash",
                "weighted_selection_signature",
            ],
        },
        "candidate_count": len(TASKS),
        "id_collisions": [],
    }


def _owned_reset(out: Path) -> None:
    if not out.exists():
        return
    owner_record = out / ".state/owner.json"
    if not owner_record.is_file():
        _fail("unsafe_output_root", "existing output lacks owner record")
    if json.loads(owner_record.read_text()).get("owner") != OWNER:
        _fail("unsafe_output_root", "foreign owner")
    for child in out.iterdir():
        if child.name == ".state":
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    state = out / ".state"
    for child in state.iterdir():
        if child.name in {"cycles", "audits", "remedy", "source-inventory-snapshots"}:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def materialize(out: Path, *, force: bool = False) -> dict[str, object]:
    out = _safe_output(out)
    if out.exists() and any(out.iterdir()) and not force:
        _fail("output_exists", str(out))
    if force:
        _owned_reset(out)
    out.mkdir(parents=True, exist_ok=True)
    state = out / ".state"
    _write_json(state / "owner.json", {"family_id": FAMILY_ID, "owner": OWNER})
    inventory = _freeze_inventory(out)
    _write_json(state / "source-inventory.json", inventory)
    proposals = [
        {
            "proposal_id": f"proposal-{index:02d}",
            "task_id": case.task_id,
            "domain": case.domain,
            "mechanism": case.mechanism,
            "decision": "selected-new-root",
        }
        for index, case in enumerate(TASKS, 1)
    ]
    raw_proposals = proposals + [
        {
            "proposal_id": "proposal-rejected-rational-weighted-median",
            "task_id": "rational-weighted-median",
            "domain": "rational",
            "mechanism": "stable value ordering and exact cumulative half-weight selection",
            "decision": "rejected-semantic-duplicate",
            "duplicate_of": "weighted-median-mark",
            "replacement_id": "rational-amortization-schedule",
            "finding_id": "RC-AUD-008",
        }
    ]
    _write_json(state / "raw-proposals.json", {"schema_version": 1, "proposals": raw_proposals})
    _write_json(
        state / "selected-manifest.json",
        {
            "schema_version": 1,
            "family_id": FAMILY_ID,
            "requested_count": 40,
            "retained_count": 40,
            "tasks": proposals,
        },
    )
    _write_json(
        state / "rejected-proposals.json",
        {
            "schema_version": 1,
            "rejected": [
                {"proposal_id": "control-domain-identifier-renamed", "reason": "adversarial clone control"},
                {"proposal_id": "control-constants-policy-only", "reason": "adversarial clone control"},
                {"proposal_id": "control-opposite-end-selection", "reason": "adversarial clone control"},
                {"proposal_id": "control-representation-changed-weighted-selection", "reason": "semantic clone control"},
                {
                    "proposal_id": "proposal-rejected-rational-weighted-median",
                    "task_id": "rational-weighted-median",
                    "reason": "semantic duplicate of weighted-median-mark",
                    "finding_id": "RC-AUD-008",
                    "replacement_id": "rational-amortization-schedule",
                },
            ],
        },
    )
    for case in TASKS:
        root = out / case.task_id
        for relative, content in _task_files(case).items():
            _write(root / relative, content)
    manifest = {
        "schema_version": 1,
        "family_id": FAMILY_ID,
        "owner": OWNER,
        "case_owner": CASE_OWNER,
        "root_count": 40,
        "roots": [
            {"task_id": case.task_id, "tree_hash": _tree_hash(out / case.task_id)} for case in TASKS
        ],
    }
    _write_json(state / "materialization-manifest.json", manifest)
    return {"tasks": 40, "family_tree_hash": _tree_hash(out), "inventory": inventory["counts"]}


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    if marker not in text:
        return ""
    tail = text.split(marker, 1)[1]
    return tail.split("\n## ", 1)[0]


def _core(text: str) -> str:
    if "// CORE_BEGIN" not in text or "// CORE_END" not in text:
        return ""
    return text.split("// CORE_BEGIN", 1)[1].split("// CORE_END", 1)[0]


def _normalized_tokens(text: str, root_name: str) -> set[str]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " literal ", text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", " literal ", text)
    text = re.sub(r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[LlUuFf]*\b", " number ", text)
    text = text.lower()
    class_name = "".join(part.title() for part in root_name.split("-")).lower()
    for variant in (root_name.lower(), root_name.lower().replace("-", "_"), class_name):
        text = text.replace(variant, " taskid ")
    text = re.sub(r"\b(?:rational|complex|gaussian)\b", " domain ", text)
    tokens = re.findall(r"[a-z_]+|==|!=|<=|>=|&&|\|\||[+*/%<>-]", text)
    stop = {"the", "and", "or", "a", "an", "to", "of", "in", "for", "with", "return", "std", "const"}
    return {token for token in tokens if token not in stop and len(token) > 1}


def _control_signature(text: str) -> tuple[int, ...]:
    return (
        text.count("for("), text.count("while("), text.count("if("),
        text.count("std::sort"), text.count("std::queue"), text.count("std::map"),
        text.count("mul_r"), text.count("div_r"), text.count("mul_c"), text.count("div_c"),
        text.count("push_back"), text.count("std::nullopt"),
        text.count("std::vector"), text.count("std::optional"), text.count("std::string"),
        text.count("->"), text.count("["), text.count("{"), text.count(","),
        text.count("||"), text.count("&&"), text.count("=="), text.count("!="),
    )


def _feature_scopes(root: Path) -> dict[str, tuple[set[str], tuple[int, ...]]]:
    config = json.loads((root / ".meta/config.json").read_text())
    task_id = Path(config["files"]["solution"][0]).stem
    instructions = (root / ".docs/instructions.md").read_text()
    header = (root / config["files"]["solution"][0]).read_text()
    reference = (root / ".meta/example.cpp").read_text()
    visible = (root / "task_visible_test.cpp").read_text()
    hidden = (root / ".meta/task_hidden_test.cpp").read_text()
    negative = (root / ".meta/negative_false_substitute.cpp").read_text()
    core = _core(reference)
    scopes = {
        "public_api": header + _section(instructions, "Public API"),
        "owned_state_or_algorithm": _section(instructions, "Mechanism") + core,
        "mutation_selection_rules": _section(instructions, "Mutation, ordering, and ties") + visible,
        "invalid_boundary_behavior": _section(instructions, "Invalid and boundary behavior") + hidden,
        "reference_control_flow": core,
        "deterministic_oracle": visible + hidden,
        "topic_negative_fixture": _core(negative),
    }
    return {name: (_normalized_tokens(value, task_id), _control_signature(value)) for name, value in scopes.items()}


def _pair_decision(left: Path, right: Path) -> dict[str, object]:
    lf = _feature_scopes(left)
    rf = _feature_scopes(right)
    dimensions: dict[str, object] = {}
    for name in HARD_RULE_DIMENSIONS:
        left_tokens, left_signature = lf[name]
        right_tokens, right_signature = rf[name]
        union = left_tokens | right_tokens
        overlap = len(left_tokens & right_tokens) / len(union) if union else 1.0
        symmetric = len(left_tokens ^ right_tokens)
        structural = left_signature != right_signature
        if name in {"public_api", "deterministic_oracle"}:
            distinct = symmetric >= 2 and overlap <= 0.94
        else:
            distinct = symmetric >= 3 and overlap <= 0.94 and (structural or symmetric >= 6)
        dimensions[name] = {
            "overlap": round(overlap, 6),
            "symmetric_difference": symmetric,
            "left_structure": list(left_signature),
            "right_structure": list(right_signature),
            "distinct": distinct,
        }
    return {
        "left": Path(json.loads((left / ".meta/config.json").read_text())["files"]["solution"][0]).stem,
        "right": Path(json.loads((right / ".meta/config.json").read_text())["files"]["solution"][0]).stem,
        "dimensions": dimensions,
        "pass": all(record["distinct"] for record in dimensions.values()),
    }


def _renamed_control(base: ArithmeticCase, task_id: str, **changes: object) -> ArithmeticCase:
    renamed = replace(base, task_id=task_id, **changes)
    return replace(
        renamed,
        visible_test=renamed.visible_test.replace(base.class_name, renamed.class_name),
        hidden_test=renamed.hidden_test.replace(base.class_name, renamed.class_name),
    )


def _weighted_selection_clone_case() -> ArithmeticCase:
    return ArithmeticCase(
        "control-rational-weighted-selection",
        "Representation-changed exact weighted selection",
        "rational",
        "stable rational-value ordering and exact cumulative half-weight selection",
        "std::optional<Rational> select(std::vector<WeightedSample> samples) const",
        "std::optional<Rational> {cls}::select(std::vector<WeightedSample> samples) const",
        r'''if(samples.empty())return std::nullopt;R total{0,1};for(auto&sample:samples){auto value=normalized(sample.value),weight=normalized(sample.weight);auto positive=weight?cmp_r(*weight,{0,1}):std::nullopt;if(!value||!weight||!positive||*positive<=0)return std::nullopt;sample.value=*value;sample.weight=*weight;auto next=add_r(total,*weight);if(!next)return std::nullopt;total=*next;}std::stable_sort(samples.begin(),samples.end(),[](const auto&a,const auto&b){auto c=cmp_r(a.value,b.value);return c&&(*c<0||(*c==0&&a.original_index<b.original_index));});R cumulative{0,1};for(const auto&sample:samples){auto next=add_r(cumulative,sample.weight);if(!next)return std::nullopt;cumulative=*next;auto doubled=mul_r(cumulative,{2,1});auto reached=doubled?cmp_r(*doubled,total):std::nullopt;if(!reached)return std::nullopt;if(*reached>=0)return sample.value;}return std::nullopt;''',
        r'''if(samples.empty())return std::nullopt;std::sort(samples.begin(),samples.end(),[](const auto&a,const auto&b){auto c=cmp_r(a.value,b.value);return c&&*c<0;});return normalized(samples[samples.size()/2].value);''',
        "auto r=ControlRationalWeightedSelection{}.select({{{1,1},{1,10},0},{{2,1},{7,10},1},{{9,1},{1,5},2}});return !r||!same(*r,{2,1});",
        "auto x=ControlRationalWeightedSelection{};auto lower=x.select({{{1,1},{1,2},1},{{4,1},{1,2},0}});return !lower||!same(*lower,{1,1})||x.select({{{1,0},{1,1},0}})||x.select({{{1,1},{0,1},0}})||x.select({});",
        "Sort exact rational samples and select the first cumulative positive weight reaching half the total.",
        "Reject empty input, invalid values, nonpositive weights, or overflow.",
        "Sort by rational value then original index; exact half selects the lower value.",
        "ordinary-unweighted-median",
        "struct WeightedSample { Rational value; Rational weight; std::size_t original_index; };",
    )


def _weighted_selection_signature(root: Path) -> bool:
    payload = _semantic_payload(root).lower().replace("_", "-")
    groups = (
        ("weight",),
        ("sort", "order"),
        ("cumulative",),
        ("half",),
        ("first", "lower"),
    )
    return all(any(token in payload for token in alternatives) for alternatives in groups)


def _control_cases() -> tuple[tuple[str, ArithmeticCase], ...]:
    base = TASKS[0]
    domain = _renamed_control(
        base,
        "control-ledger-recurrence",
        title="Ledger ratio recurrence",
        mechanism="second-order ledger numerator/denominator recurrence emitting every checkpoint",
    )
    constants = _renamed_control(
        base,
        "control-short-convergents",
        title="Short continued-fraction convergents",
        visible_test="auto r=RationalContinuedFractionConvergents{}.convergents({2,3});return !r||r->size()!=2||!same((*r)[0],{2,1})||!same((*r)[1],{7,3});",
        valid_behavior=base.valid_behavior + " This policy example uses two coefficients instead of three.",
    )
    opposite_core = base.core.rsplit("return out;", 1)[0] + "std::reverse(out.begin(),out.end());return out;"
    opposite = _renamed_control(
        base,
        "control-reverse-convergents",
        title="Reverse continued-fraction convergents",
        core=opposite_core,
        visible_test=base.visible_test.replace("(*r)[0],{1,1}", "(*r)[0],{7,5}").replace("(*r)[2],{7,5}", "(*r)[2],{1,1}"),
        ordering_behavior="Emit the final convergent first and the initial convergent last.",
    )
    return (
        ("domain-identifier-renamed", domain),
        ("constants-policy-only", constants),
        ("opposite-end-selection", opposite),
        ("representation-changed-weighted-selection", _weighted_selection_clone_case()),
    )


def _materialize_controls(out: Path) -> list[dict[str, object]]:
    controls_root = out / ".state/adversarial-clone-controls"
    if controls_root.exists():
        shutil.rmtree(controls_root)
    records: list[dict[str, object]] = []
    base_root = out / TASKS[0].task_id
    base_hashes = {relative: _sha256(content.encode()) for relative, content in _task_files(TASKS[0]).items()}
    for name, case in _control_cases():
        root = controls_root / name
        files = _task_files(case)
        for relative, content in files.items():
            _write(root / relative, content)
        changed = sum(base_hashes.get(relative) != _sha256(content.encode()) for relative, content in files.items())
        if name == "representation-changed-weighted-selection":
            existing = (
                EXPANSION_ROOT
                / "numerical-arithmetic/overflow-scoring-combinatorial/weighted-median-mark"
            )
            if not existing.is_dir() or not _weighted_selection_signature(root) or not _weighted_selection_signature(existing):
                _fail("adversarial_clone_not_rejected", f"{name}:semantic-signature")
            raw_decision = _pair_decision(existing, root)
            decision = {
                **raw_decision,
                "raw_pair_pass": raw_decision["pass"],
                "pass": False,
                "semantic_rule": "representation-invariant-stable-weighted-cumulative-half-selection",
                "semantic_target": "weighted-median-mark",
            }
        else:
            decision = _pair_decision(base_root, root)
        if changed == 0:
            _fail("adversarial_clone_no_change", name)
        if decision["pass"]:
            _fail("adversarial_clone_not_rejected", name)
        records.append(
            {
                "name": name,
                "task_id": case.task_id,
                "tree_hash": _tree_hash(root, include_state=True),
                "changed_file_count": changed,
                "comparison": decision,
                "coherent_build": "pending_docker_sanity",
            }
        )
    bundle_hash = _control_bundle_hash(controls_root)
    _write_json(
        controls_root / "manifest.json",
        {"schema_version": 1, "control_bundle_hash": bundle_hash, "controls": records},
    )
    return records


def _semantic_payload(root: Path) -> str:
    pieces: list[str] = []
    for relative in (
        ".docs/introduction.md", ".docs/instructions.md", ".meta/example.cpp",
        ".meta/task_hidden_test.cpp", "task_visible_test.cpp",
    ):
        path = root / relative
        if path.is_file():
            pieces.append(_core(path.read_text()) if path.name == "example.cpp" else path.read_text())
    headers = sorted(root.glob("*.h"))
    if headers:
        pieces.append(headers[0].read_text())
    return "\n".join(pieces)


def _snapshot_record(
    *, tree: str, inventory_key: str, task_id: str, path: Path
) -> dict[str, object]:
    semantic_payload = _semantic_payload(path)
    semantic_tokens = sorted(_normalized_tokens(semantic_payload, task_id))
    reference_path = path / ".meta/example.cpp"
    reference_bytes = reference_path.read_bytes() if reference_path.is_file() else b""
    return {
        "tree": tree,
        "task_id": task_id,
        "inventory_key": inventory_key,
        "path": str(path),
        "tree_hash": _tree_hash(path),
        "semantic_payload_hash": _sha256(semantic_payload.encode()),
        "semantic_tokens": semantic_tokens,
        "semantic_token_hash": _sha256("\0".join(semantic_tokens).encode()),
        "prompt_hash": _snapshot_prompt_hash(path),
        "reference_hash": _sha256(reference_bytes),
        "weighted_selection_signature": _weighted_selection_signature(path),
    }


def _snapshot_prompt_hash(root: Path) -> str:
    try:
        return _sha256(build_prompt(load_task(root)).encode())
    except (TaskEvalError, WholeFormatError, json.JSONDecodeError):
        pieces: list[str] = []
        for relative in (".docs/introduction.md", ".docs/instructions.md"):
            path = root / relative
            pieces.append(f"{relative}\0{path.read_text() if path.is_file() else ''}")
        config_path = root / ".meta/config.json"
        solution: list[str] = []
        if config_path.is_file():
            try:
                config = json.loads(config_path.read_text())
                configured = config.get("files", {}).get("solution", [])
                if isinstance(configured, list):
                    solution = [item for item in configured if isinstance(item, str)]
            except json.JSONDecodeError:
                pass
        for relative in solution:
            path = root / relative
            pieces.append(f"{relative}\0{path.read_text() if path.is_file() else '<missing>'}")
        return _sha256("\n".join(pieces).encode())


def _semantic_snapshot_hash(records: Iterable[dict[str, object]]) -> str:
    canonical = [
        {
            key: record[key]
            for key in (
                "tree",
                "task_id",
                "inventory_key",
                "tree_hash",
                "semantic_payload_hash",
                "semantic_token_hash",
                "prompt_hash",
                "reference_hash",
                "weighted_selection_signature",
            )
        }
        for record in records
    ]
    return _sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    )


def _validate_snapshot_record(record: dict[str, object]) -> set[str]:
    raw_tokens = record.get("semantic_tokens")
    if not isinstance(raw_tokens, list) or not all(
        isinstance(token, str) for token in raw_tokens
    ):
        _fail("external_inventory_snapshot_invalid", str(record.get("task_id")))
    tokens = list(raw_tokens)
    if tokens != sorted(set(tokens)):
        _fail("external_inventory_snapshot_invalid", str(record.get("task_id")))
    if record.get("semantic_token_hash") != _sha256("\0".join(tokens).encode()):
        _fail("external_inventory_snapshot_invalid", str(record.get("task_id")))
    return set(tokens)


def _overlap(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def _screen_external(
    out: Path,
    inventory: Iterable[dict[str, object]],
    *,
    threshold: float,
    failure_code: str,
) -> tuple[int, list[dict[str, object]], list[dict[str, object]]]:
    external = [
        (
            str(record["task_id"]),
            _validate_snapshot_record(record),
            str(record["prompt_hash"]),
            str(record["reference_hash"]),
            bool(record["weighted_selection_signature"]),
        )
        for record in inventory
    ]
    comparisons = 0
    maxima: list[dict[str, object]] = []
    flagged: list[dict[str, object]] = []
    for case in TASKS:
        candidate_root = out / case.task_id
        candidate_tokens = _normalized_tokens(_semantic_payload(candidate_root), case.task_id)
        candidate_prompt_hash = _snapshot_prompt_hash(candidate_root)
        candidate_reference_hash = _sha256(
            (candidate_root / ".meta/example.cpp").read_bytes()
        )
        candidate_is_weighted_selection = _weighted_selection_signature(candidate_root)
        best_id = ""
        best_score = -1.0
        for task_id, tokens, prompt_hash, reference_hash, weighted_selection in external:
            comparisons += 1
            score = _overlap(candidate_tokens, tokens)
            if score > best_score:
                best_id, best_score = task_id, score
            if score >= threshold:
                flagged.append({"candidate": case.task_id, "external": task_id, "overlap": round(score, 6)})
            if candidate_prompt_hash == prompt_hash:
                flagged.append(
                    {
                        "candidate": case.task_id,
                        "external": task_id,
                        "exact_match": "prompt",
                    }
                )
            if candidate_reference_hash == reference_hash:
                flagged.append(
                    {
                        "candidate": case.task_id,
                        "external": task_id,
                        "exact_match": "reference",
                    }
                )
            if candidate_is_weighted_selection and weighted_selection:
                flagged.append(
                    {
                        "candidate": case.task_id,
                        "external": task_id,
                        "overlap": round(score, 6),
                        "semantic_rule": "representation-invariant-stable-weighted-cumulative-half-selection",
                    }
                )
        maxima.append({"candidate": case.task_id, "nearest": best_id, "overlap": round(max(best_score, 0.0), 6)})
    if flagged:
        _fail(failure_code, json.dumps(flagged[:5], sort_keys=True))
    return comparisons, maxima, flagged


def verify_core(out: Path) -> dict[str, object]:
    out = _safe_output(out)
    expected = {case.task_id for case in TASKS}
    actual = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", f"missing={sorted(expected-actual)} extra={sorted(actual-expected)}")
    manifest = json.loads((out / ".state/materialization-manifest.json").read_text())
    if manifest.get("root_count") != 40 or {item["task_id"] for item in manifest["roots"]} != expected:
        _fail("generator_output_drift", "materialization manifest")
    prompt_records: list[dict[str, object]] = []
    prompt_hashes: dict[str, str] = {}
    reference_hashes: dict[str, str] = {}
    for case in TASKS:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        solution = config.get("files", {}).get("solution")
        if solution != [f"{case.task_id}.h", f"{case.task_id}.cpp"]:
            _fail("target_reference_mismatch", case.task_id)
        if set(solution) & set(config["files"]["test"]):
            _fail("unsafe_path", case.task_id)
        prompt = build_prompt(load_task(root))
        for private in (
            "CMakeLists.txt", "provenance.json", "example.cpp", "task_hidden_test",
            "negative_false", ".state", "tests.toml",
        ):
            if private in prompt:
                _fail("prompt_contract_incomplete", f"{case.task_id}:{private}")
        if not all(filename in prompt for filename in solution):
            _fail("prompt_contract_incomplete", case.task_id)
        response = "\n\n".join(
            f"{filename}\n```cpp\n{(root / '.meta' / ('example.h' if filename.endswith('.h') else 'example.cpp')).read_text().rstrip()}\n```"
            for filename in solution
        )
        if set(parse_whole_file_blocks(response)) != set(solution):
            _fail("whole_format_failed", case.task_id)
        prompt_hash = _sha256(prompt.encode())
        reference_hash = _sha256((root / ".meta/example.cpp").read_bytes())
        if prompt_hash in prompt_hashes:
            _fail("duplicate_task", f"prompt:{prompt_hashes[prompt_hash]}:{case.task_id}")
        if reference_hash in reference_hashes:
            _fail("duplicate_task", f"reference:{reference_hashes[reference_hash]}:{case.task_id}")
        prompt_hashes[prompt_hash] = case.task_id
        reference_hashes[reference_hash] = case.task_id
        prompt_records.append(
            {
                "task_id": case.task_id,
                "prompt_hash": prompt_hash,
                "starter_hashes": [_sha256((root / filename).read_bytes()) for filename in solution],
                "reference_hash": reference_hash,
                "visible_test_hash": _sha256((root / "task_visible_test.cpp").read_bytes()),
                "hidden_test_hash": _sha256((root / ".meta/task_hidden_test.cpp").read_bytes()),
                "negative_hash": _sha256((root / ".meta/negative_false_substitute.cpp").read_bytes()),
            }
        )
    pairs = [_pair_decision(out / left.task_id, out / right.task_id) for left, right in combinations(TASKS, 2)]
    failed_pairs = [pair for pair in pairs if not pair["pass"]]
    if failed_pairs:
        first = failed_pairs[0]
        failed_dimensions = [name for name, record in first["dimensions"].items() if not record["distinct"]]
        _fail("duplicate_family", f"{first['left']}:{first['right']}:{','.join(failed_dimensions)}")
    controls = _materialize_controls(out)
    inventory_record = json.loads((out / ".state/source-inventory.json").read_text())
    current_inventory = _freeze_inventory(out)
    if current_inventory["inventory_hash"] != inventory_record["inventory_hash"]:
        snapshots = out / ".state/source-inventory-snapshots"
        old_name = str(inventory_record["inventory_hash"]).removeprefix("sha256:") + ".json"
        _write_json(snapshots / old_name, inventory_record)
        _write_json(out / ".state/source-inventory.json", current_inventory)
        inventory_record = current_inventory
    lineage_count, lineage_maxima, _ = _screen_external(
        out,
        list(inventory_record["records"]),
        threshold=0.72,
        failure_code="semantic_lineage_overlap",
    )
    if not HOLDOUT_ROOT.is_dir():
        _fail("benchmark_content_unavailable", str(HOLDOUT_ROOT))
    holdouts = {
        path.name: path
        for path in HOLDOUT_ROOT.iterdir()
        if path.is_dir() and path.name in OFFICIAL_HOLDOUTS
    }
    if set(holdouts) != OFFICIAL_HOLDOUTS:
        _fail("benchmark_content_unavailable", ",".join(sorted(OFFICIAL_HOLDOUTS - set(holdouts))))
    holdout_records = [
        _snapshot_record(
            tree="official_holdout",
            inventory_key=task_id,
            task_id=task_id,
            path=path,
        )
        for task_id, path in sorted(holdouts.items())
    ]
    holdout_count, holdout_maxima, _ = _screen_external(
        out,
        holdout_records,
        threshold=0.64,
        failure_code="benchmark_content_overlap",
    )
    final_inventory = _freeze_inventory(out)
    if final_inventory["inventory_hash"] != inventory_record["inventory_hash"]:
        _fail(
            "external_inventory_changed_during_screen",
            f"start={inventory_record['inventory_hash']} end={final_inventory['inventory_hash']}",
        )
    state = out / ".state"
    screen = {
        "schema_version": 1,
        "normalizer": NORMALIZER,
        "root_count": 40,
        "pair_count": len(pairs),
        "expected_pair_count": 780,
        "dimensions": list(HARD_RULE_DIMENSIONS),
        "pairs": pairs,
        "control_bundle_hash": _control_bundle_hash(state / "adversarial-clone-controls"),
        "controls": controls,
        "status": "pass",
    }
    _write_json(state / "family-screen.json", screen)
    _write_json(state / "prompt-boundary.json", {"schema_version": 1, "status": "pass", "records": prompt_records})
    _write_json(
        state / "lineage-screen.json",
        {
            "schema_version": 3,
            "status": "pass",
            "normalizer": NORMALIZER,
            "source_inventory_record_hash": _sha256(
                (state / "source-inventory.json").read_bytes()
            ),
            "source_inventory_hash": inventory_record["inventory_hash"],
            "semantic_snapshot_hash": inventory_record["semantic_snapshot_hash"],
            "semantic_snapshot_record_count": inventory_record[
                "semantic_snapshot_record_count"
            ],
            "inventory_counts": inventory_record["counts"],
            "screen_start_inventory_hash": inventory_record["inventory_hash"],
            "screen_end_inventory_hash": final_inventory["inventory_hash"],
            "comparison_count": lineage_count,
            "nearest": lineage_maxima,
        },
    )
    _write_json(
        state / "benchmark-screen.json",
        {"schema_version": 1, "status": "pass", "holdout_count": 26, "comparison_count": holdout_count, "nearest": holdout_maxima},
    )
    return {
        "root_count": 40,
        "pair_count": 780,
        "control_count": 4,
        "prompt_count": 40,
        "existing_comparisons": lineage_count,
        "holdout_comparisons": holdout_count,
        "status": "pass",
    }


DOCKER_SCRIPT = r'''
set -eu
current_task=preflight
current_mode=none
trap 'status=$?; if [ "$status" -ne 0 ]; then echo "FAILED|${current_task}|${current_mode}|${status}" >&2; for log in /tmp/configure.log /tmp/build.log /tmp/reference-tests.log /tmp/negative-build.log /tmp/negative-tests.log; do if [ -f "$log" ]; then echo "LOG|$log" >&2; tail -80 "$log" >&2; fi; done; fi' EXIT
cd /tasks
mount_hash=$(find . -type f ! -path './.state/*' -print0 | sort -z | while IFS= read -r -d '' file; do sha256sum "$file" | sed 's#  \./#  #'; done | sha256sum | awk '{print $1}')
echo "MOUNT_HASH|${mount_hash}"
control_mount_hash=$(cd .state/adversarial-clone-controls && find . -type f ! -name manifest.json -print0 | sort -z | while IFS= read -r -d '' file; do sha256sum "$file" | sed 's#  \./#  #'; done | sha256sum | awk '{print $1}')
echo "CONTROL_MOUNT_HASH|${control_mount_hash}"
run_one() {
  source_root="$1"
  task_id="$2"
  mode="$3"
  current_task="$task_id"
  current_mode="$mode"
  work="/tmp/rational-complex-${task_id}-${mode}"
  rm -rf "$work"
  cp -a "$source_root" "$work"
  cp "$work/.meta/example.h" "$work/${task_id}.h"
  cp "$work/.meta/example.cpp" "$work/${task_id}.cpp"
  sanitize=OFF
  if [ "$mode" = sanitizer ]; then sanitize=ON; fi
  cmake -S "$work" -B "$work/build" -G "Unix Makefiles" -DSANITIZE="$sanitize" >/tmp/configure.log 2>&1
  cmake --build "$work/build" -j2 >/tmp/build.log 2>&1
  discovered=$(ctest --test-dir "$work/build" -N | sed -n 's/.*Total Tests: *//p')
  [ "$discovered" = 2 ]
  ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir "$work/build" --output-on-failure >/tmp/reference-tests.log 2>&1
  cp "$work/.meta/negative_false_substitute.cpp" "$work/${task_id}.cpp"
  cmake --build "$work/build" -j2 >/tmp/negative-build.log 2>&1
  if ASAN_OPTIONS=detect_leaks=0:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir "$work/build" --output-on-failure >/tmp/negative-tests.log 2>&1; then
    echo "negative fixture unexpectedly passed for ${task_id} ${mode}" >&2
    exit 31
  fi
  negative_discovered=$(ctest --test-dir "$work/build" -N | sed -n 's/.*Total Tests: *//p')
  [ "$negative_discovered" = 2 ]
  echo "RECORD|${task_id}|${mode}|${discovered}|${negative_discovered}|rejected"
}
for root in /tasks/*; do
  [ -d "$root" ] || continue
  task_id=$(basename "$root")
  run_one "$root" "$task_id" normal
  run_one "$root" "$task_id" sanitizer
done
for root in /tasks/.state/adversarial-clone-controls/*; do
  [ -d "$root" ] || continue
  [ -f "$root/.meta/config.json" ] || continue
  task_id=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["files"]["solution"][0][:-2])' "$root/.meta/config.json")
  run_one "$root" "$task_id" normal
  run_one "$root" "$task_id" sanitizer
done
'''


def _bind_control_evidence(
    state: Path,
    records: Sequence[dict[str, object]],
    mounted_control_bundle_hash: str,
) -> tuple[str, str, str]:
    controls_root = state / "adversarial-clone-controls"
    current_bundle_hash = _control_bundle_hash(controls_root)
    manifest_path = controls_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest.get("control_bundle_hash") != current_bundle_hash
        or mounted_control_bundle_hash != current_bundle_hash
    ):
        _fail("adversarial_control_stale", current_bundle_hash)
    for control in manifest["controls"]:
        root = controls_root / str(control["name"])
        if control.get("tree_hash") != _tree_hash(root, include_state=True):
            _fail("adversarial_control_stale", str(control["name"]))
        modes = {
            str(record["mode"])
            for record in records
            if record["task_id"] == control["task_id"]
        }
        if modes != {"normal", "sanitizer"}:
            _fail("adversarial_control_stale", f"{control['name']}:records")
        control["coherent_build"] = "pass_normal_and_fresh_sanitizer"
        control["docker_modes"] = sorted(modes)
    _write_json(manifest_path, manifest)
    screen_path = state / "family-screen.json"
    screen = json.loads(screen_path.read_text())
    screen["control_bundle_hash"] = current_bundle_hash
    screen["controls"] = manifest["controls"]
    screen["control_status"] = "pass_normal_and_fresh_sanitizer"
    _write_json(screen_path, screen)
    return (
        current_bundle_hash,
        _sha256(manifest_path.read_bytes()),
        _sha256(screen_path.read_bytes()),
    )


def docker_sanity(out: Path) -> dict[str, object]:
    out = _safe_output(out)
    core_result = verify_core(out)
    command = [
        "docker", "run", "--rm", "--network", "none",
        "-v", f"{out.resolve()}:/tasks:ro", SANITY_IMAGE,
        "bash", "-lc", DOCKER_SCRIPT,
    ]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if completed.returncode != 0:
        _fail("docker_sanity_failed", (completed.stderr + completed.stdout)[-20000:])
    mount_lines = [line for line in completed.stdout.splitlines() if line.startswith("MOUNT_HASH|")]
    if len(mount_lines) != 1:
        _fail("grader_mount_hash_mismatch", "missing mounted hash")
    mounted = "sha256:" + mount_lines[0].split("|", 1)[1]
    portable = _portable_tree_hash(out)
    if mounted != portable:
        _fail("grader_mount_hash_mismatch", f"owner={portable} mounted={mounted}")
    control_mount_lines = [
        line
        for line in completed.stdout.splitlines()
        if line.startswith("CONTROL_MOUNT_HASH|")
    ]
    if len(control_mount_lines) != 1:
        _fail("grader_mount_hash_mismatch", "missing mounted control hash")
    mounted_control_bundle_hash = "sha256:" + control_mount_lines[0].split("|", 1)[1]
    records: list[dict[str, object]] = []
    for line in completed.stdout.splitlines():
        if not line.startswith("RECORD|"):
            continue
        _, task_id, mode, discovered, negative_discovered, outcome = line.split("|")
        records.append(
            {
                "task_id": task_id,
                "mode": mode,
                "discovered_tests": int(discovered),
                "negative_discovered_tests": int(negative_discovered),
                "negative_outcome": outcome,
            }
        )
    expected_ids = {case.task_id for case in TASKS} | {case.task_id for _, case in _control_cases()}
    if len(records) != 88 or {record["task_id"] for record in records} != expected_ids:
        _fail("sanitizer_test_count_mismatch", f"records={len(records)} ids={len({r['task_id'] for r in records})}")
    for task_id in expected_ids:
        task_records = [record for record in records if record["task_id"] == task_id]
        if {record["mode"] for record in task_records} != {"normal", "sanitizer"}:
            _fail("sanitizer_test_count_mismatch", task_id)
        if any(record["discovered_tests"] != 2 or record["negative_discovered_tests"] != 2 for record in task_records):
            _fail("sanitizer_test_count_mismatch", task_id)
    inspect = subprocess.run(
        ["docker", "image", "inspect", SANITY_IMAGE, "--format", "{{.Id}}"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    compiler = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", SANITY_IMAGE, "bash", "-lc", "command -v c++; c++ --version | head -1; sha256sum $(command -v c++) | awk '{print $1}'"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    cmake = subprocess.run(
        ["docker", "run", "--rm", "--network", "none", SANITY_IMAGE, "cmake", "--version"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if inspect.returncode or compiler.returncode or cmake.returncode:
        _fail("docker_sanity_failed", "environment identity")
    compiler_lines = compiler.stdout.splitlines()
    state = out / ".state"
    control_bundle_hash, control_manifest_hash, family_screen_hash = _bind_control_evidence(
        state, records, mounted_control_bundle_hash
    )
    receipt = {
        "schema_version": 1,
        "family_id": FAMILY_ID,
        "status": "pass",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "network_policy": "none",
        "image": SANITY_IMAGE,
        "image_id": inspect.stdout.strip(),
        "compiler_path": compiler_lines[0] if compiler_lines else "unknown",
        "compiler_version": compiler_lines[1] if len(compiler_lines) > 1 else "unknown",
        "compiler_sha256": "sha256:" + compiler_lines[2] if len(compiler_lines) > 2 else "unknown",
        "cmake_version": cmake.stdout.splitlines()[0] if cmake.stdout else "unknown",
        "owner_hash": _sha256(Path(OWNER).read_bytes()),
        "case_owner_hash": _sha256(Path(CASE_OWNER).read_bytes()),
        "family_tree_hash": _tree_hash(out),
        "portable_tree_hash": portable,
        "mounted_tree_hash": mounted,
        "control_bundle_hash": control_bundle_hash,
        "mounted_control_bundle_hash": mounted_control_bundle_hash,
        "control_manifest_hash": control_manifest_hash,
        "family_screen_hash": family_screen_hash,
        "normal_records": 44,
        "sanitizer_records": 44,
        "negative_records": 88,
        "records": records,
        "commands": [command],
        "creator_core": core_result,
    }
    _write_json(state / "docker-sanity-receipt.json", receipt)
    for case in TASKS:
        root = out / case.task_id
        task_records = [record for record in records if record["task_id"] == case.task_id]
        _write_json(
            state / "receipts" / f"{case.task_id}.json",
            {
                "schema_version": 1,
                "task_id": case.task_id,
                "status": "local_family_verified_pending_fresh_audit",
                "tree_hash": _tree_hash(root),
                "prompt_hash": next(record["prompt_hash"] for record in json.loads((state / "prompt-boundary.json").read_text())["records"] if record["task_id"] == case.task_id),
                "reference_hash": _sha256((root / ".meta/example.cpp").read_bytes()),
                "test_hashes": [_sha256((root / "task_visible_test.cpp").read_bytes()), _sha256((root / ".meta/task_hidden_test.cpp").read_bytes())],
                "negative_hash": _sha256((root / ".meta/negative_false_substitute.cpp").read_bytes()),
                "owner_hash": receipt["owner_hash"],
                "case_owner_hash": receipt["case_owner_hash"],
                "image_id": receipt["image_id"],
                "network_policy": "none",
                "records": task_records,
                "prompt_boundary": "pass",
                "family_screen": "pass",
                "benchmark_screen": "pass",
                "dataset_handoff": "not_requested",
            },
        )
    return {"root_count": 40, "control_count": 4, "records": 88, "status": "pass"}


HOST_SANITIZER_ENV = {
    "ASAN_OPTIONS": "detect_leaks=0:halt_on_error=1",
    "UBSAN_OPTIONS": "halt_on_error=1",
}


def _ctest_discovery_count(output: str) -> int:
    match = re.search(r"Total Tests:\s*(\d+)", output)
    return int(match.group(1)) if match else 0


def _validate_host_records(
    records: Sequence[dict[str, object]], expected_ids: set[str]
) -> None:
    if len(records) != 2 * len(expected_ids) or {
        str(record["task_id"]) for record in records
    } != expected_ids:
        _fail(
            "sanitizer_test_count_mismatch",
            f"records={len(records)} ids={len({str(r['task_id']) for r in records})}",
        )
    for task_id in sorted(expected_ids):
        task_records = [record for record in records if record["task_id"] == task_id]
        if {str(record["mode"]) for record in task_records} != {"normal", "sanitizer"}:
            _fail("sanitizer_test_count_mismatch", task_id)
        for record in task_records:
            label = f"{task_id}:{record['mode']}"
            if record["discovered_tests"] == 0 or record["negative_discovered_tests"] == 0:
                _fail("zero_tests", label)
            if record["discovered_tests"] != 2 or record["negative_discovered_tests"] != 2:
                _fail("sanitizer_test_count_mismatch", label)
            if record["negative_outcome"] != "rejected":
                _fail("negative_fixture_not_rejected", label)


def _host_run(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
    )


def verify_host(out: Path) -> dict[str, object]:
    """Run the owner oracle on the host toolchain for every root and control.

    For each root this configures a clean normal C++17 build and a separate
    fresh ASan/UBSan build with the host ``Unix Makefiles`` generator, requires
    a positive equal discovery count, runs the reference against all visible
    and hidden tests, then rebuilds with the negative false substitute and
    requires an executed test rejection in both modes.
    """
    out = _safe_output(out)
    core_result = verify_core(out)
    cmake = shutil.which("cmake")
    compiler = shutil.which("c++")
    ctest = shutil.which("ctest")
    if not cmake or not compiler or not ctest:
        _fail("verification_not_completed", "host cmake, ctest, and c++ required")
    roots = [(out / case.task_id, case.task_id) for case in TASKS]
    controls_root = out / ".state" / "adversarial-clone-controls"
    roots.extend(
        (controls_root / name, case.task_id) for name, case in _control_cases()
    )
    expected_ids = {task_id for _, task_id in roots}
    test_env = dict(os.environ, **HOST_SANITIZER_ENV)
    records: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="rational-complex-host-") as temp:
        for source_root, task_id in roots:
            for mode in ("normal", "sanitizer"):
                failure_code = (
                    "reference_tests_failed"
                    if mode == "normal"
                    else "reference_sanitizer_failed"
                )
                work = Path(temp) / f"{task_id}-{mode}"
                shutil.copytree(source_root, work)
                # copyfile (not copy2): the destination mtime must be newer
                # than any prior build object so make always recompiles the
                # replacement source instead of reusing a stale reference
                # object, which would fake a negative-fixture pass.
                shutil.copyfile(work / ".meta/example.h", work / f"{task_id}.h")
                shutil.copyfile(work / ".meta/example.cpp", work / f"{task_id}.cpp")
                build = work / "build"
                sanitize = "ON" if mode == "sanitizer" else "OFF"
                for command in (
                    [cmake, "-S", str(work), "-B", str(build), "-G", "Unix Makefiles", f"-DSANITIZE={sanitize}"],
                    [cmake, "--build", str(build), "-j2"],
                ):
                    completed = _host_run(command)
                    if completed.returncode != 0:
                        _fail(
                            failure_code,
                            f"{task_id}:{mode}:configure/build:{completed.stderr[-2000:]}",
                        )
                discovery = _host_run([ctest, "--test-dir", str(build), "-N"])
                discovered = _ctest_discovery_count(discovery.stdout)
                run = _host_run(
                    [ctest, "--test-dir", str(build), "--output-on-failure"],
                    env=test_env,
                )
                if run.returncode != 0:
                    _fail(
                        failure_code,
                        f"{task_id}:{mode}:tests:{run.stdout[-2000:]}",
                    )
                shutil.copyfile(
                    work / ".meta/negative_false_substitute.cpp",
                    work / f"{task_id}.cpp",
                )
                rebuild = _host_run([cmake, "--build", str(build), "-j2"])
                if rebuild.returncode != 0:
                    _fail(
                        failure_code,
                        f"{task_id}:{mode}:negative-build:{rebuild.stderr[-2000:]}",
                    )
                negative = _host_run(
                    [ctest, "--test-dir", str(build), "--output-on-failure"],
                    env=test_env,
                )
                negative_discovery = _host_run([ctest, "--test-dir", str(build), "-N"])
                records.append(
                    {
                        "task_id": task_id,
                        "mode": mode,
                        "discovered_tests": discovered,
                        "negative_discovered_tests": _ctest_discovery_count(
                            negative_discovery.stdout
                        ),
                        "negative_outcome": (
                            "rejected" if negative.returncode != 0 else "passed"
                        ),
                    }
                )
    _validate_host_records(records, expected_ids)
    compiler_version = _host_run([compiler, "--version"]).stdout.splitlines()
    compiler_hash = _sha256(Path(compiler).read_bytes()) if Path(compiler).is_file() else "unknown"
    cmake_version = _host_run([cmake, "--version"]).stdout.splitlines()
    receipt = {
        "schema_version": 1,
        "family_id": FAMILY_ID,
        "status": "pass",
        "evidence_class": "host_verify",
        "locked_oracle": False,
        "network_policy": "host_local_no_network_required",
        "compiler_path": compiler,
        "compiler_version": compiler_version[0] if compiler_version else "unknown",
        "compiler_sha256": compiler_hash,
        "cmake_version": cmake_version[0] if cmake_version else "unknown",
        "owner_hash": _sha256(Path(OWNER).read_bytes()),
        "case_owner_hash": _sha256(Path(CASE_OWNER).read_bytes()),
        "family_tree_hash": _tree_hash(out),
        "normal_records": len(expected_ids),
        "sanitizer_records": len(expected_ids),
        "negative_records": 2 * len(expected_ids),
        "records": records,
        "commands": [
            "cmake -S <work> -B <work>/build -G 'Unix Makefiles' -DSANITIZE=<OFF|ON>",
            "cmake --build <work>/build -j2",
            "ctest --test-dir <work>/build -N",
            "ctest --test-dir <work>/build --output-on-failure",
        ],
        "creator_core": core_result,
    }
    _write_json(out / ".state" / "host-verify-receipt.json", receipt)
    return {
        "root_count": 40,
        "control_count": 4,
        "records": len(records),
        "status": "pass",
    }


def _validate_inventory_screen_binding(
    out: Path,
) -> tuple[Path, dict[str, object], str]:
    inventory_path = out / ".state/source-inventory.json"
    bound_inventory = json.loads(inventory_path.read_text())
    lineage_path = out / ".state/lineage-screen.json"
    lineage_screen = json.loads(lineage_path.read_text())
    inventory_record_hash = _sha256(inventory_path.read_bytes())
    snapshot_records = list(bound_inventory.get("records", []))
    for record in snapshot_records:
        if not isinstance(record, dict):
            _fail("external_inventory_snapshot_invalid", str(lineage_path))
        _validate_snapshot_record(record)
    if (
        bound_inventory.get("schema_version") != 2
        or bound_inventory.get("semantic_snapshot_record_count")
        != len(snapshot_records)
        or lineage_screen.get("schema_version") != 3
        or lineage_screen.get("source_inventory_record_hash") != inventory_record_hash
        or lineage_screen.get("source_inventory_hash") != bound_inventory["inventory_hash"]
        or lineage_screen.get("semantic_snapshot_hash")
        != bound_inventory["semantic_snapshot_hash"]
        or lineage_screen.get("semantic_snapshot_record_count")
        != bound_inventory["semantic_snapshot_record_count"]
        or bound_inventory.get("semantic_snapshot_hash")
        != _semantic_snapshot_hash(snapshot_records)
        or lineage_screen.get("inventory_counts") != bound_inventory["counts"]
        or lineage_screen.get("screen_start_inventory_hash")
        != bound_inventory["inventory_hash"]
        or lineage_screen.get("screen_end_inventory_hash")
        != bound_inventory["inventory_hash"]
    ):
        _fail("external_inventory_screen_binding_mismatch", str(lineage_path))
    return inventory_path, bound_inventory, inventory_record_hash


def creator_preflight(out: Path) -> dict[str, object]:
    out = _safe_output(out)
    core = verify_core(out)
    receipt_path = out / ".state/docker-sanity-receipt.json"
    if not receipt_path.is_file():
        _fail("docker_sanity_not_completed", str(receipt_path))
    receipt = json.loads(receipt_path.read_text())
    if (
        receipt.get("status") != "pass"
        or receipt.get("family_tree_hash") != _tree_hash(out)
        or receipt.get("owner_hash") != _sha256(Path(OWNER).read_bytes())
        or receipt.get("case_owner_hash") != _sha256(Path(CASE_OWNER).read_bytes())
    ):
        _fail("docker_sanity_not_completed", "stale receipt")
    state = out / ".state"
    control_bundle_hash, control_manifest_hash, family_screen_hash = _bind_control_evidence(
        state,
        receipt["records"],
        str(receipt["mounted_control_bundle_hash"]),
    )
    if (
        receipt.get("control_bundle_hash") != control_bundle_hash
        or receipt.get("control_manifest_hash") != control_manifest_hash
        or receipt.get("family_screen_hash") != family_screen_hash
    ):
        _fail("docker_sanity_not_completed", "stale control evidence")
    inventory_path, bound_inventory, inventory_record_hash = (
        _validate_inventory_screen_binding(out)
    )
    lineage_path = out / ".state/lineage-screen.json"
    current_inventory = _freeze_inventory(out)
    if current_inventory["inventory_hash"] != bound_inventory["inventory_hash"]:
        _fail(
            "external_inventory_changed_before_subject",
            f"bound={bound_inventory['inventory_hash']} current={current_inventory['inventory_hash']}",
        )
    subject = {
        "family_id": FAMILY_ID,
        "tree_hash": _tree_hash(out),
        "owner_hash": _sha256(Path(OWNER).read_bytes()),
        "case_owner_hash": _sha256(Path(CASE_OWNER).read_bytes()),
        "curriculum_hash": _sha256(CURRICULUM.read_bytes()),
        "spec_hash": _sha256(FAMILY_SPEC.read_bytes()),
        "focused_test_hash": _sha256(Path(FOCUSED_TEST).read_bytes()),
        "source_inventory_hash": inventory_record_hash,
        "selected_manifest_hash": _sha256((out / ".state/selected-manifest.json").read_bytes()),
        "family_screen_hash": _sha256((out / ".state/family-screen.json").read_bytes()),
        "control_bundle_hash": control_bundle_hash,
        "control_manifest_hash": control_manifest_hash,
        "benchmark_screen_hash": _sha256((out / ".state/benchmark-screen.json").read_bytes()),
        "lineage_screen_hash": _sha256(lineage_path.read_bytes()),
        "docker_receipt_hash": _sha256(receipt_path.read_bytes()),
        "root_count": 40,
    }
    subject_hash = _sha256(json.dumps(subject, sort_keys=True, separators=(",", ":")).encode())
    audit_subject = {"schema_version": 1, "audit_subject_hash": subject_hash, "subject": subject}
    _write_json(out / ".state/audit-subject.json", audit_subject)
    cycles = out / ".state/cycles"
    existing = sorted(cycles.glob("cycle-*.json")) if cycles.is_dir() else []
    cycle_number = len(existing) + 1
    cycle = {
        "schema_version": 1,
        "cycle": cycle_number,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "state": "creator_preflight" if cycle_number == 1 else "remediation_preflight",
        "family_id": FAMILY_ID,
        "audit_subject_hash": subject_hash,
        "subject": subject,
        "retained_ids": [case.task_id for case in TASKS],
        "rejected_proposals": [
            "control-domain-identifier-renamed",
            "control-constants-policy-only",
            "control-opposite-end-selection",
            "control-representation-changed-weighted-selection",
            "rational-weighted-median",
        ],
        "replaced_ids": (
            [
                {
                    "rejected_id": "rational-weighted-median",
                    "replacement_id": "rational-amortization-schedule",
                    "finding_id": "RC-AUD-008",
                }
            ]
            if cycle_number > 1
            else []
        ),
        "blocked_ids": [],
        "invalidated_evidence": [] if cycle_number == 1 else ["all prior receipts and audit conclusions bind an earlier subject"],
        "creator_preflight": core,
        "terminal_status": "pending_independent_audit",
    }
    _write_json(cycles / f"cycle-{cycle_number:02d}.json", cycle)
    return {"audit_subject_hash": subject_hash, "cycle": cycle_number, "root_count": 40, "status": "pending_independent_audit"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--creator-preflight", action="store_true")
    args = parser.parse_args(argv)
    results: dict[str, object] = {}
    if args.force:
        results["materialize"] = materialize(args.out, force=True)
    elif not args.out.exists():
        results["materialize"] = materialize(args.out, force=False)
    if args.verify_core:
        results["verify_core"] = verify_core(args.out)
    if args.verify_host:
        results["verify_host"] = verify_host(args.out)
    if args.docker_sanity:
        results["docker_sanity"] = docker_sanity(args.out)
    if args.creator_preflight:
        results["creator_preflight"] = creator_preflight(args.out)
    if not results:
        results["materialize"] = materialize(args.out, force=False)
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
