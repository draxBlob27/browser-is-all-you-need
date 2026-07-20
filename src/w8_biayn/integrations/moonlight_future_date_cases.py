"""Independent contracts for future-date-calculations v2."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FutureDateCase:
    legacy_id: str
    task_id: str
    title: str
    profile: str
    public_api: str
    marker: str
    instructions: str
    header: str
    reference: str
    visible_test: str
    hidden_test: str
    negative_old: str
    negative_new: str
    negative_reason: str

    @property
    def starter(self) -> str:
        return '#include "task.h"\nnamespace curriculum { /* Implement the documented API. */ }\n'


CASES = (
    FutureDateCase(
        "future-warranty-milestones",
        "warranty-service-calendar",
        "Warranty Service Calendar",
        "month-clamp-plus-closure-walk",
        "make_service_calendar(SalePolicy, optional<Date>, closures)",
        "while(blocked(out.inspection))",
        r"""# Instructions

Implement `make_service_calendar`. Validate the sale date, positive ordered month
offsets, an optional registration date not before sale, and unique valid closure
dates. Add policy months with end-of-month clamping. Registration moves only the
extended-warranty base forward. Move an inspection forward one day repeatedly while
it lands on a closure. Return `valid=false` atomically on invalid input.
""",
        r"""#pragma once
#include <optional>
#include <vector>
namespace curriculum { struct Date{int year,month,day;}; struct SalePolicy{Date sold;int inspection_months;int standard_months;int extension_months;}; struct ServiceCalendar{bool valid=false;Date inspection{};Date standard_end{};Date extended_end{};int closure_shifts=0;}; ServiceCalendar make_service_calendar(const SalePolicy&,std::optional<Date>,const std::vector<Date>&); }
""",
        r"""#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum { namespace { bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);} int dim(int y,int m){static const int d[]={31,28,31,30,31,30,31,31,30,31,30,31};return m==2?d[1]+(leap(y)?1:0):(m>=1&&m<=12?d[m-1]:0);} bool valid(Date x){return x.year>=1&&x.year<=9999&&x.month>=1&&x.month<=12&&x.day>=1&&x.day<=dim(x.year,x.month);} long long serial(Date x){long long y=x.year-1,n=365*y+y/4-y/100+y/400;for(int m=1;m<x.month;++m)n+=dim(x.year,m);return n+x.day-1;} Date from(long long n){int y=1;while(n>=365+(leap(y)?1:0)){n-=365+(leap(y)?1:0);++y;}int m=1;while(n>=dim(y,m))n-=dim(y,m++);return{y,m,(int)n+1};} bool addm(Date x,int n,Date& o){if(!valid(x)||n<0)return false;long long k=(long long)(x.year-1)*12+x.month-1+n;if(k>=9999LL*12)return false;o={(int)(k/12)+1,(int)(k%12)+1,std::min(x.day,dim((int)(k/12)+1,(int)(k%12)+1))};return true;} }
ServiceCalendar make_service_calendar(const SalePolicy&p,std::optional<Date> registration,const std::vector<Date>&closures){ServiceCalendar out;if(!valid(p.sold)||p.inspection_months<=0||p.standard_months<p.inspection_months||p.extension_months<=0)return out;if(registration&&(!valid(*registration)||serial(*registration)<serial(p.sold)))return out;std::set<long long> blocked;for(Date d:closures)if(!valid(d)||!blocked.insert(serial(d)).second)return out;if(!addm(p.sold,p.inspection_months,out.inspection)||!addm(p.sold,p.standard_months,out.standard_end))return out;Date base=registration&&serial(*registration)>serial(out.standard_end)?*registration:out.standard_end;if(!addm(base,p.extension_months,out.extended_end))return out;while(blocked.count(serial(out.inspection))){long long next=serial(out.inspection)+1;if(next>serial({9999,12,31}))return ServiceCalendar{};out.inspection=from(next);++out.closure_shifts;}out.valid=true;return out;} }
""",
        r"""#include "task.h"
int main(){using namespace curriculum;auto r=make_service_calendar({{2024,1,31},1,12,6},std::nullopt,{});return r.valid&&r.inspection.year==2024&&r.inspection.month==2&&r.inspection.day==29&&r.standard_end.year==2025?0:1;}
""",
        r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto r=make_service_calendar({{2024,1,29},1,12,3},Date{2025,3,1},{{2024,2,29},{2024,3,1}});f+=!(r.valid&&r.closure_shifts==2&&r.inspection.month==3&&r.inspection.day==2&&r.extended_end.month==6);f+=make_service_calendar({{2024,1,1},1,2,1},std::nullopt,{{2024,2,1},{2024,2,1}}).valid;return f;}
""",
        "while(blocked.count(serial(out.inspection)))",
        "if(blocked.count(serial(out.inspection)))",
        "advance through every consecutive closure rather than only one",
    ),
    FutureDateCase(
        "future-crop-treatment",
        "orchard-treatment-window",
        "Orchard Treatment Window",
        "stable-stage-order-plus-blackout-jump",
        "schedule_treatments(Date, stages, blackouts, horizon)",
        "std::stable_sort(order.begin(),order.end()",
        r"""# Instructions

Implement `schedule_treatments`. Stage IDs and blackout IDs are unique. Stage offsets
are nonnegative and processed by offset then input order. Blackouts are inclusive
valid intervals. A proposed day inside a blackout jumps to the day after that
interval, repeating across touching blackouts. Mark the stage unscheduled when the
result exceeds the inclusive horizon. Invalid input rejects the whole schedule.
""",
        r"""#pragma once
#include <string>
#include <vector>
namespace curriculum { struct Date{int year,month,day;}; struct GrowthStage{std::string id;int offset_days;}; struct Blackout{std::string id;Date first,last;}; struct Treatment{std::string stage;Date date{};bool scheduled=false;}; struct TreatmentPlan{bool valid=false;std::vector<Treatment> treatments;}; TreatmentPlan schedule_treatments(Date,const std::vector<GrowthStage>&,const std::vector<Blackout>&,Date); }
""",
        r"""#include "task.h"
#include <algorithm>
#include <numeric>
#include <set>
namespace curriculum { namespace { bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);} int dim(int y,int m){static const int d[]={31,28,31,30,31,30,31,31,30,31,30,31};return m==2?d[1]+leap(y):(m>0&&m<13?d[m-1]:0);} bool valid(Date x){return x.year>0&&x.year<10000&&x.month>0&&x.month<13&&x.day>0&&x.day<=dim(x.year,x.month);} long long serial(Date x){long long y=x.year-1,n=365*y+y/4-y/100+y/400;for(int m=1;m<x.month;++m)n+=dim(x.year,m);return n+x.day-1;} Date from(long long n){int y=1;while(n>=365+leap(y)){n-=365+leap(y);++y;}int m=1;while(n>=dim(y,m))n-=dim(y,m++);return{y,m,(int)n+1};} }
TreatmentPlan schedule_treatments(Date planted,const std::vector<GrowthStage>&stages,const std::vector<Blackout>&blackouts,Date horizon){TreatmentPlan out;if(!valid(planted)||!valid(horizon)||serial(horizon)<serial(planted))return out;std::set<std::string> ids;for(auto&s:stages)if(s.id.empty()||s.offset_days<0||!ids.insert(s.id).second)return out;ids.clear();std::vector<std::pair<long long,long long>> stops;for(auto&b:blackouts){if(b.id.empty()||!ids.insert(b.id).second||!valid(b.first)||!valid(b.last)||serial(b.last)<serial(b.first))return out;stops.push_back({serial(b.first),serial(b.last)});}std::sort(stops.begin(),stops.end());std::vector<std::size_t> order(stages.size());std::iota(order.begin(),order.end(),0);std::stable_sort(order.begin(),order.end(),[&](auto a,auto b){return stages[a].offset_days<stages[b].offset_days;});for(auto i:order){long long day=serial(planted)+stages[i].offset_days;bool moved=true;while(moved){moved=false;for(auto [a,b]:stops)if(day>=a&&day<=b){day=b+1;moved=true;}}Treatment t{stages[i].id,{},false};if(day<=serial(horizon)){t.date=from(day);t.scheduled=true;}out.treatments.push_back(t);}out.valid=true;return out;} }
""",
        r"""#include "task.h"
int main(){using namespace curriculum;auto p=schedule_treatments({2024,4,1},{{"fruit",5},{"bud",1}},{{"rain",{2024,4,2},{2024,4,3}}},{2024,4,30});return p.valid&&p.treatments.size()==2&&p.treatments[0].stage=="bud"&&p.treatments[0].date.day==4?0:1;}
""",
        r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto p=schedule_treatments({2024,1,1},{{"a",1},{"b",2}},{{"x",{2024,1,2},{2024,1,3}},{"y",{2024,1,4},{2024,1,5}}},{2024,1,5});f+=!(p.valid&&!p.treatments[0].scheduled&&!p.treatments[1].scheduled);f+=schedule_treatments({2024,1,1},{{"a",1},{"a",2}},{},{2024,2,1}).valid;return f;}
""",
        "day>=a&&day<=b",
        "day>a&&day<=b",
        "treat a blackout's first day as inclusive",
    ),
    FutureDateCase(
        "future-invoice-followups",
        "invoice-contact-state-machine",
        "Invoice Contact State Machine",
        "event-reduction-with-terminal-precedence",
        "plan_contacts(Invoice, events, ContactPolicy)",
        "terminal_day=std::min(terminal_day",
        r"""# Instructions

Implement `plan_contacts`. Validate unique event IDs and chronological dates at or
after issue. Paid and disputed events are terminal; the earliest terminal event
suppresses actions on or after its day. Otherwise schedule reminder from issue and
escalation from the latest prior contact. Existing contact kinds suppress the same
planned kind. Invalid histories return no partial actions.
""",
        r"""#pragma once
#include <string>
#include <vector>
namespace curriculum { struct Date{int year,month,day;}; enum class EventKind{contact_reminder,contact_escalation,paid,disputed}; struct Invoice{std::string id;Date issued;}; struct InvoiceEvent{std::string id;Date date;EventKind kind;}; struct ContactPolicy{int reminder_days;int escalation_days;}; struct ContactAction{EventKind kind;Date date;}; struct ContactPlan{bool valid=false;bool terminal=false;std::vector<ContactAction> actions;}; ContactPlan plan_contacts(const Invoice&,const std::vector<InvoiceEvent>&,ContactPolicy); }
""",
        r"""#include "task.h"
#include <algorithm>
#include <limits>
#include <set>
namespace curriculum { namespace { bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);} int dim(int y,int m){static int d[]={31,28,31,30,31,30,31,31,30,31,30,31};return m==2?d[1]+leap(y):(m>0&&m<13?d[m-1]:0);} bool valid(Date x){return x.year>0&&x.year<10000&&x.month>0&&x.month<13&&x.day>0&&x.day<=dim(x.year,x.month);} long long serial(Date x){long long y=x.year-1,n=365*y+y/4-y/100+y/400;for(int m=1;m<x.month;++m)n+=dim(x.year,m);return n+x.day-1;} Date from(long long n){int y=1;while(n>=365+leap(y)){n-=365+leap(y);++y;}int m=1;while(n>=dim(y,m))n-=dim(y,m++);return{y,m,(int)n+1};} }
ContactPlan plan_contacts(const Invoice&i,const std::vector<InvoiceEvent>&events,ContactPolicy p){ContactPlan out;if(i.id.empty()||!valid(i.issued)||p.reminder_days<0||p.escalation_days<0)return out;long long issue=serial(i.issued),last_contact=issue,terminal_day=std::numeric_limits<long long>::max();bool had_reminder=false,had_escalation=false;std::set<std::string> ids;for(auto&e:events){if(e.id.empty()||!ids.insert(e.id).second||!valid(e.date)||serial(e.date)<issue)return out;long long day=serial(e.date);if(e.kind==EventKind::paid||e.kind==EventKind::disputed){terminal_day=std::min(terminal_day,day);}else{last_contact=std::max(last_contact,day);had_reminder|=e.kind==EventKind::contact_reminder;had_escalation|=e.kind==EventKind::contact_escalation;}}long long reminder=issue+p.reminder_days,escalation=last_contact+p.escalation_days;out.terminal=terminal_day!=std::numeric_limits<long long>::max();if(!had_reminder&&reminder<terminal_day)out.actions.push_back({EventKind::contact_reminder,from(reminder)});if(!had_escalation&&escalation<terminal_day)out.actions.push_back({EventKind::contact_escalation,from(escalation)});out.valid=true;return out;} }
""",
        r"""#include "task.h"
int main(){using namespace curriculum;auto p=plan_contacts({"i",{2024,1,1}},{{"r",{2024,1,5},EventKind::contact_reminder}},{3,7});return p.valid&&p.actions.size()==1&&p.actions[0].kind==EventKind::contact_escalation&&p.actions[0].date.day==12?0:1;}
""",
        r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto p=plan_contacts({"i",{2024,1,1}},{{"paid",{2024,1,3},EventKind::paid}}, {2,9});f+=!(p.valid&&p.terminal&&p.actions.empty());f+=plan_contacts({"i",{2024,1,1}},{{"x",{2024,1,2},EventKind::paid},{"x",{2024,1,3},EventKind::disputed}},{1,1}).valid;return f;}
""",
        "reminder<terminal_day",
        "reminder<=terminal_day",
        "terminal-day precedence suppresses actions at equality",
    ),
    FutureDateCase(
        "future-licence-renewal",
        "licence-renewal-boundaries",
        "Licence Renewal Boundaries",
        "reverse-deadline-and-state-classifier",
        "classify_renewal(Date expiry, Date as_of, RenewalRule)",
        "day<notice?RenewalState::not_open",
        r"""# Instructions

Implement `classify_renewal`. Subtract the notification lead from expiry and add the
grace and reinstatement spans with checked civil-date arithmetic. Classify `as_of`
using inclusive boundaries: notice opens on its date, ordinary renewal includes
expiry, grace begins the next day, and reinstatement begins after grace. Reject
negative spans, invalid dates, or range overflow.
""",
        r"""#pragma once
namespace curriculum { struct Date{int year,month,day;}; struct RenewalRule{int notice_lead_days;int grace_days;int reinstatement_days;}; enum class RenewalState{invalid,not_open,renewal_open,in_grace,reinstatement,expired}; struct RenewalView{RenewalState state=RenewalState::invalid;Date notice{};Date grace_end{};Date reinstatement_end{};}; RenewalView classify_renewal(Date,Date,RenewalRule); }
""",
        r"""#include "task.h"
namespace curriculum { namespace { bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}int dim(int y,int m){static int d[]={31,28,31,30,31,30,31,31,30,31,30,31};return m==2?d[1]+leap(y):(m>0&&m<13?d[m-1]:0);}bool valid(Date x){return x.year>0&&x.year<10000&&x.month>0&&x.month<13&&x.day>0&&x.day<=dim(x.year,x.month);}long long serial(Date x){long long y=x.year-1,n=365*y+y/4-y/100+y/400;for(int m=1;m<x.month;++m)n+=dim(x.year,m);return n+x.day-1;}Date from(long long n){int y=1;while(n>=365+leap(y)){n-=365+leap(y);++y;}int m=1;while(n>=dim(y,m))n-=dim(y,m++);return{y,m,(int)n+1};}}
RenewalView classify_renewal(Date expiry,Date as_of,RenewalRule r){RenewalView out;if(!valid(expiry)||!valid(as_of)||r.notice_lead_days<0||r.grace_days<0||r.reinstatement_days<0)return out;long long end=serial(expiry),notice=end-r.notice_lead_days,grace=end+r.grace_days,reinstatement=grace+r.reinstatement_days;if(notice<0||reinstatement>serial({9999,12,31}))return out;out.notice=from(notice);out.grace_end=from(grace);out.reinstatement_end=from(reinstatement);long long day=serial(as_of);out.state=day<notice?RenewalState::not_open:day<=end?RenewalState::renewal_open:day<=grace?RenewalState::in_grace:day<=reinstatement?RenewalState::reinstatement:RenewalState::expired;return out;} }
""",
        r"""#include "task.h"
int main(){using namespace curriculum;auto r=classify_renewal({2024,3,1},{2024,3,1},{1,2,3});return r.state==RenewalState::renewal_open&&r.notice.month==2&&r.notice.day==29?0:1;}
""",
        r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto a=classify_renewal({2024,1,31},{2024,2,1},{10,1,1});f+=a.state!=RenewalState::in_grace;auto b=classify_renewal({1,1,1},{1,1,1},{1,0,0});f+=b.state!=RenewalState::invalid;return f;}
""",
        "day<=grace?RenewalState::in_grace",
        "day<grace?RenewalState::in_grace",
        "include the grace-end equality boundary",
    ),
    FutureDateCase(
        "future-lab-sample",
        "sample-stability-ledger",
        "Sample Stability Ledger",
        "interval-union-penalty-ledger",
        "forecast_stability(Sample, interruptions, base_days, warning_lead)",
        "merged.back().second+1",
        r"""# Instructions

Implement `forecast_stability`. Interruption IDs are unique and intervals are
inclusive, valid, and not before collection. Merge overlapping or adjacent intervals
before counting unstable days; overlapping records must not double-charge viability.
Subtract the merged-day total from base viability, then compute warning and discard
dates. Reject a nonpositive remaining lifetime or invalid input atomically.
""",
        r"""#pragma once
#include <string>
#include <vector>
namespace curriculum { struct Date{int year,month,day;}; struct Sample{std::string id;Date collected;}; struct Interruption{std::string id;Date first,last;}; struct StabilityForecast{bool valid=false;int unstable_days=0;Date warning{};Date discard{};}; StabilityForecast forecast_stability(const Sample&,const std::vector<Interruption>&,int,int); }
""",
        r"""#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum { namespace { bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}int dim(int y,int m){static int d[]={31,28,31,30,31,30,31,31,30,31,30,31};return m==2?d[1]+leap(y):(m>0&&m<13?d[m-1]:0);}bool valid(Date x){return x.year>0&&x.year<10000&&x.month>0&&x.month<13&&x.day>0&&x.day<=dim(x.year,x.month);}long long serial(Date x){long long y=x.year-1,n=365*y+y/4-y/100+y/400;for(int m=1;m<x.month;++m)n+=dim(x.year,m);return n+x.day-1;}Date from(long long n){int y=1;while(n>=365+leap(y)){n-=365+leap(y);++y;}int m=1;while(n>=dim(y,m))n-=dim(y,m++);return{y,m,(int)n+1};}}
StabilityForecast forecast_stability(const Sample&s,const std::vector<Interruption>&xs,int base_days,int warning_lead){StabilityForecast out;if(s.id.empty()||!valid(s.collected)||base_days<=0||warning_lead<0)return out;std::set<std::string> ids;std::vector<std::pair<long long,long long>> spans;for(auto&x:xs){if(x.id.empty()||!ids.insert(x.id).second||!valid(x.first)||!valid(x.last)||serial(x.first)<serial(s.collected)||serial(x.last)<serial(x.first))return out;spans.push_back({serial(x.first),serial(x.last)});}std::sort(spans.begin(),spans.end());std::vector<std::pair<long long,long long>> merged;for(auto span:spans){if(merged.empty()||span.first>merged.back().second+1)merged.push_back(span);else merged.back().second=std::max(merged.back().second,span.second);}for(auto [a,b]:merged)out.unstable_days+=(int)(b-a+1);int remaining=base_days-out.unstable_days;if(remaining<=0||warning_lead>remaining)return StabilityForecast{};long long discard=serial(s.collected)+remaining;out.discard=from(discard);out.warning=from(discard-warning_lead);out.valid=true;return out;} }
""",
        r"""#include "task.h"
int main(){using namespace curriculum;auto f=forecast_stability({"s",{2024,2,27}},{{"a",{2024,2,28},{2024,2,29}},{"b",{2024,2,29},{2024,3,1}}},10,2);return f.valid&&f.unstable_days==3&&f.discard.month==3&&f.discard.day==5?0:1;}
""",
        r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto x=forecast_stability({"s",{2024,1,1}},{{"a",{2024,1,2},{2024,1,2}},{"b",{2024,1,3},{2024,1,3}}},5,1);f+=!(x.valid&&x.unstable_days==2);f+=forecast_stability({"s",{2024,1,2}},{{"x",{2024,1,1},{2024,1,1}}},5,1).valid;return f;}
""",
        "span.first>merged.back().second+1",
        "span.first>merged.back().second-1",
        "merge overlaps without double-charging shared days",
    ),
    FutureDateCase(
        "future-construction-deadline",
        "construction-phase-network",
        "Construction Phase Network",
        "topological-longest-path-with-closures",
        "schedule_phases(Date, phases, amendments, closures)",
        "ready.insert(next)",
        r"""# Instructions

Implement `schedule_phases`. Phase IDs are unique, durations are positive, and every
dependency names a phase. Amendments add nonnegative days to exactly one phase and
have unique IDs. Schedule the dependency DAG in lexicographic ready order; each phase
starts after the latest dependency and its inclusive finish is extended once for each
closure day it crosses. Reject cycles and all invalid input without partial output.
""",
        r"""#pragma once
#include <string>
#include <vector>
namespace curriculum { struct Date{int year,month,day;}; struct Phase{std::string id;int duration_days;std::vector<std::string> depends_on;}; struct Amendment{std::string id,phase;int extra_days;}; struct PhaseFinish{std::string phase;Date finish;}; struct NetworkSchedule{bool valid=false;std::vector<PhaseFinish> finishes;}; NetworkSchedule schedule_phases(Date,const std::vector<Phase>&,const std::vector<Amendment>&,const std::vector<Date>&); }
""",
        r"""#include "task.h"
#include <algorithm>
#include <map>
#include <set>
namespace curriculum { namespace { bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}int dim(int y,int m){static int d[]={31,28,31,30,31,30,31,31,30,31,30,31};return m==2?d[1]+leap(y):(m>0&&m<13?d[m-1]:0);}bool valid(Date x){return x.year>0&&x.year<10000&&x.month>0&&x.month<13&&x.day>0&&x.day<=dim(x.year,x.month);}long long serial(Date x){long long y=x.year-1,n=365*y+y/4-y/100+y/400;for(int m=1;m<x.month;++m)n+=dim(x.year,m);return n+x.day-1;}Date from(long long n){int y=1;while(n>=365+leap(y)){n-=365+leap(y);++y;}int m=1;while(n>=dim(y,m))n-=dim(y,m++);return{y,m,(int)n+1};}}
NetworkSchedule schedule_phases(Date start,const std::vector<Phase>&phases,const std::vector<Amendment>&amendments,const std::vector<Date>&closures){NetworkSchedule out;if(!valid(start))return out;std::map<std::string,Phase> by;std::map<std::string,int> indegree,extra;std::map<std::string,std::vector<std::string>> next;for(auto&p:phases)if(p.id.empty()||p.duration_days<=0||!by.emplace(p.id,p).second)return out;for(auto&p:phases)for(auto&d:p.depends_on){if(!by.count(d)||d==p.id)return out;++indegree[p.id];next[d].push_back(p.id);}std::set<std::string> amendment_ids;for(auto&a:amendments)if(a.id.empty()||!amendment_ids.insert(a.id).second||!by.count(a.phase)||a.extra_days<0)return out;else extra[a.phase]+=a.extra_days;std::set<long long> shut;for(Date d:closures)if(!valid(d)||!shut.insert(serial(d)).second)return out;std::set<std::string> ready;for(auto&[id,p]:by)if(indegree[id]==0)ready.insert(id);std::map<std::string,long long> finish;while(!ready.empty()){std::string id=*ready.begin();ready.erase(ready.begin());long long begin=serial(start);for(auto&dep:by[id].depends_on)begin=std::max(begin,finish[dep]+1);long long end=begin+by[id].duration_days+extra[id]-1;for(long long day=begin;day<=end;++day)if(shut.count(day))++end;if(end>serial({9999,12,31}))return NetworkSchedule{};finish[id]=end;out.finishes.push_back({id,from(end)});for(auto&child:next[id])if(--indegree[child]==0)ready.insert(child);}if(out.finishes.size()!=phases.size())return NetworkSchedule{};out.valid=true;return out;} }
""",
        r"""#include "task.h"
int main(){using namespace curriculum;auto s=schedule_phases({2024,1,1},{{"foundation",2,{}},{"frame",3,{"foundation"}}},{{"a","frame",1}},{{2024,1,2}});return s.valid&&s.finishes.size()==2&&s.finishes[0].finish.day==3&&s.finishes[1].finish.day==7?0:1;}
""",
        r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto s=schedule_phases({2024,1,1},{{"b",1,{}},{"a",1,{}}},{},{ });f+=!(s.valid&&s.finishes[0].phase=="a");f+=schedule_phases({2024,1,1},{{"a",1,{"b"}},{"b",1,{"a"}}},{},{}).valid;return f;}
""",
        "ready.insert(child)",
        "ready.insert(id)",
        "release the newly unblocked successor rather than the completed phase",
    ),
    FutureDateCase(
        "future-vaccine-series",
        "vaccine-eligibility-window",
        "Vaccine Eligibility Window",
        "validated-dose-history-window",
        "next_dose_window(Date today, history, rules, catch_up)",
        "std::stable_sort(doses.begin(),doses.end()",
        r"""# Instructions

Implement `next_dose_window`. Validate unique dose IDs, one product, valid dates not
after `today`, and a strictly increasing history after stable date ordering. Rule
index equals doses already received; each rule has `0 <= minimum <= maximum`.
Catch-up shortens only the minimum by its documented reduction, never below zero.
Return earliest/latest dates from the last dose, or `complete=true` when no rule
remains. Invalid history returns no window.
""",
        r"""#pragma once
#include <string>
#include <vector>
namespace curriculum { struct Date{int year,month,day;}; struct Dose{std::string id,product;Date given;}; struct IntervalRule{int minimum_days,maximum_days,catchup_reduction;}; struct DoseWindow{bool valid=false;bool complete=false;Date earliest{},latest{};int next_number=0;}; DoseWindow next_dose_window(Date,std::vector<Dose>,const std::vector<IntervalRule>&,bool); }
""",
        r"""#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum { namespace { bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}int dim(int y,int m){static int d[]={31,28,31,30,31,30,31,31,30,31,30,31};return m==2?d[1]+leap(y):(m>0&&m<13?d[m-1]:0);}bool valid(Date x){return x.year>0&&x.year<10000&&x.month>0&&x.month<13&&x.day>0&&x.day<=dim(x.year,x.month);}long long serial(Date x){long long y=x.year-1,n=365*y+y/4-y/100+y/400;for(int m=1;m<x.month;++m)n+=dim(x.year,m);return n+x.day-1;}Date from(long long n){int y=1;while(n>=365+leap(y)){n-=365+leap(y);++y;}int m=1;while(n>=dim(y,m))n-=dim(y,m++);return{y,m,(int)n+1};}}
DoseWindow next_dose_window(Date today,std::vector<Dose>doses,const std::vector<IntervalRule>&rules,bool catch_up){DoseWindow out;if(!valid(today))return out;for(auto&r:rules)if(r.minimum_days<0||r.maximum_days<r.minimum_days||r.catchup_reduction<0)return out;std::set<std::string> ids;std::string product;for(auto&d:doses){if(d.id.empty()||!ids.insert(d.id).second||d.product.empty()||!valid(d.given)||serial(d.given)>serial(today))return out;if(product.empty())product=d.product;else if(product!=d.product)return out;}std::stable_sort(doses.begin(),doses.end(),[](auto&a,auto&b){return serial(a.given)<serial(b.given);});for(std::size_t i=1;i<doses.size();++i)if(serial(doses[i-1].given)>=serial(doses[i].given))return out;out.next_number=(int)doses.size()+1;if(doses.size()>=rules.size()){out.valid=true;out.complete=true;return out;}long long base=doses.empty()?serial(today):serial(doses.back().given);auto r=rules[doses.size()];int minimum=catch_up?std::max(0,r.minimum_days-r.catchup_reduction):r.minimum_days;if(base+r.maximum_days>serial({9999,12,31}))return out;out.earliest=from(base+minimum);out.latest=from(base+r.maximum_days);out.valid=true;return out;} }
""",
        r"""#include "task.h"
int main(){using namespace curriculum;auto w=next_dose_window({2024,2,20},{{"d1","p",{2024,2,1}}},{{0,0,0},{28,35,7}},true);return w.valid&&!w.complete&&w.next_number==2&&w.earliest.month==2&&w.earliest.day==22?0:1;}
""",
        r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto w=next_dose_window({2024,3,1},{{"b","p",{2024,2,2}},{"a","p",{2024,2,1}}},{{1,2,0},{2,3,1},{4,5,1}},false);f+=!(w.valid&&w.next_number==3);f+=next_dose_window({2024,3,1},{{"a","p",{2024,2,1}},{"b","q",{2024,2,2}}},{{1,2,0},{2,3,0}},false).valid;return f;}
""",
        "else if(product!=d.product)",
        "else if(product==d.product)",
        "reject mixed products while retaining a same-product series",
    ),
    FutureDateCase(
        "future-equipment-calibration",
        "calibration-trigger-forecast",
        "Calibration Trigger Forecast",
        "usage-rate-projection-versus-calendar",
        "forecast_calibration(Date installed, readings, policy)",
        "usage_days=(remaining+rate-1)/rate",
        r"""# Instructions

Implement `forecast_calibration`. Readings have unique IDs, strictly increasing dates
and nondecreasing usage. Estimate an integer daily usage rate as ceiling of usage
growth divided by elapsed days between the first and last reading. Project the day
the usage limit is reached and compare it with the fixed calendar limit from
installation; the earlier date wins and equality reports `both`. Reject stale,
overflowing, or insufficient readings atomically.
""",
        r"""#pragma once
#include <string>
#include <vector>
namespace curriculum { struct Date{int year,month,day;}; struct UsageReading{std::string id;Date date;int units;}; struct CalibrationPolicy{int calendar_days;int usage_limit;}; enum class Trigger{invalid,calendar,usage,both}; struct CalibrationForecast{Trigger trigger=Trigger::invalid;Date due{};int daily_rate=0;}; CalibrationForecast forecast_calibration(Date,const std::vector<UsageReading>&,CalibrationPolicy); }
""",
        r"""#include "task.h"
#include <set>
namespace curriculum { namespace { bool leap(int y){return y%4==0&&(y%100!=0||y%400==0);}int dim(int y,int m){static int d[]={31,28,31,30,31,30,31,31,30,31,30,31};return m==2?d[1]+leap(y):(m>0&&m<13?d[m-1]:0);}bool valid(Date x){return x.year>0&&x.year<10000&&x.month>0&&x.month<13&&x.day>0&&x.day<=dim(x.year,x.month);}long long serial(Date x){long long y=x.year-1,n=365*y+y/4-y/100+y/400;for(int m=1;m<x.month;++m)n+=dim(x.year,m);return n+x.day-1;}Date from(long long n){int y=1;while(n>=365+leap(y)){n-=365+leap(y);++y;}int m=1;while(n>=dim(y,m))n-=dim(y,m++);return{y,m,(int)n+1};}}
CalibrationForecast forecast_calibration(Date installed,const std::vector<UsageReading>&readings,CalibrationPolicy p){CalibrationForecast out;if(!valid(installed)||p.calendar_days<=0||p.usage_limit<=0||readings.size()<2)return out;std::set<std::string> ids;for(std::size_t i=0;i<readings.size();++i){auto&r=readings[i];if(r.id.empty()||!ids.insert(r.id).second||!valid(r.date)||serial(r.date)<serial(installed)||r.units<0)return out;if(i&&(serial(readings[i-1].date)>=serial(r.date)||readings[i-1].units>r.units))return out;}auto&a=readings.front();auto&b=readings.back();long long elapsed=serial(b.date)-serial(a.date),growth=b.units-a.units;if(growth<=0||b.units>=p.usage_limit)return out;int rate=(int)((growth+elapsed-1)/elapsed);int remaining=p.usage_limit-b.units;long long usage_days=(remaining+rate-1)/rate;long long usage_due=serial(b.date)+usage_days,calendar_due=serial(installed)+p.calendar_days;if(usage_due>serial({9999,12,31})||calendar_due>serial({9999,12,31}))return out;long long due=usage_due<calendar_due?usage_due:calendar_due;out.trigger=usage_due<calendar_due?Trigger::usage:calendar_due<usage_due?Trigger::calendar:Trigger::both;out.due=from(due);out.daily_rate=rate;return out;} }
""",
        r"""#include "task.h"
int main(){using namespace curriculum;auto f=forecast_calibration({2024,1,1},{{"a",{2024,1,2},10},{"b",{2024,1,5},19}},{30,40});return f.trigger==Trigger::usage&&f.daily_rate==3&&f.due.day==12?0:1;}
""",
        r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto x=forecast_calibration({2024,1,1},{{"a",{2024,1,2},0},{"b",{2024,1,4},4}},{5,8});f+=!(x.trigger==Trigger::both&&x.daily_rate==2&&x.due.day==6);auto rounded=forecast_calibration({2024,1,1},{{"c",{2024,1,2},0},{"d",{2024,1,4},4}},{100,9});f+=!(rounded.trigger==Trigger::usage&&rounded.due.day==7);f+=forecast_calibration({2024,1,1},{{"a",{2024,1,2},1},{"b",{2024,1,2},2}},{5,9}).trigger!=Trigger::invalid;return f;}
""",
        "usage_days=(remaining+rate-1)/rate",
        "usage_days=remaining/rate",
        "round projected usage days upward rather than early",
    ),
)

NEGATIVE_MUTATIONS = {
    case.task_id: (case.negative_old, case.negative_new, case.negative_reason) for case in CASES
}
