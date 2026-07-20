"""Independent traces and false substitutes for ordered-registry remediation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationCase:
    logic: str
    state: str
    mutation: str
    selection: str
    boundary: str
    false_name: str
    false_old: str
    false_new: str
    trace: str


def _trace(class_name: str, body: str, extra: str = "") -> str:
    return f'''#include "task.h"
#include <algorithm>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <tuple>
#include <utility>
#include <vector>
{extra}
int main() {{
  int failures=0; const auto check=[&](bool ok){{if(!ok)++failures;}};
  using curriculum::{class_name};
  {body}
  return failures==0?0:1;
}}
'''


CASES: dict[str, VerificationCase] = {
    "registry-audit-retention": VerificationCase(
        "hold-gated expiry collection", "ordered record map with orthogonal hold bit",
        "conditional erase after mutable hold transition", "expiry then identity ordering",
        "expiry equality with non-mutating held rejection", "ignores-legal-hold",
        "it->second.held||it->second.expires>today", "it->second.expires>today",
        _trace("AuditRetentionLedger", r'''AuditRetentionLedger x; std::map<int,std::pair<int,bool>> model;
  auto audit=[&](){for(int id=1;id<=4;++id){auto it=model.find(id);check(x.expiry(id)==(it==model.end()?std::nullopt:std::optional<int>(it->second.first)));}for(int t:{0,4,8,12}){std::vector<std::pair<int,int>> q;for(auto [id,r]:model)if(!r.second&&r.first<=t)q.push_back({r.first,id});std::sort(q.begin(),q.end());std::vector<int> e;for(auto p:q)e.push_back(p.second);check(x.eligible(t)==e);}};
  auto add=[&](int id,int due){bool e=id>0&&due>=0&&!model.count(id);check(x.add(id,due)==e);if(e)model[id]={due,false};audit();};
  auto hold=[&](int id,bool value){bool e=model.count(id);check(x.set_hold(id,value)==e);if(e)model[id].second=value;audit();};
  auto erase=[&](int id,int now){auto it=model.find(id);bool e=it!=model.end()&&!it->second.second&&it->second.first<=now;check(x.erase_if_eligible(id,now)==e);if(e)model.erase(id);audit();};
  add(2,8);add(1,4);add(1,9);hold(2,true);erase(2,12);hold(2,false);erase(2,8);erase(9,8);'''),
    ),
    "customs-clearance-workflow": VerificationCase(
        "finite declaration state machine", "map of immutable lane/deadline plus enum stage",
        "guarded filed-inspected-cleared transitions", "deadline then identity pending order",
        "no transition skipping or replay", "permits-direct-clearance",
        "it->second.stage!=ClearanceStage::inspected", "it->second.stage!=ClearanceStage::filed",
        _trace("CustomsClearanceWorkflow", r'''using curriculum::ClearanceStage; CustomsClearanceWorkflow x; struct M{std::string lane;int due;ClearanceStage stage;};std::map<int,M> model;
  auto audit=[&](){for(int id=1;id<=4;++id){auto it=model.find(id);check(x.stage(id)==(it==model.end()?std::nullopt:std::optional<ClearanceStage>(it->second.stage)));}for(std::string lane:{"red","green"}){std::vector<std::pair<int,int>> q;for(auto [id,d]:model)if(d.lane==lane&&d.stage!=ClearanceStage::cleared)q.push_back({d.due,id});std::sort(q.begin(),q.end());std::vector<int> e;for(auto p:q)e.push_back(p.second);check(x.pending(lane)==e);}};
  auto file=[&](int id,std::string lane,int due){bool e=id>0&&!lane.empty()&&due>=0&&!model.count(id);check(x.file(id,lane,due)==e);if(e)model[id]={lane,due,ClearanceStage::filed};audit();};
  auto inspect=[&](int id){auto it=model.find(id);bool e=it!=model.end()&&it->second.stage==ClearanceStage::filed;check(x.inspect(id)==e);if(e)it->second.stage=ClearanceStage::inspected;audit();};
  auto clear=[&](int id){auto it=model.find(id);bool e=it!=model.end()&&it->second.stage==ClearanceStage::inspected;check(x.clear(id)==e);if(e)it->second.stage=ClearanceStage::cleared;audit();};
  file(2,"red",9);file(1,"red",4);clear(1);inspect(1);inspect(1);clear(1);clear(1);file(3,"green",0);'''),
    ),
    "triage-priority-board": VerificationCase(
        "mutable clinical priority selection", "arrival-preserving patient vector",
        "in-place severity update and selected erase", "severity descending then arrival and identity",
        "bounded severity with empty extraction", "uses-lowest-severity-first",
        "return as!=bs?as>bs", "return as!=bs?as<bs",
        _trace("TriagePriorityBoard", r'''TriagePriorityBoard x;struct M{int id,severity,arrival;};std::vector<M> model;
  auto order=[&](){auto v=model;std::sort(v.begin(),v.end(),[](auto a,auto b){return a.severity!=b.severity?a.severity>b.severity:(a.arrival!=b.arrival?a.arrival<b.arrival:a.id<b.id);});std::vector<int> out;for(auto p:v)out.push_back(p.id);return out;};auto audit=[&](){check(x.waiting_order()==order());};
  auto arrive=[&](int id,int s,int at){bool e=id>0&&s>=1&&s<=5&&at>=0&&std::none_of(model.begin(),model.end(),[&](auto p){return p.id==id;});check(x.arrive(id,s,at)==e);if(e)model.push_back({id,s,at});audit();};
  auto reprio=[&](int id,int s){auto it=std::find_if(model.begin(),model.end(),[&](auto p){return p.id==id;});bool e=it!=model.end()&&s>=1&&s<=5;check(x.reprioritize(id,s)==e);if(e)it->severity=s;audit();};
  auto treat=[&](){auto o=order();auto e=o.empty()?std::nullopt:std::optional<int>(o.front());check(x.treat_next()==e);if(e)model.erase(std::find_if(model.begin(),model.end(),[&](auto p){return p.id==*e;}));audit();};
  treat();arrive(2,2,1);arrive(1,2,1);arrive(3,5,9);arrive(3,1,0);reprio(2,5);reprio(9,3);treat();treat();'''),
    ),
    "session-seat-waitlist": VerificationCase(
        "capacity admission with promotion", "per-session seats and timestamped queue plus owner index",
        "cancel-promote and cross-session transfer", "request stamp then attendee wait order",
        "zero capacity and atomic ownership", "drops-promotion-on-cancel",
        "if(!s.waiting.empty()){s.seated.push_back", "if(false&&!s.waiting.empty()){s.seated.push_back",
        _trace("SessionSeatWaitlist", r'''SessionSeatWaitlist x;struct R{int id,stamp;};struct S{std::size_t cap;std::vector<int> seats;std::vector<R> wait;};std::map<std::string,S> model;std::map<int,std::string> owner;
  auto audit=[&](){for(std::string n:{"a","b"}){std::vector<int>w;if(model.count(n))for(auto r:model[n].wait)w.push_back(r.id);check(x.waiting(n)==w);check(x.seated(n)==(model.count(n)?model[n].seats:std::vector<int>{}));}};auto insert=[&](S&s,int id,int stamp){if(s.seats.size()<s.cap)s.seats.push_back(id);else{s.wait.push_back({id,stamp});std::sort(s.wait.begin(),s.wait.end(),[](auto a,auto b){return a.stamp!=b.stamp?a.stamp<b.stamp:a.id<b.id;});}};
  auto config=[&](std::string n,std::size_t c){bool e=!n.empty()&&!model.count(n);check(x.configure(n,c)==e);if(e)model[n]={c,{},{}};audit();};auto request=[&](std::string n,int id,int stamp){bool e=model.count(n)&&id>0&&stamp>=0&&!owner.count(id);check(x.request(n,id,stamp)==e);if(e){insert(model[n],id,stamp);owner[id]=n;}audit();};
  auto cancel=[&](std::string n,int id){bool e=model.count(n)&&owner.count(id)&&owner[id]==n;check(x.cancel(n,id)==e);if(e){auto&s=model[n];auto it=std::find(s.seats.begin(),s.seats.end(),id);if(it!=s.seats.end()){s.seats.erase(it);if(!s.wait.empty()){s.seats.push_back(s.wait.front().id);s.wait.erase(s.wait.begin());}}else s.wait.erase(std::remove_if(s.wait.begin(),s.wait.end(),[&](auto r){return r.id==id;}),s.wait.end());owner.erase(id);}audit();};
  auto transfer=[&](std::string a,std::string b,int id,int stamp){bool e=model.count(a)&&model.count(b)&&owner.count(id)&&owner[id]==a&&stamp>=0;check(x.transfer(a,b,id,stamp)==e);if(e){auto&s=model[a];auto si=std::find(s.seats.begin(),s.seats.end(),id);if(si!=s.seats.end()){s.seats.erase(si);if(!s.wait.empty()){s.seats.push_back(s.wait.front().id);s.wait.erase(s.wait.begin());}}else s.wait.erase(std::remove_if(s.wait.begin(),s.wait.end(),[&](auto r){return r.id==id;}),s.wait.end());insert(model[b],id,stamp);owner[id]=b;}audit();};
  config("a",1);config("b",1);request("a",1,5);request("a",2,3);request("a",3,4);cancel("a",1);transfer("a","b",2,8);cancel("a",9);'''),
    ),
    "device-heartbeat-index": VerificationCase(
        "monotonic temporal index", "identity map of ring and last-seen value",
        "forward heartbeat and ring-only move", "last-seen then identity stale order",
        "strict cutoff and backward-time rejection", "accepts-backward-heartbeat",
        "seen<it->second.seen", "seen<0",
        _trace("DeviceHeartbeatIndex", r'''DeviceHeartbeatIndex x;struct M{std::string ring;int seen;};std::map<int,M> model;auto audit=[&](){for(std::string r:{"a","b"}){std::vector<int>e;for(auto [id,d]:model)if(d.ring==r)e.push_back(id);check(x.in_ring(r)==e);}for(int t:{0,5,9}){std::vector<std::pair<int,int>>q;for(auto[id,d]:model)if(d.seen<t)q.push_back({d.seen,id});std::sort(q.begin(),q.end());std::vector<int>e;for(auto p:q)e.push_back(p.second);check(x.stale_before(t)==e);}};
  auto enroll=[&](int id,std::string r,int seen){bool e=id>0&&!r.empty()&&seen>=0&&!model.count(id);check(x.enroll(id,r,seen)==e);if(e)model[id]={r,seen};audit();};auto beat=[&](int id,int seen){auto it=model.find(id);bool e=it!=model.end()&&seen>=it->second.seen;check(x.heartbeat(id,seen)==e);if(e)it->second.seen=seen;audit();};auto move=[&](int id,std::string r){bool e=model.count(id)&&!r.empty();check(x.move(id,r)==e);if(e)model[id].ring=r;audit();};
  enroll(2,"a",8);enroll(1,"b",4);enroll(1,"a",9);beat(1,3);beat(1,9);move(1,"a");move(9,"b");'''),
    ),
    "rollout-token-ring": VerificationCase(
        "clockwise consistent-hash routing", "ordered token-to-cohort ring",
        "atomic token relocation without account state", "lower-bound successor with cyclic wrap",
        "empty ring and 359-to-zero wraparound", "drops-clockwise-wraparound",
        "if(it==ring_.end())it=ring_.begin()", "if(it==ring_.end())return std::nullopt",
        _trace("RolloutTokenRing", r'''RolloutTokenRing x;std::map<int,std::string>ring;auto routed=[&](int account){if(account<0||ring.empty())return std::optional<std::string>{};auto it=ring.lower_bound(account%360);if(it==ring.end())it=ring.begin();return std::optional<std::string>(it->second);};auto audit=[&](){for(int account:{0,59,60,100,300,359})check(x.route(account)==routed(account));for(std::string c:{"a","b"}){std::vector<int>e;for(auto[t,n]:ring)if(n==c)e.push_back(t);check(x.tokens_for(c)==e);}};auto add=[&](int token,std::string c){bool e=token>=0&&token<360&&!c.empty()&&!ring.count(token);check(x.add_token(token,c)==e);if(e)ring[token]=c;audit();};auto move=[&](int token,int replacement){bool e=ring.count(token)&&replacement>=0&&replacement<360&&!ring.count(replacement);check(x.move_token(token,replacement)==e);if(e){auto c=ring[token];ring.erase(token);ring[replacement]=c;}audit();};auto remove=[&](int token){bool e=ring.erase(token)==1;check(x.remove_token(token)==e);audit();};add(300,"a");add(60,"b");add(60,"a");move(60,90);move(9,10);remove(300);remove(300);'''),
    ),
    "gate-conflict-scheduler": VerificationCase(
        "compatibility-filtered interval placement", "gate type sets plus flight interval map",
        "atomic placement and relocation", "future start then identity selection",
        "half-open touching and invalid interval", "treats-touching-stays-as-conflicts",
        "f.start<o.end&&o.start<f.end", "f.start<=o.end&&o.start<=f.end",
        _trace("GateConflictScheduler", r'''GateConflictScheduler x;struct F{std::string type;int start,end;std::string gate;};std::map<std::string,std::set<std::string>>gates;std::map<int,F>flights;auto fits=[&](int ignore,F f){if(!gates.count(f.gate)||!gates[f.gate].count(f.type))return false;for(auto[id,o]:flights)if(id!=ignore&&o.gate==f.gate&&f.start<o.end&&o.start<f.end)return false;return true;};auto audit=[&](){for(std::string g:{"g1","g2"})for(int after:{0,10,20}){std::optional<std::pair<int,int>>b;for(auto[id,f]:flights)if(f.gate==g&&f.start>=after&&(!b||std::pair<int,int>{f.start,id}<*b))b={f.start,id};check(x.next_departure(g,after)==(b?std::optional<int>(b->second):std::nullopt));}};auto add=[&](std::string g,std::vector<std::string>t){bool e=!g.empty()&&!t.empty()&&!gates.count(g)&&std::all_of(t.begin(),t.end(),[](auto&s){return !s.empty();});check(x.add_gate(g,t)==e);if(e)gates[g]={t.begin(),t.end()};audit();};auto schedule=[&](int id,std::string t,int s,int e,std::string g){F f{t,s,e,g};bool ok=id>0&&s>=0&&s<e&&!flights.count(id)&&fits(id,f);check(x.schedule(id,t,s,e,g)==ok);if(ok)flights[id]=f;audit();};auto move=[&](int id,std::string g){bool ok=flights.count(id);F f;if(ok){f=flights[id];f.gate=g;ok=fits(id,f);}check(x.move(id,g)==ok);if(ok)flights[id]=f;audit();};auto depart=[&](int id){bool e=flights.erase(id)==1;check(x.depart(id)==e);audit();};add("g1",{"jet"});add("g2",{"jet","prop"});schedule(1,"jet",0,10,"g1");schedule(2,"jet",10,20,"g1");schedule(3,"jet",9,11,"g1");move(2,"g2");move(1,"missing");depart(1);depart(9);'''),
    ),
    "dish-allergen-catalog": VerificationCase(
        "canonical set disjointness", "dish map of deduplicated allergen sets",
        "validated whole-set replacement", "lexical dish and allergen ordering",
        "empty forbidden set and invalid empty allergen", "ignores-forbidden-allergens",
        "if(a.count(x)){safe=false", "if(false&&a.count(x)){safe=false",
        _trace("DishAllergenCatalog", r'''DishAllergenCatalog x;std::map<std::string,std::set<std::string>>model;auto canon=[](std::vector<std::string>v){std::optional<std::set<std::string>>o=std::set<std::string>{};for(auto&s:v)if(s.empty())return std::optional<std::set<std::string>>{};else o->insert(s);return o;};auto audit=[&](){for(std::string d:{"rice","soup","pie"}){auto it=model.find(d);check(x.allergens_of(d)==(it==model.end()?std::nullopt:std::optional<std::vector<std::string>>(std::vector<std::string>(it->second.begin(),it->second.end()))));}for(auto f:std::vector<std::vector<std::string>>{{},{"milk"},{"nut","soy"}}){auto c=canon(f);std::vector<std::string>e;if(c)for(auto[d,a]:model){bool safe=true;for(auto&s:*c)if(a.count(s))safe=false;if(safe)e.push_back(d);}check(x.safe_for(f)==e);}};auto add=[&](std::string d,std::vector<std::string>a){auto c=canon(a);bool e=!d.empty()&&c&&!model.count(d);check(x.add(d,a)==e);if(e)model[d]=*c;audit();};auto replace=[&](std::string d,std::vector<std::string>a){auto c=canon(a);bool e=model.count(d)&&c;check(x.replace_recipe(d,a)==e);if(e)model[d]=*c;audit();};auto erase=[&](std::string d){bool e=model.erase(d)==1;check(x.erase(d)==e);audit();};add("soup",{"milk","milk"});add("rice",{});add("pie",{""});replace("soup",{"soy"});replace("missing",{});erase("rice");erase("rice");'''),
    ),
    "proposal-review-matcher": VerificationCase(
        "conflict-constrained bipartite matching", "proposal and two edge sets",
        "independent conflict and assignment edge updates", "review deficit then proposal identity",
        "duplicate edge and absent proposal", "allows-conflicted-reviewer",
        "!conflicts_.count({p,r})&&assignments_", "assignments_",
        _trace("ProposalReviewMatcher", r'''ProposalReviewMatcher x;std::set<int>p;std::set<std::pair<int,int>>conflicts,assigned;auto count=[&](int id){std::size_t n=0;for(auto e:assigned)if(e.first==id)++n;return n;};auto audit=[&](){for(int id=1;id<=4;++id)check(x.review_count(id)==count(id));for(std::size_t need:{0U,1U,2U}){std::vector<std::pair<std::size_t,int>>q;for(int id:p)if(count(id)<need)q.push_back({count(id),id});std::sort(q.begin(),q.end());std::vector<int>e;for(auto v:q)e.push_back(v.second);check(x.under_reviewed(need)==e);}};auto add=[&](int id){bool e=id>0&&p.insert(id).second;check(x.add_proposal(id)==e);audit();};auto conflict=[&](int id,int r){bool e=p.count(id)&&r>0&&conflicts.insert({id,r}).second;check(x.add_conflict(id,r)==e);audit();};auto assign=[&](int id,int r){bool e=p.count(id)&&r>0&&!conflicts.count({id,r})&&assigned.insert({id,r}).second;check(x.assign(id,r)==e);audit();};auto withdraw=[&](int id,int r){bool e=assigned.erase({id,r})==1;check(x.withdraw(id,r)==e);audit();};add(2);add(1);add(1);conflict(1,7);assign(1,7);assign(1,8);assign(2,8);withdraw(1,8);withdraw(1,8);'''),
    ),
    "room-stay-calendar": VerificationCase(
        "lowest-room interval calendar", "room classes, per-room stay vectors, reservation index",
        "first-fit booking and indexed cancellation", "lowest compatible room then earliest candidate time",
        "half-open adjacency and duration overflow", "uses-closed-interval-overlap",
        "start<s.end&&s.start<end", "start<=s.end&&s.start<=end",
        _trace("RoomStayCalendar", r'''RoomStayCalendar x;struct S{int reservation,start,end;};std::map<int,std::string>rooms;std::map<int,std::vector<S>>cal;std::map<int,int>res;auto free=[&](int r,int s,int e){for(auto v:cal[r])if(s<v.end&&v.start<e)return false;return true;};auto earliest=[&](std::string c,int from,int duration){if(c.empty()||from<0||duration<=0)return std::optional<int>{};std::vector<int>starts{from};for(auto[r,rc]:rooms)if(rc==c)for(auto s:cal[r])if(s.end>=from)starts.push_back(s.end);std::sort(starts.begin(),starts.end());for(int s:starts)for(auto[r,rc]:rooms)if(rc==c&&free(r,s,s+duration))return std::optional<int>(r);return std::optional<int>{};};auto audit=[&](){for(int id=1;id<=5;++id)check(x.room_for(id)==(res.count(id)?std::optional<int>(res[id]):std::nullopt));for(std::string c:{"suite","basic"})for(int t:{0,5,10})check(x.earliest_free(c,t,2)==earliest(c,t,2));};auto add=[&](int r,std::string c){bool e=r>0&&!c.empty()&&!rooms.count(r);check(x.add_room(r,c)==e);if(e)rooms[r]=c;audit();};auto book=[&](int id,std::string c,int s,int e){std::optional<int>expected;if(id>0&&!c.empty()&&s>=0&&s<e&&!res.count(id))for(auto[r,rc]:rooms)if(rc==c&&free(r,s,e)){expected=r;break;}check(x.book(id,c,s,e)==expected);if(expected){cal[*expected].push_back({id,s,e});res[id]=*expected;}audit();};auto cancel=[&](int id){bool e=res.count(id);check(x.cancel(id)==e);if(e){int r=res[id];cal[r].erase(std::remove_if(cal[r].begin(),cal[r].end(),[&](auto s){return s.reservation==id;}),cal[r].end());res.erase(id);}audit();};add(2,"suite");add(1,"suite");book(1,"suite",0,10);book(2,"suite",10,20);book(3,"suite",5,7);cancel(1);cancel(9);'''),
    ),
    "service-incident-queue": VerificationCase(
        "monotonic incident escalation", "service-keyed incident records",
        "severity-only escalation and terminal erase", "severity descending then opened time and identity",
        "bounded severity and no de-escalation", "permits-severity-decrease",
        "severity<it->second.severity||severity>10", "severity>10",
        _trace("ServiceIncidentQueue", r'''ServiceIncidentQueue x;struct M{std::string service;int severity,opened;};std::map<int,M>model;auto ordered=[&](std::string s){std::vector<std::tuple<int,int,int>>q;for(auto[id,v]:model)if(v.service==s)q.push_back({-v.severity,v.opened,id});std::sort(q.begin(),q.end());std::vector<int>e;for(auto v:q)e.push_back(std::get<2>(v));return e;};auto audit=[&](){for(std::string s:{"api","db"}){auto e=ordered(s);check(x.unresolved(s)==e);check(x.next(s)==(e.empty()?std::nullopt:std::optional<int>(e.front())));}};auto open=[&](int id,std::string s,int sev,int at){bool e=id>0&&!s.empty()&&sev>=0&&sev<=10&&at>=0&&!model.count(id);check(x.open(id,s,sev,at)==e);if(e)model[id]={s,sev,at};audit();};auto escalate=[&](int id,int sev){auto it=model.find(id);bool e=it!=model.end()&&sev>=it->second.severity&&sev<=10;check(x.escalate(id,sev)==e);if(e)it->second.severity=sev;audit();};auto resolve=[&](int id){bool e=model.erase(id)==1;check(x.resolve(id)==e);audit();};open(2,"api",4,1);open(1,"api",4,1);open(3,"api",8,9);escalate(2,3);escalate(2,9);resolve(3);resolve(9);'''),
    ),
    "copy-loan-ledger": VerificationCase(
        "exclusive physical-copy loan", "copy-indexed borrower and due records",
        "forward renewal and return erase", "due date then copy identity",
        "strict overdue boundary and duplicate copy", "marks-due-today-overdue",
        "if(l.due<today)", "if(l.due<=today)",
        _trace("CopyLoanLedger", r'''CopyLoanLedger x;std::map<int,std::pair<int,int>>model;auto audit=[&](){for(int id=1;id<=4;++id)check(x.borrower(id)==(model.count(id)?std::optional<int>(model[id].first):std::nullopt));for(int today:{0,4,8}){std::vector<std::pair<int,int>>q;for(auto[c,v]:model)if(v.second<today)q.push_back({v.second,c});std::sort(q.begin(),q.end());std::vector<int>e;for(auto p:q)e.push_back(p.second);check(x.overdue(today)==e);}};auto lend=[&](int c,int p,int due){bool e=c>0&&p>0&&due>=0&&!model.count(c);check(x.lend(c,p,due)==e);if(e)model[c]={p,due};audit();};auto renew=[&](int c,int due){bool e=model.count(c)&&due>model[c].second;check(x.renew(c,due)==e);if(e)model[c].second=due;audit();};auto ret=[&](int c){bool e=model.erase(c)==1;check(x.return_copy(c)==e);audit();};lend(2,7,5);lend(1,8,3);lend(1,9,9);renew(1,3);renew(1,8);ret(2);ret(2);'''),
    ),
    "crew-workload-ledger": VerificationCase(
        "weighted capacity ledger", "crew capacities, aggregate loads, and effort-bearing work",
        "effort-preserving atomic reassignment", "lexical feasible-crew enumeration",
        "zero capacity and exact-fit admission", "counts-orders-instead-of-effort",
        "load_[crew]+=effort", "load_[crew]+=1",
        _trace("CrewWorkloadLedger", r'''CrewWorkloadLedger x;std::map<std::string,int>cap;struct W{std::string crew;int effort;};std::map<int,W>work;auto load=[&](std::string c){int n=0;for(auto[id,w]:work)if(w.crew==c)n+=w.effort;return n;};auto audit=[&](){for(std::string c:{"a","b","z"})check(x.workload(c)==(cap.count(c)?std::optional<int>(load(c)):std::nullopt));for(int effort:{1,3,5}){std::vector<std::string>e;for(auto[c,n]:cap)if(load(c)<=n-effort)e.push_back(c);check(x.available_for(effort)==e);}};auto add=[&](std::string c,int n){bool e=!c.empty()&&n>=0&&!cap.count(c);check(x.add_crew(c,n)==e);if(e)cap[c]=n;audit();};auto assign=[&](int id,std::string c,int effort){bool e=id>0&&effort>0&&!work.count(id)&&cap.count(c)&&load(c)<=cap[c]-effort;check(x.assign(id,c,effort)==e);if(e)work[id]={c,effort};audit();};auto reassign=[&](int id,std::string c){bool e=work.count(id)&&cap.count(c)&&(work[id].crew==c||load(c)<=cap[c]-work[id].effort);check(x.reassign(id,c)==e);if(e)work[id].crew=c;audit();};auto complete=[&](int id){bool e=work.erase(id)==1;check(x.complete(id)==e);audit();};add("z",0);add("a",5);add("b",4);assign(1,"a",4);assign(2,"a",2);assign(2,"b",1);reassign(1,"b");complete(2);reassign(1,"b");complete(9);'''),
    ),
    "asset-custody-history": VerificationCase(
        "historical temporal ownership", "identity map of append-only event vectors",
        "strict timestamp append and whole-chain erase", "upper-bound predecessor lookup",
        "query before first event and same-stamp rejection", "overwrites-custody-history",
        "it->second.push_back({std::move(custodian),stamp})", "it->second.clear();it->second.push_back({std::move(custodian),stamp})",
        _trace("AssetCustodyHistory", r'''AssetCustodyHistory x;using E=curriculum::CustodyEvent;std::map<int,std::vector<E>>model;auto owner=[&](int id,int stamp){if(!model.count(id)||stamp<0)return std::optional<std::string>{};std::optional<std::string>out;for(auto e:model[id])if(e.stamp<=stamp)out=e.custodian;else break;return out;};auto audit=[&](){for(int id=1;id<=3;++id){check(x.history(id)==(model.count(id)?model[id]:std::vector<E>{}));for(int stamp:{0,2,5,9})check(x.owner_at(id,stamp)==owner(id,stamp));}};auto add=[&](int id,std::string c,int stamp){bool e=id>0&&!c.empty()&&stamp>=0&&!model.count(id);check(x.add_asset(id,c,stamp)==e);if(e)model[id]={{c,stamp}};audit();};auto transfer=[&](int id,std::string c,int stamp){bool e=model.count(id)&&!c.empty()&&stamp>model[id].back().stamp;check(x.transfer(id,c,stamp)==e);if(e)model[id].push_back({c,stamp});audit();};auto erase=[&](int id){bool e=model.erase(id)==1;check(x.erase_asset(id)==e);audit();};add(1,"museum",2);transfer(1,"lab",5);transfer(1,"vault",9);transfer(1,"x",9);add(1,"x",10);erase(1);erase(1);'''),
    ),
    "permit-expiry-wheel": VerificationCase(
        "bounded modular timing wheel", "cyclic buckets plus absolute-due permit map",
        "issue/revoke with tickwise bucket draining", "tick sequence then permit identity",
        "delay horizon and stale wraparound suppression", "expires-entire-bucket-on-wrap",
        "if(it->second.due==now_)", "if(true)",
        _trace("PermitExpiryWheel", r'''PermitExpiryWheel x(3);struct P{std::string zone;std::size_t due;};std::map<int,P>model;std::size_t now=0;auto audit=[&](){check(x.now()==now);for(std::string z:{"a","b"}){std::vector<int>e;for(auto[id,p]:model)if(p.zone==z)e.push_back(id);check(x.active_in(z)==e);}};auto issue=[&](int id,std::string z,std::size_t d){bool e=id>0&&!z.empty()&&d>0&&d<=3&&!model.count(id);check(x.issue(id,z,d)==e);if(e)model[id]={z,now+d};audit();};auto extend=[&](int id,std::size_t d){bool e=model.count(id)&&d>0&&d<=3;check(x.extend(id,d)==e);if(e)model[id].due=now+d;audit();};auto revoke=[&](int id){bool e=model.erase(id)==1;check(x.revoke(id)==e);audit();};auto advance=[&](std::size_t ticks){std::vector<int>e;for(std::size_t i=0;i<ticks;++i){++now;std::vector<int>due;for(auto[id,p]:model)if(p.due==now)due.push_back(id);for(int id:due)model.erase(id);std::sort(due.begin(),due.end());e.insert(e.end(),due.begin(),due.end());}check(x.advance(ticks)==e);audit();};issue(2,"a",3);issue(1,"a",1);issue(3,"b",4);advance(1);extend(2,3);advance(2);extend(9,1);advance(1);revoke(2);'''),
    ),
    "shipping-rate-resolver": VerificationCase(
        "multi-key interval quote resolution", "contract-indexed inclusive rate bands",
        "band insertion and retirement", "cost then width then contract identity",
        "inclusive singleton band and invalid range", "chooses-narrowest-before-lowest-cost",
        "return a.cost!=b.cost?a.cost<b.cost:(a.width!=b.width", "return a.width!=b.width?a.width<b.width:(a.cost!=b.cost",
        _trace("ShippingRateResolver", r'''ShippingRateResolver x;struct R{std::string region;int low,high,cost;};std::map<int,R>model;auto covering=[&](std::string region,int w){std::vector<std::tuple<int,long long,int>>q;for(auto[id,r]:model)if(r.region==region&&r.low<=w&&w<=r.high)q.push_back({r.cost,(long long)r.high-r.low,id});std::sort(q.begin(),q.end());std::vector<int>e;for(auto v:q)e.push_back(std::get<2>(v));return e;};auto audit=[&](){for(std::string r:{"eu","us"})for(int w:{0,5,10}){auto e=covering(r,w);check(x.covering(r,w)==e);check(x.resolve(r,w)==(e.empty()?std::nullopt:std::optional<curriculum::RateQuote>({e.front(),model[e.front()].cost})));}};auto add=[&](int id,std::string r,int lo,int hi,int cost){bool e=id>0&&!r.empty()&&lo>=0&&lo<=hi&&cost>=0&&!model.count(id);check(x.add(id,r,lo,hi,cost)==e);if(e)model[id]={r,lo,hi,cost};audit();};auto retire=[&](int id){bool e=model.erase(id)==1;check(x.retire(id)==e);audit();};add(3,"eu",0,10,5);add(2,"eu",3,7,5);add(1,"eu",0,9,4);add(4,"eu",8,2,1);retire(1);retire(9);'''),
    ),
    "billing-cycle-counter": VerificationCase(
        "two-dimensional membership aggregate", "account-cell map plus reconciled cell counts",
        "old-cell decrement/new-cell increment and cancellation", "lexical plan-cycle snapshot",
        "idempotent same-cell change and zero-cell removal", "leaves-zero-count-cells",
        "if(--counts_[old]==0)counts_.erase(old)", "--counts_[old]",
        _trace("BillingCycleCounter", r'''BillingCycleCounter x;using Cell=std::pair<std::string,std::string>;std::map<int,Cell>accounts;auto audit=[&](){std::map<Cell,std::size_t>counts;for(auto[id,c]:accounts)++counts[c];std::vector<curriculum::BillingCount>e;for(auto[c,n]:counts)e.push_back({c.first,c.second,n});check(x.snapshot()==e);for(int id=1;id<=4;++id)check(x.plan_of(id)==(accounts.count(id)?std::optional<std::string>(accounts[id].first):std::nullopt));};auto start=[&](int id,std::string p,std::string c){bool e=id>0&&!p.empty()&&!c.empty()&&!accounts.count(id);check(x.start(id,p,c)==e);if(e)accounts[id]={p,c};audit();};auto change=[&](int id,std::string p,std::string c){bool e=accounts.count(id)&&!p.empty()&&!c.empty();check(x.change(id,p,c)==e);if(e)accounts[id]={p,c};audit();};auto cancel=[&](int id){bool e=accounts.erase(id)==1;check(x.cancel(id)==e);audit();};start(1,"pro","month");start(2,"pro","year");start(1,"x","x");change(2,"pro","month");change(9,"x","x");cancel(1);cancel(1);'''),
    ),
    "sla-escalation-heap": VerificationCase(
        "indexed binary heap maintenance", "heap vector plus exact identity-position index",
        "bidirectional sift after update and indexed removal", "priority then deadline/opened/identity among breached",
        "deadline gate and invalid priority", "reprioritize-without-reheapifying",
        "heap_[i].priority=priority;up(i);down(index_[id])", "heap_[i].priority=priority;return true",
        _trace("SlaEscalationHeap", r'''SlaEscalationHeap x;struct C{int priority,opened,deadline;};std::map<int,C>model;auto before=[](auto a,int ai,auto b,int bi){return a.priority!=b.priority?a.priority>b.priority:(a.deadline!=b.deadline?a.deadline<b.deadline:(a.opened!=b.opened?a.opened<b.opened:ai<bi));};auto audit=[&](){check(x.size()==model.size());std::optional<int>front;for(auto[id,c]:model)if(!front||before(c,id,model[*front],*front))front=id;check(x.priority_front()==front);for(int now:{0,10,30,60}){std::optional<int>e;for(auto[id,c]:model)if(c.deadline<=now&&(!e||before(c,id,model[*e],*e)))e=id;check(x.breach_candidate(now)==e);}};auto open=[&](int id,int p,int at,int due){bool e=id>0&&p>=0&&p<=100&&at>=0&&due>=at&&!model.count(id);check(x.open(id,p,at,due)==e);if(e)model[id]={p,at,due};audit();};auto reprio=[&](int id,int p){bool e=model.count(id)&&p>=0&&p<=100;check(x.reprioritize(id,p)==e);if(e)model[id].priority=p;audit();};auto close=[&](int id){bool e=model.erase(id)==1;check(x.close(id)==e);audit();};open(1,5,0,10);open(2,8,1,20);open(3,9,0,8);reprio(1,10);reprio(9,1);close(3);close(9);'''),
    ),
    "vaccine-lot-fefo": VerificationCase(
        "transactional FEFO allocation", "lot records with mutable dose balances",
        "plan-first multi-lot decrement", "expiry then lot identity",
        "expiry-at-today admission and all-or-nothing shortfall", "partially-allocates-on-shortfall",
        "if(total<doses)return std::nullopt", "if(false&&total<doses)return std::nullopt",
        _trace("VaccineLotFefo", r'''VaccineLotFefo x;struct L{std::string product;int expiry,remaining;};std::map<int,L>model;auto audit=[&](){for(int id=1;id<=4;++id)check(x.remaining(id)==(model.count(id)?std::optional<int>(model[id].remaining):std::nullopt));for(std::string p:{"p","q"})for(int by:{4,8}){std::vector<std::pair<int,int>>q;for(auto[id,l]:model)if(l.product==p&&l.remaining>0&&l.expiry<=by)q.push_back({l.expiry,id});std::sort(q.begin(),q.end());std::vector<int>e;for(auto v:q)e.push_back(v.second);check(x.expiring(p,by)==e);}};auto receive=[&](int id,std::string p,int expiry,int doses){bool e=id>0&&!p.empty()&&expiry>=0&&doses>0&&!model.count(id);check(x.receive(id,p,expiry,doses)==e);if(e)model[id]={p,expiry,doses};audit();};auto allocate=[&](std::string p,int today,int doses){std::vector<std::pair<int,int>>q;int total=0;if(!p.empty()&&today>=0&&doses>0)for(auto[id,l]:model)if(l.product==p&&l.expiry>=today&&l.remaining>0){q.push_back({l.expiry,id});total+=l.remaining;}std::sort(q.begin(),q.end());std::optional<std::vector<curriculum::LotUse>>e;if(!p.empty()&&today>=0&&doses>0&&total>=doses){e=std::vector<curriculum::LotUse>{};int left=doses;for(auto v:q){int take=std::min(left,model[v.second].remaining);if(take){e->push_back({v.second,take});left-=take;}if(!left)break;}for(auto use:*e)model[use.lot].remaining-=use.doses;}check(x.allocate(p,today,doses)==e);audit();};receive(2,"p",8,4);receive(1,"p",5,3);receive(1,"q",9,1);allocate("p",5,8);allocate("p",5,5);allocate("p",9,1);'''),
    ),
    "warehouse-batch-splitter": VerificationCase(
        "conservative batch partition and merge", "zone capacity/load maps plus unit-bearing batches",
        "unit split, compatible merge, and atomic load transfer", "expiry then batch identity",
        "strict proper split and destination exact fit", "duplicates-units-during-split",
        "batches_[fresh]={it->second.zone,units,it->second.expiry}", "batches_[fresh]={it->second.zone,it->second.units,it->second.expiry}",
        _trace("WarehouseBatchSplitter", r'''WarehouseBatchSplitter x;struct B{std::string zone;int units,expiry;};std::map<std::string,int>cap;std::map<int,B>batches;auto load=[&](std::string z){int n=0;for(auto[id,b]:batches)if(b.zone==z)n+=b.units;return n;};auto audit=[&](){for(std::string z:{"a","b"})for(int by:{2,5}){std::vector<std::pair<int,int>>q;for(auto[id,b]:batches)if(b.zone==z&&b.expiry<=by)q.push_back({b.expiry,id});std::sort(q.begin(),q.end());std::vector<int>e;for(auto p:q)e.push_back(p.second);check(x.expiring(z,by)==e);}};auto zone=[&](std::string z,int n){bool e=!z.empty()&&n>=0&&!cap.count(z);check(x.add_zone(z,n)==e);if(e)cap[z]=n;audit();};auto receive=[&](int id,std::string z,int n,int expiry){bool e=id>0&&n>0&&expiry>=0&&!batches.count(id)&&cap.count(z)&&load(z)<=cap[z]-n;check(x.receive(id,z,n,expiry)==e);if(e)batches[id]={z,n,expiry};audit();};auto split=[&](int id,int fresh,int n){bool e=batches.count(id)&&fresh>0&&!batches.count(fresh)&&n>0&&n<batches[id].units;check(x.split(id,fresh,n)==e);if(e){batches[id].units-=n;batches[fresh]={batches[id].zone,n,batches[id].expiry};}audit();};auto merge=[&](int a,int b){bool e=batches.count(a)&&batches.count(b)&&a!=b&&batches[a].zone==batches[b].zone&&batches[a].expiry==batches[b].expiry;check(x.merge(a,b)==e);if(e){batches[a].units+=batches[b].units;batches.erase(b);}audit();};auto move=[&](int id,std::string z){bool e=batches.count(id)&&cap.count(z)&&(batches[id].zone==z||load(z)<=cap[z]-batches[id].units);check(x.move(id,z)==e);if(e)batches[id].zone=z;audit();};zone("a",10);zone("b",4);receive(1,"a",8,4);split(1,2,3);move(1,"b");move(2,"b");merge(1,2);move(2,"a");'''),
    ),
}
