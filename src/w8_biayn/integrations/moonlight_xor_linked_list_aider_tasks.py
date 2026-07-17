"""Materialize safe slot-index XOR linked-list curriculum tasks."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from typing import Sequence

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/xor-linked-list")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_XOR_LINKED_LIST_CURRICULUM.md"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str; class_name: str; noun: str; add: str; remove: str; move: str; contract: str; circular: bool = False


_ROWS = (
    ("xor-embedded-playlist", "EmbeddedPlaylist", "track", "add_track", "remove_track", "move_track_after", "Track IDs are stable handles; adding with no anchor appends."),
    ("xor-device-event-log", "DeviceEventLog", "event", "append_event", "prune_event", "relocate_event_after", "Events retain insertion order unless explicitly relocated."),
    ("xor-firmware-task-chain", "FirmwareTaskChain", "task", "schedule_task", "cancel_task", "reschedule_task_after", "Scheduling after a handle places a task immediately after that task."),
    ("xor-sensor-sample-history", "SensorSampleHistory", "sample", "record_sample", "discard_sample", "place_sample_after", "Samples can be inspected in either historical direction."),
    ("xor-train-car-store", "TrainCarStore", "car", "attach_car", "detach_car", "relocate_car_after", "Cars are identified by unique positive car IDs."),
    ("xor-radio-station-list", "RadioStationList", "preset", "add_preset", "remove_preset", "seek_preset_after", "Preset order is explicit and never sorted by ID."),
    ("xor-print-job-store", "PrintJobStore", "job", "submit_job", "cancel_job", "rotate_job_after", "A rotation changes position without changing a job handle."),
    ("xor-packet-reassembly-order", "PacketReassemblyOrder", "packet", "retain_packet", "discard_packet", "insert_packet_after", "Packet IDs are retained in the requested reassembly order."),
    ("xor-recipe-step-chain", "RecipeStepChain", "step", "add_step", "remove_step", "reorder_step_after", "Step order is semantic and duplicate IDs are rejected."),
    ("xor-route-waypoint-store", "RouteWaypointStore", "waypoint", "add_waypoint", "remove_waypoint", "place_waypoint_after", "Waypoints support predecessor and successor inspection."),
    ("xor-chat-message-history", "ChatMessageHistory", "message", "append_message", "delete_message", "page_message_after", "Messages retain bidirectional paging order."),
    ("xor-inventory-pick-chain", "InventoryPickChain", "pick", "add_pick", "cancel_pick", "relocate_pick_after", "Cancelled picks become stale and cannot be moved again."),
    ("xor-card-game-turns", "CardGameTurns", "player", "join_player", "leave_player", "move_player_after", "Turn navigation wraps at both ends when the table is nonempty.", True),
    ("xor-document-revisions", "DocumentRevisions", "revision", "insert_revision", "discard_revision", "move_revision_after", "Revision handles remain valid until their revision is discarded."),
    ("xor-parking-queue", "ParkingQueue", "vehicle", "arrive_vehicle", "depart_vehicle", "relocate_vehicle_after", "Vehicle order models the physical parking queue."),
    ("xor-notification-history", "NotificationHistory", "notification", "add_notification", "dismiss_notification", "move_notification_after", "Dismissed notifications are rejected by all later navigation calls."),
    ("xor-support-ticket-order", "SupportTicketOrder", "ticket", "open_ticket", "close_ticket", "reposition_ticket_after", "Priority repositioning is caller-directed rather than numeric sorting."),
    ("xor-file-block-chain", "FileBlockChain", "block", "link_block", "unlink_block", "seek_block_after", "Logical blocks form a mutable file-order chain."),
    ("xor-museum-tour", "MuseumTour", "waypoint", "add_waypoint", "remove_waypoint", "move_waypoint_after", "Tour edits preserve stable waypoint handles."),
    ("xor-delivery-stop-chain", "DeliveryStopChain", "stop", "add_stop", "remove_stop", "reverse_stop_after", "The named reposition operation moves one stop after a retained anchor."),
)
TASKS = tuple(TaskSpec(*row) for row in _ROWS)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text() != content and not force: raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)


def _header(s: TaskSpec) -> str:
    return f'''#pragma once
#include <cstddef>
#include <cstdint>
#include <optional>
#include <vector>
namespace curriculum {{ class {s.class_name} {{ public:
  using Handle=std::uint64_t; Handle {s.add}(int value, Handle after=0); bool {s.remove}(Handle); bool {s.move}(Handle, Handle after);
  std::vector<int> forward_values() const; std::vector<int> reverse_values() const; std::optional<int> successor_value(Handle) const; std::optional<int> predecessor_value(Handle) const; std::size_t size() const;
 private: struct Node {{ int value=0; std::uint32_t link=0,generation=0; bool live=false; }}; bool valid(Handle) const; std::uint32_t slot_of(Handle) const; Handle handle_of(std::uint32_t) const; std::uint32_t allocate(int); bool locate(std::uint32_t,std::uint32_t&,std::uint32_t&) const; void insert_after_slot(std::uint32_t,std::uint32_t); void unlink_slot(std::uint32_t,std::uint32_t,std::uint32_t); std::vector<Node> arena_{{Node{{}}}}; std::uint32_t head_=0,tail_=0; std::size_t size_=0;
}}; }}
'''


def _reference(s: TaskSpec) -> str:
    tail = "return head_ ? std::optional<int>(arena_[head_].value) : std::nullopt;" if s.circular else "return std::nullopt;"
    head = "return tail_ ? std::optional<int>(arena_[tail_].value) : std::nullopt;" if s.circular else "return std::nullopt;"
    return f'''#include "task.h"
namespace curriculum {{
bool {s.class_name}::valid(Handle h) const {{ auto x=slot_of(h); return h&&x<arena_.size()&&arena_[x].live&&arena_[x].generation==static_cast<std::uint32_t>(h>>32U); }} std::uint32_t {s.class_name}::slot_of(Handle h) const {{ return static_cast<std::uint32_t>(h); }} {s.class_name}::Handle {s.class_name}::handle_of(std::uint32_t x) const {{ return (static_cast<Handle>(arena_[x].generation)<<32U)|x; }}
std::uint32_t {s.class_name}::allocate(int value) {{ for(std::uint32_t x=1;x<arena_.size();++x) if(!arena_[x].live) {{ auto& n=arena_[x]; n={{value,0,n.generation+1U,true}}; if(!n.generation)++n.generation; return x; }} arena_.push_back(Node{{value,0,1,true}}); return static_cast<std::uint32_t>(arena_.size()-1U); }}
bool {s.class_name}::locate(std::uint32_t wanted,std::uint32_t& p,std::uint32_t& n) const {{ p=0; for(std::uint32_t c=head_;c;c=n) {{ n=p^arena_[c].link; if(c==wanted)return true; p=c; }} n=0; return false; }}
void {s.class_name}::insert_after_slot(std::uint32_t x,std::uint32_t after) {{ std::uint32_t next=head_; if(after) {{ std::uint32_t p=0; locate(after,p,next); }} arena_[x].link=after^next; if(after)arena_[after].link^=next^x;else head_=x; if(next)arena_[next].link^=after^x;else tail_=x; ++size_; }} void {s.class_name}::unlink_slot(std::uint32_t x,std::uint32_t p,std::uint32_t n) {{ if(p)arena_[p].link^=x^n;else head_=n; if(n)arena_[n].link^=x^p;else tail_=p;arena_[x].link=0;--size_; }}
{s.class_name}::Handle {s.class_name}::{s.add}(int v,Handle after) {{ if(after&&!valid(after))return 0; auto x=allocate(v);insert_after_slot(x,after?slot_of(after):tail_);return handle_of(x); }} bool {s.class_name}::{s.remove}(Handle h) {{ if(!valid(h))return false;std::uint32_t p=0,n=0;locate(slot_of(h),p,n);unlink_slot(slot_of(h),p,n);arena_[slot_of(h)].live=false;return true; }} bool {s.class_name}::{s.move}(Handle h,Handle after) {{ if(!valid(h)||!valid(after)||h==after)return false;std::uint32_t p=0,n=0;locate(slot_of(h),p,n);unlink_slot(slot_of(h),p,n);insert_after_slot(slot_of(h),slot_of(after));return true; }}
std::vector<int> {s.class_name}::forward_values() const {{ std::vector<int> out;for(std::uint32_t p=0,c=head_,n=0;c;p=c,c=n){{out.push_back(arena_[c].value);n=p^arena_[c].link;}}return out; }} std::vector<int> {s.class_name}::reverse_values() const {{ std::vector<int> out;for(std::uint32_t n=0,c=tail_,p=0;c;n=c,c=p){{out.push_back(arena_[c].value);p=n^arena_[c].link;}}return out; }}
std::optional<int> {s.class_name}::successor_value(Handle h) const {{if(!valid(h))return std::nullopt;std::uint32_t p=0,n=0;locate(slot_of(h),p,n);if(n)return arena_[n].value;{tail}}} std::optional<int> {s.class_name}::predecessor_value(Handle h) const {{if(!valid(h))return std::nullopt;std::uint32_t p=0,n=0;locate(slot_of(h),p,n);if(p)return arena_[p].value;{head}}} std::size_t {s.class_name}::size() const{{return size_;}}
}}
'''


def _starter(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{ bool {s.class_name}::valid(Handle)const{{return false;}}std::uint32_t {s.class_name}::slot_of(Handle)const{{return 0;}}{s.class_name}::Handle {s.class_name}::handle_of(std::uint32_t)const{{return 0;}}std::uint32_t {s.class_name}::allocate(int){{return 0;}}bool {s.class_name}::locate(std::uint32_t,std::uint32_t&,std::uint32_t&)const{{return false;}}void {s.class_name}::insert_after_slot(std::uint32_t,std::uint32_t){{}}void {s.class_name}::unlink_slot(std::uint32_t,std::uint32_t,std::uint32_t){{}}{s.class_name}::Handle {s.class_name}::{s.add}(int,Handle){{return 0;}}bool {s.class_name}::{s.remove}(Handle){{return false;}}bool {s.class_name}::{s.move}(Handle,Handle){{return false;}}std::vector<int> {s.class_name}::forward_values()const{{return {{}};}}std::vector<int> {s.class_name}::reverse_values()const{{return {{}};}}std::optional<int> {s.class_name}::successor_value(Handle)const{{return std::nullopt;}}std::optional<int> {s.class_name}::predecessor_value(Handle)const{{return std::nullopt;}}std::size_t {s.class_name}::size()const{{return 0;}} }}
'''


def _test(s: TaskSpec, hidden: bool) -> str:
    last = "std::optional<int>(10)" if s.circular else "std::nullopt"
    first = "std::optional<int>(30)" if s.circular else "std::nullopt"
    trace = ""
    if hidden: trace = f'''\n  curriculum::{s.class_name} trace;std::vector<int> oracle;std::vector<curriculum::{s.class_name}::Handle> hs;for(int i=1;i<=180;++i){{if(i%4==0&&!hs.empty()){{auto h=hs.front();hs.erase(hs.begin());check(trace.{s.remove}(h));oracle.erase(oracle.begin());check(!trace.{s.remove}(h));}}else{{auto h=trace.{s.add}(i);check(h!=0);hs.push_back(h);oracle.push_back(i);}}check(trace.forward_values()==oracle);std::vector<int> rev(oracle.rbegin(),oracle.rend());check(trace.reverse_values()==rev);}}'''
    return f'''#include "task.h"
#include <optional>
#include <vector>
int main(){{int failures=0;auto check=[&](bool x){{if(!x)++failures;}};curriculum::{s.class_name} task;auto a=task.{s.add}(10),b=task.{s.add}(20,a),c=task.{s.add}(30,b);check(a&&b&&c);check(task.forward_values()==std::vector<int>{{10,20,30}});check(task.reverse_values()==std::vector<int>{{30,20,10}});check(task.predecessor_value(a)=={first});check(task.successor_value(c)=={last});check(task.{s.move}(c,a));check(task.forward_values()==std::vector<int>{{10,30,20}});check(task.{s.remove}(b));check(!task.{s.remove}(b));auto replacement=task.{s.add}(40);check(replacement&&replacement!=b);check(task.reverse_values()==std::vector<int>{{40,30,10}});{trace}return failures?1:0;}}
'''


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(xor_linked_list_curriculum LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(target task_visible task_hidden)
 target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
 target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
'''


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    roots=[]
    for s in TASKS:
        root=out/s.task_id; header=_header(s)
        config={"authors":["w8-biayn"],"blurb":s.contract,"files":{"solution":["task.h","task.cpp"],"test":["task_visible_test.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}}
        provenance={"curriculum_document":CURRICULUM,"curriculum_task_id":s.task_id,"origin":"newly-authored in-repository diagnostic task","status":"local task artifact; not admitted SFT data","version":1,"benchmark_separation":"A domain-specific safe slot-index XOR API independently authored from the official Aider Polyglot linked-list benchmark.","representation":"Links XOR stable nonzero arena slots only; raw pointer XOR and pointer/integer address encoding are forbidden."}
        files={".docs/introduction.md":f"# {s.class_name}\n\nA newly authored local XOR-linked-list diagnostic for {s.noun} workflow.\n",".docs/instructions.md":f"# Instructions\n\nImplement `{s.class_name}`. `{s.add}` returns a nonzero generation-bound handle, or zero for a stale anchor. `{s.remove}` and `{s.move}` reject invalid or stale handles without mutation. {s.contract} `forward_values()` and `reverse_values()` must be exact reverses. Use stable integer arena slots only: each live link is `previous_slot XOR next_slot`; do not XOR native addresses or use pointer/integer casts. {'Neighbor inspection wraps at either end.' if s.circular else 'Endpoint neighbor inspection returns no value.'}\n",".meta/config.json":json.dumps(config,indent=2,sort_keys=True)+"\n",".meta/provenance.json":json.dumps(provenance,indent=2,sort_keys=True)+"\n",".meta/tests.toml":"[visible]\ndescription = \"domain API, handle validity, forward/reverse order, and endpoint navigation\"\n\n[hidden]\ndescription = \"empty/singleton states, head/tail/middle mutations, slot reuse with stale-handle rejection, and vector-oracle traces\"\n","task.h":header,"task.cpp":_starter(s),".meta/example.h":header,".meta/example.cpp":_reference(s),"task_visible_test.cpp":_test(s,False),".meta/task_hidden_test.cpp":_test(s,True),"CMakeLists.txt":_cmake()}
        files = task_named_files(root, files)
        for relative,content in files.items(): _write(root/relative,content,force)
        roots.append(root)
    return tuple(roots)


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    for spec in TASKS:
        with tempfile.TemporaryDirectory(prefix="xor-linked-list-") as temp:
            copied=Path(temp)/spec.task_id; shutil.copytree(out/spec.task_id,copied); reference=copied/".meta/example.cpp"
            for name,flags in (("normal",[]),("sanitizer",["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined","-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir=copied/f"build-{name}"; subprocess.run(["cmake","-S",str(copied),"-B",str(build_dir),f"-DTASK_SOURCE={reference}",*flags],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True); subprocess.run(["cmake","--build",str(build_dir),"--parallel","2"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True); subprocess.run(["ctest","--test-dir",str(build_dir),"--output-on-failure"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Materialize local safe XOR-linked-list Aider curriculum tasks."); parser.add_argument("--out",type=Path,default=DEFAULT_OUT); parser.add_argument("--force",action="store_true"); parser.add_argument("--verify",action="store_true"); args=parser.parse_args(argv); roots=build(args.out,args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} XOR-linked-list curriculum tasks under {args.out}"); return 0


if __name__ == "__main__": raise SystemExit(main())
