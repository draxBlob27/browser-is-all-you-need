"""Executable case inventory for the 90-root time/offset/meeting expansion family."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TransformSpec:
    key: str
    slug: str
    title: str
    input_name: str
    fields: str
    objective: str
    boundary: str
    mechanism: str
    reference: str
    negative_old: str
    negative_new: str
    visible_input: str
    hidden_input: str


@dataclass(frozen=True)
class ReducerSpec:
    key: str
    slug: str
    title: str
    report_name: str
    report_fields: str
    parameters: str
    arguments: str
    objective: str
    boundary: str
    mechanism: str
    reference: str
    negative_old: str
    negative_new: str
    assertion: str


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    title: str
    transform: TransformSpec
    reducer: ReducerSpec
    function_name: str
    lineage_id: str


TRANSFORMS = (
    TransformSpec(
        "wrap", "overnight", "Overnight windows", "OvernightWindow",
        "int id; int start_minute; int end_minute; int load;",
        "unwrap each nonempty daily window across at most one midnight",
        "minutes are in 0..1439, equal endpoints are invalid, and a lower end wraps once",
        "single-wrap half-open interval normalization",
        """for(const auto& item:input){if(item.id<=0||!ids.insert(item.id).second||!valid_clock(item.start_minute)||!valid_clock(item.end_minute)||item.start_minute==item.end_minute||item.load<=0)return false;int end=item.end_minute;if(end<item.start_minute)end+=1440;spans.push_back({item.id,item.start_minute,end,item.load});}""",
        "if(end<item.start_minute)end+=1440;", "if(end<item.start_minute)end+=720;",
        "{{1,1380,60,2},{2,40,100,1},{3,90,180,3},{4,180,240,1}}",
        "{{1,1320,30,1},{2,30,90,2},{3,80,140,1},{4,140,200,2}}",
    ),
    TransformSpec(
        "offset", "fixed-offset", "Fixed-offset windows", "OffsetWindow",
        "int id; int start_local; int end_local; int utc_offset; int load;",
        "convert fixed-offset local windows to a two-day UTC minute axis",
        "offsets are whole minutes in -840..840 and local windows may wrap once",
        "signed fixed-offset conversion with floor normalization",
        """for(const auto& item:input){if(item.id<=0||!ids.insert(item.id).second||!valid_clock(item.start_local)||!valid_clock(item.end_local)||item.start_local==item.end_local||item.utc_offset<-840||item.utc_offset>840||item.load<=0)return false;int duration=item.end_local-item.start_local;if(duration<=0)duration+=1440;int start=item.start_local-item.utc_offset;while(start<0)start+=1440;while(start>=1440)start-=1440;spans.push_back({item.id,start,start+duration,item.load});}""",
        "int start=item.start_local-item.utc_offset;", "int start=item.start_local+item.utc_offset;",
        "{{1,120,240,60,2},{2,180,300,120,1},{3,1380,60,-60,3},{4,300,360,0,1}}",
        "{{1,30,120,120,1},{2,1380,30,-120,2},{3,240,360,180,1},{4,420,480,0,2}}",
    ),
    TransformSpec(
        "day", "day-projected", "Day-projected windows", "DayWindow",
        "int id; int start_minute; int end_minute; int day_index; int load;",
        "project local windows onto explicit day zero or day one positions",
        "day_index is 0 or 1 and a wrapping window may end on the following day within the horizon",
        "explicit civil-day projection",
        """for(const auto& item:input){if(item.id<=0||!ids.insert(item.id).second||!valid_clock(item.start_minute)||!valid_clock(item.end_minute)||item.start_minute==item.end_minute||(item.day_index!=0&&item.day_index!=1)||item.load<=0)return false;int start=item.start_minute+item.day_index*1440;int end=item.end_minute+item.day_index*1440;if(end<start)end+=1440;if(end>2880)return false;spans.push_back({item.id,start,end,item.load});}""",
        "int start=item.start_minute+item.day_index*1440;", "int start=item.start_minute+item.day_index*60;",
        "{{1,60,180,0,2},{2,120,240,0,1},{3,30,150,1,3},{4,150,210,1,1}}",
        "{{1,1320,60,0,1},{2,30,120,1,2},{3,180,300,1,1},{4,300,360,1,2}}",
    ),
    TransformSpec(
        "repeat", "recurring", "Recurring windows", "RecurringWindow",
        "int id; int start_minute; int duration; int period; int repeats; int load;",
        "expand bounded fixed-period meeting occurrences without truncating the final occurrence",
        "duration, period, and repeats are positive; every expanded end must stay within two days",
        "bounded arithmetic recurrence expansion",
        """for(const auto& item:input){if(item.id<=0||!ids.insert(item.id).second||item.start_minute<0||item.start_minute>=2880||item.duration<=0||item.period<=0||item.repeats<=0||item.repeats>8||item.load<=0)return false;for(int repeat=0;repeat<item.repeats;++repeat){int start=item.start_minute+repeat*item.period;int end=start+item.duration;if(end>2880)return false;spans.push_back({item.id*10+repeat,start,end,item.load});}}""",
        "repeat*item.period", "repeat*(item.period+1)",
        "{{1,60,90,120,3,2},{2,100,40,180,2,1},{3,300,60,240,2,3}}",
        "{{1,1320,120,180,3,1},{2,1380,60,120,4,2},{3,1500,30,300,2,1}}",
    ),
    TransformSpec(
        "clip", "horizon-clipped", "Horizon-clipped windows", "ClippedWindow",
        "int id; int start_minute; int end_minute; int clip_start; int clip_end; int load;",
        "intersect every proposal with its own required observation horizon",
        "all endpoints lie on 0..2880, source and clip ranges are nonempty, and empty intersections are omitted",
        "per-record half-open interval clipping",
        """for(const auto& item:input){if(item.id<=0||!ids.insert(item.id).second||item.start_minute<0||item.start_minute>=item.end_minute||item.end_minute>2880||item.clip_start<0||item.clip_start>=item.clip_end||item.clip_end>2880||item.load<=0)return false;int start=std::max(item.start_minute,item.clip_start);int end=std::min(item.end_minute,item.clip_end);if(start<end)spans.push_back({item.id,start,end,item.load});}""",
        "std::max(item.start_minute,item.clip_start)", "std::min(item.start_minute,item.clip_start)",
        "{{1,50,220,100,200,2},{2,150,300,120,260,1},{3,280,400,300,360,3},{4,500,550,400,520,1}}",
        "{{1,1300,1600,1380,1500,1},{2,1400,1700,1450,1650,2},{3,1800,1900,1700,1850,1}}",
    ),
    TransformSpec(
        "buffer", "buffer-expanded", "Buffer-expanded windows", "BufferedWindow",
        "int id; int start_minute; int end_minute; int before; int after; int load;",
        "expand meetings by asymmetric setup and travel buffers before analysis",
        "base ranges are nonempty on 0..2880 and buffers are nonnegative without crossing the horizon",
        "asymmetric interval dilation",
        """for(const auto& item:input){if(item.id<=0||!ids.insert(item.id).second||item.start_minute<0||item.start_minute>=item.end_minute||item.end_minute>2880||item.before<0||item.after<0||item.start_minute<item.before||item.end_minute>2880-item.after||item.load<=0)return false;int start=item.start_minute-item.before;int end=item.end_minute+item.after;spans.push_back({item.id,start,end,item.load});}""",
        "item.start_minute-item.before", "item.start_minute+item.before",
        "{{1,100,180,20,30,2},{2,190,250,10,20,1},{3,300,360,40,10,3},{4,400,440,0,0,1}}",
        "{{1,1320,1440,60,30,1},{2,1470,1560,30,60,2},{3,1700,1760,20,20,1}}",
    ),
    TransformSpec(
        "participant", "participant-normalized", "Participant-normalized windows", "ParticipantWindow",
        "int window_id; int participant_id; int start_local; int end_local; int utc_offset; int priority;",
        "normalize multiple windows per participant to UTC and retain their nonempty common intersection",
        "window IDs are unique, participant IDs and priorities are positive, offsets are bounded, and every participant must use one priority",
        "grouped fixed-offset intersection by participant",
        """struct Common{int start;int end;int priority;};std::map<int,Common> common;for(const auto& item:input){if(item.window_id<=0||!ids.insert(item.window_id).second||item.participant_id<=0||!valid_clock(item.start_local)||!valid_clock(item.end_local)||item.start_local==item.end_local||item.utc_offset<-840||item.utc_offset>840||item.priority<=0)return false;int duration=item.end_local-item.start_local;if(duration<=0)duration+=1440;int start=item.start_local-item.utc_offset;while(start<0)start+=1440;while(start>=1440)start-=1440;auto found=common.find(item.participant_id);if(found==common.end())common[item.participant_id]={start,start+duration,item.priority};else{if(found->second.priority!=item.priority)return false;found->second.start=std::max(found->second.start,start);found->second.end=std::min(found->second.end,start+duration);}}for(const auto& entry:common)if(entry.second.start<entry.second.end)spans.push_back({entry.first,entry.second.start,entry.second.end,entry.second.priority});""",
        "found->second.start=std::max(found->second.start,start);", "found->second.start=std::min(found->second.start,start);",
        "{{1,10,120,240,60,2},{2,10,180,300,120,2},{3,20,60,180,0,3},{4,20,90,210,0,3},{5,30,1380,60,-60,1}}",
        "{{1,10,30,180,120,1},{2,10,90,240,180,1},{3,20,1380,30,-120,2},{4,20,60,180,0,2},{5,30,240,360,180,1}}",
    ),
    TransformSpec(
        "capacity", "capacity-weighted", "Capacity-weighted windows", "CapacityWindow",
        "int room_id; int start_minute; int end_minute; int capacity;",
        "treat each room interval as capacity units rather than one undifferentiated window",
        "room IDs are unique, capacity is positive, and ranges are nonempty on the two-day axis",
        "capacity-carrying interval projection",
        """for(const auto& item:input){if(item.room_id<=0||!ids.insert(item.room_id).second||item.start_minute<0||item.start_minute>=item.end_minute||item.end_minute>2880||item.capacity<=0)return false;spans.push_back({item.room_id,item.start_minute,item.end_minute,item.capacity});}""",
        "spans.push_back({item.room_id,item.start_minute,item.end_minute,item.capacity});", "spans.push_back({item.room_id,item.start_minute,item.end_minute,1});",
        "{{1,60,180,3},{2,120,240,2},{3,200,300,4},{4,300,360,1}}",
        "{{1,1320,1500,2},{2,1380,1560,3},{3,1500,1620,1},{4,1700,1760,4}}",
    ),
    TransformSpec(
        "precedence", "precedence-shifted", "Precedence-shifted windows", "DependentWindow",
        "int id; int start_minute; int end_minute; int predecessor_id; int lag; int load;",
        "shift each meeting after an earlier listed predecessor and its required handoff lag",
        "predecessors must already exist or be zero, lags are nonnegative, and shifted ends stay within two days",
        "single-pass precedence lower-bound propagation",
        """std::map<int,int> finishes;for(const auto& item:input){if(item.id<=0||!ids.insert(item.id).second||item.start_minute<0||item.start_minute>=item.end_minute||item.end_minute>2880||item.predecessor_id<0||item.lag<0||item.load<=0)return false;int start=item.start_minute;int duration=item.end_minute-item.start_minute;if(item.predecessor_id!=0){auto found=finishes.find(item.predecessor_id);if(found==finishes.end())return false;start=std::max(start,found->second+item.lag);}if(start+duration>2880)return false;finishes[item.id]=start+duration;spans.push_back({item.id,start,start+duration,item.load});}""",
        "std::max(start,found->second+item.lag)", "std::min(start,found->second+item.lag)",
        "{{1,60,150,0,0,2},{2,100,180,1,30,1},{3,170,230,2,20,3},{4,200,260,1,0,1}}",
        "{{1,1320,1410,0,0,1},{2,1380,1470,1,30,2},{3,1450,1510,2,15,1}}",
    ),
    TransformSpec(
        "blackout", "blackout-subtracted", "Blackout-subtracted windows", "BlackoutWindow",
        "int id; int start_minute; int end_minute; int blackout_start; int blackout_end; int load;",
        "subtract one optional internal blackout from every meeting window, preserving both surviving pieces",
        "ranges use 0..2880; an empty blackout is allowed, otherwise it must be contained in the source range",
        "interval subtraction with possible two-piece output",
        """for(const auto& item:input){if(item.id<=0||!ids.insert(item.id).second||item.start_minute<0||item.start_minute>=item.end_minute||item.end_minute>2880||item.blackout_start<item.start_minute||item.blackout_end>item.end_minute||item.blackout_start>item.blackout_end||item.load<=0)return false;if(item.blackout_start==item.blackout_end){spans.push_back({item.id,item.start_minute,item.end_minute,item.load});continue;}if(item.start_minute<item.blackout_start)spans.push_back({item.id*10,item.start_minute,item.blackout_start,item.load});if(item.blackout_end<item.end_minute)spans.push_back({item.id*10+1,item.blackout_end,item.end_minute,item.load});}""",
        "item.blackout_end<item.end_minute", "item.blackout_end<=item.end_minute",
        "{{1,60,220,100,140,2},{2,120,280,180,200,1},{3,300,380,300,300,3},{4,400,460,430,460,1}}",
        "{{1,1320,1530,1380,1440,1},{2,1400,1600,1500,1540,2},{3,1700,1760,1700,1760,1}}",
    ),
)


REDUCERS = (
    ReducerSpec(
        "union", "merged-coverage", "Merged coverage", "CoverageReport",
        "bool valid=false; int covered_minutes=0; int segment_count=0;", "", "",
        "merge touching or overlapping transformed spans and report their union",
        "empty input is valid with zero coverage; touching spans form one segment",
        "ordered interval-union scan",
        """std::sort(spans.begin(),spans.end(),[](const Span&a,const Span&b){return a.start<b.start||(a.start==b.start&&a.end<b.end);});int left=-1,right=-1;for(const auto&s:spans){if(left<0||s.start>right){if(left>=0){out.covered_minutes+=right-left;++out.segment_count;}left=s.start;right=s.end;}else right=std::max(right,s.end);}if(left>=0){out.covered_minutes+=right-left;++out.segment_count;}out.valid=true;""",
        "if(left>=0){out.covered_minutes+=right-left;++out.segment_count;}out.valid=true;", "if(left>=0){out.covered_minutes+=right-left-1;++out.segment_count;}out.valid=true;", "out.valid&&out.covered_minutes=={metric}&&out.segment_count=={aux}",
    ),
    ReducerSpec(
        "peak", "peak-load", "Peak load", "PeakReport",
        "bool valid=false; int peak_load=0; int first_minute=-1;", "", "",
        "find maximum simultaneous transformed load and its earliest minute",
        "end events precede start events at a half-open touching boundary",
        "weighted event sweep with end-before-start ties",
        """std::vector<std::pair<int,int>> events;for(const auto&s:spans){events.push_back({s.start,s.load});events.push_back({s.end,-s.load});}std::sort(events.begin(),events.end(),[](auto a,auto b){return a.first<b.first||(a.first==b.first&&a.second<b.second);});int load=0;for(const auto&e:events){load+=e.second;if(load>out.peak_load){out.peak_load=load;out.first_minute=e.first;}}out.valid=true;""",
        "out.peak_load=load;", "out.peak_load=load-1;", "out.valid&&out.peak_load=={metric}&&out.first_minute=={aux}",
    ),
    ReducerSpec(
        "exact", "exact-coverage", "Exact coverage", "ExactReport",
        "bool valid=false; int exact_minutes=0; int exact_load=0;", ", int exact_load", ", exact_load",
        "measure minutes whose transformed load equals a caller-selected positive value",
        "an invalid exact load rejects the complete query",
        "difference-array exact-load accumulation",
        """if(exact_load<=0){return out;}std::array<int,2881> diff{};for(const auto&s:spans){diff[static_cast<std::size_t>(s.start)]+=s.load;diff[static_cast<std::size_t>(s.end)]-=s.load;}int load=0;for(int minute=0;minute<2880;++minute){load+=diff[static_cast<std::size_t>(minute)];if(load==exact_load)++out.exact_minutes;}out.exact_load=exact_load;out.valid=true;""",
        "++out.exact_minutes", "out.exact_minutes+=2", "out.valid&&out.exact_minutes=={metric}&&out.exact_load=={aux}",
    ),
    ReducerSpec(
        "slot", "earliest-quorum-slot", "Earliest quorum slot", "SlotReport",
        "bool valid=false; bool found=false; int start_minute=-1; int end_minute=-1;", ", int required_load, int duration", ", required_load, duration",
        "return the earliest continuous slot meeting a required transformed load",
        "required load and duration are positive; no solution is valid with found=false",
        "difference-array threshold run selection",
        """if(required_load<=0||duration<=0){return out;}std::array<int,2881> diff{};for(const auto&s:spans){diff[static_cast<std::size_t>(s.start)]+=s.load;diff[static_cast<std::size_t>(s.end)]-=s.load;}int load=0,run=-1;for(int minute=0;minute<2880;++minute){load+=diff[static_cast<std::size_t>(minute)];if(load>=required_load){if(run<0)run=minute;if(minute+1-run>=duration){out.found=true;out.start_minute=run;out.end_minute=run+duration;break;}}else run=-1;}out.valid=true;""",
        "out.end_minute=run+duration;", "out.end_minute=run+duration-1;", "out.valid&&out.found=={found}&&out.start_minute=={metric}&&out.end_minute=={aux}",
    ),
    ReducerSpec(
        "gap", "longest-gap", "Longest gap", "GapReport",
        "bool valid=false; int start_minute=-1; int end_minute=-1; int minutes=0;", ", int horizon_start, int horizon_end", ", horizon_start, horizon_end",
        "find the earliest longest uncovered gap inside a caller horizon",
        "the horizon is nonempty inside 0..2880; spans are clipped before union",
        "clipped union-complement maximum scan",
        """if(horizon_start<0||horizon_start>=horizon_end||horizon_end>2880){return out;}std::sort(spans.begin(),spans.end(),[](const Span&a,const Span&b){return a.start<b.start||(a.start==b.start&&a.end<b.end);});int cursor=horizon_start;for(const auto&s:spans){int left=std::max(horizon_start,s.start),right=std::min(horizon_end,s.end);if(left>=right)continue;if(left>cursor&&left-cursor>out.minutes){out.start_minute=cursor;out.end_minute=left;out.minutes=left-cursor;}cursor=std::max(cursor,right);}if(horizon_end-cursor>out.minutes){out.start_minute=cursor;out.end_minute=horizon_end;out.minutes=horizon_end-cursor;}out.valid=true;""",
        "out.valid=true;", "++out.minutes;out.valid=true;", "out.valid&&out.start_minute=={metric}&&out.end_minute=={aux}&&out.minutes=={extra}",
    ),
    ReducerSpec(
        "rooms", "room-demand", "Room demand", "RoomReport",
        "bool valid=false; int rooms=0; std::vector<int> room_by_sorted_span;", "", "",
        "assign transformed spans to the smallest reusable room and report minimum demand",
        "touching spans reuse a room and output follows start/end/ID order",
        "two-heap stable interval partitioning",
        """std::sort(spans.begin(),spans.end(),[](const Span&a,const Span&b){return a.start<b.start||(a.start==b.start&&(a.end<b.end||(a.end==b.end&&a.id<b.id)));});using Busy=std::pair<int,int>;std::priority_queue<Busy,std::vector<Busy>,std::greater<Busy>> busy;std::priority_queue<int,std::vector<int>,std::greater<int>> free_rooms;int next_room=0;for(const auto&s:spans){while(!busy.empty()&&busy.top().first<=s.start){free_rooms.push(busy.top().second);busy.pop();}int room;if(free_rooms.empty())room=next_room++;else{room=free_rooms.top();free_rooms.pop();}out.room_by_sorted_span.push_back(room);busy.push({s.end,room});}out.rooms=next_room;out.valid=true;""",
        "out.rooms=next_room;", "out.rooms=next_room+1;", "out.valid&&out.rooms=={metric}&&out.room_by_sorted_span=={vector}",
    ),
    ReducerSpec(
        "weighted", "weighted-exposure", "Weighted exposure", "WeightReport",
        "bool valid=false; long long weighted_minutes=0; int peak_weight=0;", "", "",
        "integrate transformed load over time and report the maximum concurrent load",
        "empty input has zero exposure and every product uses signed 64-bit accumulation",
        "weighted event-area sweep",
        """std::vector<std::pair<int,int>> events;for(const auto&s:spans){events.push_back({s.start,s.load});events.push_back({s.end,-s.load});}std::sort(events.begin(),events.end(),[](auto a,auto b){return a.first<b.first||(a.first==b.first&&a.second<b.second);});int load=0,previous=0;for(const auto&e:events){out.weighted_minutes+=static_cast<long long>(e.first-previous)*load;load+=e.second;out.peak_weight=std::max(out.peak_weight,load);previous=e.first;}out.valid=true;""",
        "static_cast<long long>(e.first-previous)*load", "static_cast<long long>(e.first-previous)", "out.valid&&out.weighted_minutes=={long_metric}&&out.peak_weight=={aux}",
    ),
    ReducerSpec(
        "order", "stable-order", "Stable order", "OrderReport",
        "bool valid=false; std::vector<int> ids;", "", "",
        "return transformed identities ordered by start, then end, then identity",
        "recurrence and blackout transformations may produce derived identities that remain distinct",
        "stable three-key ordering",
        """std::sort(spans.begin(),spans.end(),[](const Span&a,const Span&b){return a.start<b.start||(a.start==b.start&&(a.end<b.end||(a.end==b.end&&a.id<b.id)));});for(const auto&s:spans){out.ids.push_back(s.id);}out.valid=true;""",
        "a.start<b.start", "a.start>b.start", "out.valid&&out.ids=={vector}",
    ),
    ReducerSpec(
        "conflicts", "conflict-audit", "Conflict audit", "ConflictReport",
        "bool valid=false; int count=0; std::vector<std::pair<int,int>> pairs;", "", "",
        "enumerate every pair of transformed identities with positive half-open overlap",
        "touching is not a conflict and pairs are sorted by smaller then larger identity",
        "quadratic interval-intersection audit",
        """for(std::size_t i=0;i<spans.size();++i){for(std::size_t j=i+1;j<spans.size();++j){if(std::max(spans[i].start,spans[j].start)<std::min(spans[i].end,spans[j].end)){int a=std::min(spans[i].id,spans[j].id),b=std::max(spans[i].id,spans[j].id);out.pairs.push_back({a,b});}}}std::sort(out.pairs.begin(),out.pairs.end());out.pairs.erase(std::unique(out.pairs.begin(),out.pairs.end()),out.pairs.end());out.count=static_cast<int>(out.pairs.size());out.valid=true;""",
        "<std::min(spans[i].end,spans[j].end)", ">std::min(spans[i].end,spans[j].end)", "out.valid&&out.count=={metric}&&out.pairs=={pairs}",
    ),
)


def _function_name(transform: TransformSpec, reducer: ReducerSpec) -> str:
    return f"analyze_{transform.key}_{reducer.key}"


TASKS = tuple(
    TaskSpec(
        task_id=f"{transform.slug}-{reducer.slug}",
        title=f"{transform.title}: {reducer.title}",
        transform=transform,
        reducer=reducer,
        function_name=_function_name(transform, reducer),
        lineage_id=f"cross-midnight-offset-meeting/{transform.key}/{reducer.key}/v1",
    )
    for transform in TRANSFORMS
    for reducer in REDUCERS
)


assert len(TASKS) == 90
assert len({task.task_id for task in TASKS}) == 90
assert len({task.lineage_id for task in TASKS}) == 90
