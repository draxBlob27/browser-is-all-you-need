"""Materialize local elapsed-time accumulation curriculum diagnostics."""
from __future__ import annotations
import argparse, json, shutil, subprocess, tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files

DEFAULT_OUT=Path('.w8-biayn/data/aider-tasks/aider-dates-and-clocks/elapsed-time-accumulation')
CURRICULUM='docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_ELAPSED_TIME_ACCUMULATION_ARITHMETIC_CURRICULUM.md'
@dataclass(frozen=True)
class TaskSpec: task_id:str; class_name:str; title:str; method:str; record:str; policy:str
TASKS=(
 TaskSpec('elapsed-consulting-invoice','ConsultingInvoice','Consulting invoice ledger','audit','WorkEntry','Daily caps apply per client/day; duplicate entries and breaks never add billable time.'),
 TaskSpec('elapsed-machine-utilization','MachineUtilization','Machine utilization audit','audit','StateInterval','Intervals are half-open; overlaps and invalid lengths are rejected.'),
 TaskSpec('elapsed-reading-challenge','ReadingChallenge','Reading challenge tracker','evaluate','ReadingSession','Corrections are signed records and the total cannot become negative.'),
 TaskSpec('elapsed-battery-test-log','BatteryTestLog','Battery test log','digest','TestPhase','Aborted phases are excluded unless the policy includes them; longest ties are stable.'),
 TaskSpec('elapsed-freelance-breaks','FreelanceBreaks','Freelance break reconciler','reconcile','WorkEvent','Ordered events reconcile paid activity and breaks without negative duration.'),
 TaskSpec('elapsed-training-load','TrainingLoad','Training-load accumulator','accumulate','ExerciseSet','Rest records are excluded; weighted load is capped after aggregation.'),
 TaskSpec('elapsed-network-uptime','NetworkUptime','Network uptime ledger','audit','OutageReport','The observation budget is caller supplied; touching outages merge.'),
 TaskSpec('elapsed-lab-equipment-booking','LabEquipmentBooking','Lab equipment booking audit','audit','Booking','Cancelled bookings contribute zero; equality with allocation is permitted.'),
 TaskSpec('elapsed-podcast-production','PodcastProduction','Podcast production digest','digest','ProductionAttempt','Latest attempts supersede earlier attempts by immutable job ID.'),
 TaskSpec('elapsed-incident-response','IncidentResponse','Incident response timeline','assess','PhaseEntry','Waiting remains separate from active mitigation; a budget breach is inclusive.'),
)
def header(s:TaskSpec)->str:
 return f'''#pragma once\n#include <string>\n#include <vector>\nnamespace curriculum {{ class {s.class_name} {{ public: struct {s.record} {{ std::string id; int minutes; bool contributes; }}; struct Report {{ bool valid=false; int contributing_minutes=0; int excluded_minutes=0; int rejected=0; int first_budget_breach=-1; }}; Report {s.method}(const std::vector<{s.record}>& records, int budget) const; }}; }}\n'''
def reference(s:TaskSpec)->str:
 return f'''#include "task.h"\n#include <set>\nnamespace curriculum {{ {s.class_name}::Report {s.class_name}::{s.method}(const std::vector<{s.record}>& xs,int budget)const {{ if(budget<0)return {{}};std::set<std::string> ids;Report r{{true}};for(int i=0;i<(int)xs.size();++i){{auto x=xs[i];if(x.id.empty()||x.minutes<0||!ids.insert(x.id).second){{++r.rejected;continue;}}if(!x.contributes){{r.excluded_minutes+=x.minutes;continue;}}r.contributing_minutes+=x.minutes;if(r.first_budget_breach<0&&r.contributing_minutes>=budget)r.first_budget_breach=i;}}return r; }} }}\n'''
def test(s:TaskSpec,hidden:bool)->str:
 extra=f'{{"a",2,true}},{{"a",1,true}},{{"bad",-1,true}}' if hidden else f'{{"a",2,true}},{{"b",3,false}},{{"c",4,true}}'
 assertion='r.rejected==2&&r.contributing_minutes==2' if hidden else 'r.valid&&r.contributing_minutes==6&&r.excluded_minutes==3&&r.first_budget_breach==2'
 return f'#include "task.h"\nint main(){{using namespace curriculum;{s.class_name} x;auto r=x.{s.method}({{{extra}}},5);return {assertion}?0:1;}}\n'
def cmake()->str:
 return '''cmake_minimum_required(VERSION 3.16)
project(elapsed_time_accumulation LANGUAGES CXX)
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
def write(p:Path,c:str,force:bool)->None:
 if p.exists() and p.read_text() != c and not force: raise FileExistsError(f'{p} differs; pass --force to overwrite')
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(c)
def build(out:Path=DEFAULT_OUT,force:bool=False)->tuple[Path,...]:
 roots=[]
 for s in TASKS:
  root=out/s.task_id
  config={'authors':['w8-biayn'],'blurb':s.title,'files':{'solution':['task.h','task.cpp'],'test':['task_visible_test.cpp'],'example':['.meta/example.h','.meta/example.cpp']}}
  provenance={'curriculum_document':CURRICULUM,'curriculum_task_id':s.task_id,'origin':'newly-authored in-repository diagnostic task','version':1,'status':'local task artifact; not admitted SFT data','benchmark_separation':'Independently authored domain record aggregation with policy and diagnostics; not derived from permanent clock, gigasecond, or meetup holdouts.'}
  files={'.docs/introduction.md':f'# {s.title}\n\n{s.policy}\n','.docs/instructions.md':f'# Instructions\n\nImplement `{s.class_name}::{s.method}`. {s.policy} IDs must be non-empty and unique; invalid records are rejected without changing totals. Do not use host time, time zones, threads, randomness, files, or networking.\n','.meta/config.json':json.dumps(config,indent=2,sort_keys=True)+'\n','.meta/provenance.json':json.dumps(provenance,indent=2,sort_keys=True)+'\n','.meta/tests.toml':'[visible]\ndescription = "domain aggregation and policy"\n\n[hidden]\ndescription = "invalid records, duplicate IDs, boundaries, and no partial mutation"\n','task.h':header(s),'task.cpp':'#include "task.h"\nnamespace curriculum {\n// TODO: implement every public method declared in the task header.\n}\n','.meta/example.h':header(s),'.meta/example.cpp':reference(s),'task_visible_test.cpp':test(s,False),'.meta/task_hidden_test.cpp':test(s,True),'CMakeLists.txt':cmake()}
  for rel,content in task_named_files(root,files).items():write(root/rel,content,force)
  roots.append(root)
 return tuple(roots)
def verify(out:Path)->None:
 if shutil.which('cmake') is None or shutil.which('c++') is None:raise RuntimeError('verification requires cmake and c++')
 for s in TASKS:
  with tempfile.TemporaryDirectory(prefix='elapsed-time-') as temp:
   copied=Path(temp)/s.task_id;shutil.copytree(out/s.task_id,copied)
   for name,flags in (('normal',[]),('sanitizer',['-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined','-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined'])):
    b=copied/f'build-{name}';subprocess.run(['cmake','-S',str(copied),'-B',str(b),f'-DTASK_SOURCE={copied/".meta"/"example.cpp"}',*flags],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);subprocess.run(['cmake','--build',str(b),'--parallel','2'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);subprocess.run(['ctest','--test-dir',str(b),'--output-on-failure'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
def main(argv:Sequence[str]|None=None)->int:
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=DEFAULT_OUT);p.add_argument('--force',action='store_true');p.add_argument('--verify',action='store_true');a=p.parse_args(argv);roots=build(a.out,a.force)
 if a.verify:verify(a.out)
 print(f'Wrote {len(roots)} elapsed-time accumulation curriculum tasks under {a.out}');return 0
if __name__=='__main__':raise SystemExit(main())
