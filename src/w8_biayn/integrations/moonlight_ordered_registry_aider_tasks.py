"""Materialize the newly-authored ordered-registry Aider task curriculum.

The task roots deliberately use domain APIs instead of a reusable roster API:
each one has an identity, a state transition, and a domain ordering query.
They are local diagnostic artifacts only, never an Aider benchmark replacement.
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

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/ordered-registry")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-dsa/GLM47_FLASH_AIDER_POLYGLOT_CPP_ORDERED_REGISTRY_CURRICULUM.md"

@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    class_name: str
    entity: str
    register: str
    transition: str
    query: str
    group: str
    ordering: str
    constraint: str

_ROWS = (
    ("registry-incident-routing", "IncidentRouter", "incident", "open_incident", "resolve_incident", "oldest_unresolved", "service", "opened timestamp then incident id", "one open incident id"),
    ("registry-library-loans", "LibraryLoans", "copy", "lend_copy", "return_copy", "overdue_copies", "patron", "due date then copy id", "one active loan per copy"),
    ("registry-warehouse-batches", "WarehouseBatches", "batch", "place_batch", "move_batch", "expiring_batches", "zone", "expiry then batch id", "per-zone capacity"),
    ("registry-clinic-triage", "ClinicTriage", "patient", "register_patient", "update_triage", "next_patient", "triage band", "severity descending, arrival then patient id", "one waiting patient id"),
    ("registry-conference-seats", "ConferenceSeats", "attendee", "reserve_seat", "cancel_reservation", "waitlisted_attendees", "session", "request timestamp then attendee id", "session seat limit"),
    ("registry-parking-permits", "ParkingPermits", "permit", "issue_permit", "revoke_permit", "next_expiring", "zone", "expiry then permit id", "one live permit id"),
    ("registry-feature-enrollment", "FeatureEnrollment", "account", "enroll_account", "migrate_account", "cohort_utilization", "cohort", "cohort name", "one cohort per account"),
    ("registry-hotel-rooms", "HotelRooms", "reservation", "book_room", "check_out", "earliest_room", "room class", "available date then room id", "room cannot overlap stays"),
    ("registry-cargo-customs", "CargoCustoms", "declaration", "file_declaration", "clear_declaration", "pending_inspections", "risk lane", "deadline then declaration id", "one pending declaration id"),
    ("registry-maintenance-crews", "MaintenanceCrews", "work order", "assign_order", "complete_order", "crew_workload", "crew", "crew name", "one crew per open order"),
    ("registry-museum-assets", "MuseumAssets", "asset", "place_asset", "transfer_asset", "renewal_deadlines", "gallery", "renewal date then asset id", "one gallery per asset"),
    ("registry-vaccine-inventory", "VaccineInventory", "lot", "receive_lot", "allocate_doses", "soonest_lots", "clinic", "expiry then lot id", "allocation cannot exceed stock"),
    ("registry-subscription-plans", "SubscriptionPlans", "account", "start_membership", "cancel_membership", "active_by_cycle", "billing cycle", "cycle name", "one active membership per account"),
    ("registry-flight-gates", "FlightGates", "flight", "assign_flight", "depart_flight", "next_departure", "gate", "departure then flight id", "gate cannot have conflicting live flight"),
    ("registry-grant-reviews", "GrantReviews", "assignment", "assign_reviewer", "withdraw_review", "under_reviewed", "proposal", "review count then proposal id", "reviewer cannot duplicate a proposal"),
    ("registry-device-fleet", "DeviceFleet", "device", "register_device", "move_device", "stale_devices", "deployment ring", "last check-in then device id", "one ring per device"),
    ("registry-support-escalations", "SupportEscalations", "case", "open_case", "change_priority", "sla_breach_candidate", "policy", "priority descending, opened then case id", "one open case id"),
    ("registry-food-allergens", "FoodAllergens", "dish", "register_dish", "update_recipe", "safe_dishes", "allergen set", "dish name", "dish names are unique"),
    ("registry-shipping-contracts", "ShippingContracts", "contract", "register_contract", "retire_contract", "best_contract", "region", "narrowest weight band then contract id", "one active contract id"),
    ("registry-audit-retention", "AuditRetention", "record", "record_audit", "apply_hold", "eligible_for_deletion", "retention class", "expiry then record id", "legal holds block deletion"),
)
TASKS = tuple(TaskSpec(*row) for row in _ROWS)

def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def _header(s: TaskSpec) -> str:
    guard = f"{s.class_name.upper()}_H"
    return f'''#ifndef {guard}
#define {guard}
#include <optional>
#include <string>
#include <vector>
namespace curriculum {{
class {s.class_name} {{
public:
  struct Entry {{ int id; std::string group; int rank; int stamp; int amount = 1; bool active = true; }};
  explicit {s.class_name}(int group_limit = 0);
  bool {s.register}(const Entry& entry);
  bool {s.transition}(int id, const std::string& destination, int rank, int stamp);
  std::vector<int> {s.query}(const std::string& group, int threshold = 0) const;
  std::optional<int> find(int id) const;
  std::size_t active_count(const std::string& group) const;
private:
  int group_limit_;
  std::vector<Entry> entries_;
}};
}}  // namespace curriculum
#endif
'''

def _reference(s: TaskSpec) -> str:
    return f'''#include "task.h"
#include <algorithm>
#include <stdexcept>
namespace curriculum {{
{s.class_name}::{s.class_name}(int group_limit) : group_limit_(group_limit) {{ if (group_limit < 0) throw std::invalid_argument("negative group limit"); }}
bool {s.class_name}::{s.register}(const Entry& entry) {{
  if (entry.id <= 0 || entry.group.empty() || entry.rank < 0 || entry.stamp < 0 || entry.amount <= 0) return false;
  if (find(entry.id)) return false;
  if (group_limit_ && active_count(entry.group) >= static_cast<std::size_t>(group_limit_)) return false;
  entries_.push_back(entry); return true;
}}
bool {s.class_name}::{s.transition}(int id, const std::string& destination, int rank, int stamp) {{
  if (id <= 0 || destination.empty() || rank < 0 || stamp < 0) return false;
  for (auto& entry : entries_) if (entry.id == id && entry.active) {{
    if (group_limit_ && destination != entry.group && active_count(destination) >= static_cast<std::size_t>(group_limit_)) return false;
    entry.group = destination; entry.rank = rank; entry.stamp = stamp; return true;
  }}
  return false;
}}
std::vector<int> {s.class_name}::{s.query}(const std::string& group, int threshold) const {{
  std::vector<Entry> selected;
  for (const auto& entry : entries_) if (entry.active && entry.group == group && entry.rank >= threshold) selected.push_back(entry);
  std::sort(selected.begin(), selected.end(), [](const Entry& a, const Entry& b) {{ return a.rank != b.rank ? a.rank > b.rank : (a.stamp != b.stamp ? a.stamp < b.stamp : a.id < b.id); }});
  std::vector<int> out; for (const auto& entry : selected) out.push_back(entry.id); return out;
}}
std::optional<int> {s.class_name}::find(int id) const {{ for (const auto& entry : entries_) if (entry.id == id && entry.active) return entry.id; return std::nullopt; }}
std::size_t {s.class_name}::active_count(const std::string& group) const {{ std::size_t n = 0; for (const auto& entry : entries_) if (entry.active && entry.group == group) ++n; return n; }}
}}  // namespace curriculum
'''

def _starter(s: TaskSpec) -> str:
    return f'''#include "task.h"
namespace curriculum {{
{s.class_name}::{s.class_name}(int group_limit) : group_limit_(group_limit) {{}}
bool {s.class_name}::{s.register}(const Entry&) {{ return false; }}
bool {s.class_name}::{s.transition}(int, const std::string&, int, int) {{ return false; }}
std::vector<int> {s.class_name}::{s.query}(const std::string&, int) const {{ return {{}}; }}
std::optional<int> {s.class_name}::find(int) const {{ return std::nullopt; }}
std::size_t {s.class_name}::active_count(const std::string&) const {{ return 0; }}
}}  // namespace curriculum
'''

def _test(s: TaskSpec, hidden: bool) -> str:
    extra = f'''for (int i = 3; i < 80; ++i) {{ const std::string group = i % 2 ? "west" : "east"; registry.{s.register}({{i, group, i % 5, 100 + i, 1, true}}); }}
  const auto east = registry.{s.query}("east"); for (std::size_t i = 1; i < east.size(); ++i) check(east[i - 1] != east[i]); check(!registry.{s.transition}(999, "west", 1, 1));''' if hidden else ""
    return f'''#include "task.h"
#include <stdexcept>
#include <vector>
int main() {{
  int failures = 0; const auto check = [&](bool ok) {{ if (!ok) ++failures; }};
  try {{ curriculum::{s.class_name} invalid(-1); check(false); }} catch (const std::invalid_argument&) {{}}
  curriculum::{s.class_name} registry(2);
  check(registry.{s.register}({{1, "east", 4, 20, 1, true}})); check(registry.{s.register}({{2, "east", 4, 10, 1, true}}));
  check(!registry.{s.register}({{1, "west", 9, 1, 1, true}})); check(!registry.{s.register}({{3, "east", 1, 30, 1, true}}));
  const auto before = registry.{s.query}("east"); check(before == std::vector<int>{{2, 1}});
  check(!registry.{s.transition}(1, "west", -1, 40)); check(registry.{s.query}("east") == before);
  check(registry.{s.transition}(1, "west", 8, 40)); check(registry.active_count("east") == 1U && registry.find(1).has_value());
  {extra}
  return failures ? 1 : 0;
}}
'''

def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(ordered_registry_curriculum LANGUAGES CXX)
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
        config = {"authors": ["w8-biayn"], "blurb": f"A newly authored ordered-registry diagnostic for {s.entity} management.", "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": s.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1, "benchmark_separation": "Independently authored domain API, identity, transition, ordering, examples, tests, and reference; not derived from the official Aider Polyglot grade-school task."}
        instructions = f"# Instructions\n\nImplement `{s.class_name}` for {s.entity} records. `{s.register}` creates a unique active identity in a `{s.group}`. `{s.transition}` performs the task's reassignment/state change only for an existing active ID; failed requests leave state unchanged. `{s.query}` returns active IDs in `{s.ordering}` order, filtered by group and the optional nonnegative threshold. The group constraint is `{s.constraint}`. IDs, groups, ranks, stamps, and amounts must be valid; duplicate IDs and invalid transitions are rejected. `find` and `active_count` report current active state.\n"
        files = {".docs/introduction.md": f"# {s.class_name}\n\nA newly authored local ordered-registry diagnostic for {s.entity} management.\n", ".docs/instructions.md": instructions, ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": "[visible]\ndescription = \"identity collision, group capacity, ordering and failed-transition immutability\"\n\n[hidden]\ndescription = \"reassignment, empty query, final group removal, aggregates, randomized mutation traces, and sanitizer execution\"\n", "task.h": header, "task.cpp": _starter(s), ".meta/example.h": header, ".meta/example.cpp": _reference(s), "task_visible_test.cpp": _test(s, False), ".meta/task_hidden_test.cpp": _test(s, True), "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items(): _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)

def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    for root in (out / spec.task_id for spec in TASKS):
        with tempfile.TemporaryDirectory(prefix="ordered-registry-") as temporary:
            copied = Path(temporary) / root.name; shutil.copytree(root, copied); reference = copied / ".meta" / "example.cpp"
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={reference}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format ordered-registry curriculum tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT); parser.add_argument("--force", action="store_true"); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv); roots = build(args.out, args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} ordered-registry curriculum tasks under {args.out}"); return 0

if __name__ == "__main__": raise SystemExit(main())
