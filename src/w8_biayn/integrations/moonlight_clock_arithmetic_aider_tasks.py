"""Remediate and locally reverify the clock-arithmetic Aider task family."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from pathlib import PurePosixPath
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-reverify/"
    "aider-text-grid-reshaping/clock-arithmetic"
)
REQUESTED_LEGACY_ROOT = Path(
    ".w8-biayn/data/aider-tasks/aider-text-grid-reshaping/clock-arithmetic"
)
LEGACY_ROOT = Path(
    ".w8-biayn/data/aider-tasks/aider-dates-and-clocks/clock-arithmetic"
)
CURRICULUM = (
    "docs/aider-synthetic/aider-synthetic-clock-tasks/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_CLOCK_ARITHMETIC_CURRICULUM.md"
)
FAMILY_SPEC = (
    "docs/aider-tasks-spec/aider-text-grid-reshaping/clock-arithmetic.md"
)
PROMPT_PATH = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
GENERATOR_PATH = (
    "src/w8_biayn/integrations/moonlight_clock_arithmetic_aider_tasks.py"
)
FOCUSED_TEST_PATH = "tests/test_moonlight_clock_arithmetic_aider_tasks.py"
WRAPPER_PATH = (
    "examples/slime/moonlight_cpp_perf/prepare_clock_arithmetic_aider_tasks.sh"
)
FAMILY_ID_BEFORE = "aider-dates-and-clocks-clock-arithmetic-v1"
FAMILY_ID = "aider-text-grid-reshaping-clock-arithmetic-v2"
LEGACY_GENERATOR_REVISION = (
    "sha256:85e2723ae262e4a76ea7c40190e703d9a7d5b7e882cb7ee339251b707174e1b3"
)
MIN_ROOTS = 8
MAX_ROOTS = 12
SEMANTIC_NORMALIZER = (
    "clock-arithmetic-v2-identifier-literal-endpoint-neutral-7gram"
)
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
DEFAULT_HOLDOUT_ROOT = Path(
    ".cache/upstreams/aider-polyglot/cpp/exercises/practice"
)
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_or_selection_rules",
    "invalid_and_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
HARD_RULE_LIMITS = {dimension: 0.75 for dimension in HARD_RULE_DIMENSIONS}
ADVERSARIAL_CONTROLS = (
    "domain-identifier-renamed-clone",
    "constants-policy-only-clone",
    "opposite-end-selection-clone",
)
OFFICIAL_AIDER_CPP_HOLDOUTS = frozenset(
    {
        "all-your-base", "allergies", "bank-account", "binary-search-tree",
        "circular-buffer", "clock", "complex-numbers", "crypto-square",
        "diamond", "dnd-character", "gigasecond", "grade-school",
        "kindergarten-garden", "knapsack", "linked-list", "meetup",
        "parallel-letter-frequency", "perfect-numbers", "phone-number",
        "queen-attack", "robot-name", "space-age", "spiral-matrix",
        "sublist", "yacht", "zebra-puzzle",
    }
)
REMEDY_HEADINGS = (
    "Identity", "Objective", "Public API", "Behavior table",
    "Implementation invariant", "Starter and reference", "Tests",
    "Files and metadata", "Build/oracle", "Family/contamination",
    "Optional dataset handoff", "Acceptance",
)


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    title: str
    contract: str
    mechanism: str
    reference_marker: str
    negative_old: str
    negative_new: str
    negative_reason: str


TASKS = (
    TaskSpec(
        "time-parking-grace-audit", "ParkingGraceAudit", "Parking grace audit",
        "Audit two validated local-day readings. Equality at the grace limit is free; invalid readings produce no partial bill.",
        "explicit one-day interval linearization followed by grace subtraction",
        "elapsed>grace?elapsed-grace:0",
        "elapsed>grace?elapsed-grace:0", "elapsed>=grace?elapsed-grace+1:0",
        "charging the equality boundary",
    ),
    TaskSpec(
        "time-rail-transfer-checker", "RailTransferChecker", "Rail transfer checker",
        "Inspect ordered rail legs. A same-service continuation needs no transfer; a different service needs the configured layover, including across midnight.",
        "adjacent itinerary scan with service-sensitive layover feasibility",
        "xs[i].service!=xs[i-1].service && lay<minimum",
        "lay<minimum", "lay<=minimum", "rejecting an exactly sufficient transfer",
    ),
    TaskSpec(
        "time-medication-window", "MedicationWindow", "Medication window",
        "Check ordered dose events against a half-open cyclic window and minimum spacing; report the first violating event.",
        "cyclic half-open membership plus normalized consecutive-spacing scan",
        "Violation::too_soon",
        "begin<=end?(x>=begin&&x<end)", "begin<=end?(x>=begin&&x<=end)",
        "accepting the excluded window endpoint",
    ),
    TaskSpec(
        "time-overnight-roster", "OvernightRoster", "Overnight roster",
        "Compute paid and premium minutes for a half-open overnight shift after subtracting valid nonoverlapping breaks.",
        "linearized shift segmentation with break validation and premium overlap subtraction",
        "n-=std::max(0,std::min(r,x.end)-std::max(l,x.begin))",
        "n-=std::max(0,std::min(r,x.end)-std::max(l,x.begin))",
        "n-=std::max(0,std::min(r,x.end)-std::max(l,x.begin))/2",
        "paying premium during an unpaid break",
    ),
    TaskSpec(
        "time-irrigation-cycle", "IrrigationCycle", "Irrigation cycle planner",
        "Find the first run in one caller-supplied cycle that fits a duration and avoids blackout intervals.",
        "wrapped-blackout canonicalization followed by anchor-ordered slot search",
        "int s=(anchor+step)%cycle",
        "q<x.end", "q<=x.end", "treating a half-open blackout endpoint as blocked",
    ),
    TaskSpec(
        "time-backup-cutover", "BackupCutover", "Backup cutover verifier",
        "Apply ordered maintenance events through a serving/draining/offline/restoring state machine and preserve the valid prefix on failure.",
        "four-state legal-transition fold with prefix duration accounting",
        "state=(state+1)%4",
        "if(state==0)service+=x.minute-last", "if(state<=1)service+=x.minute-last",
        "counting draining time as serving time",
    ),
    TaskSpec(
        "time-briefing-offset-board", "BriefingOffsetBoard", "Briefing offset board",
        "Map one reference minute to labelled fixed offsets, returning normalized minutes and previous/same/next day markers.",
        "stable one-to-many signed-offset normalization with relative-day classification",
        "total>=1440?Day::next:Day::same",
        "total>=1440", "total>1440", "misclassifying an exact next-day boundary",
    ),
    TaskSpec(
        "time-satellite-phase-log", "SatellitePhaseLog", "Satellite phase log",
        "Normalize signed advances on an arbitrary positive orbital period and compute the shortest signed correction.",
        "overflow-safe modular fold with backward half-period tie breaking",
        "forward*2==p)correction=backward",
        "correction=backward", "correction=forward", "choosing the forward half-period tie",
    ),
    TaskSpec(
        "time-school-bell-repair", "SchoolBellRepair", "School bell repair",
        "Apply ordered delay, cancellation, and insertion operations; unknown or invalid changes are diagnostic and output order is repaired minute then ID.",
        "stable-ID change replay followed by minute-and-ID canonical ordering",
        "x.minute!=y.minute?x.minute<y.minute:x.id<y.id",
        "x.minute!=y.minute?x.minute<y.minute:x.id<y.id", "x.id<y.id",
        "ordering primarily by identifier instead of repaired minute",
    ),
    TaskSpec(
        "time-oven-program", "OvenProgram", "Oven program sequencer",
        "Advance positive-duration cooking stages through elapsed minutes, reporting completed actions and remaining stage/program time.",
        "persistent staged-duration state machine with multi-stage consumption",
        "if(used_==stages_[stage_].duration)",
        "done_.push_back(stages_[stage_].action)",
        "done_.push_back(stages_[stage_].action+\"!\")",
        "corrupting each recorded completion action",
    ),
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
"time-satellite-phase-log": '''SatellitePhaseLog::Report SatellitePhaseLog::advance(int p,int initial,const std::vector<long long>& xs,int target)const {if(p<=0||initial<0||initial>=p||target<0||target>=p)return {};long long phase=initial;for(long long x:xs){long long step=x%p;phase=(phase+step)%p;if(phase<0)phase+=p;}int forward=(target-(int)phase+p)%p;int backward=forward-p;int correction=(forward*2<=p)?forward:backward;if(p%2==0&&forward*2==p)correction=backward;return {true,(int)phase,correction}; }''',
"time-school-bell-repair": '''SchoolBellRepair::Report SchoolBellRepair::repair(const std::vector<Bell>& initial,const std::vector<Change>& xs)const {std::vector<Bell> b=initial;int d=0;for(size_t i=0;i<b.size();++i){if(b[i].id<=0||b[i].minute<0||b[i].minute>=1440)return {};for(size_t j=0;j<i;++j)if(b[j].id==b[i].id)return {};}for(auto c:xs){auto it=std::find_if(b.begin(),b.end(),[&](Bell x){return x.id==c.id;});if(c.kind==Kind::insert){if(it!=b.end()||c.id<=0||c.value<0||c.value>=1440){++d;continue;}b.push_back({c.id,c.value});}else if(it==b.end()){++d;}else if(c.kind==Kind::cancel)b.erase(it);else{if(c.value<0){++d;continue;}it->minute=(it->minute+c.value)%1440;}}std::sort(b.begin(),b.end(),[](Bell x,Bell y){return x.minute!=y.minute?x.minute<y.minute:x.id<y.id;});return {true,d,b}; }''',
"time-oven-program": '''OvenProgram::OvenProgram(std::vector<Stage> s):stages_(std::move(s)){long long total=0;for(auto x:stages_){if(x.action.empty()||x.duration<=0)valid_=false;total+=x.duration;if(total>std::numeric_limits<int>::max())valid_=false;}} OvenProgram::Report OvenProgram::snapshot()const {long long remain=0;for(int i=stage_;i<(int)stages_.size();++i)remain+=stages_[i].duration-(i==stage_?used_:0);if(!valid_)return {};if(stage_==(int)stages_.size())return {true,true,-1,0,0,done_};return {true,false,stage_,stages_[stage_].duration-used_,static_cast<int>(remain),done_};} OvenProgram::Report OvenProgram::advance(int elapsed){if(!valid_||elapsed<0)return {};while(elapsed&&stage_<(int)stages_.size()){int left=stages_[stage_].duration-used_;int take=std::min(left,elapsed);used_+=take;elapsed-=take;if(used_==stages_[stage_].duration){done_.push_back(stages_[stage_].action);++stage_;used_=0;}}return snapshot();}''',
    }
    return '#include "task.h"\n#include <algorithm>\n#include <limits>\n#include <utility>\nnamespace curriculum {\n' + bodies[s.task_id] + '\n}  // namespace curriculum\n'


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


def _instructions(s: TaskSpec) -> str:
    details = {
        "time-parking-grace-audit": """`arrival` and `departure` are in `[0, 1440)`, and `grace` is nonnegative. `departure_is_next_day` adds exactly one day before subtraction. A same-day departure before arrival is invalid. On success, charge only elapsed minutes strictly beyond grace; equality is free. `crossed_midnight` repeats the supplied next-day flag.""",
        "time-rail-transfer-checker": """Every leg has validated `[0, 1440)` arrival/departure readings and a nonempty service. For each adjacent pair, normalize `current.departure - previous.arrival` by adding one day when negative. Add every layover to `total_layover`. A service change misses only when the layover is strictly below `minimum_transfer`; equality passes. Invalid input returns `valid=false` and its first bad index. A missed connection keeps `valid=true` and reports its index.""",
        "time-medication-window": """The window endpoints and every dose are in `[0, 1440)`, and spacing is nonnegative. Membership is half-open: `[start,end)` when nonwrapping and `[start,1440) union [0,end)` when wrapping; equal endpoints describe an empty window. Inspect doses in caller order, normalize each consecutive gap by at most one day, and report the first invalid, outside-window, or too-soon event.""",
        "time-overnight-roster": """Shift endpoints and premium-band endpoints are in `[0, 1440)`. `ends_next_day` adds exactly 1440 to the shift end; a negative resulting duration is invalid. Breaks use the resulting unwrapped minute axis, must be positive, contained, and nonoverlapping (adjacency is allowed). Paid time is shift duration minus breaks. Premium is the half-open premium-band overlap, including a wrapped band, after subtracting break overlap.""",
        "time-irrigation-cycle": """`cycle` is positive, `anchor` is in `[0,cycle)`, and duration is in `[1,cycle]`. Blackout endpoints are in `[0,cycle)`; equal endpoints are empty and a descending span wraps. A run occupies `duration` integer slots modulo the cycle. Search starts at `anchor` and advances one slot, returning the first collision-free start. If none exists, return a valid report with `start=-1`.""",
        "time-backup-cutover": """`window_end` is nonnegative. Entries have nondecreasing minutes in `[0,window_end]`; equal-minute entries execute in input order. The only legal cycle is serving -> drain -> offline -> restore -> serve. Count time only in serving and offline states. An illegal or out-of-order entry returns its index and the durations from the valid prefix. A legal but unfinished final state returns `valid=false` with `invalid_index=-1`.""",
        "time-briefing-offset-board": """The reference minute is in `[0,1440)`. Each location has a nonempty label and a signed offset in `[-2880,2880]`. Preserve input order. Normalize each sum into `[0,1440)`; any negative sum is `previous`, any sum at least 1440 is `next`, otherwise it is `same`. Any invalid element rejects the complete render with `nullopt`.""",
        "time-satellite-phase-log": """The period is positive and initial/target phases lie in `[0,period)`. Fold every signed 64-bit advance modulo the period without summing the raw advances. Return the final normalized phase and the shortest signed correction to target. When an even period has an exact half-period tie, choose the negative/backward correction.""",
        "time-school-bell-repair": """Initial bell IDs are unique and positive and minutes lie in `[0,1440)`; otherwise the whole call is invalid. Replay changes in order. Insert requires a new positive ID and valid absolute minute. Cancel/delay of an absent ID, duplicate insert, invalid insert, or negative delay increments diagnostics without mutation. Delay wraps modulo 1440. Return bells sorted by repaired minute, then ID; equal minutes are allowed.""",
        "time-oven-program": """Construction accepts ordered stages with nonempty action names, positive durations, and a total duration representable by `int`; otherwise all reports are invalid. `advance` consumes a nonnegative elapsed duration across any number of stages, records each completed action once, and ignores excess time after completion. A negative advance is invalid and leaves state unchanged. `snapshot` and zero advance do not mutate.""",
    }
    return (
        f"# Instructions\n\nImplement `{s.class_name}`. {s.contract}\n\n"
        f"{details[s.task_id]}\n\nThe required mechanism is {s.mechanism}. "
        "All behavior is deterministic and offline; do not consult host time, a time-zone database, the filesystem, or the network. This is a domain policy task, not a reusable clock value object.\n"
    )


def _test(s: TaskSpec, hidden: bool) -> str:
    visible = {
        "time-parking-grace-audit": "ParkingGraceAudit x;auto r=x.audit(1430,10,true,20);check(r.valid&&r.chargeable_minutes==0&&r.crossed_midnight);check(!x.audit(-1,1,false,0).valid);check(x.audit(20,50,false,10).chargeable_minutes==20);",
        "time-rail-transfer-checker": "RailTransferChecker x;auto r=x.inspect({{200,100,\"A\"},{300,250,\"B\"}},50);check(r.valid&&r.first_missed==-1&&r.total_layover==50);auto equal=x.inspect({{1430,0,\"A\"},{20,10,\"B\"}},20);check(equal.valid&&equal.first_missed==-1&&equal.total_layover==20);auto missed=x.inspect({{1430,0,\"A\"},{20,10,\"B\"}},21);check(missed.valid&&missed.first_missed==1);",
        "time-medication-window": "MedicationWindow x;auto r=x.check({1300,60},1200,120,100);check(r.violation==MedicationWindow::Violation::none);check(x.check({1300,60},1200,120,300).violation==MedicationWindow::Violation::too_soon);",
        "time-overnight-roster": "OvernightRoster x;auto r=x.calculate(1300,200,true,{{1350,1400}},OvernightRoster::Span{1320,120});check(r.valid&&r.paid_minutes==290&&r.premium_minutes==190);check(!x.calculate(100,50,false,{},OvernightRoster::Span{0,10}).valid);",
        "time-irrigation-cycle": "IrrigationCycle x;auto r=x.next_run(10,8,3,{{8,1}});check(r.valid&&r.start==1);check(!x.next_run(0,0,1,{}).valid);",
        "time-backup-cutover": "BackupCutover x;auto r=x.verify({{2,BackupCutover::Event::drain},{3,BackupCutover::Event::offline},{7,BackupCutover::Event::restore},{8,BackupCutover::Event::serve}},10);check(r.valid&&r.service_minutes==4&&r.outage_minutes==4);",
        "time-briefing-offset-board": "BriefingOffsetBoard x;auto r=x.render(10,{{\"west\",-20},{\"east\",1500}});check(r&&r->size()==2&&(*r)[0].local_minute==1430&&(*r)[0].day==BriefingOffsetBoard::Day::previous&&(*r)[1].day==BriefingOffsetBoard::Day::next);",
        "time-satellite-phase-log": "SatellitePhaseLog x;auto r=x.advance(10,1,{-13,5},1);check(r.valid&&r.phase==3&&r.correction==-2);check(x.advance(10,0,{},5).correction==-5);",
        "time-school-bell-repair": "SchoolBellRepair x;auto r=x.repair({{2,20},{1,10}},{{SchoolBellRepair::Kind::delay,1,15},{SchoolBellRepair::Kind::cancel,9,0}});check(r.valid&&r.diagnostics==1&&r.bells.size()==2&&r.bells[0].id==2&&r.bells[1].minute==25);",
        "time-oven-program": "OvenProgram x({{\"warm\",3},{\"bake\",5}});auto r=x.advance(4);check(r.valid&&!r.completed&&r.stage_index==1&&r.stage_remaining==4&&r.completed_actions.size()==1);check(x.advance(4).completed);",
    }
    private = {
        "time-parking-grace-audit": "ParkingGraceAudit x;check(x.audit(10,30,false,20).chargeable_minutes==0);check(x.audit(1439,0,true,0).chargeable_minutes==1);check(!x.audit(100,99,false,0).valid);check(!x.audit(0,0,false,-1).valid);",
        "time-rail-transfer-checker": "RailTransferChecker x;auto equal=x.inspect({{100,0,\"A\"},{200,150,\"B\"}},50);check(equal.valid&&equal.first_missed==-1&&equal.total_layover==50);auto same=x.inspect({{100,0,\"A\"},{200,101,\"A\"}},99);check(same.valid&&same.first_missed==-1&&same.total_layover==1);auto wrap=x.inspect({{1430,0,\"A\"},{20,10,\"B\"}},20);check(wrap.first_missed==-1&&wrap.total_layover==20);check(!x.inspect({{0,0,\"\"}},0).valid);",
        "time-medication-window": "MedicationWindow x;check(x.check({120},120,120,0).violation==MedicationWindow::Violation::missed_window);check(x.check({10,20},0,20,0).violation==MedicationWindow::Violation::missed_window);check(x.check({1430,10},1400,40,20).violation==MedicationWindow::Violation::none);check(x.check({-1},0,1,0).event_index==0);",
        "time-overnight-roster": "OvernightRoster x;auto r=x.calculate(1200,120,true,{{1250,1300},{1300,1310}},OvernightRoster::Span{1230,60});check(r.valid&&r.paid_minutes==300&&r.premium_minutes==210);check(!x.calculate(1200,120,true,{{1250,1310},{1300,1320}},OvernightRoster::Span{0,60}).valid);check(!x.calculate(1200,120,true,{{1100,1150}},OvernightRoster::Span{0,60}).valid);",
        "time-irrigation-cycle": "IrrigationCycle x;check(x.next_run(10,8,3,{{8,1}}).start==1);check(x.next_run(5,3,2,{{0,0}}).start==3);check(x.next_run(4,0,1,{{0,1},{1,2},{2,3},{3,0}}).start==-1);check(!x.next_run(4,4,1,{}).valid);",
        "time-backup-cutover": "BackupCutover x;auto bad=x.verify({{2,BackupCutover::Event::offline}},10);check(!bad.valid&&bad.invalid_index==0&&bad.service_minutes==2&&bad.outage_minutes==0);auto incomplete=x.verify({{2,BackupCutover::Event::drain}},10);check(!incomplete.valid&&incomplete.invalid_index==-1&&incomplete.service_minutes==2);auto equal=x.verify({{1,BackupCutover::Event::drain},{1,BackupCutover::Event::offline},{1,BackupCutover::Event::restore},{1,BackupCutover::Event::serve}},2);check(equal.valid&&equal.service_minutes==2);",
        "time-briefing-offset-board": "BriefingOffsetBoard x;auto exact=x.render(0,{{\"tomorrow\",1440},{\"yesterday\",-1},{\"now\",0}});check(exact&&(*exact)[0].local_minute==0&&(*exact)[0].day==BriefingOffsetBoard::Day::next&&(*exact)[1].local_minute==1439&&(*exact)[2].day==BriefingOffsetBoard::Day::same);check(!x.render(0,{{\"\",0}}));check(!x.render(1440,{}));",
        "time-satellite-phase-log": "SatellitePhaseLog x;auto huge=x.advance(97,3,{LLONG_MAX,LLONG_MIN},42);long long model=3;for(long long step:std::vector<long long>{LLONG_MAX,LLONG_MIN}){model=(model+step%97)%97;if(model<0)model+=97;}check(huge.valid&&huge.phase==model);check(x.advance(8,0,{},4).correction==-4);check(!x.advance(0,0,{},0).valid);",
        "time-school-bell-repair": "SchoolBellRepair x;check(!x.repair({{1,10},{1,20}},{}).valid);auto r=x.repair({{4,1435},{2,30}},{{SchoolBellRepair::Kind::delay,4,10},{SchoolBellRepair::Kind::insert,3,5},{SchoolBellRepair::Kind::insert,2,8},{SchoolBellRepair::Kind::delay,9,1}});check(r.valid&&r.diagnostics==2&&r.bells.size()==3&&r.bells[0].id==3&&r.bells[1].id==4&&r.bells[2].id==2);auto c=x.repair({{1,5}},{{SchoolBellRepair::Kind::cancel,1,999}});check(c.valid&&c.bells.empty());",
        "time-oven-program": "OvenProgram x({{\"a\",2},{\"b\",3},{\"c\",4}});auto before=x.snapshot();check(before.valid&&before.program_remaining==9);check(!x.advance(-1).valid);auto same=x.snapshot();check(same.stage_index==0&&same.program_remaining==9);auto all=x.advance(99);check(all.valid&&all.completed&&all.completed_actions==std::vector<std::string>({\"a\",\"b\",\"c\"}));check(x.advance(1).completed);OvenProgram bad({{\"x\",INT_MAX},{\"y\",1}});check(!bad.snapshot().valid);",
    }
    body = private[s.task_id] if hidden else visible[s.task_id]
    includes = '#include "task.h"\n#include <climits>\n#include <vector>\n'
    return (
        includes
        + "int main(){int failures=0;auto check=[&](bool ok){if(!ok)++failures;}"
        + ";using namespace curriculum;" + body + "return failures?1:0;}\n"
    )


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(clock_arithmetic_v2 LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
enable_testing()
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(target task_visible task_hidden)
  target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
'''


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _sha_bytes(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _source_hash(path: Path | None = None) -> str:
    return _sha_bytes((path or Path(__file__)).read_bytes())


def _tree_hash(root: Path, *, include_state: bool = False) -> str:
    if not root.is_dir():
        return "not_available"
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if not include_state and ".state" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _negative_source(s: TaskSpec) -> str:
    reference = _reference(s)
    if reference.count(s.negative_old) != 1:
        _fail("invariant_not_enforced", f"negative mutation drift: {s.task_id}")
    return reference.replace(s.negative_old, s.negative_new, 1)


def _remedy_markdown(s: TaskSpec) -> str:
    header = _header(s).replace("\n", " ").strip()
    return f"""## Identity

Task ID: `{s.task_id}`; task-spec revision: 2; family ID: `{FAMILY_ID}/{s.task_id}`; disposition: `repair-in-place`; source inventory: `clock-arithmetic-legacy-v1`; license result: repository-authored/pass; generator: `{GENERATOR_PATH}`; benchmark screen: pending. Selected prompt: `{PROMPT_PATH}` with `FAMILY_NAME=clock-arithmetic`, `FAMILY_TYPE=aider-text-grid-reshaping`. The requested legacy path `{REQUESTED_LEGACY_ROOT}` is absent; immutable audit evidence comes from the actual owner-generated legacy path `{LEGACY_ROOT}`.

## Objective

{s.contract}

## Public API

C++17 namespace `curriculum`; editable order is `{s.task_id}.h`, then `{s.task_id}.cpp`. Complete declarations: `{header}` Inputs and outputs are owned values. Invalid calls use the documented report/nullopt behavior and do not partially mutate persistent state.

## Behavior table

Valid, invalid, duplicate, absent, empty, mutation, ordering, tie, overflow, and cycle-boundary behavior are fully specified in `.docs/instructions.md`. The public and private executables cover the published boundary rules; no private test introduces an undisclosed policy.

## Implementation invariant

Required mechanism: {s.mechanism}. The reference must contain the emitted mechanism marker `{s.reference_marker}`. Forbidden substitutes are a reusable clock value object, host time or time-zone lookup, hard-coded examples, an official holdout implementation, or another counted root's algorithm. Topic-specific false substitute: {s.negative_reason}.

## Starter and reference

The task-named header declares the complete API and the task-named source is a coherent incomplete stub. `.meta/example.cpp` independently implements the required mechanism without importing legacy renderers, hidden fixtures, or benchmark assets. `.meta/negative_false_substitute.cpp` is a strict-compiling behavioral error.

## Tests

`task_visible_test.cpp` covers ordinary documented behavior. `.meta/task_hidden_test.cpp` covers empty/invalid input, exact boundaries, cyclic crossings, deterministic ordering or state preservation, and the named negative. The all-pairs screen derives seven dimensions from actual docs/API/reference/tests/negative files. Coherent identifier/domain-renamed, constants/policy-only, and opposite-end-selection clones must build, pass their internally consistent tests, and be rejected in all seven dimensions by the production evaluator.

## Files and metadata

Solutions: `{s.task_id}.h`, `{s.task_id}.cpp`; visible test: `task_visible_test.cpp`; private test: `.meta/task_hidden_test.cpp`; references: `.meta/example.h`, `.meta/example.cpp`; false substitute: `.meta/negative_false_substitute.cpp`. Config maps one reference per solution suffix. Docs, tests, metadata, CMake, references, controls, manifests, and receipts remain private.

## Build/oracle

C++17 with `-Wall -Wextra -Wpedantic -Werror`, explicit `Unix Makefiles`, and exactly two positive CTest discoveries. Run clean normal and fresh ASan/UBSan builds in `{SANITY_IMAGE}` with Docker network `none`. The receipt binds independently computed mounted hashes, owner/reference/negative hashes, image identity, compiler/CMake identity, commands, and equal counts.

## Family/contamination

The user-authorized hard count is {MIN_ROOTS}-{MAX_ROOTS}; this owner emits {len(TASKS)} counted roots and compares all {len(TASKS) * (len(TASKS) - 1) // 2} unordered pairs separately across all seven hard-rule dimensions. Screen every counted root against all 26 bound official C++ holdouts using `{SEMANTIC_NORMALIZER}`. Official `clock`, `gigasecond`, and `meetup` remain permanent holdouts.

## Optional dataset handoff

`not_requested`. No JSONL, token/mask evidence, split, export, consumer verification, training, or release is authorized.

## Acceptance

Run focused pytest, owner `--verify-core`, owner `--verify` for truthful host iteration evidence, and owner `--docker-sanity`. Require deterministic regeneration, strict prompt/role/reference mapping, {len(TASKS)} roots within the authorized {MIN_ROOTS}-{MAX_ROOTS} bound, every pair distinct in every hard dimension, all three coherent controls rejected in all seven dimensions, 260 holdout comparisons, executed rejection of all topic negatives in both modes, and two equal positive normal/fresh-sanitizer tests for every root and control. Stable failures include `remedy_spec_incomplete`, `hard_rule_root_count`, `hard_rule_evidence_incomplete`, `prompt_contract_incomplete`, `invariant_not_enforced`, `duplicate_family`, `benchmark_content_overlap`, `generator_output_drift`, `negative_fixture_not_rejected`, `grader_mount_hash_mismatch`, and `sanitizer_test_count_mismatch`.
"""


def _write_remedies(out: Path, force: bool) -> None:
    remedy_root = out / ".state/remedy"
    for s in TASKS:
        markdown = _remedy_markdown(s)
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": s.task_id,
            "family_id_before": FAMILY_ID_BEFORE,
            "family_id_after": f"{FAMILY_ID}/{s.task_id}",
            "tree_hash_before": _tree_hash(LEGACY_ROOT / s.task_id),
            "requested_legacy_root": str(REQUESTED_LEGACY_ROOT),
            "actual_legacy_root": str(LEGACY_ROOT),
            "requested_legacy_root_status": "absent",
            "generator_path": GENERATOR_PATH,
            "generator_revision": LEGACY_GENERATOR_REVISION,
            "selected_prompt": PROMPT_PATH,
            "user_inputs": {
                "FAMILY_NAME": "clock-arithmetic",
                "FAMILY_TYPE": "aider-text-grid-reshaping",
                "hard_rule_root_count": "8-12",
            },
            "finding_ids": [
                "CA-F1-under-specified-prompt-contracts",
                "CA-F2-private-tests-repeat-visible-cases",
                "CA-F3-no-executed-topic-negatives",
                "CA-F4-no-seven-dimension-family-screen",
                "CA-F5-host-only-unrecorded-oracle",
                "CA-F6-no-bound-holdout-semantic-screen",
                "CA-F7-requested-family-type-mismatch",
            ],
            "disposition": "repair-in-place",
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": f".state/remedy/{s.task_id}.md",
            "remedy_spec_hash": _sha_bytes(markdown.encode()),
            "status": "planned",
            "primary_core_objective": "specified",
            "dataset_handoff": "not_requested",
        }
        _write(remedy_root / f"{s.task_id}.md", markdown, force)
        _write(
            remedy_root / f"{s.task_id}.json",
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            force,
        )


def _case_files(s: TaskSpec) -> dict[str, str]:
    header = _header(s)
    config = {
        "authors": ["w8-biayn"],
        "blurb": s.contract,
        "files": {
            "solution": ["task.h", "task.cpp"],
            "test": ["task_visible_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "family_id": FAMILY_ID,
        "task_id": s.task_id,
        "legacy_task_id": s.task_id,
        "disposition": "repair-in-place",
        "curriculum_document": CURRICULUM,
        "family_spec": FAMILY_SPEC,
        "selected_prompt": PROMPT_PATH,
        "origin": "independently authored repository remediation",
        "license_result": "repository-authored/pass",
        "semantic_profile": s.mechanism,
        "primary_core_objective": "achieved",
        "status": "local candidate artifact; dataset handoff not requested",
    }
    return {
        ".docs/introduction.md": (
            f"# {s.title}\n\n{s.contract}\n\n"
            "This deterministic diagnostic never reads host time or a time-zone database.\n"
        ),
        ".docs/instructions.md": _instructions(s),
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": (
            f'[visible]\ndescription = "published behavior for {s.title}"\n\n'
            f'[hidden]\ndescription = "boundary, invalid, state/order, and {s.negative_reason} rejection"\n'
        ),
        "task.h": header,
        "task.cpp": _starter(s),
        ".meta/example.h": header,
        ".meta/example.cpp": _reference(s),
        ".meta/negative_false_substitute.cpp": _negative_source(s),
        "task_visible_test.cpp": _test(s, False),
        ".meta/task_hidden_test.cpp": _test(s, True),
        "CMakeLists.txt": _cmake(),
    }


def _control_files(name: str) -> dict[str, str]:
    base = TASKS[0] if name != "opposite-end-selection-clone" else TASKS[8]
    files = _case_files(base)
    selected = {
        "task.h": files["task.h"],
        "candidate.cpp": files[".meta/example.cpp"],
        ".docs/instructions.md": files[".docs/instructions.md"],
        "task_visible_test.cpp": files["task_visible_test.cpp"],
        ".meta/task_hidden_test.cpp": files[".meta/task_hidden_test.cpp"],
        ".meta/negative_false_substitute.cpp": files[".meta/negative_false_substitute.cpp"],
        ".meta/provenance.json": files[".meta/provenance.json"],
        "CMakeLists.txt": files["CMakeLists.txt"],
    }
    if name == "domain-identifier-renamed-clone":
        replacements = (
            ("ParkingGraceAudit", "MooringGraceAudit"),
            ("parking", "mooring"),
            ("Parking", "Mooring"),
        )
        for relative, content in tuple(selected.items()):
            for old, new in replacements:
                content = content.replace(old, new)
            selected[relative] = content
    elif name == "constants-policy-only-clone":
        selected["candidate.cpp"] = selected["candidate.cpp"].replace(
            "elapsed>grace?elapsed-grace:0", "elapsed>=grace?elapsed-grace+1:0"
        )
        for relative in ("task_visible_test.cpp", ".meta/task_hidden_test.cpp"):
            selected[relative] = selected[relative].replace(
                "chargeable_minutes==0", "chargeable_minutes==1"
            )
        selected["task_visible_test.cpp"] = selected["task_visible_test.cpp"].replace(
            "audit(20,50,false,10).chargeable_minutes==20",
            "audit(20,50,false,10).chargeable_minutes==21",
        )
        selected[".meta/task_hidden_test.cpp"] = selected[
            ".meta/task_hidden_test.cpp"
        ].replace(
            "audit(1439,0,true,0).chargeable_minutes==1",
            "audit(1439,0,true,0).chargeable_minutes==2",
        )
        selected[".docs/instructions.md"] = selected[".docs/instructions.md"].replace(
            "equality is free", "equality charges one minute"
        ).replace("strictly beyond grace", "at or beyond grace")
    elif name == "opposite-end-selection-clone":
        selected["candidate.cpp"] = selected["candidate.cpp"].replace(
            "x.minute!=y.minute?x.minute<y.minute:x.id<y.id",
            "x.minute!=y.minute?x.minute>y.minute:x.id>y.id",
        )
        selected["task_visible_test.cpp"] = selected["task_visible_test.cpp"].replace(
            "r.bells[0].id==2&&r.bells[1].minute==25",
            "r.bells[0].id==1&&r.bells[1].minute==20",
        )
        selected[".meta/task_hidden_test.cpp"] = selected[
            ".meta/task_hidden_test.cpp"
        ].replace(
            "r.bells[0].id==3&&r.bells[1].id==4&&r.bells[2].id==2",
            "r.bells[0].id==2&&r.bells[1].id==4&&r.bells[2].id==3",
        )
        selected[".docs/instructions.md"] = selected[".docs/instructions.md"].replace(
            "sorted by repaired minute, then ID", "sorted by repaired minute descending, then ID descending"
        )
    else:
        _fail("adversarial_control_invalid", name)
    return selected


def _write_controls(out: Path, force: bool) -> None:
    root = out / ".state/hard-rule-controls"
    manifest: dict[str, object] = {
        "schema_version": "clock-arithmetic-hard-rule-controls-v1",
        "controls": {},
    }
    for name in ADVERSARIAL_CONTROLS:
        files = _control_files(name)
        base = TASKS[0] if name != "opposite-end-selection-clone" else TASKS[8]
        raw = _case_files(base)
        unmodified = {
            "task.h": raw["task.h"],
            "candidate.cpp": raw[".meta/example.cpp"],
            ".docs/instructions.md": raw[".docs/instructions.md"],
            "task_visible_test.cpp": raw["task_visible_test.cpp"],
            ".meta/task_hidden_test.cpp": raw[".meta/task_hidden_test.cpp"],
            ".meta/negative_false_substitute.cpp": raw[".meta/negative_false_substitute.cpp"],
            ".meta/provenance.json": raw[".meta/provenance.json"],
            "CMakeLists.txt": raw["CMakeLists.txt"],
        }
        changed = [
            relative
            for relative, content in files.items()
            if content != unmodified[relative]
        ]
        if not changed:
            _fail("adversarial_control_invalid", f"no-op control: {name}")
        for relative, content in files.items():
            _write(root / name / relative, content, force)
        manifest["controls"][name] = {
            "expected_compile": "pass",
            "expected_ctest": "pass",
            "expected_semantic_screen": "duplicate_family_all_seven_dimensions",
            "changed_files": sorted(changed),
        }
    _write(root / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", force)


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() in {LEGACY_ROOT.resolve(), REQUESTED_LEGACY_ROOT.resolve()}:
        _fail("legacy_root_immutable", str(out))
    if force:
        for name in (
            "materialization-manifest.json",
            "host-verification-receipt.json",
            "docker-sanity.json",
        ):
            (out / ".state" / name).unlink(missing_ok=True)
    _write_remedies(out, force)
    expected = {s.task_id for s in TASKS}
    if out.exists():
        foreign = {
            path.name for path in out.iterdir()
            if path.is_dir() and path.name != ".state"
        } - expected
        if foreign:
            _fail("generator_output_drift", f"foreign roots: {sorted(foreign)}")
    roots: list[Path] = []
    for s in TASKS:
        root = out / s.task_id
        for relative, content in task_named_files(root, _case_files(s)).items():
            _write(root / relative, content, force)
        roots.append(root)
    _write_controls(out, force)
    return tuple(roots)


_CPP_KEYWORDS = frozenset(
    "alignas alignof and and_eq asm auto bitand bitor bool break case catch char "
    "class compl const constexpr continue decltype default delete do double "
    "dynamic_cast else enum explicit export extern false float for friend goto if "
    "inline int long mutable namespace new noexcept not not_eq nullptr operator or "
    "or_eq private protected public register reinterpret_cast return short signed "
    "sizeof static static_assert static_cast struct switch template this thread_local "
    "throw true try typedef typeid typename union unsigned using virtual void volatile "
    "wchar_t while xor xor_eq".split()
)


def _normalized_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.M | re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " literal ", text)
    tokens = re.findall(
        r"[A-Za-z_][A-Za-z0-9_]*|==|!=|<=|>=|&&|\|\||[-+*/%<>{}()[\];,.?:=!&|]",
        text,
    )
    normalized: list[str] = []
    allowed = {
        "std", "vector", "optional", "string", "size_t", "sort", "min",
        "max", "find_if", "move", "numeric_limits",
    }
    for token in tokens:
        if token in {"begin", "rbegin", "end", "rend", "front", "back"}:
            normalized.append("endpoint")
        elif re.match(r"[A-Za-z_]", token) and token not in _CPP_KEYWORDS and token not in allowed:
            normalized.append("identifier")
        else:
            normalized.append(token)
    return tuple(normalized)


def _ngrams(tokens: tuple[str, ...], width: int = 7) -> set[tuple[str, ...]]:
    if len(tokens) < width:
        return {tokens} if tokens else set()
    return {tokens[index:index + width] for index in range(len(tokens) - width + 1)}


def _similarity(left: str, right: str) -> float:
    a = _ngrams(_normalized_tokens(left))
    b = _ngrams(_normalized_tokens(right))
    return 0.0 if not a or not b else len(a & b) / len(a | b)


def _artifact_dimensions(root: Path, *, control: bool = False) -> dict[str, str]:
    header = root / ("task.h" if control else f"{root.name}.h")
    reference = root / ("candidate.cpp" if control else ".meta/example.cpp")
    paths = {
        "header": header,
        "reference": reference,
        "instructions": root / ".docs/instructions.md",
        "visible": root / "task_visible_test.cpp",
        "hidden": root / ".meta/task_hidden_test.cpp",
        "negative": root / ".meta/negative_false_substitute.cpp",
        "provenance": root / ".meta/provenance.json",
    }
    for name, path in paths.items():
        if not path.is_file():
            _fail("hard_rule_evidence_incomplete", f"{root}: missing {name}")
    text = {name: path.read_text(encoding="utf-8") for name, path in paths.items()}
    return {
        "public_api": text["header"],
        "owned_state_or_algorithm": text["reference"] + text["provenance"],
        "mutation_or_selection_rules": text["instructions"] + text["reference"],
        "invalid_and_boundary_behavior": text["instructions"] + text["hidden"],
        "reference_control_flow": text["reference"],
        "deterministic_oracle": text["visible"] + text["hidden"],
        "topic_specific_negative_fixture": text["negative"] + text["hidden"],
    }


def _pair_decision(
    left: dict[str, str], right: dict[str, str], left_id: str, right_id: str,
) -> dict[str, object]:
    decisions = {
        dimension: {
            "similarity": _similarity(left[dimension], right[dimension]),
            "limit": HARD_RULE_LIMITS[dimension],
            "materially_distinct": _similarity(left[dimension], right[dimension])
            < HARD_RULE_LIMITS[dimension],
        }
        for dimension in HARD_RULE_DIMENSIONS
    }
    failed = [
        dimension for dimension, decision in decisions.items()
        if not decision["materially_distinct"]
    ]
    return {
        "left": left_id,
        "right": right_id,
        "dimensions": decisions,
        "failed_dimensions": failed,
        "materially_distinct_in_all_dimensions": not failed,
    }


def _validate_remedy(s: TaskSpec, out: Path) -> None:
    record_path = out / ".state/remedy" / f"{s.task_id}.json"
    spec_path = out / ".state/remedy" / f"{s.task_id}.md"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    markdown = spec_path.read_text(encoding="utf-8")
    if tuple(re.findall(r"^## (.+)$", markdown, flags=re.M)) != REMEDY_HEADINGS:
        _fail("remedy_spec_incomplete", s.task_id)
    if record.get("remedy_spec_hash") != _sha_bytes(markdown.encode()):
        _fail("remedy_spec_incomplete", f"hash: {s.task_id}")
    if record.get("disposition") != "repair-in-place":
        _fail("remedy_disposition_conflict", s.task_id)
    if record.get("tree_hash_before") != _tree_hash(LEGACY_ROOT / s.task_id):
        _fail("remedy_disposition_conflict", f"legacy hash: {s.task_id}")


def _validate_prompt_roles(s: TaskSpec, root: Path) -> None:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    expected = [f"{s.task_id}.h", f"{s.task_id}.cpp"]
    if config["files"]["solution"] != expected:
        _fail("prompt_contract_incomplete", f"solution order: {s.task_id}")
    roles = sum(
        (config["files"][key] for key in ("solution", "test", "example")), []
    )
    if len(set(roles)) != len(roles):
        _fail("unsafe_path", f"duplicate role: {s.task_id}")
    for value in roles:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or not (root / value).is_file():
            _fail("unsafe_path", f"{s.task_id}: {value}")
    task = load_task(root)
    prompt = build_prompt(task)
    for private in (
        "example.cpp", "task_hidden_test", "CMakeLists", "provenance.json",
        "negative_false_substitute", "tests.toml",
    ):
        if private in prompt:
            _fail("prompt_contract_incomplete", f"{s.task_id}: exposed {private}")
    for visible in (s.task_id + ".h", s.task_id + ".cpp", s.class_name):
        if visible not in prompt:
            _fail("prompt_contract_incomplete", f"{s.task_id}: absent {visible}")
    answer = build_assistant_response(
        task, load_example_files_from_config(root)
    )
    if not answer.startswith(f"{s.task_id}.h\n```") or f"{s.task_id}.cpp\n```" not in answer:
        _fail("target_reference_mismatch", s.task_id)


def _screen_controls(out: Path) -> dict[str, object]:
    base_for = {
        "domain-identifier-renamed-clone": TASKS[0],
        "constants-policy-only-clone": TASKS[0],
        "opposite-end-selection-clone": TASKS[8],
    }
    results: dict[str, object] = {}
    for name in ADVERSARIAL_CONTROLS:
        base = base_for[name]
        base_root = out / base.task_id
        control_root = out / ".state/hard-rule-controls" / name
        if _tree_hash(control_root, include_state=True) == "not_available":
            _fail("adversarial_control_invalid", name)
        decision = _pair_decision(
            _artifact_dimensions(base_root),
            _artifact_dimensions(control_root, control=True),
            base.task_id,
            name,
        )
        if set(decision["failed_dimensions"]) != set(HARD_RULE_DIMENSIONS):
            _fail(
                "duplicate_family",
                f"control escaped one or more dimensions: {name}: "
                f"{decision['failed_dimensions']}",
            )
        results[name] = {
            "status": "rejected",
            "reason": "duplicate_family",
            "production_evaluator": True,
            "changed_files": sorted(_control_files(name)),
            "decision": decision,
        }
    return results


def _holdout_screen(
    out: Path, holdout_root: Path = DEFAULT_HOLDOUT_ROOT,
) -> dict[str, object]:
    if not holdout_root.is_dir():
        return {
            "status": "not_completed",
            "reason": f"missing {holdout_root}",
            "holdout_root_count": 0,
            "comparison_count": 0,
        }
    holdouts = sorted(
        path for path in holdout_root.iterdir()
        if path.is_dir() and path.name in OFFICIAL_AIDER_CPP_HOLDOUTS
    )
    if {path.name for path in holdouts} != OFFICIAL_AIDER_CPP_HOLDOUTS:
        _fail("benchmark_content_overlap", "incomplete bound holdout inventory")
    normalized_holdouts = {
        holdout.name: "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in holdout.rglob("*")
            if path.is_file() and path.stat().st_size < 2_000_000
        )
        for holdout in holdouts
    }
    comparisons_count = 0
    strongest = {"score": 0.0, "candidate": None, "holdout": None}
    for s in TASKS:
        candidate = "\n".join(_artifact_dimensions(out / s.task_id).values())
        for holdout_id, content in normalized_holdouts.items():
            score = _similarity(candidate, content)
            if score > strongest["score"]:
                strongest = {
                    "score": score,
                    "candidate": s.task_id,
                    "holdout": holdout_id,
                }
            if score >= 0.90:
                _fail(
                    "benchmark_content_overlap",
                    f"{s.task_id}/{holdout_id}: {score:.3f}",
                )
            comparisons_count += 1
    return {
        "status": "pass",
        "normalizer": SEMANTIC_NORMALIZER,
        "holdout_root_count": len(holdouts),
        "comparison_count": comparisons_count,
        "strongest_comparison": strongest,
    }


def verify_core(out: Path) -> dict[str, object]:
    if not MIN_ROOTS <= len(TASKS) <= MAX_ROOTS:
        _fail("hard_rule_root_count", f"{len(TASKS)} not in {MIN_ROOTS}-{MAX_ROOTS}")
    expected = {s.task_id for s in TASKS}
    actual = {
        path.name for path in out.iterdir()
        if path.is_dir() and path.name != ".state"
    }
    if actual != expected:
        _fail("generator_output_drift", f"expected {sorted(expected)}, got {sorted(actual)}")
    dimensions: dict[str, dict[str, str]] = {}
    for s in TASKS:
        _validate_remedy(s, out)
        root = out / s.task_id
        _validate_prompt_roles(s, root)
        reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
        if s.reference_marker not in reference:
            _fail("invariant_not_enforced", f"{s.task_id}: {s.reference_marker}")
        dimensions[s.task_id] = _artifact_dimensions(root)
    pairs = []
    for left, right in combinations(TASKS, 2):
        decision = _pair_decision(
            dimensions[left.task_id], dimensions[right.task_id],
            left.task_id, right.task_id,
        )
        if not decision["materially_distinct_in_all_dimensions"]:
            _fail(
                "duplicate_family",
                f"{left.task_id}/{right.task_id}: {decision['failed_dimensions']}",
            )
        pairs.append(decision)
    expected_pairs = len(TASKS) * (len(TASKS) - 1) // 2
    if len(pairs) != expected_pairs:
        _fail("hard_rule_evidence_incomplete", "pair count")
    controls = _screen_controls(out)
    holdouts = _holdout_screen(out)
    manifest = {
        "schema_version": "clock-arithmetic-materialization-v2",
        "family_id": FAMILY_ID,
        "task_count": len(TASKS),
        "task_ids": [s.task_id for s in TASKS],
        "hard_rule_root_bounds": {"minimum": MIN_ROOTS, "maximum": MAX_ROOTS},
        "requested_legacy_root": str(REQUESTED_LEGACY_ROOT),
        "requested_legacy_root_status": "absent",
        "actual_legacy_root": str(LEGACY_ROOT),
        "legacy_root_immutable": True,
        "tree_hash": _tree_hash(out),
        "owner_hash": _source_hash(),
        "status": "implemented",
        "screen": {
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
            "hard_rule": {
                "status": "pending_execution",
                "dimensions": list(HARD_RULE_DIMENSIONS),
                "dimension_limits": HARD_RULE_LIMITS,
                "pair_count": len(pairs),
                "expected_pair_count": expected_pairs,
                "pairs": pairs,
            },
            "adversarial_controls": controls,
            "semantic_holdout": holdouts,
        },
        "dataset_handoff": "not_requested",
    }
    _write(
        out / ".state/materialization-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        True,
    )
    return manifest


def _ctest_count(build_dir: Path) -> int:
    result = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "--show-only=json-v1"],
        check=True, capture_output=True, text=True,
    )
    count = len(json.loads(result.stdout)["tests"])
    if count <= 0:
        _fail("zero_tests", str(build_dir))
    return count


def verify(out: Path) -> dict[str, object]:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        missing = [name for name in ("cmake", "c++") if shutil.which(name) is None]
        receipt = {
            "schema_version": "clock-arithmetic-host-iteration-v1",
            "status": "not_completed",
            "reason": "host verification requires both cmake and c++",
            "blocked_command": f"{WRAPPER_PATH} --force --verify-core --verify",
            "missing_prerequisites": missing,
            "evidence_class": "host_iteration",
            "local_family_verified": False,
            "tree_hash": _tree_hash(out),
        }
        _write(
            out / ".state/host-verification-receipt.json",
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            True,
        )
        return receipt
    records: list[dict[str, object]] = []
    for s in TASKS:
        root = out / s.task_id
        with tempfile.TemporaryDirectory(prefix="clock-arithmetic-host-") as temporary:
            copied = Path(temporary) / s.task_id
            shutil.copytree(root, copied)
            counts: dict[str, int] = {}
            for mode, flags in (
                ("normal", []),
                (
                    "sanitizer",
                    [
                        "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
                        "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
                    ],
                ),
            ):
                build_dir = copied / f"build-{mode}"
                subprocess.run(
                    [
                        "cmake", "-S", str(copied), "-B", str(build_dir),
                        "-G", "Unix Makefiles",
                        f"-DTASK_SOURCE={copied / '.meta/example.cpp'}", *flags,
                    ],
                    check=True, capture_output=True, text=True,
                )
                subprocess.run(
                    ["cmake", "--build", str(build_dir), "--parallel", "2"],
                    check=True, capture_output=True, text=True,
                )
                counts[mode] = _ctest_count(build_dir)
                subprocess.run(
                    ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
                    check=True, capture_output=True, text=True,
                )
            if counts["normal"] != counts["sanitizer"]:
                _fail("sanitizer_test_count_mismatch", s.task_id)
            negative_build = copied / "build-negative"
            subprocess.run(
                [
                    "cmake", "-S", str(copied), "-B", str(negative_build),
                    "-G", "Unix Makefiles",
                    f"-DTASK_SOURCE={copied / '.meta/negative_false_substitute.cpp'}",
                ],
                check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["cmake", "--build", str(negative_build), "--parallel", "2"],
                check=True, capture_output=True, text=True,
            )
            rejected = subprocess.run(
                ["ctest", "--test-dir", str(negative_build), "--output-on-failure"],
                capture_output=True, text=True,
            ).returncode != 0
            if not rejected:
                _fail("negative_fixture_not_rejected", s.task_id)
            records.append({
                "task_id": s.task_id,
                "normal_tests": counts["normal"],
                "sanitizer_tests": counts["sanitizer"],
                "negative_rejected": True,
            })
    receipt = {
        "schema_version": "clock-arithmetic-host-iteration-v1",
        "status": "pass",
        "evidence_class": "host_iteration",
        "local_family_verified": False,
        "tree_hash": _tree_hash(out),
        "records": records,
    }
    _write(
        out / ".state/host-verification-receipt.json",
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        True,
    )
    return receipt


DOCKER_RUNNER = r'''import hashlib,json,os,pathlib,shutil,subprocess,tarfile
archive=pathlib.Path("/input/family.tar")
root=pathlib.Path("/tmp/clock-family")
if root.exists(): shutil.rmtree(root)
root.mkdir()
with tarfile.open(archive) as handle: handle.extractall(root)
expected=json.loads(pathlib.Path("/input/expected.json").read_text())
def tree_hash(path):
    digest=hashlib.sha256()
    for item in sorted(value for value in path.rglob("*") if value.is_file()):
        digest.update(item.relative_to(path).as_posix().encode());digest.update(b"\0")
        digest.update(item.read_bytes());digest.update(b"\0")
    return "sha256:"+digest.hexdigest()
def configure_and_run(task_id,path,source,mode):
    build=pathlib.Path("/tmp/clock-build")/task_id/mode
    if build.exists(): shutil.rmtree(build)
    args=["cmake","-S",str(path),"-B",str(build),"-G","Unix Makefiles",
          "-DCMAKE_CXX_COMPILER=/usr/local/bin/g++","-DTASK_SOURCE="+str(source)]
    if mode.endswith("sanitizer"):
        args += ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
                 "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]
    subprocess.run(args,check=True,capture_output=True,text=True,timeout=120)
    subprocess.run(["cmake","--build",str(build),"--parallel","2"],check=True,capture_output=True,text=True,timeout=120)
    shown=subprocess.run(["ctest","--test-dir",str(build),"--show-only=json-v1"],check=True,capture_output=True,text=True,timeout=30)
    count=len(json.loads(shown.stdout)["tests"])
    env=dict(os.environ);env["ASAN_OPTIONS"]="detect_leaks=0"
    run=subprocess.run(["ctest","--test-dir",str(build),"--output-on-failure"],env=env,capture_output=True,text=True,timeout=30)
    return count,run.returncode
task_results=[]
for task_id,want in expected["tasks"].items():
    task=root/"tasks"/task_id
    got=tree_hash(task)
    if got!=want: raise SystemExit("grader_mount_hash_mismatch:"+task_id+":"+got+":"+want)
    for mode in ("normal","sanitizer"):
        count,status=configure_and_run(task_id,task,task/".meta/example.cpp",mode)
        if count!=2 or status!=0: raise SystemExit("reference_tests_failed:"+task_id+":"+mode)
        negative_count,negative_status=configure_and_run(task_id+"-negative",task,task/".meta/negative_false_substitute.cpp",mode)
        if negative_count!=2 or negative_status==0: raise SystemExit("negative_fixture_not_rejected:"+task_id+":"+mode)
        task_results.append({"task_id":task_id,"mode":mode,"test_count":count,
          "negative_test_count":negative_count,"negative_rejected":True,"mounted_tree_hash":got})
control_results=[]
for name,want in expected["controls"].items():
    control=root/"controls"/name
    got=tree_hash(control)
    if got!=want: raise SystemExit("grader_mount_hash_mismatch:control:"+name)
    for mode in ("normal","sanitizer"):
        count,status=configure_and_run("control-"+name,control,control/"candidate.cpp",mode)
        if count!=2 or status!=0: raise SystemExit("adversarial_control_invalid:"+name+":"+mode)
        control_results.append({"control":name,"mode":mode,"test_count":count,"mounted_tree_hash":got})
compiler=pathlib.Path("/usr/local/bin/g++")
toolchain={"compiler_path":str(compiler),
 "compiler_version":subprocess.run([str(compiler),"--version"],check=True,capture_output=True,text=True).stdout.splitlines()[0],
 "compiler_hash":"sha256:"+hashlib.sha256(compiler.read_bytes()).hexdigest(),
 "cmake_version":subprocess.run(["cmake","--version"],check=True,capture_output=True,text=True).stdout.splitlines()[0]}
pathlib.Path("/output/result.json").write_text(json.dumps({"tasks":task_results,"controls":control_results,"toolchain":toolchain},sort_keys=True))
'''


def _write_deterministic_archive(out: Path, archive: Path) -> str:
    entries: list[tuple[str, Path]] = []
    for s in TASKS:
        root = out / s.task_id
        for path in sorted(value for value in root.rglob("*") if value.is_file()):
            entries.append((f"tasks/{s.task_id}/{path.relative_to(root).as_posix()}", path))
    for name in ADVERSARIAL_CONTROLS:
        root = out / ".state/hard-rule-controls" / name
        for path in sorted(value for value in root.rglob("*") if value.is_file()):
            entries.append((f"controls/{name}/{path.relative_to(root).as_posix()}", path))
    with tarfile.open(archive, "w") as handle:
        for relative, path in entries:
            content = path.read_bytes()
            info = tarfile.TarInfo(relative)
            info.size = len(content)
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mode = 0o644
            with tempfile.SpooledTemporaryFile() as stream:
                stream.write(content)
                stream.seek(0)
                handle.addfile(info, stream)
    return _sha_bytes(archive.read_bytes())


def docker_sanity(out: Path, image: str = SANITY_IMAGE) -> dict[str, object]:
    if shutil.which("docker") is None:
        _fail("docker_sanity_not_completed", "docker executable unavailable")
    manifest = verify_core(out)
    holdout = manifest["screen"]["semantic_holdout"]
    if holdout["status"] != "pass" or holdout["holdout_root_count"] != 26:
        _fail("benchmark_content_overlap", f"holdout screen: {holdout}")
    inspect = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        capture_output=True, text=True,
    )
    if inspect.returncode != 0:
        _fail("docker_sanity_not_completed", inspect.stderr.strip())
    task_hashes = {s.task_id: _tree_hash(out / s.task_id) for s in TASKS}
    control_hashes = {
        name: _tree_hash(out / ".state/hard-rule-controls" / name, include_state=True)
        for name in ADVERSARIAL_CONTROLS
    }
    with tempfile.TemporaryDirectory(prefix="clock-arithmetic-docker-") as temporary:
        temporary_root = Path(temporary)
        archive = temporary_root / "family.tar"
        archive_hash = _write_deterministic_archive(out, archive)
        (temporary_root / "expected.json").write_text(
            json.dumps({"tasks": task_hashes, "controls": control_hashes}, sort_keys=True),
            encoding="utf-8",
        )
        (temporary_root / "runner.py").write_text(DOCKER_RUNNER, encoding="utf-8")
        output = temporary_root / "output"
        output.mkdir()
        result = subprocess.run(
            [
                "docker", "run", "--rm", "--network", "none",
                "-v", f"{temporary_root}:/input:ro",
                "-v", f"{output}:/output",
                image, "python3", "/input/runner.py",
            ],
            capture_output=True, text=True, timeout=1800,
        )
        if result.returncode != 0:
            _fail(
                "docker_sanity_failed",
                (result.stdout + "\n" + result.stderr)[-12000:],
            )
        raw = json.loads((output / "result.json").read_text(encoding="utf-8"))
    task_records: dict[str, dict[str, object]] = {}
    for s in TASKS:
        records = [item for item in raw["tasks"] if item["task_id"] == s.task_id]
        if {item["mode"] for item in records} != {"normal", "sanitizer"}:
            _fail("docker_sanity_incomplete", s.task_id)
        if any(item["test_count"] != 2 or item["negative_test_count"] != 2 for item in records):
            _fail("sanitizer_test_count_mismatch", s.task_id)
        if any(item["mounted_tree_hash"] != task_hashes[s.task_id] for item in records):
            _fail("grader_mount_hash_mismatch", s.task_id)
        task_records[s.task_id] = {
            "normal_tests": 2,
            "sanitizer_tests": 2,
            "negative_normal": "rejected",
            "negative_sanitizer": "rejected",
            "tree_hash": task_hashes[s.task_id],
            "mounted_tree_hash": task_hashes[s.task_id],
            "reference_hash": _source_hash(out / s.task_id / ".meta/example.cpp"),
            "negative_hash": _source_hash(out / s.task_id / ".meta/negative_false_substitute.cpp"),
        }
    control_records: dict[str, dict[str, object]] = {}
    for name in ADVERSARIAL_CONTROLS:
        records = [item for item in raw["controls"] if item["control"] == name]
        if {item["mode"] for item in records} != {"normal", "sanitizer"}:
            _fail("docker_sanity_incomplete", f"control: {name}")
        if any(item["test_count"] != 2 for item in records):
            _fail("sanitizer_test_count_mismatch", f"control: {name}")
        if any(item["mounted_tree_hash"] != control_hashes[name] for item in records):
            _fail("grader_mount_hash_mismatch", f"control: {name}")
        control_records[name] = {
            "normal_tests": 2,
            "sanitizer_tests": 2,
            "tree_hash": control_hashes[name],
            "mounted_tree_hash": control_hashes[name],
            "semantic_screen": "duplicate_family_all_seven_dimensions",
        }
    receipt: dict[str, object] = {
        "schema_version": "clock-arithmetic-docker-sanity-v1",
        "status": "local_family_verified",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "image": image,
        "image_id": inspect.stdout.strip(),
        "network_policy": "none",
        "archive_hash": archive_hash,
        "family_tree_hash": _tree_hash(out),
        "owner_hash": _source_hash(),
        "toolchain": raw["toolchain"],
        "commands": [
            "exact deterministic archive mounted read-only",
            "clean normal CMake/CTest with explicit Unix Makefiles",
            "fresh ASan/UBSan CMake/CTest",
            "strict build and executed-test rejection of each topic false substitute in both modes",
            "strict build and passing tests for every coherent adversarial clone in both modes",
        ],
        "tasks": task_records,
        "hard_rule": {
            "root_bounds": {"minimum": MIN_ROOTS, "maximum": MAX_ROOTS},
            "root_count": len(TASKS),
            "pair_count": len(TASKS) * (len(TASKS) - 1) // 2,
            "dimensions": list(HARD_RULE_DIMENSIONS),
            "status": "pass",
        },
        "hard_rule_controls": control_records,
        "benchmark_screen": holdout,
        "dataset_handoff": "not_requested",
    }
    receipt_hash = _sha_bytes(json.dumps(receipt, sort_keys=True).encode())
    receipt["receipt_hash"] = receipt_hash
    _write(
        out / ".state/docker-sanity.json",
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        True,
    )
    for s in TASKS:
        record_path = out / ".state/remedy" / f"{s.task_id}.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record.update({
            "status": "verified",
            "primary_core_objective": "achieved",
            "tree_hash_after": task_hashes[s.task_id],
            "benchmark_screen": "pass",
            "family_screen": "pass",
            "hard_rule_status": "pass",
            "hard_rule_pair_count": len(TASKS) * (len(TASKS) - 1) // 2,
            "hard_rule_dimensions": list(HARD_RULE_DIMENSIONS),
            "prompt_boundary": "pass",
            "normal_test_count": 2,
            "sanitizer_test_count": 2,
            "negative_fixture_normal": "rejected",
            "negative_fixture_sanitizer": "rejected",
            "oracle_receipt": ".state/docker-sanity.json",
            "oracle_receipt_hash": receipt_hash,
            "strongest_local_status": "local_family_verified",
        })
        _write(
            record_path, json.dumps(record, indent=2, sort_keys=True) + "\n", True
        )
    manifest["status"] = "local_family_verified"
    manifest["screen"]["hard_rule"]["status"] = "pass"
    manifest["docker_receipt"] = ".state/docker-sanity.json"
    manifest["docker_receipt_hash"] = receipt_hash
    _write(
        out / ".state/materialization-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        True,
    )
    return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    if args.docker_sanity:
        docker_sanity(args.out, args.image)
    print(f"Wrote {len(roots)} remediated clock-arithmetic tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
