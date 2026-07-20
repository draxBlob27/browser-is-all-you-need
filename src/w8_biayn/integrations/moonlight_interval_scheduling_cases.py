"""C++ contracts and fixtures for the interval-scheduling v2 materializer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskSpec:
    legacy_id: str
    task_id: str
    class_name: str
    mode: str
    title: str
    contract: str
    rules: str
    boundary_example: str
    api: str
    marker: str
    negative_fixture: str


TASKS = (
    TaskSpec(
        "interval-operating-rooms",
        "surgery-value-plan-v2",
        "SurgeryValuePlan",
        "weighted_interval_dp",
        "Surgery value plan",
        "Choose a maximum-value compatible surgery plan with per-surgery cleanup.",
        "Surgeries are half-open, IDs are unique and positive, and compatibility uses prior end plus cleanup.",
        "For jobs (1,0,3,5,1), (2,3,5,9,0), and (3,4,6,8,0), the optimal IDs are 1 and 3.",
        "Surgery; Plan; choose(vector<Surgery>)",
        "std::upper_bound",
        "earliest-finish-only greedy",
    ),
    TaskSpec(
        "interval-delivery-windows",
        "delivery-route-cover-v2",
        "DeliveryRouteCover",
        "greedy_target_cover",
        "Delivery route cover",
        "Cover a target route segment with the fewest delivery windows.",
        "At each covered coordinate choose the eligible window reaching farthest, breaking equal reach by lower ID.",
        "Windows [0,4), [2,7), [4,9) cover [0,9) with IDs 1 and 3 only when their reaches dictate it.",
        "Window; Cover; cover(left,right,vector<Window>)",
        "best_right",
        "shortest-first window choice",
    ),
    TaskSpec(
        "interval-broadcast-lineup",
        "broadcast-break-stab-v2",
        "BroadcastBreakStab",
        "minimum_stabbing",
        "Broadcast break stabbing",
        "Place the minimum break instants that hit every closed program interval.",
        "Closed intervals may be zero length; choose right endpoints in ascending end order.",
        "Programs [1,3], [2,5], [5,7] need break instants 3 and 7.",
        "Program; BreakPlan; place(vector<Program>)",
        "last_point",
        "midpoint placement",
    ),
    TaskSpec(
        "interval-machine-maintenance",
        "maintenance-throughput-order-v2",
        "MaintenanceThroughputOrder",
        "moore_hodgson",
        "Maintenance throughput order",
        "Keep the largest number of jobs that meet their deadlines.",
        "Scan jobs by deadline and remove the longest current job whenever cumulative duration exceeds that deadline.",
        "Durations 4/3, 2/4, 2/6 reject the four-unit job and retain the other two.",
        "Job; Schedule; maximize_count(vector<Job>)",
        "priority_queue",
        "EDF without overload removal",
    ),
    TaskSpec(
        "interval-court-docket",
        "docket-lateness-order-v2",
        "DocketLatenessOrder",
        "edf_max_lateness",
        "Docket lateness order",
        "Order every hearing to minimize maximum lateness.",
        "Order by due time then ID, accumulate completion, and report signed maximum lateness.",
        "Hearings (duration,due) (3,8), (2,4), (1,4) run IDs 2,3,1.",
        "Hearing; Docket; order(vector<Hearing>)",
        "max_lateness",
        "input-order scheduling",
    ),
    TaskSpec(
        "interval-charging-stations",
        "charging-priority-admission-v2",
        "ChargingPriorityAdmission",
        "capacity_eviction_sweep",
        "Charging priority admission",
        "Retain higher-priority sessions when plug capacity is exceeded.",
        "Half-open sessions ending at a timestamp leave before starts; overload evicts lowest priority and then highest ID.",
        "With one plug, overlapping priorities 2 and 9 retain priority 9.",
        "Session; Admission; admit(plugs,vector<Session>)",
        "evicted",
        "first-come admission",
    ),
    TaskSpec(
        "interval-field-bookings",
        "field-reservation-ledger-v2",
        "FieldReservationLedger",
        "ordered_mutable_calendar",
        "Field reservation ledger",
        "Book, cancel, reschedule, and list non-overlapping reservations atomically.",
        "Intervals are half-open with start below end; failed reschedule restores the prior booking exactly.",
        "Bookings [1,3) and [3,5) may touch; moving the first into the second fails without mutation.",
        "Booking; book; cancel; reschedule; agenda",
        "by_start_",
        "append-only booking vector",
    ),
    TaskSpec(
        "interval-freight-platforms",
        "freight-platform-peak-v2",
        "FreightPlatformPeak",
        "peak_overlap_sweep",
        "Freight platform peak",
        "Find the earliest peak occupancy and its active freight IDs.",
        "End events precede start events at equal time under half-open semantics.",
        "Freights [0,4), [2,5), [3,6) peak at time 3 with all three IDs.",
        "Freight; Peak; inspect(vector<Freight>)",
        "active",
        "pairwise conflict count",
    ),
    TaskSpec(
        "interval-ad-campaigns",
        "campaign-budget-selection-v2",
        "CampaignBudgetSelection",
        "budgeted_interval_dp",
        "Campaign budget selection",
        "Choose compatible campaigns under a spend budget.",
        "Maximize value, then minimize spend, then choose lexicographically smaller schedule IDs.",
        "A conflicting high-value campaign may lose to two compatible campaigns only when both fit the budget.",
        "Campaign; Plan; choose(budget,vector<Campaign>)",
        "budget + 1",
        "budget-only or interval-only DP",
    ),
    TaskSpec(
        "interval-shift-coverage",
        "shift-cost-cover-v2",
        "ShiftCostCover",
        "minimum_cost_cover_dag",
        "Shift cost cover",
        "Cover a target interval at minimum cost.",
        "Shifts may extend beyond the target; minimize cost, then count, then lexicographic IDs.",
        "Two cheap touching shifts can beat one expensive long shift while still covering every point.",
        "Shift; Cover; cover(left,right,vector<Shift>)",
        "coordinates",
        "farthest-reach greedy",
    ),
    TaskSpec(
        "interval-flight-gates",
        "flight-gate-partition-v2",
        "FlightGatePartition",
        "interval_partition_heap",
        "Flight gate partition",
        "Assign buffered turnarounds to the minimum number of gates.",
        "Release all ready gates before each start and reuse the lowest available gate number.",
        "Flights [0,3) and [3,5) reuse gate zero when the first buffer is zero.",
        "Flight; Assignment; assign(vector<Flight>)",
        "busy",
        "always allocate a new gate",
    ),
    TaskSpec(
        "interval-warehouse-docks",
        "dock-common-free-slot-v2",
        "DockCommonFreeSlot",
        "multi_calendar_intersection",
        "Dock common free slot",
        "Find the earliest requested-duration slot free in every dock calendar.",
        "Calendars must be sorted non-overlapping half-open busy spans; zero duration returns open.",
        "If one dock is busy [0,2) and another [2,4), the first two-unit common slot begins at 4.",
        "Busy; Slot; find(open,close,duration,calendars)",
        "cursor",
        "checking only one calendar",
    ),
    TaskSpec(
        "interval-road-closures",
        "road-closure-complement-v2",
        "RoadClosureComplement",
        "union_complement",
        "Road closure complement",
        "Merge clipped closures and report open route segments.",
        "Touching closures merge and closures outside the route are clipped or ignored.",
        "On route [0,10), closures [-2,2), [2,4), [7,12) leave [4,7) open.",
        "Closure; Segment; Report; analyze(bounds,closures)",
        "out.closed",
        "adjacent-only non-transitive merge",
    ),
    TaskSpec(
        "interval-sensor-outages",
        "sensor-k-outage-duration-v2",
        "SensorKOutageDuration",
        "k_coverage_sweep",
        "Sensor k-outage duration",
        "Measure spans with at least k simultaneous outages.",
        "Use half-open deltas; return maximal qualifying spans and total duration.",
        "Outages [0,4), [2,6), [3,5) with k=2 qualify on [2,5).",
        "Outage; Span; Coverage; measure(k,outages)",
        "level",
        "plain union duration",
    ),
    TaskSpec(
        "interval-stream-recording",
        "recording-conflict-components-v2",
        "RecordingConflictComponents",
        "overlap_components_dsu",
        "Recording conflict components",
        "Build connected components of the recording overlap graph.",
        "Half-open touching is not overlap; connectivity is transitive; sort members and components deterministically.",
        "Recordings [0,3), [2,5), [4,6) form one component through an overlap chain.",
        "Recording; Components; group(vector<Recording>)",
        "parent",
        "direct-neighbor groups without transitive closure",
    ),
    TaskSpec(
        "interval-conference-tracks",
        "conference-containment-forest-v2",
        "ConferenceContainmentForest",
        "containment_stack",
        "Conference containment forest",
        "Build the immediate strict-containment forest of session windows.",
        "Crossing and identical windows reject the batch; roots and children follow deterministic interval order.",
        "[0,10) contains [1,4), which contains [2,3); the immediate parents are preserved.",
        "Session; Forest; build(vector<Session>)",
        "stack",
        "assigning every descendant to the root",
    ),
    TaskSpec(
        "interval-patrol-routes",
        "patrol-travel-chain-v2",
        "PatrolTravelChain",
        "travel_dag_longest_path",
        "Patrol travel chain",
        "Choose the highest-score chain using directed zone travel gaps.",
        "The travel matrix is square and nonnegative; maximize score then lexicographic schedule IDs.",
        "An asymmetric travel matrix can allow A-to-B while forbidding B-to-A.",
        "Patrol; Chain; choose(patrols,travel)",
        "travel[",
        "constant symmetric gap scheduling",
    ),
    TaskSpec(
        "interval-lease-audits",
        "lease-cyclic-normalization-v2",
        "LeaseCyclicNormalization",
        "cyclic_interval_normalization",
        "Lease cyclic normalization",
        "Normalize weekly arcs that may wrap across the period boundary.",
        "Endpoints lie in the period; equal endpoints mean the full cycle; merge touching pieces and rejoin boundary pieces.",
        "In period 10, [8,2) and [1,4) normalize to wrapped [8,4).",
        "Lease; Arc; Normalized; normalize(period,leases)",
        "pieces",
        "rejecting every start above end",
    ),
    TaskSpec(
        "interval-rescue-dispatch",
        "rescue-team-matching-v2",
        "RescueTeamMatching",
        "bipartite_augmenting_match",
        "Rescue team matching",
        "Compute a deterministic maximum-cardinality incident/team matching.",
        "A team must cover the full incident interval and skill; augmenting paths may rematch earlier incidents.",
        "A flexible team assigned first must be rematched so a later constrained incident is also served.",
        "Incident; Team; Pair; Match; assign(incidents,teams)",
        "augment",
        "one-pass greedy matching",
    ),
    TaskSpec(
        "interval-data-backups",
        "backup-checkpoint-cover-v2",
        "BackupCheckpointCover",
        "bitmask_set_cover",
        "Backup checkpoint cover",
        "Choose the fewest windows covering every required checkpoint.",
        "Windows contain closed endpoints; at most 20 unique checkpoints; tie by lexicographic window IDs.",
        "A greedy window covering many early points can lose to two windows that cover all points.",
        "Window; Cover; choose(checkpoints,windows)",
        "full_mask",
        "greedy most-points selection",
    ),
)


DECLARATIONS = {
    "weighted_interval_dp": "struct Surgery { int id,start,end,value,cleanup; }; struct Plan { bool valid=false; int total_value=0; std::vector<int> ids; }; static Plan choose(const std::vector<Surgery>&);",
    "greedy_target_cover": "struct Window { int id,left,right; }; struct Cover { bool valid=false; bool possible=false; std::vector<int> ids; }; static Cover cover(int,int,const std::vector<Window>&);",
    "minimum_stabbing": "struct Program { int id,start,end; }; struct BreakPlan { bool valid=false; std::vector<int> points; }; static BreakPlan place(const std::vector<Program>&);",
    "moore_hodgson": "struct Job { int id,duration,deadline; }; struct Schedule { bool valid=false; std::vector<int> kept_ids; std::vector<int> rejected_ids; }; static Schedule maximize_count(const std::vector<Job>&);",
    "edf_max_lateness": "struct Hearing { int id,duration,due; }; struct Docket { bool valid=false; long long max_lateness=0; std::vector<int> ids; std::vector<long long> completion; }; static Docket order(const std::vector<Hearing>&);",
    "capacity_eviction_sweep": "struct Session { int id,start,end,priority; }; struct Admission { bool valid=false; std::vector<int> admitted_ids; std::vector<int> rejected_ids; }; static Admission admit(int,const std::vector<Session>&);",
    "ordered_mutable_calendar": "struct Booking { int id,start,end; }; bool book(Booking); bool cancel(int); bool reschedule(int,int,int); std::vector<int> agenda() const; private: std::map<std::pair<int,int>,Booking> by_start_; std::map<int,std::pair<int,int>> starts_by_id_; bool conflict(int,int,int) const;",
    "peak_overlap_sweep": "struct Freight { int id,start,end; }; struct Peak { bool valid=false; int count=0; int first_time=0; std::vector<int> ids; }; static Peak inspect(const std::vector<Freight>&);",
    "budgeted_interval_dp": "struct Campaign { int id,start,end,spend,value; }; struct Plan { bool valid=false; int total_value=0; int total_spend=0; std::vector<int> ids; }; static Plan choose(int,const std::vector<Campaign>&);",
    "minimum_cost_cover_dag": "struct Shift { int id,start,end,cost; }; struct Cover { bool valid=false; bool possible=false; long long cost=0; std::vector<int> ids; }; static Cover cover(int,int,const std::vector<Shift>&);",
    "interval_partition_heap": "struct Flight { int id,start,end,buffer; }; struct Assignment { bool valid=false; int gate_count=0; std::vector<int> gate_for_input; std::vector<std::vector<int>> flights_by_gate; }; static Assignment assign(const std::vector<Flight>&);",
    "multi_calendar_intersection": "struct Busy { int start,end; }; using Calendar=std::vector<Busy>; struct Slot { bool valid=false; bool found=false; int start=0; int end=0; }; static Slot find(int,int,int,const std::vector<Calendar>&);",
    "union_complement": "struct Closure { int id,left,right; }; struct Segment { int left,right; }; struct Report { bool valid=false; std::vector<Segment> closed; std::vector<Segment> open; }; static Report analyze(int,int,const std::vector<Closure>&);",
    "k_coverage_sweep": "struct Outage { int id,start,end; }; struct Span { int start,end; }; struct Coverage { bool valid=false; long long duration=0; std::vector<Span> spans; }; static Coverage measure(int,const std::vector<Outage>&);",
    "overlap_components_dsu": "struct Recording { int id,start,end; }; struct Components { bool valid=false; std::vector<std::vector<int>> groups; }; static Components group(const std::vector<Recording>&);",
    "containment_stack": "struct Session { int id,start,end; }; struct Forest { bool valid=false; std::vector<int> parent_for_input; std::vector<int> roots; }; static Forest build(const std::vector<Session>&);",
    "travel_dag_longest_path": "struct Patrol { int id,zone,start,end,score; }; struct Chain { bool valid=false; int score=0; std::vector<int> ids; }; static Chain choose(const std::vector<Patrol>&,const std::vector<std::vector<int>>&);",
    "cyclic_interval_normalization": "struct Lease { int id,start,end; }; struct Arc { int start,end; }; struct Normalized { bool valid=false; int covered=0; std::vector<Arc> arcs; }; static Normalized normalize(int,const std::vector<Lease>&);",
    "bipartite_augmenting_match": "struct Incident { int id,start,end,skill; }; struct Team { int id,available_start,available_end,skill; }; struct Pair { int incident_id,team_id; }; struct Match { bool valid=false; std::vector<Pair> pairs; std::vector<int> unmatched_incidents; }; static Match assign(const std::vector<Incident>&,const std::vector<Team>&);",
    "bitmask_set_cover": "struct Window { int id,start,end; }; struct Cover { bool valid=false; bool possible=false; std::vector<int> ids; }; static Cover choose(const std::vector<int>&,const std::vector<Window>&);",
}


def header_for(spec: TaskSpec) -> str:
    return f"""#pragma once
#include <map>
#include <optional>
#include <utility>
#include <vector>
namespace curriculum {{
class {spec.class_name} {{ public: {DECLARATIONS[spec.mode]} }};
}}  // namespace curriculum
"""


STARTERS = {
    "weighted_interval_dp": '#include "task.h"\nnamespace curriculum { CLASS::Plan CLASS::choose(const std::vector<Surgery>&){return {};} }\n',
    "greedy_target_cover": '#include "task.h"\nnamespace curriculum { CLASS::Cover CLASS::cover(int,int,const std::vector<Window>&){return {};} }\n',
    "minimum_stabbing": '#include "task.h"\nnamespace curriculum { CLASS::BreakPlan CLASS::place(const std::vector<Program>&){return {};} }\n',
    "moore_hodgson": '#include "task.h"\nnamespace curriculum { CLASS::Schedule CLASS::maximize_count(const std::vector<Job>&){return {};} }\n',
    "edf_max_lateness": '#include "task.h"\nnamespace curriculum { CLASS::Docket CLASS::order(const std::vector<Hearing>&){return {};} }\n',
    "capacity_eviction_sweep": '#include "task.h"\nnamespace curriculum { CLASS::Admission CLASS::admit(int,const std::vector<Session>&){return {};} }\n',
    "ordered_mutable_calendar": '#include "task.h"\nnamespace curriculum { bool CLASS::conflict(int,int,int)const{return true;} bool CLASS::book(Booking){return false;} bool CLASS::cancel(int){return false;} bool CLASS::reschedule(int,int,int){return false;} std::vector<int> CLASS::agenda()const{return {};} }\n',
    "peak_overlap_sweep": '#include "task.h"\nnamespace curriculum { CLASS::Peak CLASS::inspect(const std::vector<Freight>&){return {};} }\n',
    "budgeted_interval_dp": '#include "task.h"\nnamespace curriculum { CLASS::Plan CLASS::choose(int,const std::vector<Campaign>&){return {};} }\n',
    "minimum_cost_cover_dag": '#include "task.h"\nnamespace curriculum { CLASS::Cover CLASS::cover(int,int,const std::vector<Shift>&){return {};} }\n',
    "interval_partition_heap": '#include "task.h"\nnamespace curriculum { CLASS::Assignment CLASS::assign(const std::vector<Flight>&){return {};} }\n',
    "multi_calendar_intersection": '#include "task.h"\nnamespace curriculum { CLASS::Slot CLASS::find(int,int,int,const std::vector<Calendar>&){return {};} }\n',
    "union_complement": '#include "task.h"\nnamespace curriculum { CLASS::Report CLASS::analyze(int,int,const std::vector<Closure>&){return {};} }\n',
    "k_coverage_sweep": '#include "task.h"\nnamespace curriculum { CLASS::Coverage CLASS::measure(int,const std::vector<Outage>&){return {};} }\n',
    "overlap_components_dsu": '#include "task.h"\nnamespace curriculum { CLASS::Components CLASS::group(const std::vector<Recording>&){return {};} }\n',
    "containment_stack": '#include "task.h"\nnamespace curriculum { CLASS::Forest CLASS::build(const std::vector<Session>&){return {};} }\n',
    "travel_dag_longest_path": '#include "task.h"\nnamespace curriculum { CLASS::Chain CLASS::choose(const std::vector<Patrol>&,const std::vector<std::vector<int>>&){return {};} }\n',
    "cyclic_interval_normalization": '#include "task.h"\nnamespace curriculum { CLASS::Normalized CLASS::normalize(int,const std::vector<Lease>&){return {};} }\n',
    "bipartite_augmenting_match": '#include "task.h"\nnamespace curriculum { CLASS::Match CLASS::assign(const std::vector<Incident>&,const std::vector<Team>&){return {};} }\n',
    "bitmask_set_cover": '#include "task.h"\nnamespace curriculum { CLASS::Cover CLASS::choose(const std::vector<int>&,const std::vector<Window>&){return {};} }\n',
}


REFERENCES: dict[str, str] = {}
TESTS: dict[str, tuple[str, str]] = {}

REFERENCES.update(
    {
        "weighted_interval_dp": r"""#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum {
CLASS::Plan CLASS::choose(const std::vector<Surgery>& input) {
  Plan invalid; std::set<int> seen; for (const auto& x:input) if(x.id<=0||x.start>=x.end||x.value<0||x.cleanup<0||!seen.insert(x.id).second) return invalid;
  auto jobs=input; std::sort(jobs.begin(),jobs.end(),[](const Surgery&a,const Surgery&b){const long long ar=(long long)a.end+a.cleanup,br=(long long)b.end+b.cleanup;return ar!=br?ar<br:a.id<b.id;});
  struct State{int value=0;std::vector<int> ids;}; std::vector<long long> ready; for(const auto&x:jobs)ready.push_back((long long)x.end+x.cleanup); std::vector<State> dp(jobs.size()+1);
  auto better=[](const State&a,const State&b){return a.value!=b.value?a.value>b.value:std::lexicographical_compare(a.ids.begin(),a.ids.end(),b.ids.begin(),b.ids.end());};
  for(std::size_t i=1;i<=jobs.size();++i){const auto&x=jobs[i-1];const auto p=(std::size_t)(std::upper_bound(ready.begin(),ready.begin()+(long long)i-1,(long long)x.start)-ready.begin());State take=dp[p];take.value+=x.value;take.ids.push_back(x.id);dp[i]=better(take,dp[i-1])?take:dp[i-1];}
  return {true,dp.back().value,dp.back().ids};
}}
""",
        "greedy_target_cover": r"""#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum {
CLASS::Cover CLASS::cover(int left,int right,const std::vector<Window>& input){Cover out;std::set<int>seen;if(left>right)return out;for(const auto&w:input)if(w.id<=0||w.left>=w.right||!seen.insert(w.id).second)return out;out.valid=true;if(left==right){out.possible=true;return out;}auto windows=input;std::sort(windows.begin(),windows.end(),[](const Window&a,const Window&b){return a.left!=b.left?a.left<b.left:(a.right!=b.right?a.right>b.right:a.id<b.id);});int at=left;std::size_t i=0;while(at<right){int best_right=at,best_id=-1;while(i<windows.size()&&windows[i].left<=at){if(windows[i].right>best_right||(windows[i].right==best_right&&(best_id<0||windows[i].id<best_id))){best_right=windows[i].right;best_id=windows[i].id;}++i;}if(best_id<0){out.ids.clear();return out;}out.ids.push_back(best_id);at=best_right;}out.possible=true;return out;}
}
""",
        "minimum_stabbing": r"""#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum {
CLASS::BreakPlan CLASS::place(const std::vector<Program>& input){BreakPlan out;std::set<int>seen;for(const auto&p:input)if(p.id<=0||p.start>p.end||!seen.insert(p.id).second)return out;auto programs=input;std::sort(programs.begin(),programs.end(),[](const Program&a,const Program&b){return a.end!=b.end?a.end<b.end:(a.start!=b.start?a.start<b.start:a.id<b.id);});std::optional<int>last_point;for(const auto&p:programs)if(!last_point||*last_point<p.start){last_point=p.end;out.points.push_back(p.end);}out.valid=true;return out;}
}
""",
        "moore_hodgson": r"""#include "task.h"
#include <algorithm>
#include <queue>
#include <set>
namespace curriculum {
CLASS::Schedule CLASS::maximize_count(const std::vector<Job>& input){Schedule out;std::set<int>seen;for(const auto&j:input)if(j.id<=0||j.duration<=0||j.deadline<0||!seen.insert(j.id).second)return out;auto jobs=input;std::sort(jobs.begin(),jobs.end(),[](const Job&a,const Job&b){return a.deadline!=b.deadline?a.deadline<b.deadline:a.id<b.id;});std::priority_queue<std::pair<int,int>> longest;std::set<int>removed;long long elapsed=0;for(const auto&j:jobs){elapsed+=j.duration;longest.push({j.duration,j.id});if(elapsed>j.deadline){auto drop=longest.top();longest.pop();elapsed-=drop.first;removed.insert(drop.second);}}for(const auto&j:jobs)if(!removed.count(j.id))out.kept_ids.push_back(j.id);out.rejected_ids.assign(removed.begin(),removed.end());out.valid=true;return out;}
}
""",
        "edf_max_lateness": r"""#include "task.h"
#include <algorithm>
#include <limits>
#include <set>
namespace curriculum {
CLASS::Docket CLASS::order(const std::vector<Hearing>& input){Docket out;std::set<int>seen;for(const auto&h:input)if(h.id<=0||h.duration<=0||!seen.insert(h.id).second)return out;auto hearings=input;std::sort(hearings.begin(),hearings.end(),[](const Hearing&a,const Hearing&b){return a.due!=b.due?a.due<b.due:a.id<b.id;});long long at=0;long long max_lateness=std::numeric_limits<long long>::min();for(const auto&h:hearings){at+=h.duration;out.ids.push_back(h.id);out.completion.push_back(at);max_lateness=std::max(max_lateness,at-(long long)h.due);}out.max_lateness=hearings.empty()?0:max_lateness;out.valid=true;return out;}
}
""",
        "capacity_eviction_sweep": r"""#include "task.h"
#include <algorithm>
#include <queue>
#include <set>
namespace curriculum {
CLASS::Admission CLASS::admit(int plugs,const std::vector<Session>& input){Admission out;if(plugs<0)return out;std::set<int>seen;for(const auto&s:input)if(s.id<=0||s.start>=s.end||s.priority<0||!seen.insert(s.id).second)return out;auto sessions=input;std::sort(sessions.begin(),sessions.end(),[](const Session&a,const Session&b){return a.start!=b.start?a.start<b.start:a.id<b.id;});std::priority_queue<std::pair<int,int>,std::vector<std::pair<int,int>>,std::greater<std::pair<int,int>>> endings;std::set<std::pair<int,int>> by_priority;std::set<int>active,evicted;for(const auto&s:sessions){while(!endings.empty()&&endings.top().first<=s.start){int id=endings.top().second;endings.pop();if(active.erase(id))for(auto it=by_priority.begin();it!=by_priority.end();++it)if(-it->second==id){by_priority.erase(it);break;}}active.insert(s.id);endings.push({s.end,s.id});by_priority.insert({s.priority,-s.id});if((int)active.size()>plugs){auto worst=*by_priority.begin();by_priority.erase(by_priority.begin());int id=-worst.second;active.erase(id);evicted.insert(id);}}
  for(const auto&s:input){(evicted.count(s.id)?out.rejected_ids:out.admitted_ids).push_back(s.id);}std::sort(out.admitted_ids.begin(),out.admitted_ids.end());std::sort(out.rejected_ids.begin(),out.rejected_ids.end());out.valid=true;return out;}
}
""",
        "ordered_mutable_calendar": r"""#include "task.h"
#include <algorithm>
namespace curriculum {
bool CLASS::conflict(int start,int end,int ignored)const{auto it=by_start_.lower_bound({start,-1});if(it!=by_start_.end()&&it->second.id!=ignored&&it->second.start<end)return true;if(it!=by_start_.begin()){--it;if(it->second.id!=ignored&&start<it->second.end)return true;}return false;}
bool CLASS::book(Booking b){if(b.id<=0||b.start>=b.end||starts_by_id_.count(b.id)||conflict(b.start,b.end,-1))return false;auto key=std::make_pair(b.start,b.id);by_start_[key]=b;starts_by_id_[b.id]=key;return true;}
bool CLASS::cancel(int id){auto found=starts_by_id_.find(id);if(found==starts_by_id_.end())return false;by_start_.erase(found->second);starts_by_id_.erase(found);return true;}
bool CLASS::reschedule(int id,int start,int end){auto found=starts_by_id_.find(id);if(found==starts_by_id_.end()||start>=end)return false;Booking old=by_start_.at(found->second);by_start_.erase(found->second);starts_by_id_.erase(found);Booking moved{id,start,end};if(!book(moved)){book(old);return false;}return true;}
std::vector<int> CLASS::agenda()const{std::vector<int>out;for(const auto&entry:by_start_)out.push_back(entry.second.id);return out;}
}
""",
        "peak_overlap_sweep": r"""#include "task.h"
#include <algorithm>
#include <set>
#include <tuple>
namespace curriculum {
CLASS::Peak CLASS::inspect(const std::vector<Freight>& input){Peak out;std::set<int>seen;std::vector<std::tuple<int,int,int>>events;for(const auto&f:input){if(f.id<=0||f.start>=f.end||!seen.insert(f.id).second)return out;events.push_back({f.start,1,f.id});events.push_back({f.end,0,f.id});}std::sort(events.begin(),events.end());std::set<int>active;std::size_t i=0;while(i<events.size()){int time=std::get<0>(events[i]);while(i<events.size()&&std::get<0>(events[i])==time&&std::get<1>(events[i])==0){active.erase(std::get<2>(events[i++]));}while(i<events.size()&&std::get<0>(events[i])==time&&std::get<1>(events[i])==1){active.insert(std::get<2>(events[i++]));}if((int)active.size()>out.count){out.count=(int)active.size();out.first_time=time;out.ids.assign(active.begin(),active.end());}}out.valid=true;return out;}
}
""",
        "budgeted_interval_dp": r"""#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum {
CLASS::Plan CLASS::choose(int budget,const std::vector<Campaign>& input){Plan invalid;if(budget<0)return invalid;std::set<int>seen;for(const auto&c:input)if(c.id<=0||c.start>=c.end||c.spend<0||c.value<0||!seen.insert(c.id).second)return invalid;auto jobs=input;std::sort(jobs.begin(),jobs.end(),[](const Campaign&a,const Campaign&b){return a.end!=b.end?a.end<b.end:a.id<b.id;});std::vector<int>ends;for(const auto&x:jobs)ends.push_back(x.end);struct State{bool set=false;int value=0,spend=0;std::vector<int>ids;};auto better=[](const State&a,const State&b){if(!a.set)return false;if(!b.set)return true;if(a.value!=b.value)return a.value>b.value;if(a.spend!=b.spend)return a.spend<b.spend;return std::lexicographical_compare(a.ids.begin(),a.ids.end(),b.ids.begin(),b.ids.end());};std::vector<std::vector<State>>dp(jobs.size()+1,std::vector<State>((std::size_t)budget + 1));for(int b=0;b<=budget;++b)dp[0][b].set=true;for(std::size_t i=1;i<=jobs.size();++i){auto x=jobs[i-1];auto p=(std::size_t)(std::upper_bound(ends.begin(),ends.begin()+(long long)i-1,x.start)-ends.begin());for(int b=0;b<=budget;++b){dp[i][b]=dp[i-1][b];if(x.spend<=b){State take=dp[p][b-x.spend];take.set=true;take.value+=x.value;take.spend+=x.spend;take.ids.push_back(x.id);if(better(take,dp[i][b]))dp[i][b]=take;}}}auto best=dp.back()[budget];return {true,best.value,best.spend,best.ids};}
}
""",
        "minimum_cost_cover_dag": r"""#include "task.h"
#include <algorithm>
#include <limits>
#include <set>
namespace curriculum {
CLASS::Cover CLASS::cover(int left,int right,const std::vector<Shift>& input){Cover out;std::set<int>seen;if(left>right)return out;for(const auto&s:input)if(s.id<=0||s.start>=s.end||s.cost<0||!seen.insert(s.id).second)return out;out.valid=true;if(left==right){out.possible=true;return out;}std::vector<int>coordinates{left,right};for(const auto&s:input){coordinates.push_back(std::max(left,std::min(right,s.start)));coordinates.push_back(std::max(left,std::min(right,s.end)));}std::sort(coordinates.begin(),coordinates.end());coordinates.erase(std::unique(coordinates.begin(),coordinates.end()),coordinates.end());struct State{bool set=false;long long cost=0;std::vector<int>ids;};auto better=[](const State&a,const State&b){if(!a.set)return false;if(!b.set)return true;if(a.cost!=b.cost)return a.cost<b.cost;if(a.ids.size()!=b.ids.size())return a.ids.size()<b.ids.size();return std::lexicographical_compare(a.ids.begin(),a.ids.end(),b.ids.begin(),b.ids.end());};std::vector<State>dp(coordinates.size());dp[0].set=true;for(std::size_t i=0;i<coordinates.size();++i)if(dp[i].set)for(const auto&s:input)if(s.start<=coordinates[i]&&s.end>coordinates[i]){int reach=std::min(right,s.end);auto j=(std::size_t)(std::lower_bound(coordinates.begin(),coordinates.end(),reach)-coordinates.begin());State next=dp[i];next.cost+=s.cost;next.ids.push_back(s.id);if(better(next,dp[j]))dp[j]=next;}if(dp.back().set){out.possible=true;out.cost=dp.back().cost;out.ids=dp.back().ids;}return out;}
}
""",
    }
)


def _test_source(body: str) -> str:
    return (
        '#include "task.h"\n'
        "#include <algorithm>\n#include <optional>\n#include <vector>\n"
        "using curriculum::CLASS;\n"
        "int main(){int failures=0;auto check=[&](bool ok){if(!ok)++failures;};"
        + body
        + "return failures?1:0;}\n"
    )


TESTS.update(
    {
        "weighted_interval_dp": (
            _test_source(
                "auto x=CLASS::choose({{1,0,3,5,1},{2,3,5,9,0},{3,4,6,8,0}});check(x.valid&&x.total_value==13&&x.ids==std::vector<int>({1,3}));"
            ),
            _test_source(
                "auto x=CLASS::choose({{1,0,6,10,0},{2,0,3,6,0},{3,3,6,6,0}});check(x.valid&&x.total_value==12&&x.ids==std::vector<int>({2,3}));check(!CLASS::choose({{1,0,1,1,0},{1,2,3,2,0}}).valid);"
            ),
        ),
        "greedy_target_cover": (
            _test_source(
                "auto x=CLASS::cover(0,9,{{1,0,4},{2,2,7},{3,4,9}});check(x.valid&&x.possible&&x.ids==std::vector<int>({1,3}));"
            ),
            _test_source(
                "auto x=CLASS::cover(0,10,{{1,0,2},{2,0,5},{3,5,10},{4,2,6}});check(x.possible&&x.ids==std::vector<int>({2,3}));check(!CLASS::cover(0,4,{{1,0,2},{2,3,4}}).possible);check(!CLASS::cover(2,1,{}).valid);"
            ),
        ),
        "minimum_stabbing": (
            _test_source(
                "auto x=CLASS::place({{1,1,3},{2,2,5},{3,5,7}});check(x.valid&&x.points==std::vector<int>({3,7}));"
            ),
            _test_source(
                "auto x=CLASS::place({{1,0,10},{2,2,2},{3,2,5},{4,8,9}});check(x.valid&&x.points==std::vector<int>({2,9}));check(!CLASS::place({{1,3,2}}).valid);"
            ),
        ),
        "moore_hodgson": (
            _test_source(
                "auto x=CLASS::maximize_count({{1,4,3},{2,2,4},{3,2,6}});check(x.valid&&x.kept_ids==std::vector<int>({2,3})&&x.rejected_ids==std::vector<int>({1}));"
            ),
            _test_source(
                "auto x=CLASS::maximize_count({{1,3,3},{2,2,3},{3,1,4}});check(x.valid&&x.kept_ids==std::vector<int>({2,3}));check(!CLASS::maximize_count({{1,0,2}}).valid);"
            ),
        ),
        "edf_max_lateness": (
            _test_source(
                "auto x=CLASS::order({{1,3,8},{2,2,4},{3,1,4}});check(x.valid&&x.ids==std::vector<int>({2,3,1})&&x.completion==std::vector<long long>({2,3,6})&&x.max_lateness==-1);"
            ),
            _test_source(
                "auto x=CLASS::order({{2,2,1},{1,2,1}});check(x.valid&&x.ids==std::vector<int>({1,2})&&x.max_lateness==3);check(!CLASS::order({{1,-1,2}}).valid);"
            ),
        ),
        "capacity_eviction_sweep": (
            _test_source(
                "auto x=CLASS::admit(1,{{1,0,5,2},{2,1,4,9}});check(x.valid&&x.admitted_ids==std::vector<int>({2})&&x.rejected_ids==std::vector<int>({1}));"
            ),
            _test_source(
                "auto x=CLASS::admit(2,{{1,0,3,5},{2,0,3,5},{3,1,2,9},{4,3,4,1}});check(x.valid&&x.admitted_ids==std::vector<int>({1,3,4})&&x.rejected_ids==std::vector<int>({2}));check(!CLASS::admit(-1,{}).valid);"
            ),
        ),
        "ordered_mutable_calendar": (
            _test_source(
                "CLASS x;check(x.book({1,1,3}));check(x.book({2,3,5}));check(!x.reschedule(1,4,6));check(x.agenda()==std::vector<int>({1,2}));check(x.cancel(1));"
            ),
            _test_source(
                "CLASS x;check(x.book({2,5,7}));check(x.book({1,1,2}));check(x.reschedule(2,2,4));check(x.agenda()==std::vector<int>({1,2}));check(!x.cancel(9));check(!x.book({1,8,9}));"
            ),
        ),
        "peak_overlap_sweep": (
            _test_source(
                "auto x=CLASS::inspect({{1,0,4},{2,2,5},{3,3,6}});check(x.valid&&x.count==3&&x.first_time==3&&x.ids==std::vector<int>({1,2,3}));"
            ),
            _test_source(
                "auto x=CLASS::inspect({{1,0,2},{2,2,4},{3,1,3}});check(x.valid&&x.count==2&&x.first_time==1&&x.ids==std::vector<int>({1,3}));check(!CLASS::inspect({{1,2,2}}).valid);"
            ),
        ),
        "budgeted_interval_dp": (
            _test_source(
                "auto x=CLASS::choose(4,{{1,0,2,2,5},{2,2,4,2,5},{3,0,4,3,8}});check(x.valid&&x.total_value==10&&x.total_spend==4&&x.ids==std::vector<int>({1,2}));"
            ),
            _test_source(
                "auto x=CLASS::choose(3,{{1,0,2,0,3},{2,2,4,3,4},{3,0,4,2,6}});check(x.valid&&x.total_value==7&&x.ids==std::vector<int>({1,2}));check(!CLASS::choose(-1,{}).valid);"
            ),
        ),
        "minimum_cost_cover_dag": (
            _test_source(
                "auto x=CLASS::cover(0,4,{{1,0,2,2},{2,2,4,2},{3,0,4,7}});check(x.valid&&x.possible&&x.cost==4&&x.ids==std::vector<int>({1,2}));"
            ),
            _test_source(
                "auto x=CLASS::cover(0,6,{{1,-2,2,1},{2,2,5,1},{3,5,9,1},{4,0,6,8}});check(x.possible&&x.cost==3&&x.ids==std::vector<int>({1,2,3}));check(!CLASS::cover(0,5,{{1,0,2,1},{2,3,5,1}}).possible);"
            ),
        ),
        "interval_partition_heap": (
            _test_source(
                "auto x=CLASS::assign({{1,0,3,0},{2,3,5,0},{3,2,4,0}});check(x.valid&&x.gate_count==2&&x.gate_for_input==std::vector<int>({0,0,1}));"
            ),
            _test_source(
                "auto x=CLASS::assign({{1,0,2,2},{2,2,3,0},{3,4,5,0}});check(x.valid&&x.gate_count==2&&x.gate_for_input==std::vector<int>({0,1,0}));check(!CLASS::assign({{1,2,2,0}}).valid);"
            ),
        ),
        "multi_calendar_intersection": (
            _test_source(
                "auto x=CLASS::find(0,10,2,{{{0,2}},{{2,4}}});check(x.valid&&x.found&&x.start==4&&x.end==6);"
            ),
            _test_source(
                "auto x=CLASS::find(0,8,2,{{{1,3},{5,6}},{{0,2},{4,5}}});check(x.valid&&x.found&&x.start==6);check(CLASS::find(3,3,0,{}).found);check(!CLASS::find(0,5,1,{{{3,4},{2,3}}}).valid);"
            ),
        ),
        "union_complement": (
            _test_source(
                "auto x=CLASS::analyze(0,10,{{1,-2,2},{2,2,4},{3,7,12}});check(x.valid&&x.closed.size()==2&&x.closed[0].left==0&&x.closed[0].right==4&&x.open.size()==1&&x.open[0].left==4&&x.open[0].right==7);"
            ),
            _test_source(
                "auto x=CLASS::analyze(0,10,{{1,1,3},{2,3,5},{3,4,8}});check(x.valid&&x.closed.size()==1&&x.closed[0].right==8&&x.open.size()==2);check(!CLASS::analyze(4,2,{}).valid);"
            ),
        ),
        "k_coverage_sweep": (
            _test_source(
                "auto x=CLASS::measure(2,{{1,0,4},{2,2,6},{3,3,5}});check(x.valid&&x.duration==3&&x.spans.size()==1&&x.spans[0].start==2&&x.spans[0].end==5);"
            ),
            _test_source(
                "auto x=CLASS::measure(3,{{1,0,10},{2,2,8},{3,4,6},{4,6,7}});check(x.valid&&x.duration==3&&x.spans.size()==1&&x.spans[0].start==4&&x.spans[0].end==7);check(!CLASS::measure(0,{}).valid);"
            ),
        ),
        "overlap_components_dsu": (
            _test_source(
                "auto x=CLASS::group({{1,0,3},{2,2,5},{3,4,6},{4,8,9}});check(x.valid&&x.groups==std::vector<std::vector<int>>({{1,2,3},{4}}));"
            ),
            _test_source(
                "auto x=CLASS::group({{1,0,2},{2,2,4},{3,1,3},{4,7,9}});check(x.valid&&x.groups==std::vector<std::vector<int>>({{1,2,3},{4}}));check(!CLASS::group({{1,0,0}}).valid);"
            ),
        ),
        "containment_stack": (
            _test_source(
                "auto x=CLASS::build({{1,0,10},{2,1,4},{3,2,3}});check(x.valid&&x.parent_for_input==std::vector<int>({-1,1,2})&&x.roots==std::vector<int>({1}));"
            ),
            _test_source(
                "auto x=CLASS::build({{1,0,10},{2,1,3},{3,4,8},{4,5,7}});check(x.valid&&x.parent_for_input==std::vector<int>({-1,1,1,3}));check(!CLASS::build({{1,0,5},{2,3,7}}).valid);check(!CLASS::build({{1,0,5},{2,0,5}}).valid);"
            ),
        ),
        "travel_dag_longest_path": (
            _test_source(
                "auto x=CLASS::choose({{1,0,0,2,4},{2,1,3,5,8},{3,0,5,6,3}},{{0,1},{5,0}});check(x.valid&&x.score==12&&x.ids==std::vector<int>({1,2}));"
            ),
            _test_source(
                "auto x=CLASS::choose({{1,1,0,2,5},{2,0,3,4,6},{3,0,4,5,9}},{{0,8},{0,0}});check(x.valid&&x.score==20&&x.ids==std::vector<int>({1,2,3}));check(!CLASS::choose({{1,2,0,1,1}},{{0}}).valid);"
            ),
        ),
        "cyclic_interval_normalization": (
            _test_source(
                "auto x=CLASS::normalize(10,{{1,8,2},{2,1,4}});check(x.valid&&x.covered==6&&x.arcs.size()==1&&x.arcs[0].start==8&&x.arcs[0].end==4);"
            ),
            _test_source(
                "auto full=CLASS::normalize(7,{{1,3,3}});check(full.valid&&full.covered==7&&full.arcs.size()==1&&full.arcs[0].start==0&&full.arcs[0].end==0);auto x=CLASS::normalize(10,{{1,9,1},{2,1,3},{3,5,7}});check(x.valid&&x.covered==6&&x.arcs.size()==2);check(!CLASS::normalize(10,{{1,-1,2}}).valid);"
            ),
        ),
        "bipartite_augmenting_match": (
            _test_source(
                "auto x=CLASS::assign({{1,0,4,1},{2,1,3,2}},{{1,0,4,2},{2,0,4,1}});check(x.valid&&x.pairs.size()==2&&x.unmatched_incidents.empty());"
            ),
            _test_source(
                "auto x=CLASS::assign({{1,0,5,2},{2,2,4,1},{3,0,9,3}},{{1,0,5,2},{2,0,4,1}});check(x.valid&&x.pairs.size()==2&&x.unmatched_incidents==std::vector<int>({3}));check(!CLASS::assign({{1,2,2,1}},{}).valid);"
            ),
        ),
        "bitmask_set_cover": (
            _test_source(
                "auto x=CLASS::choose({1,2,3,4,5,6},{{1,2,5},{2,1,3},{3,4,6}});check(x.valid&&x.possible&&x.ids==std::vector<int>({2,3}));"
            ),
            _test_source(
                "auto x=CLASS::choose({1,1,4},{{1,0,1},{2,1,4}});check(x.valid&&x.possible&&x.ids==std::vector<int>({2}));check(!CLASS::choose({0},{{1,1,2}}).possible);std::vector<int>many;for(int i=0;i<21;++i)many.push_back(i);check(!CLASS::choose(many,{}).valid);"
            ),
        ),
    }
)

REFERENCES.update(
    {
        "interval_partition_heap": r"""#include "task.h"
#include <algorithm>
#include <functional>
#include <queue>
#include <set>
namespace curriculum {
CLASS::Assignment CLASS::assign(const std::vector<Flight>& input){Assignment out;std::set<int>seen;for(const auto&f:input)if(f.id<=0||f.start>=f.end||f.buffer<0||!seen.insert(f.id).second)return out;std::vector<int>order(input.size());for(std::size_t i=0;i<input.size();++i)order[i]=(int)i;std::sort(order.begin(),order.end(),[&](int a,int b){return input[a].start!=input[b].start?input[a].start<input[b].start:input[a].id<input[b].id;});using Pair=std::pair<long long,int>;std::priority_queue<Pair,std::vector<Pair>,std::greater<Pair>>busy;std::priority_queue<int,std::vector<int>,std::greater<int>>free;out.gate_for_input.assign(input.size(),-1);for(int index:order){while(!busy.empty()&&busy.top().first<=input[index].start){free.push(busy.top().second);busy.pop();}int gate;if(free.empty()){gate=(int)out.flights_by_gate.size();out.flights_by_gate.push_back({});}else{gate=free.top();free.pop();}out.gate_for_input[(std::size_t)index]=gate;out.flights_by_gate[(std::size_t)gate].push_back(input[index].id);busy.push({(long long)input[index].end+input[index].buffer,gate});}out.gate_count=(int)out.flights_by_gate.size();out.valid=true;return out;}
}
""",
        "multi_calendar_intersection": r"""#include "task.h"
#include <algorithm>
namespace curriculum {
CLASS::Slot CLASS::find(int open,int close,int duration,const std::vector<Calendar>& calendars){Slot out;if(open>close||duration<0)return out;for(const auto&cal:calendars){int prior=open;for(const auto&b:cal){if(b.start>=b.end||b.start<prior){return out;}prior=b.end;}}out.valid=true;if(duration==0){out.found=true;out.start=out.end=open;return out;}std::vector<std::size_t>cursor(calendars.size());long long candidate=open;while(candidate+duration<=close){bool moved=false;for(std::size_t c=0;c<calendars.size();++c){while(cursor[c]<calendars[c].size()&&calendars[c][cursor[c]].end<=candidate)++cursor[c];if(cursor[c]<calendars[c].size()){const auto&busy=calendars[c][cursor[c]];if(candidate<busy.end&&candidate+duration>busy.start){candidate=busy.end;moved=true;break;}}}if(!moved){out.found=true;out.start=(int)candidate;out.end=(int)candidate+duration;return out;}}return out;}
}
""",
        "union_complement": r"""#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum {
CLASS::Report CLASS::analyze(int left,int right,const std::vector<Closure>& input){Report out;if(left>right)return out;std::set<int>seen;std::vector<Segment>pieces;for(const auto&c:input){if(c.id<=0||c.left>=c.right||!seen.insert(c.id).second)return out;int a=std::max(left,c.left),b=std::min(right,c.right);if(a<b)pieces.push_back({a,b});}std::sort(pieces.begin(),pieces.end(),[](const Segment&a,const Segment&b){return a.left!=b.left?a.left<b.left:a.right<b.right;});for(const auto&p:pieces)if(out.closed.empty()||out.closed.back().right<p.left)out.closed.push_back(p);else out.closed.back().right=std::max(out.closed.back().right,p.right);int at=left;for(const auto&p:out.closed){if(at<p.left)out.open.push_back({at,p.left});at=p.right;}if(at<right)out.open.push_back({at,right});out.valid=true;return out;}
}
""",
        "k_coverage_sweep": r"""#include "task.h"
#include <map>
#include <set>
namespace curriculum {
CLASS::Coverage CLASS::measure(int k,const std::vector<Outage>& input){Coverage out;if(k<=0)return out;std::set<int>seen;std::map<int,int>delta;for(const auto&o:input){if(o.id<=0||o.start>=o.end||!seen.insert(o.id).second)return out;++delta[o.start];--delta[o.end];}int level=0;std::optional<int>opened;for(const auto&event:delta){int before=level;level+=event.second;if(before<k&&level>=k)opened=event.first;if(before>=k&&level<k&&opened){out.spans.push_back({*opened,event.first});out.duration+=(long long)event.first-*opened;opened.reset();}}out.valid=true;return out;}
}
""",
        "overlap_components_dsu": r"""#include "task.h"
#include <algorithm>
#include <map>
#include <numeric>
#include <set>
namespace curriculum {
CLASS::Components CLASS::group(const std::vector<Recording>& input){Components out;std::set<int>seen;for(const auto&r:input)if(r.id<=0||r.start>=r.end||!seen.insert(r.id).second)return out;std::vector<int>order(input.size());std::iota(order.begin(),order.end(),0);std::sort(order.begin(),order.end(),[&](int a,int b){return input[a].start!=input[b].start?input[a].start<input[b].start:input[a].id<input[b].id;});std::vector<int>parent(input.size());std::iota(parent.begin(),parent.end(),0);auto find=[&](int x){while(parent[(std::size_t)x]!=x){parent[(std::size_t)x]=parent[(std::size_t)parent[(std::size_t)x]];x=parent[(std::size_t)x];}return x;};std::vector<int>active;for(int index:order){active.erase(std::remove_if(active.begin(),active.end(),[&](int j){return input[j].end<=input[index].start;}),active.end());for(int j:active){int a=find(index),b=find(j);if(a!=b)parent[(std::size_t)a]=b;}active.push_back(index);}std::map<int,std::vector<int>>groups;for(std::size_t i=0;i<input.size();++i)groups[find((int)i)].push_back(input[i].id);for(auto&entry:groups){auto ids=entry.second;std::sort(ids.begin(),ids.end());out.groups.push_back(ids);}std::sort(out.groups.begin(),out.groups.end(),[](const auto&a,const auto&b){return a.front()<b.front();});out.valid=true;return out;}
}
""",
        "containment_stack": r"""#include "task.h"
#include <algorithm>
#include <numeric>
#include <set>
namespace curriculum {
CLASS::Forest CLASS::build(const std::vector<Session>& input){Forest out;std::set<int>seen;for(const auto&s:input)if(s.id<=0||s.start>=s.end||!seen.insert(s.id).second)return out;std::vector<int>order(input.size());std::iota(order.begin(),order.end(),0);std::sort(order.begin(),order.end(),[&](int a,int b){return input[a].start!=input[b].start?input[a].start<input[b].start:(input[a].end!=input[b].end?input[a].end>input[b].end:input[a].id<input[b].id);});out.parent_for_input.assign(input.size(),-1);std::vector<int>stack;for(int index:order){while(!stack.empty()&&input[stack.back()].end<=input[index].start)stack.pop_back();if(!stack.empty()){const auto&p=input[stack.back()];const auto&c=input[index];if(c.end>p.end||(c.start==p.start&&c.end==p.end))return {};out.parent_for_input[(std::size_t)index]=p.id;}else out.roots.push_back(input[index].id);stack.push_back(index);}out.valid=true;return out;}
}
""",
        "travel_dag_longest_path": r"""#include "task.h"
#include <algorithm>
#include <numeric>
#include <set>
namespace curriculum {
CLASS::Chain CLASS::choose(const std::vector<Patrol>& input,const std::vector<std::vector<int>>& travel){Chain out;const std::size_t zones=travel.size();for(const auto&row:travel){if(row.size()!=zones)return out;for(int value:row)if(value<0)return out;}std::set<int>seen;for(const auto&p:input)if(p.id<=0||p.zone<0||(std::size_t)p.zone>=zones||p.start>=p.end||p.score<0||!seen.insert(p.id).second)return out;std::vector<int>order(input.size());std::iota(order.begin(),order.end(),0);std::sort(order.begin(),order.end(),[&](int a,int b){return input[a].start!=input[b].start?input[a].start<input[b].start:input[a].id<input[b].id;});struct State{int score=0;std::vector<int>ids;};auto better=[](const State&a,const State&b){return a.score!=b.score?a.score>b.score:std::lexicographical_compare(a.ids.begin(),a.ids.end(),b.ids.begin(),b.ids.end());};std::vector<State>dp(input.size());State best;for(std::size_t oi=0;oi<order.size();++oi){int i=order[oi];dp[(std::size_t)i]={input[i].score,{input[i].id}};for(std::size_t oj=0;oj<oi;++oj){int j=order[oj];if((long long)input[j].end+travel[(std::size_t)input[j].zone][(std::size_t)input[i].zone]<=input[i].start){State next=dp[(std::size_t)j];next.score+=input[i].score;next.ids.push_back(input[i].id);if(better(next,dp[(std::size_t)i]))dp[(std::size_t)i]=next;}}if(better(dp[(std::size_t)i],best))best=dp[(std::size_t)i];}out.valid=true;out.score=best.score;out.ids=best.ids;return out;}
}
""",
        "cyclic_interval_normalization": r"""#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum {
CLASS::Normalized CLASS::normalize(int period,const std::vector<Lease>& input){Normalized out;if(period<=0)return out;std::set<int>seen;std::vector<Arc>pieces;for(const auto&x:input){if(x.id<=0||x.start<0||x.start>=period||x.end<0||x.end>=period||!seen.insert(x.id).second)return out;if(x.start==x.end)pieces.push_back({0,period});else if(x.start<x.end)pieces.push_back({x.start,x.end});else{pieces.push_back({x.start,period});pieces.push_back({0,x.end});}}std::sort(pieces.begin(),pieces.end(),[](const Arc&a,const Arc&b){return a.start!=b.start?a.start<b.start:a.end<b.end;});std::vector<Arc>merged;for(const auto&p:pieces)if(merged.empty()||merged.back().end<p.start)merged.push_back(p);else merged.back().end=std::max(merged.back().end,p.end);for(const auto&a:merged)out.covered+=a.end-a.start;if(out.covered==period)out.arcs.push_back({0,0});else if(merged.size()>=2&&merged.front().start==0&&merged.back().end==period){out.arcs.push_back({merged.back().start,merged.front().end});for(std::size_t i=1;i+1<merged.size();++i)out.arcs.push_back(merged[i]);}else out.arcs=merged;out.valid=true;return out;}
}
""",
        "bipartite_augmenting_match": r"""#include "task.h"
#include <algorithm>
#include <functional>
#include <map>
#include <set>
namespace curriculum {
CLASS::Match CLASS::assign(const std::vector<Incident>& incidents,const std::vector<Team>& teams){Match out;std::set<int>ids;for(const auto&i:incidents)if(i.id<=0||i.start>=i.end||i.skill<0||!ids.insert(i.id).second)return out;ids.clear();for(const auto&t:teams)if(t.id<=0||t.available_start>t.available_end||t.skill<0||!ids.insert(t.id).second)return out;std::vector<int>io(incidents.size()),to(teams.size());for(std::size_t i=0;i<io.size();++i)io[i]=(int)i;for(std::size_t i=0;i<to.size();++i)to[i]=(int)i;std::sort(io.begin(),io.end(),[&](int a,int b){return incidents[a].id<incidents[b].id;});std::sort(to.begin(),to.end(),[&](int a,int b){return teams[a].id<teams[b].id;});std::vector<int>team_match(teams.size(),-1);std::function<bool(int,std::vector<bool>&)>augment=[&](int ii,std::vector<bool>&seen){for(int ti:to){const auto&i=incidents[ii];const auto&t=teams[ti];if(seen[(std::size_t)ti]||t.skill<i.skill||t.available_start>i.start||t.available_end<i.end)continue;seen[(std::size_t)ti]=true;if(team_match[(std::size_t)ti]<0||augment(team_match[(std::size_t)ti],seen)){team_match[(std::size_t)ti]=ii;return true;}}return false;};for(int ii:io){std::vector<bool>seen_team(teams.size());augment(ii,seen_team);}std::map<int,int>by_incident;for(std::size_t ti=0;ti<team_match.size();++ti)if(team_match[ti]>=0)by_incident[incidents[(std::size_t)team_match[ti]].id]=teams[ti].id;for(int ii:io){auto found=by_incident.find(incidents[ii].id);if(found==by_incident.end())out.unmatched_incidents.push_back(incidents[ii].id);else out.pairs.push_back({found->first,found->second});}out.valid=true;return out;}
}
""",
        "bitmask_set_cover": r"""#include "task.h"
#include <algorithm>
#include <cstdint>
#include <limits>
#include <set>
namespace curriculum {
CLASS::Cover CLASS::choose(const std::vector<int>& raw_points,const std::vector<Window>& windows){Cover out;std::vector<int>points=raw_points;std::sort(points.begin(),points.end());points.erase(std::unique(points.begin(),points.end()),points.end());if(points.size()>20)return out;std::set<int>seen;for(const auto&w:windows)if(w.id<=0||w.start>w.end||!seen.insert(w.id).second)return out;out.valid=true;if(points.empty()){out.possible=true;return out;}const std::uint32_t full_mask=(1U<<points.size())-1U;struct State{bool set=false;std::vector<int>ids;};std::vector<State>dp((std::size_t)full_mask+1);dp[0].set=true;auto better=[](const State&a,const State&b){if(!a.set)return false;if(!b.set)return true;if(a.ids.size()!=b.ids.size())return a.ids.size()<b.ids.size();return std::lexicographical_compare(a.ids.begin(),a.ids.end(),b.ids.begin(),b.ids.end());};for(const auto&w:windows){std::uint32_t cover=0;for(std::size_t i=0;i<points.size();++i)if(w.start<=points[i]&&points[i]<=w.end)cover|=(1U<<i);auto next=dp;for(std::uint32_t mask=0;mask<=full_mask;++mask)if(dp[mask].set){State candidate=dp[mask];candidate.ids.push_back(w.id);std::sort(candidate.ids.begin(),candidate.ids.end());auto target=mask|cover;if(better(candidate,next[target]))next[target]=candidate;}dp.swap(next);}if(dp[full_mask].set){out.possible=true;out.ids=dp[full_mask].ids;}return out;}
}
""",
    }
)
