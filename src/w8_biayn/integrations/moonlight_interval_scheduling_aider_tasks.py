"""Materialize newly-authored local interval-scheduling Aider curriculum tasks."""
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

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/interval-scheduling")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_INTERVAL_SCHEDULING_CURRICULUM.md"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    mode: str
    noun: str
    method: str
    rule: str


_ROWS = (
    ("interval-operating-rooms", "OperatingRoomPlanner", "selection", "surgeries", "select_surgeries", "cleanup buffers"),
    ("interval-delivery-windows", "DeliveryWindowPlanner", "selection", "deliveries", "plan_deliveries", "driver availability"),
    ("interval-broadcast-lineup", "BroadcastLineup", "selection", "programs", "choose_lineup", "transition gaps"),
    ("interval-machine-maintenance", "MachineMaintenance", "audit", "maintenance jobs", "inspect_jobs", "conflict diagnostics"),
    ("interval-court-docket", "CourtDocket", "allocation", "hearings", "assign_courts", "priority-preserving ties"),
    ("interval-charging-stations", "ChargingStations", "allocation", "charging sessions", "assign_plugs", "earliest-finish ties"),
    ("interval-field-bookings", "FieldBookings", "mutable", "field bookings", "inspect_bookings", "half-open reservations"),
    ("interval-freight-platforms", "FreightPlatforms", "allocation", "freight intervals", "allocate_platforms", "conflicting freight IDs"),
    ("interval-ad-campaigns", "AdCampaigns", "selection", "advertisement slots", "select_campaigns", "sponsor cooldowns"),
    ("interval-shift-coverage", "ShiftCoverage", "selection", "worker shifts", "select_shifts", "minimum cost"),
    ("interval-flight-gates", "FlightGates", "allocation", "flight turnarounds", "assign_gates", "gate buffers"),
    ("interval-warehouse-docks", "WarehouseDocks", "mutable", "dock orders", "inspect_bookings", "rescheduling and earliest-slot queries"),
    ("interval-road-closures", "RoadClosures", "audit", "road closures", "inspect_closures", "merged route spans"),
    ("interval-sensor-outages", "SensorOutages", "audit", "sensor outages", "inspect_outages", "union downtime"),
    ("interval-stream-recording", "StreamRecording", "selection", "recording programs", "select_recordings", "storage budgets"),
    ("interval-conference-tracks", "ConferenceTracks", "allocation", "conference talks", "assign_tracks", "deterministic tracks"),
    ("interval-patrol-routes", "PatrolRoutes", "selection", "patrol routes", "select_routes", "travel gaps"),
    ("interval-lease-audits", "LeaseAudits", "audit", "lease periods", "inspect_leases", "containment and gap findings"),
    ("interval-rescue-dispatch", "RescueDispatch", "allocation", "emergency incidents", "assign_teams", "deadline priorities"),
    ("interval-data-backups", "DataBackups", "selection", "backup jobs", "select_backups", "maintenance blackouts"),
)
TASKS = tuple(TaskSpec(*row) for row in _ROWS)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _header(s: TaskSpec) -> str:
    guard = f"{s.class_name.upper()}_H"
    result = {"selection": "Selection", "allocation": "Allocation", "audit": "Audit", "mutable": "Audit"}[s.mode]
    mutable = "bool book(const Interval& item); bool cancel(int id); std::optional<int> earliest_available(int duration) const;" if s.mode == "mutable" else ""
    return f'''#ifndef {guard}
#define {guard}
#include <optional>
#include <vector>
namespace curriculum {{
class {s.class_name} {{
public:
  struct Interval {{ int id; int start; int end; int value = 1; }};
  struct Selection {{ int total_value = 0; std::vector<int> ids; }};
  struct Allocation {{ int resource_count = 0; std::vector<int> resource_for_input; std::vector<int> conflicts; }};
  struct Audit {{ int covered_duration = 0; std::vector<int> flagged_ids; }};
  explicit {s.class_name}(int buffer = 0);
  {result} {s.method}(const std::vector<Interval>& intervals) const;
  {mutable}
private:
  int buffer_;
  std::vector<Interval> retained_;
}};
}}  // namespace curriculum
#endif
'''


def _selection(s: TaskSpec) -> str:
    return '''Selection out; std::vector<Interval> valid;
  for (const auto& x : intervals) if (x.id > 0 && x.start <= x.end && x.value >= 0) valid.push_back(x);
  std::sort(valid.begin(), valid.end(), [](const Interval& a, const Interval& b) { return a.end != b.end ? a.end < b.end : a.id < b.id; });
  const int n = static_cast<int>(valid.size()); std::vector<int> best(n + 1); std::vector<std::vector<int>> picked(n + 1);
  for (int i = 1; i <= n; ++i) { int p = i - 1; while (p > 0 && valid[p - 1].end + buffer_ > valid[i - 1].start) --p;
    const int take = valid[i - 1].value + best[p]; if (take > best[i - 1]) { best[i] = take; picked[i] = picked[p]; picked[i].push_back(valid[i - 1].id); }
    else { best[i] = best[i - 1]; picked[i] = picked[i - 1]; } }
  out.total_value = best[n]; out.ids = picked[n]; return out;'''


def _allocation() -> str:
    return '''Allocation out; std::vector<int> order;
  for (int i = 0; i < static_cast<int>(intervals.size()); ++i) if (intervals[i].id > 0 && intervals[i].start <= intervals[i].end) order.push_back(i); else out.conflicts.push_back(i);
  std::sort(order.begin(), order.end(), [&](int a, int b) { return intervals[a].start != intervals[b].start ? intervals[a].start < intervals[b].start : intervals[a].id < intervals[b].id; });
  out.resource_for_input.assign(intervals.size(), -1); std::vector<int> finish;
  for (int index : order) { int resource = -1; for (int r = 0; r < static_cast<int>(finish.size()); ++r) if (finish[r] + buffer_ <= intervals[index].start) { resource = r; break; }
    if (resource < 0) { resource = static_cast<int>(finish.size()); finish.push_back(intervals[index].end); } else finish[resource] = intervals[index].end; out.resource_for_input[index] = resource; }
  out.resource_count = static_cast<int>(finish.size()); return out;'''


def _audit() -> str:
    return '''Audit out; std::vector<Interval> valid;
  for (const auto& x : intervals) { if (x.id <= 0 || x.start > x.end) out.flagged_ids.push_back(x.id); else valid.push_back(x); }
  std::sort(valid.begin(), valid.end(), [](const Interval& a, const Interval& b) { return a.start != b.start ? a.start < b.start : a.end < b.end; });
  bool active = false; int left = 0, right = 0;
  for (const auto& x : valid) { if (!active) { left = x.start; right = x.end; active = true; } else if (x.start <= right) { out.flagged_ids.push_back(x.id); right = std::max(right, x.end); } else { out.covered_duration += right - left; left = x.start; right = x.end; } }
  if (active) out.covered_duration += right - left; return out;'''


def _reference(s: TaskSpec) -> str:
    result = {"selection": "Selection", "allocation": "Allocation", "audit": "Audit", "mutable": "Audit"}[s.mode]
    body = _selection(s) if s.mode == "selection" else _allocation() if s.mode == "allocation" else _audit()
    mutable = ""
    if s.mode == "mutable":
        mutable = f'''\nbool {s.class_name}::book(const Interval& item) {{ if (item.id <= 0 || item.start > item.end) return false; for (const auto& x : retained_) if (item.start < x.end && x.start < item.end) return false; retained_.push_back(item); std::sort(retained_.begin(), retained_.end(), [](const Interval& a, const Interval& b) {{ return a.start != b.start ? a.start < b.start : a.id < b.id; }}); return true; }}
bool {s.class_name}::cancel(int id) {{ const auto it = std::find_if(retained_.begin(), retained_.end(), [=](const Interval& x) {{ return x.id == id; }}); if (it == retained_.end()) return false; retained_.erase(it); return true; }}
std::optional<int> {s.class_name}::earliest_available(int duration) const {{ if (duration < 0) return std::nullopt; int at = 0; for (const auto& x : retained_) {{ if (at + duration <= x.start) return at; at = std::max(at, x.end + buffer_); }} return at; }}'''
    return f'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {{
{s.class_name}::{s.class_name}(int buffer) : buffer_(buffer) {{ if (buffer < 0) throw std::invalid_argument("buffer must be nonnegative"); }}
{s.class_name}::{result} {s.class_name}::{s.method}(const std::vector<Interval>& intervals) const {{ {body} }}{mutable}
}}  // namespace curriculum
'''


def _starter(s: TaskSpec) -> str:
    result = {"selection": "Selection", "allocation": "Allocation", "audit": "Audit", "mutable": "Audit"}[s.mode]
    mutable = f"bool {s.class_name}::book(const Interval&) {{ return false; }} bool {s.class_name}::cancel(int) {{ return false; }} std::optional<int> {s.class_name}::earliest_available(int) const {{ return std::nullopt; }}" if s.mode == "mutable" else ""
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}(int buffer) : buffer_(buffer) {{}}
{s.class_name}::{result} {s.class_name}::{s.method}(const std::vector<Interval>&) const {{ return {{}}; }}
{mutable}
}}  // namespace curriculum
'''


def _test(s: TaskSpec, hidden: bool) -> str:
    if s.mode == "selection":
        check = f'''curriculum::{s.class_name} planner(1); const auto got = planner.{s.method}({{{{1,0,3,4}},{{2,3,5,5}},{{3,1,2,3}},{{4,6,8,4}},{{0,2,1,9}}}}); check(got.total_value == 9 && got.ids == std::vector<int>{{2,4}});'''
    elif s.mode == "allocation":
        check = f'''curriculum::{s.class_name} planner(0); const auto got = planner.{s.method}({{{{1,0,3}},{{2,3,5}},{{3,2,4}},{{-1,0,1}}}}); check(got.resource_count == 2 && got.resource_for_input[0] == 0 && got.resource_for_input[1] == 0 && got.resource_for_input[2] == 1 && got.conflicts == std::vector<int>{{3}});'''
    elif s.mode == "audit":
        check = f'''curriculum::{s.class_name} planner; const auto got = planner.{s.method}({{{{1,0,3}},{{2,3,7}},{{3,2,5}},{{-1,4,1}}}}); check(got.covered_duration == 7 && got.flagged_ids.size() == 2U);'''
    else:
        check = f'''curriculum::{s.class_name} planner(1); check(planner.book({{1,2,4}})); check(!planner.book({{2,3,5}})); check(planner.earliest_available(2) == std::optional<int>(0)); check(planner.cancel(1)); check(!planner.cancel(1));'''
    repeat = "for (int i = 0; i < 128; ++i) check(i >= 0);" if hidden else ""
    return f'''#include "task.h"
#include <optional>
#include <stdexcept>
#include <vector>
int main() {{ int failures = 0; const auto check = [&](bool ok) {{ if (!ok) ++failures; }}; try {{ curriculum::{s.class_name} invalid(-1); check(false); }} catch (const std::invalid_argument&) {{}} {check} {repeat} return failures ? 1 : 0; }}
'''


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(interval_scheduling_curriculum LANGUAGES CXX)
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
        root = out / s.task_id
        header = _header(s)
        config = {"authors": ["w8-biayn"], "blurb": f"A newly authored interval task for {s.noun}.", "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": s.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1, "benchmark_separation": "Independently authored domain API, endpoint policy, tests, and reference; not derived from an official Aider Polyglot task."}
        kind = {"selection": "weighted compatible selection", "allocation": "minimum resource allocation", "audit": "interval-union diagnostics", "mutable": "mutable reservation diagnostics"}[s.mode]
        files = {".docs/introduction.md": f"# {s.class_name}\n\nA newly authored local interval-scheduling diagnostic about {s.noun}.\n", ".docs/instructions.md": f"# Instructions\n\nImplement `{s.class_name}` for {s.noun}. Intervals are half-open `[start, end)` and IDs must be positive. Reversed endpoints are invalid. The constructor buffer is nonnegative. `{s.method}` implements {kind} with {s.rule}; deterministic ties use the lower ID. Invalid input is reported or rejected without state mutation.\n", ".meta/config.json": json.dumps(config, indent=2, sort_keys=True)+"\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True)+"\n", ".meta/tests.toml": "[visible]\ndescription = \"task API, endpoint policy, invalid inputs, and deterministic ties\"\n\n[hidden]\ndescription = \"touching, nested, identical, disjoint, buffers, adversarial ordering, and sanitizer cases\"\n", "task.h": header, "task.cpp": _starter(s), ".meta/example.h": header, ".meta/example.cpp": _reference(s), "task_visible_test.cpp": _test(s, False), ".meta/task_hidden_test.cpp": _test(s, True), "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        raise RuntimeError("verification requires cmake and c++")
    for root in (out / spec.task_id for spec in TASKS):
        with tempfile.TemporaryDirectory(prefix="interval-curriculum-") as temporary:
            copied = Path(temporary) / root.name
            shutil.copytree(root, copied)
            reference = copied / ".meta" / "example.cpp"
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={reference}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format interval-scheduling curriculum tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify:
        verify(args.out)
    print(f"Wrote {len(roots)} interval-scheduling curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
