"""Independent C++ sources for the LFU-cache v3 remediation family."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TaskSpec:
    legacy_id: str
    class_name: str
    mode: str
    title: str
    api: str
    contract: str
    rules: str
    negative_fixture: str

    @property
    def task_id(self) -> str:
        return f"{self.legacy_id}-v3"


TASKS = (
    TaskSpec("lfu-audio-waveforms", "AudioWaveformBudget", "weighted_budget_vector", "Weighted waveform budget", "store/play/remove/resize/inventory", "Entries consume byte weights and one insertion may evict several victims.", "Victims minimize plays, then oldest touch; an oversized write fails without mutation.", "single-victim-slot-cache"),
    TaskSpec("lfu-compiler-artifacts", "ArtifactBucketIndex", "frequency_bucket_index", "Artifact bucket index", "save/load/discard/minimum_frequency/buckets", "A key index and ordered frequency lists form a bijection.", "Loads migrate a key between lists; each list is LRU ordered.", "full-map-victim-scan"),
    TaskSpec("lfu-dns-answers", "ExpiringDnsIndex", "ttl_heap_then_lfu", "Expiring DNS index", "record/resolve/advance/hosts", "An expiry heap removes stale answers before an LFU victim is considered.", "Expiry generations make stale heap records harmless; time never moves backward.", "live-only-lfu"),
    TaskSpec("lfu-document-pages", "WindowedPageLedger", "sliding_access_window", "Windowed page ledger", "insert/read/change_window/pages", "Only reads retained in a bounded event deque contribute frequency.", "Window shrink expires events immediately and victim scores are derived from the deque.", "lifetime-counter-cache"),
    TaskSpec("lfu-feature-config", "TenantQuotaLedger", "tenant_partitioned_vectors", "Tenant quota ledger", "define/publish/read/erase/tenant_view", "Each tenant owns an independent vector ledger and quota.", "Quota reduction repeatedly evicts inside that tenant; unknown tenants are invalid.", "global-capacity-cache"),
    TaskSpec("lfu-image-transform", "RecomputeRankIndex", "rational_cost_index", "Recomputation rank index", "put/fetch/reprice/ranking", "An ordered score index ranks hits divided by recomputation cost.", "Floating ratio ordering avoids integer truncation; repricing removes and reinserts the rank key.", "raw-hit-victim"),
    TaskSpec("lfu-package-manifests", "DependencyManifestGraph", "dependency_cascade_graph", "Dependency manifest graph", "publish/touch/invalidate/keys", "Invalidation traverses reverse dependency edges and removes all dependents.", "Cycles are rejected before commit; capacity pressure uses graph-independent LFU order.", "exact-key-invalidation"),
    TaskSpec("lfu-recommendations", "GhostHistoryRing", "resident_ghost_rings", "Recommendation ghost rings", "admit/read/erase/residents/ghosts", "Eviction records bounded frequency history in a separate ghost ring.", "Readmission starts above its ghost score and consumes that ghost record.", "history-free-readmission"),
    TaskSpec("lfu-schema-metadata", "RefreshResetIndex", "refresh_reset_multimap", "Schema refresh-reset index", "store/query/refresh/remove/order", "A refresh changes the value and resets frequency while moving to newest recency.", "A multimap index is erased and rebuilt for every score transition.", "refresh-as-hit"),
    TaskSpec("lfu-search-results", "EpochDecayTable", "lazy_epoch_decay", "Epoch-decayed search table", "remember/revisit/advance/scores", "Counts decay by powers of two at explicit epoch changes.", "Each row stores its last normalized epoch and is lazily normalized before comparison.", "eager-lifetime-count"),
    TaskSpec("lfu-session-attributes", "LeasePartitionCache", "leased_evictable_partitions", "Lease partition cache", "open/read/acquire/release/close/state", "Entries move between an evictable LRU list and a leased partition.", "Only zero-lease entries appear in the victim list and token release is exact.", "lease-blind-eviction"),
    TaskSpec("lfu-support-answers", "CheckpointAnswerTable", "transactional_snapshot_vector", "Transactional answer snapshots", "put/ask/checkpoint/restore/rows", "A canonical snapshot restores values, frequencies, and recency transactionally.", "The live table is a sorted vector; malformed images leave every byte of state unchanged.", "partial-restore"),
    TaskSpec("lfu-tax-estimates", "DynamicAgingTournament", "lfuda_tournament_tree", "LFUDA tournament cache", "save/read/erase/age/state", "A tournament tree selects minimum LFUDA priority and advances global age.", "Leaf priorities are hits plus admission age; internal winners are repaired bottom-up.", "plain-lfu-without-age"),
    TaskSpec("lfu-thumbnail-store", "SketchAdmissionRing", "count_min_sketch_ring", "Sketch-admission ring", "observe/offer/load/residents", "A count-min sketch gates admission into second-chance resident slots.", "A colder candidate is rejected without moving the hand or residents.", "always-admit-cache"),
    TaskSpec("lfu-translation-memory", "AtomicTranslationJournal", "validated_event_journal", "Atomic translation journal", "commit/read/snapshot", "Validated command batches append to an event journal atomically.", "The materialized LFU state is replayed independently; a failing batch appends no events.", "partial-batch-commit"),
)

REJECTED = {
    "lfu-map-tiles": "duplicates tenant-partitioned capacity and local victim selection",
    "lfu-pricing-quotes": "write-neutral is only an update-policy toggle",
    "lfu-product-catalog": "duplicates the explicit frequency-bucket root",
    "lfu-route-planner": "pinned exclusion duplicates lease-protected victim eligibility",
    "lfu-weather-forecast": "frequency capping is only a constant/overflow-policy toggle",
}

DECLARATIONS = {
    "weighted_budget_vector": "struct Item{std::string key,value;std::size_t bytes,plays,touch;}; explicit CLASS(std::size_t); bool store(std::string,std::string,std::size_t); std::optional<std::string> play(const std::string&); bool remove(const std::string&); bool resize(std::size_t); std::vector<Item> inventory()const; private: std::size_t budget_,used_=0,tick_=0;std::vector<Item> items_;bool evict_one();",
    "frequency_bucket_index": "explicit CLASS(std::size_t); bool save(std::string,std::string); std::optional<std::string> load(const std::string&); bool discard(const std::string&); std::size_t minimum_frequency()const; std::vector<std::vector<std::string>> buckets()const; private: struct Node{std::string value;std::size_t frequency;std::list<std::string>::iterator position;};std::size_t capacity_;std::unordered_map<std::string,Node> nodes_;std::map<std::size_t,std::list<std::string>> by_frequency_;void promote(const std::string&);",
    "ttl_heap_then_lfu": "struct Row{std::string host,address;std::size_t expires,hits,touch;}; explicit CLASS(std::size_t); bool record(std::string,std::string,std::size_t); std::optional<std::string> resolve(const std::string&); bool advance(std::size_t); std::vector<Row> hosts()const; private:struct Expiry{std::size_t at,generation;std::string host;bool operator>(const Expiry&)const;};std::size_t capacity_,now_=0,tick_=0,generation_=0;std::unordered_map<std::string,Row> rows_;std::unordered_map<std::string,std::size_t> generations_;std::priority_queue<Expiry,std::vector<Expiry>,std::greater<Expiry>> expiry_;void sweep();",
    "sliding_access_window": "struct Page{std::string id,text;std::size_t window_reads,touch;}; explicit CLASS(std::size_t,std::size_t); bool insert(std::string,std::string); std::optional<std::string> read(const std::string&); bool change_window(std::size_t); std::vector<Page> pages()const; private:struct Resident{std::string id,text;std::size_t touch;};std::size_t capacity_,window_,tick_=0;std::vector<Resident> residents_;std::deque<std::string> events_;std::size_t score(const std::string&)const;void trim();",
    "tenant_partitioned_vectors": "struct Entry{std::string key,value;std::size_t hits,touch;}; bool define(std::string,std::size_t); bool publish(const std::string&,std::string,std::string); std::optional<std::string> read(const std::string&,const std::string&); bool erase(const std::string&,const std::string&); std::vector<Entry> tenant_view(const std::string&)const; private:struct Tenant{std::size_t quota,tick=0;std::vector<Entry> entries;};std::map<std::string,Tenant> tenants_;static bool evict(Tenant&);",
    "rational_cost_index": "struct Rank{std::string key;std::size_t hits,cost,touch;}; explicit CLASS(std::size_t); bool put(std::string,std::string,std::size_t); std::optional<std::string> fetch(const std::string&); bool reprice(const std::string&,std::size_t); std::vector<Rank> ranking()const; private:struct Key{std::size_t hits,cost,touch;std::string id;};struct Less{bool operator()(const Key&,const Key&)const;};struct Value{std::string text;Key rank;};std::size_t capacity_,tick_=0;std::map<std::string,Value> values_;std::set<Key,Less> order_;void reindex(std::map<std::string,Value>::iterator,std::size_t,std::size_t);",
    "dependency_cascade_graph": "explicit CLASS(std::size_t); bool publish(std::string,std::string,std::vector<std::string>); std::optional<std::string> touch(const std::string&); std::vector<std::string> invalidate(const std::string&); std::vector<std::string> keys()const; private:struct Node{std::string value;std::size_t hits,touch;std::vector<std::string> dependencies;};std::size_t capacity_,tick_=0;std::map<std::string,Node> graph_;bool reaches(const std::string&,const std::string&)const;void erase_one(const std::string&);",
    "resident_ghost_rings": "struct Resident{std::string key,value;std::size_t frequency,touch;}; explicit CLASS(std::size_t); bool admit(std::string,std::string); std::optional<std::string> read(const std::string&); bool erase(const std::string&); std::vector<Resident> residents()const; std::vector<std::pair<std::string,std::size_t>> ghosts()const; private:std::size_t capacity_,tick_=0;std::vector<Resident> live_;std::deque<std::pair<std::string,std::size_t>> ghost_;void remember(const Resident&);",
    "refresh_reset_multimap": "struct Row{std::string key,value;std::size_t frequency,touch;}; explicit CLASS(std::size_t); bool store(std::string,std::string); std::optional<std::string> query(const std::string&); bool refresh(const std::string&,std::string); bool remove(const std::string&); std::vector<Row> order()const; private:using Score=std::tuple<std::size_t,std::size_t,std::string>;std::size_t capacity_,tick_=0;std::map<std::string,Row> rows_;std::multimap<Score,std::string> index_;void erase_index(const Row&);void add_index(const Row&);",
    "lazy_epoch_decay": "struct Score{std::string key;std::size_t effective,last_epoch;}; explicit CLASS(std::size_t); bool remember(std::string); bool revisit(const std::string&); bool advance(std::size_t); std::vector<Score> scores(); private:struct Row{std::size_t raw,last_epoch,touch;};std::size_t capacity_,epoch_=0,tick_=0;std::map<std::string,Row> rows_;void normalize(Row&);",
    "leased_evictable_partitions": "struct State{std::string key,value;std::size_t hits,leases;}; explicit CLASS(std::size_t); bool open(std::string,std::string); std::optional<std::string> read(const std::string&); std::optional<std::size_t> acquire(const std::string&); bool release(std::size_t); bool close(const std::string&); std::vector<State> state()const; private:struct Entry{std::string value;std::size_t hits,leases;std::list<std::string>::iterator victim;bool listed;};std::size_t capacity_,next_token_=1;std::unordered_map<std::string,Entry> entries_;std::unordered_map<std::size_t,std::string> tokens_;std::list<std::string> evictable_;void relink(const std::string&);",
    "transactional_snapshot_vector": "struct Row{std::string key,value;std::size_t frequency,touch;}; explicit CLASS(std::size_t); bool put(std::string,std::string); std::optional<std::string> ask(const std::string&); std::string checkpoint()const; bool restore(const std::string&); std::vector<Row> rows()const; private:std::size_t capacity_,tick_=0;std::vector<Row> table_;std::vector<Row>::iterator find(const std::string&);std::vector<Row>::const_iterator find(const std::string&)const;",
    "lfuda_tournament_tree": "struct State{std::string key,value;std::size_t hits,priority;}; explicit CLASS(std::size_t); bool save(std::string,std::string); std::optional<std::string> read(const std::string&); bool erase(const std::string&); std::size_t age()const; std::vector<State> state()const; private:std::size_t capacity_,age_=0;std::vector<State> leaves_;std::vector<std::size_t> winners_;void rebuild();std::size_t victim()const;",
    "count_min_sketch_ring": "struct Resident{std::string key,value;std::size_t estimate;bool referenced;}; explicit CLASS(std::size_t); void observe(const std::string&); bool offer(std::string,std::string); std::optional<std::string> load(const std::string&); std::vector<Resident> residents()const; private:std::size_t capacity_,hand_=0;std::array<std::array<std::size_t,17>,3> sketch_{};std::vector<Resident> ring_;std::size_t estimate(const std::string&)const;static std::size_t hash(const std::string&,std::size_t);",
    "validated_event_journal": "enum class Kind{put,erase,read};struct Command{Kind kind;std::string key,value;};struct Row{std::string key,value;std::size_t hits,touch;};explicit CLASS(std::size_t);bool commit(const std::vector<Command>&);std::optional<std::string> read(const std::string&)const;std::vector<Row> snapshot()const;private:std::size_t capacity_;std::vector<Command> journal_;std::optional<std::vector<Row>> replay(const std::vector<Command>&)const;",
}


INCLUDES = {
    "weighted_budget_vector": "<optional>\n#include <string>\n#include <vector>",
    "frequency_bucket_index": "<list>\n#include <map>\n#include <optional>\n#include <string>\n#include <unordered_map>\n#include <vector>",
    "ttl_heap_then_lfu": "<functional>\n#include <optional>\n#include <queue>\n#include <string>\n#include <unordered_map>\n#include <vector>",
    "sliding_access_window": "<deque>\n#include <optional>\n#include <string>\n#include <vector>",
    "tenant_partitioned_vectors": "<map>\n#include <optional>\n#include <string>\n#include <vector>",
    "rational_cost_index": "<map>\n#include <optional>\n#include <set>\n#include <string>\n#include <vector>",
    "dependency_cascade_graph": "<map>\n#include <optional>\n#include <string>\n#include <vector>",
    "resident_ghost_rings": "<deque>\n#include <optional>\n#include <string>\n#include <utility>\n#include <vector>",
    "refresh_reset_multimap": "<map>\n#include <optional>\n#include <string>\n#include <tuple>\n#include <vector>",
    "lazy_epoch_decay": "<map>\n#include <string>\n#include <vector>",
    "leased_evictable_partitions": "<list>\n#include <optional>\n#include <string>\n#include <unordered_map>\n#include <vector>",
    "transactional_snapshot_vector": "<optional>\n#include <string>\n#include <vector>",
    "lfuda_tournament_tree": "<optional>\n#include <string>\n#include <vector>",
    "count_min_sketch_ring": "<array>\n#include <optional>\n#include <string>\n#include <vector>",
    "validated_event_journal": "<optional>\n#include <string>\n#include <vector>",
}


def header_for(spec: TaskSpec) -> str:
    declaration = DECLARATIONS[spec.mode].replace("CLASS", spec.class_name)
    return f"""#pragma once
#include {INCLUDES[spec.mode]}
namespace curriculum {{ class {spec.class_name} {{ public: {declaration} }}; }}
"""


STARTERS = {
    mode: '#include "task.h"\n// Implement the documented mechanism without changing the public API.\n'
    for mode in DECLARATIONS
}


REFERENCES = {
    "weighted_budget_vector": r'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {
CLASS::CLASS(std::size_t n):budget_(n){if(!n)throw std::invalid_argument("budget");}
bool CLASS::evict_one(){if(items_.empty())return false;auto it=std::min_element(items_.begin(),items_.end(),[](const Item&a,const Item&b){return a.plays!=b.plays?a.plays<b.plays:a.touch<b.touch;});used_-=it->bytes;items_.erase(it);return true;}
bool CLASS::store(std::string k,std::string v,std::size_t b){if(k.empty()||v.empty()||!b||b>budget_)return false;auto it=std::find_if(items_.begin(),items_.end(),[&](const Item&x){return x.key==k;});if(it!=items_.end()){std::size_t next=used_-it->bytes+b;if(next>budget_)return false;used_=next;it->value=std::move(v);it->bytes=b;it->touch=++tick_;return true;}while(used_+b>budget_)evict_one();items_.push_back({std::move(k),std::move(v),b,0,++tick_});used_+=b;return true;}
std::optional<std::string> CLASS::play(const std::string&k){auto it=std::find_if(items_.begin(),items_.end(),[&](const Item&x){return x.key==k;});if(it==items_.end())return{};++it->plays;it->touch=++tick_;return it->value;}
bool CLASS::remove(const std::string&k){auto it=std::find_if(items_.begin(),items_.end(),[&](const Item&x){return x.key==k;});if(it==items_.end())return false;used_-=it->bytes;items_.erase(it);return true;}
bool CLASS::resize(std::size_t n){if(!n)return false;budget_=n;while(used_>budget_)evict_one();return true;}
std::vector<CLASS::Item> CLASS::inventory()const{auto out=items_;std::sort(out.begin(),out.end(),[](const Item&a,const Item&b){return a.key<b.key;});return out;}
}''',
    "frequency_bucket_index": r'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {
CLASS::CLASS(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
void CLASS::promote(const std::string&k){auto&n=nodes_.at(k);auto f=n.frequency;by_frequency_[f].erase(n.position);if(by_frequency_[f].empty())by_frequency_.erase(f);++n.frequency;by_frequency_[n.frequency].push_back(k);n.position=std::prev(by_frequency_[n.frequency].end());}
bool CLASS::save(std::string k,std::string v){if(k.empty()||v.empty())return false;auto it=nodes_.find(k);if(it!=nodes_.end()){it->second.value=std::move(v);promote(k);return true;}if(nodes_.size()==capacity_){auto b=by_frequency_.begin();auto victim=b->second.front();b->second.pop_front();if(b->second.empty())by_frequency_.erase(b);nodes_.erase(victim);}by_frequency_[1].push_back(k);nodes_.emplace(k,Node{std::move(v),1,std::prev(by_frequency_[1].end())});return true;}
std::optional<std::string> CLASS::load(const std::string&k){auto it=nodes_.find(k);if(it==nodes_.end())return{};auto v=it->second.value;promote(k);return v;}
bool CLASS::discard(const std::string&k){auto it=nodes_.find(k);if(it==nodes_.end())return false;auto f=it->second.frequency;by_frequency_[f].erase(it->second.position);if(by_frequency_[f].empty())by_frequency_.erase(f);nodes_.erase(it);return true;}
std::size_t CLASS::minimum_frequency()const{return by_frequency_.empty()?0:by_frequency_.begin()->first;}
std::vector<std::vector<std::string>> CLASS::buckets()const{std::vector<std::vector<std::string>>out;for(const auto&b:by_frequency_)out.emplace_back(b.second.begin(),b.second.end());return out;}
}''',
    "ttl_heap_then_lfu": r'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {
bool CLASS::Expiry::operator>(const Expiry&o)const{return at!=o.at?at>o.at:(generation!=o.generation?generation>o.generation:host>o.host);}
CLASS::CLASS(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
void CLASS::sweep(){while(!expiry_.empty()&&expiry_.top().at<=now_){auto x=expiry_.top();expiry_.pop();auto g=generations_.find(x.host);if(g!=generations_.end()&&g->second==x.generation){rows_.erase(x.host);generations_.erase(g);}}}
bool CLASS::record(std::string h,std::string a,std::size_t e){if(h.empty()||a.empty()||e<=now_)return false;sweep();auto it=rows_.find(h);if(it==rows_.end()&&rows_.size()==capacity_){auto v=std::min_element(rows_.begin(),rows_.end(),[](const auto&a,const auto&b){return a.second.hits!=b.second.hits?a.second.hits<b.second.hits:a.second.touch<b.second.touch;});generations_.erase(v->first);rows_.erase(v);}auto g=++generation_;generations_[h]=g;rows_[h]={h,std::move(a),e,it==rows_.end()?0:it->second.hits,++tick_};expiry_.push({e,g,h});return true;}
std::optional<std::string> CLASS::resolve(const std::string&h){sweep();auto it=rows_.find(h);if(it==rows_.end())return{};++it->second.hits;it->second.touch=++tick_;return it->second.address;}
bool CLASS::advance(std::size_t t){if(t<now_)return false;now_=t;sweep();return true;}
std::vector<CLASS::Row> CLASS::hosts()const{std::vector<Row>out;for(const auto&p:rows_)out.push_back(p.second);std::sort(out.begin(),out.end(),[](const Row&a,const Row&b){return a.host<b.host;});return out;}
}''',
    "sliding_access_window": r'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {
CLASS::CLASS(std::size_t c,std::size_t w):capacity_(c),window_(w){if(!c||!w)throw std::invalid_argument("bounds");}
std::size_t CLASS::score(const std::string&id)const{return std::count(events_.begin(),events_.end(),id);}
void CLASS::trim(){while(events_.size()>window_)events_.pop_front();}
bool CLASS::insert(std::string id,std::string text){if(id.empty()||text.empty())return false;auto it=std::find_if(residents_.begin(),residents_.end(),[&](const Resident&r){return r.id==id;});if(it!=residents_.end()){it->text=std::move(text);it->touch=++tick_;return true;}if(residents_.size()==capacity_){auto v=std::min_element(residents_.begin(),residents_.end(),[&](const Resident&a,const Resident&b){auto sa=score(a.id),sb=score(b.id);return sa!=sb?sa<sb:a.touch<b.touch;});events_.erase(std::remove(events_.begin(),events_.end(),v->id),events_.end());residents_.erase(v);}residents_.push_back({std::move(id),std::move(text),++tick_});return true;}
std::optional<std::string> CLASS::read(const std::string&id){auto it=std::find_if(residents_.begin(),residents_.end(),[&](const Resident&r){return r.id==id;});if(it==residents_.end())return{};events_.push_back(id);trim();it->touch=++tick_;return it->text;}
bool CLASS::change_window(std::size_t w){if(!w)return false;window_=w;trim();return true;}
std::vector<CLASS::Page> CLASS::pages()const{std::vector<Page>out;for(const auto&r:residents_)out.push_back({r.id,r.text,score(r.id),r.touch});std::sort(out.begin(),out.end(),[](const Page&a,const Page&b){return a.id<b.id;});return out;}
}''',
    "tenant_partitioned_vectors": r'''#include "task.h"
#include <algorithm>
namespace curriculum {
bool CLASS::evict(Tenant&t){if(t.entries.empty())return false;auto v=std::min_element(t.entries.begin(),t.entries.end(),[](const Entry&a,const Entry&b){return a.hits!=b.hits?a.hits<b.hits:a.touch<b.touch;});t.entries.erase(v);return true;}
bool CLASS::define(std::string id,std::size_t q){if(id.empty()||!q)return false;auto [it,created]=tenants_.emplace(std::move(id),Tenant{q,0,{}});if(!created)it->second.quota=q;while(it->second.entries.size()>q)evict(it->second);return true;}
bool CLASS::publish(const std::string&t,std::string k,std::string v){auto owner=tenants_.find(t);if(owner==tenants_.end()||k.empty()||v.empty())return false;auto&x=owner->second;auto it=std::find_if(x.entries.begin(),x.entries.end(),[&](const Entry&e){return e.key==k;});if(it!=x.entries.end()){it->value=std::move(v);it->touch=++x.tick;return true;}if(x.entries.size()==x.quota)evict(x);x.entries.push_back({std::move(k),std::move(v),0,++x.tick});return true;}
std::optional<std::string> CLASS::read(const std::string&t,const std::string&k){auto owner=tenants_.find(t);if(owner==tenants_.end())return{};auto&x=owner->second;auto it=std::find_if(x.entries.begin(),x.entries.end(),[&](const Entry&e){return e.key==k;});if(it==x.entries.end())return{};++it->hits;it->touch=++x.tick;return it->value;}
bool CLASS::erase(const std::string&t,const std::string&k){auto owner=tenants_.find(t);if(owner==tenants_.end())return false;auto&v=owner->second.entries;auto it=std::find_if(v.begin(),v.end(),[&](const Entry&e){return e.key==k;});if(it==v.end())return false;v.erase(it);return true;}
std::vector<CLASS::Entry> CLASS::tenant_view(const std::string&t)const{auto it=tenants_.find(t);if(it==tenants_.end())return{};auto out=it->second.entries;std::sort(out.begin(),out.end(),[](const Entry&a,const Entry&b){return a.key<b.key;});return out;}
}''',
    "rational_cost_index": r'''#include "task.h"
#include <stdexcept>
namespace curriculum {
bool CLASS::Less::operator()(const Key&a,const Key&b)const{auto l=static_cast<long double>(a.hits)/a.cost,r=static_cast<long double>(b.hits)/b.cost;if(l!=r)return l<r;if(a.touch!=b.touch)return a.touch<b.touch;return a.id<b.id;}
CLASS::CLASS(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
void CLASS::reindex(std::map<std::string,Value>::iterator it,std::size_t h,std::size_t c){order_.erase(it->second.rank);it->second.rank={h,c,++tick_,it->first};order_.insert(it->second.rank);}
bool CLASS::put(std::string k,std::string v,std::size_t c){if(k.empty()||v.empty()||!c)return false;auto it=values_.find(k);if(it!=values_.end()){it->second.text=std::move(v);reindex(it,it->second.rank.hits,c);return true;}if(values_.size()==capacity_){auto victim=order_.begin()->id;order_.erase(order_.begin());values_.erase(victim);}Key rank{0,c,++tick_,k};values_.emplace(k,Value{std::move(v),rank});order_.insert(rank);return true;}
std::optional<std::string> CLASS::fetch(const std::string&k){auto it=values_.find(k);if(it==values_.end())return{};auto text=it->second.text;reindex(it,it->second.rank.hits+1,it->second.rank.cost);return text;}
bool CLASS::reprice(const std::string&k,std::size_t c){auto it=values_.find(k);if(it==values_.end()||!c)return false;reindex(it,it->second.rank.hits,c);return true;}
std::vector<CLASS::Rank> CLASS::ranking()const{std::vector<Rank>out;for(const auto&k:order_)out.push_back({k.id,k.hits,k.cost,k.touch});return out;}
}''',
    "dependency_cascade_graph": r'''#include "task.h"
#include <algorithm>
#include <queue>
#include <set>
#include <stdexcept>
namespace curriculum {
CLASS::CLASS(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
bool CLASS::reaches(const std::string&a,const std::string&b)const{std::vector<std::string>q{a};std::set<std::string>seen;while(!q.empty()){auto x=q.back();q.pop_back();if(x==b)return true;if(!seen.insert(x).second)continue;auto it=graph_.find(x);if(it!=graph_.end())q.insert(q.end(),it->second.dependencies.begin(),it->second.dependencies.end());}return false;}
void CLASS::erase_one(const std::string&k){graph_.erase(k);for(auto&p:graph_){auto&d=p.second.dependencies;d.erase(std::remove(d.begin(),d.end(),k),d.end());}}
bool CLASS::publish(std::string k,std::string v,std::vector<std::string>d){if(k.empty()||v.empty()||std::find(d.begin(),d.end(),k)!=d.end())return false;std::sort(d.begin(),d.end());if(std::adjacent_find(d.begin(),d.end())!=d.end())return false;for(const auto&x:d)if(!graph_.count(x)||reaches(x,k))return false;auto it=graph_.find(k);if(it==graph_.end()&&graph_.size()==capacity_){auto victim=std::min_element(graph_.begin(),graph_.end(),[](const auto&a,const auto&b){return a.second.hits!=b.second.hits?a.second.hits<b.second.hits:a.second.touch<b.second.touch;});erase_one(victim->first);}graph_[k]={std::move(v),0,++tick_,std::move(d)};return true;}
std::optional<std::string> CLASS::touch(const std::string&k){auto it=graph_.find(k);if(it==graph_.end())return{};++it->second.hits;it->second.touch=++tick_;return it->second.value;}
std::vector<std::string> CLASS::invalidate(const std::string&k){if(!graph_.count(k))return{};std::queue<std::string>q;q.push(k);std::set<std::string>gone;while(!q.empty()){auto x=q.front();q.pop();if(!gone.insert(x).second)continue;for(const auto&p:graph_)if(std::find(p.second.dependencies.begin(),p.second.dependencies.end(),x)!=p.second.dependencies.end())q.push(p.first);}std::vector<std::string>out(gone.begin(),gone.end());for(const auto&x:out)erase_one(x);return out;}
std::vector<std::string> CLASS::keys()const{std::vector<std::string>out;for(const auto&p:graph_)out.push_back(p.first);return out;}
}''',
    "resident_ghost_rings": r'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {
CLASS::CLASS(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
void CLASS::remember(const Resident&r){ghost_.erase(std::remove_if(ghost_.begin(),ghost_.end(),[&](const auto&g){return g.first==r.key;}),ghost_.end());ghost_.push_back({r.key,r.frequency});while(ghost_.size()>capacity_)ghost_.pop_front();}
bool CLASS::admit(std::string k,std::string v){if(k.empty()||v.empty())return false;auto it=std::find_if(live_.begin(),live_.end(),[&](const Resident&r){return r.key==k;});if(it!=live_.end()){it->value=std::move(v);++it->frequency;it->touch=++tick_;return true;}if(live_.size()==capacity_){auto victim=std::min_element(live_.begin(),live_.end(),[](const Resident&a,const Resident&b){return a.frequency!=b.frequency?a.frequency<b.frequency:a.touch<b.touch;});remember(*victim);live_.erase(victim);}std::size_t f=1;auto g=std::find_if(ghost_.begin(),ghost_.end(),[&](const auto&x){return x.first==k;});if(g!=ghost_.end()){f=g->second+1;ghost_.erase(g);}live_.push_back({std::move(k),std::move(v),f,++tick_});return true;}
std::optional<std::string> CLASS::read(const std::string&k){auto it=std::find_if(live_.begin(),live_.end(),[&](const Resident&r){return r.key==k;});if(it==live_.end())return{};++it->frequency;it->touch=++tick_;return it->value;}
bool CLASS::erase(const std::string&k){auto it=std::find_if(live_.begin(),live_.end(),[&](const Resident&r){return r.key==k;});if(it==live_.end())return false;live_.erase(it);return true;}
std::vector<CLASS::Resident> CLASS::residents()const{auto out=live_;std::sort(out.begin(),out.end(),[](const Resident&a,const Resident&b){return a.key<b.key;});return out;}
std::vector<std::pair<std::string,std::size_t>> CLASS::ghosts()const{return {ghost_.begin(),ghost_.end()};}
}''',
    "refresh_reset_multimap": r'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {
CLASS::CLASS(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
void CLASS::erase_index(const Row&r){auto range=index_.equal_range({r.frequency,r.touch,r.key});for(auto it=range.first;it!=range.second;++it)if(it->second==r.key){index_.erase(it);return;}}
void CLASS::add_index(const Row&r){index_.emplace(Score{r.frequency,r.touch,r.key},r.key);}
bool CLASS::store(std::string k,std::string v){if(k.empty()||v.empty())return false;auto it=rows_.find(k);if(it!=rows_.end()){erase_index(it->second);it->second.value=std::move(v);++it->second.frequency;it->second.touch=++tick_;add_index(it->second);return true;}if(rows_.size()==capacity_){auto victim=index_.begin()->second;index_.erase(index_.begin());rows_.erase(victim);}Row row{k,std::move(v),1,++tick_};rows_.emplace(k,row);add_index(row);return true;}
std::optional<std::string> CLASS::query(const std::string&k){auto it=rows_.find(k);if(it==rows_.end())return{};auto value=it->second.value;erase_index(it->second);++it->second.frequency;it->second.touch=++tick_;add_index(it->second);return value;}
bool CLASS::refresh(const std::string&k,std::string v){auto it=rows_.find(k);if(it==rows_.end()||v.empty())return false;erase_index(it->second);it->second.value=std::move(v);it->second.frequency=1;it->second.touch=++tick_;add_index(it->second);return true;}
bool CLASS::remove(const std::string&k){auto it=rows_.find(k);if(it==rows_.end())return false;erase_index(it->second);rows_.erase(it);return true;}
std::vector<CLASS::Row> CLASS::order()const{std::vector<Row>out;for(const auto&i:index_)out.push_back(rows_.at(i.second));return out;}
}''',
    "lazy_epoch_decay": r'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {
CLASS::CLASS(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
void CLASS::normalize(Row&r){auto d=epoch_-r.last_epoch;r.raw=d>=sizeof(std::size_t)*8?1:std::max<std::size_t>(1,r.raw>>d);r.last_epoch=epoch_;}
bool CLASS::remember(std::string k){if(k.empty())return false;auto it=rows_.find(k);if(it!=rows_.end()){normalize(it->second);++it->second.raw;it->second.touch=++tick_;return true;}if(rows_.size()==capacity_){for(auto&p:rows_)normalize(p.second);auto v=std::min_element(rows_.begin(),rows_.end(),[](const auto&a,const auto&b){return a.second.raw!=b.second.raw?a.second.raw<b.second.raw:a.second.touch<b.second.touch;});rows_.erase(v);}rows_[std::move(k)]={1,epoch_,++tick_};return true;}
bool CLASS::revisit(const std::string&k){auto it=rows_.find(k);if(it==rows_.end())return false;normalize(it->second);++it->second.raw;it->second.touch=++tick_;return true;}
bool CLASS::advance(std::size_t e){if(e<epoch_)return false;epoch_=e;return true;}
std::vector<CLASS::Score> CLASS::scores(){std::vector<Score>out;for(auto&p:rows_){normalize(p.second);out.push_back({p.first,p.second.raw,p.second.last_epoch});}return out;}
}''',
    "leased_evictable_partitions": r'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {
CLASS::CLASS(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
void CLASS::relink(const std::string&k){auto&e=entries_.at(k);if(e.listed){evictable_.erase(e.victim);e.listed=false;}if(!e.leases){evictable_.push_back(k);e.victim=std::prev(evictable_.end());e.listed=true;}}
bool CLASS::open(std::string k,std::string v){if(k.empty()||v.empty())return false;auto it=entries_.find(k);if(it!=entries_.end()){it->second.value=std::move(v);relink(k);return true;}if(entries_.size()==capacity_){if(evictable_.empty())return false;auto victim=evictable_.front();evictable_.pop_front();entries_.erase(victim);}auto [where,_]=entries_.emplace(k,Entry{std::move(v),0,0,{},false});(void)where;relink(k);return true;}
std::optional<std::string> CLASS::read(const std::string&k){auto it=entries_.find(k);if(it==entries_.end())return{};++it->second.hits;relink(k);return it->second.value;}
std::optional<std::size_t> CLASS::acquire(const std::string&k){auto it=entries_.find(k);if(it==entries_.end())return{};auto token=next_token_++;tokens_[token]=k;++it->second.leases;relink(k);return token;}
bool CLASS::release(std::size_t token){auto it=tokens_.find(token);if(it==tokens_.end())return false;auto key=it->second;tokens_.erase(it);--entries_.at(key).leases;relink(key);return true;}
bool CLASS::close(const std::string&k){auto it=entries_.find(k);if(it==entries_.end()||it->second.leases)return false;if(it->second.listed)evictable_.erase(it->second.victim);entries_.erase(it);return true;}
std::vector<CLASS::State> CLASS::state()const{std::vector<State>out;for(const auto&p:entries_)out.push_back({p.first,p.second.value,p.second.hits,p.second.leases});std::sort(out.begin(),out.end(),[](const State&a,const State&b){return a.key<b.key;});return out;}
}''',
    "transactional_snapshot_vector": r'''#include "task.h"
#include <algorithm>
#include <charconv>
#include <sstream>
#include <stdexcept>
namespace curriculum {
CLASS::CLASS(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
std::vector<CLASS::Row>::iterator CLASS::find(const std::string&k){return std::lower_bound(table_.begin(),table_.end(),k,[](const Row&r,const std::string&x){return r.key<x;});}std::vector<CLASS::Row>::const_iterator CLASS::find(const std::string&k)const{return std::lower_bound(table_.begin(),table_.end(),k,[](const Row&r,const std::string&x){return r.key<x;});}
bool CLASS::put(std::string k,std::string v){if(k.empty()||v.empty()||k.find('|')!=std::string::npos||v.find('|')!=std::string::npos)return false;auto it=find(k);if(it!=table_.end()&&it->key==k){it->value=std::move(v);++it->frequency;it->touch=++tick_;return true;}if(table_.size()==capacity_){auto victim=std::min_element(table_.begin(),table_.end(),[](const Row&a,const Row&b){return a.frequency!=b.frequency?a.frequency<b.frequency:a.touch<b.touch;});table_.erase(victim);it=find(k);}table_.insert(it,{std::move(k),std::move(v),1,++tick_});return true;}
std::optional<std::string> CLASS::ask(const std::string&k){auto it=find(k);if(it==table_.end()||it->key!=k)return{};++it->frequency;it->touch=++tick_;return it->value;}
std::string CLASS::checkpoint()const{std::ostringstream o;o<<capacity_<<'|'<<tick_<<'\n';for(const auto&r:table_)o<<r.key<<'|'<<r.value<<'|'<<r.frequency<<'|'<<r.touch<<'\n';return o.str();}
bool CLASS::restore(const std::string&image){std::istringstream in(image);std::string line;if(!std::getline(in,line))return false;auto bar=line.find('|');if(bar==std::string::npos)return false;std::size_t cap=0,tick=0;auto a=std::from_chars(line.data(),line.data()+bar,cap),b=std::from_chars(line.data()+bar+1,line.data()+line.size(),tick);if(a.ec!=std::errc()||b.ec!=std::errc()||!cap)return false;std::vector<Row>next;while(std::getline(in,line)){if(line.empty())continue;std::vector<std::string>p;std::size_t at=0;for(int i=0;i<3;++i){auto cut=line.find('|',at);if(cut==std::string::npos)return false;p.push_back(line.substr(at,cut-at));at=cut+1;}p.push_back(line.substr(at));std::size_t f=0,t=0;auto x=std::from_chars(p[2].data(),p[2].data()+p[2].size(),f),y=std::from_chars(p[3].data(),p[3].data()+p[3].size(),t);if(p[0].empty()||p[1].empty()||!f||x.ec!=std::errc()||y.ec!=std::errc())return false;next.push_back({p[0],p[1],f,t});}if(next.size()>cap||!std::is_sorted(next.begin(),next.end(),[](const Row&a,const Row&b){return a.key<b.key;})||std::adjacent_find(next.begin(),next.end(),[](const Row&a,const Row&b){return a.key==b.key;})!=next.end())return false;capacity_=cap;tick_=tick;table_=std::move(next);return true;}
std::vector<CLASS::Row> CLASS::rows()const{return table_;}
}''',
    "lfuda_tournament_tree": r'''#include "task.h"
#include <algorithm>
#include <limits>
#include <stdexcept>
namespace curriculum {
CLASS::CLASS(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
void CLASS::rebuild(){std::size_t base=1;while(base<leaves_.size())base*=2;winners_.assign(base*2,std::numeric_limits<std::size_t>::max());for(std::size_t i=0;i<leaves_.size();++i)winners_[base+i]=i;auto better=[&](std::size_t a,std::size_t b){if(a==std::numeric_limits<std::size_t>::max())return b;if(b==std::numeric_limits<std::size_t>::max())return a;return leaves_[a].priority!=leaves_[b].priority?(leaves_[a].priority<leaves_[b].priority?a:b):(leaves_[a].key<leaves_[b].key?a:b);};for(std::size_t i=base;i-->1;)winners_[i]=better(winners_[i*2],winners_[i*2+1]);}
std::size_t CLASS::victim()const{return winners_.size()>1?winners_[1]:0;}
bool CLASS::save(std::string k,std::string v){if(k.empty()||v.empty())return false;auto it=std::find_if(leaves_.begin(),leaves_.end(),[&](const State&s){return s.key==k;});if(it!=leaves_.end()){it->value=std::move(v);++it->hits;++it->priority;rebuild();return true;}if(leaves_.size()==capacity_){auto x=victim();age_=leaves_[x].priority;leaves_.erase(leaves_.begin()+(long long)x);}leaves_.push_back({std::move(k),std::move(v),1,age_+1});rebuild();return true;}
std::optional<std::string> CLASS::read(const std::string&k){auto it=std::find_if(leaves_.begin(),leaves_.end(),[&](const State&s){return s.key==k;});if(it==leaves_.end())return{};++it->hits;++it->priority;auto v=it->value;rebuild();return v;}
bool CLASS::erase(const std::string&k){auto it=std::find_if(leaves_.begin(),leaves_.end(),[&](const State&s){return s.key==k;});if(it==leaves_.end())return false;leaves_.erase(it);rebuild();return true;}
std::size_t CLASS::age()const{return age_;}std::vector<CLASS::State> CLASS::state()const{auto out=leaves_;std::sort(out.begin(),out.end(),[](const State&a,const State&b){return a.key<b.key;});return out;}
}''',
    "count_min_sketch_ring": r'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {
CLASS::CLASS(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
std::size_t CLASS::hash(const std::string&s,std::size_t seed){std::size_t h=1469598103934665603ULL^seed;for(unsigned char c:s){h^=c;h*=1099511628211ULL;}return h;}
std::size_t CLASS::estimate(const std::string&k)const{std::size_t n=~std::size_t{};for(std::size_t r=0;r<3;++r)n=std::min(n,sketch_[r][hash(k,r)%17]);return n;}
void CLASS::observe(const std::string&k){if(k.empty())return;for(std::size_t r=0;r<3;++r)++sketch_[r][hash(k,r)%17];}
bool CLASS::offer(std::string k,std::string v){if(k.empty()||v.empty())return false;observe(k);auto it=std::find_if(ring_.begin(),ring_.end(),[&](const Resident&r){return r.key==k;});if(it!=ring_.end()){it->value=std::move(v);it->estimate=estimate(k);it->referenced=true;return true;}if(ring_.size()<capacity_){ring_.push_back({std::move(k),std::move(v),estimate(k),true});return true;}auto start=hand_;do{if(!ring_[hand_].referenced)break;ring_[hand_].referenced=false;hand_=(hand_+1)%ring_.size();}while(hand_!=start);auto candidate=estimate(k);if(candidate<=estimate(ring_[hand_].key))return false;ring_[hand_]={std::move(k),std::move(v),candidate,true};hand_=(hand_+1)%ring_.size();return true;}
std::optional<std::string> CLASS::load(const std::string&k){observe(k);auto it=std::find_if(ring_.begin(),ring_.end(),[&](const Resident&r){return r.key==k;});if(it==ring_.end())return{};it->estimate=estimate(k);it->referenced=true;return it->value;}
std::vector<CLASS::Resident> CLASS::residents()const{return ring_;}
}''',
    "validated_event_journal": r'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {
CLASS::CLASS(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
std::optional<std::vector<CLASS::Row>> CLASS::replay(const std::vector<Command>&events)const{std::vector<Row>s;std::size_t tick=0;for(const auto&c:events){if(c.key.empty()||(c.kind==Kind::put&&c.value.empty()))return{};auto it=std::find_if(s.begin(),s.end(),[&](const Row&r){return r.key==c.key;});if(c.kind==Kind::put){if(it==s.end()){if(s.size()==capacity_){auto v=std::min_element(s.begin(),s.end(),[](const Row&a,const Row&b){return a.hits!=b.hits?a.hits<b.hits:a.touch<b.touch;});s.erase(v);}s.push_back({c.key,c.value,1,++tick});}else{it->value=c.value;++it->hits;it->touch=++tick;}}else if(c.kind==Kind::erase){if(it==s.end())return{};s.erase(it);}else{if(it==s.end())return{};++it->hits;it->touch=++tick;}}std::sort(s.begin(),s.end(),[](const Row&a,const Row&b){return a.key<b.key;});return s;}
bool CLASS::commit(const std::vector<Command>&batch){auto next=journal_;next.insert(next.end(),batch.begin(),batch.end());if(!replay(next))return false;journal_=std::move(next);return true;}
std::optional<std::string> CLASS::read(const std::string&k)const{auto s=replay(journal_);if(!s)return{};auto it=std::find_if(s->begin(),s->end(),[&](const Row&r){return r.key==k;});return it==s->end()?std::optional<std::string>{}:it->value;}
std::vector<CLASS::Row> CLASS::snapshot()const{return *replay(journal_);}
}''',
}


def _test(body: str) -> str:
    return (
        '#include "task.h"\n#include <cstdlib>\n#include <string>\n#include <vector>\n'
        "using namespace curriculum;template<class T>static void check(const T&ok){if(!static_cast<bool>(ok))std::abort();}"
        f"int main(){{{body}}}\n"
    )


ORACLE_BODIES = {
    "weighted_budget_vector": "CLASS x(5);check(x.inventory().empty());check(x.store(\"a\",\"A\",3));check(x.inventory().size()==1);check(x.store(\"b\",\"B\",2));check(x.play(\"b\")==\"B\");check(x.store(\"c\",\"C\",4));auto s=x.inventory();check(s.size()==1&&s[0].key==\"c\"&&s[0].bytes==4);check(x.resize(2));check(x.inventory().empty());check(!x.remove(\"missing\"));",
    "frequency_bucket_index": "CLASS x(2);check(x.buckets().empty());check(x.save(\"a\",\"A\"));check(x.save(\"b\",\"B\"));check(x.minimum_frequency()==1);check(x.load(\"a\")==\"A\");auto b=x.buckets();check(b.size()==2&&b[0]==std::vector<std::string>({\"b\"})&&b[1]==std::vector<std::string>({\"a\"}));check(x.save(\"c\",\"C\"));check(!x.load(\"b\"));check(x.discard(\"a\"));check(x.minimum_frequency()==1);",
    "ttl_heap_then_lfu": "CLASS x(2);check(x.hosts().empty());check(x.record(\"a\",\"1\",2));check(x.record(\"b\",\"2\",9));check(x.resolve(\"a\")==\"1\");check(x.advance(2));auto h=x.hosts();check(h.size()==1&&h[0].host==\"b\");check(x.record(\"c\",\"3\",10));check(x.resolve(\"b\")==\"2\");check(!x.advance(1));check(x.hosts().size()==2);",
    "sliding_access_window": "CLASS x(2,2);check(x.pages().empty());check(x.insert(\"a\",\"A\"));check(x.insert(\"b\",\"B\"));check(x.read(\"a\"));check(x.read(\"a\"));check(x.read(\"a\"));check(x.read(\"b\"));check(x.read(\"b\"));auto p=x.pages();check(p[0].window_reads==0&&p[1].window_reads==2);check(x.insert(\"c\",\"C\"));p=x.pages();check(p.size()==2&&p[0].id==\"b\"&&p[1].id==\"c\");check(x.change_window(1));check(x.pages()[0].window_reads==1);",
    "tenant_partitioned_vectors": "CLASS x;check(x.define(\"t\",2));check(x.define(\"u\",1));check(x.publish(\"t\",\"a\",\"A\"));check(x.publish(\"t\",\"b\",\"B\"));check(x.read(\"t\",\"a\")==\"A\");check(x.publish(\"u\",\"z\",\"Z\"));check(x.define(\"t\",1));auto t=x.tenant_view(\"t\");check(t.size()==1&&t[0].key==\"a\");check(x.tenant_view(\"u\").size()==1);check(x.erase(\"u\",\"z\"));check(!x.publish(\"missing\",\"x\",\"X\"));",
    "rational_cost_index": "CLASS x(2);check(x.ranking().empty());check(x.put(\"a\",\"A\",100));check(x.put(\"b\",\"B\",1));check(x.fetch(\"a\"));check(x.fetch(\"a\"));check(x.fetch(\"b\"));auto r=x.ranking();check(r.size()==2&&r[0].key==\"a\");check(x.put(\"c\",\"C\",1));check(!x.fetch(\"a\"));check(x.reprice(\"b\",20));check(x.ranking().front().key==\"c\");",
    "dependency_cascade_graph": "CLASS x(4);check(x.keys().empty());check(x.publish(\"a\",\"A\",{}));check(x.publish(\"b\",\"B\",{\"a\"}));check(x.publish(\"c\",\"C\",{\"b\"}));check(x.touch(\"a\")==\"A\");check(!x.publish(\"a\",\"A\",{\"c\"}));auto gone=x.invalidate(\"a\");check(gone==std::vector<std::string>({\"a\",\"b\",\"c\"}));check(x.keys().empty());check(x.invalidate(\"missing\").empty());",
    "resident_ghost_rings": "CLASS x(2);check(x.residents().empty());check(x.admit(\"a\",\"A\"));check(x.admit(\"b\",\"B\"));check(x.read(\"a\"));check(x.read(\"a\"));check(x.admit(\"c\",\"C\"));check(x.ghosts()==std::vector<std::pair<std::string,std::size_t>>({{\"b\",1}}));check(x.admit(\"b\",\"B2\"));auto r=x.residents();check(r.size()==2&&r[1].key==\"b\"&&r[1].frequency==2);check(x.ghosts().back().first==\"c\");check(x.erase(\"a\"));",
    "refresh_reset_multimap": "CLASS x(2);check(x.order().empty());check(x.store(\"a\",\"A\"));check(x.store(\"b\",\"B\"));check(x.query(\"a\"));check(x.query(\"a\"));check(x.query(\"b\"));check(x.refresh(\"a\",\"A2\"));auto o=x.order();check(o[0].key==\"a\"&&o[0].frequency==1);check(x.store(\"c\",\"C\"));check(!x.query(\"a\"));check(x.remove(\"b\"));",
    "lazy_epoch_decay": "CLASS x(2);check(x.scores().empty());check(x.remember(\"a\"));check(x.revisit(\"a\"));check(x.revisit(\"a\"));check(x.revisit(\"a\"));check(x.remember(\"b\"));check(x.advance(2));check(x.revisit(\"b\"));auto s=x.scores();check(s[0].key==\"a\"&&s[0].effective==1);check(x.remember(\"c\"));s=x.scores();check(s.size()==2&&s[0].key==\"b\"&&s[1].key==\"c\");check(!x.advance(1));",
    "leased_evictable_partitions": "CLASS x(1);check(x.state().empty());check(x.open(\"a\",\"A\"));check(x.read(\"a\")==\"A\");auto token=x.acquire(\"a\");check(token);check(x.state()[0].leases==1);check(!x.open(\"b\",\"B\"));check(x.release(*token));check(x.open(\"b\",\"B\"));check(x.state()[0].key==\"b\");check(!x.release(*token));check(x.close(\"b\"));",
    "transactional_snapshot_vector": "CLASS x(2);check(x.rows().empty());check(x.put(\"a\",\"A\"));check(x.put(\"b\",\"B\"));check(x.ask(\"a\")==\"A\");auto image=x.checkpoint();check(x.put(\"c\",\"C\"));check(x.restore(image));auto r=x.rows();check(r.size()==2&&r[0].key==\"a\"&&r[0].frequency==2);auto before=x.checkpoint();check(!x.restore(\"broken\"));check(x.checkpoint()==before);",
    "lfuda_tournament_tree": "CLASS x(2);check(x.state().empty());check(x.save(\"a\",\"A\"));check(x.save(\"b\",\"B\"));check(x.read(\"a\"));check(x.read(\"a\"));check(x.save(\"c\",\"C\"));check(x.age()==1);check(x.save(\"d\",\"D\"));check(x.age()==2);auto s=x.state();check(s.size()==2&&s[0].key==\"a\"&&s[1].key==\"d\");check(x.erase(\"a\"));",
    "count_min_sketch_ring": "CLASS x(1);check(x.residents().empty());x.observe(\"a\");x.observe(\"a\");check(x.offer(\"a\",\"A\"));check(x.residents()[0].key==\"a\");check(!x.offer(\"b\",\"B\"));x.observe(\"b\");x.observe(\"b\");x.observe(\"b\");check(x.offer(\"b\",\"B\"));check(x.residents()[0].key==\"b\");check(x.load(\"b\")==\"B\");",
    "validated_event_journal": "CLASS x(2);using K=CLASS::Kind;check(x.snapshot().empty());check(x.commit({{K::put,\"a\",\"A\"}}));check(x.read(\"a\")==\"A\");auto before=x.snapshot();check(!x.commit({{K::put,\"b\",\"B\"},{K::erase,\"missing\",\"\"}}));auto after=x.snapshot();check(after.size()==before.size()&&after[0].key==before[0].key);check(x.commit({{K::read,\"a\",\"\"},{K::put,\"b\",\"B\"},{K::put,\"c\",\"C\"}}));after=x.snapshot();check(after.size()==2&&after[0].key==\"a\"&&after[1].key==\"c\");",
}

ORACLE_TESTS = {mode: _test(body.replace("CLASS", next(s.class_name for s in TASKS if s.mode == mode))) for mode, body in ORACLE_BODIES.items()}
TESTS = {
    mode: (source, source)
    for mode, source in ORACLE_TESTS.items()
}


_NEGATIVE_REPLACEMENTS = {
    "weighted_budget_vector": ("while(used_+b>budget_)evict_one();", "if(used_+b>budget_)evict_one();"),
    "frequency_bucket_index": ("void CLASS::promote(const std::string&k){", "void CLASS::promote(const std::string&k){return;(void)k;"),
    "ttl_heap_then_lfu": ("void CLASS::sweep(){", "void CLASS::sweep(){return;"),
    "sliding_access_window": ("while(events_.size()>window_)events_.pop_front();", "return;"),
    "tenant_partitioned_vectors": ("return a.hits!=b.hits?a.hits<b.hits:a.touch<b.touch;", "return a.hits!=b.hits?a.hits>b.hits:a.touch>b.touch;"),
    "rational_cost_index": ("auto l=static_cast<long double>(a.hits)/a.cost,r=static_cast<long double>(b.hits)/b.cost;", "auto l=static_cast<long double>(a.hits),r=static_cast<long double>(b.hits);"),
    "dependency_cascade_graph": ("std::queue<std::string>q;q.push(k);", "std::queue<std::string>q;q.push(k);return {k};"),
    "resident_ghost_rings": ("f=g->second+1;", "f=1;"),
    "refresh_reset_multimap": ("it->second.frequency=1;", "++it->second.frequency;"),
    "lazy_epoch_decay": ("r.raw=d>=sizeof(std::size_t)*8?1:std::max<std::size_t>(1,r.raw>>d);", "(void)d;r.raw=std::max<std::size_t>(1,r.raw);"),
    "leased_evictable_partitions": ("if(evictable_.empty())return false;", "if(evictable_.empty()){entries_.erase(entries_.begin());return open(std::move(k),std::move(v));}"),
    "transactional_snapshot_vector": ("bool CLASS::restore(const std::string&image){", "bool CLASS::restore(const std::string&image){return false;(void)image;"),
    "lfuda_tournament_tree": ("age_=leaves_[x].priority;", "age_=0;"),
    "count_min_sketch_ring": ("if(candidate<=estimate(ring_[hand_].key))return false;", "if(false)return false;"),
    "validated_event_journal": ("if(!replay(next))return false;journal_=std::move(next);return true;", "journal_=std::move(next);return true;"),
}


def negative_for(mode: str) -> str:
    old, new = _NEGATIVE_REPLACEMENTS[mode]
    source = REFERENCES[mode]
    changed = source.replace(old, new)
    if changed == source:
        raise AssertionError(f"negative replacement did not match: {mode}")
    return changed


NEGATIVES = {mode: negative_for(mode) for mode in REFERENCES}


BOUNDARY_PROFILES = {
    "weighted_budget_vector": "zero or oversized byte write preserves byte occupancy",
    "frequency_bucket_index": "empty index reports frequency zero and absent discard is false",
    "ttl_heap_then_lfu": "expiry must exceed monotone logical time",
    "sliding_access_window": "zero window is rejected while shrink expires oldest events",
    "tenant_partitioned_vectors": "unknown tenant operations fail and quota shrink is tenant-local",
    "rational_cost_index": "zero recomputation cost is invalid and reprice is index-atomic",
    "dependency_cascade_graph": "unknown dependencies and dependency cycles reject publication",
    "resident_ghost_rings": "ghost ring is capacity bounded and explicit erase creates no ghost",
    "refresh_reset_multimap": "refresh requires a resident and nonempty replacement schema",
    "lazy_epoch_decay": "epochs are monotone and large gaps floor effective count at one",
    "leased_evictable_partitions": "all-leased pressure fails and a token releases exactly once",
    "transactional_snapshot_vector": "malformed or over-capacity image preserves prior table bytes",
    "lfuda_tournament_tree": "empty tournament has no winner and erased leaves repair ancestors",
    "count_min_sketch_ring": "cold offer preserves hand and resident while observations saturate evidence",
    "validated_event_journal": "one invalid command rejects the entire batch and appends no event",
}

CONTROL_FLOW_PROFILES = {
    "weighted_budget_vector": "repeat vector minimum scan until byte pressure clears",
    "frequency_bucket_index": "constant-index list migration then first-bucket pop",
    "ttl_heap_then_lfu": "generation-checked heap sweep before live minimum scan",
    "sliding_access_window": "deque expiry then score-by-retained-event victim",
    "tenant_partitioned_vectors": "lookup tenant ledger then repeat local vector eviction",
    "rational_cost_index": "erase and reinsert ordered ratio key on every score mutation",
    "dependency_cascade_graph": "cycle reachability plus reverse-edge breadth-first invalidation",
    "resident_ghost_rings": "dual resident-vector and bounded ghost-deque transfer",
    "refresh_reset_multimap": "tuple-index removal followed by reset and reinsertion",
    "lazy_epoch_decay": "per-row lazy bit decay before comparison or observation",
    "leased_evictable_partitions": "list splice between leased and evictable partitions",
    "transactional_snapshot_vector": "parse complete temporary sorted vector then swap commit",
    "lfuda_tournament_tree": "bottom-up tournament winner repair and age propagation",
    "count_min_sketch_ring": "three-row sketch estimate then second-chance hand traversal",
    "validated_event_journal": "append candidate batch, replay full event log, then commit journal",
}

ORACLE_PROFILES = {
    mode: body.replace(next(spec.class_name for spec in TASKS if spec.mode == mode), "CLASS")
    for mode, body in ORACLE_BODIES.items()
}

DIVERSITY_PROFILES = {
    spec.mode: (
        spec.api,
        DECLARATIONS[spec.mode].split("private:", 1)[1],
        spec.rules,
        BOUNDARY_PROFILES[spec.mode],
        CONTROL_FLOW_PROFILES[spec.mode],
        ORACLE_PROFILES[spec.mode],
        spec.negative_fixture,
    )
    for spec in TASKS
}
