"""Materialize newly authored local AVL/red-black Aider curriculum tasks."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from typing import Sequence

from w8_biayn.integrations import moonlight_binary_search_tree_aider_tasks as ordered

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dsa/balanced-search-tree")
CURRICULUM = "docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_BALANCED_SEARCH_TREE_CURRICULUM.md"
TaskSpec = ordered.TaskSpec

# Every API is a domain contract, not a renamed textbook node interface.  The
# reference uses std::set as an independent ordered balanced-index oracle.
TASKS: tuple[TaskSpec, ...] = (
    TaskSpec("avl-live-leaderboard", "LiveLeaderboard", "unique player scores", "record_score", "remove_score", "has_score", "score_below", "score_at_or_above", "scores", "rank", "rank_of", "Record and remove unique positive scores while reporting an ascending rank.", "`rank_of(score)` is one-based, or zero when the score is absent."),
    TaskSpec("avl-api-rate-limits", "ApiRateLimits", "active rate thresholds", "activate_limit", "expire_limit", "is_active", "limit_below", "limit_at_or_above", "active_limits", "range", "limits_in_window", "Activate unique positive request-rate limits and expire only active values.", "`limits_in_window(first, last)` returns active thresholds in the inclusive window."),
    TaskSpec("avl-appointment-slots", "AppointmentSlots", "available slots", "release_slot", "reserve_slot", "is_available", "slot_before", "slot_at_or_after", "available_slots", "nearest", "nearest_available", "Release unique positive appointment slots and reserve only slots that are available.", "`nearest_available(request)` breaks equal-distance ties toward the earlier slot."),
    TaskSpec("avl-inventory-restock", "InventoryRestock", "reorder levels", "add_reorder_level", "retire_reorder_level", "has_reorder_level", "level_below", "level_at_or_above", "reorder_levels", "nearest", "closest_level_meeting", "Maintain unique positive reorder levels and locate the closest level to a demand.", "`closest_level_meeting(demand)` prefers the lower value on an equal-distance tie."),
    TaskSpec("avl-memory-free-ranges", "MemoryFreeRanges", "free block starts", "release_block", "allocate_block", "is_free_block", "block_before", "block_at_or_after", "free_block_starts", "range", "blocks_in_range", "Track unique positive free block starts; allocation removes one exact start and release restores it.", "`blocks_in_range(first, last)` reports free starts in the inclusive address range."),
    TaskSpec("avl-coupon-thresholds", "CouponThresholds", "coupon thresholds", "add_threshold", "retire_threshold", "has_threshold", "threshold_below", "threshold_at_or_above", "thresholds", "floor", "best_threshold_below", "Maintain unique positive spending thresholds and retire only existing rules.", "`best_threshold_below(budget)` is strictly below the budget."),
    TaskSpec("avl-game-matchmaking", "GameMatchmaking", "waiting ratings", "join_rating", "leave_rating", "is_waiting", "rating_below", "rating_at_or_above", "waiting_ratings", "nearest", "closest_compatible", "Join and leave unique positive ratings while locating a closest compatible opponent.", "`closest_compatible(rating)` prefers the lower rating on an equal-distance tie."),
    TaskSpec("avl-energy-tariffs", "EnergyTariffs", "tariff breakpoints", "set_breakpoint", "remove_breakpoint", "has_breakpoint", "breakpoint_below", "breakpoint_at_or_above", "breakpoints", "floor", "active_tariff_before", "Store unique positive tariff breakpoints and resolve the active breakpoint strictly before usage.", "`active_tariff_before(usage)` returns no breakpoint at the first boundary."),
    TaskSpec("avl-shipping-weight-bands", "ShippingWeightBands", "weight boundaries", "add_boundary", "remove_boundary", "has_boundary", "boundary_below", "boundary_at_or_above", "boundaries", "range", "boundaries_in_band", "Maintain unique positive shipping-weight boundaries.", "`boundaries_in_band(first, last)` returns every inclusive boundary."),
    TaskSpec("avl-library-holds", "LibraryHolds", "hold priorities", "place_hold", "cancel_hold", "has_hold", "priority_below", "priority_at_or_above", "priorities", "promote", "next_eligible", "Place or cancel unique positive hold priorities.", "`next_eligible(minimum)` removes and returns the smallest priority at least `minimum`."),
    TaskSpec("rb-order-book", "OrderBook", "bid levels", "add_bid", "cancel_bid", "has_bid", "bid_below", "bid_at_or_above", "bid_levels", "floor", "best_bid_below", "Add and cancel unique positive bid levels in an order book.", "`best_bid_below(limit)` excludes a bid exactly at the limit."),
    TaskSpec("rb-file-version-index", "FileVersionIndex", "file revisions", "store_revision", "erase_revision", "has_revision", "revision_before", "revision_at_or_after", "revisions", "range", "revisions_in_range", "Store and erase unique positive file revision IDs.", "`revisions_in_range(first, last)` returns the inclusive version interval."),
    TaskSpec("rb-reservation-directory", "ReservationDirectory", "booking codes", "allocate_code", "release_code", "has_booking", "booking_before", "booking_at_or_after", "booking_codes", "nearest", "nearest_booking", "Allocate and release unique positive confirmation codes.", "`nearest_booking(request)` prefers the lower code on an equal-distance tie."),
    TaskSpec("rb-medication-schedule", "MedicationSchedule", "dose times", "schedule_dose", "cancel_dose", "has_dose", "dose_before", "dose_at_or_after", "dose_times", "range", "doses_in_window", "Schedule and cancel unique positive dose times.", "`doses_in_window(first, last)` returns all doses in the inclusive window."),
    TaskSpec("rb-access-control-rules", "AccessControlRules", "rule IDs", "add_rule", "revoke_rule", "has_rule", "rule_below", "rule_at_or_above", "rule_ids", "floor", "highest_matching_rule", "Add and revoke unique positive access-control rule IDs.", "`highest_matching_rule(request)` returns the greatest rule strictly below the request."),
    TaskSpec("rb-cargo-manifest", "CargoManifest", "cargo IDs", "add_cargo", "remove_cargo", "has_cargo", "cargo_before", "cargo_at_or_after", "cargo_ids", "range", "cargo_in_range", "Add and remove unique positive cargo IDs.", "`cargo_in_range(first, last)` returns IDs in the inclusive manifest slice."),
    TaskSpec("rb-metric-percentiles", "MetricPercentiles", "metric observations", "record_observation", "remove_observation", "has_observation", "observation_below", "observation_at_or_above", "observations", "percentile", "percentile_boundary", "Maintain unique positive observations for percentile lookup.", "`percentile_boundary(percent)` uses the ceiling rank from 1 through 100."),
    TaskSpec("rb-travel-fare-table", "TravelFareTable", "fare tiers", "add_fare", "remove_fare", "has_fare", "fare_below", "fare_at_or_above", "fare_tiers", "floor", "best_fare_below", "Maintain unique positive fare tiers and choose the best fare under a budget.", "`best_fare_below(budget)` is strictly below the budget."),
    TaskSpec("rb-audit-event-index", "AuditEventIndex", "audit event IDs", "record_event", "redact_event", "has_event", "event_before", "event_at_or_after", "event_ids", "range", "events_in_range", "Record and redact unique positive audit event IDs.", "`events_in_range(first, last)` returns the inclusive event range."),
    TaskSpec("rb-support-escalations", "SupportEscalations", "escalation priorities", "open_escalation", "close_escalation", "has_escalation", "priority_below", "priority_at_or_above", "priorities", "promote", "next_case", "Open and close unique positive escalation priorities.", "`next_case(minimum)` removes and returns the smallest eligible priority."),
)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force: raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content, encoding="utf-8")


def _hidden_test(spec: TaskSpec) -> str:
    # The sequences named below trigger LL/RR/LR/RL insertion shapes in an AVL
    # implementation and deletion cases in either AVL or red-black internals.
    rotations = f'''\n    for (const std::vector<int>& sequence : std::vector<std::vector<int>>{{{{30, 20, 10}}, {{10, 20, 30}}, {{30, 10, 20}}, {{10, 30, 20}}}}) {{
        curriculum::{spec.class_name} rebalance_case;
        for (const int value : sequence) check(rebalance_case.{spec.add}(value));
        check(rebalance_case.{spec.remove}(sequence[1]));
        check(!rebalance_case.{spec.contains}(sequence[1]));
    }}
'''
    return ordered._test(spec, True).replace(
        "    return failures == 0 ? 0 : 1;", rotations + "    return failures == 0 ? 0 : 1;"
    )


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    roots: list[Path] = []
    for spec in TASKS:
        root = out / spec.task_id; header = ordered._header(spec); tree_kind = "AVL" if spec.task_id.startswith("avl-") else "red-black"
        config = {"authors": ["w8-biayn"], "blurb": spec.contract, "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": spec.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1, "tree_curriculum": tree_kind, "benchmark_separation": "Not derived from the official Aider Polyglot binary-search-tree task; domain API and observable contract are independently authored."}
        files = {".docs/introduction.md": f"# {spec.class_name}\n\nA newly authored local {tree_kind} ordered-index diagnostic about {spec.noun}.\n", ".docs/instructions.md": f"# Instructions\n\nImplement `{spec.class_name}`. {spec.contract} Values must be positive. Insertions reject duplicates and removals reject stale values without changing state. `{spec.lower}` is strict predecessor, `{spec.upper}` is ceiling, and `{spec.ordered}()` is strictly ascending. {spec.extra_contract}\n", ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": f"[visible]\ndescription = \"{tree_kind} domain operations, duplicates, and ordered queries\"\n\n[hidden]\ndescription = \"LL/RR/LR/RL insertion sequences, deletion cases, empty/singleton boundaries, and randomized sorted-oracle mutations\"\n", "task.h": header, "task.cpp": ordered._starter(spec), ".meta/example.h": header, ".meta/example.cpp": ordered._reference(spec), "task_visible_test.cpp": ordered._test(spec, False), ".meta/task_hidden_test.cpp": _hidden_test(spec), "CMakeLists.txt": ordered._cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items(): _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None: raise RuntimeError("verification requires cmake and c++")
    for root in (out / spec.task_id for spec in TASKS):
        with tempfile.TemporaryDirectory(prefix="balanced-tree-") as temporary:
            copied = Path(temporary) / root.name; shutil.copytree(root, copied); reference = copied / ".meta" / "example.cpp"
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={reference}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format balanced-search-tree curriculum tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT); parser.add_argument("--force", action="store_true"); parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv); roots = build(args.out, args.force)
    if args.verify: verify(args.out)
    print(f"Wrote {len(roots)} balanced-tree curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__": raise SystemExit(main())
