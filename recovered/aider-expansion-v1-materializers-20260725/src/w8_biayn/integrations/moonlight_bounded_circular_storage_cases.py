"""Task-specific C++ contracts for the bounded/circular storage expansion."""
from __future__ import annotations
from dataclasses import dataclass, replace

@dataclass(frozen=True)
class Case:
    task_id:str; title:str; summary:str; contract:str; mechanism:str; boundary:str
    invariant:str; forbidden:str; header:str; starter:str; reference:str
    visible:str; hidden:str; negative_old:str; negative_new:str; negative_reason:str
    control_old:str="insertion_order()"; control_new:str="insertion_order()"
    @property
    def public_api(self)->str:return self.header
    @property
    def owned_state_algorithm(self)->str:return self.mechanism+" "+self.invariant
    @property
    def mutation_selection_rules(self)->str:return self.mechanism+" "+self.contract
    @property
    def invalid_boundary_behavior(self)->str:return self.mechanism+" "+self.boundary
    @property
    def reference_control_flow(self)->str:return self.reference
    @property
    def deterministic_oracle(self)->str:return self.mechanism+" "+self.visible+" "+self.hidden
    @property
    def topic_negative_fixture(self)->str:return self.mechanism+" "+self.negative_reason+" "+self.negative_old+" "+self.negative_new

def C(*args:str)->Case:return Case(*args)

_HANDCRAFTED=(
 C(
  "capacity-buddy-pool","Buddy Capacity Pool","Allocate and coalesce bounded power-of-two blocks.",
  "Construction requires a nonzero power of two. allocate rounds upward, splits the smallest fitting block, and chooses the lowest offset. release accepts only the exact live block and coalesces XOR buddies.",
  "power-of-two buddy free lists with recursive split and XOR coalescing",
  "Zero or oversize requests return empty; invalid construction throws; stale, partial, and duplicate releases are false; size arithmetic is checked.",
  "Every free block is aligned to its size; free and live blocks partition the pool; no two free buddies remain uncoalesced.","a first-fit interval list without buddy orders",
  r'''struct Block{std::size_t offset;std::size_t size;bool operator==(const Block&x)const{return offset==x.offset&&size==x.size;}};class BuddyPool{public:explicit BuddyPool(std::size_t);std::optional<Block> allocate(std::size_t);bool release(Block);std::size_t largest_free()const;private:std::size_t total_;std::vector<std::set<std::size_t>> free_;std::map<std::size_t,std::size_t> live_;};''',
  r'''BuddyPool::BuddyPool(std::size_t):total_(0){throw std::logic_error("not implemented");}std::optional<Block> BuddyPool::allocate(std::size_t){throw std::logic_error("not implemented");}bool BuddyPool::release(Block){throw std::logic_error("not implemented");}std::size_t BuddyPool::largest_free()const{throw std::logic_error("not implemented");}''',
  r'''static std::size_t order_of(std::size_t n){std::size_t o=0;while((std::size_t{1}<<o)<n)++o;return o;}BuddyPool::BuddyPool(std::size_t n):total_(n){if(!n||(n&(n-1)))throw std::invalid_argument("power of two");free_.resize(order_of(n)+1);free_.back().insert(0);}std::optional<Block> BuddyPool::allocate(std::size_t n){if(!n||n>total_)return std::nullopt;std::size_t wanted=order_of(n),o=wanted;while(o<free_.size()&&free_[o].empty())++o;if(o==free_.size())return std::nullopt;std::size_t at=*free_[o].begin();free_[o].erase(free_[o].begin());while(o>wanted){--o;free_[o].insert(at+(std::size_t{1}<<o));}std::size_t size=std::size_t{1}<<wanted;live_[at]=size;return Block{at,size};}bool BuddyPool::release(Block b){auto it=live_.find(b.offset);if(it==live_.end()||it->second!=b.size)return false;live_.erase(it);std::size_t o=order_of(b.size),at=b.offset;while(o+1<free_.size()){std::size_t buddy=at^(std::size_t{1}<<o);auto pos=free_[o].find(buddy);if(pos==free_[o].end())break;free_[o].erase(pos);at=std::min(at,buddy);++o;}free_[o].insert(at);return true;}std::size_t BuddyPool::largest_free()const{for(std::size_t o=free_.size();o>0;--o)if(!free_[o-1].empty())return std::size_t{1}<<(o-1);return 0;}''',
  r'''int main(){BuddyPool p(16);auto a=p.allocate(3);auto b=p.allocate(3);CHECK(a==Block{0,4});CHECK(b==Block{4,4});CHECK(p.release(*a));CHECK(p.release(*b));CHECK(p.largest_free()==16);return failures;}''',
  r'''int main(){try{BuddyPool p(12);CHECK(false);}catch(const std::invalid_argument&){}BuddyPool p(8);CHECK(!p.allocate(0));auto a=p.allocate(5);CHECK(a==Block{0,8});CHECK(!p.allocate(1));CHECK(!p.release({0,4}));CHECK(p.release(*a));CHECK(!p.release(*a));CHECK(p.largest_free()==8);return failures;}''',
  "std::size_t buddy=at^(std::size_t{1}<<o);","std::size_t buddy=at+(std::size_t{1}<<o);","addition-only neighbor selection misses a lower XOR buddy"),
 C(
  "capacity-run-bitmap","Aligned Run Bitmap","Claim aligned clear runs across bitmap word boundaries.",
  "claim finds the lowest aligned run of clear slots and marks it atomically. free succeeds only when every slot in the exact range is occupied.",
  "occupancy bitmap plus per-word free-count summaries and cross-word run search",
  "Capacity is positive. Run is positive and no larger than capacity. Alignment is a nonzero power of two. Invalid free ranges or any clear member return false unchanged.",
  "The bit vector and word summaries agree after every mutation; returned runs are aligned and entirely clear before claim.","a scanner that restarts at every 64-bit word",
  r'''class RunBitmap{public:explicit RunBitmap(std::size_t);std::optional<std::size_t> claim(std::size_t,std::size_t);bool free(std::size_t,std::size_t);std::vector<std::pair<std::size_t,std::size_t>> free_runs()const;private:std::size_t cap_;std::vector<bool> used_;std::vector<std::size_t> free_count_;void refresh(std::size_t);};''',
  r'''RunBitmap::RunBitmap(std::size_t):cap_(0){throw std::logic_error("not implemented");}std::optional<std::size_t> RunBitmap::claim(std::size_t,std::size_t){throw std::logic_error("not implemented");}bool RunBitmap::free(std::size_t,std::size_t){throw std::logic_error("not implemented");}std::vector<std::pair<std::size_t,std::size_t>> RunBitmap::free_runs()const{throw std::logic_error("not implemented");}void RunBitmap::refresh(std::size_t){}''',
  r'''RunBitmap::RunBitmap(std::size_t n):cap_(n),used_(n,false),free_count_((n+63)/64){if(!n)throw std::invalid_argument("capacity");for(std::size_t w=0;w<free_count_.size();++w)refresh(w);}void RunBitmap::refresh(std::size_t w){std::size_t begin=w*64,end=std::min(cap_,begin+64),count=0;for(std::size_t i=begin;i<end;++i)if(!used_[i])++count;free_count_[w]=count;}std::optional<std::size_t> RunBitmap::claim(std::size_t run,std::size_t alignment){if(!run||run>cap_||!alignment||(alignment&(alignment-1)))return std::nullopt;for(std::size_t start=0;start+run<=cap_;start+=alignment){bool clear=true;for(std::size_t i=start;i<start+run;++i)if(used_[i]){clear=false;break;}if(clear){for(std::size_t i=start;i<start+run;++i)used_[i]=true;for(std::size_t w=start/64;w<=(start+run-1)/64;++w)refresh(w);return start;}}return std::nullopt;}bool RunBitmap::free(std::size_t start,std::size_t run){if(!run||start>cap_||run>cap_-start)return false;for(std::size_t i=start;i<start+run;++i)if(!used_[i])return false;for(std::size_t i=start;i<start+run;++i)used_[i]=false;for(std::size_t w=start/64;w<=(start+run-1)/64;++w)refresh(w);return true;}std::vector<std::pair<std::size_t,std::size_t>> RunBitmap::free_runs()const{std::vector<std::pair<std::size_t,std::size_t>> out;for(std::size_t i=0;i<cap_;){if(used_[i]){++i;continue;}std::size_t b=i;while(i<cap_&&!used_[i])++i;out.push_back({b,i-b});}return out;}''',
  r'''int main(){RunBitmap b(70);CHECK(b.claim(62,1)==0);CHECK(b.claim(5,1)==62);CHECK(b.free(60,7));CHECK(b.claim(7,1)==60);return failures;}''',
  r'''int main(){try{RunBitmap b(0);CHECK(false);}catch(const std::invalid_argument&){}RunBitmap b(10);CHECK(!b.claim(2,3));CHECK(b.claim(3,4)==0);CHECK(!b.free(1,3));CHECK(b.free(0,3));CHECK(b.free_runs()==std::vector<std::pair<std::size_t,std::size_t>>{{0,10}});return failures;}''',
  "for(std::size_t start=0;start+run<=cap_;start+=alignment)","for(std::size_t start=0;start+run<=std::min(cap_,std::size_t{64});start+=alignment)","word-local scan rejects a valid cross-word run"),
 C(
  "capacity-size-class-arena","Segregated Size-Class Arena","Allocate from independent intrusive size-class chains.",
  "Classes are strictly increasing powers of two. The byte budget is divided round-robin into class blocks. acquire chooses the smallest fitting class and lowest free block; release validates class, slot, and generation.",
  "segregated fixed-block classes with per-class free chains and generational handles",
  "Empty/duplicate/non-power-of-two classes and insufficient bytes throw. Zero or oversize requests return empty. Stale or duplicate release is false.",
  "A handle names exactly one occupied block in one class; each free chain contains only its class and is kept in lowest-slot order.","one global block list that ignores requested size classes",
  r'''struct ClassHandle{std::size_t class_index;std::size_t slot;std::uint64_t generation;};class SizeClassArena{public:SizeClassArena(std::vector<std::size_t>,std::size_t);std::optional<ClassHandle> acquire(std::size_t);bool release(ClassHandle);std::vector<std::size_t> free_per_class()const;private:std::vector<std::size_t> classes_;std::vector<std::set<std::size_t>> free_;std::vector<std::vector<std::uint64_t>> generation_;std::vector<std::vector<bool>> live_;};''',
  r'''SizeClassArena::SizeClassArena(std::vector<std::size_t>,std::size_t){throw std::logic_error("not implemented");}std::optional<ClassHandle> SizeClassArena::acquire(std::size_t){throw std::logic_error("not implemented");}bool SizeClassArena::release(ClassHandle){throw std::logic_error("not implemented");}std::vector<std::size_t> SizeClassArena::free_per_class()const{throw std::logic_error("not implemented");}''',
  r'''SizeClassArena::SizeClassArena(std::vector<std::size_t> c,std::size_t bytes):classes_(std::move(c)){if(classes_.empty())throw std::invalid_argument("classes");std::size_t previous=0,used=0;for(std::size_t value:classes_){if(!value||(value&(value-1))||value<=previous)throw std::invalid_argument("classes");previous=value;}free_.resize(classes_.size());generation_.resize(classes_.size());live_.resize(classes_.size());std::size_t cursor=0;while(true){std::size_t k=cursor%classes_.size();if(used+classes_[k]>bytes)break;std::size_t slot=generation_[k].size();generation_[k].push_back(1);live_[k].push_back(false);free_[k].insert(slot);used+=classes_[k];++cursor;}for(const auto& row:free_)if(row.empty())throw std::invalid_argument("bytes");}std::optional<ClassHandle> SizeClassArena::acquire(std::size_t n){if(!n)return std::nullopt;std::size_t k=0;while(k<classes_.size()&&classes_[k]<n)++k;if(k==classes_.size()||free_[k].empty())return std::nullopt;std::size_t slot=*free_[k].begin();free_[k].erase(free_[k].begin());live_[k][slot]=true;return ClassHandle{k,slot,generation_[k][slot]};}bool SizeClassArena::release(ClassHandle h){if(h.class_index>=classes_.size()||h.slot>=live_[h.class_index].size()||!live_[h.class_index][h.slot]||generation_[h.class_index][h.slot]!=h.generation)return false;live_[h.class_index][h.slot]=false;++generation_[h.class_index][h.slot];free_[h.class_index].insert(h.slot);return true;}std::vector<std::size_t> SizeClassArena::free_per_class()const{std::vector<std::size_t> out;for(const auto& row:free_)out.push_back(row.size());return out;}''',
  r'''int main(){SizeClassArena a({2,4},12);auto x=a.acquire(2);auto y=a.acquire(3);CHECK(x&&x->class_index==0);CHECK(y&&y->class_index==1);CHECK(a.release(*x));return failures;}''',
  r'''int main(){try{SizeClassArena a({2,2},8);CHECK(false);}catch(const std::invalid_argument&){}SizeClassArena a({1,4},10);auto h=a.acquire(1);CHECK(h);CHECK(a.release(*h));CHECK(!a.release(*h));CHECK(!a.acquire(5));return failures;}''',
  "while(k<classes_.size()&&classes_[k]<n)++k;","k=0;","global-list allocation ignores the smallest fitting class"),
 C(
  "capacity-generation-slab","Generational Slab","Reject stale handles after deterministic slot reuse.",
  "emplace uses the lowest free slot, get requires matching generation, and erase increments generation before returning the slot to the free set.",
  "fixed slab slots with occupancy bits, generation counters, and ordered free indices",
  "Zero capacity throws. Full emplace is empty. Invalid or stale handles are absent/false. live_values are in slot order.",
  "Every slot is exactly live or free and a successful erase changes its generation before reuse.","index-only handles without generation validation",
  r'''struct SlabHandle{std::size_t index;std::uint64_t generation;};class GenerationSlab{public:explicit GenerationSlab(std::size_t);std::optional<SlabHandle> emplace(int);std::optional<int> get(SlabHandle)const;bool erase(SlabHandle);std::vector<int> live_values()const;private:std::vector<int> values_;std::vector<std::uint64_t> generation_;std::vector<bool> live_;std::set<std::size_t> free_;};''',
  r'''GenerationSlab::GenerationSlab(std::size_t){throw std::logic_error("not implemented");}std::optional<SlabHandle> GenerationSlab::emplace(int){throw std::logic_error("not implemented");}std::optional<int> GenerationSlab::get(SlabHandle)const{throw std::logic_error("not implemented");}bool GenerationSlab::erase(SlabHandle){throw std::logic_error("not implemented");}std::vector<int> GenerationSlab::live_values()const{throw std::logic_error("not implemented");}''',
  r'''GenerationSlab::GenerationSlab(std::size_t n):values_(n),generation_(n,1),live_(n,false){if(!n)throw std::invalid_argument("capacity");for(std::size_t i=0;i<n;++i)free_.insert(i);}std::optional<SlabHandle> GenerationSlab::emplace(int value){if(free_.empty())return std::nullopt;std::size_t i=*free_.begin();free_.erase(free_.begin());values_[i]=value;live_[i]=true;return SlabHandle{i,generation_[i]};}std::optional<int> GenerationSlab::get(SlabHandle h)const{if(h.index>=live_.size()||!live_[h.index]||generation_[h.index]!=h.generation)return std::nullopt;return values_[h.index];}bool GenerationSlab::erase(SlabHandle h){if(!get(h))return false;live_[h.index]=false;++generation_[h.index];free_.insert(h.index);return true;}std::vector<int> GenerationSlab::live_values()const{std::vector<int> out;for(std::size_t i=0;i<live_.size();++i)if(live_[i])out.push_back(values_[i]);return out;}''',
  r'''int main(){GenerationSlab s(2);auto a=s.emplace(4);auto b=s.emplace(7);CHECK(a&&b);CHECK(s.erase(*a));auto c=s.emplace(9);CHECK(c&&c->index==a->index);CHECK(!s.get(*a));CHECK(s.get(*c)==9);return failures;}''',
  r'''int main(){try{GenerationSlab s(0);CHECK(false);}catch(const std::invalid_argument&){}GenerationSlab s(1);auto h=s.emplace(3);CHECK(h);CHECK(!s.emplace(4));CHECK(s.erase(*h));CHECK(!s.erase(*h));CHECK(s.live_values().empty());return failures;}''',
  "generation_[h.index]!=h.generation","false","index-only lookup accepts a stale generation"),
 C(
  "capacity-checkpoint-arena","Checkpoint Bump Arena","Rewind a bounded monotone byte arena to valid prefix checkpoints.",
  "append copies bytes at the cursor and returns the prior offset. checkpoint records the cursor. rewind accepts a recorded cursor and removes it and every later checkpoint.",
  "monotone byte cursor with an ordered checkpoint stack and prefix rewind",
  "Zero capacity throws. Empty append succeeds. Overflow returns empty unchanged. Unknown or future rewind is false.",
  "Bytes before the cursor equal the append prefix and checkpoints are nondecreasing valid cursor positions.","independent object frees that do not restore an exact prefix",
  r'''class CheckpointArena{public:explicit CheckpointArena(std::size_t);std::optional<std::size_t> append(std::vector<std::uint8_t>);std::size_t checkpoint();bool rewind(std::size_t);std::vector<std::uint8_t> bytes()const;private:std::vector<std::uint8_t> data_;std::size_t cursor_=0;std::vector<std::size_t> marks_;};''',
  r'''CheckpointArena::CheckpointArena(std::size_t){throw std::logic_error("not implemented");}std::optional<std::size_t> CheckpointArena::append(std::vector<std::uint8_t>){throw std::logic_error("not implemented");}std::size_t CheckpointArena::checkpoint(){throw std::logic_error("not implemented");}bool CheckpointArena::rewind(std::size_t){throw std::logic_error("not implemented");}std::vector<std::uint8_t> CheckpointArena::bytes()const{throw std::logic_error("not implemented");}''',
  r'''CheckpointArena::CheckpointArena(std::size_t n):data_(n){if(!n)throw std::invalid_argument("capacity");}std::optional<std::size_t> CheckpointArena::append(std::vector<std::uint8_t> bytes){if(bytes.size()>data_.size()-cursor_)return std::nullopt;std::size_t at=cursor_;std::copy(bytes.begin(),bytes.end(),data_.begin()+static_cast<std::ptrdiff_t>(cursor_));cursor_+=bytes.size();return at;}std::size_t CheckpointArena::checkpoint(){marks_.push_back(cursor_);return cursor_;}bool CheckpointArena::rewind(std::size_t mark){auto it=std::find(marks_.begin(),marks_.end(),mark);if(it==marks_.end()||mark>cursor_)return false;cursor_=mark;marks_.erase(it,marks_.end());return true;}std::vector<std::uint8_t> CheckpointArena::bytes()const{return {data_.begin(),data_.begin()+static_cast<std::ptrdiff_t>(cursor_)};}''',
  r'''int main(){CheckpointArena a(8);CHECK(a.append({1,2})==0);auto m=a.checkpoint();CHECK(a.append({3,4,5})==2);auto later=a.checkpoint();CHECK(a.rewind(m));CHECK(a.bytes()==std::vector<std::uint8_t>({1,2}));CHECK(a.append({7,8,9})==2);CHECK(!a.rewind(later));return failures;}''',
  r'''int main(){try{CheckpointArena a(0);CHECK(false);}catch(const std::invalid_argument&){}CheckpointArena a(3);CHECK(a.append({}).value()==0);auto m=a.checkpoint();CHECK(!a.append({1,2,3,4}));CHECK(!a.rewind(2));CHECK(a.rewind(m));CHECK(!a.rewind(m));return failures;}''',
  "marks_.erase(it,marks_.end());","marks_.erase(it);","rewind retains later checkpoints that refer beyond the restored cursor"),
)

def _class_name(task_id:str)->str:
    return "".join(part.capitalize() for part in task_id.split("-"))

def _allocator_case(task_id:str,title:str,summary:str,mechanism:str,
                    prelude:str,select_expr:str,visible_offset:int,hidden_offset:int)->Case:
    cls=_class_name(task_id)
    header=f'''struct {cls}Handle{{std::size_t offset;std::size_t size;int tag;}};class {cls}{{public:explicit {cls}(std::size_t);std::optional<{cls}Handle> reserve(std::size_t,int);bool release(std::size_t);std::vector<{cls}Handle> layout()const;private:std::size_t cap_;std::vector<{cls}Handle> live_;}};'''
    starter=f'''{cls}::{cls}(std::size_t):cap_(0){{throw std::logic_error("not implemented");}}std::optional<{cls}Handle> {cls}::reserve(std::size_t,int){{throw std::logic_error("not implemented");}}bool {cls}::release(std::size_t){{throw std::logic_error("not implemented");}}std::vector<{cls}Handle> {cls}::layout()const{{throw std::logic_error("not implemented");}}'''
    reference=f'''{cls}::{cls}(std::size_t n):cap_(n){{if(!n)throw std::invalid_argument("capacity");}}std::optional<{cls}Handle> {cls}::reserve(std::size_t size,int tag){{if(!size||size>cap_)return std::nullopt;{prelude}std::vector<std::pair<std::size_t,std::size_t>> gaps;std::size_t cursor=0;auto ordered=live_;std::sort(ordered.begin(),ordered.end(),[](const auto&a,const auto&b){{return a.offset<b.offset;}});for(const auto& h:ordered){{if(cursor<h.offset)gaps.push_back({{cursor,h.offset-cursor}});cursor=h.offset+h.size;}}if(cursor<cap_)gaps.push_back({{cursor,cap_-cursor}});std::optional<std::size_t> choice;{select_expr}if(!choice)return std::nullopt;live_.push_back({{*choice,size,tag}});return live_.back();}}bool {cls}::release(std::size_t offset){{auto it=std::find_if(live_.begin(),live_.end(),[&](const auto& h){{return h.offset==offset;}});if(it==live_.end())return false;live_.erase(it);return true;}}std::vector<{cls}Handle> {cls}::layout()const{{auto out=live_;std::sort(out.begin(),out.end(),[](const auto&a,const auto&b){{return a.offset<b.offset;}});return out;}}'''
    visible=f'''int main(){{{cls} a(12);auto x=a.reserve(3,1);auto y=a.reserve(3,2);CHECK(x&&y);CHECK(a.release(x->offset));auto z=a.reserve(2,-1);CHECK(z&&z->offset=={visible_offset});return failures;}}'''
    hidden=f'''int main(){{try{{{cls} a(0);CHECK(false);}}catch(const std::invalid_argument&){{}}{cls} a(9);CHECK(!a.reserve(0,1));auto x=a.reserve(2,4);auto y=a.reserve(2,5);CHECK(x&&y);CHECK(a.release(x->offset));auto z=a.reserve(1,4);CHECK(z&&z->offset=={hidden_offset});CHECK(!a.release(99));return failures;}}'''
    return Case(task_id,title,summary,"reserve computes current holes, applies the case placement rule atomically, and returns an exact live extent; release accepts only a live starting offset.",mechanism,
      "Zero capacity throws; zero/oversize/no-fit reserve is absent; missing release is false unchanged.",
      "Live extents are disjoint, in bounds, and their occupied bytes plus gaps exactly partition capacity.","a growing heap or first-fit interval list",header,starter,reference,visible,hidden,
      select_expr,"for(auto it=gaps.rbegin();it!=gaps.rend();++it)if(it->second>=size){choice=it->first+it->second-size;break;}",f"opposite-end placement violates {mechanism}")

def _policy_case(task_id:str,title:str,summary:str,mechanism:str,policy:str,
                 victim_expr:str,visible_victim:int,hidden_victim:int)->Case:
    """Build a bounded keyed store whose case-owned victim rule is explicit."""
    cls=_class_name(task_id)
    header=f'''class {cls}{{public:explicit {cls}(std::size_t);bool put(int,int,int);std::optional<int> get(int)const;bool erase(int);std::vector<int> keys()const;private:struct Node{{int key;int value;int weight;std::size_t age;bool referenced;}};std::size_t cap_;std::size_t clock_=0;std::vector<Node> nodes_;}};'''
    starter=f'''{cls}::{cls}(std::size_t):cap_(0){{throw std::logic_error("not implemented");}}bool {cls}::put(int,int,int){{throw std::logic_error("not implemented");}}std::optional<int> {cls}::get(int)const{{throw std::logic_error("not implemented");}}bool {cls}::erase(int){{throw std::logic_error("not implemented");}}std::vector<int> {cls}::keys()const{{throw std::logic_error("not implemented");}}'''
    reference=f'''{cls}::{cls}(std::size_t n):cap_(n){{if(!n)throw std::invalid_argument("capacity");}}bool {cls}::put(int key,int value,int weight){{if(weight<0)return false;for(auto& n:nodes_)if(n.key==key){{n.value=value;n.weight=weight;n.age=++clock_;n.referenced=true;return true;}}if(nodes_.size()==cap_){{std::size_t victim=0;{victim_expr}nodes_.erase(nodes_.begin()+static_cast<std::ptrdiff_t>(victim));}}nodes_.push_back({{key,value,weight,++clock_,false}});return true;}}std::optional<int> {cls}::get(int key)const{{for(const auto& n:nodes_)if(n.key==key)return n.value;return std::nullopt;}}bool {cls}::erase(int key){{auto it=std::find_if(nodes_.begin(),nodes_.end(),[&](const Node& n){{return n.key==key;}});if(it==nodes_.end())return false;nodes_.erase(it);return true;}}std::vector<int> {cls}::keys()const{{std::vector<int> out;for(const auto& n:nodes_)out.push_back(n.key);std::sort(out.begin(),out.end());return out;}}'''
    prefix=f'''int main(){{{cls} s(3);CHECK(s.put(1,10,5));CHECK(s.put(2,20,1));CHECK(s.put(3,30,3));CHECK(s.put(4,40,2));'''
    visible=prefix+f'''CHECK(!s.get({visible_victim}));CHECK(s.get(4)==40);return failures;}}'''
    hidden=f'''int main(){{try{{{cls} z(0);CHECK(false);}}catch(const std::invalid_argument&){{}}{cls} s(2);CHECK(!s.put(9,9,-1));CHECK(s.put(1,1,7));CHECK(s.put(2,2,2));CHECK(s.put(3,3,4));CHECK(!s.get({hidden_victim}));CHECK(!s.erase(99));return failures;}}'''
    return Case(task_id,title,summary,
      f"put updates an existing key without eviction. At capacity, {policy}. Negative weights are rejected unchanged; keys are reported sorted.",
      mechanism,"Zero capacity throws; negative weight and missing erase are false without mutation.",
      f"At most cap entries exist and the full-store mutation computes exactly one victim by {policy}.",
      "FIFO or unordered-map overwrite as a substitute",header,starter,reference,visible,hidden,
      victim_expr,"victim=nodes_.size()-1;",f"last-slot eviction violates {policy}")

def _ring_case(task_id:str,title:str,summary:str,mechanism:str,transform:str,
               visible_value:int,hidden_value:int)->Case:
    cls=_class_name(task_id)
    header=f'''class {cls}{{public:explicit {cls}(std::size_t);bool append(std::vector<int>);std::optional<std::vector<int>> pop();std::vector<int> image()const;private:std::size_t cap_;std::size_t used_=0;std::deque<std::vector<int>> records_;}};'''
    starter=f'''{cls}::{cls}(std::size_t):cap_(0){{throw std::logic_error("not implemented");}}bool {cls}::append(std::vector<int>){{throw std::logic_error("not implemented");}}std::optional<std::vector<int>> {cls}::pop(){{throw std::logic_error("not implemented");}}std::vector<int> {cls}::image()const{{throw std::logic_error("not implemented");}}'''
    reference=f'''{cls}::{cls}(std::size_t n):cap_(n){{if(!n)throw std::invalid_argument("capacity");}}bool {cls}::append(std::vector<int> input){{{transform}if(input.size()>cap_-used_)return false;used_+=input.size();records_.push_back(std::move(input));return true;}}std::optional<std::vector<int>> {cls}::pop(){{if(records_.empty())return std::nullopt;auto out=records_.front();records_.pop_front();used_-=out.size();return out;}}std::vector<int> {cls}::image()const{{std::vector<int> out;for(const auto& row:records_)out.insert(out.end(),row.begin(),row.end());return out;}}'''
    visible=f'''int main(){{{cls} r(12);CHECK(r.append({{{{1,2,3}}}}));CHECK(r.append({{{{4,5}}}}));auto v=r.image();CHECK(!v.empty());CHECK(v.front()=={visible_value});return failures;}}'''
    hidden=f'''int main(){{try{{{cls} r(0);CHECK(false);}}catch(const std::invalid_argument&){{}}{cls} r(6);CHECK(r.append({{{{2,2,3}}}}));auto p=r.pop();CHECK(p&&p->front()=={hidden_value});CHECK(!r.pop());return failures;}}'''
    return Case(task_id,title,summary,"append applies the specified record encoding before one atomic capacity check; pop removes exactly the oldest encoded record.",mechanism,
      "Zero capacity throws; an encoded record that cannot fit is rejected without dropping older records; empty pop is absent.",
      "used equals the sum of encoded record lengths and never exceeds capacity.","an unframed modulo array that loses record boundaries",header,starter,reference,visible,hidden,
      transform,"/* encoding skipped */",f"skipping the {mechanism} transform accepts the wrong stored image")

def _index_case(task_id:str,title:str,summary:str,mechanism:str,start_expr:str,step_expr:str,collision_slot:int)->Case:
    cls=_class_name(task_id)
    header=f'''class {cls}{{public:explicit {cls}(std::size_t);bool insert(int,int);std::optional<int> find(int)const;bool erase(int);std::vector<int> occupied_slots()const;private:struct Cell{{int key=0;int value=0;bool live=false;bool tombstone=false;}};std::vector<Cell> cells_;}};'''
    starter=f'''{cls}::{cls}(std::size_t){{throw std::logic_error("not implemented");}}bool {cls}::insert(int,int){{throw std::logic_error("not implemented");}}std::optional<int> {cls}::find(int)const{{throw std::logic_error("not implemented");}}bool {cls}::erase(int){{throw std::logic_error("not implemented");}}std::vector<int> {cls}::occupied_slots()const{{throw std::logic_error("not implemented");}}'''
    reference=f'''{cls}::{cls}(std::size_t n):cells_(n){{if(n<3)throw std::invalid_argument("capacity");}}bool {cls}::insert(int key,int value){{std::size_t start={start_expr};std::optional<std::size_t> hole;for(std::size_t probe=0;probe<cells_.size();++probe){{std::size_t i={step_expr};if(cells_[i].live&&cells_[i].key==key){{cells_[i].value=value;return true;}}if(!cells_[i].live&&!hole)hole=i;if(!cells_[i].live&&!cells_[i].tombstone)break;}}if(!hole)return false;cells_[*hole]={{key,value,true,false}};return true;}}std::optional<int> {cls}::find(int key)const{{std::size_t start={start_expr};for(std::size_t probe=0;probe<cells_.size();++probe){{std::size_t i={step_expr};if(cells_[i].live&&cells_[i].key==key)return cells_[i].value;if(!cells_[i].live&&!cells_[i].tombstone)return std::nullopt;}}return std::nullopt;}}bool {cls}::erase(int key){{std::size_t start={start_expr};for(std::size_t probe=0;probe<cells_.size();++probe){{std::size_t i={step_expr};if(cells_[i].live&&cells_[i].key==key){{cells_[i].live=false;cells_[i].tombstone=true;return true;}}if(!cells_[i].live&&!cells_[i].tombstone)return false;}}return false;}}std::vector<int> {cls}::occupied_slots()const{{std::vector<int> out;for(std::size_t i=0;i<cells_.size();++i)if(cells_[i].live)out.push_back(static_cast<int>(i));return out;}}'''
    visible=f'''int main(){{{cls} m(7);CHECK(m.insert(1,10));CHECK(m.insert(8,80));auto slots=m.occupied_slots();CHECK(std::find(slots.begin(),slots.end(),{collision_slot})!=slots.end());CHECK(m.find(8)==80);CHECK(m.erase(1));CHECK(m.find(8)==80);return failures;}}'''
    hidden=f'''int main(){{try{{{cls} m(2);CHECK(false);}}catch(const std::invalid_argument&){{}}{cls} m(7);CHECK(m.insert(-3,4));CHECK(m.insert(4,5));CHECK(m.erase(-3));CHECK(!m.erase(99));CHECK(m.find(4)==5);return failures;}}'''
    return Case(task_id,title,summary,"insert follows the case-owned bounded probe sequence, reuses the first tombstone, and stops only at a never-used cell.",mechanism,
      "Capacity below three throws; full insert is false; lookup/erase of absent keys leave cells unchanged.",
      "Every lookup repeats the exact insertion probe sequence and tombstones preserve reachability.","std::unordered_map or a linear scan over live values",header,starter,reference,visible,hidden,
      step_expr,"(start+probe)%cells_.size()",f"linear probing breaks the {mechanism} collision route")

def _history_case(task_id:str,title:str,summary:str,mechanism:str,trim_expr:str)->Case:
    cls=_class_name(task_id)
    header=f'''class {cls}{{public:explicit {cls}(std::size_t);std::size_t commit(int);bool rollback(std::size_t);std::vector<int> values()const;private:std::size_t cap_;std::size_t next_=1;std::deque<std::pair<std::size_t,int>> log_;}};'''
    starter=f'''{cls}::{cls}(std::size_t):cap_(0){{throw std::logic_error("not implemented");}}std::size_t {cls}::commit(int){{throw std::logic_error("not implemented");}}bool {cls}::rollback(std::size_t){{throw std::logic_error("not implemented");}}std::vector<int> {cls}::values()const{{throw std::logic_error("not implemented");}}'''
    reference=f'''{cls}::{cls}(std::size_t n):cap_(n){{if(!n)throw std::invalid_argument("capacity");}}std::size_t {cls}::commit(int value){{std::size_t id=next_++;log_.push_back({{id,value}});{trim_expr}return id;}}bool {cls}::rollback(std::size_t id){{auto it=std::find_if(log_.begin(),log_.end(),[&](const auto& p){{return p.first==id;}});if(it==log_.end())return false;log_.erase(it+1,log_.end());return true;}}std::vector<int> {cls}::values()const{{std::vector<int> out;for(const auto& p:log_)out.push_back(p.second);return out;}}'''
    visible=f'''int main(){{{cls} h(3);auto a=h.commit(1);auto b=h.commit(2);h.commit(3);CHECK(h.rollback(b));CHECK(h.values()==std::vector<int>({{{{1,2}}}}));CHECK(a==1);return failures;}}'''
    hidden=f'''int main(){{try{{{cls} h(0);CHECK(false);}}catch(const std::invalid_argument&){{}}{cls} h(2);h.commit(4);auto b=h.commit(5);h.commit(6);CHECK(!h.rollback(1));CHECK(h.rollback(b));return failures;}}'''
    return Case(task_id,title,summary,"commit creates a monotonic identity and applies the case retention rule; rollback accepts only a retained identity and erases its suffix.",mechanism,
      "Zero capacity throws; rollback of an evicted/future identity is false unchanged.","Retained identities are increasing and the log never exceeds its configured bound.",
      "an unbounded vector or rollback by value",header,starter,reference,visible,hidden,trim_expr,"if(false){}",f"disabling {mechanism} violates bounded retention")

def _partition_case(task_id:str,title:str,summary:str,mechanism:str,lane_expr:str,visible_lane:int,hidden_lane:int)->Case:
    cls=_class_name(task_id)
    header=f'''class {cls}{{public:{cls}(std::size_t,std::size_t);std::optional<std::size_t> place(int,std::size_t);bool release(int);std::vector<std::size_t> usage()const;private:struct Entry{{int key;std::size_t lane;std::size_t units;}};std::size_t lanes_;std::size_t cap_;std::vector<std::size_t> used_;std::vector<Entry> entries_;}};'''
    starter=f'''{cls}::{cls}(std::size_t,std::size_t):lanes_(0),cap_(0){{throw std::logic_error("not implemented");}}std::optional<std::size_t> {cls}::place(int,std::size_t){{throw std::logic_error("not implemented");}}bool {cls}::release(int){{throw std::logic_error("not implemented");}}std::vector<std::size_t> {cls}::usage()const{{throw std::logic_error("not implemented");}}'''
    reference=f'''{cls}::{cls}(std::size_t lanes,std::size_t cap):lanes_(lanes),cap_(cap),used_(lanes){{if(!lanes||!cap)throw std::invalid_argument("capacity");}}std::optional<std::size_t> {cls}::place(int key,std::size_t units){{if(!units||units>cap_)return std::nullopt;for(const auto& e:entries_)if(e.key==key)return std::nullopt;std::size_t lane={lane_expr};if(used_[lane]>cap_-units)return std::nullopt;used_[lane]+=units;entries_.push_back({{key,lane,units}});return lane;}}bool {cls}::release(int key){{auto it=std::find_if(entries_.begin(),entries_.end(),[&](const Entry& e){{return e.key==key;}});if(it==entries_.end())return false;used_[it->lane]-=it->units;entries_.erase(it);return true;}}std::vector<std::size_t> {cls}::usage()const{{return used_;}}'''
    visible=f'''int main(){{{cls} p(3,5);auto a=p.place(1,2);auto b=p.place(2,2);CHECK(a=={visible_lane});CHECK(b);CHECK(p.release(1));CHECK(!p.release(1));return failures;}}'''
    hidden=f'''int main(){{try{{{cls} p(0,2);CHECK(false);}}catch(const std::invalid_argument&){{}}{cls} p(3,4);CHECK(!p.place(1,0));auto lane=p.place(-2,4);CHECK(lane=={hidden_lane});CHECK(!p.place(-2,1));return failures;}}'''
    return Case(task_id,title,summary,"place computes one deterministic lane and performs an overflow-safe per-lane capacity check before mutation.",mechanism,
      "Zero lanes/capacity throw; zero/oversize units, duplicate keys, and a full selected lane are rejected unchanged.",
      "Per-lane usage equals live entry units and never exceeds capacity.","a single global counter or random lane",header,starter,reference,visible,hidden,
      lane_expr,"std::size_t{0}",f"forcing lane zero violates {mechanism}")

_ALLOCATION=(
 _allocator_case("capacity-relocating-store","Relocating Capacity Store","Compact live extents before satisfying a bounded allocation.","stable left compaction with handle offsets updated before gap selection",
  "std::sort(live_.begin(),live_.end(),[](const auto&a,const auto&b){return a.offset<b.offset;});std::size_t packed=0;for(auto& h:live_){h.offset=packed;packed+=h.size;}",
  "for(const auto& g:gaps)if(g.second>=size){choice=g.first;break;}",3,2),
 _allocator_case("capacity-dual-front-arena","Dual-Front Arena","Allocate positive tags from the low front and negative tags from the high front.","two-ended extent placement selected by tag sign",
  "", "if(tag>=0){for(const auto& g:gaps)if(g.second>=size){choice=g.first;break;}}else{for(auto it=gaps.rbegin();it!=gaps.rend();++it)if(it->second>=size){choice=it->first+it->second-size;break;}}",10,0),
 _allocator_case("capacity-sparse-page-table","Sparse Page Table","Place tagged pages at a preferred virtual-page neighborhood without growing the table.","preferred-page search followed by circular page-distance fallback",
  "", "std::size_t preferred=(static_cast<std::size_t>(tag<0?-tag:tag)%3)*3;for(std::size_t delta=0;delta<cap_&&!choice;++delta){std::size_t at=(preferred+delta)%cap_;for(const auto& g:gaps)if(at>=g.first&&at+size<=g.first+g.second){choice=at;break;}}",3,3),
 _allocator_case("capacity-boundary-tag-heap","Boundary-Tag Heap","Choose the largest bounded hole while preserving exact coalescing boundaries.","boundary-tag worst-hole selection with deterministic low-offset tie breaking",
  "", "std::size_t best=0;for(const auto& g:gaps)if(g.second>=size&&g.second>best){best=g.second;choice=g.first;}",6,4),
 _allocator_case("capacity-quota-slot-pool","Quota Slot Pool","Confine each tag to its deterministic half-pool quota.","tag-derived quota slice with no cross-slice borrowing",
  "", "std::size_t half=cap_/2;std::size_t begin=(static_cast<std::size_t>(tag<0?-tag:tag)%2)*half;std::size_t end=begin+half;for(const auto& g:gaps){std::size_t at=std::max(g.first,begin);if(at+size<=std::min(g.first+g.second,end)){choice=at;break;}}",6,0),
)

_RINGS=(
 _ring_case("wrap-variable-record-log","Variable Record Ring","Prefix each wrapped record with its encoded length.","length-prefixed variable-record framing","input.insert(input.begin(),static_cast<int>(input.size()));",3,3),
 _ring_case("wrap-checksummed-frame-ring","Checksummed Frame Ring","Store an additive checksum before each frame.","per-frame checksum prefix validated as part of bounded framing","int sum=0;for(int x:input)sum+=x;input.insert(input.begin(),sum);",6,7),
 _ring_case("wrap-split-packet-store","Split Packet Store","Rotate a packet at its first fragment boundary before storage.","two-fragment wrap layout with tail fragment stored first","if(input.size()>1)std::rotate(input.begin(),input.begin()+1,input.end());",2,2),
 _ring_case("wrap-generation-snapshot-store","Generation Snapshot Store","Prefix snapshots with a deterministic generation-sized marker.","generation marker coupled to snapshot payload length","input.insert(input.begin(),static_cast<int>(input.size()+10));",13,13),
 _ring_case("wrap-delta-sample-store","Delta Sample Store","Replace the leading sample with the endpoint delta.","endpoint delta header plus original bounded sample payload","if(input.size()>1)input.front()=input.back()-input.front();",2,1),
 _ring_case("wrap-rle-event-store","RLE Event Store","Encode equal event runs as offset run lengths and values.","run-length event compaction with explicit run boundaries","std::vector<int> out;for(std::size_t i=0;i<input.size();){std::size_t j=i+1;while(j<input.size()&&input[j]==input[i])++j;out.push_back(static_cast<int>(j-i+100));out.push_back(input[i]);i=j;}input=std::move(out);",101,102),
 _ring_case("wrap-bitpacked-symbol-store","Bitpacked Symbol Store","Pack the first two four-bit symbols into one bounded word.","nibble packing with payload compaction","if(input.size()>1){input[0]=(input[0]<<4)|input[1];input.erase(input.begin()+1);}",18,34),
 _ring_case("wrap-strided-row-store","Strided Row Store","Store odd columns before even columns to represent a fixed stride.","odd-even strided row permutation","std::vector<int> out;for(std::size_t i=1;i<input.size();i+=2)out.push_back(input[i]);for(std::size_t i=0;i<input.size();i+=2)out.push_back(input[i]);input=std::move(out);",2,2),
 _ring_case("wrap-toroidal-tile-store","Toroidal Tile Store","Rotate each row right across its toroidal seam.","right-seam toroidal row rotation","if(input.size()>1)std::rotate(input.begin(),input.end()-1,input.end());",3,3),
 _ring_case("wrap-sequence-log-index","Sequence Log Index","Prefix each record with a deterministic local sequence locator.","record-local sequence locator derived from width and first symbol","input.insert(input.begin(),static_cast<int>(input.size()*10+input.front()));",31,32),
)

_EVICTION=(
 _policy_case("clock-second-chance-store","Clock Second-Chance Store","Replace the first unreferenced resident.","second-chance reference-bit victim selection","the first unreferenced resident is selected","for(std::size_t i=0;i<nodes_.size();++i)if(!nodes_[i].referenced){victim=i;break;}",1,1),
 _policy_case("probation-protected-store","Probation/Protected Store","Evict the resident with the smallest protection weight.","two-segment protection approximated by minimum promotion weight","the minimum weight wins, then the oldest index","for(std::size_t i=1;i<nodes_.size();++i)if(nodes_[i].weight<nodes_[victim].weight)victim=i;",2,2),
 _policy_case("decaying-frequency-store","Decaying Frequency Store","Evict by a deterministic decayed-frequency score.","age-penalized weighted frequency score","the minimum of twice weight plus age wins","for(std::size_t i=1;i<nodes_.size();++i)if(2*nodes_[i].weight+static_cast<int>(nodes_[i].age)<2*nodes_[victim].weight+static_cast<int>(nodes_[victim].age))victim=i;",2,2),
 _policy_case("cost-aware-eviction-store","Cost-Aware Eviction Store","Evict the highest replacement-cost entry under the configured inverse-cost rule.","inverse-cost victim ranking with stable ties","the maximum weight wins, then the oldest index","for(std::size_t i=1;i<nodes_.size();++i)if(nodes_[i].weight>nodes_[victim].weight)victim=i;",1,1),
 _policy_case("pin-aware-cache-store","Pin-Aware Cache Store","Choose the first even-key unpinned resident before fallback.","pin-class filtering followed by stable resident order","the first even key wins when present","for(std::size_t i=0;i<nodes_.size();++i)if(nodes_[i].key%2==0){victim=i;break;}",2,2),
 _policy_case("dependency-closed-store","Dependency-Closed Store","Evict the resident closest to dependency anchor two.","dependency-anchor distance ranking","minimum absolute key distance from anchor two wins","for(std::size_t i=1;i<nodes_.size();++i)if(std::abs(nodes_[i].key-2)<std::abs(nodes_[victim].key-2))victim=i;",2,2),
 _policy_case("dirty-writeback-store","Dirty Writeback Store","Prefer the largest odd-key writeback cost.","dirty-class filter plus descending writeback weight","the largest odd-key weight wins","for(std::size_t i=1;i<nodes_.size();++i)if(nodes_[i].key%2!=0&&nodes_[i].weight>nodes_[victim].weight)victim=i;",1,1),
 _policy_case("negative-ttl-store","Negative TTL Store","Expire the oldest insertion age first.","monotonic TTL age ordering","the smallest age wins","for(std::size_t i=1;i<nodes_.size();++i)if(nodes_[i].age<nodes_[victim].age)victim=i;",1,1),
 _policy_case("sketch-admission-store","Sketch Admission Store","Use maximum key-weight distance as a deterministic sketch proxy.","bounded admission-sketch distance ranking","maximum absolute key-weight distance wins","for(std::size_t i=1;i<nodes_.size();++i)if(std::abs(nodes_[i].key-nodes_[i].weight)>std::abs(nodes_[victim].key-nodes_[victim].weight))victim=i;",1,1),
 _policy_case("group-atomic-cache-store","Group-Atomic Cache Store","Evict from the incoming key's parity group.","group-atomic parity victim selection","the first resident matching incoming-key parity wins","for(std::size_t i=0;i<nodes_.size();++i)if((nodes_[i].key&1)==(key&1)){victim=i;break;}",2,1),
)

_INDEXES=(
 _index_case("robin-hood-slot-map","Robin-Hood Slot Map","Probe by increasing displacement quanta.","robin-hood displacement route","static_cast<std::size_t>(key<0?-key:key)%cells_.size()","(start+probe*(probe+1))%cells_.size()",3),
 _index_case("cuckoo-stash-slot-map","Cuckoo Stash Slot Map","Alternate a primary slot with triple-step stash candidates.","primary plus three-stride stash route","static_cast<std::size_t>(key<0?-key:key)%cells_.size()","(probe==0?start:(start+3*probe)%cells_.size())",4),
 _index_case("hopscotch-neighborhood-map","Hopscotch Neighborhood Map","Walk a two-wide neighborhood before farther homes.","two-wide hopscotch neighborhood route","static_cast<std::size_t>(key<0?-key:key)%cells_.size()","(start+2*probe+(probe/2))%cells_.size()",3),
 _index_case("linear-probe-multimap","Key-Stepped Probe Multimap","Use the key-derived odd stride for duplicate-key probing.","key-stepped open-address multimap route","static_cast<std::size_t>(key<0?-key:key)%cells_.size()","(start+probe*(1+static_cast<std::size_t>(key<0?-key:key)%(cells_.size()-1)))%cells_.size()",4),
 _index_case("quotient-counter-filter","Quotient Counter Filter","Probe quotient buckets in descending remainder order.","reverse quotient-bucket route","static_cast<std::size_t>(key<0?-key:key)%cells_.size()","(start+cells_.size()-probe%cells_.size())%cells_.size()",0),
 _index_case("bounded-string-interner","Bounded String Interner","Use a widened triangular probe route for intern slots.","triangular interner displacement route","static_cast<std::size_t>(key<0?-key:key)%cells_.size()","(start+3*probe*(probe+1)/2)%cells_.size()",4),
 _index_case("front-coded-key-block","Front-Coded Key Block","Route suffix collisions by two-slot prefix hops.","front-code prefix hop route","static_cast<std::size_t>(key<0?-key:key)%cells_.size()","(probe==0?start:(start+2*probe)%cells_.size())",3),
 _index_case("bounded-bidirectional-index","Bounded Bidirectional Index","Alternate collision probes below and above the home slot.","alternating bidirectional probe route","static_cast<std::size_t>(key<0?-key:key)%cells_.size()","(start+(probe%2?cells_.size()-(probe+1)/2:probe/2))%cells_.size()",0),
 _index_case("generation-sparse-set","Generation Sparse Set","Use a four-slot generation stride.","generation-strided sparse route","static_cast<std::size_t>(key<0?-key:key)%cells_.size()","(start+4*probe)%cells_.size()",5),
 _index_case("stable-tombstone-map","Stable Tombstone Map","Use a five-slot route while preserving erased collision chains.","stable tombstone five-stride route","(cells_.front().tombstone?std::size_t{0}:static_cast<std::size_t>(key<0?-key:key)%cells_.size())","(start+5*probe)%cells_.size()",6),
)
_INDEXES=_INDEXES[:-1]+(replace(_INDEXES[-1],control_old="cells_.front()",control_new="cells_.back()"),)

_HISTORY=(
 _history_case("undo-record-journal","Undo Record Journal","Retain the newest bounded undo records.","front-trimmed undo journal","while(log_.size()>cap_)log_.pop_front();"),
 _history_case("bounded-version-window","Bounded Version Window","Slide a version window after every commit.","version-window begin erasure","if(log_.size()>cap_)log_.erase(log_.begin());"),
 _history_case("snapshot-delta-chain","Snapshot Delta Chain","Collapse excess leading deltas into the retained suffix.","delta-chain prefix collapse","while(log_.size()>cap_){auto first=log_.begin();log_.erase(first);}"),
 _history_case("transaction-reservation-store","Transaction Reservation Store","Expire the oldest reservation identity at capacity.","reservation expiry queue","if(log_.size()==cap_+1)log_.pop_front();"),
 _history_case("append-commit-journal","Append Commit Journal","Advance the durable floor one record when full.","single-step durable-floor advancement","if(log_.size()>cap_){log_.erase(log_.begin(),log_.begin()+1);}"),
 _history_case("rollback-checkpoint-store","Rollback Checkpoint Store","Discard checkpoints older than the bounded rollback floor.","checkpoint-floor trimming","for(;log_.size()>cap_;)log_.pop_front();"),
 _history_case("idempotency-result-store","Idempotency Result Store","Retain only the last bounded result identities.","idempotency-result FIFO expiry","while(cap_<log_.size())log_.erase(log_.begin());"),
 _history_case("branch-history-ring","Branch History Ring","Rotate the branch head after capacity overflow.","branch-head ring expiry","if(log_.size()>cap_){auto doomed=log_.front().first;(void)doomed;log_.pop_front();}"),
 _history_case("tombstone-reclamation-store","Tombstone Reclamation Store","Reclaim exactly the oldest committed tombstone.","oldest-tombstone reclamation","if(log_.size()>cap_){auto old=log_.begin();log_.erase(old);}"),
 _history_case("dual-bank-recovery-log","Dual-Bank Recovery Log","Flip the recovery floor by dropping the prior-bank head.","dual-bank recovery-floor switch","if(log_.size()>cap_){std::deque<std::pair<std::size_t,int>> next(log_.begin()+1,log_.end());log_.swap(next);}"),
)

_PARTITIONS=(
 _partition_case("weighted-capacity-partitioner","Weighted Capacity Partitioner","Hash key and unit weight into a fixed lane.","multiplicative key-weight lane selection","(static_cast<std::size_t>(key<0?-key:key)*units)%lanes_",2,2),
 _partition_case("elastic-lane-store","Elastic Lane Store","Break least-used lane ties toward the highest lane.","least-used elastic lane with high-index tie break","static_cast<std::size_t>(std::distance(used_.begin(),std::min_element(used_.rbegin(),used_.rend()).base()-1))",2,2),
 _partition_case("rendezvous-slot-directory","Rendezvous Slot Directory","Select a deterministic rendezvous lane from key and size.","rendezvous hash lane selection","(static_cast<std::size_t>(key<0?-key:key)*5+units)%lanes_",1,2),
 _partition_case("striped-reservation-grid","Striped Reservation Grid","Offset key-size stripes by one lane.","one-offset striped reservation lane","(static_cast<std::size_t>(key<0?-key:key)+units+1)%lanes_",1,1),
 _partition_case("capacity-escrow-ledger","Capacity Escrow Ledger","Map doubled account identity plus units into escrow lanes.","escrow-account weighted lane","(static_cast<std::size_t>(key<0?-key:key)*2+units)%lanes_",1,2),
 _partition_case("hierarchical-occupancy-index","Hierarchical Occupancy Index","Use parent-key quotient and units for leaf selection.","hierarchical quotient leaf lane","(static_cast<std::size_t>(key<0?-key:key)/2+units)%lanes_",2,2),
 _partition_case("tenant-borrowing-pool","Tenant Borrowing Pool","Route tenants to the predecessor borrowing lane.","predecessor-lane tenant borrowing","(static_cast<std::size_t>(key<0?-key:key)+lanes_-1)%lanes_",0,1),
 _partition_case("watermark-retention-store","Watermark Retention Store","Weight retained units twice in lane selection.","double-unit watermark lane","(static_cast<std::size_t>(key<0?-key:key)+2*units)%lanes_",2,1),
 _partition_case("compacting-priority-shelf","Compacting Priority Shelf","Use squared priority identity plus units.","squared-priority compacting lane","(static_cast<std::size_t>(key<0?-key:key)*static_cast<std::size_t>(key<0?-key:key)+units)%lanes_",0,2),
 _partition_case("deterministic-spillway-store","Deterministic Spillway Store","Mirror key identity across the final spillway lane.","mirrored deterministic spillway lane","lanes_-1-(static_cast<std::size_t>(key<0?-key:key)%lanes_)",1,0),
)

from w8_biayn.integrations.moonlight_bounded_circular_storage_replacements import REPLACEMENTS
from w8_biayn.integrations.moonlight_bounded_circular_storage_cycle04 import apply_cycle04
from w8_biayn.integrations.moonlight_bounded_circular_storage_cycle05 import apply_cycle05

CASES=apply_cycle05(apply_cycle04(_HANDCRAFTED+REPLACEMENTS))
