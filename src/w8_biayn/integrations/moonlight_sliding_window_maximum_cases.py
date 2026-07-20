"""Clean-room v2 cases for the sliding-window-maximum remediation family."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SlidingCase:
    legacy_id: str
    task_id: str
    title: str
    profile: str
    objective: str
    public_api: str
    invariant: str
    marker: str
    required_tokens: tuple[str, ...]
    header: str
    starter: str
    reference: str
    visible_test: str
    hidden_test: str

    @property
    def instructions(self) -> str:
        return (
            f"# Instructions\n\n{self.objective}\n\n"
            f"Implement this C++17 API exactly: `{self.public_api}`. "
            f"The required implementation mechanism is {self.invariant}. "
            "Invalid input must follow the documented sentinel or rejection rule without partial mutation. "
            "Returned records use deterministic ordering and the tie rule stated by the API comments.\n"
        )


def _test(body: str) -> str:
    return f"""#include "task.h"
#include <cstdlib>
#include <utility>
#include <vector>
int main() {{
  int failures = 0;
  const auto require = [&](bool ok) {{ if (!ok) ++failures; }};
{body}
  return failures == 0 ? EXIT_SUCCESS : EXIT_FAILURE;
}}
"""


CASES = (
    SlidingCase(
        "swmax-stock-peaks",
        "trade-tick-monotonic-peak",
        "Trade tick monotonic peak",
        "count-monotonic-deque-latest-tie",
        "Emit the price and tick of the latest equal maximum for every complete trade-count window.",
        "std::vector<TradePeak> trade_tick_peaks(const std::vector<int>& prices, std::size_t width)",
        "an index-owning decreasing deque; rescanning or sorting each window is forbidden",
        "candidates.pop_back",
        ("std::deque<std::size_t>", "candidates.pop_front", "candidates.pop_back"),
        """#pragma once
#include <cstddef>
#include <vector>
namespace curriculum {
struct TradePeak { int price; std::size_t tick; };
std::vector<TradePeak> trade_tick_peaks(const std::vector<int>& prices, std::size_t width);
}
""",
        """#include "task.h"
namespace curriculum { std::vector<TradePeak> trade_tick_peaks(const std::vector<int>&, std::size_t) { return {}; } }
""",
        """#include "task.h"
#include <deque>
namespace curriculum {
std::vector<TradePeak> trade_tick_peaks(const std::vector<int>& prices, std::size_t width) {
  if (width == 0 || width > prices.size()) return {};
  std::deque<std::size_t> candidates; std::vector<TradePeak> out;
  for (std::size_t i=0;i<prices.size();++i) {
    while (!candidates.empty() && candidates.front()+width<=i) candidates.pop_front();
    while (!candidates.empty() && prices[candidates.back()]<=prices[i]) candidates.pop_back();
    candidates.push_back(i);
    if (i+1>=width) out.push_back({prices[candidates.front()],candidates.front()});
  }
  return out;
}
}
""",
        _test("""  const auto got=curriculum::trade_tick_peaks({4,2,5,5,1},3);
  require(got.size()==3 && got[0].price==5 && got[0].tick==2);
  require(got[1].tick==3 && got[2].tick==3);"""),
        _test("""  require(curriculum::trade_tick_peaks({1,2},0).empty());
  require(curriculum::trade_tick_peaks({1,2},3).empty());
  const auto got=curriculum::trade_tick_peaks({9,8,7,6},2);
  require(got.size()==3 && got[0].tick==0 && got[2].price==7);"""),
    ),
    SlidingCase(
        "swmax-temperature-alerts",
        "thermal-duration-earliest-peak",
        "Thermal duration earliest peak",
        "timestamp-monotonic-deque-earliest-tie",
        "Report the earliest equal hottest reading after each observation in an inclusive timestamp horizon.",
        "std::vector<ThermalPeak> thermal_duration_peaks(const std::vector<ThermalReading>& readings, long long horizon)",
        "a timestamp-expiring decreasing deque with nondecreasing-time validation",
        "reading.time-horizon",
        ("std::deque<std::size_t>", "reading.time-horizon", "<reading.temperature"),
        """#pragma once
#include <cstddef>
#include <vector>
namespace curriculum {
struct ThermalReading { long long time; int temperature; };
struct ThermalPeak { long long time; int temperature; std::size_t source; };
std::vector<ThermalPeak> thermal_duration_peaks(const std::vector<ThermalReading>& readings, long long horizon);
}
""",
        """#include "task.h"
namespace curriculum { std::vector<ThermalPeak> thermal_duration_peaks(const std::vector<ThermalReading>&, long long) { return {}; } }
""",
        """#include "task.h"
#include <deque>
namespace curriculum {
std::vector<ThermalPeak> thermal_duration_peaks(const std::vector<ThermalReading>& readings, long long horizon) {
  if (horizon<0) return {};
  for (std::size_t i=1;i<readings.size();++i) if (readings[i].time<readings[i-1].time) return {};
  std::deque<std::size_t> q; std::vector<ThermalPeak> out;
  for (std::size_t i=0;i<readings.size();++i) { const auto& reading=readings[i];
    while(!q.empty() && readings[q.front()].time<reading.time-horizon) q.pop_front();
    while(!q.empty() && readings[q.back()].temperature<reading.temperature) q.pop_back();
    q.push_back(i); const auto& peak=readings[q.front()]; out.push_back({peak.time,peak.temperature,q.front()});
  }
  return out;
}
}
""",
        _test("""  using curriculum::ThermalReading;
  const auto got=curriculum::thermal_duration_peaks({{0,8},{2,12},{4,12},{7,9}},3);
  require(got.size()==4 && got[2].source==1 && got[3].source==2);"""),
        _test("""  using curriculum::ThermalReading;
  require(curriculum::thermal_duration_peaks({{3,1},{2,9}},4).empty());
  const auto got=curriculum::thermal_duration_peaks({{1,5},{5,7},{9,6}},0);
  require(got.size()==3 && got[0].temperature==5 && got[2].temperature==6);"""),
    ),
    SlidingCase(
        "swmax-network-latency",
        "latency-two-stack-max-queue",
        "Latency two-stack maximum queue",
        "two-stack-aggregate-queue",
        "Maintain FIFO latency samples with amortized constant-time enqueue, dequeue, and maximum queries.",
        "class LatencyMaxQueue { void push(int); bool pop(); std::optional<int> maximum() const; std::size_t size() const; }",
        "two aggregate stacks; a deque scan or priority queue is forbidden",
        "transfer_if_needed",
        ("struct Entry", "incoming_", "outgoing_", "transfer_if_needed"),
        """#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum {
class LatencyMaxQueue { public: void push(int value); bool pop(); std::optional<int> maximum() const; std::size_t size() const;
 private: struct Entry { int value; int aggregate; }; std::vector<Entry> incoming_, outgoing_; void transfer_if_needed(); };
}
""",
        """#include "task.h"
namespace curriculum { void LatencyMaxQueue::push(int) {} bool LatencyMaxQueue::pop(){return false;} std::optional<int> LatencyMaxQueue::maximum()const{return std::nullopt;} std::size_t LatencyMaxQueue::size()const{return 0;} void LatencyMaxQueue::transfer_if_needed(){} }
""",
        """#include "task.h"
#include <algorithm>
namespace curriculum {
void LatencyMaxQueue::push(int value){ const int peak=incoming_.empty()?value:std::max(value,incoming_.back().aggregate); incoming_.push_back({value,peak}); }
void LatencyMaxQueue::transfer_if_needed(){ if(!outgoing_.empty())return; while(!incoming_.empty()){int value=incoming_.back().value; incoming_.pop_back(); int peak=outgoing_.empty()?value:std::max(value,outgoing_.back().aggregate); outgoing_.push_back({value,peak});}}
bool LatencyMaxQueue::pop(){transfer_if_needed(); if(outgoing_.empty())return false; outgoing_.pop_back(); return true;}
std::optional<int> LatencyMaxQueue::maximum()const{if(incoming_.empty()&&outgoing_.empty())return std::nullopt; if(incoming_.empty())return outgoing_.back().aggregate; if(outgoing_.empty())return incoming_.back().aggregate; return std::max(incoming_.back().aggregate,outgoing_.back().aggregate);}
std::size_t LatencyMaxQueue::size()const{return incoming_.size()+outgoing_.size();}
}
""",
        _test("""  curriculum::LatencyMaxQueue q; q.push(4); q.push(9); q.push(2);
  require(q.maximum()==9 && q.pop() && q.maximum()==9); q.pop(); require(q.maximum()==2);"""),
        _test("""  curriculum::LatencyMaxQueue q; require(!q.pop() && !q.maximum());
  for(int value:{7,1,8,3,6})q.push(value); require(q.size()==5 && q.maximum()==8);
  q.pop();q.pop();q.pop();require(q.maximum()==6);"""),
    ),
    SlidingCase(
        "swmax-cpu-bursts",
        "cpu-block-prefix-suffix-peaks",
        "CPU block prefix/suffix peaks",
        "offline-block-prefix-suffix",
        "Compute all complete fixed-width CPU maxima with the offline prefix/suffix block technique.",
        "std::vector<int> cpu_block_peaks(const std::vector<int>& load, std::size_t width)",
        "block-aligned prefix and suffix maximum arrays; a deque or per-window scan is forbidden",
        "suffix[i]",
        ("prefix", "suffix", "i%width"),
        """#pragma once
#include <cstddef>
#include <vector>
namespace curriculum { std::vector<int> cpu_block_peaks(const std::vector<int>& load, std::size_t width); }
""",
        """#include "task.h"
namespace curriculum { std::vector<int> cpu_block_peaks(const std::vector<int>&,std::size_t){return{};} }
""",
        """#include "task.h"
#include <algorithm>
namespace curriculum {
std::vector<int> cpu_block_peaks(const std::vector<int>& load,std::size_t width){
 if(width==0||width>load.size())return{}; const std::size_t n=load.size(); std::vector<int> prefix(n),suffix(n),out;
 for(std::size_t i=0;i<n;++i)prefix[i]=(i%width==0)?load[i]:std::max(prefix[i-1],load[i]);
 for(std::size_t i=n;i-->0;)suffix[i]=(i==n-1||(i+1)%width==0)?load[i]:std::max(suffix[i+1],load[i]);
 for(std::size_t i=0;i+width<=n;++i)out.push_back(std::max(suffix[i],prefix[i+width-1])); return out;
}
}
""",
        _test("""  const auto got=curriculum::cpu_block_peaks({1,4,2,8,5,3},3);
  require(got==std::vector<int>({4,8,8,8}));"""),
        _test("""  require(curriculum::cpu_block_peaks({1},0).empty());
  require(curriculum::cpu_block_peaks({5,4,3,2},1)==std::vector<int>({5,4,3,2}));"""),
    ),
    SlidingCase(
        "swmax-power-demand",
        "demand-lazy-heap-window",
        "Demand lazy-heap window",
        "lazy-expiry-max-heap",
        "Track maximum demand over the most recent accepted intervals using indexed lazy heap expiry.",
        "class DemandHeapWindow { explicit DemandHeapWindow(std::size_t); bool record(int); std::optional<int> maximum(); }",
        "a max heap of value/index pairs plus FIFO index expiry; a monotonic deque is forbidden",
        "discard_expired",
        ("std::priority_queue", "next_index_", "discard_expired"),
        """#pragma once
#include <cstddef>
#include <optional>
#include <queue>
#include <utility>
namespace curriculum { class DemandHeapWindow { public: explicit DemandHeapWindow(std::size_t width); bool record(int value); std::optional<int> maximum(); private: std::size_t width_,next_index_=0; std::priority_queue<std::pair<int,std::size_t>> heap_; void discard_expired(); }; }
""",
        """#include "task.h"
namespace curriculum { DemandHeapWindow::DemandHeapWindow(std::size_t width):width_(width){} bool DemandHeapWindow::record(int){return false;} std::optional<int> DemandHeapWindow::maximum(){return std::nullopt;} void DemandHeapWindow::discard_expired(){} }
""",
        """#include "task.h"
namespace curriculum {
DemandHeapWindow::DemandHeapWindow(std::size_t width):width_(width){}
bool DemandHeapWindow::record(int value){if(width_==0||value<0)return false;heap_.push({value,next_index_++});discard_expired();return true;}
void DemandHeapWindow::discard_expired(){const std::size_t first=next_index_>width_?next_index_-width_:0;while(!heap_.empty()&&heap_.top().second<first)heap_.pop();}
std::optional<int> DemandHeapWindow::maximum(){discard_expired();if(heap_.empty())return std::nullopt;return heap_.top().first;}
}
""",
        _test(
            """  curriculum::DemandHeapWindow w(3); for(int value:{9,3,7,2})require(w.record(value)); require(w.maximum()==7);"""
        ),
        _test("""  curriculum::DemandHeapWindow z(0);require(!z.record(4)&&!z.maximum());
  curriculum::DemandHeapWindow w(2);require(!w.record(-1));w.record(5);w.record(5);w.record(1);require(w.maximum()==5);"""),
    ),
    SlidingCase(
        "swmax-heart-rate",
        "heart-rate-frequency-window",
        "Heart-rate frequency window",
        "bounded-frequency-buckets",
        "Maintain the maximum accepted heart rate in a count window over the documented 0..240 domain.",
        "class HeartRateFrequencyWindow { explicit HeartRateFrequencyWindow(std::size_t); bool record(int); std::optional<int> maximum() const; }",
        "a FIFO plus fixed 241-entry frequency table; ordered sets, heaps, and deques of candidates are forbidden",
        "frequency_[",
        ("std::array<std::size_t,241>", "frequency_[", "readings_"),
        """#pragma once
#include <array>
#include <cstddef>
#include <deque>
#include <optional>
namespace curriculum { class HeartRateFrequencyWindow { public: explicit HeartRateFrequencyWindow(std::size_t width); bool record(int bpm); std::optional<int> maximum() const; private: std::size_t width_; std::deque<int> readings_; std::array<std::size_t,241> frequency_{}; }; }
""",
        """#include "task.h"
namespace curriculum { HeartRateFrequencyWindow::HeartRateFrequencyWindow(std::size_t width):width_(width){} bool HeartRateFrequencyWindow::record(int){return false;} std::optional<int> HeartRateFrequencyWindow::maximum()const{return std::nullopt;} }
""",
        """#include "task.h"
namespace curriculum {
HeartRateFrequencyWindow::HeartRateFrequencyWindow(std::size_t width):width_(width){}
bool HeartRateFrequencyWindow::record(int bpm){if(width_==0||bpm<0||bpm>240)return false;readings_.push_back(bpm);++frequency_[static_cast<std::size_t>(bpm)];if(readings_.size()>width_){--frequency_[static_cast<std::size_t>(readings_.front())];readings_.pop_front();}return true;}
std::optional<int> HeartRateFrequencyWindow::maximum()const{for(int bpm=240;bpm>=0;--bpm)if(frequency_[static_cast<std::size_t>(bpm)]!=0)return bpm;return std::nullopt;}
}
""",
        _test(
            """  curriculum::HeartRateFrequencyWindow w(3);w.record(80);w.record(120);w.record(90);require(w.maximum()==120);w.record(70);require(w.maximum()==120);w.record(60);require(w.maximum()==90);"""
        ),
        _test(
            """  curriculum::HeartRateFrequencyWindow w(2);require(!w.record(241));require(!w.maximum());w.record(0);w.record(240);require(w.maximum()==240);"""
        ),
    ),
    SlidingCase(
        "swmax-wind-gusts",
        "gust-circular-segment-tree",
        "Gust circular segment tree",
        "circular-point-update-segment-tree",
        "Store a circular set of gust slots and answer inclusive maximum queries that may wrap around slot zero.",
        "class GustSegmentRing { explicit GustSegmentRing(std::size_t); bool update(std::size_t,int); std::optional<int> peak(std::size_t,std::size_t) const; }",
        "an iterative max segment tree over stable circular slots; scanning the arc is forbidden",
        "range_peak",
        ("tree_", "base_", "range_peak"),
        """#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum { class GustSegmentRing { public: explicit GustSegmentRing(std::size_t slots); bool update(std::size_t slot,int value); std::optional<int> peak(std::size_t first,std::size_t last) const; private: std::size_t slots_,base_=1; std::vector<int> tree_; int range_peak(std::size_t left,std::size_t right) const; }; }
""",
        """#include "task.h"
namespace curriculum { GustSegmentRing::GustSegmentRing(std::size_t slots):slots_(slots){} bool GustSegmentRing::update(std::size_t,int){return false;} std::optional<int> GustSegmentRing::peak(std::size_t,std::size_t)const{return std::nullopt;} int GustSegmentRing::range_peak(std::size_t,std::size_t)const{return 0;} }
""",
        """#include "task.h"
#include <algorithm>
#include <limits>
namespace curriculum {
GustSegmentRing::GustSegmentRing(std::size_t slots):slots_(slots){while(base_<slots_)base_*=2;tree_.assign(base_*2,std::numeric_limits<int>::min());}
bool GustSegmentRing::update(std::size_t slot,int value){if(slot>=slots_)return false;std::size_t p=base_+slot;tree_[p]=value;while(p>1){p/=2;tree_[p]=std::max(tree_[p*2],tree_[p*2+1]);}return true;}
int GustSegmentRing::range_peak(std::size_t left,std::size_t right)const{int answer=std::numeric_limits<int>::min();for(left+=base_,right+=base_+1;left<right;left/=2,right/=2){if(left%2)answer=std::max(answer,tree_[left++]);if(right%2)answer=std::max(answer,tree_[--right]);}return answer;}
std::optional<int> GustSegmentRing::peak(std::size_t first,std::size_t last)const{if(slots_==0||first>=slots_||last>=slots_)return std::nullopt;int value=first<=last?range_peak(first,last):std::max(range_peak(first,slots_-1),range_peak(0,last));if(value==std::numeric_limits<int>::min())return std::nullopt;return value;}
}
""",
        _test(
            """  curriculum::GustSegmentRing ring(4);ring.update(0,4);ring.update(1,9);ring.update(3,7);require(ring.peak(3,1)==9);"""
        ),
        _test(
            """  curriculum::GustSegmentRing ring(3);require(!ring.update(3,1)&&!ring.peak(0,2));ring.update(2,-4);require(ring.peak(2,2)==-4);"""
        ),
    ),
    SlidingCase(
        "swmax-video-bitrate",
        "bitrate-gap-reset-peaks",
        "Bitrate gap-reset peaks",
        "optional-gap-reset-monotonic-window",
        "Return a peak only after a complete run of present bitrate segments; a missing segment resets the window.",
        "std::vector<std::optional<int>> bitrate_gap_peaks(const std::vector<std::optional<int>>& segments, std::size_t width)",
        "a run-relative monotonic deque reset on nullopt; carrying candidates across gaps is forbidden",
        "candidates.clear",
        ("std::optional<int>", "candidates.clear", "run_start"),
        """#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum { std::vector<std::optional<int>> bitrate_gap_peaks(const std::vector<std::optional<int>>& segments,std::size_t width); }
""",
        """#include "task.h"
namespace curriculum { std::vector<std::optional<int>> bitrate_gap_peaks(const std::vector<std::optional<int>>&,std::size_t){return{};} }
""",
        """#include "task.h"
#include <deque>
namespace curriculum {
std::vector<std::optional<int>> bitrate_gap_peaks(const std::vector<std::optional<int>>& segments,std::size_t width){std::vector<std::optional<int>> out(segments.size());if(width==0)return out;std::deque<std::size_t> candidates;std::size_t run_start=0;for(std::size_t i=0;i<segments.size();++i){if(!segments[i]){candidates.clear();run_start=i+1;continue;}while(!candidates.empty()&&candidates.front()+width<=i)candidates.pop_front();while(!candidates.empty()&&*segments[candidates.back()]<=*segments[i])candidates.pop_back();candidates.push_back(i);if(i+1-run_start>=width)out[i]=*segments[candidates.front()];}return out;}
}
""",
        _test(
            """  using O=std::optional<int>;const auto got=curriculum::bitrate_gap_peaks({O(4),O(8),O(),O(5),O(3)},2);require(got.size()==5&&got[1]==8&&!got[2]&&!got[3]&&got[4]==5);"""
        ),
        _test(
            """  using O=std::optional<int>;const auto got=curriculum::bitrate_gap_peaks({O(1),O(),O(9)},1);require(got[0]==1&&!got[1]&&got[2]==9);"""
        ),
    ),
    SlidingCase(
        "swmax-warehouse-throughput",
        "warehouse-sqrt-range-peak",
        "Warehouse square-root range peak",
        "mutable-sqrt-decomposition",
        "Maintain interval throughput values under point corrections and answer inclusive range maxima.",
        "class ThroughputBlocks { explicit ThroughputBlocks(std::vector<int>); bool correct(std::size_t,int); std::optional<int> peak(std::size_t,std::size_t) const; }",
        "square-root blocks with per-block maxima; a full range scan is forbidden",
        "block_peak_",
        ("block_size_", "block_peak_", "rebuild"),
        """#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum { class ThroughputBlocks { public: explicit ThroughputBlocks(std::vector<int> values); bool correct(std::size_t index,int value); std::optional<int> peak(std::size_t left,std::size_t right) const; private: std::vector<int> values_,block_peak_; std::size_t block_size_=1; void rebuild(std::size_t block); }; }
""",
        """#include "task.h"
namespace curriculum { ThroughputBlocks::ThroughputBlocks(std::vector<int> values):values_(std::move(values)){} bool ThroughputBlocks::correct(std::size_t,int){return false;} std::optional<int> ThroughputBlocks::peak(std::size_t,std::size_t)const{return std::nullopt;} void ThroughputBlocks::rebuild(std::size_t){} }
""",
        """#include "task.h"
#include <algorithm>
#include <cmath>
#include <limits>
namespace curriculum {
ThroughputBlocks::ThroughputBlocks(std::vector<int> values):values_(std::move(values)){block_size_=values_.empty()?1:static_cast<std::size_t>(std::sqrt(static_cast<double>(values_.size())))+1;block_peak_.assign((values_.size()+block_size_-1)/block_size_,std::numeric_limits<int>::min());for(std::size_t b=0;b<block_peak_.size();++b)rebuild(b);}
void ThroughputBlocks::rebuild(std::size_t block){int value=std::numeric_limits<int>::min();for(std::size_t i=block*block_size_;i<std::min(values_.size(),(block+1)*block_size_);++i)value=std::max(value,values_[i]);block_peak_[block]=value;}
bool ThroughputBlocks::correct(std::size_t index,int value){if(index>=values_.size())return false;values_[index]=value;rebuild(index/block_size_);return true;}
std::optional<int> ThroughputBlocks::peak(std::size_t left,std::size_t right)const{if(left>right||right>=values_.size())return std::nullopt;int answer=std::numeric_limits<int>::min();while(left<=right&&left%block_size_!=0)answer=std::max(answer,values_[left++]);while(left+block_size_-1<=right){answer=std::max(answer,block_peak_[left/block_size_]);left+=block_size_;}while(left<=right)answer=std::max(answer,values_[left++]);return answer;}
}
""",
        _test(
            """  curriculum::ThroughputBlocks b({2,8,3,5,7});require(b.peak(1,4)==8);require(b.correct(1,1)&&b.peak(1,4)==7);"""
        ),
        _test(
            """  curriculum::ThroughputBlocks b({-4,-2,-9});require(b.peak(0,2)==-2);require(!b.correct(3,1)&&!b.peak(2,1));"""
        ),
    ),
    SlidingCase(
        "swmax-game-score-streak",
        "score-sparse-table-queries",
        "Score sparse-table queries",
        "immutable-idempotent-sparse-table",
        "Preprocess immutable turn scores and answer arbitrary inclusive maximum interval queries.",
        "class ScoreSparseTable { explicit ScoreSparseTable(const std::vector<int>&); std::optional<int> maximum(std::size_t,std::size_t) const; }",
        "a logarithm table and overlapping power-of-two sparse maxima; segment trees and scans are forbidden",
        "logs_",
        ("levels_", "logs_", "1U<<power"),
        """#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum { class ScoreSparseTable { public: explicit ScoreSparseTable(const std::vector<int>& scores); std::optional<int> maximum(std::size_t first,std::size_t last) const; private: std::vector<std::size_t> logs_; std::vector<std::vector<int>> levels_; }; }
""",
        """#include "task.h"
namespace curriculum { ScoreSparseTable::ScoreSparseTable(const std::vector<int>&){} std::optional<int> ScoreSparseTable::maximum(std::size_t,std::size_t)const{return std::nullopt;} }
""",
        """#include "task.h"
#include <algorithm>
namespace curriculum {
ScoreSparseTable::ScoreSparseTable(const std::vector<int>& scores){logs_.assign(scores.size()+1,0);for(std::size_t i=2;i<logs_.size();++i)logs_[i]=logs_[i/2]+1;if(scores.empty())return;levels_.push_back(scores);for(std::size_t power=1;(1U<<power)<=scores.size();++power){const std::size_t span=1U<<power,half=span/2;std::vector<int> level(scores.size()-span+1);for(std::size_t i=0;i<level.size();++i)level[i]=std::max(levels_[power-1][i],levels_[power-1][i+half]);levels_.push_back(std::move(level));}}
std::optional<int> ScoreSparseTable::maximum(std::size_t first,std::size_t last)const{if(levels_.empty()||first>last||last>=levels_[0].size())return std::nullopt;const std::size_t length=last-first+1,power=logs_[length],span=1U<<power;return std::max(levels_[power][first],levels_[power][last-span+1]);}
}
""",
        _test(
            """  curriculum::ScoreSparseTable table({3,9,4,8,2});require(table.maximum(0,2)==9&&table.maximum(2,4)==8);"""
        ),
        _test(
            """  curriculum::ScoreSparseTable empty({});require(!empty.maximum(0,0));curriculum::ScoreSparseTable one({-5});require(one.maximum(0,0)==-5&&!one.maximum(1,1));"""
        ),
    ),
    SlidingCase(
        "swmax-web-traffic",
        "traffic-tournament-ring",
        "Traffic tournament ring",
        "overwrite-tournament-tree",
        "Append traffic counts into a fixed circular horizon and report its maximum after overwrites.",
        "class TrafficTournament { explicit TrafficTournament(std::size_t); bool append(int); std::optional<int> maximum() const; std::size_t size() const; }",
        "a complete winner tree whose leaves are overwritten in ring order; heaps and candidate deques are forbidden",
        "winner_",
        ("leaves_", "winner_", "cursor_"),
        """#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum { class TrafficTournament { public: explicit TrafficTournament(std::size_t capacity); bool append(int requests); std::optional<int> maximum() const; std::size_t size() const; private: std::size_t capacity_,leaves_=1,cursor_=0,size_=0; std::vector<int> winner_; }; }
""",
        """#include "task.h"
namespace curriculum { TrafficTournament::TrafficTournament(std::size_t capacity):capacity_(capacity){} bool TrafficTournament::append(int){return false;} std::optional<int> TrafficTournament::maximum()const{return std::nullopt;} std::size_t TrafficTournament::size()const{return 0;} }
""",
        """#include "task.h"
#include <algorithm>
#include <limits>
namespace curriculum {
TrafficTournament::TrafficTournament(std::size_t capacity):capacity_(capacity){while(leaves_<capacity_)leaves_*=2;winner_.assign(leaves_*2,std::numeric_limits<int>::min());}
bool TrafficTournament::append(int requests){if(capacity_==0||requests<0)return false;std::size_t node=leaves_+cursor_;winner_[node]=requests;while(node>1){node/=2;winner_[node]=std::max(winner_[node*2],winner_[node*2+1]);}cursor_=(cursor_+1)%capacity_;if(size_<capacity_)++size_;return true;}
std::optional<int> TrafficTournament::maximum()const{if(size_==0)return std::nullopt;return winner_[1];}
std::size_t TrafficTournament::size()const{return size_;}
}
""",
        _test(
            """  curriculum::TrafficTournament t(3);t.append(4);t.append(9);t.append(2);require(t.maximum()==9);t.append(7);require(t.maximum()==9);t.append(1);require(t.maximum()==7);"""
        ),
        _test(
            """  curriculum::TrafficTournament t(1);require(!t.append(-1)&&!t.maximum());t.append(5);t.append(2);require(t.maximum()==2&&t.size()==1);"""
        ),
    ),
    SlidingCase(
        "swmax-log-severity",
        "severity-bitmask-window",
        "Severity bitmask window",
        "bounded-bitmask-multiplicity",
        "Track the greatest severity code in a count window over the validated 0..63 domain.",
        "class SeverityMaskWindow { explicit SeverityMaskWindow(std::size_t); bool append(unsigned); std::optional<unsigned> maximum() const; }",
        "a 64-bit presence mask plus multiplicity counters and FIFO expiry; ordered containers are forbidden",
        "presence_",
        ("std::array<std::size_t,64>", "presence_", "counts_"),
        """#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <optional>
namespace curriculum { class SeverityMaskWindow { public: explicit SeverityMaskWindow(std::size_t width); bool append(unsigned code); std::optional<unsigned> maximum() const; private: std::size_t width_; std::deque<unsigned> codes_; std::array<std::size_t,64> counts_{}; std::uint64_t presence_=0; }; }
""",
        """#include "task.h"
namespace curriculum { SeverityMaskWindow::SeverityMaskWindow(std::size_t width):width_(width){} bool SeverityMaskWindow::append(unsigned){return false;} std::optional<unsigned> SeverityMaskWindow::maximum()const{return std::nullopt;} }
""",
        """#include "task.h"
namespace curriculum {
SeverityMaskWindow::SeverityMaskWindow(std::size_t width):width_(width){}
bool SeverityMaskWindow::append(unsigned code){if(width_==0||code>=64)return false;codes_.push_back(code);if(++counts_[code]==1)presence_|=(std::uint64_t{1}<<code);if(codes_.size()>width_){unsigned old=codes_.front();codes_.pop_front();if(--counts_[old]==0)presence_&=~(std::uint64_t{1}<<old);}return true;}
std::optional<unsigned> SeverityMaskWindow::maximum()const{if(presence_==0)return std::nullopt;for(int bit=63;bit>=0;--bit)if((presence_&(std::uint64_t{1}<<bit))!=0)return static_cast<unsigned>(bit);return std::nullopt;}
}
""",
        _test(
            """  curriculum::SeverityMaskWindow w(2);w.append(3);w.append(40);require(w.maximum()==40);w.append(2);require(w.maximum()==40);w.append(1);require(w.maximum()==2);"""
        ),
        _test(
            """  curriculum::SeverityMaskWindow w(3);require(!w.append(64)&&!w.maximum());w.append(63);w.append(63);w.append(1);w.append(2);require(w.maximum()==63);"""
        ),
    ),
    SlidingCase(
        "swmax-machine-vibration",
        "vibration-treap-window",
        "Vibration treap window",
        "deterministic-priority-treap-multiset",
        "Maintain a count-window maximum with a repository-owned treap multiset and duplicate counts.",
        "class VibrationTreapWindow { explicit VibrationTreapWindow(std::size_t); bool sample(int); std::optional<int> maximum() const; }",
        "a rotated treap with deterministic key priorities, subtree maxima, duplicate counts, and FIFO expiry",
        "rotate_left",
        ("struct Node", "rotate_left", "erase", "subtree_max"),
        """#pragma once
#include <cstddef>
#include <cstdint>
#include <deque>
#include <memory>
#include <optional>
namespace curriculum { class VibrationTreapWindow { public: explicit VibrationTreapWindow(std::size_t width); bool sample(int value); std::optional<int> maximum() const; private: struct Node { int key,subtree_max; unsigned count; std::uint32_t priority; std::unique_ptr<Node> left,right; explicit Node(int); }; std::size_t width_; std::deque<int> fifo_; std::unique_ptr<Node> root_; static void insert(std::unique_ptr<Node>&,int); static void erase(std::unique_ptr<Node>&,int); static void rotate_left(std::unique_ptr<Node>&); static void rotate_right(std::unique_ptr<Node>&); static void pull(Node*); }; }
""",
        """#include "task.h"
namespace curriculum { VibrationTreapWindow::Node::Node(int value):key(value),subtree_max(value),count(1),priority(0){} VibrationTreapWindow::VibrationTreapWindow(std::size_t width):width_(width){} bool VibrationTreapWindow::sample(int){return false;} std::optional<int> VibrationTreapWindow::maximum()const{return std::nullopt;} void VibrationTreapWindow::insert(std::unique_ptr<Node>&,int){} void VibrationTreapWindow::erase(std::unique_ptr<Node>&,int){} void VibrationTreapWindow::rotate_left(std::unique_ptr<Node>&){} void VibrationTreapWindow::rotate_right(std::unique_ptr<Node>&){} void VibrationTreapWindow::pull(Node*){} }
""",
        """#include "task.h"
#include <algorithm>
namespace curriculum {
VibrationTreapWindow::Node::Node(int value):key(value),subtree_max(value),count(1),priority(static_cast<std::uint32_t>(value)*2654435761U+1013904223U){}
VibrationTreapWindow::VibrationTreapWindow(std::size_t width):width_(width){}
void VibrationTreapWindow::pull(Node* n){if(!n)return;n->subtree_max=n->key;if(n->left)n->subtree_max=std::max(n->subtree_max,n->left->subtree_max);if(n->right)n->subtree_max=std::max(n->subtree_max,n->right->subtree_max);}
void VibrationTreapWindow::rotate_left(std::unique_ptr<Node>& n){auto r=std::move(n->right);n->right=std::move(r->left);pull(n.get());r->left=std::move(n);pull(r.get());n=std::move(r);}
void VibrationTreapWindow::rotate_right(std::unique_ptr<Node>& n){auto l=std::move(n->left);n->left=std::move(l->right);pull(n.get());l->right=std::move(n);pull(l.get());n=std::move(l);}
void VibrationTreapWindow::insert(std::unique_ptr<Node>& n,int value){if(!n){n=std::make_unique<Node>(value);return;}if(value==n->key)++n->count;else if(value<n->key){insert(n->left,value);if(n->left->priority<n->priority)rotate_right(n);}else{insert(n->right,value);if(n->right->priority<n->priority)rotate_left(n);}pull(n.get());}
void VibrationTreapWindow::erase(std::unique_ptr<Node>& n,int value){if(!n)return;if(value<n->key)erase(n->left,value);else if(value>n->key)erase(n->right,value);else if(n->count>1)--n->count;else if(!n->left)n=std::move(n->right);else if(!n->right)n=std::move(n->left);else if(n->left->priority<n->right->priority){rotate_right(n);erase(n->right,value);}else{rotate_left(n);erase(n->left,value);}pull(n.get());}
bool VibrationTreapWindow::sample(int value){if(width_==0||value<0)return false;fifo_.push_back(value);insert(root_,value);if(fifo_.size()>width_){erase(root_,fifo_.front());fifo_.pop_front();}return true;}
std::optional<int> VibrationTreapWindow::maximum()const{if(!root_)return std::nullopt;return root_->subtree_max;}
}
""",
        _test(
            """  curriculum::VibrationTreapWindow w(3);for(int value:{4,9,2,7})w.sample(value);require(w.maximum()==9);w.sample(1);require(w.maximum()==7);"""
        ),
        _test(
            """  curriculum::VibrationTreapWindow w(2);require(!w.sample(-1));w.sample(5);w.sample(5);w.sample(1);require(w.maximum()==5);w.sample(0);require(w.maximum()==1);"""
        ),
    ),
    SlidingCase(
        "swmax-route-speed",
        "route-next-greater-window",
        "Route next-greater window",
        "offline-next-greater-jump",
        "Compute each route-window peak by building a strict next-greater jump chain and advancing its current champion.",
        "std::vector<RoutePeak> route_next_greater_peaks(const std::vector<RouteSample>& samples,std::size_t width)",
        "an offline next-greater index table plus champion jumps; a deque or per-window scan is forbidden",
        "next_greater",
        ("next_greater", "stack", "champion"),
        """#pragma once
#include <cstddef>
#include <vector>
namespace curriculum { struct RouteSample{int speed;};struct RoutePeak{int speed;std::size_t index;}; std::vector<RoutePeak> route_next_greater_peaks(const std::vector<RouteSample>& samples,std::size_t width); }
""",
        """#include "task.h"
namespace curriculum { std::vector<RoutePeak> route_next_greater_peaks(const std::vector<RouteSample>&,std::size_t){return{};} }
""",
        """#include "task.h"
namespace curriculum {
std::vector<RoutePeak> route_next_greater_peaks(const std::vector<RouteSample>& samples,std::size_t width){if(width==0||width>samples.size())return{};const std::size_t n=samples.size();std::vector<std::size_t> next_greater(n,n),stack;for(std::size_t i=n;i-->0;){while(!stack.empty()&&samples[stack.back()].speed<=samples[i].speed)stack.pop_back();if(!stack.empty())next_greater[i]=stack.back();stack.push_back(i);}std::vector<RoutePeak> out;std::size_t champion=0;for(std::size_t left=0;left+width<=n;++left){if(champion<left)champion=left;while(next_greater[champion]<left+width)champion=next_greater[champion];out.push_back({samples[champion].speed,champion});}return out;}
}
""",
        _test(
            """  const auto got=curriculum::route_next_greater_peaks({{2},{7},{3},{8},{1}},3);require(got.size()==3&&got[0].index==1&&got[1].index==3&&got[2].speed==8);"""
        ),
        _test(
            """  const auto got=curriculum::route_next_greater_peaks({{5},{5},{4}},2);require(got.size()==2&&got[0].index==0&&got[1].index==1);require(curriculum::route_next_greater_peaks({{1}},2).empty());"""
        ),
    ),
    SlidingCase(
        "swmax-battery-drain",
        "drain-top-two-aggregate-queue",
        "Drain top-two aggregate queue",
        "two-stack-top-two-monoid",
        "Maintain the greatest and second-greatest distinct drain values while explicitly expiring the oldest sample.",
        "class DrainTopTwoQueue { bool push(int); bool expire_oldest(); std::optional<DrainPair> top_two() const; }",
        "two FIFO stacks whose entries cache a top-two-distinct aggregate monoid",
        "combine",
        ("struct Entry", "DrainPair aggregate", "combine"),
        """#pragma once
#include <optional>
#include <vector>
namespace curriculum { struct DrainPair{int first;std::optional<int> second;}; class DrainTopTwoQueue{public:bool push(int value);bool expire_oldest();std::optional<DrainPair> top_two()const;private:struct Entry{int value;DrainPair aggregate;};std::vector<Entry> in_,out_;static DrainPair combine(const DrainPair&,const DrainPair&);void transfer();}; }
""",
        """#include "task.h"
namespace curriculum { bool DrainTopTwoQueue::push(int){return false;} bool DrainTopTwoQueue::expire_oldest(){return false;} std::optional<DrainPair> DrainTopTwoQueue::top_two()const{return std::nullopt;} DrainPair DrainTopTwoQueue::combine(const DrainPair&a,const DrainPair&){return a;} void DrainTopTwoQueue::transfer(){} }
""",
        """#include "task.h"
#include <algorithm>
namespace curriculum {
DrainPair DrainTopTwoQueue::combine(const DrainPair&a,const DrainPair&b){int first=std::max(a.first,b.first);std::optional<int> second;const auto take=[&](int v){if(v==first)return;if(!second||v>*second)second=v;};take(a.first);if(a.second)take(*a.second);take(b.first);if(b.second)take(*b.second);return{first,second};}
bool DrainTopTwoQueue::push(int value){if(value<0)return false;DrainPair one{value,std::nullopt};DrainPair aggregate=in_.empty()?one:combine(in_.back().aggregate,one);in_.push_back({value,aggregate});return true;}
void DrainTopTwoQueue::transfer(){if(!out_.empty())return;while(!in_.empty()){int value=in_.back().value;in_.pop_back();DrainPair one{value,std::nullopt};DrainPair aggregate=out_.empty()?one:combine(out_.back().aggregate,one);out_.push_back({value,aggregate});}}
bool DrainTopTwoQueue::expire_oldest(){transfer();if(out_.empty())return false;out_.pop_back();return true;}
std::optional<DrainPair> DrainTopTwoQueue::top_two()const{if(in_.empty()&&out_.empty())return std::nullopt;if(in_.empty())return out_.back().aggregate;if(out_.empty())return in_.back().aggregate;return combine(in_.back().aggregate,out_.back().aggregate);}
}
""",
        _test(
            """  curriculum::DrainTopTwoQueue q;for(int v:{5,2,5,4})q.push(v);auto p=q.top_two();require(p&&p->first==5&&p->second==4);q.expire_oldest();q.expire_oldest();p=q.top_two();require(p&&p->first==5&&p->second==4);"""
        ),
        _test(
            """  curriculum::DrainTopTwoQueue q;require(!q.push(-1)&&!q.expire_oldest());q.push(3);q.push(3);auto p=q.top_two();require(p&&p->first==3&&!p->second);"""
        ),
    ),
    SlidingCase(
        "swmax-auction-bids",
        "auction-avl-bid-window",
        "Auction AVL bid window",
        "owned-avl-multiset-window",
        "Keep a count-window of bids in an owned AVL multiset and report the greatest active bid.",
        "class AuctionAvlWindow { explicit AuctionAvlWindow(std::size_t); bool bid(int); std::optional<int> maximum() const; }",
        "an owned height-balanced node tree with duplicate counts, rotations, and FIFO expiry; std::map/set are forbidden",
        "rebalance",
        ("struct Node", "height", "rotate_left", "rebalance"),
        """#pragma once
#include <cstddef>
#include <deque>
#include <memory>
#include <optional>
namespace curriculum { class AuctionAvlWindow{public:explicit AuctionAvlWindow(std::size_t width);bool bid(int value);std::optional<int> maximum()const;private:struct Node{int key,height=1;unsigned count=1;std::unique_ptr<Node>left,right;explicit Node(int);};std::size_t width_;std::deque<int>fifo_;std::unique_ptr<Node>root_;static int height(const std::unique_ptr<Node>&);static void pull(Node*);static void rotate_left(std::unique_ptr<Node>&);static void rotate_right(std::unique_ptr<Node>&);static void rebalance(std::unique_ptr<Node>&);static void insert(std::unique_ptr<Node>&,int);static void erase(std::unique_ptr<Node>&,int);}; }
""",
        """#include "task.h"
namespace curriculum { AuctionAvlWindow::Node::Node(int value):key(value){} AuctionAvlWindow::AuctionAvlWindow(std::size_t width):width_(width){} bool AuctionAvlWindow::bid(int){return false;} std::optional<int>AuctionAvlWindow::maximum()const{return std::nullopt;} int AuctionAvlWindow::height(const std::unique_ptr<Node>&){return 0;} void AuctionAvlWindow::pull(Node*){} void AuctionAvlWindow::rotate_left(std::unique_ptr<Node>&){} void AuctionAvlWindow::rotate_right(std::unique_ptr<Node>&){} void AuctionAvlWindow::rebalance(std::unique_ptr<Node>&){} void AuctionAvlWindow::insert(std::unique_ptr<Node>&,int){} void AuctionAvlWindow::erase(std::unique_ptr<Node>&,int){} }
""",
        """#include "task.h"
#include <algorithm>
namespace curriculum {
AuctionAvlWindow::Node::Node(int value):key(value){}AuctionAvlWindow::AuctionAvlWindow(std::size_t width):width_(width){}
int AuctionAvlWindow::height(const std::unique_ptr<Node>&n){return n?n->height:0;}void AuctionAvlWindow::pull(Node*n){if(n)n->height=1+std::max(height(n->left),height(n->right));}
void AuctionAvlWindow::rotate_left(std::unique_ptr<Node>&n){auto r=std::move(n->right);n->right=std::move(r->left);pull(n.get());r->left=std::move(n);pull(r.get());n=std::move(r);}void AuctionAvlWindow::rotate_right(std::unique_ptr<Node>&n){auto l=std::move(n->left);n->left=std::move(l->right);pull(n.get());l->right=std::move(n);pull(l.get());n=std::move(l);}
void AuctionAvlWindow::rebalance(std::unique_ptr<Node>&n){if(!n)return;pull(n.get());int balance=height(n->left)-height(n->right);if(balance>1){if(height(n->left->left)<height(n->left->right))rotate_left(n->left);rotate_right(n);}else if(balance<-1){if(height(n->right->right)<height(n->right->left))rotate_right(n->right);rotate_left(n);}}
void AuctionAvlWindow::insert(std::unique_ptr<Node>&n,int v){if(!n){n=std::make_unique<Node>(v);return;}if(v==n->key)++n->count;else if(v<n->key)insert(n->left,v);else insert(n->right,v);rebalance(n);}
void AuctionAvlWindow::erase(std::unique_ptr<Node>&n,int v){if(!n)return;if(v<n->key)erase(n->left,v);else if(v>n->key)erase(n->right,v);else if(n->count>1)--n->count;else if(!n->left)n=std::move(n->right);else if(!n->right)n=std::move(n->left);else{Node*s=n->right.get();while(s->left)s=s->left.get();n->key=s->key;n->count=1;erase(n->right,s->key);}rebalance(n);}
bool AuctionAvlWindow::bid(int value){if(width_==0||value<0)return false;fifo_.push_back(value);insert(root_,value);if(fifo_.size()>width_){erase(root_,fifo_.front());fifo_.pop_front();}return true;}
std::optional<int>AuctionAvlWindow::maximum()const{const Node*n=root_.get();if(!n)return std::nullopt;while(n->right)n=n->right.get();return n->key;}
}
""",
        _test(
            """  curriculum::AuctionAvlWindow w(3);for(int v:{5,9,2,7})w.bid(v);require(w.maximum()==9);w.bid(1);require(w.maximum()==7);"""
        ),
        _test(
            """  curriculum::AuctionAvlWindow w(2);w.bid(4);w.bid(4);w.bid(1);require(w.maximum()==4);w.bid(0);require(w.maximum()==1);"""
        ),
    ),
    SlidingCase(
        "swmax-support-load",
        "support-variable-width-peaks",
        "Support variable-width peaks",
        "variable-left-boundary-monotonic-deque",
        "Report a maximum for each day whose supplied left boundary is monotone and never exceeds that day.",
        "std::vector<int> support_variable_peaks(const std::vector<int>& load,const std::vector<std::size_t>& first_day)",
        "a monotonic deque driven by externally supplied monotone left boundaries; invalid boundary schedules reject the batch",
        "first_day[i]",
        ("first_day[i]", "first_day[i-1]", "candidates.front()<first_day"),
        """#pragma once
#include <cstddef>
#include <vector>
namespace curriculum { std::vector<int> support_variable_peaks(const std::vector<int>& load,const std::vector<std::size_t>& first_day); }
""",
        """#include "task.h"
namespace curriculum { std::vector<int> support_variable_peaks(const std::vector<int>&,const std::vector<std::size_t>&){return{};} }
""",
        """#include "task.h"
#include <deque>
namespace curriculum { std::vector<int> support_variable_peaks(const std::vector<int>&load,const std::vector<std::size_t>&first_day){if(load.size()!=first_day.size())return{};std::deque<std::size_t>candidates;std::vector<int>out;for(std::size_t i=0;i<load.size();++i){if(first_day[i]>i||(i>0&&first_day[i]<first_day[i-1]))return{};while(!candidates.empty()&&candidates.front()<first_day[i])candidates.pop_front();while(!candidates.empty()&&load[candidates.back()]<=load[i])candidates.pop_back();candidates.push_back(i);out.push_back(load[candidates.front()]);}return out;} }
""",
        _test(
            """  const auto got=curriculum::support_variable_peaks({2,7,4,9},{0,0,1,2});require(got==std::vector<int>({2,7,7,9}));"""
        ),
        _test(
            """  require(curriculum::support_variable_peaks({1,2},{0}).empty());require(curriculum::support_variable_peaks({1,2,3},{0,1,0}).empty());require(curriculum::support_variable_peaks({9,1,2},{0,1,1})==std::vector<int>({9,1,2}));"""
        ),
    ),
    SlidingCase(
        "swmax-production-defects",
        "defect-grid-window-max",
        "Defect grid window maximum",
        "separable-two-dimensional-deques",
        "Compute every rectangular defect-grid maximum with horizontal then vertical monotonic passes.",
        "std::vector<std::vector<int>> defect_grid_peaks(const std::vector<std::vector<int>>&,std::size_t,std::size_t)",
        "two separable monotonic-deque passes; flattening or rescanning each rectangle is forbidden",
        "horizontal",
        ("horizontal", "row_window", "column_window"),
        """#pragma once
#include <cstddef>
#include <vector>
namespace curriculum { std::vector<std::vector<int>> defect_grid_peaks(const std::vector<std::vector<int>>&grid,std::size_t row_window,std::size_t column_window); }
""",
        """#include "task.h"
namespace curriculum { std::vector<std::vector<int>> defect_grid_peaks(const std::vector<std::vector<int>>&,std::size_t,std::size_t){return{};} }
""",
        """#include "task.h"
#include <deque>
namespace curriculum { std::vector<std::vector<int>> defect_grid_peaks(const std::vector<std::vector<int>>&grid,std::size_t row_window,std::size_t column_window){if(grid.empty()||grid[0].empty()||row_window==0||column_window==0||row_window>grid.size()||column_window>grid[0].size())return{};for(const auto&row:grid)if(row.size()!=grid[0].size())return{};std::vector<std::vector<int>>horizontal(grid.size(),std::vector<int>(grid[0].size()-column_window+1));for(std::size_t r=0;r<grid.size();++r){std::deque<std::size_t>q;for(std::size_t c=0;c<grid[r].size();++c){while(!q.empty()&&q.front()+column_window<=c)q.pop_front();while(!q.empty()&&grid[r][q.back()]<=grid[r][c])q.pop_back();q.push_back(c);if(c+1>=column_window)horizontal[r][c+1-column_window]=grid[r][q.front()];}}std::vector<std::vector<int>>out(grid.size()-row_window+1,std::vector<int>(horizontal[0].size()));for(std::size_t c=0;c<horizontal[0].size();++c){std::deque<std::size_t>q;for(std::size_t r=0;r<horizontal.size();++r){while(!q.empty()&&q.front()+row_window<=r)q.pop_front();while(!q.empty()&&horizontal[q.back()][c]<=horizontal[r][c])q.pop_back();q.push_back(r);if(r+1>=row_window)out[r+1-row_window][c]=horizontal[q.front()][c];}}return out;} }
""",
        _test(
            """  const auto got=curriculum::defect_grid_peaks({{1,5,2},{7,3,4},{0,6,8}},2,2);require(got==std::vector<std::vector<int>>({{7,5},{7,8}}));"""
        ),
        _test(
            """  require(curriculum::defect_grid_peaks({{1},{2,3}},1,1).empty());require(curriculum::defect_grid_peaks({{1}},0,1).empty());"""
        ),
    ),
    SlidingCase(
        "swmax-rainfall",
        "rainfall-generation-time-wheel",
        "Rainfall generation time wheel",
        "generation-stamped-time-wheel",
        "Store per-epoch rainfall maxima in a finite time wheel and query an inclusive recent epoch horizon.",
        "class RainfallWheel { explicit RainfallWheel(std::size_t); bool observe(long long,int); std::optional<int> peak(long long,std::size_t) const; }",
        "generation-stamped modulo buckets that reset on epoch reuse; stale generations must never leak",
        "generation_",
        ("generation_", "%buckets_", "bucket_peak_"),
        """#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum { class RainfallWheel{public:explicit RainfallWheel(std::size_t buckets);bool observe(long long epoch,int intensity);std::optional<int> peak(long long now,std::size_t horizon)const;private:std::size_t buckets_;std::vector<long long>generation_;std::vector<int>bucket_peak_;}; }
""",
        """#include "task.h"
namespace curriculum { RainfallWheel::RainfallWheel(std::size_t buckets):buckets_(buckets){} bool RainfallWheel::observe(long long,int){return false;} std::optional<int>RainfallWheel::peak(long long,std::size_t)const{return std::nullopt;} }
""",
        """#include "task.h"
#include <algorithm>
#include <limits>
namespace curriculum { RainfallWheel::RainfallWheel(std::size_t buckets):buckets_(buckets),generation_(buckets,-1),bucket_peak_(buckets,std::numeric_limits<int>::min()){}bool RainfallWheel::observe(long long epoch,int intensity){if(buckets_==0||epoch<0||intensity<0)return false;std::size_t slot=static_cast<std::size_t>(epoch)%buckets_;if(generation_[slot]!=epoch){generation_[slot]=epoch;bucket_peak_[slot]=intensity;}else bucket_peak_[slot]=std::max(bucket_peak_[slot],intensity);return true;}std::optional<int>RainfallWheel::peak(long long now,std::size_t horizon)const{if(buckets_==0||now<0||horizon>=buckets_)return std::nullopt;int answer=std::numeric_limits<int>::min();long long first=now-static_cast<long long>(horizon);for(long long epoch=std::max(0LL,first);epoch<=now;++epoch){std::size_t slot=static_cast<std::size_t>(epoch)%buckets_;if(generation_[slot]==epoch)answer=std::max(answer,bucket_peak_[slot]);}if(answer==std::numeric_limits<int>::min())return std::nullopt;return answer;} }
""",
        _test(
            """  curriculum::RainfallWheel w(5);w.observe(1,4);w.observe(2,9);w.observe(2,7);require(w.peak(3,2)==9);"""
        ),
        _test(
            """  curriculum::RainfallWheel w(3);w.observe(0,8);w.observe(3,2);require(w.peak(3,2)==2);require(!w.peak(3,3)&&!w.observe(-1,4));"""
        ),
    ),
    SlidingCase(
        "swmax-delivery-delay",
        "delivery-persistent-peak-snapshots",
        "Delivery persistent peak snapshots",
        "persistent-segment-tree-prefixes",
        "Build immutable delivery-delay prefixes and query maxima over any historical contiguous window.",
        "class DeliveryPeakHistory { explicit DeliveryPeakHistory(const std::vector<int>&); std::optional<int> maximum(std::size_t,std::size_t) const; }",
        "a persistent point-update segment tree with one root per prefix; mutable range structures and scans are forbidden",
        "versions_",
        ("struct Node", "versions_", "update", "query"),
        """#pragma once
#include <cstddef>
#include <memory>
#include <optional>
#include <vector>
namespace curriculum { class DeliveryPeakHistory{public:explicit DeliveryPeakHistory(const std::vector<int>&delays);std::optional<int>maximum(std::size_t first,std::size_t last)const;private:struct Node{int peak;std::shared_ptr<Node>left,right;};std::size_t size_=0;std::vector<std::shared_ptr<Node>>versions_;static std::shared_ptr<Node>update(const std::shared_ptr<Node>&,std::size_t,std::size_t,std::size_t,int);static int query(const std::shared_ptr<Node>&,std::size_t,std::size_t,std::size_t,std::size_t);}; }
""",
        """#include "task.h"
namespace curriculum { DeliveryPeakHistory::DeliveryPeakHistory(const std::vector<int>&){} std::optional<int>DeliveryPeakHistory::maximum(std::size_t,std::size_t)const{return std::nullopt;} std::shared_ptr<DeliveryPeakHistory::Node>DeliveryPeakHistory::update(const std::shared_ptr<Node>&n,std::size_t,std::size_t,std::size_t,int){return n;} int DeliveryPeakHistory::query(const std::shared_ptr<Node>&,std::size_t,std::size_t,std::size_t,std::size_t){return 0;} }
""",
        """#include "task.h"
#include <algorithm>
#include <limits>
namespace curriculum { std::shared_ptr<DeliveryPeakHistory::Node>DeliveryPeakHistory::update(const std::shared_ptr<Node>&node,std::size_t left,std::size_t right,std::size_t index,int value){auto copy=node?std::make_shared<Node>(*node):std::make_shared<Node>(Node{std::numeric_limits<int>::min(),nullptr,nullptr});if(right-left==1){copy->peak=value;return copy;}std::size_t middle=(left+right)/2;if(index<middle)copy->left=update(copy->left,left,middle,index,value);else copy->right=update(copy->right,middle,right,index,value);int a=copy->left?copy->left->peak:std::numeric_limits<int>::min(),b=copy->right?copy->right->peak:std::numeric_limits<int>::min();copy->peak=std::max(a,b);return copy;}int DeliveryPeakHistory::query(const std::shared_ptr<Node>&node,std::size_t left,std::size_t right,std::size_t ql,std::size_t qr){if(!node||qr<=left||right<=ql)return std::numeric_limits<int>::min();if(ql<=left&&right<=qr)return node->peak;std::size_t middle=(left+right)/2;return std::max(query(node->left,left,middle,ql,qr),query(node->right,middle,right,ql,qr));}DeliveryPeakHistory::DeliveryPeakHistory(const std::vector<int>&delays):size_(delays.size()){std::size_t base=1;while(base<size_)base*=2;size_=base;versions_.push_back(nullptr);for(std::size_t i=0;i<delays.size();++i)versions_.push_back(update(versions_.back(),0,size_,i,delays[i]));}std::optional<int>DeliveryPeakHistory::maximum(std::size_t first,std::size_t last)const{if(versions_.size()<=1||first>last||last+1>=versions_.size())return std::nullopt;return query(versions_[last+1],0,size_,first,last+1);} }
""",
        _test(
            """  curriculum::DeliveryPeakHistory h({4,9,2,7});require(h.maximum(0,2)==9&&h.maximum(2,3)==7);"""
        ),
        _test(
            """  curriculum::DeliveryPeakHistory h({-5,-2});require(h.maximum(0,1)==-2&&!h.maximum(1,0)&&!h.maximum(0,2));"""
        ),
    ),
)
