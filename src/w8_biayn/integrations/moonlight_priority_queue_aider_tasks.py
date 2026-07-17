"""Materialize newly-authored local priority-queue Aider curriculum tasks."""
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

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/priority-queue")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_PRIORITY_QUEUE_CURRICULUM.md"

@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    submit: str
    revise: str
    cancel: str
    select: str
    noun: str
    key_description: str

_ROWS = (
    ("pq-emergency-dispatch", "EmergencyDispatch", "report_incident", "revise_incident", "cancel_incident", "dispatch_next", "incidents", "severity descending, deadline ascending"),
    ("pq-build-scheduler", "BuildScheduler", "queue_build", "revise_build", "cancel_build", "start_next_build", "build jobs", "ready priority descending, estimated duration ascending"),
    ("pq-flight-standby", "FlightStandby", "join_standby", "revise_status", "withdraw_passenger", "promote_next", "passengers", "status descending, check-in time ascending"),
    ("pq-print-routing", "PrintRouting", "submit_print", "revise_print", "cancel_print", "route_next_print", "print jobs", "urgency descending, page count ascending"),
    ("pq-hospital-triage", "HospitalTriage", "admit_patient", "revise_acuity", "discharge_patient", "select_next_patient", "patients", "acuity descending, arrival time ascending"),
    ("pq-network-retries", "NetworkRetries", "schedule_retry", "reschedule_retry", "cancel_retry", "take_next_retry", "retry requests", "retry deadline ascending, failure score descending"),
    ("pq-warehouse-picks", "WarehousePicks", "add_pick", "revise_pick", "cancel_pick", "dispatch_next_pick", "warehouse picks", "shipping cutoff ascending, walking-zone cost ascending"),
    ("pq-road-snowplows", "SnowplowDispatch", "report_segment", "revise_weather", "close_segment", "assign_next_segment", "road segments", "hazard descending, deadline ascending"),
    ("pq-support-escalations", "SupportEscalations", "open_ticket", "revise_ticket", "resolve_ticket", "take_next_ticket", "support tickets", "SLA risk descending, opened time ascending"),
    ("pq-auction-orders", "AuctionOrders", "place_order", "revise_order", "cancel_order", "match_best_order", "auction orders", "price descending, submitted time ascending"),
    ("pq-video-transcodes", "VideoTranscodes", "submit_transcode", "revise_transcode", "cancel_transcode", "assign_next_transcode", "transcodes", "customer tier descending, render cost ascending"),
    ("pq-data-backups", "DataBackups", "schedule_backup", "revise_backup", "cancel_backup", "start_next_backup", "backup jobs", "risk descending, age descending"),
    ("pq-package-delivery", "PackageDelivery", "accept_parcel", "correct_parcel", "cancel_parcel", "dispatch_next_parcel", "parcels", "promised window ascending, route zone ascending"),
    ("pq-game-matchmaking", "GameMatchmaking", "join_player", "revise_player", "remove_player", "select_next_player", "waiting players", "rating deviation descending, wait time descending"),
    ("pq-memory-reclaimer", "MemoryReclaimer", "track_block", "revise_block", "pin_or_remove_block", "reclaim_next_block", "cache blocks", "reclaim score descending, age descending"),
    ("pq-conference-talks", "ConferenceTalks", "register_talk", "revise_talk", "cancel_talk", "prepare_next_talk", "conference talks", "room readiness descending, start deadline ascending"),
    ("pq-security-alerts", "SecurityAlerts", "report_alert", "revise_alert", "dismiss_alert", "investigate_next_alert", "security alerts", "risk descending, asset criticality descending"),
    ("pq-maintenance-crews", "MaintenanceCrews", "open_work_order", "revise_work_order", "close_work_order", "assign_next_work_order", "work orders", "outage impact descending, due time ascending"),
    ("pq-search-top-results", "SearchTopResults", "consider_result", "revise_result", "remove_result", "take_best_result", "search results", "score descending, result ID ascending"),
    ("pq-metric-anomalies", "MetricAnomalies", "report_anomaly", "revise_anomaly", "resolve_anomaly", "take_next_anomaly", "metric anomalies", "anomaly score descending, first-seen time ascending"),
)
TASKS = tuple(TaskSpec(*row) for row in _ROWS)

def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def _header(s: TaskSpec) -> str:
    return f'''#ifndef {s.class_name.upper()}_H
#define {s.class_name.upper()}_H
#include <cstddef>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>
namespace curriculum {{
class {s.class_name} {{
public:
  struct Request {{ std::string id; int primary; int secondary; int timestamp; }};
  struct Selection {{ std::string id; int primary; int secondary; int timestamp; }};
  explicit {s.class_name}(std::size_t capacity);
  bool {s.submit}(const Request& request);
  bool {s.revise}(const std::string& id, int primary, int secondary);
  bool {s.cancel}(const std::string& id);
  std::optional<Selection> {s.select}();
  std::vector<std::string> pending_ids() const;
  std::size_t size() const;
private:
  struct Entry {{ int primary; int secondary; int timestamp; std::size_t sequence; }};
  std::size_t capacity_; std::size_t sequence_ = 0; std::unordered_map<std::string, Entry> entries_;
}};
}}  // namespace curriculum
#endif
'''

def _reference(s: TaskSpec) -> str:
    return f'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t capacity) : capacity_(capacity) {{ if (capacity == 0U) throw std::invalid_argument("capacity must be positive"); }}
bool {s.class_name}::{s.submit}(const Request& request) {{ if (request.id.empty() || request.primary < 0 || request.secondary < 0 || request.timestamp < 0 || entries_.count(request.id) || entries_.size() == capacity_) return false; entries_.emplace(request.id, Entry{{request.primary, request.secondary, request.timestamp, ++sequence_}}); return true; }}
bool {s.class_name}::{s.revise}(const std::string& id, int primary, int secondary) {{ auto it = entries_.find(id); if (it == entries_.end() || primary < 0 || secondary < 0) return false; it->second.primary = primary; it->second.secondary = secondary; return true; }}
bool {s.class_name}::{s.cancel}(const std::string& id) {{ return entries_.erase(id) != 0U; }}
std::optional<{s.class_name}::Selection> {s.class_name}::{s.select}() {{ if (entries_.empty()) return std::nullopt; auto best = entries_.begin(); for (auto it = entries_.begin(); it != entries_.end(); ++it) {{ const Entry& a = it->second; const Entry& b = best->second; if (a.primary > b.primary || (a.primary == b.primary && (a.secondary < b.secondary || (a.secondary == b.secondary && (a.timestamp < b.timestamp || (a.timestamp == b.timestamp && a.sequence < b.sequence)))))) best = it; }} Selection result{{best->first, best->second.primary, best->second.secondary, best->second.timestamp}}; entries_.erase(best); return result; }}
std::vector<std::string> {s.class_name}::pending_ids() const {{ std::vector<std::string> ids; for (const auto& item : entries_) ids.push_back(item.first); std::sort(ids.begin(), ids.end()); return ids; }}
std::size_t {s.class_name}::size() const {{ return entries_.size(); }}
}}  // namespace curriculum
'''

def _starter(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}(std::size_t capacity) : capacity_(capacity) {{}}
bool {s.class_name}::{s.submit}(const Request&) {{ return false; }} bool {s.class_name}::{s.revise}(const std::string&, int, int) {{ return false; }} bool {s.class_name}::{s.cancel}(const std::string&) {{ return false; }}
std::optional<{s.class_name}::Selection> {s.class_name}::{s.select}() {{ return std::nullopt; }} std::vector<std::string> {s.class_name}::pending_ids() const {{ return {{}}; }} std::size_t {s.class_name}::size() const {{ return 0U; }}
}}  // namespace curriculum
'''

def _test(s: TaskSpec, hidden: bool) -> str:
    trace = f''' curriculum::{s.class_name} trace(8); for (int i = 0; i < 160; ++i) {{ const std::string id = "r" + std::to_string(i % 11); if (i % 5 == 0) trace.{s.cancel}(id); else if (i % 3 == 0) trace.{s.revise}(id, i % 13, i % 7); else trace.{s.submit}({{id, i % 13, i % 7, i}}); check(trace.size() <= 8U); }} while (trace.{s.select}()) check(trace.size() <= 8U);''' if hidden else ""
    return f'''#include "task.h"
#include <stdexcept>
#include <string>
int main() {{ int failures = 0; const auto check = [&](bool ok) {{ if (!ok) ++failures; }}; try {{ curriculum::{s.class_name} invalid(0); check(false); }} catch (const std::invalid_argument&) {{}} curriculum::{s.class_name} queue(3); check(!queue.{s.submit}({{"", 1, 1, 1}})); check(queue.{s.submit}({{"late", 5, 2, 9}})); check(queue.{s.submit}({{"early", 5, 2, 3}})); check(queue.{s.submit}({{"low", 2, 0, 1}})); check(!queue.{s.submit}({{"full", 9, 0, 0}})); check(queue.{s.revise}("low", 8, 4)); const auto first = queue.{s.select}(); check(first && first->id == "low"); const auto second = queue.{s.select}(); check(second && second->id == "early"); check(queue.{s.cancel}("late")); check(!queue.{s.select}()); {trace} return failures == 0 ? 0 : 1; }}
'''

def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(priority_queue_curriculum LANGUAGES CXX)
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
    roots: list[Path] = []
    for s in TASKS:
        root = out / s.task_id; header = _header(s)
        config = {"authors": ["w8-biayn"], "blurb": f"A deterministic bounded scheduler for {s.noun}.", "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": s.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1, "benchmark_separation": "Newly authored task-specific priority API and tests; not derived from an official Aider Polyglot benchmark task or its artifacts."}
        files = {".docs/introduction.md": f"# {s.class_name}\n\nA newly authored local priority-scheduling diagnostic for {s.noun}.\n", ".docs/instructions.md": f"# Instructions\n\nImplement `{s.class_name}`. `{s.submit}` admits a unique nonempty request ID while capacity remains. Priorities are nonnegative. `{s.revise}` changes the two priority fields of a retained ID without changing its original arrival order; `{s.cancel}` removes an ID. `{s.select}` returns and removes the best request, or no value when empty. The ordering is {s.key_description}, then original arrival sequence. Invalid calls and capacity failures return `false` without state mutation. `pending_ids()` is a sorted diagnostic snapshot.\n", ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": "[visible]\ndescription = \"domain API, validation, bounded admission, updates, cancellation, and deterministic ties\"\n\n[hidden]\ndescription = \"empty and singleton states, stale update/cancellation paths, randomized bounded traces, exact-once selection, and sanitizer execution\"\n", "task.h": header, "task.cpp": _starter(s), ".meta/example.h": header, ".meta/example.cpp": _reference(s), "task_visible_test.cpp": _test(s, False), ".meta/task_hidden_test.cpp": _test(s, True), "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items(): _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)

def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    for root in (out / s.task_id for s in TASKS):
        with tempfile.TemporaryDirectory(prefix="priority-queue-curriculum-") as temporary:
            copied = Path(temporary) / root.name; shutil.copytree(root, copied); reference = copied / ".meta" / "example.cpp"
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={reference}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format priority-queue curriculum tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT); parser.add_argument("--force", action="store_true"); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv); roots = build(args.out, args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} priority-queue curriculum tasks under {args.out}"); return 0

if __name__ == "__main__": raise SystemExit(main())
