"""Case contract and partition/decomposition roots for DPR expansion v2."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DprCase:
    task_id: str
    class_name: str
    title: str
    group: str
    api: str
    definition: str
    starter: str
    visible: str
    hidden: str
    negative_old: str
    negative_new: str
    mechanism: str
    boundary: str
    negative_reason: str


def _case(*values: str) -> DprCase:
    return DprCase(*values)


CASES: tuple[DprCase, ...] = (
    _case(
        "dpr-minimax-contiguous-cuts", "MinimaxCuts", "Minimax contiguous cuts", "decomposition",
        "class MinimaxCuts { public: struct Plan { long long peak; std::vector<std::size_t> cuts; bool operator==(const Plan& o) const{return peak==o.peak&&cuts==o.cuts;} }; static std::optional<Plan> partition(const std::vector<long long>& weights,std::size_t workers); };",
        "std::optional<MinimaxCuts::Plan> MinimaxCuts::partition(const std::vector<long long>& a,std::size_t w){if(w==0||w>a.size()||a.size()>14||std::any_of(a.begin(),a.end(),[](long long x){return x<0;}))return std::nullopt;long long best=LLONG_MAX;std::vector<std::size_t> best_cuts,cuts;std::function<void(std::size_t,std::size_t)> rec=[&](std::size_t begin,std::size_t left){if(left==1){long long sum=0;for(std::size_t i=begin;i<a.size();++i){if(__builtin_add_overflow(sum,a[i],&sum))return;}long long peak=sum;std::size_t prior=0;for(std::size_t cut:cuts){long long part=0;for(std::size_t i=prior;i<cut;++i){if(__builtin_add_overflow(part,a[i],&part))return;}peak=std::max(peak,part);prior=cut;}auto candidate=cuts;candidate.push_back(a.size());if(peak<best||(peak==best&&candidate<best_cuts)){best=peak;best_cuts=candidate;}return;}for(std::size_t cut=begin+1;cut+left-1<=a.size();++cut){cuts.push_back(cut);rec(cut,left-1);cuts.pop_back();}};rec(0,w);if(best==LLONG_MAX)return std::nullopt;return Plan{best,best_cuts};}",
        "std::optional<MinimaxCuts::Plan> MinimaxCuts::partition(const std::vector<long long>&,std::size_t){return std::nullopt;}",
        "auto p=MinimaxCuts::partition({7,2,5,10,8},2);check(p&&p->peak==18&&p->cuts==std::vector<std::size_t>({3,5}));",
        "check(!MinimaxCuts::partition({1,-1},1));check(!MinimaxCuts::partition({1},0));check(!MinimaxCuts::partition({LLONG_MAX,1,1},2));auto p=MinimaxCuts::partition({4,4,4},3);check(p&&p->cuts==std::vector<std::size_t>({1,2,3}));auto q=MinimaxCuts::partition({1,1,1,1},2);check(q&&q->cuts==std::vector<std::size_t>({2,4}));",
        "if(peak<best||(peak==best&&candidate<best_cuts))", "if(peak<=best)",
        "exact exhaustive minimax partition with lexicographic cut ties", "workers create nonempty contiguous ranges and overflow rejects atomically", "equal-peak plans keep the last rather than lexicographically first cuts",
    ),
    _case(
        "dpr-key-affinity-shards", "KeyAffinityShards", "Key affinity shards", "decomposition",
        "class KeyAffinityShards { public: struct Item{int id;std::string key;}; struct Assignment{std::vector<std::vector<int>> ids;}; static std::optional<Assignment> assign(const std::vector<Item>& items,std::size_t shards); };",
        "std::optional<KeyAffinityShards::Assignment> KeyAffinityShards::assign(const std::vector<Item>& items,std::size_t n){if(n==0)return std::nullopt;std::set<int> ids;Assignment out;out.ids.resize(n);for(const auto& x:items){if(x.key.empty()||!ids.insert(x.id).second)return std::nullopt;std::uint64_t h=1469598103934665603ULL;for(unsigned char c:x.key){h^=c;h*=1099511628211ULL;}out.ids[static_cast<std::size_t>(h%n)].push_back(x.id);}return out;}",
        "std::optional<KeyAffinityShards::Assignment> KeyAffinityShards::assign(const std::vector<Item>&,std::size_t){return std::nullopt;}",
        "std::vector<KeyAffinityShards::Item> a{{1,\"alpha\"},{2,\"beta\"},{3,\"alpha\"}};auto p=KeyAffinityShards::assign(a,3);check(p.has_value());std::size_t one=9,two=9,three=9;for(std::size_t i=0;i<p->ids.size();++i)for(int id:p->ids[i]){if(id==1)one=i;if(id==2)two=i;if(id==3)three=i;}check(one==0&&two==1&&three==0);",
        "check(!KeyAffinityShards::assign({{1,\"\"}},2));check(!KeyAffinityShards::assign({{1,\"a\"},{1,\"b\"}},2));auto p=KeyAffinityShards::assign({},2);check(p&&p->ids.size()==2);auto q=KeyAffinityShards::assign({{7,\"beta\"}},3);check(q&&q->ids[1]==std::vector<int>({7}));",
        "h^=c;h*=1099511628211ULL;", "h+=c;",
        "canonical FNV-1a affinity with stable per-shard filtering", "empty keys and duplicate item identities reject before publication", "a byte-sum hash replaces the specified affinity digest",
    ),
    _case(
        "dpr-halo-stencil-tiles", "HaloStencilTiles", "Halo stencil tiles", "decomposition",
        "class HaloStencilTiles { public: struct Rect{int top,left,bottom,right;bool operator==(const Rect&o)const{return std::tie(top,left,bottom,right)==std::tie(o.top,o.left,o.bottom,o.right);}}; struct Tile{Rect core,halo;}; static std::optional<std::vector<Tile>> make(int rows,int cols,int tile_rows,int tile_cols,int halo); };",
        "std::optional<std::vector<HaloStencilTiles::Tile>> HaloStencilTiles::make(int rows,int cols,int tr,int tc,int h){if(rows<=0||cols<=0||tr<=0||tc<=0||h<0)return std::nullopt;std::vector<Tile> out;for(int r=0;;){int bottom; if(__builtin_add_overflow(r,tr,&bottom))return std::nullopt; if(bottom>rows)bottom=rows;for(int c=0;;){int right; if(__builtin_add_overflow(c,tc,&right))return std::nullopt; if(right>cols)right=cols;Rect core{r,c,bottom,right};int hb,hr; if(__builtin_add_overflow(bottom,h,&hb))hb=rows; if(__builtin_add_overflow(right,h,&hr))hr=cols; Rect halo{h>r?0:r-h,h>c?0:c-h,hb>rows?rows:hb,hr>cols?cols:hr};out.push_back({core,halo});if(right==cols)break;c=right;}if(bottom==rows)break;r=bottom;}return out;}",
        "std::optional<std::vector<HaloStencilTiles::Tile>> HaloStencilTiles::make(int,int,int,int,int){return std::nullopt;}",
        "auto t=HaloStencilTiles::make(3,5,2,3,1);check(t&&t->size()==4);check((*t)[0].core==HaloStencilTiles::Rect{0,0,2,3});check((*t)[0].halo==HaloStencilTiles::Rect{0,0,3,4});",
        "check(!HaloStencilTiles::make(0,2,1,1,0));check(!HaloStencilTiles::make(2,2,1,1,-1));auto t=HaloStencilTiles::make(2,2,3,3,4);check(t&&t->size()==1&&(*t)[0].halo==HaloStencilTiles::Rect{0,0,2,2});auto q=HaloStencilTiles::make(1,1,1,1,INT_MAX);check(q&&(*q)[0].halo==HaloStencilTiles::Rect{0,0,1,1});",
        "h>r?0:r-h,h>c?0:c-h", "r-h,c-h",
        "disjoint row-major core rectangles with clipped stencil halos", "edge halos clip independently while cores cover each cell exactly once", "edge halos retain negative coordinates instead of clipping",
    ),
    _case(
        "dpr-frame-aligned-slices", "FrameAlignedSlices", "Frame aligned slices", "decomposition",
        "class FrameAlignedSlices { public: static std::optional<std::vector<std::size_t>> partition(std::size_t total,const std::vector<std::size_t>& frames,std::size_t workers); };",
        "std::optional<std::vector<std::size_t>> FrameAlignedSlices::partition(std::size_t total,const std::vector<std::size_t>& frames,std::size_t workers){if(workers==0||workers>frames.size()||total==0)return std::nullopt;std::vector<std::size_t> ends;std::size_t sum=0;for(std::size_t len:frames){if(len==0||len>total||sum>total-len||total==0)return std::nullopt;sum+=len;ends.push_back(sum);}if(sum!=total)return std::nullopt;std::vector<std::size_t> cuts;std::size_t previous=0;for(std::size_t w=1;w<workers;++w){std::size_t q=total/workers,r=total%workers;if(q&&w>SIZE_MAX/q)return std::nullopt;std::size_t target=q*w;if(r&&w>SIZE_MAX/r)return std::nullopt;target+=r*w/workers;std::size_t best=0,dist=SIZE_MAX;for(std::size_t e:ends)if(e>previous&&e<total){std::size_t d=e>target?e-target:target-e;if(d<dist||(d==dist&&e<best)){best=e;dist=d;}}if(best==0)return std::nullopt;cuts.push_back(best);previous=best;}cuts.push_back(total);return cuts;}",
        "std::optional<std::vector<std::size_t>> FrameAlignedSlices::partition(std::size_t,const std::vector<std::size_t>&,std::size_t){return std::nullopt;}",
        "auto c=FrameAlignedSlices::partition(12,{3,2,4,3},3);check(c&&*c==std::vector<std::size_t>({3,9,12}));",
        "check(!FrameAlignedSlices::partition(4,{2,0,2},2));check(!FrameAlignedSlices::partition(5,{2,2},2));check(!FrameAlignedSlices::partition(2,{1,1},3));check(!FrameAlignedSlices::partition(0,{SIZE_MAX,1},1));auto c=FrameAlignedSlices::partition(6,{2,2,2},2);check(c&&(*c)[0]==2);",
        "d==dist&&e<best", "d==dist&&e>best",
        "nearest cumulative byte targets constrained to frame boundaries", "coverage must be exact and equal-distance ties choose the earlier boundary", "equal-distance targets choose the later frame boundary",
    ),
    _case(
        "dpr-morton-grid-tiles", "MortonGridTiles", "Morton grid tiles", "decomposition",
        "class MortonGridTiles { public: struct Tile{unsigned row,col,key,owner;}; static std::optional<std::vector<Tile>> plan(unsigned tile_rows,unsigned tile_cols,unsigned workers); };",
        "std::optional<std::vector<MortonGridTiles::Tile>> MortonGridTiles::plan(unsigned rows,unsigned cols,unsigned workers){if(rows==0||cols==0||workers==0||rows>256||cols>256)return std::nullopt;auto morton=[](unsigned r,unsigned c){unsigned z=0;for(unsigned b=0;b<8;++b){z|=((c>>b)&1U)<<(2*b);z|=((r>>b)&1U)<<(2*b+1);}return z;};std::vector<Tile> out;for(unsigned r=0;r<rows;++r)for(unsigned c=0;c<cols;++c)out.push_back({r,c,morton(r,c),0});std::sort(out.begin(),out.end(),[](const Tile&a,const Tile&b){return std::tie(a.key,a.row,a.col)<std::tie(b.key,b.row,b.col);});for(std::size_t i=0;i<out.size();++i)out[i].owner=static_cast<unsigned>((i*workers)/out.size());return out;}",
        "std::optional<std::vector<MortonGridTiles::Tile>> MortonGridTiles::plan(unsigned,unsigned,unsigned){return std::nullopt;}",
        "auto p=MortonGridTiles::plan(2,2,2);check(p&&p->size()==4);check((*p)[0].row==0&&(*p)[0].col==0&&(*p)[1].col==1&&(*p)[2].row==1);",
        "check(!MortonGridTiles::plan(0,2,1));check(!MortonGridTiles::plan(2,2,0));auto p=MortonGridTiles::plan(1,3,5);check(p&&p->back().owner<5);",
        "z|=((r>>b)&1U)<<(2*b+1);", "z|=((r>>b)&1U)<<(2*b);",
        "bit-interleaved Morton tile order with contiguous rank ownership", "coordinates are bounded to the eight-bit interleaving domain", "row and column bits collide in the same Morton positions",
    ),
    _case(
        "dpr-speed-aware-list-schedule", "SpeedAwareSchedule", "Speed aware list schedule", "decomposition",
        "class SpeedAwareSchedule { public: struct Worker{int id;long long speed;}; struct Job{int id;long long cost;}; static std::optional<std::vector<int>> assign(const std::vector<Job>& jobs,const std::vector<Worker>& workers); };",
        "std::optional<std::vector<int>> SpeedAwareSchedule::assign(const std::vector<Job>& jobs,const std::vector<Worker>& workers){if(workers.empty())return std::nullopt;std::set<int> ids;for(const auto&w:workers)if(w.speed<=0||!ids.insert(w.id).second)return std::nullopt;std::vector<long long> load(workers.size());std::vector<int> out;for(const auto&j:jobs){if(j.cost<0)return std::nullopt;std::size_t best=0;for(std::size_t i=1;i<workers.size();++i){long long li=0,lb=0,left=0,right=0;if(__builtin_add_overflow(load[i],j.cost,&li)||__builtin_add_overflow(load[best],j.cost,&lb)||__builtin_mul_overflow(li,workers[best].speed,&left)||__builtin_mul_overflow(lb,workers[i].speed,&right))return std::nullopt;if(left<right||(left==right&&workers[i].id<workers[best].id))best=i;}if(__builtin_add_overflow(load[best],j.cost,&load[best]))return std::nullopt;out.push_back(workers[best].id);}return out;}",
        "std::optional<std::vector<int>> SpeedAwareSchedule::assign(const std::vector<Job>&,const std::vector<Worker>&){return std::nullopt;}",
        "auto p=SpeedAwareSchedule::assign({{1,6},{2,6},{3,6}},{{7,1},{3,2}});check(p&&*p==std::vector<int>({3,3,7}));",
        "check(!SpeedAwareSchedule::assign({},{}));check(!SpeedAwareSchedule::assign({{1,-1}},{{1,1}}));check(!SpeedAwareSchedule::assign({},{{1,0}}));check(!SpeedAwareSchedule::assign({{1,LLONG_MAX},{2,1}},{{1,1}}));auto p=SpeedAwareSchedule::assign({{1,1}},{{9,1},{2,1}});check(p&&(*p)[0]==2);",
        "left==right&&workers[i].id<workers[best].id", "left==right&&workers[i].id>workers[best].id",
        "exact rational projected-finish list scheduling", "worker IDs break equal projected completion times", "equal projected completion chooses the larger worker identity",
    ),
    _case(
        "dpr-antichain-work-waves", "AntichainWorkWaves", "Antichain work waves", "decomposition",
        "class AntichainWorkWaves { public: static std::optional<std::vector<std::vector<int>>> build(const std::vector<int>& nodes,const std::vector<std::pair<int,int>>& edges); };",
        "std::optional<std::vector<std::vector<int>>> AntichainWorkWaves::build(const std::vector<int>& nodes,const std::vector<std::pair<int,int>>& edges){std::set<int> remaining(nodes.begin(),nodes.end());if(remaining.size()!=nodes.size())return std::nullopt;std::set<std::pair<int,int>> unique;std::map<int,int> indegree;for(int n:nodes)indegree[n]=0;for(auto e:edges){if(!remaining.count(e.first)||!remaining.count(e.second)||e.first==e.second)return std::nullopt;if(unique.insert(e).second)++indegree[e.second];}std::vector<std::vector<int>> waves;while(!remaining.empty()){std::vector<int> wave;for(int n:remaining)if(indegree[n]==0)wave.push_back(n);if(wave.empty())return std::nullopt;waves.push_back(wave);for(int n:wave)remaining.erase(n);for(auto e:unique)if(std::find(wave.begin(),wave.end(),e.first)!=wave.end())--indegree[e.second];}return waves;}",
        "std::optional<std::vector<std::vector<int>>> AntichainWorkWaves::build(const std::vector<int>&,const std::vector<std::pair<int,int>>&){return std::nullopt;}",
        "auto w=AntichainWorkWaves::build({1,2,3,4},{{1,3},{2,3},{3,4}});check(w&&*w==std::vector<std::vector<int>>({{1,2},{3},{4}}));",
        "check(!AntichainWorkWaves::build({1,2},{{1,2},{2,1}}));check(!AntichainWorkWaves::build({1},{{1,2}}));auto w=AntichainWorkWaves::build({2,1},{});check(w&&(*w)[0]==std::vector<int>({1,2}));",
        "waves.push_back(wave);for(int n:wave)remaining.erase(n);", "for(int n:wave){waves.push_back({n});remaining.erase(n);}",
        "stable Kahn decomposition with wave-delayed edge release", "all currently ready nodes enter one sorted antichain before successors", "ready nodes are emitted as singleton waves",
    ),
    _case(
        "dpr-component-affinity-shards", "ComponentAffinityShards", "Component affinity shards", "decomposition",
        "class ComponentAffinityShards { public: static std::optional<std::map<int,std::size_t>> assign(const std::vector<int>& vertices,const std::vector<std::pair<int,int>>& affinity,std::size_t shards); };",
        "std::optional<std::map<int,std::size_t>> ComponentAffinityShards::assign(const std::vector<int>& vertices,const std::vector<std::pair<int,int>>& edges,std::size_t shards){if(shards==0)return std::nullopt;std::map<int,int> parent;for(int v:vertices)if(!parent.emplace(v,v).second)return std::nullopt;std::function<int(int)> root=[&](int x){while(parent[x]!=x)x=parent[x];return x;};for(auto e:edges){if(!parent.count(e.first)||!parent.count(e.second))return std::nullopt;int a=root(e.first),b=root(e.second);if(a!=b)parent[std::max(a,b)]=std::min(a,b);}std::map<int,std::vector<int>> components;for(int v:vertices)components[root(v)].push_back(v);std::map<int,std::size_t> out;std::size_t ordinal=0;for(auto&c:components){for(int v:c.second)out[v]=ordinal%shards;++ordinal;}return out;}",
        "std::optional<std::map<int,std::size_t>> ComponentAffinityShards::assign(const std::vector<int>&,const std::vector<std::pair<int,int>>&,std::size_t){return std::nullopt;}",
        "auto a=ComponentAffinityShards::assign({1,2,3,4},{{1,3},{2,4}},2);check(a&&(*a)[1]==(*a)[3]&&(*a)[2]==(*a)[4]&&(*a)[1]!=(*a)[2]);",
        "check(!ComponentAffinityShards::assign({1,1},{},2));check(!ComponentAffinityShards::assign({1},{{1,2}},2));check(!ComponentAffinityShards::assign({1},{},0));",
        "parent[std::max(a,b)]=std::min(a,b);", "if(e.first>e.second)parent[a]=b;",
        "canonical connected-component affinity assignment", "component minima establish stable component order before shard assignment", "ascending affinity edges are incorrectly ignored",
    ),
    _case(
        "dpr-sparse-row-lpt-shards", "SparseRowLptShards", "Sparse row LPT shards", "decomposition",
        "class SparseRowLptShards { public: struct Plan{std::vector<std::vector<std::size_t>> rows;std::vector<std::size_t> loads;}; static std::optional<Plan> assign(const std::vector<std::size_t>& offsets,std::size_t workers); };",
        "std::optional<SparseRowLptShards::Plan> SparseRowLptShards::assign(const std::vector<std::size_t>& offsets,std::size_t workers){if(workers==0||offsets.empty()||offsets[0]!=0||!std::is_sorted(offsets.begin(),offsets.end()))return std::nullopt;std::vector<std::pair<std::size_t,std::size_t>> rows;for(std::size_t r=0;r+1<offsets.size();++r)rows.push_back({offsets[r+1]-offsets[r],r});std::sort(rows.begin(),rows.end(),[](auto a,auto b){return a.first>b.first||(a.first==b.first&&a.second<b.second);});Plan out;out.rows.resize(workers);out.loads.assign(workers,0);for(auto row:rows){std::size_t w=0;for(std::size_t i=1;i<workers;++i)if(std::tie(out.loads[i],i)<std::tie(out.loads[w],w))w=i;out.rows[w].push_back(row.second);out.loads[w]+=row.first;}for(auto&v:out.rows)std::sort(v.begin(),v.end());return out;}",
        "std::optional<SparseRowLptShards::Plan> SparseRowLptShards::assign(const std::vector<std::size_t>&,std::size_t){return std::nullopt;}",
        "auto p=SparseRowLptShards::assign({0,5,6,10,10},2);check(p&&p->loads==std::vector<std::size_t>({5,5}));check(p->rows[0]==std::vector<std::size_t>({0,3}));",
        "check(!SparseRowLptShards::assign({1,2},1));check(!SparseRowLptShards::assign({0,2,1},1));check(!SparseRowLptShards::assign({0},0));auto p=SparseRowLptShards::assign({0,0,0},2);check(p&&p->rows[0]==std::vector<std::size_t>({0,1})&&p->rows[1].empty());auto q=SparseRowLptShards::assign({0,3,5,6},2);check(q&&q->rows[0]==std::vector<std::size_t>({0})&&q->rows[1]==std::vector<std::size_t>({1,2}));",
        "a.first>b.first", "a.first<b.first",
        "longest-processing-time sparse-row assignment", "row weight comes from monotone CSR offsets and load ties use worker index", "shortest rows are scheduled first instead of LPT order",
    ),
    _case(
        "dpr-stable-three-way-scatter", "StableThreeWayScatter", "Stable three-way scatter", "decomposition",
        "class StableThreeWayScatter { public: struct Result{std::vector<long long> values;std::size_t equal_begin,equal_end;}; static std::optional<Result> scatter(const std::vector<long long>& input,long long pivot,std::size_t block); };",
        "std::optional<StableThreeWayScatter::Result> StableThreeWayScatter::scatter(const std::vector<long long>& input,long long pivot,std::size_t block){if(block==0)return std::nullopt;std::vector<std::array<std::size_t,3>> counts;for(std::size_t b=0;b<input.size();b+=block){std::array<std::size_t,3> c{};for(std::size_t i=b;i<std::min(input.size(),b+block);++i)++c[input[i]<pivot?0:input[i]==pivot?1:2];counts.push_back(c);}std::array<std::size_t,3> total{};for(auto c:counts)for(int k=0;k<3;++k)total[k]+=c[k];Result out;out.values.reserve(input.size());for(int k=0;k<3;++k)for(long long v:input)if((v<pivot?0:v==pivot?1:2)==k)out.values.push_back(v);out.equal_begin=total[0];out.equal_end=total[0]+total[1];return out;}",
        "std::optional<StableThreeWayScatter::Result> StableThreeWayScatter::scatter(const std::vector<long long>&,long long,std::size_t){return std::nullopt;}",
        "auto r=StableThreeWayScatter::scatter({4,1,3,2,3,0},3,2);check(r&&r->values==std::vector<long long>({1,2,0,3,3,4})&&r->equal_begin==3&&r->equal_end==5);",
        "check(!StableThreeWayScatter::scatter({},0,0));auto r=StableThreeWayScatter::scatter({},2,3);check(r&&r->values.empty()&&r->equal_begin==0);auto q=StableThreeWayScatter::scatter({2,1,2,1},2,1);check(q&&q->values==std::vector<long long>({1,1,2,2}));",
        "for(long long v:input)", "for(long long v:std::vector<long long>(input.rbegin(),input.rend()))",
        "block-counted stable less/equal/greater scatter", "global offsets preserve source order independently within all three classes", "each class is filled in reverse source order",
    ),
    _case(
        "dpr-permutation-cycle-shards", "PermutationCycleShards", "Permutation cycle shards", "decomposition",
        "class PermutationCycleShards { public: static std::optional<std::vector<std::vector<std::vector<std::size_t>>>> partition(const std::vector<std::size_t>& permutation,std::size_t workers); };",
        "std::optional<std::vector<std::vector<std::vector<std::size_t>>>> PermutationCycleShards::partition(const std::vector<std::size_t>& p,std::size_t workers){if(workers==0)return std::nullopt;std::vector<bool> seen_value(p.size());for(std::size_t x:p){if(x>=p.size()||seen_value[x])return std::nullopt;seen_value[x]=true;}std::vector<bool> seen(p.size());std::vector<std::vector<std::size_t>> cycles;for(std::size_t start=0;start<p.size();++start)if(!seen[start]){std::vector<std::size_t> cycle;std::size_t x=start;do{seen[x]=true;cycle.push_back(x);x=p[x];}while(x!=start);auto it=std::min_element(cycle.begin(),cycle.end());std::rotate(cycle.begin(),it,cycle.end());cycles.push_back(cycle);}std::sort(cycles.begin(),cycles.end());std::vector<std::vector<std::vector<std::size_t>>> out(workers);for(std::size_t i=0;i<cycles.size();++i)out[i%workers].push_back(cycles[i]);return out;}",
        "std::optional<std::vector<std::vector<std::vector<std::size_t>>>> PermutationCycleShards::partition(const std::vector<std::size_t>&,std::size_t){return std::nullopt;}",
        "auto p=PermutationCycleShards::partition({1,0,4,2,3},2);check(p&&(*p)[0][0]==std::vector<std::size_t>({0,1})&&(*p)[1][0]==std::vector<std::size_t>({2,4,3}));",
        "check(!PermutationCycleShards::partition({0,0},1));check(!PermutationCycleShards::partition({2,0},1));check(!PermutationCycleShards::partition({},0));auto p=PermutationCycleShards::partition({},2);check(p&&p->size()==2);auto q=PermutationCycleShards::partition({2,0,1},1);check(q&&(*q)[0][0]==std::vector<std::size_t>({0,2,1}));",
        "auto it=std::min_element(cycle.begin(),cycle.end());std::rotate(cycle.begin(),it,cycle.end());", "std::sort(cycle.begin(),cycle.end());",
        "minimum-rotated permutation cycles assigned without splitting", "input must be a complete permutation and empty permutations remain valid", "cycle traversal is incorrectly replaced by sorted vertex order",
    ),
    _case(
        "dpr-block-cyclic-matrix-tiles", "BlockCyclicMatrixTiles", "Block cyclic matrix tiles", "decomposition",
        "class BlockCyclicMatrixTiles { public: struct Tile{int row0,col0,row1,col1,worker;}; static std::optional<std::vector<Tile>> assign(int rows,int cols,int block_rows,int block_cols,int worker_rows,int worker_cols); };",
        "std::optional<std::vector<BlockCyclicMatrixTiles::Tile>> BlockCyclicMatrixTiles::assign(int rows,int cols,int br,int bc,int wr,int wc){if(rows<=0||cols<=0||br<=0||bc<=0||wr<=0||wc<=0)return std::nullopt;std::vector<Tile> out;int r=0,tr=0;for(;;){int row1; if(__builtin_add_overflow(r,br,&row1))row1=rows; else if(row1>rows)row1=rows;int c=0,tc=0;for(;;){int col1; if(__builtin_add_overflow(c,bc,&col1))col1=cols; else if(col1>cols)col1=cols;long long owner=static_cast<long long>(tr%wr)*wc+(tc%wc);if(owner>INT_MAX)return std::nullopt;out.push_back({r,c,row1,col1,static_cast<int>(owner)});if(col1==cols)break;c=col1;++tc;}if(row1==rows)break;r=row1;++tr;}return out;}",
        "std::optional<std::vector<BlockCyclicMatrixTiles::Tile>> BlockCyclicMatrixTiles::assign(int,int,int,int,int,int){return std::nullopt;}",
        "auto t=BlockCyclicMatrixTiles::assign(5,5,2,3,2,2);check(t&&t->size()==6);check((*t)[0].worker==0&&(*t)[1].worker==1&&(*t)[2].worker==2);check(t->back().row1==5&&t->back().col1==5);",
        "check(!BlockCyclicMatrixTiles::assign(2,2,0,1,1,1));check(!BlockCyclicMatrixTiles::assign(2,2,1,1,0,1));auto t=BlockCyclicMatrixTiles::assign(1,1,4,4,2,2);check(t&&t->size()==1&&(*t)[0].worker==0);auto q=BlockCyclicMatrixTiles::assign(3,3,1,2,2,3);check(q&&(*q)[2].worker==3);auto z=BlockCyclicMatrixTiles::assign(INT_MAX,1,INT_MAX-1,1,1,1);check(z&&z->size()==2&&z->back().row1==INT_MAX);",
        "static_cast<long long>(tr%wr)*wc+(tc%wc)", "static_cast<long long>(tc%wc)*wr+(tr%wr)",
        "two-dimensional block-cyclic process-grid assignment", "partial edge tiles clip while process coordinates remain row-major", "process-grid coordinates are transposed",
    ),
)


assert len(CASES) == 12
