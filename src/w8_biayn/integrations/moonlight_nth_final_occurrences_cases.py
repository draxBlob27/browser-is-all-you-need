"""Clean-room cases for the remediated nth/final-occurrences family."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OccurrenceCase:
    legacy_id: str
    task_id: str
    title: str
    objective: str
    mechanism: str
    public_api: str
    boundary: str
    header: str
    reference: str
    visible_test: str
    hidden_test: str
    negative_old: str
    negative_new: str
    negative_reason: str
    disposition: str = "replace"


def _case(**values: str) -> OccurrenceCase:
    return OccurrenceCase(**values)


CASES = (
    _case(
        legacy_id="occurrence-inspection-route",
        task_id="occurrence-inspection-route",
        title="Inspection Route Selector",
        objective="Validate a route snapshot, filter passed inspections by zone and severity, and return a numbered match or the final match.",
        mechanism="validated stable-order filtered-index scan",
        public_api="Selection choose(const vector<Inspection>&, const RoutePolicy&, size_t); Selection final(const vector<Inspection>&, const RoutePolicy&)",
        boundary="Ordinals are one-based; duplicate IDs or non-increasing sequence values invalidate the complete query.",
        disposition="repair-in-place",
        header=r"""#ifndef TASK_H
#define TASK_H
#include <cstddef>
#include <vector>
namespace curriculum {
struct Inspection { int sequence; int id; int zone; int severity; bool passed; };
struct RoutePolicy { int zone; int minimum_severity; };
struct Selection { bool valid; bool found; int id; int sequence; };
class InspectionRouteSelector {
 public:
  static Selection choose(const std::vector<Inspection>& records, const RoutePolicy& policy, std::size_t ordinal);
  static Selection final(const std::vector<Inspection>& records, const RoutePolicy& policy);
};
}
#endif
""",
        reference=r"""#include "task.h"
#include <set>
namespace curriculum {
namespace {
std::vector<Inspection> matches(const std::vector<Inspection>& records, const RoutePolicy& policy, bool& valid) {
  std::vector<Inspection> out; std::set<int> ids; int prior = -1; valid = true;
  for (const auto& item : records) {
    if (item.sequence <= prior || item.id < 0 || !ids.insert(item.id).second) { valid = false; return {}; }
    prior = item.sequence;
    if (item.passed && item.zone == policy.zone && item.severity >= policy.minimum_severity) out.push_back(item);
  }
  return out;
}
Selection result(const std::vector<Inspection>& found, std::size_t index) {
  if (index >= found.size()) return {true, false, -1, -1};
  return {true, true, found[index].id, found[index].sequence};
}
}
Selection InspectionRouteSelector::choose(const std::vector<Inspection>& records, const RoutePolicy& policy, std::size_t ordinal) {
  if (ordinal == 0U) return {false, false, -1, -1}; bool valid = false; const auto found = matches(records, policy, valid);
  return valid ? result(found, ordinal - 1U) : Selection{false, false, -1, -1};
}
Selection InspectionRouteSelector::final(const std::vector<Inspection>& records, const RoutePolicy& policy) {
  bool valid = false; const auto found = matches(records, policy, valid);
  return !valid ? Selection{false, false,-1,-1} : (found.empty() ? Selection{true,false,-1,-1} : Selection{true,true,found.back().id,found.back().sequence});
}
}
""",
        visible_test=r"""#include "task.h"
int main() { using namespace curriculum; const std::vector<Inspection> rows{{1,11,2,4,true},{2,12,3,9,true},{3,13,2,3,true},{4,14,2,8,true}}; const RoutePolicy p{2,4}; const auto n=InspectionRouteSelector::choose(rows,p,2); const auto f=InspectionRouteSelector::final(rows,p); return n.valid&&n.found&&n.id==14&&f.found&&f.id==14 ? 0:1; }
""",
        hidden_test=r"""#include "task.h"
int main() { using namespace curriculum; const RoutePolicy p{2,4}; const auto zero=InspectionRouteSelector::choose({},p,0); const auto none=InspectionRouteSelector::final({},p); const auto bad=InspectionRouteSelector::choose({{2,1,2,5,true},{1,2,2,5,true}},p,1); return !zero.valid&&none.valid&&!none.found&&!bad.valid ? 0:1; }
""",
        negative_old="found.back().id,found.back().sequence",
        negative_new="found.front().id,found.front().sequence",
        negative_reason="returns the first qualifying inspection for final mode",
    ),
    _case(
        legacy_id="occurrence-invoice-escalation",
        task_id="escalation-state-ledger",
        title="Escalation State Ledger",
        objective="Replay invoice lifecycle events and query the nth transition into unresolved escalation or the final overdue open invoice.",
        mechanism="event-sourced per-invoice state transition ledger",
        public_api="bool apply(Event); optional<int> nth_escalated(size_t) const; optional<int> final_overdue() const",
        boundary="Event sequence is global and strictly increasing; a resolve before open or repeated open is rejected atomically.",
        header=r"""#ifndef TASK_H
#define TASK_H
#include <cstddef>
#include <map>
#include <optional>
#include <vector>
namespace curriculum {
enum class InvoiceAction { open, escalate, mark_overdue, resolve };
struct InvoiceEvent { int sequence; int invoice; InvoiceAction action; };
class EscalationStateLedger { struct State { bool open=false; bool escalated=false; bool overdue=false; }; std::map<int,State> states_; std::vector<int> transitions_; int last_= -1;
 public: bool apply(const InvoiceEvent& event); std::optional<int> nth_escalated(std::size_t ordinal) const; std::optional<int> final_overdue() const; };
}
#endif
""",
        reference=r"""#include "task.h"
namespace curriculum {
bool EscalationStateLedger::apply(const InvoiceEvent& e) {
  if(e.sequence<=last_||e.invoice<0) return false; auto next=states_; auto& s=next[e.invoice];
  if(e.action==InvoiceAction::open){if(s.open)return false;s.open=true;}
  else if(!s.open)return false;
  else if(e.action==InvoiceAction::escalate){if(!s.escalated){s.escalated=true;transitions_.push_back(e.invoice);}}
  else if(e.action==InvoiceAction::mark_overdue)s.overdue=true;
  else {s.open=false;s.escalated=false;s.overdue=false;}
  states_=next;last_=e.sequence;return true;
}
std::optional<int> EscalationStateLedger::nth_escalated(std::size_t n) const { if(n==0U||n>transitions_.size())return {};return transitions_[n-1U]; }
std::optional<int> EscalationStateLedger::final_overdue() const { std::optional<int> out; for(const auto& [id,s]:states_)if(s.open&&s.overdue)out=id;return out; }
}
""",
        visible_test=r"""#include "task.h"
int main(){using namespace curriculum;EscalationStateLedger x;bool ok=x.apply({1,8,InvoiceAction::open})&&x.apply({2,8,InvoiceAction::escalate})&&x.apply({3,9,InvoiceAction::open})&&x.apply({4,9,InvoiceAction::mark_overdue})&&x.apply({5,9,InvoiceAction::escalate});auto n=x.nth_escalated(2);auto f=x.final_overdue();return ok&&n&&*n==9&&f&&*f==9?0:1;}
""",
        hidden_test=r"""#include "task.h"
int main(){using namespace curriculum;EscalationStateLedger x;bool bad=x.apply({1,3,InvoiceAction::resolve});bool a=x.apply({1,3,InvoiceAction::open});bool repeat=x.apply({2,3,InvoiceAction::open});return !bad&&a&&!repeat&&!x.nth_escalated(0)&&!x.final_overdue()?0:1;}
""",
        negative_old="if(!s.escalated){s.escalated=true;transitions_.push_back(e.invoice);}",
        negative_new="if(!s.escalated){s.escalated=true;}",
        negative_reason="forgets escalation occurrence history",
    ),
    _case(
        legacy_id="occurrence-lab-sample",
        task_id="calibration-run-index",
        title="Calibration Run Index",
        objective="Index maximal runs of consecutive calibrated measurements above a threshold and select the nth run or final run.",
        mechanism="maximal-run segmentation with gap-sensitive closure",
        public_api="vector<Run> build_runs(vector<Measurement>, int); optional<Run> nth_run(...); optional<Run> final_run(...) const",
        boundary="Positions must strictly increase; invalid measurements split runs and a threshold-equal value qualifies.",
        header=r"""#ifndef TASK_H
#define TASK_H
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum { struct Measurement{int position;int value;bool valid;bool calibrated;}; struct Run{int first;int last;std::size_t count;}; class CalibrationRunIndex{std::vector<Run> runs_;bool valid_;public:CalibrationRunIndex(const std::vector<Measurement>& rows,int threshold);bool valid()const{return valid_;}std::optional<Run> nth_run(std::size_t ordinal)const;std::optional<Run> final_run()const;}; }
#endif
""",
        reference=r"""#include "task.h"
namespace curriculum {
CalibrationRunIndex::CalibrationRunIndex(const std::vector<Measurement>& rows,int threshold):valid_(true){int prior=-1;Run current{0,0,0};for(const auto& x:rows){if(x.position<=prior){valid_=false;runs_.clear();return;}prior=x.position;const bool good=x.valid&&x.calibrated&&x.value>=threshold;if(good){if(current.count==0U)current.first=x.position;current.last=x.position;++current.count;}else if(current.count){runs_.push_back(current);current={0,0,0};}}if(current.count)runs_.push_back(current);}
std::optional<Run> CalibrationRunIndex::nth_run(std::size_t n)const{if(!valid_||n==0U||n>runs_.size())return{};return runs_[n-1U];}
std::optional<Run> CalibrationRunIndex::final_run()const{if(!valid_||runs_.empty())return{};return runs_.back();}
}
""",
        visible_test=r"""#include "task.h"
int main(){using namespace curriculum;CalibrationRunIndex x({{1,5,true,true},{2,6,true,true},{3,9,false,true},{4,7,true,true}},5);auto a=x.nth_run(1),f=x.final_run();return x.valid()&&a&&a->count==2&&f&&f->first==4?0:1;}
""",
        hidden_test=r"""#include "task.h"
int main(){using namespace curriculum;CalibrationRunIndex empty({},3),bad({{2,4,true,true},{1,5,true,true}},3);return empty.valid()&&!empty.final_run()&&!empty.nth_run(0)&&!bad.valid()&&!bad.final_run()?0:1;}
""",
        negative_old="x.value>=threshold",
        negative_new="x.value>threshold",
        negative_reason="drops threshold-equal measurements",
    ),
    _case(
        legacy_id="occurrence-transit-stop",
        task_id="accessible-route-occurrences",
        title="Accessible Route Occurrences",
        objective="Traverse a directed route graph from an origin and select the nth reachable accessible stop in BFS order or the final reachable transfer stop.",
        mechanism="stable adjacency breadth-first reachability traversal",
        public_api="bool add_stop(Stop); bool add_leg(int,int); optional<int> nth_accessible(int,size_t) const; optional<int> final_transfer(int) const",
        boundary="Stop IDs are unique; legs require known endpoints; neighbor visitation follows insertion order and cycles are visited once.",
        header=r"""#ifndef TASK_H
#define TASK_H
#include <cstddef>
#include <map>
#include <optional>
#include <vector>
namespace curriculum {struct Stop{int id;bool accessible;bool transfer;bool cancelled;};class AccessibleRouteOccurrences{std::map<int,Stop> stops_;std::map<int,std::vector<int>> edges_;public:bool add_stop(Stop stop);bool add_leg(int from,int to);std::optional<int> nth_accessible(int origin,std::size_t ordinal)const;std::optional<int> final_transfer(int origin)const;};}
#endif
""",
        reference=r"""#include "task.h"
#include <queue>
#include <set>
namespace curriculum {bool AccessibleRouteOccurrences::add_stop(Stop s){return s.id>=0&&stops_.emplace(s.id,s).second;}bool AccessibleRouteOccurrences::add_leg(int a,int b){if(!stops_.count(a)||!stops_.count(b))return false;edges_[a].push_back(b);return true;}
static std::vector<int> walk(const std::map<int,Stop>& stops,const std::map<int,std::vector<int>>& edges,int origin){if(!stops.count(origin))return{};std::queue<int> q;std::set<int> seen;std::vector<int> out;q.push(origin);seen.insert(origin);while(!q.empty()){int id=q.front();q.pop();out.push_back(id);auto it=edges.find(id);if(it!=edges.end())for(int n:it->second)if(seen.insert(n).second)q.push(n);}return out;}
std::optional<int> AccessibleRouteOccurrences::nth_accessible(int origin,std::size_t n)const{if(n==0U)return{};for(int id:walk(stops_,edges_,origin)){const auto& s=stops_.at(id);if(s.accessible&&!s.cancelled&&--n==0U)return id;}return{};}
std::optional<int> AccessibleRouteOccurrences::final_transfer(int origin)const{std::optional<int> out;for(int id:walk(stops_,edges_,origin)){const auto& s=stops_.at(id);if(s.transfer&&!s.cancelled)out=id;}return out;}}
""",
        visible_test=r"""#include "task.h"
int main(){using namespace curriculum;AccessibleRouteOccurrences g;g.add_stop({1,true,false,false});g.add_stop({2,true,true,false});g.add_stop({3,true,true,false});g.add_leg(1,2);g.add_leg(1,3);auto n=g.nth_accessible(1,2),f=g.final_transfer(1);return n&&*n==2&&f&&*f==3?0:1;}
""",
        hidden_test=r"""#include "task.h"
int main(){using namespace curriculum;AccessibleRouteOccurrences g;bool a=g.add_stop({1,true,false,false});bool d=g.add_stop({1,true,false,false});bool e=g.add_leg(1,9);g.add_stop({2,false,true,true});g.add_leg(1,2);return a&&!d&&!e&&!g.nth_accessible(9,1)&&!g.nth_accessible(1,0)&&!g.final_transfer(1)?0:1;}
""",
        negative_old="seen.insert(n).second",
        negative_new="seen.count(n)>0U",
        negative_reason="enqueues only already-visited neighbors",
    ),
    _case(
        legacy_id="occurrence-quality-audit",
        task_id="defect-episode-audit",
        title="Defect Episode Audit",
        objective="Fold open, severity-change, and remediation findings into defect episodes and select the nth still-open episode by class or final critical episode.",
        mechanism="keyed episode state machine with ordered closure",
        public_api="bool ingest(Finding); optional<Episode> nth_open(int,size_t) const; optional<Episode> final_critical(int) const",
        boundary="Sequences strictly increase; opening an existing item or updating a closed item is invalid without partial mutation.",
        header=r"""#ifndef TASK_H
#define TASK_H
#include <cstddef>
#include <map>
#include <optional>
namespace curriculum {enum class FindingAction{open,raise,remediate};struct Finding{int sequence;int item;int kind;int severity;FindingAction action;};struct Episode{int item;int opened;int severity;};class DefectEpisodeAudit{struct State{int kind;int opened;int severity;bool open;};std::map<int,State> states_;int last_=-1;public:bool ingest(Finding finding);std::optional<Episode> nth_open(int kind,std::size_t ordinal)const;std::optional<Episode> final_critical(int minimum)const;};}
#endif
""",
        reference=r"""#include "task.h"
namespace curriculum {bool DefectEpisodeAudit::ingest(Finding f){if(f.sequence<=last_||f.item<0||f.severity<0)return false;auto next=states_;auto it=next.find(f.item);if(f.action==FindingAction::open){if(it!=next.end()&&it->second.open)return false;next[f.item]={f.kind,f.sequence,f.severity,true};}else{if(it==next.end()||!it->second.open)return false;if(f.action==FindingAction::raise)it->second.severity=f.severity;else it->second.open=false;}states_=next;last_=f.sequence;return true;}
std::optional<Episode> DefectEpisodeAudit::nth_open(int kind,std::size_t n)const{if(n==0U)return{};for(const auto& [id,s]:states_)if(s.open&&s.kind==kind&&--n==0U)return Episode{id,s.opened,s.severity};return{};}
std::optional<Episode> DefectEpisodeAudit::final_critical(int minimum)const{std::optional<Episode> out;for(const auto& [id,s]:states_)if(s.open&&s.severity>=minimum&&(!out||s.opened>out->opened))out=Episode{id,s.opened,s.severity};return out;}}
""",
        visible_test=r"""#include "task.h"
int main(){using namespace curriculum;DefectEpisodeAudit a;a.ingest({1,4,2,3,FindingAction::open});a.ingest({2,8,2,7,FindingAction::open});auto n=a.nth_open(2,2),f=a.final_critical(5);return n&&n->item==8&&f&&f->item==8?0:1;}
""",
        hidden_test=r"""#include "task.h"
int main(){using namespace curriculum;DefectEpisodeAudit a;bool bad=a.ingest({1,3,1,2,FindingAction::remediate});bool ok=a.ingest({1,3,1,2,FindingAction::open});bool close=a.ingest({2,3,1,2,FindingAction::remediate});bool reopen=a.ingest({3,3,1,4,FindingAction::open});return !bad&&ok&&close&&reopen&&!a.nth_open(1,0)&&!a.final_critical(9)?0:1;}
""",
        negative_old="it->second.open=false",
        negative_new="it->second.severity=0",
        negative_reason="remediation leaves an episode open",
    ),
    _case(
        legacy_id="occurrence-support-breach",
        task_id="sla-window-crossings",
        title="SLA Window Crossings",
        objective="Maintain a fixed-width rolling breach score, record upward threshold crossings, and query the nth crossing or whether the final window remains breached.",
        mechanism="rolling-window sum with edge-triggered crossing history",
        public_api="explicit Tracker(size_t,int); bool push(Sample); optional<int> nth_crossing(size_t) const; optional<int> final_active() const",
        boundary="Width and limit are positive; sample sequences strictly increase; remaining above the limit does not create repeated crossings.",
        header=r"""#ifndef TASK_H
#define TASK_H
#include <cstddef>
#include <deque>
#include <optional>
#include <vector>
namespace curriculum {struct BreachSample{int sequence;int weight;};class SlaWindowCrossings{std::size_t width_;int limit_;int total_=0;int last_=-1;bool active_=false;bool valid_;std::deque<BreachSample> window_;std::vector<int> crossings_;public:SlaWindowCrossings(std::size_t width,int limit);bool valid()const{return valid_;}bool push(BreachSample sample);std::optional<int> nth_crossing(std::size_t ordinal)const;std::optional<int> final_active()const;};}
#endif
""",
        reference=r"""#include "task.h"
namespace curriculum {SlaWindowCrossings::SlaWindowCrossings(std::size_t w,int l):width_(w),limit_(l),valid_(w>0U&&l>0){}
bool SlaWindowCrossings::push(BreachSample s){if(!valid_||s.sequence<=last_||s.weight<0)return false;window_.push_back(s);total_+=s.weight;if(window_.size()>width_){total_-=window_.front().weight;window_.pop_front();}const bool now=total_>=limit_;if(now&&!active_)crossings_.push_back(s.sequence);active_=now;last_=s.sequence;return true;}
std::optional<int> SlaWindowCrossings::nth_crossing(std::size_t n)const{if(n==0U||n>crossings_.size())return{};return crossings_[n-1U];}
std::optional<int> SlaWindowCrossings::final_active()const{if(!active_||window_.empty())return{};return window_.back().sequence;}}
""",
        visible_test=r"""#include "task.h"
int main(){using namespace curriculum;SlaWindowCrossings t(2,5);t.push({1,2});t.push({2,3});t.push({3,3});t.push({4,0});t.push({5,5});auto a=t.nth_crossing(1),b=t.nth_crossing(2),f=t.final_active();return a&&*a==2&&b&&*b==5&&f&&*f==5?0:1;}
""",
        hidden_test=r"""#include "task.h"
int main(){using namespace curriculum;SlaWindowCrossings bad(0,3),t(1,2);bool a=t.push({1,2});bool stale=t.push({1,3});return !bad.valid()&&a&&!stale&&!t.nth_crossing(0)&&t.final_active()?0:1;}
""",
        negative_old="if(now&&!active_)",
        negative_new="if(now)",
        negative_reason="records every breached sample instead of upward crossings",
    ),
    _case(
        legacy_id="occurrence-sports-qualifier",
        task_id="athlete-record-board",
        title="Athlete Record Board",
        objective="Track per-athlete personal-best improvements, select the nth record event, and return the final eligible athlete by score and stable event order.",
        mechanism="per-key maximum index plus chronological record log",
        public_api="bool submit(Attempt); optional<Record> nth_record(size_t) const; optional<Record> final_eligible(int) const",
        boundary="Event IDs strictly increase; disqualified attempts never improve a record; equal scores are not new records.",
        header=r"""#ifndef TASK_H
#define TASK_H
#include <cstddef>
#include <map>
#include <optional>
#include <vector>
namespace curriculum {struct Attempt{int event;int athlete;int score;bool disqualified;};struct Record{int event;int athlete;int score;};class AthleteRecordBoard{std::map<int,int> best_;std::vector<Record> records_;int last_=-1;public:bool submit(Attempt attempt);std::optional<Record> nth_record(std::size_t ordinal)const;std::optional<Record> final_eligible(int minimum_score)const;};}
#endif
""",
        reference=r"""#include "task.h"
namespace curriculum {bool AthleteRecordBoard::submit(Attempt a){if(a.event<=last_||a.athlete<0||a.score<0)return false;last_=a.event;if(a.disqualified)return true;auto it=best_.find(a.athlete);if(it==best_.end()||a.score>it->second){best_[a.athlete]=a.score;records_.push_back({a.event,a.athlete,a.score});}return true;}
std::optional<Record> AthleteRecordBoard::nth_record(std::size_t n)const{if(n==0U||n>records_.size())return{};return records_[n-1U];}
std::optional<Record> AthleteRecordBoard::final_eligible(int minimum)const{std::optional<Record> out;for(const auto& r:records_)if(r.score>=minimum)out=r;return out;}}
""",
        visible_test=r"""#include "task.h"
int main(){using namespace curriculum;AthleteRecordBoard b;b.submit({1,7,10,false});b.submit({2,7,10,false});b.submit({3,8,12,false});auto n=b.nth_record(2),f=b.final_eligible(11);return n&&n->athlete==8&&f&&f->event==3?0:1;}
""",
        hidden_test=r"""#include "task.h"
int main(){using namespace curriculum;AthleteRecordBoard b;bool a=b.submit({1,2,4,true});bool stale=b.submit({1,2,9,false});return a&&!stale&&!b.nth_record(1)&&!b.nth_record(0)&&!b.final_eligible(0)?0:1;}
""",
        negative_old="a.score>it->second",
        negative_new="a.score>=it->second",
        negative_reason="counts score ties as record occurrences",
    ),
    _case(
        legacy_id="occurrence-library-hold",
        task_id="hold-dispatch-snapshot",
        title="Hold Dispatch Snapshot",
        objective="Validate a hold snapshot, rank ready holds by entitlement and request order, select the nth dispatch, and find the final expired hold by expiry time.",
        mechanism="snapshot validation with stable multi-key ordering",
        public_api="optional<Dispatch> nth_ready(vector<Hold>,int,size_t); optional<Dispatch> final_expired(vector<Hold>,int)",
        boundary="IDs and request order are unique; branch mismatch excludes a hold; ready ranking is priority descending then request ascending.",
        header=r"""#ifndef TASK_H
#define TASK_H
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum {struct Hold{int id;int branch;int request_order;int priority;int expires;bool eligible;bool ready;};struct Dispatch{int id;int rank_value;};class HoldDispatchSnapshot{public:static std::optional<Dispatch> nth_ready(const std::vector<Hold>& holds,int branch,std::size_t ordinal);static std::optional<Dispatch> final_expired(const std::vector<Hold>& holds,int as_of);};}
#endif
""",
        reference=r"""#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum {static bool valid(const std::vector<Hold>& hs){std::set<int> ids,orders;for(const auto& h:hs)if(h.id<0||!ids.insert(h.id).second||!orders.insert(h.request_order).second)return false;return true;}
std::optional<Dispatch> HoldDispatchSnapshot::nth_ready(const std::vector<Hold>& hs,int branch,std::size_t n){if(n==0U||!valid(hs))return{};std::vector<Hold> q;for(const auto& h:hs)if(h.branch==branch&&h.eligible&&h.ready)q.push_back(h);std::sort(q.begin(),q.end(),[](const Hold& a,const Hold& b){return a.priority!=b.priority?a.priority>b.priority:a.request_order<b.request_order;});if(n>q.size())return{};return Dispatch{q[n-1U].id,q[n-1U].priority};}
std::optional<Dispatch> HoldDispatchSnapshot::final_expired(const std::vector<Hold>& hs,int as_of){if(!valid(hs))return{};const Hold* pick=nullptr;for(const auto& h:hs)if(h.expires<=as_of&&(!pick||h.expires>pick->expires))pick=&h;return pick?std::optional<Dispatch>{{pick->id,pick->expires}}:std::nullopt;}}
""",
        visible_test=r"""#include "task.h"
int main(){using namespace curriculum;std::vector<Hold> h{{1,2,1,3,9,true,true},{2,2,2,7,5,true,true},{3,2,3,7,8,true,true}};auto n=HoldDispatchSnapshot::nth_ready(h,2,2),f=HoldDispatchSnapshot::final_expired(h,8);return n&&n->id==3&&f&&f->id==3?0:1;}
""",
        hidden_test=r"""#include "task.h"
int main(){using namespace curriculum;std::vector<Hold> bad{{1,2,1,3,9,true,true},{1,2,2,4,8,true,true}};return !HoldDispatchSnapshot::nth_ready(bad,2,1)&&!HoldDispatchSnapshot::nth_ready({},2,0)&&!HoldDispatchSnapshot::final_expired({},9)?0:1;}
""",
        negative_old="a.priority>b.priority",
        negative_new="a.priority<b.priority",
        negative_reason="dispatches lowest priority first",
    ),
    _case(
        legacy_id="occurrence-security-alert",
        task_id="alert-retention-ring",
        title="Alert Retention Ring",
        objective="Own a bounded alert ring, overwrite the oldest slot, mutate acknowledgement/suppression state, and query nth reviewable or final critical retained alert.",
        mechanism="fixed-capacity circular retention buffer with logical-order scan",
        public_api="explicit Ring(size_t); bool push(Alert); bool acknowledge(int); bool suppress(int); optional<int> nth_review(size_t,int) const; optional<int> final_critical(int) const",
        boundary="Capacity is positive; alert IDs are nonnegative and unique while retained; queries use oldest-to-newest logical order.",
        header=r"""#ifndef TASK_H
#define TASK_H
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum {struct Alert{int id;int category;int severity;bool acknowledged;bool suppressed;};class AlertRetentionRing{std::vector<Alert> slots_;std::size_t capacity_;std::size_t start_=0;public:explicit AlertRetentionRing(std::size_t capacity);bool valid()const{return capacity_>0U;}bool push(Alert alert);bool acknowledge(int id);bool suppress(int id);std::optional<int> nth_review(std::size_t ordinal,int category)const;std::optional<int> final_critical(int minimum)const;};}
#endif
""",
        reference=r"""#include "task.h"
namespace curriculum {AlertRetentionRing::AlertRetentionRing(std::size_t c):capacity_(c){}bool AlertRetentionRing::push(Alert a){if(!valid()||a.id<0)return false;for(const auto& x:slots_)if(x.id==a.id)return false;if(slots_.size()<capacity_)slots_.push_back(a);else{slots_[start_]=a;start_=(start_+1U)%capacity_;}return true;}
bool AlertRetentionRing::acknowledge(int id){for(auto& x:slots_)if(x.id==id){x.acknowledged=true;return true;}return false;}bool AlertRetentionRing::suppress(int id){for(auto& x:slots_)if(x.id==id){x.suppressed=true;return true;}return false;}
std::optional<int> AlertRetentionRing::nth_review(std::size_t n,int category)const{if(n==0U)return{};for(std::size_t i=0;i<slots_.size();++i){const auto& x=slots_[(start_+i)%slots_.size()];if(x.category==category&&!x.acknowledged&&!x.suppressed&&--n==0U)return x.id;}return{};}
std::optional<int> AlertRetentionRing::final_critical(int minimum)const{std::optional<int> out;for(std::size_t i=0;i<slots_.size();++i){const auto& x=slots_[(start_+i)%slots_.size()];if(x.severity>=minimum&&!x.acknowledged&&!x.suppressed)out=x.id;}return out;}}
""",
        visible_test=r"""#include "task.h"
int main(){using namespace curriculum;AlertRetentionRing r(2);r.push({1,4,3,false,false});r.push({2,4,8,false,false});r.push({3,4,9,false,false});auto n=r.nth_review(1,4),f=r.final_critical(7);return n&&*n==2&&f&&*f==3?0:1;}
""",
        hidden_test=r"""#include "task.h"
int main(){using namespace curriculum;AlertRetentionRing bad(0),r(2);bool a=r.push({1,2,5,false,false});bool dup=r.push({1,2,6,false,false});bool ack=r.acknowledge(1);return !bad.valid()&&a&&!dup&&ack&&!r.nth_review(1,2)&&!r.nth_review(0,2)&&!r.final_critical(1)?0:1;}
""",
        negative_old="start_=(start_+1U)%capacity_",
        negative_new="start_=0U",
        negative_reason="loses circular overwrite order after wraparound",
    ),
    _case(
        legacy_id="occurrence-maintenance-log",
        task_id="maintenance-cycle-ledger",
        title="Maintenance Cycle Ledger",
        objective="Validate periodic maintenance completions, map them to due cycles, select the nth satisfied cycle, and report the final overdue unsatisfied cycle.",
        mechanism="periodic due-cycle expansion with one-completion-per-cycle matching",
        public_api="Audit inspect(Plan,vector<Completion>,int); optional<int> nth_satisfied(Audit,size_t); optional<int> final_overdue(Audit)",
        boundary="Period is positive; completion times strictly increase and each completion satisfies at most its earliest unmatched due cycle.",
        header=r"""#ifndef TASK_H
#define TASK_H
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum {struct MaintenancePlan{int first_due;int period;int tolerance;};struct Completion{int time;};struct Cycle{int due;bool satisfied;};struct MaintenanceAudit{bool valid;std::vector<Cycle> cycles;};class MaintenanceCycleLedger{public:static MaintenanceAudit inspect(MaintenancePlan plan,const std::vector<Completion>& completions,int as_of);static std::optional<int> nth_satisfied(const MaintenanceAudit& audit,std::size_t ordinal);static std::optional<int> final_overdue(const MaintenanceAudit& audit);};}
#endif
""",
        reference=r"""#include "task.h"
namespace curriculum {MaintenanceAudit MaintenanceCycleLedger::inspect(MaintenancePlan p,const std::vector<Completion>& cs,int as_of){if(p.period<=0||p.tolerance<0)return{false,{}};int prior=-1;for(const auto& c:cs)if(c.time<=prior)return{false,{}};else prior=c.time;MaintenanceAudit out{true,{}};std::size_t next=0;for(int due=p.first_due;due<=as_of;due+=p.period){bool hit=false;while(next<cs.size()&&cs[next].time<due-p.tolerance)++next;if(next<cs.size()&&cs[next].time<=due+p.tolerance){hit=true;++next;}out.cycles.push_back({due,hit});}return out;}
std::optional<int> MaintenanceCycleLedger::nth_satisfied(const MaintenanceAudit& a,std::size_t n){if(!a.valid||n==0U)return{};for(const auto& c:a.cycles)if(c.satisfied&&--n==0U)return c.due;return{};}
std::optional<int> MaintenanceCycleLedger::final_overdue(const MaintenanceAudit& a){if(!a.valid)return{};std::optional<int> out;for(const auto& c:a.cycles)if(!c.satisfied)out=c.due;return out;}}
""",
        visible_test=r"""#include "task.h"
int main(){using namespace curriculum;auto a=MaintenanceCycleLedger::inspect({10,5,1},{{9},{16}},20);auto n=MaintenanceCycleLedger::nth_satisfied(a,2),f=MaintenanceCycleLedger::final_overdue(a);return a.valid&&n&&*n==15&&f&&*f==20?0:1;}
""",
        hidden_test=r"""#include "task.h"
int main(){using namespace curriculum;auto bad=MaintenanceCycleLedger::inspect({1,0,0},{},5);auto order=MaintenanceCycleLedger::inspect({5,3,0},{{4},{3}},10);auto empty=MaintenanceCycleLedger::inspect({20,3,0},{},10);return !bad.valid&&!order.valid&&empty.valid&&!MaintenanceCycleLedger::nth_satisfied(empty,0)&&!MaintenanceCycleLedger::final_overdue(empty)?0:1;}
""",
        negative_old="cs[next].time<=due+p.tolerance",
        negative_new="cs[next].time<due+p.tolerance",
        negative_reason="rejects completion exactly on the tolerance boundary",
    ),
)
