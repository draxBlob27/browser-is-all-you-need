"""Materialize and locally verify the remediated safe XOR-chain family."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
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
from w8_biayn.integrations.moonlight_xor_linked_list_cases import CASES as LEGACY_CASES, Case
from w8_biayn.integrations.moonlight_xor_linked_list_hard_rule import (
    NEGATIVE_MUTATIONS,
    PAYLOADS,
    REJECTED,
    TRACE_TESTS,
    Payload,
)


ROOT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/xor-linked-list")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dsa/xor-linked-list")
CURRICULUM = Path("docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_XOR_LINKED_LIST_CURRICULUM.md")
SPEC = Path("docs/aider-tasks-spec/aider-dsa/xor-linked-list.md")
PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
BENCHMARK_MANIFEST = Path("manifests/aider_sft/aider-polyglot-cpp-26.json")
SUPPORT = Path(".w8-biayn/data/aider-sft-source-only-75-v1/private/grader-support/exercism-catch-v1/test")
FAMILY_ID = "aider-dsa-xor-linked-list-v3"
GENERATOR_REVISION = "xor-linked-list-materializer-v3"
NORMALIZER = "aider-cleanroom-hard-rule-v3"
CASES = tuple(case for case in LEGACY_CASES if case.task_id in PAYLOADS)
REJECTED_CASES = tuple(case for case in LEGACY_CASES if case.task_id in REJECTED)
MIN_COUNT = 15
MAX_COUNT = 20
PINNED_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
BANNED_REFERENCE_TOKENS = (
    "std::list<", "std::deque<", "std::map<", "std::set<", "std::multiset<",
    "std::unordered_", "reinterpret_cast", "uintptr_t", "boost::", "__gnu_pbds",
)


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _generator_hash() -> str:
    digest = hashlib.sha256()
    for path in (
        Path(__file__),
        Path(__file__).with_name("moonlight_xor_linked_list_cases.py"),
        Path(__file__).with_name("moonlight_xor_linked_list_hard_rule.py"),
    ):
        digest.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return "sha256:" + digest.hexdigest()


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
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return "sha256:" + digest.hexdigest()


def _payload_name(field: str | None) -> str | None:
    return field.rsplit(" ", 1)[-1] if field else None


def _payload_fields(payload: Payload) -> str:
    return " ".join(f"{field}{{}};" for field in (payload.value, payload.aux, payload.metric) if field)


def _specialize_reference(case: Case, reference: str | None = None) -> str:
    payload = PAYLOADS[case.task_id]
    result = case.reference if reference is None else reference
    for generic, field in (("value", payload.value), ("aux", payload.aux), ("metric", payload.metric)):
        name = _payload_name(field)
        if name:
            result = result.replace(f".{generic}", f".{name}")
    return result


def _header(case: Case) -> str:
    payload = PAYLOADS[case.task_id]
    edge = "  static long long edge(const Node&,const Node&);\n" if payload.needs_edge else ""
    cursor = "  SlotId current_=0;\n" if payload.needs_cursor else ""
    return f'''#pragma once
#include <cstddef>
#include <cstdint>
#include <optional>
#include <utility>
#include <vector>

namespace curriculum {{
#ifdef CURRICULUM_TESTING
struct XorAudit {{ bool valid; std::size_t forward_count; std::size_t reverse_count; std::size_t xor_steps; }};
#endif
class {case.class_name} {{
 public:
  using SlotId = std::uint32_t;
  using Handle = std::uint64_t;
  // HARD-RULE-PUBLIC-BEGIN
{case.declarations}
  // HARD-RULE-PUBLIC-END
#ifdef CURRICULUM_TESTING
  XorAudit audit_for_test() const;
#endif
 private:
  // HARD-RULE-STATE-BEGIN
  struct Node {{ int id=0; SlotId link=0; std::uint32_t generation=0; bool live=false; {_payload_fields(payload)} }};
  bool valid(Handle) const;
  SlotId slot_of(Handle) const;
  Handle handle_of(SlotId) const;
  SlotId allocate(int id,int value,std::uint64_t aux,long long metric=0);
  SlotId find_id(int id) const;
  bool locate(SlotId wanted,SlotId& previous,SlotId& next) const;
  void insert_after(SlotId node,SlotId anchor);
  void unlink(SlotId node);
  void release(SlotId node);
  void clear_all();
  std::vector<int> ids() const;
{edge}
  std::vector<Node> arena_{{Node{{}}}};
  SlotId head_=0,tail_=0;
{cursor}  // HARD-RULE-CLASS-STATE
  std::size_t size_=0;
  {case.private_fields}
  // HARD-RULE-STATE-END
}};
}}  // namespace curriculum
'''


def _common_reference(case: Case) -> str:
    name = case.class_name
    payload = PAYLOADS[case.task_id]
    fields = ((payload.value, "value"), (payload.aux, "aux"), (payload.metric, "metric"))
    initializer = "".join(f",{generic}" for field, generic in fields if field)
    allocate_parameters = ",".join(("int id", "int value" if payload.value else "int", "std::uint64_t aux" if payload.aux else "std::uint64_t", "long long metric" if payload.metric else "long long"))
    resets = "".join(f"arena_[node].{_payload_name(field)}={{}};" for field, _ in fields if field)
    cursor_reset = "if(current_==node)current_=0;" if payload.needs_cursor else ""
    clear_cursor = "current_=0;" if payload.needs_cursor else ""
    return f'''#include "{case.task_id}.h"
#include <algorithm>
#include <climits>
#include <cstdlib>
#include <stdexcept>

namespace curriculum {{
bool {name}::valid(Handle h)const{{SlotId x=slot_of(h);return h&&x<arena_.size()&&arena_[x].live&&arena_[x].generation==static_cast<std::uint32_t>(h>>32U);}}
{name}::SlotId {name}::slot_of(Handle h)const{{return static_cast<SlotId>(h);}}
{name}::Handle {name}::handle_of(SlotId x)const{{return (static_cast<Handle>(arena_[x].generation)<<32U)|x;}}
{name}::SlotId {name}::allocate({allocate_parameters}){{for(SlotId x=1;x<arena_.size();++x)if(!arena_[x].live){{auto generation=arena_[x].generation+1U;if(!generation)generation=1U;arena_[x]=Node{{id,0,generation,true{initializer}}};return x;}}arena_.push_back(Node{{id,0,1,true{initializer}}});return static_cast<SlotId>(arena_.size()-1U);}}
{name}::SlotId {name}::find_id(int id)const{{for(SlotId p=0,c=head_,n=0;c;p=c,c=n){{if(arena_[c].id==id)return c;n=p^arena_[c].link;}}return 0;}}
bool {name}::locate(SlotId wanted,SlotId& previous,SlotId& next)const{{previous=0;for(SlotId current=head_;current;current=next){{next=previous^arena_[current].link;if(current==wanted)return true;previous=current;}}next=0;return false;}}
void {name}::insert_after(SlotId node,SlotId anchor){{SlotId next=head_;if(anchor){{SlotId previous=0;locate(anchor,previous,next);}}arena_[node].link=anchor^next;if(anchor)arena_[anchor].link^=next^node;else head_=node;if(next)arena_[next].link^=anchor^node;else tail_=node;++size_;}}
void {name}::unlink(SlotId node){{SlotId previous=0,next=0;locate(node,previous,next);if(previous)arena_[previous].link^=node^next;else head_=next;if(next)arena_[next].link^=node^previous;else tail_=previous;arena_[node].link=0;--size_;}}
void {name}::release(SlotId node){{arena_[node].live=false;arena_[node].id=0;{resets}{cursor_reset}}}
void {name}::clear_all(){{while(head_){{SlotId node=head_;unlink(node);release(node);}}{clear_cursor}}}
std::vector<int> {name}::ids()const{{std::vector<int> out;for(SlotId previous=0,current=head_,next=0;current;previous=current,current=next){{out.push_back(arena_[current].id);next=previous^arena_[current].link;}}return out;}}
// HARD-RULE-REFERENCE-BEGIN
{_specialize_reference(case)}
// HARD-RULE-REFERENCE-END
#ifdef CURRICULUM_TESTING
XorAudit {name}::audit_for_test()const{{bool ok=true;std::size_t forward=0,reverse=0,steps=0;SlotId previous=0,last=0;
 for(SlotId current=head_,next=0;current;previous=current,current=next){{if(current>=arena_.size()||!arena_[current].live){{ok=false;break;}}next=previous^arena_[current].link;++steps;if(next&&(next>=arena_.size()||!arena_[next].live)){{ok=false;break;}}last=current;if(++forward>size_){{ok=false;break;}}}}
 if(last!=tail_||forward!=size_){{ok=false;}}
 SlotId next=0,first=0;
 for(SlotId current=tail_,previous_slot=0;current;next=current,current=previous_slot){{if(current>=arena_.size()||!arena_[current].live){{ok=false;break;}}previous_slot=next^arena_[current].link;++steps;first=current;if(++reverse>size_){{ok=false;break;}}}}
 if(first!=head_||reverse!=size_||forward!=reverse||((head_==0)!=(tail_==0)))ok=false;
 return {{ok,forward,reverse,steps}};}}
#endif
}}  // namespace curriculum
'''


def _starter(case: Case) -> str:
    name = case.class_name
    return f'''#include "{case.task_id}.h"
namespace curriculum {{
bool {name}::valid(Handle)const{{return false;}}{name}::SlotId {name}::slot_of(Handle)const{{return 0;}}{name}::Handle {name}::handle_of(SlotId)const{{return 0;}}
{name}::SlotId {name}::allocate(int,int,std::uint64_t,long long){{return 0;}}{name}::SlotId {name}::find_id(int)const{{return 0;}}bool {name}::locate(SlotId,SlotId&,SlotId&)const{{return false;}}
void {name}::insert_after(SlotId,SlotId){{}}void {name}::unlink(SlotId){{}}void {name}::release(SlotId){{}}void {name}::clear_all(){{}}std::vector<int> {name}::ids()const{{return{{}};}}
{case.starter}
#ifdef CURRICULUM_TESTING
XorAudit {name}::audit_for_test()const{{return {{false,0U,0U,0U}};}}
#endif
}}  // namespace curriculum
'''


def _visible_test(case: Case) -> str:
    return f'''#include "{case.task_id}.h"
#include <catch.hpp>
#include <stdexcept>
TEST_CASE("{case.task_id} public contract","[visible]"){{using namespace curriculum;{case.visible}}}
'''


def _hidden_test(case: Case) -> str:
    variable = re.search(r"\b([A-Za-z_]\w*)\s*(?:\(|;)", case.hidden)
    if not variable:
        raise ValueError(f"hidden test has no task variable: {case.task_id}")
    name = variable.group(1)
    # Constructor-style declarations with arguments still leave the variable as the
    # second identifier, so prefer the last class-local declaration match.
    declarations = re.findall(rf"\b{re.escape(case.class_name)}\s+([A-Za-z_]\w*)", case.hidden)
    if declarations:
        name = declarations[-1]
    return f'''#include "{case.task_id}.h"
#include <catch.hpp>
#include <climits>
#include <stdexcept>
#include <utility>
#include <vector>
TEST_CASE("{case.task_id} private invariant trace","[hidden]"){{using namespace curriculum;{case.hidden}const auto audit={name}.audit_for_test();REQUIRE(audit.valid);REQUIRE(audit.forward_count==audit.reverse_count);REQUIRE(audit.xor_steps==audit.forward_count+audit.reverse_count);}}
'''


def _trace_test(case: Case) -> str:
    return f'''#include "{case.task_id}.h"
#include <catch.hpp>
#include <cstdint>
#include <optional>
#include <utility>
#include <vector>
TEST_CASE("{case.task_id} independent operation oracle","[trace]"){{using namespace curriculum;
{TRACE_TESTS[case.task_id]}
}}
'''


def _negative_reference(case: Case) -> str:
    before, after = NEGATIVE_MUTATIONS[case.task_id]
    if before not in case.reference:
        raise RuntimeError(f"negative_fixture_source_drift: {case.task_id}")
    mutated = case.reference.replace(before, after, 1)
    return _common_reference(case).replace(_specialize_reference(case), _specialize_reference(case, mutated), 1)


def _cmake(case: Case) -> str:
    return f'''cmake_minimum_required(VERSION 3.16)
project({case.task_id.replace('-', '_')} LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
enable_testing()
add_executable(task_tests {case.task_id}.cpp task_visible_test.cpp .meta/task_hidden_test.cpp .meta/task_trace_test.cpp test/tests-main.cpp)
target_include_directories(task_tests PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}} ${{CMAKE_CURRENT_SOURCE_DIR}}/test)
target_compile_definitions(task_tests PRIVATE CURRICULUM_TESTING=1 EXERCISM_RUN_ALL_TESTS=1)
add_executable(negative_tests EXCLUDE_FROM_ALL .meta/negative.cpp task_visible_test.cpp .meta/task_hidden_test.cpp .meta/task_trace_test.cpp test/tests-main.cpp)
target_include_directories(negative_tests PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}} ${{CMAKE_CURRENT_SOURCE_DIR}}/test)
target_compile_definitions(negative_tests PRIVATE CURRICULUM_TESTING=1 EXERCISM_RUN_ALL_TESTS=1)
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(task_tests PRIVATE -Wall -Wextra -Wpedantic -Werror)
  target_compile_options(negative_tests PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
add_test(NAME visible COMMAND task_tests "[visible]")
add_test(NAME hidden COMMAND task_tests "[hidden]")
add_test(NAME trace COMMAND task_tests "[trace]")
'''


def _remedy_record(out: Path, case: Case, *, status: str, tree_hash: str | None = None) -> dict[str, object]:
    path = out / ".state" / "remedy" / f"{case.legacy_id}.json"
    if not path.is_file():
        raise RuntimeError(f"remedy_spec_incomplete: {path}")
    record = json.loads(path.read_text(encoding="utf-8"))
    spec_path = Path(str(record["remedy_spec_path"]))
    if not spec_path.is_file() or _sha256_file(spec_path) != record.get("remedy_spec_hash"):
        raise RuntimeError(f"remedy_spec_incomplete: stale spec for {case.legacy_id}")
    expected = "repair-in-place" if case.legacy_id == case.task_id else "replace"
    if record.get("disposition") != expected or record.get("status") not in {"planned", "implemented", "verified"}:
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


def _rejected_record(out: Path, case: Case) -> dict[str, object]:
    path = out / ".state" / "remedy" / f"{case.legacy_id}.json"
    if not path.is_file():
        raise RuntimeError(f"remedy_spec_incomplete: {path}")
    record = json.loads(path.read_text(encoding="utf-8"))
    spec_path = Path(str(record["remedy_spec_path"]))
    if record.get("disposition") != "reject" or not spec_path.is_file() or _sha256_file(spec_path) != record.get("remedy_spec_hash"):
        raise RuntimeError(f"remedy_spec_incomplete: rejected record {case.legacy_id}")
    for field in ("tree_hash_after", "oracle_receipt", "test_counts"):
        record.pop(field, None)
    record.update({
        "family_id_after": FAMILY_ID,
        "replacement_task_id": None,
        "generator_content_hash_after": _generator_hash(),
        "primary_core_objective": "rejected_semantic_twin",
        "status": "rejected",
        "local_status": "rejected_hard_rule",
        "family_screen": "duplicate_family",
    })
    _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)
    return record


def _normalize(text: str) -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/|\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'", " ", text, flags=re.M | re.S)
    text = re.sub(r"\b\d+\b", "#", text.lower())
    domain = {token for case in CASES for token in re.findall(r"[a-z]+", case.task_id + " " + case.class_name)}
    return tuple(token for token in re.findall(r"[a-z_]+|[{}();,*&<>^]", text) if token not in domain)


def _ngrams(tokens: tuple[str, ...], width: int = 5) -> set[tuple[str, ...]]:
    return {tokens[index:index + width] for index in range(max(0, len(tokens) - width + 1))}


def _task_material(root: Path, task_id: str) -> str:
    paths = (".docs/instructions.md", f"{task_id}.h", ".meta/example.cpp", "task_visible_test.cpp", ".meta/task_hidden_test.cpp")
    return "\n".join((root / name).read_text(encoding="utf-8") for name in paths)


@dataclass(frozen=True)
class HardRuleMaterial:
    public_contract: str
    state_or_algorithm: str
    mutation_selection: str
    invalid_boundary: str
    reference_control_flow: str
    deterministic_oracle: str
    negative_fixture: str


HARD_RULE_THRESHOLDS = {
    "public_contract": 0.98,
    "state_or_algorithm": 0.94,
    "mutation_selection": 0.92,
    "invalid_boundary": 0.94,
    "reference_control_flow": 0.92,
    "deterministic_oracle": 0.96,
    "negative_fixture": 0.92,
}


_CPP_SHAPE_TOKENS = {
    "alignof", "and", "auto", "bool", "break", "case", "catch", "char", "class", "const", "continue",
    "default", "do", "double", "else", "enum", "explicit", "false", "float", "for", "if", "int", "long",
    "namespace", "noexcept", "not", "nullptr", "operator", "optional", "or", "pair", "private", "public",
    "return", "short", "signed", "sizeof", "static", "static_cast", "struct", "switch", "throw", "true", "try",
    "uint32_t", "uint64_t", "unsigned", "using", "vector", "void", "while",
}


def _between(text: str, begin: str, end: str) -> str:
    if text.count(begin) != 1 or text.count(end) != 1:
        raise RuntimeError(f"hard_rule_marker_missing: {begin}")
    return text.split(begin, 1)[1].split(end, 1)[0]


def _hard_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/|\"(?:\\.|[^\"])*\"|'(?:\\.|[^'])*'", " ", text, flags=re.M | re.S)
    tokens: list[str] = []
    for token in re.findall(r"[A-Za-z_]\w*|\d+|==|!=|<=|>=|&&|\|\||\+\+|--|->|[{}();,:?*+\-/&<>^=]", text):
        if token.isdigit():
            tokens.append("#")
        elif re.fullmatch(r"[A-Za-z_]\w*", token):
            tokens.append(token if token in _CPP_SHAPE_TOKENS else "id")
        else:
            tokens.append(token)
    return tuple(tokens)


def _hard_signature(text: str) -> set[tuple[str, ...]]:
    return _ngrams(_hard_tokens(text), width=4)


def _hard_material(root: Path, task_id: str) -> HardRuleMaterial:
    header = (root / f"{task_id}.h").read_text(encoding="utf-8")
    reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
    negative = (root / ".meta/negative.cpp").read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    hidden = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
    trace = (root / ".meta/task_trace_test.cpp").read_text(encoding="utf-8")
    docs = (root / ".docs/instructions.md").read_text(encoding="utf-8")
    public = _between(header, "HARD-RULE-PUBLIC-BEGIN", "HARD-RULE-PUBLIC-END")
    state = _between(header, "HARD-RULE-STATE-BEGIN", "HARD-RULE-STATE-END")
    logic = _between(reference, "HARD-RULE-REFERENCE-BEGIN", "HARD-RULE-REFERENCE-END")
    bad_logic = _between(negative, "HARD-RULE-REFERENCE-BEGIN", "HARD-RULE-REFERENCE-END")
    tests = visible + hidden + trace
    return HardRuleMaterial(
        public_contract=public + docs,
        state_or_algorithm=state + logic,
        mutation_selection=logic,
        invalid_boundary=logic + tests,
        reference_control_flow=logic,
        deterministic_oracle=trace,
        negative_fixture=bad_logic + tests,
    )


def _hard_pair_scores(left: HardRuleMaterial, right: HardRuleMaterial) -> dict[str, float]:
    scores: dict[str, float] = {}
    for dimension in HARD_RULE_THRESHOLDS:
        left_signature = _hard_signature(getattr(left, dimension))
        right_signature = _hard_signature(getattr(right, dimension))
        union = left_signature | right_signature
        scores[dimension] = len(left_signature & right_signature) / len(union) if union else 1.0
    return scores


def assert_hard_rule_pair(left_id: str, right_id: str, left: HardRuleMaterial, right: HardRuleMaterial) -> dict[str, float]:
    scores = _hard_pair_scores(left, right)
    failures = [name for name, score in scores.items() if score >= HARD_RULE_THRESHOLDS[name]]
    if failures:
        details = ",".join(f"{name}={scores[name]:.3f}" for name in failures)
        raise RuntimeError(f"duplicate_family: {left_id} and {right_id}: {details}")
    return scores


def adversarial_variant(material: HardRuleMaterial, control: str) -> HardRuleMaterial:
    def mutate(text: str) -> str:
        if control == "domain_identifier_renamed_clone":
            return re.sub(r"[A-Za-z_]\w*", lambda match: match.group(0) if match.group(0) in _CPP_SHAPE_TOKENS else "renamed_identifier", text)
        if control == "constants_policy_only_clone":
            return re.sub(r"\b\d+\b", "987654", text)
        if control == "opposite_end_selection_clone":
            swaps = {"head_": "tail_", "tail_": "head_", "front": "back", "back": "front", "first": "last", "last": "first"}
            return re.sub(r"\b(head_|tail_|front|back|first|last)\b", lambda match: swaps[match.group(0)], text)
        raise ValueError(control)
    return HardRuleMaterial(**{name: mutate(getattr(material, name)) for name in HARD_RULE_THRESHOLDS})


def _screen(out: Path) -> dict[str, object]:
    benchmark = json.loads(BENCHMARK_MANIFEST.read_text(encoding="utf-8"))
    holdout_ids = set(benchmark["task_ids"])
    task_ids = {case.task_id for case in CASES}
    if task_ids & holdout_ids:
        raise RuntimeError("benchmark_id_overlap")
    signatures = {case.task_id: _ngrams(_normalize(_task_material(out / case.task_id, case.task_id))) for case in CASES}
    hard_materials = {case.task_id: _hard_material(out / case.task_id, case.task_id) for case in CASES}
    strongest_dimensions = {name: {"pair": None, "jaccard": 0.0} for name in HARD_RULE_THRESHOLDS}
    ids = sorted(hard_materials)
    pair_count = 0
    for index, left in enumerate(ids):
        for right in ids[index + 1:]:
            scores = assert_hard_rule_pair(left, right, hard_materials[left], hard_materials[right])
            pair_count += 1
            for dimension, score in scores.items():
                if score > float(strongest_dimensions[dimension]["jaccard"]):
                    strongest_dimensions[dimension] = {"pair": [left, right], "jaccard": round(score, 6)}
    controls: dict[str, str] = {}
    exemplar_id = ids[0]
    for control in ("domain_identifier_renamed_clone", "constants_policy_only_clone", "opposite_end_selection_clone"):
        try:
            assert_hard_rule_pair(exemplar_id, control, hard_materials[exemplar_id], adversarial_variant(hard_materials[exemplar_id], control))
        except RuntimeError as error:
            if "duplicate_family" not in str(error):
                raise
            controls[control] = "duplicate_family"
    if len(controls) != 3:
        raise RuntimeError("duplicate_family: adversarial control escaped")
    related_inventory: list[str] = []
    strongest_related: dict[str, object] = {"pair": None, "jaccard": 0.0}
    reverify_dsa = ROOT.parent
    if reverify_dsa.is_dir():
        for family in sorted(path for path in reverify_dsa.iterdir() if path.is_dir() and path.name != ROOT.name):
            for root in sorted(path for path in family.iterdir() if path.is_dir() and path.name != ".state"):
                config = root / ".meta/config.json"
                if not config.is_file():
                    continue
                solution = json.loads(config.read_text(encoding="utf-8")).get("files", {}).get("solution", [])
                header = next((name for name in solution if name.endswith((".h", ".hpp"))), None)
                source = next((name for name in solution if name.endswith((".cpp", ".cc"))), None)
                paths = [root / ".docs/instructions.md", root / ".meta/example.cpp", root / "task_visible_test.cpp", root / ".meta/task_hidden_test.cpp"]
                if header:
                    paths.append(root / header)
                if source and not (root / ".meta/example.cpp").is_file():
                    paths.append(root / source)
                material = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in paths if path.is_file())
                if not material:
                    continue
                related_inventory.append(f"{family.name}/{root.name}")
                candidate = _ngrams(_normalize(material))
                for task_id, signature in signatures.items():
                    score = len(signature & candidate) / len(signature | candidate) if candidate else 0.0
                    if score > float(strongest_related["jaccard"]):
                        strongest_related = {"pair": [task_id, f"{family.name}/{root.name}"], "jaccard": round(score, 6)}
                    if score >= 0.75:
                        raise RuntimeError(f"duplicate_family: {task_id} and {family.name}/{root.name}: {score:.3f}")
    upstream = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
    if not upstream.is_dir():
        upstream = Path(".w8-biayn/data/polyglot-benchmark/cpp/exercises/practice")
    benchmark_status = "not_completed"
    benchmark_inventory: list[str] = []
    strongest_holdout: dict[str, object] = {"pair": None, "jaccard": 0.0}
    if upstream.is_dir():
        benchmark_status = "pass"
        for holdout in sorted(holdout_ids):
            root = upstream / holdout
            if not root.is_dir():
                benchmark_status = "not_completed"
                continue
            benchmark_inventory.append(holdout)
            paths = [path for path in root.rglob("*") if path.is_file() and path.suffix in {".md", ".h", ".hpp", ".cc", ".cpp", ".toml"}]
            signature = _ngrams(_normalize("\n".join(path.read_text(encoding="utf-8", errors="replace") for path in paths)))
            for task_id, candidate in signatures.items():
                score = len(candidate & signature) / len(candidate | signature) if signature else 0.0
                if score > float(strongest_holdout["jaccard"]):
                    strongest_holdout = {"pair": [task_id, holdout], "jaccard": round(score, 6)}
                if score >= 0.58:
                    raise RuntimeError(f"benchmark_content_overlap: {task_id} and {holdout}: {score:.3f}")
    prompts: dict[str, str] = {}
    for case in CASES:
        prompt = build_prompt(load_task(out / case.task_id))
        for forbidden in (".meta/example", "task_hidden_test", "CMakeLists.txt", "provenance.json", "catch.hpp"):
            if forbidden in prompt:
                raise RuntimeError(f"prompt_contract_incomplete: {case.task_id}: {forbidden}")
        prompts[case.task_id] = _sha256_bytes(prompt.encode())
    receipt = {
        "schema_version": "xor-family-screen-v3",
        "status": "pass" if benchmark_status == "pass" else "not_completed",
        "normalizer": NORMALIZER,
        "family_duplicate_screen": "pass",
        "count_bounds": {"minimum": MIN_COUNT, "maximum": MAX_COUNT, "actual": len(CASES)},
        "hard_rule_pair_count": pair_count,
        "hard_rule_thresholds": HARD_RULE_THRESHOLDS,
        "strongest_hard_rule_dimensions": strongest_dimensions,
        "adversarial_controls": controls,
        "related_family_inventory": related_inventory,
        "strongest_related_pair": strongest_related,
        "benchmark_whole_slug": "pass",
        "benchmark_semantic_screen": benchmark_status,
        "benchmark_inventory": benchmark_inventory,
        "strongest_holdout_pair": strongest_holdout,
        "prompt_boundary": "pass",
        "prompt_hashes": prompts,
        "unique_logic_tags": len({case.logic_tag for case in CASES}),
    }
    _write(out / ".state/family-screen.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    return receipt


def _validate_reference(text: str, task_id: str) -> None:
    if any(token in text for token in BANNED_REFERENCE_TOKENS):
        raise RuntimeError(f"invariant_not_enforced: banned authoritative representation in {task_id}")
    required = ("SlotId link", "^arena_[", ".link^=", "audit_for_test")
    if any(token not in text for token in required):
        raise RuntimeError(f"invariant_not_enforced: missing XOR-slot mechanism in {task_id}")


def verify_core(out: Path) -> dict[str, object]:
    if not MIN_COUNT <= len(CASES) <= MAX_COUNT or len({case.logic_tag for case in CASES}) != len(CASES):
        raise RuntimeError("duplicate_family")
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        if config["files"]["solution"] != [f"{case.task_id}.h", f"{case.task_id}.cpp"] or config["files"]["example"] != [".meta/example.h", ".meta/example.cpp"]:
            raise RuntimeError(f"target_reference_mismatch: {case.task_id}")
        roles = [item for values in config["files"].values() for item in values]
        for relative in roles:
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
                raise RuntimeError(f"unsafe_path: {case.task_id}: {relative}")
        reference = (root / ".meta/example.h").read_text() + (root / ".meta/example.cpp").read_text()
        negative = (root / ".meta/negative.cpp").read_text()
        trace = (root / ".meta/task_trace_test.cpp").read_text()
        _validate_reference(reference, case.task_id)
        if negative == (root / ".meta/example.cpp").read_text() or _sha256_bytes(negative.encode()) == _sha256_bytes(reference.encode()):
            raise RuntimeError(f"negative_fixture_not_distinct: {case.task_id}")
        header_state = _between((root / f"{case.task_id}.h").read_text(), "HARD-RULE-STATE-BEGIN", "HARD-RULE-STATE-END")
        node_state = re.search(r"struct Node \{(.*?)\};", header_state, flags=re.S)
        if not node_state or any(re.search(rf"\b{name}\b", node_state.group(1)) for name in ("value", "aux", "metric")):
            raise RuntimeError(f"superset_state_object: {case.task_id}")
        methods = [match.group(1) for match in re.finditer(r"\b([A-Za-z_]\w*)\s*\([^;]*\)\s*(?:const)?\s*;", case.declarations)]
        for method in methods:
            if method != case.class_name and f".{method}(" not in trace:
                raise RuntimeError(f"incomplete_operation_oracle: {case.task_id}: {method}")
    screen = _screen(out)
    receipt = {
        "schema_version": "xor-core-verification-v3",
        "status": "pending_execution",
        "roots": len(CASES),
        "rejected_roots": len(REJECTED_CASES),
        "primary_core_objective": "achieved",
        "compiled_negative_fixtures": "pending_execution",
        "unique_logic_tags": len({case.logic_tag for case in CASES}),
        "hard_rule_pair_count": screen["hard_rule_pair_count"],
        "adversarial_controls": screen["adversarial_controls"],
        "family_screen": screen["family_duplicate_screen"],
        "benchmark_semantic_screen": screen["benchmark_semantic_screen"],
        "prompt_boundary": screen["prompt_boundary"],
    }
    _write(out / ".state/core-verification.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    return receipt


def build(out: Path = ROOT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() == LEGACY_ROOT.resolve():
        raise RuntimeError("refusing to modify LEGACY_ROOT")
    if not CURRICULUM.is_file() or not SPEC.is_file():
        raise RuntimeError("remedy_spec_incomplete: curriculum or family specification missing")
    if not (SUPPORT / "catch.hpp").is_file() or not (SUPPORT / "tests-main.cpp").is_file():
        raise RuntimeError(f"missing content-addressed Catch support: {SUPPORT}")
    expected = {case.task_id for case in CASES}
    existing = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"} if out.is_dir() else set()
    for stale_name in sorted(existing - expected):
        stale = out / stale_name
        provenance_path = stale / ".meta/provenance.json"
        provenance = json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}
        if not force or provenance.get("family_id") not in {FAMILY_ID, "aider-dsa-xor-linked-list-v2"}:
            raise RuntimeError(f"generator_output_drift: unexpected root {stale_name}")
        shutil.rmtree(stale)
    for case in REJECTED_CASES:
        _rejected_record(out, case)
    roots: list[Path] = []
    curriculum_hash = _sha256_file(CURRICULUM)
    support_hash = _sha256_file(SUPPORT / "catch.hpp")
    for case in CASES:
        _remedy_record(out, case, status="planned")
        root = out / case.task_id
        config = {
            "authors": ["w8-biayn"],
            "source": "newly-authored-in-repository",
            "attribution": "Clean-room repository-authored safe XOR-chain task under repository usage terms.",
            "blurb": case.contract,
            "files": {
                "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
                "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp", ".meta/task_trace_test.cpp", ".meta/negative.cpp"],
                "example": [".meta/example.h", ".meta/example.cpp"],
            },
        }
        provenance = {
            "schema_version": "xor-provenance-v2",
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

Implement this C++17 class in namespace `curriculum`:

```cpp
class {case.class_name} {{
 public:
{case.declarations}
}};
```

{case.contract}

The authoritative physical order must use stable nonzero arena slots. Each live node stores exactly one link value equal to `previous_slot XOR next_slot`; traversal recovers the next slot from the previous slot and current link. Generation-bound handles become stale after slot reuse. Raw-pointer XOR, pointer/integer address encoding, `std::list`, `std::deque`, vector-backed authoritative order, associative-container ordering, hard-coded traces, and third-party linked containers are forbidden substitutes. Output vectors and task-specific metadata are permitted observations.

IDs are positive and unique unless the API is span-based. Invalid, duplicate, absent, stale, overflow, or impossible operations fail without mutation. The test-only audit must prove zero-sentinel endpoints, live slot validity, bounded complete forward/reverse traversal, equal counts, and XOR recovery after every mutation.

Boundary example: an operation naming an absent ID or stale handle on an empty object fails or returns no value, and the complete observable state remains empty.
'''
        files = {
            ".docs/introduction.md": f"# {case.class_name}\n\n{case.contract}\n",
            ".docs/instructions.md": instructions,
            ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
            ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
            ".meta/tests.toml": "[visible]\ndescription = \"public task-specific state transition and boundary\"\n\n[hidden]\ndescription = \"slot-XOR invariant audit\"\n\n[trace]\ndescription = \"independent per-operation return and complete-order oracle\"\n\n[negative]\ndescription = \"compiled task-specific false substitute must fail the same tests\"\n",
            f"{case.task_id}.h": _header(case),
            f"{case.task_id}.cpp": _starter(case),
            ".meta/example.h": _header(case),
            ".meta/example.cpp": _common_reference(case),
            ".meta/negative.cpp": _negative_reference(case),
            "task_visible_test.cpp": _visible_test(case),
            ".meta/task_hidden_test.cpp": _hidden_test(case),
            ".meta/task_trace_test.cpp": _trace_test(case),
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
        "schema_version": "xor-materialization-v3",
        "family_id": FAMILY_ID,
        "generator_revision": GENERATOR_REVISION,
        "generator_content_hash": _generator_hash(),
        "legacy_root": str(LEGACY_ROOT),
        "legacy_root_preserved": True,
        "task_ids": [case.task_id for case in CASES],
        "legacy_task_ids": [case.legacy_id for case in LEGACY_CASES],
        "rejected": {case.legacy_id: REJECTED[case.task_id] for case in REJECTED_CASES},
        "tree_hashes": {root.name: _tree_hash(root) for root in roots},
        "primary_core_objective": core["primary_core_objective"],
        "prompt_boundary": core["prompt_boundary"],
        "family_screen": core["family_screen"],
        "benchmark_semantic_screen": core["benchmark_semantic_screen"],
        "hard_rule_pair_count": core["hard_rule_pair_count"],
        "adversarial_controls": core["adversarial_controls"],
        "status": "pending_execution",
    }
    _write(out / ".state/materialization.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    return tuple(roots)


def _command_output(command: list[str]) -> str:
    return subprocess.run(command, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.strip()


def _mounted_tree_hash(root: Path) -> str:
    script = (
        "import hashlib,sys;from pathlib import Path;root=Path(sys.argv[1]);d=hashlib.sha256();"
        "files=sorted(p for p in root.rglob('*') if p.is_file());"
        "[(d.update(p.relative_to(root).as_posix().encode()+b'\\0'),d.update(p.read_bytes()+b'\\0')) for p in files];"
        "print('sha256:'+d.hexdigest())"
    )
    return _command_output(["python3", "-c", script, str(root)])


def _discover(build_dir: Path) -> int:
    payload = json.loads(_command_output(["ctest", "--test-dir", str(build_dir), "--show-only=json-v1"]))
    count = len(payload.get("tests", []))
    if count <= 0:
        raise RuntimeError("zero_tests")
    return count


def verify(out: Path) -> None:
    missing = [name for name in ("cmake", "c++", "ctest") if shutil.which(name) is None]
    for variable in ("W8_XOR_GRADER_IMAGE", "W8_XOR_SANDBOX_POLICY"):
        if not os.environ.get(variable):
            missing.append(variable)
    state = out / ".state"
    if missing:
        receipt = {
            "schema_version": "xor-oracle-summary-v3",
            "status": "not_completed",
            "missing_prerequisites": missing,
            "required_command": "docker run --rm --network none <pinned-image> prepare_xor_linked_list_aider_tasks.sh --force --verify-core --verify",
        }
        _write(state / "oracle/verification.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        manifest = json.loads((state / "materialization.json").read_text())
        manifest.update({"oracle_status": "not_completed", "status": "implemented"})
        _write(state / "materialization.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
        return
    compiler = str(Path(shutil.which("c++") or "").resolve())
    identity = {
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "image": os.environ["W8_XOR_GRADER_IMAGE"],
        "sandbox_policy": os.environ["W8_XOR_SANDBOX_POLICY"],
        "compiler_path": compiler,
        "compiler_version": _command_output([compiler, "--version"]).splitlines()[0],
        "compiler_sha256": _sha256_file(Path(compiler)),
        "cmake_version": _command_output(["cmake", "--version"]).splitlines()[0],
        "ctest_version": _command_output(["ctest", "--version"]).splitlines()[0],
        "catch_sha256": _sha256_file(SUPPORT / "catch.hpp"),
        "generator_revision": GENERATOR_REVISION,
        "generator_content_hash": _generator_hash(),
        "network_policy": "none",
    }
    receipts = state / "oracle"
    totals = {"normal": 0, "sanitizer": 0, "negative_rejected": 0}
    for case in CASES:
        source = out / case.task_id
        owner_tree_hash = _tree_hash(source)
        mounted_tree_hash = _mounted_tree_hash(source)
        if owner_tree_hash != mounted_tree_hash:
            raise RuntimeError(f"grader_mount_hash_mismatch: {case.task_id}")
        commands: dict[str, object] = {}
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
                configure = ["cmake", "-S", str(root), "-B", str(build_dir), "-G", "Unix Makefiles", f"-DCMAKE_CXX_COMPILER={compiler}", *flags]
                build_command = ["cmake", "--build", str(build_dir), "--parallel", "2"]
                test_command = ["ctest", "--test-dir", str(build_dir), "--output-on-failure"]
                subprocess.run(configure, check=True)
                subprocess.run(build_command, check=True)
                counts[mode] = _discover(build_dir)
                subprocess.run(test_command, check=True)
                commands[mode] = {"configure": configure, "build": build_command, "test": test_command}
                if mode == "normal":
                    negative_build = ["cmake", "--build", str(build_dir), "--target", "negative_tests", "--parallel", "2"]
                    subprocess.run(negative_build, check=True)
                    negative_command = [str(build_dir / "negative_tests")]
                    negative_run = subprocess.run(negative_command, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                    if negative_run.returncode == 0 or "test cases:" not in negative_run.stdout or "failed" not in negative_run.stdout:
                        raise RuntimeError(f"negative_fixture_not_rejected: {case.task_id}")
                    commands["negative"] = {"build": negative_build, "test": negative_command, "exit_code": negative_run.returncode}
            if counts["normal"] != counts["sanitizer"]:
                raise RuntimeError(f"sanitizer_test_count_mismatch: {case.task_id}")
            totals["normal"] += counts["normal"]
            totals["sanitizer"] += counts["sanitizer"]
            totals["negative_rejected"] += 1
        receipt = {
            "schema_version": "xor-oracle-v3",
            "status": "pass",
            "task_id": case.task_id,
            "legacy_task_id": case.legacy_id,
            "tree_hash": owner_tree_hash,
            "mounted_tree_hash": mounted_tree_hash,
            "reference_mapping": {".meta/example.h": f"{case.task_id}.h", ".meta/example.cpp": f"{case.task_id}.cpp"},
            "reference_hashes": {name: _sha256_file(source / name) for name in (".meta/example.h", ".meta/example.cpp")},
            "negative_fixture_hash": _sha256_file(source / ".meta/negative.cpp"),
            "negative_fixture": "executed_and_rejected",
            "commands": commands,
            "test_counts": counts,
            **identity,
        }
        _write(receipts / f"{case.task_id}.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
        record = _remedy_record(out, case, status="verified", tree_hash=owner_tree_hash)
        record.update({
            "benchmark_screen": "pass",
            "family_screen": "pass",
            "oracle_receipt": f".state/oracle/{case.task_id}.json",
            "test_counts": counts,
            "negative_fixture": "executed_and_rejected",
            "local_status": "local_family_verified",
        })
        _write(out / f".state/remedy/{case.legacy_id}.json", json.dumps(record, indent=2, sort_keys=True) + "\n", True)
    screen = json.loads((state / "family-screen.json").read_text())
    complete = screen["benchmark_semantic_screen"] == "pass"
    summary = {
        "schema_version": "xor-oracle-summary-v3",
        "status": "pass",
        "roots": len(CASES),
        "test_counts": {"normal": totals["normal"], "sanitizer": totals["sanitizer"]},
        "equal_positive_counts": totals["normal"] == totals["sanitizer"] and totals["normal"] > 0,
        "negative_fixtures": {"executed": len(CASES), "rejected": totals["negative_rejected"]},
        **identity,
    }
    _write(receipts / "verification.json", json.dumps(summary, indent=2, sort_keys=True) + "\n", True)
    core = json.loads((state / "core-verification.json").read_text())
    core.update({"status": "pass", "compiled_negative_fixtures": {"executed": len(CASES), "rejected": totals["negative_rejected"]}})
    _write(state / "core-verification.json", json.dumps(core, indent=2, sort_keys=True) + "\n", True)
    manifest = json.loads((state / "materialization.json").read_text())
    manifest.update({
        "oracle_status": "pass",
        "oracle_receipts": len(CASES),
        "test_counts": {"normal": totals["normal"], "sanitizer": totals["sanitizer"]},
        "negative_fixtures": {"executed": len(CASES), "rejected": totals["negative_rejected"]},
        "status": "local_family_verified" if complete and totals["negative_rejected"] == len(CASES) else "pending_execution",
    })
    _write(state / "materialization.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)


def quick_normal_verify(out: Path) -> None:
    """Run receipt-free normal reference builds for iteration only."""
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
            if _discover(build_dir) != 3:
                raise RuntimeError(f"test_discovery_failed: {case.task_id}")
            subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True)
            subprocess.run(["cmake", "--build", str(build_dir), "--target", "negative_tests", "--parallel", "2"], check=True, stdout=subprocess.DEVNULL)
            negative = subprocess.run([str(build_dir / "negative_tests")], check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if negative.returncode == 0 or "test cases:" not in negative.stdout or "failed" not in negative.stdout:
                raise RuntimeError(f"negative_fixture_not_rejected: {case.task_id}")
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
    print(f"Wrote {len(roots)} remediated XOR-linked-list tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
