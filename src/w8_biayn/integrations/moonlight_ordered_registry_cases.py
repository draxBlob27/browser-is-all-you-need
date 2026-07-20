"""Task-specific C++ contracts for the ordered-registry v2 family.

The cases intentionally keep their complete APIs and reference algorithms
separate.  Sharing a renderer here must never collapse them back into the
legacy register/transition/query template.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    legacy_id: str
    task_id: str
    title: str
    class_name: str
    objective: str
    header: str
    starter: str
    reference: str
    visible: str
    hidden: str
    core_markers: tuple[str, ...]
    forbidden_markers: tuple[str, ...] = ("struct Entry { int id; std::string group; int rank; int stamp;",)


COMMON_INCLUDES = """#pragma once
#include <cstddef>
#include <map>
#include <optional>
#include <set>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>
"""


def _header(body: str) -> str:
    return COMMON_INCLUDES + "namespace curriculum {\n" + body + "\n}  // namespace curriculum\n"


def _source(body: str) -> str:
    return '#include "task.h"\n#include <algorithm>\n#include <limits>\nnamespace curriculum {\n' + body + "\n}  // namespace curriculum\n"


def _test(class_name: str, body: str) -> str:
    return f'''#include "task.h"
#include <optional>
#include <string>
#include <vector>
int main() {{
  int failures = 0;
  const auto check = [&](bool value) {{ if (!value) ++failures; }};
  using curriculum::{class_name};
  {body}
  return failures == 0 ? 0 : 1;
}}
'''


CASES = (
    Case(
        "registry-audit-retention", "registry-audit-retention", "Audit retention ledger", "AuditRetentionLedger",
        "Track retention expiry independently from legal holds and erase only eligible records.",
        _header("""class AuditRetentionLedger { public:
  bool add(int id, int expires); bool set_hold(int id, bool held);
  bool erase_if_eligible(int id, int today); std::vector<int> eligible(int today) const;
  std::optional<int> expiry(int id) const;
 private: struct Record { int expires; bool held; }; std::map<int, Record> records_; std::set<std::pair<int,int>> eligible_index_; };"""),
        _source("""bool AuditRetentionLedger::add(int,int){return false;} bool AuditRetentionLedger::set_hold(int,bool){return false;}
bool AuditRetentionLedger::erase_if_eligible(int,int){return false;} std::vector<int> AuditRetentionLedger::eligible(int)const{return {};}
std::optional<int> AuditRetentionLedger::expiry(int)const{return std::nullopt;}"""),
        _source("""bool AuditRetentionLedger::add(int id,int expires){if(id<=0||expires<0||records_.count(id))return false;records_[id]={expires,false};eligible_index_.insert({expires,id});return true;}
bool AuditRetentionLedger::set_hold(int id,bool held){auto it=records_.find(id);if(it==records_.end())return false;if(it->second.held==held)return true;if(held)eligible_index_.erase({it->second.expires,id});else eligible_index_.insert({it->second.expires,id});it->second.held=held;return true;}
bool AuditRetentionLedger::erase_if_eligible(int id,int today){auto it=records_.find(id);if(it==records_.end()||it->second.held||it->second.expires>today)return false;eligible_index_.erase({it->second.expires,id});records_.erase(it);return true;}
std::vector<int> AuditRetentionLedger::eligible(int today)const{std::vector<int> out;for(auto [expires,id]:eligible_index_){if(expires>today)break;out.push_back(id);}return out;}
std::optional<int> AuditRetentionLedger::expiry(int id)const{auto it=records_.find(id);return it==records_.end()?std::nullopt:std::optional<int>(it->second.expires);}"""),
        _test("AuditRetentionLedger", "AuditRetentionLedger x; check(x.add(2,8)); check(x.add(1,8)); check(!x.add(1,9)); check(x.eligible(8)==std::vector<int>({1,2})); check(x.set_hold(1,true)); check(x.eligible(8)==std::vector<int>({2}));"),
        _test("AuditRetentionLedger", "AuditRetentionLedger x; check(x.add(3,0)); check(!x.erase_if_eligible(4,0)); check(x.set_hold(3,true)); check(!x.erase_if_eligible(3,99)); check(x.set_hold(3,false)); check(x.erase_if_eligible(3,0)); check(!x.expiry(3)); check(!x.add(0,1));"),
        ("eligible_index_", "eligible_index_.erase", "if(expires>today)break", "erase_if_eligible"),
    ),
    Case(
        "registry-cargo-customs", "customs-clearance-workflow", "Customs clearance workflow", "CustomsClearanceWorkflow",
        "Enforce filed-to-inspected-to-cleared declaration transitions and deadline ordering.",
        _header("""enum class ClearanceStage { filed, inspected, cleared };
class CustomsClearanceWorkflow { public: bool file(int id,std::string lane,int deadline); bool inspect(int id); bool clear(int id);
 std::vector<int> pending(const std::string& lane) const; std::optional<ClearanceStage> stage(int id) const;
 private: struct Declaration { std::string lane; int deadline; ClearanceStage stage; }; std::map<int,Declaration> declarations_; };"""),
        _source("""bool CustomsClearanceWorkflow::file(int,std::string,int){return false;} bool CustomsClearanceWorkflow::inspect(int){return false;} bool CustomsClearanceWorkflow::clear(int){return false;} std::vector<int> CustomsClearanceWorkflow::pending(const std::string&)const{return {};} std::optional<ClearanceStage> CustomsClearanceWorkflow::stage(int)const{return std::nullopt;}"""),
        _source("""bool CustomsClearanceWorkflow::file(int id,std::string lane,int deadline){return id>0&&!lane.empty()&&deadline>=0&&declarations_.emplace(id,Declaration{std::move(lane),deadline,ClearanceStage::filed}).second;}
bool CustomsClearanceWorkflow::inspect(int id){auto it=declarations_.find(id);if(it==declarations_.end()||it->second.stage!=ClearanceStage::filed)return false;it->second.stage=ClearanceStage::inspected;return true;}
bool CustomsClearanceWorkflow::clear(int id){auto it=declarations_.find(id);if(it==declarations_.end()||it->second.stage!=ClearanceStage::inspected)return false;it->second.stage=ClearanceStage::cleared;return true;}
std::vector<int> CustomsClearanceWorkflow::pending(const std::string& lane)const{std::vector<std::pair<int,int>> v;for(const auto& [id,d]:declarations_)if(d.lane==lane&&d.stage!=ClearanceStage::cleared)v.push_back({d.deadline,id});std::sort(v.begin(),v.end());std::vector<int> out;for(auto p:v)out.push_back(p.second);return out;}
std::optional<ClearanceStage> CustomsClearanceWorkflow::stage(int id)const{auto it=declarations_.find(id);return it==declarations_.end()?std::nullopt:std::optional<ClearanceStage>(it->second.stage);}"""),
        _test("CustomsClearanceWorkflow", "CustomsClearanceWorkflow x; check(x.file(2,\"red\",9)); check(x.file(1,\"red\",5)); check(x.pending(\"red\")==std::vector<int>({1,2})); check(!x.clear(1)); check(x.inspect(1)); check(x.clear(1)); check(x.pending(\"red\")==std::vector<int>({2}));"),
        _test("CustomsClearanceWorkflow", "CustomsClearanceWorkflow x; check(!x.file(0,\"red\",1)); check(x.file(1,\"green\",0)); check(!x.inspect(9)); check(x.inspect(1)); check(!x.inspect(1)); check(x.clear(1)); check(!x.clear(1)); check(x.stage(1)==curriculum::ClearanceStage::cleared);"),
        ("enum class ClearanceStage", "ClearanceStage::filed", "ClearanceStage::inspected", "ClearanceStage::cleared"),
    ),
    Case(
        "registry-clinic-triage", "triage-priority-board", "Triage priority board", "TriagePriorityBoard",
        "Reprioritize waiting patients while preserving arrival order and remove the next patient.",
        _header("""class TriagePriorityBoard { public: bool arrive(int id,int severity,int arrival); bool reprioritize(int id,int severity);
 std::optional<int> treat_next(); std::vector<int> waiting_order() const;
 private: struct Patient { int id; int severity; int arrival; }; std::vector<Patient> waiting_; };"""),
        _source("""bool TriagePriorityBoard::arrive(int,int,int){return false;} bool TriagePriorityBoard::reprioritize(int,int){return false;} std::optional<int> TriagePriorityBoard::treat_next(){return std::nullopt;} std::vector<int> TriagePriorityBoard::waiting_order()const{return {};}"""),
        _source("""bool triage_before_values(int as,int aa,int ai,int bs,int ba,int bi){return as!=bs?as>bs:(aa!=ba?aa<ba:ai<bi);}
bool TriagePriorityBoard::arrive(int id,int severity,int arrival){if(id<=0||severity<1||severity>5||arrival<0)return false;for(const auto&p:waiting_)if(p.id==id)return false;waiting_.push_back({id,severity,arrival});return true;}
bool TriagePriorityBoard::reprioritize(int id,int severity){if(severity<1||severity>5)return false;for(auto&p:waiting_)if(p.id==id){p.severity=severity;return true;}return false;}
std::vector<int> TriagePriorityBoard::waiting_order()const{auto copy=waiting_;std::sort(copy.begin(),copy.end(),[](const Patient&a,const Patient&b){return triage_before_values(a.severity,a.arrival,a.id,b.severity,b.arrival,b.id);});std::vector<int> out;for(auto p:copy)out.push_back(p.id);return out;}
std::optional<int> TriagePriorityBoard::treat_next(){if(waiting_.empty())return std::nullopt;auto it=std::min_element(waiting_.begin(),waiting_.end(),[](const Patient&a,const Patient&b){return triage_before_values(a.severity,a.arrival,a.id,b.severity,b.arrival,b.id);});int id=it->id;waiting_.erase(it);return id;}"""),
        _test("TriagePriorityBoard", "TriagePriorityBoard x; check(x.arrive(2,3,1)); check(x.arrive(1,3,1)); check(x.arrive(3,5,9)); check(x.waiting_order()==std::vector<int>({3,1,2})); check(x.treat_next()==3); check(x.reprioritize(2,5)); check(x.treat_next()==2);"),
        _test("TriagePriorityBoard", "TriagePriorityBoard x; check(!x.arrive(1,0,0)); check(x.arrive(1,1,7)); check(!x.arrive(1,5,1)); check(!x.reprioritize(9,3)); check(x.reprioritize(1,5)); check(x.waiting_order()==std::vector<int>({1})); check(x.treat_next()==1); check(!x.treat_next());"),
        ("struct Patient", "treat_next", "waiting_.erase"),
    ),
    Case(
        "registry-conference-seats", "session-seat-waitlist", "Session seat waitlist", "SessionSeatWaitlist",
        "Promote a deterministic waitlist when bounded session seats are cancelled.",
        _header("""class SessionSeatWaitlist { public: bool configure(std::string session,std::size_t seats); bool request(std::string session,int attendee,int stamp); bool cancel(std::string session,int attendee); bool transfer(std::string from,std::string to,int attendee,int stamp); std::vector<int> seated(std::string session) const; std::vector<int> waiting(std::string session) const;
 private: struct Request { int attendee; int stamp; }; struct Session { std::size_t capacity; std::vector<int> seated; std::vector<Request> waiting; }; std::map<std::string,Session> sessions_; std::map<int,std::string> owner_; bool insert_request(Session&,int,int); };"""),
        _source("""bool SessionSeatWaitlist::configure(std::string,std::size_t){return false;} bool SessionSeatWaitlist::request(std::string,int,int){return false;} bool SessionSeatWaitlist::cancel(std::string,int){return false;} bool SessionSeatWaitlist::transfer(std::string,std::string,int,int){return false;} std::vector<int> SessionSeatWaitlist::seated(std::string)const{return {};} std::vector<int> SessionSeatWaitlist::waiting(std::string)const{return {};} bool SessionSeatWaitlist::insert_request(Session&,int,int){return false;}"""),
        _source("""bool SessionSeatWaitlist::configure(std::string name,std::size_t seats){return !name.empty()&&sessions_.emplace(std::move(name),Session{seats,{},{}}).second;}
bool SessionSeatWaitlist::insert_request(Session&s,int attendee,int stamp){if(s.seated.size()<s.capacity)s.seated.push_back(attendee);else{s.waiting.push_back({attendee,stamp});std::sort(s.waiting.begin(),s.waiting.end(),[](auto a,auto b){return a.stamp!=b.stamp?a.stamp<b.stamp:a.attendee<b.attendee;});}return true;}
bool SessionSeatWaitlist::request(std::string name,int attendee,int stamp){auto it=sessions_.find(name);if(it==sessions_.end()||attendee<=0||stamp<0||owner_.count(attendee))return false;insert_request(it->second,attendee,stamp);owner_[attendee]=name;return true;}
bool SessionSeatWaitlist::cancel(std::string name,int attendee){auto it=sessions_.find(name);auto owned=owner_.find(attendee);if(it==sessions_.end()||owned==owner_.end()||owned->second!=name)return false;auto& s=it->second;auto seat=std::find(s.seated.begin(),s.seated.end(),attendee);if(seat!=s.seated.end()){s.seated.erase(seat);if(!s.waiting.empty()){s.seated.push_back(s.waiting.front().attendee);s.waiting.erase(s.waiting.begin());}}else{s.waiting.erase(std::remove_if(s.waiting.begin(),s.waiting.end(),[&](auto r){return r.attendee==attendee;}),s.waiting.end());}owner_.erase(attendee);return true;}
bool SessionSeatWaitlist::transfer(std::string from,std::string to,int attendee,int stamp){auto target=sessions_.find(to);auto source=sessions_.find(from);auto owned=owner_.find(attendee);if(target==sessions_.end()||source==sessions_.end()||owned==owner_.end()||owned->second!=from||stamp<0)return false;cancel(from,attendee);insert_request(target->second,attendee,stamp);owner_[attendee]=to;return true;}
std::vector<int> SessionSeatWaitlist::seated(std::string name)const{auto it=sessions_.find(name);return it==sessions_.end()?std::vector<int>{}:it->second.seated;}
std::vector<int> SessionSeatWaitlist::waiting(std::string name)const{std::vector<int> out;auto it=sessions_.find(name);if(it!=sessions_.end())for(auto r:it->second.waiting)out.push_back(r.attendee);return out;}"""),
        _test("SessionSeatWaitlist", "SessionSeatWaitlist x; check(x.configure(\"cpp\",1)); check(x.request(\"cpp\",1,5)); check(x.request(\"cpp\",2,4)); check(x.request(\"cpp\",3,3)); check(x.waiting(\"cpp\")==std::vector<int>({3,2})); check(x.cancel(\"cpp\",1)); check(x.seated(\"cpp\")==std::vector<int>({3}));"),
        _test("SessionSeatWaitlist", "SessionSeatWaitlist x; check(x.configure(\"a\",0)); check(x.configure(\"b\",1)); check(!x.cancel(\"a\",9)); check(x.request(\"a\",9,0)); check(x.cancel(\"a\",9)); check(x.request(\"a\",4,1)); check(x.waiting(\"a\")==std::vector<int>({4})); check(x.transfer(\"a\",\"b\",4,2)); check(x.seated(\"b\")==std::vector<int>({4})); check(!x.request(\"a\",4,9));"),
        ("struct Session", "waiting.erase", "insert_request"),
    ),
    Case(
        "registry-device-fleet", "device-heartbeat-index", "Device heartbeat index", "DeviceHeartbeatIndex",
        "Preserve monotonic heartbeats across deployment-ring moves and list globally stale devices.",
        _header("""class DeviceHeartbeatIndex { public: bool enroll(int id,std::string ring,int seen); bool heartbeat(int id,int seen); bool move(int id,std::string ring); std::vector<int> stale_before(int cutoff) const; std::vector<int> in_ring(std::string ring) const;
 private: struct Device { std::string ring; int seen; }; std::map<int,Device> devices_; };"""),
        _source("""bool DeviceHeartbeatIndex::enroll(int,std::string,int){return false;} bool DeviceHeartbeatIndex::heartbeat(int,int){return false;} bool DeviceHeartbeatIndex::move(int,std::string){return false;} std::vector<int> DeviceHeartbeatIndex::stale_before(int)const{return {};} std::vector<int> DeviceHeartbeatIndex::in_ring(std::string)const{return {};}"""),
        _source("""bool DeviceHeartbeatIndex::enroll(int id,std::string ring,int seen){return id>0&&!ring.empty()&&seen>=0&&devices_.emplace(id,Device{std::move(ring),seen}).second;}
bool DeviceHeartbeatIndex::heartbeat(int id,int seen){auto it=devices_.find(id);if(it==devices_.end()||seen<it->second.seen)return false;it->second.seen=seen;return true;}
bool DeviceHeartbeatIndex::move(int id,std::string ring){auto it=devices_.find(id);if(it==devices_.end()||ring.empty())return false;it->second.ring=std::move(ring);return true;}
std::vector<int> DeviceHeartbeatIndex::stale_before(int cutoff)const{std::vector<std::pair<int,int>> v;for(auto [id,d]:devices_)if(d.seen<cutoff)v.push_back({d.seen,id});std::sort(v.begin(),v.end());std::vector<int> out;for(auto p:v)out.push_back(p.second);return out;}
std::vector<int> DeviceHeartbeatIndex::in_ring(std::string ring)const{std::vector<int> out;for(auto [id,d]:devices_)if(d.ring==ring)out.push_back(id);return out;}"""),
        _test("DeviceHeartbeatIndex", "DeviceHeartbeatIndex x; check(x.enroll(2,\"canary\",8)); check(x.enroll(1,\"stable\",4)); check(x.stale_before(8)==std::vector<int>({1})); check(x.move(1,\"canary\")); check(x.in_ring(\"canary\")==std::vector<int>({1,2})); check(x.heartbeat(1,9)); check(x.stale_before(9)==std::vector<int>({2}));"),
        _test("DeviceHeartbeatIndex", "DeviceHeartbeatIndex x; check(x.enroll(1,\"a\",5)); check(!x.heartbeat(1,4)); check(x.move(1,\"b\")); check(x.stale_before(6)==std::vector<int>({1})); check(!x.enroll(1,\"c\",9)); check(!x.move(9,\"x\"));"),
        ("struct Device", "seen<it->second.seen", "stale_before"),
    ),
    Case(
        "registry-feature-enrollment", "rollout-token-ring", "Rollout token ring", "RolloutTokenRing",
        "Route account hashes clockwise through a mutable ordered rollout-token ring with wraparound.",
        _header("""class RolloutTokenRing { public: bool add_token(int token,std::string cohort); bool move_token(int token,int replacement); bool remove_token(int token); std::optional<std::string> route(int account) const; std::vector<int> tokens_for(std::string cohort) const;
 private: std::map<int,std::string> ring_; };"""),
        _source("""bool RolloutTokenRing::add_token(int,std::string){return false;} bool RolloutTokenRing::move_token(int,int){return false;} bool RolloutTokenRing::remove_token(int){return false;} std::optional<std::string> RolloutTokenRing::route(int)const{return std::nullopt;} std::vector<int> RolloutTokenRing::tokens_for(std::string)const{return {};}"""),
        _source("""bool RolloutTokenRing::add_token(int token,std::string cohort){return token>=0&&token<360&&!cohort.empty()&&ring_.emplace(token,std::move(cohort)).second;}
bool RolloutTokenRing::move_token(int token,int replacement){auto it=ring_.find(token);if(it==ring_.end()||replacement<0||replacement>=360||ring_.count(replacement))return false;auto cohort=it->second;ring_.erase(it);ring_.emplace(replacement,std::move(cohort));return true;}
bool RolloutTokenRing::remove_token(int token){return ring_.erase(token)==1U;}
std::optional<std::string> RolloutTokenRing::route(int account)const{if(account<0||ring_.empty())return std::nullopt;int hash=account%360;auto it=ring_.lower_bound(hash);if(it==ring_.end())it=ring_.begin();return it->second;}
std::vector<int> RolloutTokenRing::tokens_for(std::string cohort)const{std::vector<int> out;for(auto [token,name]:ring_)if(name==cohort)out.push_back(token);return out;}"""),
        _test("RolloutTokenRing", "RolloutTokenRing x; check(x.add_token(300,\"stable\")); check(x.add_token(60,\"canary\")); check(x.route(10)==\"canary\"); check(x.route(100)==\"stable\"); check(x.route(350)==\"canary\"); check(x.move_token(60,90)); check(x.tokens_for(\"canary\")==std::vector<int>({90}));"),
        _test("RolloutTokenRing", "RolloutTokenRing x; check(!x.route(1)); check(!x.add_token(-1,\"x\")); check(x.add_token(0,\"a\")); check(!x.add_token(0,\"b\")); check(!x.move_token(9,1)); check(x.move_token(0,359)); check(x.route(359)==\"a\"); check(x.remove_token(359)); check(!x.route(0));"),
        ("lower_bound(hash)", "if(it==ring_.end())it=ring_.begin()", "ring_.emplace(replacement"),
    ),
    Case(
        "registry-flight-gates", "gate-conflict-scheduler", "Gate conflict scheduler", "GateConflictScheduler",
        "Schedule compatible flights on half-open gate calendars and move them atomically.",
        _header("""class GateConflictScheduler { public: bool add_gate(std::string gate,std::vector<std::string> types); bool schedule(int flight,std::string type,int start,int end,std::string gate); bool move(int flight,std::string gate); bool depart(int flight); std::optional<int> next_departure(std::string gate,int after) const;
 private: struct Flight { std::string type; int start; int end; std::string gate; }; std::map<std::string,std::set<std::string>> gates_; std::map<int,Flight> flights_; bool fits(int ignore,const Flight&) const; };"""),
        _source("""bool GateConflictScheduler::add_gate(std::string,std::vector<std::string>){return false;} bool GateConflictScheduler::schedule(int,std::string,int,int,std::string){return false;} bool GateConflictScheduler::move(int,std::string){return false;} bool GateConflictScheduler::depart(int){return false;} std::optional<int> GateConflictScheduler::next_departure(std::string,int)const{return std::nullopt;} bool GateConflictScheduler::fits(int,const Flight&)const{return false;}"""),
        _source("""bool GateConflictScheduler::add_gate(std::string gate,std::vector<std::string> types){if(gate.empty()||types.empty()||gates_.count(gate))return false;std::set<std::string> accepted;for(auto&t:types){if(t.empty())return false;accepted.insert(t);}gates_[gate]=std::move(accepted);return true;}
bool GateConflictScheduler::fits(int ignore,const Flight& f)const{auto g=gates_.find(f.gate);if(g==gates_.end()||!g->second.count(f.type))return false;for(auto [id,o]:flights_)if(id!=ignore&&o.gate==f.gate&&f.start<o.end&&o.start<f.end)return false;return true;}
bool GateConflictScheduler::schedule(int id,std::string type,int start,int end,std::string gate){Flight f{std::move(type),start,end,std::move(gate)};if(id<=0||start<0||start>=end||flights_.count(id)||!fits(id,f))return false;flights_[id]=std::move(f);return true;}
bool GateConflictScheduler::move(int id,std::string gate){auto it=flights_.find(id);if(it==flights_.end())return false;Flight candidate=it->second;candidate.gate=std::move(gate);if(!fits(id,candidate))return false;it->second=std::move(candidate);return true;}
bool GateConflictScheduler::depart(int id){return flights_.erase(id)==1U;}
std::optional<int> GateConflictScheduler::next_departure(std::string gate,int after)const{std::optional<std::pair<int,int>> best;for(auto [id,f]:flights_)if(f.gate==gate&&f.start>=after&&(!best||std::pair<int,int>{f.start,id}<*best))best={f.start,id};return best?std::optional<int>(best->second):std::nullopt;}"""),
        _test("GateConflictScheduler", "GateConflictScheduler x; check(x.add_gate(\"g1\",{\"jet\"})); check(x.add_gate(\"g2\",{\"jet\"})); check(x.schedule(2,\"jet\",10,20,\"g1\")); check(x.schedule(1,\"jet\",20,30,\"g1\")); check(!x.schedule(3,\"jet\",19,21,\"g1\")); check(x.next_departure(\"g1\",0)==2); check(x.move(1,\"g2\"));"),
        _test("GateConflictScheduler", "GateConflictScheduler x; check(x.add_gate(\"g\",{\"jet\"})); check(!x.schedule(1,\"prop\",0,1,\"g\")); check(x.schedule(1,\"jet\",0,2,\"g\")); check(!x.move(1,\"missing\")); check(x.next_departure(\"g\",0)==1); check(x.depart(1)); check(!x.next_departure(\"g\",0));"),
        ("struct Flight", "f.start<o.end&&o.start<f.end", "fits(id,candidate)"),
    ),
    Case(
        "registry-food-allergens", "dish-allergen-catalog", "Dish allergen catalog", "DishAllergenCatalog",
        "Canonicalize allergen sets and return dishes disjoint from a forbidden set.",
        _header("""class DishAllergenCatalog { public: bool add(std::string dish,std::vector<std::string> allergens); bool replace_recipe(std::string dish,std::vector<std::string> allergens); bool erase(std::string dish); std::vector<std::string> safe_for(std::vector<std::string> forbidden) const; std::optional<std::vector<std::string>> allergens_of(std::string dish) const;
 private: std::map<std::string,std::set<std::string>> dishes_; static std::optional<std::set<std::string>> canonical(std::vector<std::string>); };"""),
        _source("""bool DishAllergenCatalog::add(std::string,std::vector<std::string>){return false;} bool DishAllergenCatalog::replace_recipe(std::string,std::vector<std::string>){return false;} bool DishAllergenCatalog::erase(std::string){return false;} std::vector<std::string> DishAllergenCatalog::safe_for(std::vector<std::string>)const{return {};} std::optional<std::vector<std::string>> DishAllergenCatalog::allergens_of(std::string)const{return std::nullopt;} std::optional<std::set<std::string>> DishAllergenCatalog::canonical(std::vector<std::string>){return std::nullopt;}"""),
        _source("""std::optional<std::set<std::string>> DishAllergenCatalog::canonical(std::vector<std::string> values){std::set<std::string> out;for(auto&v:values){if(v.empty())return std::nullopt;out.insert(std::move(v));}return out;}
bool DishAllergenCatalog::add(std::string dish,std::vector<std::string> allergens){auto c=canonical(std::move(allergens));return !dish.empty()&&c&&dishes_.emplace(std::move(dish),std::move(*c)).second;}
bool DishAllergenCatalog::replace_recipe(std::string dish,std::vector<std::string> allergens){auto it=dishes_.find(dish);auto c=canonical(std::move(allergens));if(it==dishes_.end()||!c)return false;it->second=std::move(*c);return true;}
bool DishAllergenCatalog::erase(std::string dish){return dishes_.erase(dish)==1U;}
std::vector<std::string> DishAllergenCatalog::safe_for(std::vector<std::string> forbidden)const{auto f=canonical(std::move(forbidden));if(!f)return {};std::vector<std::string> out;for(const auto&[dish,a]:dishes_){bool safe=true;for(const auto&x:*f)if(a.count(x)){safe=false;break;}if(safe)out.push_back(dish);}return out;}
std::optional<std::vector<std::string>> DishAllergenCatalog::allergens_of(std::string dish)const{auto it=dishes_.find(dish);if(it==dishes_.end())return std::nullopt;return std::vector<std::string>(it->second.begin(),it->second.end());}"""),
        _test("DishAllergenCatalog", "DishAllergenCatalog x; check(x.add(\"soup\",{\"milk\",\"milk\"})); check(x.add(\"rice\",{})); check(x.allergens_of(\"soup\")==std::vector<std::string>({\"milk\"})); check(x.safe_for({\"milk\"})==std::vector<std::string>({\"rice\"})); check(x.replace_recipe(\"soup\",{\"soy\"})); check(x.safe_for({\"milk\"})==std::vector<std::string>({\"rice\",\"soup\"}));"),
        _test("DishAllergenCatalog", "DishAllergenCatalog x; check(!x.add(\"\",{})); check(!x.add(\"x\",{\"\"})); check(x.add(\"x\",{\"nut\"})); check(!x.add(\"x\",{})); check(x.safe_for({})==std::vector<std::string>({\"x\"})); check(x.erase(\"x\")); check(!x.erase(\"x\"));"),
        ("std::set<std::string>", "canonical", "a.count(x)"),
    ),
    Case(
        "registry-grant-reviews", "proposal-review-matcher", "Proposal review matcher", "ProposalReviewMatcher",
        "Separate reviewer conflicts from assignment edges and rank proposals by review deficit.",
        _header("""class ProposalReviewMatcher { public: bool add_proposal(int id); bool add_conflict(int proposal,int reviewer); bool assign(int proposal,int reviewer); bool withdraw(int proposal,int reviewer); std::vector<int> under_reviewed(std::size_t required) const; std::size_t review_count(int proposal) const;
 private: std::set<int> proposals_; std::set<std::pair<int,int>> conflicts_; std::set<std::pair<int,int>> assignments_; };"""),
        _source("""bool ProposalReviewMatcher::add_proposal(int){return false;} bool ProposalReviewMatcher::add_conflict(int,int){return false;} bool ProposalReviewMatcher::assign(int,int){return false;} bool ProposalReviewMatcher::withdraw(int,int){return false;} std::vector<int> ProposalReviewMatcher::under_reviewed(std::size_t)const{return {};} std::size_t ProposalReviewMatcher::review_count(int)const{return 0;}"""),
        _source("""bool ProposalReviewMatcher::add_proposal(int id){return id>0&&proposals_.insert(id).second;}
bool ProposalReviewMatcher::add_conflict(int p,int r){return proposals_.count(p)&&r>0&&conflicts_.insert({p,r}).second;}
bool ProposalReviewMatcher::assign(int p,int r){return proposals_.count(p)&&r>0&&!conflicts_.count({p,r})&&assignments_.insert({p,r}).second;}
bool ProposalReviewMatcher::withdraw(int p,int r){return assignments_.erase({p,r})==1U;}
std::size_t ProposalReviewMatcher::review_count(int p)const{std::size_t n=0;for(auto edge:assignments_)if(edge.first==p)++n;return n;}
std::vector<int> ProposalReviewMatcher::under_reviewed(std::size_t required)const{std::vector<std::pair<std::size_t,int>> v;for(int p:proposals_){auto n=review_count(p);if(n<required)v.push_back({n,p});}std::sort(v.begin(),v.end());std::vector<int> out;for(auto x:v)out.push_back(x.second);return out;}"""),
        _test("ProposalReviewMatcher", "ProposalReviewMatcher x; check(x.add_proposal(2)); check(x.add_proposal(1)); check(x.add_conflict(1,9)); check(!x.assign(1,9)); check(x.assign(1,8)); check(x.assign(2,8)); check(x.assign(2,7)); check(x.under_reviewed(2)==std::vector<int>({1}));"),
        _test("ProposalReviewMatcher", "ProposalReviewMatcher x; check(!x.add_proposal(0)); check(x.add_proposal(1)); check(!x.assign(9,1)); check(x.assign(1,2)); check(!x.assign(1,2)); check(x.withdraw(1,2)); check(!x.withdraw(1,2)); check(x.under_reviewed(0).empty());"),
        ("conflicts_", "assignments_", "std::set<std::pair<int,int>>"),
    ),
    Case(
        "registry-hotel-rooms", "room-stay-calendar", "Room stay calendar", "RoomStayCalendar",
        "Choose the smallest class-compatible room whose half-open calendar does not overlap.",
        _header("""class RoomStayCalendar { public: bool add_room(int room,std::string room_class); std::optional<int> book(int reservation,std::string room_class,int start,int end); bool cancel(int reservation); std::optional<int> room_for(int reservation) const; std::optional<int> earliest_free(std::string room_class,int from,int duration) const;
 private: struct Stay { int reservation; int start; int end; }; std::map<int,std::string> rooms_; std::map<int,std::vector<Stay>> calendars_; std::map<int,int> reservations_; bool free_at(int room,int start,int end) const; };"""),
        _source("""bool RoomStayCalendar::add_room(int,std::string){return false;} std::optional<int> RoomStayCalendar::book(int,std::string,int,int){return std::nullopt;} bool RoomStayCalendar::cancel(int){return false;} std::optional<int> RoomStayCalendar::room_for(int)const{return std::nullopt;} std::optional<int> RoomStayCalendar::earliest_free(std::string,int,int)const{return std::nullopt;} bool RoomStayCalendar::free_at(int,int,int)const{return false;}"""),
        _source("""bool RoomStayCalendar::add_room(int room,std::string c){return room>0&&!c.empty()&&rooms_.emplace(room,std::move(c)).second;}
bool RoomStayCalendar::free_at(int room,int start,int end)const{auto it=calendars_.find(room);if(it==calendars_.end())return true;for(auto s:it->second)if(start<s.end&&s.start<end)return false;return true;}
std::optional<int> RoomStayCalendar::book(int reservation,std::string c,int start,int end){if(reservation<=0||c.empty()||start<0||start>=end||reservations_.count(reservation))return std::nullopt;for(auto [room,rc]:rooms_)if(rc==c&&free_at(room,start,end)){calendars_[room].push_back({reservation,start,end});reservations_[reservation]=room;return room;}return std::nullopt;}
bool RoomStayCalendar::cancel(int reservation){auto it=reservations_.find(reservation);if(it==reservations_.end())return false;auto& v=calendars_[it->second];v.erase(std::remove_if(v.begin(),v.end(),[&](auto s){return s.reservation==reservation;}),v.end());reservations_.erase(it);return true;}
std::optional<int> RoomStayCalendar::room_for(int reservation)const{auto it=reservations_.find(reservation);return it==reservations_.end()?std::nullopt:std::optional<int>(it->second);}
std::optional<int> RoomStayCalendar::earliest_free(std::string c,int from,int duration)const{if(c.empty()||from<0||duration<=0||from>std::numeric_limits<int>::max()-duration)return std::nullopt;std::vector<int> starts{from};for(auto [room,rc]:rooms_)if(rc==c){auto it=calendars_.find(room);if(it!=calendars_.end())for(auto s:it->second)if(s.end>=from)starts.push_back(s.end);}std::sort(starts.begin(),starts.end());for(int start:starts){if(start>std::numeric_limits<int>::max()-duration)continue;for(auto [room,rc]:rooms_)if(rc==c&&free_at(room,start,start+duration))return room;}return std::nullopt;}"""),
        _test("RoomStayCalendar", "RoomStayCalendar x; check(x.add_room(2,\"suite\")); check(x.add_room(1,\"suite\")); check(x.book(1,\"suite\",0,10)==1); check(x.book(2,\"suite\",10,20)==1); check(x.book(3,\"suite\",5,8)==2); check(x.room_for(3)==2); check(x.cancel(1)); check(x.book(4,\"suite\",1,2)==1);"),
        _test("RoomStayCalendar", "RoomStayCalendar x; check(!x.add_room(0,\"x\")); check(x.add_room(1,\"x\")); check(!x.book(1,\"x\",2,2)); check(x.book(1,\"x\",2,4)==1); check(x.earliest_free(\"x\",2,2)==1); check(!x.cancel(9)); check(x.cancel(1));"),
        ("struct Stay", "start<s.end&&s.start<end", "calendars_"),
    ),
)

CASES += (
    Case(
        "registry-incident-routing", "service-incident-queue", "Service incident queue", "ServiceIncidentQueue",
        "Preserve incident service and opening time while severity escalates and resolution removes work.",
        _header("""class ServiceIncidentQueue { public: bool open(int id,std::string service,int severity,int opened); bool escalate(int id,int severity); bool resolve(int id); std::optional<int> next(std::string service) const; std::vector<int> unresolved(std::string service) const;
 private: struct Incident { std::string service; int severity; int opened; }; using Key=std::tuple<int,int,int>; std::map<int,Incident> incidents_; std::map<std::string,std::set<Key>> queues_; };"""),
        _source("""bool ServiceIncidentQueue::open(int,std::string,int,int){return false;} bool ServiceIncidentQueue::escalate(int,int){return false;} bool ServiceIncidentQueue::resolve(int){return false;} std::optional<int> ServiceIncidentQueue::next(std::string)const{return std::nullopt;} std::vector<int> ServiceIncidentQueue::unresolved(std::string)const{return {};}"""),
        _source("""bool ServiceIncidentQueue::open(int id,std::string service,int severity,int opened){if(id<=0||service.empty()||severity<0||severity>10||opened<0||incidents_.count(id))return false;incidents_[id]={service,severity,opened};queues_[service].insert({-severity,opened,id});return true;}
bool ServiceIncidentQueue::escalate(int id,int severity){auto it=incidents_.find(id);if(it==incidents_.end()||severity<it->second.severity||severity>10)return false;auto& q=queues_[it->second.service];q.erase({-it->second.severity,it->second.opened,id});it->second.severity=severity;q.insert({-severity,it->second.opened,id});return true;}
bool ServiceIncidentQueue::resolve(int id){auto it=incidents_.find(id);if(it==incidents_.end())return false;auto queue=queues_.find(it->second.service);queue->second.erase({-it->second.severity,it->second.opened,id});if(queue->second.empty())queues_.erase(queue);incidents_.erase(it);return true;}
std::vector<int> ServiceIncidentQueue::unresolved(std::string service)const{std::vector<int> out;auto it=queues_.find(service);if(it!=queues_.end())for(auto key:it->second)out.push_back(std::get<2>(key));return out;}
std::optional<int> ServiceIncidentQueue::next(std::string service)const{auto it=queues_.find(service);return it==queues_.end()?std::nullopt:std::optional<int>(std::get<2>(*it->second.begin()));}"""),
        _test("ServiceIncidentQueue", "ServiceIncidentQueue x; check(x.open(2,\"api\",4,1)); check(x.open(1,\"api\",4,1)); check(x.open(3,\"api\",8,9)); check(x.next(\"api\")==3); check(x.resolve(3)); check(x.escalate(2,9)); check(x.unresolved(\"api\")==std::vector<int>({2,1}));"),
        _test("ServiceIncidentQueue", "ServiceIncidentQueue x; check(!x.open(0,\"x\",1,0)); check(x.open(1,\"x\",5,4)); check(!x.escalate(1,4)); check(x.escalate(1,5)); check(!x.resolve(9)); check(x.resolve(1)); check(!x.next(\"x\"));"),
        ("std::map<std::string,std::set<Key>>", "queues_[service].insert", "q.erase", "severity<it->second.severity"),
    ),
    Case(
        "registry-library-loans", "copy-loan-ledger", "Copy loan ledger", "CopyLoanLedger",
        "Keep one active borrower per physical copy with forward-only renewals and strict overdue bounds.",
        _header("""class CopyLoanLedger { public: bool lend(int copy,int patron,int due); bool renew(int copy,int due); bool return_copy(int copy); std::vector<int> overdue(int today) const; std::optional<int> borrower(int copy) const;
 private: struct Loan { int patron; int due; }; std::map<int,Loan> loans_; };"""),
        _source("""bool CopyLoanLedger::lend(int,int,int){return false;} bool CopyLoanLedger::renew(int,int){return false;} bool CopyLoanLedger::return_copy(int){return false;} std::vector<int> CopyLoanLedger::overdue(int)const{return {};} std::optional<int> CopyLoanLedger::borrower(int)const{return std::nullopt;}"""),
        _source("""bool CopyLoanLedger::lend(int copy,int patron,int due){return copy>0&&patron>0&&due>=0&&loans_.emplace(copy,Loan{patron,due}).second;}
bool CopyLoanLedger::renew(int copy,int due){auto it=loans_.find(copy);if(it==loans_.end()||due<=it->second.due)return false;it->second.due=due;return true;}
bool CopyLoanLedger::return_copy(int copy){return loans_.erase(copy)==1U;}
std::vector<int> CopyLoanLedger::overdue(int today)const{std::vector<std::pair<int,int>> v;for(auto [copy,l]:loans_)if(l.due<today)v.push_back({l.due,copy});std::sort(v.begin(),v.end());std::vector<int> out;for(auto p:v)out.push_back(p.second);return out;}
std::optional<int> CopyLoanLedger::borrower(int copy)const{auto it=loans_.find(copy);return it==loans_.end()?std::nullopt:std::optional<int>(it->second.patron);}"""),
        _test("CopyLoanLedger", "CopyLoanLedger x; check(x.lend(2,7,5)); check(x.lend(1,8,3)); check(!x.lend(1,9,9)); check(x.overdue(5)==std::vector<int>({1})); check(x.renew(1,8)); check(x.overdue(9)==std::vector<int>({2,1})); check(x.borrower(1)==8);"),
        _test("CopyLoanLedger", "CopyLoanLedger x; check(!x.lend(0,1,2)); check(x.lend(1,2,4)); check(x.overdue(4).empty()); check(!x.renew(1,4)); check(x.renew(1,5)); check(x.return_copy(1)); check(!x.return_copy(1));"),
        ("struct Loan", "due<=it->second.due", "l.due<today"),
    ),
    Case(
        "registry-maintenance-crews", "crew-workload-ledger", "Crew workload ledger", "CrewWorkloadLedger",
        "Constrain weighted work by per-crew capacity and reassign work atomically.",
        _header("""class CrewWorkloadLedger { public: bool add_crew(std::string crew,int capacity); bool assign(int order,std::string crew,int effort); bool reassign(int order,std::string crew); bool complete(int order); std::optional<int> workload(std::string crew) const; std::vector<std::string> available_for(int effort) const;
 private: struct Work { std::string crew; int effort; }; std::map<std::string,int> capacity_; std::map<std::string,int> load_; std::map<int,Work> work_; };"""),
        _source("""bool CrewWorkloadLedger::add_crew(std::string,int){return false;} bool CrewWorkloadLedger::assign(int,std::string,int){return false;} bool CrewWorkloadLedger::reassign(int,std::string){return false;} bool CrewWorkloadLedger::complete(int){return false;} std::optional<int> CrewWorkloadLedger::workload(std::string)const{return std::nullopt;} std::vector<std::string> CrewWorkloadLedger::available_for(int)const{return {};}"""),
        _source("""bool CrewWorkloadLedger::add_crew(std::string crew,int cap){return !crew.empty()&&cap>=0&&capacity_.emplace(crew,cap).second;}
bool CrewWorkloadLedger::assign(int order,std::string crew,int effort){if(order<=0||effort<=0||work_.count(order)||!capacity_.count(crew)||load_[crew]>capacity_[crew]-effort)return false;work_[order]={crew,effort};load_[crew]+=effort;return true;}
bool CrewWorkloadLedger::reassign(int order,std::string crew){auto it=work_.find(order);if(it==work_.end()||!capacity_.count(crew))return false;if(it->second.crew==crew)return true;if(load_[crew]>capacity_[crew]-it->second.effort)return false;load_[it->second.crew]-=it->second.effort;load_[crew]+=it->second.effort;it->second.crew=crew;return true;}
bool CrewWorkloadLedger::complete(int order){auto it=work_.find(order);if(it==work_.end())return false;load_[it->second.crew]-=it->second.effort;work_.erase(it);return true;}
std::optional<int> CrewWorkloadLedger::workload(std::string crew)const{if(!capacity_.count(crew))return std::nullopt;auto it=load_.find(crew);return it==load_.end()?std::optional<int>(0):std::optional<int>(it->second);}
std::vector<std::string> CrewWorkloadLedger::available_for(int effort)const{std::vector<std::string> out;if(effort<=0)return out;for(auto [crew,cap]:capacity_){auto it=load_.find(crew);int used=it==load_.end()?0:it->second;if(used<=cap-effort)out.push_back(crew);}return out;}"""),
        _test("CrewWorkloadLedger", "CrewWorkloadLedger x; check(x.add_crew(\"a\",5)); check(x.add_crew(\"b\",5)); check(x.assign(1,\"a\",4)); check(!x.assign(2,\"a\",2)); check(x.assign(2,\"b\",2)); check(!x.reassign(1,\"b\")); check(x.complete(2)); check(x.reassign(1,\"b\")); check(x.workload(\"b\")==4);"),
        _test("CrewWorkloadLedger", "CrewWorkloadLedger x; check(x.add_crew(\"zero\",0)); check(!x.assign(1,\"zero\",1)); check(x.add_crew(\"a\",10)); check(x.assign(1,\"a\",7)); check(x.available_for(4).empty()); check(x.complete(1)); check(x.workload(\"a\")==0);"),
        ("struct Work", "load_[crew]+=effort", "load_[it->second.crew]-="),
    ),
    Case(
        "registry-museum-assets", "asset-custody-history", "Asset custody history", "AssetCustodyHistory",
        "Preserve an append-only, timestamped custody chain and answer historical owner queries.",
        _header("""struct CustodyEvent { std::string custodian; int stamp; bool operator==(const CustodyEvent& o) const { return custodian==o.custodian&&stamp==o.stamp; } };
class AssetCustodyHistory { public: bool add_asset(int asset,std::string custodian,int stamp); bool transfer(int asset,std::string custodian,int stamp); bool erase_asset(int asset); std::optional<std::string> owner_at(int asset,int stamp) const; std::vector<CustodyEvent> history(int asset) const;
 private: std::map<int,std::vector<CustodyEvent>> events_; };"""),
        _source("""bool AssetCustodyHistory::add_asset(int,std::string,int){return false;} bool AssetCustodyHistory::transfer(int,std::string,int){return false;} bool AssetCustodyHistory::erase_asset(int){return false;} std::optional<std::string> AssetCustodyHistory::owner_at(int,int)const{return std::nullopt;} std::vector<CustodyEvent> AssetCustodyHistory::history(int)const{return {};}"""),
        _source("""bool AssetCustodyHistory::add_asset(int id,std::string custodian,int stamp){return id>0&&!custodian.empty()&&stamp>=0&&events_.emplace(id,std::vector<CustodyEvent>{{std::move(custodian),stamp}}).second;}
bool AssetCustodyHistory::transfer(int id,std::string custodian,int stamp){auto it=events_.find(id);if(it==events_.end()||custodian.empty()||stamp<=it->second.back().stamp)return false;it->second.push_back({std::move(custodian),stamp});return true;}
bool AssetCustodyHistory::erase_asset(int id){return events_.erase(id)==1U;}
std::optional<std::string> AssetCustodyHistory::owner_at(int id,int stamp)const{auto found=events_.find(id);if(found==events_.end()||stamp<0)return std::nullopt;const auto& chain=found->second;auto it=std::upper_bound(chain.begin(),chain.end(),stamp,[](int value,const CustodyEvent& event){return value<event.stamp;});if(it==chain.begin())return std::nullopt;return std::prev(it)->custodian;}
std::vector<CustodyEvent> AssetCustodyHistory::history(int id)const{auto it=events_.find(id);return it==events_.end()?std::vector<CustodyEvent>{}:it->second;}"""),
        _test("AssetCustodyHistory", "AssetCustodyHistory x; check(x.add_asset(1,\"museum\",2)); check(x.transfer(1,\"lab\",5)); check(x.transfer(1,\"vault\",9)); check(x.owner_at(1,1)==std::nullopt); check(x.owner_at(1,5)==\"lab\"); check(x.history(1)==std::vector<curriculum::CustodyEvent>({{\"museum\",2},{\"lab\",5},{\"vault\",9}}));"),
        _test("AssetCustodyHistory", "AssetCustodyHistory x; check(!x.add_asset(0,\"a\",0)); check(x.add_asset(1,\"a\",0)); check(!x.transfer(1,\"b\",0)); check(!x.transfer(1,\"\",2)); check(x.transfer(1,\"b\",2)); check(x.erase_asset(1)); check(x.history(1).empty()); check(!x.erase_asset(1));"),
        ("std::map<int,std::vector<CustodyEvent>>", "std::upper_bound", "it->second.push_back", "std::prev(it)"),
    ),
    Case(
        "registry-parking-permits", "permit-expiry-wheel", "Permit expiry wheel", "PermitExpiryWheel",
        "Place and extend permits in bounded modular expiry buckets without accepting stale bucket entries.",
        _header("""class PermitExpiryWheel { public: explicit PermitExpiryWheel(std::size_t horizon); bool issue(int permit,std::string zone,std::size_t delay); bool extend(int permit,std::size_t delay); bool revoke(int permit); std::vector<int> advance(std::size_t ticks); std::vector<int> active_in(std::string zone) const; std::size_t now() const;
 private: struct Permit { std::string zone; std::size_t due; }; std::vector<std::vector<int>> wheel_; std::map<int,Permit> permits_; std::size_t now_=0U; };"""),
        _source("""PermitExpiryWheel::PermitExpiryWheel(std::size_t){} bool PermitExpiryWheel::issue(int,std::string,std::size_t){return false;} bool PermitExpiryWheel::extend(int,std::size_t){return false;} bool PermitExpiryWheel::revoke(int){return false;} std::vector<int> PermitExpiryWheel::advance(std::size_t){return {};} std::vector<int> PermitExpiryWheel::active_in(std::string)const{return {};} std::size_t PermitExpiryWheel::now()const{return 0;}"""),
        _source("""PermitExpiryWheel::PermitExpiryWheel(std::size_t horizon):wheel_(horizon){}
bool PermitExpiryWheel::issue(int id,std::string zone,std::size_t delay){if(id<=0||zone.empty()||wheel_.empty()||delay==0||delay>wheel_.size()||permits_.count(id))return false;std::size_t due=now_+delay;permits_[id]={std::move(zone),due};wheel_[due%wheel_.size()].push_back(id);return true;}
bool PermitExpiryWheel::extend(int id,std::size_t delay){auto it=permits_.find(id);if(it==permits_.end()||delay==0||delay>wheel_.size())return false;it->second.due=now_+delay;wheel_[it->second.due%wheel_.size()].push_back(id);return true;}
bool PermitExpiryWheel::revoke(int id){return permits_.erase(id)==1U;}
std::vector<int> PermitExpiryWheel::advance(std::size_t ticks){std::vector<int> out;if(wheel_.empty())return out;for(std::size_t i=0;i<ticks;++i){++now_;auto& bucket=wheel_[now_%wheel_.size()];std::vector<int> keep;std::vector<int> due;for(int id:bucket){auto it=permits_.find(id);if(it==permits_.end())continue;if(it->second.due==now_){due.push_back(id);permits_.erase(it);}else keep.push_back(id);}bucket=std::move(keep);std::sort(due.begin(),due.end());out.insert(out.end(),due.begin(),due.end());}return out;}
std::vector<int> PermitExpiryWheel::active_in(std::string zone)const{std::vector<int> out;for(auto [id,p]:permits_)if(p.zone==zone)out.push_back(id);return out;}
std::size_t PermitExpiryWheel::now()const{return now_;}"""),
        _test("PermitExpiryWheel", "PermitExpiryWheel x(3); check(x.issue(2,\"z\",3)); check(x.issue(1,\"z\",1)); check(x.advance(1)==std::vector<int>({1})); check(x.extend(2,3)); check(x.advance(2).empty()); check(x.active_in(\"z\")==std::vector<int>({2})); check(x.advance(1)==std::vector<int>({2}));"),
        _test("PermitExpiryWheel", "PermitExpiryWheel z(0); check(!z.issue(1,\"x\",1)); PermitExpiryWheel x(2); check(!x.issue(1,\"x\",0)); check(x.issue(1,\"x\",2)); check(!x.extend(1,0)); check(x.extend(1,1)); check(x.advance(1)==std::vector<int>({1})); check(!x.extend(1,1)); check(!x.revoke(1));"),
        ("wheel_", "due%wheel_.size()", "it->second.due==now_"),
        ("std::priority_queue", "struct Entry { int id; std::string group; int rank; int stamp;"),
    ),
    Case(
        "registry-shipping-contracts", "shipping-rate-resolver", "Shipping rate resolver", "ShippingRateResolver",
        "Resolve overlapping weight bands by cost, width, and contract ID.",
        _header("""struct RateQuote { int contract; int cost; bool operator==(const RateQuote& o) const { return contract==o.contract&&cost==o.cost; } };
class ShippingRateResolver { public: bool add(int contract,std::string region,int min_weight,int max_weight,int cost); bool retire(int contract); std::optional<RateQuote> resolve(std::string region,int weight) const; std::vector<int> covering(std::string region,int weight) const;
 private: struct Rate { std::string region; int low; int high; int cost; }; std::map<int,Rate> rates_; };"""),
        _source("""bool ShippingRateResolver::add(int,std::string,int,int,int){return false;} bool ShippingRateResolver::retire(int){return false;} std::optional<RateQuote> ShippingRateResolver::resolve(std::string,int)const{return std::nullopt;} std::vector<int> ShippingRateResolver::covering(std::string,int)const{return {};}"""),
        _source("""bool ShippingRateResolver::add(int id,std::string region,int low,int high,int cost){return id>0&&!region.empty()&&low>=0&&low<=high&&cost>=0&&rates_.emplace(id,Rate{std::move(region),low,high,cost}).second;}
bool ShippingRateResolver::retire(int id){return rates_.erase(id)==1U;}
std::vector<int> ShippingRateResolver::covering(std::string region,int weight)const{struct Choice{int cost;long long width;int id;};std::vector<Choice> v;for(auto [id,r]:rates_)if(r.region==region&&r.low<=weight&&weight<=r.high)v.push_back({r.cost,static_cast<long long>(r.high)-r.low,id});std::sort(v.begin(),v.end(),[](auto a,auto b){return a.cost!=b.cost?a.cost<b.cost:(a.width!=b.width?a.width<b.width:a.id<b.id);});std::vector<int> out;for(auto x:v)out.push_back(x.id);return out;}
std::optional<RateQuote> ShippingRateResolver::resolve(std::string region,int weight)const{auto ids=covering(std::move(region),weight);if(ids.empty())return std::nullopt;return RateQuote{ids.front(),rates_.at(ids.front()).cost};}"""),
        _test("ShippingRateResolver", "ShippingRateResolver x; check(x.add(3,\"eu\",0,10,5)); check(x.add(2,\"eu\",3,7,5)); check(x.add(1,\"eu\",0,9,4)); check(x.covering(\"eu\",5)==std::vector<int>({1,2,3})); check(x.resolve(\"eu\",5)==curriculum::RateQuote{1,4}); check(x.retire(1)); check(x.resolve(\"eu\",5)==curriculum::RateQuote{2,5});"),
        _test("ShippingRateResolver", "ShippingRateResolver x; check(!x.add(1,\"x\",4,3,1)); check(x.add(1,\"x\",0,0,0)); check(x.resolve(\"x\",0)==curriculum::RateQuote{1,0}); check(!x.resolve(\"x\",1)); check(!x.retire(9));"),
        ("struct Rate", "static_cast<long long>(r.high)-r.low", "a.cost!=b.cost"),
    ),
    Case(
        "registry-subscription-plans", "billing-cycle-counter", "Billing cycle counter", "BillingCycleCounter",
        "Reconcile active accounts with a two-dimensional plan and billing-cycle aggregate.",
        _header("""struct BillingCount { std::string plan; std::string cycle; std::size_t active; bool operator==(const BillingCount& o) const { return plan==o.plan&&cycle==o.cycle&&active==o.active; } };
class BillingCycleCounter { public: bool start(int account,std::string plan,std::string cycle); bool change(int account,std::string plan,std::string cycle); bool cancel(int account); std::vector<BillingCount> snapshot() const; std::optional<std::string> plan_of(int account) const;
 private: using Cell=std::pair<std::string,std::string>; std::map<int,Cell> accounts_; std::map<Cell,std::size_t> counts_; };"""),
        _source("""bool BillingCycleCounter::start(int,std::string,std::string){return false;} bool BillingCycleCounter::change(int,std::string,std::string){return false;} bool BillingCycleCounter::cancel(int){return false;} std::vector<BillingCount> BillingCycleCounter::snapshot()const{return {};} std::optional<std::string> BillingCycleCounter::plan_of(int)const{return std::nullopt;}"""),
        _source("""bool BillingCycleCounter::start(int id,std::string plan,std::string cycle){if(id<=0||plan.empty()||cycle.empty()||accounts_.count(id))return false;Cell c{std::move(plan),std::move(cycle)};accounts_[id]=c;++counts_[c];return true;}
bool BillingCycleCounter::change(int id,std::string plan,std::string cycle){auto it=accounts_.find(id);if(it==accounts_.end()||plan.empty()||cycle.empty())return false;Cell next{std::move(plan),std::move(cycle)};if(it->second==next)return true;auto old=it->second;if(--counts_[old]==0)counts_.erase(old);it->second=next;++counts_[next];return true;}
bool BillingCycleCounter::cancel(int id){auto it=accounts_.find(id);if(it==accounts_.end())return false;auto c=it->second;if(--counts_[c]==0)counts_.erase(c);accounts_.erase(it);return true;}
std::vector<BillingCount> BillingCycleCounter::snapshot()const{std::vector<BillingCount> out;for(auto [c,n]:counts_)out.push_back({c.first,c.second,n});return out;}
std::optional<std::string> BillingCycleCounter::plan_of(int id)const{auto it=accounts_.find(id);return it==accounts_.end()?std::nullopt:std::optional<std::string>(it->second.first);}"""),
        _test("BillingCycleCounter", "BillingCycleCounter x; check(x.start(1,\"pro\",\"monthly\")); check(x.start(2,\"pro\",\"annual\")); check(x.change(2,\"pro\",\"monthly\")); check(x.snapshot()==std::vector<curriculum::BillingCount>({{\"pro\",\"monthly\",2}})); check(x.cancel(1)); check(x.snapshot()==std::vector<curriculum::BillingCount>({{\"pro\",\"monthly\",1}}));"),
        _test("BillingCycleCounter", "BillingCycleCounter x; check(!x.start(0,\"p\",\"c\")); check(x.start(1,\"p\",\"c\")); check(x.change(1,\"p\",\"c\")); check(!x.change(9,\"p\",\"c\")); check(x.cancel(1)); check(x.snapshot().empty());"),
        ("using Cell=std::pair", "counts_", "counts_.erase"),
    ),
    Case(
        "registry-support-escalations", "sla-escalation-heap", "SLA escalation heap", "SlaEscalationHeap",
        "Maintain an indexed binary heap under reprioritization/removal and select breached cases.",
        _header("""class SlaEscalationHeap { public: bool open(int id,int priority,int opened,int deadline); bool reprioritize(int id,int priority); bool close(int id); std::optional<int> priority_front() const; std::optional<int> breach_candidate(int now) const; std::size_t size() const;
 private: struct Case { int id; int priority; int opened; int deadline; }; std::vector<Case> heap_; std::map<int,std::size_t> index_; static bool before(const Case&,const Case&); void swap_nodes(std::size_t,std::size_t); void up(std::size_t); void down(std::size_t); };"""),
        _source("""bool SlaEscalationHeap::open(int,int,int,int){return false;} bool SlaEscalationHeap::reprioritize(int,int){return false;} bool SlaEscalationHeap::close(int){return false;} std::optional<int> SlaEscalationHeap::priority_front()const{return std::nullopt;} std::optional<int> SlaEscalationHeap::breach_candidate(int)const{return std::nullopt;} std::size_t SlaEscalationHeap::size()const{return 0;} bool SlaEscalationHeap::before(const Case&,const Case&){return false;} void SlaEscalationHeap::swap_nodes(std::size_t,std::size_t){} void SlaEscalationHeap::up(std::size_t){} void SlaEscalationHeap::down(std::size_t){}"""),
        _source("""bool SlaEscalationHeap::before(const Case&a,const Case&b){return a.priority!=b.priority?a.priority>b.priority:(a.deadline!=b.deadline?a.deadline<b.deadline:(a.opened!=b.opened?a.opened<b.opened:a.id<b.id));}
void SlaEscalationHeap::swap_nodes(std::size_t a,std::size_t b){std::swap(heap_[a],heap_[b]);index_[heap_[a].id]=a;index_[heap_[b].id]=b;}
void SlaEscalationHeap::up(std::size_t i){while(i){std::size_t p=(i-1)/2;if(!before(heap_[i],heap_[p]))break;swap_nodes(i,p);i=p;}}
void SlaEscalationHeap::down(std::size_t i){for(;;){std::size_t best=i,l=2*i+1,r=l+1;if(l<heap_.size()&&before(heap_[l],heap_[best]))best=l;if(r<heap_.size()&&before(heap_[r],heap_[best]))best=r;if(best==i)break;swap_nodes(i,best);i=best;}}
bool SlaEscalationHeap::open(int id,int priority,int opened,int deadline){if(id<=0||priority<0||priority>100||opened<0||deadline<opened||index_.count(id))return false;index_[id]=heap_.size();heap_.push_back({id,priority,opened,deadline});up(heap_.size()-1);return true;}
bool SlaEscalationHeap::reprioritize(int id,int priority){auto it=index_.find(id);if(it==index_.end()||priority<0||priority>100)return false;std::size_t i=it->second;heap_[i].priority=priority;up(i);down(index_[id]);return true;}
bool SlaEscalationHeap::close(int id){auto it=index_.find(id);if(it==index_.end())return false;std::size_t i=it->second,last=heap_.size()-1;swap_nodes(i,last);heap_.pop_back();index_.erase(id);if(i<heap_.size()){int moved=heap_[i].id;up(i);down(index_[moved]);}return true;}
std::optional<int> SlaEscalationHeap::priority_front()const{return heap_.empty()?std::nullopt:std::optional<int>(heap_.front().id);}
std::optional<int> SlaEscalationHeap::breach_candidate(int now)const{std::optional<Case> best;for(const auto& c:heap_)if(c.deadline<=now&&(!best||before(c,*best)))best=c;return best?std::optional<int>(best->id):std::nullopt;}
std::size_t SlaEscalationHeap::size()const{return heap_.size();}"""),
        _test("SlaEscalationHeap", "SlaEscalationHeap x; check(x.open(1,5,0,10)); check(x.open(2,8,1,20)); check(x.priority_front()==2); check(!x.breach_candidate(9)); check(x.breach_candidate(10)==1); check(x.reprioritize(1,9)); check(x.priority_front()==1); check(x.open(3,10,0,8)); check(x.priority_front()==3); check(x.close(3)); check(x.priority_front()==1);"),
        _test("SlaEscalationHeap", "SlaEscalationHeap x; for(int i=1;i<=30;++i)check(x.open(i,i%11,i,40+i)); for(int i=1;i<=30;i+=3)check(x.reprioritize(i,99-i)); for(int i=2;i<=30;i+=4)check(x.close(i)); check(x.size()==22); check(!x.open(0,1,0,1)); check(!x.reprioritize(99,1));"),
        ("std::vector<Case> heap_", "index_", "void SlaEscalationHeap::up", "void SlaEscalationHeap::down"),
        ("std::priority_queue", "std::make_heap", "std::push_heap", "std::pop_heap", "struct Entry { int id; std::string group; int rank; int stamp;"),
    ),
    Case(
        "registry-vaccine-inventory", "vaccine-lot-fefo", "Vaccine lot FEFO", "VaccineLotFefo",
        "Plan and commit transactional multi-lot first-expiry-first-out allocations.",
        _header("""struct LotUse { int lot; int doses; bool operator==(const LotUse& o) const { return lot==o.lot&&doses==o.doses; } };
class VaccineLotFefo { public: bool receive(int lot,std::string product,int expiry,int doses); std::optional<std::vector<LotUse>> allocate(std::string product,int today,int doses); std::optional<int> remaining(int lot) const; std::vector<int> expiring(std::string product,int by) const;
 private: struct Lot { std::string product; int expiry; int remaining; }; std::map<int,Lot> lots_; };"""),
        _source("""bool VaccineLotFefo::receive(int,std::string,int,int){return false;} std::optional<std::vector<LotUse>> VaccineLotFefo::allocate(std::string,int,int){return std::nullopt;} std::optional<int> VaccineLotFefo::remaining(int)const{return std::nullopt;} std::vector<int> VaccineLotFefo::expiring(std::string,int)const{return {};}"""),
        _source("""bool VaccineLotFefo::receive(int id,std::string product,int expiry,int doses){return id>0&&!product.empty()&&expiry>=0&&doses>0&&lots_.emplace(id,Lot{std::move(product),expiry,doses}).second;}
std::vector<int> VaccineLotFefo::expiring(std::string product,int by)const{std::vector<std::pair<int,int>> v;for(auto [id,l]:lots_)if(l.product==product&&l.remaining>0&&l.expiry<=by)v.push_back({l.expiry,id});std::sort(v.begin(),v.end());std::vector<int> out;for(auto p:v)out.push_back(p.second);return out;}
std::optional<std::vector<LotUse>> VaccineLotFefo::allocate(std::string product,int today,int doses){if(product.empty()||today<0||doses<=0)return std::nullopt;struct Candidate{int expiry;int id;};std::vector<Candidate> order;long long total=0;for(auto [id,l]:lots_)if(l.product==product&&l.expiry>=today&&l.remaining>0){order.push_back({l.expiry,id});total+=l.remaining;}if(total<doses)return std::nullopt;std::sort(order.begin(),order.end(),[](auto a,auto b){return a.expiry!=b.expiry?a.expiry<b.expiry:a.id<b.id;});std::vector<LotUse> plan;int left=doses;for(auto c:order){int take=std::min(left,lots_[c.id].remaining);if(take){plan.push_back({c.id,take});left-=take;}if(!left)break;}for(auto use:plan)lots_[use.lot].remaining-=use.doses;return plan;}
std::optional<int> VaccineLotFefo::remaining(int id)const{auto it=lots_.find(id);return it==lots_.end()?std::nullopt:std::optional<int>(it->second.remaining);}"""),
        _test("VaccineLotFefo", "VaccineLotFefo x; check(x.receive(2,\"p\",8,4)); check(x.receive(1,\"p\",5,3)); check(x.allocate(\"p\",5,5)==std::vector<curriculum::LotUse>({{1,3},{2,2}})); check(x.remaining(1)==0); check(x.remaining(2)==2);"),
        _test("VaccineLotFefo", "VaccineLotFefo x; check(x.receive(1,\"p\",4,2)); check(x.receive(2,\"p\",5,2)); check(!x.allocate(\"p\",5,3)); check(x.remaining(1)==2); check(x.remaining(2)==2); check(x.allocate(\"p\",4,4).has_value()); check(!x.allocate(\"p\",4,1));"),
        ("std::vector<LotUse> plan", "total<doses", "for(auto use:plan)"),
    ),
    Case(
        "registry-warehouse-batches", "warehouse-batch-splitter", "Warehouse batch splitter", "WarehouseBatchSplitter",
        "Conserve weighted batch units across split, merge, and atomic zone moves.",
        _header("""class WarehouseBatchSplitter { public: bool add_zone(std::string zone,int capacity); bool receive(int batch,std::string zone,int units,int expiry); bool split(int batch,int new_batch,int units); bool merge(int target,int source); bool move(int batch,std::string zone); std::vector<int> expiring(std::string zone,int by) const;
 private: struct Batch { std::string zone; int units; int expiry; }; std::map<std::string,int> capacity_; std::map<std::string,int> load_; std::map<int,Batch> batches_; };"""),
        _source("""bool WarehouseBatchSplitter::add_zone(std::string,int){return false;} bool WarehouseBatchSplitter::receive(int,std::string,int,int){return false;} bool WarehouseBatchSplitter::split(int,int,int){return false;} bool WarehouseBatchSplitter::merge(int,int){return false;} bool WarehouseBatchSplitter::move(int,std::string){return false;} std::vector<int> WarehouseBatchSplitter::expiring(std::string,int)const{return {};}"""),
        _source("""bool WarehouseBatchSplitter::add_zone(std::string zone,int capacity){return !zone.empty()&&capacity>=0&&capacity_.emplace(zone,capacity).second;}
bool WarehouseBatchSplitter::receive(int id,std::string zone,int units,int expiry){if(id<=0||units<=0||expiry<0||batches_.count(id)||!capacity_.count(zone)||load_[zone]>capacity_[zone]-units)return false;batches_[id]={zone,units,expiry};load_[zone]+=units;return true;}
bool WarehouseBatchSplitter::split(int id,int fresh,int units){auto it=batches_.find(id);if(it==batches_.end()||fresh<=0||batches_.count(fresh)||units<=0||units>=it->second.units)return false;it->second.units-=units;batches_[fresh]={it->second.zone,units,it->second.expiry};return true;}
bool WarehouseBatchSplitter::merge(int target,int source){auto a=batches_.find(target),b=batches_.find(source);if(a==batches_.end()||b==batches_.end()||target==source||a->second.zone!=b->second.zone||a->second.expiry!=b->second.expiry||a->second.units>std::numeric_limits<int>::max()-b->second.units)return false;a->second.units+=b->second.units;batches_.erase(b);return true;}
bool WarehouseBatchSplitter::move(int id,std::string zone){auto it=batches_.find(id);if(it==batches_.end()||!capacity_.count(zone))return false;if(it->second.zone==zone)return true;if(load_[zone]>capacity_[zone]-it->second.units)return false;load_[it->second.zone]-=it->second.units;load_[zone]+=it->second.units;it->second.zone=zone;return true;}
std::vector<int> WarehouseBatchSplitter::expiring(std::string zone,int by)const{std::vector<std::pair<int,int>> v;for(auto [id,b]:batches_)if(b.zone==zone&&b.expiry<=by)v.push_back({b.expiry,id});std::sort(v.begin(),v.end());std::vector<int> out;for(auto p:v)out.push_back(p.second);return out;}"""),
        _test("WarehouseBatchSplitter", "WarehouseBatchSplitter x; check(x.add_zone(\"a\",10)); check(x.add_zone(\"b\",4)); check(x.receive(1,\"a\",8,4)); check(x.split(1,2,3)); check(!x.move(1,\"b\")); check(x.move(2,\"b\")); check(x.expiring(\"b\",4)==std::vector<int>({2}));"),
        _test("WarehouseBatchSplitter", "WarehouseBatchSplitter x; check(x.add_zone(\"a\",10)); check(x.receive(1,\"a\",6,2)); check(x.split(1,2,2)); check(x.merge(1,2)); check(!x.merge(1,1)); check(!x.split(1,3,6)); check(!x.receive(4,\"a\",5,1));"),
        ("struct Batch", "it->second.units-=units", "a->second.units+=b->second.units", "load_[zone]+="),
    ),
)
