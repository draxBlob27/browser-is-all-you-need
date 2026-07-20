"""Task-specific C++ contracts for the robot-simulation v2 family."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RobotCase:
    legacy_id: str
    task_id: str
    title: str
    profile: str
    objective: str
    public_api: str
    marker: str
    instructions: str
    header: str
    starter: str
    reference: str
    visible_test: str
    hidden_test: str
    visible_description: str = "ordinary behavior and one public boundary"
    hidden_description: str = "task-specific adversarial, atomicity, and tie cases"


def _starter(class_name: str) -> str:
    return f'#include "task.h"\nnamespace curriculum {{ /* Implement every declared {class_name} operation. */ }}\n'


CASES = (
RobotCase(
"sim-warehouse-picker","warehouse-wave-router","Warehouse Wave Router","directed-bfs-capacity-waves",
"Plan capacity-bounded shelf-picking waves over a directed aisle graph.",
"WarehouseWaveRouter(graph).route_wave(start,shelves,capacity)->WavePlan","std::queue<int>",
r"""# Instructions

Implement `WarehouseWaveRouter` for a directed aisle graph. Vertices are numbered by
index and vertex 0 is the unload depot. `route_wave` starts at `start`, visits each
requested shelf in order using a shortest directed path, and returns to depot whenever
`capacity` picks have been accumulated and after the final partial wave. BFS ties use
smaller neighboring vertex IDs. An unreachable shelf is appended to `unreachable`
without changing the current vertex or consuming capacity. Duplicate requests are
separate picks. Invalid vertices and non-positive capacity throw `std::invalid_argument`.
`route` includes the start and every traversed vertex; `batches` counts depot returns.
""",
r"""#pragma once
#include <vector>
namespace curriculum {
struct WavePlan { std::vector<int> route; int batches=0; std::vector<int> unreachable; };
class WarehouseWaveRouter { std::vector<std::vector<int>> graph_; public:
 explicit WarehouseWaveRouter(std::vector<std::vector<int>> graph);
 WavePlan route_wave(int start,const std::vector<int>& shelves,int capacity) const;
}; }
""",_starter("WarehouseWaveRouter"),
r"""#include "task.h"
#include <algorithm>
#include <queue>
#include <stdexcept>
namespace curriculum {
WarehouseWaveRouter::WarehouseWaveRouter(std::vector<std::vector<int>> g):graph_(std::move(g)){
 for(auto& row:graph_){for(int v:row)if(v<0||v>=static_cast<int>(graph_.size()))throw std::invalid_argument("edge");std::sort(row.begin(),row.end());}
}
WavePlan WarehouseWaveRouter::route_wave(int start,const std::vector<int>& shelves,int capacity)const{
 if(start<0||start>=static_cast<int>(graph_.size())||capacity<=0)throw std::invalid_argument("input");
 WavePlan out;out.route.push_back(start);int at=start,load=0;
 auto path=[&](int s,int goal){std::vector<int> prev(graph_.size(),-1);std::queue<int> q;q.push(s);prev[s]=s;
  while(!q.empty()){int u=q.front();q.pop();for(int v:graph_[u])if(prev[v]<0){prev[v]=u;q.push(v);}}
  std::vector<int> p;if(goal<0||goal>=static_cast<int>(graph_.size())||prev[goal]<0)return p;
  for(int v=goal;v!=s;v=prev[v]){p.push_back(v);}std::reverse(p.begin(),p.end());return p;};
 for(int shelf:shelves){auto p=path(at,shelf);if(shelf!=at&&p.empty()){out.unreachable.push_back(shelf);continue;}
  out.route.insert(out.route.end(),p.begin(),p.end());at=shelf;++load;
  if(load==capacity){auto home=path(at,0);if(home.empty()&&at!=0){out.unreachable.push_back(shelf);break;}out.route.insert(out.route.end(),home.begin(),home.end());at=0;load=0;++out.batches;}}
 if(load){auto home=path(at,0);if(!home.empty()||at==0){out.route.insert(out.route.end(),home.begin(),home.end());++out.batches;}}
 return out;
}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;WarehouseWaveRouter r({{1,2},{0,3},{3},{0}});auto p=r.route_wave(0,{3,2},1);return p.batches==2&&p.unreachable.empty()&&p.route.front()==0&&p.route.back()==0?0:1;}
""",
r"""#include "task.h"
#include <stdexcept>
int main(){using namespace curriculum;int f=0;WarehouseWaveRouter r({{1},{0},{}});auto p=r.route_wave(0,{1,2,1},2);f+=!(p.batches==1&&p.unreachable==std::vector<int>{2});try{r.route_wave(0,{},0);++f;}catch(const std::invalid_argument&){}return f;}
"""),
RobotCase(
"sim-greenhouse-cart","greenhouse-moisture-controller","Greenhouse Moisture Controller","event-decay-longest-dry-run",
"Advance evaporation and locate the longest contiguous dry greenhouse run.",
"GreenhouseMoistureController(moisture,threshold); tick; water; next_dry_run; snapshot","length>best.length",
r"""# Instructions

Each plot has moisture in [0,100]. `tick(e)` subtracts non-negative `e` from
every plot, clamping at zero. `water(i,u)` adds positive units to a valid plot,
clamping at 100, and returns false without mutation otherwise. `next_dry_run`
returns the longest contiguous run whose moisture is strictly below the constructor
threshold; ties choose the smaller begin index and no dry plots produce length zero.
The snapshot includes all moisture values and the number of successful ticks.
""",
r"""#pragma once
#include <cstddef>
#include <vector>
namespace curriculum {
struct DryRun{std::size_t begin=0,length=0;};
struct MoistureSnapshot{std::vector<int> moisture;int ticks=0;};
class GreenhouseMoistureController{std::vector<int> moisture_;int threshold_,ticks_=0;public:
 GreenhouseMoistureController(std::vector<int>,int);
 void tick(int evaporation);bool water(std::size_t plot,int units);
 DryRun next_dry_run()const;MoistureSnapshot snapshot()const;
};}
""",_starter("GreenhouseMoistureController"),
r"""#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {
GreenhouseMoistureController::GreenhouseMoistureController(std::vector<int> m,int t):moisture_(std::move(m)),threshold_(t){
 if(t<0||t>100)throw std::invalid_argument("threshold");for(int v:moisture_)if(v<0||v>100)throw std::invalid_argument("moisture");}
void GreenhouseMoistureController::tick(int e){if(e<0)throw std::invalid_argument("evaporation");for(int& v:moisture_)v=std::max(0,v-e);++ticks_;}
bool GreenhouseMoistureController::water(std::size_t i,int u){if(i>=moisture_.size()||u<=0)return false;moisture_[i]=std::min(100,moisture_[i]+u);return true;}
DryRun GreenhouseMoistureController::next_dry_run()const{DryRun best;std::size_t begin=0,length=0;
 for(std::size_t i=0;i<=moisture_.size();++i){if(i<moisture_.size()&&moisture_[i]<threshold_){if(!length)begin=i;++length;}else{if(length>best.length)best={begin,length};length=0;}}return best;}
MoistureSnapshot GreenhouseMoistureController::snapshot()const{return{moisture_,ticks_};}
}
""",
r"""#include "task.h"
int main(){using namespace curriculum;GreenhouseMoistureController c({40,15,10,60,5},20);auto d=c.next_dry_run();c.tick(10);return d.begin==1&&d.length==2&&c.snapshot().ticks==1?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;GreenhouseMoistureController c({5,40,5,40},20);auto d=c.next_dry_run();f+=!(d.begin==0&&d.length==1);f+=!c.water(0,200);f+=c.snapshot().moisture[0]!=100;auto before=c.snapshot();f+=c.water(99,2);f+=before.moisture!=c.snapshot().moisture;return f;}
"""),
RobotCase(
"sim-drone-delivery","drone-altitude-pathfinder","Drone Altitude Pathfinder","layered-battery-state-dijkstra",
"Find a least-energy route through layered airspace with recharge pads.",
"DroneAltitudePathfinder(layers,rows,cols,no_fly,chargers).shortest_flight","priority_queue<Node",
r"""# Instructions

Cells are `{layer,row,col}`. Horizontal moves cost one battery unit and vertical
moves cost two. No-fly cells cannot be entered. A charger restores the battery to
the initial capacity immediately on arrival. `shortest_flight` minimizes total
energy spent; ties are deterministic by encoded cell/state order. It searches
cell-plus-remaining-battery states, returns both endpoints in `path`, and reports
unreachable without a path. Invalid dimensions, cells, or negative battery throw.
""",
r"""#pragma once
#include <vector>
namespace curriculum {
struct AirCell{int layer=0,row=0,col=0;bool operator==(const AirCell& o)const{return layer==o.layer&&row==o.row&&col==o.col;}};
struct Flight{bool reachable=false;int energy=0,recharges=0;std::vector<AirCell> path;};
class DroneAltitudePathfinder{int l_,r_,c_;std::vector<int> blocked_,chargers_;public:
 DroneAltitudePathfinder(int,int,int,std::vector<AirCell>,std::vector<AirCell>);
 Flight shortest_flight(AirCell start,AirCell goal,int battery)const;
};}
""",_starter("DroneAltitudePathfinder"),
r"""#include "task.h"
#include <algorithm>
#include <limits>
#include <queue>
#include <stdexcept>
namespace curriculum {
DroneAltitudePathfinder::DroneAltitudePathfinder(int l,int r,int c,std::vector<AirCell>b,std::vector<AirCell>p):l_(l),r_(r),c_(c){
 if(l<=0||r<=0||c<=0)throw std::invalid_argument("dimensions");auto enc=[&](AirCell x){if(x.layer<0||x.layer>=l_||x.row<0||x.row>=r_||x.col<0||x.col>=c_)throw std::invalid_argument("cell");return(x.layer*r_+x.row)*c_+x.col;};
 for(auto x:b)blocked_.push_back(enc(x));for(auto x:p)chargers_.push_back(enc(x));}
Flight DroneAltitudePathfinder::shortest_flight(AirCell s,AirCell g,int cap)const{
 auto enc=[&](AirCell x){return(x.layer*r_+x.row)*c_+x.col;};int n=l_*r_*c_;if(cap<0||enc(s)<0||enc(s)>=n||enc(g)<0||enc(g)>=n)throw std::invalid_argument("input");
 if(std::find(blocked_.begin(),blocked_.end(),enc(s))!=blocked_.end())return{};
 int states=n*(cap+1),start=enc(s)*(cap+1)+cap;std::vector<int>d(states,std::numeric_limits<int>::max()),prev(states,-1);using Node=std::pair<int,int>;std::priority_queue<Node,std::vector<Node>,std::greater<Node>> q;d[start]=0;q.push({0,start});
 int dirs[6][3]={{1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1},{0,0,-1}};
 while(!q.empty()){auto [cost,state]=q.top();q.pop();if(cost!=d[state])continue;int cell=state/(cap+1),rem=state%(cap+1),z=cell/(r_*c_),y=(cell/c_)%r_,x=cell%c_;
  for(auto& v:dirs){int nz=z+v[0],ny=y+v[1],nx=x+v[2],use=v[0]?2:1;if(nz<0||nz>=l_||ny<0||ny>=r_||nx<0||nx>=c_||use>rem)continue;int nc=(nz*r_+ny)*c_+nx;if(std::find(blocked_.begin(),blocked_.end(),nc)!=blocked_.end())continue;int nr=rem-use;if(std::find(chargers_.begin(),chargers_.end(),nc)!=chargers_.end())nr=cap;int ns=nc*(cap+1)+nr;if(cost+use<d[ns]){d[ns]=cost+use;prev[ns]=state;q.push({d[ns],ns});}}}
 int best=-1;for(int rem=0;rem<=cap;++rem){int st=enc(g)*(cap+1)+rem;if(best<0||d[st]<d[best])best=st;}if(best<0||d[best]==std::numeric_limits<int>::max())return{};
 Flight out;out.reachable=true;out.energy=d[best];for(int st=best;st>=0;st=prev[st]){int cell=st/(cap+1);out.path.push_back({cell/(r_*c_),(cell/c_)%r_,cell%c_});if(st!=start&&st%(cap+1)==cap)++out.recharges;}std::reverse(out.path.begin(),out.path.end());return out;
}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;DroneAltitudePathfinder d(2,2,2,{},{{0,0,1}});auto f=d.shortest_flight({0,0,0},{1,0,1},2);return f.reachable&&f.energy==3&&f.recharges>=1?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;DroneAltitudePathfinder d(1,2,3,{{0,0,1},{0,1,1}},{});auto x=d.shortest_flight({0,0,0},{0,0,2},5);f+=x.reachable;auto same=d.shortest_flight({0,1,0},{0,1,0},0);f+=!(same.reachable&&same.path.size()==1);return f;}
"""),
RobotCase(
"sim-harbor-crane","harbor-stack-rebalancer","Harbor Stack Rebalancer","bounded-top-stack-transfer",
"Move top containers between bounded harbor stacks with atomic rejection.",
"HarborStackRebalancer(stacks,max_height).move_top; snapshot; rejected","pop_back()",
r"""# Instructions

Stacks are bottom-to-top integer vectors. `move_top(from,to)` moves exactly the top
container, updates crane position to `to`, and returns true. It returns false and
increments `rejected` without any yard or crane mutation for an invalid index, same
stack, empty source, or full target. Container IDs must be positive and initial stack
heights may not exceed `max_height`. `snapshot` returns the complete yard and crane.
""",
r"""#pragma once
#include <cstddef>
#include <vector>
namespace curriculum {struct Yard{std::vector<std::vector<int>> stacks;std::size_t crane=0;int rejected=0;};
class HarborStackRebalancer{std::vector<std::vector<int>> stacks_;std::size_t max_,crane_=0;int rejected_=0;public:
 HarborStackRebalancer(std::vector<std::vector<int>>,std::size_t);bool move_top(std::size_t,std::size_t);Yard snapshot()const;int rejected()const{return rejected_;};};}
""",_starter("HarborStackRebalancer"),
r"""#include "task.h"
#include <stdexcept>
namespace curriculum {HarborStackRebalancer::HarborStackRebalancer(std::vector<std::vector<int>> s,std::size_t m):stacks_(std::move(s)),max_(m){if(!m)throw std::invalid_argument("height");for(auto& st:stacks_){if(st.size()>m)throw std::invalid_argument("height");for(int id:st)if(id<=0)throw std::invalid_argument("id");}}
bool HarborStackRebalancer::move_top(std::size_t a,std::size_t b){if(a>=stacks_.size()||b>=stacks_.size()||a==b||stacks_[a].empty()||stacks_[b].size()>=max_){++rejected_;return false;}int id=stacks_[a].back();stacks_[a].pop_back();stacks_[b].push_back(id);crane_=b;return true;}
Yard HarborStackRebalancer::snapshot()const{return{stacks_,crane_,rejected_};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;HarborStackRebalancer y({{1,2},{3},{}},3);y.move_top(0,2);auto s=y.snapshot();return s.stacks[0]==std::vector<int>{1}&&s.stacks[2]==std::vector<int>{2}&&s.crane==2?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;HarborStackRebalancer y({{1},{2,3}},2);auto before=y.snapshot();int f=0;f+=y.move_top(0,1);auto after=y.snapshot();f+=before.stacks!=after.stacks;f+=after.rejected!=1;f+=y.move_top(0,0);return f;}
"""),
RobotCase(
"sim-mars-rover-energy","mars-energy-route-planner","Mars Energy Route Planner","weighted-terrain-dijkstra",
"Compute a minimum-energy terrain route subject to a slope limit and budget.",
"MarsEnergyRoutePlanner(elevation,slope_limit).cheapest(start,goal,budget)","positive_gain",
r"""# Instructions

The rectangular elevation grid has four-neighbor movement. A move costs
`1 + max(0,next-current)`; an absolute elevation difference above `slope_limit`
is impassable. `cheapest` uses minimum total energy, with row-major deterministic
ties, and returns unreachable when the minimum exceeds `budget`. A reachable path
contains both endpoints. Ragged grids, invalid cells, negative limits, or budgets throw.
""",
r"""#pragma once
#include <vector>
namespace curriculum {struct TerrainCell{int row=0,col=0;bool operator==(const TerrainCell&o)const{return row==o.row&&col==o.col;}};
struct EnergyRoute{bool reachable=false;int energy=0;std::vector<TerrainCell> path;};
class MarsEnergyRoutePlanner{std::vector<std::vector<int>> elevation_;int slope_;public:MarsEnergyRoutePlanner(std::vector<std::vector<int>>,int);EnergyRoute cheapest(TerrainCell,TerrainCell,int)const;};}
""",_starter("MarsEnergyRoutePlanner"),
r"""#include "task.h"
#include <algorithm>
#include <limits>
#include <queue>
#include <stdexcept>
namespace curriculum {MarsEnergyRoutePlanner::MarsEnergyRoutePlanner(std::vector<std::vector<int>> e,int s):elevation_(std::move(e)),slope_(s){if(elevation_.empty()||elevation_[0].empty()||s<0)throw std::invalid_argument("grid");for(auto&r:elevation_)if(r.size()!=elevation_[0].size())throw std::invalid_argument("ragged");}
EnergyRoute MarsEnergyRoutePlanner::cheapest(TerrainCell a,TerrainCell b,int budget)const{int rows=elevation_.size(),cols=elevation_[0].size();auto ok=[&](TerrainCell x){return x.row>=0&&x.row<rows&&x.col>=0&&x.col<cols;};if(!ok(a)||!ok(b)||budget<0)throw std::invalid_argument("input");int n=rows*cols,src=a.row*cols+a.col,dst=b.row*cols+b.col,inf=std::numeric_limits<int>::max();std::vector<int>d(n,inf),p(n,-1);using N=std::pair<int,int>;std::priority_queue<N,std::vector<N>,std::greater<N>>q;d[src]=0;q.push({0,src});int dr[4]={-1,0,0,1},dc[4]={0,-1,1,0};
 while(!q.empty()){auto [cost,u]=q.top();q.pop();if(cost!=d[u])continue;int r=u/cols,c=u%cols;for(int k=0;k<4;++k){int nr=r+dr[k],nc=c+dc[k];if(nr<0||nr>=rows||nc<0||nc>=cols)continue;int diff=elevation_[nr][nc]-elevation_[r][c];if(std::abs(diff)>slope_)continue;int positive_gain=diff>0?diff:0,w=1+positive_gain,v=nr*cols+nc;if(cost<=inf-w&&cost+w<d[v]){d[v]=cost+w;p[v]=u;q.push({d[v],v});}}}
 if(d[dst]>budget)return{};EnergyRoute out{true,d[dst],{}};for(int v=dst;v>=0;v=p[v]){out.path.push_back({v/cols,v%cols});if(v==src)break;}std::reverse(out.path.begin(),out.path.end());return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;MarsEnergyRoutePlanner p({{0,3,0},{0,0,0}},3);auto r=p.cheapest({0,0},{0,2},5);return r.reachable&&r.energy==4&&r.path.size()==5?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;MarsEnergyRoutePlanner p({{0,5},{0,0}},2);auto x=p.cheapest({0,0},{0,1},9);auto y=p.cheapest({0,0},{1,1},1);return !x.reachable&&!y.reachable?0:1;}
"""),
RobotCase(
"sim-subway-maintenance","subway-switch-inspector","Subway Switch Inspector","switch-gated-graph-traversal",
"Traverse a rail graph with explicit switch selections and first-visit inspections.",
"SubwaySwitchInspector(stations,edges).set_switch; traverse","selected_[station]",
r"""# Instructions

Each directed `RailEdge{from,to,branch}` uses branch -1 for ordinary track or 0/1
for a switch branch. `set_switch` accepts only a station that has the requested
branch. `traverse(start,requested_next)` processes requested stations in order.
A step is accepted only if a matching ordinary edge exists or its branch equals the
selected branch; otherwise traversal stops, records that requested station as rejected,
and leaves the cart at its prior station. `inspected` records each reached station once.
""",
r"""#pragma once
#include <vector>
namespace curriculum {struct RailEdge{int from,to,branch;};struct RailTrace{int final_station=-1;std::vector<int> visited,inspected;int rejected_station=-1;};
class SubwaySwitchInspector{int stations_;std::vector<RailEdge> edges_;std::vector<int> selected_;public:SubwaySwitchInspector(int,std::vector<RailEdge>);bool set_switch(int,int);RailTrace traverse(int,const std::vector<int>&)const;};}
""",_starter("SubwaySwitchInspector"),
r"""#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {SubwaySwitchInspector::SubwaySwitchInspector(int n,std::vector<RailEdge> e):stations_(n),edges_(std::move(e)),selected_(n,0){if(n<=0)throw std::invalid_argument("stations");for(auto x:edges_)if(x.from<0||x.from>=n||x.to<0||x.to>=n||x.branch < -1||x.branch>1)throw std::invalid_argument("edge");}
bool SubwaySwitchInspector::set_switch(int station,int branch){if(station<0||station>=stations_||(branch!=0&&branch!=1))return false;bool exists=false;for(auto e:edges_)exists|=e.from==station&&e.branch==branch;if(!exists)return false;selected_[station]=branch;return true;}
RailTrace SubwaySwitchInspector::traverse(int start,const std::vector<int>& next)const{if(start<0||start>=stations_)throw std::invalid_argument("start");RailTrace out;out.final_station=start;out.visited.push_back(start);out.inspected.push_back(start);
 for(int wanted:next){bool pass=false;for(auto e:edges_)if(e.from==out.final_station&&e.to==wanted&&(e.branch<0||e.branch==selected_[out.final_station])){pass=true;break;}if(!pass){out.rejected_station=wanted;break;}out.final_station=wanted;out.visited.push_back(wanted);if(std::find(out.inspected.begin(),out.inspected.end(),wanted)==out.inspected.end())out.inspected.push_back(wanted);}return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;SubwaySwitchInspector s(4,{{0,1,-1},{1,2,0},{1,3,1}});s.set_switch(1,1);auto t=s.traverse(0,{1,3});return t.final_station==3&&t.inspected.size()==3?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;SubwaySwitchInspector s(3,{{0,1,0},{0,2,1},{1,0,-1}});int f=0;f+=!s.set_switch(0,1);auto t=s.traverse(0,{1});f+=t.final_station!=0||t.rejected_station!=1;f+=s.set_switch(2,0);return f;}
"""),
RobotCase(
"sim-firefighter-bot","fire-spread-responder","Fire Spread Responder","double-buffer-cellular-spread",
"Apply water, then simulate simultaneous four-neighbor fire spread.",
"FireSpreadResponder(grid,water).step(actions); snapshot","next = grid_",
r"""# Instructions

Grid cells are `.` open, `#` wall, `F` fire, and `T` protected target.
Each `step` first extinguishes requested burning cells, one water unit each; invalid
or non-burning requests are rejected without spending water. Fire then spreads
simultaneously from every remaining fire into adjacent open or target cells. A cell
ignited during this tick cannot spread until the next tick. The snapshot reports the
complete grid, remaining water, cumulative rejections, and surviving targets.
""",
r"""#pragma once
#include <string>
#include <vector>
namespace curriculum {struct FireCell{int row,col;};struct FireSnapshot{std::vector<std::string> grid;int water=0,rejected=0,surviving_targets=0;};
class FireSpreadResponder{std::vector<std::string> grid_;int water_,rejected_=0;public:FireSpreadResponder(std::vector<std::string>,int);FireSnapshot step(const std::vector<FireCell>&);FireSnapshot snapshot()const;};}
""",_starter("FireSpreadResponder"),
r"""#include "task.h"
#include <stdexcept>
namespace curriculum {FireSpreadResponder::FireSpreadResponder(std::vector<std::string> g,int w):grid_(std::move(g)),water_(w){if(grid_.empty()||grid_[0].empty()||w<0)throw std::invalid_argument("grid");for(auto&r:grid_)if(r.size()!=grid_[0].size())throw std::invalid_argument("ragged");}
FireSnapshot FireSpreadResponder::snapshot()const{int targets=0;for(auto&r:grid_)for(char c:r)targets+=c=='T';return{grid_,water_,rejected_,targets};}
FireSnapshot FireSpreadResponder::step(const std::vector<FireCell>& actions){int rows=grid_.size(),cols=grid_[0].size();for(auto a:actions){if(a.row<0||a.row>=rows||a.col<0||a.col>=cols||grid_[a.row][a.col]!='F'||water_==0){++rejected_;continue;}grid_[a.row][a.col]='.';--water_;}
 auto next = grid_;int dr[4]={-1,1,0,0},dc[4]={0,0,-1,1};for(int r=0;r<rows;++r)for(int c=0;c<cols;++c)if(grid_[r][c]=='F')for(int k=0;k<4;++k){int nr=r+dr[k],nc=c+dc[k];if(nr>=0&&nr<rows&&nc>=0&&nc<cols&&(grid_[nr][nc]=='.'||grid_[nr][nc]=='T'))next[nr][nc]='F';}grid_=std::move(next);return snapshot();}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;FireSpreadResponder f({".F.","...","T#."},1);auto s=f.step({});return s.grid[1][1]=='F'&&s.grid[2][0]=='T'?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;FireSpreadResponder f({".F.","..."},1);auto s=f.step({{0,1},{0,1}});return s.water==0&&s.rejected==1&&s.grid[1][1]=='.'?0:1;}
"""),
RobotCase(
"sim-orchard-harvester","orchard-capacity-harvester","Orchard Capacity Harvester","serpentine-capacity-harvest",
"Harvest ripe trees in serpentine row order under a bin capacity.",
"OrchardCapacityHarvester(fruit,capacity).harvest(minimum); unload; snapshot","reverse(order.begin()",
r"""# Instructions

The fruit matrix stores non-negative fruit counts. Harvest visits even rows left-to-right
and odd rows right-to-left. A tree below `minimum_ripeness` is skipped. A qualifying
tree that does not fit in the remaining bin stops the pass immediately and remains
unchanged. Harvested trees become zero and their coordinates are returned in visit order.
`unload` returns the bin load and resets it. Invalid matrices, capacity, or threshold throw.
""",
r"""#pragma once
#include <vector>
namespace curriculum {struct OrchardCell{int row,col;};struct Harvest{int collected=0;bool capacity_stop=false;std::vector<OrchardCell> trees;};struct OrchardSnapshot{std::vector<std::vector<int>> fruit;int bin_load=0;};
class OrchardCapacityHarvester{std::vector<std::vector<int>> fruit_;int capacity_,load_=0;public:OrchardCapacityHarvester(std::vector<std::vector<int>>,int);Harvest harvest(int);int unload();OrchardSnapshot snapshot()const;};}
""",_starter("OrchardCapacityHarvester"),
r"""#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {OrchardCapacityHarvester::OrchardCapacityHarvester(std::vector<std::vector<int>> f,int c):fruit_(std::move(f)),capacity_(c){if(fruit_.empty()||fruit_[0].empty()||c<=0)throw std::invalid_argument("orchard");for(auto&r:fruit_){if(r.size()!=fruit_[0].size())throw std::invalid_argument("ragged");for(int v:r)if(v<0)throw std::invalid_argument("fruit");}}
Harvest OrchardCapacityHarvester::harvest(int minimum){if(minimum<0)throw std::invalid_argument("minimum");Harvest out;for(std::size_t r=0;r<fruit_.size();++r){std::vector<std::size_t> order(fruit_[r].size());for(std::size_t i=0;i<order.size();++i)order[i]=i;if(r%2)std::reverse(order.begin(),order.end());for(auto c:order){int v=fruit_[r][c];if(v<minimum)continue;if(load_+v>capacity_){out.capacity_stop=true;return out;}load_+=v;out.collected+=v;fruit_[r][c]=0;out.trees.push_back({static_cast<int>(r),static_cast<int>(c)});}}return out;}
int OrchardCapacityHarvester::unload(){int n=load_;load_=0;return n;}OrchardSnapshot OrchardCapacityHarvester::snapshot()const{return{fruit_,load_};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;OrchardCapacityHarvester h({{2,4},{3,1}},8);auto x=h.harvest(2);return x.collected==6&&x.capacity_stop&&x.trees.size()==2?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;OrchardCapacityHarvester h({{1,2},{4,3}},20);auto x=h.harvest(2);int f=0;f+=!(x.trees.size()==3&&x.trees[1].col==1);f+=h.unload()!=9;f+=h.snapshot().bin_load!=0;return f;}
"""),
RobotCase(
"sim-hospital-courier","hospital-priority-courier","Hospital Priority Courier","stable-manual-binary-heap",
"Dispatch samples by priority then arrival order while enforcing sterile-zone compatibility.",
"HospitalPriorityCourier.enqueue; dispatch; pending","sift_up",
r"""# Instructions

Each sample has a positive unique ID, integer priority, and `sterile_only` flag.
`enqueue` rejects duplicate/non-positive IDs. `dispatch(sterile_zone)` chooses the
highest priority compatible sample; equal priorities use earlier arrival. In a
non-sterile zone, sterile-only samples remain queued while a lower compatible sample
may be dispatched. Return `std::nullopt` if none is compatible. Implement the owned
binary heap directly; do not delegate the substantive ordering to `std::priority_queue`.
""",
r"""#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum {struct Sample{int id=0,priority=0;bool sterile_only=false;};class HospitalPriorityCourier{struct Entry{Sample sample;std::size_t sequence;};std::vector<Entry> heap_;std::size_t next_=0;bool better(const Entry&,const Entry&)const;void sift_up(std::size_t);void sift_down(std::size_t);public:bool enqueue(Sample);std::optional<Sample> dispatch(bool sterile_zone);std::size_t pending()const{return heap_.size();}};}
""",_starter("HospitalPriorityCourier"),
r"""#include "task.h"
#include <algorithm>
namespace curriculum {bool HospitalPriorityCourier::better(const Entry&a,const Entry&b)const{return a.sample.priority!=b.sample.priority?a.sample.priority>b.sample.priority:a.sequence<b.sequence;}
void HospitalPriorityCourier::sift_up(std::size_t i){while(i){std::size_t p=(i-1)/2;if(!better(heap_[i],heap_[p]))break;std::swap(heap_[i],heap_[p]);i=p;}}
void HospitalPriorityCourier::sift_down(std::size_t i){for(;;){std::size_t b=i,l=i*2+1,r=l+1;if(l<heap_.size()&&better(heap_[l],heap_[b]))b=l;if(r<heap_.size()&&better(heap_[r],heap_[b]))b=r;if(b==i)break;std::swap(heap_[i],heap_[b]);i=b;}}
bool HospitalPriorityCourier::enqueue(Sample s){if(s.id<=0)return false;for(auto&e:heap_)if(e.sample.id==s.id)return false;heap_.push_back({s,next_++});sift_up(heap_.size()-1);return true;}
std::optional<Sample> HospitalPriorityCourier::dispatch(bool sterile){std::size_t best=heap_.size();for(std::size_t i=0;i<heap_.size();++i)if((sterile||!heap_[i].sample.sterile_only)&&(best==heap_.size()||better(heap_[i],heap_[best])))best=i;if(best==heap_.size())return std::nullopt;Sample out=heap_[best].sample;heap_[best]=heap_.back();heap_.pop_back();if(best<heap_.size()){sift_up(best);sift_down(best);}return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;HospitalPriorityCourier q;q.enqueue({1,5,true});q.enqueue({2,3,false});auto x=q.dispatch(false);return x&&x->id==2&&q.pending()==1?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;HospitalPriorityCourier q;int f=0;f+=!q.enqueue({1,4,false});f+=q.enqueue({1,9,false});q.enqueue({2,4,false});auto a=q.dispatch(true),b=q.dispatch(true);f+=!(a&&b&&a->id==1&&b->id==2);f+=q.dispatch(true).has_value();return f;}
"""),
RobotCase(
"sim-ocean-survey","ocean-dive-profiler","Ocean Dive Profiler","depth-time-decompression-profile",
"Validate depth-time legs against oxygen, ascent-rate, and decompression rules.",
"OceanDiveProfiler(oxygen).run(legs)->DiveReport","needs_stop",
r"""# Instructions

A leg names target depth (0..100) and duration in positive minutes. Oxygen cost is
`duration * (1 + target_depth/10)`. Depth may change by at most 10 metres per minute.
After ever reaching depth >=30, the profile must include a leg at depth 5 lasting at
least 3 minutes before returning to zero. Processing stops at the first invalid leg or
oxygen exhaustion, reporting its index and preserving oxygen spent by earlier legs.
Completion requires a final depth of zero and the decompression rule.
""",
r"""#pragma once
#include <vector>
namespace curriculum {struct DiveLeg{int target_depth,duration;};struct DiveReport{bool completed=false;int oxygen_left=0,final_depth=0,rejected_index=-1;std::vector<int> depth_trace;};
class OceanDiveProfiler{int oxygen_;public:explicit OceanDiveProfiler(int);DiveReport run(const std::vector<DiveLeg>&)const;};}
""",_starter("OceanDiveProfiler"),
r"""#include "task.h"
#include <cstdlib>
#include <stdexcept>
namespace curriculum {OceanDiveProfiler::OceanDiveProfiler(int o):oxygen_(o){if(o<0)throw std::invalid_argument("oxygen");}
DiveReport OceanDiveProfiler::run(const std::vector<DiveLeg>& legs)const{DiveReport out;out.oxygen_left=oxygen_;int depth=0;bool needs_stop=false,stopped=false;for(std::size_t i=0;i<legs.size();++i){auto x=legs[i];long long use=1LL*x.duration*(1+x.target_depth/10);if(x.target_depth<0||x.target_depth>100||x.duration<=0||std::abs(x.target_depth-depth)>10*x.duration||use>out.oxygen_left){out.rejected_index=static_cast<int>(i);out.final_depth=depth;return out;}out.oxygen_left-=static_cast<int>(use);depth=x.target_depth;out.depth_trace.push_back(depth);needs_stop|=depth>=30;stopped|=depth==5&&x.duration>=3;}out.final_depth=depth;out.completed=depth==0&&(!needs_stop||stopped);return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;OceanDiveProfiler d(200);auto r=d.run({{20,2},{30,1},{5,3},{0,1}});return r.completed&&r.rejected_index<0?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;OceanDiveProfiler d(1000);auto fast=d.run({{30,1}});auto no_stop=d.run({{30,3},{0,3}});return fast.rejected_index==0&&!no_stop.completed?0:1;}
"""),
RobotCase(
"sim-construction-hauler","construction-load-router","Construction Load Router","load-constrained-road-replay",
"Replay load, road, and unload operations over roads with payload limits.",
"ConstructionLoadRouter(sites,roads,capacity,start); load; travel; unload; snapshot","road.limit",
r"""# Instructions

`Road{from,to,limit}` is directed. The hauler has a vehicle capacity and starts at a
valid site. `load(units)` succeeds only at site 0 with positive units fitting capacity.
`travel(next)` succeeds only on a road from the current site whose limit is at least
the current load. `unload()` succeeds only at the final site (`sites-1`) and returns
the delivered load. Every rejected operation increments `rejected` and is atomic.
""",
r"""#pragma once
#include <vector>
namespace curriculum {struct Road{int from,to,limit;};struct HaulState{int site=0,load=0,delivered=0,rejected=0;};
class ConstructionLoadRouter{int sites_,capacity_;std::vector<Road> roads_;HaulState state_;public:ConstructionLoadRouter(int,std::vector<Road>,int,int=0);bool load(int);bool travel(int);int unload();HaulState snapshot()const{return state_;}};}
""",_starter("ConstructionLoadRouter"),
r"""#include "task.h"
#include <stdexcept>
namespace curriculum {ConstructionLoadRouter::ConstructionLoadRouter(int n,std::vector<Road> r,int c,int s):sites_(n),capacity_(c),roads_(std::move(r)){if(n<2||c<=0||s<0||s>=n)throw std::invalid_argument("input");state_.site=s;for(auto road:roads_)if(road.from<0||road.from>=n||road.to<0||road.to>=n||road.limit<0)throw std::invalid_argument("road");}
bool ConstructionLoadRouter::load(int n){if(state_.site!=0||n<=0||n>capacity_-state_.load){++state_.rejected;return false;}state_.load+=n;return true;}
bool ConstructionLoadRouter::travel(int next){for(auto road:roads_)if(road.from==state_.site&&road.to==next&&state_.load<=road.limit){state_.site=next;return true;}++state_.rejected;return false;}
int ConstructionLoadRouter::unload(){if(state_.site!=sites_-1||state_.load==0){++state_.rejected;return 0;}int n=state_.load;state_.load=0;state_.delivered+=n;return n;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;ConstructionLoadRouter h(3,{{0,1,5},{1,2,3}},5);h.load(3);return h.travel(1)&&h.travel(2)&&h.unload()==3?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;ConstructionLoadRouter h(3,{{0,1,2}},4);h.load(3);auto before=h.snapshot();int f=0;f+=h.travel(1);auto after=h.snapshot();f+=before.site!=after.site;f+=after.rejected!=1;f+=h.unload()!=0;return f;}
"""),
RobotCase(
"sim-library-sorter","library-label-sorter","Library Label Sorter","lexical-checksum-routing",
"Parse, validate, and stably route category labels with a lexical state machine.",
"LibraryLabelSorter(categories).sort(labels)->SortResult","for(char ch:label)",
r"""# Instructions

Labels have exactly `CATEGORY-NUMBER-CHECK`: CATEGORY is one or more uppercase
letters, NUMBER is 1..9999 with no sign, and CHECK is one decimal digit equal to the
sum of NUMBER's decimal digits modulo 10. CATEGORY must be in the constructor list.
`sort` parses character by character (no regex), appends valid original labels to
their category bin preserving input order, and appends invalid input indices to
`rejected_indices`. Duplicate labels are independent records.
""",
r"""#pragma once
#include <map>
#include <string>
#include <vector>
namespace curriculum {struct SortResult{std::map<std::string,std::vector<std::string>> bins;std::vector<int> rejected_indices;};
class LibraryLabelSorter{std::vector<std::string> categories_;public:explicit LibraryLabelSorter(std::vector<std::string>);SortResult sort(const std::vector<std::string>&)const;};}
""",_starter("LibraryLabelSorter"),
r"""#include "task.h"
#include <algorithm>
#include <cctype>
#include <stdexcept>
namespace curriculum {LibraryLabelSorter::LibraryLabelSorter(std::vector<std::string> c):categories_(std::move(c)){if(categories_.empty())throw std::invalid_argument("categories");}
SortResult LibraryLabelSorter::sort(const std::vector<std::string>& labels)const{SortResult out;for(std::size_t index=0;index<labels.size();++index){const auto& label=labels[index];std::string cat;int number=0,sum=0,stage=0,digits=0,check=-1;bool ok=true;
 for(char ch:label){if(stage==0){if(ch=='-'&&!cat.empty())stage=1;else if(ch>='A'&&ch<='Z')cat+=ch;else ok=false;}else if(stage==1){if(ch=='-'&&digits)stage=2;else if(std::isdigit(static_cast<unsigned char>(ch))&&digits<4){number=number*10+(ch-'0');sum+=ch-'0';++digits;}else ok=false;}else if(stage==2&&check<0&&std::isdigit(static_cast<unsigned char>(ch)))check=ch-'0';else ok=false;}
 ok=ok&&stage==2&&check>=0&&number>0&&check==sum%10&&std::find(categories_.begin(),categories_.end(),cat)!=categories_.end();if(ok)out.bins[cat].push_back(label);else out.rejected_indices.push_back(static_cast<int>(index));}return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;LibraryLabelSorter s({"SCI","ART"});auto r=s.sort({"SCI-123-6","ART-8-8"});return r.rejected_indices.empty()&&r.bins["SCI"].size()==1?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;LibraryLabelSorter s({"SCI"});auto r=s.sort({"SCI-12-4","sci-12-3","BIO-1-1","SCI-0-0","SCI-12-3"});return r.bins["SCI"]==std::vector<std::string>{"SCI-12-3"}&&r.rejected_indices.size()==4?0:1;}
"""),
RobotCase(
"sim-factory-inspector","factory-lockout-inspector","Factory Lockout Inspector","explicit-lockout-fsm",
"Apply an explicit machine lockout protocol and retain a fault ledger.",
"FactoryLockoutInspector.apply(Event); snapshot","switch(event)",
r"""# Instructions

States are Off, Running, Locked, and Maintenance. Start Off. Start: Off->Running.
Stop: Running->Off. Fault(code>0): Running->Locked and records code. EnterMaintenance:
Off->Maintenance. ExitMaintenance: Maintenance->Off. Reset: Locked->Off only after
`acknowledge_fault(code)` matches the most recent fault. All other events or bad
acknowledgements are rejected without changing state. The transition result reports
before, after, acceptance, and cumulative rejection count.
""",
r"""#pragma once
#include <vector>
namespace curriculum {enum class MachineMode{Off,Running,Locked,Maintenance};enum class MachineEvent{Start,Stop,Fault,EnterMaintenance,ExitMaintenance,Reset};struct Transition{MachineMode before,after;bool accepted;int rejected;};
class FactoryLockoutInspector{MachineMode mode_=MachineMode::Off;std::vector<int> faults_;int rejected_=0,ack_=0;public:bool acknowledge_fault(int);Transition apply(MachineEvent,int code=0);MachineMode mode()const{return mode_;}const std::vector<int>& faults()const{return faults_;}};}
""",_starter("FactoryLockoutInspector"),
r"""#include "task.h"
namespace curriculum {bool FactoryLockoutInspector::acknowledge_fault(int c){if(mode_!=MachineMode::Locked||faults_.empty()||faults_.back()!=c){++rejected_;return false;}ack_=c;return true;}
Transition FactoryLockoutInspector::apply(MachineEvent event,int code){auto before=mode_;bool ok=false;switch(event){case MachineEvent::Start:ok=mode_==MachineMode::Off;if(ok)mode_=MachineMode::Running;break;case MachineEvent::Stop:ok=mode_==MachineMode::Running;if(ok)mode_=MachineMode::Off;break;case MachineEvent::Fault:ok=mode_==MachineMode::Running&&code>0;if(ok){faults_.push_back(code);mode_=MachineMode::Locked;ack_=0;}break;case MachineEvent::EnterMaintenance:ok=mode_==MachineMode::Off;if(ok)mode_=MachineMode::Maintenance;break;case MachineEvent::ExitMaintenance:ok=mode_==MachineMode::Maintenance;if(ok)mode_=MachineMode::Off;break;case MachineEvent::Reset:ok=mode_==MachineMode::Locked&&!faults_.empty()&&ack_==faults_.back();if(ok)mode_=MachineMode::Off;break;}if(!ok)++rejected_;return{before,mode_,ok,rejected_};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;FactoryLockoutInspector f;f.apply(MachineEvent::Start);auto x=f.apply(MachineEvent::Fault,7);f.acknowledge_fault(7);auto y=f.apply(MachineEvent::Reset);return x.after==MachineMode::Locked&&y.after==MachineMode::Off?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;FactoryLockoutInspector f;int n=0;n+=f.apply(MachineEvent::Reset).accepted;f.apply(MachineEvent::Start);f.apply(MachineEvent::Fault,9);n+=f.acknowledge_fault(8);n+=f.apply(MachineEvent::Reset).accepted;return n==0&&f.mode()==MachineMode::Locked?0:1;}
"""),
RobotCase(
"sim-snowplow-route","snowplow-edge-router","Snowplow Edge Router","directed-hierholzer-edge-trail",
"Find a deterministic directed trail that clears every road edge exactly once.",
"SnowplowEdgeRouter(vertices,roads).plan(start)->PlowPlan","edge_stack",
r"""# Instructions

Each `SnowRoad{from,to,id}` is a distinct directed snowy road with a non-negative,
unique ID. `plan(start)` returns a trail of vertex and edge IDs using every road
exactly once, or `possible=false`. It must validate directed Euler degree conditions,
reachability of all nonzero-degree vertices from the start in the usable direction,
and the requested start. When multiple unused outgoing roads exist, take smaller edge
ID first. Parallel roads are preserved. Empty roads yield the one-vertex trail.
""",
r"""#pragma once
#include <vector>
namespace curriculum {struct SnowRoad{int from,to,id;};struct PlowPlan{bool possible=false;std::vector<int> vertices,edge_ids;};
class SnowplowEdgeRouter{int vertices_;std::vector<SnowRoad> roads_;public:SnowplowEdgeRouter(int,std::vector<SnowRoad>);PlowPlan plan(int)const;};}
""",_starter("SnowplowEdgeRouter"),
r"""#include "task.h"
#include <algorithm>
#include <set>
#include <stdexcept>
namespace curriculum {SnowplowEdgeRouter::SnowplowEdgeRouter(int n,std::vector<SnowRoad> r):vertices_(n),roads_(std::move(r)){if(n<=0)throw std::invalid_argument("vertices");std::set<int>ids;for(auto e:roads_)if(e.from<0||e.from>=n||e.to<0||e.to>=n||e.id<0||!ids.insert(e.id).second)throw std::invalid_argument("road");}
PlowPlan SnowplowEdgeRouter::plan(int start)const{if(start<0||start>=vertices_)throw std::invalid_argument("start");std::vector<int>in(vertices_),out(vertices_);std::vector<std::vector<SnowRoad>> adj(vertices_);for(auto e:roads_){++out[e.from];++in[e.to];adj[e.from].push_back(e);}for(auto&v:adj)std::sort(v.begin(),v.end(),[](auto a,auto b){return a.id>b.id;});int plus=0,minus=0;for(int v=0;v<vertices_;++v){plus+=out[v]-in[v]==1;minus+=in[v]-out[v]==1;if(std::abs(out[v]-in[v])>1)return{};}if(!((plus==0&&minus==0)||(plus==1&&minus==1))||(plus==1&&out[start]-in[start]!=1))return{};
 std::vector<int>vertex_stack{start},edge_stack,rev_v,rev_e;while(!vertex_stack.empty()){int v=vertex_stack.back();if(!adj[v].empty()){auto e=adj[v].back();adj[v].pop_back();vertex_stack.push_back(e.to);edge_stack.push_back(e.id);}else{rev_v.push_back(v);vertex_stack.pop_back();if(!edge_stack.empty()){rev_e.push_back(edge_stack.back());edge_stack.pop_back();}}}if(rev_e.size()!=roads_.size())return{};std::reverse(rev_v.begin(),rev_v.end());std::reverse(rev_e.begin(),rev_e.end());return{true,rev_v,rev_e};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;SnowplowEdgeRouter r(3,{{0,1,4},{1,2,2},{2,0,7}});auto p=r.plan(0);return p.possible&&p.edge_ids==std::vector<int>({4,2,7})?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;SnowplowEdgeRouter parallel(2,{{0,1,2},{0,1,1},{1,0,3}});auto p=parallel.plan(0);SnowplowEdgeRouter bad(3,{{0,1,1},{2,2,2}});return p.possible&&p.edge_ids.front()==1&&!bad.plan(0).possible?0:1;}
"""),
RobotCase(
"sim-space-station-repair","station-airlock-repair","Station Airlock Repair","pressure-gated-airlock-state",
"Operate pressure-gated airlocks and seal module leaks with finite kits.",
"StationAirlockRepair(pressures,leaks,airlocks,kits,start); set_airlock; move; seal","pressure_[edges_[edge].a]",
r"""# Instructions

Airlocks connect two modules and start closed. Opening an airlock succeeds only when
endpoint pressures are equal; closing always succeeds. `move(module)` requires an
open incident airlock. `seal()` consumes one kit only when the current module has a
leak, then clears it. Invalid operations are atomic and increment `rejected`.
Opening, moving, or sealing never silently changes pressure. Constructor vectors must
agree in size, pressures are non-negative, and the start module is valid.
""",
r"""#pragma once
#include <vector>
namespace curriculum {struct Airlock{int a,b;};struct StationState{int module=0,kits=0,sealed=0,rejected=0;std::vector<bool> leaks,open;};
class StationAirlockRepair{std::vector<int> pressure_;std::vector<Airlock> edges_;StationState state_;public:StationAirlockRepair(std::vector<int>,std::vector<bool>,std::vector<Airlock>,int,int=0);bool set_airlock(int,bool);bool move(int);bool seal();StationState snapshot()const{return state_;}};}
""",_starter("StationAirlockRepair"),
r"""#include "task.h"
#include <stdexcept>
namespace curriculum {StationAirlockRepair::StationAirlockRepair(std::vector<int> p,std::vector<bool> l,std::vector<Airlock> e,int kits,int start):pressure_(std::move(p)),edges_(std::move(e)){if(pressure_.empty()||l.size()!=pressure_.size()||kits<0||start<0||start>=static_cast<int>(pressure_.size()))throw std::invalid_argument("input");for(int v:pressure_)if(v<0)throw std::invalid_argument("pressure");for(auto x:edges_)if(x.a<0||x.b<0||x.a>=static_cast<int>(pressure_.size())||x.b>=static_cast<int>(pressure_.size())||x.a==x.b)throw std::invalid_argument("edge");state_.module=start;state_.kits=kits;state_.leaks=std::move(l);state_.open.assign(edges_.size(),false);}
bool StationAirlockRepair::set_airlock(int edge,bool open){if(edge<0||edge>=static_cast<int>(edges_.size())||(open&&pressure_[edges_[edge].a]!=pressure_[edges_[edge].b])){++state_.rejected;return false;}state_.open[edge]=open;return true;}
bool StationAirlockRepair::move(int module){for(std::size_t i=0;i<edges_.size();++i)if(state_.open[i]&&((edges_[i].a==state_.module&&edges_[i].b==module)||(edges_[i].b==state_.module&&edges_[i].a==module))){state_.module=module;return true;}++state_.rejected;return false;}
bool StationAirlockRepair::seal(){if(!state_.leaks[state_.module]||state_.kits==0){++state_.rejected;return false;}state_.leaks[state_.module]=false;--state_.kits;++state_.sealed;return true;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;StationAirlockRepair s({10,10},{false,true},{{0,1}},1);return s.set_airlock(0,true)&&s.move(1)&&s.seal()&&s.snapshot().sealed==1?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;StationAirlockRepair s({10,9},{true,false},{{0,1}},0);auto before=s.snapshot();int f=0;f+=s.set_airlock(0,true);f+=s.move(1);f+=s.seal();auto after=s.snapshot();f+=before.module!=after.module||after.rejected!=3;return f;}
"""),
RobotCase(
"sim-museum-guide","museum-tour-planner","Museum Tour Planner","closure-aware-weighted-tour",
"Plan minimum weighted gallery legs to exhibits while respecting closures.",
"MuseumTourPlanner(rooms,edges).plan(entrance,exhibits,closed)","std::priority_queue",
r"""# Instructions

Gallery edges are undirected with positive walking distance. For each requested exhibit
in order, append a minimum-distance path from the current room; repeated requests at
the current room add no distance. Closed rooms cannot be entered, including a requested
exhibit or entrance. Dijkstra ties choose the smaller predecessor room. If any leg is
unreachable, return `complete=false`, retain the route through prior completed legs,
and report that exhibit in `unreachable_exhibit`.
""",
r"""#pragma once
#include <vector>
namespace curriculum {struct GalleryEdge{int a,b,distance;};struct Tour{bool complete=false;int distance=0,unreachable_exhibit=-1;std::vector<int> rooms;};
class MuseumTourPlanner{int rooms_;std::vector<GalleryEdge> edges_;public:MuseumTourPlanner(int,std::vector<GalleryEdge>);Tour plan(int,const std::vector<int>&,const std::vector<int>&)const;};}
""",_starter("MuseumTourPlanner"),
r"""#include "task.h"
#include <algorithm>
#include <limits>
#include <queue>
#include <stdexcept>
namespace curriculum {MuseumTourPlanner::MuseumTourPlanner(int n,std::vector<GalleryEdge> e):rooms_(n),edges_(std::move(e)){if(n<=0)throw std::invalid_argument("rooms");for(auto x:edges_)if(x.a<0||x.b<0||x.a>=n||x.b>=n||x.distance<=0)throw std::invalid_argument("edge");}
Tour MuseumTourPlanner::plan(int start,const std::vector<int>& exhibits,const std::vector<int>& closed)const{if(start<0||start>=rooms_)throw std::invalid_argument("start");auto is_closed=[&](int v){return std::find(closed.begin(),closed.end(),v)!=closed.end();};Tour out;out.rooms.push_back(start);if(is_closed(start)){out.unreachable_exhibit=start;return out;}int at=start,inf=std::numeric_limits<int>::max();
 for(int goal:exhibits){if(goal<0||goal>=rooms_||is_closed(goal)){out.unreachable_exhibit=goal;return out;}std::vector<int>d(rooms_,inf),p(rooms_,-1);using N=std::pair<int,int>;std::priority_queue<N,std::vector<N>,std::greater<N>>q;d[at]=0;q.push({0,at});while(!q.empty()){auto [cost,u]=q.top();q.pop();if(cost!=d[u])continue;for(auto e:edges_){int v=-1,w=e.distance;if(e.a==u)v=e.b;else if(e.b==u)v=e.a;if(v<0||is_closed(v))continue;if(cost+w<d[v]||(cost+w==d[v]&&u<p[v])){d[v]=cost+w;p[v]=u;q.push({d[v],v});}}}if(d[goal]==inf){out.unreachable_exhibit=goal;return out;}std::vector<int>leg;for(int v=goal;v!=at;v=p[v])leg.push_back(v);std::reverse(leg.begin(),leg.end());out.rooms.insert(out.rooms.end(),leg.begin(),leg.end());out.distance+=d[goal];at=goal;}out.complete=true;return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;MuseumTourPlanner p(4,{{0,1,5},{0,2,1},{2,1,1},{1,3,1}});auto t=p.plan(0,{1,3},{});return t.complete&&t.distance==3&&t.rooms==std::vector<int>({0,2,1,3})?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;MuseumTourPlanner p(3,{{0,1,1},{1,2,1}});auto t=p.plan(0,{1,2},{2});return !t.complete&&t.distance==1&&t.unreachable_exhibit==2?0:1;}
"""),
RobotCase(
"sim-recycling-sorter","recycling-conveyor-controller","Recycling Conveyor Controller","simultaneous-conveyor-ticks",
"Advance staged conveyor slots simultaneously and latch routing jams.",
"RecyclingConveyorController(slots,bin_types).tick(arrivals); clear_jam; snapshot","for(std::size_t i=slots_.size();i-- > 1;)",
r"""# Instructions

The conveyor has at least two slots and each `Item{id,material}` has a positive unique
ID. On a tick, if jammed, nothing moves and all arrivals are rejected. Otherwise slots
advance simultaneously right-to-left; the terminal item is sorted only when its
material is a configured bin. An unknown terminal material latches a jam and remains
in place. At most one arrival may enter slot 0 after movement; multiple arrivals or an
occupied slot 0 latch a jam. `clear_jam` removes only an unknown terminal item.
""",
r"""#pragma once
#include <optional>
#include <string>
#include <vector>
namespace curriculum {struct Item{int id;std::string material;};struct TickResult{int moved=0,sorted=0,rejected=0;bool jammed=false;};struct ConveyorSnapshot{std::vector<std::optional<Item>> slots;std::vector<Item> sorted;bool jammed=false;};
class RecyclingConveyorController{std::vector<std::optional<Item>> slots_;std::vector<std::string> bins_;std::vector<Item> sorted_;bool jammed_=false;public:RecyclingConveyorController(std::size_t,std::vector<std::string>);TickResult tick(const std::vector<Item>&);bool clear_jam();ConveyorSnapshot snapshot()const;};}
""",_starter("RecyclingConveyorController"),
r"""#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {RecyclingConveyorController::RecyclingConveyorController(std::size_t n,std::vector<std::string>b):slots_(n),bins_(std::move(b)){if(n<2||bins_.empty())throw std::invalid_argument("input");}
TickResult RecyclingConveyorController::tick(const std::vector<Item>& arrivals){TickResult out;if(jammed_){out.rejected=arrivals.size();out.jammed=true;return out;}auto& last=slots_.back();if(last){if(std::find(bins_.begin(),bins_.end(),last->material)==bins_.end()){jammed_=true;out.jammed=true;out.rejected=arrivals.size();return out;}sorted_.push_back(*last);last.reset();++out.sorted;}
 for(std::size_t i=slots_.size();i-- > 1;)if(!slots_[i]&&slots_[i-1]){slots_[i]=slots_[i-1];slots_[i-1].reset();++out.moved;}
 if(arrivals.size()>1||(!arrivals.empty()&&slots_[0])){jammed_=true;out.rejected=arrivals.size();}else if(!arrivals.empty()){if(arrivals[0].id<=0){++out.rejected;}else slots_[0]=arrivals[0];}out.jammed=jammed_;return out;}
bool RecyclingConveyorController::clear_jam(){if(!jammed_)return false;auto& last=slots_.back();if(last&&std::find(bins_.begin(),bins_.end(),last->material)==bins_.end())last.reset();jammed_=false;return true;}
ConveyorSnapshot RecyclingConveyorController::snapshot()const{return{slots_,sorted_,jammed_};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;RecyclingConveyorController c(2,{"glass"});c.tick({{1,"glass"}});c.tick({});auto r=c.tick({});return r.sorted==1&&c.snapshot().sorted.size()==1?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;RecyclingConveyorController c(2,{"glass"});c.tick({{1,"metal"}});c.tick({});auto j=c.tick({});int f=0;f+=!j.jammed;f+=!c.clear_jam();f+=c.snapshot().jammed;f+=!c.tick({{2,"glass"},{3,"glass"}}).jammed;return f;}
"""),
RobotCase(
"sim-farm-irrigator","farm-pressure-irrigator","Farm Pressure Irrigator","difference-array-pressure-allocation",
"Apply overlapping range requests under a shared integer pressure budget.",
"FarmPressureIrrigator(cells,pressure).apply(requests)","difference[request.begin]",
r"""# Instructions

Each inclusive `IrrigationRequest{begin,end,units}` contributes non-negative requested
units to every covered cell. First accumulate all ranges with a difference array.
If total requested delivery is at most `pressure`, deliver it exactly. Otherwise
allocate `floor(request_i*pressure/total)` per cell, then give remaining units one at
a time to cells with larger fractional remainder, ties by smaller index. Invalid ranges
or negative units reject the whole call with no delivery. Zero total is valid.
""",
r"""#pragma once
#include <vector>
namespace curriculum {struct IrrigationRequest{int begin,end,units;};struct IrrigationReport{bool accepted=false;int used_pressure=0;std::vector<int> requested,delivered;};
class FarmPressureIrrigator{int cells_,pressure_;public:FarmPressureIrrigator(int,int);IrrigationReport apply(const std::vector<IrrigationRequest>&)const;};}
""",_starter("FarmPressureIrrigator"),
r"""#include "task.h"
#include <algorithm>
#include <numeric>
#include <stdexcept>
namespace curriculum {FarmPressureIrrigator::FarmPressureIrrigator(int c,int p):cells_(c),pressure_(p){if(c<=0||p<0)throw std::invalid_argument("input");}
IrrigationReport FarmPressureIrrigator::apply(const std::vector<IrrigationRequest>& requests)const{IrrigationReport out;std::vector<long long> difference(cells_+1);for(auto request:requests){if(request.begin<0||request.end<request.begin||request.end>=cells_||request.units<0)return out;difference[request.begin]+=request.units;difference[request.end+1]-=request.units;}out.requested.resize(cells_);long long run=0,total=0;for(int i=0;i<cells_;++i){run+=difference[i];out.requested[i]=static_cast<int>(run);total+=run;}out.delivered.assign(cells_,0);if(total==0){out.accepted=true;return out;}if(total<=pressure_){out.delivered=out.requested;out.used_pressure=static_cast<int>(total);out.accepted=true;return out;}
 std::vector<std::pair<long long,int>> remainder;int used=0;for(int i=0;i<cells_;++i){long long product=1LL*out.requested[i]*pressure_;out.delivered[i]=product/total;used+=out.delivered[i];remainder.push_back({-(product%total),i});}std::sort(remainder.begin(),remainder.end());for(int k=0;k<pressure_-used;++k)++out.delivered[remainder[k].second];out.used_pressure=pressure_;out.accepted=true;return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;FarmPressureIrrigator f(3,5);auto r=f.apply({{0,1,3},{1,2,1}});return r.accepted&&r.delivered==std::vector<int>({2,2,1})?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;FarmPressureIrrigator f(3,2);auto tie=f.apply({{0,2,1}});auto bad=f.apply({{-1,1,2}});return tie.delivered==std::vector<int>({1,1,0})&&!bad.accepted&&bad.delivered.empty()?0:1;}
"""),
RobotCase(
"sim-search-and-rescue","rescue-frontier-explorer","Rescue Frontier Explorer","weighted-frontier-target-extraction",
"Explore targets by traversal cost while accounting for rubble markers.",
"RescueFrontierExplorer(grid).explore(start,markers)","std::priority_queue<Node",
r"""# Instructions

Grid cells are `.` open, `#` blocked, `R` rubble, and `T` target. Entering open
or target costs 1; entering rubble costs 2 and consumes one marker. `explore` runs a
Dijkstra frontier over (cell,markers-used), then reports every reachable target ordered
by minimum cost and row/column ties. Each target includes its reconstructed path and
markers used. A target may not consume markers for later targets because results are
independent routes from the start. Invalid starts or marker counts throw.
""",
r"""#pragma once
#include <string>
#include <vector>
namespace curriculum {struct RescueCell{int row,col;bool operator==(const RescueCell&o)const{return row==o.row&&col==o.col;}};struct RescueTarget{RescueCell cell;int cost=0,markers_used=0;std::vector<RescueCell> path;};struct RescueReport{std::vector<RescueTarget> targets;};
class RescueFrontierExplorer{std::vector<std::string> grid_;public:explicit RescueFrontierExplorer(std::vector<std::string>);RescueReport explore(RescueCell,int)const;};}
""",_starter("RescueFrontierExplorer"),
r"""#include "task.h"
#include <algorithm>
#include <limits>
#include <queue>
#include <stdexcept>
namespace curriculum {RescueFrontierExplorer::RescueFrontierExplorer(std::vector<std::string> g):grid_(std::move(g)){if(grid_.empty()||grid_[0].empty())throw std::invalid_argument("grid");for(auto&r:grid_)if(r.size()!=grid_[0].size())throw std::invalid_argument("ragged");}
RescueReport RescueFrontierExplorer::explore(RescueCell s,int markers)const{int rows=grid_.size(),cols=grid_[0].size();if(s.row<0||s.row>=rows||s.col<0||s.col>=cols||grid_[s.row][s.col]=='#'||markers<0)throw std::invalid_argument("start");int stride=markers+1,n=rows*cols*stride,inf=std::numeric_limits<int>::max(),src=(s.row*cols+s.col)*stride;std::vector<int>d(n,inf),p(n,-1);using Node=std::pair<int,int>;std::priority_queue<Node,std::vector<Node>,std::greater<Node>>q;d[src]=0;q.push({0,src});int dr[4]={-1,0,0,1},dc[4]={0,-1,1,0};
 while(!q.empty()){auto [cost,state]=q.top();q.pop();if(cost!=d[state])continue;int cell=state/stride,used=state%stride,r=cell/cols,c=cell%cols;for(int k=0;k<4;++k){int nr=r+dr[k],nc=c+dc[k];if(nr<0||nr>=rows||nc<0||nc>=cols||grid_[nr][nc]=='#')continue;int add=grid_[nr][nc]=='R',nu=used+add;if(nu>markers)continue;int ns=(nr*cols+nc)*stride+nu,w=add?2:1;if(cost+w<d[ns]){d[ns]=cost+w;p[ns]=state;q.push({d[ns],ns});}}}
 RescueReport out;for(int r=0;r<rows;++r)for(int c=0;c<cols;++c)if(grid_[r][c]=='T'){int best=-1;for(int u=0;u<=markers;++u){int st=(r*cols+c)*stride+u;if(best<0||d[st]<d[best])best=st;}if(best>=0&&d[best]<inf){RescueTarget t{{r,c},d[best],best%stride,{}};for(int st=best;st>=0;st=p[st]){int cell=st/stride;t.path.push_back({cell/cols,cell%cols});if(st==src)break;}std::reverse(t.path.begin(),t.path.end());out.targets.push_back(std::move(t));}}std::sort(out.targets.begin(),out.targets.end(),[](const auto&a,const auto&b){if(a.cost!=b.cost)return a.cost<b.cost;if(a.cell.row!=b.cell.row)return a.cell.row<b.cell.row;return a.cell.col<b.cell.col;});return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;RescueFrontierExplorer e({".T","RT"});auto r=e.explore({0,0},1);return r.targets.size()==2&&r.targets[0].cell==RescueCell{0,1}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;RescueFrontierExplorer e({".#T","RR.","T.."});auto none=e.explore({0,0},0);auto some=e.explore({0,0},1);return none.targets.empty()&&some.targets.size()==2&&some.targets[0].cell==RescueCell{2,0}&&some.targets[0].markers_used==1?0:1;}
"""),
RobotCase(
"sim-airport-tug","airport-taxiway-scheduler","Airport Taxiway Scheduler","segment-interval-conflict-scheduling",
"Reserve taxiway segments at the earliest conflict-free time.",
"AirportTaxiwayScheduler(edges).schedule(path,earliest); reservations","while(conflict)",
r"""# Instructions

Taxiway edges are undirected and have positive travel durations. A reservation occupies
each path segment over a half-open interval [start,end). `schedule(path,earliest)`
finds the smallest common departure time >= earliest for which every sequential
segment interval avoids every prior reservation on that undirected segment. On a
conflict it advances departure just enough for that interval, then checks the full path
again. Back-to-back intervals do not conflict. Invalid paths return `accepted=false`
without adding reservations; negative earliest throws.
""",
r"""#pragma once
#include <vector>
namespace curriculum {struct TaxiEdge{int a,b,duration;};struct SegmentUse{int a,b,start,end;};struct Reservation{bool accepted=false;int departure=0,arrival=0;std::vector<SegmentUse> segments;};
class AirportTaxiwayScheduler{std::vector<TaxiEdge> edges_;std::vector<Reservation> reservations_;public:explicit AirportTaxiwayScheduler(std::vector<TaxiEdge>);Reservation schedule(const std::vector<int>&,int);const std::vector<Reservation>& reservations()const{return reservations_;}};}
""",_starter("AirportTaxiwayScheduler"),
r"""#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {AirportTaxiwayScheduler::AirportTaxiwayScheduler(std::vector<TaxiEdge> e):edges_(std::move(e)){for(auto x:edges_)if(x.a<0||x.b<0||x.a==x.b||x.duration<=0)throw std::invalid_argument("edge");}
Reservation AirportTaxiwayScheduler::schedule(const std::vector<int>& path,int earliest){if(earliest<0)throw std::invalid_argument("time");Reservation out;if(path.size()<2)return out;std::vector<int> durations;for(std::size_t i=1;i<path.size();++i){auto it=std::find_if(edges_.begin(),edges_.end(),[&](auto e){return(e.a==path[i-1]&&e.b==path[i])||(e.b==path[i-1]&&e.a==path[i]);});if(it==edges_.end())return out;durations.push_back(it->duration);}
 int departure=earliest;bool conflict=true;while(conflict){conflict=false;int offset=0,advance=departure;for(std::size_t i=0;i<durations.size();++i){int begin=departure+offset,end=begin+durations[i];int a=std::min(path[i],path[i+1]),b=std::max(path[i],path[i+1]);for(auto&r:reservations_)for(auto s:r.segments)if(std::min(s.a,s.b)==a&&std::max(s.a,s.b)==b&&begin<s.end&&s.start<end){conflict=true;advance=std::max(advance,s.end-offset);}offset+=durations[i];}if(conflict)departure=advance;}
 out.accepted=true;out.departure=departure;int time=departure;for(std::size_t i=0;i<durations.size();++i){out.segments.push_back({path[i],path[i+1],time,time+durations[i]});time+=durations[i];}out.arrival=time;reservations_.push_back(out);return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;AirportTaxiwayScheduler s({{0,1,3},{1,2,2}});auto a=s.schedule({0,1,2},0);auto b=s.schedule({1,0},0);return a.accepted&&b.departure==3?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;AirportTaxiwayScheduler s({{0,1,2}});auto a=s.schedule({0,1},0);auto b=s.schedule({1,0},2);auto before=s.reservations().size();auto bad=s.schedule({0,2},0);return a.arrival==2&&b.departure==2&&!bad.accepted&&s.reservations().size()==before?0:1;}
"""),
)
