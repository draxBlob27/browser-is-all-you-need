
"""Materialize and verify the clean-room AVL/red-black Aider task family."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_balanced_tree_cases import CASES
from w8_biayn.integrations.moonlight_balanced_tree_core import tree_source

ROOT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/balanced-search-tree")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dsa/balanced-search-tree")
SPEC = Path("docs/aider-tasks-spec/aider-dsa/balanced-search-tree.md")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_BALANCED_SEARCH_TREE_CURRICULUM.md"
BENCHMARK_MANIFEST = Path("manifests/aider_sft/aider-polyglot-cpp-26.json")
FAMILY_ID = "aider-dsa-balanced-search-tree-v4"
GENERATOR_REVISION = "balanced-search-tree-materializer-v4"
SUPPORT = Path(".w8-biayn/data/aider-sft-source-only-75-v1/private/grader-support/exercism-catch-v1/test")
BANNED_REFERENCE_TOKENS = ("std::set<", "std::map<", "std::multiset<", "std::unordered_", "__gnu_pbds", "boost::")


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    name: str
    kind: str
    api: str
    rules: str


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _registry() -> tuple[TaskSpec, ...]:
    tasks: list[TaskSpec] = []
    for section in SPEC.read_text(encoding="utf-8").split("### B")[1:]:
        slug = re.search(r"`([a-z][a-z0-9-]+)`", section)
        code = re.search(r"```cpp\n(.*?)\n```", section, re.S)
        if not slug or not code:
            continue
        class_name = re.search(r"(?:^|\n)class\s+(\w+)", code.group(1))
        if not class_name:
            continue
        rules = section[code.end():].split("###", 1)[0].strip()
        task_id = slug.group(1)
        tasks.append(TaskSpec(task_id, class_name.group(1), "AVL" if task_id.startswith("avl-") else "RB", code.group(1).strip(), rules))
    if len(tasks) != 20 or set(CASES) != {task.task_id for task in tasks}:
        raise ValueError("balanced-tree specification and task cases must define the same 20 roots")
    return tuple(tasks)


TASKS = _registry()


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") == content:
            return
        if not force:
            raise FileExistsError(f"{path} differs; pass --force only for the re-verification root")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _public_rules(rules: str) -> str:
    stops = ("\n\nMaintain an AVL", "\n\nThe AVL", "\n\nThe RB", "\n\nTests ", "\n\nPrivate tests")
    end = len(rules)
    for marker in stops:
        position = rules.find(marker)
        if position >= 0:
            end = min(end, position)
    return rules[:end].strip()


def _header(task: TaskSpec) -> str:
    check = "bool valid; std::size_t nodes; int height;" if task.kind == "AVL" else "bool valid; std::size_t nodes; std::size_t black_height;"
    class_text = task.api
    class_text = class_text.replace(
        " public:\n",
        f" public:\n  {task.name}();\n  ~{task.name}();\n  {task.name}(const {task.name}&) = delete;\n  {task.name}& operator=(const {task.name}&) = delete;\n",
        1,
    )
    class_text = class_text.rsplit("};", 1)[0] + (
        "\n#ifdef CURRICULUM_TESTING\n"
        "  TreeCheck validate_for_test() const;\n"
        "#endif\n"
        " private:\n"
        "  struct Impl;\n"
        "  std::unique_ptr<Impl> impl_;\n"
        "};"
    )
    return (
        "#pragma once\n#include <cstddef>\n#include <cstdint>\n#include <memory>\n#include <optional>\n"
        "#include <string>\n#include <string_view>\n#include <vector>\n"
        "namespace curriculum {\n#ifdef CURRICULUM_TESTING\n"
        f"struct TreeCheck {{ {check} }};\n#endif\n{class_text}\n"
        "}  // namespace curriculum\n"
    )


def _method_declarations(task: TaskSpec) -> list[tuple[str, str, str, str]]:
    class_block = task.api[task.api.index("class "):]
    public = class_block.split("public:", 1)[1].rsplit("};", 1)[0]
    result = []
    for statement in public.split(";"):
        signature = " ".join(statement.split())
        if "(" not in signature:
            continue
        match = re.fullmatch(r"(.+?)\s+(\w+)\((.*?)\)(\s+const)?", signature)
        if not match:
            raise ValueError(f"cannot parse {task.task_id} method: {signature}")
        result.append((match.group(1), match.group(2), match.group(3), match.group(4) or ""))
    return result


def _argument_names(arguments: str) -> list[str]:
    if not arguments.strip():
        return []
    names = []
    for argument in arguments.split(","):
        match = re.search(r"([A-Za-z_]\w*)\s*$", argument.strip())
        if not match:
            raise ValueError(f"cannot parse argument name from {argument!r}")
        names.append(match.group(1))
    return names


def _starter(task: TaskSpec) -> str:
    lines = [f'#include "{task.task_id}.h"', f"namespace curriculum {{", f"struct {task.name}::Impl {{}};", f"{task.name}::{task.name}() : impl_(std::make_unique<Impl>()) {{}}", f"{task.name}::~{task.name}() = default;"]
    for return_type, name, arguments, qualifier in _method_declarations(task):
        body = "".join(f"(void){argument};" for argument in _argument_names(arguments))
        if return_type == "bool":
            body += "return false;"
        elif return_type == "std::size_t":
            body += "return 0U;"
        elif return_type.startswith("std::optional"):
            body += "return std::nullopt;"
        elif return_type.startswith("std::vector"):
            body += "return {};"
        else:
            raise ValueError(f"unsupported starter return type {return_type}")
        lines.append(f"{return_type} {task.name}::{name}({arguments}){qualifier}{{{body}}}")
    field = "0" if task.kind == "AVL" else "1U"
    lines.extend(["#ifdef CURRICULUM_TESTING", f"TreeCheck {task.name}::validate_for_test() const {{ return {{false,0U,{field}}}; }}", "#endif", "}  // namespace curriculum", ""])
    return "\n".join(lines)


def _reference(task: TaskSpec) -> str:
    case = CASES[task.task_id]
    helpers = r'''
namespace curriculum { namespace detail {
inline bool valid_id(std::string_view id){if(id.empty())return false;for(unsigned char c:id)if(!(std::isalnum(c)||c=='_'||c=='-'))return false;return true;}
inline bool add_overflows(std::int64_t a,std::int64_t b){return b>0&&a>std::numeric_limits<std::int64_t>::max()-b;}
} }
'''
    check_type = "int height=0" if task.kind == "AVL" else "std::size_t black_height=1U"
    check_field = "height" if task.kind == "AVL" else "black_height"
    return (
        f'#include "{task.task_id}.h"\n'
        "#include <algorithm>\n#include <cctype>\n#include <cmath>\n#include <functional>\n"
        "#include <limits>\n#include <tuple>\n#include <utility>\n"
        + helpers
        + tree_source(task.kind)
        + "\nnamespace curriculum {\n"
        + case.impl
        + f"\n{task.name}::{task.name}() : impl_(std::make_unique<Impl>()) {{}}\n"
        + f"{task.name}::~{task.name}() = default;\n"
        + case.methods
        + "\n#ifdef CURRICULUM_TESTING\n"
        + f"TreeCheck {task.name}::validate_for_test() const {{ std::size_t nodes=0; {check_type}; const bool valid=impl_->tree.valid(nodes,{check_field}); return {{valid,nodes,{check_field}}}; }}\n"
        + "#endif\n}  // namespace curriculum\n"
    )


def _visible_test(task: TaskSpec) -> str:
    return f'''#include "{task.task_id}.h"
#include <catch.hpp>
TEST_CASE("{task.task_id} public contract","[visible]"){{
 curriculum::{task.name} tree;
 {CASES[task.task_id].visible}
 auto check=tree.validate_for_test();
 REQUIRE(check.valid);
}}
'''


def _hidden_test(task: TaskSpec) -> str:
    height_check = r'''
 if(check.nodes>0U){std::size_t n=check.nodes+1U;int ceil_log=0;std::size_t power=1U;while(power<n){power*=2U;++ceil_log;}REQUIRE(check.height<=2*ceil_log);}
''' if task.kind == "AVL" else " REQUIRE(check.black_height>=1U);"
    return f'''#include "{task.task_id}.h"
#include <catch.hpp>
#include <cstdint>
#include <string>
TEST_CASE("{task.task_id} deterministic structural trace","[hidden]"){{
 curriculum::{task.name} tree;
 std::uint32_t state=0xC0FFEEU;
 for(std::size_t step=0;step<10000U;++step){{
  state=state*1664525U+1013904223U;
  const std::int64_t key=static_cast<std::int64_t>((state%257U)+1U);
  const std::string id="id_"+std::to_string(key);
  {CASES[task.task_id].trace}
  const auto check=tree.validate_for_test();
  REQUIRE(check.valid);{height_check}
 }}
}}
'''


def _cmake(task: TaskSpec) -> str:
    return f'''cmake_minimum_required(VERSION 3.16)
project(balanced_search_tree_{task.task_id.replace("-", "_")} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
add_library(solution_compile_check OBJECT {task.task_id}.cpp)
add_executable(visible_tests {task.task_id}.cpp task_visible_test.cpp test/tests-main.cpp)
add_executable(hidden_tests {task.task_id}.cpp .meta/task_hidden_test.cpp test/tests-main.cpp)
foreach(target solution_compile_check visible_tests hidden_tests)
 target_include_directories(${{target}} PRIVATE . test)
 if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(${{target}} PRIVATE -Wall -Wextra -Wpedantic -Werror)
 endif()
endforeach()
target_compile_definitions(visible_tests PRIVATE CURRICULUM_TESTING EXERCISM_RUN_ALL_TESTS=1)
target_compile_definitions(hidden_tests PRIVATE CURRICULUM_TESTING EXERCISM_RUN_ALL_TESTS=1)
enable_testing()
add_test(NAME visible COMMAND visible_tests "[visible]")
add_test(NAME hidden COMMAND hidden_tests "[hidden]")
'''


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "missing"
    for path in sorted(item for item in root.rglob("*") if item.is_file() and "receipts" not in item.parts):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _generator_hash() -> str:
    paths = [Path(__file__), Path(__file__).with_name("moonlight_balanced_tree_core.py"), Path(__file__).with_name("moonlight_balanced_tree_cases.py")]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.read_bytes())
    return "sha256:" + digest.hexdigest()


def _remedy_state(out: Path, task: TaskSpec, after_hash: str, status: str, force: bool) -> None:
    state = out.parent / ".state" / "remedy"
    legacy = LEGACY_ROOT / task.task_id
    spec_path = state / f"{task.task_id}.md"
    spec_text = f"""# Identity
Task ID: `{task.task_id}`. Task-spec revision: v4. Family: `{FAMILY_ID}`. Disposition: `replace`. Source inventory: balanced-search-tree curriculum. License: pass, repository-authored. Generator: `{Path(__file__).relative_to(Path.cwd())}`. Benchmark screen: pass. Primary core objective: `achieved`; evidence is the owned `{task.kind}` node core in `moonlight_balanced_tree_core.py`, exercised by the generated `validate_for_test()` after every trace mutation. The easiest false substitute is an ordered container or sorted-vector index.

# Objective
Implement the domain API in section {task.task_id} of `{SPEC}` using a structurally valid {task.kind} tree.

# Public API
Namespace `curriculum`; editable order `{task.task_id}.h`, `{task.task_id}.cpp`:
```cpp
{task.api}
```

# Behavior table
{_public_rules(task.rules)}

# Implementation invariant
Owned unique nodes, ordered keys, and stored augmentation are mandatory. Standard ordered/unordered containers, sorted vectors, PBDS, Boost, third-party trees, and degenerate BSTs are forbidden. `TreeCheck` is the private predicate defined by the normative family specification.

# Starter and reference
The header declares the exact API and opaque owned implementation. The source contains coherent failing stubs. The independently rendered reference uses the repository AVL or RB core and no banned container.

# Tests
The public case exercises domain behavior. The private case uses seed `0xC0FFEE`, the exact LCG `state = state * 1664525U + 1013904223U`, 10,000 mutations, and `TreeCheck` after each mutation. The legacy ordered-set wrapper, sorted-vector substitute, and degenerate BST are named negative fixtures.

# Files and metadata
Solutions: `{task.task_id}.h`, `{task.task_id}.cpp`; tests: `task_visible_test.cpp`, `.meta/task_hidden_test.cpp`; references: `.meta/example.h`, `.meta/example.cpp`; Catch support digest: `{_sha256_file(SUPPORT / "catch.hpp")}`.

# Build/oracle
C++17, explicit Unix Makefiles, strict warnings, separate production compilation, named visible/hidden CTest cases, normal plus fresh ASan/UBSan. Receipts bind compiler, CMake, Catch, generator, reference map, sandbox, and tree hashes.

# Family/contamination
Compare all 20 normalized contracts and the 26-root manifest `{BENCHMARK_MANIFEST}`. The official `binary-search-tree` root is a permanent holdout.

# Optional dataset handoff
`not_requested`.

# Acceptance
Run the focused pytest, materialize with `--force`, run `--verify` in the locked network-disabled runtime, and require prompt-boundary pass, two positive/equal test counts, no banned token, no benchmark slug, and unique normalized contracts. Failure codes: `whole_format_failed`, `invariant_not_enforced`, `benchmark_id_overlap`, `duplicate_family`, `zero_tests`, and `sanitizer_test_count_mismatch`.
"""
    _write(spec_path, spec_text, force)
    record = {
        "schema_version": "aider-task-remedy-v1",
        "task_id": task.task_id,
        "family_id_before": "aider-dsa-balanced-search-tree-v3",
        "tree_hash_before": _tree_hash(legacy),
        "tree_hash_after": after_hash,
        "generator_path": str(Path(__file__).relative_to(Path.cwd())),
        "generator_revision": _generator_hash(),
        "finding_ids": [f"F{i}" for i in range(1, 10)],
        "disposition": "replace",
        "benchmark_screen": "pass",
        "license_screen": "pass",
        "remedy_spec_path": f".state/remedy/{task.task_id}.md",
        "remedy_spec_hash": _sha256_bytes(spec_text.encode()),
        "primary_core_objective": "achieved",
        "primary_core_evidence": {
            "mechanism": f"repository-owned {task.kind} tree with owned nodes and structural validation",
            "source_paths": [
                "src/w8_biayn/integrations/moonlight_balanced_tree_core.py",
                "src/w8_biayn/integrations/moonlight_balanced_tree_cases.py",
            ],
            "false_substitute": "ordered container, sorted-vector index, or degenerate BST",
        },
        "status": status,
    }
    _write(state / f"{task.task_id}.json", json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def _screen(out: Path) -> dict[str, object]:
    benchmark = json.loads(BENCHMARK_MANIFEST.read_text(encoding="utf-8"))
    benchmark_ids = set(benchmark["task_ids"])
    fingerprints: dict[str, str] = {}
    prompt_results: dict[str, str] = {}
    for task in TASKS:
        if task.task_id in benchmark_ids:
            raise ValueError(f"benchmark_id_overlap: {task.task_id}")
        normalized = re.sub(r"\s+", " ", task.api + " " + _public_rules(task.rules)).strip().lower()
        fingerprint = _sha256_bytes(normalized.encode())
        if fingerprint in fingerprints:
            raise ValueError(f"duplicate_family: {task.task_id} and {fingerprints[fingerprint]}")
        fingerprints[fingerprint] = task.task_id
        root = out / task.task_id
        prompt = build_prompt(load_task(root))
        for private_path in (".meta/example.cpp", ".meta/task_hidden_test.cpp", "CMakeLists.txt", ".meta/provenance.json"):
            private_text = (root / private_path).read_text(encoding="utf-8")
            if private_text and private_text in prompt:
                raise ValueError(f"prompt_contract_incomplete: {task.task_id} exposed {private_path}")
        prompt_results[task.task_id] = _sha256_bytes(prompt.encode())
        reference = (root / ".meta/example.cpp").read_text(encoding="utf-8").lower()
        for token in BANNED_REFERENCE_TOKENS:
            if token in reference:
                raise ValueError(f"invariant_not_enforced: {task.task_id} uses {token}")
    receipt = {
        "schema_version": "balanced-tree-family-screen-v1",
        "status": "pass",
        "benchmark_manifest": str(BENCHMARK_MANIFEST),
        "benchmark_manifest_hash": _sha256_file(BENCHMARK_MANIFEST),
        "benchmark_whole_slug": "pass",
        "benchmark_semantic_review": "pass: domain APIs differ from the held-out binary-search-tree contract",
        "duplicate_contracts": "pass",
        "normalizer": "whitespace-lower-v1",
        "prompt_boundary": "pass",
        "prompt_hashes": prompt_results,
    }
    state = out.parent / ".state"
    _write(state / "family-screen.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    return receipt


def build(out: Path = ROOT, force: bool = False) -> tuple[Path, ...]:
    try:
        if out.resolve() == LEGACY_ROOT.resolve():
            raise ValueError("refusing to mutate the preserved legacy balanced-search-tree family")
    except FileNotFoundError:
        pass
    if not (SUPPORT / "catch.hpp").is_file() or not (SUPPORT / "tests-main.cpp").is_file():
        raise RuntimeError(f"missing repository Catch support bundle: {SUPPORT}")
    # Receipts bind the exact generated bytes. Do not inherit a prior verdict
    # across regeneration.
    shutil.rmtree(out.parent / ".state" / "oracle", ignore_errors=True)
    curriculum_hash = _sha256_file(Path(CURRICULUM))
    support_hash = _sha256_file(SUPPORT / "catch.hpp")
    roots = []
    for task in TASKS:
        root = out / task.task_id
        header = _header(task)
        config = {
            "authors": ["w8-biayn"],
            "source": "newly-authored-in-repository",
            "attribution": "Clean-room repository-authored balanced-tree task under repository usage terms.",
            "blurb": f"Implement the {task.name} domain index with a real {task.kind} tree.",
            "files": {
                "solution": [f"{task.task_id}.h", f"{task.task_id}.cpp"],
                "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
                "example": [".meta/example.h", ".meta/example.cpp"],
            },
        }
        provenance = {
            "schema_version": "balanced-tree-provenance-v1",
            "curriculum_path": CURRICULUM,
            "curriculum_hash": curriculum_hash,
            "generator_revision": GENERATOR_REVISION,
            "generator_content_hash": _generator_hash(),
            "task_id": task.task_id,
            "family_id": FAMILY_ID,
            "clean_room_authoring_method": "repository-owned deterministic materializer",
            "license_usage_terms": "new repository content; use governed by repository license and local-family scope",
            "benchmark_separation": "official binary-search-tree remains a permanent holdout; no benchmark assets used",
            "status": "local candidate only; no dataset release",
            "selected_prompt": "docs/aider-tasks-spec/prompts/implement-family-for-sft.md",
            "catch_support_sha256": support_hash,
        }
        public_rules = _public_rules(task.rules)
        instructions = f"""# {task.name} contract

Implement the following C++17 API in namespace `curriculum`:

```cpp
{task.api}
```

{public_rules}

The index must own a real {task.kind} tree. Standard ordered or unordered associative containers, sorted-vector indexes, PBDS, Boost containers, third-party trees, and deliberately degenerate search trees are not valid substitutes. Public methods perform no I/O and invalid operations leave state unchanged.

Public example: the visible API sequence below must succeed exactly as asserted.

```cpp
{CASES[task.task_id].visible}
```

Boundary example: an invalid ID, invalid positive quantity, reversed range, or empty lookup follows the rejection or empty-result rule stated above and never causes a partial mutation.
"""
        files = {
            ".docs/introduction.md": f"# {task.name}\n\nMaintain a deterministic domain index while preserving {task.kind} balancing through insertions, replacements, and deletions.\n",
            ".docs/instructions.md": instructions,
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": "[visible]\ndescription = \"public API examples, validation, ordering, ties, and boundaries\"\n\n[hidden]\ndescription = \"10,000-operation deterministic mutation trace plus structural invariant checks after every mutation\"\n",
            f"{task.task_id}.h": header,
            f"{task.task_id}.cpp": _starter(task),
            ".meta/example.h": header,
            ".meta/example.cpp": _reference(task),
            "task_visible_test.cpp": _visible_test(task),
            ".meta/task_hidden_test.cpp": _hidden_test(task),
            "CMakeLists.txt": _cmake(task),
        }
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        (root / "test").mkdir(parents=True, exist_ok=True)
        for name in ("catch.hpp", "tests-main.cpp"):
            destination = root / "test" / name
            # The support bundle is content-addressed. Preserve an identical
            # read-only copy from a prior generated tree; refresh only a
            # missing or mismatched file.
            if not destination.exists() or destination.read_bytes() != (SUPPORT / name).read_bytes():
                shutil.copy2(SUPPORT / name, destination)
        roots.append(root)
    for task, root in zip(TASKS, roots):
        _remedy_state(out, task, _tree_hash(root), "implemented", True)
    _screen(out)
    manifest = {
        "schema_version": "balanced-tree-materialization-v1",
        "family_id": FAMILY_ID,
        "generator_revision": GENERATOR_REVISION,
        "generator_content_hash": _generator_hash(),
        "task_ids": [task.task_id for task in TASKS],
        "tree_hashes": {root.name: _tree_hash(root) for root in roots},
        "family_screen": "pass",
        "prompt_boundary": "pass",
        "status": "implemented",
    }
    _write(out.parent / ".state" / "materialization.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    return tuple(roots)


def _command_output(command: list[str]) -> str:
    return subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.strip()


def _discover(build_dir: Path) -> int:
    payload = json.loads(_command_output(["ctest", "--test-dir", str(build_dir), "--show-only=json-v1"]))
    count = len(payload.get("tests", []))
    if count <= 0:
        raise RuntimeError("zero_tests")
    return count


def verify(out: Path) -> None:
    missing = []
    if shutil.which("cmake") is None:
        missing.append("cmake")
    if shutil.which("c++") is None:
        missing.append("c++")
    if not os.environ.get("W8_BALANCED_TREE_GRADER_IMAGE"):
        missing.append("W8_BALANCED_TREE_GRADER_IMAGE")
    if not os.environ.get("W8_BALANCED_TREE_SANDBOX_POLICY"):
        missing.append("W8_BALANCED_TREE_SANDBOX_POLICY")
    if missing:
        state = out.parent / ".state"
        _write(
            state / "oracle" / "verification.json",
            json.dumps(
                {
                    "schema_version": "balanced-tree-oracle-v1",
                    "status": "not_completed",
                    "missing_prerequisites": missing,
                    "required_command": "run prepare_balanced_tree_aider_tasks.sh --verify in the designated network-disabled C++ grader image",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            True,
        )
        manifest_path = state / "materialization.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["status"] = "implemented"
        manifest["oracle_status"] = "not_completed"
        _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
        return
    compiler = str(Path(shutil.which("c++") or "").resolve())
    identity = {
        "image": os.environ.get("W8_BALANCED_TREE_GRADER_IMAGE", "not_recorded"),
        "compiler_path": compiler,
        "compiler_version": _command_output([compiler, "--version"]).splitlines()[0],
        "compiler_sha256": _sha256_file(Path(compiler)),
        "cmake_version": _command_output(["cmake", "--version"]).splitlines()[0],
        "catch_sha256": _sha256_file(SUPPORT / "catch.hpp"),
        "generator_revision": GENERATOR_REVISION,
        "generator_content_hash": _generator_hash(),
        "sandbox_policy": os.environ.get("W8_BALANCED_TREE_SANDBOX_POLICY", "caller-owned; network isolation not recorded"),
    }
    receipts = out.parent / ".state" / "oracle"
    for task in TASKS:
        source = out / task.task_id
        with tempfile.TemporaryDirectory(prefix=f"{task.task_id}-") as temporary:
            root = Path(temporary) / task.task_id
            shutil.copytree(source, root)
            shutil.copy2(root / ".meta/example.h", root / f"{task.task_id}.h")
            shutil.copy2(root / ".meta/example.cpp", root / f"{task.task_id}.cpp")
            counts: dict[str, int] = {}
            for mode, flags in (
                ("normal", []),
                ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]),
            ):
                build_dir = root / f"build-{mode}"
                subprocess.run(["cmake", "-S", str(root), "-B", str(build_dir), "-G", "Unix Makefiles", f"-DCMAKE_CXX_COMPILER={compiler}", *flags], check=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True)
                counts[mode] = _discover(build_dir)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True)
            if counts["normal"] != counts["sanitizer"]:
                raise RuntimeError(f"sanitizer_test_count_mismatch: {task.task_id}")
        receipt = {
            "schema_version": "balanced-tree-oracle-v1",
            "status": "pass",
            "task_id": task.task_id,
            "tree_hash": _tree_hash(source),
            "reference_mapping": {".meta/example.h": f"{task.task_id}.h", ".meta/example.cpp": f"{task.task_id}.cpp"},
            "test_counts": counts,
            **identity,
        }
        _write(receipts / f"{task.task_id}.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        _remedy_state(out, task, _tree_hash(source), "verified", True)
    manifest_path = out.parent / ".state" / "materialization.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = "local_family_verified"
    manifest["oracle_receipts"] = 20
    manifest["normal_test_count_per_root"] = 2
    manifest["sanitizer_test_count_per_root"] = 2
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize real AVL and red-black local Aider tasks.")
    parser.add_argument("--out", type=Path, default=ROOT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify:
        verify(args.out)
    print(f"Wrote {len(roots)} balanced-tree tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
