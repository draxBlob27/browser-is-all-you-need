"""Clean-room v2 cases for the duration-formatting remediation family."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DurationCase:
    legacy_id: str
    task_id: str
    title: str
    objective: str
    instructions: str
    public_api: str
    algorithm_profile: str
    header: str
    starter: str
    reference: str
    visible_test: str
    hidden_test: str
    negative_old: str
    negative_new: str
    negative_reason: str


CASES = (
    DurationCase(
        "duration-parking-receipt", "parking-block-receipt", "Parking block receipt",
        "Compute chargeable parking blocks and a canonical receipt from a visit and tariff.",
        """# Instructions

Implement `duration_formatting::ParkingBlockReceipt::make`. Inputs are caller-supplied elapsed minutes and a tariff. Reject negative minutes or tariff fields, a non-positive block size, and any result that exceeds `int`. A visit at or below the free allowance has zero billed blocks and charge. Otherwise round the excess upward to complete blocks, then multiply by the charge per block. Return the original minutes, billed blocks, charge, and exactly `free: <m> min` or `billed: <b> blocks, <u> units`. Do not read a clock or use files, networking, threads, or randomness.
""",
        "ParkingTariff record -> checked ceiling blocks -> ParkingReceipt",
        "checked-ceiling-then-multiply",
        r'''#ifndef TASK_H
#define TASK_H
#include <string>
namespace duration_formatting {
struct ParkingTariff { int free_minutes; int block_minutes; int units_per_block; };
struct ParkingReceipt { bool valid; int parked_minutes; int billed_blocks; int charge_units; std::string text; };
class ParkingBlockReceipt { public: ParkingReceipt make(int parked_minutes, const ParkingTariff& tariff) const; };
}
#endif
''',
        r'''#include "task.h"
namespace duration_formatting { ParkingReceipt ParkingBlockReceipt::make(int, const ParkingTariff&) const { return {false,0,0,0,"invalid"}; } }
''',
        r'''#include "task.h"
#include <climits>
namespace duration_formatting {
ParkingReceipt ParkingBlockReceipt::make(int minutes,const ParkingTariff& t)const{
 if(minutes<0||t.free_minutes<0||t.block_minutes<=0||t.units_per_block<0)return {false,0,0,0,"invalid"};
 if(minutes<=t.free_minutes)return {true,minutes,0,0,"free: "+std::to_string(minutes)+" min"};
 const long long excess=static_cast<long long>(minutes)-t.free_minutes;
 const long long blocks=(excess+t.block_minutes-1)/t.block_minutes;
 const long long charge=blocks*t.units_per_block;
 if(blocks>INT_MAX||charge>INT_MAX)return {false,0,0,0,"invalid"};
 return {true,minutes,static_cast<int>(blocks),static_cast<int>(charge),"billed: "+std::to_string(blocks)+" blocks, "+std::to_string(charge)+" units"};
}}
''',
        r'''#include "task.h"
#include <string>
int main(){duration_formatting::ParkingBlockReceipt f;auto a=f.make(20,{20,15,3});auto b=f.make(21,{20,15,3});return a.valid&&a.billed_blocks==0&&a.text=="free: 20 min"&&b.valid&&b.billed_blocks==1&&b.charge_units==3?0:1;}
''',
        r'''#include "task.h"
#include <climits>
int main(){duration_formatting::ParkingBlockReceipt f;auto z=f.make(0,{0,10,2});auto e=f.make(40,{10,15,4});auto p=f.make(41,{10,15,4});auto bad=f.make(5,{0,0,1});auto neg=f.make(-1,{0,5,1});auto ov=f.make(INT_MAX,{0,1,INT_MAX});return z.valid&&e.valid&&e.billed_blocks==2&&e.charge_units==8&&p.valid&&p.billed_blocks==3&&!bad.valid&&!neg.valid&&!ov.valid?0:1;}
''',
        "const long long blocks=(excess+t.block_minutes-1)/t.block_minutes;",
        "const long long blocks=excess/t.block_minutes;",
        "floor division under-bills a partial block",
    ),
    DurationCase(
        "duration-build-summary", "pipeline-stage-digest", "Pipeline stage digest",
        "Aggregate named build stages and select the earliest longest stage while reporting failures.",
        """# Instructions

Implement `duration_formatting::PipelineStageDigest::summarize`. Stage names must be nonempty and unique, seconds must be nonnegative, and the checked total must fit `int`. Empty input is a valid zero report. Preserve input order for failed-stage names. Select the earliest stage among equal longest durations. Text is `empty pipeline` for empty input, otherwise `<total>s total; longest=<name>; failed=<count>`. Invalid input returns `valid=false` without a partial report. All behavior is deterministic and offline.
""",
        "ordered BuildStage collection -> total/strict maximum/failure list",
        "single-pass-validation-strict-max-stable-failures",
        r'''#ifndef TASK_H
#define TASK_H
#include <string>
#include <vector>
namespace duration_formatting {
struct BuildStage { std::string name; int seconds; bool failed; };
struct PipelineDigest { bool valid; int total_seconds; std::string longest_stage; std::vector<std::string> failed_stages; std::string text; };
class PipelineStageDigest { public: PipelineDigest summarize(const std::vector<BuildStage>& stages) const; };
}
#endif
''',
        r'''#include "task.h"
namespace duration_formatting { PipelineDigest PipelineStageDigest::summarize(const std::vector<BuildStage>&) const { return {false,0,{}, {},"invalid"}; } }
''',
        r'''#include "task.h"
#include <climits>
#include <unordered_set>
namespace duration_formatting {
PipelineDigest PipelineStageDigest::summarize(const std::vector<BuildStage>& stages)const{
 if(stages.empty())return {true,0,"",{},"empty pipeline"};
 std::unordered_set<std::string> seen;long long total=0;int longest=-1;std::string longest_name;std::vector<std::string> failed;
 for(const auto& s:stages){if(s.name.empty()||s.seconds<0||!seen.insert(s.name).second)return {false,0,"",{},"invalid"};total+=s.seconds;if(total>INT_MAX)return {false,0,"",{},"invalid"};if(s.seconds>longest){longest=s.seconds;longest_name=s.name;}if(s.failed)failed.push_back(s.name);}
 return {true,static_cast<int>(total),longest_name,failed,std::to_string(total)+"s total; longest="+longest_name+"; failed="+std::to_string(failed.size())};
}}
''',
        r'''#include "task.h"
int main(){duration_formatting::PipelineStageDigest d;auto r=d.summarize({{"compile",12,false},{"link",12,true},{"test",4,true}});auto e=d.summarize({});return r.valid&&r.total_seconds==28&&r.longest_stage=="compile"&&r.failed_stages==std::vector<std::string>({"link","test"})&&e.valid&&e.text=="empty pipeline"?0:1;}
''',
        r'''#include "task.h"
#include <climits>
int main(){duration_formatting::PipelineStageDigest d;auto tie=d.summarize({{"first",7,false},{"second",7,false}});auto dup=d.summarize({{"x",1,false},{"x",2,false}});auto neg=d.summarize({{"x",-1,false}});auto ov=d.summarize({{"x",INT_MAX,false},{"y",1,false}});return tie.valid&&tie.longest_stage=="first"&&!dup.valid&&!neg.valid&&!ov.valid?0:1;}
''',
        "if(s.seconds>longest){longest=s.seconds;longest_name=s.name;}",
        "if(s.seconds>=longest){longest=s.seconds;longest_name=s.name;}",
        "latest stage incorrectly wins a longest-duration tie",
    ),
    DurationCase(
        "duration-media-chapters", "chapter-timeline-labels", "Chapter timeline labels",
        "Validate a complete media partition and render millisecond-precise chapter labels.",
        """# Instructions

Implement `duration_formatting::ChapterTimelineLabels::format`. Media length and span endpoints are nonnegative. A zero-length medium has exactly an empty chapter list. Otherwise titles are nonempty, the first span starts at zero, every span has positive length, spans are contiguous in input order, and the last ends at media length. Reject gaps, overlaps, and out-of-range endpoints without returning partial labels. Each label is `<title> [MM:SS.mmm-MM:SS.mmm]`, preserving input order; minutes may exceed 59. Use integer arithmetic only.
""",
        "contiguous ChapterSpan partition -> validate-all then fixed-width labels",
        "two-phase-partition-validation-and-integer-formatting",
        r'''#ifndef TASK_H
#define TASK_H
#include <string>
#include <vector>
namespace duration_formatting {
struct ChapterSpan { std::string title; int start_ms; int end_ms; };
struct ChapterLabels { bool valid; std::vector<std::string> labels; std::string error; };
class ChapterTimelineLabels { public: ChapterLabels format(int media_length_ms,const std::vector<ChapterSpan>& chapters) const; };
}
#endif
''',
        r'''#include "task.h"
namespace duration_formatting { ChapterLabels ChapterTimelineLabels::format(int,const std::vector<ChapterSpan>&) const { return {false,{},"invalid"}; } }
''',
        r'''#include "task.h"
#include <iomanip>
#include <sstream>
namespace { std::string stamp(int ms){std::ostringstream o;o<<std::setfill('0')<<std::setw(2)<<(ms/60000)<<":"<<std::setw(2)<<((ms/1000)%60)<<"."<<std::setw(3)<<(ms%1000);return o.str();} }
namespace duration_formatting {
ChapterLabels ChapterTimelineLabels::format(int length,const std::vector<ChapterSpan>& chapters)const{
 if(length<0||(length==0&&!chapters.empty())||(length>0&&chapters.empty()))return {false,{},"invalid partition"};
 int cursor=0;for(const auto& c:chapters){if(c.title.empty()||c.start_ms!=cursor||c.end_ms<=c.start_ms||c.end_ms>length)return {false,{},"invalid partition"};cursor=c.end_ms;}if(cursor!=length)return {false,{},"invalid partition"};
 std::vector<std::string> labels;labels.reserve(chapters.size());for(const auto& c:chapters)labels.push_back(c.title+" ["+stamp(c.start_ms)+"-"+stamp(c.end_ms)+"]");return {true,labels,""};
}}
''',
        r'''#include "task.h"
int main(){duration_formatting::ChapterTimelineLabels f;auto r=f.format(61500,{{"intro",0,1500},{"main",1500,61500}});return r.valid&&r.labels==std::vector<std::string>({"intro [00:00.000-00:01.500]","main [00:01.500-01:01.500]"})?0:1;}
''',
        r'''#include "task.h"
int main(){duration_formatting::ChapterTimelineLabels f;auto z=f.format(0,{});auto gap=f.format(20,{{"a",0,5},{"b",6,20}});auto overlap=f.format(20,{{"a",0,10},{"b",9,20}});auto short_end=f.format(20,{{"a",0,19}});auto title=f.format(1,{{"",0,1}});return z.valid&&z.labels.empty()&&!gap.valid&&!overlap.valid&&!short_end.valid&&!title.valid?0:1;}
''',
        "c.start_ms!=cursor",
        "c.start_ms<cursor",
        "a gap is accepted instead of requiring a complete partition",
    ),
    DurationCase(
        "duration-delivery-sla", "split-budget-sla", "Split budget SLA",
        "Compare two measured phases against independent budgets and explain the combined status.",
        """# Instructions

Implement `duration_formatting::SplitBudgetSla::explain`. All measured and allowance seconds must be nonnegative. Equality is on time. Compute processing and transit excess independently, clamp each at zero, and checked-sum them. Status is `on_time`, `processing_late`, `transit_late`, or `both_late`. Text is exactly `on time` or `processing +<p>s; transit +<t>s`. Invalid input has `valid=false`. Do not replace the independent budgets with one combined-total comparison.
""",
        "two SplitBudget records -> independent excess lattice -> SlaExplanation",
        "lane-wise-clamp-and-four-state-selection",
        r'''#ifndef TASK_H
#define TASK_H
#include <string>
namespace duration_formatting {
enum class SlaStatus { on_time, processing_late, transit_late, both_late };
struct SplitBudget { int processing_seconds; int transit_seconds; };
struct SlaExplanation { bool valid; SlaStatus status; int processing_excess; int transit_excess; int total_excess; std::string text; };
class SplitBudgetSla { public: SlaExplanation explain(const SplitBudget& measured,const SplitBudget& allowance) const; };
}
#endif
''',
        r'''#include "task.h"
namespace duration_formatting { SlaExplanation SplitBudgetSla::explain(const SplitBudget&,const SplitBudget&) const { return {false,SlaStatus::on_time,0,0,0,"invalid"}; } }
''',
        r'''#include "task.h"
#include <climits>
#include <algorithm>
namespace duration_formatting {
SlaExplanation SplitBudgetSla::explain(const SplitBudget& m,const SplitBudget& a)const{
 if(m.processing_seconds<0||m.transit_seconds<0||a.processing_seconds<0||a.transit_seconds<0)return {false,SlaStatus::on_time,0,0,0,"invalid"};
 const int pe=std::max(0,m.processing_seconds-a.processing_seconds);const int te=std::max(0,m.transit_seconds-a.transit_seconds);if(static_cast<long long>(pe)+te>INT_MAX)return {false,SlaStatus::on_time,0,0,0,"invalid"};
 const bool p=pe>0,t=te>0;const SlaStatus status=p?(t?SlaStatus::both_late:SlaStatus::processing_late):(t?SlaStatus::transit_late:SlaStatus::on_time);const std::string text=(p||t)?"processing +"+std::to_string(pe)+"s; transit +"+std::to_string(te)+"s":"on time";return {true,status,pe,te,pe+te,text};
}}
''',
        r'''#include "task.h"
int main(){duration_formatting::SplitBudgetSla s;auto a=s.explain({10,20},{10,20});auto b=s.explain({13,25},{10,20});return a.valid&&a.status==duration_formatting::SlaStatus::on_time&&a.text=="on time"&&b.valid&&b.status==duration_formatting::SlaStatus::both_late&&b.total_excess==8?0:1;}
''',
        r'''#include "task.h"
int main(){duration_formatting::SplitBudgetSla s;auto p=s.explain({20,10},{10,20});auto t=s.explain({10,20},{20,10});auto bad=s.explain({-1,0},{0,0});return p.valid&&p.status==duration_formatting::SlaStatus::processing_late&&p.processing_excess==10&&p.transit_excess==0&&t.valid&&t.status==duration_formatting::SlaStatus::transit_late&&!bad.valid?0:1;}
''',
        "const bool p=pe>0,t=te>0;",
        "const bool p=(m.processing_seconds+m.transit_seconds)>(a.processing_seconds+a.transit_seconds),t=false;",
        "a combined-total comparison hides which independent phase is late",
    ),
    DurationCase(
        "duration-sports-splits", "ranked-lap-recap", "Ranked lap recap",
        "Rank uniquely numbered laps by elapsed milliseconds and summarize total and spread.",
        """# Instructions

Implement `duration_formatting::RankedLapRecapBuilder::recap`. Lap numbers and milliseconds must be positive and lap numbers unique; checked total must fit `int`. Empty input is valid with zero total/spread and empty rank. Rank fastest first, breaking equal-duration ties by lower lap number, without changing the input. Spread is slowest minus fastest. Text is `<total>ms; spread=<spread>ms; complete|partial`. Invalid input returns no partial rank.
""",
        "LapSplit list -> checked extrema/total -> comparator-ranked lap numbers",
        "index-sort-fastest-then-lap-number",
        r'''#ifndef TASK_H
#define TASK_H
#include <string>
#include <vector>
namespace duration_formatting {
struct LapSplit { int lap_number; int milliseconds; };
struct RankedLapRecap { bool valid; int total_ms; int spread_ms; std::vector<int> rank_order; std::string text; };
class RankedLapRecapBuilder { public: RankedLapRecap recap(const std::vector<LapSplit>& laps,bool complete) const; };
}
#endif
''',
        r'''#include "task.h"
namespace duration_formatting { RankedLapRecap RankedLapRecapBuilder::recap(const std::vector<LapSplit>&,bool) const { return {false,0,0,{},"invalid"}; } }
''',
        r'''#include "task.h"
#include <algorithm>
#include <climits>
#include <unordered_set>
namespace duration_formatting {
RankedLapRecap RankedLapRecapBuilder::recap(const std::vector<LapSplit>& laps,bool complete)const{
 if(laps.empty())return {true,0,0,{},complete?"0ms; spread=0ms; complete":"0ms; spread=0ms; partial"};
 std::unordered_set<int> ids;long long total=0;int lo=INT_MAX,hi=0;std::vector<std::size_t> order;
 for(std::size_t i=0;i<laps.size();++i){const auto& x=laps[i];if(x.lap_number<=0||x.milliseconds<=0||!ids.insert(x.lap_number).second)return {false,0,0,{},"invalid"};total+=x.milliseconds;if(total>INT_MAX)return {false,0,0,{},"invalid"};lo=std::min(lo,x.milliseconds);hi=std::max(hi,x.milliseconds);order.push_back(i);}
 std::sort(order.begin(),order.end(),[&](std::size_t a,std::size_t b){return laps[a].milliseconds!=laps[b].milliseconds?laps[a].milliseconds<laps[b].milliseconds:laps[a].lap_number<laps[b].lap_number;});std::vector<int> rank;for(auto i:order)rank.push_back(laps[i].lap_number);const int spread=hi-lo;return {true,static_cast<int>(total),spread,rank,std::to_string(total)+"ms; spread="+std::to_string(spread)+"ms; "+(complete?"complete":"partial")};
}}
''',
        r'''#include "task.h"
int main(){duration_formatting::RankedLapRecapBuilder b;auto r=b.recap({{3,1000},{1,900},{2,900}},false);return r.valid&&r.total_ms==2800&&r.spread_ms==100&&r.rank_order==std::vector<int>({1,2,3})&&r.text=="2800ms; spread=100ms; partial"?0:1;}
''',
        r'''#include "task.h"
#include <climits>
int main(){duration_formatting::RankedLapRecapBuilder b;auto e=b.recap({},true);auto d=b.recap({{1,2},{1,3}},true);auto n=b.recap({{1,0}},true);auto ov=b.recap({{1,INT_MAX},{2,1}},true);return e.valid&&e.rank_order.empty()&&!d.valid&&!n.valid&&!ov.valid?0:1;}
''',
        "laps[a].milliseconds<laps[b].milliseconds",
        "laps[a].milliseconds>laps[b].milliseconds",
        "the ranking orders the slowest lap first",
    ),
    DurationCase(
        "duration-battery-forecast", "reserve-discharge-forecast", "Reserve discharge forecast",
        "Derive a conservative operating-time forecast from capacity, reserve, and observed drain.",
        """# Instructions

Implement `duration_formatting::ReserveDischargeForecast::forecast`. Stored and reserve units are nonnegative and reserve may not exceed stored. At least one sample is required; each sample has positive consumed units and elapsed seconds. Checked-sum samples, then set conservative rate to `ceil(total consumed / total seconds)`. Usable units exclude reserve and whole seconds use floor division by that rate. Band is `empty` at zero seconds, `short` below 60, otherwise `steady`. Return text `<seconds>s at <rate> units/s (<band>)`. Invalid input returns `valid=false`.
""",
        "DrainSample observations -> aggregate ceiling rate -> reserve-excluded floor forecast",
        "aggregate-ceiling-rate-then-floor-duration-band",
        r'''#ifndef TASK_H
#define TASK_H
#include <string>
#include <vector>
namespace duration_formatting {
struct DrainSample { int consumed_units; int elapsed_seconds; };
struct DischargeForecast { bool valid; int usable_units; int conservative_rate; int whole_seconds; std::string band; std::string text; };
class ReserveDischargeForecast { public: DischargeForecast forecast(int stored_units,int reserve_units,const std::vector<DrainSample>& samples) const; };
}
#endif
''',
        r'''#include "task.h"
namespace duration_formatting { DischargeForecast ReserveDischargeForecast::forecast(int,int,const std::vector<DrainSample>&) const { return {false,0,0,0,"","invalid"}; } }
''',
        r'''#include "task.h"
#include <climits>
namespace duration_formatting {
DischargeForecast ReserveDischargeForecast::forecast(int stored,int reserve,const std::vector<DrainSample>& samples)const{
 if(stored<0||reserve<0||reserve>stored||samples.empty())return {false,0,0,0,"","invalid"};
 long long used=0,secs=0;for(const auto& s:samples){if(s.consumed_units<=0||s.elapsed_seconds<=0)return {false,0,0,0,"","invalid"};used+=s.consumed_units;secs+=s.elapsed_seconds;if(used>INT_MAX||secs>INT_MAX)return {false,0,0,0,"","invalid"};}
 const long long rate=(used+secs-1)/secs;const int usable=stored-reserve;const int whole=static_cast<int>(usable/rate);const std::string band=whole==0?"empty":(whole<60?"short":"steady");return {true,usable,static_cast<int>(rate),whole,band,std::to_string(whole)+"s at "+std::to_string(rate)+" units/s ("+band+")"};
}}
''',
        r'''#include "task.h"
int main(){duration_formatting::ReserveDischargeForecast f;auto r=f.forecast(100,10,{{3,2},{2,2}});return r.valid&&r.usable_units==90&&r.conservative_rate==2&&r.whole_seconds==45&&r.band=="short"?0:1;}
''',
        r'''#include "task.h"
#include <climits>
int main(){duration_formatting::ReserveDischargeForecast f;auto z=f.forecast(10,10,{{1,1}});auto bad=f.forecast(5,6,{{1,1}});auto empty=f.forecast(5,0,{});auto sample=f.forecast(5,0,{{0,1}});auto ov=f.forecast(5,0,{{INT_MAX,1},{1,1}});return z.valid&&z.whole_seconds==0&&z.band=="empty"&&!bad.valid&&!empty.valid&&!sample.valid&&!ov.valid?0:1;}
''',
        "const long long rate=(used+secs-1)/secs;",
        "const long long rate=used/secs;",
        "a truncated drain rate overstates remaining time",
    ),
    DurationCase(
        "duration-maintenance-window", "maintenance-event-ledger", "Maintenance event ledger",
        "Interpret begin/pause/resume/finish events into active and paused maintenance totals.",
        """# Instructions

Implement `duration_formatting::MaintenanceEventLedger::report`. Planned minutes and event times are nonnegative and event times strictly increase. A nonempty sequence must be `begin_work`, zero or more `pause,resume` pairs, then `finish`; finishing while paused is invalid. Empty input is valid only for a zero plan. Attribute each interval to active or paused state. Remaining is `max(0, planned-active)` and overrun means active exceeds plan. Invalid sequences return no partial totals. Text is `active=<a>; paused=<p>; remaining=<r>; ok|overrun`.
""",
        "WindowEvent trace -> finite-state interval attribution -> MaintenanceLedger",
        "strict-event-state-machine-active-paused-ledger",
        r'''#ifndef TASK_H
#define TASK_H
#include <string>
#include <vector>
namespace duration_formatting {
enum class WindowEventKind { begin_work, pause, resume, finish };
struct WindowEvent { WindowEventKind kind; int minute; };
struct MaintenanceLedger { bool valid; int active_minutes; int paused_minutes; int remaining_minutes; bool overrun; std::string text; };
class MaintenanceEventLedger { public: MaintenanceLedger report(int planned_minutes,const std::vector<WindowEvent>& events) const; };
}
#endif
''',
        r'''#include "task.h"
namespace duration_formatting { MaintenanceLedger MaintenanceEventLedger::report(int,const std::vector<WindowEvent>&) const { return {false,0,0,0,false,"invalid"}; } }
''',
        r'''#include "task.h"
#include <algorithm>
namespace duration_formatting {
MaintenanceLedger MaintenanceEventLedger::report(int planned,const std::vector<WindowEvent>& events)const{
 if(planned<0)return {false,0,0,0,false,"invalid"};
 if(events.empty())return planned==0?MaintenanceLedger{true,0,0,0,false,"active=0; paused=0; remaining=0; ok"}:MaintenanceLedger{false,0,0,0,false,"invalid"};
 if(events.front().kind!=WindowEventKind::begin_work||events.front().minute<0)return {false,0,0,0,false,"invalid"};
 bool working=true;int last=events.front().minute,active=0,paused=0;for(std::size_t i=1;i<events.size();++i){const auto& e=events[i];if(e.minute<=last)return {false,0,0,0,false,"invalid"};if(e.kind==WindowEventKind::pause&&working){active+=e.minute-last;working=false;}else if(e.kind==WindowEventKind::resume&&!working){paused+=e.minute-last;working=true;}else if(e.kind==WindowEventKind::finish&&working&&i+1==events.size()){active+=e.minute-last;last=e.minute;const int remaining=std::max(0,planned-active);const bool over=active>planned;return {true,active,paused,remaining,over,"active="+std::to_string(active)+"; paused="+std::to_string(paused)+"; remaining="+std::to_string(remaining)+"; "+(over?"overrun":"ok")};}else return {false,0,0,0,false,"invalid"};last=e.minute;}return {false,0,0,0,false,"invalid"};
}}
''',
        r'''#include "task.h"
using K=duration_formatting::WindowEventKind;
int main(){duration_formatting::MaintenanceEventLedger r;auto x=r.report(20,{{K::begin_work,2},{K::pause,7},{K::resume,10},{K::finish,18}});return x.valid&&x.active_minutes==13&&x.paused_minutes==3&&x.remaining_minutes==7&&!x.overrun?0:1;}
''',
        r'''#include "task.h"
using K=duration_formatting::WindowEventKind;
int main(){duration_formatting::MaintenanceEventLedger r;auto z=r.report(0,{});auto empty=r.report(1,{});auto order=r.report(5,{{K::begin_work,1},{K::finish,1}});auto resume=r.report(5,{{K::begin_work,0},{K::resume,1},{K::finish,2}});auto paused_finish=r.report(5,{{K::begin_work,0},{K::pause,1},{K::finish,2}});auto over=r.report(2,{{K::begin_work,0},{K::finish,3}});return z.valid&&!empty.valid&&!order.valid&&!resume.valid&&!paused_finish.valid&&over.valid&&over.overrun?0:1;}
''',
        "paused+=e.minute-last;working=true;",
        "active+=e.minute-last;working=true;",
        "paused time is incorrectly charged as active work",
    ),
    DurationCase(
        "duration-study-ledger", "categorized-focus-digest", "Categorized focus digest",
        "Aggregate study entries in configured category order with an explicit unassigned bucket.",
        """# Instructions

Implement `duration_formatting::CategorizedFocusDigest::digest`. Configured category names must be nonempty and unique. Entry minutes must be positive. Aggregate known entries into the caller's category order and all unknown categories into `unassigned_minutes`; never discard them. Empty configuration/entries are valid. Checked totals must fit `int`. Text has one `<category>=<minutes>` row in configured order, followed by `unassigned=<minutes>; total=<minutes>`. Invalid input returns no partial buckets.
""",
        "configured category index + FocusEntry stream -> ordered buckets/unassigned",
        "lookup-indexed-stable-bucket-aggregation",
        r'''#ifndef TASK_H
#define TASK_H
#include <string>
#include <vector>
namespace duration_formatting {
struct FocusEntry { std::string category; int minutes; };
struct FocusDigest { bool valid; std::vector<int> category_minutes; int unassigned_minutes; int total_minutes; std::string text; };
class CategorizedFocusDigest { public: FocusDigest digest(const std::vector<std::string>& category_order,const std::vector<FocusEntry>& entries) const; };
}
#endif
''',
        r'''#include "task.h"
namespace duration_formatting { FocusDigest CategorizedFocusDigest::digest(const std::vector<std::string>&,const std::vector<FocusEntry>&) const { return {false,{},0,0,"invalid"}; } }
''',
        r'''#include "task.h"
#include <climits>
#include <unordered_map>
namespace duration_formatting {
FocusDigest CategorizedFocusDigest::digest(const std::vector<std::string>& order,const std::vector<FocusEntry>& entries)const{
 std::unordered_map<std::string,std::size_t> index;for(std::size_t i=0;i<order.size();++i)if(order[i].empty()||!index.emplace(order[i],i).second)return {false,{},0,0,"invalid"};std::vector<long long> sums(order.size());long long unassigned=0,total=0;
 for(const auto& entry:entries){if(entry.minutes<=0)return {false,{},0,0,"invalid"};total+=entry.minutes;if(total>INT_MAX)return {false,{},0,0,"invalid"};const auto found=index.find(entry.category);if(found==index.end())unassigned+=entry.minutes;else sums[found->second]+=entry.minutes;}
 std::vector<int> values;std::string text;for(std::size_t i=0;i<order.size();++i){values.push_back(static_cast<int>(sums[i]));text+=order[i]+"="+std::to_string(sums[i])+"; ";}text+="unassigned="+std::to_string(unassigned)+"; total="+std::to_string(total);return {true,values,static_cast<int>(unassigned),static_cast<int>(total),text};
}}
''',
        r'''#include "task.h"
int main(){duration_formatting::CategorizedFocusDigest d;auto r=d.digest({"math","reading"},{{"reading",10},{"other",5},{"math",7}});return r.valid&&r.category_minutes==std::vector<int>({7,10})&&r.unassigned_minutes==5&&r.total_minutes==22&&r.text=="math=7; reading=10; unassigned=5; total=22"?0:1;}
''',
        r'''#include "task.h"
#include <climits>
int main(){duration_formatting::CategorizedFocusDigest d;auto e=d.digest({},{});auto dup=d.digest({"x","x"},{});auto blank=d.digest({""},{});auto neg=d.digest({"x"},{{"x",0}});auto ov=d.digest({"x"},{{"x",INT_MAX},{"x",1}});auto u=d.digest({},{{"a",2},{"b",3}});return e.valid&&!dup.valid&&!blank.valid&&!neg.valid&&!ov.valid&&u.valid&&u.unassigned_minutes==5?0:1;}
''',
        "if(found==index.end())unassigned+=entry.minutes;",
        "if(found==index.end())unassigned+=0;",
        "unknown-category minutes are silently discarded",
    ),
    DurationCase(
        "duration-rescue-air", "turnback-air-plan", "Turn-back air plan",
        "Compute conservative team use, reserve, usable duration, and a turn-back minute.",
        """# Instructions

Implement `duration_formatting::TurnbackAirPlan::plan`. Cylinder units are positive, reserve basis points are 0..10000, outbound minutes are nonnegative, samples are nonempty, diver IDs are positive and unique, and use/minutes are positive. Round each diver's sampled rate upward before summing team rate. Reserve units are `ceil(cylinder*basis_points/10000)`. Usable duration floors `(cylinder-reserve)/team_rate`; turn-back is the smaller of outbound minutes and half the usable duration. Checked arithmetic failure is invalid. Text is `rate=<r>; reserve=<u>; usable=<m>; turn=<t>`.
""",
        "unique BreathingSample team -> per-diver ceiling -> reserve ceiling/turnback minimum",
        "per-member-rounding-sum-and-conservative-turnback",
        r'''#ifndef TASK_H
#define TASK_H
#include <string>
#include <vector>
namespace duration_formatting {
struct BreathingSample { int diver_id; int units_used; int minutes; };
struct TurnbackPlan { bool valid; int team_rate; int reserve_units; int usable_minutes; int turnback_minute; std::string text; };
class TurnbackAirPlan { public: TurnbackPlan plan(int cylinder_units,int reserve_basis_points,int outbound_minutes,const std::vector<BreathingSample>& samples) const; };
}
#endif
''',
        r'''#include "task.h"
namespace duration_formatting { TurnbackPlan TurnbackAirPlan::plan(int,int,int,const std::vector<BreathingSample>&) const { return {false,0,0,0,0,"invalid"}; } }
''',
        r'''#include "task.h"
#include <algorithm>
#include <climits>
#include <unordered_set>
namespace duration_formatting {
TurnbackPlan TurnbackAirPlan::plan(int cylinder,int basis,int outbound,const std::vector<BreathingSample>& samples)const{
 if(cylinder<=0||basis<0||basis>10000||outbound<0||samples.empty())return {false,0,0,0,0,"invalid"};
 std::unordered_set<int> ids;long long rate=0;for(const auto& s:samples){if(s.diver_id<=0||s.units_used<=0||s.minutes<=0||!ids.insert(s.diver_id).second)return {false,0,0,0,0,"invalid"};rate+=(static_cast<long long>(s.units_used)+s.minutes-1)/s.minutes;if(rate>INT_MAX)return {false,0,0,0,0,"invalid"};}
 const long long reserve=(static_cast<long long>(cylinder)*basis+9999)/10000;const int usable=static_cast<int>((cylinder-reserve)/rate);const int turn=std::min(outbound,usable/2);return {true,static_cast<int>(rate),static_cast<int>(reserve),usable,turn,"rate="+std::to_string(rate)+"; reserve="+std::to_string(reserve)+"; usable="+std::to_string(usable)+"; turn="+std::to_string(turn)};
}}
''',
        r'''#include "task.h"
int main(){duration_formatting::TurnbackAirPlan p;auto r=p.plan(100,1000,20,{{1,5,2},{2,4,3}});return r.valid&&r.team_rate==5&&r.reserve_units==10&&r.usable_minutes==18&&r.turnback_minute==9?0:1;}
''',
        r'''#include "task.h"
int main(){duration_formatting::TurnbackAirPlan p;auto clamp=p.plan(100,0,3,{{1,10,10}});auto full=p.plan(100,10000,3,{{1,10,10}});auto dup=p.plan(100,0,3,{{1,1,1},{1,1,1}});auto bad=p.plan(0,0,0,{{1,1,1}});return clamp.valid&&clamp.turnback_minute==3&&full.valid&&full.usable_minutes==0&&!dup.valid&&!bad.valid?0:1;}
''',
        "rate+=(static_cast<long long>(s.units_used)+s.minutes-1)/s.minutes;",
        "rate+=static_cast<long long>(s.units_used)/s.minutes;",
        "per-diver rate truncation weakens the conservative team envelope",
    ),
    DurationCase(
        "duration-archive-retention", "tiered-retention-notice", "Tiered retention notice",
        "Select the greatest age-qualified tier and render retention policy state.",
        """# Instructions

Implement `duration_formatting::TieredRetentionNotice::render`. Age is nonnegative. Policy is nonempty; tier labels are nonempty, minimum ages strictly increase, and each purge age is at least its minimum. Select the greatest tier whose minimum is at most the age; age below the first tier is invalid. Validate policy before applying legal hold. A legal hold is `indefinite`. Otherwise return `retained` with days remaining, `due_now` at equality, or `overdue` with overdue magnitude. Text is `<tier>: hold`, `<tier>: <n> days remaining`, `<tier>: due now`, or `<tier>: overdue <n> days`.
""",
        "ordered RetentionTier policy -> greatest qualifying selection -> precedence/state notice",
        "validate-then-greatest-lower-bound-and-state-precedence",
        r'''#ifndef TASK_H
#define TASK_H
#include <string>
#include <vector>
namespace duration_formatting {
struct RetentionTier { int minimum_age_days; int purge_age_days; std::string label; };
enum class RetentionState { retained, due_now, overdue, indefinite };
struct RetentionNotice { bool valid; RetentionState state; std::string tier; int days; std::string text; };
class TieredRetentionNotice { public: RetentionNotice render(int age_days,bool legal_hold,const std::vector<RetentionTier>& tiers) const; };
}
#endif
''',
        r'''#include "task.h"
namespace duration_formatting { RetentionNotice TieredRetentionNotice::render(int,bool,const std::vector<RetentionTier>&) const { return {false,RetentionState::retained,"",0,"invalid"}; } }
''',
        r'''#include "task.h"
namespace duration_formatting {
RetentionNotice TieredRetentionNotice::render(int age,bool hold,const std::vector<RetentionTier>& tiers)const{
 if(age<0||tiers.empty())return {false,RetentionState::retained,"",0,"invalid"};
 for(std::size_t i=0;i<tiers.size();++i)if(tiers[i].minimum_age_days<0||tiers[i].purge_age_days<tiers[i].minimum_age_days||tiers[i].label.empty()||(i>0&&tiers[i-1].minimum_age_days>=tiers[i].minimum_age_days))return {false,RetentionState::retained,"",0,"invalid"};
 std::size_t choice=0;bool found=false;for(std::size_t i=0;i<tiers.size();++i){if(tiers[i].minimum_age_days<=age){choice=i;found=true;}else break;}if(!found)return {false,RetentionState::retained,"",0,"invalid"};const auto& t=tiers[choice];if(hold)return {true,RetentionState::indefinite,t.label,0,t.label+": hold"};if(age<t.purge_age_days){const int days=t.purge_age_days-age;return {true,RetentionState::retained,t.label,days,t.label+": "+std::to_string(days)+" days remaining"};}if(age==t.purge_age_days)return {true,RetentionState::due_now,t.label,0,t.label+": due now"};const int days=age-t.purge_age_days;return {true,RetentionState::overdue,t.label,days,t.label+": overdue "+std::to_string(days)+" days"};
}}
''',
        r'''#include "task.h"
int main(){duration_formatting::TieredRetentionNotice n;std::vector<duration_formatting::RetentionTier> p={{0,10,"new"},{5,20,"aged"}};auto a=n.render(5,false,p);auto h=n.render(7,true,p);return a.valid&&a.tier=="aged"&&a.days==15&&h.valid&&h.state==duration_formatting::RetentionState::indefinite&&h.text=="aged: hold"?0:1;}
''',
        r'''#include "task.h"
int main(){duration_formatting::TieredRetentionNotice n;std::vector<duration_formatting::RetentionTier> p={{2,5,"warm"},{7,9,"cold"}};auto low=n.render(1,false,p);auto due=n.render(9,false,p);auto late=n.render(11,false,p);auto order=n.render(8,false,{{2,5,"x"},{2,8,"y"}});auto malformed_hold=n.render(8,true,{{2,1,"x"}});return !low.valid&&due.valid&&due.state==duration_formatting::RetentionState::due_now&&late.valid&&late.state==duration_formatting::RetentionState::overdue&&late.days==2&&!order.valid&&!malformed_hold.valid?0:1;}
''',
        "choice=i;found=true;",
        "choice=i;found=true;break;",
        "the least-qualified tier wins instead of the greatest-qualified tier",
    ),
)


NEGATIVE_MUTATIONS = {
    case.task_id: (case.negative_old, case.negative_new, case.negative_reason)
    for case in CASES
}
