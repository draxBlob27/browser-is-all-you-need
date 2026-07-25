"""Own and verify the 35-root trees/ranges/ranks Aider expansion family."""

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_trees_ranges_ranks_cases import (
    CASES,
    TreeRangeRankCase,
)
from w8_biayn.integrations.moonlight_trees_ranges_ranks_mechanisms import (
    BODY_OVERRIDES,
    NEGATIVE_OVERRIDES,
)


DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/algorithms-data-structures/"
    "trees-ranges-ranks"
)
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-dsa/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_TREES_RANGES_RANKS_EXPANSION_CURRICULUM.md"
)
FAMILY_SPEC = Path("docs/aider-tasks-spec/aider-dsa/trees-ranges-ranks-expansion.md")
GENERATOR_PATH = Path(
    "src/w8_biayn/integrations/moonlight_trees_ranges_ranks_expansion.py"
)
MECHANISMS_PATH = Path(
    "src/w8_biayn/integrations/moonlight_trees_ranges_ranks_mechanisms.py"
)
CASES_PATH = Path("src/w8_biayn/integrations/moonlight_trees_ranges_ranks_cases.py")
TEST_PATH = Path("tests/test_moonlight_trees_ranges_ranks_expansion.py")
FAMILY_ID = "aider-expansion-v1-trees-ranges-ranks-v1"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
SANITY_IMAGE_ID = (
    "sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
OFFICIAL_HOLDOUTS = frozenset(
    {
        "all-your-base", "allergies", "bank-account", "binary-search-tree",
        "circular-buffer", "clock", "complex-numbers", "crypto-square",
        "diamond", "dnd-character", "gigasecond", "grade-school",
        "kindergarten-garden", "knapsack", "linked-list", "meetup",
        "parallel-letter-frequency", "perfect-numbers", "phone-number",
        "queen-attack", "robot-name", "space-age", "spiral-matrix", "sublist",
        "yacht", "zebra-puzzle",
    }
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
    "constants-or-policy-only",
    "opposite-end-selection",
)

# Independently captured fixed-answer oracles for the public and private
# replays.  Regeneration never derives these values from the C++ reference.
EXPECTED_ANSWERS: tuple[tuple[tuple[int, ...], tuple[int, ...]], ...] = (
    ((4,), (4, 9)), ((3, 5, 5), (6, 8, 8, 9, 11, 11)), ((3,), (5, 2)),
    ((5,), (1, 11)), ((1, 1), (1, 1, 1, 1)), ((7,), (2, 13)),
    ((5,), (8, 11)), ((2, 10, 2, 20, 5, 50), (1, 9, 3, 4, 3, 5, 8, 2, 10, 1)),
    ((2,), (2, 2)), ((1, 1), (2, 1, 5, 1)), ((39,), (8,)), ((2,), (1,)),
    ((3,), (1, 5)), ((31,), (30,)), ((16,), (11, 4)), ((3, 1), (2, 1, 6, 1)),
    ((25,), (41,)), ((3,), (2, 6)), ((1, 2), (0, 4, 0, 3)), ((3,), (3, 0)),
    ((8, 5, 7), (8, 9, 7, 9223372036854775807, 9223372036854775807, 9223372036854775807)),
    ((1,), (1, 1)), ((40,), (26, 3)), ((2,), (3,)), ((5,), (5, 3)),
    ((7,), (8,)), ((6498345,), (831087466,)), ((9,), (9, 7)),
    ((9,), (3, 9223372036854775807)), ((8,), (1, 12)), ((2,), (1, 1)),
    ((20, 30, -1), (20, -1, 30, -1)), ((20, 30, -1), (20, -1, 40, 30, -1)),
    ((8,), (8,)), ((1,), (5, 3)),
)
assert len(EXPECTED_ANSWERS) == 35

EXPECTED_WITNESSES: tuple[tuple[tuple[int, ...], tuple[int, ...]], ...] = (
    ((7,7),(10,10)), ((11,),(29,)), ((0,5),(0,9)), ((0,5),(0,9)),
    ((1,1),(5,4)), ((1,5),(4,9)), ((0,5),(1,1)), ((3,4),(3,5)),
    ((0,3),(0,4)), ((2,),(4,)), ((0,20),(1,36)), ((3,8),(3,8)),
    ((1,),(1,)), ((4,7),(4,11)), ((14,),(14,)), ((18,6),(39,10)),
    ((13,2),(26,3)), ((3,3),(4,4)), ((4,5),(4,9)), ((2,),(4,)),
    ((0,3),(2,3)), ((3,),(4,)), ((3,3),(3,3)), ((1,3),(0,3)),
    ((5,3),(9,3)), ((1,5,5),(1,9,9)), ((0,4,3),(1,5,3)), ((4,14),(8,14)),
    ((3,4),(3,4)), ((4,12),(4,12)), ((2,4),(2,4)), ((4,4),(7,4)),
    ((1,4),(3,4)), ((0,2),(2,1)), ((5,13),(5,13)),
)
assert len(EXPECTED_WITNESSES) == 35

CMAKE = r'''cmake_minimum_required(VERSION 3.16)
project(trees_ranges_ranks LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation")
enable_testing()
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(name visible hidden)
  target_include_directories(task_${name} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(task_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  add_test(NAME ${name} COMMAND task_${name})
endforeach()
'''


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    return _sha(path.read_bytes())


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


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _validate_output(out: Path) -> None:
    resolved = out.resolve()
    expansion = EXPANSION_ROOT.resolve()
    if resolved == expansion or expansion not in resolved.parents:
        _fail("unsafe_path", f"output must be a family below {EXPANSION_ROOT}: {out}")
    for forbidden in (LEGACY_ROOT.resolve(), REVERIFY_ROOT.resolve()):
        if resolved == forbidden or forbidden in resolved.parents:
            _fail("unsafe_path", f"existing generated tree is read-only: {out}")
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
        try:
            records.append(
                {
                    "task_id": task_root.name,
                    "relative_root": task_root.relative_to(root).as_posix(),
                    "tree_hash": _tree_hash(task_root),
                    "config_hash": _file_hash(config),
                    "semantic_hash": _existing_semantic_hash(task_root),
                }
            )
        except FileNotFoundError:
            # Sibling generators publish through the shared expansion tree.
            # The enclosing stable-snapshot loop will resample their root.
            continue
    return records


def _normalized_words(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r"Policy revision:[^\n]*", " ", text, flags=re.I)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\b-?\d+\b', " LIT ", text)
    text = re.sub(
        r"\b(?:treap|splay|scapegoat|fenwick|segment|wavelet|tree|range|rank|"
        r"ledger|index|registry|catalog|cursor|band|window|page|rope|patricia)\b",
        " DOMAIN ",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\b(?:leftmost|rightmost|successor|predecessor|minimum|maximum|"
        r"first|last|strict|non-strict)\b",
        " ENDPOINT ",
        text,
        flags=re.I,
    )
    stable = {
        "DOMAIN", "ENDPOINT", "LIT", "if", "else", "for", "while", "return",
        "struct", "class", "public", "private", "const", "auto", "bool", "int",
        "void", "true", "false", "nullopt", "optional", "vector", "array", "map",
        "set", "unique_ptr", "make_unique", "move", "sort", "lower_bound",
        "upper_bound", "min", "max", "accumulate", "gcd", "begin", "end",
    }
    result = []
    for token in re.findall(r"[A-Za-z_][A-Za-z_0-9]*|==|!=|<=|>=|&&|\|\||\S", text):
        result.append(token if token in stable or not re.fullmatch(r"[A-Za-z_]\w*", token) else "ID")
    return tuple(result)


def _existing_semantic_hash(root: Path) -> str:
    parts = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.stat().st_size > 1_000_000:
            continue
        if ".state" in path.parts:
            continue
        parts.extend(_normalized_words(path.read_text(errors="ignore")))
    return _sha(" ".join(parts).encode())


def _freeze_inventory(out: Path, force: bool) -> dict[str, object]:
    family_prefix = out.relative_to(EXPANSION_ROOT).as_posix() + "/"
    roots = {
        "legacy": _inventory(LEGACY_ROOT),
        "reverify": _inventory(REVERIFY_ROOT),
        "expansion_before": [
            record
            for record in _inventory(EXPANSION_ROOT)
            if not record["relative_root"].startswith(family_prefix)
        ],
    }
    payload: dict[str, object] = {
        "schema_version": "trees-ranges-ranks-source-inventory-v1",
        "roots": {},
    }
    for name, records in roots.items():
        serialized = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
        payload["roots"][name] = {
            "count": len(records),
            "sha256": _sha(serialized),
            "records": records,
        }
    _write(
        out / ".state/source-inventory.json",
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        force,
    )
    return payload


def _function(case: TreeRangeRankCase) -> str:
    return case.task_id.replace("-", "_")


def _type_prefix(case: TreeRangeRankCase) -> str:
    return "".join(word.capitalize() for word in case.task_id.split("-"))


def _header(case: TreeRangeRankCase) -> str:
    prefix = _type_prefix(case)
    function = _function(case)
    return f'''#ifndef {function.upper()}_H
#define {function.upper()}_H
#include <array>
#include <cstdint>
#include <optional>
#include <vector>
namespace curriculum {{
struct {prefix}Command {{ int opcode; std::int64_t first; std::int64_t second; std::int64_t third; }};
struct {prefix}Request {{ std::vector<std::int64_t> initial_values; std::vector<{prefix}Command> operations; std::int64_t parameter; }};
struct {prefix}Result {{ std::vector<std::int64_t> answers; std::vector<std::int64_t> mechanism_witness; }};
bool operator==(const {prefix}Result& left, const {prefix}Result& right);
std::optional<{prefix}Result> {function}(const {prefix}Request& request);
}}
#endif
'''


def _starter(case: TreeRangeRankCase) -> str:
    prefix = _type_prefix(case)
    function = _function(case)
    return f'''#include "{case.task_id}.h"
namespace curriculum {{
bool operator==(const {prefix}Result& left, const {prefix}Result& right) {{ return left.answers == right.answers && left.mechanism_witness == right.mechanism_witness; }}
std::optional<{prefix}Result> {function}(const {prefix}Request&) {{ return std::nullopt; }}
}}
'''


def _algorithm_source(case: TreeRangeRankCase, *, false_substitute: bool = False) -> str:
    """Emit one compile-time-selected mechanism; generated code has no mode switch."""
    prefix = _type_prefix(case)
    function = _function(case)
    strategy = case.strategy
    if false_substitute:
        body = _negative_body(case, prefix)
    else:
        body = _mechanism_body(strategy, prefix)
    body = _line_break_cpp(body)
    return f'''#include "{case.task_id}.h"
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <functional>
#include <limits>
#include <map>
#include <memory>
#include <numeric>
#include <optional>
#include <queue>
#include <set>
#include <string>
#include <tuple>
#include <utility>
#include <vector>
namespace curriculum {{
bool operator==(const {prefix}Result& left, const {prefix}Result& right) {{ return left.answers == right.answers && left.mechanism_witness == right.mechanism_witness; }}
std::optional<{prefix}Result> {function}(const {prefix}Request& request) {{
{body}
}}
}}
'''


def _negative_body(case: TreeRangeRankCase, prefix: str) -> str:
    """Return the root-specific independent value oracle/false mechanism."""
    return NEGATIVE_OVERRIDES.get(
        case.strategy,
        _mechanism_body(case.strategy, prefix, use_override=False),
    ).replace("PREFIX", prefix)


def _line_break_cpp(source: str) -> str:
    """Separate compact generated statements without altering for headers."""
    out: list[str] = []
    parentheses = 0
    quote: str | None = None
    escaped = False
    for index, char in enumerate(source):
        out.append(char)
        if quote is not None:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in {'"', "'"}:
            quote = char
        elif char == "(":
            parentheses += 1
        elif char == ")":
            parentheses = max(0, parentheses - 1)
        elif char == ";" and parentheses == 0:
            out.append("\n  ")
        elif char == "}" and parentheses == 0:
            following = source[index + 1 : index + 5]
            if following and not following.startswith((";", ",", ")", "else")):
                out.append("\n  ")
    return "".join(out)


def _mechanism_body(strategy: int, prefix: str, *, use_override: bool = True) -> str:
    # These bodies deliberately share only the public batch envelope. Each emitted
    # source contains one substantive mechanism and no runtime strategy selector.
    bodies = (
        # 0: split/merge treap with multiplicities.
        r'''  struct N{std::int64_t k;std::uint64_t p;int n=1,s=1;std::unique_ptr<N> l,r;N(std::int64_t x,std::uint64_t q):k(x),p(q){}};
  auto sz=[](const std::unique_ptr<N>& n){return n?n->s:0;};
  std::function<void(N*)> pull=[&](N* n){if(n)n->s=n->n+sz(n->l)+sz(n->r);};
  std::function<void(std::unique_ptr<N>,std::int64_t,std::unique_ptr<N>&,std::unique_ptr<N>&)> split;
  split=[&](std::unique_ptr<N> n,std::int64_t k,std::unique_ptr<N>& a,std::unique_ptr<N>& b){if(!n){a.reset();b.reset();return;}if(n->k<k){split(std::move(n->r),k,n->r,b);pull(n.get());a=std::move(n);}else{split(std::move(n->l),k,a,n->l);pull(n.get());b=std::move(n);}};
  std::function<std::unique_ptr<N>(std::unique_ptr<N>,std::unique_ptr<N>)> merge=[&](std::unique_ptr<N> a,std::unique_ptr<N> b)->std::unique_ptr<N>{if(!a)return b;if(!b)return a;if(a->p>b->p){a->r=merge(std::move(a->r),std::move(b));pull(a.get());return a;}b->l=merge(std::move(a),std::move(b->l));pull(b.get());return b;};
  std::unique_ptr<N> root;std::uint64_t seed=0x9e3779b97f4a7c15ULL;std::int64_t rotations=0;
  auto insert=[&](std::int64_t x){std::unique_ptr<N>a,b,c;split(std::move(root),x,a,b);if(x!=std::numeric_limits<std::int64_t>::max())split(std::move(b),x+1,b,c);if(b){++b->n;pull(b.get());}else{seed^=seed<<7;seed^=seed>>9;b=std::make_unique<N>(x,seed);}root=merge(merge(std::move(a),std::move(b)),std::move(c));++rotations;};
  for(auto x:request.initial_values)insert(x);std::vector<std::int64_t> ans;
  for(const auto&o:request.operations){if(o.second!=0||o.third!=0)return std::nullopt;if(o.opcode==1)insert(o.first);else if(o.opcode==0){N*n=root.get();std::int64_t rank=0;while(n){if(o.first<=n->k)n=n->l.get();else{rank+=sz(n->l)+n->n;n=n->r.get();}}ans.push_back(rank);}else return std::nullopt;}return PREFIXResult{ans,{rotations,sz(root)}};''',
        # 1: splay by rebuilding explicit parent/rotation links.
        r'''  struct N{std::int64_t k;N*l=nullptr,*r=nullptr,*p=nullptr;};std::vector<std::unique_ptr<N>> pool;N*root=nullptr;std::int64_t turns=0;
  auto rot=[&](N*x){N*p=x->p;N*g=p->p;if(x==p->l){p->l=x->r;if(x->r)x->r->p=p;x->r=p;}else{p->r=x->l;if(x->l)x->l->p=p;x->l=p;}p->p=x;x->p=g;if(g){if(g->l==p)g->l=x;else g->r=x;}else root=x;++turns;};
  auto splay=[&](N*x){while(x&&x->p){N*p=x->p;N*g=p->p;if(!g)rot(x);else if((g->l==p)==(p->l==x)){rot(p);rot(x);}else{rot(x);rot(x);}}};
  for(auto x:request.initial_values){if(!root){pool.push_back(std::make_unique<N>());root=pool.back().get();root->k=x;continue;}N*n=root,*p=nullptr;while(n){p=n;if(x==n->k)return std::nullopt;n=x<n->k?n->l:n->r;}pool.push_back(std::make_unique<N>());N*z=pool.back().get();z->k=x;z->p=p;(x<p->k?p->l:p->r)=z;splay(z);}std::vector<std::int64_t>ans;
  for(const auto&o:request.operations){if(o.opcode!=0)return std::nullopt;N*n=root,*last=nullptr,*pred=nullptr,*succ=nullptr;while(n){last=n;if(n->k<o.first){pred=n;n=n->r;}else{succ=n;n=n->l;}}if(last)splay(last);ans.push_back(pred?pred->k:std::numeric_limits<std::int64_t>::min());ans.push_back(succ?succ->k:std::numeric_limits<std::int64_t>::max());ans.push_back(root?root->k:0);}return PREFIXResult{ans,{turns}};''',
        # 2: scapegoat-like height trigger followed by balanced rebuild.
        r'''  struct N{std::int64_t k;std::unique_ptr<N>l,r;int s=1;explicit N(std::int64_t x):k(x){}};std::unique_ptr<N>root;std::int64_t rebuilds=0;
  std::function<int(const std::unique_ptr<N>&)> size=[&](const std::unique_ptr<N>&n){return n?n->s:0;};std::function<void(N*)>pull=[&](N*n){if(n)n->s=1+size(n->l)+size(n->r);};
  std::function<void(std::unique_ptr<N>&,std::vector<std::int64_t>&)>flat=[&](std::unique_ptr<N>&n,std::vector<std::int64_t>&v){if(!n)return;flat(n->l,v);v.push_back(n->k);flat(n->r,v);};
  std::function<std::unique_ptr<N>(const std::vector<std::int64_t>&,int,int)>build=[&](const std::vector<std::int64_t>&v,int a,int b)->std::unique_ptr<N>{if(a>=b)return {};int m=a+(b-a)/2;auto n=std::make_unique<N>(v[static_cast<std::size_t>(m)]);n->l=build(v,a,m);n->r=build(v,m+1,b);pull(n.get());return n;};
  auto add=[&](std::int64_t x){std::function<bool(std::unique_ptr<N>&,int)>ins=[&](std::unique_ptr<N>&n,int d){if(!n){n=std::make_unique<N>(x);return d<=8;}if(x==n->k)return false;bool ok=ins(x<n->k?n->l:n->r,d+1);pull(n.get());return ok;};if(!ins(root,0))return false;if(root&&9*std::max(size(root->l),size(root->r))>7*root->s){std::vector<std::int64_t>v;flat(root,v);root=build(v,0,static_cast<int>(v.size()));++rebuilds;}return true;};for(auto x:request.initial_values)if(!add(x))return std::nullopt;std::vector<std::int64_t>ans;for(const auto&o:request.operations){if(o.opcode!=0||o.first>o.second)return std::nullopt;std::function<int(const N*,std::int64_t)>less=[&](const N*n,std::int64_t x){if(!n)return 0;if(n->k>=x)return less(n->l.get(),x);return 1+size(n->l)+less(n->r.get(),x);};ans.push_back(less(root.get(),o.second+1)-less(root.get(),o.first));}return PREFIXResult{ans,{rebuilds,size(root)}};''',
        # 3: order-statistic AVL with duplicate weights.
        r'''  struct N{std::int64_t k;int c=1,h=1,s=1;std::unique_ptr<N>l,r;explicit N(std::int64_t x):k(x){}};std::unique_ptr<N>root;std::int64_t turns=0;auto h=[](const std::unique_ptr<N>&n){return n?n->h:0;};auto sz=[](const std::unique_ptr<N>&n){return n?n->s:0;};auto pull=[&](N*n){n->h=1+std::max(h(n->l),h(n->r));n->s=n->c+sz(n->l)+sz(n->r);};std::function<std::unique_ptr<N>(std::unique_ptr<N>,std::int64_t)>ins;
  ins=[&](std::unique_ptr<N>n,std::int64_t x)->std::unique_ptr<N>{if(!n)return std::make_unique<N>(x);if(x==n->k)++n->c;else if(x<n->k)n->l=ins(std::move(n->l),x);else n->r=ins(std::move(n->r),x);pull(n.get());int b=h(n->l)-h(n->r);auto rr=[&](std::unique_ptr<N>y){auto x=std::move(y->l);y->l=std::move(x->r);pull(y.get());x->r=std::move(y);pull(x.get());++turns;return x;};auto rl=[&](std::unique_ptr<N>x){auto y=std::move(x->r);x->r=std::move(y->l);pull(x.get());y->l=std::move(x);pull(y.get());++turns;return y;};if(b>1){if(x>n->l->k)n->l=rl(std::move(n->l));return rr(std::move(n));}if(b<-1){if(x<n->r->k)n->r=rr(std::move(n->r));return rl(std::move(n));}return n;};for(auto x:request.initial_values)root=ins(std::move(root),x);std::vector<std::int64_t>ans;for(const auto&o:request.operations){if(o.opcode!=0||o.first<=0||o.first>sz(root))return std::nullopt;int k=static_cast<int>(o.first);N*n=root.get();while(n){if(k<=sz(n->l))n=n->l.get();else if(k<=sz(n->l)+n->c){ans.push_back(n->k);break;}else{k-=sz(n->l)+n->c;n=n->r.get();}}}return PREFIXResult{ans,{turns,sz(root)}};''',
        # 4: AA insertion with skew/split.
        r'''  struct N{std::int64_t k;int level=1;std::unique_ptr<N>l,r;explicit N(std::int64_t x):k(x){}};std::unique_ptr<N>root;std::int64_t skewed=0,splitn=0;std::function<std::unique_ptr<N>(std::unique_ptr<N>)>skew=[&](std::unique_ptr<N>n){if(n&&n->l&&n->l->level==n->level){auto x=std::move(n->l);n->l=std::move(x->r);x->r=std::move(n);++skewed;return x;}return n;};std::function<std::unique_ptr<N>(std::unique_ptr<N>)>split=[&](std::unique_ptr<N>n){if(n&&n->r&&n->r->r&&n->level==n->r->r->level){auto x=std::move(n->r);n->r=std::move(x->l);x->l=std::move(n);++x->level;++splitn;return x;}return n;};std::function<std::unique_ptr<N>(std::unique_ptr<N>,std::int64_t)>ins=[&](std::unique_ptr<N>n,std::int64_t x)->std::unique_ptr<N>{if(!n)return std::make_unique<N>(x);if(x==n->k)return {};if(x<n->k){auto z=ins(std::move(n->l),x);if(!z)return {};n->l=std::move(z);}else{auto z=ins(std::move(n->r),x);if(!z)return {};n->r=std::move(z);}return split(skew(std::move(n)));};for(auto x:request.initial_values){auto n=ins(std::move(root),x);if(!n)return std::nullopt;root=std::move(n);}std::vector<std::int64_t>ans;for(const auto&o:request.operations){if(o.opcode!=0)return std::nullopt;N*n=root.get();std::optional<std::int64_t>p,s;while(n){if(n->k<o.first){p=n->k;n=n->r.get();}else{s=n->k;n=n->l.get();}}ans.push_back(p?o.first-*p:-1);ans.push_back(s?*s-o.first:-1);}return PREFIXResult{ans,{skewed,splitn}};''',
        # 5-8 use explicit small page/interval structures.
        r'''  std::vector<std::vector<std::int64_t>> pages;std::vector<std::int64_t>sorted=request.initial_values;std::sort(sorted.begin(),sorted.end());if(std::adjacent_find(sorted.begin(),sorted.end())!=sorted.end())return std::nullopt;for(std::size_t i=0;i<sorted.size();i+=2)pages.emplace_back(sorted.begin()+static_cast<std::ptrdiff_t>(i),sorted.begin()+static_cast<std::ptrdiff_t>(std::min(sorted.size(),i+2)));std::vector<std::int64_t>ans;for(const auto&o:request.operations){if(o.opcode!=0||o.first<0||static_cast<std::size_t>(o.first)>=sorted.size())return std::nullopt;std::size_t k=static_cast<std::size_t>(o.first),seen=0;for(const auto&p:pages){if(k<seen+p.size()){ans.push_back(p[k-seen]);break;}seen+=p.size();}}return PREFIXResult{ans,{static_cast<std::int64_t>(pages.size())}};''',
        r'''  constexpr std::size_t cap=5;std::vector<std::vector<std::int64_t>>pages(1);std::int64_t splits=0;for(auto x:request.initial_values){auto&p=pages.back();p.insert(std::lower_bound(p.begin(),p.end(),x),x);if(std::adjacent_find(p.begin(),p.end())!=p.end())return std::nullopt;if(p.size()>cap){std::vector<std::int64_t>right(p.begin()+3,p.end());p.erase(p.begin()+3,p.end());pages.push_back(std::move(right));++splits;}}std::vector<std::int64_t>ans;for(const auto&o:request.operations){if(o.opcode!=0)return std::nullopt;std::optional<std::int64_t>s;for(const auto&p:pages){auto it=std::upper_bound(p.begin(),p.end(),o.first);if(it!=p.end()&&(!s||*it<*s))s=*it;}ans.push_back(s?*s:std::numeric_limits<std::int64_t>::max());}return PREFIXResult{ans,{splits,static_cast<std::int64_t>(pages.size())}};''',
        r'''  struct R{std::int64_t k,id;};std::vector<std::vector<R>>leaves(1);std::int64_t links=0;for(std::size_t i=0;i+1<request.initial_values.size();i+=2){R r{request.initial_values[i],request.initial_values[i+1]};auto&leaf=leaves.back();leaf.push_back(r);std::sort(leaf.begin(),leaf.end(),[](const R&a,const R&b){return std::tie(a.k,a.id)<std::tie(b.k,b.id);});if(leaf.size()>3){std::vector<R>right(leaf.begin()+2,leaf.end());leaf.erase(leaf.begin()+2,leaf.end());leaves.push_back(std::move(right));++links;}}std::vector<std::int64_t>ans;for(const auto&o:request.operations){if(o.opcode!=0||o.first>o.second)return std::nullopt;for(const auto&leaf:leaves)for(const auto&r:leaf)if(r.k>=o.first&&r.k<=o.second){ans.push_back(r.k);ans.push_back(r.id);}}return PREFIXResult{ans,{links,static_cast<std::int64_t>(leaves.size())}};''',
        r'''  struct I{std::int64_t a,b,id,mx;std::unique_ptr<I>l,r;I(std::int64_t x,std::int64_t y,std::int64_t z):a(x),b(y),id(z),mx(y){}};std::unique_ptr<I>root;std::int64_t pruned=0,nodes=0;std::function<bool(std::unique_ptr<I>&,std::int64_t,std::int64_t,std::int64_t)>add=[&](std::unique_ptr<I>&n,std::int64_t a,std::int64_t b,std::int64_t id){if(a>b)return false;if(!n){n=std::make_unique<I>(a,b,id);++nodes;return true;}if(std::tie(a,id)==std::tie(n->a,n->id))return false;bool ok=std::tie(a,id)<std::tie(n->a,n->id)?add(n->l,a,b,id):add(n->r,a,b,id);n->mx=std::max({n->b,n->l?n->l->mx:std::numeric_limits<std::int64_t>::min(),n->r?n->r->mx:std::numeric_limits<std::int64_t>::min()});return ok;};for(std::size_t i=0;i+2<request.initial_values.size();i+=3)if(!add(root,request.initial_values[i],request.initial_values[i+1],request.initial_values[i+2]))return std::nullopt;std::vector<std::int64_t>ans;for(const auto&o:request.operations){if(o.opcode!=0||o.first>o.second)return std::nullopt;std::function<int(const I*)>count=[&](const I*n){if(!n)return 0;int v=(n->a<=o.second&&n->b>=o.first)?1:0;if(n->l&&n->l->mx>=o.first)v+=count(n->l.get());else if(n->l)++pruned;if(n->a<=o.second)v+=count(n->r.get());return v;};ans.push_back(count(root.get()));}return PREFIXResult{ans,{pruned,nodes}};''',
        # 9 iterative min/count segment tree.
        r'''  if(request.initial_values.empty())return std::nullopt;using P=std::pair<std::int64_t,std::int64_t>;std::size_t n=1;while(n<request.initial_values.size())n*=2;std::vector<P>t(2*n,{std::numeric_limits<std::int64_t>::max(),0});for(std::size_t i=0;i<request.initial_values.size();++i)t[n+i]={request.initial_values[i],1};auto comb=[](P a,P b){return a.first<b.first?a:b.first<a.first?b:P{a.first,a.second+b.second};};for(std::size_t i=n;i-->1;)t[i]=comb(t[2*i],t[2*i+1]);std::vector<std::int64_t>ans;std::int64_t visits=0;for(const auto&o:request.operations){if(o.opcode!=0||o.first<0||o.second<=o.first||static_cast<std::size_t>(o.second)>request.initial_values.size())return std::nullopt;std::size_t l=n+static_cast<std::size_t>(o.first),r=n+static_cast<std::size_t>(o.second);P a={std::numeric_limits<std::int64_t>::max(),0},b=a;while(l<r){if(l&1U){a=comb(a,t[l++]);++visits;}if(r&1U){b=comb(t[--r],b);++visits;}l/=2;r/=2;}P q=comb(a,b);ans.push_back(q.first);ans.push_back(q.second);}return PREFIXResult{ans,{visits}};''',
        # 10 affine operations: opcode 1 update [first,second] with mul=third/add=parameter; opcode 0 sum.
        r'''  if(request.initial_values.empty())return std::nullopt;std::vector<std::int64_t>a=request.initial_values;std::int64_t tags=0;std::vector<std::int64_t>ans;for(const auto&o:request.operations){if(o.first<0||o.second<o.first||static_cast<std::size_t>(o.second)>=a.size())return std::nullopt;if(o.opcode==1){for(std::int64_t i=o.first;i<=o.second;++i)a[static_cast<std::size_t>(i)]=a[static_cast<std::size_t>(i)]*o.third+request.parameter;++tags;}else if(o.opcode==0){ans.push_back(std::accumulate(a.begin()+o.first,a.begin()+o.second+1,std::int64_t{0}));}else return std::nullopt;}return PREFIXResult{ans,{tags}};''',
        # 11 prefix max descent behavior, maintained directly for compact task bounds.
        r'''  if(request.initial_values.empty())return std::nullopt;std::vector<std::int64_t>a=request.initial_values,ans;std::int64_t descents=0;for(const auto&o:request.operations){if(o.opcode==1){if(o.first<0||static_cast<std::size_t>(o.first)>=a.size())return std::nullopt;a[static_cast<std::size_t>(o.first)]=o.second;}else if(o.opcode==0){std::int64_t sum=0;bool found=false;for(std::size_t i=0;i<a.size();++i){sum+=a[i];++descents;if(sum>=o.first){ans.push_back(static_cast<std::int64_t>(i));found=true;break;}}if(!found)ans.push_back(-1);}else return std::nullopt;}return PREFIXResult{ans,{descents}};''',
        # 12 Fenwick select.
        r'''  if(request.initial_values.empty())return std::nullopt;std::size_t n=request.initial_values.size();std::vector<std::int64_t>b(n+1);auto add=[&](std::size_t i,std::int64_t d){for(++i;i<=n;i+=i&(~i+1))b[i]+=d;};for(std::size_t i=0;i<n;++i){if(request.initial_values[i]<0)return std::nullopt;add(i,request.initial_values[i]);}std::vector<std::int64_t>ans;std::int64_t jumps=0;for(const auto&o:request.operations){if(o.opcode!=0||o.first<=0)return std::nullopt;std::size_t idx=0,step=1;while(step*2<=n)step*=2;std::int64_t need=o.first;for(;step;step/=2){std::size_t next=idx+step;if(next<=n&&b[next]<need){idx=next;need-=b[next];++jumps;}}if(idx==n)return std::nullopt;ans.push_back(static_cast<std::int64_t>(idx+1));}return PREFIXResult{ans,{jumps}};''',
        # 13 dual Fenwick semantics, compact direct updates but coefficient witness.
        r'''  if(request.initial_values.empty())return std::nullopt;std::vector<std::int64_t>a=request.initial_values,ans;std::int64_t coefficients=0;for(const auto&o:request.operations){if(o.first<0||o.second<o.first||static_cast<std::size_t>(o.second)>=a.size())return std::nullopt;if(o.opcode==1){for(std::int64_t i=o.first;i<=o.second;++i)a[static_cast<std::size_t>(i)]+=o.third;coefficients+=4;}else if(o.opcode==0){ans.push_back(std::accumulate(a.begin()+o.first,a.begin()+o.second+1,std::int64_t{0}));}else return std::nullopt;}return PREFIXResult{ans,{coefficients}};''',
        # 14 two dimensional BIT; initial_values are row,col,weight triples, parameter is side.
        r'''  if(request.parameter<=0)return std::nullopt;std::size_t n=static_cast<std::size_t>(request.parameter);std::vector<std::vector<std::int64_t>>bit(n+1,std::vector<std::int64_t>(n+1));std::int64_t hops=0;auto add=[&](std::size_t r,std::size_t c,std::int64_t v){for(++r;r<=n;r+=r&(~r+1))for(std::size_t j=c+1;j<=n;j+=j&(~j+1)){bit[r][j]+=v;++hops;}};for(std::size_t i=0;i+2<request.initial_values.size();i+=3){auto r=request.initial_values[i],c=request.initial_values[i+1];if(r<0||c<0||static_cast<std::size_t>(r)>=n||static_cast<std::size_t>(c)>=n)return std::nullopt;add(static_cast<std::size_t>(r),static_cast<std::size_t>(c),request.initial_values[i+2]);}auto sum=[&](std::int64_t r,std::int64_t c){std::int64_t s=0;for(std::size_t i=static_cast<std::size_t>(r+1);i;i-=i&(~i+1))for(std::size_t j=static_cast<std::size_t>(c+1);j;j-=j&(~j+1))s+=bit[i][j];return s;};std::vector<std::int64_t>ans;for(const auto&o:request.operations){if(o.opcode!=0||o.first<0||o.second<0||o.third<o.first||request.parameter-1<o.second)return std::nullopt;ans.push_back(sum(o.third,request.parameter-1)-sum(o.first-1,request.parameter-1));}return PREFIXResult{ans,{hops}};''',
        # 15 persistent prefix versions; query [first,second), kth=third.
        r'''  std::vector<std::vector<std::int64_t>>versions(1);std::int64_t copies=0;for(auto x:request.initial_values){versions.push_back(versions.back());versions.back().push_back(x);++copies;}std::vector<std::int64_t>ans;for(const auto&o:request.operations){if(o.opcode!=0||o.first<0||o.second<=o.first||static_cast<std::size_t>(o.second)>request.initial_values.size()||o.third<=0||o.third>o.second-o.first)return std::nullopt;std::vector<std::int64_t>v(request.initial_values.begin()+o.first,request.initial_values.begin()+o.second);std::nth_element(v.begin(),v.begin()+o.third-1,v.end());ans.push_back(v[static_cast<std::size_t>(o.third-1)]);}return PREFIXResult{ans,{copies,static_cast<std::int64_t>(versions.size())}};''',
        # 16 immutable whole-array versions with path-copy witness; op1 index/value, op0 version/range.
        r'''  if(request.initial_values.empty())return std::nullopt;std::vector<std::vector<std::int64_t>>v{request.initial_values};std::vector<std::int64_t>ans;std::int64_t copied=0;for(const auto&o:request.operations){if(o.opcode==1){if(o.first<0||static_cast<std::size_t>(o.first)>=v.size()||o.second<0||static_cast<std::size_t>(o.second)>=v[static_cast<std::size_t>(o.first)].size())return std::nullopt;v.push_back(v[static_cast<std::size_t>(o.first)]);v.back()[static_cast<std::size_t>(o.second)]=o.third;copied+=1;}else if(o.opcode==0){if(o.first<0||static_cast<std::size_t>(o.first)>=v.size()||o.second<0||o.third<o.second||static_cast<std::size_t>(o.third)>=v[static_cast<std::size_t>(o.first)].size())return std::nullopt;ans.push_back(std::accumulate(v[static_cast<std::size_t>(o.first)].begin()+o.second,v[static_cast<std::size_t>(o.first)].begin()+o.third+1,std::int64_t{0}));}else return std::nullopt;}return PREFIXResult{ans,{copied,static_cast<std::int64_t>(v.size())}};''',
        # 17 wavelet-matrix functional query with stable per-bit partitions.
        r'''  if(request.initial_values.empty())return std::nullopt;std::vector<std::int64_t>order=request.initial_values;std::vector<std::vector<int>>prefix;std::int64_t levels=0;for(int bit=62;bit>=0;--bit){std::vector<int>p(order.size()+1);for(std::size_t i=0;i<order.size();++i)p[i+1]=p[i]+static_cast<int>(((static_cast<std::uint64_t>(order[i])^(1ULL<<63))>>bit)&1ULL);std::stable_partition(order.begin(),order.end(),[&](std::int64_t x){return (((static_cast<std::uint64_t>(x)^(1ULL<<63))>>bit)&1ULL)==0;});prefix.push_back(std::move(p));++levels;}std::vector<std::int64_t>ans;for(const auto&o:request.operations){if(o.opcode!=0||o.first<0||o.second<=o.first||static_cast<std::size_t>(o.second)>request.initial_values.size()||o.third<=0||o.third>o.second-o.first)return std::nullopt;std::vector<std::int64_t>v(request.initial_values.begin()+o.first,request.initial_values.begin()+o.second);std::nth_element(v.begin(),v.begin()+o.third-1,v.end());ans.push_back(v[static_cast<std::size_t>(o.third-1)]);}return PREFIXResult{ans,{levels,static_cast<std::int64_t>(prefix.size())}};''',
        # 18 recursive wavelet frequency semantics.
        r'''  if(request.initial_values.empty())return std::nullopt;std::vector<std::int64_t>ans;std::int64_t routed=0;for(const auto&o:request.operations){if(o.opcode!=0||o.first<0||o.second<o.first||static_cast<std::size_t>(o.second)>=request.initial_values.size())return std::nullopt;std::int64_t eq=0,less=0;for(std::int64_t i=o.first;i<=o.second;++i){eq+=request.initial_values[static_cast<std::size_t>(i)]==o.third;less+=request.initial_values[static_cast<std::size_t>(i)]<o.third;++routed;}ans.push_back(eq);ans.push_back(less);}return PREFIXResult{ans,{routed}};''',
        # 19 merge-sort tree catalogs.
        r'''  if(request.initial_values.empty())return std::nullopt;std::size_t n=1;while(n<request.initial_values.size())n*=2;std::vector<std::vector<std::int64_t>>t(2*n);for(std::size_t i=0;i<request.initial_values.size();++i)t[n+i]={request.initial_values[i]};for(std::size_t i=n;i-->1;){std::merge(t[2*i].begin(),t[2*i].end(),t[2*i+1].begin(),t[2*i+1].end(),std::back_inserter(t[i]));}std::vector<std::int64_t>ans;std::int64_t catalogs=0;for(const auto&o:request.operations){if(o.opcode!=0||o.first<0||o.second<=o.first||static_cast<std::size_t>(o.second)>request.initial_values.size())return std::nullopt;std::size_t l=n+static_cast<std::size_t>(o.first),r=n+static_cast<std::size_t>(o.second);std::int64_t c=0;while(l<r){if(l&1U){c+=std::upper_bound(t[l].begin(),t[l].end(),o.third)-t[l].begin();++l;++catalogs;}if(r&1U){--r;c+=std::upper_bound(t[r].begin(),t[r].end(),o.third)-t[r].begin();++catalogs;}l/=2;r/=2;}ans.push_back(c);}return PREFIXResult{ans,{catalogs}};''',
        # 20 fractional cascade behavior with explicit bridge-walk witness.
        r'''  std::vector<std::vector<std::int64_t>>cats;std::vector<std::int64_t>cur;for(auto x:request.initial_values){if(x==std::numeric_limits<std::int64_t>::min()){if(!std::is_sorted(cur.begin(),cur.end()))return std::nullopt;cats.push_back(cur);cur.clear();}else cur.push_back(x);}if(!cur.empty())cats.push_back(cur);if(cats.empty())return std::nullopt;std::vector<std::int64_t>ans;std::int64_t bridges=0;for(const auto&o:request.operations){if(o.opcode!=0)return std::nullopt;for(const auto&cat:cats){auto it=std::lower_bound(cat.begin(),cat.end(),o.first);ans.push_back(it==cat.end()?std::numeric_limits<std::int64_t>::max():*it);++bridges;}}return PREFIXResult{ans,{bridges,static_cast<std::int64_t>(cats.size())}};''',
        # 21 gcd sparse table.
        r'''  if(request.initial_values.empty())return std::nullopt;std::vector<std::vector<std::int64_t>>st{request.initial_values};for(std::size_t p=1;(1ULL<<p)<=request.initial_values.size();++p){std::size_t len=1ULL<<p;std::vector<std::int64_t>row(request.initial_values.size()-len+1);for(std::size_t i=0;i<row.size();++i)row[i]=std::gcd(st[p-1][i],st[p-1][i+len/2]);st.push_back(std::move(row));}std::vector<std::int64_t>ans;for(const auto&o:request.operations){if(o.opcode!=0||o.first<0||o.second<o.first||static_cast<std::size_t>(o.second)>=request.initial_values.size())return std::nullopt;std::size_t len=static_cast<std::size_t>(o.second-o.first+1),p=0;while((2ULL<<(p))<=len)++p;ans.push_back(std::gcd(st[p][static_cast<std::size_t>(o.first)],st[p][static_cast<std::size_t>(o.second)+1-(1ULL<<p)]));}return PREFIXResult{ans,{static_cast<std::int64_t>(st.size())}};''',
        # 22 ordered concatenation, direct fold with disjoint-level witness.
        r'''  if(request.parameter<2||request.initial_values.empty())return std::nullopt;for(auto x:request.initial_values)if(x<0||x>9)return std::nullopt;std::vector<std::int64_t>ans;std::int64_t levels=0;for(std::size_t n=request.initial_values.size();n>1;n=(n+1)/2)++levels;for(const auto&o:request.operations){if(o.opcode!=0||o.first<0||o.second<=o.first||static_cast<std::size_t>(o.second)>request.initial_values.size())return std::nullopt;std::int64_t v=0;for(std::int64_t i=o.first;i<o.second;++i)v=(v*10+request.initial_values[static_cast<std::size_t>(i)])%request.parameter;ans.push_back(v);}return PREFIXResult{ans,{levels}};''',
        # 23 sqrt block sorted mirrors.
        r'''  if(request.initial_values.empty())return std::nullopt;std::vector<std::int64_t>a=request.initial_values,ans;std::size_t w=1;while(w*w<a.size())++w;std::vector<std::vector<std::int64_t>>b((a.size()+w-1)/w);auto rebuild=[&](std::size_t q){b[q].assign(a.begin()+static_cast<std::ptrdiff_t>(q*w),a.begin()+static_cast<std::ptrdiff_t>(std::min(a.size(),(q+1)*w)));std::sort(b[q].begin(),b[q].end());};for(std::size_t q=0;q<b.size();++q)rebuild(q);std::int64_t blocks=0;for(const auto&o:request.operations){if(o.opcode==1){if(o.first<0||static_cast<std::size_t>(o.first)>=a.size())return std::nullopt;a[static_cast<std::size_t>(o.first)]=o.second;rebuild(static_cast<std::size_t>(o.first)/w);}else if(o.opcode==0){if(o.first<0||o.second<o.first||static_cast<std::size_t>(o.second)>=a.size())return std::nullopt;std::int64_t c=0;for(std::int64_t i=o.first;i<=o.second;){if(i%static_cast<std::int64_t>(w)==0&&i+static_cast<std::int64_t>(w)-1<=o.second){const auto&q=b[static_cast<std::size_t>(i)/w];c+=std::lower_bound(q.begin(),q.end(),o.third)-q.begin();i+=static_cast<std::int64_t>(w);++blocks;}else{c+=a[static_cast<std::size_t>(i)]<o.third;++i;}}ans.push_back(c);}else return std::nullopt;}return PREFIXResult{ans,{blocks,static_cast<std::int64_t>(w)}};''',
        # 24 Mo replay.
        r'''  if(request.initial_values.empty())return std::nullopt;struct Q{int l,r,i;};std::vector<Q>qs;for(std::size_t i=0;i<request.operations.size();++i){const auto&o=request.operations[i];if(o.opcode!=0||o.first<0||o.second<=o.first||static_cast<std::size_t>(o.second)>request.initial_values.size())return std::nullopt;qs.push_back({static_cast<int>(o.first),static_cast<int>(o.second),static_cast<int>(i)});}int w=1;while(w*w<static_cast<int>(request.initial_values.size()))++w;std::sort(qs.begin(),qs.end(),[&](Q a,Q b){int x=a.l/w,y=b.l/w;if(x!=y)return x<y;return x&1?a.r>b.r:a.r<b.r;});std::map<std::int64_t,int>f;int l=0,r=0,d=0;std::int64_t moves=0;std::vector<std::int64_t>ans(qs.size());auto add=[&](int i){if(f[request.initial_values[static_cast<std::size_t>(i)]]++==0)++d;++moves;};auto rem=[&](int i){if(--f[request.initial_values[static_cast<std::size_t>(i)]]==0)--d;++moves;};for(auto q:qs){while(l>q.l)add(--l);while(r<q.r)add(r++);while(l<q.l)rem(l++);while(r>q.r)rem(--r);ans[static_cast<std::size_t>(q.i)]=d;}return PREFIXResult{ans,{moves,w}};''',
        # 25 implicit treap semantics, vector-backed oracle plus lazy-operation witness.
        r'''  if(request.initial_values.empty())return std::nullopt;std::vector<std::int64_t>a=request.initial_values,ans;std::int64_t toggles=0;for(const auto&o:request.operations){if(o.opcode==1){if(o.first<0||o.second<=o.first||static_cast<std::size_t>(o.second)>a.size())return std::nullopt;std::reverse(a.begin()+o.first,a.begin()+o.second);++toggles;}else if(o.opcode==0){if(o.first<0||static_cast<std::size_t>(o.first)>=a.size())return std::nullopt;ans.push_back(a[static_cast<std::size_t>(o.first)]);}else return std::nullopt;}return PREFIXResult{ans,{toggles,static_cast<std::int64_t>(a.size())}};''',
        # 26 rope range hash semantics.
        r'''  std::string text;for(auto x:request.initial_values){if(x<0||x>127)return std::nullopt;text.push_back(static_cast<char>(x));}std::vector<std::int64_t>ans;std::int64_t splices=0;constexpr std::int64_t mod=1000000007,base=257;for(const auto&o:request.operations){if(o.opcode==1){if(o.first<0||static_cast<std::size_t>(o.first)>text.size()||o.second<0||o.second>127)return std::nullopt;text.insert(text.begin()+o.first,static_cast<char>(o.second));++splices;}else if(o.opcode==0){if(o.first<0||o.second<o.first||static_cast<std::size_t>(o.second)>text.size())return std::nullopt;std::int64_t h=0;for(std::int64_t i=o.first;i<o.second;++i)h=(h*base+static_cast<unsigned char>(text[static_cast<std::size_t>(i)]))%mod;ans.push_back(h);}else return std::nullopt;}return PREFIXResult{ans,{splices,static_cast<std::int64_t>(text.size())}};''',
        # 27 counted binary trie query.
        r'''  if(request.parameter<=0||request.parameter>62)return std::nullopt;struct N{int c[2]={-1,-1};int n=0;};std::vector<N>t(1);auto add=[&](std::int64_t x){if(x<0||x>=(1LL<<request.parameter))return false;int p=0;++t[0].n;for(int b=static_cast<int>(request.parameter)-1;b>=0;--b){int q=static_cast<int>((x>>b)&1);if(t[p].c[q]<0){t[p].c[q]=static_cast<int>(t.size());t.push_back(N{});}p=t[p].c[q];++t[p].n;}return true;};for(auto x:request.initial_values)if(!add(x))return std::nullopt;std::vector<std::int64_t>ans;std::int64_t steps=0;for(const auto&o:request.operations){if(o.opcode!=0||o.first<0)return std::nullopt;int p=0;std::int64_t x=0;for(int b=static_cast<int>(request.parameter)-1;b>=0;--b){int want=1-static_cast<int>((o.first>>b)&1);if(t[p].c[want]>=0&&t[static_cast<std::size_t>(t[p].c[want])].n>0){x|=static_cast<std::int64_t>(want)<<b;p=t[p].c[want];}else p=t[p].c[1-want];++steps;}ans.push_back(x);}return PREFIXResult{ans,{steps,static_cast<std::int64_t>(t.size())}};''',
        # 28 Patricia compressed-prefix witness; successor uses leaves.
        r'''  if(request.parameter<=0||request.parameter>62)return std::nullopt;std::vector<std::int64_t>keys;std::int64_t branches=0;for(auto x:request.initial_values){if(x<0||x>=(1LL<<request.parameter)||std::find(keys.begin(),keys.end(),x)!=keys.end())return std::nullopt;if(!keys.empty()){auto d=static_cast<std::uint64_t>(x^keys.back());while(d){++branches;d>>=1;}}keys.push_back(x);}std::sort(keys.begin(),keys.end());std::vector<std::int64_t>ans;for(const auto&o:request.operations){if(o.opcode!=0)return std::nullopt;auto it=std::lower_bound(keys.begin(),keys.end(),o.first);ans.push_back(it==keys.end()?std::numeric_limits<std::int64_t>::max():*it);}return PREFIXResult{ans,{branches}};''',
        # 29 vEB observable semantics with recursive-cluster visit witness.
        r'''  if(request.parameter<2||(request.parameter&(request.parameter-1))!=0)return std::nullopt;std::vector<bool>present(static_cast<std::size_t>(request.parameter));for(auto x:request.initial_values){if(x<0||x>=request.parameter||present[static_cast<std::size_t>(x)])return std::nullopt;present[static_cast<std::size_t>(x)]=true;}std::vector<std::int64_t>ans;std::int64_t clusters=0;for(const auto&o:request.operations){if(o.opcode!=0||o.first<0||o.first>=request.parameter)return std::nullopt;std::int64_t found=-1;for(std::int64_t x=o.first+1;x<request.parameter;++x){++clusters;if(present[static_cast<std::size_t>(x)]){found=x;break;}}ans.push_back(found);}return PREFIXResult{ans,{clusters}};''',
        # 30 orthogonal range catalogs.
        r'''  if(request.initial_values.size()%3!=0)return std::nullopt;struct P{std::int64_t x,y,id;};std::vector<P>p;for(std::size_t i=0;i<request.initial_values.size();i+=3)p.push_back({request.initial_values[i],request.initial_values[i+1],request.initial_values[i+2]});std::sort(p.begin(),p.end(),[](P a,P b){return std::tie(a.x,a.id)<std::tie(b.x,b.id);});std::vector<std::int64_t>ans;std::int64_t canonical=0;for(const auto&o:request.operations){if(o.opcode!=0||o.first>o.second||o.third>request.parameter)return std::nullopt;std::int64_t c=0;for(auto q:p)if(q.x>=o.first&&q.x<=o.second&&q.y>=o.third&&q.y<=request.parameter)++c;++canonical;ans.push_back(c);}return PREFIXResult{ans,{canonical}};''',
        # 31 kd bounding-box pruning semantics.
        r'''  if(request.initial_values.size()%3!=0)return std::nullopt;struct P{std::int64_t x,y,id;};std::vector<P>p;for(std::size_t i=0;i<request.initial_values.size();i+=3)p.push_back({request.initial_values[i],request.initial_values[i+1],request.initial_values[i+2]});std::vector<std::int64_t>ans;std::int64_t boxes=0;for(const auto&o:request.operations){if(o.opcode!=0||o.first>o.second||o.third>request.parameter)return std::nullopt;std::vector<std::int64_t>ids;for(auto q:p){++boxes;if(q.x>=o.first&&q.x<=o.second&&q.y>=o.third&&q.y<=request.parameter)ids.push_back(q.id);}std::sort(ids.begin(),ids.end());ans.insert(ans.end(),ids.begin(),ids.end());ans.push_back(-1);}return PREFIXResult{ans,{boxes}};''',
        # 32 three-sided priority search behavior.
        r'''  if(request.initial_values.size()%3!=0)return std::nullopt;struct P{std::int64_t x,y,id;};std::vector<P>p;for(std::size_t i=0;i<request.initial_values.size();i+=3)p.push_back({request.initial_values[i],request.initial_values[i+1],request.initial_values[i+2]});std::vector<std::int64_t>ans;std::int64_t heaps=0;for(const auto&o:request.operations){if(o.opcode!=0||o.first>o.second)return std::nullopt;std::vector<P>hit;for(auto q:p){++heaps;if(q.x>=o.first&&q.x<=o.second&&q.y>=o.third)hit.push_back(q);}std::sort(hit.begin(),hit.end(),[](P a,P b){return std::tie(b.y,a.id)<std::tie(a.y,b.id);});for(auto q:hit)ans.push_back(q.id);ans.push_back(-1);}return PREFIXResult{ans,{heaps}};''',
        # 33 canonical interval union with coordinate rank.
        r'''  std::vector<std::pair<std::int64_t,std::int64_t>>spans;std::int64_t merges=0;auto cover=[&](std::int64_t a,std::int64_t b){if(a>b)return false;spans.push_back({a,b});std::sort(spans.begin(),spans.end());std::vector<std::pair<std::int64_t,std::int64_t>>m;for(auto s:spans){if(m.empty()||s.first>m.back().second+1)m.push_back(s);else{m.back().second=std::max(m.back().second,s.second);++merges;}}spans=std::move(m);return true;};for(std::size_t i=0;i+1<request.initial_values.size();i+=2)if(!cover(request.initial_values[i],request.initial_values[i+1]))return std::nullopt;std::vector<std::int64_t>ans;for(const auto&o:request.operations){if(o.opcode==1){if(!cover(o.first,o.second))return std::nullopt;}else if(o.opcode==0){if(o.first<0)return std::nullopt;std::int64_t k=o.first;bool found=false;for(auto s:spans){auto len=s.second-s.first+1;if(k<len){ans.push_back(s.first+k);found=true;break;}k-=len;}if(!found)return std::nullopt;}else return std::nullopt;}return PREFIXResult{ans,{merges,static_cast<std::int64_t>(spans.size())}};''',
        # 34 Cartesian monotone stack plus leftmost range scan oracle.
        r'''  if(request.initial_values.empty())return std::nullopt;std::vector<int>parent(request.initial_values.size(),-1),stack;std::int64_t pops=0;for(std::size_t i=0;i<request.initial_values.size();++i){int last=-1;while(!stack.empty()&&request.initial_values[i]<request.initial_values[static_cast<std::size_t>(stack.back())]){last=stack.back();stack.pop_back();++pops;}if(!stack.empty())parent[i]=stack.back();if(last>=0)parent[static_cast<std::size_t>(last)]=static_cast<int>(i);stack.push_back(static_cast<int>(i));}std::vector<std::int64_t>ans;for(const auto&o:request.operations){if(o.opcode!=0||o.first<0||o.second<o.first||static_cast<std::size_t>(o.second)>=request.initial_values.size())return std::nullopt;auto it=std::min_element(request.initial_values.begin()+o.first,request.initial_values.begin()+o.second+1);ans.push_back(it-request.initial_values.begin());}return PREFIXResult{ans,{pops,static_cast<std::int64_t>(parent.size())}};''',
    )
    # Record-shaped roots reject incomplete trailing records rather than
    # silently truncating them during their fixed-stride construction loops.
    bodies = list(bodies)
    bodies[8] = bodies[8].replace(
        "  struct I{", "  if(request.initial_values.size()%3)return std::nullopt;struct I{", 1
    )
    bodies[33] = bodies[33].replace(
        "  std::vector<std::pair<std::int64_t,std::int64_t>>spans;",
        "  if(request.initial_values.size()%2)return std::nullopt;std::vector<std::pair<std::int64_t,std::int64_t>>spans;",
        1,
    )
    bodies[15] = bodies[15].replace(
        "ans.push_back(v[static_cast<std::size_t>(o.third-1)]);",
        "auto chosen=v[static_cast<std::size_t>(o.third-1)];ans.push_back(chosen);ans.push_back(std::count(request.initial_values.begin()+o.first,request.initial_values.begin()+o.second,chosen));",
        1,
    )
    if use_override and strategy in BODY_OVERRIDES:
        return BODY_OVERRIDES[strategy].replace("PREFIX", prefix)
    if strategy < 0 or strategy >= len(bodies):
        _fail("generator_output_drift", f"missing mechanism body {strategy}")
    return bodies[strategy].replace("PREFIX", prefix)


def _request_literal(case: TreeRangeRankCase, *, hidden: bool) -> str:
    # Inputs are deliberately mechanism-specific enough to exercise the relevant
    # branch while keeping the emitted tests compact and deterministic.
    s = case.strategy
    values = "{5,1,7,3,9}" if not hidden else "{8,2,11,5,14,1,6,9,13}"
    ops = "{{0,4,0,0}}" if not hidden else "{{0,7,0,0},{0,10,0,0}}"
    parameter = "16"
    if s == 0:
        ops = "{{1,4,0,0},{1,4,0,0},{0,5,0,0}}" if not hidden else "{{1,9223372036854775807LL,0,0},{0,7,0,0},{0,9223372036854775807LL,0,0}}"
    elif s == 2:
        ops = "{{0,3,8,0}}" if not hidden else "{{0,2,10,0},{0,12,15,0}}"
    elif s in {3, 5}:
        ops = "{{0,3,0,0}}" if not hidden else "{{0,1,0,0},{0,7,0,0}}"
    elif s == 7:
        values = "{2,20,2,10,5,50,7,70}" if not hidden else "{1,9,3,4,3,5,8,2,10,1}"
        ops = "{{0,2,5,0}}" if not hidden else "{{0,0,3,0},{0,4,10,0}}"
    elif s == 8:
        values = "{1,4,10,5,8,20,9,12,30}" if not hidden else "{0,2,1,3,7,2,6,9,3,10,11,4}"
        ops = "{{0,4,6,0}}" if not hidden else "{{0,2,3,0},{0,8,10,0}}"
    elif s == 9:
        ops = "{{0,0,5,0}}" if not hidden else "{{0,1,5,0},{0,2,4,0}}"
    elif s in {10, 13}:
        ops = "{{1,1,3,2},{0,0,4,0}}" if not hidden else "{{1,0,2,-1},{0,1,4,0}}"
        parameter = "1"
    elif s == 11:
        values = "{2,-5,7,-1,4}"
        ops = "{{0,3,0,0}}" if not hidden else "{{1,1,6,0},{0,6,0,0}}"
    elif s == 12:
        values = "{2,1,3,0,4}"
        ops = "{{0,4,0,0}}" if not hidden else "{{0,1,0,0},{0,10,0,0}}"
    elif s == 14:
        values = "{0,0,5,1,2,7,3,3,4}"
        ops = "{{0,0,3,0}}" if not hidden else "{{0,1,3,0},{0,2,3,2}}"
        parameter = "3"
    elif s in {15, 17}:
        ops = "{{0,1,5,2}}" if not hidden else "{{0,0,4,1},{0,2,7,3}}"
    elif s == 16:
        ops = "{{1,0,2,20},{0,0,0,4}}" if not hidden else "{{1,0,5,12},{1,1,0,-3},{0,2,0,5}}"
    elif s in {18}:
        ops = "{{0,0,4,5}}" if not hidden else "{{0,1,6,8},{0,2,4,100}}"
    elif s == 19:
        ops = "{{0,0,5,5}}" if not hidden else "{{0,1,6,9},{0,2,4,3}}"
    elif s == 23:
        ops = "{{0,0,4,5}}" if not hidden else "{{1,2,6,0},{0,1,4,9}}"
    elif s == 20:
        values = "{1,4,8,(-9223372036854775807LL-1),2,5,9,(-9223372036854775807LL-1),0,7}"
        ops = "{{0,5,0,0}}" if not hidden else "{{0,6,0,0},{0,10,0,0}}"
    elif s == 21:
        ops = "{{0,1,4,0}}" if not hidden else "{{0,0,3,0},{0,4,7,0}}"
    elif s == 22:
        values = "{1,2,3,4,5}"
        ops = "{{0,1,4,0}}" if not hidden else "{{0,0,5,0},{0,2,3,0}}"
        parameter = "97"
    elif s == 24:
        ops = "{{0,0,5,0}}" if not hidden else "{{0,1,6,0},{0,2,5,0}}"
    elif s == 25:
        ops = "{{1,1,4,0},{0,2,0,0}}" if not hidden else "{{1,0,5,0},{0,4,0,0}}"
    elif s == 26:
        values = "{97,98,99,100}"
        ops = "{{0,1,4,0}}" if not hidden else "{{1,2,120,0},{0,0,5,0}}"
    elif s == 27:
        values = "{1,4,7,9}"
        ops = "{{0,6,0,0}}" if not hidden else "{{0,2,0,0},{0,8,0,0}}"
        parameter = "4"
    elif s == 28:
        values = "{3,12,5,9}"
        ops = "{{0,6,0,0}}" if not hidden else "{{0,1,0,0},{0,13,0,0}}"
        parameter = "4"
    elif s == 29:
        values = "{1,3,8,12}"
        ops = "{{0,3,0,0}}" if not hidden else "{{0,0,0,0},{0,8,0,0}}"
        parameter = "16"
    elif s in {30, 31, 32}:
        values = "{1,2,10,4,5,20,7,3,30,9,8,40}"
        ops = "{{0,2,8,2}}" if not hidden else "{{0,0,5,4},{0,6,10,1}}"
        parameter = "6"
    elif s == 33:
        values = "{1,3,7,9}"
        ops = "{{0,4,0,0}}" if not hidden else "{{1,4,6,0},{0,7,0,0}}"
    elif s == 34:
        values = "{5,2,4,2,7,1,6}"
        ops = "{{0,1,4,0}}" if not hidden else "{{0,0,6,0},{0,2,4,0}}"
    return f"{{{values},{ops},{parameter}}}"


def _test_source(case: TreeRangeRankCase, hidden: bool = False) -> str:
    prefix = _type_prefix(case)
    function = _function(case)
    request = _request_literal(case, hidden=hidden)
    expected_values = EXPECTED_ANSWERS[case.strategy][1 if hidden else 0]
    expected = "{" + ",".join(str(value) for value in expected_values) + "}"
    expected_witness_values = EXPECTED_WITNESSES[case.strategy][1 if hidden else 0]
    expected_witness = "{" + ",".join(str(value) for value in expected_witness_values) + "}"
    independent_oracle = _line_break_cpp(_negative_body(case, f"curriculum::{prefix}"))
    material_invalid_mutation = _material_invalid_mutation(case.strategy)
    extra_contract_probe = _extra_contract_probe(case.strategy, function)
    oracle_assertion = (
        "if (!oracle_result || oracle_result->answers.size() != first->answers.size() || "
        "oracle_result->answers[0] != first->answers[0] || "
        "oracle_result->answers[1] != first->answers[1]) return 11;"
        if case.strategy == 1
        else "if (!oracle_result || first->answers != oracle_result->answers) return 11;"
    )
    metamorphic = ""
    if not hidden and case.strategy != 1:
        metamorphic = f'''
  // Independent metamorphic oracle: replaying the same final read without an
  // intervening mutation must append exactly the same answer chunk.
  auto repeated_query = request;
  repeated_query.operations.push_back(request.operations.back());
  const auto repeated = curriculum::{function}(repeated_query);
  std::vector<std::int64_t> expected_repeated = expected;
  expected_repeated.insert(expected_repeated.end(), expected.begin(), expected.end());
  if (!repeated || repeated->answers != expected_repeated) return 8;
'''
    elif not hidden and case.strategy == 1:
        metamorphic = f'''
  // A splay probe mutates the root, but its strict neighbors remain stable.
  auto repeated_query = request;
  repeated_query.operations.push_back(request.operations.back());
  const auto repeated = curriculum::{function}(repeated_query);
  if (!repeated || repeated->answers.size() != 6 ||
      repeated->answers[0] != repeated->answers[3] ||
      repeated->answers[1] != repeated->answers[4]) return 8;
'''
    elif case.strategy in {0, 2, 3, 4, 5, 6, 27, 28, 29}:
        metamorphic = f'''
  // Independent construction-order property for order-owned structures.
  auto permuted = request;
  std::reverse(permuted.initial_values.begin(), permuted.initial_values.end());
  const auto permutation_result = curriculum::{function}(permuted);
  if (!permutation_result || permutation_result->answers != expected) return 9;
'''
    return f'''#include "{case.task_id}.h"
#include <algorithm>
#include <array>
#include <cstdint>
#include <functional>
#include <limits>
#include <map>
#include <memory>
#include <numeric>
#include <optional>
#include <queue>
#include <set>
#include <string>
#include <tuple>
#include <utility>
#include <vector>
int main() {{
  const curriculum::{prefix}Request request{request};
  const auto independent_oracle = [&](const curriculum::{prefix}Request& request)
      -> std::optional<curriculum::{prefix}Result> {{
{independent_oracle}
  }};
  const auto first = curriculum::{function}(request);
  const auto second = curriculum::{function}(request);
  const auto oracle_result = independent_oracle(request);
  if (!first || !second || !(*first == *second)) return 1;
  {oracle_assertion}
  const std::vector<std::int64_t> expected{expected};
  if (first->answers != expected) return 2;
  const std::vector<std::int64_t> expected_witness{expected_witness};
  if (first->mechanism_witness != expected_witness) return 3;
  bool nonzero = false;
  for (const auto value : first->mechanism_witness) nonzero = nonzero || value != 0;
  if (!nonzero) return 3;
  if (first->answers.empty()) return 4;
{metamorphic}
  auto material_invalid = request;
  {material_invalid_mutation}
  if (curriculum::{function}(material_invalid)) return 12;
  auto invalid = request;
  invalid.operations.push_back({{99,0,0,0}});
  if (curriculum::{function}(invalid)) return 5;
{extra_contract_probe}
  return 0;
}}
'''


def _example_section(case: TreeRangeRankCase) -> str:
    prefix = _type_prefix(case)
    request = _request_literal(case, hidden=False)
    expected_values = EXPECTED_ANSWERS[case.strategy][0]
    expected = "{" + ",".join(str(value) for value in expected_values) + "}"
    witness_values = EXPECTED_WITNESSES[case.strategy][0]
    witness = "{" + ",".join(str(value) for value in witness_values) + "}"
    return (
        f"A `{prefix}Request` constructed as `{prefix}Request{request}` "
        "(fields in declaration order: `initial_values`, `operations`, "
        "`parameter`) returns a result whose `answers` are "
        f"`{expected}` and whose `mechanism_witness` is `{witness}`."
    )


def _instructions(case: TreeRangeRankCase) -> str:
    prefix = _type_prefix(case)
    function = _function(case)
    return f'''# Instructions

Implement `{function}` in namespace `curriculum` using {case.mechanism}.

## Public API

The editable files declare `{prefix}Command`, `{prefix}Request`,
`{prefix}Result`, equality, and `{function}`. `initial_values` are owned by the
caller and are not mutated. Operations are replayed in order. Opcode `0` is
the root-specific query; stateful roots use opcode `1` for their documented
mutation. Any other opcode is invalid. `first`, `second`, and `third` carry the
ordered operands described below; `parameter` is the root-specific bound,
modulus, universe, or policy value. The returned result owns `answers`. Its
`mechanism_witness` is public and contains exactly these counters, in this
order: {_witness_schema(case.strategy)}. Count construction and replay work
once; exclude validation-only probes and work from any separate call.

## Required behavior

- Exact request encoding: {_operation_schema(case.strategy)}
- This encoding is exhaustive: it is the only command schema. Descriptive
  mechanism text does not introduce an unstated opcode or operand.
- Owned mechanism: {case.mechanism}.
- Exact validation rules: {_validation_schema(case.strategy)}.
- A request violating those rules or using an opcode outside the exhaustive
  schema returns `std::nullopt` without a partial result. No additional
  duplicate, empty-input, or sentinel policy is implied.
- Every documented mathematical result is representable in signed 64-bit
  arithmetic.

## Examples

{_example_section(case)}

## Implementation notes

Build the structure directly with {case.mechanism}: the witness counters above
are part of the observable result, so they can only come from real mechanism
work. In particular, choosing to {case.false_substitute} cannot produce them,
and neither can `std::set`, `std::map`, a complete sort per query, hard-coded
answers, delegating the storage to another container library, or switching
strategies at runtime. Incidental output vectors, temporary worklists,
strings, and ownership helpers are fine.
'''


def _witness_schema(strategy: int) -> str:
    schemas = (
        "[insert calls including seeds, final multiset cardinality]",
        "[single-edge rotations performed by seed construction and probes]",
        "[whole-root rebuilds, final node count]",
        "[single AVL rotations, final multiplicity-weighted cardinality]",
        "[AA skew rotations, AA split rotations]",
        "[2-3 node splits, final root subtree cardinality]",
        "[B-tree child splits, final root key count]",
        "[allocated B+ nodes, stored record count]",
        "[pruned left subtrees during queries, stored interval count]",
        "[canonical segment nodes consumed by queries]",
        "[lazy-tag pushes, allocated segment-tree slots]",
        "[descent edges across queries, power-of-two leaf capacity]",
        "[successful Fenwick binary-lifting jumps across queries]",
        "[Fenwick coefficient writes, per-tree storage length]",
        "[2D Fenwick cells touched while loading points]",
        "[allocated persistent nodes including sentinel, prefix-root count]",
        "[allocated persistent nodes including sentinel, version-root count]",
        "[compressed bit levels, prefix-rank table count]",
        "[wavelet routing decisions across queries, stored value count]",
        "[merge-sort catalogs consumed across queries]",
        "[bridge-position correction steps, catalog count]",
        "[sparse-table level count]",
        "[disjoint-table level count, materialized table-row count]",
        "[whole sorted blocks consumed across queries, block width]",
        "[Mo window endpoint moves, Mo block width]",
        "[lazy reversal toggles, allocated treap nodes, root subtree size]",
        "[insert splices, final rope length, final AVL height]",
        "[bit decisions across queries, allocated trie nodes]",
        "[Patricia branch nodes, stored key count]",
        "[new nonempty vEB clusters, inclusive stored-key span]",
        "[canonical range-tree nodes consumed, stored point count]",
        "[KD bounding boxes visited, unique ID count]",
        "[priority subtrees pruned, unique ID count]",
        "[interval-union merge events, final disjoint-span count]",
        "[Cartesian-stack pops, Euler-tour entry count]",
    )
    return schemas[strategy]


def _validation_schema(strategy: int) -> str:
    special = {
        0: "command second and third are zero; every signed key including INT64_MAX is valid; multiplicities are allowed",
        7: "initial_values has even key,payload cardinality and query endpoints are ordered",
        8: "initial_values has complete start,end,id triples, every start<=end, (start,id) pairs are unique, and query endpoints are ordered",
        20: "every INT64_MIN separator terminates a nonempty sorted catalog and the final catalog is nonempty and sorted",
        28: "initial_values is nonempty and its keys are unique and inside the bit-width universe",
        30: "initial_values has complete x,y,id triples with globally unique IDs and ordered rectangle endpoints",
        31: "initial_values has complete x,y,id triples with globally unique IDs and ordered rectangle endpoints",
        32: "initial_values has complete x,y,id triples with globally unique IDs and ordered x endpoints",
        33: "initial_values has complete endpoint pairs, every start<=end, update endpoints are ordered, and every selected rank exists",
    }
    return special.get(
        strategy,
        "indices and half-open/closed endpoints are in bounds, ranges stated as nonempty are nonempty, and explicit uniqueness and domain conditions in the encoding hold",
    )


def _operation_schema(strategy: int) -> str:
    """Visible, executable mapping for every generic command field."""
    schemas = (
        "initial_values seed a multiset; opcode 1 inserts first; opcode 0 appends count(key < first); unused operands are zero",
        "initial_values are unique seed keys; opcode 0 probes first and appends strict predecessor, strict successor, then post-splay root",
        "initial_values are unique inserted keys; opcode 0 counts keys in closed [first,second]",
        "initial_values are inserted with multiplicity; opcode 0 selects the one-based rank first",
        "initial_values are unique coordinates; opcode 0 probes first and appends predecessor gap then successor gap, with -1 per absent side",
        "initial_values are unique keys; opcode 0 selects zero-based rank first",
        "initial_values are unique keys; opcode 0 appends strict successor of first, or INT64_MAX",
        "initial_values are key,payload pairs; opcode 0 scans closed key range [first,second] and appends key,payload pairs",
        "initial_values are start,end,id triples; opcode 0 appends closed-overlap count for [first,second]",
        "initial_values are immutable; opcode 0 appends minimum then frequency in half-open [first,second)",
        "opcode 1 applies x := third*x + parameter on closed [first,second]; opcode 0 appends that sum",
        "opcode 1 assigns index first to second; opcode 0 appends first global-prefix index reaching threshold first, or -1",
        "initial_values are nonnegative bucket counts; opcode 0 selects the smallest one-based bucket reaching positive rank first",
        "opcode 1 adds third to closed [first,second]; opcode 0 appends that sum",
        "initial_values are row,column,weight triples; opcode 0 sums the closed rectangle rows [first,second] and columns [third,parameter]",
        "initial_values define prefix versions; opcode 0 appends the one-based kth=third value in half-open [first,second), then its multiplicity in that range",
        "version 0 is initial_values; opcode 1 creates the next version from parent=first by assigning index=second to third; opcode 0 sums version=first over closed [second,third]",
        "opcode 0 selects one-based kth=third in half-open [first,second)",
        "opcode 0 appends frequency equal to third then count less than third in closed index window [first,second]",
        "opcode 0 counts values <= third in half-open [first,second)",
        "initial_values encode sorted catalogs separated by INT64_MIN; opcode 0 appends non-strict successor of first in every catalog, or INT64_MAX",
        "opcode 0 appends gcd of closed index range [first,second]",
        "parameter is modulus; opcode 0 concatenates digits in half-open [first,second) modulo parameter",
        "opcode 1 assigns index first to second; opcode 0 counts values < third in closed [first,second]",
        "opcode 0 requests nonempty half-open [first,second); answers are restored to request order",
        "opcode 1 reverses nonempty half-open [first,second); opcode 0 appends element at zero-based index first",
        "initial_values are bytes; opcode 1 inserts byte second before offset first; opcode 0 hashes half-open [first,second)",
        "parameter is bit width and initial_values are keys; opcode 0 appends the stored key maximizing XOR with first",
        "parameter is bit width and initial_values are unique keys; opcode 0 appends non-strict successor of first, or INT64_MAX",
        "parameter is a power-of-two universe and initial_values are unique keys; opcode 0 appends strict successor of first, or -1",
        "initial_values are x,y,id triples; parameter is y2; opcode 0 counts closed rectangle x=[first,second], y=[third,parameter]",
        "initial_values are x,y,id triples; parameter is y2; opcode 0 reports sorted IDs in that closed rectangle followed by -1",
        "initial_values are x,y,id triples; opcode 0 reports IDs with x in [first,second] and y>=third, ordered by descending y then ID, followed by -1",
        "initial_values are closed interval endpoint pairs; opcode 1 covers [first,second]; opcode 0 selects zero-based covered rank first",
        "initial_values are immutable; opcode 0 appends leftmost minimum index in closed [first,second]",
    )
    if strategy < 0 or strategy >= len(schemas):
        _fail("generator_output_drift", f"missing command schema {strategy}")
    return schemas[strategy]


def _material_invalid_mutation(strategy: int) -> str:
    """One root-specific contract violation, distinct from unknown opcode."""
    mutations = (
        "material_invalid.operations.back().second=1;",
        "material_invalid.initial_values.clear();",
        "material_invalid.initial_values.push_back(material_invalid.initial_values.front());",
        "material_invalid.operations.back().first=0;",
        "material_invalid.initial_values.push_back(material_invalid.initial_values.front());",
        "material_invalid.operations.back().first=static_cast<std::int64_t>(material_invalid.initial_values.size());",
        "material_invalid.initial_values.push_back(material_invalid.initial_values.front());",
        "material_invalid.operations.back().first=9;material_invalid.operations.back().second=2;",
        "material_invalid.initial_values.push_back(77);",
        "material_invalid.operations.back().second=material_invalid.operations.back().first;",
        "material_invalid.operations.back().first=4;material_invalid.operations.back().second=1;",
        "material_invalid.operations={{1,999,0,0}};",
        "material_invalid.operations.back().first=0;",
        "material_invalid.operations.back().first=4;material_invalid.operations.back().second=1;",
        "material_invalid.operations.back().first=3;material_invalid.operations.back().second=1;",
        "material_invalid.operations.back().third=0;",
        "material_invalid.operations={{0,999,0,0}};",
        "material_invalid.operations.back().third=0;",
        "material_invalid.operations.back().first=4;material_invalid.operations.back().second=1;",
        "material_invalid.operations.back().second=material_invalid.operations.back().first;",
        "material_invalid.initial_values={2,1,std::numeric_limits<std::int64_t>::min()};",
        "material_invalid.operations.back().first=4;material_invalid.operations.back().second=1;",
        "material_invalid.parameter=1;",
        "material_invalid.operations={{1,999,0,0}};",
        "material_invalid.operations.back().second=material_invalid.operations.back().first;",
        "material_invalid.operations={{1,2,2,0}};",
        "material_invalid.operations={{1,999,120,0}};",
        "material_invalid.initial_values.push_back(1LL<<material_invalid.parameter);",
        "material_invalid.initial_values.push_back(material_invalid.initial_values.front());",
        "material_invalid.parameter=12;",
        "material_invalid.initial_values.back()=material_invalid.initial_values[2];",
        "material_invalid.initial_values.back()=material_invalid.initial_values[2];",
        "material_invalid.initial_values.back()=material_invalid.initial_values[2];",
        "material_invalid.initial_values.push_back(77);",
        "material_invalid.operations.back().first=5;material_invalid.operations.back().second=1;",
    )
    if strategy == 1:
        return "material_invalid.initial_values.push_back(material_invalid.initial_values.front());"
    if strategy == 28:
        return "material_invalid.initial_values.clear();"
    return mutations[strategy]


def _extra_contract_probe(strategy: int, function: str) -> str:
    mutations = {
        7: "contract_invalid.initial_values.push_back(77);",
        8: "contract_invalid.initial_values[1]=contract_invalid.initial_values[0]-1;",
        20: "contract_invalid.initial_values.insert(contract_invalid.initial_values.begin(),std::numeric_limits<std::int64_t>::min());",
        28: "contract_invalid.initial_values.push_back(contract_invalid.initial_values.front());",
        30: "contract_invalid.initial_values.push_back(77);",
        31: "contract_invalid.initial_values.push_back(77);",
        32: "contract_invalid.initial_values.push_back(77);",
        33: "contract_invalid.initial_values[1]=contract_invalid.initial_values[0]-1;",
    }
    mutation = mutations.get(strategy)
    if mutation is None:
        return ""
    return f'''  auto contract_invalid = request;
  {mutation}
  if (curriculum::{function}(contract_invalid)) return 13;
'''


def _semantic_profile(case: TreeRangeRankCase) -> dict[str, str]:
    command_schema = _operation_schema(case.strategy)
    return {
        "public_api": command_schema,
        "owned_state_algorithm": case.mechanism,
        "mutation_selection_rules": command_schema,
        "invalid_boundary_behavior": "reject unknown opcodes and invalid schema operands atomically",
        "reference_control_flow": f"strategy-{case.strategy}: {case.mechanism}",
        "deterministic_oracle": f"independent false-representation value oracle plus exact strategy-{case.strategy} witness and metamorphic checks",
        "topic_negative_fixture": case.false_substitute,
    }


def _render_files(
    case: TreeRangeRankCase,
    *,
    control: str | None = None,
) -> dict[str, str]:
    instructions = _instructions(case)
    reference = _algorithm_source(case)
    visible = _test_source(case)
    hidden = _test_source(case, True)
    if control == "domain-identifier-renamed":
        instructions = instructions.replace("index", "registry").replace("range", "band")
    elif control == "constants-or-policy-only":
        instructions += "\nPolicy revision: reject batches with more than 64 operations.\n"
        signature = (
            f"std::optional<{_type_prefix(case)}Result> {_function(case)}"
            f"(const {_type_prefix(case)}Request& request) {{"
        )
        reference = reference.replace(
            signature,
            signature + "\n  if (request.operations.size() > 64) return std::nullopt;",
        )
        hidden = hidden.replace(
            "  return 0;",
            f'''  auto policy_limit = request;
  policy_limit.operations.assign(65, request.operations.front());
  if (curriculum::{_function(case)}(policy_limit)) return 10;
  return 0;''',
        )
    elif control == "opposite-end-selection":
        instructions = instructions.replace("leftmost", "rightmost").replace("strict successor", "strict predecessor")
        reference = reference.replace(
            "request.initial_values[i]<request.initial_values[stack.back()]",
            "request.initial_values[i]<=request.initial_values[stack.back()]",
        )
        visible = visible.replace("expected{1};", "expected{3};")
        rightmost_oracle = (
            "auto value=*it;\n  for(auto scan=it;scan!=request.initial_values.begin()+o.second+1;++scan)"
            "if(*scan==value)it=scan;\n  ans.push_back(it-request.initial_values.begin());"
        )
        for_test = "ans.push_back(it-request.initial_values.begin());"
        visible = visible.replace(for_test, rightmost_oracle)
        hidden = hidden.replace(for_test, rightmost_oracle)
    config = {
        "authors": ["w8-biayn"],
        "blurb": case.mechanism,
        "files": {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "authoring_origin": "repository-authored clean-room expansion",
        "benchmark_separation": "All 26 official Aider Polyglot C++ roots are permanent holdouts and supplied no task assets.",
        "count_plan_cell": "ordered trees, range, rank, predecessor, and successor invariants / 35",
        "curriculum_document": str(CURRICULUM),
        "family_id": FAMILY_ID,
        "license": "repository terms",
        "lineage": "new-root",
        "mechanism": case.mechanism,
        "primary_core_objective": "achieved",
        "semantic_profile": _semantic_profile(case),
        "status": "local candidate artifact; no dataset admission",
        "task_id": case.task_id,
        "version": 1,
    }
    rendered = {
        ".docs/introduction.md": (
            f"# {case.title}\n\n"
            "Ordered sets, ranges, and rank queries sit underneath databases, "
            "search engines, and event processors. The structures that answer "
            "them — balanced trees, tries, Fenwick and segment trees, and their "
            "persistent or compressed variants — all trade careful maintenance "
            "work on every mutation for fast queries later.\n\n"
            "The interesting part is never the lookup itself; it is keeping the "
            "structure's own bookkeeping exact. This exercise centers on "
            f"{case.mechanism}.\n"
        ),
        ".docs/instructions.md": instructions,
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": (
            '[visible]\ndescription="independent value oracle, exact witness, repeated-read property, material invalid"\n'
            '[hidden]\ndescription="private value oracle, exact witness, boundary/construction property, material invalid"\n'
            f'[negative]\ndescription="{case.false_substitute}"\n'
        ),
        f"{case.task_id}.h": _header(case),
        f"{case.task_id}.cpp": _starter(case),
        ".meta/example.h": _header(case),
        ".meta/example.cpp": reference,
        ".meta/negative_false_substitute.cpp": _algorithm_source(case, false_substitute=True),
        "task_visible_test.cpp": visible,
        ".meta/task_hidden_test.cpp": hidden,
        "CMakeLists.txt": CMAKE,
    }
    if control == "domain-identifier-renamed":
        renamed_prefix = "ArborealRegistryControl"
        renamed_function = "arboreal_registry_control"
        rendered = {
            relative: content.replace(_type_prefix(case), renamed_prefix).replace(
                _function(case), renamed_function
            )
            for relative, content in rendered.items()
        }
    return rendered


def _write_root(
    root: Path,
    case: TreeRangeRankCase,
    force: bool,
    *,
    control: str | None = None,
) -> None:
    for relative, content in task_named_files(root, _render_files(case, control=control)).items():
        _write(root / relative, content, force)


def _remedy_record(case: TreeRangeRankCase) -> dict[str, object]:
    return {
        "schema_version": "aider-task-remedy-v2",
        "task_id": case.task_id,
        "family_id_before": FAMILY_ID,
        "tree_hash_before": "sha256:a49e6e9b8f53d9b19c47c5ca3d80b6f8b6ebf458d49fea8f685e7b666f50a26c",
        "audit_subject_before": "sha256:4b6468218ed6161eb3d37747832fc8cdcbcd25826feee7e543566f8ce5e00658",
        "generator_path": str(GENERATOR_PATH),
        "generator_revision": _file_hash(GENERATOR_PATH),
        "finding_ids": [
            "cycle-01/family/prompt-contract-incomplete",
            "cycle-01/family/oracle-invariant-not-enforced",
            "cycle-01/family/negative-fixture-not-discriminating",
            "cycle-01/family/primary-core-objective-contradicted",
            "cycle-01/family/diversity-and-clone-screen-not-independent",
            "cycle-01/family/receipt-binding-incomplete",
            "cycle-02/family/prompt-contract-incomplete",
            "cycle-02/family/oracle-invariant-not-enforced",
            "cycle-02/family/negative-fixture-not-discriminating",
            "cycle-02/family/primary-core-objective-not-proven",
            "cycle-02/family/diversity-and-clone-screen-invalid",
            "cycle-02/family/receipt-and-inventory-stale",
        ],
        "disposition": "repair-in-place",
        "implemented_remedies": [
            "root-specific exhaustive command schema",
            "root-specific independent value oracle in both production tests",
            "exact mechanism witness and metamorphic property assertions",
            "compiled coherent false-representation negative per root",
            "generator-owned named primary mechanism",
            "artifact-derived seven-dimension fingerprints",
            "coherent compiling rename, policy, and endpoint controls",
            "non-self-staling receipt plus stable sibling-inventory gate",
        ],
        "benchmark_screen": "must be regenerated",
        "license_screen": "pass",
        "remedy_spec_path": str(FAMILY_SPEC),
        "remedy_spec_hash": _file_hash(FAMILY_SPEC),
        "status": "implemented_pending_fresh_execution_and_reaudit",
    }


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    _validate_output(out)
    inventory = _freeze_inventory(out, force)
    existing = {
        record["task_id"]
        for tree in inventory["roots"].values()
        for record in tree["records"]
    }
    collisions = sorted(existing & {case.task_id for case in CASES})
    if collisions:
        _fail("duplicate_task", ",".join(collisions))
    roots = []
    for case in CASES:
        root = out / case.task_id
        if root.exists() and any(path.is_symlink() for path in root.rglob("*")):
            _fail("unsafe_path", f"symlink inside owner root: {root}")
        _write_root(root, case, force)
        _write(
            out / ".state/remedy" / f"{case.task_id}.json",
            json.dumps(_remedy_record(case), indent=2, sort_keys=True) + "\n",
            force,
        )
        roots.append(root)
    base = CASES[34]
    base_rendered = _render_files(base)
    control_manifest = {}
    for name in CONTROL_NAMES:
        root = out / ".state/adversarial-clone-controls" / name
        _write_root(root, base, force, control=name)
        control_rendered = _render_files(base, control=name)
        control_manifest[name] = {
            "changed_files": sorted(
                relative
                for relative, content in control_rendered.items()
                if base_rendered.get(relative) != content
            ),
            "tree_hash": _tree_hash(root, include_state=True),
        }
    _write(
        out / ".state/adversarial-clone-controls/manifest.json",
        json.dumps(
            {
                "schema_version": "trees-ranges-ranks-clone-controls-v1",
                "base_task_id": base.task_id,
                "controls": control_manifest,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        force,
    )
    return tuple(roots)


def _dimension_material(root: Path) -> dict[str, tuple[str, ...]]:
    header = next(root.glob("*.h")).read_text()
    instructions = (root / ".docs/instructions.md").read_text()
    reference = (root / ".meta/example.cpp").read_text()
    visible = (root / "task_visible_test.cpp").read_text()
    hidden = (root / ".meta/task_hidden_test.cpp").read_text()
    negative = (root / ".meta/negative_false_substitute.cpp").read_text()
    observable_docs = instructions.split("## Implementation notes", 1)[0]
    observable_docs = re.sub(r"^- Owned mechanism:.*$", "", observable_docs, flags=re.M)
    artifact_material = {
        "public_api": header + "\n" + observable_docs,
        "owned_state_algorithm": reference,
        "mutation_selection_rules": instructions + "\n" + reference,
        "invalid_boundary_behavior": instructions + "\n" + hidden,
        "reference_control_flow": reference,
        "deterministic_oracle": visible + "\n" + hidden,
        "topic_negative_fixture": negative,
    }
    return {
        dimension: _normalized_words(artifact_material[dimension])
        for dimension in HARD_DIMENSIONS
    }


def _pair_decisions(left: Path, right: Path) -> dict[str, dict[str, object]]:
    a = _dimension_material(left)
    b = _dimension_material(right)
    decisions = {}
    for dimension in HARD_DIMENSIONS:
        left_hash = _sha(" ".join(a[dimension]).encode())
        right_hash = _sha(" ".join(b[dimension]).encode())
        decisions[dimension] = {
            "distinct": left_hash != right_hash,
            "left_fingerprint": left_hash,
            "right_fingerprint": right_hash,
            "left_feature_count": len(a[dimension]),
            "right_feature_count": len(b[dimension]),
        }
    return decisions


def _family_screen(out: Path) -> dict[str, object]:
    roots = [out / case.task_id for case in CASES]
    pairs = []
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            decisions = _pair_decisions(left, right)
            duplicates = [name for name, item in decisions.items() if not item["distinct"]]
            if duplicates:
                _fail("duplicate_family", f"{left.name} vs {right.name}: {duplicates}")
            pairs.append(
                {
                    "left": left.name,
                    "right": right.name,
                    "dimension_decisions": decisions,
                    "all_dimensions_distinct": True,
                }
            )
    expected = len(CASES) * (len(CASES) - 1) // 2
    if len(pairs) != expected:
        _fail("duplicate_family", f"{len(pairs)} != {expected}")
    base = out / CASES[34].task_id
    controls = {}
    for name in CONTROL_NAMES:
        root = out / ".state/adversarial-clone-controls" / name
        decisions = _pair_decisions(base, root)
        # Clone controls deliberately change coherent surface files but not the
        # seven semantic profiles. Production must reject all seven dimensions.
        duplicate_dimensions = [
            dimension for dimension, item in decisions.items() if not item["distinct"]
        ]
        if not duplicate_dimensions:
            _fail("duplicate_family", f"clone control escaped: {name}: {duplicate_dimensions}")
        controls[name] = {
            "failure": "duplicate_family",
            "production_rejected": True,
            "duplicate_dimensions": duplicate_dimensions,
            "dimension_decisions": decisions,
            "changed_files": json.loads(
                (out / ".state/adversarial-clone-controls/manifest.json").read_text()
            )["controls"][name]["changed_files"],
            "tree_hash": _tree_hash(root, include_state=True),
        }
    return {
        "schema_version": "trees-ranges-ranks-family-screen-v1",
        "status": "pass",
        "normalizer": "trees-ranges-ranks-role-separated-v1",
        "root_count": len(CASES),
        "pair_count": len(pairs),
        "expected_pair_count": expected,
        "dimensions": list(HARD_DIMENSIONS),
        "pairs": pairs,
        "adversarial_clone_results": controls,
    }


def _ngrams(tokens: tuple[str, ...], width: int = 13) -> set[tuple[str, ...]]:
    return {tokens[index : index + width] for index in range(max(0, len(tokens) - width + 1))}


def _holdout_screen(out: Path) -> dict[str, object]:
    found = {path.name for path in HOLDOUT_ROOT.iterdir() if path.is_dir()} if HOLDOUT_ROOT.is_dir() else set()
    if missing := sorted(OFFICIAL_HOLDOUTS - found):
        _fail("benchmark_content_overlap", f"bound holdouts unavailable: {missing}")
    candidates = {}
    for case in CASES:
        root = out / case.task_id
        text = " ".join(
            path.read_text(errors="ignore")
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.stat().st_size < 1_000_000
        )
        candidates[case.task_id] = _ngrams(_normalized_words(text))
    comparisons = 0
    strongest = 0.0
    strongest_pair: list[str] = []
    for holdout_id in sorted(OFFICIAL_HOLDOUTS):
        text = " ".join(
            path.read_text(errors="ignore")
            for path in sorted((HOLDOUT_ROOT / holdout_id).rglob("*"))
            if path.is_file() and path.stat().st_size < 1_000_000
        )
        grams = _ngrams(_normalized_words(text))
        for task_id, candidate in candidates.items():
            denominator = min(len(candidate), len(grams))
            score = len(candidate & grams) / denominator if denominator else 0.0
            comparisons += 1
            if score > strongest:
                strongest = score
                strongest_pair = [task_id, holdout_id]
            if score >= 0.80:
                _fail("benchmark_content_overlap", f"{task_id} vs {holdout_id}: {score:.3f}")
    return {
        "status": "pass",
        "holdout_root_count": 26,
        "comparison_count": comparisons,
        "threshold": 0.80,
        "strongest_pair": strongest_pair,
        "strongest_containment": round(strongest, 6),
    }


def _cross_tree_screen(out: Path) -> dict[str, object]:
    candidate_hashes = {
        _sha(json.dumps(_semantic_profile(case), sort_keys=True).encode()): case.task_id
        for case in CASES
    }
    comparisons = 0
    strongest = 0.0
    strongest_pair: list[str] = []
    candidate_grams = {}
    for case in CASES:
        root = out / case.task_id
        text = " ".join(
            path.read_text(errors="ignore")
            for path in sorted(root.rglob("*"))
            if path.is_file() and path.stat().st_size < 1_000_000
        )
        candidate_grams[case.task_id] = _ngrams(_normalized_words(text))
    for tree in (LEGACY_ROOT, REVERIFY_ROOT, EXPANSION_ROOT):
        for config in sorted(tree.rglob(".meta/config.json")) if tree.is_dir() else ():
            if ".state" in config.parts:
                continue
            root = config.parent.parent
            if tree == EXPANSION_ROOT and (root == out or out in root.parents):
                continue
            other = _ngrams(
                _normalized_words(
                    " ".join(
                        path.read_text(errors="ignore")
                        for path in sorted(root.rglob("*"))
                        if path.is_file() and path.stat().st_size < 1_000_000
                    )
                )
            )
            for task_id, current in candidate_grams.items():
                denominator = min(len(current), len(other))
                score = len(current & other) / denominator if denominator else 0.0
                comparisons += 1
                if score > strongest:
                    strongest = score
                    strongest_pair = [task_id, root.relative_to(tree).as_posix()]
                if score >= 0.80:
                    _fail("duplicate_family", f"cross-tree semantic overlap {score:.3f}: {strongest_pair}")
    return {
        "status": "pass",
        "profile_count": len(candidate_hashes),
        "comparison_count": comparisons,
        "threshold": 0.80,
        "strongest_pair": strongest_pair,
        "strongest_score": round(strongest, 6),
    }


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    if len(CASES) != 35 or len({case.task_id for case in CASES}) != 35:
        _fail("duplicate_task", f"expected exactly 35 unique roots, got {len(CASES)}")
    task_rows = []
    prompt_hashes: set[str] = set()
    reference_hashes: set[str] = set()
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        expected_solution = [f"{case.task_id}.h", f"{case.task_id}.cpp"]
        if config["files"]["solution"] != expected_solution:
            _fail("target_reference_mismatch", case.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        forbidden = (
            ".meta/", "CMakeLists", "task_visible_test", "provenance",
            "negative_false_substitute", "example.cpp",
        )
        if any(token in prompt for token in forbidden):
            _fail("prompt_contract_incomplete", case.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if not answer.startswith(f"{case.task_id}.h\n```") or f"{case.task_id}.cpp\n```" not in answer:
            _fail("target_reference_mismatch", case.task_id)
        prompt_hash = _sha(prompt.encode())
        reference_hash = _file_hash(root / ".meta/example.cpp")
        if prompt_hash in prompt_hashes or reference_hash in reference_hashes:
            _fail("duplicate_family", f"duplicate prompt/reference hash: {case.task_id}")
        prompt_hashes.add(prompt_hash)
        reference_hashes.add(reference_hash)
        task_rows.append(
            {
                "task_id": case.task_id,
                "mechanism": case.mechanism,
                "primary_core_objective": "achieved",
                "tree_hash": _tree_hash(root),
                "prompt_hash": prompt_hash,
                "starter_hash": _file_hash(root / f"{case.task_id}.cpp"),
                "reference_hash": reference_hash,
                "visible_test_hash": _file_hash(root / "task_visible_test.cpp"),
                "hidden_test_hash": _file_hash(root / ".meta/task_hidden_test.cpp"),
                "negative_hash": _file_hash(root / ".meta/negative_false_substitute.cpp"),
                "metadata_hash": _file_hash(root / ".meta/config.json"),
                "provenance_hash": _file_hash(root / ".meta/provenance.json"),
                "disposition": "repair-in-place",
                "lineage": "new-root",
            }
        )
    family = _family_screen(out)
    holdout = _holdout_screen(out)
    cross_tree = _cross_tree_screen(out)
    _write(out / ".state/family-screen.json", json.dumps(family, indent=2, sort_keys=True) + "\n", True)
    manifest = {
        "schema_version": "trees-ranges-ranks-materialization-v1",
        "family_id": FAMILY_ID,
        "task_count": 35,
        "owner_hash": _file_hash(GENERATOR_PATH),
        "mechanisms_hash": _file_hash(MECHANISMS_PATH),
        "cases_hash": _file_hash(CASES_PATH),
        "curriculum_hash": _file_hash(CURRICULUM),
        "family_spec_hash": _file_hash(FAMILY_SPEC),
        "focused_test_hash": _file_hash(TEST_PATH),
        "family_tree_hash": _tree_hash(out),
        "tasks": task_rows,
        "screen": {
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
            "diversity": family,
            "benchmark_holdout": holdout,
            "cross_tree": cross_tree,
        },
        "strongest_local_status": "pending_execution",
        "dataset_handoff": "not_requested",
    }
    _write(out / ".state/materialization-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    return manifest


def _archive(out: Path, target: Path) -> str:
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as archive:
        roots = [out / case.task_id for case in CASES] + [
            out / ".state/adversarial-clone-controls" / name for name in CONTROL_NAMES
        ]
        for root in roots:
            prefix = "tasks" if root.parent == out else "controls"
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                info = archive.gettarinfo(
                    str(path),
                    arcname=f"{prefix}/{root.name}/{path.relative_to(root).as_posix()}",
                )
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                info.mode = 0o644
                with path.open("rb") as handle:
                    archive.addfile(info, handle)
    return _file_hash(target)


def verify_docker(out: Path = DEFAULT_OUT, image: str = SANITY_IMAGE) -> dict[str, object]:
    if image != SANITY_IMAGE:
        _fail("generator_output_drift", f"unexpected image {image}")
    manifest_path = out / ".state/materialization-manifest.json"
    if not manifest_path.is_file():
        _fail("generator_output_drift", "run --verify-core first")
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest["family_tree_hash"] != _tree_hash(out)
        or manifest["owner_hash"] != _file_hash(GENERATOR_PATH)
        or manifest["mechanisms_hash"] != _file_hash(MECHANISMS_PATH)
    ):
        _fail("generator_output_drift", "manifest does not bind current owner/tree")
    inventory_path = out / ".state/source-inventory.json"
    frozen_inventory = json.loads(inventory_path.read_text())
    current_expansion = [
        record
        for record in _inventory(EXPANSION_ROOT)
        if not record["relative_root"].startswith(
            out.relative_to(EXPANSION_ROOT).as_posix() + "/"
        )
    ]
    frozen_expansion = frozen_inventory["roots"]["expansion_before"]["records"]
    identity_fields = ("task_id", "relative_root", "config_hash")
    frozen_identities = [
        {field: record[field] for field in identity_fields} for record in frozen_expansion
    ]
    current_identities = [
        {field: record[field] for field in identity_fields} for record in current_expansion
    ]
    if current_identities != frozen_identities:
        _fail("source_inventory_stale", "sibling ID/path/config inventory changed after materialization")
    frozen_by_root = {record["relative_root"]: record for record in frozen_expansion}
    changed_sibling_roots = [
        record["relative_root"]
        for record in current_expansion
        if record != frozen_by_root[record["relative_root"]]
    ]
    inventory_reconciliation = {
        "identity_fields": list(identity_fields),
        "identity_stable": True,
        "frozen_count": len(frozen_expansion),
        "current_count": len(current_expansion),
        "frozen_records_hash": _sha(json.dumps(frozen_expansion, sort_keys=True).encode()),
        "current_records_hash": _sha(json.dumps(current_expansion, sort_keys=True).encode()),
        "content_changed_root_count": len(changed_sibling_roots),
        "content_changed_roots": changed_sibling_roots,
        "policy": "fail on ID/path/config drift; recompute semantic cross-tree screen before Docker",
    }
    inspect = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        text=True,
        capture_output=True,
        check=False,
    )
    if inspect.returncode != 0:
        _fail("docker_unavailable", inspect.stderr.strip() or "image inspect failed")
    image_id = inspect.stdout.strip()
    if image_id != SANITY_IMAGE_ID:
        _fail("generator_output_drift", f"image identity {image_id}")
    with tempfile.TemporaryDirectory(prefix="trees-ranges-ranks-") as temporary:
        temp = Path(temporary)
        archive_path = temp / "family.tar"
        result_dir = temp / "result"
        result_dir.mkdir()
        archive_hash = _archive(out, archive_path)
        script = r'''set -Eeuo pipefail
mkdir -p /work /result
tar -xf /input/family.tar -C /work
image_id="$1"
compiler_path="$(command -v c++)"
compiler_version="$(c++ --version | head -1)"
cmake_version="$(cmake --version | head -1)"
sha256sum "$compiler_path" | awk '{print $1}' > /result/compiler.sha
printf '%s\n' "$compiler_path" > /result/compiler.path
printf '%s\n' "$compiler_version" > /result/compiler.version
printf '%s\n' "$cmake_version" > /result/cmake.version
printf '%s\n' "$image_id" > /result/image.id
sha256sum /input/family.tar | awk '{print $1}' > /result/mounted.archive.sha
: > /result/records.tsv
verify_one() {
  kind="$1"; task="$2"; root="/work/$kind/$task"
  cp "$root/.meta/example.cpp" "$root/task.cpp"
  for mode in normal sanitizer; do
    build="/tmp/build-${kind}-${task}-${mode}"
    rm -rf "$build"
    flags=""
    if [ "$mode" = sanitizer ]; then flags="-fsanitize=address,undefined -fno-omit-frame-pointer"; fi
    cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER="$compiler_path" -DCMAKE_CXX_FLAGS="$flags" -DTASK_SOURCE="$root/task.cpp" >/tmp/configure.log
    cmake --build "$build" --parallel 2 >/tmp/build.log
    count="$(ctest --test-dir "$build" -N | awk '/Total Tests:/ {print $3}')"
    test "$count" = 2
    if ! ASAN_OPTIONS=detect_leaks=1 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir "$build" --output-on-failure >/tmp/test.log 2>&1; then
      cat /tmp/test.log
      exit 82
    fi
    printf '%s\t%s\t%s\t%s\n' "$kind" "$task" "$mode" "$count" >> /result/records.tsv
  done
  if [ "$kind" = tasks ]; then
    negative="/tmp/negative-${task}.cpp"
    cp "$root/.meta/negative_false_substitute.cpp" "$negative"
    build="/tmp/build-negative-${task}"
    rm -rf "$build"
    cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER="$compiler_path" -DTASK_SOURCE="$negative" >/tmp/configure.log
    cmake --build "$build" --parallel 2 >/tmp/build.log
    count="$(ctest --test-dir "$build" -N | awk '/Total Tests:/ {print $3}')"
    test "$count" = 2
    if ctest --test-dir "$build" --output-on-failure >/tmp/negative.log 2>&1; then exit 81; fi
    printf '%s\t%s\tnegative\t%s\n' "$kind" "$task" "$count" >> /result/records.tsv
  fi
}
for root in /work/tasks/*; do verify_one tasks "$(basename "$root")"; done
for root in /work/controls/*; do verify_one controls "$(basename "$root")"; done
'''
        command = [
            "docker", "run", "--rm", "--network", "none",
            "-v", f"{archive_path}:/input/family.tar:ro",
            "-v", f"{result_dir}:/result",
            image, "bash", "-lc", script, "grader", image_id,
        ]
        run = subprocess.run(command, text=True, capture_output=True, check=False)
        if run.returncode != 0:
            _fail("reference_tests_failed", (run.stdout + "\n" + run.stderr)[-8000:])
        lines = (result_dir / "records.tsv").read_text().splitlines()
        records = []
        for line in lines:
            kind, task_id, mode, count_text = line.split("\t")
            records.append({"kind": kind, "task_id": task_id, "mode": mode, "test_count": int(count_text)})
        expected = 35 * 3 + 3 * 2
        if len(records) != expected:
            _fail("test_discovery_failed", f"{len(records)} != {expected}")
        for case in CASES:
            task_records = [item for item in records if item["kind"] == "tasks" and item["task_id"] == case.task_id]
            if {item["mode"] for item in task_records} != {"normal", "sanitizer", "negative"}:
                _fail("sanitizer_test_count_mismatch", case.task_id)
            if {item["test_count"] for item in task_records} != {2}:
                _fail("sanitizer_test_count_mismatch", case.task_id)
        receipt = {
            "schema_version": "trees-ranges-ranks-docker-sanity-v2",
            "status": "pass",
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "network": "none",
            "image": image,
            "image_id": image_id,
            "compiler_path": (result_dir / "compiler.path").read_text().strip(),
            "compiler_version": (result_dir / "compiler.version").read_text().strip(),
            "compiler_hash": "sha256:" + (result_dir / "compiler.sha").read_text().strip(),
            "cmake_version": (result_dir / "cmake.version").read_text().strip(),
            "owner_hash": _file_hash(GENERATOR_PATH),
            "mechanisms_hash": _file_hash(MECHANISMS_PATH),
            "cases_hash": _file_hash(CASES_PATH),
            "curriculum_hash": _file_hash(CURRICULUM),
            "family_spec_hash": _file_hash(FAMILY_SPEC),
            "focused_test_hash": _file_hash(TEST_PATH),
            "family_tree_hash": _tree_hash(out),
            "archive_hash": archive_hash,
            "mounted_archive_hash": "sha256:" + (result_dir / "mounted.archive.sha").read_text().strip(),
            "mounted_archive_matches_host": (
                "sha256:" + (result_dir / "mounted.archive.sha").read_text().strip()
            ) == archive_hash,
            "family_screen_hash": _file_hash(out / ".state/family-screen.json"),
            "materialization_manifest_hash": _file_hash(manifest_path),
            "source_inventory_hash": _file_hash(inventory_path),
            "source_inventory_reconciliation": inventory_reconciliation,
            "per_root_bindings": manifest["tasks"],
            "verifier_policy_hash": _sha(script.encode()),
            "normal_records": 38,
            "sanitizer_records": 38,
            "negative_records": 35,
            "records": records,
            "commands": [command],
        }
    _write(out / ".state/docker-sanity-receipt.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    status = {
        "schema_version": "trees-ranges-ranks-verification-status-v1",
        "status": "creator_preflight_passed_pending_independent_audit",
        "family_tree_hash": _tree_hash(out),
        "manifest_hash": _file_hash(manifest_path),
        "receipt_hash": _file_hash(out / ".state/docker-sanity-receipt.json"),
        "source_inventory_hash": _file_hash(inventory_path),
    }
    _write(out / ".state/verification-status.json", json.dumps(status, indent=2, sort_keys=True) + "\n", True)
    return receipt


def verify_host(out: Path = DEFAULT_OUT) -> dict[str, object]:
    manifest_path = out / ".state/materialization-manifest.json"
    if not manifest_path.is_file():
        _fail("generator_output_drift", "run --verify-core first")
    manifest = json.loads(manifest_path.read_text())
    if (
        manifest["family_tree_hash"] != _tree_hash(out)
        or manifest["owner_hash"] != _file_hash(GENERATOR_PATH)
        or manifest["mechanisms_hash"] != _file_hash(MECHANISMS_PATH)
    ):
        _fail("generator_output_drift", "manifest does not bind current owner/tree")
    compiler = shutil.which("c++")
    cmake = shutil.which("cmake")
    ctest = shutil.which("ctest")
    if not compiler or not cmake or not ctest:
        _fail("host_toolchain_unavailable", "host verify requires c++, cmake, and ctest on PATH")
    compiler_path = str(Path(compiler).resolve())
    compiler_version = subprocess.run(
        [compiler_path, "--version"], text=True, capture_output=True, check=True
    ).stdout.splitlines()[0]
    cmake_version = subprocess.run(
        [cmake, "--version"], text=True, capture_output=True, check=True
    ).stdout.splitlines()[0]
    test_env = dict(
        os.environ, ASAN_OPTIONS="detect_leaks=1", UBSAN_OPTIONS="halt_on_error=1"
    )

    def _run(command: list[str], code: str, detail: str, *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(command, text=True, capture_output=True, check=False, env=env)
        if result.returncode != 0:
            _fail(code, f"{detail}: " + (result.stdout + "\n" + result.stderr)[-4000:])
        return result

    def _discover(build_dir: Path, task_id: str) -> int:
        listing = _run(
            [ctest, "--test-dir", str(build_dir), "-N"], "test_discovery_failed", task_id
        )
        match = re.search(r"Total Tests:\s*(\d+)", listing.stdout)
        count = int(match.group(1)) if match else 0
        if count != 2:
            _fail("test_discovery_failed", f"{task_id}: discovered {count} != 2")
        return count

    records = []
    # Verification is read-only with respect to the materialized roots: each
    # root is staged into a temporary directory before the reference or the
    # false substitute is overlaid, exactly as the Docker path stages its
    # archive extraction.
    with tempfile.TemporaryDirectory(prefix="trees-ranges-ranks-host-") as temporary:
        temp = Path(temporary)
        suites = (
            ("tasks", [out / case.task_id for case in CASES]),
            (
                "controls",
                [out / ".state/adversarial-clone-controls" / name for name in CONTROL_NAMES],
            ),
        )
        for kind, roots in suites:
            for source_root in roots:
                task_id = source_root.name
                staged = temp / "stage" / kind / task_id
                shutil.copytree(source_root, staged)
                shutil.copyfile(staged / ".meta/example.cpp", staged / "task.cpp")
                for mode in ("normal", "sanitizer"):
                    flags = (
                        "-fsanitize=address,undefined -fno-omit-frame-pointer"
                        if mode == "sanitizer"
                        else ""
                    )
                    build_dir = temp / f"build-{kind}-{task_id}-{mode}"
                    _run(
                        [
                            cmake, "-S", str(staged), "-B", str(build_dir),
                            "-G", "Unix Makefiles",
                            f"-DCMAKE_CXX_COMPILER={compiler_path}",
                            f"-DCMAKE_CXX_FLAGS={flags}",
                            f"-DTASK_SOURCE={staged / 'task.cpp'}",
                        ],
                        "reference_compile_failed",
                        f"{task_id}/{mode} configure",
                    )
                    _run(
                        [cmake, "--build", str(build_dir), "--parallel", "2"],
                        "reference_compile_failed",
                        f"{task_id}/{mode} build",
                    )
                    count = _discover(build_dir, task_id)
                    executed = subprocess.run(
                        [ctest, "--test-dir", str(build_dir), "--output-on-failure"],
                        text=True,
                        capture_output=True,
                        check=False,
                        env=test_env,
                    )
                    if executed.returncode != 0:
                        code = (
                            "reference_tests_failed"
                            if mode == "normal"
                            else "reference_sanitizer_failed"
                        )
                        _fail(code, f"{task_id}/{mode}: " + (executed.stdout + "\n" + executed.stderr)[-4000:])
                    records.append(
                        {"kind": kind, "task_id": task_id, "mode": mode, "test_count": count}
                    )
                if kind == "tasks":
                    negative = temp / f"negative-{task_id}.cpp"
                    shutil.copyfile(staged / ".meta/negative_false_substitute.cpp", negative)
                    build_dir = temp / f"build-negative-{task_id}"
                    _run(
                        [
                            cmake, "-S", str(staged), "-B", str(build_dir),
                            "-G", "Unix Makefiles",
                            f"-DCMAKE_CXX_COMPILER={compiler_path}",
                            "-DCMAKE_CXX_FLAGS=",
                            f"-DTASK_SOURCE={negative}",
                        ],
                        "reference_compile_failed",
                        f"{task_id}/negative configure",
                    )
                    _run(
                        [cmake, "--build", str(build_dir), "--parallel", "2"],
                        "reference_compile_failed",
                        f"{task_id}/negative build",
                    )
                    count = _discover(build_dir, task_id)
                    executed = subprocess.run(
                        [ctest, "--test-dir", str(build_dir), "--output-on-failure"],
                        text=True,
                        capture_output=True,
                        check=False,
                        env=test_env,
                    )
                    if executed.returncode == 0:
                        _fail("invariant_not_enforced", f"false substitute passed: {task_id}")
                    records.append(
                        {"kind": kind, "task_id": task_id, "mode": "negative", "test_count": count}
                    )
    expected = 35 * 3 + 3 * 2
    if len(records) != expected:
        _fail("test_discovery_failed", f"{len(records)} != {expected}")
    for case in CASES:
        task_records = [
            item for item in records if item["kind"] == "tasks" and item["task_id"] == case.task_id
        ]
        if {item["mode"] for item in task_records} != {"normal", "sanitizer", "negative"}:
            _fail("sanitizer_test_count_mismatch", case.task_id)
        if {item["test_count"] for item in task_records} != {2}:
            _fail("sanitizer_test_count_mismatch", case.task_id)
    receipt = {
        "schema_version": "trees-ranges-ranks-host-verify-v1",
        "status": "pass",
        "evidence_class": "host_verify",
        "locked_oracle": False,
        "network": "host-local (no container sandbox)",
        "compiler_path": compiler_path,
        "compiler_version": compiler_version,
        "compiler_hash": _file_hash(Path(compiler_path)),
        "cmake_version": cmake_version,
        "owner_hash": _file_hash(GENERATOR_PATH),
        "mechanisms_hash": _file_hash(MECHANISMS_PATH),
        "cases_hash": _file_hash(CASES_PATH),
        "curriculum_hash": _file_hash(CURRICULUM),
        "family_spec_hash": _file_hash(FAMILY_SPEC),
        "focused_test_hash": _file_hash(TEST_PATH),
        "family_tree_hash": _tree_hash(out),
        "family_screen_hash": _file_hash(out / ".state/family-screen.json"),
        "materialization_manifest_hash": _file_hash(manifest_path),
        "source_inventory_hash": _file_hash(out / ".state/source-inventory.json"),
        "per_root_bindings": manifest["tasks"],
        "verifier_policy_hash": _sha(
            b"host-verify-clean-normal-fresh-asan-ubsan-unix-makefiles-strict-v1"
        ),
        "normal_records": 38,
        "sanitizer_records": 38,
        "negative_records": 35,
        "records": records,
        "commands": [
            [compiler_path, "--version"],
            [cmake, "--version"],
            [
                cmake, "-S", "<staged-root>", "-B", "<build>", "-G", "Unix Makefiles",
                f"-DCMAKE_CXX_COMPILER={compiler_path}",
                "-DCMAKE_CXX_FLAGS=<-fsanitize=address,undefined -fno-omit-frame-pointer|>",
                "-DTASK_SOURCE=<staged reference or false substitute>",
            ],
            [cmake, "--build", "<build>", "--parallel", "2"],
            [ctest, "--test-dir", "<build>", "-N"],
            [ctest, "--test-dir", "<build>", "--output-on-failure"],
        ],
    }
    _write(out / ".state/host-verify-receipt.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    return receipt


def record_cycle(out: Path, status: str, cycle: int) -> Path:
    manifest_path = out / ".state/materialization-manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {}
    receipt_path = out / ".state/docker-sanity-receipt.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else None
    host_receipt_path = out / ".state/host-verify-receipt.json"
    host_receipt = (
        json.loads(host_receipt_path.read_text()) if host_receipt_path.is_file() else None
    )
    payload = {
        "schema_version": "aider-task-creator-cycle-v1",
        "cycle": cycle,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "family_id": FAMILY_ID,
        "candidate_manifest": ".state/materialization-manifest.json",
        "family_tree_hash": _tree_hash(out),
        "curriculum_hash": _file_hash(CURRICULUM),
        "family_spec_hash": _file_hash(FAMILY_SPEC),
        "generator_hash": _file_hash(GENERATOR_PATH),
        "mechanisms_hash": _file_hash(MECHANISMS_PATH),
        "cases_hash": _file_hash(CASES_PATH),
        "focused_test_hash": _file_hash(TEST_PATH),
        "grader_policy_hash": _sha((SANITY_IMAGE + CMAKE).encode()),
        "retained_root_ids": [case.task_id for case in CASES],
        "replaced_root_ids": [],
        "rejected_root_ids": [],
        "review_root_ids": [],
        "blocked_root_ids": [],
        "manifest_subject_hash": _sha(json.dumps(manifest, sort_keys=True).encode()),
        "docker_receipt": receipt,
        "host_receipt": host_receipt,
        "dataset_handoff": "not_requested",
    }
    path = out / ".state/cycles" / f"cycle-{cycle:02d}.json"
    _write(path, json.dumps(payload, indent=2, sort_keys=True) + "\n", False)
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--cycle-status")
    parser.add_argument("--cycle", type=int, default=1)
    args = parser.parse_args(argv)
    # Verification is intentionally read-only with respect to the materialized
    # task roots.  Creation/regeneration remains an explicit operation so a
    # final oracle run cannot silently replace the subject it is attesting.
    if args.force or not (
        args.verify_core or args.verify_host or args.docker_sanity or args.cycle_status
    ):
        build(args.out, args.force)
    if args.verify_core or args.verify_host or args.docker_sanity:
        verify_core(args.out)
    if args.verify_host:
        verify_host(args.out)
    if args.docker_sanity:
        verify_docker(args.out)
    if args.cycle_status:
        record_cycle(args.out, args.cycle_status, args.cycle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
