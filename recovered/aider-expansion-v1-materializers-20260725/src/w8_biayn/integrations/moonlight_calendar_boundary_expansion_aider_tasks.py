"""Own the expansion-v1 calendar-difference, leap, and month-end family."""

from __future__ import annotations

import argparse
import calendar
import concurrent.futures
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, replace
from datetime import date, timedelta, timezone, datetime
from itertools import combinations
from pathlib import Path
from typing import Iterable, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task


DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/time-date/"
    "calendar-difference-leap-month-end"
)
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-clock-tasks/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_CALENDAR_BOUNDARY_EXPANSION_CURRICULUM.md"
)
FAMILY_SPEC = Path(
    "docs/aider-tasks-spec/aider-dates-and-clocks/"
    "calendar-difference-leap-month-end-expansion.md"
)
REMEDY_RECORD = Path(
    "docs/aider-tasks-spec/aider-dates-and-clocks/remedies/"
    "calendar-boundary-expansion-cycle-002-remedy.md"
)
SELECTED_PROMPTS = (
    "docs/aider-tasks-spec/prompts/generate-family-spec.md",
    "docs/aider-tasks-spec/prompts/implement-family-for-sft.md",
)
FAMILY_ID = "expansion-v1-calendar-difference-leap-month-end-v1"
OWNER = "src/w8_biayn/integrations/moonlight_calendar_boundary_expansion_aider_tasks.py"
FOCUSED_TEST = "tests/test_moonlight_calendar_boundary_expansion_aider_tasks.py"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
NORMALIZER = "calendar-boundary-artifacts-plus-observable-probes-v2"
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
)
OFFICIAL_HOLDOUTS = frozenset(
    {
        "all-your-base", "allergies", "bank-account", "binary-search-tree",
        "circular-buffer", "clock", "complex-numbers", "crypto-square",
        "diamond", "dnd-character", "gigasecond", "grade-school",
        "kindergarten-garden", "knapsack", "linked-list", "meetup",
        "parallel-letter-frequency", "perfect-numbers", "phone-number",
        "queen-attack", "robot-name", "space-age", "spiral-matrix",
        "sublist", "yacht", "zebra-puzzle",
    }
)
_SOURCE_INVENTORY_CACHE:dict[tuple[str,str],dict[str,object]]={}


class VerificationError(RuntimeError):
    """A fail-closed creator or verifier gate did not pass."""


def _fail(code: str, detail: str = "") -> None:
    raise VerificationError(f"{code}: {detail}" if detail else code)


@dataclass(frozen=True)
class TaskCase:
    task_id: str
    title: str
    cluster: str
    mechanism: str
    operation: int
    api_kind: str

    @property
    def class_name(self) -> str:
        return "".join(part.title() for part in self.task_id.split("-"))

    @property
    def method_name(self) -> str:
        words = self.task_id.split("-")[2:]
        return "_".join(words)


METRIC_TASKS = (
    ("calendar-signed-day-distance", "Signed day distance", "signed ordinal subtraction"),
    ("calendar-weekday-cardinality", "Weekday cardinality", "Monday-through-Friday span accumulation"),
    ("calendar-midpoint-ordinal", "Midpoint ordinal", "overflow-safe ordinal midpoint selection"),
    ("calendar-interior-day-cardinality", "Interior day cardinality", "open-span cardinality"),
    ("calendar-crossed-month-boundaries", "Crossed month boundaries", "month-transition scan"),
    ("calendar-crossed-year-boundaries", "Crossed year boundaries", "year-transition scan"),
    ("calendar-contained-leap-days", "Contained leap days", "leap-day membership scan"),
    ("calendar-contained-month-ends", "Contained month ends", "month-end membership scan"),
    ("calendar-month-end-parity-balance", "Month-end parity balance", "alternating month-end parity fold"),
    ("calendar-complete-months-between", "Complete months between", "clamped whole-month decomposition"),
    ("calendar-complete-years-between", "Complete years between", "anniversary whole-year decomposition"),
    ("calendar-thirty-day-convention", "Thirty-day convention", "30E/360 bounded difference"),
    ("calendar-actual-year-fraction", "Actual year fraction basis points", "leap-aware annual fraction segmentation"),
    ("calendar-month-fragment-count", "Month fragment count", "calendar-month partition counting"),
    ("calendar-year-fragment-count", "Year fragment count", "calendar-year partition counting"),
    ("calendar-february-day-count", "February day count", "February membership accumulation"),
    ("calendar-long-month-day-count", "Long-month day count", "31-day-month membership accumulation"),
    ("calendar-month-capacity-transition-count", "Month-capacity transition count", "month-boundary capacity-change detection"),
    ("calendar-day-of-year-displacement", "Day-of-year displacement", "year-relative ordinal subtraction"),
    ("calendar-month-weighted-distance", "Month-weighted distance", "month-index weighted span fold"),
    ("calendar-day-number-checksum", "Day-number checksum", "day-of-month span checksum"),
    ("calendar-leap-year-day-count", "Leap-year day count", "leap-year membership accumulation"),
    ("calendar-post-leap-pivot-day-count", "Post-leap-pivot day count", "post-February leap-year segment accumulation"),
    ("calendar-century-day-count", "Century-year day count", "century boundary membership accumulation"),
    ("calendar-endpoint-month-length-delta", "Endpoint month-length delta", "endpoint month-capacity comparison"),
    ("calendar-endpoint-month-residual-delta", "Endpoint month residual delta", "endpoint residual-month displacement"),
    ("calendar-month-end-distance-sum", "Month-end distance sum", "per-day residual-month fold"),
    ("calendar-triangular-day-load", "Triangular day load", "per-day triangular position fold"),
    ("calendar-leap-cycle-index-delta", "Leap-cycle index delta", "400-year cycle coordinate difference"),
    ("calendar-boundary-density-score", "Boundary density score", "weighted month/year/leap boundary density"),
)

TRANSFORM_TASKS = (
    ("monthend-add-days", "Add civil days", "ordinal day displacement"),
    ("monthend-subtract-days", "Subtract civil days", "reverse ordinal displacement"),
    ("monthend-add-months-clamped", "Add months with clamp", "target-month day clamp"),
    ("monthend-add-months-rolled", "Add months with rollover", "overflow-day rollover"),
    ("monthend-add-months-eom-anchor", "Add months preserving month end", "end-of-month anchor propagation"),
    ("monthend-add-years-clamped", "Add years with clamp", "February anniversary clamp"),
    ("monthend-add-years-march-shift", "Add years with March shift", "February anniversary March policy"),
    ("monthend-current-last-day", "Current month last day", "month-capacity projection"),
    ("monthend-next-boundary", "Next month-end boundary", "strict forward month-end selection"),
    ("monthend-previous-boundary", "Previous month-end boundary", "strict reverse month-end selection"),
    ("monthend-nth-forward-boundary", "Nth forward month end", "iterated month-end stepping"),
    ("monthend-nth-reverse-boundary", "Nth reverse month end", "reverse month-end stepping"),
    ("monthend-quarter-boundary", "Quarter-end projection", "quarter terminal-month selection"),
    ("monthend-year-boundary", "Year-end projection", "year terminal-day selection"),
    ("monthend-fiscal-boundary", "Fiscal-year-end projection", "parameterized fiscal terminal selection"),
    ("monthend-next-leap-day", "Next leap day", "strict forward leap-day search"),
    ("monthend-previous-leap-day", "Previous leap day", "strict reverse leap-day search"),
    ("monthend-nth-leap-day", "Nth leap day", "bounded leap-year enumeration"),
    ("monthend-clamp-requested-day", "Clamp requested day", "same-month requested-day clamp"),
    ("monthend-roll-requested-day", "Roll requested day", "same-month overflow rollover"),
    ("monthend-reflect-day", "Reflected day-of-month", "month-capacity mirror selection"),
    ("monthend-month-end-offset", "Month-end offset", "month-terminal reverse displacement"),
    ("monthend-next-month-start", "Next month start", "strict forward month-origin selection"),
    ("monthend-quarter-start", "Quarter-start projection", "quarter origin selection"),
    ("monthend-semester-boundary", "Semester-end projection", "half-year terminal selection"),
    ("monthend-next-smaller-month", "Next smaller month", "forward month-capacity extremum search"),
    ("monthend-february-boundary", "February-end projection", "same-year February capacity selection"),
    ("monthend-century-cycle-clamp", "Century-cycle clamp", "hundred-year February clamp projection"),
    ("monthend-four-century-cycle", "Four-century cycle projection", "four-hundred-year exact-cycle projection"),
    ("monthend-ordinal-day-normalizer", "Ordinal-day normalizer", "year-relative ordinal normalization"),
)

SERIES_TASKS = (
    ("leapseries-month-end-partition", "Month-end partition", "closed-span month-end enumeration"),
    ("leapseries-month-start-partition", "Month-start partition", "closed-span month-origin enumeration"),
    ("leapseries-month-capacity-changes", "Month-capacity changes", "month-terminal capacity-transition enumeration"),
    ("leapseries-year-end-partition", "Year-end partition", "closed-span year-terminal enumeration"),
    ("leapseries-leap-day-partition", "Leap-day partition", "closed-span leap-day enumeration"),
    ("leapseries-february-end-partition", "February-end partition", "closed-span February terminal enumeration"),
    ("leapseries-clamped-monthly-anchor", "Clamped monthly anchors", "fixed requested-day monthly schedule"),
    ("leapseries-midmonth-monthly-anchor", "Midmonth monthly anchors", "month-midpoint anchored schedule"),
    ("leapseries-rolled-monthly-anchor", "Rolled monthly anchors", "overflow-day monthly schedule"),
    ("leapseries-quarterly-anchor", "Quarterly anchors", "clamped three-month schedule"),
    ("leapseries-annual-clamped-anchor", "Annual clamped anchors", "February-safe annual schedule"),
    ("leapseries-annual-march-anchor", "Annual March-shift anchors", "March-shift annual schedule"),
    ("leapseries-month-fragment-origins", "Month fragment origins", "month-partition origin sequence"),
    ("leapseries-leap-status-run-starts", "Leap-status run starts", "maximal equal leap-status run origins"),
    ("leapseries-long-month-terminals", "Long-month terminals", "31-day-month terminal selection"),
    ("leapseries-leap-year-quarter-ends", "Leap-year quarter ends", "leap-year canonical quarter-terminal selection"),
    ("leapseries-century-exception-vector", "Century exception vector", "Gregorian century-exception enumeration"),
    ("leapseries-four-hundred-cycle-vector", "Four-hundred-year leap vector", "complete Gregorian-cycle enumeration"),
    ("leapseries-penultimate-month-days", "Penultimate month days", "monthly penultimate-day selection"),
    ("leapseries-prime-month-days", "Prime month days", "monthly prime-numbered-day selection"),
    ("leapseries-fiscal-end-partition", "Fiscal-end partition", "parameterized fiscal terminal enumeration"),
    ("leapseries-capacity-run-starts", "Capacity-run starts", "maximal equal-capacity month-run origins"),
    ("leapseries-semester-end-partition", "Semester-end partition", "half-year terminal enumeration"),
    ("leapseries-century-clamped-anchors", "Century-clamped anchors", "hundred-year clamped anniversary sequence"),
    ("leapseries-leap-status-transitions", "Leap-status transitions", "annual leap-status transition anniversary sequence"),
    ("leapseries-quarter-start-partition", "Quarter-start partition", "canonical quarter-origin selection"),
    ("leapseries-leap-gap-midpoints", "Inter-leap-day midpoints", "consecutive leap-day midpoint selection"),
    ("leapseries-capacity-change-pairs", "Capacity-change boundary pairs", "month-capacity transition pair encoding"),
    ("leapseries-february-capacity-transitions", "February capacity transitions", "February-capacity change-origin selection"),
    ("leapseries-calendar-cycle-checkpoints", "Calendar cycle checkpoints", "century and 400-year checkpoint merge"),
)


def _make_tasks() -> tuple[TaskCase, ...]:
    tasks: list[TaskCase] = []
    for api_kind, cluster, rows in (
        ("metric", "calendar-difference", METRIC_TASKS),
        ("transform", "month-end-transform", TRANSFORM_TASKS),
        ("series", "leap-month-series", SERIES_TASKS),
    ):
        for operation, (task_id, title, mechanism) in enumerate(rows):
            tasks.append(TaskCase(task_id, title, cluster, mechanism, operation, api_kind))
    if len(tasks) != 90 or len({task.task_id for task in tasks}) != 90:
        raise AssertionError("the binding plan cell requires 90 unique task IDs")
    return tuple(tasks)


TASKS = _make_tasks()


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "sha256:absent"
    for path in sorted(
        item
        for item in root.rglob("*")
        if item.is_file() and ".state" not in item.relative_to(root).parts
    ):
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, value: object) -> None:
    _write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _slug_files(case: TaskCase) -> tuple[str, str]:
    return f"{case.task_id}.h", f"{case.task_id}.cpp"


CPP_SUPPORT = r'''
namespace {
[[maybe_unused]] bool leap(int y) { return y % 4 == 0 && (y % 100 != 0 || y % 400 == 0); }
[[maybe_unused]] int calendar_month_days(int y, int m) {
  static const int days[] = {31,28,31,30,31,30,31,31,30,31,30,31};
  if (m < 1 || m > 12) return 0;
  return days[m - 1] + (m == 2 && leap(y) ? 1 : 0);
}
[[maybe_unused]] bool valid(Date d) {
  return d.year >= 1 && d.year <= 9999 && d.month >= 1 && d.month <= 12 &&
         d.day >= 1 && d.day <= calendar_month_days(d.year, d.month);
}
[[maybe_unused]] long long serial(Date d) {
  long long y = d.year - 1;
  long long result = 365 * y + y / 4 - y / 100 + y / 400;
  for (int m = 1; m < d.month; ++m) result += calendar_month_days(d.year, m);
  return result + d.day - 1;
}
[[maybe_unused]] Date civil(long long n) {
  int low = 1, high = 9999;
  while (low < high) {
    int mid = low + (high - low + 1) / 2;
    if (serial({mid, 1, 1}) <= n) low = mid; else high = mid - 1;
  }
  int year = low, month = 1;
  n -= serial({year, 1, 1});
  while (month < 12 && n >= calendar_month_days(year, month)) n -= calendar_month_days(year, month++);
  return {year, month, static_cast<int>(n) + 1};
}
[[maybe_unused]] Date add_months_clamped(Date d, int delta) {
  long long index = static_cast<long long>(d.year - 1) * 12 + d.month - 1 + delta;
  if (index < 0) return {};
  if (index >= 9999LL * 12) return {10000, 1, 1};
  int y = static_cast<int>(index / 12) + 1;
  int m = static_cast<int>(index % 12) + 1;
  return {y, m, std::min(d.day, calendar_month_days(y, m))};
}
[[maybe_unused]] Date add_months_rolled(Date d, int delta) {
  Date target = add_months_clamped({d.year, d.month, 1}, delta);
  if (!valid(target)) return {};
  long long origin = serial(target);
  if (origin + d.day - 1 > serial({9999, 12, 31})) return {};
  return civil(origin + d.day - 1);
}
[[maybe_unused]] bool before(Date a, Date b) { return serial(a) < serial(b); }
}  // namespace
'''


METRIC_CORES = (
    "return serial(b) - serial(a);",
    "long long n=0;for(Date d=a;;d=civil(serial(d)+1)){if(serial(d)%7<5)++n;if(serial(d)==serial(b))break;}return n;",
    "long long lo=serial(a),hi=serial(b); return lo+(hi-lo)/2;",
    "return std::max(0LL, std::llabs(serial(b) - serial(a)) - 1);",
    "long long n=0; for(Date d=a; before(d,b); d=civil(serial(d)+1)) if(d.day==month_days(d.year,d.month)) ++n; return n;",
    "long long n=0; for(int y=a.year; y<b.year; ++y) if(serial({y+1,1,1})>serial(a)&&serial({y+1,1,1})<=serial(b)) ++n; return n;",
    "long long n=0; for(int y=a.year; y<=b.year; ++y) if(leap(y)&&serial({y,2,29})>=serial(a)&&serial({y,2,29})<=serial(b)) ++n; return n;",
    "long long n=0; for(Date d=a; serial(d)<=serial(b); d=civil(serial(d)+1)) if(d.day==month_days(d.year,d.month)) ++n; return n;",
    "long long balance=0; for(Date d=a;serial(d)<=serial(b);d=civil(serial(d)+1))if(d.day==month_days(d.year,d.month))balance+=(d.month%2==0?1:-1);return balance;",
    "long long months=(b.year-a.year)*12+b.month-a.month; if(b.day<std::min(a.day,month_days(b.year,b.month))) --months; return std::max(0LL,months);",
    "long long years=b.year-a.year; Date anniversary{b.year,a.month,std::min(a.day,month_days(b.year,a.month))}; if(before(b,anniversary)) --years; return std::max(0LL,years);",
    "long long y=360LL*(b.year-a.year)+30LL*(b.month-a.month)+std::min(b.day,30)-std::min(a.day,30); return y;",
    "long long total=0; for(int y=a.year;y<=b.year;++y){long long lo=std::max(serial(a),serial({y,1,1}));long long hi=std::min(serial(b),serial({y,12,31}));if(lo<=hi)total+=(hi-lo+1)*10000/(leap(y)?366:365);} return total;",
    "long long n=0; Date d{a.year,a.month,1}; while(valid(d)&&serial(d)<=serial(b)){++n;d=add_months_clamped(d,1);} return n;",
    "long long n=0; for(int y=a.year;y<=b.year;++y) if(serial({y,1,1})<=serial(b)&&serial({y,12,31})>=serial(a)) ++n; return n;",
    "long long n=0; for(Date d=a;serial(d)<=serial(b);d=civil(serial(d)+1)) if(d.month==2) ++n; return n;",
    "long long n=0; for(Date d=a;serial(d)<=serial(b);d=civil(serial(d)+1)) if(month_days(d.year,d.month)==31) ++n; return n;",
    "long long n=0; for(Date d=a;serial(d)<serial(b);d=civil(serial(d)+1)) if(d.day==month_days(d.year,d.month)){Date next=civil(serial(d)+1);if(month_days(d.year,d.month)!=month_days(next.year,next.month))++n;} return n;",
    "return (serial(b)-serial({b.year,1,1}))-(serial(a)-serial({a.year,1,1}));",
    "long long n=0; for(Date d=a;serial(d)<=serial(b);d=civil(serial(d)+1)) n+=d.month; return n;",
    "long long n=0; for(Date d=a;serial(d)<=serial(b);d=civil(serial(d)+1)) n+=d.day; return n;",
    "long long n=0; for(Date d=a;serial(d)<=serial(b);d=civil(serial(d)+1)) if(leap(d.year)) ++n; return n;",
    "long long n=0;for(int y=a.year;y<=b.year;++y)if(leap(y)){long long lo=std::max(serial(a),serial({y,3,1}));long long hi=std::min(serial(b),serial({y,12,31}));if(lo<=hi)n+=hi-lo+1;}return n;",
    "long long n=0; for(Date d=a;serial(d)<=serial(b);d=civil(serial(d)+1)) if(d.year%100==0) ++n; return n;",
    "return month_days(b.year,b.month)-month_days(a.year,a.month);",
    "return (month_days(b.year,b.month)-b.day)-(month_days(a.year,a.month)-a.day);",
    "long long n=0; for(Date d=a;serial(d)<=serial(b);d=civil(serial(d)+1)) n+=month_days(d.year,d.month)-d.day; return n;",
    "long long n=0;for(Date d=a;serial(d)<=serial(b);d=civil(serial(d)+1))n+=static_cast<long long>(d.day)*(d.day+1)/2;return n;",
    "return ((b.year-1)%400)*366LL+b.month*31LL+b.day-(((a.year-1)%400)*366LL+a.month*31LL+a.day);",
    "long long m=0,y=0,l=0; for(Date d=a;serial(d)<=serial(b);d=civil(serial(d)+1)){m+=d.day==month_days(d.year,d.month);y+=d.month==12&&d.day==31;l+=d.month==2&&d.day==29;} return 3*m+7*y+11*l;",
)


TRANSFORM_CORES = (
    "if(p<0)return std::nullopt;long long n=serial(a)+p; return n>=0&&n<=serial({9999,12,31})?std::optional<Date>(civil(n)):std::nullopt;",
    "if(p<0)return std::nullopt;long long n=serial(a)-p; return n>=0?std::optional<Date>(civil(n)):std::nullopt;",
    "Date d=add_months_clamped(a,p); return valid(d)?std::optional<Date>(d):std::nullopt;",
    "Date d=add_months_rolled(a,p); return valid(d)?std::optional<Date>(d):std::nullopt;",
    "bool end=a.day==month_days(a.year,a.month); Date d=add_months_clamped(a,p); if(end&&valid(d))d.day=month_days(d.year,d.month); return valid(d)?std::optional<Date>(d):std::nullopt;",
    "long long y=static_cast<long long>(a.year)+p; if(y<1||y>9999)return std::nullopt; int target=static_cast<int>(y); return Date{target,a.month,std::min(a.day,month_days(target,a.month))};",
    "long long y=static_cast<long long>(a.year)+p; if(y<1||y>9999)return std::nullopt; int target=static_cast<int>(y); if(a.month==2&&a.day==29&&!leap(target))return Date{target,3,1}; return Date{target,a.month,a.day};",
    "return Date{a.year,a.month,month_days(a.year,a.month)};",
    "Date d={a.year,a.month,month_days(a.year,a.month)}; if(!before(a,d)){d=add_months_clamped({a.year,a.month,1},1);if(!valid(d))return std::nullopt;d.day=month_days(d.year,d.month);} return d;",
    "Date first={a.year,a.month,1}; Date d=add_months_clamped(first,-1); if(!valid(d))return std::nullopt; if(before({d.year,d.month,month_days(d.year,d.month)},a))return Date{d.year,d.month,month_days(d.year,d.month)}; return std::nullopt;",
    "if(p<1)return std::nullopt; Date d={a.year,a.month,month_days(a.year,a.month)}; for(int i=1;i<p;++i){d=add_months_clamped({d.year,d.month,1},1);if(!valid(d))return std::nullopt;d.day=month_days(d.year,d.month);} return d;",
    "if(p<1)return std::nullopt; Date d=add_months_clamped({a.year,a.month,1},-p); return valid(d)?std::optional<Date>(Date{d.year,d.month,month_days(d.year,d.month)}):std::nullopt;",
    "int m=((a.month-1)/3+1)*3; return Date{a.year,m,month_days(a.year,m)};",
    "return Date{a.year,12,31};",
    "if(p<1||p>12)return std::nullopt; int y=a.month>p?a.year+1:a.year; return y<=9999?std::optional<Date>(Date{y,p,month_days(y,p)}):std::nullopt;",
    "for(int y=a.year;y<=9999;++y)if(leap(y)&&before(a,{y,2,29}))return Date{y,2,29}; return std::nullopt;",
    "for(int y=a.year;y>=1;--y)if(leap(y)&&before({y,2,29},a))return Date{y,2,29}; return std::nullopt;",
    "if(p<1)return std::nullopt; int found=0; for(int y=a.year;y<=9999;++y)if(leap(y)&&before(a,{y,2,29})&&++found==p)return Date{y,2,29}; return std::nullopt;",
    "if(p<1)return std::nullopt; return Date{a.year,a.month,std::min(static_cast<int>(p),month_days(a.year,a.month))};",
    "if(p<1)return std::nullopt; long long n=serial({a.year,a.month,1})+p-1; return n<=serial({9999,12,31})?std::optional<Date>(civil(n)):std::nullopt;",
    "return Date{a.year,a.month,month_days(a.year,a.month)-a.day+1};",
    "if(p<0)return std::nullopt; long long n=serial({a.year,a.month,month_days(a.year,a.month)})-p; return n>=0?std::optional<Date>(civil(n)):std::nullopt;",
    "Date d=add_months_clamped({a.year,a.month,1},1); return valid(d)?std::optional<Date>(d):std::nullopt;",
    "int m=((a.month-1)/3)*3+1;return Date{a.year,m,1};",
    "int m=a.month<=6?6:12; return Date{a.year,m,month_days(a.year,m)};",
    "if(p<1)return std::nullopt;int capacity=month_days(a.year,a.month);Date d={a.year,a.month,1};for(int i=0;i<p;++i){d=add_months_clamped(d,1);if(!valid(d))return std::nullopt;if(month_days(d.year,d.month)<capacity)return Date{d.year,d.month,month_days(d.year,d.month)};}return std::nullopt;",
    "return Date{a.year,2,month_days(a.year,2)};",
    "long long delta=static_cast<long long>(p)*100;long long y=static_cast<long long>(a.year)+delta;if(y<1||y>9999)return std::nullopt;return Date{static_cast<int>(y),a.month,std::min(a.day,month_days(static_cast<int>(y),a.month))};",
    "long long delta=static_cast<long long>(p)*400;long long y=static_cast<long long>(a.year)+delta;if(y<1||y>9999)return std::nullopt;return Date{static_cast<int>(y),a.month,a.day};",
    "if(p<1||p>(leap(a.year)?366:365))return std::nullopt; return civil(serial({a.year,1,1})+p-1);",
)


SERIES_CORES = (
    "for(Date d=a;serial(d)<=serial(b);d=civil(serial(d)+1))if(d.day==month_days(d.year,d.month))out.push_back(d);",
    "for(Date d=a;serial(d)<=serial(b);d=civil(serial(d)+1))if(d.day==1)out.push_back(d);",
    "for(Date d={a.year,a.month,month_days(a.year,a.month)};serial(d)<=serial(b);){Date next=add_months_clamped({d.year,d.month,1},1);if(!valid(next))break;if(month_days(d.year,d.month)!=month_days(next.year,next.month)&&serial(d)>=serial(a))out.push_back(d);d={next.year,next.month,month_days(next.year,next.month)};}",
    "for(int y=a.year;y<=b.year;++y){Date d{y,12,31};if(serial(d)>=serial(a)&&serial(d)<=serial(b))out.push_back(d);}",
    "for(int y=a.year;y<=b.year;++y)if(leap(y)){Date d{y,2,29};if(serial(d)>=serial(a)&&serial(d)<=serial(b))out.push_back(d);}",
    "for(int y=a.year;y<=b.year;++y){Date d{y,2,month_days(y,2)};if(serial(d)>=serial(a)&&serial(d)<=serial(b))out.push_back(d);}",
    "if(p<1)return {}; for(Date m={a.year,a.month,1};valid(m);m=add_months_clamped(m,1)){Date d{m.year,m.month,std::min(static_cast<int>(p),month_days(m.year,m.month))};if(serial(d)>serial(b))break;if(serial(d)>=serial(a))out.push_back(d);}",
    "for(Date d={a.year,a.month,1};valid(d)&&serial(d)<=serial(b);d=add_months_clamped(d,1)){Date mid{d.year,d.month,(month_days(d.year,d.month)+1)/2};if(serial(mid)>=serial(a)&&serial(mid)<=serial(b))out.push_back(mid);}",
    "if(p<1)return {}; for(Date base={a.year,a.month,1};valid(base);base=add_months_clamped(base,1)){long long ordinal=serial(base)+p-1;if(ordinal>serial({9999,12,31}))break;Date d=civil(ordinal);if(serial(d)>serial(b))break;if(serial(d)>=serial(a))out.push_back(d);}",
    "for(int k=1;;++k){Date d=add_months_clamped(a,3*k);if(!valid(d)||serial(d)>serial(b))break;out.push_back(d);}",
    "for(int y=a.year+1;y<=b.year;++y){Date d{y,a.month,std::min(a.day,month_days(y,a.month))};if(serial(d)<=serial(b))out.push_back(d);}",
    "for(int y=a.year+1;y<=b.year;++y){Date d{y,a.month,a.day};if(a.month==2&&a.day==29&&!leap(y))d={y,3,1};if(serial(d)<=serial(b))out.push_back(d);}",
    "for(Date start=a;serial(start)<=serial(b);){out.push_back(start);Date end{start.year,start.month,month_days(start.year,start.month)};long long hi=std::min(serial(end),serial(b));if(hi==serial(b))break;start=civil(hi+1);}",
    "for(Date start=a;serial(start)<=serial(b);){out.push_back(start);bool status=leap(start.year);int y=start.year+1;while(y<=b.year&&leap(y)==status)++y;if(y>b.year)break;start={y,1,1};}",
    "for(Date d={a.year,a.month,1};valid(d)&&serial(d)<=serial(b);d=add_months_clamped(d,1))if(month_days(d.year,d.month)==31){Date end{d.year,d.month,31};if(serial(end)>=serial(a)&&serial(end)<=serial(b))out.push_back(end);}",
    "for(int y=a.year;y<=b.year;++y)if(leap(y))for(Date d:std::initializer_list<Date>{{y,3,31},{y,6,30},{y,9,30},{y,12,31}})if(serial(d)>=serial(a)&&serial(d)<=serial(b))out.push_back(d);",
    "for(int y=((a.year+99)/100)*100;y<=b.year;y+=100)if(!leap(y)){Date d{y,2,28};if(serial(d)>=serial(a)&&serial(d)<=serial(b))out.push_back(d);}",
    "for(int y=((a.year+399)/400)*400;y<=b.year;y+=400){Date d{y,2,29};if(serial(d)>=serial(a)&&serial(d)<=serial(b))out.push_back(d);}",
    "for(Date d={a.year,a.month,1};valid(d)&&serial(d)<=serial(b);d=add_months_clamped(d,1)){Date penultimate{d.year,d.month,month_days(d.year,d.month)-1};if(serial(penultimate)>=serial(a)&&serial(penultimate)<=serial(b))out.push_back(penultimate);}",
    "for(Date month={a.year,a.month,1};valid(month)&&serial(month)<=serial(b);month=add_months_clamped(month,1))for(int day:{2,3,5,7,11}){Date d{month.year,month.month,day};if(serial(d)>=serial(a)&&serial(d)<=serial(b))out.push_back(d);}",
    "if(p<1||p>12)return {}; for(int y=a.year;y<=b.year;++y){Date d{y,p,month_days(y,p)};if(serial(d)>=serial(a)&&serial(d)<=serial(b))out.push_back(d);}",
    "Date d=a;int prior=-1;while(valid(d)&&serial(d)<=serial(b)){int capacity=month_days(d.year,d.month);if(prior<0||capacity!=prior)out.push_back(d);prior=capacity;d=add_months_clamped({d.year,d.month,1},1);}",
    "for(int y=a.year;y<=b.year;++y)for(int m:{6,12}){Date d{y,m,month_days(y,m)};if(serial(d)>=serial(a)&&serial(d)<=serial(b))out.push_back(d);}",
    "for(long long y=static_cast<long long>(a.year)+100;y<=b.year;y+=100){Date d{static_cast<int>(y),a.month,std::min(a.day,month_days(static_cast<int>(y),a.month))};if(serial(d)<=serial(b))out.push_back(d);}",
    "for(int y=a.year+1;y<=b.year;++y)if(leap(y)!=leap(y-1)){Date d{y,a.month,std::min(a.day,month_days(y,a.month))};if(serial(d)<=serial(b))out.push_back(d);}",
    "for(int y=a.year;y<=b.year;++y)for(int m:{1,4,7,10}){Date d{y,m,1};if(serial(d)>=serial(a)&&serial(d)<=serial(b))out.push_back(d);}",
    "std::optional<Date> previous;for(int y=a.year;y<=b.year;++y)if(leap(y)){Date d{y,2,29};if(serial(d)>=serial(a)&&serial(d)<=serial(b)){if(previous)out.push_back(civil(serial(*previous)+(serial(d)-serial(*previous))/2));previous=d;}}",
    "Date d={a.year,a.month,1};int prior=month_days(d.year,d.month);for(d=add_months_clamped(d,1);valid(d)&&serial(d)<=serial(b);d=add_months_clamped(d,1)){int capacity=month_days(d.year,d.month);Date terminal{d.year,d.month,capacity};if(capacity!=prior&&serial(terminal)<=serial(b)){out.push_back(d);out.push_back(terminal);}prior=capacity;}",
    "for(int y=std::max(2,a.year);y<=b.year;++y)if(leap(y)!=leap(y-1)){Date d{y,2,1};if(serial(d)>=serial(a)&&serial(d)<=serial(b))out.push_back(d);}",
    "for(int y=a.year;y<=b.year;++y)if(y%100==0||y%400==0){Date d{y,2,leap(y)?29:28};if(serial(d)>=serial(a)&&serial(d)<=serial(b))out.push_back(d);}",
)


def _header(case: TaskCase) -> str:
    header, _ = _slug_files(case)
    guard = re.sub(r"[^A-Z0-9]", "_", header.upper()) + "_"
    if case.api_kind == "metric":
        declaration = f"std::optional<long long> {case.method_name}(Date first, Date last) const;"
    elif case.api_kind == "transform":
        declaration = f"std::optional<Date> {case.method_name}(Date value, int parameter) const;"
    else:
        declaration = f"std::optional<std::vector<Date>> {case.method_name}(Date first, Date last, int parameter) const;"
    return f'''#ifndef {guard}\n#define {guard}\n#include <optional>\n#include <vector>\nnamespace curriculum {{\nstruct Date {{ int year; int month; int day; friend bool operator==(Date a, Date b) {{ return a.year==b.year&&a.month==b.month&&a.day==b.day; }} }};\nclass {case.class_name} {{ public: {declaration} }};\n}}  // namespace curriculum\n#endif\n'''


def _format_core(core: str) -> str:
    """Break compact generated statements without splitting for-loop headers."""
    result=[];parentheses=0
    for character in core:
        result.append(character)
        if character=="(":parentheses+=1
        elif character==")":parentheses-=1
        elif character==";" and parentheses==0:result.append("\n")
    if parentheses!=0:_fail("generator_core_unbalanced_parentheses")
    return "".join(result)


def _reference(case: TaskCase) -> str:
    header, _ = _slug_files(case)
    if case.api_kind == "metric":
        signature = f"std::optional<long long> {case.class_name}::{case.method_name}(Date a, Date b) const"
        validation = "if(!valid(a)||!valid(b)||before(b,a))return std::nullopt;"
        core = _format_core(METRIC_CORES[case.operation].replace("month_days(", "calendar_month_days("))
    elif case.api_kind == "transform":
        signature = f"std::optional<Date> {case.class_name}::{case.method_name}(Date a, int p) const"
        validation = "if(!valid(a))return std::nullopt;static_cast<void>(p);"
        core = _format_core(TRANSFORM_CORES[case.operation].replace("month_days(", "calendar_month_days("))
    else:
        signature = f"std::optional<std::vector<Date>> {case.class_name}::{case.method_name}(Date a, Date b, int p) const"
        validation = "if(!valid(a)||!valid(b)||before(b,a))return std::nullopt;static_cast<void>(p);std::vector<Date> out;"
        core = _format_core(
            (SERIES_CORES[case.operation] + " return out;").replace(
                "month_days(", "calendar_month_days("
            )
        )
    return f'''#include "{header}"\n#include <algorithm>\n#include <cstdlib>\n#include <initializer_list>\n#include <limits>\nnamespace curriculum {{\n{CPP_SUPPORT}\n{signature} {{ {validation}\n// CORE_BEGIN: {case.mechanism}\n{core}\n// CORE_END\n}}\n}}  // namespace curriculum\n'''


def _starter(case: TaskCase) -> str:
    header, _ = _slug_files(case)
    if case.api_kind == "metric":
        signature = f"std::optional<long long> {case.class_name}::{case.method_name}(Date, Date) const"
    elif case.api_kind == "transform":
        signature = f"std::optional<Date> {case.class_name}::{case.method_name}(Date, int) const"
    else:
        signature = f"std::optional<std::vector<Date>> {case.class_name}::{case.method_name}(Date, Date, int) const"
    return f'''#include "{header}"\nnamespace curriculum {{\n{signature} {{ return std::nullopt; }}\n}}  // namespace curriculum\n'''


def _test_source(case: TaskCase, *, hidden: bool, negative_operation: int | None = None) -> str:
    header, _ = _slug_files(case)
    cls=case.class_name;method=case.method_name;operation=case.operation if negative_operation is None else negative_operation
    def cpp_date(value:date)->str:return f"{{{value.year},{value.month},{value.day}}}"
    if case.api_kind == "metric":
        cases=[(date(1900,2,28),date(2000,3,1)),(date(1900,2,28),date(1900,3,1)),(date(2000,2,28),date(2000,3,1)),(date(1,1,1),date(1,1,1)),(date(9999,12,31),date(9999,12,31))] if hidden else [(date(2023,12,31),date(2024,3,1)),(date(2024,2,28),date(2024,3,1)),(date(2024,2,29),date(2024,2,29))]
        checks=[]
        for index,(first,last) in enumerate(cases):
            expected=_metric_expected(operation,first,last)
            checks.append(f"auto r{index}=x.{method}({cpp_date(first)},{cpp_date(last)});if(!r{index}||*r{index}!={expected}LL)return {10+index};")
        checks.append(f"if(x.{method}({{2024,3,1}},{{2024,2,29}}))return 30;if(x.{method}({{2024,2,30}},{{2024,3,1}}))return 31;")
        support="";body=f"{cls} x;"+"".join(checks)+"return 0;"
    elif case.api_kind == "transform":
        cases=[(date(2000,2,29),3),(date(1900,2,28),1),(date(2000,2,29),1),(date(1,1,1),1),(date(9999,12,31),1),(date(2024,1,31),-1),(date(2024,1,31),13)] if hidden else [(date(2024,1,31),2),(date(2024,2,29),1),(date(2024,12,31),0)]
        checks=[]
        for index,(value,parameter) in enumerate(cases):
            expected=_safe_transform_value(operation,value,parameter)
            if expected is None:checks.append(f"if(x.{method}({cpp_date(value)},{parameter}))return {10+index};")
            else:checks.append(f"auto r{index}=x.{method}({cpp_date(value)},{parameter});if(!r{index}||!(*r{index}==Date{cpp_date(expected)}))return {10+index};")
        if operation in (5,6):
            checks.append(
                f"if(x.{method}({{2000,2,29}},std::numeric_limits<int>::max()))return 32;"
                f"if(x.{method}({{2000,2,29}},std::numeric_limits<int>::min()))return 33;"
            )
        checks.append(f"if(x.{method}({{2024,2,30}},2))return 30;")
        support="";body=f"{cls} x;"+"".join(checks)+"return 0;"
    else:
        cases=[(date(1999,12,1),date(2000,3,15),3),(date(1900,2,28),date(1900,3,2),1),(date(2000,2,28),date(2000,3,2),1),(date(1,1,1),date(1,2,1),1),(date(9999,12,1),date(9999,12,31),1)] if hidden else [(date(2023,12,15),date(2024,5,20),2),(date(2024,2,28),date(2024,3,2),1),(date(2024,2,29),date(2024,2,29),1)]
        if operation==6:cases.append((date(2023,12,15),date(2024,3,31),31))
        if operation==8:cases.append((date(9999,12,15),date(9999,12,31),32))
        if operation==9:cases.append((date(2024,1,31),date(2024,12,31),1))
        checks=[]
        for index,(first,last,parameter) in enumerate(cases):
            values=_series_value(operation,first,last,parameter)
            if values is None:_fail("oracle_invalid_valid_case",case.task_id)
            expected="{"+",".join(cpp_date(value) for value in values)+"}"
            checks.append(f"auto r{index}=x.{method}({cpp_date(first)},{cpp_date(last)},{parameter});std::vector<Date> e{index}{expected};if(!r{index}||*r{index}!=e{index}||!valid_series(*r{index},{cpp_date(first)},{cpp_date(last)}))return {10+index};")
        if operation in (6,8):
            checks.append(f"if(x.{method}({{2024,1,1}},{{2024,3,31}},0))return 32;")
        elif operation == 20:
            checks.append(
                f"if(x.{method}({{2024,1,1}},{{2024,12,31}},0))return 32;"
                f"if(x.{method}({{2024,1,1}},{{2024,12,31}},13))return 33;"
            )
        checks.append(f"if(x.{method}({{2024,3,1}},{{2024,2,29}},1))return 30;if(x.{method}({{2024,2,30}},{{2024,3,1}},1))return 31;")
        support="long long key(Date d){return d.year*10000LL+d.month*100+d.day;}bool valid_series(const std::vector<Date>&v,Date first,Date last){long long prior=-1;for(Date d:v){long long current=key(d);if(d.year<1||d.year>9999||d.month<1||d.month>12||d.day<1||current<key(first)||current>key(last)||current<=prior)return false;prior=current;}return true;}"
        body=f"{cls} x;"+"".join(checks)+"return 0;"
    return f'''#include "{header}"\n#include <limits>\n#include <vector>\nusing namespace curriculum;\nnamespace {{{support}}}\nint main(){{ {body} }}\n'''


def _py_leap(year: int) -> bool:
    return calendar.isleap(year)


def _py_month_days(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _py_add_months(value: date, delta: int, *, roll: bool = False, eom: bool = False) -> date | None:
    index = (value.year - 1) * 12 + value.month - 1 + delta
    if index < 0 or index >= 9999 * 12:
        return None
    year, month = divmod(index, 12)
    year += 1
    month += 1
    if roll:
        try:
            return date(year, month, 1) + timedelta(days=value.day - 1)
        except (ValueError, OverflowError):
            return None
    day = _py_month_days(year, month) if eom and value.day == _py_month_days(value.year, value.month) else min(value.day, _py_month_days(year, month))
    return date(year, month, day)


def _metric_expected(operation: int, a: date, b: date) -> int:
    days = list(a + timedelta(days=i) for i in range((b - a).days + 1))
    values = [
        (b-a).days, sum((d.toordinal()-1)%7<5 for d in days), a.toordinal()-1+(b.toordinal()-a.toordinal())//2, max(0,abs((b-a).days)-1),
        sum(d.day==_py_month_days(d.year,d.month) for d in days[:-1]),
        sum(date(y+1,1,1)>a and date(y+1,1,1)<=b for y in range(a.year,b.year)),
        sum(_py_leap(y) and a<=date(y,2,29)<=b for y in range(a.year,b.year+1)),
        sum(d.day==_py_month_days(d.year,d.month) for d in days),
        sum((1 if d.month%2==0 else -1) for d in days if d.day==_py_month_days(d.year,d.month)),
    ]
    months=(b.year-a.year)*12+b.month-a.month-(b.day<min(a.day,_py_month_days(b.year,b.month)))
    years=b.year-a.year-(b<date(b.year,a.month,min(a.day,_py_month_days(b.year,a.month))))
    values.extend([
        max(0,months), max(0,years), 360*(b.year-a.year)+30*(b.month-a.month)+min(b.day,30)-min(a.day,30),
        sum((min(b,date(y,12,31))-max(a,date(y,1,1))).days+1 for y in range(a.year,b.year+1))*0,
        len({(d.year,d.month) for d in days}), len({d.year for d in days}),
        sum(d.month==2 for d in days), sum(_py_month_days(d.year,d.month)==31 for d in days),
        sum(_py_month_days(d.year,d.month)==30 for d in days),
        (b-date(b.year,1,1)).days-(a-date(a.year,1,1)).days, sum(d.month for d in days),
        sum(d.day for d in days), sum(_py_leap(d.year) for d in days), sum(max(0,(min(b,date(y,12,31))-max(a,date(y,3,1))).days+1) for y in range(a.year,b.year+1) if _py_leap(y)),
        sum(d.year%100==0 for d in days), _py_month_days(b.year,b.month)-_py_month_days(a.year,a.month),
        (_py_month_days(b.year,b.month)-b.day)-(_py_month_days(a.year,a.month)-a.day),
        sum(_py_month_days(d.year,d.month)-d.day for d in days), sum(d.day*(d.day+1)//2 for d in days),
        ((b.year-1)%400)*366+b.month*31+b.day-(((a.year-1)%400)*366+a.month*31+a.day),
        3*sum(d.day==_py_month_days(d.year,d.month) for d in days)+7*sum(d.month==12 and d.day==31 for d in days)+11*sum(d.month==2 and d.day==29 for d in days),
    ])
    values[17]=sum(
        d<b
        and d.day==_py_month_days(d.year,d.month)
        and _py_month_days(d.year,d.month)!=_py_month_days((d+timedelta(days=1)).year,(d+timedelta(days=1)).month)
        for d in days
    )
    if operation == 12:
        total=0
        for y in range(a.year,b.year+1):
            lo=max(a,date(y,1,1)); hi=min(b,date(y,12,31))
            if lo<=hi: total+=((hi-lo).days+1)*10000//(366 if _py_leap(y) else 365)
        values[12]=total
    return int(values[operation])


def _transform_value(operation: int, a: date, p: int) -> date | None:
    if operation == 0: return a + timedelta(days=p) if p>=0 else None
    if operation == 1: return a - timedelta(days=p) if p>=0 else None
    if operation == 2: return _py_add_months(a,p)
    if operation == 3: return _py_add_months(a,p,roll=True)
    if operation == 4: return _py_add_months(a,p,eom=True)
    if operation == 5:
        y=a.year+p
        return date(y,a.month,min(a.day,_py_month_days(y,a.month))) if 1<=y<=9999 else None
    if operation == 6:
        y=a.year+p
        if not 1<=y<=9999:return None
        return date(y,3,1) if a.month==2 and a.day==29 and not _py_leap(y) else date(y,a.month,a.day)
    if operation == 7:return date(a.year,a.month,_py_month_days(a.year,a.month))
    if operation == 8:
        d=date(a.year,a.month,_py_month_days(a.year,a.month))
        target=date(a.year,a.month,1) if a<d else _py_add_months(date(a.year,a.month,1),1)
        return date(target.year,target.month,_py_month_days(target.year,target.month)) if target else None
    if operation == 9:
        target=_py_add_months(date(a.year,a.month,1),-1)
        return date(target.year,target.month,_py_month_days(target.year,target.month)) if target else None
    if operation == 10:
        target=_py_add_months(date(a.year,a.month,1),p-1) if p>=1 else None
        return date(target.year,target.month,_py_month_days(target.year,target.month)) if target else None
    if operation == 11:
        target=_py_add_months(date(a.year,a.month,1),-p) if p>=1 else None
        return date(target.year,target.month,_py_month_days(target.year,target.month)) if target else None
    if operation == 12:
        m=((a.month-1)//3+1)*3;return date(a.year,m,_py_month_days(a.year,m))
    if operation == 13:return date(a.year,12,31)
    if operation == 14:
        if not 1<=p<=12:return None
        y=a.year+(a.month>p);return date(y,p,_py_month_days(y,p))
    if operation in (15,17):
        found=0
        for y in range(a.year,10000):
            if _py_leap(y) and a<date(y,2,29):
                found+=1
                if operation==15 or found==p:return date(y,2,29)
    if operation == 16:
        for y in range(a.year,0,-1):
            if _py_leap(y) and date(y,2,29)<a:return date(y,2,29)
    if operation == 18:return date(a.year,a.month,min(p,_py_month_days(a.year,a.month))) if p>=1 else None
    if operation == 19:return date(a.year,a.month,1)+timedelta(days=p-1) if p>=1 else None
    if operation == 20:return date(a.year,a.month,_py_month_days(a.year,a.month)-a.day+1)
    if operation == 21:return date(a.year,a.month,_py_month_days(a.year,a.month))-timedelta(days=p) if p>=0 else None
    if operation == 22:return _py_add_months(date(a.year,a.month,1),1)
    if operation == 23:return date(a.year,((a.month-1)//3)*3+1,1)
    if operation == 24:
        m=6 if a.month<=6 else 12;return date(a.year,m,_py_month_days(a.year,m))
    if operation == 25:
        if p<1:return None
        capacity=_py_month_days(a.year,a.month);current=date(a.year,a.month,1)
        for _ in range(p):
            current=_py_add_months(current,1)
            if current is None:return None
            if _py_month_days(current.year,current.month)<capacity:return date(current.year,current.month,_py_month_days(current.year,current.month))
        return None
    if operation == 26:return date(a.year,2,_py_month_days(a.year,2))
    if operation == 27:
        y=a.year+p*100
        return date(y,a.month,min(a.day,_py_month_days(y,a.month))) if 1<=y<=9999 else None
    if operation == 28:
        y=a.year+p*400
        return date(y,a.month,a.day) if 1<=y<=9999 else None
    if operation == 29:return date(a.year,1,1)+timedelta(days=p-1) if 1<=p<=(366 if _py_leap(a.year) else 365) else None
    return None


def _safe_transform_value(operation:int,value:date,parameter:int)->date|None:
    try:return _transform_value(operation,value,parameter)
    except (OverflowError,ValueError):return None


def _series_value(operation: int, a: date, b: date, p: int) -> list[date] | None:
    if operation in (6, 8) and p < 1:
        return None
    if operation == 20 and not 1 <= p <= 12:
        return None
    days=[a+timedelta(days=i) for i in range((b-a).days+1)]
    if operation==0:return [d for d in days if d.day==_py_month_days(d.year,d.month)]
    if operation==1:return [d for d in days if d.day==1]
    if operation==2:
        out=[];current=date(a.year,a.month,_py_month_days(a.year,a.month))
        while current<=b:
            next_month=_py_add_months(date(current.year,current.month,1),1)
            if next_month is None:break
            if _py_month_days(current.year,current.month)!=_py_month_days(next_month.year,next_month.month) and current>=a:out.append(current)
            current=date(next_month.year,next_month.month,_py_month_days(next_month.year,next_month.month))
        return out
    if operation==3:return [date(y,12,31) for y in range(a.year,b.year+1) if a<=date(y,12,31)<=b]
    if operation==4:return [date(y,2,29) for y in range(a.year,b.year+1) if _py_leap(y) and a<=date(y,2,29)<=b]
    if operation==5:return [date(y,2,_py_month_days(y,2)) for y in range(a.year,b.year+1) if a<=date(y,2,_py_month_days(y,2))<=b]
    if operation in (6,7,8):
        out=[]; current=date(a.year,a.month,1)
        while current<=b:
            if operation==6:d=date(current.year,current.month,min(p,_py_month_days(current.year,current.month)))
            elif operation==7:d=date(current.year,current.month,(_py_month_days(current.year,current.month)+1)//2)
            else:
                try:d=current+timedelta(days=p-1)
                except OverflowError:break
            if a<=d<=b:out.append(d)
            next_current=_py_add_months(current,1)
            if next_current is None:break
            current=next_current
        return out
    if operation==9:
        out=[];k=1
        while True:
            d=_py_add_months(a,3*k)
            if d is None or d>b:break
            out.append(d);k+=1
        return out
    if operation in (10,11):
        out=[]
        for y in range(a.year+1,b.year+1):
            d=date(y,a.month,min(a.day,_py_month_days(y,a.month)))
            if operation in (11,24) and a.month==2 and a.day==29 and not _py_leap(y):d=date(y,3,1)
            if a<=d<=b:out.append(d)
        return out
    if operation==23:
        out=[]
        for y in range(a.year+100,b.year+1,100):
            d=date(y,a.month,min(a.day,_py_month_days(y,a.month)))
            if a<=d<=b:out.append(d)
        return out
    if operation==24:
        return [date(y,a.month,min(a.day,_py_month_days(y,a.month))) for y in range(a.year+1,b.year+1) if _py_leap(y)!=_py_leap(y-1) and a<=date(y,a.month,min(a.day,_py_month_days(y,a.month)))<=b]
    if operation==12:
        out=[];start=a
        while start<=b:
            end=date(start.year,start.month,_py_month_days(start.year,start.month))
            hi=min(end,b);out.append(start)
            if hi==b:break
            start=hi+timedelta(days=1)
        return out
    if operation==13:
        out=[];start=a
        while start<=b:
            out.append(start);status=_py_leap(start.year);year=start.year+1
            while year<=b.year and _py_leap(year)==status:year+=1
            if year>b.year:break
            start=date(year,1,1)
        return out
    if operation==14:
        return [date(y,m,31) for y in range(a.year,b.year+1) for m in (1,3,5,7,8,10,12) if a<=date(y,m,31)<=b]
    if operation==15:return [d for y in range(a.year,b.year+1) if _py_leap(y) for d in (date(y,3,31),date(y,6,30),date(y,9,30),date(y,12,31)) if a<=d<=b]
    if operation==16:return [date(y,2,28) for y in range(((a.year+99)//100)*100,b.year+1,100) if not _py_leap(y) and a<=date(y,2,28)<=b]
    if operation==17:return [date(y,2,29) for y in range(((a.year+399)//400)*400,b.year+1,400) if a<=date(y,2,29)<=b]
    if operation==18:
        return [date(y,m,_py_month_days(y,m)-1) for y in range(a.year,b.year+1) for m in range(1,13) if a<=date(y,m,_py_month_days(y,m)-1)<=b]
    if operation==19:
        return [date(y,m,d) for y in range(a.year,b.year+1) for m in range(1,13) for d in (2,3,5,7,11) if a<=date(y,m,d)<=b]
    if operation==20:
        return [date(y,p,_py_month_days(y,p)) for y in range(a.year,b.year+1) if a<=date(y,p,_py_month_days(y,p))<=b]
    if operation==21:
        out=[];current=a;prior=None
        while current<=b:
            capacity=_py_month_days(current.year,current.month)
            if capacity!=prior:out.append(current)
            prior=capacity;next_current=_py_add_months(date(current.year,current.month,1),1)
            if next_current is None:break
            current=next_current
        return out
    if operation==22:
        return [date(y,m,_py_month_days(y,m)) for y in range(a.year,b.year+1) for m in (6,12) if a<=date(y,m,_py_month_days(y,m))<=b]
    if operation==25:
        return [date(y,m,1) for y in range(a.year,b.year+1) for m in (1,4,7,10) if a<=date(y,m,1)<=b]
    if operation==26:
        leaps=[date(y,2,29) for y in range(a.year,b.year+1) if _py_leap(y) and a<=date(y,2,29)<=b]
        return [left+timedelta(days=(right-left).days//2) for left,right in zip(leaps,leaps[1:],strict=False)]
    if operation==27:
        out=[];d=date(a.year,a.month,1);prior=_py_month_days(d.year,d.month);d=_py_add_months(d,1)
        while d is not None and d<=b:
            capacity=_py_month_days(d.year,d.month)
            terminal=date(d.year,d.month,capacity)
            if capacity!=prior and terminal<=b:out.extend([d,terminal])
            prior=capacity;d=_py_add_months(d,1)
        return out
    if operation==28:return [date(y,2,1) for y in range(max(2,a.year),b.year+1) if _py_leap(y)!=_py_leap(y-1) and a<=date(y,2,1)<=b]
    if operation==29:return [d for y in range(a.year,b.year+1) if y%100==0 or y%400==0 for d in [date(y,2,29) if _py_leap(y) else date(y,2,28)] if a<=d<=b]
    return []


def _digest_dates(values: Iterable[date] | None) -> int:
    if values is None:
        return -1
    result=17
    for value in values:
        result=(result*1000003+value.year*10000+value.month*100+value.day)%1000000007
    return result


def _expected(case: TaskCase, *, hidden: bool, operation: int | None = None) -> int:
    op=case.operation if operation is None else operation
    if case.api_kind=="metric":
        a=date(1900,2,28) if hidden else date(2023,12,31);b=date(2000,3,1) if hidden else date(2024,3,1)
        return _metric_expected(op,a,b)
    if case.api_kind=="transform":
        a=date(2000,2,29) if hidden else date(2024,1,31);p=3 if hidden else 2
        value=_transform_value(op,a,p)
        if value is None:return -1
        return value.year*10000+value.month*100+value.day
    a=date(1899,12,1) if hidden else date(2023,12,15);b=date(2001,3,15) if hidden else date(2024,5,20);p=3 if hidden else 2
    return _digest_dates(_series_value(op,a,b,p))


def _behavior_signature(case:TaskCase)->dict[str,object]:
    records=[]
    if case.api_kind=="metric":
        intervals=[(date(1,1,1),date(1,1,1)),(date(1899,12,15),date(1900,3,2)),(date(1900,2,28),date(1900,3,1)),(date(1999,12,31),date(2000,3,1)),(date(2000,2,28),date(2000,3,1)),(date(2023,1,30),date(2024,5,20)),(date(2024,2,29),date(2024,2,29)),(date(9999,12,1),date(9999,12,31))]
        records=[_metric_expected(case.operation,first,last) for first,last in intervals]
    elif case.api_kind=="transform":
        values=[date(1,1,1),date(1900,2,28),date(2000,2,29),date(2024,1,31),date(2024,2,29),date(9999,12,31)]
        for value in values:
            for parameter in (-(2**31),-1,0,1,2,3,13,32,2**31-1):
                result=_safe_transform_value(case.operation,value,parameter)
                records.append(None if result is None else result.isoformat())
    else:
        intervals=[(date(1,1,1),date(1,2,1),1),(date(1899,12,15),date(1900,3,2),1),(date(1999,1,1),date(2005,12,31),31),(date(2000,2,29),date(2201,3,2),3),(date(2023,1,1),date(2024,12,31),3),(date(2024,2,29),date(2024,2,29),1),(date(9999,12,1),date(9999,12,31),1),(date(1900,1,1),date(1900,12,31),0),(date(2000,1,1),date(2000,12,31),13)]
        records=[]
        for first,last,parameter in intervals:
            values=_series_value(case.operation,first,last,parameter)
            records.append(None if values is None else [value.isoformat() for value in values])
    payload={"schema_version":1,"api_kind":case.api_kind,"probe_policy":"calendar-boundary-observable-v2","records":records}
    payload["signature"]=_sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode())
    return payload


def _negative_case(case: TaskCase) -> TaskCase:
    for offset in range(1, 30):
        wrong = replace(case, operation=(case.operation + offset) % 30)
        if (
            _expected(case, hidden=False) != _expected(wrong, hidden=False)
            and _expected(case, hidden=True) != _expected(wrong, hidden=True)
        ):
            return wrong
    _fail("invariant_not_enforced", case.task_id)


def _negative_source(case: TaskCase) -> str:
    wrong=_negative_case(case)
    text=_reference(wrong)
    return text.replace(wrong.class_name,case.class_name).replace(wrong.method_name,case.method_name).replace(f'"{wrong.task_id}.h"',f'"{case.task_id}.h"')


METRIC_PUBLIC_RULES = (
    "Return `serial(last) - serial(first)`, where adjacent civil dates differ by one.",
    "Count closed-span dates whose proleptic weekday is Monday through Friday; civil ordinal zero is Monday.",
    "Return the zero-based civil ordinal halfway from `first` to `last`, rounding toward `first`.",
    "Return the number of civil dates strictly between the endpoints: `max(0, serial(last)-serial(first)-1)`.",
    "Count month terminals `d` with `first <= d < last`; each is one crossed month boundary.",
    "Count January 1 boundaries `d` with `first < d <= last`.",
    "Count February 29 dates in the closed span.",
    "Count month-terminal dates in the closed span.",
    "For each contained month terminal add +1 for an even month and -1 for an odd month.",
    "Count whole clamped month anniversaries from `first` that do not pass `last`; an incomplete final month is excluded.",
    "Count whole clamped year anniversaries from `first` that do not pass `last`; February 29 clamps to February 28.",
    "Use 30E/360: `360*(Y2-Y1)+30*(M2-M1)+min(D2,30)-min(D1,30)`.",
    "Partition the closed span by calendar year and sum `floor(days_in_fragment*10000/days_in_year)` for each fragment.",
    "Return the number of distinct `(year, month)` pairs touched by the closed span.",
    "Return the number of distinct years touched by the closed span.",
    "Count closed-span dates whose month is February.",
    "Count closed-span dates whose containing month has 31 days.",
    "Count month terminals before `last` whose following month has a different capacity.",
    "Return `day_of_year(last)-day_of_year(first)`, with January 1 equal to zero.",
    "Sum the one-based month number of every date in the closed span.",
    "Sum the day-of-month number of every date in the closed span.",
    "Count closed-span dates whose year is Gregorian-leap.",
    "Count dates from March 1 through December 31 of leap years that lie in the closed span.",
    "Count closed-span dates whose year is divisible by 100.",
    "Return `days_in_month(last)-days_in_month(first)`.",
    "Return `(days_in_month(last)-last.day) - (days_in_month(first)-first.day)`.",
    "For every closed-span date add the number of later dates remaining in its month.",
    "For every closed-span date add `day*(day+1)/2`.",
    "Map each endpoint to `((year-1)%400)*366 + month*31 + day` and subtract the first coordinate from the last.",
    "Return `3*M + 7*Y + 11*L`, where M counts month ends, Y counts December 31, and L counts February 29 in the closed span.",
)

TRANSFORM_PUBLIC_RULES = (
    "`parameter` is a nonnegative day displacement; add it by civil ordinal and return null on year-range overflow.",
    "`parameter` is a nonnegative day displacement; subtract it by civil ordinal and return null before year 1.",
    "Add signed `parameter` months and clamp the day to the target month's last valid day.",
    "Add signed `parameter` months from the target month origin, then roll the original zero-based day offset forward.",
    "Add signed `parameter` months; if the input is a month terminal, force the result to the target terminal, otherwise clamp.",
    "Add signed `parameter` years and clamp February 29 to February 28 when required.",
    "Add signed `parameter` years; map February 29 to March 1 in a common target year.",
    "Ignore `parameter` and return the terminal of the input month.",
    "Ignore `parameter` and return the first month terminal strictly after the input.",
    "Ignore `parameter` and return the last month terminal strictly before the input.",
    "Require `parameter >= 1`; enumerate month terminals at or after the input and return the parameter-th one.",
    "Require `parameter >= 1`; return the terminal exactly `parameter` calendar months before the input month.",
    "Ignore `parameter` and return the terminal of the input's January-March, April-June, July-September, or October-December quarter.",
    "Ignore `parameter` and return December 31 of the input year.",
    "Require `1 <= parameter <= 12`; return the next terminal of that numbered month, using the current year when its month has not passed.",
    "Ignore `parameter` and return the first February 29 strictly after the input.",
    "Ignore `parameter` and return the last February 29 strictly before the input.",
    "Require `parameter >= 1`; return the parameter-th February 29 strictly after the input.",
    "Require `parameter >= 1`; return day `min(parameter, month_capacity)` in the input month.",
    "Require `parameter >= 1`; count from the input month's first day as ordinal one and roll excess into following months.",
    "Ignore `parameter`; map day `d` to `month_capacity-d+1` in the same month.",
    "Require `parameter >= 0`; subtract that many days from the input month's terminal.",
    "Ignore `parameter` and return the first day of the following month.",
    "Ignore `parameter` and return the first day of the input's canonical quarter.",
    "Ignore `parameter`; January-June maps to June 30 and July-December maps to December 31.",
    "Require `parameter >= 1`; inspect at most that many following months and return the first terminal with smaller capacity than the input month.",
    "Ignore `parameter` and return the input year's February terminal.",
    "Add `100*parameter` years and clamp the day to the target month capacity.",
    "Add `400*parameter` years; Gregorian-cycle identity preserves month and day, with null on range overflow.",
    "Require `parameter` to be a valid one-based ordinal day of the input year and return that date.",
)

SERIES_PUBLIC_RULES = (
    "Emit every month terminal in the closed span.",
    "Emit every first day of a month in the closed span.",
    "Emit a month terminal only when the immediately following month has different capacity.",
    "Emit every December 31 in the closed span.",
    "Emit every February 29 in the closed span.",
    "Emit each year's February terminal that lies in the closed span.",
    "Require `parameter >= 1`; in each touched month emit day `min(parameter, month_capacity)` when it lies in the span.",
    "Ignore `parameter`; in each touched month emit its midpoint day `(month_capacity+1)/2` when it lies in the span.",
    "Require `parameter >= 1`; treat it as a one-based offset from each month origin and emit each resulting in-span date.",
    "Ignore `parameter`; emit `first` advanced by 3, 6, 9, and further months, clamping the day of `first` to each target month's capacity, while the result remains in span.",
    "Ignore `parameter`; emit each later yearly anniversary of `first`, clamping to the target month capacity.",
    "Ignore `parameter`; emit each later yearly anniversary, moving a February 29 anniversary to March 1 in common years.",
    "Ignore `parameter`; emit `first`, then the first day after each completed month fragment through the fragment containing `last`.",
    "Ignore `parameter`; emit `first`, then January 1 whenever the Gregorian leap status differs from the preceding emitted run.",
    "Ignore `parameter`; emit terminals of 31-day months that lie in the closed span.",
    "Ignore `parameter`; in each Gregorian leap year emit the in-span canonical quarter terminals March 31, June 30, September 30, and December 31.",
    "Ignore `parameter`; emit February 28 for each non-leap century year in the closed span.",
    "Ignore `parameter`; emit February 29 for each year divisible by 400 in the closed span.",
    "Ignore `parameter`; emit the penultimate day of every touched month when that date lies in the span.",
    "Ignore `parameter`; in every touched month emit in-span days 2, 3, 5, 7, and 11.",
    "Require `1 <= parameter <= 12`; emit each in-span terminal of that numbered month.",
    "Ignore `parameter`; emit `first`, then the first month origin at each subsequent change in month capacity.",
    "Ignore `parameter`; emit June 30 and December 31 values in the closed span.",
    "Ignore `parameter`; add 100 years repeatedly to `first`, clamping each anniversary, and emit in-span results.",
    "Ignore `parameter`; emit later yearly anniversaries only when the target year's leap status differs from the previous year.",
    "Ignore `parameter`; emit January 1, April 1, July 1, and October 1 values in the closed span.",
    "Ignore `parameter`; for each consecutive pair of contained February 29 values emit their earlier-biased midpoint date.",
    "Ignore `parameter`; when adjacent months differ in capacity, emit the new month origin and terminal only if both lie in the span.",
    "Ignore `parameter`; emit February 1 when that year's February capacity differs from the previous year's.",
    "Ignore `parameter`; for century years emit February 28 in common centuries or February 29 in 400-year leap centuries, when in span.",
)


def _instructions(case: TaskCase) -> str:
    if case.api_kind=="metric":
        api=f"`{case.class_name}::{case.method_name}(Date first, Date last)` returns a scalar metric"
        result="Return `std::nullopt` for an invalid date or a reversed interval. The interval and endpoint convention are part of the named mechanism."
    elif case.api_kind=="transform":
        api=f"`{case.class_name}::{case.method_name}(Date value, int parameter)` returns one transformed date"
        result="Return `std::nullopt` for an invalid date, an invalid parameter, or a result outside years 1..9999."
    else:
        api=f"`{case.class_name}::{case.method_name}(Date first, Date last, int parameter)` returns an ordered date vector"
        result="Return `std::nullopt` for an invalid date, reversed interval, or parameter rejected by the observable rule. Output is chronological, contains no duplicates, and includes only boundaries selected by the mechanism."
    boundary_notes = {
        ("metric", 16): "A date contributes only when its containing month has 31 days; endpoint membership is closed.",
        ("metric", 17): "A transition contributes only at a month terminal whose successor month has a different capacity; the last endpoint has no successor in the span.",
        ("metric", 13): "A partial first or last calendar month still counts exactly once; equality therefore returns one touched month.",
        ("metric", 14): "A partial first or last calendar year still counts exactly once; equality therefore returns one touched year.",
        ("metric", 21): "Membership follows the leap status of each visited year and includes both valid endpoints.",
        ("metric", 22): "Only dates strictly after February 29 inside leap years contribute; common-year dates never contribute.",
        ("transform", 0): "Parameter zero preserves the input; positive displacement moves toward later ordinals and rejects upper-range overflow.",
        ("transform", 1): "Parameter zero preserves the input; positive displacement moves toward earlier ordinals and rejects lower-range underflow.",
        ("transform", 12): "The selected terminal belongs to the input's current three-month quarter and may equal the input.",
        ("transform", 13): "The selected terminal is December 31 of the input year and may equal the input.",
        ("transform", 20): "Reflect the input day across the containing month's midpoint: first maps to last and last maps to first; the parameter is ignored.",
        ("transform", 23): "The result is the first day of the input's current January/March/July/October quarter and may equal the input.",
        ("transform", 24): "January through June select June 30; July through December select December 31.",
        ("transform", 25): "Search at most `parameter` later months and select the first terminal whose month capacity is smaller than the input month's capacity.",
        ("transform", 27): "The parameter counts complete hundred-year cycles; February 29 clamps when the target century is common.",
        ("transform", 28): "The parameter counts complete 400-year Gregorian cycles, which preserve February 29 exactly.",
        ("series", 2): "Emit a month terminal only when the immediately following month has a different day capacity.",
        ("series", 3): "Only December 31 values inside the closed span are emitted.",
        ("series", 5): "Each spanned year's February terminal is considered independently and must lie inside the closed span.",
        ("series", 12): "The first output is exactly `first`; later outputs are month origins, and `last` is emitted only when it is itself such an origin.",
        ("series", 13): "The first output is exactly `first`, even mid-year; every later output is January 1 of a year whose leap status differs from the preceding run.",
        ("series", 21): "Emit the first day of every maximal run of consecutive months with equal capacity, including the first in-range run.",
        ("series", 23): "Advance in exact hundred-year steps and clamp each anniversary to the target month's capacity.",
        ("series", 24): "Emit an anniversary only where the target year's leap status differs from the previous year's status.",
        ("series", 25): "Only canonical quarter origins inside the closed span are emitted; equality emits one value only when the endpoint is a quarter origin.",
        ("series", 26): "Each midpoint uses half the positive ordinal gap rounded toward the earlier leap day; fewer than two contained leap days produce an engaged empty vector.",
        ("series", 27): "For each adjacent month-capacity change, emit the new month origin followed by that new month terminal.",
        ("series", 28): "Emit February 1 only when that year's February capacity differs from the preceding year; every emitted origin must lie inside the closed span.",
    }
    rules={"metric":METRIC_PUBLIC_RULES,"transform":TRANSFORM_PUBLIC_RULES,"series":SERIES_PUBLIC_RULES}[case.api_kind]
    boundary = boundary_notes.get((case.api_kind, case.operation), "Equality and the first and last representable civil dates follow the rule above; no implicit wraparound is allowed.")
    if case.api_kind=="metric":
        first,last=date(2023,12,31),date(2024,3,1)
        example=f"Calling `x.{case.method_name}({{2023,12,31}}, {{2024,3,1}})` on a `{case.class_name}` value returns `{_metric_expected(case.operation,first,last)}`."
    elif case.api_kind=="transform":
        value,parameter=date(2024,1,31),2
        expected=_safe_transform_value(case.operation,value,parameter)
        if expected is None:
            example=f"Calling `x.{case.method_name}({{2024,1,31}}, 2)` on a `{case.class_name}` value returns `std::nullopt`."
        else:
            example=f"Calling `x.{case.method_name}({{2024,1,31}}, 2)` on a `{case.class_name}` value returns `Date{{{expected.year},{expected.month},{expected.day}}}`."
    else:
        first,last,parameter=date(2023,12,15),date(2024,5,20),2
        values=_series_value(case.operation,first,last,parameter)
        if values is None:_fail("oracle_invalid_visible_example",case.task_id)
        rendered="{"+", ".join(f"{{{value.year},{value.month},{value.day}}}" for value in values)+"}"
        example=f"Calling `x.{case.method_name}({{2023,12,15}}, {{2024,5,20}}, 2)` on a `{case.class_name}` value returns the vector `{rendered}`."
    return f'''# Instructions\n\nImplement the complete C++17 API. {api}.\n\nThe operation is {case.mechanism}. Use the proleptic Gregorian rule: divisible by 4, except centuries unless divisible by 400. **Observable rule:** {rules[case.operation]} {result} {boundary}\n\n## Example\n\n{example}\n\nCompute every result from the civil calendar state passed in: system clock and time zone APIs, locale data, files, and networking have no place here, and a lookup table of precomputed answers would only cover the dates someone anticipated. All arithmetic must avoid undefined signed overflow. Empty collections are valid where the API returns a collection. Every returned series date must be valid, lie inside the requested closed span, be strictly increasing, and appear at most once.\n'''


def _cmake(case: TaskCase) -> str:
    header, source=_slug_files(case)
    return f'''cmake_minimum_required(VERSION 3.16)\nproject({case.task_id} LANGUAGES CXX)\nset(CMAKE_CXX_STANDARD 17)\nset(CMAKE_CXX_STANDARD_REQUIRED ON)\nset(CMAKE_CXX_EXTENSIONS OFF)\nadd_library(solution STATIC {source})\ntarget_include_directories(solution PUBLIC ${{CMAKE_CURRENT_SOURCE_DIR}})\ntarget_compile_options(solution PRIVATE -Wall -Wextra -Wpedantic -Werror)\nadd_executable(visible_test task_visible_test.cpp)\ntarget_link_libraries(visible_test PRIVATE solution)\ntarget_compile_options(visible_test PRIVATE -Wall -Wextra -Wpedantic -Werror)\nadd_executable(hidden_test .meta/task_hidden_test.cpp)\ntarget_link_libraries(hidden_test PRIVATE solution)\ntarget_compile_options(hidden_test PRIVATE -Wall -Wextra -Wpedantic -Werror)\nadd_executable(negative_test .meta/negative_false_substitute.cpp .meta/task_negative_test.cpp)\ntarget_include_directories(negative_test PRIVATE ${{CMAKE_CURRENT_SOURCE_DIR}})\ntarget_compile_options(negative_test PRIVATE -Wall -Wextra -Wpedantic -Werror)\nenable_testing()\nadd_test(NAME visible COMMAND visible_test)\nadd_test(NAME hidden COMMAND hidden_test)\n'''


def _task_files(case: TaskCase) -> dict[str,str]:
    header,source=_slug_files(case)
    config={"authors":["w8-biayn"],"blurb":case.title,"files":{"solution":[header,source],"test":["task_visible_test.cpp",".meta/task_hidden_test.cpp"],"example":[".meta/example.h",".meta/example.cpp"]}}
    provenance={"schema_version":"aider-local-provenance-v2","task_id":case.task_id,"family_id":FAMILY_ID,"lineage":"new-root","source_document":str(CURRICULUM),"authoring_origin":"clean-room deterministic repository generator","license":"Apache-2.0","generator":OWNER,"selected_prompts":list(SELECTED_PROMPTS),"status":"local candidate; not dataset admission"}
    return {
        ".docs/instructions.md":_instructions(case),
        ".meta/config.json":json.dumps(config,indent=2,sort_keys=True)+"\n",
        ".meta/provenance.json":json.dumps(provenance,indent=2,sort_keys=True)+"\n",
        ".meta/behavior-signature.json":json.dumps(_behavior_signature(case),indent=2,sort_keys=True)+"\n",
        ".meta/tests.toml":f'[visible]\ndescription = "2024 public boundary example for {case.mechanism}"\n\n[hidden]\ndescription = "1900/2000 Gregorian boundary, invalid input, and deterministic property"\n\n[topic_negative]\ndescription = "the adjacent plausible calendar mechanism compiles but must be rejected"\n',
        header:_header(case),source:_starter(case),".meta/example.h":_header(case),".meta/example.cpp":_reference(case),
        "task_visible_test.cpp":_test_source(case,hidden=False),".meta/task_hidden_test.cpp":_test_source(case,hidden=True),
        ".meta/negative_false_substitute.cpp":_negative_source(case),".meta/task_negative_test.cpp":_test_source(case,hidden=True),"CMakeLists.txt":_cmake(case),
    }


def _safe_output(out: Path) -> Path:
    resolved=out.resolve()
    expansion=EXPANSION_ROOT.resolve()
    if not resolved.is_relative_to(expansion):
        _fail("unsafe_output_root",f"{out} is not under {EXPANSION_ROOT}")
    for forbidden in (LEGACY_ROOT.resolve(),REVERIFY_ROOT.resolve()):
        if resolved==forbidden or resolved.is_relative_to(forbidden):_fail("unsafe_output_root",str(out))
    current=resolved
    while current!=expansion.parent:
        if current.exists() and current.is_symlink():_fail("unsafe_output_symlink",str(current))
        if current==expansion:break
        current=current.parent
    return resolved


def _task_inventory(root: Path) -> dict[str,Path]:
    result={}
    if not root.is_dir():return result
    for config in sorted(root.rglob(".meta/config.json")):
        if ".state" in config.parts:continue
        task=config.parent.parent
        qualified=task.relative_to(root).as_posix()
        if qualified in result:_fail("duplicate_task",qualified)
        result[qualified]=task
    return result


def _normalize(text: str) -> set[str]:
    text=re.sub(r"//.*?$|/\*.*?\*/", " ", text, flags=re.M|re.S)
    text=re.sub(r'"(?:\\.|[^"\\])*"', ' STRING ', text)
    text=re.sub(r"\b\d+\b", " NUMBER ", text.lower())
    return set(re.findall(r"[a-z_][a-z0-9_]*|==|!=|<=|>=|\+\+|--",text))


def _normalize_sequence(text:str)->tuple[str,...]:
    text=re.sub(r"//.*?$|/\*.*?\*/"," ",text,flags=re.M|re.S)
    text=re.sub(r'"(?:\\.|[^"\\])*"',' STRING ',text)
    text=re.sub(r"\b\d+\b"," NUMBER ",text.lower())
    return tuple(re.findall(r"[a-z_][a-z0-9_]*|==|!=|<=|>=|\+\+|--|[-+*/%<>{}()]",text))


def _semantic_text(root: Path) -> str:
    paths=list((root/".docs").glob("*.md"))+[p for p in root.glob("*.h")]+[root/".meta/example.cpp",root/"task_visible_test.cpp",root/".meta/task_hidden_test.cpp"]
    return "\n".join(path.read_text(encoding="utf-8") for path in paths if path.is_file())


def _hash_files(root:Path,patterns:Sequence[str])->str:
    digest=hashlib.sha256();paths=[]
    for pattern in patterns:paths.extend(root.glob(pattern))
    for path in sorted({path for path in paths if path.is_file()}):
        relative=path.relative_to(root).as_posix().encode();data=path.read_bytes()
        digest.update(relative+b"\0"+data+b"\0")
    return "sha256:"+digest.hexdigest()


def _role_hashes(root:Path)->dict[str,str]:
    result={
        "tree":_tree_hash(root),"public_contract":_hash_files(root,[".docs/*.md"]),
        "editable_starter":_hash_files(root,["*.h","*.cpp"]),"reference":_hash_files(root,[".meta/example.h",".meta/example.cpp"]),
        "visible_test":_hash_files(root,["task_visible_test.cpp"]),"hidden_test":_hash_files(root,[".meta/task_hidden_test.cpp"]),
        "metadata":_hash_files(root,[".meta/config.json",".meta/tests.toml"]),"provenance":_hash_files(root,[".meta/provenance.json"]),
        "negative":_hash_files(root,[".meta/negative_false_substitute.cpp",".meta/task_negative_test.cpp"]),"behavior_signature":_hash_files(root,[".meta/behavior-signature.json"]),
    }
    try:result["prompt"]=_sha256(build_prompt(load_task(root)).encode())
    except Exception:result["prompt"]=_hash_files(root,[".docs/*.md","*.h","*.cpp"])
    result["role_bundle"]=_sha256(json.dumps(result,sort_keys=True,separators=(",",":")).encode())
    return result


def _overlap(left:set[str],right:set[str])->float:
    return len(left&right)/max(1,len(left|right))


def _validate_cross_tree(out:Path)->dict[str,object]:
    cache_key=(str(LEGACY_ROOT.resolve()),str(REVERIFY_ROOT.resolve()))
    if cache_key in _SOURCE_INVENTORY_CACHE:return _SOURCE_INVENTORY_CACHE[cache_key]
    legacy=_task_inventory(LEGACY_ROOT);reverify=_task_inventory(REVERIFY_ROOT)
    existing_ids={path.name for path in [*legacy.values(),*reverify.values()]}
    collisions=sorted(existing_ids&{case.task_id for case in TASKS})
    if collisions:_fail("duplicate_task",",".join(collisions))
    inventories={"legacy":[{"task_id":task_id,"root":str(root),"roles":_role_hashes(root)} for task_id,root in sorted(legacy.items())],"reverify":[{"task_id":task_id,"root":str(root),"roles":_role_hashes(root)} for task_id,root in sorted(reverify.items())]}
    result={"schema_version":2,"legacy_count":len(legacy),"reverify_count":len(reverify),"candidate_count":len(TASKS),"id_collisions":[],"inventories":inventories,"inventory_hash":_sha256(json.dumps(inventories,sort_keys=True,separators=(",",":")).encode())}
    _SOURCE_INVENTORY_CACHE[cache_key]=result
    return result


def _archive_prior_evidence(out:Path)->None:
    state=out/".state";subject=state/"audit-subject.json"
    if not subject.is_file():return
    prior=json.loads(subject.read_text());short=prior.get("audit_subject_hash","unknown").split(":")[-1][:12]
    archive=state/"cycles"/f"prior-subject-{short}"
    if archive.exists():return
    archive.mkdir(parents=True)
    for name in ("audit-subject.json","docker-sanity-receipt.json","family-screen.json","prompt-boundary.json","lineage-screen.json","benchmark-screen.json","source-inventory.json","raw-proposals.json","selected-manifest.json","rejected-proposals.json"):
        source=state/name
        if source.is_file():shutil.copy2(source,archive/name)
    if (state/"receipts").is_dir():shutil.copytree(state/"receipts",archive/"receipts")


def materialize(out:Path,*,force:bool=False)->dict[str,object]:
    _safe_output(out);inventory=_validate_cross_tree(out)
    out.mkdir(parents=True,exist_ok=True)
    if force:_archive_prior_evidence(out)
    foreign=[]
    for child in out.iterdir():
        if child.name==".state":continue
        if not child.is_dir() or not (child/".meta/provenance.json").is_file():foreign.append(child.name);continue
        provenance=json.loads((child/".meta/provenance.json").read_text())
        if provenance.get("generator")!=OWNER:foreign.append(child.name)
    if foreign:_fail("foreign_generated_root",",".join(sorted(foreign)))
    existing={p.name for p in out.iterdir() if p.is_dir() and p.name!=".state"}
    expected={case.task_id for case in TASKS}
    if existing and existing!=expected and not force:_fail("generator_output_drift",f"existing={len(existing)} expected=90")
    if force:
        for task_id in sorted(existing):shutil.rmtree(out/task_id)
    elif existing:
        _fail("output_exists","pass --force for owner-controlled regeneration")
    for case in TASKS:
        root=out/case.task_id
        for relative,content in _task_files(case).items():_write(root/relative,content)
    state=out/".state";state.mkdir(parents=True,exist_ok=True)
    if force and (state/"receipts").is_dir():
        shutil.rmtree(state/"receipts")
    proposals=[{"proposal_id":f"proposal-{i+1:03d}","task_id":case.task_id,"cluster":case.cluster,"mechanism":case.mechanism,"decision":"selected-new-root"} for i,case in enumerate(TASKS)]
    rejected=[{"proposal_id":"control-domain-rename","reason":"domain/identifier rename only","decision":"reject"},{"proposal_id":"control-policy-only","reason":"constants/policy-only variant","decision":"reject"},{"proposal_id":"control-opposite-end","reason":"opposite-end variant","decision":"reject"}]
    _write_json(state/"raw-proposals.json",{"schema_version":1,"proposals":proposals+rejected})
    _write_json(state/"selected-manifest.json",{"schema_version":1,"family_id":FAMILY_ID,"requested_count":90,"retained_count":90,"tasks":proposals})
    _write_json(state/"rejected-proposals.json",{"schema_version":1,"rejected":rejected})
    _write_json(state/"source-inventory.json",inventory)
    return {"out":str(out),"tasks":90,"tree_hash":_tree_hash(out),"legacy_count":inventory["legacy_count"],"reverify_count":inventory["reverify_count"],"candidate_count":90,"id_collisions":[]}


def _feature_texts(root:Path)->dict[str,str]:
    header=next(root.glob("*.h")).read_text();reference=(root/".meta/example.cpp").read_text();docs=(root/".docs/instructions.md").read_text();visible=(root/"task_visible_test.cpp").read_text();hidden=(root/".meta/task_hidden_test.cpp").read_text();negative=(root/".meta/negative_false_substitute.cpp").read_text()
    core_region=reference.split("// CORE_BEGIN",1)[1].split("// CORE_END",1)[0]
    core=core_region.split("\n",1)[1] if "\n" in core_region else ""
    return {"public_api":header+docs,"owned_state_or_algorithm":core,"mutation_selection_rules":docs+core,"invalid_boundary_behavior":docs+hidden,"reference_control_flow":core,"deterministic_oracle":visible+hidden,"topic_negative_fixture":negative}


def _feature_scopes(root:Path)->dict[str,set[str]]:return {name:_normalize(value) for name,value in _feature_texts(root).items()}


def _pair_decision(left:Path,right:Path)->dict[str,object]:
    left_text=_feature_texts(left);right_text=_feature_texts(right);lf=_feature_scopes(left);rf=_feature_scopes(right);dimensions={}
    for name in HARD_RULE_DIMENSIONS:
        score=_overlap(lf[name],rf[name]);symmetric=len(lf[name]^rf[name]);left_sequence=_sha256("\n".join(_normalize_sequence(left_text[name])).encode());right_sequence=_sha256("\n".join(_normalize_sequence(right_text[name])).encode());distinct=score<1.0 and left_sequence!=right_sequence
        dimensions[name]={"overlap":round(score,6),"symmetric_difference":symmetric,"left_sequence":left_sequence,"right_sequence":right_sequence,"distinct":distinct}
    left_behavior=json.loads((left/".meta/behavior-signature.json").read_text())["signature"]
    right_behavior=json.loads((right/".meta/behavior-signature.json").read_text())["signature"]
    observable_distinct=left_behavior!=right_behavior
    left_contract=_sha256("\n".join(_normalize_sequence((left/".docs/instructions.md").read_text())).encode());right_contract=_sha256("\n".join(_normalize_sequence((right/".docs/instructions.md").read_text())).encode());contract_distinct=left_contract!=right_contract
    return {"left":left.name,"right":right.name,"dimensions":dimensions,"public_contract":{"left":left_contract,"right":right_contract,"distinct":contract_distinct},"observable_behavior":{"left":left_behavior,"right":right_behavior,"distinct":observable_distinct},"pass":contract_distinct and observable_distinct and all(v["distinct"] for v in dimensions.values())}


def _render_control(out:Path,name:str,operation:int)->Path:
    base=TASKS[0]
    control=replace(base,task_id=name,operation=0)
    root=out/".state/hard-rule-controls"/name
    if root.exists():shutil.rmtree(root)
    files=_task_files(control)
    if name=="constants-or-policy-only":
        original="return serial(b) - serial(a);";policy_core="return serial(b) - serial(a) + 1;"
        files[".meta/example.cpp"]=files[".meta/example.cpp"].replace(original,policy_core)
        for test_path in ("task_visible_test.cpp",".meta/task_hidden_test.cpp"):
            files[test_path]=re.sub(r"\*r(\d+)!=(-?\d+)LL",lambda match:f"*r{match.group(1)}!={int(match.group(2))+1}LL",files[test_path])
        behavior=json.loads(files[".meta/behavior-signature.json"]);behavior["records"]=[value+1 for value in behavior["records"]];behavior.pop("signature",None);behavior["signature"]=_sha256(json.dumps(behavior,sort_keys=True,separators=(",",":")).encode());files[".meta/behavior-signature.json"]=json.dumps(behavior,indent=2,sort_keys=True)+"\n"
    if name=="opposite-end-selection":
        original="return serial(b) - serial(a);"
        reversed_core="return serial(a) - serial(b);"
        files[".meta/example.cpp"]=files[".meta/example.cpp"].replace(original,reversed_core)
        for test_path in ("task_visible_test.cpp",".meta/task_hidden_test.cpp"):
            files[test_path]=re.sub(r"\*r(\d+)!=(-?\d+)LL",lambda match:f"*r{match.group(1)}!={-int(match.group(2))}LL",files[test_path])
        behavior=json.loads(files[".meta/behavior-signature.json"]);behavior["records"]=[-value for value in behavior["records"]];behavior.pop("signature",None);behavior["signature"]=_sha256(json.dumps(behavior,sort_keys=True,separators=(",",":")).encode());files[".meta/behavior-signature.json"]=json.dumps(behavior,indent=2,sort_keys=True)+"\n"
    for relative,content in files.items():_write(root/relative,content)
    return root


def verify_core(out:Path)->dict[str,object]:
    roots=[out/case.task_id for case in TASKS]
    if any(not (root/".meta/config.json").is_file() for root in roots):_fail("generator_output_drift","missing task root")
    scratch_parent=EXPANSION_ROOT/".state/generator-scratch"
    scratch_parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="calendar-expansion-fresh-",dir=scratch_parent) as temp:
        fresh=Path(temp)/"family";materialize(fresh,force=False)
        for case in TASKS:
            if _tree_hash(out/case.task_id)!=_tree_hash(fresh/case.task_id):_fail("generator_output_drift",case.task_id)
    prompt_records=[]
    for case,root in zip(TASKS,roots,strict=True):
        config=json.loads((root/".meta/config.json").read_text());solution=config["files"]["solution"]
        expected=list(_slug_files(case))
        if solution!=expected or any(p.startswith((".meta/",".docs/")) or p=="CMakeLists.txt" for p in solution):_fail("unsafe_path",case.task_id)
        prompt=build_prompt(load_task(root))
        for private in ("CMakeLists.txt","provenance.json","example.cpp","task_hidden_test","negative_false"):
            if private in prompt:_fail("prompt_contract_incomplete",f"{case.task_id}:{private}")
        if not all(name in prompt for name in expected):_fail("prompt_contract_incomplete",case.task_id)
        prompt_records.append({"task_id":case.task_id,"prompt_hash":_sha256(prompt.encode()),"solution":expected})
        if _expected(case,hidden=True)==_expected(_negative_case(case),hidden=True):_fail("invariant_not_enforced",case.task_id)
    pairs=[_pair_decision(left,right) for left,right in combinations(roots,2)]
    failed=[row for row in pairs if not row["pass"]]
    if failed:_fail("duplicate_family",f"{len(failed)} of {len(pairs)} pairs")
    controls={"domain-identifier-renamed":_render_control(out,"domain-identifier-renamed",0),"constants-or-policy-only":_render_control(out,"constants-or-policy-only",0),"opposite-end-selection":_render_control(out,"opposite-end-selection",0)}
    control_records=[]
    for name,root in controls.items():
        decision=_pair_decision(roots[0],root)
        if decision["pass"]:_fail("adversarial_clone_not_rejected",name)
        control_records.append({"control":name,"changed_tree":_tree_hash(root)!=_tree_hash(roots[0]),"decision":decision})
    existing=[*(_task_inventory(LEGACY_ROOT).values()),*(_task_inventory(REVERIFY_ROOT).values())]
    existing_tokens=[(root,_normalize(_semantic_text(root)),_sha256("\n".join(_normalize_sequence(_semantic_text(root))).encode()),_role_hashes(root)) for root in existing]
    lineage=[]
    for root in roots:
        tokens=_normalize(_semantic_text(root));sequence_hash=_sha256("\n".join(_normalize_sequence(_semantic_text(root))).encode());roles=_role_hashes(root);best=(0.0,"");matches=[]
        for other,other_tokens,other_sequence,other_roles in existing_tokens:
            score=_overlap(tokens,other_tokens)
            if score>best[0]:best=(score,str(other))
            role_matches=[name for name in ("prompt","public_contract","editable_starter","reference","visible_test","hidden_test","negative") if roles[name]==other_roles[name]]
            if role_matches or sequence_hash==other_sequence:matches.append({"root":str(other),"role_matches":role_matches,"normalized_sequence_match":sequence_hash==other_sequence})
        if best[0]>=0.90:_fail("duplicate_family",f"{root.name} ~= {best[1]} ({best[0]:.3f})")
        if any(row["normalized_sequence_match"] or any(name in row["role_matches"] for name in ("prompt","reference","hidden_test")) for row in matches):_fail("duplicate_family",f"exact cross-tree role collision:{root.name}")
        lineage.append({"task_id":root.name,"roles":roles,"normalized_sequence_hash":sequence_hash,"strongest_existing_overlap":round(best[0],6),"existing_root":best[1],"exact_matches":matches})
    if not HOLDOUT_ROOT.is_dir():_fail("benchmark_content_unavailable",str(HOLDOUT_ROOT))
    holdouts={p.name:p for p in HOLDOUT_ROOT.iterdir() if p.is_dir() and p.name in OFFICIAL_HOLDOUTS}
    if set(holdouts)!=OFFICIAL_HOLDOUTS:_fail("benchmark_content_unavailable",str(sorted(OFFICIAL_HOLDOUTS-set(holdouts))))
    contamination=[]
    holdout_tokens={name:_normalize(_semantic_text(root)) for name,root in holdouts.items()};holdout_inventory={name:{"tree_hash":_tree_hash(root),"roles":_role_hashes(root)} for name,root in sorted(holdouts.items())}
    for root in roots:
        tokens=_normalize(_semantic_text(root));scores={name:_overlap(tokens,value) for name,value in holdout_tokens.items()};name=max(scores,key=scores.get)
        if scores[name]>=0.82:_fail("benchmark_content_overlap",f"{root.name}:{name}:{scores[name]:.3f}")
        contamination.append({"task_id":root.name,"strongest_holdout":name,"overlap":round(scores[name],6)})
    state=out/".state"
    screen={"schema_version":1,"normalizer":NORMALIZER,"root_count":90,"pair_count":len(pairs),"expected_pair_count":4005,"dimensions":list(HARD_RULE_DIMENSIONS),"pairs":pairs,"controls":control_records,"status":"pass"}
    source_inventory=json.loads((state/"source-inventory.json").read_text())
    _write_json(state/"family-screen.json",screen);_write_json(state/"prompt-boundary.json",{"status":"pass","records":prompt_records});_write_json(state/"lineage-screen.json",{"status":"pass","policy":"role-hashes-plus-ordered-normalized-sequence-v2","source_inventory_hash":source_inventory["inventory_hash"],"existing_comparison_count":len(existing)*90,"records":lineage});_write_json(state/"benchmark-screen.json",{"status":"pass","policy":"digest-bound-role-and-semantic-screen-v2","holdout_count":26,"holdout_inventory":holdout_inventory,"holdout_inventory_hash":_sha256(json.dumps(holdout_inventory,sort_keys=True,separators=(",",":")).encode()),"comparison_count":26*90,"records":contamination})
    return {"root_count":90,"pair_count":4005,"control_count":3,"prompt_count":90,"existing_comparisons":len(existing)*90,"holdout_comparisons":2340,"status":"pass"}


DOCKER_SCRIPT = r'''set -eu
root=/tasks
work=/tmp/calendar-family
rm -rf "$work"
mkdir -p "$work"
run_subject() {
  task=$1
  kind=$2
  [ -f "$task/.meta/config.json" ] || return
  id=$(basename "$task")
  for mode in normal sanitizer; do
    dst="$work/$id-$mode"
    cp -R "$task" "$dst"
    cp "$dst/.meta/example.h" "$dst/$id.h"
    cp "$dst/.meta/example.cpp" "$dst/$id.cpp"
    flags=""
    if [ "$mode" = sanitizer ]; then flags="-fsanitize=address,undefined -fno-omit-frame-pointer"; fi
    if ! cmake -S "$dst" -B "$dst/build" -G "Unix Makefiles" -DCMAKE_CXX_FLAGS="$flags" >/tmp/configure.log 2>&1; then echo "FAIL|$kind|$id|$mode|configure"; cat /tmp/configure.log; exit 1; fi
    if ! cmake --build "$dst/build" --parallel 2 >/tmp/build.log 2>&1; then echo "FAIL|$kind|$id|$mode|build"; cat /tmp/build.log; exit 1; fi
    count=$(ctest --test-dir "$dst/build" -N | sed -n 's/.*Total Tests: //p')
    [ "$count" = 2 ]
    if ! timeout 20s env ASAN_OPTIONS=detect_leaks=0 ctest --test-dir "$dst/build" --output-on-failure >/tmp/ctest.log 2>&1; then echo "FAIL|$kind|$id|$mode|ctest"; cat /tmp/ctest.log; exit 1; fi
    set +e
    timeout 10s env ASAN_OPTIONS=detect_leaks=0 "$dst/build/negative_test" >/tmp/negative.log 2>&1
    negative=$?
    set -e
    [ "$negative" -ne 0 ]
    echo "RESULT|$kind|$id|$mode|$count|$negative"
  done
}
for task in "$root"/*; do
  [ -f "$task/.meta/config.json" ] || continue
  run_subject "$task" task
done
for task in "$root/.state/hard-rule-controls"/*; do
  [ -f "$task/.meta/config.json" ] || continue
  run_subject "$task" control
done
'''


def docker_sanity(out:Path)->dict[str,object]:
    verify_core(out)
    command=["docker","run","--rm","--network","none","-v",f"{out.resolve()}:/tasks:ro",SANITY_IMAGE,"sh","-lc",DOCKER_SCRIPT]
    completed=subprocess.run(command,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False,timeout=3600)
    if completed.returncode!=0:_fail("docker_sanity_failed",completed.stderr[-2000:]+completed.stdout[-2000:])
    records=[]
    for line in completed.stdout.splitlines():
        if not line.startswith("RESULT|"):continue
        _,kind,task_id,mode,count,negative=line.split("|")
        records.append({"kind":kind,"task_id":task_id,"mode":mode,"test_count":int(count),"negative_exit":int(negative)})
    expected_ids={case.task_id for case in TASKS}
    expected_controls={"domain-identifier-renamed","constants-or-policy-only","opposite-end-selection"}
    actual_tasks={row["task_id"] for row in records if row["kind"]=="task"}
    actual_controls={row["task_id"] for row in records if row["kind"]=="control"}
    if actual_tasks!=expected_ids or actual_controls!=expected_controls or len(records)!=186:_fail("test_discovery_failed",f"records={len(records)} tasks={len(actual_tasks)} controls={len(actual_controls)}")
    if any(row["test_count"]!=2 or row["negative_exit"]==0 for row in records):_fail("reference_tests_failed")
    image=subprocess.run(["docker","image","inspect",SANITY_IMAGE,"--format","{{.Id}}"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    if image.returncode!=0:_fail("grader_image_unavailable",image.stderr.strip())
    compiler=subprocess.run(["docker","run","--rm","--network","none",SANITY_IMAGE,"sh","-lc",'tool=$(command -v c++); printf "%s\\n" "$tool"; sha256sum "$tool"; c++ --version'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    cmake=subprocess.run(["docker","run","--rm","--network","none",SANITY_IMAGE,"cmake","--version"],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    compiler_lines=compiler.stdout.splitlines();compiler_path=compiler_lines[0] if len(compiler_lines)>0 else "unknown";compiler_hash=("sha256:"+compiler_lines[1].split()[0]) if len(compiler_lines)>1 else "unknown";compiler_version=compiler_lines[2] if len(compiler_lines)>2 else "unknown";policy_hash=_sha256((DOCKER_SCRIPT+NORMALIZER+SANITY_IMAGE).encode())
    receipt={"schema_version":2,"family_id":FAMILY_ID,"status":"pass","evidence_class":"locked_docker_oracle","locked_oracle":True,"network_policy":"none","image":SANITY_IMAGE,"image_id":image.stdout.strip(),"compiler_path":compiler_path,"compiler_hash":compiler_hash,"compiler_version":compiler_version,"cmake_version":cmake.stdout.splitlines()[0] if cmake.stdout else "unknown","policy_hash":policy_hash,"owner_hash":_sha256(Path(__file__).read_bytes()),"family_tree_hash":_tree_hash(out),"normal_records":93,"sanitizer_records":93,"task_records":180,"control_records":6,"records":records,"commands":[command]}
    _write_json(out/".state/docker-sanity-receipt.json",receipt)
    for case in TASKS:
        task_records=[row for row in records if row["kind"]=="task" and row["task_id"]==case.task_id]
        _write_json(out/".state/receipts"/f"{case.task_id}.json",{"schema_version":2,"task_id":case.task_id,"status":"local_family_verified_pending_fresh_audit","roles":_role_hashes(out/case.task_id),"owner_hash":receipt["owner_hash"],"image_id":receipt["image_id"],"compiler_path":compiler_path,"compiler_hash":compiler_hash,"compiler_version":compiler_version,"policy_hash":policy_hash,"network_policy":"none","commands":[command],"records":task_records,"prompt_boundary":"pass","family_screen":"pass","lineage_screen":"pass","benchmark_screen":"pass","dataset_handoff":"not_requested"})
    active_receipts={path.stem for path in (out/".state/receipts").glob("*.json")}
    if active_receipts!=expected_ids:
        _fail("active_receipt_set_mismatch",str(sorted(active_receipts^expected_ids)))
    return receipt


HOST_VERIFY_POLICY = "host-normal-plus-fresh-asan-ubsan-v1"


def _host_verify_subject(subject: Path, kind: str, work_parent: Path) -> list[dict[str, object]]:
    """Build and run one task or control root on the host in both modes."""
    task_id = subject.name
    records = []
    for mode in ("normal", "sanitizer"):
        dst = work_parent / f"{task_id}-{mode}"
        shutil.copytree(subject, dst)
        shutil.copy2(dst / ".meta/example.h", dst / f"{task_id}.h")
        shutil.copy2(dst / ".meta/example.cpp", dst / f"{task_id}.cpp")
        flags = "-fsanitize=address,undefined -fno-omit-frame-pointer" if mode == "sanitizer" else ""
        configure = subprocess.run(
            ["cmake", "-S", str(dst), "-B", str(dst / "build"), "-G", "Unix Makefiles",
             f"-DCMAKE_CXX_FLAGS={flags}"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if configure.returncode != 0:
            _fail("reference_compile_failed", f"{kind}|{task_id}|{mode}|configure\n{configure.stderr[-1500:]}")
        build = subprocess.run(
            ["cmake", "--build", str(dst / "build"), "--parallel", "2"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if build.returncode != 0:
            _fail("reference_compile_failed", f"{kind}|{task_id}|{mode}|build\n{build.stderr[-1500:]}")
        discover = subprocess.run(
            ["ctest", "--test-dir", str(dst / "build"), "-N"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        match = re.search(r"Total Tests: (\d+)", discover.stdout)
        count = int(match.group(1)) if match else 0
        if count != 2:
            _fail("test_discovery_failed", f"{kind}|{task_id}|{mode}|count={count}")
        env = dict(os.environ, ASAN_OPTIONS="detect_leaks=0")
        run = subprocess.run(
            ["ctest", "--test-dir", str(dst / "build"), "--output-on-failure"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, env=env, timeout=120)
        if run.returncode != 0:
            _fail("reference_tests_failed", f"{kind}|{task_id}|{mode}|ctest\n{run.stdout[-1500:]}")
        negative = subprocess.run(
            [str(dst / "build" / "negative_test")],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, env=env, timeout=60)
        if negative.returncode == 0:
            _fail("invariant_not_enforced", f"{kind}|{task_id}|{mode}|negative accepted")
        records.append({"kind": kind, "task_id": task_id, "mode": mode,
                        "test_count": count, "negative_exit": negative.returncode})
    return records


def verify_host(out: Path, *, workers: int = 8) -> dict[str, object]:
    """Host-side normal plus fresh ASan/UBSan reference verification.

    This is the campaign done gate when Docker is unavailable: it mirrors the
    DOCKER_SCRIPT protocol on the host toolchain for every root and every
    hard-rule control, including negative-fixture rejection.
    """
    verify_core(out)
    subjects = [(out / case.task_id, "task") for case in TASKS]
    controls_dir = out / ".state/hard-rule-controls"
    controls = sorted(path for path in controls_dir.iterdir() if path.is_dir()) if controls_dir.is_dir() else []
    if {path.name for path in controls} != {"domain-identifier-renamed", "constants-or-policy-only", "opposite-end-selection"}:
        _fail("generator_output_drift", "hard-rule controls missing")
    subjects += [(path, "control") for path in controls]
    scratch_parent = EXPANSION_ROOT / ".state/generator-scratch"
    scratch_parent.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="calendar-host-verify-", dir=scratch_parent) as temp:
        def run_one(item: tuple[Path, str]) -> list[dict[str, object]]:
            subject, kind = item
            work = Path(temp) / f"{kind}-{subject.name}"
            work.mkdir()
            return _host_verify_subject(subject, kind, work)
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            for result in pool.map(run_one, subjects):
                records.extend(result)
    expected_ids = {case.task_id for case in TASKS}
    actual_tasks = {row["task_id"] for row in records if row["kind"] == "task"}
    actual_controls = {row["task_id"] for row in records if row["kind"] == "control"}
    if actual_tasks != expected_ids or len(actual_controls) != 3 or len(records) != 186:
        _fail("test_discovery_failed", f"records={len(records)} tasks={len(actual_tasks)} controls={len(actual_controls)}")
    compiler_path = shutil.which("c++") or "unknown"
    compiler_hash = _sha256(Path(compiler_path).read_bytes()) if compiler_path != "unknown" else "unknown"
    compiler_version = subprocess.run(["c++", "--version"], text=True, stdout=subprocess.PIPE, check=False).stdout.splitlines()[0]
    cmake_version = subprocess.run(["cmake", "--version"], text=True, stdout=subprocess.PIPE, check=False).stdout.splitlines()[0]
    policy_hash = _sha256((HOST_VERIFY_POLICY + NORMALIZER).encode())
    receipt = {
        "schema_version": 1, "family_id": FAMILY_ID, "status": "pass",
        "evidence_class": "host_verify", "locked_oracle": False,
        "network_policy": "not_applicable_host",
        "compiler_path": compiler_path, "compiler_hash": compiler_hash,
        "compiler_version": compiler_version, "cmake_version": cmake_version,
        "policy_hash": policy_hash, "owner_hash": _sha256(Path(__file__).read_bytes()),
        "family_tree_hash": _tree_hash(out),
        "normal_records": 93, "sanitizer_records": 93,
        "task_records": 180, "control_records": 6, "records": records,
        "commands": ["cmake -S <dst> -B <dst>/build -G 'Unix Makefiles' -DCMAKE_CXX_FLAGS=<mode flags>",
                     "cmake --build <dst>/build --parallel 2",
                     "ctest --test-dir <dst>/build -N",
                     "ctest --test-dir <dst>/build --output-on-failure",
                     "<dst>/build/negative_test (must exit nonzero)"],
    }
    _write_json(out / ".state/host-verify-receipt.json", receipt)
    return receipt


def creator_preflight(out:Path)->dict[str,object]:
    core=verify_core(out);receipt_path=out/".state/docker-sanity-receipt.json"
    if not receipt_path.is_file():_fail("docker_sanity_not_completed",str(receipt_path))
    receipt=json.loads(receipt_path.read_text())
    if receipt.get("family_tree_hash")!=_tree_hash(out):_fail("stale_receipt")
    state=out/".state";state_files=("raw-proposals.json","selected-manifest.json","rejected-proposals.json","source-inventory.json","prompt-boundary.json","family-screen.json","lineage-screen.json","benchmark-screen.json","docker-sanity-receipt.json")
    expected_receipts={case.task_id for case in TASKS};active_receipts={path.stem for path in (state/"receipts").glob("*.json")}
    if active_receipts!=expected_receipts:_fail("active_receipt_set_mismatch",str(sorted(active_receipts^expected_receipts)))
    state_hashes={name:_sha256((state/name).read_bytes()) for name in state_files};root_roles={case.task_id:_role_hashes(out/case.task_id) for case in TASKS};receipt_hashes={case.task_id:_sha256((state/"receipts"/f"{case.task_id}.json").read_bytes()) for case in TASKS};control_roles={root.name:_role_hashes(root) for root in sorted((state/"hard-rule-controls").iterdir()) if root.is_dir()}
    subject={"schema_version":2,"family_id":FAMILY_ID,"tree_hash":_tree_hash(out),"owner_hash":_sha256(Path(__file__).read_bytes()),"curriculum_hash":_sha256(CURRICULUM.read_bytes()),"spec_hash":_sha256(FAMILY_SPEC.read_bytes()),"focused_test_hash":_sha256(Path(FOCUSED_TEST).read_bytes()),"remedy_record_hash":_sha256(REMEDY_RECORD.read_bytes()),"state_hashes":state_hashes,"root_roles":root_roles,"receipt_hashes":receipt_hashes,"control_roles":control_roles,"grader_identity":{"image_id":receipt["image_id"],"compiler_path":receipt["compiler_path"],"compiler_hash":receipt["compiler_hash"],"compiler_version":receipt["compiler_version"],"cmake_version":receipt["cmake_version"],"policy_hash":receipt["policy_hash"],"network_policy":receipt["network_policy"]},"root_count":90}
    subject_hash=_sha256(json.dumps(subject,sort_keys=True,separators=(",",":")).encode());subject["audit_subject_hash"]=subject_hash
    _write_json(state/"audit-subject.json",subject)
    prior_paths=sorted((state/"cycles").glob("cycle-*-creator-preflight.json"));same=next((path for path in prior_paths if json.loads(path.read_text()).get("audit_subject_hash")==subject_hash),None)
    if same:return json.loads(same.read_text())
    cycle_number=max([int(path.name.split("-")[1]) for path in prior_paths],default=0)+1
    replaced=["calendar-absolute-day-gap","calendar-endpoint-month-index-delta","leapseries-eom-monthly-anchor","leapseries-month-fragment-lengths","leapseries-leap-status-run-lengths","leapseries-month-capacity-vector","leapseries-leap-year-vector","leapseries-month-end-offsets","leapseries-month-start-offsets","leapseries-monthly-proration-vector","leapseries-leap-gap-vector"]
    findings=["CAL-C01-004","CAL-C01-007",*[f"CAL-C02-{index:03d}" for index in range(1,6)]]
    cycle={"schema_version":2,"cycle":cycle_number,"created_at":datetime.now(timezone.utc).isoformat(),"state":"creator_preflight","audit_subject_hash":subject_hash,"subject":subject,"prior_audit":{"subject_hash":"sha256:65f5b236a8318ec356901aed46b4b12e0c412d9c2ae42c73ef8e34e6e9e665e5","report":"docs/aider-tasks-spec/aider-dates-and-clocks/audits/calendar-boundary-expansion-cycle-002-independent-reaudit.md","report_hash":"sha256:0b8eeca4fce067189f692c550e456c86a03fa8470ae0aa9c3aa6d51513a2eec9","finding_ids":findings},"remediation":{"remedy_record":str(REMEDY_RECORD),"dispositions":{finding:"owner_changed_regenerated_pending_fresh_audit" for finding in findings}},"retained_ids":[case.task_id for case in TASKS],"replaced_ids":replaced,"rejected_proposals":["control-domain-rename","control-policy-only","control-opposite-end"],"blocked_ids":[],"invalidated_evidence":["cycle-002 docker receipt","cycle-002 per-root receipts","cycle-002 audit subject"],"creator_preflight":core,"terminal_status":"pending_fresh_independent_audit"}
    cycle_path=state/"cycles"/f"cycle-{cycle_number:03d}-creator-preflight.json"
    _write_json(cycle_path,cycle)
    return cycle


def main(argv:Sequence[str]|None=None)->int:
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--out",type=Path,default=DEFAULT_OUT);parser.add_argument("--force",action="store_true");parser.add_argument("--verify-core",action="store_true");parser.add_argument("--verify-host",action="store_true");parser.add_argument("--docker-sanity",action="store_true");parser.add_argument("--creator-preflight",action="store_true");args=parser.parse_args(argv)
    if args.force or not args.out.exists():print(json.dumps(materialize(args.out,force=args.force),sort_keys=True))
    if args.verify_core:print(json.dumps(verify_core(args.out),sort_keys=True))
    if args.verify_host:print(json.dumps({key:value for key,value in verify_host(args.out).items() if key!="records"},sort_keys=True))
    if args.docker_sanity:print(json.dumps(docker_sanity(args.out),sort_keys=True))
    if args.creator_preflight:print(json.dumps(creator_preflight(args.out),sort_keys=True))
    if not any((args.force,args.verify_core,args.verify_host,args.docker_sanity,args.creator_preflight)):print(json.dumps(materialize(args.out,force=False),sort_keys=True))
    return 0


if __name__=="__main__":raise SystemExit(main())
