"""Create and verify the 90-root weekday/recurrence/business-day expansion."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)

DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/time-date/"
    "weekday-recurrence-business-day"
)
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-clock-tasks/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_WEEKDAY_RECURRENCE_BUSINESS_DAY_"
    "EXPANSION_CURRICULUM.md"
)
FAMILY_SPEC = Path(
    "docs/aider-tasks-spec/aider-dates-and-clocks/"
    "weekday-recurrence-business-day-expansion.md"
)
GENERATOR_PATH = Path(
    "src/w8_biayn/integrations/"
    "moonlight_weekday_recurrence_business_day_expansion.py"
)
TEST_PATH = Path("tests/test_moonlight_weekday_recurrence_business_day_expansion.py")
FAMILY_ID = "aider-expansion-v1-weekday-recurrence-business-day-v1"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
OFFICIAL_HOLDOUTS = frozenset(
    {
        "all-your-base", "allergies", "bank-account", "binary-search-tree",
        "circular-buffer", "clock", "complex-numbers", "crypto-square", "diamond",
        "dnd-character", "gigasecond", "grade-school", "kindergarten-garden",
        "knapsack", "linked-list", "meetup", "parallel-letter-frequency",
        "perfect-numbers", "phone-number", "queen-attack", "robot-name", "space-age",
        "spiral-matrix", "sublist", "yacht", "zebra-puzzle",
    }
)
HARD_DIMENSIONS = (
    "public_api",
    "owned_state_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
)


@dataclass(frozen=True)
class Operation:
    slug: str
    title: str
    mechanism: str
    output: str


@dataclass(frozen=True)
class Case:
    group: str
    operation: Operation
    ordinal: int

    @property
    def task_id(self) -> str:
        return f"{self.group}-{self.operation.slug}"

    @property
    def title(self) -> str:
        prefix = {
            "weekday": "Weekday",
            "recurrence": "Recurrence",
            "business-day": "Business Day",
        }[self.group]
        return f"{prefix} {self.operation.title}"


OPERATIONS = (
    Operation("first-occurrence", "First Occurrence", "bounded first-occurrence selection", "the first eligible serial day, or an empty vector"),
    Operation("final-occurrence", "Final Occurrence", "bounded final-occurrence selection", "the final eligible serial day, or an empty vector"),
    Operation("nth-occurrence", "Nth Occurrence", "one-based nth-occurrence selection", "the parameter-th eligible serial day, or an empty vector"),
    Operation("nth-from-end", "Nth From End", "one-based reverse occurrence selection", "the parameter-th eligible serial day counted from the end, or an empty vector"),
    Operation("occurrence-exists", "Occurrence Existence", "bounded occurrence-existence decision", "a one-element 1/0 existence vector for the parameter-th occurrence"),
    Operation("rolling-density", "Rolling Density", "fixed-width rolling density", "window hit counts"),
    Operation("bounded-batches", "Bounded Batches", "bounded batch endpoint partition", "batch endpoint pairs"),
    Operation("stable-overlay", "Stable Overlay", "stable two-stream overlay", "tagged merged serials"),
    Operation("exclusion-intersection", "Exclusion Intersection", "raw-rule/exclusion intersection", "excluded rule matches"),
    Operation("symmetric-calendar", "Symmetric Calendar", "symmetric difference of rule and exception calendars", "tagged symmetric difference"),
    Operation("forward-expansion", "Forward Expansion", "bounded forward occurrence expansion", "expanded serial days"),
    Operation("anchored-shift", "Anchored Shift", "checked anchor shift with stable deduplication", "shifted serial days"),
    Operation("nearest-index", "Nearest Index", "deterministic exhaustive nearest eligible lookup", "query/day pairs"),
    Operation("exception-ranks", "Exception Ranks", "lower-bound rank queries", "exception/rank pairs"),
    Operation("weekday-quota", "Weekday Quota", "per-weekday bounded quota allocation", "quota-admitted days"),
    Operation("capacity-spill", "Capacity Spill", "bucket capacity with explicit spill ledger", "day/spill-rank pairs"),
    Operation("transition-edges", "Transition Edges", "eligibility transition detection", "transition serial days"),
    Operation("longest-streak", "Longest Streak", "longest consecutive eligible streak", "start/length pair"),
    Operation("cyclic-rotation", "Cyclic Rotation", "normalized cyclic rotation", "rotated eligible sequence"),
    Operation("period-buckets", "Period Buckets", "floor-division period aggregation", "bucket/count pairs"),
    Operation("pair-distances", "Pair Distances", "adjacent eligible-pair distance scan", "left/distance pairs"),
    Operation("missing-slots", "Missing Slots", "bounded missing-slot reconstruction", "missing expected serial days"),
    Operation("arithmetic-compression", "Arithmetic Compression", "maximal arithmetic-run compression", "start/step/count triples"),
    Operation("exception-substitution", "Exception Substitution", "monotone exception replacement", "substituted serial days"),
    Operation("collision-resolution", "Collision Resolution", "forward open-address collision resolution", "collision-free shifted days"),
    Operation("checkpoint-sampling", "Checkpoint Sampling", "ordinal checkpoint sampling", "every kth eligible day"),
    Operation("coverage-union", "Coverage Union", "interval expansion and union", "merged interval endpoint pairs"),
    Operation("parity-lanes", "Parity Lanes", "stable even/odd lane partition", "even lane then odd lane"),
    Operation("distance-score", "Distance Score", "bounded distance-weight scoring", "day/score pairs"),
    Operation("dual-rule-consensus", "Dual Rule Consensus", "conjunctive primary/secondary calendar consensus", "consensus serial days"),
)

OPERATION_CONTRACTS = (
    "Return only the first eligible day; return an engaged empty vector when no occurrence exists.",
    "Return only the final eligible day; return an engaged empty vector when no occurrence exists.",
    "Treat parameter as a one-based ordinal and return that eligible occurrence; zero is invalid and an absent ordinal returns an engaged empty vector.",
    "Treat parameter as a one-based ordinal from the end and return that occurrence; an absent ordinal returns an engaged empty vector.",
    "Return {1} exactly when at least parameter eligible occurrences exist, otherwise return {0}.",
    "For every day in the inclusive window return the number of eligible days in the trailing parameter-day window, including the current day.",
    "Partition eligible days into stable groups of at most parameter and flatten each group's first and final day; a singleton contributes the same day twice.",
    "Merge eligible days tagged as 2*day with exclusions tagged as 2*day+1, then sort the tagged integers ascending.",
    "Return raw rule matches that are also exclusions, in ascending serial-day order.",
    "Return the symmetric difference: nonexcluded raw matches tagged 2*day and exclusions that are not raw matches tagged 2*day+1, sorted ascending.",
    "Expand every eligible day by offsets [0,parameter), then sort and deduplicate the expanded serial days.",
    "Add parameter to every eligible day, then sort and deduplicate; the supported input range guarantees checked int arithmetic.",
    "For each exclusion query in ascending order, return query followed by the closest eligible day; equal distance chooses the earlier day; omit all pairs when no eligible day exists.",
    "For each exclusion query return query followed by the zero-based count of eligible days strictly before it.",
    "Admit at most parameter eligible days for each floor-modulo weekday, preserving ascending day order.",
    "Bucket eligible days by floor(day/7); after parameter admissions in a bucket, emit day followed by its one-based spill rank.",
    "Return each window day whose eligibility differs from the immediately preceding window day; the first day is never a transition.",
    "Return start and length of the longest consecutive eligible streak; ties keep the earlier streak; no streak returns an engaged empty vector.",
    "Rotate the eligible sequence left by parameter modulo its size; an empty sequence stays empty.",
    "Bucket eligible days by mathematical floor(day/parameter) and return ascending bucket/count pairs.",
    "For every adjacent eligible pair return the left day followed by the positive distance to the right day.",
    "Starting at the first eligible day, step by parameter through the final eligible day and return expected slots that are not eligible.",
    "Compress maximal constant-step runs as start, step, count triples; a singleton uses step 0.",
    "For every raw occurrence, repeatedly add parameter while it is excluded; return the sorted deduplicated replacements.",
    "Map each eligible day to floor-modulo parameter and resolve occupied slots by forward open addressing; stop when all parameter slots are occupied.",
    "Return every parameter-th eligible day using one-based occurrence ranks.",
    "Expand each eligible day to the closed integer interval [day,day+parameter], merge touching/overlapping intervals, and flatten start/end pairs.",
    "Return eligible days with even floor-modulo weekday first and odd floor-modulo weekday second, preserving order within each lane.",
    "For each eligible day return day followed by max(0,parameter-abs(day)); the supported range makes abs defined.",
    "Return eligible days whose day+parameter is also a raw rule match, preserving ascending order.",
)
GROUPS = ("weekday", "recurrence", "business-day")
CASES = tuple(
    Case(group, operation, group_index * len(OPERATIONS) + operation_index)
    for group_index, group in enumerate(GROUPS)
    for operation_index, operation in enumerate(OPERATIONS)
)
REPLACED_OPERATION_IDS = {
    "eligible-projection": "first-occurrence",
    "gap-ledger": "final-occurrence",
    "prefix-ranks": "nth-occurrence",
    "run-summary": "nth-from-end",
    "weekday-histogram": "occurrence-exists",
}
REPLACED_TASK_IDS = {
    f"{group}-{old_slug}": f"{group}-{new_slug}"
    for group in GROUPS
    for old_slug, new_slug in REPLACED_OPERATION_IDS.items()
}

CMAKE = r'''cmake_minimum_required(VERSION 3.16)
project(calendar_expansion LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation")
enable_testing()
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
foreach(name visible hidden)
  target_include_directories(task_${name} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(task_${name} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  add_test(NAME ${name} COMMAND task_${name})
endforeach()
'''


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    return _sha(path.read_bytes())


def _tree_hash(root: Path, *, include_state: bool = False) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "not_available"
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if not include_state and ".state" in path.parts:
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _inventory(root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    if not root.is_dir():
        return records
    for config in sorted(root.rglob(".meta/config.json")):
        if ".state" in config.parts:
            continue
        task_root = config.parent.parent
        before_hash = _tree_hash(task_root)
        parsed = json.loads(config.read_text())
        docs = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in sorted((task_root / ".docs").glob("*.md"))
        )
        starters = "\n".join(
            (task_root / relative).read_text(encoding="utf-8", errors="ignore")
            for relative in parsed.get("files", {}).get("solution", [])
            if (task_root / relative).is_file()
        )
        references = "\n".join(
            (task_root / relative).read_text(encoding="utf-8", errors="ignore")
            for relative in parsed.get("files", {}).get("example", [])
            if (task_root / relative).is_file()
        )
        tests = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in sorted(task_root.rglob("*test*"))
            if path.is_file() and path.stat().st_size < 1_000_000
        )
        screen_text = " ".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in sorted(task_root.rglob("*"))
            if path.is_file() and path.stat().st_size < 1_000_000
        )
        after_hash = _tree_hash(task_root)
        if after_hash != before_hash:
            _fail(
                "comparator_inventory_changed",
                f"{task_root} changed while its snapshot was captured",
            )
        records.append(
            {
                "task_id": task_root.name,
                "relative_root": task_root.relative_to(root).as_posix(),
                "tree_hash": after_hash,
                "config_hash": _file_hash(config),
                "prompt_material_hash": _sha((docs + starters).encode()),
                "answer_material_hash": _sha(references.encode()),
                "contract_material_hash": _sha((docs + starters + references + tests).encode()),
                "_screen_text": screen_text,
                "_prompt_material": docs + "\n" + starters,
                "_answer_material": references,
            }
        )
    return records


def _validate_output(out: Path) -> None:
    resolved = out.resolve()
    expansion = EXPANSION_ROOT.resolve()
    if resolved == expansion or expansion not in resolved.parents:
        _fail("unsafe_path", f"output must be a family below {EXPANSION_ROOT}: {out}")
    for forbidden in (LEGACY_ROOT.resolve(), REVERIFY_ROOT.resolve()):
        if resolved == forbidden or forbidden in resolved.parents:
            _fail("unsafe_path", f"existing tree is read-only: {out}")
    cursor = out
    while cursor != EXPANSION_ROOT.parent and cursor != cursor.parent:
        if cursor.is_symlink():
            _fail("unsafe_path", f"symlink component: {cursor}")
        cursor = cursor.parent


def _mod7(value: int) -> int:
    return value % 7


def _raw_selected(case: Case, day: int, primary: int, interval: int) -> bool:
    if case.group == "weekday":
        return _mod7(day) == primary
    if case.group == "recurrence":
        return day >= primary and (day - primary) % interval == 0
    return bool(primary & (1 << _mod7(day)))


def _operation_oracle(
    operation: int,
    days: list[int],
    exclusions: list[int],
    primary: int,
    interval: int,
    parameter: int,
    group: str,
    *,
    apply_exclusions: bool = True,
    prefer_earlier: bool = True,
    invert_rule: bool = False,
) -> list[int]:
    excluded = set(exclusions)
    raw = [_raw_selected(Case(group, OPERATIONS[operation], operation), day, primary, interval) for day in days]
    if invert_rule:
        raw = [not flag for flag in raw]
    chosen = [flag and (day not in excluded or not apply_exclusions) for day, flag in zip(days, raw, strict=True)]
    selected = [day for day, flag in zip(days, chosen, strict=True) if flag]
    p = parameter
    if operation == 0:
        return selected[:1]
    if operation == 1:
        return selected[-1:]
    if operation == 2:
        return selected[p - 1 : p]
    if operation == 3:
        return selected[-p : len(selected) - p + 1] if len(selected) >= p else []
    if operation == 4:
        return [int(len(selected) >= p)]
    if operation == 5:
        return [sum(chosen[max(0, index - p + 1) : index + 1]) for index in range(len(chosen))]
    if operation == 6:
        return [value for index in range(0, len(selected), p) for value in (selected[index], selected[min(index + p - 1, len(selected) - 1)])]
    if operation == 7:
        return sorted([day * 2 for day in selected] + [day * 2 + 1 for day in exclusions])
    if operation == 8:
        return [day for day, flag in zip(days, raw, strict=True) if flag and day in excluded]
    if operation == 9:
        return sorted(([day * 2 for day, flag in zip(days, raw, strict=True) if flag and day not in excluded] + [day * 2 + 1 for day in exclusions if not _raw_selected(Case(group, OPERATIONS[operation], operation), day, primary, interval)]))
    if operation == 10:
        return sorted(set(day + offset for day in selected for offset in range(p)))
    if operation == 11:
        return sorted(set(day + p for day in selected))
    if operation == 12:
        out = []
        for query in exclusions:
            if not selected:
                break
            best = min(selected, key=lambda day: (abs(day - query), day if prefer_earlier else -day))
            out += [query, best]
        return out
    if operation == 13:
        return [value for query in exclusions for value in (query, sum(day < query for day in selected))]
    if operation == 14:
        used = [0] * 7
        out = []
        for day in selected:
            weekday = _mod7(day)
            if used[weekday] < p:
                used[weekday] += 1
                out.append(day)
        return out
    if operation == 15:
        counts: dict[int, int] = {}
        out = []
        for day in selected:
            bucket = day // 7
            counts[bucket] = counts.get(bucket, 0) + 1
            if counts[bucket] > p:
                out += [day, counts[bucket] - p]
        return out
    if operation == 16:
        return [days[index] for index in range(1, len(days)) if chosen[index] != chosen[index - 1]]
    if operation == 17:
        best_start = 0
        best_len = 0
        current_start = 0
        current_len = 0
        for day in days:
            if day in selected and (current_len == 0 or day == current_start + current_len):
                if current_len == 0:
                    current_start = day
                current_len += 1
                if current_len > best_len:
                    best_start, best_len = current_start, current_len
            else:
                current_len = 0
        return [] if best_len == 0 else [best_start, best_len]
    if operation == 18:
        if not selected:
            return []
        shift = p % len(selected)
        return selected[shift:] + selected[:shift]
    if operation == 19:
        buckets: dict[int, int] = {}
        for day in selected:
            bucket = day // p
            buckets[bucket] = buckets.get(bucket, 0) + 1
        return [value for item in sorted(buckets.items()) for value in item]
    if operation == 20:
        return [value for index in range(1, len(selected)) for value in (selected[index - 1], selected[index] - selected[index - 1])]
    if operation == 21:
        if len(selected) < 2:
            return []
        present = set(selected)
        return [day for day in range(selected[0], selected[-1] + 1, p) if day not in present]
    if operation == 22:
        out = []
        index = 0
        while index < len(selected):
            step = selected[index + 1] - selected[index] if index + 1 < len(selected) else 0
            end = index + 1
            while end < len(selected) and selected[end] - selected[end - 1] == step:
                end += 1
            out += [selected[index], step, end - index]
            index = end
        return out
    if operation == 23:
        out = []
        for day, flag in zip(days, raw, strict=True):
            if not flag:
                continue
            replacement = day
            while replacement in excluded:
                replacement += p
            out.append(replacement)
        return sorted(set(out))
    if operation == 24:
        occupied: set[int] = set()
        out = []
        for day in selected:
            candidate = day % p
            while candidate in occupied:
                candidate = (candidate + 1) % p
                if len(occupied) >= p:
                    return out
            occupied.add(candidate)
            out.append(candidate)
        return out
    if operation == 25:
        return [day for index, day in enumerate(selected, 1) if index % p == 0]
    if operation == 26:
        intervals = sorted((day, day + p) for day in selected)
        merged: list[list[int]] = []
        for start, end in intervals:
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        return [value for interval_pair in merged for value in interval_pair]
    if operation == 27:
        return [day for day in selected if _mod7(day) % 2 == 0] + [day for day in selected if _mod7(day) % 2 == 1]
    if operation == 28:
        return [value for day in selected for value in (day, max(0, p - abs(day)))]
    return [day for day in selected if _raw_selected(Case(group, OPERATIONS[operation], operation), day + p, primary, interval)]


def _cpp_vector(values: Iterable[int]) -> str:
    return "{" + ",".join(str(value) for value in values) + "}"


def _api(case: Case) -> str:
    function = case.operation.slug.replace("-", "_")
    return f"std::optional<std::vector<int>> {case.group.replace('-', '_')}_{function}(const CalendarRequest& request)"


def _header(case: Case) -> str:
    function = case.operation.slug.replace("-", "_")
    return f'''#ifndef CALENDAR_TASK_H
#define CALENDAR_TASK_H
#include <optional>
#include <vector>
namespace curriculum {{
struct CalendarRequest {{
  int start_day;
  int end_day;
  std::vector<int> exclusions;
  int primary;
  int interval;
  int parameter;
}};
std::optional<std::vector<int>> {case.group.replace('-', '_')}_{function}(const CalendarRequest& request);
}}
#endif
'''


def _predicate_cpp(case: Case) -> str:
    if case.group == "weekday":
        return "mod7(day)==request.primary"
    if case.group == "recurrence":
        return "day>=request.primary && (static_cast<long long>(day)-request.primary)%request.interval==0"
    return "(request.primary & (1 << mod7(day))) != 0"


def _operation_cpp(index: int) -> str:
    bodies = (
        "for(std::size_t i=0;i<days.size();++i)if(chosen[i]){out.push_back(days[i]);break;}",
        "for(std::size_t i=days.size();i>0;--i)if(chosen[i-1]){out.push_back(days[i-1]);break;}",
        "int rank=0;for(std::size_t i=0;i<days.size();++i)if(chosen[i]&&++rank==p){out.push_back(days[i]);break;}",
        "int rank=0;for(std::size_t i=days.size();i>0;--i)if(chosen[i-1]&&++rank==p){out.push_back(days[i-1]);break;}",
        "int count=0;for(bool flag:chosen)if(flag)++count;out.push_back(count>=p?1:0);",
        "int count=0;for(std::size_t i=0;i<days.size();++i){if(chosen[i])++count;if(i>=static_cast<std::size_t>(p)&&chosen[i-static_cast<std::size_t>(p)])--count;out.push_back(count);}",
        "std::vector<int> selected;for(std::size_t i=0;i<days.size();++i)if(chosen[i])selected.push_back(days[i]);for(std::size_t i=0;i<selected.size();i+=static_cast<std::size_t>(p)){out.push_back(selected[i]);out.push_back(selected[std::min(i+static_cast<std::size_t>(p)-1,selected.size()-1)]);}",
        "for(std::size_t i=0;i<days.size();++i)if(chosen[i])out.push_back(days[i]*2);for(int day:request.exclusions)out.push_back(day*2+1);std::sort(out.begin(),out.end());",
        "for(std::size_t i=0;i<days.size();++i)if(raw[i]&&blocked.count(days[i])!=0U)out.push_back(days[i]);",
        "for(std::size_t i=0;i<days.size();++i)if(raw[i]&&blocked.count(days[i])==0U)out.push_back(days[i]*2);for(int day:request.exclusions)if(!raw_rule(day,request))out.push_back(day*2+1);std::sort(out.begin(),out.end());",
        "for(std::size_t i=0;i<days.size();++i)if(chosen[i])for(int offset=0;offset<p;++offset)out.push_back(days[i]+offset);std::sort(out.begin(),out.end());out.erase(std::unique(out.begin(),out.end()),out.end());",
        "for(std::size_t i=0;i<days.size();++i)if(chosen[i])out.push_back(days[i]+p);std::sort(out.begin(),out.end());out.erase(std::unique(out.begin(),out.end()),out.end());",
        "std::vector<int> selected;for(std::size_t i=0;i<days.size();++i)if(chosen[i])selected.push_back(days[i]);for(int query:request.exclusions){if(selected.empty())break;int best=selected.front();for(int day:selected)if(std::abs(day-query)<std::abs(best-query)||(std::abs(day-query)==std::abs(best-query)&&day<best))best=day;out.push_back(query);out.push_back(best);}",
        "std::vector<int> selected;for(std::size_t i=0;i<days.size();++i)if(chosen[i])selected.push_back(days[i]);for(int query:request.exclusions){out.push_back(query);out.push_back(static_cast<int>(std::lower_bound(selected.begin(),selected.end(),query)-selected.begin()));}",
        "std::array<int,7> used{};for(std::size_t i=0;i<days.size();++i)if(chosen[i]){std::size_t w=static_cast<std::size_t>(mod7(days[i]));if(used[w]<p){++used[w];out.push_back(days[i]);}}",
        "std::map<int,int> counts;for(std::size_t i=0;i<days.size();++i)if(chosen[i]){int count=++counts[floor_div(days[i],7)];if(count>p){out.push_back(days[i]);out.push_back(count-p);}}",
        "for(std::size_t i=1;i<days.size();++i)if(chosen[i]!=chosen[i-1])out.push_back(days[i]);",
        "int best_start=0,best_len=0,current_start=0,current_len=0;for(std::size_t i=0;i<days.size();++i){if(chosen[i]&&(current_len==0||days[i]==current_start+current_len)){if(current_len==0)current_start=days[i];++current_len;if(current_len>best_len){best_start=current_start;best_len=current_len;}}else current_len=0;}if(best_len>0){out.push_back(best_start);out.push_back(best_len);}",
        "for(std::size_t i=0;i<days.size();++i)if(chosen[i])out.push_back(days[i]);if(!out.empty())std::rotate(out.begin(),out.begin()+p%static_cast<int>(out.size()),out.end());",
        "std::map<int,int> buckets;for(std::size_t i=0;i<days.size();++i)if(chosen[i])++buckets[floor_div(days[i],p)];for(const auto& item:buckets){out.push_back(item.first);out.push_back(item.second);}",
        "int prior=0;bool have=false;for(std::size_t i=0;i<days.size();++i)if(chosen[i]){if(have){out.push_back(prior);out.push_back(days[i]-prior);}prior=days[i];have=true;}",
        "std::vector<int> selected;for(std::size_t i=0;i<days.size();++i)if(chosen[i])selected.push_back(days[i]);if(selected.size()>1U){std::set<int> present(selected.begin(),selected.end());for(int day=selected.front();day<=selected.back();day+=p)if(present.count(day)==0U)out.push_back(day);}",
        "std::vector<int> selected;for(std::size_t i=0;i<days.size();++i)if(chosen[i])selected.push_back(days[i]);for(std::size_t i=0;i<selected.size();){int step=i+1<selected.size()?selected[i+1]-selected[i]:0;std::size_t j=i+1;while(j<selected.size()&&selected[j]-selected[j-1]==step)++j;out.push_back(selected[i]);out.push_back(step);out.push_back(static_cast<int>(j-i));i=j;}",
        "for(std::size_t i=0;i<days.size();++i)if(raw[i]){int value=days[i];while(blocked.count(value)!=0U)value+=p;out.push_back(value);}std::sort(out.begin(),out.end());out.erase(std::unique(out.begin(),out.end()),out.end());",
        "std::set<int> occupied;for(std::size_t i=0;i<days.size();++i)if(chosen[i]){int value=mod_positive(days[i],p);while(occupied.count(value)!=0U){if(static_cast<int>(occupied.size())>=p)return out;value=(value+1)%p;}occupied.insert(value);out.push_back(value);}",
        "int rank=0;for(std::size_t i=0;i<days.size();++i)if(chosen[i]&&++rank%p==0)out.push_back(days[i]);",
        "std::vector<std::pair<int,int>> intervals;for(std::size_t i=0;i<days.size();++i)if(chosen[i])intervals.push_back({days[i],days[i]+p});for(const auto& item:intervals){if(out.empty()||item.first>out.back()){out.push_back(item.first);out.push_back(item.second);}else out.back()=std::max(out.back(),item.second);}",
        "for(int parity=0;parity<2;++parity)for(std::size_t i=0;i<days.size();++i)if(chosen[i]&&mod7(days[i])%2==parity)out.push_back(days[i]);",
        "for(std::size_t i=0;i<days.size();++i)if(chosen[i]){out.push_back(days[i]);out.push_back(std::max(0,p-std::abs(days[i])));}",
        "for(std::size_t i=0;i<days.size();++i)if(chosen[i]&&raw_rule(days[i]+p,request))out.push_back(days[i]);",
    )
    return bodies[index]


def _reference(
    case: Case,
    *,
    apply_exclusions: bool = True,
    prefer_earlier: bool = True,
    invert_rule: bool = False,
    nonempty_on_absence: bool = False,
) -> str:
    function = case.operation.slug.replace("-", "_")
    raw_predicate = _predicate_cpp(case)
    if invert_rule:
        raw_predicate = f"!({raw_predicate})"
    chosen_expr = "raw[i]&&blocked.count(days[i])==0U" if apply_exclusions else "raw[i]"
    nearest_tie = "day<best" if prefer_earlier else "day>best"
    body = _operation_cpp(case.ordinal % len(OPERATIONS)).replace("day<best", nearest_tie)
    group_validation = {
        "weekday": "if(request.primary<0||request.primary>6)return std::nullopt;",
        "recurrence": "if(request.primary<kMinSerial||request.primary>kMaxSerial||request.interval<=0)return std::nullopt;",
        "business-day": "if(request.primary<=0||request.primary>127)return std::nullopt;",
    }[case.group]
    absence_mutation = (
        "if(std::none_of(raw.begin(),raw.end(),[](bool value){return value;}))"
        "return std::vector<int>{100001};"
        if nonempty_on_absence
        else ""
    )
    return f'''#include "{case.task_id}.h"
#include <algorithm>
#include <array>
#include <cstdlib>
#include <functional>
#include <map>
#include <set>
#include <utility>
namespace curriculum {{
namespace {{
[[maybe_unused]] int mod7(int value){{int result=value%7;return result<0?result+7:result;}}
[[maybe_unused]] int mod_positive(int value,int modulus){{int result=value%modulus;return result<0?result+modulus:result;}}
[[maybe_unused]] int floor_div(int value,int divisor){{int quotient=value/divisor;int remainder=value%divisor;return remainder<0?quotient-1:quotient;}}
bool raw_rule(int day,const CalendarRequest& request){{return {raw_predicate};}}
bool sorted_unique(const std::vector<int>& values){{return std::adjacent_find(values.begin(),values.end(),std::greater_equal<int>())==values.end();}}
}}
std::optional<std::vector<int>> {case.group.replace('-', '_')}_{function}(const CalendarRequest& request){{
  constexpr int kMinSerial=-100000;constexpr int kMaxSerial=100000;
  if(request.start_day<kMinSerial||request.end_day>kMaxSerial||request.start_day>request.end_day||request.end_day-request.start_day>=512)return std::nullopt;
  if(!sorted_unique(request.exclusions)||std::any_of(request.exclusions.begin(),request.exclusions.end(),[](int value){{return value<kMinSerial||value>kMaxSerial;}})||request.parameter<=0||request.parameter>64)return std::nullopt;
  {group_validation}
  std::vector<int> days;days.reserve(static_cast<std::size_t>(request.end_day-request.start_day+1));for(int day=request.start_day;;++day){{days.push_back(day);if(day==request.end_day)break;}}
  [[maybe_unused]] const int p=request.parameter;
  std::set<int> blocked(request.exclusions.begin(),request.exclusions.end());
  std::vector<bool> raw;raw.reserve(days.size());for(int day:days)raw.push_back(raw_rule(day,request));
  {absence_mutation}
  std::vector<bool> chosen;chosen.reserve(days.size());for(std::size_t i=0;i<days.size();++i)chosen.push_back({chosen_expr});
  std::vector<int> out;{body}
  return out;
}}
}}
'''


def _request_values(case: Case, hidden: bool = False) -> tuple[list[int], list[int], int, int, int]:
    days = list(range(-21 if hidden else -14, 36 if hidden else 29))
    if case.group == "weekday":
        primary, interval = (2 if hidden else 1), 1
    elif case.group == "recurrence":
        primary, interval = (-13 if hidden else -11), (5 if hidden else 4)
    else:
        primary, interval = (0b0011111 if hidden else 0b0111110), 1
    raw_days = [day for day in days if _raw_selected(case, day, primary, interval)]
    exclusions = sorted(set(raw_days[1::3] + [34 if hidden else 27]))
    parameter = 4 if hidden else 3
    if case.ordinal % len(OPERATIONS) == 4:
        retained_raw = sum(day not in set(exclusions) for day in raw_days)
        retained_inverse = sum(
            not _raw_selected(case, day, primary, interval) and day not in set(exclusions)
            for day in days
        )
        parameter = min(64, min(retained_raw, retained_inverse) + 1)
    return days, exclusions, primary, interval, parameter


def _test_source(case: Case, hidden: bool = False, *, apply_exclusions: bool = True, prefer_earlier: bool = True) -> str:
    days, exclusions, primary, interval, parameter = _request_values(case, hidden)
    expected = _operation_oracle(
        case.ordinal % len(OPERATIONS), days, exclusions, primary, interval, parameter,
        case.group, apply_exclusions=apply_exclusions, prefer_earlier=prefer_earlier,
    )
    function = f"{case.group.replace('-', '_')}_{case.operation.slug.replace('-', '_')}"
    invalid_primary_low = -1 if case.group == "weekday" else (primary if case.group == "recurrence" else 0)
    invalid_primary_high = 7 if case.group == "weekday" else (primary if case.group == "recurrence" else 128)
    invalid_interval_low = -1 if case.group == "recurrence" else interval
    invalid_interval_high = 0 if case.group == "recurrence" else interval
    absent_primary = 6 if case.group == "weekday" else (1 if case.group == "recurrence" else 2)
    absent_days = [0]
    absent_expected = _operation_oracle(
        case.ordinal % len(OPERATIONS), absent_days, [], absent_primary, interval,
        parameter, case.group, apply_exclusions=apply_exclusions,
        prefer_earlier=prefer_earlier,
    )
    recurrence_anchor_checks = "" if case.group != "recurrence" else f'''CalendarRequest anchor_low{{-100000,-99999,{{}},-100000,1,{parameter}}};
  CalendarRequest anchor_high{{99999,100000,{{}},100000,1,{parameter}}};
  CalendarRequest anchor_outside_low{{0,1,{{}},-100001,1,{parameter}}};
  CalendarRequest anchor_outside_high{{0,1,{{}},100001,1,{parameter}}};
  auto anchor_low_result={function}(anchor_low);auto anchor_high_result={function}(anchor_high);
  if(!anchor_low_result||!anchor_high_result||{function}(anchor_outside_low).has_value()||{function}(anchor_outside_high).has_value())return 2;'''
    invalid_checks = "" if not hidden else f'''CalendarRequest reversed{{2,1,{_cpp_vector(exclusions)},{primary},{interval},{parameter}}};
  CalendarRequest duplicate_exclusions{{{days[0]},{days[-1]},{{1,1}},{primary},{interval},{parameter}}};
  CalendarRequest unsorted_exclusions{{{days[0]},{days[-1]},{{2,1}},{primary},{interval},{parameter}}};
  CalendarRequest bad_rule_low{{{days[0]},{days[-1]},{_cpp_vector(exclusions)},{invalid_primary_low},{invalid_interval_low},{parameter}}};
  CalendarRequest bad_rule_high{{{days[0]},{days[-1]},{_cpp_vector(exclusions)},{invalid_primary_high},{invalid_interval_high},{parameter}}};
  CalendarRequest zero_parameter{{{days[0]},{days[-1]},{_cpp_vector(exclusions)},{primary},{interval},0}};
  CalendarRequest large_parameter{{{days[0]},{days[-1]},{_cpp_vector(exclusions)},{primary},{interval},65}};
  CalendarRequest wide{{-100000,100000,{{}},{primary},{interval},{parameter}}};
  CalendarRequest outside{{-100001,-100000,{{}},{primary},{interval},{parameter}}};
  CalendarRequest exclusion_outside{{{days[0]},{days[-1]},{{100001}},{primary},{interval},{parameter}}};
  CalendarRequest lower_boundary{{-100000,-99999,{{}},{primary},{interval},{parameter}}};
  CalendarRequest upper_boundary{{99999,100000,{{}},{primary},{interval},{parameter}}};
  CalendarRequest absent{{0,0,{{}},{absent_primary},{interval},{parameter}}};
  auto lower_result={function}(lower_boundary);auto upper_result={function}(upper_boundary);auto absent_result={function}(absent);
  const std::vector<int> absent_expected{_cpp_vector(absent_expected)};
  if({function}(reversed).has_value()||{function}(duplicate_exclusions).has_value()||{function}(unsorted_exclusions).has_value()||{function}(bad_rule_low).has_value()||{function}(bad_rule_high).has_value()||{function}(zero_parameter).has_value()||{function}(large_parameter).has_value()||{function}(wide).has_value()||{function}(outside).has_value()||{function}(exclusion_outside).has_value()||!lower_result||!upper_result||!absent_result||*absent_result!=absent_expected)return 2;
  {recurrence_anchor_checks}'''
    return f'''#include "{case.task_id}.h"
#include <vector>
int main(){{using namespace curriculum;
  CalendarRequest request{{{days[0]},{days[-1]},{_cpp_vector(exclusions)},{primary},{interval},{parameter}}};
  auto got={function}(request);const std::vector<int> expected{_cpp_vector(expected)};
  if(!got||*got!=expected)return 1;
  {invalid_checks}
  return 0;
}}
'''


def _instructions(case: Case) -> str:
    selector = {
        "weekday": "A day is raw-eligible when its floor-modulo weekday equals `primary`.",
        "recurrence": "A day is raw-eligible when it is on or after the `primary` anchor in `[-100000,100000]` and lies on the positive `interval` recurrence.",
        "business-day": "A day is raw-eligible when its floor-modulo weekday bit is set in the seven-bit `primary` workweek mask.",
    }[case.group]
    example_days = list(range(-3, 11))
    example_primary = 1 if case.group != "business-day" else 0b0111110
    example_interval = 3
    example_raw = [
        day
        for day in example_days
        if _raw_selected(case, day, example_primary, example_interval)
    ]
    example_exclusions = example_raw[1:2]
    example_parameter = 2
    example_expected = _operation_oracle(
        case.ordinal % len(OPERATIONS),
        example_days,
        example_exclusions,
        example_primary,
        example_interval,
        example_parameter,
        case.group,
    )
    return f'''# Instructions

Implement `{case.title}` in C++17.

Public API: `{_api(case)}`. `start_day` and `end_day` define an inclusive serial-day window. Both endpoints and every exclusion must be in `[-100000,100000]`; the window must contain 1 through 512 days. `exclusions` must be strictly increasing and duplicate-free. {selector} Excluded serial days are not eligible unless the operation explicitly reports or substitutes exclusions. `parameter` is in `[1,64]`; recurrence intervals are positive; weekday selectors are 0 through 6; workweek masks are 1 through 127. Invalid input returns `std::nullopt` without partial output. When no raw day exists and exclusions are empty, follow the named operation exactly: `occurrence-exists` returns `{{0}}`, `rolling-density` returns one zero per window day, and every other operation returns an engaged empty vector.

Required mechanism: {case.operation.mechanism}. Return {case.operation.output}. Operation semantics: {OPERATION_CONTRACTS[case.ordinal % len(OPERATIONS)]} Use floor-modulo arithmetic for negative serial days.

Visible example: `CalendarRequest{{-3,10,{_cpp_vector(example_exclusions)},{example_primary},{example_interval},{example_parameter}}}` returns `{_cpp_vector(example_expected)}`.

Implement the direct mechanism; do not delegate to host date/time/calendar APIs, a generic mode-switch rule engine, precomputed answers, files, networking, threads, or randomness.
'''


def _semantic_profile(case: Case) -> dict[str, str]:
    selector = {
        "weekday": "modular-weekday-selector",
        "recurrence": "anchored-positive-interval-selector",
        "business-day": "workweek-mask-and-closure-selector",
    }[case.group]
    operation = case.operation.slug
    return {
        "public_api": f"{selector}/{operation}/optional-vector-result",
        "owned_state_algorithm": f"{selector}/{case.operation.mechanism}",
        "mutation_selection_rules": f"exclusion-aware/{operation}/stable-order",
        "invalid_boundary_behavior": f"{selector}/strict-order/positive-parameter/{operation}",
        "reference_control_flow": f"direct-specialized/{selector}/{operation}",
        "deterministic_oracle": f"literal-visible-hidden/{selector}/{operation}",
        "topic_negative_fixture": f"inverted-eligibility/{selector}/{operation}",
    }


def _remedy_markdown(case: Case) -> str:
    return f'''## Identity

Task ID `{case.task_id}`; family `{FAMILY_ID}`; task-spec revision 1; disposition `new-root`; repository-authored clean-room provenance; generator `{GENERATOR_PATH}`; benchmark screen pending.

## Objective

Implement {case.operation.mechanism} over the `{case.group}` eligibility model and return {case.operation.output}.

## Public API

C++17 namespace `curriculum`; editable order `{case.task_id}.h`, `{case.task_id}.cpp`; API `{_api(case)}`; caller owns inputs and returned values.

## Behavior table

An inclusive 1–512-day window inside `[-100000,100000]` executes the documented rule. Recurrence anchors use that same range and subtraction is widened. Invalid endpoints, unsorted/duplicate/out-of-range exclusions, invalid selector/mask/anchor/interval, or parameter outside `[1,64]` returns `std::nullopt`. With no raw day and no exclusions, existence returns `{{0}}`, density returns window-length zeros, and other operations return an engaged empty vector. Exclusions, endpoints, ties, tags, and ordering follow the public operation contract; checked input bounds make every intermediate signed integer safe.

## Implementation invariant

The direct required mechanism is `{case.operation.mechanism}` combined with the group-specific selector. Forbidden substitutes are host calendar APIs, a runtime mode switch, hard-coded examples, ignored exclusions, renamed roots, constant-only policies, and endpoint-only variants.

## Starter and reference

The task-named header declares the complete API. The starter source is coherent and incomplete. `.meta/example.h` and `.meta/example.cpp` replace both editable files and directly implement this root without benchmark or sibling-root imports.

## Tests

Visible and hidden literal oracles cover negative serial days, a raw match that is excluded, stable ordering, exact operation semantics, exact operation-specific empty/absent behavior, duplicate and unsorted exclusions, both parameter bounds, invalid range/selector/anchor/interval/mask, and supported integer boundaries. `.meta/negative_false_substitute.cpp` inverts raw eligibility and `.meta/negative_nonempty_absence.cpp` returns a marker for an absent result; both compile and must be rejected.

## Files and metadata

Solutions are `{case.task_id}.h` and `{case.task_id}.cpp`; the visible test is `task_visible_test.cpp`; private test/reference/negative/provenance assets remain under `.meta`; CMake remains private.

## Build/oracle

Strict C++17, `Unix Makefiles`, network-disabled `{SANITY_IMAGE}`, two positive normal tests and two equal fresh ASan/UBSan tests. Receipt binds compiler path/version/hash, CMake, image, archive/mount, owner, tree, prompt, starter, reference, tests, metadata, policy, and result digests.

## Family/contamination

Compare all 4,005 unordered retained pairs conjunctively in seven dimensions from emitted docs/API/reference/tests/negative fixtures; reject coherent rename, constant/policy, and opposite-end controls. Screen all 26 official C++ holdouts and both existing generated trees.

## Optional dataset handoff

`not_requested`; no JSONL, split, release, export, training, or uplift is authorized.

## Acceptance

Owner regeneration, focused tests, prompt/role/reference validation, all-pairs diversity, controls, cross-tree ID/lineage screen, benchmark screen, normal/sanitizer reference passes, and 180 compiled/executed/rejected negatives must all pass. Stable failures include `unsafe_path`, `duplicate_task`, `duplicate_family`, `comparator_inventory_changed`, `benchmark_content_overlap`, `prompt_contract_incomplete`, `target_reference_mismatch`, `negative_fixture_not_rejected`, `grader_mount_hash_mismatch`, and `sanitizer_test_count_mismatch`.
'''


def _render_files(case: Case, *, control: str | None = None) -> dict[str, str]:
    reference = _reference(case)
    visible = _test_source(case)
    hidden = _test_source(case, True)
    instructions = _instructions(case)
    if control == "opposite-end-selection":
        reference = _reference(case, prefer_earlier=False)
        visible = _test_source(case, prefer_earlier=False)
        hidden = _test_source(case, True, prefer_earlier=False)
        instructions = instructions.replace("equal distance chooses the earlier day", "equal distance chooses the later day")
    if control == "constants-policy-only":
        pass
    negative = _reference(case, invert_rule=True)
    absence_negative = _reference(case, nonempty_on_absence=True)
    config = {
        "authors": ["w8-biayn"],
        "blurb": f"{case.operation.mechanism} for {case.group} rules.",
        "files": {
            "solution": [f"{case.task_id}.h", f"{case.task_id}.cpp"],
            "test": ["task_visible_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "benchmark_separation": "All official Aider Polyglot C++ roots are permanent holdouts; no holdout assets were used.",
        "count_plan_cell": "weekday, nth/final occurrence, recurrence, and business-day rules / 90",
        "curriculum_document": str(CURRICULUM),
        "family_id": FAMILY_ID,
        "lineage": "new-root",
        "mechanism": case.operation.mechanism,
        "origin": "repository-authored clean-room expansion",
        "semantic_profile": _semantic_profile(case),
        "status": "local task artifact; not admitted SFT data",
        "task_id": case.task_id,
        "version": 1,
    }
    files = {
        ".docs/introduction.md": f"# {case.title}\n\n" + ("A roster-planning domain rename with identical calendar behavior." if control == "domain-identifier-renamed" else f"A clean-room serial-day task for {case.operation.mechanism}." + (" Policy revision 2." if control == "constants-policy-only" else "")) + "\n",
        ".docs/instructions.md": instructions,
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": '[visible]\ndescription="deterministic public example and exact operation result"\n[hidden]\ndescription="negative serials, exclusions, ordering, exact empty/absent output, parameter and supported-range boundaries"\n[negative]\ndescription="coherent implementation inverts raw eligibility while retaining exclusion handling"\n[absence_negative]\ndescription="coherent implementation returns a nonempty marker when no raw occurrence exists"\n',
        f"{case.task_id}.h": _header(case),
        f"{case.task_id}.cpp": f'#include "{case.task_id}.h"\nnamespace curriculum {{\nstd::optional<std::vector<int>> {case.group.replace("-", "_")}_{case.operation.slug.replace("-", "_")}(const CalendarRequest&){{return std::nullopt;}}\n}}\n',
        ".meta/example.h": _header(case),
        ".meta/example.cpp": reference,
        ".meta/negative_false_substitute.cpp": negative,
        ".meta/negative_nonempty_absence.cpp": absence_negative,
        "task_visible_test.cpp": visible,
        ".meta/task_hidden_test.cpp": hidden,
        "CMakeLists.txt": CMAKE,
    }
    if control == "domain-identifier-renamed":
        for relative in (
            ".docs/introduction.md", ".docs/instructions.md",
            f"{case.task_id}.h", f"{case.task_id}.cpp", ".meta/example.h",
            ".meta/example.cpp", ".meta/negative_false_substitute.cpp",
            ".meta/negative_nonempty_absence.cpp",
            "task_visible_test.cpp", ".meta/task_hidden_test.cpp",
        ):
            files[relative] = files[relative].replace("Weekday", "Rota").replace(
                "weekday", "rota"
            ).replace(f"rota-{case.operation.slug}.h", f"weekday-{case.operation.slug}.h")
    if control == "constants-policy-only":
        files[".docs/instructions.md"] = files[".docs/instructions.md"].replace(
            "[1,64]", "[1,63]"
        )
        files[".meta/example.cpp"] = files[".meta/example.cpp"].replace(
            "request.parameter>64", "request.parameter>63"
        )
        files[".meta/negative_false_substitute.cpp"] = files[
            ".meta/negative_false_substitute.cpp"
        ].replace("request.parameter>64", "request.parameter>63")
        files[".meta/negative_nonempty_absence.cpp"] = files[
            ".meta/negative_nonempty_absence.cpp"
        ].replace("request.parameter>64", "request.parameter>63")
        files[".meta/task_hidden_test.cpp"] = files[
            ".meta/task_hidden_test.cpp"
        ].replace(",65};", ",64};")
    return files


def _write_root(root: Path, case: Case, force: bool, *, control: str | None = None) -> None:
    rendered = task_named_files(root, _render_files(case, control=control))
    if control:
        rendered["CMakeLists.txt"] = rendered["CMakeLists.txt"].replace(
            f"{root.name}.cpp", f"{case.task_id}.cpp"
        )
    for relative, content in rendered.items():
        _write(root / relative, content, force)


def _write_controls(out: Path, force: bool) -> None:
    case = CASES[12]
    controls = ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection")
    records = {}
    for name in controls:
        root = out / ".state/adversarial-clone-controls" / name
        _write_root(root, case, force, control=name)
        base = out / case.task_id
        changed_files = []
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = path.relative_to(root)
            counterpart = base / relative
            if not counterpart.is_file() or counterpart.read_bytes() != path.read_bytes():
                changed_files.append(relative.as_posix())
        if not changed_files:
            _fail("duplicate_family", f"clone control changed no emitted file: {name}")
        records[name] = {"changed_files": changed_files, "tree_hash": _tree_hash(root, include_state=True)}
    _write(out / ".state/adversarial-clone-controls/manifest.json", json.dumps({"schema_version": "calendar-expansion-clone-controls-v1", "base_task_id": case.task_id, "controls": records}, indent=2, sort_keys=True) + "\n", force)


def _freeze_inventory(out: Path, force: bool) -> dict[str, object]:
    inventories = {
        "legacy": _inventory(LEGACY_ROOT),
        "reverify": _inventory(REVERIFY_ROOT),
        "expansion_before": [record for record in _inventory(EXPANSION_ROOT) if not record["relative_root"].startswith(out.relative_to(EXPANSION_ROOT).as_posix() + "/")],
    }
    payload: dict[str, object] = {"schema_version": "calendar-expansion-source-inventory-v2", "roots": {}, "_snapshot_material": {}}
    for name, records in inventories.items():
        public_records = [
            {key: value for key, value in record.items() if not key.startswith("_")}
            for record in records
        ]
        serialized = json.dumps(public_records, sort_keys=True, separators=(",", ":")).encode()
        payload["roots"][name] = {"count": len(records), "sha256": _sha(serialized), "records": public_records}
        payload["_snapshot_material"][name] = [
            {
                "task_id": record["task_id"],
                "relative_root": record["relative_root"],
                "tree_hash": record["tree_hash"],
                "screen_text": record["_screen_text"],
                "prompt_material": record["_prompt_material"],
                "answer_material": record["_answer_material"],
            }
            for record in records
        ]
    public_payload = {key: value for key, value in payload.items() if not key.startswith("_")}
    _write(out / ".state/source-inventory.json", json.dumps(public_payload, indent=2, sort_keys=True) + "\n", force)
    return payload


def _write_remediation_records(
    out: Path, prior_hashes: dict[str, str], force: bool
) -> None:
    finding_ids = [f"WRBD-AUD-{index:03d}" for index in range(1, 11)]
    root = out / ".state/remedy/cycle-02"
    dispositions = []
    for case in CASES:
        markdown = _remedy_markdown(case)
        markdown_path = root / f"{case.task_id}.md"
        _write(markdown_path, markdown, force)
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": case.task_id,
            "family_id_before": FAMILY_ID,
            "family_id_after": FAMILY_ID,
            "tree_hash_before": prior_hashes.get(case.task_id, "not_available"),
            "tree_hash_after": _tree_hash(out / case.task_id),
            "generator_path": str(GENERATOR_PATH),
            "generator_revision": _file_hash(Path(__file__)),
            "finding_ids": finding_ids,
            "disposition": "repair-in-place",
            "benchmark_screen": "pending_reverification",
            "license_screen": "pass",
            "remedy_spec_path": markdown_path.relative_to(out).as_posix(),
            "remedy_spec_hash": _file_hash(markdown_path),
            "status": "implemented",
            "primary_core_objective": "achieved_pending_fresh_audit",
            "prior_audit_subject_hash": "sha256:48d7dbb1443ad4a96afa25253c87157a6d518140e062735e111861558be64fda",
        }
        _write(root / f"{case.task_id}.json", json.dumps(record, indent=2, sort_keys=True) + "\n", force)
        dispositions.append({"task_id": case.task_id, "disposition": "repair-in-place", "record": f".state/remedy/cycle-02/{case.task_id}.json"})
    report = {
        "schema_version": "weekday-recurrence-business-day-remediation-cycle-v1",
        "prior_audit_subject_hash": "sha256:48d7dbb1443ad4a96afa25253c87157a6d518140e062735e111861558be64fda",
        "finding_dispositions": {
            "WRBD-AUD-001": "redesign bounded window and explicit occurrence/recurrence/business calendar contracts",
            "WRBD-AUD-002": "operation-complete public contracts and deterministic examples",
            "WRBD-AUD-003": "truthful inverted-eligibility negative identity",
            "WRBD-AUD-004": "expanded invalid, empty, boundary, tie, and operation oracle tests",
            "WRBD-AUD-005": "identifier-neutral artifact-derived seven-gram clone evaluator and coherent controls",
            "WRBD-AUD-006": "fresh digest-bound comparator inventories and per-pair ledger",
            "WRBD-AUD-007": "nearest mechanism truthfully specified as exhaustive deterministic lookup",
            "WRBD-AUD-008": "per-root Docker result ledger retained in receipt",
            "WRBD-AUD-009": "public -100000..100000 range and bounded 512-day windows",
            "WRBD-AUD-010": "26-root holdout tree-hash inventory bound into creator manifest",
        },
        "root_dispositions": dispositions,
        "prior_evidence_invalidated": [".state/docker-sanity.json", ".state/materialization-manifest.json", ".state/cycles/cycle-07.json"],
        "status": "implemented_pending_remediation_verification_and_fresh_audit",
    }
    _write(root / "remediation-report.json", json.dumps(report, indent=2, sort_keys=True) + "\n", force)


def _reconcile_owned_roots(out: Path, force: bool) -> list[dict[str, str]]:
    """Move known generator-replaced roots out of the active task inventory."""
    expected = {case.task_id for case in CASES}
    active = {
        child.name: child
        for child in out.iterdir()
        if child.is_dir() and child.name != ".state" and (child / ".meta/config.json").is_file()
    } if out.is_dir() else {}
    unexpected = sorted(set(active) - expected)
    ledger_path = out / ".state/remedy/cycle-03/replaced-roots.json"
    if not unexpected:
        if ledger_path.is_file():
            return json.loads(ledger_path.read_text())["replacements"]
        return []
    if not force:
        _fail(
            "generator_output_drift",
            f"unexpected owned roots require --force reconciliation: {unexpected}",
        )
    unknown = sorted(set(unexpected) - set(REPLACED_TASK_IDS))
    if unknown:
        _fail("unsafe_path", f"refusing to move unknown task roots: {unknown}")
    replacements = []
    quarantine = out / ".state/rejected/cycle-03"
    quarantine.mkdir(parents=True, exist_ok=True)
    for task_id in unexpected:
        source = active[task_id]
        provenance_path = source / ".meta/provenance.json"
        provenance = json.loads(provenance_path.read_text()) if provenance_path.is_file() else {}
        if provenance.get("family_id") != FAMILY_ID or provenance.get("task_id") != task_id:
            _fail("unsafe_path", f"root is not generator-owned: {source}")
        destination = quarantine / task_id
        if destination.exists():
            _fail("unsafe_path", f"quarantine destination already exists: {destination}")
        tree_hash = _tree_hash(source)
        source.rename(destination)
        replacements.append(
            {
                "rejected_task_id": task_id,
                "replacement_task_id": REPLACED_TASK_IDS[task_id],
                "rejected_tree_hash": tree_hash,
                "quarantine_root": destination.relative_to(out).as_posix(),
                "disposition": "replaced-and-quarantined-outside-active-inventory",
            }
        )
    _write(
        ledger_path,
        json.dumps(
            {
                "schema_version": "calendar-expansion-replacement-ledger-v1",
                "prior_audit_subject_hash": "sha256:1defaa650e9573d2c7f9da29a3ca6566189737cb8d8d52c7b64d70e8a40738c9",
                "replacements": replacements,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        force,
    )
    return replacements


def _write_cycle3_remediation_records(
    out: Path,
    prior_hashes: dict[str, str],
    replacements: list[dict[str, str]],
    force: bool,
) -> None:
    root = out / ".state/remedy/cycle-03"
    replacement_by_new = {
        row["replacement_task_id"]: row["rejected_task_id"]
        for row in replacements
    }
    dispositions = []
    for case in CASES:
        disposition = (
            "replacement-backfill-and-reverify"
            if case.task_id in replacement_by_new
            else "repair-in-place-and-reverify"
        )
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": case.task_id,
            "family_id": FAMILY_ID,
            "tree_hash_before": prior_hashes.get(case.task_id, "not_available"),
            "tree_hash_after": _tree_hash(out / case.task_id),
            "generator_path": str(GENERATOR_PATH),
            "generator_revision": _file_hash(Path(__file__)),
            "finding_ids": [f"WRBD-AUD2-{index:03d}" for index in range(1, 5)],
            "disposition": disposition,
            "replaces_task_id": replacement_by_new.get(case.task_id),
            "status": "implemented_pending_fresh_reverification",
            "prior_audit_subject_hash": "sha256:1defaa650e9573d2c7f9da29a3ca6566189737cb8d8d52c7b64d70e8a40738c9",
        }
        path = root / f"{case.task_id}.json"
        _write(path, json.dumps(record, indent=2, sort_keys=True) + "\n", force)
        dispositions.append(
            {
                "task_id": case.task_id,
                "disposition": disposition,
                "record": path.relative_to(out).as_posix(),
            }
        )
    report = {
        "schema_version": "weekday-recurrence-business-day-remediation-cycle-v2",
        "prior_audit_subject_hash": "sha256:1defaa650e9573d2c7f9da29a3ca6566189737cb8d8d52c7b64d70e8a40738c9",
        "finding_dispositions": {
            "WRBD-AUD2-001": "15 known generator-orphaned roots quarantined under .state with explicit old-to-new replacement lineage; exact active inventory enforced",
            "WRBD-AUD2-002": "recurrence primary bound to -100000..100000, difference widened to long long, exact boundary/out-of-range tests added",
            "WRBD-AUD2-003": "exact operation-specific absent outputs asserted and a second coherent nonempty-absence mutant executed",
            "WRBD-AUD2-004": "cross-tree screening captures hash-frozen comparator material, rejects drift during each capture, and evaluates only the bound snapshot",
        },
        "root_dispositions": dispositions,
        "replaced_roots": replacements,
        "prior_evidence_invalidated": [
            ".state/docker-sanity.json",
            ".state/materialization-manifest.json",
            ".state/cycles/cycle-08.json",
        ],
        "status": "implemented_pending_fresh_reverification_and_independent_audit",
    }
    _write(
        root / "remediation-report.json",
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        force,
    )


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    _validate_output(out)
    replacements = _reconcile_owned_roots(out, force)
    prior_hashes: dict[str, str] = {}
    prior_manifest_path = out / ".state/materialization-manifest.json"
    if prior_manifest_path.is_file():
        prior_manifest = json.loads(prior_manifest_path.read_text())
        prior_hashes = {
            row["task_id"]: row["tree_hash"] for row in prior_manifest.get("tasks", [])
        }
    source_inventory = _freeze_inventory(out, force)
    existing = {
        record["task_id"]
        for name in ("legacy", "reverify", "expansion_before")
        for record in source_inventory["roots"][name]["records"]
    }
    collisions = sorted(existing & {case.task_id for case in CASES})
    if collisions:
        _fail("duplicate_task", ",".join(collisions))
    roots = []
    for case in CASES:
        root = out / case.task_id
        if root.exists() and any(path.is_symlink() for path in root.rglob("*")):
            _fail("unsafe_path", f"symlink in owned root: {root}")
        _write_root(root, case, force)
        roots.append(root)
    _write_controls(out, force)
    _write_remediation_records(out, prior_hashes, force)
    _write_cycle3_remediation_records(out, prior_hashes, replacements, force)
    return tuple(roots)


def _normalized_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"|(?<![A-Za-z_])-?\d+', " LIT ", text)
    text = re.sub(r"\b(front|back|earlier|later|minimum|maximum|stable|reverse|tie|order|endpoint)\b", " ENDPOINT ", text, flags=re.I)
    text = re.sub(r">=|<=|>|<", " REL ", text)
    text = re.sub(r"rota", "weekday", text, flags=re.I)
    keep = {
        "if", "else", "for", "while", "return", "break", "continue", "class",
        "struct", "const", "auto", "bool", "int", "void", "true", "false",
        "vector", "array", "map", "set", "optional", "size", "begin", "end",
        "sort", "rotate", "lower", "bound", "unique", "weekday", "recurrence",
        "business", "workweek", "closure", "first", "final", "nth", "occurrence",
        "eligible", "exclusion", "intersection", "symmetric", "expansion", "shift",
        "nearest", "rank", "quota", "capacity", "spill", "transition", "streak",
        "cyclic", "rotation", "period", "bucket", "pair", "distance", "missing",
        "arithmetic", "compression", "substitution", "collision", "checkpoint",
        "coverage", "union", "parity", "score", "consensus", "rolling", "density",
        "bounded", "batches", "overlay", "exists", "REL", "ENDPOINT", "LIT",
    }
    output: list[str] = []
    for token in re.findall(r"[A-Za-z_][A-Za-z_0-9]*|==|!=|&&|\|\||[-+*/%{}()[\];,?:=.]", text):
        if re.match(r"[A-Za-z_]", token):
            parts = [part.lower() for part in token.split("_") if part]
            output.extend(part if part in keep else "ID" for part in parts)
        else:
            output.append(token)
    return tuple(output)


def _dimension_material(root: Path) -> dict[str, tuple[str, ...]]:
    reference = (root / ".meta/example.cpp").read_text()
    instructions = (root / ".docs/instructions.md").read_text()
    header = next(path for path in root.glob("*.h")).read_text()
    visible = (root / "task_visible_test.cpp").read_text()
    hidden = (root / ".meta/task_hidden_test.cpp").read_text()
    negative = (root / ".meta/negative_false_substitute.cpp").read_text()
    absence_negative = (root / ".meta/negative_nonempty_absence.cpp").read_text()
    return {
        "public_api": _normalized_tokens(header + instructions),
        "owned_state_algorithm": _normalized_tokens(header + reference),
        "mutation_selection_rules": _normalized_tokens(instructions + reference),
        "invalid_boundary_behavior": _normalized_tokens(instructions + hidden),
        "reference_control_flow": _normalized_tokens(reference),
        "deterministic_oracle": _normalized_tokens(visible + hidden),
        "topic_negative_fixture": _normalized_tokens(negative + absence_negative),
    }


def _token_similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    left_grams = _ngrams(left, 7)
    right_grams = _ngrams(right, 7)
    denominator = min(len(left_grams), len(right_grams))
    return len(left_grams & right_grams) / denominator if denominator else 1.0


def _pair_decisions(left: Path, right: Path) -> tuple[dict[str, bool], dict[str, float]]:
    return _material_decisions(_dimension_material(left), _dimension_material(right))


def _material_decisions(
    a: dict[str, tuple[str, ...]], b: dict[str, tuple[str, ...]]
) -> tuple[dict[str, bool], dict[str, float]]:
    similarities = {
        dimension: round(_token_similarity(a[dimension], b[dimension]), 6)
        for dimension in HARD_DIMENSIONS
    }
    decisions = {
        dimension: a[dimension] != b[dimension] and similarities[dimension] < 0.995
        for dimension in HARD_DIMENSIONS
    }
    return decisions, similarities


def _semantic_screen(out: Path) -> dict[str, object]:
    pairs = []
    roots = sorted((out / case.task_id for case in CASES), key=lambda path: path.name)
    materials = {root.name: _dimension_material(root) for root in roots}
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            decisions, similarities = _material_decisions(
                materials[left.name], materials[right.name]
            )
            if not all(decisions.values()):
                _fail("duplicate_family", f"{left.name} vs {right.name}: {decisions}; {similarities}")
            pairs.append({"left": left.name, "right": right.name, "decisions": decisions, "similarities": similarities})
    expected = len(CASES) * (len(CASES) - 1) // 2
    if len(pairs) != expected:
        _fail("duplicate_family", f"{len(pairs)} != {expected}")
    base = out / CASES[12].task_id
    base_material = materials[base.name]
    controls = {}
    for name in ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection"):
        root = out / ".state/adversarial-clone-controls" / name
        decisions, similarities = _material_decisions(
            base_material, _dimension_material(root)
        )
        if any(decisions.values()):
            _fail("duplicate_family", f"clone control escaped: {name}: {decisions}; {similarities}")
        controls[name] = {"decisions": decisions, "similarities": similarities, "production_rejected": True}
    return {"status": "pass", "root_count": len(CASES), "pair_count": len(pairs), "expected_pair_count": expected, "dimensions": list(HARD_DIMENSIONS), "pairs": pairs, "controls": controls, "threshold": 0.995, "normalizer": "calendar-expansion-v2-identifier-literal-endpoint-neutral-seven-gram-containment"}


def _ngrams(tokens: tuple[str, ...], width: int = 11) -> set[tuple[str, ...]]:
    return {tokens[index : index + width] for index in range(max(0, len(tokens) - width + 1))}


def _holdout_screen(out: Path) -> dict[str, object]:
    found = {path.name for path in HOLDOUT_ROOT.iterdir() if path.is_dir()} if HOLDOUT_ROOT.is_dir() else set()
    if missing := sorted(OFFICIAL_HOLDOUTS - found):
        _fail("benchmark_content_overlap", f"bound holdouts unavailable: {missing}")
    inventory = [
        {"task_id": task_id, "tree_hash": _tree_hash(HOLDOUT_ROOT / task_id)}
        for task_id in sorted(OFFICIAL_HOLDOUTS)
    ]
    inventory_hash = _sha(
        json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    )
    strongest = 0.0
    strongest_pair: list[str] = []
    comparisons = 0
    candidates = {case.task_id: _ngrams(_normalized_tokens(" ".join(path.read_text(errors="ignore") for path in sorted((out / case.task_id).rglob("*")) if path.is_file()))) for case in CASES}
    for holdout_id in sorted(OFFICIAL_HOLDOUTS):
        text = " ".join(path.read_text(errors="ignore") for path in sorted((HOLDOUT_ROOT / holdout_id).rglob("*")) if path.is_file() and path.stat().st_size < 1_000_000)
        grams = _ngrams(_normalized_tokens(text))
        for task_id, candidate in candidates.items():
            denominator = min(len(candidate), len(grams))
            score = len(candidate & grams) / denominator if denominator else 0.0
            comparisons += 1
            if score > strongest:
                strongest, strongest_pair = score, [task_id, holdout_id]
            if score >= 0.80:
                _fail("benchmark_content_overlap", f"{task_id} vs {holdout_id}: {score:.3f}")
    return {"status": "pass", "holdout_root_count": 26, "holdout_inventory": inventory, "holdout_inventory_hash": inventory_hash, "comparison_count": comparisons, "threshold": 0.80, "strongest_pair": strongest_pair, "strongest_containment": round(strongest, 6)}


def _cross_tree_semantic_screen(
    out: Path, source_inventory: dict[str, object]
) -> dict[str, object]:
    candidate_material = {}
    for case in CASES:
        root = out / case.task_id
        text = " ".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in sorted(root.rglob("*"))
            if path.is_file()
        )
        config = json.loads((root / ".meta/config.json").read_text())
        prompt_material = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in sorted((root / ".docs").glob("*.md"))
        ) + "\n" + "\n".join((root / relative).read_text() for relative in config["files"]["solution"])
        answer_material = "\n".join((root / relative).read_text() for relative in config["files"]["example"])
        candidate_material[case.task_id] = {
            "grams": _ngrams(_normalized_tokens(text)),
            "prompt_hash": _sha(prompt_material.encode()),
            "answer_hash": _sha(answer_material.encode()),
            "tree_hash": _tree_hash(root),
        }
    comparisons = 0
    strongest = 0.0
    strongest_pair: list[str] = []
    collision_count = 0
    ledger_lines = []
    inventory_hashes = {}
    comparator_material = []
    snapshot_lines = []
    for inventory_name in ("legacy", "reverify", "expansion_before"):
        inventory_record = source_inventory["roots"][inventory_name]
        inventory_hashes[inventory_name] = inventory_record["sha256"]
        frozen_material = source_inventory["_snapshot_material"][inventory_name]
        if len(frozen_material) != len(inventory_record["records"]):
            _fail("comparator_inventory_changed", f"{inventory_name} snapshot cardinality")
        for frozen, material in zip(
            inventory_record["records"], frozen_material, strict=True
        ):
            comparator_material.append(
                {
                    "inventory_name": inventory_name,
                    "relative_root": frozen["relative_root"],
                    "task_id": material["task_id"],
                    "tree_hash": frozen["tree_hash"],
                    "grams": _ngrams(_normalized_tokens(material["screen_text"])),
                    "prompt_hash": _sha(material["prompt_material"].encode()),
                    "answer_hash": _sha(material["answer_material"].encode()),
                }
            )
            snapshot_lines.append(
                json.dumps(
                    {
                        "comparator_tree": inventory_name,
                        **frozen,
                    },
                    sort_keys=True,
                )
            )
    snapshot_ledger = "\n".join(snapshot_lines) + "\n"
    _write(out / ".state/comparator-snapshot.jsonl", snapshot_ledger, True)
    for other in comparator_material:
        other_grams = other["grams"]
        for task_id, current in candidate_material.items():
            denominator = min(len(current["grams"]), len(other_grams))
            score = len(current["grams"] & other_grams) / denominator if denominator else 0.0
            exact_collision = task_id == other["task_id"] or current["prompt_hash"] == other["prompt_hash"] or current["answer_hash"] == other["answer_hash"] or current["tree_hash"] == other["tree_hash"]
            comparisons += 1
            if score > strongest:
                strongest, strongest_pair = score, [task_id, f"{other['inventory_name']}:{other['relative_root']}"]
            if exact_collision:
                collision_count += 1
                _fail("duplicate_family", f"exact cross-tree collision: {task_id} vs {other['inventory_name']}:{other['relative_root']}")
            passed = score < 0.90
            ledger_lines.append(json.dumps({"candidate": task_id, "comparator_tree": other["inventory_name"], "comparator_root": other["relative_root"], "comparator_tree_hash": other["tree_hash"], "semantic_score": round(score, 6), "passed": passed}, sort_keys=True))
            if not passed:
                _fail("duplicate_family", f"cross-tree semantic overlap {score:.3f}: {strongest_pair}")
    ledger = "\n".join(ledger_lines) + "\n"
    _write(out / ".state/cross-tree-screen.jsonl", ledger, True)
    return {"status": "pass", "comparison_count": comparisons, "candidate_count": len(candidate_material), "comparator_count": len(comparator_material), "comparator_inventory_hashes": inventory_hashes, "snapshot_capture_status": "each comparator stable across bound material read", "snapshot_ledger": ".state/comparator-snapshot.jsonl", "snapshot_ledger_hash": _sha(snapshot_ledger.encode()), "threshold": 0.90, "strongest_pair": strongest_pair, "strongest_score": round(strongest, 6), "exact_collision_count": collision_count, "decision_ledger": ".state/cross-tree-screen.jsonl", "decision_ledger_hash": _sha(ledger.encode())}


def verify_core(out: Path = DEFAULT_OUT) -> None:
    source_inventory = _freeze_inventory(out, True)
    if len(CASES) != 90 or len({case.task_id for case in CASES}) != 90:
        _fail("duplicate_task", f"expected exactly 90 unique roots, got {len(CASES)}")
    observed_roots = {
        config.parent.parent.relative_to(out).as_posix()
        for config in out.rglob(".meta/config.json")
        if ".state" not in config.parts
    }
    expected_roots = {case.task_id for case in CASES}
    if observed_roots != expected_roots:
        _fail(
            "generator_output_drift",
            f"active roots differ: missing={sorted(expected_roots-observed_roots)} "
            f"unexpected={sorted(observed_roots-expected_roots)}",
        )
    rows = []
    prompt_hashes: set[str] = set()
    reference_hashes: set[str] = set()
    for case in CASES:
        root = out / case.task_id
        config = json.loads((root / ".meta/config.json").read_text())
        if config["files"]["solution"] != [f"{case.task_id}.h", f"{case.task_id}.cpp"]:
            _fail("target_reference_mismatch", case.task_id)
        task = load_task(root)
        prompt = build_prompt(task)
        if any(token in prompt for token in (".meta/", "CMakeLists", "task_visible_test", "provenance", "negative_false_substitute")):
            _fail("prompt_contract_incomplete", case.task_id)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        if not answer.startswith(f"{case.task_id}.h\n```") or f"{case.task_id}.cpp\n```" not in answer:
            _fail("target_reference_mismatch", case.task_id)
        prompt_hash = _sha(prompt.encode())
        reference_hash = _file_hash(root / ".meta/example.cpp")
        if prompt_hash in prompt_hashes or reference_hash in reference_hashes:
            _fail("duplicate_family", f"duplicate prompt/reference hash: {case.task_id}")
        prompt_hashes.add(prompt_hash)
        reference_hashes.add(reference_hash)
        rows.append({"task_id": case.task_id, "group": case.group, "mechanism": case.operation.mechanism, "tree_hash": _tree_hash(root), "prompt_hash": prompt_hash, "starter_hash": _file_hash(root / f"{case.task_id}.cpp"), "reference_hash": reference_hash, "visible_test_hash": _file_hash(root / "task_visible_test.cpp"), "hidden_test_hash": _file_hash(root / ".meta/task_hidden_test.cpp"), "negative_hash": _file_hash(root / ".meta/negative_false_substitute.cpp"), "absence_negative_hash": _file_hash(root / ".meta/negative_nonempty_absence.cpp"), "metadata_hash": _file_hash(root / ".meta/config.json"), "provenance_hash": _file_hash(root / ".meta/provenance.json"), "primary_core_objective": "achieved"})
    diversity = _semantic_screen(out)
    holdout = _holdout_screen(out)
    cross_tree = _cross_tree_semantic_screen(out, source_inventory)
    manifest = {"schema_version": "calendar-expansion-materialization-v2", "family_id": FAMILY_ID, "task_count": 90, "group_counts": {group: sum(case.group == group for case in CASES) for group in GROUPS}, "owner_hash": _file_hash(Path(__file__)), "curriculum_hash": _file_hash(CURRICULUM), "family_spec_hash": _file_hash(FAMILY_SPEC), "focused_test_hash": _file_hash(TEST_PATH), "family_tree_hash": _tree_hash(out), "tasks": rows, "screen": {"prompt_boundary": "pass", "reference_mapping": "pass", "exact_active_root_inventory": "pass", "diversity": diversity, "benchmark_holdout": holdout, "cross_tree": cross_tree}, "strongest_local_status": "pending_execution", "dataset_handoff": "not_requested"}
    receipt_path = out / ".state/docker-sanity.json"
    if receipt_path.is_file():
        receipt = json.loads(receipt_path.read_text())
        if (
            receipt.get("status") == "pass"
            and receipt.get("family_tree_hash") == manifest["family_tree_hash"]
            and receipt.get("owner_hash") == manifest["owner_hash"]
            and receipt.get("normal_reference_count") == 90
            and receipt.get("sanitizer_reference_count") == 90
            and receipt.get("negative_fixture_count") == 180
            and len(receipt.get("results", [])) == 366
        ):
            manifest["docker_sanity"] = {
                "status": "pass",
                "receipt": ".state/docker-sanity.json",
                "normal_test_count_per_root": 2,
                "sanitizer_test_count_per_root": 2,
                "negative_fixture_count": 180,
                "negative_fixture_types": 2,
                "control_count": 3,
            }
            manifest["strongest_local_status"] = (
                "creator_preflight_passed_pending_independent_audit"
            )
    host_receipt_path = out / ".state/host-verify.json"
    if host_receipt_path.is_file():
        receipt = json.loads(host_receipt_path.read_text())
        if (
            receipt.get("status") == "pass"
            and receipt.get("family_tree_hash") == manifest["family_tree_hash"]
            and receipt.get("owner_hash") == manifest["owner_hash"]
            and receipt.get("normal_reference_count") == 90
            and receipt.get("sanitizer_reference_count") == 90
            and receipt.get("negative_fixture_count") == 180
            and len(receipt.get("results", [])) == 366
        ):
            manifest["host_verify"] = {
                "status": "pass",
                "receipt": ".state/host-verify.json",
                "normal_test_count_per_root": 2,
                "sanitizer_test_count_per_root": 2,
                "negative_fixture_count": 180,
                "negative_fixture_types": 2,
                "control_count": 3,
            }
            if manifest["strongest_local_status"] == "pending_execution":
                manifest["strongest_local_status"] = "campaign_verified_host_only"
    _write(out / ".state/materialization-manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)


def _archive(out: Path, target: Path) -> str:
    with tarfile.open(target, "w", format=tarfile.PAX_FORMAT) as archive:
        roots = [out / case.task_id for case in CASES] + [out / ".state/adversarial-clone-controls" / name for name in ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection")]
        for root in roots:
            prefix = "tasks" if root.parent == out else "controls"
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                info = archive.gettarinfo(str(path), arcname=f"{prefix}/{root.name}/{path.relative_to(root).as_posix()}")
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                info.mode = 0o644
                with path.open("rb") as handle:
                    archive.addfile(info, handle)
    return _file_hash(target)


def verify_docker(out: Path = DEFAULT_OUT, image: str = SANITY_IMAGE) -> None:
    manifest_path = out / ".state/materialization-manifest.json"
    if not manifest_path.is_file():
        _fail("generator_output_drift", "run --verify-core first")
    manifest = json.loads(manifest_path.read_text())
    if manifest["family_tree_hash"] != _tree_hash(out) or manifest["owner_hash"] != _file_hash(Path(__file__)):
        _fail("generator_output_drift", "manifest does not bind current owner/tree")
    with tempfile.TemporaryDirectory(prefix="calendar-expansion-") as temporary:
        temp = Path(temporary)
        archive = temp / "family.tar"
        result = temp / "result"
        result.mkdir()
        archive_hash = _archive(out, archive)
        script = r'''set -Eeuo pipefail
trap 'status=$?; echo "docker verifier failed: ${status}" >&2; for log in /tmp/config.log /tmp/build.log /tmp/test.log; do if [ -f "$log" ]; then echo "== $log ==" >&2; tail -120 "$log" >&2; fi; done; exit "$status"' ERR
mkdir -p /work /result
tar -xf /input/family.tar -C /work
sha256sum /input/family.tar | awk '{print "archive\t"$1}' > /result/results.tsv
command -v c++ > /result/compiler.path
c++ --version | head -1 > /result/compiler.version
sha256sum "$(command -v c++)" | awk '{print $1}' > /result/compiler.sha256
cmake --version | head -1 > /result/cmake.version
run_one(){ kind="$1"; id="$2"; mode="$3"; source="$4"; root="/work/${kind}/${id}"; build="/tmp/${kind}-${id}-${mode}-${source##*/}"; flags=(); if [ "$mode" = sanitizer ];then flags+=("-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined");fi; cmake -S "$root" -B "$build" -G "Unix Makefiles" -DTASK_SOURCE="$root/$source" "${flags[@]}" >/tmp/config.log 2>&1;cmake --build "$build" --parallel 2 >/tmp/build.log 2>&1;count=$(ctest --test-dir "$build" -N | sed -n 's/^Total Tests: //p');test "$count" = 2;outcome=pass;if [[ "$source" == .meta/negative_*.cpp ]];then if ctest --test-dir "$build" --output-on-failure >/tmp/test.log 2>&1;then echo "negative passed $id $source" >&2;exit 71;fi;outcome=rejected;else ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$build" --output-on-failure >/tmp/test.log 2>&1;fi;printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$kind" "$id" "$mode" "$source" "$count" "$outcome" >>/result/results.tsv;}
for root in /work/tasks/*;do id=${root##*/};run_one tasks "$id" normal .meta/example.cpp;run_one tasks "$id" sanitizer .meta/example.cpp;run_one tasks "$id" normal .meta/negative_false_substitute.cpp;run_one tasks "$id" normal .meta/negative_nonempty_absence.cpp;done
for root in /work/controls/*;do id=${root##*/};run_one controls "$id" normal .meta/example.cpp;run_one controls "$id" sanitizer .meta/example.cpp;done
'''
        completed = subprocess.run(["docker", "run", "--rm", "--network", "none", "--mount", f"type=bind,src={archive},dst=/input/family.tar,readonly", "--mount", f"type=bind,src={result},dst=/result", image, "bash", "-lc", script], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if completed.returncode != 0:
            _fail("docker_sanity_failed", (completed.stdout + completed.stderr)[-12000:])
        rows = [line.split("\t") for line in (result / "results.tsv").read_text().splitlines()]
        mounted = "sha256:" + rows[0][1]
        if mounted != archive_hash:
            _fail("grader_mount_hash_mismatch", f"{mounted} != {archive_hash}")
        refs = [row for row in rows if row[0] == "tasks" and row[3] == ".meta/example.cpp"]
        negatives = [
            row
            for row in rows
            if row[0] == "tasks" and row[3].startswith(".meta/negative_")
        ]
        controls = [row for row in rows if row[0] == "controls"]
        if len(refs) != 180 or len(negatives) != 180 or len(controls) != 6:
            _fail("sanitizer_test_count_mismatch", f"refs={len(refs)} negatives={len(negatives)} controls={len(controls)}")
        detailed_results = [
            {"kind": row[0], "task_or_control_id": row[1], "mode": row[2], "source_role": row[3], "discovered_test_count": int(row[4]), "outcome": row[5]}
            for row in rows[1:]
        ]
        results_ledger = "\n".join("\t".join(row) for row in rows[1:]) + "\n"
        receipt = {"schema_version": "calendar-expansion-docker-sanity-v3", "status": "pass", "evidence_class": "docker_sanity", "locked_oracle": False, "network_policy": "none", "image": image, "archive_hash": archive_hash, "mounted_archive_hash": mounted, "family_tree_hash": _tree_hash(out), "owner_hash": _file_hash(Path(__file__)), "compiler": {"path": (result / "compiler.path").read_text().strip(), "version": (result / "compiler.version").read_text().strip(), "sha256": "sha256:" + (result / "compiler.sha256").read_text().strip()}, "cmake": (result / "cmake.version").read_text().strip(), "normal_reference_count": 90, "sanitizer_reference_count": 90, "normal_test_count_per_root": 2, "sanitizer_test_count_per_root": 2, "negative_fixture_count": 180, "negative_fixture_types": ["inverted-eligibility", "nonempty-on-absence"], "control_mode_count": 6, "result_ledger_hash": _sha(results_ledger.encode()), "results": detailed_results, "commands": {"normal": "cmake -G Unix Makefiles; cmake --build; ctest -N; ctest --output-on-failure", "sanitizer": "same with -fsanitize=address,undefined -fno-omit-frame-pointer in fresh build", "network": "docker run --rm --network none"}}
        _write(out / ".state/docker-sanity.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    manifest = json.loads(manifest_path.read_text())
    manifest["docker_sanity"] = {"status": "pass", "receipt": ".state/docker-sanity.json", "normal_test_count_per_root": 2, "sanitizer_test_count_per_root": 2, "negative_fixture_count": 180, "negative_fixture_types": 2, "control_count": 3}
    manifest["strongest_local_status"] = "creator_preflight_passed_pending_independent_audit"
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)


def _run_host_build(
    kind: str, root: Path, source: str, mode: str, builds: Path
) -> list[str]:
    """Configure, build, and run one host CTest target; return its ledger row."""
    build_dir = builds / f"{kind}-{root.name}-{mode}-{Path(source).name}"
    flags: list[str] = []
    if mode == "sanitizer":
        flags = [
            "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
            "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
        ]
    configure = subprocess.run(
        ["cmake", "-S", str(root), "-B", str(build_dir), "-G", "Unix Makefiles",
         f"-DTASK_SOURCE={root}/{source}", *flags],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if configure.returncode != 0:
        _fail("reference_compile_failed", f"{root.name} {mode} {source} configure: {configure.stdout[-4000:]}")
    compiled = subprocess.run(
        ["cmake", "--build", str(build_dir), "--parallel", "2"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if compiled.returncode != 0:
        _fail("reference_compile_failed", f"{root.name} {mode} {source} build: {compiled.stdout[-4000:]}")
    discovery = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "-N"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    match = re.search(r"^Total Tests: (\d+)$", discovery.stdout, flags=re.M)
    count = int(match.group(1)) if match else 0
    if count != 2:
        _fail("sanitizer_test_count_mismatch", f"{root.name} {mode} {source} discovered {count}")
    environment = dict(os.environ, ASAN_OPTIONS="detect_leaks=0")
    executed = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=environment,
    )
    if source.startswith(".meta/negative_"):
        if executed.returncode == 0:
            _fail("negative_fixture_not_rejected", f"{root.name} {source} passed its tests")
        outcome = "rejected"
    else:
        if executed.returncode != 0:
            _fail("reference_tests_failed" if mode == "normal" else "reference_sanitizer_failed",
                  f"{root.name} {mode} {source}: {executed.stdout[-4000:]}")
        outcome = "pass"
    return [kind, root.name, mode, source, str(count), outcome]


def verify_host(out: Path = DEFAULT_OUT, workers: int | None = None) -> None:
    """Host normal + fresh ASan/UBSan reference verification (no Docker).

    Mirrors verify_docker's evidence requirements on the host toolchain:
    every reference passes clean normal and fresh sanitizer builds with two
    discovered tests each, both negative fixtures compile and are rejected,
    and all three adversarial controls pass in both modes. The receipt binds
    the current owner and family tree.
    """
    manifest_path = out / ".state/materialization-manifest.json"
    if not manifest_path.is_file():
        _fail("generator_output_drift", "run --verify-core first")
    manifest = json.loads(manifest_path.read_text())
    if manifest["family_tree_hash"] != _tree_hash(out) or manifest["owner_hash"] != _file_hash(Path(__file__)):
        _fail("generator_output_drift", "manifest does not bind current owner/tree")
    compiler = shutil.which("c++")
    cmake = shutil.which("cmake")
    if not compiler or not cmake:
        _fail("reference_compile_failed", "host c++ or cmake unavailable")
    jobs: list[tuple[str, Path, str, str]] = []
    for case in CASES:
        root = out / case.task_id
        jobs.append(("tasks", root, ".meta/example.cpp", "normal"))
        jobs.append(("tasks", root, ".meta/example.cpp", "sanitizer"))
        jobs.append(("tasks", root, ".meta/negative_false_substitute.cpp", "normal"))
        jobs.append(("tasks", root, ".meta/negative_nonempty_absence.cpp", "normal"))
    for name in ("domain-identifier-renamed", "constants-policy-only", "opposite-end-selection"):
        root = out / ".state/adversarial-clone-controls" / name
        jobs.append(("controls", root, ".meta/example.cpp", "normal"))
        jobs.append(("controls", root, ".meta/example.cpp", "sanitizer"))
    with tempfile.TemporaryDirectory(prefix="calendar-expansion-host-") as temporary:
        builds = Path(temporary)
        parallelism = workers or min(8, (os.cpu_count() or 2))
        with concurrent.futures.ThreadPoolExecutor(max_workers=parallelism) as pool:
            rows = list(pool.map(lambda job: _run_host_build(*job, builds), jobs))
    rows.sort()
    refs = [row for row in rows if row[0] == "tasks" and row[3] == ".meta/example.cpp"]
    negatives = [row for row in rows if row[0] == "tasks" and row[3].startswith(".meta/negative_")]
    controls = [row for row in rows if row[0] == "controls"]
    if len(refs) != 180 or len(negatives) != 180 or len(controls) != 6:
        _fail("sanitizer_test_count_mismatch", f"refs={len(refs)} negatives={len(negatives)} controls={len(controls)}")
    detailed_results = [
        {"kind": row[0], "task_or_control_id": row[1], "mode": row[2], "source_role": row[3], "discovered_test_count": int(row[4]), "outcome": row[5]}
        for row in rows
    ]
    results_ledger = "\n".join("\t".join(row) for row in rows) + "\n"
    compiler_version = subprocess.run(["c++", "--version"], text=True, stdout=subprocess.PIPE).stdout.splitlines()[0].strip()
    cmake_version = subprocess.run(["cmake", "--version"], text=True, stdout=subprocess.PIPE).stdout.splitlines()[0].strip()
    receipt = {"schema_version": "calendar-expansion-host-verify-v1", "status": "pass", "evidence_class": "host_verify", "locked_oracle": False, "family_tree_hash": _tree_hash(out), "owner_hash": _file_hash(Path(__file__)), "compiler": {"path": compiler, "version": compiler_version, "sha256": _file_hash(Path(compiler))}, "cmake": cmake_version, "normal_reference_count": 90, "sanitizer_reference_count": 90, "normal_test_count_per_root": 2, "sanitizer_test_count_per_root": 2, "negative_fixture_count": 180, "negative_fixture_types": ["inverted-eligibility", "nonempty-on-absence"], "control_mode_count": 6, "result_ledger_hash": _sha(results_ledger.encode()), "results": detailed_results, "commands": {"normal": "cmake -G Unix Makefiles; cmake --build; ctest -N; ctest --output-on-failure", "sanitizer": "same with -fsanitize=address,undefined -fno-omit-frame-pointer in a fresh build", "environment": "ASAN_OPTIONS=detect_leaks=0"}}
    _write(out / ".state/host-verify.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    manifest = json.loads(manifest_path.read_text())
    manifest["host_verify"] = {"status": "pass", "receipt": ".state/host-verify.json", "normal_test_count_per_root": 2, "sanitizer_test_count_per_root": 2, "negative_fixture_count": 180, "negative_fixture_types": 2, "control_count": 3}
    if manifest.get("docker_sanity", {}).get("status") != "pass":
        manifest["docker_sanity"] = {"status": "not_completed (campaign gate: host verify only)", "stale_receipt": ".state/docker-sanity.json"}
    manifest["strongest_local_status"] = "campaign_verified_host_only"
    _write(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n", True)


def _append_cycle(out: Path, status: str) -> None:
    state = out / ".state/cycles"
    state.mkdir(parents=True, exist_ok=True)
    number = len(list(state.glob("cycle-*.json"))) + 1
    manifest = json.loads((out / ".state/materialization-manifest.json").read_text()) if (out / ".state/materialization-manifest.json").is_file() else {}
    receipt = json.loads((out / ".state/docker-sanity.json").read_text()) if (out / ".state/docker-sanity.json").is_file() else None
    replacement_path = out / ".state/remedy/cycle-03/replaced-roots.json"
    replacements = json.loads(replacement_path.read_text())["replacements"] if replacement_path.is_file() else []
    record = {"schema_version": "aider-task-creator-cycle-v1", "cycle": number, "timestamp": datetime.now(timezone.utc).isoformat(), "status": status, "family_id": FAMILY_ID, "candidate_manifest": ".state/materialization-manifest.json", "family_tree_hash": _tree_hash(out), "curriculum_hash": _file_hash(CURRICULUM), "generator_hash": _file_hash(Path(__file__)), "focused_test_hash": _file_hash(TEST_PATH), "grader_policy_hash": _sha((SANITY_IMAGE + CMAKE).encode()), "retained_root_ids": [case.task_id for case in CASES], "replaced_root_ids": [row["replacement_task_id"] for row in replacements], "rejected_root_ids": [row["rejected_task_id"] for row in replacements], "review_root_ids": [], "blocked_root_ids": [], "manifest_subject_hash": _sha(json.dumps(manifest, sort_keys=True).encode()), "docker_receipt": receipt}
    _write(state / f"cycle-{number:02d}.json", json.dumps(record, indent=2, sort_keys=True) + "\n", False)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--record-cycle", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify_core or args.verify_host or args.docker_sanity:
        verify_core(args.out)
    if args.verify_host:
        verify_host(args.out)
    if args.docker_sanity:
        verify_docker(args.out)
    if args.record_cycle:
        manifest = json.loads(
            (args.out / ".state/materialization-manifest.json").read_text()
        )
        status = (
            "creator_preflight"
            if manifest.get("strongest_local_status")
            in (
                "creator_preflight_passed_pending_independent_audit",
                "campaign_verified_host_only",
            )
            else "generated"
        )
        _append_cycle(args.out, status)
    print(f"Wrote {len(roots)} weekday/recurrence/business-day roots under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
