"""Create and verify the 90-root cross-midnight/offset/meeting expansion family."""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import heapq
import itertools
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_cross_midnight_offsets_meetings_cases import (
    REDUCERS as REDUCERS,
    TASKS,
    TRANSFORMS as TRANSFORMS,
    TaskSpec,
)
from w8_biayn.integrations.moonlight_cross_midnight_offsets_meetings_hard_rule import (
    HARD_DIMENSIONS,
    MAX_NORMALIZED_SIMILARITY,
    analyze_root,
    compare_roots,
    read_artifacts,
)


EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
DEFAULT_OUT = EXPANSION_ROOT / "time-date/cross-midnight-offsets-meetings"
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-clock-tasks/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_CROSS_MIDNIGHT_OFFSETS_MEETINGS_EXPANSION_CURRICULUM.md"
)
FAMILY_SPEC = Path(
    "docs/aider-tasks-spec/aider-expansion-v1/cross-midnight-offsets-meetings.md"
)
SELECTED_PROMPT = Path("docs/aider-tasks-spec/prompts/generate-family-spec.md")
IMPLEMENT_PROMPT = Path("docs/aider-tasks-spec/prompts/implement-family-for-sft.md")
BENCHMARK_MANIFEST = Path("manifests/aider_sft/aider-polyglot-cpp-26.json")
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
FAMILY_ID = "aider-expansion-v1/time-date/cross-midnight-offsets-meetings-v1"
SCHEMA_VERSION = "aider-expansion-cross-midnight-offset-meeting-v1"
NORMALIZER = "time-pipeline-seven-dimension-v1"
PLAN_REVERIFY_ROOTS_SHA256 = (
    "d0eedeacf075e30b357100a92a5b39a524fba7a1290cf607a0d30aacd5202791"
)
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
SANITY_IMAGE_ID = "sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
OWNER_PATHS = {
    "materializer": Path(__file__),
    "cases": Path(__file__).with_name(
        "moonlight_cross_midnight_offsets_meetings_cases.py"
    ),
    "hard_rule": Path(__file__).with_name(
        "moonlight_cross_midnight_offsets_meetings_hard_rule.py"
    ),
}
CONTROL_NAMES = (
    "domain-identifier-renamed-clone",
    "constants-policy-only-clone",
    "opposite-end-selection-clone",
)


CMAKE = r'''cmake_minimum_required(VERSION 3.16)
project(cross_midnight_offsets_meetings LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
enable_testing()
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/TASK_CPP" CACHE FILEPATH "Implementation to grade")
set(NEGATIVE_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/.meta/negative.cpp" CACHE FILEPATH "False substitute")
foreach(mode visible hidden)
  if(mode STREQUAL "visible")
    set(TEST_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task_visible_test.cpp")
  else()
    set(TEST_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/.meta/task_hidden_test.cpp")
  endif()
  add_executable(task_${mode} "${TASK_SOURCE}" "${TEST_SOURCE}")
  add_executable(negative_${mode} "${NEGATIVE_SOURCE}" "${TEST_SOURCE}")
  foreach(target task_${mode} negative_${mode})
    target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
    if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
      target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
    endif()
  endforeach()
  add_test(NAME ${mode} COMMAND task_${mode})
endforeach()
'''


DOCKER_SCRIPT = r'''set -eu
rm -rf /tmp/w8-time-family /tmp/w8-time-build
mkdir -p /tmp/w8-time-family
tar -xf /input/family.tar -C /tmp/w8-time-family
compiler=$(command -v c++)
echo "W8TOOL compiler_path $compiler"
echo "W8TOOL compiler_hash sha256:$(sha256sum "$compiler" | sed 's/ .*//')"
echo "W8TOOL compiler_version $(c++ --version | head -1)"
echo "W8TOOL cmake_version $(cmake --version | head -1)"
run_root() {
  category=$1
  root=$2
  item=${root##*/}
  mounted_hash=$(python3 -c 'import hashlib,pathlib,sys
r=pathlib.Path(sys.argv[1]);d=hashlib.sha256()
for p in sorted(x for x in r.rglob("*") if x.is_file() and ".state" not in x.relative_to(r).parts):
 d.update(p.relative_to(r).as_posix().encode());d.update(b"\0");d.update(p.read_bytes());d.update(b"\0")
print("sha256:"+d.hexdigest())' "$root")
  echo "W8HASH $category $item $mounted_hash"
  for mode in normal asan_ubsan; do
    flags=
    if [ "$mode" = asan_ubsan ]; then flags='-fsanitize=address,undefined -fno-omit-frame-pointer'; fi
    build=/tmp/w8-time-build/$category-$item-$mode
    cmake -S "$root" -B "$build" -G 'Unix Makefiles' -DCMAKE_CXX_COMPILER="$compiler" -DTASK_SOURCE="$root/.meta/example.cpp" -DNEGATIVE_SOURCE="$root/.meta/negative.cpp" -DCMAKE_CXX_FLAGS="$flags" -DCMAKE_EXE_LINKER_FLAGS="$flags" >/dev/null
    cmake --build "$build" --parallel 2 >/dev/null
    count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: *//p')
    test "$count" = 2
    ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$build" --output-on-failure >/dev/null
    if [ "$category" = tasks ]; then
      set +e
      ASAN_OPTIONS=detect_leaks=0 "$build/negative_visible" >/tmp/negative-visible.log 2>&1
      visible_status=$?
      ASAN_OPTIONS=detect_leaks=0 "$build/negative_hidden" >/tmp/negative-hidden.log 2>&1
      hidden_status=$?
      set -e
      if [ "$visible_status" = 0 ] && [ "$hidden_status" = 0 ]; then
        echo "false substitute unexpectedly passed for $item $mode" >&2
        exit 31
      fi
      echo "W8NEG $category $item $mode rejected"
    fi
    echo "W8COUNT $category $item $mode $count"
  done
}
for root in /tmp/w8-time-family/family/*; do
  [ -d "$root" ] || continue
  [ "${root##*/}" = .state ] && continue
  run_root tasks "$root"
done
for root in /tmp/w8-time-family/family/.state/hard-rule-controls/*; do
  [ -d "$root" ] || continue
  run_root controls "$root"
done
'''


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _sha_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        item
        for item in root.rglob("*")
        if item.is_file() and ".state" not in item.relative_to(root).parts
    ):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _family_hash(out: Path) -> str:
    digest = hashlib.sha256()
    for task in TASKS:
        digest.update(task.task_id.encode())
        digest.update(b"\0")
        digest.update(_tree_hash(out / task.task_id).encode())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _owner_hashes() -> dict[str, str]:
    return {name: _sha_file(path) for name, path in OWNER_PATHS.items()}


def _owner_revision() -> str:
    digest = hashlib.sha256()
    for name, value in sorted(_owner_hashes().items()):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(value.encode())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _write(path: Path, content: str, force: bool = True) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; use --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _validate_out(out: Path) -> None:
    expected = DEFAULT_OUT.resolve()
    if out.resolve() != expected:
        _fail("unsafe_expansion_output", f"required {DEFAULT_OUT}, received {out}")
    if any(path.is_symlink() for path in (out, *out.parents) if path.exists()):
        _fail("unsafe_expansion_output", "symlinked output path")
    for forbidden in (LEGACY_ROOT.resolve(), REVERIFY_ROOT.resolve()):
        try:
            out.resolve().relative_to(forbidden)
        except ValueError:
            continue
        _fail("unsafe_expansion_output", f"existing tree is read-only: {forbidden}")


def _owned_root(root: Path) -> bool:
    provenance = root / ".meta/provenance.json"
    if not provenance.is_file():
        return False
    try:
        return json.loads(provenance.read_text(encoding="utf-8")).get("family_id") == FAMILY_ID
    except json.JSONDecodeError:
        return False


def _inventory_configs(root: Path) -> tuple[Path, ...]:
    if not root.is_dir():
        return ()
    return tuple(
        sorted(
            path
            for path in root.rglob("config.json")
            if path.parent.name == ".meta" and ".state" not in path.relative_to(root).parts
        )
    )


def _plan_root_inventory_hash(root: Path) -> str:
    paths = [
        config.parent.parent.as_posix()
        for config in _inventory_configs(root)
    ]
    payload = ("\n".join(paths) + "\n").encode()
    return hashlib.sha256(payload).hexdigest()


def _inventory_existing(out: Path) -> dict[str, Any]:
    roots: list[dict[str, str]] = []
    seen: set[str] = set()
    expansion_roots = _inventory_configs(EXPANSION_ROOT)
    owner_expansion_roots = tuple(
        path for path in expansion_roots if _owned_root(path.parent.parent)
    )
    foreign_expansion_roots = tuple(
        path for path in expansion_roots if not _owned_root(path.parent.parent)
    )
    for source_name, configs in (
        ("legacy", _inventory_configs(LEGACY_ROOT)),
        ("reverify", _inventory_configs(REVERIFY_ROOT)),
        ("expansion-v1-foreign", foreign_expansion_roots),
    ):
        for config_path in configs:
            task_root = config_path.parent.parent
            task_id = task_root.name
            if task_id in seen:
                # Duplicate leaf IDs already exist across legacy/reverify and are
                # reserved once for collision purposes.
                pass
            seen.add(task_id)
            docs = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in sorted((task_root / ".docs").glob("*.md"))
            )
            config = json.loads(config_path.read_text(encoding="utf-8"))
            headers = "\n".join(
                (task_root / rel).read_text(encoding="utf-8", errors="replace")
                for rel in config.get("files", {}).get("solution", [])
                if (task_root / rel).suffix in {".h", ".hpp"} and (task_root / rel).is_file()
            )
            roots.append(
                {
                    "source": source_name,
                    "task_id": task_id,
                    "path": task_root.as_posix(),
                    "contract_hash": _sha_bytes((docs + "\n" + headers).encode()),
                    "normalized_contract": _normalize_contract(docs + "\n" + headers),
                }
            )
    requested = {task.task_id for task in TASKS}
    collisions = sorted(requested & seen)
    if collisions:
        _fail("duplicate_task", ", ".join(collisions))
    reverify_hash = _plan_root_inventory_hash(REVERIFY_ROOT)
    if reverify_hash != PLAN_REVERIFY_ROOTS_SHA256:
        _fail(
            "count_plan_inventory_drift",
            f"expected {PLAN_REVERIFY_ROOTS_SHA256}, found {reverify_hash}",
        )
    return {
        "roots": roots,
        "reserved_task_ids": sorted(seen),
        "expansion_roots_before": len(expansion_roots),
        "owner_expansion_roots_before": len(owner_expansion_roots),
        "foreign_expansion_roots_before": len(foreign_expansion_roots),
        "reverify_sorted_root_sha256": reverify_hash,
    }


def _normalize_contract(text: str) -> str:
    text = re.sub(r"`[^`]*`", " ", text.lower())
    text = re.sub(r"[^a-z]+", " ", text)
    stop = {
        "the", "a", "an", "and", "or", "to", "of", "in", "is", "are", "for",
        "with", "each", "return", "returns", "must", "task", "implement",
        "pragma", "once", "include", "utility", "vector", "namespace", "curriculum",
        "struct", "class", "public", "private", "const", "int", "long", "bool",
        "true", "false", "valid", "std", "size", "input", "output", "result",
        "function", "files", "editable", "complete", "replacement", "invalid",
        "without", "all", "only", "one", "no", "other", "this", "that", "then",
    }
    return " ".join(word for word in text.split() if word not in stop)


def _contract_similarity(left: str, right: str) -> float:
    a, b = set(left.split()), set(right.split())
    return len(a & b) / max(1, min(len(a), len(b)))


def _parse_rows(literal: str) -> list[list[int]]:
    return [
        [int(part.strip()) for part in group.split(",")]
        for group in re.findall(r"\{([^{}]+)\}", literal)
    ]


def _transform_rows(key: str, rows: list[list[int]]) -> tuple[bool, list[tuple[int, int, int, int]]]:
    ids: set[int] = set()
    spans: list[tuple[int, int, int, int]] = []
    finishes: dict[int, int] = {}
    for row in rows:
        identity = row[0]
        if identity <= 0 or identity in ids:
            return False, []
        ids.add(identity)
        if key == "wrap":
            _, start, end, load = row
            if not (0 <= start < 1440 and 0 <= end < 1440) or start == end or load <= 0:
                return False, []
            if end < start:
                end += 1440
            spans.append((identity, start, end, load))
        elif key == "offset":
            _, start, end, offset, load = row
            if not (0 <= start < 1440 and 0 <= end < 1440) or start == end or not (-840 <= offset <= 840) or load <= 0:
                return False, []
            duration = end - start
            if duration <= 0:
                duration += 1440
            start = (start - offset) % 1440
            spans.append((identity, start, start + duration, load))
        elif key == "participant":
            # Handled as a grouped pass below after validating unique window IDs.
            pass
        elif key == "day":
            _, start, end, day, load = row
            if not (0 <= start < 1440 and 0 <= end < 1440) or start == end or day not in {0, 1} or load <= 0:
                return False, []
            start += day * 1440
            end += day * 1440
            if end < start:
                end += 1440
            if end > 2880:
                return False, []
            spans.append((identity, start, end, load))
        elif key == "repeat":
            _, start, duration, period, repeats, load = row
            if start < 0 or start >= 2880 or min(duration, period, repeats, load) <= 0 or repeats > 8:
                return False, []
            for repeat in range(repeats):
                item_start = start + repeat * period
                if item_start + duration > 2880:
                    return False, []
                spans.append((identity * 10 + repeat, item_start, item_start + duration, load))
        elif key == "clip":
            _, start, end, clip_start, clip_end, load = row
            if start < 0 or start >= end or end > 2880 or clip_start < 0 or clip_start >= clip_end or clip_end > 2880 or load <= 0:
                return False, []
            start, end = max(start, clip_start), min(end, clip_end)
            if start < end:
                spans.append((identity, start, end, load))
        elif key == "buffer":
            _, start, end, before, after, load = row
            if start < 0 or start >= end or end > 2880 or min(before, after) < 0 or start < before or end > 2880 - after or load <= 0:
                return False, []
            spans.append((identity, start - before, end + after, load))
        elif key == "capacity":
            _, start, end, capacity = row
            if start < 0 or start >= end or end > 2880 or capacity <= 0:
                return False, []
            spans.append((identity, start, end, capacity))
        elif key == "precedence":
            _, start, end, predecessor, lag, load = row
            if start < 0 or start >= end or end > 2880 or predecessor < 0 or lag < 0 or load <= 0:
                return False, []
            duration = end - start
            if predecessor:
                if predecessor not in finishes:
                    return False, []
                start = max(start, finishes[predecessor] + lag)
            if start + duration > 2880:
                return False, []
            finishes[identity] = start + duration
            spans.append((identity, start, start + duration, load))
        elif key == "blackout":
            _, start, end, blackout_start, blackout_end, load = row
            if start < 0 or start >= end or end > 2880 or blackout_start < start or blackout_end > end or blackout_start > blackout_end or load <= 0:
                return False, []
            if blackout_start == blackout_end:
                spans.append((identity, start, end, load))
            else:
                if start < blackout_start:
                    spans.append((identity * 10, start, blackout_start, load))
                if blackout_end < end:
                    spans.append((identity * 10 + 1, blackout_end, end, load))
        else:
            raise AssertionError(key)
    if key == "participant":
        common: dict[int, tuple[int, int, int]] = {}
        for window_id, participant_id, start, end, offset, priority in rows:
            if window_id <= 0 or participant_id <= 0 or not (0 <= start < 1440 and 0 <= end < 1440) or start == end or not (-840 <= offset <= 840) or priority <= 0:
                return False, []
            duration = end - start
            if duration <= 0:
                duration += 1440
            start = (start - offset) % 1440
            if participant_id not in common:
                common[participant_id] = (start, start + duration, priority)
            else:
                old_start, old_end, old_priority = common[participant_id]
                if old_priority != priority:
                    return False, []
                common[participant_id] = (max(old_start, start), min(old_end, start + duration), priority)
        spans = [
            (participant_id, start, end, priority)
            for participant_id, (start, end, priority) in sorted(common.items())
            if start < end
        ]
    return True, spans


def _reducer_args(key: str) -> tuple[int, ...]:
    return {"exact": (3,), "slot": (3, 30), "gap": (0, 600)}.get(key, ())


def _reduce(key: str, spans: list[tuple[int, int, int, int]], args: tuple[int, ...]) -> dict[str, Any]:
    if key == "union":
        merged: list[list[int]] = []
        for _, start, end, _ in sorted(spans, key=lambda row: (row[1], row[2])):
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        return {"metric": sum(end - start for start, end in merged), "aux": len(merged)}
    if key in {"peak", "weighted"}:
        events = sorted((point, delta) for _, start, end, load in spans for point, delta in ((start, load), (end, -load)))
        current = peak = 0
        first = -1
        previous = 0
        weighted = 0
        for point, delta in events:
            weighted += (point - previous) * current
            current += delta
            if current > peak:
                peak, first = current, point
            previous = point
        if key == "peak":
            return {"metric": peak, "aux": first}
        return {"long_metric": weighted, "aux": peak}
    if key in {"exact", "slot"}:
        load = [0] * 2880
        for _, start, end, weight in spans:
            for minute in range(start, end):
                load[minute] += weight
        if key == "exact":
            exact = args[0]
            return {"metric": sum(value == exact for value in load), "aux": exact}
        required, duration = args
        run = -1
        for minute, value in enumerate(load):
            if value >= required:
                if run < 0:
                    run = minute
                if minute + 1 - run >= duration:
                    return {"found": "true", "metric": run, "aux": run + duration}
            else:
                run = -1
        return {"found": "false", "metric": -1, "aux": -1}
    if key == "gap":
        horizon_start, horizon_end = args
        clipped = sorted((max(horizon_start, start), min(horizon_end, end)) for _, start, end, _ in spans if max(horizon_start, start) < min(horizon_end, end))
        cursor = horizon_start
        best = (-1, -1, 0)
        for start, end in clipped:
            if start > cursor and start - cursor > best[2]:
                best = (cursor, start, start - cursor)
            cursor = max(cursor, end)
        if horizon_end - cursor > best[2]:
            best = (cursor, horizon_end, horizon_end - cursor)
        return {"metric": best[0], "aux": best[1], "extra": best[2]}
    if key == "rooms":
        busy: list[tuple[int, int]] = []
        free: list[int] = []
        next_room = 0
        assigned: list[int] = []
        for identity, start, end, _ in sorted(spans, key=lambda row: (row[1], row[2], row[0])):
            del identity
            while busy and busy[0][0] <= start:
                _, room = heapq.heappop(busy)
                heapq.heappush(free, room)
            if free:
                room = heapq.heappop(free)
            else:
                room, next_room = next_room, next_room + 1
            assigned.append(room)
            heapq.heappush(busy, (end, room))
        return {"metric": next_room, "vector": _cpp_vector(assigned)}
    if key == "order":
        ids = [identity for identity, _, _, _ in sorted(spans, key=lambda row: (row[1], row[2], row[0]))]
        return {"vector": _cpp_vector(ids)}
    if key == "conflicts":
        pairs = sorted(
            {
                tuple(sorted((left[0], right[0])))
                for index, left in enumerate(spans)
                for right in spans[index + 1 :]
                if max(left[1], right[1]) < min(left[2], right[2])
            }
        )
        literal = "std::vector<std::pair<int,int>>{" + ",".join(f"{{{a},{b}}}" for a, b in pairs) + "}"
        return {"metric": len(pairs), "pairs": literal}
    raise AssertionError(key)


def _cpp_vector(values: Sequence[int]) -> str:
    return "std::vector<int>{" + ",".join(str(value) for value in values) + "}"


def _expected(task: TaskSpec, literal: str) -> dict[str, Any]:
    valid, spans = _transform_rows(task.transform.key, _parse_rows(literal))
    if not valid:
        raise AssertionError(f"invalid owner fixture for {task.task_id}")
    return _reduce(task.reducer.key, spans, _reducer_args(task.reducer.key))


def _input_type(task: TaskSpec) -> str:
    return task.transform.input_name


def _field_names(declarations: str) -> tuple[str, ...]:
    return tuple(
        re.findall(
            r"(?:\bbool|\bint|\blong long|std::vector<[^;]+>)\s+"
            r"([a-zA-Z_][a-zA-Z0-9_]*)(?:\s*=\s*[^;]+)?\s*;",
            declarations,
        )
    )


def _id_field(task: TaskSpec) -> str:
    return {
        "participant": "window_id",
        "capacity": "room_id",
    }.get(task.transform.key, "id")


def _weight_field(task: TaskSpec) -> str:
    return {
        "participant": "priority",
        "capacity": "capacity",
    }.get(task.transform.key, "load")


def _arithmetic_guard(task: TaskSpec) -> str:
    transform = task.transform.key
    extra = ""
    if transform == "participant":
        extra = "||item.participant_id<=0||item.participant_id>200000000"
    elif transform == "repeat":
        extra = "||item.duration>2880||item.period>2880"
    elif transform == "precedence":
        extra = "||item.lag>2880"
    return (
        "if(input.size()>1000){return false;}\n"
        f"for(const auto& item:input){{\nif(item.{_id_field(task)}<=0||"
        f"item.{_id_field(task)}>200000000||item.{_weight_field(task)}<=0||"
        f"item.{_weight_field(task)}>1000000{extra}){{return false;}}\n}}"
    )


def _header(task: TaskSpec) -> str:
    reducer = task.reducer
    transform = task.transform
    return f'''#pragma once
#include <utility>
#include <vector>
namespace curriculum {{
struct {transform.input_name}{{{transform.fields}}};
struct {reducer.report_name}{{{reducer.report_fields}}};
{reducer.report_name} {task.function_name}(const std::vector<{transform.input_name}>& input{reducer.parameters});
}}
'''


def _starter(task: TaskSpec) -> str:
    return f'''#include "{task.task_id}.h"
namespace curriculum {{ {task.reducer.report_name} {task.function_name}(const std::vector<{_input_type(task)}>&{task.reducer.parameters}){{return {{}};}} }}
'''


def _reference(task: TaskSpec) -> str:
    return f'''#include "{task.task_id}.h"
#include <algorithm>
#include <array>
#include <functional>
#include <map>
#include <queue>
#include <set>
// W8_TRANSFORM:{task.transform.key}
// W8_REDUCER:{task.reducer.key}
namespace curriculum {{ namespace {{
struct Span{{int id;int start;int end;int load;}};
[[maybe_unused]] bool valid_clock(int minute){{return minute>=0&&minute<1440;}}
bool make_spans(const std::vector<{task.transform.input_name}>& input,std::vector<Span>& spans){{
  std::set<int> ids;
  {_arithmetic_guard(task)}
  {task.transform.reference}
  return true;
}}
}}
{task.reducer.report_name} {task.function_name}(const std::vector<{task.transform.input_name}>& input{task.reducer.parameters}){{
  {task.reducer.report_name} out;
  std::vector<Span> spans;
  if(!make_spans(input,spans))return out;
  {task.reducer.reference}
  return out;
}}
}}
'''


def _negative(task: TaskSpec, reference: str) -> str:
    changed = reference
    for old, new in (
        (task.transform.negative_old, task.transform.negative_new),
        (task.reducer.negative_old, task.reducer.negative_new),
    ):
        if changed.count(old) != 1:
            _fail("invariant_not_enforced", f"{task.task_id}: mutation {old!r}")
        changed = changed.replace(old, new, 1)
    if changed == reference:
        _fail("invariant_not_enforced", task.task_id)
    return changed


def _argument_values(task: TaskSpec) -> str:
    args = _reducer_args(task.reducer.key)
    return "" if not args else ", " + ", ".join(str(value) for value in args)


def _assertion(task: TaskSpec, literal: str, variable: str = "out") -> str:
    expected = _expected(task, literal)
    return task.reducer.assertion.format(**expected).replace("out.", f"{variable}.")


def _transform_witness(task: TaskSpec, literal: str) -> str:
    rows = _parse_rows(literal)
    key = task.transform.key
    if key == "wrap":
        expected = sum(row[2] < row[1] for row in rows)
        return f"int wrapped=0;for(const auto& item:input)if(item.end_minute<item.start_minute)++wrapped;if(wrapped!={expected})return 2;"
    if key == "offset":
        expected = sum(row[3] for row in rows)
        return f"int offset_sum=0;for(const auto& item:input)offset_sum+=item.utc_offset;if(offset_sum!={expected})return 2;"
    if key == "day":
        expected = sum(row[3] for row in rows)
        return f"int projected_days=0;for(const auto& item:input)projected_days+=item.day_index;if(projected_days!={expected})return 2;"
    if key == "repeat":
        expected = sum(row[2] * row[4] for row in rows)
        return f"int occurrence_minutes=0;for(const auto& item:input)occurrence_minutes+=item.duration*item.repeats;if(occurrence_minutes!={expected})return 2;"
    if key == "clip":
        expected = sum(row[3] > row[1] or row[4] < row[2] for row in rows)
        return f"int clipped=0;for(const auto& item:input)if(item.clip_start>item.start_minute||item.clip_end<item.end_minute)++clipped;if(clipped!={expected})return 2;"
    if key == "buffer":
        expected = sum(row[3] + row[4] for row in rows)
        return f"int buffer_minutes=0;for(const auto& item:input)buffer_minutes+=item.before+item.after;if(buffer_minutes!={expected})return 2;"
    if key == "participant":
        expected = sum(row[5] for row in rows)
        return f"int priority_sum=0;for(const auto& item:input){{if(item.window_id<=0||item.participant_id<=0)return 2;priority_sum+=item.priority;}}if(priority_sum!={expected})return 2;"
    if key == "capacity":
        expected = sum(row[3] for row in rows)
        return f"int seat_capacity=0;for(const auto& item:input)seat_capacity+=item.capacity;if(seat_capacity!={expected})return 2;"
    if key == "precedence":
        expected = sum(row[4] for row in rows if row[3])
        return f"int handoff_lag=0;for(const auto& item:input)if(item.predecessor_id!=0)handoff_lag+=item.lag;if(handoff_lag!={expected})return 2;"
    if key == "blackout":
        expected = sum(row[4] - row[3] for row in rows)
        return f"int blackout_minutes=0;for(const auto& item:input)blackout_minutes+=item.blackout_end-item.blackout_start;if(blackout_minutes!={expected})return 2;"
    raise AssertionError(key)


def _reducer_witness(task: TaskSpec, variable: str, failure: int) -> str:
    key = task.reducer.key
    checks = {
        "union": f"if({variable}.covered_minutes<0||{variable}.segment_count<0)return {failure};",
        "peak": f"if(({variable}.peak_load==0)!=({variable}.first_minute==-1))return {failure};",
        "exact": f"if({variable}.exact_minutes<0||{variable}.exact_load!=3)return {failure};",
        "slot": f"if({variable}.found&&({variable}.start_minute<0||{variable}.end_minute-{variable}.start_minute!=30))return {failure};",
        "gap": f"if({variable}.minutes<0||({variable}.minutes>0&&{variable}.end_minute-{variable}.start_minute!={variable}.minutes))return {failure};",
        "rooms": f"for(int room:{variable}.room_by_sorted_span)if(room<0||room>={variable}.rooms)return {failure};",
        "weighted": f"if({variable}.weighted_minutes<0||{variable}.peak_weight<0)return {failure};",
        "order": f"if({variable}.ids.size()>1000)return {failure};",
        "conflicts": f"if({variable}.count!=static_cast<int>({variable}.pairs.size()))return {failure};",
    }
    return checks[key]


def _touching_tie_literal(task: TaskSpec) -> str:
    return {
        "wrap": "{{3,60,120,1},{1,60,120,2},{2,120,180,3}}",
        "offset": "{{3,60,120,0,1},{1,60,120,0,2},{2,120,180,0,3}}",
        "day": "{{3,60,120,0,1},{1,60,120,0,2},{2,120,180,0,3}}",
        "repeat": "{{3,60,60,120,1,1},{1,60,60,120,1,2},{2,120,60,120,1,3}}",
        "clip": "{{3,60,120,60,120,1},{1,60,120,60,120,2},{2,120,180,120,180,3}}",
        "buffer": "{{3,70,110,10,10,1},{1,70,110,10,10,2},{2,130,170,10,10,3}}",
        "participant": "{{30,3,60,120,0,1},{10,1,60,120,0,2},{20,2,120,180,0,3}}",
        "capacity": "{{3,60,120,1},{1,60,120,2},{2,120,180,3}}",
        "precedence": "{{3,60,120,0,0,1},{1,60,120,0,0,2},{2,120,180,0,0,3}}",
        "blackout": "{{3,60,120,90,90,1},{1,60,120,90,90,2},{2,120,180,150,150,3}}",
    }[task.transform.key]


def _inclusive_maximum_mutation(task: TaskSpec) -> str:
    specific = {
        "wrap": "boundary[0].start_minute=0;boundary[0].end_minute=1439;",
        "offset": "boundary[0].start_local=0;boundary[0].end_local=1;boundary[0].utc_offset=840;",
        "day": "boundary[0].start_minute=0;boundary[0].end_minute=1439;boundary[0].day_index=1;",
        "repeat": "boundary[0].start_minute=0;boundary[0].duration=2880;boundary[0].period=2880;boundary[0].repeats=1;",
        "clip": "boundary[0].start_minute=0;boundary[0].end_minute=2880;boundary[0].clip_start=0;boundary[0].clip_end=2880;",
        "buffer": "boundary[0].start_minute=0;boundary[0].end_minute=2880;boundary[0].before=0;boundary[0].after=0;",
        "participant": "boundary[0].participant_id=200000000;boundary[0].start_local=0;boundary[0].end_local=1;boundary[0].utc_offset=840;",
        "capacity": "boundary[0].start_minute=0;boundary[0].end_minute=2880;",
        "precedence": "boundary[0].start_minute=0;boundary[0].end_minute=1;boundary[0].predecessor_id=0;boundary[0].lag=2880;",
        "blackout": "boundary[0].start_minute=0;boundary[0].end_minute=2880;boundary[0].blackout_start=1440;boundary[0].blackout_end=1440;",
    }[task.transform.key]
    return (
        f"boundary[0].{_id_field(task)}=200000000;"
        f"boundary[0].{_weight_field(task)}=1000000;"
        + specific
    )


def _valid_omission_literal(task: TaskSpec) -> str | None:
    return {
        "clip": "{{1,100,200,300,400,1}}",
        "participant": "{{1,10,60,120,0,1},{2,10,180,240,0,1}}",
    }.get(task.transform.key)


def _same_input_function(task: TaskSpec) -> str:
    comparisons = "&&".join(
        f"left[index].{field}==right[index].{field}"
        for field in _field_names(task.transform.fields)
    )
    return f'''bool same_input(const std::vector<curriculum::{_input_type(task)}>& left,const std::vector<curriculum::{_input_type(task)}>& right){{
  if(left.size()!=right.size())return false;
  for(std::size_t index=0;index<left.size();++index)if(!({comparisons}))return false;
  return true;
}}
'''


def _same_report_function(task: TaskSpec) -> str:
    comparisons = "&&".join(
        f"left.{field}==right.{field}"
        for field in _field_names(task.reducer.report_fields)
    )
    return f'''bool same_report(const curriculum::{task.reducer.report_name}& left,const curriculum::{task.reducer.report_name}& right){{return {comparisons};}}
'''


def _transform_invalid_mutations(task: TaskSpec) -> tuple[tuple[str, str], ...]:
    common = [
        ("id-zero", f"bad[0].{_id_field(task)}=0;"),
        ("id-upper-bound", f"bad[0].{_id_field(task)}=200000001;"),
        ("duplicate-id", "bad.push_back(bad.front());"),
        ("weight-zero", f"bad[0].{_weight_field(task)}=0;"),
        ("weight-upper-bound", f"bad[0].{_weight_field(task)}=1000001;"),
    ]
    specific: dict[str, tuple[tuple[str, str], ...]] = {
        "wrap": (
            ("clock-lower-bound", "bad[0].start_minute=-1;"),
            ("clock-upper-bound", "bad[0].end_minute=1440;"),
            ("nonempty-window", "bad[0].end_minute=bad[0].start_minute;"),
        ),
        "offset": (
            ("local-clock-bound", "bad[0].start_local=-1;"),
            ("nonempty-window", "bad[0].end_local=bad[0].start_local;"),
            ("offset-lower-bound", "bad[0].utc_offset=-841;"),
            ("offset-upper-bound", "bad[0].utc_offset=841;"),
        ),
        "day": (
            ("local-clock-bound", "bad[0].end_minute=1440;"),
            ("nonempty-window", "bad[0].end_minute=bad[0].start_minute;"),
            ("day-index", "bad[0].day_index=2;"),
            ("two-day-horizon", "bad[0].start_minute=1380;bad[0].end_minute=60;bad[0].day_index=1;"),
        ),
        "repeat": (
            ("start-bound", "bad[0].start_minute=2880;"),
            ("duration-positive", "bad[0].duration=0;"),
            ("duration-arithmetic-bound", "bad[0].duration=2881;"),
            ("period-positive", "bad[0].period=0;"),
            ("period-arithmetic-bound", "bad[0].period=2881;"),
            ("repeat-positive", "bad[0].repeats=0;"),
            ("repeat-upper-bound", "bad[0].repeats=9;"),
            ("final-occurrence-horizon", "bad[0].start_minute=2800;bad[0].duration=81;bad[0].period=1;bad[0].repeats=1;"),
        ),
        "clip": (
            ("source-lower-bound", "bad[0].start_minute=-1;"),
            ("source-nonempty", "bad[0].end_minute=bad[0].start_minute;"),
            ("source-upper-bound", "bad[0].end_minute=2881;"),
            ("clip-lower-bound", "bad[0].clip_start=-1;"),
            ("clip-nonempty", "bad[0].clip_end=bad[0].clip_start;"),
            ("clip-upper-bound", "bad[0].clip_end=2881;"),
        ),
        "buffer": (
            ("source-nonempty", "bad[0].end_minute=bad[0].start_minute;"),
            ("before-nonnegative", "bad[0].before=-1;"),
            ("after-nonnegative", "bad[0].after=-1;"),
            ("buffer-underflow", "bad[0].before=bad[0].start_minute+1;"),
            ("buffer-overflow", "bad[0].after=2881-bad[0].end_minute;"),
        ),
        "participant": (
            ("participant-id-positive", "bad[0].participant_id=0;"),
            ("participant-id-upper-bound", "bad[0].participant_id=200000001;"),
            ("local-clock-bound", "bad[0].start_local=-1;"),
            ("nonempty-window", "bad[0].end_local=bad[0].start_local;"),
            ("offset-bound", "bad[0].utc_offset=841;"),
            ("consistent-priority", "bad[1].priority=bad[0].priority+1;"),
        ),
        "capacity": (
            ("range-lower-bound", "bad[0].start_minute=-1;"),
            ("range-nonempty", "bad[0].end_minute=bad[0].start_minute;"),
            ("range-upper-bound", "bad[0].end_minute=2881;"),
        ),
        "precedence": (
            ("range-nonempty", "bad[0].end_minute=bad[0].start_minute;"),
            ("predecessor-nonnegative", "bad[0].predecessor_id=-1;"),
            ("predecessor-must-precede", "bad[0].predecessor_id=999;"),
            ("lag-nonnegative", "bad[0].lag=-1;"),
            ("lag-arithmetic-bound", "bad[0].lag=2881;"),
            ("shifted-horizon", "bad[1].lag=2800;"),
        ),
        "blackout": (
            ("source-nonempty", "bad[0].end_minute=bad[0].start_minute;"),
            ("source-upper-bound", "bad[0].end_minute=2881;"),
            ("blackout-contained-left", "bad[0].blackout_start=bad[0].start_minute-1;"),
            ("blackout-contained-right", "bad[0].blackout_end=bad[0].end_minute+1;"),
            ("blackout-ordered", "bad[0].blackout_start=bad[0].blackout_end+1;"),
        ),
    }
    return tuple(common) + specific[task.transform.key]


def _invalid_case(task: TaskSpec, label: str, mutation: str, code: int) -> str:
    return f'''  // W8_ASSERT:hidden.invalid.{label}
  {{auto bad=input;{mutation}auto bad_before=bad;auto invalid={task.function_name}(bad{_argument_values(task)});if(!same_report(invalid,{task.reducer.report_name}{{}}))return {code};if(!same_input(bad,bad_before))return {code};}}
'''


def _reducer_invalid_cases(task: TaskSpec, start_code: int) -> tuple[str, tuple[str, ...]]:
    calls = {
        "exact": (("exact-load-positive", "0"),),
        "slot": (("required-load-positive", "0, 30"), ("duration-positive", "3, 0")),
        "gap": (("horizon-nonempty", "10, 10"), ("horizon-lower-bound", "-1, 10"), ("horizon-upper-bound", "0, 2881")),
    }.get(task.reducer.key, ())
    blocks = []
    labels = []
    for offset, (label, arguments) in enumerate(calls):
        code = start_code + offset
        labels.append(f"hidden.reducer-invalid.{label}")
        blocks.append(
            f'''  // W8_ASSERT:hidden.reducer-invalid.{label}
  {{auto invalid={task.function_name}(input, {arguments});if(!same_report(invalid,{task.reducer.report_name}{{}}))return {code};if(!same_input(input,before))return {code};}}
'''
        )
    return "".join(blocks), tuple(labels)


def _visible_test(task: TaskSpec) -> str:
    literal = task.transform.visible_input
    return f'''#include "{task.task_id}.h"
#include <cstddef>
{_same_input_function(task)}
int main(){{using namespace curriculum;std::vector<{_input_type(task)}> input{literal};auto before=input;{_transform_witness(task,literal)}/* W8_ASSERT:visible.valid-oracle */auto out={task.function_name}(input{_argument_values(task)});if(!({_assertion(task,literal)}))return 1;{_reducer_witness(task,"out",3)}/* W8_ASSERT:visible.input-immutability */return same_input(input,before)?0:2;}}
'''


def _hidden_test(task: TaskSpec) -> str:
    literal = task.transform.hidden_input
    invalids = _transform_invalid_mutations(task)
    invalid_blocks = "".join(
        _invalid_case(task, label, mutation, 20 + index)
        for index, (label, mutation) in enumerate(invalids)
    )
    limit_code = 20 + len(invalids)
    reducer_blocks, _ = _reducer_invalid_cases(task, limit_code + 2)
    boundary_literal = _touching_tie_literal(task)
    omission_literal = _valid_omission_literal(task)
    omission_block = ""
    if omission_literal is not None:
        omission_block = f'''  // W8_ASSERT:hidden.valid-empty-omission
  {{std::vector<{_input_type(task)}> omission{omission_literal};auto omission_before=omission;auto omission_out={task.function_name}(omission{_argument_values(task)});if(!({_assertion(task,omission_literal,variable="omission_out")}))return 10;if(!same_input(omission,omission_before))return 10;}}
'''
    return f'''#include "{task.task_id}.h"
#include <cstddef>
{_same_input_function(task)}{_same_report_function(task)}
int main(){{
  using namespace curriculum;
  std::vector<{_input_type(task)}> input{literal};auto before=input;
  {_transform_witness(task,literal)}
  // W8_ASSERT:hidden.valid-oracle
  auto out={task.function_name}(input{_argument_values(task)});if(!({_assertion(task,literal)}))return 1;
  {_reducer_witness(task,"out",5)}
  // W8_ASSERT:hidden.input-immutability
  if(!same_input(input,before))return 2;
  // W8_ASSERT:hidden.empty-input
  std::vector<{_input_type(task)}> empty;auto empty_before=empty;auto empty_out={task.function_name}(empty{_argument_values(task)});if(!({_assertion(task,"{}",variable="empty_out")}))return 3;if(!same_input(empty,empty_before))return 4;
  // W8_ASSERT:hidden.touching-and-tie-oracle
  std::vector<{_input_type(task)}> touching{boundary_literal};auto touching_before=touching;auto touching_out={task.function_name}(touching{_argument_values(task)});if(!({_assertion(task,boundary_literal,variable="touching_out")}))return 6;{_reducer_witness(task,"touching_out",7)}if(!same_input(touching,touching_before))return 8;
  // W8_ASSERT:hidden.valid-inclusive-maxima
  {{std::vector<{_input_type(task)}> boundary{{input.front()}};{_inclusive_maximum_mutation(task)}auto boundary_before=boundary;auto boundary_out={task.function_name}(boundary{_argument_values(task)});if(!boundary_out.valid)return 9;if(!same_input(boundary,boundary_before))return 9;}}
{omission_block}{invalid_blocks}  // W8_ASSERT:hidden.invalid.input-size-upper-bound
  {{std::vector<{_input_type(task)}> bad(1001,input.front());for(std::size_t index=0;index<bad.size();++index)bad[index].{_id_field(task)}=static_cast<int>(index)+1;auto bad_before=bad;auto invalid={task.function_name}(bad{_argument_values(task)});if(!same_report(invalid,{task.reducer.report_name}{{}}))return {limit_code};if(!same_input(bad,bad_before))return {limit_code};}}
  // W8_ASSERT:hidden.valid-input-size-1000
  {{std::vector<{_input_type(task)}> boundary(1000,input.front());for(std::size_t index=0;index<boundary.size();++index)boundary[index].{_id_field(task)}=static_cast<int>(index)+1;auto boundary_before=boundary;auto boundary_out={task.function_name}(boundary{_argument_values(task)});if(!boundary_out.valid)return {limit_code + 1};if(!same_input(boundary,boundary_before))return {limit_code + 1};}}
{reducer_blocks}  return 0;
}}
'''


def _example_block(task: TaskSpec) -> str:
    literal = task.transform.visible_input
    expected = _expected(task, literal)
    parts = []
    for clause in task.reducer.assertion.format(**expected).split("&&"):
        if clause == "out.valid":
            parts.append("`valid == true`")
        elif clause.startswith("out.") and "==" in clause:
            field, value = clause[4:].split("==", 1)
            parts.append(f"`{field} == {value}`")
        else:
            parts.append(f"`{clause}`")
    call = f"`{task.function_name}(input{_argument_values(task)})`"
    joined = ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1]
    return f"## Example\n\nFor `input == {literal}`, {call} returns a report with {joined}.\n"


def _capitalize(sentence: str) -> str:
    return sentence[:1].upper() + sentence[1:] if sentence else sentence


def _instructions(task: TaskSpec) -> str:
    return f'''# Instructions

Implement `{task.function_name}` in C++17. The function must {task.transform.objective},
then {task.reducer.objective}. The first stage uses {task.transform.mechanism}; the
second uses {task.reducer.mechanism}. The transformation and analysis are both part of
the required behavior; a solution that skips either stage is incorrect.

Inputs own no external state and are never mutated. Inputs contain at most 1,000 records;
IDs must be unique in 1..200,000,000, and loads/priorities/capacities must be in
1..1,000,000. Recurrence duration/period and precedence lag are at most 2,880.
{_capitalize(task.transform.boundary)}. {_capitalize(task.reducer.boundary)}. Invalid input returns the report's
default `valid=false` state without partial output. Empty input is valid after reducer
parameter validation: it produces the natural empty report (the longest-gap reducer
returns the complete requested horizon). All intervals are half-open, all ordering is
deterministic, and every arithmetic result must fit the declared type.

{_example_block(task)}
The editable files are `{task.task_id}.h` followed by `{task.task_id}.cpp`. Return a
complete replacement for both files and no other file.
'''


def _requirements(task: TaskSpec) -> dict[str, Any]:
    transform_labels = [
        f"hidden.invalid.{label}" for label, _ in _transform_invalid_mutations(task)
    ] + ["hidden.invalid.input-size-upper-bound"]
    _, reducer_labels = _reducer_invalid_cases(task, 0)
    requirements = [
        {
            "requirement_id": "input-immutability",
            "contract": "The const input sequence and every record remain byte-for-field unchanged.",
            "applicability": "required",
            "assertions": ["visible.input-immutability", "hidden.input-immutability"],
        },
        {
            "requirement_id": "empty-input",
            "contract": task.reducer.boundary,
            "applicability": "required",
            "assertions": ["hidden.empty-input"],
        },
        {
            "requirement_id": "identity-and-size-bounds",
            "contract": "At most 1,000 records with unique IDs in 1..200,000,000.",
            "applicability": "required",
            "assertions": [
                "hidden.invalid.id-zero",
                "hidden.invalid.id-upper-bound",
                "hidden.invalid.duplicate-id",
                "hidden.invalid.input-size-upper-bound",
                "hidden.valid-inclusive-maxima",
                "hidden.valid-input-size-1000",
            ],
        },
        {
            "requirement_id": "load-and-arithmetic-bounds",
            "contract": "Weights and intermediate arithmetic remain within declared bounds.",
            "applicability": "required",
            "assertions": [
                "hidden.invalid.weight-zero",
                "hidden.invalid.weight-upper-bound",
                "hidden.valid-inclusive-maxima",
                *[label for label in transform_labels if "arithmetic" in label or "horizon" in label],
            ],
        },
        {
            "requirement_id": "transform-validation-and-mechanism",
            "contract": f"{task.transform.objective}; {task.transform.boundary}.",
            "applicability": "required",
            "assertions": ["visible.valid-oracle", "hidden.valid-oracle", *transform_labels],
        },
        {
            "requirement_id": "transform-valid-empty-omission",
            "contract": "Valid empty clip/common intersections are omitted without invalidating the query.",
            "applicability": (
                "required"
                if _valid_omission_literal(task) is not None
                else "not_applicable_transform_has_no_omission_branch"
            ),
            "assertions": (
                ["hidden.valid-empty-omission"]
                if _valid_omission_literal(task) is not None
                else []
            ),
        },
        {
            "requirement_id": "reducer-parameter-validation",
            "contract": task.reducer.boundary,
            "applicability": "required" if reducer_labels else "not_applicable_no_parameters",
            "assertions": list(reducer_labels),
        },
        {
            "requirement_id": "half-open-and-deterministic-selection",
            "contract": "Half-open boundaries, earliest ties, and stable ordering follow the declared reducer policy.",
            "applicability": "required",
            "assertions": ["hidden.touching-and-tie-oracle"],
        },
        {
            "requirement_id": "atomic-invalid-report",
            "contract": "Every invalid query returns the complete default report without partial output.",
            "applicability": "required",
            "assertions": [*transform_labels, *reducer_labels],
        },
        {
            "requirement_id": "primary-two-stage-objective",
            "contract": f"{task.transform.mechanism} followed by {task.reducer.mechanism}.",
            "applicability": "required",
            "assertions": [
                "visible.valid-oracle",
                "hidden.valid-oracle",
                "docker.compiled-negative-normal",
                "docker.compiled-negative-asan-ubsan",
            ],
        },
    ]
    return {
        "schema_version": "aider-task-requirement-ledger-v1",
        "task_id": task.task_id,
        "contract_hash": _sha_bytes(_instructions(task).encode()),
        "requirements": requirements,
        "assertion_marker": "W8_ASSERT:<assertion-id>",
        "status": "generated_pending_execution",
    }


def _contract(task: TaskSpec) -> str:
    return f'''# {task.task_id} creation contract

## Identity

- New-root lineage: `{task.lineage_id}`
- Family: `{FAMILY_ID}`
- Clean-room source: `{CURRICULUM}`
- Benchmark relation: no parent; official Aider C++ roots remain holdouts.

## Public API

```cpp
{_header(task).strip()}
```

## Behavior

- Transformation: {task.transform.objective} using {task.transform.mechanism}.
- Analysis: {task.reducer.objective} using {task.reducer.mechanism}.
- Invalid/duplicate/empty/boundary behavior: {task.transform.boundary}; {task.reducer.boundary}.
- Input is borrowed by const reference; output owns all vectors.
- Ordering and ties follow the analysis contract; half-open endpoints never overlap when touching.

## Core objective and forbidden substitutes

The reference must contain both emitted mechanisms. A no-wrap/no-offset projection,
untransformed interval analysis, transform-only answer, reducer-only answer, closed-end
comparison, or renamed/policy-only clone is forbidden. The compiled negative mutates
one transformation decision and one analysis decision and must be rejected.

## Tests and oracle

Visible and private deterministic examples are independent hard-coded results. The
private case also proves duplicate rejection without mutation. Normal and fresh
ASan/UBSan runs must discover the same two positive CTests; the false substitute must
compile and fail at least one test in both modes.

## Files, provenance, and handoff

The prompt exposes only instructions plus `{task.task_id}.h` and `{task.task_id}.cpp`.
References, tests, CMake, provenance, receipts, and this contract are private. Dataset
handoff is `not_requested`.
'''


def _config(task: TaskSpec) -> dict[str, Any]:
    return {
        "authors": ["w8-biayn"],
        "blurb": f"{task.transform.mechanism} followed by {task.reducer.mechanism}.",
        "files": {
            "solution": [f"{task.task_id}.h", f"{task.task_id}.cpp"],
            "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
        "source": "Clean-room w8-biayn count-plan expansion",
    }


def _provenance(task: TaskSpec) -> dict[str, Any]:
    return {
        "schema_version": "aider-local-task-provenance-v1",
        "task_id": task.task_id,
        "lineage_id": task.lineage_id,
        "relation": "new-root",
        "family_id": FAMILY_ID,
        "capability": "cross-midnight-fixed-offset-meeting-interval-intersections",
        "curriculum": CURRICULUM.as_posix(),
        "count_plan": "docs/GLM47_FLASH_AIDER_POLYGLOT_CPP_2500_TASK_COUNT_PLAN.md",
        "authoring_origin": "deterministic clean-room repository generator",
        "license": "repository-local clean-room material",
        "selected_prompt": SELECTED_PROMPT.as_posix(),
        "implementation_prompt": IMPLEMENT_PROMPT.as_posix(),
        "status": "candidate_pending_independent_audit",
        "dataset_handoff": "not_requested",
    }


def _materialize_task(out: Path, task: TaskSpec, force: bool) -> Path:
    root = out / task.task_id
    if root.exists():
        if not force:
            raise FileExistsError(f"{root} exists; use --force")
        if not _owned_root(root):
            _fail("generator_output_drift", f"foreign root: {root}")
        shutil.rmtree(root)
    reference = _reference(task)
    files = {
        ".docs/instructions.md": _instructions(task),
        ".meta/config.json": json.dumps(_config(task), indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(_provenance(task), indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": "[visible]\nname = \"contract example\"\n[hidden]\nname = \"boundary, duplicate, and negative discriminator\"\n",
        ".meta/requirements.json": json.dumps(_requirements(task), indent=2, sort_keys=True) + "\n",
        ".meta/example.h": _header(task),
        ".meta/example.cpp": reference,
        ".meta/negative.cpp": _negative(task, reference),
        ".meta/task_hidden_test.cpp": _hidden_test(task),
        f"{task.task_id}.h": _header(task),
        f"{task.task_id}.cpp": _starter(task),
        "task_visible_test.cpp": _visible_test(task),
        "CMakeLists.txt": CMAKE.replace("TASK_CPP", f"{task.task_id}.cpp"),
    }
    for relative, content in files.items():
        _write(root / relative, content)
    return root


def _write_creation_contracts(out: Path) -> None:
    for task in TASKS:
        _write(out / ".state/contracts" / f"{task.task_id}.md", _contract(task))


def _write_candidate_manifests(out: Path) -> None:
    rows = [
        {
            "task_id": task.task_id,
            "lineage_id": task.lineage_id,
            "transform": task.transform.key,
            "reducer": task.reducer.key,
            "contract_path": (out / ".state/contracts" / f"{task.task_id}.md").as_posix(),
            "contract_hash": _sha_file(out / ".state/contracts" / f"{task.task_id}.md"),
            "disposition": "selected",
        }
        for task in TASKS
    ]
    _write(
        out / ".state/candidates/raw-proposals.json",
        json.dumps({"schema_version": "aider-creation-proposals-v1", "count": 90, "proposals": rows}, indent=2, sort_keys=True) + "\n",
    )
    _write(
        out / ".state/candidates/selected.json",
        json.dumps({"schema_version": "aider-selected-candidates-v1", "count": 90, "tasks": rows}, indent=2, sort_keys=True) + "\n",
    )
    _write(
        out / ".state/candidates/rejected.json",
        json.dumps({"schema_version": "aider-rejected-candidates-v1", "count": 0, "tasks": []}, indent=2, sort_keys=True) + "\n",
    )


def _copy_control(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)


def _replace_all(root: Path, replacements: Sequence[tuple[str, str]]) -> None:
    changed = False
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        revised = text
        for old, new in replacements:
            revised = revised.replace(old, new)
        if revised != text:
            path.write_text(revised, encoding="utf-8")
            changed = True
    if not changed:
        _fail("adversarial_control_invalid", root.name)


def _materialize_controls(out: Path) -> None:
    controls = out / ".state/hard-rule-controls"
    controls.mkdir(parents=True, exist_ok=True)
    domain = controls / CONTROL_NAMES[0]
    _copy_control(out / "overnight-merged-coverage", domain)
    _replace_all(
        domain,
        (("Overnight", "Voyage"), ("analyze_wrap_union", "audit_voyage_union")),
    )
    for relative in (".docs/instructions.md", ".meta/provenance.json"):
        path = domain / relative
        path.write_text(path.read_text(encoding="utf-8").replace("overnight", "voyage"), encoding="utf-8")
    constants = controls / CONTROL_NAMES[1]
    _copy_control(out / "fixed-offset-merged-coverage", constants)
    _replace_all(
        constants,
        (("-841", "-901"), ("841", "901"), ("840", "900")),
    )
    opposite = controls / CONTROL_NAMES[2]
    source_task = next(task for task in TASKS if task.task_id == "overnight-stable-order")
    _copy_control(out / source_task.task_id, opposite)
    _replace_all(
        opposite,
        (("a.start<b.start", "a.start>b.start"),),
    )
    # Replace the exact ascending vector literals with independently computed
    # descending-start results so the control remains behaviorally coherent.
    for literal, relative in (
        (source_task.transform.visible_input, "task_visible_test.cpp"),
        (source_task.transform.hidden_input, ".meta/task_hidden_test.cpp"),
        (_touching_tie_literal(source_task), ".meta/task_hidden_test.cpp"),
    ):
        _, spans = _transform_rows("wrap", _parse_rows(literal))
        ascending = _reduce("order", spans, ())["vector"]
        descending = _cpp_vector([row[0] for row in sorted(spans, key=lambda row: (-row[1], row[2], row[0]))])
        path = opposite / relative
        text = path.read_text(encoding="utf-8")
        if ascending not in text:
            _fail("adversarial_control_invalid", f"missing order oracle: {relative}")
        path.write_text(text.replace(ascending, descending), encoding="utf-8")
    docs = opposite / ".docs/instructions.md"
    docs.write_text(
        docs.read_text(encoding="utf-8").replace(
            "ordered by start, then end, then identity",
            "ordered by descending start, then end, then identity",
        ),
        encoding="utf-8",
    )


def _archive_prior_cycle(out: Path, cycle_number: int) -> None:
    if cycle_number <= 1 or not out.is_dir():
        return
    prior = cycle_number - 1
    cycle_dir = out / ".state/cycles"
    for name in (
        "manifest.json",
        "source-inventory.json",
        "family-screen.json",
        "docker-sanity.json",
        "creator-preflight.json",
    ):
        source = out / ".state" / name
        target = cycle_dir / f"cycle-{prior:02d}-{name}"
        if source.is_file() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)


def build(
    out: Path = DEFAULT_OUT, force: bool = False, cycle_number: int = 1
) -> tuple[Path, ...]:
    _validate_out(out)
    if cycle_number < 1:
        _fail("invalid_cycle", str(cycle_number))
    _archive_prior_cycle(out, cycle_number)
    read_artifacts.cache_clear()
    analyze_root.cache_clear()
    inventory = _inventory_existing(out)
    out.mkdir(parents=True, exist_ok=True)
    if force:
        selected = {task.task_id for task in TASKS}
        for child in out.iterdir():
            if child.name == ".state" or not child.is_dir() or child.name in selected:
                continue
            if _owned_root(child):
                shutil.rmtree(child)
            else:
                _fail("generator_output_drift", f"foreign obsolete root: {child}")
    _write_creation_contracts(out)
    _write_candidate_manifests(out)
    roots = tuple(_materialize_task(out, task, force) for task in TASKS)
    _materialize_controls(out)
    inventory_payload = {
        "schema_version": "aider-expansion-source-inventory-v1",
        "legacy_real_roots": len(_inventory_configs(LEGACY_ROOT)),
        "reverify_real_roots": len(_inventory_configs(REVERIFY_ROOT)),
        "reverify_sorted_root_sha256": inventory["reverify_sorted_root_sha256"],
        "count_plan_reverify_sorted_root_sha256": PLAN_REVERIFY_ROOTS_SHA256,
        "expansion_roots_before": inventory["expansion_roots_before"],
        "owner_expansion_roots_before": inventory["owner_expansion_roots_before"],
        "foreign_expansion_roots_before": inventory["foreign_expansion_roots_before"],
        "reserved_task_id_count": len(inventory["reserved_task_ids"]),
        "reserved_task_ids_hash": _sha_bytes("\n".join(inventory["reserved_task_ids"]).encode()),
        "source_roots": inventory["roots"],
    }
    _write(out / ".state/source-inventory.json", json.dumps(inventory_payload, indent=2, sort_keys=True) + "\n")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "family_id": FAMILY_ID,
        "status": "generated_pending_creator_preflight",
        "root_count": len(roots),
        "task_ids": [task.task_id for task in TASKS],
        "family_hash": _family_hash(out),
        "owner_hashes": _owner_hashes(),
        "roots": {root.name: _tree_hash(root) for root in roots},
    }
    _write(out / ".state/manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return roots


def _validate_structure(out: Path) -> dict[str, Any]:
    prompt_hashes: set[str] = set()
    reference_hashes: set[str] = set()
    roots: dict[str, Any] = {}
    for task in TASKS:
        root = out / task.task_id
        if not root.is_dir():
            _fail("generator_output_drift", task.task_id)
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        expected_solution = [f"{task.task_id}.h", f"{task.task_id}.cpp"]
        if config.get("files", {}).get("solution") != expected_solution:
            _fail("unsafe_path", task.task_id)
        if config["files"].get("example") != [".meta/example.h", ".meta/example.cpp"]:
            _fail("target_reference_mismatch", task.task_id)
        task_model = load_task(root)
        prompt = build_prompt(task_model)
        for forbidden in (".meta/", "CMakeLists.txt", "task_hidden_test", "negative.cpp", "provenance"):
            if forbidden in prompt:
                _fail("prompt_contract_incomplete", f"{task.task_id}: {forbidden}")
        answer = build_assistant_response(task_model, load_example_files_from_config(root))
        if not answer.startswith(f"{task.task_id}.h\n```") or f"{task.task_id}.cpp\n```" not in answer:
            _fail("whole_format_failed", task.task_id)
        prompt_hash = _sha_bytes(prompt.encode())
        reference_hash = _sha_bytes(answer.encode())
        if prompt_hash in prompt_hashes:
            _fail("duplicate_prompt", task.task_id)
        if reference_hash in reference_hashes:
            _fail("duplicate_reference", task.task_id)
        prompt_hashes.add(prompt_hash)
        reference_hashes.add(reference_hash)
        negative = (root / ".meta/negative.cpp").read_text(encoding="utf-8")
        reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
        if negative == reference:
            _fail("invariant_not_enforced", task.task_id)
        ledger = json.loads((root / ".meta/requirements.json").read_text(encoding="utf-8"))
        if ledger.get("contract_hash") != _sha_bytes(_instructions(task).encode()):
            _fail("requirement_ledger_stale", task.task_id)
        visible_test = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
        hidden_test = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
        assertion_ids: set[str] = set()
        for requirement in ledger.get("requirements", []):
            applicability = requirement.get("applicability")
            assertions = requirement.get("assertions", [])
            if applicability == "required" and not assertions:
                _fail("requirement_without_assertion", f"{task.task_id}: {requirement.get('requirement_id')}")
            for assertion_id in assertions:
                if assertion_id.startswith("docker."):
                    assertion_ids.add(assertion_id)
                    continue
                marker = f"W8_ASSERT:{assertion_id}"
                if marker not in visible_test and marker not in hidden_test:
                    _fail("requirement_assertion_missing", f"{task.task_id}: {assertion_id}")
                assertion_ids.add(assertion_id)
        if "hidden.empty-input" not in assertion_ids or "hidden.input-immutability" not in assertion_ids:
            _fail("requirement_assertion_missing", task.task_id)
        roots[task.task_id] = {
            "tree_hash": _tree_hash(root),
            "prompt_hash": prompt_hash,
            "reference_hash": reference_hash,
            "starter_hash": _sha_bytes(
                ((root / f"{task.task_id}.h").read_text() + (root / f"{task.task_id}.cpp").read_text()).encode()
            ),
            "tests_hash": _sha_bytes(
                ((root / "task_visible_test.cpp").read_text() + (root / ".meta/task_hidden_test.cpp").read_text()).encode()
            ),
            "requirement_ledger_hash": _sha_file(root / ".meta/requirements.json"),
            "requirement_assertion_count": len(assertion_ids),
            "primary_core_objective": "achieved",
        }
    return {"status": "pass", "roots": roots}


def _family_screen(out: Path) -> dict[str, Any]:
    pairs = []
    failed = []
    for left, right in itertools.combinations((out / task.task_id for task in TASKS), 2):
        comparison = compare_roots(left, right)
        pairs.append(comparison)
        if not comparison["pass"]:
            failed.append((left.name, right.name))
    if failed:
        _fail("duplicate_family", f"{len(failed)} failed pairs; first={failed[:3]}")
    evidence = {task.task_id: analyze_root(out / task.task_id) for task in TASKS}
    return {
        "status": "pass",
        "normalizer": NORMALIZER,
        "root_count": len(TASKS),
        "pair_count": len(pairs),
        "expected_pair_count": len(TASKS) * (len(TASKS) - 1) // 2,
        "dimensions": list(HARD_DIMENSIONS),
        "thresholds": MAX_NORMALIZED_SIMILARITY,
        "artifact_evidence": evidence,
        "pairs": pairs,
    }


def _control_screen(out: Path) -> dict[str, Any]:
    controls = out / ".state/hard-rule-controls"
    comparisons = (
        ("domain-identifier-renamed-clone", out / "overnight-merged-coverage"),
        ("constants-policy-only-clone", out / "fixed-offset-merged-coverage"),
        ("opposite-end-selection-clone", out / "overnight-stable-order"),
    )
    rows = []
    for name, base in comparisons:
        control = controls / name
        comparison = compare_roots(base, control)
        changed = _tree_hash(base) != _tree_hash(control)
        rejected = not comparison["pass"]
        if not changed or not rejected:
            _fail("adversarial_control_invalid", name)
        rows.append(
            {
                "name": name,
                "base": base.name,
                "changed": changed,
                "rejected": rejected,
                "control_tree_hash": _tree_hash(control),
                "comparison": comparison,
            }
        )
    return {"status": "pass", "controls": rows}


def _benchmark_and_lineage_screen(out: Path) -> dict[str, Any]:
    benchmark = json.loads(BENCHMARK_MANIFEST.read_text(encoding="utf-8"))
    holdout_ids = set(benchmark["task_ids"])
    task_ids = {task.task_id for task in TASKS}
    if task_ids & holdout_ids:
        _fail("benchmark_id_overlap", ", ".join(sorted(task_ids & holdout_ids)))
    inventory = json.loads((out / ".state/source-inventory.json").read_text(encoding="utf-8"))
    existing = inventory["source_roots"]
    rows = []
    for task in TASKS:
        root = out / task.task_id
        content = _normalize_contract(
            (root / ".docs/instructions.md").read_text(encoding="utf-8")
            + "\n"
            + (root / f"{task.task_id}.h").read_text(encoding="utf-8")
        )
        best = {"similarity": 0.0, "path": None, "task_id": None}
        for item in existing:
            similarity = _contract_similarity(content, item["normalized_contract"])
            if similarity > best["similarity"]:
                best = {"similarity": similarity, "path": item["path"], "task_id": item["task_id"]}
        if best["similarity"] >= 0.82:
            _fail("duplicate_family", f"{task.task_id} near {best}")
        rows.append({"task_id": task.task_id, "closest_existing": best})
    if not HOLDOUT_ROOT.is_dir():
        _fail("benchmark_content_screen_unavailable", HOLDOUT_ROOT.as_posix())
    holdout_rows = []
    for task in TASKS:
        root = out / task.task_id
        content = _normalize_contract(
            (root / ".docs/instructions.md").read_text(encoding="utf-8")
            + "\n"
            + (root / f"{task.task_id}.h").read_text(encoding="utf-8")
        )
        best = {"similarity": 0.0, "task_id": None}
        for holdout_id in sorted(holdout_ids):
            holdout = HOLDOUT_ROOT / holdout_id
            if not holdout.is_dir():
                _fail("benchmark_content_screen_unavailable", holdout_id)
            holdout_content = "\n".join(
                path.read_text(encoding="utf-8", errors="replace")
                for path in sorted(holdout.rglob("*"))
                if path.is_file() and path.suffix in {".md", ".h", ".hpp", ".cpp"}
            )
            similarity = _contract_similarity(content, _normalize_contract(holdout_content))
            if similarity > best["similarity"]:
                best = {"similarity": similarity, "task_id": holdout_id}
        if best["similarity"] >= 0.72:
            _fail("benchmark_content_overlap", f"{task.task_id} near {best}")
        holdout_rows.append({"task_id": task.task_id, "closest_holdout": best})
    return {
        "status": "pass",
        "holdout_revision": benchmark["revision"],
        "holdout_count": len(holdout_ids),
        "existing_comparisons": len(TASKS) * len(existing),
        "holdout_comparisons": len(TASKS) * len(holdout_ids),
        "existing_rows": rows,
        "holdout_rows": holdout_rows,
    }


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, Any]:
    _validate_out(out)
    structure = _validate_structure(out)
    family = _family_screen(out)
    controls = _control_screen(out)
    contamination = _benchmark_and_lineage_screen(out)
    screen = {
        "schema_version": "aider-expansion-time-family-screen-v1",
        "status": "pass",
        "family_hash": _family_hash(out),
        "owner_revision": _owner_revision(),
        "structure": structure,
        "hard_rule": family,
        "adversarial_controls": controls,
        "benchmark_and_lineage": contamination,
    }
    _write(out / ".state/family-screen.json", json.dumps(screen, indent=2, sort_keys=True) + "\n")
    return screen


def _write_archive(out: Path, archive: Path) -> str:
    with tarfile.open(archive, "w") as handle:
        for path in sorted(item for item in out.rglob("*") if item.is_file()):
            info = handle.gettarinfo(path, arcname=(Path("family") / path.relative_to(out)).as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            with path.open("rb") as source:
                handle.addfile(info, source)
    return _sha_file(archive)


def docker_sanity(out: Path = DEFAULT_OUT, cycle_number: int = 1) -> dict[str, Any]:
    screen = verify_core(out)
    with tempfile.TemporaryDirectory(prefix="w8-time-family-") as temporary:
        archive = Path(temporary) / "family.tar"
        archive_hash = _write_archive(out, archive)
        image_id = subprocess.run(
            ["docker", "image", "inspect", SANITY_IMAGE, "--format", "{{.Id}}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if image_id != SANITY_IMAGE_ID:
            _fail("docker_sanity_receipt_invalid", f"unexpected image {image_id}")
        process = subprocess.run(
            [
                "docker", "run", "--rm", "--network", "none",
                "-v", f"{archive}:/input/family.tar:ro", SANITY_IMAGE,
                "sh", "-lc", DOCKER_SCRIPT,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if process.returncode != 0:
            failure_dir = out / ".state/docker-sanity-failures"
            attempt = len(tuple(failure_dir.glob("attempt-*.json"))) + 1 if failure_dir.is_dir() else 1
            failure = {
                "schema_version": "aider-expansion-time-docker-failure-v1",
                "status": "fail",
                "attempt": attempt,
                "family_hash": _family_hash(out),
                "owner_revision": _owner_revision(),
                "archive_hash": archive_hash,
                "image": SANITY_IMAGE,
                "image_id": image_id,
                "network": "none",
                "returncode": process.returncode,
                "bounded_log_tail": (process.stdout + "\n" + process.stderr)[-20000:],
            }
            _write(
                failure_dir / f"attempt-{attempt:02d}.json",
                json.dumps(failure, indent=2, sort_keys=True) + "\n",
            )
            _fail("docker_sanity_failed", failure["bounded_log_tail"])
    counts: dict[tuple[str, str], dict[str, int]] = {}
    for category, item, mode, count in re.findall(
        r"^W8COUNT (tasks|controls) (\S+) (normal|asan_ubsan) (\d+)$",
        process.stdout,
        flags=re.M,
    ):
        counts.setdefault((category, item), {})[mode] = int(count)
    mounted = {
        (category, item): digest
        for category, item, digest in re.findall(
            r"^W8HASH (tasks|controls) (\S+) (sha256:[0-9a-f]{64})$",
            process.stdout,
            flags=re.M,
        )
    }
    negatives = {
        (category, item, mode)
        for category, item, mode in re.findall(
            r"^W8NEG (tasks|controls) (\S+) (normal|asan_ubsan) rejected$",
            process.stdout,
            flags=re.M,
        )
    }
    task_receipts: dict[str, Any] = {}
    for task in TASKS:
        key = ("tasks", task.task_id)
        if counts.get(key) != {"normal": 2, "asan_ubsan": 2}:
            _fail("sanitizer_test_count_mismatch", task.task_id)
        if key + ("normal",) not in negatives or key + ("asan_ubsan",) not in negatives:
            _fail("invariant_not_enforced", task.task_id)
        live_hash = _tree_hash(out / task.task_id)
        if mounted.get(key) != live_hash:
            _fail("grader_mount_hash_mismatch", task.task_id)
        task_receipts[task.task_id] = {
            "tree_hash": live_hash,
            "mounted_tree_hash": mounted[key],
            "normal": 2,
            "asan_ubsan": 2,
            "negative_normal": True,
            "negative_asan_ubsan": True,
        }
    control_receipts: dict[str, Any] = {}
    for name in CONTROL_NAMES:
        key = ("controls", name)
        if counts.get(key) != {"normal": 2, "asan_ubsan": 2}:
            _fail("sanitizer_test_count_mismatch", name)
        live_hash = _tree_hash(out / ".state/hard-rule-controls" / name)
        if mounted.get(key) != live_hash:
            _fail("grader_mount_hash_mismatch", name)
        control_receipts[name] = {
            "tree_hash": live_hash,
            "mounted_tree_hash": mounted[key],
            "normal": 2,
            "asan_ubsan": 2,
        }
    toolchain = dict(re.findall(r"^W8TOOL (\S+) (.+)$", process.stdout, flags=re.M))
    receipt = {
        "schema_version": "aider-expansion-time-docker-sanity-v1",
        "status": "pass",
        "cycle": cycle_number,
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "network": "none",
        "image": SANITY_IMAGE,
        "image_id": SANITY_IMAGE_ID,
        "archive_hash": archive_hash,
        "family_hash": _family_hash(out),
        "owner_revision": _owner_revision(),
        "family_screen_hash": _sha_file(out / ".state/family-screen.json"),
        "toolchain": toolchain,
        "commands": [
            "archive-mounted network-disabled normal CMake/CTest",
            "normal compiled false-substitute execution",
            "fresh ASan/UBSan CMake/CTest",
            "ASan/UBSan compiled false-substitute execution",
        ],
        "tasks": task_receipts,
        "controls": control_receipts,
    }
    receipt_text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    _write(out / ".state/docker-sanity.json", receipt_text)
    _write(
        out / f".state/cycles/cycle-{cycle_number:02d}-docker-sanity.json",
        receipt_text,
        force=False,
    )
    preflight = {
        "schema_version": "aider-creator-preflight-v1",
        "status": "pass",
        "cycle": cycle_number,
        "terminal_candidate_status": "creator_preflight_passed_pending_independent_audit",
        "requested_roots": 90,
        "retained_roots": 90,
        "family_hash": receipt["family_hash"],
        "owner_revision": receipt["owner_revision"],
        "family_screen_hash": receipt["family_screen_hash"],
        "docker_sanity_hash": _sha_file(out / ".state/docker-sanity.json"),
        "normal_test_count": 180,
        "asan_ubsan_test_count": 180,
        "negative_normal_count": 90,
        "negative_asan_ubsan_count": 90,
        "control_normal_test_count": 6,
        "control_asan_ubsan_test_count": 6,
        "prompt_boundary": "pass",
        "family_diversity": "pass",
        "benchmark_contamination": "pass",
        "source_lineage": "pass",
        "dataset_handoff": "not_requested",
    }
    preflight_text = json.dumps(preflight, indent=2, sort_keys=True) + "\n"
    _write(out / ".state/creator-preflight.json", preflight_text)
    _write(
        out / f".state/cycles/cycle-{cycle_number:02d}-creator-preflight.json",
        preflight_text,
        force=False,
    )
    cycle = {
        "schema_version": "aider-creation-cycle-v1",
        "cycle": cycle_number,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "state": "auditing",
        "family_id": FAMILY_ID,
        "candidate_manifest": (out / ".state/candidates/selected.json").as_posix(),
        "curriculum_hash": _sha_file(CURRICULUM),
        "family_spec_hash": _sha_file(FAMILY_SPEC),
        "owner_hashes": _owner_hashes(),
        "generated_tree_hash": _family_hash(out),
        "grader_policy_hash": _sha_bytes(DOCKER_SCRIPT.encode()),
        "creator_preflight_hash": _sha_file(out / ".state/creator-preflight.json"),
        "audit_subject_hash": audit_subject_hash(out),
        "audit_report_path": None,
        "finding_ids": [],
        "retained": [task.task_id for task in TASKS],
        "replaced": [],
        "rejected": [],
        "review": [],
        "blocked": [],
        "terminal_status": "pending_independent_audit",
    }
    _write(
        out / f".state/cycles/cycle-{cycle_number:02d}.json",
        json.dumps(cycle, indent=2, sort_keys=True) + "\n",
        force=False,
    )
    return {"screen": screen, "receipt": receipt, "preflight": preflight}


def _host_tool(tool: str) -> str:
    resolved = shutil.which(tool)
    if resolved is None:
        _fail("host_toolchain_unavailable", f"missing host tool: {tool}")
    return resolved


def _host_build_and_run(
    root: Path, build_parent: Path, category: str, mode: str, compiler: str
) -> dict[str, Any]:
    flags = ""
    if mode == "asan_ubsan":
        flags = "-fsanitize=address,undefined -fno-omit-frame-pointer"
    build = build_parent / f"{category}-{root.name}-{mode}"
    env = dict(os.environ)
    env["ASAN_OPTIONS"] = "detect_leaks=0"

    def run(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command, check=False, capture_output=True, text=True, env=env
        )

    steps = [
        run(
            [
                _host_tool("cmake"), "-S", str(root), "-B", str(build),
                "-G", "Unix Makefiles", f"-DCMAKE_CXX_COMPILER={compiler}",
                f"-DTASK_SOURCE={root}/.meta/example.cpp",
                f"-DNEGATIVE_SOURCE={root}/.meta/negative.cpp",
                f"-DCMAKE_CXX_FLAGS={flags}", f"-DCMAKE_EXE_LINKER_FLAGS={flags}",
            ]
        ),
        run([_host_tool("cmake"), "--build", str(build), "--parallel", "4"]),
    ]
    for process in steps:
        if process.returncode != 0:
            return {
                "ok": False,
                "log": (process.stdout + "\n" + process.stderr)[-8000:],
            }
    count_match = re.search(
        r"Total Tests:\s*(\d+)",
        run([_host_tool("ctest"), "--test-dir", str(build), "-N"]).stdout,
    )
    count = int(count_match.group(1)) if count_match else 0
    if count != 2:
        return {"ok": False, "log": f"expected 2 CTests, discovered {count}"}
    executed = run([_host_tool("ctest"), "--test-dir", str(build), "--output-on-failure"])
    if executed.returncode != 0:
        return {
            "ok": False,
            "log": (executed.stdout + "\n" + executed.stderr)[-8000:],
        }
    result: dict[str, Any] = {"ok": True, "count": count}
    if category == "tasks":
        visible = run([str(build / "negative_visible")])
        hidden = run([str(build / "negative_hidden")])
        if visible.returncode == 0 and hidden.returncode == 0:
            return {
                "ok": False,
                "log": "false substitute unexpectedly passed visible and hidden tests",
            }
        result["negative_rejected"] = True
    return result


def verify_host(out: Path = DEFAULT_OUT, cycle_number: int = 1) -> dict[str, Any]:
    """Host normal + fresh ASan/UBSan reference verification (no Docker).

    Mirrors the docker_sanity semantics on the host toolchain: a clean normal
    CMake/CTest build and a separate fresh ASan/UBSan build per root and per
    hard-rule control, positive equal discovery counts, and compiled
    false-substitute rejection for every task root in both modes. This is
    `host_verify` evidence, not `docker_sanity` or `locked_oracle` evidence.
    """
    screen = verify_core(out)
    cmake = _host_tool("cmake")
    compiler = _host_tool("c++")
    _host_tool("ctest")
    toolchain = {
        "cmake_path": cmake,
        "cmake_version": subprocess.run(
            [cmake, "--version"], check=True, capture_output=True, text=True
        ).stdout.splitlines()[0],
        "compiler_path": compiler,
        "compiler_hash": _sha_file(Path(compiler)),
        "compiler_version": subprocess.run(
            [compiler, "--version"], check=True, capture_output=True, text=True
        ).stdout.splitlines()[0],
        "network": "not_applicable_host_processes",
    }
    roots: list[tuple[str, Path]] = [("tasks", out / task.task_id) for task in TASKS]
    roots += [
        ("controls", out / ".state/hard-rule-controls" / name)
        for name in CONTROL_NAMES
    ]
    failures: list[dict[str, str]] = []
    counts: dict[tuple[str, str], dict[str, int]] = {}
    negatives: set[tuple[str, str, str]] = set()
    with tempfile.TemporaryDirectory(prefix="w8-time-host-verify-") as temporary:
        build_parent = Path(temporary)
        jobs = [
            (category, root, mode)
            for category, root in roots
            for mode in ("normal", "asan_ubsan")
        ]
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = {
                (category, root.name, mode): outcome
                for (category, root, mode), outcome in zip(
                    jobs,
                    pool.map(
                        lambda job: _host_build_and_run(
                            job[1], build_parent, job[0], job[2], compiler
                        ),
                        jobs,
                    ),
                    strict=True,
                )
            }
    for category, root in roots:
        for mode in ("normal", "asan_ubsan"):
            outcome = results[(category, root.name, mode)]
            if not outcome["ok"]:
                failures.append(
                    {"root": root.name, "category": category, "mode": mode,
                     "log": outcome["log"]}
                )
                continue
            counts.setdefault((category, root.name), {})[mode] = outcome["count"]
            if outcome.get("negative_rejected"):
                negatives.add((category, root.name, mode))
    if failures:
        failure_dir = out / ".state/host-verify-failures"
        attempt = (
            len(tuple(failure_dir.glob("attempt-*.json"))) + 1
            if failure_dir.is_dir()
            else 1
        )
        failure = {
            "schema_version": "aider-expansion-time-host-verify-failure-v1",
            "status": "fail",
            "attempt": attempt,
            "family_hash": _family_hash(out),
            "owner_revision": _owner_revision(),
            "toolchain": toolchain,
            "failures": failures[:20],
            "failure_count": len(failures),
        }
        _write(
            failure_dir / f"attempt-{attempt:02d}.json",
            json.dumps(failure, indent=2, sort_keys=True) + "\n",
        )
        _fail("host_verify_failed", json.dumps(failures[:3]))
    task_receipts: dict[str, Any] = {}
    for task in TASKS:
        key = ("tasks", task.task_id)
        if counts.get(key) != {"normal": 2, "asan_ubsan": 2}:
            _fail("sanitizer_test_count_mismatch", task.task_id)
        if key + ("normal",) not in negatives or key + ("asan_ubsan",) not in negatives:
            _fail("invariant_not_enforced", task.task_id)
        task_receipts[task.task_id] = {
            "tree_hash": _tree_hash(out / task.task_id),
            "normal": 2,
            "asan_ubsan": 2,
            "negative_normal": True,
            "negative_asan_ubsan": True,
        }
    control_receipts: dict[str, Any] = {}
    for name in CONTROL_NAMES:
        key = ("controls", name)
        if counts.get(key) != {"normal": 2, "asan_ubsan": 2}:
            _fail("sanitizer_test_count_mismatch", name)
        control_receipts[name] = {
            "tree_hash": _tree_hash(out / ".state/hard-rule-controls" / name),
            "normal": 2,
            "asan_ubsan": 2,
        }
    receipt = {
        "schema_version": "aider-expansion-time-host-verify-v1",
        "status": "pass",
        "cycle": cycle_number,
        "evidence_class": "host_verify",
        "locked_oracle": False,
        "docker_sanity": "not_completed (campaign gate: host verify only)",
        "family_hash": _family_hash(out),
        "owner_revision": _owner_revision(),
        "family_screen_hash": _sha_file(out / ".state/family-screen.json"),
        "toolchain": toolchain,
        "commands": [
            "host clean normal CMake/CTest reference build and run",
            "host normal compiled false-substitute execution",
            "host fresh ASan/UBSan CMake/CTest reference build and run",
            "host ASan/UBSan compiled false-substitute execution",
        ],
        "tasks": task_receipts,
        "controls": control_receipts,
    }
    receipt_text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    _write(out / ".state/host-verify.json", receipt_text)
    _write(
        out / f".state/cycles/cycle-{cycle_number:02d}-host-verify.json",
        receipt_text,
        force=False,
    )
    return {"screen": screen, "receipt": receipt}


def plan_remediation(out: Path, audit_report: Path) -> Path:
    """Freeze an audit finding plan before any generator source is edited."""
    _validate_out(out)
    if not audit_report.is_file():
        _fail("audit_report_missing", audit_report.as_posix())
    report = json.loads(audit_report.read_text(encoding="utf-8"))
    cycle_number = int(report.get("cycle", 1))
    findings = report.get("findings", [])
    finding_ids = [
        str(item.get("finding_id") or item.get("id"))
        for item in findings
        if item.get("finding_id") or item.get("id")
    ]
    if not finding_ids:
        _fail("remediation_without_finding", audit_report.as_posix())
    record = {
        "schema_version": "aider-family-remedy-plan-v1",
        "status": "planned_before_source_edit",
        "family_id": FAMILY_ID,
        "cycle": cycle_number,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "audit_report_path": audit_report.as_posix(),
        "audit_report_hash": _sha_file(audit_report),
        "audit_subject_hash": audit_subject_hash(out),
        "finding_ids": finding_ids,
        "pre_edit_owner_hashes": _owner_hashes(),
        "pre_edit_family_hash": _family_hash(out),
        "invariant_to_restore": "Every audit finding must be fixed by the deterministic owner, regenerated, and freshly re-audited.",
        "allowed_patch_sites": [path.as_posix() for path in OWNER_PATHS.values()] + [
            CURRICULUM.as_posix(),
            FAMILY_SPEC.as_posix(),
            "tests/test_moonlight_cross_midnight_offsets_meetings_aider_tasks.py",
        ],
        "minimal_counterexample": "See the immutable finding records in the bound audit report.",
        "regression_tests": [
            "focused family pytest",
            "all-pairs seven-dimension screen",
            "three adversarial clone controls",
            "pinned network-disabled normal and fresh ASan/UBSan Docker sanity",
        ],
        "expected_regenerated_evidence": [
            ".state/manifest.json",
            ".state/family-screen.json",
            ".state/docker-sanity.json",
            ".state/creator-preflight.json",
            f".state/cycles/cycle-{cycle_number + 1:02d}.json",
            f".state/audits/cycle-{cycle_number + 1:02d}/audit-report.json",
        ],
        "stale_evidence_policy": "Cycle-01 evidence remains immutable history and cannot verify regenerated bytes.",
        "out_of_scope": [
            "SFT JSONL projection",
            "dataset release",
            "training authorization",
            "benchmark score or uplift",
        ],
    }
    target = out / f".state/remedy/cycle-{cycle_number:02d}-family.json"
    _write(target, json.dumps(record, indent=2, sort_keys=True) + "\n", force=False)
    markdown = f"""# Cross-midnight family remediation plan

## Finding IDs
{chr(10).join(f'- `{item}`' for item in finding_ids)}

## Pre-edit evidence
- Audit report: `{audit_report}`
- Audit hash: `{record['audit_report_hash']}`
- Audit subject: `{record['audit_subject_hash']}`
- Family hash: `{record['pre_edit_family_hash']}`

## Invariant to restore
{record['invariant_to_restore']}

## Minimal counterexample
{record['minimal_counterexample']}

## Allowed patch sites
{chr(10).join(f'- `{item}`' for item in record['allowed_patch_sites'])}

## Regression tests
{chr(10).join(f'- {item}' for item in record['regression_tests'])}

## Expected regenerated evidence
{chr(10).join(f'- `{item}`' for item in record['expected_regenerated_evidence'])}

## Stale evidence policy
{record['stale_evidence_policy']}

## Out of scope
{chr(10).join(f'- {item}' for item in record['out_of_scope'])}
"""
    _write(target.with_suffix(".md"), markdown, force=False)
    return target


def audit_subject_hash(out: Path = DEFAULT_OUT) -> str:
    digest = hashlib.sha256()
    for relative in (
        ".state/manifest.json",
        ".state/candidates/raw-proposals.json",
        ".state/candidates/selected.json",
        ".state/candidates/rejected.json",
        ".state/source-inventory.json",
        ".state/family-screen.json",
        ".state/docker-sanity.json",
        ".state/creator-preflight.json",
    ):
        path = out / relative
        if path.is_file():
            digest.update(relative.encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    digest.update(_family_hash(out).encode())
    return "sha256:" + digest.hexdigest()


def finalize_audit(out: Path, audit_report: Path, cycle_number: int) -> Path:
    """Record local-family verification only from a fresh passing audit."""
    _validate_out(out)
    report = json.loads(audit_report.read_text(encoding="utf-8"))
    subject = report.get("audit_subject", {})
    counts = report.get("confirmed_counts", {})
    live_subject = audit_subject_hash(out)
    if report.get("cycle") != cycle_number:
        _fail("audit_cycle_mismatch", audit_report.as_posix())
    if report.get("verdict") not in {"pass", "train"} or report.get("findings"):
        _fail("audit_not_passing", audit_report.as_posix())
    if subject.get("hash") != live_subject or not subject.get("match"):
        _fail("audit_subject_mismatch", f"report={subject.get('hash')} live={live_subject}")
    if counts.get("cataloged_roots") != 90 or counts.get("audit_admitted_roots", 0) < 60:
        _fail("retained_quota_not_met", str(counts))
    terminal = {
        "schema_version": "aider-local-family-verification-v1",
        "status": "local_family_verified",
        "family_id": FAMILY_ID,
        "cycle": cycle_number,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "retained_roots": counts["audit_admitted_roots"],
        "requested_roots": 90,
        "minimum_required_retained_roots": 60,
        "audit_subject_hash": live_subject,
        "audit_report_path": audit_report.as_posix(),
        "audit_report_hash": _sha_file(audit_report),
        "creator_preflight_hash": _sha_file(out / ".state/creator-preflight.json"),
        "docker_sanity_hash": _sha_file(out / ".state/docker-sanity.json"),
        "family_hash": _family_hash(out),
        "dataset_handoff": "not_requested",
        "nonclaims": ["SFT release", "training authorization", "benchmark uplift"],
    }
    target = out / ".state/local-family-verified.json"
    _write(target, json.dumps(terminal, indent=2, sort_keys=True) + "\n", force=False)
    return target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--cycle", type=int, default=1)
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--audit-subject-hash", action="store_true")
    parser.add_argument("--plan-remediation-from", type=Path)
    parser.add_argument("--finalize-audit-from", type=Path)
    args = parser.parse_args(argv)
    if args.plan_remediation_from:
        target = plan_remediation(args.out, args.plan_remediation_from)
        print(f"Wrote pre-edit remediation plan to {target}")
        return 0
    if args.audit_subject_hash:
        _validate_out(args.out)
        print(audit_subject_hash(args.out))
        return 0
    if args.finalize_audit_from:
        target = finalize_audit(args.out, args.finalize_audit_from, args.cycle)
        print(f"Wrote terminal local-family receipt to {target}")
        return 0
    roots = build(args.out, force=args.force, cycle_number=args.cycle)
    if args.verify_core:
        verify_core(args.out)
    if args.verify_host:
        verify_host(args.out, cycle_number=args.cycle)
    if args.docker_sanity:
        docker_sanity(args.out, cycle_number=args.cycle)
    print(f"Wrote {len(roots)} cross-midnight/offset/meeting tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
