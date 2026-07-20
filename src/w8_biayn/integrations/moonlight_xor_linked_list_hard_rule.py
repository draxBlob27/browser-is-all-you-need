"""Hard-rule inputs for the independently counted XOR-chain roots."""

from __future__ import annotations

from dataclasses import dataclass


REJECTED = {
    "xor-monotonic-sample-window": "policy_only_bounded_window_sibling",
    "xor-escalation-ticket-chain": "stable_priority_band_sibling",
    "xor-consist-block-editor": "range_reverse_detach_sibling",
}


@dataclass(frozen=True)
class Payload:
    value: str | None = None
    aux: str | None = None
    metric: str | None = None
    needs_cursor: bool = False
    needs_edge: bool = False


PAYLOADS = {
    "xor-card-game-turns": Payload("int turns_left", needs_cursor=True),
    "xor-branching-chat-journal": Payload(needs_cursor=True),
    "xor-delivery-range-ledger": Payload(),
    "xor-bounded-event-window": Payload("int event_code", "std::uint64_t sequence"),
    "xor-revision-checkpoint-chain": Payload(metric="long long delta"),
    "xor-weighted-playback-ring": Payload("int weight", metric="long long credit"),
    "xor-block-offset-chain": Payload(aux="std::uint64_t byte_count"),
    "xor-dependency-ready-chain": Payload("int dependency_id", "std::uint64_t completed"),
    "xor-precedence-pick-chain": Payload("int prerequisite_id", "std::uint64_t completed"),
    "xor-accessible-tour-cursor": Payload("int access_mask", needs_cursor=True),
    "xor-pinned-notification-feed": Payload("int pinned", "std::uint64_t read"),
    "xor-packet-gap-index": Payload(aux="std::uint64_t first", metric="long long last"),
    "xor-neighbor-departure-line": Payload(),
    "xor-priority-print-spool": Payload("int priority"),
    "xor-band-preset-ring": Payload("int band", needs_cursor=True),
    "xor-recipe-dependency-chain": Payload(aux="std::uint64_t completed"),
    "xor-waypoint-distance-chain": Payload("int x", metric="long long y", needs_edge=True),
}


NEGATIVE_MUTATIONS = {
    "xor-card-game-turns": ("if(--arena_[x].value==0)", "if(arena_[x].value--==0)"),
    "xor-branching-chat-journal": ("while(n){", "if(n){"),
    "xor-delivery-range-ledger": ("if(!found)return false;if(f==l)return true;", "if(found)return false;if(f==l)return true;"),
    "xor-bounded-event-window": ("while(size_>capacity_)", "while(size_>capacity_+1U)"),
    "xor-revision-checkpoint-chain": ("total_-=arena_[x].metric", "total_+=arena_[x].metric"),
    "xor-weighted-playback-ring": ("arena_[best].metric-=total_weight_", "arena_[best].metric+=total_weight_"),
    "xor-block-offset-chain": ("if(offset-base<arena_[c].aux)", "if(offset-base<=arena_[c].aux)"),
    "xor-dependency-ready-chain": ("if(arena_[c].aux==0){SlotId dep", "if(arena_[c].aux!=0){SlotId dep"),
    "xor-precedence-pick-chain": ("if(d&&arena_[d].aux==0)return false;", "if(d&&arena_[d].aux!=0)return false;"),
    "xor-accessible-tour-cursor": (
        "if(static_cast<unsigned>(arena_[c].value)&allowed_){current_=c;return arena_[c].id;}",
        "if((static_cast<unsigned>(arena_[c].value)&allowed_)==0U){current_=c;return arena_[c].id;}",
    ),
    "xor-pinned-notification-feed": ("if(pinned){for(SlotId", "if(!pinned){for(SlotId"),
    "xor-packet-gap-index": ("+1U<r.first", "+1U<=r.first"),
    "xor-neighbor-departure-line": ("insert_after(b,p);", "insert_after(b,a);"),
    "xor-priority-print-spool": ("if(arena_[c].value<priority)break;", "if(arena_[c].value>priority)break;"),
    "xor-band-preset-ring": ("x=direction>0?", "x=direction<0?"),
    "xor-recipe-dependency-chain": ("if(ready)return arena_[c].id;", "if(!ready)return arena_[c].id;"),
    "xor-waypoint-distance-chain": ("distance_+=fresh-old", "distance_+=old-fresh"),
}


TRACE_TESTS = {
    "xor-card-game-turns": r"""
CardGameTurns x;std::vector<int> model;REQUIRE(x.order()==model);
auto a=x.seat(1,2);REQUIRE(a);model={1};REQUIRE(x.order()==model);
auto b=x.seat(2,1,a);REQUIRE(b);model={1,2};REQUIRE(x.order()==model);
REQUIRE(x.grant(a,1));REQUIRE(x.order()==model);
REQUIRE(x.advance(1)==2);REQUIRE(x.order()==model);
REQUIRE(x.reverse());REQUIRE(x.order()==model);
REQUIRE(x.consume_turn()==2);model={1};REQUIRE(x.order()==model);
REQUIRE(x.advance(0)==1);REQUIRE(x.order()==model);
""",
    "xor-branching-chat-journal": r"""
BranchingChatJournal x;std::vector<int> model;REQUIRE(x.timeline()==model);
REQUIRE(x.post(1));model={1};REQUIRE(x.timeline()==model);
REQUIRE(x.post(2));model={1,2};REQUIRE(x.timeline()==model);
REQUIRE(x.post(3));model={1,2,3};REQUIRE(x.timeline()==model);
REQUIRE(x.post(4));model={1,2,3,4};REQUIRE(x.timeline()==model);
REQUIRE(x.back(2)==2);REQUIRE(x.timeline()==model);
REQUIRE(x.post(5));model={1,2,5};REQUIRE(x.timeline()==model);
REQUIRE_FALSE(x.forward(1));REQUIRE(x.timeline()==model);
REQUIRE(x.erase_current());model={1,2};REQUIRE(x.timeline()==model);
""",
    "xor-delivery-range-ledger": r"""
DeliveryRangeLedger x;std::vector<int> model;REQUIRE(x.route()==model);
auto a=x.append(1);REQUIRE(a);model={1};REQUIRE(x.route()==model);
auto b=x.append(2);REQUIRE(b);model={1,2};REQUIRE(x.route()==model);
auto c=x.append(3);REQUIRE(c);model={1,2,3};REQUIRE(x.route()==model);
REQUIRE(x.reverse_range(b,c));model={1,3,2};REQUIRE(x.route()==model);
REQUIRE(x.detach_range(c,b)==std::vector<int>{3,2});model={1};REQUIRE(x.route()==model);
REQUIRE(x.insert_block_after(a,{4,5}));model={1,4,5};REQUIRE(x.route()==model);
""",
    "xor-bounded-event-window": r"""
BoundedEventWindow x(2);std::vector<std::uint64_t> model;REQUIRE(x.sequences()==model);
REQUIRE(x.append(10,1));model={10};REQUIRE(x.sequences()==model);
REQUIRE(x.append(20,2));model={10,20};REQUIRE(x.sequences()==model);
REQUIRE(x.append(30,3));model={20,30};REQUIRE(x.sequences()==model);
REQUIRE(x.code(20)==2);REQUIRE(x.sequences()==model);
REQUIRE(x.trim_before(30));model={30};REQUIRE(x.sequences()==model);
""",
    "xor-revision-checkpoint-chain": r"""
RevisionCheckpointChain x;std::vector<int> model;REQUIRE(x.revisions()==model);REQUIRE(x.total()==0);
REQUIRE(x.commit(1,4));model={1};REQUIRE(x.revisions()==model);REQUIRE(x.total()==4);
REQUIRE(x.checkpoint(7));REQUIRE(x.revisions()==model);
REQUIRE(x.commit(2,3));model={1,2};REQUIRE(x.revisions()==model);REQUIRE(x.total()==7);
REQUIRE(x.commit(3,-1));model={1,2,3};REQUIRE(x.revisions()==model);REQUIRE(x.total()==6);
REQUIRE(x.squash_last_two(4));model={1,4};REQUIRE(x.revisions()==model);REQUIRE(x.total()==6);
REQUIRE(x.rollback(7));model={1};REQUIRE(x.revisions()==model);REQUIRE(x.total()==4);
""",
    "xor-weighted-playback-ring": r"""
WeightedPlaybackRing x;std::vector<int> model;REQUIRE(x.physical_order()==model);
auto a=x.add(1,1);REQUIRE(a);model={1};REQUIRE(x.physical_order()==model);
auto b=x.add(2,2,a);REQUIRE(b);model={1,2};REQUIRE(x.physical_order()==model);
REQUIRE(x.set_weight(a,3));REQUIRE(x.physical_order()==model);
REQUIRE(x.next()==1);REQUIRE(x.physical_order()==model);
REQUIRE(x.remove(b));model={1};REQUIRE(x.physical_order()==model);
""",
    "xor-block-offset-chain": r"""
BlockOffsetChain x;std::vector<int> model;
auto observe=[&x](){std::vector<int> out;for(std::uint64_t offset=0;offset<x.size_bytes();++offset){auto id=x.block_at(offset);REQUIRE(id);out.push_back(*id);}return out;};
REQUIRE(observe()==model);
auto a=x.append(1,8);REQUIRE(a);model=std::vector<int>(8,1);REQUIRE(observe()==model);
auto right=x.split(a,3,2);REQUIRE(right);model={1,1,1,2,2,2,2,2};REQUIRE(observe()==model);
REQUIRE(x.merge_with_next(a));model=std::vector<int>(8,1);REQUIRE(observe()==model);
REQUIRE_FALSE(x.block_at(8));REQUIRE(observe()==model);
""",
    "xor-dependency-ready-chain": r"""
DependencyReadyChain x;std::vector<int> model;REQUIRE(x.pending()==model);
auto a=x.schedule(1,0);REQUIRE(a);model={1};REQUIRE(x.pending()==model);
auto b=x.schedule(2,1,a);REQUIRE(b);model={1,2};REQUIRE(x.pending()==model);
REQUIRE(x.next_ready()==1);REQUIRE(x.pending()==model);
REQUIRE(x.mark_complete(a));model={2};REQUIRE(x.pending()==model);
REQUIRE(x.next_ready()==2);REQUIRE(x.pending()==model);
REQUIRE(x.cancel(b));model={};REQUIRE(x.pending()==model);
REQUIRE(x.cancel(a));REQUIRE(x.pending()==model);
""",
    "xor-precedence-pick-chain": r"""
PrecedencePickChain x;std::vector<int> model;REQUIRE(x.feasible_order()==model);
auto a=x.add(1,0);REQUIRE(a);model={1};REQUIRE(x.feasible_order()==model);
auto b=x.add(2,1);REQUIRE(b);model={1,2};REQUIRE(x.feasible_order()==model);
auto c=x.add(3,0);REQUIRE(c);model={1,2,3};REQUIRE(x.feasible_order()==model);
REQUIRE(x.relocate_after(c,a));model={1,3,2};REQUIRE(x.feasible_order()==model);
REQUIRE(x.complete(a));REQUIRE(x.feasible_order()==model);
REQUIRE(x.next_pick()==3);REQUIRE(x.feasible_order()==model);
""",
    "xor-accessible-tour-cursor": r"""
AccessibleTourCursor x;std::vector<int> model;REQUIRE(x.route()==model);
auto a=x.append(1,1);REQUIRE(a);model={1};REQUIRE(x.route()==model);
auto b=x.append(2,2);REQUIRE(b);model={1,2};REQUIRE(x.route()==model);
REQUIRE(x.set_allowed(2));REQUIRE(x.route()==model);
REQUIRE(x.next_accessible()==2);REQUIRE(x.route()==model);
REQUIRE(x.previous_accessible()==std::nullopt);REQUIRE(x.route()==model);
REQUIRE(x.erase(b));model={1};REQUIRE(x.route()==model);
""",
    "xor-pinned-notification-feed": r"""
PinnedNotificationFeed x;std::vector<int> model;REQUIRE(x.feed()==model);
auto a=x.push(1,false);REQUIRE(a);model={1};REQUIRE(x.feed()==model);
auto b=x.push(2,true);REQUIRE(b);model={2,1};REQUIRE(x.feed()==model);
REQUIRE(x.set_pinned(a,true));model={2,1};REQUIRE(x.feed()==model);
REQUIRE(x.next_unread()==2);REQUIRE(x.feed()==model);
REQUIRE(x.mark_read(b));REQUIRE(x.feed()==model);
REQUIRE(x.next_unread()==1);REQUIRE(x.feed()==model);
""",
    "xor-packet-gap-index": r"""
PacketGapIndex x;std::vector<std::pair<std::uint32_t,std::uint32_t>> model;REQUIRE(x.spans()==model);
REQUIRE(x.insert(10,12));model={{10,12}};REQUIRE(x.spans()==model);
REQUIRE(x.insert(14,15));model={{10,12},{14,15}};REQUIRE(x.spans()==model);
REQUIRE(x.insert(13,13));model={{10,15}};REQUIRE(x.spans()==model);
REQUIRE(x.first_gap(10)==16);REQUIRE(x.spans()==model);
REQUIRE(x.erase(12,13));model={{10,11},{14,15}};REQUIRE(x.spans()==model);
""",
    "xor-neighbor-departure-line": r"""
NeighborDepartureLine x;std::vector<int> model;REQUIRE(x.line()==model);
auto a=x.arrive(1);REQUIRE(a);model={1};REQUIRE(x.line()==model);
auto b=x.arrive(2);REQUIRE(b);model={1,2};REQUIRE(x.line()==model);
auto c=x.arrive(3);REQUIRE(c);model={1,2,3};REQUIRE(x.line()==model);
REQUIRE(x.swap_adjacent(a,b));model={2,1,3};REQUIRE(x.line()==model);
auto receipt=x.depart(a);REQUIRE(receipt);REQUIRE(receipt->before==2);REQUIRE(receipt->after==3);model={2,3};REQUIRE(x.line()==model);
""",
    "xor-priority-print-spool": r"""
PriorityPrintSpool x;std::vector<int> model;REQUIRE(x.order()==model);
auto a=x.submit(1,1);REQUIRE(a);model={1};REQUIRE(x.order()==model);
auto b=x.submit(2,3);REQUIRE(b);model={2,1};REQUIRE(x.order()==model);
REQUIRE(x.reprioritize(a,4));model={1,2};REQUIRE(x.order()==model);
REQUIRE(x.dispatch()==1);model={2};REQUIRE(x.order()==model);
REQUIRE(x.cancel(b));model={};REQUIRE(x.order()==model);
""",
    "xor-band-preset-ring": r"""
BandPresetRing x;std::vector<int> model;REQUIRE(x.presets()==model);
auto a=x.add(1,1);REQUIRE(a);model={1};REQUIRE(x.presets()==model);
auto b=x.add(2,2,a);REQUIRE(b);model={1,2};REQUIRE(x.presets()==model);
auto c=x.add(3,4,b);REQUIRE(c);model={1,2,3};REQUIRE(x.presets()==model);
REQUIRE(x.tune(a));REQUIRE(x.presets()==model);
REQUIRE(x.seek(1,6)==2);REQUIRE(x.presets()==model);
REQUIRE(x.remove(b));model={1,3};REQUIRE(x.presets()==model);
""",
    "xor-recipe-dependency-chain": r"""
RecipeDependencyChain x;std::vector<int> model;REQUIRE(x.order()==model);
auto a=x.add(1,{});REQUIRE(a);model={1};REQUIRE(x.order()==model);
auto b=x.add(2,{1});REQUIRE(b);model={1,2};REQUIRE(x.order()==model);
auto c=x.add(3,{1});REQUIRE(c);model={1,2,3};REQUIRE(x.order()==model);
REQUIRE(x.move_after(c,a));model={1,3,2};REQUIRE(x.order()==model);
REQUIRE(x.complete(a));REQUIRE(x.order()==model);
REQUIRE(x.next_ready()==3);REQUIRE(x.order()==model);
REQUIRE(x.complete(c));REQUIRE(x.order()==model);
""",
    "xor-waypoint-distance-chain": r"""
WaypointDistanceChain x;std::vector<int> model;REQUIRE(x.route()==model);REQUIRE(x.distance()==0);
auto a=x.append(1,0,0);REQUIRE(a);model={1};REQUIRE(x.route()==model);REQUIRE(x.distance()==0);
auto b=x.append(2,3,0);REQUIRE(b);model={1,2};REQUIRE(x.route()==model);REQUIRE(x.distance()==3);
auto c=x.append(3,3,4);REQUIRE(c);model={1,2,3};REQUIRE(x.route()==model);REQUIRE(x.distance()==7);
REQUIRE(x.move(b,5,0));REQUIRE(x.route()==model);REQUIRE(x.distance()==11);
REQUIRE(x.erase(b));model={1,3};REQUIRE(x.route()==model);REQUIRE(x.distance()==7);
""",
}


if set(PAYLOADS) != set(TRACE_TESTS) or set(PAYLOADS) != set(NEGATIVE_MUTATIONS):
    raise RuntimeError("hard-rule case registries must cover the same counted roots")
