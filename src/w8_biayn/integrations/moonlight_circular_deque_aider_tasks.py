"""Materialize three semantically distinct clean-room circular-deque tasks."""

from __future__ import annotations
import argparse, json, re, shutil, subprocess, tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_circular_deque_cases import CASES
from w8_biayn.integrations.moonlight_circular_deque_semantics import (
    NORMALIZER_VERSION,
    assert_no_holdout_overlap,
    assert_semantic_diversity,
    load_artifact,
    load_holdout,
    strongest,
)

DEFAULT_OUT=Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/circular-deque")
LEGACY_OUT=Path(".w8-biayn/data/aider-tasks/aider-dsa/circular-deque")
CURRICULUM="docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_CIRCULAR_DEQUE_CURRICULUM.md"
HOLDOUT=Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice/circular-buffer/.docs/instructions.md")
MANIFEST=Path("manifests/aider_sft/aider-polyglot-cpp-26.json")
PROMPT="docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
LEGACY_IDS=("cdeque-audio-jitter","cdeque-browser-tabs","cdeque-build-work-items","cdeque-card-draw-pile","cdeque-delivery-resequence","cdeque-event-replay","cdeque-game-turns","cdeque-log-recovery","cdeque-meal-orders","cdeque-media-preview","cdeque-patient-triage","cdeque-print-priority","cdeque-route-detours","cdeque-sensor-calibration","cdeque-shuttle-stops","cdeque-support-callbacks","cdeque-ticket-escalation","cdeque-tool-rental","cdeque-transit-passengers","cdeque-warehouse-loading")

@dataclass(frozen=True)
class TaskSpec:
    task_id:str; class_name:str; kind:str; title:str; objective:str

TASKS=(
 TaskSpec("deque-work-steal-scheduler","WorkStealScheduler","work_ring","Work-stealing scheduler","Grow a wrapped owner/thief ring without changing logical work order."),
 TaskSpec("deque-window-extrema","WindowExtremaMonitor","extrema","Streaming window extrema","Maintain sliding-window minima and maxima with two monotonic deques."),
 TaskSpec("deque-zero-one-router","minimum_tolls","router","Zero-one toll router","Find graph toll distances with front/back 0-1 BFS relaxation."),
) + tuple(TaskSpec(c.task_id,c.class_name,c.kind,c.title,c.objective) for c in CASES)

def _extra(s:TaskSpec):
    return next((case for case in CASES if case.kind==s.kind),None)

def _write(path:Path,data:str,force:bool)->None:
    if path.exists() and path.read_text()!=data and not force: raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(data)

def _header(s:TaskSpec)->str:
    extra=_extra(s)
    if extra:return extra.header
    if s.kind=="work_ring": return """#pragma once
#include <cstddef>
#include <optional>
#include <string>
#include <vector>
namespace curriculum { class WorkStealScheduler { public:
 WorkStealScheduler(); void push_local(const std::string& id);
 std::optional<std::string> pop_local(); std::optional<std::string> steal_oldest();
 std::size_t size() const; std::size_t storage_capacity() const;
 private: void grow(); std::vector<std::optional<std::string>> slots_; std::size_t head_=0U,size_=0U; }; }
"""
    if s.kind=="extrema": return """#pragma once
#include <cstddef>
#include <deque>
#include <optional>
#include <utility>
namespace curriculum { struct WindowExtrema { int minimum; int maximum; bool operator==(const WindowExtrema& other) const; };
class WindowExtremaMonitor { public: explicit WindowExtremaMonitor(std::size_t width);
 std::optional<WindowExtrema> push(int value); std::size_t processed() const;
 private: std::size_t width_,processed_=0U; std::deque<std::pair<std::size_t,int>> minima_,maxima_; }; }
"""
    return """#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum { struct TollEdge { std::size_t from; std::size_t to; unsigned toll; };
std::optional<std::vector<std::optional<unsigned>>> minimum_tolls(std::size_t node_count,const std::vector<TollEdge>& edges,std::size_t source); }
"""

def _starter(s:TaskSpec)->str:
    extra=_extra(s)
    if extra:return extra.starter
    if s.kind=="work_ring": return """#include "task.h"
namespace curriculum { WorkStealScheduler::WorkStealScheduler():slots_(4U){} void WorkStealScheduler::grow(){} void WorkStealScheduler::push_local(const std::string&){} std::optional<std::string> WorkStealScheduler::pop_local(){return std::nullopt;} std::optional<std::string> WorkStealScheduler::steal_oldest(){return std::nullopt;} std::size_t WorkStealScheduler::size()const{return 0U;} std::size_t WorkStealScheduler::storage_capacity()const{return slots_.size();} }
"""
    if s.kind=="extrema": return """#include "task.h"
namespace curriculum { bool WindowExtrema::operator==(const WindowExtrema& o)const{return minimum==o.minimum&&maximum==o.maximum;} WindowExtremaMonitor::WindowExtremaMonitor(std::size_t width):width_(width){} std::optional<WindowExtrema> WindowExtremaMonitor::push(int){return std::nullopt;} std::size_t WindowExtremaMonitor::processed()const{return processed_;} }
"""
    return """#include "task.h"
namespace curriculum { std::optional<std::vector<std::optional<unsigned>>> minimum_tolls(std::size_t,const std::vector<TollEdge>&,std::size_t){return std::nullopt;} }
"""

def _reference(s:TaskSpec)->str:
    extra=_extra(s)
    if extra:return extra.reference
    if s.kind=="work_ring": return """#include "task.h"
#include <utility>
namespace curriculum {
WorkStealScheduler::WorkStealScheduler():slots_(4U){}
void WorkStealScheduler::grow(){std::vector<std::optional<std::string>> next(slots_.size()*2U);for(std::size_t i=0;i<size_;++i)next[i]=std::move(slots_[(head_+i)%slots_.size()]);slots_=std::move(next);head_=0U;}
void WorkStealScheduler::push_local(const std::string& id){if(id.empty())return;if(size_==slots_.size())grow();slots_[(head_+size_)%slots_.size()]=id;++size_;}
std::optional<std::string> WorkStealScheduler::pop_local(){if(!size_)return std::nullopt;const auto i=(head_+size_-1U)%slots_.size();auto out=std::move(slots_[i]);slots_[i].reset();--size_;if(!size_)head_=0U;return out;}
std::optional<std::string> WorkStealScheduler::steal_oldest(){if(!size_)return std::nullopt;auto out=std::move(slots_[head_]);slots_[head_].reset();head_=(head_+1U)%slots_.size();--size_;if(!size_)head_=0U;return out;}
std::size_t WorkStealScheduler::size()const{return size_;} std::size_t WorkStealScheduler::storage_capacity()const{return slots_.size();} }
"""
    if s.kind=="extrema": return """#include "task.h"
#include <limits>
namespace curriculum {
bool WindowExtrema::operator==(const WindowExtrema& o)const{return minimum==o.minimum&&maximum==o.maximum;}
WindowExtremaMonitor::WindowExtremaMonitor(std::size_t width):width_(width){}
std::optional<WindowExtrema> WindowExtremaMonitor::push(int value){if(processed_==std::numeric_limits<std::size_t>::max())return std::nullopt;const auto index=processed_++;if(!width_)return std::nullopt;if(index>=width_){const auto expired=index-width_;if(!minima_.empty()&&minima_.front().first<=expired)minima_.pop_front();if(!maxima_.empty()&&maxima_.front().first<=expired)maxima_.pop_front();}while(!minima_.empty()&&minima_.back().second>=value)minima_.pop_back();while(!maxima_.empty()&&maxima_.back().second<=value)maxima_.pop_back();minima_.push_back({index,value});maxima_.push_back({index,value});if(processed_<width_)return std::nullopt;return WindowExtrema{minima_.front().second,maxima_.front().second};}
std::size_t WindowExtremaMonitor::processed()const{return processed_;} }
"""
    return """#include "task.h"
#include <deque>
#include <limits>
#include <utility>
namespace curriculum {
std::optional<std::vector<std::optional<unsigned>>> minimum_tolls(std::size_t n,const std::vector<TollEdge>& edges,std::size_t source){if(!n||source>=n)return std::nullopt;std::vector<std::vector<std::pair<std::size_t,unsigned>>> adjacency(n);for(const auto& e:edges){if(e.from>=n||e.to>=n||e.toll>1U)return std::nullopt;adjacency[e.from].push_back({e.to,e.toll});}std::vector<std::optional<unsigned>> distance(n);std::deque<std::size_t> frontier;distance[source]=0U;frontier.push_front(source);while(!frontier.empty()){const auto node=frontier.front();frontier.pop_front();const auto current=*distance[node];for(const auto& edge:adjacency[node]){if(current>std::numeric_limits<unsigned>::max()-edge.second)continue;const auto candidate=current+edge.second;if(distance[edge.first]&&*distance[edge.first]<=candidate)continue;distance[edge.first]=candidate;if(edge.second==0U)frontier.push_front(edge.first);else frontier.push_back(edge.first);}}return distance;} }
"""

def _instructions(s:TaskSpec)->str:
    extra=_extra(s)
    if extra:
        rules={
          "center_halves":"push_middle inserts at index (size+1)/2; pop_middle removes index (size-1)/2. Empty pop returns no value.",
          "prefix_parser":"Tokens are strict base-10 integers or +, -, *, /. Operators consume exactly two prefix expressions. Reject malformed, trailing, divide-by-zero, and overflowing input.",
          "run_editor":"Zero-count additions do nothing. Equal boundary characters merge. Drops remove up to the requested count and report the count removed.",
          "snake_body":"The body is head-to-tail. A non-growing move vacates the tail before collision testing. Wall or self collision leaves state unchanged; invalid initial bodies stay invalid.",
          "deficit_rr":"Quantum, flow, job, and cost must be nonzero/nonempty. Each active visit adds quantum; a job dispatches only when its flow deficit covers its cost, and unused deficit carries.",
          "temporal_join":"Each side must arrive in nondecreasing timestamp order with nonempty IDs. Compare stream fronts: pair within tolerance, otherwise drop only the provably too-early front.",
          "pal_hash":"End pushes and pops update both fingerprints. Empty pops return no value. is_palindrome compares maintained forward and reverse fingerprints without rescanning text.",
          "chunked_text":"Limit zero rejects additions. Chunks are nonempty and never exceed the limit. Bulk erase removes up to the requested count and reports the amount removed.",
          "josephus":"Step must be positive and IDs unique. Rotate step-1 positions in the selected direction, remove the active end, and continue until empty.",
          "lex_picker":"Choose the smaller end; when equal, compare symmetric inward characters until a difference and choose left on a complete tie. Return both value and L/R choices.",
          "war_cycle":"Draw deck fronts; the higher card wins and appends winner then loser. Equal cards are invalid. Stop on empty deck, repeated paired state, or the round limit.",
          "radix_buckets":"Base must be 2 through 16. Preserve input order within every digit bucket and gather buckets in digit order for each LSD place."
        }[s.kind]
        return f"# Instructions\n\nImplement {s.class_name}. {s.objective} {rules} This is local candidate material, not a dataset release.\n"
    detail={"work_ring":"The owner appends non-empty IDs, pops newest work, and a thief steals oldest work. Empty IDs are ignored, duplicates are allowed, storage starts at four slots, and growth doubles storage while preserving order.","extrema":"Each push accepts an integer. No result appears before a complete window; then return the minimum and maximum of exactly the latest width values. Width zero never yields extrema.","router":"Endpoints must be in range and tolls must be zero or one. Invalid input returns no outer value. Valid output has one optional distance per node; duplicate edges are allowed."}[s.kind]
    return f"# Instructions\n\nImplement {s.class_name}. {s.objective} {detail} This is local candidate material, not a dataset release.\n"

def _test(s:TaskSpec,hidden:bool)->str:
    extra=_extra(s)
    if extra:return extra.hidden if hidden else extra.visible
    if s.kind=="work_ring":
        extra="""std::deque<std::string> oracle;unsigned state=19073U;for(int step=0;step<600;++step){state=state*1664525U+1013904223U;const auto op=state%4U;if(op<2U){const auto v=(step%19==0)?std::string():("job-"+std::to_string(state%31U));q.push_local(v);if(!v.empty())oracle.push_back(v);}else if(op==2U){const auto e=oracle.empty()?std::nullopt:std::optional<std::string>(oracle.back());check(q.pop_local()==e);if(!oracle.empty())oracle.pop_back();}else{const auto e=oracle.empty()?std::nullopt:std::optional<std::string>(oracle.front());check(q.steal_oldest()==e);if(!oracle.empty())oracle.pop_front();}check(q.size()==oracle.size());}""" if hidden else """q.push_local("compile");q.push_local("link");q.push_local("test");check(q.pop_local()==std::optional<std::string>("test"));check(q.steal_oldest()==std::optional<std::string>("compile"));check(q.pop_local()==std::optional<std::string>("link"));"""
        return f"""#include "task.h"
#include <deque>
#include <optional>
#include <string>
int main(){{int failures=0;auto check=[&](bool ok){{if(!ok)++failures;}};curriculum::WorkStealScheduler q;check(!q.pop_local()&&!q.steal_oldest());{extra}return failures?1:0;}}
"""
    if s.kind=="extrema":
        extra="""curriculum::WindowExtremaMonitor z(0U);check(!z.push(1));curriculum::WindowExtremaMonitor m(9U);std::vector<int> v;unsigned state=271828U;for(int i=0;i<700;++i){state=state*1103515245U+12345U;v.push_back(static_cast<int>(state%81U)-40);const auto got=m.push(v.back());if(v.size()<9U)check(!got);else{const auto mm=std::minmax_element(v.end()-9,v.end());check(got==std::optional<curriculum::WindowExtrema>({*mm.first,*mm.second}));}}""" if hidden else """curriculum::WindowExtremaMonitor m(3U);check(!m.push(4));check(!m.push(2));check(m.push(7)==std::optional<curriculum::WindowExtrema>({2,7}));check(m.push(5)==std::optional<curriculum::WindowExtrema>({2,7}));check(m.push(1)==std::optional<curriculum::WindowExtrema>({1,7}));"""
        return f"""#include "task.h"
#include <algorithm>
#include <optional>
#include <vector>
int main(){{int failures=0;auto check=[&](bool ok){{if(!ok)++failures;}};{extra}return failures?1:0;}}
"""
    extra="""check(!curriculum::minimum_tolls(0U,{},0U));check(!curriculum::minimum_tolls(2U,{{0U,2U,1U}},0U));unsigned state=424242U;for(std::size_t trial=0;trial<120U;++trial){const auto n=2U+trial%7U;std::vector<curriculum::TollEdge> edges;for(std::size_t i=0;i<n*3U;++i){state=state*1664525U+1013904223U;const auto from=state%n;state=state*1664525U+1013904223U;edges.push_back({from,state%n,(state>>8U)&1U});}const auto got=curriculum::minimum_tolls(n,edges,0U);std::vector<unsigned> expected(n,std::numeric_limits<unsigned>::max());expected[0]=0U;for(std::size_t pass=1;pass<n;++pass)for(const auto& e:edges)if(expected[e.from]!=std::numeric_limits<unsigned>::max())expected[e.to]=std::min(expected[e.to],expected[e.from]+e.toll);check(got.has_value());if(got)for(std::size_t i=0;i<n;++i)check(expected[i]==std::numeric_limits<unsigned>::max()?!(*got)[i]:(*got)[i]==std::optional<unsigned>(expected[i]));}""" if hidden else """const std::vector<curriculum::TollEdge> e{{0U,1U,1U},{0U,2U,0U},{2U,1U,0U},{1U,3U,1U}};const auto got=curriculum::minimum_tolls(5U,e,0U);check(got&&(*got)[1]==std::optional<unsigned>(0U)&&(*got)[3]==std::optional<unsigned>(1U)&&!(*got)[4]);"""
    return f"""#include "task.h"
#include <algorithm>
#include <limits>
#include <optional>
#include <vector>
int main(){{int failures=0;auto check=[&](bool ok){{if(!ok)++failures;}};{extra}return failures?1:0;}}
"""

CMAKE="""cmake_minimum_required(VERSION 3.16)
project(circular_deque_distinct LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(target task_visible task_hidden)
 target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
 if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
 endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
"""

def build(out:Path=DEFAULT_OUT,force:bool=False)->tuple[Path,...]:
    roots=[]
    for s in TASKS:
        root=out/s.task_id; header=_header(s)
        config={"authors":["w8-biayn"],"blurb":s.objective,"files":{"solution":["task.h","task.cpp"],"test":["task_visible_test.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}}
        provenance={"curriculum_document":CURRICULUM,"curriculum_task_id":s.task_id,"origin":"clean-room semantic replacement for rejected template roots","status":"local task artifact; not admitted SFT data","version":3,"selected_prompt_path":PROMPT,"requested_root_bounds":{"minimum":15,"maximum":20},"hard_diversity_rule":"Every root differs in primary logic and implementation, not names or policy toggles.","benchmark_separation":"No fixed-capacity FIFO read/write, full-write rejection, forced overwrite, or clear contract.","legacy_family_preserved_at":LEGACY_OUT.as_posix()}
        files={".docs/introduction.md":f"# {s.title}\n\n{s.objective} This root has an independent API, state model, implementation, and oracle.\n",".docs/instructions.md":_instructions(s),".meta/config.json":json.dumps(config,indent=2,sort_keys=True)+"\n",".meta/provenance.json":json.dumps(provenance,indent=2,sort_keys=True)+"\n",".meta/tests.toml":'[visible]\ndescription = "public contract and representative transitions"\n\n[hidden]\ndescription = "deterministic boundaries, randomized oracle, and core discriminators"\n',"task.h":header,"task.cpp":_starter(s),".meta/example.h":header,".meta/example.cpp":_reference(s),"task_visible_test.cpp":_test(s,False),".meta/task_hidden_test.cpp":_test(s,True),"CMakeLists.txt":CMAKE}
        for name,data in task_named_files(root,files).items(): _write(root/name,data,force)
        roots.append(root)
    return tuple(roots)

def required_marker(s:TaskSpec)->str:
    extra=_extra(s)
    if extra:return extra.required[0]
    return {"work_ring":"grow()","extrema":"maxima_","router":"push_front"}[s.kind]

def _core_failure(s:TaskSpec,source:str)->str|None:
    extra=_extra(s)
    if extra:
        return "invariant_not_enforced" if any(x not in source for x in extra.required) or any(x in source for x in extra.forbidden) else None
    required={"work_ring":("slots_","head_","grow()","%slots_.size()"),"extrema":("minima_","maxima_","minima_.pop_back()","maxima_.pop_back()","pop_front()"),"router":("adjacency","std::deque<std::size_t>","push_front","push_back")}[s.kind]
    forbidden={"work_ring":("std::deque","overwrite(","clear()"),"extrema":("std::multiset","std::sort("),"router":("std::queue","std::priority_queue")}[s.kind]
    return "invariant_not_enforced" if any(x not in source for x in required) or any(x in source for x in forbidden) else None

def verify_core(out:Path)->dict[str,object]:
    if not HOLDOUT.is_file(): raise RuntimeError("benchmark_content_overlap:official_holdout_unavailable")
    holdout=HOLDOUT.read_text().lower()
    if not all(x in holdout for x in ("fixed-size buffer","oldest values","full an error","overwrite the oldest")): raise RuntimeError("benchmark_content_overlap:holdout_contract_changed")
    if not 15 <= len(TASKS) <= 20: raise RuntimeError(f"family_count_out_of_bounds:{len(TASKS)}")
    holdouts=set(json.loads(MANIFEST.read_text())["task_ids"]); kinds=set()
    for s in TASKS:
        if s.kind in kinds: raise RuntimeError(f"duplicate_family:{s.task_id}")
        kinds.add(s.kind)
        if s.task_id in holdouts or s.task_id in LEGACY_IDS: raise RuntimeError(f"benchmark_id_overlap:{s.task_id}")
        root=out/s.task_id; config=json.loads((root/".meta/config.json").read_text())
        if config["files"]["solution"]!=[f"{s.task_id}.h",f"{s.task_id}.cpp"]: raise RuntimeError(f"role_mapping_failed:{s.task_id}")
        if config["files"]["example"]!=[".meta/example.h",".meta/example.cpp"]: raise RuntimeError(f"target_reference_mismatch:{s.task_id}")
        prompt=build_prompt(load_task(root))
        if any(x in prompt for x in (".meta/example","task_hidden_test","CMakeLists.txt","provenance.json")): raise RuntimeError(f"prompt_boundary_failed:{s.task_id}")
        if any(x in prompt.lower() for x in ("fixed-size buffer","forced write","overwrite the oldest","circular_buffer","circular-buffer")): raise RuntimeError(f"benchmark_content_overlap:{s.task_id}")
        source=(root/".meta/example.cpp").read_text()
        if _core_failure(s,source): raise RuntimeError(f"invariant_not_enforced:{s.task_id}")
        if _core_failure(s,source.replace(required_marker(s),"removed"))!="invariant_not_enforced": raise RuntimeError(f"negative_fixture_not_rejected:{s.task_id}")
        extra=_extra(s)
        banned=extra.forbidden[0] if extra else {"work_ring":"std::deque","extrema":"std::multiset","router":"std::priority_queue"}[s.kind]
        if _core_failure(s,source+"\\n// "+banned)!="invariant_not_enforced": raise RuntimeError(f"negative_fixture_not_rejected:{s.task_id}")
    actual={p.name for p in out.iterdir() if p.is_dir() and p.name!=".state"}; expected={s.task_id for s in TASKS}
    if actual!=expected: raise RuntimeError(f"generator_output_drift:expected={sorted(expected)}:actual={sorted(actual)}")
    artifacts=tuple(load_artifact(out/s.task_id) for s in TASKS)
    family_scores=assert_semantic_diversity(artifacts)
    holdout_scores=assert_no_holdout_overlap(
        artifacts,
        (load_holdout(HOLDOUT.parent.parent),),
    )
    family_max=strongest(family_scores)
    holdout_max=strongest(holdout_scores)
    return {
        "normalizer":NORMALIZER_VERSION,
        "comparison_scope":{
            "family_roots":len(artifacts),
            "family_pairs":len(family_scores),
            "holdouts":1,
            "holdout_pairs":len(holdout_scores),
        },
        "strongest_family_pair":family_max.reason() if family_max else None,
        "strongest_holdout_pair":holdout_max.reason() if holdout_max else None,
    }

def _ctest_count(stdout:str)->int|None:
    match=re.search(r"out of (\d+)",stdout)
    return int(match.group(1)) if match and "100% tests passed" in stdout else None

def verify(out:Path)->dict[str,dict[str,int]]:
    if not shutil.which("cmake") or not shutil.which("c++"): raise RuntimeError("oracle_not_completed: verification requires cmake and c++; install documented prerequisites or use a designated locked grader")
    receipts={}
    for s in TASKS:
        receipts[s.task_id]={}
        with tempfile.TemporaryDirectory(prefix="cdeque-distinct-") as tmp:
            copied=Path(tmp)/s.task_id; shutil.copytree(out/s.task_id,copied)
            for name,flags in (("normal",[]),("sanitizer",["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined","-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                b=copied/f"build-{name}"; commands=(["cmake","-G","Unix Makefiles","-S",str(copied),"-B",str(b),f"-DTASK_SOURCE={copied/'.meta/example.cpp'}",*flags],["cmake","--build",str(b),"--parallel","2"],["ctest","--test-dir",str(b),"--output-on-failure"])
                for command in commands:
                    result=subprocess.run(command,capture_output=True,text=True)
                    if result.returncode: raise RuntimeError(f"reference_{name}_failed:{s.task_id}\\n{result.stdout}\\n{result.stderr}")
                count=_ctest_count(result.stdout)
                if count!=2: raise RuntimeError(f"test_discovery_failed:{s.task_id}:{name}\n{result.stdout}\n{result.stderr}")
                receipts[s.task_id][name]=count
        if receipts[s.task_id]["normal"]!=receipts[s.task_id]["sanitizer"]: raise RuntimeError(f"sanitizer_test_count_mismatch:{s.task_id}")
    return receipts

def main(argv:Sequence[str]|None=None)->int:
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--out",type=Path,default=DEFAULT_OUT);p.add_argument("--force",action="store_true");p.add_argument("--verify-core",action="store_true");p.add_argument("--verify",action="store_true");args=p.parse_args(argv)
    roots=build(args.out,args.force)
    if args.verify_core: verify_core(args.out)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} distinct circular-deque tasks under {args.out}");return 0
if __name__=="__main__": raise SystemExit(main())
