"""Materialize clean-room cyclic-slot-system Aider C++ tasks.

These tasks deliberately avoid FIFO buffer, full-write, and forced-overwrite
semantics so they are not circular-buffer holdout variants.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import (
    WholeFormatError,
    build_prompt,
    load_task,
    parse_whole_file_blocks,
)
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)


DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-dsa/circular-buffer")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks/aider-dsa/circular-buffer")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_CYCLIC_SLOT_SYSTEMS_CURRICULUM.md"
PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY_ID = "aider-dsa/cyclic-slot-systems-v2"
GENERATOR_PATH = "src/w8_biayn/integrations/moonlight_cyclic_slot_systems_aider_tasks.py"
MIN_ROOTS = 15
MAX_ROOTS = 20
BENCHMARK_MANIFEST = Path("manifests/aider_sft/aider-polyglot-cpp-26.json")
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
NORMALIZER = "cyclic-slot-semantic-v4-artifact-derived"
DIAGNOSTIC_IMAGE = "w8-biayn-circular-buffer-verify:ephemeral"
DIAGNOSTIC_IMAGE_ID = "sha256:5f16a282d1fd83be028185f8e03319bf4d6b84cf4fad62f931b21cc5f21b7208"
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
SANITY_IMAGE_ID = "sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
REMEDY_HEADINGS = (
    "Identity",
    "Objective",
    "Public API",
    "Behavior table",
    "Implementation invariant",
    "Starter and reference",
    "Tests",
    "Files and metadata",
    "Build/oracle",
    "Family/contamination",
    "Optional dataset handoff",
    "Acceptance",
)
LEGACY_TASK_IDS = frozenset(
    {
        "ring-audio-frame-store", "ring-build-events", "ring-bus-messages",
        "ring-camera-preview", "ring-currency-quotes", "ring-customer-arrivals",
        "ring-delivery-scans", "ring-game-replay", "ring-gps-trail",
        "ring-keyboard-input", "ring-log-tail", "ring-machine-alerts",
        "ring-medication-reminders", "ring-network-packets", "ring-print-spool",
        "ring-stock-ticks", "ring-telemetry-history", "ring-ui-event-queue",
        "ring-weather-readings", "ring-workout-laps",
    }
)


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    kind: str
    title: str
    contract: str
    seed: str
    mechanism: tuple[str, ...]
    prompt_terms: tuple[str, ...]
    forbidden: tuple[str, ...]


TASKS = (
    TaskSpec(
        "parking-permit-slot-allocator",
        "PermitSlotAllocator",
        "allocator",
        "Parking permit slots",
        "Allocate and release numbered permits by circular first-fit search.",
        "0xA110CA7E",
        ("used_", "cursor_", "%used_.size()", "for(std::size_t offset", "occupied_slots"),
        ("scans from the current cursor", "reserve", "release", "zero capacity", "occupied_slots"),
        ("monotone_allocator", "std::deque"),
    ),
    TaskSpec(
        "maintenance-duty-wheel",
        "MaintenanceDutyWheel",
        "wheel",
        "Maintenance duty wheel",
        "Schedule named maintenance work at future wheel ticks and advance deterministic due work.",
        "0x71A1E001",
        ("wheel_", "now_", "%wheel_.size()", "for(std::size_t step", "scheduled"),
        ("delay must be in 1 through", "globally unique", "lexicographic order", "scheduled", "ticks remaining"),
        ("fifo_delay_queue", "immediate_sorted_dispatch"),
    ),
    TaskSpec(
        "api-sampling-window-counter",
        "SamplingWindowCounter",
        "counter",
        "API sampling window",
        "Aggregate non-negative samples in timestamped modular buckets over a fixed recent window.",
        "0xC0A17E02",
        ("buckets_", "latest_", "%buckets_.size()", "bucket.stamp", "buckets_at"),
        ("non-negative amounts", "non-decreasing ticks", "stale aggregate", "buckets_at", "in increasing tick order"),
        ("untagged_ring", "stale_cell_accumulation"),
    ),
    TaskSpec(
        "weighted-service-rotor", "WeightedServiceRotor", "weighted", "Weighted service rotor",
        "Select service lanes with smooth weighted recurrence.", "0x51A0F001",
        ("lanes_", "total_weight", "best_score", "lane.score+="),
        ("smooth weighted", "original order", "all weights are zero", "set_weight", "lanes"),
        ("cursor_only_round_robin", "expanded_repeated_schedule"),
    ),
    TaskSpec(
        "generation-arrival-barrier", "GenerationArrivalBarrier", "barrier", "Generation arrival barrier",
        "Track distinct arrivals and automatically complete generations.", "0xBA221E02",
        ("arrived_", "generation_", "arrived_count_", "std::fill(arrived_"),
        ("once per generation", "last distinct arrival", "withdraw", "zero participants", "arrived"),
        ("raw_arrival_counter", "manual_reset_latch"),
    ),
    TaskSpec(
        "traffic-phase-controller", "TrafficPhaseController", "phase", "Traffic phase controller",
        "Consume elapsed ticks across cyclic phases with exact residual time.", "0xFA5E0003",
        ("durations_", "remaining_", "while(ticks", "entered.push_back"),
        ("zero duration", "phase 0", "remaining", "several phases or cycles", "zero advance"),
        ("one_transition_per_call", "phase_count_modulo_only"),
    ),
    TaskSpec(
        "circular-signal-convolution", "circular_convolution", "convolution", "Circular signal convolution",
        "Compute equal-length circular convolution by modular indexing.", "0xC04A0004",
        ("circular_convolution", "%left.size()", "for(std::size_t k", "for(std::size_t i"),
        ("empty", "unequal", "exactly", "modular", "long-long"),
        ("linear_convolution", "truncated_convolution"),
    ),
    TaskSpec(
        "modular-arc-set", "ModularArcSet", "arcs", "Modular arc set",
        "Maintain wraparound arcs as canonical disjoint linear intervals.", "0xA2C50005",
        ("intervals_", "add_segment", "remove_segment", "capacity_-start"),
        ("1 through capacity", "wrap", "merge", "split", "intervals"),
        ("capacity_sized_bitmap", "unmerged_arc_list"),
    ),
    TaskSpec(
        "clockwise-token-router", "ClockwiseTokenRouter", "router", "Clockwise token router",
        "Route positions to the first clockwise token with wraparound.", "0xC10C0006",
        ("tokens_", "lower_bound", "tokens_.insert", "owner_of"),
        ("unique", "non-empty", "greater than or equal", "wraps", "tokens"),
        ("key_modulo_token_count", "insertion_order_lookup"),
    ),
    TaskSpec(
        "functional-cycle-index", "FunctionalCycleIndex", "graph", "Functional cycle index",
        "Index canonical cycles and distances in a functional graph.", "0xF00C0007",
        ("successors_", "indegree", "reverse", "cycle_id"),
        ("successor", "minimum node", "distance", "cycle position", "cycle id"),
        ("reachability_only", "per_query_repeated_walk"),
    ),
    TaskSpec(
        "round-robin-pairing-table", "RoundRobinPairingTable", "tournament", "Round-robin pairing table",
        "Generate deterministic tournament rounds with the circle method.", "0x20B10008",
        ("rotation", "std::rotate", "result.push_back", "bye"),
        ("non-empty", "unique", "n-1", "bye", "every unordered pair"),
        ("non_rotating_adjacency", "all_pairs_one_round"),
    ),
    TaskSpec(
        "crc-byte-register", "CrcByteRegister", "crc", "CRC byte register",
        "Maintain a streaming bitwise polynomial remainder.", "0xC2C80009",
        ("register_", "polynomial_", "&0x80", "<<1"),
        ("polynomial zero", "eight", "high-bit", "reset", "unchanged"),
        ("additive_checksum", "xor_only_checksum"),
    ),
    TaskSpec(
        "epoch-stamped-sparse-table", "EpochStampedSparseTable", "epoch", "Epoch-stamped sparse table",
        "Clear sparse slot values logically with generation stamps.", "0xE90C0010",
        ("stamps_", "epoch_", "std::fill(stamps_", "stamp==epoch_"),
        ("out-of-range", "logical clear", "wrap", "epoch", "entries"),
        ("clear_every_value", "map_delegation"),
    ),
    TaskSpec(
        "rotating-bloom-membership", "RotatingBloomMembership", "bloom", "Rotating Bloom membership",
        "Track probabilistic membership across rotating bit slices.", "0xB1000011",
        ("slices_", "hash_one", "hash_two", "current_"),
        ("zero slice or bit counts", "empty keys", "both", "rotate", "active_bits"),
        ("exact_unordered_set", "unioned_global_bitmap"),
    ),
    TaskSpec(
        "serial-replay-window", "SerialReplayWindow", "replay", "Serial replay window",
        "Admit unseen wrap-safe serials in a bounded bitmap window.", "0x5E2A0012",
        ("bitmap_", "highest_", "serial_delta", "<<static_cast<unsigned>(delta)"),
        ("1 through 64", "first serial", "ambiguous half-range", "wrap", "bitmap"),
        ("ordinary_unsigned_order", "unbounded_seen_set"),
    ),
)

EXTRA_KINDS = frozenset(spec.kind for spec in TASKS[3:])

if not MIN_ROOTS <= len(TASKS) <= MAX_ROOTS:
    raise RuntimeError(
        f"binding_root_count_failed: expected {MIN_ROOTS}..{MAX_ROOTS}, found {len(TASKS)}"
    )


def _extra_header(kind: str) -> str:
    headers = {
        "weighted": """#pragma once
#include <cstddef>
#include <optional>
#include <string>
#include <utility>
#include <vector>
namespace curriculum { struct LaneScore { std::string id; unsigned weight; long long score; }; bool operator==(const LaneScore&,const LaneScore&); class WeightedServiceRotor { public: explicit WeightedServiceRotor(const std::vector<std::pair<std::string,unsigned>>& lanes); bool valid() const; bool set_weight(const std::string&,unsigned); std::optional<std::string> next(); std::vector<LaneScore> lanes() const; private: std::vector<LaneScore> lanes_; bool valid_=true; }; }
""",
        "barrier": """#pragma once
#include <cstddef>
#include <vector>
namespace curriculum { struct BarrierState { std::size_t generation; std::vector<std::size_t> arrived; }; bool operator==(const BarrierState&,const BarrierState&); class GenerationArrivalBarrier { public: explicit GenerationArrivalBarrier(std::size_t participants); bool arrive(std::size_t); bool withdraw(std::size_t); BarrierState state() const; private: std::vector<bool> arrived_; std::size_t arrived_count_=0U; std::size_t generation_=0U; }; }
""",
        "phase": """#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum { struct PhaseState { std::size_t phase; std::size_t remaining; }; bool operator==(const PhaseState&,const PhaseState&); class TrafficPhaseController { public: explicit TrafficPhaseController(const std::vector<std::size_t>& durations); bool valid() const; std::optional<std::vector<std::size_t>> advance(std::size_t ticks); std::optional<PhaseState> state() const; private: std::vector<std::size_t> durations_; std::size_t phase_=0U; std::size_t remaining_=0U; bool valid_=false; }; }
""",
        "convolution": """#pragma once
#include <optional>
#include <vector>
namespace curriculum { std::optional<std::vector<long long>> circular_convolution(const std::vector<int>& left,const std::vector<int>& right); }
""",
        "arcs": """#pragma once
#include <cstddef>
#include <vector>
namespace curriculum { struct LinearArc { std::size_t begin; std::size_t end; }; bool operator==(const LinearArc&,const LinearArc&); class ModularArcSet { public: explicit ModularArcSet(std::size_t capacity); bool add(std::size_t start,std::size_t length); bool remove(std::size_t start,std::size_t length); bool contains(std::size_t slot) const; std::vector<LinearArc> intervals() const; private: void add_segment(std::size_t,std::size_t); void remove_segment(std::size_t,std::size_t); std::size_t capacity_; std::vector<LinearArc> intervals_; }; }
""",
        "router": """#pragma once
#include <cstdint>
#include <optional>
#include <string>
#include <vector>
namespace curriculum { struct RouteToken { std::uint32_t position; std::string owner; }; bool operator==(const RouteToken&,const RouteToken&); class ClockwiseTokenRouter { public: bool add_token(std::uint32_t,const std::string&); bool remove_token(std::uint32_t); std::optional<std::string> owner_of(std::uint32_t) const; std::vector<RouteToken> tokens() const; private: std::vector<RouteToken> tokens_; }; }
""",
        "graph": """#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum { struct CycleInfo { std::size_t cycle_id; std::size_t distance; std::size_t position; std::size_t cycle_length; }; bool operator==(const CycleInfo&,const CycleInfo&); class FunctionalCycleIndex { public: explicit FunctionalCycleIndex(const std::vector<std::size_t>& successors); bool valid() const; std::size_t cycle_count() const; std::optional<CycleInfo> info(std::size_t node) const; private: std::vector<std::size_t> successors_; std::vector<CycleInfo> info_; bool valid_=false; std::size_t cycle_count_=0U; }; }
""",
        "tournament": """#pragma once
#include <string>
#include <vector>
namespace curriculum { struct Pairing { std::string first; std::string second; }; bool operator==(const Pairing&,const Pairing&); class RoundRobinPairingTable { public: explicit RoundRobinPairingTable(const std::vector<std::string>& teams); bool valid() const; std::vector<std::vector<Pairing>> rounds() const; private: std::vector<std::string> teams_; bool valid_=true; }; }
""",
        "crc": """#pragma once
#include <cstdint>
namespace curriculum { class CrcByteRegister { public: CrcByteRegister(std::uint8_t polynomial,std::uint8_t initial); bool valid() const; bool update(std::uint8_t byte); std::uint8_t value() const; void reset(); private: std::uint8_t polynomial_; std::uint8_t initial_; std::uint8_t register_; bool valid_; }; }
""",
        "epoch": """#pragma once
#include <cstddef>
#include <cstdint>
#include <optional>
#include <vector>
namespace curriculum { struct SparseEntry { std::size_t index; int value; }; bool operator==(const SparseEntry&,const SparseEntry&); class EpochStampedSparseTable { public: explicit EpochStampedSparseTable(std::size_t capacity); bool set(std::size_t,int); std::optional<int> get(std::size_t) const; void clear(); std::uint8_t generation() const; std::vector<SparseEntry> entries() const; private: std::vector<int> values_; std::vector<std::uint8_t> stamps_; std::uint8_t epoch_=1U; }; }
""",
        "bloom": """#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>
namespace curriculum { class RotatingBloomMembership { public: RotatingBloomMembership(std::size_t slices,std::size_t bits_per_slice); bool valid() const; bool insert(const std::string&); bool possibly_contains(const std::string&) const; bool rotate(); std::size_t current_slice() const; std::vector<std::vector<std::size_t>> active_bits() const; private: std::size_t hash_one(const std::string&) const; std::size_t hash_two(const std::string&) const; std::vector<std::vector<bool>> slices_; std::size_t bits_=0U; std::size_t current_=0U; }; }
""",
        "replay": """#pragma once
#include <cstddef>
#include <cstdint>
namespace curriculum { struct ReplayState { bool initialized; std::uint32_t highest; std::uint64_t bitmap; }; bool operator==(const ReplayState&,const ReplayState&); class SerialReplayWindow { public: explicit SerialReplayWindow(std::size_t width); bool valid() const; bool accept(std::uint32_t serial); ReplayState state() const; private: std::size_t width_; bool initialized_=false; std::uint32_t highest_=0U; std::uint64_t bitmap_=0U; }; }
""",
    }
    return headers[kind]


def _extra_reference(kind: str) -> str:
    references = {
        "weighted": """#include \"task.h\"
#include <algorithm>
#include <limits>
#include <set>
namespace curriculum { bool operator==(const LaneScore& a,const LaneScore& b){return a.id==b.id&&a.weight==b.weight&&a.score==b.score;} WeightedServiceRotor::WeightedServiceRotor(const std::vector<std::pair<std::string,unsigned>>& input){std::set<std::string> ids;for(const auto& item:input){if(item.first.empty()||item.second>1000000U||!ids.insert(item.first).second){valid_=false;lanes_.clear();return;}lanes_.push_back({item.first,item.second,0});}} bool WeightedServiceRotor::valid()const{return valid_;} bool WeightedServiceRotor::set_weight(const std::string& id,unsigned weight){if(!valid_||weight>1000000U)return false;for(auto& lane:lanes_)if(lane.id==id){lane.weight=weight;return true;}return false;} std::optional<std::string> WeightedServiceRotor::next(){if(!valid_)return std::nullopt;long long total_weight=0;for(const auto& lane:lanes_)total_weight+=lane.weight;if(total_weight==0)return std::nullopt;std::size_t best=0U;long long best_score=std::numeric_limits<long long>::min();for(std::size_t i=0;i<lanes_.size();++i){auto& lane=lanes_[i];lane.score+=lane.weight;if(lane.score>best_score){best_score=lane.score;best=i;}}lanes_[best].score-=total_weight;return lanes_[best].id;} std::vector<LaneScore> WeightedServiceRotor::lanes()const{return lanes_;} }
""",
        "barrier": """#include \"task.h\"
#include <algorithm>
namespace curriculum { bool operator==(const BarrierState& a,const BarrierState& b){return a.generation==b.generation&&a.arrived==b.arrived;} GenerationArrivalBarrier::GenerationArrivalBarrier(std::size_t participants):arrived_(participants,false){} bool GenerationArrivalBarrier::arrive(std::size_t participant){if(participant>=arrived_.size()||arrived_[participant])return false;arrived_[participant]=true;++arrived_count_;if(arrived_count_==arrived_.size()){++generation_;std::fill(arrived_.begin(),arrived_.end(),false);arrived_count_=0U;}return true;} bool GenerationArrivalBarrier::withdraw(std::size_t participant){if(participant>=arrived_.size()||!arrived_[participant])return false;arrived_[participant]=false;--arrived_count_;return true;} BarrierState GenerationArrivalBarrier::state()const{BarrierState result{generation_,{}};for(std::size_t i=0;i<arrived_.size();++i)if(arrived_[i])result.arrived.push_back(i);return result;} }
""",
        "phase": """#include \"task.h\"
#include <algorithm>
namespace curriculum { bool operator==(const PhaseState& a,const PhaseState& b){return a.phase==b.phase&&a.remaining==b.remaining;} TrafficPhaseController::TrafficPhaseController(const std::vector<std::size_t>& durations):durations_(durations){valid_=!durations_.empty()&&std::all_of(durations_.begin(),durations_.end(),[](std::size_t value){return value>0U;});if(valid_)remaining_=durations_[0];} bool TrafficPhaseController::valid()const{return valid_;} std::optional<std::vector<std::size_t>> TrafficPhaseController::advance(std::size_t ticks){if(!valid_)return std::nullopt;std::vector<std::size_t> entered;while(ticks>=remaining_){ticks-=remaining_;phase_=(phase_+1U)%durations_.size();remaining_=durations_[phase_];entered.push_back(phase_);}remaining_-=ticks;return entered;} std::optional<PhaseState> TrafficPhaseController::state()const{if(!valid_)return std::nullopt;return PhaseState{phase_,remaining_};} }
""",
        "convolution": """#include \"task.h\"
namespace curriculum { std::optional<std::vector<long long>> circular_convolution(const std::vector<int>& left,const std::vector<int>& right){if(left.empty()||left.size()!=right.size())return std::nullopt;std::vector<long long> result(left.size(),0);for(std::size_t k=0;k<left.size();++k)for(std::size_t i=0;i<left.size();++i)result[k]+=static_cast<long long>(left[i])*right[(k+left.size()-i)%left.size()];return result;} }
""",
        "arcs": """#include \"task.h\"
#include <algorithm>
namespace curriculum { bool operator==(const LinearArc& a,const LinearArc& b){return a.begin==b.begin&&a.end==b.end;} ModularArcSet::ModularArcSet(std::size_t capacity):capacity_(capacity){} void ModularArcSet::add_segment(std::size_t begin,std::size_t end){intervals_.push_back({begin,end});std::sort(intervals_.begin(),intervals_.end(),[](const auto& a,const auto& b){return a.begin<b.begin;});std::vector<LinearArc> merged;for(const auto& arc:intervals_){if(merged.empty()||merged.back().end<arc.begin)merged.push_back(arc);else merged.back().end=std::max(merged.back().end,arc.end);}intervals_=std::move(merged);} void ModularArcSet::remove_segment(std::size_t begin,std::size_t end){std::vector<LinearArc> kept;for(const auto& arc:intervals_){if(arc.end<=begin||arc.begin>=end)kept.push_back(arc);else{if(arc.begin<begin)kept.push_back({arc.begin,begin});if(arc.end>end)kept.push_back({end,arc.end});}}intervals_=std::move(kept);} bool ModularArcSet::add(std::size_t start,std::size_t length){if(capacity_==0U||start>=capacity_||length==0U||length>capacity_)return false;if(length==capacity_){intervals_={{0U,capacity_}};return true;}const auto tail=capacity_-start;if(length<=tail)add_segment(start,start+length);else{add_segment(start,capacity_);add_segment(0U,length-tail);}return true;} bool ModularArcSet::remove(std::size_t start,std::size_t length){if(capacity_==0U||start>=capacity_||length==0U||length>capacity_)return false;if(length==capacity_){intervals_.clear();return true;}const auto tail=capacity_-start;if(length<=tail)remove_segment(start,start+length);else{remove_segment(start,capacity_);remove_segment(0U,length-tail);}return true;} bool ModularArcSet::contains(std::size_t slot)const{if(slot>=capacity_)return false;for(const auto& arc:intervals_)if(slot>=arc.begin&&slot<arc.end)return true;return false;} std::vector<LinearArc> ModularArcSet::intervals()const{return intervals_;} }
""",
        "router": """#include \"task.h\"
#include <algorithm>
namespace curriculum { bool operator==(const RouteToken& a,const RouteToken& b){return a.position==b.position&&a.owner==b.owner;} bool ClockwiseTokenRouter::add_token(std::uint32_t position,const std::string& owner){if(owner.empty())return false;const auto it=std::lower_bound(tokens_.begin(),tokens_.end(),position,[](const auto& token,std::uint32_t value){return token.position<value;});if(it!=tokens_.end()&&it->position==position)return false;tokens_.insert(it,{position,owner});return true;} bool ClockwiseTokenRouter::remove_token(std::uint32_t position){const auto it=std::lower_bound(tokens_.begin(),tokens_.end(),position,[](const auto& token,std::uint32_t value){return token.position<value;});if(it==tokens_.end()||it->position!=position)return false;tokens_.erase(it);return true;} std::optional<std::string> ClockwiseTokenRouter::owner_of(std::uint32_t position)const{if(tokens_.empty())return std::nullopt;const auto it=std::lower_bound(tokens_.begin(),tokens_.end(),position,[](const auto& token,std::uint32_t value){return token.position<value;});return (it==tokens_.end()?tokens_.front():*it).owner;} std::vector<RouteToken> ClockwiseTokenRouter::tokens()const{return tokens_;} }
""",
        "graph": """#include \"task.h\"
#include <algorithm>
namespace curriculum { bool operator==(const CycleInfo& a,const CycleInfo& b){return a.cycle_id==b.cycle_id&&a.distance==b.distance&&a.position==b.position&&a.cycle_length==b.cycle_length;} FunctionalCycleIndex::FunctionalCycleIndex(const std::vector<std::size_t>& successors):successors_(successors){const auto n=successors_.size();if(std::any_of(successors_.begin(),successors_.end(),[n](std::size_t value){return value>=n;}))return;valid_=true;info_.assign(n,{0U,0U,0U,0U});std::vector<std::size_t> indegree(n,0U);std::vector<std::vector<std::size_t>> reverse(n);for(std::size_t i=0;i<n;++i){++indegree[successors_[i]];reverse[successors_[i]].push_back(i);}std::vector<std::size_t> work;for(std::size_t i=0;i<n;++i)if(indegree[i]==0U)work.push_back(i);for(std::size_t p=0;p<work.size();++p){const auto next=successors_[work[p]];if(--indegree[next]==0U)work.push_back(next);}std::vector<bool> assigned(n,false);for(std::size_t seed=0;seed<n;++seed){if(indegree[seed]==0U||assigned[seed])continue;std::vector<std::size_t> cycle;auto node=seed;do{cycle.push_back(node);node=successors_[node];}while(node!=seed);const auto minimum=*std::min_element(cycle.begin(),cycle.end());cycle.clear();node=minimum;do{cycle.push_back(node);node=successors_[node];}while(node!=minimum);for(std::size_t position=0;position<cycle.size();++position){const auto member=cycle[position];assigned[member]=true;info_[member]={cycle_count_,0U,position,cycle.size()};}++cycle_count_;}std::vector<std::size_t> frontier;for(std::size_t i=0;i<n;++i)if(assigned[i])frontier.push_back(i);for(std::size_t p=0;p<frontier.size();++p){const auto parent=frontier[p];for(const auto child:reverse[parent])if(!assigned[child]){assigned[child]=true;info_[child]=info_[parent];++info_[child].distance;frontier.push_back(child);}}} bool FunctionalCycleIndex::valid()const{return valid_;} std::size_t FunctionalCycleIndex::cycle_count()const{return valid_?cycle_count_:0U;} std::optional<CycleInfo> FunctionalCycleIndex::info(std::size_t node)const{if(!valid_||node>=info_.size())return std::nullopt;return info_[node];} }
""",
        "tournament": """#include \"task.h\"
#include <algorithm>
#include <set>
namespace curriculum { bool operator==(const Pairing& a,const Pairing& b){return a.first==b.first&&a.second==b.second;} RoundRobinPairingTable::RoundRobinPairingTable(const std::vector<std::string>& teams):teams_(teams){std::set<std::string> unique;for(const auto& team:teams_)if(team.empty()||!unique.insert(team).second){valid_=false;teams_.clear();return;}} bool RoundRobinPairingTable::valid()const{return valid_;} std::vector<std::vector<Pairing>> RoundRobinPairingTable::rounds()const{std::vector<std::vector<Pairing>> result;if(!valid_||teams_.size()<2U)return result;std::vector<std::string> rotation=teams_;const std::string bye; if(rotation.size()%2U!=0U)rotation.push_back(bye);for(std::size_t round=0;round+1U<rotation.size();++round){std::vector<Pairing> matches;for(std::size_t i=0;i<rotation.size()/2U;++i){auto first=rotation[i];auto second=rotation[rotation.size()-1U-i];if(first.empty()||second.empty())continue;if(second<first)std::swap(first,second);matches.push_back({first,second});}std::sort(matches.begin(),matches.end(),[](const auto& a,const auto& b){return a.first<b.first||(a.first==b.first&&a.second<b.second);});result.push_back(matches);std::rotate(rotation.begin()+1,rotation.end()-1,rotation.end());}return result;} }
""",
        "crc": """#include \"task.h\"
namespace curriculum { CrcByteRegister::CrcByteRegister(std::uint8_t polynomial,std::uint8_t initial):polynomial_(polynomial),initial_(initial),register_(initial),valid_(polynomial!=0U){} bool CrcByteRegister::valid()const{return valid_;} bool CrcByteRegister::update(std::uint8_t byte){if(!valid_)return false;register_^=byte;for(unsigned bit=0;bit<8U;++bit)register_=static_cast<std::uint8_t>((register_&0x80U)!=0U?(register_<<1U)^polynomial_:register_<<1U);return true;} std::uint8_t CrcByteRegister::value()const{return register_;} void CrcByteRegister::reset(){register_=initial_;} }
""",
        "epoch": """#include \"task.h\"
#include <algorithm>
namespace curriculum { bool operator==(const SparseEntry& a,const SparseEntry& b){return a.index==b.index&&a.value==b.value;} EpochStampedSparseTable::EpochStampedSparseTable(std::size_t capacity):values_(capacity,0),stamps_(capacity,0U){} bool EpochStampedSparseTable::set(std::size_t index,int value){if(index>=values_.size())return false;values_[index]=value;stamps_[index]=epoch_;return true;} std::optional<int> EpochStampedSparseTable::get(std::size_t index)const{if(index>=values_.size()||stamps_[index]!=epoch_)return std::nullopt;return values_[index];} void EpochStampedSparseTable::clear(){++epoch_;if(epoch_==0U){std::fill(stamps_.begin(),stamps_.end(),0U);epoch_=1U;}} std::uint8_t EpochStampedSparseTable::generation()const{return epoch_;} std::vector<SparseEntry> EpochStampedSparseTable::entries()const{std::vector<SparseEntry> result;for(std::size_t index=0;index<values_.size();++index){const auto stamp=stamps_[index];if(stamp==epoch_)result.push_back({index,values_[index]});}return result;} }
""",
        "bloom": """#include \"task.h\"
#include <algorithm>
namespace curriculum { RotatingBloomMembership::RotatingBloomMembership(std::size_t slices,std::size_t bits_per_slice):slices_(slices,std::vector<bool>(bits_per_slice,false)),bits_(bits_per_slice){} bool RotatingBloomMembership::valid()const{return !slices_.empty()&&bits_>0U;} std::size_t RotatingBloomMembership::hash_one(const std::string& key)const{std::uint64_t hash=1469598103934665603ULL;for(unsigned char byte:key){hash^=byte;hash*=1099511628211ULL;}return static_cast<std::size_t>(hash%bits_);} std::size_t RotatingBloomMembership::hash_two(const std::string& key)const{std::uint64_t hash=5381U;for(unsigned char byte:key)hash=((hash<<5U)+hash)^byte;return static_cast<std::size_t>(hash%bits_);} bool RotatingBloomMembership::insert(const std::string& key){if(!valid()||key.empty())return false;slices_[current_][hash_one(key)]=true;slices_[current_][hash_two(key)]=true;return true;} bool RotatingBloomMembership::possibly_contains(const std::string& key)const{if(!valid()||key.empty())return false;const auto first=hash_one(key);const auto second=hash_two(key);return std::any_of(slices_.begin(),slices_.end(),[first,second](const auto& slice){return slice[first]&&slice[second];});} bool RotatingBloomMembership::rotate(){if(!valid())return false;current_=(current_+1U)%slices_.size();std::fill(slices_[current_].begin(),slices_[current_].end(),false);return true;} std::size_t RotatingBloomMembership::current_slice()const{return current_;} std::vector<std::vector<std::size_t>> RotatingBloomMembership::active_bits()const{std::vector<std::vector<std::size_t>> result(slices_.size());for(std::size_t slice=0;slice<slices_.size();++slice)for(std::size_t bit=0;bit<bits_;++bit)if(slices_[slice][bit])result[slice].push_back(bit);return result;} }
""",
        "replay": """#include \"task.h\"
#include <limits>
namespace curriculum { bool operator==(const ReplayState& a,const ReplayState& b){return a.initialized==b.initialized&&a.highest==b.highest&&a.bitmap==b.bitmap;} namespace { std::int64_t serial_delta(std::uint32_t left,std::uint32_t right){const auto raw=static_cast<std::uint32_t>(left-right);if(raw==0x80000000U)return std::numeric_limits<std::int64_t>::min();if(raw<0x80000000U)return raw;return -static_cast<std::int64_t>(0x100000000ULL-raw);} } SerialReplayWindow::SerialReplayWindow(std::size_t width):width_(width){} bool SerialReplayWindow::valid()const{return width_>=1U&&width_<=64U;} bool SerialReplayWindow::accept(std::uint32_t serial){if(!valid())return false;if(!initialized_){initialized_=true;highest_=serial;bitmap_=1U;return true;}const auto delta=serial_delta(serial,highest_);if(delta==std::numeric_limits<std::int64_t>::min()||delta==0)return false;if(delta>0){if(static_cast<std::uint64_t>(delta)>=width_)bitmap_=1U;else bitmap_=(bitmap_<<static_cast<unsigned>(delta))|1U;highest_=serial;if(width_<64U)bitmap_&=(1ULL<<width_)-1ULL;return true;}const auto distance=static_cast<std::uint64_t>(-delta);if(distance>=width_)return false;const auto mask=1ULL<<distance;if((bitmap_&mask)!=0U)return false;bitmap_|=mask;return true;} ReplayState SerialReplayWindow::state()const{return {initialized_,highest_,bitmap_};} }
""",
    }
    return references[kind]


def _extra_starter(kind: str) -> str:
    starters = {
        "weighted": """#include \"task.h\"
namespace curriculum { bool operator==(const LaneScore&,const LaneScore&){return false;} WeightedServiceRotor::WeightedServiceRotor(const std::vector<std::pair<std::string,unsigned>>&){} bool WeightedServiceRotor::valid()const{return false;} bool WeightedServiceRotor::set_weight(const std::string&,unsigned){return false;} std::optional<std::string> WeightedServiceRotor::next(){return std::nullopt;} std::vector<LaneScore> WeightedServiceRotor::lanes()const{return {};} }
""",
        "barrier": """#include \"task.h\"
namespace curriculum { bool operator==(const BarrierState&,const BarrierState&){return false;} GenerationArrivalBarrier::GenerationArrivalBarrier(std::size_t){} bool GenerationArrivalBarrier::arrive(std::size_t){return false;} bool GenerationArrivalBarrier::withdraw(std::size_t){return false;} BarrierState GenerationArrivalBarrier::state()const{return {0U,{}};} }
""",
        "phase": """#include \"task.h\"
namespace curriculum { bool operator==(const PhaseState&,const PhaseState&){return false;} TrafficPhaseController::TrafficPhaseController(const std::vector<std::size_t>&){} bool TrafficPhaseController::valid()const{return false;} std::optional<std::vector<std::size_t>> TrafficPhaseController::advance(std::size_t){return std::nullopt;} std::optional<PhaseState> TrafficPhaseController::state()const{return std::nullopt;} }
""",
        "convolution": """#include \"task.h\"
namespace curriculum { std::optional<std::vector<long long>> circular_convolution(const std::vector<int>&,const std::vector<int>&){return std::nullopt;} }
""",
        "arcs": """#include \"task.h\"
namespace curriculum { bool operator==(const LinearArc&,const LinearArc&){return false;} ModularArcSet::ModularArcSet(std::size_t):capacity_(0U){} void ModularArcSet::add_segment(std::size_t,std::size_t){} void ModularArcSet::remove_segment(std::size_t,std::size_t){} bool ModularArcSet::add(std::size_t,std::size_t){return false;} bool ModularArcSet::remove(std::size_t,std::size_t){return false;} bool ModularArcSet::contains(std::size_t)const{return false;} std::vector<LinearArc> ModularArcSet::intervals()const{return {};} }
""",
        "router": """#include \"task.h\"
namespace curriculum { bool operator==(const RouteToken&,const RouteToken&){return false;} bool ClockwiseTokenRouter::add_token(std::uint32_t,const std::string&){return false;} bool ClockwiseTokenRouter::remove_token(std::uint32_t){return false;} std::optional<std::string> ClockwiseTokenRouter::owner_of(std::uint32_t)const{return std::nullopt;} std::vector<RouteToken> ClockwiseTokenRouter::tokens()const{return {};} }
""",
        "graph": """#include \"task.h\"
namespace curriculum { bool operator==(const CycleInfo&,const CycleInfo&){return false;} FunctionalCycleIndex::FunctionalCycleIndex(const std::vector<std::size_t>&){} bool FunctionalCycleIndex::valid()const{return false;} std::size_t FunctionalCycleIndex::cycle_count()const{return 0U;} std::optional<CycleInfo> FunctionalCycleIndex::info(std::size_t)const{return std::nullopt;} }
""",
        "tournament": """#include \"task.h\"
namespace curriculum { bool operator==(const Pairing&,const Pairing&){return false;} RoundRobinPairingTable::RoundRobinPairingTable(const std::vector<std::string>&){} bool RoundRobinPairingTable::valid()const{return false;} std::vector<std::vector<Pairing>> RoundRobinPairingTable::rounds()const{return {};} }
""",
        "crc": """#include \"task.h\"
namespace curriculum { CrcByteRegister::CrcByteRegister(std::uint8_t,std::uint8_t):polynomial_(0U),initial_(0U),register_(0U),valid_(false){} bool CrcByteRegister::valid()const{return false;} bool CrcByteRegister::update(std::uint8_t){return false;} std::uint8_t CrcByteRegister::value()const{return 0U;} void CrcByteRegister::reset(){} }
""",
        "epoch": """#include \"task.h\"
namespace curriculum { bool operator==(const SparseEntry&,const SparseEntry&){return false;} EpochStampedSparseTable::EpochStampedSparseTable(std::size_t){} bool EpochStampedSparseTable::set(std::size_t,int){return false;} std::optional<int> EpochStampedSparseTable::get(std::size_t)const{return std::nullopt;} void EpochStampedSparseTable::clear(){} std::uint8_t EpochStampedSparseTable::generation()const{return 0U;} std::vector<SparseEntry> EpochStampedSparseTable::entries()const{return {};} }
""",
        "bloom": """#include \"task.h\"
namespace curriculum { RotatingBloomMembership::RotatingBloomMembership(std::size_t,std::size_t){} bool RotatingBloomMembership::valid()const{return false;} std::size_t RotatingBloomMembership::hash_one(const std::string&)const{return 0U;} std::size_t RotatingBloomMembership::hash_two(const std::string&)const{return 0U;} bool RotatingBloomMembership::insert(const std::string&){return false;} bool RotatingBloomMembership::possibly_contains(const std::string&)const{return false;} bool RotatingBloomMembership::rotate(){return false;} std::size_t RotatingBloomMembership::current_slice()const{return 0U;} std::vector<std::vector<std::size_t>> RotatingBloomMembership::active_bits()const{return {};} }
""",
        "replay": """#include \"task.h\"
namespace curriculum { bool operator==(const ReplayState&,const ReplayState&){return false;} SerialReplayWindow::SerialReplayWindow(std::size_t):width_(0U){} bool SerialReplayWindow::valid()const{return false;} bool SerialReplayWindow::accept(std::uint32_t){return false;} ReplayState SerialReplayWindow::state()const{return {false,0U,0U};} }
""",
    }
    return starters[kind]


def _extra_instructions(spec: TaskSpec) -> str:
    details = {
        "weighted": "IDs must be non-empty and unique and weights must be at most 1000000. On each `next`, add every lane weight to its score, choose the greatest score with original order as the tie rule, then subtract total active weight. `set_weight` retains scores. If all weights are zero, `next` has no value. `lanes` returns the complete original-order score state.",
        "barrier": "A participant may arrive once per generation. The last distinct arrival increments the generation and clears all arrivals atomically. `withdraw` removes only an arrival in the current generation. Zero participants reject mutation. `state.arrived` is increasing and complete.",
        "phase": "An empty duration list or any zero duration is invalid. A valid controller starts in phase 0 with its full duration. `advance` consumes every tick, may enter several phases or cycles, returns each entered phase, and preserves exact remaining time. Zero advance is non-mutating.",
        "convolution": "Empty or unequal vectors return no value. For equal length N, output k is the long-long sum of left[i] times right[(k+N-i) modulo N] for every i. Return exactly N outputs and do not mutate inputs.",
        "arcs": "Capacity zero is invalid. Start must be in range and length must be 1 through capacity. Wrap arcs split at zero. Add merges overlaps and adjacency; remove subtracts and may split. `intervals` returns the complete sorted, disjoint, non-adjacent linear representation.",
        "router": "Token positions are unique and owners non-empty. `owner_of` selects the first token position greater than or equal to the key and wraps to the first token. Empty lookup has no value. `tokens` is the complete increasing-position state.",
        "graph": "Every successor must be in range. Cycles are identified in ascending order of their minimum node; cycle position zero is that minimum and positions follow successors. Each node reports its cycle ID, edge distance to that cycle, reached cycle position, and cycle length.",
        "tournament": "Team names must be non-empty and unique. Use the circle method. Even N yields N-1 rounds; odd N uses an internal bye and yields N rounds. Omit byes, order each pair lexicographically, sort each round, and schedule every unordered pair exactly once.",
        "crc": "Polynomial zero is invalid. A valid `update` XORs the byte into the register and performs eight high-bit conditional left-shift polynomial steps. `reset` restores the initial register. Invalid updates return false unchanged.",
        "epoch": "Set and get reject out-of-range indices. Set stamps a slot with the current nonzero epoch. `clear` is a logical clear by epoch increment; only when the 8-bit epoch wraps to zero are all stamps reset before epoch becomes one. `entries` is the complete increasing-index current state.",
        "bloom": "Zero slice or bit counts are invalid and empty keys are rejected. Insert sets two deterministic hash bits in the current slice. Query succeeds only if one individual slice contains both bits. Rotate advances cyclically and clears the newly current slice. `active_bits` is complete per-slice state.",
        "replay": "Width must be in 1 through 64. The first serial initializes the window. Newer serials use wrap-safe 32-bit serial distance and advance the bitmap; older in-window serials are accepted once. Reject duplicates, too-old values, and the ambiguous half-range delta. Zero after UINT32_MAX is newer. `state` is complete.",
    }
    return (
        f"# Instructions\n\nImplement `{spec.class_name}`. {spec.contract} "
        f"{details[spec.kind]} Invalid requests do not mutate valid state. "
        "This is local candidate material, not an SFT release.\n"
    )


def _extra_test(kind: str, hidden: bool) -> str:
    visible = {
        "weighted": """#include \"task.h\"
#include <string>
#include <utility>
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::WeightedServiceRotor rotor({{"a",5U},{"b",1U},{"c",1U}});c(rotor.valid());std::vector<std::string> got;for(int i=0;i<7;++i)got.push_back(*rotor.next());c(got==std::vector<std::string>({"a","a","b","a","c","a","a"}));c(rotor.set_weight("b",0U));c(!rotor.set_weight("missing",1U));curriculum::WeightedServiceRotor zero({{"x",0U}});c(!zero.next());curriculum::WeightedServiceRotor bad({{"x",1U},{"x",2U}});c(!bad.valid());return f?1:0;}
""",
        "barrier": """#include \"task.h\"
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::GenerationArrivalBarrier b(3U);c(b.arrive(2U));c(!b.arrive(2U));c(b.arrive(0U));c(b.state()==curriculum::BarrierState{0U,{0U,2U}});c(b.withdraw(2U));c(!b.withdraw(1U));c(b.arrive(1U));c(b.arrive(2U));c(b.state()==curriculum::BarrierState{1U,{}});curriculum::GenerationArrivalBarrier z(0U);c(!z.arrive(0U));return f?1:0;}
""",
        "phase": """#include \"task.h\"
#include <optional>
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::TrafficPhaseController p({2U,3U});c(p.valid());c(p.advance(1U)==std::optional<std::vector<std::size_t>>(std::vector<std::size_t>{}));c(p.state()==std::optional<curriculum::PhaseState>({0U,1U}));c(p.advance(1U)==std::optional<std::vector<std::size_t>>({1U}));c(p.advance(4U)==std::optional<std::vector<std::size_t>>({0U}));c(p.state()==std::optional<curriculum::PhaseState>({0U,1U}));curriculum::TrafficPhaseController bad({1U,0U});c(!bad.valid());c(!bad.advance(1U));return f?1:0;}
""",
        "convolution": """#include \"task.h\"
#include <optional>
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};c(curriculum::circular_convolution({1,2},{3,4})==std::optional<std::vector<long long>>({11,10}));c(curriculum::circular_convolution({1,0,0},{5,6,7})==std::optional<std::vector<long long>>({5,6,7}));c(!curriculum::circular_convolution({},{}));c(!curriculum::circular_convolution({1},{1,2}));return f?1:0;}
""",
        "arcs": """#include \"task.h\"
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::ModularArcSet arcs(10U);c(arcs.add(8U,4U));c(arcs.intervals()==std::vector<curriculum::LinearArc>({{0U,2U},{8U,10U}}));c(arcs.add(1U,8U));c(arcs.intervals()==std::vector<curriculum::LinearArc>({{0U,10U}}));c(arcs.remove(3U,4U));c(arcs.intervals()==std::vector<curriculum::LinearArc>({{0U,3U},{7U,10U}}));c(arcs.contains(8U));c(!arcs.contains(5U));c(!arcs.add(10U,1U));return f?1:0;}
""",
        "router": """#include \"task.h\"
#include <optional>
#include <string>
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::ClockwiseTokenRouter r;c(!r.owner_of(0U));c(r.add_token(100U,"a"));c(r.add_token(20U,"b"));c(r.owner_of(20U)==std::optional<std::string>("b"));c(r.owner_of(21U)==std::optional<std::string>("a"));c(r.owner_of(101U)==std::optional<std::string>("b"));c(!r.add_token(20U,"x"));c(r.tokens()==std::vector<curriculum::RouteToken>({{20U,"b"},{100U,"a"}}));c(r.remove_token(20U));return f?1:0;}
""",
        "graph": """#include \"task.h\"
#include <optional>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::FunctionalCycleIndex g({1U,2U,0U,2U,5U,4U,5U});c(g.valid());c(g.cycle_count()==2U);c(g.info(0U)==std::optional<curriculum::CycleInfo>({0U,0U,0U,3U}));c(g.info(3U)==std::optional<curriculum::CycleInfo>({0U,1U,2U,3U}));c(g.info(4U)==std::optional<curriculum::CycleInfo>({1U,0U,0U,2U}));c(g.info(6U)==std::optional<curriculum::CycleInfo>({1U,1U,1U,2U}));curriculum::FunctionalCycleIndex bad({1U});c(!bad.valid());return f?1:0;}
""",
        "tournament": """#include \"task.h\"
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::RoundRobinPairingTable t({"a","b","c","d"});c(t.valid());c(t.rounds()==std::vector<std::vector<curriculum::Pairing>>({{{"a","d"},{"b","c"}},{{"a","c"},{"b","d"}},{{"a","b"},{"c","d"}}}));curriculum::RoundRobinPairingTable odd({"a","b","c"});c(odd.rounds().size()==3U);curriculum::RoundRobinPairingTable bad({"a","a"});c(!bad.valid());return f?1:0;}
""",
        "crc": """#include \"task.h\"
#include <cstdint>
static std::uint8_t step(std::uint8_t reg,std::uint8_t poly,std::uint8_t byte){reg^=byte;for(unsigned i=0;i<8U;++i)reg=static_cast<std::uint8_t>((reg&0x80U)?(reg<<1U)^poly:reg<<1U);return reg;}int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::CrcByteRegister r(0x07U,0U);c(r.valid());std::uint8_t expected=0U;const std::uint8_t bytes[]{'1','2','3'};for(auto byte:bytes){expected=step(expected,0x07U,byte);c(r.update(byte));c(r.value()==expected);}r.reset();c(r.value()==0U);curriculum::CrcByteRegister bad(0U,9U);c(!bad.valid());c(!bad.update(1U));c(bad.value()==9U);return f?1:0;}
""",
        "epoch": """#include \"task.h\"
#include <optional>
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::EpochStampedSparseTable t(4U);c(t.set(2U,7));c(t.get(2U)==std::optional<int>(7));c(t.entries()==std::vector<curriculum::SparseEntry>({{2U,7}}));t.clear();c(!t.get(2U));c(t.set(0U,-2));c(!t.set(4U,1));for(int i=0;i<260;++i)t.clear();c(t.generation()!=0U);c(t.entries().empty());return f?1:0;}
""",
        "bloom": """#include \"task.h\"
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::RotatingBloomMembership b(2U,17U);c(b.valid());c(b.insert("alpha"));c(b.possibly_contains("alpha"));const auto before=b.active_bits();c(before.size()==2U&&!before[0].empty());c(b.rotate());c(b.possibly_contains("alpha"));c(b.rotate());c(!b.possibly_contains("alpha"));c(!b.insert(""));curriculum::RotatingBloomMembership bad(0U,4U);c(!bad.valid());return f?1:0;}
""",
        "replay": """#include \"task.h\"
#include <cstdint>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::SerialReplayWindow w(4U);c(w.valid());c(w.accept(10U));c(w.accept(12U));c(w.state()==curriculum::ReplayState{true,12U,5U});c(w.accept(11U));c(w.state().bitmap==7U);c(!w.accept(11U));c(!w.accept(8U));curriculum::SerialReplayWindow wrap(8U);c(wrap.accept(0xffffffffU));c(wrap.accept(0U));c(wrap.state().highest==0U);curriculum::SerialReplayWindow bad(65U);c(!bad.valid());return f?1:0;}
""",
    }
    if not hidden:
        return visible[kind]
    hidden_tests = {
        "weighted": """#include \"task.h\"
#include <cstdint>
#include <limits>
#include <optional>
#include <string>
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::WeightedServiceRotor subject({{"red",4U},{"blue",2U},{"green",1U}});std::vector<curriculum::LaneScore> model{{"red",4U,0},{"blue",2U,0},{"green",1U,0}};std::uint32_t rng=0x51A0F001U;for(std::size_t step=0;step<256U;++step){rng=rng*1664525U+1013904223U;if(rng%7U==0U){const auto index=(rng>>8U)%3U;const unsigned weight=(rng>>16U)%6U;c(subject.set_weight(model[index].id,weight));model[index].weight=weight;}else{long long total=0;for(auto& lane:model){lane.score+=lane.weight;total+=lane.weight;}std::optional<std::string> expected;if(total>0){std::size_t best=0U;for(std::size_t i=1;i<model.size();++i)if(model[i].score>model[best].score)best=i;model[best].score-=total;expected=model[best].id;}c(subject.next()==expected);}c(subject.lanes()==model);}return f?1:0;}
""",
        "barrier": """#include \"task.h\"
#include <cstdint>
#include <set>
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::GenerationArrivalBarrier subject(9U);std::set<std::size_t> arrived;std::size_t generation=0U;std::uint32_t rng=0xBA221E02U;for(std::size_t step=0;step<300U;++step){rng=rng*1103515245U+12345U;const auto id=static_cast<std::size_t>((rng>>8U)%11U);if(rng&1U){const bool expected=id<9U&&arrived.insert(id).second;c(subject.arrive(id)==expected);if(expected&&arrived.size()==9U){arrived.clear();++generation;}}else{const bool expected=arrived.erase(id)==1U;c(subject.withdraw(id)==expected);}const std::vector<std::size_t> values(arrived.begin(),arrived.end());c(subject.state()==curriculum::BarrierState{generation,values});}return f?1:0;}
""",
        "phase": """#include \"task.h\"
#include <cstdint>
#include <optional>
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};const std::vector<std::size_t> durations{2U,5U,3U,1U};curriculum::TrafficPhaseController subject(durations);std::size_t phase=0U,remaining=2U;std::uint32_t rng=0xFA5E0003U;for(std::size_t step=0;step<256U;++step){rng=rng*1664525U+1013904223U;auto ticks=static_cast<std::size_t>((rng>>8U)%13U);std::vector<std::size_t> entered;auto left=ticks;while(left>=remaining){left-=remaining;phase=(phase+1U)%durations.size();remaining=durations[phase];entered.push_back(phase);}remaining-=left;c(subject.advance(ticks)==std::optional<std::vector<std::size_t>>(entered));c(subject.state()==std::optional<curriculum::PhaseState>({phase,remaining}));}return f?1:0;}
""",
        "convolution": """#include \"task.h\"
#include <cstdint>
#include <optional>
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};std::uint32_t rng=0xC04A0004U;for(std::size_t n=1;n<=17U;++n){std::vector<int> a(n),b(n);for(std::size_t i=0;i<n;++i){rng=rng*1664525U+1013904223U;a[i]=static_cast<int>(rng%19U)-9;rng=rng*1664525U+1013904223U;b[i]=static_cast<int>(rng%17U)-8;}std::vector<long long> expected(n,0);for(std::size_t out=0;out<n;++out)for(std::size_t in=0;in<n;++in){auto index=out>=in?out-in:n-(in-out);expected[out]+=static_cast<long long>(a[in])*b[index];}c(curriculum::circular_convolution(a,b)==std::optional<std::vector<long long>>(expected));}return f?1:0;}
""",
        "arcs": """#include \"task.h\"
#include <cstdint>
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};constexpr std::size_t capacity=19U;curriculum::ModularArcSet subject(capacity);std::vector<bool> occupied(capacity,false);std::uint32_t rng=0xA2C50005U;for(std::size_t step=0;step<300U;++step){rng=rng*1664525U+1013904223U;const auto start=static_cast<std::size_t>((rng>>8U)%22U);const auto length=static_cast<std::size_t>((rng>>16U)%22U);const bool expected=start<capacity&&length>=1U&&length<=capacity;const bool adding=(rng&1U)!=0U;c((adding?subject.add(start,length):subject.remove(start,length))==expected);if(expected)for(std::size_t offset=0;offset<length;++offset)occupied[(start+offset)%capacity]=adding;std::vector<curriculum::LinearArc> intervals;for(std::size_t i=0;i<capacity;){if(!occupied[i]){++i;continue;}const auto begin=i;while(i<capacity&&occupied[i])++i;intervals.push_back({begin,i});}c(subject.intervals()==intervals);for(std::size_t i=0;i<capacity;++i)c(subject.contains(i)==occupied[i]);}return f?1:0;}
""",
        "router": """#include \"task.h\"
#include <map>
#include <optional>
#include <string>
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::ClockwiseTokenRouter subject;std::map<std::uint32_t,std::string> model;std::uint32_t rng=0xC10C0006U;for(std::size_t step=0;step<300U;++step){rng=rng*1664525U+1013904223U;const auto position=(rng>>8U)%97U;const auto owner=std::string("node-")+std::to_string((rng>>16U)%13U);if(rng%3U==0U){const bool expected=model.emplace(position,owner).second;c(subject.add_token(position,owner)==expected);}else if(rng%3U==1U){const bool expected=model.erase(position)==1U;c(subject.remove_token(position)==expected);}else{std::optional<std::string> expected;if(!model.empty()){auto it=model.lower_bound(position);if(it==model.end())it=model.begin();expected=it->second;}c(subject.owner_of(position)==expected);}std::vector<curriculum::RouteToken> tokens;for(const auto& item:model)tokens.push_back({item.first,item.second});c(subject.tokens()==tokens);}return f?1:0;}
""",
        "graph": """#include \"task.h\"
#include <optional>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::FunctionalCycleIndex g({1U,2U,0U,2U,5U,4U,5U,8U,7U,8U});c(g.valid());const curriculum::CycleInfo expected[]={{0U,0U,0U,3U},{0U,0U,1U,3U},{0U,0U,2U,3U},{0U,1U,2U,3U},{1U,0U,0U,2U},{1U,0U,1U,2U},{1U,1U,1U,2U},{2U,0U,0U,2U},{2U,0U,1U,2U},{2U,1U,1U,2U}};c(g.cycle_count()==3U);for(std::size_t i=0;i<10U;++i)c(g.info(i)==std::optional<curriculum::CycleInfo>(expected[i]));c(!g.info(10U));return f?1:0;}
""",
        "tournament": """#include \"task.h\"
#include <set>
#include <string>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};for(std::size_t count=2U;count<=9U;++count){std::vector<std::string> teams;for(std::size_t i=0;i<count;++i)teams.push_back("t"+std::to_string(i));curriculum::RoundRobinPairingTable table(teams);const auto rounds=table.rounds();c(rounds.size()==(count%2U==0U?count-1U:count));std::set<std::pair<std::string,std::string>> all;for(const auto& round:rounds){std::set<std::string> used;for(const auto& match:round){c(match.first<match.second);c(used.insert(match.first).second);c(used.insert(match.second).second);c(all.insert({match.first,match.second}).second);}}c(all.size()==count*(count-1U)/2U);}return f?1:0;}
""",
        "crc": """#include \"task.h\"
#include <cstdint>
static std::uint8_t oracle(std::uint8_t reg,std::uint8_t poly,std::uint8_t byte){reg^=byte;for(unsigned bit=0;bit<8U;++bit){const bool high=(reg&128U)!=0U;reg=static_cast<std::uint8_t>(reg*2U);if(high)reg^=poly;}return reg;}int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::CrcByteRegister subject(0x1dU,0xa5U);std::uint8_t model=0xa5U;std::uint32_t rng=0xC2C80009U;for(std::size_t step=0;step<512U;++step){rng=rng*1103515245U+12345U;const auto byte=static_cast<std::uint8_t>(rng>>16U);model=oracle(model,0x1dU,byte);c(subject.update(byte));c(subject.value()==model);if(step%97U==0U){subject.reset();model=0xa5U;c(subject.value()==model);}}return f?1:0;}
""",
        "epoch": """#include \"task.h\"
#include <map>
#include <optional>
#include <vector>
int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::EpochStampedSparseTable subject(13U);std::map<std::size_t,int> model;std::uint8_t generation=1U;std::uint32_t rng=0xE90C0010U;for(std::size_t step=0;step<700U;++step){rng=rng*1664525U+1013904223U;const auto index=static_cast<std::size_t>((rng>>8U)%16U);if(rng%4U==0U){subject.clear();model.clear();++generation;if(generation==0U)generation=1U;}else{const int value=static_cast<int>(rng>>16U);const bool expected=index<13U;c(subject.set(index,value)==expected);if(expected)model[index]=value;}std::vector<curriculum::SparseEntry> entries;for(const auto& item:model)entries.push_back({item.first,item.second});c(subject.generation()==generation);c(subject.entries()==entries);for(std::size_t i=0;i<13U;++i){const auto it=model.find(i);c(subject.get(i)==(it==model.end()?std::optional<int>{}:std::optional<int>{it->second}));}}return f?1:0;}
""",
        "bloom": """#include \"task.h\"
#include <algorithm>
#include <cstdint>
#include <string>
#include <vector>
static std::size_t h1(const std::string& key){std::uint64_t h=1469598103934665603ULL;for(unsigned char b:key){h^=b;h*=1099511628211ULL;}return h%31U;}static std::size_t h2(const std::string& key){std::uint64_t h=5381U;for(unsigned char b:key)h=((h<<5U)+h)^b;return h%31U;}int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::RotatingBloomMembership subject(3U,31U);std::vector<std::vector<bool>> bits(3U,std::vector<bool>(31U,false));std::size_t current=0U;for(std::size_t step=0;step<240U;++step){const auto key=std::string("key-")+std::to_string((step*17U)%53U);if(step%7U==0U){current=(current+1U)%3U;std::fill(bits[current].begin(),bits[current].end(),false);c(subject.rotate());}else{bits[current][h1(key)]=true;bits[current][h2(key)]=true;c(subject.insert(key));}std::vector<std::vector<std::size_t>> snapshot(3U);for(std::size_t s=0;s<3U;++s)for(std::size_t b=0;b<31U;++b)if(bits[s][b])snapshot[s].push_back(b);c(subject.current_slice()==current);c(subject.active_bits()==snapshot);const auto probe=std::string("key-")+std::to_string((step*11U)%53U);bool expected=false;for(const auto& slice:bits)if(slice[h1(probe)]&&slice[h2(probe)])expected=true;c(subject.possibly_contains(probe)==expected);}return f?1:0;}
""",
        "replay": """#include \"task.h\"
#include <cstdint>
#include <limits>
static std::int64_t delta(std::uint32_t a,std::uint32_t b){const auto raw=static_cast<std::uint32_t>(a-b);if(raw==0x80000000U)return std::numeric_limits<std::int64_t>::min();return raw<0x80000000U?static_cast<std::int64_t>(raw):-static_cast<std::int64_t>(0x100000000ULL-raw);}int main(){int f=0;auto c=[&](bool ok){if(!ok)++f;};curriculum::SerialReplayWindow subject(32U);bool initialized=false;std::uint32_t highest=0U;std::uint64_t bitmap=0U;std::uint32_t rng=0x5E2A0012U;for(std::size_t step=0;step<400U;++step){rng=rng*1664525U+1013904223U;const auto serial=step%29U==0U?static_cast<std::uint32_t>(highest+40U):static_cast<std::uint32_t>(highest+static_cast<std::int32_t>((rng>>16U)%41U)-20);bool expected=false;if(!initialized){initialized=true;highest=serial;bitmap=1U;expected=true;}else{const auto d=delta(serial,highest);if(d>0){bitmap=static_cast<std::uint64_t>(d)>=32U?1U:(bitmap<<d)|1U;highest=serial;bitmap&=0xffffffffULL;expected=true;}else if(d!=0&&d!=std::numeric_limits<std::int64_t>::min()){const auto distance=static_cast<std::uint64_t>(-d);if(distance<32U&&(bitmap&(1ULL<<distance))==0U){bitmap|=1ULL<<distance;expected=true;}}}c(subject.accept(serial)==expected);c(subject.state()==curriculum::ReplayState{initialized,highest,bitmap});}return f?1:0;}
""",
    }
    return hidden_tests[kind]


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _header(spec: TaskSpec) -> str:
    if spec.kind in EXTRA_KINDS:
        return _extra_header(spec.kind)
    if spec.kind == "allocator":
        body = """#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum { class PermitSlotAllocator { public:
 explicit PermitSlotAllocator(std::size_t capacity); std::optional<std::size_t> acquire();
 bool reserve(std::size_t slot); bool release(std::size_t slot); std::size_t active() const;
 std::vector<std::size_t> occupied_slots() const;
 private: std::vector<bool> used_; std::size_t cursor_=0U; }; }
"""
    elif spec.kind == "wheel":
        body = """#pragma once
#include <cstddef>
#include <string>
#include <vector>
namespace curriculum { struct ScheduledDuty { std::string id; std::size_t ticks_remaining; };
bool operator==(const ScheduledDuty& left,const ScheduledDuty& right);
class MaintenanceDutyWheel { public:
 explicit MaintenanceDutyWheel(std::size_t slots); bool schedule(const std::string& id, std::size_t delay);
 bool cancel(const std::string& id); std::vector<std::string> advance(std::size_t ticks); std::size_t now() const;
 std::vector<ScheduledDuty> scheduled() const;
 private: std::vector<std::vector<std::string>> wheel_; std::size_t now_=0U; }; }
"""
    else:
        body = """#pragma once
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum { struct WindowBucket { std::size_t tick; long long total; };
bool operator==(const WindowBucket& left,const WindowBucket& right);
class SamplingWindowCounter { public:
 explicit SamplingWindowCounter(std::size_t width); bool record(std::size_t tick, int amount);
 std::optional<long long> sum_at(std::size_t tick) const;
 std::optional<std::vector<WindowBucket>> buckets_at(std::size_t tick) const;
 private: struct Bucket { bool occupied; std::size_t stamp; long long total; }; std::vector<Bucket> buckets_; std::optional<std::size_t> latest_; }; }
"""
    return body


def _reference(spec: TaskSpec) -> str:
    if spec.kind in EXTRA_KINDS:
        return _extra_reference(spec.kind)
    if spec.kind == "allocator":
        return """#include \"task.h\"
namespace curriculum {
PermitSlotAllocator::PermitSlotAllocator(std::size_t capacity):used_(capacity,false){}
std::optional<std::size_t> PermitSlotAllocator::acquire(){if(used_.empty())return std::nullopt;for(std::size_t offset=0;offset<used_.size();++offset){const auto slot=(cursor_+offset)%used_.size();if(!used_[slot]){used_[slot]=true;cursor_=(slot+1U)%used_.size();return slot;}}return std::nullopt;}
bool PermitSlotAllocator::reserve(std::size_t slot){if(slot>=used_.size()||used_[slot])return false;used_[slot]=true;return true;}
bool PermitSlotAllocator::release(std::size_t slot){if(slot>=used_.size()||!used_[slot])return false;used_[slot]=false;return true;}
std::size_t PermitSlotAllocator::active()const{std::size_t total=0U;for(bool value:used_)if(value)++total;return total;}
std::vector<std::size_t> PermitSlotAllocator::occupied_slots()const{std::vector<std::size_t> result;for(std::size_t slot=0;slot<used_.size();++slot)if(used_[slot])result.push_back(slot);return result;}
}
"""
    if spec.kind == "wheel":
        return """#include \"task.h\"
#include <algorithm>
namespace curriculum {
bool operator==(const ScheduledDuty& left,const ScheduledDuty& right){return left.id==right.id&&left.ticks_remaining==right.ticks_remaining;}
MaintenanceDutyWheel::MaintenanceDutyWheel(std::size_t slots):wheel_(slots){}
bool MaintenanceDutyWheel::schedule(const std::string& id,std::size_t delay){if(id.empty()||wheel_.empty()||delay==0U||delay>wheel_.size())return false;for(const auto& bucket:wheel_)for(const auto& existing:bucket)if(existing==id)return false;wheel_[(now_+delay)%wheel_.size()].push_back(id);return true;}
bool MaintenanceDutyWheel::cancel(const std::string& id){for(auto& bucket:wheel_){const auto it=std::find(bucket.begin(),bucket.end(),id);if(it!=bucket.end()){bucket.erase(it);return true;}}return false;}
std::vector<std::string> MaintenanceDutyWheel::advance(std::size_t ticks){std::vector<std::string> due;if(wheel_.empty())return due;for(std::size_t step=0;step<ticks;++step){now_=(now_+1U)%wheel_.size();auto& bucket=wheel_[now_];due.insert(due.end(),bucket.begin(),bucket.end());bucket.clear();}std::sort(due.begin(),due.end());return due;}
std::size_t MaintenanceDutyWheel::now()const{return now_;}
std::vector<ScheduledDuty> MaintenanceDutyWheel::scheduled()const{std::vector<ScheduledDuty> result;if(wheel_.empty())return result;for(std::size_t slot=0;slot<wheel_.size();++slot){auto remaining=(slot+wheel_.size()-now_)%wheel_.size();if(remaining==0U)remaining=wheel_.size();for(const auto& id:wheel_[slot])result.push_back({id,remaining});}std::sort(result.begin(),result.end(),[](const auto& left,const auto& right){return left.ticks_remaining<right.ticks_remaining||(left.ticks_remaining==right.ticks_remaining&&left.id<right.id);});return result;}
}
"""
    return """#include \"task.h\"
#include <algorithm>
namespace curriculum {
bool operator==(const WindowBucket& left,const WindowBucket& right){return left.tick==right.tick&&left.total==right.total;}
SamplingWindowCounter::SamplingWindowCounter(std::size_t width):buckets_(width,{false,0U,0}){}
bool SamplingWindowCounter::record(std::size_t tick,int amount){if(buckets_.empty()||amount<0||(latest_&&tick<*latest_))return false;auto& bucket=buckets_[tick%buckets_.size()];if(!bucket.occupied||bucket.stamp!=tick)bucket={true,tick,0};bucket.total+=amount;latest_=tick;return true;}
std::optional<std::vector<WindowBucket>> SamplingWindowCounter::buckets_at(std::size_t tick)const{if(buckets_.empty()||(latest_&&tick<*latest_))return std::nullopt;std::vector<WindowBucket> result;for(const auto& bucket:buckets_)if(bucket.occupied&&tick>=bucket.stamp&&tick-bucket.stamp<buckets_.size())result.push_back({bucket.stamp,bucket.total});std::sort(result.begin(),result.end(),[](const auto& left,const auto& right){return left.tick<right.tick;});return result;}
std::optional<long long> SamplingWindowCounter::sum_at(std::size_t tick)const{const auto snapshot=buckets_at(tick);if(!snapshot)return std::nullopt;long long total=0;for(const auto& bucket:*snapshot)total+=bucket.total;return total;}
}
"""


def _starter(spec: TaskSpec) -> str:
    if spec.kind in EXTRA_KINDS:
        return _extra_starter(spec.kind)
    if spec.kind == "allocator":
        return """#include \"task.h\"
namespace curriculum { PermitSlotAllocator::PermitSlotAllocator(std::size_t){} std::optional<std::size_t> PermitSlotAllocator::acquire(){return std::nullopt;} bool PermitSlotAllocator::reserve(std::size_t){return false;} bool PermitSlotAllocator::release(std::size_t){return false;} std::size_t PermitSlotAllocator::active()const{return 0U;} std::vector<std::size_t> PermitSlotAllocator::occupied_slots()const{return {};} }
"""
    if spec.kind == "wheel":
        return """#include \"task.h\"
namespace curriculum { bool operator==(const ScheduledDuty&,const ScheduledDuty&){return false;} MaintenanceDutyWheel::MaintenanceDutyWheel(std::size_t){} bool MaintenanceDutyWheel::schedule(const std::string&,std::size_t){return false;} bool MaintenanceDutyWheel::cancel(const std::string&){return false;} std::vector<std::string> MaintenanceDutyWheel::advance(std::size_t){return {};} std::size_t MaintenanceDutyWheel::now()const{return 0U;} std::vector<ScheduledDuty> MaintenanceDutyWheel::scheduled()const{return {};} }
"""
    return """#include \"task.h\"
namespace curriculum { bool operator==(const WindowBucket&,const WindowBucket&){return false;} SamplingWindowCounter::SamplingWindowCounter(std::size_t){} bool SamplingWindowCounter::record(std::size_t,int){return false;} std::optional<long long> SamplingWindowCounter::sum_at(std::size_t)const{return std::nullopt;} std::optional<std::vector<WindowBucket>> SamplingWindowCounter::buckets_at(std::size_t)const{return std::nullopt;} }
"""


def _test(spec: TaskSpec, hidden: bool) -> str:
    if spec.kind in EXTRA_KINDS:
        return _extra_test(spec.kind, hidden)
    if spec.kind == "allocator":
        trace = "" if not hidden else """
curriculum::PermitSlotAllocator trace(11U);std::vector<bool> occupied(11U,false);std::size_t cursor=0U;std::uint32_t state=0xA110CA7EU;
for(std::size_t step=0;step<512U;++step){state=state*1664525U+1013904223U;const auto operation=state%4U;const auto slot=static_cast<std::size_t>((state>>8U)%13U);if(operation==0U){const bool expected=slot<occupied.size()&&!occupied[slot];check(trace.reserve(slot)==expected);if(expected)occupied[slot]=true;}else if(operation==1U){const bool expected=slot<occupied.size()&&occupied[slot];check(trace.release(slot)==expected);if(expected)occupied[slot]=false;}else{std::optional<std::size_t> expected;for(std::size_t offset=0;offset<occupied.size();++offset){const auto candidate=(cursor+offset)%occupied.size();if(!occupied[candidate]){expected=candidate;occupied[candidate]=true;cursor=(candidate+1U)%occupied.size();break;}}check(trace.acquire()==expected);}std::vector<std::size_t> expected_slots;for(std::size_t index=0;index<occupied.size();++index)if(occupied[index])expected_slots.push_back(index);check(trace.active()==expected_slots.size());check(trace.occupied_slots()==expected_slots);}
"""
        return f"""#include \"task.h\"
#include <cstdint>
#include <optional>
#include <vector>
int main(){{int failures=0;auto check=[&](bool ok){{if(!ok)++failures;}};curriculum::PermitSlotAllocator zero(0U);check(!zero.acquire());check(zero.occupied_slots().empty());curriculum::PermitSlotAllocator subject(3U);check(subject.acquire()==std::optional<std::size_t>(0U));check(subject.reserve(2U));check(subject.acquire()==std::optional<std::size_t>(1U));check(!subject.acquire());check(subject.release(0U));check(subject.acquire()==std::optional<std::size_t>(0U));check(subject.active()==3U);check(subject.occupied_slots()==std::vector<std::size_t>{{0U,1U,2U}});check(!subject.reserve(9U));check(!subject.release(9U));{trace}return failures?1:0;}}
"""
    if spec.kind == "wheel":
        trace = "" if not hidden else """
curriculum::MaintenanceDutyWheel trace(7U);std::map<std::string,std::size_t> due;std::size_t absolute_now=0U;std::uint32_t state=0x71A1E001U;
for(std::size_t step=0;step<512U;++step){state=state*1664525U+1013904223U;const auto operation=state%3U;const std::string id="job-"+std::to_string((state>>8U)%13U);if(operation==0U){const std::size_t delay=(state>>16U)%9U;const bool expected=!id.empty()&&delay>=1U&&delay<=7U&&due.count(id)==0U;check(trace.schedule(id,delay)==expected);if(expected)due[id]=absolute_now+delay;}else if(operation==1U){const bool expected=due.erase(id)==1U;check(trace.cancel(id)==expected);}else{const std::size_t ticks=(state>>16U)%5U;absolute_now+=ticks;std::vector<std::string> expected;for(auto it=due.begin();it!=due.end();){if(it->second<=absolute_now){expected.push_back(it->first);it=due.erase(it);}else{++it;}}std::sort(expected.begin(),expected.end());check(trace.advance(ticks)==expected);check(trace.now()==absolute_now%7U);}std::vector<curriculum::ScheduledDuty> expected_schedule;for(const auto& entry:due)expected_schedule.push_back({entry.first,entry.second-absolute_now});std::sort(expected_schedule.begin(),expected_schedule.end(),[](const auto& left,const auto& right){return left.ticks_remaining<right.ticks_remaining||(left.ticks_remaining==right.ticks_remaining&&left.id<right.id);});check(trace.scheduled()==expected_schedule);}
"""
        return f"""#include \"task.h\"
#include <algorithm>
#include <cstdint>
#include <map>
#include <string>
#include <vector>
int main(){{int failures=0;auto check=[&](bool ok){{if(!ok)++failures;}};curriculum::MaintenanceDutyWheel zero(0U);check(!zero.schedule(\"x\",1U));check(zero.scheduled().empty());curriculum::MaintenanceDutyWheel subject(3U);check(subject.schedule(\"alpha\",1U));check(subject.schedule(\"charlie\",3U));check(subject.schedule(\"bravo\",3U));check(subject.scheduled()==std::vector<curriculum::ScheduledDuty>{{{{\"alpha\",1U}},{{\"bravo\",3U}},{{\"charlie\",3U}}}});check(!subject.schedule(\"alpha\",2U));check(subject.advance(1U)==std::vector<std::string>{{\"alpha\"}});check(subject.now()==1U);check(subject.cancel(\"charlie\"));check(!subject.cancel(\"missing\"));check(subject.advance(2U)==std::vector<std::string>{{\"bravo\"}});check(subject.scheduled().empty());check(!subject.schedule(\"\",1U));check(!subject.schedule(\"late\",4U));{trace}return failures?1:0;}}
"""
    trace = "" if not hidden else """
curriculum::SamplingWindowCounter trace(7U);std::map<std::size_t,long long> totals;std::optional<std::size_t> latest;std::uint32_t state=0xC0A17E02U;
for(std::size_t step=0;step<512U;++step){state=state*1664525U+1013904223U;if(state%3U!=0U){const std::size_t base=latest.value_or(0U);const bool stale=(state&8U)!=0U&&base>0U;const std::size_t tick=stale?base-1U:base+((state>>8U)%3U);const int amount=state%11U==0U?-1:static_cast<int>((state>>16U)%17U);const bool expected=amount>=0&&(!latest||tick>=*latest);check(trace.record(tick,amount)==expected);if(expected){totals[tick]+=amount;latest=tick;}}else{const std::size_t tick=latest?(*latest+((state>>8U)%4U)):0U;long long expected=0;for(const auto& entry:totals)if(tick>=entry.first&&tick-entry.first<7U)expected+=entry.second;check(trace.sum_at(tick)==std::optional<long long>(expected));}const std::size_t observed_tick=latest.value_or(0U);std::vector<curriculum::WindowBucket> expected_buckets;for(const auto& entry:totals)if(observed_tick>=entry.first&&observed_tick-entry.first<7U)expected_buckets.push_back({entry.first,entry.second});check(trace.buckets_at(observed_tick)==std::optional<std::vector<curriculum::WindowBucket>>(expected_buckets));}
curriculum::SamplingWindowCounter maximum(3U);const auto max_tick=std::numeric_limits<std::size_t>::max();check(maximum.record(max_tick,9));check(maximum.sum_at(max_tick)==std::optional<long long>(9));check(maximum.buckets_at(max_tick)==std::optional<std::vector<curriculum::WindowBucket>>(std::vector<curriculum::WindowBucket>{curriculum::WindowBucket{max_tick,9}}));
"""
    return f"""#include \"task.h\"
#include <cstdint>
#include <limits>
#include <map>
#include <optional>
int main(){{int failures=0;auto check=[&](bool ok){{if(!ok)++failures;}};curriculum::SamplingWindowCounter zero(0U);check(!zero.record(0U,1));check(!zero.sum_at(0U));check(!zero.buckets_at(0U));curriculum::SamplingWindowCounter subject(3U);check(subject.record(1U,2));check(subject.record(2U,3));check(subject.sum_at(2U)==std::optional<long long>(5));check(subject.buckets_at(2U)==std::optional<std::vector<curriculum::WindowBucket>>(std::vector<curriculum::WindowBucket>{{{{1U,2}},{{2U,3}}}}));check(subject.record(4U,5));check(subject.sum_at(4U)==std::optional<long long>(8));check(subject.record(4U,7));check(subject.sum_at(4U)==std::optional<long long>(15));check(subject.buckets_at(4U)==std::optional<std::vector<curriculum::WindowBucket>>(std::vector<curriculum::WindowBucket>{{{{2U,3}},{{4U,12}}}}));check(!subject.record(3U,-1));check(!subject.record(2U,1));check(!subject.sum_at(1U));check(!subject.buckets_at(1U));{trace}return failures?1:0;}}
"""


def _instructions(spec: TaskSpec) -> str:
    if spec.kind in EXTRA_KINDS:
        return _extra_instructions(spec)
    if spec.kind == "allocator":
        detail = "`acquire` scans from the current cursor through each numbered slot once and returns the first free slot, then moves the cursor after that slot. `reserve` marks one explicit free slot; `release` succeeds only for an active slot. `occupied_slots` returns every active slot in increasing numeric order without mutation. Zero capacity has no allocatable slots. For capacity 3, reserving slot 2 and then acquiring yields slot 0 and an occupied snapshot of [0, 2]."
    elif spec.kind == "wheel":
        detail = "A delay must be in 1 through the wheel size. IDs are globally unique while scheduled. `advance` moves one tick at a time, returns all work due during those ticks in lexicographic order, and removes returned work. `cancel` removes one scheduled ID. `scheduled` returns complete pending state by ticks remaining and then ID. On a three-slot wheel, jobs at delays 1 and 3 appear as [(id, 1), (id, 3)]."
    else:
        detail = "`record` accepts non-negative amounts at monotonically non-decreasing ticks. A newer tick that maps to an old modular bucket replaces that bucket's stale aggregate. `sum_at` returns the aggregate whose timestamps are less than the configured width old; it rejects a query before the latest recorded tick. `buckets_at` applies the same query rule and returns complete retained (tick, total) buckets in increasing tick order. With width 3 and records (1,2), (2,3), the tick-2 snapshot is [(1,2), (2,3)]."
    return (
        f"# Instructions\n\nImplement `{spec.class_name}`. {spec.contract} {detail} "
        "Invalid requests return `false` or no value without changing valid state. "
        "This is local candidate material, not an SFT release.\n"
    )


CMAKE = """cmake_minimum_required(VERSION 3.16)
project(cyclic_slot_systems LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_library(solution_compile_check OBJECT "${TASK_SOURCE}")
add_executable(task_visible $<TARGET_OBJECTS:solution_compile_check> task_visible_test.cpp)
add_executable(task_hidden $<TARGET_OBJECTS:solution_compile_check> .meta/task_hidden_test.cpp)
foreach(target solution_compile_check task_visible task_hidden)
 target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
 if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
 endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
"""


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() == LEGACY_ROOT.resolve():
        raise ValueError("preserved legacy circular-buffer root must not be regenerated")
    roots: list[Path] = []
    for spec in TASKS:
        root = out / spec.task_id
        header = _header(spec)
        config = {
            "authors": ["w8-biayn"],
            "attribution": "Original clean-room task authored in this repository.",
            "blurb": spec.contract,
            "files": {
                "solution": ["task.h", "task.cpp"],
                "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
                "example": [".meta/example.h", ".meta/example.cpp"],
            },
            "source": "newly-authored-in-repository",
        }
        provenance = {
            "benchmark_separation": "Different primary contract: cyclic allocation, timed work-wheel scheduling, or timestamped aggregate buckets; no FIFO reads, full-buffer write policy, or forced overwrite.",
            "curriculum_document": CURRICULUM,
            "curriculum_task_id": spec.task_id,
            "family_id": FAMILY_ID,
            "license": "repository-authored; project terms",
            "origin": "clean-room replacement after rejected circular-buffer family",
            "selected_prompt": PROMPT,
            "status": "local task artifact; not admitted SFT data",
            "requested_root_bounds": {"minimum": MIN_ROOTS, "maximum": MAX_ROOTS},
            "hard_diversity_rule": "Every counted root differs materially in primary logic and implementation, not names, constants, end selection, or policy toggles.",
            "version": 2,
        }
        docs = _instructions(spec)
        files = {".docs/introduction.md": f"# {spec.title}\n\nA clean-room cyclic-slot systems task.\n", ".docs/instructions.md": docs, ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": "[visible]\ndescription = \"public contract and primary state transition\"\n\n[hidden]\ndescription = \"boundary, wraparound, invalid-input, and representation-discriminating cases\"\n", "task.h": header, "task.cpp": _starter(spec), ".meta/example.h": header, ".meta/example.cpp": _reference(spec), "task_visible_test.cpp": _test(spec, False), ".meta/task_hidden_test.cpp": _test(spec, True), "CMakeLists.txt": CMAKE}
        for name, content in task_named_files(root, files).items():
            _write(root / name, content, force)
        roots.append(root)
    return tuple(roots)


def _fail(code: str, detail: str = "") -> None:
    raise RuntimeError(f"{code}{': ' + detail if detail else ''}")


def _sha256_bytes(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _tree_hash(root: Path) -> str:
    if not root.is_dir():
        return "missing"
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _generator_revision() -> str:
    return _sha256_bytes(Path(__file__).read_bytes())


def _reference_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for relative in (".meta/example.h", ".meta/example.cpp"):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update((root / relative).read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _normalized_tokens(content: str) -> tuple[str, ...]:
    content = re.sub(r"//.*?$|/\*.*?\*/", " ", content, flags=re.MULTILINE | re.DOTALL)
    content = re.sub(r'"(?:\\.|[^"\\])*"', '"S"', content)
    content = re.sub(r"'(?:\\.|[^'\\])*'", "'C'", content)
    content = re.sub(
        r"\b(?:0[xX][0-9A-Fa-f]+|\d+(?:\.\d+)?)(?:[UuLlFf]+)?\b",
        "N",
        content,
    )
    return tuple(re.findall(r"[A-Za-z_]\w*|==|!=|<=|>=|->|\S", content))


_SEMANTIC_STABLE_IDENTIFIERS = frozenset(
    {
        "auto", "bool", "break", "class", "const", "continue", "else",
        "false", "for", "if", "int", "long", "namespace", "optional",
        "private", "public", "return", "size_t", "std", "string", "struct",
        "true", "vector", "void", "while",
    }
)


def _semantic_tokens(content: str) -> tuple[str, ...]:
    """Remove domain nouns while retaining identifier reuse and control flow."""
    identifiers: dict[str, str] = {}
    normalized: list[str] = []
    for token in _normalized_tokens(content):
        if not re.fullmatch(r"[A-Za-z_]\w*", token):
            normalized.append(token)
            continue
        lowered = token.lower()
        if lowered in _SEMANTIC_STABLE_IDENTIFIERS:
            normalized.append(lowered)
            continue
        if lowered not in identifiers:
            identifiers[lowered] = f"ID{len(identifiers)}"
        normalized.append(identifiers[lowered])
    return tuple(normalized)


def _ngram_set(tokens: tuple[str, ...], width: int = 5) -> set[str]:
    return {
        " ".join(tokens[index : index + width])
        for index in range(max(0, len(tokens) - width + 1))
    }


def _semantic_corpus(root: Path) -> str:
    included = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "catch.hpp" or "build-" in path.parts:
            continue
        if path.suffix in {".cpp", ".h", ".md", ".json", ".toml", ".txt"}:
            included.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(included)


def _semantic_overlap(left: str, right: str) -> float:
    left_ngrams = _ngram_set(_semantic_tokens(left))
    right_ngrams = _ngram_set(_semantic_tokens(right))
    return len(left_ngrams & right_ngrams) / max(
        1, min(len(left_ngrams), len(right_ngrams))
    )


def _duplicate_failure(left: str, right: str) -> str | None:
    return "duplicate_family" if _semantic_overlap(left, right) >= 0.70 else None


def _domain_renamed_clone(content: str) -> str:
    renamed = content
    replacements = (
        ("ClockwiseTokenRouter", "RenamedPlacementCoordinator"),
        ("RouteToken", "RenamedPlacementEntry"),
        ("clockwise-token-router", "renamed-placement-coordinator"),
        ("add_token", "register_entry"),
        ("remove_token", "erase_entry"),
        ("owner_of", "label_for"),
        ("tokens_", "entries_"),
        ("tokens", "entries"),
        ("position", "coordinate"),
        ("owner", "label"),
    )
    for old, new in replacements:
        renamed = renamed.replace(old, new)
    return renamed


def _adversarial_clone_results(root: Path) -> dict[str, dict[str, object]]:
    original = _semantic_corpus(root)
    renamed = _domain_renamed_clone(original)
    constants_policy = re.sub(
        r"\b(?:0[xX][0-9A-Fa-f]+|\d+)(?:[UuLlFf]+)?\b", "997U", original
    ).replace(">=", ">", 1)
    opposite_end = original.replace(".front()", ".back()")
    clones = {
        "domain-identifier-renamed": renamed,
        "constants-or-policy-only": constants_policy,
        "opposite-end-selection": opposite_end,
    }
    results: dict[str, dict[str, object]] = {}
    for name, clone in clones.items():
        overlap = _semantic_overlap(original, clone)
        failure = _duplicate_failure(original, clone)
        if failure != "duplicate_family":
            _fail("adversarial_clone_not_rejected", f"{name}:{overlap:.3f}")
        results[name] = {"failure": failure, "overlap": round(overlap, 6)}
    return results


def _core_failure(spec: TaskSpec, source: str) -> str | None:
    code = " ".join(_normalized_tokens(source))
    normalized_markers = (" ".join(_normalized_tokens(marker)) for marker in spec.mechanism)
    if any(marker not in code for marker in normalized_markers):
        return "invariant_not_enforced"
    banned = ("std : : deque", "std : : queue", "forced write", "pop_front")
    if any(marker in code.lower() for marker in banned):
        return "invariant_not_enforced"
    forbidden_markers = (" ".join(_normalized_tokens(marker)) for marker in spec.forbidden)
    if any(marker in code for marker in forbidden_markers):
        return "invariant_not_enforced"
    return None


def _role_failure(root: Path, files: object) -> str | None:
    if not isinstance(files, dict):
        return "target_reference_mismatch"
    roles: dict[str, list[str]] = {}
    for role in ("solution", "test", "example"):
        values = files.get(role)
        if not isinstance(values, list) or not values or not all(isinstance(item, str) for item in values):
            return "target_reference_mismatch"
        roles[role] = values
    flattened = [item for values in roles.values() for item in values]
    if len(flattened) != len(set(flattened)):
        return "unsafe_path"
    for value in flattened:
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
            return "unsafe_path"
    for value in roles["solution"]:
        path = Path(value)
        if path.parts[0] in {".docs", ".meta"} or path.name == "CMakeLists.txt" or "test" in path.stem:
            return "unsafe_path"
    if len(roles["solution"]) != len(roles["example"]):
        return "target_reference_mismatch"
    if any(
        Path(solution).suffix != Path(example).suffix
        for solution, example in zip(roles["solution"], roles["example"], strict=True)
    ):
        return "target_reference_mismatch"
    return None


def _whole_format_failure(task: object, content: str) -> str | None:
    try:
        parsed = parse_whole_file_blocks(content)
    except WholeFormatError:
        return "whole_format_failed"
    return None if set(parsed) == set(task.editable_files) else "whole_format_failed"


def _prompt_contract_failure(spec: TaskSpec, instructions: str) -> str | None:
    lowered = instructions.lower()
    return None if all(term in lowered for term in spec.prompt_terms) else "prompt_contract_incomplete"


def required_marker(spec: TaskSpec) -> str:
    return spec.mechanism[0]


def _count_failure(count: int) -> str | None:
    return None if MIN_ROOTS <= count <= MAX_ROOTS else "binding_root_count_failed"


def _verify_remedy_records(out: Path) -> None:
    remedy_root = out / ".state" / "remedy"
    records = {path.stem: path for path in remedy_root.glob("*.json")}
    expected = LEGACY_TASK_IDS | {spec.task_id for spec in TASKS}
    if set(records) != expected:
        _fail("remedy_spec_incomplete", f"expected {len(expected)} records, found {len(records)}")
    for task_id, record_path in sorted(records.items()):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        specification = remedy_root / f"{task_id}.md"
        if record.get("schema_version") != "aider-task-remedy-v1" or not specification.is_file():
            _fail("remedy_spec_incomplete", task_id)
        text = specification.read_text(encoding="utf-8")
        headings = [line[2:] for line in text.splitlines() if line.startswith("# ")]
        if tuple(headings) != REMEDY_HEADINGS:
            _fail("remedy_spec_incomplete", f"heading order for {task_id}")
        if record.get("remedy_spec_hash") != _sha256_bytes(text.encode("utf-8")):
            _fail("remedy_spec_incomplete", f"stale specification hash for {task_id}")
        if task_id in LEGACY_TASK_IDS:
            if record.get("disposition") != "reject" or record.get("status") != "rejected" or record.get("benchmark_screen") != "reject":
                _fail("remedy_disposition_conflict", task_id)
        elif record.get("disposition") != "replace" or record.get("status") not in {"planned", "implemented"}:
            _fail("remedy_disposition_conflict", task_id)


def _benchmark_screen(root: Path, benchmark_ids: set[str]) -> dict[str, object]:
    missing = [task_id for task_id in sorted(benchmark_ids) if not (HOLDOUT_ROOT / task_id).is_dir()]
    if missing:
        _fail("official_holdout_content_unavailable", ",".join(missing))
    candidate_ngrams = _ngram_set(_semantic_tokens(_semantic_corpus(root)))
    strongest = {"task_id": "", "overlap": 0.0}
    for task_id in sorted(benchmark_ids):
        holdout_ngrams = _ngram_set(_semantic_tokens(_semantic_corpus(HOLDOUT_ROOT / task_id)))
        overlap = len(candidate_ngrams & holdout_ngrams) / max(
            1, min(len(candidate_ngrams), len(holdout_ngrams))
        )
        if overlap > strongest["overlap"]:
            strongest = {"task_id": task_id, "overlap": overlap}
        if overlap >= 0.80:
            _fail("benchmark_content_overlap", f"{root.name} ~ {task_id}: {overlap:.3f}")
    return strongest


def _update_replacement_records(out: Path, evidence: dict[str, dict[str, object]]) -> None:
    remedy_root = out / ".state" / "remedy"
    revision = _generator_revision()
    for spec in TASKS:
        path = remedy_root / f"{spec.task_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        current_tree_hash = _tree_hash(out / spec.task_id)
        evidence_is_stale = (
            record.get("generator_revision") != revision
            or record.get("tree_hash_after") != current_tree_hash
        )
        if evidence_is_stale:
            record.pop("oracle_evidence", None)
            record["local_status"] = "not_completed_oracle_evidence_invalidated"
        record.update(
            {
                "benchmark_screen": "pass",
                "generator_revision": revision,
                "primary_core_objective": "achieved",
                "primary_core_evidence": evidence[spec.task_id],
                "status": "implemented",
                "tree_hash_after": current_tree_hash,
            }
        )
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)


def verify_core(
    out: Path, *, require_remedy: bool = True
) -> dict[str, dict[str, object]]:
    if require_remedy:
        _verify_remedy_records(out)
    expected = {spec.task_id for spec in TASKS}
    if _count_failure(len(expected)):
        _fail("binding_root_count_failed", f"expected {MIN_ROOTS}..{MAX_ROOTS}, found {len(expected)}")
    actual = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    if actual != expected:
        _fail("generator_output_drift", f"expected {sorted(expected)}, found {sorted(actual)}")
    with tempfile.TemporaryDirectory(prefix="cyclic-slot-fresh-") as temporary:
        fresh = Path(temporary) / "family"
        build(fresh)
        for task_id in sorted(expected):
            if _tree_hash(out / task_id) != _tree_hash(fresh / task_id):
                _fail("generator_output_drift", task_id)

    benchmark_ids = set(json.loads(BENCHMARK_MANIFEST.read_text(encoding="utf-8"))["task_ids"])
    seen_kinds: set[str] = set()
    seen_api_signatures: set[str] = set()
    seen_source_signatures: set[str] = set()
    evidence: dict[str, dict[str, object]] = {}
    prompt_hashes: dict[str, str] = {}
    benchmark_results: dict[str, dict[str, object]] = {}
    semantic_profiles: dict[str, set[str]] = {}
    negative_results: dict[str, dict[str, str]] = {}
    for spec in TASKS:
        if spec.kind in seen_kinds or spec.task_id in benchmark_ids:
            _fail("duplicate_family" if spec.kind in seen_kinds else "benchmark_id_overlap", spec.task_id)
        seen_kinds.add(spec.kind)
        root = out / spec.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        expected_solution = [f"{spec.task_id}.h", f"{spec.task_id}.cpp"]
        expected_tests = ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"]
        expected_examples = [".meta/example.h", ".meta/example.cpp"]
        files = config.get("files", {})
        if files.get("solution") != expected_solution or files.get("test") != expected_tests or files.get("example") != expected_examples:
            _fail("target_reference_mismatch", spec.task_id)
        role_failure = _role_failure(root, files)
        if role_failure:
            _fail(role_failure, spec.task_id)
        unsafe_roles = json.loads(json.dumps(files))
        unsafe_roles["solution"].append("CMakeLists.txt")
        missing_reference = json.loads(json.dumps(files))
        missing_reference["example"].pop()
        misordered_reference = json.loads(json.dumps(files))
        misordered_reference["example"].reverse()
        role_fixtures = {
            "unsafe-solution-role": _role_failure(root, unsafe_roles),
            "missing-reference": _role_failure(root, missing_reference),
            "misordered-reference": _role_failure(root, misordered_reference),
        }
        if role_fixtures != {
            "unsafe-solution-role": "unsafe_path",
            "missing-reference": "target_reference_mismatch",
            "misordered-reference": "target_reference_mismatch",
        }:
            _fail("negative_fixture_failed", f"{spec.task_id}:roles:{role_fixtures}")
        task = load_task(root)
        prompt = build_prompt(task)
        instructions = (root / ".docs/instructions.md").read_text(encoding="utf-8")
        if _prompt_contract_failure(spec, instructions):
            _fail("prompt_contract_incomplete", spec.task_id)
        incomplete_instructions = re.sub(
            re.escape(spec.prompt_terms[0]),
            "omitted-contract-term",
            instructions,
            count=0,
            flags=re.IGNORECASE,
        )
        if _prompt_contract_failure(spec, incomplete_instructions) != "prompt_contract_incomplete":
            _fail("negative_fixture_failed", f"{spec.task_id}:prompt-term-omission")
        visible_contents = {
            (root / relative).read_text(encoding="utf-8")
            for relative in expected_solution
        }
        for visible_path in (*expected_solution, ".docs/introduction.md", ".docs/instructions.md"):
            visible = (root / visible_path).read_text(encoding="utf-8").rstrip()
            if visible and visible not in prompt:
                _fail("prompt_contract_incomplete", f"{spec.task_id}:{visible_path}")
        for private_path in (*expected_tests, *expected_examples, ".meta/provenance.json", "CMakeLists.txt"):
            private = (root / private_path).read_text(encoding="utf-8")
            if private not in visible_contents and private and private in prompt:
                _fail("prompt_contract_incomplete", f"{spec.task_id}:{private_path}")
            if private_path in prompt:
                _fail("prompt_contract_incomplete", f"{spec.task_id}:{private_path}")
        forbidden_contracts = ("fifo", "oldest item", "oldest value", "full-buffer", "forced overwrite", "forced write")
        if any(term in prompt.lower() for term in forbidden_contracts):
            _fail("benchmark_content_overlap", spec.task_id)
        examples = load_example_files_from_config(root)
        valid_whole = build_assistant_response(task, examples)
        if _whole_format_failure(task, valid_whole):
            _fail("whole_format_failed", f"valid reference rejected for {spec.task_id}")
        parsed_whole = parse_whole_file_blocks(valid_whole)
        first_editable = task.editable_files[0]
        omitted_whole = "\n\n".join(
            f"{filename}\n```\n{parsed_whole[filename].rstrip()}\n```"
            for filename in task.editable_files[1:]
        )
        whole_fixtures = {
            "omitted-file": _whole_format_failure(task, omitted_whole),
            "extra-file": _whole_format_failure(
                task, valid_whole + "\n\nunexpected.cpp\n```\nint unexpected = 0;\n```"
            ),
            "prose-prefix": _whole_format_failure(task, "Here are the files.\n" + valid_whole),
            "duplicate-file": _whole_format_failure(
                task,
                valid_whole
                + f"\n\n{first_editable}\n```\n{parsed_whole[first_editable].rstrip()}\n```",
            ),
        }
        if any(result != "whole_format_failed" for result in whole_fixtures.values()):
            _fail("negative_fixture_failed", f"{spec.task_id}:whole:{whole_fixtures}")
        source = (root / ".meta/example.cpp").read_text(encoding="utf-8")
        failure = _core_failure(spec, source)
        if failure:
            _fail(failure, spec.task_id)
        if _core_failure(spec, source.replace(required_marker(spec), "removed_primary_state")) is None:
            _fail("invariant_not_enforced", f"negative fixture accepted for {spec.task_id}")
        if _core_failure(spec, source + "\n#include <deque>\nstd::deque<int> authoritative;") is None:
            _fail("invariant_not_enforced", f"deque fixture accepted for {spec.task_id}")
        false_substitute = source + f"\nint {spec.forbidden[0]} = 0;\n"
        if _core_failure(spec, false_substitute) is None:
            _fail("invariant_not_enforced", f"topic substitute accepted for {spec.task_id}")
        for other in TASKS:
            if other.kind != spec.kind and _core_failure(spec, _reference(other)) is None:
                _fail("duplicate_family", f"{other.task_id} accepted as {spec.task_id}")
        api_signature = _sha256_bytes(" ".join(_semantic_tokens(_header(spec))).encode("utf-8"))
        source_signature = _sha256_bytes(" ".join(_semantic_tokens(source)).encode("utf-8"))
        if api_signature in seen_api_signatures or source_signature in seen_source_signatures:
            _fail("duplicate_family", spec.task_id)
        seen_api_signatures.add(api_signature)
        seen_source_signatures.add(source_signature)
        semantic_profiles[spec.task_id] = _ngram_set(
            _semantic_tokens(_semantic_corpus(root))
        )
        prompt_hashes[spec.task_id] = _sha256_bytes(prompt.encode("utf-8"))
        benchmark_results[spec.task_id] = _benchmark_screen(root, benchmark_ids)
        negative_results[spec.task_id] = {
            **role_fixtures,
            "prompt-term-omission": "prompt_contract_incomplete",
            **whole_fixtures,
            "required-state-removed": "invariant_not_enforced",
            "authoritative-deque": "invariant_not_enforced",
            "topic-specific-substitute": "invariant_not_enforced",
            "cross-root-reference": "duplicate_family_or_invariant_not_enforced",
        }
        evidence[spec.task_id] = {
            "api_signature": api_signature,
            "mechanism": spec.kind,
            "mechanism_markers": list(spec.mechanism),
            "negative_fixtures": sorted(negative_results[spec.task_id]),
            "source_signature": source_signature,
            "trace_seed": spec.seed,
        }
    pairwise_semantic_overlap: list[dict[str, object]] = []
    ordered_ids = sorted(semantic_profiles)
    for left_index, left_id in enumerate(ordered_ids):
        for right_id in ordered_ids[left_index + 1 :]:
            left = semantic_profiles[left_id]
            right = semantic_profiles[right_id]
            overlap = len(left & right) / max(1, min(len(left), len(right)))
            pairwise_semantic_overlap.append(
                {"left": left_id, "right": right_id, "overlap": round(overlap, 6)}
            )
            if overlap >= 0.70:
                _fail("duplicate_family", f"{left_id} ~ {right_id}: {overlap:.3f}")
    screen = {
        "schema_version": "cyclic-slot-family-screen-v4",
        "status": "pass",
        "benchmark_manifest": str(BENCHMARK_MANIFEST),
        "benchmark_semantic_review": benchmark_results,
        "benchmark_whole_slug": "pass",
        "duplicate_family": "pass: 15 roots compared over actual emitted docs, APIs, references, and tests",
        "negative_fixture_results": negative_results,
        "adversarial_clone_results": _adversarial_clone_results(
            out / "clockwise-token-router"
        ),
        "normalizer": NORMALIZER,
        "pairwise_semantic_overlap": pairwise_semantic_overlap,
        "prompt_boundary": "pass",
        "prompt_hashes": prompt_hashes,
        "root_count": len(TASKS),
        "user_count_bound": {"minimum": MIN_ROOTS, "maximum": MAX_ROOTS},
        "count_negative_fixtures": {
            "below_minimum": _count_failure(MIN_ROOTS - 1),
            "at_minimum": _count_failure(MIN_ROOTS),
            "at_maximum": _count_failure(MAX_ROOTS),
            "above_maximum": _count_failure(MAX_ROOTS + 1),
        },
    }
    _write(out / ".state" / "family-screen.json", json.dumps(screen, indent=2, sort_keys=True) + "\n", True)
    manifest = {
        "schema_version": "cyclic-slot-generator-manifest-v1",
        "family_id": FAMILY_ID,
        "generator_path": GENERATOR_PATH,
        "generator_revision": _generator_revision(),
        "task_ids": ordered_ids,
        "task_tree_hashes": {task_id: _tree_hash(out / task_id) for task_id in ordered_ids},
    }
    _write(out / ".state" / "generator-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)
    if require_remedy:
        _update_replacement_records(out, evidence)
    return evidence


def verify(out: Path) -> dict[str, dict[str, int]]:
    cmake = shutil.which("cmake")
    compiler = shutil.which("c++")
    if not cmake or not compiler:
        raise RuntimeError("verification requires cmake and c++; designated locked runtime is not configured")
    counts: dict[str, dict[str, int]] = {}
    for spec in TASKS:
        root = out / spec.task_id
        counts[spec.task_id] = {}
        with tempfile.TemporaryDirectory(prefix="cyclic-slot-systems-") as temporary:
            copied = Path(temporary) / root.name
            shutil.copytree(root, copied)
            for name, flags in (
                ("normal", []),
                ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"]),
            ):
                build_dir = copied / f"build-{name}"
                commands = (
                    [cmake, "-G", "Unix Makefiles", "-S", str(copied), "-B", str(build_dir), f"-DCMAKE_CXX_COMPILER={compiler}", f"-DTASK_SOURCE={copied / '.meta/example.cpp'}", *flags],
                    [cmake, "--build", str(build_dir), "--parallel", "2"],
                    ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
                )
                result = None
                for command in commands:
                    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if result.returncode:
                        _fail(f"reference_{name}_failed", f"{spec.task_id}\n{result.stdout}\n{result.stderr}")
                assert result is not None
                match = re.search(r"100% tests passed, 0 tests failed out of (\d+)", result.stdout)
                if not match or int(match.group(1)) <= 0:
                    _fail("zero_tests", f"{spec.task_id}:{name}")
                counts[spec.task_id][name] = int(match.group(1))
        if counts[spec.task_id]["normal"] != counts[spec.task_id]["sanitizer"]:
            _fail("sanitizer_test_count_mismatch", spec.task_id)
    receipt = {
        "schema_version": "cyclic-slot-host-oracle-v1",
        "status": "host_oracle_passed_locked_runtime_not_designated",
        "compiler": compiler,
        "cmake": cmake,
        "counts": counts,
        "designated_locked_runtime": False,
    }
    _write(out / ".state" / "host-oracle-receipt.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    return counts


def import_diagnostic_receipt(out: Path, receipt_path: Path) -> dict[str, object]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != "cyclic-slot-direct-docker-v1":
        _fail("direct_receipt_invalid", "schema")
    if receipt.get("image") != DIAGNOSTIC_IMAGE or receipt.get("image_id") != DIAGNOSTIC_IMAGE_ID:
        _fail("direct_receipt_invalid", "image identity")
    if receipt.get("network") != "none" or receipt.get("designated_locked_runtime") is not False:
        _fail("direct_receipt_invalid", "sandbox classification")
    archive_path = Path(str(receipt.get("archive_path", "")))
    if not archive_path.is_file() or _sha256_bytes(archive_path.read_bytes()) != receipt.get("archive_hash"):
        _fail("grader_mount_hash_mismatch", "archive")
    tasks = receipt.get("tasks")
    if not isinstance(tasks, dict) or set(tasks) != {spec.task_id for spec in TASKS}:
        _fail("direct_receipt_invalid", "task inventory")
    for spec in TASKS:
        task = tasks[spec.task_id]
        if task.get("tree_hash") != _tree_hash(out / spec.task_id):
            _fail("grader_mount_hash_mismatch", spec.task_id)
        normal = task.get("normal")
        sanitizer = task.get("sanitizer")
        if normal != 2 or sanitizer != 2 or normal != sanitizer:
            _fail("sanitizer_test_count_mismatch", spec.task_id)
    imported = {
        **receipt,
        "evidence_class": "diagnostic_container_only",
        "imported_by_generator": _generator_revision(),
        "local_status": "container_oracle_passed_locked_runtime_not_designated",
        "owner_validation": "pass",
    }
    target = out / ".state" / "diagnostic-oracle-receipt.json"
    _write(target, json.dumps(imported, indent=2, sort_keys=True) + "\n", True)
    for spec in TASKS:
        record_path = out / ".state" / "remedy" / f"{spec.task_id}.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["local_status"] = imported["local_status"]
        record["oracle_evidence"] = {
            "asan_ubsan": {"result": "passed", "test_count": 2},
            "compiler": receipt["compiler"],
            "cmake": receipt["cmake"],
            "evidence_class": imported["evidence_class"],
            "image": receipt["image"],
            "image_id": receipt["image_id"],
            "normal": {"result": "passed", "test_count": 2},
            "tree_hash": tasks[spec.task_id]["tree_hash"],
        }
        _write(record_path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)
    return imported


def import_docker_sanity_receipt(out: Path, receipt_path: Path) -> dict[str, object]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != "cyclic-slot-docker-sanity-v1":
        _fail("docker_sanity_receipt_invalid", "schema")
    if receipt.get("image") != SANITY_IMAGE or receipt.get("image_id") != SANITY_IMAGE_ID:
        _fail("docker_sanity_receipt_invalid", "image identity")
    if (
        receipt.get("network") != "none"
        or receipt.get("evidence_class") != "docker_sanity"
        or receipt.get("locked_oracle") is not False
    ):
        _fail("docker_sanity_receipt_invalid", "evidence classification")
    if receipt.get("generator_revision") != _generator_revision():
        _fail("docker_sanity_receipt_invalid", "generator revision")
    tasks = receipt.get("tasks")
    expected_ids = {spec.task_id for spec in TASKS}
    if not isinstance(tasks, dict) or set(tasks) != expected_ids:
        _fail("docker_sanity_receipt_invalid", "task inventory")
    for spec in TASKS:
        root = out / spec.task_id
        task = tasks[spec.task_id]
        if task.get("tree_hash") != _tree_hash(root):
            _fail("grader_mount_hash_mismatch", spec.task_id)
        if task.get("reference_hash") != _reference_hash(root):
            _fail("grader_mount_hash_mismatch", f"{spec.task_id}:reference")
        normal = task.get("normal")
        sanitizer = task.get("asan_ubsan")
        if normal != 2 or sanitizer != 2 or normal != sanitizer:
            _fail("sanitizer_test_count_mismatch", spec.task_id)
    imported = {
        **receipt,
        "host_container_mount_hash_match": True,
        "owner_validation": "pass",
        "status": "pass",
    }
    target = out / ".state" / "docker-sanity.json"
    serialized = json.dumps(imported, indent=2, sort_keys=True) + "\n"
    _write(target, serialized, True)
    receipt_hash = _sha256_bytes(serialized.encode("utf-8"))
    for spec in TASKS:
        record_path = out / ".state" / "remedy" / f"{spec.task_id}.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["local_status"] = "local_family_verified"
        record["oracle_evidence"] = {
            "asan_ubsan": {"result": "passed", "test_count": 2},
            "compiler": receipt["compiler"],
            "compiler_sha256": receipt["compiler_sha256"],
            "cmake": receipt["cmake"],
            "evidence_class": "docker_sanity",
            "image": SANITY_IMAGE,
            "image_id": SANITY_IMAGE_ID,
            "locked_oracle": False,
            "network": "none",
            "normal": {"result": "passed", "test_count": 2},
            "reference_hash": tasks[spec.task_id]["reference_hash"],
            "tree_hash": tasks[spec.task_id]["tree_hash"],
        }
        record["docker_sanity_receipt"] = {
            "path": str(target),
            "sha256": receipt_hash,
        }
        _write(record_path, json.dumps(record, indent=2, sort_keys=True) + "\n", True)
    return imported


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--import-diagnostic-receipt", type=Path)
    parser.add_argument("--import-docker-sanity-receipt", type=Path)
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    if args.import_diagnostic_receipt:
        import_diagnostic_receipt(args.out, args.import_diagnostic_receipt)
    if args.import_docker_sanity_receipt:
        import_docker_sanity_receipt(args.out, args.import_docker_sanity_receipt)
    print(f"Wrote {len(roots)} cyclic-slot-system tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
