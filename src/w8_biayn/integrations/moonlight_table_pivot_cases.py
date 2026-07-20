"""Algorithmically distinct C++17 cases for table-pivot family remediation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PivotCase:
    legacy_id: str
    task_id: str
    title: str
    objective: str
    public_api: str
    profile: str
    marker: str
    instructions: str
    header: str
    reference: str
    visible_test: str
    hidden_test: str
    negative_old: str
    negative_new: str
    negative_reason: str
    disposition: str = "replace"


def _header(declarations: str, includes: str = "<vector>") -> str:
    declarations = declarations.replace("#include <string>\n", "")
    return f"""#pragma once
#include {includes}
#include <string>
namespace curriculum {{
{declarations}
}}  // namespace curriculum
"""


def _source(body: str, extra: str = "") -> str:
    # Keep every statement on its own physical line so GCC's strict
    # -Wmisleading-indentation check can judge the generated source reliably.
    body = body.replace(";", ";\n")
    return f"""#include \"task.h\"
{extra}
namespace curriculum {{
{body}
}}  // namespace curriculum
"""


def _test(body: str, extra: str = "") -> str:
    return f"""#include \"task.h\"
{extra}
int main() {{
  int failures = 0;
  const auto check = [&](bool value) {{ if (!value) ++failures; }};
{body}
  return failures == 0 ? 0 : 1;
}}
"""


CASES = (
    PivotCase(
        legacy_id="pivot-call-center",
        task_id="pivot-call-center",
        title="Call-center shift pivot",
        objective="Build an agent-by-shift call matrix and select each agent's busiest shift with an earliest-shift tie rule.",
        public_api="CallMatrix pivot_calls(const std::vector<std::string>& shifts, const std::vector<CallRecord>& calls)",
        profile="validated additive cross-tabulation plus earliest argmax per row",
        marker="agent_shift_cells",
        disposition="repair-in-place",
        instructions="""Implement `pivot_calls`. Shift names must be nonempty and unique. Each call has a nonempty agent, a known shift, and a nonnegative handled count. Sum duplicate agent/shift records. Emit agents lexicographically, preserve shift order, and report the earliest busiest shift; an all-zero row chooses the first shift. Empty calls are valid, but an empty shift schema is invalid.""",
        header=_header("""#include <string>
struct CallRecord { std::string agent; std::string shift; int handled; };
struct AgentCalls { std::string agent; std::vector<int> counts; int total=0; int busiest_shift=-1; };
struct CallMatrix { bool valid=false; std::vector<std::string> shifts; std::vector<AgentCalls> rows; };
CallMatrix pivot_calls(const std::vector<std::string>& shifts, const std::vector<CallRecord>& calls);"""),
        reference=_source("""CallMatrix pivot_calls(const std::vector<std::string>& shifts,const std::vector<CallRecord>& calls){
  CallMatrix out; std::map<std::string,int> shift_index;
  for(int i=0;i<static_cast<int>(shifts.size());++i) if(shifts[static_cast<std::size_t>(i)].empty()||!shift_index.emplace(shifts[static_cast<std::size_t>(i)],i).second)return out;
  if(shifts.empty())return out; std::map<std::string,std::vector<int>> agent_shift_cells;
  for(const auto& call:calls){auto it=shift_index.find(call.shift);if(call.agent.empty()||call.handled<0||it==shift_index.end())return out;agent_shift_cells[call.agent].resize(shifts.size());agent_shift_cells[call.agent][static_cast<std::size_t>(it->second)]+=call.handled;}
  out.valid=true;out.shifts=shifts;for(const auto& entry:agent_shift_cells){AgentCalls row;row.agent=entry.first;row.counts=entry.second;row.busiest_shift=0;for(int i=0;i<static_cast<int>(row.counts.size());++i){row.total+=row.counts[static_cast<std::size_t>(i)];if(row.counts[static_cast<std::size_t>(i)]>row.counts[static_cast<std::size_t>(row.busiest_shift)])row.busiest_shift=i;}out.rows.push_back(row);}return out;
}""", "#include <map>"),
        visible_test=_test("""  const auto r=curriculum::pivot_calls({"morning","evening"},{{"bea","evening",3},{"ana","morning",2},{"ana","evening",2},{"bea","evening",4}});
  check(r.valid&&r.rows.size()==2&&r.rows[0].agent=="ana"&&r.rows[0].total==4&&r.rows[0].busiest_shift==0);
  check(r.rows[1].counts==std::vector<int>({0,7})&&r.rows[1].busiest_shift==1);"""),
        hidden_test=_test("""  check(curriculum::pivot_calls({"day"},{}).valid);
  check(!curriculum::pivot_calls({},{}).valid);
  check(!curriculum::pivot_calls({"day","day"},{}).valid);
  check(!curriculum::pivot_calls({"day"},{{"a","night",1}}).valid);
  const auto z=curriculum::pivot_calls({"a","b"},{{"x","b",0}});check(z.valid&&z.rows[0].busiest_shift==0);"""),
        negative_old="row.busiest_shift=0;",
        negative_new="row.busiest_shift=static_cast<int>(row.counts.size())-1;",
        negative_reason="breaks the earliest-shift tie rule",
    ),
    PivotCase(
        legacy_id="pivot-clinic-visits",
        task_id="clinic-state-transition-grid",
        title="Clinic state-transition grid",
        objective="Count transitions between consecutive visit states rather than merely grouping observations.",
        public_api="TransitionGrid build_transition_grid(const std::vector<std::string>& states, const std::vector<VisitState>& visits)",
        profile="per-patient chronological state machine folded into a square transition matrix",
        marker="chronological_visits",
        instructions="""Implement `build_transition_grid`. States are a nonempty unique ordered schema. Visits require nonempty patients, known states, and nonnegative unique sequence numbers per patient. Sort each patient's visits by sequence and count each adjacent state transition. Preserve schema order. A patient with fewer than two visits contributes no transition.""",
        header=_header("""#include <string>
struct VisitState { std::string patient; int sequence; std::string state; };
struct TransitionGrid { bool valid=false; std::vector<std::string> states; std::vector<std::vector<int>> counts; int transitions=0; };
TransitionGrid build_transition_grid(const std::vector<std::string>& states,const std::vector<VisitState>& visits);"""),
        reference=_source("""TransitionGrid build_transition_grid(const std::vector<std::string>& states,const std::vector<VisitState>& visits){
  TransitionGrid out;std::map<std::string,int> ids;for(int i=0;i<static_cast<int>(states.size());++i)if(states[static_cast<std::size_t>(i)].empty()||!ids.emplace(states[static_cast<std::size_t>(i)],i).second)return out;if(states.empty())return out;
  std::map<std::string,std::vector<std::pair<int,int>>> chronological_visits;for(const auto& v:visits){auto it=ids.find(v.state);if(v.patient.empty()||v.sequence<0||it==ids.end())return out;chronological_visits[v.patient].push_back({v.sequence,it->second});}
  out.counts.assign(states.size(),std::vector<int>(states.size()));for(auto& entry:chronological_visits){auto& row=entry.second;std::sort(row.begin(),row.end());for(std::size_t i=1;i<row.size();++i){if(row[i-1].first==row[i].first)return TransitionGrid{};++out.counts[static_cast<std::size_t>(row[i-1].second)][static_cast<std::size_t>(row[i].second)];++out.transitions;}}out.valid=true;out.states=states;return out;
}""", "#include <algorithm>\n#include <map>\n#include <utility>"),
        visible_test=_test("""  const auto g=curriculum::build_transition_grid({"waiting","seen","released"},{{"p",2,"released"},{"p",0,"waiting"},{"p",1,"seen"},{"q",0,"waiting"},{"q",1,"seen"}});
  check(g.valid&&g.transitions==3&&g.counts[0][1]==2&&g.counts[1][2]==1);"""),
        hidden_test=_test("""  check(curriculum::build_transition_grid({"x"},{}).valid);
  check(!curriculum::build_transition_grid({},{}).valid);
  check(!curriculum::build_transition_grid({"x"},{{"p",0,"y"}}).valid);
  check(!curriculum::build_transition_grid({"x"},{{"p",0,"x"},{"p",0,"x"}}).valid);"""),
        negative_old="std::sort(row.begin(),row.end());",
        negative_new="std::sort(row.rbegin(),row.rend());",
        negative_reason="reverses chronological transitions",
    ),
    PivotCase(
        legacy_id="pivot-community-events",
        task_id="venue-capacity-grid",
        title="Venue capacity allocation grid",
        objective="Allocate registrations into session columns while enforcing a separate venue/session capacity table.",
        public_api="VenueGrid allocate_sessions(const std::vector<Capacity>& capacities, const std::vector<Registration>& registrations)",
        profile="capacity-key join plus duplicate-summing allocation and overflow rejection",
        marker="capacity_by_cell",
        instructions="""Implement `allocate_sessions`. Capacity keys and registration keys require nonempty venue/session names. Capacity cells must be unique and nonnegative. Every registration must match a capacity cell and have nonnegative seats. Sum registrations per cell; if any total exceeds capacity, return invalid. Emit venues and sessions lexicographically and occupancy rows in that cross-product.""",
        header=_header("""#include <string>
struct Capacity { std::string venue; std::string session; int seats; };
struct Registration { std::string venue; std::string session; int seats; };
struct VenueGrid { bool valid=false; std::vector<std::string> venues; std::vector<std::string> sessions; std::vector<std::vector<int>> occupied; };
VenueGrid allocate_sessions(const std::vector<Capacity>& capacities,const std::vector<Registration>& registrations);"""),
        reference=_source("""VenueGrid allocate_sessions(const std::vector<Capacity>& capacities,const std::vector<Registration>& registrations){
  VenueGrid out;std::map<std::pair<std::string,std::string>,int> capacity_by_cell,used;std::set<std::string> venues,sessions;
  for(const auto& c:capacities){if(c.venue.empty()||c.session.empty()||c.seats<0||!capacity_by_cell.emplace(std::make_pair(c.venue,c.session),c.seats).second)return out;venues.insert(c.venue);sessions.insert(c.session);}
  for(const auto& r:registrations){auto key=std::make_pair(r.venue,r.session);auto it=capacity_by_cell.find(key);if(r.venue.empty()||r.session.empty()||r.seats<0||it==capacity_by_cell.end())return out;used[key]+=r.seats;if(used[key]>it->second)return out;}
  out.valid=true;out.venues.assign(venues.begin(),venues.end());out.sessions.assign(sessions.begin(),sessions.end());for(const auto& v:out.venues){std::vector<int> row;for(const auto& s:out.sessions)row.push_back(used[{v,s}]);out.occupied.push_back(row);}return out;
}""", "#include <map>\n#include <set>\n#include <utility>"),
        visible_test=_test("""  const auto g=curriculum::allocate_sessions({{"hall","am",5},{"hall","pm",4},{"yard","am",3}},{{"hall","am",2},{"hall","am",1},{"yard","am",3}});
  check(g.valid&&g.venues==std::vector<std::string>({"hall","yard"})&&g.sessions==std::vector<std::string>({"am","pm"}));
  check(g.occupied[0]==std::vector<int>({3,0})&&g.occupied[1][0]==3);""", "#include <string>"),
        hidden_test=_test("""  check(curriculum::allocate_sessions({},{}).valid);
  check(!curriculum::allocate_sessions({{"v","s",1}},{{"v","s",2}}).valid);
  check(!curriculum::allocate_sessions({{"v","s",1},{"v","s",2}},{}).valid);
  check(!curriculum::allocate_sessions({{"v","s",1}},{{"v","x",1}}).valid);"""),
        negative_old="if(used[key]>it->second)return out;",
        negative_new="if(used[key]>=it->second)return out;",
        negative_reason="rejects exactly-full valid sessions",
    ),
    PivotCase(
        legacy_id="pivot-emergency-supplies",
        task_id="depot-shortfall-table",
        title="Depot shortfall table",
        objective="Join required and observed stock tables and rank only positive per-depot shortfalls.",
        public_api="ShortfallTable compute_shortfalls(const std::vector<StockTarget>& targets, const std::vector<StockCheck>& checks)",
        profile="full-key target/check reconciliation plus descending deficit selection",
        marker="target_by_key",
        instructions="""Implement `compute_shortfalls`. Targets are unique nonempty depot/item keys with nonnegative required quantities. Checks use the same validation and may repeat; the last sequence wins, with unique sequence numbers per key. Every check must have a target. Missing checks mean observed zero. Emit positive shortfalls sorted by units descending, then depot, then item.""",
        header=_header("""#include <string>
struct StockTarget { std::string depot; std::string item; int required; };
struct StockCheck { std::string depot; std::string item; int sequence; int observed; };
struct Shortfall { std::string depot; std::string item; int missing; };
struct ShortfallTable { bool valid=false; std::vector<Shortfall> rows; int missing_units=0; };
ShortfallTable compute_shortfalls(const std::vector<StockTarget>& targets,const std::vector<StockCheck>& checks);"""),
        reference=_source("""ShortfallTable compute_shortfalls(const std::vector<StockTarget>& targets,const std::vector<StockCheck>& checks){
  ShortfallTable out;using Key=std::pair<std::string,std::string>;std::map<Key,int> target_by_key;for(const auto&t:targets)if(t.depot.empty()||t.item.empty()||t.required<0||!target_by_key.emplace(Key{t.depot,t.item},t.required).second)return out;
  std::map<Key,std::pair<int,int>> latest;for(const auto&c:checks){Key key{c.depot,c.item};if(c.sequence<0||c.observed<0||target_by_key.count(key)==0)return out;auto it=latest.find(key);if(it!=latest.end()&&it->second.first==c.sequence)return out;if(it==latest.end()||c.sequence>it->second.first)latest[key]={c.sequence,c.observed};}
  for(const auto& entry:target_by_key){int observed=latest.count(entry.first)?latest[entry.first].second:0;int missing=entry.second-observed;if(missing>0){out.rows.push_back({entry.first.first,entry.first.second,missing});out.missing_units+=missing;}}
  std::sort(out.rows.begin(),out.rows.end(),[](const auto&a,const auto&b){if(a.missing!=b.missing)return a.missing>b.missing;if(a.depot!=b.depot)return a.depot<b.depot;return a.item<b.item;});out.valid=true;return out;
}""", "#include <algorithm>\n#include <map>\n#include <utility>"),
        visible_test=_test("""  const auto t=curriculum::compute_shortfalls({{"north","water",10},{"south","food",8}},{{"north","water",0,4},{"north","water",1,7}});
  check(t.valid&&t.missing_units==11&&t.rows.size()==2&&t.rows[0].depot=="south"&&t.rows[0].missing==8);"""),
        hidden_test=_test("""  check(curriculum::compute_shortfalls({},{}).valid);
  check(!curriculum::compute_shortfalls({{"d","i",1},{"d","i",2}},{}).valid);
  check(!curriculum::compute_shortfalls({{"d","i",1}},{{"x","i",0,0}}).valid);
  const auto full=curriculum::compute_shortfalls({{"d","i",2}},{{"d","i",0,2}});check(full.valid&&full.rows.empty());"""),
        negative_old="int observed=latest.count(entry.first)?latest[entry.first].second:0;",
        negative_new="int observed=latest.count(entry.first)?latest[entry.first].second:entry.second;",
        negative_reason="treats an absent stock check as fully stocked",
    ),
    PivotCase(
        legacy_id="pivot-energy-bills",
        task_id="tiered-billing-pivot",
        title="Tiered billing pivot",
        objective="Pivot cumulative meter reads into period consumption and apply account-specific tier prices.",
        public_api="BillingTable bill_periods(const std::vector<std::string>& periods, const std::vector<Tariff>& tariffs, const std::vector<MeterRead>& reads)",
        profile="monotone cumulative-read differencing followed by two-tier cost projection",
        marker="cumulative_reads",
        instructions="""Implement `bill_periods`. Periods are unique ordered labels. Each account has one nonnegative threshold, low price, and high price. Reads are unique account/period cumulative kWh values. Every account needs every period, values must be nondecreasing, and reads must match a tariff. Consumption is the first cumulative value then adjacent differences; cost uses the low price through threshold and high price above it. Emit accounts lexicographically.""",
        header=_header("""#include <string>
struct Tariff { std::string account; int threshold; int low_cents; int high_cents; };
struct MeterRead { std::string account; std::string period; int cumulative_kwh; };
struct BillRow { std::string account; std::vector<int> consumption; std::vector<int> cents; };
struct BillingTable { bool valid=false; std::vector<BillRow> rows; };
BillingTable bill_periods(const std::vector<std::string>& periods,const std::vector<Tariff>& tariffs,const std::vector<MeterRead>& reads);"""),
        reference=_source("""BillingTable bill_periods(const std::vector<std::string>& periods,const std::vector<Tariff>& tariffs,const std::vector<MeterRead>& reads){
  BillingTable out;std::map<std::string,int> period_index;for(int i=0;i<static_cast<int>(periods.size());++i)if(periods[static_cast<std::size_t>(i)].empty()||!period_index.emplace(periods[static_cast<std::size_t>(i)],i).second)return out;if(periods.empty())return out;
  std::map<std::string,Tariff> rules;for(const auto&t:tariffs)if(t.account.empty()||t.threshold<0||t.low_cents<0||t.high_cents<0||!rules.emplace(t.account,t).second)return out;
  std::map<std::string,std::vector<int>> cumulative_reads;for(const auto&r:reads){auto p=period_index.find(r.period);if(r.cumulative_kwh<0||p==period_index.end()||rules.count(r.account)==0)return out;auto& row=cumulative_reads[r.account];if(row.empty())row.assign(periods.size(),-1);if(row[static_cast<std::size_t>(p->second)]!=-1)return out;row[static_cast<std::size_t>(p->second)]=r.cumulative_kwh;}
  for(const auto& rule:rules){auto it=cumulative_reads.find(rule.first);if(it==cumulative_reads.end())return out;BillRow row;row.account=rule.first;int prior=0;for(int value:it->second){if(value<prior)return out;int use=value-prior;prior=value;row.consumption.push_back(use);int low=std::min(use,rule.second.threshold);row.cents.push_back(low*rule.second.low_cents+(use-low)*rule.second.high_cents);}out.rows.push_back(row);}out.valid=true;return out;
}""", "#include <algorithm>\n#include <map>"),
        visible_test=_test("""  const auto b=curriculum::bill_periods({"jan","feb"},{{"a",5,2,4}},{{"a","feb",12},{"a","jan",7}});
  check(b.valid&&b.rows[0].consumption==std::vector<int>({7,5})&&b.rows[0].cents==std::vector<int>({18,10}));"""),
        hidden_test=_test("""  check(!curriculum::bill_periods({}, {}, {}).valid);
  check(!curriculum::bill_periods({"p"},{{"a",1,1,2}},{}).valid);
  check(!curriculum::bill_periods({"p","q"},{{"a",1,1,2}},{{"a","p",3},{"a","q",2}}).valid);
  check(curriculum::bill_periods({"p"},{},{}).valid);"""),
        negative_old="int prior=0;",
        negative_new="int prior=it->second.front();",
        negative_reason="drops first-period consumption",
    ),
    PivotCase(
        legacy_id="pivot-factory-defects",
        task_id="defect-pareto-matrix",
        title="Defect Pareto matrix",
        objective="Cross-tabulate defect counts and compute a stable Pareto ordering with cumulative shares.",
        public_api="ParetoMatrix rank_defects(const std::vector<DefectEvent>& events)",
        profile="line/type additive cross-tabulation plus descending marginal Pareto scan",
        marker="counts_by_line_type",
        instructions="""Implement `rank_defects`. Events require nonempty line/type names and positive counts. Sum duplicate cells. Emit line and type labels lexicographically with their matrix, then rank types by total descending and name ascending. `cumulative_per_mille` is the rounded-down cumulative type count times 1000 divided by the grand total. Empty input is valid.""",
        header=_header("""#include <string>
struct DefectEvent { std::string line; std::string type; int count; };
struct ParetoType { std::string type; int count; int cumulative_per_mille; };
struct ParetoMatrix { bool valid=false; std::vector<std::string> lines; std::vector<std::string> types; std::vector<std::vector<int>> cells; std::vector<ParetoType> pareto; };
ParetoMatrix rank_defects(const std::vector<DefectEvent>& events);"""),
        reference=_source("""ParetoMatrix rank_defects(const std::vector<DefectEvent>& events){
  ParetoMatrix out;std::set<std::string> lines,types;std::map<std::pair<std::string,std::string>,int> counts_by_line_type;std::map<std::string,int> totals;int grand=0;
  for(const auto&e:events){if(e.line.empty()||e.type.empty()||e.count<=0)return out;lines.insert(e.line);types.insert(e.type);counts_by_line_type[{e.line,e.type}]+=e.count;totals[e.type]+=e.count;grand+=e.count;}
  out.lines.assign(lines.begin(),lines.end());out.types.assign(types.begin(),types.end());for(const auto& line:out.lines){std::vector<int> row;for(const auto& type:out.types)row.push_back(counts_by_line_type[{line,type}]);out.cells.push_back(row);}for(const auto& entry:totals)out.pareto.push_back({entry.first,entry.second,0});std::sort(out.pareto.begin(),out.pareto.end(),[](const auto&a,const auto&b){return a.count!=b.count?a.count>b.count:a.type<b.type;});int cumulative=0;for(auto& item:out.pareto){cumulative+=item.count;item.cumulative_per_mille=cumulative*1000/grand;}out.valid=true;return out;
}""", "#include <algorithm>\n#include <map>\n#include <set>\n#include <utility>"),
        visible_test=_test("""  const auto p=curriculum::rank_defects({{"l2","scratch",2},{"l1","dent",3},{"l1","scratch",2}});
  check(p.valid&&p.pareto.size()==2&&p.pareto[0].type=="scratch"&&p.pareto[0].count==4&&p.pareto[0].cumulative_per_mille==571);"""),
        hidden_test=_test("""  check(curriculum::rank_defects({}).valid);
  check(!curriculum::rank_defects({{"","x",1}}).valid);
  check(!curriculum::rank_defects({{"l","x",0}}).valid);
  const auto tie=curriculum::rank_defects({{"l","b",1},{"l","a",1}});check(tie.pareto[0].type=="a"&&tie.pareto.back().cumulative_per_mille==1000);"""),
        negative_old="a.count>b.count",
        negative_new="a.count<b.count",
        negative_reason="orders the Pareto table by smallest defect total",
    ),
    PivotCase(
        legacy_id="pivot-farm-harvests",
        task_id="seasonal-yield-delta",
        title="Seasonal yield delta table",
        objective="Align field-season harvest totals, compute signed adjacent-season deltas, and report the largest decline.",
        public_api="YieldDeltaTable yield_deltas(const std::vector<std::string>& seasons, const std::vector<HarvestLot>& lots)",
        profile="additive field/season pivot followed by adjacent-column differencing",
        marker="yield_by_field",
        instructions="""Implement `yield_deltas`. Seasons are nonempty unique ordered labels. Lots require a nonempty field, known season, and nonnegative kilograms; duplicates sum. Emit fields lexicographically. Totals preserve season order and deltas contain `totals[i]-totals[i-1]`; missing cells count as zero. `largest_drop` is the most negative delta, or zero when no decline exists. Empty lots are valid.""",
        header=_header("""#include <string>
struct HarvestLot { std::string field; std::string season; int kilograms; };
struct YieldDeltaRow { std::string field; std::vector<int> totals; std::vector<int> deltas; int largest_drop=0; };
struct YieldDeltaTable { bool valid=false; std::vector<YieldDeltaRow> rows; };
YieldDeltaTable yield_deltas(const std::vector<std::string>& seasons,const std::vector<HarvestLot>& lots);"""),
        reference=_source("""YieldDeltaTable yield_deltas(const std::vector<std::string>& seasons,const std::vector<HarvestLot>& lots){
  YieldDeltaTable out;std::map<std::string,int> index;for(int i=0;i<static_cast<int>(seasons.size());++i)if(seasons[static_cast<std::size_t>(i)].empty()||!index.emplace(seasons[static_cast<std::size_t>(i)],i).second)return out;if(seasons.empty())return out;std::map<std::string,std::vector<int>> yield_by_field;
  for(const auto& lot:lots){auto it=index.find(lot.season);if(lot.field.empty()||lot.kilograms<0||it==index.end())return out;auto& totals=yield_by_field[lot.field];if(totals.empty())totals.resize(seasons.size());totals[static_cast<std::size_t>(it->second)]+=lot.kilograms;}
  for(const auto& entry:yield_by_field){YieldDeltaRow row;row.field=entry.first;row.totals=entry.second;for(std::size_t i=1;i<row.totals.size();++i){int delta=row.totals[i]-row.totals[i-1];row.deltas.push_back(delta);row.largest_drop=std::min(row.largest_drop,delta);}out.rows.push_back(row);}out.valid=true;return out;
}""", "#include <algorithm>\n#include <map>"),
        visible_test=_test("""  const auto t=curriculum::yield_deltas({"spring","fall"},{{"east","fall",8},{"east","spring",3},{"east","spring",2}});
  check(t.valid&&t.rows[0].totals==std::vector<int>({5,8})&&t.rows[0].deltas==std::vector<int>({3})&&t.rows[0].largest_drop==0);"""),
        hidden_test=_test("""  check(curriculum::yield_deltas({"s"},{}).valid);
  check(!curriculum::yield_deltas({},{}).valid);
  check(!curriculum::yield_deltas({"s","s"},{}).valid);
  const auto m=curriculum::yield_deltas({"a","b"},{{"f","a",4}});check(m.rows[0].deltas[0]==-4&&m.rows[0].largest_drop==-4);"""),
        negative_old="row.totals[i]-row.totals[i-1]",
        negative_new="row.totals[i-1]-row.totals[i]",
        negative_reason="reverses every seasonal delta",
    ),
    PivotCase(
        legacy_id="pivot-flight-delays",
        task_id="airport-delay-percentiles",
        title="Airport delay percentiles",
        objective="Bucket delay samples by airport/hour and select a nearest-rank percentile per cell.",
        public_api="DelayPercentileTable delay_percentiles(const std::vector<int>& hours, const std::vector<DelaySample>& samples, int percentile)",
        profile="cell-wise sample collection plus nearest-rank order statistic",
        marker="samples_by_cell",
        instructions="""Implement `delay_percentiles`. Hours are unique integers 0..23 in output order. Percentile is 1..100. Samples require nonempty airport, known hour, and nonnegative minutes. Collect duplicate cell samples. For each present cell sort samples and select index `ceil(percentile*n/100)-1`; missing cells are `-1`. Emit airports lexicographically.""",
        header=_header("""#include <string>
struct DelaySample { std::string airport; int hour; int minutes; };
struct DelayPercentileRow { std::string airport; std::vector<int> minutes; };
struct DelayPercentileTable { bool valid=false; std::vector<DelayPercentileRow> rows; };
DelayPercentileTable delay_percentiles(const std::vector<int>& hours,const std::vector<DelaySample>& samples,int percentile);"""),
        reference=_source("""DelayPercentileTable delay_percentiles(const std::vector<int>& hours,const std::vector<DelaySample>& samples,int percentile){
  DelayPercentileTable out;if(percentile<1||percentile>100||hours.empty())return out;std::map<int,int> index;for(int i=0;i<static_cast<int>(hours.size());++i)if(hours[static_cast<std::size_t>(i)]<0||hours[static_cast<std::size_t>(i)]>23||!index.emplace(hours[static_cast<std::size_t>(i)],i).second)return out;
  std::map<std::string,std::vector<std::vector<int>>> samples_by_cell;for(const auto&s:samples){auto it=index.find(s.hour);if(s.airport.empty()||s.minutes<0||it==index.end())return out;auto& cells=samples_by_cell[s.airport];if(cells.empty())cells.resize(hours.size());cells[static_cast<std::size_t>(it->second)].push_back(s.minutes);}
  for(auto& entry:samples_by_cell){DelayPercentileRow row;row.airport=entry.first;for(auto& cell:entry.second){if(cell.empty()){row.minutes.push_back(-1);continue;}std::sort(cell.begin(),cell.end());std::size_t rank=(static_cast<std::size_t>(percentile)*cell.size()+99U)/100U;row.minutes.push_back(cell[rank-1]);}out.rows.push_back(row);}out.valid=true;return out;
}""", "#include <algorithm>\n#include <map>"),
        visible_test=_test("""  const auto t=curriculum::delay_percentiles({8,9},{{"A",8,30},{"A",8,10},{"A",8,20},{"B",9,5}},50);
  check(t.valid&&t.rows[0].minutes==std::vector<int>({20,-1})&&t.rows[1].minutes==std::vector<int>({-1,5}));"""),
        hidden_test=_test("""  check(!curriculum::delay_percentiles({}, {},50).valid);
  check(!curriculum::delay_percentiles({24},{},50).valid);
  check(!curriculum::delay_percentiles({1},{{"a",2,3}},50).valid);
  const auto hi=curriculum::delay_percentiles({1},{{"a",1,1},{"a",1,9}},100);check(hi.rows[0].minutes[0]==9);"""),
        negative_old="cell[rank-1]",
        negative_new="cell[rank-rank]",
        negative_reason="returns the minimum instead of the requested percentile",
    ),
    PivotCase(
        legacy_id="pivot-hotel-bookings",
        task_id="room-occupancy-interval-grid",
        title="Room occupancy interval grid",
        objective="Expand half-open stays into a room-by-date occupancy grid while detecting overlap.",
        public_api="OccupancyGrid expand_stays(const std::vector<std::string>& dates, const std::vector<Stay>& stays)",
        profile="half-open interval expansion over an ordered date axis with collision detection",
        marker="occupied_dates",
        instructions="""Implement `expand_stays`. Dates are nonempty unique labels in chronological order. Each stay has a nonempty room, nonnegative guests, known check-in/check-out dates, and check-in strictly before check-out. Mark guests on `[check_in, check_out)`. Overlapping stays in one room are invalid. Emit rooms lexicographically; unoccupied cells are zero.""",
        header=_header("""#include <string>
struct Stay { std::string room; std::string check_in; std::string check_out; int guests; };
struct RoomOccupancy { std::string room; std::vector<int> guests; };
struct OccupancyGrid { bool valid=false; std::vector<RoomOccupancy> rows; };
OccupancyGrid expand_stays(const std::vector<std::string>& dates,const std::vector<Stay>& stays);"""),
        reference=_source("""OccupancyGrid expand_stays(const std::vector<std::string>& dates,const std::vector<Stay>& stays){
  OccupancyGrid out;std::map<std::string,int> index;for(int i=0;i<static_cast<int>(dates.size());++i)if(dates[static_cast<std::size_t>(i)].empty()||!index.emplace(dates[static_cast<std::size_t>(i)],i).second)return out;if(dates.empty())return out;std::map<std::string,std::vector<int>> occupied_dates;
  for(const auto&s:stays){auto first=index.find(s.check_in),last=index.find(s.check_out);if(s.room.empty()||s.guests<0||first==index.end()||last==index.end()||first->second>=last->second)return out;auto& row=occupied_dates[s.room];if(row.empty())row.resize(dates.size());for(int i=first->second;i<last->second;++i){if(row[static_cast<std::size_t>(i)]!=0)return out;row[static_cast<std::size_t>(i)]=s.guests;}}
  for(const auto& entry:occupied_dates)out.rows.push_back({entry.first,entry.second});out.valid=true;return out;
}""", "#include <map>"),
        visible_test=_test("""  const auto g=curriculum::expand_stays({"d1","d2","d3"},{{"101","d1","d3",2},{"102","d2","d3",1}});
  check(g.valid&&g.rows[0].guests==std::vector<int>({2,2,0})&&g.rows[1].guests==std::vector<int>({0,1,0}));"""),
        hidden_test=_test("""  check(curriculum::expand_stays({"a"},{}).valid);
  check(!curriculum::expand_stays({},{}).valid);
  check(!curriculum::expand_stays({"a","b"},{{"r","a","a",1}}).valid);
  check(!curriculum::expand_stays({"a","b","c"},{{"r","a","c",1},{"r","b","c",1}}).valid);"""),
        negative_old="i<last->second",
        negative_new="i<=last->second",
        negative_reason="treats a half-open checkout date as occupied",
    ),
    PivotCase(
        legacy_id="pivot-lab-results",
        task_id="assay-weighted-mean-table",
        title="Assay weighted-mean table",
        objective="Aggregate replicate assay values by inverse precision weight and retain explicit missing cells.",
        public_api="AssayTable weighted_assays(const std::vector<std::string>& analytes, const std::vector<Assay>& assays)",
        profile="per-cell weighted numerator/denominator reduction with rounded quotient",
        marker="weighted_cells",
        instructions="""Implement `weighted_assays`. Analytes are unique nonempty ordered labels. Assays require a nonempty sample, known analyte, nonnegative value, and positive weight. Duplicate cells combine. Round the weighted mean to nearest integer using `(numerator + weight/2)/weight`. Missing cells are `-1`; emit samples lexicographically.""",
        header=_header("""#include <string>
struct Assay { std::string sample; std::string analyte; int value; int weight; };
struct AssayRow { std::string sample; std::vector<int> means; };
struct AssayTable { bool valid=false; std::vector<AssayRow> rows; };
AssayTable weighted_assays(const std::vector<std::string>& analytes,const std::vector<Assay>& assays);"""),
        reference=_source("""AssayTable weighted_assays(const std::vector<std::string>& analytes,const std::vector<Assay>& assays){
  AssayTable out;std::map<std::string,int> index;for(int i=0;i<static_cast<int>(analytes.size());++i)if(analytes[static_cast<std::size_t>(i)].empty()||!index.emplace(analytes[static_cast<std::size_t>(i)],i).second)return out;if(analytes.empty())return out;using Pair=std::pair<long long,long long>;std::map<std::string,std::vector<Pair>> weighted_cells;
  for(const auto&a:assays){auto it=index.find(a.analyte);if(a.sample.empty()||a.value<0||a.weight<=0||it==index.end())return out;auto& cells=weighted_cells[a.sample];if(cells.empty())cells.resize(analytes.size());auto& cell=cells[static_cast<std::size_t>(it->second)];cell.first+=static_cast<long long>(a.value)*a.weight;cell.second+=a.weight;}
  for(const auto& entry:weighted_cells){AssayRow row;row.sample=entry.first;for(const auto& cell:entry.second)row.means.push_back(cell.second==0?-1:static_cast<int>((cell.first+cell.second/2)/cell.second));out.rows.push_back(row);}out.valid=true;return out;
}""", "#include <map>\n#include <utility>"),
        visible_test=_test("""  const auto t=curriculum::weighted_assays({"x","y"},{{"s","x",10,1},{"s","x",20,3}});
  check(t.valid&&t.rows[0].means==std::vector<int>({18,-1}));"""),
        hidden_test=_test("""  check(curriculum::weighted_assays({"x"},{}).valid);
  check(!curriculum::weighted_assays({},{}).valid);
  check(!curriculum::weighted_assays({"x"},{{"s","x",1,0}}).valid);
  check(!curriculum::weighted_assays({"x"},{{"s","y",1,1}}).valid);"""),
        negative_old="cell.first+cell.second/2",
        negative_new="cell.first",
        negative_reason="truncates rather than rounds a weighted mean",
    ),
    PivotCase(
        legacy_id="pivot-library-circulation",
        task_id="branch-category-distinct-table",
        title="Branch-category distinct circulation",
        objective="Count distinct loaned titles per branch/category cell while separately preserving loan totals.",
        public_api="CirculationTable summarize_circulation(const std::vector<Loan>& loans)",
        profile="cell-key set cardinality paired with additive event totals",
        marker="titles_by_cell",
        instructions="""Implement `summarize_circulation`. Loans require nonempty branch, category, and title plus a positive count. Duplicate records add to loan totals, while a title contributes once to distinct-title count in its branch/category cell. Emit branches and categories lexicographically and aligned matrices. Empty input is valid.""",
        header=_header("""#include <string>
struct Loan { std::string branch; std::string category; std::string title; int count; };
struct CirculationTable { bool valid=false; std::vector<std::string> branches; std::vector<std::string> categories; std::vector<std::vector<int>> loans; std::vector<std::vector<int>> distinct_titles; };
CirculationTable summarize_circulation(const std::vector<Loan>& loans);"""),
        reference=_source("""CirculationTable summarize_circulation(const std::vector<Loan>& loans){
  CirculationTable out;using Key=std::pair<std::string,std::string>;std::set<std::string> branches,categories;std::map<Key,int> totals;std::map<Key,std::set<std::string>> titles_by_cell;
  for(const auto& loan:loans){if(loan.branch.empty()||loan.category.empty()||loan.title.empty()||loan.count<=0)return out;Key key{loan.branch,loan.category};branches.insert(loan.branch);categories.insert(loan.category);totals[key]+=loan.count;titles_by_cell[key].insert(loan.title);}
  out.branches.assign(branches.begin(),branches.end());out.categories.assign(categories.begin(),categories.end());for(const auto& b:out.branches){std::vector<int> count_row,title_row;for(const auto& c:out.categories){Key key{b,c};count_row.push_back(totals[key]);title_row.push_back(static_cast<int>(titles_by_cell[key].size()));}out.loans.push_back(count_row);out.distinct_titles.push_back(title_row);}out.valid=true;return out;
}""", "#include <map>\n#include <set>\n#include <utility>"),
        visible_test=_test("""  const auto t=curriculum::summarize_circulation({{"a","fiction","one",2},{"a","fiction","one",1},{"a","fiction","two",1}});
  check(t.valid&&t.loans[0][0]==4&&t.distinct_titles[0][0]==2);"""),
        hidden_test=_test("""  check(curriculum::summarize_circulation({}).valid);
  check(!curriculum::summarize_circulation({{"","c","t",1}}).valid);
  check(!curriculum::summarize_circulation({{"b","c","t",0}}).valid);
  const auto x=curriculum::summarize_circulation({{"z","b","t",1},{"a","a","q",1}});check(x.branches[0]=="a"&&x.categories[0]=="a");"""),
        negative_old="titles_by_cell[key].insert(loan.title);",
        negative_new="titles_by_cell[key].insert(loan.category);",
        negative_reason="counts categories instead of distinct titles",
    ),
    PivotCase(
        legacy_id="pivot-market-sales",
        task_id="vendor-product-leader-table",
        title="Vendor product leader table",
        objective="Build vendor/product revenue cells and select a unique revenue leader for each product.",
        public_api="SalesLeaderTable product_leaders(const std::vector<Sale>& sales)",
        profile="two-dimensional revenue fold plus per-column stable argmax",
        marker="revenue_by_vendor_product",
        instructions="""Implement `product_leaders`. Sales require nonempty vendor/product, positive units, and nonnegative unit cents. Sum revenue with signed-64-bit arithmetic. Emit vendors and products lexicographically and the revenue matrix. For each product choose greatest revenue, breaking ties by lexicographically smaller vendor. Empty input is valid.""",
        header=_header("""#include <string>
struct Sale { std::string vendor; std::string product; int units; int unit_cents; };
struct ProductLeader { std::string product; std::string vendor; long long revenue; };
struct SalesLeaderTable { bool valid=false; std::vector<std::string> vendors; std::vector<std::string> products; std::vector<std::vector<long long>> revenue; std::vector<ProductLeader> leaders; };
SalesLeaderTable product_leaders(const std::vector<Sale>& sales);"""),
        reference=_source("""SalesLeaderTable product_leaders(const std::vector<Sale>& sales){
  SalesLeaderTable out;using Key=std::pair<std::string,std::string>;std::set<std::string> vendors,products;std::map<Key,long long> revenue_by_vendor_product;
  for(const auto&s:sales){if(s.vendor.empty()||s.product.empty()||s.units<=0||s.unit_cents<0)return out;vendors.insert(s.vendor);products.insert(s.product);revenue_by_vendor_product[{s.vendor,s.product}]+=static_cast<long long>(s.units)*s.unit_cents;}
  out.vendors.assign(vendors.begin(),vendors.end());out.products.assign(products.begin(),products.end());for(const auto& v:out.vendors){std::vector<long long> row;for(const auto&p:out.products)row.push_back(revenue_by_vendor_product[{v,p}]);out.revenue.push_back(row);}for(const auto&p:out.products){ProductLeader leader{p,"",0};for(const auto&v:out.vendors){long long value=revenue_by_vendor_product[{v,p}];if(leader.vendor.empty()||value>leader.revenue){leader.vendor=v;leader.revenue=value;}}out.leaders.push_back(leader);}out.valid=true;return out;
}""", "#include <map>\n#include <set>\n#include <utility>"),
        visible_test=_test("""  const auto t=curriculum::product_leaders({{"b","tea",2,100},{"a","tea",1,250},{"b","cake",1,80}});
  check(t.valid&&t.leaders[0].product=="cake"&&t.leaders[0].vendor=="b"&&t.leaders[1].vendor=="a");"""),
        hidden_test=_test("""  check(curriculum::product_leaders({}).valid);
  check(!curriculum::product_leaders({{"v","p",0,1}}).valid);
  const auto tie=curriculum::product_leaders({{"b","p",1,2},{"a","p",1,2}});check(tie.leaders[0].vendor=="a");
  const auto sum=curriculum::product_leaders({{"v","p",2,3},{"v","p",1,4}});check(sum.leaders[0].revenue==10);"""),
        negative_old="value>leader.revenue",
        negative_new="value>=leader.revenue",
        negative_reason="breaks the lexicographically earliest vendor tie rule",
    ),
    PivotCase(
        legacy_id="pivot-museum-tickets",
        task_id="exhibit-running-attendance",
        title="Exhibit running attendance",
        objective="Pivot daily ticket deltas and derive a cumulative attendance curve for each exhibit.",
        public_api="AttendanceTable running_attendance(const std::vector<std::string>& days, const std::vector<TicketDelta>& deltas)",
        profile="signed daily delta cross-tabulation plus row-wise prefix accumulation",
        marker="daily_deltas",
        instructions="""Implement `running_attendance`. Days are unique nonempty labels in order. Deltas require nonempty exhibits, known days, and may be positive or negative. Duplicate cells sum. The running count starts at zero and must never become negative; otherwise return invalid. Emit exhibits lexicographically with daily deltas and cumulative counts. Empty deltas are valid.""",
        header=_header("""#include <string>
struct TicketDelta { std::string exhibit; std::string day; int change; };
struct AttendanceRow { std::string exhibit; std::vector<int> deltas; std::vector<int> running; };
struct AttendanceTable { bool valid=false; std::vector<AttendanceRow> rows; };
AttendanceTable running_attendance(const std::vector<std::string>& days,const std::vector<TicketDelta>& deltas);"""),
        reference=_source("""AttendanceTable running_attendance(const std::vector<std::string>& days,const std::vector<TicketDelta>& deltas){
  AttendanceTable out;std::map<std::string,int> index;for(int i=0;i<static_cast<int>(days.size());++i)if(days[static_cast<std::size_t>(i)].empty()||!index.emplace(days[static_cast<std::size_t>(i)],i).second)return out;if(days.empty())return out;std::map<std::string,std::vector<int>> daily_deltas;
  for(const auto& d:deltas){auto it=index.find(d.day);if(d.exhibit.empty()||it==index.end())return out;auto& row=daily_deltas[d.exhibit];if(row.empty())row.resize(days.size());row[static_cast<std::size_t>(it->second)]+=d.change;}
  for(const auto& entry:daily_deltas){AttendanceRow row;row.exhibit=entry.first;row.deltas=entry.second;int total=0;for(int change:row.deltas){total+=change;if(total<0)return AttendanceTable{};row.running.push_back(total);}out.rows.push_back(row);}out.valid=true;return out;
}""", "#include <map>"),
        visible_test=_test("""  const auto t=curriculum::running_attendance({"d1","d2","d3"},{{"art","d1",5},{"art","d2",-2},{"art","d2",1}});
  check(t.valid&&t.rows[0].deltas==std::vector<int>({5,-1,0})&&t.rows[0].running==std::vector<int>({5,4,4}));"""),
        hidden_test=_test("""  check(curriculum::running_attendance({"d"},{}).valid);
  check(!curriculum::running_attendance({},{}).valid);
  check(!curriculum::running_attendance({"d"},{{"x","q",1}}).valid);
  check(!curriculum::running_attendance({"a","b"},{{"x","a",1},{"x","b",-2}}).valid);"""),
        negative_old="total+=change;",
        negative_new="total=change;",
        negative_reason="fails to accumulate attendance across days",
    ),
    PivotCase(
        legacy_id="pivot-orchard-inspections",
        task_id="orchard-score-band-table",
        title="Orchard score-band table",
        objective="Assign inspection scores to configured bands and cross-tabulate band counts per block.",
        public_api="ScoreBandTable band_inspections(const std::vector<int>& upper_bounds, const std::vector<Inspection>& inspections)",
        profile="ordered threshold classification plus block/band histogram",
        marker="band_counts",
        instructions="""Implement `band_inspections`. Upper bounds are nonnegative and strictly increasing. Inspections require nonempty blocks and nonnegative scores no greater than the final bound. Assign each score to the first bound greater than or equal to it. Emit blocks lexicographically, preserve band order, count duplicates, and report each block's highest occupied band. Empty inspections are valid.""",
        header=_header("""#include <string>
struct Inspection { std::string block; int score; };
struct BlockBands { std::string block; std::vector<int> counts; int highest=-1; };
struct ScoreBandTable { bool valid=false; std::vector<BlockBands> rows; };
ScoreBandTable band_inspections(const std::vector<int>& upper_bounds,const std::vector<Inspection>& inspections);"""),
        reference=_source("""ScoreBandTable band_inspections(const std::vector<int>& upper_bounds,const std::vector<Inspection>& inspections){
  ScoreBandTable out;if(upper_bounds.empty())return out;for(std::size_t i=0;i<upper_bounds.size();++i)if(upper_bounds[i]<0||(i>0&&upper_bounds[i]<=upper_bounds[i-1]))return out;std::map<std::string,std::vector<int>> band_counts;
  for(const auto& x:inspections){if(x.block.empty()||x.score<0||x.score>upper_bounds.back())return out;auto it=std::lower_bound(upper_bounds.begin(),upper_bounds.end(),x.score);auto& counts=band_counts[x.block];if(counts.empty())counts.resize(upper_bounds.size());++counts[static_cast<std::size_t>(it-upper_bounds.begin())];}
  for(const auto& entry:band_counts){BlockBands row;row.block=entry.first;row.counts=entry.second;for(int i=0;i<static_cast<int>(row.counts.size());++i)if(row.counts[static_cast<std::size_t>(i)]>0)row.highest=i;out.rows.push_back(row);}out.valid=true;return out;
}""", "#include <algorithm>\n#include <map>"),
        visible_test=_test("""  const auto t=curriculum::band_inspections({2,5,9},{{"b",0},{"b",5},{"b",6}});
  check(t.valid&&t.rows[0].counts==std::vector<int>({1,1,1})&&t.rows[0].highest==2);"""),
        hidden_test=_test("""  check(curriculum::band_inspections({1},{}).valid);
  check(!curriculum::band_inspections({},{}).valid);
  check(!curriculum::band_inspections({2,2},{}).valid);
  check(!curriculum::band_inspections({2},{{"b",3}}).valid);
  const auto edge=curriculum::band_inspections({2,4},{{"b",2}});check(edge.rows[0].counts[0]==1);"""),
        negative_old="std::lower_bound",
        negative_new="std::upper_bound",
        negative_reason="places scores equal to a boundary in the next band",
    ),
    PivotCase(
        legacy_id="pivot-research-cohorts",
        task_id="cohort-visit-retention",
        title="Cohort visit retention",
        objective="Pivot participant attendance and compute retention against each cohort's baseline visit.",
        public_api="RetentionTable cohort_retention(const std::vector<std::string>& visits, const std::vector<Enrollment>& enrollments, const std::vector<Attendance>& attendance)",
        profile="cohort membership join, unique attendance bitmap, and baseline-normalized column ratios",
        marker="attendance_by_participant",
        instructions="""Implement `cohort_retention`. Visits are unique nonempty ordered labels. Enrollment has unique nonempty participants and cohorts. Attendance participant/visit pairs must be unique and reference enrolled participants and known visits. Count attendees per cohort/visit; retention per mille is count*1000 divided by the cohort's first-visit count. A cohort with zero baseline has `-1` for every retention value. Emit cohorts lexicographically.""",
        header=_header("""#include <string>
struct Enrollment { std::string participant; std::string cohort; };
struct Attendance { std::string participant; std::string visit; };
struct RetentionRow { std::string cohort; std::vector<int> attendees; std::vector<int> per_mille; };
struct RetentionTable { bool valid=false; std::vector<RetentionRow> rows; };
RetentionTable cohort_retention(const std::vector<std::string>& visits,const std::vector<Enrollment>& enrollments,const std::vector<Attendance>& attendance);"""),
        reference=_source("""RetentionTable cohort_retention(const std::vector<std::string>& visits,const std::vector<Enrollment>& enrollments,const std::vector<Attendance>& attendance){
  RetentionTable out;std::map<std::string,int> visit_index;for(int i=0;i<static_cast<int>(visits.size());++i)if(visits[static_cast<std::size_t>(i)].empty()||!visit_index.emplace(visits[static_cast<std::size_t>(i)],i).second)return out;if(visits.empty())return out;std::map<std::string,std::string> cohort_by_person;std::set<std::string> cohorts;for(const auto&e:enrollments)if(e.participant.empty()||e.cohort.empty()||!cohort_by_person.emplace(e.participant,e.cohort).second)return out;else cohorts.insert(e.cohort);
  std::set<std::pair<std::string,std::string>> seen;std::map<std::string,std::vector<int>> attendance_by_participant;for(const auto&a:attendance){auto p=cohort_by_person.find(a.participant);auto v=visit_index.find(a.visit);if(p==cohort_by_person.end()||v==visit_index.end()||!seen.insert({a.participant,a.visit}).second)return out;auto& counts=attendance_by_participant[p->second];if(counts.empty())counts.resize(visits.size());++counts[static_cast<std::size_t>(v->second)];}
  for(const auto& c:cohorts){RetentionRow row;row.cohort=c;row.attendees=attendance_by_participant[c];if(row.attendees.empty())row.attendees.resize(visits.size());int baseline=row.attendees[0];for(int count:row.attendees)row.per_mille.push_back(baseline==0?-1:count*1000/baseline);out.rows.push_back(row);}out.valid=true;return out;
}""", "#include <map>\n#include <set>\n#include <utility>"),
        visible_test=_test("""  const auto t=curriculum::cohort_retention({"v1","v2"},{{"a","c"},{"b","c"}},{{"a","v1"},{"b","v1"},{"a","v2"}});
  check(t.valid&&t.rows[0].attendees==std::vector<int>({2,1})&&t.rows[0].per_mille==std::vector<int>({1000,500}));"""),
        hidden_test=_test("""  check(curriculum::cohort_retention({"v"},{},{}).valid);
  check(!curriculum::cohort_retention({}, {}, {}).valid);
  check(!curriculum::cohort_retention({"v"},{{"a","c"},{"a","d"}},{}).valid);
  const auto zero=curriculum::cohort_retention({"v"},{{"a","c"}},{});check(zero.rows[0].per_mille[0]==-1);
  check(!curriculum::cohort_retention({"v"},{{"a","c"}},{{"a","v"},{"a","v"}}).valid);"""),
        negative_old="int baseline=row.attendees[0];",
        negative_new="int baseline=static_cast<int>(cohort_by_person.size());",
        negative_reason="normalizes by all enrollments instead of the cohort baseline",
    ),
    PivotCase(
        legacy_id="pivot-river-quality",
        task_id="river-unit-normalized-table",
        title="River unit-normalized table",
        objective="Normalize mixed-unit measurements before pivoting site/month minimum-to-maximum ranges.",
        public_api="QualityTable normalize_quality(const std::vector<std::string>& months, const std::vector<QualitySample>& samples)",
        profile="unit conversion to milli-units plus per-cell extremum range reduction",
        marker="normalized_cells",
        instructions="""Implement `normalize_quality`. Months are unique nonempty ordered labels. Samples require nonempty sites, known months, nonnegative values, and unit `milli` or `base`; base values convert by multiplying by 1000. Reject converted values beyond signed int range. For each present cell return its minimum, maximum, and spread; missing minima/maxima/spreads are `-1`. Emit sites lexicographically.""",
        header=_header("""#include <string>
struct QualitySample { std::string site; std::string month; int value; std::string unit; };
struct QualityRow { std::string site; std::vector<int> minimum; std::vector<int> maximum; std::vector<int> spread; };
struct QualityTable { bool valid=false; std::vector<QualityRow> rows; };
QualityTable normalize_quality(const std::vector<std::string>& months,const std::vector<QualitySample>& samples);"""),
        reference=_source("""QualityTable normalize_quality(const std::vector<std::string>& months,const std::vector<QualitySample>& samples){
  QualityTable out;std::map<std::string,int> index;for(int i=0;i<static_cast<int>(months.size());++i)if(months[static_cast<std::size_t>(i)].empty()||!index.emplace(months[static_cast<std::size_t>(i)],i).second)return out;if(months.empty())return out;struct Cell{int low=-1;int high=-1;};std::map<std::string,std::vector<Cell>> normalized_cells;
  for(const auto&s:samples){auto it=index.find(s.month);if(s.site.empty()||s.value<0||it==index.end()||(s.unit!="milli"&&s.unit!="base"))return out;long long value=s.unit=="base"?static_cast<long long>(s.value)*1000:s.value;if(value>2147483647LL)return out;auto& cells=normalized_cells[s.site];if(cells.empty())cells.resize(months.size());auto& cell=cells[static_cast<std::size_t>(it->second)];int measured=static_cast<int>(value);cell.low=cell.low<0?measured:std::min(cell.low,measured);cell.high=std::max(cell.high,measured);}
  for(const auto& entry:normalized_cells){QualityRow row;row.site=entry.first;for(const auto& cell:entry.second){row.minimum.push_back(cell.low);row.maximum.push_back(cell.high);row.spread.push_back(cell.low<0?-1:cell.high-cell.low);}out.rows.push_back(row);}out.valid=true;return out;
}""", "#include <algorithm>\n#include <map>"),
        visible_test=_test("""  const auto t=curriculum::normalize_quality({"jan","feb"},{{"s","jan",2,"base"},{"s","jan",500,"milli"}});
  check(t.valid&&t.rows[0].minimum==std::vector<int>({500,-1})&&t.rows[0].maximum==std::vector<int>({2000,-1})&&t.rows[0].spread[0]==1500);"""),
        hidden_test=_test("""  check(curriculum::normalize_quality({"m"},{}).valid);
  check(!curriculum::normalize_quality({},{}).valid);
  check(!curriculum::normalize_quality({"m"},{{"s","m",1,"ppm"}}).valid);
  check(!curriculum::normalize_quality({"m"},{{"s","m",3000000,"base"}}).valid);"""),
        negative_old="static_cast<long long>(s.value)*1000",
        negative_new="static_cast<long long>(s.value)*100",
        negative_reason="uses the wrong base-to-milli conversion factor",
    ),
    PivotCase(
        legacy_id="pivot-school-grades",
        task_id="student-letter-grade-table",
        title="Student letter-grade table",
        objective="Resolve assessment attempts and classify final numeric scores into configured letter bands.",
        public_api="GradeTable final_grades(const std::vector<GradeBand>& bands, const std::vector<Assessment>& assessments)",
        profile="latest-attempt arbitration followed by descending threshold classification",
        marker="latest_attempt",
        instructions="""Implement `final_grades`. Bands require nonempty unique letters, thresholds 0..100, strictly descending thresholds, and a final threshold of zero. Assessments require nonempty student/subject, scores 0..100, and nonnegative attempts. Attempt numbers are unique per student/subject; greatest attempt wins. Emit students and subjects lexicographically with numeric scores (`-1` missing) and letter strings (empty missing).""",
        header=_header("""#include <string>
struct GradeBand { int minimum; std::string letter; };
struct Assessment { std::string student; std::string subject; int attempt; int score; };
struct StudentGrades { std::string student; std::vector<int> scores; std::vector<std::string> letters; };
struct GradeTable { bool valid=false; std::vector<std::string> subjects; std::vector<StudentGrades> rows; };
GradeTable final_grades(const std::vector<GradeBand>& bands,const std::vector<Assessment>& assessments);"""),
        reference=_source("""GradeTable final_grades(const std::vector<GradeBand>& bands,const std::vector<Assessment>& assessments){
  GradeTable out;if(bands.empty()||bands.back().minimum!=0)return out;std::set<std::string> letters;for(std::size_t i=0;i<bands.size();++i)if(bands[i].minimum<0||bands[i].minimum>100||bands[i].letter.empty()||!letters.insert(bands[i].letter).second||(i>0&&bands[i].minimum>=bands[i-1].minimum))return out;
  using Key=std::pair<std::string,std::string>;std::map<Key,std::pair<int,int>> latest_attempt;std::set<std::string> students,subjects;for(const auto&a:assessments){if(a.student.empty()||a.subject.empty()||a.attempt<0||a.score<0||a.score>100)return out;Key key{a.student,a.subject};auto it=latest_attempt.find(key);if(it!=latest_attempt.end()&&it->second.first==a.attempt)return out;if(it==latest_attempt.end()||a.attempt>it->second.first)latest_attempt[key]={a.attempt,a.score};students.insert(a.student);subjects.insert(a.subject);}
  out.subjects.assign(subjects.begin(),subjects.end());for(const auto&s:students){StudentGrades row;row.student=s;for(const auto& subject:out.subjects){auto it=latest_attempt.find({s,subject});if(it==latest_attempt.end()){row.scores.push_back(-1);row.letters.push_back("");continue;}row.scores.push_back(it->second.second);std::string letter;for(const auto& band:bands)if(it->second.second>=band.minimum){letter=band.letter;break;}row.letters.push_back(letter);}out.rows.push_back(row);}out.valid=true;return out;
}""", "#include <map>\n#include <set>\n#include <utility>"),
        visible_test=_test("""  const auto t=curriculum::final_grades({{90,"A"},{70,"B"},{0,"F"}},{{"s","math",0,60},{"s","math",1,75},{"s","art",0,95}});
  check(t.valid&&t.subjects==std::vector<std::string>({"art","math"})&&t.rows[0].letters==std::vector<std::string>({"A","B"}));""", "#include <string>"),
        hidden_test=_test("""  check(curriculum::final_grades({{0,"F"}},{}).valid);
  check(!curriculum::final_grades({},{}).valid);
  check(!curriculum::final_grades({{0,"F"},{50,"A"}},{}).valid);
  check(!curriculum::final_grades({{0,"F"}},{{"s","x",0,101}}).valid);
  check(!curriculum::final_grades({{0,"F"}},{{"s","x",0,1},{"s","x",0,2}}).valid);"""),
        negative_old="a.attempt>it->second.first",
        negative_new="a.attempt<it->second.first",
        negative_reason="keeps the oldest rather than latest assessment attempt",
    ),
    PivotCase(
        legacy_id="pivot-solar-output",
        task_id="solar-gap-interpolation-table",
        title="Solar gap interpolation table",
        objective="Pivot panel readings and fill only single-hour interior gaps by linear interpolation.",
        public_api="SolarTable interpolate_single_gaps(const std::vector<int>& hours, const std::vector<PanelRead>& reads)",
        profile="unique sparse pivot plus bounded one-cell linear interpolation",
        marker="panel_readings",
        instructions="""Implement `interpolate_single_gaps`. Hours must be unique and strictly increasing. Reads require nonempty panels, known hours, nonnegative watts, and unique panel/hour cells. Preserve hour order and emit panels lexicographically. Missing cells are `-1`; fill an interior missing cell only when both immediate neighbors are present, using integer floor average. Do not fill edge or multi-cell gaps.""",
        header=_header("""#include <string>
struct PanelRead { std::string panel; int hour; int watts; };
struct SolarRow { std::string panel; std::vector<int> watts; std::vector<bool> interpolated; };
struct SolarTable { bool valid=false; std::vector<SolarRow> rows; };
SolarTable interpolate_single_gaps(const std::vector<int>& hours,const std::vector<PanelRead>& reads);"""),
        reference=_source("""SolarTable interpolate_single_gaps(const std::vector<int>& hours,const std::vector<PanelRead>& reads){
  SolarTable out;if(hours.empty())return out;std::map<int,int> index;for(int i=0;i<static_cast<int>(hours.size());++i)if((i>0&&hours[static_cast<std::size_t>(i)]<=hours[static_cast<std::size_t>(i-1)])||!index.emplace(hours[static_cast<std::size_t>(i)],i).second)return out;std::map<std::string,std::vector<int>> panel_readings;
  for(const auto&r:reads){auto it=index.find(r.hour);if(r.panel.empty()||r.watts<0||it==index.end())return out;auto& row=panel_readings[r.panel];if(row.empty())row.assign(hours.size(),-1);if(row[static_cast<std::size_t>(it->second)]!=-1)return out;row[static_cast<std::size_t>(it->second)]=r.watts;}
  for(const auto& entry:panel_readings){SolarRow row;row.panel=entry.first;row.watts=entry.second;row.interpolated.assign(hours.size(),false);for(std::size_t i=1;i+1<row.watts.size();++i)if(entry.second[i]==-1&&entry.second[i-1]!=-1&&entry.second[i+1]!=-1){row.watts[i]=(entry.second[i-1]+entry.second[i+1])/2;row.interpolated[i]=true;}out.rows.push_back(row);}out.valid=true;return out;
}""", "#include <map>"),
        visible_test=_test("""  const auto t=curriculum::interpolate_single_gaps({8,9,10},{{"p",8,10},{"p",10,20}});
  check(t.valid&&t.rows[0].watts==std::vector<int>({10,15,20})&&t.rows[0].interpolated==std::vector<bool>({false,true,false}));"""),
        hidden_test=_test("""  check(curriculum::interpolate_single_gaps({1},{}).valid);
  check(!curriculum::interpolate_single_gaps({},{}).valid);
  const auto edge=curriculum::interpolate_single_gaps({1,2},{{"p",2,4}});check(edge.rows[0].watts[0]==-1);
  const auto wide=curriculum::interpolate_single_gaps({1,2,3,4},{{"p",1,2},{"p",4,8}});check(wide.rows[0].watts[1]==-1&&wide.rows[0].watts[2]==-1);
  check(!curriculum::interpolate_single_gaps({1},{{"p",1,2},{"p",1,3}}).valid);"""),
        negative_old="entry.second[i-1]+entry.second[i+1]",
        negative_new="entry.second[i-1]+entry.second[i-1]",
        negative_reason="copies the left neighbor instead of interpolating",
    ),
    PivotCase(
        legacy_id="pivot-transit-ridership",
        task_id="route-stop-cross-tab",
        title="Route-stop ridership cross-tab",
        objective="Join ordered route paths with stop counts and distinguish off-route observations from missing cells.",
        public_api="RidershipTable route_stop_table(const std::vector<RoutePath>& paths, const std::vector<StopCount>& counts)",
        profile="route-specific path validation and sparse observation projection onto global stop order",
        marker="path_membership",
        instructions="""Implement `route_stop_table`. Each route path has a unique nonempty route and a nonempty list of unique nonempty stops. Counts require a known route, a stop on that route, nonnegative riders, and a unique route/stop cell. Global stop columns are the lexicographic union. Emit routes lexicographically; a path stop without a count is zero, while an off-route cell is `-1`.""",
        header=_header("""#include <string>
struct RoutePath { std::string route; std::vector<std::string> stops; };
struct StopCount { std::string route; std::string stop; int riders; };
struct RouteRidership { std::string route; std::vector<int> riders; };
struct RidershipTable { bool valid=false; std::vector<std::string> stops; std::vector<RouteRidership> rows; };
RidershipTable route_stop_table(const std::vector<RoutePath>& paths,const std::vector<StopCount>& counts);"""),
        reference=_source("""RidershipTable route_stop_table(const std::vector<RoutePath>& paths,const std::vector<StopCount>& counts){
  RidershipTable out;std::map<std::string,std::set<std::string>> path_membership;std::set<std::string> stops;for(const auto&p:paths){if(p.route.empty()||p.stops.empty()||path_membership.count(p.route))return out;std::set<std::string> local;for(const auto&s:p.stops)if(s.empty()||!local.insert(s).second)return out;else stops.insert(s);path_membership[p.route]=local;}
  std::map<std::pair<std::string,std::string>,int> values;for(const auto&c:counts){auto p=path_membership.find(c.route);if(c.riders<0||p==path_membership.end()||p->second.count(c.stop)==0||!values.emplace(std::make_pair(c.route,c.stop),c.riders).second)return out;}
  out.stops.assign(stops.begin(),stops.end());for(const auto& path:path_membership){RouteRidership row;row.route=path.first;for(const auto&s:out.stops)row.riders.push_back(path.second.count(s)==0?-1:values[{path.first,s}]);out.rows.push_back(row);}out.valid=true;return out;
}""", "#include <map>\n#include <set>\n#include <utility>"),
        visible_test=_test("""  const auto t=curriculum::route_stop_table({{"r1",{"a","b"}},{"r2",{"b","c"}}},{{"r1","a",3},{"r2","c",4}});
  check(t.valid&&t.stops==std::vector<std::string>({"a","b","c"})&&t.rows[0].riders==std::vector<int>({3,0,-1})&&t.rows[1].riders==std::vector<int>({-1,0,4}));""", "#include <string>"),
        hidden_test=_test("""  check(curriculum::route_stop_table({},{}).valid);
  check(!curriculum::route_stop_table({{"r",{}}},{}).valid);
  check(!curriculum::route_stop_table({{"r",{"a","a"}}},{}).valid);
  check(!curriculum::route_stop_table({{"r",{"a"}}},{{"r","b",1}}).valid);
  check(!curriculum::route_stop_table({{"r",{"a"}}},{{"r","a",1},{"r","a",2}}).valid);"""),
        negative_old="path.second.count(s)==0?-1:values",
        negative_new="path.second.count(s)==0?0:values",
        negative_reason="collapses off-route cells into missing observations",
    ),
    PivotCase(
        legacy_id="pivot-warehouse-orders",
        task_id="warehouse-backlog-aging",
        title="Warehouse backlog aging table",
        objective="Replay ordered demand and shipment events into day-end backlog age buckets.",
        public_api="BacklogTable age_backlog(const std::vector<std::string>& days, const std::vector<OrderEvent>& events)",
        profile="FIFO demand-lot ledger replay with day-end age-bucket projection",
        marker="open_lots",
        instructions="""Implement `age_backlog`. Days are unique nonempty ordered labels. Events require a nonempty item, known day, nonnegative sequence, type `demand` or `ship`, and positive units. Sequence is unique within each day and events replay by day then sequence. Demand appends a lot; shipments consume oldest lots and may not exceed backlog. Emit items lexicographically and at each day end report units aged 0 days, 1 day, and 2-or-more days.""",
        header=_header("""#include <string>
struct OrderEvent { std::string item; std::string day; int sequence; std::string type; int units; };
struct BacklogDay { int age0=0; int age1=0; int age2plus=0; };
struct BacklogRow { std::string item; std::vector<BacklogDay> days; };
struct BacklogTable { bool valid=false; std::vector<BacklogRow> rows; };
BacklogTable age_backlog(const std::vector<std::string>& days,const std::vector<OrderEvent>& events);"""),
        reference=_source("""BacklogTable age_backlog(const std::vector<std::string>& days,const std::vector<OrderEvent>& events){
  BacklogTable out;std::map<std::string,int> day_index;for(int i=0;i<static_cast<int>(days.size());++i)if(days[static_cast<std::size_t>(i)].empty()||!day_index.emplace(days[static_cast<std::size_t>(i)],i).second)return out;if(days.empty())return out;std::vector<OrderEvent> ordered=events;std::set<std::pair<int,int>> sequences;std::set<std::string> items;for(const auto&e:ordered){auto d=day_index.find(e.day);if(e.item.empty()||d==day_index.end()||e.sequence<0||e.units<=0||(e.type!="demand"&&e.type!="ship")||!sequences.insert({d->second,e.sequence}).second)return out;items.insert(e.item);}std::sort(ordered.begin(),ordered.end(),[&](const auto&a,const auto&b){int da=day_index[a.day],db=day_index[b.day];return da!=db?da<db:a.sequence<b.sequence;});
  for(const auto& item:items){std::deque<std::pair<int,int>> open_lots;BacklogRow row;row.item=item;std::size_t cursor=0;for(int day=0;day<static_cast<int>(days.size());++day){while(cursor<ordered.size()&&day_index[ordered[cursor].day]==day){const auto&e=ordered[cursor++];if(e.item!=item)continue;if(e.type=="demand")open_lots.push_back({day,e.units});else{int remaining=e.units;while(remaining>0&&!open_lots.empty()){int take=std::min(remaining,open_lots.front().second);remaining-=take;open_lots.front().second-=take;if(open_lots.front().second==0)open_lots.pop_front();}if(remaining>0)return BacklogTable{};}}BacklogDay cell;for(const auto& lot:open_lots){int age=day-lot.first;if(age==0)cell.age0+=lot.second;else if(age==1)cell.age1+=lot.second;else cell.age2plus+=lot.second;}row.days.push_back(cell);}out.rows.push_back(row);}out.valid=true;return out;
}""", "#include <algorithm>\n#include <deque>\n#include <map>\n#include <set>\n#include <utility>"),
        visible_test=_test("""  const auto t=curriculum::age_backlog({"d1","d2","d3"},{{"x","d1",0,"demand",5},{"x","d2",0,"ship",2},{"x","d3",0,"demand",4}});
  check(t.valid&&t.rows[0].days[0].age0==5&&t.rows[0].days[1].age1==3&&t.rows[0].days[2].age2plus==3&&t.rows[0].days[2].age0==4);"""),
        hidden_test=_test("""  check(curriculum::age_backlog({"d"},{}).valid);
  check(!curriculum::age_backlog({},{}).valid);
  check(!curriculum::age_backlog({"d"},{{"x","d",0,"ship",1}}).valid);
  check(!curriculum::age_backlog({"d"},{{"x","d",0,"demand",1},{"y","d",0,"demand",1}}).valid);
  const auto fifo=curriculum::age_backlog({"a","b"},{{"x","a",0,"demand",2},{"x","b",0,"demand",3},{"x","b",1,"ship",2}});check(fifo.valid&&fifo.rows[0].days[1].age0==3&&fifo.rows[0].days[1].age1==0);"""),
        negative_old="open_lots.front()",
        negative_new="open_lots.back()",
        negative_reason="ships newest demand instead of FIFO oldest demand",
    ),
)
