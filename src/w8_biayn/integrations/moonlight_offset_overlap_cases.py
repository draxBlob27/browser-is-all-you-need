"""Distinct clean-room cases for offset-aware range-overlap remediation."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    legacy_id: str
    task_id: str
    disposition: str
    title: str
    profile: str
    header: str
    source: str
    starter: str
    visible: str
    hidden: str
    negative: str
    instructions: str


def _case(legacy: str, task: str, disposition: str, title: str, profile: str,
          header: str, source: str, visible: str, hidden: str, negative: str,
          instructions: str) -> Case:
    declaration = header.split("namespace curriculum {", 1)[1].split("}", 1)[0]
    function = declaration.rsplit(" ", 1)[-1].split("(", 1)[0]
    starter = f'#include "{task}.h"\nnamespace curriculum {{\n'
    if "class " in header:
        # Class-based cases provide their own compact starter below.
        starter = ""
    return Case(legacy, task, disposition, title, profile, header, source,
                starter, visible, hidden, negative, instructions)


FREEZE_HEADER = r'''#pragma once
#include <string>
#include <vector>
namespace curriculum {
struct Release { int id; int local_minute; int utc_offset_minutes; };
struct FreezeWindow { int jurisdiction_id; int local_begin; int local_end; int utc_offset_minutes; int precedence; };
struct FreezeFinding { bool valid=false; bool blocked=false; int jurisdiction_id=-1; int normalized_minute=0; };
class BuildFreezeAudit { public: FreezeFinding classify(const Release&, const std::vector<FreezeWindow>&) const; };
}
'''
FREEZE_SOURCE = r'''#include "offset-build-freeze.h"
#include <set>
namespace curriculum { namespace {
bool offset_ok(int x){return x>=-840&&x<=840;} int instant(int local,int offset){return local-offset;}
}
FreezeFinding BuildFreezeAudit::classify(const Release& release,const std::vector<FreezeWindow>& windows) const {
  FreezeFinding out; if(release.id<=0||release.local_minute<0||release.local_minute>=20160||!offset_ok(release.utc_offset_minutes)) return out;
  std::set<int> ids; for(const auto& w:windows) if(w.jurisdiction_id<=0||!ids.insert(w.jurisdiction_id).second||w.local_begin<0||w.local_end<=w.local_begin||w.local_end>20160||!offset_ok(w.utc_offset_minutes)||w.precedence<0) return out;
  out.valid=true; out.normalized_minute=instant(release.local_minute,release.utc_offset_minutes); int best=0;
  for(const auto& w:windows){int begin=instant(w.local_begin,w.utc_offset_minutes),end=instant(w.local_end,w.utc_offset_minutes);if(begin<=out.normalized_minute&&out.normalized_minute<end&&(!out.blocked||w.precedence<best||(w.precedence==best&&w.jurisdiction_id<out.jurisdiction_id))){out.blocked=true;out.jurisdiction_id=w.jurisdiction_id;best=w.precedence;}}
  return out;
}}
'''
FREEZE_NEG = FREEZE_SOURCE.replace("w.precedence<best||(w.precedence==best&&w.jurisdiction_id<out.jurisdiction_id)", "w.precedence>best||(w.precedence==best&&w.jurisdiction_id<out.jurisdiction_id)")
FREEZE_VISIBLE = r'''#include "offset-build-freeze.h"
using namespace curriculum; int main(){BuildFreezeAudit a;auto r=a.classify({7,600,60},{{9,500,650,0,4},{3,540,660,0,2},{2,500,540,0,2}});return !r.valid||!r.blocked||r.jurisdiction_id!=3||r.normalized_minute!=540;}
'''
FREEZE_HIDDEN = r'''#include "offset-build-freeze.h"
using namespace curriculum; int main(){BuildFreezeAudit a;auto touch=a.classify({1,100,0},{{2,50,100,0,0}});auto extreme=a.classify({1,900,840},{{8,0,100,0,1}});auto duplicate=a.classify({1,50,0},{{2,0,60,0,1},{2,0,70,0,2}});return !touch.valid||touch.blocked||!extreme.blocked||duplicate.valid;}
'''


BORDER_HEADER = r'''#pragma once
#include <vector>
namespace curriculum {
struct DispatchWindow{int local_begin;int local_end;int utc_offset_minutes;}; struct AcceptanceWindow{int local_begin;int local_end;int utc_offset_minutes;};
struct CustomsClosure{int id;int local_begin;int local_end;int utc_offset_minutes;}; struct DeliverySlot{int begin_utc;int end_utc;}; struct SlotReport{bool valid=false;std::vector<DeliverySlot> slots;};
SlotReport enumerate_border_slots(const DispatchWindow&,const AcceptanceWindow&,const std::vector<CustomsClosure>&,int minimum_minutes);
}
'''
BORDER_SOURCE = r'''#include "offset-border-slot-enumerator.h"
#include <algorithm>
#include <set>
namespace curriculum { namespace {bool ok(int b,int e,int o){return b>=0&&e>b&&e<=20160&&o>=-840&&o<=840;}}
SlotReport enumerate_border_slots(const DispatchWindow& d,const AcceptanceWindow& a,const std::vector<CustomsClosure>& closures,int minimum){SlotReport out;if(minimum<=0||!ok(d.local_begin,d.local_end,d.utc_offset_minutes)||!ok(a.local_begin,a.local_end,a.utc_offset_minutes))return out;int left=std::max(d.local_begin-d.utc_offset_minutes,a.local_begin-a.utc_offset_minutes),right=std::min(d.local_end-d.utc_offset_minutes,a.local_end-a.utc_offset_minutes);std::set<int> ids;std::vector<DeliverySlot> blocked;for(const auto& c:closures){if(c.id<=0||!ids.insert(c.id).second||!ok(c.local_begin,c.local_end,c.utc_offset_minutes))return out;int b=std::max(left,c.local_begin-c.utc_offset_minutes),e=std::min(right,c.local_end-c.utc_offset_minutes);if(b<e)blocked.push_back({b,e});}std::sort(blocked.begin(),blocked.end(),[](auto x,auto y){return x.begin_utc<y.begin_utc;});int cursor=left;for(auto x:blocked){if(x.begin_utc-cursor>=minimum)out.slots.push_back({cursor,x.begin_utc});cursor=std::max(cursor,x.end_utc);}if(right-cursor>=minimum)out.slots.push_back({cursor,right});out.valid=true;return out;}}
'''
BORDER_NEG = BORDER_SOURCE.replace("for(auto x:blocked){", "blocked.clear();for(auto x:blocked){")
BORDER_VISIBLE = r'''#include "offset-border-slot-enumerator.h"
using namespace curriculum;int main(){auto r=enumerate_border_slots({100,300,60},{0,260,-40},{{1,130,170,0}},30);return !r.valid||r.slots.size()!=2||r.slots[0].begin_utc!=40||r.slots[0].end_utc!=130||r.slots[1].begin_utc!=170||r.slots[1].end_utc!=240;}
'''
BORDER_HIDDEN = r'''#include "offset-border-slot-enumerator.h"
using namespace curriculum;int main(){auto touch=enumerate_border_slots({0,100,0},{0,100,0},{{1,100,120,0}},100);auto dup=enumerate_border_slots({0,100,0},{0,100,0},{{1,10,20,0},{1,30,40,0}},1);auto bad=enumerate_border_slots({0,100,841},{0,100,0},{},1);return !touch.valid||touch.slots.size()!=1||dup.valid||bad.valid;}
'''


QUORUM_HEADER = r'''#pragma once
#include <string>
#include <vector>
namespace curriculum {struct ServiceWindow{std::string id;int local_begin;int local_end;int utc_offset_minutes;int weight;};struct QuorumSpan{int begin_utc;int end_utc;};struct QuorumReport{bool valid=false;std::vector<QuorumSpan> spans;};QuorumReport deployment_quorum(const std::vector<ServiceWindow>&,int threshold);}
'''
QUORUM_SOURCE = r'''#include "offset-deployment-quorum-sweep.h"
#include <algorithm>
#include <set>
#include <utility>
namespace curriculum {QuorumReport deployment_quorum(const std::vector<ServiceWindow>& windows,int threshold){QuorumReport out;if(threshold<=0)return out;std::set<std::string> ids;std::vector<std::pair<int,int>> events;int total=0;for(const auto&w:windows){if(w.id.empty()||!ids.insert(w.id).second||w.local_begin<0||w.local_end<=w.local_begin||w.local_end>20160||w.utc_offset_minutes< -840||w.utc_offset_minutes>840||w.weight<=0)return out;events.push_back({w.local_begin-w.utc_offset_minutes,w.weight});events.push_back({w.local_end-w.utc_offset_minutes,-w.weight});total+=w.weight;}if(threshold>total)return out;std::sort(events.begin(),events.end(),[](auto a,auto b){return a.first!=b.first?a.first<b.first:a.second<b.second;});int active=0;for(std::size_t i=0;i<events.size();){int at=events[i].first;if(i>0&&events[i-1].first<at&&active>=threshold){if(!out.spans.empty()&&out.spans.back().end_utc==events[i-1].first)out.spans.back().end_utc=at;else out.spans.push_back({events[i-1].first,at});}while(i<events.size()&&events[i].first==at)active+=events[i++].second;}out.valid=true;return out;}}
'''
QUORUM_NEG = QUORUM_SOURCE.replace("active>=threshold", "active==total")
QUORUM_VISIBLE = r'''#include "offset-deployment-quorum-sweep.h"
using namespace curriculum;int main(){auto r=deployment_quorum({{"api",100,300,60,2},{"db",0,200,-40,3},{"cache",170,260,0,1}},4);return !r.valid||r.spans.size()!=1||r.spans[0].begin_utc!=40||r.spans[0].end_utc!=240;}
'''
QUORUM_HIDDEN = r'''#include "offset-deployment-quorum-sweep.h"
using namespace curriculum;int main(){auto touching=deployment_quorum({{"a",0,50,0,1},{"b",50,100,0,1}},2);auto dup=deployment_quorum({{"a",0,50,0,1},{"a",10,60,0,1}},1);auto high=deployment_quorum({{"a",0,50,0,1}},2);return !touching.valid||!touching.spans.empty()||dup.valid||high.valid;}
'''


RELAY_HEADER = r'''#pragma once
#include <string>
#include <vector>
namespace curriculum {struct Incident{int id;int local_begin;int local_end;int utc_offset_minutes;std::string skill;};struct RelayTeam{int id;int local_begin;int local_end;int utc_offset_minutes;std::string skill;int capacity;};struct RelayAssignment{int incident_id;int team_id;};struct RelayPlan{bool valid=false;std::vector<RelayAssignment> assignments;std::vector<int> unassigned;};class RelayMatcher{public:RelayPlan assign(const std::vector<Incident>&,const std::vector<RelayTeam>&) const;};}
'''
RELAY_SOURCE = r'''#include "offset-relay-capacity-matching.h"
#include <algorithm>
#include <functional>
#include <set>
namespace curriculum {RelayPlan RelayMatcher::assign(const std::vector<Incident>& incidents,const std::vector<RelayTeam>& teams) const{RelayPlan out;std::set<int> ids;for(const auto&i:incidents)if(i.id<=0||!ids.insert(i.id).second||i.local_begin<0||i.local_end<=i.local_begin||i.local_end>20160||i.utc_offset_minutes< -840||i.utc_offset_minutes>840||i.skill.empty())return out;ids.clear();std::vector<int> slots;for(const auto&t:teams){if(t.id<=0||!ids.insert(t.id).second||t.local_begin<0||t.local_end<=t.local_begin||t.local_end>20160||t.utc_offset_minutes< -840||t.utc_offset_minutes>840||t.skill.empty()||t.capacity<=0)return out;for(int n=0;n<t.capacity;++n)slots.push_back(t.id);}std::sort(slots.begin(),slots.end());std::vector<int> owner(slots.size(),-1);auto eligible=[&](const Incident&i,int team_id){const auto&t=*std::find_if(teams.begin(),teams.end(),[&](const auto&x){return x.id==team_id;});return i.skill==t.skill&&std::max(i.local_begin-i.utc_offset_minutes,t.local_begin-t.utc_offset_minutes)<std::min(i.local_end-i.utc_offset_minutes,t.local_end-t.utc_offset_minutes);};std::function<bool(int,std::set<int>&)>augment=[&](int pos,std::set<int>&seen){for(std::size_t s=0;s<slots.size();++s)if(!seen.count(static_cast<int>(s))&&eligible(incidents[static_cast<std::size_t>(pos)],slots[s])){seen.insert(static_cast<int>(s));if(owner[s]<0||augment(owner[s],seen)){owner[s]=pos;return true;}}return false;};for(std::size_t i=0;i<incidents.size();++i){std::set<int> seen;if(!augment(static_cast<int>(i),seen))out.unassigned.push_back(incidents[i].id);}for(std::size_t s=0;s<slots.size();++s)if(owner[s]>=0)out.assignments.push_back({incidents[static_cast<std::size_t>(owner[s])].id,slots[s]});std::sort(out.assignments.begin(),out.assignments.end(),[](auto a,auto b){return a.incident_id<b.incident_id;});out.valid=true;return out;}}
'''
RELAY_NEG = RELAY_SOURCE.replace("if(owner[s]<0||augment(owner[s],seen))", "if(owner[s]<0)")
RELAY_VISIBLE = r'''#include "offset-relay-capacity-matching.h"
using namespace curriculum;int main(){RelayMatcher m;auto r=m.assign({{1,100,200,0,"med"},{2,120,180,0,"med"}},{{10,100,150,0,"med",1},{20,100,220,0,"med",1}});return !r.valid||r.assignments.size()!=2||r.assignments[0].team_id!=20||r.assignments[1].team_id!=10;}
'''
RELAY_HIDDEN = r'''#include "offset-relay-capacity-matching.h"
using namespace curriculum;int main(){RelayMatcher m;auto cap=m.assign({{1,0,30,0,"x"},{2,0,30,0,"x"}},{{9,0,30,0,"x",2}});auto skill=m.assign({{1,0,30,0,"x"}},{{9,0,30,0,"y",1}});auto dup=m.assign({{1,0,30,0,"x"},{1,0,30,0,"x"}},{});return !cap.valid||cap.assignments.size()!=2||!skill.valid||skill.unassigned.size()!=1||dup.valid;}
'''


REST_HEADER = r'''#pragma once
#include <vector>
namespace curriculum {struct RestEnvelope{int crew_id;int local_begin;int local_end;int utc_offset_minutes;};struct DutyFragment{int id;int crew_id;int local_begin;int local_end;int utc_offset_minutes;};struct RestAudit{bool valid=false;bool compliant=false;int longest_common_minutes=0;int common_begin_utc=0;};RestAudit audit_rest(const RestEnvelope&,const RestEnvelope&,const std::vector<DutyFragment>&,int required_minutes);}
'''
REST_SOURCE = r'''#include "offset-rest-gap-compliance.h"
#include <algorithm>
#include <set>
#include <utility>
namespace curriculum {namespace {using Span=std::pair<int,int>;bool ok(int b,int e,int o){return b>=0&&e>b&&e<=20160&&o>=-840&&o<=840;}std::vector<Span> free_spans(const RestEnvelope&e,std::vector<Span> duty){std::sort(duty.begin(),duty.end());std::vector<Span> out;int cursor=e.local_begin-e.utc_offset_minutes,finish=e.local_end-e.utc_offset_minutes;for(auto d:duty){d.first=std::max(d.first,cursor);d.second=std::min(d.second,finish);if(d.first>cursor)out.push_back({cursor,d.first});cursor=std::max(cursor,d.second);}if(cursor<finish)out.push_back({cursor,finish});return out;}}
RestAudit audit_rest(const RestEnvelope&a,const RestEnvelope&b,const std::vector<DutyFragment>& duties,int required){RestAudit out;if(required<=0||a.crew_id<=0||b.crew_id<=0||a.crew_id==b.crew_id||!ok(a.local_begin,a.local_end,a.utc_offset_minutes)||!ok(b.local_begin,b.local_end,b.utc_offset_minutes))return out;std::set<int> ids;std::vector<Span> da,db;for(const auto&d:duties){if(d.id<=0||!ids.insert(d.id).second||!ok(d.local_begin,d.local_end,d.utc_offset_minutes)||(d.crew_id!=a.crew_id&&d.crew_id!=b.crew_id))return out;(d.crew_id==a.crew_id?da:db).push_back({d.local_begin-d.utc_offset_minutes,d.local_end-d.utc_offset_minutes});}auto fa=free_spans(a,da),fb=free_spans(b,db);std::size_t i=0,j=0;while(i<fa.size()&&j<fb.size()){int l=std::max(fa[i].first,fb[j].first),r=std::min(fa[i].second,fb[j].second);if(r-l>out.longest_common_minutes){out.longest_common_minutes=r-l;out.common_begin_utc=l;}if(fa[i].second<fb[j].second)++i;else ++j;}out.valid=true;out.compliant=out.longest_common_minutes>=required;return out;}}
'''
REST_NEG = REST_SOURCE.replace("auto fa=free_spans(a,da),fb=free_spans(b,db);", "auto fa=free_spans(a,{}),fb=free_spans(b,{});")
REST_VISIBLE = r'''#include "offset-rest-gap-compliance.h"
using namespace curriculum;int main(){auto r=audit_rest({1,100,400,60},{2,0,300,-40},{{7,1,180,240,0},{8,2,140,200,0}},80);return !r.valid||!r.compliant||r.longest_common_minutes!=100||r.common_begin_utc!=40;}
'''
REST_HIDDEN = r'''#include "offset-rest-gap-compliance.h"
using namespace curriculum;int main(){auto edge=audit_rest({1,0,100,0},{2,0,100,0},{{1,1,20,40,0},{2,1,40,60,0}},40);auto unknown=audit_rest({1,0,100,0},{2,0,100,0},{{1,3,20,40,0}},1);auto dup=audit_rest({1,0,100,0},{2,0,100,0},{{1,1,20,40,0},{1,2,50,60,0}},1);return !edge.valid||!edge.compliant||edge.longest_common_minutes!=40||unknown.valid||dup.valid;}
'''

AUCTION_HEADER = r'''#pragma once
#include <string>
#include <vector>
namespace curriculum {struct TradingSession{int id;int local_begin;int local_end;int utc_offset_minutes;std::string venue;int liquidity;};struct AuctionChoice{bool valid=false;bool found=false;int first_id=-1;int second_id=-1;int overlap_minutes=0;int executable_units=0;long long score=0;};AuctionChoice select_liquidity_pair(const std::vector<TradingSession>&,int lot_size);}
'''
AUCTION_SOURCE = r'''#include "offset-auction-liquidity-intersection.h"
#include <algorithm>
#include <set>
#include <utility>
namespace curriculum {AuctionChoice select_liquidity_pair(const std::vector<TradingSession>& sessions,int lot){AuctionChoice out;if(lot<=0)return out;std::set<int> ids;for(const auto&s:sessions)if(s.id<=0||!ids.insert(s.id).second||s.local_begin<0||s.local_end<=s.local_begin||s.local_end>20160||s.utc_offset_minutes< -840||s.utc_offset_minutes>840||s.venue.empty()||s.liquidity<=0)return out;out.valid=true;for(std::size_t i=0;i<sessions.size();++i)for(std::size_t j=i+1;j<sessions.size();++j){const auto&a=sessions[i];const auto&b=sessions[j];if(a.venue!=b.venue)continue;int overlap=std::max(0,std::min(a.local_end-a.utc_offset_minutes,b.local_end-b.utc_offset_minutes)-std::max(a.local_begin-a.utc_offset_minutes,b.local_begin-b.utc_offset_minutes));int units=(std::min(a.liquidity,b.liquidity)/lot)*lot;long long score=static_cast<long long>(overlap)*units;auto ids_pair=std::minmax(a.id,b.id);if(overlap>0&&units>0&&(!out.found||score>out.score||(score==out.score&&std::pair<int,int>{ids_pair.first,ids_pair.second}<std::pair<int,int>{out.first_id,out.second_id}))){out.found=true;out.first_id=ids_pair.first;out.second_id=ids_pair.second;out.overlap_minutes=overlap;out.executable_units=units;out.score=score;}}return out;}}
'''
AUCTION_NEG = AUCTION_SOURCE.replace("static_cast<long long>(overlap)*units", "static_cast<long long>(overlap)")
AUCTION_VISIBLE = r'''#include "offset-auction-liquidity-intersection.h"
using namespace curriculum;int main(){auto r=select_liquidity_pair({{1,0,200,0,"x",100},{2,0,100,0,"x",20},{3,100,260,0,"x",50}},10);return !r.valid||!r.found||r.first_id!=1||r.second_id!=3||r.score!=5000;}
'''
AUCTION_HIDDEN = r'''#include "offset-auction-liquidity-intersection.h"
using namespace curriculum;int main(){auto none=select_liquidity_pair({{1,0,50,0,"x",9},{2,0,50,0,"x",9}},10);auto venues=select_liquidity_pair({{1,0,50,0,"x",10},{2,0,50,0,"y",10}},5);auto dup=select_liquidity_pair({{1,0,50,0,"x",10},{1,0,50,0,"x",10}},5);return !none.valid||none.found||!venues.valid||venues.found||dup.valid;}
'''

SUPPORT_HEADER = r'''#pragma once
#include <string>
#include <vector>
namespace curriculum {struct SupportRequest{int id;int local_begin;int local_end;int utc_offset_minutes;std::string language;};struct SupportShift{int id;int local_begin;int local_end;int utc_offset_minutes;std::string language;};struct SupportChainPlan{bool valid=false;bool complete=false;int covered_until_utc=0;std::vector<int> shift_ids;};SupportChainPlan plan_support_chain(const SupportRequest&,const std::vector<SupportShift>&);}
'''
SUPPORT_SOURCE = r'''#include "offset-support-coverage-chain.h"
#include <algorithm>
#include <set>
namespace curriculum {SupportChainPlan plan_support_chain(const SupportRequest& request,const std::vector<SupportShift>& shifts){SupportChainPlan out;if(request.id<=0||request.local_begin<0||request.local_end<=request.local_begin||request.local_end>20160||request.utc_offset_minutes< -840||request.utc_offset_minutes>840||request.language.empty())return out;std::set<int> ids;for(const auto&shift:shifts)if(shift.id<=0||!ids.insert(shift.id).second||shift.local_begin<0||shift.local_end<=shift.local_begin||shift.local_end>20160||shift.utc_offset_minutes< -840||shift.utc_offset_minutes>840||shift.language.empty())return out;int cursor=request.local_begin-request.utc_offset_minutes;const int finish=request.local_end-request.utc_offset_minutes;out.valid=true;out.covered_until_utc=cursor;while(cursor<finish){int best_id=-1,best_reach=cursor;for(const auto&shift:shifts){const int begin=shift.local_begin-shift.utc_offset_minutes;const int reach=shift.local_end-shift.utc_offset_minutes;if(shift.language==request.language&&begin<=cursor&&reach>cursor&&(reach>best_reach||(reach==best_reach&&(best_id<0||shift.id<best_id)))){best_id=shift.id;best_reach=reach;}}if(best_id<0)return out;out.shift_ids.push_back(best_id);cursor=std::min(best_reach,finish);out.covered_until_utc=cursor;}out.complete=true;return out;}}
'''
SUPPORT_NEG = SUPPORT_SOURCE.replace("reach>best_reach||(reach==best_reach", "reach<best_reach||(reach==best_reach").replace("best_reach=cursor", "best_reach=finish+1")
SUPPORT_VISIBLE = r'''#include "offset-support-coverage-chain.h"
using namespace curriculum;int main(){auto r=plan_support_chain({7,0,180,0,"en"},{{1,0,100,0,"en"},{2,0,60,0,"en"},{3,60,180,0,"en"}});return !r.valid||!r.complete||r.covered_until_utc!=180||r.shift_ids.size()!=2||r.shift_ids[0]!=1||r.shift_ids[1]!=3;}
'''
SUPPORT_HIDDEN = r'''#include "offset-support-coverage-chain.h"
using namespace curriculum;int main(){auto offset=plan_support_chain({7,120,240,60,"en"},{{1,0,90,0,"en"},{2,80,200,0,"en"}});auto gap=plan_support_chain({8,0,100,0,"en"},{{3,0,40,0,"en"},{4,50,100,0,"en"}});auto language=plan_support_chain({9,0,30,0,"en"},{{5,0,30,0,"fr"}});auto dup=plan_support_chain({10,0,30,0,"en"},{{5,0,20,0,"en"},{5,10,30,0,"en"}});return !offset.valid||!offset.complete||offset.shift_ids.size()!=2||!gap.valid||gap.complete||gap.covered_until_utc!=40||!language.valid||language.complete||dup.valid;}
'''

COVERAGE_HEADER = r'''#pragma once
#include <string>
#include <vector>
namespace curriculum {struct ObservationWindow{int id;std::string instrument;int local_begin;int local_end;int utc_offset_minutes;};struct CalibrationWindow{int id;std::string instrument;int local_begin;int local_end;int utc_offset_minutes;};struct InstrumentCoverage{std::string instrument;int available_minutes;};struct CoverageReport{bool valid=false;int combined_minutes=0;std::vector<InstrumentCoverage> instruments;};CoverageReport measure_coverage(const std::vector<ObservationWindow>&,const std::vector<CalibrationWindow>&);}
'''
COVERAGE_SOURCE = r'''#include "offset-observation-coverage-subtraction.h"
#include <algorithm>
#include <map>
#include <set>
#include <utility>
namespace curriculum {namespace {using Span=std::pair<int,int>;bool ok(int b,int e,int o){return b>=0&&e>b&&e<=20160&&o>=-840&&o<=840;}std::vector<Span> merged(std::vector<Span> v){std::sort(v.begin(),v.end());std::vector<Span> out;for(auto x:v)if(out.empty()||x.first>out.back().second)out.push_back(x);else out.back().second=std::max(out.back().second,x.second);return out;}int length(const std::vector<Span>&v){int n=0;for(auto x:v)n+=x.second-x.first;return n;}}
CoverageReport measure_coverage(const std::vector<ObservationWindow>& observations,const std::vector<CalibrationWindow>& calibrations){CoverageReport out;std::set<int> ids;std::map<std::string,std::vector<Span>> obs,cal;for(const auto&w:observations){if(w.id<=0||w.instrument.empty()||!ids.insert(w.id).second||!ok(w.local_begin,w.local_end,w.utc_offset_minutes))return out;obs[w.instrument].push_back({w.local_begin-w.utc_offset_minutes,w.local_end-w.utc_offset_minutes});}ids.clear();for(const auto&w:calibrations){if(w.id<=0||w.instrument.empty()||!ids.insert(w.id).second||!ok(w.local_begin,w.local_end,w.utc_offset_minutes)||!obs.count(w.instrument))return out;cal[w.instrument].push_back({w.local_begin-w.utc_offset_minutes,w.local_end-w.utc_offset_minutes});}std::vector<Span> global;for(auto&item:obs){auto available=merged(item.second);for(auto block:merged(cal[item.first])){std::vector<Span> next;for(auto span:available){if(block.second<=span.first||block.first>=span.second)next.push_back(span);else{if(span.first<block.first)next.push_back({span.first,block.first});if(block.second<span.second)next.push_back({block.second,span.second});}}available=next;}out.instruments.push_back({item.first,length(available)});global.insert(global.end(),available.begin(),available.end());}out.combined_minutes=length(merged(global));out.valid=true;return out;}}
'''
COVERAGE_NEG = COVERAGE_SOURCE.replace("for(auto block:merged(cal[item.first]))", "cal[item.first].clear();for(auto block:merged(cal[item.first]))")
COVERAGE_VISIBLE = r'''#include "offset-observation-coverage-subtraction.h"
using namespace curriculum;int main(){auto r=measure_coverage({{1,"a",0,100,0},{2,"b",50,150,0}},{{3,"a",20,40,0}});return !r.valid||r.instruments.size()!=2||r.instruments[0].available_minutes!=80||r.combined_minutes!=130;}
'''
COVERAGE_HIDDEN = r'''#include "offset-observation-coverage-subtraction.h"
using namespace curriculum;int main(){auto merged=measure_coverage({{1,"a",0,100,0}},{{2,"a",20,40,0},{3,"a",40,60,0}});auto unknown=measure_coverage({{1,"a",0,100,0}},{{2,"b",20,40,0}});auto dup=measure_coverage({{1,"a",0,100,0},{1,"b",0,50,0}},{});return !merged.valid||merged.instruments[0].available_minutes!=60||unknown.valid||dup.valid;}
'''

CONTACT_HEADER = r'''#pragma once
#include <vector>
namespace curriculum {struct ContactPass{int id;int local_begin;int local_end;int utc_offset_minutes;int value;};struct ContactPlan{bool valid=false;int total_value=0;std::vector<int> selected_ids;};ContactPlan schedule_contacts(const std::vector<ContactPass>&,int setup_minutes);}
'''
CONTACT_SOURCE = r'''#include "offset-station-contact-weighted-schedule.h"
#include <algorithm>
#include <set>
namespace curriculum {ContactPlan schedule_contacts(const std::vector<ContactPass>& passes,int setup){ContactPlan out;if(setup<0)return out;std::set<int> ids;struct Item{int id;int begin;int end;int value;};std::vector<Item> items;for(const auto&p:passes){if(p.id<=0||!ids.insert(p.id).second||p.local_begin<0||p.local_end<=p.local_begin||p.local_end>20160||p.utc_offset_minutes< -840||p.utc_offset_minutes>840||p.value<0)return out;items.push_back({p.id,p.local_begin-p.utc_offset_minutes,p.local_end-p.utc_offset_minutes,p.value});}std::sort(items.begin(),items.end(),[](auto a,auto b){return a.end!=b.end?a.end<b.end:a.id<b.id;});std::vector<int> best(items.size()+1);std::vector<std::vector<int>> chosen(items.size()+1);for(std::size_t i=1;i<=items.size();++i){std::size_t p=0;for(std::size_t j=0;j+1<i;++j)if(items[j].end+setup<=items[i-1].begin)p=j+1;int take=best[p]+items[i-1].value;auto ids_take=chosen[p];ids_take.push_back(items[i-1].id);if(take>best[i-1]||(take==best[i-1]&&ids_take<chosen[i-1])){best[i]=take;chosen[i]=ids_take;}else{best[i]=best[i-1];chosen[i]=chosen[i-1];}}out.valid=true;out.total_value=best.back();out.selected_ids=chosen.back();return out;}}
'''
CONTACT_NEG = CONTACT_SOURCE.replace("int take=best[p]+items[i-1].value;", "int take=best[p]+1;")
CONTACT_VISIBLE = r'''#include "offset-station-contact-weighted-schedule.h"
using namespace curriculum;int main(){auto r=schedule_contacts({{1,0,100,0,5},{2,100,200,0,5},{3,0,200,0,20}},0);return !r.valid||r.total_value!=20||r.selected_ids.size()!=1||r.selected_ids[0]!=3;}
'''
CONTACT_HIDDEN = r'''#include "offset-station-contact-weighted-schedule.h"
using namespace curriculum;int main(){auto gap=schedule_contacts({{1,0,50,0,5},{2,50,100,0,6}},1);auto tie=schedule_contacts({{1,0,50,0,5},{2,0,50,0,5}},0);auto dup=schedule_contacts({{1,0,50,0,5},{1,50,100,0,6}},0);return !gap.valid||gap.total_value!=6||tie.selected_ids[0]!=1||dup.valid;}
'''

CLINIC_HEADER = r'''#pragma once
#include <map>
#include <optional>
#include <string>
#include <utility>
#include <vector>
namespace curriculum {struct Appointment{int id;int local_begin;int local_end;int clinic_offset_minutes;std::string specialty;};struct Clinician{int id;int local_begin;int local_end;int utc_offset_minutes;std::string specialty;int daily_cap;};struct Booking{int appointment_id;int clinician_id;};class ClinicRoster{public:explicit ClinicRoster(std::vector<Clinician>);bool valid() const;bool book(const Appointment&);bool cancel(int appointment_id);std::optional<Booking> lookup(int appointment_id) const;std::vector<Booking> assignments() const;private:struct Stored{Appointment appointment;int clinician_id;int clinician_day;};bool valid_=false;std::vector<Clinician> clinicians_;std::map<int,Stored> booked_;std::map<std::pair<int,int>,int> used_;};}
'''
CLINIC_SOURCE = r'''#include "offset-clinic-capacity-assignment.h"
#include <algorithm>
#include <set>
#include <tuple>
namespace curriculum {namespace {bool range_ok(int begin,int end,int offset){return begin>=0&&end>begin&&end<=20160&&offset>=-840&&offset<=840;}int day_index(int minute){return minute>=0?minute/1440:-((-minute+1439)/1440);}}
ClinicRoster::ClinicRoster(std::vector<Clinician> clinicians):clinicians_(std::move(clinicians)){std::set<int> ids;for(const auto&c:clinicians_)if(c.id<=0||!ids.insert(c.id).second||!range_ok(c.local_begin,c.local_end,c.utc_offset_minutes)||c.specialty.empty()||c.daily_cap<=0)return;valid_=true;}
bool ClinicRoster::valid() const{return valid_;}
bool ClinicRoster::book(const Appointment& appointment){if(!valid_||appointment.id<=0||booked_.count(appointment.id)||!range_ok(appointment.local_begin,appointment.local_end,appointment.clinic_offset_minutes)||appointment.specialty.empty())return false;const int begin=appointment.local_begin-appointment.clinic_offset_minutes,end=appointment.local_end-appointment.clinic_offset_minutes;int best=-1,best_used=0,best_day=0;for(const auto&c:clinicians_){const int day=day_index(begin+c.utc_offset_minutes);const int count=used_[{c.id,day}];if(c.specialty==appointment.specialty&&c.local_begin-c.utc_offset_minutes<=begin&&end<=c.local_end-c.utc_offset_minutes&&count<c.daily_cap&&(best<0||std::tie(count,c.id)<std::tie(best_used,best))){best=c.id;best_used=count;best_day=day;}}if(best<0)return false;booked_.insert({appointment.id,{appointment,best,best_day}});++used_[{best,best_day}];return true;}
bool ClinicRoster::cancel(int appointment_id){auto found=booked_.find(appointment_id);if(found==booked_.end())return false;--used_[{found->second.clinician_id,found->second.clinician_day}];booked_.erase(found);return true;}
std::optional<Booking> ClinicRoster::lookup(int appointment_id) const{auto found=booked_.find(appointment_id);if(found==booked_.end())return std::nullopt;return Booking{appointment_id,found->second.clinician_id};}
std::vector<Booking> ClinicRoster::assignments() const{std::vector<Booking> out;for(const auto&item:booked_)out.push_back({item.first,item.second.clinician_id});return out;}}
'''
CLINIC_NEG = CLINIC_SOURCE.replace("day_index(begin+c.utc_offset_minutes)", "day_index(begin)")
CLINIC_STARTER = r'''#include "offset-clinic-capacity-assignment.h"
namespace curriculum {ClinicRoster::ClinicRoster(std::vector<Clinician>){ }bool ClinicRoster::valid() const{return false;}bool ClinicRoster::book(const Appointment&){return false;}bool ClinicRoster::cancel(int){return false;}std::optional<Booking> ClinicRoster::lookup(int) const{return std::nullopt;}std::vector<Booking> ClinicRoster::assignments() const{return {};}}
'''
CLINIC_VISIBLE = r'''#include "offset-clinic-capacity-assignment.h"
using namespace curriculum;int main(){ClinicRoster r({{10,1300,1600,60,"cardio",1},{20,1300,1600,0,"cardio",2}});bool first=r.book({1,1400,1430,0,"cardio"});bool second=r.book({2,1450,1480,0,"cardio"});auto a=r.lookup(1);auto b=r.lookup(2);return !r.valid()||!first||!second||!a||!b||a->clinician_id!=10||b->clinician_id!=20||r.assignments().size()!=2;}
'''
CLINIC_HIDDEN = r'''#include "offset-clinic-capacity-assignment.h"
using namespace curriculum;int main(){ClinicRoster r({{9,1200,1700,120,"x",1}});bool first=r.book({1,1300,1320,0,"x"});bool second=r.book({2,1400,1420,0,"x"});bool duplicate=r.book({2,1450,1470,0,"x"});bool missing_cancel=r.cancel(99);bool cancelled=r.cancel(1);bool rebooked=r.book({3,1300,1320,0,"x"});auto ordered=r.assignments();ClinicRoster bad({{9,0,20,0,"x",0}});return !first||!second||duplicate||missing_cancel||!cancelled||!rebooked||ordered.size()!=2||ordered[0].appointment_id!=2||ordered[1].appointment_id!=3||bad.valid();}
'''


def _starter(task_id: str, signature: str) -> str:
    return f'#include "{task_id}.h"\nnamespace curriculum {{\n{signature}\n}}\n'


CASES = (
    Case("offset-build-freeze","offset-build-freeze","repair-in-place","Build freeze release audit","normalized interval stabbing with precedence",FREEZE_HEADER,FREEZE_SOURCE,_starter("offset-build-freeze","FreezeFinding BuildFreezeAudit::classify(const Release&,const std::vector<FreezeWindow>&) const{return {};}") ,FREEZE_VISIBLE,FREEZE_HIDDEN,FREEZE_NEG,"Normalize the release point and every half-open freeze interval. Select the containing window with lowest precedence then jurisdiction ID. Validate all records before classification; touching the end is not blocked."),
    Case("offset-crossborder-delivery","offset-border-slot-enumerator","replace","Border delivery slot enumerator","intersection minus canonical closure union",BORDER_HEADER,BORDER_SOURCE,_starter("offset-border-slot-enumerator","SlotReport enumerate_border_slots(const DispatchWindow&,const AcceptanceWindow&,const std::vector<CustomsClosure>&,int){return {};}") ,BORDER_VISIBLE,BORDER_HIDDEN,BORDER_NEG,"Normalize and intersect dispatch and acceptance windows, merge touching customs closures, subtract them, and emit maximal slots meeting minimum_minutes in UTC order. Reject malformed or duplicate input atomically."),
    Case("offset-distributed-deploy","offset-deployment-quorum-sweep","replace","Deployment quorum sweep","weighted half-open boundary-event sweep",QUORUM_HEADER,QUORUM_SOURCE,_starter("offset-deployment-quorum-sweep","QuorumReport deployment_quorum(const std::vector<ServiceWindow>&,int){return {};}") ,QUORUM_VISIBLE,QUORUM_HIDDEN,QUORUM_NEG,"Normalize weighted service windows and emit maximal half-open UTC spans whose active weight meets threshold. Process end events before starts at equal instants. Reject duplicate services and impossible policies."),
    Case("offset-emergency-escalation","offset-relay-capacity-matching","replace","Relay capacity matching","capacity-slot augmenting-path matching",RELAY_HEADER,RELAY_SOURCE,_starter("offset-relay-capacity-matching","RelayPlan RelayMatcher::assign(const std::vector<Incident>&,const std::vector<RelayTeam>&) const{return {};}") ,RELAY_VISIBLE,RELAY_HIDDEN,RELAY_NEG,"Build eligibility from matching skill and positive normalized overlap. Find a maximum matching over team capacity slots, preferring lower team IDs while allowing augmenting reassignment. Report unmatched incidents."),
    Case("offset-flight-crew-rest","offset-rest-gap-compliance","replace","Crew rest gap compliance","duty union subtraction plus free-span intersection",REST_HEADER,REST_SOURCE,_starter("offset-rest-gap-compliance","RestAudit audit_rest(const RestEnvelope&,const RestEnvelope&,const std::vector<DutyFragment>&,int){return {};}") ,REST_VISIBLE,REST_HIDDEN,REST_NEG,"Subtract each crew member's normalized duty union from that member's rest envelope, intersect the resulting free spans, and report the earliest longest common rest. Equality meets required_minutes."),
    Case("offset-market-auction","offset-auction-liquidity-intersection","replace","Auction liquidity intersection","liquidity-duration pair scoring",AUCTION_HEADER,AUCTION_SOURCE,_starter("offset-auction-liquidity-intersection","AuctionChoice select_liquidity_pair(const std::vector<TradingSession>&,int){return {};}") ,AUCTION_VISIBLE,AUCTION_HIDDEN,AUCTION_NEG,"For same-venue session pairs, score normalized overlap minutes times executable liquidity rounded down to lot_size. Select maximum score, then lexicographically smaller IDs. A valid no-pair result has found=false."),
    Case("offset-remote-support","offset-support-coverage-chain","replace","Support coverage chain","farthest-frontier minimum interval cover",SUPPORT_HEADER,SUPPORT_SOURCE,_starter("offset-support-coverage-chain","SupportChainPlan plan_support_chain(const SupportRequest&,const std::vector<SupportShift>&){return {};}") ,SUPPORT_VISIBLE,SUPPORT_HIDDEN,SUPPORT_NEG,"Cover the normalized request continuously with the fewest compatible shifts. At each uncovered frontier choose the eligible shift reaching farthest, breaking equal reach by ID; report a valid incomplete plan when a gap remains."),
    Case("offset-research-coverage","offset-observation-coverage-subtraction","replace","Observation coverage subtraction","grouped union, subtraction, and global union",COVERAGE_HEADER,COVERAGE_SOURCE,_starter("offset-observation-coverage-subtraction","CoverageReport measure_coverage(const std::vector<ObservationWindow>&,const std::vector<CalibrationWindow>&){return {};}") ,COVERAGE_VISIBLE,COVERAGE_HIDDEN,COVERAGE_NEG,"For each instrument, union normalized observation windows and subtract its merged calibration windows. Report instrument names in lexical order and the union length across all remaining instrument coverage."),
    Case("offset-satellite-contact","offset-station-contact-weighted-schedule","replace","Weighted contact schedule","weighted interval scheduling dynamic program",CONTACT_HEADER,CONTACT_SOURCE,_starter("offset-station-contact-weighted-schedule","ContactPlan schedule_contacts(const std::vector<ContactPass>&,int){return {};}") ,CONTACT_VISIBLE,CONTACT_HIDDEN,CONTACT_NEG,"Normalize passes and select a maximum-value non-overlapping subsequence with setup_minutes between contacts. Resolve equal total value by lexicographically smaller selected ID sequence."),
    Case("offset-telehealth-roster","offset-clinic-capacity-assignment","replace","Clinic capacity booking ledger","stateful transactional booking and cancellation ledger",CLINIC_HEADER,CLINIC_SOURCE,CLINIC_STARTER,CLINIC_VISIBLE,CLINIC_HIDDEN,CLINIC_NEG,"Construct a validated roster, then book and cancel appointments transactionally. Choose an eligible containing clinician with least used capacity then ID, count daily_cap by that clinician's local day, preserve state after every rejected operation, and return assignments in appointment-ID order."),
)
