"""Bespoke bounded-concurrency cases for the hard-rule remediation owner."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Case:
    legacy_id: str
    task_id: str
    class_name: str
    summary: str
    contract: str
    profile: str
    marker: str
    header: str
    reference: str
    visible: str
    hidden: str
    hard_rule: str
    negative_old: str
    negative_new: str
    negative_reason: str


def _case(*values: str) -> Case:
    return Case(*values)


CASES = (
    _case(
        "bbq-audio-processing", "bbq-audio-processing-v2", "AudioFrameWindow",
        "Publish weighted audio frames and atomically take the next contiguous sequence through a watermark.",
        "Frames have positive stream, sequence, and sample counts. Publication blocks on sample budget; duplicate or consumed sequences fail. A take waits for a complete contiguous prefix through its watermark. Sealing makes an unfillable gap terminal.",
        "ordered weighted sequence window", "frames_.find(s)==frames_.end()",
        r'''struct AudioFrame { int stream_id; int sequence; std::size_t samples; bool operator==(const AudioFrame& x) const { return stream_id==x.stream_id&&sequence==x.sequence&&samples==x.samples; } };
class AudioFrameWindow { public: explicit AudioFrameWindow(std::size_t sample_budget); bool publish(AudioFrame frame); std::vector<AudioFrame> take_through(int sequence); bool seal(int final_sequence); std::size_t buffered_samples() const; private: std::size_t budget_; std::size_t used_=0; int next_=1; int final_=0; bool sealed_=false; std::map<int,AudioFrame> frames_; mutable std::mutex mutex_; std::condition_variable data_; std::condition_variable space_; };''',
        r'''AudioFrameWindow::AudioFrameWindow(std::size_t n):budget_(n){if(!n)throw std::invalid_argument("sample budget");}
bool AudioFrameWindow::publish(AudioFrame f){if(f.stream_id<=0||f.sequence<=0||!f.samples||f.samples>budget_)return false;std::unique_lock<std::mutex> l(mutex_);if(f.sequence<next_||frames_.count(f.sequence)||(sealed_&&f.sequence>final_))return false;space_.wait(l,[&]{return sealed_||used_+f.samples<=budget_;});if(sealed_)return false;used_+=f.samples;frames_[f.sequence]=f;l.unlock();data_.notify_all();return true;}
std::vector<AudioFrame> AudioFrameWindow::take_through(int end){std::unique_lock<std::mutex> l(mutex_);if(end<next_)return{};data_.wait(l,[&]{if(sealed_&&end>final_)return true;for(int s=next_;s<=end;++s)if(frames_.find(s)==frames_.end())return sealed_;return true;});for(int s=next_;s<=end;++s)if(frames_.find(s)==frames_.end())return{};std::vector<AudioFrame> out;while(next_<=end){auto it=frames_.find(next_++);used_-=it->second.samples;out.push_back(it->second);frames_.erase(it);}l.unlock();space_.notify_all();return out;}
bool AudioFrameWindow::seal(int f){std::lock_guard<std::mutex> l(mutex_);if(sealed_||f<next_-1)return false;sealed_=true;final_=f;data_.notify_all();space_.notify_all();return true;}
std::size_t AudioFrameWindow::buffered_samples()const{std::lock_guard<std::mutex> l(mutex_);return used_;}''',
        r'''int main(){AudioFrameWindow q(8);CHECK(q.publish({1,2,3}));CHECK(q.publish({1,1,2}));auto out=q.take_through(2);CHECK(out.size()==2&&out[0].sequence==1&&out[1].sequence==2);CHECK(q.buffered_samples()==0);return failures;}''',
        r'''int main(){AudioFrameWindow q(4);CHECK(!q.publish({0,1,1}));CHECK(q.publish({1,1,4}));CHECK(!q.publish({1,1,1}));CHECK(q.seal(2));CHECK(!q.publish({1,2,1}));CHECK(q.take_through(2).empty());return failures;}''',
        r'''int main(){AudioFrameWindow q(6);CHECK(q.publish({4,3,1}));CHECK(q.publish({4,1,2}));CHECK(q.publish({4,2,3}));auto x=q.take_through(3);CHECK(x==std::vector<AudioFrame>{{4,1,2},{4,2,3},{4,3,1}});return failures;}''',
        "if(end<next_)return{};",
        "if(end>=next_)return{};",
        "contiguous-prefix implementation refuses every forward watermark",
    ),
    _case(
        "bbq-build-worker-pool", "bbq-build-worker-pool-v2", "DependencyBuildPool",
        "Admit a bounded dependency graph and release the earliest submitted ready job.",
        "Jobs have unique positive IDs and known, distinct prerequisites. Self-dependencies, unknown prerequisites, and dependency cycles are rejected. Taking waits for a ready job and uses submission order; completion is unique and unlocks dependents.",
        "dependency DAG readiness scheduler", "std::all_of(j.prerequisites.begin()",
        r'''struct BuildJob { int id; std::vector<int> prerequisites; };
class DependencyBuildPool { public: explicit DependencyBuildPool(std::size_t capacity); bool submit(BuildJob job); std::optional<int> take_ready(); bool complete(int job_id); void close(); private: bool ready(const BuildJob&) const; std::size_t capacity_; bool closed_=false; std::deque<int> order_; std::map<int,BuildJob> jobs_; std::set<int> known_; std::set<int> completed_; std::set<int> running_; std::mutex mutex_; std::condition_variable changed_; std::condition_variable space_; };''',
        r'''DependencyBuildPool::DependencyBuildPool(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
bool DependencyBuildPool::ready(const BuildJob& j)const{return std::all_of(j.prerequisites.begin(),j.prerequisites.end(),[&](int d){return completed_.count(d);});}
bool DependencyBuildPool::submit(BuildJob j){if(j.id<=0||std::find(j.prerequisites.begin(),j.prerequisites.end(),j.id)!=j.prerequisites.end())return false;std::unique_lock<std::mutex> l(mutex_);if(known_.count(j.id)||!std::all_of(j.prerequisites.begin(),j.prerequisites.end(),[&](int d){return known_.count(d)>0;}))return false;space_.wait(l,[&]{return closed_||jobs_.size()<capacity_;});if(closed_)return false;known_.insert(j.id);order_.push_back(j.id);jobs_[j.id]=std::move(j);l.unlock();changed_.notify_all();return true;}
std::optional<int> DependencyBuildPool::take_ready(){std::unique_lock<std::mutex> l(mutex_);changed_.wait(l,[&]{return closed_||std::any_of(order_.begin(),order_.end(),[&](int id){return ready(jobs_.at(id));});});auto it=std::find_if(order_.begin(),order_.end(),[&](int id){return ready(jobs_.at(id));});if(it==order_.end())return std::nullopt;int id=*it;order_.erase(it);jobs_.erase(id);running_.insert(id);l.unlock();space_.notify_one();return id;}
bool DependencyBuildPool::complete(int id){std::lock_guard<std::mutex> l(mutex_);if(!running_.erase(id))return false;completed_.insert(id);changed_.notify_all();return true;}
void DependencyBuildPool::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;changed_.notify_all();space_.notify_all();}''',
        r'''int main(){DependencyBuildPool q(3);CHECK(q.submit({1,{}}));CHECK(q.submit({2,{1}}));CHECK(q.take_ready()==1);CHECK(q.complete(1));CHECK(q.take_ready()==2);return failures;}''',
        r'''int main(){DependencyBuildPool q(2);CHECK(!q.submit({2,{9}}));CHECK(!q.submit({1,{1}}));CHECK(q.submit({1,{}}));CHECK(!q.submit({1,{}}));q.close();CHECK(!q.submit({3,{1}}));return failures;}''',
        r'''int main(){DependencyBuildPool q(4);CHECK(q.submit({1,{}}));CHECK(q.submit({2,{1}}));CHECK(q.take_ready()==1);q.close();CHECK(!q.take_ready());CHECK(q.complete(1));CHECK(q.take_ready()==2);return failures;}''',
        "return std::all_of(j.prerequisites.begin(),j.prerequisites.end(),[&](int d){return completed_.count(d);});",
        "return j.id>0;",
        "plain FIFO ignores prerequisite readiness",
    ),
    _case(
        "bbq-customer-support", "bbq-customer-support-v2", "TenantFairIntake",
        "Dispatch bounded tenant queues with deterministic weighted deficit round robin.",
        "Weights, tenant IDs, ticket IDs, and costs are positive. Total capacity bounds all tenants. Dispatch preserves FIFO within a tenant, accrues configured quantum during rotation, and returns the first affordable head.",
        "weighted deficit round robin", "deficit_[tenant] += weights_[tenant]",
        r'''struct SupportTicket { int tenant; int id; int cost; bool operator==(const SupportTicket& x)const{return tenant==x.tenant&&id==x.id&&cost==x.cost;} };
class TenantFairIntake { public: explicit TenantFairIntake(std::size_t capacity); bool set_weight(int tenant,int weight); bool open(SupportTicket ticket); std::optional<SupportTicket> take_fair(); void close(); private: std::size_t capacity_;std::size_t pending_=0,cursor_=0;bool closed_=false;std::vector<int> rotation_;std::map<int,int> weights_,deficit_;std::map<int,std::deque<SupportTicket>> queues_;std::mutex mutex_;std::condition_variable work_,space_; };''',
        r'''TenantFairIntake::TenantFairIntake(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
bool TenantFairIntake::set_weight(int t,int w){if(t<=0||w<=0)return false;std::lock_guard<std::mutex> l(mutex_);if(weights_.count(t))return false;weights_[t]=w;deficit_[t]=0;rotation_.push_back(t);return true;}
bool TenantFairIntake::open(SupportTicket x){if(x.tenant<=0||x.id<=0||x.cost<=0)return false;std::unique_lock<std::mutex> l(mutex_);if(!weights_.count(x.tenant))return false;for(const auto& row:queues_)if(std::any_of(row.second.begin(),row.second.end(),[&](const auto& v){return v.id==x.id;}))return false;space_.wait(l,[&]{return closed_||pending_<capacity_;});if(closed_)return false;queues_[x.tenant].push_back(x);++pending_;l.unlock();work_.notify_all();return true;}
std::optional<SupportTicket> TenantFairIntake::take_fair(){std::unique_lock<std::mutex> l(mutex_);work_.wait(l,[&]{return closed_||pending_>0;});if(!pending_)return std::nullopt;for(std::size_t rounds=0;rounds<rotation_.size()*8;++rounds){int tenant=rotation_[cursor_++%rotation_.size()];deficit_[tenant]+=weights_[tenant];auto& q=queues_[tenant];if(!q.empty()&&q.front().cost<=deficit_[tenant]){auto x=q.front();q.pop_front();deficit_[tenant]-=x.cost;--pending_;l.unlock();space_.notify_one();return x;}}return std::nullopt;}
void TenantFairIntake::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;work_.notify_all();space_.notify_all();}''',
        r'''int main(){TenantFairIntake q(4);CHECK(q.set_weight(1,1));CHECK(q.set_weight(2,3));CHECK(q.open({1,10,2}));CHECK(q.open({2,20,2}));CHECK(q.take_fair()->id==20);CHECK(q.take_fair()->id==10);return failures;}''',
        r'''int main(){TenantFairIntake q(2);CHECK(!q.set_weight(0,1));CHECK(q.set_weight(1,2));CHECK(!q.open({9,1,1}));CHECK(q.open({1,1,1}));CHECK(!q.open({1,1,1}));q.close();CHECK(!q.open({1,2,1}));return failures;}''',
        r'''int main(){TenantFairIntake q(5);CHECK(q.set_weight(1,1));CHECK(q.set_weight(2,2));CHECK(q.open({1,1,3}));CHECK(q.open({2,2,2}));CHECK(q.open({2,3,2}));CHECK(q.take_fair()->id==2);CHECK(q.take_fair()->id==3);CHECK(q.take_fair()->id==1);return failures;}''',
        "deficit_[tenant]+=weights_[tenant];",
        "deficit_[tenant]+=1;",
        "global FIFO or constant quantum defeats weighted deficit fairness",
    ),
    _case(
        "bbq-database-write-behind", "bbq-database-write-behind-v2", "CoalescingWriteQueue",
        "Coalesce pending mutations per key while preserving first-key admission order.",
        "Capacity counts distinct pending keys. A higher version for an existing key merges its delta without a slot and retains the key's position. Stale versions fail. Taking removes the oldest key and returns its latest version and combined delta.",
        "first-key ordered coalescing map", "it->second.delta+=m.delta",
        r'''struct Mutation { int key;int version;int delta;bool operator==(const Mutation& x)const{return key==x.key&&version==x.version&&delta==x.delta;} };
class CoalescingWriteQueue { public: explicit CoalescingWriteQueue(std::size_t key_capacity);bool enqueue(Mutation mutation);std::optional<Mutation> take_oldest_key();void close();std::size_t pending_keys()const;private:std::size_t capacity_;bool closed_=false;std::deque<int> order_;std::map<int,Mutation> pending_;mutable std::mutex mutex_;std::condition_variable work_,space_;};''',
        r'''CoalescingWriteQueue::CoalescingWriteQueue(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
bool CoalescingWriteQueue::enqueue(Mutation m){if(m.key<=0||m.version<=0)return false;std::unique_lock<std::mutex> l(mutex_);auto it=pending_.find(m.key);if(it!=pending_.end()){if(m.version<=it->second.version)return false;it->second.delta+=m.delta;it->second.version=m.version;return true;}space_.wait(l,[&]{return closed_||pending_.size()<capacity_;});if(closed_)return false;order_.push_back(m.key);pending_[m.key]=m;l.unlock();work_.notify_one();return true;}
std::optional<Mutation> CoalescingWriteQueue::take_oldest_key(){std::unique_lock<std::mutex> l(mutex_);work_.wait(l,[&]{return closed_||!order_.empty();});if(order_.empty())return std::nullopt;int key=order_.front();order_.pop_front();Mutation out=pending_.at(key);pending_.erase(key);l.unlock();space_.notify_one();return out;}
void CoalescingWriteQueue::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;work_.notify_all();space_.notify_all();}
std::size_t CoalescingWriteQueue::pending_keys()const{std::lock_guard<std::mutex> l(mutex_);return pending_.size();}''',
        r'''int main(){CoalescingWriteQueue q(2);CHECK(q.enqueue({7,1,3}));CHECK(q.enqueue({8,1,4}));CHECK(q.enqueue({7,2,-1}));CHECK(q.take_oldest_key()==Mutation{7,2,2});CHECK(q.take_oldest_key()==Mutation{8,1,4});return failures;}''',
        r'''int main(){CoalescingWriteQueue q(1);CHECK(!q.enqueue({0,1,1}));CHECK(q.enqueue({1,2,5}));CHECK(!q.enqueue({1,2,7}));q.close();CHECK(!q.enqueue({2,1,1}));return failures;}''',
        r'''int main(){CoalescingWriteQueue q(3);CHECK(q.enqueue({3,1,1}));CHECK(q.enqueue({1,1,2}));CHECK(q.enqueue({3,4,8}));CHECK(q.pending_keys()==2);auto x=q.take_oldest_key();CHECK(x->key==3&&x->delta==9&&x->version==4);return failures;}''',
        "it->second.delta+=m.delta;it->second.version=m.version;return true;",
        "order_.push_back(m.key);pending_[m.key]=m;return true;",
        "append-only handling emits multiple rows for one pending key",
    ),
    _case(
        "bbq-document-indexer", "bbq-document-indexer-v2", "GenerationIndexQueue",
        "Keep only the newest pending generation per document and order replacements by epoch.",
        "Schedules require positive strictly increasing generations. Replacing a pending document moves it to the newest epoch without increasing occupancy. New documents block at capacity. Taking removes the oldest surviving epoch.",
        "generation supersession epoch queue", "order_.erase(std::find(order_.begin()",
        r'''struct IndexRequest{int document;int generation;bool operator==(const IndexRequest& x)const{return document==x.document&&generation==x.generation;}};enum class ScheduleResult{accepted,replaced,stale,closed};
class GenerationIndexQueue{public:explicit GenerationIndexQueue(std::size_t capacity);ScheduleResult schedule(IndexRequest request);std::optional<IndexRequest> take_latest();void close();private:std::size_t capacity_;bool closed_=false;std::deque<int> order_;std::map<int,IndexRequest> pending_;std::map<int,int> last_;std::mutex mutex_;std::condition_variable work_,space_;};''',
        r'''GenerationIndexQueue::GenerationIndexQueue(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
ScheduleResult GenerationIndexQueue::schedule(IndexRequest r){if(r.document<=0||r.generation<=0)return ScheduleResult::stale;std::unique_lock<std::mutex> l(mutex_);if(r.generation<=last_[r.document])return ScheduleResult::stale;if(closed_)return ScheduleResult::closed;last_[r.document]=r.generation;if(pending_.count(r.document)){order_.erase(std::find(order_.begin(),order_.end(),r.document));order_.push_back(r.document);pending_[r.document]=r;return ScheduleResult::replaced;}space_.wait(l,[&]{return closed_||pending_.size()<capacity_;});if(closed_)return ScheduleResult::closed;order_.push_back(r.document);pending_[r.document]=r;l.unlock();work_.notify_one();return ScheduleResult::accepted;}
std::optional<IndexRequest> GenerationIndexQueue::take_latest(){std::unique_lock<std::mutex> l(mutex_);work_.wait(l,[&]{return closed_||!order_.empty();});if(order_.empty())return std::nullopt;int d=order_.front();order_.pop_front();auto out=pending_.at(d);pending_.erase(d);l.unlock();space_.notify_one();return out;}
void GenerationIndexQueue::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;work_.notify_all();space_.notify_all();}''',
        r'''int main(){GenerationIndexQueue q(2);CHECK(q.schedule({1,1})==ScheduleResult::accepted);CHECK(q.schedule({2,1})==ScheduleResult::accepted);CHECK(q.schedule({1,2})==ScheduleResult::replaced);CHECK(q.take_latest()==IndexRequest{2,1});CHECK(q.take_latest()==IndexRequest{1,2});return failures;}''',
        r'''int main(){GenerationIndexQueue q(1);CHECK(q.schedule({0,1})==ScheduleResult::stale);CHECK(q.schedule({1,3})==ScheduleResult::accepted);CHECK(q.schedule({1,2})==ScheduleResult::stale);q.close();CHECK(q.schedule({2,1})==ScheduleResult::closed);return failures;}''',
        r'''int main(){GenerationIndexQueue q(3);CHECK(q.schedule({8,1})==ScheduleResult::accepted);CHECK(q.schedule({9,1})==ScheduleResult::accepted);CHECK(q.schedule({8,4})==ScheduleResult::replaced);CHECK(q.take_latest()->document==9);CHECK(q.take_latest()==IndexRequest{8,4});return failures;}''',
        "order_.erase(std::find(order_.begin(),order_.end(),r.document));order_.push_back(r.document);",
        "pending_[r.document]=r;",
        "replacement fails to move the superseded document to its new epoch",
    ),
    _case(
        "bbq-email-delivery", "bbq-email-delivery-v2", "LogicalRetryWheel",
        "Schedule bounded mail attempts on logical time and drain due buckets deterministically.",
        "IDs are unique while pending and due ticks cannot precede current logical time. Time advances monotonically. Taking waits for a due bucket or closure and drains due tick then insertion order up to a positive limit.",
        "logical-time retry bucket wheel", "buckets_.begin()->first<=now_",
        r'''struct MailAttempt{int id;int due_tick;};class LogicalRetryWheel{public:explicit LogicalRetryWheel(std::size_t capacity);bool schedule(MailAttempt attempt);bool advance_to(int tick);std::vector<int> take_due(std::size_t limit);bool cancel(int id);void close();private:std::size_t capacity_,pending_=0;int now_=0;bool closed_=false;std::map<int,std::deque<int>> buckets_;std::map<int,int> by_id_;std::mutex mutex_;std::condition_variable due_,space_;};''',
        r'''LogicalRetryWheel::LogicalRetryWheel(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
bool LogicalRetryWheel::schedule(MailAttempt a){if(a.id<=0)return false;std::unique_lock<std::mutex> l(mutex_);if(a.due_tick<now_||by_id_.count(a.id))return false;space_.wait(l,[&]{return closed_||pending_<capacity_;});if(closed_)return false;buckets_[a.due_tick].push_back(a.id);by_id_[a.id]=a.due_tick;++pending_;l.unlock();due_.notify_all();return true;}
bool LogicalRetryWheel::advance_to(int t){std::lock_guard<std::mutex> l(mutex_);if(t<now_)return false;now_=t;due_.notify_all();return true;}
std::vector<int> LogicalRetryWheel::take_due(std::size_t n){if(!n)return{};std::unique_lock<std::mutex> l(mutex_);due_.wait(l,[&]{return closed_||(!buckets_.empty()&&buckets_.begin()->first<=now_);});std::vector<int> out;while(n&&!buckets_.empty()&&buckets_.begin()->first<=now_){auto it=buckets_.begin();while(n&&!it->second.empty()){int id=it->second.front();it->second.pop_front();by_id_.erase(id);--pending_;--n;out.push_back(id);}if(it->second.empty())buckets_.erase(it);}l.unlock();space_.notify_all();return out;}
bool LogicalRetryWheel::cancel(int id){std::lock_guard<std::mutex> l(mutex_);auto pos=by_id_.find(id);if(pos==by_id_.end())return false;auto& q=buckets_[pos->second];q.erase(std::find(q.begin(),q.end(),id));if(q.empty())buckets_.erase(pos->second);by_id_.erase(pos);--pending_;space_.notify_one();return true;}
void LogicalRetryWheel::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;due_.notify_all();space_.notify_all();}''',
        r'''int main(){LogicalRetryWheel q(4);CHECK(q.schedule({1,5}));CHECK(q.schedule({2,3}));CHECK(q.advance_to(3));CHECK(q.take_due(2)==std::vector<int>{2});CHECK(q.advance_to(5));CHECK(q.take_due(2)==std::vector<int>{1});return failures;}''',
        r'''int main(){LogicalRetryWheel q(2);CHECK(q.advance_to(4));CHECK(!q.schedule({1,3}));CHECK(q.schedule({1,4}));CHECK(!q.schedule({1,5}));CHECK(q.cancel(1));CHECK(!q.cancel(1));q.close();CHECK(!q.schedule({2,4}));return failures;}''',
        r'''int main(){LogicalRetryWheel q(5);CHECK(q.schedule({4,8}));CHECK(q.schedule({2,7}));CHECK(q.schedule({3,7}));CHECK(q.advance_to(8));CHECK(q.take_due(3)==std::vector<int>({2,3,4}));return failures;}''',
        "buckets_[a.due_tick].push_back(a.id);",
        "buckets_[a.due_tick].push_front(a.id);",
        "same-tick mail attempts are released in reverse insertion order",
    ),
    _case(
        "bbq-file-scan", "bbq-file-scan-v2", "RootQuotaScanner",
        "Dispatch paths round-robin across registered roots under global and per-root bounds.",
        "Roots and paths are positive and roots register once with a positive quota. Submission blocks when either the root quota or global bound is full. Taking rotates roots, skips empties, and preserves per-root FIFO.",
        "quota-bound round-robin root scanner", "cursor_=(index+1)%roots_.size()",
        r'''struct ScanPath{int root;int path;bool operator==(const ScanPath& x)const{return root==x.root&&path==x.path;}};class RootQuotaScanner{public:explicit RootQuotaScanner(std::size_t global_capacity);bool add_root(int root,std::size_t quota);bool submit(ScanPath path);std::optional<ScanPath> take_next();bool retire_root(int root);void close();private:std::size_t capacity_,pending_=0,cursor_=0;bool closed_=false;std::vector<int> roots_;std::map<int,std::size_t> quotas_;std::map<int,std::deque<int>> queues_;std::mutex mutex_;std::condition_variable work_,space_;};''',
        r'''RootQuotaScanner::RootQuotaScanner(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
bool RootQuotaScanner::add_root(int r,std::size_t q){if(r<=0||!q)return false;std::lock_guard<std::mutex> l(mutex_);if(quotas_.count(r))return false;roots_.push_back(r);quotas_[r]=q;return true;}
bool RootQuotaScanner::submit(ScanPath x){if(x.root<=0||x.path<=0)return false;std::unique_lock<std::mutex> l(mutex_);if(!quotas_.count(x.root))return false;space_.wait(l,[&]{return closed_||(pending_<capacity_&&queues_[x.root].size()<quotas_[x.root]);});if(closed_)return false;queues_[x.root].push_back(x.path);++pending_;l.unlock();work_.notify_one();return true;}
std::optional<ScanPath> RootQuotaScanner::take_next(){std::unique_lock<std::mutex> l(mutex_);work_.wait(l,[&]{return closed_||pending_;});if(!pending_)return std::nullopt;for(std::size_t n=0;n<roots_.size();++n){std::size_t index=(cursor_+n)%roots_.size();int r=roots_[index];if(!queues_[r].empty()){int p=queues_[r].front();queues_[r].pop_front();--pending_;cursor_=(index+1)%roots_.size();l.unlock();space_.notify_all();return ScanPath{r,p};}}return std::nullopt;}
bool RootQuotaScanner::retire_root(int r){std::lock_guard<std::mutex> l(mutex_);if(!quotas_.count(r)||!queues_[r].empty())return false;quotas_.erase(r);roots_.erase(std::remove(roots_.begin(),roots_.end(),r),roots_.end());cursor_=0;return true;}
void RootQuotaScanner::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;work_.notify_all();space_.notify_all();}''',
        r'''int main(){RootQuotaScanner q(5);CHECK(q.add_root(1,3));CHECK(q.add_root(2,2));CHECK(q.submit({1,10}));CHECK(q.submit({1,11}));CHECK(q.submit({2,20}));CHECK(q.take_next()==ScanPath{1,10});CHECK(q.take_next()==ScanPath{2,20});CHECK(q.take_next()==ScanPath{1,11});return failures;}''',
        r'''int main(){RootQuotaScanner q(2);CHECK(!q.add_root(0,1));CHECK(q.add_root(1,1));CHECK(!q.add_root(1,2));CHECK(!q.submit({9,1}));CHECK(q.retire_root(1));CHECK(!q.submit({1,2}));q.close();return failures;}''',
        r'''int main(){RootQuotaScanner q(6);CHECK(q.add_root(3,3));CHECK(q.add_root(4,3));CHECK(q.submit({3,1}));CHECK(q.submit({3,2}));CHECK(q.submit({4,8}));CHECK(q.take_next()->root==3);CHECK(q.take_next()->root==4);return failures;}''',
        "cursor_=(index+1)%roots_.size();",
        "cursor_=0;",
        "global FIFO never advances a per-root round-robin cursor",
    ),
    _case(
        "bbq-fraud-review", "bbq-fraud-review-v2", "AgingFraudQueue",
        "Select cases by score promoted through deterministic logical aging.",
        "IDs and scores are positive, arrivals cannot exceed the selection epoch, and logical epochs never move backward. Effective score is base score plus completed aging intervals; ties use earlier arrival then smaller ID.",
        "logical-age promoted selection", "x.score+(epoch-x.arrival_epoch)/aging_",
        r'''struct FraudCase{int id;int score;int arrival_epoch;};class AgingFraudQueue{public:explicit AgingFraudQueue(std::size_t capacity,int aging_step);bool submit(FraudCase item);std::optional<FraudCase> take_at(int epoch);void close();private:std::size_t capacity_;int aging_,now_=0;bool closed_=false;std::vector<FraudCase> cases_;std::set<int> ids_;std::mutex mutex_;std::condition_variable work_,space_;};''',
        r'''AgingFraudQueue::AgingFraudQueue(std::size_t n,int a):capacity_(n),aging_(a){if(!n||a<=0)throw std::invalid_argument("configuration");}
bool AgingFraudQueue::submit(FraudCase x){if(x.id<=0||x.score<=0||x.arrival_epoch<0)return false;std::unique_lock<std::mutex> l(mutex_);if(ids_.count(x.id)||x.arrival_epoch<now_)return false;space_.wait(l,[&]{return closed_||cases_.size()<capacity_;});if(closed_)return false;ids_.insert(x.id);cases_.push_back(x);l.unlock();work_.notify_one();return true;}
std::optional<FraudCase> AgingFraudQueue::take_at(int epoch){std::unique_lock<std::mutex> l(mutex_);if(epoch<now_)return std::nullopt;now_=epoch;work_.wait(l,[&]{return closed_||!cases_.empty();});if(cases_.empty())return std::nullopt;auto better=[&](const FraudCase& x,const FraudCase& y){int ex=x.score+(epoch-x.arrival_epoch)/aging_,ey=y.score+(epoch-y.arrival_epoch)/aging_;return ex!=ey?ex>ey:(x.arrival_epoch!=y.arrival_epoch?x.arrival_epoch<y.arrival_epoch:x.id<y.id);};auto it=std::max_element(cases_.begin(),cases_.end(),[&](const auto& x,const auto& y){return better(y,x);});FraudCase out=*it;ids_.erase(out.id);cases_.erase(it);l.unlock();space_.notify_one();return out;}
void AgingFraudQueue::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;work_.notify_all();space_.notify_all();}''',
        r'''int main(){AgingFraudQueue q(4,2);CHECK(q.submit({1,5,0}));CHECK(q.submit({2,7,4}));CHECK(q.take_at(4)->id==1);CHECK(q.take_at(4)->id==2);return failures;}''',
        r'''int main(){AgingFraudQueue q(2,3);CHECK(!q.submit({0,1,0}));CHECK(q.submit({1,2,0}));CHECK(!q.submit({1,3,0}));CHECK(q.take_at(5)->id==1);CHECK(!q.take_at(4));q.close();return failures;}''',
        r'''int main(){AgingFraudQueue q(3,2);CHECK(q.submit({9,4,0}));CHECK(q.submit({3,5,4}));CHECK(q.submit({4,5,4}));CHECK(q.take_at(6)->id==9);CHECK(q.take_at(6)->id==3);return failures;}''',
        "int ex=x.score+(epoch-x.arrival_epoch)/aging_,ey=y.score+(epoch-y.arrival_epoch)/aging_;",
        "int ex=x.score,ey=y.score;",
        "static priority ignores deterministic age promotion",
    ),
    _case(
        "bbq-image-upload", "bbq-image-upload-v2", "UploadReservationQueue",
        "Reserve byte budget separately from commit order and dispatch only committed uploads.",
        "Reservations use positive unique IDs and nonzero bytes no larger than the total budget. Reserve blocks on bytes. Commit is one-shot. Taking selects the earliest committed reservation while skipping earlier uncommitted reservations. Cancellation releases bytes.",
        "two-phase byte reservation queue", "committed_.count(id)",
        r'''struct UploadReservation{int id;std::size_t bytes;bool operator==(const UploadReservation& x)const{return id==x.id&&bytes==x.bytes;}};class UploadReservationQueue{public:explicit UploadReservationQueue(std::size_t byte_budget);bool reserve(UploadReservation reservation);bool commit(int id);bool cancel(int id);std::optional<UploadReservation> take_committed();void close();private:std::size_t budget_,used_=0;bool closed_=false;std::deque<int> order_;std::map<int,UploadReservation> reserved_;std::set<int> committed_;std::mutex mutex_;std::condition_variable ready_,space_;};''',
        r'''UploadReservationQueue::UploadReservationQueue(std::size_t n):budget_(n){if(!n)throw std::invalid_argument("budget");}
bool UploadReservationQueue::reserve(UploadReservation r){if(r.id<=0||!r.bytes||r.bytes>budget_)return false;std::unique_lock<std::mutex> l(mutex_);if(reserved_.count(r.id))return false;space_.wait(l,[&]{return closed_||used_+r.bytes<=budget_;});if(closed_)return false;used_+=r.bytes;order_.push_back(r.id);reserved_[r.id]=r;return true;}
bool UploadReservationQueue::commit(int id){std::lock_guard<std::mutex> l(mutex_);if(closed_||!reserved_.count(id)||!committed_.insert(id).second)return false;ready_.notify_one();return true;}
bool UploadReservationQueue::cancel(int id){std::lock_guard<std::mutex> l(mutex_);auto it=reserved_.find(id);if(it==reserved_.end())return false;used_-=it->second.bytes;reserved_.erase(it);committed_.erase(id);order_.erase(std::find(order_.begin(),order_.end(),id));space_.notify_all();return true;}
std::optional<UploadReservation> UploadReservationQueue::take_committed(){std::unique_lock<std::mutex> l(mutex_);ready_.wait(l,[&]{return closed_||std::any_of(order_.begin(),order_.end(),[&](int id){return committed_.count(id);});});auto it=std::find_if(order_.begin(),order_.end(),[&](int id){return committed_.count(id);});if(it==order_.end())return std::nullopt;int id=*it;order_.erase(it);auto out=reserved_.at(id);used_-=out.bytes;reserved_.erase(id);committed_.erase(id);l.unlock();space_.notify_all();return out;}
void UploadReservationQueue::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;ready_.notify_all();space_.notify_all();}''',
        r'''int main(){UploadReservationQueue q(10);CHECK(q.reserve({1,6}));CHECK(q.reserve({2,4}));CHECK(q.commit(2));CHECK(q.take_committed()==UploadReservation{2,4});CHECK(q.commit(1));CHECK(q.take_committed()==UploadReservation{1,6});return failures;}''',
        r'''int main(){UploadReservationQueue q(5);CHECK(!q.reserve({1,6}));CHECK(q.reserve({1,5}));CHECK(!q.reserve({1,1}));CHECK(!q.commit(9));CHECK(q.cancel(1));CHECK(!q.cancel(1));q.close();return failures;}''',
        r'''int main(){UploadReservationQueue q(9);CHECK(q.reserve({1,3}));CHECK(q.reserve({2,3}));CHECK(q.commit(2));CHECK(q.take_committed()->id==2);return failures;}''',
        "auto it=std::find_if(order_.begin(),order_.end(),[&](int id){return committed_.count(id);});",
        "auto it=std::find_if(order_.begin(),order_.end(),[&](int id){return reserved_.count(id);});",
        "uncommitted reservations become dispatchable",
    ),
    _case(
        "bbq-log-writer", "bbq-log-writer-v2", "ContiguousLogBuffer",
        "Reorder bounded log records and release only the next contiguous sequence prefix.",
        "Sequences and payloads are positive. Old and duplicate records fail; append blocks at item capacity. Taking waits for the next expected sequence, drains consecutive records up to a positive limit, and never skips a gap. A seal sets the final sequence once.",
        "contiguous sequence reorder buffer", "records_.find(next_)!=records_.end()",
        r'''struct LogRecord{int sequence;int payload;bool operator==(const LogRecord& x)const{return sequence==x.sequence&&payload==x.payload;}};class ContiguousLogBuffer{public:explicit ContiguousLogBuffer(std::size_t capacity,int first_sequence);bool append(LogRecord record);std::vector<LogRecord> take_contiguous(std::size_t limit);bool seal(int final_sequence);private:std::size_t capacity_;int next_,final_=0;bool sealed_=false;std::map<int,LogRecord> records_;std::mutex mutex_;std::condition_variable contiguous_,space_;};''',
        r'''ContiguousLogBuffer::ContiguousLogBuffer(std::size_t n,int first):capacity_(n),next_(first){if(!n||first<=0)throw std::invalid_argument("configuration");}
bool ContiguousLogBuffer::append(LogRecord r){if(r.sequence<=0||r.payload<=0)return false;std::unique_lock<std::mutex> l(mutex_);if(r.sequence<next_||records_.count(r.sequence)||(sealed_&&r.sequence>final_))return false;space_.wait(l,[&]{return sealed_||records_.size()<capacity_;});if(sealed_&&r.sequence>final_)return false;records_[r.sequence]=r;l.unlock();contiguous_.notify_all();return true;}
std::vector<LogRecord> ContiguousLogBuffer::take_contiguous(std::size_t n){if(!n)return{};std::unique_lock<std::mutex> l(mutex_);contiguous_.wait(l,[&]{return records_.find(next_)!=records_.end()||(sealed_&&next_>final_);});std::vector<LogRecord> out;while(n&&records_.count(next_)){out.push_back(records_.at(next_));records_.erase(next_++);--n;}l.unlock();space_.notify_all();return out;}
bool ContiguousLogBuffer::seal(int f){std::lock_guard<std::mutex> l(mutex_);if(sealed_||f<next_-1)return false;sealed_=true;final_=f;contiguous_.notify_all();space_.notify_all();return true;}''',
        r'''int main(){ContiguousLogBuffer q(4,1);CHECK(q.append({2,20}));CHECK(q.append({1,10}));CHECK(q.append({3,30}));CHECK(q.take_contiguous(5)==std::vector<LogRecord>({{1,10},{2,20},{3,30}}));return failures;}''',
        r'''int main(){ContiguousLogBuffer q(2,5);CHECK(!q.append({4,1}));CHECK(q.append({5,1}));CHECK(!q.append({5,2}));CHECK(q.seal(5));CHECK(!q.append({6,1}));CHECK(q.take_contiguous(0).empty());return failures;}''',
        r'''int main(){ContiguousLogBuffer q(3,7);CHECK(q.append({9,90}));CHECK(q.append({7,70}));CHECK(q.take_contiguous(3)==std::vector<LogRecord>{{7,70}});CHECK(q.append({8,80}));CHECK(q.take_contiguous(3)==std::vector<LogRecord>({{8,80},{9,90}}));return failures;}''',
        "while(n&&records_.count(next_))",
        "while(n&&!records_.empty())",
        "smallest-available draining skips a sequence gap",
    ),
    _case(
        "bbq-network-message-pump", "bbq-network-message-pump-v2", "CreditChannelPump",
        "Admit messages only when global space and channel credit are both available.",
        "Channels register once with positive credits. Sending consumes channel credit and global capacity. Taking rotates nonempty channels. Returned credit cannot exceed the configured maximum. IDs are unique within a channel.",
        "credit-gated rotating channel pump", "--available_[m.channel]",
        r'''struct ChannelMessage{int channel;int id;bool operator==(const ChannelMessage& x)const{return channel==x.channel&&id==x.id;}};class CreditChannelPump{public:explicit CreditChannelPump(std::size_t global_capacity);bool open_channel(int channel,std::size_t credits);bool send(ChannelMessage message);std::optional<ChannelMessage> take_any();bool return_credit(int channel);void close();private:std::size_t capacity_,pending_=0,cursor_=0;bool closed_=false;std::vector<int> channels_;std::map<int,std::size_t> maximum_,available_;std::map<int,std::deque<int>> queues_;std::mutex mutex_;std::condition_variable work_,credit_;};''',
        r'''CreditChannelPump::CreditChannelPump(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
bool CreditChannelPump::open_channel(int c,std::size_t n){if(c<=0||!n)return false;std::lock_guard<std::mutex> l(mutex_);if(maximum_.count(c))return false;channels_.push_back(c);maximum_[c]=available_[c]=n;return true;}
bool CreditChannelPump::send(ChannelMessage m){if(m.channel<=0||m.id<=0)return false;std::unique_lock<std::mutex> l(mutex_);if(!maximum_.count(m.channel)||std::find(queues_[m.channel].begin(),queues_[m.channel].end(),m.id)!=queues_[m.channel].end())return false;credit_.wait(l,[&]{return closed_||(pending_<capacity_&&available_[m.channel]>0);});if(closed_)return false;--available_[m.channel];queues_[m.channel].push_back(m.id);++pending_;l.unlock();work_.notify_one();return true;}
std::optional<ChannelMessage> CreditChannelPump::take_any(){std::unique_lock<std::mutex> l(mutex_);work_.wait(l,[&]{return closed_||pending_;});if(!pending_)return std::nullopt;for(std::size_t n=0;n<channels_.size();++n){std::size_t i=(cursor_+n)%channels_.size();int c=channels_[i];if(!queues_[c].empty()){int id=queues_[c].front();queues_[c].pop_front();--pending_;cursor_=(i+1)%channels_.size();credit_.notify_all();return ChannelMessage{c,id};}}return std::nullopt;}
bool CreditChannelPump::return_credit(int c){std::lock_guard<std::mutex> l(mutex_);if(!maximum_.count(c)||available_[c]>=maximum_[c])return false;++available_[c];credit_.notify_all();return true;}
void CreditChannelPump::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;work_.notify_all();credit_.notify_all();}''',
        r'''int main(){CreditChannelPump q(4);CHECK(q.open_channel(1,2));CHECK(q.open_channel(2,1));CHECK(q.send({1,10}));CHECK(q.send({2,20}));CHECK(q.take_any()==ChannelMessage{1,10});CHECK(q.take_any()==ChannelMessage{2,20});CHECK(q.return_credit(2));return failures;}''',
        r'''int main(){CreditChannelPump q(2);CHECK(!q.open_channel(0,1));CHECK(q.open_channel(1,1));CHECK(!q.open_channel(1,2));CHECK(!q.send({9,1}));CHECK(q.send({1,1}));CHECK(!q.return_credit(9));q.close();CHECK(!q.send({1,2}));return failures;}''',
        r'''int main(){CreditChannelPump q(5);CHECK(q.open_channel(1,2));CHECK(q.open_channel(2,2));CHECK(q.send({1,1}));CHECK(q.send({1,2}));CHECK(q.send({2,3}));CHECK(q.take_any()->channel==1);CHECK(q.take_any()->channel==2);CHECK(q.return_credit(1));return failures;}''',
        "cursor_=(i+1)%channels_.size();",
        "cursor_=0;",
        "channel-blind FIFO never rotates across channels",
    ),
    _case(
        "bbq-notification-delivery", "bbq-notification-delivery-v2", "BroadcastCursorQueue",
        "Publish a bounded shared log and advance independent subscriber cursors.",
        "Subscribers register once. Publications use contiguous sequences and block while capacity cannot be reclaimed because a subscriber still needs the oldest entry. Every subscriber receives every later entry once; advancing or unsubscribing reclaims the common prefix.",
        "multi-subscriber bounded cursor log", "minimum=std::min(minimum,cursor.second)",
        r'''struct Notification{int sequence;int payload;bool operator==(const Notification& x)const{return sequence==x.sequence&&payload==x.payload;}};class BroadcastCursorQueue{public:explicit BroadcastCursorQueue(std::size_t capacity);bool subscribe(int subscriber);bool publish(Notification item);std::optional<Notification> take(int subscriber);bool unsubscribe(int subscriber);void close();private:void reclaim();std::size_t capacity_;int next_=1,base_=1;bool closed_=false;std::deque<Notification> log_;std::map<int,int> cursors_;std::mutex mutex_;std::condition_variable data_,space_;};''',
        r'''BroadcastCursorQueue::BroadcastCursorQueue(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
bool BroadcastCursorQueue::subscribe(int s){if(s<=0)return false;std::lock_guard<std::mutex> l(mutex_);return cursors_.emplace(s,next_).second;}
void BroadcastCursorQueue::reclaim(){int minimum=next_;for(const auto& cursor:cursors_)minimum=std::min(minimum,cursor.second);while(base_<minimum&&!log_.empty()){log_.pop_front();++base_;}}
bool BroadcastCursorQueue::publish(Notification x){if(x.sequence<=0||x.payload<=0)return false;std::unique_lock<std::mutex> l(mutex_);if(x.sequence!=next_)return false;space_.wait(l,[&]{return closed_||log_.size()<capacity_;});if(closed_)return false;log_.push_back(x);++next_;l.unlock();data_.notify_all();return true;}
std::optional<Notification> BroadcastCursorQueue::take(int s){std::unique_lock<std::mutex> l(mutex_);if(!cursors_.count(s))return std::nullopt;data_.wait(l,[&]{return closed_||cursors_[s]<next_;});if(cursors_[s]>=next_)return std::nullopt;int seq=cursors_[s]++;auto out=log_.at(static_cast<std::size_t>(seq-base_));reclaim();l.unlock();space_.notify_all();return out;}
bool BroadcastCursorQueue::unsubscribe(int s){std::lock_guard<std::mutex> l(mutex_);if(!cursors_.erase(s))return false;reclaim();space_.notify_all();return true;}
void BroadcastCursorQueue::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;data_.notify_all();space_.notify_all();}''',
        r'''int main(){BroadcastCursorQueue q(3);CHECK(q.subscribe(1));CHECK(q.subscribe(2));CHECK(q.publish({1,9}));CHECK(q.take(1)==Notification{1,9});CHECK(q.take(2)==Notification{1,9});CHECK(q.publish({2,8}));return failures;}''',
        r'''int main(){BroadcastCursorQueue q(2);CHECK(!q.subscribe(0));CHECK(q.subscribe(1));CHECK(!q.subscribe(1));CHECK(!q.publish({2,1}));CHECK(!q.take(9));CHECK(q.unsubscribe(1));CHECK(!q.unsubscribe(1));q.close();return failures;}''',
        r'''int main(){BroadcastCursorQueue q(3);CHECK(q.subscribe(3));CHECK(q.subscribe(4));CHECK(q.publish({1,1}));CHECK(q.publish({2,2}));CHECK(q.take(3)->sequence==1);CHECK(q.take(3)->sequence==2);CHECK(q.take(4)->sequence==1);CHECK(q.take(4)->sequence==2);return failures;}''',
        "int seq=cursors_[s]++;",
        "int seq=cursors_[s];",
        "a subscriber cursor does not advance after delivery",
    ),
    _case(
        "bbq-order-kitchen", "bbq-order-kitchen-v2", "CompleteOrderAssembler",
        "Assemble multi-part orders and dispatch complete orders by first-part arrival.",
        "Part fields are positive, expected counts remain consistent, and duplicate parts fail. Capacity counts distinct orders. Taking skips incomplete orders, selects the earliest first-arrived complete order, and returns sorted part IDs.",
        "bounded multipart completion assembler", "parts_[order].size()==static_cast<std::size_t>(expected_[order])",
        r'''struct OrderPart{int order;int part;int expected_parts;};class CompleteOrderAssembler{public:explicit CompleteOrderAssembler(std::size_t order_capacity);bool add(OrderPart part);std::optional<std::vector<int>> take_complete();bool cancel(int order);void close();private:std::size_t capacity_;bool closed_=false;std::deque<int> arrival_;std::map<int,int> expected_;std::map<int,std::set<int>> parts_;std::mutex mutex_;std::condition_variable complete_,space_;};''',
        r'''CompleteOrderAssembler::CompleteOrderAssembler(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
bool CompleteOrderAssembler::add(OrderPart x){if(x.order<=0||x.part<=0||x.expected_parts<=0)return false;std::unique_lock<std::mutex> l(mutex_);if(expected_.count(x.order)){if(expected_[x.order]!=x.expected_parts||parts_[x.order].count(x.part))return false;}else{space_.wait(l,[&]{return closed_||expected_.size()<capacity_;});if(closed_)return false;expected_[x.order]=x.expected_parts;arrival_.push_back(x.order);}if(static_cast<int>(parts_[x.order].size())>=x.expected_parts)return false;parts_[x.order].insert(x.part);l.unlock();complete_.notify_all();return true;}
std::optional<std::vector<int>> CompleteOrderAssembler::take_complete(){std::unique_lock<std::mutex> l(mutex_);complete_.wait(l,[&]{return closed_||std::any_of(arrival_.begin(),arrival_.end(),[&](int order){return parts_[order].size()==static_cast<std::size_t>(expected_[order]);});});auto it=std::find_if(arrival_.begin(),arrival_.end(),[&](int order){return parts_[order].size()==static_cast<std::size_t>(expected_[order]);});if(it==arrival_.end())return std::nullopt;int order=*it;std::vector<int> out(parts_[order].begin(),parts_[order].end());arrival_.erase(it);parts_.erase(order);expected_.erase(order);l.unlock();space_.notify_one();return out;}
bool CompleteOrderAssembler::cancel(int order){std::lock_guard<std::mutex> l(mutex_);if(!expected_.erase(order))return false;parts_.erase(order);arrival_.erase(std::find(arrival_.begin(),arrival_.end(),order));space_.notify_one();return true;}
void CompleteOrderAssembler::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;complete_.notify_all();space_.notify_all();}''',
        r'''int main(){CompleteOrderAssembler q(3);CHECK(q.add({1,2,2}));CHECK(q.add({2,7,1}));CHECK(q.add({1,1,2}));CHECK(q.take_complete()==std::vector<int>{1,2});CHECK(q.take_complete()==std::vector<int>{7});return failures;}''',
        r'''int main(){CompleteOrderAssembler q(2);CHECK(!q.add({0,1,1}));CHECK(q.add({1,1,2}));CHECK(!q.add({1,1,2}));CHECK(!q.add({1,2,3}));CHECK(q.cancel(1));CHECK(!q.cancel(1));q.close();return failures;}''',
        r'''int main(){CompleteOrderAssembler q(3);CHECK(q.add({5,1,3}));CHECK(q.add({6,9,1}));CHECK(q.take_complete()==std::vector<int>{9});CHECK(q.add({5,2,3}));CHECK(q.add({5,3,3}));CHECK(q.take_complete()==std::vector<int>({1,2,3}));return failures;}''',
        "auto it=std::find_if(arrival_.begin(),arrival_.end(),[&](int order){return parts_[order].size()==static_cast<std::size_t>(expected_[order]);});",
        "auto it=std::find_if(arrival_.begin(),arrival_.end(),[&](int order){return !parts_[order].empty();});",
        "partial order is dispatched before all distinct parts arrive",
    ),
    _case(
        "bbq-payment-retry", "bbq-payment-retry-v2", "LeasedRetryQueue",
        "Lease retry jobs and reconcile acknowledgement, negative acknowledgement, and logical expiry.",
        "Jobs are unique and positive. Leasing uses positive worker, time, and TTL, moves FIFO-ready work in flight, and returns ownership. Ack frees capacity; nack appends to the ready tail; expire returns leases ordered by expiry then job. Time is monotonic.",
        "leased ready/in-flight retry scheduler", "lease.expires_at<=now",
        r'''struct RetryLease{int job;int worker;int expires_at;};class LeasedRetryQueue{public:explicit LeasedRetryQueue(std::size_t capacity);bool enqueue(int job);std::optional<RetryLease> lease(int worker,int now,int ttl);bool ack(int worker,int job);bool nack(int worker,int job);std::size_t expire(int now);void close();private:std::size_t capacity_;int now_=0;bool closed_=false;std::deque<int> ready_;std::map<int,RetryLease> inflight_;std::set<int> active_;std::mutex mutex_;std::condition_variable work_,space_;};''',
        r'''LeasedRetryQueue::LeasedRetryQueue(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
bool LeasedRetryQueue::enqueue(int job){if(job<=0)return false;std::unique_lock<std::mutex> l(mutex_);if(active_.count(job))return false;space_.wait(l,[&]{return closed_||active_.size()<capacity_;});if(closed_)return false;active_.insert(job);ready_.push_back(job);l.unlock();work_.notify_one();return true;}
std::optional<RetryLease> LeasedRetryQueue::lease(int worker,int now,int ttl){if(worker<=0||ttl<=0)return std::nullopt;std::unique_lock<std::mutex> l(mutex_);if(now<now_)return std::nullopt;now_=now;work_.wait(l,[&]{return closed_||!ready_.empty();});if(ready_.empty())return std::nullopt;int job=ready_.front();ready_.pop_front();RetryLease out{job,worker,now+ttl};inflight_[job]=out;return out;}
bool LeasedRetryQueue::ack(int worker,int job){std::lock_guard<std::mutex> l(mutex_);auto it=inflight_.find(job);if(it==inflight_.end()||it->second.worker!=worker)return false;inflight_.erase(it);active_.erase(job);space_.notify_one();return true;}
bool LeasedRetryQueue::nack(int worker,int job){std::lock_guard<std::mutex> l(mutex_);auto it=inflight_.find(job);if(it==inflight_.end()||it->second.worker!=worker)return false;inflight_.erase(it);ready_.push_back(job);work_.notify_one();return true;}
std::size_t LeasedRetryQueue::expire(int now){std::lock_guard<std::mutex> l(mutex_);if(now<now_)return 0;now_=now;std::vector<std::pair<int,int>> due;for(const auto& [job,lease]:inflight_)if(lease.expires_at<=now)due.push_back({lease.expires_at,job});std::sort(due.begin(),due.end());for(const auto& row:due){inflight_.erase(row.second);ready_.push_back(row.second);}if(!due.empty())work_.notify_all();return due.size();}
void LeasedRetryQueue::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;work_.notify_all();space_.notify_all();}''',
        r'''int main(){LeasedRetryQueue q(3);CHECK(q.enqueue(1));auto l=q.lease(7,10,5);CHECK(l&&l->job==1&&l->expires_at==15);CHECK(q.nack(7,1));CHECK(q.lease(8,11,2)->job==1);CHECK(q.ack(8,1));return failures;}''',
        r'''int main(){LeasedRetryQueue q(2);CHECK(!q.enqueue(0));CHECK(q.enqueue(1));CHECK(!q.enqueue(1));CHECK(!q.lease(0,0,1));auto l=q.lease(2,3,2);CHECK(l);CHECK(!q.ack(9,1));CHECK(q.expire(2)==0);q.close();return failures;}''',
        r'''int main(){LeasedRetryQueue q(4);CHECK(q.enqueue(4));CHECK(q.enqueue(3));CHECK(q.lease(1,10,5)->job==4);CHECK(q.lease(2,10,2)->job==3);CHECK(q.expire(12)==1);return failures;}''',
        "if(lease.expires_at<=now)due.push_back({lease.expires_at,job});",
        "if(false)due.push_back({lease.expires_at,job});",
        "pop-only queue never restores expired in-flight work",
    ),
    _case(
        "bbq-print-dispatch", "bbq-print-dispatch-v2", "PrinterAffinityDispatcher",
        "Assign jobs only to compatible least-served printers while retaining job age.",
        "Printers register unique positive IDs and nonzero capability masks. Jobs have unique IDs and nonzero requirements. Submission blocks at capacity. A compatible job is claimable only by the least-served compatible printer, printer ID breaking ties.",
        "least-served compatible printer ownership", "served_[p]++",
        r'''struct PrintJob{int id;unsigned required_mask;bool operator==(const PrintJob& x)const{return id==x.id&&required_mask==x.required_mask;}};class PrinterAffinityDispatcher{public:explicit PrinterAffinityDispatcher(std::size_t capacity);bool register_printer(int printer,unsigned capability_mask);bool submit(PrintJob job);std::optional<PrintJob> take_for(int printer);std::size_t served(int printer)const;void close();private:bool owns(int printer,const PrintJob& job)const;std::size_t capacity_;bool closed_=false;std::deque<PrintJob> jobs_;std::map<int,unsigned> capabilities_;std::map<int,std::size_t> served_;std::set<int> ids_;mutable std::mutex mutex_;std::condition_variable work_,space_;};''',
        r'''PrinterAffinityDispatcher::PrinterAffinityDispatcher(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
bool PrinterAffinityDispatcher::register_printer(int p,unsigned mask){if(p<=0||!mask)return false;std::lock_guard<std::mutex> l(mutex_);if(capabilities_.count(p))return false;capabilities_[p]=mask;served_[p]=0;return true;}
bool PrinterAffinityDispatcher::owns(int p,const PrintJob& j)const{if(!capabilities_.count(p)||(capabilities_.at(p)&j.required_mask)!=j.required_mask)return false;for(const auto& [other,mask]:capabilities_)if((mask&j.required_mask)==j.required_mask&&std::pair<std::size_t,int>{served_.at(other),other}<std::pair<std::size_t,int>{served_.at(p),p})return false;return true;}
bool PrinterAffinityDispatcher::submit(PrintJob j){if(j.id<=0||!j.required_mask)return false;std::unique_lock<std::mutex> l(mutex_);if(ids_.count(j.id)||std::none_of(capabilities_.begin(),capabilities_.end(),[&](const auto& row){return (row.second&j.required_mask)==j.required_mask;}))return false;space_.wait(l,[&]{return closed_||jobs_.size()<capacity_;});if(closed_)return false;jobs_.push_back(j);ids_.insert(j.id);l.unlock();work_.notify_all();return true;}
std::optional<PrintJob> PrinterAffinityDispatcher::take_for(int p){std::unique_lock<std::mutex> l(mutex_);if(!capabilities_.count(p))return std::nullopt;work_.wait(l,[&]{return closed_||std::any_of(jobs_.begin(),jobs_.end(),[&](const auto& j){return owns(p,j);});});auto it=std::find_if(jobs_.begin(),jobs_.end(),[&](const auto& j){return owns(p,j);});if(it==jobs_.end())return std::nullopt;auto out=*it;ids_.erase(out.id);jobs_.erase(it);served_[p]++;l.unlock();space_.notify_one();work_.notify_all();return out;}
std::size_t PrinterAffinityDispatcher::served(int p)const{std::lock_guard<std::mutex> l(mutex_);auto it=served_.find(p);return it==served_.end()?0:it->second;}
void PrinterAffinityDispatcher::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;work_.notify_all();space_.notify_all();}''',
        r'''int main(){PrinterAffinityDispatcher q(3);CHECK(q.register_printer(1,3));CHECK(q.register_printer(2,1));CHECK(q.submit({7,1}));CHECK(q.take_for(1)==PrintJob{7,1});CHECK(q.submit({8,1}));CHECK(q.take_for(2)==PrintJob{8,1});return failures;}''',
        r'''int main(){PrinterAffinityDispatcher q(2);CHECK(!q.register_printer(0,1));CHECK(q.register_printer(1,1));CHECK(!q.register_printer(1,2));CHECK(!q.submit({1,2}));CHECK(q.submit({1,1}));CHECK(!q.submit({1,1}));q.close();return failures;}''',
        r'''int main(){PrinterAffinityDispatcher q(4);CHECK(q.register_printer(1,3));CHECK(q.register_printer(2,3));CHECK(q.submit({1,1}));CHECK(q.take_for(1)->id==1);CHECK(q.submit({2,1}));CHECK(q.take_for(2)->id==2);CHECK(q.served(1)==1&&q.served(2)==1);return failures;}''',
        "auto it=served_.find(p);return it==served_.end()?0:it->second;",
        "(void)p;return 0;",
        "served-count ownership is not observable or maintained",
    ),
    _case(
        "bbq-route-calculation", "bbq-route-calculation-v2", "LatestRouteQueue",
        "Keep the latest version for each route key without changing first-key FIFO position.",
        "Origin and destination are positive and distinct; versions strictly increase per key. A pending replacement updates in place and uses no slot. A new key blocks at distinct-key capacity. Taking removes the oldest key with its latest version.",
        "latest-value stable-key FIFO", "pending_[key]=r",
        r'''struct RouteRequest{int origin;int destination;int version;bool operator==(const RouteRequest& x)const{return origin==x.origin&&destination==x.destination&&version==x.version;}};enum class RouteUpsert{inserted,replaced,stale,closed};class LatestRouteQueue{public:explicit LatestRouteQueue(std::size_t key_capacity);RouteUpsert upsert(RouteRequest request);std::optional<RouteRequest> take();void close();private:using Key=std::pair<int,int>;std::size_t capacity_;bool closed_=false;std::deque<Key> order_;std::map<Key,RouteRequest> pending_;std::map<Key,int> last_;std::mutex mutex_;std::condition_variable work_,space_;};''',
        r'''LatestRouteQueue::LatestRouteQueue(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
RouteUpsert LatestRouteQueue::upsert(RouteRequest r){if(r.origin<=0||r.destination<=0||r.origin==r.destination||r.version<=0)return RouteUpsert::stale;Key key{r.origin,r.destination};std::unique_lock<std::mutex> l(mutex_);if(r.version<=last_[key])return RouteUpsert::stale;if(closed_)return RouteUpsert::closed;last_[key]=r.version;if(pending_.count(key)){pending_[key]=r;return RouteUpsert::replaced;}space_.wait(l,[&]{return closed_||pending_.size()<capacity_;});if(closed_)return RouteUpsert::closed;order_.push_back(key);pending_[key]=r;l.unlock();work_.notify_one();return RouteUpsert::inserted;}
std::optional<RouteRequest> LatestRouteQueue::take(){std::unique_lock<std::mutex> l(mutex_);work_.wait(l,[&]{return closed_||!order_.empty();});if(order_.empty())return std::nullopt;Key key=order_.front();order_.pop_front();auto out=pending_.at(key);pending_.erase(key);l.unlock();space_.notify_one();return out;}
void LatestRouteQueue::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;work_.notify_all();space_.notify_all();}''',
        r'''int main(){LatestRouteQueue q(2);CHECK(q.upsert({1,2,1})==RouteUpsert::inserted);CHECK(q.upsert({3,4,1})==RouteUpsert::inserted);CHECK(q.upsert({1,2,2})==RouteUpsert::replaced);CHECK(q.take()==RouteRequest{1,2,2});CHECK(q.take()==RouteRequest{3,4,1});return failures;}''',
        r'''int main(){LatestRouteQueue q(1);CHECK(q.upsert({1,1,1})==RouteUpsert::stale);CHECK(q.upsert({1,2,3})==RouteUpsert::inserted);CHECK(q.upsert({1,2,2})==RouteUpsert::stale);q.close();CHECK(q.upsert({2,3,1})==RouteUpsert::closed);return failures;}''',
        r'''int main(){LatestRouteQueue q(3);CHECK(q.upsert({5,6,1})==RouteUpsert::inserted);CHECK(q.upsert({7,8,1})==RouteUpsert::inserted);CHECK(q.upsert({5,6,9})==RouteUpsert::replaced);CHECK(q.take()->origin==5);return failures;}''',
        "if(pending_.count(key)){pending_[key]=r;return RouteUpsert::replaced;}",
        "if(pending_.count(key)){order_.erase(std::find(order_.begin(),order_.end(),key));order_.push_back(key);pending_[key]=r;return RouteUpsert::replaced;}",
        "replacement moves a stable route key to the tail",
    ),
    _case(
        "bbq-sensor-fusion", "bbq-sensor-fusion-v2", "TimestampFusionBarrier",
        "Join one sample from every registered sensor at a shared timestamp.",
        "Sensors register once. Each sensor/timestamp cell is unique. Capacity counts distinct timestamps. Taking waits for a complete timestamp, selects the smallest complete time, and returns samples ordered by sensor. Retiring requires no pending cell for that sensor.",
        "multi-source timestamp join barrier", "row.second.size()==sensors_.size()",
        r'''struct SensorSample{int sensor;int timestamp;int value;bool operator==(const SensorSample& x)const{return sensor==x.sensor&&timestamp==x.timestamp&&value==x.value;}};class TimestampFusionBarrier{public:explicit TimestampFusionBarrier(std::size_t timestamp_capacity);bool register_sensor(int sensor);bool submit(SensorSample sample);std::optional<std::vector<SensorSample>> take_fused();bool retire_sensor(int sensor);void close();private:std::size_t capacity_;bool closed_=false;std::set<int> sensors_;std::map<int,std::map<int,SensorSample>> frames_;std::mutex mutex_;std::condition_variable complete_,space_;};''',
        r'''TimestampFusionBarrier::TimestampFusionBarrier(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
bool TimestampFusionBarrier::register_sensor(int s){if(s<=0)return false;std::lock_guard<std::mutex> l(mutex_);return sensors_.insert(s).second;}
bool TimestampFusionBarrier::submit(SensorSample x){if(x.sensor<=0||x.timestamp<=0)return false;std::unique_lock<std::mutex> l(mutex_);if(!sensors_.count(x.sensor)||frames_[x.timestamp].count(x.sensor))return false;if(!frames_.count(x.timestamp))space_.wait(l,[&]{return closed_||frames_.size()<capacity_;});if(closed_)return false;frames_[x.timestamp][x.sensor]=x;l.unlock();complete_.notify_all();return true;}
std::optional<std::vector<SensorSample>> TimestampFusionBarrier::take_fused(){std::unique_lock<std::mutex> l(mutex_);complete_.wait(l,[&]{return closed_||std::any_of(frames_.begin(),frames_.end(),[&](const auto& row){return row.second.size()==sensors_.size();});});auto it=std::find_if(frames_.begin(),frames_.end(),[&](const auto& row){return row.second.size()==sensors_.size();});if(it==frames_.end())return std::nullopt;std::vector<SensorSample> out;for(const auto& row:it->second)out.push_back(row.second);frames_.erase(it);l.unlock();space_.notify_one();return out;}
bool TimestampFusionBarrier::retire_sensor(int s){std::lock_guard<std::mutex> l(mutex_);if(!sensors_.count(s)||std::any_of(frames_.begin(),frames_.end(),[&](const auto& row){return row.second.count(s);}))return false;sensors_.erase(s);complete_.notify_all();return true;}
void TimestampFusionBarrier::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;complete_.notify_all();space_.notify_all();}''',
        r'''int main(){TimestampFusionBarrier q(3);CHECK(q.register_sensor(1));CHECK(q.register_sensor(2));CHECK(q.submit({2,5,20}));CHECK(q.submit({1,5,10}));CHECK(q.take_fused()==std::vector<SensorSample>({{1,5,10},{2,5,20}}));return failures;}''',
        r'''int main(){TimestampFusionBarrier q(2);CHECK(!q.register_sensor(0));CHECK(q.register_sensor(1));CHECK(!q.register_sensor(1));CHECK(!q.submit({9,1,1}));CHECK(q.submit({1,1,1}));CHECK(!q.submit({1,1,2}));CHECK(!q.retire_sensor(1));q.close();return failures;}''',
        r'''int main(){TimestampFusionBarrier q(4);CHECK(q.register_sensor(2));CHECK(q.register_sensor(1));CHECK(q.submit({1,8,1}));CHECK(q.submit({1,7,2}));CHECK(q.submit({2,8,3}));CHECK(q.submit({2,7,4}));CHECK(q.take_fused()->front().timestamp==7);return failures;}''',
        "for(const auto& row:it->second)out.push_back(row.second);",
        "for(auto row=it->second.rbegin();row!=it->second.rend();++row)out.push_back(row->second);",
        "fused samples are returned in reverse sensor order",
    ),
    _case(
        "bbq-telemetry-ingest", "bbq-telemetry-ingest-v2", "HysteresisTelemetryBuffer",
        "Apply high/low-watermark backpressure and drain complete pressure epochs.",
        "The constructor requires 0 < low < high. Positive readings append. Reaching high enters a paused phase; later producers wait until a drain reduces occupancy to low or closure. Draining waits for high or closure and removes FIFO down to low.",
        "high-low hysteresis buffer", "while(readings_.size()>low_)",
        r'''class HysteresisTelemetryBuffer{public:HysteresisTelemetryBuffer(std::size_t low,std::size_t high);bool push(int reading);std::vector<int> wait_and_drain();bool producer_paused()const;void close();private:std::size_t low_,high_;bool paused_=false,closed_=false;std::deque<int> readings_;mutable std::mutex mutex_;std::condition_variable high_water_,low_water_;};''',
        r'''HysteresisTelemetryBuffer::HysteresisTelemetryBuffer(std::size_t low,std::size_t high):low_(low),high_(high){if(!low||low>=high)throw std::invalid_argument("watermarks");}
bool HysteresisTelemetryBuffer::push(int x){if(x<=0)return false;std::unique_lock<std::mutex> l(mutex_);low_water_.wait(l,[&]{return closed_||!paused_;});if(closed_)return false;readings_.push_back(x);if(readings_.size()>=high_){paused_=true;high_water_.notify_one();}return true;}
std::vector<int> HysteresisTelemetryBuffer::wait_and_drain(){std::unique_lock<std::mutex> l(mutex_);high_water_.wait(l,[&]{return closed_||readings_.size()>=high_;});std::vector<int> out;while(readings_.size()>low_){out.push_back(readings_.front());readings_.pop_front();}if(paused_&&readings_.size()<=low_){paused_=false;low_water_.notify_all();}return out;}
bool HysteresisTelemetryBuffer::producer_paused()const{std::lock_guard<std::mutex> l(mutex_);return paused_;}
void HysteresisTelemetryBuffer::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;high_water_.notify_all();low_water_.notify_all();}''',
        r'''int main(){HysteresisTelemetryBuffer q(2,4);CHECK(q.push(1));CHECK(q.push(2));CHECK(q.push(3));CHECK(q.push(4));CHECK(q.producer_paused());CHECK(q.wait_and_drain()==std::vector<int>({1,2}));CHECK(!q.producer_paused());return failures;}''',
        r'''int main(){try{HysteresisTelemetryBuffer bad(2,2);CHECK(false);}catch(const std::invalid_argument&){}HysteresisTelemetryBuffer q(1,3);CHECK(!q.push(0));CHECK(q.push(1));q.close();CHECK(!q.push(2));CHECK(q.wait_and_drain().empty());return failures;}''',
        r'''int main(){HysteresisTelemetryBuffer q(1,3);CHECK(q.push(7));CHECK(q.push(8));CHECK(!q.producer_paused());CHECK(q.push(9));CHECK(q.producer_paused());CHECK(q.wait_and_drain()==std::vector<int>({7,8}));return failures;}''',
        "while(readings_.size()>low_)",
        "if(!readings_.empty())",
        "single-pop wakeup defeats low-water hysteresis",
    ),
    _case(
        "bbq-video-transcode", "bbq-video-transcode-v2", "StageBarrierPipeline",
        "Release an asset only when every segment has completed every stage in order.",
        "Assets, segments, counts, and stages are positive and consistent. A segment advances one stage at a time. Capacity counts distinct assets. Taking chooses first-arrived complete assets; cancellation frees a slot.",
        "per-segment multistage completion barrier", "stage_[key]+1!=x.stage",
        r'''struct SegmentStage{int asset;int segment;int segment_count;int stage;};class StageBarrierPipeline{public:StageBarrierPipeline(std::size_t asset_capacity,int final_stage);bool mark(SegmentStage mark);std::optional<int> take_complete_asset();bool cancel_asset(int asset);void close();private:bool complete(int asset)const;std::size_t capacity_;int final_stage_;bool closed_=false;std::deque<int> order_;std::map<int,int> counts_;std::map<std::pair<int,int>,int> stage_;std::mutex mutex_;std::condition_variable done_,space_;};''',
        r'''StageBarrierPipeline::StageBarrierPipeline(std::size_t n,int final):capacity_(n),final_stage_(final){if(!n||final<=0)throw std::invalid_argument("configuration");}
bool StageBarrierPipeline::mark(SegmentStage x){if(x.asset<=0||x.segment<=0||x.segment>x.segment_count||x.segment_count<=0||x.stage<=0||x.stage>final_stage_)return false;std::unique_lock<std::mutex> l(mutex_);if(!counts_.count(x.asset)){space_.wait(l,[&]{return closed_||counts_.size()<capacity_;});if(closed_)return false;counts_[x.asset]=x.segment_count;order_.push_back(x.asset);}if(counts_[x.asset]!=x.segment_count)return false;auto key=std::make_pair(x.asset,x.segment);if(stage_[key]+1!=x.stage)return false;stage_[key]=x.stage;l.unlock();done_.notify_all();return true;}
bool StageBarrierPipeline::complete(int asset)const{for(int segment=1;segment<=counts_.at(asset);++segment){auto it=stage_.find({asset,segment});if(it==stage_.end()||it->second!=final_stage_)return false;}return true;}
std::optional<int> StageBarrierPipeline::take_complete_asset(){std::unique_lock<std::mutex> l(mutex_);done_.wait(l,[&]{return closed_||std::any_of(order_.begin(),order_.end(),[&](int a){return complete(a);});});auto it=std::find_if(order_.begin(),order_.end(),[&](int a){return complete(a);});if(it==order_.end())return std::nullopt;int asset=*it;order_.erase(it);int count=counts_[asset];counts_.erase(asset);for(int s=1;s<=count;++s)stage_.erase({asset,s});l.unlock();space_.notify_one();return asset;}
bool StageBarrierPipeline::cancel_asset(int asset){std::lock_guard<std::mutex> l(mutex_);auto it=counts_.find(asset);if(it==counts_.end())return false;for(int s=1;s<=it->second;++s)stage_.erase({asset,s});counts_.erase(it);order_.erase(std::find(order_.begin(),order_.end(),asset));space_.notify_one();return true;}
void StageBarrierPipeline::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;done_.notify_all();space_.notify_all();}''',
        r'''int main(){StageBarrierPipeline q(2,2);CHECK(q.mark({1,1,2,1}));CHECK(q.mark({1,2,2,1}));CHECK(q.mark({1,2,2,2}));CHECK(q.mark({1,1,2,2}));CHECK(q.take_complete_asset()==1);return failures;}''',
        r'''int main(){StageBarrierPipeline q(2,2);CHECK(!q.mark({0,1,1,1}));CHECK(q.mark({1,1,2,1}));CHECK(!q.mark({1,1,2,1}));CHECK(!q.mark({1,2,3,1}));CHECK(q.cancel_asset(1));CHECK(!q.cancel_asset(1));StageBarrierPipeline partial(1,2);CHECK(partial.mark({3,1,2,1}));CHECK(partial.mark({3,1,2,2}));partial.close();CHECK(!partial.take_complete_asset());q.close();return failures;}''',
        r'''int main(){StageBarrierPipeline q(3,3);CHECK(q.mark({4,1,2,1}));CHECK(q.mark({4,2,2,1}));q.close();CHECK(!q.take_complete_asset());return failures;}''',
        "if(it==stage_.end()||it->second!=final_stage_)return false;",
        "if(it==stage_.end())return false;",
        "total marks substitute completes an asset while a segment lacks the final stage",
    ),
    _case(
        "bbq-warehouse-pick", "bbq-warehouse-pick-v2", "ZoneStealingPickQueue",
        "Serve local-zone work first and steal deterministically from the largest remote backlog.",
        "Zones register once. Tasks have globally unique positive IDs and submission blocks at global capacity. A worker consumes local FIFO first; otherwise it steals the head of the largest remote queue, smallest zone breaking ties.",
        "largest-backlog deterministic work stealing", "queues_[candidate].size()>best_size",
        r'''struct PickTask{int zone;int id;bool operator==(const PickTask& x)const{return zone==x.zone&&id==x.id;}};class ZoneStealingPickQueue{public:explicit ZoneStealingPickQueue(std::size_t global_capacity);bool add_zone(int zone);bool submit(PickTask task);std::optional<PickTask> take_for(int worker_zone);std::size_t pending(int zone)const;void close();private:std::size_t capacity_,total_=0;bool closed_=false;std::set<int> zones_,ids_;std::map<int,std::deque<int>> queues_;mutable std::mutex mutex_;std::condition_variable work_,space_;};''',
        r'''ZoneStealingPickQueue::ZoneStealingPickQueue(std::size_t n):capacity_(n){if(!n)throw std::invalid_argument("capacity");}
bool ZoneStealingPickQueue::add_zone(int z){if(z<=0)return false;std::lock_guard<std::mutex> l(mutex_);return zones_.insert(z).second;}
bool ZoneStealingPickQueue::submit(PickTask x){if(x.zone<=0||x.id<=0)return false;std::unique_lock<std::mutex> l(mutex_);if(!zones_.count(x.zone)||ids_.count(x.id))return false;space_.wait(l,[&]{return closed_||total_<capacity_;});if(closed_)return false;queues_[x.zone].push_back(x.id);ids_.insert(x.id);++total_;l.unlock();work_.notify_all();return true;}
std::optional<PickTask> ZoneStealingPickQueue::take_for(int local){std::unique_lock<std::mutex> l(mutex_);if(!zones_.count(local))return std::nullopt;work_.wait(l,[&]{return closed_||total_;});if(!total_)return std::nullopt;int zone=local;if(queues_[zone].empty()){std::size_t best_size=0;for(int candidate:zones_)if(candidate!=local&&(queues_[candidate].size()>best_size||(queues_[candidate].size()==best_size&&best_size&&candidate<zone))){zone=candidate;best_size=queues_[candidate].size();}}if(queues_[zone].empty())return std::nullopt;int id=queues_[zone].front();queues_[zone].pop_front();ids_.erase(id);--total_;l.unlock();space_.notify_one();return PickTask{zone,id};}
std::size_t ZoneStealingPickQueue::pending(int z)const{std::lock_guard<std::mutex> l(mutex_);auto it=queues_.find(z);return it==queues_.end()?0:it->second.size();}
void ZoneStealingPickQueue::close(){std::lock_guard<std::mutex> l(mutex_);closed_=true;work_.notify_all();space_.notify_all();}''',
        r'''int main(){ZoneStealingPickQueue q(6);CHECK(q.add_zone(1));CHECK(q.add_zone(2));CHECK(q.add_zone(3));CHECK(q.submit({2,20}));CHECK(q.submit({3,30}));CHECK(q.submit({3,31}));CHECK(q.take_for(1)==PickTask{3,30});CHECK(q.take_for(2)==PickTask{2,20});return failures;}''',
        r'''int main(){ZoneStealingPickQueue q(2);CHECK(!q.add_zone(0));CHECK(q.add_zone(1));CHECK(!q.add_zone(1));CHECK(!q.submit({9,1}));CHECK(q.submit({1,1}));CHECK(!q.submit({1,1}));q.close();return failures;}''',
        r'''int main(){ZoneStealingPickQueue q(6);CHECK(q.add_zone(1));CHECK(q.add_zone(2));CHECK(q.add_zone(3));CHECK(q.submit({2,1}));CHECK(q.submit({3,2}));CHECK(q.take_for(1)->zone==2);CHECK(q.submit({3,3}));CHECK(q.submit({3,4}));CHECK(q.take_for(1)->zone==3);return failures;}''',
        "queues_[candidate].size()>best_size",
        "candidate<zone",
        "fixed-neighbor stealing ignores largest backlog",
    ),
)
