"""Executable diversity fixtures for producer-consumer protocol rings."""

from __future__ import annotations

from typing import Final


NEGATIVE_REWRITES: Final[dict[str, tuple[str, str, str]]] = {
    "audio-spsc-frame-pipe": ("stuck_read_cursor", "read_=(read_+1)%slots_.size()", "read_=0"),
    "camera-generation-overwrite": ("lost_skip_accounting", "++skipped_", "skipped_=0"),
    "telemetry-source-quota-ring": ("unfair_source_cursor", "cursor_=(s+1)%slots_.size()", "cursor_=s"),
    "network-fragment-assembly-ring": ("partial_packet_visible", "[](bool v){return v;}", "[](bool){return true;}"),
    "log-severity-lane-ring": ("wrong_service_schedule", "schedule{{2,2,1,0}}", "schedule{{0,1,2,2}}"),
    "keyboard-transition-coalescer": ("inverse_not_cancelled", "old.event.reset();", "old.event=e;"),
    "can-sequence-reorder-window": ("wrong_next_slot", "auto i=static_cast<std::size_t>(next_)%slots_.size();", "auto i=static_cast<std::size_t>(next_+1)%slots_.size();"),
    "market-symbol-coalescing-ring": ("corrupt_replacement", "slots_[it->second]->price=t.price", "slots_[it->second]->price=t.price+1"),
    "gps-watermark-batch-ring": ("descending_ready_order", "a.first.timestamp<b.first.timestamp", "a.first.timestamp>b.first.timestamp"),
    "build-epoch-barrier-ring": ("inverted_barrier", "slot.count!=static_cast<std::size_t>(workers_)", "slot.count==static_cast<std::size_t>(workers_)"),
    "video-reservation-commit-ring": ("reserved_is_visible", "x.state=State::reserved", "x.state=State::committed"),
    "sensor-timestamp-merge-ring": ("ignores_source_watermarks", "if(mark<stamp)return std::nullopt;", "if(mark<stamp&&false)return std::nullopt;"),
    "print-aging-priority-ring": ("oldest_ignores_priority", "s.job->priority>best->job->priority", "s.order<best->order"),
    "payment-hash-chain-ring": ("accepts_broken_chain", "||e.previous!=chain_||e.digest!=compute(e.id,e.previous)", ""),
    "file-change-debounce-ring": ("create_delete_not_cancelled", "old.reset();index_.erase(it);return true;", "old->kind=ChangeKind::erase;return true;"),
    "robot-command-retry-ring": ("retry_attempt_not_incremented", "++item.attempt;", "item.attempt=1;"),
    "support-broadcast-cursor-ring": ("early_broadcast_reclaim", "std::min_element(cursors_.begin(),cursors_.end())", "std::max_element(cursors_.begin(),cursors_.end())"),
    "weather-aggregation-bucket-ring": ("new_bucket_wrong_count", "b={tick,value,value,1}", "b={tick,value,value,2}"),
    "game-tick-snapshot-ring": ("first_input_wins", "s.actions[in.player]=in.action", "s.actions.emplace(in.player,in.action)"),
    "warehouse-dedup-window-ring": ("dedup_window_off_by_one", "generation_-it->second<history_", "generation_-it->second<=history_"),
}


TRACE_TESTS: dict[str, str] = {}


TRACE_TESTS.update({
    "video-reservation-commit-ring": """#include "task.h"
#include <optional>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::SegmentCommitRing q(3);struct M{std::optional<curriculum::Reservation> ticket;int state=0,value=0;};std::vector<M> model(3);std::vector<curriculum::Reservation> tickets;for(int i=0;i<3;++i){auto t=q.reserve();c(bool(t));tickets.push_back(*t);model[t->slot].ticket=t;model[t->slot].state=1;}c(!q.reserve());c(q.commit(tickets[1],20));model[tickets[1].slot].state=2;model[tickets[1].slot].value=20;c(!q.take());c(q.cancel(tickets[0]));model[tickets[0].slot].state=3;auto out=q.take();c(out&&*out==model[tickets[1].slot].value);c(q.cancel(tickets[2]));c(!q.take());auto fresh=q.reserve();c(fresh&&fresh->generation!=tickets[0].generation);q.close();c(!q.reserve());return f?1:0;}
""",
    "sensor-timestamp-merge-ring": """#include "task.h"
#include <array>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::SensorMergeRing q(3,3);std::array<std::vector<curriculum::SensorSample>,3> model;std::array<int,3> marks{{0,0,0}};for(auto x:std::vector<curriculum::SensorSample>{{1,2,12},{2,1,21},{3,3,33},{1,4,14}}){bool want=model[x.source-1].size()<3&&(model[x.source-1].empty()||x.timestamp>model[x.source-1].back().timestamp);c(q.publish(x)==want);if(want)model[x.source-1].push_back(x);}for(int s=1;s<=3;++s){c(q.watermark(s,4));marks[s-1]=4;for(;;){int pick=-1;for(int i=0;i<3;++i)if(!model[i].empty()&&(pick<0||model[i].front().timestamp<model[pick].front().timestamp))pick=i;bool safe=pick>=0;for(int mark:marks)if(pick>=0&&mark<model[pick].front().timestamp)safe=false;auto out=q.take_safe();c(bool(out)==safe);if(!safe)break;c(out->source==pick+1&&out->timestamp==model[pick].front().timestamp);model[pick].erase(model[pick].begin());}}q.close();return f?1:0;}
""",
    "print-aging-priority-ring": """#include "task.h"
#include <algorithm>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::AgingPrintRing q(4);struct M{curriculum::PrintJob job;int age;int order;};std::vector<M> model;int order=0;for(auto x:std::vector<curriculum::PrintJob>{{1,0},{2,2},{3,1}}){c(q.submit(x));model.push_back({x,0,order++});}for(int step=0;step<3;++step){q.advance_age();for(auto& x:model)if(x.job.priority<2&&++x.age==2){++x.job.priority;x.age=0;}auto best=std::max_element(model.begin(),model.end(),[](auto a,auto b){return a.job.priority!=b.job.priority?a.job.priority<b.job.priority:a.order>b.order;});auto out=q.take();c(out&&out->id==best->job.id&&out->priority==best->job.priority);model.erase(best);if(model.empty())break;}q.close();c(!q.submit({4,0}));return f?1:0;}
""",
    "payment-hash-chain-ring": """#include "task.h"
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::PaymentChainRing q(4);std::vector<curriculum::PaymentEvent> model;unsigned tail=q.tail_digest();unsigned wrong=tail+1;c(!q.publish({99,wrong,curriculum::PaymentChainRing::compute(99,wrong)}));c(q.tail_digest()==tail);for(int id=1;id<=4;++id){unsigned digest=curriculum::PaymentChainRing::compute(id,tail);curriculum::PaymentEvent x{id,tail,digest};bool want=model.size()<4;c(q.publish(x)==want);if(want){model.push_back(x);tail=digest;}c(q.tail_digest()==tail);}c(!q.publish({9,0,0}));while(!model.empty()){auto out=q.audit();c(out&&out->id==model.front().id&&out->previous==model.front().previous&&out->digest==model.front().digest);model.erase(model.begin());}q.close();return f?1:0;}
""",
    "file-change-debounce-ring": """#include "task.h"
#include <algorithm>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::FileDebounceRing q(4);std::vector<curriculum::FileChange> model;for(auto x:std::vector<curriculum::FileChange>{{1,curriculum::ChangeKind::create},{2,curriculum::ChangeKind::modify},{1,curriculum::ChangeKind::modify},{2,curriculum::ChangeKind::erase},{1,curriculum::ChangeKind::erase},{3,curriculum::ChangeKind::erase},{3,curriculum::ChangeKind::create}}){auto it=std::find_if(model.begin(),model.end(),[&](auto y){return y.path==x.path;});bool want=true;if(it==model.end())model.push_back(x);else if(it->kind==curriculum::ChangeKind::create&&x.kind==curriculum::ChangeKind::erase)model.erase(it);else if(it->kind==curriculum::ChangeKind::create&&x.kind==curriculum::ChangeKind::modify){}else if(it->kind==curriculum::ChangeKind::erase&&x.kind==curriculum::ChangeKind::create)it->kind=curriculum::ChangeKind::modify;else it->kind=x.kind;c(q.publish(x)==want);}while(!model.empty()){auto out=q.take();c(out&&out->path==model.front().path&&out->kind==model.front().kind);model.erase(model.begin());}q.close();return f?1:0;}
""",
    "robot-command-retry-ring": """#include "task.h"
#include <optional>
#include <set>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::CommandRetryRing q(3,3);std::vector<curriculum::Dispatch> model;std::set<int> ids;std::optional<curriculum::Dispatch> flight;for(int id=1;id<=3;++id){bool want=ids.insert(id).second&&model.size()<3;c(q.submit(id)==want);if(want)model.push_back({id,1});}for(bool ok:std::vector<bool>{false,true,false,false}){auto out=q.dispatch();bool ready=!flight&& !model.empty();c(bool(out)==ready);if(ready){flight=model.front();model.erase(model.begin());c(out->id==flight->id&&out->attempt==flight->attempt);int id=flight->id;c(q.acknowledge(id,ok));auto item=*flight;flight.reset();if(ok||item.attempt>=3)ids.erase(id);else{++item.attempt;model.push_back(item);}}}q.close();c(!q.submit(9));return f?1:0;}
""",
    "support-broadcast-cursor-ring": """#include "task.h"
#include <algorithm>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::BroadcastNotificationRing q(3,3);std::vector<int> model;std::vector<std::size_t> cursors(3);for(int value=1;value<=6;++value){auto minimum=*std::min_element(cursors.begin(),cursors.end());bool want=model.size()-minimum<3;c(q.publish(value)==want);if(want)model.push_back(value);for(int consumer=0;consumer<3;++consumer)if((value+consumer)%2==0){auto out=q.take(consumer);bool ready=cursors[consumer]<model.size();c(bool(out)==ready);if(ready){c(*out==model[cursors[consumer]]);++cursors[consumer];}}minimum=*std::min_element(cursors.begin(),cursors.end());c(q.retained()==model.size()-minimum);}q.close();c(!q.publish(9));return f?1:0;}
""",
    "weather-aggregation-bucket-ring": """#include "task.h"
#include <map>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::WeatherBucketRing q(3);struct M{int lo,hi,count;};std::map<int,M> model;int latest=-1;for(auto x:std::vector<std::pair<int,int>>{{1,5},{1,2},{2,7},{4,9},{4,3}}){bool want=x.first>=latest;c(q.publish(x.first,x.second)==want);if(want){latest=x.first;for(auto it=model.begin();it!=model.end();)if(it->first%3==x.first%3&&it->first!=x.first)it=model.erase(it);else++it;auto it=model.find(x.first);if(it==model.end())model[x.first]={x.second,x.second,1};else{it->second.lo=std::min(it->second.lo,x.second);it->second.hi=std::max(it->second.hi,x.second);++it->second.count;}}auto out=q.take_bucket(x.first);c(bool(out)==model.count(x.first));if(out){auto m=model[x.first];c(out->minimum==m.lo&&out->maximum==m.hi&&out->count==m.count);model.erase(x.first);}}q.close();return f?1:0;}
""",
    "game-tick-snapshot-ring": """#include "task.h"
#include <algorithm>
#include <map>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::GameTickRing q(4);std::map<int,std::map<int,int>> model;std::map<int,bool> sealed;for(auto x:std::vector<curriculum::Input>{{2,2,20},{1,1,10},{2,2,21},{1,3,13},{3,1,30}}){bool want=!sealed[x.tick];c(q.publish(x)==want);if(want)model[x.tick][x.player]=x.action;}for(int tick:std::vector<int>{2,1,3}){bool want=model.count(tick)&&!sealed[tick];c(q.seal(tick)==want);if(want)sealed[tick]=true;int first=-1;for(auto item:sealed)if(item.second&&(first<0||item.first<first))first=item.first;auto out=q.take_tick();c(bool(out)==(first>=0));if(out){std::vector<curriculum::Input> expected;for(auto item:model[first])expected.push_back({first,item.first,item.second});c(out->size()==expected.size());for(std::size_t i=0;i<out->size();++i)c((*out)[i].player==expected[i].player&&(*out)[i].action==expected[i].action);model.erase(first);sealed.erase(first);}}q.close();return f?1:0;}
""",
    "warehouse-dedup-window-ring": """#include "task.h"
#include <map>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::ScanDedupRing q(4,3);std::vector<curriculum::Scan> model;std::map<int,std::size_t> last;std::size_t generation=0;for(auto x:std::vector<curriculum::Scan>{{1,1},{2,1},{1,2},{3,1},{4,1},{1,2},{5,1}}){auto it=last.find(x.parcel);bool recent=it!=last.end()&&generation-it->second<3;bool want=!recent&&model.size()<4;c(q.submit(x)==want);if(want){++generation;last[x.parcel]=generation;model.push_back(x);}if(model.size()==3){auto out=q.take();c(out&&out->parcel==model.front().parcel&&out->station==model.front().station);model.erase(model.begin());}}while(!model.empty()){auto out=q.take();c(out&&out->parcel==model.front().parcel);model.erase(model.begin());}q.close();return f?1:0;}
""",
})



def negative_source(task_id: str, reference: str) -> tuple[str, str]:
    name, old, new = NEGATIVE_REWRITES[task_id]
    if reference.count(old) != 1:
        raise RuntimeError(f"negative_fixture_rewrite_mismatch:{task_id}:{reference.count(old)}")
    return name, reference.replace(old, new)


TRACE_TESTS.update({
    "audio-spsc-frame-pipe": """#include "task.h"
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::AudioFramePipe q(3);std::vector<curriculum::Frame> model;c(!q.capture({0,1}));int id=1;for(int round=0;round<4;++round){for(int slot=0;slot<3;++slot){curriculum::Frame x{id,id+100};++id;c(q.capture(x));model.push_back(x);c(q.pending()==model.size());}while(!model.empty()){auto out=q.playback();c(out&&*out==model.front());model.erase(model.begin());c(q.pending()==model.size());}}q.finish();c(!q.playback());c(!q.capture({99,1}));return f?1:0;}
""",
    "camera-generation-overwrite": """#include "task.h"
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::CameraGenerationRing q(3);std::vector<curriculum::CameraFrame> model;std::size_t skipped=0;for(int i=1;i<=9;++i){bool got=q.publish({i,i});c(got);if(model.size()==3){model.erase(model.begin());++skipped;}model.push_back({i,i});if(i%4==0){auto out=q.next();c(out&&out->frame.id==model.front().id&&out->skipped==skipped);model.erase(model.begin());skipped=0;}}while(!model.empty()){auto out=q.next();c(out&&out->frame.id==model.front().id&&out->skipped==skipped);model.erase(model.begin());skipped=0;}q.close();c(!q.publish({20,20}));return f?1:0;}
""",
    "telemetry-source-quota-ring": """#include "task.h"
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::TelemetryQuotaRing q(3,3);std::vector<std::vector<int>> model(3);std::size_t cursor=0;for(int round=1;round<=3;++round)for(int source=1;source<=3;++source){bool got=q.submit({source,round});bool want=model[source-1].size()<3;c(got==want);if(want)model[source-1].push_back(round);c(q.pending(source)==model[source-1].size());}for(int n=0;n<9;++n){std::size_t pick=cursor;while(model[pick].empty())pick=(pick+1)%3;auto out=q.take_fair();c(out&&out->source==static_cast<int>(pick+1)&&out->sequence==model[pick].front());model[pick].erase(model[pick].begin());cursor=(pick+1)%3;for(int s=1;s<=3;++s)c(q.pending(s)==model[s-1].size());}q.close();c(!q.submit({1,4}));return f?1:0;}
""",
    "network-fragment-assembly-ring": """#include "task.h"
#include <map>
#include <optional>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::FragmentAssemblyRing q(2);std::map<int,std::vector<std::optional<int>>> model;std::vector<curriculum::Fragment> ops{{1,1,3,11},{2,0,2,20},{1,0,3,10},{1,2,3,12},{2,1,2,21}};for(auto x:ops){if(model[x.packet].empty())model[x.packet].resize(x.total);bool want=!model[x.packet][x.index].has_value();bool got=q.receive(x);c(got==want);if(got)model[x.packet][x.index]=x.value;auto first=model.begin();bool complete=first!=model.end();if(complete)for(auto v:first->second)complete=complete&&v.has_value();auto out=q.take_complete();c(bool(out)==complete);if(complete){std::vector<int> expected;for(auto v:first->second)expected.push_back(*v);c(*out==expected);model.erase(first);}}q.close();c(!q.receive({3,0,1,1}));return f?1:0;}
""",
    "log-severity-lane-ring": """#include "task.h"
#include <array>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::SeverityLaneRing q(4);std::array<std::vector<int>,3> model;for(auto x:std::vector<curriculum::LogRecord>{{1,0},{2,2},{3,1},{4,2},{5,0}}){bool got=q.append(x);c(got);model[x.severity].push_back(x.id);}std::array<int,4> schedule{{2,2,1,0}};std::size_t cursor=0;for(int n=0;n<5;++n){int lane=-1;for(int k=0;k<4&&lane<0;++k){int p=schedule[cursor];cursor=(cursor+1)%4;if(!model[p].empty())lane=p;}auto out=q.take_weighted();c(out&&out->id==model[lane].front());model[lane].erase(model[lane].begin());}c(!q.take_weighted());q.close();c(!q.append({6,0}));return f?1:0;}
""",
    "keyboard-transition-coalescer": """#include "task.h"
#include <algorithm>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::KeyTransitionRing q(4);std::vector<curriculum::KeyEvent> model;for(auto x:std::vector<curriculum::KeyEvent>{{1,true},{2,true},{1,false},{3,false},{2,false},{4,true}}){auto it=std::find_if(model.begin(),model.end(),[&](auto y){return y.key==x.key;});bool want=true;if(it!=model.end()){if(it->down==x.down)want=false;else model.erase(it);}else if(model.size()==4)want=false;else model.push_back(x);c(q.emit(x)==want);}while(!model.empty()){auto out=q.take();c(out&&out->key==model.front().key&&out->down==model.front().down);model.erase(model.begin());}q.close();c(!q.emit({5,true}));return f?1:0;}
""",
    "can-sequence-reorder-window": """#include "task.h"
#include <map>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::CanReorderWindow q(10,4);std::map<int,int> model;int next=10;for(auto x:std::vector<curriculum::CanMessage>{{12,120},{10,100},{13,130},{11,110}}){bool want=x.sequence>=next&&x.sequence<next+4&&!model.count(x.sequence);c(q.publish(x)==want);if(want)model[x.sequence]=x.payload;auto out=q.take_next();bool ready=model.count(next);c(bool(out)==ready);if(ready){c(out->payload==model[next]);model.erase(next++);}}while(model.count(next)){auto out=q.take_next();c(out&&out->payload==model[next]);model.erase(next++);}q.close();c(!q.publish({next,1}));return f?1:0;}
""",
    "market-symbol-coalescing-ring": """#include "task.h"
#include <algorithm>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::SymbolCoalescingRing q(3);std::vector<curriculum::Tick> model;std::size_t replacements=0;for(auto x:std::vector<curriculum::Tick>{{1,10},{2,20},{1,11},{3,30},{2,22}}){auto it=std::find_if(model.begin(),model.end(),[&](auto y){return y.symbol==x.symbol;});bool want=it!=model.end()||model.size()<3;c(q.publish(x)==want);if(it!=model.end()){it->price=x.price;++replacements;}else if(want)model.push_back(x);c(q.replacements()==replacements);}while(!model.empty()){auto out=q.take();c(out&&out->symbol==model.front().symbol&&out->price==model.front().price);model.erase(model.begin());}q.close();c(!q.publish({4,4}));return f?1:0;}
""",
    "gps-watermark-batch-ring": """#include "task.h"
#include <algorithm>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::GpsWatermarkRing q(5);std::vector<curriculum::GpsSample> model;int watermark=0;for(auto x:std::vector<curriculum::GpsSample>{{5,50},{2,20},{4,40},{3,30}}){bool want=x.timestamp>watermark&&model.size()<5;c(q.publish(x)==want);if(want)model.push_back(x);}for(int mark:std::vector<int>{2,4,6}){bool want=mark>watermark;c(q.advance_watermark(mark)==want);if(want)watermark=mark;std::vector<curriculum::GpsSample> ready;for(auto x:model)if(x.timestamp<=watermark)ready.push_back(x);std::stable_sort(ready.begin(),ready.end(),[](auto a,auto b){return a.timestamp<b.timestamp;});auto out=q.take_ready();c(out.size()==ready.size());for(std::size_t i=0;i<out.size();++i)c(out[i].timestamp==ready[i].timestamp&&out[i].point==ready[i].point);model.erase(std::remove_if(model.begin(),model.end(),[&](auto x){return x.timestamp<=watermark;}),model.end());}q.close();return f?1:0;}
""",
    "build-epoch-barrier-ring": """#include "task.h"
#include <map>
#include <set>
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::BuildEpochRing q(3,3);std::map<int,std::set<int>> model;int next=0;for(auto x:std::vector<curriculum::BuildEvent>{{0,1},{0,0},{2,0},{1,0},{1,1},{2,1},{0,2},{1,2},{2,2}}){bool want=x.worker>=0&&x.worker<3&&x.epoch>=next&&x.epoch<next+3&&!model[x.epoch].count(x.worker);c(q.arrive(x)==want);if(want)model[x.epoch].insert(x.worker);auto out=q.take_completed_epoch();bool ready=model[next].size()==3;c(bool(out)==ready);if(ready){c(*out==next);model.erase(next++);}}q.close();c(!q.arrive({0,next}));return f?1:0;}
""",
})
