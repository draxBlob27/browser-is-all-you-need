"""Independent contracts and operations for the remediated XOR-chain family."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    legacy_id: str
    task_id: str
    class_name: str
    declarations: str
    private_fields: str
    starter: str
    reference: str
    visible: str
    hidden: str
    contract: str
    logic_tag: str


CASES = (
    Case("xor-card-game-turns", "xor-card-game-turns", "CardGameTurns", """
  Handle seat(int player_id, unsigned quota, Handle after = 0);
  bool grant(Handle player, unsigned extra);
  std::optional<int> advance(unsigned steps);
  std::optional<int> consume_turn();
  bool reverse();
  std::vector<int> order() const;""", "int direction_ = 1;", """
CardGameTurns::Handle CardGameTurns::seat(int,unsigned,Handle){return 0;} bool CardGameTurns::grant(Handle,unsigned){return false;}
std::optional<int> CardGameTurns::advance(unsigned){return std::nullopt;} std::optional<int> CardGameTurns::consume_turn(){return std::nullopt;}
bool CardGameTurns::reverse(){return false;} std::vector<int> CardGameTurns::order()const{return{};}""", """
CardGameTurns::Handle CardGameTurns::seat(int id,unsigned quota,Handle after){if(id<=0||quota==0||find_id(id)||(after&&!valid(after)))return 0;SlotId x=allocate(id,static_cast<int>(quota),0);insert_after(x,after?slot_of(after):tail_);if(!current_)current_=x;return handle_of(x);}
bool CardGameTurns::grant(Handle h,unsigned extra){if(!valid(h)||extra==0||extra>static_cast<unsigned>(INT_MAX-arena_[slot_of(h)].value))return false;arena_[slot_of(h)].value+=static_cast<int>(extra);return true;}
std::optional<int> CardGameTurns::advance(unsigned steps){if(!current_)return std::nullopt;for(unsigned i=0;i<steps;++i){SlotId p=0,n=0;locate(current_,p,n);current_=direction_>0?(n?n:head_):(p?p:tail_);}return arena_[current_].id;}
std::optional<int> CardGameTurns::consume_turn(){if(!current_)return std::nullopt;SlotId x=current_,p=0,n=0;locate(x,p,n);int id=arena_[x].id;if(--arena_[x].value==0){current_=size_==1?0:(direction_>0?(n?n:head_):(p?p:tail_));unlink(x);release(x);}return id;}
bool CardGameTurns::reverse(){if(!current_)return false;direction_=-direction_;return true;} std::vector<int> CardGameTurns::order()const{return ids();}""", """
CardGameTurns g;auto a=g.seat(1,2),b=g.seat(2,1,a),c=g.seat(3,1,b);REQUIRE((a&&b&&c));REQUIRE(g.advance(2)==3);REQUIRE(g.consume_turn()==3);REQUIRE(g.order()==std::vector<int>{1,2});g.reverse();REQUIRE(g.advance(1)==2);""", """
CardGameTurns g;REQUIRE_FALSE(g.reverse());auto a=g.seat(7,1);REQUIRE(a);REQUIRE_FALSE(g.seat(7,2));REQUIRE(g.consume_turn()==7);REQUIRE_FALSE(g.grant(a,1));auto b=g.seat(8,2);REQUIRE((b&&b!=a));REQUIRE(g.grant(b,3));REQUIRE(g.advance(9)==8);""",
         "A quota-bearing circular turn ring removes exhausted players and changes traversal direction without changing physical order.", "quota-ring-direction-elimination"),
    Case("xor-chat-message-history", "xor-branching-chat-journal", "BranchingChatJournal", """
  Handle post(int message_id);
  std::optional<int> back(unsigned steps);
  std::optional<int> forward(unsigned steps);
  bool erase_current();
  std::vector<int> timeline() const;""", "", """
BranchingChatJournal::Handle BranchingChatJournal::post(int){return 0;}std::optional<int> BranchingChatJournal::back(unsigned){return std::nullopt;}
std::optional<int> BranchingChatJournal::forward(unsigned){return std::nullopt;}bool BranchingChatJournal::erase_current(){return false;}
std::vector<int> BranchingChatJournal::timeline()const{return{};}""", """
BranchingChatJournal::Handle BranchingChatJournal::post(int id){if(id<=0||find_id(id))return 0;if(current_){SlotId p=0,n=0;locate(current_,p,n);while(n){SlotId q=0,next=0;locate(n,q,next);unlink(n);release(n);n=next;}}SlotId x=allocate(id,0,0);insert_after(x,current_?current_:tail_);current_=x;return handle_of(x);}
std::optional<int> BranchingChatJournal::back(unsigned steps){SlotId x=current_;for(unsigned i=0;i<steps;++i){if(!x)return std::nullopt;SlotId p=0,n=0;locate(x,p,n);if(!p)return std::nullopt;x=p;}if(!x)return std::nullopt;current_=x;return arena_[x].id;}
std::optional<int> BranchingChatJournal::forward(unsigned steps){SlotId x=current_;for(unsigned i=0;i<steps;++i){if(!x)return std::nullopt;SlotId p=0,n=0;locate(x,p,n);if(!n)return std::nullopt;x=n;}if(!x)return std::nullopt;current_=x;return arena_[x].id;}
bool BranchingChatJournal::erase_current(){if(!current_)return false;SlotId x=current_,p=0,n=0;locate(x,p,n);current_=n?n:p;unlink(x);release(x);return true;}std::vector<int> BranchingChatJournal::timeline()const{return ids();}""", """
BranchingChatJournal j;j.post(1);j.post(2);j.post(3);REQUIRE(j.back(1)==2);j.post(4);REQUIRE(j.timeline()==std::vector<int>{1,2,4});REQUIRE_FALSE(j.forward(1));""", """
BranchingChatJournal j;REQUIRE_FALSE(j.erase_current());for(int id:{1,2,3,4})REQUIRE(j.post(id));REQUIRE(j.back(2)==2);REQUIRE_FALSE(j.back(3));REQUIRE(j.forward(1)==3);REQUIRE(j.erase_current());REQUIRE(j.timeline()==std::vector<int>{1,2,4});""",
         "Posting after backward navigation prunes the entire forward branch; failed navigation is atomic.", "cursor-branch-pruning"),
    Case("xor-delivery-stop-chain", "xor-delivery-range-ledger", "DeliveryRangeLedger", """
  Handle append(int stop_id);
  bool reverse_range(Handle first, Handle last);
  std::vector<int> detach_range(Handle first, Handle last);
  bool insert_block_after(Handle anchor, const std::vector<int>& stops);
  std::vector<int> route() const;""", "", """
DeliveryRangeLedger::Handle DeliveryRangeLedger::append(int){return 0;}bool DeliveryRangeLedger::reverse_range(Handle,Handle){return false;}
std::vector<int> DeliveryRangeLedger::detach_range(Handle,Handle){return{};}bool DeliveryRangeLedger::insert_block_after(Handle,const std::vector<int>&){return false;}
std::vector<int> DeliveryRangeLedger::route()const{return{};}""", """
DeliveryRangeLedger::Handle DeliveryRangeLedger::append(int id){if(id<=0||find_id(id))return 0;SlotId x=allocate(id,0,0);insert_after(x,tail_);return handle_of(x);}
bool DeliveryRangeLedger::reverse_range(Handle first,Handle last){if(!valid(first)||!valid(last))return false;SlotId f=slot_of(first),l=slot_of(last),p=0,n=0;locate(f,p,n);bool found=f==l;for(SlotId prev=f,c=n,next=0;c&&!found;prev=c,c=next){next=prev^arena_[c].link;if(c==l)found=true;}if(!found)return false;if(f==l)return true;SlotId before=0,after=0;locate(f,before,n);locate(l,p,after);arena_[f].link^=before^after;arena_[l].link^=after^before;if(before)arena_[before].link^=f^l;else head_=l;if(after)arena_[after].link^=l^f;else tail_=f;return true;}
std::vector<int> DeliveryRangeLedger::detach_range(Handle first,Handle last){if(!valid(first)||!valid(last))return{};SlotId f=slot_of(first),l=slot_of(last),before=0,n=0;locate(f,before,n);std::vector<SlotId> slots{f};for(SlotId prev=f,c=n,next=0;c&&slots.back()!=l;prev=c,c=next){slots.push_back(c);next=prev^arena_[c].link;}if(slots.back()!=l)return{};std::vector<int> out;for(SlotId x:slots)out.push_back(arena_[x].id);for(SlotId x:slots){unlink(x);release(x);}return out;}
bool DeliveryRangeLedger::insert_block_after(Handle anchor,const std::vector<int>& stops){if((anchor&&!valid(anchor))||stops.empty())return false;for(std::size_t i=0;i<stops.size();++i){if(stops[i]<=0||find_id(stops[i]))return false;for(std::size_t j=0;j<i;++j)if(stops[i]==stops[j])return false;}SlotId a=anchor?slot_of(anchor):0;for(int id:stops){SlotId x=allocate(id,0,0);insert_after(x,a);a=x;}return true;}std::vector<int> DeliveryRangeLedger::route()const{return ids();}""", """
DeliveryRangeLedger r;auto a=r.append(1),b=r.append(2),c=r.append(3),d=r.append(4);REQUIRE(r.reverse_range(b,d));REQUIRE(r.route()==std::vector<int>{1,4,3,2});REQUIRE(r.detach_range(d,c)==std::vector<int>{4,3});REQUIRE(r.insert_block_after(a,{8,9}));""", """
DeliveryRangeLedger r;auto a=r.append(1),b=r.append(2),c=r.append(3);REQUIRE_FALSE(r.reverse_range(c,a));REQUIRE(r.route()==std::vector<int>{1,2,3});REQUIRE_FALSE(r.insert_block_after(a,{4,4}));REQUIRE(r.detach_range(a,b)==std::vector<int>{1,2});REQUIRE(r.route()==std::vector<int>{3});""",
         "Inclusive range reversal and detachment rewrite XOR links at every internal and boundary node; block insertion validates atomically.", "range-reverse-detach-block"),
    Case("xor-device-event-log", "xor-bounded-event-window", "BoundedEventWindow", """
  explicit BoundedEventWindow(std::size_t capacity);
  Handle append(std::uint64_t sequence, int code);
  bool trim_before(std::uint64_t sequence);
  std::optional<int> code(std::uint64_t sequence) const;
  std::vector<std::uint64_t> sequences() const;""", "std::size_t capacity_;", """
BoundedEventWindow::BoundedEventWindow(std::size_t c):capacity_(c){}BoundedEventWindow::Handle BoundedEventWindow::append(std::uint64_t,int){return 0;}
bool BoundedEventWindow::trim_before(std::uint64_t){return false;}std::optional<int> BoundedEventWindow::code(std::uint64_t)const{return std::nullopt;}
std::vector<std::uint64_t> BoundedEventWindow::sequences()const{return{};}""", """
BoundedEventWindow::BoundedEventWindow(std::size_t c):capacity_(c){if(c==0)throw std::invalid_argument("capacity");}
BoundedEventWindow::Handle BoundedEventWindow::append(std::uint64_t seq,int code_value){if(tail_&&seq<=arena_[tail_].aux)return 0;SlotId x=allocate(static_cast<int>(seq&0x7fffffffU),code_value,seq);insert_after(x,tail_);while(size_>capacity_){SlotId old=head_;unlink(old);release(old);}return handle_of(x);}
bool BoundedEventWindow::trim_before(std::uint64_t seq){bool changed=false;while(head_&&arena_[head_].aux<seq){SlotId old=head_;unlink(old);release(old);changed=true;}return changed;}
std::optional<int> BoundedEventWindow::code(std::uint64_t seq)const{for(SlotId p=0,c=head_,n=0;c;p=c,c=n){if(arena_[c].aux==seq)return arena_[c].value;n=p^arena_[c].link;}return std::nullopt;}
std::vector<std::uint64_t> BoundedEventWindow::sequences()const{std::vector<std::uint64_t> out;for(SlotId p=0,c=head_,n=0;c;p=c,c=n){out.push_back(arena_[c].aux);n=p^arena_[c].link;}return out;}""", """
BoundedEventWindow w(3);w.append(10,1);w.append(20,2);w.append(30,3);w.append(40,4);REQUIRE(w.sequences()==std::vector<std::uint64_t>{20,30,40});REQUIRE(w.code(30)==3);""", """
REQUIRE_THROWS_AS(BoundedEventWindow(0),std::invalid_argument);BoundedEventWindow w(2);auto a=w.append(1,7);REQUIRE(a);REQUIRE_FALSE(w.append(1,8));w.append(2,8);w.append(3,9);REQUIRE(w.sequences()==std::vector<std::uint64_t>{2,3});REQUIRE(w.trim_before(3));REQUIRE_FALSE(w.trim_before(3));""",
         "A positive-capacity sequence window evicts its oldest node and rejects nonmonotonic sequence numbers.", "capacity-prefix-eviction"),
    Case("xor-document-revisions", "xor-revision-checkpoint-chain", "RevisionCheckpointChain", """
  Handle commit(int revision_id, long long delta);
  bool checkpoint(int tag);
  bool rollback(int tag);
  bool squash_last_two(int new_id);
  long long total() const;
  std::vector<int> revisions() const;""", "std::vector<std::pair<int,Handle>> checkpoints_; long long total_ = 0;", """
RevisionCheckpointChain::Handle RevisionCheckpointChain::commit(int,long long){return 0;}bool RevisionCheckpointChain::checkpoint(int){return false;}
bool RevisionCheckpointChain::rollback(int){return false;}bool RevisionCheckpointChain::squash_last_two(int){return false;}long long RevisionCheckpointChain::total()const{return 0;}
std::vector<int> RevisionCheckpointChain::revisions()const{return{};}""", """
RevisionCheckpointChain::Handle RevisionCheckpointChain::commit(int id,long long delta){if(id<=0||find_id(id)||(delta>0&&total_>LLONG_MAX-delta)||(delta<0&&total_<LLONG_MIN-delta))return 0;SlotId x=allocate(id,0,0,delta);insert_after(x,tail_);total_+=delta;return handle_of(x);}
bool RevisionCheckpointChain::checkpoint(int tag){for(const auto& p:checkpoints_)if(p.first==tag)return false;checkpoints_.push_back({tag,tail_?handle_of(tail_):0});return true;}
bool RevisionCheckpointChain::rollback(int tag){Handle target=0;bool found=false;for(const auto& p:checkpoints_)if(p.first==tag){target=p.second;found=true;}if(!found||(target&&!valid(target)))return false;SlotId keep=target?slot_of(target):0;while(tail_!=keep){SlotId x=tail_;total_-=arena_[x].metric;unlink(x);release(x);}return true;}
bool RevisionCheckpointChain::squash_last_two(int id){if(size_<2||id<=0||find_id(id))return false;SlotId b=tail_,p=0,n=0;locate(b,p,n);SlotId a=p;long long da=arena_[a].metric,db=arena_[b].metric;if((db>0&&da>LLONG_MAX-db)||(db<0&&da<LLONG_MIN-db))return false;long long sum=da+db;unlink(b);release(b);unlink(a);release(a);SlotId x=allocate(id,0,0,sum);insert_after(x,tail_);for(auto& cp:checkpoints_)if(cp.second&&(slot_of(cp.second)==a||slot_of(cp.second)==b))cp.second=handle_of(x);return true;}
long long RevisionCheckpointChain::total()const{return total_;}std::vector<int> RevisionCheckpointChain::revisions()const{return ids();}""", """
RevisionCheckpointChain r;r.commit(1,5);r.checkpoint(7);r.commit(2,-2);r.commit(3,4);REQUIRE(r.total()==7);REQUIRE(r.rollback(7));REQUIRE(r.revisions()==std::vector<int>{1});REQUIRE(r.total()==5);""", """
RevisionCheckpointChain r;REQUIRE(r.checkpoint(1));r.commit(1,4);r.commit(2,5);REQUIRE(r.squash_last_two(3));REQUIRE(r.revisions()==std::vector<int>{3});REQUIRE(r.total()==9);REQUIRE_FALSE(r.checkpoint(1));REQUIRE(r.rollback(1));REQUIRE(r.revisions().empty());""",
         "Named checkpoints bind generation handles; rollback truncates a suffix and squashing retargets checkpoints while preserving checked totals.", "checkpoint-rollback-squash"),
    Case("xor-embedded-playlist", "xor-weighted-playback-ring", "WeightedPlaybackRing", """
  Handle add(int track_id, unsigned weight, Handle after = 0);
  bool set_weight(Handle track, unsigned weight);
  std::optional<int> next();
  bool remove(Handle track);
  std::vector<int> physical_order() const;""", "long long total_weight_ = 0;", """
WeightedPlaybackRing::Handle WeightedPlaybackRing::add(int,unsigned,Handle){return 0;}bool WeightedPlaybackRing::set_weight(Handle,unsigned){return false;}
std::optional<int> WeightedPlaybackRing::next(){return std::nullopt;}bool WeightedPlaybackRing::remove(Handle){return false;}std::vector<int> WeightedPlaybackRing::physical_order()const{return{};}""", """
WeightedPlaybackRing::Handle WeightedPlaybackRing::add(int id,unsigned weight,Handle after){if(id<=0||weight==0||weight>static_cast<unsigned>(INT_MAX)||find_id(id)||(after&&!valid(after)))return 0;SlotId x=allocate(id,static_cast<int>(weight),0);insert_after(x,after?slot_of(after):tail_);total_weight_+=weight;return handle_of(x);}
bool WeightedPlaybackRing::set_weight(Handle h,unsigned weight){if(!valid(h)||weight==0||weight>static_cast<unsigned>(INT_MAX))return false;Node& n=arena_[slot_of(h)];total_weight_+=static_cast<long long>(weight)-n.value;n.value=static_cast<int>(weight);return true;}
std::optional<int> WeightedPlaybackRing::next(){if(!head_)return std::nullopt;SlotId best=0;long long score=LLONG_MIN;for(SlotId p=0,c=head_,n=0;c;p=c,c=n){arena_[c].metric+=arena_[c].value;long long s=arena_[c].metric;if(!best||s>score){best=c;score=s;}n=p^arena_[c].link;}arena_[best].metric-=total_weight_;return arena_[best].id;}
bool WeightedPlaybackRing::remove(Handle h){if(!valid(h))return false;SlotId x=slot_of(h);total_weight_-=arena_[x].value;unlink(x);release(x);return true;}std::vector<int> WeightedPlaybackRing::physical_order()const{return ids();}""", """
WeightedPlaybackRing p;auto a=p.add(1,3),b=p.add(2,1,a);REQUIRE((a&&b));REQUIRE(p.next()==1);REQUIRE(p.next()==1);REQUIRE(p.next()==2);REQUIRE(p.physical_order()==std::vector<int>{1,2});""", """
WeightedPlaybackRing p;REQUIRE_FALSE(p.next());auto a=p.add(1,1),b=p.add(2,2,a);REQUIRE_FALSE(p.set_weight(a,0));REQUIRE(p.set_weight(a,4));REQUIRE(p.next()==1);REQUIRE(p.remove(b));REQUIRE_FALSE(p.remove(b));""",
         "Smooth weighted selection updates per-node credit while the physical XOR order remains caller-controlled.", "smooth-weighted-selection"),
    Case("xor-file-block-chain", "xor-block-offset-chain", "BlockOffsetChain", """
  Handle append(int block_id, std::uint64_t bytes);
  std::optional<Handle> split(Handle block, std::uint64_t left_bytes, int right_id);
  bool merge_with_next(Handle block);
  std::optional<int> block_at(std::uint64_t offset) const;
  std::uint64_t size_bytes() const;""", "std::uint64_t bytes_ = 0;", """
BlockOffsetChain::Handle BlockOffsetChain::append(int,std::uint64_t){return 0;}std::optional<BlockOffsetChain::Handle> BlockOffsetChain::split(Handle,std::uint64_t,int){return std::nullopt;}
bool BlockOffsetChain::merge_with_next(Handle){return false;}std::optional<int> BlockOffsetChain::block_at(std::uint64_t)const{return std::nullopt;}std::uint64_t BlockOffsetChain::size_bytes()const{return 0;}""", """
BlockOffsetChain::Handle BlockOffsetChain::append(int id,std::uint64_t bytes){if(id<=0||bytes==0||find_id(id)||bytes_>UINT64_MAX-bytes)return 0;SlotId x=allocate(id,0,bytes);insert_after(x,tail_);bytes_+=bytes;return handle_of(x);}
std::optional<BlockOffsetChain::Handle> BlockOffsetChain::split(Handle h,std::uint64_t left,int right_id){if(!valid(h)||right_id<=0||find_id(right_id))return std::nullopt;SlotId x=slot_of(h);if(left==0||left>=arena_[x].aux)return std::nullopt;std::uint64_t right=arena_[x].aux-left;arena_[x].aux=left;SlotId y=allocate(right_id,0,right);insert_after(y,x);return handle_of(y);}
bool BlockOffsetChain::merge_with_next(Handle h){if(!valid(h))return false;SlotId x=slot_of(h),p=0,n=0;locate(x,p,n);if(!n||arena_[x].aux>UINT64_MAX-arena_[n].aux)return false;arena_[x].aux+=arena_[n].aux;unlink(n);release(n);return true;}
std::optional<int> BlockOffsetChain::block_at(std::uint64_t offset)const{if(offset>=bytes_)return std::nullopt;std::uint64_t base=0;for(SlotId p=0,c=head_,n=0;c;p=c,c=n){if(offset-base<arena_[c].aux)return arena_[c].id;base+=arena_[c].aux;n=p^arena_[c].link;}return std::nullopt;}std::uint64_t BlockOffsetChain::size_bytes()const{return bytes_;}""", """
BlockOffsetChain f;auto a=f.append(1,10);auto right=f.split(a,4,2);REQUIRE(right);REQUIRE(f.block_at(3)==1);REQUIRE(f.block_at(4)==2);REQUIRE(f.merge_with_next(a));REQUIRE(f.size_bytes()==10);""", """
BlockOffsetChain f;auto a=f.append(1,5);REQUIRE_FALSE(f.split(a,0,2));REQUIRE_FALSE(f.split(a,5,2));REQUIRE_FALSE(f.block_at(5));auto b=f.append(2,3);REQUIRE(b);REQUIRE_FALSE(f.merge_with_next(b));REQUIRE(f.block_at(7)==2);""",
         "Extent nodes own byte lengths; split and merge relink neighbors while logical offset lookup uses half-open ranges.", "extent-split-merge-offset"),
    Case("xor-firmware-task-chain", "xor-dependency-ready-chain", "DependencyReadyChain", """
  Handle schedule(int task_id, int dependency_id, Handle after = 0);
  bool mark_complete(Handle task);
  std::optional<int> next_ready() const;
  bool cancel(Handle task);
  std::vector<int> pending() const;""", "", """
DependencyReadyChain::Handle DependencyReadyChain::schedule(int,int,Handle){return 0;}bool DependencyReadyChain::mark_complete(Handle){return false;}
std::optional<int> DependencyReadyChain::next_ready()const{return std::nullopt;}bool DependencyReadyChain::cancel(Handle){return false;}std::vector<int> DependencyReadyChain::pending()const{return{};}""", """
DependencyReadyChain::Handle DependencyReadyChain::schedule(int id,int dependency,Handle after){if(id<=0||find_id(id)||(dependency!=0&&!find_id(dependency))||dependency==id||(after&&!valid(after)))return 0;SlotId x=allocate(id,dependency,0);insert_after(x,after?slot_of(after):tail_);return handle_of(x);}
bool DependencyReadyChain::mark_complete(Handle h){if(!valid(h))return false;arena_[slot_of(h)].aux=1;return true;}
std::optional<int> DependencyReadyChain::next_ready()const{for(SlotId p=0,c=head_,n=0;c;p=c,c=n){if(arena_[c].aux==0){SlotId dep=find_id(arena_[c].value);if(arena_[c].value==0||!dep||arena_[dep].aux==1)return arena_[c].id;}n=p^arena_[c].link;}return std::nullopt;}
bool DependencyReadyChain::cancel(Handle h){if(!valid(h))return false;int id=arena_[slot_of(h)].id;for(SlotId p=0,c=head_,n=0;c;p=c,c=n){if(arena_[c].value==id&&c!=slot_of(h))return false;n=p^arena_[c].link;}SlotId x=slot_of(h);unlink(x);release(x);return true;}std::vector<int> DependencyReadyChain::pending()const{std::vector<int> out;for(SlotId p=0,c=head_,n=0;c;p=c,c=n){if(arena_[c].aux==0)out.push_back(arena_[c].id);n=p^arena_[c].link;}return out;}""", """
DependencyReadyChain q;auto a=q.schedule(1,0),b=q.schedule(2,1,a);REQUIRE((a&&b));REQUIRE(q.next_ready()==1);REQUIRE(q.mark_complete(a));REQUIRE(q.next_ready()==2);REQUIRE_FALSE(q.cancel(a));""", """
DependencyReadyChain q;REQUIRE_FALSE(q.schedule(2,1));auto a=q.schedule(1,0);auto b=q.schedule(2,1,a);REQUIRE_FALSE(q.schedule(2,0));REQUIRE(q.mark_complete(a));REQUIRE(q.cancel(b));REQUIRE(q.cancel(a));REQUIRE(q.pending().empty());""",
         "A task is ready only when its predecessor dependency is completed; referenced tasks cannot be cancelled.", "dependency-readiness-cancel-guard"),
    Case("xor-inventory-pick-chain", "xor-precedence-pick-chain", "PrecedencePickChain", """
  Handle add(int pick_id, int must_follow_id);
  bool relocate_after(Handle pick, Handle anchor);
  bool complete(Handle pick);
  std::vector<int> feasible_order() const;
  std::optional<int> next_pick() const;""", "", """
PrecedencePickChain::Handle PrecedencePickChain::add(int,int){return 0;}bool PrecedencePickChain::relocate_after(Handle,Handle){return false;}
bool PrecedencePickChain::complete(Handle){return false;}std::vector<int> PrecedencePickChain::feasible_order()const{return{};}std::optional<int> PrecedencePickChain::next_pick()const{return std::nullopt;}""", """
PrecedencePickChain::Handle PrecedencePickChain::add(int id,int dependency){if(id<=0||find_id(id)||(dependency&&!find_id(dependency)))return 0;SlotId x=allocate(id,dependency,0);insert_after(x,tail_);return handle_of(x);}
bool PrecedencePickChain::relocate_after(Handle h,Handle anchor){if(!valid(h)||(anchor&&!valid(anchor))||h==anchor)return false;SlotId x=slot_of(h),a=anchor?slot_of(anchor):0;auto proposed=ids();int id=arena_[x].id;proposed.erase(std::find(proposed.begin(),proposed.end(),id));auto position=proposed.begin();if(a){position=std::find(proposed.begin(),proposed.end(),arena_[a].id);++position;}proposed.insert(position,id);for(SlotId p=0,c=head_,n=0;c;p=c,c=n){int dependency=arena_[c].value;if(dependency&&std::find(proposed.begin(),proposed.end(),dependency)>std::find(proposed.begin(),proposed.end(),arena_[c].id))return false;n=p^arena_[c].link;}unlink(x);insert_after(x,a);return true;}
bool PrecedencePickChain::complete(Handle h){if(!valid(h))return false;SlotId x=slot_of(h),d=find_id(arena_[x].value);if(d&&arena_[d].aux==0)return false;arena_[x].aux=1;return true;}
std::vector<int> PrecedencePickChain::feasible_order()const{return ids();}std::optional<int> PrecedencePickChain::next_pick()const{for(SlotId p=0,c=head_,n=0;c;p=c,c=n){SlotId d=find_id(arena_[c].value);if(arena_[c].aux==0&&(!d||arena_[d].aux==1))return arena_[c].id;n=p^arena_[c].link;}return std::nullopt;}""", """
PrecedencePickChain p;auto a=p.add(1,0),b=p.add(2,1),c=p.add(3,0);REQUIRE((a&&b&&c));REQUIRE_FALSE(p.relocate_after(b,0));REQUIRE(p.relocate_after(c,a));REQUIRE(p.complete(a));REQUIRE(p.next_pick()==3);""", """
PrecedencePickChain p;auto a=p.add(1,0),b=p.add(2,1),c=p.add(3,2);REQUIRE_FALSE(p.complete(c));REQUIRE(p.complete(a));REQUIRE(p.complete(b));REQUIRE(p.next_pick()==3);REQUIRE_FALSE(p.relocate_after(a,c));""",
         "Relocation is accepted only when every predecessor remains before its dependent; completion follows the same dependency state.", "precedence-preserving-relocation"),
    Case("xor-museum-tour", "xor-accessible-tour-cursor", "AccessibleTourCursor", """
  Handle append(int waypoint_id, unsigned access_mask);
  bool set_allowed(unsigned allowed_mask);
  std::optional<int> next_accessible();
  std::optional<int> previous_accessible();
  bool erase(Handle waypoint);
  std::vector<int> route() const;""", "unsigned allowed_ = 1;", """
AccessibleTourCursor::Handle AccessibleTourCursor::append(int,unsigned){return 0;}bool AccessibleTourCursor::set_allowed(unsigned){return false;}
std::optional<int> AccessibleTourCursor::next_accessible(){return std::nullopt;}std::optional<int> AccessibleTourCursor::previous_accessible(){return std::nullopt;}
bool AccessibleTourCursor::erase(Handle){return false;}std::vector<int> AccessibleTourCursor::route()const{return{};}""", """
AccessibleTourCursor::Handle AccessibleTourCursor::append(int id,unsigned mask){if(id<=0||mask==0||find_id(id))return 0;SlotId x=allocate(id,static_cast<int>(mask),0);insert_after(x,tail_);if(!current_&&(mask&allowed_))current_=x;return handle_of(x);}
bool AccessibleTourCursor::set_allowed(unsigned mask){if(mask==0)return false;allowed_=mask;current_=0;return true;}
std::optional<int> AccessibleTourCursor::next_accessible(){SlotId p=0,n=0;if(current_)locate(current_,p,n);else n=head_;for(SlotId prev=current_,c=n,next=0;c;prev=c,c=next){if(static_cast<unsigned>(arena_[c].value)&allowed_){current_=c;return arena_[c].id;}next=prev^arena_[c].link;}return std::nullopt;}
std::optional<int> AccessibleTourCursor::previous_accessible(){if(!current_)return std::nullopt;SlotId p=0,n=0;locate(current_,p,n);for(SlotId next=current_,c=p,prev=0;c;next=c,c=prev){if(static_cast<unsigned>(arena_[c].value)&allowed_){current_=c;return arena_[c].id;}prev=next^arena_[c].link;}return std::nullopt;}
bool AccessibleTourCursor::erase(Handle h){if(!valid(h))return false;SlotId x=slot_of(h),p=0,n=0;locate(x,p,n);if(current_==x)current_=n?n:p;unlink(x);release(x);return true;}std::vector<int> AccessibleTourCursor::route()const{return ids();}""", """
AccessibleTourCursor t;auto a=t.append(1,1),b=t.append(2,2),c=t.append(3,1);REQUIRE((a&&b&&c));REQUIRE(t.next_accessible()==3);REQUIRE_FALSE(t.next_accessible());REQUIRE(t.previous_accessible()==1);""", """
AccessibleTourCursor t;t.append(1,1);auto b=t.append(2,2);t.append(3,4);REQUIRE(t.set_allowed(2));REQUIRE(t.next_accessible()==2);REQUIRE(t.erase(b));REQUIRE_FALSE(t.next_accessible());REQUIRE_FALSE(t.set_allowed(0));""",
         "A changing access mask drives nonwrapping cursor scans while the complete physical tour remains intact.", "filtered-cursor-mask"),
    Case("xor-notification-history", "xor-pinned-notification-feed", "PinnedNotificationFeed", """
  Handle push(int notification_id, bool pinned);
  bool set_pinned(Handle notification, bool pinned);
  bool mark_read(Handle notification);
  std::optional<int> next_unread() const;
  std::vector<int> feed() const;""", "", """
PinnedNotificationFeed::Handle PinnedNotificationFeed::push(int,bool){return 0;}bool PinnedNotificationFeed::set_pinned(Handle,bool){return false;}
bool PinnedNotificationFeed::mark_read(Handle){return false;}std::optional<int> PinnedNotificationFeed::next_unread()const{return std::nullopt;}std::vector<int> PinnedNotificationFeed::feed()const{return{};}""", """
PinnedNotificationFeed::Handle PinnedNotificationFeed::push(int id,bool pinned){if(id<=0||find_id(id))return 0;SlotId anchor=0;if(pinned){for(SlotId p=0,c=head_,n=0;c;p=c,c=n){if(arena_[c].value==0)break;anchor=c;n=p^arena_[c].link;}}else anchor=tail_;SlotId x=allocate(id,pinned?1:0,0);insert_after(x,anchor);return handle_of(x);}
bool PinnedNotificationFeed::set_pinned(Handle h,bool pinned){if(!valid(h))return false;SlotId x=slot_of(h);if((arena_[x].value!=0)==pinned)return true;unlink(x);arena_[x].value=pinned?1:0;SlotId anchor=0;if(pinned){for(SlotId p=0,c=head_,n=0;c;p=c,c=n){if(arena_[c].value==0)break;anchor=c;n=p^arena_[c].link;}}else anchor=tail_;insert_after(x,anchor);return true;}
bool PinnedNotificationFeed::mark_read(Handle h){if(!valid(h))return false;arena_[slot_of(h)].aux=1;return true;}std::optional<int> PinnedNotificationFeed::next_unread()const{for(SlotId p=0,c=head_,n=0;c;p=c,c=n){if(arena_[c].aux==0)return arena_[c].id;n=p^arena_[c].link;}return std::nullopt;}std::vector<int> PinnedNotificationFeed::feed()const{return ids();}""", """
PinnedNotificationFeed f;auto a=f.push(1,false),b=f.push(2,true),c=f.push(3,false);REQUIRE((a&&b&&c));REQUIRE(f.feed()==std::vector<int>{2,1,3});REQUIRE(f.set_pinned(c,true));REQUIRE(f.feed()==std::vector<int>{2,3,1});""", """
PinnedNotificationFeed f;auto a=f.push(1,true),b=f.push(2,false);REQUIRE(f.next_unread()==1);REQUIRE(f.mark_read(a));REQUIRE(f.next_unread()==2);REQUIRE(f.mark_read(b));REQUIRE_FALSE(f.next_unread());REQUIRE(f.set_pinned(b,true));""",
         "Pinned and unpinned nodes form stable partitions; unread selection scans the resulting XOR order.", "stable-partition-unread"),
    Case("xor-packet-reassembly-order", "xor-packet-gap-index", "PacketGapIndex", """
  bool insert(std::uint32_t first, std::uint32_t last);
  bool erase(std::uint32_t first, std::uint32_t last);
  std::optional<std::uint32_t> first_gap(std::uint32_t from) const;
  std::vector<std::pair<std::uint32_t,std::uint32_t>> spans() const;""", "", """
bool PacketGapIndex::insert(std::uint32_t,std::uint32_t){return false;}bool PacketGapIndex::erase(std::uint32_t,std::uint32_t){return false;}
std::optional<std::uint32_t> PacketGapIndex::first_gap(std::uint32_t)const{return std::nullopt;}std::vector<std::pair<std::uint32_t,std::uint32_t>> PacketGapIndex::spans()const{return{};}""", """
bool PacketGapIndex::insert(std::uint32_t first,std::uint32_t last){if(first>last)return false;std::vector<std::pair<std::uint32_t,std::uint32_t>> v=spans();v.push_back({first,last});std::sort(v.begin(),v.end());std::vector<std::pair<std::uint32_t,std::uint32_t>> merged;for(auto r:v){if(merged.empty()||static_cast<std::uint64_t>(merged.back().second)+1U<r.first)merged.push_back(r);else if(r.second>merged.back().second)merged.back().second=r.second;}clear_all();for(auto r:merged){SlotId x=allocate(static_cast<int>(r.first&0x7fffffffU),0,r.first,static_cast<long long>(r.second));insert_after(x,tail_);}return true;}
bool PacketGapIndex::erase(std::uint32_t first,std::uint32_t last){if(first>last)return false;auto v=spans();std::vector<std::pair<std::uint32_t,std::uint32_t>> out;bool changed=false;for(auto r:v){if(last<r.first||first>r.second){out.push_back(r);continue;}changed=true;if(first>r.first)out.push_back({r.first,first-1U});if(last<r.second&&last!=UINT32_MAX)out.push_back({last+1U,r.second});}if(!changed)return false;clear_all();for(auto r:out){SlotId x=allocate(static_cast<int>(r.first&0x7fffffffU),0,r.first,static_cast<long long>(r.second));insert_after(x,tail_);}return true;}
std::optional<std::uint32_t> PacketGapIndex::first_gap(std::uint32_t from)const{std::uint32_t candidate=from;for(auto r:spans()){if(candidate<r.first)return candidate;if(candidate<=r.second){if(r.second==UINT32_MAX)return std::nullopt;candidate=r.second+1U;}}return candidate;}
std::vector<std::pair<std::uint32_t,std::uint32_t>> PacketGapIndex::spans()const{std::vector<std::pair<std::uint32_t,std::uint32_t>> out;for(SlotId p=0,c=head_,n=0;c;p=c,c=n){out.push_back({static_cast<std::uint32_t>(arena_[c].aux),static_cast<std::uint32_t>(arena_[c].metric)});n=p^arena_[c].link;}return out;}""", """
PacketGapIndex g;REQUIRE(g.insert(10,12));REQUIRE(g.insert(14,15));REQUIRE(g.insert(13,13));REQUIRE(g.spans()==std::vector<std::pair<std::uint32_t,std::uint32_t>>{{10,15}});REQUIRE(g.first_gap(10)==16);""", """
PacketGapIndex g;REQUIRE_FALSE(g.insert(5,4));g.insert(1,10);REQUIRE(g.erase(4,6));REQUIRE(g.spans()==std::vector<std::pair<std::uint32_t,std::uint32_t>>{{1,3},{7,10}});REQUIRE(g.first_gap(2)==4);REQUIRE_FALSE(g.erase(20,30));""",
         "Sorted disjoint packet spans merge on insertion, split on erasure, and expose the first missing sequence without overflow.", "interval-merge-split-gap"),
    Case("xor-parking-queue", "xor-neighbor-departure-line", "NeighborDepartureLine", """
  struct Departure { int vehicle; std::optional<int> before; std::optional<int> after; };
  Handle arrive(int vehicle_id);
  std::optional<Departure> depart(Handle vehicle);
  bool swap_adjacent(Handle left, Handle right);
  std::vector<int> line() const;""", "", """
NeighborDepartureLine::Handle NeighborDepartureLine::arrive(int){return 0;}std::optional<NeighborDepartureLine::Departure> NeighborDepartureLine::depart(Handle){return std::nullopt;}
bool NeighborDepartureLine::swap_adjacent(Handle,Handle){return false;}std::vector<int> NeighborDepartureLine::line()const{return{};}""", """
NeighborDepartureLine::Handle NeighborDepartureLine::arrive(int id){if(id<=0||find_id(id))return 0;SlotId x=allocate(id,0,0);insert_after(x,tail_);return handle_of(x);}
std::optional<NeighborDepartureLine::Departure> NeighborDepartureLine::depart(Handle h){if(!valid(h))return std::nullopt;SlotId x=slot_of(h),p=0,n=0;locate(x,p,n);Departure d{arena_[x].id,p?std::optional<int>(arena_[p].id):std::nullopt,n?std::optional<int>(arena_[n].id):std::nullopt};unlink(x);release(x);return d;}
bool NeighborDepartureLine::swap_adjacent(Handle left,Handle right){if(!valid(left)||!valid(right))return false;SlotId a=slot_of(left),b=slot_of(right),p=0,n=0;locate(a,p,n);if(n!=b)return false;SlotId q=0,after=0;locate(b,q,after);unlink(b);insert_after(b,p);return true;}std::vector<int> NeighborDepartureLine::line()const{return ids();}""", """
NeighborDepartureLine l;auto a=l.arrive(1),b=l.arrive(2),c=l.arrive(3);REQUIRE(c);REQUIRE(l.swap_adjacent(a,b));REQUIRE(l.line()==std::vector<int>{2,1,3});auto d=l.depart(a);REQUIRE(d);REQUIRE(d->before==2);REQUIRE(d->after==3);""", """
NeighborDepartureLine l;auto a=l.arrive(1),b=l.arrive(2),c=l.arrive(3);REQUIRE_FALSE(l.swap_adjacent(a,c));auto d=l.depart(b);REQUIRE(d->before==1);REQUIRE(d->after==3);REQUIRE_FALSE(l.depart(b));REQUIRE(l.line()==std::vector<int>{1,3});""",
         "Departure returns pre-removal neighbors and adjacent transposition rewrites the four surrounding XOR relations.", "neighbor-report-adjacent-swap"),
    Case("xor-print-job-store", "xor-priority-print-spool", "PriorityPrintSpool", """
  Handle submit(int job_id, int priority);
  bool reprioritize(Handle job, int priority);
  std::optional<int> dispatch();
  bool cancel(Handle job);
  std::vector<int> order() const;""", "", """
PriorityPrintSpool::Handle PriorityPrintSpool::submit(int,int){return 0;}bool PriorityPrintSpool::reprioritize(Handle,int){return false;}
std::optional<int> PriorityPrintSpool::dispatch(){return std::nullopt;}bool PriorityPrintSpool::cancel(Handle){return false;}std::vector<int> PriorityPrintSpool::order()const{return{};}""", """
PriorityPrintSpool::Handle PriorityPrintSpool::submit(int id,int priority){if(id<=0||priority<0||priority>9||find_id(id))return 0;SlotId anchor=0;for(SlotId p=0,c=head_,n=0;c;p=c,c=n){if(arena_[c].value<priority)break;anchor=c;n=p^arena_[c].link;}SlotId x=allocate(id,priority,0);insert_after(x,anchor);return handle_of(x);}
bool PriorityPrintSpool::reprioritize(Handle h,int priority){if(!valid(h)||priority<0||priority>9)return false;SlotId x=slot_of(h);if(arena_[x].value==priority)return true;unlink(x);arena_[x].value=priority;SlotId anchor=0;for(SlotId p=0,c=head_,n=0;c;p=c,c=n){if(c!=x&&arena_[c].value<priority)break;if(c!=x)anchor=c;n=p^arena_[c].link;}insert_after(x,anchor);return true;}
std::optional<int> PriorityPrintSpool::dispatch(){if(!head_)return std::nullopt;SlotId x=head_;int id=arena_[x].id;unlink(x);release(x);return id;}bool PriorityPrintSpool::cancel(Handle h){if(!valid(h))return false;SlotId x=slot_of(h);unlink(x);release(x);return true;}std::vector<int> PriorityPrintSpool::order()const{return ids();}""", """
PriorityPrintSpool q;auto a=q.submit(1,2),b=q.submit(2,5),c=q.submit(3,5);REQUIRE((a&&b&&c));REQUIRE(q.order()==std::vector<int>{2,3,1});REQUIRE(q.dispatch()==2);""", """
PriorityPrintSpool q;auto a=q.submit(1,1),b=q.submit(2,1);REQUIRE_FALSE(q.submit(3,10));REQUIRE(q.reprioritize(a,3));REQUIRE(q.order()==std::vector<int>{1,2});REQUIRE(q.cancel(b));REQUIRE_FALSE(q.cancel(b));""",
         "Jobs form stable descending priority bands; reprioritization relinks a node and dispatch removes the oldest highest-priority job.", "stable-priority-bands"),
    Case("xor-radio-station-list", "xor-band-preset-ring", "BandPresetRing", """
  Handle add(int preset_id, unsigned band, Handle after = 0);
  bool remove(Handle preset);
  std::optional<int> seek(int direction, unsigned allowed_bands);
  bool tune(Handle preset);
  std::vector<int> presets() const;""", "", """
BandPresetRing::Handle BandPresetRing::add(int,unsigned,Handle){return 0;}bool BandPresetRing::remove(Handle){return false;}
std::optional<int> BandPresetRing::seek(int,unsigned){return std::nullopt;}bool BandPresetRing::tune(Handle){return false;}std::vector<int> BandPresetRing::presets()const{return{};}""", """
BandPresetRing::Handle BandPresetRing::add(int id,unsigned band,Handle after){if(id<=0||band==0||(band&(band-1U))||find_id(id)||(after&&!valid(after)))return 0;SlotId x=allocate(id,static_cast<int>(band),0);insert_after(x,after?slot_of(after):tail_);if(!current_)current_=x;return handle_of(x);}
bool BandPresetRing::remove(Handle h){if(!valid(h))return false;SlotId x=slot_of(h),p=0,n=0;locate(x,p,n);if(current_==x)current_=n?n:p;unlink(x);release(x);return true;}
std::optional<int> BandPresetRing::seek(int direction,unsigned allowed){if(!current_||(direction!=-1&&direction!=1)||allowed==0)return std::nullopt;SlotId x=current_;for(std::size_t i=0;i<size_;++i){SlotId p=0,n=0;locate(x,p,n);x=direction>0?(n?n:head_):(p?p:tail_);if(static_cast<unsigned>(arena_[x].value)&allowed){current_=x;return arena_[x].id;}}return std::nullopt;}
bool BandPresetRing::tune(Handle h){if(!valid(h))return false;current_=slot_of(h);return true;}std::vector<int> BandPresetRing::presets()const{return ids();}""", """
BandPresetRing r;auto a=r.add(1,1),b=r.add(2,2,a),c=r.add(3,4,b);REQUIRE((a&&b&&c));REQUIRE(r.seek(1,4)==3);REQUIRE(r.seek(1,1)==1);REQUIRE(r.seek(-1,2)==2);""", """
BandPresetRing r;auto a=r.add(1,1),b=r.add(2,2,a);REQUIRE_FALSE(r.add(3,3));REQUIRE_FALSE(r.seek(0,1));REQUIRE(r.tune(b));REQUIRE(r.remove(b));REQUIRE_FALSE(r.tune(b));REQUIRE(r.seek(1,1)==1);""",
         "Directional band-filtered seek wraps at most once around a physical XOR ring and updates a tuned cursor.", "band-filtered-circular-seek"),
    Case("xor-recipe-step-chain", "xor-recipe-dependency-chain", "RecipeDependencyChain", """
  Handle add(int step_id, const std::vector<int>& prerequisites);
  bool move_after(Handle step, Handle anchor);
  bool complete(Handle step);
  std::optional<int> next_ready() const;
  std::vector<int> order() const;""", "std::vector<std::pair<int,std::vector<int>>> requirements_;", """
RecipeDependencyChain::Handle RecipeDependencyChain::add(int,const std::vector<int>&){return 0;}bool RecipeDependencyChain::move_after(Handle,Handle){return false;}
bool RecipeDependencyChain::complete(Handle){return false;}std::optional<int> RecipeDependencyChain::next_ready()const{return std::nullopt;}std::vector<int> RecipeDependencyChain::order()const{return{};}""", """
RecipeDependencyChain::Handle RecipeDependencyChain::add(int id,const std::vector<int>& req){if(id<=0||find_id(id))return 0;for(std::size_t i=0;i<req.size();++i){if(req[i]<=0||!find_id(req[i]))return 0;for(std::size_t j=0;j<i;++j)if(req[i]==req[j])return 0;}SlotId x=allocate(id,0,0);insert_after(x,tail_);requirements_.push_back({id,req});return handle_of(x);}
bool RecipeDependencyChain::move_after(Handle h,Handle anchor){if(!valid(h)||(anchor&&!valid(anchor))||h==anchor)return false;SlotId x=slot_of(h),a=anchor?slot_of(anchor):0;auto proposed=ids();int id=arena_[x].id;proposed.erase(std::find(proposed.begin(),proposed.end(),id));auto at=proposed.begin();if(a){at=std::find(proposed.begin(),proposed.end(),arena_[a].id);++at;}proposed.insert(at,id);for(const auto& row:requirements_)for(int req:row.second)if(std::find(proposed.begin(),proposed.end(),req)>std::find(proposed.begin(),proposed.end(),row.first))return false;unlink(x);insert_after(x,a);return true;}
bool RecipeDependencyChain::complete(Handle h){if(!valid(h))return false;int id=arena_[slot_of(h)].id;for(const auto& row:requirements_)if(row.first==id)for(int req:row.second){SlotId x=find_id(req);if(x&&arena_[x].aux==0)return false;}arena_[slot_of(h)].aux=1;return true;}
std::optional<int> RecipeDependencyChain::next_ready()const{for(SlotId p=0,c=head_,n=0;c;p=c,c=n){if(arena_[c].aux==0){bool ready=true;for(const auto& row:requirements_)if(row.first==arena_[c].id)for(int req:row.second){SlotId x=find_id(req);if(x&&arena_[x].aux==0)ready=false;}if(ready)return arena_[c].id;}n=p^arena_[c].link;}return std::nullopt;}std::vector<int> RecipeDependencyChain::order()const{return ids();}""", """
RecipeDependencyChain r;auto a=r.add(1,{}),b=r.add(2,{1}),c=r.add(3,{1});REQUIRE((a&&b&&c));REQUIRE_FALSE(r.move_after(a,c));REQUIRE(r.complete(a));REQUIRE(r.next_ready()==2);REQUIRE(r.move_after(c,a));""", """
RecipeDependencyChain r;auto a=r.add(1,{}),b=r.add(2,{1});REQUIRE_FALSE(r.add(3,{9}));REQUIRE_FALSE(r.complete(b));REQUIRE(r.complete(a));REQUIRE(r.complete(b));REQUIRE_FALSE(r.next_ready());REQUIRE_FALSE(r.move_after(a,b));""",
         "Multiple prerequisite edges constrain physical order, completion, and deterministic ready-step selection.", "multi-prerequisite-topology"),
    Case("xor-route-waypoint-store", "xor-waypoint-distance-chain", "WaypointDistanceChain", """
  Handle append(int waypoint_id, int x, int y);
  bool move(Handle waypoint, int x, int y);
  bool erase(Handle waypoint);
  std::optional<long long> distance() const;
  std::vector<int> route() const;""", "long long distance_ = 0;", """
WaypointDistanceChain::Handle WaypointDistanceChain::append(int,int,int){return 0;}bool WaypointDistanceChain::move(Handle,int,int){return false;}
bool WaypointDistanceChain::erase(Handle){return false;}std::optional<long long> WaypointDistanceChain::distance()const{return std::nullopt;}std::vector<int> WaypointDistanceChain::route()const{return{};}""", """
long long WaypointDistanceChain::edge(const Node&a,const Node&b){return std::llabs(static_cast<long long>(a.value)-b.value)+std::llabs(a.metric-b.metric);}
WaypointDistanceChain::Handle WaypointDistanceChain::append(int id,int x,int y){if(id<=0||find_id(id)||x<-1000000000||x>1000000000||y<-1000000000||y>1000000000)return 0;SlotId s=allocate(id,x,0,y);if(tail_)distance_+=edge(arena_[tail_],arena_[s]);insert_after(s,tail_);return handle_of(s);}
bool WaypointDistanceChain::move(Handle h,int x,int y){if(!valid(h)||x<-1000000000||x>1000000000||y<-1000000000||y>1000000000)return false;SlotId s=slot_of(h),p=0,n=0;locate(s,p,n);long long old=(p?edge(arena_[p],arena_[s]):0)+(n?edge(arena_[s],arena_[n]):0);Node candidate=arena_[s];candidate.value=x;candidate.metric=y;long long fresh=(p?edge(arena_[p],candidate):0)+(n?edge(candidate,arena_[n]):0);distance_+=fresh-old;arena_[s].value=x;arena_[s].metric=y;return true;}
bool WaypointDistanceChain::erase(Handle h){if(!valid(h))return false;SlotId s=slot_of(h),p=0,n=0;locate(s,p,n);distance_-=(p?edge(arena_[p],arena_[s]):0)+(n?edge(arena_[s],arena_[n]):0);if(p&&n)distance_+=edge(arena_[p],arena_[n]);unlink(s);release(s);return true;}std::optional<long long> WaypointDistanceChain::distance()const{return distance_;}std::vector<int> WaypointDistanceChain::route()const{return ids();}""", """
WaypointDistanceChain r;auto a=r.append(1,0,0),b=r.append(2,3,4),c=r.append(3,5,4);REQUIRE((a&&b&&c));REQUIRE(r.distance()==9);REQUIRE(r.move(b,1,1));REQUIRE(r.distance()==9);""", """
WaypointDistanceChain r;auto a=r.append(1,0,0),b=r.append(2,2,0),c=r.append(3,5,0);REQUIRE((a&&c));REQUIRE_FALSE(r.append(4,1000000001,0));REQUIRE(r.erase(b));REQUIRE(r.distance()==5);REQUIRE_FALSE(r.erase(b));REQUIRE(r.route()==std::vector<int>{1,3});""",
         "Coordinate mutations update only neighboring Manhattan edges while preserving a checked route aggregate.", "neighbor-delta-distance"),
    Case("xor-sensor-sample-history", "xor-monotonic-sample-window", "MonotonicSampleWindow", """
  explicit MonotonicSampleWindow(std::size_t capacity);
  bool record(std::uint64_t timestamp, int value);
  bool discard_through(std::uint64_t timestamp);
  std::optional<int> latest_at(std::uint64_t timestamp) const;
  std::vector<std::uint64_t> timestamps() const;""", "std::size_t capacity_;", """
MonotonicSampleWindow::MonotonicSampleWindow(std::size_t c):capacity_(c){}bool MonotonicSampleWindow::record(std::uint64_t,int){return false;}
bool MonotonicSampleWindow::discard_through(std::uint64_t){return false;}std::optional<int> MonotonicSampleWindow::latest_at(std::uint64_t)const{return std::nullopt;}
std::vector<std::uint64_t> MonotonicSampleWindow::timestamps()const{return{};}""", """
MonotonicSampleWindow::MonotonicSampleWindow(std::size_t c):capacity_(c){if(c==0)throw std::invalid_argument("capacity");}
bool MonotonicSampleWindow::record(std::uint64_t ts,int value){for(SlotId p=0,c=head_,n=0;c;p=c,c=n){if(arena_[c].aux==ts){arena_[c].value=value;return true;}if(arena_[c].aux>ts){SlotId x=allocate(static_cast<int>(ts&0x7fffffffU),value,ts);insert_after(x,p);while(size_>capacity_){SlotId old=head_;unlink(old);release(old);}return true;}n=p^arena_[c].link;}SlotId x=allocate(static_cast<int>(ts&0x7fffffffU),value,ts);insert_after(x,tail_);while(size_>capacity_){SlotId old=head_;unlink(old);release(old);}return true;}
bool MonotonicSampleWindow::discard_through(std::uint64_t ts){bool changed=false;while(head_&&arena_[head_].aux<=ts){SlotId old=head_;unlink(old);release(old);changed=true;}return changed;}
std::optional<int> MonotonicSampleWindow::latest_at(std::uint64_t ts)const{std::optional<int> out;for(SlotId p=0,c=head_,n=0;c;p=c,c=n){if(arena_[c].aux>ts)break;out=arena_[c].value;n=p^arena_[c].link;}return out;}
std::vector<std::uint64_t> MonotonicSampleWindow::timestamps()const{std::vector<std::uint64_t> out;for(SlotId p=0,c=head_,n=0;c;p=c,c=n){out.push_back(arena_[c].aux);n=p^arena_[c].link;}return out;}""", """
MonotonicSampleWindow w(3);w.record(30,3);w.record(10,1);w.record(20,2);REQUIRE(w.timestamps()==std::vector<std::uint64_t>{10,20,30});w.record(20,8);REQUIRE(w.latest_at(20)==8);""", """
REQUIRE_THROWS_AS(MonotonicSampleWindow(0),std::invalid_argument);MonotonicSampleWindow w(2);w.record(2,2);w.record(1,1);w.record(3,3);REQUIRE(w.timestamps()==std::vector<std::uint64_t>{2,3});REQUIRE(w.discard_through(2));REQUIRE_FALSE(w.discard_through(2));""",
         "Out-of-order timestamps are inserted in sorted order, equal times replace values, and capacity evicts the oldest time.", "sorted-time-replace-evict"),
    Case("xor-support-ticket-order", "xor-escalation-ticket-chain", "EscalationTicketChain", """
  Handle open(int ticket_id, unsigned severity);
  bool escalate(Handle ticket, unsigned delta);
  bool resolve(Handle ticket);
  std::optional<int> next() const;
  std::vector<int> order() const;""", "", """
EscalationTicketChain::Handle EscalationTicketChain::open(int,unsigned){return 0;}bool EscalationTicketChain::escalate(Handle,unsigned){return false;}
bool EscalationTicketChain::resolve(Handle){return false;}std::optional<int> EscalationTicketChain::next()const{return std::nullopt;}std::vector<int> EscalationTicketChain::order()const{return{};}""", """
EscalationTicketChain::Handle EscalationTicketChain::open(int id,unsigned severity){if(id<=0||severity<1||severity>5||find_id(id))return 0;SlotId anchor=0;for(SlotId p=0,c=head_,n=0;c;p=c,c=n){if(static_cast<unsigned>(arena_[c].value)<severity)break;anchor=c;n=p^arena_[c].link;}SlotId x=allocate(id,static_cast<int>(severity),0);insert_after(x,anchor);return handle_of(x);}
bool EscalationTicketChain::escalate(Handle h,unsigned delta){if(!valid(h)||delta==0)return false;SlotId x=slot_of(h);unsigned severity=static_cast<unsigned>(arena_[x].value);if(severity+delta>5)return false;unlink(x);arena_[x].value=static_cast<int>(severity+delta);SlotId anchor=0;for(SlotId p=0,c=head_,n=0;c;p=c,c=n){if(c!=x&&arena_[c].value<arena_[x].value)break;if(c!=x)anchor=c;n=p^arena_[c].link;}insert_after(x,anchor);return true;}
bool EscalationTicketChain::resolve(Handle h){if(!valid(h))return false;SlotId x=slot_of(h);unlink(x);release(x);return true;}std::optional<int> EscalationTicketChain::next()const{return head_?std::optional<int>(arena_[head_].id):std::nullopt;}std::vector<int> EscalationTicketChain::order()const{return ids();}""", """
EscalationTicketChain d;auto a=d.open(1,2),b=d.open(2,4),c=d.open(3,2);REQUIRE((a&&b&&c));REQUIRE(d.order()==std::vector<int>{2,1,3});REQUIRE(d.escalate(a,3));REQUIRE(d.next()==1);""", """
EscalationTicketChain d;auto a=d.open(1,1);REQUIRE_FALSE(d.open(2,0));REQUIRE_FALSE(d.escalate(a,5));REQUIRE(d.escalate(a,4));REQUIRE_FALSE(d.escalate(a,1));REQUIRE(d.resolve(a));REQUIRE_FALSE(d.resolve(a));""",
         "Checked severity transitions relink tickets into stable descending bands and stale resolved handles are rejected.", "checked-escalation-order"),
    Case("xor-train-car-store", "xor-consist-block-editor", "ConsistBlockEditor", """
  bool couple_after(int anchor_id, const std::vector<int>& cars);
  std::vector<int> detach(int first_id, int last_id);
  bool reverse(int first_id, int last_id);
  std::vector<int> consist() const;""", "", """
bool ConsistBlockEditor::couple_after(int,const std::vector<int>&){return false;}std::vector<int> ConsistBlockEditor::detach(int,int){return{};}
bool ConsistBlockEditor::reverse(int,int){return false;}std::vector<int> ConsistBlockEditor::consist()const{return{};}""", """
bool ConsistBlockEditor::couple_after(int anchor_id,const std::vector<int>& cars){SlotId anchor=anchor_id?find_id(anchor_id):0;if((anchor_id&&!anchor)||cars.empty())return false;for(std::size_t i=0;i<cars.size();++i){if(cars[i]<=0||find_id(cars[i]))return false;for(std::size_t j=0;j<i;++j)if(cars[i]==cars[j])return false;}for(int id:cars){SlotId x=allocate(id,0,0);insert_after(x,anchor);anchor=x;}return true;}
std::vector<int> ConsistBlockEditor::detach(int first_id,int last_id){SlotId first=find_id(first_id),last=find_id(last_id);if(!first||!last)return{};std::vector<SlotId> slots{first};SlotId p=0,n=0;locate(first,p,n);for(SlotId prev=first,c=n,next=0;c&&slots.back()!=last;prev=c,c=next){slots.push_back(c);next=prev^arena_[c].link;}if(slots.back()!=last)return{};std::vector<int> out;for(SlotId x:slots)out.push_back(arena_[x].id);for(SlotId x:slots){unlink(x);release(x);}return out;}
bool ConsistBlockEditor::reverse(int first_id,int last_id){SlotId first=find_id(first_id),last=find_id(last_id);if(!first||!last)return false;SlotId before=0,n=0;locate(first,before,n);bool found=first==last;for(SlotId prev=first,c=n,next=0;c&&!found;prev=c,c=next){next=prev^arena_[c].link;if(c==last)found=true;}if(!found)return false;if(first==last)return true;SlotId p=0,after=0;locate(last,p,after);arena_[first].link^=before^after;arena_[last].link^=after^before;if(before)arena_[before].link^=first^last;else head_=last;if(after)arena_[after].link^=last^first;else tail_=first;return true;}std::vector<int> ConsistBlockEditor::consist()const{return ids();}""", """
ConsistBlockEditor c;REQUIRE(c.couple_after(0,{1,2,3,4}));REQUIRE(c.reverse(2,4));REQUIRE(c.consist()==std::vector<int>{1,4,3,2});REQUIRE(c.detach(4,3)==std::vector<int>{4,3});""", """
ConsistBlockEditor c;REQUIRE_FALSE(c.couple_after(0,{1,1}));REQUIRE(c.couple_after(0,{1,2,3}));REQUIRE_FALSE(c.reverse(3,1));REQUIRE(c.detach(2,3)==std::vector<int>{2,3});REQUIRE(c.couple_after(1,{8,9}));REQUIRE(c.consist()==std::vector<int>{1,8,9});""",
         "Validated car blocks are coupled atomically; contiguous detach and reversal operate through XOR-link boundary rewrites.", "consist-block-couple-detach-reverse"),
)
