"""Materialize and verify the 80-root duration/elapsed/countdown expansion.

The owner writes only beneath the count-plan expansion tree.  Existing task
trees are immutable inventory and semantic-screen inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import itertools
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_duration_elapsed_countdown_expansion_cases import (
    CASES,
    REJECTED_CYCLE_01_IDS,
    DurationExpansionCase,
)


EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
DEFAULT_OUT = EXPANSION_ROOT / "time-date" / "duration-elapsed-countdown"
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_DURATION_ELAPSED_COUNTDOWN_EXPANSION_CURRICULUM.md"
FAMILY_SPEC = "docs/aider-tasks-spec/aider-dates-and-clocks/duration-elapsed-countdown-expansion.md"
GENERATOR_PATH = (
    "src/w8_biayn/integrations/moonlight_duration_elapsed_countdown_expansion_aider_tasks.py"
)
CASES_PATH = "src/w8_biayn/integrations/moonlight_duration_elapsed_countdown_expansion_cases.py"
TEST_PATH = "tests/test_moonlight_duration_elapsed_countdown_expansion_aider_tasks.py"
PROMPT_DESIGN = "docs/aider-tasks-spec/prompts/generate-family-spec.md"
PROMPT_IMPLEMENT = "docs/aider-tasks-spec/prompts/implement-family-for-sft.md"
FAMILY_ID = "aider-expansion-duration-elapsed-countdown-v1"
COUNT_PLAN_CELL = "time-date/duration-elapsed-countdown-lifecycle-state"
MIN_ROOTS = MAX_ROOTS = 80
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
DEFAULT_HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
OFFICIAL_AIDER_CPP_HOLDOUTS = frozenset(
    {
        "all-your-base",
        "allergies",
        "bank-account",
        "binary-search-tree",
        "circular-buffer",
        "clock",
        "complex-numbers",
        "crypto-square",
        "diamond",
        "dnd-character",
        "gigasecond",
        "grade-school",
        "kindergarten-garden",
        "knapsack",
        "linked-list",
        "meetup",
        "parallel-letter-frequency",
        "perfect-numbers",
        "phone-number",
        "queen-attack",
        "robot-name",
        "space-age",
        "spiral-matrix",
        "sublist",
        "yacht",
        "zebra-puzzle",
    }
)


def _fail(code: str, detail: str = "") -> None:
    raise RuntimeError(f"{code}: {detail}" if detail else code)


def _write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, str):
        content = content.encode()
    if path.is_file() and path.read_bytes() == content:
        return
    path.write_bytes(content)


def _sha_bytes(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _source_hash(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _owner_hash() -> str:
    digest = hashlib.sha256()
    # Bind every source that can change materialization, verification, diversity,
    # contamination, or the focused policy assertions.  A green receipt must go
    # stale when any of these policy inputs changes.
    for path in (
        Path(GENERATOR_PATH),
        Path(CASES_PATH),
        Path(CURRICULUM),
        Path(FAMILY_SPEC),
        Path(TEST_PATH),
    ):
        digest.update(path.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "sha256:" + digest.hexdigest()
    for path in sorted(
        item for item in root.rglob("*") if item.is_file() and ".state" not in item.parts
    ):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def _pascal(task_id: str) -> str:
    return "".join(part.capitalize() for part in task_id.split("-"))


def _method(case: DurationExpansionCase) -> str:
    return {
        "rate-integration": "integrate",
        "elapsed-replay": "replay",
        "countdown-state": "simulate",
        "deadline-policy": "schedule",
        "timeline-analysis": "analyze",
    }[case.subtopic]


def _entry_fields(case: DurationExpansionCase) -> tuple[tuple[str, str], ...]:
    group = case.strategy // 10
    common = (("std::string", "id"), ("long long", "start"), ("long long", "end"))
    extras = (
        (("long long", "amount"), ("long long", "weight")),
        (("long long", "reserve"), ("long long", "deadline")),
        (("long long", "amount"), ("bool", "enabled")),
        (("long long", "deadline"), ("int", "sequence")),
        (("long long", "amount"), ("long long", "weight"), ("int", "sequence")),
        (("bool", "enabled"), ("int", "generation")),
        (("long long", "amount"), ("int", "sequence")),
        (("long long", "amount"), ("long long", "reserve"), ("long long", "weight")),
    )[group]
    return common + extras


def _initializer(
    case: DurationExpansionCase, *, alternate: bool = False, boundary: bool = False
) -> str:
    base = {
        "id": '"a"' if not alternate else '"b"',
        "start": "0" if not alternate else "3",
        "end": "3" if not alternate else "7",
        "amount": "2" if not alternate else "4",
        "sequence": "0" if not alternate else "1",
        "weight": "2" if not alternate else "3",
        "enabled": "true" if not alternate else "false",
        "kind": "0" if not alternate else "1",
        "deadline": "9" if not alternate else "12",
        "generation": "1" if not alternate else "2",
        "reserve": "1" if not alternate else "2",
    }
    if boundary:
        base.update(
            {
                "id": '"c"',
                "start": "7",
                "end": "7",
                "amount": "0",
                "sequence": "2",
                "weight": "1",
                "enabled": "true",
                "deadline": "7",
                "generation": "0",
                "reserve": "7",
            }
        )
    return "{" + ",".join(base[name] for _, name in _entry_fields(case)) + "}"


def _header(case: DurationExpansionCase) -> str:
    class_name = _pascal(case.task_id)
    fields = " ".join(f"{type_name} {name};" for type_name, name in _entry_fields(case))
    return f"""#pragma once
#include <string>
#include <vector>
namespace curriculum {{
class {class_name} {{
 public:
  struct Entry {{ {fields} }};
  struct Report {{ bool valid; long long value; long long witness; int accepted; int rejected; std::vector<std::string> events; }};
  Report {_method(case)}(const std::vector<Entry>& entries, long long limit) const;
}};
}}
"""


def _algorithm(case: DurationExpansionCase, *, opposite: bool = False) -> str:
    group, variant = divmod(case.strategy, 10)
    del opposite
    transforms = (
        """    Big numerator = span * Big(entry.amount);
    Big sample = (numerator + Big(entry.weight) - 1) / Big(entry.weight);""",
        """    const Big left = entry.start > entry.reserve ? Big(entry.start) : Big(entry.reserve);
    const Big right = entry.end < entry.deadline ? Big(entry.end) : Big(entry.deadline);
    Big sample = right > left ? right - left : 0;""",
        """    const Big spent = span * Big(entry.amount);
    Big sample = entry.enabled ? (spent >= limit_big ? Big(0) : limit_big - spent) : limit_big;""",
        """    Big sample = Big(entry.deadline) > Big(entry.end) ? Big(entry.deadline) - Big(entry.end) : Big(0);""",
        """    Big sample = Big(entry.amount) + Big(entry.sequence) * Big(entry.weight);""",
        """    Big sample = entry.enabled ? span * (Big(entry.generation) + 1) : Big(0);""",
        """    serial_cursor = serial_cursor > Big(entry.start) ? serial_cursor : Big(entry.start);
    checked_add(serial_cursor, span);
    checked_add(serial_cursor, Big(entry.amount));
    Big sample = serial_cursor;""",
        """    Big net = span * Big(entry.amount) - Big(entry.reserve);
    if (net < 0) net = 0;
    Big sample = (net + Big(entry.weight) - 1) / Big(entry.weight);""",
    )
    reducers = (
        """    checked_add(accumulator, sample);""",
        """    checked_add(accumulator, sample);
    checked_add(sample_count, 1);""",
        """    checked_add(accumulator, sample);""",
        """    if (!have_sample || sample > accumulator) {
      accumulator = sample;
      witness = Big(index);
      have_sample = true;
    }""",
        """    if (sample >= limit_big) {
      checked_add(accumulator, 1);
      if (witness < 0) witness = Big(index);
    }""",
        """    if (sample > 0) {
      checked_add(accumulator, sample);
      checked_add(positive_count, 1);
    }""",
        """    checked_add(prefix, sample);
    if (witness < 0 && prefix >= limit_big) witness = Big(index);""",
        """    if (accumulator < limit_big) {
      const Big room = limit_big - accumulator;
      checked_add(accumulator, sample < room ? sample : room);
      if (accumulator == limit_big && witness < 0) witness = Big(index);
    }""",
        """    if (!have_sample || sample != previous_sample) {
      checked_add(accumulator, 1);
      witness = Big(index);
      previous_sample = sample;
      have_sample = true;
    }""",
        """    if (index % 2 == 0) checked_add(even_total, sample);
    else checked_add(odd_total, sample);""",
    )
    finalize = (
        "",
        """  if (sample_count != 0) {
    checked_add(accumulator, sample_count - 1);
    accumulator /= sample_count;
  }
  witness = sample_count;""",
        """  const Big divisor = limit_big + 1;
  witness = accumulator / divisor;
  accumulator %= divisor;""",
        "",
        "",
        """  witness = positive_count;""",
        """  accumulator = prefix;""",
        "",
        "",
        """  accumulator = even_total >= odd_total ? even_total - odd_total : odd_total - even_total;
  witness = even_total >= odd_total ? 0 : 1;""",
    )
    state = ["Big accumulator = 0;", "Big witness = -1;", "bool arithmetic_ok = true;"]
    if variant == 6:
        state.append("Big prefix = 0;")
    if group == 6:
        state.append("Big serial_cursor = 0;")
    if variant == 8:
        state.append("Big previous_sample = 0;")
    if variant == 9:
        state.extend(("Big even_total = 0;", "Big odd_total = 0;"))
    if variant == 1:
        state.append("Big sample_count = 0;")
    if variant == 5:
        state.append("Big positive_count = 0;")
    if variant in {3, 8}:
        state.append("bool have_sample = false;")
    if group == 2 or variant in {2, 4, 6, 7}:
        state.append("const Big limit_big = limit;")
    if group == 6 or variant != 3:
        state.append(
            "const auto checked_add = [&arithmetic_ok](Big& target, const Big& increment) {\n"
            "  Big result = 0;\n"
            "  if (__builtin_add_overflow(target, increment, &result)) arithmetic_ok = false;\n"
            "  else target = result;\n"
            "};"
        )
    declarations = "\n  ".join(state)
    span_declaration = (
        "    const Big span = Big(entry.end) - Big(entry.start);"
        if group in {0, 2, 5, 6, 7}
        else ""
    )
    return f"""  {declarations}
  std::size_t index = 0;
  for (const auto& entry : ordered) {{
{span_declaration}
{transforms[group]}
{reducers[variant]}
    ++index;
  }}
{finalize[variant]}
"""


def _reference(
    case: DurationExpansionCase, *, opposite: bool = False, policy_limit: int | None = None
) -> str:
    class_name = _pascal(case.task_id)
    method = _method(case)
    group = case.strategy // 10
    sort_direction = ">" if opposite else "<"
    limit_guard = "limit < 0" if policy_limit is None else f"limit < {policy_limit}"
    extra_invalid = (
        "entry.amount < 0 || entry.weight <= 0",
        "entry.reserve < 0 || entry.deadline < entry.reserve",
        "entry.amount < 0",
        "entry.deadline < 0 || entry.sequence < 0",
        "entry.amount < 0 || entry.weight < 0 || entry.sequence < 0",
        "entry.generation < 0",
        "entry.amount < 0 || entry.sequence < 0",
        "entry.amount < 0 || entry.reserve < 0 || entry.weight <= 0",
    )[group]
    if group in {3, 4, 6}:
        primary = f"left.sequence != right.sequence ? left.sequence {sort_direction} right.sequence"
        tie = "left.start != right.start ? left.start < right.start : left.id < right.id"
    else:
        primary = f"left.start != right.start ? left.start {sort_direction} right.start"
        tie = "left.id < right.id"
    comparator = f"return {primary} : {tie};"
    return f"""#include "task.h"
#include <algorithm>
#include <climits>
#include <set>
namespace curriculum {{
namespace {{
__extension__ using Big = __int128;
bool fits_long_long(const Big& value) {{
  return value >= static_cast<Big>(LLONG_MIN) && value <= static_cast<Big>(LLONG_MAX);
}}
}}
{class_name}::Report {class_name}::{method}(const std::vector<Entry>& entries, long long limit) const {{
  Report report{{true, 0, -1, 0, 0, {{}}}};
  if ({limit_guard}) return {{false, 0, -1, 0, 0, {{}}}};
  std::set<std::string> ids;
  std::vector<Entry> ordered;
  for (const auto& entry : entries) {{
    if (entry.id.empty() || entry.start < 0 || entry.end < entry.start ||
        {extra_invalid} || !ids.insert(entry.id).second) {{
      ++report.rejected;
      continue;
    }}
    ordered.push_back(entry);
  }}
  std::stable_sort(ordered.begin(), ordered.end(), [](const Entry& left, const Entry& right) {{
    {comparator}
  }});
  if (ordered.size() > static_cast<std::size_t>(INT_MAX)) return {{false, 0, -1, 0, 0, {{}}}};
  report.accepted = static_cast<int>(ordered.size());
{_algorithm(case, opposite=opposite)}  if (!arithmetic_ok || !fits_long_long(accumulator) || !fits_long_long(witness)) {{
    return {{false, 0, -1, 0, 0, {{}}}};
  }}
  report.value = static_cast<long long>(accumulator);
  report.witness = static_cast<long long>(witness);
  for (const auto& entry : ordered) report.events.push_back(entry.id);
  return report;
}}
}}
"""


def _starter(case: DurationExpansionCase) -> str:
    class_name = _pascal(case.task_id)
    return f"""#include "task.h"
namespace curriculum {{
{class_name}::Report {class_name}::{_method(case)}(const std::vector<Entry>&, long long) const {{
  return {{false, 0, -1, 0, 0, {{}}}};
}}
}}
"""


def _mutated_source(source: str, case: DurationExpansionCase) -> str:
    variant = case.strategy % 10
    mutations = (
        ("checked_add(accumulator, sample);", "checked_add(accumulator, sample + 1);"),
        (
            "checked_add(accumulator, sample_count - 1);",
            "checked_add(accumulator, sample_count + sample_count);",
        ),
        ("const Big divisor = limit_big + 1;", "const Big divisor = limit_big / 2 + 1;"),
        ("sample > accumulator", "sample < accumulator"),
        ("sample >= limit_big", "sample < limit_big"),
        ("sample > 0", "sample <= 0"),
        ("prefix >= limit_big", "prefix < limit_big"),
        (
            "checked_add(accumulator, sample < room ? sample : room);",
            "checked_add(accumulator, (sample < room ? sample : room) + 1);",
        ),
        ("sample != previous_sample", "sample == previous_sample"),
        (
            "even_total >= odd_total ? even_total - odd_total : odd_total - even_total",
            "even_total + odd_total + 1",
        ),
    )
    original, mutated = mutations[variant]
    if source.count(original) != 1:
        _fail("negative_fixture_generation_failed", f"{case.task_id}: {original}")
    return source.replace(original, mutated, 1)


def _negative(case: DurationExpansionCase) -> str:
    return _mutated_source(_reference(case), case)


def _negative_transform(case: DurationExpansionCase) -> str:
    source = _reference(case)
    group = case.strategy // 10
    mutations = (
        (
            "(numerator + Big(entry.weight) - 1) / Big(entry.weight)",
            "numerator / Big(entry.weight)",
        ),
        ("entry.start > entry.reserve ? Big(entry.start) : Big(entry.reserve)", "Big(entry.start)"),
        ("limit_big - spent", "limit_big"),
        ("Big(entry.deadline) - Big(entry.end)", "Big(1)"),
        (
            "Big(entry.amount) + Big(entry.sequence) * Big(entry.weight)",
            "Big(entry.amount) - Big(entry.sequence) * Big(entry.weight)",
        ),
        (
            "entry.enabled ? span * (Big(entry.generation) + 1)",
            "!entry.enabled ? span * (Big(entry.generation) + 1)",
        ),
        ("serial_cursor > Big(entry.start)", "serial_cursor < Big(entry.start)"),
        (
            "span * Big(entry.amount) - Big(entry.reserve)",
            "span * Big(entry.amount) + Big(entry.reserve)",
        ),
    )
    original, replacement = mutations[group]
    if source.count(original) != 1:
        _fail("negative_fixture_generation_failed", f"{case.task_id}: transform")
    return source.replace(original, replacement, 1)


def _base_records(*, boundary: bool = False) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [
        {
            "id": "a",
            "start": 0,
            "end": 3,
            "amount": 2,
            "sequence": 0,
            "weight": 2,
            "enabled": True,
            "deadline": 9,
            "generation": 1,
            "reserve": 1,
        },
        {
            "id": "b",
            "start": 3,
            "end": 7,
            "amount": 4,
            "sequence": 1,
            "weight": 3,
            "enabled": False,
            "deadline": 12,
            "generation": 2,
            "reserve": 2,
        },
    ]
    if boundary:
        rows.append(
            {
                "id": "c",
                "start": 7,
                "end": 7,
                "amount": 0,
                "sequence": 2,
                "weight": 1,
                "enabled": True,
                "deadline": 7,
                "generation": 0,
                "reserve": 7,
            }
        )
    return rows


def _evaluate_records(
    case: DurationExpansionCase,
    records: Sequence[dict[str, object]],
    *,
    limit: int,
    opposite: bool = False,
    transform_mutated: bool = False,
) -> tuple[int, int, int, int, tuple[str, ...]]:
    ordered = [dict(row) for row in records]
    group, variant = divmod(case.strategy, 10)
    if group in {3, 4, 6}:
        ordered.sort(
            key=lambda row: (
                (-int(row["sequence"])) if opposite else int(row["sequence"]),
                int(row["start"]),
                str(row["id"]),
            )
        )
    else:
        ordered.sort(
            key=lambda row: (
                (-int(row["start"])) if opposite else int(row["start"]),
                str(row["id"]),
            )
        )
    samples: list[int] = []
    serial_cursor = 0
    for entry in ordered:
        start, end = int(entry["start"]), int(entry["end"])
        span = end - start
        amount, weight = int(entry["amount"]), int(entry["weight"])
        reserve, deadline = int(entry["reserve"]), int(entry["deadline"])
        sequence, generation = int(entry["sequence"]), int(entry["generation"])
        enabled = bool(entry["enabled"])
        if group == 0:
            numerator = span * amount
            sample = (
                numerator // weight if transform_mutated else (numerator + weight - 1) // weight
            )
        elif group == 1:
            left = start if transform_mutated else max(start, reserve)
            sample = max(0, min(end, deadline) - left)
        elif group == 2:
            spent = span * amount
            if not enabled:
                sample = limit
            elif spent >= limit:
                sample = 0
            else:
                sample = limit if transform_mutated else limit - spent
        elif group == 3:
            sample = (1 if deadline > end else 0) if transform_mutated else max(0, deadline - end)
        elif group == 4:
            sample = amount - sequence * weight if transform_mutated else amount + sequence * weight
        elif group == 5:
            active = not enabled if transform_mutated else enabled
            sample = span * (generation + 1) if active else 0
        elif group == 6:
            serial_cursor = (
                (min(serial_cursor, start) if transform_mutated else max(serial_cursor, start))
                + span
                + amount
            )
            sample = serial_cursor
        else:
            net = span * amount + reserve if transform_mutated else max(0, span * amount - reserve)
            sample = (net + weight - 1) // weight
        samples.append(sample)
    witness = -1
    if variant == 0:
        value = sum(samples)
    elif variant == 1:
        value = (sum(samples) + len(samples) - 1) // len(samples) if samples else 0
        witness = len(samples)
    elif variant == 2:
        witness, value = divmod(sum(samples), limit + 1)
    elif variant == 3:
        value = max(samples, default=0)
        witness = samples.index(value) if samples else -1
    elif variant == 4:
        selected = [index for index, sample in enumerate(samples) if sample >= limit]
        value, witness = len(selected), (selected[0] if selected else -1)
    elif variant == 5:
        selected = [sample for sample in samples if sample > 0]
        value, witness = sum(selected), len(selected)
    elif variant == 6:
        prefix = 0
        for index, sample in enumerate(samples):
            prefix += sample
            if witness < 0 and prefix >= limit:
                witness = index
        value = prefix
    elif variant == 7:
        value = 0
        for index, sample in enumerate(samples):
            value += min(sample, limit - value)
            if value == limit and witness < 0:
                witness = index
    elif variant == 8:
        value, previous = 0, None
        for index, sample in enumerate(samples):
            if previous is None or sample != previous:
                value, witness, previous = value + 1, index, sample
    else:
        even, odd = sum(samples[::2]), sum(samples[1::2])
        value, witness = abs(even - odd), (0 if even >= odd else 1)
    return value, witness, len(ordered), 0, tuple(str(row["id"]) for row in ordered)


def _run_value(
    case: DurationExpansionCase, *, opposite: bool = False, limit: int = 10, boundary: bool = False
) -> tuple[int, int, int, int, tuple[str, ...]]:
    return _evaluate_records(case, _base_records(boundary=boundary), limit=limit, opposite=opposite)


def _cpp_record(case: DurationExpansionCase, record: dict[str, object]) -> str:
    values = {
        "id": f'"{record["id"]}"',
        "enabled": "true" if record["enabled"] else "false",
        **{key: str(value) for key, value in record.items() if key not in {"id", "enabled"}},
    }
    return "{" + ",".join(values[name] for _, name in _entry_fields(case)) + "}"


def _invalid_initializer(case: DurationExpansionCase) -> str:
    record = _base_records()[0]
    group = case.strategy // 10
    key, value = (
        ("weight", 0),
        ("deadline", 0),
        ("amount", -1),
        ("sequence", -1),
        ("weight", -1),
        ("generation", -1),
        ("amount", -1),
        ("weight", 0),
    )[group]
    record[key] = value
    if group == 1:
        record["reserve"] = 1
    return _cpp_record(case, record)


def _invalid_records(case: DurationExpansionCase) -> tuple[tuple[str, dict[str, object]], ...]:
    base = _base_records()[0]
    records: list[tuple[str, dict[str, object]]] = []

    def add(name: str, **changes: object) -> None:
        record = dict(base)
        record.update(changes)
        records.append((name, record))

    add("empty_id", id="")
    add("negative_start", start=-1)
    add("reversed_span", start=3, end=2)
    group = case.strategy // 10
    additions = {
        0: (("negative_amount", {"amount": -1}), ("zero_weight", {"weight": 0})),
        1: (
            ("negative_reserve", {"reserve": -1}),
            ("deadline_before_reserve", {"reserve": 2, "deadline": 1}),
        ),
        2: (("negative_amount", {"amount": -1}),),
        3: (
            ("negative_deadline", {"deadline": -1}),
            ("negative_sequence", {"sequence": -1}),
        ),
        4: (
            ("negative_amount", {"amount": -1}),
            ("negative_weight", {"weight": -1}),
            ("negative_sequence", {"sequence": -1}),
        ),
        5: (("negative_generation", {"generation": -1}),),
        6: (
            ("negative_amount", {"amount": -1}),
            ("negative_sequence", {"sequence": -1}),
        ),
        7: (
            ("negative_amount", {"amount": -1}),
            ("negative_reserve", {"reserve": -1}),
            ("zero_weight", {"weight": 0}),
        ),
    }[group]
    for name, changes in additions:
        add(name, **changes)
    return tuple(records)


def _with_counts(
    report: tuple[int, int, int, int, tuple[str, ...]],
    *,
    accepted: int | None = None,
    rejected: int | None = None,
) -> tuple[int, int, int, int, tuple[str, ...]]:
    value, witness, old_accepted, old_rejected, events = report
    return (
        value,
        witness,
        old_accepted if accepted is None else accepted,
        old_rejected if rejected is None else rejected,
        events,
    )


def _unsorted_records(case: DurationExpansionCase) -> list[dict[str, object]]:
    rows = _base_records(boundary=True)
    return [rows[2], rows[0], rows[1]]


def _tie_records(case: DurationExpansionCase) -> list[dict[str, object]]:
    rows = [dict(row) for row in _base_records()]
    rows = rows[:2]
    rows[0]["id"], rows[1]["id"] = "z", "a"
    rows[0]["start"] = rows[1]["start"] = 0
    if case.strategy // 10 in {3, 4, 6}:
        rows[0]["sequence"] = rows[1]["sequence"] = 0
    return rows


def _large_records(case: DurationExpansionCase) -> list[dict[str, object]]:
    maximum = 9223372036854775807
    group = case.strategy // 10
    rows = []
    for index, identity in enumerate(("x", "y", "z")):
        row: dict[str, object] = {
            "id": identity,
            "start": 0,
            "end": maximum,
            "amount": 1,
            "sequence": index,
            "weight": 1,
            "enabled": True,
            "deadline": maximum,
            "generation": 0,
            "reserve": 0,
        }
        if group == 2:
            row.update({"end": 1, "amount": 0, "enabled": False})
        elif group == 3:
            row.update({"end": 0})
        elif group == 4:
            row.update({"end": 0, "amount": maximum, "weight": 0})
        elif group == 6:
            row.update({"amount": 0})
        rows.append(row)
    return rows


def _overflow_records(case: DurationExpansionCase) -> list[dict[str, object]]:
    maximum = 9223372036854775807
    group = case.strategy // 10
    rows: list[dict[str, object]] = []
    for index, identity in enumerate(("u", "v", "w")):
        row: dict[str, object] = {
            "id": identity,
            "start": 0,
            "end": maximum,
            "amount": maximum,
            "sequence": index,
            "weight": 1,
            "enabled": True,
            "deadline": maximum,
            "generation": 0,
            "reserve": 0,
        }
        if group == 1:
            row.update({"amount": 0})
        elif group == 2:
            row.update({"end": 1, "amount": 0, "enabled": False})
        elif group == 3:
            row.update({"end": 0, "amount": 0})
        elif group == 4:
            row.update({"end": 0, "weight": maximum})
        elif group == 5:
            row.update({"amount": 0, "generation": 2147483647})
        elif group == 6:
            row.update({"amount": maximum})
        rows.append(row)
    if case.strategy % 10 == 9 and group != 6:
        middle = rows[1]
        middle.update(_zero_record("v"))
        middle["start"] = 0
        middle["sequence"] = 1
        if group == 2:
            middle.update({"end": 1, "amount": maximum, "enabled": True})
    return rows


def _range_bounded(case: DurationExpansionCase) -> bool:
    group, variant = divmod(case.strategy, 10)
    return (
        variant in {4, 7, 8}
        or (variant in {1, 3} and group in {1, 2, 3})
        or (variant == 2 and group == 2)
    )


def _overflow_limit(case: DurationExpansionCase) -> int:
    group, variant = divmod(case.strategy, 10)
    return 0 if variant == 2 and group != 2 else 9223372036854775807


def _transform_probe(
    case: DurationExpansionCase,
) -> tuple[list[dict[str, object]], int, tuple[int, int, int, int, tuple[str, ...]]]:
    variant = case.strategy % 10
    pool = []
    for seed in range(6):
        start = seed % 3
        reserve = (seed + 1) % 3
        pool.append(
            {
                "id": "unset",
                "start": start,
                "end": start + seed % 4,
                "amount": seed % 4,
                "sequence": seed,
                "weight": seed % 3 + 1,
                "enabled": seed % 2 == 0,
                "deadline": max(
                    reserve,
                    start + (seed + 1) % 4,
                    start + seed % 4 + seed % 3,
                ),
                "generation": seed % 3,
                "reserve": reserve,
            }
        )
    pool.append(
        {
            "id": "unset",
            "start": 1,
            "end": 2,
            "amount": 1,
            "sequence": 7,
            "weight": 2,
            "enabled": True,
            "deadline": 2,
            "generation": 1,
            "reserve": 1,
        }
    )
    for width in (2, 3):
        for choices in itertools.product(pool, repeat=width):
            records = []
            for index, selected in enumerate(choices):
                row = dict(selected)
                row["id"] = chr(ord("p") + index)
                records.append(row)
            limits = (1, 2, 3, 5, 7, 10) if variant == 7 else (0, 1, 2, 3, 5, 7, 10)
            for limit in limits:
                expected = _evaluate_records(case, records, limit=limit)
                wrong = _evaluate_records(case, records, limit=limit, transform_mutated=True)
                if expected[:2] != wrong[:2]:
                    return records, limit, expected
    _fail("transform_discriminator_missing", case.task_id)


def _report_assertion(variable: str, expected: tuple[int, int, int, int, tuple[str, ...]]) -> str:
    value, witness, accepted, rejected, events = expected
    event_values = ",".join(f'"{item}"' for item in events)
    return (
        f"{variable}.valid && {variable}.value=={value} && {variable}.witness=={witness} && "
        f"{variable}.accepted=={accepted} && {variable}.rejected=={rejected} && "
        f"{variable}.events==std::vector<std::string>{{{event_values}}}"
    )


def _complete_assertion(variable: str, expected: tuple[int, int, int, int, tuple[str, ...]]) -> str:
    if all(-9223372036854775808 <= item <= 9223372036854775807 for item in expected[:2]):
        return _report_assertion(variable, expected)
    return (
        f"!{variable}.valid && {variable}.value==0 && {variable}.witness==-1 && "
        f"{variable}.accepted==0 && {variable}.rejected==0 && {variable}.events.empty()"
    )


def _zero_record(identity: str = "zero") -> dict[str, object]:
    return {
        "id": identity,
        "start": 0,
        "end": 0,
        "amount": 0,
        "sequence": 0,
        "weight": 1,
        "enabled": True,
        "deadline": 0,
        "generation": 0,
        "reserve": 0,
    }


def _reducer_probe(
    case: DurationExpansionCase,
) -> tuple[list[dict[str, object]], int, tuple[int, int, int, int, tuple[str, ...]]]:
    variant = case.strategy % 10
    if variant == 2:
        records = _large_records(case)
        limit = 9223372036854775807
    elif variant in {0, 4, 5, 6}:
        records = [_zero_record()]
        limit = 0
    elif variant in {3, 8, 9}:
        first, second = _zero_record("z"), _zero_record("a")
        records = [first, second]
        limit = 1
    elif variant == 7:
        records = _base_records(boundary=True)
        for limit in range(1, 21):
            expected = _evaluate_records(case, records, limit=limit)
            if expected[0] == limit and expected[1] >= 0:
                return records, limit, expected
        _fail("reducer_boundary_missing", case.task_id)
    else:
        records = [_zero_record(), dict(_base_records()[0], id="positive")]
        limit = 3
    return records, limit, _evaluate_records(case, records, limit=limit)


def _test_source(
    case: DurationExpansionCase, *, hidden: bool = False, opposite: bool = False
) -> str:
    class_name = _pascal(case.task_id)
    method = _method(case)
    if not hidden:
        expected = _run_value(case, opposite=opposite)
        assertions = _report_assertion("r", expected)
        return f"""#include "task.h"
#include <string>
#include <vector>
int main() {{
  curriculum::{class_name} subject;
  const auto r=subject.{method}({{{_initializer(case)}, {_initializer(case, alternate=True)}}},10);
  return {assertions} ? 0 : 1;
}}
"""
    declarations: list[str] = []
    assertions: list[str] = []

    def add_case(
        name: str,
        records: Sequence[dict[str, object]],
        limit: int | str,
        expected: tuple[int, int, int, int, tuple[str, ...]],
    ) -> None:
        literal = ",".join(_cpp_record(case, row) for row in records)
        declarations.append(f"  const auto {name}=subject.{method}({{{literal}}},{limit});")
        assertions.append(f"({_complete_assertion(name, expected)})")

    boundary_records = _base_records(boundary=True)
    add_case(
        "transform_boundary",
        boundary_records,
        10,
        _evaluate_records(case, boundary_records, limit=10, opposite=opposite),
    )
    probe_records, probe_limit, probe_expected = _transform_probe(case)
    if opposite:
        probe_expected = _evaluate_records(case, probe_records, limit=probe_limit, opposite=True)
    add_case("transform_probe", probe_records, probe_limit, probe_expected)
    reducer_records, reducer_limit, reducer_expected = _reducer_probe(case)
    if opposite:
        reducer_expected = _evaluate_records(
            case, reducer_records, limit=reducer_limit, opposite=True
        )
    add_case("reducer_boundary", reducer_records, reducer_limit, reducer_expected)
    unsorted_records = _unsorted_records(case)
    add_case(
        "unsorted_input",
        unsorted_records,
        10,
        _evaluate_records(case, unsorted_records, limit=10, opposite=opposite),
    )
    tie_records = _tie_records(case)
    add_case(
        "primary_key_tie",
        tie_records,
        10,
        _evaluate_records(case, tie_records, limit=10, opposite=opposite),
    )
    empty_expected = _evaluate_records(case, [], limit=10, opposite=opposite)
    for invalid_name, invalid_record in _invalid_records(case):
        add_case(
            f"malformed_{invalid_name}",
            [invalid_record],
            10,
            _with_counts(empty_expected, accepted=0, rejected=1),
        )
    duplicate_record = _base_records()[0]
    duplicate_expected = _evaluate_records(case, [duplicate_record], limit=10, opposite=opposite)
    add_case(
        "duplicate_id",
        [duplicate_record, duplicate_record],
        10,
        _with_counts(duplicate_expected, accepted=1, rejected=1),
    )
    add_case("empty_input", [], 10, empty_expected)
    near_records = _large_records(case)[:1]
    add_case(
        "near_limit",
        near_records,
        "LLONG_MAX",
        _evaluate_records(case, near_records, limit=9223372036854775807),
    )
    overflow_records = _overflow_records(case)
    overflow_limit = _overflow_limit(case)
    overflow_expected = _evaluate_records(case, overflow_records, limit=overflow_limit)
    overflow_fits = all(
        -9223372036854775808 <= item <= 9223372036854775807 for item in overflow_expected[:2]
    )
    if overflow_fits != _range_bounded(case):
        _fail("overflow_probe_policy_mismatch", case.task_id)
    add_case(
        "overflow_or_range_bound",
        overflow_records,
        "LLONG_MAX" if overflow_limit == 9223372036854775807 else overflow_limit,
        overflow_expected,
    )
    declarations.append(
        f"  const auto negative_limit=subject.{method}({{{_cpp_record(case, _zero_record())}}},-1);"
    )
    assertions.append(
        "(!negative_limit.valid && negative_limit.value==0 && negative_limit.witness==-1 && "
        "negative_limit.accepted==0 && negative_limit.rejected==0 && negative_limit.events.empty())"
    )
    declaration_text = "\n".join(declarations)
    assertion_text = " &&\n         ".join(assertions)
    return f"""#include "task.h"
#include <climits>
#include <vector>
int main() {{
  curriculum::{class_name} subject;
{declaration_text}
  return {assertion_text} ? 0 : 1;
}}
"""


def _instructions(case: DurationExpansionCase) -> str:
    class_name = _pascal(case.task_id)
    fields = ", ".join(f"`{type_name} {name}`" for type_name, name in _entry_fields(case))
    group, variant = divmod(case.strategy, 10)
    transforms = (
        "For each record let span=end-start and sample=ceil(span*amount/weight). amount is nonnegative and weight is positive.",
        "For each record require reserve>=0 and deadline>=reserve, intersect [start,end) with [reserve,deadline), and use the nonnegative intersection length as sample.",
        "For each record require amount>=0 and let spent=(end-start)*amount. If enabled, sample=max(limit-spent,0); otherwise sample=limit.",
        "Require deadline>=0 and sequence>=0. Process by sequence, then start, then ID. sample=max(deadline-end,0), so late records have zero remaining slack.",
        "Require amount>=0, weight>=0, and sequence>=0. Process by sequence, then start, then ID. sample=amount+sequence*weight.",
        "Require generation>=0. For enabled records sample=(end-start)*(generation+1); disabled records have sample zero.",
        "Require amount>=0 and sequence>=0. Process by sequence, then start, then ID. Maintain cursor=max(cursor,start)+end-start+amount and use the new cursor as sample.",
        "Require amount>=0, reserve>=0, and weight>0. Let net=max((end-start)*amount-reserve,0) and sample=ceil(net/weight).",
    )
    reducers = (
        "value is the sum of samples; witness is -1.",
        "value is ceil(sum(samples)/count); witness is count. Empty input returns value 0 and witness 0.",
        "Divide the sample sum by limit+1: value is the nonnegative remainder and witness is the quotient.",
        "value is the greatest sample and witness its zero-based first processing index; empty input returns 0,-1.",
        "value counts samples >= limit and witness is the first matching index or -1.",
        "value sums strictly positive samples and witness counts them.",
        "value is the complete sample sum and witness is the first index whose prefix is >= limit, or -1.",
        "value accumulates each sample but is capped at limit; witness is the first index reaching the cap, or -1.",
        "value counts runs of unequal adjacent samples and witness is the final run's starting index, or -1.",
        "value is abs(sum(even-index samples)-sum(odd-index samples)); witness is 0 when even is at least odd, otherwise 1.",
    )
    if _range_bounded(case):
        range_policy = (
            "For this transform/reducer combination, the final value and witness stay "
            "bounded by the limit, the accepted count (which is at most INT_MAX), or a "
            "single long-long-bounded transformed sample, so extreme accepted inputs "
            "remain valid."
        )
    else:
        range_policy = (
            "This transform/reducer can produce a final value or witness above LLONG_MAX; "
            "such a result must yield the complete atomic invalid report, while a "
            "representable LLONG_MAX result must stay valid."
        )
    value, witness, accepted, rejected, events = _run_value(case)
    event_text = ", ".join(f"`{item}`" for item in events)
    return f"""# Instructions

Implement `curriculum::{class_name}::{_method(case)}` in C++17. The editable
`Entry` fields are {fields}; the returned `Report` owns its event IDs.

{transforms[group]} {reducers[variant]}

A record ID must be nonempty and unique. `start` and `end` are nonnegative
half-open duration coordinates with `end>=start`. Extra numeric fields must
satisfy the positivity rules above; sequence and generation are nonnegative.
Malformed or duplicate records increment `rejected` and do not mutate the
accepted computation. Other records increment `accepted`. Except for the
sequence-ordered transforms, processing order is start then ID. `events`
contains accepted IDs in processing order.

All intermediate arithmetic is mathematical integer arithmetic. If final
`value` or `witness` cannot fit `long long`, return the atomic empty invalid
report `{{false,0,-1,0,0,{{}}}}`. A negative `limit` does the same. {range_policy}

Boundary policy: {case.boundary_rule}.

## Example

For the records
`{_initializer(case)}` and `{_initializer(case, alternate=True)}` with limit
10, the complete report is valid with value {value}, witness {witness}, accepted
{accepted}, rejected {rejected}, and events [{event_text}].

Compute every report from the input records on each call: a hard-coded result
would only cover the cases someone anticipated. Apply both the transform and
the reducer, keep the declared order and tie rule, and check all signed
arithmetic. Return complete replacements for the two declared editable files
only.
"""


CMAKE = r"""cmake_minimum_required(VERSION 3.16)
project(duration_expansion_task LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(NOT DEFINED TASK_SOURCE)
  set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp")
endif()
add_library(task_solution STATIC "${TASK_SOURCE}")
target_include_directories(task_solution PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(task_solution PRIVATE -Wall -Wextra -Wpedantic -Werror)
endif()
enable_testing()
foreach(test_source IN ITEMS task_visible_test.cpp .meta/task_hidden_test.cpp)
  get_filename_component(test_name "${test_source}" NAME_WE)
  add_executable("${test_name}" "${test_source}")
  target_link_libraries("${test_name}" PRIVATE task_solution)
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options("${test_name}" PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
  add_test(NAME "${test_name}" COMMAND "${test_name}")
endforeach()
"""


def _case_files(case: DurationExpansionCase) -> dict[str, str]:
    config = {
        "authors": ["w8-biayn"],
        "blurb": case.mechanism.capitalize() + ".",
        "files": {
            "solution": ["task.h", "task.cpp"],
            "test": ["task_visible_test.cpp"],
            "example": [".meta/example.h", ".meta/example.cpp"],
        },
    }
    provenance = {
        "schema_version": "aider-expansion-provenance-v1",
        "family_id": FAMILY_ID,
        "curriculum_document": CURRICULUM,
        "family_specification": FAMILY_SPEC,
        "curriculum_task_id": case.task_id,
        "count_plan_cell": COUNT_PLAN_CELL,
        "lineage": "replacement-new-root",
        "replaces": REJECTED_CYCLE_01_IDS[case.strategy],
        "origin": "newly authored in-repository clean-room expansion",
        "license": "repository-authored",
        "semantic_mechanism": case.mechanism,
        "status": "local task artifact; not admitted SFT data",
        "benchmark_separation": "No official Aider task prompt, API, tests, reference, response, or retry history was used.",
        "version": 4,
    }
    return {
        ".docs/instructions.md": _instructions(case),
        ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n",
        ".meta/tests.toml": f'[visible]\ndescription = "normal {case.mechanism}"\n\n[hidden]\ndescription = "complete-report transform and reducer boundaries, every malformed field class, duplicate, empty, unsorted order, primary-key tie, negative limit, representable near-limit, and overflow-or-proved-range-bound behavior"\n\n[negative_transform]\ndescription = "compiled transform misconception must fail"\n\n[negative_reducer]\ndescription = "compiled reducer misconception must fail"\n',
        "task.h": _header(case),
        "task.cpp": _starter(case),
        ".meta/example.h": _header(case),
        ".meta/example.cpp": _reference(case),
        ".meta/negative_false_substitute.cpp": _negative(case),
        ".meta/negative_transform.cpp": _negative_transform(case),
        "task_visible_test.cpp": _test_source(case),
        ".meta/task_hidden_test.cpp": _test_source(case, hidden=True),
        "CMakeLists.txt": CMAKE,
    }


def _inventory(root: Path, *, exclude: Path | None = None) -> dict[str, object]:
    records = []
    for config in sorted(root.rglob(".meta/config.json")) if root.is_dir() else []:
        if ".state" in config.parts:
            continue
        task_root = config.parent.parent
        if exclude is not None and (task_root == exclude or exclude in task_root.parents):
            continue
        records.append(
            {
                "task_id": task_root.name,
                "root": task_root.as_posix(),
                "tree_hash": _tree_hash(task_root),
            }
        )
    encoded = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return {
        "root": root.as_posix(),
        "count": len(records),
        "records": records,
        "inventory_hash": _sha_bytes(encoded),
    }


def _validate_output_root(out: Path) -> None:
    resolved = out.resolve()
    expansion = EXPANSION_ROOT.resolve()
    if resolved != expansion and expansion not in resolved.parents:
        _fail("expansion_output_required", out.as_posix())
    for forbidden in (LEGACY_ROOT.resolve(), REVERIFY_ROOT.resolve()):
        if resolved == forbidden or forbidden in resolved.parents:
            _fail("existing_tree_immutable", out.as_posix())
    cursor = out
    while cursor != cursor.parent:
        if cursor.is_symlink():
            _fail("expansion_symlink_refused", cursor.as_posix())
        if cursor == EXPANSION_ROOT:
            break
        cursor = cursor.parent


def _existing_ids(out: Path) -> set[str]:
    ids: set[str] = set()
    for root in (LEGACY_ROOT, REVERIFY_ROOT, EXPANSION_ROOT):
        if not root.is_dir():
            continue
        for config in root.rglob(".meta/config.json"):
            if ".state" in config.parts:
                continue
            task_root = config.parent.parent
            if out in task_root.parents:
                continue
            if task_root.name in ids:
                # Existing legacy/reverify mirrors are reserved once; their
                # duplicate identity does not authorize a new expansion copy.
                continue
            ids.add(task_root.name)
    return ids


def _write_source_manifests(out: Path) -> None:
    state = out / ".state"
    for name, root in (
        ("legacy", LEGACY_ROOT),
        ("reverify", REVERIFY_ROOT),
        ("expansion-before", EXPANSION_ROOT),
    ):
        inventory = _inventory(root, exclude=out if name == "expansion-before" else None)
        _write(
            state / "source-inventory" / f"{name}.json",
            json.dumps(inventory, indent=2, sort_keys=True) + "\n",
        )
    proposals = [
        {"task_id": task_id, "disposition": "rejected_cycle_01_formula_bank"}
        for task_id in REJECTED_CYCLE_01_IDS
    ] + [{**asdict(case), "disposition": "selected_cycle_02_replacement"} for case in CASES]
    _write(
        state / "proposals" / "raw-proposals.json",
        json.dumps({"count": len(proposals), "proposals": proposals}, indent=2, sort_keys=True)
        + "\n",
    )


def _invalidate_previous_evidence(out: Path) -> None:
    state = out / ".state"
    for receipt_name in ("oracle-receipt.json", "host-oracle-receipt.json"):
        receipt = state / receipt_name
        if not receipt.is_file():
            continue
        suffix = _source_hash(receipt).removeprefix("sha256:")[:16]
        archive = state / "invalidated" / suffix
        archive.mkdir(parents=True, exist_ok=True)
        shutil.copy2(receipt, archive / receipt.name)
        manifest = state / "materialization-manifest.json"
        if manifest.is_file():
            shutil.copy2(manifest, archive / manifest.name)
        _write(
            archive / "invalidation.json",
            json.dumps(
                {
                    "reason": "owner_or_artifact_change_requires_complete_regeneration",
                    "prior_receipt_hash": _source_hash(receipt),
                    "required_state": "planned",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        receipt.unlink()


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    del force
    _validate_output_root(out)
    if len(CASES) != 80 or not MIN_ROOTS <= len(CASES) <= MAX_ROOTS:
        _fail("hard_rule_count_failed", str(len(CASES)))
    proposed = {case.task_id for case in CASES}
    collisions = sorted(proposed & _existing_ids(out))
    if collisions:
        _fail("duplicate_task", ",".join(collisions))
    _invalidate_previous_evidence(out)
    out.mkdir(parents=True, exist_ok=True)
    _write_source_manifests(out)
    for existing in sorted(
        path for path in out.iterdir() if path.is_dir() and path.name != ".state"
    ):
        provenance_path = existing / ".meta/provenance.json"
        if not provenance_path.is_file():
            _fail("generator_output_drift", f"refusing unowned root {existing}")
        provenance = json.loads(provenance_path.read_text())
        if provenance.get("family_id") != FAMILY_ID:
            _fail("generator_output_drift", f"refusing foreign root {existing}")
        if existing.name not in proposed:
            shutil.rmtree(existing)
    roots = []
    for case in CASES:
        root = out / case.task_id
        files = task_named_files(root, _case_files(case))
        for relative, content in files.items():
            _write(root / relative, content)
        for stale in sorted(item for item in root.rglob("*") if item.is_file()):
            if stale.relative_to(root).as_posix() not in files:
                stale.unlink()
        roots.append(root)
    candidate_rows = [
        {
            "task_id": case.task_id,
            "root": (out / case.task_id).as_posix(),
            "tree_hash": _tree_hash(out / case.task_id),
            "status": "selected_cycle_02_replacement",
            "lineage": "replacement-new-root",
            "replaces": REJECTED_CYCLE_01_IDS[case.strategy],
        }
        for case in CASES
    ]
    _write(
        out / ".state/candidates/candidate-manifest.json",
        json.dumps(
            {
                "schema_version": "aider-expansion-candidates-v1",
                "count": 80,
                "rows": candidate_rows,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    _write(
        out / ".state/candidates/rejected-manifest.json",
        json.dumps(
            {
                "schema_version": "aider-expansion-rejected-v1",
                "count": 80,
                "rows": [
                    {
                        "task_id": old_id,
                        "status": "rejected_cycle_01_formula_bank",
                        "replacement_task_id": CASES[index].task_id,
                        "finding_ids": [
                            "AUD-DUR-002",
                            "AUD-DUR-003",
                            "AUD-DUR-004",
                            "AUD-DUR-005",
                            "AUD-DUR-006",
                            "AUD-DUR-007",
                        ],
                    }
                    for index, old_id in enumerate(REJECTED_CYCLE_01_IDS)
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    _write_controls(out)
    return tuple(roots)


def _normalized_tokens(content: str, *, keep_identifiers: bool = False) -> tuple[str, ...]:
    content = re.sub(r"/\*.*?\*/|//[^\n]*", " ", content, flags=re.S)
    content = re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\b\d+\b', " LIT ", content)
    raw = re.findall(r"[A-Za-z_]\w*|==|!=|<=|>=|&&|\|\||\+\+|--|[-+*/%<>{}()[\];,?:=.]", content)
    keywords = {
        "if",
        "else",
        "for",
        "while",
        "return",
        "class",
        "struct",
        "const",
        "auto",
        "bool",
        "int",
        "long",
        "void",
        "true",
        "false",
        "public",
        "private",
        "namespace",
        "std",
        "vector",
        "set",
        "map",
        "sort",
        "stable_sort",
        "min",
        "max",
    }
    return tuple(
        token
        if keep_identifiers or token in keywords or not re.match(r"[A-Za-z_]", token)
        else "ID"
        for token in raw
    )


def _artifact_sources(root: Path) -> dict[str, str]:
    config_path = root / ".meta/config.json"
    if config_path.is_file():
        config = json.loads(config_path.read_text())
        header = root / config["files"]["solution"][0]
        reference = root / config["files"]["example"][1]
    else:
        header = root / "task.h"
        reference = root / "candidate.cpp"
    paths = {
        "docs": root / ".docs/instructions.md",
        "header": header,
        "reference": reference,
        "visible": root / "task_visible_test.cpp",
        "hidden": root / ".meta/task_hidden_test.cpp",
        "negative": root / ".meta/negative_false_substitute.cpp",
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        _fail("generator_output_drift", f"{root}: {missing}")
    return {name: path.read_text() for name, path in paths.items()}


def _control_flow(reference: str) -> str:
    return "\n".join(
        line
        for line in reference.splitlines()
        if re.search(
            r"\b(if|else|for|while|return|sort|accumulator|witness|sample|numerator|spent|left|right|net|prefix|serial_cursor|even_total|odd_total|previous_sample)\b",
            line,
        )
    )


def _mechanism_core(reference: str) -> str:
    start = reference.find("  Big accumulator = 0;")
    end = reference.find("  if (!arithmetic_ok", start)
    if start < 0 or end < 0:
        _fail("mechanism_contract_mismatch", "reference mechanism boundaries missing")
    return reference[start:end]


def _dimension_material(root: Path) -> dict[str, str]:
    source = _artifact_sources(root)
    negative_delta = "\n".join(
        line
        for line in source["negative"].splitlines()
        if line not in source["reference"].splitlines()
    )
    return {
        "public_api": source["header"] + "\n" + source["docs"],
        "owned_state_algorithm": _mechanism_core(source["reference"]),
        "mutation_selection_rules": source["docs"] + "\n" + _control_flow(source["reference"]),
        "invalid_boundary_behavior": source["docs"] + "\n" + source["hidden"],
        "reference_control_flow": _control_flow(source["reference"]),
        "deterministic_oracle": source["visible"] + "\n" + source["hidden"],
        "topic_specific_negative_fixture": _control_flow(_mechanism_core(source["negative"]))
        + "\n"
        + negative_delta
        + "\n"
        + source["hidden"],
    }


def _dimension_features(root: Path) -> dict[str, set[tuple[str, ...]]]:
    material = _dimension_material(root)
    result: dict[str, set[tuple[str, ...]]] = {}
    for dimension, content in material.items():
        tokens = _normalized_tokens(
            content,
            keep_identifiers=dimension
            in {
                "public_api",
                "mutation_selection_rules",
                "invalid_boundary_behavior",
                "deterministic_oracle",
            },
        )
        width = 5 if len(tokens) >= 5 else max(1, len(tokens))
        result[dimension] = {
            tokens[index : index + width] for index in range(max(1, len(tokens) - width + 1))
        }
    return result


def _feature_pair_decision(
    left_features: dict[str, set[tuple[str, ...]]],
    right_features: dict[str, set[tuple[str, ...]]],
) -> dict[str, object]:
    decisions: dict[str, object] = {}
    for dimension in HARD_RULE_DIMENSIONS:
        a, b = left_features[dimension], right_features[dimension]
        union = a | b
        overlap = len(a & b) / len(union) if union else 1.0
        distinct = bool(a ^ b) and overlap < 0.995
        decisions[dimension] = {
            "overlap": overlap,
            "distinct": distinct,
            "left_feature_count": len(a),
            "right_feature_count": len(b),
        }
    decisions["pass"] = all(row["distinct"] for row in decisions.values())
    return decisions


def _pair_decision(left: Path, right: Path) -> dict[str, object]:
    return _feature_pair_decision(_dimension_features(left), _dimension_features(right))


def _behavior_vector(case: DurationExpansionCase, *, opposite: bool = False) -> tuple[int, ...]:
    vector: list[int] = []
    for limit in (0, 1, 3, 7, 10):
        value, witness, accepted, rejected, _ = _evaluate_records(
            case, _base_records(boundary=True), limit=limit, opposite=opposite
        )
        vector.extend((value, witness, accepted, rejected))
    large = _evaluate_records(
        case, _large_records(case), limit=9223372036854775807, opposite=opposite
    )
    vector.extend(large[:4])
    group = case.strategy // 10
    for reducer in range(10):
        synthetic = replace(case, strategy=group * 10 + reducer)
        value, witness, _, _, _ = _evaluate_records(
            synthetic, _base_records(boundary=True), limit=5, opposite=opposite
        )
        vector.extend((value, witness))
    variant = case.strategy % 10
    for samples in ((0,), (1, 1), (1, 2), (0, 3, 1), (5, 0, 5)):
        for limit in (0, 1, 2, 4):
            if variant == 0:
                reduced = (sum(samples), -1)
            elif variant == 1:
                reduced = ((sum(samples) + len(samples) - 1) // len(samples), len(samples))
            elif variant == 2:
                quotient, remainder = divmod(sum(samples), limit + 1)
                reduced = (remainder, quotient)
            elif variant == 3:
                peak = max(samples)
                reduced = (peak, samples.index(peak))
            elif variant == 4:
                selected = [index for index, sample in enumerate(samples) if sample >= limit]
                reduced = (len(selected), selected[0] if selected else -1)
            elif variant == 5:
                positive = [sample for sample in samples if sample > 0]
                reduced = (sum(positive), len(positive))
            elif variant == 6:
                prefix, crossing = 0, -1
                for index, sample in enumerate(samples):
                    prefix += sample
                    if crossing < 0 and prefix >= limit:
                        crossing = index
                reduced = (prefix, crossing)
            elif variant == 7:
                total, crossing = 0, -1
                for index, sample in enumerate(samples):
                    total += min(sample, limit - total)
                    if total == limit and crossing < 0:
                        crossing = index
                reduced = (total, crossing)
            elif variant == 8:
                runs, previous, last = 0, None, -1
                for index, sample in enumerate(samples):
                    if previous is None or sample != previous:
                        runs, previous, last = runs + 1, sample, index
                reduced = (runs, last)
            else:
                even, odd = sum(samples[::2]), sum(samples[1::2])
                reduced = (abs(even - odd), 0 if even >= odd else 1)
            vector.extend(reduced)
    return tuple(vector)


def _hard_rule_matrix(out: Path) -> dict[str, object]:
    roots = [out / case.task_id for case in CASES]
    features = {root.name: _dimension_features(root) for root in roots}
    behavior = {case.task_id: _behavior_vector(case) for case in CASES}
    pairs = []
    for left, right in itertools.combinations(roots, 2):
        dimensions = _feature_pair_decision(features[left.name], features[right.name])
        if not dimensions["pass"]:
            failed = [name for name in HARD_RULE_DIMENSIONS if not dimensions[name]["distinct"]]
            _fail("duplicate_family", f"{left.name}/{right.name}: {failed}")
        behavior_distinct = behavior[left.name] != behavior[right.name]
        if not behavior_distinct:
            _fail("duplicate_family", f"{left.name}/{right.name}: behavior_vector")
        pairs.append(
            {
                "left": left.name,
                "right": right.name,
                "dimensions": dimensions,
                "behavior_distinct": True,
                "left_behavior_hash": _sha_bytes(json.dumps(behavior[left.name]).encode()),
                "right_behavior_hash": _sha_bytes(json.dumps(behavior[right.name]).encode()),
            }
        )
    return {
        "status": "pending_execution",
        "root_count": len(roots),
        "pair_count": len(pairs),
        "expected_pair_count": len(roots) * (len(roots) - 1) // 2,
        "dimensions": list(HARD_RULE_DIMENSIONS),
        "pairs": pairs,
    }


def _control_files(
    case: DurationExpansionCase,
    *,
    domain: bool = False,
    constants: bool = False,
    opposite: bool = False,
    superficial: bool = False,
) -> dict[str, str]:
    header = _header(case)
    reference = _reference(case, opposite=opposite, policy_limit=0 if constants else None)
    visible = _test_source(case, opposite=opposite)
    hidden = _test_source(case, hidden=True, opposite=opposite)
    docs = _instructions(case)
    if domain:
        replacements = (
            (_pascal(case.task_id), "RenamedDurationDomain"),
            (case.title, "Renamed duration domain"),
            ("entry", "record"),
            ("Entry", "Record"),
        )
        for old, new in replacements:
            header = header.replace(old, new)
            reference = reference.replace(old, new)
            visible = visible.replace(old, new)
            hidden = hidden.replace(old, new)
            docs = docs.replace(old, new)
    if constants:
        docs = docs.replace("negative `limit`", "limit below zero")
    if superficial:
        reference = reference.replace(
            "  Report report{true, 0, -1, 0, 0, {}};",
            "  static_cast<void>(0);\n  Report report{true, 0, -1, 0, 0, {}};",
        )
        docs += "\nEquivalent implementations may include harmless no-op statements.\n"
    negative = reference.replace(
        "  report.value = accumulator;",
        "  report.value = accumulator;\n  ++report.accepted;",
    )
    return {
        ".docs/instructions.md": docs,
        "task.h": header,
        "candidate.cpp": reference,
        ".meta/negative_false_substitute.cpp": negative,
        "task_visible_test.cpp": visible,
        ".meta/task_hidden_test.cpp": hidden,
        "CMakeLists.txt": CMAKE,
    }


def _write_controls(out: Path) -> None:
    specs = {
        "domain-identifier-renamed-clone": (CASES[0], {"domain": True}),
        "constants-policy-clone": (CASES[1], {"constants": True}),
        "opposite-end-selection-clone": (CASES[10], {"opposite": True}),
        "superficial-token-difference-clone": (CASES[20], {"superficial": True}),
    }
    manifest: dict[str, object] = {
        "schema_version": "aider-duration-expansion-controls-v1",
        "controls": {},
    }
    for name, (case, kwargs) in specs.items():
        root = out / ".state/hard-rule-controls" / name
        files = _control_files(case, **kwargs)
        for relative, content in files.items():
            _write(root / relative, content)
        base = out / case.task_id
        base_sources = _artifact_sources(base)
        changed = []
        mapping = {
            ".docs/instructions.md": "docs",
            "task.h": "header",
            "candidate.cpp": "reference",
            ".meta/negative_false_substitute.cpp": "negative",
            "task_visible_test.cpp": "visible",
            ".meta/task_hidden_test.cpp": "hidden",
        }
        for relative, key in mapping.items():
            if files[relative] != base_sources[key]:
                changed.append(relative)
        if not changed:
            _fail("adversarial_control_noop", name)
        manifest["controls"][name] = {
            "base_task_id": case.task_id,
            "changed_files": sorted(changed),
            "behavior_mode": "opposite" if kwargs.get("opposite") else "base",
            "expected_build": "pass",
            "expected_behavior": "pass",
            "expected_production_screen": "duplicate_family",
        }
    _write(
        out / ".state/hard-rule-controls/manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )


def _screen_controls(out: Path) -> dict[str, object]:
    manifest = json.loads((out / ".state/hard-rule-controls/manifest.json").read_text())
    cases = {case.task_id: case for case in CASES}
    results = {}
    for name, row in manifest["controls"].items():
        base = out / row["base_task_id"]
        control = out / ".state/hard-rule-controls" / name
        decisions = _pair_decision(base, control)
        case = cases[row["base_task_id"]]
        base_behavior = _behavior_vector(case)
        control_behavior = _behavior_vector(case, opposite=row["behavior_mode"] == "opposite")
        behavior_equal = base_behavior == control_behavior
        contract_duplicate = not decisions["pass"]
        if not behavior_equal and not contract_duplicate:
            _fail("adversarial_control_not_rejected", name)
        rejection_basis = []
        if behavior_equal:
            rejection_basis.append("behavior_vector_equal")
        if contract_duplicate:
            rejection_basis.append("contract_dimension_duplicate")
        results[name] = {
            "changed": True,
            "changed_files": row["changed_files"],
            "dimensions": decisions,
            "production_evaluator": "rejected:duplicate_family",
            "behavior_vector_equal": behavior_equal,
            "base_behavior_hash": _sha_bytes(json.dumps(base_behavior).encode()),
            "control_behavior_hash": _sha_bytes(json.dumps(control_behavior).encode()),
            "rejection_basis": rejection_basis,
        }
    return results


def _semantic_tokens(content: str) -> tuple[str, ...]:
    return _normalized_tokens(content, keep_identifiers=False)


def _semantic_holdout_screen(
    out: Path, holdout_root: Path = DEFAULT_HOLDOUT_ROOT
) -> dict[str, object]:
    available = (
        sorted(path for path in holdout_root.iterdir() if path.is_dir())
        if holdout_root.is_dir()
        else []
    )
    if {path.name for path in available} != OFFICIAL_AIDER_CPP_HOLDOUTS:
        _fail("semantic_screen_not_completed", f"expected exact 26-root holdout at {holdout_root}")
    holdout_features = {}
    for holdout in available:
        content = "\n".join(
            path.read_text(errors="ignore")
            for path in sorted(holdout.rglob("*"))
            if path.is_file() and path.stat().st_size < 1_000_000
        )
        tokens = _semantic_tokens(content)
        holdout_features[holdout.name] = {
            tokens[index : index + 9] for index in range(max(1, len(tokens) - 8))
        }
    comparisons = 0
    strongest = {"overlap": 0.0, "candidate": None, "holdout": None}
    for case in CASES:
        candidate = _semantic_tokens("\n".join(_artifact_sources(out / case.task_id).values()))
        candidate_set = {
            candidate[index : index + 9] for index in range(max(1, len(candidate) - 8))
        }
        for holdout in available:
            holdout_set = holdout_features[holdout.name]
            overlap = (
                len(candidate_set & holdout_set) / len(candidate_set | holdout_set)
                if candidate_set | holdout_set
                else 0.0
            )
            comparisons += 1
            if overlap > strongest["overlap"]:
                strongest = {"overlap": overlap, "candidate": case.task_id, "holdout": holdout.name}
            if overlap >= 0.80:
                _fail("benchmark_content_overlap", f"{case.task_id}/{holdout.name}: {overlap}")
    return {
        "status": "pass",
        "holdout_root": holdout_root.as_posix(),
        "holdout_root_count": len(available),
        "comparison_count": comparisons,
        "normalizer": "duration-expansion-role-aware-9gram-v1",
        "strongest": strongest,
    }


def _role_fingerprint(root: Path) -> dict[str, str] | None:
    config_path = root / ".meta/config.json"
    if not config_path.is_file():
        return None
    try:
        config = json.loads(config_path.read_text())
        files = config["files"]
        solution = [root / item for item in files.get("solution", [])]
        examples = [root / item for item in files.get("example", [])]
        tests = [root / item for item in files.get("test", [])]
    except (KeyError, TypeError, json.JSONDecodeError):
        return None
    docs = sorted((root / ".docs").glob("*.md")) if (root / ".docs").is_dir() else []
    hidden = root / ".meta/task_hidden_test.cpp"
    if hidden.is_file():
        tests.append(hidden)
    roles = {
        "docs": docs,
        "api": solution[:1],
        "starter": solution[1:],
        "reference": examples,
        "tests": tests,
    }
    result = {}
    for role, paths in roles.items():
        content = "\n".join(path.read_text(errors="ignore") for path in paths if path.is_file())
        tokens = _normalized_tokens(content, keep_identifiers=False)
        result[role] = _sha_bytes(" ".join(tokens).encode())
    return result


def _contract_signature(root: Path) -> frozenset[int]:
    config_path = root / ".meta/config.json"
    paths: list[Path] = []
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text())
            files = config["files"]
            for role in ("solution", "example", "test"):
                paths.extend(root / item for item in files.get(role, []))
        except (KeyError, TypeError, json.JSONDecodeError):
            return frozenset()
    else:
        paths.extend(
            (
                root / "task.h",
                root / "candidate.cpp",
                root / "task_visible_test.cpp",
            )
        )
    if (root / ".docs").is_dir():
        paths.extend(sorted((root / ".docs").glob("*.md")))
    hidden = root / ".meta/task_hidden_test.cpp"
    if hidden.is_file():
        paths.append(hidden)
    content = "\n".join(path.read_text(errors="ignore") for path in paths if path.is_file())
    tokens = _normalized_tokens(content, keep_identifiers=False)
    width = 5 if len(tokens) >= 5 else max(1, len(tokens))
    hashes = {
        int.from_bytes(
            hashlib.blake2b(
                " ".join(tokens[index : index + width]).encode(), digest_size=8
            ).digest(),
            "big",
        )
        for index in range(max(1, len(tokens) - width + 1))
    }
    return frozenset(sorted(hashes)[:64])


def _contract_similarity(left: frozenset[int], right: frozenset[int]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def _cross_tree_semantic_screen(out: Path) -> dict[str, object]:
    candidate = {case.task_id: _role_fingerprint(out / case.task_id) for case in CASES}
    candidate_contracts = {case.task_id: _contract_signature(out / case.task_id) for case in CASES}
    if any(value is None for value in candidate.values()):
        _fail("cross_tree_semantic_screen_incomplete", "candidate role fingerprint")
    sources = (
        ("legacy", LEGACY_ROOT),
        ("reverify", REVERIFY_ROOT),
        ("other_expansion", EXPANSION_ROOT),
    )
    reports = {}
    for name, source_root in sources:
        existing = []
        if source_root.is_dir():
            for config in sorted(source_root.rglob(".meta/config.json")):
                if ".state" in config.parts:
                    continue
                root = config.parent.parent
                if root == out or out in root.parents:
                    continue
                fingerprint = _role_fingerprint(root)
                if fingerprint is not None:
                    existing.append((root, fingerprint, _contract_signature(root)))
        strongest = {"equal_role_count": 0, "candidate": None, "existing": None}
        strongest_contract = {"similarity": 0.0, "candidate": None, "existing": None}
        comparisons = 0
        for task_id, left in candidate.items():
            assert left is not None
            for root, right, right_contract in existing:
                comparisons += 1
                equal_roles = sum(left[role] == right[role] for role in left)
                if equal_roles > strongest["equal_role_count"]:
                    strongest = {
                        "equal_role_count": equal_roles,
                        "candidate": task_id,
                        "existing": root.as_posix(),
                    }
                if equal_roles >= 4:
                    _fail("cross_tree_semantic_duplicate", f"{task_id}/{root}: {equal_roles} roles")
                similarity = _contract_similarity(candidate_contracts[task_id], right_contract)
                if similarity > strongest_contract["similarity"]:
                    strongest_contract = {
                        "similarity": similarity,
                        "candidate": task_id,
                        "existing": root.as_posix(),
                    }
                if similarity >= 0.95:
                    _fail(
                        "cross_tree_contract_near_duplicate",
                        f"{task_id}/{root}: {similarity}",
                    )
        reports[name] = {
            "existing_root_count": len(existing),
            "comparison_count": comparisons,
            "role_normalizer": "identifier-and-literal-neutral-role-hash-v1",
            "contract_normalizer": "identifier-and-literal-neutral-bottom-64-five-gram-v1",
            "strongest": strongest,
            "strongest_contract": strongest_contract,
            "status": "pass",
        }
    clone_base = out / CASES[20].task_id
    clone = out / ".state/hard-rule-controls/superficial-token-difference-clone"
    clone_similarity = _contract_similarity(
        _contract_signature(clone_base), _contract_signature(clone)
    )
    if clone_similarity < 0.95:
        _fail("cross_tree_contract_control_not_rejected", str(clone_similarity))
    return {
        "status": "pass",
        "sources": reports,
        "adversarial_contract_clone": {
            "base_task_id": CASES[20].task_id,
            "control": "superficial-token-difference-clone",
            "similarity": clone_similarity,
            "threshold": 0.95,
            "decision": "rejected:cross_tree_contract_near_duplicate",
        },
    }


def _role_and_prompt_check(root: Path) -> dict[str, str]:
    config = json.loads((root / ".meta/config.json").read_text())
    solution = config["files"]["solution"]
    examples = config["files"]["example"]
    if solution != [f"{root.name}.h", f"{root.name}.cpp"] or examples != [
        ".meta/example.h",
        ".meta/example.cpp",
    ]:
        _fail("reference_map_failed", root.name)
    task = load_task(root)
    prompt = build_prompt(task)
    forbidden = (
        ".meta/example",
        "task_hidden_test",
        "CMakeLists.txt",
        "provenance.json",
        "negative_false_substitute",
        "negative_transform",
    )
    if any(item in prompt for item in forbidden):
        _fail("prompt_boundary_failed", root.name)
    answer = build_assistant_response(task, load_example_files_from_config(root))
    if (
        answer.count("```") != 4
        or not answer.startswith(f"{root.name}.h\n```")
        or f"{root.name}.cpp\n```" not in answer
    ):
        _fail("whole_format_failed", root.name)
    return {
        "prompt_hash": _sha_bytes(prompt.encode()),
        "answer_hash": _sha_bytes(answer.encode()),
        "header_hash": _source_hash(root / solution[0]),
        "starter_hash": _source_hash(root / solution[1]),
        "reference_header_hash": _source_hash(root / examples[0]),
        "reference_source_hash": _source_hash(root / examples[1]),
        "visible_test_hash": _source_hash(root / "task_visible_test.cpp"),
        "hidden_test_hash": _source_hash(root / ".meta/task_hidden_test.cpp"),
        "metadata_hash": _source_hash(root / ".meta/config.json"),
        "provenance_hash": _source_hash(root / ".meta/provenance.json"),
    }


def verify_core(out: Path = DEFAULT_OUT) -> dict[str, object]:
    _validate_output_root(out)
    roots = [out / case.task_id for case in CASES]
    if any(not root.is_dir() for root in roots):
        _fail("generator_output_drift", "missing generated root")
    actual = {path.name for path in out.iterdir() if path.is_dir() and path.name != ".state"}
    if actual != {case.task_id for case in CASES}:
        _fail("generator_output_drift", "unexpected generated roots")
    if {case.task_id for case in CASES} & _existing_ids(out):
        _fail("duplicate_task", "cross-tree task ID collision")
    task_rows = []
    prompt_hashes, answer_hashes, reference_hashes = set(), set(), set()
    for case, root in zip(CASES, roots, strict=True):
        evidence = _role_and_prompt_check(root)
        for key, seen in (
            ("prompt_hash", prompt_hashes),
            ("answer_hash", answer_hashes),
            ("reference_source_hash", reference_hashes),
        ):
            if evidence[key] in seen:
                _fail("duplicate_family", f"duplicate {key}: {case.task_id}")
            seen.add(evidence[key])
        task_rows.append(
            {
                "task_id": case.task_id,
                "tree_hash": _tree_hash(root),
                "primary_core_objective": "achieved",
                "disposition": "retain",
                "status": "implemented",
                **evidence,
            }
        )
    hard_rule = _hard_rule_matrix(out)
    controls = _screen_controls(out)
    holdout = _semantic_holdout_screen(out)
    cross_tree = _cross_tree_semantic_screen(out)
    manifest = {
        "schema_version": "aider-duration-expansion-materialization-v1",
        "family_id": FAMILY_ID,
        "count_plan_cell": COUNT_PLAN_CELL,
        "task_count": len(roots),
        "owner_hash": _owner_hash(),
        "family_tree_hash": _tree_hash(out),
        "root_hash_ledger_hash": _sha_bytes(
            "\n".join(row["tree_hash"] for row in task_rows).encode()
        ),
        "status": "implemented",
        "selected_prompt_sequence": [PROMPT_DESIGN, PROMPT_IMPLEMENT],
        "tasks": task_rows,
        "screen": {
            "prompt_boundary": "pass",
            "reference_mapping": "pass",
            "unique_task_id": "pass",
            "unique_prompt_hash": "pass",
            "unique_answer_hash": "pass",
            "unique_reference_hash": "pass",
            "hard_rule": hard_rule,
            "adversarial_controls": controls,
            "benchmark_contamination": "pass",
            "semantic_holdout": holdout,
            "cross_tree_semantic": cross_tree,
        },
    }
    _write(
        out / ".state/materialization-manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
    )
    _write(
        out / ".state/candidates/selected-manifest.json",
        json.dumps(
            {
                "schema_version": "aider-expansion-selected-v1",
                "count": 80,
                "status": "pending_execution",
                "rows": [
                    {
                        "task_id": case.task_id,
                        "disposition": "retain",
                        "tree_hash": _tree_hash(out / case.task_id),
                    }
                    for case in CASES
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    _write(
        out / ".state/candidates/rejected-manifest.json",
        json.dumps(
            {
                "schema_version": "aider-expansion-rejected-v1",
                "count": 80,
                "rows": [
                    {
                        "task_id": old_id,
                        "status": "rejected_cycle_01_formula_bank",
                        "replacement_task_id": CASES[index].task_id,
                    }
                    for index, old_id in enumerate(REJECTED_CYCLE_01_IDS)
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return manifest


def _deterministic_archive(out: Path, destination: Path) -> str:
    with tarfile.open(destination, "w") as archive:
        sources: list[tuple[Path, Path]] = []
        for case in sorted(CASES, key=lambda item: item.task_id):
            root = out / case.task_id
            sources.extend(
                (path, Path(case.task_id) / path.relative_to(root))
                for path in sorted(item for item in root.rglob("*") if item.is_file())
            )
        controls = out / ".state/hard-rule-controls"
        sources.extend(
            (path, Path(".hard-rule-controls") / path.relative_to(controls))
            for path in sorted(item for item in controls.rglob("*") if item.is_file())
        )
        for path, relative in sources:
            data = path.read_bytes()
            info = tarfile.TarInfo(relative.as_posix())
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(data))
    return _source_hash(destination)


def _host_command(command: list[str], *, detail: str) -> str:
    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    if result.returncode:
        _fail("host_verify_failed", f"{detail}: {result.stdout[-4000:]}")
    return result.stdout


def _host_tool_version(command: list[str]) -> str:
    return _host_command(command, detail="tool version").splitlines()[0].strip()


def _host_ctest_count(build_dir: Path) -> int:
    listed = _host_command(
        ["ctest", "--test-dir", str(build_dir), "-N"], detail=f"ctest discovery {build_dir}"
    )
    match = re.search(r"Total Tests: (\d+)", listed)
    if match is None:
        _fail("test_discovery_failed", str(build_dir))
    return int(match.group(1))


def _host_build(root: Path, source: Path, build_dir: Path, *, sanitizer: bool = False) -> int:
    root = root.resolve()
    source = source.resolve()
    build_dir = build_dir.resolve()
    configure = [
        "cmake",
        "-S",
        str(root),
        "-B",
        str(build_dir),
        "-G",
        "Unix Makefiles",
        "-DCMAKE_CXX_COMPILER=c++",
        f"-DTASK_SOURCE={source}",
    ]
    if sanitizer:
        configure += [
            "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer",
            "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined",
        ]
    _host_command(configure, detail=f"configure {build_dir}")
    _host_command(
        ["cmake", "--build", str(build_dir), "--parallel", "2"], detail=f"build {build_dir}"
    )
    count = _host_ctest_count(build_dir)
    if count <= 0:
        _fail("zero_tests", str(build_dir))
    return count


def _host_ctest_run(build_dir: Path, *, expect_failure: bool = False) -> int:
    result = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "--output-on-failure"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode and not expect_failure:
        _fail("host_verify_failed", f"ctest {build_dir}: {result.stdout[-4000:]}")
    return result.returncode


def verify_host(out: Path = DEFAULT_OUT) -> dict[str, object]:
    """Owner-designated host verification: the same fresh normal and ASan/UBSan
    reference builds, negative-fixture rejections, and coherent-control builds as
    the network-disabled Docker runner, executed on the host toolchain.  The
    receipt is `host_verify` evidence only; it is not `docker_sanity` and cannot
    support `local_family_verified`."""
    manifest = verify_core(out)
    if shutil.which("cmake") is None or shutil.which("c++") is None or shutil.which("ctest") is None:
        _fail(
            "host_verify_not_completed",
            "host verification requires cmake, ctest, and c++ on PATH",
        )
    compiler = _host_tool_version(["c++", "--version"])
    cmake_version = _host_tool_version(["cmake", "--version"])
    with tempfile.TemporaryDirectory(prefix="duration-expansion-host-") as temporary:
        work = Path(temporary)
        counts: dict[str, dict[str, int]] = {}
        negatives: dict[str, dict[str, object]] = {}
        for case in CASES:
            root = out / case.task_id
            modes = {}
            for mode, sanitizer in (("normal", False), ("sanitizer", True)):
                build_dir = work / f"{case.task_id}-{mode}"
                count = _host_build(
                    root, root / ".meta/example.cpp", build_dir, sanitizer=sanitizer
                )
                _host_ctest_run(build_dir)
                modes[mode] = count
            if modes["normal"] != modes["sanitizer"]:
                _fail("sanitizer_test_count_mismatch", case.task_id)
            counts[case.task_id] = modes
            for kind, relative in (
                ("reducer", ".meta/negative_false_substitute.cpp"),
                ("transform", ".meta/negative_transform.cpp"),
            ):
                build_dir = work / f"{case.task_id}-negative-{kind}"
                count = _host_build(root, root / relative, build_dir)
                status = _host_ctest_run(build_dir, expect_failure=True)
                negatives[f"{case.task_id}:{kind}"] = {
                    "task_id": case.task_id,
                    "kind": kind,
                    "compiled": True,
                    "discovered_tests": count,
                    "ctest_exit": status,
                    "rejected_by_executed_tests": status != 0,
                }
        if any(not row["rejected_by_executed_tests"] for row in negatives.values()):
            _fail("negative_fixture_not_rejected", "host negative passed its tests")
        controls: dict[str, dict[str, object]] = {}
        semantic_controls = _screen_controls(out)
        for name in semantic_controls:
            root = out / ".state/hard-rule-controls" / name
            build_dir = work / f"control-{name}"
            count = _host_build(root, root / "candidate.cpp", build_dir)
            _host_ctest_run(build_dir)
            controls[name] = {
                "compiled": True,
                "tests_passed": True,
                "discovered_tests": count,
                "production_evaluator": semantic_controls[name]["production_evaluator"],
            }
        receipt = {
            "schema_version": "aider-duration-expansion-host-verify-v1",
            "evidence_class": "host_verify",
            "locked_oracle": False,
            "docker_sanity": "not_completed (campaign gate: host verify only)",
            "owner_hash": _owner_hash(),
            "family_tree_hash": manifest["family_tree_hash"],
            "compiler": compiler,
            "cmake": cmake_version,
            "commands": {
                "normal": "fresh Unix Makefiles reference build and ctest on the host",
                "sanitizer": "fresh ASan/UBSan Unix Makefiles reference build and ctest on the host",
                "negative": "two strict transform/reducer misconception builds followed by executed-test rejection",
                "controls": "strict build and passing behavior tests followed by production duplicate-family rejection",
            },
            "test_counts": counts,
            "topic_negative_execution": negatives,
            "adversarial_control_execution": controls,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        receipt_path = out / ".state/host-oracle-receipt.json"
        _write(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        manifest_path = out / ".state/materialization-manifest.json"
        current = json.loads(manifest_path.read_text())
        current["status"] = "host_verify_passed"
        current["hard_rule_status"] = "pass"
        current["host_oracle_receipt"] = ".state/host-oracle-receipt.json"
        current["host_oracle_receipt_hash"] = _source_hash(receipt_path)
        current["host_evidence_class"] = "host_verify"
        current["docker_sanity"] = "not_completed (campaign gate: host verify only)"
        current["screen"]["hard_rule"]["status"] = "pass"
        current["screen"]["hard_rule"]["topic_negative_execution"] = negatives
        current["screen"]["hard_rule"]["adversarial_control_execution"] = controls
        _write(manifest_path, json.dumps(current, indent=2, sort_keys=True) + "\n")
        selected = json.loads((out / ".state/candidates/selected-manifest.json").read_text())
        selected["status"] = "host_verify_passed"
        for row in selected["rows"]:
            row["status"] = "host_verify_passed"
        _write(
            out / ".state/candidates/selected-manifest.json",
            json.dumps(selected, indent=2, sort_keys=True) + "\n",
        )
        return receipt


def verify_docker(out: Path = DEFAULT_OUT, image: str = SANITY_IMAGE) -> dict[str, object]:
    manifest = verify_core(out)
    if shutil.which("docker") is None:
        _fail("docker_sanity_not_completed", "docker executable unavailable")
    inspect = subprocess.run(
        ["docker", "image", "inspect", image, "--format", "{{.Id}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if inspect.returncode:
        _fail("docker_sanity_not_completed", inspect.stderr.strip())
    image_id = inspect.stdout.strip()
    with tempfile.TemporaryDirectory(prefix="duration-expansion-docker-") as temporary:
        temp = Path(temporary)
        archive = temp / "family.tar"
        results = temp / "results"
        results.mkdir()
        archive_hash = _deterministic_archive(out, archive)
        runner = r"""set -eu
mkdir -p /tmp/family
tar -xf /input/family.tar -C /tmp/family
: > /result/counts.tsv
: > /result/negative.tsv
: > /result/controls.tsv
c++ --version | head -1 > /result/compiler.txt
cmake --version | head -1 > /result/cmake.txt
for root in /tmp/family/*; do
  task=$(basename "$root")
  test "$task" != ".hard-rule-controls" || continue
  for mode in normal sanitizer; do
    build="/tmp/build-${task}-${mode}"
    if test "$mode" = sanitizer; then
      cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp" "-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer" "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"
    else
      cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/.meta/example.cpp"
    fi
    cmake --build "$build" --parallel 2
    count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
    test -n "$count" && test "$count" -gt 0
    ctest --test-dir "$build" --output-on-failure
    printf '%s\t%s\t%s\n' "$task" "$mode" "$count" >> /result/counts.tsv
  done
  for negative_kind in reducer transform; do
    if test "$negative_kind" = reducer; then negative_source="$root/.meta/negative_false_substitute.cpp"; else negative_source="$root/.meta/negative_transform.cpp"; fi
    build="/tmp/build-${task}-negative-${negative_kind}"
    cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$negative_source"
    cmake --build "$build" --parallel 2
    count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
    set +e; ctest --test-dir "$build" --output-on-failure; status=$?; set -e
    test -n "$count" && test "$count" -gt 0 && test "$status" -ne 0
    printf '%s\t%s\t%s\t%s\n' "$task" "$negative_kind" "$count" "$status" >> /result/negative.tsv
  done
done
for root in /tmp/family/.hard-rule-controls/*; do
  test -d "$root" || continue
  name=$(basename "$root"); build="/tmp/build-control-${name}"
  cmake -S "$root" -B "$build" -G "Unix Makefiles" -DCMAKE_CXX_COMPILER=c++ -DTASK_SOURCE="$root/candidate.cpp"
  cmake --build "$build" --parallel 2
  count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: \([0-9][0-9]*\).*/\1/p')
  ctest --test-dir "$build" --output-on-failure
  printf '%s\t%s\n' "$name" "$count" >> /result/controls.tsv
done
sha256sum /input/family.tar | awk '{print "sha256:" $1}' > /result/archive.sha256
"""
        command = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--mount",
            f"type=bind,src={archive},dst=/input/family.tar,readonly",
            "--mount",
            f"type=bind,src={results},dst=/result",
            image,
            "sh",
            "-lc",
            runner,
        ]
        run = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if run.returncode:
            _write(out / ".state/docker-failure.log", run.stdout[-20000:])
            _fail("docker_sanity_failed", run.stdout[-6000:])
        mounted_hash = (results / "archive.sha256").read_text().strip()
        if mounted_hash != archive_hash:
            _fail("grader_mount_hash_mismatch", f"owner={archive_hash} docker={mounted_hash}")
        counts: dict[str, dict[str, int]] = {}
        for line in (results / "counts.tsv").read_text().splitlines():
            task_id, mode, raw = line.split("\t")
            counts.setdefault(task_id, {})[mode] = int(raw)
        expected = {case.task_id for case in CASES}
        if set(counts) != expected:
            _fail("test_discovery_failed", f"expected {len(expected)}, got {len(counts)}")
        for task_id, modes in counts.items():
            if modes.get("normal", 0) <= 0 or modes.get("normal") != modes.get("sanitizer"):
                _fail("sanitizer_test_count_mismatch", task_id)
        negatives = {}
        for line in (results / "negative.tsv").read_text().splitlines():
            task_id, kind, raw_count, raw_status = line.split("\t")
            negatives[f"{task_id}:{kind}"] = {
                "task_id": task_id,
                "kind": kind,
                "compiled": True,
                "discovered_tests": int(raw_count),
                "ctest_exit": int(raw_status),
                "rejected_by_executed_tests": int(raw_status) != 0,
            }
        expected_negatives = {
            f"{task_id}:{kind}" for task_id in expected for kind in ("reducer", "transform")
        }
        if set(negatives) != expected_negatives or any(
            not row["rejected_by_executed_tests"] for row in negatives.values()
        ):
            _fail("negative_fixture_not_rejected", "incomplete or passing negative")
        controls = {}
        semantic_controls = _screen_controls(out)
        for line in (results / "controls.tsv").read_text().splitlines():
            name, raw_count = line.split("\t")
            controls[name] = {
                "compiled": True,
                "tests_passed": True,
                "discovered_tests": int(raw_count),
                "production_evaluator": semantic_controls[name]["production_evaluator"],
            }
        if set(controls) != set(semantic_controls) or any(
            row["discovered_tests"] <= 0 for row in controls.values()
        ):
            _fail("adversarial_control_execution_failed", "control receipt mismatch")
        receipt = {
            "schema_version": "aider-duration-expansion-docker-sanity-v1",
            "evidence_class": "docker_sanity",
            "locked_oracle": False,
            "network_policy": "none",
            "image": image,
            "image_id": image_id,
            "archive_hash": archive_hash,
            "mounted_archive_hash": mounted_hash,
            "owner_hash": _owner_hash(),
            "family_tree_hash": manifest["family_tree_hash"],
            "compiler": (results / "compiler.txt").read_text().strip(),
            "cmake": (results / "cmake.txt").read_text().strip(),
            "commands": {
                "normal": "fresh Unix Makefiles reference build and ctest",
                "sanitizer": "fresh ASan/UBSan Unix Makefiles reference build and ctest",
                "negative": "two strict transform/reducer misconception builds followed by executed-test rejection",
                "controls": "strict build and passing behavior tests followed by production duplicate-family rejection",
            },
            "test_counts": counts,
            "topic_negative_execution": negatives,
            "adversarial_control_execution": controls,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        receipt_path = out / ".state/oracle-receipt.json"
        _write(receipt_path, json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        manifest_path = out / ".state/materialization-manifest.json"
        current = json.loads(manifest_path.read_text())
        current["status"] = "creator_preflight_passed"
        current["hard_rule_status"] = "pass"
        current["oracle_receipt"] = ".state/oracle-receipt.json"
        current["oracle_receipt_hash"] = _source_hash(receipt_path)
        current["evidence_class"] = "docker_sanity"
        current["screen"]["hard_rule"]["status"] = "pass"
        current["screen"]["hard_rule"]["topic_negative_execution"] = negatives
        current["screen"]["hard_rule"]["adversarial_control_execution"] = controls
        _write(manifest_path, json.dumps(current, indent=2, sort_keys=True) + "\n")
        selected = json.loads((out / ".state/candidates/selected-manifest.json").read_text())
        selected["status"] = "creator_preflight_passed"
        for row in selected["rows"]:
            row["status"] = "creator_preflight_passed"
        _write(
            out / ".state/candidates/selected-manifest.json",
            json.dumps(selected, indent=2, sort_keys=True) + "\n",
        )
        return receipt


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--image", default=SANITY_IMAGE)
    args = parser.parse_args(argv)
    roots = build(args.out, force=args.force)
    if args.verify_core:
        verify_core(args.out)
    if args.verify_host:
        verify_host(args.out)
    if args.docker_sanity:
        verify_docker(args.out, args.image)
    print(f"Wrote {len(roots)} duration/elapsed/countdown expansion roots under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
