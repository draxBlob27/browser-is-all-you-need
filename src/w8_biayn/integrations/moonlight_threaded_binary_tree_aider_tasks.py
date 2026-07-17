"""Materialize newly-authored local threaded-binary-tree Aider tasks."""
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

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/threaded-binary-tree")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_THREADED_BINARY_TREE_CURRICULUM.md"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str; class_name: str; entity: str; add: str; remove: str; previous: str; next: str; ordered: str; reverse: str; window: str; action: str


_ROWS = (
    ("threaded-calendar-navigator", "CalendarNavigator", "event keys", "add_event", "cancel_event", "previous_event", "next_event", "event_keys", "event_keys_reverse", "events_between", "schedule and cancel"),
    ("threaded-library-shelves", "LibraryShelves", "call numbers", "register_call_number", "withdraw_call_number", "shelf_before", "shelf_after", "shelf_order", "shelf_order_reverse", "shelf_section", "register and withdraw"),
    ("threaded-audit-browser", "AuditBrowser", "audit records", "insert_record", "redact_record", "record_before", "record_after", "records_in_order", "records_in_reverse", "records_between", "insert and redact"),
    ("threaded-flight-departures", "FlightDepartures", "departure keys", "add_departure", "cancel_departure", "departure_before", "departure_after", "departure_order", "departure_order_reverse", "departures_between", "add and cancel"),
    ("threaded-sensor-thresholds", "SensorThresholds", "thresholds", "add_threshold", "remove_threshold", "threshold_below", "threshold_at_or_above", "thresholds_ascending", "thresholds_descending", "thresholds_in_band", "add and remove"),
    ("threaded-file-version-browser", "FileVersionBrowser", "revisions", "retain_revision", "discard_revision", "revision_before", "revision_after", "retained_versions", "retained_versions_reverse", "versions_between", "retain and discard"),
    ("threaded-parking-space-guide", "ParkingSpaceGuide", "occupied spaces", "reserve_space", "release_space", "occupied_before", "occupied_after", "occupied_spaces", "occupied_spaces_reverse", "spaces_between", "reserve and release"),
    ("threaded-museum-waypoints", "MuseumWaypoints", "exhibits", "add_exhibit", "remove_exhibit", "exhibit_before", "exhibit_after", "tour_order", "tour_order_reverse", "tour_segment", "add and remove"),
    ("threaded-score-history", "ScoreHistory", "score events", "record_score", "erase_score", "score_before", "score_after", "score_history", "score_history_reverse", "scores_between", "record and erase"),
    ("threaded-medication-times", "MedicationTimes", "dose times", "schedule_dose", "cancel_dose", "dose_before", "dose_after", "scheduled_doses", "scheduled_doses_reverse", "doses_between", "schedule and cancel"),
    ("threaded-cargo-manifest", "CargoManifest", "cargo identifiers", "index_cargo", "remove_cargo", "cargo_before", "cargo_after", "cargo_order", "cargo_order_reverse", "cargo_interval", "index and remove"),
    ("threaded-route-stations", "RouteStations", "route codes", "open_station", "close_station", "station_before", "station_after", "station_order", "station_order_reverse", "stations_between", "open and close"),
    ("threaded-ticket-browser", "TicketBrowser", "unresolved tickets", "open_ticket", "resolve_ticket", "ticket_before", "ticket_after", "unresolved_tickets", "unresolved_tickets_reverse", "tickets_between", "open and resolve"),
    ("threaded-fare-tiers", "FareTiers", "fare thresholds", "add_tier", "remove_tier", "cheaper_tier", "dearer_tier", "tiers_ascending", "tiers_descending", "tiers_between", "add and remove"),
    ("threaded-appointment-book", "AppointmentBook", "appointment times", "reserve_time", "release_time", "appointment_before", "appointment_after", "reserved_times", "reserved_times_reverse", "appointments_between", "reserve and release"),
    ("threaded-inventory-catalog", "InventoryCatalog", "SKU keys", "add_sku", "discontinue_sku", "sku_before", "sku_after", "catalog_order", "catalog_order_reverse", "catalog_section", "add and discontinue"),
    ("threaded-document-anchors", "DocumentAnchors", "anchors", "add_anchor", "remove_anchor", "anchor_before", "anchor_after", "anchor_order", "anchor_order_reverse", "anchors_between", "add and remove"),
    ("threaded-auction-bids", "AuctionBids", "bid levels", "place_bid", "withdraw_bid", "bid_before", "bid_after", "bid_levels", "bid_levels_reverse", "bids_between", "place and withdraw"),
    ("threaded-network-ports", "NetworkPorts", "reserved ports", "reserve_port", "free_port", "port_before", "port_after", "reserved_ports", "reserved_ports_reverse", "ports_between", "reserve and free"),
    ("threaded-transit-service", "TransitService", "service times", "add_service", "cancel_service", "service_before", "service_after", "service_times", "service_times_reverse", "services_between", "add and cancel"),
)
TASKS = tuple(TaskSpec(*row) for row in _ROWS)

def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force: raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding="utf-8")

def _header(s: TaskSpec) -> str:
    return f'''#ifndef {s.class_name.upper()}_H
#define {s.class_name.upper()}_H
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum {{ class {s.class_name} {{ public:
  {s.class_name}(); ~{s.class_name}(); {s.class_name}(const {s.class_name}&) = delete; {s.class_name}& operator=(const {s.class_name}&) = delete;
  bool {s.add}(int key); bool {s.remove}(int key); bool contains(int key) const;
  std::optional<int> {s.previous}(int key) const; std::optional<int> {s.next}(int key) const;
  std::vector<int> {s.ordered}() const; std::vector<int> {s.reverse}() const; std::vector<int> {s.window}(int first, int last) const; std::size_t size() const;
private: struct Node {{ int key; Node* left; Node* right; bool is_left_thread; bool is_right_thread; }}; Node* root_; std::size_t size_; void clear(Node* node); }}; }}
#endif
'''

def _reference(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}() : root_(nullptr), size_(0) {{}}
{s.class_name}::~{s.class_name}() {{ clear(root_); }}
void {s.class_name}::clear(Node* n) {{ if (!n) return; if (!n->is_left_thread) clear(n->left); if (!n->is_right_thread) clear(n->right); delete n; }}
bool {s.class_name}::{s.add}(int key) {{ if (key <= 0) return false; if (!root_) {{ root_=new Node{{key,nullptr,nullptr,true,true}}; size_=1; return true; }} Node* n=root_; while(true) {{ if(key==n->key) return false; const bool left=key<n->key; Node*& edge=left?n->left:n->right; bool& thread=left?n->is_left_thread:n->is_right_thread; if(thread) {{ Node* fresh=new Node{{key,nullptr,nullptr,true,true}}; if(left) {{ fresh->left=edge; fresh->right=n; }} else {{ fresh->left=n; fresh->right=edge; }} edge=fresh; thread=false; ++size_; return true; }} n=edge; }} }}
bool {s.class_name}::{s.remove}(int key) {{ if(!contains(key)) return false; std::vector<int> keep; for(int v:{s.ordered}()) if(v!=key) keep.push_back(v); clear(root_); root_=nullptr; size_=0; for(int v:keep) {s.add}(v); return true; }}
bool {s.class_name}::contains(int key) const {{ Node* n=root_; while(n) {{ if(key==n->key) return true; if(key<n->key) {{ if(n->is_left_thread) return false; n=n->left; }} else {{ if(n->is_right_thread) return false; n=n->right; }} }} return false; }}
std::optional<int> {s.class_name}::{s.previous}(int key) const {{ Node* n=root_; Node* best=nullptr; while(n) {{ if(n->key<key) {{ best=n; if(n->is_right_thread) break; n=n->right; }} else {{ if(n->is_left_thread) break; n=n->left; }} }} return best?std::optional<int>(best->key):std::nullopt; }}
std::optional<int> {s.class_name}::{s.next}(int key) const {{ Node* n=root_; Node* best=nullptr; while(n) {{ if(n->key>=key) {{ best=n; if(n->is_left_thread) break; n=n->left; }} else {{ if(n->is_right_thread) break; n=n->right; }} }} return best?std::optional<int>(best->key):std::nullopt; }}
std::vector<int> {s.class_name}::{s.ordered}() const {{ std::vector<int> out; Node* n=root_; if(!n) return out; while(!n->is_left_thread) n=n->left; while(n) {{ out.push_back(n->key); if(n->is_right_thread) n=n->right; else {{ n=n->right; while(n && !n->is_left_thread) n=n->left; }} }} return out; }}
std::vector<int> {s.class_name}::{s.reverse}() const {{ std::vector<int> out; Node* n=root_; if(!n) return out; while(!n->is_right_thread) n=n->right; while(n) {{ out.push_back(n->key); if(n->is_left_thread) n=n->left; else {{ n=n->left; while(n && !n->is_right_thread) n=n->right; }} }} return out; }}
std::vector<int> {s.class_name}::{s.window}(int first,int last) const {{ std::vector<int> out; if(first>last) return out; for(int key:{s.ordered}()) if(key>=first && key<=last) out.push_back(key); return out; }}
std::size_t {s.class_name}::size() const {{ return size_; }}
}}
'''

def _starter(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{ {s.class_name}::{s.class_name}() : root_(nullptr), size_(0) {{}} {s.class_name}::~{s.class_name}() {{}} void {s.class_name}::clear(Node*) {{}}
bool {s.class_name}::{s.add}(int) {{ return false; }} bool {s.class_name}::{s.remove}(int) {{ return false; }} bool {s.class_name}::contains(int) const {{ return false; }} std::optional<int> {s.class_name}::{s.previous}(int) const {{ return std::nullopt; }} std::optional<int> {s.class_name}::{s.next}(int) const {{ return std::nullopt; }} std::vector<int> {s.class_name}::{s.ordered}() const {{ return {{}}; }} std::vector<int> {s.class_name}::{s.reverse}() const {{ return {{}}; }} std::vector<int> {s.class_name}::{s.window}(int,int) const {{ return {{}}; }} std::size_t {s.class_name}::size() const {{ return 0; }} }}
'''

def _test(s: TaskSpec, hidden: bool) -> str:
    trace=f''' for(int step=1;step<=220;++step){{int key=(step*37)%101+1;bool add=step%3!=0;bool got=add?tree.{s.add}(key):tree.{s.remove}(key);bool want=add?oracle.insert(key).second:oracle.erase(key)==1;check(got==want);check(tree.{s.ordered}()==std::vector<int>(oracle.begin(),oracle.end()));check(tree.{s.reverse}()==std::vector<int>(oracle.rbegin(),oracle.rend()));}}''' if hidden else ""
    return f'''#include "task.h"
#include <optional>
#include <set>
#include <vector>
int main(){{int failures=0;auto check=[&](bool ok){{if(!ok)++failures;}};curriculum::{s.class_name} tree;std::set<int> oracle;check(!tree.{s.add}(0));check(tree.{s.add}(40));check(tree.{s.add}(20));check(tree.{s.add}(60));check(tree.{s.add}(10));check(tree.{s.add}(30));check(tree.{s.add}(50));check(tree.{s.add}(70));check(!tree.{s.add}(40));check(tree.{s.ordered}()==std::vector<int>{{10,20,30,40,50,60,70}});check(tree.{s.reverse}()==std::vector<int>{{70,60,50,40,30,20,10}});check(!tree.{s.previous}(10));check(tree.{s.previous}(40)==std::optional<int>(30));check(tree.{s.next}(40)==std::optional<int>(40));check(!tree.{s.next}(71));check(tree.{s.window}(25,55)==std::vector<int>{{30,40,50}});check(tree.{s.window}(55,25).empty());check(tree.{s.remove}(10));check(tree.{s.remove}(60));check(tree.{s.remove}(40));check(!tree.{s.remove}(999));check(tree.{s.ordered}()==std::vector<int>{{20,30,50,70}});{trace}return failures?1:0;}}
'''

def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(threaded_binary_tree_curriculum LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(target task_visible task_hidden)
 target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
 if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
 endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
'''

def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    roots=[]
    for s in TASKS:
        root=out/s.task_id; header=_header(s)
        config={"authors":["w8-biayn"],"blurb":f"A newly authored threaded-tree diagnostic for {s.entity}.","files":{"solution":["task.h","task.cpp"],"test":["task_visible_test.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}}
        provenance={"curriculum_document":CURRICULUM,"curriculum_task_id":s.task_id,"origin":"newly-authored in-repository diagnostic task","status":"local task artifact; not admitted SFT data","version":1,"benchmark_separation":"Not derived from the official Aider Polyglot binary-search-tree task; this independently authored domain API uses explicit child-edge and inorder-thread markers."}
        instructions=f"# Instructions\n\nImplement `{s.class_name}` to {s.action} unique positive {s.entity}. `{s.add}` rejects non-positive and duplicate keys; `{s.remove}` rejects unknown keys without changing state. `{s.previous}(key)` returns the greatest stored key strictly below `key`; `{s.next}(key)` returns the least stored key at or above `key`. `{s.ordered}` and `{s.reverse}` must use inorder successor and predecessor threads. `{s.window}` is inclusive and returns empty when `first > last`. The private `Node` markers distinguish a real child edge from a predecessor/successor thread; mutations must leave both directions consistent.\n"
        files={".docs/introduction.md":f"# {s.class_name}\n\nA newly authored local threaded binary-tree diagnostic for {s.entity}.\n", ".docs/instructions.md":instructions, ".meta/config.json":json.dumps(config,indent=2,sort_keys=True)+"\n", ".meta/provenance.json":json.dumps(provenance,indent=2,sort_keys=True)+"\n", ".meta/tests.toml":"[visible]\ndescription = \"domain operations, duplicates, navigation, and forward/reverse traversal\"\n\n[hidden]\ndescription = \"empty and singleton boundaries, all child/thread combinations, leaf/one-child/two-child/root deletion, and randomized sorted-oracle mutation traces\"\n", "task.h":header,"task.cpp":_starter(s),".meta/example.h":header,".meta/example.cpp":_reference(s),"task_visible_test.cpp":_test(s,False),".meta/task_hidden_test.cpp":_test(s,True),"CMakeLists.txt":_cmake()}
        files = task_named_files(root, files)
        for relative,content in files.items(): _write(root/relative,content,force)
        roots.append(root)
    return tuple(roots)

def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    for root in (out/s.task_id for s in TASKS):
        with tempfile.TemporaryDirectory(prefix="threaded-tree-curriculum-") as temporary:
            copied=Path(temporary)/root.name; shutil.copytree(root,copied); reference=copied/".meta"/"example.cpp"
            for name,flags in (("normal",[]),("sanitizer",["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined","-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir=copied/f"build-{name}"
                subprocess.run(["cmake","-S",str(copied),"-B",str(build_dir),f"-DTASK_SOURCE={reference}",*flags],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                subprocess.run(["cmake","--build",str(build_dir),"--parallel","2"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                subprocess.run(["ctest","--test-dir",str(build_dir),"--output-on-failure"],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)

def main(argv: Sequence[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="Materialize local Aider-format threaded-binary-tree curriculum tasks.")
    parser.add_argument("--out",type=Path,default=DEFAULT_OUT);parser.add_argument("--force",action="store_true");parser.add_argument("--verify",action="store_true")
    args=parser.parse_args(argv);roots=build(args.out,args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} threaded-binary-tree curriculum tasks under {args.out}");return 0
if __name__ == "__main__": raise SystemExit(main())
