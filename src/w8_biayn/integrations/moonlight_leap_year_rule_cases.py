"""Clean-room leap-year-rule replacement cases for local family verification."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeapCase:
    task_id: str
    legacy_id: str | None
    title: str
    objective: str
    public_api: str
    mechanism: str
    instructions: str
    header: str
    starter: str
    reference: str
    visible_test: str
    hidden_test: str
    hard_rule_test: str
    negative_source: str
    negative_reason: str


CASES = (
    LeapCase(
        "leap-capacity-calendar",
        "leap-february-inventory",
        "February Capacity Calendar",
        "Audit sparse February capacity declarations with fixed day-indexed occupancy.",
        "CapacityReport audit_capacity(int year, int per_day_capacity, const std::vector<DayLoad>& loads)",
        "bounded day-indexed occupancy and seen arrays",
        """# Instructions

Implement `audit_capacity`. Gregorian leap years are divisible by 4, except centuries unless divisible by 400. Years must be in 1..9999 and capacity must be nonnegative. Each supplied day must be unique, inside that year's February, and have a load from zero through capacity. Reject the first invalid record without counting it. On success report the month's day count, missing days, and total load.
""",
        r'''#pragma once
#include <vector>
namespace curriculum {
enum class CapacityStatus { ok, invalid_year, invalid_capacity, invalid_day, duplicate_day, invalid_load };
struct DayLoad { int day; int load; };
struct CapacityReport { CapacityStatus status; int month_days; int missing_days; int total_load; int first_problem_day; };
CapacityReport audit_capacity(int year, int per_day_capacity, const std::vector<DayLoad>& loads);
}
''',
        r'''#include "task.h"
namespace curriculum {
CapacityReport audit_capacity(int, int, const std::vector<DayLoad>&) { return {CapacityStatus::invalid_year, 0, 0, 0, 0}; }
}
''',
        r'''#include "task.h"
#include <array>
namespace curriculum {
namespace { bool leap(int y) { return y % 4 == 0 && (y % 100 != 0 || y % 400 == 0); } }
CapacityReport audit_capacity(int year, int capacity, const std::vector<DayLoad>& loads) {
  if (year < 1 || year > 9999) return {CapacityStatus::invalid_year, 0, 0, 0, 0};
  const int month_days = leap(year) ? 29 : 28;
  if (capacity < 0) return {CapacityStatus::invalid_capacity, month_days, month_days, 0, 0};
  std::array<bool, 30> seen{}; std::array<int, 30> occupancy{}; int total = 0;
  for (const DayLoad item : loads) {
    if (item.day < 1 || item.day > month_days) return {CapacityStatus::invalid_day, month_days, month_days, total, item.day};
    if (seen[static_cast<std::size_t>(item.day)]) return {CapacityStatus::duplicate_day, month_days, month_days, total, item.day};
    if (item.load < 0 || item.load > capacity) return {CapacityStatus::invalid_load, month_days, month_days, total, item.day};
    seen[static_cast<std::size_t>(item.day)] = true; occupancy[static_cast<std::size_t>(item.day)] = item.load; total += occupancy[static_cast<std::size_t>(item.day)];
  }
  int present = 0; for (int day = 1; day <= month_days; ++day) present += seen[static_cast<std::size_t>(day)] ? 1 : 0;
  return {CapacityStatus::ok, month_days, month_days - present, total, 0};
}
}
''',
        r'''#include "task.h"
int main() { using namespace curriculum; const auto r = audit_capacity(2024, 7, {{1, 3}, {29, 7}}); return r.status == CapacityStatus::ok && r.month_days == 29 && r.missing_days == 27 && r.total_load == 10 ? 0 : 1; }
''',
        r'''#include "task.h"
int main() { using namespace curriculum; if (audit_capacity(1900, 1, {{29, 0}}).status != CapacityStatus::invalid_day) return 1; if (audit_capacity(2000, 2, {{29, 1}, {29, 1}}).status != CapacityStatus::duplicate_day) return 2; if (audit_capacity(2024, 2, {{28, 3}}).status != CapacityStatus::invalid_load) return 3; return audit_capacity(0, 1, {}).status == CapacityStatus::invalid_year ? 0 : 4; }
''',
        r'''#include "task.h"
int main() { using namespace curriculum; for (int y : {1999, 2000, 2004, 2100}) { const auto r = audit_capacity(y, 0, {}); const int expected = (y % 4 == 0 && (y % 100 != 0 || y % 400 == 0)) ? 29 : 28; if (r.month_days != expected || r.missing_days != expected) return 1; } return 0; }
''',
        r'''#include "task.h"
#include <set>
namespace curriculum { namespace { bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);} } CapacityReport audit_capacity(int y,int cap,const std::vector<DayLoad>& xs){if(y<1||y>9999)return{CapacityStatus::invalid_year,0,0,0,0};const int n=leap(y)?29:28;if(cap<0)return{CapacityStatus::invalid_capacity,n,n,0,0};std::set<int> days;int total=0;for(auto x:xs){if(x.day<1||x.day>n)return{CapacityStatus::invalid_day,n,n,total,x.day};if(x.load<0||x.load>cap)return{CapacityStatus::invalid_load,n,n,total,x.day};days.insert(x.day);total+=x.load;}return{CapacityStatus::ok,n,n-static_cast<int>(days.size()),total,0};} }
''',
        "duplicate day declarations are silently collapsed",
    ),
    LeapCase(
        "leap-benefit-apportionment",
        "leap-payroll-accrual",
        "Leap Benefit Apportionment",
        "Distribute leap-day benefit units by stable largest remainder.",
        "BenefitReport apportion_benefit(int year, int units, const std::vector<BenefitAccount>& accounts)",
        "weighted quotient and largest-remainder ordering",
        """# Instructions

Implement weighted leap-day benefit apportionment. A common year distributes zero units. In a leap year, nonnegative units are divided among active positive-weight accounts. IDs must be nonempty and unique; negative weights are invalid. If units are positive and there is no active weight, reject. Allocate floor shares, then remaining units by larger remainder and finally lexical ID. Return allocations in lexical ID order and conserve the pool exactly.
""",
        r'''#pragma once
#include <string>
#include <vector>
namespace curriculum { enum class BenefitStatus { ok, invalid_year, invalid_units, invalid_account, no_active_weight }; struct BenefitAccount { std::string id; int weight; bool active; }; struct BenefitShare { std::string id; int units; }; struct BenefitReport { BenefitStatus status; int distributed; std::vector<BenefitShare> shares; }; BenefitReport apportion_benefit(int year,int units,const std::vector<BenefitAccount>& accounts); }
''',
        r'''#include "task.h"
namespace curriculum { BenefitReport apportion_benefit(int,int,const std::vector<BenefitAccount>&){return{BenefitStatus::invalid_year,0,{}};} }
''',
        r'''#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum { namespace { bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);} struct Part{std::string id;int units;long long rem;}; }
BenefitReport apportion_benefit(int y,int units,const std::vector<BenefitAccount>& accounts){if(y<1||y>9999)return{BenefitStatus::invalid_year,0,{}};if(units<0)return{BenefitStatus::invalid_units,0,{}};std::set<std::string> ids;long long total_weight=0;for(const auto& a:accounts){if(a.id.empty()||a.weight<0||!ids.insert(a.id).second)return{BenefitStatus::invalid_account,0,{}};if(a.active)total_weight+=a.weight;}const int pool=leap(y)?units:0;if(pool>0&&total_weight==0)return{BenefitStatus::no_active_weight,0,{}};std::vector<Part> parts;int assigned=0;for(const auto& a:accounts)if(a.active&&a.weight>0){const long long scaled=static_cast<long long>(pool)*a.weight;const int share=total_weight?static_cast<int>(scaled/total_weight):0;parts.push_back({a.id,share,total_weight?scaled%total_weight:0});assigned+=share;}std::sort(parts.begin(),parts.end(),[](const Part& a,const Part& b){return a.rem!=b.rem?a.rem>b.rem:a.id<b.id;});for(int i=0;i<pool-assigned;++i)++parts[static_cast<std::size_t>(i)].units;std::sort(parts.begin(),parts.end(),[](const Part&a,const Part&b){return a.id<b.id;});std::vector<BenefitShare> out;for(const auto&p:parts)out.push_back({p.id,p.units});return{BenefitStatus::ok,pool,out};}
}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto r=apportion_benefit(2024,5,{{"a",1,true},{"b",2,true},{"z",4,false}});return r.status==BenefitStatus::ok&&r.distributed==5&&r.shares.size()==2&&r.shares[0].units==2&&r.shares[1].units==3?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;if(apportion_benefit(1900,7,{{"a",1,true}}).distributed!=0)return 1;if(apportion_benefit(2000,1,{{"b",1,true},{"a",1,true}}).shares[0].units!=1)return 2;if(apportion_benefit(2024,1,{{"a",0,false}}).status!=BenefitStatus::no_active_weight)return 3;return apportion_benefit(2024,1,{{"x",1,true},{"x",2,true}}).status==BenefitStatus::invalid_account?0:4;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;for(int units=0;units<17;++units){auto r=apportion_benefit(2400,units,{{"a",2,true},{"b",3,true},{"c",5,true}});int sum=0;for(auto s:r.shares)sum+=s.units;if(sum!=units||r.distributed!=units)return 1;}return 0;}
''',
        r'''#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum { namespace {bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}} BenefitReport apportion_benefit(int y,int units,const std::vector<BenefitAccount>& as){if(y<1||y>9999)return{BenefitStatus::invalid_year,0,{}};if(units<0)return{BenefitStatus::invalid_units,0,{}};std::set<std::string> ids;std::vector<BenefitShare> out;for(auto a:as){if(a.id.empty()||a.weight<0||!ids.insert(a.id).second)return{BenefitStatus::invalid_account,0,{}};if(a.active&&a.weight>0)out.push_back({a.id,0});}const int pool=leap(y)?units:0;if(pool>0&&out.empty())return{BenefitStatus::no_active_weight,0,{}};for(int i=0;i<pool&&!out.empty();++i)++out[static_cast<std::size_t>(i)%out.size()].units;std::sort(out.begin(),out.end(),[](auto&a,auto&b){return a.id<b.id;});return{BenefitStatus::ok,pool,out};} }
''',
        "weighted apportionment is replaced by equal round robin",
    ),
    LeapCase(
        "leap-archive-gap-index", "leap-weather-archive", "February Archive Gap Index", "Maintain a stateful ID and per-day completeness index.", "ArchiveGapIndex constructor, insert, missing_days, count_on, size", "stateful identifier set and fixed day-count index",
        """# Instructions

Implement `ArchiveGapIndex`. Construction accepts a Gregorian year from 1 through 9999. `insert` accepts a nonempty never-before-seen ID and a valid February day; rejection never mutates state. Multiple IDs may share a day. `missing_days` returns every zero-count day in ascending order, `count_on` returns -1 for an invalid day, and `size` counts accepted IDs.
""",
        r'''#pragma once
#include <array>
#include <set>
#include <string>
#include <vector>
namespace curriculum { class ArchiveGapIndex { public: explicit ArchiveGapIndex(int year); bool valid() const; bool insert(const std::string& id,int day); std::vector<int> missing_days() const; int count_on(int day) const; int size() const; private:int days_=0;std::array<int,30> counts_{};std::set<std::string> ids_;}; }
''',
        r'''#include "task.h"
namespace curriculum { ArchiveGapIndex::ArchiveGapIndex(int){} bool ArchiveGapIndex::valid()const{return false;} bool ArchiveGapIndex::insert(const std::string&,int){return false;} std::vector<int> ArchiveGapIndex::missing_days()const{return{};} int ArchiveGapIndex::count_on(int)const{return-1;} int ArchiveGapIndex::size()const{return 0;} }
''',
        r'''#include "task.h"
namespace curriculum { namespace{bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}} ArchiveGapIndex::ArchiveGapIndex(int y){if(y>=1&&y<=9999)days_=leap(y)?29:28;}bool ArchiveGapIndex::valid()const{return days_>0;}bool ArchiveGapIndex::insert(const std::string&id,int day){if(!valid()||id.empty()||day<1||day>days_||ids_.count(id))return false;ids_.insert(id);++counts_[static_cast<std::size_t>(day)];return true;}std::vector<int> ArchiveGapIndex::missing_days()const{std::vector<int> out;for(int d=1;d<=days_;++d)if(counts_[static_cast<std::size_t>(d)]==0)out.push_back(d);return out;}int ArchiveGapIndex::count_on(int d)const{return d>=1&&d<=days_?counts_[static_cast<std::size_t>(d)]:-1;}int ArchiveGapIndex::size()const{return static_cast<int>(ids_.size());} }
''',
        r'''#include "task.h"
int main(){curriculum::ArchiveGapIndex x(2024);return x.valid()&&x.insert("a",29)&&x.insert("b",29)&&x.count_on(29)==2&&x.missing_days().size()==28?0:1;}
''',
        r'''#include "task.h"
int main(){curriculum::ArchiveGapIndex x(1900);if(x.insert("a",29)||!x.insert("a",28)||x.insert("a",27)||x.size()!=1)return 1;curriculum::ArchiveGapIndex bad(0);return !bad.valid()&&bad.count_on(1)==-1?0:2;}
''',
        r'''#include "task.h"
int main(){curriculum::ArchiveGapIndex x(2000);for(int d=1;d<=29;++d)if(!x.insert("id"+std::to_string(d),d))return 1;return x.missing_days().empty()&&x.size()==29?0:2;}
''',
        r'''#include "task.h"
namespace curriculum { namespace{bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}} ArchiveGapIndex::ArchiveGapIndex(int y){if(y>=1&&y<=9999)days_=leap(y)?29:28;}bool ArchiveGapIndex::valid()const{return days_>0;}bool ArchiveGapIndex::insert(const std::string&id,int day){if(!valid()||id.empty()||day<1||day>days_||ids_.count(id))return false;ids_.insert(id);return true;}std::vector<int> ArchiveGapIndex::missing_days()const{return{};}int ArchiveGapIndex::count_on(int d)const{return d>=1&&d<=days_?0:-1;}int ArchiveGapIndex::size()const{return static_cast<int>(ids_.size());} }
''',
        "accepted IDs do not update the per-day index",
    ),
    LeapCase(
        "leap-maintenance-ledger", "leap-facility-booking", "February Maintenance Ledger", "Admit inclusive interval demand with atomic line-sweep capacity checks.", "MaintenanceLedger constructor, admit, load_on, booking_count", "difference-array trial sweep followed by atomic load commit",
        """# Instructions

Implement `MaintenanceLedger`. The constructor validates year 1..9999, nonnegative capacity, and unique valid blackout days. A booking has a nonempty unique ID, inclusive valid start/end, and positive demand. Reject a booking if any covered day is blacked out or would exceed capacity; equality is accepted. Rejection is atomic. `load_on` returns -1 for invalid days.
""",
        r'''#pragma once
#include <array>
#include <set>
#include <string>
#include <vector>
namespace curriculum { struct MaintenanceBooking{std::string id;int first_day;int last_day;int demand;}; class MaintenanceLedger{public:MaintenanceLedger(int year,int capacity,const std::vector<int>& blackout);bool valid()const;bool admit(const MaintenanceBooking&);int load_on(int day)const;int booking_count()const;private:int days_=0,capacity_=0,count_=0;bool valid_=false;std::array<bool,30> blackout_{};std::array<int,30> loads_{};std::set<std::string> ids_;}; }
''',
        r'''#include "task.h"
namespace curriculum { MaintenanceLedger::MaintenanceLedger(int,int,const std::vector<int>&){}bool MaintenanceLedger::valid()const{return false;}bool MaintenanceLedger::admit(const MaintenanceBooking&){return false;}int MaintenanceLedger::load_on(int)const{return-1;}int MaintenanceLedger::booking_count()const{return 0;} }
''',
        r'''#include "task.h"
namespace curriculum { namespace{bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}} MaintenanceLedger::MaintenanceLedger(int y,int cap,const std::vector<int>& blocked):capacity_(cap){if(y<1||y>9999||cap<0)return;days_=leap(y)?29:28;std::set<int> seen;for(int d:blocked)if(d<1||d>days_||!seen.insert(d).second)return;for(int d:blocked)blackout_[static_cast<std::size_t>(d)]=true;valid_=true;}bool MaintenanceLedger::valid()const{return valid_;}bool MaintenanceLedger::admit(const MaintenanceBooking& b){if(!valid_||b.id.empty()||ids_.count(b.id)||b.first_day<1||b.last_day>b.first_day+days_||b.last_day>days_||b.first_day>b.last_day||b.demand<=0)return false;std::array<int,31> delta{};delta[static_cast<std::size_t>(b.first_day)]+=b.demand;delta[static_cast<std::size_t>(b.last_day+1)]-=b.demand;int extra=0;for(int d=1;d<=days_;++d){extra+=delta[static_cast<std::size_t>(d)];if((extra>0&&blackout_[static_cast<std::size_t>(d)])||loads_[static_cast<std::size_t>(d)]+extra>capacity_)return false;}for(int d=b.first_day;d<=b.last_day;++d)loads_[static_cast<std::size_t>(d)]+=b.demand;ids_.insert(b.id);++count_;return true;}int MaintenanceLedger::load_on(int d)const{return valid_&&d>=1&&d<=days_?loads_[static_cast<std::size_t>(d)]:-1;}int MaintenanceLedger::booking_count()const{return count_;} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;MaintenanceLedger l(2024,5,{});return l.valid()&&l.admit({"a",28,29,3})&&l.admit({"b",29,29,2})&&l.load_on(29)==5&&l.booking_count()==2?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;MaintenanceLedger l(1900,3,{2});if(l.admit({"x",1,2,1})||l.booking_count()!=0)return 1;if(!l.admit({"x",1,1,3})||l.admit({"x",3,3,1}))return 2;return !l.admit({"y",1,2,1})&&l.load_on(2)==0?0:3;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;MaintenanceLedger l(2000,4,{});for(int d=1;d<=29;++d)if(!l.admit({"b"+std::to_string(d),d,d,4}))return 1;return l.booking_count()==29&&l.load_on(29)==4?0:2;}
''',
        r'''#include "task.h"
namespace curriculum { namespace{bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}} MaintenanceLedger::MaintenanceLedger(int y,int cap,const std::vector<int>& blocked):capacity_(cap){if(y<1||y>9999||cap<0)return;days_=leap(y)?29:28;for(int d:blocked)if(d>=1&&d<=days_)blackout_[static_cast<std::size_t>(d)]=true;valid_=true;}bool MaintenanceLedger::valid()const{return valid_;}bool MaintenanceLedger::admit(const MaintenanceBooking& b){if(!valid_||b.id.empty()||ids_.count(b.id)||b.first_day<1||b.last_day>days_||b.first_day>b.last_day||b.demand<=0)return false;if(blackout_[static_cast<std::size_t>(b.first_day)]||loads_[static_cast<std::size_t>(b.first_day)]+b.demand>capacity_)return false;for(int d=b.first_day;d<=b.last_day;++d)loads_[static_cast<std::size_t>(d)]+=b.demand;ids_.insert(b.id);++count_;return true;}int MaintenanceLedger::load_on(int d)const{return valid_&&d>=1&&d<=days_?loads_[static_cast<std::size_t>(d)]:-1;}int MaintenanceLedger::booking_count()const{return count_;} }
''',
        "only the first covered day is checked",
    ),
    LeapCase(
        "leap-cadence-wheel", "leap-publication-cycle", "February Cadence Wheel", "Build modular issue slots with bounded cancellation recovery.", "CadencePlan build_cadence_wheel(int year,int anchor,int cadence,int recovery,const std::vector<int>& cancelled)", "modular stepping with cancellation membership and bounded forward recovery",
        """# Instructions

Implement the cadence wheel. Validate year, a valid anchor day, positive cadence, nonnegative recovery, and unique valid cancelled days. Starting at the anchor, step by cadence through February. A cancelled hit scans forward at most `recovery` days for the first uncancelled day not already emitted; otherwise record the original hit as skipped. Return emitted and skipped days in encounter order.
""",
        r'''#pragma once
#include <vector>
namespace curriculum { enum class CadenceStatus{ok,invalid_year,invalid_policy,invalid_cancellation};struct CadencePlan{CadenceStatus status;std::vector<int> issue_days;std::vector<int> skipped_days;};CadencePlan build_cadence_wheel(int year,int anchor,int cadence,int recovery,const std::vector<int>& cancelled); }
''',
        r'''#include "task.h"
namespace curriculum { CadencePlan build_cadence_wheel(int,int,int,int,const std::vector<int>&){return{CadenceStatus::invalid_year,{},{}};} }
''',
        r'''#include "task.h"
#include <set>
namespace curriculum { namespace{bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}} CadencePlan build_cadence_wheel(int y,int anchor,int cadence,int recovery,const std::vector<int>& cancelled){if(y<1||y>9999)return{CadenceStatus::invalid_year,{},{}};const int n=leap(y)?29:28;if(anchor<1||anchor>n||cadence<=0||recovery<0)return{CadenceStatus::invalid_policy,{},{}};std::set<int> stops;for(int d:cancelled)if(d<1||d>n||!stops.insert(d).second)return{CadenceStatus::invalid_cancellation,{},{}};CadencePlan out{CadenceStatus::ok,{},{}};std::set<int> used;for(int hit=anchor;hit<=n;hit+=cadence){int chosen=hit;while(chosen<=n&&(stops.count(chosen)||used.count(chosen))&&chosen-hit<recovery)++chosen;if(chosen<=n&&!stops.count(chosen)&&!used.count(chosen)){out.issue_days.push_back(chosen);used.insert(chosen);}else out.skipped_days.push_back(hit);}return out;} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto p=build_cadence_wheel(2024,1,14,2,{15,16});return p.status==CadenceStatus::ok&&p.issue_days==std::vector<int>({1,17,29})&&p.skipped_days.empty()?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;if(build_cadence_wheel(1900,29,1,0,{}).status!=CadenceStatus::invalid_policy)return 1;if(build_cadence_wheel(2000,29,1,0,{}).issue_days!=std::vector<int>({29}))return 2;return build_cadence_wheel(2024,1,3,1,{4,4}).status==CadenceStatus::invalid_cancellation?0:3;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto p=build_cadence_wheel(2024,1,1,0,{});if(p.issue_days.size()!=29)return 1;for(int i=0;i<29;++i)if(p.issue_days[static_cast<std::size_t>(i)]!=i+1)return 2;return 0;}
''',
        r'''#include "task.h"
#include <set>
namespace curriculum { namespace{bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}} CadencePlan build_cadence_wheel(int y,int anchor,int cadence,int recovery,const std::vector<int>& cancelled){if(y<1||y>9999)return{CadenceStatus::invalid_year,{},{}};const int n=leap(y)?29:28;if(anchor<1||anchor>n||cadence<=0||recovery<0)return{CadenceStatus::invalid_policy,{},{}};std::set<int> stops(cancelled.begin(),cancelled.end());CadencePlan out{CadenceStatus::ok,{},{}};for(int hit=anchor;hit<=n;hit+=cadence)if(stops.count(hit))out.skipped_days.push_back(hit);else out.issue_days.push_back(hit);return out;} }
''',
        "cancelled cadence hits are filtered without recovery",
    ),
    LeapCase(
        "leap-coverage-segments", None, "February Coverage Segments", "Union inclusive coverage intervals and report maximal uncovered gaps.", "CoverageReport uncovered_segments(int year,const std::vector<CoverageSegment>& segments)", "sorted interval union followed by complement construction",
        """# Instructions

Implement February coverage union. Validate year 1..9999 and every inclusive segment inside February with `first <= last`. Sort by start then end, merge overlapping or adjacent segments, and return the maximal uncovered inclusive gaps in ascending order. Empty input leaves the whole month uncovered. Any invalid segment rejects the entire input.
""",
        r'''#pragma once
#include <vector>
namespace curriculum { enum class CoverageStatus{ok,invalid_year,invalid_segment};struct CoverageSegment{int first;int last;};inline bool operator==(CoverageSegment a,CoverageSegment b){return a.first==b.first&&a.last==b.last;}struct CoverageReport{CoverageStatus status;std::vector<CoverageSegment> gaps;int covered_days;};CoverageReport uncovered_segments(int year,const std::vector<CoverageSegment>& segments); }
''',
        r'''#include "task.h"
namespace curriculum { CoverageReport uncovered_segments(int,const std::vector<CoverageSegment>&){return{CoverageStatus::invalid_year,{},0};} }
''',
        r'''#include "task.h"
#include <algorithm>
namespace curriculum { namespace{bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}} CoverageReport uncovered_segments(int y,const std::vector<CoverageSegment>& input){if(y<1||y>9999)return{CoverageStatus::invalid_year,{},0};const int n=leap(y)?29:28;auto xs=input;for(auto s:xs)if(s.first<1||s.last>n||s.first>s.last)return{CoverageStatus::invalid_segment,{},0};std::sort(xs.begin(),xs.end(),[](auto a,auto b){return a.first!=b.first?a.first<b.first:a.last<b.last;});std::vector<CoverageSegment> merged;for(auto s:xs){if(merged.empty()||s.first>merged.back().last+1)merged.push_back(s);else merged.back().last=std::max(merged.back().last,s.last);}std::vector<CoverageSegment> gaps;int cursor=1,covered=0;for(auto s:merged){if(cursor<s.first)gaps.push_back({cursor,s.first-1});covered+=s.last-s.first+1;cursor=s.last+1;}if(cursor<=n)gaps.push_back({cursor,n});return{CoverageStatus::ok,gaps,covered};} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto r=uncovered_segments(2024,{{1,3},{3,5},{8,9}});return r.status==CoverageStatus::ok&&r.covered_days==7&&r.gaps==std::vector<CoverageSegment>({{6,7},{10,29}})?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto e=uncovered_segments(1900,{});if(e.gaps.size()!=1||e.gaps[0].last!=28)return 1;auto a=uncovered_segments(2000,{{1,28},{29,29}});if(!a.gaps.empty()||a.covered_days!=29)return 2;return uncovered_segments(2024,{{0,1}}).status==CoverageStatus::invalid_segment?0:3;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;for(int split=1;split<29;++split){auto r=uncovered_segments(2024,{{split+1,29}});if(r.gaps.size()!=1||r.gaps[0].first!=1||r.gaps[0].last!=split)return 1;}return 0;}
''',
        r'''#include "task.h"
#include <algorithm>
namespace curriculum { namespace{bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}} CoverageReport uncovered_segments(int y,const std::vector<CoverageSegment>& input){if(y<1||y>9999)return{CoverageStatus::invalid_year,{},0};const int n=leap(y)?29:28;auto xs=input;for(auto s:xs)if(s.first<1||s.last>n||s.first>s.last)return{CoverageStatus::invalid_segment,{},0};std::sort(xs.begin(),xs.end(),[](auto a,auto b){return a.first<b.first;});std::vector<CoverageSegment> gaps;int cursor=1,covered=0;for(auto s:xs){if(cursor<s.first)gaps.push_back({cursor,s.first-1});covered+=s.last-s.first+1;cursor=s.last+1;}if(cursor<=n)gaps.push_back({cursor,n});return{CoverageStatus::ok,gaps,covered};} }
''',
        "overlapping and adjacent segments are not merged",
    ),
    LeapCase(
        "leap-shift-matching", None, "Leap Shift Matching", "Find a maximum deterministic worker/day matching.", "ShiftMatching match_leap_shifts(int year,const std::vector<WorkerAvailability>& workers)", "bipartite augmenting-path rematching",
        """# Instructions

Implement maximum bipartite matching from workers to February days. Worker IDs must be unique and nonempty; each availability list must contain unique valid days for the supplied Gregorian year. Use at most one day per worker and one worker per day. Return a maximum-cardinality assignment sorted by worker ID. If several maximum matchings exist, process workers by lexical ID and each adjacency list in ascending day order.
""",
        r'''#pragma once
#include <string>
#include <vector>
namespace curriculum { enum class MatchStatus{ok,invalid_year,invalid_worker,invalid_day};struct WorkerAvailability{std::string id;std::vector<int> days;};struct ShiftAssignment{std::string id;int day;};struct ShiftMatching{MatchStatus status;std::vector<ShiftAssignment> assignments;};ShiftMatching match_leap_shifts(int year,const std::vector<WorkerAvailability>& workers); }
''',
        r'''#include "task.h"
namespace curriculum { ShiftMatching match_leap_shifts(int,const std::vector<WorkerAvailability>&){return{MatchStatus::invalid_year,{}};} }
''',
        r'''#include "task.h"
#include <algorithm>
#include <functional>
#include <set>
namespace curriculum { namespace{bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}} ShiftMatching match_leap_shifts(int y,const std::vector<WorkerAvailability>& input){if(y<1||y>9999)return{MatchStatus::invalid_year,{}};const int n=leap(y)?29:28;auto ws=input;std::sort(ws.begin(),ws.end(),[](const auto&a,const auto&b){return a.id<b.id;});std::set<std::string> ids;for(auto&w:ws){if(w.id.empty()||!ids.insert(w.id).second)return{MatchStatus::invalid_worker,{}};std::sort(w.days.begin(),w.days.end());if(std::adjacent_find(w.days.begin(),w.days.end())!=w.days.end())return{MatchStatus::invalid_day,{}};for(int d:w.days)if(d<1||d>n)return{MatchStatus::invalid_day,{}};}std::vector<int> owner(static_cast<std::size_t>(n+1),-1);std::function<bool(int,std::vector<bool>&)> augment=[&](int i,std::vector<bool>&seen){for(int d:ws[static_cast<std::size_t>(i)].days){if(seen[static_cast<std::size_t>(d)])continue;seen[static_cast<std::size_t>(d)]=true;if(owner[static_cast<std::size_t>(d)]<0||augment(owner[static_cast<std::size_t>(d)],seen)){owner[static_cast<std::size_t>(d)]=i;return true;}}return false;};for(int i=0;i<static_cast<int>(ws.size());++i){std::vector<bool> seen(static_cast<std::size_t>(n+1));augment(i,seen);}std::vector<ShiftAssignment> out;for(int d=1;d<=n;++d)if(owner[static_cast<std::size_t>(d)]>=0)out.push_back({ws[static_cast<std::size_t>(owner[static_cast<std::size_t>(d)])].id,d});std::sort(out.begin(),out.end(),[](auto&a,auto&b){return a.id<b.id;});return{MatchStatus::ok,out};} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto r=match_leap_shifts(2024,{{"a",{1,2}},{"b",{1}},{"c",{29}}});return r.status==MatchStatus::ok&&r.assignments.size()==3&&r.assignments[0].day==2&&r.assignments[1].day==1&&r.assignments[2].day==29?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;if(match_leap_shifts(1900,{{"a",{29}}}).status!=MatchStatus::invalid_day)return 1;if(match_leap_shifts(2000,{{"a",{29}}}).assignments.size()!=1)return 2;return match_leap_shifts(2024,{{"x",{1}},{"x",{2}}}).status==MatchStatus::invalid_worker?0:3;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto r=match_leap_shifts(2024,{{"a",{1,2}},{"b",{1}},{"c",{2,3}},{"d",{3,4}}});std::vector<bool> days(30);for(auto a:r.assignments){if(days[static_cast<std::size_t>(a.day)])return 1;days[static_cast<std::size_t>(a.day)]=true;}return r.assignments.size()==4?0:2;}
''',
        r'''#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum { namespace{bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}} ShiftMatching match_leap_shifts(int y,const std::vector<WorkerAvailability>& input){if(y<1||y>9999)return{MatchStatus::invalid_year,{}};const int n=leap(y)?29:28;auto ws=input;std::sort(ws.begin(),ws.end(),[](const auto&a,const auto&b){return a.id<b.id;});std::set<std::string> ids;std::set<int> used;std::vector<ShiftAssignment> out;for(auto w:ws){if(w.id.empty()||!ids.insert(w.id).second)return{MatchStatus::invalid_worker,{}};std::sort(w.days.begin(),w.days.end());for(int d:w.days)if(d<1||d>n)return{MatchStatus::invalid_day,{}};for(int d:w.days)if(!used.count(d)){used.insert(d);out.push_back({w.id,d});break;}}return{MatchStatus::ok,out};} }
''',
        "greedy first-fit cannot rematch an earlier worker",
    ),
    LeapCase(
        "leap-policy-replay", None, "Leap Policy Replay", "Replay monotonic policy events through a terminal finite-state machine.", "LeapPolicyReplay constructor, apply, allows_day, state, last_sequence", "explicit monotonic-sequence finite-state transition table",
        """# Instructions

Implement a sequence-numbered policy replay. Events have strictly increasing nonnegative sequence numbers and actions `enable`, `disable`, or `freeze`. Enabled/disabled may toggle; `freeze` enters a terminal frozen state that rejects later events. Rejected events do not mutate sequence or state. `allows_day` rejects days outside February and permits day 29 only for a leap year while enabled; days 1..28 are allowed unless frozen.
""",
        r'''#pragma once
namespace curriculum { enum class PolicyAction{enable,disable,freeze};enum class PolicyState{enabled,disabled,frozen};struct PolicyEvent{int sequence;PolicyAction action;};class LeapPolicyReplay{public:explicit LeapPolicyReplay(int year);bool valid()const;bool apply(PolicyEvent);bool allows_day(int day)const;PolicyState state()const;int last_sequence()const;private:int days_=0,last_=-1;PolicyState state_=PolicyState::disabled;}; }
''',
        r'''#include "task.h"
namespace curriculum { LeapPolicyReplay::LeapPolicyReplay(int){}bool LeapPolicyReplay::valid()const{return false;}bool LeapPolicyReplay::apply(PolicyEvent){return false;}bool LeapPolicyReplay::allows_day(int)const{return false;}PolicyState LeapPolicyReplay::state()const{return state_;}int LeapPolicyReplay::last_sequence()const{return last_;} }
''',
        r'''#include "task.h"
namespace curriculum { namespace{bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}} LeapPolicyReplay::LeapPolicyReplay(int y){if(y>=1&&y<=9999)days_=leap(y)?29:28;}bool LeapPolicyReplay::valid()const{return days_>0;}bool LeapPolicyReplay::apply(PolicyEvent e){if(!valid()||e.sequence<0||e.sequence<=last_||state_==PolicyState::frozen)return false;switch(e.action){case PolicyAction::enable:state_=PolicyState::enabled;break;case PolicyAction::disable:state_=PolicyState::disabled;break;case PolicyAction::freeze:state_=PolicyState::frozen;break;}last_=e.sequence;return true;}bool LeapPolicyReplay::allows_day(int d)const{if(!valid()||d<1||d>days_||state_==PolicyState::frozen)return false;return d<=28||state_==PolicyState::enabled;}PolicyState LeapPolicyReplay::state()const{return state_;}int LeapPolicyReplay::last_sequence()const{return last_;} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;LeapPolicyReplay p(2024);return p.apply({1,PolicyAction::enable})&&p.allows_day(29)&&p.apply({2,PolicyAction::disable})&&!p.allows_day(29)&&p.last_sequence()==2?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;LeapPolicyReplay p(1900);if(!p.apply({1,PolicyAction::enable})||p.allows_day(29))return 1;if(!p.apply({2,PolicyAction::freeze})||p.apply({3,PolicyAction::enable})||p.last_sequence()!=2)return 2;LeapPolicyReplay q(2000);return q.apply({0,PolicyAction::enable})&&q.allows_day(29)&&!q.apply({0,PolicyAction::disable})?0:3;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;LeapPolicyReplay p(2024);PolicyEvent trace[]={{1,PolicyAction::enable},{4,PolicyAction::disable},{7,PolicyAction::enable},{9,PolicyAction::freeze}};for(auto e:trace)if(!p.apply(e))return 1;return p.state()==PolicyState::frozen&&!p.allows_day(1)&&!p.apply({10,PolicyAction::disable})?0:2;}
''',
        r'''#include "task.h"
namespace curriculum { namespace{bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}} LeapPolicyReplay::LeapPolicyReplay(int y){if(y>=1&&y<=9999)days_=leap(y)?29:28;}bool LeapPolicyReplay::valid()const{return days_>0;}bool LeapPolicyReplay::apply(PolicyEvent e){if(!valid()||e.sequence<0||e.sequence<=last_)return false;if(e.action==PolicyAction::enable)state_=PolicyState::enabled;else if(e.action==PolicyAction::disable)state_=PolicyState::disabled;else state_=PolicyState::frozen;last_=e.sequence;return true;}bool LeapPolicyReplay::allows_day(int d)const{return valid()&&d>=1&&d<=days_&&(d<=28||state_==PolicyState::enabled);}PolicyState LeapPolicyReplay::state()const{return state_;}int LeapPolicyReplay::last_sequence()const{return last_;} }
''',
        "frozen state accepts later events and is not terminal",
    ),
)
