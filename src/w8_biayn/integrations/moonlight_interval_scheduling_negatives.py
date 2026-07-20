"""Executable false substitutes and independent discriminators for interval v2."""

from __future__ import annotations


def _oracle(body: str) -> str:
    return f"""#include "task.h"\n#include <algorithm>\n#include <cstdlib>\n#include <vector>\nusing namespace curriculum;\nstatic void check(bool ok){{if(!ok)std::abort();}}\nint main(){{{body}}}\n"""


NEGATIVES = {
    "weighted_interval_dp": r"""#include "task.h"
#include <algorithm>
namespace curriculum { CLASS::Plan CLASS::choose(const std::vector<Surgery>& input){auto jobs=input;std::sort(jobs.begin(),jobs.end(),[](const auto&a,const auto&b){return a.end+a.cleanup<b.end+b.cleanup;});Plan out;out.valid=true;long long ready=-(1LL<<60);for(const auto&x:jobs)if(x.start>=ready){out.ids.push_back(x.id);out.total_value+=x.value;ready=(long long)x.end+x.cleanup;}return out;} }
""",
    "greedy_target_cover": r"""#include "task.h"
#include <algorithm>
namespace curriculum { CLASS::Cover CLASS::cover(int left,int right,const std::vector<Window>& windows){Cover out;out.valid=true;int at=left;while(at<right){const Window*pick=nullptr;for(const auto&w:windows)if(w.left<=at&&at<w.right&&(!pick||w.right-w.left<pick->right-pick->left||(w.right-w.left==pick->right-pick->left&&w.id<pick->id)))pick=&w;if(!pick)return out;out.ids.push_back(pick->id);at=pick->right;}out.possible=true;return out;} }
""",
    "minimum_stabbing": r"""#include "task.h"
#include <algorithm>
namespace curriculum { CLASS::BreakPlan CLASS::place(const std::vector<Program>& input){BreakPlan out;out.valid=true;auto xs=input;std::sort(xs.begin(),xs.end(),[](const auto&a,const auto&b){return a.start<b.start;});for(const auto&x:xs){int p=x.start+(x.end-x.start)/2;if(out.points.empty()||out.points.back()<x.start||out.points.back()>x.end)out.points.push_back(p);}return out;} }
""",
    "moore_hodgson": r"""#include "task.h"
#include <algorithm>
namespace curriculum { CLASS::Schedule CLASS::maximize_count(const std::vector<Job>& input){Schedule out;out.valid=true;auto jobs=input;std::sort(jobs.begin(),jobs.end(),[](const auto&a,const auto&b){return a.deadline!=b.deadline?a.deadline<b.deadline:a.id<b.id;});for(const auto&x:jobs)out.kept_ids.push_back(x.id);return out;} }
""",
    "edf_max_lateness": r"""#include "task.h"
#include <algorithm>
namespace curriculum { CLASS::Docket CLASS::order(const std::vector<Hearing>& input){Docket out;out.valid=true;long long t=0;out.max_lateness=-(1LL<<60);for(const auto&x:input){t+=x.duration;out.ids.push_back(x.id);out.completion.push_back(t);out.max_lateness=std::max(out.max_lateness,t-x.due);}if(input.empty())out.max_lateness=0;return out;} }
""",
    "capacity_eviction_sweep": r"""#include "task.h"
#include <algorithm>
#include <vector>
namespace curriculum { CLASS::Admission CLASS::admit(int plugs,const std::vector<Session>& input){Admission out;if(plugs<0)return out;out.valid=true;auto xs=input;std::sort(xs.begin(),xs.end(),[](const auto&a,const auto&b){return a.start!=b.start?a.start<b.start:a.id<b.id;});std::vector<int>ends;for(const auto&x:xs){ends.erase(std::remove_if(ends.begin(),ends.end(),[&](int e){return e<=x.start;}),ends.end());if((int)ends.size()<plugs){ends.push_back(x.end);out.admitted_ids.push_back(x.id);}else out.rejected_ids.push_back(x.id);}std::sort(out.admitted_ids.begin(),out.admitted_ids.end());std::sort(out.rejected_ids.begin(),out.rejected_ids.end());return out;} }
""",
    "ordered_mutable_calendar": r"""#include "task.h"
namespace curriculum { bool CLASS::conflict(int,int,int)const{return false;} bool CLASS::book(Booking b){auto key=std::make_pair(b.start,b.id);by_start_[key]=b;starts_by_id_[b.id]=key;return true;} bool CLASS::cancel(int id){auto it=starts_by_id_.find(id);if(it==starts_by_id_.end())return false;by_start_.erase(it->second);starts_by_id_.erase(it);return true;} bool CLASS::reschedule(int id,int start,int end){if(!cancel(id))return false;return book({id,start,end});} std::vector<int> CLASS::agenda()const{std::vector<int>out;for(const auto&x:by_start_)out.push_back(x.second.id);return out;} }
""",
    "peak_overlap_sweep": r"""#include "task.h"
namespace curriculum { CLASS::Peak CLASS::inspect(const std::vector<Freight>& input){Peak out;out.valid=true;if(!input.empty()){out.count=input.size()==1?1:2;out.first_time=input.front().start;for(std::size_t i=0;i<(std::size_t)out.count;++i)out.ids.push_back(input[i].id);}return out;} }
""",
    "budgeted_interval_dp": r"""#include "task.h"
#include <algorithm>
namespace curriculum { CLASS::Plan CLASS::choose(int budget,const std::vector<Campaign>& input){Plan out;if(budget<0)return out;out.valid=true;for(const auto&x:input)if(out.total_spend+x.spend<=budget){out.total_spend+=x.spend;out.total_value+=x.value;out.ids.push_back(x.id);}std::sort(out.ids.begin(),out.ids.end());return out;} }
""",
    "minimum_cost_cover_dag": r"""#include "task.h"
namespace curriculum { CLASS::Cover CLASS::cover(int left,int right,const std::vector<Shift>& input){Cover out;out.valid=true;int at=left;while(at<right){const Shift*best=nullptr;for(const auto&x:input)if(x.start<=at&&x.end>at&&(!best||x.end>best->end))best=&x;if(!best)return out;out.ids.push_back(best->id);out.cost+=best->cost;at=best->end;}out.possible=true;return out;} }
""",
    "interval_partition_heap": r"""#include "task.h"
namespace curriculum { CLASS::Assignment CLASS::assign(const std::vector<Flight>& input){Assignment out;out.valid=true;out.gate_count=(int)input.size();out.gate_for_input.resize(input.size());for(std::size_t i=0;i<input.size();++i){out.gate_for_input[i]=(int)i;out.flights_by_gate.push_back({input[i].id});}return out;} }
""",
    "multi_calendar_intersection": r"""#include "task.h"
namespace curriculum { CLASS::Slot CLASS::find(int open,int close,int duration,const std::vector<Calendar>& calendars){Slot out;out.valid=true;int at=open;if(!calendars.empty())for(const auto&b:calendars.front())if(at+duration>b.start&&at<b.end)at=b.end;if(at+duration<=close){out.found=true;out.start=at;out.end=at+duration;}return out;} }
""",
    "union_complement": r"""#include "task.h"
#include <algorithm>
namespace curriculum { CLASS::Report CLASS::analyze(int left,int right,const std::vector<Closure>& input){Report out;if(left>right)return out;out.valid=true;for(const auto&x:input){int a=std::max(left,x.left),b=std::min(right,x.right);if(a<b){if(!out.closed.empty()&&out.closed.back().right==a)out.closed.back().right=b;else out.closed.push_back({a,b});}}int at=left;for(const auto&x:out.closed){if(at<x.left)out.open.push_back({at,x.left});at=x.right;}if(at<right)out.open.push_back({at,right});return out;} }
""",
    "k_coverage_sweep": r"""#include "task.h"
#include <algorithm>
namespace curriculum { CLASS::Coverage CLASS::measure(int,const std::vector<Outage>& input){Coverage out;out.valid=true;std::vector<Span> xs;for(const auto&x:input)xs.push_back({x.start,x.end});std::sort(xs.begin(),xs.end(),[](const auto&a,const auto&b){return a.start<b.start;});for(const auto&x:xs)if(out.spans.empty()||out.spans.back().end<x.start)out.spans.push_back(x);else out.spans.back().end=std::max(out.spans.back().end,x.end);for(const auto&x:out.spans)out.duration+=x.end-x.start;return out;} }
""",
    "overlap_components_dsu": r"""#include "task.h"
#include <algorithm>
namespace curriculum { CLASS::Components CLASS::group(const std::vector<Recording>& input){Components out;out.valid=true;for(std::size_t i=0;i<input.size();++i){std::vector<int>g{input[i].id};for(std::size_t j=i+1;j<input.size();++j)if(input[i].start<input[j].end&&input[j].start<input[i].end)g.push_back(input[j].id);std::sort(g.begin(),g.end());out.groups.push_back(g);}return out;} }
""",
    "containment_stack": r"""#include "task.h"
namespace curriculum { CLASS::Forest CLASS::build(const std::vector<Session>& input){Forest out;out.valid=true;out.parent_for_input.assign(input.size(),-1);if(input.empty())return out;out.roots.push_back(input.front().id);for(std::size_t i=1;i<input.size();++i)out.parent_for_input[i]=input.front().id;return out;} }
""",
    "travel_dag_longest_path": r"""#include "task.h"
#include <algorithm>
namespace curriculum { CLASS::Chain CLASS::choose(const std::vector<Patrol>& input,const std::vector<std::vector<int>>&){Chain out;out.valid=true;auto xs=input;std::sort(xs.begin(),xs.end(),[](const auto&a,const auto&b){return a.start<b.start;});int end=-(1<<30);for(const auto&x:xs)if(x.start>=end){out.ids.push_back(x.id);out.score+=x.score;end=x.end;}return out;} }
""",
    "cyclic_interval_normalization": r"""#include "task.h"
namespace curriculum { CLASS::Normalized CLASS::normalize(int period,const std::vector<Lease>& input){Normalized out;if(period<=0)return out;out.valid=true;for(const auto&x:input){if(x.start>x.end)return {};out.arcs.push_back({x.start,x.end});out.covered+=x.end-x.start;}return out;} }
""",
    "bipartite_augmenting_match": r"""#include "task.h"
#include <vector>
namespace curriculum { CLASS::Match CLASS::assign(const std::vector<Incident>& incidents,const std::vector<Team>& teams){Match out;out.valid=true;std::vector<bool>used(teams.size());for(const auto&i:incidents){bool found=false;for(std::size_t t=0;t<teams.size();++t)if(!used[t]&&teams[t].skill>=i.skill&&teams[t].available_start<=i.start&&teams[t].available_end>=i.end){used[t]=true;out.pairs.push_back({i.id,teams[t].id});found=true;break;}if(!found)out.unmatched_incidents.push_back(i.id);}return out;} }
""",
    "bitmask_set_cover": r"""#include "task.h"
#include <algorithm>
#include <set>
namespace curriculum { CLASS::Cover CLASS::choose(const std::vector<int>& points,const std::vector<Window>& windows){Cover out;out.valid=true;std::set<int>missing(points.begin(),points.end());std::vector<bool>used(windows.size());while(!missing.empty()){std::size_t best=windows.size(),count=0;for(std::size_t i=0;i<windows.size();++i)if(!used[i]){std::size_t c=0;for(int p:missing)if(windows[i].start<=p&&p<=windows[i].end)++c;if(c>count){count=c;best=i;}}if(best==windows.size()||count==0)return out;used[best]=true;out.ids.push_back(windows[best].id);for(auto it=missing.begin();it!=missing.end();)if(windows[best].start<=*it&&*it<=windows[best].end)it=missing.erase(it);else ++it;}std::sort(out.ids.begin(),out.ids.end());out.possible=true;return out;} }
""",
}


DIVERSITY_PROFILES = {
    "weighted_interval_dp": (
        "predecessor-indexed value table",
        "take-or-skip value maximization",
        "cleanup-adjusted half-open compatibility",
        "weighted-greedy-trap",
    ),
    "greedy_target_cover": (
        "monotone covered-coordinate frontier",
        "eligible farthest-reach choice",
        "target-empty versus uncovered distinction",
        "shortest-window-trap",
    ),
    "minimum_stabbing": (
        "last chosen closed-interval point",
        "ascending-right-endpoint placement",
        "zero-length closed interval admission",
        "midpoint-trap",
    ),
    "moore_hodgson": (
        "deadline prefix plus max-duration heap",
        "evict longest overloaded job",
        "positive-duration deadline feasibility",
        "edf-no-eviction-trap",
    ),
    "edf_max_lateness": (
        "completion prefix sequence",
        "due-time stable ordering",
        "signed lateness on empty/all-job schedule",
        "input-order-trap",
    ),
    "capacity_eviction_sweep": (
        "active priority set at event time",
        "lowest-priority overload eviction",
        "end-before-start plug release",
        "first-come-trap",
    ),
    "ordered_mutable_calendar": (
        "dual start/id ordered indexes",
        "atomic book-cancel-reschedule",
        "failed-reschedule rollback and touching",
        "unchecked-ledger-trace",
    ),
    "peak_overlap_sweep": (
        "active witness id set",
        "earliest maximum occupancy snapshot",
        "half-open end-before-start events",
        "pair-count-trap",
    ),
    "budgeted_interval_dp": (
        "budget-by-predecessor state grid",
        "value-spend-lexicographic optimization",
        "nonnegative spend and budget",
        "budget-only-trap",
    ),
    "minimum_cost_cover_dag": (
        "coordinate reachability cost states",
        "cost-count-id path minimization",
        "gap-impossible versus invalid bounds",
        "farthest-reach-trap",
    ),
    "interval_partition_heap": (
        "busy and reusable gate heaps",
        "lowest released gate reuse",
        "buffered release boundary",
        "new-gate-trap",
    ),
    "multi_calendar_intersection": (
        "one monotone cursor per calendar",
        "advance past first blocking calendar",
        "sorted disjoint calendars and zero duration",
        "single-calendar-trap",
    ),
    "union_complement": (
        "canonical clipped merged segments",
        "merge then complement",
        "outside clipping and touching closure",
        "nontransitive-merge-trap",
    ),
    "k_coverage_sweep": (
        "coverage-level delta map",
        "open/close maximal k-level spans",
        "positive k half-open deltas",
        "plain-union-trap",
    ),
    "overlap_components_dsu": (
        "active sweep plus disjoint-set parents",
        "union every live overlap edge",
        "touching non-edge and transitive closure",
        "direct-neighbor-trap",
    ),
    "containment_stack": (
        "nested immediate-parent stack",
        "nearest strict container assignment",
        "crossing and identical batch rejection",
        "root-parent-trap",
    ),
    "travel_dag_longest_path": (
        "per-patrol directed predecessor states",
        "score then lexicographic chain DP",
        "square nonnegative asymmetric travel matrix",
        "zero-travel-trap",
    ),
    "cyclic_interval_normalization": (
        "split linear arc pieces plus boundary rejoin",
        "merge and wrap canonical arcs",
        "equal endpoints full-cycle semantics",
        "reject-wrap-trap",
    ),
    "bipartite_augmenting_match": (
        "team-to-incident match graph",
        "recursive augmenting rematch",
        "full-window and skill compatibility",
        "one-pass-match-trap",
    ),
    "bitmask_set_cover": (
        "checkpoint coverage masks",
        "cardinality then id-list subset DP",
        "closed endpoints and twenty-point cap",
        "most-points-greedy-trap",
    ),
}


ORACLE_TESTS = {
    "weighted_interval_dp": _oracle(
        "auto x=CLASS::choose({{1,0,2,1,0},{2,1,3,10,0}});check(x.valid&&x.total_value==10&&x.ids==std::vector<int>({2}));"
    ),
    "greedy_target_cover": _oracle(
        "auto x=CLASS::cover(0,9,{{1,0,4},{2,2,7},{3,4,9}});check(x.valid&&x.possible&&x.ids==std::vector<int>({1,3}));"
    ),
    "minimum_stabbing": _oracle(
        "auto x=CLASS::place({{1,0,10},{2,2,2},{3,2,5},{4,8,9}});check(x.valid&&x.points==std::vector<int>({2,9}));"
    ),
    "moore_hodgson": _oracle(
        "auto x=CLASS::maximize_count({{1,4,3},{2,2,4},{3,2,6}});check(x.valid&&x.kept_ids==std::vector<int>({2,3}));"
    ),
    "edf_max_lateness": _oracle(
        "auto x=CLASS::order({{1,3,8},{2,2,4},{3,1,4}});check(x.valid&&x.ids==std::vector<int>({2,3,1})&&x.max_lateness==-1);"
    ),
    "capacity_eviction_sweep": _oracle(
        "auto x=CLASS::admit(1,{{1,0,5,2},{2,1,4,9}});check(x.valid&&x.admitted_ids==std::vector<int>({2}));"
    ),
    "ordered_mutable_calendar": _oracle(
        "CLASS x;std::vector<CLASS::Booking> model;auto agenda=[&](){auto copy=model;std::sort(copy.begin(),copy.end(),[](const auto&a,const auto&b){return a.start!=b.start?a.start<b.start:a.id<b.id;});std::vector<int>ids;for(const auto&b:copy)ids.push_back(b.id);return ids;};auto book=[&](CLASS::Booking b){if(b.id<=0||b.start>=b.end)return false;for(const auto&e:model)if(e.id==b.id||(b.start<e.end&&e.start<b.end))return false;model.push_back(b);return true;};check(x.book({1,1,3})==book({1,1,3}));check(x.agenda()==agenda());check(x.book({2,3,5})==book({2,3,5}));check(x.agenda()==agenda());check(x.book({3,2,4})==book({3,2,4}));check(x.agenda()==agenda());check(!x.reschedule(1,4,6));check(x.agenda()==agenda());check(x.cancel(2));model.erase(std::remove_if(model.begin(),model.end(),[](const auto&b){return b.id==2;}),model.end());check(x.agenda()==agenda());check(x.reschedule(1,5,7));model[0]={1,5,7};check(x.agenda()==agenda());check(!x.cancel(99));check(x.agenda()==agenda());"
    ),
    "peak_overlap_sweep": _oracle(
        "auto x=CLASS::inspect({{1,0,4},{2,2,5},{3,3,6}});check(x.valid&&x.count==3&&x.first_time==3&&x.ids==std::vector<int>({1,2,3}));"
    ),
    "budgeted_interval_dp": _oracle(
        "auto x=CLASS::choose(2,{{1,0,4,1,4},{2,1,3,1,4}});check(x.valid&&x.total_value==4&&x.ids==std::vector<int>({1}));"
    ),
    "minimum_cost_cover_dag": _oracle(
        "auto x=CLASS::cover(0,4,{{1,0,4,9},{2,0,2,2},{3,2,4,2}});check(x.valid&&x.possible&&x.cost==4&&x.ids==std::vector<int>({2,3}));"
    ),
    "interval_partition_heap": _oracle(
        "auto x=CLASS::assign({{1,0,3,0},{2,3,5,0},{3,2,4,0}});check(x.valid&&x.gate_count==2&&x.gate_for_input==std::vector<int>({0,0,1}));"
    ),
    "multi_calendar_intersection": _oracle(
        "auto x=CLASS::find(0,10,2,{{{0,2}},{{2,4}}});check(x.valid&&x.found&&x.start==4);"
    ),
    "union_complement": _oracle(
        "auto x=CLASS::analyze(0,10,{{1,1,4},{2,3,6}});check(x.valid&&x.closed.size()==1&&x.closed[0].left==1&&x.closed[0].right==6);"
    ),
    "k_coverage_sweep": _oracle(
        "auto x=CLASS::measure(2,{{1,0,4},{2,2,6},{3,3,5}});check(x.valid&&x.duration==3&&x.spans.size()==1&&x.spans[0].start==2&&x.spans[0].end==5);"
    ),
    "overlap_components_dsu": _oracle(
        "auto x=CLASS::group({{1,0,3},{2,2,5},{3,4,6},{4,8,9}});check(x.valid&&x.groups==std::vector<std::vector<int>>({{1,2,3},{4}}));"
    ),
    "containment_stack": _oracle(
        "auto x=CLASS::build({{1,0,10},{2,1,4},{3,2,3}});check(x.valid&&x.parent_for_input==std::vector<int>({-1,1,2}));"
    ),
    "travel_dag_longest_path": _oracle(
        "auto x=CLASS::choose({{1,0,0,2,4},{2,1,3,5,8},{3,0,5,6,3}},{{0,1},{5,0}});check(x.valid&&x.score==12&&x.ids==std::vector<int>({1,2}));"
    ),
    "cyclic_interval_normalization": _oracle(
        "auto x=CLASS::normalize(10,{{1,8,2},{2,1,4}});check(x.valid&&x.covered==6&&x.arcs.size()==1&&x.arcs[0].start==8&&x.arcs[0].end==4);"
    ),
    "bipartite_augmenting_match": _oracle(
        "auto x=CLASS::assign({{1,0,4,1},{2,1,3,2}},{{1,0,4,2},{2,0,4,1}});check(x.valid&&x.pairs.size()==2&&x.unmatched_incidents.empty());"
    ),
    "bitmask_set_cover": _oracle(
        "auto x=CLASS::choose({1,2,3,4,5,6},{{1,2,5},{2,1,3},{3,4,6}});check(x.valid&&x.possible&&x.ids==std::vector<int>({2,3}));"
    ),
}
