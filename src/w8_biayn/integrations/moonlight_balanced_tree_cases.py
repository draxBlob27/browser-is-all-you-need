
"""Task-specific C++ fragments for the balanced-search-tree materializer."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Case:
    impl: str
    methods: str
    visible: str
    trace: str

def _case(impl: str, methods: str, visible: str, trace: str) -> Case:
    return Case(impl.strip(), methods.strip(), visible.strip(), trace.strip())

CASES = {
"avl-live-leaderboard": _case(
"""struct LiveLeaderboard::Impl { detail::AvlTree<std::tuple<std::int64_t,std::string>,LeaderboardEntry> tree; };""",
"""bool LiveLeaderboard::upsert(std::string id,std::int64_t score){if(!detail::valid_id(id)||score<=0)return false;for(const auto&e:impl_->tree.values())if(e.player_id==id){if(e.score==score)return false;impl_->tree.erase({-e.score,e.player_id});break;}impl_->tree.put({-score,id},{id,score});return true;}
bool LiveLeaderboard::erase(std::string_view id){if(!detail::valid_id(id))return false;for(const auto&e:impl_->tree.values())if(e.player_id==id)return impl_->tree.erase({-e.score,e.player_id});return false;}
std::optional<LeaderboardEntry> LiveLeaderboard::entry(std::string_view id)const{if(!detail::valid_id(id))return std::nullopt;for(const auto&e:impl_->tree.values())if(e.player_id==id)return e;return std::nullopt;}
std::optional<std::size_t> LiveLeaderboard::rank_of(std::string_view id)const{const auto entry=this->entry(id);if(!entry)return std::nullopt;return impl_->tree.rank_of({-entry->score,entry->player_id});}
std::vector<LeaderboardEntry> LiveLeaderboard::top(std::size_t count)const{std::vector<LeaderboardEntry> out;for(std::size_t rank=1;rank<=count;++rank){const auto*entry=impl_->tree.select(rank);if(!entry)break;out.push_back(*entry);}return out;}""",
"""REQUIRE(tree.upsert("amy",50));REQUIRE(tree.upsert("bob",70));REQUIRE(tree.upsert("ann",70));REQUIRE(tree.rank_of("ann")==1U);REQUIRE(tree.top(2).size()==2U);REQUIRE(!tree.upsert("ann",70));REQUIRE(!tree.upsert("bad id",1));REQUIRE(tree.erase("bob"));""",
"""if((state&1U)==0U)tree.upsert(id,key+1);else tree.erase(id);"""
),
"avl-api-rate-limits": _case(
"""struct ApiRateLimits::Impl { detail::AvlTree<std::int64_t,RateLimit> tree; };""",
"""bool ApiRateLimits::put(RateLimit r){if(r.threshold<=0||r.max_requests<=0||!detail::valid_id(r.rule_id))return false;if(const auto*o=impl_->tree.find(r.threshold))if(o->max_requests==r.max_requests&&o->rule_id==r.rule_id)return false;impl_->tree.put(r.threshold,r);return true;}
bool ApiRateLimits::erase(std::int64_t k){return k>0&&impl_->tree.erase(k);}
std::optional<RateLimit> ApiRateLimits::resolve(std::int64_t q)const{std::optional<RateLimit> out;for(const auto&r:impl_->tree.values())if(r.threshold<=q)out=r;else break;return out;}
std::vector<RateLimit> ApiRateLimits::in_window(std::int64_t a,std::int64_t b)const{std::vector<RateLimit> out;if(a>b)return out;for(const auto&r:impl_->tree.values())if(r.threshold>=a&&r.threshold<=b)out.push_back(r);return out;}""",
"""REQUIRE(tree.put({10,100,"base"}));REQUIRE(tree.put({20,150,"burst"}));REQUIRE(tree.resolve(19)->rule_id=="base");REQUIRE(tree.in_window(10,20).size()==2U);REQUIRE(!tree.put({0,1,"bad"}));REQUIRE(tree.erase(10));""",
"""if((state&1U)==0U)tree.put({key,key+10,id});else tree.erase(key);"""
),
"avl-appointment-slots": _case(
"""struct AppointmentSlots::Impl { detail::AvlTree<std::int64_t,Appointment> tree; };""",
"""bool AppointmentSlots::reserve(Appointment a){if(a.start<0||a.duration<=0||!detail::valid_id(a.booking_id)||detail::add_overflows(a.start,a.duration))return false;const auto end=a.start+a.duration;for(const auto&e:impl_->tree.values()){if(e.booking_id==a.booking_id)return false;const auto eend=e.start+e.duration;if(a.start<eend&&e.start<end)return false;}impl_->tree.put(a.start,a);return true;}
bool AppointmentSlots::cancel(std::string_view id){if(!detail::valid_id(id))return false;for(const auto&e:impl_->tree.values())if(e.booking_id==id)return impl_->tree.erase(e.start);return false;}
std::optional<std::int64_t> AppointmentSlots::next_available(std::int64_t start,std::int64_t duration)const{if(start<0||duration<=0)return std::nullopt;std::int64_t candidate=start;for(const auto&e:impl_->tree.values()){if(detail::add_overflows(candidate,duration))return std::nullopt;if(candidate+duration<=e.start)return candidate;if(candidate<e.start+e.duration)candidate=e.start+e.duration;}if(detail::add_overflows(candidate,duration))return std::nullopt;return candidate;}
std::vector<Appointment> AppointmentSlots::scheduled()const{return impl_->tree.values();}""",
"""REQUIRE(tree.reserve({10,5,"a"}));REQUIRE(tree.reserve({15,5,"b"}));REQUIRE(!tree.reserve({14,2,"c"}));REQUIRE(tree.next_available(12,2)==20);REQUIRE(tree.cancel("a"));REQUIRE(tree.next_available(10,2)==10);""",
"""if((state&1U)==0U)tree.reserve({key*3,1,id});else tree.cancel(id);"""
),
"avl-inventory-restock": _case(
"""struct InventoryRestock::Impl { detail::AvlTree<std::tuple<std::int64_t,std::string>,RestockRule> tree; };""",
"""bool InventoryRestock::put(RestockRule r){if(!detail::valid_id(r.sku)||r.reorder_at<=0||r.target_stock<r.reorder_at)return false;for(const auto&e:impl_->tree.values())if(e.sku==r.sku){if(e.reorder_at==r.reorder_at&&e.target_stock==r.target_stock)return false;impl_->tree.erase({e.reorder_at,e.sku});break;}impl_->tree.put({r.reorder_at,r.sku},r);return true;}
bool InventoryRestock::erase(std::string_view sku){if(!detail::valid_id(sku))return false;for(const auto&e:impl_->tree.values())if(e.sku==sku)return impl_->tree.erase({e.reorder_at,e.sku});return false;}
std::optional<RestockRule> InventoryRestock::next_rule(std::int64_t on_hand)const{std::optional<RestockRule> out;for(const auto&r:impl_->tree.values())if(r.reorder_at<=on_hand&&(!out||r.reorder_at>out->reorder_at))out=r;return out;}
std::vector<RestockRule> InventoryRestock::rules()const{return impl_->tree.values();}""",
"""REQUIRE(tree.put({"a",5,20}));REQUIRE(tree.put({"b",5,30}));REQUIRE(tree.next_rule(5)->sku=="a");REQUIRE(!tree.put({"bad id",1,2}));REQUIRE(tree.erase("a"));""",
"""if((state&1U)==0U)tree.put({id,key+1,key+20});else tree.erase(id);"""
),
"avl-memory-free-ranges": _case(
"""struct MemoryFreeRanges::Impl { detail::AvlTree<std::int64_t,Block> tree; };""",
"""bool MemoryFreeRanges::release(Block b){if(b.start<0||b.length<=0||detail::add_overflows(b.start,b.length))return false;std::int64_t start=b.start,end=b.start+b.length;std::vector<std::int64_t> merge;for(const auto&e:impl_->tree.values()){const auto eend=e.start+e.length;if(start<eend&&e.start<end)return false;if(eend==start){start=e.start;merge.push_back(e.start);}else if(end==e.start){end=eend;merge.push_back(e.start);}}for(auto k:merge)impl_->tree.erase(k);impl_->tree.put(start,{start,end-start});return true;}
std::optional<Block> MemoryFreeRanges::allocate(std::int64_t length){if(length<=0)return std::nullopt;for(const auto&b:impl_->tree.values())if(b.length>=length){impl_->tree.erase(b.start);if(b.length>length)impl_->tree.put(b.start+length,{b.start+length,b.length-length});return Block{b.start,length};}return std::nullopt;}
std::vector<Block> MemoryFreeRanges::free_blocks()const{return impl_->tree.values();}""",
"""REQUIRE(tree.release({0,4}));REQUIRE(tree.release({4,4}));REQUIRE(tree.free_blocks().size()==1U);REQUIRE(tree.allocate(3)->start==0);REQUIRE(tree.free_blocks()[0].start==3);REQUIRE(!tree.release({4,2}));""",
"""if((state&1U)==0U)tree.release({key*4,2});else tree.allocate((key%3)+1);"""
),

"avl-coupon-thresholds": _case(
"""struct CouponThresholds::Impl { detail::AvlTree<std::int64_t,Coupon> tree; };""",
"""bool CouponThresholds::put(Coupon c){if(c.minimum_spend<=0||c.discount_cents<=0||!detail::valid_id(c.code))return false;if(const auto*o=impl_->tree.find(c.minimum_spend))if(o->discount_cents==c.discount_cents&&o->code==c.code)return false;impl_->tree.put(c.minimum_spend,c);return true;}
bool CouponThresholds::erase(std::int64_t k){return k>0&&impl_->tree.erase(k);}
std::optional<Coupon> CouponThresholds::best_for(std::int64_t spend)const{std::optional<Coupon> out;for(const auto&c:impl_->tree.values())if(c.minimum_spend<=spend)out=c;else break;return out;}""",
"""REQUIRE(tree.put({1000,100,"SAVE"}));REQUIRE(!tree.best_for(999));REQUIRE(tree.best_for(1000)->code=="SAVE");REQUIRE(tree.put({1000,200,"MORE"}));REQUIRE(tree.best_for(1000)->discount_cents==200);""",
"""if((state&1U)==0U)tree.put({key,key+1,id});else tree.erase(key);"""
),
"avl-game-matchmaking": _case(
"""struct GameMatchmaking::Impl { detail::AvlTree<std::tuple<std::int64_t,std::string>,Player> tree; };""",
"""bool GameMatchmaking::join(Player p){if(!detail::valid_id(p.player_id)||p.rating<=0)return false;for(const auto&e:impl_->tree.values())if(e.player_id==p.player_id)return false;impl_->tree.put({p.rating,p.player_id},p);return true;}
bool GameMatchmaking::leave(std::string_view id){if(!detail::valid_id(id))return false;for(const auto&e:impl_->tree.values())if(e.player_id==id)return impl_->tree.erase({e.rating,e.player_id});return false;}
std::optional<Player> GameMatchmaking::closest_opponent(std::string_view id,std::int64_t max_delta)const{if(!detail::valid_id(id)||max_delta<0)return std::nullopt;std::optional<Player> self,best;std::uint64_t best_delta=0;auto v=impl_->tree.values();for(const auto&p:v)if(p.player_id==id)self=p;if(!self)return std::nullopt;for(const auto&p:v)if(p.player_id!=id){std::uint64_t d=p.rating>self->rating?static_cast<std::uint64_t>(p.rating-self->rating):static_cast<std::uint64_t>(self->rating-p.rating);if(d<=static_cast<std::uint64_t>(max_delta)&&(!best||d<best_delta||(d==best_delta&&std::tie(p.rating,p.player_id)<std::tie(best->rating,best->player_id)))){best=p;best_delta=d;}}return best;}""",
"""REQUIRE(tree.join({"self",100}));REQUIRE(tree.join({"low",90}));REQUIRE(tree.join({"high",110}));REQUIRE(tree.closest_opponent("self",10)->player_id=="low");REQUIRE(!tree.closest_opponent("missing",10));REQUIRE(tree.leave("low"));""",
"""if((state&1U)==0U)tree.join({id,key+1});else tree.leave(id);"""
),
"avl-energy-tariffs": _case(
"""struct EnergyTariffs::Impl { detail::AvlTree<std::int64_t,Tariff> tree; };""",
"""bool EnergyTariffs::put(Tariff t){if(t.start_usage<0||t.cents_per_unit<=0||!detail::valid_id(t.tariff_id))return false;if(const auto*o=impl_->tree.find(t.start_usage))if(o->cents_per_unit==t.cents_per_unit&&o->tariff_id==t.tariff_id)return false;impl_->tree.put(t.start_usage,t);return true;}
bool EnergyTariffs::erase(std::int64_t k){return k>=0&&impl_->tree.erase(k);}
std::optional<Tariff> EnergyTariffs::active_at(std::int64_t usage)const{std::optional<Tariff> out;for(const auto&t:impl_->tree.values())if(t.start_usage<=usage)out=t;else break;return out;}""",
"""REQUIRE(tree.put({0,5,"base"}));REQUIRE(tree.put({100,7,"peak"}));REQUIRE(tree.active_at(99)->tariff_id=="base");REQUIRE(tree.active_at(100)->tariff_id=="peak");REQUIRE(tree.erase(100));""",
"""if((state&1U)==0U)tree.put({key,key+1,id});else tree.erase(key);"""
),
"avl-shipping-weight-bands": _case(
"""struct ShippingWeightBands::Impl { detail::AvlTree<std::int64_t,WeightBand> tree; };""",
"""bool ShippingWeightBands::put(WeightBand b){if(b.first<=0||b.last<b.first||b.cents<=0)return false;for(const auto&e:impl_->tree.values()){if(e.first==b.first)return false;const bool overlap=b.first<=e.last&&e.first<=b.last;const bool adjacent=(e.last<std::numeric_limits<std::int64_t>::max()&&e.last+1==b.first)||(b.last<std::numeric_limits<std::int64_t>::max()&&b.last+1==e.first);if(overlap||adjacent)return false;}impl_->tree.put(b.first,b);return true;}
bool ShippingWeightBands::erase(std::int64_t k){return k>0&&impl_->tree.erase(k);}
std::optional<WeightBand> ShippingWeightBands::quote_for(std::int64_t w)const{for(const auto&b:impl_->tree.values())if(w>=b.first&&w<=b.last)return b;return std::nullopt;}
std::vector<WeightBand> ShippingWeightBands::bands()const{return impl_->tree.values();}""",
"""REQUIRE(tree.put({1,5,100}));REQUIRE(!tree.put({6,8,200}));REQUIRE(tree.put({7,9,200}));REQUIRE(tree.quote_for(5)->cents==100);REQUIRE(!tree.quote_for(6));REQUIRE(tree.erase(1));""",
"""if((state&1U)==0U)tree.put({key*3,key*3+1,key+1});else tree.erase(key*3);"""
),
"avl-library-holds": _case(
"""struct LibraryHolds::Impl { detail::AvlTree<std::tuple<std::int64_t,std::int64_t,std::string>,Hold> tree; };""",
"""bool LibraryHolds::place(Hold h){if(!detail::valid_id(h.hold_id)||!detail::valid_id(h.patron_id)||h.priority<=0||h.placed_at<0)return false;for(const auto&e:impl_->tree.values())if(e.hold_id==h.hold_id)return false;impl_->tree.put({h.priority,h.placed_at,h.hold_id},h);return true;}
bool LibraryHolds::cancel(std::string_view id){if(!detail::valid_id(id))return false;for(const auto&e:impl_->tree.values())if(e.hold_id==id)return impl_->tree.erase({e.priority,e.placed_at,e.hold_id});return false;}
std::optional<Hold> LibraryHolds::promote_next(std::int64_t minimum){if(minimum<=0)return std::nullopt;for(const auto&h:impl_->tree.values())if(h.priority>=minimum){impl_->tree.erase({h.priority,h.placed_at,h.hold_id});return h;}return std::nullopt;}""",
"""REQUIRE(tree.place({"h2","p2",5,2}));REQUIRE(tree.place({"h1","p1",5,1}));REQUIRE(tree.promote_next(5)->hold_id=="h1");REQUIRE(!tree.cancel("h1"));REQUIRE(tree.cancel("h2"));""",
"""if((state&1U)==0U)tree.place({id,"patron",key+1,key});else tree.cancel(id);"""
),

"rb-order-book": _case(
"""struct OrderBook::Impl { detail::RbTree<std::int64_t,BidLevel> tree; };""",
"""bool OrderBook::set_bid(BidLevel b){if(b.price<=0||b.quantity<=0)return false;if(const auto*o=impl_->tree.find(b.price))if(o->quantity==b.quantity)return false;impl_->tree.put(b.price,b);return true;}
bool OrderBook::cancel_bid(std::int64_t p){return p>0&&impl_->tree.erase(p);}
std::optional<BidLevel> OrderBook::best_bid(std::int64_t limit)const{std::optional<BidLevel> out;for(const auto&b:impl_->tree.values())if(b.price<limit)out=b;else break;return out;}
std::vector<BidLevel> OrderBook::bids()const{auto v=impl_->tree.values();std::reverse(v.begin(),v.end());return v;}""",
"""REQUIRE(tree.set_bid({100,2}));REQUIRE(tree.set_bid({90,3}));REQUIRE(tree.best_bid(100)->price==90);REQUIRE(tree.bids()[0].price==100);REQUIRE(tree.cancel_bid(100));""",
"""if((state&1U)==0U)tree.set_bid({key,key+1});else tree.cancel_bid(key);"""
),
"rb-file-version-index": _case(
"""struct FileVersionIndex::Impl { detail::RbTree<std::int64_t,Version> tree; };""",
"""bool FileVersionIndex::put(Version v){if(v.revision<=0||!detail::valid_id(v.content_hash))return false;if(const auto*o=impl_->tree.find(v.revision))if(o->content_hash==v.content_hash)return false;impl_->tree.put(v.revision,v);return true;}
bool FileVersionIndex::erase(std::int64_t r){return r>0&&impl_->tree.erase(r);}
std::optional<Version> FileVersionIndex::latest_not_after(std::int64_t r)const{std::optional<Version> out;for(const auto&v:impl_->tree.values())if(v.revision<=r)out=v;else break;return out;}
std::vector<Version> FileVersionIndex::between(std::int64_t a,std::int64_t b)const{std::vector<Version> out;if(a>b)return out;for(const auto&v:impl_->tree.values())if(v.revision>=a&&v.revision<=b)out.push_back(v);return out;}""",
"""REQUIRE(tree.put({1,"h1"}));REQUIRE(tree.put({3,"h3"}));REQUIRE(tree.latest_not_after(2)->revision==1);REQUIRE(tree.between(1,3).size()==2U);REQUIRE(tree.erase(1));""",
"""if((state&1U)==0U)tree.put({key,id});else tree.erase(key);"""
),
"rb-reservation-directory": _case(
"""struct ReservationDirectory::Impl { detail::RbTree<std::tuple<std::int64_t,std::string>,Reservation> tree; };""",
"""bool ReservationDirectory::allocate(Reservation r){if(r.code<=0||!detail::valid_id(r.reservation_id))return false;for(const auto&e:impl_->tree.values())if(e.code==r.code||e.reservation_id==r.reservation_id)return false;impl_->tree.put({r.code,r.reservation_id},r);return true;}
bool ReservationDirectory::release(std::string_view id){if(!detail::valid_id(id))return false;for(const auto&e:impl_->tree.values())if(e.reservation_id==id)return impl_->tree.erase({e.code,e.reservation_id});return false;}
std::optional<Reservation> ReservationDirectory::nearest_code(std::int64_t requested)const{if(requested<=0)return std::nullopt;std::optional<Reservation> best;std::uint64_t delta=0;for(const auto&r:impl_->tree.values()){auto d=r.code>requested?static_cast<std::uint64_t>(r.code-requested):static_cast<std::uint64_t>(requested-r.code);if(!best||d<delta||(d==delta&&std::tie(r.code,r.reservation_id)<std::tie(best->code,best->reservation_id))){best=r;delta=d;}}return best;}""",
"""REQUIRE(tree.allocate({10,"a"}));REQUIRE(tree.allocate({20,"b"}));REQUIRE(tree.nearest_code(15)->code==10);REQUIRE(!tree.allocate({10,"c"}));REQUIRE(tree.release("a"));""",
"""if((state&1U)==0U)tree.allocate({key,id});else tree.release(id);"""
),
"rb-medication-schedule": _case(
"""struct MedicationSchedule::Impl { detail::RbTree<std::tuple<std::int64_t,std::string>,ScheduleEntry> tree; };""",
"""bool MedicationSchedule::schedule(ScheduleEntry e){if(e.time<0||e.dose_units<=0||!detail::valid_id(e.entry_id))return false;for(const auto&x:impl_->tree.values())if(x.entry_id==e.entry_id)return false;impl_->tree.put({e.time,e.entry_id},e);return true;}
bool MedicationSchedule::cancel(std::string_view id){if(!detail::valid_id(id))return false;for(const auto&e:impl_->tree.values())if(e.entry_id==id)return impl_->tree.erase({e.time,e.entry_id});return false;}
std::optional<ScheduleEntry> MedicationSchedule::next_at_or_after(std::int64_t time)const{for(const auto&e:impl_->tree.values())if(e.time>=time)return e;return std::nullopt;}
std::vector<ScheduleEntry> MedicationSchedule::in_window(std::int64_t a,std::int64_t b)const{std::vector<ScheduleEntry> out;if(a>b)return out;for(const auto&e:impl_->tree.values())if(e.time>=a&&e.time<=b)out.push_back(e);return out;}""",
"""REQUIRE(tree.schedule({5,"b",2}));REQUIRE(tree.schedule({5,"a",1}));REQUIRE(tree.next_at_or_after(5)->entry_id=="a");REQUIRE(tree.in_window(5,5).size()==2U);REQUIRE(tree.cancel("a"));""",
"""if((state&1U)==0U)tree.schedule({key,id,(key%5)+1});else tree.cancel(id);"""
),
"rb-access-control-rules": _case(
"""struct AccessControlRules::Impl { detail::RbTree<std::tuple<std::int64_t,std::string>,AccessRule> tree; };""",
"""bool AccessControlRules::put(AccessRule r){if(r.priority<=0||!detail::valid_id(r.rule_id))return false;for(const auto&e:impl_->tree.values())if(e.rule_id==r.rule_id){if(e.priority==r.priority&&e.effect==r.effect)return false;impl_->tree.erase({e.priority,e.rule_id});break;}impl_->tree.put({r.priority,r.rule_id},r);return true;}
bool AccessControlRules::erase(std::string_view id){if(!detail::valid_id(id))return false;for(const auto&e:impl_->tree.values())if(e.rule_id==id)return impl_->tree.erase({e.priority,e.rule_id});return false;}
std::optional<AccessRule> AccessControlRules::resolve(std::int64_t requested)const{std::optional<AccessRule> out;for(const auto&r:impl_->tree.values())if(r.priority<=requested&&(!out||r.priority>out->priority))out=r;return out;}""",
"""REQUIRE(tree.put({5,curriculum::Effect::deny,"a"}));REQUIRE(tree.put({5,curriculum::Effect::allow,"b"}));REQUIRE(tree.resolve(5)->rule_id=="a");REQUIRE(tree.put({7,curriculum::Effect::deny,"b"}));REQUIRE(tree.resolve(6)->rule_id=="a");""",
"""if((state&1U)==0U)tree.put({key,(key&1)?curriculum::Effect::allow:curriculum::Effect::deny,id});else tree.erase(id);"""
),

"rb-cargo-manifest": _case(
"""struct CargoManifest::Impl { detail::RbTree<std::int64_t,Cargo> tree; };""",
"""bool CargoManifest::put(Cargo c){if(c.cargo_id<=0||c.weight<=0||!detail::valid_id(c.destination))return false;if(const auto*o=impl_->tree.find(c.cargo_id))if(o->weight==c.weight&&o->destination==c.destination)return false;impl_->tree.put(c.cargo_id,c);return true;}
bool CargoManifest::erase(std::int64_t id){return id>0&&impl_->tree.erase(id);}
std::optional<Cargo> CargoManifest::find(std::int64_t id)const{if(id<=0)return std::nullopt;if(const auto*c=impl_->tree.find(id))return *c;return std::nullopt;}
std::vector<Cargo> CargoManifest::in_id_range(std::int64_t a,std::int64_t b)const{std::vector<Cargo> out;if(a>b)return out;for(const auto&c:impl_->tree.values())if(c.cargo_id>=a&&c.cargo_id<=b)out.push_back(c);return out;}""",
"""REQUIRE(tree.put({1,50,"north"}));REQUIRE(tree.find(1)->weight==50);REQUIRE(tree.put({1,60,"south"}));REQUIRE(tree.in_id_range(1,1)[0].destination=="south");REQUIRE(tree.erase(1));""",
"""if((state&1U)==0U)tree.put({key,key+1,id});else tree.erase(key);"""
),
"rb-metric-percentiles": _case(
"""struct MetricPercentiles::Impl { detail::RbTree<std::int64_t,std::int64_t> tree; };""",
"""bool MetricPercentiles::add(std::int64_t value){if(value<=0)return false;if(const auto*n=impl_->tree.find(value)){const auto next=*n+1;impl_->tree.put(value,next);impl_->tree.set_weight(value,static_cast<std::size_t>(next));}else impl_->tree.put(value,1);return true;}
bool MetricPercentiles::remove(std::int64_t value){if(value<=0)return false;const auto*n=impl_->tree.find(value);if(!n)return false;if(*n==1)return impl_->tree.erase(value);const auto next=*n-1;impl_->tree.put(value,next);impl_->tree.set_weight(value,static_cast<std::size_t>(next));return true;}
std::size_t MetricPercentiles::count()const{return impl_->tree.total_weight();}
std::optional<std::int64_t> MetricPercentiles::percentile(std::int64_t percent)const{const auto n=count();if(percent<1||percent>100||n==0)return std::nullopt;const auto rank=(static_cast<std::uint64_t>(percent)*n+99U)/100U;if(const auto*v=impl_->tree.select_key(static_cast<std::size_t>(rank)))return *v;return std::nullopt;}""",
"""REQUIRE(tree.add(10));REQUIRE(tree.add(10));REQUIRE(tree.add(30));REQUIRE(tree.count()==3U);REQUIRE(tree.percentile(50)==10);REQUIRE(tree.percentile(100)==30);REQUIRE(tree.remove(10));""",
"""if((state&1U)==0U)tree.add(key);else tree.remove(key);"""
),
"rb-travel-fare-table": _case(
"""struct TravelFareTable::Impl { detail::RbTree<std::int64_t,Fare> tree; };""",
"""bool TravelFareTable::put(Fare f){if(f.maximum_budget<=0||f.cents<=0||!detail::valid_id(f.fare_id))return false;if(const auto*o=impl_->tree.find(f.maximum_budget))if(o->cents==f.cents&&o->fare_id==f.fare_id)return false;impl_->tree.put(f.maximum_budget,f);return true;}
bool TravelFareTable::erase(std::int64_t b){return b>0&&impl_->tree.erase(b);}
std::optional<Fare> TravelFareTable::best_for(std::int64_t budget)const{std::optional<Fare> out;for(const auto&f:impl_->tree.values())if(f.maximum_budget<=budget)out=f;else break;return out;}""",
"""REQUIRE(tree.put({1000,800,"basic"}));REQUIRE(tree.put({2000,1500,"flex"}));REQUIRE(tree.best_for(1999)->fare_id=="basic");REQUIRE(tree.best_for(2000)->fare_id=="flex");REQUIRE(tree.erase(1000));""",
"""if((state&1U)==0U)tree.put({key,key+1,id});else tree.erase(key);"""
),
"rb-audit-event-index": _case(
"""struct AuditEventIndex::Impl { detail::RbTree<std::int64_t,AuditEvent> tree; };""",
"""bool AuditEventIndex::record(AuditEvent e){if(e.event_id<=0||!detail::valid_id(e.actor_id)||e.redacted||impl_->tree.find(e.event_id))return false;impl_->tree.put(e.event_id,e);return true;}
bool AuditEventIndex::redact(std::int64_t id){if(id<=0)return false;const auto*old=impl_->tree.find(id);if(!old||old->redacted)return false;auto e=*old;e.redacted=true;impl_->tree.put(id,e);return true;}
bool AuditEventIndex::remove_for_retention(std::int64_t id){return id>0&&impl_->tree.erase(id);}
std::optional<AuditEvent> AuditEventIndex::find(std::int64_t id)const{if(id<=0)return std::nullopt;if(const auto*e=impl_->tree.find(id))return *e;return std::nullopt;}
std::vector<AuditEvent> AuditEventIndex::between(std::int64_t a,std::int64_t b)const{std::vector<AuditEvent> out;if(a>b)return out;for(const auto&e:impl_->tree.values())if(e.event_id>=a&&e.event_id<=b)out.push_back(e);return out;}""",
"""REQUIRE(tree.record({1,"actor",false}));REQUIRE(tree.redact(1));REQUIRE(!tree.redact(1));REQUIRE(tree.find(1)->redacted);REQUIRE(tree.remove_for_retention(1));REQUIRE(!tree.find(1));""",
"""if((state&1U)==0U)tree.record({key,id,false});else if((state&2U)==0U)tree.redact(key);else tree.remove_for_retention(key);"""
),
"rb-support-escalations": _case(
"""struct SupportEscalations::Impl { detail::RbTree<std::tuple<std::int64_t,std::int64_t,std::string>,Escalation> tree; };""",
"""bool SupportEscalations::open(Escalation e){if(!detail::valid_id(e.case_id)||e.priority<=0||e.opened_at<0||e.state!=curriculum::CaseState::open)return false;for(const auto&x:impl_->tree.values())if(x.case_id==e.case_id)return false;impl_->tree.put({e.priority,e.opened_at,e.case_id},e);return true;}
bool SupportEscalations::close(std::string_view id){if(!detail::valid_id(id))return false;for(const auto&e:impl_->tree.values())if(e.case_id==id)return impl_->tree.erase({e.priority,e.opened_at,e.case_id});return false;}
bool SupportEscalations::reprioritize(std::string_view id,std::int64_t priority){if(!detail::valid_id(id)||priority<=0)return false;for(const auto&e:impl_->tree.values())if(e.case_id==id){if(e.priority==priority)return false;auto changed=e;changed.priority=priority;impl_->tree.erase({e.priority,e.opened_at,e.case_id});impl_->tree.put({changed.priority,changed.opened_at,changed.case_id},changed);return true;}return false;}
std::optional<Escalation> SupportEscalations::take_next(std::int64_t minimum){if(minimum<=0)return std::nullopt;for(const auto&e:impl_->tree.values())if(e.priority>=minimum){impl_->tree.erase({e.priority,e.opened_at,e.case_id});return e;}return std::nullopt;}""",
"""REQUIRE(tree.open({"b",5,2,curriculum::CaseState::open}));REQUIRE(tree.open({"a",5,1,curriculum::CaseState::open}));REQUIRE(tree.take_next(5)->case_id=="a");REQUIRE(tree.reprioritize("b",7));REQUIRE(tree.take_next(6)->case_id=="b");""",
"""if((state&1U)==0U)tree.open({id,key+1,key,curriculum::CaseState::open});else if((state&2U)==0U)tree.reprioritize(id,(key%97)+1);else tree.close(id);"""
),
}
