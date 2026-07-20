"""Executable hard-rule fixtures for sliding-window-maximum v2 roots."""

from __future__ import annotations


# Each mutation changes one algorithmic decision in the independently authored
# reference.  The emitted result must compile under the task's ordinary strict
# flags and must be rejected by that task's visible/private tests.
NEGATIVE_MUTATIONS: dict[str, tuple[str, str, str]] = {
    "trade-tick-monotonic-peak": (
        "prices[candidates.back()]<=prices[i]",
        "prices[candidates.back()]<prices[i]",
        "keeps the earliest equal maximum instead of the latest",
    ),
    "thermal-duration-earliest-peak": (
        "readings[q.back()].temperature<reading.temperature",
        "readings[q.back()].temperature<=reading.temperature",
        "keeps the latest equal hottest reading instead of the earliest",
    ),
    "latency-two-stack-max-queue": (
        "std::max(value,incoming_.back().aggregate)",
        "std::min(value,incoming_.back().aggregate)",
        "stores an incoming minimum aggregate instead of a maximum",
    ),
    "cpu-block-prefix-suffix-peaks": (
        "out.push_back(std::max(suffix[i],prefix[i+width-1]))",
        "out.push_back(std::min(suffix[i],prefix[i+width-1]))",
        "combines the two block fragments with minimum",
    ),
    "demand-lazy-heap-window": (
        "next_index_>width_?next_index_-width_:0",
        "next_index_>=width_?next_index_-width_+1:0",
        "expires one accepted interval too early",
    ),
    "heart-rate-frequency-window": (
        "for(int bpm=240;bpm>=0;--bpm)",
        "for(int bpm=0;bpm<=240;++bpm)",
        "returns the lowest present heart rate",
    ),
    "gust-circular-segment-tree": (
        "std::max(range_peak(first,slots_-1),range_peak(0,last))",
        "range_peak(first,slots_-1)",
        "drops the post-wrap segment of a circular query",
    ),
    "bitrate-gap-reset-peaks": (
        "run_start=i+1",
        "run_start=i",
        "counts the missing segment toward the next complete run",
    ),
    "warehouse-sqrt-range-peak": (
        "values_[index]=value;rebuild(index/block_size_);return true;",
        "values_[index]=value;return true;",
        "accepts a correction without rebuilding its block aggregate",
    ),
    "score-sparse-table-queries": (
        "return std::max(levels_[power][first],levels_[power][last-span+1]);",
        "return std::min(levels_[power][first],levels_[power][last-span+1]);",
        "combines overlapping sparse intervals with minimum",
    ),
    "traffic-tournament-ring": (
        "winner_[node]=std::max(winner_[node*2],winner_[node*2+1]);",
        "winner_[node]=std::min(winner_[node*2],winner_[node*2+1]);",
        "propagates losing leaves through the tournament tree",
    ),
    "severity-bitmask-window": (
        "for(int bit=63;bit>=0;--bit)",
        "for(int bit=0;bit<=63;++bit)",
        "returns the lowest present severity code",
    ),
    "vibration-treap-window": (
        "erase(root_,fifo_.front());fifo_.pop_front();",
        "(void)fifo_.front();fifo_.pop_front();",
        "forgets FIFO metadata but leaves the expired key in the treap",
    ),
    "route-next-greater-window": (
        "samples[stack.back()].speed<=samples[i].speed",
        "samples[stack.back()].speed<samples[i].speed",
        "treats an equal value as a strict next-greater jump",
    ),
    "drain-top-two-aggregate-queue": (
        "if(v==first)return;",
        "if(v==first){second=v;return;}",
        "reports the maximum itself as a distinct second value",
    ),
    "auction-avl-bid-window": (
        "erase(root_,fifo_.front());fifo_.pop_front();",
        "(void)fifo_.front();fifo_.pop_front();",
        "leaves an expired bid in the AVL multiset",
    ),
    "support-variable-width-peaks": (
        "while(!candidates.empty()&&candidates.front()<first_day[i])candidates.pop_front();",
        "while(false)candidates.pop_front();",
        "never removes candidates before the supplied left boundary",
    ),
    "defect-grid-window-max": (
        "horizontal[q.back()][c]<=horizontal[r][c]",
        "horizontal[q.back()][c]>=horizontal[r][c]",
        "runs the vertical pass as a minimum deque",
    ),
    "rainfall-generation-time-wheel": (
        "bucket_peak_[slot]=intensity;}else",
        "bucket_peak_[slot]=std::max(bucket_peak_[slot],intensity);}else",
        "allows a stale generation maximum to leak after slot reuse",
    ),
    "delivery-persistent-peak-snapshots": (
        "return query(versions_[last+1],0,size_,first,last+1);",
        "return versions_[last+1]->peak;",
        "returns the historical prefix maximum instead of the requested range",
    ),
}


# These snippets are appended to the private tests.  Every stateful public
# operation is exercised, and every observable value is compared with a small
# independent model after each operation.  Immutable query structures receive
# an exhaustive deterministic query trace as well.
TRACE_SNIPPETS: dict[str, str] = {
    "latency-two-stack-max-queue": r'''
  // hard_rule_trace:latency-two-stack-max-queue
  curriculum::LatencyMaxQueue trace_q; std::vector<int> trace_values;
  const auto trace_check=[&](){require(trace_q.size()==trace_values.size());auto got=trace_q.maximum();if(trace_values.empty()){require(!got);return;}int expected=trace_values[0];for(int value:trace_values)if(value>expected)expected=value;require(got==expected);};
  trace_check();for(int value:{4,1,9,3,9,2}){trace_q.push(value);trace_values.push_back(value);trace_check();}
  for(int step=0;step<7;++step){const bool expected=!trace_values.empty();require(trace_q.pop()==expected);if(expected)trace_values.erase(trace_values.begin());trace_check();}
''',
    "demand-lazy-heap-window": r'''
  // hard_rule_trace:demand-lazy-heap-window
  curriculum::DemandHeapWindow trace_w(3);std::vector<int> trace_values;
  const auto trace_check=[&](){auto got=trace_w.maximum();if(trace_values.empty()){require(!got);return;}int expected=trace_values[0];for(int value:trace_values)if(value>expected)expected=value;require(got==expected);};
  trace_check();for(int value:{8,2,5,1,7,3}){require(trace_w.record(value));trace_values.push_back(value);if(trace_values.size()>3)trace_values.erase(trace_values.begin());trace_check();}require(!trace_w.record(-1));trace_check();
''',
    "heart-rate-frequency-window": r'''
  // hard_rule_trace:heart-rate-frequency-window
  curriculum::HeartRateFrequencyWindow trace_w(4);std::vector<int> trace_values;
  const auto trace_check=[&](){auto got=trace_w.maximum();if(trace_values.empty()){require(!got);return;}int expected=trace_values[0];for(int value:trace_values)if(value>expected)expected=value;require(got==expected);};
  trace_check();for(int value:{0,240,80,240,12,90}){require(trace_w.record(value));trace_values.push_back(value);if(trace_values.size()>4)trace_values.erase(trace_values.begin());trace_check();}require(!trace_w.record(241));trace_check();
''',
    "gust-circular-segment-tree": r'''
  // hard_rule_trace:gust-circular-segment-tree
  curriculum::GustSegmentRing trace_ring(4);std::vector<int> trace_values(4,0);std::vector<bool> trace_set(4,false);
  const auto trace_check=[&](){for(std::size_t first=0;first<4;++first)for(std::size_t last=0;last<4;++last){bool found=false;int expected=0;std::size_t at=first;for(;;){if(trace_set[at]&&(!found||trace_values[at]>expected)){found=true;expected=trace_values[at];}if(at==last)break;at=(at+1)%4;}auto got=trace_ring.peak(first,last);require(found?(got&&*got==expected):!got);}};
  trace_check();for(const auto update:std::vector<std::pair<std::size_t,int>>{{2,4},{0,9},{3,-2},{1,7},{0,1}}){require(trace_ring.update(update.first,update.second));trace_values[update.first]=update.second;trace_set[update.first]=true;trace_check();}require(!trace_ring.update(4,8));trace_check();
''',
    "warehouse-sqrt-range-peak": r'''
  // hard_rule_trace:warehouse-sqrt-range-peak
  std::vector<int> trace_values{4,-1,8,2,7,3};curriculum::ThroughputBlocks trace_blocks(trace_values);
  const auto trace_check=[&](){for(std::size_t left=0;left<trace_values.size();++left)for(std::size_t right=left;right<trace_values.size();++right){int expected=trace_values[left];for(std::size_t i=left;i<=right;++i)if(trace_values[i]>expected)expected=trace_values[i];require(trace_blocks.peak(left,right)==expected);}};
  trace_check();for(const auto correction:std::vector<std::pair<std::size_t,int>>{{2,0},{0,10},{5,12},{3,-9}}){require(trace_blocks.correct(correction.first,correction.second));trace_values[correction.first]=correction.second;trace_check();}require(!trace_blocks.correct(trace_values.size(),4));trace_check();require(!trace_blocks.peak(3,2));
''',
    "score-sparse-table-queries": r'''
  // hard_rule_trace:score-sparse-table-queries
  const std::vector<int> trace_values{4,-1,8,8,2,11,3};curriculum::ScoreSparseTable trace_table(trace_values);
  for(std::size_t left=0;left<trace_values.size();++left)for(std::size_t right=left;right<trace_values.size();++right){int expected=trace_values[left];for(std::size_t i=left;i<=right;++i)if(trace_values[i]>expected)expected=trace_values[i];require(trace_table.maximum(left,right)==expected);}require(!trace_table.maximum(4,3));require(!trace_table.maximum(0,trace_values.size()));
''',
    "traffic-tournament-ring": r'''
  // hard_rule_trace:traffic-tournament-ring
  curriculum::TrafficTournament trace_t(3);std::vector<int> trace_values;
  const auto trace_check=[&](){require(trace_t.size()==trace_values.size());auto got=trace_t.maximum();if(trace_values.empty()){require(!got);return;}int expected=trace_values[0];for(int value:trace_values)if(value>expected)expected=value;require(got==expected);};
  trace_check();for(int value:{5,1,9,2,8,3}){require(trace_t.append(value));if(trace_values.size()==3)trace_values.erase(trace_values.begin());trace_values.push_back(value);trace_check();}require(!trace_t.append(-1));trace_check();
''',
    "severity-bitmask-window": r'''
  // hard_rule_trace:severity-bitmask-window
  curriculum::SeverityMaskWindow trace_w(3);std::vector<unsigned> trace_values;
  const auto trace_check=[&](){auto got=trace_w.maximum();if(trace_values.empty()){require(!got);return;}unsigned expected=trace_values[0];for(unsigned value:trace_values)if(value>expected)expected=value;require(got==expected);};
  trace_check();for(unsigned value:{0U,63U,7U,63U,2U,40U}){require(trace_w.append(value));trace_values.push_back(value);if(trace_values.size()>3)trace_values.erase(trace_values.begin());trace_check();}require(!trace_w.append(64));trace_check();
''',
    "vibration-treap-window": r'''
  // hard_rule_trace:vibration-treap-window
  curriculum::VibrationTreapWindow trace_w(3);std::vector<int> trace_values;
  const auto trace_check=[&](){auto got=trace_w.maximum();if(trace_values.empty()){require(!got);return;}int expected=trace_values[0];for(int value:trace_values)if(value>expected)expected=value;require(got==expected);};
  trace_check();for(int value:{5,1,9,9,2,8,0}){require(trace_w.sample(value));trace_values.push_back(value);if(trace_values.size()>3)trace_values.erase(trace_values.begin());trace_check();}require(!trace_w.sample(-1));trace_check();
''',
    "drain-top-two-aggregate-queue": r'''
  // hard_rule_trace:drain-top-two-aggregate-queue
  curriculum::DrainTopTwoQueue trace_q;std::vector<int> trace_values;
  const auto trace_check=[&](){auto got=trace_q.top_two();if(trace_values.empty()){require(!got);return;}int first=trace_values[0];for(int value:trace_values)if(value>first)first=value;std::optional<int> second;for(int value:trace_values)if(value!=first&&(!second||value>*second))second=value;require(got&&got->first==first&&got->second==second);};
  trace_check();for(int value:{5,5,1,9,7,9}){require(trace_q.push(value));trace_values.push_back(value);trace_check();}require(!trace_q.push(-1));trace_check();for(int step=0;step<7;++step){const bool expected=!trace_values.empty();require(trace_q.expire_oldest()==expected);if(expected)trace_values.erase(trace_values.begin());trace_check();}
''',
    "auction-avl-bid-window": r'''
  // hard_rule_trace:auction-avl-bid-window
  curriculum::AuctionAvlWindow trace_w(4);std::vector<int> trace_values;
  const auto trace_check=[&](){auto got=trace_w.maximum();if(trace_values.empty()){require(!got);return;}int expected=trace_values[0];for(int value:trace_values)if(value>expected)expected=value;require(got==expected);};
  trace_check();for(int value:{5,1,9,9,2,8,0}){require(trace_w.bid(value));trace_values.push_back(value);if(trace_values.size()>4)trace_values.erase(trace_values.begin());trace_check();}require(!trace_w.bid(-1));trace_check();
''',
    "rainfall-generation-time-wheel": r'''
  // hard_rule_trace:rainfall-generation-time-wheel
  curriculum::RainfallWheel trace_w(4);std::vector<std::pair<long long,int>> trace_values;
  const auto trace_check=[&](long long now){for(std::size_t horizon=0;horizon<4;++horizon){bool found=false;int expected=0;for(const auto value:trace_values)if(value.first>=now-static_cast<long long>(horizon)&&value.first<=now&&(!found||value.second>expected)){found=true;expected=value.second;}auto got=trace_w.peak(now,horizon);require(found?(got&&*got==expected):!got);}};
  for(const auto observation:std::vector<std::pair<long long,int>>{{0,8},{0,3},{1,4},{3,9},{4,2},{7,6}}){require(trace_w.observe(observation.first,observation.second));bool merged=false;for(auto& value:trace_values)if(value.first==observation.first){if(observation.second>value.second)value.second=observation.second;merged=true;}if(!merged)trace_values.push_back(observation);trace_check(observation.first);}require(!trace_w.observe(-1,3));trace_check(7);require(!trace_w.peak(7,4));
''',
    "delivery-persistent-peak-snapshots": r'''
  // hard_rule_trace:delivery-persistent-peak-snapshots
  const std::vector<int> trace_values{4,9,-2,7,11,3};curriculum::DeliveryPeakHistory trace_history(trace_values);
  for(std::size_t left=0;left<trace_values.size();++left)for(std::size_t right=left;right<trace_values.size();++right){int expected=trace_values[left];for(std::size_t i=left;i<=right;++i)if(trace_values[i]>expected)expected=trace_values[i];require(trace_history.maximum(left,right)==expected);}require(!trace_history.maximum(3,2));require(!trace_history.maximum(0,trace_values.size()));
''',
}


TRACE_OPERATION_TOKENS: dict[str, tuple[str, ...]] = {
    "latency-two-stack-max-queue": (".push(", ".pop(", ".maximum(", ".size("),
    "demand-lazy-heap-window": (".record(", ".maximum("),
    "heart-rate-frequency-window": (".record(", ".maximum("),
    "gust-circular-segment-tree": (".update(", ".peak("),
    "warehouse-sqrt-range-peak": (".correct(", ".peak("),
    "score-sparse-table-queries": (".maximum(",),
    "traffic-tournament-ring": (".append(", ".maximum(", ".size("),
    "severity-bitmask-window": (".append(", ".maximum("),
    "vibration-treap-window": (".sample(", ".maximum("),
    "drain-top-two-aggregate-queue": (".push(", ".expire_oldest(", ".top_two("),
    "auction-avl-bid-window": (".bid(", ".maximum("),
    "rainfall-generation-time-wheel": (".observe(", ".peak("),
    "delivery-persistent-peak-snapshots": (".maximum(",),
}
