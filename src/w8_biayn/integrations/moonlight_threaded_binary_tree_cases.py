"""Independent contracts and C++ fragments for threaded-tree remediation."""

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
    Case("threaded-appointment-book", "threaded-appointment-book", "AppointmentBook", """
  bool reserve(int minute); bool release(int minute);
  std::optional<int> before(int minute) const; std::optional<int> at_or_after(int minute) const;
  std::vector<int> schedule() const;""", "", """
bool AppointmentBook::reserve(int){return false;} bool AppointmentBook::release(int){return false;}
std::optional<int> AppointmentBook::before(int)const{return std::nullopt;} std::optional<int> AppointmentBook::at_or_after(int)const{return std::nullopt;}
std::vector<int> AppointmentBook::schedule()const{return{};}""", """
bool AppointmentBook::reserve(int k){return k>0&&insert_node(new Node{k,k,0,0,1,false,nullptr,nullptr,nullptr,true,true});}
bool AppointmentBook::release(int k){Node*n=find_order(k);if(!n)return false;erase_node(n);return true;}
std::optional<int> AppointmentBook::before(int k)const{Node*n=lower_bound(k);n=n?predecessor(n):maximum();return n?std::optional<int>(n->id):std::nullopt;}
std::optional<int> AppointmentBook::at_or_after(int k)const{Node*n=lower_bound(k);return n?std::optional<int>(n->id):std::nullopt;}
std::vector<int> AppointmentBook::schedule()const{std::vector<int>v;for(Node*n=minimum();n;n=successor(n))v.push_back(n->id);return v;}""", """
AppointmentBook b; REQUIRE(b.reserve(30)); REQUIRE(b.reserve(10)); REQUIRE(b.reserve(50)); REQUIRE(b.before(30)==10); REQUIRE(b.at_or_after(31)==50);""", """
AppointmentBook b; for(int k:{40,20,60,10,30,50,70})REQUIRE(b.reserve(k)); REQUIRE(b.release(40)); REQUIRE(b.release(10)); REQUIRE(b.schedule()==std::vector<int>{20,30,50,60,70}); REQUIRE(b.audit_for_test().valid);""",
         "Maintain unique positive appointment minutes with direct double-threaded insertion and deletion; predecessor is strict and lower bound is inclusive.", "direct-double-threaded-mutation"),
    Case("threaded-auction-bids", "threaded-bid-multiplicity-index", "BidMultiplicityIndex", """
  bool place(int level); bool withdraw(int level); std::size_t count(int level) const;
  std::optional<int> next_level(int level) const; std::vector<std::pair<int,std::size_t>> levels() const;""", "", """
bool BidMultiplicityIndex::place(int){return false;} bool BidMultiplicityIndex::withdraw(int){return false;} std::size_t BidMultiplicityIndex::count(int)const{return 0;}
std::optional<int> BidMultiplicityIndex::next_level(int)const{return std::nullopt;} std::vector<std::pair<int,std::size_t>> BidMultiplicityIndex::levels()const{return{};}""", """
bool BidMultiplicityIndex::place(int k){if(k<=0)return false;if(Node*n=find_order(k)){++n->count;return true;}return insert_node(new Node{k,k,0,0,1,false,nullptr,nullptr,nullptr,true,true});}
bool BidMultiplicityIndex::withdraw(int k){Node*n=find_order(k);if(!n)return false;if(--n->count==0)erase_node(n);return true;}std::size_t BidMultiplicityIndex::count(int k)const{Node*n=find_order(k);return n?n->count:0;}
std::optional<int> BidMultiplicityIndex::next_level(int k)const{Node*n=lower_bound(static_cast<long long>(k)+1);return n?std::optional<int>(n->id):std::nullopt;}
std::vector<std::pair<int,std::size_t>> BidMultiplicityIndex::levels()const{std::vector<std::pair<int,std::size_t>>v;for(Node*n=minimum();n;n=successor(n))v.push_back({n->id,n->count});return v;}""", """
BidMultiplicityIndex b; REQUIRE(b.place(10)); REQUIRE(b.place(10)); REQUIRE(b.place(20)); REQUIRE(b.count(10)==2); REQUIRE(b.next_level(10)==20);""", """
BidMultiplicityIndex b; for(int k:{20,10,30,20})REQUIRE(b.place(k)); REQUIRE(b.withdraw(20)); REQUIRE(b.count(20)==1); REQUIRE(b.withdraw(20)); REQUIRE(b.levels()==std::vector<std::pair<int,std::size_t>>{{10,1},{30,1}}); REQUIRE(b.audit_for_test().valid);""",
         "Store one threaded node per positive bid level and a multiplicity counter; withdrawal deletes the node only when its counter reaches zero.", "multiplicity-nodes-and-distinct-level-threads"),
    Case("threaded-audit-browser", "threaded-audit-tombstone-index", "AuditTombstoneIndex", """
  bool append(int record); bool redact(int record); bool restore(int record);
  std::optional<int> next_live(int record) const; std::vector<int> live_records() const; std::size_t compact();""", "", """
bool AuditTombstoneIndex::append(int){return false;}bool AuditTombstoneIndex::redact(int){return false;}bool AuditTombstoneIndex::restore(int){return false;}
std::optional<int> AuditTombstoneIndex::next_live(int)const{return std::nullopt;}std::vector<int> AuditTombstoneIndex::live_records()const{return{};}std::size_t AuditTombstoneIndex::compact(){return 0;}""", """
bool AuditTombstoneIndex::append(int k){return k>0&&insert_node(new Node{k,k,0,0,1,false,nullptr,nullptr,nullptr,true,true});}bool AuditTombstoneIndex::redact(int k){Node*n=find_order(k);if(!n||n->flag)return false;n->flag=true;return true;}bool AuditTombstoneIndex::restore(int k){Node*n=find_order(k);if(!n||!n->flag)return false;n->flag=false;return true;}
std::optional<int> AuditTombstoneIndex::next_live(int k)const{for(Node*n=lower_bound(static_cast<long long>(k)+1);n;n=successor(n))if(!n->flag)return n->id;return std::nullopt;}std::vector<int> AuditTombstoneIndex::live_records()const{std::vector<int>v;for(Node*n=minimum();n;n=successor(n))if(!n->flag)v.push_back(n->id);return v;}
std::size_t AuditTombstoneIndex::compact(){std::size_t count=0;for(Node*n=minimum();n;){long long order=n->order;if(n->flag){erase_node(n);++count;}n=lower_bound(order+1);}return count;}""", """
AuditTombstoneIndex a; for(int k:{2,1,3})REQUIRE(a.append(k)); REQUIRE(a.redact(2)); REQUIRE(a.live_records()==std::vector<int>{1,3}); REQUIRE(a.restore(2));""", """
AuditTombstoneIndex a; for(int k:{4,2,6,1,3,5,7})REQUIRE(a.append(k)); REQUIRE(a.redact(2)); REQUIRE(a.redact(6)); REQUIRE(a.next_live(1)==3); REQUIRE(a.compact()==2); REQUIRE(a.live_records()==std::vector<int>{1,3,4,5,7}); REQUIRE(a.audit_for_test().valid);""",
         "Keep redacted records as tombstones during navigation, restore them in place, and physically delete all tombstones only during compaction.", "lazy-tombstones-and-threaded-compaction"),
    Case("threaded-calendar-navigator", "threaded-calendar-cursor", "CalendarCursor", """
  bool add(int event); bool cancel(int event); bool seek(int event);
  std::optional<int> next(); std::optional<int> previous(); std::optional<int> current() const;""", "Node* current_ = nullptr;", """
bool CalendarCursor::add(int){return false;}bool CalendarCursor::cancel(int){return false;}bool CalendarCursor::seek(int){return false;}std::optional<int> CalendarCursor::next(){return std::nullopt;}std::optional<int> CalendarCursor::previous(){return std::nullopt;}std::optional<int> CalendarCursor::current()const{return std::nullopt;}""", """
bool CalendarCursor::add(int k){return k>0&&insert_node(new Node{k,k,0,0,1,false,nullptr,nullptr,nullptr,true,true});}bool CalendarCursor::seek(int k){Node*n=find_order(k);if(!n)return false;current_=n;return true;}bool CalendarCursor::cancel(int k){Node*n=find_order(k);if(!n)return false;int wanted=0;if(n==current_){Node*fallback=successor(n)?successor(n):predecessor(n);wanted=fallback?fallback->id:0;}else wanted=current_?current_->id:0;erase_node(n);current_=wanted?find_order(wanted):nullptr;return true;}
std::optional<int> CalendarCursor::next(){Node*n=current_?successor(current_):minimum();if(!n)return std::nullopt;current_=n;return n->id;}std::optional<int> CalendarCursor::previous(){Node*n=current_?predecessor(current_):maximum();if(!n)return std::nullopt;current_=n;return n->id;}std::optional<int> CalendarCursor::current()const{return current_?std::optional<int>(current_->id):std::nullopt;}""", """
CalendarCursor c; for(int k:{20,10,30})REQUIRE(c.add(k)); REQUIRE(c.next()==10); REQUIRE(c.next()==20); REQUIRE(c.previous()==10);""", """
CalendarCursor c; for(int k:{40,20,60,10,30})REQUIRE(c.add(k)); REQUIRE(c.seek(20)); REQUIRE(c.cancel(20)); REQUIRE(c.current()==30); REQUIRE(c.previous()==10); REQUIRE_FALSE(c.previous()); REQUIRE(c.current()==10); REQUIRE(c.audit_for_test().valid);""",
         "Maintain a stateful cursor over inorder threads; failed boundary movement is atomic and deleting the cursor selects successor then predecessor.", "stateful-thread-cursor-with-delete-fallback"),
    Case("threaded-cargo-manifest", "threaded-cargo-interval-tree", "CargoIntervalTree", """
  bool add(int cargo_id,int first,int last); bool remove(int cargo_id);
  std::vector<int> overlapping(int first,int last) const; std::vector<int> cargo_order() const;""", "", """
bool CargoIntervalTree::add(int,int,int){return false;}bool CargoIntervalTree::remove(int){return false;}std::vector<int> CargoIntervalTree::overlapping(int,int)const{return{};}std::vector<int> CargoIntervalTree::cargo_order()const{return{};}""", """
bool CargoIntervalTree::add(int id,int first,int last){if(id<=0||first<0||first>last||find_id(id))return false;long long order=static_cast<long long>(first)*1000000+id;return insert_node(new Node{order,id,first,last,1,false,nullptr,nullptr,nullptr,true,true});}bool CargoIntervalTree::remove(int id){Node*n=find_id(id);if(!n)return false;erase_node(n);return true;}
std::vector<int> CargoIntervalTree::overlapping(int first,int last)const{std::vector<int>v;if(first>last)return v;for(Node*n=minimum();n;n=successor(n))if(n->value<=last&&n->aux>=first)v.push_back(n->id);return v;}std::vector<int> CargoIntervalTree::cargo_order()const{std::vector<int>v;for(Node*n=minimum();n;n=successor(n))v.push_back(n->id);return v;}""", """
CargoIntervalTree t; REQUIRE(t.add(1,10,20)); REQUIRE(t.add(2,30,40)); REQUIRE(t.add(3,18,35)); REQUIRE(t.overlapping(19,31)==std::vector<int>{1,3,2});""", """
CargoIntervalTree t; REQUIRE_FALSE(t.add(1,5,4)); for(auto x:std::vector<std::tuple<int,int,int>>{{1,5,8},{2,1,2},{3,7,9},{4,7,7}})REQUIRE(t.add(std::get<0>(x),std::get<1>(x),std::get<2>(x))); REQUIRE(t.cargo_order()==std::vector<int>{2,1,3,4}); REQUIRE(t.remove(3)); REQUIRE(t.overlapping(7,7)==std::vector<int>{1,4}); REQUIRE(t.audit_for_test().valid);""",
         "Order closed cargo intervals by start then ID and answer deterministic overlap scans through inorder successor threads.", "interval-payload-threaded-overlap-scan"),
    Case("threaded-document-anchors", "threaded-anchor-rank-tree", "AnchorRankTree", """
  bool add(int offset); bool remove(int offset); std::optional<int> select(std::size_t rank) const;
  std::size_t rank(int offset) const; std::vector<int> anchors() const;""", "", """
bool AnchorRankTree::add(int){return false;}bool AnchorRankTree::remove(int){return false;}std::optional<int> AnchorRankTree::select(std::size_t)const{return std::nullopt;}std::size_t AnchorRankTree::rank(int)const{return 0;}std::vector<int> AnchorRankTree::anchors()const{return{};}""", """
bool AnchorRankTree::add(int k){return k>0&&insert_node(new Node{k,k,0,0,1,false,nullptr,nullptr,nullptr,true,true});}bool AnchorRankTree::remove(int k){Node*n=find_order(k);if(!n)return false;erase_node(n);return true;}std::optional<int> AnchorRankTree::select(std::size_t r)const{Node*n=minimum();while(n&&r--!=0)n=successor(n);return n?std::optional<int>(n->id):std::nullopt;}std::size_t AnchorRankTree::rank(int k)const{std::size_t r=0;for(Node*n=minimum();n&&n->id<k;n=successor(n))++r;return r;}std::vector<int> AnchorRankTree::anchors()const{std::vector<int>v;for(Node*n=minimum();n;n=successor(n))v.push_back(n->id);return v;}""", """
AnchorRankTree t; for(int k:{30,10,20})REQUIRE(t.add(k)); REQUIRE(t.select(1)==20); REQUIRE(t.rank(25)==2);""", """
AnchorRankTree t; for(int k:{40,20,60,10,30,50,70})REQUIRE(t.add(k)); REQUIRE(t.select(6)==70); REQUIRE_FALSE(t.select(7)); REQUIRE(t.remove(40)); REQUIRE(t.rank(60)==4); REQUIRE(t.audit_for_test().valid);""",
         "Expose zero-based select and strict rank as thread-walk operations over a directly mutable ordered anchor tree.", "thread-rank-and-select-walk"),
    Case("threaded-fare-tiers", "threaded-fare-prefix-tree", "FarePrefixTree", """
  bool set(int tier,int fare); bool erase(int tier); std::optional<long long> prefix_total(int tier) const;
  std::optional<int> lower_bound_total(long long target) const;""", "", """
bool FarePrefixTree::set(int,int){return false;}bool FarePrefixTree::erase(int){return false;}std::optional<long long> FarePrefixTree::prefix_total(int)const{return std::nullopt;}std::optional<int> FarePrefixTree::lower_bound_total(long long)const{return std::nullopt;}""", """
bool FarePrefixTree::set(int tier,int fare){if(tier<=0||fare<0)return false;if(Node*n=find_order(tier)){n->value=fare;return true;}return insert_node(new Node{tier,tier,fare,0,1,false,nullptr,nullptr,nullptr,true,true});}bool FarePrefixTree::erase(int tier){Node*n=find_order(tier);if(!n)return false;erase_node(n);return true;}std::optional<long long> FarePrefixTree::prefix_total(int tier)const{long long total=0;bool any=false;for(Node*n=minimum();n&&n->id<=tier;n=successor(n)){total+=n->value;any=true;}return any?std::optional<long long>(total):std::nullopt;}std::optional<int> FarePrefixTree::lower_bound_total(long long target)const{if(target<=0)return std::nullopt;long long total=0;for(Node*n=minimum();n;n=successor(n)){total+=n->value;if(total>=target)return n->id;}return std::nullopt;}""", """
FarePrefixTree t; REQUIRE(t.set(1,5)); REQUIRE(t.set(3,7)); REQUIRE(t.set(2,4)); REQUIRE(t.prefix_total(2)==9); REQUIRE(t.lower_bound_total(10)==3);""", """
FarePrefixTree t; REQUIRE_FALSE(t.set(0,2)); for(auto p:std::vector<std::pair<int,int>>{{4,2},{2,3},{6,5}})REQUIRE(t.set(p.first,p.second)); REQUIRE(t.set(2,7)); REQUIRE(t.prefix_total(5)==9); REQUIRE(t.erase(4)); REQUIRE(t.lower_bound_total(8)==6); REQUIRE(t.audit_for_test().valid);""",
         "Store nonnegative fare payloads on threaded tier nodes and compute prefix totals plus the first tier reaching a target by successor walk.", "threaded-prefix-aggregate-selection"),
    Case("threaded-file-version-browser", "threaded-version-access-index", "VersionAccessIndex", """
  bool retain(int version); bool discard(int version); bool access(int version);
  std::optional<int> most_accessed() const; std::vector<std::pair<int,std::size_t>> versions() const;""", "", """
bool VersionAccessIndex::retain(int){return false;}bool VersionAccessIndex::discard(int){return false;}bool VersionAccessIndex::access(int){return false;}std::optional<int> VersionAccessIndex::most_accessed()const{return std::nullopt;}std::vector<std::pair<int,std::size_t>> VersionAccessIndex::versions()const{return{};}""", """
bool VersionAccessIndex::retain(int k){return k>0&&insert_node(new Node{k,k,0,0,0,false,nullptr,nullptr,nullptr,true,true});}bool VersionAccessIndex::discard(int k){Node*n=find_order(k);if(!n)return false;erase_node(n);return true;}bool VersionAccessIndex::access(int k){Node*n=find_order(k);if(!n||n->count==std::numeric_limits<std::size_t>::max())return false;++n->count;return true;}std::optional<int> VersionAccessIndex::most_accessed()const{Node*best=nullptr;for(Node*n=minimum();n;n=successor(n))if(!best||n->count>best->count)best=n;return best?std::optional<int>(best->id):std::nullopt;}std::vector<std::pair<int,std::size_t>> VersionAccessIndex::versions()const{std::vector<std::pair<int,std::size_t>>v;for(Node*n=minimum();n;n=successor(n))v.push_back({n->id,n->count});return v;}""", """
VersionAccessIndex i; for(int k:{3,1,2})REQUIRE(i.retain(k)); REQUIRE(i.access(2)); REQUIRE(i.access(2)); REQUIRE(i.most_accessed()==2);""", """
VersionAccessIndex i; for(int k:{4,2,6})REQUIRE(i.retain(k)); REQUIRE(i.access(6)); REQUIRE(i.access(2)); REQUIRE(i.most_accessed()==2); REQUIRE(i.discard(2)); REQUIRE(i.most_accessed()==6); REQUIRE(i.audit_for_test().valid);""",
         "Track per-version access counts in nodes and scan threads for the highest count, breaking ties by the smaller version.", "per-node-access-count-and-threaded-tie-scan"),
    Case("threaded-flight-departures", "threaded-departure-day-index", "DepartureDayIndex", """
  bool schedule(int minute,int gate); bool cancel(int minute); std::optional<int> next_gate(int minute,int gate) const;
  std::vector<int> departures() const;""", "", """
bool DepartureDayIndex::schedule(int,int){return false;}bool DepartureDayIndex::cancel(int){return false;}std::optional<int> DepartureDayIndex::next_gate(int,int)const{return std::nullopt;}std::vector<int> DepartureDayIndex::departures()const{return{};}""", """
bool DepartureDayIndex::schedule(int minute,int gate){return minute>=0&&minute<1440&&gate>0&&insert_node(new Node{minute,minute,gate,0,1,false,nullptr,nullptr,nullptr,true,true});}bool DepartureDayIndex::cancel(int minute){Node*n=find_order(minute);if(!n)return false;erase_node(n);return true;}std::optional<int> DepartureDayIndex::next_gate(int minute,int gate)const{for(Node*n=lower_bound(minute);n;n=successor(n))if(n->value==gate)return n->id;return std::nullopt;}std::vector<int> DepartureDayIndex::departures()const{std::vector<int>v;for(Node*n=minimum();n;n=successor(n))v.push_back(n->id);return v;}""", """
DepartureDayIndex d; REQUIRE(d.schedule(100,2)); REQUIRE(d.schedule(50,1)); REQUIRE(d.schedule(150,1)); REQUIRE(d.next_gate(60,1)==150);""", """
DepartureDayIndex d; REQUIRE_FALSE(d.schedule(1440,1)); for(auto p:std::vector<std::pair<int,int>>{{400,2},{200,1},{600,2},{500,1}})REQUIRE(d.schedule(p.first,p.second)); REQUIRE(d.next_gate(401,2)==600); REQUIRE_FALSE(d.next_gate(601,2)); REQUIRE(d.cancel(400)); REQUIRE(d.audit_for_test().valid);""",
         "Index one departure per minute and scan successor threads at-or-after a cursor until a requested gate payload is found.", "time-ordered-payload-filtered-thread-scan"),
    Case("threaded-inventory-catalog", "threaded-catalog-stock-index", "CatalogStockIndex", """
  bool add(int sku,int stock); bool restock(int sku,int amount); bool consume(int sku,int amount);
  bool erase_empty(int sku); std::optional<int> next_in_stock(int sku) const;""", "", """
bool CatalogStockIndex::add(int,int){return false;}bool CatalogStockIndex::restock(int,int){return false;}bool CatalogStockIndex::consume(int,int){return false;}bool CatalogStockIndex::erase_empty(int){return false;}std::optional<int> CatalogStockIndex::next_in_stock(int)const{return std::nullopt;}""", """
bool CatalogStockIndex::add(int sku,int stock){return sku>0&&stock>=0&&insert_node(new Node{sku,sku,stock,0,1,false,nullptr,nullptr,nullptr,true,true});}bool CatalogStockIndex::restock(int sku,int amount){Node*n=find_order(sku);if(!n||amount<=0||n->value>std::numeric_limits<int>::max()-amount)return false;n->value+=amount;return true;}bool CatalogStockIndex::consume(int sku,int amount){Node*n=find_order(sku);if(!n||amount<=0||n->value<amount)return false;n->value-=amount;return true;}bool CatalogStockIndex::erase_empty(int sku){Node*n=find_order(sku);if(!n||n->value!=0)return false;erase_node(n);return true;}std::optional<int> CatalogStockIndex::next_in_stock(int sku)const{for(Node*n=lower_bound(sku);n;n=successor(n))if(n->value>0)return n->id;return std::nullopt;}""", """
CatalogStockIndex c; REQUIRE(c.add(20,0)); REQUIRE(c.add(10,2)); REQUIRE(c.add(30,4)); REQUIRE(c.next_in_stock(15)==30); REQUIRE(c.restock(20,1)); REQUIRE(c.next_in_stock(15)==20);""", """
CatalogStockIndex c; for(auto p:std::vector<std::pair<int,int>>{{40,1},{20,2},{60,0}})REQUIRE(c.add(p.first,p.second)); REQUIRE_FALSE(c.consume(20,3)); REQUIRE(c.consume(20,2)); REQUIRE(c.erase_empty(20)); REQUIRE(c.restock(60,5)); REQUIRE(c.next_in_stock(21)==40); REQUIRE(c.audit_for_test().valid);""",
         "Maintain stock payload transitions and find the first at-or-after SKU with positive stock through inorder successor threads.", "stock-payload-transitions-and-filtered-successor"),
    Case("threaded-library-shelves", "threaded-shelf-bulk-builder", "ShelfBulkBuilder", """
  bool rebuild(const std::vector<int>& call_numbers); std::vector<int> forward() const;
  std::vector<int> reverse() const; int height() const;""", "", """
bool ShelfBulkBuilder::rebuild(const std::vector<int>&){return false;}std::vector<int> ShelfBulkBuilder::forward()const{return{};}std::vector<int> ShelfBulkBuilder::reverse()const{return{};}int ShelfBulkBuilder::height()const{return 0;}""", """
bool ShelfBulkBuilder::rebuild(const std::vector<int>&v){for(std::size_t i=0;i<v.size();++i)if(v[i]<=0||(i&&v[i-1]>=v[i]))return false;clear_all();std::function<void(std::size_t,std::size_t)>add=[&](std::size_t a,std::size_t b){if(a>=b)return;std::size_t m=a+(b-a)/2;insert_node(new Node{v[m],v[m],0,0,1,false,nullptr,nullptr,nullptr,true,true});add(a,m);add(m+1,b);};add(0,v.size());return true;}std::vector<int> ShelfBulkBuilder::forward()const{std::vector<int>v;for(Node*n=minimum();n;n=successor(n))v.push_back(n->id);return v;}std::vector<int> ShelfBulkBuilder::reverse()const{std::vector<int>v;for(Node*n=maximum();n;n=predecessor(n))v.push_back(n->id);return v;}int ShelfBulkBuilder::height()const{std::function<int(Node*)>h=[&](Node*n){if(!n)return 0;return 1+std::max(n->left_thread?0:h(n->left),n->right_thread?0:h(n->right));};return h(root_);}""", """
ShelfBulkBuilder b; REQUIRE(b.rebuild({1,2,3,4,5,6,7})); REQUIRE(b.height()==3); REQUIRE(b.reverse()==std::vector<int>{7,6,5,4,3,2,1});""", """
ShelfBulkBuilder b; REQUIRE(b.rebuild({2,4,6})); REQUIRE_FALSE(b.rebuild({2,2,3})); REQUIRE(b.forward()==std::vector<int>{2,4,6}); REQUIRE(b.rebuild({})); REQUIRE(b.height()==0); REQUIRE(b.audit_for_test().valid);""",
         "Atomically replace the tree from strictly increasing input using midpoint-first balanced construction, then expose both thread directions.", "balanced-bulk-build-and-thread-overlay"),
    Case("threaded-medication-times", "threaded-dose-range-pruner", "DoseRangePruner", """
  bool schedule(int minute); std::size_t cancel_between(int first,int last);
  std::vector<int> doses() const; std::vector<int> reverse_doses() const;""", "", """
bool DoseRangePruner::schedule(int){return false;}std::size_t DoseRangePruner::cancel_between(int,int){return 0;}std::vector<int> DoseRangePruner::doses()const{return{};}std::vector<int> DoseRangePruner::reverse_doses()const{return{};}""", """
bool DoseRangePruner::schedule(int k){return k>=0&&k<1440&&insert_node(new Node{k,k,0,0,1,false,nullptr,nullptr,nullptr,true,true});}std::size_t DoseRangePruner::cancel_between(int first,int last){if(first>last)return 0;std::size_t count=0;for(Node*n=lower_bound(first);n&&n->id<=last;){long long order=n->order;erase_node(n);++count;n=lower_bound(order+1);}return count;}std::vector<int> DoseRangePruner::doses()const{std::vector<int>v;for(Node*n=minimum();n;n=successor(n))v.push_back(n->id);return v;}std::vector<int> DoseRangePruner::reverse_doses()const{std::vector<int>v;for(Node*n=maximum();n;n=predecessor(n))v.push_back(n->id);return v;}""", """
DoseRangePruner p; for(int k:{10,20,30,40})REQUIRE(p.schedule(k)); REQUIRE(p.cancel_between(15,35)==2); REQUIRE(p.doses()==std::vector<int>{10,40});""", """
DoseRangePruner p; for(int k:{400,200,600,100,300,500,700})REQUIRE(p.schedule(k)); REQUIRE(p.cancel_between(200,600)==5); REQUIRE(p.reverse_doses()==std::vector<int>{700,100}); REQUIRE(p.cancel_between(9,1)==0); REQUIRE(p.audit_for_test().valid);""",
         "Delete every dose in an inclusive time range by saving and following successor threads while each node is directly erased.", "successor-driven-direct-range-erasure"),
    Case("threaded-museum-waypoints", "threaded-waypoint-split-tree", "WaypointSplitTree", """
  bool add(int waypoint); std::pair<std::vector<int>,std::vector<int>> split_snapshot(int pivot) const;
  bool erase_side(int pivot,bool erase_lower); std::vector<int> tour() const;""", "", """
bool WaypointSplitTree::add(int){return false;}std::pair<std::vector<int>,std::vector<int>> WaypointSplitTree::split_snapshot(int)const{return{};}bool WaypointSplitTree::erase_side(int,bool){return false;}std::vector<int> WaypointSplitTree::tour()const{return{};}""", """
bool WaypointSplitTree::add(int k){return k>0&&insert_node(new Node{k,k,0,0,1,false,nullptr,nullptr,nullptr,true,true});}std::pair<std::vector<int>,std::vector<int>> WaypointSplitTree::split_snapshot(int p)const{std::pair<std::vector<int>,std::vector<int>>out;for(Node*n=minimum();n;n=successor(n))(n->id<p?out.first:out.second).push_back(n->id);return out;}bool WaypointSplitTree::erase_side(int p,bool lower){std::vector<int>ids;for(Node*n=minimum();n;n=successor(n))if((n->id<p)==lower)ids.push_back(n->id);for(int id:ids)erase_node(find_order(id));return !ids.empty();}std::vector<int> WaypointSplitTree::tour()const{std::vector<int>v;for(Node*n=minimum();n;n=successor(n))v.push_back(n->id);return v;}""", """
WaypointSplitTree t; for(int k:{4,2,6,1,3,5})REQUIRE(t.add(k)); auto s=t.split_snapshot(4); REQUIRE(s.first==std::vector<int>{1,2,3}); REQUIRE(s.second==std::vector<int>{4,5,6});""", """
WaypointSplitTree t; for(int k:{40,20,60,10,30,50,70})REQUIRE(t.add(k)); REQUIRE(t.erase_side(40,false)); REQUIRE(t.tour()==std::vector<int>{10,20,30}); REQUIRE_FALSE(t.erase_side(40,false)); REQUIRE(t.audit_for_test().valid);""",
         "Partition a threaded tour at a pivot and optionally erase exactly one partition while preserving the other side's threads.", "thread-boundary-pivot-partition"),
    Case("threaded-network-ports", "threaded-port-gap-tree", "PortGapTree", """
  bool reserve(int port); bool release(int port); std::optional<int> first_free(int first,int last) const;
  std::vector<std::pair<int,int>> reserved_runs() const;""", "", """
bool PortGapTree::reserve(int){return false;}bool PortGapTree::release(int){return false;}std::optional<int> PortGapTree::first_free(int,int)const{return std::nullopt;}std::vector<std::pair<int,int>> PortGapTree::reserved_runs()const{return{};}""", """
bool PortGapTree::reserve(int p){return p>=1&&p<=65535&&insert_node(new Node{p,p,0,0,1,false,nullptr,nullptr,nullptr,true,true});}bool PortGapTree::release(int p){Node*n=find_order(p);if(!n)return false;erase_node(n);return true;}std::optional<int> PortGapTree::first_free(int first,int last)const{if(first<1||last>65535||first>last)return std::nullopt;int candidate=first;for(Node*n=lower_bound(first);n&&n->id<=last;n=successor(n)){if(n->id>candidate)return candidate;if(n->id==candidate)++candidate;}return candidate<=last?std::optional<int>(candidate):std::nullopt;}std::vector<std::pair<int,int>> PortGapTree::reserved_runs()const{std::vector<std::pair<int,int>>v;for(Node*n=minimum();n;){int a=n->id,b=a;Node*next=successor(n);while(next&&next->id==b+1){b=next->id;next=successor(next);}v.push_back({a,b});n=next;}return v;}""", """
PortGapTree t; for(int p:{3,1,2,5})REQUIRE(t.reserve(p)); REQUIRE(t.first_free(1,5)==4); REQUIRE(t.reserved_runs()==std::vector<std::pair<int,int>>{{1,3},{5,5}});""", """
PortGapTree t; for(int p:{10,11,12,14,20})REQUIRE(t.reserve(p)); REQUIRE_FALSE(t.first_free(0,2)); REQUIRE(t.first_free(10,14)==13); REQUIRE(t.release(11)); REQUIRE(t.first_free(10,12)==11); REQUIRE(t.audit_for_test().valid);""",
         "Detect the lowest free port and coalesce consecutive reserved runs solely by walking neighboring inorder threads.", "thread-gap-and-run-detection"),
    Case("threaded-parking-space-guide", "threaded-space-state-tree", "SpaceStateTree", """
  bool define(int space); bool occupy(int space); bool vacate(int space);
  std::optional<int> next_free(int space) const; std::vector<int> free_spaces() const;""", "", """
bool SpaceStateTree::define(int){return false;}bool SpaceStateTree::occupy(int){return false;}bool SpaceStateTree::vacate(int){return false;}std::optional<int> SpaceStateTree::next_free(int)const{return std::nullopt;}std::vector<int> SpaceStateTree::free_spaces()const{return{};}""", """
bool SpaceStateTree::define(int k){return k>0&&insert_node(new Node{k,k,0,0,1,false,nullptr,nullptr,nullptr,true,true});}bool SpaceStateTree::occupy(int k){Node*n=find_order(k);if(!n||n->flag)return false;n->flag=true;return true;}bool SpaceStateTree::vacate(int k){Node*n=find_order(k);if(!n||!n->flag)return false;n->flag=false;return true;}std::optional<int> SpaceStateTree::next_free(int k)const{for(Node*n=lower_bound(k);n;n=successor(n))if(!n->flag)return n->id;return std::nullopt;}std::vector<int> SpaceStateTree::free_spaces()const{std::vector<int>v;for(Node*n=minimum();n;n=successor(n))if(!n->flag)v.push_back(n->id);return v;}""", """
SpaceStateTree t; for(int k:{2,1,3})REQUIRE(t.define(k)); REQUIRE(t.occupy(1)); REQUIRE(t.occupy(2)); REQUIRE(t.next_free(1)==3);""", """
SpaceStateTree t; for(int k:{40,20,60,10})REQUIRE(t.define(k)); REQUIRE(t.occupy(20)); REQUIRE_FALSE(t.occupy(20)); REQUIRE(t.vacate(20)); REQUIRE(t.next_free(15)==20); REQUIRE(t.free_spaces()==std::vector<int>{10,20,40,60}); REQUIRE(t.audit_for_test().valid);""",
         "Keep occupancy as node payload and find the inclusive next free space by filtering the successor-thread walk.", "payload-state-filtered-thread-scan"),
    Case("threaded-route-stations", "threaded-station-rekey-tree", "StationRekeyTree", """
  bool open(int station); bool close(int station); bool rekey(int old_station,int new_station);
  std::vector<int> stations() const;""", "", """
bool StationRekeyTree::open(int){return false;}bool StationRekeyTree::close(int){return false;}bool StationRekeyTree::rekey(int,int){return false;}std::vector<int> StationRekeyTree::stations()const{return{};}""", """
bool StationRekeyTree::open(int k){return k>0&&insert_node(new Node{k,k,0,0,1,false,nullptr,nullptr,nullptr,true,true});}bool StationRekeyTree::close(int k){Node*n=find_order(k);if(!n)return false;erase_node(n);return true;}bool StationRekeyTree::rekey(int old_k,int new_k){Node*n=find_order(old_k);if(!n||new_k<=0||(old_k!=new_k&&find_order(new_k)))return false;if(old_k==new_k)return true;erase_node(n);return insert_node(new Node{new_k,new_k,0,0,1,false,nullptr,nullptr,nullptr,true,true});}std::vector<int> StationRekeyTree::stations()const{std::vector<int>v;for(Node*n=minimum();n;n=successor(n))v.push_back(n->id);return v;}""", """
StationRekeyTree t; for(int k:{20,10,30})REQUIRE(t.open(k)); REQUIRE(t.rekey(20,25)); REQUIRE(t.stations()==std::vector<int>{10,25,30});""", """
StationRekeyTree t; for(int k:{40,20,60,10,30})REQUIRE(t.open(k)); REQUIRE_FALSE(t.rekey(20,30)); REQUIRE(t.rekey(40,50)); REQUIRE(t.close(10)); REQUIRE(t.stations()==std::vector<int>{20,30,50,60}); REQUIRE(t.audit_for_test().valid);""",
         "Validate then replace a station key through direct erase and insert so both neighboring thread pairs are repaired atomically.", "atomic-key-replacement-with-thread-repair"),
    Case("threaded-score-history", "threaded-score-thread-auditor", "ScoreThreadAuditor", """
  bool add(int score); bool corrupt_successor_for_test(int score);
  std::optional<int> first_broken_thread() const; bool repair_threads(); std::vector<int> scores() const;""", "", """
bool ScoreThreadAuditor::add(int){return false;}bool ScoreThreadAuditor::corrupt_successor_for_test(int){return false;}std::optional<int> ScoreThreadAuditor::first_broken_thread()const{return std::nullopt;}bool ScoreThreadAuditor::repair_threads(){return false;}std::vector<int> ScoreThreadAuditor::scores()const{return{};}""", """
bool ScoreThreadAuditor::add(int k){return k>0&&insert_node(new Node{k,k,0,0,1,false,nullptr,nullptr,nullptr,true,true});}bool ScoreThreadAuditor::corrupt_successor_for_test(int k){Node*n=find_order(k);if(!n||!n->right_thread)return false;n->right=nullptr;return true;}std::optional<int> ScoreThreadAuditor::first_broken_thread()const{std::vector<Node*>v;child_inorder(root_,v);for(std::size_t i=0;i<v.size();++i){Node*pred=i?v[i-1]:nullptr;Node*succ=i+1<v.size()?v[i+1]:nullptr;if((v[i]->left_thread&&v[i]->left!=pred)||(v[i]->right_thread&&v[i]->right!=succ))return v[i]->id;}return std::nullopt;}bool ScoreThreadAuditor::repair_threads(){std::vector<Node*>v;child_inorder(root_,v);for(std::size_t i=0;i<v.size();++i){if(v[i]->left_thread)v[i]->left=i?v[i-1]:nullptr;if(v[i]->right_thread)v[i]->right=i+1<v.size()?v[i+1]:nullptr;}return true;}std::vector<int> ScoreThreadAuditor::scores()const{std::vector<Node*>nodes;child_inorder(root_,nodes);std::vector<int>v;for(Node*n:nodes)v.push_back(n->id);return v;}""", """
ScoreThreadAuditor a; for(int k:{20,10,30})REQUIRE(a.add(k)); REQUIRE(a.corrupt_successor_for_test(10)); REQUIRE(a.first_broken_thread()==10); REQUIRE(a.repair_threads()); REQUIRE_FALSE(a.first_broken_thread());""", """
ScoreThreadAuditor a; for(int k:{40,20,60,10,30,50,70})REQUIRE(a.add(k)); REQUIRE(a.corrupt_successor_for_test(30)); REQUIRE(a.first_broken_thread()==30); auto before=a.scores(); REQUIRE(a.repair_threads()); REQUIRE(a.scores()==before); REQUIRE(a.audit_for_test().valid);""",
         "Independently derive child-edge inorder, identify the first predecessor/successor thread mismatch, and repair only thread edges.", "independent-child-inorder-thread-audit-and-repair"),
    Case("threaded-sensor-thresholds", "threaded-threshold-hysteresis-tree", "ThresholdHysteresisTree", """
  bool add(int threshold,int width); bool erase(int threshold); std::optional<int> transition(int reading);
  std::optional<int> active_band() const; std::vector<int> thresholds() const;""", "Node* active_ = nullptr;", """
bool ThresholdHysteresisTree::add(int,int){return false;}bool ThresholdHysteresisTree::erase(int){return false;}std::optional<int> ThresholdHysteresisTree::transition(int){return std::nullopt;}std::optional<int> ThresholdHysteresisTree::active_band()const{return std::nullopt;}std::vector<int> ThresholdHysteresisTree::thresholds()const{return{};}""", """
bool ThresholdHysteresisTree::add(int k,int width){return k>0&&width>=0&&insert_node(new Node{k,k,width,0,1,false,nullptr,nullptr,nullptr,true,true});}bool ThresholdHysteresisTree::erase(int k){Node*n=find_order(k);if(!n)return false;int active_id=active_&&active_!=n?active_->id:0;erase_node(n);active_=active_id?find_order(active_id):nullptr;return true;}std::optional<int> ThresholdHysteresisTree::transition(int reading){if(active_&&reading>=active_->id-active_->value&&reading<=active_->id+active_->value)return active_->id;Node*n=lower_bound(static_cast<long long>(reading)+1);n=n?predecessor(n):maximum();active_=n;return n?std::optional<int>(n->id):std::nullopt;}std::optional<int> ThresholdHysteresisTree::active_band()const{return active_?std::optional<int>(active_->id):std::nullopt;}std::vector<int> ThresholdHysteresisTree::thresholds()const{std::vector<int>v;for(Node*n=minimum();n;n=successor(n))v.push_back(n->id);return v;}""", """
ThresholdHysteresisTree t; REQUIRE(t.add(10,2)); REQUIRE(t.add(20,3)); REQUIRE(t.transition(21)==20); REQUIRE(t.transition(18)==20); REQUIRE(t.transition(15)==10);""", """
ThresholdHysteresisTree t; for(auto p:std::vector<std::pair<int,int>>{{30,5},{10,1},{20,2}})REQUIRE(t.add(p.first,p.second)); REQUIRE_FALSE(t.transition(5)); REQUIRE(t.transition(25)==20); REQUIRE(t.transition(24)==20); REQUIRE(t.transition(29)==20); REQUIRE(t.transition(30)==30); REQUIRE(t.erase(30)); REQUIRE_FALSE(t.active_band()); REQUIRE(t.audit_for_test().valid);""",
         "Choose the greatest threshold not above a reading, but retain the active node while readings remain inside its node-specific hysteresis band.", "stateful-hysteresis-transition-over-threads"),
    Case("threaded-ticket-browser", "threaded-ticket-priority-tree", "TicketPriorityTree", """
  bool open(int ticket,int severity); bool reprioritize(int ticket,int severity); bool resolve(int ticket);
  std::optional<int> next_ticket() const; std::vector<int> queue() const;""", "", """
bool TicketPriorityTree::open(int,int){return false;}bool TicketPriorityTree::reprioritize(int,int){return false;}bool TicketPriorityTree::resolve(int){return false;}std::optional<int> TicketPriorityTree::next_ticket()const{return std::nullopt;}std::vector<int> TicketPriorityTree::queue()const{return{};}""", """
bool TicketPriorityTree::open(int id,int severity){if(id<=0||id>=1000000||severity<0||severity>1000||find_id(id))return false;long long order=static_cast<long long>(1000-severity)*1000000+id;return insert_node(new Node{order,id,severity,0,1,false,nullptr,nullptr,nullptr,true,true});}bool TicketPriorityTree::reprioritize(int id,int severity){Node*n=find_id(id);if(!n||severity<0||severity>1000)return false;if(n->value==severity)return true;erase_node(n);return open(id,severity);}bool TicketPriorityTree::resolve(int id){Node*n=find_id(id);if(!n)return false;erase_node(n);return true;}std::optional<int> TicketPriorityTree::next_ticket()const{Node*n=minimum();return n?std::optional<int>(n->id):std::nullopt;}std::vector<int> TicketPriorityTree::queue()const{std::vector<int>v;for(Node*n=minimum();n;n=successor(n))v.push_back(n->id);return v;}""", """
TicketPriorityTree t; REQUIRE(t.open(2,3)); REQUIRE(t.open(1,3)); REQUIRE(t.open(3,5)); REQUIRE(t.queue()==std::vector<int>{3,1,2});""", """
TicketPriorityTree t; for(auto p:std::vector<std::pair<int,int>>{{1,2},{2,5},{3,2},{4,1}})REQUIRE(t.open(p.first,p.second)); REQUIRE(t.reprioritize(4,6)); REQUIRE(t.queue()==std::vector<int>{4,2,1,3}); REQUIRE(t.resolve(2)); REQUIRE(t.next_ticket()==4); REQUIRE(t.audit_for_test().valid);""",
         "Order tickets by severity descending then ID ascending using a composite threaded key, and repair order by validated reprioritization.", "composite-priority-order-and-rekey"),
    Case("threaded-transit-service", "threaded-service-wrap-tree", "ServiceWrapTree", """
  bool add(int minute); bool cancel(int minute); std::optional<int> next_wrapped(int minute) const;
  std::optional<int> previous_wrapped(int minute) const; std::vector<int> day_order() const;""", "", """
bool ServiceWrapTree::add(int){return false;}bool ServiceWrapTree::cancel(int){return false;}std::optional<int> ServiceWrapTree::next_wrapped(int)const{return std::nullopt;}std::optional<int> ServiceWrapTree::previous_wrapped(int)const{return std::nullopt;}std::vector<int> ServiceWrapTree::day_order()const{return{};}""", """
bool ServiceWrapTree::add(int k){return k>=0&&k<1440&&insert_node(new Node{k,k,0,0,1,false,nullptr,nullptr,nullptr,true,true});}bool ServiceWrapTree::cancel(int k){Node*n=find_order(k);if(!n)return false;erase_node(n);return true;}std::optional<int> ServiceWrapTree::next_wrapped(int k)const{Node*n=lower_bound(k);if(!n)n=minimum();return n?std::optional<int>(n->id):std::nullopt;}std::optional<int> ServiceWrapTree::previous_wrapped(int k)const{Node*n=lower_bound(static_cast<long long>(k)+1);n=n?predecessor(n):maximum();if(!n)n=maximum();return n?std::optional<int>(n->id):std::nullopt;}std::vector<int> ServiceWrapTree::day_order()const{std::vector<int>v;for(Node*n=minimum();n;n=successor(n))v.push_back(n->id);return v;}""", """
ServiceWrapTree t; for(int k:{100,500,900})REQUIRE(t.add(k)); REQUIRE(t.next_wrapped(901)==100); REQUIRE(t.previous_wrapped(50)==900);""", """
ServiceWrapTree t; for(int k:{40,20,60,10,30})REQUIRE(t.add(k)); REQUIRE(t.next_wrapped(25)==30); REQUIRE(t.previous_wrapped(25)==20); REQUIRE(t.cancel(20)); REQUIRE(t.previous_wrapped(25)==10); REQUIRE(t.audit_for_test().valid);""",
         "Provide a cyclic day view over ordinary inorder successor/predecessor threads, wrapping only at the two null boundaries.", "cyclic-boundary-thread-view"),
)


assert len(CASES) == 20
assert len({case.legacy_id for case in CASES}) == 20
assert len({case.task_id for case in CASES}) == 20
assert len({case.logic_tag for case in CASES}) == 20


# Each entry changes one task-specific semantic decision in the emitted
# reference.  The resulting source must still compile under the ordinary
# strict flags, but that root's ordinary visible/private tests must reject it.
# Keeping these mutations next to the contracts makes a missing or ambiguous
# discriminator a generator error rather than unverifiable prose.
NEGATIVE_MUTATIONS: dict[str, tuple[str, str, str]] = {
    "threaded-appointment-book": (
        "n=n?predecessor(n):maximum()",
        "n=n?successor(n):minimum()",
        "uses the opposite neighbor for the strict-before query",
    ),
    "threaded-bid-multiplicity-index": (
        "if(Node*n=find_order(k)){++n->count;return true;}",
        "if(Node*n=find_order(k)){(void)n;return false;}",
        "rejects a repeated bid instead of increasing multiplicity",
    ),
    "threaded-audit-tombstone-index": (
        "if(!n->flag)v.push_back(n->id)",
        "if(n->flag)v.push_back(n->id)",
        "returns tombstones instead of live audit records",
    ),
    "threaded-calendar-cursor": (
        "Node*n=current_?successor(current_):minimum()",
        "Node*n=current_?predecessor(current_):maximum()",
        "moves the cursor from the opposite end and direction",
    ),
    "threaded-cargo-interval-tree": (
        "n->value<=last&&n->aux>=first",
        "n->value>=last&&n->aux>=first",
        "uses the wrong closed-interval overlap predicate",
    ),
    "threaded-anchor-rank-tree": (
        "while(n&&r--!=0)n=successor(n)",
        "while(n&&r--!=0)n=predecessor(n)",
        "walks predecessors from the minimum for rank selection",
    ),
    "threaded-fare-prefix-tree": (
        "for(Node*n=minimum();n;n=successor(n)){total+=n->value;if(total>=target)",
        "for(Node*n=minimum();n;n=successor(n)){total=n->value;if(total>=target)",
        "forgets prior fares while searching the prefix threshold",
    ),
    "threaded-version-access-index": (
        "if(!best||n->count>best->count)best=n",
        "if(!best||n->count<best->count)best=n",
        "selects the least-accessed version",
    ),
    "threaded-departure-day-index": (
        "if(n->value==gate)return n->id",
        "if(n->value!=gate)return n->id",
        "returns the first departure at a different gate",
    ),
    "threaded-catalog-stock-index": (
        "if(n->value>0)return n->id",
        "if(n->value==0)return n->id",
        "selects an empty SKU instead of an in-stock SKU",
    ),
    "threaded-shelf-bulk-builder": (
        "std::size_t m=a+(b-a)/2",
        "std::size_t m=a",
        "builds a degenerate chain instead of midpoint-first balance",
    ),
    "threaded-dose-range-pruner": (
        "n&&n->id<=last",
        "n&&n->id<last",
        "makes the documented inclusive range upper bound exclusive",
    ),
    "threaded-waypoint-split-tree": (
        "if((n->id<p)==lower)ids.push_back(n->id)",
        "if((n->id<p)!=lower)ids.push_back(n->id)",
        "erases the partition opposite the requested side",
    ),
    "threaded-port-gap-tree": (
        "if(n->id>candidate)return candidate",
        "if(n->id>=candidate)return candidate",
        "reports a reserved boundary as the first free port",
    ),
    "threaded-space-state-tree": (
        "if(!n->flag)return n->id",
        "if(n->flag)return n->id",
        "selects the next occupied space instead of the next free space",
    ),
    "threaded-station-rekey-tree": (
        "return insert_node(new Node{new_k,new_k,0,0,1,false",
        "return insert_node(new Node{old_k,old_k,0,0,1,false",
        "reinserts the old station key after a successful rekey validation",
    ),
    "threaded-score-thread-auditor": (
        "if(v[i]->right_thread)v[i]->right=i+1<v.size()?v[i+1]:nullptr",
        "if(v[i]->right_thread)v[i]->right=nullptr",
        "repairs every successor thread to null",
    ),
    "threaded-threshold-hysteresis-tree": (
        "reading>=active_->id-active_->value",
        "reading>=active_->id-active_->value-1000",
        "extends the lower hysteresis boundary far below the node-specific width",
    ),
    "threaded-ticket-priority-tree": (
        "static_cast<long long>(1000-severity)*1000000+id",
        "static_cast<long long>(severity)*1000000+id",
        "orders lower severity ahead of higher severity",
    ),
    "threaded-service-wrap-tree": (
        "if(!n)n=minimum()",
        "if(!n)n=maximum()",
        "wraps the next-service query to the last service",
    ),
}

assert set(NEGATIVE_MUTATIONS) == {case.task_id for case in CASES}
