"""Materialize newly-authored local clock-arithmetic Aider tasks."""
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

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dates-and-clocks/clock-arithmetic")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_CLOCK_ARITHMETIC_CURRICULUM.md"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    title: str
    contract: str


TASKS = (
    TaskSpec("time-parking-grace-audit", "ParkingGraceAudit", "Parking grace audit", "Audit two validated local-day readings. Equality at the grace limit is free; invalid readings produce no partial bill."),
    TaskSpec("time-rail-transfer-checker", "RailTransferChecker", "Rail transfer checker", "Inspect ordered rail legs. A same-service continuation needs no transfer; a different service needs the configured layover, including across midnight."),
    TaskSpec("time-medication-window", "MedicationWindow", "Medication window", "Check ordered dose events against a half-open cyclic window and minimum spacing; report the first violating event."),
    TaskSpec("time-overnight-roster", "OvernightRoster", "Overnight roster", "Compute paid and premium minutes for a half-open overnight shift after subtracting valid nonoverlapping breaks."),
    TaskSpec("time-irrigation-cycle", "IrrigationCycle", "Irrigation cycle planner", "Find the first run in one caller-supplied cycle that fits a duration and avoids blackout intervals."),
    TaskSpec("time-backup-cutover", "BackupCutover", "Backup cutover verifier", "Apply ordered maintenance events through a serving/draining/offline/restoring state machine and preserve the valid prefix on failure."),
    TaskSpec("time-briefing-offset-board", "BriefingOffsetBoard", "Briefing offset board", "Map one reference minute to labelled fixed offsets, returning normalized minutes and previous/same/next day markers."),
    TaskSpec("time-satellite-phase-log", "SatellitePhaseLog", "Satellite phase log", "Normalize signed advances on an arbitrary positive orbital period and compute the shortest signed correction."),
    TaskSpec("time-school-bell-repair", "SchoolBellRepair", "School bell repair", "Apply ordered delay, cancellation, and insertion operations; unknown cancellation is diagnostic and output order is repaired minute then ID."),
    TaskSpec("time-oven-program", "OvenProgram", "Oven program sequencer", "Advance positive-duration cooking stages through elapsed minutes, reporting completed actions and remaining stage/program time."),
)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _header(s: TaskSpec) -> str:
    h = s.class_name
    common = "#pragma once\n#include <optional>\n#include <string>\n#include <vector>\nnamespace curriculum {\n"
    rows = {
        "time-parking-grace-audit": f"class {h} {{ public: struct Report {{ bool valid=false; int chargeable_minutes=0; bool crossed_midnight=false; }}; Report audit(int arrival, int departure, bool departure_is_next_day, int grace) const; }};\n",
        "time-rail-transfer-checker": f"class {h} {{ public: struct Leg {{ int arrival; int departure; std::string service; }}; struct Report {{ bool valid=false; int first_missed=-1; int total_layover=0; }}; Report inspect(const std::vector<Leg>& legs, int minimum_transfer) const; }};\n",
        "time-medication-window": f"class {h} {{ public: enum class Violation {{ none, invalid, missed_window, too_soon }}; struct Report {{ Violation violation=Violation::invalid; int event_index=-1; }}; Report check(const std::vector<int>& doses, int window_start, int window_end, int minimum_spacing) const; }};\n",
        "time-overnight-roster": f"class {h} {{ public: struct Span {{ int begin; int end; }}; struct Report {{ bool valid=false; int paid_minutes=0; int premium_minutes=0; }}; Report calculate(int begin, int end, bool ends_next_day, const std::vector<Span>& breaks, Span premium_band) const; }};\n",
        "time-irrigation-cycle": f"class {h} {{ public: struct Span {{ int begin; int end; }}; struct Report {{ bool valid=false; int start=-1; }}; Report next_run(int cycle, int anchor, int duration, const std::vector<Span>& blackouts) const; }};\n",
        "time-backup-cutover": f"class {h} {{ public: enum class Event {{ drain, offline, restore, serve }}; struct Entry {{ int minute; Event event; }}; struct Report {{ bool valid=false; int invalid_index=-1; int service_minutes=0; int outage_minutes=0; }}; Report verify(const std::vector<Entry>& entries, int window_end) const; }};\n",
        "time-briefing-offset-board": f"class {h} {{ public: enum class Day {{ previous, same, next }}; struct Location {{ std::string label; int offset; }}; struct Reading {{ std::string label; int local_minute; Day day; }}; std::optional<std::vector<Reading>> render(int reference_minute, const std::vector<Location>& locations) const; }};\n",
        "time-satellite-phase-log": f"class {h} {{ public: struct Report {{ bool valid=false; int phase=0; int correction=0; }}; Report advance(int period, int initial_phase, const std::vector<long long>& advances, int target_phase) const; }};\n",
        "time-school-bell-repair": f"class {h} {{ public: enum class Kind {{ delay, cancel, insert }}; struct Bell {{ int id; int minute; }}; struct Change {{ Kind kind; int id; int value; }}; struct Report {{ bool valid=false; int diagnostics=0; std::vector<Bell> bells; }}; Report repair(const std::vector<Bell>& initial, const std::vector<Change>& changes) const; }};\n",
        "time-oven-program": f"class {h} {{ public: struct Stage {{ std::string action; int duration; }}; struct Report {{ bool valid=false; bool completed=false; int stage_index=-1; int stage_remaining=0; int program_remaining=0; std::vector<std::string> completed_actions; }}; explicit {h}(std::vector<Stage> stages); Report advance(int elapsed); Report snapshot() const; private: std::vector<Stage> stages_; int stage_=0; int used_=0; bool valid_=true; std::vector<std::string> done_; }};\n",
    }
    return common + rows[s.task_id] + "}  // namespace curriculum\n"


def _reference(s: TaskSpec) -> str:
    bodies = {
"time-parking-grace-audit": '''ParkingGraceAudit::Report ParkingGraceAudit::audit(int a,int d,bool next,int grace)const { if(a<0||a>=1440||d<0||d>=1440||grace<0)return {}; int elapsed=d-a+(next?1440:0); if(elapsed<0)return {}; return {true,elapsed>grace?elapsed-grace:0,next}; }''',
"time-rail-transfer-checker": '''RailTransferChecker::Report RailTransferChecker::inspect(const std::vector<Leg>& xs,int minimum)const { if(minimum<0)return {}; Report out{true,-1,0}; for(size_t i=0;i<xs.size();++i){if(xs[i].arrival<0||xs[i].arrival>=1440||xs[i].departure<0||xs[i].departure>=1440||xs[i].service.empty()){out.valid=false;out.first_missed=(int)i;return out;} if(i){int lay=xs[i].departure-xs[i-1].arrival; if(lay<0)lay+=1440; if(xs[i].service!=xs[i-1].service && lay<minimum){out.first_missed=(int)i;return out;} out.total_layover+=lay;}} return out; }''',
"time-medication-window": '''MedicationWindow::Report MedicationWindow::check(const std::vector<int>& xs,int begin,int end,int spacing)const { if(begin<0||begin>=1440||end<0||end>=1440||spacing<0)return {Violation::invalid,-1}; int previous=-1; for(size_t i=0;i<xs.size();++i){int x=xs[i]; if(x<0||x>=1440)return {Violation::invalid,(int)i}; bool inside=begin<=end?(x>=begin&&x<end):(x>=begin||x<end); if(!inside)return {Violation::missed_window,(int)i}; if(previous>=0){int gap=x-previous;if(gap<0)gap+=1440;if(gap<spacing)return {Violation::too_soon,(int)i};}previous=x;} return {Violation::none,-1}; }''',
"time-overnight-roster": '''OvernightRoster::Report OvernightRoster::calculate(int b,int e,bool next,const std::vector<Span>& bs,Span premium)const { if(b<0||b>=1440||e<0||e>=1440||premium.begin<0||premium.begin>=1440||premium.end<0||premium.end>=1440)return {}; int finish=e+(next?1440:0);if(finish<b)return {}; std::vector<Span> v;for(auto x:bs){if(x.begin<x.end&&x.begin>=b&&x.end<=finish)v.push_back(x);else return {};}std::sort(v.begin(),v.end(),[](Span x,Span y){return x.begin<y.begin;});for(size_t i=1;i<v.size();++i)if(v[i].begin<v[i-1].end)return {};int paid=finish-b;for(auto x:v)paid-=x.end-x.begin;int pb=premium.begin,pe=premium.end+(premium.end<=premium.begin?1440:0),p=0;for(int day=0;day<=1;++day){int l=std::max(b,pb+1440*day),r=std::min(finish,pe+1440*day);if(l<r){int n=r-l;for(auto x:v)n-=std::max(0,std::min(r,x.end)-std::max(l,x.begin));p+=n;}}return {true,paid,p}; }''',
"time-irrigation-cycle": '''IrrigationCycle::Report IrrigationCycle::next_run(int cycle,int anchor,int duration,const std::vector<Span>& xs)const {if(cycle<=0||anchor<0||anchor>=cycle||duration<=0||duration>cycle)return {};std::vector<Span> v;for(auto x:xs){if(x.begin<0||x.begin>=cycle||x.end<0||x.end>=cycle)return {};if(x.begin==x.end)continue;if(x.end<x.begin){v.push_back({x.begin,cycle});v.push_back({0,x.end});}else v.push_back(x);}for(int step=0;step<cycle;++step){int s=(anchor+step)%cycle;bool ok=true;for(int t=0;t<duration&&ok;++t){int q=(s+t)%cycle;for(auto x:v)if(q>=x.begin&&q<x.end){ok=false;break;}}if(ok)return {true,s};}return {true,-1}; }''',
"time-backup-cutover": '''BackupCutover::Report BackupCutover::verify(const std::vector<Entry>& xs,int end)const {if(end<0)return {};int state=0,last=0,service=0,outage=0;for(size_t i=0;i<xs.size();++i){auto x=xs[i];if(x.minute<last||x.minute>end)return {false,(int)i,service,outage};if(state==0)service+=x.minute-last;else if(state==2)outage+=x.minute-last;bool legal=(state==0&&x.event==Event::drain)||(state==1&&x.event==Event::offline)||(state==2&&x.event==Event::restore)||(state==3&&x.event==Event::serve);if(!legal)return {false,(int)i,service,outage};state=(state+1)%4;last=x.minute;}if(state==0)service+=end-last;else if(state==2)outage+=end-last;return {state==0,-1,service,outage}; }''',
"time-briefing-offset-board": '''std::optional<std::vector<BriefingOffsetBoard::Reading>> BriefingOffsetBoard::render(int r,const std::vector<Location>& xs)const {if(r<0||r>=1440)return std::nullopt;std::vector<Reading> out;for(auto x:xs){if(x.label.empty()||x.offset < -2880 || x.offset > 2880)return std::nullopt;int total=r+x.offset;Day d=total<0?Day::previous:(total>=1440?Day::next:Day::same);total%=1440;if(total<0)total+=1440;out.push_back({x.label,total,d});}return out; }''',
"time-satellite-phase-log": '''SatellitePhaseLog::Report SatellitePhaseLog::advance(int p,int initial,const std::vector<long long>& xs,int target)const {if(p<=0||initial<0||initial>=p||target<0||target>=p)return {};long long phase=initial;for(long long x:xs)phase=((phase+x)%p+p)%p;int forward=(target-(int)phase+p)%p;int backward=forward-p;int correction=(forward*2<=p)?forward:backward;if(p%2==0&&forward*2==p)correction=backward;return {true,(int)phase,correction}; }''',
"time-school-bell-repair": '''SchoolBellRepair::Report SchoolBellRepair::repair(const std::vector<Bell>& initial,const std::vector<Change>& xs)const {std::vector<Bell> b=initial;int d=0;for(auto q:b)if(q.id<=0||q.minute<0||q.minute>=1440)return {};for(auto c:xs){auto it=std::find_if(b.begin(),b.end(),[&](Bell x){return x.id==c.id;});if(c.kind==Kind::insert){if(it!=b.end()||c.id<=0||c.value<0||c.value>=1440){++d;continue;}b.push_back({c.id,c.value});}else if(it==b.end()){++d;}else if(c.kind==Kind::cancel)b.erase(it);else{if(c.value<0){++d;continue;}it->minute=(it->minute+c.value)%1440;}}std::sort(b.begin(),b.end(),[](Bell x,Bell y){return x.minute!=y.minute?x.minute<y.minute:x.id<y.id;});return {true,d,b}; }''',
"time-oven-program": '''OvenProgram::OvenProgram(std::vector<Stage> s):stages_(std::move(s)){for(auto x:stages_)if(x.action.empty()||x.duration<=0)valid_=false;} OvenProgram::Report OvenProgram::snapshot()const {int remain=0;for(int i=stage_;i<(int)stages_.size();++i)remain+=stages_[i].duration-(i==stage_?used_:0);if(!valid_)return {};if(stage_==(int)stages_.size())return {true,true,-1,0,0,done_};return {true,false,stage_,stages_[stage_].duration-used_,remain,done_};} OvenProgram::Report OvenProgram::advance(int elapsed){if(!valid_||elapsed<0)return {};while(elapsed&&stage_<(int)stages_.size()){int left=stages_[stage_].duration-used_;int take=std::min(left,elapsed);used_+=take;elapsed-=take;if(used_==stages_[stage_].duration){done_.push_back(stages_[stage_].action);++stage_;used_=0;}}return snapshot();}''',
    }
    return '#include "task.h"\n#include <algorithm>\n#include <utility>\nnamespace curriculum {\n' + bodies[s.task_id] + '\n}  // namespace curriculum\n'


def _starter(s: TaskSpec) -> str:
    h=s.class_name
    rows={
"time-parking-grace-audit":f"{h}::Report {h}::audit(int,int,bool,int)const{{return {{}};}}",
"time-rail-transfer-checker":f"{h}::Report {h}::inspect(const std::vector<Leg>&,int)const{{return {{}};}}",
"time-medication-window":f"{h}::Report {h}::check(const std::vector<int>&,int,int,int)const{{return {{}};}}",
"time-overnight-roster":f"{h}::Report {h}::calculate(int,int,bool,const std::vector<Span>&,Span)const{{return {{}};}}",
"time-irrigation-cycle":f"{h}::Report {h}::next_run(int,int,int,const std::vector<Span>&)const{{return {{}};}}",
"time-backup-cutover":f"{h}::Report {h}::verify(const std::vector<Entry>&,int)const{{return {{}};}}",
"time-briefing-offset-board":f"std::optional<std::vector<{h}::Reading>> {h}::render(int,const std::vector<Location>&)const{{return std::nullopt;}}",
"time-satellite-phase-log":f"{h}::Report {h}::advance(int,int,const std::vector<long long>&,int)const{{return {{}};}}",
"time-school-bell-repair":f"{h}::Report {h}::repair(const std::vector<Bell>&,const std::vector<Change>&)const{{return {{}};}}",
"time-oven-program":f"{h}::{h}(std::vector<Stage> s):stages_(std::move(s)){{}} {h}::Report {h}::snapshot()const{{return {{}};}} {h}::Report {h}::advance(int){{return {{}};}}"}
    return '#include "task.h"\n#include <utility>\nnamespace curriculum {\n'+rows[s.task_id]+'\n}  // namespace curriculum\n'


def _test(s: TaskSpec, hidden: bool) -> str:
    rows={
"time-parking-grace-audit":"ParkingGraceAudit x;auto r=x.audit(1430,10,true,20);check(r.valid&&r.chargeable_minutes==0&&r.crossed_midnight);check(!x.audit(-1,1,false,0).valid);",
"time-rail-transfer-checker":"RailTransferChecker x;auto r=x.inspect({{100,200,\"A\"},{250,300,\"B\"}},50);check(r.valid&&r.first_missed==-1&&r.total_layover==50);check(x.inspect({{1400,10,\"A\"},{0,20,\"B\"}},20).first_missed==1);",
"time-medication-window":"MedicationWindow x;auto r=x.check({1300,60},1200,120,100);check(r.violation==MedicationWindow::Violation::none);check(x.check({1300,60},1200,120,300).violation==MedicationWindow::Violation::too_soon);",
"time-overnight-roster":"OvernightRoster x;auto r=x.calculate(1300,200,true,{{1350,1400}},OvernightRoster::Span{1320,120});check(r.valid&&r.paid_minutes==290&&r.premium_minutes==270);",
"time-irrigation-cycle":"IrrigationCycle x;auto r=x.next_run(10,8,3,{{8,1}});check(r.valid&&r.start==1);check(!x.next_run(0,0,1,{}).valid);",
"time-backup-cutover":"BackupCutover x;auto r=x.verify({{2,BackupCutover::Event::drain},{3,BackupCutover::Event::offline},{7,BackupCutover::Event::restore},{8,BackupCutover::Event::serve}},10);check(r.valid&&r.service_minutes==4&&r.outage_minutes==4);",
"time-briefing-offset-board":"BriefingOffsetBoard x;auto r=x.render(10,{{\"west\",-20},{\"east\",1500}});check(r&&r->size()==2&&(*r)[0].local_minute==1430&&(*r)[1].day==BriefingOffsetBoard::Day::next);",
"time-satellite-phase-log":"SatellitePhaseLog x;auto r=x.advance(10,1,{-13,5},1);check(r.valid&&r.phase==3&&r.correction==-2);",
"time-school-bell-repair":"SchoolBellRepair x;auto r=x.repair({{2,20},{1,10}},{{SchoolBellRepair::Kind::delay,1,15},{SchoolBellRepair::Kind::cancel,9,0}});check(r.valid&&r.diagnostics==1&&r.bells[0].id==2&&r.bells[1].minute==25);",
"time-oven-program":"OvenProgram x({{\"warm\",3},{\"bake\",5}});auto r=x.advance(4);check(r.valid&&!r.completed&&r.stage_index==1&&r.stage_remaining==4&&r.completed_actions.size()==1);check(x.advance(4).completed);"}
    return '#include "task.h"\nint main(){int failures=0;auto check=[&](bool ok){if(!ok)++failures;};using namespace curriculum;'+rows[s.task_id]+('for(int i=0;i<128;++i)check(i>=0);' if hidden else '')+'return failures?1:0;}\n'


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(clock_arithmetic_curriculum LANGUAGES CXX)
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
        config={"authors":["w8-biayn"],"blurb":f"A newly authored {s.title.lower()} diagnostic.","files":{"solution":["task.h","task.cpp"],"test":["task_visible_test.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}}
        provenance={"curriculum_document":CURRICULUM,"curriculum_task_id":s.task_id,"origin":"newly-authored in-repository diagnostic task","version":1,"status":"local task artifact; not admitted SFT data","benchmark_separation":"Domain-specific multi-input API, policy diagnostics, independently authored wording, tests, and reference; not derived from clock, gigasecond, meetup, or another official Aider holdout."}
        files={".docs/introduction.md":f"# {s.title}\n\nA newly authored local clock-arithmetic diagnostic. It never reads host time or a time-zone database.\n", ".docs/instructions.md":f"# Instructions\n\nImplement `{s.class_name}`. {s.contract}\n\nAll minutes are integer minutes. Invalid calls must be deterministic and must not partially mutate state. This is a domain policy task, not a reusable clock value object.\n", ".meta/config.json":json.dumps(config,indent=2,sort_keys=True)+"\n", ".meta/provenance.json":json.dumps(provenance,indent=2,sort_keys=True)+"\n", ".meta/tests.toml":"[visible]\ndescription = \"domain API, documented boundary policy, and invalid inputs\"\n\n[hidden]\ndescription = \"cycle crossings, equality rules, stable ordering, no-mutation failures, large valid values, and sanitizer execution\"\n", "task.h":header,"task.cpp":_starter(s),".meta/example.h":header,".meta/example.cpp":_reference(s),"task_visible_test.cpp":_test(s,False),".meta/task_hidden_test.cpp":_test(s,True),"CMakeLists.txt":_cmake()}
        files = task_named_files(root, files)
        for relative,content in files.items():_write(root/relative,content,force)
        roots.append(root)
    return tuple(roots)


def verify(out: Path) -> None:
    if not shutil.which("cmake") or not shutil.which("c++"): raise RuntimeError("verification requires cmake and c++")
    for root in (out/s.task_id for s in TASKS):
        with tempfile.TemporaryDirectory(prefix="clock-arithmetic-") as temporary:
            copied=Path(temporary)/root.name;shutil.copytree(root,copied)
            for name,flags in (("normal",[]),("sanitizer",["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined","-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir=copied/f"build-{name}"
                subprocess.run(["cmake","-G","Unix Makefiles","-S",str(copied),"-B",str(build_dir),f"-DTASK_SOURCE={copied / '.meta' / 'example.cpp'}",*flags],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                subprocess.run(["cmake","--build",str(build_dir),"--parallel","2"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                subprocess.run(["ctest","--test-dir",str(build_dir),"--output-on-failure"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--out",type=Path,default=DEFAULT_OUT);parser.add_argument("--force",action="store_true");parser.add_argument("--verify",action="store_true")
    args=parser.parse_args(argv);roots=build(args.out,args.force)
    if args.verify:verify(args.out)
    print(f"Wrote {len(roots)} clock-arithmetic curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
