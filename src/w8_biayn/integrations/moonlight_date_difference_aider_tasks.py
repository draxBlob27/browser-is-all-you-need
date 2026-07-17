"""Materialize the newly authored local date-difference Aider curriculum."""
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

DEFAULT_OUT = Path(".w8-biayn/data/aider-tasks/aider-dates-and-clocks/date-difference")
CURRICULUM = "docs/aider-synthetic/aider-synthetic-clock-tasks/GLM47_FLASH_AIDER_POLYGLOT_CPP_DATE_DIFFERENCE_CURRICULUM.md"


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    title: str
    blurb: str


TASKS = (
    TaskSpec("dated-warranty-audit", "Warranty claim audit", "Audit warranty claims against inclusive coverage policies."),
    TaskSpec("dated-project-burnup", "Project burn-up report", "Count scheduled workdays between project milestones."),
    TaskSpec("dated-library-loan", "Library loan reconciliation", "Reconcile loan dates, closures, and tiered overdue fees."),
    TaskSpec("dated-experiment-window", "Experiment observation window", "Subtract blackout spans from a study observation window."),
    TaskSpec("dated-retention-review", "Records retention review", "Review archived records using category retention policies."),
)


def _write(path: Path, content: str, force: bool) -> None:
    if path.exists() and path.read_text(encoding="utf-8") != content and not force:
        raise FileExistsError(f"{path} differs; pass --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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
    if (!seen.insert(claim.id).second || claim.id.empty()) {{ out.push_back({{claim.id, ClaimStatus::duplicate_id}}); continue; }}
    if (!valid(claim.purchased) || !valid(claim.claimed)) {{ out.push_back({{claim.id, ClaimStatus::invalid_date}}); continue; }}
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
  if (start.id.empty() || end.id.empty() || start.id == end.id) return {{BurnupStatus::duplicate_milestone}};
  if (!valid(start.date) || !valid(end.date)) return {{BurnupStatus::invalid_date}};
  if (serial(end.date) < serial(start.date)) return {{BurnupStatus::reversed}};
  std::set<long long> closed; for (Date d : holidays) {{ if (!valid(d)) return {{BurnupStatus::invalid_date}}; if (!closed.insert(serial(d)).second) return {{BurnupStatus::duplicate_holiday}}; }}
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
 if(!valid(loan.checkout)||!valid(loan.due)||!valid(loan.returned)) return {{LoanStatus::invalid_date}};
 if(serial(loan.due)<serial(loan.checkout)) return {{LoanStatus::due_before_checkout}};
 if(serial(loan.returned)<serial(loan.checkout)) return {{LoanStatus::return_before_checkout}};
 std::set<long long> closed; for(Date d:closures) {{ if(!valid(d)) return {{LoanStatus::invalid_date}};
 if(!closed.insert(serial(d)).second) return {{LoanStatus::duplicate_closure}}; }} int overdue=0; for(long long x=serial(loan.due)+1;x<=serial(loan.returned);++x) if(!closed.count(x)) ++overdue;
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
 if(!valid(today)) {{for(auto r:records)out.push_back({{r.id,ReviewStatus::invalid_date}});return out;}} std::map<std::string,RetentionPolicy> by; for(auto p:policies) {{if(p.category.empty()||p.retention_days<=0||p.review_lead_days<0){{for(auto r:records)out.push_back({{r.id,ReviewStatus::invalid_policy}});return out;}}if(!by.emplace(p.category,p).second){{for(auto r:records)out.push_back({{r.id,ReviewStatus::duplicate_category}});return out;}}}} for(auto r:records) {{if(!valid(r.archived)){{out.push_back({{r.id,ReviewStatus::invalid_date}});continue;}}auto it=by.find(r.category);if(it==by.end()){{out.push_back({{r.id,ReviewStatus::unknown_category}});continue;}}long long age=serial(today)-serial(r.archived);int remain=it->second.retention_days-static_cast<int>(age);if(age>=it->second.retention_days)out.push_back({{r.id,ReviewStatus::expired,remain}});else if(age>=it->second.retention_days-it->second.review_lead_days)out.push_back({{r.id,ReviewStatus::review_due,remain}});else out.push_back({{r.id,ReviewStatus::active,remain}});}}return out; }}
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


BUILDERS = {"dated-warranty-audit": _warranty, "dated-project-burnup": _burnup, "dated-library-loan": _loan, "dated-experiment-window": _experiment, "dated-retention-review": _retention}


def _cmake() -> str:
    return '''cmake_minimum_required(VERSION 3.16)
project(date_difference_curriculum LANGUAGES CXX)
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
    for spec in TASKS:
        root = out / spec.task_id
        data = BUILDERS[spec.task_id]()
        config = {"authors": ["w8-biayn"], "blurb": spec.blurb, "files": {"solution": ["task.h", "task.cpp"], "test": ["task_visible_test.cpp"], "example": [".meta/example.h", ".meta/example.cpp"]}}
        provenance = {"curriculum_document": CURRICULUM, "curriculum_task_id": spec.task_id, "origin": "newly-authored in-repository diagnostic task", "status": "local task artifact; not admitted SFT data", "version": 1, "benchmark_separation": "Independent domain API, records, endpoint policy, diagnostics, tests, and reference; not derived from an official Aider Polyglot task."}
        files = {".docs/introduction.md": f"# {spec.title}\n\nA newly authored local C++17 diagnostic about domain-specific Gregorian date records.\n", ".docs/instructions.md": data["instructions"], ".meta/config.json": json.dumps(config, indent=2, sort_keys=True) + "\n", ".meta/provenance.json": json.dumps(provenance, indent=2, sort_keys=True) + "\n", ".meta/tests.toml": "[visible]\ndescription = \"public domain API, leap boundaries, and endpoint policy\"\n\n[hidden]\ndescription = \"Gregorian century rules, invalid relations, duplicate records, equality boundaries, and deterministic diagnostics\"\n", "task.h": data["header"], "task.cpp": data["starter"], ".meta/example.h": data["header"], ".meta/example.cpp": data["reference"], "task_visible_test.cpp": data["visible"], ".meta/task_hidden_test.cpp": data["hidden"], "CMakeLists.txt": _cmake()}
        files = task_named_files(root, files)
        for relative, content in files.items():
            _write(root / relative, content, force)
        roots.append(root)
    return tuple(roots)


def verify(out: Path) -> None:
    if shutil.which("cmake") is None or shutil.which("c++") is None:
        raise RuntimeError("verification requires cmake and c++")
    for spec in TASKS:
        root = out / spec.task_id
        with tempfile.TemporaryDirectory(prefix="date-difference-curriculum-") as temporary:
            copied = Path(temporary) / root.name
            shutil.copytree(root, copied)
            reference = copied / ".meta" / "example.cpp"
            for name, flags in (("normal", []), ("sanitizer", ["-DCMAKE_CXX_FLAGS=-fsanitize=address,undefined", "-DCMAKE_EXE_LINKER_FLAGS=-fsanitize=address,undefined"])):
                build_dir = copied / f"build-{name}"
                subprocess.run(["cmake", "-S", str(copied), "-B", str(build_dir), f"-DTASK_SOURCE={reference}", *flags], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["cmake", "--build", str(build_dir), "--parallel", "2"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                subprocess.run(["ctest", "--test-dir", str(build_dir), "--output-on-failure"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize local Aider-format date-difference curriculum tasks.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    roots = build(args.out, args.force)
    if args.verify:
        verify(args.out)
    print(f"Wrote {len(roots)} date-difference curriculum tasks under {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
