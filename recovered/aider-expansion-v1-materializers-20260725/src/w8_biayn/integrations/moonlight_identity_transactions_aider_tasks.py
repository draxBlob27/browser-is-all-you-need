"""Create and verify the 60-root identity/collision/reset/transactions family."""
from __future__ import annotations

import argparse
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
from typing import Iterable, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_sft import build_assistant_response, load_example_files_from_config
from w8_biayn.integrations.moonlight_identity_transactions_cases import CASES as IDENTITY_CASES
from w8_biayn.integrations.moonlight_identity_transactions_contracts import OPERATION_CONTRACT_REQUIRED_FRAGMENTS, OPERATION_CONTRACTS
from w8_biayn.integrations.moonlight_identity_transactions_collision_cases import CASES as COLLISION_CASES
from w8_biayn.integrations.moonlight_identity_transactions_hard_rule import family_screen, file_hash, semantic_text, sha256_bytes, shingles, tree_hash
from w8_biayn.integrations.moonlight_identity_transactions_reset_cases import CASES as RESET_CASES
from w8_biayn.integrations.moonlight_identity_transactions_transaction_cases import CASES as TRANSACTION_CASES

CASES = IDENTITY_CASES + COLLISION_CASES + RESET_CASES + TRANSACTION_CASES
DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/identity-collision-reset-transactions")
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
CURRICULUM = Path("docs/aider-synthetic/aider-synthetic-state-concurrency/GLM47_FLASH_AIDER_POLYGLOT_CPP_IDENTITY_COLLISION_RESET_TRANSACTIONS_CURRICULUM.md")
FAMILY_SPEC = Path("docs/aider-tasks-spec/aider-state-concurrency/identity-collision-reset-transactions.md")
GENERATOR = Path("src/w8_biayn/integrations/moonlight_identity_transactions_aider_tasks.py")
CASE_PATHS = tuple(Path(f"src/w8_biayn/integrations/moonlight_identity_transactions_{suffix}.py") for suffix in ("cases", "collision_cases", "reset_cases", "transaction_cases"))
HARD_RULE = Path("src/w8_biayn/integrations/moonlight_identity_transactions_hard_rule.py")
CONTRACTS = Path("src/w8_biayn/integrations/moonlight_identity_transactions_contracts.py")
FOCUSED_TEST = Path("tests/test_moonlight_identity_transactions_aider_tasks.py")
FAMILY_ID = "aider-expansion-v1-identity-collision-reset-transactions-v1"
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
OFFICIAL_HOLDOUTS = frozenset({"all-your-base","allergies","bank-account","binary-search-tree","circular-buffer","clock","complex-numbers","crypto-square","diamond","dnd-character","gigasecond","grade-school","kindergarten-garden","knapsack","linked-list","meetup","parallel-letter-frequency","perfect-numbers","phone-number","queen-attack","robot-name","space-age","spiral-matrix","sublist","yacht","zebra-puzzle"})
CONTROL_NAMES = ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection")

COMMON_INCLUDES = """#include <algorithm>
#include <array>
#include <cctype>
#include <climits>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <deque>
#include <functional>
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
CMAKE = """cmake_minimum_required(VERSION 3.16)
project(identity_transaction_task LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE \"${CMAKE_CURRENT_SOURCE_DIR}/@TASK_ID@.cpp\" CACHE FILEPATH \"Implementation\")
enable_testing()
add_executable(task_visible \"${TASK_SOURCE}\" task_visible_test.cpp)
add_executable(task_hidden \"${TASK_SOURCE}\" .meta/task_hidden_test.cpp)
foreach(name visible hidden)
  target_include_directories(task_${name} PRIVATE \"${CMAKE_CURRENT_SOURCE_DIR}\")
  if(CMAKE_CXX_COMPILER_ID MATCHES \"GNU|Clang\")
    target_compile_options(task_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  add_test(NAME ${name} COMMAND task_${name})
endforeach()
"""


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _validate_operation_contract_source(contracts: dict[str, str]) -> None:
    for task_id, fragments in OPERATION_CONTRACT_REQUIRED_FRAGMENTS.items():
        contract = contracts.get(task_id, "")
        missing = [fragment for fragment in fragments if fragment not in contract]
        if missing:
            _fail("operation_contract_semantics_missing", f"{task_id}: {missing!r}")


def _inventory(root: Path) -> list[dict[str, str]]:
    records = []
    if root.is_dir():
        for config in sorted(root.rglob(".meta/config.json")):
            if ".state" in config.parts:
                continue
            task_root = config.parent.parent
            records.append({"task_id": task_root.name, "relative_root": task_root.relative_to(root).as_posix(), "tree_hash": tree_hash(task_root), "config_hash": file_hash(config)})
    return records


def _inventory_hash(records: Iterable[dict[str, str]]) -> str:
    return sha256_bytes(json.dumps(list(records), sort_keys=True).encode())


def _validate_output(out: Path) -> None:
    resolved, expansion = out.resolve(), EXPANSION_ROOT.resolve()
    if resolved == expansion or expansion not in resolved.parents:
        _fail("unsafe_path", f"output must be a family below {EXPANSION_ROOT}: {out}")
    for forbidden in (LEGACY_ROOT.resolve(), REVERIFY_ROOT.resolve()):
        if resolved == forbidden or forbidden in resolved.parents:
            _fail("unsafe_path", f"existing tree is read-only: {out}")
    cursor = out
    while cursor != EXPANSION_ROOT.parent and cursor != cursor.parent:
        if cursor.is_symlink():
            _fail("unsafe_path", f"symlink component: {cursor}")
        cursor = cursor.parent


def _existing_ids(out: Path) -> dict[str, str]:
    found = {}
    for root in (LEGACY_ROOT, REVERIFY_ROOT, EXPANSION_ROOT):
        for record in _inventory(root):
            path = root / record["relative_root"]
            if out == path or out in path.parents:
                continue
            found.setdefault(record["task_id"], str(path))
    return found


def _header(case: object) -> str:
    guard = re.sub(r"[^A-Z0-9]", "_", case.task_id.upper()) + "_H"
    return f"#ifndef {guard}\n#define {guard}\n{COMMON_INCLUDES}\nnamespace curriculum {{\n{case.api}\n}}\n#endif\n"


def _source(case: object, definition: str) -> str:
    return f'#include "{case.task_id}.h"\nnamespace curriculum {{\n{definition}\n}}\n'


def _test(case: object, body: str) -> str:
    return f'#include "{case.task_id}.h"\n#include <stdexcept>\nusing namespace curriculum;\nstatic void check(bool value){{if(!value)throw std::runtime_error("check");}}\nint main(){{{body}return 0;}}\n'


def _instructions(case: object) -> str:
    clauses = _contract_clauses(case)
    clause_lines = "\n".join(f"- **{row['requirement_id']}**: {row['clause']}" for row in clauses)
    return f"""# {case.title}

Implement the public C++17 API below as complete replacements of
`{case.task_id}.h` and `{case.task_id}.cpp`.

```cpp
namespace curriculum {{
{case.api}
}}
```

## Normative contract

{clause_lines}

The public API, nested types, private state shape, constructor defaults, and
method return types shown above are normative. `std::nullopt`, `false`, and any
non-success integer demonstrated below are failure results. Every failure is
atomic: it leaves all observable state, counters, ordering, and allocation
history unchanged.

The following public example is normative. Each `check(expression)` requires
`expression` to evaluate true; it defines successful return values, ordering,
ties, state transitions, and observable queries without exposing private tests.

```cpp
{case.visible}
```

Do not replace the mechanism with {case.negative_reason}. Implement the owned
state and transition logic directly. Standard containers are allowed only as
incidental storage or output when they do not perform the advertised mechanism.
"""


def _contract_clauses(case: object) -> list[dict[str, object]]:
    assertion_ids = _assertion_ids(case)
    visible = assertion_ids["visible"]
    hidden = assertion_ids["hidden"]
    negative = assertion_ids["negative"]
    return [
        {"requirement_id": "R0-operation-contract", "clause": OPERATION_CONTRACTS[case.task_id], "assertion_ids": visible+hidden},
        {"requirement_id": "R1-api-and-initial-state", "clause": "Use exactly the declared API and its shown initial member state; do not add observable operations.", "assertion_ids": visible+hidden},
        {"requirement_id": "R2-owned-mechanism", "clause": f"Implement {case.mechanism}; this is the owned state transition, not merely an output convention.", "assertion_ids": visible+hidden+negative},
        {"requirement_id": "R3-task-boundary", "clause": case.boundary.capitalize() + ".", "assertion_ids": visible+hidden},
        {"requirement_id": "R4-public-example", "clause": "The normative public example below fixes successful results, ordering, ties, and query conventions.", "assertion_ids": visible},
        {"requirement_id": "R5-invalid-and-atomic-failure", "clause": "Invalid, duplicate, absent, empty, out-of-range, exhausted, stale, or otherwise rejected operations return their declared failure value and leave every observable value unchanged.", "assertion_ids": hidden},
        {"requirement_id": "R6-plausible-wrong-rejection", "clause": f"The implementation must not behave as though {case.negative_reason}.", "assertion_ids": negative},
    ]


def _assertion_ids(case: object) -> dict[str, list[str]]:
    return {
        "visible": [f"V{index:02d}" for index in range(1, case.visible.count("check(")+1)],
        "hidden": [f"H{index:02d}" for index in range(1, case.hidden.count("check(")+1)],
        "negative": ["N01"],
    }


def _requirements(case: object) -> dict[str, object]:
    visible = _test(case, case.visible)
    hidden = _test(case, case.hidden)
    artifacts = {
        "visible": {"path": "task_visible_test.cpp", "sha256": sha256_bytes(visible.encode())},
        "hidden": {"path": ".meta/task_hidden_test.cpp", "sha256": sha256_bytes(hidden.encode())},
        "negative": {"path": ".meta/negative_false_substitute.cpp", "sha256": sha256_bytes(_source(case, case.definition.replace(case.negative_old, case.negative_new)).encode())},
    }
    assertion_catalog = []
    for role, ids in _assertion_ids(case).items():
        for ordinal, assertion_id in enumerate(ids, 1):
            assertion_catalog.append({"assertion_id":assertion_id,"role":role,"ordinal":ordinal,"artifact":artifacts[role]["path"],"artifact_sha256":artifacts[role]["sha256"],"expected":"check expression evaluates true" if role!="negative" else "compiled substitute is rejected by at least one designated test"})
    return {
        "schema_version": "aider-public-requirement-trace-v1",
        "task_id": case.task_id,
        "public_contract": ".docs/instructions.md",
        "requirements": _contract_clauses(case),
        "assertion_artifacts": artifacts,
        "assertion_catalog": assertion_catalog,
    }


def _provenance(case: object) -> dict[str, object]:
    return {"schema_version":"aider-local-provenance-v1","family_id":FAMILY_ID,"task_id":case.task_id,"lineage":{"relation":"new-root","parent":None},"source_document":CURRICULUM.as_posix(),"family_specification":FAMILY_SPEC.as_posix(),"authoring_origin":"clean-room repository-authored","license":"repository-local research artifact","status_boundary":"local candidate; not dataset admission","semantic_profile":{"public_api":case.api,"owned_state_algorithm":case.mechanism,"mutation_selection_rules":case.boundary,"invalid_boundary_behavior":"invalid duplicate absent empty boundary overflow atomic failure "+case.boundary,"reference_control_flow":case.mechanism+" "+case.definition,"deterministic_oracle":case.visible+" "+case.hidden,"topic_negative_fixture":case.negative_reason}}


def _materialize(case: object, root: Path) -> None:
    header = _header(case)
    negative = case.definition.replace(case.negative_old, case.negative_new)
    if negative == case.definition:
        _fail("negative_fixture_invalid", f"replacement marker absent: {case.task_id}")
    files = {
        ".docs/introduction.md": f"# {case.title}\n\nA clean-room C++17 `{case.group}` state-mechanism task.\n",
        ".docs/instructions.md": _instructions(case),
        ".meta/config.json": json.dumps({"authors":["w8-biayn"],"blurb":case.title,"files":{"solution":[f"{case.task_id}.h",f"{case.task_id}.cpp"],"test":["task_visible_test.cpp",".meta/task_hidden_test.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}},indent=2,sort_keys=True)+"\n",
        ".meta/provenance.json": json.dumps(_provenance(case),indent=2,sort_keys=True)+"\n",
        ".meta/requirements.json": json.dumps(_requirements(case),indent=2,sort_keys=True)+"\n",
        ".meta/tests.toml": f'visible = "public examples for {case.mechanism}"\nhidden = "invalid boundary and {case.negative_reason}"\n',
        ".meta/example.h": header,
        ".meta/example.cpp": _source(case, case.definition),
        ".meta/task_hidden_test.cpp": _test(case, case.hidden),
        ".meta/negative_false_substitute.cpp": _source(case, negative),
        f"{case.task_id}.h": header,
        f"{case.task_id}.cpp": _source(case, case.starter),
        "task_visible_test.cpp": _test(case, case.visible),
        "CMakeLists.txt": CMAKE.replace("@TASK_ID@", case.task_id),
    }
    for relative, content in files.items():
        _write(root / relative, content)


def _safe_force(out: Path) -> dict[Path, bytes]:
    if not out.exists():
        return {}
    for config in out.glob("*/.meta/config.json"):
        provenance = config.parent / "provenance.json"
        if not provenance.is_file() or json.loads(provenance.read_text()).get("family_id") != FAMILY_ID:
            _fail("foreign_generated_root", str(config.parent.parent))
    preserved = {
        path.relative_to(out): path.read_bytes()
        for directory in (out/".state/audits", out/".state/remedy", out/".state/cycles")
        if directory.is_dir()
        for path in directory.rglob("*")
        if path.is_file()
    }
    shutil.rmtree(out)
    return preserved


def _controls(out: Path) -> dict[str, Path]:
    source, base = out / CASES[0].task_id, out / ".state/adversarial-clone-controls"
    controls = {}
    for name in CONTROL_NAMES:
        target = base / name
        shutil.copytree(source, target)
        controls[name] = target
    renamed = controls["domain-identifier-renamed"]
    replacements = (
        ("idtx-generation-slot-pool", "idtx-permit-entry-ledger"),
        ("GenerationSlotPool", "PermitEntryLedger"),
        ("Generation slot pool", "Permit entry ledger"),
        ("generation slot pool", "permit entry ledger"),
        ("generation-stamped reusable slot handles", "revision-stamped reusable permit tickets"),
        ("acquire", "claim"), ("release", "retire"), ("resolve", "lookup"),
        ("Handle", "Ticket"), ("handle", "ticket"), ("Slot", "Entry"), ("slots_", "entries_"),
        ("generation", "revision"), ("payload", "resource"), ("slot", "entry"),
        ("capacity", "limit"),
    )
    for path in sorted((p for p in renamed.rglob("*") if p.is_file()), reverse=True):
        content = path.read_text()
        for old, new in replacements:
            content = content.replace(old, new)
        path.write_text(content)
    for suffix in (".h", ".cpp"):
        old = renamed / f"{CASES[0].task_id}{suffix}"
        old.rename(renamed / f"idtx-permit-entry-ledger{suffix}")
    renamed_requirements = renamed/".meta/requirements.json"
    renamed_payload = json.loads(renamed_requirements.read_text())
    for role, relative in (("visible", "task_visible_test.cpp"), ("hidden", ".meta/task_hidden_test.cpp"), ("negative", ".meta/negative_false_substitute.cpp")):
        digest=file_hash(renamed/relative)
        renamed_payload["assertion_artifacts"][role]["sha256"] = digest
        for assertion in renamed_payload["assertion_catalog"]:
            if assertion["role"]==role:
                assertion["artifact_sha256"]=digest
    renamed_requirements.write_text(json.dumps(renamed_payload, indent=2, sort_keys=True)+"\n")
    for relative in ("task_visible_test.cpp", ".meta/task_hidden_test.cpp", ".docs/instructions.md"):
        path = controls["constants-policy-only"] / relative
        path.write_text(path.read_text().replace("7","17").replace("9","19"))
    for relative in (".meta/example.cpp", ".meta/negative_false_substitute.cpp"):
        path = controls["opposite-end-selection"] / relative
        before = path.read_text()
        after = before.replace("for(std::size_t i=0;i<slots_.size();++i)","for(std::size_t i=slots_.size();i-->0;)",1)
        if after == before:
            _fail("clone_control_noop", str(path))
        path.write_text(after)
    opposite = controls["opposite-end-selection"]
    instructions = opposite/".docs/instructions.md"
    instructions.write_text(instructions.read_text().replace(
        "## Normative contract",
        "## Normative contract\n\nThis coherent variant scans free slots from the highest index down; returned handles expose that descending choice.",
    ))
    hidden = opposite/".meta/task_hidden_test.cpp"
    hidden.write_text(hidden.read_text().replace(
        "check(a&&b&&!p.acquire(3));",
        "check(a&&b&&!p.acquire(3));check(a->slot==1&&b->slot==0);",
    ))
    requirements = opposite/".meta/requirements.json"
    payload = json.loads(requirements.read_text())
    payload["variant_rule"] = "scan free slots from the highest index down"
    hidden_hash=file_hash(hidden)
    payload["assertion_artifacts"]["hidden"]["sha256"] = hidden_hash
    for assertion in payload["assertion_catalog"]:
        if assertion["role"]=="hidden":
            assertion["artifact_sha256"]=hidden_hash
    requirements.write_text(json.dumps(payload, indent=2, sort_keys=True)+"\n")
    return controls


def build(out: Path = DEFAULT_OUT, *, force: bool = False) -> list[Path]:
    _validate_output(out)
    if len(CASES) != 60 or len({c.task_id for c in CASES}) != 60:
        _fail("count_mismatch", f"expected 60 unique roots, got {len(CASES)}")
    if set(OPERATION_CONTRACTS)!={c.task_id for c in CASES}:
        _fail("operation_contract_inventory_mismatch",repr(sorted(set(OPERATION_CONTRACTS)^{c.task_id for c in CASES})))
    _validate_operation_contract_source(OPERATION_CONTRACTS)
    existing = _existing_ids(out)
    collisions = sorted(c.task_id for c in CASES if c.task_id in existing)
    if collisions:
        _fail("task_id_collision", json.dumps({x:existing[x] for x in collisions}))
    preserved: dict[Path, bytes] = {}
    if out.exists():
        if not force:
            _fail("output_exists", f"pass --force for owner-controlled regeneration: {out}")
        preserved = _safe_force(out)
    out.mkdir(parents=True)
    for relative, content in preserved.items():
        path = out/relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    roots = []
    for case in CASES:
        root = out / case.task_id
        _materialize(case, root)
        roots.append(root)
    controls = _controls(out)
    legacy, reverify = _inventory(LEGACY_ROOT), _inventory(REVERIFY_ROOT)
    _write(out/".state/proposals.json",json.dumps({"schema_version":"idtx-proposals-v1","raw_proposal_count":60,"selected_count":60,"rejected_count":0,"selected":[c.task_id for c in CASES],"rejected":[]},indent=2,sort_keys=True)+"\n")
    _write(out/".state/source-inventory.json",json.dumps({"legacy":{"count":len(legacy),"hash":_inventory_hash(legacy),"roots":legacy},"reverify":{"count":len(reverify),"hash":_inventory_hash(reverify),"roots":reverify},"reserved_task_ids":sorted(existing),"controls":{n:tree_hash(p,include_state=True) for n,p in controls.items()}},indent=2,sort_keys=True)+"\n")
    return roots


def _prompt_and_roles(root: Path, case: object) -> dict[str, str]:
    config = json.loads((root/".meta/config.json").read_text())
    expected = [f"{case.task_id}.h",f"{case.task_id}.cpp"]
    if config["files"]["solution"] != expected:
        _fail("target_reference_mismatch",case.task_id)
    task = load_task(root)
    prompt = build_prompt(task)
    forbidden = (".meta/","CMakeLists","task_visible_test","task_hidden_test","provenance","negative_false_substitute",case.definition)
    if any(token in prompt for token in forbidden):
        _fail("prompt_private_asset_leak",case.task_id)
    answer = build_assistant_response(task,load_example_files_from_config(root))
    if not answer.startswith(f"{case.task_id}.h\n```\n") or answer.count("```") != 4:
        _fail("target_reference_mismatch",case.task_id)
    return {"prompt_hash":sha256_bytes(prompt.encode()),"answer_hash":sha256_bytes(answer.encode())}


def _validate_requirements(root: Path, case: object) -> None:
    path=root/".meta/requirements.json"
    actual=json.loads(path.read_text())
    expected=_requirements(case)
    if actual!=expected:
        _fail("requirement_trace_drift",case.task_id)
    instructions=(root/".docs/instructions.md").read_text()
    for requirement in actual["requirements"]:
        if requirement["clause"] not in instructions or not requirement["assertion_ids"]:
            _fail("public_requirement_unmapped",f"{case.task_id}:{requirement['requirement_id']}")
    catalog={row["assertion_id"] for row in actual["assertion_catalog"]}
    referenced={assertion_id for requirement in actual["requirements"] for assertion_id in requirement["assertion_ids"]}
    if catalog!=referenced:
        _fail("assertion_trace_incomplete",case.task_id)


def _cross_tree_screen(roots: list[Path]) -> dict[str, object]:
    comparisons, strongest, strongest_pair = 0, 0.0, []
    candidates = {root.name:shingles(semantic_text(root)) for root in roots}
    for tree in (LEGACY_ROOT,REVERIFY_ROOT):
        for record in _inventory(tree):
            other = shingles(semantic_text(tree/record["relative_root"]))
            for root in roots:
                current = candidates[root.name]
                score = len(current&other)/min(len(current),len(other)) if current and other else 0.0
                comparisons += 1
                if score > strongest:
                    strongest,strongest_pair = score,[root.name,record["relative_root"]]
                if score >= 0.90:
                    _fail("cross_tree_semantic_overlap",f"{strongest_pair}: {score:.4f}")
    return {"status":"pass","comparison_count":comparisons,"threshold":0.90,"strongest_pair":strongest_pair,"strongest_containment":round(strongest,6)}


def _holdout_screen(roots: list[Path]) -> dict[str, object]:
    found = {p.name for p in HOLDOUT_ROOT.iterdir() if p.is_dir()} if HOLDOUT_ROOT.is_dir() else set()
    if missing := sorted(OFFICIAL_HOLDOUTS-found):
        _fail("benchmark_content_unavailable",repr(missing))
    comparisons, strongest, strongest_pair = 0, 0.0, []
    candidates = {root.name:shingles(semantic_text(root)) for root in roots}
    for holdout in sorted(OFFICIAL_HOLDOUTS):
        other = shingles(semantic_text(HOLDOUT_ROOT/holdout))
        for root in roots:
            current = candidates[root.name]
            score = len(current&other)/min(len(current),len(other)) if current and other else 0.0
            comparisons += 1
            if score > strongest:
                strongest,strongest_pair = score,[root.name,holdout]
            if score >= 0.80:
                _fail("benchmark_content_overlap",f"{strongest_pair}: {score:.4f}")
    return {"status":"pass","holdout_root_count":26,"comparison_count":comparisons,"threshold":0.80,"strongest_pair":strongest_pair,"strongest_containment":round(strongest,6)}


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    roots = [out/c.task_id for c in CASES]
    if not all(root.is_dir() for root in roots):
        _fail("generator_output_drift","regenerate the complete family")
    prompts, answers, rows = set(), set(), []
    for case,root in zip(CASES,roots,strict=True):
        _validate_requirements(root,case)
        boundary = _prompt_and_roles(root,case)
        if boundary["prompt_hash"] in prompts or boundary["answer_hash"] in answers:
            _fail("duplicate_prompt_or_answer",case.task_id)
        prompts.add(boundary["prompt_hash"]);answers.add(boundary["answer_hash"])
        rows.append({"task_id":case.task_id,"group":case.group,"mechanism":case.mechanism,"lineage":"new-root","tree_hash":tree_hash(root),**boundary,"editable_manifest_hash":file_hash(root/".meta/config.json"),"starter_hashes":[file_hash(root/f"{case.task_id}.h"),file_hash(root/f"{case.task_id}.cpp")],"reference_hashes":[file_hash(root/".meta/example.h"),file_hash(root/".meta/example.cpp")],"visible_test_hash":file_hash(root/"task_visible_test.cpp"),"hidden_test_hash":file_hash(root/".meta/task_hidden_test.cpp"),"negative_hash":file_hash(root/".meta/negative_false_substitute.cpp"),"provenance_hash":file_hash(root/".meta/provenance.json"),"primary_core_objective":"achieved_pending_runtime_confirmation"})
    controls = {name:out/".state/adversarial-clone-controls"/name for name in CONTROL_NAMES}
    diversity = family_screen(roots,controls)
    manifest = {"schema_version":"idtx-materialization-v2","family_id":FAMILY_ID,"task_count":60,"group_counts":{group:sum(c.group==group for c in CASES) for group in ("identity","collision","reset","transactions")},"owner_hash":file_hash(GENERATOR),"case_hashes":{p.as_posix():file_hash(p) for p in CASE_PATHS},"operation_contracts_hash":file_hash(CONTRACTS),"hard_rule_hash":file_hash(HARD_RULE),"curriculum_hash":file_hash(CURRICULUM),"family_spec_hash":file_hash(FAMILY_SPEC),"focused_test_hash":file_hash(FOCUSED_TEST),"family_tree_hash":tree_hash(out),"control_tree_hashes":{name:tree_hash(path,include_state=True) for name,path in controls.items()},"tasks":rows,"screen":{"prompt_boundary":"pass","reference_mapping":"pass","requirements_trace":"pass","diversity":diversity,"cross_tree":_cross_tree_screen(roots),"benchmark_holdout":_holdout_screen(roots)},"strongest_local_status":"pending_execution","dataset_handoff":"not_requested"}
    _write(out/".state/materialization-manifest.json",json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    return manifest


def _archive(out: Path,target: Path) -> str:
    roots = [out/c.task_id for c in CASES]+[out/".state/adversarial-clone-controls"/n for n in CONTROL_NAMES]
    with tarfile.open(target,"w",format=tarfile.PAX_FORMAT) as archive:
        for root in roots:
            prefix = "tasks" if root.parent==out else "controls"
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                info = archive.gettarinfo(str(path),arcname=f"{prefix}/{root.name}/{path.relative_to(root).as_posix()}")
                info.uid=info.gid=info.mtime=0;info.uname=info.gname="";info.mode=0o644
                with path.open("rb") as handle:
                    archive.addfile(info,handle)
    return file_hash(target)


DOCKER_SCRIPT = r'''set -Eeuo pipefail
mkdir -p /work /result
report_failure(){
  code=$?
  echo "docker oracle command failed with exit ${code}" >&2
  for log in /tmp/config.log /tmp/build.log /tmp/test.log; do
    if [ -f "$log" ]; then
      echo "===== ${log} =====" >&2
      tail -200 "$log" >&2
    fi
  done
  exit "$code"
}
trap report_failure ERR
tar -xf /input/family.tar -C /work
sha256sum /input/family.tar | awk '{print "archive\t"$1}' > /result/results.tsv
command -v c++ > /result/compiler.path
c++ --version | head -1 > /result/compiler.version
sha256sum "$(command -v c++)" | awk '{print $1}' > /result/compiler.sha256
cmake --version | head -1 > /result/cmake.version
run_one(){
  kind="$1"; id="$2"; mode="$3"; source="$4"
  root="/work/${kind}/${id}"; build="/tmp/${kind}-${id}-${mode}-${source##*/}"
  flags=()
  if [ "$mode" = sanitizer ]; then
    flags+=("-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined")
  fi
  cmake -S "$root" -B "$build" -G "Unix Makefiles" -DTASK_SOURCE="$root/$source" "${flags[@]}" >/tmp/config.log 2>&1
  cmake --build "$build" --parallel 2 >/tmp/build.log 2>&1
  count=$(ctest --test-dir "$build" -N | sed -n 's/^Total Tests: //p')
  test "$count" = 2
  if [ "$source" = .meta/negative_false_substitute.cpp ]; then
    rejectors=""
    if ! "$build/task_visible" >/tmp/test-visible.log 2>&1; then rejectors="visible"; fi
    if ! "$build/task_hidden" >/tmp/test-hidden.log 2>&1; then rejectors="${rejectors:+${rejectors},}hidden"; fi
    if [ -z "$rejectors" ]; then echo "negative passed $id" >&2; exit 71; fi
    outcome="expected_negative_rejection"
  else
    ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$build" --output-on-failure >/tmp/test.log 2>&1
    rejectors="-"
    outcome="reference_pass"
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$kind" "$id" "$mode" "$source" "$count" "$outcome" "$rejectors" >>/result/results.tsv
}
for root in /work/tasks/*; do
  id=${root##*/}
  run_one tasks "$id" normal .meta/example.cpp
  run_one tasks "$id" sanitizer .meta/example.cpp
  run_one tasks "$id" normal .meta/negative_false_substitute.cpp
done
for root in /work/controls/*; do
  id=${root##*/}
  run_one controls "$id" normal .meta/example.cpp
  run_one controls "$id" sanitizer .meta/example.cpp
done
'''


def verify_docker(out: Path=DEFAULT_OUT,image: str=SANITY_IMAGE) -> dict[str,object]:
    manifest_path = out/".state/materialization-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest["family_tree_hash"]!=tree_hash(out) or manifest["owner_hash"]!=file_hash(GENERATOR):
        _fail("generator_output_drift","core manifest is stale")
    with tempfile.TemporaryDirectory(prefix="idtx-docker-") as temporary:
        temp=Path(temporary);archive=temp/"family.tar";result=temp/"result";result.mkdir()
        archive_hash=_archive(out,archive)
        completed=subprocess.run(["docker","run","--rm","--network","none","--mount",f"type=bind,src={archive},dst=/input/family.tar,readonly","--mount",f"type=bind,src={result},dst=/result",image,"bash","-lc",DOCKER_SCRIPT],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if completed.returncode!=0:
            _fail("docker_sanity_failed",(completed.stdout+completed.stderr)[-12000:])
        rows=[line.split("\t") for line in (result/"results.tsv").read_text().splitlines()]
        mounted="sha256:"+rows[0][1]
        if mounted!=archive_hash:
            _fail("grader_mount_hash_mismatch",f"{mounted} != {archive_hash}")
        execution_rows=rows[1:]
        refs=[r for r in execution_rows if r[0]=="tasks" and r[3]==".meta/example.cpp"]
        negatives=[r for r in execution_rows if r[0]=="tasks" and r[3]==".meta/negative_false_substitute.cpp"]
        controls=[r for r in execution_rows if r[0]=="controls"]
        if (len(refs),len(negatives),len(controls))!=(120,60,6):
            _fail("sanitizer_test_count_mismatch",f"{len(refs)}, {len(negatives)}, {len(controls)}")
        task_manifest={row["task_id"]:row for row in manifest["tasks"]}
        records=[]
        for kind,identifier,mode,source,count,outcome,rejectors in execution_rows:
            root=(out/identifier) if kind=="tasks" else (out/".state/adversarial-clone-controls"/identifier)
            task_row=task_manifest.get(identifier)
            hashes={
                "root_tree_hash":tree_hash(root,include_state=(kind=="controls")),
                "reference_hash":file_hash(root/".meta/example.cpp"),
                "visible_test_hash":file_hash(root/"task_visible_test.cpp"),
                "hidden_test_hash":file_hash(root/".meta/task_hidden_test.cpp"),
                "negative_hash":file_hash(root/".meta/negative_false_substitute.cpp"),
            }
            if task_row and hashes["root_tree_hash"]!=task_row["tree_hash"]:
                _fail("row_tree_hash_mismatch",identifier)
            if kind=="controls" and hashes["root_tree_hash"]!=manifest["control_tree_hashes"].get(identifier):
                _fail("control_tree_hash_mismatch",identifier)
            build_dir=f"/tmp/{kind}-{identifier}-{mode}-{source.rsplit('/',1)[-1]}"
            flags=" -DCMAKE_CXX_FLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' -DCMAKE_EXE_LINKER_FLAGS='-fsanitize=address,undefined'" if mode=="sanitizer" else ""
            records.append({
                "kind":kind,"task_id":identifier,"mode":mode,"source":source,
                "discovered_test_count":int(count),"outcome":outcome,
                "rejecting_tests":[] if rejectors=="-" else rejectors.split(","),
                "artifact_hashes":hashes,
                "commands":{
                    "configure":f"cmake -S /work/{kind}/{identifier} -B {build_dir} -G 'Unix Makefiles' -DTASK_SOURCE=/work/{kind}/{identifier}/{source}{flags}",
                    "build":f"cmake --build {build_dir} --parallel 2",
                    "discover":f"ctest --test-dir {build_dir} -N",
                    "execute":f"ASAN_OPTIONS=detect_leaks=0 ctest --test-dir {build_dir} --output-on-failure" if source==".meta/example.cpp" else f"{build_dir}/task_visible ; {build_dir}/task_hidden (at least one must reject)",
                },
            })
        policy_hash=sha256_bytes((image+DOCKER_SCRIPT+CMAKE).encode())
        ledger={"schema_version":"idtx-row-oracle-ledger-v1","status":"pass","family_id":FAMILY_ID,"family_tree_hash":tree_hash(out),"owner_hash":file_hash(GENERATOR),"policy_hash":policy_hash,"archive_hash":archive_hash,"mounted_archive_hash":mounted,"image":image,"network_policy":"none","records":records}
        ledger_path=out/".state/docker-oracle-ledger.json"
        _write(ledger_path,json.dumps(ledger,indent=2,sort_keys=True)+"\n")
        receipt={"schema_version":"idtx-docker-sanity-v2","status":"pass","evidence_class":"docker_sanity","locked_oracle":False,"network_policy":"none","image":image,"archive_hash":archive_hash,"mounted_archive_hash":mounted,"family_tree_hash":tree_hash(out),"owner_hash":file_hash(GENERATOR),"policy_hash":policy_hash,"compiler":{"path":(result/"compiler.path").read_text().strip(),"version":(result/"compiler.version").read_text().strip(),"sha256":"sha256:"+(result/"compiler.sha256").read_text().strip()},"cmake":(result/"cmake.version").read_text().strip(),"normal_reference_count":60,"sanitizer_reference_count":60,"normal_test_count_per_root":2,"sanitizer_test_count_per_root":2,"negative_fixture_count":60,"control_count":3,"row_count":len(records),"ledger":".state/docker-oracle-ledger.json","ledger_hash":file_hash(ledger_path)}
        _write(out/".state/docker-sanity.json",json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    manifest=json.loads(manifest_path.read_text())
    ledger=json.loads((out/".state/docker-oracle-ledger.json").read_text())
    by_task={task_id:[row for row in ledger["records"] if row["kind"]=="tasks" and row["task_id"]==task_id] for task_id in task_manifest}
    for task in manifest["tasks"]:
        task_rows=by_task[task["task_id"]]
        if len(task_rows)!=3 or {row["outcome"] for row in task_rows}!={"reference_pass","expected_negative_rejection"} or any(row["discovered_test_count"]!=2 for row in task_rows):
            _fail("row_oracle_reconciliation_failed",task["task_id"])
        task["primary_core_objective"]="achieved"
        task["creator_disposition"]="retained_pending_independent_audit"
        task["runtime_evidence"]={"ledger":".state/docker-oracle-ledger.json","record_keys":[[row["mode"],row["source"]] for row in task_rows]}
    manifest["docker_sanity"]={"status":"pass","receipt":".state/docker-sanity.json","ledger":".state/docker-oracle-ledger.json","ledger_hash":file_hash(out/".state/docker-oracle-ledger.json")};manifest["strongest_local_status"]="creator_preflight_passed_pending_independent_audit"
    _write(manifest_path,json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    return receipt


HOST_VERIFY_WORKERS = 8


def _host_tool(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        _fail("host_toolchain_missing", tool)
    return path


def _run_host_job(job: tuple[str, Path, str, str, str], build_parent: Path) -> dict[str, object]:
    kind, root, identifier, mode, source = job
    build = build_parent / f"{kind}-{identifier}-{mode}-{source.rsplit('/', 1)[-1]}"
    flags: list[str] = []
    if mode == "sanitizer":
        flags = ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]
    configure = ["cmake", "-S", str(root), "-B", str(build), "-G", "Unix Makefiles", f"-DTASK_SOURCE={root}/{source}", *flags]
    completed = subprocess.run(configure, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode != 0:
        _fail("reference_compile_failed", f"{identifier}/{mode}/{source} configure: {completed.stdout[-4000:]}")
    completed = subprocess.run(["cmake", "--build", str(build), "--parallel", "2"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode != 0:
        _fail("reference_compile_failed", f"{identifier}/{mode}/{source} build: {completed.stdout[-4000:]}")
    discovery = subprocess.run(["ctest", "--test-dir", str(build), "-N"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    match = re.search(r"^Total Tests: (\d+)$", discovery.stdout, re.M)
    count = int(match.group(1)) if match else 0
    if count == 0:
        _fail("zero_tests", f"{identifier}/{mode}/{source}")
    if count != 2:
        _fail("sanitizer_test_count_mismatch", f"{identifier}/{mode}/{source}: {count}")
    env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0")
    if source == ".meta/negative_false_substitute.cpp":
        rejectors = [name for name in ("task_visible", "task_hidden") if subprocess.run([str(build / name)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env).returncode != 0]
        if not rejectors:
            _fail("negative_fixture_not_rejected", identifier)
        outcome = "expected_negative_rejection"
    else:
        completed = subprocess.run(["ctest", "--test-dir", str(build), "--output-on-failure"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
        if completed.returncode != 0:
            _fail("reference_sanitizer_failed" if mode == "sanitizer" else "reference_tests_failed", f"{identifier}/{mode}: {completed.stdout[-4000:]}")
        rejectors = []
        outcome = "reference_pass"
    return {"kind": kind, "task_id": identifier, "mode": mode, "source": source, "discovered_test_count": count, "outcome": outcome, "rejecting_tests": rejectors,
            "commands": {"configure": " ".join(configure), "build": f"cmake --build {build} --parallel 2", "discover": f"ctest --test-dir {build} -N",
                         "execute": f"ASAN_OPTIONS=detect_leaks=0 ctest --test-dir {build} --output-on-failure" if source == ".meta/example.cpp" else f"{build}/task_visible ; {build}/task_hidden (at least one must reject)"}}


def verify_host(out: Path = DEFAULT_OUT, *, cases: Sequence[object] | None = None) -> dict[str, object]:
    full = cases is None
    selected = list(CASES if full else cases or [])
    manifest_path = out / ".state/materialization-manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else None
    if full and (manifest is None or manifest["family_tree_hash"] != tree_hash(out) or manifest["owner_hash"] != file_hash(GENERATOR)):
        _fail("generator_output_drift", "core manifest is stale")
    compiler = _host_tool("c++")
    _host_tool("cmake")
    _host_tool("ctest")
    compiler_version = subprocess.run([compiler, "--version"], text=True, stdout=subprocess.PIPE).stdout.splitlines()[0]
    cmake_version = subprocess.run(["cmake", "--version"], text=True, stdout=subprocess.PIPE).stdout.splitlines()[0]
    jobs: list[tuple[str, Path, str, str, str]] = []
    for case in selected:
        root = out / case.task_id
        jobs += [("tasks", root, case.task_id, "normal", ".meta/example.cpp"), ("tasks", root, case.task_id, "sanitizer", ".meta/example.cpp"), ("tasks", root, case.task_id, "normal", ".meta/negative_false_substitute.cpp")]
    if full:
        for name in CONTROL_NAMES:
            root = out / ".state/adversarial-clone-controls" / name
            jobs += [("controls", root, name, "normal", ".meta/example.cpp"), ("controls", root, name, "sanitizer", ".meta/example.cpp")]
    with tempfile.TemporaryDirectory(prefix="idtx-host-") as temporary:
        parent = Path(temporary)
        with ThreadPoolExecutor(max_workers=HOST_VERIFY_WORKERS) as pool:
            futures = [pool.submit(_run_host_job, job, parent) for job in jobs]
            rows = sorted((future.result() for future in futures), key=lambda row: (row["kind"], row["task_id"], row["mode"], row["source"]))
    records = []
    for row in rows:
        root = (out / row["task_id"]) if row["kind"] == "tasks" else (out / ".state/adversarial-clone-controls" / row["task_id"])
        row["artifact_hashes"] = {
            "root_tree_hash": tree_hash(root, include_state=(row["kind"] == "controls")),
            "reference_hash": file_hash(root / ".meta/example.cpp"),
            "visible_test_hash": file_hash(root / "task_visible_test.cpp"),
            "hidden_test_hash": file_hash(root / ".meta/task_hidden_test.cpp"),
            "negative_hash": file_hash(root / ".meta/negative_false_substitute.cpp"),
        }
        records.append(row)
    policy_hash = sha256_bytes(("host" + json.dumps({"workers": HOST_VERIFY_WORKERS, "sanitizer_flags": "-fsanitize=address,undefined -fno-omit-frame-pointer"}, sort_keys=True) + CMAKE).encode())
    receipt = {"schema_version": "idtx-host-verify-v1", "status": "pass", "evidence_class": "host_verify", "locked_oracle": False, "network_policy": "host-local (no container; campaign gate: host verify only)", "family_tree_hash": tree_hash(out), "owner_hash": file_hash(GENERATOR), "policy_hash": policy_hash,
               "compiler": {"path": compiler, "version": compiler_version, "sha256": file_hash(Path(compiler))}, "cmake": cmake_version,
               "normal_reference_count": len(selected), "sanitizer_reference_count": len(selected), "negative_fixture_count": len(selected), "control_count": len(CONTROL_NAMES) if full else 0, "normal_test_count_per_root": 2, "sanitizer_test_count_per_root": 2, "row_count": len(records), "records": records}
    if not full:
        return receipt
    receipt_path = out / ".state/host-verify.json"
    _write(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    task_manifest = {row["task_id"]: row for row in manifest["tasks"]}
    for row in records:
        task_row = task_manifest.get(row["task_id"])
        if task_row and row["artifact_hashes"]["root_tree_hash"] != task_row["tree_hash"]:
            _fail("row_tree_hash_mismatch", row["task_id"])
        if row["kind"] == "controls" and row["artifact_hashes"]["root_tree_hash"] != manifest["control_tree_hashes"].get(row["task_id"]):
            _fail("control_tree_hash_mismatch", row["task_id"])
    for task in manifest["tasks"]:
        task_rows = [row for row in records if row["kind"] == "tasks" and row["task_id"] == task["task_id"]]
        if len(task_rows) != 3 or {row["outcome"] for row in task_rows} != {"reference_pass", "expected_negative_rejection"} or any(row["discovered_test_count"] != 2 for row in task_rows):
            _fail("row_oracle_reconciliation_failed", task["task_id"])
        task["primary_core_objective"] = "achieved"
        task["creator_disposition"] = "retained_pending_independent_audit"
        task["runtime_evidence"] = {"receipt": ".state/host-verify.json", "evidence_class": "host_verify", "record_keys": [[row["mode"], row["source"]] for row in task_rows]}
    manifest["host_verify"] = {"status": "pass", "evidence_class": "host_verify", "receipt": ".state/host-verify.json", "receipt_hash": file_hash(receipt_path)}
    manifest["strongest_local_status"] = "host_verify_passed_pending_independent_audit"
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return receipt


def append_cycle(out: Path,status: str) -> Path:
    cycles=out/".state/cycles";cycles.mkdir(parents=True,exist_ok=True);number=len(list(cycles.glob("cycle-*.json")))+1
    manifest=json.loads((out/".state/materialization-manifest.json").read_text())
    record={"schema_version":"aider-task-creator-cycle-v1","cycle":number,"timestamp":datetime.now(timezone.utc).isoformat(),"status":status,"family_id":FAMILY_ID,"candidate_manifest":".state/materialization-manifest.json","audit_subject_hash":sha256_bytes(json.dumps(manifest,sort_keys=True).encode()),"family_tree_hash":tree_hash(out),"curriculum_hash":file_hash(CURRICULUM),"generator_hash":file_hash(GENERATOR),"operation_contracts_hash":file_hash(CONTRACTS),"hard_rule_hash":file_hash(HARD_RULE),"focused_test_hash":file_hash(FOCUSED_TEST),"grader_policy_hash":sha256_bytes((SANITY_IMAGE+CMAKE).encode()),"retained_root_ids":[c.task_id for c in CASES],"replaced_root_ids":[],"rejected_root_ids":[],"review_root_ids":[],"blocked_root_ids":[],"prior_evidence_invalidated":[],"docker_receipt":json.loads((out/".state/docker-sanity.json").read_text()) if (out/".state/docker-sanity.json").is_file() else None}
    path=cycles/f"cycle-{number:02d}.json";_write(path,json.dumps(record,indent=2,sort_keys=True)+"\n");return path


def main(argv: Sequence[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--out",type=Path,default=DEFAULT_OUT);parser.add_argument("--force",action="store_true");parser.add_argument("--verify-core",action="store_true");parser.add_argument("--verify-host",action="store_true");parser.add_argument("--docker-sanity",action="store_true");parser.add_argument("--record-cycle",action="store_true");parser.add_argument("--image",default=os.environ.get("W8_IDTX_GRADER_IMAGE",SANITY_IMAGE));args=parser.parse_args(argv)
    roots=build(args.out,force=args.force)
    if args.verify_core or args.verify_host or args.docker_sanity:verify_core(args.out)
    if args.verify_host:verify_host(args.out)
    if args.docker_sanity:verify_docker(args.out,args.image)
    if args.record_cycle:append_cycle(args.out,"creator_preflight" if args.docker_sanity else ("host_verify" if args.verify_host else "generated"))
    print(f"Wrote {len(roots)} identity/collision/reset/transaction roots under {args.out}");return 0


if __name__=="__main__":
    raise SystemExit(main())
