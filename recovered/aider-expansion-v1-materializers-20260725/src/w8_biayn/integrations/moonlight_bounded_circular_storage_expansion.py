"""Materialize and verify the 60-root bounded/circular storage expansion."""
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
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_sft import build_assistant_response, load_example_files_from_config
from w8_biayn.integrations.moonlight_bounded_circular_storage_cases import CASES, Case

DEFAULT_OUT=Path(".w8-biayn/data/aider-tasks-expansion-v1/state-concurrency/bounded-circular-storage")
EXPANSION_ROOT=Path(".w8-biayn/data/aider-tasks-expansion-v1")
LEGACY_ROOT=Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT=Path(".w8-biayn/data/aider-tasks-reverify")
CURRICULUM=Path("docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_BOUNDED_CIRCULAR_STORAGE_EXPANSION_CURRICULUM.md")
GENERATOR_PATH=Path("src/w8_biayn/integrations/moonlight_bounded_circular_storage_expansion.py")
CASES_PATH=Path("src/w8_biayn/integrations/moonlight_bounded_circular_storage_cases.py")
REPLACEMENTS_PATH=Path("src/w8_biayn/integrations/moonlight_bounded_circular_storage_replacements.py")
OVERRIDES_PATH=Path("src/w8_biayn/integrations/moonlight_bounded_circular_storage_cycle04.py")
CYCLE05_PATH=Path("src/w8_biayn/integrations/moonlight_bounded_circular_storage_cycle05.py")
TEST_PATH=Path("tests/test_moonlight_bounded_circular_storage_expansion.py")
FAMILY_ID="aider-expansion-v1-bounded-circular-storage-v1"
SANITY_IMAGE="w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
HOLDOUTS=frozenset({"all-your-base","allergies","bank-account","binary-search-tree","circular-buffer","clock","complex-numbers","crypto-square","diamond","dnd-character","gigasecond","grade-school","kindergarten-garden","knapsack","linked-list","meetup","parallel-letter-frequency","perfect-numbers","phone-number","queen-attack","robot-name","space-age","spiral-matrix","sublist","yacht","zebra-puzzle"})
DIMENSIONS=("public_api","owned_state_algorithm","mutation_selection_rules","invalid_boundary_behavior","reference_control_flow","deterministic_oracle","topic_negative_fixture")

COMMON_HEADER='''#pragma once
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <limits>
#include <map>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <tuple>
#include <utility>
#include <vector>
'''
TEST_PRE='''#include <iostream>
#include <stdexcept>
#include <vector>
static int failures=0;
#define CHECK(...) do{if(!(__VA_ARGS__)){std::cerr<<"CHECK failed: " #__VA_ARGS__ "\\n";++failures;}}while(false)
'''
CMAKE='''cmake_minimum_required(VERSION 3.16)
project(bounded_circular_storage LANGUAGES CXX)
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
if(DEFINED NEGATIVE_SOURCE)
 add_executable(negative_visible "${NEGATIVE_SOURCE}" task_visible_test.cpp)
 add_executable(negative_hidden "${NEGATIVE_SOURCE}" .meta/task_hidden_test.cpp)
 foreach(name visible hidden)
  target_include_directories(negative_${name} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
   target_compile_options(negative_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
 endforeach()
endif()
'''

def fail(code:str,detail:str)->None: raise RuntimeError(f"{code}: {detail}")
def sha(data:bytes)->str: return "sha256:"+hashlib.sha256(data).hexdigest()
def file_hash(path:Path)->str: return sha(path.read_bytes())
def tree_hash(root:Path,include_state:bool=False)->str:
 d=hashlib.sha256()
 if not root.is_dir(): return "not_available"
 for path in sorted(p for p in root.rglob("*") if p.is_file()):
  relative=path.relative_to(root)
  if not include_state and ".state" in relative.parts: continue
  d.update(relative.as_posix().encode());d.update(b"\0");d.update(path.read_bytes());d.update(b"\0")
 return "sha256:"+d.hexdigest()
def write(path:Path,content:str,force:bool)->None:
 if path.exists() and path.read_text()!=content and not force: raise FileExistsError(f"{path} differs; pass --force")
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
def inventory(root:Path)->list[dict[str,str]]:
 rows=[]
 if not root.is_dir(): return rows
 for config in sorted(root.rglob(".meta/config.json")):
  if ".state" in config.parts: continue
  task=config.parent.parent
  rows.append({"task_id":task.name,"relative_root":task.relative_to(root).as_posix(),"tree_hash":tree_hash(task),"config_hash":file_hash(config)})
 return rows
def validate_out(out:Path)->None:
 resolved=out.resolve();expansion=EXPANSION_ROOT.resolve()
 if resolved==expansion or expansion not in resolved.parents: fail("unsafe_path",str(out))
 if LEGACY_ROOT.resolve() in resolved.parents or REVERIFY_ROOT.resolve() in resolved.parents: fail("unsafe_path",str(out))
 cursor=out
 while cursor!=EXPANSION_ROOT.parent and cursor!=cursor.parent:
  if cursor.is_symlink(): fail("unsafe_path",f"symlink {cursor}")
  cursor=cursor.parent

def instructions(case:Case)->str:
 return f"""# Instructions

Implement `{case.task_id}.h` and `{case.task_id}.cpp` in C++17.

## Contract

{case.contract}

## Mechanism

{case.mechanism}

## Boundaries

{case.boundary}

## Examples

The visible check exercises these cases:

```cpp
{case.visible}
```

Capacity never grows. Invalid operations leave state unchanged. Build the mechanism directly: {case.forbidden} cannot reproduce the documented behavior.
"""
def contract(case:Case)->str:
 return f"""# {case.task_id}

## Identity
New-root revision 1 in `{FAMILY_ID}`; `repair-in-place` from the initial unmaterialized design; CC0-1.0 clean-room source; benchmark screen required.

## Objective
{case.mechanism}

## Public API
```cpp
{case.header}
```

## Behavior table
{case.contract} {case.boundary}

## Implementation invariant
{case.invariant} Forbidden: {case.forbidden}.

## Starter and reference
Complete throwing starter and independent case-owned reference.

## Tests
Visible behavior, private invariant trace, and compiling wrong substitute: {case.negative_reason}

## Files and metadata
Header then source; references map by extension; private assets are never prompt-visible.

## Build/oracle
C++17 strict warnings; two normal and two fresh sanitizer CTests in the pinned network-disabled image.

## Family/contamination
1,770 family pairs, both existing trees, other expansion roots, and 26 official holdouts.

## Optional dataset handoff
`not_requested`.

## Acceptance
Reference passes and the compiling wrong substitute is rejected in both modes.
"""
def render(case:Case)->dict[str,str]:
 header=COMMON_HEADER+"\nnamespace bounded_storage {\n"+case.header+"\n}\n"
 starter=f'#include "{case.task_id}.h"\nnamespace bounded_storage {{\n{case.starter}\n}}\n'
 reference=f'#include "{case.task_id}.h"\nnamespace bounded_storage {{\n{case.reference}\n}}\n'
 negative=reference.replace(case.negative_old,case.negative_new,1)
 if negative==reference: fail("invariant_not_enforced",case.task_id)
 visible=TEST_PRE+f'#include "{case.task_id}.h"\nusing namespace bounded_storage;\n'+case.visible+"\n"
 hidden=TEST_PRE+f'#include "{case.task_id}.h"\nusing namespace bounded_storage;\n'+case.hidden+"\n"
 profile={name:getattr(case,name) for name in DIMENSIONS}
 config={"authors":["w8-biayn"],"blurb":case.summary,"files":{"solution":[f"{case.task_id}.h",f"{case.task_id}.cpp"],"test":["task_visible_test.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}}
 provenance={"task_id":case.task_id,"family_id":FAMILY_ID,"lineage":"new-root","origin":"repository-authored clean-room expansion","license":"CC0-1.0","count_plan_cell":"state/concurrency / bounded and circular storage with explicit capacity policies / 60","curriculum_document":str(CURRICULUM),"mechanism":case.mechanism,"semantic_profile":profile,"benchmark_separation":"The 26 official Aider C++ roots are permanent holdouts; no holdout assets were used.","status":"local task artifact; not admitted SFT data","version":1}
 return {".docs/introduction.md":f"# {case.title}\n\nBounded storage is the discipline of embedded and streaming systems: a ring buffer, a fixed-size cache, a stash that can never grow. When capacity is fixed, every policy — what to evict, when to refuse, how to wrap — is part of the observable behavior.\n\n{case.summary}\n",".docs/instructions.md":instructions(case),".meta/config.json":json.dumps(config,indent=2,sort_keys=True)+"\n",".meta/provenance.json":json.dumps(provenance,indent=2,sort_keys=True)+"\n",".meta/tests.toml":f'[visible]\ndescription="documented behavior"\n[hidden]\ndescription="boundary and invariant trace"\n[negative]\ndescription="{case.negative_reason}"\n',".meta/example.h":header,".meta/example.cpp":reference,".meta/task_hidden_test.cpp":hidden,".meta/negative_false_substitute.cpp":negative,f"{case.task_id}.h":header,f"{case.task_id}.cpp":starter,"task_visible_test.cpp":visible,"CMakeLists.txt":CMAKE}

def freeze_inventory(out:Path,force:bool)->dict[str,object]:
 relative=out.resolve().relative_to(EXPANSION_ROOT.resolve()).as_posix()
 groups={"legacy":inventory(LEGACY_ROOT),"reverify":inventory(REVERIFY_ROOT),"expansion_before":[r for r in inventory(EXPANSION_ROOT) if not r["relative_root"].startswith(relative+"/")]}
 payload={"schema_version":"bounded-circular-source-inventory-v1","captured_at":datetime.now(timezone.utc).isoformat(),"roots":{}}
 for name,rows in groups.items(): payload["roots"][name]={"count":len(rows),"sha256":sha(json.dumps(rows,sort_keys=True,separators=(",",":")).encode()),"records":rows}
 # The inventory is a .state evidence snapshot with a fresh timestamp; always
 # refresh it so verify-only invocations work, while task output keeps its
 # drift protection through the caller's force flag.
 write(out/".state/source-inventory.json",json.dumps(payload,indent=2,sort_keys=True)+"\n",True);return payload
def write_controls(out:Path,force:bool)->None:
 base=next(c for c in CASES if c.task_id=="rollback-spill-routing-banks");files=render(base)
 transforms={
  "domain-identifier-renamed":lambda s:s.replace("spill","overflow_route").replace("Spill","OverflowRoute"),
  "constants-policy-only":lambda s:s.replace("({1,2,1})","({1,3,1})"),
  "opposite-end-selection":lambda s:s.replace("front","back").replace("FIFO","LIFO").replace("oldest","newest").replace("s.take(1)==8","s.take(1)==9").replace("({{3},{1,2},{}})","({{1},{2,3},{}})"),
 }
 records={}
 for name,transform in transforms.items():
  root=out/".state/adversarial-clone-controls"/name
  if force and root.is_dir():shutil.rmtree(root)
  changed=[]
  for relative,content in files.items():
   mutated=transform(content)
   if mutated!=content: changed.append(relative)
   target_relative=transform(relative) if name=="domain-identifier-renamed" else relative
   write(root/target_relative,mutated,force)
  if not changed: fail("adversarial_control_invalid",name)
  records[name]={"base_task_id":base.task_id,"changed_files":changed,"tree_hash":tree_hash(root,True)}
 write(out/".state/adversarial-clone-controls/manifest.json",json.dumps({"schema_version":"bounded-circular-controls-v1","controls":records},indent=2,sort_keys=True)+"\n",force)
def build(out:Path=DEFAULT_OUT,force:bool=False)->tuple[Path,...]:
 validate_out(out)
 if len(CASES)!=60 or len({c.task_id for c in CASES})!=60: fail("duplicate_task",f"case count {len(CASES)}")
 if force and out.is_dir():
  current={c.task_id for c in CASES};rejected=out/".state/rejected-cycle-04";rejected.mkdir(parents=True,exist_ok=True)
  for config in sorted(out.glob("*/.meta/provenance.json")):
   root=config.parent.parent
   if root.name in current:continue
   provenance=json.loads(config.read_text())
   if provenance.get("family_id")!=FAMILY_ID:fail("generator_output_drift",f"foreign root {root}")
   destination=rejected/root.name
   if destination.exists():
    if tree_hash(destination)!=tree_hash(root):fail("generator_output_drift",f"rejected archive mismatch {root.name}")
    shutil.rmtree(root)
   else:shutil.move(str(root),str(destination))
 frozen=freeze_inventory(out,force);existing={r["task_id"] for g in frozen["roots"].values() for r in g["records"]};collisions=existing&{c.task_id for c in CASES}
 if collisions: fail("duplicate_task",",".join(sorted(collisions)))
 roots=[]
 for case in CASES:
  root=out/case.task_id
  if root.exists() and any(p.is_symlink() for p in root.rglob("*")): fail("unsafe_path",str(root))
  for relative,content in render(case).items(): write(root/relative,content,force)
  write(out/".state/contracts"/f"{case.task_id}.md",contract(case),force);roots.append(root)
 write_controls(out,force);return tuple(roots)

def normalized(text:str)->tuple[str,...]:
 text=re.sub(r"/\*.*?\*/|//[^\n]*"," ",text,flags=re.S);text=re.sub(r'"(?:\\.|[^"\\])*"'," LIT ",text);text=re.sub(r"\b(?:true|false)\b|-?\d+(?:[uUlL]+)?"," LIT ",text)
 tokens=re.findall(r"[A-Za-z_][A-Za-z_0-9]*|<=|>=|==|!=|&&|\|\||[-+*/%<>{}()[\];,?:=.]",text)
 keep={"alignof","auto","bool","break","case","catch","char","class","const","continue","decltype","default","do","double","else","enum","explicit","false","float","for","friend","if","int","long","namespace","new","noexcept","nullptr","operator","private","protected","public","return","short","signed","sizeof","static","struct","switch","template","this","throw","true","try","typedef","typename","union","unsigned","using","virtual","void","volatile","while","std","array","deque","map","set","vector","optional","pair","tuple","string","string_view","size_t","uint8_t","uint16_t","uint32_t","uint64_t","int64_t","numeric_limits","nullopt","move","min","max","sort","find","find_if","lower_bound","upper_bound","copy","copy_n","fill","count_if","any_of","all_of","remove","remove_if","unique","reverse","rotate","tie","get","begin","end","rbegin","rend","push_back","push_front","pop_back","pop_front","erase","insert","clear","reset","value","has_value","ENDPOINT","LIT"}
 endpoints={"front":"ENDPOINT","back":"ENDPOINT","first":"ENDPOINT","last":"ENDPOINT","left":"ENDPOINT","right":"ENDPOINT","spill":"ENDPOINT","overflow_route":"ENDPOINT","tombstone":"ENDPOINT","grave_marker":"ENDPOINT","push_front":"PUSH_ENDPOINT","push_back":"PUSH_ENDPOINT","pop_front":"POP_ENDPOINT","pop_back":"POP_ENDPOINT"}
 return tuple(endpoints.get(token.lower(),token if token in keep or not re.match(r"^[A-Za-z_]",token) else "ID") for token in tokens)
def material(root:Path)->dict[str,tuple[str,...]]:
 h=next(root.glob("*.h")).read_text();r=(root/".meta/example.cpp").read_text();i=(root/".docs/instructions.md").read_text();v=(root/"task_visible_test.cpp").read_text();x=(root/".meta/task_hidden_test.cpp").read_text();n=(root/".meta/negative_false_substitute.cpp").read_text();private=h.split("private:",1)[1] if "private:" in h else h
 raw={"public_api":h.split("private:",1)[0],"owned_state_algorithm":private+r,"mutation_selection_rules":i+r,"invalid_boundary_behavior":i+x,"reference_control_flow":r,"deterministic_oracle":v+x,"topic_negative_fixture":n+v+x}
 return {k:normalized(v) for k,v in raw.items()}
def pair(left:Path,right:Path)->dict[str,bool]:
 a,b=material(left),material(right);return {d:a[d]!=b[d] for d in DIMENSIONS}
def semantic_screen(out:Path)->dict[str,object]:
 roots=sorted((out/c.task_id for c in CASES),key=lambda p:p.name);pairs=[]
 for index,left in enumerate(roots):
  for right in roots[index+1:]:
   decisions=pair(left,right)
   if not all(decisions.values()): fail("duplicate_family",f"{left.name} vs {right.name}: {decisions}")
   pairs.append({"left":left.name,"right":right.name,"decisions":decisions})
 if len(pairs)!=1770: fail("duplicate_family",f"pair count {len(pairs)}")
 base=out/"rollback-spill-routing-banks";controls={}
 for name in ("domain-identifier-renamed","constants-policy-only","opposite-end-selection"):
  decisions=pair(base,out/".state/adversarial-clone-controls"/name)
  if any(decisions.values()): fail("duplicate_family",f"clone escaped {name}: {decisions}")
  controls[name]={"decisions":decisions,"production_rejected":True}
 return {"status":"pass","root_count":60,"pair_count":1770,"dimensions":list(DIMENSIONS),"pairs":pairs,"controls":controls}

def _ngrams(tokens:tuple[str,...],n:int=5)->set[tuple[str,...]]:
 return {tokens[i:i+n] for i in range(max(0,len(tokens)-n+1))}
def _similarity(left:str,right:str)->float:
 a,b=_ngrams(normalized(left)),_ngrams(normalized(right));return len(a&b)/max(1,len(a|b))
def _gram_similarity(left:set[tuple[str,...]],right:set[tuple[str,...]])->float:
 return len(left&right)/max(1,len(left|right))
def _semantic_text(root:Path)->str:
 paths=[]
 for pattern in (".docs/*.md","*.h",".meta/example.cpp","task_visible_test.cpp",".meta/task_hidden_test.cpp"):paths.extend(root.glob(pattern))
 return "\n".join(p.read_text(errors="replace") for p in sorted(set(paths)))
def cross_tree_screen(out:Path)->dict[str,object]:
 current={c.task_id:_semantic_text(out/c.task_id) for c in CASES};grams={k:_ngrams(normalized(v)) for k,v in current.items()};highest={k:{"similarity":0.0,"other":"not_available"} for k in current};exact={sha(v.encode()):k for k,v in current.items()};screened=0
 for base in (LEGACY_ROOT,REVERIFY_ROOT,EXPANSION_ROOT):
  if not base.is_dir():continue
  for config in sorted(base.rglob(".meta/config.json")):
   root=config.parent.parent
   if out.resolve() in root.resolve().parents or ".state" in root.parts:continue
   if root.name in current:fail("duplicate_task",f"existing ID {root.name}")
   other=_semantic_text(root);other_grams=_ngrams(normalized(other));screened+=1
   if sha(other.encode()) in exact:fail("duplicate_family",f"exact material {root}")
   for task_id,ours in grams.items():
    score=_gram_similarity(ours,other_grams)
    if score>highest[task_id]["similarity"]:highest[task_id]={"similarity":round(score,6),"other":root.as_posix()}
    if score>=0.92:fail("duplicate_family",f"near clone {task_id} vs {root}: {score:.4f}")
 holdout_root=Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
 if not holdout_root.is_dir():fail("benchmark_assets_missing",str(holdout_root))
 holdouts=[]
 for task_id in sorted(HOLDOUTS):
  root=holdout_root/task_id
  if not root.is_dir():fail("benchmark_assets_missing",str(root))
  files=sorted(p for p in root.rglob("*") if p.is_file() and p.suffix in {".cpp",".h",".md"});other="\n".join(p.read_text(errors="replace") for p in files);other_grams=_ngrams(normalized(other));best=max((_gram_similarity(ours,other_grams) for ours in grams.values()),default=0.0)
  if best>=0.92:fail("benchmark_contamination",f"{task_id}: {best:.4f}")
  holdouts.append({"task_id":task_id,"file_count":len(files),"content_hash":sha(other.encode()),"highest_similarity":round(best,6)})
 return {"status":"pass","screened_existing_roots":screened,"threshold":0.92,"highest_existing_by_task":highest,"holdout_checkout":str(holdout_root),"holdouts":holdouts}
def verify_core(out:Path=DEFAULT_OUT)->None:
 rows=[];prompts=set();references=set()
 for case in CASES:
  root=out/case.task_id;config=json.loads((root/".meta/config.json").read_text());expected=[f"{case.task_id}.h",f"{case.task_id}.cpp"]
  if config["files"]["solution"]!=expected: fail("target_reference_mismatch",case.task_id)
  task=load_task(root);prompt=build_prompt(task)
  if any(m in prompt for m in (".meta/","CMakeLists","task_visible_test","provenance","negative_false")): fail("prompt_contract_incomplete",case.task_id)
  answer=build_assistant_response(task,load_example_files_from_config(root))
  if not answer.startswith(f"{case.task_id}.h\n```") or f"{case.task_id}.cpp\n```" not in answer: fail("target_reference_mismatch",case.task_id)
  ph,rh=sha(prompt.encode()),file_hash(root/".meta/example.cpp")
  if ph in prompts or rh in references: fail("duplicate_family",f"duplicate prompt/reference {case.task_id}")
  prompts.add(ph);references.add(rh);rows.append({"task_id":case.task_id,"mechanism":case.mechanism,"tree_hash":tree_hash(root),"prompt_hash":ph,"reference_hash":rh,"starter_hash":file_hash(root/f"{case.task_id}.cpp"),"visible_test_hash":file_hash(root/"task_visible_test.cpp"),"hidden_test_hash":file_hash(root/".meta/task_hidden_test.cpp"),"negative_hash":file_hash(root/".meta/negative_false_substitute.cpp"),"contract_hash":file_hash(out/".state/contracts"/f"{case.task_id}.md"),"primary_core_objective":"achieved_pending_execution"})
 if {c.task_id for c in CASES}&HOLDOUTS: fail("benchmark_id_overlap","holdout ID")
 manifest={"schema_version":"bounded-circular-materialization-v1","family_id":FAMILY_ID,"task_count":60,"owner_hash":file_hash(GENERATOR_PATH),"case_catalog_hash":file_hash(CASES_PATH),"replacements_hash":file_hash(REPLACEMENTS_PATH),"cycle04_overrides_hash":file_hash(OVERRIDES_PATH),"cycle05_repairs_hash":file_hash(CYCLE05_PATH),"curriculum_hash":file_hash(CURRICULUM),"focused_test_hash":file_hash(TEST_PATH),"family_tree_hash":tree_hash(out),"tasks":rows,"screen":{"prompt_boundary":"pass","reference_mapping":"pass","diversity":semantic_screen(out),"benchmark_ids":"pass","cross_tree":cross_tree_screen(out)},"strongest_local_status":"pending_execution","dataset_handoff":"not_requested"}
 write(out/".state/materialization-manifest.json",json.dumps(manifest,indent=2,sort_keys=True)+"\n",True)

def archive_family(out:Path,target:Path)->str:
 with tarfile.open(target,"w",format=tarfile.PAX_FORMAT) as archive:
  roots=[out/c.task_id for c in CASES]+[out/".state/adversarial-clone-controls"/n for n in ("domain-identifier-renamed","constants-policy-only","opposite-end-selection")]
  for root in roots:
   prefix="tasks" if root.parent==out else "controls"
   for path in sorted(p for p in root.rglob("*") if p.is_file()):
    info=archive.gettarinfo(str(path),arcname=f"{prefix}/{root.name}/{path.relative_to(root).as_posix()}")
    info.uid=info.gid=info.mtime=0;info.uname=info.gname="";info.mode=0o644
    with path.open("rb") as handle:archive.addfile(info,handle)
 return file_hash(target)
def mounted_task_digest(out:Path)->str:
 lines=[]
 for case in sorted(CASES,key=lambda c:c.task_id):
  root=out/case.task_id
  for path in sorted(p for p in root.rglob("*") if p.is_file()):
   lines.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  tasks/{case.task_id}/{path.relative_to(root).as_posix()}\n")
 return sha("".join(lines).encode())

DOCKER_SCRIPT=r'''set -Eeuo pipefail
mkdir -p /work /result
tar -xf /input/family.tar -C /work
compiler="$(command -v c++)"
printf '%s\n' "$compiler" > /result/compiler.path
c++ --version | head -1 > /result/compiler.version
cmake --version | head -1 > /result/cmake.version
sha256sum "$compiler" | awk '{print $1}' > /result/compiler.sha
(cd /work && find tasks -type f -print0 | sort -z | xargs -0 sha256sum > /result/mounted.files)
sha256sum /result/mounted.files | awk '{print $1}' > /result/mounted.digest
: > /result/records.tsv
verify_one(){
 kind="$1"; task="$2"; root="/work/$kind/$task"
 cp "$root/.meta/example.cpp" "$root/task.cpp"
 for mode in normal sanitizer; do
  build="/tmp/build-${kind}-${task}-${mode}"; flags=""
  if [ "$mode" = sanitizer ]; then flags="-fsanitize=address,undefined -fno-omit-frame-pointer"; fi
  cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER="$compiler" -DCMAKE_CXX_FLAGS="$flags" -DTASK_SOURCE="$root/task.cpp" >/tmp/configure.log
  cmake --build "$build" --parallel 2 >/tmp/build.log
  count="$(ctest --test-dir "$build" -N | awk '/Total Tests:/ {print $3}')"; test "$count" = 2
  ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir "$build" --output-on-failure >/tmp/test.log 2>&1 || { cat /tmp/test.log; exit 82; }
  printf '%s\t%s\t%s\t%s\n' "$kind" "$task" "$mode" "$count" >> /result/records.tsv
 done
 if [ "$kind" = tasks ]; then
  negative="/tmp/negative-${task}.cpp"; cp "$root/.meta/negative_false_substitute.cpp" "$negative"
  for mode in negative-normal negative-sanitizer; do
   build="/tmp/build-${mode}-${task}"; flags=""
   if [ "$mode" = negative-sanitizer ]; then flags="-fsanitize=address,undefined -fno-omit-frame-pointer"; fi
   cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER="$compiler" -DCMAKE_CXX_FLAGS="$flags" -DTASK_SOURCE="$negative" >/tmp/configure.log
   cmake --build "$build" --parallel 2 >/tmp/build.log
   count="$(ctest --test-dir "$build" -N | awk '/Total Tests:/ {print $3}')"; test "$count" = 2
   if ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir "$build" --output-on-failure >/tmp/negative.log 2>&1; then echo "negative accepted: $task/$mode"; exit 81; fi
   printf '%s\t%s\t%s\t%s\n' "$kind" "$task" "$mode" "$count" >> /result/records.tsv
  done
 fi
}
for root in /work/tasks/*; do verify_one tasks "$(basename "$root")"; done
for root in /work/controls/*; do verify_one controls "$(basename "$root")"; done
'''

def verify_docker(out:Path=DEFAULT_OUT,image:str=SANITY_IMAGE)->dict[str,object]:
 if image!=SANITY_IMAGE:fail("generator_output_drift",image)
 manifest_path=out/".state/materialization-manifest.json"
 if not manifest_path.is_file():fail("generator_output_drift","run --verify-core first")
 manifest=json.loads(manifest_path.read_text())
 if manifest["family_tree_hash"]!=tree_hash(out) or manifest["owner_hash"]!=file_hash(GENERATOR_PATH):fail("generator_output_drift","manifest owner/tree mismatch")
 inspect=subprocess.run(["docker","image","inspect",image,"--format","{{.Id}}"],text=True,capture_output=True,check=False)
 if inspect.returncode:fail("docker_unavailable",inspect.stderr.strip())
 image_id=inspect.stdout.strip()
 with tempfile.TemporaryDirectory(prefix="bounded-circular-") as temporary:
  temp=Path(temporary);tar_path=temp/"family.tar";result=temp/"result";result.mkdir();archive_hash=archive_family(out,tar_path);expected_mounted=mounted_task_digest(out)
  command=["docker","run","--rm","--network","none","-v",f"{tar_path}:/input/family.tar:ro","-v",f"{result}:/result",image,"bash","-lc",DOCKER_SCRIPT]
  run=subprocess.run(command,text=True,capture_output=True,check=False)
  if run.returncode:fail("reference_tests_failed",(run.stdout+"\n"+run.stderr)[-12000:])
  actual_mounted="sha256:"+(result/"mounted.digest").read_text().strip()
  if actual_mounted!=expected_mounted:fail("grader_mount_hash_mismatch",f"{actual_mounted} != {expected_mounted}")
  records=[]
  for line in (result/"records.tsv").read_text().splitlines():
   kind,task_id,mode,count=line.split("\t");records.append({"kind":kind,"task_id":task_id,"mode":mode,"test_count":int(count)})
  if len(records)!=246:fail("test_discovery_failed",f"record count {len(records)}")
  for case in CASES:
   rows=[r for r in records if r["kind"]=="tasks" and r["task_id"]==case.task_id]
   if {r["mode"] for r in rows}!={"normal","sanitizer","negative-normal","negative-sanitizer"} or {r["test_count"] for r in rows}!={2}:fail("sanitizer_test_count_mismatch",case.task_id)
  receipt={"schema_version":"bounded-circular-docker-sanity-v3","status":"pass","evidence_class":"docker_sanity","locked_oracle":False,"network":"none","image":image,"image_id":image_id,"compiler":{"path":(result/"compiler.path").read_text().strip(),"version":(result/"compiler.version").read_text().strip(),"sha256":"sha256:"+(result/"compiler.sha").read_text().strip()},"cmake":(result/"cmake.version").read_text().strip(),"owner_hash":file_hash(GENERATOR_PATH),"case_catalog_hash":file_hash(CASES_PATH),"replacements_hash":file_hash(REPLACEMENTS_PATH),"cycle04_overrides_hash":file_hash(OVERRIDES_PATH),"cycle05_repairs_hash":file_hash(CYCLE05_PATH),"family_tree_hash":tree_hash(out),"archive_hash":archive_hash,"mounted_task_digest":actual_mounted,"host_expected_mounted_task_digest":expected_mounted,"normal_reference_count":63,"sanitizer_reference_count":63,"negative_normal_count":60,"negative_sanitizer_count":60,"negative_fixture_count":60,"test_count_per_mode":2,"records":records,"command":["docker","run","--rm","--network","none","<binds>",image]}
 write(out/".state/docker-sanity.json",json.dumps(receipt,indent=2,sort_keys=True)+"\n",True)
 manifest["strongest_local_status"]="creator_preflight_passed";manifest["docker_sanity_hash"]=file_hash(out/".state/docker-sanity.json");write(manifest_path,json.dumps(manifest,indent=2,sort_keys=True)+"\n",True)
 return receipt

def _run_command(command:list[str],env:dict[str,str]|None=None,cwd:Path|None=None)->subprocess.CompletedProcess[str]:
 return subprocess.run(command,text=True,capture_output=True,check=False,env=env,cwd=cwd)
def _discovered_count(build:Path)->int:
 probe=_run_command(["ctest","--test-dir",str(build),"-N"])
 match=re.search(r"Total Tests:\s*(\d+)",probe.stdout)
 if not match:fail("test_discovery_failed",probe.stdout[-2000:]+probe.stderr[-2000:])
 return int(match.group(1))
def _host_verify_root(root:Path,work:Path,compiler:str,negative:bool)->list[dict[str,object]]:
 records=[];env=dict(os.environ);env["ASAN_OPTIONS"]="detect_leaks=1:halt_on_error=1";env["UBSAN_OPTIONS"]="halt_on_error=1"
 modes=[("normal","","reference",False),("sanitizer","-fsanitize=address,undefined -fno-omit-frame-pointer","reference",False)]
 if negative:
  modes+=[("negative-normal","","negative",True),("negative-sanitizer","-fsanitize=address,undefined -fno-omit-frame-pointer","negative",True)]
 for mode,flags,kind,must_reject in modes:
  build=work/f"build-{mode}";source=(root/".meta/example.cpp") if kind=="reference" else (root/".meta/negative_false_substitute.cpp")
  configure=_run_command(["cmake","-S",str(root),"-B",str(build),"-G","Unix Makefiles",f"-DCMAKE_CXX_COMPILER={compiler}",f"-DCMAKE_CXX_FLAGS={flags}",f"-DTASK_SOURCE={source}"])
  if configure.returncode:fail("reference_compile_failed",f"{root.name}/{mode} configure: {configure.stderr[-4000:]}")
  compiled=_run_command(["cmake","--build",str(build),"--parallel","2"])
  if compiled.returncode:
   code="reference_compile_failed" if kind=="reference" else "invariant_not_enforced"
   fail(code,f"{root.name}/{mode} build: {compiled.stderr[-4000:]}")
  count=_discovered_count(build)
  if count!=2:fail("test_discovery_failed",f"{root.name}/{mode} discovered {count}")
  tested=_run_command(["ctest","--test-dir",str(build),"--output-on-failure"],env=env)
  if must_reject:
   if tested.returncode==0:fail("invariant_not_enforced",f"negative accepted: {root.name}/{mode}")
  elif tested.returncode:
   code="reference_sanitizer_failed" if mode=="sanitizer" else "reference_tests_failed"
   fail(code,f"{root.name}/{mode}: {(tested.stdout+tested.stderr)[-4000:]}")
  records.append({"task_id":root.name,"mode":mode,"test_count":count})
 return records

def verify_host(out:Path=DEFAULT_OUT,jobs:int|None=None)->dict[str,object]:
 manifest_path=out/".state/materialization-manifest.json"
 if not manifest_path.is_file():fail("generator_output_drift","run --verify-core first")
 manifest=json.loads(manifest_path.read_text())
 if manifest["family_tree_hash"]!=tree_hash(out) or manifest["owner_hash"]!=file_hash(GENERATOR_PATH):fail("generator_output_drift","manifest owner/tree mismatch")
 compiler=shutil.which("c++")
 if compiler is None:fail("toolchain_missing","c++ not on PATH")
 if shutil.which("cmake") is None or shutil.which("ctest") is None:fail("toolchain_missing","cmake/ctest not on PATH")
 compiler_version=_run_command([compiler,"--version"]).stdout.splitlines()[0].strip()
 cmake_version=_run_command(["cmake","--version"]).stdout.splitlines()[0].strip()
 roots=[("tasks",out/c.task_id,True) for c in CASES]+[("controls",out/".state/adversarial-clone-controls"/name,False) for name in ("domain-identifier-renamed","constants-policy-only","opposite-end-selection")]
 workers=jobs or min(24,os.cpu_count() or 4)
 records=[]
 with tempfile.TemporaryDirectory(prefix="bounded-circular-host-") as temporary:
  temp=Path(temporary)
  def one(entry:tuple[str,Path,bool])->list[dict[str,object]]:
   kind,root,negative=entry
   rows=_host_verify_root(root,temp/f"{kind}-{root.name}",compiler,negative)
   for row in rows:row["kind"]=kind
   return rows
  with ThreadPoolExecutor(max_workers=workers) as pool:
   for rows in pool.map(one,roots):records.extend(rows)
 if len(records)!=246:fail("test_discovery_failed",f"record count {len(records)}")
 for case in CASES:
  rows=[r for r in records if r["kind"]=="tasks" and r["task_id"]==case.task_id]
  if {r["mode"] for r in rows}!={"normal","sanitizer","negative-normal","negative-sanitizer"} or {r["test_count"] for r in rows}!={2}:fail("sanitizer_test_count_mismatch",case.task_id)
 receipt={"schema_version":"bounded-circular-host-verify-v1","status":"pass","evidence_class":"host_verify","locked_oracle":False,"network":"not_applicable_host","compiler":{"path":compiler,"version":compiler_version,"sha256":file_hash(Path(compiler))},"cmake":cmake_version,"owner_hash":file_hash(GENERATOR_PATH),"case_catalog_hash":file_hash(CASES_PATH),"replacements_hash":file_hash(REPLACEMENTS_PATH),"cycle04_overrides_hash":file_hash(OVERRIDES_PATH),"cycle05_repairs_hash":file_hash(CYCLE05_PATH),"family_tree_hash":tree_hash(out),"normal_reference_count":63,"sanitizer_reference_count":63,"negative_normal_count":60,"negative_sanitizer_count":60,"negative_fixture_count":60,"test_count_per_mode":2,"parallel_workers":workers,"records":sorted(records,key=lambda r:(r["kind"],r["task_id"],r["mode"])),"command":["cmake","-S","<root>","-B","<build>","-G","Unix Makefiles","-DCMAKE_CXX_COMPILER=<c++>","-DTASK_SOURCE=<reference|negative>",";","cmake","--build",";","ctest","--test-dir"]}
 write(out/".state/host-verify.json",json.dumps(receipt,indent=2,sort_keys=True)+"\n",True)
 manifest["host_verify_hash"]=file_hash(out/".state/host-verify.json");write(manifest_path,json.dumps(manifest,indent=2,sort_keys=True)+"\n",True)
 return receipt

def record_cycle(out:Path,status:str,cycle:int)->Path:
 manifest_path=out/".state/materialization-manifest.json";manifest=json.loads(manifest_path.read_text()) if manifest_path.is_file() else {};receipt_path=out/".state/docker-sanity.json"
 replacement_map=[{"archived_task_id":"capacity-generation-slab","replacement_task_id":"capacity-indirect-compacting-slab"},{"archived_task_id":"order-linked-open-map","replacement_task_id":"rank-select-bit-directory"}]
 payload={"schema_version":"aider-task-creator-cycle-v1","cycle":cycle,"timestamp":datetime.now(timezone.utc).isoformat(),"status":status,"family_id":FAMILY_ID,"candidate_manifest":".state/materialization-manifest.json","family_tree_hash":tree_hash(out),"curriculum_hash":file_hash(CURRICULUM),"generator_hash":file_hash(GENERATOR_PATH),"case_catalog_hash":file_hash(CASES_PATH),"focused_test_hash":file_hash(TEST_PATH),"grader_policy_hash":sha((SANITY_IMAGE+CMAKE).encode()),"retained_root_ids":[c.task_id for c in CASES],"replaced_root_ids":[x["archived_task_id"] for x in replacement_map],"replacement_root_ids":[x["replacement_task_id"] for x in replacement_map],"replacement_map":replacement_map,"rejected_root_ids":[],"review_root_ids":[],"blocked_root_ids":[],"manifest_subject_hash":sha(json.dumps(manifest,sort_keys=True).encode()),"docker_receipt":json.loads(receipt_path.read_text()) if receipt_path.is_file() else None,"dataset_handoff":"not_requested"}
 path=out/".state/cycles"/f"cycle-{cycle:02d}.json";write(path,json.dumps(payload,indent=2,sort_keys=True)+"\n",False);return path

def main(argv:Sequence[str]|None=None)->int:
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--out",type=Path,default=DEFAULT_OUT);parser.add_argument("--force",action="store_true");parser.add_argument("--verify-core",action="store_true");parser.add_argument("--verify-host",action="store_true");parser.add_argument("--docker-sanity",action="store_true");parser.add_argument("--host-jobs",type=int,default=None);parser.add_argument("--cycle-status");parser.add_argument("--cycle",type=int,default=1);args=parser.parse_args(argv)
 if not args.cycle_status or args.force or args.verify_core or args.verify_host or args.docker_sanity:build(args.out,args.force)
 if args.verify_core or args.verify_host or args.docker_sanity:verify_core(args.out)
 if args.verify_host:verify_host(args.out,args.host_jobs)
 if args.docker_sanity:verify_docker(args.out)
 if args.cycle_status:record_cycle(args.out,args.cycle_status,args.cycle)
 return 0

if __name__=="__main__":raise SystemExit(main())
