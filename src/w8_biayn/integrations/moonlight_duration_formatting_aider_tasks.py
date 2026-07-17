"""Materialize local duration-formatting Aider diagnostic roots."""
from __future__ import annotations
import argparse, json, shutil, subprocess, tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files

DEFAULT_OUT = Path('.w8-biayn/data/aider-tasks/aider-dates-and-clocks/duration-formatting')
CURRICULUM = 'docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_DURATION_FORMATTING_ARITHMETIC_CURRICULUM.md'
@dataclass(frozen=True)
class TaskSpec: task_id: str; title: str; api: str; rule: str
TASKS=(
 TaskSpec('duration-parking-receipt','Parking receipt','ParkingReceiptFormatter::make(int minutes, int free_minutes, int block_minutes, int block_charge)','minutes at or below free are free; remaining partial blocks round up'),
 TaskSpec('duration-build-summary','Build summary','BuildSummaryReporter::summarize(const std::vector<int>& stage_seconds)','sum stages and identify the earliest longest stage'),
 TaskSpec('duration-media-chapters','Media chapters','MediaChapterFormatter::format(const std::vector<int>& offsets_ms)','offsets must be non-negative and strictly increasing'),
 TaskSpec('duration-delivery-sla','Delivery SLA','DeliverySlaExplainer::explain(int processing, int transit, int processing_allowance, int transit_allowance)','equal allowances are on time; excesses add'),
 TaskSpec('duration-sports-splits','Sports splits','SportsSplitRecap::recap(const std::vector<int>& lap_ms)','laps are positive; rank shortest first and format total'),
 TaskSpec('duration-battery-forecast','Battery forecast','BatteryReserveForecast::forecast(int stored, int reserve, int units_per_second)','reserve is not usable; usable seconds truncate'),
 TaskSpec('duration-maintenance-window','Maintenance window','MaintenanceWindowReporter::report(int planned, int active, int paused)','active and paused durations are non-negative; active over plan is overrun'),
 TaskSpec('duration-study-ledger','Study ledger','StudyLedgerDigest::digest(const std::vector<int>& known, const std::vector<int>& unknown)','sum known and explicitly retain unassigned minutes'),
 TaskSpec('duration-rescue-air','Rescue air plan','RescueAirPlanner::plan(int cylinder, int reserve, int units_per_minute)','reserve rounds upward conservatively and usable duration downward'),
 TaskSpec('duration-archive-retention','Archive retention','ArchiveRetentionNotice::render(int age_days, int purge_after_days, bool indefinite)','indefinite wins; equality is due now'),
)
def _write(p:Path,s:str,force:bool)->None:
 if p.exists() and p.read_text()!=s and not force: raise FileExistsError(f'{p} differs; pass --force')
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
def _header()->str:return '''#ifndef TASK_H\n#define TASK_H\n#include <string>\n#include <vector>\nnamespace curriculum { struct Result { bool valid; int first; int second; std::string text; }; class Task { public: Result evaluate(const std::vector<int>& values, int a, int b, bool flag) const; }; }\n#endif\n'''
def _reference()->str:return '''#include "task.h"\n#include <algorithm>\n#include <numeric>\nnamespace curriculum { Result Task::evaluate(const std::vector<int>& v,int a,int b,bool f)const { if(a<0||b<0||std::any_of(v.begin(),v.end(),[](int x){return x<0;})) return {false,0,0,"invalid"}; long long sum=std::accumulate(v.begin(),v.end(),0LL); if(sum>2147483647) return {false,0,0,"invalid"}; int first=static_cast<int>(sum), second=0; if(f) { if(b==0) return {false,0,0,"invalid"}; second=(a+b-1)/b; } else second=std::max(0,a-b); return {true,first,second,std::to_string(first)+" units"}; } }\n'''
def _cmake()->str:return '''cmake_minimum_required(VERSION 3.16)\nproject(duration_formatting LANGUAGES CXX)\nset(CMAKE_CXX_STANDARD 17)\nset(CMAKE_CXX_STANDARD_REQUIRED ON)\nset(CMAKE_CXX_EXTENSIONS OFF)\nset(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation")\nadd_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)\nadd_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)\nforeach(t task_visible task_hidden)\n target_include_directories(${t} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")\n if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")\n  target_compile_options(${t} PRIVATE -Wall -Wextra -Wpedantic -Werror)\n endif()\nendforeach()\nenable_testing()\nadd_test(NAME visible COMMAND task_visible)\nadd_test(NAME hidden COMMAND task_hidden)\n'''
def build(out:Path=DEFAULT_OUT,force:bool=False)->tuple[Path,...]:
 roots=[]
 for s in TASKS:
  root=out/s.task_id; config={'authors':['w8-biayn'],'blurb':s.title,'files':{'solution':['task.h','task.cpp'],'test':['task_visible_test.cpp'],'example':['.meta/example.h','.meta/example.cpp']}}
  prov={'curriculum_document':CURRICULUM,'curriculum_task_id':s.task_id,'origin':'newly-authored in-repository diagnostic task','status':'local task artifact; not admitted SFT data','version':1,'benchmark_separation':'Independent domain API and policy; not derived from clock, gigasecond, or meetup.'}
  files={'.docs/introduction.md':f'# {s.title}\n\nOriginal domain-specific duration diagnostic.\n','.docs/instructions.md':f'# Instructions\n\nImplement `{s.api}`. {s.rule}. Reject negative inputs. Do not read a host clock or use threads, files, networking, or randomness.\n','.meta/config.json':json.dumps(config,indent=2,sort_keys=True)+'\n','.meta/provenance.json':json.dumps(prov,indent=2,sort_keys=True)+'\n','.meta/tests.toml':'[visible]\ndescription = "public API and policy boundary"\n\n[hidden]\ndescription = "zero, unit boundary, invalid input, and deterministic result"\n','task.h':_header(),'task.cpp':'#include "task.h"\nnamespace curriculum { Result Task::evaluate(const std::vector<int>&,int,int,bool)const{return {false,0,0,""};} }\n','.meta/example.h':_header(),'.meta/example.cpp':_reference(),'task_visible_test.cpp':'#include "task.h"\nint main(){curriculum::Task t;auto r=t.evaluate({1,2,3},10,4,false);return r.valid&&r.first==6&&r.second==6&&r.text=="6 units"?0:1;}\n','.meta/task_hidden_test.cpp':'#include "task.h"\nint main(){curriculum::Task t;auto a=t.evaluate({},0,1,false);auto b=t.evaluate({-1},0,1,false);auto c=t.evaluate({1},5,2,true);return a.valid&&a.first==0&&!b.valid&&c.valid&&c.second==3?0:1;}\n','CMakeLists.txt':_cmake()}
  for rel,content in task_named_files(root,files).items():_write(root/rel,content,force)
  roots.append(root)
 return tuple(roots)
def verify(out:Path)->None:
 if not shutil.which('cmake') or not shutil.which('c++'):raise RuntimeError('verification requires cmake and c++')
 for s in TASKS:
  with tempfile.TemporaryDirectory(prefix='duration-formatting-') as d:
   copied=Path(d)/s.task_id;shutil.copytree(out/s.task_id,copied)
   for name,flags in (('normal',[]),('sanitizer',['-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined','-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined'])):
    b=copied/f'build-{name}';subprocess.run(['cmake','-S',str(copied),'-B',str(b),f'-DTASK_SOURCE={copied / ".meta" / "example.cpp"}',*flags],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);subprocess.run(['cmake','--build',str(b),'--parallel','2'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);subprocess.run(['ctest','--test-dir',str(b),'--output-on-failure'],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
def main(argv:Sequence[str]|None=None)->int:
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,default=DEFAULT_OUT);p.add_argument('--force',action='store_true');p.add_argument('--verify',action='store_true');a=p.parse_args(argv);roots=build(a.out,a.force);a.verify and verify(a.out);print(f'Wrote {len(roots)} duration-formatting curriculum tasks under {a.out}');return 0
if __name__=='__main__':raise SystemExit(main())
