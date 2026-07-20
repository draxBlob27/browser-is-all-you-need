"""Task-specific C++ contracts for run-length-encoding remediation v2."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RleCase:
    legacy_id: str
    task_id: str
    disposition: str
    title: str
    profile: str
    objective: str
    public_api: str
    marker: str
    prompt_terms: tuple[str, ...]
    instructions: str
    header: str
    starter: str
    reference: str
    visible_test: str
    hidden_test: str


CASES = (
RleCase(
"rle-access-badges","rle-access-badges","repair-in-place","Access Badge Denial Tracker","per-door-streaming-denial-streaks",
"Track independent denial streaks per door without merging interleaved doors.",
"AccessBadgeTracker::record; longest_denial; snapshot","door_runs_",("independent", "door", "denial"),
r"""# Instructions

Implement `AccessBadgeTracker`. `record` rejects an empty door or user without mutation.
Each door owns an independent chronological stream: an event extends that door's last run
only when both the user and granted flag match, even when other doors were recorded between.
`longest_denial(door)` returns the longest denied run for that door; ties keep the earlier run.
An absent door returns no value. `snapshot` returns doors lexicographically and each door's runs
in chronological order. Counts must not overflow `std::size_t`.
""",
r"""#pragma once
#include <cstddef>
#include <map>
#include <optional>
#include <string>
#include <vector>
namespace curriculum { struct AccessRun{std::string user;bool granted=false;std::size_t count=0;bool operator==(const AccessRun&o)const{return user==o.user&&granted==o.granted&&count==o.count;}}; struct DoorRuns{std::string door;std::vector<AccessRun> runs;}; class AccessBadgeTracker{std::map<std::string,std::vector<AccessRun>> door_runs_;public:bool record(const std::string&,const std::string&,bool);std::optional<AccessRun> longest_denial(const std::string&)const;std::vector<DoorRuns> snapshot()const;};}
""",
r"""#include "task.h"
namespace curriculum { bool AccessBadgeTracker::record(const std::string&,const std::string&,bool){return false;} std::optional<AccessRun> AccessBadgeTracker::longest_denial(const std::string&)const{return std::nullopt;} std::vector<DoorRuns> AccessBadgeTracker::snapshot()const{return{};} }
""",
r"""#include "task.h"
#include <limits>
namespace curriculum { bool AccessBadgeTracker::record(const std::string&door,const std::string&user,bool granted){if(door.empty()||user.empty())return false;auto& runs=door_runs_[door];if(!runs.empty()&&runs.back().user==user&&runs.back().granted==granted){if(runs.back().count==std::numeric_limits<std::size_t>::max())return false;++runs.back().count;}else runs.push_back({user,granted,1});return true;} std::optional<AccessRun> AccessBadgeTracker::longest_denial(const std::string&door)const{auto it=door_runs_.find(door);if(it==door_runs_.end())return std::nullopt;std::optional<AccessRun> best;for(const auto&r:it->second)if(!r.granted&&(!best||r.count>best->count))best=r;return best;} std::vector<DoorRuns> AccessBadgeTracker::snapshot()const{std::vector<DoorRuns> out;for(const auto&entry:door_runs_)out.push_back({entry.first,entry.second});return out;} }
""",
r"""#include "task.h"
int main(){using namespace curriculum;AccessBadgeTracker t;t.record("east","ana",false);t.record("west","bo",true);t.record("east","ana",false);auto r=t.longest_denial("east");return r&&r->count==2&&t.snapshot().size()==2?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;AccessBadgeTracker t;
auto state=[&](const std::vector<DoorRuns>&want){auto got=t.snapshot();if(got.size()!=want.size())return false;for(std::size_t i=0;i<got.size();++i)if(got[i].door!=want[i].door||got[i].runs!=want[i].runs)return false;return true;};
f+=t.record("","u",false);f+=!state({});f+=t.longest_denial("x").has_value();
f+=!t.record("d","a",false);f+=!state({{"d",{{"a",false,1}}}});auto first=t.longest_denial("d");f+=!first||!(*first==AccessRun{"a",false,1});
f+=!t.record("x","z",true);f+=!state({{"d",{{"a",false,1}}},{"x",{{"z",true,1}}}});
f+=!t.record("d","b",false);f+=!state({{"d",{{"a",false,1},{"b",false,1}}},{"x",{{"z",true,1}}}});
f+=!t.record("d","b",false);f+=!state({{"d",{{"a",false,1},{"b",false,2}}},{"x",{{"z",true,1}}}});
f+=!t.record("d","a",false);f+=!state({{"d",{{"a",false,1},{"b",false,2},{"a",false,1}}},{"x",{{"z",true,1}}}});auto r=t.longest_denial("d");f+=!(r&&r->user=="b"&&r->count==2);return f;}
"""),
RleCase(
"rle-telemetry-packets","packet-run-stream","replace","Packet Run Stream","bounded-count-stream-packets",
"Incrementally emit bounded count packets while retaining a carry packet.","PacketRunStream::push; flush; pending; emitted","pending_",("flush", "pending", "max_count"),
r"""# Instructions

Implement `PacketRunStream(max_count)`. Symbols are nonempty and `max_count` is positive.
`push` rejects an empty symbol without mutation. Equal consecutive symbols extend the pending
packet until `max_count`; the next equal symbol emits the full packet and starts a new pending
packet. A symbol change emits the pending packet. `flush` emits any pending packet and is
idempotent. `emitted` excludes the pending packet; `pending` exposes it.
""",
r"""#pragma once
#include <cstddef>
#include <optional>
#include <string>
#include <vector>
namespace curriculum{struct Packet{std::string symbol;std::size_t count=0;bool operator==(const Packet&o)const{return symbol==o.symbol&&count==o.count;}};class PacketRunStream{std::size_t max_;std::optional<Packet> pending_;std::vector<Packet> emitted_;public:explicit PacketRunStream(std::size_t);bool push(const std::string&);void flush();const std::optional<Packet>& pending()const;const std::vector<Packet>& emitted()const;};}
""",
r"""#include "task.h"
namespace curriculum{PacketRunStream::PacketRunStream(std::size_t m):max_(m){}bool PacketRunStream::push(const std::string&){return false;}void PacketRunStream::flush(){}const std::optional<Packet>&PacketRunStream::pending()const{return pending_;}const std::vector<Packet>&PacketRunStream::emitted()const{return emitted_;}}
""",
r"""#include "task.h"
#include <stdexcept>
namespace curriculum{PacketRunStream::PacketRunStream(std::size_t m):max_(m){if(!m)throw std::invalid_argument("max");}bool PacketRunStream::push(const std::string&s){if(s.empty())return false;if(!pending_)pending_=Packet{s,1};else if(pending_->symbol!=s||pending_->count==max_){emitted_.push_back(*pending_);pending_=Packet{s,1};}else ++pending_->count;return true;}void PacketRunStream::flush(){if(pending_){emitted_.push_back(*pending_);pending_.reset();}}const std::optional<Packet>&PacketRunStream::pending()const{return pending_;}const std::vector<Packet>&PacketRunStream::emitted()const{return emitted_;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;PacketRunStream s(2);s.push("a");s.push("a");s.push("a");return s.emitted()==std::vector<Packet>{{"a",2}}&&s.pending()==Packet{"a",1}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;PacketRunStream s(3);auto state=[&](std::optional<Packet>pending,std::vector<Packet>emitted){return s.pending()==pending&&s.emitted()==emitted;};
f+=s.push("");f+=!state(std::nullopt,{});f+=!s.push("x");f+=!state(Packet{"x",1},{});f+=!s.push("x");f+=!state(Packet{"x",2},{});f+=!s.push("x");f+=!state(Packet{"x",3},{});f+=!s.push("x");f+=!state(Packet{"x",1},{{"x",3}});f+=!s.push("y");f+=!state(Packet{"y",1},{{"x",3},{"x",1}});s.flush();f+=!state(std::nullopt,{{"x",3},{"x",1},{"y",1}});s.flush();f+=!state(std::nullopt,{{"x",3},{"x",1},{"y",1}});return f;}
"""),
RleCase(
"rle-monochrome-raster","raster-row-runs","replace","Raster Row Runs","row-bounded-binary-encoding",
"Encode binary rows while forbidding runs from crossing row boundaries.","encode_raster(rows,width); decode_raster","row_break",("row", "binary", "width"),
r"""# Instructions

Implement `encode_raster(rows,width)` and `decode_raster`. Width must be positive; every row
must contain exactly `width` values and each value must be 0 or 1. Runs never cross a row
boundary, including equal last/first pixels. Encoding invalid input throws. Decoding rejects
zero counts, nonbinary pixels, wrong row totals, or a row-break sequence that does not produce
exactly the declared row count, returning no value.
""",
r"""#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum{struct PixelRun{int value=0;std::size_t count=0;bool row_break=false;};struct RasterRuns{std::size_t width=0,rows=0;std::vector<PixelRun> runs;};RasterRuns encode_raster(const std::vector<std::vector<int>>&,std::size_t);std::optional<std::vector<std::vector<int>>> decode_raster(const RasterRuns&);}
""",
r"""#include "task.h"
namespace curriculum{RasterRuns encode_raster(const std::vector<std::vector<int>>&,std::size_t){return{};}std::optional<std::vector<std::vector<int>>> decode_raster(const RasterRuns&){return std::nullopt;}}
""",
r"""#include "task.h"
#include <stdexcept>
namespace curriculum{RasterRuns encode_raster(const std::vector<std::vector<int>>&rows,std::size_t width){if(!width)throw std::invalid_argument("width");RasterRuns out{width,rows.size(),{}};for(const auto&row:rows){if(row.size()!=width)throw std::invalid_argument("row");for(std::size_t i=0;i<row.size();++i){int v=row[i];if(v!=0&&v!=1)throw std::invalid_argument("pixel");if(i&&out.runs.back().value==v)++out.runs.back().count;else out.runs.push_back({v,1,false});}out.runs.back().row_break=true;}return out;}std::optional<std::vector<std::vector<int>>> decode_raster(const RasterRuns&x){if(!x.width)return std::nullopt;std::vector<std::vector<int>> rows;std::vector<int> row;for(const auto&r:x.runs){if(!r.count||(r.value!=0&&r.value!=1))return std::nullopt;row.insert(row.end(),r.count,r.value);if(row.size()>x.width)return std::nullopt;if(r.row_break){if(row.size()!=x.width)return std::nullopt;rows.push_back(row);row.clear();}}if(!row.empty()||rows.size()!=x.rows)return std::nullopt;return rows;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;std::vector<std::vector<int>> x{{0,0,1},{1,1,0}};auto e=encode_raster(x,3);auto d=decode_raster(e);return d&&*d==x&&e.runs.size()==4?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto e=encode_raster({{1,1},{1,1}},2);if(e.runs.size()!=2)return 1;RasterRuns bad=e;bad.runs[0].count=3;f+=decode_raster(bad).has_value();bad=e;bad.runs[0].row_break=false;f+=decode_raster(bad).has_value();return f;}
"""),
RleCase(
"rle-dna-quality","quality-delta-runs","replace","Quality Delta Runs","signed-delta-run-codec",
"Compress repeated signed differences and reconstruct bounded quality samples.","encode_quality_deltas; decode_quality_deltas","value",("differences", "quality range", "decode_quality_deltas"),
r"""# Instructions

Quality values are integers in [0,93]. The encoded form stores the first value and runs of
equal signed differences between consecutive values. `encode_quality_deltas` rejects invalid
samples with no result. `decode_quality_deltas` rejects zero counts, arithmetic leaving the
quality range, count overflow, or a nonempty delta list without an initial value. Empty input
round-trips as an empty sequence.
""",
r"""#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum{struct DeltaRun{int delta=0;std::size_t count=0;};struct QualityDeltaCode{std::optional<int> first;std::vector<DeltaRun> runs;};std::optional<QualityDeltaCode> encode_quality_deltas(const std::vector<int>&);std::optional<std::vector<int>> decode_quality_deltas(const QualityDeltaCode&);}
""",
r"""#include "task.h"
namespace curriculum{std::optional<QualityDeltaCode> encode_quality_deltas(const std::vector<int>&){return std::nullopt;}std::optional<std::vector<int>> decode_quality_deltas(const QualityDeltaCode&){return std::nullopt;}}
""",
r"""#include "task.h"
#include <limits>
namespace curriculum{std::optional<QualityDeltaCode> encode_quality_deltas(const std::vector<int>&v){QualityDeltaCode out;if(v.empty())return out;for(int x:v)if(x<0||x>93)return std::nullopt;out.first=v[0];for(std::size_t i=1;i<v.size();++i){int d=v[i]-v[i-1];if(!out.runs.empty()&&out.runs.back().delta==d)++out.runs.back().count;else out.runs.push_back({d,1});}return out;}std::optional<std::vector<int>> decode_quality_deltas(const QualityDeltaCode&x){if(!x.first){if(x.runs.empty())return std::vector<int>{};return std::nullopt;}if(*x.first<0||*x.first>93)return std::nullopt;std::vector<int> out{*x.first};long long value=*x.first;for(const auto&r:x.runs){if(!r.count||r.count>1000000)return std::nullopt;for(std::size_t i=0;i<r.count;++i){value+=r.delta;if(value<0||value>93)return std::nullopt;out.push_back(static_cast<int>(value));}}return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;std::vector<int> q{10,12,14,13,12};auto e=encode_quality_deltas(q);auto d=e?decode_quality_deltas(*e):std::nullopt;return e&&e->runs.size()==2&&d&&*d==q?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;f+=!encode_quality_deltas({1,2,3}).has_value();f+=encode_quality_deltas({94}).has_value();QualityDeltaCode bad{90,{{5,1}}};f+=decode_quality_deltas(bad).has_value();bad={10,{{1,0}}};f+=decode_quality_deltas(bad).has_value();return f;}
"""),
RleCase(
"rle-log-severity-spans","severity-time-spans","replace","Severity Time Spans","timestamp-contiguous-span-coalescing",
"Coalesce severity intervals only when timestamps are contiguous.","SeverityTimeline::append; spans; longest_at_least","end_ms",("adjacent", "timestamps", "allowed severities"),
r"""# Instructions

Implement `SeverityTimeline`. Events have nonempty severity and `begin_ms < end_ms`.
Timestamps must be nondecreasing: overlap or time reversal rejects without mutation. Adjacent
events merge only when severity matches and the prior end equals the new begin; gaps remain
separate spans. `longest_at_least(names)` chooses the greatest duration among allowed severities,
ties by earliest begin, and returns no value when absent.
""",
r"""#pragma once
#include <optional>
#include <set>
#include <string>
#include <vector>
namespace curriculum{struct SeveritySpan{std::string severity;long long begin_ms=0,end_ms=0;};class SeverityTimeline{std::vector<SeveritySpan> spans_;public:bool append(const SeveritySpan&);const std::vector<SeveritySpan>&spans()const;std::optional<SeveritySpan> longest_at_least(const std::set<std::string>&)const;};}
""",
r"""#include "task.h"
namespace curriculum{bool SeverityTimeline::append(const SeveritySpan&){return false;}const std::vector<SeveritySpan>&SeverityTimeline::spans()const{return spans_;}std::optional<SeveritySpan> SeverityTimeline::longest_at_least(const std::set<std::string>&)const{return std::nullopt;}}
""",
r"""#include "task.h"
namespace curriculum{bool SeverityTimeline::append(const SeveritySpan&x){if(x.severity.empty()||x.begin_ms>=x.end_ms||(!spans_.empty()&&x.begin_ms<spans_.back().end_ms))return false;if(!spans_.empty()&&x.begin_ms==spans_.back().end_ms&&x.severity==spans_.back().severity)spans_.back().end_ms=x.end_ms;else spans_.push_back(x);return true;}const std::vector<SeveritySpan>&SeverityTimeline::spans()const{return spans_;}std::optional<SeveritySpan> SeverityTimeline::longest_at_least(const std::set<std::string>&allowed)const{std::optional<SeveritySpan> best;for(const auto&s:spans_)if(allowed.count(s.severity)&&(!best||s.end_ms-s.begin_ms>best->end_ms-best->begin_ms))best=s;return best;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;SeverityTimeline t;t.append({"warn",0,3});t.append({"warn",3,8});t.append({"info",10,12});auto x=t.longest_at_least({"warn"});return t.spans().size()==2&&x&&x->end_ms==8?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;SeverityTimeline t;auto state=[&](const std::vector<SeveritySpan>&want){const auto&got=t.spans();if(got.size()!=want.size())return false;for(std::size_t i=0;i<got.size();++i)if(got[i].severity!=want[i].severity||got[i].begin_ms!=want[i].begin_ms||got[i].end_ms!=want[i].end_ms)return false;return true;};
f+=t.append({"",0,1});f+=!state({});f+=!t.append({"x",5,8});f+=!state({{"x",5,8}});f+=t.append({"x",7,9});f+=!state({{"x",5,8}});f+=!t.append({"x",8,10});f+=!state({{"x",5,10}});f+=!t.append({"y",10,12});f+=!state({{"x",5,10},{"y",10,12}});auto best=t.longest_at_least({"x","y"});f+=!(best&&best->severity=="x"&&best->begin_ms==5&&best->end_ms==10);return f;}
"""),
RleCase(
"rle-video-frame-holds","frame-duration-runs","replace","Frame Duration Runs","duration-sum-frame-holds",
"Merge frame hashes while summing validated durations and split at a duration cap.","FrameHoldTrack::append; holds; frame_at","total_ms",("cap", "frame_at", "positive durations"),
r"""# Instructions

`FrameHoldTrack(max_hold_ms)` accepts nonempty frame hashes with positive durations not greater
than the cap. Equal adjacent hashes merge only when their duration sum does not exceed the cap;
otherwise a new hold starts. Invalid input and integer overflow reject without mutation.
`frame_at(offset_ms)` uses zero-based time, returning no value at or beyond total duration.
""",
r"""#pragma once
#include <optional>
#include <string>
#include <vector>
namespace curriculum{struct FrameHold{std::string hash;long long duration_ms=0;};class FrameHoldTrack{long long cap_,total_ms_=0;std::vector<FrameHold> holds_;public:explicit FrameHoldTrack(long long);bool append(std::string,long long);const std::vector<FrameHold>&holds()const;std::optional<std::string> frame_at(long long)const;long long total_ms()const;};}
""",
r"""#include "task.h"
namespace curriculum{FrameHoldTrack::FrameHoldTrack(long long c):cap_(c){}bool FrameHoldTrack::append(std::string,long long){return false;}const std::vector<FrameHold>&FrameHoldTrack::holds()const{return holds_;}std::optional<std::string>FrameHoldTrack::frame_at(long long)const{return std::nullopt;}long long FrameHoldTrack::total_ms()const{return total_ms_;}}
""",
r"""#include "task.h"
#include <limits>
#include <stdexcept>
namespace curriculum{FrameHoldTrack::FrameHoldTrack(long long c):cap_(c){if(c<=0)throw std::invalid_argument("cap");}bool FrameHoldTrack::append(std::string h,long long d){if(h.empty()||d<=0||d>cap_||total_ms_>std::numeric_limits<long long>::max()-d)return false;if(!holds_.empty()&&holds_.back().hash==h&&holds_.back().duration_ms<=cap_-d)holds_.back().duration_ms+=d;else holds_.push_back({std::move(h),d});total_ms_+=d;return true;}const std::vector<FrameHold>&FrameHoldTrack::holds()const{return holds_;}std::optional<std::string>FrameHoldTrack::frame_at(long long at)const{if(at<0||at>=total_ms_)return std::nullopt;long long pos=0;for(const auto&h:holds_){pos+=h.duration_ms;if(at<pos)return h.hash;}return std::nullopt;}long long FrameHoldTrack::total_ms()const{return total_ms_;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;FrameHoldTrack t(10);t.append("a",6);t.append("a",5);return t.holds().size()==2&&t.frame_at(6)==std::optional<std::string>{"a"}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;FrameHoldTrack t(8);auto state=[&](const std::vector<FrameHold>&want,long long total,const std::vector<std::string>&expanded){const auto&got=t.holds();if(got.size()!=want.size()||t.total_ms()!=total)return false;for(std::size_t i=0;i<got.size();++i)if(got[i].hash!=want[i].hash||got[i].duration_ms!=want[i].duration_ms)return false;for(long long i=0;i<total;++i)if(t.frame_at(i)!=std::optional<std::string>{expanded[static_cast<std::size_t>(i)]})return false;return !t.frame_at(-1)&&!t.frame_at(total);};
f+=t.append("",2);f+=!state({},0,{});f+=!t.append("x",3);f+=!state({{"x",3}},3,{"x","x","x"});f+=!t.append("x",5);f+=!state({{"x",8}},8,{"x","x","x","x","x","x","x","x"});f+=!t.append("x",1);f+=!state({{"x",8},{"x",1}},9,{"x","x","x","x","x","x","x","x","x"});f+=!t.append("y",2);f+=!state({{"x",8},{"x",1},{"y",2}},11,{"x","x","x","x","x","x","x","x","x","y","y"});return f;}
"""),
RleCase(
"rle-traffic-lights","signal-phase-coalescer","replace","Signal Phase Coalescer","legal-transition-duration-coalescer",
"Validate a phase state machine before coalescing repeated legal phases.","SignalPhaseCoalescer::append; runs; cycle_ms","allowed_next_",("illegal transition", "cycle_ms", "phase"),
r"""# Instructions

Construct with a nonempty cycle of unique nonempty phase names. `append(phase,duration)` accepts
positive duration. The first phase may be any cycle member. A later different phase must be the
next phase in the declared cycle; the same phase extends the current run. Invalid input or an
illegal transition rejects without mutation. `cycle_ms` sums durations since the most recent
occurrence of the cycle's first phase, or returns no value if that phase has not occurred.
""",
r"""#pragma once
#include <optional>
#include <string>
#include <vector>
namespace curriculum{struct PhaseRun{std::string phase;long long duration=0;};class SignalPhaseCoalescer{std::vector<std::string> cycle_;std::vector<PhaseRun> runs_;std::size_t allowed_next_(const std::string&)const;public:explicit SignalPhaseCoalescer(std::vector<std::string>);bool append(const std::string&,long long);const std::vector<PhaseRun>&runs()const;std::optional<long long>cycle_ms()const;};}
""",
r"""#include "task.h"
namespace curriculum{SignalPhaseCoalescer::SignalPhaseCoalescer(std::vector<std::string> c):cycle_(std::move(c)){}std::size_t SignalPhaseCoalescer::allowed_next_(const std::string&)const{return 0;}bool SignalPhaseCoalescer::append(const std::string&,long long){return false;}const std::vector<PhaseRun>&SignalPhaseCoalescer::runs()const{return runs_;}std::optional<long long>SignalPhaseCoalescer::cycle_ms()const{return std::nullopt;}}
""",
r"""#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum{SignalPhaseCoalescer::SignalPhaseCoalescer(std::vector<std::string> c):cycle_(std::move(c)){if(cycle_.empty())throw std::invalid_argument("cycle");for(std::size_t i=0;i<cycle_.size();++i)if(cycle_[i].empty()||std::find(cycle_.begin(),cycle_.begin()+static_cast<long>(i),cycle_[i])!=cycle_.begin()+static_cast<long>(i))throw std::invalid_argument("phase");}std::size_t SignalPhaseCoalescer::allowed_next_(const std::string&p)const{auto it=std::find(cycle_.begin(),cycle_.end(),p);return(static_cast<std::size_t>(it-cycle_.begin())+1)%cycle_.size();}bool SignalPhaseCoalescer::append(const std::string&p,long long d){auto it=std::find(cycle_.begin(),cycle_.end(),p);if(d<=0||it==cycle_.end())return false;if(!runs_.empty()&&runs_.back().phase!=p&&cycle_[allowed_next_(runs_.back().phase)]!=p)return false;if(!runs_.empty()&&runs_.back().phase==p)runs_.back().duration+=d;else runs_.push_back({p,d});return true;}const std::vector<PhaseRun>&SignalPhaseCoalescer::runs()const{return runs_;}std::optional<long long>SignalPhaseCoalescer::cycle_ms()const{std::optional<std::size_t> start;for(std::size_t i=0;i<runs_.size();++i)if(runs_[i].phase==cycle_[0])start=i;if(!start)return std::nullopt;long long total=0;for(std::size_t i=*start;i<runs_.size();++i)total+=runs_[i].duration;return total;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;SignalPhaseCoalescer s({"r","g","a"});s.append("r",2);s.append("r",3);s.append("g",4);return s.runs().size()==2&&s.cycle_ms()==std::optional<long long>{9}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;SignalPhaseCoalescer s({"r","g","a"});auto state=[&](const std::vector<PhaseRun>&want,std::optional<long long>cycle){const auto&got=s.runs();if(got.size()!=want.size()||s.cycle_ms()!=cycle)return false;for(std::size_t i=0;i<got.size();++i)if(got[i].phase!=want[i].phase||got[i].duration!=want[i].duration)return false;return true;};
f+=s.append("x",1);f+=!state({},std::nullopt);f+=!s.append("r",1);f+=!state({{"r",1}},1);f+=s.append("a",1);f+=!state({{"r",1}},1);f+=!s.append("r",2);f+=!state({{"r",3}},3);f+=!s.append("g",4);f+=!state({{"r",3},{"g",4}},7);f+=!s.append("a",5);f+=!state({{"r",3},{"g",4},{"a",5}},12);f+=!s.append("r",2);f+=!state({{"r",3},{"g",4},{"a",5},{"r",2}},2);return f;}
"""),
RleCase(
"rle-factory-defects","defect-threshold-index","replace","Defect Threshold Index","online-threshold-crossing-index",
"Index the first contiguous defect interval reaching each requested length.","DefectThresholdIndex::record; first_reaching; run_count","first_by_length_",("remember", "positive", "passing inspection"),
r"""# Instructions

`record(defect)` consumes one inspection. A passing inspection ends the current defect run.
For every newly reached positive length, remember the run's zero-based starting index the first
time that length is reached. `first_reaching(k)` returns that earliest start for a positive `k`,
or no value. `run_count` counts completed or current nonempty defect runs. Queries do not expand
or rescan the event history.
""",
r"""#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum{class DefectThresholdIndex{std::size_t position_=0,current_start_=0,current_length_=0,runs_=0;std::vector<std::optional<std::size_t>>first_by_length_;public:void record(bool);std::optional<std::size_t>first_reaching(std::size_t)const;std::size_t run_count()const;};}
""",
r"""#include "task.h"
namespace curriculum{void DefectThresholdIndex::record(bool){}std::optional<std::size_t>DefectThresholdIndex::first_reaching(std::size_t)const{return std::nullopt;}std::size_t DefectThresholdIndex::run_count()const{return runs_;}}
""",
r"""#include "task.h"
namespace curriculum{void DefectThresholdIndex::record(bool defect){if(defect){if(!current_length_){current_start_=position_;++runs_;}++current_length_;if(first_by_length_.size()<=current_length_)first_by_length_.resize(current_length_+1);if(!first_by_length_[current_length_])first_by_length_[current_length_]=current_start_;}else current_length_=0;++position_;}std::optional<std::size_t>DefectThresholdIndex::first_reaching(std::size_t k)const{if(!k||k>=first_by_length_.size())return std::nullopt;return first_by_length_[k];}std::size_t DefectThresholdIndex::run_count()const{return runs_;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;DefectThresholdIndex x;for(bool v:{true,true,false,true,true,true})x.record(v);return x.first_reaching(2)==std::optional<std::size_t>{0}&&x.first_reaching(3)==std::optional<std::size_t>{3}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;DefectThresholdIndex x;auto state=[&](std::size_t runs,std::optional<std::size_t>one,std::optional<std::size_t>two,std::optional<std::size_t>three){return x.run_count()==runs&&!x.first_reaching(0)&&x.first_reaching(1)==one&&x.first_reaching(2)==two&&x.first_reaching(3)==three;};
f+=!state(0,std::nullopt,std::nullopt,std::nullopt);x.record(false);f+=!state(0,std::nullopt,std::nullopt,std::nullopt);x.record(true);f+=!state(1,1,std::nullopt,std::nullopt);x.record(true);f+=!state(1,1,1,std::nullopt);x.record(false);f+=!state(1,1,1,std::nullopt);x.record(true);f+=!state(2,1,1,std::nullopt);x.record(true);f+=!state(2,1,1,std::nullopt);x.record(true);f+=!state(2,1,1,4);return f;}
"""),
RleCase(
"rle-audio-silence","amplitude-tolerance-runs","replace","Amplitude Tolerance Runs","representative-tolerance-bucketing",
"Build tolerance runs whose representative remains the first sample.","AmplitudeRuns::append; runs; silent_ranges","representative",("representative", "tolerance", "silence limit"),
r"""# Instructions

Construct with nonnegative tolerance and silence limit. `append(sample)` groups with the last run
when `abs(sample - run.representative) <= tolerance`; the representative is always the first
sample and never a rolling average. `silent_ranges` returns `{begin,count}` sample-index ranges
whose representative absolute value is at most the silence limit. Invalid constructor values
throw; all integer-difference calculations must avoid overflow.
""",
r"""#pragma once
#include <cstddef>
#include <vector>
namespace curriculum{struct AmplitudeRun{int representative=0;std::size_t count=0;};struct SampleRange{std::size_t begin=0,count=0;};class AmplitudeRuns{long long tolerance_,silence_;std::vector<AmplitudeRun>runs_;public:AmplitudeRuns(int,int);void append(int);const std::vector<AmplitudeRun>&runs()const;std::vector<SampleRange>silent_ranges()const;};}
""",
r"""#include "task.h"
namespace curriculum{AmplitudeRuns::AmplitudeRuns(int t,int s):tolerance_(t),silence_(s){}void AmplitudeRuns::append(int){}const std::vector<AmplitudeRun>&AmplitudeRuns::runs()const{return runs_;}std::vector<SampleRange>AmplitudeRuns::silent_ranges()const{return{};}}
""",
r"""#include "task.h"
#include <cstdlib>
#include <stdexcept>
namespace curriculum{AmplitudeRuns::AmplitudeRuns(int t,int s):tolerance_(t),silence_(s){if(t<0||s<0)throw std::invalid_argument("limit");}void AmplitudeRuns::append(int v){if(!runs_.empty()&&std::llabs(static_cast<long long>(v)-runs_.back().representative)<=tolerance_)++runs_.back().count;else runs_.push_back({v,1});}const std::vector<AmplitudeRun>&AmplitudeRuns::runs()const{return runs_;}std::vector<SampleRange>AmplitudeRuns::silent_ranges()const{std::vector<SampleRange>out;std::size_t at=0;for(const auto&r:runs_){if(std::llabs(static_cast<long long>(r.representative))<=silence_)out.push_back({at,r.count});at+=r.count;}return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;AmplitudeRuns a(2,3);for(int v:{1,3,4,8})a.append(v);auto s=a.silent_ranges();return a.runs().size()==3&&s.size()==1&&s[0].count==2?0:1;}
""",
r"""#include "task.h"
#include <limits>
int main(){using namespace curriculum;int f=0;AmplitudeRuns a(3,9);auto state=[&](const std::vector<AmplitudeRun>&want,const std::vector<SampleRange>&silent){const auto&got=a.runs();if(got.size()!=want.size())return false;for(std::size_t i=0;i<got.size();++i)if(got[i].representative!=want[i].representative||got[i].count!=want[i].count)return false;auto ranges=a.silent_ranges();if(ranges.size()!=silent.size())return false;for(std::size_t i=0;i<ranges.size();++i)if(ranges[i].begin!=silent[i].begin||ranges[i].count!=silent[i].count)return false;return true;};
f+=!state({},{});a.append(10);f+=!state({{10,1}},{});a.append(13);f+=!state({{10,2}},{});a.append(15);f+=!state({{10,2},{15,1}},{});a.append(8);f+=!state({{10,2},{15,1},{8,1}},{{3,1}});AmplitudeRuns extremes(1,0);extremes.append(std::numeric_limits<int>::min());extremes.append(std::numeric_limits<int>::max());f+=extremes.runs().size()!=2;return f;}
"""),
RleCase(
"rle-weather-stations","station-chunk-carry","replace","Station Chunk Carry","transactional-chunk-carry-state",
"Merge station status chunks through an explicit carry and atomic validation.","StationChunkCarry::accept_chunk; finish; completed; carry","carry_",("atomic", "carry", "finish"),
r"""# Instructions

`accept_chunk` receives a nonempty chunk of nonempty status strings. Invalid chunks reject
atomically. Within and across chunks, equal statuses merge into the carry run; every status
change moves the previous carry to `completed`. `finish` moves the carry once and is idempotent.
After finish, further chunks reject. `completed` never includes a live carry.
""",
r"""#pragma once
#include <cstddef>
#include <optional>
#include <string>
#include <vector>
namespace curriculum{struct StatusRun{std::string status;std::size_t count=0;bool operator==(const StatusRun&o)const{return status==o.status&&count==o.count;}bool operator!=(const StatusRun&o)const{return!(*this==o);}};class StationChunkCarry{std::vector<StatusRun>completed_;std::optional<StatusRun>carry_;bool finished_=false;public:bool accept_chunk(const std::vector<std::string>&);void finish();const std::vector<StatusRun>&completed()const;const std::optional<StatusRun>&carry()const;};}
""",
r"""#include "task.h"
namespace curriculum{bool StationChunkCarry::accept_chunk(const std::vector<std::string>&){return false;}void StationChunkCarry::finish(){}const std::vector<StatusRun>&StationChunkCarry::completed()const{return completed_;}const std::optional<StatusRun>&StationChunkCarry::carry()const{return carry_;}}
""",
r"""#include "task.h"
namespace curriculum{bool StationChunkCarry::accept_chunk(const std::vector<std::string>&chunk){if(finished_||chunk.empty())return false;for(const auto&s:chunk)if(s.empty())return false;auto complete=completed_;auto carry=carry_;for(const auto&s:chunk){if(carry&&carry->status==s)++carry->count;else{if(carry)complete.push_back(*carry);carry=StatusRun{s,1};}}completed_=std::move(complete);carry_=std::move(carry);return true;}void StationChunkCarry::finish(){if(!finished_){if(carry_)completed_.push_back(*carry_);carry_.reset();finished_=true;}}const std::vector<StatusRun>&StationChunkCarry::completed()const{return completed_;}const std::optional<StatusRun>&StationChunkCarry::carry()const{return carry_;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;StationChunkCarry c;c.accept_chunk({"sun","sun"});c.accept_chunk({"sun","rain"});return c.completed()==std::vector<StatusRun>{{"sun",3}}&&c.carry()==StatusRun{"rain",1}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;StationChunkCarry c;auto state=[&](std::vector<StatusRun>done,std::optional<StatusRun>carry){return c.completed()==done&&c.carry()==carry;};
f+=c.accept_chunk({});f+=!state({},std::nullopt);f+=!c.accept_chunk({"a"});f+=!state({},StatusRun{"a",1});f+=c.accept_chunk({"a",""});f+=!state({},StatusRun{"a",1});f+=!c.accept_chunk({"a","b"});f+=!state({{"a",2}},StatusRun{"b",1});f+=!c.accept_chunk({"b","c"});f+=!state({{"a",2},{"b",2}},StatusRun{"c",1});c.finish();f+=!state({{"a",2},{"b",2},{"c",1}},std::nullopt);c.finish();f+=!state({{"a",2},{"b",2},{"c",1}},std::nullopt);f+=c.accept_chunk({"d"});f+=!state({{"a",2},{"b",2},{"c",1}},std::nullopt);return f;}
"""),
RleCase(
"rle-network-flags","flag-record-decoder","replace","Flag Record Decoder","binary-count-record-parser",
"Parse and canonicalize a compact flag/count byte record.","decode_flag_record; encode_flag_record","cursor",("truncation", "triples", "canonical"),
r"""# Instructions

A record is repeated triples `[flags, count_hi, count_lo]`, with a big-endian positive count.
`decode_flag_record` rejects truncation, zero counts, or adjacent entries with the same flags;
it also rejects an expanded total above `max_total`. `encode_flag_record` rejects zero counts,
adjacent duplicates, or counts above 65535 and returns canonical triples. Empty input is valid.
""",
r"""#pragma once
#include <cstddef>
#include <cstdint>
#include <optional>
#include <vector>
namespace curriculum{struct FlagRun{std::uint8_t flags=0;std::uint32_t count=0;bool operator==(const FlagRun&o)const{return flags==o.flags&&count==o.count;}};std::optional<std::vector<FlagRun>>decode_flag_record(const std::vector<std::uint8_t>&,std::size_t);std::optional<std::vector<std::uint8_t>>encode_flag_record(const std::vector<FlagRun>&);}
""",
r"""#include "task.h"
namespace curriculum{std::optional<std::vector<FlagRun>>decode_flag_record(const std::vector<std::uint8_t>&,std::size_t){return std::nullopt;}std::optional<std::vector<std::uint8_t>>encode_flag_record(const std::vector<FlagRun>&){return std::nullopt;}}
""",
r"""#include "task.h"
namespace curriculum{std::optional<std::vector<FlagRun>>decode_flag_record(const std::vector<std::uint8_t>&b,std::size_t max_total){if(b.size()%3)return std::nullopt;std::vector<FlagRun>out;std::size_t total=0;for(std::size_t cursor=0;cursor<b.size();cursor+=3){std::uint32_t count=(static_cast<std::uint32_t>(b[cursor+1])<<8)|b[cursor+2];if(!count||(!out.empty()&&out.back().flags==b[cursor])||count>max_total-total)return std::nullopt;total+=count;out.push_back({b[cursor],count});}return out;}std::optional<std::vector<std::uint8_t>>encode_flag_record(const std::vector<FlagRun>&runs){std::vector<std::uint8_t>out;for(std::size_t i=0;i<runs.size();++i){const auto&r=runs[i];if(!r.count||r.count>65535||(i&&runs[i-1].flags==r.flags))return std::nullopt;out.push_back(r.flags);out.push_back(static_cast<std::uint8_t>(r.count>>8));out.push_back(static_cast<std::uint8_t>(r.count));}return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;std::vector<FlagRun>x{{1,2},{3,258}};auto b=encode_flag_record(x);auto d=b?decode_flag_record(*b,300):std::nullopt;return b&&d&&*d==x?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto bytes=encode_flag_record({{1,1},{2,258}});f+=!bytes||*bytes!=std::vector<std::uint8_t>({1,0,1,2,1,2});f+=!decode_flag_record({1,0,1},9).has_value();f+=decode_flag_record({1,0},9).has_value();f+=decode_flag_record({1,0,0},9).has_value();f+=decode_flag_record({1,0,1,1,0,1},9).has_value();f+=decode_flag_record({1,0,5},4).has_value();f+=encode_flag_record({{1,1},{1,2}}).has_value();return f;}
"""),
RleCase(
"rle-inventory-shelves","shelf-gap-index","replace","Shelf Gap Index","free-interval-split-merge-index",
"Maintain maximal free shelf intervals under occupy and release mutations.","ShelfGapIndex::occupy; release; gaps; first_fit","gaps_",("maximal interval", "first_fit", "release"),
r"""# Instructions

`ShelfGapIndex(size)` starts with one free interval `[0,size)`. `occupy(slot)` removes one free
slot, splitting its maximal interval; occupying an occupied or out-of-range slot returns false.
`release(slot)` merges adjacent free intervals and rejects a slot already free. `first_fit(k)`
returns the smallest start of a gap of at least positive length `k`. `gaps` stays sorted,
disjoint, nonempty, and maximally merged.
""",
r"""#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum{struct Gap{std::size_t begin=0,end=0;bool operator==(const Gap&o)const{return begin==o.begin&&end==o.end;}};class ShelfGapIndex{std::size_t size_;std::vector<Gap>gaps_;public:explicit ShelfGapIndex(std::size_t);bool occupy(std::size_t);bool release(std::size_t);std::optional<std::size_t>first_fit(std::size_t)const;const std::vector<Gap>&gaps()const;};}
""",
r"""#include "task.h"
namespace curriculum{ShelfGapIndex::ShelfGapIndex(std::size_t n):size_(n){}bool ShelfGapIndex::occupy(std::size_t){return false;}bool ShelfGapIndex::release(std::size_t){return false;}std::optional<std::size_t>ShelfGapIndex::first_fit(std::size_t)const{return std::nullopt;}const std::vector<Gap>&ShelfGapIndex::gaps()const{return gaps_;}}
""",
r"""#include "task.h"
#include <stdexcept>
namespace curriculum{ShelfGapIndex::ShelfGapIndex(std::size_t n):size_(n){if(!n)throw std::invalid_argument("size");gaps_.push_back({0,n});}bool ShelfGapIndex::occupy(std::size_t slot){if(slot>=size_)return false;for(std::size_t i=0;i<gaps_.size();++i)if(gaps_[i].begin<=slot&&slot<gaps_[i].end){Gap g=gaps_[i];gaps_.erase(gaps_.begin()+static_cast<long>(i));if(g.begin<slot)gaps_.insert(gaps_.begin()+static_cast<long>(i++),{g.begin,slot});if(slot+1<g.end)gaps_.insert(gaps_.begin()+static_cast<long>(i),{slot+1,g.end});return true;}return false;}bool ShelfGapIndex::release(std::size_t slot){if(slot>=size_)return false;std::size_t pos=0;while(pos<gaps_.size()&&gaps_[pos].end<=slot)++pos;if(pos<gaps_.size()&&gaps_[pos].begin<=slot)return false;std::size_t begin=slot,end=slot+1;if(pos&&gaps_[pos-1].end==slot){begin=gaps_[pos-1].begin;gaps_.erase(gaps_.begin()+static_cast<long>(--pos));}if(pos<gaps_.size()&&gaps_[pos].begin==slot+1){end=gaps_[pos].end;gaps_.erase(gaps_.begin()+static_cast<long>(pos));}gaps_.insert(gaps_.begin()+static_cast<long>(pos),{begin,end});return true;}std::optional<std::size_t>ShelfGapIndex::first_fit(std::size_t k)const{if(!k)return std::nullopt;for(const auto&g:gaps_)if(g.end-g.begin>=k)return g.begin;return std::nullopt;}const std::vector<Gap>&ShelfGapIndex::gaps()const{return gaps_;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;ShelfGapIndex x(6);x.occupy(2);x.occupy(3);return x.gaps()==std::vector<Gap>{{0,2},{4,6}}&&x.first_fit(2)==std::optional<std::size_t>{0}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;ShelfGapIndex x(5);auto state=[&](std::vector<Gap>want,std::optional<std::size_t>fit1,std::optional<std::size_t>fit2){return x.gaps()==want&&x.first_fit(1)==fit1&&x.first_fit(2)==fit2&&!x.first_fit(0);};
f+=!state({{0,5}},0,0);f+=!x.occupy(2);f+=!state({{0,2},{3,5}},0,0);f+=x.occupy(2);f+=!state({{0,2},{3,5}},0,0);f+=!x.occupy(0);f+=!state({{1,2},{3,5}},1,3);f+=!x.release(2);f+=!state({{1,5}},1,1);f+=!x.release(0);f+=!state({{0,5}},0,0);f+=x.release(0);f+=x.occupy(9);f+=!state({{0,5}},0,0);return f;}
"""),
RleCase(
"rle-document-whitespace","protected-whitespace-runs","replace","Protected Whitespace Runs","mode-aware-whitespace-canonicalizer",
"Canonicalize whitespace outside protected regions while preserving protected bytes.","canonicalize_regions","protected_region",("protected", "one space", "newline"),
r"""# Instructions

Each `TextRegion` has bytes and a `protected_region` flag. Protected bytes are copied exactly and
break any outside run. In unprotected regions, spaces and tabs become one space, while any run
containing a newline becomes one newline. Runs may merge across adjacent unprotected regions.
Leading/trailing canonical whitespace is retained. Empty regions are valid. Return both text
and the number of unprotected whitespace runs consumed.
""",
r"""#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum{struct TextRegion{std::string text;bool protected_region=false;};struct CanonicalText{std::string text;std::size_t whitespace_runs=0;};CanonicalText canonicalize_regions(const std::vector<TextRegion>&);}
""",
r"""#include "task.h"
namespace curriculum{CanonicalText canonicalize_regions(const std::vector<TextRegion>&){return{};}}
""",
r"""#include "task.h"
namespace curriculum{CanonicalText canonicalize_regions(const std::vector<TextRegion>&regions){CanonicalText out;bool in_space=false,has_newline=false;auto flush=[&](){if(in_space){out.text.push_back(has_newline?'\n':' ');++out.whitespace_runs;in_space=false;has_newline=false;}};for(const auto&r:regions){if(r.protected_region){flush();out.text+=r.text;continue;}for(char c:r.text){if(c==' '||c=='\t'||c=='\n'||c=='\r'){in_space=true;has_newline=has_newline||c=='\n'||c=='\r';}else{flush();out.text.push_back(c);}}}flush();return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;auto x=canonicalize_regions({{"a \t",false},{" b",false},{"  X\n",true},{"\n\nc",false}});return x.text=="a b  X\n\nc"&&x.whitespace_runs==2?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;auto x=canonicalize_regions({{" \t",false},{"\n",false}});f+=x.text!="\n"||x.whitespace_runs!=1;auto p=canonicalize_regions({{"\t\t",true}});f+=p.text!="\t\t"||p.whitespace_runs;return f;}
"""),
RleCase(
"rle-game-terrain","terrain-row-decoder","replace","Terrain Row Decoder","row-checksummed-run-decoder",
"Decode row-addressed terrain runs with exact width and checksum validation.","decode_terrain_rows","checksum",("checksum", "row index", "expanded width"),
r"""# Instructions

`TerrainRow` records a zero-based row index, positive `{symbol,count}` runs, and a checksum equal
to the sum of unsigned symbol byte times count modulo 65536. `decode_terrain_rows(rows,width)`
requires positive width, row indices exactly `0..n-1`, nonempty symbols, no adjacent equal runs,
exact expanded width, and matching checksums. It returns no value on any error and never accepts
partial rows; empty row input is valid.
""",
r"""#pragma once
#include <cstddef>
#include <cstdint>
#include <optional>
#include <string>
#include <vector>
namespace curriculum{struct TerrainRun{char symbol=' ';std::size_t count=0;};struct TerrainRow{std::size_t row=0;std::vector<TerrainRun>runs;std::uint16_t checksum=0;};std::optional<std::vector<std::string>>decode_terrain_rows(const std::vector<TerrainRow>&,std::size_t);}
""",
r"""#include "task.h"
namespace curriculum{std::optional<std::vector<std::string>>decode_terrain_rows(const std::vector<TerrainRow>&,std::size_t){return std::nullopt;}}
""",
r"""#include "task.h"
namespace curriculum{std::optional<std::vector<std::string>>decode_terrain_rows(const std::vector<TerrainRow>&rows,std::size_t width){if(!width)return std::nullopt;std::vector<std::string>out;for(std::size_t index=0;index<rows.size();++index){const auto&row=rows[index];if(row.row!=index)return std::nullopt;std::string text;unsigned checksum=0;char prior='\0';for(const auto&r:row.runs){if(!r.count||r.symbol=='\0'||r.symbol==prior||r.count>width-text.size())return std::nullopt;text.append(r.count,r.symbol);checksum=(checksum+static_cast<unsigned char>(r.symbol)*r.count)%65536U;prior=r.symbol;}if(text.size()!=width||checksum!=row.checksum)return std::nullopt;out.push_back(std::move(text));}return out;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;TerrainRow r{0,{{'a',2},{'b',1}},static_cast<unsigned short>('a'*2+'b')};auto x=decode_terrain_rows({r},3);return x&&*x==std::vector<std::string>{"aab"}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;TerrainRow good{0,{{'a',2}},static_cast<unsigned short>('a'*2)};f+=!decode_terrain_rows({good},2).has_value();TerrainRow r{1,{{'a',2}},static_cast<unsigned short>('a'*2)};f+=decode_terrain_rows({r},2).has_value();r.row=0;r.runs.push_back({'a',1});f+=decode_terrain_rows({r},3).has_value();r.runs={{'a',2}};r.checksum=0;f+=decode_terrain_rows({r},2).has_value();return f;}
"""),
RleCase(
"rle-medication-adherence","adherence-calendar-streaks","replace","Adherence Calendar Streaks","date-contiguous-missed-streaks",
"Track missed-dose streaks only across consecutive calendar ordinals.","AdherenceCalendar::record; missed_streaks; longest_missed","last_day_",("consecutive days", "duplicate", "missed streak"),
r"""# Instructions

`record(day,taken)` requires strictly increasing nonnegative day ordinals. Duplicate or earlier
days reject without mutation. A missed streak contains consecutive days with `taken=false`;
any taken day or calendar gap ends it. `missed_streaks` includes a current open streak and is
ordered by start. `longest_missed` chooses greatest count, ties by earliest start, or no value.
""",
r"""#pragma once
#include <optional>
#include <vector>
namespace curriculum{struct MissedStreak{int first_day=0,last_day=0,count=0;bool operator==(const MissedStreak&o)const{return first_day==o.first_day&&last_day==o.last_day&&count==o.count;}};class AdherenceCalendar{std::optional<int>last_day_;std::vector<MissedStreak>streaks_;public:bool record(int,bool);const std::vector<MissedStreak>&missed_streaks()const;std::optional<MissedStreak>longest_missed()const;};}
""",
r"""#include "task.h"
namespace curriculum{bool AdherenceCalendar::record(int,bool){return false;}const std::vector<MissedStreak>&AdherenceCalendar::missed_streaks()const{return streaks_;}std::optional<MissedStreak>AdherenceCalendar::longest_missed()const{return std::nullopt;}}
""",
r"""#include "task.h"
namespace curriculum{bool AdherenceCalendar::record(int day,bool taken){if(day<0||(last_day_&&day<=*last_day_))return false;if(!taken){if(last_day_&&day==*last_day_+1&&!streaks_.empty()&&streaks_.back().last_day==*last_day_){streaks_.back().last_day=day;++streaks_.back().count;}else streaks_.push_back({day,day,1});}last_day_=day;return true;}const std::vector<MissedStreak>&AdherenceCalendar::missed_streaks()const{return streaks_;}std::optional<MissedStreak>AdherenceCalendar::longest_missed()const{std::optional<MissedStreak>best;for(const auto&s:streaks_)if(!best||s.count>best->count)best=s;return best;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;AdherenceCalendar c;c.record(3,false);c.record(4,false);c.record(6,false);auto x=c.longest_missed();return x&&x->count==2&&c.missed_streaks().size()==2?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;AdherenceCalendar c;auto state=[&](std::vector<MissedStreak>want,std::optional<MissedStreak>longest){return c.missed_streaks()==want&&c.longest_missed()==longest;};
f+=!state({},std::nullopt);f+=!c.record(1,false);f+=!state({{1,1,1}},MissedStreak{1,1,1});f+=c.record(1,true);f+=!state({{1,1,1}},MissedStreak{1,1,1});f+=!c.record(2,false);f+=!state({{1,2,2}},MissedStreak{1,2,2});f+=!c.record(4,false);f+=!state({{1,2,2},{4,4,1}},MissedStreak{1,2,2});f+=!c.record(5,true);f+=!state({{1,2,2},{4,4,1}},MissedStreak{1,2,2});f+=!c.record(6,false);f+=!state({{1,2,2},{4,4,1},{6,6,1}},MissedStreak{1,2,2});return f;}
"""),
RleCase(
"rle-power-modes","power-energy-runs","replace","Power Energy Runs","mode-duration-energy-ledger",
"Coalesce modes while accumulating overflow-safe duration and energy.","PowerEnergyRuns::append; runs; energy_for","energy_mj",("milliwatts", "energy", "zero-duration"),
r"""# Instructions

`append(mode,duration_ms,milliwatts)` rejects empty modes, negative durations or power, and
overflow without mutation. Zero-duration events are accepted but add no run. Adjacent events
merge only when mode and power both match. A run stores total duration and energy in
millijoules as `duration_ms*milliwatts/1000`, carrying the exact numerator internally so
chunking does not change rounding. `energy_for` sums a mode's final millijoules.
""",
r"""#pragma once
#include <string>
#include <vector>
namespace curriculum{struct PowerRun{std::string mode;long long duration_ms=0,milliwatts=0,energy_mj=0;};class PowerEnergyRuns{struct ExactRun{PowerRun view;long long numerator=0;};std::vector<ExactRun>exact_;mutable std::vector<PowerRun>view_;public:bool append(const std::string&,long long,long long);const std::vector<PowerRun>&runs()const;long long energy_for(const std::string&)const;};}
""",
r"""#include "task.h"
namespace curriculum{bool PowerEnergyRuns::append(const std::string&,long long,long long){return false;}const std::vector<PowerRun>&PowerEnergyRuns::runs()const{return view_;}long long PowerEnergyRuns::energy_for(const std::string&)const{return 0;}}
""",
r"""#include "task.h"
#include <limits>
namespace curriculum{bool PowerEnergyRuns::append(const std::string&m,long long d,long long w){if(m.empty()||d<0||w<0||(d&&(w>std::numeric_limits<long long>::max()/d)))return false;if(!d)return true;long long product=d*w;if(!exact_.empty()&&exact_.back().view.mode==m&&exact_.back().view.milliwatts==w){auto&x=exact_.back();if(x.view.duration_ms>std::numeric_limits<long long>::max()-d||x.numerator>std::numeric_limits<long long>::max()-product)return false;x.view.duration_ms+=d;x.numerator+=product;x.view.energy_mj=x.numerator/1000;}else exact_.push_back({{m,d,w,product/1000},product});return true;}const std::vector<PowerRun>&PowerEnergyRuns::runs()const{view_.clear();for(const auto&x:exact_)view_.push_back(x.view);return view_;}long long PowerEnergyRuns::energy_for(const std::string&m)const{long long total=0;for(const auto&x:exact_)if(x.view.mode==m)total+=x.view.energy_mj;return total;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;PowerEnergyRuns p;p.append("idle",500,3);p.append("idle",500,3);return p.runs().size()==1&&p.runs()[0].energy_mj==3?0:1;}
""",
r"""#include "task.h"
#include <limits>
int main(){using namespace curriculum;int f=0;PowerEnergyRuns p;auto state=[&](const std::vector<PowerRun>&want,long long x_energy,long long y_energy){const auto&got=p.runs();if(got.size()!=want.size()||p.energy_for("x")!=x_energy||p.energy_for("y")!=y_energy)return false;for(std::size_t i=0;i<got.size();++i)if(got[i].mode!=want[i].mode||got[i].duration_ms!=want[i].duration_ms||got[i].milliwatts!=want[i].milliwatts||got[i].energy_mj!=want[i].energy_mj)return false;return true;};
f+=!state({},0,0);f+=!p.append("x",0,9);f+=!state({},0,0);f+=p.append("",1,1);f+=!state({},0,0);f+=!p.append("x",2,1000);f+=!state({{"x",2,1000,2}},2,0);f+=!p.append("x",3,1000);f+=!state({{"x",5,1000,5}},5,0);f+=!p.append("y",4,500);f+=!state({{"x",5,1000,5},{"y",4,500,2}},5,2);f+=p.append("x",std::numeric_limits<long long>::max(),2);f+=!state({{"x",5,1000,5},{"y",4,500,2}},5,2);return f;}
"""),
RleCase(
"rle-chat-reactions","reaction-cluster-editor","replace","Reaction Cluster Editor","run-level-splice-editor",
"Edit an expanded reaction stream through canonical run-level splices.","ReactionClusterEditor::insert; erase; runs; at","canonicalize_",("insert", "erase", "canonical"),
r"""# Instructions

The editor stores canonical nonempty reaction runs. `insert(index,reaction,count)` inserts before
an expanded index in `[0,size]`; reaction and count must be nonempty/positive. `erase(index,count)`
requires the complete expanded range to exist. Both operations are atomic and must split and
then merge neighboring equal runs. `at` is zero-based. Counts and total size must not overflow.
""",
r"""#pragma once
#include <cstddef>
#include <optional>
#include <string>
#include <vector>
namespace curriculum{struct ReactionRun{std::string reaction;std::size_t count=0;bool operator==(const ReactionRun&o)const{return reaction==o.reaction&&count==o.count;}};class ReactionClusterEditor{std::vector<ReactionRun>runs_;std::size_t size_=0;void canonicalize_(std::vector<std::string>);public:bool insert(std::size_t,const std::string&,std::size_t);bool erase(std::size_t,std::size_t);std::optional<std::string>at(std::size_t)const;const std::vector<ReactionRun>&runs()const;std::size_t size()const;};}
""",
r"""#include "task.h"
namespace curriculum{void ReactionClusterEditor::canonicalize_(std::vector<std::string>){}bool ReactionClusterEditor::insert(std::size_t,const std::string&,std::size_t){return false;}bool ReactionClusterEditor::erase(std::size_t,std::size_t){return false;}std::optional<std::string>ReactionClusterEditor::at(std::size_t)const{return std::nullopt;}const std::vector<ReactionRun>&ReactionClusterEditor::runs()const{return runs_;}std::size_t ReactionClusterEditor::size()const{return size_;}}
""",
r"""#include "task.h"
#include <limits>
namespace curriculum{void ReactionClusterEditor::canonicalize_(std::vector<std::string>v){runs_.clear();for(auto&s:v){if(!runs_.empty()&&runs_.back().reaction==s)++runs_.back().count;else runs_.push_back({std::move(s),1});}size_=v.size();}bool ReactionClusterEditor::insert(std::size_t at,const std::string&r,std::size_t count){if(at>size_||r.empty()||!count||count>std::numeric_limits<std::size_t>::max()-size_)return false;std::vector<std::string>v;v.reserve(size_+count);for(const auto&run:runs_)for(std::size_t i=0;i<run.count;++i)v.push_back(run.reaction);v.insert(v.begin()+static_cast<long>(at),count,r);canonicalize_(std::move(v));return true;}bool ReactionClusterEditor::erase(std::size_t at,std::size_t count){if(!count||at>size_||count>size_-at)return false;std::vector<std::string>v;for(const auto&run:runs_)for(std::size_t i=0;i<run.count;++i)v.push_back(run.reaction);v.erase(v.begin()+static_cast<long>(at),v.begin()+static_cast<long>(at+count));canonicalize_(std::move(v));return true;}std::optional<std::string>ReactionClusterEditor::at(std::size_t at)const{if(at>=size_)return std::nullopt;for(const auto&r:runs_)if(at<r.count)return r.reaction;else at-=r.count;return std::nullopt;}const std::vector<ReactionRun>&ReactionClusterEditor::runs()const{return runs_;}std::size_t ReactionClusterEditor::size()const{return size_;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;ReactionClusterEditor e;e.insert(0,"a",2);e.insert(1,"b",1);e.erase(1,1);return e.runs()==std::vector<ReactionRun>{{"a",2}}&&e.size()==2?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;ReactionClusterEditor e;auto state=[&](std::vector<ReactionRun>want,std::vector<std::string>expanded){if(e.runs()!=want||e.size()!=expanded.size())return false;for(std::size_t i=0;i<expanded.size();++i)if(e.at(i)!=std::optional<std::string>{expanded[i]})return false;return !e.at(expanded.size());};
f+=!state({},{});f+=!e.insert(0,"a",2);f+=!state({{"a",2}},{"a","a"});f+=e.erase(1,2);f+=!state({{"a",2}},{"a","a"});f+=!e.insert(1,"b",2);f+=!state({{"a",1},{"b",2},{"a",1}},{"a","b","b","a"});f+=!e.erase(1,2);f+=!state({{"a",2}},{"a","a"});f+=!e.insert(2,"a",1);f+=!state({{"a",3}},{"a","a","a"});f+=e.insert(4,"x",1);f+=!state({{"a",3}},{"a","a","a"});return f;}
"""),
RleCase(
"rle-bus-occupancy","occupancy-plateau-index","replace","Occupancy Plateau Index","timestamped-capacity-plateaus",
"Build occupancy plateaus from timestamped samples and query full-capacity duration.","OccupancyPlateaus::append; close; plateaus; longest_full","open_",("strictly increasing", "close", "capacity"),
r"""# Instructions

Construct with positive capacity. Samples have strictly increasing timestamps and occupancy in
`[0,capacity]`. Each sample starts an open plateau; the next sample closes it at that timestamp,
and equal occupancy merges by extending the same plateau. `close(end)` closes the open plateau
once and forbids later samples. Invalid operations reject atomically. `longest_full` considers
only closed plateaus and ties by earlier start.
""",
r"""#pragma once
#include <optional>
#include <vector>
namespace curriculum{struct Plateau{long long begin=0,end=0;int occupancy=0;};class OccupancyPlateaus{int capacity_;std::vector<Plateau>closed_;std::optional<Plateau>open_;bool finished_=false;public:explicit OccupancyPlateaus(int);bool append(long long,int);bool close(long long);const std::vector<Plateau>&plateaus()const;std::optional<Plateau>longest_full()const;};}
""",
r"""#include "task.h"
namespace curriculum{OccupancyPlateaus::OccupancyPlateaus(int c):capacity_(c){}bool OccupancyPlateaus::append(long long,int){return false;}bool OccupancyPlateaus::close(long long){return false;}const std::vector<Plateau>&OccupancyPlateaus::plateaus()const{return closed_;}std::optional<Plateau>OccupancyPlateaus::longest_full()const{return std::nullopt;}}
""",
r"""#include "task.h"
#include <stdexcept>
namespace curriculum{OccupancyPlateaus::OccupancyPlateaus(int c):capacity_(c){if(c<=0)throw std::invalid_argument("capacity");}bool OccupancyPlateaus::append(long long at,int value){if(finished_||value<0||value>capacity_||(open_&&at<=open_->begin))return false;if(open_){if(open_->occupancy==value)return open_->end=at,true;open_->end=at;closed_.push_back(*open_);}open_=Plateau{at,at,value};return true;}bool OccupancyPlateaus::close(long long end){if(finished_||!open_||end<=open_->begin)return false;open_->end=end;closed_.push_back(*open_);open_.reset();finished_=true;return true;}const std::vector<Plateau>&OccupancyPlateaus::plateaus()const{return closed_;}std::optional<Plateau>OccupancyPlateaus::longest_full()const{std::optional<Plateau>best;for(const auto&p:closed_)if(p.occupancy==capacity_&&(!best||p.end-p.begin>best->end-best->begin))best=p;return best;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;OccupancyPlateaus p(5);p.append(0,5);p.append(3,5);p.append(8,2);p.close(10);auto x=p.longest_full();return x&&x->begin==0&&x->end==8&&p.plateaus().size()==2?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;OccupancyPlateaus p(2);auto state=[&](const std::vector<Plateau>&want,std::optional<Plateau>best){const auto&got=p.plateaus();if(got.size()!=want.size())return false;for(std::size_t i=0;i<got.size();++i)if(got[i].begin!=want[i].begin||got[i].end!=want[i].end||got[i].occupancy!=want[i].occupancy)return false;auto actual=p.longest_full();if(actual.has_value()!=best.has_value())return false;return !actual||(actual->begin==best->begin&&actual->end==best->end&&actual->occupancy==best->occupancy);};
f+=!state({},std::nullopt);f+=!p.append(5,1);f+=!state({},std::nullopt);f+=p.append(5,2);f+=!state({},std::nullopt);f+=!p.append(7,2);f+=!state({{5,7,1}},std::nullopt);f+=!p.append(9,2);f+=!state({{5,7,1}},std::nullopt);f+=!p.append(10,1);f+=!state({{5,7,1},{7,10,2}},Plateau{7,10,2});f+=!p.close(12);f+=!state({{5,7,1},{7,10,2},{10,12,1}},Plateau{7,10,2});f+=p.append(13,1);f+=p.close(14);f+=!state({{5,7,1},{7,10,2},{10,12,1}},Plateau{7,10,2});return f;}
"""),
RleCase(
"rle-barcode-scans","barcode-batch-cursor","replace","Barcode Batch Cursor","stateful-partial-run-decoder",
"Decode bounded pieces of barcode runs while preserving cursor state.","BarcodeBatchCursor::take; remaining; position","run_index_",("partial", "position", "remaining"),
r"""# Instructions

Construct from nonempty barcode strings with positive counts; adjacent equal barcodes are
rejected as noncanonical. `take(limit)` requires positive limit and returns up to that many
expanded scans, advancing through partial runs without materializing the full stream. At end it
returns an empty vector. `remaining` is overflow-checked at construction and decreases exactly;
`position` returns `{run_index,offset_within_run}` and equals `{runs.size(),0}` at end.
""",
r"""#pragma once
#include <cstddef>
#include <string>
#include <utility>
#include <vector>
namespace curriculum{struct BarcodeRun{std::string code;std::size_t count=0;};class BarcodeBatchCursor{std::vector<BarcodeRun>runs_;std::size_t run_index_=0,offset_=0,remaining_=0;public:explicit BarcodeBatchCursor(std::vector<BarcodeRun>);std::vector<std::string>take(std::size_t);std::size_t remaining()const;std::pair<std::size_t,std::size_t>position()const;};}
""",
r"""#include "task.h"
namespace curriculum{BarcodeBatchCursor::BarcodeBatchCursor(std::vector<BarcodeRun>r):runs_(std::move(r)){}std::vector<std::string>BarcodeBatchCursor::take(std::size_t){return{};}std::size_t BarcodeBatchCursor::remaining()const{return remaining_;}std::pair<std::size_t,std::size_t>BarcodeBatchCursor::position()const{return{run_index_,offset_};}}
""",
r"""#include "task.h"
#include <limits>
#include <stdexcept>
namespace curriculum{BarcodeBatchCursor::BarcodeBatchCursor(std::vector<BarcodeRun>r):runs_(std::move(r)){for(std::size_t i=0;i<runs_.size();++i){if(runs_[i].code.empty()||!runs_[i].count||(i&&runs_[i-1].code==runs_[i].code)||runs_[i].count>std::numeric_limits<std::size_t>::max()-remaining_)throw std::invalid_argument("run");remaining_+=runs_[i].count;}}std::vector<std::string>BarcodeBatchCursor::take(std::size_t limit){if(!limit)throw std::invalid_argument("limit");std::vector<std::string>out;while(limit&&run_index_<runs_.size()){std::size_t available=runs_[run_index_].count-offset_;std::size_t n=available<limit?available:limit;out.insert(out.end(),n,runs_[run_index_].code);offset_+=n;remaining_-=n;limit-=n;if(offset_==runs_[run_index_].count){++run_index_;offset_=0;}}return out;}std::size_t BarcodeBatchCursor::remaining()const{return remaining_;}std::pair<std::size_t,std::size_t>BarcodeBatchCursor::position()const{return{run_index_,offset_};}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;BarcodeBatchCursor c({{"a",3},{"b",2}});auto x=c.take(4);return x==std::vector<std::string>{"a","a","a","b"}&&c.position()==std::pair<std::size_t,std::size_t>{1,1}&&c.remaining()==1?0:1;}
""",
r"""#include "task.h"
#include <stdexcept>
int main(){using namespace curriculum;int f=0;try{BarcodeBatchCursor bad({{"a",1},{"a",2}});++f;}catch(const std::invalid_argument&){}BarcodeBatchCursor c({{"x",2},{"y",1}});auto state=[&](std::size_t remaining,std::pair<std::size_t,std::size_t>position){return c.remaining()==remaining&&c.position()==position;};
f+=!state(3,{0,0});f+=c.take(1)!=std::vector<std::string>{"x"};f+=!state(2,{0,1});f+=c.take(2)!=std::vector<std::string>({"x","y"});f+=!state(0,{2,0});f+=!c.take(2).empty();f+=!state(0,{2,0});try{c.take(0);++f;}catch(const std::invalid_argument&){}f+=!state(0,{2,0});return f;}
"""),
RleCase(
"rle-pricing-bands","price-offset-index","replace","Price Offset Index","prefix-end-offset-search",
"Canonicalize price bands and answer offsets by binary search over prefix ends.","PriceOffsetIndex::append; price_at; band_at; total_units","ends_",("prefix ends", "offset", "binary"),
r"""# Instructions

`append(price,units)` accepts nonnegative prices and positive units; invalid or overflowing input
rejects atomically. Adjacent equal prices merge while retaining canonical bands. The index stores
exclusive prefix ends. `price_at(offset)` and `band_at(offset)` are zero-based and use binary
search over prefix ends, returning no value at or beyond total units. `bands` exposes canonical
input order.
""",
r"""#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum{struct PriceBand{long long price=0;std::size_t units=0;bool operator==(const PriceBand&o)const{return price==o.price&&units==o.units;}};class PriceOffsetIndex{std::vector<PriceBand>bands_;std::vector<std::size_t>ends_;public:bool append(long long,std::size_t);std::optional<long long>price_at(std::size_t)const;std::optional<std::size_t>band_at(std::size_t)const;std::size_t total_units()const;const std::vector<PriceBand>&bands()const;};}
""",
r"""#include "task.h"
namespace curriculum{bool PriceOffsetIndex::append(long long,std::size_t){return false;}std::optional<long long>PriceOffsetIndex::price_at(std::size_t)const{return std::nullopt;}std::optional<std::size_t>PriceOffsetIndex::band_at(std::size_t)const{return std::nullopt;}std::size_t PriceOffsetIndex::total_units()const{return 0;}const std::vector<PriceBand>&PriceOffsetIndex::bands()const{return bands_;}}
""",
r"""#include "task.h"
#include <algorithm>
#include <limits>
namespace curriculum{bool PriceOffsetIndex::append(long long price,std::size_t units){std::size_t total=total_units();if(price<0||!units||units>std::numeric_limits<std::size_t>::max()-total)return false;if(!bands_.empty()&&bands_.back().price==price){bands_.back().units+=units;ends_.back()+=units;}else{bands_.push_back({price,units});ends_.push_back(total+units);}return true;}std::optional<std::size_t>PriceOffsetIndex::band_at(std::size_t at)const{auto it=std::upper_bound(ends_.begin(),ends_.end(),at);if(it==ends_.end())return std::nullopt;return static_cast<std::size_t>(it-ends_.begin());}std::optional<long long>PriceOffsetIndex::price_at(std::size_t at)const{auto i=band_at(at);return i?std::optional<long long>{bands_[*i].price}:std::nullopt;}std::size_t PriceOffsetIndex::total_units()const{return ends_.empty()?0:ends_.back();}const std::vector<PriceBand>&PriceOffsetIndex::bands()const{return bands_;}}
""",
r"""#include "task.h"
int main(){using namespace curriculum;PriceOffsetIndex p;p.append(10,2);p.append(10,3);p.append(20,1);return p.bands()==std::vector<PriceBand>{{10,5},{20,1}}&&p.price_at(5)==std::optional<long long>{20}?0:1;}
""",
r"""#include "task.h"
int main(){using namespace curriculum;int f=0;PriceOffsetIndex p;auto state=[&](std::vector<PriceBand>want,const std::vector<long long>&expanded){if(p.bands()!=want||p.total_units()!=expanded.size())return false;for(std::size_t i=0;i<expanded.size();++i)if(p.price_at(i)!=std::optional<long long>{expanded[i]}||!p.band_at(i))return false;return !p.price_at(expanded.size())&&!p.band_at(expanded.size());};
f+=!state({},{});f+=p.append(-1,1);f+=!state({},{});f+=p.append(1,0);f+=!state({},{});f+=!p.append(2,2);f+=!state({{2,2}},{2,2});f+=!p.append(2,1);f+=!state({{2,3}},{2,2,2});f+=!p.append(5,2);f+=!state({{2,3},{5,2}},{2,2,2,5,5});f+=p.band_at(0)!=std::optional<std::size_t>{0};f+=p.band_at(3)!=std::optional<std::size_t>{1};return f;}
"""),
)
