"""Materialize and locally verify the remediated threaded-tree family."""

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
from w8_biayn.integrations.moonlight_threaded_binary_tree_cases import (
    CASES,
    NEGATIVE_MUTATIONS,
    Case,
)


ROOT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/threaded-binary-tree")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dsa/threaded-binary-tree")
CURRICULUM = Path("docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_THREADED_BINARY_TREE_CURRICULUM.md")
SPEC = Path("docs/aider-tasks-spec/aider-dsa/threaded-binary-tree.md")
PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
BENCHMARK_MANIFEST = Path("manifests/aider_sft/aider-polyglot-cpp-26.json")
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
SUPPORT = Path(".w8-biayn/data/aider-sft-source-only-75-v1/private/grader-support/exercism-catch-v1/test")
FAMILY_ID = "aider-dsa-threaded-binary-tree-v3-hard-rule"
GENERATOR_REVISION = "threaded-binary-tree-materializer-v3-hard-rule"
NORMALIZER = "aider-threaded-tree-artifact-semantics-v3"
IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
PAIR_THRESHOLD = 0.98
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
)
BANNED_REFERENCE_TOKENS = (
    "std::set<", "std::map<", "std::multiset<", "std::unordered_", "std::list<",
    "std::deque<", "std::priority_queue<", "boost::", "__gnu_pbds",
)


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _generator_hash() -> str:
    paths = (Path(__file__), Path(__file__).with_name("moonlight_threaded_binary_tree_cases.py"))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _spec_contract_hash() -> str:
    normative = SPEC.read_text(encoding="utf-8").split("\n## Final re-verification evidence\n", 1)[0].rstrip() + "\n"
    return _sha256_bytes(normative.encode())


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _write(path: Path, content: str, force: bool = True) -> None:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    if path.exists() and not force:
        raise FileExistsError(f"{path} differs; pass --force only for the re-verification root")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(content, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _header(case: Case) -> str:
    guard = case.task_id.replace("-", "_").upper() + "_H"
    return f'''#ifndef {guard}
#define {guard}
#include <algorithm>
#include <cstddef>
#include <functional>
#include <limits>
#include <optional>
#include <tuple>
#include <utility>
#include <vector>

namespace curriculum {{
#ifdef CURRICULUM_TESTING
struct ThreadAudit {{ bool valid; std::size_t node_count; std::size_t forward_count; std::size_t reverse_count; }};
#endif
class {case.class_name} {{
 public:
  {case.class_name}() = default;
  ~{case.class_name}();
  {case.class_name}(const {case.class_name}&) = delete;
  {case.class_name}& operator=(const {case.class_name}&) = delete;
{case.declarations}
#ifdef CURRICULUM_TESTING
  ThreadAudit audit_for_test() const;
#endif
 private:
  struct Node {{
    long long order; int id; int value; int aux; std::size_t count; bool flag;
    Node* parent; Node* left; Node* right; bool left_thread; bool right_thread;
  }};
  Node* root_ = nullptr;
  {case.private_fields}
  Node* find_order(long long order) const;
  Node* find_id(int id) const;
  Node* lower_bound(long long order) const;
  Node* minimum() const;
  Node* maximum() const;
  Node* successor(Node* node) const;
  Node* predecessor(Node* node) const;
  bool insert_node(Node* node);
  void erase_node(Node* node);
  void clear_all();
  static void child_inorder(Node* node, std::vector<Node*>& out);
}};
}}  // namespace curriculum
#endif
'''


def _common_reference(case: Case) -> str:
    return f'''#include "{case.task_id}.h"

namespace curriculum {{
{case.class_name}::~{case.class_name}(){{clear_all();}}
void {case.class_name}::child_inorder(Node*n,std::vector<Node*>&out){{if(!n)return;if(!n->left_thread)child_inorder(n->left,out);out.push_back(n);if(!n->right_thread)child_inorder(n->right,out);}}
void {case.class_name}::clear_all(){{std::vector<Node*>nodes;child_inorder(root_,nodes);for(Node*n:nodes)delete n;root_=nullptr;}}
{case.class_name}::Node* {case.class_name}::minimum()const{{Node*n=root_;if(!n)return nullptr;while(!n->left_thread)n=n->left;return n;}}
{case.class_name}::Node* {case.class_name}::maximum()const{{Node*n=root_;if(!n)return nullptr;while(!n->right_thread)n=n->right;return n;}}
{case.class_name}::Node* {case.class_name}::successor(Node*n)const{{if(!n)return nullptr;if(n->right_thread)return n->right;n=n->right;while(n&&!n->left_thread)n=n->left;return n;}}
{case.class_name}::Node* {case.class_name}::predecessor(Node*n)const{{if(!n)return nullptr;if(n->left_thread)return n->left;n=n->left;while(n&&!n->right_thread)n=n->right;return n;}}
{case.class_name}::Node* {case.class_name}::find_order(long long k)const{{Node*n=root_;while(n){{if(k==n->order)return n;if(k<n->order){{if(n->left_thread)return nullptr;n=n->left;}}else{{if(n->right_thread)return nullptr;n=n->right;}}}}return nullptr;}}
{case.class_name}::Node* {case.class_name}::find_id(int id)const{{for(Node*n=minimum();n;n=successor(n))if(n->id==id)return n;return nullptr;}}
{case.class_name}::Node* {case.class_name}::lower_bound(long long k)const{{Node*n=root_,*best=nullptr;while(n){{if(n->order>=k){{best=n;if(n->left_thread)break;n=n->left;}}else{{if(n->right_thread)break;n=n->right;}}}}return best;}}
bool {case.class_name}::insert_node(Node*fresh){{if(!fresh)return false;fresh->parent=nullptr;fresh->left=fresh->right=nullptr;fresh->left_thread=fresh->right_thread=true;if(!root_){{root_=fresh;return true;}}Node*n=root_;while(true){{if(fresh->order==n->order){{delete fresh;return false;}}if(fresh->order<n->order){{if(n->left_thread){{Node*pred=n->left;fresh->parent=n;fresh->left=pred;fresh->right=n;n->left=fresh;n->left_thread=false;if(pred&&pred->right_thread&&pred->right==n)pred->right=fresh;return true;}}n=n->left;}}else{{if(n->right_thread){{Node*succ=n->right;fresh->parent=n;fresh->left=n;fresh->right=succ;n->right=fresh;n->right_thread=false;if(succ&&succ->left_thread&&succ->left==n)succ->left=fresh;return true;}}n=n->right;}}}}}}
void {case.class_name}::erase_node(Node*n){{if(!n)return;if(!n->left_thread&&!n->right_thread){{Node*s=successor(n);n->order=s->order;n->id=s->id;n->value=s->value;n->aux=s->aux;n->count=s->count;n->flag=s->flag;n=s;}}Node*pred=predecessor(n);Node*succ=successor(n);Node*child=nullptr;if(!n->left_thread)child=n->left;else if(!n->right_thread)child=n->right;if(child)child->parent=n->parent;if(!n->parent)root_=child;else if(!n->parent->left_thread&&n->parent->left==n){{n->parent->left=child?child:pred;n->parent->left_thread=child==nullptr;}}else{{n->parent->right=child?child:succ;n->parent->right_thread=child==nullptr;}}if(pred&&pred->right_thread&&pred->right==n)pred->right=succ;if(succ&&succ->left_thread&&succ->left==n)succ->left=pred;if(child){{if(child==n->left){{Node*r=child;while(!r->right_thread)r=r->right;r->right=succ;if(succ&&succ->left_thread)succ->left=r;}}else{{Node*l=child;while(!l->left_thread)l=l->left;l->left=pred;if(pred&&pred->right_thread)pred->right=l;}}}}delete n;}}
#ifdef CURRICULUM_TESTING
ThreadAudit {case.class_name}::audit_for_test()const{{std::vector<Node*>nodes;child_inorder(root_,nodes);bool ok=true;for(std::size_t i=0;i<nodes.size();++i){{Node*n=nodes[i];Node*pred=i?nodes[i-1]:nullptr;Node*succ=i+1<nodes.size()?nodes[i+1]:nullptr;if(i&&nodes[i-1]->order>=n->order)ok=false;if(n->left_thread)ok=ok&&n->left==pred;else ok=ok&&n->left&&n->left->parent==n&&n->left->order<n->order;if(n->right_thread)ok=ok&&n->right==succ;else ok=ok&&n->right&&n->right->parent==n&&n->right->order>n->order;}}std::size_t f=0,r=0;for(Node*n=minimum();n&&f<=nodes.size();n=successor(n))++f;for(Node*n=maximum();n&&r<=nodes.size();n=predecessor(n))++r;ok=ok&&f==nodes.size()&&r==nodes.size()&&(!root_||root_->parent==nullptr);return{{ok,nodes.size(),f,r}};}}
#endif
{case.reference}
}}  // namespace curriculum
'''


def _starter(case: Case) -> str:
    return f'''#include "{case.task_id}.h"
namespace curriculum {{
{case.class_name}::~{case.class_name}(){{clear_all();}}
void {case.class_name}::child_inorder(Node*,std::vector<Node*>&){{}}
void {case.class_name}::clear_all(){{root_=nullptr;}}
{case.class_name}::Node* {case.class_name}::find_order(long long)const{{return nullptr;}}
{case.class_name}::Node* {case.class_name}::find_id(int)const{{return nullptr;}}
{case.class_name}::Node* {case.class_name}::lower_bound(long long)const{{return nullptr;}}
{case.class_name}::Node* {case.class_name}::minimum()const{{return nullptr;}}
{case.class_name}::Node* {case.class_name}::maximum()const{{return nullptr;}}
{case.class_name}::Node* {case.class_name}::successor(Node*)const{{return nullptr;}}
{case.class_name}::Node* {case.class_name}::predecessor(Node*)const{{return nullptr;}}
bool {case.class_name}::insert_node(Node*){{return false;}}
void {case.class_name}::erase_node(Node*){{}}
#ifdef CURRICULUM_TESTING
ThreadAudit {case.class_name}::audit_for_test()const{{return{{false,0,0,0}};}}
#endif
{case.starter}
}}  // namespace curriculum
'''


def _test(case: Case, hidden: bool) -> str:
    body = case.hidden if hidden else case.visible
    return f'''#include "catch.hpp"
#include "{case.task_id}.h"

using namespace curriculum;
TEST_CASE("{case.logic_tag}"){{
{body}
}}
'''


def _cmake(case: Case) -> str:
    return f'''cmake_minimum_required(VERSION 3.16)
project({case.task_id.replace('-', '_')} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${{CMAKE_CURRENT_SOURCE_DIR}}/{case.task_id}.cpp" CACHE FILEPATH "solution source")
add_library(task_solution STATIC "${{TASK_SOURCE}}")
target_include_directories(task_solution PUBLIC "${{CMAKE_CURRENT_SOURCE_DIR}}")
target_compile_definitions(task_solution PUBLIC CURRICULUM_TESTING=1)
add_executable(task_visible test/tests-main.cpp task_visible_test.cpp)
add_executable(task_hidden test/tests-main.cpp .meta/task_hidden_test.cpp)
foreach(target task_solution task_visible task_hidden)
  target_include_directories(${{target}} PRIVATE "${{CMAKE_CURRENT_SOURCE_DIR}}" "${{CMAKE_CURRENT_SOURCE_DIR}}/test")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${{target}} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
target_link_libraries(task_visible PRIVATE task_solution)
target_link_libraries(task_hidden PRIVATE task_solution)
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
'''


def _normalize(text: str) -> set[str]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " string ", text)
    text = re.sub(r"\b\d+\b", " number ", text.lower())
    tokens = re.findall(r"[a-z_][a-z0-9_]*|==|!=|<=|>=|->|&&|\|\|", text)
    nouns = {part for case in CASES for part in re.split(r"[-_]", case.task_id)}
    tokens = [token for token in tokens if token not in nouns and token not in {"curriculum", "threaded", "tree"}]
    return {" ".join(tokens[index:index + 5]) for index in range(max(0, len(tokens) - 4))}


def _jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left or right else 1.0


def _normalized_code_tokens(content: str) -> list[str]:
    content = re.sub(r"/\*.*?\*/|//[^\n]*", " ", content, flags=re.S)
    content = re.sub(
        r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b',
        " LIT ",
        content,
    )
    raw = re.findall(
        r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]",
        content,
    )
    keywords = {
        "if", "else", "for", "while", "return", "class", "struct", "const",
        "auto", "bool", "int", "long", "void", "true", "false", "public",
        "private", "namespace", "std", "vector", "optional", "pair", "tuple",
        "size_t", "nullptr", "static_cast", "new", "delete",
    }
    return [
        token if token in keywords or not re.match(r"[A-Za-z_]", token) else "ID"
        for token in raw
    ]


def _ngrams(tokens: list[str], width: int = 9) -> set[tuple[str, ...]]:
    return {
        tuple(tokens[index:index + width])
        for index in range(max(0, len(tokens) - width + 1))
    }


def _dimension_hash(*contents: str) -> str:
    tokens = _normalized_code_tokens("\n".join(contents))
    return _sha256_bytes(" ".join(tokens).encode())


def _artifact_parts(root: Path) -> dict[str, str]:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    solution = [str(value) for value in config["files"]["solution"]]
    examples = [str(value) for value in config["files"]["example"]]
    header_name = next(value for value in solution if value.endswith((".h", ".hpp")))
    reference_name = next(value for value in examples if value.endswith(".cpp"))
    header = (root / header_name).read_text(encoding="utf-8")
    reference = (root / reference_name).read_text(encoding="utf-8")
    public_match = re.search(
        r"\n public:\n(.*?)\n#ifdef CURRICULUM_TESTING", header, flags=re.S
    )
    private_match = re.search(r"\n private:\n(.*)\n};", header, flags=re.S)
    if public_match is None or private_match is None or "#endif" not in reference:
        raise RuntimeError(f"artifact_profile_incomplete: {root.name}")
    task_reference = reference.rsplit("#endif", 1)[1]
    task_reference = task_reference.rsplit("}  // namespace curriculum", 1)[0]
    return {
        "docs": (root / ".docs/introduction.md").read_text(encoding="utf-8"),
        "api": public_match.group(1),
        "state": private_match.group(1),
        "reference": task_reference,
        "visible": (root / "task_visible_test.cpp").read_text(encoding="utf-8"),
        "hidden": (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8"),
        "negative": (root / ".meta/negative_fixture.cpp").read_text(encoding="utf-8"),
    }


def _artifact_profile(root: Path) -> dict[str, object]:
    parts = _artifact_parts(root)
    primary = "\n".join(
        parts[name] for name in ("docs", "api", "reference", "visible", "hidden")
    )
    dimensions = {
        "public_api": _dimension_hash(parts["docs"], parts["api"]),
        "owned_state_or_algorithm": _dimension_hash(parts["state"], parts["reference"]),
        "mutation_selection_rules": _dimension_hash(parts["reference"], parts["visible"]),
        "invalid_boundary_behavior": _dimension_hash(parts["docs"], parts["hidden"]),
        "reference_control_flow": _dimension_hash(parts["reference"]),
        "deterministic_oracle": _dimension_hash(parts["visible"], parts["hidden"]),
        "topic_negative_fixture": _dimension_hash(parts["negative"]),
    }
    return {
        "task_id": root.name,
        "dimensions": dimensions,
        "grams": _ngrams(_normalized_code_tokens(primary)),
    }


def _pair_evidence(left: dict[str, object], right: dict[str, object]) -> dict[str, object]:
    left_dimensions = left["dimensions"]
    right_dimensions = right["dimensions"]
    assert isinstance(left_dimensions, dict) and isinstance(right_dimensions, dict)
    same = sorted(
        name for name in HARD_RULE_DIMENSIONS
        if left_dimensions[name] == right_dimensions[name]
    )
    left_grams = left["grams"]
    right_grams = right["grams"]
    assert isinstance(left_grams, set) and isinstance(right_grams, set)
    denominator = min(len(left_grams), len(right_grams))
    overlap = len(left_grams & right_grams) / denominator if denominator else 1.0
    violations = [f"same:{name}" for name in same]
    if overlap >= PAIR_THRESHOLD:
        violations.append("combined_primary_logic_implementation")
    return {
        "left": left["task_id"],
        "right": right["task_id"],
        "differing_dimensions": sorted(set(HARD_RULE_DIMENSIONS) - set(same)),
        "same_dimensions": same,
        "combined_overlap": round(overlap, 6),
        "violations": violations,
    }


def _require_distinct_pair(evidence: dict[str, object]) -> None:
    if evidence["violations"]:
        raise RuntimeError(
            "duplicate_family: "
            f"{evidence['left']} / {evidence['right']}: {evidence['violations']}"
        )


def _screen_artifact_roots(
    roots: Sequence[tuple[str, Path]], *, enforce_dimensions: bool = True
) -> dict[str, object]:
    profiles = {task_id: _artifact_profile(root) for task_id, root in roots}
    pair_evidence: list[dict[str, object]] = []
    ordered = sorted(profiles)
    for index, left in enumerate(ordered):
        for right in ordered[index + 1:]:
            evidence = _pair_evidence(profiles[left], profiles[right])
            if not enforce_dimensions:
                evidence["violations"] = (
                    ["combined_primary_logic_implementation"]
                    if evidence["combined_overlap"] >= PAIR_THRESHOLD else []
                )
            _require_distinct_pair(evidence)
            pair_evidence.append(evidence)
    expected = len(roots) * (len(roots) - 1) // 2
    if len(pair_evidence) != expected:
        raise RuntimeError(
            f"duplicate_family: all-pairs incomplete: {len(pair_evidence)} != {expected}"
        )
    strongest = max(pair_evidence, key=lambda item: item["combined_overlap"])
    return {
        "status": "pass",
        "normalizer": NORMALIZER,
        "comparison_scope": (
            "actual emitted docs, public API, owned state, task reference control flow, "
            "visible/private deterministic tests, and topic negative fixture"
        ),
        "required_dimensions": list(HARD_RULE_DIMENSIONS),
        "all_pairs_compared": len(pair_evidence),
        "pair_threshold": PAIR_THRESHOLD,
        "strongest_pair": strongest,
        "dimension_hashes": {
            task_id: profiles[task_id]["dimensions"] for task_id in ordered
        },
        "pair_evidence": pair_evidence,
        "negative_fixtures_excluded_from_similarity": True,
    }


def _holdout_ids() -> list[str]:
    if not BENCHMARK_MANIFEST.is_file():
        return []
    payload = json.loads(BENCHMARK_MANIFEST.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        values = payload.get("task_ids") or payload.get("tasks") or payload.get("ids") or []
    else:
        values = payload
    result = []
    for value in values:
        if isinstance(value, str):
            result.append(value.rsplit("/", 1)[-1])
        elif isinstance(value, dict):
            candidate = value.get("task_id") or value.get("id") or value.get("slug")
            if candidate:
                result.append(str(candidate).rsplit("/", 1)[-1])
    return sorted(set(result))


def _replace_emitted_text(root: Path, old: str, new: str) -> None:
    changed = 0
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        if path == root / ".meta/config.json" or relative.parts[0] == "test":
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if old in content:
            path.write_text(content.replace(old, new), encoding="utf-8")
            changed += 1
    if changed == 0:
        raise RuntimeError(f"adversarial_control_invalid: {old!r} absent")


def _make_adversarial_clone(source: Path, clone: Path, clone_kind: str) -> None:
    shutil.copytree(source, clone)
    if clone_kind == "domain-identifier-renamed-clone":
        _replace_emitted_text(clone, "Appointment", "Reservation")
        _replace_emitted_text(clone, "appointment", "reservation")
    elif clone_kind == "constants-or-policy-only-clone":
        _replace_emitted_text(clone, "30", "31")
    elif clone_kind == "opposite-end-selection-clone":
        for left, right in (
            ("successor", "predecessor"),
            ("minimum", "maximum"),
        ):
            marker = f"hard_rule_temporary_{left}"
            _replace_emitted_text(clone, left, marker)
            _replace_emitted_text(clone, right, left)
            _replace_emitted_text(clone, marker, right)
    else:
        raise ValueError(f"unknown adversarial clone kind: {clone_kind}")


def _run_adversarial_controls(out: Path) -> dict[str, str]:
    base = CASES[0]
    outcomes: dict[str, str] = {}
    names = (
        "domain-identifier-renamed-clone",
        "constants-or-policy-only-clone",
        "opposite-end-selection-clone",
    )
    with tempfile.TemporaryDirectory(prefix="threaded-tree-hard-rule-") as temporary:
        temporary_root = Path(temporary)
        for name in names:
            _make_adversarial_clone(
                out / base.task_id, temporary_root / name, name
            )
        for name in names:
            try:
                _screen_artifact_roots(
                    [
                        (base.task_id, out / base.task_id),
                        (name, temporary_root / name),
                    ],
                    enforce_dimensions=False,
                )
            except RuntimeError as error:
                if "duplicate_family" not in str(error):
                    raise
                outcomes[name] = "rejected:duplicate_family:emitted_artifacts"
            else:
                raise RuntimeError(f"duplicate_family: adversarial control passed: {name}")
    return outcomes


def _screen(out: Path) -> dict[str, object]:
    prompt_hashes: dict[str, str] = {}
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        solution = config["files"]["solution"]
        if solution != [f"{case.task_id}.h", f"{case.task_id}.cpp"]:
            raise RuntimeError(f"target_reference_mismatch: {case.task_id}")
        for role, relatives in config["files"].items():
            for relative in relatives:
                path = Path(relative)
                if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
                    raise RuntimeError(f"unsafe_path: {case.task_id}: {role}: {relative}")
                if role == "solution" and (relative.startswith(".meta/") or relative.startswith(".docs/") or relative == "CMakeLists.txt"):
                    raise RuntimeError(f"unsafe_path: {case.task_id}: role conflict")
        prompt = build_prompt(load_task(root))
        forbidden = (".meta/example", "task_hidden_test", "CMakeLists.txt", "provenance.json", "catch.hpp")
        if any(token in prompt for token in forbidden):
            raise RuntimeError(f"prompt_contract_incomplete: {case.task_id}")
        for relative in solution:
            if relative not in prompt:
                raise RuntimeError(f"prompt_contract_incomplete: {case.task_id}: {relative}")
        prompt_hashes[case.task_id] = _sha256_bytes(prompt.encode())
        if ".meta/negative_fixture.cpp" in prompt or ".meta/negative_fixture.json" in prompt:
            raise RuntimeError(f"prompt_contract_incomplete: {case.task_id}: negative fixture leaked")
    hard_rule = _screen_artifact_roots(
        [(case.task_id, out / case.task_id) for case in CASES]
    )
    controls = _run_adversarial_controls(out)
    holdout_ids = _holdout_ids()
    if any(case.task_id in holdout_ids for case in CASES):
        raise RuntimeError("benchmark_id_overlap")
    holdout_profiles: dict[str, set[str]] = {}
    for slug in holdout_ids:
        root = HOLDOUT_ROOT / slug
        if not root.is_dir():
            continue
        texts = [path.read_text(encoding="utf-8", errors="replace") for path in sorted(root.rglob("*")) if path.is_file() and path.suffix in {".md", ".h", ".hpp", ".cpp", ".toml", ".json"}]
        holdout_profiles[slug] = _normalize("\n".join(texts))
    candidate_profiles = {
        case.task_id: _normalize(
            "\n".join(_artifact_parts(out / case.task_id)[name]
                       for name in ("docs", "api", "reference", "visible", "hidden"))
        )
        for case in CASES
    }
    holdout_pairs = [(case.task_id, slug, _jaccard(candidate_profiles[case.task_id], profile)) for case in CASES for slug, profile in holdout_profiles.items()]
    strongest_holdout = max(holdout_pairs, key=lambda item: item[2]) if holdout_pairs else None
    if strongest_holdout and strongest_holdout[2] >= 0.62:
        raise RuntimeError(f"benchmark_content_overlap: {strongest_holdout}")
    receipt = {
        "schema_version": "threaded-tree-family-screen-v3",
        "normalizer": NORMALIZER,
        "family_duplicate_screen": "pass",
        "hard_rule": hard_rule,
        "hard_rule_status": "pass",
        "all_pairs_compared": hard_rule["all_pairs_compared"],
        "strongest_family_pair": hard_rule["strongest_pair"],
        "adversarial_clone_results": controls,
        "benchmark_id_screen": "pass" if holdout_ids else "not_completed",
        "benchmark_semantic_screen": "pass" if len(holdout_profiles) == len(holdout_ids) and holdout_ids else "not_completed",
        "holdout_ids": len(holdout_ids),
        "holdout_profiles": len(holdout_profiles),
        "holdout_pairs_compared": len(holdout_pairs),
        "strongest_holdout_pair": None if strongest_holdout is None else {"task": strongest_holdout[0], "holdout": strongest_holdout[1], "score": strongest_holdout[2]},
        "prompt_boundary": "pass",
        "prompt_hashes": prompt_hashes,
    }
    _write(out / ".state/family-screen.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def _planned_records(out: Path) -> dict[str, dict[str, object]]:
    remedy = out / ".state/remedy"
    records: dict[str, dict[str, object]] = {}
    for case in CASES:
        path = remedy / f"{case.legacy_id}.json"
        spec = remedy / f"{case.legacy_id}.md"
        if not path.is_file() or not spec.is_file():
            raise RuntimeError(f"remedy_spec_incomplete: {case.legacy_id}")
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("status") not in {"planned", "implemented", "verified"} or record.get("remediated_task_id") != case.task_id:
            raise RuntimeError(f"remedy_disposition_conflict: {case.legacy_id}")
        if record.get("remedy_spec_hash") != _sha256_file(spec):
            raise RuntimeError(f"remedy_spec_incomplete: stale hash: {case.legacy_id}")
        records[case.legacy_id] = record
    return records


def _update_record(out: Path, case: Case, **updates: object) -> dict[str, object]:
    path = out / ".state/remedy" / f"{case.legacy_id}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record.update(updates)
    _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record


def _validate_reference(source: str, label: str) -> None:
    if any(token in source for token in BANNED_REFERENCE_TOKENS):
        raise RuntimeError(f"invariant_not_enforced: {label}: banned authoritative container")
    required = ("left_thread", "right_thread", "successor(", "predecessor(", "insert_node(", "erase_node(")
    if any(token not in source for token in required):
        raise RuntimeError(f"invariant_not_enforced: {label}: missing threaded mutation")
    if "clear_all();root_=nullptr" in source or "std::vector<int> keep" in source:
        raise RuntimeError(f"invariant_not_enforced: {label}: full rebuild deletion")


def _negative_source(case: Case) -> str:
    reference = _common_reference(case)
    old, new, _description = NEGATIVE_MUTATIONS[case.task_id]
    if reference.count(old) != 1:
        raise RuntimeError(
            f"negative_fixture_ambiguous: {case.task_id}: expected one {old!r}"
        )
    negative = reference.replace(old, new, 1)
    if negative == reference:
        raise RuntimeError(f"negative_fixture_missing: {case.task_id}")
    return negative


def verify_core(out: Path) -> dict[str, object]:
    fixture = '''#include <vector>
struct Legacy { std::vector<int> values; void erase(int k){std::vector<int> keep;for(int v:values)if(v!=k)keep.push_back(v);values=keep;} };
int main(){Legacy x;x.erase(1);}
'''
    compiler = shutil.which("c++")
    if compiler:
        with tempfile.TemporaryDirectory(prefix="threaded-fixture-") as temporary:
            source = Path(temporary) / "fixture.cpp"
            source.write_text(fixture, encoding="utf-8")
            subprocess.run([compiler, "-std=c++17", "-fsyntax-only", str(source)], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    fixture_rejected = False
    try:
        _validate_reference(fixture, "legacy-rebuild-template")
    except RuntimeError as error:
        fixture_rejected = "invariant_not_enforced" in str(error)
    if not fixture_rejected:
        raise RuntimeError("invariant_not_enforced: legacy-rebuild-template passed")
    fixture_hashes: dict[str, str] = {}
    for case in CASES:
        root = out / case.task_id
        reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
        negative = (root / ".meta/negative_fixture.cpp").read_text(encoding="utf-8")
        _validate_reference(reference, case.task_id)
        _validate_reference(negative, f"{case.task_id}:topic-negative")
        if negative != _negative_source(case):
            raise RuntimeError(f"negative_fixture_drift: {case.task_id}")
        fixture_hashes[case.task_id] = _sha256_bytes(negative.encode())
    screen = _screen(out)
    receipt = {
        "schema_version": "threaded-tree-core-verification-v3",
        "status": "pass",
        "roots": len(CASES),
        "primary_core_objective": "achieved",
        "negative_fixture": "legacy-rebuild-template",
        "negative_fixture_compiled": compiler is not None,
        "negative_fixture_result": "invariant_not_enforced",
        "topic_negative_fixtures": {
            "status": "pending_docker_execution",
            "count": len(fixture_hashes),
            "hashes": fixture_hashes,
        },
        "unique_logic_tags": len({case.logic_tag for case in CASES}),
        "family_screen": screen["family_duplicate_screen"],
        "hard_rule_status": screen["hard_rule_status"],
        "adversarial_clone_results": screen["adversarial_clone_results"],
        "benchmark_semantic_screen": screen["benchmark_semantic_screen"],
        "prompt_boundary": screen["prompt_boundary"],
    }
    _write(out / ".state/core-verification.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    return receipt


def build(out: Path = ROOT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() == LEGACY_ROOT.resolve():
        raise RuntimeError("refusing to modify LEGACY_ROOT")
    if not CURRICULUM.is_file() or not SPEC.is_file():
        raise RuntimeError("remedy_spec_incomplete: curriculum or family specification missing")
    if not (SUPPORT / "catch.hpp").is_file() or not (SUPPORT / "tests-main.cpp").is_file():
        raise RuntimeError(f"missing content-addressed Catch support: {SUPPORT}")
    records = _planned_records(out)
    expected = {case.task_id for case in CASES}
    existing = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"} if out.is_dir() else set()
    for stale_name in sorted(existing - expected):
        stale = out / stale_name
        provenance_path = stale / ".meta/provenance.json"
        provenance = json.loads(provenance_path.read_text(encoding="utf-8")) if provenance_path.is_file() else {}
        if not force or provenance.get("family_id") != FAMILY_ID:
            raise RuntimeError(f"generator_output_drift: unexpected root {stale_name}")
        shutil.rmtree(stale)
    roots: list[Path] = []
    curriculum_hash = _sha256_file(CURRICULUM)
    spec_hash = _spec_contract_hash()
    support_hash = _sha256_file(SUPPORT / "catch.hpp")
    for case in CASES:
        root = out / case.task_id
        config = {
            "authors": ["w8-biayn"],
            "source": "newly-authored-in-repository",
            "attribution": "Clean-room repository-authored threaded-tree task under repository usage terms.",
            "blurb": case.contract,
            "files": {"solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"], "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]},
        }
        provenance = {
            "schema_version": "threaded-tree-provenance-v3",
            "task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "disposition": records[case.legacy_id]["disposition"],
            "family_id": FAMILY_ID,
            "curriculum_path": str(CURRICULUM),
            "curriculum_hash": curriculum_hash,
            "spec_path": str(SPEC),
            "spec_contract_hash": spec_hash,
            "spec_hash_scope": "content before Final re-verification evidence",
            "generator_revision": GENERATOR_REVISION,
            "generator_content_hash": _generator_hash(),
            "selected_prompt": PROMPT,
            "logic_tag": case.logic_tag,
            "hard_rule_dimensions": list(HARD_RULE_DIMENSIONS),
            "topic_negative_fixture": NEGATIVE_MUTATIONS[case.task_id][2],
            "clean_room_authoring_method": "repository-owned deterministic materializer",
            "license_usage_terms": "new repository content governed by repository license and local-family scope",
            "benchmark_separation": "official binary-search-tree is a permanent holdout; no benchmark assets imported",
            "catch_support_sha256": support_hash,
            "status": "local candidate only; no dataset release",
        }
        instructions = f'''# {case.class_name} contract

Implement the C++17 class `{case.class_name}` in namespace `curriculum` using the declarations in the provided header.

{case.contract}

The authoritative representation is the private heap-owned binary tree. Every node distinguishes a real left/right child from an inorder predecessor/successor thread with `left_thread` and `right_thread`. Mutations must directly repair affected child, parent, predecessor, and successor relations. A sorted vector, set/map, list/deque, unthreaded tree, hard-coded trace, or clear-and-reinsert implementation is not a substitute. Output vectors are observations only.

Unless the task-specific rule says otherwise, invalid or absent targets fail without mutation. Empty optional queries return `std::nullopt`. The `CURRICULUM_TESTING` audit must prove ordered acyclic child topology, correct parent links, exact predecessor/successor threads, and equal complete forward/reverse counts.

Boundary example: querying or deleting key `999` on an empty object returns failure or `std::nullopt` and leaves the object empty.
'''
        files = {
            ".docs/introduction.md": f"# {case.class_name}\n\n{case.contract}\n",
            ".docs/instructions.md": instructions,
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": f"[visible]\ndescription = \"{case.logic_tag} public behavior\"\n\n[hidden]\ndescription = \"task-specific boundary trace plus child/thread/parent audit\"\n",
            f"{case.task_id}.h": _header(case),
            f"{case.task_id}.cpp": _starter(case),
            ".meta/example.h": _header(case),
            ".meta/example.cpp": _common_reference(case),
            ".meta/negative_fixture.cpp": _negative_source(case),
            ".meta/negative_fixture.json": json.dumps(
                {
                    "schema_version": "threaded-tree-topic-negative-v1",
                    "task_id": case.task_id,
                    "description": NEGATIVE_MUTATIONS[case.task_id][2],
                    "expected_result": "strict_compile_pass_and_designated_tests_fail",
                    "test_scope": ["visible", "hidden"],
                },
                indent=2,
                sort_keys=True,
            ) + "\n",
            "task_visible_test.cpp": _test(case, False),
            ".meta/task_hidden_test.cpp": _test(case, True),
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
        _update_record(out, case, status="implemented", primary_core_objective="achieved", tree_hash_after=tree_hash, changed_owner_paths=[str(Path(__file__)), str(Path(__file__).with_name("moonlight_threaded_binary_tree_cases.py")), str(CURRICULUM), str(SPEC), "tests/test_moonlight_threaded_binary_tree_aider_tasks.py"])
        roots.append(root)
    core = verify_core(out)
    manifest = {
        "schema_version": "threaded-tree-materialization-v3",
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
        "hard_rule_status": core["hard_rule_status"],
        "adversarial_clone_results": core["adversarial_clone_results"],
        "topic_negative_fixtures": core["topic_negative_fixtures"],
        "benchmark_semantic_screen": core["benchmark_semantic_screen"],
        "status": "implemented",
    }
    _write(out / ".state/materialization.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
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
    if missing:
        receipt = {"schema_version": "threaded-tree-oracle-summary-v2", "status": "not_completed", "missing_prerequisites": missing, "required_command": "run the owner verifier in the designated network-disabled C++ image"}
        _write(out / ".state/oracle/verification.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        return
    compiler = str(Path(shutil.which("c++") or "").resolve())
    evidence_class = "docker_sanity" if os.environ.get("W8_THREADED_TREE_GRADER_IMAGE") else "host_diagnostic"
    identity = {
        "evidence_class": evidence_class,
        "locked_oracle": False,
        "image": os.environ.get("W8_THREADED_TREE_GRADER_IMAGE"),
        "network_policy": os.environ.get("W8_THREADED_TREE_SANDBOX_POLICY", "host"),
        "compiler_path": compiler,
        "compiler_version": _command_output([compiler, "--version"]).splitlines()[0],
        "compiler_sha256": _sha256_file(Path(compiler)),
        "cmake_version": _command_output(["cmake", "--version"]).splitlines()[0],
        "ctest_version": _command_output(["ctest", "--version"]).splitlines()[0],
        "catch_sha256": _sha256_file(SUPPORT / "catch.hpp"),
        "generator_revision": GENERATOR_REVISION,
        "generator_content_hash": _generator_hash(),
    }
    totals = {"normal": 0, "sanitizer": 0, "negative": 0}
    negative_results: dict[str, dict[str, object]] = {}
    for case in CASES:
        source = out / case.task_id
        with tempfile.TemporaryDirectory(prefix=f"{case.task_id}-") as temporary:
            root = Path(temporary) / case.task_id
            shutil.copytree(source, root)
            counts: dict[str, int] = {}
            commands: dict[str, list[str]] = {}
            for mode, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = root / f"build-{mode}"
                configure = ["cmake", "-S", str(root), "-B", str(build_dir), "-G", "Unix Makefiles", f"-DCMAKE_CXX_COMPILER={compiler}", f"-DTASK_SOURCE={root / '.meta/example.cpp'}", *flags]
                subprocess.run(configure, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                counts[mode] = _discover(build_dir)
                test_run = subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                if test_run.returncode != 0:
                    raise RuntimeError(f"reference_sanitizer_failed: {case.task_id}: {mode}\n{test_run.stdout}")
                commands[mode] = configure
            if counts["normal"] != counts["sanitizer"]:
                raise RuntimeError(f"sanitizer_test_count_mismatch: {case.task_id}")
            totals["normal"] += counts["normal"]
            totals["sanitizer"] += counts["sanitizer"]
            negative_build = root / "build-negative"
            negative_configure = [
                "cmake", "-S", str(root), "-B", str(negative_build), "-G",
                "Unix Makefiles", f"-DCMAKE_CXX_COMPILER={compiler}",
                f"-DTASK_SOURCE={root / '.meta/negative_fixture.cpp'}",
            ]
            subprocess.run(negative_configure, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            negative_compile = subprocess.run(
                ["cmake", "--build", str(negative_build), "--parallel", "2"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if negative_compile.returncode != 0:
                raise RuntimeError(
                    f"negative_fixture_compile_failed: {case.task_id}\n"
                    f"{negative_compile.stdout[-4000:]}"
                )
            negative_count = _discover(negative_build)
            negative_run = subprocess.run(
                ["ctest", "--test-dir", str(negative_build), "--output-on-failure"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            if negative_run.returncode == 0:
                raise RuntimeError(f"negative_fixture_not_rejected: {case.task_id}")
            if negative_count != counts["normal"]:
                raise RuntimeError(f"negative_fixture_test_count_mismatch: {case.task_id}")
            counts["negative"] = negative_count
            commands["negative"] = negative_configure
            totals["negative"] += negative_count
            negative_results[case.task_id] = {
                "strict_compile": "pass",
                "discovered_tests": negative_count,
                "test_returncode": negative_run.returncode,
                "test_log_hash": _sha256_bytes(negative_run.stdout.encode()),
                "result": "rejected_false_substitute",
                "description": NEGATIVE_MUTATIONS[case.task_id][2],
            }
        receipt = {"schema_version": "threaded-tree-oracle-v3", "status": "pass", "task_id": case.task_id, "legacy_task_id": case.legacy_id, "tree_hash": _tree_hash(source), "reference_hashes": {"header": _sha256_file(source / ".meta/example.h"), "source": _sha256_file(source / ".meta/example.cpp"), "negative": _sha256_file(source / ".meta/negative_fixture.cpp")}, "reference_mapping": {".meta/example.h": f"{case.task_id}.h", ".meta/example.cpp": f"{case.task_id}.cpp"}, "test_counts": counts, "negative_fixture_result": negative_results[case.task_id], "commands": commands, **identity}
        _write(out / ".state/oracle" / f"{case.task_id}.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        local_status = "oracle_verified" if evidence_class == "docker_sanity" else "implemented"
        _update_record(out, case, oracle_receipt=str(out / ".state/oracle" / f"{case.task_id}.json"), test_counts=counts, local_status=local_status)
    screen = json.loads((out / ".state/family-screen.json").read_text(encoding="utf-8"))
    complete = evidence_class == "docker_sanity" and identity["network_policy"] == "none" and screen["benchmark_semantic_screen"] == "pass" and screen["hard_rule_status"] == "pass" and len(negative_results) == len(CASES)
    summary = {"schema_version": "threaded-tree-oracle-summary-v3", "status": "pass", "roots": len(CASES), "test_counts": totals, "equal_positive_counts": totals["normal"] == totals["sanitizer"] and totals["normal"] > 0, "negative_fixture_results": negative_results, "executed_negative_fixtures": len(negative_results), "rejected_negative_fixtures": sum(result["result"] == "rejected_false_substitute" for result in negative_results.values()), **identity}
    _write(out / ".state/oracle/verification.json", json.dumps(summary, indent=2, sort_keys=True) + "\n")
    manifest = json.loads((out / ".state/materialization.json").read_text(encoding="utf-8"))
    manifest.update({"oracle_status": "pass", "oracle_evidence_class": evidence_class, "oracle_receipts": len(CASES), "test_counts": totals, "topic_negative_fixtures": {"status": "pass", "compiled": len(negative_results), "rejected": len(negative_results)}, "status": "local_family_verified" if complete else "implemented"})
    _write(out / ".state/materialization.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    for case in CASES:
        _update_record(out, case, status="verified" if complete else "implemented", benchmark_screen="pass" if screen["benchmark_semantic_screen"] == "pass" else "pending", family_screen="pass", hard_rule_status=screen["hard_rule_status"], adversarial_clone_results=screen["adversarial_clone_results"], negative_fixture_result=negative_results[case.task_id], prompt_boundary="pass", local_status="local_family_verified" if complete else "implemented")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    print(f"Wrote {len(roots)} remediated threaded-binary-tree tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
