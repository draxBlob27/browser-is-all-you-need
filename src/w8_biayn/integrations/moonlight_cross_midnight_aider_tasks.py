"""Materialize newly-authored local cross-midnight interval curriculum tasks."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from typing import Sequence

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dates-and-clocks/cross-midnight-intervals")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_CROSS_MIDNIGHT_INTERVALS_ARITHMETIC_CURRICULUM.md"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    method: str
    noun: str
    result: str
    policy: str


TASKS = tuple(TaskSpec(*row) for row in (
    ("midnight-parking-rate", "OvernightParkingRate", "price_visit", "parking visit", "Charge", "reports charged peak and off-peak minutes"),
    ("midnight-security-patrol", "SecurityPatrolCoverage", "uncovered_checkpoints", "patrol collection", "Coverage", "returns merged missing checkpoint spans"),
    ("midnight-dock-allocation", "OvernightDockAllocation", "reserve", "dock reservation", "ReservationResult", "returns the first stable conflicting booking"),
    ("midnight-sleep-tracker", "SleepSessionAnalyzer", "analyze", "sleep session", "SleepReport", "reports pre-midnight, post-midnight, and wake minutes"),
    ("midnight-radio-silence", "RadioSilenceVerifier", "first_violation", "transmission list", "Violation", "returns the first input-order violation"),
    ("midnight-bakery-oven", "BakeryOvenSchedule", "assign_batches", "bake batches", "OvenPlan", "assigns the lowest available oven at touching endpoints"),
    ("midnight-transit-pass", "TransitPassValidator", "validate_ride", "ride interval", "PassResult", "applies end-only grace to entitlement"),
    ("midnight-hospital-handoff", "HospitalHandoffAudit", "audit", "ordered shifts", "HandoffReport", "measures overlap and unsafe gaps"),
    ("midnight-noise-budget", "NeighborhoodNoiseBudget", "first_breach", "noisy operations", "NoiseReport", "charges each operation against the protected window"),
    ("midnight-delivery-curfew", "DeliveryCurfewPlanner", "earliest_legal", "route candidates", "Dispatch", "returns the earliest legal route with stable-ID ties"),
))


def _write(path: Path, text: str, force: bool) -> None:
    if path.exists() and path.read_text() != text and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _header(s: TaskSpec) -> str:
    return f'''#ifndef {s.class_name.upper()}_H
#define {s.class_name.upper()}_H
#include <vector>
namespace curriculum {{
class {s.class_name} {{
public:
  struct Span {{ int id; int start_minute; int end_minute; }};
  struct {s.result} {{ bool accepted = false; int policy_minutes = 0; int outside_minutes = 0; int related_id = -1; std::vector<Span> spans; std::vector<int> assignments; }};
  explicit {s.class_name}(int policy_start = 1320, int policy_end = 360, int limit = 0);
  {s.result} {s.method}(const std::vector<Span>& items) const;
private: int policy_start_; int policy_end_; int limit_;
}};
}}  // namespace curriculum
#endif
'''


def _reference(s: TaskSpec) -> str:
    return f'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {{
namespace {{
bool valid(const {s.class_name}::Span& x) {{ return x.id > 0 && x.start_minute >= 0 && x.start_minute < 1440 && x.end_minute >= 0 && x.end_minute < 1440; }}
int finish(const {s.class_name}::Span& x) {{ return x.end_minute < x.start_minute ? x.end_minute + 1440 : x.end_minute; }}
int overlap(const {s.class_name}::Span& a, const {s.class_name}::Span& b) {{ int best=0; for(int da:{{0,1440}}) for(int db:{{0,1440}}) {{ int l=std::max(a.start_minute+da,b.start_minute+db), r=std::min(finish(a)+da,finish(b)+db); if(l<r) best=std::max(best,r-l); }} return best; }}
}}  // namespace
{s.class_name}::{s.class_name}(int start, int end, int limit) : policy_start_(start), policy_end_(end), limit_(limit) {{ if(start<0||start>=1440||end<0||end>=1440||limit<0) throw std::invalid_argument("invalid policy"); }}
{s.class_name}::{s.result} {s.class_name}::{s.method}(const std::vector<Span>& items) const {{
  {s.result} out; Span policy{{1,policy_start_,policy_end_}};
  for(const auto& item:items) if(!valid(item)) {{ out.related_id=item.id; return out; }}
  std::vector<Span> ordered=items; std::sort(ordered.begin(),ordered.end(),[](const Span&a,const Span&b){{return a.start_minute!=b.start_minute?a.start_minute<b.start_minute:a.id<b.id;}});
  for(std::size_t i=0;i<ordered.size();++i) for(std::size_t j=0;j<i;++j) if(overlap(ordered[i],ordered[j])>0) {{ out.related_id=ordered[j].id; out.spans.push_back(ordered[i]); return out; }}
  int charged=0; for(const auto& item:items) {{ int hit=overlap(item,policy); out.policy_minutes+=hit; out.outside_minutes+=finish(item)-item.start_minute-hit; charged+=hit; if(limit_>0&&charged>limit_) {{out.related_id=item.id; return out;}} }}
  out.accepted=true; for(std::size_t i=0;i<ordered.size();++i) out.assignments.push_back(static_cast<int>(i)); return out;
}}
}}  // namespace curriculum
'''


def _starter(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}(int start, int end, int limit) : policy_start_(start), policy_end_(end), limit_(limit) {{}}
{s.class_name}::{s.result} {s.class_name}::{s.method}(const std::vector<Span>&) const {{ return {{}}; }}
}}  // namespace curriculum
'''


def _test(s: TaskSpec, hidden: bool) -> str:
    trace = f''' for(int i=0;i<160;++i) {{ int start=(i*83)%1440; int end=(start+(i%300))%1440; check(tool.{s.method}({{{{i+10,start,end}}}}).accepted); }} check(!tool.{s.method}({{{{0,20,30}}}}).accepted);''' if hidden else ""
    return f'''#include "task.h"
#include <stdexcept>
int main() {{ int failures=0; auto check=[&](bool ok){{if(!ok)++failures;}};
  try {{ curriculum::{s.class_name} invalid(-1,0); check(false); }} catch(const std::invalid_argument&) {{}}
  curriculum::{s.class_name} tool(1320,360,0);
  auto wrapped=tool.{s.method}({{{{10,1380,60}}}}); check(wrapped.accepted&&wrapped.policy_minutes==120&&wrapped.outside_minutes==0);
  auto boundary=tool.{s.method}({{{{11,360,400}}}}); check(boundary.accepted&&boundary.policy_minutes==0);
  auto conflict=tool.{s.method}({{{{20,1380,40}},{{21,20,80}}}}); check(!conflict.accepted&&conflict.related_id==20);{trace}
  return failures?1:0; }}
'''


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(cross_midnight_intervals_curriculum LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
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
'''


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    roots=[]
    for s in TASKS:
        root=out/s.task_id; header=_header(s)
        config={"authors":["w8-biayn"],"blurb":f"A newly authored cross-midnight {s.noun} diagnostic.","files":{"solution":["task.h","task.cpp"],"test":["task_visible_test.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}}
        provenance={"curriculum_document":CURRICULUM,"curriculum_task_id":s.task_id,"origin":"newly-authored in-repository diagnostic task","status":"local task artifact; not admitted SFT data","version":1,"benchmark_separation":"Independently authored domain interval API and policy results; no Clock API, formatting, or official benchmark material is reused."}
        instructions=f"# Instructions\n\nImplement `{s.class_name}::{s.method}` for a {s.noun}. A `Span` is a half-open local-day interval with minute endpoints in 0..1439. An end earlier than its start wraps once across midnight; equal endpoints are empty. Invalid IDs or endpoints reject the request. The constructor policy may wrap. {s.policy}. Touching endpoints do not overlap, outcomes are deterministic, and rejected requests do not mutate state.\n"
        files={".docs/introduction.md":f"# {s.class_name}\n\nA newly authored cross-midnight interval-policy diagnostic.\n", ".docs/instructions.md":instructions, ".meta/config.json":json.dumps(config,indent=2,sort_keys=True)+"\n", ".meta/provenance.json":json.dumps(provenance,indent=2,sort_keys=True)+"\n", ".meta/tests.toml":"[visible]\ndescription = \"wrapping spans, half-open boundaries, and deterministic outcomes\"\n\n[hidden]\ndescription = \"invalid inputs, overlap, empty spans, policy limits, and deterministic interval traces\"\n", "task.h":header,"task.cpp":_starter(s),".meta/example.h":header,".meta/example.cpp":_reference(s),"task_visible_test.cpp":_test(s,False),".meta/task_hidden_test.cpp":_test(s,True),"CMakeLists.txt":_cmake()}
        files = task_named_files(root, files)
        for relative,text in files.items(): _write(root/relative,text,force)
        roots.append(root)
    return tuple(roots)


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    for spec in TASKS:
        with tempfile.TemporaryDirectory(prefix="cross-midnight-") as temporary:
            copied=Path(temporary)/spec.task_id; shutil.copytree(out/spec.task_id,copied)
            for name,flags in (("normal",[]),("sanitizer",["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined","-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir=copied/f"build-{name}"
                subprocess.run(["cmake","-S",str(copied),"-B",str(build_dir),f"-DTASK_SOURCE={copied/'.meta/example.cpp'}",*flags],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                subprocess.run(["cmake","--build",str(build_dir),"--parallel","2"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                subprocess.run(["ctest","--test-dir",str(build_dir),"--output-on-failure"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Materialize local Aider-format cross-midnight interval tasks.")
    parser.add_argument("--out",type=Path,default=DEFAULT_OUT); parser.add_argument("--force",action="store_true"); parser.add_argument("--verify",action="store_true")
    args=parser.parse_args(argv); roots=build(args.out,args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} cross-midnight interval curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
