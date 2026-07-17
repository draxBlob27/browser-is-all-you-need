"""Materialize newly-authored local circular-deque Aider curriculum tasks.

These roots are deliberately local diagnostics.  They are not primary SFT
dataset candidates and never reuse the official Polyglot circular-buffer task.
"""
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

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/circular-deque")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_CIRCULAR_DEQUE_CURRICULUM.md"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    front_add: str
    back_add: str
    take: str
    take_front: bool
    policy: str
    blurb: str


_ROWS = (
    ("cdeque-shuttle-stops", "ShuttleStops", "add_urgent_stop", "add_regular_stop", "serve_next_stop", True, "reject", "Urgent stops join the boarding end and regular stops join the exit end."),
    ("cdeque-patient-triage", "PatientTriage", "admit_emergency", "admit_routine", "select_next_patient", True, "evict_back", "Emergency patients are selected first; a full triage list may displace one routine-tail patient."),
    ("cdeque-card-draw-pile", "CardDrawPile", "return_to_top", "return_to_bottom", "draw_bottom_card", False, "reject", "Returned cards go to a named end and draws occur from the bottom."),
    ("cdeque-audio-jitter", "AudioJitterBuffer", "insert_late_frame", "queue_playback_frame", "drain_playback_frame", True, "evict_back", "Late frames precede queued playback; overflow drops the farthest queued frame."),
    ("cdeque-delivery-resequence", "DeliveryResequencer", "add_expedited_parcel", "add_standard_parcel", "dispatch_parcel", False, "evict_front", "Dispatch uses the dock end while full standard intake discards the oldest expedited end."),
    ("cdeque-browser-tabs", "BrowserTabs", "open_foreground_tab", "open_background_tab", "close_background_tab", False, "reject", "Foreground and background tab openings use opposite ends and capacity rejects new tabs."),
    ("cdeque-print-priority", "PrintPriority", "submit_urgent_job", "submit_normal_job", "dispatch_print_job", True, "evict_back", "Urgent jobs displace the least-priority queued job when capacity is exhausted."),
    ("cdeque-event-replay", "EventReplay", "prepend_recovered_event", "append_live_event", "replay_latest_event", False, "evict_front", "Recovered events are prepended, live events appended, and replay proceeds backward."),
    ("cdeque-ticket-escalation", "TicketEscalation", "escalate_ticket", "demote_ticket", "resolve_escalated_ticket", True, "reject", "Escalation and demotion are visible state changes; full intake is rejected without mutation."),
    ("cdeque-warehouse-loading", "WarehouseLoading", "load_fragile_package", "load_standard_package", "unload_dock_package", False, "evict_front", "Fragile packages use the protected end and full loading drops its oldest package."),
    ("cdeque-game-turns", "GameTurns", "grant_bonus_turn", "queue_normal_turn", "take_active_turn", True, "reject", "Bonus turns become active before normal turns and rejected inserts preserve turn order."),
    ("cdeque-transit-passengers", "TransitPassengers", "board_priority_passenger", "board_regular_passenger", "unload_front_door", True, "evict_back", "Priority boarding uses the front door; overload removes the last regular-side passenger."),
    ("cdeque-log-recovery", "LogRecovery", "prepend_recovered_record", "append_live_record", "consume_newest_record", False, "evict_front", "Recovery records lead live records, while consumption reads the newest retained record."),
    ("cdeque-tool-rental", "ToolRentalQueue", "return_repair_tool", "return_standard_tool", "issue_standard_tool", False, "reject", "Repair returns are expedited, standard returns are queued, and issuing uses the standard end."),
    ("cdeque-sensor-calibration", "SensorCalibration", "add_critical_calibration", "add_routine_calibration", "take_critical_calibration", True, "evict_back", "Critical calibrations preempt routine tail work when the bounded queue is full."),
    ("cdeque-meal-orders", "MealOrders", "add_rush_order", "add_standard_order", "serve_rush_end", True, "reject", "Rush orders and standard orders enter different ends; service uses the kitchen rush end."),
    ("cdeque-route-detours", "RouteDetours", "prepend_detour", "append_planned_stop", "take_planned_end", False, "evict_front", "Temporary detours occupy the front and a full route replaces its oldest detour-side action."),
    ("cdeque-media-preview", "MediaPreview", "add_instant_preview", "queue_preview", "discard_queued_preview", False, "reject", "Instant and queued previews are independently observable ends with non-mutating overflow rejection."),
    ("cdeque-support-callbacks", "SupportCallbacks", "escalate_callback", "queue_routine_callback", "take_escalated_callback", True, "evict_back", "Escalated callbacks preempt routine callbacks and full intake drops the routine tail."),
    ("cdeque-build-work-items", "BuildWorkItems", "add_retry_work", "add_new_work", "process_new_work", False, "evict_front", "Retries are prepended, new work appended, and processing uses the explicitly named new-work end."),
)
TASKS = tuple(TaskSpec(*row) for row in _ROWS)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text() != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _header(s: TaskSpec) -> str:
    guard = f"{s.class_name.upper()}_H"
    return f'''#ifndef {guard}
#define {guard}
#include <cstddef>
#include <optional>
#include <vector>
namespace curriculum {{
class {s.class_name} {{
public:
  explicit {s.class_name}(std::size_t capacity);
  std::size_t capacity() const; std::size_t size() const; bool empty() const;
  bool {s.front_add}(int value); bool {s.back_add}(int value);
  std::optional<int> {s.take}(); std::vector<int> snapshot() const; void clear();
private:
  bool insert_front(int value); bool insert_back(int value); std::optional<int> remove_front(); std::optional<int> remove_back();
  std::vector<int> slots_; std::size_t head_ = 0, size_ = 0;
}};
}}  // namespace curriculum
#endif
'''


def _reference(s: TaskSpec) -> str:
    on_full_front = "remove_back();" if s.policy == "evict_back" else ("remove_front();" if s.policy == "evict_front" else "return false;")
    on_full_back = "remove_back();" if s.policy == "evict_back" else ("remove_front();" if s.policy == "evict_front" else "return false;")
    take = "remove_front()" if s.take_front else "remove_back()"
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t capacity) : slots_(capacity) {{}}
std::size_t {s.class_name}::capacity() const {{ return slots_.size(); }} std::size_t {s.class_name}::size() const {{ return size_; }} bool {s.class_name}::empty() const {{ return size_ == 0U; }}
bool {s.class_name}::insert_front(int value) {{ if (slots_.empty()) return false; if (size_ == slots_.size()) {{ {on_full_front} }} head_ = (head_ + slots_.size() - 1U) % slots_.size(); slots_[head_] = value; ++size_; return true; }}
bool {s.class_name}::insert_back(int value) {{ if (slots_.empty()) return false; if (size_ == slots_.size()) {{ {on_full_back} }} slots_[(head_ + size_) % slots_.size()] = value; ++size_; return true; }}
std::optional<int> {s.class_name}::remove_front() {{ if (empty()) return std::nullopt; int value=slots_[head_]; head_=(head_+1U)%slots_.size(); --size_; return value; }}
std::optional<int> {s.class_name}::remove_back() {{ if (empty()) return std::nullopt; std::size_t index=(head_+size_-1U)%slots_.size(); int value=slots_[index]; --size_; return value; }}
bool {s.class_name}::{s.front_add}(int value) {{ return insert_front(value); }} bool {s.class_name}::{s.back_add}(int value) {{ return insert_back(value); }}
std::optional<int> {s.class_name}::{s.take}() {{ return {take}; }}
std::vector<int> {s.class_name}::snapshot() const {{ std::vector<int> out; for(std::size_t i=0;i<size_;++i) out.push_back(slots_[(head_+i)%slots_.size()]); return out; }}
void {s.class_name}::clear() {{ head_=0; size_=0; }}
}}  // namespace curriculum
'''


def _starter(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t) {{}} std::size_t {s.class_name}::capacity() const {{ return 0; }} std::size_t {s.class_name}::size() const {{ return 0; }} bool {s.class_name}::empty() const {{ return true; }}
bool {s.class_name}::insert_front(int) {{ return false; }} bool {s.class_name}::insert_back(int) {{ return false; }} std::optional<int> {s.class_name}::remove_front() {{ return std::nullopt; }} std::optional<int> {s.class_name}::remove_back() {{ return std::nullopt; }}
bool {s.class_name}::{s.front_add}(int) {{ return false; }} bool {s.class_name}::{s.back_add}(int) {{ return false; }} std::optional<int> {s.class_name}::{s.take}() {{ return std::nullopt; }} std::vector<int> {s.class_name}::snapshot() const {{ return {{}}; }} void {s.class_name}::clear() {{}}
}}  // namespace curriculum
'''


def _test(s: TaskSpec, hidden: bool) -> str:
    take_oracle = "oracle.front()" if s.take_front else "oracle.back()"
    take_pop = "oracle.pop_front()" if s.take_front else "oracle.pop_back()"
    overflow = ("oracle.pop_back();" if s.policy == "evict_back" else "oracle.pop_front();") if s.policy != "reject" else ""
    full_expected = "true" if s.policy != "reject" else "false"
    trace = ""
    if hidden:
        trace = f'''\n  curriculum::{s.class_name} trace(4); std::deque<int> oracle;
  for (int step=1; step<=320; ++step) {{
    if (step%5==0) {{ const auto got=trace.{s.take}(); check(got==(oracle.empty()?std::nullopt:std::optional<int>({take_oracle}))); if(!oracle.empty()) {{ {take_pop} }} }}
    else {{ const bool front=step%2==0; const int value=(step*41)%127; bool expected=true; if(oracle.size()==4U) {{ {'expected=false;' if s.policy == 'reject' else overflow} }} if(expected) {{ if(front) oracle.push_front(value); else oracle.push_back(value); }} const bool got=front ? trace.{s.front_add}(value) : trace.{s.back_add}(value); check(got==expected); }}
    check(trace.snapshot()==std::vector<int>(oracle.begin(), oracle.end()));
  }}'''
    return f'''#include "task.h"
#include <deque>
#include <optional>
#include <vector>
int main() {{ int failures=0; const auto check=[&](bool value){{ if(!value) ++failures; }};
  curriculum::{s.class_name} zero(0); check(!zero.{s.front_add}(1)); check(!zero.{s.back_add}(2)); check(!zero.{s.take}());
  curriculum::{s.class_name} queue(3); check(queue.{s.front_add}(20)); check(queue.{s.back_add}(30)); check(queue.{s.front_add}(10)); check(queue.snapshot()==std::vector<int>{{10,20,30}}); check(queue.{s.back_add}(40)=={full_expected});
  check(queue.size()==3U); check(queue.{s.take}()==std::optional<int>({10 if s.take_front else 30})); check(queue.snapshot()==std::vector<int>{{{20 if s.take_front else 10},{30 if s.take_front else 20}}}); queue.clear(); check(queue.empty());{trace}
  return failures==0 ? 0 : 1; }}
'''


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(circular_deque_curriculum LANGUAGES CXX)
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


def _policy(s: TaskSpec) -> str:
    return {"reject": "When full, either insertion is rejected without state mutation.", "evict_back": "When full, an insertion succeeds after removing exactly the current back item.", "evict_front": "When full, an insertion succeeds after removing exactly the current front item."}[s.policy]


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    roots: list[Path] = []
    for s in TASKS:
        root = out / s.task_id
        header = _header(s)
        config = {"authors": ["w8-biayn"], "blurb": s.blurb, "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": s.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1, "benchmark_separation": "Not derived from the official Aider Polyglot circular-buffer task; it has an independently authored domain API, side policy, tests, and reference implementation."}
        files = {".docs/introduction.md": f"# {s.class_name}\n\n{s.blurb} This is a newly authored bounded circular-deque diagnostic.\n", ".docs/instructions.md": f"# Instructions\n\nImplement `{s.class_name}`. `{s.front_add}` adds an item at the front and `{s.back_add}` adds an item at the back. `{s.take}` returns and removes the {'front' if s.take_front else 'back'} item, or no value when empty. `snapshot()` returns front-to-back order without mutation. Zero capacity is valid but stores nothing. {_policy(s)} `clear()` removes all retained items.\n", ".meta/config.json": json.dumps(config, indent=2, sort_keys=True)+"\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True)+"\n", ".meta/tests.toml": "[visible]\ndescription = \"task API, end selection, capacity behavior, and front-to-back snapshots\"\n\n[hidden]\ndescription = \"zero/singleton boundaries, both wrap directions, rejected-operation immutability, overwrite behavior, and randomized std::deque oracle traces\"\n", "task.h": header, "task.cpp": _starter(s), ".meta/example.h": header, ".meta/example.cpp": _reference(s), "task_visible_test.cpp": _test(s, False), ".meta/task_hidden_test.cpp": _test(s, True), "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        raise RuntimeError("verification requires cmake and c++")
    for root in (out / s.task_id for s in TASKS):
        with tempfile.TemporaryDirectory(prefix="circular-deque-curriculum-") as temporary:
            copied = Path(temporary) / root.name
            shutil.copytree(root, copied)
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={copied / '.meta/example.cpp'}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format circular-deque curriculum tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify:
        verify(args.out)
    print(f"Wrote {len(roots)} circular-deque curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
