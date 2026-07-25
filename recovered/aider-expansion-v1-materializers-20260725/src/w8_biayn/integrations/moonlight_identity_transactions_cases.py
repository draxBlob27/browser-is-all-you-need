"""Case inventory for the identity/collision/reset/transactions expansion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IdentityTransactionCase:
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


def _case(
    task_id: str,
    class_name: str,
    title: str,
    group: str,
    api: str,
    definition: str,
    starter: str,
    visible: str,
    hidden: str,
    negative_old: str,
    negative_new: str,
    mechanism: str,
    boundary: str,
    negative_reason: str,
) -> IdentityTransactionCase:
    return IdentityTransactionCase(
        task_id, class_name, title, group, api, definition, starter,
        visible, hidden, negative_old, negative_new, mechanism, boundary,
        negative_reason,
    )


CASES: tuple[IdentityTransactionCase, ...] = (
    _case(
        "idtx-generation-slot-pool", "GenerationSlotPool", "Generation slot pool", "identity",
        "class GenerationSlotPool { public: struct Handle { int slot; unsigned generation; bool operator==(const Handle& o) const { return slot==o.slot&&generation==o.generation; } }; explicit GenerationSlotPool(int capacity); std::optional<Handle> acquire(int payload); bool release(Handle handle); std::optional<int> resolve(Handle handle) const; private: struct Slot { unsigned generation=1; std::optional<int> payload; }; std::vector<Slot> slots_; };",
        "GenerationSlotPool::GenerationSlotPool(int n):slots_(n>0?static_cast<std::size_t>(n):0){} std::optional<GenerationSlotPool::Handle> GenerationSlotPool::acquire(int p){for(std::size_t i=0;i<slots_.size();++i)if(!slots_[i].payload){slots_[i].payload=p;return Handle{static_cast<int>(i),slots_[i].generation};}return std::nullopt;} bool GenerationSlotPool::release(Handle h){if(h.slot<0||static_cast<std::size_t>(h.slot)>=slots_.size())return false;auto& s=slots_[static_cast<std::size_t>(h.slot)];if(!s.payload||s.generation!=h.generation)return false;s.payload.reset();++s.generation;if(s.generation==0)++s.generation;return true;} std::optional<int> GenerationSlotPool::resolve(Handle h)const{if(h.slot<0||static_cast<std::size_t>(h.slot)>=slots_.size())return std::nullopt;const auto&s=slots_[static_cast<std::size_t>(h.slot)];return s.payload&&s.generation==h.generation?s.payload:std::nullopt;}",
        "GenerationSlotPool::GenerationSlotPool(int n):slots_(n>0?static_cast<std::size_t>(n):0){} std::optional<GenerationSlotPool::Handle> GenerationSlotPool::acquire(int){return std::nullopt;} bool GenerationSlotPool::release(Handle){return false;} std::optional<int> GenerationSlotPool::resolve(Handle)const{return std::nullopt;}",
        "GenerationSlotPool p(1);auto a=p.acquire(7);check(a&&p.resolve(*a)==7);check(p.release(*a));auto b=p.acquire(9);check(b&&b->slot==a->slot&&b->generation!=a->generation);check(!p.resolve(*a));",
        "GenerationSlotPool p(2);check(!p.release({-1,1}));auto a=p.acquire(1);auto b=p.acquire(2);check(a&&b&&!p.acquire(3));check(!p.release({a->slot,a->generation+1}));check(p.resolve(*b)==2);",
        "++s.generation;if(s.generation==0)++s.generation;", "s.generation=1;",
        "generation-stamped reusable slot handles", "a stale handle never resolves after its slot is reused", "release resets the generation and revives stale handles",
    ),
    _case(
        "idtx-monotonic-tombstone-registry", "TombstoneRegistry", "Monotonic tombstone registry", "identity",
        "class TombstoneRegistry { public: long long create(const std::string& name); bool retire(long long id); bool rename(long long id,const std::string& name); std::optional<std::string> lookup(long long id) const; void reset_active(); private: long long next_=1; std::map<long long,std::string> active_; std::set<long long> tombstones_; };",
        "long long TombstoneRegistry::create(const std::string& n){if(n.empty()||next_==LLONG_MAX)return -1;long long id=next_++;active_[id]=n;return id;} bool TombstoneRegistry::retire(long long id){auto it=active_.find(id);if(it==active_.end())return false;active_.erase(it);tombstones_.insert(id);return true;} bool TombstoneRegistry::rename(long long id,const std::string& n){auto it=active_.find(id);if(it==active_.end()||n.empty())return false;it->second=n;return true;} std::optional<std::string> TombstoneRegistry::lookup(long long id)const{auto it=active_.find(id);return it==active_.end()?std::nullopt:std::optional<std::string>(it->second);} void TombstoneRegistry::reset_active(){for(const auto&e:active_)tombstones_.insert(e.first);active_.clear();}",
        "long long TombstoneRegistry::create(const std::string&){return -1;} bool TombstoneRegistry::retire(long long){return false;} bool TombstoneRegistry::rename(long long,const std::string&){return false;} std::optional<std::string> TombstoneRegistry::lookup(long long)const{return std::nullopt;} void TombstoneRegistry::reset_active(){}",
        "TombstoneRegistry r;auto a=r.create(\"a\");auto b=r.create(\"b\");check(a==1&&b==2&&r.retire(a));r.reset_active();check(!r.lookup(b));check(r.create(\"c\")==3);",
        "TombstoneRegistry r;check(r.create(\"\")==-1);auto a=r.create(\"a\");check(!r.retire(99)&&!r.rename(99,\"x\")&&!r.rename(a,\"\"));check(r.rename(a,\"z\")&&r.lookup(a)==\"z\");",
        "active_.clear();", "active_.clear();next_=1;",
        "monotonic allocation with permanent retirement history", "reset removes active entries but never rewinds the identity frontier", "reset rewinds the counter and reissues retired identities",
    ),
    _case(
        "idtx-block-lease-allocator", "BlockLeaseAllocator", "Coalescing block lease allocator", "identity",
        "class BlockLeaseAllocator { public: struct Lease { int begin; int length; bool operator==(const Lease& o) const { return begin==o.begin&&length==o.length; } }; BlockLeaseAllocator(int first,int count); std::optional<Lease> lease(int length); bool release(Lease lease); std::vector<Lease> free_blocks() const; private: std::map<int,int> free_; std::map<int,int> live_; };",
        "BlockLeaseAllocator::BlockLeaseAllocator(int f,int n){if(n>0)free_[f]=n;} std::optional<BlockLeaseAllocator::Lease> BlockLeaseAllocator::lease(int n){if(n<=0)return std::nullopt;for(auto it=free_.begin();it!=free_.end();++it)if(it->second>=n){int b=it->first,left=it->second-n;free_.erase(it);if(left)free_[b+n]=left;live_[b]=n;return Lease{b,n};}return std::nullopt;} bool BlockLeaseAllocator::release(Lease x){auto it=live_.find(x.begin);if(it==live_.end()||it->second!=x.length)return false;live_.erase(it);int b=x.begin,n=x.length;auto next=free_.lower_bound(b);if(next!=free_.begin()){auto prev=std::prev(next);if(prev->first+prev->second==b){b=prev->first;n+=prev->second;free_.erase(prev);}}next=free_.lower_bound(b);if(next!=free_.end()&&b+n==next->first){n+=next->second;free_.erase(next);}free_[b]=n;return true;} std::vector<BlockLeaseAllocator::Lease> BlockLeaseAllocator::free_blocks()const{std::vector<Lease> out;for(const auto&e:free_)out.push_back({e.first,e.second});return out;}",
        "BlockLeaseAllocator::BlockLeaseAllocator(int,int){} std::optional<BlockLeaseAllocator::Lease> BlockLeaseAllocator::lease(int){return std::nullopt;} bool BlockLeaseAllocator::release(Lease){return false;} std::vector<BlockLeaseAllocator::Lease> BlockLeaseAllocator::free_blocks()const{return {};}",
        "BlockLeaseAllocator a(10,8);auto x=a.lease(3);auto y=a.lease(2);check(x==BlockLeaseAllocator::Lease{10,3}&&y==BlockLeaseAllocator::Lease{13,2});check(a.release(*x)&&a.release(*y));check(a.free_blocks()==std::vector<BlockLeaseAllocator::Lease>{{10,8}});",
        "BlockLeaseAllocator a(0,4);check(!a.lease(0));auto x=a.lease(4);check(x&&!a.lease(1));check(!a.release({x->begin,3}));check(a.release(*x));",
        "if(next!=free_.end()&&b+n==next->first)", "if(false&&next!=free_.end()&&b+n==next->first)",
        "first-fit contiguous leases with bidirectional gap coalescing", "exact-fit removal and two-sided adjacent releases reconstruct one block", "released neighbors remain fragmented",
    ),
    _case(
        "idtx-worker-epoch-id", "WorkerEpochIds", "Worker epoch packed IDs", "identity",
        "class WorkerEpochIds { public: struct Parts { int epoch; int worker; int sequence; }; WorkerEpochIds(int workers,int sequence_bits); std::optional<long long> next(int worker,int epoch); std::optional<Parts> decode(long long id) const; private: int workers_; int bits_; std::vector<int> epoch_; std::vector<int> sequence_; };",
        "WorkerEpochIds::WorkerEpochIds(int w,int b):workers_(w),bits_(b),epoch_(w>0?static_cast<std::size_t>(w):0,-1),sequence_(w>0?static_cast<std::size_t>(w):0,0){} std::optional<long long> WorkerEpochIds::next(int w,int e){if(w<0||w>=workers_||e<0||bits_<=0||bits_>30||e<epoch_[w])return std::nullopt;if(e>epoch_[w]){epoch_[w]=e;sequence_[w]=0;}long long limit=1LL<<bits_;if(sequence_[w]>=limit)return std::nullopt;long long id=(static_cast<long long>(e)*workers_+w)*limit+sequence_[w]++;return id;} std::optional<WorkerEpochIds::Parts> WorkerEpochIds::decode(long long id)const{if(id<0||workers_<=0||bits_<=0||bits_>30)return std::nullopt;long long limit=1LL<<bits_,head=id/limit;return Parts{static_cast<int>(head/workers_),static_cast<int>(head%workers_),static_cast<int>(id%limit)};}",
        "WorkerEpochIds::WorkerEpochIds(int w,int b):workers_(w),bits_(b){} std::optional<long long> WorkerEpochIds::next(int,int){return std::nullopt;} std::optional<WorkerEpochIds::Parts> WorkerEpochIds::decode(long long)const{return std::nullopt;}",
        "WorkerEpochIds ids(3,2);auto a=ids.next(1,4);auto b=ids.next(1,4);check(a&&b&&*b==*a+1);auto p=ids.decode(*a);check(p&&p->epoch==4&&p->worker==1&&p->sequence==0);",
        "WorkerEpochIds ids(1,1);check(ids.next(0,2).has_value()&&ids.next(0,2).has_value()&&!ids.next(0,2));check(!ids.next(0,1));check(ids.next(0,3).has_value());check(!ids.next(2,3));WorkerEpochIds q(1,2);check(q.next(0,3).has_value()&&!q.next(0,2));",
        "||e<epoch_[w]", "||false",
        "worker-partitioned packed epoch and bounded sequence identity", "epoch regression and per-worker sequence exhaustion reject without mutation", "a regressed epoch rewinds a worker and can collide",
    ),
    _case(
        "idtx-hierarchical-scope-id", "ScopedIdentityTree", "Hierarchical scope identities", "identity",
        "class ScopedIdentityTree { public: bool add_scope(const std::string& parent,const std::string& child); std::optional<std::string> allocate(const std::string& scope); bool erase_scope(const std::string& scope); bool valid(const std::string& id) const; private: struct Scope { long long next=1; std::set<std::string> children; }; std::map<std::string,Scope> scopes_{{\"root\",{}}}; std::set<std::string> live_; };",
        "bool ScopedIdentityTree::add_scope(const std::string&p,const std::string&c){if(c.empty()||c==\"root\"||!scopes_.count(p)||scopes_.count(c))return false;scopes_[p].children.insert(c);scopes_[c]=Scope{};return true;} std::optional<std::string> ScopedIdentityTree::allocate(const std::string&s){auto it=scopes_.find(s);if(it==scopes_.end())return std::nullopt;std::string id=s+\"#\"+std::to_string(it->second.next++);live_.insert(id);return id;} bool ScopedIdentityTree::erase_scope(const std::string&s){if(s==\"root\"||!scopes_.count(s))return false;std::set<std::string> doomed{s};for(auto it=doomed.begin();it!=doomed.end();++it)for(const auto&c:scopes_[*it].children)doomed.insert(c);for(const auto&d:doomed){scopes_.erase(d);for(auto i=live_.begin();i!=live_.end();)i->rfind(d+\"#\",0)==0?i=live_.erase(i):++i;}for(auto&e:scopes_)for(const auto&d:doomed)e.second.children.erase(d);return true;} bool ScopedIdentityTree::valid(const std::string&id)const{return live_.count(id)>0;}",
        "bool ScopedIdentityTree::add_scope(const std::string&,const std::string&){return false;} std::optional<std::string> ScopedIdentityTree::allocate(const std::string&){return std::nullopt;} bool ScopedIdentityTree::erase_scope(const std::string&){return false;} bool ScopedIdentityTree::valid(const std::string&)const{return false;}",
        "ScopedIdentityTree t;check(t.add_scope(\"root\",\"team\")&&t.add_scope(\"team\",\"job\"));auto a=t.allocate(\"team\");auto b=t.allocate(\"job\");check(a&&b&&t.erase_scope(\"team\")&&!t.valid(*a)&&!t.valid(*b));",
        "ScopedIdentityTree t;check(!t.add_scope(\"missing\",\"x\")&&!t.erase_scope(\"root\"));check(t.add_scope(\"root\",\"x\")&&!t.add_scope(\"root\",\"x\"));auto a=t.allocate(\"root\");check(a&&t.valid(*a));",
        "for(const auto&c:scopes_[*it].children)doomed.insert(c);", "/* descendants are intentionally retained */",
        "parent-owned scope tree with scoped monotonic identities", "erasing a scope recursively invalidates every descendant identity but not siblings", "only the named scope is erased",
    ),
    _case(
        "idtx-content-probe-id", "ContentProbeIds", "Content-addressed probing IDs", "identity",
        "class ContentProbeIds { public: explicit ContentProbeIds(int modulus); std::optional<int> intern(const std::string& payload); std::optional<std::string> payload(int id) const; private: int modulus_; std::map<int,std::string> slots_; static unsigned digest(const std::string& text); };",
        "ContentProbeIds::ContentProbeIds(int m):modulus_(m){} unsigned ContentProbeIds::digest(const std::string&s){unsigned h=2166136261U;for(unsigned char c:s){h^=c;h*=16777619U;}return h;} std::optional<int> ContentProbeIds::intern(const std::string&s){if(s.empty()||modulus_<=0)return std::nullopt;int start=static_cast<int>(digest(s)%static_cast<unsigned>(modulus_));for(int n=0;n<modulus_;++n){int id=(start+n)%modulus_;auto it=slots_.find(id);if(it==slots_.end()){slots_[id]=s;return id;}if(it->second==s)return id;}return std::nullopt;} std::optional<std::string> ContentProbeIds::payload(int id)const{auto it=slots_.find(id);return it==slots_.end()?std::nullopt:std::optional<std::string>(it->second);}",
        "ContentProbeIds::ContentProbeIds(int m):modulus_(m){} unsigned ContentProbeIds::digest(const std::string&){return 0;} std::optional<int> ContentProbeIds::intern(const std::string&){return std::nullopt;} std::optional<std::string> ContentProbeIds::payload(int)const{return std::nullopt;}",
        "ContentProbeIds p(2);auto a=p.intern(\"alpha\");auto again=p.intern(\"alpha\");auto b=p.intern(\"beta\");check(a&&again&&b&&*a==*again&&*a!=*b&&p.payload(*b)==\"beta\");",
        "ContentProbeIds p(1);check(!p.intern(\"\"));auto a=p.intern(\"x\");check(a&&!p.intern(\"y\"));ContentProbeIds bad(0);check(!bad.intern(\"x\"));",
        "if(it->second==s)return id;", "if(it->second!=s)return id;",
        "deterministic digest start with linear collision probing and idempotent payloads", "equal payloads reuse one ID while unequal colliders probe without overwrite", "a different colliding payload aliases the occupied ID",
    ),
    _case(
        "idtx-dense-handle-table", "DenseHandleTable", "Dense swap-remove handle table", "identity",
        "class DenseHandleTable { public: int insert(int value); bool erase(int handle); std::optional<int> get(int handle) const; std::vector<int> dense_values() const; private: struct Entry { int handle; int value; }; int next_=1; std::vector<Entry> dense_; std::map<int,std::size_t> sparse_; };",
        "int DenseHandleTable::insert(int v){int h=next_++;sparse_[h]=dense_.size();dense_.push_back({h,v});return h;} bool DenseHandleTable::erase(int h){auto it=sparse_.find(h);if(it==sparse_.end())return false;std::size_t i=it->second,last=dense_.size()-1;if(i!=last){dense_[i]=dense_[last];sparse_[dense_[i].handle]=i;}dense_.pop_back();sparse_.erase(it);return true;} std::optional<int> DenseHandleTable::get(int h)const{auto it=sparse_.find(h);return it==sparse_.end()?std::nullopt:std::optional<int>(dense_[it->second].value);} std::vector<int> DenseHandleTable::dense_values()const{std::vector<int> out;for(const auto&e:dense_)out.push_back(e.value);return out;}",
        "int DenseHandleTable::insert(int){return -1;} bool DenseHandleTable::erase(int){return false;} std::optional<int> DenseHandleTable::get(int)const{return std::nullopt;} std::vector<int> DenseHandleTable::dense_values()const{return {};}",
        "DenseHandleTable t;auto a=t.insert(10);auto b=t.insert(20);auto c=t.insert(30);check(t.erase(b)&&t.get(a)==10&&t.get(c)==30);auto d=t.insert(40);check(t.get(c)==30&&t.get(d)==40);check(t.dense_values()==std::vector<int>({10,30,40}));",
        "DenseHandleTable t;check(!t.erase(1));auto a=t.insert(4);check(t.erase(a)&&!t.get(a));auto b=t.insert(5);check(b!=a);",
        "sparse_[dense_[i].handle]=i;", "/* moved sparse index is not repaired */",
        "dense storage with stable sparse handles and swap-remove repair", "moving the last dense entry updates exactly its sparse indirection", "swap-remove leaves the moved handle pointing past its entry",
    ),
    _case(
        "idtx-interval-id-leases", "IntervalLeaseBook", "Splittable interval identity leases", "identity",
        "class IntervalLeaseBook { public: bool grant(int owner,long long begin,long long end); bool release(int owner,long long begin,long long end); std::vector<std::tuple<long long,long long,int>> leases() const; private: std::map<long long,std::pair<long long,int>> by_begin_; };",
        "bool IntervalLeaseBook::grant(int o,long long b,long long e){if(o<=0||b>=e)return false;auto n=by_begin_.lower_bound(b);if(n!=by_begin_.end()&&n->first<e)return false;if(n!=by_begin_.begin()&&std::prev(n)->second.first>b)return false;by_begin_[b]={e,o};return true;} bool IntervalLeaseBook::release(int o,long long b,long long e){if(b>=e)return false;auto it=by_begin_.upper_bound(b);if(it==by_begin_.begin())return false;--it;long long lb=it->first,le=it->second.first;int owner=it->second.second;if(owner!=o||b<lb||e>le)return false;by_begin_.erase(it);if(lb<b)by_begin_[lb]={b,o};if(e<le)by_begin_[e]={le,o};return true;} std::vector<std::tuple<long long,long long,int>> IntervalLeaseBook::leases()const{std::vector<std::tuple<long long,long long,int>> out;for(const auto&e:by_begin_)out.emplace_back(e.first,e.second.first,e.second.second);return out;}",
        "bool IntervalLeaseBook::grant(int,long long,long long){return false;} bool IntervalLeaseBook::release(int,long long,long long){return false;} std::vector<std::tuple<long long,long long,int>> IntervalLeaseBook::leases()const{return {};}",
        "IntervalLeaseBook b;check(b.grant(1,10,20)&&b.release(1,13,17));check(b.leases()==std::vector<std::tuple<long long,long long,int>>{{10,13,1},{17,20,1}});",
        "IntervalLeaseBook b;check(!b.grant(0,1,2)&&!b.grant(1,2,2));check(b.grant(1,0,5)&&b.grant(2,5,9)&&!b.grant(3,4,6));check(!b.release(2,0,1));",
        "if(lb<b)by_begin_[lb]={b,o};if(e<le)by_begin_[e]={le,o};", "/* partial release discards the complete lease */",
        "ordered half-open interval ownership with partial-release splitting", "touching leases coexist and a strict subrange release creates two residual leases", "any release removes the entire containing lease",
    ),
    _case(
        "idtx-namespace-quota-ids", "NamespaceQuotaIds", "Namespace quota identities", "identity",
        "class NamespaceQuotaIds { public: bool add_namespace(const std::string& name,int quota); std::optional<std::string> allocate(const std::string& name); bool release(const std::string& id); int active(const std::string& name) const; private: struct Space { int quota; int active=0; long long next=1; }; std::map<std::string,Space> spaces_; std::map<std::string,std::string> owner_; };",
        "bool NamespaceQuotaIds::add_namespace(const std::string&n,int q){return !n.empty()&&q>0&&spaces_.emplace(n,Space{q}).second;} std::optional<std::string> NamespaceQuotaIds::allocate(const std::string&n){auto it=spaces_.find(n);if(it==spaces_.end()||it->second.active>=it->second.quota)return std::nullopt;auto id=n+\"/\"+std::to_string(it->second.next++);++it->second.active;owner_[id]=n;return id;} bool NamespaceQuotaIds::release(const std::string&id){auto it=owner_.find(id);if(it==owner_.end())return false;--spaces_[it->second].active;owner_.erase(it);return true;} int NamespaceQuotaIds::active(const std::string&n)const{auto it=spaces_.find(n);return it==spaces_.end()?-1:it->second.active;}",
        "bool NamespaceQuotaIds::add_namespace(const std::string&,int){return false;} std::optional<std::string> NamespaceQuotaIds::allocate(const std::string&){return std::nullopt;} bool NamespaceQuotaIds::release(const std::string&){return false;} int NamespaceQuotaIds::active(const std::string&)const{return -1;}",
        "NamespaceQuotaIds q;check(q.add_namespace(\"a\",1)&&q.add_namespace(\"b\",2));auto a=q.allocate(\"a\");check(a&&!q.allocate(\"a\")&&q.allocate(\"b\"));check(q.release(*a)&&q.active(\"a\")==0);",
        "NamespaceQuotaIds q;check(!q.add_namespace(\"\",1)&&!q.add_namespace(\"x\",0));check(q.add_namespace(\"x\",1)&&!q.add_namespace(\"x\",2));check(!q.release(\"missing\")&&q.active(\"missing\")==-1);",
        "if(it==spaces_.end()||it->second.active>=it->second.quota)return std::nullopt;", "if(it==spaces_.end())return std::nullopt;",
        "independent namespace quotas with monotonic local sequences", "quota rejection consumes neither active capacity nor the local sequence", "allocation ignores the namespace quota",
    ),
    _case(
        "idtx-epoch-sequence-book", "EpochSequenceBook", "Epoch sequence book", "identity",
        "class EpochSequenceBook { public: bool advance(int epoch); std::optional<std::pair<int,int>> issue(const std::string& stream); bool live(std::pair<int,int> token) const; private: int epoch_=0; std::map<std::string,int> next_; std::set<std::pair<int,int>> live_; };",
        "bool EpochSequenceBook::advance(int e){if(e<=epoch_)return false;epoch_=e;next_.clear();live_.clear();return true;} std::optional<std::pair<int,int>> EpochSequenceBook::issue(const std::string&s){if(s.empty()||epoch_<=0)return std::nullopt;int seq=++next_[s];auto token=std::make_pair(epoch_,seq);while(live_.count(token))token.second=++next_[s];live_.insert(token);return token;} bool EpochSequenceBook::live(std::pair<int,int>t)const{return t.first==epoch_&&live_.count(t)>0;}",
        "bool EpochSequenceBook::advance(int){return false;} std::optional<std::pair<int,int>> EpochSequenceBook::issue(const std::string&){return std::nullopt;} bool EpochSequenceBook::live(std::pair<int,int>)const{return false;}",
        "EpochSequenceBook b;check(b.advance(4));auto a=b.issue(\"x\");auto c=b.issue(\"x\");check(a&&c&&a->second==1&&c->second==2);check(b.advance(5)&&!b.live(*a));auto d=b.issue(\"x\");check(d&&d->first==5&&d->second==1);",
        "EpochSequenceBook b;check(!b.issue(\"x\")&&!b.advance(0)&&b.advance(1)&&!b.advance(1)&&!b.issue(\"\"));",
        "next_.clear();", "/* per-stream sequence positions survive the epoch */",
        "epoch transition with per-stream sequences and token retirement", "advancing strictly clears all old-token authority and restarts stream sequences", "old sequence positions survive the epoch change",
    ),
    _case(
        "idtx-partition-stride-ids", "PartitionStrideIds", "Partition stride identities", "identity",
        "class PartitionStrideIds { public: explicit PartitionStrideIds(int partitions); std::optional<long long> next(int partition); bool reconfigure(int partitions); std::vector<long long> issued() const; private: int partitions_; std::vector<long long> next_; std::vector<long long> issued_; };",
        "PartitionStrideIds::PartitionStrideIds(int p):partitions_(p),next_(p>0?static_cast<std::size_t>(p):0){for(int i=0;i<p;++i)next_[static_cast<std::size_t>(i)]=i;} std::optional<long long> PartitionStrideIds::next(int p){if(p<0||p>=partitions_)return std::nullopt;long long id=next_[static_cast<std::size_t>(p)];if(id>LLONG_MAX-partitions_)return std::nullopt;next_[static_cast<std::size_t>(p)]+=partitions_;issued_.push_back(id);return id;} bool PartitionStrideIds::reconfigure(int p){if(p<=0||!issued_.empty())return false;partitions_=p;next_.resize(static_cast<std::size_t>(p));for(int i=0;i<p;++i)next_[static_cast<std::size_t>(i)]=i;return true;} std::vector<long long> PartitionStrideIds::issued()const{return issued_;}",
        "PartitionStrideIds::PartitionStrideIds(int p):partitions_(p){} std::optional<long long> PartitionStrideIds::next(int){return std::nullopt;} bool PartitionStrideIds::reconfigure(int){return false;} std::vector<long long> PartitionStrideIds::issued()const{return {};}",
        "PartitionStrideIds p(3);check(p.next(0)==0&&p.next(1)==1&&p.next(0)==3&&p.next(2)==2);check(!p.reconfigure(4));",
        "PartitionStrideIds p(2);check(!p.next(-1)&&!p.next(2));PartitionStrideIds q(0);check(!q.next(0)&&q.reconfigure(2)&&q.next(1)==1);",
        "if(p<=0||!issued_.empty())return false;", "if(p<=0)return false;",
        "partition-specific arithmetic progressions with immutable live stride", "reconfiguration is allowed only before the first issue to prevent overlap", "stride changes after issuance and creates colliding progressions",
    ),
    _case(
        "idtx-capability-token-pool", "CapabilityTokenPool", "Revocable capability token pool", "identity",
        "class CapabilityTokenPool { public: std::optional<unsigned long long> mint(int resource); bool revoke(unsigned long long token); std::optional<int> authorize(unsigned long long token) const; void rotate_epoch(); private: unsigned epoch_=1; unsigned sequence_=1; std::map<unsigned long long,int> live_; std::set<unsigned long long> revoked_; };",
        "std::optional<unsigned long long> CapabilityTokenPool::mint(int r){if(r<=0||sequence_==UINT_MAX)return std::nullopt;unsigned long long t=(static_cast<unsigned long long>(epoch_)<<32)|sequence_++;live_[t]=r;return t;} bool CapabilityTokenPool::revoke(unsigned long long t){auto it=live_.find(t);if(it==live_.end())return false;live_.erase(it);revoked_.insert(t);return true;} std::optional<int> CapabilityTokenPool::authorize(unsigned long long t)const{auto it=live_.find(t);return it==live_.end()?std::nullopt:std::optional<int>(it->second);} void CapabilityTokenPool::rotate_epoch(){live_.clear();revoked_.clear();++epoch_;if(epoch_==0)++epoch_;sequence_=1;}",
        "std::optional<unsigned long long> CapabilityTokenPool::mint(int){return std::nullopt;} bool CapabilityTokenPool::revoke(unsigned long long){return false;} std::optional<int> CapabilityTokenPool::authorize(unsigned long long)const{return std::nullopt;} void CapabilityTokenPool::rotate_epoch(){}",
        "CapabilityTokenPool p;auto a=p.mint(7);check(a&&p.authorize(*a)==7&&p.revoke(*a)&&!p.authorize(*a));auto b=p.mint(7);check(b&&*b!=*a);p.rotate_epoch();check(!p.authorize(*b));auto c=p.mint(7);check(c&&*c!=*b&&*c!=*a);",
        "CapabilityTokenPool p;check(!p.mint(0)&&!p.revoke(1));auto a=p.mint(1);check(a&&p.authorize(*a)==1);",
        "++epoch_;if(epoch_==0)++epoch_;sequence_=1;", "sequence_=1;",
        "epoch-scoped opaque capability tokens with explicit revocation", "epoch rotation invalidates all tokens and changes the high identity component", "rotation rewinds only sequence and reissues old capabilities",
    ),
    _case(
        "idtx-reversible-id-stack", "ReversibleIdStack", "Checkpointed reversible IDs", "identity",
        "class ReversibleIdStack { public: using Checkpoint=std::size_t; int allocate(); Checkpoint checkpoint() const; bool rollback(Checkpoint checkpoint); bool release(int id); std::vector<int> live() const; private: int next_=1; std::vector<int> log_; std::set<int> live_; };",
        "int ReversibleIdStack::allocate(){int id=next_++;live_.insert(id);log_.push_back(id);return id;} ReversibleIdStack::Checkpoint ReversibleIdStack::checkpoint()const{return log_.size();} bool ReversibleIdStack::rollback(Checkpoint c){if(c>log_.size())return false;while(log_.size()>c){live_.erase(log_.back());log_.pop_back();--next_;}return true;} bool ReversibleIdStack::release(int id){return live_.erase(id)>0;} std::vector<int> ReversibleIdStack::live()const{return {live_.begin(),live_.end()};}",
        "int ReversibleIdStack::allocate(){return -1;} ReversibleIdStack::Checkpoint ReversibleIdStack::checkpoint()const{return 0;} bool ReversibleIdStack::rollback(Checkpoint){return false;} bool ReversibleIdStack::release(int){return false;} std::vector<int> ReversibleIdStack::live()const{return {};}",
        "ReversibleIdStack s;auto a=s.allocate();auto c=s.checkpoint();auto b=s.allocate();check(s.release(a)&&s.rollback(c));check(s.live().empty());check(s.allocate()==b);",
        "ReversibleIdStack s;auto c=s.checkpoint();check(!s.rollback(c+1));auto a=s.allocate();check(s.release(a)&&!s.release(a));check(s.rollback(c));",
        "while(log_.size()>c){live_.erase(log_.back());log_.pop_back();--next_;}", "while(log_.size()>c){live_.erase(log_.back());log_.pop_back();}",
        "LIFO allocation log with exact frontier rollback", "rollback removes post-checkpoint IDs and makes their contiguous suffix issuable again", "rollback removes liveness but leaves the allocation frontier advanced",
    ),
    _case(
        "idtx-reserved-band-allocator", "ReservedBandAllocator", "Reserved band allocator", "identity",
        "class ReservedBandAllocator { public: bool reserve_band(const std::string& name,int begin,int end); std::optional<int> allocate(const std::string& name,int hint); bool release(const std::string& name,int id); private: struct Band { int begin; int end; std::set<int> used; }; std::map<std::string,Band> bands_; };",
        "bool ReservedBandAllocator::reserve_band(const std::string&n,int b,int e){if(n.empty()||b>=e)return false;for(const auto&x:bands_)if(std::max(b,x.second.begin)<std::min(e,x.second.end))return false;return bands_.emplace(n,Band{b,e,{}}).second;} std::optional<int> ReservedBandAllocator::allocate(const std::string&n,int h){auto it=bands_.find(n);if(it==bands_.end())return std::nullopt;int start=(h>=it->second.begin&&h<it->second.end)?h:it->second.begin;for(int pass=0;pass<2;++pass){int b=pass?it->second.begin:start,e=pass?start:it->second.end;for(int id=b;id<e;++id)if(!it->second.used.count(id)){it->second.used.insert(id);return id;}}return std::nullopt;} bool ReservedBandAllocator::release(const std::string&n,int id){auto it=bands_.find(n);return it!=bands_.end()&&it->second.used.erase(id)>0;}",
        "bool ReservedBandAllocator::reserve_band(const std::string&,int,int){return false;} std::optional<int> ReservedBandAllocator::allocate(const std::string&,int){return std::nullopt;} bool ReservedBandAllocator::release(const std::string&,int){return false;}",
        "ReservedBandAllocator a;check(a.reserve_band(\"sys\",10,13)&&a.reserve_band(\"usr\",20,22));check(a.allocate(\"sys\",12)==12&&a.allocate(\"sys\",12)==10&&a.allocate(\"sys\",12)==11&&!a.allocate(\"sys\",0));",
        "ReservedBandAllocator a;check(!a.reserve_band(\"\",0,1)&&a.reserve_band(\"a\",0,3)&&!a.reserve_band(\"b\",2,4));auto x=a.allocate(\"a\",1);check(x&&a.release(\"a\",*x)&&!a.release(\"a\",*x));",
        "if(!it->second.used.count(id)){it->second.used.insert(id);return id;}", "if(!it->second.used.count(id))return id;",
        "non-overlapping reserved bands with hint-centered circular first fit", "allocation never escapes its named half-open band and reserves atomically", "selected identities are returned without being marked used",
    ),
    _case(
        "idtx-alias-component-ids", "AliasComponentIds", "Alias component canonical IDs", "identity",
        "class AliasComponentIds { public: bool add(int id); bool alias(int left,int right); std::optional<int> canonical(int id) const; int components() const; private: mutable std::map<int,int> parent_; std::map<int,int> rank_; int components_=0; int root(int id) const; };",
        "int AliasComponentIds::root(int x)const{auto it=parent_.find(x);if(it==parent_.end())return -1;while(it->second!=x){x=it->second;it=parent_.find(x);}return x;} bool AliasComponentIds::add(int id){if(id<=0||parent_.count(id))return false;parent_[id]=id;rank_[id]=0;++components_;return true;} bool AliasComponentIds::alias(int a,int b){int x=root(a),y=root(b);if(x<0||y<0||x==y)return false;if(rank_[x]<rank_[y]||(rank_[x]==rank_[y]&&x>y))std::swap(x,y);parent_[y]=x;if(rank_[x]==rank_[y])++rank_[x];--components_;return true;} std::optional<int> AliasComponentIds::canonical(int id)const{int r=root(id);return r<0?std::nullopt:std::optional<int>(r);} int AliasComponentIds::components()const{return components_;}",
        "int AliasComponentIds::root(int)const{return -1;} bool AliasComponentIds::add(int){return false;} bool AliasComponentIds::alias(int,int){return false;} std::optional<int> AliasComponentIds::canonical(int)const{return std::nullopt;} int AliasComponentIds::components()const{return 0;}",
        "AliasComponentIds a;check(a.add(3)&&a.add(1)&&a.add(2));check(a.alias(3,1)&&a.alias(2,3));check(a.components()==1&&a.canonical(1)==1&&a.canonical(2)==1);",
        "AliasComponentIds a;check(!a.add(0)&&a.add(1)&&!a.add(1)&&a.add(2));check(!a.alias(1,9)&&a.alias(1,2)&&!a.alias(1,2));check(!a.canonical(9));",
        "if(rank_[x]<rank_[y]||(rank_[x]==rank_[y]&&x>y))std::swap(x,y);", "if(x<y)std::swap(x,y);",
        "union by rank with deterministic existing-root tie handling", "unknown and already-equal unions reject while canonical authority follows rank", "every union chooses the numerically larger root regardless of rank",
    ),
)


assert len(CASES) == 15
assert len({case.task_id for case in CASES}) == 15
assert len({case.mechanism for case in CASES}) == 15
