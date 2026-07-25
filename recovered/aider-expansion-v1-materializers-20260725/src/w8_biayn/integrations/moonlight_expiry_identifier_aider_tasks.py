"""Own the 90-root date-bearing identifier expansion family.

The generated roots are local candidate artifacts only.  This owner refuses
the two legacy trees, validates cross-tree identity/lineage before writing,
and keeps mutable receipts beneath the expansion family's ``.state`` folder.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable, Sequence

from w8_biayn.integrations.moonlight_aider_task_eval import build_prompt, load_task
from w8_biayn.integrations.moonlight_aider_task_sft import (
    build_assistant_response,
    load_example_files_from_config,
)
from w8_biayn.integrations.moonlight_expiry_identifier_cases import CASES, Case


DEFAULT_OUT = Path(
    ".w8-biayn/data/aider-tasks-expansion-v1/validation-input-parsing/"
    "date-bearing-identifiers"
)
LEGACY_ROOT = Path(".w8-biayn/data/aider-tasks")
REVERIFY_ROOT = Path(".w8-biayn/data/aider-tasks-reverify")
EXPANSION_ROOT = Path(".w8-biayn/data/aider-tasks-expansion-v1")
CURRICULUM = Path(
    "docs/aider-synthetic/aider-synthetic-validation-input-parsing/"
    "GLM47_FLASH_AIDER_POLYGLOT_CPP_DATES_AND_EXPIRATION_POLICIES_CURRICULUM.md"
)
FAMILY_SPEC = Path(
    "docs/aider-tasks-spec/aider-validation-input-parsing/"
    "date-bearing-identifiers.md"
)
FOCUSED_TEST = Path("tests/test_moonlight_expiry_identifier_aider_tasks.py")
PROMPT_PATH = Path("docs/aider-tasks-spec/prompts/implement-family-for-sft.md")
FAMILY_ID = "aider-expansion-v1-date-bearing-identifiers-v1"
SCHEMA = "aider-expiry-identifiers-materialization-v1"
NORMALIZER = "expiry-identifiers-role-aware-cpp-5gram-v2-fail-closed"
SANITY_IMAGE = (
    "w8-biayn-polyglot-cpp@sha256:"
    "4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
)
HOLDOUT_ROOT = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_specific_negative_fixture",
)
HARD_RULE_LIMITS = {
    **{dimension: 0.95 for dimension in HARD_RULE_DIMENSIONS},
    # Test programs are intentionally compact. Grammar-shaped literal tokens
    # preserve parser evidence while a high threshold still rejects the exact
    # coherent controls, whose normalized oracle containment is 1.0.
    "deterministic_oracle": 0.99,
}
OFFICIAL_HOLDOUTS = frozenset(
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


def _fail(code: str, detail: str) -> None:
    raise RuntimeError(f"{code}: {detail}")


def _sha_bytes(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _sha_file(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "not_available"
    for path in sorted(
        item
        for item in root.rglob("*")
        if item.is_file() and ".state" not in item.parts
    ):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _class_name(task_id: str) -> str:
    return "".join(part.capitalize() for part in task_id.split("-"))


def _named(task_id: str) -> tuple[str, str]:
    return f"{task_id}.h", f"{task_id}.cpp"


def _date_literal(value: dt.date) -> str:
    return f"CivilDate{{{value.year},{value.month},{value.day}}}"


def _days_in_month(year: int, month: int) -> int:
    if month == 12:
        following = dt.date(year + 1, 1, 1)
    else:
        following = dt.date(year, month + 1, 1)
    return (following - dt.timedelta(days=1)).day


def _packed(year: int, month: int, day: int) -> tuple[int, int]:
    value = (year << 9) | (month << 5) | day
    check = 0
    for shift in (0, 8, 16, 24):
        check ^= (value >> shift) & 0xFF
    return value, check


def _fixture(case: Case) -> tuple[str, dt.date, str]:
    name = f"{_class_name(case.task_id)}Input"
    parser = case.parser_index
    if parser == 0:
        return f'{name}{{"2025-06"}}', dt.date(2025, 6, 30), f'{name}{{"2025-6"}}'
    if parser == 1:
        return (
            f'{name}{{"QA","20250630-8"}}',
            dt.date(2025, 6, 30),
            f'{name}{{"QA","20250630-7"}}',
        )
    if parser == 2:
        return (
            f'{name}{{"2025-181",2000}}',
            dt.date(2025, 6, 30),
            f'{name}{{"2025-366",2000}}',
        )
    if parser == 3:
        return (
            f'{name}{{"2025W261",40}}',
            dt.date(2025, 6, 25),
            f'{name}{{"2025W411",40}}',
        )
    if parser == 4:
        return (
            f'{name}{{"FY2025-Q2",1}}',
            dt.date(2025, 6, 30),
            f'{name}{{"FY2025-Q5",1}}',
        )
    if parser == 5:
        return (
            f'{name}{{"06/25",2000}}',
            dt.date(2025, 6, 30),
            f'{name}{{"13/25",2000}}',
        )
    if parser == 6:
        return (
            f'{name}{{"0",CivilDate{{2025,6,30}}}}',
            dt.date(2025, 6, 30),
            f'{name}{{"!",CivilDate{{2025,6,30}}}}',
        )
    if parser == 7:
        value, check = _packed(2025, 6, 30)
        return (
            f"{name}{{{value}U,{check}U}}",
            dt.date(2025, 6, 30),
            f"{name}{{{value}U,{check ^ 1}U}}",
        )
    if parser == 8:
        return (
            f'{name}{{"S2-2025",false}}',
            dt.date(2025, 6, 30),
            f'{name}{{"S5-2025",false}}',
        )
    return (
        f"{name}{{0LL,60}}",
        dt.date(2000, 1, 1),
        f"{name}{{0LL,900}}",
    )


def _common_header(case: Case) -> str:
    guard = case.task_id.upper().replace("-", "_") + "_H"
    class_name = _class_name(case.task_id)
    input_name = f"{class_name}Input"
    parser = case.parser
    policy = case.policy_index
    input_fields = "; ".join(field.strip() for field in parser.input_fields.split(";"))
    result_declarations = {
        0: "",
        1: "",
        2: "struct BusinessWindow { CivilDate cutoff{}; bool open=false; };",
        3: "struct ShelfDecision { CivilDate expiry{}; ExpiryState state=ExpiryState::invalid; };",
        4: "",
        5: "struct RenewalPlan { CivilDate opens{}; CivilDate closes{}; ExpiryState state=ExpiryState::invalid; };",
        6: "struct ExposureScore { int remaining_days=0; int score=0; bool valid=false; };",
        7: "struct AdmissionDecision { bool admitted=false; ExpiryState state=ExpiryState::invalid; };",
        8: "",
    }[policy]
    methods = {
        0: f"ExpiryState classify({input_name} input, CivilDate reference) const;",
        1: f"std::optional<CivilDate> grace_cutoff({input_name} input, CivilDate reference, int grace_days) const;",
        2: f"BusinessWindow business_window({input_name} input, CivilDate reference, int business_grace) const;",
        3: f"ShelfDecision shelf_decision({input_name} input, CivilDate reference, int shelf_months) const;",
        4: f"ExpiryState adjudicate({input_name} input, CivilDate reference, std::optional<CivilDate> revoked_on) const;",
        5: f"RenewalPlan renewal_plan({input_name} input, CivilDate reference, int notice_days) const;",
        6: f"ExposureScore exposure({input_name} input, CivilDate reference, int units) const;",
        7: f"AdmissionDecision admit({input_name} input, CivilDate reference, CivilDate opens, CivilDate closes) const;",
        8: f"std::optional<int> remaining({input_name} input, CivilDate reference, bool inclusive) const;",
    }[policy]
    return f"""#ifndef {guard}
#define {guard}
#include <cstdint>
#include <optional>
#include <string>
namespace expiry_identifiers {{
struct CivilDate {{ int year=0; int month=0; int day=0; }};
inline bool operator==(CivilDate left, CivilDate right) {{ return left.year==right.year && left.month==right.month && left.day==right.day; }}
enum class ExpiryState {{ invalid, active, warning, expired, revoked, early, open, closed }};
struct {input_name} {{ {input_fields}; }};
{result_declarations}
class {class_name} {{
public:
  {methods}
}};
}}  // namespace expiry_identifiers
#endif
"""


_SUPPORT = r'''
namespace {
[[maybe_unused]] bool leap(int year) { return year % 4 == 0 && (year % 100 != 0 || year % 400 == 0); }
[[maybe_unused]] int month_days(int year, int month) {
  static const int table[] = {0,31,28,31,30,31,30,31,31,30,31,30,31};
  if (month < 1 || month > 12) return 0;
  return month == 2 && leap(year) ? 29 : table[month];
}
[[maybe_unused]] bool valid(CivilDate value) {
  return value.year >= 1 && value.year <= 9999 && value.month >= 1 &&
         value.month <= 12 && value.day >= 1 && value.day <= month_days(value.year, value.month);
}
[[maybe_unused]] long long serial(CivilDate value) {
  int year = value.year;
  unsigned month = static_cast<unsigned>(value.month);
  unsigned day = static_cast<unsigned>(value.day);
  year -= month <= 2U;
  const int era = (year >= 0 ? year : year - 399) / 400;
  const unsigned year_of_era = static_cast<unsigned>(year - era * 400);
  const unsigned day_of_year = (153U * (month + (month > 2U ? static_cast<unsigned>(-3) : 9U)) + 2U) / 5U + day - 1U;
  const unsigned day_of_era = year_of_era * 365U + year_of_era / 4U - year_of_era / 100U + day_of_year;
  return static_cast<long long>(era) * 146097LL + static_cast<long long>(day_of_era);
}
[[maybe_unused]] CivilDate civil(long long value) {
  const long long era = (value >= 0 ? value : value - 146096LL) / 146097LL;
  const unsigned day_of_era = static_cast<unsigned>(value - era * 146097LL);
  const unsigned year_of_era = (day_of_era - day_of_era / 1460U + day_of_era / 36524U - day_of_era / 146096U) / 365U;
  int year = static_cast<int>(year_of_era) + static_cast<int>(era) * 400;
  const unsigned day_of_year = day_of_era - (365U * year_of_era + year_of_era / 4U - year_of_era / 100U);
  const unsigned shifted_month = (5U * day_of_year + 2U) / 153U;
  const unsigned day = day_of_year - (153U * shifted_month + 2U) / 5U + 1U;
  const unsigned month = shifted_month + (shifted_month < 10U ? 3U : static_cast<unsigned>(-9));
  year += month <= 2U;
  CivilDate result{year, static_cast<int>(month), static_cast<int>(day)};
  return valid(result) ? result : CivilDate{};
}
[[maybe_unused]] int compare(CivilDate left, CivilDate right) {
  const long long a = serial(left), b = serial(right);
  return a < b ? -1 : (a > b ? 1 : 0);
}
[[maybe_unused]] CivilDate add_days(CivilDate value, long long days) {
  if (!valid(value)) return {};
  const long long origin = serial(value);
  const long long minimum = serial(CivilDate{1,1,1});
  const long long maximum = serial(CivilDate{9999,12,31});
  if (days < minimum-origin || days > maximum-origin) return {};
  CivilDate result = civil(origin + days);
  return valid(result) ? result : CivilDate{};
}
[[maybe_unused]] CivilDate add_months(CivilDate value, int months) {
  if (!valid(value)) return {};
  const long long index = static_cast<long long>(value.year - 1) * 12LL + value.month - 1 + months;
  if (index < 0 || index >= 9999LL * 12LL) return {};
  const int year = static_cast<int>(index / 12LL) + 1;
  const int month = static_cast<int>(index % 12LL) + 1;
  return {year, month, std::min(value.day, month_days(year, month))};
}
[[maybe_unused]] CivilDate add_business_days(CivilDate value, int count) {
  if (!valid(value) || count < 0) return {};
  if (static_cast<long long>(count) > serial(CivilDate{9999,12,31})-serial(value)) return {};
  while (count > 0) {
    value = add_days(value, 1);
    if (!valid(value)) return {};
    const int weekday = static_cast<int>((serial(value) + 2LL) % 7LL + 7LL) % 7;
    if (weekday < 5) --count;
  }
  return value;
}
[[maybe_unused]] bool digits(const std::string& text, std::size_t begin, std::size_t count) {
  if (begin + count > text.size()) return false;
  for (std::size_t i = begin; i < begin + count; ++i) if (text[i] < '0' || text[i] > '9') return false;
  return true;
}
[[maybe_unused]] int number(const std::string& text, std::size_t begin, std::size_t count) {
  int value = 0;
  for (std::size_t i = begin; i < begin + count; ++i) value = value * 10 + text[i] - '0';
  return value;
}
'''


def _parser_source(case: Case) -> str:
    name = f"{_class_name(case.task_id)}Input"
    parser = case.parser_index
    if parser == 0:
        return f'''std::optional<CivilDate> parse(const {name}& input) {{
  if (input.token.size()!=7 || input.token[4]!='-' || !digits(input.token,0,4) || !digits(input.token,5,2)) return std::nullopt;
  const int year=number(input.token,0,4), month=number(input.token,5,2);
  CivilDate result{{year,month,month_days(year,month)}};
  return valid(result) ? std::optional<CivilDate>(result) : std::nullopt;
}}
'''
    if parser == 1:
        return f'''std::optional<CivilDate> parse(const {name}& input) {{
  if (input.issuer.empty() || input.stamp.size()!=10 || input.stamp[8]!='-' || !digits(input.stamp,0,8) || !digits(input.stamp,9,1)) return std::nullopt;
  int sum=0; for (int i=0;i<8;++i) sum+=input.stamp[static_cast<std::size_t>(i)]-'0';
  if (sum%10 != input.stamp[9]-'0') return std::nullopt;
  CivilDate result{{number(input.stamp,0,4),number(input.stamp,4,2),number(input.stamp,6,2)}};
  return valid(result) ? std::optional<CivilDate>(result) : std::nullopt;
}}
'''
    if parser == 2:
        return f'''std::optional<CivilDate> parse(const {name}& input) {{
  if (input.serial.size()!=8 || input.serial[4]!='-' || !digits(input.serial,0,4) || !digits(input.serial,5,3)) return std::nullopt;
  const int year=number(input.serial,0,4), ordinal=number(input.serial,5,3);
  if (year<input.minimum_year || ordinal<1 || ordinal>(leap(year)?366:365)) return std::nullopt;
  CivilDate result{{year,1,1}};
  if (!valid(result)) return std::nullopt;
  result=add_days(result,ordinal-1);
  return valid(result) ? std::optional<CivilDate>(result) : std::nullopt;
}}
'''
    if parser == 3:
        return f'''std::optional<CivilDate> parse(const {name}& input) {{
  if (input.credential.size()!=8 || input.credential[4]!='W' || !digits(input.credential,0,4) || !digits(input.credential,5,2) || !digits(input.credential,7,1)) return std::nullopt;
  const int year=number(input.credential,0,4), week=number(input.credential,5,2), slot=number(input.credential,7,1);
  if (week<1 || week>input.maximum_week || slot<1 || slot>7) return std::nullopt;
  CivilDate result=add_days(CivilDate{{year,1,1}},(week-1)*7+slot-1);
  return valid(result) && result.year==year ? std::optional<CivilDate>(result) : std::nullopt;
}}
'''
    if parser == 4:
        return f'''std::optional<CivilDate> parse(const {name}& input) {{
  if (input.mark.size()!=9 || input.mark.substr(0,2)!="FY" || input.mark[6]!='-' || input.mark[7]!='Q' || !digits(input.mark,2,4) || !digits(input.mark,8,1)) return std::nullopt;
  const int fiscal=number(input.mark,2,4), quarter=number(input.mark,8,1);
  if (input.fiscal_start_month<1 || input.fiscal_start_month>12 || quarter<1 || quarter>4) return std::nullopt;
  const int absolute=(input.fiscal_start_month-1)+quarter*3-1;
  const long long wide_year=static_cast<long long>(fiscal)+absolute/12;
  if (wide_year<1 || wide_year>9999) return std::nullopt;
  const int year=static_cast<int>(wide_year), month=absolute%12+1;
  CivilDate result{{year,month,month_days(year,month)}};
  return valid(result) ? std::optional<CivilDate>(result) : std::nullopt;
}}
'''
    if parser == 5:
        return f'''std::optional<CivilDate> parse(const {name}& input) {{
  if (input.tag.size()!=5 || input.tag[2]!='/' || !digits(input.tag,0,2) || !digits(input.tag,3,2) || input.century_base<100 || input.century_base>9900 || input.century_base%100!=0) return std::nullopt;
  const int month=number(input.tag,0,2), year=input.century_base+number(input.tag,3,2);
  CivilDate result{{year,month,month_days(year,month)}};
  return valid(result) ? std::optional<CivilDate>(result) : std::nullopt;
}}
'''
    if parser == 6:
        return f'''std::optional<CivilDate> parse(const {name}& input) {{
  if (input.code.empty() || input.code.size()>4 || !valid(input.epoch)) return std::nullopt;
  int value=0; for (char byte:input.code) {{ int digit=byte>='0'&&byte<='9'?byte-'0':byte>='A'&&byte<='Z'?byte-'A'+10:-1; if(digit<0 || value>(3660-digit)/36) return std::nullopt; value=value*36+digit; }}
  if (value>3660) return std::nullopt;
  CivilDate result=add_days(input.epoch,value);
  return valid(result) ? std::optional<CivilDate>(result) : std::nullopt;
}}
'''
    if parser == 7:
        return f'''std::optional<CivilDate> parse(const {name}& input) {{
  unsigned check=0; for (int shift:{{0,8,16,24}}) check^=(input.packed>>shift)&255U;
  if (check!=input.check_byte || (input.packed & ~8388607U)!=0U) return std::nullopt;
  CivilDate result{{static_cast<int>((input.packed>>9)&16383U),static_cast<int>((input.packed>>5)&15U),static_cast<int>(input.packed&31U)}};
  return valid(result) ? std::optional<CivilDate>(result) : std::nullopt;
}}
'''
    if parser == 8:
        return f'''std::optional<CivilDate> parse(const {name}& input) {{
  if (input.mark.size()!=7 || input.mark[0]!='S' || input.mark[2]!='-' || !digits(input.mark,1,1) || !digits(input.mark,3,4)) return std::nullopt;
  const int season=number(input.mark,1,1), year=number(input.mark,3,4); if(season<1 || season>4) return std::nullopt;
  const int rotated=(season-1)*3+(input.southern_shift?6:0)+2;
  const int result_year=year+rotated/12, month=rotated%12+1;
  CivilDate result{{result_year,month,month_days(result_year,month)}};
  return valid(result) ? std::optional<CivilDate>(result) : std::nullopt;
}}
'''
    return f'''std::optional<CivilDate> parse(const {name}& input) {{
  if (input.utc_offset_minutes < -840 || input.utc_offset_minutes > 840) return std::nullopt;
  if ((input.utc_offset_minutes>0 && input.minute>std::numeric_limits<long long>::max()-input.utc_offset_minutes) ||
      (input.utc_offset_minutes<0 && input.minute<std::numeric_limits<long long>::min()-input.utc_offset_minutes)) return std::nullopt;
  const long long adjusted=input.minute+input.utc_offset_minutes;
  long long days=adjusted/1440LL; if(adjusted<0 && adjusted%1440LL) --days;
  CivilDate result=add_days(CivilDate{{2000,1,1}},days);
  return valid(result) ? std::optional<CivilDate>(result) : std::nullopt;
}}
'''


def _policy_source(case: Case) -> str:
    class_name = _class_name(case.task_id)
    input_name = f"{class_name}Input"
    policy = case.policy_index
    if policy == 0:
        return f'''ExpiryState {class_name}::classify({input_name} input, CivilDate reference) const {{
  const auto expiry=parse(input); if(!expiry || !valid(reference)) return ExpiryState::invalid;
  if(compare(reference,*expiry)>0) return ExpiryState::expired;
  return serial(*expiry)-serial(reference)<=29 ? ExpiryState::warning : ExpiryState::active;
}}
'''
    if policy == 1:
        return f'''std::optional<CivilDate> {class_name}::grace_cutoff({input_name} input, CivilDate reference, int grace_days) const {{
  const auto expiry=parse(input); if(!expiry || !valid(reference) || grace_days<0) return std::nullopt;
  CivilDate cutoff=add_days(*expiry,grace_days); if(!valid(cutoff) || compare(reference,cutoff)>0) return std::nullopt; return cutoff;
}}
'''
    if policy == 2:
        return f'''BusinessWindow {class_name}::business_window({input_name} input, CivilDate reference, int business_grace) const {{
  const auto expiry=parse(input); if(!expiry || !valid(reference) || business_grace<0) return {{}};
  CivilDate cutoff=add_business_days(*expiry,business_grace);
  if(!valid(cutoff)) return {{}};
  return {{cutoff,compare(reference,cutoff)<=0}};
}}
'''
    if policy == 3:
        return f'''ShelfDecision {class_name}::shelf_decision({input_name} input, CivilDate reference, int shelf_months) const {{
  const auto packed=parse(input); if(!packed || !valid(reference) || shelf_months<1) return {{}};
  CivilDate expiry=add_months(*packed,shelf_months);
  if(!valid(expiry)) return {{}};
  return {{expiry,compare(reference,expiry)<=0?ExpiryState::active:ExpiryState::expired}};
}}
'''
    if policy == 4:
        return f'''ExpiryState {class_name}::adjudicate({input_name} input, CivilDate reference, std::optional<CivilDate> revoked_on) const {{
  const auto expiry=parse(input); if(!expiry || !valid(reference) || (revoked_on && !valid(*revoked_on))) return ExpiryState::invalid;
  if(revoked_on && valid(*revoked_on) && compare(*revoked_on,reference)<=0) return ExpiryState::revoked;
  return compare(reference,*expiry)<=0?ExpiryState::active:ExpiryState::expired;
}}
'''
    if policy == 5:
        return f'''RenewalPlan {class_name}::renewal_plan({input_name} input, CivilDate reference, int notice_days) const {{
  const auto expiry=parse(input); if(!expiry || !valid(reference) || notice_days<0) return {{}};
  CivilDate opens=add_days(*expiry,-static_cast<long long>(notice_days));
  if(!valid(opens)) return {{}};
  ExpiryState state=compare(reference,opens)<0?ExpiryState::early:(compare(reference,*expiry)<=0?ExpiryState::open:ExpiryState::closed);
  return {{opens,*expiry,state}};
}}
'''
    if policy == 6:
        return f'''ExposureScore {class_name}::exposure({input_name} input, CivilDate reference, int units) const {{
  const auto expiry=parse(input); if(!expiry || !valid(reference) || units<=0) return {{}};
  const long long raw=serial(*expiry)-serial(reference)+1; const long long remaining=std::max(0LL,raw);
  if(remaining>2147483647LL/units) return {{}};
  return {{static_cast<int>(remaining),static_cast<int>(remaining*units),true}};
}}
'''
    if policy == 7:
        return f'''AdmissionDecision {class_name}::admit({input_name} input, CivilDate reference, CivilDate opens, CivilDate closes) const {{
  const auto expiry=parse(input); if(!expiry || !valid(reference) || !valid(opens) || !valid(closes) || compare(opens,closes)>0) return {{false,ExpiryState::invalid}};
  const bool inside=compare(reference,opens)>=0 && compare(reference,closes)<=0; const bool current=compare(reference,*expiry)<=0;
  return {{inside&&current,inside&&current?ExpiryState::active:ExpiryState::closed}};
}}
'''
    return f'''std::optional<int> {class_name}::remaining({input_name} input, CivilDate reference, bool inclusive) const {{
  const auto expiry=parse(input); if(!expiry || !valid(reference)) return std::nullopt; const long long delta=serial(*expiry)-serial(reference);
  const long long result=inclusive?delta+1:delta;
  if(result<-2147483648LL || result>2147483647LL) return std::nullopt;
  return static_cast<int>(result);
}}
'''


def _reference(case: Case) -> str:
    header, _ = _named(case.task_id)
    return (
        f'#include "{header}"\n#include <algorithm>\n#include <limits>\n'
        f'#include <optional>\n#include <string>\nnamespace expiry_identifiers {{\n{_SUPPORT}'
        f"{_parser_source(case)}}}  // namespace\n{_policy_source(case)}}}  // namespace expiry_identifiers\n"
    )


def _starter(case: Case) -> str:
    header, _ = _named(case.task_id)
    return f'''#include "{header}"
namespace expiry_identifiers {{
// TODO: validate the complete identifier, derive its civil boundary, and
// implement the documented deterministic expiry policy without a host clock.
}}  // namespace expiry_identifiers
'''


def _business_add(value: dt.date, count: int) -> dt.date:
    while count:
        value += dt.timedelta(days=1)
        if value.weekday() < 5:
            count -= 1
    return value


def _parser_invalid_inputs(case: Case) -> tuple[str, ...]:
    name = f"{_class_name(case.task_id)}Input"
    parser = case.parser_index
    if parser == 0:
        return f'{name}{{"2025-00"}}', f'{name}{{"2025-06X"}}', f'{name}{{"0000-01"}}'
    if parser == 1:
        return (
            f'{name}{{"","20250630-8"}}',
            f'{name}{{"QA","20250631-9"}}',
            f'{name}{{"QA","00000101-2"}}',
        )
    if parser == 2:
        return (
            f'{name}{{"2025-181",2026}}',
            f'{name}{{"2025-000",2000}}',
            f'{name}{{"0000-001",-1}}',
        )
    if parser == 3:
        return (
            f'{name}{{"2025W261",20}}',
            f'{name}{{"2025W260",40}}',
            f'{name}{{"2025W261X",40}}',
            f'{name}{{"0000W011",40}}',
        )
    if parser == 4:
        return (
            f'{name}{{"FY2025-Q2",0}}',
            f'{name}{{"FY2025-Q0",1}}',
            f'{name}{{"FY0000-Q1",1}}',
            f'{name}{{"FY9999-Q4",12}}',
        )
    if parser == 5:
        return (
            f'{name}{{"06/25",1950}}',
            f'{name}{{"00/25",2000}}',
            f'{name}{{"12/99",2147483600}}',
            f'{name}{{"12/99",10000}}',
        )
    if parser == 6:
        return (
            f'{name}{{"a",CivilDate{{2025,6,30}}}}',
            f'{name}{{"ZZZZZ",CivilDate{{2025,6,30}}}}',
            f'{name}{{"1",CivilDate{{9999,12,31}}}}',
            f'{name}{{"1",CivilDate{{0,1,1}}}}',
        )
    if parser == 7:
        value, check = _packed(2025, 6, 30)
        bad_value, bad_check = _packed(2025, 15, 30)
        reserved = value | (1 << 31)
        reserved_check = 0
        for shift in (0, 8, 16, 24):
            reserved_check ^= (reserved >> shift) & 0xFF
        return (
            f"{name}{{{value}U,{check ^ 4}U}}",
            f"{name}{{{bad_value}U,{bad_check}U}}",
            f"{name}{{{reserved}U,{reserved_check}U}}",
        )
    if parser == 8:
        return (
            f'{name}{{"S0-2025",false}}',
            f'{name}{{"S2/2025",true}}',
            f'{name}{{"S1-0000",false}}',
            f'{name}{{"S4-9999",true}}',
        )
    return (
        f"{name}{{0LL,841}}",
        f"{name}{{9999999999999LL,0}}",
        f"{name}{{std::numeric_limits<std::int64_t>::max(),840}}",
        f"{name}{{std::numeric_limits<std::int64_t>::min(),-840}}",
    )


def _invalid_result_expression(case: Case, input_expression: str, reference: dt.date) -> str:
    date = _date_literal(reference)
    policy = case.policy_index
    if policy == 0:
        return f"x.classify({input_expression},{date})==ExpiryState::invalid"
    if policy == 1:
        return f"!x.grace_cutoff({input_expression},{date},7)"
    if policy == 2:
        return f"!x.business_window({input_expression},{date},5).open"
    if policy == 3:
        return f"x.shelf_decision({input_expression},{date},1).state==ExpiryState::invalid"
    if policy == 4:
        return f"x.adjudicate({input_expression},{date},std::nullopt)==ExpiryState::invalid"
    if policy == 5:
        return f"x.renewal_plan({input_expression},{date},10).state==ExpiryState::invalid"
    if policy == 6:
        return f"!x.exposure({input_expression},{date},4).valid"
    if policy == 7:
        return f"x.admit({input_expression},{date},{date},{date}).state==ExpiryState::invalid"
    return f"!x.remaining({input_expression},{date},true)"


def _policy_boundary_checks(case: Case, fixture: str, expiry: dt.date) -> str:
    date = _date_literal(expiry)
    policy = case.policy_index
    if policy == 0:
        warning_edge = _date_literal(expiry - dt.timedelta(days=29))
        active_edge = _date_literal(expiry - dt.timedelta(days=30))
        return (
            f"check(x.classify({fixture},{warning_edge})==ExpiryState::warning);"
            f"check(x.classify({fixture},{active_edge})==ExpiryState::active);"
            f"check(x.classify({fixture},CivilDate{{0,1,1}})==ExpiryState::invalid);"
        )
    if policy == 1:
        cutoff = _date_literal(expiry + dt.timedelta(days=367))
        return (
            f"check(!x.grace_cutoff({fixture},{date},-1));"
            f"auto zero_grace=x.grace_cutoff({fixture},{date},0);check(zero_grace&&*zero_grace=={date});"
            f"auto wide=x.grace_cutoff({fixture},{date},367);check(wide&&*wide=={cutoff});"
            f"check(!x.grace_cutoff({fixture},{date},std::numeric_limits<int>::max()));"
        )
    if policy == 2:
        cutoff = _date_literal(_business_add(expiry, 261))
        return (
            f"auto zero_grace=x.business_window({fixture},{date},0);check(zero_grace.open&&zero_grace.cutoff=={date});"
            f"check(!x.business_window({fixture},{date},-1).open);"
            f"auto wide=x.business_window({fixture},{date},261);check(wide.open&&wide.cutoff=={cutoff});"
            f"check(!x.business_window({fixture},{date},std::numeric_limits<int>::max()).open);"
        )
    if policy == 3:
        return (
            f"check(x.shelf_decision({fixture},{date},0).state==ExpiryState::invalid);"
            f"check(x.shelf_decision({fixture},{date},121).state!=ExpiryState::invalid);"
            f"check(x.shelf_decision({fixture},{date},std::numeric_limits<int>::max()).state==ExpiryState::invalid);"
        )
    if policy == 4:
        return (
            f"check(x.adjudicate({fixture},{date},CivilDate{{0,1,1}})==ExpiryState::invalid);"
            f"check(x.adjudicate({fixture},{date},CivilDate{{9999,12,31}})==ExpiryState::active);"
        )
    if policy == 5:
        opens = _date_literal(expiry - dt.timedelta(days=367))
        return (
            f"check(x.renewal_plan({fixture},{date},-1).state==ExpiryState::invalid);"
            f"auto wide=x.renewal_plan({fixture},{date},367);check(wide.state==ExpiryState::open&&wide.opens=={opens});"
            f"check(x.renewal_plan({fixture},{date},std::numeric_limits<int>::max()).state==ExpiryState::invalid);"
        )
    if policy == 6:
        reference = _date_literal(expiry - dt.timedelta(days=2))
        return (
            f"check(!x.exposure({fixture},{date},0).valid);"
            f"auto wide=x.exposure({fixture},{reference},100001);check(wide.valid&&wide.score==300003);"
            f"check(!x.exposure({fixture},{reference},std::numeric_limits<int>::max()).valid);"
        )
    if policy == 7:
        before = _date_literal(expiry - dt.timedelta(days=1))
        return (
            f"auto on_day=x.admit({fixture},{date},{date},{date});check(on_day.admitted&&on_day.state==ExpiryState::active);"
            f"check(x.admit({fixture},{date},{date},{before}).state==ExpiryState::invalid);"
            f"check(x.admit({fixture},{date},CivilDate{{0,1,1}},{date}).state==ExpiryState::invalid);"
        )
    return f"check(!x.remaining({fixture},CivilDate{{0,1,1}},true));"


def _parser_contract_checks(case: Case, fixture: str) -> str:
    parser = case.parser_index
    checks = {
        0: "check(parser_case.token.size()==7);check(parser_case.token[4]=='-');",
        1: "check(!parser_case.issuer.empty());check(parser_case.stamp.size()==10);",
        2: "check(parser_case.serial.size()==8);check(parser_case.minimum_year==2000);",
        3: "check(parser_case.credential.size()==8);check(parser_case.maximum_week==40);",
        4: "check(parser_case.mark.size()==9);check(parser_case.fiscal_start_month==1);",
        5: "check(parser_case.tag.size()==5);check(parser_case.century_base==2000);",
        6: "check(parser_case.code.size()==1);check(parser_case.epoch==CivilDate{2025,6,30});",
        7: "check(parser_case.packed!=0U);check(parser_case.check_byte<=255U);",
        8: "check(parser_case.mark.size()==7);check(!parser_case.southern_shift);",
        9: "check(parser_case.minute==0LL);check(parser_case.utc_offset_minutes==60);",
    }
    return f"auto parser_case={fixture};{checks[parser]}"


def _tests(case: Case) -> tuple[str, str, str]:
    fixture, expiry, invalid = _fixture(case)
    class_name = _class_name(case.task_id)
    before = expiry - dt.timedelta(days=40)
    after = expiry + dt.timedelta(days=1)
    common = (
        f'#include "{case.task_id}.h"\n#include <cstdint>\n#include <cstdlib>\n#include <limits>\n#include <optional>\n'
        "using namespace expiry_identifiers;\n"
        "static void check(bool value){if(!value)std::abort();}\n"
    )
    p = case.policy_index
    if p == 0:
        late = expiry + dt.timedelta(days=30)
        visible = f"int main(){{{class_name} x;check(x.classify({fixture},{_date_literal(expiry)})==ExpiryState::warning);check(x.classify({fixture},{_date_literal(before)})==ExpiryState::active);}}"
        hidden = f"int main(){{{class_name} x;check(x.classify({invalid},{_date_literal(expiry)})==ExpiryState::invalid);check(x.classify({fixture},{_date_literal(late)})==ExpiryState::expired);}}"
        hard = f"int main(){{{class_name} x;check(x.classify({fixture},{_date_literal(expiry)})!=ExpiryState::expired);}}"
    elif p == 1:
        cutoff = expiry + dt.timedelta(days=7)
        visible = f"int main(){{{class_name} x;auto r=x.grace_cutoff({fixture},{_date_literal(expiry)},7);check(r&&*r=={_date_literal(cutoff)});}}"
        hidden = f"int main(){{{class_name} x;check(!x.grace_cutoff({invalid},{_date_literal(expiry)},7));check(!x.grace_cutoff({fixture},{_date_literal(cutoff+dt.timedelta(days=1))},7));}}"
        hard = visible
    elif p == 2:
        cutoff = _business_add(expiry, 5)
        visible = f"int main(){{{class_name} x;auto r=x.business_window({fixture},{_date_literal(cutoff)},5);check(r.open&&r.cutoff=={_date_literal(cutoff)});}}"
        hidden = f"int main(){{{class_name} x;check(!x.business_window({invalid},{_date_literal(expiry)},5).open);check(!x.business_window({fixture},{_date_literal(cutoff+dt.timedelta(days=1))},5).open);}}"
        hard = visible
    elif p == 3:
        year = expiry.year + (expiry.month + 1 - 1) // 12
        month = (expiry.month + 1 - 1) % 12 + 1
        shelf = dt.date(year, month, min(expiry.day, _days_in_month(year, month)))
        visible = f"int main(){{{class_name} x;auto r=x.shelf_decision({fixture},{_date_literal(shelf)},1);check(r.state==ExpiryState::active&&r.expiry=={_date_literal(shelf)});}}"
        hidden = f"int main(){{{class_name} x;check(x.shelf_decision({invalid},{_date_literal(expiry)},1).state==ExpiryState::invalid);check(x.shelf_decision({fixture},{_date_literal(shelf+dt.timedelta(days=1))},1).state==ExpiryState::expired);}}"
        hard = visible
    elif p == 4:
        visible = f"int main(){{{class_name} x;check(x.adjudicate({fixture},{_date_literal(expiry)},{_date_literal(expiry)})==ExpiryState::revoked);}}"
        hidden = f"int main(){{{class_name} x;check(x.adjudicate({invalid},{_date_literal(expiry)},std::nullopt)==ExpiryState::invalid);check(x.adjudicate({fixture},{_date_literal(after)},std::nullopt)==ExpiryState::expired);}}"
        hard = visible
    elif p == 5:
        opens = expiry - dt.timedelta(days=10)
        visible = f"int main(){{{class_name} x;auto r=x.renewal_plan({fixture},{_date_literal(opens)},10);check(r.opens=={_date_literal(opens)}&&r.state==ExpiryState::open);}}"
        hidden = f"int main(){{{class_name} x;check(x.renewal_plan({invalid},{_date_literal(expiry)},10).state==ExpiryState::invalid);check(x.renewal_plan({fixture},{_date_literal(after)},10).state==ExpiryState::closed);}}"
        hard = visible
    elif p == 6:
        reference = expiry - dt.timedelta(days=2)
        visible = f"int main(){{{class_name} x;auto r=x.exposure({fixture},{_date_literal(reference)},4);check(r.valid&&r.remaining_days==3&&r.score==12);}}"
        hidden = f"int main(){{{class_name} x;check(!x.exposure({invalid},{_date_literal(expiry)},4).valid);auto r=x.exposure({fixture},{_date_literal(after)},4);check(r.valid&&r.score==0);}}"
        hard = visible
    elif p == 7:
        opens = expiry - dt.timedelta(days=3)
        visible = f"int main(){{{class_name} x;auto r=x.admit({fixture},{_date_literal(opens)},{_date_literal(opens)},{_date_literal(expiry)});check(r.admitted&&r.state==ExpiryState::active);}}"
        hidden = f"int main(){{{class_name} x;check(!x.admit({invalid},{_date_literal(expiry)},{_date_literal(opens)},{_date_literal(expiry)}).admitted);check(!x.admit({fixture},{_date_literal(after)},{_date_literal(opens)},{_date_literal(expiry)}).admitted);}}"
        hard = visible
    else:
        reference = expiry - dt.timedelta(days=2)
        visible = f"int main(){{{class_name} x;auto r=x.remaining({fixture},{_date_literal(reference)},true);check(r&&*r==3);}}"
        hidden = f"int main(){{{class_name} x;check(!x.remaining({invalid},{_date_literal(expiry)},true));auto r=x.remaining({fixture},{_date_literal(after)},false);check(r&&*r==-1);}}"
        hard = visible
    parser_checks = "".join(
        f"check({_invalid_result_expression(case, invalid_input, expiry)});"
        for invalid_input in _parser_invalid_inputs(case)
    )
    hidden = (
        hidden[:-1]
        + _parser_contract_checks(case, fixture)
        + parser_checks
        + _policy_boundary_checks(case, fixture, expiry)
        + "}"
    )
    return tuple(common + body + "\n" for body in (visible, hidden, hard))


def _negative_source(case: Case, reference: str) -> str:
    mutations = {
        0: ("compare(reference,*expiry)>0", "compare(reference,*expiry)>=0"),
        1: ("add_days(*expiry,grace_days)", "add_days(*expiry,-grace_days)"),
        2: ("add_business_days(*expiry,business_grace)", "add_days(*expiry,business_grace)"),
        3: ("add_months(*packed,shelf_months)", "add_days(*packed,shelf_months)"),
        4: ("compare(*revoked_on,reference)<=0", "compare(*revoked_on,reference)<0"),
        5: (
            "add_days(*expiry,-static_cast<long long>(notice_days))",
            "add_days(*expiry,static_cast<long long>(notice_days))",
        ),
        6: ("remaining*units", "remaining+units"),
        7: ("compare(reference,opens)>=0", "compare(reference,opens)>0"),
        8: ("inclusive?delta+1:delta", "inclusive?delta:delta"),
    }
    old, new = mutations[case.policy_index]
    if reference.count(old) != 1:
        _fail("invariant_not_enforced", f"negative mutation drift for {case.task_id}")
    return reference.replace(old, new, 1)


def _instructions(case: Case) -> str:
    class_name = _class_name(case.task_id)
    input_name = f"{class_name}Input"
    return f"""# {case.title}

Implement `{class_name}` in namespace `expiry_identifiers` using the declarations
in `{case.task_id}.h`. The input record is `{input_name}`.

Identifier grammar: {case.parser.grammar}. Validate the complete representation
before producing any date; trailing bytes, partial fields, impossible calendar
values, and overflow are invalid. The parser mechanism is a
{case.parser.mechanism}. Years use the proleptic Gregorian leap rule and the
supported civil range is 0001-01-01 through 9999-12-31.

Expiry policy: {case.policy.rule}. The caller supplies every reference date and
policy argument. Do not read the host clock. Invalid input returns the invalid,
empty, or false result described by the declarations and never produces a
partially valid result. Equality, ordering, and tie behavior are exactly those
stated above; checked arithmetic must reject an out-of-range result.

The substantive work is strict parsing followed by this task's calendar-policy
transition. Generic date-parser delegation, regular-expression delegation,
timestamp libraries, host-clock access, hard-coded examples, a policy switch
shared with another root, and benchmark assets are forbidden.
"""


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(expiry_identifier_task LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation under test")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
add_executable(task_hard_rule "${TASK_SOURCE}" .meta/task_hard_rule_test.cpp)
foreach(target task_visible task_hidden task_hard_rule)
  target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_test(NAME hard_rule COMMAND task_hard_rule)
'''


def _provenance(case: Case) -> dict[str, object]:
    return {
        "schema_version": "aider-clean-room-provenance-v1",
        "task_id": case.task_id,
        "family_id": FAMILY_ID,
        "source_document": CURRICULUM.as_posix(),
        "source_task_id": case.task_id,
        "authoring_origin": "repository-authored clean-room deterministic generator",
        "license": "repository project terms",
        "lineage": {"relation": "new-root", "parent": None, "replacement": None},
        "benchmark_boundary": "all 26 official Aider Polyglot C++ roots are permanent holdouts",
        "status": "local_candidate_not_dataset_admission",
        "parser_profile": case.parser.key,
        "policy_profile": case.policy.key,
    }


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, value: object) -> None:
    _write(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _assert_output_root(out: Path) -> None:
    repo = Path.cwd().resolve()
    target = (repo / out).resolve() if not out.is_absolute() else out.resolve()
    expansion = (repo / EXPANSION_ROOT).resolve()
    legacy = (repo / LEGACY_ROOT).resolve()
    reverify = (repo / REVERIFY_ROOT).resolve()
    if target == legacy or legacy in target.parents or target == reverify or reverify in target.parents:
        _fail("unsafe_output_root", "expansion owner refuses existing generated trees")
    if target != expansion and expansion not in target.parents:
        _fail("unsafe_output_root", f"output must be below {EXPANSION_ROOT}")
    current = target
    while current.exists():
        if current.is_symlink():
            _fail("unsafe_output_root", f"symlink component: {current}")
        if current == repo or current.parent == current:
            break
        current = current.parent


def _inventory_configs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        path
        for path in root.rglob(".meta/config.json")
        if ".state" not in path.parts
    )


def _reserved_ids(out: Path) -> dict[str, str]:
    paths_by_id: dict[str, list[str]] = {}
    owned = out.resolve()
    for tree in (LEGACY_ROOT, REVERIFY_ROOT, EXPANSION_ROOT):
        for config in _inventory_configs(tree):
            task_id = config.parent.parent.name
            if tree == EXPANSION_ROOT and owned in config.resolve().parents:
                continue
            paths_by_id.setdefault(task_id, []).append(config.as_posix())
    return {task_id: " | ".join(paths) for task_id, paths in paths_by_id.items()}


def _materialize_one(case: Case, root: Path) -> None:
    header_name, source_name = _named(case.task_id)
    header = _common_header(case)
    reference = _reference(case)
    starter = _starter(case)
    visible, hidden, hard = _tests(case)
    negative = _negative_source(case, reference)
    _write(root / ".docs/introduction.md", f"# {case.title}\n\nA clean-room date-bearing identifier validation task.\n")
    _write(root / ".docs/instructions.md", _instructions(case))
    _write(root / header_name, header)
    _write(root / source_name, starter)
    _write(root / "task_visible_test.cpp", visible)
    _write(root / ".meta/example.h", header)
    _write(root / ".meta/example.cpp", reference)
    _write(root / ".meta/task_hidden_test.cpp", hidden)
    _write(root / ".meta/task_hard_rule_test.cpp", hard)
    _write(root / ".meta/negative_false_substitute.cpp", negative)
    _write(root / "CMakeLists.txt", _cmake())
    _write_json(root / ".meta/provenance.json", _provenance(case))
    _write_json(
        root / ".meta/config.json",
        {
            "authors": ["w8-biayn"],
            "blurb": case.title,
            "files": {
                "solution": [header_name, source_name],
                "test": ["task_visible_test.cpp"],
                "example": [".meta/example.h", ".meta/example.cpp"],
            },
            "source": "clean-room repository curriculum",
        },
    )
    _write(
        root / ".meta/tests.toml",
        f'''[visible]
description = "principal {case.parser.label} and {case.policy.label} behavior"
[hidden]
description = "malformed representation, boundary, overflow, and no-partial-result cases"
[hard_rule]
description = "rejects: {case.policy.negative}"
''',
    )


def build(out: Path = DEFAULT_OUT, *, force: bool = False) -> list[Path]:
    _assert_output_root(out)
    reserved = _reserved_ids(out)
    collisions = sorted(case.task_id for case in CASES if case.task_id in reserved)
    if collisions:
        _fail("duplicate_task", f"reserved task ids: {collisions}")
    expected = {case.task_id for case in CASES}
    existing = {
        path.parent.parent.name for path in _inventory_configs(out)
    }
    foreign = sorted(existing - expected)
    if foreign:
        _fail("generator_output_drift", f"foreign roots in owned family: {foreign}")
    if out.exists() and not force:
        missing = sorted(expected - existing)
        if missing:
            _fail("generator_output_drift", f"partial family exists; pass --force: {missing[:5]}")
        return [out / case.task_id for case in CASES]
    state = out / ".state"
    saved_evidence: dict[Path, bytes] = {}
    for evidence_dir in ("cycles", "audits", "remedies"):
        prior = state / evidence_dir
        if prior.is_dir():
            for path in prior.rglob("*.json"):
                saved_evidence[path.relative_to(state)] = path.read_bytes()
    if out.exists():
        shutil.rmtree(out)
    state.mkdir(parents=True, exist_ok=True)
    for relative, content in saved_evidence.items():
        path = state / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    roots: list[Path] = []
    for case in CASES:
        root = out / case.task_id
        _materialize_one(case, root)
        roots.append(root)
    _write_json(
        state / "source-inventory.json",
        {
            "schema_version": "aider-expansion-source-inventory-v1",
            "existing": {
                LEGACY_ROOT.as_posix(): len(_inventory_configs(LEGACY_ROOT)),
                REVERIFY_ROOT.as_posix(): len(_inventory_configs(REVERIFY_ROOT)),
            },
            "reserved_ids": sorted(reserved),
            "candidate_ids": sorted(expected),
            "candidate_count": len(expected),
            "lineage": "all candidates are new roots",
        },
    )
    return roots


_CPP_WORDS = frozenset(
    "alignas alignof and and_eq asm auto bitand bitor bool break case catch char "
    "class compl concept const consteval constexpr constinit const_cast continue "
    "co_await co_return co_yield decltype default delete do double dynamic_cast "
    "else enum explicit export extern false float for friend goto if inline int "
    "long mutable namespace new noexcept not not_eq nullptr operator or or_eq "
    "private protected public register reinterpret_cast requires return short "
    "signed sizeof static static_assert static_cast struct switch template this "
    "thread_local throw true try typedef typeid typename union unsigned using "
    "virtual void volatile wchar_t while xor xor_eq optional string vector min "
    "max nullopt".split()
)

_SEMANTIC_WORDS = frozenset(
    "fixed width digit digits decimal field scanner month month_end year day date "
    "issuer stamp checksum ordinal leap week slot bounded fiscal quarter rotation "
    "century pivot base offset overflow positional packed bits bit integrity xor "
    "season hemisphere epoch minute floor division civil parser parse token serial "
    "credential maximum_week minimum_year fiscal_start_month century_base code "
    "check_byte southern_shift utc_offset_minutes classify warning active expired "
    "grace cutoff grace_days business weekday business_grace shelf shelf_months "
    "revocation revoked revoked_on precedence adjudicate renewal notice notice_days "
    "exposure score units admission admit window opens closes remaining inclusive "
    "add_days add_months add_business_days compare valid empty size substr reference "
    "expiry early open closed multiplication integer range optional state".split()
)


def _literal_shape(match: re.Match[str]) -> str:
    value = match.group(0)[1:-1]
    if ".h" in value or ".cpp" in value:
        return " path_literal "
    shape: list[str] = []
    previous = ""
    count = 0
    for char in value:
        current = (
            "D"
            if char.isdigit()
            else "A"
            if char.isalpha()
            else {"-": "dash", "/": "slash", ":": "colon", "_": "under"}.get(char, "sep")
        )
        if current != previous:
            if previous:
                shape.append(f"{previous}{count}")
            previous = current
            count = 1
        else:
            count += 1
    if previous:
        shape.append(f"{previous}{count}")
    return " string_shape_" + "_".join(shape) + " "


def _normalized_tokens(text: str) -> tuple[str, ...]:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', _literal_shape, text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", " char_literal ", text)
    text = re.sub(
        r"\b\d+(?:\.\d+)?\b",
        lambda match: f" number_shape_{len(match.group(0).replace('.', ''))} ",
        text,
    )
    raw = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|<=|>=|==|!=|&&|\|\||[-+*/%<>?:{}()[\];,.]", text)
    return tuple(
        token.lower()
        if token.lower() in _CPP_WORDS
        or token.lower() in _SEMANTIC_WORDS
        or token.lower().startswith("string_shape_")
        or token.lower().startswith("number_shape_")
        else "identifier"
        for token in raw
    )


def _shingles(tokens: tuple[str, ...], width: int = 5) -> frozenset[tuple[str, ...]]:
    if len(tokens) < width:
        return frozenset({tokens}) if tokens else frozenset()
    return frozenset(tuple(tokens[index : index + width]) for index in range(len(tokens) - width + 1))


def _containment(left: str, right: str) -> float:
    a, b = _shingles(_normalized_tokens(left)), _shingles(_normalized_tokens(right))
    return _shingle_containment(a, b)


def _shingle_containment(
    a: frozenset[tuple[str, ...]], b: frozenset[tuple[str, ...]]
) -> float:
    if not a or not b:
        return 1.0 if a == b else 0.0
    return len(a & b) / min(len(a), len(b))


def _shingle_jaccard(
    a: frozenset[tuple[str, ...]], b: frozenset[tuple[str, ...]]
) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def _root_roles(root: Path) -> dict[str, str]:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    solution = config["files"]["solution"]
    header_name = next(name for name in solution if str(name).endswith(".h"))
    docs = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((root / ".docs").glob("*.md"))
    )
    header = (root / header_name).read_text(encoding="utf-8")
    raw_reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
    reference = re.sub(
        r"namespace \{\n.*?(?=std::optional<CivilDate> parse)",
        "namespace {\n/* allowlisted shared civil support */\n",
        raw_reference,
        count=1,
        flags=re.S,
    )
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    hidden = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
    hard = (root / ".meta/task_hard_rule_test.cpp").read_text(encoding="utf-8")
    raw_negative = (root / ".meta/negative_false_substitute.cpp").read_text(encoding="utf-8")
    negative = re.sub(
        r"namespace \{\n.*?(?=std::optional<CivilDate> parse)",
        "namespace {\n/* allowlisted shared civil support */\n",
        raw_negative,
        count=1,
        flags=re.S,
    )
    return {
        "public_api": docs + "\n" + header,
        "owned_state_algorithm": docs + "\n" + reference,
        "mutation_selection_rules": docs + "\n" + reference + "\n" + hard,
        "invalid_boundary_behavior": docs + "\n" + hidden,
        "reference_control_flow": reference,
        "deterministic_oracle": visible + "\n" + hidden + "\n" + hard,
        "topic_specific_negative_fixture": negative,
    }


def _pair_decision(
    left: Path,
    right: Path,
    *,
    limit: float | None = None,
    left_roles: dict[str, str] | None = None,
    right_roles: dict[str, str] | None = None,
) -> dict[str, object]:
    left_roles = left_roles or _root_roles(left)
    right_roles = right_roles or _root_roles(right)
    dimensions: dict[str, object] = {}
    for dimension in HARD_RULE_DIMENSIONS:
        score = _containment(left_roles[dimension], right_roles[dimension])
        left_set = _shingles(_normalized_tokens(left_roles[dimension]))
        right_set = _shingles(_normalized_tokens(right_roles[dimension]))
        jaccard = _shingle_jaccard(left_set, right_set)
        dimension_limit = HARD_RULE_LIMITS[dimension] if limit is None else limit
        dimensions[dimension] = {
            "containment": round(score, 6),
            "limit": dimension_limit,
            "jaccard": round(jaccard, 6),
            "jaccard_limit": 0.97,
            "distinct": score < dimension_limit and jaccard < 0.97,
        }
    dimensions["pass"] = all(
        bool(dimensions[name]["distinct"])  # type: ignore[index]
        for name in HARD_RULE_DIMENSIONS
    )
    return dimensions


def diversity_screen(out: Path = DEFAULT_OUT) -> dict[str, object]:
    roots = [out / case.task_id for case in CASES]
    if any(not root.is_dir() for root in roots):
        _fail("generator_output_drift", "diversity screen requires all 90 roots")
    role_cache = {root: _root_roles(root) for root in roots}
    shingle_cache = {
        root: {
            dimension: _shingles(_normalized_tokens(roles[dimension]))
            for dimension in HARD_RULE_DIMENSIONS
        }
        for root, roles in role_cache.items()
    }
    pairs: list[dict[str, object]] = []
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            dimensions: dict[str, object] = {}
            for dimension in HARD_RULE_DIMENSIONS:
                score = _shingle_containment(
                    shingle_cache[left][dimension], shingle_cache[right][dimension]
                )
                jaccard = _shingle_jaccard(
                    shingle_cache[left][dimension], shingle_cache[right][dimension]
                )
                limit = HARD_RULE_LIMITS[dimension]
                dimensions[dimension] = {
                    "containment": round(score, 6),
                    "limit": limit,
                    "jaccard": round(jaccard, 6),
                    "jaccard_limit": 0.97,
                    "distinct": score < limit and jaccard < 0.97,
                }
            dimensions["pass"] = all(
                bool(dimensions[name]["distinct"])  # type: ignore[index]
                for name in HARD_RULE_DIMENSIONS
            )
            pairs.append(
                {
                    "left": left.name,
                    "right": right.name,
                    "dimensions": dimensions,
                    "pass": dimensions["pass"],
                }
            )
    failed = [f"{row['left']}::{row['right']}" for row in pairs if not row["pass"]]
    report = {
        "schema_version": "aider-seven-dimension-screen-v1",
        "normalizer": NORMALIZER,
        "root_count": len(roots),
        "pair_count": len(pairs),
        "expected_pair_count": 90 * 89 // 2,
        "dimensions": list(HARD_RULE_DIMENSIONS),
        "pairs": pairs,
        "failed_pairs": failed,
        "pass": not failed and len(pairs) == 4005,
    }
    _write_json(out / ".state/diversity-screen.json", report)
    if not report["pass"]:
        _fail("duplicate_family", f"failed pair count {len(failed)}; first={failed[:3]}")
    return report


def _copy_control(base: Path, target: Path, variant: str) -> list[str]:
    shutil.copytree(base, target)
    changed: list[str] = []
    task_id = base.name
    class_name = _class_name(task_id)
    replacements: dict[str, str]
    if variant == "domain-identifier-renamed-clone":
        replacements = {
            class_name: "RenamedDomainCredential",
            "Ampoule": "Capsule",
        }
    elif variant == "constants-policy-only-clone":
        replacements = {"9999": "9998"}
    else:
        replacements = {
            "compare(reference,*expiry)>0": "compare(reference,*expiry)>=0",
            "CivilDate{2025,6,30})==ExpiryState::warning": "CivilDate{2025,6,29})==ExpiryState::warning",
            "CivilDate{2025,7,30})==ExpiryState::expired": "CivilDate{2025,6,30})==ExpiryState::expired",
            "CivilDate{2025,6,30})!=ExpiryState::expired": "CivilDate{2025,6,29})!=ExpiryState::expired",
            "expired after the encoded end": "expired at the encoded end",
        }
    for path in sorted(item for item in target.rglob("*") if item.is_file()):
        text = path.read_text(encoding="utf-8")
        updated = text
        for old, new in replacements.items():
            updated = updated.replace(old, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(path.relative_to(target).as_posix())
    if not changed:
        _fail("invariant_not_enforced", f"control made no changes: {variant}")
    return changed


def control_screen(out: Path = DEFAULT_OUT) -> dict[str, object]:
    controls_root = out / ".state/hard-rule-controls"
    if controls_root.exists():
        shutil.rmtree(controls_root)
    base = out / CASES[0].task_id
    variants = (
        "domain-identifier-renamed-clone",
        "constants-policy-only-clone",
        "opposite-end-selection-clone",
    )
    rows: dict[str, object] = {}
    for variant in variants:
        root = controls_root / variant / "root"
        changed = _copy_control(base, root, variant)
        dimensions = _pair_decision(base, root)
        failed_dimensions = [
            name
            for name in HARD_RULE_DIMENSIONS
            if not bool(dimensions[name]["distinct"])  # type: ignore[index]
        ]
        rows[variant] = {
            "base_task": base.name,
            "root": root.relative_to(out).as_posix(),
            "changed_files": changed,
            "dimensions": dimensions,
            "failed_dimensions": failed_dimensions,
            "semantic_screen": (
                "rejected:duplicate_family"
                if len(failed_dimensions) == len(HARD_RULE_DIMENSIONS)
                else "unexpectedly_distinct"
            ),
        }
    _write_json(out / ".state/adversarial-controls.json", rows)
    for name, row in rows.items():
        if row["semantic_screen"] != "rejected:duplicate_family":  # type: ignore[index]
            _fail("duplicate_family", f"adversarial clone escaped screen: {name}")
    return rows


def _prompt_boundary(out: Path) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    forbidden = (".meta/", "CMakeLists.txt", "task_hidden", "example.cpp", "provenance")
    for case in CASES:
        root = out / case.task_id
        task = load_task(root)
        prompt = build_prompt(task)
        answer = build_assistant_response(task, load_example_files_from_config(root))
        header, source = _named(case.task_id)
        if any(marker in prompt for marker in forbidden):
            _fail("prompt_contract_incomplete", f"private marker exposed by {case.task_id}")
        editable_section = prompt.split("# Supplied editable files", 1)[1]
        if editable_section.count(f"{header}\n```cpp") != 1 or editable_section.count(f"{source}\n```cpp") != 1:
            _fail("prompt_contract_incomplete", f"editable order/count drift: {case.task_id}")
        if answer.count(f"{header}\n```") != 1 or answer.count(f"{source}\n```") != 1:
            _fail("target_reference_mismatch", f"whole-file target drift: {case.task_id}")
        rows.append(
            {
                "task_id": case.task_id,
                "prompt_hash": _sha_bytes(prompt.encode()),
                "answer_hash": _sha_bytes(answer.encode()),
                "solution_order": [header, source],
                "pass": True,
            }
        )
    report = {"schema_version": "aider-prompt-boundary-v1", "rows": rows, "pass": True}
    _write_json(out / ".state/prompt-boundary.json", report)
    return report


def _semantic_text(root: Path) -> str:
    roles = _root_roles(root)
    return "\n".join(roles.values())


def _external_semantic_text(root: Path) -> str:
    paths: set[Path] = set((root / ".docs").glob("*.md"))
    config_path = root / ".meta/config.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            files = config.get("files", {})
            for role in ("solution", "test", "example"):
                for item in files.get(role, []):
                    if isinstance(item, str) and ".." not in Path(item).parts:
                        paths.add(root / item)
        except (json.JSONDecodeError, OSError, TypeError):
            pass
    paths.update((root / ".meta").glob("*test*.cpp"))
    paths.update((root / ".meta").glob("*negative*.cpp"))
    pieces: list[str] = []
    for path in sorted(paths):
        if path.is_file() and path.stat().st_size <= 512_000:
            try:
                pieces.append(path.read_text(encoding="utf-8"))
            except UnicodeDecodeError:
                continue
    return "\n".join(pieces)


def contamination_screen(out: Path = DEFAULT_OUT) -> dict[str, object]:
    candidate_ids = {case.task_id for case in CASES}
    if candidate_ids & OFFICIAL_HOLDOUTS:
        _fail("benchmark_id_overlap", str(sorted(candidate_ids & OFFICIAL_HOLDOUTS)))
    comparisons: list[dict[str, object]] = []
    conflicts: list[dict[str, object]] = []
    candidates = [
        (case.task_id, _shingles(_normalized_tokens(_semantic_text(out / case.task_id))))
        for case in CASES
    ]
    comparison_roots: list[tuple[str, Path]] = []
    for tree in (LEGACY_ROOT, REVERIFY_ROOT):
        for config in _inventory_configs(tree):
            comparison_roots.append((config.parent.parent.name, config.parent.parent))
    holdout_configs = _inventory_configs(HOLDOUT_ROOT)
    if not holdout_configs:
        _fail("benchmark_content_overlap", f"holdout content unavailable: {HOLDOUT_ROOT}")
    for config in holdout_configs:
        comparison_roots.append((f"holdout:{config.parent.parent.name}", config.parent.parent))
    comparison_texts: list[tuple[str, frozenset[tuple[str, ...]]]] = []
    for other_id, other_root in comparison_roots:
        text = _external_semantic_text(other_root)
        comparison_texts.append((other_id, _shingles(_normalized_tokens(text))))
    for candidate_id, candidate_shingles in candidates:
        for other_id, other_shingles in comparison_texts:
            score = _shingle_containment(candidate_shingles, other_shingles)
            relation = "pass" if score < 0.92 else "semantic_conflict"
            row = {
                "candidate": candidate_id,
                "other": other_id,
                "containment": round(score, 6),
                "limit": 0.92,
                "result": relation,
            }
            comparisons.append(row)
            if relation != "pass":
                conflicts.append(row)
    report = {
        "schema_version": "aider-expansion-contamination-v1",
        "normalizer": NORMALIZER,
        "candidate_count": 90,
        "existing_root_count": len(comparison_roots) - len(holdout_configs),
        "holdout_count": len(holdout_configs),
        "comparison_count": len(comparisons),
        "comparisons": comparisons,
        "conflicts": conflicts,
        "pass": not conflicts,
    }
    _write_json(out / ".state/contamination-screen.json", report)
    if conflicts:
        _fail("benchmark_content_overlap", f"semantic conflicts: {conflicts[:3]}")
    return report


def structural_preflight(out: Path = DEFAULT_OUT) -> dict[str, object]:
    roots = [out / case.task_id for case in CASES]
    if len(_inventory_configs(out)) != 90:
        _fail("generator_output_drift", "expected exactly 90 real configs")
    rows: list[dict[str, object]] = []
    prompt_hashes: set[str] = set()
    reference_hashes: set[str] = set()
    for case, root in zip(CASES, roots, strict=True):
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        provenance = json.loads((root / ".meta/provenance.json").read_text(encoding="utf-8"))
        header, source = _named(case.task_id)
        if config["files"]["solution"] != [header, source]:
            _fail("unsafe_path", f"solution order: {case.task_id}")
        if config["files"]["example"] != [".meta/example.h", ".meta/example.cpp"]:
            _fail("target_reference_mismatch", case.task_id)
        if provenance["lineage"] != {"relation": "new-root", "parent": None, "replacement": None}:
            _fail("remedy_disposition_conflict", case.task_id)
        prompt = build_prompt(load_task(root))
        prompt_hash = _sha_bytes(prompt.encode())
        reference_hash = _sha_file(root / ".meta/example.cpp")
        if prompt_hash in prompt_hashes or reference_hash in reference_hashes:
            _fail("duplicate_task", f"prompt/reference hash duplicate: {case.task_id}")
        prompt_hashes.add(prompt_hash)
        reference_hashes.add(reference_hash)
        rows.append(
            {
                "task_id": case.task_id,
                "tree_hash": _tree_hash(root),
                "prompt_hash": prompt_hash,
                "starter_hashes": [_sha_file(root / header), _sha_file(root / source)],
                "reference_hashes": [
                    _sha_file(root / ".meta/example.h"),
                    reference_hash,
                ],
                "test_hashes": [
                    _sha_file(root / "task_visible_test.cpp"),
                    _sha_file(root / ".meta/task_hidden_test.cpp"),
                    _sha_file(root / ".meta/task_hard_rule_test.cpp"),
                ],
                "negative_hash": _sha_file(root / ".meta/negative_false_substitute.cpp"),
                "primary_core_objective": "achieved",
            }
        )
    report = {
        "schema_version": SCHEMA,
        "family_id": FAMILY_ID,
        "root_count": len(rows),
        "rows": rows,
        "tree_hash": _tree_hash(out),
        "status": "pending_runtime",
    }
    _write_json(out / ".state/candidate-manifest.json", report)
    return report


def _docker_script() -> str:
    return r'''set -euo pipefail
compiler="$(command -v c++)"
echo "COMPILER_PATH ${compiler}"
echo "COMPILER_HASH sha256:$(sha256sum "${compiler}" | awk '{print $1}')"
echo "COMPILER_VERSION $(c++ --version | head -1)"
echo "CMAKE_VERSION $(cmake --version | head -1)"
mount_hash="$({ cd /tasks; find . -type f ! -path './.state/*' -print | LC_ALL=C sort | while IFS= read -r file; do rel="${file#./}"; printf '%s\0' "${rel}"; cat "${file}"; printf '\0'; done; } | sha256sum | awk '{print $1}')"
echo "MOUNT_HASH sha256:${mount_hash}"
verify_root() {
  source_root="$1"
  label="$2"
  negative="$3"
  work="/tmp/w8-expiry/${label}"
  rm -rf "${work}"
  mkdir -p "${work}"
  cp -a "${source_root}/." "${work}/"
  normal="${work}/build-normal"
  if ! cmake -S "${work}" -B "${normal}" -G "Unix Makefiles" -DTASK_SOURCE="${work}/.meta/example.cpp" >/tmp/configure.log 2>&1; then
    echo "ROOT_FAILURE ${label} normal_configure"; cat /tmp/configure.log; return 1
  fi
  if ! cmake --build "${normal}" -j2 >/tmp/build.log 2>&1; then
    echo "ROOT_FAILURE ${label} normal_build"; cat /tmp/build.log; return 1
  fi
  if ! ctest --test-dir "${normal}" --output-on-failure >/tmp/test.log 2>&1; then
    echo "ROOT_FAILURE ${label} normal_test"; cat /tmp/test.log; return 1
  fi
  normal_count="$(ctest --test-dir "${normal}" -N | sed -n 's/.*Total Tests: *//p')"
  sanitizer="${work}/build-sanitizer"
  if ! cmake -S "${work}" -B "${sanitizer}" -G "Unix Makefiles" -DTASK_SOURCE="${work}/.meta/example.cpp" -DCMAKE_CXX_FLAGS="-fsanitize=address,undefined -fno-omit-frame-pointer" >/tmp/configure-san.log 2>&1; then
    echo "ROOT_FAILURE ${label} sanitizer_configure"; cat /tmp/configure-san.log; return 1
  fi
  if ! cmake --build "${sanitizer}" -j2 >/tmp/build-san.log 2>&1; then
    echo "ROOT_FAILURE ${label} sanitizer_build"; cat /tmp/build-san.log; return 1
  fi
  if ! ASAN_OPTIONS=detect_leaks=0 UBSAN_OPTIONS=halt_on_error=1 ctest --test-dir "${sanitizer}" --output-on-failure >/tmp/test-san.log 2>&1; then
    echo "ROOT_FAILURE ${label} sanitizer_test"; cat /tmp/test-san.log; return 1
  fi
  sanitizer_count="$(ctest --test-dir "${sanitizer}" -N | sed -n 's/.*Total Tests: *//p')"
  if [ -z "${normal_count}" ] || [ "${normal_count}" -le 0 ] || [ "${normal_count}" != "${sanitizer_count}" ]; then
    echo "DISCOVERY_FAILURE ${label} ${normal_count:-missing} ${sanitizer_count:-missing}"
    return 1
  fi
  negative_result="not_applicable"
  if [ "${negative}" = "yes" ]; then
    negative_build="${work}/build-negative"
    if ! cmake -S "${work}" -B "${negative_build}" -G "Unix Makefiles" -DTASK_SOURCE="${work}/.meta/negative_false_substitute.cpp" >/tmp/configure-negative.log 2>&1; then
      echo "ROOT_FAILURE ${label} negative_configure"; cat /tmp/configure-negative.log; return 1
    fi
    if ! cmake --build "${negative_build}" -j2 >/tmp/build-negative.log 2>&1; then
      echo "ROOT_FAILURE ${label} negative_build"; cat /tmp/build-negative.log; return 1
    fi
    if ctest --test-dir "${negative_build}" --output-on-failure >/tmp/test-negative.log 2>&1; then
      echo "NEGATIVE_ACCEPTED ${label}"
      return 1
    fi
    negative_result="rejected"
  fi
  echo "ROOT_PASS ${label} ${normal_count} ${sanitizer_count} ${negative_result}"
  rm -rf "${work}"
}
mkdir -p /tmp/w8-expiry
for source_root in /tasks/*; do
  [ -d "${source_root}" ] || continue
  [ "$(basename "${source_root}")" = ".state" ] && continue
  verify_root "${source_root}" "$(basename "${source_root}")" yes
done
for source_root in /tasks/.state/hard-rule-controls/*/root; do
  [ -d "${source_root}" ] || continue
  label="control-$(basename "$(dirname "${source_root}")")"
  verify_root "${source_root}" "${label}" no
done
'''


def _redacted_docker_command(command: Sequence[str]) -> list[str]:
    if len(command) < 3 or list(command[-3:-1]) != ["bash", "-lc"]:
        _fail("receipt_command_mismatch", "unexpected Docker command tail")
    return [*command[:-1], "<owner-embedded-script>"]


def docker_sanity(out: Path = DEFAULT_OUT) -> dict[str, object]:
    _assert_output_root(out)
    expected_hash = _tree_hash(out)
    image_inspect = subprocess.run(
        ["docker", "image", "inspect", SANITY_IMAGE, "--format", "{{.Id}}"],
        check=True,
        text=True,
        capture_output=True,
    )
    command = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,exec,nosuid,size=2g",
        "-v",
        f"{out.resolve()}:/tasks:ro",
        SANITY_IMAGE,
        "bash",
        "-lc",
        _docker_script(),
    ]
    completed = subprocess.run(command, check=False, text=True, capture_output=True)
    if completed.returncode:
        failure = {
            "schema_version": "aider-expiry-docker-failure-v1",
            "image_reference": SANITY_IMAGE,
            "owner_tree_hash": expected_hash,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        _write_json(out / ".state/docker-sanity-failure.json", failure)
        diagnostic = "\n".join(
            (completed.stdout + "\n" + completed.stderr).splitlines()[-40:]
        )
        _fail("reference_tests_failed", diagnostic or "Docker exited without diagnostics")
    roots: list[dict[str, object]] = []
    environment: dict[str, str] = {}
    mounted_hash = ""
    for line in completed.stdout.splitlines():
        if line.startswith("ROOT_PASS "):
            _, task_id, normal, sanitizer, negative = line.split()
            roots.append(
                {
                    "task_id": task_id,
                    "normal_test_count": int(normal),
                    "sanitizer_test_count": int(sanitizer),
                    "negative_result": negative,
                }
            )
        elif line.startswith("MOUNT_HASH "):
            mounted_hash = line.split(maxsplit=1)[1]
        elif " " in line:
            key, value = line.split(" ", 1)
            if key in {"COMPILER_PATH", "COMPILER_HASH", "COMPILER_VERSION", "CMAKE_VERSION"}:
                environment[key.lower()] = value
    expected_labels = {case.task_id for case in CASES} | {
        "control-domain-identifier-renamed-clone",
        "control-constants-policy-only-clone",
        "control-opposite-end-selection-clone",
    }
    observed_labels = {str(row["task_id"]) for row in roots}
    if observed_labels != expected_labels:
        _fail("reference_tests_failed", f"Docker labels differ: {sorted(expected_labels ^ observed_labels)}")
    if mounted_hash != expected_hash:
        _fail("grader_mount_hash_mismatch", f"owner={expected_hash} docker={mounted_hash}")
    for row in roots:
        if row["normal_test_count"] != 3 or row["sanitizer_test_count"] != 3:
            _fail("sanitizer_test_count_mismatch", str(row))
        if not str(row["task_id"]).startswith("control-") and row["negative_result"] != "rejected":
            _fail("invariant_not_enforced", str(row))
    receipt = {
        "schema_version": "aider-expiry-docker-sanity-v1",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "image_reference": SANITY_IMAGE,
        "image_id": image_inspect.stdout.strip(),
        "network_policy": "none",
        "read_only_root": True,
        "command": _redacted_docker_command(command),
        "owner_tree_hash": expected_hash,
        "mounted_tree_hash": mounted_hash,
        "environment": environment,
        "roots": roots,
        "root_count": 90,
        "control_count": 3,
        "normal_discovery_total": sum(int(row["normal_test_count"]) for row in roots),
        "sanitizer_discovery_total": sum(int(row["sanitizer_test_count"]) for row in roots),
        "pass": True,
    }
    _write_json(out / ".state/docker-sanity-receipt.json", receipt)
    return receipt


def _owner_hash() -> str:
    digest = hashlib.sha256()
    for path in (Path(__file__), Path(__file__).with_name("moonlight_expiry_identifier_cases.py")):
        digest.update(path.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _discover_count(build_dir: Path) -> int | None:
    completed = subprocess.run(
        ["ctest", "--test-dir", str(build_dir), "-N"],
        check=False,
        text=True,
        capture_output=True,
    )
    match = re.search(r"Total Tests:\s*(\d+)", completed.stdout)
    return int(match.group(1)) if match else None


def _host_configure_build(
    work: Path, build: Path, task_source: Path, *, sanitizer: bool
) -> tuple[bool, str]:
    configure = ["cmake", "-S", str(work), "-B", str(build), "-G", "Unix Makefiles", f"-DTASK_SOURCE={task_source}"]
    if sanitizer:
        configure.append("-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer")
    completed = subprocess.run(configure, check=False, text=True, capture_output=True)
    if completed.returncode:
        return False, f"configure: {completed.stdout}\n{completed.stderr}"
    completed = subprocess.run(
        ["cmake", "--build", str(build), "-j2"], check=False, text=True, capture_output=True
    )
    if completed.returncode:
        return False, f"build: {completed.stdout}\n{completed.stderr}"
    return True, ""


def _host_ctest(build: Path, *, sanitizer: bool) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if sanitizer:
        env["ASAN_OPTIONS"] = "detect_leaks=0"
        env["UBSAN_OPTIONS"] = "halt_on_error=1"
    return subprocess.run(
        ["ctest", "--test-dir", str(build), "--output-on-failure"],
        check=False,
        text=True,
        capture_output=True,
        env=env,
    )


def _host_build_and_test(
    work: Path, build: Path, task_source: Path, *, sanitizer: bool
) -> tuple[bool, str]:
    ok, detail = _host_configure_build(work, build, task_source, sanitizer=sanitizer)
    if not ok:
        return False, detail
    completed = _host_ctest(build, sanitizer=sanitizer)
    if completed.returncode:
        return False, f"test: {completed.stdout}\n{completed.stderr}"
    return True, ""


def _verify_root_host(source_root: Path, work_parent: Path, label: str, *, task_root: bool) -> dict[str, object]:
    work = work_parent / label
    shutil.copytree(source_root, work)
    row: dict[str, object] = {"task_id": label, "ok": True, "failure": ""}
    try:
        ok, detail = _host_build_and_test(work, work / "build-normal", work / ".meta/example.cpp", sanitizer=False)
        if not ok:
            row.update(ok=False, failure=f"normal {detail}")
            return row
        normal_count = _discover_count(work / "build-normal")
        ok, detail = _host_build_and_test(work, work / "build-sanitizer", work / ".meta/example.cpp", sanitizer=True)
        if not ok:
            row.update(ok=False, failure=f"sanitizer {detail}")
            return row
        sanitizer_count = _discover_count(work / "build-sanitizer")
        row["normal_test_count"] = normal_count
        row["sanitizer_test_count"] = sanitizer_count
        if not normal_count or normal_count != sanitizer_count:
            row.update(ok=False, failure=f"discovery {normal_count} != {sanitizer_count}")
            return row
        row["negative_result"] = "not_applicable"
        row["direction_mutant_result"] = "not_applicable"
        if task_root:
            ok, detail = _host_configure_build(
                work, work / "build-negative", work / ".meta/negative_false_substitute.cpp", sanitizer=False
            )
            if not ok:
                row.update(ok=False, failure=f"negative build {detail}")
                return row
            completed = _host_ctest(work / "build-negative", sanitizer=False)
            if completed.returncode == 0:
                row.update(ok=False, failure="negative_false_substitute accepted")
                return row
            row["negative_result"] = "rejected"
        if label in {case.task_id for case in CASES if case.parser_index == 9}:
            reference = (work / ".meta/example.cpp").read_text(encoding="utf-8")
            old = "input.minute+input.utc_offset_minutes"
            if reference.count(old) != 1:
                row.update(ok=False, failure="direction mutation drift")
                return row
            mutant = work / "direction_mutant.cpp"
            mutant.write_text(reference.replace(old, "input.minute-input.utc_offset_minutes", 1), encoding="utf-8")
            ok, detail = _host_configure_build(work, work / "build-direction", mutant, sanitizer=False)
            if not ok:
                row.update(ok=False, failure=f"direction mutant build {detail}")
                return row
            completed = _host_ctest(work / "build-direction", sanitizer=False)
            if completed.returncode == 0:
                row.update(ok=False, failure="offset-direction mutant accepted")
                return row
            row["direction_mutant_result"] = "rejected"
        return row
    finally:
        shutil.rmtree(work, ignore_errors=True)


def host_verify(out: Path = DEFAULT_OUT) -> dict[str, object]:
    """Run the normal/sanitizer/negative oracle on the host (campaign gate).

    This mirrors the Docker sanity script without a container: every root's
    reference passes clean normal and fresh ASan/UBSan builds with equal
    positive discovery counts, every compiled false substitute is rejected,
    and every epoch-minute root rejects the offset-direction mutant from
    EXPIRY-AUD-008.
    """
    _assert_output_root(out)
    control_screen(out)
    expected_hash = _tree_hash(out)
    compiler = shutil.which("c++")
    cmake = shutil.which("cmake")
    if not compiler or not cmake:
        _fail("host_toolchain_missing", f"c++={compiler} cmake={cmake}")
    compiler_version = subprocess.run(
        [compiler, "--version"], check=True, text=True, capture_output=True
    ).stdout.splitlines()[0]
    cmake_version = subprocess.run(
        [cmake, "--version"], check=True, text=True, capture_output=True
    ).stdout.splitlines()[0]
    environment = {
        "compiler_path": compiler,
        "compiler_hash": _sha_file(Path(compiler)),
        "compiler_version": compiler_version,
        "cmake_version": cmake_version,
    }
    jobs: list[tuple[Path, str, bool]] = [
        (out / case.task_id, case.task_id, True) for case in CASES
    ]
    controls_root = out / ".state/hard-rule-controls"
    for variant in sorted(controls_root.iterdir()):
        jobs.append((variant / "root", f"control-{variant.name}", False))
    workers = min(12, os.cpu_count() or 4)
    with tempfile.TemporaryDirectory(prefix="w8-expiry-host-") as temporary:
        work_parent = Path(temporary)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            rows = list(
                pool.map(
                    lambda job: _verify_root_host(job[0], work_parent, job[1], task_root=job[2]),
                    jobs,
                )
            )
    rows.sort(key=lambda row: str(row["task_id"]))
    failures = [row for row in rows if not row["ok"]]
    if failures:
        diagnostic = "; ".join(
            f"{row['task_id']}: {str(row['failure'])[:400]}" for row in failures[:5]
        )
        _write_json(
            out / ".state/host-verify-failure.json",
            {
                "schema_version": "aider-expiry-host-verify-failure-v1",
                "owner_tree_hash": expected_hash,
                "environment": environment,
                "failures": failures,
            },
        )
        _fail("reference_tests_failed", diagnostic)
    epoch_minute_ids = {case.task_id for case in CASES if case.parser_index == 9}
    for row in rows:
        if row["normal_test_count"] != 3 or row["sanitizer_test_count"] != 3:
            _fail("sanitizer_test_count_mismatch", str(row))
        label = str(row["task_id"])
        if not label.startswith("control-"):
            if row["negative_result"] != "rejected":
                _fail("invariant_not_enforced", str(row))
            if label in epoch_minute_ids and row["direction_mutant_result"] != "rejected":
                _fail("invariant_not_enforced", f"offset direction undiscriminated: {label}")
    receipt = {
        "schema_version": "aider-expiry-host-verify-v1",
        "evidence_class": "host_verify",
        "campaign_gate": "host verify only; docker_sanity not run in this campaign",
        "owner_tree_hash": expected_hash,
        "environment": environment,
        "roots": rows,
        "root_count": 90,
        "control_count": 3,
        "normal_discovery_total": sum(int(row["normal_test_count"]) for row in rows),
        "sanitizer_discovery_total": sum(int(row["sanitizer_test_count"]) for row in rows),
        "negative_rejections": sum(row["negative_result"] == "rejected" for row in rows),
        "direction_mutant_rejections": sum(
            row["direction_mutant_result"] == "rejected" for row in rows
        ),
        "pass": True,
    }
    _write_json(out / ".state/host-verify-receipt.json", receipt)
    stale_failure = out / ".state/host-verify-failure.json"
    if stale_failure.is_file():
        stale_failure.unlink()
    return receipt


def _evidence_hash(paths: Iterable[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def creator_preflight(out: Path = DEFAULT_OUT, *, require_docker: bool = True) -> dict[str, object]:
    manifest = structural_preflight(out)
    prompts = _prompt_boundary(out)
    diversity = diversity_screen(out)
    controls = control_screen(out)
    contamination = contamination_screen(out)
    docker_path = out / ".state/docker-sanity-receipt.json"
    if require_docker:
        docker = docker_sanity(out)
    elif docker_path.is_file():
        docker = json.loads(docker_path.read_text(encoding="utf-8"))
    else:
        _fail("docker_sanity_not_completed", "run --docker-sanity before creator preflight")
    if docker["owner_tree_hash"] != _tree_hash(out):
        _fail("generator_output_drift", "Docker receipt is stale")
    evidence_paths = (
        out / ".state/candidate-manifest.json",
        out / ".state/prompt-boundary.json",
        out / ".state/diversity-screen.json",
        out / ".state/adversarial-controls.json",
        out / ".state/contamination-screen.json",
        docker_path,
    )
    subject = {
        "schema_version": "aider-creator-audit-subject-v1",
        "family_id": FAMILY_ID,
        "requested_root_count": 90,
        "root_count": 90,
        "tree_hash": _tree_hash(out),
        "owner_hash": _owner_hash(),
        "curriculum_hash": _sha_file(CURRICULUM),
        "family_spec_hash": _sha_file(FAMILY_SPEC),
        "focused_test_hash": _sha_file(FOCUSED_TEST),
        "prompt_path": PROMPT_PATH.as_posix(),
        "prompt_policy_hash": _sha_file(PROMPT_PATH),
        "grader_policy": {"image": SANITY_IMAGE, "network": "none"},
        "evidence_hash": _evidence_hash(evidence_paths),
        "evidence_paths": [path.as_posix() for path in evidence_paths],
        "candidate_manifest_hash": _sha_file(out / ".state/candidate-manifest.json"),
        "source_inventory_hash": _sha_file(out / ".state/source-inventory.json"),
        "holdout_inventory": HOLDOUT_ROOT.as_posix(),
    }
    subject_hash = _sha_bytes(json.dumps(subject, sort_keys=True).encode())
    subject["audit_subject_hash"] = subject_hash
    _write_json(out / ".state/audit-subject.json", subject)
    receipt = {
        "schema_version": "aider-creator-preflight-v1",
        "family_id": FAMILY_ID,
        "audit_subject_hash": subject_hash,
        "root_count": manifest["root_count"],
        "tree_hash": manifest["tree_hash"],
        "prompt_boundary": prompts["pass"],
        "diversity": diversity["pass"],
        "adversarial_controls": all(
            row["semantic_screen"] == "rejected:duplicate_family" for row in controls.values()  # type: ignore[union-attr]
        ),
        "contamination": contamination["pass"],
        "docker_sanity": docker["pass"],
        "normal_discovery_total": docker["normal_discovery_total"],
        "sanitizer_discovery_total": docker["sanitizer_discovery_total"],
        "negative_rejections": sum(
            row["negative_result"] == "rejected" for row in docker["roots"]  # type: ignore[union-attr]
        ),
        "status": "creator_preflight_pass",
        "strongest_status": "awaiting_independent_audit",
        "non_claims": ["no SFT release", "no training authorization", "no benchmark uplift"],
    }
    _write_json(out / ".state/creator-preflight-receipt.json", receipt)
    cycles = out / ".state/cycles"
    cycles.mkdir(parents=True, exist_ok=True)
    number = len(list(cycles.glob("cycle-*.json"))) + 1
    cycle = {
        "schema_version": "aider-creator-cycle-v1",
        "cycle": number,
        "state": "creator_preflight",
        "audit_subject_hash": subject_hash,
        "tree_hash": manifest["tree_hash"],
        "owner_hash": subject["owner_hash"],
        "curriculum_hash": subject["curriculum_hash"],
        "focused_test_hash": subject["focused_test_hash"],
        "retained": sorted(case.task_id for case in CASES),
        "replaced": [],
        "rejected": [],
        "review": [],
        "blocked": [],
        "finding_ids": [],
        "status": "awaiting_independent_audit",
        "evidence_paths": subject["evidence_paths"],
    }
    _write_json(cycles / f"cycle-{number:02d}.json", cycle)
    return receipt


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify-host", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--creator-preflight", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    build(args.out, force=args.force)
    if args.verify_core:
        structural_preflight(args.out)
        _prompt_boundary(args.out)
        diversity_screen(args.out)
        control_screen(args.out)
        contamination_screen(args.out)
    if args.verify_host:
        host_verify(args.out)
    if args.docker_sanity:
        docker_sanity(args.out)
    if args.creator_preflight:
        creator_preflight(args.out, require_docker=not args.docker_sanity)
    print(json.dumps({"out": args.out.as_posix(), "roots": 90, "tree_hash": _tree_hash(args.out)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
