"""Materialize newly authored local BST Aider curriculum tasks."""

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

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/binary-search-tree")
CURRICULUM = (
    "docs/aider-synthetic/aider-synthetic-dsa/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_BINARY_SEARCH_TREE_CURRICULUM.md"
)


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    noun: str
    add: str
    remove: str
    contains: str
    lower: str
    upper: str
    ordered: str
    extra: str
    extra_name: str
    contract: str
    extra_contract: str


TASKS: tuple[TaskSpec, ...] = (
    TaskSpec("bst-appointment-index", "AppointmentIndex", "appointments", "schedule", "cancel", "has_appointment", "previous_before", "next_at_or_after", "scheduled_starts", "range", "appointments_between", "Schedule unique positive start minutes and navigate neighboring appointments.", "`appointments_between(first, last)` returns scheduled starts in the inclusive window."),
    TaskSpec("bst-price-book", "PriceBook", "price levels", "add_price_level", "remove_price_level", "has_price_level", "best_at_or_below", "first_at_or_above", "price_levels", "range", "levels_in_budget", "Maintain unique positive price levels and resolve a budget without exceeding it.", "`levels_in_budget(first, last)` returns all levels in the inclusive budget band."),
    TaskSpec("bst-library-catalog", "LibraryCatalog", "call numbers", "shelve", "withdraw", "contains_call_number", "shelf_before", "shelf_at_or_after", "shelf_order", "range", "shelf_section", "Index unique positive call numbers and locate neighboring shelf entries.", "`shelf_section(first, last)` returns call numbers in shelf order for the inclusive section."),
    TaskSpec("bst-sensor-thresholds", "SensorThresholds", "thresholds", "record_threshold", "remove_threshold", "has_threshold", "lower_safety_limit", "upper_safety_limit", "thresholds", "range", "safe_band", "Record unique positive safety thresholds and find the enclosing limits.", "`safe_band(first, last)` returns recorded limits in the inclusive band."),
    TaskSpec("bst-transit-departures", "TransitDepartures", "departure times", "add_departure", "cancel_departure", "has_departure", "previous_departure_before", "next_departure_at_or_after", "departure_times", "range", "departures_in_window", "Maintain unique positive departure minutes and find the next available service.", "`departures_in_window(first, last)` returns services in the inclusive time window."),
    TaskSpec("bst-warehouse-bins", "WarehouseBins", "vacant bins", "mark_vacant", "mark_occupied", "is_vacant", "previous_vacant_before", "next_vacant_at_or_after", "vacant_bins", "range", "vacant_bins_in_aisle", "Track positive vacant bin identifiers; duplicates and occupied unknown bins are rejected.", "`vacant_bins_in_aisle(first, last)` returns vacant IDs in the inclusive aisle range."),
    TaskSpec("bst-access-key-registry", "AccessKeyRegistry", "keys", "register_key", "revoke_key", "is_registered", "previous_registered_before", "next_registered_at_or_after", "registered_keys", "count", "registered_count", "Register and revoke unique positive numeric access keys.", "`registered_count()` reports the current number of registered keys."),
    TaskSpec("bst-scoreboard-ranks", "ScoreboardRanks", "scores", "record_score", "erase_score", "has_score", "score_below", "score_at_or_above", "scores_ascending", "rank", "rank_of", "Track unique positive scores in ascending order for rank lookup.", "`rank_of(score)` is one-based ascending rank, or zero when absent."),
    TaskSpec("bst-version-catalog", "VersionCatalog", "releases", "publish", "withdraw", "has_release", "release_before", "latest_not_newer_than", "releases", "count", "release_count", "Store unique positive release numbers and resolve the newest compatible release.", "`release_count()` reports the number of published releases."),
    TaskSpec("bst-delivery-zones", "DeliveryZones", "zone boundaries", "add_boundary", "remove_boundary", "has_boundary", "boundary_below", "boundary_at_or_above", "boundaries", "range", "boundaries_between", "Maintain unique positive zone boundaries and resolve adjacent delivery zones.", "`boundaries_between(first, last)` returns the inclusive boundary interval."),
    TaskSpec("bst-audit-timeline", "AuditTimeline", "audit events", "log_event", "erase_event", "has_event", "event_before", "event_at_or_after", "event_ids", "range", "events_between", "Insert and erase unique positive audit event IDs while retaining chronological order.", "`events_between(first, last)` returns every ID in the inclusive interval."),
    TaskSpec("bst-flight-standby", "FlightStandby", "standby priorities", "add_passenger", "remove_passenger", "has_passenger", "priority_before", "priority_at_or_after", "priorities", "promote", "promote_smallest_eligible", "Maintain unique positive standby priorities and promote the smallest eligible passenger.", "`promote_smallest_eligible(minimum)` removes and returns the first priority at least `minimum`."),
    TaskSpec("bst-energy-meter-readings", "EnergyMeterReadings", "readings", "record_reading", "remove_reading", "has_reading", "reading_before", "reading_at_or_after", "readings", "sum", "sum_inclusive", "Store unique positive meter readings and calculate inclusive range aggregates.", "`count_inclusive(first, last)` and `sum_inclusive(first, last)` aggregate the inclusive range."),
    TaskSpec("bst-cargo-weight-index", "CargoWeightIndex", "allowed weights", "allow_weight", "disallow_weight", "is_allowed", "weight_below", "weight_at_or_above", "allowed_weights", "nearest", "nearest_allowed", "Store unique positive allowed weights and select the nearest permitted load.", "`nearest_allowed(request)` breaks an exact-distance tie toward the lower weight."),
    TaskSpec("bst-auction-bids", "AuctionBids", "bids", "place_bid", "retract_bid", "has_bid", "bid_below", "bid_at_or_above", "bids", "floor", "highest_bid_below", "Maintain unique positive bids and resolve the highest bid strictly below a reserve.", "`highest_bid_below(reserve)` excludes a bid exactly equal to the reserve."),
    TaskSpec("bst-parking-space-index", "ParkingSpaceIndex", "free spaces", "release_space", "occupy_space", "is_free", "free_space_before", "free_space_at_or_after", "free_spaces", "nearest", "nearest_free", "Track unique positive free spaces; releasing a free space or occupying an unavailable one fails.", "`nearest_free(request)` breaks an exact-distance tie toward the lower space number."),
    TaskSpec("bst-exam-score-index", "ExamScoreIndex", "scores", "record_score", "remove_score", "has_score", "score_below", "score_at_or_above", "scores", "percentile", "percentile_boundary", "Track unique positive scores; duplicate score insertion is rejected.", "`percentile_boundary(percent)` returns the ceiling rank at that percent (1 through 100), or no value for invalid input or an empty index."),
    TaskSpec("bst-network-port-registry", "NetworkPortRegistry", "reserved ports", "reserve", "release", "is_reserved", "reserved_before", "reserved_at_or_after", "reserved_ports", "next_free", "next_available_in_range", "Reserve unique positive ports and release only currently reserved ports.", "`next_available_in_range(first, last)` returns the first unreserved positive port in the inclusive range."),
    TaskSpec("bst-document-revision-index", "DocumentRevisionIndex", "revisions", "add_revision", "erase_revision", "has_revision", "revision_before", "revision_at_or_after", "revisions", "range", "revisions_between", "Insert and erase unique positive revision IDs while preserving ordered navigation.", "`revisions_between(first, last)` returns the inclusive revision interval."),
    TaskSpec("bst-ticket-number-index", "TicketNumberIndex", "unresolved tickets", "open_ticket", "close_ticket", "is_unresolved", "ticket_before", "next_unresolved_at_or_after", "unresolved_tickets", "range", "unresolved_between", "Open and close unique positive ticket numbers and find the next unresolved ticket.", "`unresolved_between(first, last)` returns unresolved tickets in the inclusive range."),
)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _extra_declaration(spec: TaskSpec) -> str:
    return {"range": f"std::vector<int> {spec.extra_name}(int first, int last) const;", "count": f"std::size_t {spec.extra_name}() const;", "rank": f"std::size_t {spec.extra_name}(int score) const;", "promote": f"std::optional<int> {spec.extra_name}(int minimum);", "sum": "std::size_t count_inclusive(int first, int last) const;\n    long long sum_inclusive(int first, int last) const;", "nearest": f"std::optional<int> {spec.extra_name}(int request) const;", "floor": f"std::optional<int> {spec.extra_name}(int reserve) const;", "percentile": f"std::optional<int> {spec.extra_name}(int percent) const;", "next_free": f"std::optional<int> {spec.extra_name}(int first, int last) const;"}[spec.extra]


def _header(spec: TaskSpec) -> str:
    return f'''#ifndef {spec.class_name.upper()}_H
#define {spec.class_name.upper()}_H

#include <cstddef>
#include <optional>
#include <set>
#include <vector>

namespace curriculum {{

class {spec.class_name} {{
public:
    bool {spec.add}(int value);
    bool {spec.remove}(int value);
    bool {spec.contains}(int value) const;
    std::optional<int> {spec.lower}(int value) const;
    std::optional<int> {spec.upper}(int value) const;
    std::vector<int> {spec.ordered}() const;
    {_extra_declaration(spec)}

private:
    std::set<int> values_;
}};

}}  // namespace curriculum

#endif
'''


def _reference(spec: TaskSpec) -> str:
    common = f'''#include "task.h"

#include <iterator>

namespace curriculum {{

bool {spec.class_name}::{spec.add}(int value) {{ return value > 0 && values_.insert(value).second; }}
bool {spec.class_name}::{spec.remove}(int value) {{ return values_.erase(value) == 1; }}
bool {spec.class_name}::{spec.contains}(int value) const {{ return values_.count(value) != 0; }}
std::optional<int> {spec.class_name}::{spec.lower}(int value) const {{ const auto it = values_.lower_bound(value); if (it == values_.begin()) return std::nullopt; return *std::prev(it); }}
std::optional<int> {spec.class_name}::{spec.upper}(int value) const {{ const auto it = values_.lower_bound(value); return it == values_.end() ? std::nullopt : std::optional<int>(*it); }}
std::vector<int> {spec.class_name}::{spec.ordered}() const {{ return {{values_.begin(), values_.end()}}; }}
'''
    if spec.extra == "range": extra = f'''std::vector<int> {spec.class_name}::{spec.extra_name}(int first, int last) const {{ std::vector<int> out; if (first > last) return out; for (auto it = values_.lower_bound(first); it != values_.end() && *it <= last; ++it) out.push_back(*it); return out; }}
'''
    elif spec.extra == "count": extra = f"std::size_t {spec.class_name}::{spec.extra_name}() const {{ return values_.size(); }}\n"
    elif spec.extra == "rank": extra = f"std::size_t {spec.class_name}::{spec.extra_name}(int score) const {{ const auto it = values_.find(score); return it == values_.end() ? 0U : static_cast<std::size_t>(std::distance(values_.begin(), it)) + 1U; }}\n"
    elif spec.extra == "promote": extra = f"std::optional<int> {spec.class_name}::{spec.extra_name}(int minimum) {{ const auto it = values_.lower_bound(minimum); if (it == values_.end()) return std::nullopt; const int value = *it; values_.erase(it); return value; }}\n"
    elif spec.extra == "sum": extra = f"std::size_t {spec.class_name}::count_inclusive(int first, int last) const {{ if (first > last) return 0; return static_cast<std::size_t>(std::distance(values_.lower_bound(first), values_.upper_bound(last))); }}\nlong long {spec.class_name}::sum_inclusive(int first, int last) const {{ long long total = 0; if (first > last) return total; for (auto it = values_.lower_bound(first); it != values_.end() && *it <= last; ++it) total += *it; return total; }}\n"
    elif spec.extra == "nearest": extra = f"std::optional<int> {spec.class_name}::{spec.extra_name}(int request) const {{ if (values_.empty()) return std::nullopt; const auto upper = values_.lower_bound(request); if (upper == values_.begin()) return *upper; if (upper == values_.end()) return *std::prev(upper); const int lower = *std::prev(upper); return request - lower <= *upper - request ? lower : *upper; }}\n"
    elif spec.extra == "floor": extra = f"std::optional<int> {spec.class_name}::{spec.extra_name}(int reserve) const {{ const auto it = values_.lower_bound(reserve); if (it == values_.begin()) return std::nullopt; return *std::prev(it); }}\n"
    elif spec.extra == "percentile": extra = f"std::optional<int> {spec.class_name}::{spec.extra_name}(int percent) const {{ if (percent < 1 || percent > 100 || values_.empty()) return std::nullopt; const std::size_t rank = (values_.size() * static_cast<std::size_t>(percent) + 99U) / 100U; return *std::next(values_.begin(), static_cast<long>(rank - 1U)); }}\n"
    else: extra = f"std::optional<int> {spec.class_name}::{spec.extra_name}(int first, int last) const {{ if (first <= 0 || first > last) return std::nullopt; int candidate = first; for (auto it = values_.lower_bound(first); it != values_.end() && *it <= last; ++it) {{ if (*it != candidate) return candidate; if (candidate == last) return std::nullopt; ++candidate; }} return candidate <= last ? std::optional<int>(candidate) : std::nullopt; }}\n"
    return common + extra + "\n}  // namespace curriculum\n"


def _starter(spec: TaskSpec) -> str:
    return f'''#include "task.h"

namespace curriculum {{

bool {spec.class_name}::{spec.add}(int) {{ return false; }}
bool {spec.class_name}::{spec.remove}(int) {{ return false; }}
bool {spec.class_name}::{spec.contains}(int) const {{ return false; }}
std::optional<int> {spec.class_name}::{spec.lower}(int) const {{ return std::nullopt; }}
std::optional<int> {spec.class_name}::{spec.upper}(int) const {{ return std::nullopt; }}
std::vector<int> {spec.class_name}::{spec.ordered}() const {{ return {{}}; }}

}}  // namespace curriculum
'''


def _test(spec: TaskSpec, hidden: bool) -> str:
    extra = {"range": f"check(index.{spec.extra_name}(15, 35) == std::vector<int>{{20, 30}}); check(index.{spec.extra_name}(40, 10).empty());", "count": f"check(index.{spec.extra_name}() == 4U);", "rank": f"check(index.{spec.extra_name}(30) == 3U); check(index.{spec.extra_name}(31) == 0U);", "promote": f"check(index.{spec.extra_name}(25) == std::optional<int>(30)); check(!index.{spec.contains}(30));", "sum": "check(index.count_inclusive(15, 35) == 2U); check(index.sum_inclusive(15, 35) == 50);", "nearest": f"check(index.{spec.extra_name}(25) == std::optional<int>(20)); check(index.{spec.extra_name}(39) == std::optional<int>(40));", "floor": f"check(index.{spec.extra_name}(30) == std::optional<int>(20)); check(!index.{spec.extra_name}(10));", "percentile": f"check(index.{spec.extra_name}(50) == std::optional<int>(20)); check(!index.{spec.extra_name}(0));", "next_free": f"check(index.{spec.extra_name}(10, 12) == std::optional<int>(11)); check(!index.{spec.extra_name}(12, 10));"}[spec.extra]
    trace = ""
    if hidden: trace = f'''\n    curriculum::{spec.class_name} trace_index; std::set<int> oracle;
    for (int step = 1; step <= 180; ++step) {{ const int value = (step * 37) % 97 + 1; const bool insert = step % 3 != 0; check((insert ? trace_index.{spec.add}(value) : trace_index.{spec.remove}(value)) == (insert ? oracle.insert(value).second : oracle.erase(value) == 1)); check(trace_index.{spec.ordered}() == std::vector<int>(oracle.begin(), oracle.end())); }}'''
    return f'''#include "task.h"

#include <optional>
#include <set>
#include <vector>

int main() {{
    curriculum::{spec.class_name} index; int failures = 0; const auto check = [&](bool value) {{ if (!value) ++failures; }};
    check(!index.{spec.add}(0)); check(index.{spec.add}(20)); check(index.{spec.add}(10)); check(index.{spec.add}(30)); check(index.{spec.add}(40)); check(!index.{spec.add}(20));
    check(index.{spec.lower}(10) == std::nullopt); check(index.{spec.lower}(25) == std::optional<int>(20)); check(index.{spec.upper}(25) == std::optional<int>(30)); check(!index.{spec.upper}(41));
    check(index.{spec.ordered}() == std::vector<int>{{10, 20, 30, 40}}); {extra}
    check(index.{spec.remove}(40)); check(!index.{spec.remove}(40)); check(!index.{spec.contains}(40));{trace}
    return failures == 0 ? 0 : 1;
}}
'''


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(binary_search_tree_curriculum LANGUAGES CXX)
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
add_custom_target(test_task ALL DEPENDS task_visible task_hidden COMMAND ${CMAKE_CTEST_COMMAND} --output-on-failure)
'''


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    roots: list[Path] = []
    for spec in TASKS:
        root = out / spec.task_id; header = _header(spec)
        config = {"authors": ["w8-biayn"], "blurb": spec.contract, "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": spec.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1, "benchmark_separation": "Not derived from the official Aider Polyglot binary-search-tree task; domain API and observable contract are independently authored."}
        files = {".docs/introduction.md": f"# {spec.class_name}\n\nA newly authored local ordered-index diagnostic task about {spec.noun}.\n", ".docs/instructions.md": f"# Instructions\n\nImplement `{spec.class_name}`. {spec.contract} Values must be positive integers. Insertion rejects duplicates; removal rejects absent values without changing state. `{spec.lower}(value)` returns the greatest stored value strictly below `value`; `{spec.upper}(value)` returns the least stored value at or above it. `{spec.ordered}()` is strictly ascending. {spec.extra_contract}\n", ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": "[visible]\ndescription = \"domain API, duplicate policy, and ordered navigation\"\n\n[hidden]\ndescription = \"empty and singleton boundaries, deletion, range/aggregate behavior, and randomized ordered-index traces\"\n", "task.h": header, "task.cpp": _starter(spec), ".meta/example.h": header, ".meta/example.cpp": _reference(spec), "task_visible_test.cpp": _test(spec, False), ".meta/task_hidden_test.cpp": _test(spec, True), "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items(): _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    for root in (out / spec.task_id for spec in TASKS):
        with tempfile.TemporaryDirectory(prefix="bst-curriculum-") as temporary:
            copied = Path(temporary) / root.name; shutil.copytree(root, copied); reference = copied / ".meta" / "example.cpp"
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={reference}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format binary-search-tree curriculum tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT); parser.add_argument("--force", action="store_true"); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv); roots = build(args.out, args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} BST curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
