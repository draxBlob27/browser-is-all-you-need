"""Materialize the newly authored local date-difference Aider curriculum."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from w8_biayn.integrations.moonlight_aider_task_filenames import task_named_files
from typing import Sequence

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks-reverify/aider-text-grid-reshaping/date-difference")
LEGACY_OUT = Path(".w8-biayn/data/aider-tasks/aider-dates-and-clocks/date-difference")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATE_DIFFERENCE_CURRICULUM.md"
FAMILY_SPEC = "docs/aider-tasks-spec/aider-text-grid-reshaping/date-difference.md"
SELECTED_PROMPT = "docs/aider-tasks-spec/prompts/remediate-family-reverify.md"
FAMILY_ID = "aider-text-grid-reshaping-date-difference-v3"
LEGACY_FAMILY_ID = "aider-dates-and-clocks-date-difference-v1"
SANITY_IMAGE = "w8-biayn-polyglot-cpp@sha256:4cff5e0d746a95fc3cf787ce7e1519485ca521ad1040ccbedb314d958e967991"
NORMALIZER = "date-difference-artifact-materiality-v2"
HARD_RULE_DIMENSIONS = (
    "public_api",
    "owned_state_or_algorithm",
    "mutation_selection_rules",
    "invalid_boundary_behavior",
    "reference_control_flow",
    "deterministic_oracle",
    "topic_negative_fixture",
)
HARD_RULE_THRESHOLDS = {
    "public_api": 0.75,
    "owned_state_or_algorithm": 0.65,
    "mutation_selection_rules": 0.70,
    "invalid_boundary_behavior": 0.50,
    "reference_control_flow": 0.65,
    "deterministic_oracle": 0.80,
    "topic_negative_fixture": 0.40,
}
HARD_RULE_MIN_SYMMETRIC_DIFFERENCE = {
    "public_api": 6,
    "owned_state_or_algorithm": 12,
    "mutation_selection_rules": 8,
    "invalid_boundary_behavior": 6,
    "reference_control_flow": 12,
    "deterministic_oracle": 10,
    "topic_negative_fixture": 2,
}
ADVERSARIAL_CONTROLS = (
    "domain-identifier-renamed",
    "constants-or-policy-only",
    "opposite-end-selection",
)
NEGATIVE_DESCRIPTIONS = {
    "dated-warranty-audit": "treat the first expired day as covered",
    "dated-project-burnup": "count weekend dates as project workdays",
    "dated-library-loan": "charge closure dates as overdue days",
    "dated-experiment-window": "ignore every declared blackout interval",
    "dated-retention-review": "delay expiry until strictly after its equality boundary",
    "dated-maintenance-ledger": "reuse the first asset state for interleaved assets",
    "dated-subscription-proration": "select a future price band before its effective date",
    "dated-custody-chain": "classify equality with the holding limit as a breach",
}
BENCHMARK_SLUGS = (
    "all-your-base", "allergies", "bank-account", "binary-search-tree",
    "circular-buffer", "clock", "complex-numbers", "crypto-square", "diamond",
    "dnd-character", "gigasecond", "grade-school", "kindergarten-garden",
    "knapsack", "linked-list", "meetup", "parallel-letter-frequency",
    "perfect-numbers", "phone-number", "queen-attack", "robot-name", "space-age",
    "spiral-matrix", "sublist", "yacht", "zebra-puzzle",
)


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    title: str
    blurb: str
    legacy_id: str | None = None
    disposition: str = "repair-in-place"


TASKS = (
    TaskSpec("dated-warranty-audit", "Warranty claim audit", "Audit warranty claims against inclusive coverage policies."),
    TaskSpec("dated-project-burnup", "Project burn-up report", "Count scheduled workdays between project milestones."),
    TaskSpec("dated-library-loan", "Library loan reconciliation", "Reconcile loan dates, closures, and tiered overdue fees."),
    TaskSpec("dated-experiment-window", "Experiment observation window", "Subtract blackout spans from a study observation window."),
    TaskSpec("dated-retention-review", "Records retention review", "Review archived records using category retention policies."),
    TaskSpec("dated-maintenance-ledger", "Maintenance interval ledger", "Measure per-asset service gaps across ordered maintenance events.", None, "replace"),
    TaskSpec("dated-subscription-proration", "Subscription proration", "Allocate integer billing units across dated price bands.", None, "replace"),
    TaskSpec("dated-custody-chain", "Evidence custody chain", "Validate dated custody transfers and per-stage handling limits.", None, "replace"),
)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class VerificationError(RuntimeError):
    pass


def _fail(code: str, detail: str = "") -> None:
    raise VerificationError(f"{code}: {detail}" if detail else code)


def _sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        return "sha256:absent"
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode()
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return "sha256:" + digest.hexdigest()


def _generator_revision() -> str:
    return _sha256(Path(__file__).read_bytes())


def _reference_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for relative in (".meta/example.h", ".meta/example.cpp"):
        digest.update(relative.encode())
        digest.update((root / relative).read_bytes())
    return "sha256:" + digest.hexdigest()


DATE_HELPERS = r'''namespace {
bool leap(int y) { return y % 4 == 0 && (y % 100 != 0 || y % 400 == 0); }
int month_days(int y, int m) { static const int d[] = {31,28,31,30,31,30,31,31,30,31,30,31}; return m == 2 ? d[1] + (leap(y) ? 1 : 0) : (m >= 1 && m <= 12 ? d[m - 1] : 0); }
bool valid(Date d) { return d.year >= 1 && d.month >= 1 && d.month <= 12 && d.day >= 1 && d.day <= month_days(d.year, d.month); }
long long serial(Date d) { long long y = d.year - 1; return 365 * y + y / 4 - y / 100 + y / 400 + [&] { int n = 0; for (int m = 1; m < d.month; ++m) n += month_days(d.year, m); return n + d.day - 1; }(); }
[[maybe_unused]] Date from_serial(long long n) { int y = 1; while (n >= (leap(y) ? 366 : 365)) { n -= leap(y) ? 366 : 365; ++y; } int m = 1; while (n >= month_days(y, m)) n -= month_days(y, m++); return {y, m, static_cast<int>(n) + 1}; }
[[maybe_unused]] int weekday(Date d) { return static_cast<int>(serial(d) % 7); }
}  // namespace
'''


def _warranty() -> dict[str, str]:
    header = r'''#ifndef TASK_H
#define TASK_H
#include <string>
#include <vector>
namespace curriculum {
struct Date { int year; int month; int day; };
enum class ClaimStatus { covered, expired, invalid_date, before_purchase, duplicate_id };
struct WarrantyPolicy { int coverage_days; };
struct WarrantyClaim { std::string id; Date purchased; Date claimed; };
struct ClaimFinding { std::string id; ClaimStatus status; int elapsed_days = 0; };
class WarrantyAudit { public: std::vector<ClaimFinding> audit(const WarrantyPolicy&, const std::vector<WarrantyClaim>&) const; };
}  // namespace curriculum
#endif
'''
    reference = f'''#include "task.h"
#include <set>
#include <stdexcept>
namespace curriculum {{
{DATE_HELPERS}
std::vector<ClaimFinding> WarrantyAudit::audit(const WarrantyPolicy& policy, const std::vector<WarrantyClaim>& claims) const {{
  if (policy.coverage_days <= 0) throw std::invalid_argument("coverage_days must be positive");
  std::set<std::string> seen; std::vector<ClaimFinding> out;
  for (const auto& claim : claims) {{
    if (!seen.insert(claim.id).second || claim.id.empty()) {{ out.push_back({{claim.id, ClaimStatus::duplicate_id, 0}}); continue; }}
    if (!valid(claim.purchased) || !valid(claim.claimed)) {{ out.push_back({{claim.id, ClaimStatus::invalid_date, 0}}); continue; }}
    const long long age = serial(claim.claimed) - serial(claim.purchased);
    if (age < 0) out.push_back({{claim.id, ClaimStatus::before_purchase, static_cast<int>(age)}});
    else out.push_back({{claim.id, age < policy.coverage_days ? ClaimStatus::covered : ClaimStatus::expired, static_cast<int>(age)}});
  }} return out;
}}
}}  // namespace curriculum
'''
    starter = '''#include "task.h"\nnamespace curriculum {\nstd::vector<ClaimFinding> WarrantyAudit::audit(const WarrantyPolicy&, const std::vector<WarrantyClaim>&) const { return {}; }\n}  // namespace curriculum\n'''
    visible = r'''#include "task.h"
using namespace curriculum;
int main() { WarrantyAudit a; auto r = a.audit({3}, {{"same", {2024,2,28}, {2024,2,28}}, {"edge", {2024,2,28}, {2024,3,1}}, {"late", {2024,2,28}, {2024,3,2}}}); return r.size()!=3 || r[0].status!=ClaimStatus::covered || r[1].status!=ClaimStatus::covered || r[2].status!=ClaimStatus::expired; }
'''
    hidden = r'''#include "task.h"
#include <stdexcept>
using namespace curriculum;
int main() { WarrantyAudit a; auto r=a.audit({1}, {{"a",{2000,2,29},{2000,2,29}}, {"b",{1900,2,29},{1900,3,1}}, {"c",{2025,1,2},{2025,1,1}}, {"a",{2025,1,1},{2025,1,1}}}); bool threw=false; try { a.audit({0},{}); } catch(const std::invalid_argument&) { threw=true; } return !threw || r[0].status!=ClaimStatus::covered || r[1].status!=ClaimStatus::invalid_date || r[2].status!=ClaimStatus::before_purchase || r[3].status!=ClaimStatus::duplicate_id; }
'''
    instructions = """# Instructions

Implement `WarrantyAudit::audit`. Dates are proleptic Gregorian dates (year >= 1). A policy's `coverage_days` must be positive or the method throws `std::invalid_argument`. Purchase day is coverage day zero: a claim is covered exactly when its elapsed calendar-day age is less than `coverage_days`; therefore the last covered date is included. Process claims in input order. An empty or repeated claim ID is `duplicate_id`; invalid dates are `invalid_date`; a valid claim before purchase is `before_purchase`. These findings are per-claim diagnostics and do not prevent later claims from being audited.
"""
    return {"header": header, "reference": reference, "starter": starter, "visible": visible, "hidden": hidden, "instructions": instructions}


def _burnup() -> dict[str, str]:
    header = r'''#ifndef TASK_H
#define TASK_H
#include <string>
#include <vector>
namespace curriculum { struct Date { int year; int month; int day; }; enum class BurnupStatus { ok, invalid_date, reversed, duplicate_milestone, duplicate_holiday }; struct Milestone { std::string id; Date date; }; struct BurnupReport { BurnupStatus status; int workdays = 0; }; class ProjectBurnup { public: BurnupReport report(const Milestone&, const Milestone&, const std::vector<Date>&) const; }; }
#endif
'''
    reference = f'''#include "task.h"
#include <set>
namespace curriculum {{
{DATE_HELPERS}
BurnupReport ProjectBurnup::report(const Milestone& start, const Milestone& end, const std::vector<Date>& holidays) const {{
  if (start.id.empty() || end.id.empty() || start.id == end.id) return {{BurnupStatus::duplicate_milestone, 0}};
  if (!valid(start.date) || !valid(end.date)) return {{BurnupStatus::invalid_date, 0}};
  if (serial(end.date) < serial(start.date)) return {{BurnupStatus::reversed, 0}};
  std::set<long long> closed; for (Date d : holidays) {{ if (!valid(d)) return {{BurnupStatus::invalid_date, 0}}; if (!closed.insert(serial(d)).second) return {{BurnupStatus::duplicate_holiday, 0}}; }}
  int total=0; for (long long day=serial(start.date)+1; day<=serial(end.date); ++day) {{ Date d=from_serial(day); if (weekday(d)<5 && !closed.count(day)) ++total; }} return {{BurnupStatus::ok,total}};
}}
}}  // namespace curriculum
'''
    starter = '''#include "task.h"\nnamespace curriculum { BurnupReport ProjectBurnup::report(const Milestone&, const Milestone&, const std::vector<Date>&) const { return {BurnupStatus::ok}; } }\n'''
    visible = r'''#include "task.h"
using namespace curriculum; int main(){ ProjectBurnup p; auto r=p.report({"plan",{2024,2,28}},{"ship",{2024,3,4}},{{2024,3,1}}); return r.status!=BurnupStatus::ok || r.workdays!=2; }
'''
    hidden = r'''#include "task.h"
using namespace curriculum; int main(){ ProjectBurnup p; auto a=p.report({"a",{1900,2,28}},{"b",{1900,3,1}},{}); auto b=p.report({"a",{2000,2,28}},{"b",{2000,3,1}},{}); auto c=p.report({"a",{2024,1,2}},{"b",{2024,1,1}},{}); auto d=p.report({"a",{2024,1,1}},{"b",{2024,1,2}},{{2024,1,1},{2024,1,1}}); return a.workdays!=1 || b.workdays!=2 || c.status!=BurnupStatus::reversed || d.status!=BurnupStatus::duplicate_holiday; }
'''
    instructions = """# Instructions

Implement `ProjectBurnup::report`. Milestone IDs must be non-empty and distinct. Count workdays in the half-open-to-closed elapsed interval `(start.date, end.date]`: the start milestone is not counted and the end milestone is counted when it is Monday through Friday. Saturday and Sunday are non-working days. Caller-provided holidays are also excluded, must be valid Gregorian dates, and must be unique even if they fall on a weekend or outside the interval. Return the first applicable diagnostic in this order: duplicate milestone ID, invalid date, reversed milestones, duplicate holiday.
"""
    return {"header":header,"reference":reference,"starter":starter,"visible":visible,"hidden":hidden,"instructions":instructions}


def _loan() -> dict[str, str]:
    header = r'''#ifndef TASK_H
#define TASK_H
#include <vector>
namespace curriculum { struct Date { int year; int month; int day; }; enum class LoanStatus { settled, invalid_date, due_before_checkout, return_before_checkout, duplicate_closure }; struct FeePolicy { int free_days; int first_fee; int later_fee; }; struct Loan { Date checkout; Date due; Date returned; }; struct LoanResult { LoanStatus status;
 int overdue_days=0; int fee_units=0; }; class LoanReconciler { public: LoanResult reconcile(const Loan&, const FeePolicy&, const std::vector<Date>&) const; }; }
#endif
'''
    reference = f'''#include "task.h"
#include <set>
#include <stdexcept>
namespace curriculum {{
{DATE_HELPERS}
LoanResult LoanReconciler::reconcile(const Loan& loan, const FeePolicy& fee, const std::vector<Date>& closures) const {{
 if (fee.free_days<0 || fee.first_fee<0 || fee.later_fee<0) throw std::invalid_argument("fees must be nonnegative");
 if(!valid(loan.checkout)||!valid(loan.due)||!valid(loan.returned)) return {{LoanStatus::invalid_date, 0, 0}};
 if(serial(loan.due)<serial(loan.checkout)) return {{LoanStatus::due_before_checkout, 0, 0}};
 if(serial(loan.returned)<serial(loan.checkout)) return {{LoanStatus::return_before_checkout, 0, 0}};
 std::set<long long> closed; for(Date d:closures) {{ if(!valid(d)) return {{LoanStatus::invalid_date, 0, 0}};
 if(!closed.insert(serial(d)).second) return {{LoanStatus::duplicate_closure, 0, 0}}; }} int overdue=0; for(long long x=serial(loan.due)+1;x<=serial(loan.returned);++x) if(!closed.count(x)) ++overdue;
 int bill=overdue>fee.free_days?overdue-fee.free_days:0; return {{LoanStatus::settled,overdue,bill?fee.first_fee+(bill-1)*fee.later_fee:0}};
}}
}}  // namespace curriculum
'''
    starter='''#include "task.h"\nnamespace curriculum { LoanResult LoanReconciler::reconcile(const Loan&,const FeePolicy&,const std::vector<Date>&) const { return {}; } }\n'''
    visible=r'''#include "task.h"
using namespace curriculum; int main(){ LoanReconciler r; auto x=r.reconcile({{2024,2,28},{2024,2,29},{2024,3,4}},{1,10,3},{{2024,3,2}}); return x.status!=LoanStatus::settled || x.overdue_days!=3 || x.fee_units!=13; }
'''
    hidden=r'''#include "task.h"
#include <stdexcept>
using namespace curriculum; int main(){ LoanReconciler r; auto a=r.reconcile({{2024,1,2},{2024,1,1},{2024,1,3}},{0,2,1},{}); auto b=r.reconcile({{2024,1,2},{2024,1,4},{2024,1,1}},{0,2,1},{}); auto c=r.reconcile({{2024,1,1},{2024,1,1},{2024,1,1}},{0,2,1},{}); bool t=false;try{r.reconcile({{2024,1,1},{2024,1,1},{2024,1,1}},{-1,0,0},{});}catch(const std::invalid_argument&){t=true;} return a.status!=LoanStatus::due_before_checkout || b.status!=LoanStatus::return_before_checkout || c.fee_units!=0 || !t; }
'''
    instructions="""# Instructions

Implement `LoanReconciler::reconcile`. `FeePolicy` fields must be non-negative or throw `std::invalid_argument`. A return on its due date is not late. Overdue dates are the closed interval `(due, returned]`; each valid closure date in that interval removes one overdue day. Closure records must be unique, even outside the interval. After `free_days`, the first billable day costs `first_fee` and each later billable day costs `later_fee`. Return relation diagnostics in the stated enum order after invalid calendar-date validation.
"""
    return {"header":header,"reference":reference,"starter":starter,"visible":visible,"hidden":hidden,"instructions":instructions}


def _experiment() -> dict[str, str]:
    header=r'''#ifndef TASK_H
#define TASK_H
#include <vector>
namespace curriculum { struct Date { int year; int month; int day; }; struct Span { Date begin; Date end; }; enum class WindowStatus { ok, invalid_date, invalid_span }; struct WindowResult { WindowStatus status; int observed_days=0; std::vector<Span> segments; }; class ObservationWindow { public: WindowResult subtract(const Span&, const std::vector<Span>&) const; }; }
#endif
'''
    reference=f'''#include "task.h"
#include <algorithm>
namespace curriculum {{
{DATE_HELPERS}
WindowResult ObservationWindow::subtract(const Span& study, const std::vector<Span>& blackouts) const {{ if(!valid(study.begin)||!valid(study.end)) return {{WindowStatus::invalid_date, 0, {{}}}}; long long a=serial(study.begin),b=serial(study.end);
 if(a>b) return {{WindowStatus::invalid_span, 0, {{}}}};
 std::vector<std::pair<long long,long long>> v; for(auto s:blackouts) {{ if(!valid(s.begin)||!valid(s.end)) return {{WindowStatus::invalid_date, 0, {{}}}}; auto l=serial(s.begin),r=serial(s.end);
 if(l>r) return {{WindowStatus::invalid_span, 0, {{}}}};
 l=std::max(l,a);r=std::min(r,b);if(l<r)v.push_back({{l,r}}); }} std::sort(v.begin(),v.end()); std::vector<std::pair<long long,long long>> m; for(auto x:v) {{ if(m.empty()||x.first>m.back().second)m.push_back(x);else m.back().second=std::max(m.back().second,x.second); }} WindowResult out{{WindowStatus::ok, 0, {{}}}}; long long cur=a; for(auto x:m) {{ if(cur<x.first) {{out.segments.push_back({{from_serial(cur),from_serial(x.first)}});out.observed_days+=static_cast<int>(x.first-cur);}} cur=std::max(cur,x.second); }} if(cur<b) {{out.segments.push_back({{from_serial(cur),from_serial(b)}});out.observed_days+=static_cast<int>(b-cur);}} return out; }}
}}  // namespace curriculum
'''
    starter='''#include "task.h"\nnamespace curriculum { WindowResult ObservationWindow::subtract(const Span&,const std::vector<Span>&) const { return {}; } }\n'''
    visible=r'''#include "task.h"
using namespace curriculum; int main(){ ObservationWindow w; auto r=w.subtract({{2024,2,28},{2024,3,5}},{{{2024,2,29},{2024,3,2}}}); return r.status!=WindowStatus::ok || r.observed_days!=4 || r.segments.size()!=2; }
'''
    hidden=r'''#include "task.h"
using namespace curriculum; int main(){ ObservationWindow w; auto a=w.subtract({{2000,2,28},{2000,3,2}},{{{2000,2,29},{2000,3,1}},{{2000,3,1},{2000,3,2}}}); auto b=w.subtract({{2024,1,2},{2024,1,1}},{}); auto c=w.subtract({{2024,2,30},{2024,3,1}},{}); return a.observed_days!=1 || a.segments.size()!=1 || b.status!=WindowStatus::invalid_span || c.status!=WindowStatus::invalid_date; }
'''
    instructions="""# Instructions

Implement `ObservationWindow::subtract`. Every span is half-open: `[begin, end)`. Equal endpoints are valid empty spans; reversed endpoints are `invalid_span`. Invalid calendar dates are `invalid_date`. A valid call returns the portions of the study span not covered by blackouts, in chronological order. Blackouts may overlap or touch and must be canonicalized before subtraction. Blackouts outside the study span have no effect. On any invalid input, return a diagnostic with no partial segments.
"""
    return {"header":header,"reference":reference,"starter":starter,"visible":visible,"hidden":hidden,"instructions":instructions}


def _retention() -> dict[str, str]:
    header=r'''#ifndef TASK_H
#define TASK_H
#include <string>
#include <vector>
namespace curriculum { struct Date { int year; int month; int day; }; enum class ReviewStatus { active, review_due, expired, invalid_date, unknown_category, invalid_policy, duplicate_category }; struct RetentionPolicy { std::string category; int retention_days; int review_lead_days; }; struct ArchiveRecord { std::string id; std::string category; Date archived; }; struct RetentionFinding { std::string id; ReviewStatus status; int remaining_days=0; }; class RetentionReview { public: std::vector<RetentionFinding> review(const Date&, const std::vector<RetentionPolicy>&, const std::vector<ArchiveRecord>&) const; }; }
#endif
'''
    reference=f'''#include "task.h"
#include <map>
namespace curriculum {{
{DATE_HELPERS}
std::vector<RetentionFinding> RetentionReview::review(const Date& today,const std::vector<RetentionPolicy>& policies,const std::vector<ArchiveRecord>& records) const {{ std::vector<RetentionFinding> out;
 if(!valid(today)) {{for(auto r:records)out.push_back({{r.id,ReviewStatus::invalid_date,0}});return out;}} std::map<std::string,RetentionPolicy> by; for(auto p:policies) {{if(p.category.empty()||p.retention_days<=0||p.review_lead_days<0){{for(auto r:records)out.push_back({{r.id,ReviewStatus::invalid_policy,0}});return out;}}if(!by.emplace(p.category,p).second){{for(auto r:records)out.push_back({{r.id,ReviewStatus::duplicate_category,0}});return out;}}}} for(auto r:records) {{if(!valid(r.archived)){{out.push_back({{r.id,ReviewStatus::invalid_date,0}});continue;}}auto it=by.find(r.category);if(it==by.end()){{out.push_back({{r.id,ReviewStatus::unknown_category,0}});continue;}}long long age=serial(today)-serial(r.archived);int remain=it->second.retention_days-static_cast<int>(age);if(age>=it->second.retention_days)out.push_back({{r.id,ReviewStatus::expired,remain}});else if(age>=it->second.retention_days-it->second.review_lead_days)out.push_back({{r.id,ReviewStatus::review_due,remain}});else out.push_back({{r.id,ReviewStatus::active,remain}});}}return out; }}
}}  // namespace curriculum
'''
    starter='''#include "task.h"\nnamespace curriculum { std::vector<RetentionFinding> RetentionReview::review(const Date&,const std::vector<RetentionPolicy>&,const std::vector<ArchiveRecord>&) const { return {}; } }\n'''
    visible=r'''#include "task.h"
using namespace curriculum; int main(){ RetentionReview r; auto x=r.review({2024,3,1},{{"lab",10,3}},{{"a","lab",{2024,2,20}},{"b","lab",{2024,2,22}},{"c","lab",{2024,2,21}}}); return x[0].status!=ReviewStatus::expired || x[1].status!=ReviewStatus::review_due || x[2].status!=ReviewStatus::review_due; }
'''
    hidden=r'''#include "task.h"
using namespace curriculum; int main(){ RetentionReview r; auto a=r.review({2000,3,1},{{"x",2,1}},{{"a","x",{2000,2,28}},{"b","none",{2000,2,29}},{"c","x",{1900,2,29}}}); auto b=r.review({2024,1,1},{{"x",1,0},{"x",2,0}},{{"a","x",{2024,1,1}}}); return a[0].status!=ReviewStatus::expired || a[1].status!=ReviewStatus::unknown_category || a[2].status!=ReviewStatus::invalid_date || b[0].status!=ReviewStatus::duplicate_category; }
'''
    instructions="""# Instructions

Implement `RetentionReview::review`. Policies require a non-empty unique category, positive `retention_days`, and non-negative `review_lead_days`; an invalid policy makes every record `invalid_policy` or `duplicate_category` with no partial classification. For each valid record, `remaining_days` is `retention_days - elapsed_days` from archive date to `today`. At equality with the retention duration the record is `expired`; otherwise equality with the review-lead threshold is `review_due`; earlier records are `active`. Unknown categories and invalid dates are record diagnostics. Process records in input order.
"""
    return {"header":header,"reference":reference,"starter":starter,"visible":visible,"hidden":hidden,"instructions":instructions}


def _maintenance() -> dict[str, str]:
    header = r'''#ifndef TASK_H
#define TASK_H
#include <string>
#include <vector>
namespace curriculum {
struct Date { int year; int month; int day; };
struct ServiceEvent { std::string event_id; std::string asset_id; Date performed; };
enum class LedgerStatus { ok, invalid_date, empty_id, duplicate_event, asset_time_reversal };
struct AssetGap { std::string asset_id; int largest_gap_days = 0; int event_count = 0; };
struct LedgerResult { LedgerStatus status; std::vector<AssetGap> assets; };
class MaintenanceLedger { public: LedgerResult summarize(const std::vector<ServiceEvent>&) const; };
}  // namespace curriculum
#endif
'''
    reference = f'''#include "task.h"
#include <map>
#include <set>
namespace curriculum {{
{DATE_HELPERS}
LedgerResult MaintenanceLedger::summarize(const std::vector<ServiceEvent>& events) const {{
  struct State {{ long long last; int largest; int count; }};
  std::map<std::string, State> state; std::set<std::string> event_ids;
  for (const auto& event : events) {{
    if (event.event_id.empty() || event.asset_id.empty()) return {{LedgerStatus::empty_id, {{}}}};
    if (!valid(event.performed)) return {{LedgerStatus::invalid_date, {{}}}};
    if (!event_ids.insert(event.event_id).second) return {{LedgerStatus::duplicate_event, {{}}}};
    const long long day = serial(event.performed); auto it = state.find(event.asset_id);
    if (it == state.end()) {{ state.emplace(event.asset_id, State{{day, 0, 1}}); continue; }}
    if (day < it->second.last) return {{LedgerStatus::asset_time_reversal, {{}}}};
    const int gap = static_cast<int>(day - it->second.last);
    if (gap > it->second.largest) it->second.largest = gap;
    it->second.last = day; ++it->second.count;
  }}
  LedgerResult out{{LedgerStatus::ok, {{}}}};
  for (const auto& item : state) out.assets.push_back({{item.first, item.second.largest, item.second.count}});
  return out;
}}
}}  // namespace curriculum
'''
    starter = '''#include "task.h"\nnamespace curriculum { LedgerResult MaintenanceLedger::summarize(const std::vector<ServiceEvent>&) const { return {}; } }\n'''
    visible = r'''#include "task.h"
using namespace curriculum;
int main() { MaintenanceLedger ledger; auto r=ledger.summarize({{"e1","a",{2024,2,28}},{"e2","b",{2024,3,2}},{"e3","a",{2024,3,1}}}); return r.status!=LedgerStatus::ok || r.assets.size()!=2 || r.assets[0].asset_id!="a" || r.assets[0].largest_gap_days!=2 || r.assets[0].event_count!=2; }
'''
    hidden = r'''#include "task.h"
using namespace curriculum;
int main() { MaintenanceLedger ledger; auto leap=ledger.summarize({{"a","x",{2000,2,28}},{"b","x",{2000,3,1}},{"c","x",{2000,3,1}}}); auto century=ledger.summarize({{"a","x",{1900,2,28}},{"b","x",{1900,3,1}}}); auto reverse=ledger.summarize({{"a","x",{2024,2,2}},{"b","x",{2024,2,1}}}); auto dup=ledger.summarize({{"a","x",{2024,1,1}},{"a","y",{2024,1,2}}}); return leap.assets[0].largest_gap_days!=2 || leap.assets[0].event_count!=3 || century.assets[0].largest_gap_days!=1 || reverse.status!=LedgerStatus::asset_time_reversal || dup.status!=LedgerStatus::duplicate_event; }
'''
    instructions = """# Instructions

Implement `MaintenanceLedger::summarize`. Process service events in input order while owning independent last-service state for each asset. Event and asset IDs must be non-empty; dates must be valid Gregorian dates; event IDs are globally unique. A date earlier than the preceding event for the same asset is `asset_time_reversal`, while interleaving another asset is allowed. On any error return no partial summaries. For a valid ledger, return assets in lexicographic ID order with event count and the largest elapsed calendar-day gap between consecutive events; a singleton's largest gap is zero.
"""
    return {"header":header,"reference":reference,"starter":starter,"visible":visible,"hidden":hidden,"instructions":instructions}


def _proration() -> dict[str, str]:
    header = r'''#ifndef TASK_H
#define TASK_H
#include <vector>
namespace curriculum {
struct Date { int year; int month; int day; };
struct RateBand { Date effective; int units_per_day; };
enum class ProrationStatus { ok, invalid_date, reversed_window, invalid_rate, unsorted_band, missing_initial_band };
struct ProrationResult { ProrationStatus status; int active_days = 0; long long billed_units = 0; std::vector<int> days_by_band; };
class SubscriptionProrater { public: ProrationResult calculate(Date, Date, const std::vector<RateBand>&) const; };
}  // namespace curriculum
#endif
'''
    reference = f'''#include "task.h"
namespace curriculum {{
{DATE_HELPERS}
ProrationResult SubscriptionProrater::calculate(Date begin, Date end, const std::vector<RateBand>& bands) const {{
  if (!valid(begin) || !valid(end)) return {{ProrationStatus::invalid_date, 0, 0, {{}}}};
  const long long first = serial(begin), last = serial(end);
  if (last < first) return {{ProrationStatus::reversed_window, 0, 0, {{}}}};
  if (bands.empty() || !valid(bands.front().effective) || serial(bands.front().effective) > first) return {{ProrationStatus::missing_initial_band, 0, 0, {{}}}};
  for (std::size_t i=0;i<bands.size();++i) {{
    if (!valid(bands[i].effective)) return {{ProrationStatus::invalid_date, 0, 0, {{}}}};
    if (bands[i].units_per_day < 0) return {{ProrationStatus::invalid_rate, 0, 0, {{}}}};
    if (i && serial(bands[i].effective) <= serial(bands[i-1].effective)) return {{ProrationStatus::unsorted_band, 0, 0, {{}}}};
  }}
  ProrationResult out{{ProrationStatus::ok, static_cast<int>(last-first), 0, std::vector<int>(bands.size(),0)}};
  std::size_t band=0;
  for (long long day=first; day<last; ++day) {{ while (band+1<bands.size() && serial(bands[band+1].effective)<=day) ++band; ++out.days_by_band[band]; out.billed_units += bands[band].units_per_day; }}
  return out;
}}
}}  // namespace curriculum
'''
    starter = '''#include "task.h"\nnamespace curriculum { ProrationResult SubscriptionProrater::calculate(Date, Date, const std::vector<RateBand>&) const { return {}; } }\n'''
    visible = r'''#include "task.h"
using namespace curriculum;
int main(){ SubscriptionProrater p; auto r=p.calculate({2024,2,28},{2024,3,3},{{{2024,1,1},2},{{2024,3,1},5}}); return r.status!=ProrationStatus::ok || r.active_days!=4 || r.billed_units!=14 || r.days_by_band.size()!=2 || r.days_by_band[0]!=2 || r.days_by_band[1]!=2; }
'''
    hidden = r'''#include "task.h"
using namespace curriculum;
int main(){ SubscriptionProrater p; auto empty=p.calculate({2024,1,1},{2024,1,1},{{{2024,1,1},3}}); auto missing=p.calculate({2024,1,1},{2024,1,2},{{{2024,1,2},3}}); auto unsorted=p.calculate({2024,1,1},{2024,1,2},{{{2023,1,1},1},{{2023,1,1},2}}); auto century=p.calculate({1900,2,28},{1900,3,1},{{{1900,1,1},7}}); return empty.active_days!=0 || empty.billed_units!=0 || missing.status!=ProrationStatus::missing_initial_band || unsorted.status!=ProrationStatus::unsorted_band || century.active_days!=1 || century.billed_units!=7; }
'''
    instructions = """# Instructions

Implement `SubscriptionProrater::calculate` for the half-open active window `[begin,end)`. Return `reversed_window` when end precedes begin; equal dates are a valid zero-day invoice. Rate bands are chronological change points: rates must be non-negative, every effective date valid, and dates strictly increasing. The first band must be effective on or before begin. For each active date choose the latest effective band, preserve input-band order in `days_by_band`, and accumulate exact integer billing units. Invalid inputs produce no partial allocation.
"""
    return {"header":header,"reference":reference,"starter":starter,"visible":visible,"hidden":hidden,"instructions":instructions}


def _custody() -> dict[str, str]:
    header = r'''#ifndef TASK_H
#define TASK_H
#include <string>
#include <vector>
namespace curriculum {
struct Date { int year; int month; int day; };
struct CustodyTransfer { std::string handler; Date accepted; int maximum_days; };
enum class CustodyStatus { ok, invalid_date, empty_handler, duplicate_handler, invalid_limit, chronological_reversal };
struct CustodyStage { std::string handler; int held_days = 0; bool breached = false; };
struct CustodyResult { CustodyStatus status; int total_days = 0; std::vector<CustodyStage> completed; };
class CustodyChain { public: CustodyResult inspect(const std::vector<CustodyTransfer>&) const; };
}  // namespace curriculum
#endif
'''
    reference = f'''#include "task.h"
#include <set>
namespace curriculum {{
{DATE_HELPERS}
CustodyResult CustodyChain::inspect(const std::vector<CustodyTransfer>& transfers) const {{
  std::set<std::string> handlers;
  for (const auto& transfer : transfers) {{
    if (transfer.handler.empty()) return {{CustodyStatus::empty_handler, 0, {{}}}};
    if (!valid(transfer.accepted)) return {{CustodyStatus::invalid_date, 0, {{}}}};
    if (transfer.maximum_days < 0) return {{CustodyStatus::invalid_limit, 0, {{}}}};
    if (!handlers.insert(transfer.handler).second) return {{CustodyStatus::duplicate_handler, 0, {{}}}};
  }}
  CustodyResult out{{CustodyStatus::ok,0,{{}}}};
  for (std::size_t i=1;i<transfers.size();++i) {{
    const long long elapsed=serial(transfers[i].accepted)-serial(transfers[i-1].accepted);
    if (elapsed<0) return {{CustodyStatus::chronological_reversal, 0, {{}}}};
    const int days=static_cast<int>(elapsed); out.total_days+=days;
    out.completed.push_back({{transfers[i-1].handler,days,days>transfers[i-1].maximum_days}});
  }}
  return out;
}}
}}  // namespace curriculum
'''
    starter = '''#include "task.h"\nnamespace curriculum { CustodyResult CustodyChain::inspect(const std::vector<CustodyTransfer>&) const { return {}; } }\n'''
    visible = r'''#include "task.h"
using namespace curriculum;
int main(){ CustodyChain c; auto r=c.inspect({{"intake",{2024,2,28},1},{"lab",{2024,3,1},3},{"archive",{2024,3,4},0}}); return r.status!=CustodyStatus::ok || r.total_days!=5 || r.completed.size()!=2 || !r.completed[0].breached || r.completed[1].breached; }
'''
    hidden = r'''#include "task.h"
using namespace curriculum;
int main(){ CustodyChain c; auto singleton=c.inspect({{"only",{2024,1,1},0}}); auto equal=c.inspect({{"a",{2000,2,29},0},{"b",{2000,2,29},0}}); auto reverse=c.inspect({{"a",{2024,1,2},1},{"b",{2024,1,1},1}}); auto dup=c.inspect({{"a",{2024,1,1},1},{"a",{2024,1,2},1}}); return singleton.total_days!=0 || !singleton.completed.empty() || equal.completed[0].held_days!=0 || equal.completed[0].breached || reverse.status!=CustodyStatus::chronological_reversal || dup.status!=CustodyStatus::duplicate_handler; }
'''
    instructions = """# Instructions

Implement `CustodyChain::inspect`. Each transfer names a unique non-empty handler, has a valid Gregorian acceptance date, and gives that handler's non-negative maximum holding days. Validate fields before chronological relations. Each completed stage runs from one acceptance date to the next; equality is a zero-day stage, reversal is invalid, and a stage breaches only when elapsed days are strictly greater than its limit. The final handler has no completed stage. Preserve transfer order in completed stages and return no partial stages on error.
"""
    return {"header":header,"reference":reference,"starter":starter,"visible":visible,"hidden":hidden,"instructions":instructions}


BUILDERS = {
    "dated-warranty-audit": _warranty,
    "dated-project-burnup": _burnup,
    "dated-library-loan": _loan,
    "dated-experiment-window": _experiment,
    "dated-retention-review": _retention,
    "dated-maintenance-ledger": _maintenance,
    "dated-subscription-proration": _proration,
    "dated-custody-chain": _custody,
}


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(date_difference_curriculum LANGUAGES CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(TASK_SOURCE "${CMAKE_CURRENT_SOURCE_DIR}/task.cpp" CACHE FILEPATH "Implementation to grade")
add_executable(task_visible "${TASK_SOURCE}" task_visible_test.cpp)
add_executable(task_hidden "${TASK_SOURCE}" .meta/task_hidden_test.cpp)
add_executable(task_negative .meta/negative.cpp task_visible_test.cpp)
foreach(target task_visible task_hidden task_negative)
  target_include_directories(${target} PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wpedantic -Werror)
  endif()
endforeach()
enable_testing()
add_test(NAME visible COMMAND task_visible)
add_test(NAME hidden COMMAND task_hidden)
add_test(NAME negative_fixture COMMAND task_negative)
set_tests_properties(negative_fixture PROPERTIES WILL_FAIL TRUE)
'''


def _negative_source(task_id: str, reference: str) -> str:
    mutations = {
        "dated-warranty-audit": (
            "age < policy.coverage_days ? ClaimStatus::covered",
            "age <= policy.coverage_days ? ClaimStatus::covered",
        ),
        "dated-project-burnup": (
            "if (weekday(d)<5 && !closed.count(day)) ++total;",
            "if (weekday(d)>=0 && !closed.count(day)) ++total;",
        ),
        "dated-library-loan": (
            "if(!closed.count(x)) ++overdue;",
            "++overdue;",
        ),
        "dated-experiment-window": (
            "if(l<r)v.push_back({l,r});",
            "if(l>r)v.push_back({l,r});",
        ),
        "dated-retention-review": (
            "if(age>=it->second.retention_days)out.push_back",
            "if(age>it->second.retention_days)out.push_back",
        ),
        "dated-maintenance-ledger": (
            "auto it = state.find(event.asset_id);",
            "auto it = state.empty() ? state.end() : state.begin();",
        ),
        "dated-subscription-proration": (
            "serial(bands[band+1].effective)<=day",
            "serial(bands[band+1].effective)>day",
        ),
        "dated-custody-chain": (
            "days>transfers[i-1].maximum_days",
            "days>=transfers[i-1].maximum_days",
        ),
    }
    old, new = mutations[task_id]
    if reference.count(old) != 1:
        _fail("negative_fixture_drift", f"{task_id}:{old}")
    return reference.replace(old, new, 1)


def _remedy_markdown(spec: TaskSpec) -> str:
    data = BUILDERS[spec.task_id]()
    legacy_id = spec.legacy_id or spec.task_id
    origin = "legacy root" if (LEGACY_OUT / legacy_id).is_dir() else "family-capacity replacement"
    return f"""# Remedy Specification: {spec.task_id}

## Identity

Task `{spec.task_id}`, task-spec revision 3, family `{FAMILY_ID}`, disposition `{spec.disposition}`, source inventory `{LEGACY_FAMILY_ID}:{legacy_id}`, license `repository-authored-clean-room/pass`, generator `src/w8_biayn/integrations/moonlight_date_difference_aider_tasks.py`, benchmark screen `pending`. The immutable source is a {origin}; the supplied family-type mismatch is recorded in `{FAMILY_SPEC}`.

## Objective

Implement the observable domain capability in `{spec.title}` using validated proleptic-Gregorian elapsed-day arithmetic and the task-specific collection, sweep, interval, join, or state-transition rules documented below. A bare date-offset function is outside the contract.

## Public API

The editable order is `{spec.task_id}.h`, `{spec.task_id}.cpp`, in namespace `curriculum`. The complete C++17 declarations are emitted from this owner and bound by `.meta/config.json`. The public header contract is:

```cpp
{data['header'].strip()}
```

## Behavior table

| Operation | Valid/success | Invalid/duplicate/absent/empty | Mutation/order/tie/overflow | Public boundary |
| --- | --- | --- | --- | --- |
| Task API | Applies the task-specific dated policy and returns its typed result. | Invalid Gregorian dates and documented IDs, relations, policies, duplicates, or empty collections return the documented diagnostic without partial output. | Input is caller-owned; result ordering and equality boundaries follow the visible instructions; checked integer conversions are limited to tested year ranges. | Leap-day, same-day, equality, and reversed cases are specified in `.docs/instructions.md`. |

## Implementation invariant

The reference owns the task-specific state needed by its API and derives elapsed dates through leap-aware Gregorian serial conversion. It must not delegate to host clock/calendar APIs, return precomputed cases, flatten every date to the same value, expose a bare `days_between`, or substitute a renamed copy of another root. The private predicate compares all returned fields and ordering against deterministic visible/hidden cases; the task-specific substitute “{NEGATIVE_DESCRIPTIONS[spec.task_id]}” must compile and fail.

## Starter and reference

The header is coherent and complete; the source intentionally returns an empty/default result. `.meta/example.h` reproduces the header and `.meta/example.cpp` independently implements the documented algorithm. Forbidden shortcuts include host time APIs, fixed 365-day years, 30-day months, constant results, and test-specific tables.

## Tests

Visible and private executables cover the public example, leap-century behavior, endpoint equality, ordering, invalid relations, duplicate/empty policy, and task-specific output. The deterministic topic negative is “{NEGATIVE_DESCRIPTIONS[spec.task_id]}”; it changes the substantive task mechanism, compiles under strict flags, and must exit 1 against the visible test. The three coherent family controls are domain/identifier rename, constants-or-policy-only change, and opposite-end selection; each must build and be rejected by the production seven-dimension evaluator.

## Files and metadata

Prompt-visible roles are `.docs/*.md` plus `{spec.task_id}.h` and `{spec.task_id}.cpp`; only the latter pair is editable in that order. Private roles are `.meta/example.h`, `.meta/example.cpp`, `.meta/task_hidden_test.cpp`, `.meta/negative.cpp`, config, provenance, tests metadata, CMake, receipts, screens, and remedies. Example header/source map one-to-one by suffix and order. There is no bundled support asset.

## Build/oracle

C++17, explicit `Unix Makefiles`, strict `-Wall -Wextra -Wpedantic -Werror`, repository-pinned `{SANITY_IMAGE}` Docker sanity (not locked oracle), network `none`. Run fresh normal and ASan/UBSan builds. Each mode must discover three tests, pass reference visible/hidden plus WILL_FAIL negative, and direct execution must observe the negative's exit 1. Receipt binds tree/reference/owner/image/compiler/CMake hashes and commands.

## Family/contamination

Compare all eight emitted roots across every unordered pair using `{NORMALIZER}` and all seven required artifact-derived dimensions. Materiality requires both Jaccard overlap below the dimension-specific threshold and a minimum symmetric feature difference; identifiers, literals, the shared Gregorian helper, and domain nouns are excluded. Compare task IDs and normalized content with all 26 permanent C++ holdout slugs, particularly `clock`, `gigasecond`, and `meetup`. Any failed dimension is `duplicate_family`; any holdout match is `benchmark_content_overlap` and rejection.

## Optional dataset handoff

`not_requested`. No JSONL rows, token/mask evidence, split, export, consumer verification, training, or release claim belongs to this remediation.

## Acceptance

Run focused pytest, owner `--verify-core`, owner host `--verify`, and owner `--docker-sanity`. Require 8 roots (within the user-authorized 8–12 bound), 28 unordered pairs, exactly seven passing decisions per pair, nonempty coherent control mutations rejected by the production evaluator, prompt/role/reference safety, benchmark separation, three equal positive normal/sanitizer tests per root and control, direct negative exit 1, and current-tree receipt binding. Stable failures include `remedy_spec_incomplete`, `hard_rule_root_count`, `hard_rule_evidence_incomplete`, `duplicate_family`, `benchmark_content_overlap`, `prompt_contract_incomplete`, `target_reference_mismatch`, `negative_fixture_not_rejected`, `generator_output_drift`, `grader_mount_hash_mismatch`, and `sanitizer_test_count_mismatch`.
"""


def _write_remedies(out: Path, force: bool) -> None:
    remedy = out / ".state/remedy"
    for spec in TASKS:
        legacy_id = spec.legacy_id or spec.task_id
        markdown = _remedy_markdown(spec)
        record = {
            "schema_version": "aider-task-remedy-v1",
            "task_id": spec.task_id,
            "family_id_before": LEGACY_FAMILY_ID,
            "family_id_after": FAMILY_ID,
            "tree_hash_before": _tree_hash(LEGACY_OUT / legacy_id),
            "legacy_root": str(LEGACY_OUT / legacy_id),
            "generator_path": "src/w8_biayn/integrations/moonlight_date_difference_aider_tasks.py",
            "generator_revision": _generator_revision(),
            "finding_ids": ["DATE-FAMILY-COUNT", "DATE-HARD-RULE", "DATE-ORACLE-REVERIFY", "DATE-TAXONOMY-MISMATCH"],
            "disposition": spec.disposition,
            "benchmark_screen": "pending",
            "license_screen": "pass",
            "remedy_spec_path": f".state/remedy/{spec.task_id}.md",
            "remedy_spec_hash": _sha256(markdown.encode()),
            "selected_prompt": SELECTED_PROMPT,
            "user_inputs": {"FAMILY_NAME": "date-difference", "FAMILY_TYPE": "aider-text-grid-reshaping", "hard_rule_count": "8-12"},
            "primary_core_objective": "achieved",
            "status": "planned",
            "local_status": "pending_execution",
            "prior_evidence_invalidation": ".state/invalidated/hard-rule-fingerprint-overclaim-v1/invalidation.json",
            "prior_overclaim_withdrawn": True,
        }
        _write(remedy / f"{spec.task_id}.md", markdown, force)
        _write(remedy / f"{spec.task_id}.json", json.dumps(record, indent=2, sort_keys=True) + "\n", force)


def build(out: Path = DEFAULT_OUT, force: bool = False) -> tuple[Path, ...]:
    if out.resolve() == LEGACY_OUT.resolve():
        _fail("legacy_root_immutable", str(LEGACY_OUT))
    _write_remedies(out, force)
    roots: list[Path] = []
    for spec in TASKS:
        root = out / spec.task_id
        data = BUILDERS[spec.task_id]()
        config = {"authors": ["w8-biayn"], "blurb": spec.blurb, "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "family_spec": FAMILY_SPEC, "curriculum_task_id": spec.task_id, "origin": "newly-authored in-repository clean-room remediation task", "status": "local task artifact; not admitted SFT data", "version": 3, "family_id": FAMILY_ID, "legacy_family_root": str(LEGACY_OUT), "requested_family_type": "aider-text-grid-reshaping", "taxonomy_mismatch_recorded": True, "benchmark_separation": "Independent domain API, records, endpoint policy, diagnostics, tests, and reference; not derived from an official Aider Polyglot task."}
        files = {".docs/introduction.md": f"# {spec.title}\n\nA newly authored local C++17 diagnostic about domain-specific Gregorian date records.\n", ".docs/instructions.md": data["instructions"], ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": f"[visible]\ndescription = \"public domain API, leap boundaries, and endpoint policy\"\n\n[hidden]\ndescription = \"Gregorian century rules, invalid relations, duplicates, equality boundaries, and deterministic diagnostics\"\n\n[negative]\ndescription = \"{NEGATIVE_DESCRIPTIONS[spec.task_id]}; the substitute must compile and be rejected\"\n", "task.h": data["header"], "task.cpp": data["starter"], ".meta/example.h": data["header"], ".meta/example.cpp": data["reference"], ".meta/negative.cpp": _negative_source(spec.task_id, data["reference"]), "task_visible_test.cpp": data["visible"], ".meta/task_hidden_test.cpp": data["hidden"], "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


CPP_KEYWORDS = {
    "alignas", "alignof", "and", "auto", "bool", "break", "case", "catch",
    "char", "class", "const", "constexpr", "continue", "default", "delete",
    "do", "double", "else", "enum", "explicit", "false", "float", "for",
    "friend", "if", "inline", "int", "long", "namespace", "new", "noexcept",
    "nullptr", "operator", "or", "private", "protected", "public", "return",
    "short", "signed", "sizeof", "static", "struct", "switch", "template",
    "this", "throw", "true", "try", "typedef", "typename", "union", "unsigned",
    "using", "virtual", "void", "volatile", "while",
}


def _normalize_cpp(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " STR ", text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", " STR ", text)
    text = re.sub(r"\b\d+[uUlL]*\b", " NUM ", text)
    text = re.sub(r"\b(?:front|back|begin|end|first|last)\b", " ENDSEL ", text)
    text = re.sub(r"<=|>=|==|!=|<|>", " REL ", text)
    tokens = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|::|&&|\|\||\+\+|--|[-+*/%=&|!?:;,.{}()[\]]", text)
    return " ".join(token if token in CPP_KEYWORDS or token in {"std", "vector", "map", "set", "sort", "pair", "string"} else "ID" for token in tokens)


def _normalize_docs(text: str) -> str:
    text = text.lower()
    text = re.sub(r"`[^`]+`", " api ", text)
    text = re.sub(r"\b\d+\b", " number ", text)
    text = re.sub(r"\b(?:before|after|forward|reverse|reversed|chronological|input|output|first|last|begin|end)\b", " relation ", text)
    words = re.findall(r"[a-z]+", text)
    stop = {
        "the", "a", "an", "and", "or", "to", "of", "in", "for", "is", "are",
        "be", "with", "this", "that", "each", "return", "implement", "equal",
        "warranty", "claim", "claims", "purchase", "project", "milestone", "milestones",
        "holiday", "holidays", "loan", "checkout", "closure", "closures", "fee", "fees",
        "experiment", "observation", "study", "blackout", "blackouts", "retention", "archive",
        "archived", "category", "categories", "record", "records", "maintenance", "service",
        "event", "events", "asset", "assets", "subscription", "rate", "rates", "band", "bands",
        "billing", "custody", "transfer", "transfers", "handler", "handlers", "ledger", "policy",
    }
    return " ".join(word for word in words if word not in stop)


def _fingerprint(text: str) -> str:
    return _sha256(text.encode())


def _ngrams(tokens: Sequence[str], size: int) -> set[str]:
    if len(tokens) < size:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[index:index + size]) for index in range(len(tokens) - size + 1)}


def _counted_ngrams(prefix: str, tokens: Sequence[str], size: int) -> set[str]:
    grams = Counter(
        " ".join(tokens[index:index + size])
        for index in range(max(0, len(tokens) - size + 1))
    )
    if not grams and tokens:
        grams[" ".join(tokens)] = 1
    return {f"{prefix}:{gram}:count={count}" for gram, count in grams.items()}


def _task_reference(reference: str) -> str:
    if DATE_HELPERS not in reference:
        _fail("hard_rule_evidence_incomplete", "shared date helper boundary missing")
    return reference.replace(DATE_HELPERS, "")


def _metric_features(prefix: str, text: str) -> set[str]:
    patterns = {
        "for": r"\bfor\s*\(", "while": r"\bwhile\s*\(", "if": r"\bif\s*\(",
        "sort": r"std::sort", "map": r"std::map", "set": r"std::set", "vector": r"std::vector",
        "find": r"\.find\s*\(", "insert": r"\.insert\s*\(", "emplace": r"\.emplace\s*\(",
        "push": r"push_back", "throw": r"\bthrow\b", "serial": r"\bserial\s*\(",
    }
    return {f"{prefix}:{name}:{len(re.findall(pattern, text))}" for name, pattern in patterns.items()}


def _shape_metric_features(prefix: str, text: str) -> set[str]:
    tokens = {
        "member": ".", "index": "[", "not_equal": "!=", "equal": "==",
        "or": "||", "and": "&&", "aggregate": "{", "call": "(",
        "size": ".size()", "empty": ".empty()", "catch": "catch",
    }
    return {f"{prefix}:{name}:count={text.count(token)}" for name, token in tokens.items()}


def _negative_tokens(text: str) -> list[str]:
    text = re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.S)
    text = re.sub(r'"(?:\\.|[^"\\])*"', " STR ", text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", " STR ", text)
    text = re.sub(r"\b\d+[uUlL]*\b", "NUM", text)
    tokens = re.findall(r"[A-Za-z_][A-Za-z_0-9]*|<=|>=|==|!=|&&|\|\||\+\+|--|[-+*/%=&|!?:;,.{}()[\]<>]", text)
    preserved = CPP_KEYWORDS | {"std", "vector", "map", "set", "sort", "find", "insert", "emplace", "push_back", "count", "size", "empty", "begin", "end", "front", "back", "NUM", "STR"}
    return [token if token in preserved or not re.match(r"[A-Za-z_]", token) else "ID" for token in tokens]


def _negative_delta_features(reference: str, negative: str) -> set[str]:
    reference_counts = Counter(_negative_tokens(_task_reference(reference)))
    negative_counts = Counter(_negative_tokens(_task_reference(negative)))
    features: set[str] = set()
    for token, count in sorted((reference_counts - negative_counts).items()):
        features.add(f"removed:{token}:{count}")
    for token, count in sorted((negative_counts - reference_counts).items()):
        features.add(f"added:{token}:{count}")
    if not features:
        _fail("hard_rule_evidence_incomplete", "negative fixture has no normalized semantic delta")
    return features


def _artifact_features(root: Path) -> dict[str, dict[str, object]]:
    config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
    header_name = next(name for name in config["files"]["solution"] if name.endswith(".h"))
    header = (root / header_name).read_text(encoding="utf-8")
    reference = (root / ".meta/example.cpp").read_text(encoding="utf-8")
    instructions = (root / ".docs/instructions.md").read_text(encoding="utf-8")
    visible = (root / "task_visible_test.cpp").read_text(encoding="utf-8")
    hidden = (root / ".meta/task_hidden_test.cpp").read_text(encoding="utf-8")
    negative = (root / ".meta/negative.cpp").read_text(encoding="utf-8")
    task_reference = _task_reference(reference)
    ref_tokens = _normalize_cpp(task_reference).split()
    api_tokens = _normalize_cpp(header).split()
    test_tokens = _normalize_cpp(visible + "\n" + hidden).split()
    doc_tokens = _normalize_docs(instructions).split()
    control_tokens = [token for token in ref_tokens if token in {"if", "else", "for", "while", "continue", "throw", "return", "=", "++", "--", "+", "-", "!", "&&", "||", "REL"}]
    material: dict[str, set[str]] = {
        "public_api": _counted_ngrams("api-shape", api_tokens, 4) | _metric_features("api", header),
        "owned_state_or_algorithm": _counted_ngrams("algorithm-shape", ref_tokens, 4) | _metric_features("algorithm", task_reference),
        "mutation_selection_rules": _counted_ngrams("mutation-shape", control_tokens, 3) | _metric_features("mutation", task_reference),
        "invalid_boundary_behavior": _counted_ngrams("boundary-rule", doc_tokens, 2) | {f"boundary:{token}" for token in doc_tokens if token in {"invalid", "duplicate", "unique", "empty", "positive", "negative", "included", "excluded", "strictly", "half", "open", "closed", "equality", "threshold", "partial", "ordering", "sorted"}},
        "reference_control_flow": _counted_ngrams("flow-shape", ref_tokens, 5) | _metric_features("flow", task_reference),
        "deterministic_oracle": _counted_ngrams("oracle-shape", test_tokens, 4) | _metric_features("oracle", visible + "\n" + hidden) | _shape_metric_features("oracle-structure", visible + "\n" + hidden),
        "topic_negative_fixture": _negative_delta_features(reference, negative),
    }
    result: dict[str, dict[str, object]] = {}
    for dimension, features in material.items():
        if not features:
            _fail("hard_rule_evidence_incomplete", f"{root.name}:{dimension}")
        serialized = "\n".join(sorted(features))
        result[dimension] = {
            "fingerprint": _fingerprint(serialized),
            "feature_count": len(features),
            "features": sorted(features),
            "source": "actual emitted docs/API/reference/visible-private-tests/negative delta; common date helper, identifiers, literals, and domain nouns removed",
        }
    return result


def _hard_rule_pair_result(left: Path, right: Path) -> dict[str, object]:
    left_features = _artifact_features(left)
    right_features = _artifact_features(right)
    decisions: dict[str, dict[str, object]] = {}
    for dimension in HARD_RULE_DIMENSIONS:
        left_set = set(left_features[dimension]["features"])
        right_set = set(right_features[dimension]["features"])
        union = left_set | right_set
        intersection = left_set & right_set
        overlap = len(intersection) / max(1, len(union))
        symmetric_difference = left_set ^ right_set
        threshold = HARD_RULE_THRESHOLDS[dimension]
        minimum_difference = HARD_RULE_MIN_SYMMETRIC_DIFFERENCE[dimension]
        materially_different = overlap < threshold and len(symmetric_difference) >= minimum_difference
        decisions[dimension] = {
            "left": left_features[dimension]["fingerprint"],
            "right": right_features[dimension]["fingerprint"],
            "left_feature_count": len(left_set),
            "right_feature_count": len(right_set),
            "intersection_count": len(intersection),
            "union_count": len(union),
            "jaccard_overlap": overlap,
            "threshold": threshold,
            "symmetric_difference_count": len(symmetric_difference),
            "minimum_symmetric_difference": minimum_difference,
            "left_only_witnesses": sorted(left_set - right_set)[:8],
            "right_only_witnesses": sorted(right_set - left_set)[:8],
            "materially_different": materially_different,
        }
    failed = [dimension for dimension, decision in decisions.items() if not decision["materially_different"]]
    return {
        "left": left.name,
        "right": right.name,
        "dimensions": decisions,
        "failed_dimensions": failed,
        "pass": not failed,
        "failure": None if not failed else "duplicate_family",
    }


def _role_failure(root: Path, files: dict[str, object]) -> str | None:
    solutions = files.get("solution")
    if not isinstance(solutions, list) or len(solutions) != 2:
        return "target_reference_mismatch"
    header, source = solutions
    if not isinstance(header, str) or not isinstance(source, str) or not header.endswith(".h") or source != header[:-2] + ".cpp":
        return "target_reference_mismatch"
    if root.name in {spec.task_id for spec in TASKS} and solutions != [f"{root.name}.h", f"{root.name}.cpp"]:
        return "target_reference_mismatch"
    expected = {
        "solution": solutions,
        "test": ["task_visible_test.cpp", ".meta/task_hidden_test.cpp"],
        "example": [".meta/example.h", ".meta/example.cpp"],
    }
    if files != expected:
        return "target_reference_mismatch"
    for role, paths in files.items():
        if not isinstance(paths, list):
            return "unsafe_path"
        for relative in paths:
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts or not (root / path).is_file():
                return "unsafe_path"
            if role == "solution" and (relative.startswith(".meta/") or relative.startswith(".docs/") or relative == "CMakeLists.txt" or "test" in relative):
                return "unsafe_path"
    return None


def _control_paths(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file() and path.suffix in {".h", ".cpp", ".md", ".json", ".toml", ".txt"})


def _replace_all(root: Path, replacements: Sequence[tuple[str, str]]) -> list[str]:
    changed: list[str] = []
    for path in _control_paths(root):
        text = path.read_text(encoding="utf-8")
        updated = text
        for old, new in replacements:
            updated = updated.replace(old, new)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(path.relative_to(root).as_posix())
    return changed


def _make_adversarial_clone(source: Path, variant: str, parent: Path) -> tuple[Path, dict[str, object]]:
    if variant not in ADVERSARIAL_CONTROLS:
        _fail("unknown_adversarial_control", variant)
    clone = parent / variant
    if clone.exists():
        shutil.rmtree(clone)
    shutil.copytree(source, clone)
    if variant == "domain-identifier-renamed":
        changed = _replace_all(clone, (("Warranty", "Coverage"), ("Claim", "Ticket")))
    elif variant == "constants-or-policy-only":
        changed = _replace_all(clone, (("age < policy.coverage_days", "age <= policy.coverage_days"), ("less than `coverage_days`", "less than or equal to `coverage_days`"), ("a.audit({3}", "a.audit({2}")))
        negative_path = clone / ".meta/negative.cpp"
        negative = negative_path.read_text(encoding="utf-8")
        negative_updated = negative.replace(
            "age <= policy.coverage_days ? ClaimStatus::covered",
            "age < policy.coverage_days ? ClaimStatus::covered",
            1,
        )
        if negative_updated == negative:
            _fail("hard_rule_control_noop", f"{variant}:negative")
        negative_path.write_text(negative_updated, encoding="utf-8")
        if ".meta/negative.cpp" not in changed:
            changed.append(".meta/negative.cpp")
    else:
        changed = _replace_all(clone, (("serial(claim.claimed) - serial(claim.purchased)", "serial(claim.purchased) - serial(claim.claimed)"), ("r[2].status!=ClaimStatus::before_purchase", "r[2].status!=ClaimStatus::expired"), ("before_purchase", "after_purchase"), ("claim before purchase", "claim after purchase"), ("valid claim before purchase", "valid claim after purchase"), ("r[1].status!=ClaimStatus::covered || r[2].status!=ClaimStatus::expired", "r[1].status!=ClaimStatus::after_purchase || r[2].status!=ClaimStatus::after_purchase")))
        reference = (clone / ".meta/example.cpp").read_text(encoding="utf-8")
        negative = reference.replace(
            "if (age < 0)",
            "if (age > 0)",
            1,
        )
        if negative == reference:
            _fail("hard_rule_control_noop", f"{variant}:negative")
        (clone / ".meta/negative.cpp").write_text(negative, encoding="utf-8")
        if ".meta/negative.cpp" not in changed:
            changed.append(".meta/negative.cpp")
    if not changed:
        _fail("hard_rule_control_noop", variant)
    result = _hard_rule_pair_result(source, clone)
    if result["failure"] != "duplicate_family" or not result["failed_dimensions"]:
        _fail("hard_rule_control_not_rejected", variant)
    return clone, {"changed_files": changed, "screen": result, "tree_hash": _tree_hash(clone)}


def _benchmark_tokens(root: Path) -> set[str]:
    text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in sorted(root.rglob("*")) if path.is_file() and path.suffix in {".md", ".h", ".cpp"})
    normalized = _normalize_docs(text) + " " + _normalize_cpp(text)
    return set(normalized.split())


def _benchmark_screen(out: Path) -> dict[str, object]:
    upstream = Path(".cache/upstreams/aider-polyglot/cpp/exercises/practice")
    comparisons: list[dict[str, object]] = []
    inventory: list[str] = []
    if not upstream.is_dir():
        return {"status": "not_completed", "reason": "bound upstream checkout unavailable", "inventory": [], "comparisons": []}
    holdouts = sorted(path for path in upstream.iterdir() if path.is_dir() and path.name in BENCHMARK_SLUGS)
    inventory = [path.name for path in holdouts]
    if set(inventory) != set(BENCHMARK_SLUGS):
        _fail("benchmark_inventory_incomplete", f"expected 26, found {len(inventory)}")
    for spec in TASKS:
        root = out / spec.task_id
        candidate = _benchmark_tokens(root)
        for holdout in holdouts:
            other = _benchmark_tokens(holdout)
            overlap = len(candidate & other) / max(1, len(candidate | other))
            comparisons.append({"candidate": spec.task_id, "holdout": holdout.name, "jaccard": overlap, "pass": overlap < 0.85})
    if any(not item["pass"] for item in comparisons):
        _fail("benchmark_content_overlap", "normalized semantic threshold")
    return {"status": "pass", "normalizer": NORMALIZER, "inventory": inventory, "comparisons": comparisons}


def _verify_remedies(out: Path) -> None:
    remedy = out / ".state/remedy"
    expected = {spec.task_id for spec in TASKS}
    if {path.stem for path in remedy.glob("*.json")} != expected:
        _fail("remedy_spec_incomplete", "one record per final root")
    for spec in TASKS:
        record_path = remedy / f"{spec.task_id}.json"
        markdown = remedy / f"{spec.task_id}.md"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        if record.get("disposition") != spec.disposition:
            _fail("remedy_disposition_conflict", spec.task_id)
        if record.get("remedy_spec_hash") != _sha256(markdown.read_bytes()):
            _fail("remedy_spec_incomplete", f"stale hash: {spec.task_id}")


def _update_records(out: Path, *, status: str, screen: dict[str, object], receipt: str | None = None) -> None:
    for spec in TASKS:
        path = out / ".state/remedy" / f"{spec.task_id}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record.update({
            "generator_revision": _generator_revision(),
            "tree_hash_after": _tree_hash(out / spec.task_id),
            "changed_owner_paths": [CURRICULUM, FAMILY_SPEC, "src/w8_biayn/integrations/moonlight_date_difference_aider_tasks.py", "tests/test_moonlight_date_difference_aider_tasks.py", "examples/slime/moonlight_cpp_perf/prepare_date_difference_aider_tasks.sh"],
            "benchmark_screen": screen["benchmark"]["status"],
            "family_screen": screen["hard_rule"]["status"],
            "prompt_boundary": "pass",
            "status": "verified" if status == "local_family_verified" else "implemented",
            "local_status": status,
            "docker_receipt": receipt,
            "invalidated_prior_claim": "the first eight-root local_family_verified claim was preserved under .state/invalidated/hard-rule-fingerprint-overclaim-v1 and withdrawn because fingerprint inequality, circular focused assertions, and a shared generic negative did not prove the skill's material-diversity rule",
        })
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def invalidate_hard_rule_evidence(out: Path) -> None:
    """Preserve and invalidate the fingerprint-inequality hard-rule overclaim."""
    state = out / ".state"
    destination = state / "invalidated/hard-rule-fingerprint-overclaim-v1"
    destination.mkdir(parents=True, exist_ok=True)
    preserved: dict[str, str] = {}
    for name in ("family-screen.json", "docker-sanity.json", "audit.json"):
        source = state / name
        if source.is_file():
            data = source.read_bytes()
            preserved[name] = _sha256(data)
            _write(destination / name, data.decode("utf-8"), True)
            source.unlink()
    invalidation = {
        "schema_version": "date-difference-evidence-invalidation-v1",
        "status": "invalidated",
        "reason": "normalized fingerprint inequality did not prove material seven-dimension diversity; focused assertions reused the production feature helper; negative fixtures were not task-specific",
        "preserved_evidence": preserved,
        "replacement_gate": "regenerate eight roots with semantic feature-set thresholds, eight task-specific executed negatives, independent focused assertions, coherent controls, and fresh exact-tree Docker evidence",
    }
    _write(destination / "invalidation.json", json.dumps(invalidation, indent=2, sort_keys=True) + "\n", True)
    remedy = state / "remedy"
    for record_path in remedy.glob("*.json"):
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["status"] = "planned"
        record["local_status"] = "pending_execution"
        record["hard_rule_status"] = "invalidated"
        record["invalidated_evidence"] = str(destination / "invalidation.json")
        record["invalidated_reason"] = invalidation["reason"]
        record.pop("docker_receipt", None)
        record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_core(out: Path) -> dict[str, object]:
    _verify_remedies(out)
    roots = sorted(path for path in out.iterdir() if path.is_dir() and path.name != ".state")
    if len(roots) < 8 or len(roots) > 12 or {path.name for path in roots} != {spec.task_id for spec in TASKS}:
        _fail("hard_rule_root_count", f"expected exact owner inventory of 8; found {[path.name for path in roots]}")
    task_evidence: dict[str, object] = {}
    for spec in TASKS:
        root = out / spec.task_id
        config = json.loads((root / ".meta/config.json").read_text(encoding="utf-8"))
        role_failure = _role_failure(root, config.get("files", {}))
        if role_failure:
            _fail(role_failure, spec.task_id)
        if set(BENCHMARK_SLUGS) & set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)+", spec.task_id)):
            _fail("benchmark_id_overlap", spec.task_id)
        task_evidence[spec.task_id] = {"tree_hash": _tree_hash(root), "reference_hash": _reference_hash(root), "features": _artifact_features(root), "prompt_boundary": "pass", "primary_core_objective": "achieved"}
    pairs: list[dict[str, object]] = []
    for index, left in enumerate(roots):
        for right in roots[index + 1:]:
            decision = _hard_rule_pair_result(left, right)
            if not decision["pass"]:
                _fail("duplicate_family", f"{left.name}:{right.name}:{decision['failed_dimensions']}")
            pairs.append(decision)
    if len(pairs) != 28:
        _fail("hard_rule_pair_count", str(len(pairs)))
    observed = {
        dimension: {
            "maximum_jaccard_overlap": max(pair["dimensions"][dimension]["jaccard_overlap"] for pair in pairs),
            "minimum_symmetric_difference": min(pair["dimensions"][dimension]["symmetric_difference_count"] for pair in pairs),
        }
        for dimension in HARD_RULE_DIMENSIONS
    }
    exemplar = out / "dated-warranty-audit"
    controls: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="date-difference-controls-") as temporary:
        for variant in ADVERSARIAL_CONTROLS:
            _, controls[variant] = _make_adversarial_clone(exemplar, variant, Path(temporary))
    benchmark = _benchmark_screen(out)
    if benchmark["status"] != "pass":
        _fail("benchmark_content_screen_not_completed", str(benchmark.get("reason")))
    screen = {
        "schema_version": "date-difference-family-screen-v3",
        "status": "pass",
        "normalizer": NORMALIZER,
        "root_count": len(roots),
        "hard_rule": {
            "status": "pass",
            "dimensions": list(HARD_RULE_DIMENSIONS),
            "thresholds": HARD_RULE_THRESHOLDS,
            "minimum_symmetric_differences": HARD_RULE_MIN_SYMMETRIC_DIFFERENCE,
            "observed_extrema": observed,
            "pair_count": len(pairs),
            "expected_pair_count": 28,
            "pairs": pairs,
            "controls": controls,
        },
        "benchmark": benchmark,
        "tasks": task_evidence,
    }
    _write(out / ".state/family-screen.json", json.dumps(screen, indent=2, sort_keys=True) + "\n", True)
    _update_records(out, status="pending_execution", screen=screen)
    return screen


def verify(out: Path) -> dict[str, object]:
    screen = verify_core(out)
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        raise RuntimeError("verification requires cmake and c++")
    results: dict[str, object] = {}
    for spec in TASKS:
        root = out / spec.task_id
        modes: dict[str, object] = {}
        with tempfile.TemporaryDirectory(prefix="date-difference-curriculum-") as temporary:
            copied = Path(temporary) / root.name
            shutil.copytree(root, copied)
            reference = copied / ".meta" / "example.cpp"
            for name, flags in (("normal", []), ("asan_ubsan", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined -fno-omit-frame-pointer", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), "-G", "Unix Makefiles", f"-DTASK_SOURCE={reference}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                discovery = subprocess.run(["ctest", "--test-dir", str(build_dir), "-N"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout
                match = re.search(r"Total Tests:\s*(\d+)", discovery)
                if not match or int(match.group(1)) != 3:
                    _fail("zero_tests" if not match else "sanitizer_test_count_mismatch", spec.task_id)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                negative = subprocess.run([str(build_dir / "task_negative")], check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if negative.returncode != 1:
                    _fail("negative_fixture_not_rejected", f"{spec.task_id}:{name}:{negative.returncode}")
                modes[name] = {"tests": 3, "negative_exit": 1}
        results[spec.task_id] = {"tree_hash": _tree_hash(root), "reference_hash": _reference_hash(root), **modes}
    receipt = {"schema_version": "date-difference-host-oracle-v3", "status": "pass", "classification": "host_iteration_only", "generator_revision": _generator_revision(), "tasks": results}
    _write(out / ".state/host-oracle.json", json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    _update_records(out, status="pending_execution", screen=screen)
    return receipt


def _archive(out: Path, target: Path, controls: dict[str, Path]) -> str:
    with tarfile.open(target, "w") as archive:
        entries = [("family", out / spec.task_id, spec.task_id) for spec in TASKS]
        entries.extend(("controls", root, name) for name, root in sorted(controls.items()))
        for section, root, name in entries:
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                info = archive.gettarinfo(str(path), arcname=f"{section}/{name}/{path.relative_to(root).as_posix()}")
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mtime = 0
                with path.open("rb") as stream:
                    archive.addfile(info, stream)
    return _sha256(target.read_bytes())


def _accept_docker_receipt(out: Path, receipt: dict[str, object]) -> dict[str, object]:
    if receipt.get("schema_version") != "date-difference-docker-sanity-v3" or receipt.get("status") != "pass" or receipt.get("network") != "none" or receipt.get("image") != SANITY_IMAGE or receipt.get("generator_revision") != _generator_revision():
        _fail("docker_result_identity_mismatch", "receipt header")
    tasks = receipt.get("tasks")
    if not isinstance(tasks, dict) or set(tasks) != {spec.task_id for spec in TASKS}:
        _fail("docker_sanity_incomplete", "task inventory")
    for spec in TASKS:
        item = tasks[spec.task_id]
        live_hash = _tree_hash(out / spec.task_id)
        if item.get("tree_hash") != live_hash or item.get("mounted_tree_hash") != live_hash:
            _fail("grader_mount_hash_mismatch", spec.task_id)
        if item.get("reference_hash") != _reference_hash(out / spec.task_id):
            _fail("docker_result_identity_mismatch", f"reference:{spec.task_id}")
        if item.get("normal") != 3 or item.get("asan_ubsan") != 3:
            _fail("sanitizer_test_count_mismatch", spec.task_id)
        if item.get("negative_normal") != 1 or item.get("negative_asan_ubsan") != 1:
            _fail("negative_fixture_not_rejected", spec.task_id)
    controls = receipt.get("hard_rule_controls")
    if not isinstance(controls, dict) or set(controls) != set(ADVERSARIAL_CONTROLS):
        _fail("docker_sanity_incomplete", "control inventory")
    with tempfile.TemporaryDirectory(prefix="date-difference-accept-controls-") as temporary:
        for variant in ADVERSARIAL_CONTROLS:
            clone, _ = _make_adversarial_clone(out / "dated-warranty-audit", variant, Path(temporary))
            item = controls[variant]
            if item.get("normal") != 3 or item.get("asan_ubsan") != 3 or item.get("negative_normal") != 1 or item.get("negative_asan_ubsan") != 1:
                _fail("sanitizer_test_count_mismatch", f"control:{variant}")
            if item.get("tree_hash") != _tree_hash(clone) or item.get("mounted_tree_hash") != _tree_hash(clone):
                _fail("grader_mount_hash_mismatch", f"control:{variant}")
    hard_rule_binding = receipt.get("hard_rule_binding")
    if hard_rule_binding != {
        "normalizer": NORMALIZER,
        "root_count": 8,
        "pair_count": 28,
        "dimensions": list(HARD_RULE_DIMENSIONS),
        "thresholds": HARD_RULE_THRESHOLDS,
        "minimum_symmetric_differences": HARD_RULE_MIN_SYMMETRIC_DIFFERENCE,
        "result": "pass",
    }:
        _fail("docker_result_identity_mismatch", "hard-rule binding")
    serialized = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    _write(out / ".state/docker-sanity.json", serialized, True)
    screen = verify_core(out)
    _update_records(out, status="local_family_verified", screen=screen, receipt=".state/docker-sanity.json")
    audit = {
        "schema_version": "date-difference-remedy-audit-v3",
        "status": "local_family_verified",
        "primary_core_objective": "achieved",
        "legacy_root_preserved": str(LEGACY_OUT),
        "taxonomy_mismatch": "supplied aider-text-grid-reshaping type did not contain the legacy family; source audit used aider-dates-and-clocks and the fresh destination honors the supplied type",
        "root_count": 8,
        "pair_count": 28,
        "hard_rule_dimensions": list(HARD_RULE_DIMENSIONS),
        "hard_rule_thresholds": HARD_RULE_THRESHOLDS,
        "hard_rule_minimum_symmetric_differences": HARD_RULE_MIN_SYMMETRIC_DIFFERENCE,
        "controls": list(ADVERSARIAL_CONTROLS),
        "task_specific_negatives": NEGATIVE_DESCRIPTIONS,
        "benchmark_comparisons": 208,
        "docker_receipt": ".state/docker-sanity.json",
        "invalidated_prior_claim": ".state/invalidated/hard-rule-fingerprint-overclaim-v1/invalidation.json",
        "generator_revision": _generator_revision(),
        "tree_hashes": {spec.task_id: _tree_hash(out / spec.task_id) for spec in TASKS},
        "findings": {
            "DATE-FAMILY-COUNT": "resolved and reverified: legacy 5-root family replaced/repaired by 8 counted roots",
            "DATE-HARD-RULE": "resolved and reverified after withdrawing v2: every one of 28 pairs passed per-dimension overlap plus symmetric-difference materiality gates, with independent emitted semantic witnesses",
            "DATE-ORACLE-REVERIFY": "resolved and reverified: exact network-disabled Docker normal and fresh ASan/UBSan evidence",
            "DATE-TAXONOMY-MISMATCH": "resolved by preserving the discovered legacy path and recording the supplied destination type",
        },
        "dataset_handoff": "not_requested",
    }
    _write(out / ".state/audit.json", json.dumps(audit, indent=2, sort_keys=True) + "\n", True)
    return receipt


def docker_sanity(out: Path, *, result_out: Path | None = None) -> dict[str, object]:
    core_screen = verify_core(out)
    if shutil.which("docker") is None:
        _fail("docker_sanity_not_completed", "docker executable unavailable")
    with tempfile.TemporaryDirectory(prefix="date-difference-docker-") as temporary:
        temp = Path(temporary)
        controls = {variant: _make_adversarial_clone(out / "dated-warranty-audit", variant, temp / "control-source")[0] for variant in ADVERSARIAL_CONTROLS}
        control_hashes = {name: _tree_hash(root) for name, root in controls.items()}
        archive = temp / "family.tar"
        archive_hash = _archive(out, archive, controls)
        inspect = subprocess.run(["docker", "image", "inspect", SANITY_IMAGE, "--format", "{{.Id}}"], check=False, capture_output=True, text=True)
        if inspect.returncode != 0:
            _fail("docker_sanity_not_completed", inspect.stderr.strip())
        script = r'''set -eu
mkdir -p /tmp/date-family
tar -xf /input/family.tar -C /tmp/date-family
compiler=$(command -v c++)
echo "W8TOOL compiler_path $compiler"
echo "W8TOOL compiler_hash sha256:$(sha256sum "$compiler" | sed 's/ .*//')"
echo "W8TOOL compiler_version $(c++ --version | head -1)"
echo "W8TOOL cmake_version $(cmake --version | head -1)"
for section in family controls; do
  for root in /tmp/date-family/$section/*; do
    name=${root##*/}
    mounted_hash=$(python3 -c 'import hashlib,pathlib,sys
r=pathlib.Path(sys.argv[1]); d=hashlib.sha256()
for p in sorted(x for x in r.rglob("*") if x.is_file()):
 q=p.relative_to(r).as_posix().encode(); b=p.read_bytes(); d.update(len(q).to_bytes(8,"big")); d.update(q); d.update(len(b).to_bytes(8,"big")); d.update(b)
print("sha256:"+d.hexdigest())' "$root")
    echo "W8HASH $section $name $mounted_hash"
    for mode in normal asan_ubsan; do
      flags=
      if [ "$mode" = asan_ubsan ]; then flags='-fsanitize=address,undefined -fno-omit-frame-pointer'; fi
      build=/tmp/build-$section-$name-$mode
      cmake -S "$root" -B "$build" -G 'Unix Makefiles' -DTASK_SOURCE="$root/.meta/example.cpp" -DCMAKE_CXX_FLAGS="$flags" -DCMAKE_EXE_LINKER_FLAGS="$flags" >/dev/null
      cmake --build "$build" --parallel 2 >/dev/null
      count=$(ctest --test-dir "$build" -N | sed -n 's/.*Total Tests: *//p')
      test "$count" = 3
      ctest --test-dir "$build" --output-on-failure >/dev/null
      set +e
      "$build/task_negative" >/dev/null 2>&1
      negative=$?
      set -e
      test "$negative" = 1
      echo "W8COUNT $section $name $mode $count $negative"
    done
  done
done'''
        run = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{archive}:/input/family.tar:ro", SANITY_IMAGE, "bash", "-lc", script], check=False, capture_output=True, text=True)
        if run.returncode != 0:
            _fail("docker_sanity_failed", (run.stdout + "\n" + run.stderr)[-12000:])
    parsed: dict[tuple[str, str], dict[str, int]] = {}
    for section, name, mode, count, negative in re.findall(r"^W8COUNT (\S+) (\S+) (\S+) (\d+) (\d+)$", run.stdout, re.M):
        parsed.setdefault((section, name), {})[mode] = int(count)
        parsed[(section, name)][f"negative_{mode}"] = int(negative)
    mounted = {(section, name): digest for section, name, digest in re.findall(r"^W8HASH (\S+) (\S+) (sha256:[0-9a-f]{64})$", run.stdout, re.M)}
    expected_tasks = {spec.task_id for spec in TASKS}
    if {name for section, name in parsed if section == "family"} != expected_tasks:
        _fail("docker_sanity_incomplete", "task results")
    for key, item in parsed.items():
        if item != {"normal": 3, "negative_normal": 1, "asan_ubsan": 3, "negative_asan_ubsan": 1}:
            _fail("sanitizer_test_count_mismatch", str(key))
    toolchain = dict(re.findall(r"^W8TOOL (\S+) (.+)$", run.stdout, re.M))
    receipt: dict[str, object] = {
        "schema_version": "date-difference-docker-sanity-v3",
        "status": "pass",
        "evidence_class": "docker_sanity",
        "locked_oracle": False,
        "network": "none",
        "image": SANITY_IMAGE,
        "image_id": inspect.stdout.strip(),
        "archive_hash": archive_hash,
        "generator_revision": _generator_revision(),
        "toolchain": toolchain,
        "commands": ["explicit Unix Makefiles normal build", "ctest normal", "direct negative exit 1", "fresh ASan/UBSan build", "ctest ASan/UBSan", "direct sanitizer negative exit 1"],
        "hard_rule_binding": {
            "normalizer": NORMALIZER,
            "root_count": core_screen["root_count"],
            "pair_count": core_screen["hard_rule"]["pair_count"],
            "dimensions": core_screen["hard_rule"]["dimensions"],
            "thresholds": core_screen["hard_rule"]["thresholds"],
            "minimum_symmetric_differences": core_screen["hard_rule"]["minimum_symmetric_differences"],
            "result": core_screen["hard_rule"]["status"],
        },
        "tasks": {spec.task_id: {**parsed[("family", spec.task_id)], "tree_hash": _tree_hash(out / spec.task_id), "mounted_tree_hash": mounted[("family", spec.task_id)], "reference_hash": _reference_hash(out / spec.task_id)} for spec in TASKS},
        "hard_rule_controls": {variant: {**parsed[("controls", variant)], "tree_hash": control_hashes[variant], "mounted_tree_hash": mounted[("controls", variant)], "classification": "coherent buildable clone rejected by exact production evaluator"} for variant in ADVERSARIAL_CONTROLS},
    }
    if result_out is not None:
        _write(result_out, json.dumps(receipt, indent=2, sort_keys=True) + "\n", True)
    return _accept_docker_receipt(out, receipt)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format date-difference curriculum tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify-core", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--docker-sanity", action="store_true")
    parser.add_argument("--docker-result-out", type=Path)
    parser.add_argument("--invalidate-hard-rule", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.invalidate_hard_rule:
        invalidate_hard_rule_evidence(args.out)
    if args.verify_core:
        verify_core(args.out)
    if args.verify:
        verify(args.out)
    if args.docker_sanity:
        docker_sanity(args.out, result_out=args.docker_result_out)
    print(f"Wrote {len(roots)} date-difference curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
