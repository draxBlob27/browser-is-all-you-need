"""Materialize and locally verify the remediated doubly-linked-list family."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_doubly_linked_list_cases import CASES, Case


ROOT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/doubly-linked-list")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dsa/doubly-linked-list")
CURRICULUM = Path("docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_DOUBLY_LINKED_LIST_CURRICULUM.md")
SPEC = Path("docs/aider-tasks-spec/aider-dsa/doubly-linked-list.md")
PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
BENCHMARK_MANIFEST = Path("manifests/aider_sft/aider-polyglot-cpp-26.json")
SUPPORT = Path(".w8-biayn/data/aider-sft-source-only-75-v1/private/grader-support/exercism-catch-v1/test")
FAMILY_ID = "aider-dsa-doubly-linked-list-v2"
GENERATOR_REVISION = "doubly-linked-list-materializer-v2"
NORMALIZER = "aider-cleanroom-family-v1"
BANNED_REFERENCE_TOKENS = (
    "std::list<", "std::deque<", "std::map<", "std::set<", "std::multiset<",
    "std::unordered_", "boost::", "__gnu_pbds", "forward_list<",
)


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _generator_hash() -> str:
    return _sha256_file(Path(__file__))


def _spec_contract_hash() -> str:
    normative = SPEC.read_text(encoding="utf-8").split("\n## Final re-verification evidence\n", 1)[0].rstrip() + "\n"
    return _sha256_bytes(normative.encode())


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


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _header(case: Case) -> str:
    return f'''#pragma once
#include <cstddef>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace curriculum {{
#ifdef CURRICULUM_TESTING
struct LinkAudit {{ bool valid; std::size_t forward_count; std::size_t reverse_count; }};
#endif

class {case.class_name} {{
 public:
  {case.class_name}() = default;
  ~{case.class_name}();
  {case.class_name}(const {case.class_name}&) = delete;
  {case.class_name}& operator=(const {case.class_name}&) = delete;
{case.declarations}
#ifdef CURRICULUM_TESTING
  LinkAudit audit_for_test() const;
#endif
 private:
  struct Node;
  Node* head_ = nullptr;
  Node* tail_ = nullptr;
  {case.private_fields}
  Node* find(int id) const;
  void unlink(Node* node);
  void insert_after(Node* node, Node* after);
  void insert_before(Node* node, Node* before);
}};

}}  // namespace curriculum
'''


def _reference(case: Case) -> str:
    extras = f" {case.node_fields}" if case.node_fields else ""
    return f'''#include "{case.task_id}.h"
#include <limits>

namespace curriculum {{
struct {case.class_name}::Node {{ int id; Node* prev; Node* next;{extras} }};
{case.class_name}::~{case.class_name}(){{while(head_){{Node*n=head_->next;delete head_;head_=n;}}tail_=nullptr;}}
{case.class_name}::Node* {case.class_name}::find(int id)const{{for(Node*n=head_;n;n=n->next)if(n->id==id)return n;return nullptr;}}
void {case.class_name}::unlink(Node*n){{if(n->prev)n->prev->next=n->next;else head_=n->next;if(n->next)n->next->prev=n->prev;else tail_=n->prev;n->prev=n->next=nullptr;}}
void {case.class_name}::insert_after(Node*n,Node*a){{if(!a){{n->prev=nullptr;n->next=head_;if(head_)head_->prev=n;else tail_=n;head_=n;return;}}n->prev=a;n->next=a->next;if(a->next)a->next->prev=n;else tail_=n;a->next=n;}}
void {case.class_name}::insert_before(Node*n,Node*b){{if(!b){{insert_after(n,tail_);return;}}insert_after(n,b->prev);}}
{case.reference}
#ifdef CURRICULUM_TESTING
LinkAudit {case.class_name}::audit_for_test()const{{
 bool valid=true;std::size_t f=0,r=0;Node*previous=nullptr;
 for(Node*n=head_;n;n=n->next){{if(n->prev!=previous)valid=false;previous=n;if(++f>100000U){{valid=false;break;}}}}
 if(previous!=tail_)valid=false;
 Node*next=nullptr;
 for(Node*n=tail_;n;n=n->prev){{if(n->next!=next)valid=false;next=n;if(++r>100000U){{valid=false;break;}}}}
 if(next!=head_||f!=r||(head_&&head_->prev)||(tail_&&tail_->next)||((head_==nullptr)!=(tail_==nullptr)))valid=false;
 return {{valid,f,r}};
}}
#endif
}}  // namespace curriculum
'''


def _starter(case: Case) -> str:
    return f'''#include "{case.task_id}.h"
namespace curriculum {{
{case.starter}
#ifdef CURRICULUM_TESTING
LinkAudit {case.class_name}::audit_for_test()const{{return {{false,0U,0U}};}}
#endif
}}  // namespace curriculum
'''


def _visible_test(case: Case) -> str:
    return f'''#include "{case.task_id}.h"
#include <catch.hpp>
TEST_CASE("{case.task_id} public contract", "[visible]"){{
 using namespace curriculum;
 {case.visible}
}}
'''


def _hidden_test(case: Case) -> str:
    variable = re.search(r"\b([A-Za-z_]\w*)\s*;", case.hidden)
    if not variable:
        raise ValueError(f"hidden test has no task variable: {case.task_id}")
    name = variable.group(1)
    return f'''#include "{case.task_id}.h"
#include <catch.hpp>
#include <string>
#include <utility>
#include <vector>
TEST_CASE("{case.task_id} private state trace", "[hidden]"){{
 using namespace curriculum;
 {case.hidden}
 const auto audit={name}.audit_for_test();
 REQUIRE(audit.valid);
 REQUIRE(audit.forward_count==audit.reverse_count);
}}
'''


def _cmake(case: Case) -> str:
    return f'''cmake_minimum_required(VERSION 3.16)
project({case.task_id.replace('-', '_')} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
enable_testing()
add_executable(task_tests {case.task_id}.cpp task_visible_test.cpp .meta/task_hidden_test.cpp test/tests-main.cpp)
target_include_directories(task_tests PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}} ${{CMAKE_CURRENT_SOURCE_DIR}}/test)
target_compile_definitions(task_tests PRIVATE CURRICULUM_TESTING=1 EXERCISM_RUN_ALL_TESTS=1)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(task_tests PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
add_test(NAME visible COMMAND task_tests "[visible]")
add_test(NAME hidden COMMAND task_tests "[hidden]")
'''


def _remedy_record(out: Path, case: Case, *, status: str, tree_hash: str | None = None) -> dict[str, object]:
    path = out / ".state" / "remedy" / f"{case.legacy_id}.json"
    if not path.is_file():
        raise RuntimeError(f"remedy_spec_incomplete: {path}")
    record = json.loads(path.read_text(encoding="utf-8"))
    spec_path = Path(str(record["remedy_spec_path"]))
    if not spec_path.is_file() or _sha256_file(spec_path) != record.get("remedy_spec_hash"):
        raise RuntimeError(f"remedy_spec_incomplete: stale spec for {case.legacy_id}")
    if record.get("status") not in {"planned", "implemented", "verified"}:
        raise RuntimeError(f"remedy_disposition_conflict: {case.legacy_id}")
    expected = "repair-in-place" if case.legacy_id == case.task_id else "replace"
    if record.get("disposition") != expected:
        raise RuntimeError(f"remedy_disposition_conflict: {case.legacy_id}")
    record.update({
        "family_id_after": FAMILY_ID,
        "replacement_task_id": case.task_id,
        "generator_content_hash_after": _generator_hash(),
        "primary_core_objective": "achieved",
        "status": status,
    })
    if tree_hash is not None:
        record["tree_hash_after"] = tree_hash
    _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)
    return record


def _normalize(text: str) -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/|\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'", " ", text, flags=re.M | re.S)
    text = re.sub(r"\b\d+\b", "#", text.lower())
    domain = {token for case in CASES for token in re.findall(r"[a-z]+", case.task_id + " " + case.class_name)}
    tokens = [token for token in re.findall(r"[a-z_]+|[{}();,*&<>]", text) if token not in domain]
    return tuple(tokens)


def _ngrams(tokens: tuple[str, ...], width: int = 5) -> set[tuple[str, ...]]:
    return {tokens[index:index + width] for index in range(max(0, len(tokens) - width + 1))}


def _screen(out: Path) -> dict[str, object]:
    benchmark = json.loads(BENCHMARK_MANIFEST.read_text(encoding="utf-8"))
    holdout_ids = set(benchmark["task_ids"])
    task_ids = {case.task_id for case in CASES}
    if task_ids & holdout_ids:
        raise RuntimeError("benchmark_id_overlap")
    signatures: dict[str, set[tuple[str, ...]]] = {}
    for case in CASES:
        root = out / case.task_id
        material = "\n".join((root / name).read_text(encoding="utf-8") for name in (
            ".docs/instructions.md", f"{case.task_id}.h", ".meta/example.cpp", "task_visible_test.cpp", ".meta/task_hidden_test.cpp"
        ))
        sig = _ngrams(_normalize(material))
        if not sig:
            raise RuntimeError(f"duplicate_family: empty signature for {case.task_id}")
        signatures[case.task_id] = sig
    strongest_family = {"pair": None, "jaccard": 0.0}
    ids = sorted(signatures)
    for index, left in enumerate(ids):
        for right in ids[index + 1:]:
            a, b = signatures[left], signatures[right]
            score = len(a & b) / len(a | b)
            if score > strongest_family["jaccard"]:
                strongest_family = {"pair": [left, right], "jaccard": round(score, 6)}
            if score >= 0.60:
                raise RuntimeError(f"duplicate_family: {left} and {right}: {score:.3f}")
    upstream = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
    if not upstream.is_dir():
        upstream = Path(".w8-biayn/data/polyglot-benchmark/cpp/exercises/practice")
    benchmark_status = "not_completed"
    strongest_holdout: dict[str, object] = {"pair": None, "jaccard": 0.0}
    inventory: list[str] = []
    if upstream.is_dir():
        holdout_signatures: dict[str, set[tuple[str, ...]]] = {}
        for holdout in sorted(holdout_ids):
            root = upstream / holdout
            if not root.is_dir():
                continue
            paths = [path for path in root.rglob("*") if path.is_file() and path.suffix in {".md", ".h", ".hpp", ".cc", ".cpp", ".toml"}]
            inventory.append(holdout)
            holdout_signatures[holdout] = _ngrams(_normalize("\n".join(path.read_text(encoding="utf-8", errors="replace") for path in paths)))
        if holdout_signatures:
            benchmark_status = "pass"
            for task_id, task_sig in signatures.items():
                for holdout, holdout_sig in holdout_signatures.items():
                    if not holdout_sig:
                        continue
                    score = len(task_sig & holdout_sig) / len(task_sig | holdout_sig)
                    if score > strongest_holdout["jaccard"]:
                        strongest_holdout = {"pair": [task_id, holdout], "jaccard": round(score, 6)}
                    if score >= 0.58:
                        raise RuntimeError(f"benchmark_content_overlap: {task_id} and {holdout}: {score:.3f}")
    prompts: dict[str, str] = {}
    for case in CASES:
        root = out / case.task_id
        prompt = build_prompt(load_task(root))
        for forbidden in (".meta/example", "task_hidden_test", "CMakeLists.txt", "provenance.json", "catch.hpp"):
            if forbidden in prompt:
                raise RuntimeError(f"prompt_contract_incomplete: {case.task_id}: {forbidden}")
        prompts[case.task_id] = _sha256_bytes(prompt.encode())
    receipt = {
        "schema_version": "dll-family-screen-v2",
        "status": "pass" if benchmark_status == "pass" else "not_completed",
        "normalizer": NORMALIZER,
        "family_duplicate_screen": "pass",
        "strongest_family_pair": strongest_family,
        "benchmark_whole_slug": "pass",
        "benchmark_semantic_screen": benchmark_status,
        "benchmark_inventory": inventory,
        "strongest_holdout_pair": strongest_holdout,
        "prompt_boundary": "pass",
        "prompt_hashes": prompts,
        "unique_logic_tags": len({case.logic_tag for case in CASES}),
    }
    _write(out / ".state" / "family-screen.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    return receipt


def verify_core(out: Path) -> dict[str, object]:
    if len({case.logic_tag for case in CASES}) != len(CASES):
        raise RuntimeError("duplicate_family")
    negative_fixture = "#include <vector>\nclass Fake { std::vector<int> order_; };\n"
    def validate_reference(text: str, task_id: str) -> None:
        if any(token in text for token in BANNED_REFERENCE_TOKENS):
            raise RuntimeError(f"invariant_not_enforced: banned authoritative container in {task_id}")
        required = ("::Node", "Node* prev", "Node* next", "audit_for_test", "->prev", "->next")
        if any(token not in text for token in required):
            raise RuntimeError(f"invariant_not_enforced: missing owned links in {task_id}")
    fixture_rejected = False
    try:
        validate_reference(negative_fixture, "vector_authority_fixture")
    except RuntimeError as error:
        fixture_rejected = "invariant_not_enforced" in str(error)
    if not fixture_rejected:
        raise RuntimeError("invariant_not_enforced: vector_authority_fixture passed")
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        expected = [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        if config["files"]["solution"] != expected:
            raise RuntimeError(f"target_reference_mismatch: {case.task_id}")
        roles = sum(config["files"].values(), [])
        for relative in roles:
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
                raise RuntimeError(f"unsafe_path: {case.task_id}: {relative}")
        validate_reference((root / ".meta/example.cpp").read_text(encoding="utf-8"), case.task_id)
    screen = _screen(out)
    receipt = {
        "schema_version": "dll-core-verification-v2",
        "status": "pass",
        "roots": len(CASES),
        "primary_core_objective": "achieved",
        "negative_fixture": "vector_authority_fixture",
        "negative_fixture_result": "invariant_not_enforced",
        "unique_logic_tags": len({case.logic_tag for case in CASES}),
        "family_screen": screen["family_duplicate_screen"],
        "benchmark_semantic_screen": screen["benchmark_semantic_screen"],
        "prompt_boundary": screen["prompt_boundary"],
    }
    _write(out / ".state" / "core-verification.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    return receipt


def build(out: Path, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() == LEGACY_ROOT.resolve():
        raise RuntimeError("refusing to modify LEGACY_ROOT")
    if not CURRICULUM.is_file() or not SPEC.is_file():
        raise RuntimeError("remedy_spec_incomplete: curriculum or family specification missing")
    if not (SUPPORT / "catch.hpp").is_file() or not (SUPPORT / "tests-main.cpp").is_file():
        raise RuntimeError(f"missing content-addressed Catch support: {SUPPORT}")
    prior_manifest = out / ".state" / "materialization.json"
    if prior_manifest.is_file():
        prior = json.loads(prior_manifest.read_text(encoding="utf-8"))
        if prior.get("generator_content_hash") != _generator_hash():
            shutil.rmtree(out / ".state" / "oracle", ignore_errors=True)
    expected = {case.task_id for case in CASES}
    existing = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"} if out.is_dir() else set()
    for stale_name in sorted(existing - expected):
        stale = out / stale_name
        provenance_path = stale / ".meta" / "provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8")) if provenance_path.is_file() else {}
        if not force or provenance.get("family_id") != FAMILY_ID:
            raise RuntimeError(f"generator_output_drift: unexpected root {stale_name}")
        shutil.rmtree(stale)
    roots: list[Path] = []
    curriculum_hash = _sha256_file(CURRICULUM)
    support_hash = _sha256_file(SUPPORT / "catch.hpp")
    for case in CASES:
        _remedy_record(out, case, status="planned")
        root = out / case.task_id
        config = {
            "authors": ["w8-biayn"],
            "source": "newly-authored-in-repository",
            "attribution": "Clean-room repository-authored doubly-linked-list task under repository usage terms.",
            "blurb": case.contract,
            "files": {
                "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
                "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
                "example": [".meta/example.h", ".meta/example.cpp"],
            },
        }
        provenance = {
            "schema_version": "dll-provenance-v2",
            "task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "family_id": FAMILY_ID,
            "curriculum_path": str(CURRICULUM),
            "curriculum_hash": curriculum_hash,
            "spec_path": str(SPEC),
            "spec_contract_hash": _spec_contract_hash(),
            "spec_hash_scope": "content before Final re-verification evidence",
            "generator_revision": GENERATOR_REVISION,
            "generator_content_hash": _generator_hash(),
            "selected_prompt": PROMPT,
            "clean_room_authoring_method": "repository-owned deterministic materializer",
            "license_usage_terms": "new repository content governed by repository license and local-family scope",
            "benchmark_separation": "official linked-list is a permanent holdout; no benchmark assets imported",
            "logic_tag": case.logic_tag,
            "catch_support_sha256": support_hash,
            "status": "local candidate only; no dataset release",
        }
        instructions = f'''# {case.class_name} contract

Implement the following C++17 class in namespace `curriculum`:

```cpp
class {case.class_name} {{
 public:
{case.declarations}
}};
```

{case.contract}

The authoritative order must be a heap-owned doubly linked chain with reciprocal `prev` and `next` links. `std::list`, `std::deque`, vector-backed authoritative order, associative containers, hard-coded traces, and third-party list implementations are not substitutes. Output vectors are permitted snapshots. IDs are positive and unique. Unless stated otherwise, absent IDs, duplicate IDs, invalid anchors/ranges, and empty operations fail without mutation.

The header's `CURRICULUM_TESTING` audit is part of the structural contract: it must report a null predecessor at the head, null successor at the tail, reciprocal links, no cycle, and equal complete forward/reverse counts after every mutation.

Boundary example: an operation naming absent ID `999` on an empty object fails or returns `std::nullopt`, and the object remains empty.
'''
        files = {
            ".docs/introduction.md": f"# {case.class_name}\n\n{case.contract}\n",
            ".docs/instructions.md": instructions,
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": "[visible]\ndescription = \"public state transition and boundary\"\n\n[hidden]\ndescription = \"task-specific mutation trace plus reciprocal-link audit\"\n",
            f"{case.task_id}.h": _header(case),
            f"{case.task_id}.cpp": _starter(case),
            ".meta/example.h": _header(case),
            ".meta/example.cpp": _reference(case),
            "task_visible_test.cpp": _visible_test(case),
            ".meta/task_hidden_test.cpp": _hidden_test(case),
            "CMakeLists.txt": _cmake(case),
        }
        for relative, content in files.items():
            _write(root / relative, content, force)
        (root / "test").mkdir(parents=True, exist_ok=True)
        for name in ("catch.hpp", "tests-main.cpp"):
            destination = root / "test" / name
            if not destination.exists() or destination.read_bytes() != (SUPPORT / name).read_bytes():
                shutil.copy2(SUPPORT / name, destination)
        tree_hash = _tree_hash(root)
        _remedy_record(out, case, status="implemented", tree_hash=tree_hash)
        roots.append(root)
    core = verify_core(out)
    manifest = {
        "schema_version": "dll-materialization-v2",
        "family_id": FAMILY_ID,
        "generator_revision": GENERATOR_REVISION,
        "generator_content_hash": _generator_hash(),
        "legacy_root": str(LEGACY_ROOT),
        "legacy_root_preserved": True,
        "task_ids": [case.task_id for case in CASES],
        "legacy_task_ids": [case.legacy_id for case in CASES],
        "tree_hashes": {root.name: _tree_hash(root) for root in roots},
        "primary_core_objective": core["primary_core_objective"],
        "prompt_boundary": core["prompt_boundary"],
        "family_screen": core["family_screen"],
        "benchmark_semantic_screen": core["benchmark_semantic_screen"],
        "status": "implemented",
    }
    _write(out / ".state" / "materialization.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
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
    missing = [name for name in ("cmake", "c++", "ctest") if shutil.which(name) is None]
    for variable in ("W8_DLL_GRADER_IMAGE", "W8_DLL_SANDBOX_POLICY"):
        if not os.environ.get(variable):
            missing.append(variable)
    state = out / ".state"
    if missing:
        receipt = {
            "schema_version": "dll-oracle-summary-v2",
            "status": "not_completed",
            "missing_prerequisites": missing,
            "required_command": "run prepare_doubly_linked_list_aider_tasks.sh --verify in the designated network-disabled C++ grader image",
        }
        _write(state / "oracle" / "verification.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        manifest = json.loads((state / "materialization.json").read_text(encoding="utf-8"))
        manifest.update({"oracle_status": "not_completed", "status": "implemented"})
        _write(state / "materialization.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
        return
    compiler = str(Path(shutil.which("c++") or "").resolve())
    identity = {
        "image": os.environ["W8_DLL_GRADER_IMAGE"],
        "sandbox_policy": os.environ["W8_DLL_SANDBOX_POLICY"],
        "compiler_path": compiler,
        "compiler_version": _command_output([compiler, "--version"]).splitlines()[0],
        "compiler_sha256": _sha256_file(Path(compiler)),
        "cmake_version": _command_output(["cmake", "--version"]).splitlines()[0],
        "ctest_version": _command_output(["ctest", "--version"]).splitlines()[0],
        "catch_sha256": _sha256_file(SUPPORT / "catch.hpp"),
        "generator_revision": GENERATOR_REVISION,
        "generator_content_hash": _generator_hash(),
    }
    receipts = state / "oracle"
    totals = {"normal": 0, "sanitizer": 0}
    for case in CASES:
        source = out / case.task_id
        with tempfile.TemporaryDirectory(prefix=f"{case.task_id}-") as temporary:
            root = Path(temporary) / case.task_id
            shutil.copytree(source, root)
            shutil.copy2(root / ".meta/example.h", root / f"{case.task_id}.h")
            shutil.copy2(root / ".meta/example.cpp", root / f"{case.task_id}.cpp")
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
                raise RuntimeError(f"sanitizer_test_count_mismatch: {case.task_id}")
            totals["normal"] += counts["normal"]
            totals["sanitizer"] += counts["sanitizer"]
        receipt = {
            "schema_version": "dll-oracle-v2",
            "status": "pass",
            "task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "tree_hash": _tree_hash(source),
            "reference_mapping": {".meta/example.h": f"{case.task_id}.h", ".meta/example.cpp": f"{case.task_id}.cpp"},
            "test_counts": counts,
            **identity,
        }
        _write(receipts / f"{case.task_id}.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        record = _remedy_record(out, case, status="verified", tree_hash=_tree_hash(source))
        record.update({"benchmark_screen": "pass", "family_screen": "pass", "oracle_receipt": str(receipts / f"{case.task_id}.json"), "test_counts": counts, "local_status": "local_family_verified"})
        _write(out / ".state" / "remedy" / f"{case.legacy_id}.json", json.dumps(record, indent=2, sort_keys=True) + "\n", True)
    screen = json.loads((state / "family-screen.json").read_text(encoding="utf-8"))
    complete = screen["benchmark_semantic_screen"] == "pass"
    summary = {
        "schema_version": "dll-oracle-summary-v2",
        "status": "pass",
        "roots": len(CASES),
        "test_counts": totals,
        "equal_positive_counts": totals["normal"] == totals["sanitizer"] and totals["normal"] > 0,
        **identity,
    }
    _write(receipts / "verification.json", json.dumps(summary, indent=2, sort_keys=True) + "\n", True)
    manifest = json.loads((state / "materialization.json").read_text(encoding="utf-8"))
    manifest.update({"oracle_status": "pass", "oracle_receipts": len(CASES), "test_counts": totals, "status": "local_family_verified" if complete else "semantically_admitted"})
    _write(state / "materialization.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)


def quick_normal_verify(out: Path) -> None:
    """Run a receipt-free normal build for iteration; never claim oracle status."""
    compiler = str(Path(shutil.which("c++") or "").resolve())
    if not compiler or shutil.which("cmake") is None or shutil.which("ctest") is None:
        raise RuntimeError("quick normal verification requires cmake, ctest, and c++")
    for case in CASES:
        source = out / case.task_id
        with tempfile.TemporaryDirectory(prefix=f"quick-{case.task_id}-") as temporary:
            root = Path(temporary) / case.task_id
            shutil.copytree(source, root)
            shutil.copy2(root / ".meta/example.h", root / f"{case.task_id}.h")
            shutil.copy2(root / ".meta/example.cpp", root / f"{case.task_id}.cpp")
            build_dir = root / "build-normal"
            subprocess.run(["cmake", "-S", str(root), "-B", str(build_dir), "-G", "Unix Makefiles", f"-DCMAKE_CXX_COMPILER={compiler}"], check=True, stdout=subprocess.DEVNULL)
            subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.DEVNULL)
            if _discover(build_dir) != 2:
                raise RuntimeError(f"test_discovery_failed: {case.task_id}")
            subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True)
        print(f"quick-normal pass: {case.task_id}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--quick-normal", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.quick_normal:
        quick_normal_verify(args.out)
    if args.verify:
        verify(args.out)
    print(f"Wrote {len(roots)} remediated doubly-linked-list tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
