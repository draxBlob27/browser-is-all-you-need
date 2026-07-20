"""Task-specific C++ contracts for grid-ownership-mapping v2 replacements."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GridCase:
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
    hidden_description: str = "task-specific adversarial, invalid-input, ordering, and tie cases"


def _starter(name: str) -> str:
    return f'#include "task.h"\nnamespace curriculum {{ /* Implement {name}. */ }}\n'


CASES = (
GridCase(
"ownership-airport-gates","airport-gate-closure-planner","Airport Gate Closure Planner","stable-interval-gate-assignment",
"Assign flights to compatible open gates in arrival order.","plan_gates(flights,gates,closed)->GatePlan","busy[g.name]",
r'''# Instructions

Implement `plan_gates`. Flights must have `arrival < departure`; gates have unique
names and a maximum size (`S < M < L`). Closed gates are unavailable. Process
flights in input order and assign the lexicographically smallest open compatible
gate whose previous flight departs no later than this arrival. Invalid input returns
`valid=false` atomically. Unassignable flights receive `'-'` and increment the count.
''',
r'''#pragma once
#include <vector>
namespace curriculum { struct Flight{int arrival,departure;char size;}; struct Gate{char name,max_size;}; struct GatePlan{bool valid=true;std::vector<char> assignment;int unassigned=0;}; GatePlan plan_gates(const std::vector<Flight>&,const std::vector<Gate>&,const std::vector<char>&); }
''',_starter("plan_gates"),
r'''#include "task.h"
#include <algorithm>
#include <map>
#include <set>
#include <string>
namespace curriculum { GatePlan plan_gates(const std::vector<Flight>& fs,const std::vector<Gate>& gs,const std::vector<char>& closed){GatePlan out;std::map<char,int> busy;std::map<char,char> cap;std::set<char> shut(closed.begin(),closed.end());for(auto g:gs){if(cap.count(g.name)||std::string("SML").find(g.max_size)==std::string::npos){out.valid=false;return out;}cap[g.name]=g.max_size;busy[g.name]=-1;}for(char c:closed)if(!cap.count(c)){out.valid=false;return out;}auto rank=[](char x){return x=='S'?0:x=='M'?1:x=='L'?2:-1;};for(auto f:fs){if(f.arrival>=f.departure||rank(f.size)<0){out.valid=false;out.assignment.clear();out.unassigned=0;return out;}char pick='-';for(auto [name,size]:cap)if(!shut.count(name)&&rank(size)>=rank(f.size)&&busy[name]<=f.arrival){pick=name;break;}out.assignment.push_back(pick);if(pick=='-')++out.unassigned;else busy[pick]=f.departure;}return out;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto p=plan_gates({{0,4,'M'},{4,6,'S'},{1,3,'L'}},{{'B','L'},{'A','M'}},{});return p.valid&&p.assignment==std::vector<char>{'A','A','B'}?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto p=plan_gates({{0,3,'S'},{1,2,'S'}},{{'A','S'}},{'A'});f+=!(p.valid&&p.unassigned==2);auto bad=plan_gates({{2,2,'S'}},{{'A','S'}},{});f+=bad.valid;auto endpoint=plan_gates({{0,2,'S'},{2,3,'S'}},{{'A','S'}},{});f+=endpoint.assignment!=std::vector<char>({'A','A'});return f;}
'''),
GridCase(
"ownership-campsite-map","campsite-access-zone-router","Campsite Access Zone Router","multi-source-bfs-owner-ties",
"Route every walkable plot to its nearest entrance.","route_access(grid,entrances)->AccessReport","std::queue<int>",
r'''# Instructions

Implement four-neighbor multi-source BFS on a rectangular grid where `#` is blocked
and every other cell is walkable. Entrances are zero-based cells and their vector
index is their owner. Store row-major distance and owner arrays (`-1` for blocked or
unreachable); equal distances choose the smaller entrance index. Invalid or duplicate
entrances and ragged grids return `rectangular=false` atomically.
''',
r'''#pragma once
#include <string>
#include <vector>
namespace curriculum { struct Cell{int row,col;}; struct AccessReport{bool rectangular=true;std::vector<int> distance,owner;int unreachable=0;}; AccessReport route_access(const std::vector<std::string>&,const std::vector<Cell>&); }
''',_starter("route_access"),
r'''#include "task.h"
#include <queue>
#include <set>
namespace curriculum { AccessReport route_access(const std::vector<std::string>& g,const std::vector<Cell>& starts){AccessReport o;if(g.empty())return o;int h=g.size(),w=g[0].size();for(auto& r:g)if((int)r.size()!=w){o.rectangular=false;return o;}o.distance.assign(h*w,-1);o.owner.assign(h*w,-1);std::queue<int> q;std::set<int> used;for(int i=0;i<(int)starts.size();++i){auto p=starts[i];int x=p.row*w+p.col;if(p.row<0||p.row>=h||p.col<0||p.col>=w||g[p.row][p.col]=='#'||!used.insert(x).second){o={false,{},{},0};return o;}o.distance[x]=0;o.owner[x]=i;q.push(x);}int dr[4]={-1,0,0,1},dc[4]={0,-1,1,0};while(!q.empty()){int x=q.front();q.pop();int r=x/w,c=x%w;for(int d=0;d<4;++d){int nr=r+dr[d],nc=c+dc[d];if(nr<0||nr>=h||nc<0||nc>=w||g[nr][nc]=='#')continue;int y=nr*w+nc,nd=o.distance[x]+1;if(o.distance[y]<0||nd<o.distance[y]||(nd==o.distance[y]&&o.owner[x]<o.owner[y])){o.distance[y]=nd;o.owner[y]=o.owner[x];q.push(y);}}}for(int i=0;i<h*w;++i)if(g[i/w][i%w]!='#'&&o.owner[i]<0)++o.unreachable;return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto r=route_access({"...",".#.","..."},{{0,0},{0,2}});return r.rectangular&&r.owner[1]==0&&r.distance[8]==2?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto r=route_access({".#.","###","..."},{{0,0}});f+=r.unreachable!=4;f+=route_access({"..","."},{}).rectangular;f+=route_access({".."},{{0,0},{0,0}}).rectangular;return f;}
'''),
GridCase(
"ownership-city-gardens","garden-boundary-ledger","Garden Boundary Ledger","edge-sweep-pair-aggregation",
"Measure shared and exterior garden boundaries.","measure_boundaries(grid)->GardenLedger","shared[{std::min",
r'''# Instructions

Uppercase letters are garden owners and `.` is outside. Scan a rectangular diagram.
For each orthogonal edge between different owners, add once to the unordered owner
pair. For an owner edge touching the diagram boundary or `.`, add to that owner's
exterior length. Return shared pairs and exterior totals in ascending owner order.
Invalid symbols or ragged rows set `valid=false`.
''',
r'''#pragma once
#include <string>
#include <utility>
#include <vector>
namespace curriculum { struct SharedEdge{char low,high;int length;bool operator==(const SharedEdge& o)const{return low==o.low&&high==o.high&&length==o.length;}}; struct GardenLedger{bool valid=true;std::vector<SharedEdge> shared;std::vector<std::pair<char,int>> exterior;}; GardenLedger measure_boundaries(const std::vector<std::string>&); }
''',_starter("measure_boundaries"),
r'''#include "task.h"
#include <cctype>
#include <map>
namespace curriculum { GardenLedger measure_boundaries(const std::vector<std::string>& g){GardenLedger o;if(g.empty())return o;int h=g.size(),w=g[0].size();std::map<std::pair<char,char>,int> shared;std::map<char,int> ext;for(auto& r:g)if((int)r.size()!=w){o.valid=false;return o;}for(int r=0;r<h;++r)for(int c=0;c<w;++c){char a=g[r][c];if(a!='.'&&!std::isupper(static_cast<unsigned char>(a))){o.valid=false;return o;}if(a=='.')continue;int dr[4]={-1,1,0,0},dc[4]={0,0,-1,1};for(int d=0;d<4;++d){int nr=r+dr[d],nc=c+dc[d];if(nr<0||nr>=h||nc<0||nc>=w||g[nr][nc]=='.')++ext[a];else if((d==1||d==3)&&g[nr][nc]!=a){char b=g[nr][nc];shared[{std::min(a,b),std::max(a,b)}]++;}}}for(auto [p,n]:shared)o.shared.push_back({p.first,p.second,n});for(auto p:ext)o.exterior.push_back(p);return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto x=measure_boundaries({"AB","A."});return x.valid&&x.shared==std::vector<SharedEdge>{{'A','B',1}}&&x.exterior==std::vector<std::pair<char,int>>{{'A',5},{'B',3}}?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto x=measure_boundaries({"AAA","A.A","AAA"});f+=x.exterior[0].second!=16;f+=measure_boundaries({"A","AA"}).valid;f+=measure_boundaries({"a"}).valid;return f;}
'''),
GridCase(
"ownership-construction-lots","parcel-component-perimeters","Parcel Component Perimeters","component-flood-perimeter",
"Report area and perimeter for each connected parcel component.","survey_parcels(grid)->vector<Parcel>","++p.perimeter",
r'''# Instructions

Uppercase cells are parcels and `.` is empty. A parcel component uses four-neighbor
connectivity and same-letter cells. Report every component in row-major anchor order
with label, area, perimeter, and anchor. Different components with the same label stay
separate. Ragged or illegal grids return an empty vector.
''',
r'''#pragma once
#include <string>
#include <vector>
namespace curriculum { struct Parcel{char label;int area,perimeter,anchor_row,anchor_col;bool operator==(const Parcel&o)const{return label==o.label&&area==o.area&&perimeter==o.perimeter&&anchor_row==o.anchor_row&&anchor_col==o.anchor_col;}}; std::vector<Parcel> survey_parcels(const std::vector<std::string>&); }
''',_starter("survey_parcels"),
r'''#include "task.h"
#include <cctype>
#include <queue>
namespace curriculum { std::vector<Parcel> survey_parcels(const std::vector<std::string>& g){std::vector<Parcel> out;if(g.empty())return out;int h=g.size(),w=g[0].size();for(auto&r:g)if((int)r.size()!=w)return{};for(auto&r:g)for(char x:r)if(x!='.'&&!std::isupper(static_cast<unsigned char>(x)))return{};std::vector<bool> seen(h*w);int dr[4]={-1,1,0,0},dc[4]={0,0,-1,1};for(int r=0;r<h;++r)for(int c=0;c<w;++c)if(g[r][c]!='.'&&!seen[r*w+c]){Parcel p{g[r][c],0,0,r,c};std::queue<int> q;q.push(r*w+c);seen[r*w+c]=true;while(!q.empty()){int x=q.front();q.pop(),++p.area;int a=x/w,b=x%w;for(int d=0;d<4;++d){int nr=a+dr[d],nc=b+dc[d];if(nr<0||nr>=h||nc<0||nc>=w||g[nr][nc]!=p.label)++p.perimeter;else if(!seen[nr*w+nc]){seen[nr*w+nc]=true;q.push(nr*w+nc);}}}out.push_back(p);}return out;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto p=survey_parcels({"AA.","A.B","..B"});return p==std::vector<Parcel>{{'A',3,8,0,0},{'B',2,6,1,2}}?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto p=survey_parcels({"A.A"});f+=p.size()!=2||p[0].perimeter!=4||p[1].anchor_col!=2;f+=!survey_parcels({"AA","A"}).empty();f+=!survey_parcels({"?"}).empty();return f;}
'''),
GridCase(
"ownership-data-center-racks","rack-contiguous-allocation-audit","Rack Contiguous Allocation Audit","column-interval-gap-audit",
"Find customer allocation gaps inside rack-column intervals.","audit_racks(grid)->RackAudit","seen_gap",
r'''# Instructions

Each uppercase cell is a customer slot and `.` is empty. In each column, a customer's
allocation is contiguous exactly when every row from its first to last occurrence has
that customer. Emit one issue for each nonmatching interior cell, ordered by column,
customer, then row. Report total occupied slots. Ragged or illegal input is invalid.
''',
r'''#pragma once
#include <string>
#include <vector>
namespace curriculum { struct RackIssue{char customer;int column,row;bool operator==(const RackIssue&o)const{return customer==o.customer&&column==o.column&&row==o.row;}}; struct RackAudit{bool valid=true;std::vector<RackIssue> gaps;int occupied=0;}; RackAudit audit_racks(const std::vector<std::string>&); }
''',_starter("audit_racks"),
r'''#include "task.h"
#include <cctype>
#include <map>
namespace curriculum { RackAudit audit_racks(const std::vector<std::string>& g){RackAudit o;if(g.empty())return o;int h=g.size(),w=g[0].size();for(auto&r:g)if((int)r.size()!=w){o.valid=false;return o;}for(int c=0;c<w;++c){std::map<char,std::pair<int,int>> span;for(int r=0;r<h;++r){char x=g[r][c];if(x=='.')continue;if(!std::isupper(static_cast<unsigned char>(x))){o.valid=false;o.gaps.clear();o.occupied=0;return o;}++o.occupied;if(!span.count(x))span[x]={r,r};else span[x].second=r;}for(auto [x,p]:span)for(int r=p.first;r<=p.second;++r){bool seen_gap=g[r][c]!=x;if(seen_gap)o.gaps.push_back({x,c,r});}}return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto a=audit_racks({"A.","..","A."});return a.valid&&a.occupied==2&&a.gaps==std::vector<RackIssue>{{'A',0,1}}?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto a=audit_racks({"AB","AB",".B"});f+=!a.gaps.empty()||a.occupied!=5;f+=audit_racks({"A","AA"}).valid;f+=audit_racks({"1"}).valid;return f;}
'''),
GridCase(
"ownership-farm-leases","lease-rectangle-overlay-resolver","Lease Rectangle Overlay Resolver","ordered-rectangle-cell-ledger",
"Resolve ordered rectangular lease claims and contested cells.","resolve_leases(rows,cols,claims)->LeaseResult","cell_claimants",
r'''# Instructions

Claims are half-open rectangles. Apply them in input order. A cell first receives the
claim's farmer index; repeated coverage by the same farmer is idempotent. Coverage by
a different farmer makes that cell contested (`-2`) permanently. Unclaimed is `-1`.
Invalid dimensions, empty farmer names, or malformed/out-of-range rectangles return
`valid=false` with empty ledgers.
''',
r'''#pragma once
#include <string>
#include <vector>
namespace curriculum { struct Claim{std::string farmer;int top,left,bottom,right;}; struct LeaseResult{bool valid=true;std::vector<int> owner,contested;}; LeaseResult resolve_leases(int,int,const std::vector<Claim>&); }
''',_starter("resolve_leases"),
r'''#include "task.h"
#include <map>
namespace curriculum { LeaseResult resolve_leases(int rows,int cols,const std::vector<Claim>& cs){LeaseResult o;if(rows<=0||cols<=0){o.valid=false;return o;}o.owner.assign(rows*cols,-1);std::map<std::string,int> ids;for(auto& c:cs){if(c.farmer.empty()||c.top<0||c.left<0||c.top>=c.bottom||c.left>=c.right||c.bottom>rows||c.right>cols){return{false,{},{}};}if(!ids.count(c.farmer))ids[c.farmer]=ids.size();int id=ids[c.farmer];for(int r=c.top;r<c.bottom;++r)for(int q=c.left;q<c.right;++q){int x=r*cols+q;std::vector<int> cell_claimants={o.owner[x],id};if(o.owner[x]==-1)o.owner[x]=id;else if(o.owner[x]!=id&&o.owner[x]!=-2){o.owner[x]=-2;o.contested.push_back(x);}}}return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto r=resolve_leases(2,3,{{"a",0,0,2,2},{"b",0,1,1,3}});return r.valid&&r.owner==std::vector<int>{0,-2,1,0,0,-1}&&r.contested==std::vector<int>{1}?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto r=resolve_leases(1,2,{{"a",0,0,1,2},{"a",0,1,1,2}});f+=!r.contested.empty();f+=resolve_leases(2,2,{{"",0,0,1,1}}).valid;f+=resolve_leases(2,2,{{"x",1,1,1,2}}).valid;return f;}
'''),
GridCase(
"ownership-flood-barriers","shoreline-barrier-coverage","Shoreline Barrier Coverage","sorted-interval-union-gaps",
"Merge barrier spans and report uncovered shoreline gaps.","cover_shoreline(length,barriers)->Coverage","merged_end",
r'''# Instructions

Barrier spans are half-open within `[0,length)`. Validate all spans and nonempty
district names. Sort spans by begin/end and return maximal uncovered gaps; touching
or overlapping barriers form continuous coverage. `district_lengths` follows first
district appearance and counts each district's union length independently. Zero
length is valid. Invalid input is atomic.
''',
r'''#pragma once
#include <string>
#include <vector>
namespace curriculum { struct Barrier{int begin,end;std::string district;}; struct Gap{int begin,end;bool operator==(const Gap&o)const{return begin==o.begin&&end==o.end;}}; struct Coverage{bool valid=true;std::vector<Gap> gaps;std::vector<int> district_lengths;}; Coverage cover_shoreline(int,const std::vector<Barrier>&); }
''',_starter("cover_shoreline"),
r'''#include "task.h"
#include <algorithm>
#include <map>
namespace curriculum { Coverage cover_shoreline(int n,const std::vector<Barrier>& bs){Coverage o;if(n<0){o.valid=false;return o;}std::vector<Barrier> all=bs;std::vector<std::string> order;std::map<std::string,std::vector<Gap>> by;for(auto b:bs){if(b.district.empty()||b.begin<0||b.begin>=b.end||b.end>n)return{false,{},{}};if(!by.count(b.district))order.push_back(b.district);by[b.district].push_back({b.begin,b.end});}std::sort(all.begin(),all.end(),[](auto&a,auto&b){return a.begin<b.begin||(a.begin==b.begin&&a.end<b.end);});int merged_end=0;for(auto b:all){if(b.begin>merged_end)o.gaps.push_back({merged_end,b.begin});merged_end=std::max(merged_end,b.end);}if(merged_end<n)o.gaps.push_back({merged_end,n});for(auto& name:order){auto v=by[name];std::sort(v.begin(),v.end(),[](auto&a,auto&b){return a.begin<b.begin;});int sum=0,s=-1,e=-1;for(auto x:v){if(s<0||x.begin>e){if(s>=0)sum+=e-s;s=x.begin;e=x.end;}else e=std::max(e,x.end);}if(s>=0)sum+=e-s;o.district_lengths.push_back(sum);}return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto c=cover_shoreline(10,{{1,4,"a"},{3,6,"b"},{8,10,"a"}});return c.valid&&c.gaps==std::vector<Gap>{{0,1},{6,8}}&&c.district_lengths==std::vector<int>{5,3}?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto c=cover_shoreline(5,{{0,2,"a"},{2,5,"a"}});f+=!c.gaps.empty()||c.district_lengths[0]!=5;f+=cover_shoreline(3,{{2,2,"x"}}).valid;f+=!cover_shoreline(0,{}).valid;return f;}
'''),
GridCase(
"ownership-harbor-quays","quay-concession-component-audit","Quay Concession Component Audit","owner-sensitive-component-ledger",
"Inventory connected concession components and disconnected owners.","audit_quays(grid)->QuayAudit","component_count",
r'''# Instructions

Uppercase cells are concession owners and `.` is water. Use four-neighbor connectivity
between equal labels. Emit each component in row-major anchor order with its cell
count. Emit an owner once in ascending order when it has more than one component.
Ragged or illegal grids are invalid atomically.
''',
r'''#pragma once
#include <string>
#include <vector>
namespace curriculum { struct QuayComponent{char owner;int anchor_row,anchor_col,cells;}; struct QuayAudit{bool valid=true;std::vector<QuayComponent> components;std::vector<char> disconnected;}; QuayAudit audit_quays(const std::vector<std::string>&); }
''',_starter("audit_quays"),
r'''#include "task.h"
#include <cctype>
#include <map>
#include <queue>
namespace curriculum { QuayAudit audit_quays(const std::vector<std::string>& g){QuayAudit o;if(g.empty())return o;int h=g.size(),w=g[0].size();for(auto&r:g)if((int)r.size()!=w)return{false,{},{}};std::vector<bool>s(h*w);std::map<char,int> component_count;int dr[4]={-1,1,0,0},dc[4]={0,0,-1,1};for(int r=0;r<h;++r)for(int c=0;c<w;++c){char z=g[r][c];if(z!='.'&&!std::isupper(static_cast<unsigned char>(z)))return{false,{},{}};if(z=='.'||s[r*w+c])continue;QuayComponent p{z,r,c,0};std::queue<int>q;q.push(r*w+c);s[r*w+c]=true;while(!q.empty()){int x=q.front();q.pop();++p.cells;for(int d=0;d<4;++d){int nr=x/w+dr[d],nc=x%w+dc[d];if(nr>=0&&nr<h&&nc>=0&&nc<w&&!s[nr*w+nc]&&g[nr][nc]==z){s[nr*w+nc]=true;q.push(nr*w+nc);}}}o.components.push_back(p);++component_count[z];}for(auto [x,n]:component_count)if(n>1)o.disconnected.push_back(x);return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto a=audit_quays({"AA.","..A","BB."});return a.valid&&a.components.size()==3&&a.disconnected==std::vector<char>{'A'}?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto a=audit_quays({"A.",".A"});f+=a.components.size()!=2;f+=audit_quays({"A","AA"}).valid;f+=audit_quays({"#"}).valid;return f;}
'''),
GridCase(
"ownership-lab-benches","bench-contact-compatibility","Bench Contact Compatibility","canonical-contact-rule-scan",
"Validate experiment contacts using an explicit compatibility table.","audit_contacts(grid,rules)->BenchAudit","rule[{low,high}]",
r'''# Instructions

Uppercase cells are experiments and `.` is empty. Rules name distinct experiment
pairs and whether contact is allowed; pair order is symmetric. Duplicate or conflicting
pair rules invalidate. Every distinct right/down neighboring pair requires an explicit
allowed rule; otherwise emit that edge in row-major/direction order. Same-symbol
contacts are always allowed. Unknown symbols and ragged grids invalidate.
''',
r'''#pragma once
#include <string>
#include <vector>
namespace curriculum { struct ContactRule{char first,second;bool allowed;}; struct Contact{int row,col,next_row,next_col;}; struct BenchAudit{bool valid=true;std::vector<Contact> forbidden;}; BenchAudit audit_contacts(const std::vector<std::string>&,const std::vector<ContactRule>&); }
''',_starter("audit_contacts"),
r'''#include "task.h"
#include <cctype>
#include <map>
#include <set>
namespace curriculum { BenchAudit audit_contacts(const std::vector<std::string>& g,const std::vector<ContactRule>& rs){BenchAudit o;std::map<std::pair<char,char>,bool> rule;std::set<char> known;for(auto x:rs){char a=std::min(x.first,x.second),b=std::max(x.first,x.second);if(a==b||!std::isupper((unsigned char)a)||!std::isupper((unsigned char)b)||rule.count({a,b}))return{false,{}};rule[{a,b}]=x.allowed;known.insert(a);known.insert(b);}if(g.empty())return o;int h=g.size(),w=g[0].size();for(auto&r:g)if((int)r.size()!=w)return{false,{}};for(int r=0;r<h;++r)for(int c=0;c<w;++c){char a=g[r][c];if(a!='.'&&!known.count(a))return{false,{}};int dr[2]={0,1},dc[2]={1,0};for(int d=0;d<2&&a!='.';++d){int nr=r+dr[d],nc=c+dc[d];if(nr<h&&nc<w&&g[nr][nc]!='.'&&g[nr][nc]!=a){char b=g[nr][nc],low=std::min(a,b),high=std::max(a,b);if(!rule.count({low,high})||!rule[{low,high}])o.forbidden.push_back({r,c,nr,nc});}}}return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto a=audit_contacts({"AB","AA"},{{'A','B',false}});return a.valid&&a.forbidden.size()==2?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;f+=audit_contacts({"AB"},{{'B','A',true},{'A','B',true}}).valid;f+=audit_contacts({"AC"},{{'A','B',true}}).valid;auto a=audit_contacts({"AA"},{{'A','B',false}});f+=!a.forbidden.empty();return f;}
'''),
GridCase(
"ownership-marina-slips","marina-berth-ray-attribution","Marina Berth Ray Attribution","column-ray-stop-collision",
"Extend vessel ownership rays down berth columns.","map_berths(diagram)->BerthMap","for(int r=mr+1",
r'''# Instructions

Uppercase vessel markers cast ownership downward through `:` berth cells. A `#` pier
or `.` water stops a ray. Markers themselves are occupied and also stop earlier rays.
Vessel letters must be unique. Owners appear in marker row-major order and contain
linear cell indices including the marker. If a berth was already claimed, record its
index as a collision and keep the first owner. Ragged or illegal input is invalid.
''',
r'''#pragma once
#include <string>
#include <vector>
namespace curriculum { struct BerthOwner{char vessel;std::vector<int> cells;}; struct BerthMap{bool valid=true;std::vector<BerthOwner> owners;std::vector<int> collisions;}; BerthMap map_berths(const std::vector<std::string>&); }
''',_starter("map_berths"),
r'''#include "task.h"
#include <cctype>
#include <set>
namespace curriculum { BerthMap map_berths(const std::vector<std::string>& g){BerthMap o;if(g.empty())return o;int h=g.size(),w=g[0].size();for(auto&r:g)if((int)r.size()!=w)return{false,{},{}};std::set<char> names;std::vector<int> claim(h*w,-1);for(int mr=0;mr<h;++mr)for(int c=0;c<w;++c){char x=g[mr][c];if(x!='.'&&x!='#'&&x!=':'&&!std::isupper((unsigned char)x))return{false,{},{}};if(!std::isupper((unsigned char)x))continue;if(!names.insert(x).second)return{false,{},{}};int id=o.owners.size();o.owners.push_back({x,{mr*w+c}});claim[mr*w+c]=id;for(int r=mr+1;r<h;++r){char z=g[r][c];if(z!=':')break;int p=r*w+c;if(claim[p]<0){claim[p]=id;o.owners[id].cells.push_back(p);}else o.collisions.push_back(p);}}return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto b=map_berths({"A.B",":.:",":#:"});return b.valid&&b.owners.size()==2&&b.owners[0].cells==std::vector<int>{0,3,6}&&b.owners[1].cells.size()==3?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto b=map_berths({"A","#",":"});f+=b.owners[0].cells.size()!=1;f+=map_berths({"AA"}).valid;f+=map_berths({"?"}).valid;return f;}
'''),
GridCase(
"ownership-market-stalls","market-stall-frontage-runs","Market Stall Frontage Runs","maximal-row-run-frontage",
"Extract maximal vendor runs and street frontage totals.","scan_stalls(grid)->StallReport","runs.push_back",
r'''# Instructions

Uppercase cells are vendors and `.` is empty. Emit maximal horizontal same-vendor
runs in row-major order using half-open columns. A vendor's street frontage is the
number of its cells whose lower neighbor is outside the grid or empty. Return frontage
totals in ascending vendor order. Ragged or illegal diagrams are invalid.
''',
r'''#pragma once
#include <string>
#include <utility>
#include <vector>
namespace curriculum { struct StallRun{char vendor;int row,begin,end;bool operator==(const StallRun&o)const{return vendor==o.vendor&&row==o.row&&begin==o.begin&&end==o.end;}}; struct StallReport{bool valid=true;std::vector<StallRun> runs;std::vector<std::pair<char,int>> frontage;}; StallReport scan_stalls(const std::vector<std::string>&); }
''',_starter("scan_stalls"),
r'''#include "task.h"
#include <cctype>
#include <map>
namespace curriculum { StallReport scan_stalls(const std::vector<std::string>& g){StallReport o;if(g.empty())return o;int h=g.size(),w=g[0].size();for(auto&r:g)if((int)r.size()!=w)return{false,{},{}};std::map<char,int> front;for(int r=0;r<h;++r){for(int c=0;c<w;){char x=g[r][c];if(x!='.'&&!std::isupper((unsigned char)x))return{false,{},{}};if(x=='.'){++c;continue;}int begin=c;while(c<w&&g[r][c]==x){if(r+1==h||g[r+1][c]=='.')++front[x];++c;}o.runs.push_back({x,r,begin,c});}}for(auto p:front)o.frontage.push_back(p);return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto s=scan_stalls({"AA.B","A..B"});return s.valid&&s.runs==std::vector<StallRun>{{'A',0,0,2},{'B',0,3,4},{'A',1,0,1},{'B',1,3,4}}&&s.frontage==std::vector<std::pair<char,int>>{{'A',2},{'B',1}}?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto s=scan_stalls({"AAA"});f+=s.runs.size()!=1||s.runs[0].end!=3||s.frontage[0].second!=3;f+=scan_stalls({"A","AA"}).valid;f+=scan_stalls({"1"}).valid;return f;}
'''),
GridCase(
"ownership-museum-galleries","gallery-room-label-audit","Gallery Room Label Audit","wall-room-label-flood",
"Require exactly one exhibit label in each wall-bounded room.","audit_rooms(grid)->GalleryAudit","labels.size()!=1",
r'''# Instructions

`#` is wall, `.` is room floor, and uppercase cells are exhibit labels. Flood every
four-neighbor non-wall room in row-major anchor order. A valid room has exactly one
distinct label cell; report its label and number of floor cells (including label cells).
Otherwise report the room anchor in `invalid_rooms`. Ragged or illegal input sets
`rectangular=false`.
''',
r'''#pragma once
#include <string>
#include <utility>
#include <vector>
namespace curriculum { struct Room{int anchor_row,anchor_col;char exhibit;int floor_cells;}; struct GalleryAudit{bool rectangular=true;std::vector<Room> rooms;std::vector<std::pair<int,int>> invalid_rooms;}; GalleryAudit audit_rooms(const std::vector<std::string>&); }
''',_starter("audit_rooms"),
r'''#include "task.h"
#include <cctype>
#include <queue>
#include <set>
namespace curriculum { GalleryAudit audit_rooms(const std::vector<std::string>& g){GalleryAudit o;if(g.empty())return o;int h=g.size(),w=g[0].size();for(auto&r:g)if((int)r.size()!=w)return{false,{},{}};std::vector<bool>s(h*w);int dr[4]={-1,1,0,0},dc[4]={0,0,-1,1};for(int r=0;r<h;++r)for(int c=0;c<w;++c){char z=g[r][c];if(z!='#'&&z!='.'&&!std::isupper((unsigned char)z))return{false,{},{}};if(z=='#'||s[r*w+c])continue;int cells=0;std::set<char> labels;std::queue<int>q;q.push(r*w+c);s[r*w+c]=true;while(!q.empty()){int x=q.front();q.pop();++cells;char a=g[x/w][x%w];if(std::isupper((unsigned char)a))labels.insert(a);for(int d=0;d<4;++d){int nr=x/w+dr[d],nc=x%w+dc[d];if(nr>=0&&nr<h&&nc>=0&&nc<w&&!s[nr*w+nc]&&g[nr][nc]!='#'){s[nr*w+nc]=true;q.push(nr*w+nc);}}}if(labels.size()!=1)o.invalid_rooms.push_back({r,c});else o.rooms.push_back({r,c,*labels.begin(),cells});}return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto a=audit_rooms({"#####","#A#B#","#.#.#","#####"});return a.rectangular&&a.rooms.size()==2&&a.invalid_rooms.empty()?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto a=audit_rooms({"A.B"});f+=!a.rooms.empty()||a.invalid_rooms!=std::vector<std::pair<int,int>>{{0,0}};auto u=audit_rooms({"..."});f+=u.invalid_rooms.size()!=1;f+=audit_rooms({"#","##"}).rectangular;return f;}
'''),
GridCase(
"ownership-office-desks","office-desk-voronoi-assignment","Office Desk Voronoi Assignment","layered-team-voronoi",
"Assign desks to the nearest team seed with stable ties.","assign_desks(grid,seeds)->DeskMap","teams[y].insert",
r'''# Instructions

`#` blocks movement and other cells are desks. Each seed has a unique uppercase team
and a unique valid walkable cell. Assign every reachable desk to the team at minimum
four-neighbor distance; equal-distance desks choose the alphabetically smallest team
and their linear indices appear in `tied`. Owners are row-major (`#` and unreachable
are `'-'`). Invalid grids or seeds return `valid=false`.
''',
r'''#pragma once
#include <string>
#include <vector>
namespace curriculum { struct DeskSeed{char team;int row,col;}; struct DeskMap{bool valid=true;std::vector<char> owner;std::vector<int> tied;}; DeskMap assign_desks(const std::vector<std::string>&,const std::vector<DeskSeed>&); }
''',_starter("assign_desks"),
r'''#include "task.h"
#include <cctype>
#include <queue>
#include <set>
namespace curriculum { DeskMap assign_desks(const std::vector<std::string>& g,const std::vector<DeskSeed>& seeds){DeskMap o;if(g.empty())return o;int h=g.size(),w=g[0].size();for(auto&r:g)if((int)r.size()!=w)return{false,{},{}};std::set<int> pos;std::set<char> codes;std::vector<int>d(h*w,-1);std::vector<std::set<char>> teams(h*w);std::queue<int>q;for(auto s:seeds){int x=s.row*w+s.col;if(s.row<0||s.row>=h||s.col<0||s.col>=w||g[s.row][s.col]=='#'||!std::isupper((unsigned char)s.team)||!pos.insert(x).second||!codes.insert(s.team).second)return{false,{},{}};d[x]=0;teams[x].insert(s.team);q.push(x);}int dr[4]={-1,1,0,0},dc[4]={0,0,-1,1};while(!q.empty()){int x=q.front();q.pop();for(int k=0;k<4;++k){int nr=x/w+dr[k],nc=x%w+dc[k];if(nr<0||nr>=h||nc<0||nc>=w||g[nr][nc]=='#')continue;int y=nr*w+nc;if(d[y]<0){d[y]=d[x]+1;teams[y]=teams[x];q.push(y);}else if(d[y]==d[x]+1){std::size_t before=teams[y].size();teams[y].insert(teams[x].begin(),teams[x].end());if(teams[y].size()!=before)q.push(y);}}}o.owner.assign(h*w,'-');for(int i=0;i<h*w;++i)if(!teams[i].empty()){o.owner[i]=*teams[i].begin();if(teams[i].size()>1)o.tied.push_back(i);}return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto d=assign_desks({"....."},{{'B',0,4},{'A',0,0}});return d.valid&&d.owner==std::vector<char>{'A','A','A','B','B'}&&d.tied==std::vector<int>{2}?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto d=assign_desks({".#.","###","..."},{{'A',0,0}});f+=d.owner[6]!='-';f+=assign_desks({".."},{{'A',0,0},{'B',0,0}}).valid;f+=assign_desks({"#"},{{'A',0,0}}).valid;return f;}
'''),
GridCase(
"ownership-orchard-blocks","orchard-row-quota-allocator","Orchard Row Quota Allocator","row-round-robin-quota",
"Allocate plant cells under independent grower row quotas.","allocate_orchard(grid,quotas)->OrchardPlan","remaining[j][r]",
r'''# Instructions

`*` is an allocatable tree, `#` is blocked, and `.` is unused. Each grower has a
unique uppercase code and one nonnegative quota per row. In each row, visit `*` cells
left-to-right and assign them round-robin among growers in input order who still have
row quota. Unfilled cells remain `.`. A grower with any unused quota appears once in
input order in `shortfall`. Invalid shapes, symbols, quotas, or duplicate codes are
atomic errors.
''',
r'''#pragma once
#include <string>
#include <vector>
namespace curriculum { struct GrowerQuota{char grower;std::vector<int> row_quota;}; struct OrchardPlan{bool valid=true;std::vector<std::string> owners;std::vector<char> shortfall;}; OrchardPlan allocate_orchard(const std::vector<std::string>&,const std::vector<GrowerQuota>&); }
''',_starter("allocate_orchard"),
r'''#include "task.h"
#include <cctype>
#include <set>
namespace curriculum { OrchardPlan allocate_orchard(const std::vector<std::string>& g,const std::vector<GrowerQuota>& qs){OrchardPlan o;o.owners=g;if(g.empty())return o;int h=g.size(),w=g[0].size();std::set<char> codes;std::vector<std::vector<int>> remaining;for(auto&r:g){if((int)r.size()!=w)return{false,{},{}};for(char x:r)if(x!='*'&&x!='#'&&x!='.')return{false,{},{}};}for(auto q:qs){if(!std::isupper((unsigned char)q.grower)||!codes.insert(q.grower).second||(int)q.row_quota.size()!=h)return{false,{},{}};for(int n:q.row_quota)if(n<0)return{false,{},{}};remaining.push_back(q.row_quota);}for(int r=0;r<h;++r){std::size_t cursor=0;for(int c=0;c<w;++c)if(g[r][c]=='*'){bool assigned=false;for(std::size_t k=0;k<qs.size();++k){std::size_t j=(cursor+k)%qs.size();if(remaining[j][r]>0){o.owners[r][c]=qs[j].grower;--remaining[j][r];cursor=(j+1)%qs.size();assigned=true;break;}}if(!assigned)o.owners[r][c]='.';}}for(std::size_t j=0;j<qs.size();++j){bool left=false;for(int n:remaining[j])left|=n>0;if(left)o.shortfall.push_back(qs[j].grower);}return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto p=allocate_orchard({"***","**#"},{{'A',{2,1}},{'B',{1,1}}});return p.valid&&p.owners==std::vector<std::string>{"ABA","AB#"}&&p.shortfall.empty()?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto p=allocate_orchard({"*"},{{'A',{2}}});f+=p.owners[0]!="A"||p.shortfall!=std::vector<char>{'A'};f+=allocate_orchard({"*"},{{'A',{1}},{'A',{0}}}).valid;f+=allocate_orchard({"?"},{}).valid;return f;}
'''),
GridCase(
"ownership-parking-permits","parking-permit-occupancy-audit","Parking Permit Occupancy Audit","parallel-grid-permit-lookup",
"Compare vehicle permits with bay zones.","audit_parking(zones,occupancy,vehicles)->ParkingAudit","vehicle_permit",
r'''# Instructions

`zones` contains uppercase required permit codes or `.` for no bay. `occupancy` has
`.` for empty or a vehicle mark. Vehicle marks are unique and map to uppercase permit
codes. Shapes must match exactly. Occupancy in a non-bay, an unknown vehicle, malformed
symbols, or duplicate marks invalidates. Otherwise report every permit mismatch in
row-major order and count empty real bays.
''',
r'''#pragma once
#include <string>
#include <vector>
namespace curriculum { struct Vehicle{char mark,permit;}; struct ParkingIssue{int row,col;char required,actual;}; struct ParkingAudit{bool valid=true;std::vector<ParkingIssue> issues;int empty_bays=0;}; ParkingAudit audit_parking(const std::vector<std::string>&,const std::vector<std::string>&,const std::vector<Vehicle>&); }
''',_starter("audit_parking"),
r'''#include "task.h"
#include <cctype>
#include <map>
namespace curriculum { ParkingAudit audit_parking(const std::vector<std::string>& z,const std::vector<std::string>& occ,const std::vector<Vehicle>& vs){ParkingAudit o;if(z.size()!=occ.size())return{false,{},0};std::map<char,char> vehicle_permit;for(auto v:vs)if(v.mark=='.'||!std::isupper((unsigned char)v.permit)||vehicle_permit.count(v.mark))return{false,{},0};else vehicle_permit[v.mark]=v.permit;for(int r=0;r<(int)z.size();++r){if(z[r].size()!=occ[r].size()||(r&&z[r].size()!=z[0].size()))return{false,{},0};for(int c=0;c<(int)z[r].size();++c){char need=z[r][c],car=occ[r][c];if(need!='.'&&!std::isupper((unsigned char)need))return{false,{},0};if(car=='.'){if(need!='.')++o.empty_bays;continue;}if(need=='.'||!vehicle_permit.count(car))return{false,{},0};char actual=vehicle_permit[car];if(actual!=need)o.issues.push_back({r,c,need,actual});}}return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto a=audit_parking({"AB","A."},{"x.","y."},{{'x','A'},{'y','B'}});return a.valid&&a.empty_bays==1&&a.issues.size()==1&&a.issues[0].row==1?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;f+=audit_parking({"."},{"x"},{{'x','A'}}).valid;f+=audit_parking({"A"},{"x"},{}).valid;f+=audit_parking({"A","A"},{".",".."},{}).valid;return f;}
'''),
GridCase(
"ownership-rail-platforms","rail-platform-service-zones","Rail Platform Service Zones","weighted-line-nearest-service",
"Assign platform positions by weighted walking distance.","assign_platforms(edge_cost,services)->PlatformZones","prefix[i]",
r'''# Instructions

`edge_cost[i]` is the nonnegative walking cost between positions `i` and `i+1`, so
there are `edge_cost.size()+1` positions. Services have unique uppercase codes and
unique valid positions. Assign each position to minimum weighted distance; ties choose
the alphabetically smaller code and are listed. With no services owners are `'-'` and
distances `-1`. Invalid input is atomic; sums beyond `int` invalidate.
''',
r'''#pragma once
#include <vector>
namespace curriculum { struct Service{char code;int position;}; struct PlatformZones{bool valid=true;std::vector<char> owner;std::vector<int> distance,ties;}; PlatformZones assign_platforms(const std::vector<int>&,const std::vector<Service>&); }
''',_starter("assign_platforms"),
r'''#include "task.h"
#include <cctype>
#include <climits>
#include <cstdlib>
#include <set>
namespace curriculum { PlatformZones assign_platforms(const std::vector<int>& edges,const std::vector<Service>& ss){PlatformZones o;int n=edges.size()+1;std::vector<long long> prefix(n);for(int i=0;i<(int)edges.size();++i){if(edges[i]<0)return{false,{},{},{}};prefix[i+1]=prefix[i]+edges[i];if(prefix[i+1]>INT_MAX)return{false,{},{},{}};}std::set<int>pos;std::set<char>code;for(auto s:ss)if(s.position<0||s.position>=n||!std::isupper((unsigned char)s.code)||!pos.insert(s.position).second||!code.insert(s.code).second)return{false,{},{},{}};o.owner.assign(n,'-');o.distance.assign(n,-1);for(int i=0;i<n;++i){long long best=LLONG_MAX;char who='-';bool tie=false;for(auto s:ss){long long d=std::llabs(prefix[i]-prefix[s.position]);if(d<best){best=d;who=s.code;tie=false;}else if(d==best){tie=true;who=std::min(who,s.code);}}if(best!=LLONG_MAX){o.owner[i]=who;o.distance[i]=best;if(tie)o.ties.push_back(i);}}return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto z=assign_platforms({2,2,2,2},{{'B',4},{'A',0}});return z.valid&&z.owner==std::vector<char>{'A','A','A','B','B'}&&z.ties==std::vector<int>{2}?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto z=assign_platforms({0,0},{{'B',2},{'A',0}});f+=z.owner[1]!='A'||z.ties.empty()||z.ties[0]!=0;f+=assign_platforms({-1},{}).valid;f+=assign_platforms({1},{{'A',0},{'B',0}}).valid;return f;}
'''),
GridCase(
"ownership-river-rights","river-junction-rights-propagator","River Junction Rights Propagator","dag-owner-set-propagation",
"Propagate license owners through an acyclic river network.","propagate_rights(nodes,channels,sources)->RiverRights","owner_sets[v].insert",
r'''# Instructions

Channels are directed downstream edges. Validate node indices, unique edges, and one
source record per node with an uppercase owner. Topologically propagate all source
owners reachable at each node. `sole_owner` is the one owner or `'-'`; nodes with more
than one owner are ambiguous in ascending index. Unreachable nodes remain `'-'`.
Cycles invalidate atomically; multiple sources may share an owner.
''',
r'''#pragma once
#include <vector>
namespace curriculum { struct Channel{int from,to;}; struct SourceRight{int node;char owner;}; struct RiverRights{bool valid=true;std::vector<char> sole_owner;std::vector<int> ambiguous;}; RiverRights propagate_rights(int,const std::vector<Channel>&,const std::vector<SourceRight>&); }
''',_starter("propagate_rights"),
r'''#include "task.h"
#include <cctype>
#include <queue>
#include <set>
namespace curriculum { RiverRights propagate_rights(int n,const std::vector<Channel>& es,const std::vector<SourceRight>& src){if(n<0)return{false,{},{}};std::vector<std::vector<int>>g(n);std::vector<int>deg(n);std::set<std::pair<int,int>>seen;for(auto e:es){if(e.from<0||e.from>=n||e.to<0||e.to>=n||!seen.insert({e.from,e.to}).second)return{false,{},{}};g[e.from].push_back(e.to);++deg[e.to];}std::vector<std::set<char>> owner_sets(n);std::set<int>sn;for(auto s:src)if(s.node<0||s.node>=n||!std::isupper((unsigned char)s.owner)||!sn.insert(s.node).second)return{false,{},{}};else owner_sets[s.node].insert(s.owner);std::queue<int>q;for(int i=0;i<n;++i)if(!deg[i])q.push(i);int done=0;while(!q.empty()){int u=q.front();q.pop();++done;for(int v:g[u]){owner_sets[v].insert(owner_sets[u].begin(),owner_sets[u].end());if(--deg[v]==0)q.push(v);}}if(done!=n)return{false,{},{}};RiverRights o;o.sole_owner.assign(n,'-');for(int i=0;i<n;++i)if(owner_sets[i].size()==1)o.sole_owner[i]=*owner_sets[i].begin();else if(owner_sets[i].size()>1)o.ambiguous.push_back(i);return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto r=propagate_rights(4,{{0,2},{1,2},{2,3}},{{0,'A'},{1,'B'}});return r.valid&&r.sole_owner[0]=='A'&&r.ambiguous==std::vector<int>{2,3}?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto r=propagate_rights(3,{{0,2},{1,2}},{{0,'A'},{1,'A'}});f+=r.sole_owner[2]!='A'||!r.ambiguous.empty();f+=propagate_rights(2,{{0,1},{1,0}},{}).valid;f+=propagate_rights(2,{{0,1},{0,1}},{}).valid;return f;}
'''),
GridCase(
"ownership-ski-runs","downhill-patrol-zone-propagator","Downhill Patrol Zone Propagator","descending-height-owner-flow",
"Propagate patrol owners only along strictly downhill cells.","assign_patrols(elevation,patrols)->PatrolMap","std::sort(order.begin()",
r'''# Instructions

Patrol seeds have unique uppercase codes and unique cells. Process cells from greatest
elevation to least; every owner reaching a cell flows to each strictly lower orthogonal
neighbor. Plateaus do not connect. A cell with one owner records it, a cell with many
records the alphabetically smallest and is listed ambiguous, and an unseeded cell is
`'-'`. Ragged maps or bad seeds invalidate.
''',
r'''#pragma once
#include <vector>
namespace curriculum { struct Patrol{char code;int row,col;}; struct PatrolMap{bool valid=true;std::vector<char> owner;std::vector<int> ambiguous;}; PatrolMap assign_patrols(const std::vector<std::vector<int>>&,const std::vector<Patrol>&); }
''',_starter("assign_patrols"),
r'''#include "task.h"
#include <algorithm>
#include <cctype>
#include <set>
namespace curriculum { PatrolMap assign_patrols(const std::vector<std::vector<int>>& a,const std::vector<Patrol>& ps){PatrolMap o;if(a.empty())return o;int h=a.size(),w=a[0].size();for(auto&r:a)if((int)r.size()!=w)return{false,{},{}};std::set<int>pos;std::set<char>codes;std::vector<std::set<char>> own(h*w);for(auto p:ps){int x=p.row*w+p.col;if(p.row<0||p.row>=h||p.col<0||p.col>=w||!std::isupper((unsigned char)p.code)||!pos.insert(x).second||!codes.insert(p.code).second)return{false,{},{}};own[x].insert(p.code);}std::vector<int>order(h*w);for(int i=0;i<h*w;++i)order[i]=i;std::sort(order.begin(),order.end(),[&](int x,int y){return a[x/w][x%w]>a[y/w][y%w]||(a[x/w][x%w]==a[y/w][y%w]&&x<y);});int dr[4]={-1,1,0,0},dc[4]={0,0,-1,1};for(int x:order)for(int d=0;d<4;++d){int nr=x/w+dr[d],nc=x%w+dc[d];if(nr>=0&&nr<h&&nc>=0&&nc<w&&a[nr][nc]<a[x/w][x%w])own[nr*w+nc].insert(own[x].begin(),own[x].end());}o.owner.assign(h*w,'-');for(int i=0;i<h*w;++i)if(!own[i].empty()){o.owner[i]=*own[i].begin();if(own[i].size()>1)o.ambiguous.push_back(i);}return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto m=assign_patrols({{4,3},{3,2}},{{'A',0,0},{'B',0,1}});return m.valid&&m.owner[3]=='A'&&m.ambiguous==std::vector<int>{1,3}?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto m=assign_patrols({{2,2}},{{'A',0,0}});f+=m.owner[1]!='-';f+=assign_patrols({{1},{2,3}},{}).valid;f+=assign_patrols({{1}},{{'A',0,0},{'B',0,0}}).valid;return f;}
'''),
GridCase(
"ownership-solar-array","solar-string-serpentine-audit","Solar String Serpentine Audit","serpentine-chunk-owner-check",
"Audit fixed-width serpentine panel strings for mixed owners.","audit_strings(grid,width,legend)->SolarAudit","linear.push_back",
r'''# Instructions

The rectangular panel grid contains only legend symbols. Legends map unique symbols
to unique nonempty owners. Linearize even rows left-to-right and odd rows right-to-left,
then split into exact `string_width` chunks. Each string records its first panel owner;
every later differing owner emits `{string_index,offset}`. Nonpositive width, incomplete
last chunk, bad legend, unknown panel, or ragged rows invalidate.
''',
r'''#pragma once
#include <string>
#include <vector>
namespace curriculum { struct PanelLegend{char symbol;std::string owner;}; struct SolarIssue{int string_index,offset;}; struct SolarAudit{bool valid=true;std::vector<std::string> string_owner;std::vector<SolarIssue> mixed;}; SolarAudit audit_strings(const std::vector<std::string>&,int,const std::vector<PanelLegend>&); }
''',_starter("audit_strings"),
r'''#include "task.h"
#include <map>
#include <set>
namespace curriculum { SolarAudit audit_strings(const std::vector<std::string>& g,int width,const std::vector<PanelLegend>& ls){SolarAudit o;if(width<=0)return{false,{},{}};std::map<char,std::string> owner;std::set<std::string>names;for(auto l:ls)if(owner.count(l.symbol)||l.owner.empty()||!names.insert(l.owner).second)return{false,{},{}};else owner[l.symbol]=l.owner;if(g.empty())return o;int w=g[0].size();std::vector<char> linear;for(int r=0;r<(int)g.size();++r){if((int)g[r].size()!=w)return{false,{},{}};if(r%2==0)for(char x:g[r])linear.push_back(x);else for(auto it=g[r].rbegin();it!=g[r].rend();++it)linear.push_back(*it);}if(linear.size()%width)return{false,{},{}};for(int i=0;i<(int)linear.size();i+=width){if(!owner.count(linear[i]))return{false,{},{}};std::string first=owner[linear[i]];o.string_owner.push_back(first);for(int k=0;k<width;++k){if(!owner.count(linear[i+k]))return{false,{},{}};if(owner[linear[i+k]]!=first)o.mixed.push_back({i/width,k});}}return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto a=audit_strings({"AAB","BBA"},3,{{'A',"x"},{'B',"y"}});return a.valid&&a.string_owner==std::vector<std::string>{"x","x"}&&a.mixed.size()==3?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto a=audit_strings({"AB","BA"},2,{{'A',"x"},{'B',"y"}});f+=a.string_owner[1]!="x";f+=audit_strings({"AAA"},2,{{'A',"x"}}).valid;f+=audit_strings({"X"},1,{{'A',"x"}}).valid;return f;}
'''),
GridCase(
"ownership-warehouse-aisles","warehouse-zone-capacity-counter","Warehouse Zone Capacity Counter","weighted-cell-aisle-penalty",
"Compute zone capacity and blocked-aisle boundary counts.","calculate_capacity(grid,weights)->CapacityAudit","blocked_edges",
r'''# Instructions

Uppercase cells are storage zones, `#` is a blocked aisle, and `.` is unused. Each
zone has one positive unit capacity. Sum capacity per occupied cell. Count each right
or down edge between that zone and `#`; diagram-edge exposure is not blocked. Return
rows in weight input order. Duplicate/invalid weights, unknown labels, ragged rows, or
illegal symbols invalidate atomically.
''',
r'''#pragma once
#include <string>
#include <vector>
namespace curriculum { struct ZoneWeight{char zone;int unit_capacity;}; struct CapacityRow{char zone;int usable,blocked_edges;}; struct CapacityAudit{bool valid=true;std::vector<CapacityRow> rows;}; CapacityAudit calculate_capacity(const std::vector<std::string>&,const std::vector<ZoneWeight>&); }
''',_starter("calculate_capacity"),
r'''#include "task.h"
#include <cctype>
#include <map>
namespace curriculum { CapacityAudit calculate_capacity(const std::vector<std::string>& g,const std::vector<ZoneWeight>& ws){CapacityAudit o;std::map<char,int>idx;for(auto w:ws)if(!std::isupper((unsigned char)w.zone)||w.unit_capacity<=0||idx.count(w.zone))return{false,{}};else{idx[w.zone]=o.rows.size();o.rows.push_back({w.zone,0,0});}if(g.empty())return o;int h=g.size(),w=g[0].size();for(auto&r:g)if((int)r.size()!=w)return{false,{}};for(int r=0;r<h;++r)for(int c=0;c<w;++c){char x=g[r][c];if(x=='.'||x=='#')continue;if(!idx.count(x))return{false,{}};auto& row=o.rows[idx[x]];row.usable+=ws[idx[x]].unit_capacity;int dr[4]={-1,1,0,0},dc[4]={0,0,-1,1};for(int d=0;d<4;++d){int nr=r+dr[d],nc=c+dc[d];if(nr>=0&&nr<h&&nc>=0&&nc<w&&g[nr][nc]=='#')++row.blocked_edges;}}return o;} }
''',
r'''#include "task.h"
int main(){using namespace curriculum;auto a=calculate_capacity({"A#","AB"},{{'A',3},{'B',5}});return a.valid&&a.rows[0].usable==6&&a.rows[0].blocked_edges==1&&a.rows[1].usable==5?0:1;}
''',
r'''#include "task.h"
int main(){using namespace curriculum;int f=0;auto a=calculate_capacity({"A"},{{'A',2}});f+=a.rows[0].blocked_edges!=0;f+=calculate_capacity({"B"},{{'A',1}}).valid;f+=calculate_capacity({"A"},{{'A',1},{'A',2}}).valid;return f;}
'''),
)

# Every replacement owns a compiling, task-specific false implementation.  The
# Docker verifier builds it with the same strict CMake target as the reference,
# executes both visible/private tests, and requires a non-zero CTest result.
NEGATIVE_MUTATIONS = {
    "airport-gate-closure-planner": (
        "busy[name]<=f.arrival",
        "busy[name]<f.arrival",
        "rejects exact-endpoint gate reuse",
    ),
    "campsite-access-zone-router": (
        "o.owner[x]<o.owner[y]",
        "o.owner[x]>o.owner[y]",
        "reverses equal-distance entrance ownership",
    ),
    "garden-boundary-ledger": ("++ext[a]", "ext[a]+=2", "double-counts exterior edges"),
    "parcel-component-perimeters": (
        "++p.perimeter",
        "p.perimeter+=2",
        "double-counts component perimeter",
    ),
    "rack-contiguous-allocation-audit": (
        "g[r][c]!=x",
        "g[r][c]==x",
        "marks owned interval cells as gaps",
    ),
    "lease-rectangle-overlay-resolver": (
        "o.owner[x]!=id&&o.owner[x]!=-2",
        "o.owner[x]==id&&o.owner[x]!=-2",
        "treats idempotent same-owner overlap as contested",
    ),
    "shoreline-barrier-coverage": (
        "b.begin>merged_end",
        "b.begin>=merged_end",
        "emits zero-width gaps at touching barriers",
    ),
    "quay-concession-component-audit": (
        "if(n>1)o.disconnected.push_back(x)",
        "if(n>0)o.disconnected.push_back(x)",
        "marks every concession as disconnected",
    ),
    "bench-contact-compatibility": (
        "!rule[{low,high}]",
        "rule[{low,high}]",
        "inverts explicit contact permission",
    ),
    "marina-berth-ray-attribution": (
        "if(z!=':')break",
        "if(z==':')break",
        "stops rays on valid berth cells",
    ),
    "market-stall-frontage-runs": (
        "g[r+1][c]=='.'",
        "g[r+1][c]!='.'",
        "counts covered cells instead of street frontage",
    ),
    "gallery-room-label-audit": (
        "labels.size()!=1",
        "labels.size()==1",
        "rejects exactly-one-label rooms",
    ),
    "office-desk-voronoi-assignment": (
        "*teams[i].begin()",
        "*teams[i].rbegin()",
        "selects the largest tied team",
    ),
    "orchard-row-quota-allocator": (
        "cursor=(j+1)%qs.size()",
        "cursor=j%qs.size()",
        "fails to advance round-robin ownership",
    ),
    "parking-permit-occupancy-audit": (
        "actual!=need",
        "actual==need",
        "reports matching permits as violations",
    ),
    "rail-platform-service-zones": (
        "who=std::min(who,s.code)",
        "who=std::max(who,s.code)",
        "selects the largest tied service code",
    ),
    "river-junction-rights-propagator": (
        "owner_sets[v].insert(owner_sets[u].begin(),owner_sets[u].end())",
        "owner_sets[v].insert(owner_sets[v].begin(),owner_sets[v].end())",
        "drops upstream rights at downstream edges",
    ),
    "downhill-patrol-zone-propagator": (
        "a[nr][nc]<a[x/w][x%w]",
        "a[nr][nc]>a[x/w][x%w]",
        "propagates uphill instead of downhill",
    ),
    "solar-string-serpentine-audit": (
        "if(r%2==0)",
        "if(r%2!=0)",
        "reverses the serpentine row parity",
    ),
    "warehouse-zone-capacity-counter": (
        "row.usable+=ws[idx[x]].unit_capacity",
        "row.usable-=ws[idx[x]].unit_capacity",
        "subtracts occupied-zone capacity",
    ),
}
