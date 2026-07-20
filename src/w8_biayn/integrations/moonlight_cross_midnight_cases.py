"""Clean-room replacement cases for the cross-midnight interval family."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MidnightCase:
    legacy_id: str
    task_id: str
    title: str
    objective: str
    profile: str
    public_api: str
    instructions: str
    header: str
    starter: str
    reference: str
    visible_test: str
    hidden_test: str
    negative_old: str
    negative_new: str
    negative_reason: str


def _starter(function: str, result: str, parameters: str) -> str:
    return f'''#include "task.h"
namespace curriculum {{ {result} {function}({parameters}) {{ return {{}}; }} }}
'''


ALL_CASES = (
    MidnightCase(
        "midnight-parking-rate", "overnight-parking-ledger", "Overnight Parking Ledger",
        "Split one wrapping visit over ordered tariff bands and produce an exact per-band charge ledger.",
        "boundary-event tariff sweep", "ParkingTariff(vector<TariffBand>); price(Visit); band_count()",
        r'''# Instructions

`ParkingTariff` owns validated half-open daily tariff bands and `price` evaluates one
half-open visit. Minute
endpoints are in 0..1439; an end below its start wraps once, while equal visit endpoints
mean an empty visit. Bands must have positive distinct IDs and nonnegative rates; their
coverage may wrap but no two bands may overlap. Split the visit at band boundaries,
return one `BandCharge` per band with positive charged minutes in ascending band ID,
and set `total_cents` to the exact sum. Minutes outside all bands are free. An invalid
policy makes `band_count()` zero and every price invalid; an invalid visit also returns
`valid=false` with empty charges and zero total.
''',
        r'''#pragma once
#include <cstddef>
#include <vector>
namespace curriculum { struct Visit{int start_minute,end_minute;}; struct TariffBand{int id,start_minute,end_minute,cents_per_minute;}; struct BandCharge{int band_id,minutes,cents;bool operator==(const BandCharge&o)const{return band_id==o.band_id&&minutes==o.minutes&&cents==o.cents;}}; struct ParkingCharge{bool valid=true;int total_cents=0;std::vector<BandCharge> charges;}; class ParkingTariff{public:explicit ParkingTariff(std::vector<TariffBand>);ParkingCharge price(Visit)const;std::size_t band_count()const;private:bool valid_=false;std::vector<TariffBand> bands_;}; }
''',
        r'''#include "task.h"
#include <utility>
namespace curriculum { ParkingTariff::ParkingTariff(std::vector<TariffBand> bands):bands_(std::move(bands)){} ParkingCharge ParkingTariff::price(Visit)const{return{};}std::size_t ParkingTariff::band_count()const{return 0;} }
''',
        r'''#include "task.h"
#include <algorithm>
#include <set>
#include <utility>
namespace curriculum { namespace { bool minute(int x){return x>=0&&x<1440;} int finish(int a,int b){return b<a?b+1440:b;} }
ParkingTariff::ParkingTariff(std::vector<TariffBand> bands):bands_(std::move(bands)){std::set<int> ids;struct Piece{int id,left,right;};std::vector<Piece> pieces;for(auto b:bands_){if(b.id<=0||!ids.insert(b.id).second||!minute(b.start_minute)||!minute(b.end_minute)||b.start_minute==b.end_minute||b.cents_per_minute<0)return;int e=finish(b.start_minute,b.end_minute);for(int shift:{-1440,0,1440})pieces.push_back({b.id,b.start_minute+shift,e+shift});}for(std::size_t i=0;i<pieces.size();++i)for(std::size_t j=0;j<i;++j)if(pieces[i].id!=pieces[j].id&&std::max(pieces[i].left,pieces[j].left)<std::min(pieces[i].right,pieces[j].right))return;valid_=true;}ParkingCharge ParkingTariff::price(Visit visit)const{ParkingCharge out;if(!valid_||!minute(visit.start_minute)||!minute(visit.end_minute))return{false,0,{}};int end=finish(visit.start_minute,visit.end_minute);for(auto b:bands_){int charged=0,e=finish(b.start_minute,b.end_minute);for(int shift:{-1440,0,1440})charged+=std::max(0,std::min(end,e+shift)-std::max(visit.start_minute,b.start_minute+shift));if(charged>0){int cents=charged*b.cents_per_minute;out.total_cents+=cents;out.charges.push_back({b.id,charged,cents});}}std::sort(out.charges.begin(),out.charges.end(),[](auto a,auto b){return a.band_id<b.band_id;});return out;}std::size_t ParkingTariff::band_count()const{return valid_?bands_.size():0;} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;ParkingTariff p({{2,0,360,1},{1,1320,0,3}});auto x=p.price({1380,60});return p.band_count()==2&&x.valid&&x.total_cents==240&&x.charges==std::vector<BandCharge>{{1,60,180},{2,60,60}}?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;int f=0;ParkingTariff empty({});f+=empty.price({10,10}).total_cents!=0;ParkingTariff overlap({{1,0,30,1},{2,20,40,2}});f+=overlap.band_count()!=0||overlap.price({0,60}).valid;ParkingTariff p({{4,0,60,2}});auto x=p.price({30,90});f+=x.total_cents!=60;f+=p.price({-1,2}).valid;return f;}
''',
        "int cents=charged*b.cents_per_minute;", "int cents=b.cents_per_minute;", "charge each band once instead of by charged minutes",
    ),
    MidnightCase(
        "midnight-security-patrol", "patrol-gap-union", "Patrol Gap Union",
        "Union wrapping patrol spans inside a watch window and return maximal uncovered gaps.",
        "clipped interval union complement", "uncovered_watch(WatchWindow, vector<Patrol>) -> GapReport",
        r'''# Instructions

The nonempty half-open `WatchWindow` defines the overnight axis. Each positive-ID patrol
must be fully contained in that window after at most one midnight wrap. Clip nothing:
an outside patrol is invalid. Union overlapping or touching patrols, then return maximal
uncovered `Gap` values in chronological order relative to the watch start. Duplicate IDs,
bad endpoints, or an empty watch return `valid=false`. Empty patrol input returns the
entire watch as one gap.
''',
        r'''#pragma once
#include <vector>
namespace curriculum { struct WatchWindow{int start_minute,end_minute;}; struct Patrol{int id,start_minute,end_minute;}; struct Gap{int start_minute,end_minute;bool operator==(const Gap&o)const{return start_minute==o.start_minute&&end_minute==o.end_minute;}}; struct GapReport{bool valid=true;std::vector<Gap> gaps;}; GapReport uncovered_watch(WatchWindow,const std::vector<Patrol>&); }
''',
        _starter("uncovered_watch", "GapReport", "WatchWindow,const std::vector<Patrol>&"),
        r'''#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum { namespace { bool ok(int x){return x>=0&&x<1440;} int offset(int origin,int x){int d=x-origin;return d<0?d+1440:d;} }
GapReport uncovered_watch(WatchWindow w,const std::vector<Patrol>& ps){if(!ok(w.start_minute)||!ok(w.end_minute)||w.start_minute==w.end_minute)return{false,{}};int length=offset(w.start_minute,w.end_minute);std::set<int> ids;std::vector<std::pair<int,int>> spans;for(auto p:ps){if(p.id<=0||!ids.insert(p.id).second||!ok(p.start_minute)||!ok(p.end_minute)||p.start_minute==p.end_minute)return{false,{}};int a=offset(w.start_minute,p.start_minute),b=offset(w.start_minute,p.end_minute);if(b<=a)b+=1440;if(a<0||b>length)return{false,{}};spans.push_back({a,b});}std::sort(spans.begin(),spans.end());std::vector<std::pair<int,int>> merged;for(auto s:spans){if(merged.empty()||s.first>merged.back().second)merged.push_back(s);else merged.back().second=std::max(merged.back().second,s.second);}GapReport out;int cursor=0;for(auto s:merged){if(s.first>cursor)out.gaps.push_back({(w.start_minute+cursor)%1440,(w.start_minute+s.first)%1440});cursor=std::max(cursor,s.second);}if(cursor<length)out.gaps.push_back({(w.start_minute+cursor)%1440,w.end_minute});return out;} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto r=uncovered_watch({1320,240},{{1,1380,60},{2,60,120}});return r.valid&&r.gaps==std::vector<Gap>{{1320,1380},{120,240}}?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto r=uncovered_watch({1200,120},{{1,1200,0},{2,0,120}});f+=!r.gaps.empty();auto nested=uncovered_watch({1200,120},{{3,1200,60},{4,1300,0}});f+=nested.gaps!=std::vector<Gap>{{60,120}};f+=uncovered_watch({0,0},{}).valid;f+=uncovered_watch({1200,120},{{1,1100,0}}).valid;f+=uncovered_watch({1200,120},{{1,1300,0},{1,0,60}}).valid;return f;}
''',
        "else merged.back().second=std::max(merged.back().second,s.second);",
        "else merged.back().second=s.second;",
        "let a nested patrol shorten the merged covered interval",
    ),
    MidnightCase(
        "midnight-dock-allocation", "dock-booking-calendar", "Dock Booking Calendar",
        "Maintain per-dock overnight bookings with atomic conflict rejection and deterministic availability queries.",
        "mutable per-resource ordered calendar", "DockCalendar::reserve(Booking); DockCalendar::next_free(dock,start,duration)",
        r'''# Instructions

`DockCalendar` owns `dock_count` per-dock half-open bookings on a 0..2879 minute
overnight axis. `reserve` requires a positive unique ID, a valid dock, `0 <= start < end
<= 2880`, and rejects same-dock overlap without mutation; touching is allowed. It inserts
accepted bookings in start/ID order. `next_free` returns the earliest start at or after
the query whose positive duration fits on that dock, or `-1`; invalid queries also return
`-1`. Bookings on different docks never conflict.
''',
        r'''#pragma once
#include <vector>
namespace curriculum { struct Booking{int id,dock,start_minute,end_minute;}; struct ReserveResult{bool accepted=false;int conflict_id=-1;}; class DockCalendar{public:explicit DockCalendar(int);ReserveResult reserve(Booking);int next_free(int,int,int)const;std::vector<int> booking_ids(int)const;private:int docks_;std::vector<Booking> bookings_;}; }
''',
        r'''#include "task.h"
namespace curriculum { DockCalendar::DockCalendar(int n):docks_(n){} ReserveResult DockCalendar::reserve(Booking){return{};}int DockCalendar::next_free(int,int,int)const{return -1;}std::vector<int> DockCalendar::booking_ids(int)const{return{};} }
''',
        r'''#include "task.h"
#include <algorithm>
namespace curriculum { DockCalendar::DockCalendar(int n):docks_(n){} ReserveResult DockCalendar::reserve(Booking b){if(docks_<=0||b.id<=0||b.dock<0||b.dock>=docks_||b.start_minute<0||b.start_minute>=b.end_minute||b.end_minute>2880)return{};for(auto x:bookings_)if(x.id==b.id)return{};for(auto x:bookings_){if(x.dock!=b.dock)continue;if(std::max(x.start_minute,b.start_minute)<std::min(x.end_minute,b.end_minute))return{false,x.id};}bookings_.push_back(b);std::sort(bookings_.begin(),bookings_.end(),[](auto a,auto c){return a.dock<c.dock||(a.dock==c.dock&&(a.start_minute<c.start_minute||(a.start_minute==c.start_minute&&a.id<c.id)));});return{true,-1};}int DockCalendar::next_free(int dock,int start,int duration)const{if(dock<0||dock>=docks_||start<0||start>2880||duration<=0||duration>2880-start)return -1;int candidate=start;for(auto b:bookings_)if(b.dock==dock&&b.end_minute>candidate){if(candidate+duration<=b.start_minute)return candidate;candidate=std::max(candidate,b.end_minute);}return candidate+duration<=2880?candidate:-1;}std::vector<int> DockCalendar::booking_ids(int dock)const{std::vector<int> ids;if(dock<0||dock>=docks_)return ids;for(auto b:bookings_)if(b.dock==dock)ids.push_back(b.id);return ids;} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;DockCalendar c(2);auto a=c.reserve({7,0,1380,1500});auto b=c.reserve({8,1,1400,1450});return a.accepted&&b.accepted&&c.next_free(0,1400,30)==1500&&c.booking_ids(0)==std::vector<int>{7}?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;int f=0;DockCalendar c(2);f+=!c.reserve({1,0,100,200}).accepted;auto x=c.reserve({2,0,150,250});f+=x.accepted||x.conflict_id!=1;f+=c.booking_ids(0)!=std::vector<int>{1};f+=!c.reserve({3,0,200,220}).accepted;f+=!c.reserve({4,1,150,250}).accepted;f+=c.next_free(0,0,100)!=0;return f;}
''',
        "if(x.dock!=b.dock)continue;", "if(false)continue;", "treat bookings on every dock as one global conflict calendar",
    ),
    MidnightCase(
        "midnight-sleep-tracker", "sleep-interruption-ledger", "Sleep Interruption Ledger",
        "Measure unioned wake episodes inside a wrapping sleep session and return uninterrupted sleep blocks.",
        "clipped wake union and complement", "analyze_sleep(SleepSession, vector<WakeEpisode>) -> SleepLedger",
        r'''# Instructions

A nonempty half-open sleep session may wrap midnight once. Every positive-ID wake
episode must be nonempty and fully contained in the session; duplicate IDs invalidate.
Merge touching or overlapping wake episodes before computing `awake_minutes`, so shared
minutes are counted once. Return the remaining sleep blocks in chronological session
order using local-day endpoints. Invalid input is atomic. With no wakes, the session is
one uninterrupted block.
''',
        r'''#pragma once
#include <vector>
namespace curriculum { struct SleepSession{int start_minute,end_minute;}; struct WakeEpisode{int id,start_minute,end_minute;}; struct SleepBlock{int start_minute,end_minute;bool operator==(const SleepBlock&o)const{return start_minute==o.start_minute&&end_minute==o.end_minute;}}; struct SleepLedger{bool valid=true;int asleep_minutes=0,awake_minutes=0;std::vector<SleepBlock> blocks;}; SleepLedger analyze_sleep(SleepSession,const std::vector<WakeEpisode>&); }
''',
        _starter("analyze_sleep", "SleepLedger", "SleepSession,const std::vector<WakeEpisode>&"),
        r'''#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum { namespace { bool good(int x){return x>=0&&x<1440;} int rel(int s,int x){int d=x-s;return d<0?d+1440:d;} }
SleepLedger analyze_sleep(SleepSession s,const std::vector<WakeEpisode>& wakes){if(!good(s.start_minute)||!good(s.end_minute)||s.start_minute==s.end_minute)return{false,0,0,{}};int length=rel(s.start_minute,s.end_minute);std::set<int> ids;std::vector<std::pair<int,int>> v;for(auto w:wakes){if(w.id<=0||!ids.insert(w.id).second||!good(w.start_minute)||!good(w.end_minute)||w.start_minute==w.end_minute)return{false,0,0,{}};int a=rel(s.start_minute,w.start_minute),b=rel(s.start_minute,w.end_minute);if(b<=a)b+=1440;if(b>length)return{false,0,0,{}};v.push_back({a,b});}std::sort(v.begin(),v.end());std::vector<std::pair<int,int>> u;for(auto x:v){if(u.empty()||x.first>u.back().second)u.push_back(x);else u.back().second=std::max(u.back().second,x.second);}SleepLedger out;int cursor=0;for(auto x:u){if(cursor<x.first)out.blocks.push_back({(s.start_minute+cursor)%1440,(s.start_minute+x.first)%1440});out.awake_minutes+=x.second-x.first;cursor=x.second;}if(cursor<length)out.blocks.push_back({(s.start_minute+cursor)%1440,s.end_minute});out.asleep_minutes=length-out.awake_minutes;return out;} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto x=analyze_sleep({1380,420},{{1,30,60},{2,50,90}});return x.valid&&x.awake_minutes==60&&x.asleep_minutes==420&&x.blocks==std::vector<SleepBlock>{{1380,30},{90,420}}?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto x=analyze_sleep({1200,0},{});f+=x.blocks!=std::vector<SleepBlock>{{1200,0}}||x.asleep_minutes!=240;f+=analyze_sleep({1200,60},{{1,1100,30}}).valid;f+=analyze_sleep({1,1},{}).valid;f+=analyze_sleep({1200,60},{{1,1300,0},{1,0,30}}).valid;return f;}
''',
        "else u.back().second=std::max(u.back().second,x.second);", "else u.push_back(x);", "sum overlapping wake episodes instead of their union",
    ),
    MidnightCase(
        "midnight-radio-silence", "quiet-window-violations", "Quiet Window Violations",
        "Classify transmission points against multiple quiet windows and return stable violation evidence.",
        "stable point-membership window scan", "SilencePolicy(vector<QuietWindow>); audit(vector<Transmission>)",
        r'''# Instructions

`SilencePolicy` owns nonempty half-open daily quiet windows that may wrap once. Window IDs and
transmission IDs are positive and unique within their collections. For each transmission
in input order, report one violation using the smallest matching window ID; a point at a
window start violates, while a point at its end does not. Invalid IDs/endpoints invalidate
the policy or complete audit. `valid_policy()` reports constructor validity. Empty inputs
are valid.
''',
        r'''#pragma once
#include <vector>
namespace curriculum { struct QuietWindow{int id,start_minute,end_minute;}; struct Transmission{int id,minute;}; struct Violation{int transmission_id,window_id;bool operator==(const Violation&o)const{return transmission_id==o.transmission_id&&window_id==o.window_id;}}; struct SilenceAudit{bool valid=true;std::vector<Violation> violations;}; class SilencePolicy{public:explicit SilencePolicy(std::vector<QuietWindow>);bool valid_policy()const;SilenceAudit audit(const std::vector<Transmission>&)const;private:bool valid_=false;std::vector<QuietWindow> windows_;}; }
''',
        r'''#include "task.h"
#include <utility>
namespace curriculum { SilencePolicy::SilencePolicy(std::vector<QuietWindow> w):windows_(std::move(w)){}bool SilencePolicy::valid_policy()const{return false;}SilenceAudit SilencePolicy::audit(const std::vector<Transmission>&)const{return{};} }
''',
        r'''#include "task.h"
#include <algorithm>
#include <set>
#include <utility>
namespace curriculum { namespace { bool minute(int x){return x>=0&&x<1440;} bool contains(QuietWindow w,int x){return w.start_minute<w.end_minute?(x>=w.start_minute&&x<w.end_minute):(x>=w.start_minute||x<w.end_minute);} }
SilencePolicy::SilencePolicy(std::vector<QuietWindow> windows):windows_(std::move(windows)){std::set<int> ids;for(auto w:windows_)if(w.id<=0||!ids.insert(w.id).second||!minute(w.start_minute)||!minute(w.end_minute)||w.start_minute==w.end_minute)return;valid_=true;}bool SilencePolicy::valid_policy()const{return valid_;}SilenceAudit SilencePolicy::audit(const std::vector<Transmission>& transmissions)const{if(!valid_)return{false,{}};std::set<int> ids;for(auto t:transmissions)if(t.id<=0||!ids.insert(t.id).second||!minute(t.minute))return{false,{}};SilenceAudit out;for(auto t:transmissions){int selected=-1;for(auto w:windows_)if(contains(w,t.minute)&&(selected<0||w.id<selected))selected=w.id;if(selected>0)out.violations.push_back({t.id,selected});}return out;} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;SilencePolicy p({{9,1320,360},{3,0,60}});auto a=p.audit({{1,30},{2,360},{3,1320}});return p.valid_policy()&&a.valid&&a.violations==std::vector<Violation>{{1,3},{3,9}}?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;int f=0;SilencePolicy p({{2,100,200}});auto a=p.audit({{7,100},{8,199},{9,200}});f+=a.violations.size()!=2;SilencePolicy invalid({{1,0,0}});f+=invalid.valid_policy()||invalid.audit({}).valid;SilencePolicy empty({});f+=!empty.valid_policy()||empty.audit({{1,10},{1,20}}).valid;return f;}
''',
        "return w.start_minute<w.end_minute?(x>=w.start_minute&&x<w.end_minute):(x>=w.start_minute||x<w.end_minute);",
        "return w.start_minute<w.end_minute?(x>=w.start_minute&&x<=w.end_minute):(x>=w.start_minute||x<=w.end_minute);",
        "treat the half-open quiet-window end as a violation",
    ),
    MidnightCase(
        "midnight-bakery-oven", "oven-capacity-scheduler", "Oven Capacity Scheduler",
        "Assign overnight batches to the lowest available oven while respecting release order and capacity.",
        "two-heap interval partitioning", "schedule_batches(int, vector<Batch>) -> BakeSchedule",
        r'''# Instructions

Batch release minutes are a caller-ordered overnight sequence: at most one decrease is
the midnight wrap. IDs are positive and unique, durations are positive and at most one
day, and oven count is positive. Process batches in input order. Release every oven whose
finish is at or before the batch release, assign the smallest free oven, or return
`valid=false` atomically when capacity is exhausted. Output assignments in input order
with unwrapped start/end minutes.
''',
        r'''#pragma once
#include <vector>
namespace curriculum { struct Batch{int id,release_minute,duration;}; struct OvenAssignment{int batch_id,oven,start_minute,end_minute;bool operator==(const OvenAssignment&o)const{return batch_id==o.batch_id&&oven==o.oven&&start_minute==o.start_minute&&end_minute==o.end_minute;}}; struct BakeSchedule{bool valid=true;std::vector<OvenAssignment> assignments;}; BakeSchedule schedule_batches(int,const std::vector<Batch>&); }
''',
        _starter("schedule_batches", "BakeSchedule", "int,const std::vector<Batch>&"),
        r'''#include "task.h"
#include <functional>
#include <queue>
#include <set>
namespace curriculum { BakeSchedule schedule_batches(int oven_count,const std::vector<Batch>& batches){if(oven_count<=0)return{false,{}};std::set<int> ids;std::priority_queue<int,std::vector<int>,std::greater<int>> free;for(int i=0;i<oven_count;++i)free.push(i);using Busy=std::pair<int,int>;std::priority_queue<Busy,std::vector<Busy>,std::greater<Busy>> busy;BakeSchedule out;int day=0,previous=-1;for(auto b:batches){if(b.id<=0||!ids.insert(b.id).second||b.release_minute<0||b.release_minute>=1440||b.duration<=0||b.duration>1440)return{false,{}};if(previous>=0&&b.release_minute<previous){if(day!=0)return{false,{}};day=1440;}previous=b.release_minute;int release=day+b.release_minute;while(!busy.empty()&&busy.top().first<=release){free.push(busy.top().second);busy.pop();}if(free.empty())return{false,{}};int oven=free.top();free.pop();int end=release+b.duration;busy.push({end,oven});out.assignments.push_back({b.id,oven,release,end});}return out;} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto s=schedule_batches(2,{{1,1380,90},{2,1400,30},{3,30,20}});return s.valid&&s.assignments==std::vector<OvenAssignment>{{1,0,1380,1470},{2,1,1400,1430},{3,0,1470,1490}}?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto a=schedule_batches(1,{{1,100,50},{2,150,20}});f+=!a.valid||a.assignments[1].oven!=0;f+=schedule_batches(1,{{1,100,60},{2,120,10}}).valid;f+=schedule_batches(2,{{1,100,1},{1,101,1}}).valid;f+=schedule_batches(0,{}).valid;return f;}
''',
        "while(!busy.empty()&&busy.top().first<=release)", "while(!busy.empty()&&busy.top().first<release)", "keep an oven busy at a touching half-open endpoint",
    ),
    MidnightCase(
        "midnight-transit-pass", "transit-entitlement-audit", "Transit Entitlement Audit",
        "Prove complete trip coverage by a pass after subtracting blackout intervals and applying end-only grace.",
        "entitlement interval subtraction", "check_entitlement(PassWindow, Trip, vector<Blackout>) -> Entitlement",
        r'''# Instructions

Pass and trip are nonempty half-open local-day intervals that may wrap once. Grace is
nonnegative and extends only the unwrapped pass end, never beyond minute 2880. Blackouts
are nonempty, must lie inside the unextended pass, and remove coverage. The trip is
covered only when every one of its minutes lies in the pass-plus-grace and outside every
blackout. Return the first uncovered local-day minute, or `-1` when covered. Invalid or
multi-cycle input returns `valid=false`; exact half-open endpoints are excluded.
''',
        r'''#pragma once
#include <vector>
namespace curriculum { struct PassWindow{int start_minute,end_minute,grace_minutes;}; struct Trip{int start_minute,end_minute;}; struct Blackout{int start_minute,end_minute;}; struct Entitlement{bool valid=true,covered=false;int first_uncovered_minute=-1;}; Entitlement check_entitlement(PassWindow,Trip,const std::vector<Blackout>&); }
''',
        _starter("check_entitlement", "Entitlement", "PassWindow,Trip,const std::vector<Blackout>&"),
        r'''#include "task.h"
#include <algorithm>
namespace curriculum { namespace { bool ok(int x){return x>=0&&x<1440;} int end_after(int a,int b){return b<=a?b+1440:b;} int align(int origin,int x){return x<origin?x+1440:x;} }
Entitlement check_entitlement(PassWindow p,Trip t,const std::vector<Blackout>& blackouts){if(!ok(p.start_minute)||!ok(p.end_minute)||p.start_minute==p.end_minute||p.grace_minutes<0||!ok(t.start_minute)||!ok(t.end_minute)||t.start_minute==t.end_minute)return{false,false,-1};int pe=end_after(p.start_minute,p.end_minute);if(pe+p.grace_minutes>2880)return{false,false,-1};int ts=align(p.start_minute,t.start_minute),te=end_after(ts,t.end_minute);if(te>2880)return{false,false,-1};std::vector<std::pair<int,int>> cuts;for(auto b:blackouts){if(!ok(b.start_minute)||!ok(b.end_minute)||b.start_minute==b.end_minute)return{false,false,-1};int a=align(p.start_minute,b.start_minute),e=end_after(a,b.end_minute);if(a<p.start_minute||e>pe)return{false,false,-1};cuts.push_back({a,e});}for(int minute=ts;minute<te;++minute){bool allowed=minute>=p.start_minute&&minute<pe+p.grace_minutes;for(auto cut:cuts)if(minute>=cut.first&&minute<cut.second)allowed=false;if(!allowed)return{true,false,minute%1440};}return{true,true,-1};} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto e=check_entitlement({1320,120,30},{1380,150},{});return e.valid&&e.covered?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto e=check_entitlement({1320,120,30},{1380,90},{{0,30}});f+=!e.valid||e.covered||e.first_uncovered_minute!=0;f+=check_entitlement({0,60,0},{0,60},{{50,70}}).valid;f+=check_entitlement({0,60,-1},{0,10},{}).valid;return f;}
''',
        "if(minute>=cut.first&&minute<cut.second)allowed=false;", "if(minute>=cut.first&&minute<cut.first)allowed=false;", "ignore every interior blackout while checking only pass endpoints",
    ),
    MidnightCase(
        "midnight-hospital-handoff", "handoff-continuity-audit", "Handoff Continuity Audit",
        "Audit a caller-ordered overnight shift chain for overlap, gaps, and its first unsafe handoff.",
        "adjacent continuity state accumulation", "HandoffChain(int); append(Shift); audit()",
        r'''# Instructions

`HandoffChain` incrementally owns caller-ordered shifts with positive unique IDs and nonempty half-open daily
intervals. Normalize at most one midnight wrap in the sequence; starts must remain
nondecreasing after normalization, so `append` must not sort and rejects invalid input
without mutation. For every adjacent pair, `audit`
record positive overlap or positive gap minutes. A handoff is safe when overlap is at least
`required_overlap`; equality is safe. Return the first unsafe predecessor ID. Invalid input
or a negative constructor threshold is reported deterministically; zero or one shift is safe.
''',
        r'''#pragma once
#include <vector>
namespace curriculum { struct Shift{int id,start_minute,end_minute;}; struct Handoff{int from_id,to_id,overlap_minutes,gap_minutes;bool operator==(const Handoff&o)const{return from_id==o.from_id&&to_id==o.to_id&&overlap_minutes==o.overlap_minutes&&gap_minutes==o.gap_minutes;}}; struct HandoffAudit{bool valid=true,safe=true;int first_unsafe_id=-1;std::vector<Handoff> handoffs;}; class HandoffChain{public:explicit HandoffChain(int);bool append(Shift);HandoffAudit audit()const;private:int required_;int previous_start_=-1;bool wrapped_=false;std::vector<Shift> shifts_;}; }
''',
        r'''#include "task.h"
namespace curriculum { HandoffChain::HandoffChain(int required):required_(required){}bool HandoffChain::append(Shift){return false;}HandoffAudit HandoffChain::audit()const{return{};} }
''',
        r'''#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum { HandoffChain::HandoffChain(int required):required_(required){}bool HandoffChain::append(Shift s){if(required_<0||s.id<=0||s.start_minute<0||s.start_minute>=1440||s.end_minute<0||s.end_minute>=1440||s.start_minute==s.end_minute)return false;for(auto old:shifts_)if(old.id==s.id)return false;bool next_wrap=wrapped_;if(previous_start_>=0&&s.start_minute<previous_start_){if(wrapped_)return false;next_wrap=true;}shifts_.push_back(s);previous_start_=s.start_minute;wrapped_=next_wrap;return true;}HandoffAudit HandoffChain::audit()const{if(required_<0)return{false,false,-1,{}};struct Linear{int id,start,end;};std::vector<Linear> v;int day=0,previous=-1;for(auto s:shifts_){if(previous>=0&&s.start_minute<previous)day=1440;int start=day+s.start_minute,end=day+s.end_minute;if(end<=start)end+=1440;v.push_back({s.id,start,end});previous=s.start_minute;}HandoffAudit out;for(std::size_t i=1;i<v.size();++i){int overlap=std::max(0,v[i-1].end-v[i].start),gap=std::max(0,v[i].start-v[i-1].end);out.handoffs.push_back({v[i-1].id,v[i].id,overlap,gap});if(overlap<required_&&out.safe){out.safe=false;out.first_unsafe_id=v[i-1].id;}}return out;} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;HandoffChain c(30);bool ok=c.append({1,1320,30})&&c.append({2,0,120});auto a=c.audit();return ok&&a.valid&&a.safe&&a.handoffs==std::vector<Handoff>{{1,2,30,0}}?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;int f=0;HandoffChain c(1);f+=!c.append({1,1380,30})||!c.append({2,60,120});auto a=c.audit();f+=a.safe||a.first_unsafe_id!=1||a.handoffs[0].gap_minutes!=30;auto before=a.handoffs;f+=c.append({3,40,60});f+=c.audit().handoffs!=before;HandoffChain dup(0);f+=!dup.append({1,0,10})||dup.append({1,10,20});HandoffChain invalid(-1);f+=invalid.append({1,0,10})||invalid.audit().valid;return f;}
''',
        "if(overlap<required_&&out.safe)", "if(overlap<=required_&&out.safe)", "treat equality with the required overlap as unsafe",
    ),
    MidnightCase(
        "midnight-noise-budget", "noise-budget-breach", "Noise Budget Breach",
        "Charge unique protected minutes incrementally and identify the operation causing the first budget breach.",
        "incremental protected-minute bitmap", "NoiseMeter(int, vector<ProtectedBand>); record(NoiseOperation); report(); reset()",
        r'''# Instructions

`NoiseMeter` owns a nonnegative budget and nonempty half-open daily protected bands that
may wrap once. `record` accepts nonempty operations with positive unique IDs in call order;
charge only protected minutes not already charged by an earlier operation, so overlapping
noise is never double-counted. `report` returns cumulative unique charged minutes and the first
operation whose marginal minutes make the total strictly exceed the nonnegative budget.
Invalid construction makes every record fail and the report invalid. Invalid or duplicate
records do not mutate state. Equality with the budget is allowed. `reset` clears operations
and charged minutes but preserves the policy.
''',
        r'''#pragma once
#include <array>
#include <set>
#include <vector>
namespace curriculum { struct ProtectedBand{int start_minute,end_minute;}; struct NoiseOperation{int id,start_minute,end_minute;}; struct NoiseAudit{bool valid=true,within_budget=true;int charged_minutes=0,breach_operation_id=-1;std::vector<int> marginal_minutes;}; class NoiseMeter{public:NoiseMeter(int,std::vector<ProtectedBand>);bool record(NoiseOperation);NoiseAudit report()const;void reset();private:int budget_;bool valid_=false;std::array<bool,1440> protected_{};std::array<bool,1440> charged_{};std::set<int> ids_;NoiseAudit report_;}; }
''',
        r'''#include "task.h"
namespace curriculum { NoiseMeter::NoiseMeter(int budget,std::vector<ProtectedBand>):budget_(budget){}bool NoiseMeter::record(NoiseOperation){return false;}NoiseAudit NoiseMeter::report()const{return{};}void NoiseMeter::reset(){} }
''',
        r'''#include "task.h"
namespace curriculum { namespace { bool ok(int x){return x>=0&&x<1440;} template<class F> void each(int a,int b,F f){if(a<b){for(int x=a;x<b;++x)f(x);}else{for(int x=a;x<1440;++x)f(x);for(int x=0;x<b;++x)f(x);}} }
NoiseMeter::NoiseMeter(int budget,std::vector<ProtectedBand> bands):budget_(budget){if(budget_<0)return;for(auto b:bands){if(!ok(b.start_minute)||!ok(b.end_minute)||b.start_minute==b.end_minute)return;each(b.start_minute,b.end_minute,[&](int x){protected_[x]=true;});}valid_=true;report_.valid=true;}bool NoiseMeter::record(NoiseOperation op){if(!valid_||op.id<=0||ids_.count(op.id)||!ok(op.start_minute)||!ok(op.end_minute)||op.start_minute==op.end_minute)return false;ids_.insert(op.id);int marginal=0;each(op.start_minute,op.end_minute,[&](int x){if(protected_[x]&&!charged_[x]){charged_[x]=true;++marginal;}});report_.marginal_minutes.push_back(marginal);report_.charged_minutes+=marginal;if(report_.within_budget&&report_.charged_minutes>budget_){report_.within_budget=false;report_.breach_operation_id=op.id;}return true;}NoiseAudit NoiseMeter::report()const{if(!valid_)return{false,false,0,-1,{}};return report_;}void NoiseMeter::reset(){if(!valid_)return;charged_.fill(false);ids_.clear();report_=NoiseAudit{};} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;NoiseMeter m(120,{{1320,120}});bool ok=m.record({1,1380,60})&&m.record({2,30,90});auto a=m.report();return ok&&a.valid&&!a.within_budget&&a.charged_minutes==150&&a.breach_operation_id==2&&a.marginal_minutes==std::vector<int>{120,30}?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;int f=0;NoiseMeter m(60,{{0,120}});f+=!m.record({1,0,60})||!m.record({2,30,90});auto a=m.report();f+=a.charged_minutes!=90||a.marginal_minutes[1]!=30||a.breach_operation_id!=2;f+=m.record({2,90,100});f+=m.report().charged_minutes!=90;m.reset();f+=m.report().charged_minutes!=0||!m.report().within_budget;NoiseMeter bad(-1,{});f+=bad.record({1,0,1})||bad.report().valid;NoiseMeter band(1,{{0,0}});f+=band.report().valid;return f;}
''',
        "if(protected_[x]&&!charged_[x])", "if(protected_[x])", "double charge minutes shared by multiple operations",
    ),
    MidnightCase(
        "midnight-delivery-curfew", "curfew-dispatch-selector", "Curfew Dispatch Selector",
        "Select the earliest route whose complete interval avoids every curfew, with a stable ID tie break.",
        "ordered candidate feasibility search", "select_dispatch(vector<Curfew>, vector<RouteCandidate>) -> DispatchChoice",
        r'''# Instructions

Curfews are nonempty half-open daily intervals and may wrap once. Candidate IDs are
positive and unique, starts are daily minutes, and durations are positive and at most one
day. Interpret each route on the overnight axis beginning at its start. A route is legal
only when its complete half-open interval has no positive overlap with any shifted curfew;
touching is legal. Choose the smallest unwrapped start, then smallest ID. Invalid input is
atomic. No legal candidate returns `valid=true`, `found=false`.
''',
        r'''#pragma once
#include <vector>
namespace curriculum { struct Curfew{int start_minute,end_minute;}; struct RouteCandidate{int id,start_minute,duration;}; struct DispatchChoice{bool valid=true,found=false;int route_id=-1,start_minute=-1;}; DispatchChoice select_dispatch(const std::vector<Curfew>&,const std::vector<RouteCandidate>&); }
''',
        _starter("select_dispatch", "DispatchChoice", "const std::vector<Curfew>&,const std::vector<RouteCandidate>&"),
        r'''#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum { namespace { bool ok(int x){return x>=0&&x<1440;} int end(int a,int b){return b<=a?b+1440:b;} }
DispatchChoice select_dispatch(const std::vector<Curfew>& curfews,const std::vector<RouteCandidate>& routes){std::vector<std::pair<int,int>> blocked;for(auto c:curfews){if(!ok(c.start_minute)||!ok(c.end_minute)||c.start_minute==c.end_minute)return{false,false,-1,-1};int e=end(c.start_minute,c.end_minute);for(int shift:{-1440,0,1440})blocked.push_back({c.start_minute+shift,e+shift});}std::set<int> ids;for(auto r:routes)if(r.id<=0||!ids.insert(r.id).second||!ok(r.start_minute)||r.duration<=0||r.duration>1440)return{false,false,-1,-1};std::vector<RouteCandidate> ordered=routes;std::sort(ordered.begin(),ordered.end(),[](auto a,auto b){return a.start_minute<b.start_minute||(a.start_minute==b.start_minute&&a.id<b.id);});for(auto r:ordered){int re=r.start_minute+r.duration;bool legal=true;for(auto c:blocked)if(std::max(r.start_minute,c.first)<std::min(re,c.second)){legal=false;break;}if(legal)return{true,true,r.id,r.start_minute};}return{};} }
''',
        r'''#include "task.h"
int main(){using namespace curriculum;auto c=select_dispatch({{1380,60}},{{9,1370,20},{3,60,30},{2,60,30}});return c.valid&&c.found&&c.route_id==2&&c.start_minute==60?0:1;}
''',
        r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto c=select_dispatch({{100,200}},{{1,50,50},{2,200,10}});f+=!c.found||c.route_id!=1;auto n=select_dispatch({{0,300}},{{1,10,20}});f+=!n.valid||n.found;f+=select_dispatch({},{{1,0,1},{1,2,1}}).valid;f+=select_dispatch({{0,0}},{}).valid;return f;}
''',
        "int re=r.start_minute+r.duration;", "int re=r.start_minute;", "check only the dispatch point and ignore route duration",
    ),
)

REJECTED_TASK_IDS = frozenset({"sleep-interruption-ledger", "transit-entitlement-audit"})
REJECTED_CASES = tuple(case for case in ALL_CASES if case.task_id in REJECTED_TASK_IDS)
CASES = tuple(case for case in ALL_CASES if case.task_id not in REJECTED_TASK_IDS)
