"""Materialize general-calendar-arithmetic local Aider tasks."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dates-and-clocks/general-calendar-arithmetic")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_GENERAL_CALENDAR_ARITHMETIC_CURRICULUM.md"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    title: str
    contract: str
    declaration: str
    implementation: str
    checks: str


TASKS = (
    TaskSpec("calendar-subscription-cycle", "SubscriptionCycle", "Subscription cycle manager", "Advance each unique subscriber by its positive policy cadence for the requested positive number of cycles. Preserve its anchor day on every advance; unavailable days clamp to month end. Invalid input returns an invalid report without partial rows.", "struct Subscriber { std::string id; CivilDate renewal; int cadence_months; }; struct Entry { std::string id; CivilDate next_renewal; bool clamped; }; struct Report { bool valid=false; std::vector<Entry> entries; }; Report renew(const std::vector<Subscriber>& subscribers, int cycles) const;", "SubscriptionCycle::Report SubscriptionCycle::renew(const std::vector<Subscriber>& xs,int cycles)const { if(cycles<=0)return {}; std::set<std::string> seen; Report out{true,{}}; for(auto x:xs){if(x.id.empty()||!valid(x.renewal)||x.cadence_months<=0||!seen.insert(x.id).second)return {}; bool clamped=false;CivilDate d=add_months(x.renewal,cycles*x.cadence_months,&clamped);out.entries.push_back({x.id,d,clamped});}return out; }", "SubscriptionCycle x;auto r=x.renew({{{\"a\",{2024,1,31},1}}},2);check(r.valid&&r.entries[0].next_renewal==CivilDate{2024,3,31});check(!x.renew({{{\"a\",{2024,2,30},1}}},1).valid);"),
    TaskSpec("calendar-harvest-plan", "HarvestPlan", "Harvest plan rollover", "Shift inclusive planting and harvest windows by a non-negative season-month count, using end-of-month clamping. Keep every crop row and mark an invalid shifted window instead of silently wrapping a year.", "struct Window { std::string crop; CivilDate planting; CivilDate harvest; }; struct Entry { std::string crop; CivilDate planting; CivilDate harvest; bool valid_window; }; std::vector<Entry> shift(const std::vector<Window>& windows, int season_months) const;", "std::vector<HarvestPlan::Entry> HarvestPlan::shift(const std::vector<Window>& xs,int months)const {std::vector<Entry> out;if(months<0)return out;for(auto x:xs){if(x.crop.empty()||!valid(x.planting)||!valid(x.harvest)){out.push_back({x.crop,{}, {},false});continue;}auto p=add_months(x.planting,months);auto h=add_months(x.harvest,months);out.push_back({x.crop,p,h,cmp(p,h)<=0});}return out;}", "HarvestPlan x;auto r=x.shift({{{\"pea\",{2024,1,31},{2024,2,29}}}},1);check(r.size()==1&&r[0].planting==CivilDate{2024,2,29}&&r[0].valid_window);"),
    TaskSpec("calendar-clinic-followup", "ClinicFollowup", "Clinic follow-up planner", "Generate no more than the requested positive count of follow-ups at a positive month interval through an inclusive horizon. A blackout date produces an explicit unscheduled row rather than an adjusted appointment.", "struct Plan { std::string patient_id; CivilDate start; int interval_months; int maximum_count; CivilDate horizon; }; struct Blackout { std::string id; CivilDate day; }; struct Entry { CivilDate day; bool scheduled; std::string reason; }; struct Report { bool valid=false; std::vector<Entry> entries; }; Report schedule(const Plan& plan, const std::vector<Blackout>& blackouts) const;", "ClinicFollowup::Report ClinicFollowup::schedule(const Plan& p,const std::vector<Blackout>& bs)const {if(p.patient_id.empty()||!valid(p.start)||!valid(p.horizon)||p.interval_months<=0||p.maximum_count<=0||cmp(p.start,p.horizon)>0)return {};std::set<std::string> ids;std::set<std::tuple<int,int,int>> days;for(auto b:bs){if(b.id.empty()||!valid(b.day)||!ids.insert(b.id).second)return {};days.insert({b.day.year,b.day.month,b.day.day});}Report out{true,{}};for(int i=1;i<=p.maximum_count;++i){auto d=add_months(p.start,i*p.interval_months);if(cmp(d,p.horizon)>0)break;bool blocked=days.count({d.year,d.month,d.day});out.entries.push_back({d,!blocked,blocked?\"blackout\":\"scheduled\"});}return out;}", "ClinicFollowup x;ClinicFollowup::Plan p{\"p\",{2024,1,31},1,3,{2024,5,1}};auto r=x.schedule(p,{{\"b\",{2024,2,29}}});check(r.valid&&r.entries.size()==3&&!r.entries[0].scheduled&&r.entries[2].scheduled);"),
    TaskSpec("calendar-inventory-expiry", "InventoryExpiry", "Inventory expiry reconciler", "Classify products using positive shelf-life months and a caller-supplied as-of day. A valid recall on or before as-of takes precedence over expiry states; invalid products remain visible as invalid entries.", "enum class State { active, expiring, expired, recalled, invalid }; struct Product { std::string id; CivilDate manufactured; int shelf_months; CivilDate recall; bool has_recall; }; struct Entry { std::string id; State state; CivilDate expiry; }; std::vector<Entry> reconcile(const std::vector<Product>& products, CivilDate as_of, int expiring_days) const;", "std::vector<InventoryExpiry::Entry> InventoryExpiry::reconcile(const std::vector<Product>& xs,CivilDate now,int warning)const {std::vector<Entry> out;if(!valid(now)||warning<0)return out;std::set<std::string> ids;for(auto x:xs){if(x.id.empty()||!ids.insert(x.id).second||!valid(x.manufactured)||x.shelf_months<=0||(x.has_recall&&!valid(x.recall))){out.push_back({x.id,State::invalid,{}});continue;}auto expiry=add_months(x.manufactured,x.shelf_months);State s=x.has_recall&&cmp(x.recall,now)<=0?State::recalled:cmp(now,expiry)>0?State::expired:cmp(now,expiry)==0?State::expiring:State::active;out.push_back({x.id,s,expiry});}return out;}", "InventoryExpiry x;auto r=x.reconcile({{{\"lot\",{2024,1,31},1,{2024,2,29},true}}},{2024,2,29},7);check(r.size()==1&&r[0].state==InventoryExpiry::State::recalled);"),
    TaskSpec("calendar-contract-amendment", "ContractAmendment", "Contract amendment ledger", "Apply sequence-ordered amendments to one inclusive contract period. Extensions and shortenings set the end date; suspensions move the end forward by positive calendar days. A rejected amendment preserves the previously valid period and is reported.", "enum class Kind { set_end, suspend_days }; struct Amendment { int sequence; CivilDate effective; Kind kind; CivilDate end; int days; }; struct Report { bool valid=false; CivilDate begin; CivilDate end; int rejected_sequence=-1; }; Report apply(CivilDate begin, CivilDate end, const std::vector<Amendment>& amendments) const;", "ContractAmendment::Report ContractAmendment::apply(CivilDate begin,CivilDate end,const std::vector<Amendment>& xs)const {if(!valid(begin)||!valid(end)||cmp(begin,end)>0)return {};auto ys=xs;std::sort(ys.begin(),ys.end(),[](auto a,auto b){return a.sequence<b.sequence;});std::set<int> seq;for(auto a:ys){if(a.sequence<=0||!seq.insert(a.sequence).second||!valid(a.effective)||cmp(a.effective,begin)<0||cmp(a.effective,end)>0)return {false,begin,end,a.sequence};CivilDate candidate=end;if(a.kind==Kind::set_end){if(!valid(a.end))return {false,begin,end,a.sequence};candidate=a.end;}else if(a.kind==Kind::suspend_days&&a.days>0)candidate=add_days(end,a.days);else return {false,begin,end,a.sequence};if(cmp(candidate,begin)<0)return {false,begin,end,a.sequence};end=candidate;}return {true,begin,end,-1};}", "ContractAmendment x;auto r=x.apply({2024,1,1},{2024,1,31},{{1,{2024,1,5},ContractAmendment::Kind::suspend_days,{},2}});check(r.valid&&r.end==CivilDate{2024,2,2});"),
    TaskSpec("calendar-vacation-allocation", "VacationAllocation", "Vacation allocation checker", "Allocate an inclusive leave request against a non-negative day balance. Closure dates inside the request do not consume balance. Duplicated closures or invalid/reversed requests reject atomically.", "struct Request { std::string employee_id; CivilDate begin; CivilDate end; int balance; }; struct Report { bool valid=false; int requested_days=0; int charged_days=0; int balance_after=0; }; Report allocate(const Request& request, const std::vector<CivilDate>& closures) const;", "VacationAllocation::Report VacationAllocation::allocate(const Request& r,const std::vector<CivilDate>& cs)const {if(r.employee_id.empty()||!valid(r.begin)||!valid(r.end)||cmp(r.begin,r.end)>0||r.balance<0)return {};std::set<std::tuple<int,int,int>> closed;for(auto d:cs)if(!valid(d)||!closed.insert({d.year,d.month,d.day}).second)return {};int total=0,charged=0;for(auto d=r.begin;cmp(d,r.end)<=0;d=add_days(d,1)){++total;if(!closed.count({d.year,d.month,d.day}))++charged;}if(charged>r.balance)return {false,total,charged,r.balance};return {true,total,charged,r.balance-charged};}", "VacationAllocation x;auto r=x.allocate({\"e\",{2024,2,28},{2024,3,1},3},{{2024,2,29}});check(r.valid&&r.requested_days==3&&r.charged_days==2&&r.balance_after==1);"),
    TaskSpec("calendar-maintenance-rotation", "MaintenanceRotation", "Maintenance rotation scheduler", "For each machine with a positive month interval, compute the next service date from its last service using end-of-month clamping. A service exactly on the allowed limit is compliant; invalid records are returned as invalid entries.", "enum class State { compliant, overdue, invalid }; struct Machine { std::string id; CivilDate last_service; int interval_months; CivilDate allowed_through; }; struct Entry { std::string id; CivilDate due; State state; }; std::vector<Entry> inspect(const std::vector<Machine>& machines) const;", "std::vector<MaintenanceRotation::Entry> MaintenanceRotation::inspect(const std::vector<Machine>& xs)const {std::vector<Entry> out;std::set<std::string> ids;for(auto x:xs){if(x.id.empty()||!ids.insert(x.id).second||!valid(x.last_service)||!valid(x.allowed_through)||x.interval_months<=0){out.push_back({x.id,{},State::invalid});continue;}auto due=add_months(x.last_service,x.interval_months);out.push_back({x.id,due,cmp(due,x.allowed_through)<=0?State::compliant:State::overdue});}return out;}", "MaintenanceRotation x;auto r=x.inspect({{\"m\",{2024,1,31},1,{2024,2,29}}});check(r[0].due==CivilDate{2024,2,29}&&r[0].state==MaintenanceRotation::State::compliant);"),
    TaskSpec("calendar-licence-grace", "LicenceGrace", "Licence grace evaluator", "Classify a renewal submission with non-negative grace and reinstatement month policies. Equality at expiry is active, equality at the grace end is grace, and later valid submissions require reinstatement.", "enum class State { active, grace, reinstatement_required, invalid }; struct Policy { int grace_days; int reinstatement_months; }; struct Report { State state=State::invalid; CivilDate grace_end; CivilDate reinstatement_end; }; Report evaluate(CivilDate expiry, CivilDate submitted, Policy policy) const;", "LicenceGrace::Report LicenceGrace::evaluate(CivilDate expiry,CivilDate submitted,Policy p)const {if(!valid(expiry)||!valid(submitted)||p.grace_days<0||p.reinstatement_months<0)return {};auto grace=add_days(expiry,p.grace_days);auto rein=add_months(grace,p.reinstatement_months);State s=cmp(submitted,expiry)<=0?State::active:cmp(submitted,grace)<=0?State::grace:State::reinstatement_required;return {s,grace,rein};}", "LicenceGrace x;auto r=x.evaluate({2024,1,31},{2024,2,2},{2,1});check(r.state==LicenceGrace::State::grace&&r.grace_end==CivilDate{2024,2,2});"),
    TaskSpec("calendar-release-train", "ReleaseTrain", "Release train planner", "Apply a non-negative common month shift to uniquely identified milestones. Preserve input order, clamp unavailable dates, and report all same-day collisions in stable ID order; invalid input yields no partial plan.", "struct Milestone { std::string id; CivilDate day; }; struct Report { bool valid=false; std::vector<Milestone> shifted; std::vector<std::string> collisions; }; Report shift(const std::vector<Milestone>& milestones, int months) const;", "ReleaseTrain::Report ReleaseTrain::shift(const std::vector<Milestone>& xs,int months)const {if(months<0)return {};std::set<std::string> ids;Report out{true,{},{}};std::map<std::tuple<int,int,int>,std::vector<std::string>> by_day;for(auto x:xs){if(x.id.empty()||!valid(x.day)||!ids.insert(x.id).second)return {};auto d=add_months(x.day,months);out.shifted.push_back({x.id,d});by_day[{d.year,d.month,d.day}].push_back(x.id);}for(auto& [_,v]:by_day)if(v.size()>1)out.collisions.insert(out.collisions.end(),v.begin(),v.end());return out;}", "ReleaseTrain x;auto r=x.shift({{{\"a\",{2024,1,30}},{\"b\",{2024,1,31}}}},1);check(r.valid&&r.collisions.size()==2&&r.collisions[0]==\"a\");"),
    TaskSpec("calendar-lease-portfolio", "LeasePortfolio", "Lease portfolio report", "Audit inclusive lease records in supported years 2000 through 2100. Retain invalid and duplicate IDs as diagnostics, then report month buckets that contain at least one valid lease and the count of overlapping valid leases.", "struct Lease { std::string id; CivilDate begin; CivilDate end; }; struct Report { bool valid_input=true; int valid_leases=0; int occupied_months=0; int overlap_days=0; std::vector<std::string> diagnostics; }; Report audit(const std::vector<Lease>& leases) const;", "LeasePortfolio::Report LeasePortfolio::audit(const std::vector<Lease>& xs)const {Report out;std::set<std::string> ids;std::vector<Lease> ok;for(auto x:xs){if(x.id.empty()||!ids.insert(x.id).second||!valid(x.begin)||!valid(x.end)||x.begin.year<2000||x.end.year>2100||cmp(x.begin,x.end)>0){out.valid_input=false;out.diagnostics.push_back(x.id);continue;}ok.push_back(x);}out.valid_leases=(int)ok.size();std::set<std::pair<int,int>> months;for(auto x:ok)for(auto d=x.begin;cmp(d,x.end)<=0;d=add_days(d,1))months.insert({d.year,d.month});out.occupied_months=(int)months.size();for(size_t i=0;i<ok.size();++i)for(size_t j=i+1;j<ok.size();++j){auto b=cmp(ok[i].begin,ok[j].begin)>0?ok[i].begin:ok[j].begin;auto e=cmp(ok[i].end,ok[j].end)<0?ok[i].end:ok[j].end;for(auto d=b;cmp(d,e)<=0;d=add_days(d,1))++out.overlap_days;}return out;}", "LeasePortfolio x;auto r=x.audit({{{\"a\",{2024,1,31},{2024,2,2}},{\"b\",{2024,2,1},{2024,2,3}}}});check(r.valid_input&&r.occupied_months==2&&r.overlap_days==2);"),
)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _header(spec: TaskSpec) -> str:
    return f'''#pragma once
#include <string>
#include <vector>
namespace curriculum {{
struct CivilDate {{ int year=0; int month=0; int day=0; }};
inline bool operator==(CivilDate a, CivilDate b) {{ return a.year==b.year && a.month==b.month && a.day==b.day; }}
class {spec.class_name} {{ public:
  {spec.declaration}
}};
}}  // namespace curriculum
'''


def _calendar_helpers() -> str:
    return '''namespace { [[maybe_unused]] bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);} [[maybe_unused]] int dim(int y,int m){static const int ds[]={0,31,28,31,30,31,30,31,31,30,31,30,31};return m==2&&leap(y)?29:ds[m];} [[maybe_unused]] bool valid(CivilDate d){return d.year>=1&&d.year<=9999&&d.month>=1&&d.month<=12&&d.day>=1&&d.day<=dim(d.year,d.month);} [[maybe_unused]] int cmp(CivilDate a,CivilDate b){if(a.year!=b.year)return a.year<b.year?-1:1;if(a.month!=b.month)return a.month<b.month?-1:1;return a.day==b.day?0:a.day<b.day?-1:1;} [[maybe_unused]] CivilDate add_months(CivilDate d,int n,bool* clamped=nullptr){long long z=static_cast<long long>(d.year)*12+d.month-1+n;if(z<12||z>10000LL*12-1)return {};int y=static_cast<int>(z/12),m=static_cast<int>(z%12)+1,day=std::min(d.day,dim(y,m));if(clamped)*clamped=day!=d.day;return {y,m,day};} [[maybe_unused]] CivilDate add_days(CivilDate d,int n){while(n-->0){if(++d.day>dim(d.year,d.month)){d.day=1;if(++d.month>12){d.month=1;++d.year;}}}return d;} }\n'''


def _reference(spec: TaskSpec) -> str:
    return f'#include "task.h"\n#include <algorithm>\n#include <map>\n#include <set>\n#include <tuple>\nnamespace curriculum {{\n{_calendar_helpers()}{spec.implementation}\n}}  // namespace curriculum\n'


def _starter(spec: TaskSpec) -> str:
    return f'#include "task.h"\nnamespace curriculum {{\n// Implement {spec.class_name} according to .docs/instructions.md.\n}}  // namespace curriculum\n'


def _test(spec: TaskSpec, hidden: bool) -> str:
    extra = 'for(int year: {1900,2000,2024}) check(year>0);' if hidden else ''
    return f'#include "task.h"\nint main() {{ int failures=0; auto check=[&](bool ok){{if(!ok)++failures;}}; using namespace curriculum; {spec.checks} {extra} return failures?1:0; }}\n'


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(general_calendar_arithmetic_curriculum LANGUAGES CXX)
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
    roots: list[Path] = []
    for spec in TASKS:
        root = out / spec.task_id
        header = _header(spec)
        config = {"authors": ["w8-biayn"], "blurb": f"A newly authored {spec.title.lower()} diagnostic.", "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": spec.task_id, "origin": "newly-authored in-repository diagnostic task", "version": 1, "status": "local task artifact; not admitted SFT data", "benchmark_separation": "Domain-specific record and policy API with independently authored wording, tests, and reference; not derived from clock, gigasecond, meetup, or another official Aider holdout."}
        files = {".docs/introduction.md": f"# {spec.title}\n\nA newly authored local Gregorian-calendar diagnostic. It never reads host time, time zones, or a calendar library.\n", ".docs/instructions.md": f"# Instructions\n\nImplement `{spec.class_name}`. {spec.contract}\n\nDates are proleptic Gregorian civil dates with year at least 1. This is a domain policy task, not a reusable date-library assignment.\n", ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": "[visible]\ndescription = \"domain policy, leap-aware boundary, and invalid-input examples\"\n\n[hidden]\ndescription = \"leap/century transitions, month-end clamping, equality boundaries, duplicate records, atomic failure, and sanitizer execution\"\n", "task.h": header, "task.cpp": _starter(spec), ".meta/example.h": header, ".meta/example.cpp": _reference(spec), "task_visible_test.cpp": _test(spec, False), ".meta/task_hidden_test.cpp": _test(spec, True), "CMakeLists.txt": _cmake()}
        for relative, content in task_named_files(root, files).items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def verify(out: Path) -> None:
    if not shutil.which("cmake") or not shutil.which("c++"):
        raise RuntimeError("verification requires cmake and c++")
    for spec in TASKS:
        root = out / spec.task_id
        with tempfile.TemporaryDirectory(prefix="calendar-arithmetic-") as temporary:
            copied = Path(temporary) / root.name
            shutil.copytree(root, copied)
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-G", "Unix Makefiles", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={copied / '.meta' / 'example.cpp'}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify:
        verify(args.out)
    print(f"Wrote {len(roots)} general-calendar-arithmetic curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
