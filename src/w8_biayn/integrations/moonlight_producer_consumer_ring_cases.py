"""Bespoke C++ assets for producer-consumer protocol-ring tasks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CaseAssets:
    legacy_id: str
    class_name: str
    kind: str
    title: str
    objective: str
    instructions: str
    header: str
    starter: str
    reference: str
    visible_test: str
    hidden_test: str
    required_markers: tuple[str, ...]
    benchmark_separation: str
    visible_description: str
    hidden_description: str


def _instructions(class_name: str, contract: str) -> str:
    return (
        f"# Instructions\n\nImplement {class_name}. {contract} "
        "All invalid, duplicate, absent, capacity, and closed-state results are "
        "part of the public contract and must not partially mutate state. "
        "The object owns all stored values. This is local candidate material, "
        "not a dataset release.\n"
    )


def _starter(header: str, class_name: str, definitions: str) -> str:
    del header
    return f'#include "task.h"\nnamespace curriculum {{\n{definitions}\n}}\n'


def _case(
    *,
    legacy_id: str,
    class_name: str,
    kind: str,
    title: str,
    objective: str,
    contract: str,
    header: str,
    starter: str,
    reference: str,
    visible_test: str,
    hidden_test: str,
    markers: tuple[str, ...],
) -> CaseAssets:
    return CaseAssets(
        legacy_id=legacy_id,
        class_name=class_name,
        kind=kind,
        title=title,
        objective=objective,
        instructions=_instructions(class_name, contract),
        header=header,
        starter=starter,
        reference=reference,
        visible_test=visible_test,
        hidden_test=hidden_test,
        required_markers=markers,
        benchmark_separation=(
            "Original protocol-specific API, state machine, and tests; not "
            "derived from any official Aider C++ holdout."
        ),
        visible_description=f"{kind} public transition and boundary contract",
        hidden_description=(
            f"{kind} wraparound, invalid-state, ordering, and negative-fixture checks"
        ),
    )


def _audio() -> CaseAssets:
    header = """#pragma once
#include <condition_variable>
#include <cstddef>
#include <mutex>
#include <optional>
#include <vector>
namespace curriculum {
struct Frame { int id; int samples; };
inline bool operator==(const Frame& a,const Frame& b){return a.id==b.id&&a.samples==b.samples;}
class AudioFramePipe {
 public: explicit AudioFramePipe(std::size_t capacity); bool capture(Frame frame);
 std::optional<Frame> playback(); void finish(); std::size_t pending() const;
 private: std::vector<std::optional<Frame>> slots_; std::size_t read_=0,write_=0,count_=0;
 mutable std::mutex mutex_; std::condition_variable readable_,writable_; bool finished_=false;
}; }
"""
    starter = _starter(header, "AudioFramePipe", """AudioFramePipe::AudioFramePipe(std::size_t){}
bool AudioFramePipe::capture(Frame){return false;}
std::optional<Frame> AudioFramePipe::playback(){return std::nullopt;}
void AudioFramePipe::finish(){}
std::size_t AudioFramePipe::pending()const{return 0;}""")
    reference = """#include "task.h"
#include <stdexcept>
namespace curriculum {
AudioFramePipe::AudioFramePipe(std::size_t n):slots_(n){if(!n)throw std::invalid_argument("capacity");}
bool AudioFramePipe::capture(Frame frame){if(frame.id<=0||frame.samples<=0)return false;std::unique_lock<std::mutex> lock(mutex_);writable_.wait(lock,[this]{return finished_||count_<slots_.size();});if(finished_)return false;slots_[write_]=frame;write_=(write_+1)%slots_.size();++count_;lock.unlock();readable_.notify_one();return true;}
std::optional<Frame> AudioFramePipe::playback(){std::unique_lock<std::mutex> lock(mutex_);readable_.wait(lock,[this]{return finished_||count_>0;});if(!count_)return std::nullopt;Frame out=*slots_[read_];slots_[read_].reset();read_=(read_+1)%slots_.size();--count_;lock.unlock();writable_.notify_one();return out;}
void AudioFramePipe::finish(){std::lock_guard<std::mutex> lock(mutex_);finished_=true;readable_.notify_all();writable_.notify_all();}
std::size_t AudioFramePipe::pending()const{std::lock_guard<std::mutex> lock(mutex_);return count_;}
}
"""
    visible = """#include "task.h"
#include <stdexcept>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};try{curriculum::AudioFramePipe z(0);c(false);}catch(const std::invalid_argument&){}curriculum::AudioFramePipe q(2);c(!q.capture({0,2}));c(q.capture({1,80}));c(q.capture({2,90}));c(q.playback()==curriculum::Frame{1,80});c(q.playback()==curriculum::Frame{2,90});q.finish();c(!q.playback());c(!q.capture({3,1}));return f?1:0;}
"""
    hidden = """#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::AudioFramePipe q(2);for(int i=1;i<=20;++i){c(q.capture({i,i+10}));c(q.playback()==curriculum::Frame{i,i+10});}c(q.pending()==0);q.finish();return f?1:0;}
"""
    return _case(
        legacy_id="pcr-audio-capture", class_name="AudioFramePipe",
        kind="spsc_slot_cursors", title="Audio SPSC frame pipe",
        objective="A fixed-slot SPSC ring with blocking backpressure.",
        contract="Positive frames are captured FIFO. Capture blocks only while full; playback blocks only while empty. Finish wakes both sides and playback drains accepted frames.",
        header=header, starter=starter, reference=reference,
        visible_test=visible, hidden_test=hidden,
        markers=("slots_[write_]", "read_=(read_+1)%slots_.size()"),
    )


def _camera() -> CaseAssets:
    header = """#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <vector>
namespace curriculum {
struct CameraFrame{int id;int generation;}; struct CameraRead{CameraFrame frame;std::size_t skipped;};
class CameraGenerationRing{public:explicit CameraGenerationRing(std::size_t);bool publish(CameraFrame);std::optional<CameraRead> next();void close();
private:std::vector<CameraFrame> slots_;std::size_t head_=0,count_=0,skipped_=0;int last_generation_=0;bool closed_=false;std::mutex mutex_;};}
"""
    starter = _starter(header, "CameraGenerationRing", """CameraGenerationRing::CameraGenerationRing(std::size_t){}
bool CameraGenerationRing::publish(CameraFrame){return false;}
std::optional<CameraRead> CameraGenerationRing::next(){return std::nullopt;}
void CameraGenerationRing::close(){}""")
    reference = """#include "task.h"
#include <stdexcept>
namespace curriculum {
CameraGenerationRing::CameraGenerationRing(std::size_t n):slots_(n){if(!n)throw std::invalid_argument("capacity");}
bool CameraGenerationRing::publish(CameraFrame frame){std::lock_guard<std::mutex> lock(mutex_);if(closed_||frame.id<=0||frame.generation<=last_generation_)return false;last_generation_=frame.generation;if(count_==slots_.size()){slots_[head_]=frame;head_=(head_+1)%slots_.size();++skipped_;}else{slots_[(head_+count_)%slots_.size()]=frame;++count_;}return true;}
std::optional<CameraRead> CameraGenerationRing::next(){std::lock_guard<std::mutex> lock(mutex_);if(!count_)return std::nullopt;CameraRead out{slots_[head_],skipped_};skipped_=0;head_=(head_+1)%slots_.size();--count_;return out;}
void CameraGenerationRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
}
"""
    visible = """#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::CameraGenerationRing r(2);c(r.publish({1,1}));c(r.publish({2,2}));c(r.publish({3,3}));auto x=r.next();c(x&&x->frame.id==2&&x->skipped==1);c(!r.publish({4,3}));r.close();c(!r.publish({4,4}));return f?1:0;}
"""
    hidden = """#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::CameraGenerationRing r(1);for(int i=1;i<=5;++i)c(r.publish({i,i}));auto x=r.next();c(x&&x->frame.id==5&&x->skipped==4);c(!r.next());return f?1:0;}
"""
    return _case(
        legacy_id="pcr-camera-frames", class_name="CameraGenerationRing",
        kind="generation_overwrite", title="Camera generation overwrite ring",
        objective="A generation-stamped overwrite protocol that reports skipped frames.",
        contract="Generations must strictly increase. Full publication overwrites the oldest unread frame; next reports the exact accumulated skipped count.",
        header=header, starter=starter, reference=reference,
        visible_test=visible, hidden_test=hidden,
        markers=("last_generation_", "++skipped_"),
    )


def _telemetry() -> CaseAssets:
    header = """#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <vector>
namespace curriculum {
struct Reading{int source;int sequence;};
class TelemetryQuotaRing{public:TelemetryQuotaRing(std::size_t sources,std::size_t quota);bool submit(Reading);std::optional<Reading> take_fair();void close();std::size_t pending(int)const;
private:std::vector<std::vector<std::optional<Reading>>> slots_;std::vector<std::size_t> head_,tail_,count_;std::vector<int> last_;std::size_t cursor_=0;bool closed_=false;mutable std::mutex mutex_;};}
"""
    starter = _starter(header, "TelemetryQuotaRing", """TelemetryQuotaRing::TelemetryQuotaRing(std::size_t,std::size_t){}
bool TelemetryQuotaRing::submit(Reading){return false;}
std::optional<Reading> TelemetryQuotaRing::take_fair(){return std::nullopt;}
void TelemetryQuotaRing::close(){}
std::size_t TelemetryQuotaRing::pending(int)const{return 0;}""")
    reference = """#include "task.h"
#include <stdexcept>
namespace curriculum {
TelemetryQuotaRing::TelemetryQuotaRing(std::size_t sources,std::size_t quota):slots_(sources,std::vector<std::optional<Reading>>(quota)),head_(sources),tail_(sources),count_(sources),last_(sources){if(!sources||!quota)throw std::invalid_argument("shape");}
bool TelemetryQuotaRing::submit(Reading r){std::lock_guard<std::mutex> lock(mutex_);if(closed_||r.source<=0||static_cast<std::size_t>(r.source)>slots_.size()||r.sequence<=last_[r.source-1])return false;auto s=static_cast<std::size_t>(r.source-1);if(count_[s]==slots_[s].size())return false;slots_[s][tail_[s]]=r;tail_[s]=(tail_[s]+1)%slots_[s].size();++count_[s];last_[s]=r.sequence;return true;}
std::optional<Reading> TelemetryQuotaRing::take_fair(){std::lock_guard<std::mutex> lock(mutex_);for(std::size_t n=0;n<slots_.size();++n){auto s=(cursor_+n)%slots_.size();if(count_[s]){Reading out=*slots_[s][head_[s]];slots_[s][head_[s]].reset();head_[s]=(head_[s]+1)%slots_[s].size();--count_[s];cursor_=(s+1)%slots_.size();return out;}}return std::nullopt;}
void TelemetryQuotaRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
std::size_t TelemetryQuotaRing::pending(int source)const{std::lock_guard<std::mutex> lock(mutex_);return source>0&&static_cast<std::size_t>(source)<=count_.size()?count_[source-1]:0;}
}
"""
    visible = """#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::TelemetryQuotaRing r(2,2);c(r.submit({1,1}));c(r.submit({1,2}));c(!r.submit({1,3}));c(r.submit({2,1}));c(r.take_fair()->source==1);c(r.take_fair()->source==2);c(r.take_fair()->sequence==2);return f?1:0;}
"""
    hidden = """#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::TelemetryQuotaRing r(3,1);c(!r.submit({0,1}));for(int s=1;s<=3;++s)c(r.submit({s,1}));for(int s=1;s<=3;++s)c(r.take_fair()->source==s);c(!r.submit({2,1}));r.close();c(!r.submit({2,2}));return f?1:0;}
"""
    return _case(
        legacy_id="pcr-telemetry-uplink", class_name="TelemetryQuotaRing",
        kind="per_source_round_robin", title="Telemetry source-quota ring",
        objective="Per-source subrings drained with round-robin fairness.",
        contract="Each source has an independent quota and strictly increasing sequence. Fair take visits nonempty sources round-robin.",
        header=header, starter=starter, reference=reference,
        visible_test=visible, hidden_test=hidden,
        markers=("slots_[s][tail_[s]]", "cursor_=(s+1)%slots_.size()"),
    )


def _network() -> CaseAssets:
    header = """#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <vector>
namespace curriculum {
struct Fragment{int packet;int index;int total;int value;};
class FragmentAssemblyRing{public:explicit FragmentAssemblyRing(std::size_t);bool receive(Fragment);std::optional<std::vector<int>> take_complete();void close();
private:struct Slot{int packet=0,total=0;std::vector<int> parts;std::vector<bool> seen;std::size_t order=0;};std::vector<Slot> slots_;std::size_t next_order_=1;bool closed_=false;std::mutex mutex_;};}
"""
    starter = _starter(header, "FragmentAssemblyRing", """FragmentAssemblyRing::FragmentAssemblyRing(std::size_t){}
bool FragmentAssemblyRing::receive(Fragment){return false;}
std::optional<std::vector<int>> FragmentAssemblyRing::take_complete(){return std::nullopt;}
void FragmentAssemblyRing::close(){}""")
    reference = """#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {
FragmentAssemblyRing::FragmentAssemblyRing(std::size_t n):slots_(n){if(!n)throw std::invalid_argument("capacity");}
bool FragmentAssemblyRing::receive(Fragment f){std::lock_guard<std::mutex> lock(mutex_);if(closed_||f.packet<=0||f.total<=0||f.index<0||f.index>=f.total)return false;Slot* slot=nullptr;for(auto& s:slots_)if(s.packet==f.packet)slot=&s;if(!slot){for(auto& s:slots_)if(!s.packet){slot=&s;break;}if(!slot)return false;slot->packet=f.packet;slot->total=f.total;slot->parts.assign(f.total,0);slot->seen.assign(f.total,false);slot->order=next_order_++;}if(slot->total!=f.total||slot->seen[f.index])return false;slot->parts[f.index]=f.value;slot->seen[f.index]=true;return true;}
std::optional<std::vector<int>> FragmentAssemblyRing::take_complete(){std::lock_guard<std::mutex> lock(mutex_);Slot* best=nullptr;for(auto& s:slots_)if(s.packet&&std::all_of(s.seen.begin(),s.seen.end(),[](bool v){return v;})&&(!best||s.order<best->order))best=&s;if(!best)return std::nullopt;auto out=best->parts;*best=Slot{};return out;}
void FragmentAssemblyRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
}
"""
    visible = """#include "task.h"
#include <vector>
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::FragmentAssemblyRing r(2);c(r.receive({7,1,2,20}));c(!r.take_complete());c(r.receive({7,0,2,10}));c(r.take_complete()==std::optional<std::vector<int>>({10,20}));c(!r.receive({8,2,2,1}));return f?1:0;}
"""
    hidden = """#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::FragmentAssemblyRing r(1);c(r.receive({1,0,2,4}));c(!r.receive({1,0,2,4}));c(!r.receive({2,0,1,9}));c(r.receive({1,1,2,5}));c(r.take_complete()->size()==2);c(r.receive({2,0,1,9}));return f?1:0;}
"""
    return _case(
        legacy_id="pcr-network-receiver", class_name="FragmentAssemblyRing",
        kind="fragment_assembly", title="Network fragment assembly ring",
        objective="A bounded packet assembly window for out-of-order fragments.",
        contract="Fragments occupy packet slots, reject duplicates or conflicting totals, and become consumable only when complete in packet-admission order.",
        header=header, starter=starter, reference=reference,
        visible_test=visible, hidden_test=hidden,
        markers=("slot->seen[f.index]", "std::all_of(s.seen.begin()"),
    )


def _logs() -> CaseAssets:
    header = """#pragma once
#include <array>
#include <cstddef>
#include <mutex>
#include <optional>
#include <vector>
namespace curriculum {
struct LogRecord{int id;int severity;};
class SeverityLaneRing{public:explicit SeverityLaneRing(std::size_t);bool append(LogRecord);std::optional<LogRecord> take_weighted();void close();
private:struct Lane{std::vector<std::optional<LogRecord>> slots;std::size_t head=0,tail=0,count=0;};std::array<Lane,3> lanes_;std::size_t cycle_=0;bool closed_=false;std::mutex mutex_;};}
"""
    starter = _starter(header, "SeverityLaneRing", """SeverityLaneRing::SeverityLaneRing(std::size_t){}
bool SeverityLaneRing::append(LogRecord){return false;}
std::optional<LogRecord> SeverityLaneRing::take_weighted(){return std::nullopt;}
void SeverityLaneRing::close(){}""")
    reference = """#include "task.h"
#include <stdexcept>
namespace curriculum {
SeverityLaneRing::SeverityLaneRing(std::size_t n){if(!n)throw std::invalid_argument("capacity");for(auto& lane:lanes_)lane.slots.resize(n);}
bool SeverityLaneRing::append(LogRecord r){std::lock_guard<std::mutex> lock(mutex_);if(closed_||r.id<=0||r.severity<0||r.severity>2)return false;auto& lane=lanes_[r.severity];if(lane.count==lane.slots.size())return false;lane.slots[lane.tail]=r;lane.tail=(lane.tail+1)%lane.slots.size();++lane.count;return true;}
std::optional<LogRecord> SeverityLaneRing::take_weighted(){static const std::array<int,4> schedule{{2,2,1,0}};std::lock_guard<std::mutex> lock(mutex_);for(std::size_t n=0;n<schedule.size();++n){int which=schedule[cycle_];cycle_=(cycle_+1)%schedule.size();auto& lane=lanes_[which];if(lane.count){LogRecord out=*lane.slots[lane.head];lane.slots[lane.head].reset();lane.head=(lane.head+1)%lane.slots.size();--lane.count;return out;}}return std::nullopt;}
void SeverityLaneRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
}
"""
    visible = """#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::SeverityLaneRing r(2);c(r.append({1,0}));c(r.append({2,1}));c(r.append({3,2}));c(r.append({4,2}));c(r.take_weighted()->id==3);c(r.take_weighted()->id==4);c(r.take_weighted()->id==2);c(r.take_weighted()->id==1);return f?1:0;}
"""
    hidden = """#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::SeverityLaneRing r(1);c(!r.append({1,3}));c(r.append({1,0}));c(!r.append({2,0}));c(r.take_weighted()->id==1);c(!r.take_weighted());r.close();c(!r.append({3,1}));return f?1:0;}
"""
    return _case(
        legacy_id="pcr-log-ingest", class_name="SeverityLaneRing",
        kind="weighted_severity_lanes", title="Log severity-lane ring",
        objective="Three independent rings served by a fixed weighted cycle.",
        contract="Severity 2 is offered twice, severity 1 once, and severity 0 once per cycle. Empty lanes are skipped and each lane preserves its own order.",
        header=header, starter=starter, reference=reference,
        visible_test=visible, hidden_test=hidden,
        markers=("schedule{{2,2,1,0}}", "lanes_[r.severity]"),
    )


def _keyboard() -> CaseAssets:
    header="""#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <unordered_map>
#include <vector>
namespace curriculum{struct KeyEvent{int key;bool down;};class KeyTransitionRing{public:explicit KeyTransitionRing(std::size_t);bool emit(KeyEvent);std::optional<KeyEvent> take();void close();private:struct Slot{std::optional<KeyEvent> event;std::size_t order=0;};std::vector<Slot> slots_;std::unordered_map<int,std::size_t> by_key_;std::size_t next_=1,cursor_=0;bool closed_=false;std::mutex mutex_;};}
"""
    starter=_starter(header,"KeyTransitionRing","""KeyTransitionRing::KeyTransitionRing(std::size_t){}
bool KeyTransitionRing::emit(KeyEvent){return false;}
std::optional<KeyEvent> KeyTransitionRing::take(){return std::nullopt;}
void KeyTransitionRing::close(){}""")
    reference="""#include "task.h"
#include <stdexcept>
namespace curriculum{
KeyTransitionRing::KeyTransitionRing(std::size_t n):slots_(n){if(!n)throw std::invalid_argument("capacity");}
bool KeyTransitionRing::emit(KeyEvent e){std::lock_guard<std::mutex> lock(mutex_);if(closed_||e.key<=0)return false;auto found=by_key_.find(e.key);if(found!=by_key_.end()){auto& old=slots_[found->second];if(old.event->down==e.down)return false;old.event.reset();by_key_.erase(found);return true;}if(by_key_.size()==slots_.size())return false;for(std::size_t n=0;n<slots_.size();++n){auto i=(cursor_+n)%slots_.size();if(!slots_[i].event){slots_[i]={e,next_++};by_key_[e.key]=i;cursor_=(i+1)%slots_.size();return true;}}return false;}
std::optional<KeyEvent> KeyTransitionRing::take(){std::lock_guard<std::mutex> lock(mutex_);Slot* best=nullptr;for(auto& slot:slots_)if(slot.event&&(!best||slot.order<best->order))best=&slot;if(!best)return std::nullopt;auto out=*best->event;by_key_.erase(out.key);best->event.reset();return out;}
void KeyTransitionRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
}
"""
    visible="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::KeyTransitionRing r(2);c(r.emit({1,true}));c(!r.emit({1,true}));c(r.emit({2,true}));c(r.emit({1,false}));c(r.take()->key==2);c(!r.take());return f?1:0;}
"""
    hidden="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::KeyTransitionRing r(2);c(!r.emit({0,true}));c(r.emit({1,true}));c(r.emit({2,false}));c(!r.emit({3,true}));c(r.take()->key==1);c(r.emit({3,true}));c(r.take()->key==2);c(r.take()->key==3);return f?1:0;}
"""
    return _case(legacy_id="pcr-keyboard-events",class_name="KeyTransitionRing",kind="inverse_transition_coalescing",title="Keyboard transition coalescer",objective="A key-indexed pending transition reducer.",contract="Identical pending states reject; an inverse state cancels the pending event for that key without disturbing unrelated order.",header=header,starter=starter,reference=reference,visible_test=visible,hidden_test=hidden,markers=("by_key_.find(e.key)","old.event.reset()"))


def _can() -> CaseAssets:
    header="""#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <vector>
namespace curriculum{struct CanMessage{int sequence;int payload;};class CanReorderWindow{public:CanReorderWindow(int,std::size_t);bool publish(CanMessage);std::optional<CanMessage> take_next();void close();private:std::vector<std::optional<CanMessage>> slots_;int next_;bool closed_=false;std::mutex mutex_;};}
"""
    starter=_starter(header,"CanReorderWindow","""CanReorderWindow::CanReorderWindow(int first,std::size_t):next_(first){}
bool CanReorderWindow::publish(CanMessage){return false;}
std::optional<CanMessage> CanReorderWindow::take_next(){return std::nullopt;}
void CanReorderWindow::close(){}""")
    reference="""#include "task.h"
#include <stdexcept>
namespace curriculum{
CanReorderWindow::CanReorderWindow(int first,std::size_t width):slots_(width),next_(first){if(first<=0||!width)throw std::invalid_argument("shape");}
bool CanReorderWindow::publish(CanMessage m){std::lock_guard<std::mutex> lock(mutex_);long long distance=static_cast<long long>(m.sequence)-next_;if(closed_||m.sequence<=0||distance<0||distance>=static_cast<long long>(slots_.size()))return false;auto i=static_cast<std::size_t>(m.sequence)%slots_.size();if(slots_[i])return false;slots_[i]=m;return true;}
std::optional<CanMessage> CanReorderWindow::take_next(){std::lock_guard<std::mutex> lock(mutex_);auto i=static_cast<std::size_t>(next_)%slots_.size();if(!slots_[i]||slots_[i]->sequence!=next_)return std::nullopt;auto out=slots_[i];slots_[i].reset();++next_;return out;}
void CanReorderWindow::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
}
"""
    visible="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::CanReorderWindow r(10,3);c(r.publish({12,3}));c(r.publish({10,1}));c(!r.publish({10,2}));c(r.take_next()->sequence==10);c(!r.take_next());c(r.publish({11,2}));c(r.take_next()->payload==2);c(r.take_next()->payload==3);return f?1:0;}
"""
    hidden="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::CanReorderWindow r(1,2);c(!r.publish({3,1}));for(int i=1;i<=20;++i){c(r.publish({i,i}));c(r.take_next()->sequence==i);}r.close();c(!r.publish({21,1}));return f?1:0;}
"""
    return _case(legacy_id="pcr-can-bus",class_name="CanReorderWindow",kind="sequence_reorder_window",title="CAN sequence reorder window",objective="A modular sequence-indexed reorder window.",contract="Only messages in the current sequence window are admitted. Consumers can take exactly the next sequence; stale, duplicate, and far-future messages reject.",header=header,starter=starter,reference=reference,visible_test=visible,hidden_test=hidden,markers=("distance=static_cast<long long>","slots_[i]->sequence!=next_"))


def _market() -> CaseAssets:
    header="""#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <unordered_map>
#include <vector>
namespace curriculum{struct Tick{int symbol;int price;};class SymbolCoalescingRing{public:explicit SymbolCoalescingRing(std::size_t);bool publish(Tick);std::optional<Tick> take();void close();std::size_t replacements()const;private:std::vector<std::optional<Tick>> slots_;std::unordered_map<int,std::size_t> index_;std::size_t head_=0,tail_=0,count_=0,replaced_=0;bool closed_=false;mutable std::mutex mutex_;};}
"""
    starter=_starter(header,"SymbolCoalescingRing","""SymbolCoalescingRing::SymbolCoalescingRing(std::size_t){}
bool SymbolCoalescingRing::publish(Tick){return false;}
std::optional<Tick> SymbolCoalescingRing::take(){return std::nullopt;}
void SymbolCoalescingRing::close(){}
std::size_t SymbolCoalescingRing::replacements()const{return 0;}""")
    reference="""#include "task.h"
#include <stdexcept>
namespace curriculum{
SymbolCoalescingRing::SymbolCoalescingRing(std::size_t n):slots_(n){if(!n)throw std::invalid_argument("capacity");}
bool SymbolCoalescingRing::publish(Tick t){std::lock_guard<std::mutex> lock(mutex_);if(closed_||t.symbol<=0||t.price<=0)return false;auto it=index_.find(t.symbol);if(it!=index_.end()){slots_[it->second]->price=t.price;++replaced_;return true;}if(count_==slots_.size())return false;slots_[tail_]=t;index_[t.symbol]=tail_;tail_=(tail_+1)%slots_.size();++count_;return true;}
std::optional<Tick> SymbolCoalescingRing::take(){std::lock_guard<std::mutex> lock(mutex_);if(!count_)return std::nullopt;auto out=slots_[head_];index_.erase(out->symbol);slots_[head_].reset();head_=(head_+1)%slots_.size();--count_;return out;}
void SymbolCoalescingRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
std::size_t SymbolCoalescingRing::replacements()const{std::lock_guard<std::mutex> lock(mutex_);return replaced_;}
}
"""
    visible="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::SymbolCoalescingRing r(2);c(r.publish({1,10}));c(r.publish({2,20}));c(r.publish({1,11}));c(r.take()->price==11);c(r.take()->symbol==2);c(r.replacements()==1);return f?1:0;}
"""
    hidden="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::SymbolCoalescingRing r(1);c(r.publish({1,1}));c(!r.publish({2,2}));c(r.publish({1,3}));c(r.take()->price==3);for(int i=1;i<10;++i){c(r.publish({i,i}));c(r.take()->symbol==i);}return f?1:0;}
"""
    return _case(legacy_id="pcr-market-ticks",class_name="SymbolCoalescingRing",kind="keyed_in_place_coalescing",title="Market symbol coalescing ring",objective="A keyed ring that updates a pending symbol in place.",contract="A pending symbol update replaces only its price and keeps its original order. New symbols consume capacity; taking frees their membership.",header=header,starter=starter,reference=reference,visible_test=visible,hidden_test=hidden,markers=("index_.find(t.symbol)","++replaced_"))


def _gps() -> CaseAssets:
    header="""#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <vector>
namespace curriculum{struct GpsSample{int timestamp;int point;};class GpsWatermarkRing{public:explicit GpsWatermarkRing(std::size_t);bool publish(GpsSample);bool advance_watermark(int);std::vector<GpsSample> take_ready();void close();private:struct Slot{std::optional<GpsSample> sample;std::size_t order=0;};std::vector<Slot> slots_;int watermark_=0;std::size_t order_=1;bool closed_=false;std::mutex mutex_;};}
"""
    starter=_starter(header,"GpsWatermarkRing","""GpsWatermarkRing::GpsWatermarkRing(std::size_t){}
bool GpsWatermarkRing::publish(GpsSample){return false;}
bool GpsWatermarkRing::advance_watermark(int){return false;}
std::vector<GpsSample> GpsWatermarkRing::take_ready(){return {};}
void GpsWatermarkRing::close(){}""")
    reference="""#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum{
GpsWatermarkRing::GpsWatermarkRing(std::size_t n):slots_(n){if(!n)throw std::invalid_argument("capacity");}
bool GpsWatermarkRing::publish(GpsSample s){std::lock_guard<std::mutex> lock(mutex_);if(closed_||s.timestamp<=watermark_||s.point<=0)return false;for(auto& slot:slots_)if(!slot.sample){slot={s,order_++};return true;}return false;}
bool GpsWatermarkRing::advance_watermark(int value){std::lock_guard<std::mutex> lock(mutex_);if(value<=watermark_)return false;watermark_=value;return true;}
std::vector<GpsSample> GpsWatermarkRing::take_ready(){std::lock_guard<std::mutex> lock(mutex_);std::vector<std::pair<GpsSample,std::size_t>> ready;for(auto& slot:slots_)if(slot.sample&&slot.sample->timestamp<=watermark_){ready.push_back({*slot.sample,slot.order});slot.sample.reset();}std::sort(ready.begin(),ready.end(),[](const auto& a,const auto& b){return a.first.timestamp!=b.first.timestamp?a.first.timestamp<b.first.timestamp:a.second<b.second;});std::vector<GpsSample> out;for(const auto& item:ready)out.push_back(item.first);return out;}
void GpsWatermarkRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
}
"""
    visible="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::GpsWatermarkRing r(3);c(r.publish({5,50}));c(r.publish({3,30}));c(r.advance_watermark(3));auto x=r.take_ready();c(x.size()==1&&x[0].point==30);c(!r.publish({2,20}));return f?1:0;}
"""
    hidden="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::GpsWatermarkRing r(2);c(r.publish({2,1}));c(r.publish({2,2}));c(!r.publish({3,3}));c(r.advance_watermark(2));auto x=r.take_ready();c(x.size()==2&&x[0].point==1&&x[1].point==2);c(!r.advance_watermark(2));return f?1:0;}
"""
    return _case(legacy_id="pcr-gps-samples",class_name="GpsWatermarkRing",kind="watermark_release_batch",title="GPS watermark batch ring",objective="A bounded out-of-order sample ring released by watermark.",contract="Samples newer than the watermark may arrive out of order. Advancing a monotonic watermark releases all eligible samples ordered by timestamp then admission.",header=header,starter=starter,reference=reference,visible_test=visible,hidden_test=hidden,markers=("sample->timestamp<=watermark_","ready.begin(),ready.end()"))


def _build_epoch() -> CaseAssets:
    header="""#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <vector>
namespace curriculum{struct BuildEvent{int worker;int epoch;};class BuildEpochRing{public:BuildEpochRing(int,std::size_t);bool arrive(BuildEvent);std::optional<int> take_completed_epoch();void close();private:struct Slot{int epoch=-1;std::vector<bool> workers;std::size_t count=0;};int workers_,next_epoch_=0;std::vector<Slot> slots_;bool closed_=false;std::mutex mutex_;};}
"""
    starter=_starter(header,"BuildEpochRing","""BuildEpochRing::BuildEpochRing(int workers,std::size_t):workers_(workers){}
bool BuildEpochRing::arrive(BuildEvent){return false;}
std::optional<int> BuildEpochRing::take_completed_epoch(){return std::nullopt;}
void BuildEpochRing::close(){}""")
    reference="""#include "task.h"
#include <stdexcept>
namespace curriculum{
BuildEpochRing::BuildEpochRing(int workers,std::size_t window):workers_(workers),slots_(window){if(workers<=0||!window)throw std::invalid_argument("shape");}
bool BuildEpochRing::arrive(BuildEvent e){std::lock_guard<std::mutex> lock(mutex_);if(closed_||e.worker<0||e.worker>=workers_||e.epoch<next_epoch_||e.epoch>=next_epoch_+static_cast<int>(slots_.size()))return false;auto& slot=slots_[static_cast<std::size_t>(e.epoch)%slots_.size()];if(slot.epoch!=e.epoch){slot.epoch=e.epoch;slot.workers.assign(workers_,false);slot.count=0;}if(slot.workers[e.worker])return false;slot.workers[e.worker]=true;++slot.count;return true;}
std::optional<int> BuildEpochRing::take_completed_epoch(){std::lock_guard<std::mutex> lock(mutex_);auto& slot=slots_[static_cast<std::size_t>(next_epoch_)%slots_.size()];if(slot.epoch!=next_epoch_||slot.count!=static_cast<std::size_t>(workers_))return std::nullopt;int out=next_epoch_++;slot=Slot{};return out;}
void BuildEpochRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
}
"""
    visible="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::BuildEpochRing r(2,2);c(r.arrive({0,1}));c(r.arrive({0,0}));c(!r.take_completed_epoch());c(r.arrive({1,0}));c(r.take_completed_epoch()==0);c(r.arrive({1,1}));c(r.take_completed_epoch()==1);return f?1:0;}
"""
    hidden="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::BuildEpochRing r(3,1);c(r.arrive({0,0}));c(!r.arrive({0,0}));c(!r.arrive({1,1}));c(r.arrive({1,0}));c(r.arrive({2,0}));c(r.take_completed_epoch()==0);c(r.arrive({2,1}));return f?1:0;}
"""
    return _case(legacy_id="pcr-build-events",class_name="BuildEpochRing",kind="epoch_worker_barrier",title="Build epoch barrier ring",objective="A modular window of per-worker epoch barriers.",contract="Each worker arrives once per bounded epoch. Only the fully populated current epoch is consumable, so completion remains in epoch order.",header=header,starter=starter,reference=reference,visible_test=visible,hidden_test=hidden,markers=("slot.workers[e.worker]","slot.count!=static_cast<std::size_t>(workers_)"))



def _video() -> CaseAssets:
    h="""#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <vector>
namespace curriculum{struct Reservation{std::size_t slot;unsigned generation;};class SegmentCommitRing{public:explicit SegmentCommitRing(std::size_t);std::optional<Reservation> reserve();bool commit(Reservation,int);bool cancel(Reservation);std::optional<int> take();void close();private:enum class State{free,reserved,committed,cancelled};struct Slot{State state=State::free;unsigned generation=0;int value=0;};std::vector<Slot> slots_;std::size_t head_=0,tail_=0,count_=0;bool closed_=false;std::mutex mutex_;};}
"""
    s=_starter(h,"SegmentCommitRing","""SegmentCommitRing::SegmentCommitRing(std::size_t){}
std::optional<Reservation> SegmentCommitRing::reserve(){return std::nullopt;}
bool SegmentCommitRing::commit(Reservation,int){return false;}
bool SegmentCommitRing::cancel(Reservation){return false;}
std::optional<int> SegmentCommitRing::take(){return std::nullopt;}
void SegmentCommitRing::close(){}""")
    r="""#include "task.h"
#include <stdexcept>
namespace curriculum{
SegmentCommitRing::SegmentCommitRing(std::size_t n):slots_(n){if(!n)throw std::invalid_argument("capacity");}
std::optional<Reservation> SegmentCommitRing::reserve(){std::lock_guard<std::mutex> lock(mutex_);if(closed_||count_==slots_.size())return std::nullopt;auto& x=slots_[tail_];x.state=State::reserved;++x.generation;Reservation out{tail_,x.generation};tail_=(tail_+1)%slots_.size();++count_;return out;}
bool SegmentCommitRing::commit(Reservation t,int v){std::lock_guard<std::mutex> lock(mutex_);if(t.slot>=slots_.size()||v<=0)return false;auto& x=slots_[t.slot];if(x.generation!=t.generation||x.state!=State::reserved)return false;x.value=v;x.state=State::committed;return true;}
bool SegmentCommitRing::cancel(Reservation t){std::lock_guard<std::mutex> lock(mutex_);if(t.slot>=slots_.size())return false;auto& x=slots_[t.slot];if(x.generation!=t.generation||x.state!=State::reserved)return false;x.state=State::cancelled;return true;}
std::optional<int> SegmentCommitRing::take(){std::lock_guard<std::mutex> lock(mutex_);while(count_&&slots_[head_].state==State::cancelled){slots_[head_].state=State::free;head_=(head_+1)%slots_.size();--count_;}if(!count_||slots_[head_].state!=State::committed)return std::nullopt;int out=slots_[head_].value;slots_[head_].state=State::free;head_=(head_+1)%slots_.size();--count_;return out;}
void SegmentCommitRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
}
"""
    v="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::SegmentCommitRing r(2);auto a=r.reserve(),b=r.reserve();c(a&&b);c(r.commit(*b,2));c(!r.take());c(r.cancel(*a));c(r.take()==2);c(!r.commit(*a,3));return f?1:0;}
"""
    x="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::SegmentCommitRing r(1);auto a=r.reserve();c(bool(a));c(!r.reserve());c(r.commit(*a,7));c(r.take()==7);auto b=r.reserve();c(b&&b->generation!=a->generation);c(!r.commit(*a,8));return f?1:0;}
"""
    return _case(legacy_id="pcr-video-segments",class_name="SegmentCommitRing",kind="reservation_commit_slots",title="Video reservation/commit ring",objective="A two-phase reservation and commit ring.",contract="Reserve claims a generation-stamped slot. Commit or cancel validates the ticket; consumers cannot pass an unresolved head but skip cancelled heads.",header=h,starter=s,reference=r,visible_test=v,hidden_test=x,markers=("State::reserved","x.generation!=t.generation"))


def _sensor() -> CaseAssets:
    h="""#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <vector>
namespace curriculum{struct SensorSample{int source;int timestamp;int value;};class SensorMergeRing{public:SensorMergeRing(int,std::size_t);bool publish(SensorSample);bool watermark(int,int);std::optional<SensorSample> take_safe();void close();private:std::vector<std::vector<std::optional<SensorSample>>> rings_;std::vector<std::size_t> head_,tail_,count_;std::vector<int> last_,watermarks_;bool closed_=false;std::mutex mutex_;};}
"""
    s=_starter(h,"SensorMergeRing","""SensorMergeRing::SensorMergeRing(int,std::size_t){}
bool SensorMergeRing::publish(SensorSample){return false;}
bool SensorMergeRing::watermark(int,int){return false;}
std::optional<SensorSample> SensorMergeRing::take_safe(){return std::nullopt;}
void SensorMergeRing::close(){}""")
    r="""#include "task.h"
#include <stdexcept>
namespace curriculum{
SensorMergeRing::SensorMergeRing(int n,std::size_t cap):rings_(n,std::vector<std::optional<SensorSample>>(cap)),head_(n),tail_(n),count_(n),last_(n),watermarks_(n){if(n<=0||!cap)throw std::invalid_argument("shape");}
bool SensorMergeRing::publish(SensorSample x){std::lock_guard<std::mutex> lock(mutex_);if(closed_||x.source<=0||static_cast<std::size_t>(x.source)>rings_.size())return false;auto s=x.source-1;if(x.timestamp<=last_[s]||count_[s]==rings_[s].size())return false;rings_[s][tail_[s]]=x;tail_[s]=(tail_[s]+1)%rings_[s].size();++count_[s];last_[s]=x.timestamp;return true;}
bool SensorMergeRing::watermark(int source,int stamp){std::lock_guard<std::mutex> lock(mutex_);if(source<=0||static_cast<std::size_t>(source)>rings_.size()||stamp<watermarks_[source-1])return false;watermarks_[source-1]=stamp;return true;}
std::optional<SensorSample> SensorMergeRing::take_safe(){std::lock_guard<std::mutex> lock(mutex_);int best=-1;for(std::size_t s=0;s<rings_.size();++s)if(count_[s]&&(best<0||rings_[s][head_[s]]->timestamp<rings_[best][head_[best]]->timestamp))best=static_cast<int>(s);if(best<0)return std::nullopt;int stamp=rings_[best][head_[best]]->timestamp;for(int mark:watermarks_)if(mark<stamp)return std::nullopt;auto out=rings_[best][head_[best]];rings_[best][head_[best]].reset();head_[best]=(head_[best]+1)%rings_[best].size();--count_[best];return out;}
void SensorMergeRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
}
"""
    v="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::SensorMergeRing r(2,2);c(r.publish({1,3,30}));c(r.publish({2,2,20}));c(r.watermark(1,3));c(r.watermark(2,3));c(r.take_safe()->timestamp==2);c(r.take_safe()->timestamp==3);return f?1:0;}
"""
    x="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::SensorMergeRing r(2,1);c(r.publish({1,2,1}));c(r.watermark(1,2));c(!r.take_safe());c(r.watermark(2,2));c(r.take_safe()->source==1);c(!r.publish({1,2,2}));return f?1:0;}
"""
    return _case(legacy_id="pcr-sensor-fusion",class_name="SensorMergeRing",kind="watermarked_kway_merge",title="Sensor timestamp merge ring",objective="Per-source rings merged only under safe watermarks.",contract="Source timestamps strictly increase. The global minimum head is consumable only when every source watermark proves no earlier sample can arrive.",header=h,starter=s,reference=r,visible_test=v,hidden_test=x,markers=("for(int mark:watermarks_)","rings_[best][head_[best]]"))


def _print() -> CaseAssets:
    h="""#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <vector>
namespace curriculum{struct PrintJob{int id;int priority;};class AgingPrintRing{public:explicit AgingPrintRing(std::size_t);bool submit(PrintJob);void advance_age();std::optional<PrintJob> take();void close();private:struct Slot{std::optional<PrintJob> job;int age=0;std::size_t order=0;};std::vector<Slot> slots_;std::size_t order_=1;bool closed_=false;std::mutex mutex_;};}
"""
    s=_starter(h,"AgingPrintRing","""AgingPrintRing::AgingPrintRing(std::size_t){}
bool AgingPrintRing::submit(PrintJob){return false;}
void AgingPrintRing::advance_age(){}
std::optional<PrintJob> AgingPrintRing::take(){return std::nullopt;}
void AgingPrintRing::close(){}""")
    r="""#include "task.h"
#include <stdexcept>
namespace curriculum{
AgingPrintRing::AgingPrintRing(std::size_t n):slots_(n){if(!n)throw std::invalid_argument("capacity");}
bool AgingPrintRing::submit(PrintJob j){std::lock_guard<std::mutex> lock(mutex_);if(closed_||j.id<=0||j.priority<0||j.priority>2)return false;for(auto& s:slots_)if(!s.job){s={j,0,order_++};return true;}return false;}
void AgingPrintRing::advance_age(){std::lock_guard<std::mutex> lock(mutex_);for(auto& s:slots_)if(s.job&&s.job->priority<2&&++s.age==2){++s.job->priority;s.age=0;}}
std::optional<PrintJob> AgingPrintRing::take(){std::lock_guard<std::mutex> lock(mutex_);Slot* best=nullptr;for(auto& s:slots_)if(s.job&&(!best||s.job->priority>best->job->priority||(s.job->priority==best->job->priority&&s.order<best->order)))best=&s;if(!best)return std::nullopt;auto out=best->job;best->job.reset();return out;}
void AgingPrintRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
}
"""
    v="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::AgingPrintRing r(3);c(r.submit({1,0}));c(r.submit({2,1}));c(r.take()->id==2);r.advance_age();r.advance_age();c(r.take()->id==1);return f?1:0;}
"""
    x="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::AgingPrintRing r(2);c(r.submit({1,0}));c(r.submit({2,0}));r.advance_age();r.advance_age();c(r.take()->id==1);c(r.take()->id==2);c(!r.submit({3,3}));return f?1:0;}
"""
    return _case(legacy_id="pcr-print-pipeline",class_name="AgingPrintRing",kind="aging_priority_slots",title="Aging print priority ring",objective="Bounded priority slots with deterministic age promotion.",contract="Jobs have priorities zero through two. Two age advances promote a waiting job one level; take selects highest priority then oldest admission.",header=h,starter=s,reference=r,visible_test=v,hidden_test=x,markers=("++s.age==2","s.job->priority>best->job->priority"))


def _payment() -> CaseAssets:
    h="""#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <vector>
namespace curriculum{struct PaymentEvent{int id;unsigned previous;unsigned digest;};class PaymentChainRing{public:explicit PaymentChainRing(std::size_t);bool publish(PaymentEvent);std::optional<PaymentEvent> audit();void close();unsigned tail_digest()const;static unsigned compute(int,unsigned);private:std::vector<std::optional<PaymentEvent>> slots_;std::size_t head_=0,tail_=0,count_=0;unsigned chain_=2166136261u;bool closed_=false;mutable std::mutex mutex_;};}
"""
    s=_starter(h,"PaymentChainRing","""PaymentChainRing::PaymentChainRing(std::size_t){}
bool PaymentChainRing::publish(PaymentEvent){return false;}
std::optional<PaymentEvent> PaymentChainRing::audit(){return std::nullopt;}
void PaymentChainRing::close(){}
unsigned PaymentChainRing::tail_digest()const{return 0;}
unsigned PaymentChainRing::compute(int,unsigned){return 0;}""")
    r="""#include "task.h"
#include <stdexcept>
namespace curriculum{
PaymentChainRing::PaymentChainRing(std::size_t n):slots_(n){if(!n)throw std::invalid_argument("capacity");}
unsigned PaymentChainRing::compute(int id,unsigned previous){return previous*16777619u^static_cast<unsigned>(id);}
bool PaymentChainRing::publish(PaymentEvent e){std::lock_guard<std::mutex> lock(mutex_);if(closed_||e.id<=0||count_==slots_.size()||e.previous!=chain_||e.digest!=compute(e.id,e.previous))return false;slots_[tail_]=e;tail_=(tail_+1)%slots_.size();++count_;chain_=e.digest;return true;}
std::optional<PaymentEvent> PaymentChainRing::audit(){std::lock_guard<std::mutex> lock(mutex_);if(!count_)return std::nullopt;auto out=slots_[head_];slots_[head_].reset();head_=(head_+1)%slots_.size();--count_;return out;}
void PaymentChainRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
unsigned PaymentChainRing::tail_digest()const{std::lock_guard<std::mutex> lock(mutex_);return chain_;}
}
"""
    v="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::PaymentChainRing r(2);unsigned p=r.tail_digest(),d=curriculum::PaymentChainRing::compute(1,p);c(r.publish({1,p,d}));c(!r.publish({2,p,0}));c(r.audit()->id==1);return f?1:0;}
"""
    x="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::PaymentChainRing r(1);unsigned p=r.tail_digest(),d=curriculum::PaymentChainRing::compute(1,p);c(r.publish({1,p,d}));c(!r.publish({2,d,curriculum::PaymentChainRing::compute(2,d)}));c(r.audit()->digest==d);unsigned e=curriculum::PaymentChainRing::compute(2,d);c(r.publish({2,d,e}));return f?1:0;}
"""
    return _case(legacy_id="pcr-payment-events",class_name="PaymentChainRing",kind="hash_chain_admission",title="Payment hash-chain ring",objective="A ring that admits only a valid event hash chain.",contract="Each event previous digest must equal the accepted chain tail and its digest must match compute. Invalid links never mutate the tail.",header=h,starter=s,reference=r,visible_test=v,hidden_test=x,markers=("e.previous!=chain_","chain_=e.digest"))


def _file() -> CaseAssets:
    h="""#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <unordered_map>
#include <vector>
namespace curriculum{enum class ChangeKind{create,modify,erase};struct FileChange{int path;ChangeKind kind;};class FileDebounceRing{public:explicit FileDebounceRing(std::size_t);bool publish(FileChange);std::optional<FileChange> take();void close();private:struct Slot{std::optional<FileChange> change;std::size_t order=0;};std::vector<Slot> slots_;std::unordered_map<int,std::size_t> index_;std::size_t order_=1;bool closed_=false;std::mutex mutex_;};}
"""
    s=_starter(h,"FileDebounceRing","""FileDebounceRing::FileDebounceRing(std::size_t){}
bool FileDebounceRing::publish(FileChange){return false;}
std::optional<FileChange> FileDebounceRing::take(){return std::nullopt;}
void FileDebounceRing::close(){}""")
    r="""#include "task.h"
#include <stdexcept>
namespace curriculum{
FileDebounceRing::FileDebounceRing(std::size_t n):slots_(n){if(!n)throw std::invalid_argument("capacity");}
bool FileDebounceRing::publish(FileChange c){std::lock_guard<std::mutex> lock(mutex_);if(closed_||c.path<=0)return false;auto it=index_.find(c.path);if(it!=index_.end()){auto& old=slots_[it->second].change;if(old->kind==ChangeKind::create&&c.kind==ChangeKind::erase){old.reset();index_.erase(it);return true;}if(old->kind==ChangeKind::create&&c.kind==ChangeKind::modify)return true;if(old->kind==ChangeKind::erase&&c.kind==ChangeKind::create)old->kind=ChangeKind::modify;else old->kind=c.kind;return true;}for(std::size_t i=0;i<slots_.size();++i)if(!slots_[i].change){slots_[i]={c,order_++};index_[c.path]=i;return true;}return false;}
std::optional<FileChange> FileDebounceRing::take(){std::lock_guard<std::mutex> lock(mutex_);Slot* best=nullptr;for(auto& s:slots_)if(s.change&&(!best||s.order<best->order))best=&s;if(!best)return std::nullopt;auto out=best->change;index_.erase(out->path);best->change.reset();return out;}
void FileDebounceRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
}
"""
    v="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::FileDebounceRing r(2);c(r.publish({1,curriculum::ChangeKind::create}));c(r.publish({1,curriculum::ChangeKind::modify}));c(r.take()->kind==curriculum::ChangeKind::create);c(r.publish({2,curriculum::ChangeKind::create}));c(r.publish({2,curriculum::ChangeKind::erase}));c(!r.take());return f?1:0;}
"""
    x="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::FileDebounceRing r(2);c(r.publish({1,curriculum::ChangeKind::erase}));c(r.publish({1,curriculum::ChangeKind::create}));c(r.take()->kind==curriculum::ChangeKind::modify);c(!r.publish({0,curriculum::ChangeKind::create}));return f?1:0;}
"""
    return _case(legacy_id="pcr-file-watch",class_name="FileDebounceRing",kind="change_algebra_debounce",title="File-change debounce ring",objective="A path-indexed change algebra over bounded slots.",contract="Create then erase cancels; create then modify stays create; erase then create becomes modify. Reduction never moves unrelated paths.",header=h,starter=s,reference=r,visible_test=v,hidden_test=x,markers=("ChangeKind::create&&c.kind==ChangeKind::erase","old->kind=ChangeKind::modify"))



def _robot() -> CaseAssets:
    h="""#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <unordered_set>
#include <vector>
namespace curriculum{struct Dispatch{int id;int attempt;};class CommandRetryRing{public:CommandRetryRing(std::size_t,int);bool submit(int);std::optional<Dispatch> dispatch();bool acknowledge(int,bool);void close();private:std::vector<std::optional<Dispatch>> slots_;std::unordered_set<int> ids_;std::optional<Dispatch> flight_;std::size_t head_=0,tail_=0,count_=0;int max_;bool closed_=false;std::mutex mutex_;};}
"""
    s=_starter(h,"CommandRetryRing","""CommandRetryRing::CommandRetryRing(std::size_t,int max):max_(max){}
bool CommandRetryRing::submit(int){return false;}
std::optional<Dispatch> CommandRetryRing::dispatch(){return std::nullopt;}
bool CommandRetryRing::acknowledge(int,bool){return false;}
void CommandRetryRing::close(){}""")
    r="""#include "task.h"
#include <stdexcept>
namespace curriculum{
CommandRetryRing::CommandRetryRing(std::size_t n,int max):slots_(n),max_(max){if(!n||max<=0)throw std::invalid_argument("shape");}
bool CommandRetryRing::submit(int id){std::lock_guard<std::mutex> lock(mutex_);if(closed_||id<=0||ids_.count(id)||count_==slots_.size())return false;slots_[tail_]=Dispatch{id,1};tail_=(tail_+1)%slots_.size();++count_;ids_.insert(id);return true;}
std::optional<Dispatch> CommandRetryRing::dispatch(){std::lock_guard<std::mutex> lock(mutex_);if(flight_||!count_)return std::nullopt;flight_=slots_[head_];slots_[head_].reset();head_=(head_+1)%slots_.size();--count_;return flight_;}
bool CommandRetryRing::acknowledge(int id,bool ok){std::lock_guard<std::mutex> lock(mutex_);if(!flight_||flight_->id!=id)return false;auto item=*flight_;flight_.reset();if(ok||item.attempt>=max_){ids_.erase(id);return true;}++item.attempt;slots_[tail_]=item;tail_=(tail_+1)%slots_.size();++count_;return true;}
void CommandRetryRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
}
"""
    v="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::CommandRetryRing r(2,2);c(r.submit(1));c(r.dispatch()->attempt==1);c(r.acknowledge(1,false));c(r.dispatch()->attempt==2);c(r.acknowledge(1,true));c(r.submit(1));return f?1:0;}
"""
    x="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::CommandRetryRing r(1,1);c(r.submit(1));c(!r.submit(1));c(r.dispatch()->id==1);c(!r.dispatch());c(!r.acknowledge(2,true));c(r.acknowledge(1,false));c(!r.dispatch());return f?1:0;}
"""
    return _case(legacy_id="pcr-robot-commands",class_name="CommandRetryRing",kind="dispatch_ack_retry",title="Robot command retry ring",objective="A dispatch/acknowledge protocol with bounded retry rotation.",contract="Only one command is in flight. Negative acknowledgement requeues with an incremented attempt until the limit; duplicate IDs cover queued and in-flight state.",header=h,starter=s,reference=r,visible_test=v,hidden_test=x,markers=("if(flight_||!count_)","++item.attempt"))


def _support() -> CaseAssets:
    h="""#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <vector>
namespace curriculum{class BroadcastNotificationRing{public:BroadcastNotificationRing(std::size_t,int);bool publish(int);std::optional<int> take(int);void close();std::size_t retained()const;private:struct Slot{int value=0;std::size_t sequence=0;bool occupied=false;};std::vector<Slot> slots_;std::vector<std::size_t> cursors_;std::size_t next_=0,base_=0;bool closed_=false;mutable std::mutex mutex_;void reclaim();};}
"""
    s=_starter(h,"BroadcastNotificationRing","""BroadcastNotificationRing::BroadcastNotificationRing(std::size_t,int){}
bool BroadcastNotificationRing::publish(int){return false;}
std::optional<int> BroadcastNotificationRing::take(int){return std::nullopt;}
void BroadcastNotificationRing::close(){}
std::size_t BroadcastNotificationRing::retained()const{return 0;}
void BroadcastNotificationRing::reclaim(){}""")
    r="""#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum{
BroadcastNotificationRing::BroadcastNotificationRing(std::size_t n,int consumers):slots_(n),cursors_(consumers){if(!n||consumers<=0)throw std::invalid_argument("shape");}
bool BroadcastNotificationRing::publish(int value){std::lock_guard<std::mutex> lock(mutex_);if(closed_||value<=0||next_-base_==slots_.size())return false;auto& s=slots_[next_%slots_.size()];s={value,next_,true};++next_;return true;}
std::optional<int> BroadcastNotificationRing::take(int consumer){std::lock_guard<std::mutex> lock(mutex_);if(consumer<0||static_cast<std::size_t>(consumer)>=cursors_.size()||cursors_[consumer]>=next_)return std::nullopt;auto seq=cursors_[consumer]++;auto& s=slots_[seq%slots_.size()];if(!s.occupied||s.sequence!=seq)return std::nullopt;int out=s.value;reclaim();return out;}
void BroadcastNotificationRing::reclaim(){auto minimum=*std::min_element(cursors_.begin(),cursors_.end());while(base_<minimum){slots_[base_%slots_.size()].occupied=false;++base_;}}
void BroadcastNotificationRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
std::size_t BroadcastNotificationRing::retained()const{std::lock_guard<std::mutex> lock(mutex_);return next_-base_;}
}
"""
    v="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::BroadcastNotificationRing r(2,2);c(r.publish(7));c(r.take(0)==7);c(r.retained()==1);c(r.take(1)==7);c(r.retained()==0);return f?1:0;}
"""
    x="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::BroadcastNotificationRing r(1,2);c(r.publish(1));c(!r.publish(2));c(r.take(0)==1);c(!r.publish(2));c(r.take(1)==1);c(r.publish(2));c(!r.take(9));return f?1:0;}
"""
    return _case(legacy_id="pcr-support-notifications",class_name="BroadcastNotificationRing",kind="broadcast_consumer_cursors",title="Support broadcast cursor ring",objective="A retained broadcast ring with independent consumer cursors.",contract="Every accepted notification is delivered once to every consumer. Capacity is reclaimed only after the minimum cursor passes a slot.",header=h,starter=s,reference=r,visible_test=v,hidden_test=x,markers=("std::min_element(cursors_","s.sequence!=seq"))


def _weather() -> CaseAssets:
    h="""#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <vector>
namespace curriculum{struct WeatherSummary{int tick;int minimum;int maximum;int count;};class WeatherBucketRing{public:explicit WeatherBucketRing(std::size_t);bool publish(int,int);std::optional<WeatherSummary> take_bucket(int);void close();private:struct Bucket{int stamp=-1,minimum=0,maximum=0,count=0;};std::vector<Bucket> buckets_;int latest_=-1;bool closed_=false;std::mutex mutex_;};}
"""
    s=_starter(h,"WeatherBucketRing","""WeatherBucketRing::WeatherBucketRing(std::size_t){}
bool WeatherBucketRing::publish(int,int){return false;}
std::optional<WeatherSummary> WeatherBucketRing::take_bucket(int){return std::nullopt;}
void WeatherBucketRing::close(){}""")
    r="""#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum{
WeatherBucketRing::WeatherBucketRing(std::size_t n):buckets_(n){if(!n)throw std::invalid_argument("width");}
bool WeatherBucketRing::publish(int tick,int value){std::lock_guard<std::mutex> lock(mutex_);if(closed_||tick<0||tick<latest_)return false;latest_=tick;auto& b=buckets_[static_cast<std::size_t>(tick)%buckets_.size()];if(b.stamp!=tick)b={tick,value,value,1};else{b.minimum=std::min(b.minimum,value);b.maximum=std::max(b.maximum,value);++b.count;}return true;}
std::optional<WeatherSummary> WeatherBucketRing::take_bucket(int tick){std::lock_guard<std::mutex> lock(mutex_);if(tick<0)return std::nullopt;auto& b=buckets_[static_cast<std::size_t>(tick)%buckets_.size()];if(b.stamp!=tick)return std::nullopt;WeatherSummary out{tick,b.minimum,b.maximum,b.count};b=Bucket{};return out;}
void WeatherBucketRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
}
"""
    v="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::WeatherBucketRing r(2);c(r.publish(1,5));c(r.publish(1,2));c(r.publish(1,8));auto x=r.take_bucket(1);c(x&&x->minimum==2&&x->maximum==8&&x->count==3);return f?1:0;}
"""
    x="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::WeatherBucketRing r(2);c(r.publish(1,1));c(r.publish(3,3));c(!r.take_bucket(1));c(r.take_bucket(3)->count==1);c(!r.publish(2,2));return f?1:0;}
"""
    return _case(legacy_id="pcr-weather-station",class_name="WeatherBucketRing",kind="stamped_aggregate_buckets",title="Weather aggregation bucket ring",objective="A stamped modular ring of aggregates rather than events.",contract="Ticks are nondecreasing. Values at one tick aggregate min, max, and count; a newer colliding stamp expires the older bucket.",header=h,starter=s,reference=r,visible_test=v,hidden_test=x,markers=("b.stamp!=tick","++b.count"))


def _game() -> CaseAssets:
    h="""#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <unordered_map>
#include <vector>
namespace curriculum{struct Input{int tick;int player;int action;};class GameTickRing{public:explicit GameTickRing(std::size_t);bool publish(Input);bool seal(int);std::optional<std::vector<Input>> take_tick();void close();private:struct Slot{int tick=-1;std::unordered_map<int,int> actions;bool sealed=false;};std::vector<Slot> slots_;bool closed_=false;std::mutex mutex_;};}
"""
    s=_starter(h,"GameTickRing","""GameTickRing::GameTickRing(std::size_t){}
bool GameTickRing::publish(Input){return false;}
bool GameTickRing::seal(int){return false;}
std::optional<std::vector<Input>> GameTickRing::take_tick(){return std::nullopt;}
void GameTickRing::close(){}""")
    r="""#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum{
GameTickRing::GameTickRing(std::size_t n):slots_(n){if(!n)throw std::invalid_argument("width");}
bool GameTickRing::publish(Input in){std::lock_guard<std::mutex> lock(mutex_);if(closed_||in.tick<0||in.player<=0||in.action<=0)return false;auto& s=slots_[static_cast<std::size_t>(in.tick)%slots_.size()];if(s.tick!=in.tick){if(s.tick>=0)return false;s.tick=in.tick;}if(s.sealed)return false;s.actions[in.player]=in.action;return true;}
bool GameTickRing::seal(int tick){std::lock_guard<std::mutex> lock(mutex_);if(tick<0)return false;auto& s=slots_[static_cast<std::size_t>(tick)%slots_.size()];if(s.tick!=tick||s.sealed)return false;s.sealed=true;return true;}
std::optional<std::vector<Input>> GameTickRing::take_tick(){std::lock_guard<std::mutex> lock(mutex_);Slot* best=nullptr;for(auto& s:slots_)if(s.sealed&&(!best||s.tick<best->tick))best=&s;if(!best)return std::nullopt;std::vector<Input> out;for(const auto& item:best->actions)out.push_back({best->tick,item.first,item.second});std::sort(out.begin(),out.end(),[](const Input&a,const Input&b){return a.player<b.player;});*best=Slot{};return out;}
void GameTickRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
}
"""
    v="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::GameTickRing r(2);c(r.publish({1,2,4}));c(r.publish({1,1,3}));c(r.publish({1,2,5}));c(r.seal(1));auto x=r.take_tick();c(x&&x->size()==2&&(*x)[1].action==5);return f?1:0;}
"""
    x="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::GameTickRing r(2);c(r.publish({2,1,1}));c(r.publish({1,1,1}));c(r.seal(2));c(r.seal(1));c(r.take_tick()->front().tick==1);c(r.take_tick()->front().tick==2);c(!r.seal(2));return f?1:0;}
"""
    return _case(legacy_id="pcr-game-input",class_name="GameTickRing",kind="sealed_tick_snapshots",title="Game tick snapshot ring",objective="A ring of sealed per-tick player snapshots.",contract="Only the latest unsealed input per player remains. Sealed ticks are consumed in increasing tick order with players sorted.",header=h,starter=s,reference=r,visible_test=v,hidden_test=x,markers=("s.actions[in.player]=in.action","s.sealed&&(!best"))


def _warehouse() -> CaseAssets:
    h="""#pragma once
#include <cstddef>
#include <mutex>
#include <optional>
#include <unordered_map>
#include <vector>
namespace curriculum{struct Scan{int parcel;int station;};class ScanDedupRing{public:ScanDedupRing(std::size_t,std::size_t);bool submit(Scan);std::optional<Scan> take();void close();private:std::vector<std::optional<Scan>> slots_;std::unordered_map<int,std::size_t> last_;std::size_t head_=0,tail_=0,count_=0,generation_=0,history_;bool closed_=false;std::mutex mutex_;};}
"""
    s=_starter(h,"ScanDedupRing","""ScanDedupRing::ScanDedupRing(std::size_t,std::size_t):history_(0){}
bool ScanDedupRing::submit(Scan){return false;}
std::optional<Scan> ScanDedupRing::take(){return std::nullopt;}
void ScanDedupRing::close(){}""")
    r="""#include "task.h"
#include <stdexcept>
namespace curriculum{
ScanDedupRing::ScanDedupRing(std::size_t cap,std::size_t history):slots_(cap),history_(history){if(!cap||!history)throw std::invalid_argument("shape");}
bool ScanDedupRing::submit(Scan s){std::lock_guard<std::mutex> lock(mutex_);if(closed_||s.parcel<=0||s.station<=0||count_==slots_.size())return false;auto it=last_.find(s.parcel);if(it!=last_.end()&&generation_-it->second<history_)return false;++generation_;last_[s.parcel]=generation_;slots_[tail_]=s;tail_=(tail_+1)%slots_.size();++count_;return true;}
std::optional<Scan> ScanDedupRing::take(){std::lock_guard<std::mutex> lock(mutex_);if(!count_)return std::nullopt;auto out=slots_[head_];slots_[head_].reset();head_=(head_+1)%slots_.size();--count_;return out;}
void ScanDedupRing::close(){std::lock_guard<std::mutex> lock(mutex_);closed_=true;}
}
"""
    v="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::ScanDedupRing r(3,2);c(r.submit({1,1}));c(!r.submit({1,2}));c(r.take()->parcel==1);c(r.submit({2,1}));c(!r.submit({1,2}));c(r.submit({3,1}));c(r.submit({1,2}));return f?1:0;}
"""
    x="""#include "task.h"
int main(){int f=0;auto c=[&](bool x){if(!x)++f;};curriculum::ScanDedupRing r(1,1);for(int i=1;i<=10;++i){c(r.submit({i,1}));c(r.take()->parcel==i);}c(r.submit({1,2}));c(!r.submit({1,3}));return f?1:0;}
"""
    return _case(legacy_id="pcr-warehouse-scans",class_name="ScanDedupRing",kind="generation_dedup_window",title="Warehouse deduplication ring",objective="A FIFO scan ring with an accepted-generation duplicate window.",contract="A parcel seen among the configured number of recent accepted generations rejects even after consumption; expiry permits it again.",header=h,starter=s,reference=r,visible_test=v,hidden_test=x,markers=("generation_-it->second<history_","last_[s.parcel]=generation_"))



CASES = {
    "audio-spsc-frame-pipe": _audio(),
    "camera-generation-overwrite": _camera(),
    "telemetry-source-quota-ring": _telemetry(),
    "network-fragment-assembly-ring": _network(),
    "log-severity-lane-ring": _logs(),
    "keyboard-transition-coalescer": _keyboard(),
    "can-sequence-reorder-window": _can(),
    "market-symbol-coalescing-ring": _market(),
    "gps-watermark-batch-ring": _gps(),
    "build-epoch-barrier-ring": _build_epoch(),
    "video-reservation-commit-ring": _video(),
    "sensor-timestamp-merge-ring": _sensor(),
    "print-aging-priority-ring": _print(),
    "payment-hash-chain-ring": _payment(),
    "file-change-debounce-ring": _file(),
    "robot-command-retry-ring": _robot(),
    "support-broadcast-cursor-ring": _support(),
    "weather-aggregation-bucket-ring": _weather(),
    "game-tick-snapshot-ring": _game(),
    "warehouse-dedup-window-ring": _warehouse(),
}
